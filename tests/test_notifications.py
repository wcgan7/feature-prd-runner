"""Tests for notifications module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from feature_prd_runner.notifications import (
    NotificationManager,
    create_notification_manager,
)


class TestNotificationManager:
    """Test NotificationManager class."""

    @patch("feature_prd_runner.notifications.notification")
    def test_init_enabled(self, mock_notification: MagicMock):
        """Test initialization with notifications enabled."""
        manager = NotificationManager(enabled=True)
        assert manager.enabled is True
        assert manager._notifier == mock_notification

    def test_init_disabled(self):
        """Test initialization with notifications disabled."""
        manager = NotificationManager(enabled=False)
        assert manager.enabled is False
        assert manager._notifier is None

    @patch("feature_prd_runner.notifications.notification")
    def test_init_import_error(self, mock_notification: MagicMock):
        """Test initialization when plyer is not installed."""
        with patch("feature_prd_runner.notifications.notification", side_effect=ImportError):
            manager = NotificationManager(enabled=True)
            assert manager.enabled is False
            assert manager._notifier is None

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_approval_required(self, mock_notification: MagicMock):
        """Test sending approval required notification."""
        manager = NotificationManager(enabled=True)
        manager.notify_approval_required(
            gate_type="before_implement",
            message="Review plan?",
            task_id="task-123",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "before_implement" in call_args["title"]
        assert "task-123" in call_args["message"]
        assert "Review plan?" in call_args["message"]
        assert call_args["timeout"] == 0  # No timeout for approval required

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_approval_required_no_task_id(self, mock_notification: MagicMock):
        """Test approval required notification without task ID."""
        manager = NotificationManager(enabled=True)
        manager.notify_approval_required(
            gate_type="after_implement",
            message="Review changes?",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "after_implement" in call_args["title"]
        assert "Review changes?" in call_args["message"]

    def test_notify_approval_required_disabled(self):
        """Test that notification is not sent when disabled."""
        manager = NotificationManager(enabled=False)
        manager.notify_approval_required(
            gate_type="before_implement",
            message="Review plan?",
        )
        # Should not raise, just silently skip

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_approval_timeout(self, mock_notification: MagicMock):
        """Test sending approval timeout notification."""
        manager = NotificationManager(enabled=True)
        manager.notify_approval_timeout(
            gate_type="before_implement",
            task_id="task-123",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Timeout" in call_args["title"]
        assert "before_implement" in call_args["title"]
        assert "task-123" in call_args["message"]
        assert "Auto-approved" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_blocked(self, mock_notification: MagicMock):
        """Test sending run blocked notification."""
        manager = NotificationManager(enabled=True)
        manager.notify_run_blocked(
            reason="Tests failed",
            task_id="task-123",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Blocked" in call_args["title"]
        assert "Tests failed" in call_args["message"]
        assert "task-123" in call_args["message"]
        assert call_args["timeout"] == 0  # No timeout for blocked

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_error(self, mock_notification: MagicMock):
        """Test sending run error notification."""
        manager = NotificationManager(enabled=True)
        manager.notify_run_error(
            error="Unexpected exception occurred",
            task_id="task-123",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Error" in call_args["title"]
        assert "Unexpected exception" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_error_truncates_long_messages(self, mock_notification: MagicMock):
        """Test that long error messages are truncated."""
        manager = NotificationManager(enabled=True)
        long_error = "x" * 300

        manager.notify_run_error(error=long_error)

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert len(call_args["message"]) <= 200

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_complete_success(self, mock_notification: MagicMock):
        """Test sending run complete notification for success."""
        manager = NotificationManager(enabled=True)
        manager.notify_run_complete(
            success=True,
            summary="All 5 tasks completed",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Complete" in call_args["title"]
        assert "✅" in call_args["title"]
        assert "All 5 tasks completed" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_complete_with_issues(self, mock_notification: MagicMock):
        """Test sending run complete notification with issues."""
        manager = NotificationManager(enabled=True)
        manager.notify_run_complete(
            success=False,
            summary="2 tasks failed",
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Complete with Issues" in call_args["title"]
        assert "⚠️" in call_args["title"]
        assert "2 tasks failed" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_run_complete_default_messages(self, mock_notification: MagicMock):
        """Test run complete with default messages."""
        manager = NotificationManager(enabled=True)

        # Success without summary
        manager.notify_run_complete(success=True)
        call_args = mock_notification.notify.call_args[1]
        assert "successfully" in call_args["message"]

        # Failure without summary
        manager.notify_run_complete(success=False)
        call_args = mock_notification.notify.call_args[1]
        assert "failed" in call_args["message"] or "Issues" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_steering_message_to_worker(self, mock_notification: MagicMock):
        """Test sending steering message notification (to worker)."""
        manager = NotificationManager(enabled=True)
        manager.notify_steering_message(
            message="Please focus on error handling",
            from_worker=False,
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "Sent" in call_args["title"]
        assert "Please focus on error handling" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_steering_message_from_worker(self, mock_notification: MagicMock):
        """Test sending steering message notification (from worker)."""
        manager = NotificationManager(enabled=True)
        manager.notify_steering_message(
            message="Need clarification on requirements",
            from_worker=True,
        )

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert "from Worker" in call_args["title"]
        assert "Need clarification" in call_args["message"]

    @patch("feature_prd_runner.notifications.notification")
    def test_notify_steering_message_truncates(self, mock_notification: MagicMock):
        """Test that long steering messages are truncated."""
        manager = NotificationManager(enabled=True)
        long_message = "x" * 300

        manager.notify_steering_message(message=long_message)

        mock_notification.notify.assert_called_once()
        call_args = mock_notification.notify.call_args[1]

        assert len(call_args["message"]) <= 200

    @patch("feature_prd_runner.notifications.notification")
    def test_notification_exception_handling(self, mock_notification: MagicMock):
        """Test that exceptions in notification sending are handled gracefully."""
        mock_notification.notify.side_effect = Exception("Notification failed")

        manager = NotificationManager(enabled=True)
        # Should not raise exception
        manager.notify_approval_required(
            gate_type="before_implement",
            message="Test",
        )

    @patch("feature_prd_runner.notifications.notification")
    def test_app_name_is_set(self, mock_notification: MagicMock):
        """Test that app name is set correctly."""
        manager = NotificationManager(enabled=True)
        manager.notify_run_complete(success=True)

        call_args = mock_notification.notify.call_args[1]
        assert call_args["app_name"] == "Feature PRD Runner"


class TestCreateNotificationManager:
    """Test create_notification_manager factory function."""

    @patch("feature_prd_runner.notifications.NotificationManager")
    def test_creates_manager_when_enabled(self, mock_manager_class: MagicMock):
        """Test creating notification manager when enabled in config."""
        config = {
            "human_in_the_loop": {
                "notifications": {
                    "desktop": True,
                },
            },
        }

        result = create_notification_manager(config)

        mock_manager_class.assert_called_once_with(enabled=True)
        assert result is not None

    def test_returns_none_when_disabled(self):
        """Test returns None when disabled in config."""
        config = {
            "human_in_the_loop": {
                "notifications": {
                    "desktop": False,
                },
            },
        }

        result = create_notification_manager(config)

        assert result is None

    def test_returns_none_when_config_missing(self):
        """Test returns None when notification config is missing."""
        config = {}

        result = create_notification_manager(config)

        assert result is None

    def test_returns_none_when_hitl_config_missing(self):
        """Test returns None when HITL config section is missing."""
        config = {
            "other_config": {},
        }

        result = create_notification_manager(config)

        assert result is None
