"""Test packaging metadata and installation extras."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))


def _load_pyproject() -> dict[str, Any]:
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    raw = pyproject_path.read_text(encoding="utf-8")
    if sys.version_info >= (3, 11):
        import tomllib

        return tomllib.loads(raw)

    import tomli

    return tomli.loads(raw)


def test_pyproject_declares_test_extras() -> None:
    """Ensure `pyproject.toml` declares pytest under `[project.optional-dependencies].test`."""
    data = _load_pyproject()
    test_deps = data.get("project", {}).get("optional-dependencies", {}).get("test", [])
    normalized = {str(item).strip().lower() for item in test_deps}
    assert any(item.startswith("pytest") for item in normalized)
