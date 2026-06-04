"""Code generator for new ClickUp API endpoint wrappers.

Run:  python devtools/gen_api.py
Inserts generated methods inside ClickUpClient, and appends tools/commands
to server.py and cli.py.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent
CLIENT_FILE = ROOT / "src/clickup_mcp/client.py"
SERVER_FILE = ROOT / "src/clickup_mcp/server.py"
CLI_FILE = ROOT / "src/clickup_mcp/cli.py"

# Insertion anchors
CLIENT_ANCHOR = "\n\ndef _resolve_dropdown_fields"
SERVER_ANCHOR = "\n\ndef main() -> None:"
CLI_ANCHOR = 'app.add_typer(fields_app, name="fields")'


@dataclass
class P:
    """One method parameter."""

    name: str
    type: str
    required: bool = True
    default: str = "None"
    kind: str = "body"  # "body" | "query" | "path" | "team"
    cli_flag: str = ""
    body_key: str = ""  # API body/query key when different from param name

    def cli_flag_name(self) -> str:
        return self.cli_flag if self.cli_flag else self.name.replace("_", "-")

    def api_key(self) -> str:
        return self.body_key if self.body_key else self.name

    def is_nullable(self) -> bool:
        return "| None" in self.type or self.type.startswith("None |")


@dataclass
class Endpoint:
    """One ClickUp API endpoint."""

    method: str
    http: str
    path: str
    params: list[P] = field(default_factory=list)
    response_key: str | None = None
    returns_list: bool = False
    doc: str = ""
    cli_group: str = ""
    cli_cmd: str = ""
    needs_team: bool = False
    delete_id_param: str | None = None

    def path_params(self) -> list[P]:
        return [p for p in self.params if p.kind == "path"]

    def body_params(self) -> list[P]:
        return [p for p in self.params if p.kind == "body"]

    def query_params(self) -> list[P]:
        return [p for p in self.params if p.kind == "query"]

    def team_params(self) -> list[P]:
        return [p for p in self.params if p.kind == "team"]

    def all_non_path_params(self) -> list[P]:
        return [p for p in self.params if p.kind != "path"]


ENDPOINTS: list[Endpoint] = [
    # ── Authorized user ───────────────────────────────────────────────────
    Endpoint(
        method="get_authorized_user",
        http="GET",
        path="/user",
        doc="Return the ClickUp user associated with the configured API key.",
        cli_group="root",
        cli_cmd="whoami",
    ),

    # ── Spaces ────────────────────────────────────────────────────────────
    Endpoint(
        method="get_space",
        http="GET",
        path="/space/{space_id}",
        params=[P("space_id", "str", kind="path")],
        doc="Get a single space by id.",
        cli_group="root",
        cli_cmd="space",
    ),
    Endpoint(
        method="create_space",
        http="POST",
        path="/team/{team}/space",
        params=[
            P("name", "str"),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        doc="Create a new space in a workspace.",
        cli_group="root",
        cli_cmd="space-create",
    ),
    Endpoint(
        method="update_space",
        http="PUT",
        path="/space/{space_id}",
        params=[
            P("space_id", "str", kind="path"),
            P("name", "str | None", required=False),
            P("color", "str | None", required=False),
            P("private", "bool | None", required=False),
        ],
        doc="Update a space. Pass only the fields to change.",
        cli_group="root",
        cli_cmd="space-update",
    ),
    Endpoint(
        method="delete_space",
        http="DELETE",
        path="/space/{space_id}",
        params=[P("space_id", "str", kind="path")],
        delete_id_param="space_id",
        doc="Permanently delete a space.",
        cli_group="root",
        cli_cmd="space-delete",
    ),

    # ── Folders ───────────────────────────────────────────────────────────
    Endpoint(
        method="get_folder",
        http="GET",
        path="/folder/{folder_id}",
        params=[P("folder_id", "str", kind="path")],
        doc="Get a single folder by id.",
        cli_group="root",
        cli_cmd="folder",
    ),
    Endpoint(
        method="create_folder",
        http="POST",
        path="/space/{space_id}/folder",
        params=[
            P("space_id", "str", kind="path"),
            P("name", "str"),
        ],
        doc="Create a folder inside a space.",
        cli_group="root",
        cli_cmd="folder-create",
    ),
    Endpoint(
        method="update_folder",
        http="PUT",
        path="/folder/{folder_id}",
        params=[
            P("folder_id", "str", kind="path"),
            P("name", "str"),
        ],
        doc="Rename a folder.",
        cli_group="root",
        cli_cmd="folder-update",
    ),
    Endpoint(
        method="delete_folder",
        http="DELETE",
        path="/folder/{folder_id}",
        params=[P("folder_id", "str", kind="path")],
        delete_id_param="folder_id",
        doc="Permanently delete a folder.",
        cli_group="root",
        cli_cmd="folder-delete",
    ),

    # ── Lists ─────────────────────────────────────────────────────────────
    Endpoint(
        method="get_list",
        http="GET",
        path="/list/{list_id}",
        params=[P("list_id", "str", kind="path")],
        doc="Get a single list by id.",
        cli_group="root",
        cli_cmd="list",
    ),
    Endpoint(
        method="get_list_members",
        http="GET",
        path="/list/{list_id}/member",
        params=[P("list_id", "str", kind="path")],
        response_key="members",
        returns_list=True,
        doc="List members who have access to a list.",
        cli_group="root",
        cli_cmd="list-members",
    ),
    Endpoint(
        method="create_list",
        http="POST",
        path="/folder/{folder_id}/list",
        params=[
            P("folder_id", "str", kind="path"),
            P("name", "str"),
            P("status", "str | None", required=False),
            P("due_date", "int | None", required=False),
            P("priority", "int | None", required=False),
            P("assignee", "int | None", required=False),
        ],
        doc="Create a list inside a folder. priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.",
        cli_group="root",
        cli_cmd="list-create",
    ),
    Endpoint(
        method="create_folderless_list",
        http="POST",
        path="/space/{space_id}/list",
        params=[
            P("space_id", "str", kind="path"),
            P("name", "str"),
            P("status", "str | None", required=False),
            P("due_date", "int | None", required=False),
            P("priority", "int | None", required=False),
            P("assignee", "int | None", required=False),
        ],
        doc="Create a folderless list directly inside a space. priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.",
        cli_group="root",
        cli_cmd="list-create-space",
    ),
    Endpoint(
        method="update_list",
        http="PUT",
        path="/list/{list_id}",
        params=[
            P("list_id", "str", kind="path"),
            P("name", "str | None", required=False),
            P("status", "str | None", required=False),
            P("due_date", "int | None", required=False),
            P("priority", "int | None", required=False),
        ],
        doc="Update a list. Pass only the fields to change; due_date is Unix ms.",
        cli_group="root",
        cli_cmd="list-update",
    ),
    Endpoint(
        method="delete_list",
        http="DELETE",
        path="/list/{list_id}",
        params=[P("list_id", "str", kind="path")],
        delete_id_param="list_id",
        doc="Permanently delete a list.",
        cli_group="root",
        cli_cmd="list-delete",
    ),

    # ── Task extras ───────────────────────────────────────────────────────
    Endpoint(
        method="get_task_members",
        http="GET",
        path="/task/{task_id}/member",
        params=[P("task_id", "str", kind="path")],
        response_key="members",
        returns_list=True,
        doc="List members who are assigned to or watching a task.",
        cli_group="tasks",
        cli_cmd="members",
    ),
    Endpoint(
        method="get_task_time_in_status",
        http="GET",
        path="/task/{task_id}/time_in_status",
        params=[P("task_id", "str", kind="path")],
        doc="Return the time a task has spent in each status.",
        cli_group="tasks",
        cli_cmd="time-in-status",
    ),
    Endpoint(
        method="add_dependency",
        http="POST",
        path="/task/{task_id}/dependency",
        params=[
            P("task_id", "str", kind="path"),
            P("depends_on", "str | None", required=False, default="None"),
            P("dependency_of", "str | None", required=False, default="None"),
        ],
        doc="Add a dependency between tasks. Provide depends_on (this task waits on that one) or dependency_of (that task waits on this one).",
        cli_group="tasks",
        cli_cmd="add-dep",
    ),
    Endpoint(
        method="remove_dependency",
        http="DELETE",
        path="/task/{task_id}/dependency",
        params=[
            P("task_id", "str", kind="path"),
            P("depends_on", "str | None", required=False, default="None", kind="query"),
            P("dependency_of", "str | None", required=False, default="None", kind="query"),
        ],
        delete_id_param="task_id",
        doc="Remove a dependency. Provide the same depends_on or dependency_of used when adding.",
        cli_group="tasks",
        cli_cmd="remove-dep",
    ),
    Endpoint(
        method="add_task_link",
        http="POST",
        path="/task/{task_id}/link/{links_to}",
        params=[
            P("task_id", "str", kind="path"),
            P("links_to", "str", kind="path"),
        ],
        doc="Create a link between two tasks.",
        cli_group="tasks",
        cli_cmd="link",
    ),
    Endpoint(
        method="remove_task_link",
        http="DELETE",
        path="/task/{task_id}/link/{links_to}",
        params=[
            P("task_id", "str", kind="path"),
            P("links_to", "str", kind="path"),
        ],
        delete_id_param="task_id",
        doc="Remove a link between two tasks.",
        cli_group="tasks",
        cli_cmd="unlink",
    ),
    Endpoint(
        method="move_task",
        http="POST",
        path="/task/{task_id}/move",
        params=[
            P("task_id", "str", kind="path"),
            P("list_id", "str"),
        ],
        doc="Move a task to a different list.",
        cli_group="tasks",
        cli_cmd="move",
    ),

    # ── Checklists ────────────────────────────────────────────────────────
    Endpoint(
        method="create_checklist",
        http="POST",
        path="/task/{task_id}/checklist",
        params=[
            P("task_id", "str", kind="path"),
            P("name", "str"),
        ],
        doc="Create a checklist on a task.",
        cli_group="checklists",
        cli_cmd="create",
    ),
    Endpoint(
        method="update_checklist",
        http="PUT",
        path="/checklist/{checklist_id}",
        params=[
            P("checklist_id", "str", kind="path"),
            P("name", "str | None", required=False),
            P("position", "int | None", required=False),
        ],
        doc="Rename a checklist or change its position.",
        cli_group="checklists",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_checklist",
        http="DELETE",
        path="/checklist/{checklist_id}",
        params=[P("checklist_id", "str", kind="path")],
        delete_id_param="checklist_id",
        doc="Delete a checklist.",
        cli_group="checklists",
        cli_cmd="delete",
    ),
    Endpoint(
        method="create_checklist_item",
        http="POST",
        path="/checklist/{checklist_id}/checklist_item",
        params=[
            P("checklist_id", "str", kind="path"),
            P("name", "str"),
            P("assignee", "int | None", required=False),
        ],
        doc="Add an item to a checklist.",
        cli_group="checklists",
        cli_cmd="item-create",
    ),
    Endpoint(
        method="update_checklist_item",
        http="PUT",
        path="/checklist_item/{checklist_item_id}",
        params=[
            P("checklist_item_id", "str", kind="path"),
            P("name", "str | None", required=False),
            P("resolved", "bool | None", required=False),
            P("assignee", "int | None", required=False),
        ],
        doc="Update a checklist item's name, resolution state, or assignee.",
        cli_group="checklists",
        cli_cmd="item-update",
    ),
    Endpoint(
        method="delete_checklist_item",
        http="DELETE",
        path="/checklist_item/{checklist_item_id}",
        params=[P("checklist_item_id", "str", kind="path")],
        delete_id_param="checklist_item_id",
        doc="Delete a checklist item.",
        cli_group="checklists",
        cli_cmd="item-delete",
    ),

    # ── Comments extras ───────────────────────────────────────────────────
    Endpoint(
        method="list_list_comments",
        http="GET",
        path="/list/{list_id}/comment",
        params=[P("list_id", "str", kind="path")],
        response_key="comments",
        returns_list=True,
        doc="List all comments on a list (not on a specific task).",
        cli_group="comments",
        cli_cmd="list-comments",
    ),
    Endpoint(
        method="create_list_comment",
        http="POST",
        path="/list/{list_id}/comment",
        params=[
            P("list_id", "str", kind="path"),
            P("text", "str", body_key="comment_text"),
            P("notify_all", "bool", required=False, default="False"),
        ],
        doc="Post a comment on a list; set notify_all to notify all list members.",
        cli_group="comments",
        cli_cmd="list-create",
    ),
    Endpoint(
        method="update_comment",
        http="PUT",
        path="/comment/{comment_id}",
        params=[
            P("comment_id", "str", kind="path"),
            P("text", "str", body_key="comment_text"),
        ],
        doc="Edit the text of an existing comment.",
        cli_group="comments",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_comment",
        http="DELETE",
        path="/comment/{comment_id}",
        params=[P("comment_id", "str", kind="path")],
        delete_id_param="comment_id",
        doc="Delete a comment.",
        cli_group="comments",
        cli_cmd="delete",
    ),

    # ── Custom fields extras ──────────────────────────────────────────────
    Endpoint(
        method="remove_custom_field_value",
        http="DELETE",
        path="/task/{task_id}/field/{field_id}",
        params=[
            P("task_id", "str", kind="path"),
            P("field_id", "str", kind="path"),
        ],
        delete_id_param="field_id",
        doc="Clear a custom field value on a task.",
        cli_group="fields",
        cli_cmd="clear",
    ),

    # ── Tags ──────────────────────────────────────────────────────────────
    Endpoint(
        method="get_space_tags",
        http="GET",
        path="/space/{space_id}/tag",
        params=[P("space_id", "str", kind="path")],
        response_key="tags",
        returns_list=True,
        doc="List all tags defined in a space.",
        cli_group="tags",
        cli_cmd="list",
    ),
    Endpoint(
        method="create_space_tag",
        http="POST",
        path="/space/{space_id}/tag",
        params=[
            P("space_id", "str", kind="path"),
            P("name", "str"),
            P("bg_color", "str | None", required=False),
            P("fg_color", "str | None", required=False),
        ],
        doc="Create a tag in a space. Colors are hex strings (e.g. '#ff0000').",
        cli_group="tags",
        cli_cmd="create",
    ),
    Endpoint(
        method="update_space_tag",
        http="PUT",
        path="/space/{space_id}/tag/{tag_name}",
        params=[
            P("space_id", "str", kind="path"),
            P("tag_name", "str", kind="path"),
            P("name", "str | None", required=False),
            P("bg_color", "str | None", required=False),
            P("fg_color", "str | None", required=False),
        ],
        doc="Update a space tag's name or colors.",
        cli_group="tags",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_space_tag",
        http="DELETE",
        path="/space/{space_id}/tag/{tag_name}",
        params=[
            P("space_id", "str", kind="path"),
            P("tag_name", "str", kind="path"),
        ],
        delete_id_param="tag_name",
        doc="Delete a tag from a space.",
        cli_group="tags",
        cli_cmd="delete",
    ),
    Endpoint(
        method="add_task_tag",
        http="POST",
        path="/task/{task_id}/tag/{tag_name}",
        params=[
            P("task_id", "str", kind="path"),
            P("tag_name", "str", kind="path"),
        ],
        doc="Add a tag to a task.",
        cli_group="tags",
        cli_cmd="add",
    ),
    Endpoint(
        method="remove_task_tag",
        http="DELETE",
        path="/task/{task_id}/tag/{tag_name}",
        params=[
            P("task_id", "str", kind="path"),
            P("tag_name", "str", kind="path"),
        ],
        delete_id_param="tag_name",
        doc="Remove a tag from a task.",
        cli_group="tags",
        cli_cmd="remove",
    ),

    # ── Goals & Key Results ───────────────────────────────────────────────
    Endpoint(
        method="list_goals",
        http="GET",
        path="/team/{team}/goal",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        response_key="goals",
        returns_list=True,
        doc="List all goals in a workspace.",
        cli_group="goals",
        cli_cmd="list",
    ),
    Endpoint(
        method="get_goal",
        http="GET",
        path="/goal/{goal_id}",
        params=[P("goal_id", "str", kind="path")],
        doc="Get a single goal by id.",
        cli_group="goals",
        cli_cmd="get",
    ),
    Endpoint(
        method="create_goal",
        http="POST",
        path="/team/{team}/goal",
        params=[
            P("name", "str"),
            P("due_date", "int | None", required=False),
            P("description", "str | None", required=False),
            P("color", "str | None", required=False),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        doc="Create a goal in a workspace. due_date is Unix ms.",
        cli_group="goals",
        cli_cmd="create",
    ),
    Endpoint(
        method="update_goal",
        http="PUT",
        path="/goal/{goal_id}",
        params=[
            P("goal_id", "str", kind="path"),
            P("name", "str | None", required=False),
            P("due_date", "int | None", required=False),
            P("description", "str | None", required=False),
            P("color", "str | None", required=False),
        ],
        doc="Update a goal. Pass only the fields to change.",
        cli_group="goals",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_goal",
        http="DELETE",
        path="/goal/{goal_id}",
        params=[P("goal_id", "str", kind="path")],
        delete_id_param="goal_id",
        doc="Delete a goal.",
        cli_group="goals",
        cli_cmd="delete",
    ),
    Endpoint(
        method="create_key_result",
        http="POST",
        path="/goal/{goal_id}/key_result",
        params=[
            P("goal_id", "str", kind="path"),
            P("name", "str"),
            P("type", "str"),
            P("steps_start", "int"),
            P("steps_end", "int"),
            P("unit", "str"),
            P("task_ids", "list[str] | None", required=False),
            P("list_ids", "list[str] | None", required=False),
        ],
        doc="Add a key result to a goal. type: 'number' | 'currency' | 'boolean' | 'percentage' | 'automatic'.",
        cli_group="goals",
        cli_cmd="kr-create",
    ),
    Endpoint(
        method="update_key_result",
        http="PUT",
        path="/key_result/{key_result_id}",
        params=[
            P("key_result_id", "str", kind="path"),
            P("steps_current", "int"),
            P("note", "str | None", required=False),
        ],
        doc="Update a key result's current progress.",
        cli_group="goals",
        cli_cmd="kr-update",
    ),
    Endpoint(
        method="delete_key_result",
        http="DELETE",
        path="/key_result/{key_result_id}",
        params=[P("key_result_id", "str", kind="path")],
        delete_id_param="key_result_id",
        doc="Delete a key result.",
        cli_group="goals",
        cli_cmd="kr-delete",
    ),

    # ── Views ─────────────────────────────────────────────────────────────
    Endpoint(
        method="list_workspace_views",
        http="GET",
        path="/team/{team}/view",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        response_key="views",
        returns_list=True,
        doc="List all views in a workspace.",
        cli_group="views",
        cli_cmd="workspace",
    ),
    Endpoint(
        method="list_space_views",
        http="GET",
        path="/space/{space_id}/view",
        params=[P("space_id", "str", kind="path")],
        response_key="views",
        returns_list=True,
        doc="List all views in a space.",
        cli_group="views",
        cli_cmd="space",
    ),
    Endpoint(
        method="list_folder_views",
        http="GET",
        path="/folder/{folder_id}/view",
        params=[P("folder_id", "str", kind="path")],
        response_key="views",
        returns_list=True,
        doc="List all views in a folder.",
        cli_group="views",
        cli_cmd="folder",
    ),
    Endpoint(
        method="list_list_views",
        http="GET",
        path="/list/{list_id}/view",
        params=[P("list_id", "str", kind="path")],
        response_key="views",
        returns_list=True,
        doc="List all views in a list.",
        cli_group="views",
        cli_cmd="list",
    ),
    Endpoint(
        method="get_view",
        http="GET",
        path="/view/{view_id}",
        params=[P("view_id", "str", kind="path")],
        doc="Get a single view by id.",
        cli_group="views",
        cli_cmd="get",
    ),
    Endpoint(
        method="get_view_tasks",
        http="GET",
        path="/view/{view_id}/task",
        params=[
            P("view_id", "str", kind="path"),
            P("page", "int", required=False, default="0", kind="query"),
        ],
        doc="Get tasks visible in a view. Returns one page; check has_more and increment page to paginate.",
        cli_group="views",
        cli_cmd="tasks",
    ),
    Endpoint(
        method="create_view",
        http="POST",
        path="/list/{list_id}/view",
        params=[
            P("list_id", "str", kind="path"),
            P("name", "str"),
            P("type", "str"),
        ],
        doc="Create a view on a list. type: 'list' | 'board' | 'calendar' | 'table' | 'gantt' | 'activity' | 'workload'.",
        cli_group="views",
        cli_cmd="create",
    ),
    Endpoint(
        method="update_view",
        http="PUT",
        path="/view/{view_id}",
        params=[
            P("view_id", "str", kind="path"),
            P("name", "str"),
            P("type", "str"),
        ],
        doc="Update a view's name or type.",
        cli_group="views",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_view",
        http="DELETE",
        path="/view/{view_id}",
        params=[P("view_id", "str", kind="path")],
        delete_id_param="view_id",
        doc="Delete a view.",
        cli_group="views",
        cli_cmd="delete",
    ),

    # ── Webhooks ──────────────────────────────────────────────────────────
    Endpoint(
        method="list_webhooks",
        http="GET",
        path="/team/{team}/webhook",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        response_key="webhooks",
        returns_list=True,
        doc="List all webhooks in a workspace.",
        cli_group="webhooks",
        cli_cmd="list",
    ),
    Endpoint(
        method="create_webhook",
        http="POST",
        path="/team/{team}/webhook",
        params=[
            P("endpoint", "str"),
            P("events", "list[str]"),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        doc="Register a webhook. events: list of event names, or ['*'] for all events.",
        cli_group="webhooks",
        cli_cmd="create",
    ),
    Endpoint(
        method="update_webhook",
        http="PUT",
        path="/webhook/{webhook_id}",
        params=[
            P("webhook_id", "str", kind="path"),
            P("endpoint", "str | None", required=False),
            P("events", "list[str] | None", required=False),
            P("status", "str | None", required=False),
        ],
        doc="Update a webhook's endpoint URL, subscribed events, or status ('active' | 'inactive').",
        cli_group="webhooks",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_webhook",
        http="DELETE",
        path="/webhook/{webhook_id}",
        params=[P("webhook_id", "str", kind="path")],
        delete_id_param="webhook_id",
        doc="Delete a webhook.",
        cli_group="webhooks",
        cli_cmd="delete",
    ),

    # ── Time Tracking ─────────────────────────────────────────────────────
    Endpoint(
        method="get_time_entries",
        http="GET",
        path="/team/{team}/time_entries",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
            P("start_date", "int | None", required=False, default="None", kind="query"),
            P("end_date", "int | None", required=False, default="None", kind="query"),
            P("assignee", "int | None", required=False, default="None", kind="query"),
            P("task_id", "str | None", required=False, default="None", kind="query"),
        ],
        needs_team=True,
        response_key="data",
        returns_list=True,
        doc="Get time entries for a workspace. start_date/end_date are Unix ms timestamps.",
        cli_group="time",
        cli_cmd="list",
    ),
    Endpoint(
        method="get_running_time_entry",
        http="GET",
        path="/team/{team}/time_entries/current",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        doc="Get the currently running time entry for the workspace, if any.",
        cli_group="time",
        cli_cmd="current",
    ),
    Endpoint(
        method="create_time_entry",
        http="POST",
        path="/team/{team}/time_entries",
        params=[
            P("start", "int"),
            P("duration", "int"),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
            P("task_id", "str | None", required=False),
            P("description", "str | None", required=False),
            P("billable", "bool", required=False, default="False"),
        ],
        needs_team=True,
        doc="Manually log a time entry. start is Unix ms; duration is milliseconds.",
        cli_group="time",
        cli_cmd="create",
    ),
    Endpoint(
        method="start_timer",
        http="POST",
        path="/team/{team}/time_entries/start",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
            P("task_id", "str | None", required=False),
            P("description", "str | None", required=False),
            P("billable", "bool", required=False, default="False"),
        ],
        needs_team=True,
        doc="Start a new timer. Stops any currently running timer.",
        cli_group="time",
        cli_cmd="start",
    ),
    Endpoint(
        method="stop_timer",
        http="POST",
        path="/team/{team}/time_entries/stop",
        params=[
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        doc="Stop the currently running timer.",
        cli_group="time",
        cli_cmd="stop",
    ),
    Endpoint(
        method="update_time_entry",
        http="PUT",
        path="/team/{team}/time_entries/{time_entry_id}",
        params=[
            P("time_entry_id", "str", kind="path"),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
            P("start", "int | None", required=False),
            P("duration", "int | None", required=False),
            P("description", "str | None", required=False),
            P("billable", "bool | None", required=False),
        ],
        needs_team=True,
        doc="Update a time entry. start is Unix ms; duration is ms.",
        cli_group="time",
        cli_cmd="update",
    ),
    Endpoint(
        method="delete_time_entry",
        http="DELETE",
        path="/team/{team}/time_entries/{time_entry_id}",
        params=[
            P("time_entry_id", "str", kind="path"),
            P("workspace_id", "str | None", required=False, kind="team"),
            P("workspace_name", "str | None", required=False, kind="team"),
        ],
        needs_team=True,
        delete_id_param="time_entry_id",
        doc="Delete a time entry.",
        cli_group="time",
        cli_cmd="delete",
    ),
]

NEW_CLI_GROUPS: list[tuple[str, str, str]] = [
    ("checklists_app", "checklists", "Checklist and checklist-item CRUD"),
    ("tags_app", "tags", "Space tags and task tags"),
    ("goals_app", "goals", "Goals and key results"),
    ("views_app", "views", "Views"),
    ("webhooks_app", "webhooks", "Webhooks"),
    ("time_app", "time", "Time tracking"),
]


def gen_client_method(ep: Endpoint) -> str:
    """Generate a ClickUpClient instance method (no leading indent — caller adds 4sp)."""
    path_params = ep.path_params()
    non_path = ep.all_non_path_params()
    req_non_path = [p for p in non_path if p.required]
    opt_non_path = [p for p in non_path if not p.required]

    sig_parts = ["self"]
    for p in path_params:
        sig_parts.append(f"{p.name}: {p.type}")
    for p in req_non_path:
        sig_parts.append(f"{p.name}: {p.type}")
    if opt_non_path:
        sig_parts.append("*")
        for p in opt_non_path:
            sig_parts.append(f"{p.name}: {p.type} = {p.default}")

    sig = ", ".join(sig_parts)
    ret = "list[JsonValue]" if ep.returns_list else "JsonValue"

    body: list[str] = []
    body.append(f'def {ep.method}({sig}) -> {ret}:')
    body.append(f'    """{ep.doc}"""')

    if ep.needs_team:
        team_params = ep.team_params()
        wid = "workspace_id" if any(p.name == "workspace_id" for p in team_params) else "None"
        wname = "workspace_name" if any(p.name == "workspace_name" for p in team_params) else "None"
        body.append(f'    team = self._resolve_team({wid}, {wname})')

    bparams = ep.body_params()
    qparams = ep.query_params()

    if ep.http in ("POST", "PUT") and bparams:
        body.append('    body: dict[str, object] = {}')
        for p in bparams:
            key = p.api_key()
            if p.required or not p.is_nullable():
                body.append(f'    body["{key}"] = {p.name}')
            else:
                body.append(f'    if {p.name} is not None:')
                body.append(f'        body["{key}"] = {p.name}')
        body.append(f'    return self._request("{ep.http}", f"{ep.path}", json=body)')

    elif ep.http == "DELETE":
        if qparams:
            body.append('    params: dict[str, object] = {}')
            for p in qparams:
                body.append(f'    if {p.name} is not None:')
                body.append(f'        params["{p.name}"] = {p.name}')
            body.append(f'    self._request("DELETE", f"{ep.path}", params=params)')
        else:
            body.append(f'    self._request("DELETE", f"{ep.path}")')
        if ep.delete_id_param:
            body.append(f'    return {{"deleted": {ep.delete_id_param}}}')
        else:
            body.append('    return {}')

    else:
        if qparams:
            body.append('    params: dict[str, object] = {}')
            for p in qparams:
                if p.required:
                    body.append(f'    params["{p.name}"] = {p.name}')
                else:
                    body.append(f'    if {p.name} is not None:')
                    body.append(f'        params["{p.name}"] = {p.name}')
            call = f'self._request("{ep.http}", f"{ep.path}", params=params)'
        else:
            call = f'self._request("{ep.http}", f"{ep.path}")'

        if ep.response_key:
            body.append(f'    result = self._field({call}, {ep.response_key!r})')
            body.append('    return result if isinstance(result, list) else []')
        else:
            body.append(f'    return {call}')

    return "\n".join(body)


def gen_server_tool(ep: Endpoint) -> str:
    """Generate a @mcp.tool() function."""
    path_params = ep.path_params()
    non_path = ep.all_non_path_params()
    req_non_path = [p for p in non_path if p.required]
    opt_non_path = [p for p in non_path if not p.required]

    sig_parts: list[str] = []
    for p in path_params:
        sig_parts.append(f"{p.name}: {p.type}")
    for p in req_non_path:
        sig_parts.append(f"{p.name}: {p.type}")
    for p in opt_non_path:
        sig_parts.append(f"{p.name}: {p.type} = {p.default}")

    call_parts: list[str] = []
    for p in path_params:
        call_parts.append(p.name)
    for p in req_non_path:
        call_parts.append(f"{p.name}={p.name}")
    for p in opt_non_path:
        call_parts.append(f"{p.name}={p.name}")

    sig = ", ".join(sig_parts)
    call_args = ", ".join(call_parts)

    lines: list[str] = [
        "@mcp.tool()",
        f"def {ep.method}({sig}) -> str:",
        f'    """{ep.doc}"""',
        f"    return _dump(_api().{ep.method}({call_args}))",
    ]
    return "\n".join(lines)


def gen_cli_command(ep: Endpoint) -> str:
    """Generate a CLI Typer command function."""
    path_params = ep.path_params()
    non_path = ep.all_non_path_params()
    req_non_path = [p for p in non_path if p.required]
    opt_non_path = [p for p in non_path if not p.required]

    group = ep.cli_group
    cmd = ep.cli_cmd
    fn_name = f"cli_{ep.method}"

    if group == "root":
        decorator = f'@app.command("{cmd}")'
    else:
        decorator = f'@{group}_app.command("{cmd}")'

    def param_line(p: P, required: bool) -> str:
        flag = p.cli_flag_name()
        if p.kind == "path":
            return f"{p.name}: str = typer.Argument(...)"
        if "list[" in p.type:
            if required:
                return f'{p.name}: str = typer.Option(..., "--{flag}", help="Comma-separated")'
            return f'{p.name}: str | None = typer.Option(None, "--{flag}", help="Comma-separated")'
        if p.type in ("bool", "bool | None"):
            return f'{p.name}: {p.type} = typer.Option({p.default}, "--{flag}/--no-{flag}")'
        if required:
            return f'{p.name}: {p.type} = typer.Option(..., "--{flag}")'
        return f'{p.name}: {p.type} = typer.Option({p.default}, "--{flag}")'

    sig_lines = (
        [param_line(p, True) for p in path_params]
        + [param_line(p, True) for p in req_non_path]
        + [param_line(p, False) for p in opt_non_path]
    )
    if sig_lines:
        sig_str = "(\n    " + ",\n    ".join(sig_lines) + ",\n) -> None:"
    else:
        sig_str = "() -> None:"

    def call_arg(p: P) -> str:
        if p.kind in ("path", "team"):
            return f"{p.name}={p.name}"
        if "list[" in p.type:
            if p.required:
                return f"{p.name}={p.name}.split(',')"
            return f"{p.name}={p.name}.split(',') if {p.name} else None"
        return f"{p.name}={p.name}"

    call_parts = (
        [p.name for p in path_params]
        + [call_arg(p) for p in req_non_path]
        + [call_arg(p) for p in opt_non_path]
    )
    call_args = ", ".join(call_parts)

    lines: list[str] = [
        decorator,
        f"def {fn_name}{sig_str}",
        f'    """{ep.doc}"""',
        f"    _out(ClickUpClient.from_env().{ep.method}({call_args}))",
    ]
    return "\n".join(lines)


def gen_cli_groups_block() -> str:
    lines = [""]
    for var, name, help_text in NEW_CLI_GROUPS:
        lines.append(f'{var} = typer.Typer(no_args_is_help=True, help={help_text!r})')
    lines.append("")
    for var, name, _ in NEW_CLI_GROUPS:
        lines.append(f'app.add_typer({var}, name="{name}")')
    return "\n".join(lines)


def _insert(src: str, anchor: str, insertion: str, *, after: bool = False) -> str:
    """Insert ``insertion`` immediately before (or after) ``anchor`` in ``src``."""
    idx = src.find(anchor)
    if idx == -1:
        raise ValueError(f"anchor not found: {anchor!r}")
    if after:
        idx += len(anchor)
    return src[:idx] + insertion + src[idx:]


def main() -> None:
    """Run the generator."""
    client_src = CLIENT_FILE.read_text()
    server_src = SERVER_FILE.read_text()
    cli_src = CLI_FILE.read_text()

    # ── client.py: insert methods inside the class, before module-level helpers ──
    client_methods = "\n\n".join(
        textwrap.indent(gen_client_method(ep), "    ") for ep in ENDPOINTS
    )
    client_block = f"\n\n{client_methods}\n"
    client_src = _insert(client_src, CLIENT_ANCHOR, client_block)
    CLIENT_FILE.write_text(client_src)
    print(f"✓ client.py  +{len(ENDPOINTS)} methods")

    # ── server.py: insert tools before main() ────────────────────────────────
    server_tools = "\n\n".join(gen_server_tool(ep) for ep in ENDPOINTS)
    server_block = f"\n\n{server_tools}\n"
    server_src = _insert(server_src, SERVER_ANCHOR, server_block)
    SERVER_FILE.write_text(server_src)
    print(f"✓ server.py  +{len(ENDPOINTS)} tools")

    # ── cli.py: register new sub-apps, insert commands before main() ────────
    cli_src = _insert(cli_src, CLI_ANCHOR, gen_cli_groups_block() + "\n", after=True)
    cli_cmds = "\n\n".join(gen_cli_command(ep) for ep in ENDPOINTS)
    cli_src = _insert(cli_src, "\ndef main() -> None:", f"\n\n{cli_cmds}\n")
    CLI_FILE.write_text(cli_src)
    print(f"✓ cli.py     +{len(ENDPOINTS)} commands (+{len(NEW_CLI_GROUPS)} sub-apps)")

    print(f"\nTotal: {len(ENDPOINTS)} new endpoints mapped.")


if __name__ == "__main__":
    main()
