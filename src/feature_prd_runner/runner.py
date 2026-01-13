#!/usr/bin/env python3
"""
Feature PRD Runner (FSM)
========================

Coordinator entrypoint for planning, implementing, verifying, reviewing,
and committing changes using a step-based FSM.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from .constants import (
    DEFAULT_HEARTBEAT_GRACE_SECONDS,
    DEFAULT_HEARTBEAT_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_AUTO_RESUMES,
    DEFAULT_SHIFT_MINUTES,
    DEFAULT_STOP_ON_BLOCKING_ISSUES,
    STATE_DIR_NAME,
)
from .orchestrator import run_feature_prd
from .prompts import _build_phase_prompt, _build_plan_prompt, _build_review_prompt
from .io_utils import _load_data, _load_data_with_error
from .tasks import (
    _blocking_tasks,
    _normalize_phases,
    _normalize_tasks,
    _phase_for_task,
    _read_progress_human_blockers,
    _select_next_task,
    _summarize_blocking_tasks,
    _task_summary,
 )


__all__ = [
    "run_feature_prd",
    "_build_phase_prompt",
    "_build_plan_prompt",
    "_build_review_prompt",
    "_read_progress_human_blockers",
]

def _configure_logging(level: str = "INFO") -> None:
    """Configure loguru logger with the specified level."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{module}</cyan>:<cyan>{line}</cyan>\n"
            "{message}"
        ),
    )


# Initialize with default level; will be reconfigured in main() based on CLI args
_configure_logging()


def _build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Feature PRD Runner - autonomous feature implementation coordinator",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help="Project directory (default: current directory)",
    )
    parser.add_argument(
        "--prd-file",
        type=Path,
        required=True,
        help="Path to feature PRD file",
    )
    parser.add_argument(
        "--codex-command",
        type=str,
        default="codex exec -",
        help="Codex CLI command (default: codex exec -)",
    )
    parser.add_argument(
        "--test-command",
        type=str,
        default=None,
        help="Global test command to run after each phase",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (default: unlimited)",
    )
    parser.add_argument(
        "--shift-minutes",
        type=int,
        default=DEFAULT_SHIFT_MINUTES,
        help=f"Timebox per Codex run in minutes (default: {DEFAULT_SHIFT_MINUTES})",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=DEFAULT_HEARTBEAT_SECONDS,
        help=f"Heartbeat interval in seconds (default: {DEFAULT_HEARTBEAT_SECONDS})",
    )
    parser.add_argument(
        "--heartbeat-grace-seconds",
        type=int,
        default=DEFAULT_HEARTBEAT_GRACE_SECONDS,
        help=(
            "Allowed heartbeat staleness before termination "
            f"(default: {DEFAULT_HEARTBEAT_GRACE_SECONDS})"
        ),
    )
    parser.add_argument(
        "--max-task-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=f"Max attempts per task before blocking (default: {DEFAULT_MAX_ATTEMPTS})",
    )
    parser.add_argument(
        "--max-auto-resumes",
        type=int,
        default=DEFAULT_MAX_AUTO_RESUMES,
        help=f"Max auto-resumes for transient failures (default: {DEFAULT_MAX_AUTO_RESUMES})",
    )
    parser.add_argument(
        "--stop-on-blocking-issues",
        default=DEFAULT_STOP_ON_BLOCKING_ISSUES,
        action=argparse.BooleanOptionalAction,
        help=(
            "Stop when a task is blocked and requires human intervention "
            "(default: True)"
        ),
    )
    parser.add_argument(
        "--resume-blocked",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Resume the most recent blocked task automatically (default: True)",
    )
    parser.add_argument(
        "--custom-prompt",
        type=str,
        default=None,
        help=(
            "Standalone prompt to execute before continuing implementation. "
            "The agent must complete the instructions successfully; if blocked, "
            "requires human intervention before continuing."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Set logging level (default: info)",
    )
    parser.add_argument(
        "--simple-review",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Use simplified review output schema (mergeable + issues only, default: True)",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Archive and recreate .prd_runner state before starting",
    )
    parser.add_argument(
        "--require-clean",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Refuse to run if git working tree has changes outside .prd_runner (default: True)",
    )
    parser.add_argument(
        "--commit",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Enable git commit step (default: True)",
    )
    parser.add_argument(
        "--push",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Enable git push during commit step (default: True)",
    )
    return parser


def _build_status_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Feature PRD Runner - show current .prd_runner state",
    )
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("."),
        help="Project directory (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON",
    )
    return parser


def _status_command(project_dir: Path, *, as_json: bool = False) -> int:
    project_dir = project_dir.resolve()
    state_dir = project_dir / STATE_DIR_NAME
    run_state_path = state_dir / "run_state.yaml"
    task_queue_path = state_dir / "task_queue.yaml"
    phase_plan_path = state_dir / "phase_plan.yaml"
    runs_dir = state_dir / "runs"
    blocked_report_path = state_dir / "runner_blocked.json"

    if not state_dir.exists():
        if as_json:
            sys.stdout.write('{"status":"missing_state_dir"}\n')
        else:
            sys.stdout.write(f"No state directory found at {state_dir}\n")
        return 0

    run_state, run_state_err = _load_data_with_error(run_state_path, {})
    queue, queue_err = _load_data_with_error(task_queue_path, {})
    plan, plan_err = _load_data_with_error(phase_plan_path, {})
    errors = [e for e in [run_state_err, queue_err, plan_err] if e]

    blocked_report = _load_data(blocked_report_path, {}) if blocked_report_path.exists() else {}

    tasks = _normalize_tasks(queue)
    phases = _normalize_phases(plan)
    next_task = _select_next_task(tasks) if tasks else None
    blockers = _blocking_tasks(tasks)

    payload = {
        "project_dir": str(project_dir),
        "state_dir": str(state_dir),
        "errors": errors,
        "run_state": run_state,
        "task_summary": _task_summary(tasks),
        "next_task": next_task,
        "blocking_tasks": blockers,
        "blocking_summary": _summarize_blocking_tasks(blockers),
        "blocked_report": blocked_report or None,
    }
    if as_json:
        import json

        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 2 if errors else 0

    sys.stdout.write(f"Project: {project_dir}\n")
    sys.stdout.write(f"State:   {state_dir}\n")
    if errors:
        sys.stdout.write("State errors:\n")
        for err in errors:
            sys.stdout.write(f"- {err}\n")

    status = run_state.get("status") or "unknown"
    sys.stdout.write(f"Run status: {status}\n")
    last_error = run_state.get("last_error")
    if last_error:
        sys.stdout.write(f"Last error: {last_error}\n")
    current_task_id = run_state.get("current_task_id")
    current_phase_id = run_state.get("current_phase_id")
    run_id = run_state.get("run_id")
    last_run_id = run_state.get("last_run_id")
    branch = run_state.get("branch")
    if current_task_id or current_phase_id or run_id:
        sys.stdout.write(
            f"Current: task={current_task_id or '-'} phase={current_phase_id or '-'} run_id={run_id or '-'}\n"
        )
    if branch:
        sys.stdout.write(f"Branch:  {branch}\n")

    summary = _task_summary(tasks)
    sys.stdout.write(
        "Tasks: "
        + ", ".join(f"{k}={v}" for k, v in summary.items())
        + f" (total={len(tasks)})\n"
    )
    if next_task:
        phase = _phase_for_task(phases, next_task)
        phase_name = (phase or {}).get("name") or (phase or {}).get("id")
        sys.stdout.write(
            f"Next:   {next_task.get('id')} step={next_task.get('step')} "
            f"lifecycle={next_task.get('lifecycle')} phase={phase_name or '-'}\n"
        )

    if blockers:
        sys.stdout.write(f"Blocked: {len(blockers)}\n")
        sys.stdout.write(_summarize_blocking_tasks(blockers) + "\n")
        for task in blockers[:5]:
            sys.stdout.write(
                f"- {task.get('id')}: {task.get('last_error_type') or 'unknown'}: {task.get('last_error') or ''}\n"
            )
    if blocked_report:
        sys.stdout.write(
            f"Runner blocked report: {blocked_report.get('error_type')}: {blocked_report.get('summary')}\n"
        )
        sys.stdout.write(f"Details: {blocked_report_path}\n")

    if last_run_id and (runs_dir / str(last_run_id)).exists():
        sys.stdout.write(f"Last run dir: {runs_dir / str(last_run_id)}\n")
    elif last_run_id:
        sys.stdout.write(f"Last run id: {last_run_id}\n")

    return 2 if errors else 0


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "status":
        args = _build_status_parser().parse_args(argv[1:])
        raise SystemExit(_status_command(args.project_dir, as_json=bool(args.json)))

    parser = _build_run_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.log_level)
    run_feature_prd(
        project_dir=args.project_dir,
        prd_path=args.prd_file,
        codex_command=args.codex_command,
        max_iterations=args.max_iterations,
        shift_minutes=args.shift_minutes,
        heartbeat_seconds=args.heartbeat_seconds,
        heartbeat_grace_seconds=args.heartbeat_grace_seconds,
        max_attempts=args.max_task_attempts,
        max_auto_resumes=args.max_auto_resumes,
        test_command=args.test_command,
        custom_prompt=args.custom_prompt,
        stop_on_blocking_issues=args.stop_on_blocking_issues,
        resume_blocked=args.resume_blocked,
        simple_review=args.simple_review,
        reset_state=args.reset_state,
        require_clean=args.require_clean,
        commit_enabled=args.commit,
        push_enabled=args.push,
    )


if __name__ == "__main__":
    main()
