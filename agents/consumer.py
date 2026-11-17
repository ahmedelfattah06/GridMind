"""Consumer agents (Team B1) - interface skeleton.

Owner: B1 (Consumer Agents and Base Agent).
Status: TODO. No bidding strategy is implemented in this skeleton.

Responsibilities to implement:

* read metered demand and flexibility from the observation,
* derive price ceilings from VOLL and ``max_prices``,
* submit buy orders and round dependent counter offers.

See ``docs/contracts.md`` for the observation and settlement payloads.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.base import BaseAgent
from market.orders import Order


class ConsumerAgent(BaseAgent):
    """Hospital, residential or factory agent."""

    def __init__(self, spec: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        """Create a consumer agent.

        Args:
            spec: Resolved agent specification (``id``, ``type``, ``base_mw``,
                ``flexibility``, ``voll``, ``max_price``).
            config: Full validated configuration, for market parameters.

        TODO(B1): define the consumer state (budget, deferred demand, history).
        """

        super().__init__(
            agent_id=str(spec["id"]),
            role="consumer",
            agent_type=str(spec["type"]),
        )
        self._spec = dict(spec)
        self._config = config

    def decide(self, round: int) -> list[Order]:
        """Return the consumer orders for one round.

        Raises:
            NotImplementedError: Always, until Team B1 implements the policy.

        TODO(B1): implement flexibility aware bidding.
        """

        raise NotImplementedError(
            "TODO(B1): ConsumerAgent.decide is not implemented in the skeleton"
        )
