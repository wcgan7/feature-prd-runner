"""Tests for breakpoints module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from feature_prd_runner.breakpoints import Breakpoint, BreakpointManager


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Create a temporary state directory."""
    state_dir = tmp_path / ".prd_runner"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


@pytest.fixture
def breakpoint_manager(temp_state_dir: Path) -> BreakpointManager:
    """Create a breakpoint manager instance."""
    return BreakpointManager(temp_state_dir)


class TestBreakpoint:
    """Test Breakpoint dataclass."""

    def test_create_basic_breakpoint(self):
        """Test creating a basic breakpoint."""
        bp = Breakpoint(
            id="bp-1",
            trigger="before_step",
            target="implement",
        )

        assert bp.id == "bp-1"
        assert bp.trigger == "before_step"
        assert bp.target == "implement"
        assert bp.action == "pause"
        assert bp.enabled is True
        assert bp.hit_count == 0

    def test_create_breakpoint_with_condition(self):
        """Test creating breakpoint with condition."""
        bp = Breakpoint(
            id="bp-2",
            trigger="on_condition",
            target="verify",
            condition="files_changed > 10",
            task_id="task-123",
        )

        assert bp.condition == "files_changed > 10"
        assert bp.task_id == "task-123"

    def test_to_dict(self):
        """Test converting breakpoint to dictionary."""
        bp = Breakpoint(
            id="bp-1",
            trigger="after_step",
            target="test",
            action="notify",
        )

        bp_dict = bp.to_dict()

        assert bp_dict["id"] == "bp-1"
        assert bp_dict["trigger"] == "after_step"
        assert bp_dict["target"] == "test"
        assert bp_dict["action"] == "notify"

    def test_from_dict(self):
        """Test creating breakpoint from dictionary."""
        data = {
            "id": "bp-1",
            "trigger": "on_error",
            "target": "build",
            "condition": "errors > 5",
            "action": "pause",
            "enabled": False,
            "hit_count": 3,
            "created_at": "2024-01-01T00:00:00Z",
        }

        bp = Breakpoint.from_dict(data)

        assert bp.id == "bp-1"
        assert bp.trigger == "on_error"
        assert bp.target == "build"
        assert bp.condition == "errors > 5"
        assert bp.enabled is False
        assert bp.hit_count == 3

    def test_from_dict_minimal(self):
        """Test creating breakpoint from minimal dictionary."""
        data = {
            "id": "bp-1",
            "trigger": "before_step",
            "target": "deploy",
        }

        bp = Breakpoint.from_dict(data)

        assert bp.id == "bp-1"
        assert bp.trigger == "before_step"
        assert bp.target == "deploy"
        assert bp.action == "pause"  # Default
        assert bp.enabled is True  # Default


class TestBreakpointManager:
    """Test BreakpointManager class."""

    def test_init(self, temp_state_dir: Path):
        """Test initialization."""
        manager = BreakpointManager(temp_state_dir)

        assert manager.state_dir == temp_state_dir
        assert manager.breakpoints_path == temp_state_dir / "breakpoints.json"

    def test_add_breakpoint(self, breakpoint_manager: BreakpointManager):
        """Test adding a breakpoint."""
        bp = breakpoint_manager.add_breakpoint(
            trigger="before_step",
            target="implement",
        )

        assert bp.id is not None
        assert bp.trigger == "before_step"
        assert bp.target == "implement"
        assert bp.enabled is True

        # Verify it was saved
        breakpoints = breakpoint_manager.list_breakpoints()
        assert len(breakpoints) == 1
        assert breakpoints[0].id == bp.id

    def test_add_breakpoint_with_condition(self, breakpoint_manager: BreakpointManager):
        """Test adding breakpoint with condition."""
        bp = breakpoint_manager.add_breakpoint(
            trigger="on_condition",
            target="test",
            condition="test_failures > 0",
            action="notify",
        )

        assert bp.condition == "test_failures > 0"
        assert bp.action == "notify"

    def test_add_breakpoint_with_task_id(self, breakpoint_manager: BreakpointManager):
        """Test adding breakpoint for specific task."""
        bp = breakpoint_manager.add_breakpoint(
            trigger="after_step",
            target="verify",
            task_id="task-123",
        )

        assert bp.task_id == "task-123"

    def test_add_multiple_breakpoints(self, breakpoint_manager: BreakpointManager):
        """Test adding multiple breakpoints."""
        bp1 = breakpoint_manager.add_breakpoint("before_step", "step1")
        bp2 = breakpoint_manager.add_breakpoint("after_step", "step2")
        bp3 = breakpoint_manager.add_breakpoint("on_error", "step3")

        breakpoints = breakpoint_manager.list_breakpoints()
        assert len(breakpoints) == 3

        ids = {bp.id for bp in breakpoints}
        assert bp1.id in ids
        assert bp2.id in ids
        assert bp3.id in ids

    def test_remove_breakpoint(self, breakpoint_manager: BreakpointManager):
        """Test removing a breakpoint."""
        bp = breakpoint_manager.add_breakpoint("before_step", "implement")

        result = breakpoint_manager.remove_breakpoint(bp.id)

        assert result is True
        breakpoints = breakpoint_manager.list_breakpoints()
        assert len(breakpoints) == 0

    def test_remove_nonexistent_breakpoint(self, breakpoint_manager: BreakpointManager):
        """Test removing a breakpoint that doesn't exist."""
        result = breakpoint_manager.remove_breakpoint("nonexistent-id")

        assert result is False

    def test_toggle_breakpoint(self, breakpoint_manager: BreakpointManager):
        """Test toggling breakpoint enabled status."""
        bp = breakpoint_manager.add_breakpoint("before_step", "test")
        assert bp.enabled is True

        # Toggle to disabled
        new_status = breakpoint_manager.toggle_breakpoint(bp.id)
        assert new_status is False

        # Verify in list
        breakpoints = breakpoint_manager.list_breakpoints()
        assert breakpoints[0].enabled is False

        # Toggle back to enabled
        new_status = breakpoint_manager.toggle_breakpoint(bp.id)
        assert new_status is True

    def test_toggle_nonexistent_breakpoint(self, breakpoint_manager: BreakpointManager):
        """Test toggling nonexistent breakpoint."""
        result = breakpoint_manager.toggle_breakpoint("nonexistent")

        assert result is None

    def test_list_breakpoints_empty(self, breakpoint_manager: BreakpointManager):
        """Test listing breakpoints when none exist."""
        breakpoints = breakpoint_manager.list_breakpoints()

        assert breakpoints == []

    def test_list_breakpoints(self, breakpoint_manager: BreakpointManager):
        """Test listing breakpoints."""
        breakpoint_manager.add_breakpoint("before_step", "step1")
        breakpoint_manager.add_breakpoint("after_step", "step2")

        breakpoints = breakpoint_manager.list_breakpoints()

        assert len(breakpoints) == 2
        assert all(isinstance(bp, Breakpoint) for bp in breakpoints)

    def test_clear_all(self, breakpoint_manager: BreakpointManager):
        """Test clearing all breakpoints."""
        breakpoint_manager.add_breakpoint("before_step", "step1")
        breakpoint_manager.add_breakpoint("after_step", "step2")
        breakpoint_manager.add_breakpoint("on_error", "step3")

        count = breakpoint_manager.clear_all()

        assert count == 3
        assert len(breakpoint_manager.list_breakpoints()) == 0

    def test_clear_all_empty(self, breakpoint_manager: BreakpointManager):
        """Test clearing when no breakpoints exist."""
        count = breakpoint_manager.clear_all()

        assert count == 0

    def test_check_breakpoint_match(self, breakpoint_manager: BreakpointManager):
        """Test checking for breakpoint match."""
        bp = breakpoint_manager.add_breakpoint("before_step", "implement")

        result = breakpoint_manager.check_breakpoint(
            trigger="before_step",
            target="implement",
        )

        assert result is not None
        assert result.id == bp.id

    def test_check_breakpoint_no_match(self, breakpoint_manager: BreakpointManager):
        """Test checking for breakpoint with no match."""
        breakpoint_manager.add_breakpoint("before_step", "implement")

        result = breakpoint_manager.check_breakpoint(
            trigger="after_step",
            target="implement",
        )

        assert result is None

    def test_check_breakpoint_disabled(self, breakpoint_manager: BreakpointManager):
        """Test that disabled breakpoints don't trigger."""
        bp = breakpoint_manager.add_breakpoint("before_step", "test")
        breakpoint_manager.toggle_breakpoint(bp.id)  # Disable

        result = breakpoint_manager.check_breakpoint(
            trigger="before_step",
            target="test",
        )

        assert result is None

    def test_check_breakpoint_with_task_id_match(self, breakpoint_manager: BreakpointManager):
        """Test breakpoint with task ID matches."""
        bp = breakpoint_manager.add_breakpoint(
            "before_step",
            "implement",
            task_id="task-123",
        )

        result = breakpoint_manager.check_breakpoint(
            trigger="before_step",
            target="implement",
            task_id="task-123",
        )

        assert result is not None
        assert result.id == bp.id

    def test_check_breakpoint_with_task_id_no_match(self, breakpoint_manager: BreakpointManager):
        """Test breakpoint with different task ID doesn't match."""
        breakpoint_manager.add_breakpoint(
            "before_step",
            "implement",
            task_id="task-123",
        )

        result = breakpoint_manager.check_breakpoint(
            trigger="before_step",
            target="implement",
            task_id="task-456",
        )

        assert result is None

    def test_check_breakpoint_increments_hit_count(self, breakpoint_manager: BreakpointManager):
        """Test that checking breakpoint increments hit count."""
        bp = breakpoint_manager.add_breakpoint("before_step", "test")

        breakpoint_manager.check_breakpoint("before_step", "test")
        breakpoint_manager.check_breakpoint("before_step", "test")
        breakpoint_manager.check_breakpoint("before_step", "test")

        breakpoints = breakpoint_manager.list_breakpoints()
        assert breakpoints[0].hit_count == 3

    def test_evaluate_condition_greater_than(self, breakpoint_manager: BreakpointManager):
        """Test evaluating > condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="files_changed > 5",
        )

        # Should match
        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"files_changed": 10},
        )
        assert result is not None

        # Should not match
        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"files_changed": 3},
        )
        assert result is None

    def test_evaluate_condition_less_than(self, breakpoint_manager: BreakpointManager):
        """Test evaluating < condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="errors < 10",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"errors": 5},
        )
        assert result is not None

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"errors": 15},
        )
        assert result is None

    def test_evaluate_condition_equals(self, breakpoint_manager: BreakpointManager):
        """Test evaluating == condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="status == 1",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"status": 1},
        )
        assert result is not None

    def test_evaluate_condition_not_equals(self, breakpoint_manager: BreakpointManager):
        """Test evaluating != condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="result != 0",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"result": 1},
        )
        assert result is not None

    def test_evaluate_condition_greater_equal(self, breakpoint_manager: BreakpointManager):
        """Test evaluating >= condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="count >= 5",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"count": 5},
        )
        assert result is not None

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"count": 10},
        )
        assert result is not None

    def test_evaluate_condition_less_equal(self, breakpoint_manager: BreakpointManager):
        """Test evaluating <= condition."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="max <= 100",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"max": 100},
        )
        assert result is not None

    def test_evaluate_condition_missing_variable(self, breakpoint_manager: BreakpointManager):
        """Test condition with missing variable in context."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="missing_var > 10",
        )

        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"other_var": 20},
        )

        assert result is None

    def test_evaluate_condition_invalid_format(self, breakpoint_manager: BreakpointManager):
        """Test condition with invalid format."""
        breakpoint_manager.add_breakpoint(
            "on_condition",
            "test",
            condition="invalid condition format",
        )

        # Should not raise exception, just return None
        result = breakpoint_manager.check_breakpoint(
            "on_condition",
            "test",
            context={"var": 10},
        )

        assert result is None

    def test_persistence(self, temp_state_dir: Path):
        """Test that breakpoints persist across manager instances."""
        manager1 = BreakpointManager(temp_state_dir)
        bp = manager1.add_breakpoint("before_step", "test")

        # Create new manager instance
        manager2 = BreakpointManager(temp_state_dir)
        breakpoints = manager2.list_breakpoints()

        assert len(breakpoints) == 1
        assert breakpoints[0].id == bp.id
        assert breakpoints[0].trigger == "before_step"
        assert breakpoints[0].target == "test"

    def test_breakpoint_id_is_unique(self, breakpoint_manager: BreakpointManager):
        """Test that breakpoint IDs are unique."""
        bp1 = breakpoint_manager.add_breakpoint("before_step", "test1")
        bp2 = breakpoint_manager.add_breakpoint("before_step", "test2")
        bp3 = breakpoint_manager.add_breakpoint("before_step", "test3")

        assert bp1.id != bp2.id
        assert bp2.id != bp3.id
        assert bp1.id != bp3.id

    def test_breakpoint_has_created_at(self, breakpoint_manager: BreakpointManager):
        """Test that breakpoints have created_at timestamp."""
        bp = breakpoint_manager.add_breakpoint("before_step", "test")

        assert bp.created_at is not None
        # Should be ISO format
        from datetime import datetime
        datetime.fromisoformat(bp.created_at.replace("Z", "+00:00"))
