# Agent Orchestrator

MCP-based task orchestration system for seamless integration with Claude Code sessions.

## Quick Start

```bash
# Install dependencies
uv sync

# Run the MCP server
just mcp

# Or run directly
uv run mcp-server
```

## What is This?

Agent Orchestrator transforms task management into an MCP server that integrates directly with Claude Code. Instead of managing tasks through a web dashboard, you work with tasks naturally within your Claude sessions.

### Two Modes

**🔨 Work Mode** - Track tasks while coding
Add the MCP to any Claude Code session to:
- Create and track tasks
- Update task status
- Associate tasks with code changes
- No AI overhead, just tracking

**🧠 Management Mode** - AI-assisted organization
Open dedicated sessions for task management:
- Split complex tasks with AI help
- Reorganize priorities
- Add context and tags
- Plan sprints and workflows

## Setup

### 1. Configure Claude Code

Add to your Claude Code settings (`~/.config/claude-code/settings.json`):

```json
{
  "mcpServers": {
    "tasks": {
      "command": "uv",
      "args": ["run", "mcp-server"],
      "cwd": "/path/to/agent-orchestrator",
      "env": {
        "TASK_STORE_PATH": "/path/to/tasks.json"
      }
    }
  }
}
```

Or copy the example config:
```bash
cp .claude-code/settings.example.json .claude-code/settings.json
# Edit with your paths
```

### 2. Start Using

```bash
# In your project directory
claude code

# Available commands in Claude session:
> List all my tasks
> Create a task to implement user authentication
> Start working on task T-ABC123
> Complete task T-ABC123
```

## Documentation

- [**MCP_SETUP.md**](./MCP_SETUP.md) - Complete setup guide and tool reference
- [**IDEA_DUMP.md**](./IDEA_DUMP.md) - Architecture and design decisions (legacy web dashboard)

## Project Structure

```
agent-orchestrator/
├── backend/
│   ├── mcp_server.py       # MCP server implementation ⭐
│   ├── main.py             # FastAPI backend (optional)
│   └── backend_example.py  # Legacy task manager
├── .claude-code/
│   └── settings.example.json
├── tasks.json              # Task persistence
├── MCP_SETUP.md           # Setup guide
└── justfile               # Task runner
```

## Available Tools

### Work Mode (Task Execution)
- `create_task` - Create new tasks
- `list_tasks` - List with filters
- `get_task` - Get task details
- `update_task` - Update any field
- `start_task` - Mark as in_progress
- `complete_task` - Mark as done
- `block_task` - Mark as blocked
- `delete_task` - Remove task

### Management Mode (AI-Assisted)
- `split_task` - Break down complex tasks
- `reorganize_tasks` - Bulk priority/order updates

## Example Workflows

### Daily Coding Session

```
# In project directory
claude code

> List all tasks in progress
> Start task T-123 for implementing OAuth
> [work on the code with Claude]
> Complete task T-123
```

### Weekly Planning

```
# Dedicated management session
claude code

> Show all backlog tasks
> Split the "Database Migration" task into smaller subtasks
> Reorganize all critical tasks by estimated complexity
```

### Context-Rich Task Creation

```
> Create a high-priority task to add rate limiting with context:
  - Files: src/api/middleware.py, tests/test_rate_limit.py
  - Branch: feature/rate-limit
  - Tags: #security #performance
```

## Task Data Model

Tasks are stored as JSON with full metadata:

```json
{
  "id": "T-ABC123",
  "title": "Implement user authentication",
  "description": "Add JWT-based auth",
  "status": "in_progress",
  "priority": "high",
  "tags": ["backend", "security"],
  "context": {
    "repo": "git@github.com:org/app.git",
    "branch": "feature/auth",
    "files": ["src/auth.py"]
  },
  "created": "2025-03-11T10:00:00Z",
  "updated": "2025-03-11T11:30:00Z"
}
```

## Optional Components

### FastAPI Backend

For advanced features (WebSocket, integrations):

```bash
just backend
# Access at http://localhost:8000/docs
```

### Legacy Dashboard

The frontend React dashboard is deprecated but still available:

```bash
just frontend
```

## Configuration

### Environment Variables

- `TASK_STORE_PATH` - Path to tasks.json (default: `./tasks.json`)

### Claude Code Settings

See [MCP_SETUP.md](./MCP_SETUP.md) for detailed configuration options.

## Development

```bash
# Install dependencies
uv sync

# Run MCP server
just mcp

# Test MCP connection
just test-mcp

# Run backend (optional)
just backend
```

## Migration from Web Dashboard

If you were using the old dashboard:

1. Export your tasks
2. Convert to the new JSON format (see `MCP_SETUP.md`)
3. Configure MCP server
4. Remove frontend dependencies

## Troubleshooting

### MCP Server Not Connecting

```bash
# Test directly
just test-mcp

# Check logs
uv run mcp-server 2>&1 | tee mcp.log
```

### Tasks Not Persisting

Verify `TASK_STORE_PATH` and file permissions:
```bash
echo $TASK_STORE_PATH
ls -la ./tasks.json
```

## Why MCP Instead of a Dashboard?

**Before**: Switch between code editor → web dashboard → back to code
**After**: Manage tasks directly in your Claude Code session where you're already working

Benefits:
- No context switching
- AI-assisted task organization when you need it
- Lightweight and fast
- Version control friendly (tasks.json)
- Works offline

## Future Enhancements

- PostgreSQL backend for teams
- Git integration for automatic context
- YouTrack/Jira sync
- Task templates
- Time tracking

## License

[Your License]

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)
