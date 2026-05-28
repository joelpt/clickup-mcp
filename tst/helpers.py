"""Shared test helpers for clickup-mcp."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from clickup_mcp.client import ClickUpClient

Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler, *, team_id: str | None = "team1") -> ClickUpClient:
    """Build a ClickUpClient whose network is served by ``handler`` via MockTransport."""
    return ClickUpClient("pk_test", team_id, transport=httpx.MockTransport(handler))
