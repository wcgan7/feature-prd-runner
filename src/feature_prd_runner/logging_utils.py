from typing import Any

def summarize_event(event: Any) -> dict[str, Any]:
    d: dict[str, Any] = {"event": event.__class__.__name__}

    if hasattr(event, "run_id"):
        d["run_id"] = event.run_id
    if hasattr(event, "step"):
        d["step"] = getattr(event, "step", None)

    # WorkerFailed
    if event.__class__.__name__ == "WorkerFailed":
        d["error_type"] = getattr(event, "error_type", None)
        detail = str(getattr(event, "error_detail", "") or "")
        d["error_detail"] = (detail[:240] + "…") if len(detail) > 240 else detail
        d["timed_out"] = bool(getattr(event, "timed_out", False))
        d["no_heartbeat"] = bool(getattr(event, "no_heartbeat", False))
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])
        d["changed_n"] = len(getattr(event, "changed_files", []) or [])

    # WorkerSucceeded
    if event.__class__.__name__ == "WorkerSucceeded":
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])
        d["changed_n"] = len(getattr(event, "changed_files", []) or [])
        d["repo_dirty"] = bool(getattr(event, "repo_dirty", False))
        if getattr(event, "step", None) and str(getattr(event, "step")) == "TaskStep.PLAN_IMPL":
            d["plan_valid"] = bool(getattr(event, "plan_valid", False))
            issue = getattr(event, "plan_issue", None)
            if issue:
                d["plan_issue"] = issue

    # VerificationResult
    if event.__class__.__name__ == "VerificationResult":
        d["passed"] = bool(getattr(event, "passed", False))
        d["exit_code"] = getattr(event, "exit_code", None)
        d["needs_expansion"] = bool(getattr(event, "needs_allowlist_expansion", False))
        d["expansion_n"] = len(getattr(event, "failing_paths", []) or [])
        d["error_type"] = getattr(event, "error_type", None)

    # ReviewResult
    if event.__class__.__name__ == "ReviewResult":
        d["valid"] = bool(getattr(event, "valid", False))
        d["blocking"] = bool(getattr(event, "blocking_severities_present", False))
        d["blocking_n"] = len(getattr(event, "issues", []) or [])

    # AllowlistViolation
    if event.__class__.__name__ == "AllowlistViolation":
        d["disallowed_n"] = len(getattr(event, "disallowed_paths", []) or [])
        d["introduced_n"] = len(getattr(event, "introduced_changes", []) or [])

    return d
