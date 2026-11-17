"""Producer agents (Team B2) - interface skeleton.

Owner: B2 (Producer and Storage Agents).
Status: TODO. No offering strategy is implemented in this skeleton.

Responsibilities to implement:

* derive offers from marginal cost, the configured producer step and the
  initial markup,
* respect the available generation of the current step,
* submit sell orders and round dependent counter offers.

See ``docs/contracts.md`` for the observation and settlement payloads.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.base import BaseAgent
from market.orders import Order


class ProducerAgent(BaseAgent):
    """Solar, wind, thermal or peaker agent."""

    def __init__(self, spec: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        """Create a producer agent.

        Args:
            spec: Resolved agent specification (``id``, ``type``,
                ``capacity_mw``, ``marginal_cost``, ``capacity_factor``).
            config: Full validated configuration, for market parameters.

        TODO(B2): define the producer state (offers, revenue, availability).
        """

        super().__init__(
            agent_id=str(spec["id"]),
            role="producer",
            agent_type=str(spec["type"]),
        )
        self._spec = dict(spec)
        self._config = config

    def decide(self, round: int) -> list[Order]:
        """Return the producer orders for one round.

        Raises:
            NotImplementedError: Always, until Team B2 implements the policy.

        TODO(B2): implement marginal cost based offers and counter offers.
        """

        raise NotImplementedError(
            "TODO(B2): ProducerAgent.decide is not implemented in the skeleton"
        )
