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
`get_task`, `create_task`, `update_task`, `delete_task`, `list_comments`, `add_comment`.

Hierarchy: **Workspace > Space > Folder > List > Task**.

## License

MIT
