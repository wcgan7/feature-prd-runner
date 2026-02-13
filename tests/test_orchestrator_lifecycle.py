from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from feature_prd_runner.server.api import create_app
from feature_prd_runner.v3.domain.models import RunRecord, Task, now_iso
from feature_prd_runner.v3.events.bus import EventBus
from feature_prd_runner.v3.orchestrator.service import OrchestratorService
from feature_prd_runner.v3.orchestrator.worker_adapter import DefaultWorkerAdapter
from feature_prd_runner.v3.storage.container import V3Container


def test_app_shutdown_stops_orchestrators(tmp_path: Path) -> None:
    app = create_app(project_dir=tmp_path, worker_adapter=DefaultWorkerAdapter())
    orchestrator: OrchestratorService | None = None
    with TestClient(app) as client:
        response = client.get("/api/v3/orchestrator/status")
        assert response.status_code == 200
        values = list(app.state.v3_orchestrators.values())
        assert values
        orchestrator = values[0]
        assert orchestrator._thread is not None
        assert orchestrator._thread.is_alive()

    assert orchestrator is not None
    assert app.state.v3_orchestrators == {}
    assert orchestrator._thread is None


def test_in_progress_tasks_recover_on_worker_start(tmp_path: Path) -> None:
    container = V3Container(tmp_path)
    bus = EventBus(container.events, container.project_id)

    task = Task(
        title="Recover me",
        task_type="feature",
        status="in_progress",
        approval_mode="auto_approve",
    )
    container.tasks.upsert(task)
    run = RunRecord(task_id=task.id, status="in_progress", started_at=now_iso())
    container.runs.upsert(run)

    service = OrchestratorService(container, bus, worker_adapter=DefaultWorkerAdapter())
    service.ensure_worker()
    try:
        recovered_task = container.tasks.get(task.id)
        assert recovered_task is not None
        assert recovered_task.status == "ready"
        assert recovered_task.error == "Recovered from interrupted run"

        recovered_run = container.runs.list()[0]
        assert recovered_run.status == "interrupted"
        assert recovered_run.finished_at is not None
    finally:
        service.shutdown()
