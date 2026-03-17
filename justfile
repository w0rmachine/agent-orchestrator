# AI Kanban Dashboard - Just Commands
# Usage: just <command>

set shell := ["bash", "-cu"]

# Run the MCP server (for Claude Code sessions)
mcp:
	uv run mcp-server

# Run the FastAPI backend (for state management/persistence)
backend:
	uv run -m uvicorn backend.main:app --reload --port 8000

# Run the frontend dashboard (deprecated - use MCP instead)
frontend:
	cd frontend && npm install
	cd frontend && npm run dev

# Install dependencies
install:
	uv sync

# Test the MCP server
test-mcp:
	@echo "Testing MCP server connection..."
	@echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","clientInfo":{"name":"just-test","version":"0.0.0"},"capabilities":{}}}' | uv run mcp-server

# Print the standard live MCP validation prompt for future Codex sessions
mcp-validate-prompt:
	@echo "Validate the agent-orchestrator MCP live using the PROJECT_CONTEXT.md MCP checklist. Create, read, update, filter, complete, block, and delete a temporary task and verify markdown sync expectations."

# Add MCP to Codex using the running container (stdio over podman compose exec)
mcp-add-docker:
	codex mcp add agent-orchestrator -- podman compose exec -T mcp uv run mcp-server

# Add MCP to Codex using docker compose run (stdio; no long-running container)
mcp-add-docker-compose:
	codex mcp add agent-orchestrator -- docker compose run --rm -T mcp uv run mcp-server
