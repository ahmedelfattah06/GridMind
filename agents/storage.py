"""Storage agents (Team B2) - interface skeleton.

Owner: B2 (Producer and Storage Agents), with Team C2 for the learning policy.
Status: TODO. No charging, discharging or state-of-charge logic is
implemented in this skeleton.

Responsibilities to implement:

* charging and discharging orders within capacity, rate and efficiency limits,
* the state-of-charge transition of every step,
* the pluggable tabular Q-learning policy owned by Team C2.

See ``docs/contracts.md`` for the observation and settlement payloads.
"""

from __future__ import annotations

from typing import Any, Mapping

from agents.base import BaseAgent
from market.orders import Order


class StorageAgent(BaseAgent):
    """Battery agent with capacity, rate and efficiency limits."""

    def __init__(self, spec: Mapping[str, Any], config: Mapping[str, Any]) -> None:
        """Create a storage agent.

        Args:
            spec: Resolved agent specification (``capacity_mwh``,
                ``max_rate_mw``, ``efficiency``, ``initial_soc``).
            config: Full validated configuration, for market parameters.

        TODO(B2): define the storage state and validate the limits. The
        initial state of charge is an open decision (PD-02).
        """

        super().__init__(
            agent_id=str(spec["id"]),
            role="storage",
            agent_type=str(spec["type"]),
        )
        self._spec = dict(spec)
        self._config = config
        self._soc = float(spec["initial_soc"])

    @property
    def state_of_charge(self) -> float:
        """Current state of charge, in ``[0, 1]``.

        Only the configured initial value is returned.

        TODO(B2): update the state of charge in ``update(result)``.
        """

        return self._soc

    def decide(self, round: int) -> list[Order]:
        """Return the storage orders for one round.

        Raises:
            NotImplementedError: Always, until Team B2 implements the policy.

        TODO(B2): implement charging and discharging orders.
        """

        raise NotImplementedError(
            "TODO(B2): StorageAgent.decide is not implemented in the skeleton"
        )
