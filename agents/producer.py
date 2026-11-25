"""Producer agents (Team B2).

Producers offer their entire available generation at
``marginal_cost * (1 + markup)``. Markup adapts after every hour: it rises by
5 percentage points when at least 95 % of the offer was sold and falls by the
same amount otherwise. Negotiation rounds lower the ask by the configured
``producer_step`` but never below marginal cost.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.base import BaseAgent
from market.orders import Order


class ProducerAgent(BaseAgent):
    """Solar, wind, thermal or peaker agent."""

    def __init__(
        self,
        spec: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> None:
        """Create a producer agent.

        Args:
            spec: Resolved agent specification.
            config: Full validated configuration.
        """

        self._spec = dict(spec)
        self._config = config
        self._capacity_mw = float(spec["capacity_mw"])
        self._marginal_cost = float(spec["marginal_cost"])
        self._producer_step = float(config["market"]["producer_step"])
        self._markup = float(config["market"]["initial_markup"])
        self._available_mw = 0.0
        self._sold_mw = 0.0
        self._revenue = 0.0
        super().__init__(
            agent_id=str(spec["id"]),
            role="producer",
            agent_type=str(spec["type"]),
        )

    @property
    def markup(self) -> float:
        """Current adaptive markup in ``[0, 1]``."""

        return self._markup

    def _on_observe(self, obs: dict[str, Any]) -> None:
        environment = obs["environment"]
        self._available_mw = max(
            0.0, float(environment["generation_mw"].get(self.agent_id, 0.0))
        )

    def decide(self, round: int) -> list[Order]:
        """Return one sell order for the available generation.

        Args:
            round: Negotiation round, starting at ``1``.
        """

        if round < 1:
            raise ValueError(f"round must be positive, got {round}")
        if self._available_mw <= 0.0:
            return []
        base_price = self._marginal_cost * (1.0 + self._markup)
        if round > 1:
            factor = (1.0 - self._producer_step) ** (round - 1)
            price = max(self._marginal_cost, base_price * factor)
        else:
            price = base_price
        return [
            Order(
                agent_id=self.agent_id,
                side="sell",
                qty_mw=float(self._available_mw),
                price=float(max(0.0, price)),
                priority=4,
                round=round,
            )
        ]

    def _on_update(self, result: dict[str, Any]) -> None:
        self._sold_mw = float(result.get("sold_mw", 0.0))
        self._revenue = -float(result.get("payment", 0.0))
        if self._available_mw > 0.0:
            if self._sold_mw >= 0.95 * self._available_mw:
                self._markup = min(1.0, self._markup + 0.05)
            else:
                self._markup = max(0.0, self._markup - 0.05)

    def snapshot(self) -> dict[str, Any]:
        """Return the public producer state."""

        payload = super().snapshot()
        payload.update(
            {
                "capacity_mw": float(self._capacity_mw),
                "available_mw": float(self._available_mw),
                "marginal_cost": float(self._marginal_cost),
                "markup": float(self._markup),
                "sold_mw": float(self._sold_mw),
                "revenue": float(self._revenue),
            }
        )
        return payload
