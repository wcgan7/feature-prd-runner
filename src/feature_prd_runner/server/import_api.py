"""V2 PRD import API endpoints (preview + commit)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..task_engine.engine import TaskEngine
from ..task_engine.model import Task, TaskStatus
from ..task_engine.sources.prd_import import PrdImportGenerator


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_preview_waves(tasks: list[Task]) -> list[list[str]]:
    """Topological batches for preview tasks."""
    task_map = {t.id: t for t in tasks}
    in_degree: dict[str, int] = {t.id: 0 for t in tasks}
    adj: dict[str, list[str]] = {t.id: [] for t in tasks}

    for t in tasks:
        for dep_id in t.blocked_by:
            if dep_id in task_map:
                in_degree[t.id] += 1
                adj[dep_id].append(t.id)

    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    waves: list[list[str]] = []
    while queue:
        current = list(queue)
        waves.append(current)
        next_queue: list[str] = []
        for tid in current:
            for neighbor in adj.get(tid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    next_queue.append(neighbor)
        queue = next_queue
    return waves


def _preview_payload(tasks: list[Task], prd_title: Optional[str] = None) -> dict[str, Any]:
    edges = []
    for t in tasks:
        for dep_id in t.blocked_by:
            edges.append({"from": dep_id, "to": t.id})
    root_task_ids = [t.id for t in tasks if not t.blocked_by]
    waves = _build_preview_waves(tasks)
    task_payload = [t.to_dict() for t in tasks]
    return {
        "prd_title": prd_title or (tasks[0].title if tasks else "Imported PRD"),
        "tasks": task_payload,
        "dependencies": edges,
        "root_task_ids": root_task_ids,
        "estimated_waves": waves,
        "summary": {
            "task_count": len(task_payload),
            "dependency_count": len(edges),
            "wave_count": len(waves),
        },
    }


class PrdImportPreviewRequest(BaseModel):
    prd_content: Optional[str] = None
    prd_path: Optional[str] = None
    granularity: str = "balanced"  # coarse | balanced | fine
    auto_ready: bool = False
    max_parallelism_hint: Optional[int] = None


class PrdImportPreviewResponse(BaseModel):
    job_id: str
    preview: dict[str, Any]


class PrdImportCommitRequest(BaseModel):
    job_id: Optional[str] = None
    prd_content: Optional[str] = None
    prd_path: Optional[str] = None
    created_by: Optional[str] = None
    initial_status: str = "backlog"
    granularity: str = "balanced"  # coarse | balanced | fine
    auto_ready: bool = False
    max_parallelism_hint: Optional[int] = None


class PrdImportCommitResponse(BaseModel):
    job_id: str
    created_task_ids: list[str]
    created_count: int
    dependency_count: int


class PrdImportJobResponse(BaseModel):
    job: dict[str, Any]


def create_import_router(get_engine: Any) -> APIRouter:
    router = APIRouter(prefix="/api/v2/import", tags=["import-v2"])
    valid_granularity = {"coarse", "balanced", "fine"}

    def _state_dir(engine: TaskEngine) -> Path:
        state_dir = getattr(engine, "_state_dir", None)
        if isinstance(state_dir, Path):
            return state_dir
        store_state_dir = getattr(engine.store, "_state_dir", None)
        if isinstance(store_state_dir, Path):
            return store_state_dir
        raise RuntimeError("Unable to resolve task engine state directory")

    def _jobs_path(engine: TaskEngine) -> Path:
        return _state_dir(engine) / "import_jobs.json"

    def _load_jobs(engine: TaskEngine) -> dict[str, Any]:
        path = _jobs_path(engine)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_jobs(engine: TaskEngine, jobs: dict[str, Any]) -> None:
        path = _jobs_path(engine)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    def _resolve_prd_input(
        project_dir: Optional[str],
        body_content: Optional[str],
        body_path: Optional[str],
    ) -> tuple[Optional[str], Optional[Path]]:
        content = (body_content or "").strip() or None
        path: Optional[Path] = None
        if body_path:
            raw_path = Path(body_path)
            if raw_path.is_absolute():
                path = raw_path
            elif project_dir:
                path = Path(project_dir) / raw_path
            else:
                path = Path.cwd() / raw_path
        return content, path

    @router.post("/prd/preview", response_model=PrdImportPreviewResponse)
    async def preview_prd_import(
        body: PrdImportPreviewRequest,
        project_dir: Optional[str] = Query(None),
    ) -> PrdImportPreviewResponse:
        if body.granularity not in valid_granularity:
            raise HTTPException(status_code=400, detail="granularity must be coarse|balanced|fine")
        if not (body.prd_content and body.prd_content.strip()) and not body.prd_path:
            raise HTTPException(status_code=400, detail="Provide prd_content or prd_path")

        engine = get_engine(project_dir)
        content, path = _resolve_prd_input(project_dir, body.prd_content, body.prd_path)
        if path is not None and not path.exists():
            raise HTTPException(status_code=404, detail=f"PRD file not found: {path}")

        generator = PrdImportGenerator()
        tasks = generator.generate(
            project_dir=_state_dir(engine).parent,
            prd_path=path,
            prd_content=content,
        )
        if not tasks:
            raise HTTPException(status_code=400, detail="No tasks generated from PRD input")

        preview = _preview_payload(tasks)
        job_id = f"prd-import-{uuid.uuid4().hex[:10]}"

        jobs = _load_jobs(engine)
        jobs[job_id] = {
            "id": job_id,
            "kind": "prd_import",
            "status": "preview_ready",
            "created_at": _now_iso(),
            "project_dir": str(_state_dir(engine).parent),
            "request": {
                "prd_path": str(path) if path else None,
                "used_inline_content": bool(content),
                "granularity": body.granularity,
                "auto_ready": body.auto_ready,
                "max_parallelism_hint": body.max_parallelism_hint,
            },
            "preview": preview,
        }
        _save_jobs(engine, jobs)
        return PrdImportPreviewResponse(job_id=job_id, preview=preview)

    @router.post("/prd/commit", response_model=PrdImportCommitResponse)
    async def commit_prd_import(
        body: PrdImportCommitRequest,
        project_dir: Optional[str] = Query(None),
    ) -> PrdImportCommitResponse:
        if body.granularity not in valid_granularity:
            raise HTTPException(status_code=400, detail="granularity must be coarse|balanced|fine")
        engine = get_engine(project_dir)
        desired_initial_status = TaskStatus.READY.value if body.auto_ready else body.initial_status
        if desired_initial_status not in {TaskStatus.BACKLOG.value, TaskStatus.READY.value}:
            raise HTTPException(status_code=400, detail="initial_status must be 'backlog' or 'ready'")

        jobs = _load_jobs(engine)
        job: Optional[dict[str, Any]] = None
        preview: Optional[dict[str, Any]] = None
        job_id: str

        if body.job_id:
            job = jobs.get(body.job_id)
            if not isinstance(job, dict):
                raise HTTPException(status_code=404, detail=f"Import job {body.job_id} not found")
            preview = job.get("preview")
            if not isinstance(preview, dict):
                raise HTTPException(status_code=400, detail=f"Import job {body.job_id} has no preview payload")
            job_id = body.job_id
        else:
            content, path = _resolve_prd_input(project_dir, body.prd_content, body.prd_path)
            if path is not None and not path.exists():
                raise HTTPException(status_code=404, detail=f"PRD file not found: {path}")
            if not content and not path:
                raise HTTPException(status_code=400, detail="Provide job_id or prd_content/prd_path")
            generator = PrdImportGenerator()
            tasks = generator.generate(
                project_dir=_state_dir(engine).parent,
                prd_path=path,
                prd_content=content,
            )
            if not tasks:
                raise HTTPException(status_code=400, detail="No tasks generated from PRD input")
            preview = _preview_payload(tasks)
            job_id = f"prd-import-{uuid.uuid4().hex[:10]}"
            job = {
                "id": job_id,
                "kind": "prd_import",
                "status": "preview_ready",
                "created_at": _now_iso(),
                "project_dir": str(_state_dir(engine).parent),
                "request": {
                    "prd_path": str(path) if path else None,
                    "used_inline_content": bool(content),
                    "granularity": body.granularity,
                    "auto_ready": body.auto_ready,
                    "max_parallelism_hint": body.max_parallelism_hint,
                },
                "preview": preview,
            }
            jobs[job_id] = job

        preview_tasks = preview.get("tasks", []) if isinstance(preview, dict) else []
        if not isinstance(preview_tasks, list) or not preview_tasks:
            raise HTTPException(status_code=400, detail="Preview payload has no tasks")

        # 1) Create all tasks (preserving hierarchy via id mapping).
        id_map: dict[str, str] = {}
        created_ids: list[str] = []
        source_task_payload: dict[str, dict[str, Any]] = {}

        for raw in preview_tasks:
            if not isinstance(raw, dict):
                continue
            src_id = str(raw.get("id", ""))
            if not src_id:
                continue
            source_task_payload[src_id] = raw
            parent_src = raw.get("parent_id")
            parent_id = id_map.get(parent_src) if isinstance(parent_src, str) else None
            created = engine.create_task(
                title=str(raw.get("title", "Imported Task")),
                description=str(raw.get("description", "")),
                task_type=str(raw.get("task_type", "feature")),
                priority=str(raw.get("priority", "P2")),
                labels=list(raw.get("labels", []) or []),
                acceptance_criteria=list(raw.get("acceptance_criteria", []) or []),
                context_files=list(raw.get("context_files", []) or []),
                parent_id=parent_id,
                pipeline_template=raw.get("pipeline_template"),
                source="prd_import",
                created_by=body.created_by or "prd_import_api",
                metadata={
                    "import_job_id": job_id,
                    "source_preview_task_id": src_id,
                },
            )
            id_map[src_id] = created.id
            created_ids.append(created.id)

        # 2) Recreate dependencies from preview graph.
        dependency_count = 0
        for src_id, raw in source_task_payload.items():
            target_id = id_map.get(src_id)
            if not target_id:
                continue
            blocked_by = raw.get("blocked_by") or []
            if not isinstance(blocked_by, list):
                continue
            for dep_src_id in blocked_by:
                dep_id = id_map.get(str(dep_src_id))
                if not dep_id:
                    continue
                engine.add_dependency(target_id, dep_id)
                dependency_count += 1

        # 3) Optionally place runnable roots in READY.
        if desired_initial_status == TaskStatus.READY.value:
            for src_id, raw in source_task_payload.items():
                if raw.get("blocked_by"):
                    continue
                new_id = id_map.get(src_id)
                if not new_id:
                    continue
                try:
                    engine.transition_task(new_id, TaskStatus.READY.value)
                except Exception:
                    continue

        job["status"] = "committed"
        job["committed_at"] = _now_iso()
        job["result"] = {
            "created_task_ids": created_ids,
            "created_count": len(created_ids),
            "dependency_count": dependency_count,
            "initial_status": desired_initial_status,
            "auto_ready": body.auto_ready,
            "granularity": body.granularity,
            "max_parallelism_hint": body.max_parallelism_hint,
        }
        jobs[job_id] = job
        _save_jobs(engine, jobs)

        return PrdImportCommitResponse(
            job_id=job_id,
            created_task_ids=created_ids,
            created_count=len(created_ids),
            dependency_count=dependency_count,
        )

    @router.get("/{job_id}", response_model=PrdImportJobResponse)
    async def get_import_job(
        job_id: str,
        project_dir: Optional[str] = Query(None),
    ) -> PrdImportJobResponse:
        engine = get_engine(project_dir)
        jobs = _load_jobs(engine)
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            raise HTTPException(status_code=404, detail=f"Import job {job_id} not found")
        return PrdImportJobResponse(job=job)

    return router
