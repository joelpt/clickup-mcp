"""Tests for ClickUpClient against a mocked ClickUp API."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from clickup_mcp.client import ClickUpClient
from tst.helpers import make_client


def _json(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_from_env_reads_key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key_file = tmp_path / "api-key"
    key_file.write_text("pk_fromfile\n")
    monkeypatch.delenv("CLICKUP_API_KEY", raising=False)
    monkeypatch.setenv("CLICKUP_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("CLICKUP_TEAM_ID", "t99")
    client = ClickUpClient.from_env()
    assert client._http.headers["Authorization"] == "pk_fromfile"
    assert client._team_id == "t99"


def test_from_env_prefers_inline_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLICKUP_API_KEY", "pk_inline")
    monkeypatch.setenv("CLICKUP_API_KEY_FILE", str(tmp_path / "missing"))
    assert ClickUpClient.from_env()._http.headers["Authorization"] == "pk_inline"


def test_from_env_requires_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLICKUP_API_KEY", raising=False)
    monkeypatch.delenv("CLICKUP_API_KEY_FILE", raising=False)
    with pytest.raises(ValueError, match="CLICKUP_API_KEY"):
        ClickUpClient.from_env()


def test_rate_limit_raises() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "30"}, json={})

    with pytest.raises(ValueError, match="Retry after 30s"):
        make_client(handler).list_workspaces()


def test_api_error_surfaces_err_field() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"err": "bad token"}, status=401)

    with pytest.raises(ValueError, match="ClickUp API 401: bad token"):
        make_client(handler).list_workspaces()


def test_list_workspaces() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team"
        return _json({"teams": [{"id": "1", "name": "Acme"}]})

    assert make_client(handler).list_workspaces() == [{"id": "1", "name": "Acme"}]


def test_resolve_team_by_name() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v2/team":
            teams = [{"id": "42", "name": "VeggieCo"}, {"id": "7", "name": "Other"}]
            return _json({"teams": teams})
        assert req.url.path == "/api/v2/team/42/space"
        return _json({"spaces": [{"id": "s1"}]})

    assert make_client(handler).list_spaces(workspace_name="veggieco") == [{"id": "s1"}]


def test_resolve_team_by_name_not_found() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"teams": [{"id": "1", "name": "Acme"}]})

    with pytest.raises(ValueError, match="no workspace named 'Nope'"):
        make_client(handler).list_spaces(workspace_name="Nope")


def test_create_task_builds_body() -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/L1/task"
        captured.update(json.loads(req.content))
        return _json({"id": "task1"})

    result = make_client(handler).create_task("L1", "Beans", priority=2, assignees=[123, 456])
    assert result == {"id": "task1"}
    assert captured == {"name": "Beans", "priority": 2, "assignees": [123, 456]}


def test_search_tasks_client_side_filter() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return _json({"tasks": [{"name": "fix beans"}, {"name": "buy milk"}]})

    out = make_client(handler).search_tasks("BEAN")
    assert out == {"tasks": [{"name": "fix beans"}], "has_more": False}


def test_search_tasks_includes_subtasks_by_default() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params.get("subtasks") == "true"
        return _json({"tasks": []})

    make_client(handler).search_tasks()


def test_search_tasks_can_exclude_subtasks() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "subtasks" not in req.url.params
        return _json({"tasks": []})

    make_client(handler).search_tasks(include_subtasks=False)


def test_get_task_includes_subtasks_by_default() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1"
        assert req.url.params.get("include_subtasks") == "true"
        return _json({"id": "t1", "subtasks": []})

    assert make_client(handler).get_task("t1") == {"id": "t1", "subtasks": []}


def test_get_task_can_exclude_subtasks() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "include_subtasks" not in req.url.params
        return _json({"id": "t1"})

    make_client(handler).get_task("t1", include_subtasks=False)


def test_delete_task_returns_marker() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        return httpx.Response(200)

    assert make_client(handler).delete_task("t1") == {"deleted": "t1"}


def test_list_lists_requires_a_scope() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"lists": []})

    with pytest.raises(ValueError, match="space_id or folder_id"):
        make_client(handler).list_lists()
