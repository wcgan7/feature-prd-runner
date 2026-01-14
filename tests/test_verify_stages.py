"""Test verify stage ordering and allowlist expansion signals."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner.actions import run_verify
from feature_prd_runner.io_utils import _load_data, _save_data
from feature_prd_runner.utils import _now_iso


def test_verify_lint_stage_triggers_allowlist_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure lint failures can trigger allowlist expansion signals."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    (project_dir / "src").mkdir()
    (project_dir / "src" / "a.py").write_text("import os\n")

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    # Simulate ruff output pointing at src/a.py and failing.
    output = "src/a.py:1:1: F401 `os` imported but unused\n"

    def fake_run_command(
        command: str,
        project_dir: Path,
        log_path: Path,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        _ = project_dir
        _ = timeout_seconds
        log_path.write_text(output)
        return {"command": command, "exit_code": 1, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)
    monkeypatch.setattr(run_verify, "_is_pytest_command", lambda *_: False)
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/ruff" if name == "ruff" else None)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["src/other.py"], "new_files": []},
        default_test_command=None,
        default_lint_command="ruff check .",
        timeout_seconds=10,
    )

    assert event.passed is False
    assert event.needs_allowlist_expansion is True
    assert "src/a.py" in (event.failing_paths or [])


def test_verify_uses_config_yaml_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure verify defaults can be loaded from `.prd_runner/config.yaml`."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    (project_dir / ".prd_runner").mkdir()
    (project_dir / ".prd_runner" / "config.yaml").write_text(
        "verify:\n  test_command: \"pytest\"\n"
    )

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_run_command(
        command: str,
        project_dir: Path,
        log_path: Path,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        _ = project_dir
        _ = timeout_seconds
        log_path.write_text("ok\n")
        return {"command": command, "exit_code": 0, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)
    monkeypatch.setattr(run_verify, "_is_pytest_command", lambda *_: False)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["README.md"], "new_files": []},
        default_test_command=None,
        timeout_seconds=10,
    )

    assert event.passed is True
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    assert manifest.get("stages") and manifest["stages"][0]["stage"] == "tests"


def test_verify_ensure_ruff_install_then_lint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure `ensure_ruff=install` installs ruff before running lint."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    state = {"ruff_installed": False}

    def fake_run_command(
        command: str,
        project_dir: Path,
        log_path: Path,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        _ = project_dir
        _ = timeout_seconds
        if command.startswith("python -m pip install ruff"):
            state["ruff_installed"] = True
            log_path.write_text("installed\n")
            return {"command": command, "exit_code": 0, "log_path": str(log_path), "timed_out": False}
        log_path.write_text("ok\n")
        return {"command": command, "exit_code": 0, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)
    monkeypatch.setattr(run_verify, "_is_pytest_command", lambda *_: False)

    import shutil

    def fake_which(name: str) -> str | None:
        if name == "ruff":
            return "/bin/ruff" if state["ruff_installed"] else None
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["README.md"], "new_files": []},
        default_test_command=None,
        default_lint_command="ruff check .",
        ensure_ruff="install",
        timeout_seconds=10,
    )

    assert event.passed is True
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    stage_names = [s.get("stage") for s in (manifest.get("stages") or [])]
    assert stage_names[:2] == ["ensure_ruff", "lint"]


def test_verify_ensure_deps_runs_before_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure `ensure_deps=install` runs before tests."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    calls: list[str] = []

    def fake_run_command(
        command: str,
        project_dir: Path,
        log_path: Path,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        _ = project_dir
        _ = timeout_seconds
        calls.append(command)
        log_path.write_text("ok\n")
        return {"command": command, "exit_code": 0, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)
    monkeypatch.setattr(run_verify, "_is_pytest_command", lambda *_: False)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["README.md"], "new_files": []},
        default_test_command="pytest",
        ensure_deps="install",
        ensure_deps_command="python -m pip install -e .",
        timeout_seconds=10,
    )

    assert event.passed is True
    assert calls[0] == "python -m pip install -e ."
    assert calls[1] == "pytest"
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    stage_names = [s.get("stage") for s in (manifest.get("stages") or [])]
    assert stage_names[:2] == ["ensure_deps", "tests"]


def test_verify_ensure_deps_failure_returns_blocking_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure dependency install failures are reported as blocking verify events."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fake_run_command(
        command: str,
        project_dir: Path,
        log_path: Path,
        timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        _ = project_dir
        _ = timeout_seconds
        log_path.write_text("no network\n")
        return {"command": command, "exit_code": 1, "log_path": str(log_path), "timed_out": False}

    monkeypatch.setattr(run_verify, "_run_command", fake_run_command)
    monkeypatch.setattr(run_verify, "_is_pytest_command", lambda *_: False)

    event = run_verify.run_verify_action(
        project_dir=project_dir,
        artifacts_dir=artifacts_dir,
        run_dir=run_dir,
        phase={"id": "phase-1"},
        task={"id": "phase-1", "phase_id": "phase-1"},
        run_id="run-1",
        plan_data={"files_to_change": ["README.md"], "new_files": []},
        default_test_command="pytest",
        ensure_deps="install",
        ensure_deps_command="python -m pip install -e .",
        timeout_seconds=10,
    )

    assert event.passed is False
    assert event.error_type == "deps_install_failed"
    manifest = _load_data(run_dir / "verify_manifest.json", {})
    assert manifest.get("failing_stage", {}).get("stage") == "ensure_deps"
