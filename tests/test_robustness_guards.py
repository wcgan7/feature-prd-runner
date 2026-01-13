import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner import orchestrator
from feature_prd_runner.io_utils import _load_data, _save_data
from feature_prd_runner.state import _ensure_state_files
from feature_prd_runner.utils import _now_iso
from feature_prd_runner.utils import _hash_file


def test_corrupted_task_queue_does_not_get_overwritten(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")

    paths = _ensure_state_files(project_dir, prd_path)
    bad_yaml = "tasks: [this is not valid yaml\n"
    paths["task_queue"].write_text(bad_yaml)

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        max_iterations=1,
    )

    assert paths["task_queue"].read_text() == bad_yaml
    blocked = _load_data(paths["state_dir"] / "runner_blocked.json", {})
    assert blocked.get("error_type") == "state_corrupt"
    errors = blocked.get("details", {}).get("errors", [])
    assert any("task_queue.yaml" in str(err) for err in errors)


def test_prd_mismatch_blocks_without_reset(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd1 = project_dir / "prd1.md"
    prd1.write_text("Spec 1\n")
    prd2 = project_dir / "prd2.md"
    prd2.write_text("Spec 2\n")

    _ensure_state_files(project_dir, prd1)

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd2,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "prd_mismatch"


def test_prd_content_change_blocks_without_reset(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd = project_dir / "prd.md"
    prd.write_text("Spec 1\n")

    paths = _ensure_state_files(project_dir, prd)
    run_state = _load_data(paths["run_state"], {})
    run_state["prd_hash"] = _hash_file(str(prd))
    _save_data(paths["run_state"], run_state)

    # Update PRD content in-place.
    prd.write_text("Spec 2\n")

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "prd_mismatch"


def test_reset_state_allows_new_prd(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd1 = project_dir / "prd1.md"
    prd1.write_text("Spec 1\n")
    prd2 = project_dir / "prd2.md"
    prd2.write_text("Spec 2\n")

    _ensure_state_files(project_dir, prd1)

    def fake_run_worker_action(**kwargs):
        # Create a minimal valid phase plan to keep the loop safe.
        phase_plan_path = kwargs["phase_plan_path"]
        task_queue_path = kwargs["task_queue_path"]
        _save_data(
            phase_plan_path,
            {"updated_at": _now_iso(), "phases": [{"id": "phase-1", "name": "P1", "status": "todo", "description": ""}]},
        )
        _save_data(task_queue_path, {"updated_at": _now_iso(), "tasks": []})
        from feature_prd_runner.models import WorkerSucceeded, TaskStep

        return WorkerSucceeded(step=TaskStep.PLAN_IMPL, run_id=kwargs["run_id"])

    monkeypatch.setattr(orchestrator, "run_worker_action", fake_run_worker_action)

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd2,
        reset_state=True,
        max_iterations=1,
    )

    run_state = _load_data(project_dir / ".prd_runner" / "run_state.yaml", {})
    assert Path(run_state.get("prd_path")).resolve() == prd2.resolve()


def test_require_clean_blocks_dirty_repo(tmp_path: Path) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)
    # Make dirty via an untracked file (no git config needed).
    (project_dir / "untracked.txt").write_text("hello\n")

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        require_clean=True,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "dirty_worktree"


def test_reset_state_failure_blocks(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")

    # Create a state dir so reset-state has something to move.
    state_dir = project_dir / ".prd_runner"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "run_state.yaml").write_text("status: idle\n")

    import feature_prd_runner.state as state_module

    def boom(*args, **kwargs):
        raise OSError("nope")

    monkeypatch.setattr(state_module.shutil, "move", boom)

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        reset_state=True,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "state_reset_failed"


def test_invalid_phase_plan_schema_blocks(tmp_path: Path) -> None:
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
                {"id": "phase-1", "name": "P1", "status": "todo", "description": ""},
                {"id": "phase-1", "name": "P1-dup", "status": "todo", "description": ""},
            ],
        },
    )

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "state_invalid"
    issues = blocked.get("details", {}).get("issues", [])
    assert any("duplicate phase ids" in str(item) for item in issues)


def test_invalid_task_queue_schema_blocks(tmp_path: Path) -> None:
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
                {"id": "phase-1", "name": "P1", "status": "todo", "description": ""},
            ],
        },
    )
    _save_data(
        paths["task_queue"],
        {
            "updated_at": _now_iso(),
            "tasks": [
                {"id": "phase-1", "type": "implement", "phase_id": "phase-missing", "deps": []},
            ],
        },
    )

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "state_invalid"
    issues = blocked.get("details", {}).get("issues", [])
    assert any("unknown phase_id" in str(item) for item in issues)


def test_missing_task_type_is_treated_as_implement_for_validation(tmp_path: Path) -> None:
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
                {"id": "phase-1", "name": "P1", "status": "todo", "description": ""},
            ],
        },
    )
    _save_data(
        paths["task_queue"],
        {
            "updated_at": _now_iso(),
            "tasks": [
                # Missing "type" should behave like the runner default ("implement")
                {"id": "t1", "phase_id": "phase-missing", "deps": []},
            ],
        },
    )

    orchestrator.run_feature_prd(
        project_dir=project_dir,
        prd_path=prd_path,
        max_iterations=1,
    )

    blocked = _load_data(project_dir / ".prd_runner" / "runner_blocked.json", {})
    assert blocked.get("error_type") == "state_invalid"
    issues = blocked.get("details", {}).get("issues", [])
    assert any("unknown phase_id" in str(item) for item in issues)
