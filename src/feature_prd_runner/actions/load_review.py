"""Load a structured review JSON file for a phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import _load_data


def load_review(review_path: Path) -> dict[str, Any]:
    """Load a phase review artifact from disk.

    Args:
        review_path: Path to the review JSON file.

    Returns:
        The parsed review payload as a dictionary.
    """
    return _load_data(review_path, {})
