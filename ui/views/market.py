"""Market Board page: order book, rounds, positions and clearing activity."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from ui import charts, components, state, theme
from ui.data import scenario_label, system_label

ORDER_COLUMNS = ("round", "agent_id", "side", "qty_mw", "price", "priority")
TRADE_COLUMNS = ("buyer_id", "seller_id", "qty_mw", "price")


def _frame(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> pd.DataFrame:
    frame = pd.DataFrame(list(rows))
    if frame.empty:
        return pd.DataFrame(columns=list(columns))
    return frame


def _header(snapshot: Mapping[str, Any] | None = None) -> None:
    system = str((snapshot or {}).get("mode") or st.session_state.get("ui_mode", "auction"))
    scenario = str(
        (snapshot or {}).get("scenario") or st.session_state.get("ui_scenario", "normal")
    )
    badges = [
        components.badge(system_label(system), tone="accent"),
        components.badge(scenario_label(scenario)),
    ]
    if snapshot:
        badges.append(components.badge(f"Hour {int(snapshot.get('t', 0))}"))
    components.page_header(
        "Market microstructure",
        "Market board",
        "Inspect the final clearing hour: cumulative bid and ask depth, negotiated "
        "rounds, net positions, supply mix and the run's message and outage activity.",
        badges=badges,
    )


def _kpis(
    snapshot: Mapping[str, Any],
    orders: pd.DataFrame,
    trades: pd.DataFrame,
    blackout_hours: int,
    log: pd.DataFrame,
) -> None:
    traded = float(trades["qty_mw"].sum()) if not trades.empty else 0.0
    value = (
        float((trades["qty_mw"] * trades["price"]).sum()) if not trades.empty else 0.0
    )
    messages = int(snapshot.get("messages", 0))
    cumulative_messages = int(log["messages"].sum()) if "messages" in log else messages
    items = [
        components.Kpi(
            label="Clearing price",
            value=f"{float(snapshot.get('price', 0.0)):,.2f}",
            unit="per MWh",
            detail=f"<strong>{int(snapshot.get('t', 0))}</strong> simulated hour",
            tone="accent",
        ),
        components.Kpi(
            label="Messages this hour",
            value=f"{messages:,}",
            detail=f"Run total <strong>{cumulative_messages:,}</strong>",
            help_text="Bid, ask and negotiation messages exchanged by the market protocol.",
        ),
        components.Kpi(
            label="Executed trades",
            value=f"{len(trades):,}",
            detail=f"<strong>{traded:,.2f} MW</strong> matched this hour",
            tone="info" if len(trades) else "default",
        ),
        components.Kpi(
            label="Traded value",
            value=f"{value:,.0f}",
            unit="currency",
            detail=f"<strong>{traded:,.2f} MW</strong> cleared volume",
        ),
        components.Kpi(
            label="Hospital blackout",
            value=f"{blackout_hours}",
            unit="hour" if blackout_hours == 1 else "hours",
            detail="No hospital load lost"
            if blackout_hours == 0
            else "<strong>Reliability failure recorded</strong>",
            tone="danger" if blackout_hours else "accent",
            help_text="Hours in which any hospital agent had positive unserved energy.",
        ),
    ]
    components.kpi_grid(items)


def _diagnostics(
    snapshot: Mapping[str, Any],
    orders: pd.DataFrame,
    trades: pd.DataFrame,
    log: pd.DataFrame,
) -> None:
    bid_volume = (
        float(orders.loc[orders["side"] == "buy", "qty_mw"].sum()) if not orders.empty else 0.0
    )
    ask_volume = (
        float(orders.loc[orders["side"] == "sell", "qty_mw"].sum()) if not orders.empty else 0.0
    )
    rounds = int(orders["round"].nunique()) if not orders.empty else 0
    first_price = float(log["price"].iloc[0]) if not log.empty and "price" in log else 0.0
    last_price = float(snapshot.get("price", 0.0))
    components.definition_grid(
        [
            ("Bid volume", f"{bid_volume:,.2f} MW"),
            ("Ask volume", f"{ask_volume:,.2f} MW"),
            ("Negotiation rounds", str(rounds)),
            ("Order count", str(len(orders))),
            ("Trade count", str(len(trades))),
            ("Price change", f"{last_price - first_price:+,.2f} vs first hour"),
            ("Run messages", f"{int(log['messages'].sum()):,}" if "messages" in log else "—"),
            ("Progress", f"{int(snapshot.get('t', 0))} / {int(snapshot.get('steps', 0))} h"),
        ]
    )


def _orders_table(orders: pd.DataFrame, mode: str) -> None:
    components.card_header(
        "Orders of the final hour",
        "Every bid and ask submitted to the clearing round.",
    )
    if orders.empty:
        components.empty_state(
            "No orders in this hour",
            "The order book is empty for the current snapshot."
            if not mode.startswith("central")
            else "Central LP dispatch does not emit a bid/ask order book.",
            hint="Step another hour or switch to an auction system to inspect orders.",
            icon="table",
        )
        return
    display = orders.copy()
    display["side"] = display["side"].map({"buy": "Bid", "sell": "Ask"}).fillna(display["side"])
    st.dataframe(
        display[list(ORDER_COLUMNS)],
        width="stretch",
        hide_index=True,
        column_config={
            "agent_id": st.column_config.TextColumn("Agent"),
            "side": st.column_config.TextColumn("Side"),
            "round": st.column_config.NumberColumn("Round", format="%d"),
            "qty_mw": st.column_config.NumberColumn("Quantity (MW)", format="%.2f"),
            "price": st.column_config.NumberColumn("Limit price", format="%.2f"),
            "priority": st.column_config.NumberColumn("Priority", format="%d"),
        },
    )


def _trades_table(trades: pd.DataFrame) -> None:
    components.card_header(
        "Executed trades",
        "Matched buyer and seller pairs from the final round.",
    )
    if trades.empty:
        components.empty_state(
            "No trades matched",
            "No buyer and seller overlapped at the clearing price in this hour.",
            icon="table",
        )
        return
    st.dataframe(
        trades[list(TRADE_COLUMNS)],
        width="stretch",
        hide_index=True,
        column_config={
            "buyer_id": st.column_config.TextColumn("Buyer"),
            "seller_id": st.column_config.TextColumn("Seller"),
            "qty_mw": st.column_config.NumberColumn("Quantity (MW)", format="%.2f"),
            "price": st.column_config.NumberColumn("Price", format="%.2f"),
        },
    )


def render() -> None:
    """Render the Market Board page."""

    try:
        model = state.ensure_model()
    except state.ModelBuildError as exc:
        _header()
        components.error_state(
            "This run could not start",
            str(exc),
            hint="Adjust the run settings in the sidebar and try again.",
        )
        return
    except Exception as exc:  # noqa: BLE001 - surface backend failures in the UI
        _header()
        components.error_state(
            "This run could not start",
            f"{type(exc).__name__}: {exc}",
        )
        return

    if not model.results:
        _header()
        components.empty_state(
            "The order book is still empty",
            "Step the simulation on the Live Simulation page, or execute one hour "
            "here, to populate bids, asks and trades.",
            hint="The market board only displays real snapshot data.",
            icon="activity",
        )
        if st.button("Execute one hour", key="market_step", type="primary"):
            if state.safe_step(model):
                st.rerun()
            else:
                components.error_state(
                    "The simulation stopped during a step",
                    state.step_error() or "Unknown backend error.",
                )
        return

    snapshot = model.snapshot()
    log = model.logger.get_log()
    orders = _frame(snapshot.get("orders", []) or [], ORDER_COLUMNS)
    trades = _frame(snapshot.get("trades", []) or [], TRADE_COLUMNS)
    mode = str(snapshot.get("mode", ""))
    hospital_columns = [column for column in log.columns if column.startswith("ue_hospital_")]
    blackout_hours = (
        int((log[hospital_columns].sum(axis=1) > 0.001).sum()) if hospital_columns and not log.empty else 0
    )

    _header(snapshot)
    error = state.step_error()
    if error:
        components.error_state("The simulation stopped during a step", error)
    _kpis(snapshot, orders, trades, blackout_hours, log)

    if mode.startswith("central"):
        components.callout(
            "Central LP modes clear by optimisation rather than by matching a bid/ask "
            "book, so the order and trade tables are empty by design. The reliability "
            "and cost figures remain fully populated.",
            tone="info",
            title="Central dispatch.",
        )

    with st.container(border=True):
        components.card_header(
            "Clearing diagnostics",
            "Volumes, rounds and price movement for the displayed hour.",
        )
        _diagnostics(snapshot, orders, trades, log)

    with st.container(key="gm-pair-market-depth"):
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                components.card_header(
                    "Order depth",
                    "Cumulative bid and ask curves with the clearing price.",
                    right_html=components.badge("Cumulative", tone="accent"),
                )
                st.plotly_chart(
                    charts.order_book_figure(orders, float(snapshot.get("price", 0.0))),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )
        with right:
            with st.container(border=True):
                components.card_header(
                    "Negotiation rounds",
                    "Submitted order volume in each negotiation round.",
                )
                st.plotly_chart(
                    charts.rounds_figure(orders),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )

    with st.container(key="gm-pair-market-mix"):
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                components.card_header(
                    "Net positions",
                    "Bought minus sold energy by agent in the final hour.",
                )
                st.plotly_chart(
                    charts.net_positions_figure(trades, snapshot.get("agents", {}) or {}),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )
        with right:
            with st.container(border=True):
                components.card_header(
                    "Supply and demand mix",
                    "Generation by source and demand by consumer group.",
                )
                st.plotly_chart(
                    charts.mix_figure(snapshot),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )

    with st.container(border=True):
        components.card_header(
            "Market activity",
            "Hourly message volume against unserved energy.",
            right_html=components.badge(
                f"{len(log)} hour" if len(log) == 1 else f"{len(log)} hours"
            ),
        )
        st.plotly_chart(
            charts.market_activity_figure(log),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    with st.container(key="gm-pair-market-tables"):
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                _orders_table(orders, mode)
        with right:
            with st.container(border=True):
                _trades_table(trades)
