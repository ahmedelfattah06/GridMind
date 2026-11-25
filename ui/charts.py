"""Plotly chart builders for the GridMind dashboard.

Every builder accepts real simulation output or persisted experiment tables. The
functions only transform data into figures; they do not fabricate or aggregate
values beyond the usual mean/standard deviation needed for a comparison chart.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui import theme
from ui.data import (
    SCENARIO_LABELS,
    SYSTEM_LABELS,
    agent_type_label,
    metric_label,
    metric_unit,
    scenario_label,
    system_label,
)


def _title(text: str) -> str:
    return str(text).replace("_", " ").title()


def _agent_name(agent_id: str) -> str:
    return str(agent_id).replace("_", " ").title()


NODE_PREFIX = {
    "solar": "S",
    "wind": "W",
    "thermal": "T",
    "peaker": "P",
    "hospital": "H",
    "residential": "R",
    "factory": "F",
    "battery": "B",
}


def _rgba(hex_color: str, alpha: float) -> str:
    value = hex_color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
    return f"rgba({red},{green},{blue},{alpha})"


def _empty(text: str = "No data for this view yet.") -> go.Figure:
    figure = go.Figure()
    figure.add_annotation(
        text=text,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"family": theme.FONT_UI, "size": 12, "color": theme.FAINT},
    )
    theme.style_figure(figure, height=260, legend=False, hovermode=None)
    figure.update_xaxes(visible=False, showgrid=False, zeroline=False)
    figure.update_yaxes(visible=False, showgrid=False, zeroline=False)
    return figure


# ---------------------------------------------------------------------------
# Live simulation
# ---------------------------------------------------------------------------


def network_figure(snapshot: Mapping[str, Any]) -> go.Figure:
    """Network-style view of the current agent fleet around the clearing hub."""

    agents = snapshot.get("agents", {}) or {}
    environment = snapshot.get("environment", {}) or {}
    generation = environment.get("generation_mw", {}) or {}
    demand = environment.get("demand_mw", {}) or {}
    unserved = snapshot.get("unserved", {}) or {}
    price = float(snapshot.get("price", 0.0))
    mode = str(snapshot.get("mode", "auction"))
    central = mode.startswith("central")

    producers = sorted(
        agent_id for agent_id, data in agents.items() if data.get("role") == "producer"
    )
    consumers = sorted(
        agent_id for agent_id, data in agents.items() if data.get("role") == "consumer"
    )
    storages = sorted(
        agent_id for agent_id, data in agents.items() if data.get("role") == "storage"
    )
    if not (producers or consumers or storages):
        return _empty("Start the simulation to draw the agent network.")

    positions: dict[str, tuple[float, float]] = {}
    for index, agent_id in enumerate(producers):
        x = 0.5 if len(producers) == 1 else 0.08 + 0.84 * index / (len(producers) - 1)
        positions[agent_id] = (x, 1.0)
    for index, agent_id in enumerate(consumers):
        x = 0.5 if len(consumers) == 1 else 0.05 + 0.90 * index / (len(consumers) - 1)
        # Two staggered demand rows keep the compact node labels legible on
        # wide fleets; the full agent name remains in the hover card.
        y = 0.0 if index % 2 == 0 else -0.11
        positions[agent_id] = (x, y)
    for index, agent_id in enumerate(storages):
        offset = (index - (len(storages) - 1) / 2) * 0.15
        positions[agent_id] = (0.84, 0.5 + offset)

    hub = (0.5, 0.5)
    figure = go.Figure()

    def add_edge(agent_id: str, color: str, width: float, alpha: float, dash: str = "solid") -> None:
        """Draw one hub link: a soft glow underneath and the flow line on top."""

        x, y = positions[agent_id]
        figure.add_trace(
            go.Scatter(
                x=[x, hub[0]],
                y=[y, hub[1]],
                mode="lines",
                line={"color": _rgba(color, 0.07), "width": width + 7},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[x, hub[0]],
                y=[y, hub[1]],
                mode="lines",
                line={"color": _rgba(color, alpha), "width": width, "dash": dash},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Line width follows the real energy flow; colour follows the role.
    for agent_id in producers:
        node = agents[agent_id]
        quantity = float(generation.get(agent_id, node.get("available_mw", 0.0)))
        capacity = max(1.0, float(node.get("capacity_mw", quantity)))
        share = max(0.0, min(1.0, quantity / capacity))
        add_edge(agent_id, theme.ACCENT, 1.1 + 3.4 * share, 0.22 + 0.6 * share)
    for agent_id in consumers:
        node = agents[agent_id]
        lost = float(unserved.get(agent_id, 0.0))
        quantity = float(demand.get(agent_id, node.get("demand_mw", 0.0)))
        if lost > 1e-9:
            add_edge(agent_id, theme.DANGER, 2.0, 0.85, "dot")
        else:
            bought = float(node.get("bought_mw", quantity))
            share = max(0.0, min(1.0, bought / quantity)) if quantity > 1e-9 else 0.0
            add_edge(agent_id, theme.INFO, 1.0 + 2.8 * share, 0.2 + 0.55 * share)
    for agent_id in storages:
        action = int(agents[agent_id].get("last_action", 0) or 0)
        if action == 1:
            add_edge(agent_id, "#2DD4BF", 3.0, 0.8)
        elif action == 2:
            add_edge(agent_id, theme.WARNING, 3.0, 0.8)
        else:
            add_edge(agent_id, theme.MUTED, 1.2, 0.3)

    def add_nodes(
        ids: Sequence[str],
        *,
        role: str,
        symbol: str,
        text_position: str,
        size_base: float,
    ) -> None:
        if not ids:
            return
        x_values, y_values, colors, sizes, labels, hover = [], [], [], [], [], []
        counters: dict[str, int] = {}
        for agent_id in ids:
            data = agents[agent_id]
            agent_type = str(data.get("type", "unknown"))
            count = counters.get(agent_type, 0) + 1
            counters[agent_type] = count
            label = f"{NODE_PREFIX.get(agent_type, agent_type[:1].upper())}{count}"
            x, y = positions[agent_id]
            x_values.append(x)
            y_values.append(y)
            colors.append(theme.AGENT_COLORS.get(agent_type, theme.AGENT_COLORS["unknown"]))
            if role == "producer":
                quantity = float(generation.get(agent_id, data.get("available_mw", 0.0)))
                capacity = max(1.0, float(data.get("capacity_mw", quantity)))
                size = size_base + 10.0 * min(1.0, quantity / capacity)
                hover.append(
                    f"<b>{_agent_name(agent_id)}</b><br>{agent_type_label(agent_type)} · producer"
                    f"<br>Output {quantity:,.2f} MW of {capacity:,.0f} MW"
                    f"<br>Marginal cost {float(data.get('marginal_cost', 0.0)):,.2f}"
                    f"<br>Markup {float(data.get('markup', 0.0)):.0%}"
                )
            elif role == "storage":
                soc = float(data.get("soc", 0.0))
                size = size_base + 8.0 * soc
                hover.append(
                    f"<b>{_agent_name(agent_id)}</b><br>Battery · storage"
                    f"<br>SoC {soc:.0%} · {float(data.get('soc_mwh', 0.0)):,.2f} MWh"
                    f"<br>Last action {theme.ACTION_LABELS.get(int(data.get('last_action', 0)), '—')}"
                )
            else:
                quantity = float(demand.get(agent_id, data.get("demand_mw", 0.0)))
                lost = float(unserved.get(agent_id, 0.0))
                size = size_base + (5.0 if agent_type == "hospital" else 0.0) + min(8.0, quantity / 2)
                hover.append(
                    f"<b>{_agent_name(agent_id)}</b><br>{agent_type_label(agent_type)} · consumer"
                    f"<br>Demand {quantity:,.2f} MW"
                    f"<br>Unserved {lost:,.2f} MW"
                    f"<br>Bought {float(data.get('bought_mw', 0.0)):,.2f} MW"
                )
            sizes.append(size)
            labels.append(label)
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="markers+text",
                text=labels,
                textposition=text_position,
                textfont={"family": theme.FONT_MONO, "size": 10.5, "color": theme.MUTED},
                marker={
                    "symbol": symbol,
                    "size": sizes,
                    "color": colors,
                    "line": {"width": 1.5, "color": theme.BG},
                },
                hovertext=hover,
                hovertemplate="%{hovertext}<extra></extra>",
                showlegend=False,
            )
        )

    add_nodes(
        producers,
        role="producer",
        symbol="diamond",
        text_position="top center",
        size_base=17,
    )
    add_nodes(
        consumers,
        role="consumer",
        symbol="circle",
        text_position="bottom center",
        size_base=14,
    )
    add_nodes(
        storages,
        role="storage",
        symbol="square",
        text_position="middle left",
        size_base=16,
    )

    hub_label = "CENTRAL LP" if central else "DOUBLE<br>AUCTION"
    figure.add_trace(
        go.Scatter(
            x=[hub[0]],
            y=[hub[1]],
            mode="markers+text",
            text=[f"{hub_label}<br>{price:,.2f}"],
            textposition="middle center",
            textfont={"family": theme.FONT_MONO, "size": 10, "color": "#B7F7DC"},
            marker={
                "symbol": "hexagon",
                "size": 76,
                "color": "rgba(16,185,129,0.13)",
                "line": {"width": 1.5, "color": "rgba(52,211,153,0.62)"},
            },
            hovertemplate=(
                f"<b>{'Central planner' if central else 'Uniform-price auction'}</b><br>"
                f"Clearing price {price:,.2f}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    figure.add_annotation(
        text="GENERATION",
        x=0.015,
        y=1.075,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"family": theme.FONT_MONO, "size": 8.5, "color": theme.FAINT},
    )
    figure.add_annotation(
        text="DEMAND",
        x=0.015,
        y=-0.155,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"family": theme.FONT_MONO, "size": 8.5, "color": theme.FAINT},
    )
    if storages:
        figure.add_annotation(
            text="STORAGE",
            x=0.905,
            y=0.63,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"family": theme.FONT_MONO, "size": 8.5, "color": theme.FAINT},
        )

    figure.add_annotation(
        text=(
            f"<span style='color:{theme.ACCENT}'>●</span> generation   "
            f"<span style='color:{theme.INFO}'>●</span> delivered   "
            f"<span style='color:{theme.DANGER}'>●</span> unserved   "
            "<span style='color:#2DD4BF'>●</span> charging   "
            f"<span style='color:{theme.WARNING}'>●</span> discharging"
        ),
        x=0.99,
        y=-0.155,
        xref="paper",
        yref="paper",
        xanchor="right",
        showarrow=False,
        font={"family": theme.FONT_MONO, "size": 8.5, "color": theme.FAINT},
    )
    theme.style_figure(figure, height=430, legend=False, hovermode="closest", margin={"l": 2, "r": 2, "t": 8, "b": 2})
    figure.update_layout(
        xaxis={"visible": False, "range": [-0.04, 1.02]},
        yaxis={"visible": False, "range": [-0.22, 1.14]},
    )
    return figure


def history_figure(log: pd.DataFrame, events: Sequence[Mapping[str, Any]] = ()) -> go.Figure:
    """Three-row price, supply/demand and state-of-charge history chart."""

    if log is None or log.empty:
        return _empty("The chart appears after the first simulated hour.")

    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.34, 0.36, 0.30],
        vertical_spacing=0.09,
        subplot_titles=("Clearing price", "Supply, demand and unserved energy", "Battery state of charge"),
    )
    hours = log["t"]
    price = log["price"]
    rolling = price.rolling(24, min_periods=1).mean()
    figure.add_trace(
        go.Scatter(
            x=hours,
            y=price,
            mode="lines",
            name="Price",
            line={"color": theme.WARNING, "width": 1.7},
            hovertemplate="Price %{y:,.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=hours,
            y=rolling,
            mode="lines",
            name="24 h mean",
            line={"color": theme.MUTED, "width": 1.0, "dash": "dot"},
            hovertemplate="24 h mean %{y:,.2f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=hours,
            y=log["supply"],
            mode="lines",
            name="Supply",
            line={"color": theme.ACCENT, "width": 1.6},
            fill="tozeroy",
            fillcolor="rgba(52,211,153,0.07)",
            hovertemplate="Supply %{y:,.2f} MW<extra></extra>",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=hours,
            y=log["demand"],
            mode="lines",
            name="Demand",
            line={"color": theme.INFO, "width": 1.3, "dash": "dot"},
            hovertemplate="Demand %{y:,.2f} MW<extra></extra>",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=hours,
            y=log["unserved_mw"],
            mode="lines",
            name="Unserved",
            line={"color": theme.DANGER, "width": 1.2},
            fill="tozeroy",
            fillcolor="rgba(248,113,113,0.10)",
            hovertemplate="Unserved %{y:,.2f} MW<extra></extra>",
        ),
        row=2,
        col=1,
    )
    soc_columns = [column for column in log.columns if column.startswith("soc_")]
    soc_colors = [theme.ACCENT, "#22D3EE", "#A78BFA", "#FACC15"]
    for index, column in enumerate(soc_columns):
        figure.add_trace(
            go.Scatter(
                x=hours,
                y=log[column],
                mode="lines",
                name=_agent_name(column[4:]),
                line={"color": soc_colors[index % len(soc_colors)], "width": 1.4},
                hovertemplate=f"{_agent_name(column[4:])} SoC %{{y:.1%}}<extra></extra>",
            ),
            row=3,
            col=1,
        )

    latest_hour = float(hours.max())
    for event in events:
        start = int(event.get("t_start", 0))
        end = int(event.get("t_end", start))
        name = str(event.get("name", "event")).replace("_", " ").title()
        shade_end = min(float(end), latest_hour)
        for row in (1, 2, 3):
            if shade_end > start:
                # Shade the part of the disruption window that has already played out.
                figure.add_vrect(
                    x0=start,
                    x1=shade_end,
                    fillcolor="rgba(251,191,36,0.07)",
                    line_width=0,
                    layer="below",
                    row=row,
                    col=1,
                )
            figure.add_vline(
                x=start,
                line={"color": "rgba(251,191,36,0.4)", "width": 1, "dash": "dash"},
                row=row,
                col=1,
            )
        figure.add_annotation(
            x=start,
            y=1.0,
            xref="x",
            yref="paper",
            text=name,
            showarrow=False,
            yshift=10,
            font={"family": theme.FONT_UI, "size": 8, "color": "rgba(245,165,36,0.8)"},
        )

    for annotation in figure.layout.annotations:
        if annotation.text in {
            "Clearing price",
            "Supply, demand and unserved energy",
            "Battery state of charge",
        }:
            annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}

    theme.style_figure(figure, height=560, hovermode="x unified")
    figure.update_layout(
        margin={"l": 6, "r": 6, "t": 64, "b": 6},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.105, "x": 0},
    )
    figure.update_yaxes(title_text="currency/MWh", row=1, col=1)
    figure.update_yaxes(title_text="MW", row=2, col=1)
    figure.update_yaxes(title_text="SoC", tickformat=".0%", row=3, col=1)
    figure.update_xaxes(title_text="Simulation hour", row=3, col=1)
    return figure


# ---------------------------------------------------------------------------
# Market board
# ---------------------------------------------------------------------------


def order_book_figure(orders: pd.DataFrame, clearing_price: float) -> go.Figure:
    """Cumulative bid and ask curves with the clearing price."""

    if orders is None or orders.empty:
        return _empty("No orders in the current clearing hour.")

    figure = go.Figure()
    for side, label, color, ascending in (
        ("buy", "Bids", theme.ACCENT, False),
        ("sell", "Asks", theme.DANGER, True),
    ):
        subset = orders[orders["side"] == side].sort_values("price", ascending=ascending)
        if subset.empty:
            continue
        volume = subset["qty_mw"].cumsum()
        figure.add_trace(
            go.Scatter(
                x=volume,
                y=subset["price"],
                mode="lines+markers",
                line={"shape": "hv", "width": 1.7, "color": color},
                marker={"size": 4, "color": color},
                name=label,
                hovertemplate=(
                    f"{label}<br>%{{x:,.2f}} MW cumulative<br>%{{y:,.2f}} currency/MWh<extra></extra>"
                ),
            )
        )
    figure.add_hline(
        y=clearing_price,
        line={"color": "rgba(230,237,243,0.38)", "width": 1, "dash": "dot"},
        annotation_text=f"clearing {clearing_price:,.2f}",
        annotation_position="top right",
        annotation_font={"family": theme.FONT_MONO, "size": 9, "color": theme.MUTED},
    )
    theme.style_figure(figure, height=330, hovermode="closest")
    figure.update_xaxes(title_text="Cumulative volume (MW)")
    figure.update_yaxes(title_text="Price (currency/MWh)")
    return figure


def rounds_figure(orders: pd.DataFrame) -> go.Figure:
    """Submitted order volume by negotiation round and side."""

    if orders is None or orders.empty:
        return _empty("No negotiation rounds recorded yet.")
    grouped = (
        orders.groupby(["round", "side"], as_index=False)["qty_mw"]
        .sum()
        .sort_values("round")
    )
    figure = go.Figure()
    for side, label, color in (
        ("sell", "Asks", theme.DANGER),
        ("buy", "Bids", theme.ACCENT),
    ):
        subset = grouped[grouped["side"] == side]
        if subset.empty:
            continue
        figure.add_trace(
            go.Bar(
                x=[f"Round {int(value)}" for value in subset["round"]],
                y=subset["qty_mw"],
                name=label,
                marker={"color": color, "opacity": 0.85},
                hovertemplate=f"{label}<br>%{{x}}<br>%{{y:,.2f}} MW<extra></extra>",
            )
        )
    theme.style_figure(figure, height=330, hovermode="x unified")
    figure.update_layout(barmode="group", bargap=0.35)
    figure.update_yaxes(title_text="Ordered volume (MW)")
    return figure


def net_positions_figure(trades: pd.DataFrame, agents: Mapping[str, Any]) -> go.Figure:
    """Net bought minus sold energy by agent for the current hour."""

    if trades is None or trades.empty:
        return _empty("No trades have cleared in this hour.")

    bought: dict[str, float] = {}
    sold: dict[str, float] = {}
    for row in trades.itertuples(index=False):
        bought[row.buyer_id] = bought.get(row.buyer_id, 0.0) + float(row.qty_mw)
        sold[row.seller_id] = sold.get(row.seller_id, 0.0) + float(row.qty_mw)
    ids = sorted(set(bought) | set(sold), key=lambda item: bought.get(item, 0.0) - sold.get(item, 0.0))
    net = [bought.get(agent_id, 0.0) - sold.get(agent_id, 0.0) for agent_id in ids]
    colors = [theme.ACCENT if value >= 0 else theme.DANGER for value in net]
    roles = [str(agents.get(agent_id, {}).get("type", "unknown")) for agent_id in ids]
    figure = go.Figure(
        go.Bar(
            x=net,
            y=[_agent_name(agent_id) for agent_id in ids],
            orientation="h",
            marker={"color": colors, "opacity": 0.88},
            customdata=list(zip(roles, [sold.get(agent_id, 0.0) for agent_id in ids])),
            hovertemplate=(
                "<b>%{y}</b><br>%{customdata[0]}<br>Net %{x:+,.2f} MW"
                "<br>Sold %{customdata[1]:,.2f} MW<extra></extra>"
            ),
        )
    )
    figure.add_vline(x=0, line={"color": "rgba(230,237,243,0.22)", "width": 1})
    theme.style_figure(figure, height=max(280, min(430, 30 * len(ids) + 90)), legend=False, hovermode="closest")
    figure.update_xaxes(title_text="Net position (MW) · positive = net buyer")
    return figure


def mix_figure(snapshot: Mapping[str, Any]) -> go.Figure:
    """Generation by source and demand by consumer type for the current hour."""

    agents = snapshot.get("agents", {}) or {}
    environment = snapshot.get("environment", {}) or {}
    generation = environment.get("generation_mw", {}) or {}
    demand = environment.get("demand_mw", {}) or {}
    if not agents:
        return _empty("No agent state in the current hour.")

    supply: dict[str, float] = {}
    demand_by_type: dict[str, float] = {}
    for agent_id, data in agents.items():
        agent_type = str(data.get("type", "unknown"))
        if data.get("role") == "producer":
            supply[agent_type] = supply.get(agent_type, 0.0) + float(
                generation.get(agent_id, data.get("available_mw", 0.0))
            )
        elif data.get("role") == "consumer":
            demand_by_type[agent_type] = demand_by_type.get(agent_type, 0.0) + float(
                demand.get(agent_id, data.get("demand_mw", 0.0))
            )

    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Generation by source", "Demand by consumer"),
        horizontal_spacing=0.16,
    )
    supply_items = sorted(supply.items(), key=lambda item: item[1], reverse=True)
    demand_items = sorted(demand_by_type.items(), key=lambda item: item[1], reverse=True)
    if supply_items:
        figure.add_trace(
            go.Bar(
                x=[value for _, value in supply_items],
                y=[agent_type_label(name) for name, _ in supply_items],
                orientation="h",
                marker={
                    "color": [theme.AGENT_COLORS.get(name, theme.FAINT) for name, _ in supply_items],
                    "opacity": 0.88,
                },
                name="Generation",
                hovertemplate="%{y}<br>%{x:,.2f} MW<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
    if demand_items:
        figure.add_trace(
            go.Bar(
                x=[value for _, value in demand_items],
                y=[agent_type_label(name) for name, _ in demand_items],
                orientation="h",
                marker={
                    "color": [theme.AGENT_COLORS.get(name, theme.FAINT) for name, _ in demand_items],
                    "opacity": 0.88,
                },
                name="Demand",
                hovertemplate="%{y}<br>%{x:,.2f} MW<extra></extra>",
                showlegend=False,
            ),
            row=1,
            col=2,
        )
    for annotation in figure.layout.annotations:
        annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}
    theme.style_figure(figure, height=300, legend=False, hovermode="closest")
    figure.update_layout(margin={"l": 6, "r": 6, "t": 48, "b": 6})
    figure.update_xaxes(title_text="MW", row=1, col=1)
    figure.update_xaxes(title_text="MW", row=1, col=2)
    return figure


def market_activity_figure(log: pd.DataFrame) -> go.Figure:
    """Message volume and unserved energy over the run."""

    if log is None or log.empty:
        return _empty("The activity chart appears after the first hour.")
    if len(log) < 2:
        row = log.iloc[0]
        figure = go.Figure()
        figure.add_annotation(
            text=(
                f"<b>{int(row['messages']):,}</b> messages"
                f"<span style='color:{theme.FAINT}'>  ·  </span>"
                f"<b>{float(row['unserved_mw']):,.2f} MW</b> unserved"
            ),
            x=0.5,
            y=0.56,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"family": theme.FONT_MONO, "size": 16, "color": theme.TEXT_STRONG},
        )
        figure.add_annotation(
            text=(
                f"Hour {int(row['t'])} is the only completed hour. "
                "The trend line appears once a second hour is recorded."
            ),
            x=0.5,
            y=0.4,
            xref="paper",
            yref="paper",
            showarrow=False,
            font={"family": theme.FONT_UI, "size": 11, "color": theme.FAINT},
        )
        theme.style_figure(figure, height=310, legend=False, hovermode=None)
        figure.update_xaxes(visible=False, showgrid=False, zeroline=False)
        figure.update_yaxes(visible=False, showgrid=False, zeroline=False)
        return figure
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Bar(
            x=log["t"],
            y=log["messages"],
            name="Messages",
            marker={"color": "rgba(139,154,171,0.55)"},
            hovertemplate="Hour %{x}<br>%{y:,} messages<extra></extra>",
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=log["t"],
            y=log["unserved_mw"],
            mode="lines",
            name="Unserved MW",
            line={"color": theme.DANGER, "width": 1.4},
            hovertemplate="Unserved %{y:,.2f} MW<extra></extra>",
        ),
        secondary_y=True,
    )
    theme.style_figure(figure, height=310, hovermode="x unified")
    figure.update_yaxes(title_text="Messages", secondary_y=False)
    figure.update_yaxes(title_text="Unserved (MW)", secondary_y=True, showgrid=False)
    figure.update_xaxes(title_text="Simulation hour")
    return figure


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------


def _stats(
    raw: pd.DataFrame,
    systems: Sequence[str],
    scenarios: Sequence[str],
    metric: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    subset = raw[
        raw["system"].isin(list(systems)) & raw["scenario"].isin(list(scenarios))
    ]
    means = (
        subset.pivot_table(index="scenario", columns="system", values=metric, aggfunc="mean")
        .reindex(index=list(scenarios), columns=list(systems))
    )
    stds = (
        subset.pivot_table(index="scenario", columns="system", values=metric, aggfunc="std")
        .reindex(index=list(scenarios), columns=list(systems))
    )
    return means, stds


def compare_cost_figure(
    raw: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> go.Figure:
    """Grouped mean social cost with one-standard-deviation whiskers."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    means, stds = _stats(raw, systems, scenarios, "social_cost")
    figure = go.Figure()
    for system in systems:
        if system not in means:
            continue
        figure.add_trace(
            go.Bar(
                x=[scenario_label(scenario) for scenario in scenarios],
                y=means[system].values,
                name=system_label(system),
                marker={"color": theme.SYSTEM_COLORS.get(system, theme.ACCENT), "opacity": 0.9},
                error_y={
                    "type": "data",
                    "array": stds[system].fillna(0.0).values,
                    "visible": True,
                    "thickness": 1,
                    "width": 3,
                    "color": "rgba(230,237,243,0.38)",
                },
                customdata=stds[system].fillna(0.0).values,
                hovertemplate=(
                    f"<b>{system_label(system)}</b><br>%{{x}}"
                    "<br>Mean %{y:,.0f}<br>SD %{customdata:,.0f}<extra></extra>"
                ),
            )
        )
    theme.style_figure(figure, height=390, hovermode="x unified")
    figure.update_layout(barmode="group", bargap=0.3, bargroupgap=0.07)
    figure.update_yaxes(title_text="Social cost (currency)")
    return figure


def reliability_figure(
    raw: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> go.Figure:
    """Unserved energy and recovery time by scenario and system."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    ue_means, ue_stds = _stats(raw, systems, scenarios, "ue_total")
    rec_means, rec_stds = _stats(raw, systems, scenarios, "recovery_time")
    figure = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Unserved energy", "Recovery time"),
        vertical_spacing=0.17,
    )
    x_labels = [scenario_label(scenario) for scenario in scenarios]
    for system in systems:
        color = theme.SYSTEM_COLORS.get(system, theme.ACCENT)
        if system in ue_means:
            figure.add_trace(
                go.Bar(
                    x=x_labels,
                    y=ue_means[system].values,
                    name=system_label(system),
                    marker={"color": color, "opacity": 0.88},
                    error_y={
                        "type": "data",
                        "array": ue_stds[system].fillna(0.0).values,
                        "visible": True,
                        "thickness": 1,
                        "width": 3,
                        "color": "rgba(230,237,243,0.35)",
                    },
                    legendgroup=system,
                    showlegend=True,
                    hovertemplate=(
                        f"<b>{system_label(system)}</b><br>%{{x}}"
                        "<br>UE %{y:,.1f} MWh<extra></extra>"
                    ),
                ),
                row=1,
                col=1,
            )
        if system in rec_means:            figure.add_trace(
                go.Bar(
                    x=x_labels,
                    y=rec_means[system].values,
                    name=system_label(system),
                    marker={"color": color, "opacity": 0.88},
                    error_y={
                        "type": "data",
                        "array": rec_stds[system].fillna(0.0).values,
                        "visible": True,
                        "thickness": 1,
                        "width": 3,
                        "color": "rgba(230,237,243,0.35)",
                    },
                    legendgroup=system,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{system_label(system)}</b><br>%{{x}}"
                        "<br>Recovery %{y:,.1f} h<extra></extra>"
                    ),
                ),
                row=2,
                col=1,
            )
    for annotation in figure.layout.annotations:
        if annotation.text in {"Unserved energy", "Recovery time"}:
            annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}
    theme.style_figure(figure, height=500, hovermode="x unified")
    figure.update_layout(
        barmode="group",
        bargap=0.3,
        bargroupgap=0.07,
        margin={"l": 6, "r": 6, "t": 62, "b": 6},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.1, "x": 0},
    )
    figure.update_yaxes(title_text="MWh", row=1, col=1)
    figure.update_yaxes(title_text="hours", row=2, col=1)
    figure.update_xaxes(tickangle=-18, row=1, col=1)
    figure.update_xaxes(tickangle=-18, row=2, col=1)
    return figure


def fairness_figure(
    raw: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> go.Figure:
    """Peak-to-average ratio and Gini coefficient by system."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    subset = raw[
        raw["system"].isin(list(systems)) & raw["scenario"].isin(list(scenarios))
    ]
    figure = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Peak-to-average ratio", "Gini coefficient"),
        vertical_spacing=0.18,
    )
    for system in systems:
        group = subset[subset["system"] == system]
        if group.empty:
            continue
        color = theme.SYSTEM_COLORS.get(system, theme.ACCENT)
        for column, metric, row in (("par", "PAR", 1), ("gini", "Gini", 2)):
            if column not in group:
                continue
            figure.add_trace(
                go.Bar(
                    x=[system_label(system)],
                    y=[float(group[column].mean())],
                    name=system_label(system),
                    marker={"color": color, "opacity": 0.88},
                    error_y={
                        "type": "data",
                        "array": [float(group[column].std(ddof=0))],
                        "visible": True,
                        "thickness": 1,
                        "width": 3,
                        "color": "rgba(230,237,243,0.35)",
                    },
                    showlegend=False,
                    hovertemplate=f"<b>{system_label(system)}</b><br>{metric} %{{y:,.4f}}<extra></extra>",
                ),
                row=row,
                col=1,
            )
    for annotation in figure.layout.annotations:
        if annotation.text in {"Peak-to-average ratio", "Gini coefficient"}:
            annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}
    theme.style_figure(figure, height=430, legend=False, hovermode="closest")
    figure.update_layout(margin={"l": 6, "r": 6, "t": 52, "b": 6})
    figure.update_yaxes(title_text="ratio", row=1, col=1)
    figure.update_yaxes(title_text="index", row=2, col=1)
    return figure


def tradeoff_figure(
    raw: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> go.Figure:
    """Social cost versus unserved energy, with bubble size for renewable share."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    subset = raw[
        raw["system"].isin(list(systems)) & raw["scenario"].isin(list(scenarios))
    ]
    grouped = (
        subset.groupby(["system", "scenario"], as_index=False)[
            ["social_cost", "ue_total", "renewable_share"]
        ]
        .mean()
        .sort_values(["system", "scenario"])
    )
    figure = go.Figure()
    for system in systems:
        group = grouped[grouped["system"] == system]
        if group.empty:
            continue
        color = theme.SYSTEM_COLORS.get(system, theme.ACCENT)
        figure.add_trace(
            go.Scatter(
                x=group["social_cost"],
                y=group["ue_total"],
                mode="markers",
                name=system_label(system),
                marker={
                    "size": 10 + 18 * group["renewable_share"].fillna(0.0),
                    "color": color,
                    "opacity": 0.78,
                    "line": {"width": 1, "color": theme.BG},
                },
                customdata=list(
                    zip(
                        group["scenario"].map(scenario_label),
                        group["renewable_share"].fillna(0.0),
                    )
                ),
                hovertemplate=(
                    f"<b>{system_label(system)}</b><br>%{{customdata[0]}}"
                    "<br>Social cost %{x:,.0f}"
                    "<br>UE %{y:,.1f} MWh"
                    "<br>Renewable share %{customdata[1]:.1%}<extra></extra>"
                ),
            )
        )
    theme.style_figure(figure, height=390, hovermode="closest")
    figure.update_xaxes(title_text="Social cost (currency)")
    figure.update_yaxes(title_text="Unserved energy (MWh)")
    return figure


def social_cost_box_figure(raw: pd.DataFrame, systems: Sequence[str]) -> go.Figure:
    """Distribution of per-run social cost for each selected system."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    figure = go.Figure()
    for system in systems:
        values = raw.loc[raw["system"] == system, "social_cost"].dropna()
        if values.empty:
            continue
        color = theme.SYSTEM_COLORS.get(system, theme.ACCENT)
        figure.add_trace(
            go.Box(
                y=values,
                name=system_label(system),
                marker={"color": color, "size": 3, "opacity": 0.42},
                line={"color": color, "width": 1.4},
                fillcolor="rgba(0,0,0,0)",
                boxpoints="all",
                jitter=0.32,
                pointpos=0,
                boxmean=True,
                hovertemplate=f"<b>{system_label(system)}</b><br>Social cost %{{y:,.0f}}<extra></extra>",
            )
        )
    theme.style_figure(figure, height=340, legend=False, hovermode="closest")
    figure.update_yaxes(title_text="Social cost (currency)")
    return figure


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------


def learning_curve_figure(
    curve: pd.DataFrame, metadata: Mapping[str, Any] | None = None
) -> go.Figure:
    """Reward, TD error and exploration schedule from the training run."""

    if curve is None or curve.empty:
        return _empty("No learning curve was found for this training run.")
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.52, 0.26, 0.22],
        vertical_spacing=0.09,
        subplot_titles=("Mean reward per 50 episodes", "Mean TD error", "Exploration rate"),
    )
    episodes = curve["episode"]
    mean = curve["mean_reward"]
    std = curve.get("std_reward", pd.Series(0.0, index=curve.index)).fillna(0.0)
    figure.add_trace(
        go.Scatter(
            x=episodes,
            y=mean + std,
            mode="lines",
            line={"width": 0, "color": "rgba(0,0,0,0)"},
            showlegend=False,
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=episodes,
            y=mean - std,
            mode="lines",
            line={"width": 0, "color": "rgba(0,0,0,0)"},
            fill="tonexty",
            fillcolor="rgba(52,211,153,0.10)",
            name="± 1 SD",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=episodes,
            y=mean,
            mode="lines+markers",
            name="Mean reward",
            line={"color": theme.ACCENT, "width": 1.8},
            marker={"size": 3.5, "color": theme.ACCENT},
            hovertemplate="Episode %{x}<br>Reward %{y:,.1f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    if "mean_td_error" in curve:
        figure.add_trace(
            go.Scatter(
                x=episodes,
                y=curve["mean_td_error"],
                mode="lines",
                name="TD error",
                line={"color": "#A78BFA", "width": 1.5},
                hovertemplate="TD error %{y:,.2f}<extra></extra>",
            ),
            row=2,
            col=1,
        )
    if "epsilon" in curve:
        figure.add_trace(
            go.Scatter(
                x=episodes,
                y=curve["epsilon"],
                mode="lines",
                name="Epsilon",
                line={"color": theme.WARNING, "width": 1.4},
                hovertemplate="ε %{y:.3f}<extra></extra>",
            ),
            row=3,
            col=1,
        )
        if metadata and metadata.get("epsilon_decay_episodes"):
            decay = int(metadata["epsilon_decay_episodes"])
            figure.add_vline(
                x=decay,
                line={"color": "rgba(245,165,36,0.28)", "width": 1, "dash": "dot"},
                row=3,
                col=1,
            )
    for annotation in figure.layout.annotations:
        if annotation.text in {
            "Mean reward per 50 episodes",
            "Mean TD error",
            "Exploration rate",
        }:
            annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}
    theme.style_figure(figure, height=540, hovermode="x unified")
    figure.update_layout(
        margin={"l": 6, "r": 6, "t": 66, "b": 6},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.105, "x": 0},
    )
    figure.update_yaxes(title_text="reward", row=1, col=1)
    figure.update_yaxes(title_text="TD error", row=2, col=1)
    figure.update_yaxes(title_text="ε", range=[0, 1.05], row=3, col=1)
    figure.update_xaxes(title_text="Training episode", row=3, col=1)
    return figure


_PRICE_NAMES = ("Cheap", "Normal", "Expensive")
_PERIOD_SHORT = ("Night", "Morning", "Midday", "Evening")
_SOC_LABELS = ("0–20%", "20–40%", "40–60%", "60–80%", "80–100%")


def q_heatmap_figure(qtable: np.ndarray, view: str = "policy") -> go.Figure:
    """Interactive 5 x 12 view of the learned Q-table."""

    table = np.asarray(qtable, dtype=float)
    greedy = np.argmax(table, axis=1)
    q_columns = {"wait": 0, "charge": 1, "discharge": 2}
    policy_view = view == "policy"

    z: list[list[float]] = []
    text: list[list[str]] = []
    hover: list[list[str]] = []
    for soc_row in range(5):
        soc = 4 - soc_row
        z_row: list[float] = []
        text_row: list[str] = []
        hover_row: list[str] = []
        for price in range(3):
            for period in range(4):
                state = (soc * 3 + price) * 4 + period
                values = table[state]
                action = int(greedy[state])
                state_label = (
                    f"State {state} · SoC {_SOC_LABELS[soc]} · "
                    f"{_PRICE_NAMES[price]} price · {_PERIOD_SHORT[period]}"
                )
                hover_row.append(
                    f"{state_label}<br>Greedy: {theme.ACTION_LABELS[action]}"
                    f"<br>Q(wait) {values[0]:,.2f}"
                    f"<br>Q(charge) {values[1]:,.2f}"
                    f"<br>Q(discharge) {values[2]:,.2f}"
                )
                if policy_view:
                    z_row.append(float(action))
                    text_row.append(("W", "C", "D")[action])
                else:
                    value = float(values[q_columns[view]])
                    z_row.append(value)
                    text_row.append(f"{value:,.0f}")
        z.append(z_row)
        text.append(text_row)
        hover.append(hover_row)

    if policy_view:
        colorscale = [
            [0.0, "#8B9AAB"],
            [0.333, "#8B9AAB"],
            [0.334, "#34D399"],
            [0.666, "#34D399"],
            [0.667, "#F5A524"],
            [1.0, "#F5A524"],
        ]
        zmin, zmax = -0.5, 2.5
        text_color = "#07110C"
    else:
        colorscale = [
            [0.0, "#0B1220"],
            [0.35, "#123B31"],
            [0.72, "#1D7A5C"],
            [1.0, "#6EE7B7"],
        ]
        zmin = float(np.nanmin(table))
        zmax = float(np.nanmax(table))
        text_color = "#DCE6EF"

    figure = go.Figure(
        go.Heatmap(
            z=z,
            x=list(range(12)),
            y=[_SOC_LABELS[soc] for soc in range(4, -1, -1)],
            text=text,
            texttemplate="%{text}",
            textfont={"family": theme.FONT_MONO, "size": 11, "color": text_color},
            colorscale=colorscale,
            zmin=zmin,
            zmax=zmax,
            xgap=2,
            ygap=2,
            customdata=hover,
            hovertemplate="%{customdata}<extra></extra>",
            colorbar={
                "title": {"text": "Q" if not policy_view else "", "font": {"size": 9, "color": theme.FAINT}},
                "thickness": 7,
                "len": 0.78,
                "tickfont": {"family": theme.FONT_MONO, "size": 8, "color": theme.FAINT},
                "outlinewidth": 0,
                "showticklabels": not policy_view,
            },
        )
    )
    for boundary in (3.5, 7.5):
        figure.add_vline(x=boundary, line={"color": "rgba(7,11,16,0.9)", "width": 2})
    for index, name in enumerate(("CHEAP", "NORMAL", "EXPENSIVE")):
        figure.add_annotation(
            x=index * 4 + 1.5,
            y=1.035,
            xref="x",
            yref="paper",
            text=name,
            showarrow=False,
            font={"family": theme.FONT_MONO, "size": 8, "color": theme.FAINT},
        )
    theme.style_figure(figure, height=430, legend=False, hovermode="closest")
    figure.update_xaxes(
        tickangle=-50,
        tickmode="array",
        tickvals=list(range(12)),
        ticktext=[
            _PERIOD_SHORT[period]
            for price in range(3)
            for period in range(4)
        ],
        tickfont={"family": theme.FONT_MONO, "size": 8.5, "color": theme.MUTED},
    )
    figure.update_yaxes(title_text="State of charge", autorange="reversed")
    return figure


def rule_vs_q_delta_figure(raw: pd.DataFrame) -> go.Figure:
    """Relative change from the rule-based auction to the learned policy."""

    if raw is None or raw.empty:
        return _empty("No saved experiment rows are available.")
    if "auction" not in set(raw["system"]) or "auction_q" not in set(raw["system"]):
        return _empty("Saved results do not contain both auction variants.")
    rows = []
    for scenario in [value for value in SCENARIO_LABELS if value in set(raw["scenario"])]:
        rule = raw[(raw["scenario"] == scenario) & (raw["system"] == "auction")]
        learned = raw[(raw["scenario"] == scenario) & (raw["system"] == "auction_q")]
        if rule.empty or learned.empty:
            continue
        cost_rule = float(rule["social_cost"].mean())
        ue_rule = float(rule["ue_total"].mean())
        rows.append(
            {
                "scenario": scenario,
                "cost": 100.0 * (float(learned["social_cost"].mean()) - cost_rule) / cost_rule,
                "ue": 100.0 * (float(learned["ue_total"].mean()) - ue_rule) / ue_rule,
            }
        )
    if not rows:
        return _empty("The saved results cannot be paired for this comparison.")
    frame = pd.DataFrame(rows)
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Social cost", "Unserved energy"),
        horizontal_spacing=0.18,
    )
    scenario_order = [scenario_label(value) for value in frame["scenario"]]
    for column, col, label in (("cost", 1, "Cost"), ("ue", 2, "UE")):
        colors = [
            theme.ACCENT if value <= 0 else theme.DANGER for value in frame[column]
        ]
        figure.add_trace(
            go.Bar(
                x=frame[column],
                y=scenario_order,
                orientation="h",
                marker={"color": colors, "opacity": 0.88},
                showlegend=False,
                customdata=frame[column],
                hovertemplate=f"<b>%{{y}}</b><br>{label} %{{customdata:+.2f}}% vs rule<extra></extra>",
            ),
            row=1,
            col=col,
        )
        figure.add_vline(
            x=0,
            line={"color": "rgba(230,237,243,0.22)", "width": 1},
            row=1,
            col=col,
        )
    for annotation in figure.layout.annotations:
        if annotation.text in {"Social cost", "Unserved energy"}:
            annotation.font = {"family": theme.FONT_UI, "size": 10, "color": theme.MUTED}
    theme.style_figure(figure, height=340, legend=False, hovermode="closest")
    figure.update_layout(margin={"l": 6, "r": 6, "t": 48, "b": 6})
    figure.update_yaxes(autorange="reversed", row=1, col=1)
    figure.update_yaxes(autorange="reversed", row=1, col=2)
    figure.update_xaxes(title_text="% change vs rule", row=1, col=1)
    figure.update_xaxes(title_text="% change vs rule", row=1, col=2)
    return figure



def radar_figure(
    raw: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> go.Figure:
    """Relative system profile across the headline metrics (outer ring = best)."""

    if raw is None or raw.empty:
        return _empty("No experiment rows match the current filters.")
    subset = raw[raw["system"].isin(list(systems)) & raw["scenario"].isin(list(scenarios))]
    spec = (
        ("social_cost", "Cost", False),
        ("ue_total", "Reliability", False),
        ("recovery_time", "Recovery", False),
        ("gini", "Fairness", False),
        ("par", "Peak flatness", False),
        ("renewable_share", "Renewables", True),
    )
    present = [item for item in spec if item[0] in subset.columns]
    if subset.empty or len(present) < 3:
        return _empty("Not enough metrics to draw a profile.")
    order = [system for system in systems if system in set(subset["system"])]
    means = subset.groupby("system")[[metric for metric, _, _ in present]].mean().reindex(order)
    scores = pd.DataFrame(index=means.index)
    for metric, label, higher_is_better in present:
        column = means[metric].astype(float)
        low, high = float(column.min()), float(column.max())
        if high - low <= 1e-12:
            scores[label] = 1.0
        else:
            normalised = (column - low) / (high - low)
            scores[label] = normalised if higher_is_better else 1.0 - normalised
    labels = list(scores.columns)
    figure = go.Figure()
    for system in scores.index:
        values = [float(value) for value in scores.loc[system].tolist()]
        color = theme.SYSTEM_COLORS.get(system, theme.ACCENT)
        figure.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                name=system_label(system),
                line={"color": color, "width": 2},
                fill="toself",
                fillcolor=_rgba(color, 0.10),
                hovertemplate=(
                    f"<b>{system_label(system)}</b><br>%{{theta}}: %{{r:.0%}} of best<extra></extra>"
                ),
            )
        )
    theme.style_figure(figure, height=380, hovermode="closest")
    figure.update_layout(
        polar={
            "bgcolor": "rgba(0,0,0,0)",
            "radialaxis": {
                "range": [0, 1],
                "showticklabels": False,
                "gridcolor": "rgba(148,163,184,0.16)",
                "linecolor": "rgba(148,163,184,0.16)",
                "ticks": "",
            },
            "angularaxis": {
                "gridcolor": "rgba(148,163,184,0.16)",
                "linecolor": theme.BORDER,
                "tickfont": {"family": theme.FONT_UI, "size": 10.5, "color": theme.MUTED},
            },
        },
        margin={"l": 52, "r": 52, "t": 26, "b": 40},
        legend={"orientation": "h", "yanchor": "top", "y": -0.04, "x": 0.5, "xanchor": "center"},
    )
    return figure