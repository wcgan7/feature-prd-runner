"""WebSocket helpers for the Feature PRD Runner dashboard."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import WebSocket
from loguru import logger


class ConnectionManager:
    """Track active websocket connections by run id."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        self._connections.setdefault(run_id, set()).add(websocket)
        logger.debug("WebSocket connected: run_id={} connections={}", run_id, len(self._connections[run_id]))

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        conns = self._connections.get(run_id)
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._connections.pop(run_id, None)
        logger.debug("WebSocket disconnected: run_id={}", run_id)


manager = ConnectionManager()


def _resolve_run_dir(project_dir: Path, run_id: str) -> Optional[Path]:
    runs_dir = project_dir / ".prd_runner" / "runs"
    candidate = runs_dir / run_id
    if candidate.exists():
        return candidate

    # Some call sites pass a prefix; mirror the REST endpoints behavior.
    matches = sorted(runs_dir.glob(f"{run_id}*")) if runs_dir.exists() else []
    for match in matches:
        if match.is_dir():
            return match
    return None


async def watch_run_progress(
    websocket: WebSocket,
    run_id: str,
    project_dir: Path,
    *,
    poll_seconds: float = 1.0,
) -> None:
    """Stream `progress.json` updates for a run."""
    run_dir = _resolve_run_dir(project_dir, run_id)
    if not run_dir:
        await websocket.send_text(
            json.dumps({"type": "error", "data": {"message": f"Run {run_id} not found"}})
        )
        return

    progress_path = run_dir / "progress.json"
    last_mtime: float = 0.0

    while True:
        if progress_path.exists():
            try:
                stat = progress_path.stat()
                if stat.st_mtime > last_mtime:
                    last_mtime = stat.st_mtime
                    payload = json.loads(progress_path.read_text(errors="replace") or "{}")
                    await websocket.send_text(
                        json.dumps({"type": "run_progress", "data": payload})
                    )
            except Exception as exc:
                logger.debug("Progress watch error (run_id={}): {}", run_id, exc)

        await asyncio.sleep(poll_seconds)


def _find_latest_log_file(run_dir: Path) -> Optional[Path]:
    candidates = list(run_dir.glob("*.log")) + list(run_dir.glob("*.txt"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


async def watch_logs(
    websocket: WebSocket,
    run_id: str,
    project_dir: Path,
    *,
    poll_seconds: float = 0.5,
    max_initial_bytes: int = 2_000_000,
) -> None:
    """Stream log output updates for a run.

    Message format matches what the frontend expects:
    - {"type":"log_content","data":{"content":"..."}}
    - {"type":"log_append","data":{"content":"..."}}
    """
    run_dir = _resolve_run_dir(project_dir, run_id)
    if not run_dir:
        await websocket.send_text(
            json.dumps({"type": "error", "data": {"message": f"Run {run_id} not found"}})
        )
        return

    current_log: Optional[Path] = None
    offset = 0

    while True:
        latest = _find_latest_log_file(run_dir)
        if latest and latest != current_log:
            current_log = latest
            offset = 0

        if not current_log or not current_log.exists():
            await asyncio.sleep(poll_seconds)
            continue

        try:
            size = current_log.stat().st_size
            if offset == 0:
                # Initial send: tail by bytes to avoid massive payloads.
                with open(current_log, "rb") as f:
                    if size > max_initial_bytes:
                        f.seek(size - max_initial_bytes)
                    content = f.read().decode("utf-8", errors="replace")
                offset = size
                await websocket.send_text(
                    json.dumps({"type": "log_content", "data": {"content": content}})
                )
            elif size < offset:
                # Truncated/rotated: resend full content from start.
                offset = 0
                continue
            elif size > offset:
                with open(current_log, "rb") as f:
                    f.seek(offset)
                    content = f.read().decode("utf-8", errors="replace")
                offset = size
                if content:
                    await websocket.send_text(
                        json.dumps({"type": "log_append", "data": {"content": content}})
                    )
        except Exception as exc:
            logger.debug("Log watch error (run_id={}): {}", run_id, exc)

        await asyncio.sleep(poll_seconds)

