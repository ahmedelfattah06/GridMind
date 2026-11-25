"""Tests for tabular Q-learning and the training loop (Team C2)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ai.qlearning import (
    N_ACTIONS,
    N_STATES,
    QPolicy,
    TabularQAgent,
    period_bin,
    price_bin,
    soc_bin,
    state_from_observation,
    state_index,
)
from ai.train import TrainingPolicy, train_storage_policy


def test_state_discretisation_follows_the_guide() -> None:
    assert soc_bin(0.0) == 0
    assert soc_bin(3.99) == 0
    assert soc_bin(4.0) == 1
    assert soc_bin(19.9) == 4
    assert soc_bin(100.0) == 4

    assert price_bin(50.0, 100.0) == 0
    assert price_bin(100.0, 100.0) == 1
    assert price_bin(150.0, 100.0) == 2
    assert price_bin(10.0, 0.0) == 1

    assert period_bin(0) == 0
    assert period_bin(5) == 0
    assert period_bin(6) == 1
    assert period_bin(12) == 2
    assert period_bin(18) == 3
    assert period_bin(23) == 3


def test_state_index_covers_exactly_sixty_states() -> None:
    seen = {
        state_index(soc_mwh, price, 100.0, hour)
        for soc_mwh in (0.0, 4.0, 8.0, 12.0, 16.0)
        for price in (50.0, 100.0, 150.0)
        for hour in (0, 6, 12, 18)
    }
    assert min(seen) == 0
    assert max(seen) == N_STATES - 1
    assert len(seen) == N_STATES
    with pytest.raises(ValueError):
        state_index(0.0, 10.0, 10.0, 0, price_bins=4)


def test_state_from_observation_uses_own_agent_snapshot(config: dict[str, Any]) -> None:
    observation = {
        "hour": 12,
        "last_price": 50.0,
        "own_agent": {"capacity_mwh": 20.0, "soc_mwh": 8.0, "avg_price_24h": 100.0},
    }
    state = state_from_observation(observation, config)
    assert state == state_index(8.0, 50.0, 100.0, 12)


def test_epsilon_decays_linearly(config: dict[str, Any]) -> None:
    learner = TabularQAgent(config, seed=1)
    decay = int(config["qlearning"]["epsilon_decay_episodes"])
    assert learner.epsilon_for_episode(0) == pytest.approx(1.0)
    assert learner.epsilon_for_episode(decay) == pytest.approx(0.05)
    assert learner.epsilon_for_episode(decay * 2) == pytest.approx(0.05)
    with pytest.raises(ValueError):
        learner.epsilon_for_episode(-1)


def test_q_update_matches_the_tabular_rule(config: dict[str, Any]) -> None:
    learner = TabularQAgent(config, seed=2)
    learner.qtable[5, 1] = 2.0
    learner.qtable[6, 0] = 1.0
    learner.qtable[6, 2] = 3.0

    error = learner.update(5, 1, reward=4.0, next_state=6, done=False)
    target = 4.0 + learner.gamma * 3.0
    assert error == pytest.approx(target - 2.0)
    updated = 2.0 + learner.alpha * error
    assert learner.qtable[5, 1] == pytest.approx(updated)

    terminal_error = learner.update(5, 1, reward=4.0, next_state=6, done=True)
    assert terminal_error == pytest.approx(4.0 - updated)


def test_q_agent_acts_greedily_and_validates(config: dict[str, Any]) -> None:
    learner = TabularQAgent(config, seed=3)
    learner.qtable[10, 2] = 1.0
    assert learner.act(10) == 2
    assert learner.act(0) == 0
    with pytest.raises(ValueError):
        learner.act(N_STATES)
    with pytest.raises(ValueError):
        learner.act(0, epsilon=1.5)
    with pytest.raises(ValueError):
        learner.update(0, N_ACTIONS, 1.0, 0)
    with pytest.raises(ValueError):
        learner.update(0, 0, float("nan"), 0)


def test_qtable_round_trip(config: dict[str, Any], tmp_path: Any) -> None:
    learner = TabularQAgent(config, seed=4)
    learner.qtable[7, 1] = 0.5
    path = tmp_path / "qtable.npy"
    learner.save(path)

    restored = TabularQAgent(config, seed=4)
    restored.load(path)
    assert restored.qtable.shape == (N_STATES, N_ACTIONS)
    assert restored.qtable[7, 1] == pytest.approx(0.5)

    bad = tmp_path / "bad.npy"
    np.save(bad, np.zeros((3, 2)))
    with pytest.raises(ValueError, match="shape"):
        restored.load(bad)
    with pytest.raises(FileNotFoundError):
        restored.load(tmp_path / "missing.npy")


def test_q_policy_is_greedy_and_tracks_the_last_state(config: dict[str, Any]) -> None:
    learner = TabularQAgent(config, seed=5)
    observation = {
        "hour": 12,
        "last_price": 100.0,
        "own_agent": {"capacity_mwh": 20.0, "soc_mwh": 8.0, "avg_price_24h": 100.0},
    }
    expected_state = state_index(8.0, 100.0, 100.0, 12)
    learner.qtable[expected_state, 1] = 1.0
    policy = QPolicy(learner, config)
    assert policy.act(observation) == 1
    assert policy.last_state == expected_state


class _Battery:
    state_of_charge = 0.5


def test_training_policy_accumulates_reward_and_td_errors(config: dict[str, Any]) -> None:
    learner = TabularQAgent(config, seed=6)
    policy = TrainingPolicy(learner, config, epsilon=0.0)
    observation = {
        "hour": 0,
        "last_price": 100.0,
        "own_agent": {"capacity_mwh": 20.0, "soc_mwh": 10.0, "avg_price_24h": 0.0},
    }
    policy.act(observation)
    policy.update(
        {
            "price": 50.0,
            "bought_mw": 2.0,
            "sold_mw": 3.0,
            "system_unserved_mw": 4.0,
        },
        _Battery(),
    )
    expected = 50.0 * 3.0 - 50.0 * 2.0 - 0.5 * 5.0 - 0.5 * 4.0
    assert policy.episode_reward == pytest.approx(expected)

    policy.act({**observation, "hour": 1})
    assert policy.td_errors
    policy.end_episode()
    assert policy.td_errors


def test_training_loop_writes_qtable_and_curve(config: dict[str, Any], tmp_path: Any) -> None:
    qtable = tmp_path / "qtable.npy"
    curve_path = tmp_path / "learning_curve.csv"
    learner, curve = train_storage_policy(
        config,
        episodes=1,
        seed=0,
        output_path=qtable,
        curve_path=curve_path,
        verbose=False,
    )
    assert qtable.exists()
    assert learner.qtable.shape == (N_STATES, N_ACTIONS)
    assert not np.allclose(learner.qtable, 0.0)
    assert list(curve.columns) == [
        "episode",
        "mean_reward",
        "std_reward",
        "mean_td_error",
        "epsilon",
    ]
    assert len(curve) == 1
    assert (tmp_path / "training_metadata.json").exists()
