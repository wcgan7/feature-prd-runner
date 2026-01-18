"""Tests for logging_utils module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from feature_prd_runner.logging_utils import (
    pretty,
    summarize_event,
    summarize_pytest_failures,
)


class TestSummarizePytestFailures:
    """Test summarize_pytest_failures function."""

    def test_empty_log(self):
        """Test with empty log text."""
        result = summarize_pytest_failures("")

        assert result["failed"] == []
        assert result["headline"] is None
        assert result["first_error"] is None

    def test_single_failure(self):
        """Test with single test failure."""
        log_text = """
test_module.py::test_something FAILED

________________________________ test_something ________________________________
E   AssertionError: expected 1 but got 2
"""

        result = summarize_pytest_failures(log_text)

        assert len(result["failed"]) == 1
        assert result["failed"][0] == "test_module.py::test_something"
        assert result["headline"] == "test_something"
        assert "AssertionError" in result["first_error"]

    def test_multiple_failures(self):
        """Test with multiple test failures."""
        log_text = """
test_module.py::test_one FAILED
test_module.py::test_two FAILED
test_module.py::test_three FAILED

________________________________ test_one ________________________________
E   AssertionError: test failed
"""

        result = summarize_pytest_failures(log_text)

        assert len(result["failed"]) == 3
        assert result["failed"][0] == "test_module.py::test_one"
        assert result["failed"][1] == "test_module.py::test_two"
        assert result["failed"][2] == "test_module.py::test_three"

    def test_max_failed_limit(self):
        """Test that max_failed limits the number of failures captured."""
        log_text = """
test_a.py::test_1 FAILED
test_a.py::test_2 FAILED
test_a.py::test_3 FAILED
test_a.py::test_4 FAILED
test_a.py::test_5 FAILED
test_a.py::test_6 FAILED
test_a.py::test_7 FAILED
"""

        result = summarize_pytest_failures(log_text, max_failed=3)

        assert len(result["failed"]) == 3
        assert result["failed"][0] == "test_a.py::test_1"
        assert result["failed"][2] == "test_a.py::test_3"

    def test_default_max_failed(self):
        """Test default max_failed is 5."""
        log_text = """
test_a.py::test_1 FAILED
test_a.py::test_2 FAILED
test_a.py::test_3 FAILED
test_a.py::test_4 FAILED
test_a.py::test_5 FAILED
test_a.py::test_6 FAILED
test_a.py::test_7 FAILED
"""

        result = summarize_pytest_failures(log_text)

        assert len(result["failed"]) == 5

    def test_extracts_assertion_error(self):
        """Test extraction of assertion error."""
        log_text = """
________________________________ test_example ________________________________
E   AssertionError: assert 1 == 2
E    +  where 1 = func()
"""

        result = summarize_pytest_failures(log_text)

        assert result["first_error"] == "E   AssertionError: assert 1 == 2"

    def test_extracts_exception(self):
        """Test extraction of exception."""
        log_text = """
________________________________ test_example ________________________________
E   ValueError: invalid input
"""

        result = summarize_pytest_failures(log_text)

        assert result["first_error"] == "E   ValueError: invalid input"

    def test_extracts_headline(self):
        """Test extraction of failure headline."""
        log_text = """
_________________________ test_complex_function _________________________
E   RuntimeError: something went wrong
"""

        result = summarize_pytest_failures(log_text)

        assert result["headline"] == "test_complex_function"

    def test_no_assertion_line(self):
        """Test when no assertion line is found."""
        log_text = """
FAILED test_module.py::test_something
"""

        result = summarize_pytest_failures(log_text)

        assert result["first_error"] is None

    def test_no_headline(self):
        """Test when no headline is found."""
        log_text = """
FAILED test_module.py::test_something
E   AssertionError: failed
"""

        result = summarize_pytest_failures(log_text)

        assert result["headline"] is None

    def test_complex_pytest_output(self):
        """Test with realistic complex pytest output."""
        log_text = """
collected 10 items

test_module.py::test_success PASSED
test_module.py::test_fail FAILED
test_module.py::test_error FAILED

================================= FAILURES =================================
_______________________________ test_fail _______________________________

    def test_fail():
>       assert 1 == 2
E       AssertionError: assert 1 == 2

test_module.py:10: AssertionError
_______________________________ test_error _______________________________

    def test_error():
>       raise ValueError("intentional error")
E       ValueError: intentional error

test_module.py:15: ValueError
=========================== short test summary info ========================
FAILED test_module.py::test_fail - AssertionError: assert 1 == 2
FAILED test_module.py::test_error - ValueError: intentional error
"""

        result = summarize_pytest_failures(log_text)

        assert len(result["failed"]) == 2
        assert "test_fail" in result["failed"][0]
        assert "test_error" in result["failed"][1]
        assert result["headline"] == "test_fail"
        assert "AssertionError" in result["first_error"]


class MockEvent:
    """Mock event class for testing."""

    def __init__(self, name: str, **kwargs):
        """Initialize mock event."""
        self.__class__.__name__ = name
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestSummarizeEvent:
    """Test summarize_event function."""

    def test_none_event(self):
        """Test with None event."""
        result = summarize_event(None)

        assert result == {"event": None}

    def test_basic_event(self):
        """Test with basic event."""
        event = MockEvent("TaskStarted")

        result = summarize_event(event)

        assert result["event"] == "TaskStarted"

    def test_event_with_run_id(self):
        """Test event with run_id attribute."""
        event = MockEvent("WorkerStarted", run_id="run-123")

        result = summarize_event(event)

        assert result["event"] == "WorkerStarted"
        assert result["run_id"] == "run-123"

    def test_event_with_step(self):
        """Test event with step attribute."""
        step_mock = MagicMock()
        step_mock.value = "implement"

        event = MockEvent("WorkerStarted", step=step_mock)

        result = summarize_event(event)

        assert result["step"] == "implement"

    def test_event_with_step_string(self):
        """Test event with step as string."""
        event = MockEvent("WorkerStarted", step="verify")

        result = summarize_event(event)

        assert result["step"] == "verify"

    def test_event_with_run_dir(self):
        """Test event with run_dir."""
        event = MockEvent("WorkerStarted")
        run_dir = Path("/tmp/run-123")

        result = summarize_event(event, run_dir=run_dir)

        assert result["run_dir"] == str(run_dir)

    def test_worker_failed_event(self):
        """Test WorkerFailed event."""
        event = MockEvent(
            "WorkerFailed",
            run_id="run-123",
            error_type="timeout",
            error_detail="Worker timed out after 300 seconds",
            timed_out=True,
            no_heartbeat=False,
            introduced_changes=["file1.py", "file2.py"],
            changed_files=["file1.py", "file2.py", "file3.py"],
            stderr_tail="Error: timeout",
        )

        result = summarize_event(event)

        assert result["event"] == "WorkerFailed"
        assert result["error_type"] == "timeout"
        assert result["error_detail"] == "Worker timed out after 300 seconds"
        assert result["timed_out"] is True
        assert result["no_heartbeat"] is False
        assert result["introduced_n"] == 2
        assert result["changed_n"] == 3
        assert result["stderr_tail"] == "Error: timeout"

    def test_worker_failed_with_run_dir(self):
        """Test WorkerFailed event with run_dir."""
        event = MockEvent(
            "WorkerFailed",
            error_type="error",
            error_detail="Failed",
        )
        run_dir = Path("/tmp/run-123")

        result = summarize_event(event, run_dir=run_dir)

        assert result["manifest"] == str(run_dir / "manifest.json")

    def test_worker_failed_truncates_long_detail(self):
        """Test that long error_detail is truncated."""
        long_detail = "x" * 300

        event = MockEvent(
            "WorkerFailed",
            error_type="error",
            error_detail=long_detail,
        )

        result = summarize_event(event)

        assert len(result["error_detail"]) == 241  # 240 + "…"
        assert result["error_detail"].endswith("…")

    def test_worker_failed_truncates_long_stderr(self):
        """Test that long stderr_tail is truncated."""
        long_stderr = "x" * 300

        event = MockEvent(
            "WorkerFailed",
            error_type="error",
            error_detail="Failed",
            stderr_tail=long_stderr,
        )

        result = summarize_event(event)

        assert len(result["stderr_tail"]) == 241  # 240 + "…"
        assert result["stderr_tail"].endswith("…")

    def test_worker_failed_empty_stderr(self):
        """Test WorkerFailed with empty stderr_tail."""
        event = MockEvent(
            "WorkerFailed",
            error_type="error",
            error_detail="Failed",
            stderr_tail="",
        )

        result = summarize_event(event)

        assert "stderr_tail" not in result

    def test_worker_succeeded_event(self):
        """Test WorkerSucceeded event."""
        event = MockEvent(
            "WorkerSucceeded",
            run_id="run-123",
            introduced_changes=["new_file.py"],
            changed_files=["file1.py", "file2.py"],
            repo_dirty=False,
        )

        result = summarize_event(event)

        assert result["event"] == "WorkerSucceeded"
        assert result["introduced_n"] == 1
        assert result["changed_n"] == 2
        assert result["repo_dirty"] is False

    def test_worker_succeeded_plan_impl(self):
        """Test WorkerSucceeded for plan_impl step."""
        step_mock = MagicMock()
        step_mock.value = "plan_impl"

        event = MockEvent(
            "WorkerSucceeded",
            step=step_mock,
            introduced_changes=[],
            changed_files=[],
            plan_valid=True,
        )

        result = summarize_event(event)

        assert result["step"] == "plan_impl"
        assert result["plan_valid"] is True

    def test_worker_succeeded_plan_impl_with_issue(self):
        """Test WorkerSucceeded for plan_impl with issue."""
        step_mock = MagicMock()
        step_mock.value = "plan_impl"

        event = MockEvent(
            "WorkerSucceeded",
            step=step_mock,
            introduced_changes=[],
            changed_files=[],
            plan_valid=False,
            plan_issue="Invalid plan format",
        )

        result = summarize_event(event)

        assert result["plan_valid"] is False
        assert result["plan_issue"] == "Invalid plan format"

    def test_worker_succeeded_with_run_dir(self):
        """Test WorkerSucceeded with run_dir."""
        event = MockEvent(
            "WorkerSucceeded",
            introduced_changes=[],
            changed_files=[],
        )
        run_dir = Path("/tmp/run-123")

        result = summarize_event(event, run_dir=run_dir)

        assert result["manifest"] == str(run_dir / "manifest.json")

    def test_verification_result_event(self):
        """Test VerificationResult event."""
        event = MockEvent(
            "VerificationResult",
            run_id="run-123",
            passed=True,
            exit_code=0,
            needs_allowlist_expansion=False,
            failing_paths=[],
        )

        result = summarize_event(event)

        assert result["event"] == "VerificationResult"
        assert result["passed"] is True
        assert result["exit_code"] == 0
        assert result["needs_expansion"] is False
        assert result["expansion_n"] == 0

    def test_verification_result_failed(self):
        """Test failed VerificationResult."""
        event = MockEvent(
            "VerificationResult",
            passed=False,
            exit_code=1,
            needs_allowlist_expansion=True,
            failing_paths=["test1.py", "test2.py", "test3.py", "test4.py"],
            error_type="test_failed",
        )

        result = summarize_event(event)

        assert result["passed"] is False
        assert result["exit_code"] == 1
        assert result["needs_expansion"] is True
        assert result["expansion_n"] == 4
        assert result["expansion_sample"] == ["test1.py", "test2.py", "test3.py"]
        assert result["error_type"] == "test_failed"

    def test_verification_result_with_run_dir(self):
        """Test VerificationResult with run_dir."""
        event = MockEvent(
            "VerificationResult",
            passed=True,
            exit_code=0,
        )
        run_dir = Path("/tmp/run-123")

        result = summarize_event(event, run_dir=run_dir)

        assert result["verify_manifest"] == str(run_dir / "verify_manifest.json")

    def test_review_result_event(self):
        """Test ReviewResult event."""
        event = MockEvent(
            "ReviewResult",
            mergeable=True,
            issues=[],
        )

        result = summarize_event(event)

        assert result["event"] == "ReviewResult"
        assert result["mergeable"] is True
        assert result["issues_n"] == 0

    def test_review_result_with_issues(self):
        """Test ReviewResult with blocking issues."""
        event = MockEvent(
            "ReviewResult",
            mergeable=False,
            issues=["Issue 1", "Issue 2"],
        )

        result = summarize_event(event)

        assert result["mergeable"] is False
        assert result["issues_n"] == 2

    def test_allowlist_violation_event(self):
        """Test AllowlistViolation event."""
        event = MockEvent(
            "AllowlistViolation",
            disallowed_paths=["file1.py", "file2.py"],
            introduced_changes=["file1.py"],
        )

        result = summarize_event(event)

        assert result["event"] == "AllowlistViolation"
        assert result["disallowed_n"] == 2
        assert result["introduced_n"] == 1

    def test_allowlist_violation_with_run_dir(self):
        """Test AllowlistViolation with run_dir."""
        event = MockEvent(
            "AllowlistViolation",
            disallowed_paths=[],
            introduced_changes=[],
        )
        run_dir = Path("/tmp/run-123")

        result = summarize_event(event, run_dir=run_dir)

        assert result["manifest"] == str(run_dir / "manifest.json")

    def test_unknown_event_type(self):
        """Test with unknown event type."""
        event = MockEvent("CustomEvent", run_id="run-123")

        result = summarize_event(event)

        # Should still include basic info
        assert result["event"] == "CustomEvent"
        assert result["run_id"] == "run-123"

    def test_event_with_none_attributes(self):
        """Test event with None attributes."""
        event = MockEvent(
            "WorkerFailed",
            error_type=None,
            error_detail=None,
            introduced_changes=None,
            changed_files=None,
            stderr_tail=None,
        )

        result = summarize_event(event)

        assert result["error_type"] is None
        assert result["error_detail"] == ""
        assert result["introduced_n"] == 0
        assert result["changed_n"] == 0
        assert "stderr_tail" not in result


class TestPretty:
    """Test pretty function."""

    def test_simple_dict(self):
        """Test pretty printing simple dictionary."""
        obj = {"key": "value", "number": 42}

        result = pretty(obj)

        assert '"key": "value"' in result
        assert '"number": 42' in result

    def test_nested_dict(self):
        """Test pretty printing nested dictionary."""
        obj = {
            "outer": {
                "inner": {
                    "value": 123,
                },
            },
        }

        result = pretty(obj)

        assert "outer" in result
        assert "inner" in result
        assert "123" in result

    def test_list(self):
        """Test pretty printing list."""
        obj = [1, 2, 3, 4, 5]

        result = pretty(obj)

        assert "[" in result
        assert "1" in result
        assert "5" in result

    def test_custom_indent(self):
        """Test with custom indent."""
        obj = {"a": {"b": 1}}

        result2 = pretty(obj, indent=2)
        result4 = pretty(obj, indent=4)

        # More indentation should result in longer string
        assert len(result4) > len(result2)

    def test_string(self):
        """Test pretty printing string."""
        obj = "simple string"

        result = pretty(obj)

        assert result == '"simple string"'

    def test_number(self):
        """Test pretty printing number."""
        result = pretty(42)

        assert result == "42"

    def test_boolean(self):
        """Test pretty printing boolean."""
        result_true = pretty(True)
        result_false = pretty(False)

        assert result_true == "true"
        assert result_false == "false"

    def test_none(self):
        """Test pretty printing None."""
        result = pretty(None)

        assert result == "null"

    def test_non_json_serializable(self):
        """Test with non-JSON serializable object."""

        class CustomClass:
            def __str__(self):
                return "CustomClass instance"

        obj = CustomClass()

        result = pretty(obj)

        # Should fall back to str()
        assert "CustomClass instance" in result

    def test_complex_object_with_default_str(self):
        """Test complex object uses str fallback."""
        from datetime import datetime

        obj = {
            "timestamp": datetime(2024, 1, 1, 12, 0, 0),
            "name": "test",
        }

        result = pretty(obj)

        # Should serialize datetime as string
        assert "2024-01-01" in result
        assert "test" in result

    def test_empty_dict(self):
        """Test pretty printing empty dict."""
        result = pretty({})

        assert result == "{}"

    def test_empty_list(self):
        """Test pretty printing empty list."""
        result = pretty([])

        assert result == "[]"

    def test_mixed_types(self):
        """Test pretty printing mixed types."""
        obj = {
            "string": "text",
            "number": 42,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"key": "value"},
        }

        result = pretty(obj)

        assert "text" in result
        assert "42" in result
        assert "true" in result
        assert "null" in result
        assert "[" in result
        assert "key" in result
