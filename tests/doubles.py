"""Isolated test doubles for the A1 orchestration tests.

These classes are **test-only**. They do not implement the official weather,
demand, supply, agent, auction, negotiation or central-planning logic. They
exist so that Team A1 can exercise ``GridModel`` while Teams A2/A3/B/C are still
interface skeletons.

The doubles implement exactly the frozen interfaces from ``docs/contracts.md``:

* :class:`FakeEnvironment` -- ``update``, ``apply_modifiers``, ``forecast``.
* :class:`FakeAgent` -- ``observe``, ``decide``, ``update``, ``snapshot``.
* :class:`FakeMarket` -- ``MarketInterface.clear`` and ``settle``.
* :class:`FakeNegotiation` -- ``NegotiationProtocol.refine``.
* :class:`FakeEventManager` -- the subset of ``EventManager`` used by the model.

None of these classes may be imported by production modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sin
from typing import Any, Mapping, Sequence

from agents.base import BaseAgent
from core.config import CENTRAL_MODES, derive_agent_rng, resolve_agent_specs
from core.environment import EnvironmentState
from core.events import EnvironmentModifiers
from core.logger import SimulationLogger
from market.auction import ClearingResult, MarketContext, MarketInterface, Settlement
from market.negotiation import NegotiationProtocol
from market.orders import Order, Trade

# ---------------------------------------------------------------------------
# Environment double
# ---------------------------------------------------------------------------


class FakeEnvironment:
    """Deterministic environment double used by the A1 tests."""

    def __init__(self, config: Mapping[str, Any], seed: int, calls: list[str]) -> None:
        self._config = config
        self._calls = calls
        self._specs = resolve_agent_specs(config)
        self._consumers = [spec for spec in self._specs if spec["role"] == "consumer"]
        self._producers = [spec for spec in self._specs if spec["role"] == "producer"]
        self._consumer_types = {str(spec["id"]): str(spec["type"]) for spec in self._consumers}
        self._rngs = {
            str(spec["id"]): derive_agent_rng(seed, str(spec["id"])) for spec in self._consumers
        }
        self._demand_params = config["environment"]["demand"]
        self._state: EnvironmentState | None = None
        self._base_demand_mw: dict[str, float] = {}

    @property
    def state(self) -> EnvironmentState:
        if self._state is None:
            raise RuntimeError("environment has not been updated yet; call update(t) first")
        return self._state

    def update(self, t: int) -> EnvironmentState:
        self._calls.append(f"environment.update:{t}")
        if self._state is not None and t < self._state.t:
            raise ValueError(
                f"cannot rewind the environment (current t={self._state.t}, requested t={t})"
            )
        if self._state is not None and t == self._state.t:
            return self._state
        start = -1 if self._state is None else self._state.t
        for step in range(start + 1, t + 1):
            self._advance(step)
        return self.state

    def apply_modifiers(
        self,
        modifiers: EnvironmentModifiers,
        active_events: tuple[str, ...] = (),
    ) -> EnvironmentState:
        self._calls.append(f"environment.apply_modifiers:{self.state.t}")
        state = self.state
        demand: dict[str, float] = {}
        for agent_id, base in self._base_demand_mw.items():
            consumer_type = self._consumer_types[agent_id]
            factor = modifiers.demand_multiplier.get(
                agent_id, modifiers.demand_multiplier.get(consumer_type, 1.0)
            )
            demand[agent_id] = max(0.0, base * float(factor))
        generation = self._generation(
            state.solar_profile, state.wind_index, modifiers.cloud_override, modifiers
        )
        self._state = EnvironmentState(
            t=state.t,
            hour=state.hour,
            day=state.day,
            temperature_c=state.temperature_c,
            cloud_cover=state.cloud_cover,
            effective_cloud_cover=(
                state.cloud_cover
                if modifiers.cloud_override is None
                else float(modifiers.cloud_override)
            ),
            wind_index=state.wind_index,
            solar_profile=state.solar_profile,
            demand_mw=demand,
            generation_mw=generation,
            active_events=tuple(active_events),
        )
        return self._state

    def forecast(self, t: int, horizon: int) -> dict[str, Any]:
        self._calls.append(f"environment.forecast:{t}:{horizon}")
        steps = list(range(t, t + horizon))
        hours = [step % 24 for step in steps]
        temperatures = [self._temperature(hour) for hour in hours]
        clouds = [0.5 for _ in steps]
        winds = [0.5 for _ in steps]
        solar = [self._solar_profile(hour) for hour in hours]
        demand = {
            str(spec["id"]): [
                self._demand_value(spec, hour, temperature)
                for hour, temperature in zip(hours, temperatures)
            ]
            for spec in self._consumers
        }
        generation = {
            str(spec["id"]): [
                self._producer_value(spec, solar[index], clouds[index], winds[index])
                for index in range(horizon)
            ]
            for spec in self._producers
        }
        return {
            "origin_t": t,
            "horizon": horizon,
            "t": steps,
            "hour": hours,
            "day": [step // 24 for step in steps],
            "temperature_c": temperatures,
            "cloud_cover": clouds,
            "wind_index": winds,
            "demand_mw": demand,
            "generation_mw": generation,
            "demand_total_mw": [float(sum(values)) for values in zip(*demand.values())],
            "generation_total_mw": [float(sum(values)) for values in zip(*generation.values())],
        }

    def _advance(self, t: int) -> None:
        hour = t % 24
        day = t // 24
        temperature = self._temperature(hour) + 0.5 * day
        cloud = 0.5
        wind = 0.5
        solar = self._solar_profile(hour)
        demand = {}
        for spec in self._consumers:
            agent_id = str(spec["id"])
            noise = float(self._rngs[agent_id].normal(0.0, 0.02))
            demand[agent_id] = max(0.0, self._demand_value(spec, hour, temperature) * (1.0 + noise))
        self._base_demand_mw = dict(demand)
        generation = self._generation(solar, wind, None, EnvironmentModifiers())
        self._state = EnvironmentState(
            t=t,
            hour=hour,
            day=day,
            temperature_c=temperature,
            cloud_cover=cloud,
            effective_cloud_cover=cloud,
            wind_index=wind,
            solar_profile=solar,
            demand_mw=demand,
            generation_mw=generation,
            active_events=(),
        )

    def _temperature(self, hour: int) -> float:
        return 27.0 + 8.0 * sin(2.0 * pi * (hour - 9) / 24.0)

    @staticmethod
    def _solar_profile(hour: int) -> float:
        if 6 <= hour < 18:
            return max(0.0, sin(pi * (hour - 6) / 12.0))
        return 0.0

    def _demand_value(self, spec: Mapping[str, Any], hour: int, temperature: float) -> float:
        base = float(spec["base_mw"])
        consumer_type = str(spec["type"])
        if consumer_type == "residential":
            profile = self._residential_profile(hour)
        elif consumer_type == "factory":
            profile = self._factory_profile(hour)
        else:
            profile = 1.0
        temperature_factor = 1.0 + 0.02 * max(0.0, temperature - 25.0)
        return base * profile * temperature_factor

    def _residential_profile(self, hour: int) -> float:
        profile = self._demand_params["profile"]
        for name, window in self._demand_params["windows"].items():
            start = int(window["start"])
            end = int(window["end"])
            inside = start <= hour < end if start < end else hour >= start or hour < end
            if inside:
                return float(profile[name])
        return float(profile["night"])

    def _factory_profile(self, hour: int) -> float:
        window = self._demand_params["factory_work_window"]
        if int(window["start"]) <= hour < int(window["end"]):
            return 1.0
        return float(self._demand_params["factory_off_factor"])

    def _generation(
        self,
        solar_profile: float,
        wind_index: float,
        cloud_override: float | None,
        modifiers: EnvironmentModifiers,
    ) -> dict[str, float]:
        cloud = 0.5 if cloud_override is None else float(cloud_override)
        generation: dict[str, float] = {}
        for spec in self._producers:
            agent_id = str(spec["id"])
            producer_type = str(spec["type"])
            factor = modifiers.capacity_factor.get(
                agent_id, modifiers.capacity_factor.get(producer_type, 1.0)
            )
            generation[agent_id] = self._producer_value(
                spec, solar_profile, cloud, wind_index
            ) * float(factor)
        return generation

    @staticmethod
    def _producer_value(
        spec: Mapping[str, Any], solar_profile: float, cloud: float, wind_index: float
    ) -> float:
        capacity = float(spec["capacity_mw"])
        producer_type = str(spec["type"])
        if producer_type == "solar":
            return capacity * solar_profile * cloud
        if producer_type == "wind":
            return capacity * wind_index
        factor = spec.get("capacity_factor")
        return capacity * (1.0 if factor is None else float(factor))


# ---------------------------------------------------------------------------
# Agent double
# ---------------------------------------------------------------------------


class FakeAgent(BaseAgent):
    """Minimal observable agent with deterministic, test-only behaviour."""

    def __init__(self, spec: Mapping[str, Any], calls: list[str], seed: int) -> None:
        super().__init__(
            agent_id=str(spec["id"]),
            role=str(spec["role"]),
            agent_type=str(spec["type"]),
        )
        self._spec = dict(spec)
        self._calls = calls
        self._rng = derive_agent_rng(seed, self.agent_id)
        self._markup = 0.2
        self._soc = float(spec.get("initial_soc", 0.0))
        self._available_mw = 0.0
        self._demand_mw = 0.0
        self.observation: dict[str, Any] | None = None
        self.updates: list[dict[str, Any]] = []

    @property
    def state_of_charge(self) -> float:
        return self._soc

    def observe(self, obs: dict[str, Any]) -> None:
        self._calls.append(f"agent.observe:{self.agent_id}")
        self.observation = obs
        environment = obs["environment"]
        if self.role == "producer":
            self._available_mw = float(environment["generation_mw"].get(self.agent_id, 0.0))
        elif self.role == "consumer":
            demand = float(environment["demand_mw"].get(self.agent_id, 0.0))
            forecast_error = float(self._rng.normal(0.0, 0.01))
            self._demand_mw = min(demand, max(0.0, demand * (1.0 + forecast_error)))

    def decide(self, round: int) -> list[Order]:
        self._calls.append(f"agent.decide:{self.agent_id}:{round}")
        if self.role == "producer" and self._available_mw > 0.0:
            price = float(self._spec["marginal_cost"]) * (1.0 + self._markup)
            if round > 1:
                price = max(float(self._spec["marginal_cost"]), price * (1.0 - 0.05 * (round - 1)))
            return [
                Order(
                    agent_id=self.agent_id,
                    side="sell",
                    qty_mw=self._available_mw,
                    price=price,
                    priority=3,
                    round=round,
                )
            ]
        if self.role == "consumer" and self._demand_mw > 0.0:
            price = float(self._spec["max_price"])
            if round > 1:
                price = min(price, price * 1.2)
            return [
                Order(
                    agent_id=self.agent_id,
                    side="buy",
                    qty_mw=self._demand_mw,
                    price=price,
                    priority={"hospital": 1, "residential": 2, "factory": 3}.get(
                        self.agent_type, 3
                    ),
                    round=round,
                )
            ]
        return []

    def update(self, result: dict[str, Any]) -> None:
        self._calls.append(f"agent.update:{self.agent_id}")
        self.updates.append(dict(result))
        if self.role == "producer" and self._available_mw > 0.0:
            sold = float(result.get("sold_mw", 0.0))
            if sold >= 0.95 * self._available_mw:
                self._markup = min(1.0, self._markup + 0.05)
            else:
                self._markup = max(0.0, self._markup - 0.05)
        elif self.role == "storage":
            self._soc = float(result.get("soc", self._soc))

    def snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "agent_id": self.agent_id,
            "role": self.role,
            "type": self.agent_type,
        }
        if self.role == "storage":
            payload["soc"] = self._soc
        return payload


# ---------------------------------------------------------------------------
# Market and negotiation doubles
# ---------------------------------------------------------------------------


class FakeMarket(MarketInterface):
    """Balanced matching double that satisfies the MarketInterface contract."""

    def __init__(self, calls: list[str]) -> None:
        self._calls = calls
        self._last_price = 0.0
        self.last_context: MarketContext | None = None
        self.last_settlement: Settlement | None = None
        self.rounds_cleared: list[int] = []

    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        self._calls.append(f"market.clear:{round}")
        self.last_context = context
        self.rounds_cleared.append(round)
        bids = sorted(
            (order for order in orders if order.side == "buy"),
            key=lambda order: (-order.price, order.priority, order.agent_id),
        )
        asks = sorted(
            (order for order in orders if order.side == "sell"),
            key=lambda order: (order.price, order.priority, order.agent_id),
        )
        matches: list[tuple[str, str, float, float, float]] = []
        bid_index = ask_index = 0
        bid_remaining = bids[0].qty_mw if bids else 0.0
        ask_remaining = asks[0].qty_mw if asks else 0.0
        while (
            bid_index < len(bids)
            and ask_index < len(asks)
            and bids[bid_index].price >= asks[ask_index].price
        ):
            quantity = min(bid_remaining, ask_remaining)
            if quantity > 0.0:
                matches.append(
                    (
                        bids[bid_index].agent_id,
                        asks[ask_index].agent_id,
                        quantity,
                        bids[bid_index].price,
                        asks[ask_index].price,
                    )
                )
            bid_remaining -= quantity
            ask_remaining -= quantity
            if bid_remaining <= 1e-12:
                bid_index += 1
                bid_remaining = bids[bid_index].qty_mw if bid_index < len(bids) else 0.0
            if ask_remaining <= 1e-12:
                ask_index += 1
                ask_remaining = asks[ask_index].qty_mw if ask_index < len(asks) else 0.0
        price = (matches[-1][3] + matches[-1][4]) / 2.0 if matches else self._last_price
        self._last_price = price
        trades = tuple(
            Trade(buyer_id=buyer, seller_id=seller, qty_mw=quantity, price=price)
            for buyer, seller, quantity, _, _ in matches
        )
        return ClearingResult(
            round=round,
            price=price,
            trades=trades,
            cleared_mw=float(sum(trade.qty_mw for trade in trades)),
        )

    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        self._calls.append("market.settle")
        bought: dict[str, float] = {}
        sold: dict[str, float] = {}
        for trade in trades:
            bought[trade.buyer_id] = bought.get(trade.buyer_id, 0.0) + float(trade.qty_mw)
            sold[trade.seller_id] = sold.get(trade.seller_id, 0.0) + float(trade.qty_mw)
        unserved = {
            agent_id: max(0.0, float(demand) - bought.get(agent_id, 0.0))
            for agent_id, demand in context.demand_mw.items()
        }
        deferred = {agent_id: 0.0 for agent_id in context.demand_mw}
        payments: dict[str, float] = {}
        for agent_id, quantity in bought.items():
            payments[agent_id] = payments.get(agent_id, 0.0) + float(price) * quantity
        for agent_id, quantity in sold.items():
            payments[agent_id] = payments.get(agent_id, 0.0) - float(price) * quantity
        settlement = Settlement(
            price=float(price),
            trades=tuple(trades),
            unserved=unserved,
            deferred=deferred,
            payments=payments,
        )
        self.last_settlement = settlement
        return settlement


class FakeNegotiation(NegotiationProtocol):
    """Identity negotiation double; it does not implement B3's rules."""

    def __init__(self, calls: list[str], rounds: int) -> None:
        self._calls = calls
        self._rounds = rounds

    @property
    def rounds(self) -> int:
        return self._rounds

    def refine(
        self,
        round: int,
        orders: Sequence[Order],
        previous: ClearingResult | None,
        context: MarketContext,
    ) -> list[Order]:
        self._calls.append(f"negotiation.refine:{round}")
        return list(orders)


class FakePlanner:
    """Records calls to the C1 ``central_lp.plan`` interface."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def plan(
        self, t: int, forecast: Mapping[str, Any], context: Mapping[str, Any]
    ) -> dict[str, Any]:
        self.calls.append({"t": t, "forecast": dict(forecast), "context": dict(context)})
        return {"t": t}


class CentralAdapterDouble(FakeMarket):
    """C1 adapter double: calls ``plan`` and then uses the frozen market API."""

    def __init__(self, calls: list[str]) -> None:
        super().__init__(calls)
        self.planner = FakePlanner()
        self.forecast_seen: list[dict[str, Any]] = []

    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        forecast = {
            "origin_t": context.t,
            "horizon": 1,
            "demand_mw": dict(context.demand_mw),
            "generation_mw": dict(context.generation_mw),
        }
        self.forecast_seen.append(forecast)
        self.planner.plan(context.t, forecast, {"storage_soc": dict(context.storage_soc)})
        return super().clear(orders, round, context)


# ---------------------------------------------------------------------------
# Event doubles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeEvent:
    name: str
    t_start: int
    duration: int
    params: Mapping[str, Any]

    def is_active(self, t: int) -> bool:
        return self.t_start <= t < self.t_start + self.duration

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "t_start": self.t_start,
            "duration": self.duration,
            "params": dict(self.params),
        }


class FakeEventManager:
    """In-memory event manager double used only by the A1 tests."""

    def __init__(self, calls: list[str], events: Sequence[Any] = ()) -> None:
        self._calls = calls
        self._events: list[_FakeEvent] = []
        for event in events:
            self.schedule(event)

    @property
    def events(self) -> tuple[_FakeEvent, ...]:
        return tuple(self._events)

    @property
    def history(self) -> list[dict[str, Any]]:
        return []

    def schedule(self, event: Any) -> None:
        if any(existing.name == event.name for existing in self._events):
            raise ValueError(f"event {event.name!r} is already scheduled")
        self._events.append(
            _FakeEvent(
                name=str(event.name),
                t_start=int(event.t_start),
                duration=int(event.duration),
                params=dict(event.params),
            )
        )

    def active_events(self, t: int) -> list[_FakeEvent]:
        return [event for event in self._events if event.is_active(t)]

    def apply(self, t: int) -> EnvironmentModifiers:
        self._calls.append(f"events.apply:{t}")
        demand_multiplier: dict[str, float] = {}
        capacity_factor: dict[str, float] = {}
        cloud_override: float | None = None
        for event in self.active_events(t):
            demand_multiplier.update(event.params.get("demand_multiplier", {}))
            capacity_factor.update(event.params.get("capacity_factor", {}))
            if "cloud_override" in event.params:
                cloud_override = float(event.params["cloud_override"])
        return EnvironmentModifiers(
            demand_multiplier=demand_multiplier,
            capacity_factor=capacity_factor,
            cloud_override=cloud_override,
        )


class RecordingLogger(SimulationLogger):
    """Simulation logger that also records its call in the shared trace."""

    def __init__(self, calls: list[str]) -> None:
        super().__init__()
        self._calls = calls

    def record_step(self, result: Any) -> None:
        self._calls.append("logger.record_step")
        super().record_step(result)


def install_event_doubles(monkeypatch: Any, calls: list[str]) -> None:
    """Replace the A3 event manager with :class:`FakeEventManager` for one test."""

    import core.model as model_module

    monkeypatch.setattr(
        model_module,
        "EventManager",
        lambda events=(): FakeEventManager(calls, events),
    )
    monkeypatch.setattr(model_module, "build_scenario_events", lambda config, scenario: [])


def build_model(
    config: Mapping[str, Any],
    monkeypatch: Any,
    *,
    seed: int = 7,
    mode: str = "auction",
    scenario: str = "normal",
    calls: list[str] | None = None,
    logger: SimulationLogger | None = None,
    agents: Sequence[BaseAgent] | None = None,
) -> Any:
    """Build a ``GridModel`` wired to the isolated A1 doubles."""

    from core.model import GridModel

    call_log = [] if calls is None else calls
    install_event_doubles(monkeypatch, call_log)
    specs = resolve_agent_specs(config)
    environment = FakeEnvironment(config, seed, call_log)
    agent_list = (
        list(agents) if agents is not None else [FakeAgent(spec, call_log, seed) for spec in specs]
    )
    market = CentralAdapterDouble(call_log) if mode in CENTRAL_MODES else FakeMarket(call_log)
    negotiation = (
        None if mode in CENTRAL_MODES else FakeNegotiation(call_log, config["simulation"]["rounds"])
    )
    return GridModel(
        config,
        seed,
        mode=mode,
        scenario=scenario,
        environment=environment,
        agents=agent_list,
        market=market,
        negotiation=negotiation,
        logger=logger if logger is not None else RecordingLogger(call_log),
    )
