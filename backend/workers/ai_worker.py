"""RQ worker for AI task processing."""
import asyncio
from uuid import UUID

from redis import Redis
from rq import Queue
from sqlmodel import Session, select

from backend.config import settings
from backend.database import engine
from backend.models.environment import Environment
from backend.models.task import Task, TaskStatus
from backend.models.task_event import TaskEvent, TaskEventType
from backend.services.ai_service import classify_and_prioritize_task, split_task_into_subtasks
from backend.services.markdown_service import IDGenerator
from backend.tagging import sanitize_tags

# Initialize Redis and RQ
redis_conn = Redis.from_url(settings.redis_url)
ai_queue = Queue("ai_tasks", connection=redis_conn)


def process_task_ai_analysis(task_id: str) -> dict:
    """Process AI analysis for a task (RQ job).

    This job is triggered when a task moves to Runway status.

    Args:
        task_id: Task ID to analyze

    Returns:
        Dictionary with analysis results
    """
    with Session(engine) as session:
        task = session.get(Task, UUID(task_id))
        if not task:
            return {"error": "Task not found"}

        # Step 1: Classify and prioritize with Haiku
        analysis = asyncio.run(
            classify_and_prioritize_task(
                title=task.title,
                description=task.description,
                tags=task.tags,
            )
        )

        # Update task with AI analysis
        task.priority = analysis["priority"]
        task.estimated_minutes = analysis["estimated_minutes"]
        task.tags = sanitize_tags(task.tags + analysis["suggested_tags"])

        # Log event
        event = TaskEvent(
            task_id=task.id,
            event_type=TaskEventType.TASK_PRIORITIZED,
            event_metadata={
                "priority": task.priority,
                "estimated_minutes": task.estimated_minutes,
                "reasoning": analysis["reasoning"],
            },
        )
        session.add(event)

        # Step 2: Check if task should be split with Sonnet
        environment = None
        if task.environment_id:
            environment = session.get(Environment, task.environment_id)

        env_context = None
        if environment:
            env_context = {
                "name": environment.name,
                "tech_stack": environment.tech_stack,
                "repo_path": environment.repo_path,
            }

        subtasks_data = asyncio.run(
            split_task_into_subtasks(
                title=task.title,
                description=task.description,
                environment_context=env_context,
            )
        )

        # Create subtasks if suggested
        created_subtasks = []
        if subtasks_data:
            id_gen = IDGenerator(session)

            for i, subtask_data in enumerate(subtasks_data):
                # Generate subtask ID
                subtask_code = id_gen.generate_subtask(task.task_code, i)

                subtask = Task(
                    task_code=subtask_code,
                    title=subtask_data["title"],
                    description=subtask_data.get("description", ""),
                    status=TaskStatus.RUNWAY,
                    tags=sanitize_tags(subtask_data.get("tags", [])),
                    estimated_minutes=subtask_data.get("estimated_minutes"),
                    order=task.order + i + 1,
                    parent_task_id=task.id,
                    ai_generated=True,
                    environment_id=task.environment_id,
                )

                session.add(subtask)
                created_subtasks.append(subtask_code)

            # Log split event
            if created_subtasks:
                split_event = TaskEvent(
                    task_id=task.id,
                    event_type=TaskEventType.TASK_SPLIT,
                    event_metadata={
                        "subtasks": created_subtasks,
                        "count": len(created_subtasks),
                    },
                )
                session.add(split_event)

        session.commit()

        return {
            "task_id": str(task.id),
            "task_code": task.task_code,
            "priority": task.priority,
            "estimated_minutes": task.estimated_minutes,
            "subtasks_created": len(created_subtasks),
            "subtask_codes": created_subtasks,
        }


def enqueue_task_analysis(task_id: str) -> str:
    """Enqueue a task for AI analysis.

    Args:
        task_id: Task ID to analyze

    Returns:
        Job ID
    """
    # Deduplicate: check if job already queued for this task
    existing_jobs = ai_queue.get_jobs()
    for job in existing_jobs:
        if job.args and job.args[0] == task_id and job.get_status() in ["queued", "started"]:
            return job.id

    # Enqueue new job
    job = ai_queue.enqueue(
        process_task_ai_analysis,
        task_id,
        job_timeout="5m",
        result_ttl=3600,
    )

    return job.id
