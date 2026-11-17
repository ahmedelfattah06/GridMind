"""Central linear programming planner (Team C1) - interface skeleton.

Owner: C1 (Centralized Optimization).
Status: TODO. No dispatch LP is implemented in this skeleton.

Responsibilities to implement:

* the hourly and horizon dispatch problem (generation, storage, unserved and
  deferred energy) with ``scipy.optimize.linprog``,
* an adapter that exposes the plan through ``market.auction.MarketInterface``
  so that ``GridModel`` can run the central modes.

The forecast payload consumed by :meth:`CentralLPPlanner.plan` is frozen in
``docs/contracts.md`` (section "Environment contract").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


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
        objective: Value of the LP objective, in currency units.
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
    """Centralised dispatch planner (Team C1)."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        """Create the planner.

        Args:
            config: Full validated configuration. Uses ``simulation.horizon``,
                ``voll``, ``max_prices`` and the fleet definitions.

        TODO(C1): define the LP formulation and its parameters.
        """

        self._config = config

    def plan(
        self,
        t: int,
        forecast: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> DispatchPlan:
        """Solve the dispatch problem for step ``t``.

        Args:
            t: Current step.
            forecast: Column oriented forecast from ``GridModel.forecast``.
            context: Additional state (storage SoC, agent limits).

        Raises:
            NotImplementedError: Always, until Team C1 implements the LP.
        """

        raise NotImplementedError("TODO(C1): CentralLPPlanner.plan is not implemented")
