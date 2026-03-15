# AI Kanban Dashboard - Just Commands
# Usage: just <command>

set shell := ["bash", "-cu"]

# Default recipe to display help
default:
    @just --list

# ── Setup ─────────────────────────────────────────────────────────────────────

# Install all dependencies (backend + frontend)
install:
    @echo "📦 Installing backend dependencies..."
    uv sync
    @echo "📦 Installing frontend dependencies..."
    cd frontend && npm install
    @echo "✓ All dependencies installed"

# Setup environment files
setup-env:
    @echo "⚙️  Setting up environment files..."
    @test -f .env || cp .env.example .env
    @test -f frontend/.env || cp frontend/.env.example frontend/.env
    @echo "✓ Environment files created - edit .env to add your ANTHROPIC_API_KEY"

# Complete first-time setup
setup: install setup-env
    @echo "✓ Setup complete! Run 'just start' to launch the app"

# ── Services ──────────────────────────────────────────────────────────────────

# Start PostgreSQL and Redis with Docker
start-db:
    @echo "🐘 Starting PostgreSQL and Redis..."
    docker compose up -d db redis
    @echo "⏳ Waiting for database to be ready..."
    @sleep 5
    @echo "✓ Database services running"

# Stop Docker services
stop-db:
    @echo "🛑 Stopping database services..."
    docker compose down

# Start the backend API server
start-api:
    @echo "🚀 Starting FastAPI server on http://localhost:8000"
    uv run uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# Start the frontend dev server
start-frontend:
    @echo "🎨 Starting frontend on http://localhost:5173"
    cd frontend && npm run dev

# Start the RQ worker for AI background jobs
start-worker:
    @echo "🤖 Starting AI worker..."
    uv run rq worker ai_tasks --url redis://localhost:6379/0

# Start all services (run in separate terminals)
start: start-db
    @echo ""
    @echo "✓ Database started. Now run in separate terminals:"
    @echo "  Terminal 1: just start-api"
    @echo "  Terminal 2: just start-frontend"
    @echo "  Terminal 3: just start-worker (optional, for AI features)"

# Start backend and frontend together (legacy dev command)
dev:
    just start-api &
    just start-frontend &
    wait

# ── Database ──────────────────────────────────────────────────────────────────

# Run database migrations
migrate:
    @echo "🔄 Running database migrations..."
    uv run alembic upgrade head
    @echo "✓ Database migrated"

# Create a new database migration
migrate-create NAME:
    @echo "📝 Creating migration: {{NAME}}"
    uv run alembic revision --autogenerate -m "{{NAME}}"

# Reset database (WARNING: deletes all data)
db-reset:
    @echo "⚠️  Resetting database..."
    docker compose down -v
    docker compose up -d db redis
    @sleep 5
    uv run alembic upgrade head
    @echo "✓ Database reset complete"

# Open PostgreSQL shell
db-shell:
    docker compose exec db psql -U postgres -d ai_kanban

# ── Development ───────────────────────────────────────────────────────────────

# Run all tests
test:
    @echo "🧪 Running tests..."
    uv run pytest tests/ -v

# Run tests with coverage
test-cov:
    @echo "🧪 Running tests with coverage..."
    uv run pytest tests/ -v --cov=backend --cov-report=html
    @echo "✓ Coverage report: htmlcov/index.html"

# Run backend tests only
test-backend:
    uv run pytest tests/test_tasks_api.py tests/test_markdown_parser.py tests/test_markdown_writer.py -v

# Format code
fmt:
    @echo "🎨 Formatting code..."
    -uv run ruff format backend/ tests/ cli/ 2>/dev/null || echo "Install ruff for formatting"

# Lint code
lint:
    @echo "🔍 Linting code..."
    -uv run ruff check backend/ tests/ cli/ 2>/dev/null || echo "Install ruff for linting"

# ── CLI ───────────────────────────────────────────────────────────────────────

# Show next recommended task
next:
    uv run python -m cli.kanban next

# Focus on next task (move to flight)
focus:
    uv run python -m cli.kanban focus

# List all environments
env-list:
    uv run python -m cli.kanban env list

# Add current repo as environment
env-add NAME="":
    #!/usr/bin/env bash
    if [ -z "{{NAME}}" ]; then
        uv run python -m cli.kanban env add
    else
        uv run python -m cli.kanban env add --name "{{NAME}}"
    fi

# Mark task as done
done TASK:
    uv run python -m cli.kanban done {{TASK}}

# Move task to status
move TASK STATUS:
    uv run python -m cli.kanban move {{TASK}} {{STATUS}}

# Trigger AI split on task
split TASK:
    uv run python -m cli.kanban split {{TASK}}

# ── API ───────────────────────────────────────────────────────────────────────

# Open API documentation
docs:
    @echo "📚 Opening API docs..."
    @command -v open >/dev/null 2>&1 && open http://localhost:8000/docs || xdg-open http://localhost:8000/docs 2>/dev/null || echo "Open http://localhost:8000/docs in your browser"

# Check API health
health:
    @curl -s http://localhost:8000/health | jq '.' 2>/dev/null || curl -s http://localhost:8000/health || echo "API not running. Start with 'just start-api'"

# List all tasks via API
api-tasks:
    @curl -s http://localhost:8000/tasks/ | jq '.' 2>/dev/null || curl -s http://localhost:8000/tasks/

# List all environments via API
api-envs:
    @curl -s http://localhost:8000/environments/ | jq '.' 2>/dev/null || curl -s http://localhost:8000/environments/

# List MCP tools
api-mcp-tools:
    @curl -s -X POST http://localhost:8000/mcp/tools/list | jq '.tools[] | {name, description}' 2>/dev/null || curl -s -X POST http://localhost:8000/mcp/tools/list

# ── Build ─────────────────────────────────────────────────────────────────────

# Build frontend for production
build-frontend:
    @echo "🏗️  Building frontend..."
    cd frontend && npm run build
    @echo "✓ Frontend built to frontend/dist"

# Build Docker images
build-docker:
    @echo "🐳 Building Docker images..."
    docker compose build

# ── Cleanup ───────────────────────────────────────────────────────────────────

# Clean build artifacts
clean:
    @echo "🧹 Cleaning build artifacts..."
    rm -rf frontend/dist
    rm -rf frontend/node_modules
    rm -rf .venv
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @echo "✓ Cleaned"

# Clean Docker volumes (WARNING: deletes all data)
clean-docker:
    @echo "⚠️  Cleaning Docker volumes..."
    docker compose down -v
    @echo "✓ Docker volumes removed"

# Full cleanup
clean-all: clean clean-docker

# ── Logs ──────────────────────────────────────────────────────────────────────

# Show API logs
logs-api:
    docker compose logs -f api

# Show worker logs
logs-worker:
    docker compose logs -f worker

# Show database logs
logs-db:
    docker compose logs -f db

# Show all logs
logs:
    docker compose logs -f

# ── Info ──────────────────────────────────────────────────────────────────────

# Show system status
status:
    @echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    @echo "AI Kanban Dashboard - System Status"
    @echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    @echo ""
    @echo "Docker Services:"
    @docker compose ps 2>/dev/null || echo "  Docker not running"
    @echo ""
    @echo "API Health:"
    @curl -s http://localhost:8000/health >/dev/null 2>&1 && echo "  ✓ API running" || echo "  ✗ API not running"
    @echo ""
    @echo "Frontend:"
    @curl -s http://localhost:5173 >/dev/null 2>&1 && echo "  ✓ Frontend running" || echo "  ✗ Frontend not running"
    @echo ""

# Show quick start guide
guide:
    @echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    @echo "AI Kanban Dashboard - Quick Start Guide"
    @echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    @echo ""
    @echo "1️⃣  First time setup:"
    @echo "   just setup"
    @echo ""
    @echo "2️⃣  Start services:"
    @echo "   just start          # Starts database"
    @echo ""
    @echo "3️⃣  Run migrations (one time):"
    @echo "   just migrate"
    @echo ""
    @echo "4️⃣  Start API (Terminal 1):"
    @echo "   just start-api"
    @echo ""
    @echo "5️⃣  Start frontend (Terminal 2):"
    @echo "   just start-frontend"
    @echo ""
    @echo "6️⃣  Start AI worker (Terminal 3, optional):"
    @echo "   just start-worker"
    @echo ""
    @echo "📍 Access points:"
    @echo "   Frontend:  http://localhost:5173"
    @echo "   API:       http://localhost:8000"
    @echo "   API Docs:  http://localhost:8000/docs"
    @echo ""
    @echo "🔧 Useful commands:"
    @echo "   just next          - Get next recommended task"
    @echo "   just env-list      - List environments"
    @echo "   just test          - Run tests"
    @echo "   just status        - Check system status"
    @echo "   just --list        - See all commands"
    @echo ""
