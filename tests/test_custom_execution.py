"""Tests for custom_execution module - ad-hoc task execution and flexible prompts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from feature_prd_runner.custom_execution import (
    _build_custom_prompt,
    execute_custom_prompt,
)
from feature_prd_runner.models import (
    ProgressHumanBlockers,
    ResumePromptResult,
    WorkerFailed,
)


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def progress_path(temp_project: Path) -> Path:
    """Create a progress path."""
    return temp_project / ".prd_runner" / "runs" / "test-run" / "progress.json"


class TestBuildCustomPrompt:
    """Test _build_custom_prompt function."""

    def test_basic_prompt(self, progress_path: Path):
        """Test building a basic custom prompt."""
        prompt = _build_custom_prompt(
            user_prompt="Update copyright headers",
            progress_path=progress_path,
            run_id="test-run-123",
        )

        assert "Update copyright headers" in prompt
        assert str(progress_path) in prompt
        assert "run_id=test-run-123" in prompt
        assert "task_id=\"custom_exec\"" in prompt

    def test_prompt_with_heartbeat(self, progress_path: Path):
        """Test prompt with heartbeat configuration."""
        prompt = _build_custom_prompt(
            user_prompt="Test task",
            progress_path=progress_path,
            run_id="test-run",
            heartbeat_seconds=30,
        )

        assert "heartbeat" in prompt.lower()
        assert "30 seconds" in prompt

    def test_prompt_with_context_task_id(self, progress_path: Path):
        """Test prompt with task_id in context."""
        context = {"task_id": "task-123"}

        prompt = _build_custom_prompt(
            user_prompt="Fix bug",
            progress_path=progress_path,
            run_id="test-run",
            context=context,
        )

        assert "Context:" in prompt
        assert "Task: task-123" in prompt

    def test_prompt_with_context_phase_id(self, progress_path: Path):
        """Test prompt with phase_id in context."""
        context = {"phase_id": "phase-2"}

        prompt = _build_custom_prompt(
            user_prompt="Implement feature",
            progress_path=progress_path,
            run_id="test-run",
            context=context,
        )

        assert "Phase: phase-2" in prompt

    def test_prompt_with_context_files(self, progress_path: Path):
        """Test prompt with files in context."""
        context = {"files": ["file1.py", "file2.py", "file3.py"]}

        prompt = _build_custom_prompt(
            user_prompt="Refactor code",
            progress_path=progress_path,
            run_id="test-run",
            context=context,
        )

        assert "Focus files:" in prompt
        assert "file1.py" in prompt
        assert "file2.py" in prompt

    def test_prompt_with_many_files_truncates(self, progress_path: Path):
        """Test that many files are truncated in prompt."""
        files = [f"file{i}.py" for i in range(20)]
        context = {"files": files}

        prompt = _build_custom_prompt(
            user_prompt="Update files",
            progress_path=progress_path,
            run_id="test-run",
            context=context,
        )

        assert "20 total" in prompt

    def test_prompt_without_override_agents(self, progress_path: Path):
        """Test prompt without AGENTS.md override (default)."""
        prompt = _build_custom_prompt(
            user_prompt="Test task",
            progress_path=progress_path,
            run_id="test-run",
            override_agents=False,
        )

        assert "Follow all repository rules in AGENTS.md" in prompt
        assert "SUPERADMIN" not in prompt

    def test_prompt_with_override_agents(self, progress_path: Path):
        """Test prompt with AGENTS.md override (superadmin mode)."""
        prompt = _build_custom_prompt(
            user_prompt="Emergency fix",
            progress_path=progress_path,
            run_id="test-run",
            override_agents=True,
        )

        assert "SUPERADMIN MODE" in prompt
        assert "bypass normal AGENTS.md rules" in prompt
        assert "special privileges" in prompt

    def test_prompt_includes_success_criteria(self, progress_path: Path):
        """Test that prompt includes success criteria."""
        prompt = _build_custom_prompt(
            user_prompt="Test",
            progress_path=progress_path,
            run_id="test-run",
        )

        assert "successfully completed" in prompt
        assert "human_blocking_issues MUST be empty" in prompt

    def test_prompt_includes_blocking_criteria(self, progress_path: Path):
        """Test that prompt includes blocking criteria."""
        prompt = _build_custom_prompt(
            user_prompt="Test",
            progress_path=progress_path,
            run_id="test-run",
        )

        assert "blocked" in prompt.lower()
        assert "human_blocking_issues MUST contain" in prompt

    def test_prompt_with_full_context(self, progress_path: Path):
        """Test prompt with all context fields."""
        context = {
            "task_id": "task-123",
            "phase_id": "phase-2",
            "files": ["main.py", "test.py"],
        }

        prompt = _build_custom_prompt(
            user_prompt="Complete implementation",
            progress_path=progress_path,
            run_id="test-run",
            heartbeat_seconds=60,
            override_agents=True,
            context=context,
        )

        assert "Complete implementation" in prompt
        assert "Task: task-123" in prompt
        assert "Phase: phase-2" in prompt
        assert "main.py" in prompt
        assert "60 seconds" in prompt
        assert "SUPERADMIN" in prompt


class TestExecuteCustomPrompt:
    """Test execute_custom_prompt function."""

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_success(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test successful custom prompt execution."""
        # Setup mocks
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        # Execute
        success, error = execute_custom_prompt(
            user_prompt="Update README",
            project_dir=temp_project,
        )

        assert success is True
        assert error is None
        mock_run_action.assert_called_once()

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_blocked(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test custom prompt execution that gets blocked."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        blocked_result = ProgressHumanBlockers(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            issues=["Need clarification on requirements"],
            next_steps=["Please specify which README sections to update"],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = blocked_result

        success, error = execute_custom_prompt(
            user_prompt="Update README",
            project_dir=temp_project,
        )

        assert success is False
        assert error == "Need clarification on requirements"

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_failed(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test custom prompt execution that fails."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        failed_result = WorkerFailed(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            step="custom_exec",
            error_type="execution_error",
            error_detail="Tool not found",
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = failed_result

        success, error = execute_custom_prompt(
            user_prompt="Run tests",
            project_dir=temp_project,
        )

        assert success is False
        assert "Tool not found" in error

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_with_context(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test execution with context."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        context = {
            "task_id": "task-123",
            "phase_id": "phase-2",
            "files": ["src/main.py"],
        }

        success, error = execute_custom_prompt(
            user_prompt="Refactor code",
            project_dir=temp_project,
            context=context,
        )

        assert success is True
        # Verify context was passed through (check the prompt)
        call_args = mock_run_action.call_args
        assert call_args is not None

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_with_superadmin_mode(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test execution with superadmin mode."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        success, error = execute_custom_prompt(
            user_prompt="Emergency fix",
            project_dir=temp_project,
            override_agents=True,
        )

        assert success is True
        # Verify superadmin was enabled in prompt
        call_args = mock_run_action.call_args
        prompt_text = call_args[1]["user_prompt"]
        assert "SUPERADMIN" in prompt_text

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_then_continue(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test execution with then_continue flag."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        success, error = execute_custom_prompt(
            user_prompt="Quick fix",
            project_dir=temp_project,
            then_continue=True,
        )

        assert success is True

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_with_custom_timeouts(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test execution with custom timeout settings."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        success, error = execute_custom_prompt(
            user_prompt="Long task",
            project_dir=temp_project,
            heartbeat_seconds=60,
            heartbeat_grace_seconds=600,
            shift_minutes=90,
        )

        assert success is True
        call_args = mock_run_action.call_args
        assert call_args[1]["heartbeat_seconds"] == 60
        assert call_args[1]["heartbeat_grace_seconds"] == 600
        assert call_args[1]["shift_minutes"] == 90

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_creates_run_directory(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test that execution creates proper run directory structure."""
        runs_dir = temp_project / ".prd_runner" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        mock_ensure_state.return_value = {
            "runs": runs_dir,
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        execute_custom_prompt(
            user_prompt="Test",
            project_dir=temp_project,
        )

        # Verify run directory was created
        assert runs_dir.exists()
        # Should have at least one run directory
        run_dirs = list(runs_dir.glob("*-custom"))
        assert len(run_dirs) > 0

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_writes_prompt_file(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test that execution writes prompt to file for debugging."""
        runs_dir = temp_project / ".prd_runner" / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)

        mock_ensure_state.return_value = {
            "runs": runs_dir,
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        success_result = ResumePromptResult(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            succeeded=True,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = success_result

        execute_custom_prompt(
            user_prompt="Debug test",
            project_dir=temp_project,
        )

        # Verify prompt.txt was created
        prompt_files = list(runs_dir.glob("*/prompt.txt"))
        assert len(prompt_files) > 0
        prompt_content = prompt_files[0].read_text()
        assert "Debug test" in prompt_content

    @patch("feature_prd_runner.custom_execution.run_resume_prompt_action")
    @patch("feature_prd_runner.custom_execution._ensure_state_files")
    @patch("feature_prd_runner.custom_execution.FileLock")
    def test_execute_handles_multiple_blocking_issues(
        self,
        mock_lock: MagicMock,
        mock_ensure_state: MagicMock,
        mock_run_action: MagicMock,
        temp_project: Path,
    ):
        """Test execution handles multiple blocking issues."""
        mock_ensure_state.return_value = {
            "runs": temp_project / ".prd_runner" / "runs",
            "run_state": temp_project / ".prd_runner" / "run_state.json",
            "events": temp_project / ".prd_runner" / "events.json",
        }

        blocked_result = ProgressHumanBlockers(
            run_id="test-run",
            task_id="custom_exec",
            phase="custom_exec",
            issues=[
                "Missing dependency A",
                "Configuration file not found",
                "API key required",
            ],
            next_steps=[
                "Install dependency A",
                "Create config file",
                "Set API key in environment",
            ],
            captured_at="2024-01-01T00:00:00Z",
        )
        mock_run_action.return_value = blocked_result

        success, error = execute_custom_prompt(
            user_prompt="Deploy service",
            project_dir=temp_project,
        )

        assert success is False
        assert "Missing dependency A" in error
        assert "Configuration file not found" in error
        assert "API key required" in error
