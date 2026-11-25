"""Session-state helpers for the dashboard's simulation console.

The persisted Streamlit session owns one :class:`core.model.GridModel` at a
time. These helpers rebuild it when the run signature changes, keep the demo
navigation working across widget creation, and turn build/step exceptions into
UI state instead of uncaught tracebacks.
"""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

from core.config import load_config
from core.factory import build_model, with_fleet

LOGGER = logging.getLogger(__name__)

PAGES: tuple[str, ...] = ("Live Simulation", "Market Board", "Compare", "Learning")


class ModelBuildError(RuntimeError):
    """Raised when the current sidebar configuration cannot build a model."""


def consume_pending_navigation() -> None:
    """Apply demo/page navigation before any radio widget is instantiated."""

    pending_scenario = st.session_state.pop("gm_pending_scenario", None)
    if pending_scenario is not None:
        st.session_state["ui_scenario"] = pending_scenario
    pending_page = st.session_state.pop("gm_pending_page", None)
    if pending_page is not None:
        st.session_state["ui_page"] = pending_page


def request_demo() -> None:
    """Configure the official three-step demo without touching backend logic."""

    st.session_state["gm_pending_scenario"] = "combined"
    st.session_state["gm_pending_page"] = "Live Simulation"
    st.session_state["gm_autostart"] = True
    reset_model()


def request_page(page: str) -> None:
    """Queue navigation to another dashboard page on the next rerun."""

    if page not in PAGES:
        raise ValueError(f"unknown dashboard page {page!r}")
    st.session_state["gm_pending_page"] = page


def signature() -> tuple[Any, ...]:
    """Return the configuration tuple that identifies the current model."""

    return (
        st.session_state.get("ui_mode"),
        st.session_state.get("ui_scenario"),
        int(st.session_state.get("ui_seed", 0)),
        int(st.session_state.get("ui_hospitals", 2)),
        int(st.session_state.get("ui_residential", 4)),
        int(st.session_state.get("ui_factories", 3)),
        int(st.session_state.get("ui_batteries", 2)),
    )


def get_model() -> Any | None:
    """Return the current model without building one."""

    return st.session_state.get("gm_model")


def ensure_model() -> Any:
    """Return the current model, rebuilding it when the run signature changed."""

    current_signature = signature()
    model = st.session_state.get("gm_model")
    if model is not None and st.session_state.get("gm_signature") == current_signature:
        return model

    mode, scenario, seed, hospitals, residential, factories, batteries = current_signature
    config = load_config()
    try:
        fleet = with_fleet(
            config,
            hospitals=int(hospitals),
            residential=int(residential),
            factories=int(factories),
            batteries=max(1, int(batteries)),
        )
    except ValueError as exc:
        raise ModelBuildError(f"This agent fleet is not valid: {exc}") from exc
    try:
        model = build_model(fleet, int(seed), str(mode), str(scenario))
    except FileNotFoundError as exc:
        raise ModelBuildError(str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise ModelBuildError(str(exc)) from exc

    st.session_state["gm_model"] = model
    st.session_state["gm_signature"] = current_signature
    st.session_state["gm_running"] = bool(st.session_state.pop("gm_autostart", False))
    st.session_state.pop("gm_step_error", None)
    return model


def reset_model() -> None:
    """Discard the current model and pause playback."""

    st.session_state.pop("gm_model", None)
    st.session_state["gm_running"] = False
    st.session_state.pop("gm_step_error", None)
    st.session_state.pop("gm_learning_compare", None)


def safe_step(model: Any) -> bool:
    """Advance one hour and convert failures into a visible UI state."""

    try:
        model.step()
    except Exception as exc:  # noqa: BLE001 - the UI must surface any backend failure
        LOGGER.exception("Simulation step failed")
        st.session_state["gm_running"] = False
        st.session_state["gm_step_error"] = f"{type(exc).__name__}: {exc}"
        return False
    st.session_state.pop("gm_step_error", None)
    return True


def step_error() -> str | None:
    """Return the last simulation step error, if any."""

    value = st.session_state.get("gm_step_error")
    return str(value) if value else None


def running() -> bool:
    """Whether playback is currently enabled."""

    return bool(st.session_state.get("gm_running", False))


def speed() -> int:
    """Playback speed in simulated hours per second."""

    return max(1, int(st.session_state.get("ui_speed", 4)))
