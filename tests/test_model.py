"""Tests for GridModel orchestration.

Owner: A1.

The tests use the isolated doubles in ``tests/doubles.py`` for orchestration
mechanics and the real factory for integration acceptance checks. They do not
replace the official A2/A3/B/C logic: they prove that A1 drives the frozen
interfaces in the correct order and that the real components conserve energy.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from agents.storage import StoragePolicy
from core.config import load_config, resolve_agent_specs
from core.factory import build_model as build_real_model
from core.logger import LOG_COLUMNS, SOC_PREFIX, UE_PREFIX
from core.model import GridModel, StepResult
from market.orders import Order
from tests.doubles import FakeAgent, build_model


def _run(model: GridModel, steps: int) -> list[StepResult]:
    return [model.step() for _ in range(steps)]


def test_step_follows_the_frozen_execution_order(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    model = build_model(config, monkeypatch, calls=calls)
    result = model.step()

    assert result.t == 0
    assert model.clock.t == 1

    last_observe = max(i for i, call in enumerate(calls) if call.startswith("agent.observe:"))
    first_decide = min(i for i, call in enumerate(calls) if call.startswith("agent.decide:"))
    first_clear = calls.index("market.clear:1")
    first_decide_2 = min(
        i
        for i, call in enumerate(calls)
        if call.startswith("agent.decide:") and call.endswith(":2")
    )
    first_refine_2 = calls.index("negotiation.refine:2")
    first_clear_2 = calls.index("market.clear:2")
    first_decide_3 = min(
        i
        for i, call in enumerate(calls)
        if call.startswith("agent.decide:") and call.endswith(":3")
    )
    first_refine_3 = calls.index("negotiation.refine:3")
    first_clear_3 = calls.index("market.clear:3")
    settle = calls.index("market.settle")
    first_update = min(i for i, call in enumerate(calls) if call.startswith("agent.update:"))
    log = calls.index("logger.record_step")

    assert calls.index("environment.update:0") < calls.index("events.apply:0")
    assert calls.index("events.apply:0") < calls.index("environment.apply_modifiers:0")
    assert calls.index("environment.apply_modifiers:0") < last_observe
    assert last_observe < first_decide < first_clear
    assert first_clear < first_decide_2 < first_refine_2 < first_clear_2
    assert first_clear_2 < first_decide_3 < first_refine_3 < first_clear_3
    assert first_clear_3 < settle < first_update < log
    assert result.messages == len(result.orders)


def test_agent_observes_before_its_own_first_decision(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    model = build_model(config, monkeypatch, calls=calls)
    model.step()
    for agent in model.agents:
        observe = calls.index(f"agent.observe:{agent.agent_id}")
        first_decide = min(
            i for i, call in enumerate(calls) if call.startswith(f"agent.decide:{agent.agent_id}:")
        )
        assert observe < first_decide


def test_simulation_completes_all_168_steps_with_doubles(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    model = build_model(config, monkeypatch, calls=calls)
    results = _run(model, model.clock.steps)

    assert len(results) == 168
    assert [result.t for result in results] == list(range(168))
    assert model.clock.t == 168
    assert model.clock.is_finished
    assert model.clock.remaining == 0
    assert model.clock.progress == pytest.approx(1.0)
    assert len(model.logger) == 168

    log = model.logger.get_log()
    assert len(log) == 168
    assert set(LOG_COLUMNS).issubset(log.columns)
    assert log["t"].tolist() == list(range(168))
    assert (log["supply"] >= 0.0).all()
    assert (log["demand"] > 0.0).all()
    assert (log["unserved_mw"] >= 0.0).all()
    assert (log["deferred_mw"] >= 0.0).all()
    assert log["soc_mean"].between(0.0, 1.0).all()
    assert any(column.startswith(UE_PREFIX) for column in log.columns)
    assert any(column.startswith(SOC_PREFIX) for column in log.columns)


def test_energy_is_conserved_in_every_step(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    market = model._market  # test-only access to the injected double
    for _ in range(168):
        result = model.step()
        bought = sum(trade.qty_mw for trade in result.trades)
        sold = sum(trade.qty_mw for trade in result.trades)
        assert bought == pytest.approx(sold, abs=1e-6)

        settlement = market.last_settlement
        assert settlement is not None
        assert sum(settlement.payments.values()) == pytest.approx(0.0, abs=1e-9)
        for consumer_id, demand in market.last_context.demand_mw.items():
            served = sum(trade.qty_mw for trade in result.trades if trade.buyer_id == consumer_id)
            unserved = settlement.unserved[consumer_id]
            deferred = settlement.deferred[consumer_id]
            assert served + unserved + deferred == pytest.approx(demand, abs=1e-6)


def test_step_after_finish_raises(config: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    model = build_model(config, monkeypatch)
    _run(model, model.clock.steps)
    with pytest.raises(RuntimeError, match="simulation finished"):
        model.step()


def test_step_result_is_frozen(config: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    result = build_model(config, monkeypatch).step()
    with pytest.raises(FrozenInstanceError):
        result.price = 999.0  # type: ignore[misc]


def test_snapshot_exposes_the_full_public_state(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    before = model.snapshot()
    assert before["t"] == 0
    assert before["is_finished"] is False
    assert before["environment"] == {}
    assert before["orders"] == []
    assert before["trades"] == []
    assert len(before["agents"]) == 15
    json.dumps(before)

    result = model.step()
    after = model.snapshot()
    assert after["t"] == 1
    assert after["price"] > 0.0
    assert after["environment"]["demand_total_mw"] > 0.0
    assert after["scheduled_events"] == []
    assert after["log_rows"] == 1
    assert after["messages"] == result.messages
    assert after["unserved"] == result.unserved
    assert after["deferred"] == result.deferred
    assert len(after["orders"]) == len(result.orders)
    assert len(after["trades"]) == len(result.trades)
    json.dumps(after)


def test_forecast_delegates_to_the_environment(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    forecast = model.forecast(0, 6)
    assert forecast["origin_t"] == 0
    assert forecast["horizon"] == 6
    assert forecast["mode"] == "auction"
    assert len(forecast["t"]) == 6
    assert len(forecast["demand_total_mw"]) == 6
    assert set(forecast["demand_mw"]) == {
        spec["id"] for spec in resolve_agent_specs(config) if spec["role"] == "consumer"
    }
    assert forecast == model.forecast(0, 6)


def test_forecast_rejects_invalid_arguments(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    with pytest.raises(ValueError, match="t must be an integer"):
        model.forecast(-1, 6)
    with pytest.raises(ValueError, match="t must be an integer"):
        model.forecast(169, 6)
    with pytest.raises(ValueError, match="horizon must be a positive integer"):
        model.forecast(0, 0)


def test_unknown_mode_raises(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="mode must be one of"):
        GridModel(config, 0, mode="perfect_foresight")


def test_official_modes_need_injected_components(config: dict[str, Any]) -> None:
    for mode in ("central", "central_6h", "central_1h", "auction", "auction_q"):
        with pytest.raises(RuntimeError, match="requires real agents"):
            GridModel(config, 0, mode=mode)


def test_central_mode_uses_one_clearing_and_no_negotiation(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    model = build_model(config, monkeypatch, mode="central", calls=calls)
    assert model.is_central
    result = model.step()

    assert "market.clear:1" in calls
    assert "market.clear:2" not in calls
    assert not any(call.startswith("negotiation.refine:") for call in calls)
    assert result.messages == len(result.orders)
    assert result.orders
    assert model.snapshot()["mode"] == "central"


def test_central_adapter_calls_the_plan_interface(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch, mode="central_6h")
    model.step()
    planner = model._market.planner  # test-only access to the adapter double
    assert planner.calls
    assert planner.calls[0]["t"] == 0
    assert planner.calls[0]["forecast"]["origin_t"] == 0


def test_auction_negotiation_rounds_are_driven_by_the_model(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    model = build_model(config, monkeypatch, calls=calls)
    model.step()
    assert calls.count("negotiation.refine:2") == 1
    assert calls.count("negotiation.refine:3") == 1
    assert calls.count("market.clear:1") == 1
    assert calls.count("market.clear:2") == 1
    assert calls.count("market.clear:3") == 1


def test_scenario_alias_is_normalised(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch, scenario="Plant Outage")
    assert model.scenario == "plant_outage"


def test_unknown_scenario_raises(config: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="unknown scenario"):
        build_model(config, monkeypatch, scenario="meteor_strike")


def test_runtime_event_injection_applies_to_the_next_step(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = build_model(config, monkeypatch, seed=5)
    baseline.step()
    baseline.step()
    baseline_demand = baseline.snapshot()["environment"]["demand_mw"]

    model = build_model(config, monkeypatch, seed=5)
    model.step()
    model.inject_event(
        "extra_load",
        t_start=1,
        duration=1,
        demand_multiplier={"residential": 2.0},
    )
    result = model.step()
    injected_demand = model.snapshot()["environment"]["demand_mw"]

    types = {spec["id"]: spec["type"] for spec in resolve_agent_specs(config)}
    for agent_id, demand in injected_demand.items():
        expected = baseline_demand[agent_id] * (2.0 if types[agent_id] == "residential" else 1.0)
        assert demand == pytest.approx(expected)
    assert result.t == 1
    active_at_one = model.events.active_events(1)
    assert [event.name for event in active_at_one] == ["extra_load"]
    assert model.snapshot()["scheduled_events"][0]["name"] == "extra_load"


def test_invalid_injected_event_raises(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    with pytest.raises(ValueError, match="unsupported event parameters"):
        model.inject_event("bad_event", t_start=0, duration=1, wind_multiplier=2.0)
    with pytest.raises(ValueError, match="positive integer"):
        model.inject_event("bad_duration", t_start=0, duration=0)
    with pytest.raises(ValueError, match="lies before the current step"):
        model.step()
        model.inject_event("past_event", t_start=0, duration=1)
    with pytest.raises(ValueError, match="cloud_override"):
        model.inject_event("bad_cloud", t_start=1, duration=1, cloud_override=1.5)
    model.inject_event("duplicate", t_start=1, duration=1)
    with pytest.raises(ValueError, match="already scheduled"):
        model.inject_event("duplicate", t_start=2, duration=1)


def test_agent_observations_do_not_reveal_event_names(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    model = build_model(config, monkeypatch)
    model.inject_event("hidden_event", t_start=0, duration=2, demand_multiplier={"factory": 1.5})
    model.step()
    observation = model.agents[0].observation
    assert observation is not None
    assert "active_events" not in observation
    assert "active_events" not in observation["environment"]
    assert model.snapshot()["active_events"] == ["hidden_event"]


def test_model_rejects_orders_with_the_wrong_round(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    class WrongRoundAgent(FakeAgent):
        def decide(self, round: int) -> list[Order]:
            return [
                Order(
                    agent_id=self.agent_id,
                    side="sell",
                    qty_mw=1.0,
                    price=10.0,
                    round=round + 1,
                )
            ]

    specs = resolve_agent_specs(config)
    calls: list[str] = []
    bad_agent = WrongRoundAgent(specs[0], calls, seed=1)
    good_agents = [FakeAgent(spec, calls, seed=1) for spec in specs[1:]]
    model = build_model(config, monkeypatch, calls=calls, agents=[bad_agent, *good_agents])
    with pytest.raises(ValueError, match="submitted round"):
        model.step()


def test_logger_exports_csv(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    model = build_model(config, monkeypatch)
    _run(model, 5)
    destination = model.logger.export_csv(tmp_path / "logs" / "run.csv")
    assert destination.exists()
    frame = pd.read_csv(destination)
    assert len(frame) == 5
    assert set(LOG_COLUMNS).issubset(frame.columns)
    assert frame["t"].tolist() == list(range(5))


def test_logged_soc_reflects_the_post_update_agent_state(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The settlement payload carries pre-update SOC; the log is post-update."""

    class TransitioningStorage(FakeAgent):
        def update(self, result: dict[str, Any]) -> None:
            before = float(result["soc"])
            super().update(result)
            self._soc = before + 0.01

    specs = resolve_agent_specs(config)
    calls: list[str] = []
    agents = [
        (
            TransitioningStorage(spec, calls, seed=3)
            if spec["role"] == "storage"
            else FakeAgent(spec, calls, seed=3)
        )
        for spec in specs
    ]
    model = build_model(config, monkeypatch, calls=calls, agents=agents)
    result = model.step()

    storage_ids = [spec["id"] for spec in specs if spec["role"] == "storage"]
    assert storage_ids
    for agent in model.agents:
        if agent.role != "storage":
            continue
        settlement_soc = agent.updates[-1]["soc"]
        assert result.soc[agent.agent_id] == pytest.approx(settlement_soc + 0.01)
        assert model.logger.get_log().loc[0, f"{SOC_PREFIX}{agent.agent_id}"] == pytest.approx(
            settlement_soc + 0.01
        )


def test_energy_conservation_with_real_market() -> None:
    """Acceptance test for the B3 integration phase.

    Every MW of metered demand is either traded, deferred as flexible energy or
    left unserved, and settlement payments are zero-sum.
    """

    config = load_config()
    model = build_real_model(config, seed=7, mode="auction")
    consumers = {
        str(spec["id"]) for spec in resolve_agent_specs(config) if spec["role"] == "consumer"
    }

    for _ in range(24):
        result = model.step()
        bought: dict[str, float] = {}
        sold: dict[str, float] = {}
        for trade in result.trades:
            assert trade.qty_mw > 0.0
            bought[trade.buyer_id] = bought.get(trade.buyer_id, 0.0) + trade.qty_mw
            sold[trade.seller_id] = sold.get(trade.seller_id, 0.0) + trade.qty_mw

        context = model._build_market_context(model._environment.state)  # noqa: SLF001
        total_demand = 0.0
        served_demand = 0.0
        for agent_id, demand in context.demand_mw.items():
            total_demand += demand
            bought_mw = bought.get(agent_id, 0.0)
            shortfall = max(0.0, demand - bought_mw)
            served_demand += min(bought_mw, demand)
            assert result.unserved[agent_id] + result.deferred[agent_id] == pytest.approx(
                shortfall, abs=1e-6
            )
            assert result.unserved[agent_id] >= 0.0
            assert result.deferred[agent_id] >= 0.0

        assert sum(trade.qty_mw for trade in result.trades) == pytest.approx(
            sum(bought.values())
        )
        assert served_demand + sum(result.deferred.values()) + sum(
            result.unserved.values()
        ) == pytest.approx(total_demand, abs=1e-6)
        assert set(result.unserved) == consumers
        assert set(sold).issubset(
            {str(spec["id"]) for spec in resolve_agent_specs(config)}
        )
        assert sum(sold.values()) == pytest.approx(sum(bought.values()))

        settlement = model._market.last_settlement  # noqa: SLF001 - acceptance check
        assert sum(settlement.payments.values()) == pytest.approx(0.0, abs=1e-6)


def test_storage_policy_observation_includes_the_latest_clearing_price() -> None:
    """The 24 hour mean must be current when the policy is queried.

    ``_build_observations`` snapshots the agents before ``observe``. The price
    history therefore has to be advanced during ``update`` at the end of the
    previous step, otherwise every policy observation lags by one hour.
    """

    class RecordingPolicy(StoragePolicy):
        def __init__(self) -> None:
            self.observations: list[dict[str, Any]] = []

        def act(self, obs: dict[str, Any]) -> int:
            self.observations.append(dict(obs))
            return 0

    config = load_config()
    created: list[RecordingPolicy] = []

    def factory(spec: Any, cfg: Any, seed: int) -> RecordingPolicy:
        policy = RecordingPolicy()
        created.append(policy)
        return policy

    model = build_real_model(
        config, seed=0, mode="auction", policy_factory=factory
    )
    model.step()
    model.step()

    prices = model.logger.get_log()["price"].tolist()
    assert len(created) == 2
    for policy in created:
        assert policy.observations[0]["own_agent"]["avg_price_24h"] == pytest.approx(0.0)
        assert policy.observations[1]["own_agent"]["avg_price_24h"] == pytest.approx(
            prices[0]
        )
