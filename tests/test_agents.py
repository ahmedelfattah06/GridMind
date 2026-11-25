"""Tests for the consumer, producer and storage agents (Team B1/B2)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from agents.consumer import ConsumerAgent
from agents.producer import ProducerAgent
from agents.storage import RulePolicy, StorageAgent, StoragePolicy
from core.config import (
    derive_agent_forecast_rng,
    derive_agent_rng,
    resolve_agent_specs,
)


def _spec(config: dict[str, Any], agent_id: str) -> dict[str, Any]:
    return {str(spec["id"]): spec for spec in resolve_agent_specs(config)}[agent_id]


def _observation(
    config: dict[str, Any],
    agent_id: str,
    *,
    t: int = 0,
    hour: int = 12,
    demand: float = 0.0,
    generation: float = 0.0,
    own: dict[str, Any] | None = None,
    last_price: float = 0.0,
) -> dict[str, Any]:
    demand_map = {spec["id"]: 0.0 for spec in resolve_agent_specs(config) if spec["role"] == "consumer"}
    generation_map = {
        spec["id"]: 0.0 for spec in resolve_agent_specs(config) if spec["role"] == "producer"
    }
    if agent_id in demand_map:
        demand_map[agent_id] = demand
    if agent_id in generation_map:
        generation_map[agent_id] = generation
    return {
        "t": t,
        "hour": hour,
        "day": 0,
        "last_price": last_price,
        "environment": {
            "demand_mw": demand_map,
            "generation_mw": generation_map,
        },
        "own_agent": own or {},
    }


def test_hospital_bids_full_demand_at_its_ceiling(config: dict[str, Any]) -> None:
    spec = _spec(config, "hospital_1")
    agent = ConsumerAgent(spec, config, seed=1)
    agent.observe(_observation(config, "hospital_1", demand=6.0))

    snapshot = agent.snapshot()
    demand = snapshot["demand_mw"]
    assert snapshot["metered_demand_mw"] >= 6.0
    assert demand == pytest.approx(snapshot["metered_demand_mw"])

    orders = agent.decide(1)
    assert len(orders) == 1
    assert orders[0].side == "buy"
    assert orders[0].qty_mw == pytest.approx(demand)
    assert orders[0].price == pytest.approx(spec["max_price"])
    assert orders[0].priority == 1


def test_residential_splits_flexible_demand_and_escalates(config: dict[str, Any]) -> None:
    spec = _spec(config, "residential_1")
    agent = ConsumerAgent(spec, config, seed=2)
    agent.observe(_observation(config, "residential_1", demand=8.0))
    demand = agent.snapshot()["demand_mw"]

    first = agent.decide(1)
    second = agent.decide(2)
    assert sum(order.qty_mw for order in first) == pytest.approx(demand)
    fixed = next(order for order in first if order.priority == 2)
    flex = next(order for order in first if order.priority == 4)
    assert fixed.qty_mw == pytest.approx(demand * (1.0 - spec["flexibility"]))
    assert flex.qty_mw == pytest.approx(demand * spec["flexibility"])
    assert fixed.price == pytest.approx(config["max_prices"]["residential"])
    assert flex.price == pytest.approx(config["max_prices"]["flex"])

    raised = next(order for order in second if order.priority == 2)
    assert raised.price == pytest.approx(
        min(config["max_prices"]["residential"], config["max_prices"]["residential"] * 1.2)
    )


def test_factory_has_lowest_consumer_priority(config: dict[str, Any]) -> None:
    agent = ConsumerAgent(_spec(config, "factory_1"), config, seed=3)
    assert agent.priority == 3


def test_producer_offers_available_generation_with_markup(config: dict[str, Any]) -> None:
    spec = _spec(config, "solar_1")
    agent = ProducerAgent(spec, config)
    agent.observe(_observation(config, "solar_1", generation=40.0))

    order = agent.decide(1)[0]
    expected = spec["marginal_cost"] * (1.0 + config["market"]["initial_markup"])
    assert order.side == "sell"
    assert order.qty_mw == pytest.approx(40.0)
    assert order.price == pytest.approx(expected)

    discounted = agent.decide(2)[0]
    assert discounted.price == pytest.approx(expected * (1.0 - config["market"]["producer_step"]))


def test_producer_adapts_markup_to_sales(config: dict[str, Any]) -> None:
    agent = ProducerAgent(_spec(config, "thermal_1"), config)
    agent.observe(_observation(config, "thermal_1", generation=50.0))
    initial = agent.markup

    agent.update({"price": 50.0, "sold_mw": 50.0, "payment": -2500.0})
    assert agent.markup == pytest.approx(initial + 0.05)
    agent.update({"price": 50.0, "sold_mw": 0.0, "payment": 0.0})
    assert agent.markup == pytest.approx(initial)


class _FixedPolicy(StoragePolicy):
    def __init__(self, action: int) -> None:
        self.action = action

    def act(self, obs: dict[str, Any]) -> int:
        return self.action


def test_storage_discharge_is_limited_by_rate_and_soc(config: dict[str, Any]) -> None:
    spec = _spec(config, "battery_1")
    agent = StorageAgent(spec, config, policy=_FixedPolicy(2))
    agent.observe(_observation(config, "battery_1"))

    order = agent.decide(1)[0]
    assert order.side == "sell"
    assert order.qty_mw == pytest.approx(
        min(spec["max_rate_mw"], spec["initial_soc"] * spec["capacity_mwh"] * spec["efficiency"])
    )

    agent.update({"price": 50.0, "bought_mw": 0.0, "sold_mw": 5.0})
    expected_soc = spec["initial_soc"] - 5.0 / spec["efficiency"] / spec["capacity_mwh"]
    assert agent.state_of_charge == pytest.approx(expected_soc)


def test_storage_charge_respects_headroom(config: dict[str, Any]) -> None:
    spec = _spec(config, "battery_1")
    agent = StorageAgent(spec, config, policy=_FixedPolicy(1))
    agent.observe(_observation(config, "battery_1"))

    order = agent.decide(1)[0]
    assert order.side == "buy"
    headroom = (1.0 - spec["initial_soc"]) * spec["capacity_mwh"]
    assert order.qty_mw == pytest.approx(min(spec["max_rate_mw"], headroom / spec["efficiency"]))

    agent.update({"price": 20.0, "bought_mw": 5.0, "sold_mw": 0.0})
    expected_soc = spec["initial_soc"] + spec["efficiency"] * 5.0 / spec["capacity_mwh"]
    assert agent.state_of_charge == pytest.approx(expected_soc)


def test_storage_soc_stays_within_bounds(config: dict[str, Any]) -> None:
    spec = _spec(config, "battery_2")
    agent = StorageAgent(spec, config, policy=_FixedPolicy(0))
    agent.update({"price": 10.0, "bought_mw": 1000.0, "sold_mw": 0.0})
    assert agent.state_of_charge == pytest.approx(1.0)
    agent.update({"price": 10.0, "bought_mw": 0.0, "sold_mw": 1000.0})
    assert agent.state_of_charge == pytest.approx(0.0)


def test_rule_policy_charges_cheap_and_discharges_expensive(config: dict[str, Any]) -> None:
    policy = RulePolicy(config)
    assert policy.act({"last_price": 50.0, "own_agent": {"avg_price_24h": 100.0}}) == 1
    assert policy.act({"last_price": 150.0, "own_agent": {"avg_price_24h": 100.0}}) == 2
    assert policy.act({"last_price": 100.0, "own_agent": {"avg_price_24h": 100.0}}) == 0
    assert policy.act({"last_price": 100.0, "own_agent": {"avg_price_24h": 0.0}}) == 0


class _CountingPolicy(StoragePolicy):
    def __init__(self) -> None:
        self.calls = 0

    def act(self, obs: dict[str, Any]) -> int:
        self.calls += 1
        return 0


def test_storage_policy_is_queried_once_per_hour_across_rounds(
    config: dict[str, Any],
) -> None:
    policy = _CountingPolicy()
    agent = StorageAgent(_spec(config, "battery_1"), config, policy=policy)
    agent.observe(_observation(config, "battery_1"))

    for round_number in (1, 2, 3):
        agent.decide(round_number)
    assert policy.calls == 1

    agent.update({"price": 50.0, "bought_mw": 0.0, "sold_mw": 0.0})
    agent.observe(_observation(config, "battery_1", last_price=50.0))
    agent.decide(1)
    assert policy.calls == 2


def test_storage_price_history_records_the_settled_price(config: dict[str, Any]) -> None:
    agent = StorageAgent(_spec(config, "battery_1"), config, policy=_FixedPolicy(0))

    agent.update({"price": 42.0, "bought_mw": 0.0, "sold_mw": 0.0})

    assert agent.avg_price_24h == pytest.approx(42.0)


def test_consumer_forecast_noise_uses_an_independent_stream(
    config: dict[str, Any],
) -> None:
    spec = _spec(config, "residential_1")
    forecast_draws = derive_agent_forecast_rng(7, "residential_1").normal(
        0.0, 0.03, size=8
    )
    realised_draws = derive_agent_rng(7, "residential_1").normal(0.0, 0.03, size=8)
    assert not np.allclose(forecast_draws, realised_draws)

    agent = ConsumerAgent(spec, config, seed=7)
    agent.observe(_observation(config, "residential_1", demand=10.0))
    expected_noise = derive_agent_forecast_rng(7, "residential_1").normal(0.0, 0.03)
    assert agent.snapshot()["metered_demand_mw"] == pytest.approx(
        10.0 * (1.0 + expected_noise)
    )

    repeat = ConsumerAgent(spec, config, seed=7)
    repeat.observe(_observation(config, "residential_1", demand=10.0))
    assert repeat.snapshot()["metered_demand_mw"] == pytest.approx(
        agent.snapshot()["metered_demand_mw"]
    )
