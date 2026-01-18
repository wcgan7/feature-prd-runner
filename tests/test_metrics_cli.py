"""Test the `metrics` CLI subcommand output."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from feature_prd_runner import runner
from feature_prd_runner.state import _ensure_state_files


def test_metrics_command_without_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics` shows helpful message when no state exists."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    try:
        runner.main(["metrics", "--project-dir", str(project_dir)])
    except SystemExit as exc:
        assert exc.code == 1

    out = capsys.readouterr().out
    assert "No .prd_runner state directory found" in out
    assert "Run 'feature-prd-runner run' first" in out


def test_metrics_command_with_empty_state(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics` works with empty state directory."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Test PRD\n")
    _ensure_state_files(project_dir, prd_path)

    try:
        runner.main(["metrics", "--project-dir", str(project_dir)])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    # Should show something even with no data
    assert "Run Metrics" in out or "No metrics data available" in out


def test_metrics_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics --json` emits machine-readable output."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Test PRD\n")
    _ensure_state_files(project_dir, prd_path)

    try:
        runner.main(["metrics", "--project-dir", str(project_dir), "--json"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    # Verify it's valid JSON
    data = json.loads(out)
    assert "tokens_used" in data
    assert "wall_time_seconds" in data
    assert "files_changed" in data


def test_metrics_export_csv(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics --export csv` creates a CSV file."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Test PRD\n")
    _ensure_state_files(project_dir, prd_path)

    output_file = tmp_path / "test_metrics.csv"

    try:
        runner.main([
            "metrics",
            "--project-dir", str(project_dir),
            "--export", "csv",
            "--output", str(output_file)
        ])
    except SystemExit as exc:
        assert exc.code == 0

    # Verify CSV file was created
    assert output_file.exists()

    # Verify CSV content
    content = output_file.read_text()
    assert "Metric,Value" in content

    out = capsys.readouterr().out
    assert "Metrics exported to:" in out
    assert str(output_file) in out


def test_metrics_export_html(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics --export html` creates an HTML file."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Test PRD\n")
    _ensure_state_files(project_dir, prd_path)

    output_file = tmp_path / "test_metrics.html"

    try:
        runner.main([
            "metrics",
            "--project-dir", str(project_dir),
            "--export", "html",
            "--output", str(output_file)
        ])
    except SystemExit as exc:
        assert exc.code == 0

    # Verify HTML file was created
    assert output_file.exists()

    # Verify HTML content
    content = output_file.read_text()
    assert "<!DOCTYPE html>" in content
    assert "Run Metrics Report" in content
    assert "Feature PRD Runner" in content

    out = capsys.readouterr().out
    assert "Metrics exported to:" in out
    assert str(output_file) in out


def test_metrics_export_csv_default_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ensure `metrics --export csv` uses default filename when no output specified."""
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    subprocess.run(["git", "init"], cwd=project_dir, check=True)

    prd_path = project_dir / "prd.md"
    prd_path.write_text("Test PRD\n")
    _ensure_state_files(project_dir, prd_path)

    # Change to temp directory so default file goes there
    import os
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        runner.main([
            "metrics",
            "--project-dir", str(project_dir),
            "--export", "csv"
        ])
    except SystemExit as exc:
        assert exc.code == 0
    finally:
        os.chdir(original_cwd)

    # Verify default CSV file was created
    default_file = tmp_path / "metrics.csv"
    assert default_file.exists()
