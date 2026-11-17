"""Shared pytest fixtures for the GridMind bootstrap tests."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from core.config import load_config


@pytest.fixture(scope="session")
def config() -> dict[str, Any]:
    """The validated default configuration, loaded once per test session."""

    return load_config()


@pytest.fixture()
def config_copy(config: dict[str, Any]) -> dict[str, Any]:
    """A deep copy of the default configuration, safe to mutate in a test."""

    return copy.deepcopy(config)
