"""Evaluation metrics (Team D2) - interface skeleton.

Owner: D2 (Experiments, Metrics and Reports).
Status: TODO. No metric formula is implemented in this skeleton.

The names below record the metrics the report is expected to contain. Their
definitions are an open decision (PD-09) and must not be invented here.
"""

from __future__ import annotations

import pandas as pd

PLANNED_METRICS: tuple[str, ...] = (
    "cost_total",
    "cost_mean_per_mwh",
    "unserved_energy_mwh",
    "deferred_energy_mwh",
    "voll_penalty",
    "price_mean",
    "price_volatility",
    "self_sufficiency",
    "storage_cycles",
)


def compute_run_metrics(log: pd.DataFrame) -> dict[str, float]:
    """Compute the metrics of one simulation run.

    Args:
        log: Step log produced by ``SimulationLogger.get_log``.

    Raises:
        NotImplementedError: Always, until Team D2 defines the formulas.

    TODO(D2): implement the metric formulas.
    """

    raise NotImplementedError("TODO(D2): compute_run_metrics is not implemented")
