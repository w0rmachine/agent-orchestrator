#!/usr/bin/env python3
"""AI Kanban CLI - Terminal-first task management.

Usage:
    kanban next                    # Recommend best task for current repo
    kanban focus                   # Move top recommended task to Flight
    kanban done TASK-012           # Mark task as done
    kanban move TASK-012 runway    # Move task to a column
    kanban log                     # Show recent activity (placeholder)
    kanban env list                # List environments
    kanban env add                 # Register current repo as environment
    kanban split TASK-012          # Manually trigger AI split
"""
import subprocess
import sys
from pathlib import Path

import typer
from rich import print
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="AI Kanban CLI - Terminal-first task management")
console = Console()

API_BASE = "http://localhost:8000"


def get_current_repo() -> str | None:
    """Get current git repository path using git rev-parse.

    Returns:
        Absolute path to git repository root, or None if not in a repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def call_mcp_tool(tool: str, arguments: dict) -> dict:
    """Call an MCP tool via HTTP.

    Args:
        tool: Tool name
        arguments: Tool arguments

    Returns:
        Tool result
    """
    import httpx

    response = httpx.post(
        f"{API_BASE}/mcp/tools/call",
        json={"tool": tool, "arguments": arguments},
        timeout=30.0,
    )

    if response.status_code != 200:
        console.print(f"[red]Error: {response.status_code}[/red]")
        sys.exit(1)

    data = response.json()

    if data.get("error"):
        console.print(f"[red]Tool error: {data['error']}[/red]")
        sys.exit(1)

    return data["result"]


@app.command()
def next(
    energy: str = typer.Option("medium", help="Energy level (low/medium/high)"),
    location: str = typer.Option("anywhere", help="Location (home/work/anywhere)"),
):
    """Recommend best next task for current context."""
    repo_path = get_current_repo()

    result = call_mcp_tool(
        "get_recommended_next_task",
        {
            "energy_level": energy,
            "location": location,
            "repo_path": repo_path,
        },
    )

    task = result.get("recommended_task")

    if not task:
        console.print("[yellow]No tasks available.[/yellow]")
        return

    console.print("\n[bold cyan]Best task now:[/bold cyan]\n")
    console.print(f"[bold]{task['task_code']}[/bold] — {task['title']}")
    console.print(f"[dim]Status: {task['status']}[/dim]")

    if task.get("estimated_minutes"):
        hours = task["estimated_minutes"] // 60
        mins = task["estimated_minutes"] % 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        console.print(f"[dim]Estimated time: {time_str}[/dim]")

    if task.get("priority"):
        console.print(f"[dim]Priority: {task['priority']}/5[/dim]")

    console.print(f"\n[dim]{result['reason']}[/dim]\n")


@app.command()
def focus():
    """Move top recommended task to Flight status."""
    repo_path = get_current_repo()

    # Get recommendation
    result = call_mcp_tool(
        "get_recommended_next_task",
        {
            "energy_level": "medium",
            "location": "anywhere",
            "repo_path": repo_path,
        },
    )

    task = result.get("recommended_task")

    if not task:
        console.print("[yellow]No tasks available to focus on.[/yellow]")
        return

    # Move to flight
    move_result = call_mcp_tool(
        "move_task",
        {"task_code": task["task_code"], "status": "flight"},
    )

    console.print(f"\n[bold green]✓[/bold green] Moved {move_result['task_code']} to FLIGHT\n")
    console.print(f"[bold]{task['title']}[/bold]")


@app.command()
def done(task_code: str):
    """Mark task as done."""
    result = call_mcp_tool("mark_done", {"task_code": task_code})

    console.print(f"\n[bold green]✓[/bold green] Marked {result['task_code']} as DONE\n")


@app.command()
def move(task_code: str, status: str):
    """Move task to a different status column."""
    valid_statuses = ["radar", "runway", "flight", "blocked", "done"]

    if status not in valid_statuses:
        console.print(f"[red]Invalid status. Must be one of: {', '.join(valid_statuses)}[/red]")
        sys.exit(1)

    result = call_mcp_tool("move_task", {"task_code": task_code, "status": status})

    console.print(
        f"\n[bold green]✓[/bold green] Moved {result['task_code']} "
        f"from {result['old_status']} → {result['new_status']}\n"
    )


@app.command()
def log():
    """Show recent AI activity log."""
    result = call_mcp_tool("get_ai_activity", {"limit": 20})

    console.print("[yellow]Activity log not yet fully implemented.[/yellow]")
    console.print(f"[dim]{result.get('note', '')}[/dim]")


@app.command()
def split(task_code: str):
    """Manually trigger AI split on a task."""
    result = call_mcp_tool("split_task", {"task_code": task_code})

    console.print(f"\n[bold cyan]AI analysis queued for {result['task_code']}[/bold cyan]")
    console.print(f"[dim]Job ID: {result['job_id']}[/dim]\n")


env_app = typer.Typer(help="Environment management commands")
app.add_typer(env_app, name="env")


@env_app.command("list")
def env_list():
    """List all registered environments."""
    result = call_mcp_tool("list_environments", {})

    environments = result.get("environments", [])

    if not environments:
        console.print("[yellow]No environments registered yet.[/yellow]")
        return

    table = Table(title="Registered Environments")
    table.add_column("Name", style="cyan")
    table.add_column("Repo Path", style="dim")
    table.add_column("Tech Stack", style="green")

    for env in environments:
        table.add_row(
            env["name"],
            env["repo_path"],
            ", ".join(env.get("tech_stack", [])),
        )

    console.print(table)


@env_app.command("add")
def env_add(
    name: str = typer.Option(None, help="Environment name"),
):
    """Register current repository as an environment."""
    repo_path = get_current_repo()

    if not repo_path:
        console.print("[red]Not in a git repository.[/red]")
        sys.exit(1)

    if not name:
        name = Path(repo_path).name

    import httpx

    response = httpx.post(
        f"{API_BASE}/environments/",
        json={
            "name": name,
            "repo_path": repo_path,
            "tech_stack": [],
        },
    )

    if response.status_code == 201:
        console.print(f"\n[bold green]✓[/bold green] Registered environment: {name}\n")
        console.print(f"[dim]Path: {repo_path}[/dim]\n")
    else:
        console.print(f"[red]Error: {response.status_code}[/red]")


if __name__ == "__main__":
    app()
