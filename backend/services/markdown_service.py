"""Markdown sync service.

Orchestrates parsing, writing, and syncing of Obsidian markdown files.
"""
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from backend.models.task import Task, TaskStatus
from backend.sync.markdown_parser import parse_markdown_file
from backend.sync.markdown_writer import generate_markdown
from backend.sync.merge import merge_task, should_delete_task


class IDGenerator:
    """Generate task IDs in TASK-NNN format."""

    def __init__(self, session: Session):
        """Initialize ID generator.

        Args:
            session: Database session
        """
        self.session = session
        self._next_id: int | None = None

    def _get_next_id(self) -> int:
        """Get next available ID number.

        Returns:
            Next ID number
        """
        if self._next_id is None:
            # Find highest existing ID
            tasks = self.session.exec(select(Task)).all()
            max_id = 0

            for task in tasks:
                # Extract number from TASK-NNN or TASK-NNN-X format
                match = re.match(r"TASK-(\d+)", task.task_code)
                if match:
                    task_num = int(match.group(1))
                    max_id = max(max_id, task_num)

            self._next_id = max_id + 1

        return self._next_id

    def generate(self) -> str:
        """Generate next task ID.

        Returns:
            Task ID in TASK-NNN format
        """
        next_id = self._get_next_id()
        self._next_id = next_id + 1
        return f"TASK-{next_id:03d}"

    def generate_subtask(self, parent_code: str, index: int) -> str:
        """Generate subtask ID.

        Args:
            parent_code: Parent task code (e.g., "TASK-001")
            index: Subtask index (0-based)

        Returns:
            Subtask ID in TASK-NNN-X format
        """
        # Convert index to letter (0=A, 1=B, etc.)
        letter = chr(ord("A") + index)
        return f"{parent_code}-{letter}"


class MarkdownSyncService:
    """Service for syncing markdown files with database."""

    def __init__(self, session: Session):
        """Initialize markdown sync service.

        Args:
            session: Database session
        """
        self.session = session
        self.id_gen = IDGenerator(session)

    def sync_from_file(self, filepath: str) -> dict[str, int]:
        """Sync tasks from markdown file to database.

        Args:
            filepath: Path to markdown file

        Returns:
            Dictionary with sync statistics:
            {
                'added': int,
                'updated': int,
                'deleted': int,
            }
        """
        # Parse markdown file
        md_tasks = parse_markdown_file(filepath)

        # Get all existing tasks from database
        db_tasks = self.session.exec(select(Task)).all()
        db_tasks_by_code = {t.task_code: t for t in db_tasks}

        # Track seen task codes
        seen_codes = set()

        stats = {"added": 0, "updated": 0, "deleted": 0}

        # Process tasks from markdown
        for md_task in md_tasks:
            task_code = md_task["task_code"]
            seen_codes.add(task_code)

            db_task = db_tasks_by_code.get(task_code)

            # Merge task data
            merged_data = merge_task(db_task, md_task)

            if db_task is None:
                # Create new task
                task = Task(
                    task_code=task_code,
                    title=merged_data["title"],
                    status=merged_data["status"],
                    tags=merged_data.get("tags", []),
                    order=merged_data.get("order", 0),
                )

                # Resolve parent task ID from code
                if parent_code := merged_data.get("parent_task_code"):
                    if parent_task := db_tasks_by_code.get(parent_code):
                        task.parent_task_id = parent_task.id

                self.session.add(task)
                stats["added"] += 1
            else:
                # Update existing task
                db_task.title = merged_data["title"]
                db_task.status = merged_data["status"]
                db_task.tags = merged_data.get("tags", [])
                db_task.order = merged_data.get("order", 0)

                self.session.add(db_task)
                stats["updated"] += 1

        # Delete tasks that were removed from markdown
        for db_task in db_tasks:
            if db_task.task_code not in seen_codes and should_delete_task(db_task):
                self.session.delete(db_task)
                stats["deleted"] += 1

        self.session.commit()
        return stats

    def write_to_file(self, filepath: str) -> None:
        """Write tasks from database to markdown file.

        Args:
            filepath: Path to markdown file
        """
        # Get all tasks from database
        tasks = self.session.exec(select(Task)).all()

        # Generate markdown
        markdown = generate_markdown(list(tasks))

        # Write to file
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
