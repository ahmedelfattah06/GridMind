"""Statistical comparison of systems (Team D2) - interface skeleton.

Owner: D2 (Experiments, Metrics and Reports).
Status: TODO. No statistical analysis is implemented in this skeleton.
"""

from __future__ import annotations

import pandas as pd


def summarise_runs(metrics: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-run metrics into mean, standard deviation and intervals.

    Args:
        metrics: One row per experiment, with a ``system`` and ``scenario``
            column.

    Raises:
        NotImplementedError: Always, until Team D2 implements the analysis.

    TODO(D2): implement the aggregation and confidence intervals (PD-09).
    """

    raise NotImplementedError("TODO(D2): summarise_runs is not implemented")


def paired_comparison(
    metrics: pd.DataFrame,
    baseline: str,
    treatment: str,
) -> pd.DataFrame:
    """Compare two systems over the same scenarios and seeds.

    Args:
        metrics: One row per experiment.
        baseline: Baseline system id.
        treatment: System id compared against the baseline.

    Raises:
        NotImplementedError: Always, until Team D2 implements the analysis.

    TODO(D2): implement the paired comparison.
    """

    raise NotImplementedError("TODO(D2): paired_comparison is not implemented")
