"""Tests for approval gates module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from feature_prd_runner.approval_gates import (
    ApprovalGateManager,
    GateConfig,
    GateType,
    create_default_gates_config,
)
from feature_prd_runner.messaging import ApprovalResponse


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def progress_path(temp_dir: Path) -> Path:
    """Create a progress.json path."""
    return temp_dir / "progress.json"


@pytest.fixture
def basic_config() -> dict[str, Any]:
    """Basic approval gates configuration."""
    return {
        "approval_gates": {
            "enabled": True,
            "gates": {
                "before_implement": {
                    "enabled": True,
                    "message": "Review implementation plan?",
                    "show_plan": True,
                    "timeout": 60,
                },
                "after_implement": {
                    "enabled": True,
                    "message": "Review changes?",
                    "show_diff": True,
                    "timeout": 120,
                },
                "before_commit": {
                    "enabled": True,
                    "message": "Approve commit?",
                    "show_diff": True,
                    "required": True,
                },
            },
        },
    }


@pytest.fixture
def disabled_config() -> dict[str, Any]:
    """Configuration with gates disabled."""
    return {
        "approval_gates": {
            "enabled": False,
            "gates": {},
        },
    }


class TestGateType:
    """Test GateType enum."""

    def test_gate_types_exist(self):
        """Test that all expected gate types exist."""
        assert GateType.BEFORE_PLAN_IMPL == "before_plan_impl"
        assert GateType.BEFORE_IMPLEMENT == "before_implement"
        assert GateType.AFTER_IMPLEMENT == "after_implement"
        assert GateType.BEFORE_VERIFY == "before_verify"
        assert GateType.AFTER_VERIFY == "after_verify"
        assert GateType.BEFORE_REVIEW == "before_review"
        assert GateType.AFTER_REVIEW_ISSUES == "after_review_issues"
        assert GateType.BEFORE_COMMIT == "before_commit"


class TestGateConfig:
    """Test GateConfig dataclass."""

    def test_default_config(self):
        """Test default GateConfig values."""
        config = GateConfig()
        assert config.enabled is False
        assert config.message is None
        assert config.show_diff is False
        assert config.show_plan is False
        assert config.show_tests is False
        assert config.show_review is False
        assert config.timeout == 300
        assert config.required is False
        assert config.allow_edit is False

    def test_custom_config(self):
        """Test custom GateConfig values."""
        config = GateConfig(
            enabled=True,
            message="Custom message",
            show_diff=True,
            timeout=600,
            required=True,
        )
        assert config.enabled is True
        assert config.message == "Custom message"
        assert config.show_diff is True
        assert config.timeout == 600
        assert config.required is True


class TestApprovalGateManager:
    """Test ApprovalGateManager class."""

    def test_init(self, basic_config: dict[str, Any]):
        """Test initialization."""
        manager = ApprovalGateManager(basic_config)
        assert manager.config == basic_config
        assert manager.console is not None
        assert manager.notification_manager is None

    def test_init_with_notification_manager(self, basic_config: dict[str, Any]):
        """Test initialization with notification manager."""
        mock_notifier = MagicMock()
        manager = ApprovalGateManager(basic_config, notification_manager=mock_notifier)
        assert manager.notification_manager == mock_notifier

    def test_is_gate_enabled_true(self, basic_config: dict[str, Any]):
        """Test gate enabled check when gate is enabled."""
        manager = ApprovalGateManager(basic_config)
        assert manager.is_gate_enabled(GateType.BEFORE_IMPLEMENT) is True
        assert manager.is_gate_enabled(GateType.AFTER_IMPLEMENT) is True

    def test_is_gate_enabled_false_gate_disabled(self, basic_config: dict[str, Any]):
        """Test gate enabled check when specific gate is disabled."""
        basic_config["approval_gates"]["gates"]["before_implement"]["enabled"] = False
        manager = ApprovalGateManager(basic_config)
        assert manager.is_gate_enabled(GateType.BEFORE_IMPLEMENT) is False

    def test_is_gate_enabled_false_global_disabled(self, disabled_config: dict[str, Any]):
        """Test gate enabled check when approval gates globally disabled."""
        manager = ApprovalGateManager(disabled_config)
        assert manager.is_gate_enabled(GateType.BEFORE_IMPLEMENT) is False

    def test_is_gate_enabled_missing_gate(self, basic_config: dict[str, Any]):
        """Test gate enabled check for non-existent gate."""
        manager = ApprovalGateManager(basic_config)
        assert manager.is_gate_enabled(GateType.BEFORE_PLAN_IMPL) is False

    def test_get_gate_config(self, basic_config: dict[str, Any]):
        """Test getting gate configuration."""
        manager = ApprovalGateManager(basic_config)
        config = manager.get_gate_config(GateType.BEFORE_IMPLEMENT)

        assert config.enabled is True
        assert config.message == "Review implementation plan?"
        assert config.show_plan is True
        assert config.timeout == 60

    def test_get_gate_config_defaults(self, basic_config: dict[str, Any]):
        """Test getting gate config with default values."""
        manager = ApprovalGateManager(basic_config)
        config = manager.get_gate_config(GateType.BEFORE_PLAN_IMPL)

        assert config.enabled is False
        assert config.message is None
        assert config.timeout == 300  # Default

    def test_get_gate_config_required(self, basic_config: dict[str, Any]):
        """Test getting config for required gate."""
        manager = ApprovalGateManager(basic_config)
        config = manager.get_gate_config(GateType.BEFORE_COMMIT)

        assert config.enabled is True
        assert config.required is True

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_disabled_gate(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test requesting approval for a disabled gate."""
        basic_config["approval_gates"]["gates"]["before_implement"]["enabled"] = False
        manager = ApprovalGateManager(basic_config)

        response = manager.request_approval(
            GateType.BEFORE_IMPLEMENT,
            progress_path,
            {"task_id": "test-task"},
        )

        assert response.approved is True
        assert response.feedback == "Gate not enabled"
        mock_bus_class.assert_not_called()

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_approved(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test requesting approval that is approved."""
        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        approved_response = ApprovalResponse(
            request_id="test-request",
            approved=True,
            feedback="Looks good",
            responded_at=datetime.now(timezone.utc).isoformat(),
        )
        mock_bus.request_approval.return_value = approved_response

        manager = ApprovalGateManager(basic_config)
        response = manager.request_approval(
            GateType.BEFORE_IMPLEMENT,
            progress_path,
            {"task_id": "test-task", "phase_id": "impl"},
        )

        assert response.approved is True
        assert response.feedback == "Looks good"
        mock_bus.request_approval.assert_called_once()

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_rejected(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test requesting approval that is rejected."""
        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        rejected_response = ApprovalResponse(
            request_id="test-request",
            approved=False,
            feedback="Needs more work",
            responded_at=datetime.now(timezone.utc).isoformat(),
        )
        mock_bus.request_approval.return_value = rejected_response

        manager = ApprovalGateManager(basic_config)
        response = manager.request_approval(
            GateType.BEFORE_IMPLEMENT,
            progress_path,
            {"task_id": "test-task"},
        )

        assert response.approved is False
        assert response.feedback == "Needs more work"

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_with_notification(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test requesting approval sends desktop notification."""
        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        approved_response = ApprovalResponse(
            request_id="test-request",
            approved=True,
            responded_at=datetime.now(timezone.utc).isoformat(),
        )
        mock_bus.request_approval.return_value = approved_response

        mock_notifier = MagicMock()
        manager = ApprovalGateManager(basic_config, notification_manager=mock_notifier)

        manager.request_approval(
            GateType.BEFORE_IMPLEMENT,
            progress_path,
            {"task_id": "test-task"},
        )

        mock_notifier.notify_approval_required.assert_called_once()
        call_args = mock_notifier.notify_approval_required.call_args
        assert call_args[1]["gate_type"] == "before_implement"
        assert "test-task" in str(call_args[1]["task_id"])

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_timeout_notification(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test timeout sends notification."""
        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        timeout_response = ApprovalResponse(
            request_id="test-request",
            approved=True,
            feedback="Auto-approved due to timeout",
            responded_at=datetime.now(timezone.utc).isoformat(),
        )
        mock_bus.request_approval.return_value = timeout_response

        mock_notifier = MagicMock()
        manager = ApprovalGateManager(basic_config, notification_manager=mock_notifier)

        manager.request_approval(
            GateType.BEFORE_IMPLEMENT,
            progress_path,
            {"task_id": "test-task"},
        )

        mock_notifier.notify_approval_timeout.assert_called_once()

    @patch("feature_prd_runner.approval_gates.MessageBus")
    def test_request_approval_required_gate(
        self,
        mock_bus_class: MagicMock,
        basic_config: dict[str, Any],
        progress_path: Path,
    ):
        """Test requesting approval for required gate (no timeout)."""
        mock_bus = MagicMock()
        mock_bus_class.return_value = mock_bus

        approved_response = ApprovalResponse(
            request_id="test-request",
            approved=True,
            responded_at=datetime.now(timezone.utc).isoformat(),
        )
        mock_bus.request_approval.return_value = approved_response

        manager = ApprovalGateManager(basic_config)
        manager.request_approval(
            GateType.BEFORE_COMMIT,  # Required gate
            progress_path,
            {"task_id": "test-task"},
        )

        # Verify approval request was created with None timeout
        approval_request = mock_bus.request_approval.call_args[0][0]
        assert approval_request.timeout is None

    def test_display_context_with_plan(self, basic_config: dict[str, Any]):
        """Test displaying context with plan."""
        manager = ApprovalGateManager(basic_config)
        config = GateConfig(show_plan=True)
        context = {
            "task_id": "test-task",
            "plan": {
                "files_to_change": ["file1.py", "file2.py"],
                "new_files": ["file3.py"],
            },
        }

        # Should not raise
        manager._display_context(config, context)

    def test_display_context_with_diff(self, basic_config: dict[str, Any]):
        """Test displaying context with diff."""
        manager = ApprovalGateManager(basic_config)
        config = GateConfig(show_diff=True)
        context = {
            "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,1 @@\n-old\n+new",
        }

        # Should not raise
        manager._display_context(config, context)

    def test_display_context_with_tests(self, basic_config: dict[str, Any]):
        """Test displaying context with test results."""
        manager = ApprovalGateManager(basic_config)
        config = GateConfig(show_tests=True)
        context = {
            "test_result": {
                "passed": True,
                "exit_code": 0,
            },
        }

        # Should not raise
        manager._display_context(config, context)

    def test_display_context_with_review(self, basic_config: dict[str, Any]):
        """Test displaying context with review results."""
        manager = ApprovalGateManager(basic_config)
        config = GateConfig(show_review=True)
        context = {
            "review": {
                "mergeable": False,
                "issues": [
                    {"severity": "error", "summary": "Syntax error"},
                    {"severity": "warning", "summary": "Unused import"},
                ],
            },
        }

        # Should not raise
        manager._display_context(config, context)

    def test_display_context_with_files_changed(self, basic_config: dict[str, Any]):
        """Test displaying context with files changed."""
        manager = ApprovalGateManager(basic_config)
        config = GateConfig()
        context = {
            "files_changed": [f"file{i}.py" for i in range(15)],
        }

        # Should not raise
        manager._display_context(config, context)


class TestCreateDefaultGatesConfig:
    """Test default gates configuration creation."""

    def test_creates_valid_config(self):
        """Test that default config is created correctly."""
        config = create_default_gates_config()

        assert "approval_gates" in config
        assert config["approval_gates"]["enabled"] is False
        assert "gates" in config["approval_gates"]

    def test_contains_all_standard_gates(self):
        """Test that all standard gates are included."""
        config = create_default_gates_config()
        gates = config["approval_gates"]["gates"]

        assert "before_implement" in gates
        assert "after_implement" in gates
        assert "before_commit" in gates
        assert "after_review_issues" in gates

    def test_before_commit_is_required(self):
        """Test that before_commit gate is required."""
        config = create_default_gates_config()
        before_commit = config["approval_gates"]["gates"]["before_commit"]

        assert before_commit["required"] is True

    def test_gates_have_timeouts(self):
        """Test that gates have timeout configurations."""
        config = create_default_gates_config()
        gates = config["approval_gates"]["gates"]

        for gate_name, gate_config in gates.items():
            if not gate_config.get("required", False):
                assert "timeout" in gate_config
                assert gate_config["timeout"] > 0

    def test_gates_have_messages(self):
        """Test that gates have descriptive messages."""
        config = create_default_gates_config()
        gates = config["approval_gates"]["gates"]

        for gate_name, gate_config in gates.items():
            assert "message" in gate_config
            assert isinstance(gate_config["message"], str)
            assert len(gate_config["message"]) > 0
