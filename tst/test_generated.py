"""Tests for generated ClickUp API endpoint wrappers.

One representative test per new resource area verifying correct HTTP path, method,
request body/params, and response unwrapping.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from tst.helpers import make_client


def _json(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


# ── Authorized user ────────────────────────────────────────────────────────


def test_get_authorized_user() -> None:
    user = {"id": 1, "username": "alice"}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/user"
        return _json({"user": user})

    result = make_client(handler).get_authorized_user()
    assert isinstance(result, dict)
    assert result.get("user") == user  # type: ignore[union-attr]


# ── Spaces ─────────────────────────────────────────────────────────────────


def test_get_space() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1"
        return _json({"id": "s1", "name": "Dev"})

    assert make_client(handler).get_space("s1") == {"id": "s1", "name": "Dev"}


def test_create_space_sends_name() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/space"
        assert req.method == "POST"
        captured.update(json.loads(req.content))
        return _json({"id": "sp2"})

    result = make_client(handler).create_space("New Space")
    assert result == {"id": "sp2"}
    assert captured == {"name": "New Space"}


def test_update_space_sends_only_provided_fields() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1"
        assert req.method == "PUT"
        captured.update(json.loads(req.content))
        return _json({"id": "s1"})

    make_client(handler).update_space("s1", name="Renamed", color="#ff0000")
    assert captured == {"name": "Renamed", "color": "#ff0000"}


def test_delete_space_returns_deleted_key() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_space("s1") == {"deleted": "s1"}


# ── Folders ────────────────────────────────────────────────────────────────


def test_get_folder() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/folder/f1"
        return _json({"id": "f1", "name": "Sprint"})

    assert make_client(handler).get_folder("f1") == {"id": "f1", "name": "Sprint"}


def test_create_folder() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1/folder"
        captured.update(json.loads(req.content))
        return _json({"id": "f2"})

    result = make_client(handler).create_folder("s1", "Q3")
    assert result == {"id": "f2"}
    assert captured["name"] == "Q3"


def test_delete_folder() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/folder/f1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_folder("f1") == {"deleted": "f1"}


# ── Lists ──────────────────────────────────────────────────────────────────


def test_get_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/l1"
        return _json({"id": "l1", "name": "Backlog"})

    assert make_client(handler).get_list("l1") == {"id": "l1", "name": "Backlog"}


def test_get_list_members_unwraps_key() -> None:
    members = [{"id": 1, "username": "bob"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/l1/member"
        return _json({"members": members})

    assert make_client(handler).get_list_members("l1") == members


def test_create_list_in_folder() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/folder/f1/list"
        captured.update(json.loads(req.content))
        return _json({"id": "l2"})

    make_client(handler).create_list("f1", "Backlog", priority=3)
    assert captured["name"] == "Backlog"
    assert captured["priority"] == 3


def test_create_folderless_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1/list"
        return _json({"id": "l3"})

    result = make_client(handler).create_folderless_list("s1", "No Folder")
    assert result == {"id": "l3"}


def test_delete_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/l1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_list("l1") == {"deleted": "l1"}


# ── Task extras ────────────────────────────────────────────────────────────


def test_get_task_members() -> None:
    members = [{"id": 5, "username": "carol"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/member"
        return _json({"members": members})

    assert make_client(handler).get_task_members("t1") == members


def test_get_task_time_in_status() -> None:
    data = {"current_status": {"status": "in progress", "total_time": {"by_minute": 100}}}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/time_in_status"
        return _json(data)

    assert make_client(handler).get_task_time_in_status("t1") == data


def test_add_dependency_sends_depends_on() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/dependency"
        assert req.method == "POST"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).add_dependency("t1", depends_on="t2")
    assert captured == {"depends_on": "t2"}


def test_remove_dependency_passes_query_param() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/dependency"
        assert req.method == "DELETE"
        assert req.url.params.get("depends_on") == "t2"
        return _json({})

    result = make_client(handler).remove_dependency("t1", depends_on="t2")
    assert result == {"deleted": "t1"}


def test_add_task_link() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/link/t2"
        assert req.method == "POST"
        return _json({"task": {"id": "t1"}})

    result = make_client(handler).add_task_link("t1", "t2")
    assert isinstance(result, dict)


def test_remove_task_link() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/link/t2"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).remove_task_link("t1", "t2") == {"deleted": "t1"}


def test_move_task() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/move"
        assert req.method == "POST"
        captured.update(json.loads(req.content))
        return _json({"id": "t1"})

    make_client(handler).move_task("t1", "l2")
    assert captured == {"list_id": "l2"}


# ── Checklists ─────────────────────────────────────────────────────────────


def test_create_checklist() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/checklist"
        captured.update(json.loads(req.content))
        return _json({"checklist": {"id": "cl1"}})

    make_client(handler).create_checklist("t1", "Acceptance Criteria")
    assert captured["name"] == "Acceptance Criteria"


def test_delete_checklist_item() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/checklist/cl1/checklist_item/ci1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_checklist_item("cl1", "ci1") == {"deleted": "ci1"}


def test_update_checklist_item_sends_resolved() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/checklist/cl1/checklist_item/ci1"
        assert req.method == "PUT"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).update_checklist_item("cl1", "ci1", resolved=True)
    assert captured == {"resolved": True}


# ── Comments extras ────────────────────────────────────────────────────────


def test_list_list_comments() -> None:
    comments = [{"id": "c1", "comment_text": "hi"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/l1/comment"
        return _json({"comments": comments})

    assert make_client(handler).list_list_comments("l1") == comments


def test_update_comment() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/comment/c1"
        assert req.method == "PUT"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).update_comment("c1", "revised text")
    assert captured == {"comment_text": "revised text"}


def test_delete_comment() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/comment/c1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_comment("c1") == {"deleted": "c1"}


# ── Custom field extras ────────────────────────────────────────────────────


def test_remove_custom_field_value() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/field/f1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).remove_custom_field_value("t1", "f1") == {"deleted": "f1"}


# ── Tags ───────────────────────────────────────────────────────────────────


def test_get_space_tags() -> None:
    tags = [{"name": "bug"}, {"name": "feature"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1/tag"
        return _json({"tags": tags})

    assert make_client(handler).get_space_tags("s1") == tags


def test_create_space_tag_with_colors() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1/tag"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).create_space_tag("s1", "urgent", bg_color="#ff0000", fg_color="#ffffff")
    assert captured == {"name": "urgent", "bg_color": "#ff0000", "fg_color": "#ffffff"}


def test_add_task_tag() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/tag/bug"
        assert req.method == "POST"
        return _json({})

    make_client(handler).add_task_tag("t1", "bug")


def test_remove_task_tag() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/task/t1/tag/bug"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).remove_task_tag("t1", "bug") == {"deleted": "bug"}


# ── Goals & Key Results ────────────────────────────────────────────────────


def test_list_goals_unwraps_key() -> None:
    goals = [{"id": "g1", "name": "Ship v2"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/goal"
        return _json({"goals": goals})

    assert make_client(handler).list_goals() == goals


def test_create_goal_sends_body() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/goal"
        captured.update(json.loads(req.content))
        return _json({"goal": {"id": "g2"}})

    make_client(handler).create_goal("Ship v2", due_date=1700000000000, color="#0099cc")
    assert captured["name"] == "Ship v2"
    assert captured["color"] == "#0099cc"


def test_create_key_result() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/goal/g1/key_result"
        captured.update(json.loads(req.content))
        return _json({"key_result": {"id": "kr1"}})

    make_client(handler).create_key_result("g1", "Signups", "number", 0, 1000, "users")
    assert captured == {
        "name": "Signups",
        "type": "number",
        "steps_start": 0,
        "steps_end": 1000,
        "unit": "users",
    }


def test_update_key_result() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/key_result/kr1"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).update_key_result("kr1", 500, note="Halfway!")
    assert captured == {"steps_current": 500, "note": "Halfway!"}


# ── Views ──────────────────────────────────────────────────────────────────


def test_list_space_views() -> None:
    views = [{"id": "v1", "name": "Board"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/space/s1/view"
        return _json({"views": views})

    assert make_client(handler).list_space_views("s1") == views


def test_get_view_tasks_passes_page() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/view/v1/task"
        assert req.url.params.get("page") == "2"
        return _json({"tasks": []})

    make_client(handler).get_view_tasks("v1", page=2)


def test_create_view() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/list/l1/view"
        captured.update(json.loads(req.content))
        return _json({"view": {"id": "v2"}})

    make_client(handler).create_view("l1", "Kanban", "board")
    assert captured == {"name": "Kanban", "type": "board"}


def test_delete_view() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/view/v1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_view("v1") == {"deleted": "v1"}


# ── Webhooks ───────────────────────────────────────────────────────────────


def test_list_webhooks() -> None:
    hooks = [{"id": "wh1", "endpoint": "https://example.com/hook"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/webhook"
        return _json({"webhooks": hooks})

    assert make_client(handler).list_webhooks() == hooks


def test_create_webhook_sends_events() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/webhook"
        captured.update(json.loads(req.content))
        return _json({"id": "wh2"})

    make_client(handler).create_webhook("https://my.app/hook", ["taskCreated", "taskUpdated"])
    assert captured["endpoint"] == "https://my.app/hook"
    assert captured["events"] == ["taskCreated", "taskUpdated"]


def test_delete_webhook() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/webhook/wh1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_webhook("wh1") == {"deleted": "wh1"}


# ── Time Tracking ──────────────────────────────────────────────────────────


def test_get_time_entries_unwraps_data() -> None:
    entries = [{"id": "te1", "duration": "3600000"}]

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/time_entries"
        return _json({"data": entries})

    assert make_client(handler).get_time_entries() == entries


def test_get_time_entries_passes_filters() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params.get("start_date") == "1700000000000"
        assert req.url.params.get("assignee") == "42"
        return _json({"data": []})

    make_client(handler).get_time_entries(start_date=1700000000000, assignee=42)


def test_create_time_entry_body() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/time_entries"
        assert req.method == "POST"
        captured.update(json.loads(req.content))
        return _json({"data": {"id": "te2"}})

    make_client(handler).create_time_entry(1700000000000, 3600000, task_id="t1", billable=True)
    assert captured["start"] == 1700000000000
    assert captured["duration"] == 3600000
    assert captured["billable"] is True


def test_start_timer() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/time_entries/start"
        assert req.method == "POST"
        return _json({"data": {"id": "te3"}})

    result = make_client(handler).start_timer(task_id="t1")
    assert isinstance(result, dict)


def test_stop_timer() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/time_entries/stop"
        assert req.method == "POST"
        return _json({"data": {"id": "te3"}})

    make_client(handler).stop_timer()


def test_delete_time_entry() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v2/team/team1/time_entries/te1"
        assert req.method == "DELETE"
        return _json({})

    assert make_client(handler).delete_time_entry("te1") == {"deleted": "te1"}
