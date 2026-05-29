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
) -> str:
    """Create a task in a list. priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms."""
    return _dump(
        _api().create_task(
            list_id,
            name,
            description=description,
            status=status,
            priority=priority,
            assignees=assignees,
            due_date=due_date,
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


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
