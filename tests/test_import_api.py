"""Tests for v2 PRD import preview/commit API."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from feature_prd_runner import orchestrator
from feature_prd_runner.server.api import create_app
from feature_prd_runner.task_engine.engine import TaskEngine
from feature_prd_runner.task_engine.model import TaskStatus


SAMPLE_PRD = """# Feature: Team Activity Feed

## Acceptance Criteria
- Feed shows the latest events
- Feed supports pagination

### Phase 1: Data model and API
Create storage and API endpoints for feed events.

### Phase 2: UI integration
Render the feed UI and connect it to API responses.
"""


@pytest.fixture
def app(tmp_path: Path):
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    state_dir = project_dir / ".prd_runner"
    state_dir.mkdir()
    api = create_app(project_dir=project_dir, enable_cors=False)
    api.state.test_project_dir = project_dir
    return api


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.anyio
class TestPrdImportApi:
    async def test_preview_prd_import(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v2/import/prd/preview",
            json={"prd_content": SAMPLE_PRD},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["job_id"].startswith("prd-import-")
        preview = payload["preview"]
        assert preview["summary"]["task_count"] >= 3  # parent + phases
        assert preview["summary"]["dependency_count"] >= 1
        assert len(preview["estimated_waves"]) >= 2

    async def test_commit_from_preview_job(self, client: AsyncClient) -> None:
        preview_resp = await client.post(
            "/api/v2/import/prd/preview",
            json={"prd_content": SAMPLE_PRD},
        )
        assert preview_resp.status_code == 200
        job_id = preview_resp.json()["job_id"]

        commit_resp = await client.post(
            "/api/v2/import/prd/commit",
            json={"job_id": job_id, "initial_status": "backlog"},
        )
        assert commit_resp.status_code == 200
        commit = commit_resp.json()
        assert commit["job_id"] == job_id
        assert commit["created_count"] >= 3
        assert len(commit["created_task_ids"]) == commit["created_count"]
        assert commit["dependency_count"] >= 1

        # Imported phase ordering should honor dependencies in execution batches.
        batches_resp = await client.get("/api/v2/tasks/execution-order")
        assert batches_resp.status_code == 200
        batches = batches_resp.json()["batches"]
        phase_one_id = commit["created_task_ids"][1]
        phase_two_id = commit["created_task_ids"][2]
        pos: dict[str, int] = {}
        for i, batch in enumerate(batches):
            for tid in batch:
                pos[tid] = i
        assert phase_one_id in pos
        assert phase_two_id in pos
        assert pos[phase_two_id] > pos[phase_one_id]

        job_resp = await client.get(f"/api/v2/import/{job_id}")
        assert job_resp.status_code == 200
        job = job_resp.json()["job"]
        assert job["status"] == "committed"
        assert job["result"]["created_count"] == commit["created_count"]

    async def test_commit_inline_without_preview_job(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/v2/import/prd/commit",
            json={"prd_content": SAMPLE_PRD, "initial_status": "ready"},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["created_count"] >= 3

    async def test_import_controls_are_persisted_and_auto_ready_is_applied(self, client: AsyncClient) -> None:
        preview_resp = await client.post(
            "/api/v2/import/prd/preview",
            json={
                "prd_content": SAMPLE_PRD,
                "granularity": "fine",
                "auto_ready": True,
                "max_parallelism_hint": 3,
            },
        )
        assert preview_resp.status_code == 200
        job_id = preview_resp.json()["job_id"]

        commit_resp = await client.post(
            "/api/v2/import/prd/commit",
            json={
                "job_id": job_id,
                "auto_ready": True,
                "granularity": "fine",
                "max_parallelism_hint": 3,
            },
        )
        assert commit_resp.status_code == 200

        job_resp = await client.get(f"/api/v2/import/{job_id}")
        assert job_resp.status_code == 200
        job = job_resp.json()["job"]
        assert job["request"]["granularity"] == "fine"
        assert job["request"]["auto_ready"] is True
        assert job["request"]["max_parallelism_hint"] == 3
        assert job["result"]["initial_status"] == "ready"
        assert job["result"]["auto_ready"] is True

    async def test_prd_import_executes_dependency_order_in_orchestrator(
        self,
        client: AsyncClient,
        app,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        commit_resp = await client.post(
            "/api/v2/import/prd/commit",
            json={"prd_content": SAMPLE_PRD, "initial_status": "ready"},
        )
        assert commit_resp.status_code == 200

        execution_order: list[str] = []

        def _fake_execute_custom_prompt(**kwargs):
            prompt = str(kwargs.get("user_prompt", ""))
            first_line = prompt.splitlines()[0] if prompt else ""
            if first_line.startswith("Task: "):
                execution_order.append(first_line.replace("Task: ", "", 1))
            return True, None

        monkeypatch.setenv("FEATURE_PRD_AUTO_APPROVE_REVIEW", "true")
        monkeypatch.setattr(orchestrator, "execute_custom_prompt", _fake_execute_custom_prompt)

        project_dir = Path(app.state.test_project_dir)
        state_dir = project_dir / ".prd_runner"
        run_state: dict[str, object] = {
            "status": "idle",
            "current_task_id": None,
            "run_id": None,
            "last_error": None,
        }

        max_iterations = 10
        for _ in range(max_iterations):
            handled = orchestrator._run_next_v2_task(
                project_dir=project_dir,
                state_dir=state_dir,
                run_state=run_state,
                shift_minutes=30,
                heartbeat_seconds=5,
                heartbeat_grace_seconds=120,
                override_agents=False,
            )
            if not handled:
                break

        assert execution_order
        assert "Data model and API" in execution_order
        assert "UI integration" in execution_order
        assert execution_order.index("UI integration") > execution_order.index("Data model and API")

        engine = TaskEngine(state_dir, allow_auto_approve_review=True)
        all_tasks = {t.title: t for t in engine.list_tasks()}
        assert all_tasks["Data model and API"].status == TaskStatus.DONE
        assert all_tasks["UI integration"].status == TaskStatus.DONE
