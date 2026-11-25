"""Consumer agents (Team B1).

Hospitals are inflexible and bid their full metered demand at their high
ceiling. Residential and factory agents split demand into a fixed part and a
flexible part. Flexible energy that cannot be served is deferred by settlement
and is re-bid once in the next hour (rebound). Counter-offers follow the
configured ``raise_factor`` and never exceed the agent's ceiling.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.base import BaseAgent
from core.config import derive_agent_forecast_rng
from market.orders import Order

PRIORITY_BY_TYPE = {"hospital": 1, "residential": 2, "factory": 3}
FLEX_PRIORITY = 4
EPSILON = 1e-9


class ConsumerAgent(BaseAgent):
    """Hospital, residential or factory agent."""

    def __init__(
        self,
        spec: Mapping[str, Any],
        config: Mapping[str, Any],
        seed: int = 0,
    ) -> None:
        """Create a consumer agent.

        Args:
            spec: Resolved agent specification.
            config: Full validated configuration.
            seed: Simulation seed used for the demand forecast noise.
        """

        self._spec = dict(spec)
        self._config = config
        self._max_price = float(spec["max_price"])
        self._flexibility = float(spec["flexibility"])
        self._flex_price = float(config["max_prices"]["flex"])
        self._raise_factor = float(config["market"]["raise_factor"])
        # Forecast errors use their own stream; the demand model owns the
        # realised-demand stream for the same agent id.
        self._rng = derive_agent_forecast_rng(seed, str(spec["id"]))
        self._demand_mw = 0.0
        self._metered_demand_mw = 0.0
        self._deferred_mw = 0.0
        self._bought_mw = 0.0
        self._unserved_mw = 0.0
        self._payment = 0.0
        super().__init__(
            agent_id=str(spec["id"]),
            role="consumer",
            agent_type=str(spec["type"]),
        )

    @property
    def priority(self) -> int:
        """Auction priority: hospital 1, residential 2, factory 3."""

        return PRIORITY_BY_TYPE.get(self.agent_type, 3)

    @property
    def deferred_mw(self) -> float:
        """Flexible energy deferred by the previous settlement."""

        return self._deferred_mw

    def _on_observe(self, obs: dict[str, Any]) -> None:
        environment = obs["environment"]
        metered = float(environment["demand_mw"].get(self.agent_id, 0.0))
        # Each consumer has its own forecast error; it never sees other agents.
        noise = float(self._rng.normal(0.0, 0.03))
        if self.agent_type == "hospital":
            # A hospital never deliberately reduces its bid below metered
            # demand: under-bidding would create avoidable outages for the most
            # critical load. Positive forecast error still adds a safety margin.
            noise = max(0.0, noise)
        self._metered_demand_mw = max(0.0, metered * (1.0 + noise))
        # The previous deferred energy is re-bid once in the next hour.
        self._demand_mw = self._metered_demand_mw + self._deferred_mw

    def decide(self, round: int) -> list[Order]:
        """Return the consumer orders for one round.

        Fixed demand is bid at the consumer ceiling. Flexible demand is bid at
        the ``max_prices.flex`` ceiling. Round escalation is bounded by the
        ceiling, exactly as specified by the project guide.
        """

        if round < 1:
            raise ValueError(f"round must be positive, got {round}")
        demand = max(0.0, self._demand_mw)
        if demand <= EPSILON:
            return []

        escalation = self._raise_factor ** (round - 1)
        fixed_qty = demand * (1.0 - self._flexibility)
        flex_qty = demand * self._flexibility
        orders: list[Order] = []
        if fixed_qty > EPSILON:
            orders.append(
                Order(
                    agent_id=self.agent_id,
                    side="buy",
                    qty_mw=float(fixed_qty),
                    price=float(min(self._max_price, self._max_price * escalation)),
                    priority=self.priority,
                    round=round,
                )
            )
        if flex_qty > EPSILON:
            orders.append(
                Order(
                    agent_id=self.agent_id,
                    side="buy",
                    qty_mw=float(flex_qty),
                    price=float(min(self._flex_price, self._flex_price * escalation)),
                    priority=FLEX_PRIORITY,
                    round=round,
                )
            )
        return orders

    def _on_update(self, result: dict[str, Any]) -> None:
        self._deferred_mw = float(result.get("deferred_mw", 0.0))
        self._bought_mw = float(result.get("bought_mw", 0.0))
        self._unserved_mw = float(result.get("unserved_mw", 0.0))
        self._payment = float(result.get("payment", 0.0))

    def snapshot(self) -> dict[str, Any]:
        """Return the public consumer state."""

        payload = super().snapshot()
        payload.update(
            {
                "demand_mw": float(self._demand_mw),
                "metered_demand_mw": float(self._metered_demand_mw),
                "deferred_mw": float(self._deferred_mw),
                "bought_mw": float(self._bought_mw),
                "unserved_mw": float(self._unserved_mw),
                "payment": float(self._payment),
                "flexibility": float(self._flexibility),
                "max_price": float(self._max_price),
                "priority": self.priority,
            }
        )
        return payload


__all__ = ["ConsumerAgent", "PRIORITY_BY_TYPE", "FLEX_PRIORITY"]
