# Radar·Runway — AI Agent Orchestration Dashboard

> A three-stack AI orchestration system that pulls tickets from YouTrack and Obsidian, manages them through a structured pipeline, runs isolated coding sessions, and surfaces everything in a live dashboard — with human-in-the-loop permission gates at every elevated action.

---

## Table of Contents

1. [Vision](#vision)
2. [Architecture](#architecture)
3. [Pipeline Stages](#pipeline-stages)
4. [Agent Stacks](#agent-stacks)
5. [Session Lifecycle](#session-lifecycle)
6. [Permission System](#permission-system)
7. [Integrations](#integrations)
8. [Dashboard Features](#dashboard-features)
9. [API Reference](#api-reference)
10. [WebSocket Contract](#websocket-contract)
11. [Filesystem Layout](#filesystem-layout)
12. [Feature Ideas](#feature-ideas)
13. [Open Concerns](#open-concerns)
14. [Setup & Running](#setup--running)
15. [Roadmap](#roadmap)

---

## Vision

Radar·Runway bridges your ticket tracker (YouTrack), your personal knowledge base (Obsidian), and AI coding agents. Tickets flow through a radar-to-runway metaphor — discovered, analyzed, queued, executed, tested, and landed — with a human operator staying in control of every privileged action. The dashboard is the cockpit.

```
YouTrack  ──┐
             ├──→  Manager Agent  ──→  Backlog  ──→  Session  ──→  Test Session  ──→  Done
Obsidian  ──┘         (split?)            │           (isolated)      (auto-spawn)
                                          │
                                     Human review
                                     before active
```

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Dashboard                          │
│  Kanban  │  Session View  │  Log Stream  │  Permission Alerts   │
└────────────────────────┬────────────────────────────────────────┘
                         │  WebSocket /ws  +  REST API
┌────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend                             │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Manager   │  │   Session    │  │   Permission Gate    │   │
│  │   Agent     │  │   Runner     │  │   (asyncio.Event)    │   │
│  │             │  │              │  │                      │   │
│  │ pull/analyze│  │ git · code   │  │  pending → human     │   │
│  │ split/route │  │ test · report│  │  click → resume/fail │   │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────────┘   │
│         │                │                                      │
│  ┌──────▼────────────────▼──────────────────────────────────┐   │
│  │              In-Memory Store  (→ Postgres)               │   │
│  │   Tickets  │  Sessions  │  Permissions  │  Reports       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────────┐   ┌──────────────────────────────────┐   │
│  │  WS Broadcast Mgr │   │  Background Loop (asyncio.Task)  │   │
│  └───────────────────┘   └──────────────────────────────────┘   │
└────────────┬──────────────────────────────────────────────┬─────┘
             │                                              │
    ┌────────▼────────┐                         ┌──────────▼──────┐
    │  YouTrack REST  │                         │  Obsidian Vault │
    │  /api/issues    │                         │  *.md + tags    │
    └─────────────────┘                         └─────────────────┘
```

### Backend Module Structure

```
backend/
├── main.py                  # App entry point, routes, WebSocket, lifespan
├── config.py                # Pydantic Settings (reads .env)
├── models.py                # All Pydantic models (Ticket, Session, Permission, …)
├── store.py                 # In-memory store — swap internals for SQLAlchemy
├── ws_manager.py            # WebSocket broadcast manager
├── agents/
│   ├── manager.py           # Ticket analysis, tag enrichment, splitting logic
│   ├── session.py           # Session lifecycle: git, workspace, step runner
│   └── tester.py            # Test session runner, coverage, security scan
├── integrations/
│   ├── youtrack.py          # httpx client → YouTrack REST API
│   ├── obsidian.py          # Vault scanner, frontmatter parser
│   └── anthropic.py         # Shared Claude API client + prompt templates
├── logs/                    # Disk logs — logs/{session_hash}/coding.log
├── sessions/                # Workspaces — sessions/{session_hash}/
└── .env
```

### Frontend Module Structure

```
frontend/
├── src/
│   ├── App.tsx
│   ├── ws/
│   │   └── useOrchestrator.ts   # Single WS connection, dispatches all events
│   ├── components/
│   │   ├── KanbanBoard.tsx
│   │   ├── SessionPanel.tsx
│   │   ├── LogStream.tsx
│   │   ├── PermissionAlert.tsx  # Modal/highlight for elevated actions
│   │   ├── RadarSweep.tsx       # Canvas animation for inbox tickets
│   │   ├── StackLane.tsx
│   │   └── ReportModal.tsx
│   └── store/
│       └── orchestratorStore.ts # Zustand / Redux slice
```

---

## Pipeline Stages

| Stage | Metaphor | Description |
|---|---|---|
| `inbox` | Radar signal | Newly synced from YouTrack or Obsidian, not yet reviewed |
| `backlog` | On the taxiway | Analyzed and queued, waiting for an available session slot |
| `analysis` | Approach | Manager agent is enriching tags, deciding on splitting |
| `active` | Takeoff | A session is running; agent is writing code |
| `testing` | Touch-and-go | Automated test session is verifying the implementation |
| `done` | Landed | All checks passed, branch ready for review |
| `blocked` | Diverted | Needs human input, dependency missing, or permission denied |

Stage transitions are broadcast over WebSocket immediately.

---

## Agent Stacks

### Manager (◎)
- Polls YouTrack and Obsidian on a configurable interval
- Sends each new ticket to Claude for analysis:
  - Enriches tags (area, type, risk level)
  - Decides if the ticket should be split into subtasks
  - Adds `manager_notes` with reasoning
- Routes analyzed tickets to `backlog`
- Monitors active sessions and escalates stalled ones to `blocked`

### Analyzer (◈)
- Reads the codebase for context before session begins
- Traces error paths, maps dependencies, identifies root causes
- Attaches a structured context object to the session (files to touch, risky areas, related tests)

### Coder (◇)
- Consumes the session context produced by the Analyzer
- Executes the implementation steps end-to-end
- Commits, pushes, and generates the final report
- Requests permission gates for any elevated action before executing

---

## Session Lifecycle

Each session is identified by a **SHA-256 hash** of `{ticket_id}-{uuid}`. The hash is used as both the workspace folder name and the log directory name.

```
POST /tickets/{tid}/activate
        │
        ▼
create_session()
  ├─ workspace: sessions/{hash}/
  ├─ log file:  logs/{hash}/coding.log
  ├─ branch:    {ticket-ext-id}-impl
  └─ context:   {repo, youtrack_id, ticket_title, description, …}
        │
        ▼
run_session()  ← asyncio.Task
  ├─ setup_workspace
  ├─ clone_repo
  ├─ create_branch          ← branch named after ticket ID
  ├─ index_codebase
  ├─ fetch_ticket_ctx       ← YouTrack history, comments, linked issues
  ├─ plan
  ├─ write_code
  ├─ lint
  ├─ unit_tests
  ├─ [PERMISSION GATE] db_migration    ← elevated
  ├─ run_migration
  ├─ integration_tests
  ├─ commit
  ├─ [PERMISSION GATE] git_push_remote ← elevated
  ├─ push_exec
  └─ generate_report
        │
        ▼
SessionReport
  ├─ summary, files_changed, commits
  ├─ tests_passed / tests_failed
  └─ spawns TestSession (if needed)
        │
        ▼
run_session(is_test=True)
  ├─ checkout branch
  ├─ install_deps
  ├─ full_suite
  ├─ coverage
  ├─ [PERMISSION GATE] security_scan  ← elevated
  ├─ scan_exec
  └─ finalize → ticket.stage = done
```

Every step is logged to both the in-memory store and `logs/{hash}/coding.log` on disk with a UTC timestamp and level prefix.

---

## Permission System

The permission gate is the core human-in-the-loop mechanism. It uses `asyncio.Event` — **zero polling, zero timeout** — the session coroutine is simply parked until a human acts.

```
Session coroutine                  Operator (Dashboard)
─────────────────                  ────────────────────
emit "PERMISSION REQUIRED"
create asyncio.Event()
store event by perm_id
broadcast permission_required ──→  UI shows highlighted alert + button
await event.wait()             ←   POST /permissions/{id}/approve
                                   event.set()
resume or fail gracefully
```

### Permission Levels

| Level | Examples |
|---|---|
| `elevated` | Run DB migration, push to remote, install system packages |
| `sudo` | Modify infra configs, access secrets, run as root |
| `destructive` | Drop tables, delete files, force-push, wipe environment |

Denying a permission causes the session to fail gracefully with a full log of what was attempted. The ticket moves to `blocked`.

---

## Integrations

### YouTrack
- Auth: Bearer token via `YOUTRACK_TOKEN` env var
- Polls `GET /api/issues?query=project:{PROJECT} #Unresolved`
- Fields: `id`, `summary`, `priority`, `description`, `tags`, `links`
- Writes back: session hash as a comment, status transitions on done

### Obsidian
- Scans vault directory for `.md` files with a configurable frontmatter tag (e.g. `tags: [task]`)
- Reads: `title`, `priority`, `repo`, `description` from frontmatter
- Exports: generates `kanban.md` compatible with the Obsidian Kanban plugin
- Export format supports Dataview queries via `#stack/stage` tag convention

### Claude (Anthropic)
- Model: `claude-sonnet-4` for all agent roles
- Manager agent: ticket analysis + split decision (structured JSON output)
- Analyzer agent: codebase context extraction
- Coder agent: implementation, with tool use for git and shell commands
- All prompts are versioned in `agents/prompts/`

---

## Dashboard Features

### Kanban Board
- Six columns mirroring pipeline stages
- Drag or hover-to-move for manual stage overrides
- Card shows: ticket ID, source badge, priority, age, assigned stack
- Syncs to Obsidian `kanban.md` via Copy MD or auto-watch

### Session Panel
- Live view of the active session's current step
- Progress bar through all steps with step history
- Elapsed time counter (live)
- Inline log stream filtered to the session
- Cancel button — gracefully unblocks any waiting permission and terminates

### Permission Alerts
- Highlighted banner when any session hits a gate
- Shows: action name, permission level (color-coded), exact command if applicable
- Approve / Deny buttons — immediately unblocks or fails the session
- Pending permissions badge in the header

### Log Stream
- Global feed of all agents and system events
- Filterable by session, stack, or log level
- Color-coded by source: Manager (amber), Analyzer (teal), Coder (green), System (dim)
- Raw log file accessible per session via `/sessions/{id}/logfile`

### Radar Sweep
- Canvas animation showing tickets in `inbox` and `analysis` as radar blips
- Blip count reflects real ticket count

### Stack Lanes View
- Per-stack runway: shows queued and active tasks as slots
- Completion bar per stack
- Live breathing indicator when a takeoff is active

### Report Modal
- Auto-shown when a session completes
- Summary, files changed, commit list, test counts
- Link to the spawned test session

---

## API Reference

### Tickets
| Method | Path | Description |
|---|---|---|
| `GET` | `/tickets` | List tickets (filter: stage, source, priority) |
| `POST` | `/tickets` | Create ticket manually |
| `GET` | `/tickets/{id}` | Get single ticket |
| `PATCH` | `/tickets/{id}` | Update ticket fields |
| `DELETE` | `/tickets/{id}` | Delete ticket |
| `POST` | `/tickets/{id}/analyze` | Trigger manager agent analysis |
| `POST` | `/tickets/{id}/activate` | Create + start a session for a ticket |
| `POST` | `/sync` | Pull latest from YouTrack + Obsidian |

### Sessions
| Method | Path | Description |
|---|---|---|
| `GET` | `/sessions` | List sessions (filter: status) |
| `GET` | `/sessions/{id}` | Get session detail |
| `GET` | `/sessions/{id}/logs` | Get in-memory logs for session |
| `GET` | `/sessions/{id}/logfile` | Get raw on-disk log file |
| `POST` | `/sessions/{id}/cancel` | Cancel session, unblock any permission gate |

### Permissions
| Method | Path | Description |
|---|---|---|
| `GET` | `/permissions` | List permissions (filter: status, session_id) |
| `GET` | `/permissions/{id}` | Get permission detail |
| `POST` | `/permissions/{id}/approve` | Approve — unblocks session |
| `POST` | `/permissions/{id}/deny` | Deny — fails session gracefully |

### Reports & Utilities
| Method | Path | Description |
|---|---|---|
| `GET` | `/reports` | List all session reports |
| `GET` | `/reports/{session_id}` | Get report for session |
| `GET` | `/stats` | Aggregated counts by stage, stack, status |
| `GET` | `/logs` | Global log feed |
| `GET` | `/export/obsidian` | Render kanban.md for Obsidian |

---

## WebSocket Contract

Connect to `ws://localhost:8000/ws`. On connect you receive a full `init` snapshot. All subsequent messages are push events.

### Inbound (server → client)

| `type` | Key fields | Trigger |
|---|---|---|
| `init` | `tickets`, `sessions`, `permissions`, `reports`, `logs`, `stats` | On connect |
| `ticket_created` | `ticket` | New ticket synced or created |
| `ticket_updated` | `ticket` | Any ticket field changed |
| `ticket_deleted` | `ticket_id` | Ticket removed |
| `session_created` | `session` | Session initialized |
| `session_updated` | `session` | Any session field changed |
| `session_step` | `session_id`, `step`, `message` | Each step begins |
| `session_done` | `session`, `report` | Session completed |
| `session_failed` | `session_id`, `session` | Session failed (e.g. denied permission) |
| `permission_required` | `permission`, `session` | Session hit a gate |
| `permission_resolved` | `permission` | Permission approved or denied |
| `log` | `log` | Any log emission |
| `sync_complete` | `added`, `stats` | Source sync finished |
| `stats` | `stats` | Periodic stats update |

### Outbound (client → server)

```jsonc
{ "type": "approve",  "perm_id": "abc123" }
{ "type": "deny",     "perm_id": "abc123" }
{ "type": "activate", "ticket_id": "T-XYZ" }
{ "type": "analyze",  "ticket_id": "T-XYZ" }
{ "type": "sync" }
```

---

## Filesystem Layout

```
project/
├── backend/
│   ├── main.py
│   ├── .env
│   ├── sessions/
│   │   └── {session_hash}/          # isolated workspace per session
│   │       ├── repo/                # cloned git repo
│   │       └── artifacts/           # any generated files
│   └── logs/
│       └── {session_hash}/
│           └── coding.log           # UTC-timestamped append-only log
├── frontend/
│   └── src/
└── README.md
```

Log format:
```
[2025-03-09T14:22:01] [INFO ] [create_branch] Creating branch: yt-101-impl
[2025-03-09T14:22:04] [WARN ] ⚠ PERMISSION REQUIRED [ELEVATED]: run_db_migration
[2025-03-09T14:22:19] [INFO ] ✓ Permission approved by operator: run_db_migration
[2025-03-09T14:23:45] [INFO ] ✓ Coding session complete. Report generated.
```

---

## Feature Ideas

### Agent & Orchestration
- **Multi-model routing** — route complex planning to Opus, fast coding tasks to Haiku, default to Sonnet
- **Parallel sessions** — run multiple tickets simultaneously with a configurable concurrency limit
- **Session resume** — checkpoint session state to disk so a crashed session can be replayed from the last completed step
- **Dependency graph** — detect when ticket B blocks ticket A and hold B until A is done
- **Ticket scoring** — manager agent assigns a complexity score (1–13); used to estimate session duration and alert on outliers
- **Auto-retry** — on soft failures (lint errors, test failures) the coder agent retries up to N times before escalating to blocked
- **Pre-session dry-run** — run a planning pass before starting, show the operator what steps will be taken and what permissions will be needed upfront
- **Rollback support** — on session failure, automatically revert branch and workspace to pre-session state
- **Cost tracking** — track Claude API token usage per session and surface it in the report and dashboard

### Integrations
- **GitHub / GitLab** — auto-open PRs when a session lands, post report as PR description
- **Slack / Discord notifications** — alert on permission required, session done, or blocked tickets
- **Linear** — alternative to YouTrack with the same sync pattern
- **Jira** — same
- **Dataview (Obsidian)** — auto-generate a Dataview query block in the exported kanban for cross-tag filtering
- **CI/CD webhooks** — receive build results back into the dashboard; auto-promote `testing` → `done` on green CI
- **VSCode extension** — show session status and permission alerts directly in the editor

### Dashboard
- **Timeline view** — horizontal Gantt-style view of all sessions and their steps over time
- **Permission audit log** — filterable history of every approve/deny action with operator identity
- **Session diff viewer** — show the git diff produced by a session inline in the report modal
- **Keyboard shortcuts** — `A` to approve pending permission, `D` to deny, `Space` to pause simulation
- **Dark/light mode** — system-preference aware
- **Mobile view** — compressed single-column layout for approving permissions on the go
- **Custom stage labels** — let teams rename stages to match their workflow vocabulary

### Ops & Reliability
- **Rate limiting on the API** — prevent dashboard spam-clicking from hammering the agent
- **Graceful shutdown** — on SIGTERM, finish current step, park sessions, persist state to disk
- **Health endpoint** — `/health` with session count, pending permissions, and uptime
- **Prometheus metrics** — sessions started/done/failed, permission gate latency, step durations
- **Structured logging** — emit JSON logs to stdout for ingestion by Datadog, Loki, etc.

---

## Open Concerns

### Security
- **Permission gate bypass** — the `/permissions/{id}/approve` endpoint must be protected by auth; anyone with network access can currently approve elevated actions
- **Prompt injection** — ticket titles and descriptions from YouTrack go directly into agent prompts; a malicious ticket could manipulate agent behavior
- **Secrets in context** — the session context object is stored in memory and broadcast over WebSocket; it must not contain API keys or credentials
- **Git credentials** — SSH keys or tokens used to clone/push repos must be isolated per session and not logged
- **Workspace isolation** — sessions share the same filesystem; a runaway session could read or overwrite another session's workspace

### Reliability
- **In-memory store is ephemeral** — all state is lost on server restart; needs Postgres or SQLite persistence before production use
- **asyncio.Event leaks** — if a session is cancelled mid-gate but the event is not cleaned up, it will stay in `_perm_events` forever
- **Long-running sessions** — a session with many slow steps may exhaust the asyncio event loop if not properly yielding; real agent calls must be fully async
- **WebSocket reconnect** — the frontend receives a full `init` snapshot on connect but must handle out-of-order messages if it reconnects mid-session
- **Concurrent session limit** — no back-pressure mechanism currently; 50 simultaneous sessions would saturate the Claude API rate limit

### Agent Quality
- **Split quality** — the heuristic ticket-splitting logic is keyword-based; a real LLM call may still produce poorly scoped subtasks that need human review
- **Context window limits** — large codebases may not fit in a single Claude context window; chunking and summarization strategy not yet defined
- **Hallucinated file paths** — the coder agent may reference files that don't exist; needs a verification step before committing
- **Test session false positives** — auto-spawning a test session on every coding session may be wasteful for trivial changes; needs a complexity threshold

### Process
- **Obsidian sync conflicts** — if a human edits `kanban.md` in Obsidian at the same time the backend exports a new version, changes will be overwritten
- **YouTrack status writeback** — writing session hashes back as comments requires YouTrack write permissions and must be idempotent
- **Branch naming collisions** — two sessions for the same ticket (e.g. a retry) will try to create the same branch name

---

## Setup & Running

### Requirements
- Python 3.11+
- Node 18+

### Backend

```bash
cd backend
pip install fastapi uvicorn aiofiles pydantic-settings httpx anthropic

cp .env.example .env
# Fill in YOUTRACK_URL, YOUTRACK_TOKEN, YOUTRACK_PROJECT,
# OBSIDIAN_VAULT, ANTHROPIC_API_KEY
# Set SIMULATE=true to run with seed data and no real API calls

uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `YOUTRACK_URL` | — | Base URL of your YouTrack instance |
| `YOUTRACK_TOKEN` | — | Permanent token with Issues read/write |
| `YOUTRACK_PROJECT` | — | Project short name, e.g. `PROJ` |
| `OBSIDIAN_VAULT` | `./vault` | Absolute path to Obsidian vault root |
| `WORKSPACE_ROOT` | `./sessions` | Where session workspaces are created |
| `LOGS_ROOT` | `./logs` | Where session log files are written |
| `GIT_REMOTE` | — | Fallback git remote when ticket has none |
| `ANTHROPIC_API_KEY` | — | Claude API key |
| `SIMULATE` | `true` | Run with seed data, no real API calls |

---

## Roadmap

```
Phase 1 — Foundation (current)
  ✓ In-memory store + seeded data
  ✓ Session lifecycle with asyncio steps
  ✓ Permission gate (asyncio.Event)
  ✓ WebSocket broadcast
  ✓ Kanban + Stack Lanes dashboard
  ✓ Obsidian markdown export

Phase 2 — Real Integrations
  ○ YouTrack REST sync (read + writeback)
  ○ Obsidian vault scanner + frontmatter parser
  ○ Claude API for manager agent (analysis + splitting)
  ○ Real git operations (clone, branch, commit, push)
  ○ SQLite persistence (drop-in store replacement)

Phase 3 — Production Hardening
  ○ Auth (JWT on REST + WS)
  ○ Postgres + Alembic migrations
  ○ Session checkpointing + resume
  ○ Prometheus metrics + /health
  ○ Graceful shutdown
  ○ Rate limiting + concurrency cap

Phase 4 — Advanced Orchestration
  ○ Parallel sessions with dependency graph
  ○ Multi-model routing
  ○ GitHub PR auto-creation
  ○ CI/CD webhook ingestion
  ○ Cost tracking per session
  ○ Pre-session dry-run + permission preview
```
