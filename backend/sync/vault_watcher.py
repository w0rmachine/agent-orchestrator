"""Vault watcher with hash guard and debouncing."""
import asyncio
import hashlib
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of file content.

    Args:
        filepath: Path to file

    Returns:
        Hexadecimal hash string
    """
    try:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        return ""


class VaultWatcher:
    """File watcher with hash guard and debouncing.

    Per roadmap:
    - Uses watchdog for file system events (inotify on Linux)
    - Hash guard prevents infinite write loops
    - 500ms debounce window handles multi-pass editors
    """

    def __init__(
        self,
        filepath: str,
        on_change: Callable[[str], None],
        debounce_ms: int = 500,
    ):
        """Initialize vault watcher.

        Args:
            filepath: Path to markdown file to watch
            on_change: Async callback when file changes (receives new hash)
            debounce_ms: Debounce window in milliseconds
        """
        self.filepath = Path(filepath).resolve()
        self.on_change = on_change
        self.debounce_ms = debounce_ms

        self.last_hash: str = compute_file_hash(str(self.filepath))
        self.observer: Observer | None = None
        self._debounce_task: asyncio.Task | None = None
        self._pending_hash: str | None = None

    def start(self):
        """Start watching the file."""
        if self.observer:
            return

        # Ensure parent directory exists
        if not self.filepath.parent.exists():
            raise FileNotFoundError(f"Directory not found: {self.filepath.parent}")

        # Set up watchdog observer
        event_handler = _FileEventHandler(self)
        self.observer = Observer()
        self.observer.schedule(
            event_handler,
            str(self.filepath.parent),
            recursive=False,
        )
        self.observer.start()

    def stop(self):
        """Stop watching the file."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    async def _debounced_trigger(self, new_hash: str):
        """Debounced trigger for file changes.

        Args:
            new_hash: New file hash
        """
        # Cancel existing debounce task
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        # Store pending hash
        self._pending_hash = new_hash

        # Wait for debounce window
        await asyncio.sleep(self.debounce_ms / 1000.0)

        # Trigger callback if hash actually changed
        if self._pending_hash != self.last_hash:
            self.last_hash = self._pending_hash
            await self.on_change(self._pending_hash)

    def _on_file_modified(self):
        """Called when file is modified."""
        # Compute new hash
        new_hash = compute_file_hash(str(self.filepath))

        # Hash guard: skip if unchanged
        if new_hash == self.last_hash:
            return

        # Trigger debounced callback
        asyncio.create_task(self._debounced_trigger(new_hash))


class _FileEventHandler(FileSystemEventHandler):
    """Internal event handler for watchdog."""

    def __init__(self, watcher: VaultWatcher):
        """Initialize event handler.

        Args:
            watcher: Parent VaultWatcher instance
        """
        self.watcher = watcher

    def on_modified(self, event):
        """Called when a file is modified.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        # Check if this is our target file
        if Path(event.src_path).resolve() == self.watcher.filepath:
            self.watcher._on_file_modified()

    def on_created(self, event):
        """Called when a file is created.

        Args:
            event: File system event
        """
        # Treat creation as modification
        self.on_modified(event)
