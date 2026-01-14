"""Validate implementation plan payloads against the runner's schema rules."""

from __future__ import annotations

from typing import Any, Optional

from ..validation import _validate_impl_plan_data


def validate_plan(
    plan_data: dict[str, Any],
    phase: dict[str, Any],
    *,
    prd_markers: Optional[list[str]] = None,
    prd_truncated: bool = False,
    prd_has_content: bool = True,
    expected_test_command: Optional[str] = None,
    plan_expansion_request: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """Validate an implementation plan for a specific phase.

    Args:
        plan_data: Parsed implementation plan payload.
        phase: Phase metadata the plan is expected to match.
        prd_markers: Optional PRD marker tokens extracted from the PRD text.
        prd_truncated: Whether the PRD text used for validation was truncated.
        prd_has_content: Whether PRD text content was available.
        expected_test_command: Optional expected test command for the phase.
        plan_expansion_request: Optional allowlist expansion request paths to enforce.

    Returns:
        A tuple of `(is_valid, error_message)` where `error_message` is empty when valid.
    """
    return _validate_impl_plan_data(
        plan_data,
        phase,
        prd_markers=prd_markers,
        prd_truncated=prd_truncated,
        prd_has_content=prd_has_content,
        expected_test_command=expected_test_command,
        plan_expansion_request=plan_expansion_request,
    )
