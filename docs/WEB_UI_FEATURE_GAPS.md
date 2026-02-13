# Web UI Review Findings (v3)

Status: Updated after cleanup + integration pass  
Date: 2026-02-13  
Scope: Mounted v3 web app (`web/src/App.tsx`) against v3 backend router (`src/feature_prd_runner/v3/api/router.py`).

## Closed From Prior Review

These gaps are now addressed in mounted UI:
- Settings surface for:
  - `orchestrator.concurrency`
  - `orchestrator.auto_deps`
  - `orchestrator.max_review_attempts`
  - `agent_routing.*`
  - `defaults.quality_gate.*`
  - `workers.default`
  - `workers.routing`
  - `workers.providers`
- Dependency analysis actions:
  - `POST /tasks/analyze-dependencies`
  - `POST /tasks/{id}/reset-dep-analysis`
- Gate approval action:
  - `POST /tasks/{id}/approve-gate`
- Per-task HITL mode editing (wired `HITLModeSelector` in task detail).
- `ParallelPlanView` is now mounted in Execution.
- Dependency graph visualization now exists in Task Detail (lightweight directed view around selected task).
- Compatibility visibility endpoints are now mounted:
  - `GET /api/v3/phases`
  - `GET /api/v3/collaboration/presence`
- Compatibility/collaboration endpoints are now mounted:
  - `GET /api/v3/metrics`
  - `GET /api/v3/agents/types`
  - `GET /api/v3/collaboration/timeline/{task_id}`
  - `GET/POST /api/v3/collaboration/feedback*`
  - `GET/POST /api/v3/collaboration/comments*`
- Realtime hardening for multi-project sustained websocket usage:
  - client ignores `system` frames for reload decisions
  - client coalesces reloads instead of refetching on every frame
  - client reconnects with bounded exponential backoff
  - client and websocket hub both support `project_id` scoped event filtering
- Async stale-response race guards added for:
  - task detail loading
  - collaboration loading
  - task explorer loading
  - top-level `reloadAll` hydration
- HITL mode selector accessibility/mobile hardening:
  - button/listbox semantics and keyboard escape handling
  - focus-visible styling and outside-click close
  - mobile bottom-sheet presentation for mode options
- Auth header propagation is now centralized through main request helper in mounted UI.
- Unmounted MUI shell/theme surface was removed:
  - deleted `web/src/ui/layout/AppShell.tsx`
  - deleted `web/src/ui/theme.ts`
  - deleted `web/src/ui/tokens.ts`
- Nonexistent endpoint callers removed with legacy component cleanup:
  - Task delete mismatch (`DELETE /api/v3/tasks/{id}`)
  - Live log mismatch (`GET /api/v3/logs/{runId}`)
  - Reasoning mismatch (`GET /api/v3/agents/reasoning/{taskId}`)
- Production dependency audit cleanup:
  - removed unused `recharts` dependency path (which pulled vulnerable lodash)
  - `npm audit --omit=dev` now reports 0 vulnerabilities

## Current Findings (Ordered by Severity)

No functional endpoint coverage gaps were found for mounted v3 UI flows after this pass.

### P3: Collaboration UX remains intentionally lightweight

Timeline/feedback/comments are now wired, but currently implemented as simple inline forms/lists in Task Detail.
This is functionally complete for API coverage and manual workflows, but not yet optimized for high-volume review ergonomics (threading, filtering, pagination).

### P3: Confidence could be improved with deeper scenario testing

Current frontend tests/build/lint are green, but most orchestration behavior is still validated through mocked unit-style tests rather than long-running realtime integration scenarios.

## Cleanup Notes

Legacy/unmounted component surface was pruned heavily from `web/src/components`, plus unused contexts/hooks.
Kept:
- `web/src/components/HITLModeSelector/HITLModeSelector.tsx`
- `web/src/components/ParallelPlanView.tsx` (now mounted in Execution)

Also cleaned up stale unused API helper exports in `web/src/api.ts` that no longer had callers.

## Validation Snapshot

- Frontend: `npm test` (25/25) and `npm run build` pass.
- Frontend hardening checks: `npm run lint`, `npm run check`, and `npm audit --omit=dev` pass.
- Backend (targeted): collaboration suites pass; settings endpoint round-trip passes (including workers settings).
