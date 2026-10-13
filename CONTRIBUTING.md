# Contributing

Bug reports and pull requests are welcome.

## Setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.11 or newer.

```bash
git clone https://github.com/joelpt/clickup-mcp
cd clickup-mcp
uv sync
```

## Checks

```bash
just test    # pytest, no network or API key needed
just lint    # ruff
just smoke   # tests, tool registration, and a live call if CLICKUP_API_KEY is set
```

Tests mock HTTP with `httpx.MockTransport`, so they never hit ClickUp.
That also means a mocked test only proves the code matches your assumption about the endpoint.
When adding or changing an endpoint, check the path and body against ClickUp's published spec (`https://developer.clickup.com/openapi/clickup-api-v2-reference.json`, or the v3 spec) and say which operation you matched in the PR.

## Pull requests

- Write a failing test first, then the minimal change that passes it.
- Keep each PR to one change, with a conventional commit message (`fix(tasks): ...`).
- Add the tool to the list in `README.md` and keep the tool count in `Justfile` and CI in sync.
- Never put a real API token in code, tests, or issues.

## Security

Report vulnerabilities privately, as described in [SECURITY.md](SECURITY.md).
