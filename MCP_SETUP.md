# Agent Orchestrator MCP Server Setup

## Overview

The Agent Orchestrator is now an MCP (Model Context Protocol) server that integrates with Claude Code sessions for task management. This replaces the web dashboard approach with a more seamless AI workflow.

## Two Modes of Operation

### 1. Work Mode (AI-free task tracking)
Open a Claude Code session in your project and add the MCP server to track and work on tasks:

- Create tasks
- List and filter tasks
- Update task status
- Mark tasks as in_progress/done/blocked
- Track task context (files, branches, etc.)

### 2. Management Mode (AI-assisted organization)
Open a dedicated Claude Code session for task management where AI helps you:

- Split complex tasks into subtasks
- Reorganize and prioritize tasks
- Add tags and context
- Analyze task dependencies

## Installation

```bash
# Clone and install
git clone <your-repo>
cd agent-orchestrator
uv sync
```

## Configuration

The MCP server uses a simple JSON file for task persistence:

```bash
# Default location: ./tasks.json
# Override with environment variable:
export TASK_STORE_PATH=/path/to/your/tasks.json
```

## Adding the MCP Server to Claude Code

### Option 1: Local Configuration

Add to your Claude Code configuration file (`~/.config/claude-code/settings.json`):

```json
{
  "mcpServers": {
    "agent-orchestrator": {
      "command": "uv",
      "args": ["run", "mcp-server"],
      "cwd": "/path/to/agent-orchestrator",
      "env": {
        "TASK_STORE_PATH": "/path/to/your/tasks.json"
      }
    }
  }
}
```

### Option 2: Project-Specific Configuration

Create `.claude-code/settings.json` in your project:

```json
{
  "mcpServers": {
    "tasks": {
      "command": "uv",
      "args": ["run", "mcp-server"],
      "cwd": "../agent-orchestrator"
    }
  }
}
```

## Available Tools

### Work Mode Tools (Task Execution)

#### `create_task`
Create a new task
```
Parameters:
- title (required): Task title
- description: Detailed description
- priority: critical|high|normal|low (default: normal)
- tags: Array of tags
- context: Additional context (repo, branch, files, etc.)
```

#### `list_tasks`
List tasks with filters
```
Parameters:
- status: todo|in_progress|done|blocked
- priority: critical|high|normal|low
- tags: Array of tags (matches any)
```

#### `get_task`
Get detailed task information
```
Parameters:
- task_id (required): Task ID
```

#### `update_task`
Update task fields
```
Parameters:
- task_id (required): Task ID
- title: New title
- description: New description
- status: New status
- priority: New priority
- tags: New tags array
- context: Additional context
```

#### `start_task`
Mark task as in_progress
```
Parameters:
- task_id (required): Task ID
```

#### `complete_task`
Mark task as done
```
Parameters:
- task_id (required): Task ID
```

#### `block_task`
Mark task as blocked
```
Parameters:
- task_id (required): Task ID
- reason: Reason for blocking
```

#### `delete_task`
Delete a task permanently
```
Parameters:
- task_id (required): Task ID
```

### Management Mode Tools (AI-Assisted)

#### `split_task`
Split a complex task into subtasks
```
Parameters:
- task_id (required): Parent task ID
- subtasks (required): Array of subtask objects
  - title (required)
  - description
  - priority
```

#### `reorganize_tasks`
Bulk update priorities and ordering
```
Parameters:
- updates (required): Array of update objects
  - task_id (required)
  - priority
  - order
  - tags
```

## Usage Examples

## MCP Live Test Section

After registering the MCP in Codex, run this instruction in a new session:

```text
Validate the agent-orchestrator MCP live using the PROJECT_CONTEXT.md MCP checklist. Create, read, update, filter, complete, block, and delete a temporary task and verify markdown sync expectations.
```

Expected coverage:
- MCP CRUD: `create_task`, `get_task`, `update_task`, `delete_task`
- Workflow helpers: `start_task`, `complete_task`, `block_task`
- Filter behavior: `list_tasks` by status/priority/tags/phase
- Context fields: `phase`, `due_date`, `repo_path`
- No leftover temporary tasks after validation

If sync behavior looks wrong, additionally verify `GET /sync/status` and active Kanban file selection.

### Work Session Example

```bash
# In your project directory with Claude Code
claude code

# In the Claude session:
> List all tasks that are in progress
> Start working on task T-ABC123
> Complete task T-ABC123
```

### Management Session Example

```bash
# Open a dedicated management session
claude code

# In the Claude session:
> Analyze all tasks tagged with #backend and suggest priorities
> Split task T-XYZ789 into smaller subtasks
> Reorganize all critical tasks by complexity
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 Claude Code Session                     │
│                                                         │
│  User ←→ Claude AI ←→ MCP Tools (task management)      │
└────────────────────────┬────────────────────────────────┘
                         │ MCP Protocol (stdio)
┌────────────────────────▼────────────────────────────────┐
│              MCP Server (backend/mcp_server.py)         │
│                                                         │
│  • create_task     • list_tasks    • update_task       │
│  • start_task      • complete_task • block_task        │
│  • split_task      • reorganize_tasks                  │
└────────────────────────┬────────────────────────────────┘
                         │ JSON persistence
┌────────────────────────▼────────────────────────────────┐
│                    tasks.json                           │
│                                                         │
│  Persistent task store with:                           │
│  • Task metadata    • Status tracking                  │
│  • Context data     • Parent/subtask relationships     │
└─────────────────────────────────────────────────────────┘
```

## Task Data Model

```json
{
  "id": "T-ABC123",
  "title": "Implement user authentication",
  "description": "Add JWT-based auth to the API",
  "status": "in_progress",
  "priority": "high",
  "tags": ["backend", "security"],
  "parent_id": null,
  "subtask_ids": [],
  "context": {
    "repo": "git@github.com:org/app.git",
    "branch": "feature/auth",
    "files": ["src/auth.py", "tests/test_auth.py"]
  },
  "created": "2025-03-11T10:00:00Z",
  "updated": "2025-03-11T11:30:00Z",
  "order": 0
}
```

## Workflow Patterns

### Pattern 1: Daily Work Session

```
1. Start Claude Code in your project
2. List tasks: "Show me all tasks in progress"
3. Work on tasks using Claude Code normally
4. Update status: "Mark task T-123 as complete"
```

### Pattern 2: Weekly Planning Session

```
1. Open dedicated management session
2. Review backlog: "List all todo tasks grouped by priority"
3. Organize: "Split the database migration task into subtasks"
4. Prioritize: "Reorganize critical tasks by complexity"
```

### Pattern 3: Context-Rich Tasks

```
# Create task with full context
"Create a task to implement OAuth with the following context:
- Repo: git@github.com:org/auth-service.git
- Branch: feature/oauth
- Related files: src/auth/oauth.py, config/oauth.yaml
- Priority: high
- Tags: #security #backend"
```

## Troubleshooting

### MCP Server Not Connecting

```bash
# Test the server directly
just test-mcp

# Check logs
uv run mcp-server 2>&1 | tee mcp.log
```

### Tasks Not Persisting

```bash
# Check the task store path
echo $TASK_STORE_PATH

# Verify file permissions
ls -la ./tasks.json
```

### Tool Not Available in Claude Session

1. Verify MCP server is configured in Claude Code settings
2. Restart Claude Code
3. Check that the `cwd` path is correct in the configuration

## Optional: FastAPI Backend

The project also includes a FastAPI backend (`backend/main.py`) for more advanced features like:
- WebSocket support
- Session orchestration
- YouTrack/Obsidian integration

To run it:
```bash
just backend
# Access API docs at http://localhost:8000/docs
```

This is optional and not required for basic MCP functionality.

## Migration from Web Dashboard

If you were using the previous web dashboard:

1. Export tasks from the old system
2. Convert to the new JSON format
3. Import into `tasks.json`
4. Configure MCP server
5. Remove frontend dependencies

## Future Enhancements

- [ ] PostgreSQL backend for multi-user setups
- [ ] Git integration for automatic context capture
- [ ] YouTrack/Jira bidirectional sync
- [ ] Task templates and workflows
- [ ] Time tracking and analytics

## Support

For issues or questions:
- Check the [GitHub Issues](https://github.com/your-org/agent-orchestrator/issues)
- Review the MCP protocol docs at [modelcontextprotocol.io](https://modelcontextprotocol.io)
