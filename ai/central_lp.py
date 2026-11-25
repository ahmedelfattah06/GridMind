"""Central linear-programming planner and market adapter (Team C1).

The planner solves the hourly dispatch LP from section 7.1 of the project
guide with ``scipy.optimize.linprog(method="highs")``:

``min sum_tau [ sum_k mc[k]*g[k,tau] + sum_i VOLL[i]*u[i,tau] ]``

subject to generation availability, demand limits, hourly energy balance and
battery dynamics. ``CentralMarketAdapter`` exposes the plan through the frozen
``MarketInterface``, replanning every six hours (``central_6h``) or every hour
(``central_1h``). Between replans the cached plan is executed; actual capacity
shortfalls are curtailed by lowest VOLL first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import linprog

from core.config import resolve_agent_specs
from market.auction import (
    ClearingResult,
    MarketContext,
    MarketInterface,
    Settlement,
)
from market.orders import Trade

EPSILON = 1e-9


@dataclass(frozen=True)
class DispatchPlan:
    """Dispatch decided by the central planner for one step.

    Attributes:
        t: Step the plan applies to.
        generation_mw: Dispatched generation per producer, in MW.
        served_mw: Served demand per consumer, in MW.
        charge_mw: Charging power per storage agent, in MW.
        discharge_mw: Discharging power per storage agent, in MW.
        unserved_mw: Unserved energy per consumer, in MW.
        deferred_mw: Deferred energy per consumer, in MW.
        objective: Value of the LP objective contributed by this hour, in
            currency units. The sum over every plan of one horizon equals
            :attr:`CentralLPPlanner.last_objective`.
    """

    t: int
    generation_mw: dict[str, float] = field(default_factory=dict)
    served_mw: dict[str, float] = field(default_factory=dict)
    charge_mw: dict[str, float] = field(default_factory=dict)
    discharge_mw: dict[str, float] = field(default_factory=dict)
    unserved_mw: dict[str, float] = field(default_factory=dict)
    deferred_mw: dict[str, float] = field(default_factory=dict)
    objective: float = 0.0


class CentralLPPlanner:
    """Centralised dispatch planner using a linear program."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Create the planner.

        Args:
            config: Full validated configuration.
        """

        self._config = config
        specs = resolve_agent_specs(config)
        self._producers = [spec for spec in specs if spec["role"] == "producer"]
        self._consumers = [spec for spec in specs if spec["role"] == "consumer"]
        self._storage = [spec for spec in specs if spec["role"] == "storage"]
        self._voll = {
            str(spec["id"]): float(config["voll"][str(spec["type"])]) for spec in self._consumers
        }
        self._marginal_cost = {
            str(spec["id"]): float(spec["marginal_cost"]) for spec in self._producers
        }
        self._horizon = int(config["simulation"]["horizon"])
        self.last_status: str = "not-solved"
        self.last_objective: float = 0.0

    @property
    def horizon(self) -> int:
        """Default planning horizon in hours."""

        return self._horizon

    def plan(
        self,
        t: int,
        forecast: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> DispatchPlan:
        """Solve the dispatch problem for step ``t`` and return its plan."""

        plans = self.plan_horizon(t, forecast, context)
        return plans[0]

    def plan_horizon(
        self,
        t: int,
        forecast: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> list[DispatchPlan]:
        """Solve the dispatch problem for the whole forecast horizon.

        Args:
            t: Current step.
            forecast: Column oriented forecast from ``GridModel.forecast``.
            context: Current state, optionally containing actual ``demand_mw``,
                ``generation_mw`` and ``storage_soc`` mappings.

        Returns:
            One :class:`DispatchPlan` per forecast hour.

        Raises:
            RuntimeError: If the LP does not find a solution.
        """

        demand, availability, steps = self._forecast_arrays(t, forecast, context)
        plan = self._solve(steps, demand, availability, context)
        return plan

    # ------------------------------------------------------------------
    # LP construction
    # ------------------------------------------------------------------

    def _forecast_arrays(
        self,
        t: int,
        forecast: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> tuple[dict[str, list[float]], dict[str, list[float]], list[int]]:
        steps = [int(value) for value in forecast.get("t", [])]
        if not steps:
            horizon = int(forecast.get("horizon", self._horizon))
            steps = list(range(t, t + max(1, horizon)))
        horizon = len(steps)

        forecast_demand = forecast.get("demand_mw", {})
        forecast_generation = forecast.get("generation_mw", {})
        demand: dict[str, list[float]] = {}
        for spec in self._consumers:
            agent_id = str(spec["id"])
            series = [float(value) for value in forecast_demand.get(agent_id, [0.0] * horizon)]
            demand[agent_id] = self._fit(series, horizon)

        availability: dict[str, list[float]] = {}
        for spec in self._producers:
            agent_id = str(spec["id"])
            series = [
                float(value) for value in forecast_generation.get(agent_id, [0.0] * horizon)
            ]
            availability[agent_id] = self._fit(series, horizon)

        # Actual current values replace the forecast origin for the first hour.
        actual_demand = context.get("demand_mw") if isinstance(context, Mapping) else None
        if isinstance(actual_demand, Mapping):
            for agent_id in demand:
                if agent_id in actual_demand:
                    demand[agent_id][0] = max(0.0, float(actual_demand[agent_id]))
        actual_generation = context.get("generation_mw") if isinstance(context, Mapping) else None
        if isinstance(actual_generation, Mapping):
            for agent_id in availability:
                if agent_id in actual_generation:
                    availability[agent_id][0] = max(0.0, float(actual_generation[agent_id]))
        return demand, availability, steps

    @staticmethod
    def _fit(series: list[float], horizon: int) -> list[float]:
        if len(series) >= horizon:
            return series[:horizon]
        if not series:
            return [0.0] * horizon
        return series + [series[-1]] * (horizon - len(series))

    def _solve(
        self,
        steps: Sequence[int],
        demand: Mapping[str, list[float]],
        availability: Mapping[str, list[float]],
        context: Mapping[str, Any],
    ) -> list[DispatchPlan]:
        horizon = len(steps)
        producer_ids = [str(spec["id"]) for spec in self._producers]
        consumer_ids = [str(spec["id"]) for spec in self._consumers]
        storage_ids = [str(spec["id"]) for spec in self._storage]
        n_prod = len(producer_ids)
        n_cons = len(consumer_ids)
        n_storage = len(storage_ids)

        # Variable layout per hour: generation, unserved, charge, discharge, soc.
        block = n_prod + n_cons + 3 * n_storage

        def idx(kind: str, index: int, tau: int) -> int:
            base = tau * block
            if kind == "g":
                return base + index
            if kind == "u":
                return base + n_prod + index
            if kind == "ch":
                return base + n_prod + n_cons + index
            if kind == "dis":
                return base + n_prod + n_cons + n_storage + index
            if kind == "soc":
                return base + n_prod + n_cons + 2 * n_storage + index
            raise ValueError(f"unknown variable kind {kind!r}")

        n_variables = horizon * block
        cost = np.zeros(n_variables)
        bounds: list[tuple[float, float]] = [(0.0, 0.0)] * n_variables

        for tau in range(horizon):
            for index, producer_id in enumerate(producer_ids):
                cost[idx("g", index, tau)] = self._marginal_cost[producer_id]
                bounds[idx("g", index, tau)] = (0.0, availability[producer_id][tau])
            for index, consumer_id in enumerate(consumer_ids):
                cost[idx("u", index, tau)] = self._voll[consumer_id]
                bounds[idx("u", index, tau)] = (0.0, demand[consumer_id][tau])
            for index, storage in enumerate(self._storage):
                capacity = float(storage["capacity_mwh"])
                rate = float(storage["max_rate_mw"])
                cost[idx("ch", index, tau)] = 1e-6
                cost[idx("dis", index, tau)] = 1e-6
                bounds[idx("ch", index, tau)] = (0.0, rate)
                bounds[idx("dis", index, tau)] = (0.0, rate)
                bounds[idx("soc", index, tau)] = (0.0, capacity)

        equality_rows: list[np.ndarray] = []
        equality_rhs: list[float] = []

        # Energy balance for every hour.
        for tau in range(horizon):
            row = np.zeros(n_variables)
            for index in range(n_prod):
                row[idx("g", index, tau)] = 1.0
            for index in range(n_storage):
                row[idx("dis", index, tau)] = 1.0
                row[idx("ch", index, tau)] = -1.0
            for index in range(n_cons):
                row[idx("u", index, tau)] = 1.0
            equality_rows.append(row)
            equality_rhs.append(float(sum(demand[cid][tau] for cid in consumer_ids)))

        # Battery dynamics: soc(tau) - soc(tau-1) - eta*ch + dis/eta = 0.
        storage_soc = context.get("storage_soc", {}) if isinstance(context, Mapping) else {}
        for index, storage in enumerate(self._storage):
            storage_id = str(storage["id"])
            efficiency = float(storage["efficiency"])
            initial_ratio = float(storage_soc.get(storage_id, storage["initial_soc"]))
            initial_mwh = initial_ratio * float(storage["capacity_mwh"])
            for tau in range(horizon):
                row = np.zeros(n_variables)
                row[idx("soc", index, tau)] = 1.0
                row[idx("ch", index, tau)] = -efficiency
                row[idx("dis", index, tau)] = 1.0 / efficiency
                if tau == 0:
                    equality_rhs.append(initial_mwh)
                else:
                    row[idx("soc", index, tau - 1)] = -1.0
                    equality_rhs.append(0.0)
                equality_rows.append(row)

        result = linprog(
            cost,
            A_eq=np.vstack(equality_rows),
            b_eq=np.asarray(equality_rhs, dtype=float),
            bounds=bounds,
            method="highs",
        )
        self.last_status = str(result.message)
        if not result.success or result.x is None:
            raise RuntimeError(f"central LP failed: {result.message}")
        values = np.asarray(result.x, dtype=float)
        self.last_objective = float(result.fun)

        plans: list[DispatchPlan] = []
        for tau, step in enumerate(steps):
            generation = {
                producer_id: _clean(values[idx("g", index, tau)])
                for index, producer_id in enumerate(producer_ids)
            }
            unserved = {
                consumer_id: _clean(values[idx("u", index, tau)])
                for index, consumer_id in enumerate(consumer_ids)
            }
            charge = {
                storage_id: _clean(values[idx("ch", index, tau)])
                for index, storage_id in enumerate(storage_ids)
            }
            discharge = {
                storage_id: _clean(values[idx("dis", index, tau)])
                for index, storage_id in enumerate(storage_ids)
            }
            served = {
                consumer_id: _clean(demand[consumer_id][tau] - unserved[consumer_id])
                for consumer_id in consumer_ids
            }
            # The LP minimises one objective over the whole horizon. Store this
            # hour's contribution so that summing a plan horizon does not count
            # the same total several times.
            base = tau * block
            hour_objective = float(
                np.dot(cost[base : base + block], values[base : base + block])
            )
            plans.append(
                DispatchPlan(
                    t=int(step),
                    generation_mw=generation,
                    served_mw=served,
                    charge_mw=charge,
                    discharge_mw=discharge,
                    unserved_mw=unserved,
                    deferred_mw={consumer_id: 0.0 for consumer_id in consumer_ids},
                    objective=hour_objective,
                )
            )
        return plans


class CentralMarketAdapter(MarketInterface):
    """Expose the central LP through the frozen :class:`MarketInterface`."""

    def __init__(
        self,
        config: Mapping[str, Any],
        environment: Any | None = None,
        interval: int = 6,
        planner: CentralLPPlanner | None = None,
    ) -> None:
        """Create the adapter.

        Args:
            config: Full validated configuration.
            environment: Optional Environment used to build the forecast.
            interval: Replanning interval in hours (6 for Central-6h, 1 for
                Central-1h).
            planner: Optional planner instance, mainly for tests.
        """

        if interval < 1:
            raise ValueError("interval must be a positive integer")
        self._config = config
        self._environment = environment
        self._interval = int(interval)
        self._planner = planner if planner is not None else CentralLPPlanner(config)
        self._storage_specs = {
            str(spec["id"]): spec
            for spec in resolve_agent_specs(config)
            if spec["role"] == "storage"
        }
        self._horizon = int(config["simulation"]["horizon"])
        self._plans: dict[int, DispatchPlan] = {}
        self._plan_origin: int | None = None
        self._last_price = 0.0
        self.last_context: MarketContext | None = None
        self.last_settlement: Settlement | None = None
        self.last_forecast: dict[str, Any] | None = None
        self.last_plan: DispatchPlan | None = None
        self.replan_count = 0

    @property
    def planner(self) -> CentralLPPlanner:
        """The LP planner used by this adapter."""

        return self._planner

    @property
    def interval(self) -> int:
        """Replanning interval in hours."""

        return self._interval

    def clear(
        self,
        orders: Sequence[Order],
        round: int,
        context: MarketContext,
    ) -> ClearingResult:
        """Replan when due and execute the current hour of the cached plan."""

        del orders  # Central dispatch replaces the auction order book.
        self.last_context = context
        if self._needs_replan(context.t):
            self._replan(context.t, context)
        plan = self._plans.get(context.t)
        if plan is None:
            self._replan(context.t, context)
            plan = self._plans[context.t]
        self.last_plan = plan
        trades, price, unserved = self._execute(plan, context)
        self._last_price = float(price)
        return ClearingResult(
            round=int(round),
            price=float(price),
            trades=tuple(trades),
            cleared_mw=float(sum(trade.qty_mw for trade in trades)),
        )

    def settle(
        self,
        context: MarketContext,
        trades: Sequence[Trade],
        price: float,
    ) -> Settlement:
        """Settle central dispatch with zero deferred energy."""

        bought: dict[str, float] = {}
        payments: dict[str, float] = {agent_id: 0.0 for agent_id in context.demand_mw}
        for trade in trades:
            bought[trade.buyer_id] = bought.get(trade.buyer_id, 0.0) + float(trade.qty_mw)
            payments[trade.buyer_id] = payments.get(trade.buyer_id, 0.0) + float(
                trade.qty_mw
            ) * float(trade.price)
            payments[trade.seller_id] = payments.get(trade.seller_id, 0.0) - float(
                trade.qty_mw
            ) * float(trade.price)
        unserved: dict[str, float] = {}
        for agent_id, demand in context.demand_mw.items():
            shortfall = max(0.0, float(demand) - bought.get(agent_id, 0.0))
            unserved[agent_id] = 0.0 if shortfall <= EPSILON else float(shortfall)
        deferred = {agent_id: 0.0 for agent_id in context.demand_mw}
        settlement = Settlement(
            price=float(price),
            trades=tuple(trades),
            unserved=unserved,
            deferred=deferred,
            payments=payments,
        )
        self.last_settlement = settlement
        return settlement

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _needs_replan(self, t: int) -> bool:
        if self._plan_origin is None or t not in self._plans:
            return True
        return (t - self._plan_origin) % self._interval == 0

    def _replan(self, t: int, context: MarketContext) -> None:
        forecast = self._build_forecast(t, context)
        mapping = {
            "demand_mw": dict(context.demand_mw),
            "generation_mw": dict(context.generation_mw),
            "storage_soc": dict(context.storage_soc),
        }
        plans = self._planner.plan_horizon(t, forecast, mapping)
        self._plans = {plan.t: plan for plan in plans}
        self._plan_origin = int(t)
        self.last_forecast = forecast
        self.replan_count += 1

    def _build_forecast(self, t: int, context: MarketContext) -> dict[str, Any]:
        if self._environment is not None:
            try:
                return self._environment.forecast(t, self._horizon)
            except ValueError:
                pass
        steps = list(range(t, t + self._horizon))
        consumer_demand = {agent_id: [float(value)] * self._horizon for agent_id, value in context.demand_mw.items()}
        producer_generation = {
            agent_id: [float(value)] * self._horizon
            for agent_id, value in context.generation_mw.items()
        }
        return {
            "origin_t": t,
            "horizon": self._horizon,
            "t": steps,
            "hour": [step % 24 for step in steps],
            "day": [step // 24 for step in steps],
            "demand_mw": consumer_demand,
            "generation_mw": producer_generation,
            "demand_total_mw": [float(sum(context.demand_mw.values()))] * self._horizon,
            "generation_total_mw": [float(sum(context.generation_mw.values()))] * self._horizon,
        }

    def _execute(
        self,
        plan: DispatchPlan,
        context: MarketContext,
    ) -> tuple[list[Trade], float, dict[str, float]]:
        # Actual generation is capped by the plan; unexpected surplus is
        # curtailed and unexpected shortage is curtailed by lowest VOLL first.
        generation = {
            agent_id: min(
                max(0.0, float(plan.generation_mw.get(agent_id, 0.0))),
                max(0.0, float(available)),
            )
            for agent_id, available in context.generation_mw.items()
        }
        # Physical storage limits at execution time. The cached plan may be
        # several hours old in Central-6h, so actual SoC can differ from the
        # planned trajectory.
        discharge: dict[str, float] = {}
        planned_charge: dict[str, float] = {}
        for agent_id, soc_ratio in context.storage_soc.items():
            spec = self._storage_specs.get(agent_id)
            if spec is None:  # pragma: no cover - validated fleet always matches
                continue
            capacity = float(spec["capacity_mwh"])
            rate = float(spec["max_rate_mw"])
            efficiency = float(spec["efficiency"])
            soc_mwh = max(0.0, float(soc_ratio)) * capacity
            max_discharge = min(rate, soc_mwh * efficiency)
            headroom_mwh = max(0.0, 1.0 - float(soc_ratio)) * capacity
            max_charge = min(rate, headroom_mwh / efficiency) if efficiency > 0.0 else 0.0
            discharge[agent_id] = min(
                max(0.0, float(plan.discharge_mw.get(agent_id, 0.0))),
                max_discharge,
            )
            planned_charge[agent_id] = min(
                max(0.0, float(plan.charge_mw.get(agent_id, 0.0))),
                max_charge,
            )
        total_generation = float(sum(generation.values()))
        total_discharge = float(sum(discharge.values()))
        total_demand = float(sum(float(value) for value in context.demand_mw.values()))
        supply_before_charge = total_generation + total_discharge
        if total_demand >= supply_before_charge:
            charge = {agent_id: 0.0 for agent_id in planned_charge}
            available = supply_before_charge
        else:
            surplus = supply_before_charge - total_demand
            charge = {
                agent_id: min(planned_charge[agent_id], surplus)
                for agent_id in planned_charge
            }
            # Do not charge more than the actual surplus in total.
            allocated = float(sum(charge.values()))
            if allocated > surplus:
                scale = surplus / allocated if allocated > 0.0 else 0.0
                charge = {agent_id: value * scale for agent_id, value in charge.items()}
            # Consumers are served first; charging uses only the leftover
            # surplus. Subtracting the charge from the available supply would
            # make the allocated ``served`` quantities unserved again.
            available = supply_before_charge - float(sum(charge.values()))

        # Allocate energy to consumers by descending VOLL (hospital last cut).
        order = sorted(
            context.demand_mw,
            key=lambda agent_id: (
                -float(context.voll.get(agent_id, 0.0)),
                agent_id,
            ),
        )
        served: dict[str, float] = {}
        remaining = max(0.0, available)
        for agent_id in order:
            demand = max(0.0, float(context.demand_mw[agent_id]))
            quantity = min(demand, remaining)
            served[agent_id] = _clean(quantity)
            remaining = max(0.0, remaining - quantity)
        unserved = {
            agent_id: _clean(max(0.0, float(context.demand_mw[agent_id]) - served[agent_id]))
            for agent_id in context.demand_mw
        }

        sellers: list[tuple[str, float, float]] = []
        for agent_id in sorted(
            generation, key=lambda item: (self._marginal_cost(item), item)
        ):
            if generation[agent_id] > EPSILON:
                sellers.append((agent_id, generation[agent_id], self._marginal_cost(agent_id)))
        for agent_id in sorted(discharge):
            if discharge[agent_id] > EPSILON:
                sellers.append(
                    (agent_id, discharge[agent_id], float(self._config["max_prices"]["flex"]))
                )

        buyers: list[tuple[str, float]] = [
            (agent_id, served[agent_id]) for agent_id in order if served[agent_id] > EPSILON
        ]
        buyers.extend(
            (agent_id, value) for agent_id, value in sorted(charge.items()) if value > EPSILON
        )

        matches: list[tuple[str, str, float]] = []
        used_costs: list[float] = []
        seller_index = 0
        seller_remaining = sellers[0][1] if sellers else 0.0
        for buyer_id, buyer_quantity in buyers:
            remaining_buyer = buyer_quantity
            while remaining_buyer > EPSILON and seller_index < len(sellers):
                quantity = min(remaining_buyer, seller_remaining)
                if quantity > EPSILON:
                    matches.append(
                        (buyer_id, sellers[seller_index][0], float(quantity))
                    )
                    used_costs.append(sellers[seller_index][2])
                remaining_buyer -= quantity
                seller_remaining -= quantity
                if seller_remaining <= EPSILON:
                    seller_index += 1
                    seller_remaining = sellers[seller_index][1] if seller_index < len(sellers) else 0.0
        # The uniform central price is the marginal cost of the most expensive
        # unit that actually sold. Curtailed (unused) generation must not set
        # the price.
        price = max(used_costs) if used_costs else float(self._last_price)
        trades = [
            Trade(buyer_id=buyer_id, seller_id=seller_id, qty_mw=quantity, price=float(price))
            for buyer_id, seller_id, quantity in matches
        ]
        return trades, float(price), unserved

    def _marginal_cost(self, agent_id: str) -> float:
        return float(self._planner._marginal_cost.get(agent_id, 0.0))  # noqa: SLF001


def _clean(value: float) -> float:
    value = float(value)
    return 0.0 if abs(value) <= EPSILON else value


__all__ = ["CentralLPPlanner", "CentralMarketAdapter", "DispatchPlan"]
