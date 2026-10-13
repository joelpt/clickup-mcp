"""Tests for endpoints added from the ClickUp v2 OpenAPI spec gap analysis."""

from __future__ import annotations

import json
from typing import Any

import httpx

from tst.helpers import make_client


def _json(payload: object, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_list_comment_replies() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/api/v2/comment/c1/reply"
        return _json({"comments": [{"id": "r1"}]})

    assert make_client(handler).list_comment_replies("c1") == [{"id": "r1"}]


def test_create_comment_reply() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/v2/comment/c1/reply"
        captured.update(json.loads(req.content))
        return _json({"id": "r2"})

    make_client(handler).create_comment_reply("c1", "thanks", notify_all=True, assignee=7)
    assert captured == {"comment_text": "thanks", "notify_all": True, "assignee": 7}


def test_merge_tasks() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/v2/task/t1/merge"
        captured.update(json.loads(req.content))
        return _json({"id": "t1"})

    make_client(handler).merge_tasks("t1", ["a", "b"])
    assert captured == {"source_task_ids": ["a", "b"]}


def test_add_task_to_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/v2/list/l2/task/t1"
        return _json({})

    assert make_client(handler).add_task_to_list("t1", "l2") == {}


def test_remove_task_from_list() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        assert req.url.path == "/api/v2/list/l2/task/t1"
        return _json({})

    assert make_client(handler).remove_task_from_list("t1", "l2") == {"deleted": "t1"}


def test_list_time_entry_tags() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "GET"
        assert req.url.path == "/api/v2/team/team1/time_entries/tags"
        return _json({"data": [{"name": "billable"}]})

    assert make_client(handler).list_time_entry_tags() == [{"name": "billable"}]


def test_add_time_entry_tags() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/api/v2/team/team1/time_entries/tags"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).add_time_entry_tags(["e1"], ["billable"], tag_fg="#fff", tag_bg="#000")
    assert captured == {
        "time_entry_ids": ["e1"],
        "tags": [{"name": "billable", "tag_fg": "#fff", "tag_bg": "#000"}],
    }


def test_remove_time_entry_tags() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "DELETE"
        assert req.url.path == "/api/v2/team/team1/time_entries/tags"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).remove_time_entry_tags(["e1"], ["billable"])
    assert captured["time_entry_ids"] == ["e1"]
    assert [t["name"] for t in captured["tags"]] == ["billable"]


def test_rename_time_entry_tag() -> None:
    captured: dict[str, Any] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "PUT"
        assert req.url.path == "/api/v2/team/team1/time_entries/tags"
        captured.update(json.loads(req.content))
        return _json({})

    make_client(handler).rename_time_entry_tag("old", "new", tag_fg="#fff", tag_bg="#000")
    assert captured == {"name": "old", "new_name": "new", "tag_fg": "#fff", "tag_bg": "#000"}
