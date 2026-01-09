from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from ..models import VerificationResult
    from ..signals import build_allowed_files, extract_paths_from_log, needs_allowlist_expansion
    from ..tasks import _resolve_test_command, _tests_log_path
    from ..utils import _now_iso
    from ..worker import _capture_test_result_snapshot, _run_command
except ImportError:  # pragma: no cover
    from models import VerificationResult
    from signals import build_allowed_files, extract_paths_from_log, needs_allowlist_expansion
    from tasks import _resolve_test_command, _tests_log_path
    from utils import _now_iso
    from worker import _capture_test_result_snapshot, _run_command


def run_verify_action(
    *,
    project_dir: Path,
    artifacts_dir: Path,
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

    if not test_command:
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
    failing_paths = extract_paths_from_log(log_tail, project_dir)
    needs_expansion = needs_allowlist_expansion(failing_paths, allowed_files, project_dir)
    timed_out = bool(result.get("timed_out"))
    passed = result["exit_code"] == 0 and not timed_out
    error_type = "test_timeout" if timed_out else None

    return VerificationResult(
        run_id=run_id,
        passed=passed,
        command=test_command,
        exit_code=int(result["exit_code"]),
        log_path=result["log_path"],
        log_tail=log_tail,
        captured_at=snapshot.get("captured_at", _now_iso()),
        failing_paths=failing_paths,
        needs_allowlist_expansion=needs_expansion,
        error_type=error_type,
    )
