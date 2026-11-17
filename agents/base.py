"""Base agent interface (Team B1) - interface skeleton.

Owner: B1 (Consumer Agents and Base Agent).
Status: TODO. No agent behaviour is implemented in this skeleton.

Responsibilities to implement:

* ``observe(obs)``: consume the observation documented in ``docs/contracts.md``,
* ``decide(round)``: return the orders of one negotiation round,
* ``update(result)``: consume the settlement of the step,
* ``snapshot()``: expose the public agent state for logging and the UI.

The interface is frozen in ``docs/contracts.md`` (section "Agent contract").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from market.orders import Order


class BaseAgent(ABC):
    """Common contract for every GridMind agent.

    The constructor only stores the identity fields of the frozen contract so
    that subclasses remain constructible. Agent state and behaviour belong to
    the owning team.
    """

    def __init__(self, agent_id: str, role: str, agent_type: str) -> None:
        """Create the agent.

        Args:
            agent_id: Unique agent identifier, for example ``"factory_1"``.
            role: ``"consumer"``, ``"producer"`` or ``"storage"``.
            agent_type: Concrete type, for example ``"hospital"`` or ``"solar"``.

        TODO(B1): define the validation rules and the state initialisation of
        the base agent.
        """

        self._agent_id = agent_id
        self._role = role
        self._agent_type = agent_type

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

    def observe(self, obs: dict[str, Any]) -> None:
        """Receive the observation of the current step.

        Args:
            obs: Model observation, see ``docs/contracts.md``.

        TODO(B1): store and interpret the observation.
        """

        raise NotImplementedError("TODO(B1): implement BaseAgent.observe")

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

        TODO(B1): store and interpret the settlement.
        """

        raise NotImplementedError("TODO(B1): implement BaseAgent.update")

    def snapshot(self) -> dict[str, Any]:
        """Return the public state of the agent for logging and the UI.

        TODO(B1): return at least ``agent_id``, ``role`` and ``type``.
        """

        raise NotImplementedError("TODO(B1): implement BaseAgent.snapshot")


class MockAgent(BaseAgent):
    """Removed orchestration stub, kept only for import compatibility.

    ``core/model.py`` imports this symbol. The bootstrap mock implemented a
    placeholder bidding policy, which the skeleton phase does not allow. Team
    B must supply real agents through dependency injection instead.

    TODO(B1): delete this class once ``GridModel`` no longer imports it, or
    replace it with a real agent implementation.
    """

    def __init__(self, spec: Mapping[str, Any]) -> None:
        raise NotImplementedError(
            "TODO(B1): MockAgent was removed in the skeleton phase; "
            "inject real agents via GridModel(..., agents=[...])"
        )

    def decide(self, round: int) -> list[Order]:
        """Not implemented; see :class:`BaseAgent`."""

        raise NotImplementedError("TODO(B1): implement real agent decisions")
