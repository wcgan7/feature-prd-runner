"""Breakpoints for pausing execution at specific points.

This module provides breakpoint functionality to pause execution at key
moments for inspection and human intervention.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from .io_utils import _load_data, _save_data


@dataclass
class Breakpoint:
    """Represents a breakpoint."""

    id: str
    trigger: str  # before_step, after_step, on_error, on_condition
    target: str  # step name, task_id, etc.
    task_id: Optional[str] = None
    condition: Optional[str] = None  # e.g., "files_changed > 10"
    action: str = "pause"  # pause, notify, log
    enabled: bool = True
    hit_count: int = 0
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Breakpoint":
        """Create from dictionary."""
        return cls(
            id=data.get("id", ""),
            trigger=data.get("trigger", ""),
            target=data.get("target", ""),
            task_id=data.get("task_id"),
            condition=data.get("condition"),
            action=data.get("action", "pause"),
            enabled=data.get("enabled", True),
            hit_count=data.get("hit_count", 0),
            created_at=data.get("created_at"),
        )


class BreakpointManager:
    """Manage breakpoints in the workflow."""

    def __init__(self, state_dir: Path):
        """Initialize breakpoint manager.

        Args:
            state_dir: Path to .prd_runner state directory.
        """
        self.state_dir = state_dir
        self.breakpoints_path = state_dir / "breakpoints.json"

    def add_breakpoint(
        self,
        trigger: str,
        target: str,
        task_id: Optional[str] = None,
        condition: Optional[str] = None,
        action: str = "pause",
    ) -> Breakpoint:
        """Add a breakpoint.

        Args:
            trigger: When to trigger (before_step, after_step, on_error, on_condition).
            target: What to target (step name).
            task_id: Optional specific task ID.
            condition: Optional condition expression.
            action: What to do when hit (pause, notify, log).

        Returns:
            Created breakpoint.
        """
        from datetime import datetime, timezone

        bp = Breakpoint(
            id=str(uuid.uuid4())[:8],
            trigger=trigger,
            target=target,
            task_id=task_id,
            condition=condition,
            action=action,
            enabled=True,
            hit_count=0,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        breakpoints = self._load_breakpoints()
        breakpoints.append(bp.to_dict())
        self._save_breakpoints(breakpoints)

        logger.info(
            "Breakpoint created: id={} trigger={} target={}",
            bp.id,
            bp.trigger,
            bp.target,
        )

        return bp

    def remove_breakpoint(self, breakpoint_id: str) -> bool:
        """Remove a breakpoint.

        Args:
            breakpoint_id: Breakpoint ID to remove.

        Returns:
            True if removed, False if not found.
        """
        breakpoints = self._load_breakpoints()
        initial_count = len(breakpoints)

        breakpoints = [bp for bp in breakpoints if bp.get("id") != breakpoint_id]

        if len(breakpoints) < initial_count:
            self._save_breakpoints(breakpoints)
            logger.info("Breakpoint removed: id={}", breakpoint_id)
            return True

        return False

    def toggle_breakpoint(self, breakpoint_id: str) -> Optional[bool]:
        """Toggle breakpoint enabled status.

        Args:
            breakpoint_id: Breakpoint ID to toggle.

        Returns:
            New enabled status, or None if not found.
        """
        breakpoints = self._load_breakpoints()

        for bp in breakpoints:
            if bp.get("id") == breakpoint_id:
                bp["enabled"] = not bp.get("enabled", True)
                self._save_breakpoints(breakpoints)
                logger.info(
                    "Breakpoint {} {}", breakpoint_id, "enabled" if bp["enabled"] else "disabled"
                )
                return bp["enabled"]

        return None

    def list_breakpoints(self) -> list[Breakpoint]:
        """List all breakpoints.

        Returns:
            List of breakpoints.
        """
        breakpoints_data = self._load_breakpoints()
        return [Breakpoint.from_dict(bp) for bp in breakpoints_data]

    def clear_all(self) -> int:
        """Clear all breakpoints.

        Returns:
            Number of breakpoints cleared.
        """
        breakpoints = self._load_breakpoints()
        count = len(breakpoints)
        self._save_breakpoints([])
        logger.info("All breakpoints cleared: count={}", count)
        return count

    def check_breakpoint(
        self,
        trigger: str,
        target: str,
        task_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[Breakpoint]:
        """Check if a breakpoint should trigger.

        Args:
            trigger: Trigger type.
            target: Target name.
            task_id: Optional task ID.
            context: Optional context for condition evaluation.

        Returns:
            Breakpoint that triggered, or None.
        """
        breakpoints = self.list_breakpoints()

        for bp in breakpoints:
            if not bp.enabled:
                continue

            # Check trigger and target match
            if bp.trigger != trigger:
                continue

            if bp.target != target:
                continue

            # Check task_id if specified
            if bp.task_id and bp.task_id != task_id:
                continue

            # Evaluate condition if present
            if bp.condition and context:
                if not self._evaluate_condition(bp.condition, context):
                    continue

            # Breakpoint hit!
            self._increment_hit_count(bp.id)
            logger.info(
                "Breakpoint hit: id={} trigger={} target={}",
                bp.id,
                bp.trigger,
                bp.target,
            )
            return bp

        return None

    def _evaluate_condition(self, condition: str, context: dict[str, Any]) -> bool:
        """Evaluate breakpoint condition.

        Args:
            condition: Condition expression.
            context: Context variables.

        Returns:
            True if condition met.
        """
        try:
            # Simple condition evaluation
            # Support: files_changed > N, errors > N, etc.
            parts = condition.split()
            if len(parts) >= 3:
                var = parts[0]
                op = parts[1]
                val = parts[2]

                if var in context:
                    context_val = context[var]
                    try:
                        val = int(val)
                    except ValueError:
                        pass

                    if op == ">":
                        return context_val > val
                    elif op == "<":
                        return context_val < val
                    elif op == ">=":
                        return context_val >= val
                    elif op == "<=":
                        return context_val <= val
                    elif op == "==":
                        return context_val == val
                    elif op == "!=":
                        return context_val != val

            return False
        except Exception as e:
            logger.warning("Failed to evaluate condition {}: {}", condition, e)
            return False

    def _increment_hit_count(self, breakpoint_id: str) -> None:
        """Increment hit count for a breakpoint.

        Args:
            breakpoint_id: Breakpoint ID.
        """
        breakpoints = self._load_breakpoints()

        for bp in breakpoints:
            if bp.get("id") == breakpoint_id:
                bp["hit_count"] = bp.get("hit_count", 0) + 1
                break

        self._save_breakpoints(breakpoints)

    def _load_breakpoints(self) -> list[dict[str, Any]]:
        """Load breakpoints from file.

        Returns:
            List of breakpoint dicts.
        """
        if not self.breakpoints_path.exists():
            return []

        data = _load_data(self.breakpoints_path, {})
        return data.get("breakpoints", [])

    def _save_breakpoints(self, breakpoints: list[dict[str, Any]]) -> None:
        """Save breakpoints to file.

        Args:
            breakpoints: List of breakpoint dicts.
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)
        _save_data(self.breakpoints_path, {"breakpoints": breakpoints})
