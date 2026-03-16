"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, select

from backend.api import ai, environments, tasks
from backend.config import settings
from backend.database import engine
from backend.mcp import router as mcp_router
from backend.models.task import Task
from backend.sync.markdown_parser import parse_markdown_file
from backend.sync.markdown_writer import generate_markdown


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Create database tables
    SQLModel.metadata.create_all(engine)

    # Start markdown sync service
    from backend.sync.sync_service import sync_service
    await sync_service.start()

    yield

    # Stop sync service on shutdown
    await sync_service.stop()


app = FastAPI(
    title="AI Kanban Dashboard",
    description="ADHD-friendly task manager with AI assistance and Obsidian sync",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(tasks.router)
app.include_router(environments.router)
app.include_router(ai.router)
app.include_router(mcp_router.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "AI Kanban Dashboard API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/sync/status")
def sync_status():
    """Get sync and vault file status for frontend warnings."""
    vault_path = Path(settings.obsidian_vault_path).expanduser()
    vault_exists = vault_path.exists()

    parse_error: str | None = None
    parsed_task_count = 0
    if vault_exists:
        try:
            parsed_task_count = len(parse_markdown_file(str(vault_path)))
        except Exception as exc:
            parse_error = str(exc)

    with Session(engine) as session:
        db_task_count = len(session.exec(select(Task)).all())

    return {
        "sync_enabled": settings.enable_sync,
        "vault_path": str(vault_path),
        "vault_exists": vault_exists,
        "parsed_task_count": parsed_task_count,
        "db_task_count": db_task_count,
        "parse_error": parse_error,
    }


@app.post("/sync")
async def trigger_sync():
    """Trigger one sync pass from markdown vault to database."""
    from backend.sync.sync_service import sync_service
    await sync_service._sync_from_vault()
    return {"status": "ok"}


@app.get("/export/obsidian", response_class=PlainTextResponse)
def export_obsidian() -> str:
    """Export current database tasks to Obsidian markdown format."""
    with Session(engine) as session:
        db_tasks = session.exec(select(Task)).all()

    return generate_markdown(list(db_tasks))


# WebSocket manager for broadcasting
class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                await self.disconnect(connection)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates."""
    await manager.connect(websocket)
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "init",
            "message": "Connected to AI Kanban Dashboard",
        })

        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_json({
                "type": "echo",
                "message": data,
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
