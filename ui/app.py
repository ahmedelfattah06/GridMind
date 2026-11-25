"""GridMind Streamlit dashboard (Team D1).

Four pages read from the real simulation and the persisted experiment artefacts:

* **Live Simulation** — interactive network, environment, event timeline,
  price/supply/demand/SoC history and playback controls.
* **Market Board** — order depth, negotiation rounds, net positions, supply mix,
  message activity and hospital outage counters.
* **Compare** — saved experiment results, comparison matrices, statistical
  tables and the six report figures.
* **Learning** — Q-learning curve, learned policy heatmap, state explorer and a
  rule-vs-Q comparison on a selected scenario.

All market and agent decisions stay inside the production modules; the
dashboard only calls :class:`core.model.GridModel`, reads snapshots and loads
persisted files. Run from the repository root with::

    streamlit run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# The entry point must work when Streamlit is launched from another directory.
# Streamlit puts ``ui/`` on sys.path, not the repository root, so core imports
# would otherwise fail with ModuleNotFoundError: No module named 'core'.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

from core.config import OFFICIAL_SCENARIOS, OFFICIAL_SYSTEMS, load_config  # noqa: E402
from core.factory import default_fleet_counts  # noqa: E402
from ui import components, state, theme  # noqa: E402
from ui.data import scenario_description, scenario_label, system_label  # noqa: E402
from ui.views import compare, learning, live, market  # noqa: E402


def _inject_event(model: Any, name: str, duration: int, **params: Any) -> None:
    """Queue a runtime event on the current model."""

    counter = int(st.session_state.get("gm_event_counter", 0)) + 1
    st.session_state["gm_event_counter"] = counter
    try:
        model.inject_event(
            f"{name}_{counter}",
            duration=duration,
            t_start=model.clock.t,
            **params,
        )
    except ValueError as exc:
        st.sidebar.error(str(exc))
    else:
        st.sidebar.success(f"Event queued at hour {model.clock.t}.")


def _sidebar() -> str:
    """Render the product shell and return the selected page."""

    components.sidebar_brand(version="0.1.0")
    components.sidebar_section("Workspace")
    page = st.sidebar.radio(
        "Page",
        state.PAGES,
        key="ui_page",
        label_visibility="collapsed",
    )

    components.sidebar_section("Run settings")
    st.sidebar.selectbox(
        "System",
        OFFICIAL_SYSTEMS,
        format_func=system_label,
        key="ui_mode",
        help="Official systems: double auction, auction with the learned battery, "
        "and central LP dispatch re-optimised every 1 or 6 hours.",
    )
    st.sidebar.selectbox(
        "Scenario",
        OFFICIAL_SCENARIOS,
        format_func=scenario_label,
        key="ui_scenario",
    )
    st.sidebar.caption(scenario_description(str(st.session_state.get("ui_scenario", "normal"))))
    st.sidebar.number_input(
        "Seed",
        min_value=0,
        max_value=999_999,
        value=0,
        step=1,
        key="ui_seed",
    )

    config = load_config()
    defaults = default_fleet_counts(config)
    components.sidebar_section("Agent fleet")
    st.sidebar.slider("Hospitals", 1, 4, int(defaults["hospital"]), key="ui_hospitals")
    st.sidebar.slider("Residential", 1, 8, int(defaults["residential"]), key="ui_residential")
    st.sidebar.slider("Factories", 1, 6, int(defaults["factory"]), key="ui_factories")
    st.sidebar.slider("Batteries", 1, 4, int(defaults["battery"]), key="ui_batteries")
    st.sidebar.caption("Maximum 20 agents in total; the configuration enforces the cap.")

    components.sidebar_section("Playback")
    st.sidebar.slider("Speed (steps/s)", 1, 20, 4, key="ui_speed")
    if st.sidebar.button(
        "Demo script",
        key="gm_demo",
        type="primary",
        width="stretch",
        help="Load the combined scenario and autostart the Live Simulation.",
    ):
        state.request_demo()
        st.rerun()
    st.sidebar.caption("Demo: combined scenario, Live Simulation, autostart.")

    components.sidebar_section("Runtime events")
    model = state.get_model()
    disabled = model is None or bool(model.clock.is_finished)
    if model is None:
        st.sidebar.caption("Open Live Simulation once to create a model.")
    if st.sidebar.button("Trip thermal plant", disabled=disabled, width="stretch"):
        _inject_event(model, "ui_outage", duration=12, capacity_factor={"thermal": 0.3})
    if st.sidebar.button("Demand spike (+40%)", disabled=disabled, width="stretch"):
        _inject_event(model, "ui_spike", duration=6, demand_multiplier={"residential": 1.4})
    if st.sidebar.button("Weather shift", disabled=disabled, width="stretch"):
        _inject_event(
            model,
            "ui_weather",
            duration=24,
            cloud_override=0.2,
            capacity_factor={"wind": 0.5},
        )

    components.sidebar_section("Reference")
    st.sidebar.caption("4 official systems · 5 scenarios · 168-hour horizon")
    st.sidebar.caption("All values are read from the local simulation and experiment artefacts.")
    return page


def _app_meta() -> list[str]:
    """Return the compact status badges shown in the application bar."""

    return [
        components.badge("Local workspace", tone="accent", dot=True),
        components.badge("Official systems"),
        components.badge("168 h horizon"),
    ]


def main() -> None:
    """Render the GridMind dashboard."""

    st.set_page_config(
        page_title="GridMind · Energy market intelligence",
        page_icon=":material/bolt:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.inject_theme()
    state.consume_pending_navigation()

    page = _sidebar()
    components.app_header(meta_html=_app_meta())

    if page == "Live Simulation":
        live.render()
    elif page == "Market Board":
        market.render()
    elif page == "Compare":
        compare.render()
    else:
        learning.render()


if __name__ == "__main__":
    main()
