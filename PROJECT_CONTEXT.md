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

## Notes / Caveats
- Older docs (`README.md`, `MCP_SETUP.md`, `QUICKSTART.md`) still mention JSON-backed MCP (`tasks.json`). They are now partially outdated.
- Existing tests for `backend/mcp_server.py` may assume old JSON behavior and likely need updates to reflect DB-backed behavior.
