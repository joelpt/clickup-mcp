"""Tests for the published package metadata."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def test_distribution_name_is_not_the_taken_pypi_name() -> None:
    project = tomllib.loads(PYPROJECT.read_text())["project"]
    assert project["name"] == "clickup-rest-mcp"


def test_scripts_resolve_to_callables() -> None:
    scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]
    assert {"clickup-rest-mcp", "clickup-mcp", "clickup"} <= set(scripts)
    for target in scripts.values():
        module, attr = target.split(":")
        assert callable(getattr(importlib.import_module(module), attr))


def test_server_scripts_share_one_entry_point() -> None:
    scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]
    assert scripts["clickup-rest-mcp"] == scripts["clickup-mcp"]
