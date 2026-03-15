"""AI service for task analysis and splitting using Anthropic API."""
import json
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from backend.config import settings

# Initialize Anthropic client
client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def load_prompt(prompt_name: str) -> str:
    """Load prompt template from file.

    Args:
        prompt_name: Name of prompt file (without .md extension)

    Returns:
        Prompt content as string
    """
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.md"
    return prompt_path.read_text(encoding="utf-8")


async def classify_and_prioritize_task(
    title: str,
    description: str,
    tags: list[str],
) -> dict[str, Any]:
    """Classify task and assign priority using Claude Haiku.

    Args:
        title: Task title
        description: Task description
        tags: Existing tags

    Returns:
        Dictionary with:
        - priority: int (1-5)
        - estimated_minutes: int
        - suggested_tags: list[str]
        - reasoning: str
    """
    if not client:
        # Fallback to simple heuristics
        return {
            "priority": 3,
            "estimated_minutes": 60,
            "suggested_tags": tags,
            "reasoning": "AI disabled - using defaults",
        }

    prompt_template = load_prompt("tag_classify")
    prompt = prompt_template.format(
        title=title,
        description=description or "No description provided",
        existing_tags=", ".join(tags) if tags else "None",
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON response
        content = message.content[0].text
        result = json.loads(content)

        return {
            "priority": result.get("priority", 3),
            "estimated_minutes": result.get("estimated_minutes", 60),
            "suggested_tags": result.get("suggested_tags", tags),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception as e:
        # Fallback on error
        return {
            "priority": 3,
            "estimated_minutes": 60,
            "suggested_tags": tags,
            "reasoning": f"AI error: {str(e)}",
        }


async def split_task_into_subtasks(
    title: str,
    description: str,
    environment_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Split a complex task into subtasks using Claude Sonnet.

    Args:
        title: Task title
        description: Task description
        environment_context: Optional environment info (tech stack, repo)

    Returns:
        List of subtask dictionaries:
        [
            {
                "title": str,
                "description": str,
                "tags": list[str],
                "estimated_minutes": int,
                "order": int,
            },
            ...
        ]
    """
    if not client:
        # Don't split if AI is disabled
        return []

    prompt_template = load_prompt("task_split")

    env_info = ""
    if environment_context:
        env_info = f"""
Environment: {environment_context.get('name', 'Unknown')}
Tech Stack: {', '.join(environment_context.get('tech_stack', []))}
Repo: {environment_context.get('repo_path', 'Unknown')}
"""

    prompt = prompt_template.format(
        title=title,
        description=description or "No description provided",
        environment_context=env_info,
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse JSON response
        content = message.content[0].text
        result = json.loads(content)

        subtasks = result.get("subtasks", [])

        # Add order field
        for i, subtask in enumerate(subtasks):
            subtask["order"] = i

        return subtasks
    except Exception as e:
        # Don't split on error
        print(f"AI split error: {e}")
        return []
