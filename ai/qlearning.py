"""Tabular Q-learning for the storage agent (Team C2).

The state discretisation follows section 7.3 of the project guide:

* SoC bin: five equal bins over the configured battery capacity;
* price bin: cheap (price < 0.85 * 24h mean), normal, expensive (> 1.15 * mean);
* period bin: night, morning, midday, evening (four six-hour blocks).

The flat state index is ``(soc_bin * price_bins + price_bin) * periods + period``
and therefore covers exactly 60 states. Only tabular Q-learning is used; no
deep-reinforcement-learning dependency is introduced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np

from agents.storage import EPSILON, StoragePolicy
from core.config import derive_rng

N_ACTIONS = 3
DEFAULT_SOC_BINS = 5
DEFAULT_PRICE_BINS = 3
DEFAULT_PERIODS = 4
N_STATES = DEFAULT_SOC_BINS * DEFAULT_PRICE_BINS * DEFAULT_PERIODS
QLEARNING_STREAM = 7_000


def soc_bin(soc_mwh: float, capacity_mwh: float = 20.0, bins: int = DEFAULT_SOC_BINS) -> int:
    """Return the SoC bin index for an energy level in MWh."""

    if bins < 1:
        raise ValueError("bins must be positive")
    capacity = max(float(capacity_mwh), EPSILON)
    width = capacity / bins
    index = int(max(0.0, float(soc_mwh)) // width)
    return min(bins - 1, max(0, index))


def price_bin(
    last_price: float,
    avg_price_24h: float,
    low_ratio: float = 0.85,
    high_ratio: float = 1.15,
) -> int:
    """Return 0 (cheap), 1 (normal) or 2 (expensive) for a price observation."""

    average = float(avg_price_24h)
    if average <= EPSILON:
        return 1
    ratio = float(last_price) / average
    if ratio < low_ratio:
        return 0
    if ratio > high_ratio:
        return 2
    return 1


def period_bin(hour: int, periods: int = DEFAULT_PERIODS) -> int:
    """Return the six-hour period index (night, morning, midday, evening)."""

    if periods < 1:
        raise ValueError("periods must be positive")
    block = 24 // periods
    return min(periods - 1, max(0, int(hour) // block))


def state_index(
    soc_mwh: float,
    last_price: float,
    avg_price_24h: float,
    hour: int,
    capacity_mwh: float = 20.0,
    *,
    low_ratio: float = 0.85,
    high_ratio: float = 1.15,
    soc_bins: int = DEFAULT_SOC_BINS,
    price_bins: int = DEFAULT_PRICE_BINS,
    periods: int = DEFAULT_PERIODS,
) -> int:
    """Return the flat discrete state index in ``[0, N_STATES)``."""

    if price_bins != DEFAULT_PRICE_BINS:
        # The price discretisation is fixed at three categories by design.
        raise ValueError("price_bins must be 3")
    si = soc_bin(soc_mwh, capacity_mwh, soc_bins)
    pi = price_bin(last_price, avg_price_24h, low_ratio, high_ratio)
    ti = period_bin(hour, periods)
    return int((si * price_bins + pi) * periods + ti)


def state_from_observation(
    obs: Mapping[str, Any],
    config: Mapping[str, Any],
) -> int:
    """Compute the discrete state index from a model observation."""

    own = obs.get("own_agent", {}) if isinstance(obs, Mapping) else {}
    qconfig = config.get("qlearning", {}) if isinstance(config, Mapping) else {}
    capacity = float(own.get("capacity_mwh", 20.0))
    soc_mwh = float(own.get("soc_mwh", float(own.get("soc", 0.0)) * capacity))
    average = float(own.get("avg_price_24h", 0.0))
    policy = config.get("storage_policy", {}) if isinstance(config, Mapping) else {}
    return state_index(
        soc_mwh,
        float(obs.get("last_price", 0.0)),
        average,
        int(obs.get("hour", 0)),
        capacity,
        low_ratio=float(policy.get("low_price_ratio", 0.85)),
        high_ratio=float(policy.get("high_price_ratio", 1.15)),
        soc_bins=int(qconfig.get("soc_bins", DEFAULT_SOC_BINS)),
        periods=int(qconfig.get("periods", DEFAULT_PERIODS)),
    )


class TabularQAgent:
    """Tabular Q-learning policy for one storage agent."""

    def __init__(self, config: Mapping[str, Any], seed: int) -> None:
        """Create the learner.

        Args:
            config: Full validated configuration.
            seed: Main simulation seed, used by the exploration policy.
        """

        self._config = config
        self._seed = int(seed)
        self._settings = dict(config.get("qlearning", {}))
        self._alpha = float(self._settings.get("alpha", 0.1))
        self._gamma = float(self._settings.get("gamma", 0.95))
        self._epsilon_start = float(self._settings.get("epsilon_start", 1.0))
        self._epsilon_end = float(self._settings.get("epsilon_end", 0.05))
        self._decay_episodes = int(self._settings.get("epsilon_decay_episodes", 1500))
        self._rng = derive_rng(seed, QLEARNING_STREAM)
        self._qtable = np.zeros((N_STATES, N_ACTIONS), dtype=float)

    @property
    def qtable(self) -> np.ndarray:
        """The learned Q-table, shape ``(60, 3)``."""

        return self._qtable

    @property
    def alpha(self) -> float:
        """Learning rate."""

        return self._alpha

    @property
    def gamma(self) -> float:
        """Discount factor."""

        return self._gamma

    def epsilon_for_episode(self, episode: int) -> float:
        """Linear epsilon schedule from ``epsilon_start`` to ``epsilon_end``."""

        if isinstance(episode, bool) or not isinstance(episode, int) or episode < 0:
            raise ValueError("episode must be a non-negative integer")
        if self._decay_episodes <= 0:
            return self._epsilon_end
        fraction = min(1.0, float(episode) / float(self._decay_episodes))
        return float(
            self._epsilon_start + fraction * (self._epsilon_end - self._epsilon_start)
        )

    def act(self, state: int, epsilon: float = 0.0) -> int:
        """Select an action with epsilon-greedy exploration.

        Args:
            state: Discrete state index.
            epsilon: Exploration probability in ``[0, 1]``.

        Returns:
            Action ``0`` (wait), ``1`` (charge) or ``2`` (discharge).
        """

        self._validate_state(state)
        if not 0.0 <= epsilon <= 1.0:
            raise ValueError(f"epsilon must lie in [0, 1], got {epsilon!r}")
        if epsilon > 0.0 and float(self._rng.random()) < epsilon:
            return int(self._rng.integers(0, N_ACTIONS))
        return int(np.argmax(self._qtable[state]))

    def update(
        self,
        state: int,
        action: int,
        reward: float,
        next_state: int,
        done: bool = False,
    ) -> float:
        """Apply the tabular Q-learning update rule.

        Returns:
            The temporal-difference error that was applied.
        """

        self._validate_state(state)
        self._validate_state(next_state)
        if isinstance(action, bool) or not isinstance(action, int) or not 0 <= action < N_ACTIONS:
            raise ValueError(f"action must lie in [0, {N_ACTIONS - 1}], got {action!r}")
        if not np.isfinite(float(reward)):
            raise ValueError(f"reward must be finite, got {reward!r}")
        best_next = 0.0 if done else float(np.max(self._qtable[next_state]))
        target = float(reward) + self._gamma * best_next
        error = target - float(self._qtable[state, action])
        self._qtable[state, action] += self._alpha * error
        return float(error)

    def save(self, path: str | Path) -> Path:
        """Persist the learned Q-table as ``.npy``."""

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.save(destination, self._qtable)
        return destination

    def load(self, path: str | Path) -> None:
        """Load a persisted Q-table, validating its shape."""

        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"Q-table not found: {source}")
        table = np.load(source, allow_pickle=False)
        if table.shape != (N_STATES, N_ACTIONS):
            raise ValueError(
                f"Q-table must have shape {(N_STATES, N_ACTIONS)}, got {table.shape}"
            )
        self._qtable = np.asarray(table, dtype=float)

    def _validate_state(self, state: int) -> None:
        if isinstance(state, bool) or not isinstance(state, int) or not 0 <= state < N_STATES:
            raise ValueError(f"state must lie in [0, {N_STATES - 1}], got {state!r}")


class QPolicy(StoragePolicy):
    """Storage policy backed by a learned :class:`TabularQAgent`."""

    def __init__(self, learner: TabularQAgent, config: Mapping[str, Any]) -> None:
        """Wrap a learner as a storage policy."""

        self._learner = learner
        self._config = config
        self._last_state: int | None = None

    @classmethod
    def from_file(
        cls,
        config: Mapping[str, Any],
        path: str | Path,
        seed: int = 0,
    ) -> "QPolicy":
        """Create a greedy policy from a persisted Q-table."""

        learner = TabularQAgent(config, seed)
        learner.load(path)
        return cls(learner, config)

    @property
    def learner(self) -> TabularQAgent:
        """The wrapped learner, exposed for tests and the dashboard."""

        return self._learner

    @property
    def last_state(self) -> int | None:
        """Most recently evaluated state index."""

        return self._last_state

    def act(self, obs: dict[str, Any]) -> int:
        """Select the greedy action for the discretised observation."""

        state = state_from_observation(obs, self._config)
        self._last_state = state
        return self._learner.act(state, 0.0)


__all__ = [
    "N_ACTIONS",
    "N_STATES",
    "QPolicy",
    "TabularQAgent",
    "period_bin",
    "price_bin",
    "soc_bin",
    "state_from_observation",
    "state_index",
]
