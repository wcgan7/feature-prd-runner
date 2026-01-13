from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import CONFIG_FILE, STATE_DIR_NAME
from .io_utils import _load_data_with_error


def load_runner_config(project_dir: Path) -> tuple[dict[str, Any], str | None]:
    """
    Load optional runner config from `.prd_runner/config.yaml`.

    Returns (config, error). If missing, returns ({}, None).
    """
    project_dir = project_dir.resolve()
    path = project_dir / STATE_DIR_NAME / CONFIG_FILE
    data, err = _load_data_with_error(path, {})
    if not path.exists():
        return {}, None
    if err:
        return {}, err
    return data, None


def _get_nested(config: dict[str, Any], *keys: str) -> Any:
    cur: Any = config
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def get_verify_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Return verify config block: keys may include format_command, lint_command,
    typecheck_command, test_command, ensure_ruff.
    """
    raw = _get_nested(config, "verify")
    return raw if isinstance(raw, dict) else {}

