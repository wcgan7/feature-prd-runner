"""Extract file path signals from logs to support allowlist expansion decisions."""

from __future__ import annotations

import ast
import importlib.util
import os
import re
from pathlib import Path
from typing import Any

from .git_utils import _path_is_allowed


_PATH_TOKEN_RE = re.compile(r"([A-Za-z0-9_./\\-]+\.[A-Za-z0-9_]+)")


def build_allowed_files(plan_data: dict[str, Any]) -> list[str]:
    """Build the allowlist of files the worker may change for a phase.

    Args:
        plan_data: Implementation plan payload containing `files_to_change` and `new_files`.

    Returns:
        A list of repo-relative file path patterns allowed for the phase.
    """
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
    """Extract existing repo file paths referenced in a log text.

    Args:
        log_text: Raw log output text.
        project_dir: Repository root directory.

    Returns:
        A list of unique repo-relative paths that exist on disk.
    """
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
    """Decide whether a failure indicates the allowlist should be expanded.

    Args:
        failing_paths: Repo-relative paths implicated by the failure.
        allowed_files: Current allowlist patterns from the implementation plan.
        project_dir: Repository root directory.

    Returns:
        True if any failing path is outside the allowlist; otherwise False.
    """
    if not failing_paths or not allowed_files:
        return False
    for path in failing_paths:
        if not _path_is_allowed(project_dir, path, allowed_files):
            return True
    return False


def filter_repo_file_paths(paths: list[str], project_dir: Path) -> list[str]:
    """Filter a list of strings down to repo-relative file paths.

    Args:
        paths: Candidate path strings (absolute or repo-relative).
        project_dir: Repository root directory.

    Returns:
        Sorted repo-relative paths that exist and are files under `project_dir`.
    """
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


# Robust pytest failure markers
_FAILED_NODEID_RE = re.compile(r"(?m)^FAILED\s+(\S+)")
_LOC_RE = re.compile(r"(?m)^(tests/[^\s:]+\.py):\d+:\s")


def extract_failed_test_files(text: str, project_dir: Path) -> list[str]:
    """Extract failing test file paths from pytest output.

    Parses:
    - `FAILED` nodeids like `FAILED tests/foo/test_bar.py::test_func`
    - Location lines like `tests/foo.py:123: AssertionError`
    """
    root = project_dir.resolve()
    out: set[str] = set()

    # 1) From FAILED nodeids
    for nodeid in _FAILED_NODEID_RE.findall(text or ""):
        path = nodeid.split("::", 1)[0].lstrip("./")
        p = (root / path).resolve()
        try:
            p.relative_to(root)
        except Exception:
            continue
        if p.is_file():
            out.add(p.relative_to(root).as_posix())

    # 2) From location lines like tests/foo.py:123:
    for path in _LOC_RE.findall(text or ""):
        p = (root / path).resolve()
        try:
            p.relative_to(root)
        except Exception:
            continue
        if p.is_file():
            out.add(p.relative_to(root).as_posix())

    return sorted(out)


# Keep old name as alias for backwards compatibility
def extract_failing_paths_from_pytest_log(log_text: str, project_dir: Path) -> list[str]:
    """Alias for extract_failed_test_files for backwards compatibility."""
    return extract_failed_test_files(log_text, project_dir)

# pytest frame: src/foo.py:123: in func
_PYTEST_FRAME_RE = re.compile(r"(?m)^(?P<path>(?:src|tests)/[^\s:]+\.py):\d+:")

# python traceback frame: File "src/foo.py", line 123, in func
_TB_FILE_RE = re.compile(r'(?m)^File "(?P<path>(?:src|tests)/[^"]+\.py)", line \d+,')


def extract_failures_section(full: str, max_chars: int = 60000) -> str:
    """Extract the FAILURES section from pytest output, or return last chunk as fallback."""
    if not full:
        return ""
    marker = "FAILURES"
    idx = full.find(marker)
    if idx == -1:
        # fallback: last chunk
        return full[-max_chars:]
    return full[idx: idx + max_chars]


def extract_traceback_repo_paths(log_text: str, project_dir: Path) -> list[str]:
    """Extract repo file paths from both pytest frames and Python traceback frames."""
    if not log_text:
        return []
    root = project_dir.resolve()
    out: set[str] = set()

    for rx in (_PYTEST_FRAME_RE, _TB_FILE_RE):
        for m in rx.finditer(log_text):
            rel = m.group("path").strip().lstrip("./")
            p = (root / rel).resolve()
            try:
                p.relative_to(root)
            except Exception:
                continue
            if p.is_file():
                out.add(p.relative_to(root).as_posix())

    return sorted(out)


# Support Windows drive prefixes like `C:\...` by allowing an optional `X:` prefix.
_RUFF_PATH_RE = re.compile(r"(?m)^(?P<path>(?:[A-Za-z]:)?[^:\n]+):\d+:\d+:")
_RUFF_PATH2_RE = re.compile(r"(?m)^(?P<path>(?:[A-Za-z]:)?[^:\n]+):\d+:")
_MYPY_PATH_RE = re.compile(r"(?m)^(?P<path>(?:[A-Za-z]:)?[^:\n]+):\d+:")


def extract_ruff_repo_paths(text: str, project_dir: Path) -> list[str]:
    """Extract repo file paths from ruff output.

    Examples:
    - `path/to/file.py:12:3: F401 ...`
    - `path/to/file.py:12: error ...`
    """
    root = project_dir.resolve()
    out: set[str] = set()
    for rx in (_RUFF_PATH_RE, _RUFF_PATH2_RE):
        for m in rx.finditer(text or ""):
            rel = m.group("path").strip().replace("\\", "/").lstrip("./")
            if not rel:
                continue
            p = (root / rel).resolve()
            try:
                p.relative_to(root)
            except Exception:
                continue
            if p.is_file():
                out.add(p.relative_to(root).as_posix())
    return sorted(out)


def extract_mypy_repo_paths(text: str, project_dir: Path) -> list[str]:
    """Extract repo file paths from mypy output.

    Example: `path/to/file.py:12: error: ...`
    """
    root = project_dir.resolve()
    out: set[str] = set()
    for m in _MYPY_PATH_RE.finditer(text or ""):
        rel = m.group("path").strip().replace("\\", "/").lstrip("./")
        if not rel:
            continue
        p = (root / rel).resolve()
        try:
            p.relative_to(root)
        except Exception:
            continue
        if p.is_file():
            out.add(p.relative_to(root).as_posix())
    return sorted(out)


# Pattern to find monkeypatch.setattr targets
_MONKEYPATCH_RE = re.compile(r"monkeypatch\.setattr\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*,")


def resolve_test_import_aliases_to_paths(test_file: str, project_dir: Path) -> dict[str, str]:
    """Resolve import aliases in a test file to repo-relative file paths.

    Returns a mapping of `alias_name -> repo-relative python file path` (when resolvable). This is used to
    infer likely source files when failures don't include full tracebacks.
    """
    root = project_dir.resolve()
    test_path = (root / test_file).resolve()
    if not test_path.is_file():
        return {}

    try:
        tree = ast.parse(test_path.read_text(errors="replace"))
    except SyntaxError:
        return {}

    alias_to_module: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                name = a.name  # e.g. company_intel.genesis.orchestrator
                asname = a.asname or name.split(".")[-1]
                alias_to_module[asname] = name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                # from company_intel.genesis import orchestrator as orchestrator_module
                name = f"{mod}.{a.name}" if mod else a.name
                asname = a.asname or a.name
                alias_to_module[asname] = name

    # Resolve modules to file paths (only if they are inside repo root)
    out: dict[str, str] = {}
    for alias, module in alias_to_module.items():
        try:
            spec = importlib.util.find_spec(module)
        except (ModuleNotFoundError, ValueError, ImportError):
            continue
        if not spec or not spec.origin:
            continue
        origin = Path(spec.origin).resolve()
        try:
            rel = origin.relative_to(root)
        except ValueError:
            continue
        if origin.is_file():
            out[alias] = rel.as_posix()

    return out


def extract_monkeypatch_targets(test_file: str, project_dir: Path) -> set[str]:
    """Extract alias names used as the first argument to `monkeypatch.setattr()` in a test file."""
    root = project_dir.resolve()
    test_path = (root / test_file).resolve()
    if not test_path.is_file():
        return set()

    try:
        content = test_path.read_text(errors="replace")
    except Exception:
        return set()

    return set(_MONKEYPATCH_RE.findall(content))


def infer_suspect_source_files(
    failed_test_files: list[str],
    project_dir: Path,
) -> list[str]:
    """Infer likely source files that may need changes based on failing test imports.

    Strategy:
    1. Resolve import aliases to repo paths.
    2. Keep aliases ending with `_module` or used in `monkeypatch.setattr()`.
    3. Return the unique set of resolved source file paths.
    """
    root = project_dir.resolve()
    suspects: set[str] = set()

    for test_file in failed_test_files:
        # Get all import aliases -> paths
        alias_to_path = resolve_test_import_aliases_to_paths(test_file, root)
        if not alias_to_path:
            continue

        # Get monkeypatch targets
        monkeypatch_targets = extract_monkeypatch_targets(test_file, root)

        # Filter to suspect aliases
        for alias, path in alias_to_path.items():
            # Include if alias ends with _module or is a monkeypatch target
            if alias.endswith("_module") or alias in monkeypatch_targets:
                # Only include src/ files as suspects (not test files)
                if path.startswith("src/") or not path.startswith("tests/"):
                    suspects.add(path)

    return sorted(suspects)
