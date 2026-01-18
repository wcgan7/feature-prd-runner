"""Calculate real metrics from runner state and events."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class RunMetrics:
    """Comprehensive run metrics calculated from actual data."""

    # Resource usage
    tokens_used: int = 0
    api_calls: int = 0
    estimated_cost_usd: float = 0.0

    # Timing (in seconds)
    wall_time_seconds: float = 0.0
    worker_time_seconds: float = 0.0
    verification_time_seconds: float = 0.0
    review_time_seconds: float = 0.0

    # Progress
    phases_completed: int = 0
    phases_total: int = 0
    tasks_done: int = 0
    tasks_total: int = 0

    # Code changes
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0

    # Errors
    worker_failures: int = 0
    verification_failures: int = 0
    allowlist_violations: int = 0
    review_blockers: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "tokens_used": self.tokens_used,
            "api_calls": self.api_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 2),
            "wall_time_seconds": round(self.wall_time_seconds, 2),
            "worker_time_seconds": round(self.worker_time_seconds, 2),
            "verification_time_seconds": round(self.verification_time_seconds, 2),
            "review_time_seconds": round(self.review_time_seconds, 2),
            "phases_completed": self.phases_completed,
            "phases_total": self.phases_total,
            "tasks_done": self.tasks_done,
            "tasks_total": self.tasks_total,
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "worker_failures": self.worker_failures,
            "verification_failures": self.verification_failures,
            "allowlist_violations": self.allowlist_violations,
            "review_blockers": self.review_blockers,
        }


class MetricsCalculator:
    """Calculate metrics from runner state files."""

    def __init__(self, project_dir: Path):
        """Initialize calculator with project directory.

        Args:
            project_dir: Path to the project root directory.
        """
        self.project_dir = project_dir
        self.state_dir = project_dir / ".prd_runner"
        self.artifacts_dir = self.state_dir / "artifacts"
        self.runs_dir = self.state_dir / "runs"

    def calculate_metrics(self) -> RunMetrics:
        """Calculate comprehensive metrics from all available data.

        Returns:
            RunMetrics object with calculated values.
        """
        metrics = RunMetrics()

        # Calculate from events
        self._calculate_from_events(metrics)

        # Calculate from task queue and phase plan
        self._calculate_progress(metrics)

        # Calculate from git diff
        self._calculate_git_stats(metrics)

        # Calculate timing from runs
        self._calculate_timing(metrics)

        return metrics

    def _calculate_from_events(self, metrics: RunMetrics) -> None:
        """Parse events.jsonl to extract metrics.

        Args:
            metrics: RunMetrics object to populate.
        """
        events_path = self.artifacts_dir / "events.jsonl"
        if not events_path.exists():
            return

        try:
            with open(events_path) as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        event = json.loads(line)
                        event_type = event.get("event_type", "")

                        # Count failures
                        if event_type == "worker_failed":
                            metrics.worker_failures += 1
                        elif event_type == "allowlist_violation":
                            metrics.allowlist_violations += 1
                        elif event_type == "verification_result":
                            if not event.get("passed", True):
                                metrics.verification_failures += 1
                        elif event_type == "review_result":
                            if event.get("has_blocking_issues", False):
                                metrics.review_blockers += 1

                    except json.JSONDecodeError:
                        continue

        except Exception:
            pass

    def _calculate_progress(self, metrics: RunMetrics) -> None:
        """Calculate progress from task_queue.yaml and phase_plan.yaml.

        Args:
            metrics: RunMetrics object to populate.
        """
        # Get phase progress
        phase_plan_path = self.state_dir / "phase_plan.yaml"
        if phase_plan_path.exists():
            try:
                with open(phase_plan_path) as f:
                    phase_plan = yaml.safe_load(f) or {}
                    phases = phase_plan.get("phases", [])
                    metrics.phases_total = len(phases)
            except Exception:
                pass

        # Get task progress
        task_queue_path = self.state_dir / "task_queue.yaml"
        if task_queue_path.exists():
            try:
                with open(task_queue_path) as f:
                    task_queue = yaml.safe_load(f) or {}
                    tasks = task_queue.get("tasks", [])
                    metrics.tasks_total = len(tasks)

                    # Count done tasks and phases
                    done_phases = set()
                    for task in tasks:
                        lifecycle = task.get("lifecycle", "")
                        if lifecycle == "done":
                            metrics.tasks_done += 1
                            phase_id = task.get("phase_id")
                            if phase_id:
                                done_phases.add(phase_id)

                    metrics.phases_completed = len(done_phases)

            except Exception:
                pass

    def _calculate_git_stats(self, metrics: RunMetrics) -> None:
        """Calculate code changes from git diff.

        Args:
            metrics: RunMetrics object to populate.
        """
        try:
            # Get list of changed files since main branch
            result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                changed_files = [
                    f for f in result.stdout.strip().split("\n") if f and not f.startswith(".prd_runner")
                ]
                metrics.files_changed = len(changed_files)

            # Get line stats
            result = subprocess.run(
                ["git", "diff", "--numstat", "origin/main...HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        # Skip .prd_runner files
                        if parts[2].startswith(".prd_runner"):
                            continue
                        try:
                            added = int(parts[0]) if parts[0] != "-" else 0
                            removed = int(parts[1]) if parts[1] != "-" else 0
                            metrics.lines_added += added
                            metrics.lines_removed += removed
                        except ValueError:
                            continue

        except Exception:
            # Fallback: try diff against current branch point
            try:
                result = subprocess.run(
                    ["git", "diff", "--shortstat", "HEAD^"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if result.returncode == 0 and result.stdout:
                    # Parse: " 5 files changed, 120 insertions(+), 45 deletions(-)"
                    output = result.stdout.strip()
                    if "insertion" in output:
                        parts = output.split(",")
                        for part in parts:
                            if "insertion" in part:
                                metrics.lines_added = int(part.strip().split()[0])
                            elif "deletion" in part:
                                metrics.lines_removed = int(part.strip().split()[0])
                            elif "file" in part:
                                metrics.files_changed = int(part.strip().split()[0])

            except Exception:
                pass

    def _calculate_timing(self, metrics: RunMetrics) -> None:
        """Calculate timing metrics from run directories.

        Args:
            metrics: RunMetrics object to populate.
        """
        if not self.runs_dir.exists():
            return

        run_dirs = [d for d in self.runs_dir.iterdir() if d.is_dir()]
        if not run_dirs:
            return

        # Find most recent run based on directory name (run-YYYYMMDD-HHMMSS-*)
        latest_run = max(run_dirs, key=lambda d: d.name)

        # Try to parse progress.json for timing info
        progress_path = latest_run / "progress.json"
        if progress_path.exists():
            try:
                with open(progress_path) as f:
                    progress = json.load(f)

                    # Extract timing info if available
                    started_at = progress.get("started_at")
                    heartbeat = progress.get("heartbeat")

                    if started_at and heartbeat:
                        try:
                            start_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                            end_time = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
                            metrics.wall_time_seconds = (end_time - start_time).total_seconds()
                        except Exception:
                            pass

                    # Extract token/cost info if available (from future implementations)
                    metrics.tokens_used = progress.get("tokens_used", 0)
                    metrics.api_calls = progress.get("api_calls", 0)
                    metrics.estimated_cost_usd = progress.get("estimated_cost_usd", 0.0)

            except Exception:
                pass

        # Calculate verification and review time from log files
        for run_dir in run_dirs:
            # Check for verification logs
            verify_logs = list(run_dir.glob("verify_output_*.txt"))
            for log in verify_logs:
                try:
                    stats = log.stat()
                    # Rough estimate: assume 1 second per 10KB of log
                    metrics.verification_time_seconds += stats.st_size / 10000
                except Exception:
                    pass

            # Check for review files
            review_files = list(run_dir.glob("review_*.json"))
            for review_file in review_files:
                # Rough estimate: 5 seconds per review
                metrics.review_time_seconds += 5

    def get_phase_metrics(self, phase_id: str) -> dict[str, Any]:
        """Get metrics for a specific phase.

        Args:
            phase_id: The phase identifier.

        Returns:
            Dictionary with phase-specific metrics.
        """
        # This could be expanded to track per-phase metrics
        return {
            "phase_id": phase_id,
            "completed": False,
            "tasks_done": 0,
            "tasks_total": 0,
        }


def calculate_metrics(project_dir: Path) -> RunMetrics:
    """Calculate metrics for a project.

    Args:
        project_dir: Path to the project directory.

    Returns:
        RunMetrics object with calculated values.
    """
    calculator = MetricsCalculator(project_dir)
    return calculator.calculate_metrics()
