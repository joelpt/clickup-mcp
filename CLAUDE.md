# clickup-mcp — project notes

ClickUp MCP server + CLI: a direct ClickUp REST API v2 wrapper exposing `mcp__clickup__*` tools.
This repo is the **engine**.
It is consumed by two downstream projects that pin it by git ref, so a release here is rarely standalone — it usually fans out to coordinated edits elsewhere (see below).

## Versioning — CalVer, released in lockstep with the plugin

Tag every release `vYYYY.MM.DD.N` (zero-padded month/day, `N` = that-day counter) and set the same string in `pyproject.toml`'s `version`.

- Zero-pad so tags sort correctly in any lexical view (`v2026.05.09.1` before `v2026.05.29.1`).
- PEP 440 de-pads the *installed* metadata version (`2026.5.29.1`) — expected; the git tag keeps the padding.
- Use UTC for the date (`date -u +%Y.%m.%d`).
- Share the same CalVer as `claude-plugin-clickup` whenever a server release drives a plugin bump — matching versions signal "these fit together / are compatible" to consumers at a glance.

## Coordinated release flow

A change here that downstream consumers should pick up is a multi-repo operation.
After merging to `main`:

1. Bump `pyproject.toml` `version`, then `git tag vYYYY.MM.DD.N`; push `main` + the tag.
2. `~/code/claude-plugin-clickup` — repin `.mcp.json` (`clickup-mcp@vYYYY.MM.DD.N`) and bump the plugin's own `version` to match, then its marketplace-sync flow (see that repo's `CLAUDE.md` and `~/.claude/rules/claude-plugins.md`).
3. `~/code/cclaw` — bump `CLICKUP_MCP_REF` in `bot/Dockerfile` and the fallback default in `bot/entrypoint.sh`, then rebuild the bot image.

The downstream pins must always reference a tag/commit that is **already pushed**, or `uvx` resolution fails for every consumer.
