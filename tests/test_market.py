"""Tests for the double auction, settlement and negotiation (Team B3/C1)."""

from __future__ import annotations

from typing import Any

import pytest

from ai.central_lp import CentralLPPlanner, CentralMarketAdapter, DispatchPlan
from core.environment import Environment
from market.auction import DoubleAuction, MarketContext
from market.negotiation import RaiseFactorNegotiation, StubNegotiation
from market.orders import Order, Trade


def _context(
    *,
    t: int = 0,
    demand: dict[str, float] | None = None,
    generation: dict[str, float] | None = None,
    flexibility: dict[str, float] | None = None,
    storage_soc: dict[str, float] | None = None,
) -> MarketContext:
    demand = demand or {"hospital_1": 6.0, "residential_1": 10.0}
    generation = generation or {"solar_1": 20.0}
    return MarketContext(
        t=t,
        demand_mw=demand,
        generation_mw=generation,
        flexibility=flexibility or {"hospital_1": 0.0, "residential_1": 0.1},
        consumer_types={"hospital_1": "hospital", "residential_1": "residential"},
        producer_types={"solar_1": "solar"},
        storage_soc=storage_soc or {},
        voll={"hospital_1": 1000.0, "residential_1": 100.0},
        max_price={"hospital_1": 300.0, "residential_1": 120.0},
    )


def _buy(agent_id: str, qty: float, price: float, priority: int = 1, round: int = 1) -> Order:
    return Order(
        agent_id=agent_id, side="buy", qty_mw=qty, price=price, priority=priority, round=round
    )


def _sell(agent_id: str, qty: float, price: float, round: int = 1) -> Order:
    return Order(agent_id=agent_id, side="sell", qty_mw=qty, price=price, priority=4, round=round)


def test_double_auction_matches_cheapest_asks_with_uniform_price() -> None:
    auction = DoubleAuction()
    orders = [
        _buy("hospital_1", 10.0, 60.0, priority=1),
        _buy("residential_1", 5.0, 45.0, priority=2),
        _sell("solar_1", 8.0, 40.0),
        _sell("wind_1", 20.0, 50.0),
    ]
    result = auction.clear(orders, 1, _context())

    assert result.cleared_mw == pytest.approx(10.0)
    assert result.price == pytest.approx(55.0)
    assert len(result.trades) == 2
    assert result.trades[0].buyer_id == "hospital_1"
    assert result.trades[0].seller_id == "solar_1"
    assert result.trades[0].qty_mw == pytest.approx(8.0)
    assert result.trades[1].seller_id == "wind_1"
    assert result.trades[1].qty_mw == pytest.approx(2.0)
    assert all(trade.price == pytest.approx(55.0) for trade in result.trades)


def test_double_auction_keeps_last_price_when_nothing_matches() -> None:
    auction = DoubleAuction()
    auction.clear([_buy("hospital_1", 1.0, 10.0), _sell("solar_1", 1.0, 20.0)], 1, _context())
    assert auction.last_price == pytest.approx(0.0)

    first = auction.clear(
        [_buy("hospital_1", 1.0, 30.0), _sell("solar_1", 1.0, 20.0)], 1, _context()
    )
    assert first.price == pytest.approx(25.0)
    second = auction.clear(
        [_buy("hospital_1", 1.0, 10.0), _sell("solar_1", 1.0, 20.0)], 1, _context()
    )
    assert second.price == pytest.approx(25.0)
    assert second.trades == ()


def test_settlement_defers_flexible_shortfall_then_unserved() -> None:
    auction = DoubleAuction()
    context = _context()
    trades = [
        # hospital bought 4 of 6 (inflexible), residential 6 of 10.
        Trade(buyer_id="hospital_1", seller_id="solar_1", qty_mw=4.0, price=50.0),
        Trade(buyer_id="residential_1", seller_id="solar_1", qty_mw=6.0, price=50.0),
    ]
    settlement = auction.settle(context, trades, 50.0)

    assert settlement.unserved["hospital_1"] == pytest.approx(2.0)
    assert settlement.deferred["hospital_1"] == pytest.approx(0.0)
    assert settlement.deferred["residential_1"] == pytest.approx(1.0)
    assert settlement.unserved["residential_1"] == pytest.approx(3.0)
    assert sum(settlement.payments.values()) == pytest.approx(0.0)
    assert settlement.payments["hospital_1"] == pytest.approx(200.0)
    assert settlement.payments["residential_1"] == pytest.approx(300.0)
    assert settlement.payments["solar_1"] == pytest.approx(-500.0)


def test_negotiation_validates_round_and_ceiling(config: dict[str, Any]) -> None:
    protocol = RaiseFactorNegotiation(config)
    assert protocol.rounds == config["simulation"]["rounds"]
    assert protocol.raise_factor == pytest.approx(config["market"]["raise_factor"])
    assert protocol.producer_step == pytest.approx(config["market"]["producer_step"])

    wrong_round = _buy("hospital_1", 1.0, 100.0, round=1)
    with pytest.raises(ValueError, match="carries round"):
        protocol.refine(2, [wrong_round], None, _context())

    too_expensive = _buy("hospital_1", 1.0, 400.0, round=2)
    with pytest.raises(ValueError, match="exceeds the ceiling"):
        protocol.refine(2, [too_expensive], None, _context())

    refined = protocol.refine(
        2,
        [
            _sell("solar_1", 5.0, 10.0, round=2),
            _buy("residential_1", 3.0, 80.0, priority=2, round=2),
        ],
        None,
        _context(),
    )
    assert [order.side for order in refined] == ["buy", "sell"]


def test_stub_negotiation_filters_other_rounds() -> None:
    protocol = StubNegotiation(3)
    orders = [
        _buy("hospital_1", 1.0, 100.0, round=2),
        _buy("hospital_1", 1.0, 100.0, round=3),
    ]
    assert [order.round for order in protocol.refine(2, orders, None, _context())] == [2]


def test_central_planner_balances_every_hour(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=3)
    environment.update(0)
    forecast = environment.forecast(0, config["simulation"]["horizon"])
    context = {
        "demand_mw": dict(environment.state.demand_mw),
        "generation_mw": dict(environment.state.generation_mw),
        "storage_soc": {"battery_1": 0.5, "battery_2": 0.5},
    }
    planner = CentralLPPlanner(config)
    plans = planner.plan_horizon(0, forecast, context)

    assert len(plans) == config["simulation"]["horizon"]
    assert planner.last_objective >= 0.0
    for plan in plans:
        supply = sum(plan.generation_mw.values()) + sum(plan.discharge_mw.values())
        served = sum(plan.served_mw.values())
        charge = sum(plan.charge_mw.values())
        assert supply - charge == pytest.approx(served, abs=1e-6)
        assert all(value >= 0.0 for value in plan.generation_mw.values())
        assert all(value >= 0.0 for value in plan.unserved_mw.values())
        assert all(value >= 0.0 for value in plan.charge_mw.values())
        assert all(value >= 0.0 for value in plan.discharge_mw.values())


def test_central_adapter_replans_on_its_interval(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=4)
    environment.update(0)
    state = environment.state
    adapter = CentralMarketAdapter(config, environment=environment, interval=6)
    context = _context(
        t=0,
        demand=dict(state.demand_mw),
        generation=dict(state.generation_mw),
        flexibility={agent_id: 0.0 for agent_id in state.demand_mw},
    )

    adapter.clear([], 1, context)
    assert adapter.replan_count == 1
    adapter.clear(
        [],
        1,
        _context(t=1, demand=dict(state.demand_mw), generation=dict(state.generation_mw)),
    )
    assert adapter.replan_count == 1
    final_context = _context(
        t=6, demand=dict(state.demand_mw), generation=dict(state.generation_mw)
    )
    final = adapter.clear([], 1, final_context)
    assert adapter.replan_count == 2

    settlement = adapter.settle(final_context, final.trades, final.price)
    assert sum(settlement.payments.values()) == pytest.approx(0.0)
    assert all(value == pytest.approx(0.0) for value in settlement.deferred.values())


def _dispatch_plan(**overrides: Any) -> DispatchPlan:
    payload: dict[str, Any] = {"t": 0}
    payload.update(overrides)
    return DispatchPlan(**payload)


def _full_generation(**values: float) -> dict[str, float]:
    generation = {"solar_1": 0.0, "wind_1": 0.0, "thermal_1": 0.0, "peaker_1": 0.0}
    generation.update(values)
    return generation


def test_central_execution_serves_load_before_charging(config: dict[str, Any]) -> None:
    adapter = CentralMarketAdapter(config, interval=1)
    generation = _full_generation(solar_1=100.0)
    plan = _dispatch_plan(
        generation_mw=generation,
        charge_mw={"battery_1": 5.0, "battery_2": 5.0},
    )
    context = _context(
        demand={"hospital_1": 6.0, "residential_1": 10.0},
        generation=generation,
        storage_soc={"battery_1": 0.5, "battery_2": 0.5},
    )

    trades, _, unserved = adapter._execute(plan, context)

    served = sum(trade.qty_mw for trade in trades if trade.buyer_id in context.demand_mw)
    charged = sum(trade.qty_mw for trade in trades if trade.buyer_id in context.storage_soc)
    assert served == pytest.approx(16.0)
    assert charged == pytest.approx(10.0)
    assert unserved == pytest.approx({"hospital_1": 0.0, "residential_1": 0.0})


def test_central_execution_never_charges_while_load_is_unserved(
    config: dict[str, Any],
) -> None:
    adapter = CentralMarketAdapter(config, interval=1)
    generation = _full_generation(solar_1=10.0)
    plan = _dispatch_plan(
        generation_mw=generation,
        charge_mw={"battery_1": 5.0, "battery_2": 5.0},
    )
    context = _context(
        demand={"hospital_1": 6.0, "residential_1": 10.0},
        generation=generation,
        storage_soc={"battery_1": 0.5, "battery_2": 0.5},
    )

    trades, _, unserved = adapter._execute(plan, context)

    charged = sum(trade.qty_mw for trade in trades if trade.buyer_id in context.storage_soc)
    assert charged == pytest.approx(0.0)
    assert sum(unserved.values()) == pytest.approx(6.0)


def test_central_execution_clips_charge_to_physical_headroom(
    config: dict[str, Any],
) -> None:
    adapter = CentralMarketAdapter(config, interval=1)
    generation = _full_generation(solar_1=100.0)
    plan = _dispatch_plan(generation_mw=generation, charge_mw={"battery_1": 5.0})
    context = _context(
        demand={"hospital_1": 6.0},
        generation=generation,
        storage_soc={"battery_1": 0.99},
    )

    trades, _, _ = adapter._execute(plan, context)

    spec = next(
        entry for entry in config["storage"] if entry["type"] == "battery"
    )
    headroom = (1.0 - 0.99) * float(spec["capacity_mwh"])
    expected = min(float(spec["max_rate_mw"]), headroom / float(spec["efficiency"]))
    charged = sum(trade.qty_mw for trade in trades if trade.buyer_id == "battery_1")
    assert charged == pytest.approx(expected)


def test_central_execution_clips_discharge_to_available_energy(
    config: dict[str, Any],
) -> None:
    adapter = CentralMarketAdapter(config, interval=1)
    generation = _full_generation()
    plan = _dispatch_plan(generation_mw=generation, discharge_mw={"battery_2": 5.0})
    context = _context(
        demand={"hospital_1": 1.0},
        generation=generation,
        storage_soc={"battery_2": 0.001},
    )

    trades, _, unserved = adapter._execute(plan, context)

    spec = next(
        entry for entry in config["storage"] if entry["type"] == "battery"
    )
    available = 0.001 * float(spec["capacity_mwh"]) * float(spec["efficiency"])
    expected = min(float(spec["max_rate_mw"]), available)
    sold = sum(trade.qty_mw for trade in trades if trade.seller_id == "battery_2")
    assert sold == pytest.approx(expected)
    assert unserved["hospital_1"] == pytest.approx(1.0 - expected)


def test_central_price_excludes_curtailed_generation(config: dict[str, Any]) -> None:
    adapter = CentralMarketAdapter(config, interval=1)
    generation = _full_generation(
        solar_1=10.0, wind_1=6.0, thermal_1=100.0, peaker_1=100.0
    )
    plan = _dispatch_plan(generation_mw=generation)
    context = _context(
        demand={"hospital_1": 6.0, "residential_1": 10.0},
        generation=generation,
    )

    _, price, _ = adapter._execute(plan, context)

    # Solar (5) and wind (8) cover the 16 MW load; thermal (45) and peaker
    # (90) are dispatched in the plan but curtailed, so they must not set the
    # uniform clearing price.
    assert price == pytest.approx(8.0)


def test_central_plan_objectives_sum_to_the_horizon_total(
    config: dict[str, Any],
) -> None:
    environment = Environment(config, seed=3)
    environment.update(0)
    forecast = environment.forecast(0, config["simulation"]["horizon"])
    context = {
        "demand_mw": dict(environment.state.demand_mw),
        "generation_mw": dict(environment.state.generation_mw),
        "storage_soc": {"battery_1": 0.5, "battery_2": 0.5},
    }
    planner = CentralLPPlanner(config)

    plans = planner.plan_horizon(0, forecast, context)

    assert sum(plan.objective for plan in plans) == pytest.approx(
        planner.last_objective, rel=1e-9, abs=1e-9
    )
