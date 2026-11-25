"""Live Simulation page: playback, network, environment and run detail."""

from __future__ import annotations

import time
from typing import Any, Mapping

import pandas as pd
import streamlit as st

from ui import charts, components, state, theme
from ui.data import agent_type_label, scenario_label, system_label

CAPTION = (
    "Step the official simulation hour by hour. Market and storage decisions stay "
    "inside the production modules; the console only calls GridModel with the "
    "sidebar configuration and reads its snapshots."
)


def _header(model: Any | None = None, snapshot: Mapping[str, Any] | None = None) -> None:
    system = str(
        (snapshot or {}).get("mode") or st.session_state.get("ui_mode", "auction")
    )
    scenario = str(
        (snapshot or {}).get("scenario") or st.session_state.get("ui_scenario", "normal")
    )
    badges = [
        components.badge(system_label(system), tone="accent"),
        components.badge(scenario_label(scenario)),
    ]
    if model is None:
        badges.append(components.badge("Not started", tone="warning", dot=True))
    else:
        badges.append(
            components.status_badge(
                running=state.running(),
                finished=bool(model.clock.is_finished),
            )
        )
    components.page_header(
        "Simulation console",
        "Live simulation",
        CAPTION,
        badges=badges,
    )


def _grid_status(snapshot: Mapping[str, Any]) -> tuple[str, str, list[tuple[str, float]]]:
    """Classify the current hour from the snapshot (read-only)."""

    agents = snapshot.get("agents", {}) or {}
    unserved = snapshot.get("unserved", {}) or {}
    short = [(str(agent_id), float(value)) for agent_id, value in unserved.items() if float(value) > 1e-9]
    hospitals = [
        item for item in short if str((agents.get(item[0]) or {}).get("type", "")) == "hospital"
    ]
    if hospitals:
        return "critical", "Critical", short
    if short:
        return "warning", "Shortage", short
    if snapshot.get("active_events"):
        return "event", "Event active", []
    return "normal", "Nominal", []


def _alert(snapshot: Mapping[str, Any], level: str, short: list[tuple[str, float]]) -> None:
    """Show a banner when load is unserved or a disruption is active."""

    if level == "normal":
        return
    agents = snapshot.get("agents", {}) or {}
    events = ", ".join(
        str(name).replace("_", " ").title() for name in (snapshot.get("active_events", []) or [])
    )
    if level in ("critical", "warning"):
        ranked = sorted(short, key=lambda item: item[1], reverse=True)
        parts = [
            f"{agent_type_label(str((agents.get(agent_id) or {}).get('type', 'unknown')))} "
            f"{agent_id.replace('_', ' ').title()} <strong>{value:,.2f} MW</strong>"
            for agent_id, value in ranked[:3]
        ]
        extra = f" and {len(ranked) - 3} more" if len(ranked) > 3 else ""
        total = sum(value for _, value in short)
        body = f"Unserved this hour: {', '.join(parts)}{extra} · total <strong>{total:,.2f} MW</strong>."
        if events:
            body += f" Active disruption: {events}."
        title = "Hospital supply at risk" if level == "critical" else "Demand is not fully served"
    else:
        title = "Disruption active"
        body = f"{events}. All demand is currently served."
    components.alert_banner(level=level, title=title, body_html=body)


def _playback(model: Any) -> bool:
    """Render playback controls and return the post-click running state."""

    running = state.running()
    finished = bool(model.clock.is_finished)
    snapshot = model.snapshot()
    component = snapshot.get("environment", {}) or {}
    level, level_label, short = _grid_status(snapshot)
    with st.container(key="gm-controlbar"):
        components.control_bar(
            t=int(snapshot.get("t", 0)),
            steps=int(snapshot.get("steps", 0)),
            day=int(snapshot.get("day", 0)),
            hour=int(snapshot.get("hour", 0)),
            speed=state.speed(),
            running=running,
            finished=finished,
            price=float(snapshot.get("price", 0.0)),
            supply=float(component.get("generation_total_mw", 0.0)),
            demand=float(component.get("demand_total_mw", 0.0)),
            level=level,
            level_label=level_label,
        )
        columns = st.columns(4)
        if columns[0].button(
            "Pause" if running else "Play",
            key="live_play",
            width="stretch",
            type="primary" if not running and not finished else "secondary",
            disabled=finished and not running,
        ):
            st.session_state["gm_running"] = not running
            st.rerun()
        if columns[1].button("Step 1h", key="live_step", width="stretch", disabled=finished):
            if state.safe_step(model):
                st.rerun()
        if columns[2].button("Run 10h", key="live_run10", width="stretch", disabled=finished):
            for _ in range(10):
                if model.clock.is_finished:
                    break
                if not state.safe_step(model):
                    break
            st.rerun()
        if columns[3].button("Reset", key="live_reset", width="stretch"):
            state.reset_model()
            try:
                state.ensure_model()
            except Exception:  # noqa: BLE001 - the rerun renders a readable error state
                pass
            st.rerun()
        st.progress(
            min(1.0, float(model.clock.progress)),
            text=f"{model.clock.t} / {model.clock.steps} simulated hours",
        )
    st.caption(
        f"Simulated {component.get('temperature_c', 0.0):.1f} °C · "
        f"cloud {component.get('effective_cloud_cover', 0.0):.0%} · "
        f"wind {component.get('wind_index', 0.0):.2f} · "
        f"solar {component.get('solar_profile', 0.0):.0%}"
    )
    _alert(snapshot, level, short)
    return state.running()


def _kpis(model: Any, snapshot: Mapping[str, Any], log: pd.DataFrame) -> None:
    environment = snapshot.get("environment", {}) or {}
    price = float(snapshot.get("price", 0.0))
    supplies = float(environment.get("generation_total_mw", 0.0))
    demand = float(environment.get("demand_total_mw", 0.0))
    unserved = float(snapshot.get("unserved_mw", 0.0))
    deferred = float(snapshot.get("deferred_mw", 0.0))
    history = log.tail(48) if log is not None and not log.empty else pd.DataFrame()

    def _delta(column: str) -> float | None:
        if log is None or log.empty or column not in log or len(log) < 2:
            return None
        return float(log[column].iloc[-1]) - float(log[column].iloc[-2])

    items = [
        components.Kpi(
            label="Simulation hour",
            value=f"{int(snapshot.get('t', 0))}",
            unit=f"/ {int(snapshot.get('steps', 0))} h",
            detail=(
                f"<strong>Day {int(snapshot.get('day', 0)) + 1}</strong> · "
                f"{int(snapshot.get('hour', 0)):02d}:00"
            ),
        ),
        components.Kpi(
            label="Clearing price",
            value=f"{price:,.2f}",
            unit="per MWh",
            detail=f"<strong>{system_label(str(snapshot.get('mode', 'auction')))}</strong>",
            tone="accent",
            delta=_delta("price"),
            delta_good="down",
            spark=history["price"].tolist() if "price" in history else None,
            help_text="Price returned by the auction or the central LP for this hour.",
        ),
        components.Kpi(
            label="Generation",
            value=f"{supplies:,.1f}",
            unit="MW",
            detail=(
                f"Demand <strong>{demand:,.0f} MW</strong> · "
                f"Δ {supplies - demand:+,.0f} MW"
            ),
            tone="info" if supplies >= demand else "warning",
            delta=_delta("supply"),
            delta_good="neutral",
            spark=history["supply"].tolist() if "supply" in history else None,
        ),
        components.Kpi(
            label="Unserved energy",
            value=f"{unserved:,.2f}",
            unit="MW",
            detail=(
                f"Cumulative <strong>{float(log['unserved_mw'].sum()):,.1f} MWh</strong>"
                if log is not None and not log.empty and "unserved_mw" in log
                else "No completed hours yet"
            ),
            tone="danger" if unserved > 1e-9 else "default",
            delta=_delta("unserved_mw"),
            delta_good="down",
            spark=history["unserved_mw"].tolist() if "unserved_mw" in history else None,
            help_text="Demand left unserved after the market or central dispatch clears.",
        ),
        components.Kpi(
            label="Deferred load",
            value=f"{deferred:,.2f}",
            unit="MW",
            detail=(
                f"Cumulative <strong>{float(log['deferred_mw'].sum()):,.1f} MWh</strong>"
                if log is not None and not log.empty and "deferred_mw" in log
                else "No completed hours yet"
            ),
            spark=history["deferred_mw"].tolist() if "deferred_mw" in history else None,
            help_text="Flexible demand shifted to a later hour instead of being shed.",
        ),
    ]
    components.kpi_grid(items)


def _agent_table(snapshot: Mapping[str, Any]) -> None:
    agents = pd.DataFrame(snapshot.get("agents", {}) or {}).T
    if agents.empty:
        components.empty_state(
            "No agents in this fleet",
            "The model snapshot did not contain agent state for the current hour.",
            icon="table",
        )
        return
    agents = agents.copy()
    if "role" in agents:
        agents["role"] = agents["role"].map(
            lambda value: str(value).replace("_", " ").title()
        )
    if "type" in agents:
        agents["type"] = agents["type"].map(agent_type_label)
    if "last_action" in agents:
        agents["last_action"] = agents["last_action"].map(
            lambda value: theme.ACTION_LABELS.get(int(value), str(value))
            if pd.notna(value)
            else "—"
        )
    preferred = [
        column
        for column in (
            "agent_id",
            "role",
            "type",
            "demand_mw",
            "available_mw",
            "capacity_mw",
            "soc",
            "bought_mw",
            "sold_mw",
            "deferred_mw",
            "unserved_mw",
            "markup",
            "last_action",
            "policy",
        )
        if column in agents.columns
    ]
    display = agents[preferred]
    config: dict[str, Any] = {}
    for column in ("demand_mw", "available_mw", "capacity_mw", "bought_mw", "sold_mw", "deferred_mw", "unserved_mw"):
        if column in display:
            config[column] = st.column_config.NumberColumn(column.replace("_mw", " (MW)").replace("_", " ").title(), format="%.2f")
    if "soc" in display:
        config["soc"] = st.column_config.ProgressColumn(
            "State of charge", min_value=0.0, max_value=1.0, format="percent"
        )
    if "markup" in display:
        config["markup"] = st.column_config.NumberColumn("Markup", format="percent")
    st.dataframe(display, width="stretch", hide_index=True, column_config=config)


def _step_log(log: pd.DataFrame) -> None:
    if log is None or log.empty:
        components.empty_state(
            "No completed hours",
            "The step log fills after the first simulated hour.",
            icon="table",
        )
        return
    columns = [
        column
        for column in ("t", "price", "supply", "demand", "unserved_mw", "deferred_mw", "messages")
        if column in log
    ]
    view = log[columns].tail(24).copy()
    if "t" in view:
        view = view.rename(columns={"t": "hour"})
    st.caption("The most recent 24 rows of the model's persisted step log.")
    st.dataframe(
        view,
        width="stretch",
        hide_index=True,
        column_config={
            "price": st.column_config.NumberColumn("Price", format="%.2f"),
            "supply": st.column_config.NumberColumn("Supply (MW)", format="%.2f"),
            "demand": st.column_config.NumberColumn("Demand (MW)", format="%.2f"),
            "unserved_mw": st.column_config.NumberColumn("Unserved (MW)", format="%.2f"),
            "deferred_mw": st.column_config.NumberColumn("Deferred (MW)", format="%.2f"),
        },
    )


def _manifest(model: Any, snapshot: Mapping[str, Any]) -> None:
    fleet = {
        "Hospitals": int(st.session_state.get("ui_hospitals", 2)),
        "Residential": int(st.session_state.get("ui_residential", 4)),
        "Factories": int(st.session_state.get("ui_factories", 3)),
        "Batteries": int(st.session_state.get("ui_batteries", 2)),
    }
    components.definition_grid(
        [
            ("System", system_label(str(snapshot.get("mode", "")))),
            ("Scenario", scenario_label(str(snapshot.get("scenario", "")))),
            ("Seed", str(int(snapshot.get("seed", 0)))),
            ("Horizon", f"{int(snapshot.get('steps', 0))} hours"),
            ("Progress", f"{int(snapshot.get('t', 0))} / {int(snapshot.get('steps', 0))} h"),
            ("Fleet", " · ".join(f"{name} {count}" for name, count in fleet.items())),
            ("Active events", ", ".join(snapshot.get("active_events", []) or []) or "none"),
            ("Scheduled events", str(len(snapshot.get("scheduled_events", []) or []))),
        ]
    )
    st.caption(
        "A new model is built when the system, scenario, seed or fleet changes. "
        "Runtime events are injected into the current model."
    )


def render() -> None:
    """Render the Live Simulation page."""

    try:
        model = state.ensure_model()
    except state.ModelBuildError as exc:
        _header()
        components.error_state(
            "This run could not start",
            str(exc),
            hint="Adjust the run settings in the sidebar, then open Live Simulation again.",
        )
        return
    except Exception as exc:  # noqa: BLE001 - surface backend failures in the UI
        _header()
        components.error_state(
            "This run could not start",
            f"{type(exc).__name__}: {exc}",
            hint="Check the configuration and the persisted Q-table.",
        )
        return

    _header(model)
    error = state.step_error()
    if error:
        components.error_state(
            "The simulation stopped during a step",
            error,
            hint="Playback has been paused. Reset the run or adjust the configuration.",
        )

    _playback(model)

    snapshot = model.snapshot()
    log = model.logger.get_log()
    _kpis(model, snapshot, log)

    with st.container(border=True):
        components.card_header(
            "Agent network",
            "Producers, consumers and storage around the clearing hub. Hover any node for its full state.",
            right_html=components.badge(
                "Central" if str(snapshot.get("mode", "")).startswith("central") else "Auction"
            ),
        )
        st.plotly_chart(
            charts.network_figure(snapshot),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    with st.container(key="gm-pair-live-context"):
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                components.card_header(
                    "Latest environment",
                    "A2/A3 weather, solar and wind measurements for this hour.",
                )
                components.environment_panel(snapshot.get("environment", {}) or {})
        with right:
            with st.container(border=True):
                components.card_header(
                    "Disruption schedule",
                    "Scenario events and runtime injections.",
                )
                components.event_timeline(snapshot, limit=4)

    with st.container(border=True):
        components.card_header(
            "Market and storage over time",
            "Clearing price, supply and demand, unserved energy and battery state of charge.",
            right_html=components.badge(
                f"{int(snapshot.get('t', 0))} hour recorded"
                if int(snapshot.get("t", 0)) == 1
                else f"{int(snapshot.get('t', 0))} hours recorded"
            ),
        )
        st.plotly_chart(
            charts.history_figure(log, snapshot.get("scheduled_events", [])),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    tabs = st.tabs(["Agent fleet", "Step log", "Run manifest"])
    with tabs[0]:
        _agent_table(snapshot)
    with tabs[1]:
        _step_log(log)
    with tabs[2]:
        _manifest(model, snapshot)

    if model.clock.is_finished:
        with st.container(border=True):
            components.callout(
                "Every scheduled hour is complete. The market board and experiment pages "
                "have the full run to inspect.",
                tone="success",
                title="Run complete.",
            )
            if st.button("Open Compare", key="live_open_compare", type="primary"):
                state.request_page("Compare")
                st.rerun()

    # Advance playback after the page is drawn, so charts and tables update live.
    if state.running() and not model.clock.is_finished:
        if state.safe_step(model):
            time.sleep(1.0 / state.speed())
            st.rerun()
    elif state.running() and model.clock.is_finished:
        st.session_state["gm_running"] = False