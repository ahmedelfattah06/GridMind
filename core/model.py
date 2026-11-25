"""The GridMind simulation model (Team A1).

:class:`GridModel` orchestrates one simulation run. It owns the clock, the
environment, the agents, the market, the event manager and the logger, and it
never contains market or agent decision logic itself. Those components are
injected and only have to satisfy the documented interfaces.

Execution order of one step (frozen by the specification):

1. ``Environment.update(t)``
2. ``Events.apply(t)``
3. ``Agent.observe(obs)``
4. Agent decision rounds
5. Market clearing
6. Settlement
7. Agent updates
8. Logging

Auction modes use rounds ``2..simulation.rounds`` with the injected negotiation
protocol. Central modes (``central``, ``central_6h``, ``central_1h``) delegate
clearing to the injected C1 ``MarketInterface`` adapter that calls
``ai.central_lp.CentralLPPlanner.plan()`` internally; the model contains no LP
logic. ``restore`` is intentionally not part of the frozen public contract:
the UI keeps the live model (see ``docs/contracts.md`` and the project guide's
``st.session_state`` design) and :meth:`GridModel.snapshot` exposes every value
needed to render it.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from agents.base import BaseAgent, MockAgent
from core.clock import SimulationClock
from core.config import (
    CENTRAL_MODES,
    MOCK_MODE,
    SUPPORTED_MODES,
    resolve_agent_specs,
    validate_config,
)
from core.environment import Environment, EnvironmentState
from core.events import (
    SUPPORTED_EVENT_PARAMS,
    Event,
    EventManager,
    build_scenario_events,
    normalise_scenario,
)
from core.logger import SimulationLogger
from market.auction import (
    MarketContext,
    MarketInterface,
    MockAuction,
    Settlement,
)
from market.negotiation import NegotiationProtocol, StubNegotiation
from market.orders import Order, Trade

LOGGER = logging.getLogger("gridmind.model")


@dataclass(frozen=True)
class StepResult:
    """Immutable result of one simulation step.

    This structure is a frozen integration contract: field names, types and
    units must not change without the approval of all four team leads.

    Attributes:
        t: Absolute simulation step.
        price: Final clearing price, currency per MWh.
        supply_mw: Total available generation, in MW.
        demand_mw: Total requested demand, in MW.
        unserved: Unserved energy per consumer agent, in MW.
        deferred: Deferred (flexible) energy per consumer agent, in MW.
        trades: Trades of the final negotiation round.
        orders: All orders submitted in every round.
        messages: Number of orders exchanged during the step.
        soc: State of charge per storage agent, in ``[0, 1]``.
        generation: Available generation per producer agent, in MW.
    """

    t: int
    price: float
    supply_mw: float
    demand_mw: float
    unserved: dict[str, float]
    deferred: dict[str, float]
    trades: list[Trade]
    orders: list[Order]
    messages: int
    soc: dict[str, float]
    generation: dict[str, float]


class GridModel:
    """Multi-agent smart energy trading simulation."""

    def __init__(
        self,
        config: dict[str, Any],
        seed: int,
        mode: str,
        scenario: str = "normal",
        *,
        environment: Environment | None = None,
        agents: Sequence[BaseAgent] | None = None,
        market: MarketInterface | None = None,
        negotiation: NegotiationProtocol | None = None,
        logger: SimulationLogger | None = None,
    ) -> None:
        """Create a simulation run.

        Args:
            config: Validated configuration dictionary from
                :func:`core.config.load_config`.
            seed: Main simulation seed. Every random stream derives from it.
            mode: One of ``central``, ``central_6h``, ``central_1h``,
                ``auction``, ``auction_q`` or the orchestration-only ``mock``.
                ``central`` is the generic central mode; the two official
                Central systems keep their replanning-interval ids.
            scenario: Official scenario key or display name.
            environment: Optional Environment component (A2).
            agents: Optional agent list (Team B). Required for official modes.
            market: Optional market implementation (B3 for auctions, C1
                adapter for central planning). Required for official modes.
            negotiation: Optional negotiation protocol (B3). Required for
                official modes.
            logger: Optional logger, mainly for tests.

        Raises:
            ValueError: If the config, mode, scenario or seed is invalid.
            RuntimeError: If an official mode is requested without the
                components owned by another team.
        """

        self._config = validate_config(config)
        _validate_seed(seed)
        self._seed = seed
        self._mode = _validate_mode(mode)
        self._central = self._mode in CENTRAL_MODES
        self._scenario = normalise_scenario(scenario)
        if self._scenario not in self._config["scenarios"]:
            raise ValueError(
                f"unknown scenario {scenario!r}; expected one of {sorted(self._config['scenarios'])}"
            )

        self._clock = SimulationClock(self._config["simulation"]["steps"])
        self._rounds = int(self._config["simulation"]["rounds"])
        self._environment = (
            environment if environment is not None else Environment(self._config, seed)
        )
        self._events = EventManager(build_scenario_events(self._config, self._scenario))
        self._logger = logger if logger is not None else SimulationLogger()
        self._results: list[StepResult] = []
        self._agent_specs = resolve_agent_specs(self._config)
        self._consumer_ids = [
            str(spec["id"]) for spec in self._agent_specs if spec["role"] == "consumer"
        ]
        self._producer_ids = [
            str(spec["id"]) for spec in self._agent_specs if spec["role"] == "producer"
        ]

        self._agents = self._resolve_agents(agents)
        self._market = self._resolve_market(market)
        self._negotiation: NegotiationProtocol | None = self._resolve_negotiation(negotiation)
        self._in_step = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def step(self) -> StepResult:
        """Execute one complete simulation step.

        Returns:
            The :class:`StepResult` of the executed step.

        Raises:
            RuntimeError: If the simulation has already finished or a step is
                already in progress.
        """

        if self._clock.is_finished:
            raise RuntimeError(
                f"simulation finished after {self._clock.steps} steps; no further step possible"
            )
        if self._in_step:
            raise RuntimeError("step() is not re-entrant")

        self._in_step = True
        try:
            result = self._execute_step()
        except Exception:
            self._in_step = False
            raise
        self._in_step = False
        self._clock.advance()
        return result

    def inject_event(self, name: str, **kw: Any) -> None:
        """Schedule an additional event during the run.

        Args:
            name: Event name, unique within the run.
            **kw: ``t_start`` (default: current step), ``duration`` (default:
                one step), an optional ``params`` mapping, and/or the modifier
                keywords ``demand_multiplier``, ``capacity_factor`` and
                ``cloud_override``.

        Raises:
            ValueError: If the event is invalid or already scheduled.
        """

        kwargs = dict(kw)
        t_start = kwargs.pop("t_start", self._clock.t)
        duration = kwargs.pop("duration", 1)
        params = kwargs.pop("params", {})
        if not isinstance(params, Mapping):
            raise ValueError(f"params must be a mapping, got {type(params).__name__}")
        merged_params = dict(params)
        merged_params.update(kwargs)
        _validate_injected_event(
            name,
            t_start,
            duration,
            merged_params,
            steps=self._clock.steps,
            current_t=self._clock.t,
        )
        event = Event(
            name=name,
            t_start=int(t_start),
            duration=int(duration),
            params=merged_params,
        )
        self._events.schedule(event)
        LOGGER.info("injected event %s at t=%d for %d steps", name, t_start, duration)

    def snapshot(self) -> dict[str, Any]:
        """Return the complete public state of the simulation.

        The payload is JSON-serialisable (all nested dataclasses are converted
        to plain dictionaries) and contains the clock, environment, agent
        snapshots, active and scheduled events, the last clearing result and the
        per-agent aggregates needed by the dashboard.
        """

        environment_state = self._environment.state if self._results else None
        last = self._results[-1] if self._results else None
        return {
            "t": self._clock.t,
            "hour": self._clock.hour,
            "day": self._clock.day,
            "steps": self._clock.steps,
            "is_finished": self._clock.is_finished,
            "progress": self._clock.progress,
            "mode": self._mode,
            "scenario": self._scenario,
            "seed": self._seed,
            "price": float(last.price) if last else 0.0,
            "environment": environment_state.as_dict() if environment_state else {},
            "agents": {agent.agent_id: agent.snapshot() for agent in self._agents},
            "active_events": [event.name for event in self._events.active_events(self._clock.t)],
            "scheduled_events": [event.as_dict() for event in self._events.events],
            "log_rows": len(self._logger),
            "unserved_mw": float(sum(last.unserved.values())) if last else 0.0,
            "deferred_mw": float(sum(last.deferred.values())) if last else 0.0,
            "unserved": dict(last.unserved) if last else {},
            "deferred": dict(last.deferred) if last else {},
            "soc": dict(last.soc) if last else {},
            "generation": dict(last.generation) if last else {},
            "orders": [asdict(order) for order in last.orders] if last else [],
            "trades": [asdict(trade) for trade in last.trades] if last else [],
            "messages": int(last.messages) if last else 0,
        }

    def forecast(self, t: int, horizon: int) -> dict[str, Any]:
        """Forecast environment values for the next ``horizon`` hours.

        Args:
            t: Origin step. Must not lie in the past.
            horizon: Number of hourly values to produce.

        Returns:
            Column oriented forecast dictionary, see
            :meth:`core.environment.Environment.forecast`. The keys
            ``origin_t``, ``horizon`` and ``mode`` are always present.

        Raises:
            ValueError: If ``t`` is outside the simulation or in the past.
        """

        if isinstance(t, bool) or not isinstance(t, int) or t < 0 or t > self._clock.steps:
            raise ValueError(f"t must be an integer within [0, {self._clock.steps}], got {t!r}")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise ValueError(f"horizon must be a positive integer, got {horizon!r}")
        if self._results and t < self._clock.t:
            raise ValueError(f"cannot forecast from the past (current t={self._clock.t}, got {t})")
        forecast = self._environment.forecast(t, horizon)
        forecast["mode"] = self._mode
        return forecast

    @property
    def clock(self) -> SimulationClock:
        """The simulation clock."""

        return self._clock

    @property
    def logger(self) -> SimulationLogger:
        """The simulation logger, containing every executed step."""

        return self._logger

    @property
    def results(self) -> list[StepResult]:
        """All step results executed so far."""

        return list(self._results)

    @property
    def events(self) -> EventManager:
        """The event manager of the run."""

        return self._events

    @property
    def mode(self) -> str:
        """Comparison system mode of the run."""

        return self._mode

    @property
    def is_central(self) -> bool:
        """Whether the run uses a central-planning mode."""

        return self._central

    @property
    def scenario(self) -> str:
        """Official scenario key of the run."""

        return self._scenario

    @property
    def agents(self) -> tuple[BaseAgent, ...]:
        """Agents participating in the run."""

        return tuple(self._agents)

    # ------------------------------------------------------------------
    # Step orchestration
    # ------------------------------------------------------------------

    def _execute_step(self) -> StepResult:
        t = self._clock.t

        # 1. Environment update.
        environment_state = self._environment.update(t)

        # 2. Events apply.
        modifiers = self._events.apply(t)
        active_events = tuple(event.name for event in self._events.active_events(t))
        environment_state = self._environment.apply_modifiers(modifiers, active_events)

        # 3. Agents observe.
        observations = self._build_observations(environment_state)
        for agent in self._agents:
            agent.observe(observations[agent.agent_id])

        market_context = self._build_market_context(environment_state)

        # 4. Round 1 decisions.
        all_orders = self._collect_orders(round=1)
        messages = len(all_orders)

        # 5. Market clearing.
        clearing = self._market.clear(all_orders, 1, market_context)
        LOGGER.debug("t=%d round=1 price=%.4f cleared=%.3f", t, clearing.price, clearing.cleared_mw)

        # 6. Negotiation rounds (auction modes only). Central modes delegate the
        # dispatch to the injected C1 MarketInterface adapter, which has no
        # negotiation protocol; it replans according to its own interval.
        if not self._central:
            if self._negotiation is None:  # pragma: no cover - guarded in __init__
                raise RuntimeError("auction mode requires a negotiation protocol")
            for round_number in range(2, self._rounds + 1):
                round_orders = self._negotiation.refine(
                    round_number,
                    self._collect_orders(round=round_number),
                    clearing,
                    market_context,
                )
                all_orders.extend(round_orders)
                messages += len(round_orders)
                clearing = self._market.clear(round_orders, round_number, market_context)

        # 7. Settlement.
        settlement = self._market.settle(market_context, clearing.trades, clearing.price)

        # 8. Agent updates. The settlement payload carries the state of charge
        # observed during the step; the logged value is read again afterwards so
        # that the log reflects any storage transition performed in update().
        state_of_charge = self._state_of_charge()
        self._update_agents(settlement, environment_state, state_of_charge)
        logged_soc = self._state_of_charge()

        # 9. Logging.
        result = StepResult(
            t=t,
            price=float(settlement.price),
            supply_mw=float(environment_state.generation_total_mw),
            demand_mw=float(environment_state.demand_total_mw),
            unserved=dict(settlement.unserved),
            deferred=dict(settlement.deferred),
            trades=list(settlement.trades),
            orders=list(all_orders),
            messages=int(messages),
            soc=logged_soc,
            generation=dict(environment_state.generation_mw),
        )
        self._logger.record_step(result)
        self._results.append(result)
        return result

    def _collect_orders(self, round: int) -> list[Order]:
        orders: list[Order] = []
        for agent in self._agents:
            agent_orders = agent.decide(round)
            for order in agent_orders:
                if not isinstance(order, Order):
                    raise TypeError(
                        f"agent {agent.agent_id} returned "
                        f"{type(order).__name__} instead of Order"
                    )
                if order.agent_id != agent.agent_id:
                    raise ValueError(
                        f"agent {agent.agent_id} submitted an order for {order.agent_id}"
                    )
                if order.round != round:
                    raise ValueError(
                        f"agent {agent.agent_id} submitted round {order.round} " f"in round {round}"
                    )
                orders.append(order)
        return orders

    def _build_observations(self, state: EnvironmentState) -> dict[str, dict[str, Any]]:
        # Agents only see the consequences of events, never the event names.
        environment_view = state.as_dict()
        environment_view.pop("active_events", None)
        base: dict[str, Any] = {
            "t": state.t,
            "hour": state.hour,
            "day": state.day,
            "mode": self._mode,
            "scenario": self._scenario,
            "environment": environment_view,
            "last_price": self._logger.last_price(),
            "market": dict(self._config["market"]),
        }
        return {agent.agent_id: {**base, "own_agent": agent.snapshot()} for agent in self._agents}

    def _build_market_context(self, state: EnvironmentState) -> MarketContext:
        consumers = [spec for spec in self._agent_specs if spec["role"] == "consumer"]
        producers = [spec for spec in self._agent_specs if spec["role"] == "producer"]
        return MarketContext(
            t=state.t,
            demand_mw=dict(state.demand_mw),
            generation_mw=dict(state.generation_mw),
            flexibility={str(spec["id"]): float(spec["flexibility"]) for spec in consumers},
            consumer_types={str(spec["id"]): str(spec["type"]) for spec in consumers},
            producer_types={str(spec["id"]): str(spec["type"]) for spec in producers},
            storage_soc=self._state_of_charge(),
            voll={str(spec["id"]): float(spec["voll"]) for spec in consumers},
            max_price={str(spec["id"]): float(spec["max_price"]) for spec in consumers},
            settings=dict(self._config["market"]),
        )

    def _update_agents(
        self,
        settlement: Settlement,
        state: EnvironmentState,
        state_of_charge: Mapping[str, float],
    ) -> None:
        bought: dict[str, float] = {}
        sold: dict[str, float] = {}
        for trade in settlement.trades:
            bought[trade.buyer_id] = bought.get(trade.buyer_id, 0.0) + float(trade.qty_mw)
            sold[trade.seller_id] = sold.get(trade.seller_id, 0.0) + float(trade.qty_mw)
        system_unserved = float(sum(settlement.unserved.values()))

        for agent in self._agents:
            agent_id = agent.agent_id
            agent.update(
                {
                    "t": state.t,
                    "price": float(settlement.price),
                    "bought_mw": bought.get(agent_id, 0.0),
                    "sold_mw": sold.get(agent_id, 0.0),
                    "payment": float(settlement.payments.get(agent_id, 0.0)),
                    "unserved_mw": float(settlement.unserved.get(agent_id, 0.0)),
                    "deferred_mw": float(settlement.deferred.get(agent_id, 0.0)),
                    "generation_mw": float(state.generation_mw.get(agent_id, 0.0)),
                    "system_unserved_mw": system_unserved,
                    "soc": float(state_of_charge.get(agent_id, 0.0)),
                }
            )

    def _state_of_charge(self) -> dict[str, float]:
        state_of_charge: dict[str, float] = {}
        for agent in self._agents:
            if agent.role != "storage":
                continue
            soc = getattr(agent, "state_of_charge", None)
            if soc is None:
                # The frozen contract guarantees ``soc`` in Agent.snapshot();
                # the property is only a convenience used by the implementation.
                soc = agent.snapshot().get("soc")
            if soc is not None:
                state_of_charge[agent.agent_id] = float(soc)
        return state_of_charge

    # ------------------------------------------------------------------
    # Component resolution
    # ------------------------------------------------------------------

    def _resolve_agents(self, agents: Sequence[BaseAgent] | None) -> list[BaseAgent]:
        if agents is not None:
            resolved = list(agents)
            if not resolved:
                raise ValueError("agents must not be empty")
            ids = [agent.agent_id for agent in resolved]
            if len(ids) != len(set(ids)):
                raise ValueError("agent ids must be unique")
            specs = {str(spec["id"]): spec for spec in self._agent_specs}
            for agent in resolved:
                spec = specs.get(agent.agent_id)
                if spec is None:
                    raise ValueError(
                        f"agent {agent.agent_id!r} is not defined by the configuration"
                    )
                if agent.role != spec["role"]:
                    raise ValueError(
                        f"agent {agent.agent_id!r} has role {agent.role!r}, "
                        f"configuration says {spec['role']!r}"
                    )
                if agent.agent_type != spec["type"]:
                    raise ValueError(
                        f"agent {agent.agent_id!r} has type {agent.agent_type!r}, "
                        f"configuration says {spec['type']!r}"
                    )
            return resolved
        if self._mode != MOCK_MODE:
            raise RuntimeError(
                f"mode {self._mode!r} requires real agents owned by Team B1/B2; "
                "inject them with GridModel(..., agents=[...])"
            )
        LOGGER.warning(
            "mode='mock' uses MockAgent and MockAuction: orchestration testing only, "
            "never use these results in the report"
        )
        return [MockAgent(spec) for spec in self._agent_specs]

    def _resolve_market(self, market: MarketInterface | None) -> MarketInterface:
        if market is not None:
            return market
        if self._mode != MOCK_MODE:
            raise RuntimeError(
                f"mode {self._mode!r} requires a market implementation owned by Team B3 "
                "(auction modes) or Team C1 (central modes); inject it with "
                "GridModel(..., market=...)"
            )
        return MockAuction()

    def _resolve_negotiation(
        self, negotiation: NegotiationProtocol | None
    ) -> NegotiationProtocol | None:
        if self._central:
            # Central planning has no negotiation rounds; C1's adapter owns the
            # replanning interval. An injected protocol is accepted but unused.
            return negotiation
        if negotiation is not None:
            if negotiation.rounds != self._rounds:
                raise ValueError(
                    f"negotiation.rounds={negotiation.rounds} does not match "
                    f"simulation.rounds={self._rounds}"
                )
            return negotiation
        if self._mode != MOCK_MODE:
            raise RuntimeError(
                f"mode {self._mode!r} requires a negotiation protocol owned by Team B3; "
                "inject it with GridModel(..., negotiation=...)"
            )
        return StubNegotiation(self._rounds)


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")


def _validate_mode(mode: str) -> str:
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"mode must be one of {list(SUPPORTED_MODES)}, got {mode!r}")
    return mode


def _validate_injected_event(
    name: str,
    t_start: Any,
    duration: Any,
    params: Mapping[str, Any],
    *,
    steps: int,
    current_t: int,
) -> None:
    """Validate the arguments of :meth:`GridModel.inject_event`.

    Event timing, merging and target resolution remain Team A3's responsibility.
    This boundary check only rejects payloads that can never be scheduled, so the
    caller receives a precise error instead of a failure deep inside the event
    manager.
    """

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"event name must be a non-empty string, got {name!r}")
    if isinstance(t_start, bool) or not isinstance(t_start, int):
        raise ValueError(f"t_start must be an integer, got {t_start!r}")
    if t_start < current_t:
        raise ValueError(f"t_start={t_start} lies before the current step {current_t}")
    if t_start >= steps:
        raise ValueError(f"t_start={t_start} must be smaller than simulation.steps={steps}")
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1:
        raise ValueError(f"duration must be a positive integer, got {duration!r}")

    unknown = set(params) - set(SUPPORTED_EVENT_PARAMS)
    if unknown:
        raise ValueError(f"unsupported event parameters: {sorted(unknown)}")
    for key in ("demand_multiplier", "capacity_factor"):
        if key in params and not isinstance(params[key], Mapping):
            raise ValueError(f"{key} must be a mapping, got {type(params[key]).__name__}")
    if "cloud_override" in params:
        value = params["cloud_override"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"cloud_override must be a number, got {value!r}")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"cloud_override must lie within [0, 1], got {value!r}")
