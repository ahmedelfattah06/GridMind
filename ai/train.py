"""Training entry point for the tabular Q-learning storage policy (Team C2).

The training loop follows section 7.3 of the project guide:

* 2000 episodes of 168 hourly steps,
* each episode draws an official scenario and a training seed from 1000 upwards,
* all other agents keep their fixed rule-based behaviour,
* epsilon decays linearly from 1.0 to 0.05 over the first 1500 episodes,
* the reward is ``revenue - cost - 0.5 * throughput - 0.5 * UE * 1[SoC < 1]``,
* the learned table is saved as ``qtable.npy`` with shape ``(60, 3)``.

Usage::

    python -m ai.train
    python -m ai.train --episodes 50 --output results/quick_qtable.npy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from agents.storage import StoragePolicy
from ai.qlearning import QLEARNING_STREAM, TabularQAgent, state_from_observation
from core.config import OFFICIAL_SCENARIOS, PROJECT_ROOT, derive_rng, load_config
from core.factory import DEFAULT_QTABLE_PATH, build_model

TRAINING_STREAM = QLEARNING_STREAM + 1
CURVE_WINDOW = 50


class TrainingPolicy(StoragePolicy):
    """Exploratory storage policy that feeds one shared tabular learner."""

    def __init__(
        self,
        learner: TabularQAgent,
        config: Mapping[str, Any],
        epsilon: float,
    ) -> None:
        """Create a per-battery policy for one training episode."""

        self._learner = learner
        self._config = config
        self._epsilon = float(epsilon)
        self._pending_state: int | None = None
        self._pending_action: int | None = None
        self._pending_reward = 0.0
        self._episode_reward = 0.0
        self._td_errors: list[float] = []

    @property
    def episode_reward(self) -> float:
        """Cumulative reward collected by this battery in the episode."""

        return float(self._episode_reward)

    @property
    def td_errors(self) -> list[float]:
        """Absolute temporal-difference errors observed by this policy."""

        return list(self._td_errors)

    def act(self, obs: dict[str, Any]) -> int:
        """Return an epsilon-greedy action and close the previous transition."""

        state = state_from_observation(obs, self._config)
        if self._pending_state is not None and self._pending_action is not None:
            error = self._learner.update(
                self._pending_state,
                self._pending_action,
                self._pending_reward,
                state,
                done=False,
            )
            self._td_errors.append(abs(float(error)))
        action = self._learner.act(state, self._epsilon)
        self._pending_state = int(state)
        self._pending_action = int(action)
        self._pending_reward = 0.0
        return int(action)

    def update(self, result: dict[str, Any], agent: Any) -> None:
        """Accumulate the immediate reward of the executed storage action."""

        if self._pending_state is None:
            return
        price = float(result.get("price", 0.0))
        bought = float(result.get("bought_mw", 0.0))
        sold = float(result.get("sold_mw", 0.0))
        system_unserved = float(result.get("system_unserved_mw", 0.0))
        throughput = bought + sold
        reward = price * sold - price * bought - 0.5 * throughput
        soc = float(getattr(agent, "state_of_charge", 1.0))
        if soc < 1.0:
            reward -= 0.5 * system_unserved
        self._pending_reward += float(reward)
        self._episode_reward += float(reward)

    def end_episode(self) -> None:
        """Apply the final transition with a terminal next state."""

        if self._pending_state is not None and self._pending_action is not None:
            error = self._learner.update(
                self._pending_state,
                self._pending_action,
                self._pending_reward,
                self._pending_state,
                done=True,
            )
            self._td_errors.append(abs(float(error)))
        self._pending_state = None
        self._pending_action = None
        self._pending_reward = 0.0


def train_storage_policy(
    config: Mapping[str, Any],
    episodes: int,
    seed: int = 0,
    *,
    output_path: str | Path | None = None,
    curve_path: str | Path | None = None,
    verbose: bool = True,
) -> tuple[TabularQAgent, pd.DataFrame]:
    """Train the shared storage Q-table.

    Args:
        config: Full validated configuration.
        episodes: Number of training episodes.
        seed: Learning seed. Episode seeds are ``1000 + episode`` according to
            the official design; ``seed`` only seeds the scenario schedule and
            the exploration generator.
        output_path: Destination of the Q-table. Defaults to ``qtable.npy`` in
            the project root.
        curve_path: Destination of the learning curve CSV. Defaults to
            ``results/learning_curve.csv``.
        verbose: Whether to print progress every :data:`CURVE_WINDOW` episodes.

    Returns:
        The trained learner and the learning-curve data frame.
    """

    if isinstance(episodes, bool) or not isinstance(episodes, int) or episodes < 1:
        raise ValueError("episodes must be a positive integer")
    settings = dict(config.get("qlearning", {}))
    seed_start = int(settings.get("training_seed_start", 1000))
    learner = TabularQAgent(config, seed)
    scenario_rng = derive_rng(int(seed) + seed_start, TRAINING_STREAM)
    destination = Path(output_path) if output_path is not None else DEFAULT_QTABLE_PATH
    curve_destination = (
        Path(curve_path) if curve_path is not None else PROJECT_ROOT / "results" / "learning_curve.csv"
    )

    rewards: list[float] = []
    td_error_means: list[float] = []
    for episode in range(episodes):
        epsilon = learner.epsilon_for_episode(episode)
        scenario = OFFICIAL_SCENARIOS[int(scenario_rng.integers(0, len(OFFICIAL_SCENARIOS)))]
        policies: list[TrainingPolicy] = []

        def policy_factory(
            spec: Mapping[str, Any],
            agent_config: Mapping[str, Any],
            agent_seed: int,
        ) -> StoragePolicy:
            del spec, agent_seed
            policy = TrainingPolicy(learner, agent_config, epsilon)
            policies.append(policy)
            return policy

        model = build_model(
            config,
            seed_start + episode,
            mode="auction",
            scenario=scenario,
            policy_factory=policy_factory,
        )
        while not model.clock.is_finished:
            model.step()
        for policy in policies:
            policy.end_episode()

        rewards.append(float(sum(policy.episode_reward for policy in policies)))
        errors = [error for policy in policies for error in policy.td_errors]
        td_error_means.append(float(np.mean(errors)) if errors else 0.0)
        if verbose and ((episode + 1) % CURVE_WINDOW == 0 or episode == 0):
            window = rewards[-CURVE_WINDOW:]
            print(
                f"episode {episode + 1:5d}/{episodes} "
                f"epsilon={epsilon:.3f} "
                f"mean_reward={np.mean(window):9.3f} "
                f"td_error={td_error_means[-1]:.4f}",
                file=sys.stderr,
            )

    learner.save(destination)
    curve = _build_curve(rewards, td_error_means, learner, episodes)
    curve_destination.parent.mkdir(parents=True, exist_ok=True)
    curve.to_csv(curve_destination, index=False)

    metadata = {
        "episodes": int(episodes),
        "seed": int(seed),
        "alpha": learner.alpha,
        "gamma": learner.gamma,
        "epsilon_start": float(settings.get("epsilon_start", 1.0)),
        "epsilon_end": float(settings.get("epsilon_end", 0.05)),
        "epsilon_decay_episodes": int(settings.get("epsilon_decay_episodes", 1500)),
        "qtable": str(destination),
        "qtable_shape": list(learner.qtable.shape),
        "learning_curve": str(curve_destination),
        "final_mean_reward": float(np.mean(rewards[-CURVE_WINDOW:])) if rewards else 0.0,
    }
    metadata_path = curve_destination.with_name("training_metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return learner, curve


def _build_curve(
    rewards: Sequence[float],
    td_errors: Sequence[float],
    learner: TabularQAgent,
    episodes: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for start in range(0, episodes, CURVE_WINDOW):
        stop = min(episodes, start + CURVE_WINDOW)
        window = list(rewards[start:stop])
        rows.append(
            {
                "episode": stop,
                "mean_reward": float(np.mean(window)) if window else 0.0,
                "std_reward": float(np.std(window)) if window else 0.0,
                "mean_td_error": float(np.mean(list(td_errors[start:stop]))),
                "epsilon": learner.epsilon_for_episode(stop - 1),
            }
        )
    return pd.DataFrame(rows)


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser for ``python -m ai.train``."""

    parser = argparse.ArgumentParser(
        prog="python -m ai.train",
        description="Train the GridMind tabular Q-learning storage policy.",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Number of episodes (default: qlearning.episodes from the config).",
    )
    parser.add_argument("--seed", type=int, default=0, help="Learning seed (default: 0).")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Q-table destination (default: qtable.npy in the project root).",
    )
    parser.add_argument(
        "--curve",
        type=Path,
        default=None,
        help="Learning-curve CSV destination (default: results/learning_curve.csv).",
    )
    parser.add_argument("--config", type=Path, default=None, help="Alternative config YAML.")
    parser.add_argument("--quiet", action="store_true", help="Disable progress output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point for training."""

    args = build_parser().parse_args(argv)
    config = load_config(args.config) if args.config is not None else load_config()
    episodes = args.episodes
    if episodes is None:
        episodes = int(config.get("qlearning", {}).get("episodes", 2000))
    learner, curve = train_storage_policy(
        config,
        episodes=episodes,
        seed=args.seed,
        output_path=args.output,
        curve_path=args.curve,
        verbose=not args.quiet,
    )
    print(
        f"Saved Q-table {learner.qtable.shape} to "
        f"{args.output or DEFAULT_QTABLE_PATH} and {len(curve)} curve points."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
