# Quick Start Guide

Get up and running with the Agent Orchestrator MCP server in 5 minutes.

## Step 1: Install

```bash
git clone <your-repo>
cd agent-orchestrator
uv sync
```

## Step 2: Configure Claude Code

Create or edit `~/.config/claude-code/settings.json`:

```json
{
  "mcpServers": {
    "tasks": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/agent-orchestrator", "mcp-server"],
      "env": {
        "TASK_STORE_PATH": "/absolute/path/to/agent-orchestrator/tasks.json"
      }
    }
  }
}
```

**Important**: Replace `/absolute/path/to/agent-orchestrator` with your actual path!

## Step 3: (Optional) Set up AI Analysis

If you want AI-assisted task management, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or add it to your Claude Code MCP configuration:

```json
{
  "mcpServers": {
    "tasks": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/agent-orchestrator", "mcp-server"],
      "env": {
        "TASK_STORE_PATH": "/path/to/tasks.json",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## Step 4: Test It

```bash
# Start Claude Code
claude code

# In the session, try:
> List all tasks
> Create a task to implement OAuth authentication
> Show me task details for the task you just created
```

## Usage Patterns

### Work Session (Task Tracking)

Open Claude Code in your project and work normally. Use the MCP tools to track what you're doing:

```
> Create a task to fix the login bug with priority high
> Start task T-ABC123
> [do the work with Claude]
> Complete task T-ABC123
```

### Management Session (AI Planning)

Open a dedicated Claude session for task organization:

```
> List all todo tasks
> Analyze task T-XYZ789 for complexity
> Split task T-XYZ789 based on the analysis
> Analyze my entire backlog with goal: prioritize quick wins
```

## Next Steps

- Read [MCP_SETUP.md](./MCP_SETUP.md) for complete documentation
- Review [README.md](./README.md) for architecture details
- Check [IDEA_DUMP.md](./IDEA_DUMP.md) for advanced concepts

## Troubleshooting

### "No tools available" in Claude session

1. Verify the path in your MCP configuration is absolute
2. Restart Claude Code
3. Check that `uv run mcp-server` works from the command line

### Tasks not persisting

Check that `TASK_STORE_PATH` is set and writable:

```bash
ls -la /path/to/tasks.json
```

### AI analysis not working

Verify your `ANTHROPIC_API_KEY` is set. The MCP server will work without it, but AI-assisted tools will return defaults.

## Common Commands

```bash
# Run MCP server manually
just mcp

# Test MCP connection
just test-mcp

# Run optional FastAPI backend
just backend

# Install dependencies
uv sync
```

That's it! You're ready to use the Agent Orchestrator with Claude Code.
