from __future__ import annotations

from typing import Any, Optional

try:
    from ..validation import _validate_review_data
except ImportError:  # pragma: no cover
    from validation import _validate_review_data


def validate_review(
    review_data: dict[str, Any],
    phase: dict[str, Any],
    *,
    changed_files: Optional[list[str]] = None,
    prd_markers: Optional[list[str]] = None,
    prd_truncated: bool = False,
    prd_has_content: bool = True,
) -> tuple[bool, str]:
    return _validate_review_data(
        review_data,
        phase,
        changed_files=changed_files,
        prd_markers=prd_markers,
        prd_truncated=prd_truncated,
        prd_has_content=prd_has_content,
    )
