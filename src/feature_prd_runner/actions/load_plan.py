"""Load an implementation plan JSON file for a phase."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..io_utils import _load_data


def load_plan(impl_plan_path: Path) -> dict[str, Any]:
    """Load a phase implementation plan from disk.

    Args:
        impl_plan_path: Path to the implementation plan JSON file.

    Returns:
        The parsed implementation plan as a dictionary.
    """
    return _load_data(impl_plan_path, {})
