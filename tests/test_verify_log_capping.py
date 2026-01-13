import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner.actions import run_verify
from feature_prd_runner.io_utils import _load_data


def test_verify_uses_bounded_excerpt_for_large_logs(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_a.py").write_text("def test_x(): assert False\n")

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Ensure log exceeds the excerpt window threshold (~max_chars*4 bytes).
    huge = ("x" * 300_000) + "\nFAILURES\nFAILED tests/test_a.py::test_x\n" + ("y" * 300_000)

    def fake_run_command(command, project_dir, log_path, timeout_seconds=None):
        Path(log_path).write_text(huge)
        return {"command": command, "exit_code": 1, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["src/foo.py"], "new_files": []},
        default_test_command="pytest",
        timeout_seconds=10,
    )

    assert event.passed is False
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    failing_stage = manifest.get("failing_stage") or {}
    stages = manifest.get("stages") or []
    assert any(isinstance(s, dict) and s.get("stage") == "tests" for s in stages)
    assert failing_stage.get("stage") == "tests"
    assert "pytest_failures.txt" in str(failing_stage.get("excerpt_path"))
    assert bool(failing_stage.get("excerpt_truncated")) is True
    excerpt_path = Path(failing_stage["excerpt_path"])
    assert excerpt_path.exists()


def test_verify_detects_pytest_behind_wrappers(tmp_path: Path, monkeypatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_a.py").write_text("def test_x(): assert False\n")

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    output = "FAILURES\nFAILED tests/test_a.py::test_x\n"

    def fake_run_command(command, project_dir, log_path, timeout_seconds=None):
        Path(log_path).write_text(output)
        return {"command": command, "exit_code": 1, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["src/foo.py"], "new_files": []},
        default_test_command="poetry run pytest",
        timeout_seconds=10,
    )

    assert event.passed is False
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    failing_stage = manifest.get("failing_stage") or {}
    assert failing_stage.get("stage") == "tests"
    assert "pytest_failures.txt" in str(failing_stage.get("excerpt_path"))
