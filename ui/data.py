"""Catalogue labels and artefact loaders for the dashboard.

All experiment values come from files written by ``experiments.runner`` or
``ai.train``. Loaders raise :class:`DataError` with an actionable message when a
file is missing or malformed; the views turn those errors into UI states.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import streamlit as st

from ai.qlearning import N_ACTIONS, N_STATES
from core.config import OFFICIAL_SCENARIOS, OFFICIAL_SYSTEMS, PROJECT_ROOT, load_config

RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
RAW_PATH = RESULTS_DIR / "raw.csv"
SUMMARY_PATH = RESULTS_DIR / "metrics_summary.csv"
PAIRWISE_PATH = RESULTS_DIR / "stats_pairwise.csv"
CURVE_PATH = RESULTS_DIR / "learning_curve.csv"
METADATA_PATH = RESULTS_DIR / "training_metadata.json"
QTABLE_PATH = PROJECT_ROOT / "qtable.npy"

SYSTEM_LABELS: dict[str, str] = {
    "auction": "Double auction",
    "auction_q": "Auction + Q-learning",
    "central_1h": "Central · 1h",
    "central_6h": "Central · 6h",
}
SYSTEM_SHORT: dict[str, str] = {
    "auction": "AUCTION",
    "auction_q": "AUCTION + Q",
    "central_1h": "CENTRAL 1H",
    "central_6h": "CENTRAL 6H",
}
SYSTEM_DESCRIPTIONS: dict[str, str] = {
    "auction": "Uniform-price double auction with three negotiation rounds.",
    "auction_q": "Double auction with the trained Q-learning battery policy.",
    "central_1h": "Central LP dispatch, re-optimised every hour.",
    "central_6h": "Central LP dispatch, re-optimised every six hours.",
}
SCENARIO_LABELS: dict[str, str] = {
    "normal": "Normal",
    "plant_outage": "Plant outage",
    "demand_spike": "Demand spike",
    "weather_shift": "Weather shift",
    "combined": "Combined",
}
SCENARIO_DESCRIPTIONS: dict[str, str] = {
    "normal": "Baseline operation without disruptions.",
    "plant_outage": "The thermal plant trips to 30% capacity for 12 hours.",
    "demand_spike": "Residential demand rises by 40% for six hours.",
    "weather_shift": "Dense cloud and weak wind reduce renewable output for a day.",
    "combined": "A thermal outage and a residential demand spike overlap.",
}
METRIC_LABELS: dict[str, str] = {
    "social_cost": "Social cost",
    "generation_cost": "Generation cost",
    "voll_penalty": "VOLL penalty",
    "ue_total": "Unserved energy",
    "ue_hospital": "Hospital UE",
    "ue_residential": "Residential UE",
    "ue_factory": "Factory UE",
    "hospital_outage_hours": "Hospital outage hours",
    "price_mean": "Mean price",
    "price_volatility": "Price volatility",
    "par": "Peak-to-average ratio",
    "gini": "Gini coefficient",
    "recovery_time": "Recovery time",
    "messages": "Messages",
    "renewable_share": "Renewable share",
    "self_sufficiency": "Self-sufficiency",
    "storage_cycles": "Storage cycles",
}
METRIC_UNITS: dict[str, str] = {
    "social_cost": "currency",
    "generation_cost": "currency",
    "voll_penalty": "currency",
    "ue_total": "MWh",
    "ue_hospital": "MWh",
    "ue_residential": "MWh",
    "ue_factory": "MWh",
    "hospital_outage_hours": "h",
    "price_mean": "currency/MWh",
    "price_volatility": "currency/MWh",
    "par": "ratio",
    "gini": "index",
    "recovery_time": "h",
    "messages": "msg",
    "renewable_share": "share",
    "self_sufficiency": "share",
    "storage_cycles": "cycles",
}
METRIC_HELP: dict[str, str] = {
    "social_cost": "Generation cost plus the VOLL penalty; lower is better.",
    "generation_cost": "Fuel and operating cost of dispatched generation.",
    "voll_penalty": "Value of lost load charged for unserved demand.",
    "ue_total": "Demand that remained unserved after deferral; lower is better.",
    "ue_hospital": "Unserved hospital demand; any positive value is a reliability failure.",
    "ue_residential": "Unserved residential demand.",
    "ue_factory": "Unserved factory demand. Central dispatch sheds this load because factory VOLL is below thermal cost.",
    "hospital_outage_hours": "Hours in which any hospital load was unserved.",
    "price_mean": "Mean clearing price over the run.",
    "price_volatility": "Standard deviation of the clearing price.",
    "par": "Peak demand divided by mean demand; lower is flatter.",
    "gini": "Inequality of per-agent outcomes; lower is more even.",
    "recovery_time": "Hours until price and UE return to the pre-event band. Censored at the window end.",
    "messages": "Negotiation messages exchanged during the run.",
    "renewable_share": "Share of served energy supplied by solar and wind.",
    "self_sufficiency": "Share of demand met by local generation and storage.",
    "storage_cycles": "Equivalent full charge/discharge cycles of the storage fleet.",
}


class DataError(RuntimeError):
    """Raised when a persisted dashboard artefact cannot be read."""


@st.cache_data(show_spinner=False)
def _read_csv(path: str, modified: float) -> pd.DataFrame:
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def _read_json(path: str, modified: float) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def _read_npy(path: str, modified: float) -> np.ndarray:
    return np.load(path, allow_pickle=False)


def _csv(path: Path, *, label: str, required: bool) -> pd.DataFrame | None:
    if not path.exists():
        if required:
            raise DataError(f"{label} was not found at {path}.")
        return None
    try:
        frame = _read_csv(str(path), path.stat().st_mtime)
    except Exception as exc:  # pragma: no cover - depends on a corrupt local file
        raise DataError(f"{label} could not be read: {exc}") from exc
    return frame


def load_raw_metrics(path: Path | None = None) -> pd.DataFrame:
    """Load the per-run metrics table, raising a readable error when missing."""

    frame = _csv(Path(path or RAW_PATH), label="results/raw.csv", required=True)
    assert frame is not None
    return frame


def load_summary(path: Path | None = None) -> pd.DataFrame | None:
    """Load the bootstrap summary when present."""

    return _csv(Path(path or SUMMARY_PATH), label="results/metrics_summary.csv", required=False)


def load_pairwise(path: Path | None = None) -> pd.DataFrame | None:
    """Load the paired statistical tests when present."""

    return _csv(Path(path or PAIRWISE_PATH), label="results/stats_pairwise.csv", required=False)


def load_learning_curve(path: Path | None = None) -> pd.DataFrame | None:
    """Load the Q-learning reward curve when present."""

    return _csv(Path(path or CURVE_PATH), label="results/learning_curve.csv", required=False)


def load_training_metadata(path: Path | None = None) -> dict[str, Any] | None:
    """Load the Q-learning training metadata when present."""

    target = Path(path or METADATA_PATH)
    if not target.exists():
        return None
    try:
        return _read_json(str(target), target.stat().st_mtime)
    except Exception as exc:  # pragma: no cover - depends on a corrupt local file
        raise DataError(f"results/training_metadata.json could not be read: {exc}") from exc


def load_qtable(path: Path | None = None) -> np.ndarray:
    """Load and validate the persisted Q-table."""

    target = Path(path or QTABLE_PATH)
    if not target.exists():
        raise DataError(
            "No trained Q-table was found. Run `python -m ai.train` to create qtable.npy."
        )
    try:
        table = _read_npy(str(target), target.stat().st_mtime)
    except Exception as exc:
        raise DataError(f"qtable.npy could not be read: {exc}") from exc
    if table.shape != (N_STATES, N_ACTIONS):
        raise DataError(
            f"qtable.npy has shape {table.shape}; expected {(N_STATES, N_ACTIONS)}."
        )
    if not np.isfinite(table).all():
        raise DataError("qtable.npy contains non-finite values.")
    return table


def require_experiment_artefacts() -> pd.DataFrame:
    """Return raw metrics or raise a data error with the runner command."""

    raw = load_raw_metrics()
    if raw.empty:
        raise DataError("results/raw.csv is empty. Re-run the experiment grid.")
    return raw


def system_label(system: str) -> str:
    """Human-readable system name."""

    return SYSTEM_LABELS.get(str(system), str(system))


def scenario_label(scenario: str) -> str:
    """Human-readable scenario name."""

    return SCENARIO_LABELS.get(str(scenario), str(scenario).replace("_", " ").title())


def scenario_description(scenario: str) -> str:
    """Scenario description from the official catalogue."""

    return SCENARIO_DESCRIPTIONS.get(str(scenario), "")


def metric_label(metric: str) -> str:
    """Human-readable metric name."""

    return METRIC_LABELS.get(str(metric), str(metric).replace("_", " ").title())


def metric_unit(metric: str) -> str:
    """Unit label for a metric."""

    return METRIC_UNITS.get(str(metric), "")


def metric_help(metric: str) -> str:
    """Tooltip text for a metric."""

    return METRIC_HELP.get(str(metric), "")


def agent_type_label(agent_type: str) -> str:
    """Human-readable agent type."""

    labels = {
        "hospital": "Hospital",
        "residential": "Residential",
        "factory": "Factory",
        "solar": "Solar",
        "wind": "Wind",
        "thermal": "Thermal",
        "peaker": "Peaker",
        "battery": "Battery",
    }
    return labels.get(str(agent_type), str(agent_type).replace("_", " ").title())


def event_label(name: str) -> str:
    """Human-readable event name."""

    words = str(name).replace("_", " ").split()
    labels = {
        "outage": "thermal outage",
        "spike": "demand spike",
        "shift": "weather shift",
    }
    cleaned = [labels.get(word.lower(), word) for word in words]
    return " ".join(cleaned).strip().title() or "Event"


def scenario_events(scenario: str) -> list[dict[str, Any]]:
    """Return the configured event dictionaries for a scenario."""

    config = load_config()
    entry = config.get("scenarios", {}).get(str(scenario), {})
    return list(entry.get("events", []) or [])


def censored_recovery_count(raw: pd.DataFrame) -> int:
    """Count central recovery cells that equal the remaining event window."""

    config = load_config()
    steps = int(config["simulation"]["steps"])
    count = 0
    for scenario in OFFICIAL_SCENARIOS:
        events = scenario_events(scenario)
        if not events:
            continue
        start = min(int(event["start"]) for event in events)
        remaining = steps - start
        subset = raw[raw["scenario"] == scenario]
        for system in OFFICIAL_SYSTEMS:
            if not str(system).startswith("central"):
                continue
            values = subset.loc[subset["system"] == system, "recovery_time"]
            if not values.empty and abs(float(values.mean()) - remaining) <= 0.51:
                count += 1
    return count


def available_systems(raw: pd.DataFrame) -> list[str]:
    """Official systems present in a metrics table, in official order."""

    present = set(raw.get("system", []))
    return [system for system in OFFICIAL_SYSTEMS if system in present]


def available_scenarios(raw: pd.DataFrame) -> list[str]:
    """Official scenarios present in a metrics table, in official order."""

    present = set(raw.get("scenario", []))
    return [scenario for scenario in OFFICIAL_SCENARIOS if scenario in present]


def experiment_counts(raw: pd.DataFrame) -> Mapping[str, int]:
    """Return run, seed and cell counts for the page header."""

    seeds = int(raw["seed"].nunique()) if "seed" in raw else 0
    cells = int(raw.groupby(["system", "scenario"]).ngroups) if not raw.empty else 0
    return {"runs": len(raw), "seeds": seeds, "cells": cells}
