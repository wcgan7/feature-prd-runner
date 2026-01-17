"""Tests for FSM module - task state reduction and step progression.

Unit tests for FSM state transitions. Integration tests exist in test_fsm.py.
"""

from __future__ import annotations

import pytest

from feature_prd_runner.fsm import reduce_task
from feature_prd_runner.models import (
    AllowlistViolation,
    CommitResult,
    NoIntroducedChanges,
    ProgressHumanBlockers,
    ResumePromptResult,
    ReviewResult,
    TaskLifecycle,
    TaskState,
    TaskStep,
    VerificationResult,
    WorkerFailed,
    WorkerSucceeded,
)


@pytest.fixture
def fresh_task() -> TaskState:
    """Create a fresh task state."""
    return TaskState(
        id="task-1",
        type="implement",
        phase_id="phase-1",
        lifecycle=TaskLifecycle.READY,
        step=TaskStep.PLAN_IMPL,
    )


@pytest.fixture
def caps() -> dict[str, int]:
    """Default capability caps."""
    return {
        "worker_attempts": 5,
        "plan_attempts": 3,
        "review_gen_attempts": 3,
        "test_fail_attempts": 3,
        "allowlist_expansion_attempts": 3,
        "no_progress_attempts": 3,
    }


class TestProgressHumanBlockers:
    """Test handling of human blocker events."""

    def test_blocker_sets_waiting_state(self, fresh_task: TaskState, caps: dict[str, int]):
        """Test that blocker event sets task to waiting state."""
        event = ProgressHumanBlockers(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            issues=["Need clarification"],
            next_steps=["Provide more details"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert result.block_reason == "HUMAN_REQUIRED"
        assert "Need clarification" in result.human_blocking_issues
        assert "Provide more details" in result.human_next_steps

    def test_blocker_records_run_id(self, fresh_task: TaskState, caps: dict[str, int]):
        """Test that blocker records the run ID."""
        event = ProgressHumanBlockers(
            run_id="run-456",
            task_id="task-1",
            phase="phase-1",
            issues=["Blocked"],
            next_steps=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.last_run_id == "run-456"

    def test_blocker_with_multiple_issues(self, fresh_task: TaskState, caps: dict[str, int]):
        """Test blocker with multiple issues."""
        event = ProgressHumanBlockers(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            issues=["Issue 1", "Issue 2", "Issue 3"],
            next_steps=["Step 1", "Step 2"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert len(result.human_blocking_issues) == 3
        assert len(result.human_next_steps) == 2
        assert "Issue 1; Issue 2; Issue 3" in result.last_error


class TestAllowlistViolation:
    """Test handling of allowlist violation events."""

    def test_allowlist_violation_within_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test allowlist violation when under attempt limit."""
        event = AllowlistViolation(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            disallowed_paths=["src/unauthorized.py"],
            changed_files=["src/main.py", "src/unauthorized.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.PLAN_IMPL
        assert result.allowlist_expansion_attempts == 1
        assert "src/unauthorized.py" in result.plan_expansion_request

    def test_allowlist_violation_exhausted_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test allowlist violation when attempt limit exhausted."""
        fresh_task.allowlist_expansion_attempts = 2

        event = AllowlistViolation(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            disallowed_paths=["src/file.py"],
            changed_files=["src/file.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert result.block_reason == "ALLOWLIST_EXPANSION_EXHAUSTED"
        assert result.allowlist_expansion_attempts == 3

    def test_allowlist_violation_records_files(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test that allowlist violation records changed files."""
        event = AllowlistViolation(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            disallowed_paths=["test.py"],
            changed_files=["main.py", "test.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert "main.py" in result.last_changed_files
        assert "test.py" in result.last_changed_files


class TestWorkerFailed:
    """Test handling of worker failure events."""

    def test_worker_failed_within_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker failure when under attempt limit."""
        event = WorkerFailed(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.IMPLEMENT,
            error_type="timeout",
            error_detail="Worker timed out",
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.IMPLEMENT
        assert result.worker_attempts == 1
        assert result.last_error == "Worker timed out"

    def test_worker_failed_exhausted_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker failure when attempt limit exhausted."""
        fresh_task.worker_attempts = 4

        event = WorkerFailed(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.IMPLEMENT,
            error_type="error",
            error_detail="Fatal error",
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert result.block_reason == "WORKER_FAILED"
        assert result.worker_attempts == 5

    def test_worker_failed_review_step(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker failure on review step uses separate counter."""
        fresh_task.step = TaskStep.REVIEW

        event = WorkerFailed(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.REVIEW,
            error_type="invalid_review",
            error_detail="Review format invalid",
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.review_gen_attempts == 1
        assert result.worker_attempts == 0  # Doesn't increment worker attempts


class TestWorkerSucceeded:
    """Test handling of worker success events."""

    def test_worker_succeeded_plan_valid(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker succeeded with valid plan."""
        event = WorkerSucceeded(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.PLAN_IMPL,
            plan_valid=True,
            impl_plan_path="/path/to/plan.json",
            impl_plan_hash="abc123",
            changed_files=[],
            introduced_changes=False,
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.IMPLEMENT
        assert result.impl_plan_path == "/path/to/plan.json"
        assert result.impl_plan_hash == "abc123"
        assert result.plan_attempts == 0

    def test_worker_succeeded_plan_invalid(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker succeeded but plan invalid."""
        event = WorkerSucceeded(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.PLAN_IMPL,
            plan_valid=False,
            plan_issue="Missing required fields",
            changed_files=[],
            introduced_changes=False,
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.PLAN_IMPL
        assert result.plan_attempts == 1
        assert "Missing required fields" in result.last_error

    def test_worker_succeeded_implement_with_changes(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test worker succeeded implementation with changes."""
        fresh_task.step = TaskStep.IMPLEMENT

        event = WorkerSucceeded(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            step=TaskStep.IMPLEMENT,
            introduced_changes=True,
            changed_files=["src/main.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.VERIFY
        assert result.no_progress_attempts == 0


class TestNoIntroducedChanges:
    """Test handling of no introduced changes events."""

    def test_no_changes_repo_dirty(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test no introduced changes but repo is dirty."""
        fresh_task.step = TaskStep.IMPLEMENT

        event = NoIntroducedChanges(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            repo_dirty=True,
            changed_files=["existing_change.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.VERIFY
        assert result.no_progress_attempts == 0

    def test_no_changes_repo_clean_within_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test no changes with clean repo, within attempt limit."""
        fresh_task.step = TaskStep.IMPLEMENT

        event = NoIntroducedChanges(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            repo_dirty=False,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.IMPLEMENT
        assert result.no_progress_attempts == 1
        assert "No changes detected" in result.last_error

    def test_no_changes_exhausted_attempts(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test no changes when attempt limit exhausted."""
        fresh_task.step = TaskStep.IMPLEMENT
        fresh_task.no_progress_attempts = 2

        event = NoIntroducedChanges(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            repo_dirty=False,
            changed_files=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert result.block_reason == "NO_PROGRESS"
        assert result.no_progress_attempts == 3


class TestVerificationResult:
    """Test handling of verification result events."""

    def test_verification_passed(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test successful verification."""
        fresh_task.step = TaskStep.VERIFY

        event = VerificationResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            passed=True,
            command="pytest",
            exit_code=0,
            log_path="/logs/test.log",
            log_tail="All tests passed",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.REVIEW
        assert result.test_fail_attempts == 0
        assert result.last_error is None

    def test_verification_failed(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test failed verification."""
        fresh_task.step = TaskStep.VERIFY

        event = VerificationResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            passed=False,
            command="pytest",
            exit_code=1,
            log_path="/logs/test.log",
            log_tail="Test failed: test_foo",
            error_type="tests_failed",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.last_error_type == "tests_failed"
        assert "Verification failed" in result.last_error
        assert result.last_verification is not None

    def test_verification_tool_missing(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test verification with missing tool."""
        fresh_task.step = TaskStep.VERIFY

        event = VerificationResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            passed=False,
            command="pytest",
            exit_code=127,
            log_path="/logs/test.log",
            log_tail="pytest: command not found",
            error_type="tool_missing",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert result.block_reason == "TOOL_MISSING"
        assert len(result.human_blocking_issues) > 0
        assert any("pytest" in issue.lower() for issue in result.human_blocking_issues)

    def test_verification_records_details(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test that verification records all details."""
        fresh_task.step = TaskStep.VERIFY

        event = VerificationResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            passed=True,
            command="make test",
            exit_code=0,
            log_path="/logs/make.log",
            log_tail="Build successful",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.last_verification["command"] == "make test"
        assert result.last_verification["exit_code"] == 0
        assert result.last_verification["log_path"] == "/logs/make.log"
        assert "Build successful" in result.last_verification["log_tail"]


class TestReviewResult:
    """Test handling of review result events."""

    def test_review_mergeable(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test review with mergeable result."""
        fresh_task.step = TaskStep.REVIEW

        event = ReviewResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            mergeable=True,
            issues=[],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.READY
        assert result.step == TaskStep.COMMIT

    def test_review_with_blockers(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test review with blocking issues."""
        fresh_task.step = TaskStep.REVIEW

        event = ReviewResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            mergeable=False,
            issues=["Syntax error in main.py", "Missing docstrings"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.last_review_mergeable is False
        assert len(result.last_review_issues) == 2


class TestCommitResult:
    """Test handling of commit result events."""

    def test_commit_success(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test successful commit."""
        fresh_task.step = TaskStep.COMMIT

        event = CommitResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            committed=True,
            commit_sha="abc123def",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.COMPLETE
        assert result.commit_sha == "abc123def"

    def test_commit_failure(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test failed commit."""
        fresh_task.step = TaskStep.COMMIT

        event = CommitResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            committed=False,
            error="Git push failed",
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert result.lifecycle == TaskLifecycle.WAITING_HUMAN
        assert "Git push failed" in result.last_error


class TestResumePromptResult:
    """Test handling of resume prompt results."""

    def test_resume_prompt_success(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test successful resume prompt."""
        event = ResumePromptResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            succeeded=True,
            changed_files=["fixed.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        # Resume prompt clears the current blocking state
        assert result.last_run_id == "run-123"
        assert "fixed.py" in result.last_changed_files

    def test_resume_prompt_records_changes(
        self,
        fresh_task: TaskState,
        caps: dict[str, int],
    ):
        """Test that resume prompt records changed files."""
        event = ResumePromptResult(
            run_id="run-123",
            task_id="task-1",
            phase="phase-1",
            succeeded=True,
            changed_files=["file1.py", "file2.py"],
            captured_at="2024-01-01T00:00:00Z",
        )

        result = reduce_task(fresh_task, event, caps=caps)

        assert len(result.last_changed_files) == 2
        assert "file1.py" in result.last_changed_files
        assert "file2.py" in result.last_changed_files
