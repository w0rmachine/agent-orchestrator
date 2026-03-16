"""Markdown sync service integrating vault watching and database sync."""
import asyncio
import contextlib
from pathlib import Path

from sqlmodel import Session, delete, select

from backend.config import settings
from backend.database import engine
from backend.models.task import Task, TaskStatus
from backend.models.ai_session import AISession
from backend.models.task_event import TaskEvent
from backend.models.task_path import TaskPath
from backend.sync.markdown_parser import parse_markdown_file
from backend.sync.markdown_writer import generate_markdown
from backend.sync.merge import merge_task, should_delete_task
from backend.sync.vault_watcher import VaultWatcher, compute_file_hash


class SyncService:
    """Bidirectional sync between markdown vault and database."""

    def __init__(self):
        """Initialize sync service."""
        self.vault_path = Path(settings.obsidian_vault_path).expanduser()
        self.watcher: VaultWatcher | None = None
        self._poll_task: asyncio.Task | None = None
        self._last_seen_hash: str = ""
        self._switch_lock = asyncio.Lock()
        self.running = False
        self.syncing = False  # Prevent concurrent syncs

    def _template_content(self) -> str:
        """Default markdown template for new vault files."""
        return "# AI Kanban Dashboard\n\n## RADAR\n\n## RUNWAY\n\n## FLIGHT\n\n## BLOCKED\n\n## DONE\n"

    def _ensure_vault_file(self):
        """Ensure active vault file exists."""
        if not self.vault_path.exists():
            print(f"Creating vault file at {self.vault_path}")
            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            self.vault_path.write_text(self._template_content())

    async def _stop_watchers(self):
        """Stop watcher + polling tasks."""
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        if self.watcher:
            self.watcher.stop()
            self.watcher = None

    def _start_watchers(self):
        """Start watcher + polling tasks for current vault."""
        self.watcher = VaultWatcher(
            str(self.vault_path),
            self._on_vault_changed,
        )
        self.watcher.start()
        self._poll_task = asyncio.create_task(self._poll_for_changes())

    def list_available_vault_files(self) -> list[str]:
        """List available markdown vault files in current vault directory."""
        directory = self.vault_path.parent
        files = sorted(str(p) for p in directory.glob("*.md"))
        current = str(self.vault_path)
        if current not in files:
            files.append(current)
            files.sort()
        return files

    async def switch_vault_file(self, new_path: str):
        """Switch active kanban markdown file and resync context."""
        target = Path(new_path).expanduser()
        if target.suffix.lower() != ".md":
            raise ValueError("Vault file must be a .md file")

        async with self._switch_lock:
            if target == self.vault_path:
                return

            was_running = self.running
            if was_running:
                await self._stop_watchers()

            self.vault_path = target
            self._ensure_vault_file()

            await self._sync_from_vault()
            self._last_seen_hash = compute_file_hash(str(self.vault_path))

            if was_running:
                self._start_watchers()

    async def start(self):
        """Start the sync service."""
        if not settings.enable_sync:
            print("Sync is disabled in settings")
            return

        if self.running:
            return

        # Ensure vault file exists
        self._ensure_vault_file()

        # Do initial sync from vault to DB
        await self._sync_from_vault()
        self._last_seen_hash = compute_file_hash(str(self.vault_path))

        # Start watching for changes
        self._start_watchers()
        self.running = True
        print(f"Sync service started, watching {self.vault_path}")

    async def stop(self):
        """Stop the sync service."""
        await self._stop_watchers()
        self.running = False
        print("Sync service stopped")

    async def _on_vault_changed(self, new_hash: str):
        """Called when vault file changes.

        Args:
            new_hash: New file hash
        """
        print(f"Vault changed (hash: {new_hash[:8]}...), syncing to database")
        self._last_seen_hash = new_hash
        await self._sync_from_vault()

    async def _poll_for_changes(self):
        """Poll file hash as fallback when watchdog events are missed."""
        while True:
            await asyncio.sleep(2.0)
            current_hash = compute_file_hash(str(self.vault_path))
            if current_hash and current_hash != self._last_seen_hash:
                print("Vault changed (poll), syncing to database")
                self._last_seen_hash = current_hash
                await self._sync_from_vault()

    async def _sync_from_vault(self):
        """Sync changes from vault file to database."""
        if self.syncing:
            print("Sync already in progress, skipping")
            return

        self.syncing = True
        try:
            # Parse markdown file
            vault_tasks = parse_markdown_file(str(self.vault_path))
            print(f"Parsed {len(vault_tasks)} tasks from vault")

            # Build lookup by task_code
            vault_tasks_by_code = {t["task_code"]: t for t in vault_tasks if "task_code" in t}

            with Session(engine) as session:
                # Get all existing tasks
                db_tasks = session.exec(select(Task)).all()
                db_tasks_by_code = {t.task_code: t for t in db_tasks}

                # Track processed task codes
                processed_codes = set()

                # Process each vault task
                for md_task in vault_tasks:
                    if "task_code" not in md_task:
                        print(f"Skipping task without code: {md_task.get('title', 'unknown')}")
                        continue

                    task_code = md_task["task_code"]
                    processed_codes.add(task_code)

                    db_task = db_tasks_by_code.get(task_code)

                    # Merge task
                    merged = merge_task(db_task, md_task)

                    if db_task:
                        # Update existing task
                        for key, value in merged.items():
                            if key == "parent_task_code":
                                # Resolve parent task code to ID
                                if value:
                                    parent = db_tasks_by_code.get(value)
                                    if parent:
                                        db_task.parent_task_id = parent.id
                                continue
                            if hasattr(db_task, key):
                                setattr(db_task, key, value)
                    else:
                        # Create new task
                        task_data = merged.copy()

                        # Set defaults for required fields
                        task_data.setdefault("description", "")
                        task_data.setdefault("ai_generated", False)
                        task_data.setdefault("order", 0)

                        # Remove parent_task_code (will be resolved in second pass)
                        parent_code = task_data.pop("parent_task_code", None)

                        new_task = Task(**task_data)
                        session.add(new_task)
                        session.flush()  # Get ID for the new task

                        # Resolve parent if needed
                        if parent_code:
                            parent = db_tasks_by_code.get(parent_code)
                            if parent:
                                new_task.parent_task_id = parent.id

                        db_tasks_by_code[task_code] = new_task

                # Delete tasks that were removed from markdown (if manually created)
                tasks_to_delete = [
                    db_task
                    for task_code, db_task in db_tasks_by_code.items()
                    if task_code not in processed_codes and should_delete_task(db_task)
                ]

                if tasks_to_delete:
                    ids_to_delete = [t.id for t in tasks_to_delete]

                    # Detach kept children from soon-to-be-deleted parents
                    maybe_orphans = session.exec(
                        select(Task).where(Task.parent_task_id.in_(ids_to_delete))  # type: ignore[arg-type]
                    ).all()
                    for orphan in maybe_orphans:
                        if orphan.id not in ids_to_delete:
                            orphan.parent_task_id = None

                    # Delete dependent rows first to satisfy FK constraints
                    session.exec(delete(TaskEvent).where(TaskEvent.task_id.in_(ids_to_delete)))  # type: ignore[arg-type]
                    session.exec(delete(AISession).where(AISession.task_id.in_(ids_to_delete)))  # type: ignore[arg-type]
                    session.exec(delete(TaskPath).where(TaskPath.task_id.in_(ids_to_delete)))  # type: ignore[arg-type]

                    for db_task in tasks_to_delete:
                        print(f"Deleting task removed from markdown: {db_task.task_code}")
                        session.delete(db_task)

                session.commit()
                print(f"Synced {len(processed_codes)} tasks to database")

        finally:
            self.syncing = False

    async def sync_to_vault(self):
        """Sync changes from database to vault file."""
        if not settings.enable_sync:
            return

        if self.syncing:
            print("Sync already in progress, skipping")
            return

        self.syncing = True
        try:
            # Get all tasks from DB
            with Session(engine) as session:
                tasks = session.exec(select(Task)).all()

            # Generate markdown
            markdown = generate_markdown(list(tasks))

            # Write to vault (this will trigger watcher, but hash guard prevents loop)
            self.vault_path.write_text(markdown)
            print(f"Synced {len(tasks)} tasks to vault")

        finally:
            self.syncing = False


# Global sync service instance
sync_service = SyncService()
