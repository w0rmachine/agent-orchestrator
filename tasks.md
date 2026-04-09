# Agent Orchestrator - Development Roadmap & Tasks

> **Vision**: A developer workflow OS combining Kanban (state) + AI (thinking) + CLI (execution) + Neovim (interface) + Cost-awareness (control)

---

## 🎯 Current State Assessment

### ✅ Already Implemented (Production-Ready)
- **Phase 0**: FastAPI backend, PostgreSQL DB, Docker stack
- **Phase 1**: Full task CRUD, MCP server, REST API, React dashboard, Obsidian sync
- **Phase 2**: AI task analysis (Claude), complexity scoring, time estimation, subtask generation
- **Phase 3** (Partial): Environment/repo tracking, git integration

### 🚧 In Progress
- CLI tool (scaffolded, needs full endpoint wiring)
- Task matching for current repo context
- Focus mode workflow

### ❌ Not Started
- Neovim integration (statusline, commands)
- Cost tracking & optimization
- Local LLM routing (Ollama)
- Autonomous execution features

---

## 📋 PHASE 0 — FOUNDATIONS ✅ [COMPLETE]

All foundational infrastructure is in place and exceeds original spec:
- FastAPI backend with async/await
- PostgreSQL (better than planned SQLite)
- MCP server for Claude Code integration
- Docker Compose dev stack
- React dashboard (bonus)
- Bidirectional Obsidian sync (bonus)

---

## 📋 PHASE 1 — CORE TASK SYSTEM ✅ [95% COMPLETE]

### Data Model ✅
- [x] Task model with all fields (title, description, status, priority, tags, repo_path, estimated_time, etc.)
- [x] SubTask support (parent_task_id hierarchy)
- [x] Task events for activity logging
- [x] Environment model for repo tracking

### API ✅
- [x] POST /tasks (create)
- [x] GET /tasks (list with filters)
- [x] PATCH /tasks/{id} (update)
- [x] DELETE /tasks/{id}
- [x] AI analysis endpoints
- [x] Environment endpoints

### CLI 🚧
- [x] Basic scaffolding exists (`cli/kanban.py`)
- [ ] **T1.1**: Wire CLI commands to API endpoints
  - Priority: HIGH | Estimate: 2h | Tags: #cli #api
  - Commands needed: `add`, `list`, `move`, `done`, `focus`, `next`
  - Use httpx to call FastAPI backend
  - Add config for API URL (default: http://localhost:8000)

- [ ] **T1.2**: Enhance CLI with Rich formatting
  - Priority: MEDIUM | Estimate: 1h | Tags: #cli #ux
  - Use Rich tables for `list` command
  - Add color-coded status indicators
  - Show priority with symbols (🔴🟡🟢)

### TUI (Optional) ✅
- [x] React dashboard already provides visual interface
- [ ] **T1.3**: Add Textual TUI as CLI alternative
  - Priority: LOW | Estimate: 4h | Tags: #cli #tui
  - Textual-based Kanban board
  - Keyboard navigation (vim keys)
  - Column view (RADAR, RUNWAY, FLIGHT, BLOCKED, DONE)

---

## 📋 PHASE 2 — AI INTEGRATION ✅ [COMPLETE]

All AI features implemented and cost-optimized:
- [x] Task breakdown (`split_task` MCP tool)
- [x] Time estimation (AI estimates effort in minutes)
- [x] Task enrichment (complexity, priority suggestions, tags)
- [x] AI outputs stored in DB (no recomputation)
- [x] Structured JSON-only prompts
- [x] Fallback behavior when no API key

---

## 📋 PHASE 3 — REPO AWARENESS + CLI AGENT 🚧 [60% COMPLETE]

### Repo Detection ✅
- [x] Git root detection
- [x] Environment model with repo_path, tech_stack
- [x] Multi-project config support

### Repo Indexing 🚧
- [x] Basic environment tracking
- [ ] **T3.1**: Auto-extract tech stack from repo
  - Priority: MEDIUM | Estimate: 2h | Tags: #repo #ai
  - Parse package.json, requirements.txt, Cargo.toml, go.mod
  - Detect frameworks (React, FastAPI, etc.)
  - Store in environments.tech_stack JSON field
  - Run on `kanban env add <path>`

- [ ] **T3.2**: Index repo file tree
  - Priority: MEDIUM | Estimate: 2h | Tags: #repo
  - Store file tree summary in environment
  - Use gitignore for filtering
  - Update on demand (not automatic - cost!)

### Task Matching 🚧
- [ ] **T3.3**: Implement context-aware task suggestions
  - Priority: HIGH | Estimate: 3h | Tags: #ai #cli
  - `kanban suggest` - show tasks matching current repo
  - Use pwd to detect current environment
  - Filter tasks by environment_id
  - AI ranks by relevance (optional, cached)

### Focus Mode 🚧
- [x] Basic `kanban focus` exists
- [ ] **T3.4**: Implement full AI-assisted focus mode
  - Priority: HIGH | Estimate: 4h | Tags: #ai #workflow
  - Interactive loop: AI suggests → user approves → execute
  - Actions: run command, open file, suggest edit
  - Keep execution manual (don't auto-write code yet)
  - Track session in ai_sessions table
  - Exit on `done`, `skip`, or Ctrl+C

- [ ] **T3.5**: Add safe command execution whitelist
  - Priority: HIGH | Estimate: 1h | Tags: #security
  - Allow: git status, npm test, pytest, make, just
  - Block: rm -rf, sudo, dd, destructive ops
  - Confirm before any command execution

---

## 📋 PHASE 4 — NEOVIM INTEGRATION ❌ [0% COMPLETE]

### Statusline 🎯 (Core Feature)
- [ ] **T4.1**: Create Neovim plugin skeleton
  - Priority: HIGH | Estimate: 2h | Tags: #neovim #plugin
  - Create `nvim/` directory with plugin structure
  - `lua/agent-orchestrator/init.lua`
  - `plugin/agent-orchestrator.vim`
  - README with installation instructions

- [ ] **T4.2**: Implement statusline component
  - Priority: HIGH | Estimate: 3h | Tags: #neovim #statusline
  - Call `kanban stats` via vim.fn.system()
  - Parse JSON response
  - Display: `[Task: Fix Auth] [Open: 12] [Done: 5] [€ Today: 1.32]`
  - Auto-refresh every 30s (configurable)
  - Click to open dashboard (if supported)

- [ ] **T4.3**: Add API endpoint for stats
  - Priority: HIGH | Estimate: 1h | Tags: #api
  - GET /stats endpoint
  - Return: current_task, open_count, done_count, cost_today, cost_session
  - Cache for 5s to avoid hammering on every statusline render

### Commands
- [ ] **T4.4**: Implement Neovim commands
  - Priority: MEDIUM | Estimate: 2h | Tags: #neovim
  - `:WorkFocus` - Trigger focus mode in terminal
  - `:WorkNext` - Show next recommended task
  - `:WorkDone` - Mark current task complete
  - `:WorkList` - Open task list in floating window
  - `:WorkDashboard` - Open browser to React dashboard

### Virtual Text (Bonus)
- [ ] **T4.5**: Show subtasks as virtual text
  - Priority: LOW | Estimate: 3h | Tags: #neovim #ux
  - If file is part of a task, show subtasks as virtual text
  - Use nvim_buf_set_extmark
  - Fade opacity, small font
  - Toggle with `:WorkToggleSubtasks`

---

## 📋 PHASE 5 — LOCAL LLM + COST SYSTEM ❌ [0% COMPLETE]

### Cost Tracking
- [ ] **T5.1**: Create cost tracking model
  - Priority: HIGH | Estimate: 2h | Tags: #ai #cost #db
  - Table: `ai_cost_logs` (timestamp, model, tokens_in, tokens_out, cost_usd)
  - Track every Anthropic API call in ai_manager.py
  - Use tiktoken for token counting
  - Pricing: claude-3.5-sonnet ($3/$15 per 1M tokens)

- [ ] **T5.2**: Implement cost aggregation endpoints
  - Priority: HIGH | Estimate: 1h | Tags: #api #cost
  - GET /cost/today - Daily total
  - GET /cost/session - Current session (reset on restart)
  - GET /cost/history - Last 30 days
  - Return in USD and EUR (use exchange rate API or config)

- [ ] **T5.3**: Add CLI cost commands
  - Priority: MEDIUM | Estimate: 30m | Tags: #cli #cost
  - `kanban cost` - Show today's spending
  - `kanban cost --week` - Weekly report
  - `kanban cost --breakdown` - By operation type

### Ollama Integration
- [ ] **T5.4**: Add Ollama support
  - Priority: MEDIUM | Estimate: 3h | Tags: #ai #ollama
  - Add ollama config to config.yaml (url, model)
  - Create OllamaManager class (mirror anthropic_manager.py)
  - Test with llama3.1, qwen2.5-coder
  - Fallback to Anthropic if Ollama unavailable

- [ ] **T5.5**: Implement AI routing logic
  - Priority: HIGH | Estimate: 2h | Tags: #ai #optimization
  - Route by task type:
    - Local: task breakdown, estimation, simple analysis
    - Cloud: complex reasoning, code generation, multi-step planning
  - Add config option to force cloud/local
  - Log routing decisions for analysis

### Caching Layer
- [ ] **T5.6**: Implement prompt result caching
  - Priority: HIGH | Estimate: 3h | Tags: #ai #cost #redis
  - Hash input: SHA256(prompt + context)
  - Store in Redis with TTL (24h for analysis, 1h for suggestions)
  - Check cache before API call
  - Track cache hit rate in /stats endpoint
  - CLI: `kanban cache clear` to reset

- [ ] **T5.7**: Add cache warming for common queries
  - Priority: LOW | Estimate: 1h | Tags: #ai #optimization
  - Pre-compute analysis for all RUNWAY tasks
  - Run nightly via cron or background worker
  - Configurable: enable/disable cache warming

---

## 📋 PHASE 6 — AUTONOMOUS FEATURES ⚠️ [FUTURE]

> **Warning**: Tread carefully. Automation should enhance, not replace, human judgment.

### Auto-Subtask Execution
- [ ] **T6.1**: Define safe auto-executable task types
  - Priority: LOW | Estimate: 2h | Tags: #autonomous #planning
  - Criteria: trivial, safe, reversible
  - Examples: git status, npm test, linting, type checking
  - Create whitelist in config
  - Require explicit opt-in per task

- [ ] **T6.2**: Implement auto-execution engine
  - Priority: LOW | Estimate: 4h | Tags: #autonomous #execution
  - Check if subtask matches safe patterns
  - Execute in sandboxed env (Docker?)
  - Log all actions to task_events
  - Rollback on failure
  - Never auto-commit or deploy

### Smart Suggestions
- [ ] **T6.3**: Implement repo-aware task suggestions
  - Priority: MEDIUM | Estimate: 3h | Tags: #ai #workflow
  - On `cd` into repo, check for best next task
  - Use git status, recent commits, open files
  - Suggest: "Best next step: Fix API validation"
  - Don't run automatically - only on `kanban suggest`

- [ ] **T6.4**: Add task prioritization AI
  - Priority: LOW | Estimate: 3h | Tags: #ai
  - Analyze all RADAR/RUNWAY tasks
  - Rank by: urgency, dependencies, effort, impact
  - Suggest top 3 tasks
  - Run weekly or on-demand

### Background Agent (Daemon)
- [ ] **T6.5**: Implement optional daemon mode
  - Priority: LOW | Estimate: 5h | Tags: #autonomous #daemon
  - `kanban daemon start` - Run in background
  - Monitor configured repos for changes
  - Suggest tasks on git pull, new files
  - Send notifications (desktop or terminal)
  - Stop with `kanban daemon stop`

- [ ] **T6.6**: Add daemon safety limits
  - Priority: LOW | Estimate: 1h | Tags: #autonomous #safety
  - Rate limit AI calls (max 10/hour)
  - Never modify code without approval
  - Log all suggestions to file
  - Disable by default (opt-in)

---

## 🚫 WHAT NOT TO BUILD (YET)

Resist scope creep. Focus on core workflow first.

- ❌ Full Jira/Linear clone (overkill)
- ❌ Perfect AI autonomy (dangerous)
- ❌ Complex multi-user system (not needed for solo dev)
- ❌ Mobile app (desktop workflow is primary)
- ❌ Real-time collaboration (Obsidian sync is enough)
- ❌ Advanced reporting/analytics (premature)
- ❌ Custom workflow stages (5 phases are enough)
- ❌ Webhook integrations beyond YouTrack (use MCP tools instead)

---

## 🎯 MVP CHECKLIST (Definition of "Done")

You have a production-ready system when:

- [x] Tasks can be created, moved, completed via API
- [x] AI breaks tasks into subtasks
- [x] MCP tools work in Claude Code sessions
- [ ] CLI works inside any repo (context-aware)
- [ ] CLI suggests relevant tasks based on pwd
- [ ] Neovim shows status in statusline
- [ ] Cost tracking works and shows daily spend
- [ ] Local LLM routing reduces costs by 70%+
- [ ] Focus mode helps execute tasks step-by-step

**Current Progress: 6/9 ✅ (67%)**

---

## 🔥 IMMEDIATE NEXT STEPS (Priority Order)

### Week 1: Complete CLI & Context Awareness
1. **T1.1**: Wire CLI to API endpoints (2h)
2. **T3.3**: Context-aware task suggestions (3h)
3. **T3.4**: AI-assisted focus mode (4h)
4. **T1.2**: Rich formatting in CLI (1h)

### Week 2: Neovim Integration
5. **T4.1**: Neovim plugin skeleton (2h)
6. **T4.3**: Stats API endpoint (1h)
7. **T4.2**: Statusline component (3h)
8. **T4.4**: Neovim commands (2h)

### Week 3: Cost Optimization
9. **T5.1**: Cost tracking model (2h)
10. **T5.2**: Cost aggregation API (1h)
11. **T5.6**: Prompt caching with Redis (3h)
12. **T5.4**: Ollama integration (3h)
13. **T5.5**: AI routing logic (2h)

### Week 4: Polish & Testing
14. Test all workflows end-to-end
15. Update documentation
16. Create video demo
17. Ship v1.0

---

## 📊 EFFORT ESTIMATION

| Phase | Tasks Remaining | Estimated Hours | Status |
|-------|----------------|-----------------|--------|
| Phase 0 | 0 | 0h | ✅ Complete |
| Phase 1 | 3 | 7h | 🚧 95% |
| Phase 2 | 0 | 0h | ✅ Complete |
| Phase 3 | 5 | 12h | 🚧 60% |
| Phase 4 | 5 | 11h | ❌ Not started |
| Phase 5 | 7 | 13h | ❌ Not started |
| Phase 6 | 6 | 18h | 💭 Future |
| **Total** | **26** | **61h** | **67% complete** |

---

## 🧠 DESIGN PRINCIPLES (Guiding Star)

1. **CLI-First**: Everything must work without UI
2. **AI is a Tool, Not a Boss**: Always review, always confirm
3. **Cache Everything**: Avoid repeated costs
4. **Context is Expensive**: Send minimal data to AI
5. **Fail Safe**: Never auto-delete, never auto-commit
6. **Offline-Friendly**: Work without internet (local LLM fallback)
7. **Version-Controlled**: Obsidian sync keeps history
8. **Cost-Conscious**: Track every penny, optimize ruthlessly

---

## 📚 ARCHITECTURE DECISIONS

### Why PostgreSQL over SQLite?
- Better concurrency for multi-process access (API + worker + MCP)
- JSON field support for tags and metadata
- Production-ready scaling path

### Why MCP Server?
- Integrates with Claude Code without context-switching
- Works alongside coding, no separate tool needed
- Low cognitive load for ADHD workflow

### Why Obsidian Sync?
- Human-readable, version-controlled task state
- Offline editing with automatic sync
- Familiar markdown format
- Works with existing note-taking workflow

### Why Two-Mode AI?
- **Work Mode**: Fast, no AI overhead for simple tracking
- **Management Mode**: AI assists with complex organization
- User chooses when to pay for intelligence

---

## 🔧 TECH STACK SUMMARY

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI | Async, fast, type-safe |
| Database | PostgreSQL 16 | JSON support, scalable |
| Cache | Redis | Job queue + caching |
| AI (Cloud) | Claude 3.5 Sonnet | Best reasoning |
| AI (Local) | Ollama | Cost optimization |
| CLI | Typer + Rich | Beautiful terminal UX |
| Frontend | React + Vite | Fast, modern |
| Sync | Watchdog | File watching |
| Integration | MCP Protocol | Claude Code native |
| Deployment | Docker Compose | Reproducible dev env |

---

## 📖 RELATED DOCS

- `PROJECT_CONTEXT.md` - Architectural overview
- `backend/README.md` - API documentation
- `cli/README.md` - CLI usage guide
- `nvim/README.md` - Neovim plugin docs (to be created)
- `docs/ROADMAP.md` - Long-term vision

---

## 🎓 LEARNING RESOURCES

If building features from scratch:

- **MCP Protocol**: https://modelcontextprotocol.io/
- **FastAPI Async**: https://fastapi.tiangolo.com/async/
- **SQLModel**: https://sqlmodel.tiangolo.com/
- **Neovim Lua API**: :help lua-guide
- **Ollama API**: https://ollama.ai/docs/api
- **Anthropic SDK**: https://docs.anthropic.com/claude/docs

---

**Last Updated**: 2026-04-09
**Version**: 1.0
**Status**: Living document - update as phases complete

---

## 🚀 LET'S BUILD

This roadmap is your guide, not your prison. Adapt as you learn. Ship early, iterate fast. The goal is a system that **tells you what to do, helps you do it, and knows what it costs**.

Now go build something amazing. 🔥
