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

    def list_members(
        self, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> list[JsonValue]:
        """List all members of a workspace.

        Args:
            workspace_id: Explicit workspace id (wins if provided).
            workspace_name: Workspace name to look up (case-insensitive).

        Returns:
            List of member objects, each with ``id``, ``username``, ``email``, ``role``,
            and other profile fields.
        """
        # ClickUp API v2 has no /team/{id}/member endpoint; members are embedded
        # in each workspace object returned by GET /team. Resolve + extract in one
        # pass to avoid a second network round-trip.
        teams = self.list_workspaces()
        workspace = self._find_workspace(teams, workspace_id, workspace_name)
        members = workspace.get("members", [])
        return members if isinstance(members, list) else []

    def _find_workspace(
        self,
        teams: list[JsonValue],
        workspace_id: str | None,
        workspace_name: str | None,
    ) -> dict[str, JsonValue]:
        """Return the workspace dict matching the given id, name, or configured default.

        Args:
            teams: List of workspace objects from the API.
            workspace_id: Explicit workspace id (wins if provided).
            workspace_name: Workspace name to match (case-insensitive).

        Returns:
            The matching workspace dict.

        Raises:
            ValueError: If no match is found or resolution is ambiguous.
        """
        dicts = [t for t in teams if isinstance(t, dict)]
        if workspace_id:
            for t in dicts:
                if str(t.get("id")) == workspace_id:
                    return t
            raise ValueError(f"no workspace with id {workspace_id!r}")
        if workspace_name:
            matches = [t for t in dicts if str(t.get("name", "")).lower() == workspace_name.lower()]
            if not matches:
                names = [str(t.get("name")) for t in dicts]
                raise ValueError(f"no workspace named {workspace_name!r}; available: {names}")
            if len(matches) > 1:
                raise ValueError(f"multiple workspaces named {workspace_name!r}; pass workspace_id")
            return matches[0]
        if self._team_id:
            for t in dicts:
                if str(t.get("id")) == self._team_id:
                    return t
            raise ValueError(f"configured workspace {self._team_id!r} not found in API response")
        raise ValueError("no workspace: pass workspace_id/workspace_name or set CLICKUP_TEAM_ID")

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

        # Resolve team once so paginated loops don't make repeated GET /team calls.
        team_path = (
            f"/list/{list_id}/task"
            if list_id
            else f"/team/{self._resolve_team(workspace_id, workspace_name)}/task"
        )

        def _page(p: int) -> list[JsonValue]:
            params["page"] = p
            data = self._request("GET", team_path, params=params)
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
            for t in matched:
                _resolve_dropdown_fields(t)
            return {"tasks": matched, "has_more": capped}

        tasks = _page(page)
        for t in tasks:
            _resolve_dropdown_fields(t)
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
        task = self._request("GET", f"/task/{task_id}", params=params)
        _resolve_dropdown_fields(task)
        return task

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
        parent: str | None = None,
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
            parent: Optional id of an existing task; when set, the new task is created as a
                subtask of that task. The parent must live in the same list (``list_id``).
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
        if parent is not None:
            body["parent"] = parent
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

    def list_custom_fields(
        self,
        *,
        list_id: str | None = None,
        folder_id: str | None = None,
        space_id: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
    ) -> list[JsonValue]:
        """List the custom fields accessible at one hierarchy scope.

        Provide one scope. The scopes are **not** hierarchical: each endpoint returns only
        the fields *defined at that level*. A field created on a list is not returned by the
        folder/space/workspace query, and vice versa — so to find the field that applies to a
        given task, query the list the task lives in (or inspect ``get_task``'s
        ``custom_fields``). For a ``drop_down`` field, the selectable options (each with its
        ``id`` and ``name``) are under ``type_config.options``; those option ids are what
        :meth:`set_custom_field_value` expects.

        Args:
            list_id: List scope.
            folder_id: Folder scope.
            space_id: Space scope.
            workspace_id: Workspace (team) scope, by id.
            workspace_name: Workspace (team) scope, by name.

        Returns:
            The list of custom-field definitions at the chosen scope.

        Raises:
            ValueError: If none of the list/folder/space scopes is given and no workspace
                resolves (no ``workspace_id``/``workspace_name`` and no ``CLICKUP_TEAM_ID``).
        """
        if list_id:
            path = f"/list/{list_id}/field"
        elif folder_id:
            path = f"/folder/{folder_id}/field"
        elif space_id:
            path = f"/space/{space_id}/field"
        else:
            team = self._resolve_team(workspace_id, workspace_name)
            path = f"/team/{team}/field"
        result = self._field(self._request("GET", path), "fields")
        return result if isinstance(result, list) else []

    def set_custom_field_value(
        self, task_id: str, field_id: str, value: str | int | float | bool | list[str]
    ) -> JsonValue:
        """Set a custom field's value on a task.

        Args:
            task_id: Target task id.
            field_id: The custom field's UUID (from :meth:`list_custom_fields` or ``get_task``).
            value: The new value, shaped per the field type. For a ``drop_down`` field this
                is the chosen option's UUID ``id`` (ClickUp also accepts the option's integer
                ``orderindex``); for text/url/email/phone a string; for number/money a number;
                for date a Unix ms timestamp.
        """
        return self._request("POST", f"/task/{task_id}/field/{field_id}", json={"value": value})

    def get_authorized_user(self) -> JsonValue:
        """Return the ClickUp user associated with the configured API key."""
        return self._request("GET", "/user")

    def get_space(self, space_id: str) -> JsonValue:
        """Get a single space by id."""
        return self._request("GET", f"/space/{space_id}")

    def create_space(
        self, name: str, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> JsonValue:
        """Create a new space in a workspace."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        body["name"] = name
        return self._request("POST", f"/team/{team}/space", json=body)

    def update_space(
        self,
        space_id: str,
        *,
        name: str | None = None,
        color: str | None = None,
        private: bool | None = None,
    ) -> JsonValue:
        """Update a space. Pass only the fields to change."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if color is not None:
            body["color"] = color
        if private is not None:
            body["private"] = private
        return self._request("PUT", f"/space/{space_id}", json=body)

    def delete_space(self, space_id: str) -> JsonValue:
        """Permanently delete a space."""
        self._request("DELETE", f"/space/{space_id}")
        return {"deleted": space_id}

    def get_folder(self, folder_id: str) -> JsonValue:
        """Get a single folder by id."""
        return self._request("GET", f"/folder/{folder_id}")

    def create_folder(self, space_id: str, name: str) -> JsonValue:
        """Create a folder inside a space."""
        body: dict[str, object] = {}
        body["name"] = name
        return self._request("POST", f"/space/{space_id}/folder", json=body)

    def update_folder(self, folder_id: str, name: str) -> JsonValue:
        """Rename a folder."""
        body: dict[str, object] = {}
        body["name"] = name
        return self._request("PUT", f"/folder/{folder_id}", json=body)

    def delete_folder(self, folder_id: str) -> JsonValue:
        """Permanently delete a folder."""
        self._request("DELETE", f"/folder/{folder_id}")
        return {"deleted": folder_id}

    def get_list(self, list_id: str) -> JsonValue:
        """Get a single list by id."""
        return self._request("GET", f"/list/{list_id}")

    def get_list_members(self, list_id: str) -> list[JsonValue]:
        """List members who have access to a list."""
        result = self._field(self._request("GET", f"/list/{list_id}/member"), "members")
        return result if isinstance(result, list) else []

    def create_list(
        self,
        folder_id: str,
        name: str,
        *,
        status: str | None = None,
        due_date: int | None = None,
        priority: int | None = None,
        assignee: int | None = None,
    ) -> JsonValue:
        """Create a list in a folder.

        priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
        """
        body: dict[str, object] = {}
        body["name"] = name
        if status is not None:
            body["status"] = status
        if due_date is not None:
            body["due_date"] = due_date
        if priority is not None:
            body["priority"] = priority
        if assignee is not None:
            body["assignee"] = assignee
        return self._request("POST", f"/folder/{folder_id}/list", json=body)

    def create_folderless_list(
        self,
        space_id: str,
        name: str,
        *,
        status: str | None = None,
        due_date: int | None = None,
        priority: int | None = None,
        assignee: int | None = None,
    ) -> JsonValue:
        """Create a folderless list in a space.

        priority: 1=urgent 2=high 3=normal 4=low; due_date: Unix ms.
        """
        body: dict[str, object] = {}
        body["name"] = name
        if status is not None:
            body["status"] = status
        if due_date is not None:
            body["due_date"] = due_date
        if priority is not None:
            body["priority"] = priority
        if assignee is not None:
            body["assignee"] = assignee
        return self._request("POST", f"/space/{space_id}/list", json=body)

    def update_list(
        self,
        list_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        due_date: int | None = None,
        priority: int | None = None,
    ) -> JsonValue:
        """Update a list. Pass only the fields to change; due_date is Unix ms."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if status is not None:
            body["status"] = status
        if due_date is not None:
            body["due_date"] = due_date
        if priority is not None:
            body["priority"] = priority
        return self._request("PUT", f"/list/{list_id}", json=body)

    def delete_list(self, list_id: str) -> JsonValue:
        """Permanently delete a list."""
        self._request("DELETE", f"/list/{list_id}")
        return {"deleted": list_id}

    def get_task_members(self, task_id: str) -> list[JsonValue]:
        """List members who are assigned to or watching a task."""
        result = self._field(self._request("GET", f"/task/{task_id}/member"), "members")
        return result if isinstance(result, list) else []

    def get_task_time_in_status(self, task_id: str) -> JsonValue:
        """Return the time a task has spent in each status."""
        return self._request("GET", f"/task/{task_id}/time_in_status")

    def add_dependency(
        self, task_id: str, *, depends_on: str | None = None, dependency_of: str | None = None
    ) -> JsonValue:
        """Add a dependency between tasks.

        depends_on: this task blocks on that one; dependency_of: that one blocks on this.
        """
        body: dict[str, object] = {}
        if depends_on is not None:
            body["depends_on"] = depends_on
        if dependency_of is not None:
            body["dependency_of"] = dependency_of
        return self._request("POST", f"/task/{task_id}/dependency", json=body)

    def remove_dependency(
        self, task_id: str, *, depends_on: str | None = None, dependency_of: str | None = None
    ) -> JsonValue:
        """Remove a dependency. Provide the same depends_on or dependency_of used when adding."""
        params: dict[str, object] = {}
        if depends_on is not None:
            params["depends_on"] = depends_on
        if dependency_of is not None:
            params["dependency_of"] = dependency_of
        self._request("DELETE", f"/task/{task_id}/dependency", params=params)
        return {"deleted": task_id}

    def add_task_link(self, task_id: str, links_to: str) -> JsonValue:
        """Create a link between two tasks."""
        return self._request("POST", f"/task/{task_id}/link/{links_to}")

    def remove_task_link(self, task_id: str, links_to: str) -> JsonValue:
        """Remove a link between two tasks."""
        self._request("DELETE", f"/task/{task_id}/link/{links_to}")
        return {"deleted": task_id}

    def move_task(self, task_id: str, list_id: str) -> JsonValue:
        """Move a task to a different list."""
        body: dict[str, object] = {}
        body["list_id"] = list_id
        return self._request("POST", f"/task/{task_id}/move", json=body)

    def create_checklist(self, task_id: str, name: str) -> JsonValue:
        """Create a checklist on a task."""
        body: dict[str, object] = {}
        body["name"] = name
        return self._request("POST", f"/task/{task_id}/checklist", json=body)

    def update_checklist(
        self, checklist_id: str, *, name: str | None = None, position: int | None = None
    ) -> JsonValue:
        """Rename a checklist or change its position."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if position is not None:
            body["position"] = position
        return self._request("PUT", f"/checklist/{checklist_id}", json=body)

    def delete_checklist(self, checklist_id: str) -> JsonValue:
        """Delete a checklist."""
        self._request("DELETE", f"/checklist/{checklist_id}")
        return {"deleted": checklist_id}

    def create_checklist_item(
        self, checklist_id: str, name: str, *, assignee: int | None = None
    ) -> JsonValue:
        """Add an item to a checklist."""
        body: dict[str, object] = {}
        body["name"] = name
        if assignee is not None:
            body["assignee"] = assignee
        return self._request("POST", f"/checklist/{checklist_id}/checklist_item", json=body)

    def update_checklist_item(
        self,
        checklist_id: str,
        checklist_item_id: str,
        *,
        name: str | None = None,
        resolved: bool | None = None,
        assignee: int | None = None,
    ) -> JsonValue:
        """Update a checklist item's name, resolution state, or assignee."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if resolved is not None:
            body["resolved"] = resolved
        if assignee is not None:
            body["assignee"] = assignee
        return self._request(
            "PUT", f"/checklist/{checklist_id}/checklist_item/{checklist_item_id}", json=body
        )

    def delete_checklist_item(self, checklist_id: str, checklist_item_id: str) -> JsonValue:
        """Delete a checklist item."""
        self._request("DELETE", f"/checklist/{checklist_id}/checklist_item/{checklist_item_id}")
        return {"deleted": checklist_item_id}

    def list_list_comments(self, list_id: str) -> list[JsonValue]:
        """List all comments on a list (not on a specific task)."""
        result = self._field(self._request("GET", f"/list/{list_id}/comment"), "comments")
        return result if isinstance(result, list) else []

    def create_list_comment(
        self, list_id: str, text: str, *, notify_all: bool = False
    ) -> JsonValue:
        """Post a comment on a list; set notify_all to notify all list members."""
        body: dict[str, object] = {}
        body["comment_text"] = text
        body["notify_all"] = notify_all
        return self._request("POST", f"/list/{list_id}/comment", json=body)

    def update_comment(self, comment_id: str, text: str) -> JsonValue:
        """Edit the text of an existing comment."""
        body: dict[str, object] = {}
        body["comment_text"] = text
        return self._request("PUT", f"/comment/{comment_id}", json=body)

    def delete_comment(self, comment_id: str) -> JsonValue:
        """Delete a comment."""
        self._request("DELETE", f"/comment/{comment_id}")
        return {"deleted": comment_id}

    def remove_custom_field_value(self, task_id: str, field_id: str) -> JsonValue:
        """Clear a custom field value on a task."""
        self._request("DELETE", f"/task/{task_id}/field/{field_id}")
        return {"deleted": field_id}

    def get_space_tags(self, space_id: str) -> list[JsonValue]:
        """List all tags defined in a space."""
        result = self._field(self._request("GET", f"/space/{space_id}/tag"), "tags")
        return result if isinstance(result, list) else []

    def create_space_tag(
        self, space_id: str, name: str, *, bg_color: str | None = None, fg_color: str | None = None
    ) -> JsonValue:
        """Create a tag in a space. Colors are hex strings (e.g. '#ff0000')."""
        body: dict[str, object] = {}
        body["name"] = name
        if bg_color is not None:
            body["bg_color"] = bg_color
        if fg_color is not None:
            body["fg_color"] = fg_color
        return self._request("POST", f"/space/{space_id}/tag", json=body)

    def update_space_tag(
        self,
        space_id: str,
        tag_name: str,
        *,
        name: str | None = None,
        bg_color: str | None = None,
        fg_color: str | None = None,
    ) -> JsonValue:
        """Update a space tag's name or colors."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if bg_color is not None:
            body["bg_color"] = bg_color
        if fg_color is not None:
            body["fg_color"] = fg_color
        return self._request("PUT", f"/space/{space_id}/tag/{tag_name}", json=body)

    def delete_space_tag(self, space_id: str, tag_name: str) -> JsonValue:
        """Delete a tag from a space."""
        self._request("DELETE", f"/space/{space_id}/tag/{tag_name}")
        return {"deleted": tag_name}

    def add_task_tag(self, task_id: str, tag_name: str) -> JsonValue:
        """Add a tag to a task."""
        return self._request("POST", f"/task/{task_id}/tag/{tag_name}")

    def remove_task_tag(self, task_id: str, tag_name: str) -> JsonValue:
        """Remove a tag from a task."""
        self._request("DELETE", f"/task/{task_id}/tag/{tag_name}")
        return {"deleted": tag_name}

    def list_goals(
        self, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> list[JsonValue]:
        """List all goals in a workspace."""
        team = self._resolve_team(workspace_id, workspace_name)
        result = self._field(self._request("GET", f"/team/{team}/goal"), "goals")
        return result if isinstance(result, list) else []

    def get_goal(self, goal_id: str) -> JsonValue:
        """Get a single goal by id."""
        return self._request("GET", f"/goal/{goal_id}")

    def create_goal(
        self,
        name: str,
        *,
        due_date: int | None = None,
        description: str | None = None,
        color: str | None = None,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
    ) -> JsonValue:
        """Create a goal in a workspace. due_date is Unix ms."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        body["name"] = name
        if due_date is not None:
            body["due_date"] = due_date
        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        return self._request("POST", f"/team/{team}/goal", json=body)

    def update_goal(
        self,
        goal_id: str,
        *,
        name: str | None = None,
        due_date: int | None = None,
        description: str | None = None,
        color: str | None = None,
    ) -> JsonValue:
        """Update a goal. Pass only the fields to change."""
        body: dict[str, object] = {}
        if name is not None:
            body["name"] = name
        if due_date is not None:
            body["due_date"] = due_date
        if description is not None:
            body["description"] = description
        if color is not None:
            body["color"] = color
        return self._request("PUT", f"/goal/{goal_id}", json=body)

    def delete_goal(self, goal_id: str) -> JsonValue:
        """Delete a goal."""
        self._request("DELETE", f"/goal/{goal_id}")
        return {"deleted": goal_id}

    def create_key_result(
        self,
        goal_id: str,
        name: str,
        type: str,
        steps_start: int,
        steps_end: int,
        unit: str,
        *,
        task_ids: list[str] | None = None,
        list_ids: list[str] | None = None,
    ) -> JsonValue:
        """Add a key result to a goal. type: number|currency|boolean|percentage|automatic."""
        body: dict[str, object] = {}
        body["name"] = name
        body["type"] = type
        body["steps_start"] = steps_start
        body["steps_end"] = steps_end
        body["unit"] = unit
        if task_ids is not None:
            body["task_ids"] = task_ids
        if list_ids is not None:
            body["list_ids"] = list_ids
        return self._request("POST", f"/goal/{goal_id}/key_result", json=body)

    def update_key_result(
        self, key_result_id: str, steps_current: int, *, note: str | None = None
    ) -> JsonValue:
        """Update a key result's current progress."""
        body: dict[str, object] = {}
        body["steps_current"] = steps_current
        if note is not None:
            body["note"] = note
        return self._request("PUT", f"/key_result/{key_result_id}", json=body)

    def delete_key_result(self, key_result_id: str) -> JsonValue:
        """Delete a key result."""
        self._request("DELETE", f"/key_result/{key_result_id}")
        return {"deleted": key_result_id}

    def list_workspace_views(
        self, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> list[JsonValue]:
        """List all views in a workspace."""
        team = self._resolve_team(workspace_id, workspace_name)
        result = self._field(self._request("GET", f"/team/{team}/view"), "views")
        return result if isinstance(result, list) else []

    def list_space_views(self, space_id: str) -> list[JsonValue]:
        """List all views in a space."""
        result = self._field(self._request("GET", f"/space/{space_id}/view"), "views")
        return result if isinstance(result, list) else []

    def list_folder_views(self, folder_id: str) -> list[JsonValue]:
        """List all views in a folder."""
        result = self._field(self._request("GET", f"/folder/{folder_id}/view"), "views")
        return result if isinstance(result, list) else []

    def list_list_views(self, list_id: str) -> list[JsonValue]:
        """List all views in a list."""
        result = self._field(self._request("GET", f"/list/{list_id}/view"), "views")
        return result if isinstance(result, list) else []

    def get_view(self, view_id: str) -> JsonValue:
        """Get a single view by id."""
        return self._request("GET", f"/view/{view_id}")

    def get_view_tasks(self, view_id: str, *, page: int = 0) -> JsonValue:
        """Get tasks visible in a view. Returns one page; increment page to paginate."""
        params: dict[str, object] = {}
        if page is not None:
            params["page"] = page
        return self._request("GET", f"/view/{view_id}/task", params=params)

    def create_view(self, list_id: str, name: str, type: str) -> JsonValue:
        """Create a view on a list. type: list|board|calendar|table|gantt|activity|workload."""
        body: dict[str, object] = {}
        body["name"] = name
        body["type"] = type
        return self._request("POST", f"/list/{list_id}/view", json=body)

    def update_view(self, view_id: str, name: str, type: str) -> JsonValue:
        """Update a view's name or type."""
        body: dict[str, object] = {}
        body["name"] = name
        body["type"] = type
        return self._request("PUT", f"/view/{view_id}", json=body)

    def delete_view(self, view_id: str) -> JsonValue:
        """Delete a view."""
        self._request("DELETE", f"/view/{view_id}")
        return {"deleted": view_id}

    def list_webhooks(
        self, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> list[JsonValue]:
        """List all webhooks in a workspace."""
        team = self._resolve_team(workspace_id, workspace_name)
        result = self._field(self._request("GET", f"/team/{team}/webhook"), "webhooks")
        return result if isinstance(result, list) else []

    def create_webhook(
        self,
        endpoint: str,
        events: list[str],
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
    ) -> JsonValue:
        """Register a webhook. events: list of event names, or ['*'] for all events."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        body["endpoint"] = endpoint
        body["events"] = events
        return self._request("POST", f"/team/{team}/webhook", json=body)

    def update_webhook(
        self,
        webhook_id: str,
        *,
        endpoint: str | None = None,
        events: list[str] | None = None,
        status: str | None = None,
    ) -> JsonValue:
        """Update a webhook's endpoint URL, subscribed events, or status ('active' | 'inactive')."""
        body: dict[str, object] = {}
        if endpoint is not None:
            body["endpoint"] = endpoint
        if events is not None:
            body["events"] = events
        if status is not None:
            body["status"] = status
        return self._request("PUT", f"/webhook/{webhook_id}", json=body)

    def delete_webhook(self, webhook_id: str) -> JsonValue:
        """Delete a webhook."""
        self._request("DELETE", f"/webhook/{webhook_id}")
        return {"deleted": webhook_id}

    def get_time_entries(
        self,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        start_date: int | None = None,
        end_date: int | None = None,
        assignee: int | None = None,
        task_id: str | None = None,
    ) -> list[JsonValue]:
        """Get time entries for a workspace. start_date/end_date are Unix ms timestamps."""
        team = self._resolve_team(workspace_id, workspace_name)
        params: dict[str, object] = {}
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if assignee is not None:
            params["assignee"] = assignee
        if task_id is not None:
            params["task_id"] = task_id
        result = self._field(
            self._request("GET", f"/team/{team}/time_entries", params=params), "data"
        )
        return result if isinstance(result, list) else []

    def get_running_time_entry(
        self, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> JsonValue:
        """Get the currently running time entry for the workspace, if any."""
        team = self._resolve_team(workspace_id, workspace_name)
        return self._request("GET", f"/team/{team}/time_entries/current")

    def create_time_entry(
        self,
        start: int,
        duration: int,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        task_id: str | None = None,
        description: str | None = None,
        billable: bool = False,
    ) -> JsonValue:
        """Manually log a time entry. start is Unix ms; duration is milliseconds."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        body["start"] = start
        body["duration"] = duration
        if task_id is not None:
            body["task_id"] = task_id
        if description is not None:
            body["description"] = description
        body["billable"] = billable
        return self._request("POST", f"/team/{team}/time_entries", json=body)

    def start_timer(
        self,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        task_id: str | None = None,
        description: str | None = None,
        billable: bool = False,
    ) -> JsonValue:
        """Start a new timer. Stops any currently running timer."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        if task_id is not None:
            body["task_id"] = task_id
        if description is not None:
            body["description"] = description
        body["billable"] = billable
        return self._request("POST", f"/team/{team}/time_entries/start", json=body)

    def stop_timer(
        self, *, workspace_id: str | None = None, workspace_name: str | None = None
    ) -> JsonValue:
        """Stop the currently running timer."""
        team = self._resolve_team(workspace_id, workspace_name)
        return self._request("POST", f"/team/{team}/time_entries/stop")

    def update_time_entry(
        self,
        time_entry_id: str,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
        start: int | None = None,
        duration: int | None = None,
        description: str | None = None,
        billable: bool | None = None,
    ) -> JsonValue:
        """Update a time entry. start is Unix ms; duration is ms."""
        team = self._resolve_team(workspace_id, workspace_name)
        body: dict[str, object] = {}
        if start is not None:
            body["start"] = start
        if duration is not None:
            body["duration"] = duration
        if description is not None:
            body["description"] = description
        if billable is not None:
            body["billable"] = billable
        return self._request("PUT", f"/team/{team}/time_entries/{time_entry_id}", json=body)

    def delete_time_entry(
        self,
        time_entry_id: str,
        *,
        workspace_id: str | None = None,
        workspace_name: str | None = None,
    ) -> JsonValue:
        """Delete a time entry."""
        team = self._resolve_team(workspace_id, workspace_name)
        self._request("DELETE", f"/team/{team}/time_entries/{time_entry_id}")
        return {"deleted": time_entry_id}


def _resolve_dropdown_fields(task: JsonValue) -> None:
    """Resolve drop_down custom-field integer orderindex values to option-name strings in-place.

    ClickUp returns ``"value": 0`` when the first dropdown option (orderindex 0) is selected and
    ``"value": null`` when nothing is selected.  Because 0 is falsy in Python (and JS), any code
    that checks ``if value:`` treats a zeroth-option selection identically to an unset field.
    This helper converts the raw integer to the human-readable option name so callers always see
    a string label or None, never a bare integer.
    """
    if not isinstance(task, dict):
        return
    custom_fields = task.get("custom_fields")
    if not isinstance(custom_fields, list):
        return
    for field in custom_fields:
        if not isinstance(field, dict) or field.get("type") != "drop_down":
            continue
        value = field.get("value")
        if value is None:
            continue
        type_config = field.get("type_config")
        if not isinstance(type_config, dict):
            continue
        options = type_config.get("options")
        if not isinstance(options, list):
            continue
        match = next(
            (opt for opt in options if isinstance(opt, dict) and opt.get("orderindex") == value),
            None,
        )
        if match is not None:
            field["value"] = match.get("name")


def _read_secret_file(path: str) -> str:
    """Read a secret from a file, stripping trailing whitespace/newline."""
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()
