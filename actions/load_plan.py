from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from ..io_utils import _load_data
except ImportError:  # pragma: no cover
    from io_utils import _load_data


def load_plan(impl_plan_path: Path) -> dict[str, Any]:
    return _load_data(impl_plan_path, {})
