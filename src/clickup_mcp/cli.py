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
fields_app = typer.Typer(no_args_is_help=True, help="Custom fields")
app.add_typer(tasks_app, name="tasks")
app.add_typer(comments_app, name="comments")
app.add_typer(fields_app, name="fields")
checklists_app = typer.Typer(no_args_is_help=True, help="Checklist and checklist-item CRUD")
tags_app = typer.Typer(no_args_is_help=True, help="Space tags and task tags")
goals_app = typer.Typer(no_args_is_help=True, help="Goals and key results")
views_app = typer.Typer(no_args_is_help=True, help="Views")
webhooks_app = typer.Typer(no_args_is_help=True, help="Webhooks")
time_app = typer.Typer(no_args_is_help=True, help="Time tracking")

app.add_typer(checklists_app, name="checklists")
app.add_typer(tags_app, name="tags")
app.add_typer(goals_app, name="goals")
app.add_typer(views_app, name="views")
app.add_typer(webhooks_app, name="webhooks")
app.add_typer(time_app, name="time")


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


def _value(raw: str) -> str | int | float | bool | list[str]:
    """Parse a CLI custom-field value: a JSON scalar/string-list if it parses, else the raw string.

    A dropdown option UUID or any plain word is not valid JSON and returns unchanged. A value
    that *does* parse as JSON but is not a supported field shape — an object, ``null``, or a list
    with non-string items — raises rather than silently sending the wrong thing to the API.

    Raises:
        ValueError: If ``raw`` parses as JSON but is not a string, number, boolean, or string list.
    """
    try:
        parsed = json.loads(raw)
    except ValueError:
        return raw
    if isinstance(parsed, bool | int | float | str):
        return parsed
    if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
        return parsed
    raise ValueError(
        f"unsupported --value {raw!r}: pass a string, number, boolean, or list of strings"
    )


@app.command()
def workspaces() -> None:
    """List all workspaces accessible to the API key."""
    _out(ClickUpClient.from_env().list_workspaces())


@app.command()
def members(
    workspace_id: str | None = typer.Option(None, "--workspace-id", "-w"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List all members of a workspace."""
    _out(
        ClickUpClient.from_env().list_members(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


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
    parent: str | None = typer.Option(None, "--parent", help="Parent task id (creates a subtask)."),
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
            parent=parent,
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


@fields_app.command("list")
def fields_list(
    list_id: str | None = typer.Option(None, "--list-id"),
    folder_id: str | None = typer.Option(None, "--folder-id"),
    space_id: str | None = typer.Option(None, "--space-id"),
    workspace_id: str | None = typer.Option(None, "--workspace-id", "-w"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List custom fields at one scope (list/folder/space/workspace are not hierarchical)."""
    _out(
        ClickUpClient.from_env().list_custom_fields(
            list_id=list_id,
            folder_id=folder_id,
            space_id=space_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@fields_app.command("set")
def fields_set(
    task_id: str = typer.Argument(...),
    field_id: str = typer.Option(..., "--field-id", "-f"),
    value: str = typer.Option(..., "--value", help="Dropdown option UUID, or JSON for other types"),
) -> None:
    """Set a custom field value on a task.

    For a dropdown, pass the option's UUID id. `--value` is parsed as JSON when possible
    (so `42`, `1.5`, `["id1","id2"]` work), falling back to the raw string otherwise.
    """
    _out(ClickUpClient.from_env().set_custom_field_value(task_id, field_id, _value(value)))


def main() -> None:
    """CLI entry point: run the typer app, mapping `ValueError` to a JSON error + exit 1."""
    try:
        app()
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)


@app.command("whoami")
def cli_get_authorized_user() -> None:
    """Return the ClickUp user associated with the configured API key."""
    _out(ClickUpClient.from_env().get_authorized_user())


@app.command("space")
def cli_get_space(
    space_id: str = typer.Argument(...),
) -> None:
    """Get a single space by id."""
    _out(ClickUpClient.from_env().get_space(space_id))


@app.command("space-create")
def cli_create_space(
    name: str = typer.Option(..., "--name"),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Create a new space in a workspace."""
    _out(
        ClickUpClient.from_env().create_space(
            name=name, workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@app.command("space-update")
def cli_update_space(
    space_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    color: str | None = typer.Option(None, "--color"),
    private: bool | None = typer.Option(None, "--private/--no-private"),
) -> None:
    """Update a space. Pass only the fields to change."""
    _out(ClickUpClient.from_env().update_space(space_id, name=name, color=color, private=private))


@app.command("space-delete")
def cli_delete_space(
    space_id: str = typer.Argument(...),
) -> None:
    """Permanently delete a space."""
    _out(ClickUpClient.from_env().delete_space(space_id))


@app.command("folder")
def cli_get_folder(
    folder_id: str = typer.Argument(...),
) -> None:
    """Get a single folder by id."""
    _out(ClickUpClient.from_env().get_folder(folder_id))


@app.command("folder-create")
def cli_create_folder(
    space_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
) -> None:
    """Create a folder inside a space."""
    _out(ClickUpClient.from_env().create_folder(space_id, name=name))


@app.command("folder-update")
def cli_update_folder(
    folder_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
) -> None:
    """Rename a folder."""
    _out(ClickUpClient.from_env().update_folder(folder_id, name=name))


@app.command("folder-delete")
def cli_delete_folder(
    folder_id: str = typer.Argument(...),
) -> None:
    """Permanently delete a folder."""
    _out(ClickUpClient.from_env().delete_folder(folder_id))


@app.command("list")
def cli_get_list(
    list_id: str = typer.Argument(...),
) -> None:
    """Get a single list by id."""
    _out(ClickUpClient.from_env().get_list(list_id))


@app.command("list-members")
def cli_get_list_members(
    list_id: str = typer.Argument(...),
) -> None:
    """List members who have access to a list."""
    _out(ClickUpClient.from_env().get_list_members(list_id))


@app.command("list-create")
def cli_create_list(
    folder_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    status: str | None = typer.Option(None, "--status"),
    due_date: int | None = typer.Option(None, "--due-date"),
    priority: int | None = typer.Option(None, "--priority"),
    assignee: int | None = typer.Option(None, "--assignee"),
) -> None:
    """Create a list in a folder.

    priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
    """
    _out(
        ClickUpClient.from_env().create_list(
            folder_id,
            name=name,
            status=status,
            due_date=due_date,
            priority=priority,
            assignee=assignee,
        )
    )


@app.command("list-create-space")
def cli_create_folderless_list(
    space_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    status: str | None = typer.Option(None, "--status"),
    due_date: int | None = typer.Option(None, "--due-date"),
    priority: int | None = typer.Option(None, "--priority"),
    assignee: int | None = typer.Option(None, "--assignee"),
) -> None:
    """Create a folderless list in a space.

    priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
    """
    _out(
        ClickUpClient.from_env().create_folderless_list(
            space_id,
            name=name,
            status=status,
            due_date=due_date,
            priority=priority,
            assignee=assignee,
        )
    )


@app.command("list-update")
def cli_update_list(
    list_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    status: str | None = typer.Option(None, "--status"),
    due_date: int | None = typer.Option(None, "--due-date"),
    priority: int | None = typer.Option(None, "--priority"),
) -> None:
    """Update a list. Pass only the fields to change; due_date is Unix ms."""
    _out(
        ClickUpClient.from_env().update_list(
            list_id, name=name, status=status, due_date=due_date, priority=priority
        )
    )


@app.command("list-delete")
def cli_delete_list(
    list_id: str = typer.Argument(...),
) -> None:
    """Permanently delete a list."""
    _out(ClickUpClient.from_env().delete_list(list_id))


@tasks_app.command("members")
def cli_get_task_members(
    task_id: str = typer.Argument(...),
) -> None:
    """List members who are assigned to or watching a task."""
    _out(ClickUpClient.from_env().get_task_members(task_id))


@tasks_app.command("time-in-status")
def cli_get_task_time_in_status(
    task_id: str = typer.Argument(...),
) -> None:
    """Return the time a task has spent in each status."""
    _out(ClickUpClient.from_env().get_task_time_in_status(task_id))


@tasks_app.command("add-dep")
def cli_add_dependency(
    task_id: str = typer.Argument(...),
    depends_on: str | None = typer.Option(None, "--depends-on"),
    dependency_of: str | None = typer.Option(None, "--dependency-of"),
) -> None:
    """Add a dependency between tasks.

    depends_on: this task blocks on that one; dependency_of: that one blocks on this.
    """
    _out(
        ClickUpClient.from_env().add_dependency(
            task_id, depends_on=depends_on, dependency_of=dependency_of
        )
    )


@tasks_app.command("remove-dep")
def cli_remove_dependency(
    task_id: str = typer.Argument(...),
    depends_on: str | None = typer.Option(None, "--depends-on"),
    dependency_of: str | None = typer.Option(None, "--dependency-of"),
) -> None:
    """Remove a dependency. Provide the same depends_on or dependency_of used when adding."""
    _out(
        ClickUpClient.from_env().remove_dependency(
            task_id, depends_on=depends_on, dependency_of=dependency_of
        )
    )


@tasks_app.command("link")
def cli_add_task_link(
    task_id: str = typer.Argument(...),
    links_to: str = typer.Argument(...),
) -> None:
    """Create a link between two tasks."""
    _out(ClickUpClient.from_env().add_task_link(task_id, links_to))


@tasks_app.command("unlink")
def cli_remove_task_link(
    task_id: str = typer.Argument(...),
    links_to: str = typer.Argument(...),
) -> None:
    """Remove a link between two tasks."""
    _out(ClickUpClient.from_env().remove_task_link(task_id, links_to))


@tasks_app.command("move")
def cli_move_task(
    task_id: str = typer.Argument(...),
    list_id: str = typer.Option(..., "--list-id"),
) -> None:
    """Move a task to a different list."""
    _out(ClickUpClient.from_env().move_task(task_id, list_id=list_id))


@checklists_app.command("create")
def cli_create_checklist(
    task_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
) -> None:
    """Create a checklist on a task."""
    _out(ClickUpClient.from_env().create_checklist(task_id, name=name))


@checklists_app.command("update")
def cli_update_checklist(
    checklist_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    position: int | None = typer.Option(None, "--position"),
) -> None:
    """Rename a checklist or change its position."""
    _out(ClickUpClient.from_env().update_checklist(checklist_id, name=name, position=position))


@checklists_app.command("delete")
def cli_delete_checklist(
    checklist_id: str = typer.Argument(...),
) -> None:
    """Delete a checklist."""
    _out(ClickUpClient.from_env().delete_checklist(checklist_id))


@checklists_app.command("item-create")
def cli_create_checklist_item(
    checklist_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    assignee: int | None = typer.Option(None, "--assignee"),
) -> None:
    """Add an item to a checklist."""
    _out(ClickUpClient.from_env().create_checklist_item(checklist_id, name=name, assignee=assignee))


@checklists_app.command("item-update")
def cli_update_checklist_item(
    checklist_id: str = typer.Argument(...),
    checklist_item_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    resolved: bool | None = typer.Option(None, "--resolved/--no-resolved"),
    assignee: int | None = typer.Option(None, "--assignee"),
) -> None:
    """Update a checklist item's name, resolution state, or assignee."""
    _out(
        ClickUpClient.from_env().update_checklist_item(
            checklist_id, checklist_item_id, name=name, resolved=resolved, assignee=assignee
        )
    )


@checklists_app.command("item-delete")
def cli_delete_checklist_item(
    checklist_id: str = typer.Argument(...),
    checklist_item_id: str = typer.Argument(...),
) -> None:
    """Delete a checklist item."""
    _out(ClickUpClient.from_env().delete_checklist_item(checklist_id, checklist_item_id))


@comments_app.command("list-comments")
def cli_list_list_comments(
    list_id: str = typer.Argument(...),
) -> None:
    """List all comments on a list (not on a specific task)."""
    _out(ClickUpClient.from_env().list_list_comments(list_id))


@comments_app.command("list-create")
def cli_create_list_comment(
    list_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text"),
    notify_all: bool = typer.Option(False, "--notify-all/--no-notify-all"),
) -> None:
    """Post a comment on a list; set notify_all to notify all list members."""
    _out(ClickUpClient.from_env().create_list_comment(list_id, text=text, notify_all=notify_all))


@comments_app.command("update")
def cli_update_comment(
    comment_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text"),
) -> None:
    """Edit the text of an existing comment."""
    _out(ClickUpClient.from_env().update_comment(comment_id, text=text))


@comments_app.command("delete")
def cli_delete_comment(
    comment_id: str = typer.Argument(...),
) -> None:
    """Delete a comment."""
    _out(ClickUpClient.from_env().delete_comment(comment_id))


@fields_app.command("clear")
def cli_remove_custom_field_value(
    task_id: str = typer.Argument(...),
    field_id: str = typer.Argument(...),
) -> None:
    """Clear a custom field value on a task."""
    _out(ClickUpClient.from_env().remove_custom_field_value(task_id, field_id))


@tags_app.command("list")
def cli_get_space_tags(
    space_id: str = typer.Argument(...),
) -> None:
    """List all tags defined in a space."""
    _out(ClickUpClient.from_env().get_space_tags(space_id))


@tags_app.command("create")
def cli_create_space_tag(
    space_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    bg_color: str | None = typer.Option(None, "--bg-color"),
    fg_color: str | None = typer.Option(None, "--fg-color"),
) -> None:
    """Create a tag in a space. Colors are hex strings (e.g. '#ff0000')."""
    _out(
        ClickUpClient.from_env().create_space_tag(
            space_id, name=name, bg_color=bg_color, fg_color=fg_color
        )
    )


@tags_app.command("update")
def cli_update_space_tag(
    space_id: str = typer.Argument(...),
    tag_name: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    bg_color: str | None = typer.Option(None, "--bg-color"),
    fg_color: str | None = typer.Option(None, "--fg-color"),
) -> None:
    """Update a space tag's name or colors."""
    _out(
        ClickUpClient.from_env().update_space_tag(
            space_id, tag_name, name=name, bg_color=bg_color, fg_color=fg_color
        )
    )


@tags_app.command("delete")
def cli_delete_space_tag(
    space_id: str = typer.Argument(...),
    tag_name: str = typer.Argument(...),
) -> None:
    """Delete a tag from a space."""
    _out(ClickUpClient.from_env().delete_space_tag(space_id, tag_name))


@tags_app.command("add")
def cli_add_task_tag(
    task_id: str = typer.Argument(...),
    tag_name: str = typer.Argument(...),
) -> None:
    """Add a tag to a task."""
    _out(ClickUpClient.from_env().add_task_tag(task_id, tag_name))


@tags_app.command("remove")
def cli_remove_task_tag(
    task_id: str = typer.Argument(...),
    tag_name: str = typer.Argument(...),
) -> None:
    """Remove a tag from a task."""
    _out(ClickUpClient.from_env().remove_task_tag(task_id, tag_name))


@goals_app.command("list")
def cli_list_goals(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List all goals in a workspace."""
    _out(
        ClickUpClient.from_env().list_goals(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@goals_app.command("get")
def cli_get_goal(
    goal_id: str = typer.Argument(...),
) -> None:
    """Get a single goal by id."""
    _out(ClickUpClient.from_env().get_goal(goal_id))


@goals_app.command("create")
def cli_create_goal(
    name: str = typer.Option(..., "--name"),
    due_date: int | None = typer.Option(None, "--due-date"),
    description: str | None = typer.Option(None, "--description"),
    color: str | None = typer.Option(None, "--color"),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Create a goal in a workspace. due_date is Unix ms."""
    _out(
        ClickUpClient.from_env().create_goal(
            name=name,
            due_date=due_date,
            description=description,
            color=color,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@goals_app.command("update")
def cli_update_goal(
    goal_id: str = typer.Argument(...),
    name: str | None = typer.Option(None, "--name"),
    due_date: int | None = typer.Option(None, "--due-date"),
    description: str | None = typer.Option(None, "--description"),
    color: str | None = typer.Option(None, "--color"),
) -> None:
    """Update a goal. Pass only the fields to change."""
    _out(
        ClickUpClient.from_env().update_goal(
            goal_id, name=name, due_date=due_date, description=description, color=color
        )
    )


@goals_app.command("delete")
def cli_delete_goal(
    goal_id: str = typer.Argument(...),
) -> None:
    """Delete a goal."""
    _out(ClickUpClient.from_env().delete_goal(goal_id))


@goals_app.command("kr-create")
def cli_create_key_result(
    goal_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    type: str = typer.Option(..., "--type"),
    steps_start: int = typer.Option(..., "--steps-start"),
    steps_end: int = typer.Option(..., "--steps-end"),
    unit: str = typer.Option(..., "--unit"),
    task_ids: str | None = typer.Option(None, "--task-ids", help="Comma-separated"),
    list_ids: str | None = typer.Option(None, "--list-ids", help="Comma-separated"),
) -> None:
    """Add a key result to a goal. type: number|currency|boolean|percentage|automatic."""
    _out(
        ClickUpClient.from_env().create_key_result(
            goal_id,
            name=name,
            type=type,
            steps_start=steps_start,
            steps_end=steps_end,
            unit=unit,
            task_ids=task_ids.split(",") if task_ids else None,
            list_ids=list_ids.split(",") if list_ids else None,
        )
    )


@goals_app.command("kr-update")
def cli_update_key_result(
    key_result_id: str = typer.Argument(...),
    steps_current: int = typer.Option(..., "--steps-current"),
    note: str | None = typer.Option(None, "--note"),
) -> None:
    """Update a key result's current progress."""
    _out(
        ClickUpClient.from_env().update_key_result(
            key_result_id, steps_current=steps_current, note=note
        )
    )


@goals_app.command("kr-delete")
def cli_delete_key_result(
    key_result_id: str = typer.Argument(...),
) -> None:
    """Delete a key result."""
    _out(ClickUpClient.from_env().delete_key_result(key_result_id))


@views_app.command("workspace")
def cli_list_workspace_views(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List all views in a workspace."""
    _out(
        ClickUpClient.from_env().list_workspace_views(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@views_app.command("space")
def cli_list_space_views(
    space_id: str = typer.Argument(...),
) -> None:
    """List all views in a space."""
    _out(ClickUpClient.from_env().list_space_views(space_id))


@views_app.command("folder")
def cli_list_folder_views(
    folder_id: str = typer.Argument(...),
) -> None:
    """List all views in a folder."""
    _out(ClickUpClient.from_env().list_folder_views(folder_id))


@views_app.command("list")
def cli_list_list_views(
    list_id: str = typer.Argument(...),
) -> None:
    """List all views in a list."""
    _out(ClickUpClient.from_env().list_list_views(list_id))


@views_app.command("get")
def cli_get_view(
    view_id: str = typer.Argument(...),
) -> None:
    """Get a single view by id."""
    _out(ClickUpClient.from_env().get_view(view_id))


@views_app.command("tasks")
def cli_get_view_tasks(
    view_id: str = typer.Argument(...),
    page: int = typer.Option(0, "--page"),
) -> None:
    """Get tasks visible in a view. Returns one page; increment page to paginate."""
    _out(ClickUpClient.from_env().get_view_tasks(view_id, page=page))


@views_app.command("create")
def cli_create_view(
    list_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    type: str = typer.Option(..., "--type"),
) -> None:
    """Create a view on a list. type: list|board|calendar|table|gantt|activity|workload."""
    _out(ClickUpClient.from_env().create_view(list_id, name=name, type=type))


@views_app.command("update")
def cli_update_view(
    view_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name"),
    type: str = typer.Option(..., "--type"),
) -> None:
    """Update a view's name or type."""
    _out(ClickUpClient.from_env().update_view(view_id, name=name, type=type))


@views_app.command("delete")
def cli_delete_view(
    view_id: str = typer.Argument(...),
) -> None:
    """Delete a view."""
    _out(ClickUpClient.from_env().delete_view(view_id))


@webhooks_app.command("list")
def cli_list_webhooks(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """List all webhooks in a workspace."""
    _out(
        ClickUpClient.from_env().list_webhooks(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@webhooks_app.command("create")
def cli_create_webhook(
    endpoint: str = typer.Option(..., "--endpoint"),
    events: str = typer.Option(..., "--events", help="Comma-separated"),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Register a webhook. events: list of event names, or ['*'] for all events."""
    _out(
        ClickUpClient.from_env().create_webhook(
            endpoint=endpoint,
            events=events.split(","),
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@webhooks_app.command("update")
def cli_update_webhook(
    webhook_id: str = typer.Argument(...),
    endpoint: str | None = typer.Option(None, "--endpoint"),
    events: str | None = typer.Option(None, "--events", help="Comma-separated"),
    status: str | None = typer.Option(None, "--status"),
) -> None:
    """Update a webhook's endpoint URL, subscribed events, or status ('active' | 'inactive')."""
    _out(
        ClickUpClient.from_env().update_webhook(
            webhook_id,
            endpoint=endpoint,
            events=events.split(",") if events else None,
            status=status,
        )
    )


@webhooks_app.command("delete")
def cli_delete_webhook(
    webhook_id: str = typer.Argument(...),
) -> None:
    """Delete a webhook."""
    _out(ClickUpClient.from_env().delete_webhook(webhook_id))


@time_app.command("list")
def cli_get_time_entries(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
    start_date: int | None = typer.Option(None, "--start-date"),
    end_date: int | None = typer.Option(None, "--end-date"),
    assignee: int | None = typer.Option(None, "--assignee"),
    task_id: str | None = typer.Option(None, "--task-id"),
) -> None:
    """Get time entries for a workspace. start_date/end_date are Unix ms timestamps."""
    _out(
        ClickUpClient.from_env().get_time_entries(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            start_date=start_date,
            end_date=end_date,
            assignee=assignee,
            task_id=task_id,
        )
    )


@time_app.command("current")
def cli_get_running_time_entry(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Get the currently running time entry for the workspace, if any."""
    _out(
        ClickUpClient.from_env().get_running_time_entry(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@time_app.command("create")
def cli_create_time_entry(
    start: int = typer.Option(..., "--start"),
    duration: int = typer.Option(..., "--duration"),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
    task_id: str | None = typer.Option(None, "--task-id"),
    description: str | None = typer.Option(None, "--description"),
    billable: bool = typer.Option(False, "--billable/--no-billable"),
) -> None:
    """Manually log a time entry. start is Unix ms; duration is milliseconds."""
    _out(
        ClickUpClient.from_env().create_time_entry(
            start=start,
            duration=duration,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            task_id=task_id,
            description=description,
            billable=billable,
        )
    )


@time_app.command("start")
def cli_start_timer(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
    task_id: str | None = typer.Option(None, "--task-id"),
    description: str | None = typer.Option(None, "--description"),
    billable: bool = typer.Option(False, "--billable/--no-billable"),
) -> None:
    """Start a new timer. Stops any currently running timer."""
    _out(
        ClickUpClient.from_env().start_timer(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            task_id=task_id,
            description=description,
            billable=billable,
        )
    )


@time_app.command("stop")
def cli_stop_timer(
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Stop the currently running timer."""
    _out(
        ClickUpClient.from_env().stop_timer(
            workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


@time_app.command("update")
def cli_update_time_entry(
    time_entry_id: str = typer.Argument(...),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
    start: int | None = typer.Option(None, "--start"),
    duration: int | None = typer.Option(None, "--duration"),
    description: str | None = typer.Option(None, "--description"),
    billable: bool | None = typer.Option(None, "--billable/--no-billable"),
) -> None:
    """Update a time entry. start is Unix ms; duration is ms."""
    _out(
        ClickUpClient.from_env().update_time_entry(
            time_entry_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            start=start,
            duration=duration,
            description=description,
            billable=billable,
        )
    )


@time_app.command("delete")
def cli_delete_time_entry(
    time_entry_id: str = typer.Argument(...),
    workspace_id: str | None = typer.Option(None, "--workspace-id"),
    workspace_name: str | None = typer.Option(None, "--workspace-name"),
) -> None:
    """Delete a time entry."""
    _out(
        ClickUpClient.from_env().delete_time_entry(
            time_entry_id, workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


if __name__ == "__main__":
    main()
