# Security Policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/joelpt/clickup-mcp/security/advisories/new)
rather than a public issue. Expect an acknowledgement within a few days.

## Threat model notes

- The server authenticates with a ClickUp personal API token. Prefer `CLICKUP_API_KEY_FILE`
  (a `0600` file) over `CLICKUP_API_KEY` so the token stays out of the process environment
  and shell history. Never commit a token.
- The token grants the full access of the ClickUp user who created it. The server exposes
  destructive operations (`delete_task`, `delete_space`, `delete_folder`, `delete_list`,
  `delete_webhook`, and others). Use your MCP host's per-tool permission gating to require
  confirmation for write and delete tools, or allow read-only tools only.
- `create_webhook` registers an outbound endpoint that receives workspace event data. Only
  point it at endpoints you control.
- Pin installs to a release tag or, better, a full commit SHA: `uvx --from
  git+https://github.com/joelpt/clickup-mcp@<sha> clickup-mcp`.
