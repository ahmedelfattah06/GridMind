"""Design tokens, global CSS and Plotly styling for the GridMind dashboard.

Smart Grid Control Room theme: near-black blueprint surfaces, emerald primary
accent, sky-blue secondary accent, amber warnings and red critical states.
Every colour, border and radius is defined once here. The module contains no
simulation logic and keeps the same public API as before.
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

BG = "#070B10"
SURFACE = "#0F151D"
ELEVATED = "#141D27"
BORDER = "#1F2A37"
BORDER_STRONG = "#2C3A4C"
TEXT = "#E6EDF3"
TEXT_STRONG = "#F7FAFC"
MUTED = "#94A3B8"
FAINT = "#64748B"
ACCENT = "#34D399"
ACCENT_STRONG = "#10B981"
SECONDARY = "#38BDF8"
WARNING = "#FBBF24"
DANGER = "#F87171"
INFO = "#38BDF8"
GRID = "rgba(148, 163, 184, 0.07)"

FONT_UI = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Cascadia Code', 'SFMono-Regular', Consolas, monospace"

PLOTLY_CONFIG: dict[str, Any] = {
    "displayModeBar": False,
    "displaylogo": False,
    "responsive": True,
}

SYSTEM_COLORS: dict[str, str] = {
    "auction": "#34D399",
    "auction_q": "#38BDF8",
    "central_1h": "#FBBF24",
    "central_6h": "#A78BFA",
}

AGENT_COLORS: dict[str, str] = {
    "solar": "#FACC15",
    "wind": "#38BDF8",
    "thermal": "#FB923C",
    "peaker": "#F87171",
    "storage": "#34D399",
    "battery": "#34D399",
    "hospital": "#F472B6",
    "residential": "#A78BFA",
    "factory": "#94A3B8",
    "unknown": "#64748B",
}

ROLE_COLORS: dict[str, str] = {
    "producer": "#34D399",
    "consumer": "#A78BFA",
    "storage": "#38BDF8",
}

ACTION_COLORS: dict[int, str] = {
    0: "#94A3B8",
    1: "#34D399",
    2: "#FBBF24",
}

ACTION_LABELS: dict[int, str] = {
    0: "Wait",
    1: "Charge",
    2: "Discharge",
}

CATEGORICAL: list[str] = [
    "#34D399",
    "#38BDF8",
    "#A78BFA",
    "#FBBF24",
    "#F472B6",
    "#F87171",
    "#FACC15",
    "#94A3B8",
]

# ---------------------------------------------------------------------------
# Global stylesheet
# ---------------------------------------------------------------------------

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;650;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --gm-bg: #070B10;
    --gm-surface: #0F151D;
    --gm-surface-2: #0B1017;
    --gm-elevated: #141D27;
    --gm-border: #1F2A37;
    --gm-border-soft: #172130;
    --gm-border-strong: #2C3A4C;
    --gm-text: #E6EDF3;
    --gm-text-strong: #F7FAFC;
    --gm-muted: #94A3B8;
    --gm-faint: #64748B;
    --gm-accent: #34D399;
    --gm-accent-strong: #10B981;
    --gm-secondary: #38BDF8;
    --gm-warning: #FBBF24;
    --gm-danger: #F87171;
    --gm-info: #38BDF8;
    --gm-ui: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
    --gm-mono: 'JetBrains Mono', 'Cascadia Code', 'SFMono-Regular', Consolas, monospace;
    --gm-radius: 12px;
    --gm-shadow: 0 1px 0 rgba(255,255,255,0.035) inset, 0 14px 34px rgba(0, 0, 0, 0.35);
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background: var(--gm-bg);
    color: var(--gm-text);
    font-family: var(--gm-ui);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    font-variant-numeric: tabular-nums;
}

/* Blueprint grid + ambient glows behind the whole console */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1100px 460px at 14% -16%, rgba(52, 211, 153, 0.075), transparent 62%),
        radial-gradient(900px 400px at 90% -20%, rgba(56, 189, 248, 0.055), transparent 64%),
        linear-gradient(rgba(148, 163, 184, 0.028) 1px, transparent 1px) 0 0 / 44px 44px,
        linear-gradient(90deg, rgba(148, 163, 184, 0.028) 1px, transparent 1px) 0 0 / 44px 44px,
        var(--gm-bg);
}

[data-testid="stHeader"] { height: 0; min-height: 0; background: transparent; border: none; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { visibility: hidden; }
/* The button that re-opens a collapsed sidebar lives inside the toolbar: keep it visible. */
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    visibility: visible !important;
    position: fixed !important;
    top: 14px;
    left: 14px;
    z-index: 1000002;
    display: flex !important;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: 1px solid rgba(52, 211, 153, 0.4);
    border-radius: 10px;
    background: rgba(15, 21, 29, 0.94);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5), 0 0 16px rgba(52, 211, 153, 0.12);
}
[data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapsedControl"] *,
[data-testid="collapsedControl"] * { visibility: visible !important; color: var(--gm-accent) !important; }
#MainMenu, footer, [data-testid="stStatusWidget"] { visibility: hidden; }

.block-container { max-width: 1500px; padding: 1.2rem 2rem 3.2rem; }

h1, h2, h3, h4, h5 { font-family: var(--gm-ui); letter-spacing: -0.025em; color: var(--gm-text-strong); }
p, li, label, span, div { font-family: var(--gm-ui); }
a { color: var(--gm-accent); text-decoration: none; }
a:hover { text-decoration: underline; }

code, pre, kbd { font-family: var(--gm-mono) !important; }
code {
    color: #A7F3D0 !important;
    background: rgba(52, 211, 153, 0.08) !important;
    border: 1px solid rgba(52, 211, 153, 0.18);
    border-radius: 5px;
    padding: 1px 5px;
    font-size: 0.82em;
}
hr { border-color: var(--gm-border) !important; }

/* Scrollbars */
* { scrollbar-width: thin; scrollbar-color: #2C3A4C transparent; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #243142; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #33465C; }

/* Sidebar ---------------------------------------------------------------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0A1119 0%, #070C12 100%);
    border-right: 1px solid var(--gm-border);
}
section[data-testid="stSidebar"][aria-expanded="true"] { min-width: 290px; }
section[data-testid="stSidebar"] > div { padding-top: 0.6rem; }
section[data-testid="stSidebar"] .block-container { padding: 0.7rem 1rem 2rem; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--gm-muted); }
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: #A9B6C6;
    font-size: 0.74rem;
    font-weight: 500;
    letter-spacing: 0.01em;
}
[data-testid="stSidebarCollapseButton"] button { color: var(--gm-muted); }


/* Sidebar: no scrollbar (it steals width from the controls) and full-width nav */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] * {
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}
section[data-testid="stSidebar"]::-webkit-scrollbar,
section[data-testid="stSidebar"] *::-webkit-scrollbar { width: 0 !important; height: 0 !important; display: none !important; }
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"],
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] > div { width: 100%; }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] { box-sizing: border-box; flex: 1 1 100%; }

/* Navigation (radio restyled as a vertical nav list) */
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] { gap: 4px; }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    margin: 0;
    padding: 9px 11px 9px 13px;
    border: 1px solid transparent;
    border-radius: 9px;
    color: var(--gm-muted);
    font-size: 0.86rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] > div > div:first-child { display: none; }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover { background: #0F1822; color: var(--gm-text); }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] {
    background: linear-gradient(90deg, rgba(52, 211, 153, 0.12), rgba(52, 211, 153, 0.02));
    border-color: rgba(52, 211, 153, 0.22);
    color: var(--gm-text-strong);
}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"]::after {
    content: "";
    position: absolute;
    left: -1px; top: 20%; bottom: 20%;
    width: 3px;
    border-radius: 3px;
    background: var(--gm-accent);
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.8);
}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"]::before { color: var(--gm-accent); }
section[data-testid="stSidebar"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {
    color: inherit; font-size: 0.86rem; font-weight: 500; margin: 0;
}
section[data-testid="stSidebar"] label[data-testid="stRadioOption"]::before {
    content: "";
    flex: 0 0 16px;
    width: 16px;
    height: 16px;
    background: currentColor;
    -webkit-mask-position: center; -webkit-mask-repeat: no-repeat; -webkit-mask-size: contain;
    mask-position: center; mask-repeat: no-repeat; mask-size: contain;
}
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] > div:nth-child(1) label::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12h4l2.5-6 4 12 2.5-6H21'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 12h4l2.5-6 4 12 2.5-6H21'/%3E%3C/svg%3E");
}
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] > div:nth-child(2) label::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19V9m5 10V5m5 14v-7m5 7V8'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 19V9m5 10V5m5 14v-7m5 7V8'/%3E%3C/svg%3E");
}
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] > div:nth-child(3) label::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 20V10m5 10V4m5 16v-7m5 7V7'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4 20V10m5 10V4m5 16v-7m5 7V7'/%3E%3C/svg%3E");
}
section[data-testid="stSidebar"] div[data-testid="stRadioGroup"] > div:nth-child(4) label::before {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a4 4 0 0 0-4 4 4 4 0 0 0-1 7.8V17a3 3 0 0 0 5 2.2A3 3 0 0 0 17 17v-2.2A4 4 0 0 0 16 7a4 4 0 0 0-4-4Z'/%3E%3Cpath d='M12 3v16'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a4 4 0 0 0-4 4 4 4 0 0 0-1 7.8V17a3 3 0 0 0 5 2.2A3 3 0 0 0 17 17v-2.2A4 4 0 0 0 16 7a4 4 0 0 0-4-4Z'/%3E%3Cpath d='M12 3v16'/%3E%3C/svg%3E");
}

/* Buttons ---------------------------------------------------------------- */
div.stButton > button, div.stDownloadButton > button {
    border-radius: 8px;
    border: 1px solid var(--gm-border-strong);
    background: linear-gradient(180deg, #141D27 0%, #0F151D 100%);
    color: var(--gm-text);
    font-family: var(--gm-ui);
    font-weight: 550;
    font-size: 0.8rem;
    letter-spacing: 0.01em;
    padding: 0.46rem 0.9rem;
    min-height: 38px;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease, transform 140ms ease, box-shadow 140ms ease;
}
div.stButton > button:hover, div.stDownloadButton > button:hover {
    border-color: rgba(52, 211, 153, 0.5);
    color: #FFFFFF;
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(52, 211, 153, 0.12);
}
div.stButton > button:active, div.stDownloadButton > button:active { transform: translateY(0); }
div.stButton > button:focus-visible, div.stDownloadButton > button:focus-visible {
    outline: 2px solid rgba(52, 211, 153, 0.5);
    outline-offset: 2px;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(180deg, #3FE0A5 0%, #22C58B 100%);
    border-color: #3FE0A5;
    color: #031109;
    font-weight: 650;
    box-shadow: 0 6px 20px rgba(52, 211, 153, 0.22);
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(180deg, #5BEBB6 0%, #34D399 100%);
    border-color: #5BEBB6;
    color: #020D06;
    box-shadow: 0 8px 26px rgba(52, 211, 153, 0.36);
}
div.stButton > button:disabled {
    background: #0A1017;
    border-color: #18222E;
    color: #4A586A;
    transform: none;
    box-shadow: none;
}

/* Widgets ---------------------------------------------------------------- */
div[data-baseweb="select"] > div {
    background: var(--gm-surface);
    border-color: var(--gm-border);
    border-radius: 8px;
    color: var(--gm-text);
    min-height: 39px;
}
div[data-baseweb="select"] > div:hover { border-color: var(--gm-border-strong); }
div[data-baseweb="select"] input, div[data-baseweb="select"] div { color: var(--gm-text); }
div[data-baseweb="select"] svg { fill: var(--gm-muted); }
div[data-baseweb="popover"] ul {
    background: #101821;
    border: 1px solid var(--gm-border-strong);
    border-radius: 10px;
}
div[data-baseweb="popover"] li { color: var(--gm-text); background: #101821; }
div[data-baseweb="popover"] li:hover { background: #1A2533; }

[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input {
    background: var(--gm-surface) !important;
    border-color: var(--gm-border) !important;
    color: var(--gm-text) !important;
    border-radius: 8px !important;
    font-family: var(--gm-mono) !important;
}
[data-testid="stNumberInput"] button { background: var(--gm-surface); border-color: var(--gm-border); color: var(--gm-muted); }
[data-testid="stNumberInput"] button:hover { background: var(--gm-elevated); color: var(--gm-text); }

[data-testid="stSlider"] [role="slider"] {
    background: var(--gm-accent);
    border-color: var(--gm-accent);
    box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.16), 0 0 12px rgba(52, 211, 153, 0.45);
}
[data-testid="stSlider"] [data-testid="stTickBar"] { color: var(--gm-faint); }

span[data-baseweb="tag"] {
    background: rgba(52, 211, 153, 0.13) !important;
    border: 1px solid rgba(52, 211, 153, 0.26);
    color: #B7F7DC !important;
    border-radius: 6px !important;
}
span[data-baseweb="tag"] svg { fill: #B7F7DC; }

[data-testid="stMultiSelect"] div[role="group"]:has(> [data-testid="stMultiSelectTagsContainer"]) {
    height: auto !important;
    min-height: 40px !important;
    max-height: none !important;
    align-items: stretch !important;
}
[data-testid="stMultiSelectTagsContainer"] {
    flex-wrap: wrap !important;
    overflow: visible !important;
    height: auto !important;
    row-gap: 4px;
}

[data-testid="stProgress"] > div > div { background: #151F2B; border-radius: 999px; }
[data-testid="stProgress"] [role="progressbar"] > div {
    background: linear-gradient(90deg, #10B981, #34D399 60%, #38BDF8) !important;
    border-radius: 999px;
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.35);
}
[data-testid="stProgress"] p { color: var(--gm-faint); font-size: 0.72rem; font-family: var(--gm-mono); }

/* Panels (bordered containers) with control-room corner ticks ------------- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    position: relative;
    background: linear-gradient(180deg, rgba(20, 29, 39, 0.78) 0%, rgba(15, 21, 29, 0.96) 100%);
    border: 1px solid var(--gm-border);
    border-radius: var(--gm-radius);
    padding: 0.95rem 1.05rem 0.85rem;
    box-shadow: var(--gm-shadow);
    transition: border-color 160ms ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]::before,
div[data-testid="stVerticalBlockBorderWrapper"]::after {
    content: "";
    position: absolute;
    width: 9px;
    height: 9px;
    pointer-events: none;
    border-color: rgba(52, 211, 153, 0.45);
    border-style: solid;
    opacity: 0.85;
}
div[data-testid="stVerticalBlockBorderWrapper"]::before { top: 5px; left: 5px; border-width: 1px 0 0 1px; border-top-left-radius: 4px; }
div[data-testid="stVerticalBlockBorderWrapper"]::after { bottom: 5px; right: 5px; border-width: 0 1px 1px 0; border-bottom-right-radius: 4px; }
div[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color: #2A3A4F; }
div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] { gap: 0.35rem; }

/* Tabs ------------------------------------------------------------------- */
div[data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--gm-border); padding-bottom: 2px; }
button[data-baseweb="tab"] {
    background: transparent;
    color: var(--gm-muted);
    border-radius: 7px 7px 0 0;
    font-family: var(--gm-ui);
    font-size: 0.8rem;
    font-weight: 550;
    letter-spacing: 0.01em;
    padding: 8px 13px;
}
button[data-baseweb="tab"]:hover { color: var(--gm-text); background: #0F1822; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--gm-text-strong); }
div[data-baseweb="tab-highlight"] { background: var(--gm-accent); height: 2px; box-shadow: 0 0 10px rgba(52, 211, 153, 0.6); }
div[data-baseweb="tab-border"] { background: transparent; }

/* Expanders -------------------------------------------------------------- */
details, div[data-testid="stExpander"] {
    border: 1px solid var(--gm-border) !important;
    border-radius: 10px !important;
    background: rgba(15, 21, 29, 0.65);
    overflow: hidden;
}
div[data-testid="stExpander"] summary { color: var(--gm-muted); font-size: 0.82rem; }
div[data-testid="stExpander"] summary:hover { color: var(--gm-text); }

/* Dataframes ------------------------------------------------------------- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--gm-border);
    border-radius: 10px;
    overflow: hidden;
    background: var(--gm-surface);
}
[data-testid="stDataFrame"] [role="columnheader"] { font-family: var(--gm-ui); font-weight: 600; }

/* Alerts and images ------------------------------------------------------ */
[data-testid="stAlert"] {
    border-radius: 10px;
    border: 1px solid var(--gm-border);
    background: var(--gm-surface);
    color: var(--gm-text);
}
img { border-radius: 8px; }
[data-testid="stImage"] img {
    background: #F8FAFC;
    padding: 10px;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}
[data-testid="stImageCaption"] { text-align: left !important; padding-top: 9px !important; }
[data-testid="stImageCaption"] p {
    color: var(--gm-muted) !important;
    font-size: 0.78rem !important;
    line-height: 1.45 !important;
    text-align: left !important;
}
[data-testid="stImageCaption"] a { display: none; }

/* App bar ---------------------------------------------------------------- */
.gm-appbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 4px 0 14px;
    border-bottom: 1px solid var(--gm-border);
    margin-bottom: 20px;
    position: relative;
}
.gm-appbar::after {
    content: "";
    position: absolute;
    left: 0; bottom: -1px;
    width: 160px; height: 1px;
    background: linear-gradient(90deg, var(--gm-accent), transparent);
}
.gm-brand { display: flex; align-items: center; gap: 11px; min-width: 0; }
.gm-logo {
    width: 36px;
    height: 36px;
    flex: 0 0 36px;
    border-radius: 9px;
    border: 1px solid rgba(52, 211, 153, 0.35);
    background: linear-gradient(145deg, #0F2D25 0%, #08171A 100%);
    display: grid;
    place-items: center;
    box-shadow: 0 0 0 1px rgba(52,211,153,0.06), 0 8px 22px rgba(0, 0, 0, 0.35), 0 0 20px rgba(52, 211, 153, 0.12);
}
.gm-brand-name { color: var(--gm-text-strong); font-size: 15px; font-weight: 650; letter-spacing: -0.02em; line-height: 1.15; }
.gm-brand-sub {
    color: var(--gm-faint);
    font-size: 10px;
    font-family: var(--gm-mono);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 3px;
}
.gm-app-meta { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; justify-content: flex-end; }

/* Page heading ----------------------------------------------------------- */
.gm-page-head {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 24px;
    padding: 2px 0 20px;
    margin-bottom: 18px;
    border-bottom: 1px solid var(--gm-border);
    animation: gm-rise 320ms ease-out both;
}
.gm-eyebrow {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--gm-accent);
    font-family: var(--gm-mono);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}
.gm-eyebrow .gm-dot { box-shadow: 0 0 8px currentColor; }
.gm-page-title {
    color: var(--gm-text-strong);
    font-size: clamp(1.65rem, 2.5vw, 2.2rem);
    font-weight: 650;
    letter-spacing: -0.035em;
    line-height: 1.1;
    margin: 8px 0 7px;
}
.gm-page-sub { color: var(--gm-muted); font-size: 0.9rem; line-height: 1.6; max-width: 72ch; margin: 0; }
.gm-page-badges { display: flex; align-items: center; justify-content: flex-end; gap: 7px; flex-wrap: wrap; padding-bottom: 3px; }

/* Badges / status LEDs --------------------------------------------------- */
.gm-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 9px;
    border: 1px solid var(--gm-border);
    border-radius: 6px;
    background: rgba(20, 29, 39, 0.8);
    color: var(--gm-muted);
    font-family: var(--gm-mono);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    white-space: nowrap;
    line-height: 1.3;
}
.gm-badge--accent { color: #8AF0C5; border-color: rgba(52, 211, 153, 0.32); background: rgba(52, 211, 153, 0.08); }
.gm-badge--warning { color: #FCD34D; border-color: rgba(251, 191, 36, 0.34); background: rgba(251, 191, 36, 0.08); }
.gm-badge--danger { color: #FCA5A5; border-color: rgba(248, 113, 113, 0.34); background: rgba(248, 113, 113, 0.09); }
.gm-badge--info { color: #7DD3FC; border-color: rgba(56, 189, 248, 0.34); background: rgba(56, 189, 248, 0.08); }
.gm-badge--violet { color: #C4B5FD; border-color: rgba(167, 139, 250, 0.34); background: rgba(167, 139, 250, 0.08); }
.gm-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.gm-badge .gm-dot { box-shadow: 0 0 7px currentColor; }
.gm-badge--live .gm-dot { animation: gm-pulse 2.0s ease-out infinite; }

/* KPI cards -------------------------------------------------------------- */
.gm-kpi-grid {
    display: grid;
    grid-template-columns: repeat(var(--gm-cols, 5), minmax(0, 1fr));
    gap: 11px;
    margin: 2px 0 18px;
    animation: gm-rise 360ms ease-out both;
}
.gm-kpi {
    position: relative;
    min-height: 112px;
    padding: 14px 16px 12px 18px;
    border: 1px solid var(--gm-border);
    border-radius: 12px;
    background:
        radial-gradient(220px 90px at 100% 0%, rgba(52, 211, 153, 0.06), transparent 70%),
        linear-gradient(180deg, rgba(20, 29, 39, 0.92) 0%, rgba(15, 21, 29, 0.98) 100%);
    box-shadow: var(--gm-shadow);
    overflow: hidden;
    transition: border-color 150ms ease, transform 150ms ease;
}
/* status rail on the left edge, coloured by tone */
.gm-kpi::before {
    content: "";
    position: absolute;
    left: 0; top: 14px; bottom: 14px;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: var(--gm-accent);
    box-shadow: 0 0 12px rgba(52, 211, 153, 0.55);
}
.gm-kpi--warning::before { background: var(--gm-warning); box-shadow: 0 0 12px rgba(251, 191, 36, 0.55); }
.gm-kpi--danger::before { background: var(--gm-danger); box-shadow: 0 0 12px rgba(248, 113, 113, 0.6); }
.gm-kpi--info::before { background: var(--gm-secondary); box-shadow: 0 0 12px rgba(56, 189, 248, 0.55); }
.gm-kpi--warning { background: radial-gradient(220px 90px at 100% 0%, rgba(251, 191, 36, 0.06), transparent 70%), linear-gradient(180deg, rgba(20, 29, 39, 0.92), rgba(15, 21, 29, 0.98)); }
.gm-kpi--danger { background: radial-gradient(220px 90px at 100% 0%, rgba(248, 113, 113, 0.08), transparent 70%), linear-gradient(180deg, rgba(20, 29, 39, 0.92), rgba(15, 21, 29, 0.98)); }
.gm-kpi--info { background: radial-gradient(220px 90px at 100% 0%, rgba(56, 189, 248, 0.07), transparent 70%), linear-gradient(180deg, rgba(20, 29, 39, 0.92), rgba(15, 21, 29, 0.98)); }
.gm-kpi:hover { border-color: #2E3F55; transform: translateY(-1px); }
.gm-kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.gm-kpi-label {
    color: var(--gm-muted);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.gm-kpi-help {
    display: inline-grid;
    place-items: center;
    width: 15px;
    height: 15px;
    flex: 0 0 15px;
    border-radius: 50%;
    border: 1px solid var(--gm-border-strong);
    color: var(--gm-faint);
    font-family: var(--gm-mono);
    font-size: 9px;
    cursor: help;
}
.gm-kpi-value {
    color: var(--gm-text-strong);
    font-family: var(--gm-mono);
    font-size: 1.6rem;
    font-weight: 600;
    letter-spacing: -0.045em;
    line-height: 1.1;
    margin-top: 10px;
    white-space: nowrap;
}
.gm-kpi-unit { color: var(--gm-faint); font-size: 0.68rem; font-family: var(--gm-mono); margin-left: 7px; letter-spacing: 0.02em; text-transform: uppercase; }
.gm-kpi-detail { display: block; color: var(--gm-faint); font-size: 0.7rem; line-height: 1.4; margin-top: 6px; }
.gm-kpi--spark .gm-kpi-detail { padding-right: 90px; }
.gm-kpi-detail strong { color: var(--gm-muted); font-weight: 550; }
/* the component renders the sparkline as .gm-spark */
.gm-spark, .gm-kpi-spark { position: absolute; right: 13px; bottom: 12px; opacity: 0.95; }
.gm-kpi--accent .gm-kpi-value { color: #6EE7B7; text-shadow: 0 0 22px rgba(52, 211, 153, 0.25); }
.gm-kpi--warning .gm-kpi-value { color: #FCD34D; text-shadow: 0 0 22px rgba(251, 191, 36, 0.22); }
.gm-kpi--danger .gm-kpi-value { color: #FCA5A5; text-shadow: 0 0 22px rgba(248, 113, 113, 0.28); }
.gm-kpi--info .gm-kpi-value { color: #7DD3FC; text-shadow: 0 0 22px rgba(56, 189, 248, 0.25); }

/* Card headings ---------------------------------------------------------- */
.gm-card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin: 0 0 6px; }
.gm-card-title {
    color: #EDF3F8;
    font-size: 0.78rem;
    font-weight: 650;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1.3;
}
.gm-card-sub { color: var(--gm-faint); font-size: 0.72rem; line-height: 1.5; margin-top: 3px; }
.gm-card-tools { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }

/* Callouts / empty states ------------------------------------------------ */
.gm-callout {
    display: flex;
    align-items: flex-start;
    gap: 9px;
    padding: 10px 12px;
    margin: 4px 0 14px;
    border: 1px solid var(--gm-border);
    border-left-width: 3px;
    border-radius: 8px;
    background: rgba(15, 21, 29, 0.75);
    color: #B8C4D1;
    font-size: 0.78rem;
    line-height: 1.55;
}
.gm-callout svg { flex: 0 0 15px; margin-top: 2px; }
.gm-callout strong { color: var(--gm-text); font-weight: 600; }
.gm-callout--warning { border-color: rgba(251, 191, 36, 0.28); border-left-color: var(--gm-warning); background: rgba(251, 191, 36, 0.055); color: #EBD8AE; }
.gm-callout--danger { border-color: rgba(248, 113, 113, 0.28); border-left-color: var(--gm-danger); background: rgba(248, 113, 113, 0.06); color: #F2C0C0; }
.gm-callout--success { border-color: rgba(52, 211, 153, 0.26); border-left-color: var(--gm-accent); background: rgba(52, 211, 153, 0.05); color: #B6E9D3; }
.gm-callout--info { border-color: rgba(56, 189, 248, 0.26); border-left-color: var(--gm-secondary); background: rgba(56, 189, 248, 0.05); color: #BDE3F7; }

.gm-empty {
    border: 1px dashed #2A394C;
    border-radius: 12px;
    background: rgba(15, 21, 29, 0.5);
    padding: 30px 22px;
    text-align: center;
    margin: 8px 0 16px;
}
.gm-empty-icon { color: #52657A; margin-bottom: 10px; }
.gm-empty-title { color: var(--gm-text); font-size: 0.95rem; font-weight: 600; margin-bottom: 6px; }
.gm-empty-body { color: var(--gm-muted); font-size: 0.81rem; line-height: 1.6; max-width: 62ch; margin: 0 auto; }
.gm-empty-hint { color: var(--gm-faint); font-size: 0.73rem; line-height: 1.6; margin-top: 9px; font-family: var(--gm-mono); }

/* Definition grid / environment / events --------------------------------- */
.gm-def-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 11px 20px; }
.gm-def { border-bottom: 1px solid var(--gm-border-soft); padding-bottom: 8px; min-width: 0; }
.gm-def-label { color: var(--gm-faint); font-size: 9px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
.gm-def-value { color: #D9E3EC; font-family: var(--gm-mono); font-size: 0.76rem; margin-top: 3px; overflow-wrap: anywhere; }

.gm-env-row { display: flex; align-items: center; gap: 9px; padding: 7px 0; border-bottom: 1px solid var(--gm-border-soft); }
.gm-env-row:last-child { border-bottom: none; }
.gm-env-label { color: var(--gm-muted); font-size: 0.73rem; width: 94px; flex: 0 0 94px; }
.gm-env-track { height: 4px; flex: 1; border-radius: 4px; background: #172130; overflow: hidden; }
.gm-env-fill { height: 100%; border-radius: 4px; box-shadow: 0 0 8px currentColor; }
.gm-env-value { color: #DCE6EF; font-family: var(--gm-mono); font-size: 0.72rem; width: 58px; text-align: right; flex: 0 0 58px; }

.gm-event { display: flex; align-items: flex-start; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--gm-border-soft); }
.gm-event:last-child { border-bottom: none; }
.gm-event-time {
    color: var(--gm-accent);
    font-family: var(--gm-mono);
    font-size: 0.68rem;
    flex: 0 0 46px;
    padding: 2px 0 0;
    letter-spacing: 0.04em;
}
.gm-event-body { min-width: 0; }
.gm-event-name { color: #DCE6EF; font-size: 0.78rem; font-weight: 550; }
.gm-event-meta { color: var(--gm-faint); font-size: 0.68rem; margin-top: 2px; font-family: var(--gm-mono); }

/* Comparison matrix ------------------------------------------------------ */
.gm-table-wrap { overflow-x: auto; border: 1px solid var(--gm-border); border-radius: 10px; }
table.gm-table { width: 100%; border-collapse: collapse; font-size: 0.76rem; }
table.gm-table th {
    padding: 10px 11px;
    border-bottom: 1px solid var(--gm-border);
    background: #0B1119;
    color: var(--gm-muted);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.11em;
    text-transform: uppercase;
    text-align: right;
    white-space: nowrap;
}
table.gm-table th:first-child, table.gm-table td:first-child { text-align: left; }
table.gm-table td {
    padding: 9px 11px;
    border-bottom: 1px solid var(--gm-border-soft);
    color: #C9D4E0;
    font-family: var(--gm-mono);
    text-align: right;
    white-space: nowrap;
}
table.gm-table td:first-child { font-family: var(--gm-ui); font-weight: 550; color: #DCE6EF; }
table.gm-table tr:last-child td { border-bottom: none; }
table.gm-table tbody tr:hover td { background: #0F1822; }
.gm-cell { position: relative; }
.gm-cell-bar { position: absolute; inset: 4px 3px; border-radius: 4px; opacity: 0.9; }
.gm-cell-value { position: relative; z-index: 1; }
.gm-best { color: #8AF0C5; font-weight: 600; }
.gm-best-tag {
    display: inline-block;
    margin-left: 5px;
    padding: 1px 4px;
    border-radius: 3px;
    background: var(--gm-accent);
    color: #04120C;
    font-family: var(--gm-ui);
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.1em;
    vertical-align: 1px;
    box-shadow: 0 0 10px rgba(52, 211, 153, 0.45);
}

@media (max-width: 1180px) {
    .gm-table-wrap { border: none; overflow: visible; }
    table.gm-table, table.gm-table tbody, table.gm-table tr, table.gm-table td { display: block; width: 100%; }
    table.gm-table thead { display: none; }
    table.gm-table tr {
        border: 1px solid var(--gm-border);
        border-radius: 10px;
        margin-bottom: 8px;
        overflow: hidden;
        background: rgba(15, 21, 29, 0.55);
    }
    table.gm-table tr:last-child { margin-bottom: 0; }
    table.gm-table td { padding: 8px 11px; border-bottom: 1px solid var(--gm-border-soft); text-align: right; }
    table.gm-table td:first-child {
        background: #0B1119;
        color: var(--gm-text-strong);
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    table.gm-table td:not(:first-child) { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    table.gm-table td:not(:first-child)::before {
        content: attr(data-label);
        color: var(--gm-muted);
        font-family: var(--gm-ui);
        font-size: 0.74rem;
        font-weight: 500;
        text-align: left;
    }
    .gm-table-wrap .gm-cell-bar { display: none; }
    table.gm-table tr:last-child td { border-bottom: 1px solid var(--gm-border-soft); }
    table.gm-table tr td:last-child { border-bottom: none; }
}

/* Bars, legends, sidebar bits -------------------------------------------- */
.gm-bar-list { display: flex; flex-direction: column; gap: 11px; }
.gm-bar-row { display: grid; grid-template-columns: 86px 1fr 54px; align-items: center; gap: 9px; }
.gm-bar-label { color: var(--gm-muted); font-size: 0.73rem; }
.gm-bar-track { height: 7px; background: #172130; border-radius: 5px; overflow: hidden; }
.gm-bar-fill { height: 100%; border-radius: 5px; transition: width 300ms ease; }
.gm-bar-value { color: #DCE6EF; font-family: var(--gm-mono); font-size: 0.72rem; text-align: right; }

.gm-stack { display: flex; height: 8px; border-radius: 5px; overflow: hidden; background: #172130; margin: 7px 0 10px; }
.gm-stack span { display: block; height: 100%; }
.gm-legend { display: flex; flex-wrap: wrap; gap: 10px; }
.gm-legend-item { display: inline-flex; align-items: center; gap: 5px; color: var(--gm-muted); font-size: 0.7rem; }
.gm-legend-dot { width: 6px; height: 6px; border-radius: 2px; }

.gm-side-brand { display: flex; align-items: center; gap: 14px; padding: 6px 2px 14px; }
.gm-side-logo {
    width: 58px;
    height: 58px;
    flex: 0 0 58px;
    display: grid;
    place-items: center;
    border-radius: 16px;
    border: 1px solid rgba(52, 211, 153, 0.34);
    background:
        radial-gradient(60px 40px at 30% 15%, rgba(110, 231, 183, 0.16), transparent 70%),
        linear-gradient(145deg, #0F2D25 0%, #08141C 100%);
    box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.06), 0 10px 26px rgba(0, 0, 0, 0.45), 0 0 26px rgba(52, 211, 153, 0.14);
}
.gm-side-logo svg { width: 36px; height: 36px; }
.gm-side-text { min-width: 0; }
.gm-side-name {
    color: var(--gm-text-strong);
    font-size: 1.32rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.gm-side-name span { color: var(--gm-accent); }
.gm-side-sub {
    color: var(--gm-muted);
    font-size: 9.5px;
    font-family: var(--gm-mono);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-top: 5px;
    white-space: nowrap;
}
.gm-side-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin: 0 0 12px;
    padding: 8px 11px;
    border: 1px solid var(--gm-border);
    border-radius: 9px;
    background: rgba(15, 21, 29, 0.7);
    font-family: var(--gm-mono);
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.gm-side-live { display: inline-flex; align-items: center; gap: 8px; color: #7FE3B8; }
.gm-side-live .gm-dot { color: var(--gm-accent); box-shadow: 0 0 8px currentColor; animation: gm-pulse 2.4s ease-out infinite; }
.gm-side-ver {
    color: var(--gm-faint);
    padding: 2px 7px;
    border: 1px solid var(--gm-border);
    border-radius: 5px;
    letter-spacing: 0.04em;
}
.gm-side-section {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 18px 0 8px;
    color: var(--gm-faint);
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
}
.gm-side-section::after { content: ""; height: 1px; flex: 1; background: linear-gradient(90deg, var(--gm-border), transparent); }

.gm-state-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    border: 1px solid var(--gm-border-soft);
    border-radius: 8px;
    background: var(--gm-surface-2);
    margin-bottom: 6px;
}
.gm-state-row.is-selected { border-color: rgba(52, 211, 153, 0.38); background: rgba(52, 211, 153, 0.06); }
.gm-state-name { color: var(--gm-muted); font-size: 0.72rem; }
.gm-state-value { color: #DCE6EF; font-family: var(--gm-mono); font-size: 0.74rem; }
.gm-state-row.is-selected .gm-state-value { color: #8AF0C5; }

/* Sticky control bar (Live Simulation) ------------------------------------ */
[class*="st-key-gm-controlbar"] {
    position: sticky;
    top: 0.4rem;
    z-index: 60;
    padding: 11px 14px 8px;
    margin-bottom: 12px;
    border: 1px solid var(--gm-border-strong);
    border-radius: 12px;
    background: rgba(9, 14, 21, 0.88);
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
    box-shadow: 0 16px 38px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(52, 211, 153, 0.06);
}
[class*="st-key-gm-controlbar"] [data-testid="stProgress"] { margin-top: -2px; }
.gm-cb { display: flex; align-items: center; justify-content: space-between; gap: 14px 22px; flex-wrap: wrap; }
.gm-cb-state, .gm-cb-speed { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.gm-cb-metrics { display: flex; align-items: stretch; gap: 0; flex-wrap: wrap; flex: 1 1 auto; justify-content: center; }
.gm-cb-cell { display: flex; flex-direction: column; gap: 3px; padding: 0 16px; border-left: 1px solid var(--gm-border); }
.gm-cb-cell:first-child { border-left: none; }
.gm-cb-label { color: var(--gm-faint); font-size: 9px; font-weight: 600; letter-spacing: 0.13em; text-transform: uppercase; }
.gm-cb-value { color: var(--gm-text-strong); font-family: var(--gm-mono); font-size: 1.12rem; font-weight: 600; letter-spacing: -0.03em; white-space: nowrap; }
.gm-cb-value em { color: var(--gm-faint); font-style: normal; font-size: 0.62rem; margin-left: 6px; letter-spacing: 0.02em; text-transform: uppercase; }
.gm-cb-cell.is-bad .gm-cb-value { color: #FCA5A5; }

/* Grid alert banner ------------------------------------------------------- */
.gm-alert {
    --gm-alert: var(--gm-info);
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 15px;
    margin: 0 0 14px;
    border: 1px solid color-mix(in srgb, var(--gm-alert) 40%, transparent);
    border-left: 4px solid var(--gm-alert);
    border-radius: 10px;
    background: linear-gradient(90deg, color-mix(in srgb, var(--gm-alert) 13%, transparent), color-mix(in srgb, var(--gm-alert) 3%, transparent));
    color: #D5DEE9;
    font-size: 0.8rem;
    line-height: 1.55;
    animation: gm-rise 240ms ease-out both;
}
.gm-alert--critical { --gm-alert: var(--gm-danger); animation: gm-rise 240ms ease-out both, gm-alarm 2.2s ease-in-out infinite; }
.gm-alert--warning { --gm-alert: var(--gm-warning); }
.gm-alert--event { --gm-alert: var(--gm-secondary); }
.gm-alert-dot { flex: 0 0 9px; width: 9px; height: 9px; margin-top: 6px; border-radius: 50%; background: var(--gm-alert); box-shadow: 0 0 10px var(--gm-alert); }
.gm-alert-title { color: var(--gm-text-strong); font-size: 0.82rem; font-weight: 650; letter-spacing: 0.01em; }
.gm-alert-body { color: #B8C4D1; margin-top: 2px; }
.gm-alert-body strong { color: var(--gm-text-strong); font-family: var(--gm-mono); font-weight: 600; }
@keyframes gm-alarm {
    0%, 100% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0); }
    50% { box-shadow: 0 0 0 4px rgba(248, 113, 113, 0.12), 0 0 26px rgba(248, 113, 113, 0.18); }
}

/* KPI change chip --------------------------------------------------------- */
.gm-delta {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    margin-left: 9px;
    padding: 1px 6px;
    border-radius: 5px;
    font-family: var(--gm-mono);
    font-size: 0.64rem;
    font-weight: 600;
    letter-spacing: 0;
    vertical-align: middle;
    text-shadow: none;
}
.gm-delta--good { color: #6EE7B7; background: rgba(52, 211, 153, 0.12); }
.gm-delta--bad { color: #FCA5A5; background: rgba(248, 113, 113, 0.12); }
.gm-delta--flat { color: var(--gm-muted); background: rgba(148, 163, 184, 0.10); }

/* Result summary tiles ---------------------------------------------------- */
.gm-win-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 4px 0 6px; }
.gm-win {
    position: relative;
    padding: 12px 14px 11px 16px;
    border: 1px solid var(--gm-border);
    border-radius: 10px;
    background: rgba(11, 16, 23, 0.72);
    overflow: hidden;
}
.gm-win::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--gm-win); box-shadow: 0 0 12px var(--gm-win); }
.gm-win-label { color: var(--gm-faint); font-size: 9px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
.gm-win-name { color: var(--gm-win); font-size: 0.95rem; font-weight: 650; letter-spacing: -0.01em; margin-top: 6px; }
.gm-win-value { color: var(--gm-text-strong); font-family: var(--gm-mono); font-size: 0.82rem; margin-top: 3px; }
.gm-win-hint { color: var(--gm-faint); font-size: 0.66rem; margin-top: 4px; }

@media (max-width: 760px) {
    [class*="st-key-gm-controlbar"] { position: static; }
    .gm-cb-cell { padding: 0 10px; }
    .gm-win-grid { grid-template-columns: 1fr; }
}

@keyframes gm-pulse {
    0% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.45); }
    70% { box-shadow: 0 0 0 6px rgba(52, 211, 153, 0); }
    100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
}
@keyframes gm-rise {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1180px) {
    .gm-kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .gm-page-head { align-items: flex-start; flex-direction: column; gap: 12px; }
    .gm-page-badges { justify-content: flex-start; }
    [class*="st-key-gm-pair"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] {
        flex-direction: column;
        gap: 10px;
    }
    [class*="st-key-gm-pair"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
}
@media (max-width: 1024px) { .gm-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) {
    .block-container { padding: 1.1rem 0.9rem 2.4rem; }
    .gm-kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .gm-appbar { align-items: flex-start; flex-direction: column; gap: 10px; }
    .gm-app-meta { justify-content: flex-start; }
    .gm-def-grid { grid-template-columns: 1fr; }
    .gm-bar-row { grid-template-columns: 70px 1fr 48px; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""


def inject_theme() -> None:
    """Inject the global stylesheet into the current Streamlit page."""

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def style_figure(
    figure: go.Figure,
    *,
    height: int = 360,
    hovermode: str | None = "x unified",
    legend: bool = True,
    margin: dict[str, int] | None = None,
) -> go.Figure:
    """Apply the shared dark chart treatment to a Plotly figure."""

    figure.update_layout(
        height=height,
        margin=margin or {"l": 6, "r": 6, "t": 28, "b": 6},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT_UI, "size": 11, "color": MUTED},
        hoverlabel={
            "bgcolor": ELEVATED,
            "bordercolor": BORDER_STRONG,
            "font": {"family": FONT_UI, "size": 11, "color": TEXT},
        },
        hovermode=hovermode,
        colorway=CATEGORICAL,
        showlegend=legend,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "x": 0,
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"family": FONT_UI, "size": 10, "color": MUTED},
        },
        modebar={"bgcolor": "rgba(0,0,0,0)", "color": FAINT, "activecolor": ACCENT},
    )
    figure.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=BORDER,
        linewidth=1,
        tickfont={"family": FONT_MONO, "size": 9.5, "color": FAINT},
        title_font={"family": FONT_UI, "size": 10, "color": FAINT},
        zeroline=False,
        automargin=True,
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        griddash="dot",
        showline=False,
        tickfont={"family": FONT_MONO, "size": 9.5, "color": FAINT},
        title_font={"family": FONT_UI, "size": 10, "color": FAINT},
        zeroline=False,
        automargin=True,
    )
    return figure


def annotation(text: str, *, x: float = 0.0, y: float = 1.0) -> dict[str, Any]:
    """Return a consistent chart annotation dictionary."""

    return {
        "text": text,
        "x": x,
        "y": y,
        "xref": "paper",
        "yref": "paper",
        "showarrow": False,
        "font": {"family": FONT_UI, "size": 10, "color": FAINT},
        "align": "left",
    }