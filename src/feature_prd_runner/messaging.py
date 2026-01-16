"""Message bus for bidirectional human-worker communication.

This module provides the infrastructure for humans to communicate with
running workers in real-time, enabling steering, guidance, and approvals.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .io_utils import _load_data, _save_data


@dataclass
class Message:
    """Represents a message in the communication bus."""

    id: str
    type: str  # guidance, clarification_request, approval_request, etc.
    content: str
    timestamp: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ApprovalRequest:
    """Represents a request for human approval."""

    id: str
    gate_type: str  # before_implement, after_implement, before_commit, etc.
    message: str
    context: dict[str, Any]
    timeout: Optional[int] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            gate_type=data.get("gate_type", ""),
            message=data.get("message", ""),
            context=data.get("context", {}),
            timeout=data.get("timeout"),
            created_at=data.get("created_at"),
        )


@dataclass
class ApprovalResponse:
    """Represents a human's response to an approval request."""

    request_id: str
    approved: bool
    feedback: Optional[str] = None
    modifications: Optional[dict[str, Any]] = None
    responded_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalResponse":
        """Create from dictionary."""
        return cls(
            request_id=data.get("request_id", ""),
            approved=data.get("approved", False),
            feedback=data.get("feedback"),
            modifications=data.get("modifications"),
            responded_at=data.get("responded_at"),
        )


class MessageBus:
    """Bidirectional communication bus between human and worker.

    Messages are stored in progress.json for the running worker to pick up.
    This enables real-time steering, guidance, and approvals.
    """

    def __init__(self, progress_path: Path):
        """Initialize message bus.

        Args:
            progress_path: Path to progress.json file for this run.
        """
        self.progress_path = progress_path
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)

    def send_to_worker(self, message: Message) -> None:
        """Send a message to the running worker.

        The worker will see this in progress.json on next heartbeat update.

        Args:
            message: Message to send to worker.
        """
        progress = _load_data(self.progress_path, {})

        messages_to_worker = progress.get("messages_from_human", [])
        messages_to_worker.append(message.to_dict())
        progress["messages_from_human"] = messages_to_worker

        _save_data(self.progress_path, progress)
        logger.info("Message sent to worker: type={} content={}", message.type, message.content[:100])

    def receive_from_worker(self) -> list[Message]:
        """Receive messages from the worker.

        Returns:
            List of messages from the worker since last check.
        """
        progress = _load_data(self.progress_path, {})

        messages_data = progress.get("messages_to_human", [])
        messages = [Message.from_dict(m) for m in messages_data]

        # Clear messages after reading
        if messages:
            progress["messages_to_human"] = []
            _save_data(self.progress_path, progress)
            logger.info("Received {} messages from worker", len(messages))

        return messages

    def request_approval(
        self,
        approval_request: ApprovalRequest,
        poll_interval: float = 1.0,
    ) -> ApprovalResponse:
        """Request approval from human and wait for response.

        This blocks until approval is granted/denied or timeout occurs.

        Args:
            approval_request: The approval request.
            poll_interval: How often to poll for response (seconds).

        Returns:
            ApprovalResponse with the human's decision.
        """
        # Write approval request to progress
        progress = _load_data(self.progress_path, {})
        progress["approval_pending"] = approval_request.to_dict()
        _save_data(self.progress_path, progress)

        logger.info(
            "Approval requested: gate={} message={}",
            approval_request.gate_type,
            approval_request.message,
        )

        # Poll for response
        start_time = time.time()
        timeout = approval_request.timeout or 3600  # 1 hour default

        while True:
            progress = _load_data(self.progress_path, {})

            # Check if response received
            if "approval_response" in progress:
                response_data = progress["approval_response"]
                response = ApprovalResponse.from_dict(response_data)

                # Clear approval state
                progress.pop("approval_pending", None)
                progress.pop("approval_response", None)
                _save_data(self.progress_path, progress)

                logger.info(
                    "Approval response received: approved={} feedback={}",
                    response.approved,
                    response.feedback,
                )
                return response

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning("Approval request timed out after {}s", timeout)

                # Clear pending approval
                progress.pop("approval_pending", None)
                _save_data(self.progress_path, progress)

                # Auto-approve on timeout (configurable)
                return ApprovalResponse(
                    request_id=approval_request.id,
                    approved=True,  # Auto-approve on timeout
                    feedback="Auto-approved due to timeout",
                    responded_at=datetime.now(timezone.utc).isoformat(),
                )

            time.sleep(poll_interval)

    def send_guidance(self, content: str) -> None:
        """Send guidance message to worker.

        Args:
            content: Guidance content.
        """
        msg = Message(
            id=f"guidance-{int(time.time() * 1000)}",
            type="guidance",
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={},
        )
        self.send_to_worker(msg)

    def request_explanation(self, question: str) -> Optional[str]:
        """Request explanation from worker.

        Args:
            question: Question to ask worker.

        Returns:
            Worker's explanation (if received within timeout).
        """
        msg = Message(
            id=f"question-{int(time.time() * 1000)}",
            type="clarification_request",
            content=question,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={"expects_response": True},
        )
        self.send_to_worker(msg)

        # Poll for response
        timeout = 60  # 1 minute
        start_time = time.time()

        while time.time() - start_time < timeout:
            messages = self.receive_from_worker()
            for m in messages:
                if m.type == "clarification_response" and msg.id in m.metadata.get("in_reply_to", ""):
                    return m.content
            time.sleep(1.0)

        logger.warning("No response to clarification request within timeout")
        return None

    def get_pending_approval(self) -> Optional[ApprovalRequest]:
        """Get currently pending approval request if any.

        Returns:
            Pending approval request or None.
        """
        progress = _load_data(self.progress_path, {})
        approval_data = progress.get("approval_pending")

        if approval_data:
            return ApprovalRequest.from_dict(approval_data)
        return None

    def respond_to_approval(self, response: ApprovalResponse) -> None:
        """Respond to a pending approval request.

        Args:
            response: The approval response.
        """
        progress = _load_data(self.progress_path, {})
        progress["approval_response"] = response.to_dict()
        _save_data(self.progress_path, progress)

        logger.info(
            "Approval response submitted: request_id={} approved={}",
            response.request_id,
            response.approved,
        )
