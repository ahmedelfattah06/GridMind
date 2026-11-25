"""Statistical comparison of GridMind systems (Team D2).

The report requires, for every scenario and metric:

* mean and standard deviation over the 30 seeds,
* a 95 % bootstrap confidence interval (1000 resamples),
* paired Wilcoxon signed-rank tests between systems that share scenario and
  seed,
* Bonferroni correction over all performed comparisons,
* the effect size as a relative difference of the means.

Everything is computed from the per-run metrics table; no value is hard coded.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 20_240_517
DEFAULT_METRICS: tuple[str, ...] = (
    "social_cost",
    "ue_total",
    "ue_hospital",
    "ue_residential",
    "ue_factory",
    "hospital_outage_hours",
    "price_volatility",
    "par",
    "gini",
    "recovery_time",
    "messages",
    "renewable_share",
)


def summarise_runs(
    metrics: pd.DataFrame,
    metric_columns: Sequence[str] | None = None,
    *,
    bootstrap: int = BOOTSTRAP_RESAMPLES,
) -> pd.DataFrame:
    """Aggregate per-run metrics into mean, standard deviation and 95 % CI.

    Args:
        metrics: One row per experiment with ``system``, ``scenario``, ``seed``
            and the metric columns.
        metric_columns: Metrics to summarise. Defaults to :data:`DEFAULT_METRICS`
            filtered to the available columns.
        bootstrap: Number of bootstrap resamples.

    Returns:
        Tidy frame with one row per ``(scenario, system, metric)``.
    """

    _require_columns(metrics, ("system", "scenario"))
    columns = _metric_columns(metrics, metric_columns)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows: list[dict[str, object]] = []
    for (scenario, system), group in metrics.groupby(["scenario", "system"], sort=True):
        for metric in columns:
            values = np.asarray(pd.to_numeric(group[metric], errors="coerce").dropna(), dtype=float)
            if len(values) == 0:
                continue
            mean = float(np.mean(values))
            std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
            low, high = _bootstrap_interval(values, bootstrap, rng)
            rows.append(
                {
                    "scenario": scenario,
                    "system": system,
                    "metric": metric,
                    "count": int(len(values)),
                    "mean": mean,
                    "std": std,
                    "ci_low": low,
                    "ci_high": high,
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                }
            )
    return pd.DataFrame(rows)


def paired_comparison(
    metrics: pd.DataFrame,
    baseline: str,
    treatment: str,
    metric_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Compare two systems on paired scenario/seed observations.

    Returns one row per scenario and metric with the mean difference
    (treatment - baseline), the relative effect and the two-sided Wilcoxon
    signed-rank p-value.
    """

    _require_columns(metrics, ("system", "scenario", "seed"))
    columns = _metric_columns(metrics, metric_columns)
    baseline_frame = metrics[metrics["system"] == baseline]
    treatment_frame = metrics[metrics["system"] == treatment]
    if baseline_frame.empty or treatment_frame.empty:
        raise ValueError(f"unknown system in comparison: {baseline!r} vs {treatment!r}")
    merged = baseline_frame.merge(
        treatment_frame,
        on=["scenario", "seed"],
        suffixes=("_baseline", "_treatment"),
        how="inner",
    )
    rows: list[dict[str, object]] = []
    for scenario, group in merged.groupby("scenario", sort=True):
        for metric in columns:
            base = group.get(f"{metric}_baseline")
            treat = group.get(f"{metric}_treatment")
            if base is None or treat is None:
                continue
            base_values = pd.to_numeric(base, errors="coerce").to_numpy(dtype=float)
            treat_values = pd.to_numeric(treat, errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(base_values) & np.isfinite(treat_values)
            base_values = base_values[mask]
            treat_values = treat_values[mask]
            if len(base_values) == 0:
                continue
            differences = treat_values - base_values
            statistic, p_value = _wilcoxon(differences)
            mean_base = float(np.mean(base_values))
            mean_treat = float(np.mean(treat_values))
            mean_diff = float(np.mean(differences))
            relative = mean_diff / abs(mean_base) if abs(mean_base) > 1e-12 else 0.0
            rows.append(
                {
                    "scenario": scenario,
                    "baseline": baseline,
                    "treatment": treatment,
                    "metric": metric,
                    "n_pairs": int(len(differences)),
                    "mean_baseline": mean_base,
                    "mean_treatment": mean_treat,
                    "mean_difference": mean_diff,
                    "relative_effect": float(relative),
                    "statistic": float(statistic) if statistic is not None else 0.0,
                    "p_value": float(p_value) if p_value is not None else 1.0,
                }
            )
    return pd.DataFrame(rows)


def pairwise_comparisons(
    metrics: pd.DataFrame,
    metric_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Compare every unordered pair of systems, with Bonferroni correction.

    Returns:
        A frame with all pairwise rows and the adjusted p-value. The correction
        divides each p-value by the total number of performed tests.
    """

    _require_columns(metrics, ("system", "scenario"))
    systems = sorted(str(system) for system in metrics["system"].unique())
    frames = [
        paired_comparison(metrics, left, right, metric_columns)
        for left, right in combinations(systems, 2)
    ]
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    tests = len(combined)
    combined["p_adjusted"] = np.minimum(1.0, combined["p_value"] * max(1, tests))
    combined["bonferroni_tests"] = tests
    combined["significant"] = combined["p_adjusted"] < 0.05
    return combined


def _bootstrap_interval(
    values: np.ndarray,
    resamples: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    if len(values) == 0:
        return 0.0, 0.0
    if resamples < 1:
        raise ValueError("bootstrap resamples must be positive")
    means = np.empty(resamples, dtype=float)
    for index in range(resamples):
        sample = rng.choice(values, size=len(values), replace=True)
        means[index] = float(np.mean(sample))
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def _wilcoxon(differences: np.ndarray) -> tuple[float | None, float | None]:
    nonzero = differences[np.abs(differences) > 1e-12]
    if len(nonzero) < 2:
        return 0.0, 1.0
    try:
        result = wilcoxon(nonzero, zero_method="wilcox", alternative="two-sided")
    except ValueError:
        return 0.0, 1.0
    return float(result.statistic), float(result.pvalue)


def _metric_columns(
    frame: pd.DataFrame,
    requested: Sequence[str] | None,
) -> list[str]:
    if requested is None:
        return [metric for metric in DEFAULT_METRICS if metric in frame.columns]
    missing = [metric for metric in requested if metric not in frame.columns]
    if missing:
        raise KeyError(f"metrics not found in the table: {missing}")
    return list(requested)


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise KeyError(f"metrics table is missing columns: {missing}")


__all__ = [
    "BOOTSTRAP_RESAMPLES",
    "DEFAULT_METRICS",
    "paired_comparison",
    "pairwise_comparisons",
    "summarise_runs",
]
