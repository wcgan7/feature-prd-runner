from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

from .constants import WINDOWS_LOCK_BYTES
from .utils import _now_iso, _parse_iso


def _require_yaml() -> None:
    if not yaml:
        raise RuntimeError("PyYAML is required to read/write .yaml files. Install pyyaml.")


class FileLock:
    """Best-effort cross-platform file lock."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.handle: Optional[Any] = None
        self.lock_bytes = WINDOWS_LOCK_BYTES

    def __enter__(self) -> "FileLock":
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.lock_path, "w")
        try:
            import fcntl
            fcntl.flock(self.handle, fcntl.LOCK_EX)
        except ImportError:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                self.handle.truncate(self.lock_bytes)
                self.handle.flush()
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_LOCK, self.lock_bytes)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if not self.handle:
            return
        try:
            import fcntl
            fcntl.flock(self.handle, fcntl.LOCK_UN)
        except ImportError:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, self.lock_bytes)
        self.handle.close()
        self.handle = None


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as handle:
        json.dump(data, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _load_data(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        with open(path, "r") as handle:
            if path.suffix in {".yaml", ".yml"}:
                _require_yaml()
                data = yaml.safe_load(handle)
            else:
                data = json.load(handle)
        return data if isinstance(data, dict) else default
    except (OSError, json.JSONDecodeError):
        return default
    except Exception as exc:
        if yaml and isinstance(exc, yaml.YAMLError):
            return default
        raise


def _load_data_with_error(
    path: Path,
    default: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    """
    Load JSON/YAML and return (data, error_message).

    Unlike _load_data(), this reports parse/IO failures so callers can avoid
    overwriting corrupted durable state files.
    """
    if not path.exists():
        return default, None
    try:
        with open(path, "r") as handle:
            if path.suffix in {".yaml", ".yml"}:
                _require_yaml()
                data = yaml.safe_load(handle)
            else:
                data = json.load(handle)
        if not isinstance(data, dict):
            return default, f"{path.name}: expected object, got {type(data).__name__}"
        return data, None
    except OSError as exc:
        return default, f"{path.name}: {exc.__class__.__name__}: {exc}"
    except json.JSONDecodeError as exc:
        return default, f"{path.name}: JSONDecodeError: {exc}"
    except Exception as exc:
        if yaml and isinstance(exc, yaml.YAMLError):
            return default, f"{path.name}: YAMLError: {exc}"
        return default, f"{path.name}: {exc.__class__.__name__}: {exc}"


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    _require_yaml()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w") as handle:
        yaml.safe_dump(
            data,
            handle,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _save_data(path: Path, data: dict[str, Any]) -> None:
    if path.suffix in {".yaml", ".yml"}:
        _atomic_write_yaml(path, data)
    else:
        _atomic_write_json(path, data)


def _append_event(events_path: Path, event: dict[str, Any]) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload.setdefault("timestamp", _now_iso())
    line = json.dumps(payload) + "\n"
    with open(events_path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _update_progress(progress_path: Path, updates: dict[str, Any]) -> None:
    current = _load_data(progress_path, {})
    current.update(updates)
    current["timestamp"] = _now_iso()
    current["heartbeat"] = _now_iso()
    _save_data(progress_path, current)


def _read_log_tail(path: Path, max_chars: int = 4000) -> str:
    return _read_text_tail(path, max_chars=max_chars)


def _read_text_tail(path: Path, *, max_chars: int = 4000, encoding: str = "utf-8") -> str:
    """
    Efficiently read the last ~max_chars of a text file without loading the whole file.
    """
    if max_chars <= 0:
        return ""
    if not path.exists():
        return ""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            # Overshoot in bytes to account for multi-byte encodings.
            max_bytes = min(size, max_chars * 4)
            handle.seek(-max_bytes, os.SEEK_END)
            data = handle.read()
    except OSError:
        return ""
    text = data.decode(encoding, errors="replace")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _read_text_window(
    path: Path,
    *,
    max_chars: int = 120_000,
    head_chars: int = 40_000,
    tail_chars: int = 80_000,
    encoding: str = "utf-8",
) -> tuple[str, bool]:
    """
    Read a bounded excerpt of a potentially large text file.

    Returns (text, truncated). If the file is large, returns a head+tail window.
    """
    if max_chars <= 0:
        return "", False
    head_chars = max(0, min(head_chars, max_chars))
    tail_chars = max(0, min(tail_chars, max_chars - head_chars))
    if not path.exists():
        return "", False
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            # Heuristic: if it's small, read it all.
            max_bytes = max_chars * 4
            if size <= max_bytes:
                handle.seek(0)
                data = handle.read()
                return data.decode(encoding, errors="replace"), False

            # Read head + tail windows.
            head_bytes = min(size, head_chars * 4)
            tail_bytes = min(size, tail_chars * 4)

            handle.seek(0)
            head = handle.read(head_bytes)
            handle.seek(-tail_bytes, os.SEEK_END)
            tail = handle.read(tail_bytes)
    except OSError:
        return "", False

    text = head.decode(encoding, errors="replace")
    if tail_bytes:
        text += "\n\n[runner] ... log truncated ...\n\n"
        text += tail.decode(encoding, errors="replace")
    if len(text) > max_chars:
        # As a last guard, cap the returned text while preserving the tail window.
        # Failures and tracebacks are more likely to be near the end of a log.
        text = text[-max_chars:]
    return text, True


def _read_text_for_prompt(path: Path, max_chars: int = 20000) -> tuple[str, bool]:
    try:
        content = path.read_text(errors="replace")
    except OSError:
        return "", False
    if len(content) <= max_chars:
        return content, False
    return content[:max_chars], True


def _render_json_for_prompt(data: dict[str, Any], max_chars: int = 20000) -> tuple[str, bool]:
    text = json.dumps(data, indent=2, sort_keys=True)
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _heartbeat_from_progress(
    progress_path: Path,
    expected_run_id: Optional[str] = None,
) -> Optional[datetime]:
    if not progress_path.exists():
        return None
    progress = _load_data(progress_path, {})
    if expected_run_id:
        run_id = progress.get("run_id")
        if run_id and run_id != expected_run_id:
            return None
    heartbeat = _parse_iso(progress.get("heartbeat")) or _parse_iso(progress.get("timestamp"))
    if heartbeat:
        return heartbeat
    try:
        mtime = progress_path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
    except OSError:
        return None
