"""Evaluation metrics for GridMind runs (Team D2).

The formulas follow section 9.2 of the project guide. All values are derived
from the step log produced by :class:`core.logger.SimulationLogger`; nothing is
fabricated. When the configuration is supplied, value-of-lost-load penalties,
agent types and renewable shares use the configured fleet.

The returned dictionary is suitable for one row of ``results/raw.csv``.
"""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

EPSILON = 1e-9

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


def compute_run_metrics(
    log: pd.DataFrame,
    config: Mapping[str, Any] | None = None,
    scenario: str | None = None,
) -> dict[str, float]:
    """Compute the official metrics of one simulation run.

    Args:
        log: Step log from ``SimulationLogger.get_log``.
        config: Optional validated configuration. It provides marginal costs,
            VOLL values, agent types, storage capacity and scenario timing.
        scenario: Optional scenario key, used for the recovery-time metric.

    Returns:
        Flat dictionary of metric names to numeric values. An empty log returns
        zeroes for every metric instead of raising.
    """

    metrics = _empty_metrics()
    if log is None or len(log) == 0:
        return metrics

    frame = log.copy()
    specs = _specs(config)
    producer_types = {item["id"]: str(item["type"]) for item in specs if item["role"] == "producer"}
    consumer_types = {item["id"]: str(item["type"]) for item in specs if item["role"] == "consumer"}
    consumer_ids = sorted(consumer_types)
    producer_ids = sorted(producer_types)
    voll = _voll(config, consumer_types)
    marginal_cost = {
        item["id"]: float(item.get("marginal_cost", 0.0))
        for item in specs
        if item["role"] == "producer"
    }

    unserved = _series(frame, "unserved_mw")
    deferred = _series(frame, "deferred_mw")
    demand = _series(frame, "demand")
    price = _series(frame, "price")
    messages = _series(frame, "messages")

    ue_by_consumer = {
        agent_id: _series(frame, f"ue_{agent_id}") for agent_id in consumer_ids
    }
    ue_by_type: dict[str, float] = {key: 0.0 for key in ("hospital", "residential", "factory")}
    for agent_id, values in ue_by_consumer.items():
        consumer_type = consumer_types.get(agent_id) or _type_from_id(agent_id)
        ue_by_type[consumer_type] = ue_by_type.get(consumer_type, 0.0) + float(values.sum())

    generation_cost = 0.0
    renewable_sold = 0.0
    total_sold = 0.0
    for agent_id in producer_ids:
        sold = _series(frame, f"sold_{agent_id}")
        quantity = float(sold.sum())
        generation_cost += float(marginal_cost.get(agent_id, 0.0)) * quantity
        total_sold += quantity
        if producer_types.get(agent_id) in ("solar", "wind"):
            renewable_sold += quantity

    voll_penalty = 0.0
    for agent_id, values in ue_by_consumer.items():
        consumer_type = consumer_types.get(agent_id) or _type_from_id(agent_id)
        voll_penalty += float(voll.get(agent_id, 0.0)) * float(values.sum())

    social_cost = float(generation_cost + voll_penalty)
    unserved_total = float(unserved.sum())
    deferred_total = float(deferred.sum())
    demand_total = float(demand.sum())
    served = np.clip(demand.to_numpy(dtype=float) - unserved.to_numpy(dtype=float) - deferred.to_numpy(dtype=float), 0.0, None)
    served_total = float(served.sum())
    price_array = price.to_numpy(dtype=float)

    metrics.update(
        {
            "cost_total": social_cost,
            "social_cost": social_cost,
            "cost_mean_per_mwh": social_cost / served_total if served_total > EPSILON else 0.0,
            "unserved_energy_mwh": unserved_total,
            "ue_total": unserved_total,
            "deferred_energy_mwh": deferred_total,
            "voll_penalty": float(voll_penalty),
            "generation_cost": float(generation_cost),
            "ue_hospital": float(ue_by_type.get("hospital", 0.0)),
            "ue_residential": float(ue_by_type.get("residential", 0.0)),
            "ue_factory": float(ue_by_type.get("factory", 0.0)),
            "hospital_outage_hours": float(_hospital_outage_hours(frame, consumer_types)),
            "price_mean": float(np.mean(price_array)) if len(price_array) else 0.0,
            "price_volatility": float(np.std(price_array, ddof=1))
            if len(price_array) > 1
            else 0.0,
            "par": float(np.max(served) / np.mean(served))
            if len(served) and np.mean(served) > EPSILON
            else 0.0,
            "gini": _gini(frame, consumer_ids),
            "recovery_time": float(_recovery_time(frame, config, scenario)),
            "messages": float(messages.sum()),
            "renewable_share": float(renewable_sold / total_sold)
            if total_sold > EPSILON
            else 0.0,
            "self_sufficiency": float(1.0 - unserved_total / demand_total)
            if demand_total > EPSILON
            else 0.0,
            "storage_cycles": _storage_cycles(frame, config),
        }
    )
    return metrics


def _empty_metrics() -> dict[str, float]:
    keys = (
        "cost_total",
        "social_cost",
        "cost_mean_per_mwh",
        "unserved_energy_mwh",
        "ue_total",
        "deferred_energy_mwh",
        "voll_penalty",
        "generation_cost",
        "ue_hospital",
        "ue_residential",
        "ue_factory",
        "hospital_outage_hours",
        "price_mean",
        "price_volatility",
        "par",
        "gini",
        "recovery_time",
        "messages",
        "renewable_share",
        "self_sufficiency",
        "storage_cycles",
    )
    return {key: 0.0 for key in keys}


def _series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=frame.index)


def _specs(config: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not config:
        return []
    from core.config import resolve_agent_specs

    return resolve_agent_specs(config)


def _voll(
    config: Mapping[str, Any] | None,
    consumer_types: Mapping[str, str],
) -> dict[str, float]:
    if not config:
        return {}
    table = config.get("voll", {})
    return {
        agent_id: float(table.get(consumer_type, 0.0))
        for agent_id, consumer_type in consumer_types.items()
    }


def _type_from_id(agent_id: str) -> str:
    return str(agent_id).rsplit("_", 1)[0]


def _hospital_outage_hours(frame: pd.DataFrame, consumer_types: Mapping[str, str]) -> int:
    hospital_ids = [agent_id for agent_id, kind in consumer_types.items() if kind == "hospital"]
    if not hospital_ids:
        hospital_ids = [
            column[len("ue_") :] for column in frame.columns if column.startswith("ue_hospital")
        ]
    if not hospital_ids:
        return 0
    total = np.zeros(len(frame), dtype=float)
    for agent_id in hospital_ids:
        total += _series(frame, f"ue_{agent_id}").to_numpy(dtype=float)
    return int(np.sum(total > 0.001))


def _gini(frame: pd.DataFrame, consumer_ids: list[str]) -> float:
    unit_prices: list[float] = []
    for agent_id in consumer_ids:
        bought = float(_series(frame, f"bought_{agent_id}").sum())
        paid = float(_series(frame, f"paid_{agent_id}").sum())
        if bought > EPSILON and paid > 0.0:
            unit_prices.append(paid / bought)
    n = len(unit_prices)
    if n < 2:
        return 0.0
    values = np.asarray(unit_prices, dtype=float)
    mean = float(np.mean(values))
    if mean <= EPSILON:
        return 0.0
    absolute_differences = np.abs(values[:, None] - values[None, :]).sum()
    return float(absolute_differences / (2.0 * n * n * mean))


def _recovery_time(
    frame: pd.DataFrame,
    config: Mapping[str, Any] | None,
    scenario: str | None,
) -> float:
    if not config or not scenario:
        return 0.0
    scenario_config = config.get("scenarios", {}).get(scenario, {})
    events = scenario_config.get("events", []) or []
    if not events:
        return 0.0
    start = int(min(int(event["start"]) for event in events))
    steps = len(frame)
    if start >= steps:
        return 0.0

    price = _series(frame, "price").to_numpy(dtype=float)
    unserved = _series(frame, "unserved_mw").to_numpy(dtype=float)
    baseline_slice = price[max(0, start - 24) : start]
    baseline = float(np.mean(baseline_slice)) if len(baseline_slice) else float(np.mean(price))
    tolerance = 0.10 * abs(baseline) if abs(baseline) > EPSILON else 0.0

    consecutive = 0
    for offset in range(start, steps):
        stable_price = abs(price[offset] - baseline) <= tolerance
        no_unserved = unserved[offset] <= 0.001
        if stable_price and no_unserved:
            consecutive += 1
            if consecutive >= 3:
                return float(offset - start - 2)
        else:
            consecutive = 0
    return float(steps - start)


def _storage_cycles(
    frame: pd.DataFrame,
    config: Mapping[str, Any] | None,
) -> float:
    if not config:
        return 0.0
    from core.config import resolve_agent_specs

    storage = [spec for spec in resolve_agent_specs(config) if spec["role"] == "storage"]
    cycles = 0.0
    for spec in storage:
        agent_id = str(spec["id"])
        throughput = float(
            _series(frame, f"bought_{agent_id}").sum()
            + _series(frame, f"sold_{agent_id}").sum()
        )
        capacity = float(spec["capacity_mwh"])
        if capacity > EPSILON:
            cycles += throughput / (2.0 * capacity)
    return float(cycles)


__all__ = ["PLANNED_METRICS", "compute_run_metrics"]
