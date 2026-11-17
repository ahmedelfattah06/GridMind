"""Figures for the report and the dashboard (Team D2) - interface skeleton.

Owner: D2 (Experiments, Metrics and Reports).
Status: TODO. No plotting logic is implemented in this skeleton.

Plotly is used for interactive dashboard figures and Matplotlib for static
report figures. Both are approved technologies.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def plot_price_series(log: pd.DataFrame, output_path: str | Path | None = None) -> object:
    """Plot the clearing price over time.

    Args:
        log: Step log produced by ``SimulationLogger.get_log``.
        output_path: Optional destination for a static figure.

    Raises:
        NotImplementedError: Always, until Team D2 implements the plots.

    TODO(D2): implement the figure.
    """

    raise NotImplementedError("TODO(D2): plot_price_series is not implemented")


def plot_supply_demand(log: pd.DataFrame, output_path: str | Path | None = None) -> object:
    """Plot supply, demand and unserved energy over time.

    Args:
        log: Step log produced by ``SimulationLogger.get_log``.
        output_path: Optional destination for a static figure.

    Raises:
        NotImplementedError: Always, until Team D2 implements the plots.

    TODO(D2): implement the figure.
    """

    raise NotImplementedError("TODO(D2): plot_supply_demand is not implemented")


def plot_system_comparison(metrics: pd.DataFrame, output_path: str | Path | None = None) -> object:
    """Compare the four systems across scenarios.

    Args:
        metrics: One row per experiment.
        output_path: Optional destination for a static figure.

    Raises:
        NotImplementedError: Always, until Team D2 implements the plots.

    TODO(D2): implement the figure.
    """

    raise NotImplementedError("TODO(D2): plot_system_comparison is not implemented")
