"""ClickUp MCP server — exposes the ClickUp client as FastMCP tools over stdio.

Tool names map 1:1 to ClickUpClient methods, so an MCP host can gate each operation
individually (reads vs. create/update/delete). A single client is built lazily from the
environment on first tool call and reused across the process.

Tools return JSON **text** rather than structured objects: ClickUp responses are large and
free-form, so an output schema adds no value and pydantic cannot derive one from arbitrary
JSON anyway. The model reads the JSON string directly.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from clickup_mcp.client import ClickUpClient, JsonValue

mcp = FastMCP("clickup")

_client: ClickUpClient | None = None


def _api() -> ClickUpClient:
    """Return the process-wide client, building it from the environment on first use."""
    global _client
    if _client is None:
        _client = ClickUpClient.from_env()
    return _client


def _dump(data: JsonValue) -> str:
    """Serialize a JSON value to a compact string for return to the MCP host."""
    return json.dumps(data, indent=2)


@mcp.tool()
def list_workspaces() -> str:
    """List all ClickUp workspaces (teams) accessible to the configured API key."""
    return _dump(_api().list_workspaces())


@mcp.tool()
def list_members(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """List all members of a workspace (defaults to the configured workspace)."""
    return _dump(_api().list_members(workspace_id=workspace_id, workspace_name=workspace_name))


@mcp.tool()
def list_spaces(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """List spaces in a workspace (defaults to the configured workspace)."""
    return _dump(_api().list_spaces(workspace_id=workspace_id, workspace_name=workspace_name))


@mcp.tool()
def list_folders(space_id: str) -> str:
    """List folders in a space."""
    return _dump(_api().list_folders(space_id))


@mcp.tool()
def list_lists(space_id: str | None = None, folder_id: str | None = None) -> str:
    """List lists inside a space or a folder (provide one of them)."""
    return _dump(_api().list_lists(space_id=space_id, folder_id=folder_id))


@mcp.tool()
def search_tasks(
    query: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    list_id: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    due_before: int | None = None,
    due_after: int | None = None,
    page: int = 0,
    include_subtasks: bool = True,
) -> str:
    """Search/filter tasks. With `query`, filters task names client-side (up to 500 tasks).

    Subtasks are included as their own top-level rows by default, so a `query` will also
    match subtask names. Pass `include_subtasks=False` to search only top-level tasks —
    useful when you want a clean list of parent tasks, or when many subtasks would
    otherwise crowd out top-level matches against the 500-task cap.

    Returns `{"tasks": [...], "has_more": bool}`.
    """
    return _dump(
        _api().search_tasks(
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


@mcp.tool()
def get_task(task_id: str, include_subtasks: bool = True) -> str:
    """Get full details of a task by id.

    By default the response includes the task's subtasks under a `subtasks` array, so a
    single call shows the whole subtask tree. Pass `include_subtasks=False` when you only
    need the parent task's own fields (e.g. just its description, status, or assignees)
    and the subtasks would be noise.
    """
    return _dump(_api().get_task(task_id, include_subtasks=include_subtasks))


@mcp.tool()
def create_task(
    list_id: str,
    name: str,
    description: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    assignees: list[int] | None = None,
    due_date: int | None = None,
    parent: str | None = None,
) -> str:
    """Create a task in a list. priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.

    Set `parent` to an existing task id to create the new task as a subtask of it (the
    parent must be in the same `list_id`).
    """
    return _dump(
        _api().create_task(
            list_id,
            name,
            description=description,
            status=status,
            priority=priority,
            assignees=assignees,
            due_date=due_date,
            parent=parent,
        )
    )


@mcp.tool()
def update_task(
    task_id: str,
    name: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: int | None = None,
    add_assignees: list[int] | None = None,
    remove_assignees: list[int] | None = None,
    due_date: int | None = None,
) -> str:
    """Update a task. Pass an empty string to clear a text field; due_date is Unix ms."""
    return _dump(
        _api().update_task(
            task_id,
            name=name,
            description=description,
            status=status,
            priority=priority,
            add_assignees=add_assignees,
            remove_assignees=remove_assignees,
            due_date=due_date,
        )
    )


@mcp.tool()
def delete_task(task_id: str) -> str:
    """Permanently delete a task."""
    return _dump(_api().delete_task(task_id))


@mcp.tool()
def list_comments(task_id: str) -> str:
    """List all comments on a task."""
    return _dump(_api().list_comments(task_id))


@mcp.tool()
def add_comment(task_id: str, text: str, notify_all: bool = False) -> str:
    """Post a comment on a task; set notify_all to notify all task watchers."""
    return _dump(_api().add_comment(task_id, text, notify_all=notify_all))


@mcp.tool()
def list_custom_fields(
    list_id: str | None = None,
    folder_id: str | None = None,
    space_id: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> str:
    """List custom fields at one scope (list/folder/space/workspace).

    Provide one of list_id/folder_id/space_id; with none given, the configured workspace
    (CLICKUP_TEAM_ID) or an explicit workspace_id/workspace_name is used.
    Scopes are NOT hierarchical: each returns only fields defined at that level, so to find
    a task's field, query the list it lives in. For a `drop_down` field, the selectable
    options (each with `id` and `name`) are under `type_config.options`; pass an option's
    `id` to `set_custom_field_value`. ClickUp's API cannot create or edit these options —
    that is UI-only.
    """
    return _dump(
        _api().list_custom_fields(
            list_id=list_id,
            folder_id=folder_id,
            space_id=space_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@mcp.tool()
def set_custom_field_value(
    task_id: str, field_id: str, value: str | int | float | bool | list[str]
) -> str:
    """Set a custom field's value on a task.

    `field_id` is the field's UUID (from `list_custom_fields` or `get_task`). For a
    `drop_down` field, `value` is the chosen option's UUID `id` (the integer `orderindex`
    also works); for text/url/email/phone a string; for number/money a number; for date a
    Unix ms timestamp; for a labels field a list of option ids.
    """
    return _dump(_api().set_custom_field_value(task_id, field_id, value))


@mcp.tool()
def get_authorized_user() -> str:
    """Return the ClickUp user associated with the configured API key."""
    return _dump(_api().get_authorized_user())


@mcp.tool()
def get_space(space_id: str) -> str:
    """Get a single space by id."""
    return _dump(_api().get_space(space_id))


@mcp.tool()
def create_space(
    name: str, workspace_id: str | None = None, workspace_name: str | None = None
) -> str:
    """Create a new space in a workspace."""
    return _dump(
        _api().create_space(name=name, workspace_id=workspace_id, workspace_name=workspace_name)
    )


@mcp.tool()
def update_space(
    space_id: str, name: str | None = None, color: str | None = None, private: bool | None = None
) -> str:
    """Update a space. Pass only the fields to change."""
    return _dump(_api().update_space(space_id, name=name, color=color, private=private))


@mcp.tool()
def delete_space(space_id: str) -> str:
    """Permanently delete a space."""
    return _dump(_api().delete_space(space_id))


@mcp.tool()
def get_folder(folder_id: str) -> str:
    """Get a single folder by id."""
    return _dump(_api().get_folder(folder_id))


@mcp.tool()
def create_folder(space_id: str, name: str) -> str:
    """Create a folder inside a space."""
    return _dump(_api().create_folder(space_id, name=name))


@mcp.tool()
def update_folder(folder_id: str, name: str) -> str:
    """Rename a folder."""
    return _dump(_api().update_folder(folder_id, name=name))


@mcp.tool()
def delete_folder(folder_id: str) -> str:
    """Permanently delete a folder."""
    return _dump(_api().delete_folder(folder_id))


@mcp.tool()
def get_list(list_id: str) -> str:
    """Get a single list by id."""
    return _dump(_api().get_list(list_id))


@mcp.tool()
def get_list_members(list_id: str) -> str:
    """List members who have access to a list."""
    return _dump(_api().get_list_members(list_id))


@mcp.tool()
def create_list(
    folder_id: str,
    name: str,
    status: str | None = None,
    due_date: int | None = None,
    priority: int | None = None,
    assignee: int | None = None,
) -> str:
    """Create a list in a folder.

    priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
    """
    return _dump(
        _api().create_list(
            folder_id,
            name=name,
            status=status,
            due_date=due_date,
            priority=priority,
            assignee=assignee,
        )
    )


@mcp.tool()
def create_folderless_list(
    space_id: str,
    name: str,
    status: str | None = None,
    due_date: int | None = None,
    priority: int | None = None,
    assignee: int | None = None,
) -> str:
    """Create a folderless list in a space.

    priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
    """
    return _dump(
        _api().create_folderless_list(
            space_id,
            name=name,
            status=status,
            due_date=due_date,
            priority=priority,
            assignee=assignee,
        )
    )


@mcp.tool()
def update_list(
    list_id: str,
    name: str | None = None,
    status: str | None = None,
    due_date: int | None = None,
    priority: int | None = None,
) -> str:
    """Update a list. Pass only the fields to change; due_date is Unix ms."""
    return _dump(
        _api().update_list(list_id, name=name, status=status, due_date=due_date, priority=priority)
    )


@mcp.tool()
def delete_list(list_id: str) -> str:
    """Permanently delete a list."""
    return _dump(_api().delete_list(list_id))


@mcp.tool()
def get_task_members(task_id: str) -> str:
    """List members who are assigned to or watching a task."""
    return _dump(_api().get_task_members(task_id))


@mcp.tool()
def get_task_time_in_status(task_id: str) -> str:
    """Return the time a task has spent in each status."""
    return _dump(_api().get_task_time_in_status(task_id))


@mcp.tool()
def add_dependency(
    task_id: str, depends_on: str | None = None, dependency_of: str | None = None
) -> str:
    """Add a dependency between tasks.

    depends_on: this task blocks on that one; dependency_of: that one blocks on this.
    """
    return _dump(_api().add_dependency(task_id, depends_on=depends_on, dependency_of=dependency_of))


@mcp.tool()
def remove_dependency(
    task_id: str, depends_on: str | None = None, dependency_of: str | None = None
) -> str:
    """Remove a dependency. Provide the same depends_on or dependency_of used when adding."""
    return _dump(
        _api().remove_dependency(task_id, depends_on=depends_on, dependency_of=dependency_of)
    )


@mcp.tool()
def add_task_link(task_id: str, links_to: str) -> str:
    """Create a link between two tasks."""
    return _dump(_api().add_task_link(task_id, links_to))


@mcp.tool()
def remove_task_link(task_id: str, links_to: str) -> str:
    """Remove a link between two tasks."""
    return _dump(_api().remove_task_link(task_id, links_to))


@mcp.tool()
def move_task(task_id: str, list_id: str) -> str:
    """Move a task to a different list."""
    return _dump(_api().move_task(task_id, list_id=list_id))


@mcp.tool()
def create_checklist(task_id: str, name: str) -> str:
    """Create a checklist on a task."""
    return _dump(_api().create_checklist(task_id, name=name))


@mcp.tool()
def update_checklist(
    checklist_id: str, name: str | None = None, position: int | None = None
) -> str:
    """Rename a checklist or change its position."""
    return _dump(_api().update_checklist(checklist_id, name=name, position=position))


@mcp.tool()
def delete_checklist(checklist_id: str) -> str:
    """Delete a checklist."""
    return _dump(_api().delete_checklist(checklist_id))


@mcp.tool()
def create_checklist_item(checklist_id: str, name: str, assignee: int | None = None) -> str:
    """Add an item to a checklist."""
    return _dump(_api().create_checklist_item(checklist_id, name=name, assignee=assignee))


@mcp.tool()
def update_checklist_item(
    checklist_item_id: str,
    name: str | None = None,
    resolved: bool | None = None,
    assignee: int | None = None,
) -> str:
    """Update a checklist item's name, resolution state, or assignee."""
    return _dump(
        _api().update_checklist_item(
            checklist_item_id, name=name, resolved=resolved, assignee=assignee
        )
    )


@mcp.tool()
def delete_checklist_item(checklist_item_id: str) -> str:
    """Delete a checklist item."""
    return _dump(_api().delete_checklist_item(checklist_item_id))


@mcp.tool()
def list_list_comments(list_id: str) -> str:
    """List all comments on a list (not on a specific task)."""
    return _dump(_api().list_list_comments(list_id))


@mcp.tool()
def create_list_comment(list_id: str, text: str, notify_all: bool = False) -> str:
    """Post a comment on a list; set notify_all to notify all list members."""
    return _dump(_api().create_list_comment(list_id, text=text, notify_all=notify_all))


@mcp.tool()
def update_comment(comment_id: str, text: str) -> str:
    """Edit the text of an existing comment."""
    return _dump(_api().update_comment(comment_id, text=text))


@mcp.tool()
def delete_comment(comment_id: str) -> str:
    """Delete a comment."""
    return _dump(_api().delete_comment(comment_id))


@mcp.tool()
def remove_custom_field_value(task_id: str, field_id: str) -> str:
    """Clear a custom field value on a task."""
    return _dump(_api().remove_custom_field_value(task_id, field_id))


@mcp.tool()
def get_space_tags(space_id: str) -> str:
    """List all tags defined in a space."""
    return _dump(_api().get_space_tags(space_id))


@mcp.tool()
def create_space_tag(
    space_id: str, name: str, bg_color: str | None = None, fg_color: str | None = None
) -> str:
    """Create a tag in a space. Colors are hex strings (e.g. '#ff0000')."""
    return _dump(_api().create_space_tag(space_id, name=name, bg_color=bg_color, fg_color=fg_color))


@mcp.tool()
def update_space_tag(
    space_id: str,
    tag_name: str,
    name: str | None = None,
    bg_color: str | None = None,
    fg_color: str | None = None,
) -> str:
    """Update a space tag's name or colors."""
    return _dump(
        _api().update_space_tag(space_id, tag_name, name=name, bg_color=bg_color, fg_color=fg_color)
    )


@mcp.tool()
def delete_space_tag(space_id: str, tag_name: str) -> str:
    """Delete a tag from a space."""
    return _dump(_api().delete_space_tag(space_id, tag_name))


@mcp.tool()
def add_task_tag(task_id: str, tag_name: str) -> str:
    """Add a tag to a task."""
    return _dump(_api().add_task_tag(task_id, tag_name))


@mcp.tool()
def remove_task_tag(task_id: str, tag_name: str) -> str:
    """Remove a tag from a task."""
    return _dump(_api().remove_task_tag(task_id, tag_name))


@mcp.tool()
def list_goals(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """List all goals in a workspace."""
    return _dump(_api().list_goals(workspace_id=workspace_id, workspace_name=workspace_name))


@mcp.tool()
def get_goal(goal_id: str) -> str:
    """Get a single goal by id."""
    return _dump(_api().get_goal(goal_id))


@mcp.tool()
def create_goal(
    name: str,
    due_date: int | None = None,
    description: str | None = None,
    color: str | None = None,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> str:
    """Create a goal in a workspace. due_date is Unix ms."""
    return _dump(
        _api().create_goal(
            name=name,
            due_date=due_date,
            description=description,
            color=color,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@mcp.tool()
def update_goal(
    goal_id: str,
    name: str | None = None,
    due_date: int | None = None,
    description: str | None = None,
    color: str | None = None,
) -> str:
    """Update a goal. Pass only the fields to change."""
    return _dump(
        _api().update_goal(
            goal_id, name=name, due_date=due_date, description=description, color=color
        )
    )


@mcp.tool()
def delete_goal(goal_id: str) -> str:
    """Delete a goal."""
    return _dump(_api().delete_goal(goal_id))


@mcp.tool()
def create_key_result(
    goal_id: str,
    name: str,
    type: str,
    steps_start: int,
    steps_end: int,
    unit: str,
    task_ids: list[str] | None = None,
    list_ids: list[str] | None = None,
) -> str:
    """Add a key result to a goal. type: number|currency|boolean|percentage|automatic."""
    return _dump(
        _api().create_key_result(
            goal_id,
            name=name,
            type=type,
            steps_start=steps_start,
            steps_end=steps_end,
            unit=unit,
            task_ids=task_ids,
            list_ids=list_ids,
        )
    )


@mcp.tool()
def update_key_result(key_result_id: str, steps_current: int, note: str | None = None) -> str:
    """Update a key result's current progress."""
    return _dump(_api().update_key_result(key_result_id, steps_current=steps_current, note=note))


@mcp.tool()
def delete_key_result(key_result_id: str) -> str:
    """Delete a key result."""
    return _dump(_api().delete_key_result(key_result_id))


@mcp.tool()
def list_workspace_views(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """List all views in a workspace."""
    return _dump(
        _api().list_workspace_views(workspace_id=workspace_id, workspace_name=workspace_name)
    )


@mcp.tool()
def list_space_views(space_id: str) -> str:
    """List all views in a space."""
    return _dump(_api().list_space_views(space_id))


@mcp.tool()
def list_folder_views(folder_id: str) -> str:
    """List all views in a folder."""
    return _dump(_api().list_folder_views(folder_id))


@mcp.tool()
def list_list_views(list_id: str) -> str:
    """List all views in a list."""
    return _dump(_api().list_list_views(list_id))


@mcp.tool()
def get_view(view_id: str) -> str:
    """Get a single view by id."""
    return _dump(_api().get_view(view_id))


@mcp.tool()
def get_view_tasks(view_id: str, page: int = 0) -> str:
    """Get tasks visible in a view. Returns one page; increment page to paginate."""
    return _dump(_api().get_view_tasks(view_id, page=page))


@mcp.tool()
def create_view(list_id: str, name: str, type: str) -> str:
    """Create a view on a list. type: list|board|calendar|table|gantt|activity|workload."""
    return _dump(_api().create_view(list_id, name=name, type=type))


@mcp.tool()
def update_view(view_id: str, name: str, type: str) -> str:
    """Update a view's name or type."""
    return _dump(_api().update_view(view_id, name=name, type=type))


@mcp.tool()
def delete_view(view_id: str) -> str:
    """Delete a view."""
    return _dump(_api().delete_view(view_id))


@mcp.tool()
def list_webhooks(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """List all webhooks in a workspace."""
    return _dump(_api().list_webhooks(workspace_id=workspace_id, workspace_name=workspace_name))


@mcp.tool()
def create_webhook(
    endpoint: str,
    events: list[str],
    workspace_id: str | None = None,
    workspace_name: str | None = None,
) -> str:
    """Register a webhook. events: list of event names, or ['*'] for all events."""
    return _dump(
        _api().create_webhook(
            endpoint=endpoint,
            events=events,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
        )
    )


@mcp.tool()
def update_webhook(
    webhook_id: str,
    endpoint: str | None = None,
    events: list[str] | None = None,
    status: str | None = None,
) -> str:
    """Update a webhook's endpoint URL, subscribed events, or status ('active' | 'inactive')."""
    return _dump(_api().update_webhook(webhook_id, endpoint=endpoint, events=events, status=status))


@mcp.tool()
def delete_webhook(webhook_id: str) -> str:
    """Delete a webhook."""
    return _dump(_api().delete_webhook(webhook_id))


@mcp.tool()
def get_time_entries(
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    start_date: int | None = None,
    end_date: int | None = None,
    assignee: int | None = None,
    task_id: str | None = None,
) -> str:
    """Get time entries for a workspace. start_date/end_date are Unix ms timestamps."""
    return _dump(
        _api().get_time_entries(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            start_date=start_date,
            end_date=end_date,
            assignee=assignee,
            task_id=task_id,
        )
    )


@mcp.tool()
def get_running_time_entry(
    workspace_id: str | None = None, workspace_name: str | None = None
) -> str:
    """Get the currently running time entry for the workspace, if any."""
    return _dump(
        _api().get_running_time_entry(workspace_id=workspace_id, workspace_name=workspace_name)
    )


@mcp.tool()
def create_time_entry(
    start: int,
    duration: int,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    task_id: str | None = None,
    description: str | None = None,
    billable: bool = False,
) -> str:
    """Manually log a time entry. start is Unix ms; duration is milliseconds."""
    return _dump(
        _api().create_time_entry(
            start=start,
            duration=duration,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            task_id=task_id,
            description=description,
            billable=billable,
        )
    )


@mcp.tool()
def start_timer(
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    task_id: str | None = None,
    description: str | None = None,
    billable: bool = False,
) -> str:
    """Start a new timer. Stops any currently running timer."""
    return _dump(
        _api().start_timer(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            task_id=task_id,
            description=description,
            billable=billable,
        )
    )


@mcp.tool()
def stop_timer(workspace_id: str | None = None, workspace_name: str | None = None) -> str:
    """Stop the currently running timer."""
    return _dump(_api().stop_timer(workspace_id=workspace_id, workspace_name=workspace_name))


@mcp.tool()
def update_time_entry(
    time_entry_id: str,
    workspace_id: str | None = None,
    workspace_name: str | None = None,
    start: int | None = None,
    duration: int | None = None,
    description: str | None = None,
    billable: bool | None = None,
) -> str:
    """Update a time entry. start is Unix ms; duration is ms."""
    return _dump(
        _api().update_time_entry(
            time_entry_id,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            start=start,
            duration=duration,
            description=description,
            billable=billable,
        )
    )


@mcp.tool()
def delete_time_entry(
    time_entry_id: str, workspace_id: str | None = None, workspace_name: str | None = None
) -> str:
    """Delete a time entry."""
    return _dump(
        _api().delete_time_entry(
            time_entry_id, workspace_id=workspace_id, workspace_name=workspace_name
        )
    )


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
