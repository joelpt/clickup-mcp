"""Tests for the FastMCP server: tool registration and delegation to the client."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from clickup_mcp import server

EXPECTED_TOOLS = {
    "list_workspaces",
    "list_spaces",
    "list_folders",
    "list_lists",
    "search_tasks",
    "get_task",
    "create_task",
    "update_task",
    "delete_task",
    "list_comments",
    "add_comment",
}


def test_all_tools_registered() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert {t.name for t in tools} == EXPECTED_TOOLS


def test_tool_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class FakeClient:
        def create_task(self, list_id: str, name: str, **kwargs: Any) -> dict[str, Any]:
            calls["args"] = (list_id, name, kwargs)
            return {"id": "task1"}

    monkeypatch.setattr(server, "_client", FakeClient())
    result = server.create_task("L1", "Beans", priority=2)
    assert json.loads(result) == {"id": "task1"}
    assert calls["args"][0] == "L1"
    assert calls["args"][1] == "Beans"
    assert calls["args"][2]["priority"] == 2
