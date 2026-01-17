"""Test branch creation/switching behavior used by the runner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner import orchestrator
from feature_prd_runner.io_utils import _load_data, _save_data
from feature_prd_runner.models import CommitResult, ReviewResult, TaskStep, VerificationResult, WorkerSucceeded
from feature_prd_runner.state import _ensure_state_files
from feature_prd_runner.utils import _now_iso
from feature_prd_runner.git_utils import _git_current_branch


def test_single_branch_used_across_phases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the runner uses one consistent branch across phases."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")
    paths = _ensure_state_files(project_dir, prd_path)

    _save_data(
        paths["phase_plan"],
        {
            "updated_at": _now_iso(),
            "phases": [
                {"id": "phase-1", "name": "Phase 1", "status": "todo", "description": ""},
                {"id": "phase-2", "name": "Phase 2", "status": "todo", "description": ""},
            ],
        },
    )
    _save_data(
        paths["task_queue"],
        {
            "updated_at": _now_iso(),
            "tasks": [
                {
                    "id": "phase-1",
                    "type": "implement",
                    "phase_id": "phase-1",
                    "status": "todo",
                    "lifecycle": "ready",
                    "step": "plan_impl",
                    "priority": 1,
                    "deps": [],
                    "description": "phase 1",
                },
                {
                    "id": "phase-2",
                    "type": "implement",
                    "phase_id": "phase-2",
                    "status": "todo",
                    "lifecycle": "ready",
                    "step": "plan_impl",
                    "priority": 2,
                    "deps": [],
                    "description": "phase 2",
                },
            ],
        },
    )

    ensure_calls: list[str] = []

    def fake_ensure_branch(_project_dir: Path, branch: str) -> None:
        ensure_calls.append(branch)

    def fake_worker_action(**kwargs: Any) -> WorkerSucceeded | ReviewResult:
        step = kwargs["step"]
        run_id = kwargs["run_id"]
        if step == TaskStep.PLAN_IMPL:
            return WorkerSucceeded(step=step, run_id=run_id, plan_valid=True, impl_plan_path="x", impl_plan_hash="y")
        if step == TaskStep.IMPLEMENT:
            return WorkerSucceeded(step=step, run_id=run_id, introduced_changes=["x.py"])
        if step == TaskStep.REVIEW:
            return ReviewResult(
                run_id=run_id,
                mergeable=True,
                issues=[],
                review_path=None,
            )
        raise AssertionError(f"Unexpected worker step: {step}")

    def fake_verify_action(**kwargs: Any) -> VerificationResult:
        return VerificationResult(
            run_id=kwargs["run_id"],
            passed=True,
            command="pytest",
            exit_code=0,
            log_path=None,
            log_tail="",
            captured_at=_now_iso(),
        )

    def fake_commit_action(**kwargs: Any) -> CommitResult:
        return CommitResult(run_id=kwargs["run_id"], committed=True, pushed=True, error=None, repo_clean=True)

    monkeypatch.setattr(orchestrator, "_ensure_branch", fake_ensure_branch)
    monkeypatch.setattr(orchestrator, "run_worker_action", fake_worker_action)
    monkeypatch.setattr(orchestrator, "run_verify_action", fake_verify_action)
    monkeypatch.setattr(orchestrator, "run_commit_action", fake_commit_action)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda *_: None)

    # 2 phases x (plan_impl, implement, verify, review, commit) = 10 iterations
    orchestrator.run_feature_prd(project_dir=project_dir, prd_path=prd_path, max_iterations=10)

    assert ensure_calls
    assert len(set(ensure_calls)) == 1
    branch = ensure_calls[0]
    assert branch

    queue = _load_data(paths["task_queue"], {})
    tasks = {t["id"]: t for t in (queue.get("tasks") or [])}
    assert tasks["phase-1"].get("branch") == branch
    assert tasks["phase-2"].get("branch") == branch


def test_no_new_branch_does_not_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure `--no-new-branch` preserves the current branch."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    # Ensure we're on an actual branch (git init may be enough, but create one commit to be safe).
    (project_dir / "README.md").write_text("x\n")
    subprocess.run(["git", "add", "README.md"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=project_dir, check=True)

    current = _git_current_branch(project_dir)
    assert current and current != "HEAD"

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")
    paths = _ensure_state_files(project_dir, prd_path)

    _save_data(
        paths["phase_plan"],
        {"updated_at": _now_iso(), "phases": [{"id": "phase-1", "name": "Phase 1", "status": "todo", "description": ""}]},
    )
    _save_data(
        paths["task_queue"],
        {
            "updated_at": _now_iso(),
            "tasks": [
                {
                    "id": "phase-1",
                    "type": "implement",
                    "phase_id": "phase-1",
                    "status": "todo",
                    "lifecycle": "ready",
                    "step": "plan_impl",
                    "priority": 1,
                    "deps": [],
                    "description": "phase 1",
                }
            ],
        },
    )

    ensure_calls: list[str] = []

    def fake_ensure_branch(_project_dir: Path, branch: str) -> None:
        ensure_calls.append(branch)

    def fake_worker_action(**kwargs: Any) -> WorkerSucceeded | ReviewResult:
        step = kwargs["step"]
        run_id = kwargs["run_id"]
        if step == TaskStep.PLAN_IMPL:
            return WorkerSucceeded(step=step, run_id=run_id, plan_valid=True, impl_plan_path="x", impl_plan_hash="y")
        if step == TaskStep.IMPLEMENT:
            return WorkerSucceeded(step=step, run_id=run_id, introduced_changes=["x.py"])
        if step == TaskStep.REVIEW:
            return ReviewResult(
                run_id=run_id,
                mergeable=True,
                issues=[],
                review_path=None,
            )
        raise AssertionError(f"Unexpected worker step: {step}")

    def fake_verify_action(**kwargs: Any) -> VerificationResult:
        return VerificationResult(
            run_id=kwargs["run_id"],
            passed=True,
            command="pytest",
            exit_code=0,
            log_path=None,
            log_tail="",
            captured_at=_now_iso(),
        )

    def fake_commit_action(**kwargs: Any) -> CommitResult:
        return CommitResult(run_id=kwargs["run_id"], committed=True, pushed=True, error=None, repo_clean=True)

    monkeypatch.setattr(orchestrator, "_ensure_branch", fake_ensure_branch)
    monkeypatch.setattr(orchestrator, "run_worker_action", fake_worker_action)
    monkeypatch.setattr(orchestrator, "run_verify_action", fake_verify_action)
    monkeypatch.setattr(orchestrator, "run_commit_action", fake_commit_action)
    monkeypatch.setattr(orchestrator.time, "sleep", lambda *_: None)

    orchestrator.run_feature_prd(project_dir=project_dir, prd_path=prd_path, max_iterations=5, new_branch=False)

    assert ensure_calls == []
    queue = _load_data(paths["task_queue"], {})
    task = (queue.get("tasks") or [])[0]
    assert task.get("branch") == current
