# Project Context (Session Handoff)

Updated: 2026-03-16

## Current Source of Truth
- Tasks are stored in Postgres (`backend.models.task.Task`).
- Obsidian Kanban file is synced via `backend/sync/sync_service.py`.
- Active vault path in compose: `/home/mwu/Work/notes/Work/TODO.md`.

## Important Recent Changes
- `docker-compose.yml`
  - Uses fully qualified images:
    - `docker.io/library/postgres:16`
    - `docker.io/library/redis:7-alpine`
  - `api` and `worker` now set:
    - `OBSIDIAN_VAULT_PATH=/home/mwu/Work/notes/Work/TODO.md`
  - Notes mount is `/home/mwu/Work/notes:/home/mwu/Work/notes`.

- Markdown sync reliability
  - Added polling fallback in `backend/sync/sync_service.py` (2s hash check) because file watch events can be missed on mounted volumes.
  - Manual edits in `TODO.md` now sync into DB reliably.

- MCP server behavior changed (major)
  - `backend/mcp_server.py` is now DB-backed (no JSON `tasks.json` source of truth).
  - MCP status mapping:
    - `todo` -> `radar/runway`
    - `in_progress` -> `flight`
    - `done` -> `done`
    - `blocked` -> `blocked`
  - MCP mutating actions now call markdown sync (`sync_to_vault`).
  - MCP task identifiers are now `task_code` (e.g. `O-024`) in responses; UUID lookup still works as fallback.

- Dashboard/frontend
  - Active UI is `frontend/dashboard.jsx` via `frontend/src/App.jsx`.
  - Dashboard was rewired from legacy `/tickets` to `/tasks` + `/sync/status`.
  - Workflow column is phase-driven (`phase` in `location_tags`), not tag-driven.
  - Reserved orchestration labels are stripped from task tags at ingest/write:
    - `manager`
    - `coder`
    - `analyzer`
  - Added warning banners for:
    - missing vault file
    - parse errors
    - empty task set
  - Kanban layout updates:
    - columns fill board width
    - per-column scroll for long lists
    - drag & drop between columns enabled
    - move buttons removed
    - task card shows grey task ID pill (`task_code`)
    - top duplicate stage counter row removed
    - stats panel removed
    - live log moved below radar section

## Operational Commands
- Start stack:
  - `podman compose up -d`
- Restart after config/code changes:
  - `podman compose down && podman compose up -d`
- Check API tasks:
  - `curl http://localhost:8000/tasks/`
- Check sync status:
  - `curl http://localhost:8000/sync/status`

## Codex MCP Registration (current)
- Use DB-backed MCP server (no `TASK_STORE_PATH` needed):
  - `codex mcp add agent-orchestrator -- bash -lc "cd /home/mwu/Work/projects/agent-orchestrator && uv run mcp-server"`

## MCP Live Validation (for future sessions)
- Use this exact prompt with Codex after MCP is connected:
  - `Validate the agent-orchestrator MCP live using the PROJECT_CONTEXT.md MCP checklist. Create, read, update, filter, complete, block, and delete a temporary task and verify markdown sync expectations.`
- Validation checklist (via MCP tools, not direct DB edits):
  1. `list_tasks` baseline count and confirm IDs are `task_code` style (for example `O-024` / `MCP-0001`).
  2. `create_task` with `context.phase`, `context.due_date`, `context.repo_path`, plus tags/priority.
  3. `get_task` for the new task and verify returned context fields are present.
  4. `update_task` to change title/priority/tags/context and verify with `get_task`.
  5. `start_task` then verify status becomes `in_progress`.
  6. `complete_task` then verify status becomes `done`.
  7. `block_task` on a second temporary task and verify status `blocked`.
  8. `list_tasks` filters:
     - by `status`
     - by `priority`
     - by `tags`
     - by `phase`
  9. `delete_task` cleanup for every temporary task created during validation.
- Kanban/markdown sync expectation after MCP mutation:
  - New and updated tasks should appear in the currently selected vault Kanban file after sync cycle.
  - If mismatch is observed, also check API `GET /sync/status` and selected file via `/kanban/select` flow.
- Definition of done:
  - All MCP CRUD + workflow transitions succeed.
  - Filters return expected subsets.
  - No leftover temporary tasks remain.

## Notes / Caveats
- Older docs (`README.md`, `MCP_SETUP.md`, `QUICKSTART.md`) still mention JSON-backed MCP (`tasks.json`). They are now partially outdated.
- Existing tests for `backend/mcp_server.py` may assume old JSON behavior and likely need updates to reflect DB-backed behavior.
