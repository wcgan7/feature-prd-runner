"""Validate structured review payloads produced by the worker."""

from __future__ import annotations

from typing import Any, Optional

from ..validation import _validate_review_data, _validate_simple_review_data


def validate_review(
    review_data: dict[str, Any],
    phase: dict[str, Any],
    *,
    changed_files: Optional[list[str]] = None,
    prd_markers: Optional[list[str]] = None,
    prd_truncated: bool = False,
    prd_has_content: bool = True,
    simple_review: bool = False,
) -> tuple[bool, str]:
    """Validate a review output payload for a phase.

    Args:
        review_data: Parsed review payload produced by the worker.
        phase: Phase metadata the review is expected to match.
        changed_files: Optional list of files changed in the phase.
        prd_markers: Optional PRD marker tokens extracted from the PRD text.
        prd_truncated: Whether the PRD text used for validation was truncated.
        prd_has_content: Whether PRD text content was available.
        simple_review: Whether to validate against the simplified review schema.

    Returns:
        A tuple of `(is_valid, error_message)` where `error_message` is empty when valid.
    """
    if simple_review:
        return _validate_simple_review_data(review_data)
    return _validate_review_data(
        review_data,
        phase,
        changed_files=changed_files,
        prd_markers=prd_markers,
        prd_truncated=prd_truncated,
        prd_has_content=prd_has_content,
    )
