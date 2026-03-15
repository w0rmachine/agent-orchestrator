# AI Kanban Dashboard — Project Plan & Architecture

> Local AI-assisted task operating system with bidirectional Obsidian sync.
> Last updated: March 2026

-----

## 1. Project Vision

A local AI-assisted task operating system that integrates with Obsidian Kanban markdown notes.

**The system must:**

- Sync tasks bidirectionally between Obsidian markdown and an internal PostgreSQL database
- Provide a browser-based Kanban dashboard with real-time AI activity logs
- Use AI to evaluate, split, tag, and prioritize tasks when promoted to Runway
- Track task statistics and productivity metrics
- Expose HTTP-based MCP endpoints callable by Claude or curl
- Support a CLI tool for terminal-first task management
- Later support AI agents that autonomously execute tasks

**Source of truth:** PostgreSQL database
**Human-friendly projection:** Obsidian markdown (generated view)

-----

## 2. Kanban Workflow

Tasks move through these states:

|State    |Meaning                                |
|---------|---------------------------------------|
|`Radar`  |Backlog — on your radar, not yet active|
|`Runway` |Ready to start — AI evaluates on entry |
|`Flight` |In progress                            |
|`Blocked`|Waiting on something external          |
|`Done`   |Finished                               |

### Markdown Representation

```markdown
## Radar

- [ ] Setup authentication #backend <!-- TASK-001 -->

## Runway

- [ ] Implement task API <!-- TASK-002 -->
  - [ ] Create task model <!-- TASK-002-A -->
  - [ ] Add CRUD endpoints <!-- TASK-002-B -->

## Flight

- [ ] Build markdown sync engine <!-- TASK-003 -->

## Blocked

- [ ] Waiting for API key <!-- TASK-004 -->

## Done

- [x] Initial project idea <!-- TASK-000 -->
```

**Subtasks are indented under their parent** as nested list items. This renders correctly in Obsidian and is parseable without ambiguity.

-----

## 3. Task ID Format

```
TASK-001          # top-level task
TASK-001-A        # AI-generated subtask
TASK-001-B
TASK-001-C
```

- IDs are embedded in markdown as HTML comments: `<!-- TASK-001 -->`
- IDs are stable — never reassigned after creation
- Subtask IDs are generated at split time and never change

-----

## 4. ADHD Productivity Features

### Special Tags

|Tag         |Meaning                              |
|------------|-------------------------------------|
|`#fasttask` |Completable in under 5 minutes       |
|`#deepwork` |Requires focus and uninterrupted time|
|`#lowenergy`|Can be done when tired or distracted |
|`#home`     |Requires being at home               |
|`#work`     |Requires being at a work location    |

### AI Recommendations

The AI (via MCP or CLI) can recommend the best next task based on:

- Time available
- Energy level
- Current location
- Active git repository context

**Example CLI output:**

```
Best task now:

TASK-042 — Fix README typo
Estimated time: 5 minutes
Energy required: low
Location: anywhere
Repo: ai-kanban
```

-----

## 5. Architecture

```
                Obsidian Vault
                  Kanban.md
                      ▲
                      │  (watchdog / inotify)
                  Sync Engine
                  (hash guard)
                      │
                      ▼
Frontend (React) ←→ FastAPI Backend
                      │
                      ▼
                  PostgreSQL
                      │
                      ▼
               Redis + RQ Workers
                      │
                      ▼
               Anthropic AI API
```

### Key Architectural Principles

1. **DB is source of truth.** Markdown is always rebuilt from DB state.
2. **Sync is hash-guarded.** File hash stored in DB prevents infinite write loops.
3. **Conflict resolution is explicit.** Merge rules defined in an isolated `merge.py` module.
4. **AI runs async.** All AI jobs are queued via RQ, never blocking API responses.
5. **MCP is HTTP-native.** Tool schemas exposed over HTTP — no stdio transport needed.
6. **Prompts are versioned files.** AI prompts live in `backend/prompts/`, not hardcoded.

-----

## 6. Technology Stack

### Backend

|Tool         |Version|Purpose                              |
|-------------|-------|-------------------------------------|
|Python       |3.12+  |Runtime                              |
|FastAPI      |latest |API framework                        |
|SQLModel     |latest |ORM + Pydantic models                |
|Alembic      |latest |DB migrations                        |
|watchdog     |latest |Filesystem watcher (inotify on Linux)|
|GitPython    |latest |Repo context analysis                |
|Redis        |7+     |Job queue broker                     |
|RQ           |latest |Background worker queue              |
|python-dotenv|latest |Config management                    |
|typer        |latest |CLI tool                             |

### Frontend

|Tool          |Version|Purpose                |
|--------------|-------|-----------------------|
|React         |18+    |UI framework           |
|TypeScript    |5+     |Type safety            |
|Vite          |latest |Build tool             |
|TailwindCSS   |3+     |Styling                |
|TanStack Query|v5     |Server state management|
|dnd-kit       |latest |Drag and drop          |
|WebSockets    |native |Live AI log streaming  |

### Database

|Tool          |Purpose                           |
|--------------|----------------------------------|
|PostgreSQL 16+|Primary database                  |
|JSONB columns |Tags, metadata, AI session history|
|Alembic       |Schema migrations                 |

### AI Models

|Model                      |Use Case                                                          |
|---------------------------|------------------------------------------------------------------|
|`claude-haiku-4-5-20251001`|Tag generation, classification, priority scoring (fast + cheap)   |
|`claude-sonnet-4-6`        |Task splitting, repo context analysis, subtask reasoning (quality)|

### Infrastructure

|Tool           |Purpose                    |
|---------------|---------------------------|
|Docker Compose |Local service orchestration|
|Linux (inotify)|Vault file watching        |

-----

## 7. Project Structure

```
ai-kanban/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Settings via pydantic-settings
│   ├── database.py                # Engine + session factory
│   │
│   ├── api/
│   │   ├── tasks.py               # Task CRUD + status transitions
│   │   ├── environments.py        # Environment management
│   │   ├── ai.py                  # AI job trigger endpoints
│   │   ├── metrics.py             # Stats and analytics
│   │   └── mcp.py                 # MCP HTTP tool router
│   │
│   ├── models/
│   │   ├── task.py                # Task SQLModel
│   │   ├── environment.py         # Environment SQLModel
│   │   ├── ai_session.py          # AI session + logs SQLModel
│   │   └── task_event.py          # Event log SQLModel
│   │
│   ├── services/
│   │   ├── task_service.py        # Business logic for tasks
│   │   ├── markdown_service.py    # Orchestrates parser + writer
│   │   ├── ai_service.py          # Anthropic API calls
│   │   └── repo_service.py        # Git repo analysis
│   │
│   ├── sync/
│   │   ├── markdown_parser.py     # Markdown → task dicts
│   │   ├── markdown_writer.py     # DB state → markdown rebuild
│   │   ├── merge.py               # Conflict resolution rules (isolated)
│   │   └── vault_watcher.py       # watchdog + hash guard + debounce
│   │
│   ├── workers/
│   │   └── ai_worker.py           # RQ job definitions
│   │
│   ├── mcp/
│   │   ├── tools.py               # Tool definitions + JSON schemas
│   │   └── router.py              # FastAPI MCP router
│   │
│   └── prompts/
│       ├── task_split.md          # Prompt: split task into subtasks
│       ├── tag_classify.md        # Prompt: generate and classify tags
│       └── priority_score.md     # Prompt: estimate priority
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Board.tsx          # Main Kanban board
│       │   ├── Activity.tsx       # Live AI log viewer (WebSocket)
│       │   ├── Stats.tsx          # Productivity metrics
│       │   └── Environments.tsx   # Environment management UI
│       ├── components/
│       │   ├── TaskCard.tsx
│       │   ├── Column.tsx
│       │   └── LogLine.tsx
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   └── useTasks.ts
│       └── services/
│           └── api.ts             # Typed API client
│
├── cli/
│   └── kanban.py                  # typer CLI tool
│
├── docker/
│   ├── docker-compose.yml
│   └── Dockerfile.backend
│
├── scripts/
│   └── init_db.py                 # DB bootstrap script
│
└── docs/
    └── AI_KANBAN_PROJECT_PLAN.md  # This file
```

-----

## 8. Database Schema

### `tasks`

|Column             |Type     |Notes                                         |
|-------------------|---------|----------------------------------------------|
|`id`               |UUID     |Primary key                                   |
|`task_code`        |VARCHAR  |e.g. `TASK-001`, `TASK-001-A`                 |
|`title`            |TEXT     |Task title                                    |
|`description`      |TEXT     |Optional longer description                   |
|`status`           |ENUM     |`radar`, `runway`, `flight`, `blocked`, `done`|
|`priority`         |INT      |1–5, AI-assigned                              |
|`tags`             |JSONB    |`["#fasttask", "#backend"]`                   |
|`location_tags`    |JSONB    |`["#home", "#work"]`                          |
|`environment_id`   |UUID FK  |Linked repo/environment                       |
|`parent_task_id`   |UUID FK  |Null if top-level                             |
|`ai_generated`     |BOOL     |True if created by AI split                   |
|`estimated_minutes`|INT      |AI-estimated duration                         |
|`file_hash`        |VARCHAR  |Hash of last written markdown state           |
|`created_at`       |TIMESTAMP|                                              |
|`updated_at`       |TIMESTAMP|                                              |
|`completed_at`     |TIMESTAMP|                                              |

-----

### `environments`

|Column          |Type     |Notes                            |
|----------------|---------|---------------------------------|
|`id`            |UUID     |                                 |
|`name`          |VARCHAR  |e.g. `ai-kanban`                 |
|`repo_path`     |VARCHAR  |e.g. `~/repos/ai-kanban`         |
|`git_url`       |VARCHAR  |Remote URL                       |
|`tech_stack`    |JSONB    |`["python", "react", "postgres"]`|
|`default_branch`|VARCHAR  |e.g. `main`                      |
|`created_at`    |TIMESTAMP|                                 |

-----

### `task_paths`

|Column       |Type   |Notes                                 |
|-------------|-------|--------------------------------------|
|`id`         |UUID   |                                      |
|`task_id`    |UUID FK|                                      |
|`path`       |VARCHAR|e.g. `/backend/services/ai_service.py`|
|`description`|TEXT   |Why this path is relevant             |

-----

### `ai_sessions`

|Column                |Type     |Notes                                             |
|----------------------|---------|--------------------------------------------------|
|`id`                  |UUID     |                                                  |
|`task_id`             |UUID FK  |                                                  |
|`model`               |VARCHAR  |Model used                                        |
|`status`              |ENUM     |`running`, `paused`, `action_required`, `complete`|
|`conversation_history`|JSONB    |Full message history for resumability             |
|`started_at`          |TIMESTAMP|                                                  |
|`ended_at`            |TIMESTAMP|                                                  |
|`summary`             |TEXT     |AI-generated summary of session                   |

-----

### `ai_logs`

|Column       |Type     |Notes                     |
|-------------|---------|--------------------------|
|`id`         |UUID     |                          |
|`session_id` |UUID FK  |                          |
|`timestamp`  |TIMESTAMP|                          |
|`log_message`|TEXT     |                          |
|`log_level`  |ENUM     |`info`, `warning`, `error`|

-----

### `task_events`

|Column      |Type     |Notes              |
|------------|---------|-------------------|
|`id`        |UUID     |                   |
|`task_id`   |UUID FK  |                   |
|`event_type`|ENUM     |See below          |
|`timestamp` |TIMESTAMP|                   |
|`metadata`  |JSONB    |Optional extra data|

**Event types:** `task_created`, `task_split`, `task_moved`, `task_done`, `task_blocked`, `task_tagged`, `task_prioritized`

-----

## 9. Markdown Sync System

### Conflict Resolution Rules (merge.py)

These rules are explicit and never scattered across the codebase:

|Field                      |Winner                                        |
|---------------------------|----------------------------------------------|
|Status                     |**DB wins**                                   |
|Task code / ID             |**DB wins**                                   |
|AI-generated fields        |**DB wins**                                   |
|Subtasks created by AI     |**DB wins**                                   |
|Title text edits           |**Markdown wins**                             |
|New tasks created by hand  |**Markdown wins**                             |
|Checkbox ticked in markdown|**Markdown wins** (triggers `task_done` event)|

### Hash Guard (prevents infinite loops)

```
Obsidian edits file
  → watchdog fires (inotify)
  → compute SHA256 of file content
  → compare with stored hash in DB
  → if hash unchanged: skip (no-op)
  → if hash changed: parse + merge + update DB
  → DB write triggers markdown rebuild
  → markdown writer stores new hash in DB
```

Without this guard: DB writes MD → watchdog fires → DB updates → writes MD → infinite loop.

### Debounce

Vault watcher debounces file events with a **500ms window** to handle editors that write in multiple passes.

### File → DB (Markdown wins cases)

1. Watchdog detects file change
2. Hash check passes (file actually changed)
3. Parser reads markdown → task dicts
4. Merge rules applied
5. DB updated
6. New hash stored

### DB → Markdown (DB wins cases)

1. DB state changes (API call, AI worker, status transition)
2. `markdown_writer.py` rebuilds all sections from DB
3. Writes full file (safe for <200 tasks)
4. New hash stored in DB

-----

## 10. AI Evaluation Pipeline

**Triggered when:** A task is moved from Radar → Runway

```
task_moved event (Radar → Runway)
        ↓
  RQ job enqueued
  (deduped per task_id)
        ↓
  Haiku call:
  - classify tags
  - estimate time
  - assign priority
        ↓
  Sonnet call:
  - analyze task title + description
  - check environment context (tech stack, repo)
  - generate subtasks if task is complex
        ↓
  Subtasks written to DB
  IDs assigned (TASK-021-A, -B, -C...)
        ↓
  Markdown rebuilt
        ↓
  WebSocket broadcast to dashboard
```

**Deduplication:** Only one AI job per `task_id` queued at a time. If task is already queued, new trigger is dropped.

**Example:**

Input task: `Setup authentication`

AI output:

```
TASK-021-A  Create user model               #backend  ~15min
TASK-021-B  Implement login endpoint        #backend  ~30min
TASK-021-C  Add JWT middleware              #backend  ~20min
TASK-021-D  Write authentication tests     #testing  ~25min
```

-----

## 11. MCP HTTP Interface

MCP tools are exposed as HTTP endpoints under `/mcp/`.

```
POST /mcp/tools/list
→ Returns all available tools with JSON schemas

POST /mcp/tools/call
→ Body: { "tool": "move_task", "args": { "task_code": "TASK-021", "status": "runway" } }
```

### Available Tools

|Tool                       |Description                                           |
|---------------------------|------------------------------------------------------|
|`get_tasks_for_repo`       |Returns all tasks linked to a given repo path         |
|`get_recommended_next_task`|Recommends best next task given energy, location, repo|
|`move_task`                |Moves a task to a new status column                   |
|`mark_done`                |Marks a task as done, logs completion event           |
|`add_context`              |Appends a note/context to a task                      |
|`split_task`               |Manually triggers AI split on a task                  |
|`list_environments`        |Lists all registered environments                     |
|`get_ai_activity`          |Returns recent AI log entries                         |

-----

## 12. CLI Tool

Built with `typer`. Detects current git repo automatically via:

```bash
git rev-parse --show-toplevel
```

### Commands

```bash
kanban next                    # Recommend best task for current repo
kanban focus                   # Move top recommended task to Flight
kanban done TASK-012           # Mark task as done
kanban move TASK-012 runway    # Move task to a column
kanban log                     # Tail live AI activity log
kanban env list                # List environments
kanban env add                 # Register current repo as environment
kanban split TASK-012          # Manually trigger AI split
```

-----

## 13. Dashboard Pages

### Board

- 5-column Kanban: Radar / Runway / Flight / Blocked / Done
- Drag and drop via `dnd-kit`
- Task cards show: ID, title, tags, priority, estimated time
- Moving to Runway triggers AI evaluation automatically

### Activity

- Live WebSocket log viewer
- Shows: timestamp, task ID, log message, log level
- Highlights `action_required` sessions (Phase 6)

```
[10:31:02] INFO   Evaluating TASK-021
[10:31:03] INFO   Detecting repo context → ai-kanban
[10:31:05] INFO   Sonnet: splitting task into 4 subtasks
[10:31:06] INFO   Created TASK-021-A, TASK-021-B, TASK-021-C, TASK-021-D
[10:31:06] INFO   Syncing markdown...
[10:31:06] INFO   Done
```

### Statistics

- Tasks completed today / this week / all time
- Average completion time
- Fast tasks count (`#fasttask`)
- Blocked task count
- Burn-down chart (optional)
- Productivity trend by day

### Environments

- List all environments
- Show open / active / blocked task counts per repo
- Link tasks to environments
- Register new environment via form

-----

## 14. Docker Compose

```yaml
services:
  api:
    build: ./docker/Dockerfile.backend
    ports: ["8000:8000"]
    depends_on: [db, redis]

  worker:
    build: ./docker/Dockerfile.backend
    command: rq worker
    depends_on: [db, redis]

  db:
    image: postgres:16
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7

  frontend:
    build: ./frontend
    ports: ["5173:5173"]

volumes:
  pgdata:
```

-----

## 15. Development Phases

### Phase 1 — Foundation

**Goal:** Running API, full DB schema, environment management

- [ ] FastAPI project scaffold
- [ ] SQLModel models + Alembic migrations
- [ ] Task CRUD API (`/tasks`)
- [ ] Environment CRUD API (`/environments`)
- [ ] Task event logging on all state transitions
- [ ] Docker Compose with Postgres + Redis
- [ ] Bootstrap at least one environment manually

> ⚠️ Do not skip environment setup. AI evaluation depends on it.

-----

### Phase 2 — Markdown Sync Engine

**Goal:** Bidirectional, hash-guarded sync

- [ ] `markdown_parser.py` — parse columns + extract task IDs
- [ ] `markdown_writer.py` — full markdown rebuild from DB
- [ ] `merge.py` — explicit conflict resolution rules
- [ ] `vault_watcher.py` — watchdog + hash guard + 500ms debounce
- [ ] ID generation logic (`TASK-001`, `TASK-001-A`)
- [ ] Unit tests for parser + writer against fixture markdown files

> ⚠️ Test the sync engine completely standalone before wiring to the API.

-----

### Phase 3 — Frontend Dashboard

**Goal:** Functional Kanban board with real-time log panel

- [ ] React + Vite + Tailwind + TanStack Query scaffold
- [ ] `Board.tsx` — 5-column Kanban with dnd-kit
- [ ] `Activity.tsx` — WebSocket log viewer
- [ ] `Stats.tsx` — productivity metrics
- [ ] `Environments.tsx` — environment list + task counts
- [ ] Typed API client (`api.ts`)

-----

### Phase 4 — AI Integration

**Goal:** AI evaluates and splits tasks on Runway promotion

- [ ] RQ worker + job definitions
- [ ] Haiku call: tag classification + priority + time estimate
- [ ] Sonnet call: task splitting + subtask generation
- [ ] Subtask DB writes + ID assignment
- [ ] Markdown sync after split
- [ ] WebSocket broadcast of AI log lines
- [ ] Job deduplication per task_id
- [ ] Prompt files in `backend/prompts/`

-----

### Phase 5 — MCP + CLI

**Goal:** HTTP MCP tools + terminal-first task management

- [ ] `POST /mcp/tools/list` + `POST /mcp/tools/call`
- [ ] All 8 MCP tools implemented
- [ ] `typer` CLI with all commands
- [ ] Repo auto-detection via `git rev-parse`
- [ ] CLI calls MCP endpoints internally

-----

### Phase 6 — AI Agent System (Future)

**Goal:** Autonomous task execution with dashboard oversight

- Agent session maps to `ai_session` DB row
- Statuses: `running | paused | action_required | complete`
- Conversation history checkpointed to `ai_sessions.conversation_history` (JSONB)
- Frontend subscribes to session status, highlights `action_required` tickets
- Sub-agents: planning → coding → testing → review
- Full resume capability after server restart

-----

## 16. Known Engineering Risks

|Risk                           |Mitigation                                                               |
|-------------------------------|-------------------------------------------------------------------------|
|Infinite sync loop             |Hash guard in `vault_watcher.py`                                         |
|Concurrent AI jobs on same task|RQ job dedup key per `task_id`                                           |
|Markdown parse regression      |Fixture-based unit tests for parser                                      |
|Agent session lost on restart  |Checkpoint conversation history to DB                                    |
|Obsidian plugin conflict       |Write to markdown only when DB-initiated; file watcher ignores own writes|

-----

## 17. Long-Term Vision

This system evolves into a personal AI task operating system:

- AI planning + execution with repo awareness
- Autonomous coding agents with human-in-the-loop checkpoints
- Productivity analytics and energy-aware task routing
- Obsidian as the always-readable, always-writable human interface
- MCP as the machine-readable, always-callable automation interface

-----

*Generated as part of initial project planning session. Add to repo as `docs/AI_KANBAN_PROJECT_PLAN.md`.*