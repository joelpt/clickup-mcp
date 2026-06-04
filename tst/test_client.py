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


def test_list_members() -> None:
    member = {"id": 101, "username": "alice", "email": "alice@example.com", "role": 2}

    def handler(req: httpx.Request) -> httpx.Response:
        # Members are embedded in the workspace object; no separate /member endpoint.
        assert req.url.path == "/api/v2/team"
        return _json({"teams": [{"id": "team1", "name": "Acme", "members": [member]}]})

    assert make_client(handler).list_members(workspace_id="team1") == [member]


def test_list_members_defaults_to_configured_workspace() -> None:
    member = {"id": 202, "username": "bob", "email": "bob@example.com", "role": 4}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team"
        return _json({"teams": [{"id": "team1", "name": "Acme", "members": [member]}]})

    assert make_client(handler).list_members() == [member]


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


def test_create_task_sets_parent_for_subtask() -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/L1/task"
        captured.update(json.loads(req.content))
        return _json({"id": "sub1"})

    make_client(handler).create_task("L1", "Sub", parent="parent1")
    assert captured == {"name": "Sub", "parent": "parent1"}


def test_create_task_omits_parent_when_absent() -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured.update(json.loads(req.content))
        return _json({"id": "t1"})

    make_client(handler).create_task("L1", "Top")
    assert "parent" not in captured


def test_list_custom_fields_for_list() -> None:
    field = {"id": "cf1", "name": "Stage", "type": "drop_down"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/L1/field"
        return _json({"fields": [field]})

    assert make_client(handler).list_custom_fields(list_id="L1") == [field]


def test_list_custom_fields_for_workspace_resolves_team() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/field"
        return _json({"fields": []})

    assert make_client(handler).list_custom_fields(workspace_id="team1") == []


def test_list_custom_fields_defaults_to_configured_workspace() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/field"
        return _json({"fields": []})

    assert make_client(handler).list_custom_fields() == []


def test_list_custom_fields_no_scope_and_no_default_team_raises() -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"fields": []})

    with pytest.raises(ValueError, match="no workspace"):
        make_client(handler, team_id=None).list_custom_fields()


def test_set_custom_field_value_posts_value() -> None:
    captured: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/v2/task/t1/field/cf1"
        captured.update(json.loads(req.content))
        return _json({"id": "t1"})

    make_client(handler).set_custom_field_value("t1", "cf1", "option-uuid-9")
    assert captured == {"value": "option-uuid-9"}


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


def test_search_tasks_status_uses_array_bracket_notation() -> None:
    """ClickUp rejects a scalar ``statuses`` (PUBAPITASK_014); it must be ``statuses[]``."""

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params.get("statuses[]") == "done"
        assert "statuses" not in [k for k in req.url.params if k != "statuses[]"]
        return _json({"tasks": []})

    make_client(handler).search_tasks(status="done")


def test_search_tasks_excludes_closed_by_default() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert "include_closed" not in req.url.params
        return _json({"tasks": []})

    make_client(handler).search_tasks()


def test_search_tasks_can_include_closed() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params.get("include_closed") == "true"
        return _json({"tasks": []})

    make_client(handler).search_tasks(include_closed=True)


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


# --- dropdown custom-field resolution ---

_DROPDOWN_FIELD_TEMPLATE: dict = {
    "id": "cf1",
    "name": "Project/Workstream",
    "type": "drop_down",
    "type_config": {
        "options": [
            {"orderindex": 0, "name": "Product Development", "id": "opt0"},
            {"orderindex": 1, "name": "Company Governance", "id": "opt1"},
        ]
    },
}


def test_dropdown_orderindex_zero_resolves_to_label_get_task() -> None:
    """value:0 must resolve to the first option's name, not be treated as unset."""
    field = {**_DROPDOWN_FIELD_TEMPLATE, "value": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"id": "t1", "custom_fields": [field]})

    result = make_client(handler).get_task("t1", include_subtasks=False)
    assert isinstance(result, dict)
    assert result["custom_fields"][0]["value"] == "Product Development"


def test_dropdown_nonzero_orderindex_resolves_to_label_get_task() -> None:
    field = {**_DROPDOWN_FIELD_TEMPLATE, "value": 1}

    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"id": "t1", "custom_fields": [field]})

    result = make_client(handler).get_task("t1", include_subtasks=False)
    assert isinstance(result, dict)
    assert result["custom_fields"][0]["value"] == "Company Governance"


def test_dropdown_null_value_stays_none_get_task() -> None:
    field = {**_DROPDOWN_FIELD_TEMPLATE, "value": None}

    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"id": "t1", "custom_fields": [field]})

    result = make_client(handler).get_task("t1", include_subtasks=False)
    assert isinstance(result, dict)
    assert result["custom_fields"][0]["value"] is None


def test_dropdown_orderindex_zero_resolves_in_search_tasks() -> None:
    """Dropdown resolution must also apply to tasks returned by search_tasks."""
    field = {**_DROPDOWN_FIELD_TEMPLATE, "value": 0}

    def handler(_req: httpx.Request) -> httpx.Response:
        return _json({"tasks": [{"id": "t1", "name": "VTT SOW 1", "custom_fields": [field]}]})

    result = make_client(handler).search_tasks()
    assert isinstance(result, dict)
    tasks = result["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["custom_fields"][0]["value"] == "Product Development"  # type: ignore[index]
