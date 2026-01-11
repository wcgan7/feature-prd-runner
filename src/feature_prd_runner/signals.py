from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .git_utils import _path_is_allowed


_PATH_TOKEN_RE = re.compile(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)")


def build_allowed_files(plan_data: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("files_to_change", "new_files"):
        value = plan_data.get(key)
        if isinstance(value, list):
            for item in value:
                path = str(item).strip()
                if path:
                    files.append(path)
    if "README.md" not in files:
        files.append("README.md")
    return files


def extract_paths_from_log(log_text: str, project_dir: Path) -> list[str]:
    if not log_text:
        return []

    candidates = _PATH_TOKEN_RE.findall(log_text)
    seen: set[str] = set()
    paths: list[str] = []
    project_dir = project_dir.resolve()

    for token in candidates:
        cleaned = token.strip().strip("\"'<>[](){};,:")
        if "::" in cleaned:
            cleaned = cleaned.split("::", 1)[0]
        cleaned = cleaned.replace("\\", "/")
        if not cleaned:
            continue

        path_value = cleaned
        if os.path.isabs(path_value):
            try:
                rel = Path(path_value).resolve().relative_to(project_dir)
            except ValueError:
                continue
            path_value = str(rel)
        else:
            path_value = path_value.lstrip("./")

        if not path_value:
            continue
        if path_value in seen:
            continue
        candidate_path = project_dir / path_value
        if not candidate_path.exists():
            continue
        seen.add(path_value)
        paths.append(path_value)

    return paths


def needs_allowlist_expansion(
    failing_paths: list[str],
    allowed_files: list[str],
    project_dir: Path,
) -> bool:
    if not failing_paths or not allowed_files:
        return False
    for path in failing_paths:
        if not _path_is_allowed(project_dir, path, allowed_files):
            return True
    return False


def filter_repo_file_paths(paths: list[str], project_dir: Path) -> list[str]:
    root = project_dir.resolve()
    out: set[str] = set()

    for raw in paths:
        s = str(raw).strip()
        if not s:
            continue

        # Handle absolute paths
        p = Path(s)
        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(root)
            except Exception:
                continue
            candidate = root / rel
        else:
            # Treat as repo-relative candidate
            candidate = (root / p).resolve()
            try:
                candidate.relative_to(root)
            except Exception:
                continue

        # Only keep actual files under repo root
        if candidate.is_file():
            out.add(candidate.relative_to(root).as_posix())

    return sorted(out)


_FAILED_LINE_RE = re.compile(r"^FAILED\s+([^\s:]+\.py)(?:::|\s|$)")

def extract_failing_paths_from_pytest_log(log_text: str, project_dir: Path) -> list[str]:
    if not log_text:
        return []
    root = project_dir.resolve()
    out: set[str] = set()

    for line in log_text.splitlines():
        m = _FAILED_LINE_RE.match(line.strip())
        if not m:
            continue
        p = m.group(1).strip().lstrip("./")
        candidate = (root / p).resolve()
        try:
            candidate.relative_to(root)
        except Exception:
            continue
        if candidate.is_file():
            out.add(candidate.relative_to(root).as_posix())

    return sorted(out)