"""Tests for messaging module."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from feature_prd_runner.messaging import (
    ApprovalRequest,
    ApprovalResponse,
    Message,
    MessageBus,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def progress_path(temp_dir: Path) -> Path:
    """Create a progress.json path."""
    progress_path = temp_dir / "progress.json"
    # Initialize with empty progress
    progress_path.write_text(json.dumps({}))
    return progress_path


@pytest.fixture
def message_bus(progress_path: Path) -> MessageBus:
    """Create a MessageBus instance."""
    return MessageBus(progress_path)


class TestMessage:
    """Test Message dataclass."""

    def test_create_message(self):
        """Test creating a message."""
        msg = Message(
            id="msg-1",
            type="guidance",
            content="Test message",
            timestamp="2024-01-01T00:00:00Z",
            metadata={"key": "value"},
        )

        assert msg.id == "msg-1"
        assert msg.type == "guidance"
        assert msg.content == "Test message"
        assert msg.metadata == {"key": "value"}

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        msg = Message(
            id="msg-1",
            type="clarification_request",
            content="What should I do?",
            timestamp="2024-01-01T00:00:00Z",
            metadata={},
        )

        msg_dict = msg.to_dict()

        assert msg_dict["id"] == "msg-1"
        assert msg_dict["type"] == "clarification_request"
        assert msg_dict["content"] == "What should I do?"

    def test_message_from_dict(self):
        """Test creating message from dictionary."""
        data = {
            "id": "msg-2",
            "type": "guidance",
            "content": "Focus on tests",
            "timestamp": "2024-01-01T12:00:00Z",
            "metadata": {"priority": "high"},
        }

        msg = Message.from_dict(data)

        assert msg.id == "msg-2"
        assert msg.type == "guidance"
        assert msg.content == "Focus on tests"
        assert msg.metadata["priority"] == "high"


class TestApprovalRequest:
    """Test ApprovalRequest dataclass."""

    def test_create_approval_request(self):
        """Test creating an approval request."""
        req = ApprovalRequest(
            id="req-1",
            gate_type="before_implement",
            message="Review plan?",
            context={"task_id": "task-1"},
            timeout=300,
            created_at="2024-01-01T00:00:00Z",
        )

        assert req.id == "req-1"
        assert req.gate_type == "before_implement"
        assert req.message == "Review plan?"
        assert req.timeout == 300

    def test_approval_request_to_dict(self):
        """Test converting approval request to dictionary."""
        req = ApprovalRequest(
            id="req-1",
            gate_type="after_implement",
            message="Review changes?",
            context={},
        )

        req_dict = req.to_dict()

        assert req_dict["id"] == "req-1"
        assert req_dict["gate_type"] == "after_implement"
        assert req_dict["message"] == "Review changes?"

    def test_approval_request_from_dict(self):
        """Test creating approval request from dictionary."""
        data = {
            "id": "req-2",
            "gate_type": "before_commit",
            "message": "Approve commit?",
            "context": {"files": ["file1.py"]},
            "timeout": 600,
        }

        req = ApprovalRequest.from_dict(data)

        assert req.id == "req-2"
        assert req.gate_type == "before_commit"
        assert req.timeout == 600


class TestApprovalResponse:
    """Test ApprovalResponse dataclass."""

    def test_create_approval_response(self):
        """Test creating an approval response."""
        resp = ApprovalResponse(
            request_id="req-1",
            approved=True,
            feedback="Looks good",
            responded_at="2024-01-01T00:05:00Z",
        )

        assert resp.request_id == "req-1"
        assert resp.approved is True
        assert resp.feedback == "Looks good"

    def test_approval_response_rejected(self):
        """Test creating a rejected approval response."""
        resp = ApprovalResponse(
            request_id="req-1",
            approved=False,
            feedback="Needs more work",
        )

        assert resp.approved is False
        assert resp.feedback == "Needs more work"

    def test_approval_response_to_dict(self):
        """Test converting approval response to dictionary."""
        resp = ApprovalResponse(
            request_id="req-1",
            approved=True,
        )

        resp_dict = resp.to_dict()

        assert resp_dict["request_id"] == "req-1"
        assert resp_dict["approved"] is True

    def test_approval_response_from_dict(self):
        """Test creating approval response from dictionary."""
        data = {
            "request_id": "req-1",
            "approved": True,
            "feedback": "Approved with modifications",
            "modifications": {"add_tests": True},
        }

        resp = ApprovalResponse.from_dict(data)

        assert resp.approved is True
        assert resp.feedback == "Approved with modifications"
        assert resp.modifications == {"add_tests": True}


class TestMessageBus:
    """Test MessageBus class."""

    def test_init(self, progress_path: Path):
        """Test MessageBus initialization."""
        bus = MessageBus(progress_path)

        assert bus.progress_path == progress_path
        assert progress_path.exists()

    def test_init_creates_directory(self, temp_dir: Path):
        """Test that MessageBus creates parent directory if needed."""
        progress_path = temp_dir / "subdir" / "progress.json"
        bus = MessageBus(progress_path)

        assert progress_path.parent.exists()

    def test_send_to_worker(self, message_bus: MessageBus, progress_path: Path):
        """Test sending a message to the worker."""
        msg = Message(
            id="msg-1",
            type="guidance",
            content="Focus on error handling",
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={},
        )

        message_bus.send_to_worker(msg)

        # Verify message was saved to progress.json
        progress = json.loads(progress_path.read_text())
        assert "messages_from_human" in progress
        assert len(progress["messages_from_human"]) == 1
        assert progress["messages_from_human"][0]["id"] == "msg-1"
        assert progress["messages_from_human"][0]["content"] == "Focus on error handling"

    def test_send_multiple_messages(self, message_bus: MessageBus, progress_path: Path):
        """Test sending multiple messages."""
        msg1 = Message("msg-1", "guidance", "Message 1", "2024-01-01T00:00:00Z", {})
        msg2 = Message("msg-2", "guidance", "Message 2", "2024-01-01T00:01:00Z", {})

        message_bus.send_to_worker(msg1)
        message_bus.send_to_worker(msg2)

        progress = json.loads(progress_path.read_text())
        assert len(progress["messages_from_human"]) == 2

    def test_receive_from_worker_empty(self, message_bus: MessageBus):
        """Test receiving messages when none exist."""
        messages = message_bus.receive_from_worker()

        assert messages == []

    def test_receive_from_worker(self, message_bus: MessageBus, progress_path: Path):
        """Test receiving messages from worker."""
        # Manually add messages to progress
        progress = {
            "messages_to_human": [
                {
                    "id": "msg-1",
                    "type": "clarification_request",
                    "content": "Need help",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "metadata": {},
                },
                {
                    "id": "msg-2",
                    "type": "status_update",
                    "content": "Working on task",
                    "timestamp": "2024-01-01T00:01:00Z",
                    "metadata": {},
                },
            ],
        }
        progress_path.write_text(json.dumps(progress))

        messages = message_bus.receive_from_worker()

        assert len(messages) == 2
        assert messages[0].id == "msg-1"
        assert messages[0].content == "Need help"
        assert messages[1].id == "msg-2"

    def test_receive_clears_messages(self, message_bus: MessageBus, progress_path: Path):
        """Test that receiving messages clears them from progress."""
        progress = {
            "messages_to_human": [
                {
                    "id": "msg-1",
                    "type": "status",
                    "content": "Test",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "metadata": {},
                },
            ],
        }
        progress_path.write_text(json.dumps(progress))

        message_bus.receive_from_worker()

        # Messages should be cleared
        progress_after = json.loads(progress_path.read_text())
        assert progress_after["messages_to_human"] == []

    @patch("time.sleep")
    def test_request_approval_immediate_response(
        self,
        mock_sleep: Any,
        message_bus: MessageBus,
        progress_path: Path,
    ):
        """Test requesting approval with immediate response."""
        req = ApprovalRequest(
            id="req-1",
            gate_type="before_implement",
            message="Review?",
            context={},
            timeout=60,
        )

        # Simulate response being written
        def write_response(*args):
            progress = json.loads(progress_path.read_text())
            progress["approval_response"] = {
                "request_id": "req-1",
                "approved": True,
                "feedback": "Approved",
                "responded_at": datetime.now(timezone.utc).isoformat(),
            }
            progress_path.write_text(json.dumps(progress))

        mock_sleep.side_effect = write_response

        response = message_bus.request_approval(req, poll_interval=0.1)

        assert response.approved is True
        assert response.feedback == "Approved"

    @patch("time.time")
    @patch("time.sleep")
    def test_request_approval_timeout(
        self,
        mock_sleep: Any,
        mock_time: Any,
        message_bus: MessageBus,
    ):
        """Test approval request timeout."""
        # Simulate time passing
        mock_time.side_effect = [0, 0, 70]  # Start, loop, timeout check

        req = ApprovalRequest(
            id="req-1",
            gate_type="before_implement",
            message="Review?",
            context={},
            timeout=60,
        )

        response = message_bus.request_approval(req, poll_interval=0.1)

        assert response.approved is True  # Auto-approved on timeout
        assert "timeout" in response.feedback.lower()

    def test_send_guidance(self, message_bus: MessageBus, progress_path: Path):
        """Test sending guidance message."""
        message_bus.send_guidance("Focus on security")

        progress = json.loads(progress_path.read_text())
        messages = progress["messages_from_human"]

        assert len(messages) == 1
        assert messages[0]["type"] == "guidance"
        assert messages[0]["content"] == "Focus on security"

    @patch("time.sleep")
    def test_request_explanation_receives_response(
        self,
        mock_sleep: Any,
        message_bus: MessageBus,
        progress_path: Path,
    ):
        """Test requesting and receiving explanation."""
        question_id = None

        def simulate_response(*args):
            nonlocal question_id
            # Get the question ID from progress
            progress = json.loads(progress_path.read_text())
            messages = progress.get("messages_from_human", [])
            if messages:
                question_id = messages[-1]["id"]
                # Write response
                progress["messages_to_human"] = [
                    {
                        "id": "resp-1",
                        "type": "clarification_response",
                        "content": "Here's the explanation",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metadata": {"in_reply_to": question_id},
                    },
                ]
                progress_path.write_text(json.dumps(progress))

        mock_sleep.side_effect = simulate_response

        explanation = message_bus.request_explanation("Why did this fail?")

        assert explanation == "Here's the explanation"

    @patch("time.time")
    @patch("time.sleep")
    def test_request_explanation_timeout(
        self,
        mock_sleep: Any,
        mock_time: Any,
        message_bus: MessageBus,
    ):
        """Test explanation request timeout."""
        # Simulate time passing beyond timeout
        mock_time.side_effect = [0, 0, 70]

        explanation = message_bus.request_explanation("Why?")

        assert explanation is None

    def test_get_pending_approval_exists(self, message_bus: MessageBus, progress_path: Path):
        """Test getting pending approval request."""
        approval_data = {
            "id": "req-1",
            "gate_type": "before_commit",
            "message": "Approve?",
            "context": {},
            "timeout": 300,
        }

        progress = {"approval_pending": approval_data}
        progress_path.write_text(json.dumps(progress))

        pending = message_bus.get_pending_approval()

        assert pending is not None
        assert pending.id == "req-1"
        assert pending.gate_type == "before_commit"

    def test_get_pending_approval_none(self, message_bus: MessageBus):
        """Test getting pending approval when none exists."""
        pending = message_bus.get_pending_approval()

        assert pending is None

    def test_respond_to_approval(self, message_bus: MessageBus, progress_path: Path):
        """Test responding to an approval request."""
        response = ApprovalResponse(
            request_id="req-1",
            approved=True,
            feedback="Looks good",
            responded_at=datetime.now(timezone.utc).isoformat(),
        )

        message_bus.respond_to_approval(response)

        progress = json.loads(progress_path.read_text())
        assert "approval_response" in progress
        assert progress["approval_response"]["request_id"] == "req-1"
        assert progress["approval_response"]["approved"] is True

    def test_message_bus_preserves_existing_data(
        self,
        message_bus: MessageBus,
        progress_path: Path,
    ):
        """Test that MessageBus preserves other data in progress.json."""
        # Add some existing data
        existing_data = {
            "task_id": "task-1",
            "status": "running",
            "other_field": "value",
        }
        progress_path.write_text(json.dumps(existing_data))

        # Send a message
        msg = Message("msg-1", "guidance", "Test", "2024-01-01T00:00:00Z", {})
        message_bus.send_to_worker(msg)

        # Verify existing data is preserved
        progress = json.loads(progress_path.read_text())
        assert progress["task_id"] == "task-1"
        assert progress["status"] == "running"
        assert progress["other_field"] == "value"
        assert "messages_from_human" in progress

    def test_concurrent_message_types(self, message_bus: MessageBus, progress_path: Path):
        """Test that different message types coexist properly."""
        # Send guidance
        message_bus.send_guidance("Test guidance")

        # Add worker messages
        progress = json.loads(progress_path.read_text())
        progress["messages_to_human"] = [
            {
                "id": "worker-msg",
                "type": "status",
                "content": "Working",
                "timestamp": "2024-01-01T00:00:00Z",
                "metadata": {},
            },
        ]
        progress_path.write_text(json.dumps(progress))

        # Receive worker messages
        worker_messages = message_bus.receive_from_worker()

        # Send another human message
        message_bus.send_guidance("More guidance")

        progress = json.loads(progress_path.read_text())
        assert len(progress["messages_from_human"]) == 2
        assert len(worker_messages) == 1

    def test_approval_request_clears_after_response(
        self,
        message_bus: MessageBus,
        progress_path: Path,
    ):
        """Test that approval request and response are cleared after completion."""
        # Set up a pending approval with immediate response
        progress = {
            "approval_pending": {
                "id": "req-1",
                "gate_type": "before_implement",
                "message": "Approve?",
                "context": {},
                "timeout": 60,
            },
            "approval_response": {
                "request_id": "req-1",
                "approved": True,
                "responded_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        progress_path.write_text(json.dumps(progress))

        req = ApprovalRequest("req-1", "before_implement", "Approve?", {}, 60)

        with patch("time.sleep"):
            response = message_bus.request_approval(req, poll_interval=0.1)

        # Verify approval state is cleared
        progress_after = json.loads(progress_path.read_text())
        assert "approval_pending" not in progress_after
        assert "approval_response" not in progress_after
