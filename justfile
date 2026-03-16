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
	@echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | uv run mcp-server
