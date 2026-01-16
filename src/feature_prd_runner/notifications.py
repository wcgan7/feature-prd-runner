"""Desktop notifications for human-in-the-loop events.

This module provides desktop notifications for approval gates, errors,
and other important events that require human attention.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger


class NotificationManager:
    """Manage desktop notifications for HITL events."""

    def __init__(self, enabled: bool = True):
        """Initialize notification manager.

        Args:
            enabled: Whether notifications are enabled.
        """
        self.enabled = enabled
        self._notifier = None

        if enabled:
            self._initialize_notifier()

    def _initialize_notifier(self) -> None:
        """Initialize the notification backend."""
        try:
            from plyer import notification

            self._notifier = notification
            logger.debug("Desktop notifications initialized")
        except ImportError:
            logger.warning(
                "plyer not installed - desktop notifications disabled. "
                "Install with: pip install plyer"
            )
            self.enabled = False

    def notify_approval_required(
        self,
        gate_type: str,
        message: str,
        task_id: Optional[str] = None,
    ) -> None:
        """Send notification that approval is required.

        Args:
            gate_type: Type of approval gate.
            message: Approval message.
            task_id: Optional task ID.
        """
        if not self.enabled or not self._notifier:
            return

        title = f"🔔 Approval Required: {gate_type}"
        body = message
        if task_id:
            body = f"Task: {task_id}\n{message}"

        self._send_notification(title, body, timeout=0)

    def notify_approval_timeout(
        self,
        gate_type: str,
        task_id: Optional[str] = None,
    ) -> None:
        """Send notification that approval timed out.

        Args:
            gate_type: Type of approval gate.
            task_id: Optional task ID.
        """
        if not self.enabled or not self._notifier:
            return

        title = f"⏱️ Approval Timeout: {gate_type}"
        body = "Auto-approved due to timeout"
        if task_id:
            body = f"Task: {task_id}\n{body}"

        self._send_notification(title, body)

    def notify_run_blocked(
        self,
        reason: str,
        task_id: Optional[str] = None,
    ) -> None:
        """Send notification that run is blocked.

        Args:
            reason: Reason for blocking.
            task_id: Optional task ID.
        """
        if not self.enabled or not self._notifier:
            return

        title = "🚫 Run Blocked"
        body = reason
        if task_id:
            body = f"Task: {task_id}\n{reason}"

        self._send_notification(title, body, timeout=0)

    def notify_run_error(
        self,
        error: str,
        task_id: Optional[str] = None,
    ) -> None:
        """Send notification that run encountered an error.

        Args:
            error: Error message.
            task_id: Optional task ID.
        """
        if not self.enabled or not self._notifier:
            return

        title = "❌ Run Error"
        body = error[:200]  # Truncate long errors
        if task_id:
            body = f"Task: {task_id}\n{body}"

        self._send_notification(title, body)

    def notify_run_complete(
        self,
        success: bool,
        summary: Optional[str] = None,
    ) -> None:
        """Send notification that run completed.

        Args:
            success: Whether run completed successfully.
            summary: Optional summary message.
        """
        if not self.enabled or not self._notifier:
            return

        if success:
            title = "✅ Run Complete"
            body = summary or "All tasks completed successfully"
        else:
            title = "⚠️ Run Complete with Issues"
            body = summary or "Some tasks failed or were blocked"

        self._send_notification(title, body)

    def notify_steering_message(
        self,
        message: str,
        from_worker: bool = False,
    ) -> None:
        """Send notification for steering messages.

        Args:
            message: Steering message.
            from_worker: Whether message is from worker (vs to worker).
        """
        if not self.enabled or not self._notifier:
            return

        if from_worker:
            title = "💬 Message from Worker"
        else:
            title = "💬 Steering Message Sent"

        self._send_notification(title, message[:200])

    def _send_notification(
        self,
        title: str,
        message: str,
        timeout: int = 10,
    ) -> None:
        """Send desktop notification.

        Args:
            title: Notification title.
            message: Notification message.
            timeout: Timeout in seconds (0 = no timeout).
        """
        if not self._notifier:
            return

        try:
            self._notifier.notify(
                title=title,
                message=message,
                app_name="Feature PRD Runner",
                timeout=timeout,
            )
            logger.debug("Notification sent: {}", title)
        except Exception as e:
            logger.warning("Failed to send notification: {}", e)


def create_notification_manager(config: dict) -> Optional[NotificationManager]:
    """Create notification manager from config.

    Args:
        config: Configuration dict.

    Returns:
        NotificationManager or None if disabled.
    """
    hitl_config = config.get("human_in_the_loop", {})
    notifications_config = hitl_config.get("notifications", {})

    enabled = notifications_config.get("desktop", False)

    if enabled:
        return NotificationManager(enabled=True)

    return None
