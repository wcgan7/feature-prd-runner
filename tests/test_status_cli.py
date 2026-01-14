"""Test the `status` CLI subcommand output."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner import runner
from feature_prd_runner.state import _ensure_state_files


def test_status_command_does_not_require_prd_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `status` can run without providing a PRD path."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")
    _ensure_state_files(project_dir, prd_path)

    try:
        runner.main(["status", "--project-dir", str(project_dir)])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "State:" in out
    assert ".prd_runner" in out


def test_status_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `status --json` emits machine-readable output."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Spec\n")
    _ensure_state_files(project_dir, prd_path)

    try:
        runner.main(["status", "--project-dir", str(project_dir), "--json"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert '"state_dir"' in out
    assert '"run_state"' in out
