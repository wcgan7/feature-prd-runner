"""Approval gates for human-in-the-loop control.

This module provides approval gates that pause execution and wait for
human approval before proceeding. Gates can be configured at various
points in the workflow.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .messaging import ApprovalRequest, ApprovalResponse, MessageBus
from .notifications import NotificationManager


class GateType(str, Enum):
    """Types of approval gates."""

    BEFORE_PLAN_IMPL = "before_plan_impl"
    BEFORE_IMPLEMENT = "before_implement"
    AFTER_IMPLEMENT = "after_implement"
    BEFORE_VERIFY = "before_verify"
    AFTER_VERIFY = "after_verify"
    BEFORE_REVIEW = "before_review"
    AFTER_REVIEW_ISSUES = "after_review_issues"
    BEFORE_COMMIT = "before_commit"


@dataclass
class GateConfig:
    """Configuration for an approval gate."""

    enabled: bool = False
    message: Optional[str] = None
    show_diff: bool = False
    show_plan: bool = False
    show_tests: bool = False
    show_review: bool = False
    timeout: int = 300  # 5 minutes default
    required: bool = False  # If True, cannot skip/timeout
    allow_edit: bool = False


class ApprovalGateManager:
    """Manage approval gates in the workflow."""

    def __init__(
        self,
        config: dict[str, Any],
        notification_manager: Optional[NotificationManager] = None,
    ):
        """Initialize approval gate manager.

        Args:
            config: Configuration dict with gate settings.
            notification_manager: Optional notification manager for desktop notifications.
        """
        self.config = config
        self.console = Console()
        self.notification_manager = notification_manager

    def is_gate_enabled(self, gate_type: GateType) -> bool:
        """Check if a gate is enabled.

        Args:
            gate_type: Type of gate to check.

        Returns:
            True if gate is enabled.
        """
        gates_config = self.config.get("approval_gates", {})
        if not gates_config.get("enabled", False):
            return False

        gate_config = gates_config.get("gates", {}).get(gate_type.value, {})
        return gate_config.get("enabled", False)

    def get_gate_config(self, gate_type: GateType) -> GateConfig:
        """Get configuration for a gate.

        Args:
            gate_type: Type of gate.

        Returns:
            GateConfig for this gate.
        """
        gates_config = self.config.get("approval_gates", {})
        gate_dict = gates_config.get("gates", {}).get(gate_type.value, {})

        return GateConfig(
            enabled=gate_dict.get("enabled", False),
            message=gate_dict.get("message"),
            show_diff=gate_dict.get("show_diff", False),
            show_plan=gate_dict.get("show_plan", False),
            show_tests=gate_dict.get("show_tests", False),
            show_review=gate_dict.get("show_review", False),
            timeout=gate_dict.get("timeout", 300),
            required=gate_dict.get("required", False),
            allow_edit=gate_dict.get("allow_edit", False),
        )

    def request_approval(
        self,
        gate_type: GateType,
        progress_path: Path,
        context: dict[str, Any],
    ) -> ApprovalResponse:
        """Request approval at a gate.

        Args:
            gate_type: Type of gate.
            progress_path: Path to progress.json for message bus.
            context: Context information to display.

        Returns:
            ApprovalResponse with human's decision.
        """
        gate_config = self.get_gate_config(gate_type)

        if not gate_config.enabled:
            # Gate not enabled, auto-approve
            return ApprovalResponse(
                request_id="auto",
                approved=True,
                feedback="Gate not enabled",
                responded_at=datetime.now(timezone.utc).isoformat(),
            )

        # Display approval prompt to user
        self._display_approval_prompt(gate_type, gate_config, context)

        # Send desktop notification if available
        if self.notification_manager:
            self.notification_manager.notify_approval_required(
                gate_type=gate_type.value,
                message=gate_config.message or f"Approve {gate_type.value}?",
                task_id=context.get("task_id"),
            )

        # Create approval request
        request_id = str(uuid.uuid4())
        request = ApprovalRequest(
            id=request_id,
            gate_type=gate_type.value,
            message=gate_config.message or f"Approve {gate_type.value}?",
            context=context,
            timeout=None if gate_config.required else gate_config.timeout,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Use message bus to request approval
        bus = MessageBus(progress_path)
        response = bus.request_approval(request)

        # Send timeout notification if needed
        if response.approved and response.feedback == "Auto-approved due to timeout":
            if self.notification_manager:
                self.notification_manager.notify_approval_timeout(
                    gate_type=gate_type.value,
                    task_id=context.get("task_id"),
                )

        if response.approved:
            self.console.print("[green]✓ Approved - Continuing...[/green]")
        else:
            self.console.print(f"[red]✗ Rejected - {response.feedback or 'No reason given'}[/red]")

        return response

    def _display_approval_prompt(
        self,
        gate_type: GateType,
        config: GateConfig,
        context: dict[str, Any],
    ) -> None:
        """Display approval prompt to user.

        Args:
            gate_type: Type of gate.
            config: Gate configuration.
            context: Context information.
        """
        self.console.print()
        self.console.print("=" * 70)
        self.console.print(f"[bold yellow]APPROVAL REQUIRED: {gate_type.value}[/bold yellow]")
        self.console.print("=" * 70)

        # Display message
        message = config.message or f"Approve {gate_type.value}?"
        self.console.print(f"\n{message}\n")

        # Display context information
        if context:
            self._display_context(config, context)

        # Display instructions
        self.console.print("\n[bold]Waiting for approval...[/bold]")
        self.console.print(
            "Use 'feature-prd-runner approve' or 'feature-prd-runner reject' to respond"
        )

        if config.timeout and not config.required:
            self.console.print(f"[dim]Auto-approve in {config.timeout}s if no response[/dim]")
        elif config.required:
            self.console.print("[dim]Required - cannot skip or timeout[/dim]")

        self.console.print()

    def _display_context(self, config: GateConfig, context: dict[str, Any]) -> None:
        """Display context information.

        Args:
            config: Gate configuration.
            context: Context to display.
        """
        # Display task info
        if "task_id" in context:
            table = Table(show_header=False, box=None)
            table.add_row("Task:", context.get("task_id", "N/A"))
            table.add_row("Phase:", context.get("phase_id", "N/A"))
            table.add_row("Step:", context.get("step", "N/A"))
            self.console.print(table)
            self.console.print()

        # Display plan if requested
        if config.show_plan and "plan" in context:
            plan = context["plan"]
            self.console.print(Panel("[bold]Implementation Plan[/bold]"))
            if isinstance(plan, dict):
                files = plan.get("files_to_change", [])
                new_files = plan.get("new_files", [])
                if files or new_files:
                    self.console.print(f"Files to change: {len(files)}")
                    self.console.print(f"New files: {len(new_files)}")
                    self.console.print(f"\nSample files: {(files + new_files)[:5]}")
            self.console.print()

        # Display diff if requested
        if config.show_diff and "diff" in context:
            diff_text = context["diff"]
            if diff_text:
                self.console.print(Panel("[bold]Changes[/bold]"))
                syntax = Syntax(diff_text[:2000], "diff", theme="monokai")
                self.console.print(syntax)
                if len(diff_text) > 2000:
                    self.console.print("[dim]... (truncated)[/dim]")
            self.console.print()

        # Display test results if requested
        if config.show_tests and "test_result" in context:
            test_result = context["test_result"]
            self.console.print(Panel("[bold]Test Results[/bold]"))
            if isinstance(test_result, dict):
                passed = test_result.get("passed", False)
                exit_code = test_result.get("exit_code", 1)
                status = "[green]PASSED[/green]" if passed else "[red]FAILED[/red]"
                self.console.print(f"Status: {status}")
                self.console.print(f"Exit code: {exit_code}")
            self.console.print()

        # Display review if requested
        if config.show_review and "review" in context:
            review = context["review"]
            self.console.print(Panel("[bold]Review Results[/bold]"))
            if isinstance(review, dict):
                issues = review.get("issues", [])
                mergeable = review.get("mergeable", False)
                status = "[green]MERGEABLE[/green]" if mergeable else "[red]HAS ISSUES[/red]"
                self.console.print(f"Status: {status}")
                self.console.print(f"Issues found: {len(issues)}")

                if issues:
                    self.console.print("\nTop issues:")
                    for i, issue in enumerate(issues[:3], 1):
                        severity = issue.get("severity", "unknown")
                        summary = issue.get("summary", "No summary")
                        self.console.print(f"  {i}. [{severity.upper()}] {summary}")
            self.console.print()

        # Display files if present
        if "files_changed" in context:
            files = context["files_changed"]
            if files:
                self.console.print(f"[bold]Files changed:[/bold] {len(files)}")
                for f in files[:10]:
                    self.console.print(f"  • {f}")
                if len(files) > 10:
                    self.console.print(f"  ... and {len(files) - 10} more")
                self.console.print()


def create_default_gates_config() -> dict[str, Any]:
    """Create default approval gates configuration.

    Returns:
        Default configuration dict.
    """
    return {
        "approval_gates": {
            "enabled": False,  # Disabled by default
            "gates": {
                "before_implement": {
                    "enabled": False,
                    "message": "Review implementation plan before proceeding?",
                    "show_plan": True,
                    "timeout": 300,
                },
                "after_implement": {
                    "enabled": False,
                    "message": "Review code changes before verification?",
                    "show_diff": True,
                    "allow_edit": True,
                    "timeout": 300,
                },
                "before_commit": {
                    "enabled": False,
                    "message": "Review and approve commit?",
                    "show_diff": True,
                    "show_tests": True,
                    "show_review": True,
                    "required": True,  # Cannot skip
                },
                "after_review_issues": {
                    "enabled": False,
                    "message": "Review found issues. Continue fixing?",
                    "show_review": True,
                    "allow_edit": True,
                    "timeout": 300,
                },
            },
        },
    }
