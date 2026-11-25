"""Figures for the GridMind report and dashboard (Team D2).

Six static report figures are generated from real experiment artefacts:

1. social cost by system and scenario with error bars,
2. market price over seven days in the plant-outage scenario,
3. unserved energy around the outage (recovery),
4. the Q-learning curve,
5. the learned Q-table policy heatmap,
6. social-cost box plots over the 30 seeds.

Matplotlib is used for static files and Plotly for the interactive dashboard.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SYSTEM_COLORS = {
    "central_6h": "#1f77b4",
    "central_1h": "#2ca02c",
    "auction": "#d62728",
    "auction_q": "#9467bd",
}
SURFACE = "#fbfaf7"


def _prepare(output_path: str | Path | None) -> None:
    if output_path is None:
        return
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)


def _save(fig: plt.Figure, output_path: str | Path | None) -> plt.Figure:
    if output_path is not None:
        _prepare(output_path)
        fig.savefig(output_path, dpi=160, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
    return fig


def plot_price_series(log: pd.DataFrame, output_path: str | Path | None = None) -> plt.Figure:
    """Plot the clearing price of one run over the simulation horizon."""

    fig, ax = plt.subplots(figsize=(11, 3.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if log is not None and len(log):
        x = log["t"] if "t" in log else np.arange(len(log))
        ax.plot(x, log["price"], color="#c2410c", linewidth=1.4)
        ax.fill_between(x, 0, log["price"], color="#c2410c", alpha=0.08)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Price (currency/MWh)")
    ax.set_title("Market clearing price")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_supply_demand(log: pd.DataFrame, output_path: str | Path | None = None) -> plt.Figure:
    """Plot available supply, requested demand and unserved energy."""

    fig, ax = plt.subplots(figsize=(11, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if log is not None and len(log):
        x = log["t"] if "t" in log else np.arange(len(log))
        ax.plot(x, log["supply"], label="Available supply", color="#0f766e", linewidth=1.4)
        ax.plot(x, log["demand"], label="Requested demand", color="#b45309", linewidth=1.4)
        if "unserved_mw" in log:
            ax.fill_between(x, 0, log["unserved_mw"], label="Unserved", color="#b91c1c", alpha=0.35)
    ax.set_xlabel("Hour")
    ax.set_ylabel("Power (MW)")
    ax.set_title("Supply, demand and unserved energy")
    ax.legend(frameon=False, ncol=3)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_system_comparison(
    metrics: pd.DataFrame,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Bar chart of social cost per system and scenario with standard error."""

    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if metrics is None or metrics.empty:
        ax.text(0.5, 0.5, "No experiment metrics available", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)

    metric = "social_cost" if "social_cost" in metrics else "cost_total"
    grouped = metrics.groupby(["scenario", "system"])[metric]
    mean = grouped.mean().unstack("system")
    std = grouped.std(ddof=1).unstack("system")
    scenarios = list(mean.index)
    systems = list(mean.columns)
    positions = np.arange(len(scenarios))
    width = 0.8 / max(1, len(systems))
    for index, system in enumerate(systems):
        values = mean[system].to_numpy(dtype=float)
        errors = std[system].fillna(0.0).to_numpy(dtype=float)
        ax.bar(
            positions + index * width - 0.4 + width / 2,
            values,
            width=width,
            yerr=errors,
            capsize=2,
            label=system,
            color=SYSTEM_COLORS.get(system, None),
            alpha=0.9,
        )
    ax.set_xticks(positions)
    ax.set_xticklabels([scenario.replace("_", " ").title() for scenario in scenarios])
    ax.set_ylabel("Social cost (currency)")
    ax.set_title("Social cost by system and scenario (mean ± SD)")
    ax.legend(frameon=False, ncol=4)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_price_comparison(
    steps: pd.DataFrame,
    output_path: str | Path | None = None,
    *,
    scenario: str = "plant_outage",
    seed: int | None = None,
) -> plt.Figure:
    """Line chart of the price over seven days for every system."""

    fig, ax = plt.subplots(figsize=(11, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    subset = _scenario_steps(steps, scenario, seed)
    if subset.empty:
        ax.text(0.5, 0.5, "No step log available", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)
    for system, group in subset.groupby("system", sort=True):
        series = group.groupby("t")["price"].mean()
        ax.plot(
            series.index,
            series.to_numpy(dtype=float),
            label=str(system),
            linewidth=1.3,
            color=SYSTEM_COLORS.get(str(system), None),
        )
    ax.set_xlabel("Hour")
    ax.set_ylabel("Price (currency/MWh)")
    ax.set_title(f"Market price in the {scenario.replace('_', ' ')} scenario")
    ax.legend(frameon=False, ncol=4)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_recovery(
    steps: pd.DataFrame,
    output_path: str | Path | None = None,
    *,
    scenario: str = "plant_outage",
    event_start: int = 86,
    window: int = 24,
) -> plt.Figure:
    """Plot unserved energy around the disruption for every system."""

    fig, ax = plt.subplots(figsize=(11, 4.0), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    subset = _scenario_steps(steps, scenario, None)
    if subset.empty:
        ax.text(0.5, 0.5, "No step log available", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)
    lower = max(0, event_start - 6)
    upper = min(int(subset["t"].max()) + 1, event_start + window)
    for system, group in subset.groupby("system", sort=True):
        series = group.groupby("t")["unserved_mw"].mean()
        series = series.loc[(series.index >= lower) & (series.index <= upper)]
        ax.plot(
            series.index,
            series.to_numpy(dtype=float),
            label=str(system),
            linewidth=1.5,
            color=SYSTEM_COLORS.get(str(system), None),
        )
    ax.axvline(event_start, color="#111827", linestyle="--", linewidth=0.9, label="Event start")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Unserved energy (MW)")
    ax.set_title("Unserved energy around the disruption")
    ax.legend(frameon=False, ncol=5)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_learning_curve(
    curve: pd.DataFrame,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Plot the smoothed Q-learning reward curve."""

    fig, ax = plt.subplots(figsize=(9, 3.8), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if curve is None or curve.empty:
        ax.text(0.5, 0.5, "Run `python -m ai.train` to generate the curve", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)
    ax.plot(curve["episode"], curve["mean_reward"], color="#6d28d9", linewidth=1.6)
    if "std_reward" in curve:
        std = curve["std_reward"].fillna(0.0).to_numpy(dtype=float)
        mean = curve["mean_reward"].to_numpy(dtype=float)
        ax.fill_between(curve["episode"], mean - std, mean + std, color="#6d28d9", alpha=0.12)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Mean reward")
    ax.set_title("Q-learning curve (50-episode windows)")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def plot_qtable_heatmap(
    qtable: np.ndarray,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Visualise the greedy action of every one of the 60 states."""

    fig, ax = plt.subplots(figsize=(9.5, 3.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    table = np.asarray(qtable, dtype=float)
    if table.shape != (60, 3):
        ax.text(0.5, 0.5, f"Unexpected Q-table shape {table.shape}", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)
    greedy = np.argmax(table, axis=1).reshape(5, 12)
    from matplotlib.colors import ListedColormap

    cmap = ListedColormap(["#e5e7eb", "#34d399", "#f97316"])
    image = ax.imshow(greedy, aspect="auto", cmap=cmap, vmin=0, vmax=2)
    labels = np.array([["W", "C", "D"]])[0]
    for row in range(greedy.shape[0]):
        for column in range(greedy.shape[1]):
            ax.text(
                column,
                row,
                labels[greedy[row, column]],
                ha="center",
                va="center",
                fontsize=8,
                color="#111827",
            )
    ax.set_yticks(range(5))
    ax.set_yticklabels([f"SoC {index}" for index in range(5)])
    ax.set_xticks(range(12))
    ax.set_xticklabels(
        [f"{price}-{period}" for price in ("cheap", "normal", "pricey") for period in range(4)],
        rotation=45,
        ha="right",
        fontsize=7,
    )
    ax.set_title("Learned storage policy (W=wait, C=charge, D=discharge)")
    colorbar = fig.colorbar(image, ax=ax, ticks=[0, 1, 2])
    colorbar.ax.set_yticklabels(["Wait", "Charge", "Discharge"])
    fig.tight_layout()
    return _save(fig, output_path)


def plot_social_cost_box(
    metrics: pd.DataFrame,
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Box plot of the social-cost distribution over seeds for every system."""

    fig, ax = plt.subplots(figsize=(9.5, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    if metrics is None or metrics.empty:
        ax.text(0.5, 0.5, "No experiment metrics available", ha="center", va="center")
        ax.set_axis_off()
        return _save(fig, output_path)
    metric = "social_cost" if "social_cost" in metrics else "cost_total"
    systems = sorted(str(system) for system in metrics["system"].unique())
    data = [metrics.loc[metrics["system"] == system, metric].to_numpy(dtype=float) for system in systems]
    box = ax.boxplot(data, patch_artist=True, tick_labels=systems, widths=0.55)
    for patch, system in zip(box["boxes"], systems):
        patch.set_facecolor(SYSTEM_COLORS.get(system, "#9ca3af"))
        patch.set_alpha(0.75)
    ax.set_ylabel("Social cost (currency)")
    ax.set_title("Social-cost distribution over seeds")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    return _save(fig, output_path)


def generate_all_figures(
    metrics: pd.DataFrame,
    steps: pd.DataFrame,
    curve: pd.DataFrame,
    qtable: np.ndarray,
    output_dir: str | Path = "results/figures",
    *,
    event_start: int = 86,
) -> list[Path]:
    """Generate the six official report figures and return their paths."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [
        directory / "fig1_social_cost.png",
        directory / "fig2_price_plant_outage.png",
        directory / "fig3_recovery_unserved.png",
        directory / "fig4_learning_curve.png",
        directory / "fig5_qtable_heatmap.png",
        directory / "fig6_social_cost_box.png",
    ]
    plot_system_comparison(metrics, paths[0])
    plot_price_comparison(steps, paths[1], scenario="plant_outage")
    plot_recovery(steps, paths[2], scenario="plant_outage", event_start=event_start)
    plot_learning_curve(curve, paths[3])
    plot_qtable_heatmap(qtable, paths[4])
    plot_social_cost_box(metrics, paths[5])
    return paths


def _scenario_steps(
    steps: pd.DataFrame,
    scenario: str,
    seed: int | None,
) -> pd.DataFrame:
    if steps is None or steps.empty:
        return pd.DataFrame()
    frame = steps
    if "scenario" in frame.columns:
        frame = frame[frame["scenario"] == scenario]
    if seed is not None and "seed" in frame.columns:
        frame = frame[frame["seed"] == seed]
    return frame


__all__ = [
    "SYSTEM_COLORS",
    "generate_all_figures",
    "plot_learning_curve",
    "plot_price_comparison",
    "plot_price_series",
    "plot_qtable_heatmap",
    "plot_recovery",
    "plot_social_cost_box",
    "plot_supply_demand",
    "plot_system_comparison",
]
