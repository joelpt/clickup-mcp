"""HTTP client for the ClickUp REST API v2.

A thin, synchronous wrapper around `httpx` exposing the operations the MCP server
and CLI need. All public methods return parsed JSON (`JsonValue`). API and usage
errors are raised as `ValueError` with a human-readable message — the MCP runtime
surfaces these as tool errors, and the CLI converts them to `{"error": msg}` on stderr.
"""

from __future__ import annotations

import os
from typing import TypeAlias

import httpx

JsonValue: TypeAlias = "dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None"

BASE_URL = "https://api.clickup.com/api/v2"
MAX_SEARCH_PAGES = 5  # client-side text search caps at 5 * 100 = 500 tasks
_PAGE_SIZE = 100


class ClickUpClient:
    """Synchronous ClickUp REST API v2 client.

    Args:
        api_key: ClickUp personal API token (``pk_...``), sent as the ``Authorization`` header.
        team_id: Default workspace (team) id used when a call omits an explicit workspace.
        base_url: API base URL; overridable for testing.
        timeout: Per-request timeout in seconds.
        transport: Optional `httpx` transport, used by tests to mock the network.
    """

    def __init__(
        self,
        api_key: str,
        team_id: str | None = None,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ClickUp API key is required")
        self._team_id = team_id
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": api_key},
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> ClickUpClient:
        """Build a client from environment variables.

        Reads the key from ``CLICKUP_API_KEY`` or, if unset, from the file named by
        ``CLICKUP_API_KEY_FILE`` (trailing whitespace stripped). The default workspace
        comes from ``CLICKUP_TEAM_ID``.

        Returns:
            A configured client.

        Raises:
            ValueError: If no API key can be found via either variable.
        """
        key = os.environ.get("CLICKUP_API_KEY")
        if not key:
            key_file = os.environ.get("CLICKUP_API_KEY_FILE")
            if key_file:
                try:
                    key = _read_secret_file(key_file)
                except OSError as exc:
                    raise ValueError(
                        f"cannot read CLICKUP_API_KEY_FILE ({key_file}): {exc}"
                    ) from exc
        if not key:
            raise ValueError("set CLICKUP_API_KEY or CLICKUP_API_KEY_FILE")
        return cls(key, os.environ.get("CLICKUP_TEAM_ID"))

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    def __enter__(self) -> ClickUpClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: object) -> JsonValue:
        """Perform a request and return parsed JSON, raising `ValueError` on API errors.

        Args:
            method: HTTP method.
            path: API path relative to the base URL.
            **kwargs: Passed through to `httpx.Client.request` (``params``, ``json``).

        Returns:
            Parsed JSON body, or ``{}`` for an empty response.

        Raises:
            ValueError: On rate limiting or any non-2xx response.
        """
        resp = self._http.request(method, path, **kwargs)  # type: ignore[arg-type]
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "unknown")
            raise ValueError(f"Rate limited by ClickUp. Retry after {retry_after}s.")
        if resp.is_error:
            detail = resp.text[:300]
            try:
                body = resp.json()
                if isinstance(body, dict):
                    detail = str(body.get("err") or body.get("message") or detail)
            except ValueError:
                pass
            raise ValueError(f"ClickUp API {resp.status_code}: {detail}")
        if not resp.content:
            return {}
        return resp.json()

    def _field(self, data: JsonValue, key: str) -> JsonValue:
        """Return ``data[key]``, raising if the response shape is unexpected."""
        if not isinstance(data, dict) or data.get(key) is None:
            raise ValueError(f"Unexpected API response: missing '{key}' field")
        return data[key]

    def _resolve_team(
        self, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> str:
        """Resolve a workspace (team) id from an explicit id, a name, or the default.

        Args:
            workspace_id: Explicit workspace id (wins if provided).
            workspace_name: Workspace name to look up via the API (case-insensitive).

        Returns:
            The resolved workspace id.

        Raises:
            ValueError: If a name matches zero or multiple workspaces, or if nothing
                resolves and no default ``CLICKUP_TEAM_ID`` is configured.
        """
        if workspace_id:
            return workspace_id
        if workspace_name:
            teams = self.list_workspaces()
            matches = [
                t
                for t in teams
                if isinstance(t, dict) and str(t.get("name", "")).lower() == workspace_name.lower()
            ]
            if not matches:
                names = [str(t.get("name")) for t in teams if isinstance(t, dict)]
                raise ValueError(f"no workspace named {workspace_name!r}; available: {names}")
            if len(matches) > 1:
                raise ValueError(f"multiple workspaces named {workspace_name!r}; pass workspace_id")
            return str(matches[0]["id"])
        if self._team_id:
            return self._team_id
        raise ValueError("no workspace: pass workspace_id/workspace_name or set CLICKUP_TEAM_ID")

    def list_workspaces(self) -> list[JsonValue]:
        """List all workspaces (teams) accessible to the API key."""
        result = self._field(self._request("GET", "/team"), "teams")
        return result if isinstance(result, list) else []

    def list_spaces(
        self, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> list[JsonValue]:
        """List non-archived spaces in a workspace."""
        team = self._resolve_team(workspace_id, workspace_name)
        result = self._field(
            self._request("GET", f"/team/{team}/space", params={"archived": "false"}), "spaces"
        )
        return result if isinstance(result, list) else []

    def list_folders(self, space_id: str) -> list[JsonValue]:
        """List non-archived folders in a space."""
        result = self._field(
            self._request("GET", f"/space/{space_id}/folder", params={"archived": "false"}),
            "folders",
        )
        return result if isinstance(result, list) else []

    def list_lists(
        self, space_id: str | None = None, folder_id: str | None = None
    ) -> list[JsonValue]:
        """List non-archived lists in a space or a folder.

        Raises:
            ValueError: If neither ``space_id`` nor ``folder_id`` is given.
        """
        if folder_id:
            path = f"/folder/{folder_id}/list"
        elif space_id:
            path = f"/space/{space_id}/list"
        else:
            raise ValueError("provide space_id or folder_id")
        result = self._field(self._request("GET", path, params={"archived": "false"}), "lists")
        return result if isinstance(result, list) else []

    def search_tasks(
        self,
        query: str | None = None,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        list_id: str | None = None,
        status: str | None = None,
        assignee: str | None = None,
        due_before: int | None = None,
        due_after: int | None = None,
        page: int = 0,
        include_subtasks: bool = True,
    ) -> dict[str, JsonValue]:
        """Search and filter tasks.

        With ``query``: fetches up to 500 tasks and filters by name substring client-side
        (ClickUp v2 has no server-side text search). Without ``query``: returns one
        server-filtered page; inspect ``has_more`` and use ``page`` to paginate.

        ``include_subtasks`` (default True) returns subtasks as their own top-level rows.
        They count against the 500-task ``query`` cap, so on a workspace with many subtasks
        they can crowd out top-level matches; pass False to search only top-level tasks.

        Returns:
            ``{"tasks": [...], "has_more": bool}``.
        """
        params: dict[str, object] = {}
        # The list/team task endpoints spell this flag "subtasks"; get_task spells it
        # "include_subtasks". Do not unify — they are distinct ClickUp API parameters.
        if include_subtasks:
            params["subtasks"] = "true"
        if status:
            params["statuses"] = status
        if assignee:
            params["assignees"] = assignee
        if due_before is not None:
            params["due_date_lt"] = due_before
        if due_after is not None:
            params["due_date_gt"] = due_after

        def _page(p: int) -> list[JsonValue]:
            params["page"] = p
            if list_id:
                path = f"/list/{list_id}/task"
            else:
                path = f"/team/{self._resolve_team(workspace_id, workspace_name)}/task"
            data = self._request("GET", path, params=params)
            tasks = data.get("tasks", []) if isinstance(data, dict) else []
            return tasks if isinstance(tasks, list) else []

        if query:
            collected: list[JsonValue] = []
            capped = True
            for p in range(MAX_SEARCH_PAGES):
                page_tasks = _page(p)
                collected.extend(page_tasks)
                if len(page_tasks) < _PAGE_SIZE:
                    capped = False
                    break
            q = query.lower()
            matched: list[JsonValue] = [
                t for t in collected if isinstance(t, dict) and q in str(t.get("name", "")).lower()
            ]
            return {"tasks": matched, "has_more": capped}

        tasks = _page(page)
        return {"tasks": tasks, "has_more": len(tasks) == _PAGE_SIZE}

    def get_task(self, task_id: str, *, include_subtasks: bool = True) -> JsonValue:
        """Get full details of a task by id.

        Args:
            task_id: The task id.
            include_subtasks: Attach the task's subtasks as a ``subtasks`` array when True
                (the default). Pass False when only the parent task's own fields are needed.
        """
        # "include_subtasks" here vs. "subtasks" on the search endpoints — see search_tasks.
        params = {"include_subtasks": "true"} if include_subtasks else None
        return self._request("GET", f"/task/{task_id}", params=params)

    def create_task(
        self,
        list_id: str,
        name: str,
        *,
        description: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        assignees: list[int] | None = None,
        due_date: int | None = None,
    ) -> JsonValue:
        """Create a task in a list.

        Args:
            list_id: Target list id.
            name: Task name.
            description: Optional description.
            status: Optional status string (e.g. ``"in progress"``).
            priority: Optional priority (1=urgent, 2=high, 3=normal, 4=low).
            assignees: Optional list of numeric user ids.
            due_date: Optional due date as a Unix ms timestamp.
        """
        body: dict[str, object] = {"name": name}
        if description is not None:
            body["description"] = description
        if status is not None:
            body["status"] = status
        if priority is not None:
            body["priority"] = priority
        if assignees:
            body["assignees"] = assignees
        if due_date is not None:
            body["due_date"] = due_date
        return self._request("POST", f"/list/{list_id}/task", json=body)

    def update_task(
        self,
        task_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        priority: int | None = None,
        add_assignees: list[int] | None = None,
        remove_assignees: list[int] | None = None,
        due_date: int | None = None,
    ) -> JsonValue:
        """Update an existing task. Pass an empty string to clear a text field."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        if status is not None:
            body["status"] = status
        if priority is not None:
            body["priority"] = priority
        if due_date is not None:
            body["due_date"] = due_date
        if add_assignees or remove_assignees:
            assignee_delta: dict[str, list[int]] = {}
            if add_assignees:
                assignee_delta["add"] = add_assignees
            if remove_assignees:
                assignee_delta["rem"] = remove_assignees
            body["assignees"] = assignee_delta
        return self._request("PUT", f"/task/{task_id}", json=body)

    def delete_task(self, task_id: str) -> JsonValue:
        """Permanently delete a task."""
        self._request("DELETE", f"/task/{task_id}")
        return {"deleted": task_id}

    def list_comments(self, task_id: str) -> list[JsonValue]:
        """List all comments on a task."""
        result = self._field(self._request("GET", f"/task/{task_id}/comment"), "comments")
        return result if isinstance(result, list) else []

    def add_comment(self, task_id: str, text: str, *, notify_all: bool = False) -> JsonValue:
        """Post a comment on a task.

        Args:
            task_id: Target task id.
            text: Comment body.
            notify_all: Notify all task watchers when True.
        """
        return self._request(
            "POST",
            f"/task/{task_id}/comment",
            json={"comment_text": text, "notify_all": notify_all},
        )


def _read_secret_file(path: str) -> str:
    """Read a secret from a file, stripping trailing whitespace/newline."""
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()
