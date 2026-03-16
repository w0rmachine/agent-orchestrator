"""
AI-Assisted Task Management
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This module provides AI-powered task management capabilities
for use in dedicated management sessions with Claude.

These tools are meant to be used WITH AI, not by AI directly.
They help humans organize tasks through AI-assisted analysis.
"""

from __future__ import annotations

import os
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel


class TaskAnalysis(BaseModel):
    """Result of AI task analysis."""

    should_split: bool
    suggested_subtasks: list[dict[str, Any]] = []
    suggested_priority: str
    suggested_tags: list[str]
    complexity_score: int  # 1-13 fibonacci
    estimated_hours: float
    reasoning: str


class TaskBatchAnalysis(BaseModel):
    """Result of analyzing multiple tasks."""

    priority_updates: list[dict[str, Any]]
    tag_updates: list[dict[str, Any]]
    suggested_order: list[str]  # task IDs in recommended order
    insights: str


async def analyze_task_complexity(
    title: str,
    description: str,
    tags: list[str] | None = None,
) -> TaskAnalysis:
    """
    Analyze a single task using Claude AI.

    Returns structured analysis including:
    - Whether to split the task
    - Suggested subtasks if splitting
    - Priority recommendation
    - Complexity score
    - Time estimate

    This is meant for management sessions where you want AI help
    breaking down and organizing tasks.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        # Return defaults if no API key
        return TaskAnalysis(
            should_split=False,
            suggested_priority="normal",
            suggested_tags=tags or [],
            complexity_score=5,
            estimated_hours=2.0,
            reasoning="No API key configured - using defaults",
        )

    client = Anthropic(api_key=api_key)

    prompt = f"""Analyze this task for complexity and organization:

Title: {title}
Description: {description}
Current Tags: {', '.join(tags or [])}

Provide a JSON response with:
1. should_split (boolean): Whether this task should be broken into subtasks
2. suggested_subtasks (array): If splitting, list of subtasks with title, description, priority
3. suggested_priority (string): critical|high|normal|low
4. suggested_tags (array): Recommended tags for categorization
5. complexity_score (integer): 1-13 using fibonacci (1=trivial, 13=very complex)
6. estimated_hours (float): Time estimate
7. reasoning (string): Brief explanation of your analysis

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        result = json.loads(response.content[0].text)
        return TaskAnalysis(**result)

    except Exception as e:
        # Fallback to reasonable defaults
        return TaskAnalysis(
            should_split=len(description.split()) > 50,
            suggested_priority="normal",
            suggested_tags=tags or [],
            complexity_score=5,
            estimated_hours=2.0,
            reasoning=f"Analysis failed: {e}. Using defaults.",
        )


async def analyze_task_batch(
    tasks: list[dict[str, Any]],
    goal: str = "Optimize for efficiency and priority",
) -> TaskBatchAnalysis:
    """
    Analyze a batch of tasks for reorganization.

    Useful in management sessions to:
    - Re-prioritize backlog
    - Reorder tasks by dependencies
    - Add consistent tags
    - Identify patterns

    Args:
        tasks: List of task dictionaries with id, title, description, etc.
        goal: What to optimize for (e.g., "critical bugs first", "quick wins")

    Returns:
        Structured recommendations for batch updates
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return TaskBatchAnalysis(
            priority_updates=[],
            tag_updates=[],
            suggested_order=[t["id"] for t in tasks],
            insights="No API key configured",
        )

    client = Anthropic(api_key=api_key)

    # Format tasks for the prompt
    task_list = "\n".join(
        f"[{t['id']}] {t['title']} (priority: {t.get('priority', 'normal')}, "
        f"status: {t.get('status', 'todo')})"
        for t in tasks
    )

    prompt = f"""Analyze these tasks and suggest reorganization:

Goal: {goal}

Tasks:
{task_list}

Provide JSON with:
1. priority_updates: Array of {{task_id, new_priority, reason}}
2. tag_updates: Array of {{task_id, add_tags[], remove_tags[], reason}}
3. suggested_order: Array of task IDs in recommended work order
4. insights: Summary of your analysis and recommendations

Return ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        import json
        result = json.loads(response.content[0].text)
        return TaskBatchAnalysis(**result)

    except Exception as e:
        return TaskBatchAnalysis(
            priority_updates=[],
            tag_updates=[],
            suggested_order=[t["id"] for t in tasks],
            insights=f"Analysis failed: {e}",
        )


def format_analysis_for_display(analysis: TaskAnalysis) -> str:
    """Format task analysis for human-readable display."""
    result = f"""
📊 Task Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Priority: {analysis.suggested_priority.upper()}
Complexity: {analysis.complexity_score}/13 (fibonacci scale)
Estimated Time: {analysis.estimated_hours} hours

Tags: {', '.join(f'#{tag}' for tag in analysis.suggested_tags)}

Reasoning:
{analysis.reasoning}
"""

    if analysis.should_split:
        result += f"\n⚠️  Recommendation: SPLIT THIS TASK\n\n"
        result += f"Suggested subtasks ({len(analysis.suggested_subtasks)}):\n"
        for i, subtask in enumerate(analysis.suggested_subtasks, 1):
            result += f"\n{i}. {subtask['title']}\n"
            if subtask.get('description'):
                result += f"   {subtask['description']}\n"

    return result


def format_batch_analysis_for_display(analysis: TaskBatchAnalysis) -> str:
    """Format batch analysis for human-readable display."""
    result = f"""
📈 Batch Analysis Results
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{analysis.insights}

"""

    if analysis.priority_updates:
        result += f"\n🔴 Priority Updates ({len(analysis.priority_updates)}):\n"
        for update in analysis.priority_updates:
            result += f"  • {update['task_id']} → {update['new_priority']}\n"
            result += f"    Reason: {update.get('reason', 'N/A')}\n"

    if analysis.tag_updates:
        result += f"\n🏷️  Tag Updates ({len(analysis.tag_updates)}):\n"
        for update in analysis.tag_updates:
            if update.get('add_tags'):
                result += f"  • {update['task_id']} + {', '.join(update['add_tags'])}\n"
            if update.get('remove_tags'):
                result += f"  • {update['task_id']} - {', '.join(update['remove_tags'])}\n"

    result += f"\n📋 Recommended Order:\n"
    for i, task_id in enumerate(analysis.suggested_order[:10], 1):
        result += f"  {i}. {task_id}\n"

    if len(analysis.suggested_order) > 10:
        result += f"  ... and {len(analysis.suggested_order) - 10} more\n"

    return result
