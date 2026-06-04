# clickup-mcp

A [Model Context Protocol](https://modelcontextprotocol.io) server (and companion CLI)
for [ClickUp](https://clickup.com), wrapping the ClickUp REST API v2 directly — no
third-party service, no license key.

It exposes ClickUp as discrete MCP tools (`list_workspaces`, `search_tasks`,
`create_task`, …) so an MCP host can grant or gate each operation individually.

## Install / run

No PyPI release — run straight from GitHub with [uv](https://docs.astral.sh/uv/):

```bash
# MCP server (stdio transport)
uvx --from git+https://github.com/joelpt/clickup-mcp@<ref> clickup-mcp

# CLI (same operations, for humans/debugging)
uvx --from git+https://github.com/joelpt/clickup-mcp@<ref> clickup workspaces
```

Pin `<ref>` to a commit SHA (or a tag) for reproducible installs.

## Configuration

- `CLICKUP_API_KEY` — personal API token (`pk_...`) from ClickUp Settings > Apps.
- `CLICKUP_API_KEY_FILE` — alternatively, a path to a file containing the token
  (used when the key must not live in the process environment). `CLICKUP_API_KEY`
  takes precedence if both are set.
- `CLICKUP_TEAM_ID` — default workspace id (the first number in your ClickUp URL).
  Optional; tools also accept `workspace_id` / `workspace_name` to target another workspace.

## Registering with Claude Code

```bash
claude mcp add clickup \
  -e CLICKUP_API_KEY_FILE=/path/to/api-key \
  -e CLICKUP_TEAM_ID=1234567 \
  -- uvx --from git+https://github.com/joelpt/clickup-mcp@<ref> clickup-mcp
```

Tools then appear as `mcp__clickup__list_workspaces`, `mcp__clickup__create_task`, etc.

## Tools

The server exposes one tool per ClickUp operation, each individually gateable by
the MCP host. Grouped by domain:

- **Workspaces & navigation** — `list_workspaces`, `list_members`, `list_spaces`, `list_folders`, `list_lists`, `get_authorized_user`
- **Spaces** — `get_space`, `create_space`, `update_space`, `delete_space`
- **Folders** — `get_folder`, `create_folder`, `update_folder`, `delete_folder`
- **Lists** — `get_list`, `get_list_members`, `create_list`, `create_folderless_list`, `update_list`, `delete_list`
- **Tasks** — `search_tasks`, `get_task`, `create_task`, `update_task`, `delete_task`, `move_task`, `get_task_members`, `get_task_time_in_status`
- **Dependencies & links** — `add_dependency`, `remove_dependency`, `add_task_link`, `remove_task_link`
- **Checklists** — `create_checklist`, `update_checklist`, `delete_checklist`, `create_checklist_item`, `update_checklist_item`, `delete_checklist_item`
- **Comments** — `list_comments`, `add_comment`, `list_list_comments`, `create_list_comment`, `update_comment`, `delete_comment`
- **Custom fields** — `list_custom_fields`, `set_custom_field_value`, `remove_custom_field_value`
- **Tags** — `get_space_tags`, `create_space_tag`, `update_space_tag`, `delete_space_tag`, `add_task_tag`, `remove_task_tag`
- **Goals** — `list_goals`, `get_goal`, `create_goal`, `update_goal`, `delete_goal`, `create_key_result`, `update_key_result`, `delete_key_result`
- **Views** — `list_workspace_views`, `list_space_views`, `list_folder_views`, `list_list_views`, `get_view`, `get_view_tasks`, `create_view`, `update_view`, `delete_view`
- **Webhooks** — `list_webhooks`, `create_webhook`, `update_webhook`, `delete_webhook`
- **Time tracking** — `get_time_entries`, `get_running_time_entry`, `create_time_entry`, `start_timer`, `stop_timer`, `update_time_entry`, `delete_time_entry`

Hierarchy: **Workspace > Space > Folder > List > Task**.

### Subtasks

`create_task` accepts a `parent` (task id); set it to create the new task as a subtask of
that task (the parent must live in the same list).

### Completed tasks

`search_tasks` excludes closed/completed tasks by default (ClickUp's own default).
Pass `include_closed=true` to surface them in an unfiltered search — the clean path for a
full audit — or pass a `status` naming a closed-type status (e.g. `"done"`), which returns
matching closed tasks even without `include_closed`.
A `status` filter is sent as ClickUp's `statuses[]` array parameter.

### Custom fields

`list_custom_fields` enumerates the custom fields at one scope — `list_id`, `folder_id`,
`space_id`, or `workspace_id`/`workspace_name`.
The scopes are **not** hierarchical: each returns only the fields *defined at that level*,
so to find a task's field, query the list it lives in.
For a `drop_down` field, the selectable options (each with an `id` and `name`) are under
`type_config.options`.

`set_custom_field_value` assigns a value to a field on a task.
For a dropdown, pass the chosen option's `id` (its integer `orderindex` also works).
ClickUp's API can only *select* an existing option — it cannot create, edit, or delete the
list of permitted dropdown options; that is UI-only.

## License

MIT
