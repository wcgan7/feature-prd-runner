from __future__ import annotations

import shlex
from pathlib import Path
from typing import Optional

from loguru import logger

from ..git_utils import _path_is_allowed
from ..io_utils import _save_data
from ..logging_utils import summarize_pytest_failures
from ..models import VerificationResult
from ..signals import (
    build_allowed_files,
    extract_paths_from_log,
    extract_failed_test_files,
    extract_failures_section,
    extract_traceback_repo_paths,
    filter_repo_file_paths,
    infer_suspect_source_files,
)
from ..tasks import _resolve_test_command, _tests_log_path
from ..utils import _now_iso
from ..worker import _capture_test_result_snapshot, _run_command
from ..io_utils import _read_text_window


def _is_pytest_command(command: str) -> bool:
    cmd = (command or "").strip()
    if not cmd:
        return False

    # Fast-path common prefixes.
    if cmd.startswith("pytest"):
        return True
    if cmd.startswith("python") and " -m pytest" in cmd:
        return True

    # Tokenize and look for pytest invocation behind common wrappers
    # (poetry/uv/pipenv/hatch) or other prefixes.
    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()
    tokens = [t for t in tokens if t]
    if not tokens:
        return False

    if "pytest" in tokens:
        return True

    # python -m pytest ...
    if "python" in tokens:
        for i, tok in enumerate(tokens[:-1]):
            if tok == "-m" and tokens[i + 1] == "pytest":
                return True

    return False



def run_verify_action(
    *,
    project_dir: Path,
    artifacts_dir: Path,
    run_dir: Path,
    phase: Optional[dict],
    task: dict,
    run_id: str,
    plan_data: dict,
    default_test_command: Optional[str],
    timeout_seconds: int,
) -> VerificationResult:
    phase_id = str(phase.get("id") if phase else task.get("phase_id") or task.get("id"))
    test_command = _resolve_test_command(phase, task, default_test_command)
    allowed_files = build_allowed_files(plan_data)

    logger.info(
        "Running verification: command={} phase={}",
        test_command,
        phase_id,
    )

    # Add robust pytest flags if pytest is the test command
    if test_command:
        if test_command.strip().startswith("pytest") and "--tb=" not in test_command:
            test_command += " --tb=long"
        if test_command.strip().startswith("pytest") and "--disable-warnings" not in test_command:
            test_command += " --disable-warnings"
        if test_command.strip().startswith("pytest") and "-q" not in test_command.split():
            test_command += " -q"

    if not test_command:
        logger.info("Running verification: no test command configured (phase={})", phase_id)
        return VerificationResult(
            run_id=run_id,
            passed=True,
            command=None,
            exit_code=0,
            log_path=None,
            log_tail="No test command configured",
            captured_at=_now_iso(),
            failing_paths=[],
            needs_allowlist_expansion=False,
            error_type=None,
        )
    else:
        logger.info("Running verification: command={} phase={}", test_command, phase_id)

    log_path = _tests_log_path(artifacts_dir, phase_id)
    result = _run_command(
        test_command,
        project_dir,
        log_path,
        timeout_seconds=timeout_seconds,
    )
    snapshot = _capture_test_result_snapshot(
        command=test_command,
        exit_code=result["exit_code"],
        log_path=Path(result["log_path"]),
    )
    log_tail = snapshot.get("log_tail", "")

    excerpt_text, excerpt_truncated = _read_text_window(Path(result["log_path"]), max_chars=120_000)

    is_pytest = _is_pytest_command(test_command)
    if is_pytest:
        fail_text = extract_failures_section(excerpt_text)
        excerpt_kind = "pytest_failures"
        excerpt_path = run_dir / "pytest_failures.txt"
    else:
        fail_text = excerpt_text
        excerpt_kind = "verify_output"
        excerpt_path = run_dir / "verify_output.txt"

    excerpt_path.write_text(fail_text)

    # Part 1: Extract failing test files from stable pytest markers
    failed_test_files = extract_failed_test_files(fail_text, project_dir) if is_pytest else []

    # Part 2: Extract source files from tracebacks (when present)
    trace_files = extract_traceback_repo_paths(fail_text, project_dir)

    # Part 3: Infer suspect source files from test imports when tracebacks don't show them
    # Only infer if trace_files doesn't contain any src/ files
    src_in_traces = [p for p in trace_files if p.startswith("src/")]
    if not src_in_traces and failed_test_files:
        suspect_source_files = infer_suspect_source_files(failed_test_files, project_dir)
    else:
        suspect_source_files = []

    candidate_paths = []
    if not is_pytest:
        candidate_paths = filter_repo_file_paths(extract_paths_from_log(fail_text, project_dir), project_dir)
        candidate_paths = [
            p
            for p in candidate_paths
            if (p.startswith("src/") or p.startswith("tests/")) and p.endswith(".py")
        ]

    # Combine all signals into failing_repo_paths
    failing_repo_paths = sorted(
        set(failed_test_files) | set(trace_files) | set(suspect_source_files) | set(candidate_paths)
    )

    # Exclude internal/noise directories
    EXCLUDE_PREFIXES = (
        ".git/", ".prd_runner/", ".venv/", "venv/", "__pycache__/",
        ".pytest_cache/", ".mypy_cache/", ".ruff_cache/", ".tox/", ".nox/",
    )
    failing_repo_paths = [p for p in failing_repo_paths if not p.startswith(EXCLUDE_PREFIXES)]
    failing_paths = sorted(failing_repo_paths)

    meaningful_allowlist = [p for p in allowed_files if p and p != "README.md"]
    if not meaningful_allowlist:
        outside = []
        needs_expansion = False
    else:
        outside = [p for p in failing_paths if not _path_is_allowed(project_dir, p, allowed_files)]
        needs_expansion = bool(outside)
    
    expansion_paths = outside if needs_expansion else []

    logger.debug("Verify failing_repo_paths: {}", failing_paths)
    logger.debug("Verify expansion_paths: {}", expansion_paths)
    logger.debug(
        "Verify allowlist_used={}",
        allowed_files,
    )
    
    timed_out = bool(result.get("timed_out"))
    passed = result["exit_code"] == 0 and not timed_out
    error_type = "test_timeout" if timed_out else None
    
    if not passed:
        summary = summarize_pytest_failures(log_tail, max_failed=5)
        failed = summary.get("failed") or []
        first_error = summary.get("first_error")

        if failed:
            logger.info("Tests failed: {}", ", ".join(failed))
        elif failing_paths:
            logger.info("Failing files: {}", ", ".join(failing_paths[:5]))

        if first_error:
            logger.info("First error: {}", first_error)

    if needs_expansion:
        logger.info("Verification failed; switching to PLAN_IMPL (expand allowlist)")
        logger.info("Expansion paths: {}", expansion_paths)
    elif not passed:
        logger.info("Verification failed; retrying IMPLEMENT (fix tests)")
    else:
        logger.info("Verification passed")

    event = VerificationResult(
        run_id=run_id,
        passed=passed,
        command=test_command,
        exit_code=int(result["exit_code"]),
        log_path=result["log_path"],
        log_tail=log_tail,
        captured_at=snapshot.get("captured_at", _now_iso()),
        failing_paths=expansion_paths,
        needs_allowlist_expansion=needs_expansion,
        error_type=error_type,
    )
    
    verify_manifest = {
        "run_id": run_id,
        "task_id": str(task.get("id")),
        "phase_id": str(task.get("phase_id") or task.get("id") or ""),
        "step": "verify",
        "command": event.command,
        "exit_code": int(event.exit_code),
        "passed": bool(event.passed),
        "error_type": getattr(event, "error_type", None) or None,
        "timed_out": timed_out,
        "log_path": str(event.log_path),
        "log_tail": str(event.log_tail or ""),
        "captured_at": str(event.captured_at),
        "needs_allowlist_expansion": bool(getattr(event, "needs_allowlist_expansion", False)),
        "failing_paths": list(getattr(event, "failing_paths", []) or []),
        "allowlist_used": allowed_files,
        # Diagnostic breakdown of all signals
        "excerpt_kind": excerpt_kind,
        "excerpt_path": str(excerpt_path),
        "excerpt_truncated": bool(excerpt_truncated),
        "failed_test_files": failed_test_files,
        "trace_files": trace_files,
        "suspect_source_files": suspect_source_files,
        "candidate_paths": candidate_paths,
        "failing_repo_paths": failing_paths,
        "expansion_paths": expansion_paths,
    }
    _save_data(run_dir / "verify_manifest.json", verify_manifest)
    return event
