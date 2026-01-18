"""Tests for debug module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from feature_prd_runner.debug import (
    ErrorAnalyzer,
    ErrorReport,
    StateSnapshot,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def project_dir(temp_dir: Path) -> Path:
    """Create a project directory with state dir."""
    state_dir = temp_dir / ".prd_runner"
    state_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = state_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.fixture
def error_analyzer(project_dir: Path) -> ErrorAnalyzer:
    """Create an ErrorAnalyzer instance."""
    return ErrorAnalyzer(project_dir)


class TestErrorReport:
    """Test ErrorReport dataclass."""

    def test_create_error_report(self):
        """Test creating an error report."""
        report = ErrorReport(
            task_id="task-1",
            error_type="test_failed",
            error_detail="Tests failed with 3 errors",
        )

        assert report.task_id == "task-1"
        assert report.error_type == "test_failed"
        assert report.error_detail == "Tests failed with 3 errors"
        assert report.severity == "error"

    def test_error_report_with_details(self):
        """Test error report with all fields."""
        report = ErrorReport(
            task_id="task-2",
            error_type="worker_failed",
            error_detail="Worker crashed",
            root_cause="Memory error",
            files_involved=["file1.py", "file2.py"],
            suggested_actions=[{"action": "retry", "command": "retry"}],
            quick_fixes=[{"label": "fix", "command": "fix"}],
            severity="critical",
        )

        assert report.root_cause == "Memory error"
        assert len(report.files_involved) == 2
        assert len(report.suggested_actions) == 1
        assert len(report.quick_fixes) == 1
        assert report.severity == "critical"

    def test_error_report_initializes_empty_lists(self):
        """Test that empty lists are initialized properly."""
        report = ErrorReport(
            task_id="task-1",
            error_type="test",
            error_detail="detail",
        )

        assert report.files_involved == []
        assert report.suggested_actions == []
        assert report.quick_fixes == []


class TestStateSnapshot:
    """Test StateSnapshot dataclass."""

    def test_create_state_snapshot(self):
        """Test creating a state snapshot."""
        snapshot = StateSnapshot(
            task_id="task-1",
            lifecycle="waiting_human",
            step="verify",
            status="test_failed",
            worker_attempts=3,
            last_error="Tests failed",
            last_error_type="test_failed",
            context=["context1", "context2"],
            metadata={"key": "value"},
        )

        assert snapshot.task_id == "task-1"
        assert snapshot.lifecycle == "waiting_human"
        assert snapshot.step == "verify"
        assert snapshot.status == "test_failed"
        assert snapshot.worker_attempts == 3
        assert snapshot.last_error == "Tests failed"
        assert len(snapshot.context) == 2


class TestErrorAnalyzer:
    """Test ErrorAnalyzer class."""

    def test_init(self, project_dir: Path):
        """Test ErrorAnalyzer initialization."""
        analyzer = ErrorAnalyzer(project_dir)

        assert analyzer.project_dir == project_dir.resolve()
        assert analyzer.state_dir == project_dir / ".prd_runner"
        assert analyzer.console is not None

    def test_analyze_test_failure(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing test failure errors."""
        context = {
            "failed_tests": ["test_foo.py::test_1", "test_bar.py::test_2"],
            "test_output": "AssertionError: expected 1 but got 2",
        }

        report = error_analyzer.analyze_error(
            task_id="task-1",
            error_type="test_failed",
            error_detail="Tests failed",
            context=context,
        )

        assert report.task_id == "task-1"
        assert report.error_type == "test_failed"
        assert report.root_cause == "Tests failed during verification."
        assert len(report.files_involved) == 2
        assert len(report.suggested_actions) == 3
        assert len(report.quick_fixes) == 2
        assert "retry" in report.suggested_actions[1]["command"].lower()

    def test_analyze_test_failure_truncates_files(self, error_analyzer: ErrorAnalyzer):
        """Test that test failures truncate files list to 10."""
        context = {
            "failed_tests": [f"test_{i}.py" for i in range(20)],
        }

        report = error_analyzer.analyze_error(
            task_id="task-1",
            error_type="test_failed",
            error_detail="Many tests failed",
            context=context,
        )

        assert len(report.files_involved) == 10

    def test_analyze_worker_failure(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing worker failure errors."""
        context = {
            "run_id": "run-123",
            "step": "implement",
        }

        report = error_analyzer.analyze_error(
            task_id="task-2",
            error_type="worker_failed",
            error_detail="Worker process crashed",
            context=context,
        )

        assert report.root_cause == "The Codex worker failed to complete the task."
        assert len(report.suggested_actions) == 3
        assert len(report.quick_fixes) == 2
        assert "run-123" in report.quick_fixes[0]["command"]

    def test_analyze_worker_failure_without_run_id(self, error_analyzer: ErrorAnalyzer):
        """Test worker failure without run_id."""
        report = error_analyzer.analyze_error(
            task_id="task-2",
            error_type="worker_failed",
            error_detail="Worker failed",
            context={"step": "implement"},
        )

        # Should still have suggested actions but no quick fixes
        assert len(report.suggested_actions) == 3
        assert len(report.quick_fixes) == 0

    def test_analyze_allowlist_violation(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing allowlist violation errors."""
        context = {
            "disallowed_files": ["unauthorized1.py", "unauthorized2.py"],
        }

        report = error_analyzer.analyze_error(
            task_id="task-3",
            error_type="allowlist_violation",
            error_detail="Files modified outside allowlist",
            context=context,
        )

        assert "2 file(s)" in report.root_cause
        assert len(report.files_involved) == 2
        assert len(report.suggested_actions) == 3
        assert "git diff" in report.suggested_actions[0]["command"]

    def test_analyze_no_progress(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing no progress errors."""
        report = error_analyzer.analyze_error(
            task_id="task-4",
            error_type="no_progress",
            error_detail="No changes detected",
            context={},
        )

        assert report.root_cause == "Worker completed but introduced no code changes."
        assert report.severity == "warning"
        assert len(report.suggested_actions) == 3

    def test_analyze_review_failure(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing review failure errors."""
        context = {
            "issues": [
                {"file": "module.py", "issue": "Missing docstring"},
                {"file": "test.py", "issue": "No assertions"},
            ],
        }

        report = error_analyzer.analyze_error(
            task_id="task-5",
            error_type="review_failed",
            error_detail="Review found issues",
            context=context,
        )

        assert "2 blocking issue(s)" in report.root_cause
        assert report.severity == "warning"
        assert len(report.files_involved) == 2
        assert len(report.suggested_actions) == 2

    def test_analyze_review_failure_many_issues(self, error_analyzer: ErrorAnalyzer):
        """Test review failure with many issues becomes error severity."""
        context = {
            "issues": [{"file": f"file{i}.py", "issue": "issue"} for i in range(5)],
        }

        report = error_analyzer.analyze_error(
            task_id="task-5",
            error_type="review_failed",
            error_detail="Many issues found",
            context=context,
        )

        assert report.severity == "error"

    def test_analyze_git_failure(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing git push failure errors."""
        report = error_analyzer.analyze_error(
            task_id="task-6",
            error_type="git_push_failed",
            error_detail="Failed to push to remote",
            context={},
        )

        assert report.root_cause == "Failed to push changes to remote repository."
        assert len(report.suggested_actions) == 3
        assert "git remote" in report.suggested_actions[0]["command"]

    def test_analyze_generic_error(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing unknown error types."""
        report = error_analyzer.analyze_error(
            task_id="task-7",
            error_type="unknown_error",
            error_detail="Something went wrong",
            context={},
        )

        assert "unknown_error" in report.root_cause
        assert len(report.suggested_actions) == 3
        assert "inspect" in report.suggested_actions[0]["command"]

    def test_analyze_error_without_context(self, error_analyzer: ErrorAnalyzer):
        """Test analyzing error without context."""
        report = error_analyzer.analyze_error(
            task_id="task-8",
            error_type="test_failed",
            error_detail="Tests failed",
        )

        # Should still generate report with defaults
        assert report.task_id == "task-8"
        assert report.error_type == "test_failed"
        assert len(report.suggested_actions) > 0

    def test_format_error_report(self, error_analyzer: ErrorAnalyzer):
        """Test formatting error report."""
        report = ErrorReport(
            task_id="task-1",
            error_type="test_failed",
            error_detail="Tests failed with errors",
            root_cause="Assertion failed",
            files_involved=["test.py"],
            suggested_actions=[{"action": "Retry", "command": "retry task-1"}],
            quick_fixes=[{"label": "View logs", "command": "cat logs"}],
        )

        formatted = error_analyzer.format_error_report(report)

        assert "task-1" in formatted
        assert "test_failed" in formatted
        assert "Assertion failed" in formatted
        assert "test.py" in formatted
        assert "Retry" in formatted
        assert "View logs" in formatted

    def test_format_error_report_truncates_detail(self, error_analyzer: ErrorAnalyzer):
        """Test that long error details are truncated."""
        long_detail = "x" * 300

        report = ErrorReport(
            task_id="task-1",
            error_type="test",
            error_detail=long_detail,
        )

        formatted = error_analyzer.format_error_report(report, verbose=False)

        # Should be truncated
        assert "..." in formatted

    def test_format_error_report_verbose(self, error_analyzer: ErrorAnalyzer):
        """Test verbose error report formatting."""
        long_detail = "x" * 300

        report = ErrorReport(
            task_id="task-1",
            error_type="test",
            error_detail=long_detail,
        )

        formatted = error_analyzer.format_error_report(report, verbose=True)

        # Should NOT be truncated
        assert long_detail in formatted

    def test_format_error_report_many_files(self, error_analyzer: ErrorAnalyzer):
        """Test formatting report with many files involved."""
        report = ErrorReport(
            task_id="task-1",
            error_type="test",
            error_detail="detail",
            files_involved=[f"file{i}.py" for i in range(15)],
        )

        formatted = error_analyzer.format_error_report(report)

        # Should show first 10 and indicate more
        assert "and 5 more" in formatted

    def test_format_error_report_severity_colors(self, error_analyzer: ErrorAnalyzer):
        """Test different severity levels."""
        for severity in ["critical", "error", "warning"]:
            report = ErrorReport(
                task_id="task-1",
                error_type="test",
                error_detail="detail",
                severity=severity,
            )

            formatted = error_analyzer.format_error_report(report)
            assert formatted  # Should format without error

    @patch("feature_prd_runner.debug._load_data")
    def test_explain_blocking_task_not_found(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test explain_blocking when task not found."""
        mock_load.return_value = {"tasks": []}

        explanation = error_analyzer.explain_blocking("task-999")

        assert "not found" in explanation

    @patch("feature_prd_runner.debug._load_data")
    def test_explain_blocking_not_blocked(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test explain_blocking when task is not blocked."""
        mock_load.return_value = {
            "tasks": [
                {
                    "id": "task-1",
                    "lifecycle": "running",
                },
            ],
        }

        explanation = error_analyzer.explain_blocking("task-1")

        assert "not blocked" in explanation

    @patch("feature_prd_runner.debug._load_data")
    def test_explain_blocking_success(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test explain_blocking with blocked task."""
        mock_load.return_value = {
            "tasks": [
                {
                    "id": "task-1",
                    "lifecycle": "waiting_human",
                    "status": "test_failed",
                    "step": "verify",
                    "worker_attempts": 2,
                    "last_error": "Tests failed with 3 errors",
                    "last_error_type": "test_failed",
                    "block_reason": "Verification failed",
                    "human_blocking_issues": ["Fix test failures"],
                    "human_next_steps": ["Review logs", "Fix issues"],
                    "blocked_intent": {"step": "verify"},
                },
            ],
        }

        explanation = error_analyzer.explain_blocking("task-1")

        assert "task-1" in explanation
        assert "waiting_human" in explanation
        assert "test_failed" in explanation
        assert "verify" in explanation
        assert "Worker attempts: 2" in explanation
        assert "Tests failed with 3 errors" in explanation
        assert "Verification failed" in explanation
        assert "Fix test failures" in explanation
        assert "Review logs" in explanation
        assert "resume task-1" in explanation

    @patch("feature_prd_runner.debug._load_data")
    def test_explain_blocking_minimal_info(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test explain_blocking with minimal task info."""
        mock_load.return_value = {
            "tasks": [
                {
                    "id": "task-1",
                    "lifecycle": "waiting_human",
                    "status": "blocked",
                    "step": "implement",
                },
            ],
        }

        explanation = error_analyzer.explain_blocking("task-1")

        # Should still generate explanation
        assert "task-1" in explanation
        assert "blocked" in explanation

    @patch("feature_prd_runner.debug._load_data")
    def test_inspect_state_success(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test inspecting task state."""
        mock_load.return_value = {
            "tasks": [
                {
                    "id": "task-1",
                    "lifecycle": "waiting_human",
                    "step": "verify",
                    "status": "test_failed",
                    "worker_attempts": 3,
                    "last_error": "Tests failed",
                    "last_error_type": "test_failed",
                    "context": ["ctx1", "ctx2"],
                    "type": "feature",
                    "phase_id": "phase-1",
                    "prompt_mode": "standard",
                    "auto_resume_count": 1,
                    "manual_resume_attempts": 0,
                },
            ],
        }

        snapshot = error_analyzer.inspect_state("task-1")

        assert snapshot is not None
        assert snapshot.task_id == "task-1"
        assert snapshot.lifecycle == "waiting_human"
        assert snapshot.step == "verify"
        assert snapshot.status == "test_failed"
        assert snapshot.worker_attempts == 3
        assert snapshot.last_error == "Tests failed"
        assert snapshot.last_error_type == "test_failed"
        assert len(snapshot.context) == 2
        assert snapshot.metadata["type"] == "feature"
        assert snapshot.metadata["auto_resume_count"] == 1

    @patch("feature_prd_runner.debug._load_data")
    def test_inspect_state_not_found(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test inspect_state when task not found."""
        mock_load.return_value = {"tasks": []}

        snapshot = error_analyzer.inspect_state("task-999")

        assert snapshot is None

    @patch("feature_prd_runner.debug._load_data")
    def test_inspect_state_minimal_data(
        self,
        mock_load: MagicMock,
        error_analyzer: ErrorAnalyzer,
    ):
        """Test inspect_state with minimal task data."""
        mock_load.return_value = {
            "tasks": [
                {
                    "id": "task-1",
                },
            ],
        }

        snapshot = error_analyzer.inspect_state("task-1")

        assert snapshot is not None
        assert snapshot.lifecycle == "unknown"
        assert snapshot.step == "unknown"
        assert snapshot.status == "unknown"
        assert snapshot.worker_attempts == 0

    def test_trace_history_no_events_file(self, error_analyzer: ErrorAnalyzer):
        """Test trace_history when events file doesn't exist."""
        events = error_analyzer.trace_history("task-1")

        assert events == []

    def test_trace_history_success(
        self,
        error_analyzer: ErrorAnalyzer,
        project_dir: Path,
    ):
        """Test trace_history with events."""
        events_path = project_dir / ".prd_runner" / "artifacts" / "events.jsonl"

        # Write test events
        events_data = [
            {"task_id": "task-1", "event": "started", "timestamp": "2024-01-01"},
            {"task_id": "task-2", "event": "started", "timestamp": "2024-01-02"},
            {"task_id": "task-1", "event": "failed", "timestamp": "2024-01-03"},
        ]

        with events_path.open("w") as f:
            for event in events_data:
                f.write(json.dumps(event) + "\n")

        events = error_analyzer.trace_history("task-1")

        assert len(events) == 2
        assert events[0]["task_id"] == "task-1"
        assert events[0]["event"] == "started"
        assert events[1]["event"] == "failed"

    def test_trace_history_empty_lines(
        self,
        error_analyzer: ErrorAnalyzer,
        project_dir: Path,
    ):
        """Test trace_history handles empty lines."""
        events_path = project_dir / ".prd_runner" / "artifacts" / "events.jsonl"

        with events_path.open("w") as f:
            f.write('{"task_id": "task-1", "event": "started"}\n')
            f.write('\n')
            f.write('{"task_id": "task-1", "event": "completed"}\n')

        events = error_analyzer.trace_history("task-1")

        assert len(events) == 2

    def test_trace_history_invalid_json(
        self,
        error_analyzer: ErrorAnalyzer,
        project_dir: Path,
    ):
        """Test trace_history handles invalid JSON gracefully."""
        events_path = project_dir / ".prd_runner" / "artifacts" / "events.jsonl"

        with events_path.open("w") as f:
            f.write('{"task_id": "task-1", "event": "started"}\n')
            f.write('invalid json\n')
            f.write('{"task_id": "task-1", "event": "completed"}\n')

        # Should return empty or partial results without crashing
        events = error_analyzer.trace_history("task-1")
        # Implementation may vary on error handling

    def test_format_state_snapshot(self, error_analyzer: ErrorAnalyzer):
        """Test formatting state snapshot."""
        snapshot = StateSnapshot(
            task_id="task-1",
            lifecycle="waiting_human",
            step="verify",
            status="test_failed",
            worker_attempts=2,
            last_error="Tests failed with 3 errors",
            last_error_type="test_failed",
            context=["context1", "context2"],
            metadata={"type": "feature", "phase_id": "phase-1"},
        )

        formatted = error_analyzer.format_state_snapshot(snapshot)

        assert "task-1" in formatted
        assert "waiting_human" in formatted
        assert "verify" in formatted
        assert "test_failed" in formatted
        assert "2" in formatted  # worker attempts
        assert "Tests failed with 3 errors" in formatted
        assert "context1" in formatted
        assert "feature" in formatted

    def test_format_state_snapshot_many_contexts(self, error_analyzer: ErrorAnalyzer):
        """Test formatting snapshot with many context items."""
        snapshot = StateSnapshot(
            task_id="task-1",
            lifecycle="running",
            step="implement",
            status="active",
            worker_attempts=1,
            last_error=None,
            last_error_type=None,
            context=[f"context{i}" for i in range(10)],
            metadata={},
        )

        formatted = error_analyzer.format_state_snapshot(snapshot)

        # Should show first 5 and indicate more
        assert "and 5 more" in formatted

    def test_format_state_snapshot_minimal(self, error_analyzer: ErrorAnalyzer):
        """Test formatting minimal snapshot."""
        snapshot = StateSnapshot(
            task_id="task-1",
            lifecycle="queued",
            step="plan",
            status="pending",
            worker_attempts=0,
            last_error=None,
            last_error_type=None,
            context=[],
            metadata={},
        )

        formatted = error_analyzer.format_state_snapshot(snapshot)

        assert "task-1" in formatted
        assert "queued" in formatted
