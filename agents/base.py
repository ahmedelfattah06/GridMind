"""Base agent contract (Team B1).

Every GridMind agent implements the frozen interface from ``docs/contracts.md``:

* ``observe(obs)`` once per step, before any decision;
* ``decide(round)`` once per negotiation round;
* ``update(result)`` once per step, after settlement;
* ``snapshot()`` for logging and the dashboard.

The base class stores the common observation and settlement state. Concrete
agents own their decision rules; no market logic lives here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from market.orders import Order


class BaseAgent(ABC):
    """Common contract and state for every GridMind agent."""

    def __init__(
        self,
        agent_id: str,
        role: str,
        agent_type: str,
    ) -> None:
        """Create the agent.

        Args:
            agent_id: Unique agent identifier, for example ``"factory_1"``.
            role: ``"consumer"``, ``"producer"`` or ``"storage"``.
            agent_type: Concrete type, for example ``"hospital"`` or ``"solar"``.

        Raises:
            ValueError: If an identity field is empty or the role is unknown.
        """

        if not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("agent_id must be a non-empty string")
        if role not in ("consumer", "producer", "storage"):
            raise ValueError(f"unknown agent role {role!r}")
        if not isinstance(agent_type, str) or not agent_type.strip():
            raise ValueError("agent_type must be a non-empty string")
        self._agent_id = agent_id
        self._role = role
        self._agent_type = agent_type

        self._observation: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._last_price = 0.0
        self._t = 0
        self._hour = 0
        self._day = 0

    @property
    def agent_id(self) -> str:
        """Unique agent identifier."""

        return self._agent_id

    @property
    def role(self) -> str:
        """Agent role: consumer, producer or storage."""

        return self._role

    @property
    def agent_type(self) -> str:
        """Concrete agent type."""

        return self._agent_type

    @property
    def observation(self) -> dict[str, Any] | None:
        """Most recent observation, exposed for tests and the dashboard."""

        return self._observation

    @property
    def last_result(self) -> dict[str, Any] | None:
        """Most recent settlement payload."""

        return self._last_result

    def observe(self, obs: dict[str, Any]) -> None:
        """Receive the observation of the current step.

        Args:
            obs: Model observation, see ``docs/contracts.md``.

        Raises:
            ValueError: If the observation does not contain the required keys.
        """

        for key in ("t", "hour", "day", "environment", "last_price"):
            if key not in obs:
                raise ValueError(f"observation is missing required key {key!r}")
        self._observation = obs
        self._t = int(obs["t"])
        self._hour = int(obs["hour"])
        self._day = int(obs["day"])
        self._last_price = float(obs["last_price"])
        self._on_observe(obs)

    @abstractmethod
    def decide(self, round: int) -> list[Order]:
        """Return the orders submitted in one negotiation round.

        Args:
            round: Negotiation round, starting at ``1``.

        Returns:
            Orders submitted by this agent for the round.
        """

    def update(self, result: dict[str, Any]) -> None:
        """Receive the settlement of the current step.

        Args:
            result: Agent specific settlement, see ``docs/contracts.md``.
        """

        self._last_result = dict(result)
        self._last_price = float(result.get("price", self._last_price))
        self._on_update(result)

    def snapshot(self) -> dict[str, Any]:
        """Return the public state of the agent for logging and the UI."""

        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "type": self.agent_type,
        }

    # ------------------------------------------------------------------
    # Hooks for concrete agents
    # ------------------------------------------------------------------

    def _on_observe(self, obs: dict[str, Any]) -> None:
        """Interpret an observation. Subclasses override this hook."""

    def _on_update(self, result: dict[str, Any]) -> None:
        """Interpret a settlement. Subclasses override this hook."""


class MockAgent(BaseAgent):
    """Labelled orchestration-only agent for ``mode="mock"``.

    The mock mode is not used for experiments. This implementation exists so
    that the frozen constructor remains usable for smoke tests and never
    raises a placeholder exception.
    """

    def __init__(self, spec: Mapping[str, Any]) -> None:
        """Create the mock agent from a resolved specification."""

        self._spec = dict(spec)
        super().__init__(
            agent_id=str(spec["id"]),
            role=str(spec["role"]),
            agent_type=str(spec["type"]),
        )

    def _on_observe(self, obs: dict[str, Any]) -> None:
        environment = obs["environment"]
        if self.role == "producer":
            self._available_mw = float(environment["generation_mw"].get(self.agent_id, 0.0))
        elif self.role == "consumer":
            self._available_mw = float(environment["demand_mw"].get(self.agent_id, 0.0))
        else:
            self._available_mw = 0.0

    def decide(self, round: int) -> list[Order]:
        """Submit a simple order; this is not an experimental component."""

        quantity = float(getattr(self, "_available_mw", 0.0))
        if quantity <= 0.0:
            return []
        if self.role == "producer":
            price = float(self._spec.get("marginal_cost", 1.0)) * 1.2
            side = "sell"
            priority = 4
        elif self.role == "consumer":
            price = float(self._spec.get("max_price", 100.0))
            side = "buy"
            priority = {"hospital": 1, "residential": 2, "factory": 3}.get(self.agent_type, 3)
        else:
            return []
        return [
            Order(
                agent_id=self.agent_id,
                side=side,
                qty_mw=quantity,
                price=price,
                priority=priority,
                round=round,
            )
        ]

    def snapshot(self) -> dict[str, Any]:
        """Return the common snapshot plus mock availability."""

        payload = super().snapshot()
        payload["available_mw"] = float(getattr(self, "_available_mw", 0.0))
        return payload
