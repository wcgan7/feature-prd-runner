"""Format and summarize runner events and verification logs."""

import json
import re
from pathlib import Path
from typing import Any


_FAILED_RE = re.compile(r"^FAILED\s+(\S+)", re.M)
_ASSERT_RE = re.compile(r"^(E\s+.+)$", re.M)
_FAILURE_HEADER_RE = re.compile(r"^_{5,}\s*(.+?)\s*_{5,}$", re.M)


def summarize_pytest_failures(log_text: str, max_failed: int = 5) -> dict[str, object]:
    """Summarize pytest failures from a raw log.

    Args:
        log_text: Full pytest output text.
        max_failed: Maximum number of `FAILED ...` entries to capture.

    Returns:
        A dictionary with keys `failed`, `headline`, and `first_error`.
    """
    if not log_text:
        return {"failed": [], "headline": None, "first_error": None}

    failed = _FAILED_RE.findall(log_text)[:max_failed]

    # Grab first "E   ..." line (usually the key assertion or exception)
    m_err = _ASSERT_RE.search(log_text)
    first_error = m_err.group(1).strip() if m_err else None

    # Optional: failure section title like "test_xxx"
    m_head = _FAILURE_HEADER_RE.search(log_text)
    headline = m_head.group(1).strip() if m_head else None

    return {"failed": failed, "headline": headline, "first_error": first_error}


def summarize_event(event: Any, run_dir: Path | None = None) -> dict[str, Any]:
    """Render a compact, JSON-friendly summary of an event object.

    Args:
        event: Event model instance (or None).
        run_dir: Optional run directory used to attach related artifact paths.

    Returns:
        A dictionary suitable for logging or serialization.
    """
    if event is None:
        return {"event": None}

    event_name = event.__class__.__name__
    d: dict[str, Any] = {"event": event_name}

    run_id = getattr(event, "run_id", None)
    if run_id is not None:
        d["run_id"] = run_id

    step = getattr(event, "step", None)
    if step is not None:
        d["step"] = getattr(step, "value", str(step))

    if run_dir is not None:
        d["run_dir"] = str(run_dir)
        if event_name in {"WorkerFailed", "WorkerSucceeded", "AllowlistViolation"}:
            d["manifest"] = str(run_dir / "manifest.json")
        if event_name == "VerificationResult":
            d["verify_manifest"] = str(run_dir / "verify_manifest.json")

    if event_name == "WorkerFailed":
        d["error_type"] = getattr(event, "error_type", None)
        detail = str(getattr(event, "error_detail", "") or "")
        d["error_detail"] = (detail[:240] + "…") if len(detail) > 240 else detail
        d["timed_out"] = bool(getattr(event, "timed_out", False))
        d["no_heartbeat"] = bool(getattr(event, "no_heartbeat", False))
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])
        d["changed_n"] = len(getattr(event, "changed_files", []) or [])
        stderr_tail = str(getattr(event, "stderr_tail", "") or "").strip()
        if stderr_tail:
            d["stderr_tail"] = (stderr_tail[:240] + "…") if len(stderr_tail) > 240 else stderr_tail

    elif event_name == "WorkerSucceeded":
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])
        d["changed_n"] = len(getattr(event, "changed_files", []) or [])
        d["repo_dirty"] = bool(getattr(event, "repo_dirty", False))
        if d.get("step") == "plan_impl":
            d["plan_valid"] = bool(getattr(event, "plan_valid", False))
            issue = getattr(event, "plan_issue", None)
            if issue:
                d["plan_issue"] = issue

    elif event_name == "VerificationResult":
        d["passed"] = bool(getattr(event, "passed", False))
        d["exit_code"] = getattr(event, "exit_code", None)
        d["needs_expansion"] = bool(getattr(event, "needs_allowlist_expansion", False))
        paths = getattr(event, "failing_paths", []) or []
        d["expansion_n"] = len(paths)
        d["expansion_sample"] = paths[:3]
        d["error_type"] = getattr(event, "error_type", None)

    elif event_name == "ReviewResult":
        d["valid"] = bool(getattr(event, "valid", False))
        d["blocking"] = bool(getattr(event, "blocking_severities_present", False))
        d["blocking_n"] = len(getattr(event, "issues", []) or [])

    elif event_name == "AllowlistViolation":
        d["disallowed_n"] = len(getattr(event, "disallowed_paths", []) or [])
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])

    return d


def pretty(obj: Any, *, indent: int = 2) -> str:
    """Serialize an object as JSON for readable logs.

    Args:
        obj: Object to serialize.
        indent: Indentation level for JSON output.

    Returns:
        A JSON string when possible; otherwise `str(obj)`.
    """
    try:
        return json.dumps(obj, indent=indent, default=str)
    except Exception:
        return str(obj)
