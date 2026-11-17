"""Tabular Q-learning for the storage agent (Team C2) - interface skeleton.

Owner: C2 (Q-Learning).
Status: TODO. No learning algorithm, state discretisation or policy is
implemented in this skeleton.

Only tabular Q-learning is allowed by the project specification. No deep
reinforcement learning, DQN, PPO or multi-agent RL framework may be introduced.
The open design parameters are recorded as PD-08 in ``docs/decision_log.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


class TabularQAgent:
    """Tabular Q-learning policy for one storage agent (Team C2)."""

    def __init__(self, config: Mapping[str, Any], seed: int) -> None:
        """Create the learner.

        Args:
            config: Full validated configuration.
            seed: Main simulation seed, used by the exploration policy.

        TODO(C2): define the state and action discretisation and the Q-table.
        """

        self._config = config
        self._seed = seed

    def act(self, state: tuple[Any, ...]) -> int:
        """Select a discrete action for the given state.

        Raises:
            NotImplementedError: Always, until Team C2 implements the policy.

        TODO(C2): implement epsilon-greedy action selection.
        """

        raise NotImplementedError("TODO(C2): TabularQAgent.act is not implemented")

    def update(
        self,
        state: tuple[Any, ...],
        action: int,
        reward: float,
        next_state: tuple[Any, ...],
        done: bool = False,
    ) -> None:
        """Apply the Q-learning update rule.

        Raises:
            NotImplementedError: Always, until Team C2 implements the policy.

        TODO(C2): implement the tabular update rule.
        """

        raise NotImplementedError("TODO(C2): TabularQAgent.update is not implemented")

    def save(self, path: str | Path) -> Path:
        """Persist the learned Q-table.

        Raises:
            NotImplementedError: Always, until Team C2 implements persistence.

        TODO(C2): implement persistence.
        """

        raise NotImplementedError("TODO(C2): TabularQAgent.save is not implemented")

    def load(self, path: str | Path) -> None:
        """Load a persisted Q-table.

        Raises:
            NotImplementedError: Always, until Team C2 implements persistence.

        TODO(C2): implement persistence.
        """

        raise NotImplementedError("TODO(C2): TabularQAgent.load is not implemented")
