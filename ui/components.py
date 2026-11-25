"""Reusable, HTML-backed UI components for the GridMind dashboard.

The components are deliberately small and composable. They consume real values
from the simulation or the experiment artefacts and never compute business
metrics themselves. Every dynamic string is HTML-escaped unless the caller
passes an explicitly trusted fragment built by another component in this module.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Iterable, Mapping, Sequence

import streamlit as st

from ui import theme

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def esc(value: object) -> str:
    """Escape a value for safe interpolation into component HTML."""

    return html.escape(str(value), quote=True)


def fmt_int(value: float | int | None, dash: str = "—") -> str:
    """Format an integer with thousands separators."""

    if value is None or _missing(value):
        return dash
    return f"{int(round(float(value))):,}"


def fmt_number(value: float | int | None, digits: int = 2, dash: str = "—") -> str:
    """Format a number with fixed decimals and thousands separators."""

    if value is None or _missing(value):
        return dash
    return f"{float(value):,.{digits}f}"


def fmt_money(value: float | int | None, dash: str = "—") -> str:
    """Format a currency amount without a symbol; the unit is shown separately."""

    if value is None or _missing(value):
        return dash
    return f"{float(value):,.0f}"


def fmt_compact(value: float | int | None, dash: str = "—") -> str:
    """Format a number compactly, for axis labels and small cards."""

    if value is None or _missing(value):
        return dash
    number = float(value)
    magnitude = abs(number)
    if magnitude >= 1_000_000:
        return f"{number / 1_000_000:,.2f}M"
    if magnitude >= 10_000:
        return f"{number / 1_000:,.1f}k"
    if magnitude >= 1_000:
        return f"{number:,.0f}"
    if magnitude >= 10:
        return f"{number:,.1f}"
    return f"{number:,.2f}"


def fmt_share(value: float | None, digits: int = 1, dash: str = "—") -> str:
    """Format a fraction as a percentage."""

    if value is None or _missing(value):
        return dash
    return f"{float(value) * 100:,.{digits}f}%"


def fmt_signed(value: float | None, digits: int = 2, suffix: str = "") -> str:
    """Format a signed number with an explicit plus sign for positive values."""

    if value is None or _missing(value):
        return "—"
    return f"{float(value):+,.{digits}f}{suffix}"


def _missing(value: object) -> bool:
    try:
        return bool(math.isnan(float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def sparkline_svg(
    values: Iterable[float] | None,
    *,
    color: str = theme.ACCENT,
    width: int = 82,
    height: int = 25,
) -> str:
    """Render a tiny real-data sparkline as inline SVG."""

    points = [float(value) for value in (values or []) if value is not None and not _missing(value)]
    if len(points) < 2:
        return ""
    low, high = min(points), max(points)
    span = high - low
    if span <= 1e-12:
        span = 1.0
    step = width / (len(points) - 1)
    coords = [
        (round(index * step, 2), round(height - 2 - ((value - low) / span) * (height - 5), 2))
        for index, value in enumerate(points)
    ]
    line = " ".join(f"{x},{y}" for x, y in coords)
    area = f"0,{height} " + line + f" {width},{height}"
    last_x, last_y = coords[-1]
    return (
        f'<svg class="gm-spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'fill="none" aria-hidden="true">'
        f'<polygon points="{area}" fill="{color}" opacity="0.09"></polygon>'
        f'<polyline points="{line}" stroke="{color}" stroke-width="1.4" '
        f'stroke-linecap="round" stroke-linejoin="round" opacity="0.9"></polyline>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2" fill="{color}"></circle>'
        "</svg>"
    )


# ---------------------------------------------------------------------------
# Shell: header, sidebar, page heading
# ---------------------------------------------------------------------------


def app_header(*, meta_html: Sequence[str] = ()) -> None:
    """Render the slim application bar with the GridMind brand."""

    meta = "".join(meta_html)
    st.markdown(
        f"""
        <div class="gm-appbar">
            <div class="gm-brand">
                <div class="gm-logo" aria-hidden="true">
                    <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
                        <path d="M13.2 2.2 4.6 13.4h6.1L9.8 21.8l8.7-11.6h-6.1l.8-8Z"
                              fill="#34D399"/>
                    </svg>
                </div>
                <div>
                    <div class="gm-brand-name">GridMind</div>
                    <div class="gm-brand-sub">Energy market intelligence</div>
                </div>
            </div>
            <div class="gm-app-meta">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_brand(*, version: str = "v0.1.0") -> None:
    """Render the product mark at the top of the sidebar."""

    ver = "v" + str(version).lstrip("vV")
    st.sidebar.markdown(
        f"""
        <div class="gm-side-brand">
            <div class="gm-side-logo" aria-hidden="true">
                <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
                    <defs>
                        <linearGradient id="gm-logo-grad" x1="8" y1="6" x2="40" y2="44"
                                        gradientUnits="userSpaceOnUse">
                            <stop stop-color="#6EE7B7"/>
                            <stop offset="1" stop-color="#38BDF8"/>
                        </linearGradient>
                    </defs>
                    <path d="M24 4 40 13v22L24 44 8 35V13L24 4Z"
                          stroke="url(#gm-logo-grad)" stroke-width="1.6" opacity="0.55"/>
                    <path d="M26.5 10 15 26h8l-2 12 12-17h-8l1.5-11Z" fill="url(#gm-logo-grad)"/>
                    <circle cx="8" cy="13" r="2" fill="#38BDF8"/>
                    <circle cx="40" cy="35" r="2" fill="#34D399"/>
                </svg>
            </div>
            <div class="gm-side-text">
                <div class="gm-side-name">Grid<span>Mind</span></div>
                <div class="gm-side-sub">Smart Grid Control Room</div>
            </div>
        </div>
        <div class="gm-side-meta">
            <span class="gm-side-live"><span class="gm-dot"></span>Local workspace</span>
            <span class="gm-side-ver">{esc(ver)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_section(label: str) -> None:
    """Render a small uppercase section divider in the sidebar."""

    st.sidebar.markdown(f'<div class="gm-side-section">{esc(label)}</div>', unsafe_allow_html=True)


def page_header(
    eyebrow: str,
    title: str,
    subtitle: str,
    *,
    badges: Sequence[str] = (),
) -> None:
    """Render the page-level heading and status badges."""

    badge_html = "".join(badges)
    st.markdown(
        f"""
        <div class="gm-page-head">
            <div>
                <div class="gm-eyebrow">
                    <span class="gm-dot"></span>{esc(eyebrow)}
                </div>
                <div class="gm-page-title">{esc(title)}</div>
                <p class="gm-page-sub">{esc(subtitle)}</p>
            </div>
            <div class="gm-page-badges">{badge_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, *, tone: str = "neutral", dot: bool = False, live: bool = False) -> str:
    """Return an inline status badge."""

    classes = ["gm-badge"]
    if tone != "neutral":
        classes.append(f"gm-badge--{tone}")
    if live:
        classes.append("gm-badge--live")
    marker = '<span class="gm-dot"></span>' if dot else ""
    return f'<span class="{" ".join(classes)}">{marker}{esc(text)}</span>'


def status_badge(*, running: bool, finished: bool) -> str:
    """Return the simulation run-state badge."""

    if finished:
        return badge("Run complete", tone="accent", dot=True)
    if running:
        return badge("Live · stepping", tone="accent", dot=True, live=True)
    return badge("Paused", tone="warning", dot=True)


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Kpi:
    """One KPI card definition."""

    label: str
    value: str
    unit: str = ""
    detail: str = ""
    tone: str = "default"
    spark: Sequence[float] | None = field(default=None)
    help_text: str | None = None
    delta: float | None = None
    delta_good: str = "down"  # "down", "up" or "neutral": which direction is good news
    delta_digits: int = 2


def _delta_chip(item: "Kpi") -> str:
    """Small change-since-previous-hour chip shown next to a KPI value."""

    if item.delta is None or _missing(item.delta):
        return ""
    change = float(item.delta)
    if abs(change) < 1e-9:
        return '<span class="gm-delta gm-delta--flat" title="No change since the previous hour">– 0</span>'
    up = change > 0
    if item.delta_good == "neutral":
        tone = "flat"
    else:
        tone = "good" if up == (item.delta_good == "up") else "bad"
    arrow = "▲" if up else "▼"
    return (
        f'<span class="gm-delta gm-delta--{tone}" title="Change since the previous hour">'
        f"{arrow} {esc(fmt_number(abs(change), item.delta_digits))}</span>"
    )


def kpi_grid(items: Sequence[Kpi]) -> None:
    """Render a responsive grid of compact KPI cards."""

    if not items:
        return
    tone_colors = {
        "default": theme.ACCENT,
        "accent": theme.ACCENT,
        "warning": theme.WARNING,
        "danger": theme.DANGER,
        "info": theme.INFO,
    }
    cards = []
    for item in items:
        help_span = (
            f'<span class="gm-kpi-help" title="{esc(item.help_text)}">?</span>'
            if item.help_text
            else ""
        )
        spark_color = tone_colors.get(item.tone, theme.ACCENT)
        spark = sparkline_svg(item.spark, color=spark_color)
        spark_class = " gm-kpi--spark" if spark else ""
        delta_html = _delta_chip(item)
        cards.append(
            f"""
            <div class="gm-kpi gm-kpi--{esc(item.tone)}{spark_class}">
                <div class="gm-kpi-top">
                    <span class="gm-kpi-label">{esc(item.label)}</span>{help_span}
                </div>
                <div class="gm-kpi-value">{esc(item.value)}<span class="gm-kpi-unit">{esc(item.unit)}</span>{delta_html}</div>
                <div class="gm-kpi-detail"><span>{item.detail}</span></div>
                {spark}
            </div>
            """
        )
    body = "".join(dedent(card).strip() for card in cards)
    st.markdown(
        f'<div class="gm-kpi-grid" style="--gm-cols:{min(5, len(items))}">{body}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Cards, callouts and empty states
# ---------------------------------------------------------------------------


def card_header(
    title: str,
    subtitle: str | None = None,
    *,
    right_html: str = "",
) -> None:
    """Render a chart-card heading with an optional right-hand badge."""

    sub = f'<div class="gm-card-sub">{esc(subtitle)}</div>' if subtitle else ""
    tools = f'<div class="gm-card-tools">{right_html}</div>' if right_html else ""
    st.markdown(
        f'<div class="gm-card-head"><div><div class="gm-card-title">{esc(title)}</div>{sub}</div>{tools}</div>',
        unsafe_allow_html=True,
    )


_ICONS = {
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/>',
    "warning": '<path d="M10.3 3.9 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "danger": '<circle cx="12" cy="12" r="9"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "success": '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.2 2.2 4.8-5"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "activity": '<path d="M3 12h4l2.5-6 4 12 2.5-6H21"/>',
    "table": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18"/><path d="M9 10v10"/>',
}


def _icon(name: str, size: int = 15) -> str:
    path = _ICONS.get(name, _ICONS["info"])
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )


def callout(
    body_html: str,
    *,
    tone: str = "info",
    title: str | None = None,
) -> None:
    """Render an information, warning or success callout."""

    icon_name = {"info": "info", "warning": "warning", "danger": "danger", "success": "success"}.get(
        tone, "info"
    )
    prefix = f"<strong>{esc(title)}</strong> " if title else ""
    st.markdown(
        f'<div class="gm-callout gm-callout--{esc(tone)}">{_icon(icon_name)}'
        f"<div>{prefix}{body_html}</div></div>",
        unsafe_allow_html=True,
    )


def empty_state(
    title: str,
    body: str,
    *,
    hint: str | None = None,
    icon: str = "database",
) -> None:
    """Render a polished empty state with an optional hint."""

    hint_html = f'<div class="gm-empty-hint">{esc(hint)}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="gm-empty">
            <div class="gm-empty-icon">{_icon(icon, 30)}</div>
            <div class="gm-empty-title">{esc(title)}</div>
            <p class="gm-empty-body">{esc(body)}</p>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def error_state(title: str, body: str, *, hint: str | None = None) -> None:
    """Render an error state with the same visual language as empty states."""

    empty_state(title, body, hint=hint, icon="danger")


def definition_grid(rows: Sequence[tuple[str, str]]) -> None:
    """Render a compact two-column definition list."""

    items = "".join(
        f'<div class="gm-def"><div class="gm-def-label">{esc(label)}</div>'
        f'<div class="gm-def-value">{esc(value)}</div></div>'
        for label, value in rows
    )
    st.markdown(f'<div class="gm-def-grid">{items}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data visuals
# ---------------------------------------------------------------------------


def comparison_matrix(
    scenarios: Sequence[str],
    systems: Sequence[str],
    values: Mapping[tuple[str, str], float | None],
    *,
    scenario_labels: Mapping[str, str],
    system_labels: Mapping[str, str],
    system_colors: Mapping[str, str],
    formatter=fmt_money,
    lower_is_better: bool = True,
    tag: str = "BEST",
) -> None:
    """Render a compact scenario-by-system comparison matrix."""

    header = "".join(
        f"<th>{esc(system_labels.get(system, system))}</th>" for system in systems
    )
    body_rows: list[str] = []
    for scenario in scenarios:
        cells: list[str] = []
        row_values = [values.get((scenario, system)) for system in systems]
        numbers = [float(value) for value in row_values if value is not None]
        best_value = (min if lower_is_better else max)(numbers) if numbers else None
        high = max(numbers) if numbers else None
        for system, value in zip(systems, row_values):
            label = esc(system_labels.get(system, system))
            if value is None or _missing(value):
                cells.append(
                    f'<td class="gm-cell" data-label="{label}">'
                    f'<span class="gm-cell-value">—</span></td>'
                )
                continue
            number = float(value)
            width = 0.0 if high in (None, 0) else max(6.0, 100.0 * number / high)
            is_best = best_value is not None and abs(number - best_value) <= 1e-9 * max(
                1.0, abs(best_value)
            )
            color = system_colors.get(system, theme.ACCENT)
            tag_html = f'<span class="gm-best-tag">{esc(tag)}</span>' if is_best else ""
            value_class = "gm-cell-value gm-best" if is_best else "gm-cell-value"
            cells.append(
                f'<td class="gm-cell" data-label="{label}">'
                f'<span class="gm-cell-bar" style="width:{width:.1f}%;background:{color}1F"></span>'
                f'<span class="{value_class}">{esc(formatter(number))}{tag_html}</span></td>'
            )
        body_rows.append(
            f"<tr><td>{esc(scenario_labels.get(scenario, scenario))}</td>{''.join(cells)}</tr>"
        )
    st.markdown(
        f'<div class="gm-table-wrap"><table class="gm-table"><thead><tr><th>Scenario</th>{header}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def bar_list(rows: Sequence[tuple[str, float | None, str]]) -> None:
    """Render labelled horizontal bars from real values."""

    valid = [float(value) for _, value, _ in rows if value is not None and not _missing(value)]
    high = max(valid) if valid else None
    html_rows = []
    for label, value, color in rows:
        width = 0.0 if value is None or high in (None, 0) else max(2.0, 100.0 * float(value) / high)
        display = "—" if value is None or _missing(value) else fmt_number(value, 2)
        html_rows.append(
            f'<div class="gm-bar-row"><div class="gm-bar-label">{esc(label)}</div>'
            f'<div class="gm-bar-track"><div class="gm-bar-fill" style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="gm-bar-value">{esc(display)}</div></div>'
        )
    st.markdown(f'<div class="gm-bar-list">{"".join(html_rows)}</div>', unsafe_allow_html=True)


def action_distribution(counts: Mapping[int, int]) -> None:
    """Render the greedy action mix as a stacked bar plus legend."""

    total = sum(int(value) for value in counts.values()) or 1
    order = (0, 1, 2)
    segments = "".join(
        f'<span style="width:{100.0 * int(counts.get(action, 0)) / total:.2f}%;'
        f'background:{theme.ACTION_COLORS[action]}"></span>'
        for action in order
        if counts.get(action, 0)
    )
    legend = "".join(
        f'<span class="gm-legend-item"><span class="gm-legend-dot" '
        f'style="background:{theme.ACTION_COLORS[action]}"></span>'
        f"{esc(theme.ACTION_LABELS[action])} · {int(counts.get(action, 0))} "
        f"({100.0 * int(counts.get(action, 0)) / total:.0f}%)</span>"
        for action in order
    )
    st.markdown(
        f'<div class="gm-stack">{segments}</div><div class="gm-legend">{legend}</div>',
        unsafe_allow_html=True,
    )


def q_value_rows(values: Sequence[float], selected_action: int) -> None:
    """Render the three Q-values of a selected state with the chosen action marked."""

    low = min(float(value) for value in values)
    high = max(float(value) for value in values)
    span = high - low or 1.0
    rows = []
    for action, value in enumerate(values):
        width = 8.0 + 92.0 * (float(value) - low) / span
        selected = action == selected_action
        state_class = "gm-state-row is-selected" if selected else "gm-state-row"
        label = theme.ACTION_LABELS.get(action, str(action))
        delta = ' <span class="gm-best-tag">GREEDY</span>' if selected else ""
        rows.append(
            f'<div class="{state_class}"><span class="gm-state-name">{esc(label)}</span>'
            f'<span class="gm-state-value">{esc(fmt_signed(value, 2))}{delta}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def environment_panel(environment: Mapping[str, float]) -> None:
    """Render weather and solar measurements with compact magnitude bars."""

    temperature = float(environment.get("temperature_c", 0.0))
    cloud = float(environment.get("effective_cloud_cover", 0.0))
    wind = float(environment.get("wind_index", 0.0))
    solar = float(environment.get("solar_profile", 0.0))
    rows = (
        ("Temperature", max(0.0, min(1.0, (temperature + 5.0) / 45.0)), f"{temperature:.1f} °C", theme.WARNING),
        ("Cloud cover", max(0.0, min(1.0, cloud)), f"{cloud:.0%}", theme.INFO),
        ("Wind index", max(0.0, min(1.0, wind)), f"{wind:.2f}", "#38BDF8"),
        ("Solar profile", max(0.0, min(1.0, solar)), f"{solar:.0%}", "#FACC15"),
    )
    html_rows = "".join(
        f'<div class="gm-env-row"><span class="gm-env-label">{esc(label)}</span>'
        f'<span class="gm-env-track"><span class="gm-env-fill" style="width:{width * 100:.1f}%;background:{color}"></span></span>'
        f'<span class="gm-env-value">{esc(value)}</span></div>'
        for label, width, value, color in rows
    )
    st.markdown(html_rows, unsafe_allow_html=True)


def event_timeline(snapshot: Mapping[str, object], *, limit: int = 4) -> None:
    """Render scheduled and active events for the live run."""

    t = int(snapshot.get("t", 0))
    steps = int(snapshot.get("steps", 0))
    events = list(snapshot.get("scheduled_events", []) or [])
    if not events:
        empty_state(
            "No scheduled events",
            "This run has no disruption events in its scenario catalogue.",
            icon="activity",
        )
        return
    decorated = []
    for event in events:
        start = int(event.get("t_start", 0))
        end = int(event.get("t_end", start))
        active = start <= t < end
        upcoming = start > t
        decorated.append((0 if active else 1 if upcoming else 2, start, end, event, active, upcoming))
    decorated.sort(key=lambda item: (item[0], item[1]))
    rows = []
    for _, start, end, event, active, upcoming in decorated[:limit]:
        name = str(event.get("name", "event")).replace("_", " ").title()
        if active:
            state = badge("Active now", tone="warning", dot=True, live=True)
        elif upcoming:
            state = badge(f"in {max(0, start - t)} h", tone="info")
        else:
            state = badge("Passed")
        rows.append(
            f'<div class="gm-event"><div class="gm-event-time">H{start:03d}</div>'
            f'<div class="gm-event-body"><div class="gm-event-name">{esc(name)}</div>'
            f'<div class="gm-event-meta">steps {start}–{min(end, steps)} · {max(0, end - start)} h</div></div>'
            f'<div style="margin-left:auto">{state}</div></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def clock_panel(
    *,
    t: int,
    steps: int,
    day: int,
    hour: int,
    speed: int,
    running: bool,
    finished: bool,
) -> None:
    """Render the simulation clock summary used above the playback controls."""

    state = "COMPLETE" if finished else "RUNNING" if running else "PAUSED"
    tone = "accent" if running and not finished else "warning" if not finished else "info"
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
            <div>
                <div class="gm-card-sub">Simulation clock</div>
                <div style="font-family:var(--gm-mono);font-size:1.15rem;color:#F4F8FB;margin-top:2px">
                    Hour {t} <span style="color:#617084">/ {steps}</span>
                    <span style="color:#617084;font-size:.72rem;margin-left:8px">Day {day + 1} · {hour:02d}:00</span>
                </div>
            </div>
            <div style="display:flex;gap:6px;align-items:center">
                {badge(state, tone=tone, dot=True, live=running and not finished)}
                {badge(f"{speed}× speed")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stacked_definition(rows: Sequence[tuple[str, str]]) -> None:
    """Alias for :func:`definition_grid` kept for readability in views."""

    definition_grid(rows)


# ---------------------------------------------------------------------------
# Control-room components
# ---------------------------------------------------------------------------


def control_bar(
    *,
    t: int,
    steps: int,
    day: int,
    hour: int,
    speed: int,
    running: bool,
    finished: bool,
    price: float,
    supply: float,
    demand: float,
    level: str = "normal",
    level_label: str = "Nominal",
) -> None:
    """Render the sticky control-room status strip above the playback buttons."""

    state_text = "COMPLETE" if finished else "LIVE" if running else "PAUSED"
    state_tone = "info" if finished else "accent" if running else "warning"
    level_tone = {"critical": "danger", "warning": "warning", "event": "info"}.get(level, "accent")
    balance = supply - demand
    balance_class = " is-bad" if balance < -1e-9 else ""
    cells = (
        ("Hour", f"{t:03d}", f"/ {steps}", ""),
        ("Day · time", f"D{day + 1}", f"{hour:02d}:00", ""),
        ("Price", fmt_number(price, 2), "per MWh", ""),
        ("Supply", fmt_number(supply, 1), "MW", ""),
        ("Demand", fmt_number(demand, 1), "MW", ""),
        ("Balance", fmt_signed(balance, 1), "MW", balance_class),
    )
    cell_html = "".join(
        f'<div class="gm-cb-cell{extra}"><span class="gm-cb-label">{esc(label)}</span>'
        f'<span class="gm-cb-value">{esc(value)}<em>{esc(unit)}</em></span></div>'
        for label, value, unit, extra in cells
    )
    st.markdown(
        '<div class="gm-cb">'
        '<div class="gm-cb-state">'
        f"{badge(state_text, tone=state_tone, dot=True, live=running and not finished)}"
        f"{badge(level_label, tone=level_tone, dot=True)}"
        "</div>"
        f'<div class="gm-cb-metrics">{cell_html}</div>'
        f'<div class="gm-cb-speed">{badge(f"{speed}× speed")}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def alert_banner(*, level: str, title: str, body_html: str) -> None:
    """Render a prominent grid alert (critical, warning or event)."""

    st.markdown(
        f'<div class="gm-alert gm-alert--{esc(level)}" role="alert">'
        '<span class="gm-alert-dot"></span>'
        f'<div><div class="gm-alert-title">{esc(title)}</div>'
        f'<div class="gm-alert-body">{body_html}</div></div></div>',
        unsafe_allow_html=True,
    )


def winner_grid(rows: Sequence[tuple[str, str, str, str, str]]) -> None:
    """Render best-system tiles: (metric label, system name, colour, value, hint)."""

    tiles = "".join(
        f'<div class="gm-win" style="--gm-win:{esc(color)}">'
        f'<div class="gm-win-label">{esc(label)}</div>'
        f'<div class="gm-win-name">{esc(system)}</div>'
        f'<div class="gm-win-value">{esc(value)}</div>'
        f'<div class="gm-win-hint">{esc(hint)}</div></div>'
        for label, system, color, value, hint in rows
    )
    st.markdown(f'<div class="gm-win-grid">{tiles}</div>', unsafe_allow_html=True)