"""MCP tool definitions and JSON schemas."""
from typing import Any

# MCP Tool schemas
TOOL_SCHEMAS = {
    "get_tasks_for_repo": {
        "name": "get_tasks_for_repo",
        "description": "Returns all tasks linked to a given repository path",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository",
                }
            },
            "required": ["repo_path"],
        },
    },
    "get_recommended_next_task": {
        "name": "get_recommended_next_task",
        "description": "Recommends best next task given energy, location, and repo context",
        "input_schema": {
            "type": "object",
            "properties": {
                "energy_level": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Current energy level",
                },
                "location": {
                    "type": "string",
                    "enum": ["home", "work", "anywhere"],
                    "description": "Current location",
                },
                "repo_path": {
                    "type": "string",
                    "description": "Optional repository path for context",
                },
            },
            "required": ["energy_level", "location"],
        },
    },
    "move_task": {
        "name": "move_task",
        "description": "Moves a task to a new status column",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_code": {
                    "type": "string",
                    "description": "Task code (e.g., TASK-001)",
                },
                "status": {
                    "type": "string",
                    "enum": ["radar", "runway", "flight", "blocked", "done"],
                    "description": "New status",
                },
            },
            "required": ["task_code", "status"],
        },
    },
    "mark_done": {
        "name": "mark_done",
        "description": "Marks a task as done and logs completion event",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_code": {
                    "type": "string",
                    "description": "Task code (e.g., TASK-001)",
                }
            },
            "required": ["task_code"],
        },
    },
    "add_context": {
        "name": "add_context",
        "description": "Appends a note/context to a task",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_code": {
                    "type": "string",
                    "description": "Task code (e.g., TASK-001)",
                },
                "note": {
                    "type": "string",
                    "description": "Context note to add",
                },
            },
            "required": ["task_code", "note"],
        },
    },
    "split_task": {
        "name": "split_task",
        "description": "Manually triggers AI split on a task",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_code": {
                    "type": "string",
                    "description": "Task code (e.g., TASK-001)",
                }
            },
            "required": ["task_code"],
        },
    },
    "list_environments": {
        "name": "list_environments",
        "description": "Lists all registered environments",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    "get_ai_activity": {
        "name": "get_ai_activity",
        "description": "Returns recent AI log entries",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of entries to return",
                    "default": 50,
                }
            },
        },
    },
}


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Get all MCP tool schemas.

    Returns:
        List of tool schema dictionaries
    """
    return list(TOOL_SCHEMAS.values())


def get_tool_schema(tool_name: str) -> dict[str, Any] | None:
    """Get schema for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Tool schema dictionary or None if not found
    """
    return TOOL_SCHEMAS.get(tool_name)
