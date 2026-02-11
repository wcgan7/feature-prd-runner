"""Tests for v2 PRD import preview/commit API."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from feature_prd_runner.server.api import create_app


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
    return create_app(project_dir=project_dir, enable_cors=False)


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

