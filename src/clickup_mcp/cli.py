"""ClickUp CLI — the same operations as the MCP server, for humans and host scripts.

All commands print JSON to stdout. `ValueError`s raised by the client (API errors,
missing config) are caught and printed as `{"error": "..."}` to stderr with exit code 1.
"""

from __future__ import annotations

import json
import sys

import typer

from clickup_mcp.client import ClickUpClient, JsonValue

app = typer.Typer(no_args_is_help=True, help="ClickUp REST API v2 CLI.")
tasks_app = typer.Typer(no_args_is_help=True, help="Task CRUD and search")
comments_app = typer.Typer(no_args_is_help=True, help="Task comments")
app.add_typer(tasks_app, name="tasks")
app.add_typer(comments_app, name="comments")


def _out(data: JsonValue) -> None:
    typer.echo(json.dumps(data, indent=2))


def _ids(raw: str | None) -> list[int] | None:
    """Parse a comma-separated list of numeric user ids, or None."""
    if not raw:
        return None
    try:
        return [int(part.strip()) for part in raw.split(",")]
    except ValueError as exc:
        raise ValueError("user ids must be comma-separated integers (e.g. 123,456)") from exc


@app.command()
def workspaces() -> None:
    """List all workspaces accessible to the API key."""
    _out(ClickUpClient.from_env().list_workspaces())


@app.command()
def spaces(
    workspace_id: str | None = typer.Option(None, "--workspace-id", "-w"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List spaces in a workspace."""
    _out(
        ClickUpClient.from_env().list_spaces(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@app.command()
def folders(space_id: str = typer.Argument(...)) -> None:
    """List folders in a space."""
    _out(ClickUpClient.from_env().list_folders(space_id))


@app.command()
def lists(
    space_id: str | None = typer.Option(None, "--space-id"),
    folder_id: str | None = typer.Option(None, "--folder-id"),
) -> None:
    """List lists inside a space or folder."""
    _out(ClickUpClient.from_env().list_lists(space_id=space_id, folder_id=folder_id))


@tasks_app.command("search")
def tasks_search(
    query: str | None = typer.Argument(None),
    workspace_id: str | None = typer.Option(None, "--workspace-id", "-w"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
    list_id: str | None = typer.Option(None, "--list-id"),
    status: str | None = typer.Option(None, "--status"),
    assignee: str | None = typer.Option(None, "--assignee"),
    due_before: int | None = typer.Option(None, "--due-before"),
    due_after: int | None = typer.Option(None, "--due-after"),
    page: int = typer.Option(0, "--page"),
    include_subtasks: bool = typer.Option(
        True,
        "--include-subtasks/--no-include-subtasks",
        help="Include subtasks in the result (default: on).",
    ),
) -> None:
    """Search and filter tasks."""
    _out(
        ClickUpClient.from_env().search_tasks(
            query,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            list_id=list_id,
            status=status,
            assignee=assignee,
            due_before=due_before,
            due_after=due_after,
            page=page,
            include_subtasks=include_subtasks,
        )
    )


@tasks_app.command("get")
def tasks_get(
    task_id: str = typer.Argument(...),
    include_subtasks: bool = typer.Option(
        True,
        "--include-subtasks/--no-include-subtasks",
        help="Include subtasks in the result (default: on).",
    ),
) -> None:
    """Get full details of a task by id."""
    _out(ClickUpClient.from_env().get_task(task_id, include_subtasks=include_subtasks))


@tasks_app.command("create")
def tasks_create(
    list_id: str = typer.Option(..., "--list-id", "-l"),
    name: str = typer.Option(..., "--name", "-n"),
    description: str | None = typer.Option(None, "--description", "-d"),
    status: str | None = typer.Option(None, "--status", "-s"),
    priority: int | None = typer.Option(None, "--priority"),
    assignees: str | None = typer.Option(None, "--assignees"),
    due_date: int | None = typer.Option(None, "--due-date"),
) -> None:
    """Create a task in a list."""
    _out(
        ClickUpClient.from_env().create_task(
            list_id,
            name,
            description=description,
            status=status,
            priority=priority,
            assignees=_ids(assignees),
            due_date=due_date,
        )
    )


@tasks_app.command("update")
def tasks_update(
    task_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name", "-n"),
    description: str | None = typer.Option(None, "--description", "-d"),
    status: str | None = typer.Option(None, "--status", "-s"),
    priority: int | None = typer.Option(None, "--priority"),
    add_assignees: str | None = typer.Option(None, "--add-assignees"),
    remove_assignees: str | None = typer.Option(None, "--remove-assignees"),
    due_date: int | None = typer.Option(None, "--due-date"),
) -> None:
    """Update an existing task."""
    _out(
        ClickUpClient.from_env().update_task(
            task_id,
            name=name,
            description=description,
            status=status,
            priority=priority,
            add_assignees=_ids(add_assignees),
            remove_assignees=_ids(remove_assignees),
            due_date=due_date,
        )
    )


@tasks_app.command("delete")
def tasks_delete(task_id: str = typer.Argument(...)) -> None:
    """Permanently delete a task."""
    _out(ClickUpClient.from_env().delete_task(task_id))


@comments_app.command("list")
def comments_list(task_id: str = typer.Argument(...)) -> None:
    """List all comments on a task."""
    _out(ClickUpClient.from_env().list_comments(task_id))


@comments_app.command("create")
def comments_create(
    task_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text", "-t"),
    notify_all: bool = typer.Option(False, "--notify-all/--no-notify-all"),
) -> None:
    """Post a comment on a task."""
    _out(ClickUpClient.from_env().add_comment(task_id, text, notify_all=notify_all))


def main() -> None:
    """CLI entry point: run the typer app, mapping `ValueError` to a JSON error + exit 1."""
    try:
        app()
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
