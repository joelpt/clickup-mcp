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

`list_workspaces`, `list_spaces`, `list_folders`, `list_lists`, `search_tasks`,
`get_task`, `create_task`, `update_task`, `delete_task`, `list_comments`, `add_comment`,
`list_custom_fields`, `set_custom_field_value`.

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
