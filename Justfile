# clickup-mcp — ClickUp MCP server + CLI

# Run the MCP server (stdio transport)
run:
    uv run clickup-mcp

# Run the test suite
test:
    uv run pytest -q

# Lint (ruff)
lint:
    uv run ruff check .

# Build wheel + sdist
build:
    uv build

# Smoke test: tools register offline; hit the real API only if a key is present
smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "[smoke] tests"
    uv run pytest -q
    echo "[smoke] tool registration"
    uv run python -c "import asyncio; from clickup_mcp import server; n=len(asyncio.run(server.mcp.list_tools())); print(f'  {n} tools'); assert n == 11"
    if [[ -n "${CLICKUP_API_KEY:-}" || -n "${CLICKUP_API_KEY_FILE:-}" ]]; then
        echo "[smoke] live: clickup workspaces"
        uv run clickup workspaces | head -c 400; echo
    else
        echo "[smoke] no CLICKUP_API_KEY(_FILE) set — skipping live API check"
    fi
    echo "[smoke] OK"
