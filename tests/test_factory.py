"""Tests for the model factory and agent fleet resizing."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from ai.central_lp import CentralMarketAdapter
from ai.qlearning import N_ACTIONS, N_STATES, QPolicy, TabularQAgent
from core.config import ConfigError
from core.factory import (
    build_agents,
    build_market,
    build_model,
    default_fleet_counts,
    with_fleet,
)
from market.auction import DoubleAuction
from market.negotiation import RaiseFactorNegotiation


def test_default_fleet_matches_the_official_design(config: dict[str, Any]) -> None:
    assert default_fleet_counts(config) == {
        "hospital": 2,
        "residential": 4,
        "factory": 3,
        "battery": 2,
    }
    agents = build_agents(config, seed=0)
    assert len(agents) == 15
    roles = [agent.role for agent in agents]
    assert roles.count("producer") == 4
    assert roles.count("consumer") == 9
    assert roles.count("storage") == 2


def test_with_fleet_resizes_and_stays_within_the_cap(config: dict[str, Any]) -> None:
    resized = with_fleet(config, hospitals=1, residential=2, factories=1, batteries=1)
    agents = build_agents(resized, seed=0)
    assert len(agents) == 4 + 4 + 1
    assert [agent.agent_type for agent in agents].count("hospital") == 1

    with pytest.raises(ConfigError):
        with_fleet(config, hospitals=10, residential=10, factories=10, batteries=10)


def test_build_model_wires_official_modes(config: dict[str, Any]) -> None:
    auction = build_model(config, seed=1, mode="auction")
    assert isinstance(auction._market, DoubleAuction)  # noqa: SLF001
    assert isinstance(auction._negotiation, RaiseFactorNegotiation)  # noqa: SLF001
    assert len(auction.agents) == 15

    six_hour = build_model(config, seed=1, mode="central_6h")
    one_hour = build_model(config, seed=1, mode="central_1h")
    generic = build_model(config, seed=1, mode="central")
    assert isinstance(six_hour._market, CentralMarketAdapter)  # noqa: SLF001
    assert six_hour._market.interval == 6  # noqa: SLF001
    assert one_hour._market.interval == 1  # noqa: SLF001
    assert generic._market.interval == 6  # noqa: SLF001
    assert six_hour._negotiation is None  # noqa: SLF001


def test_build_market_dispatches_on_mode(config: dict[str, Any]) -> None:
    from core.environment import Environment

    environment = Environment(config, seed=0)
    assert isinstance(build_market(config, "auction", environment), DoubleAuction)
    adapter = build_market(config, "central_1h", environment)
    assert isinstance(adapter, CentralMarketAdapter)
    assert adapter.interval == 1


def test_auction_q_loads_a_shared_qtable(config: dict[str, Any], tmp_path: Any) -> None:
    learner = TabularQAgent(config, seed=0)
    learner.qtable[3, 1] = 0.75
    path = tmp_path / "qtable.npy"
    learner.save(path)

    agents = build_agents(config, seed=0, qtable_path=path)
    storage = [agent for agent in agents if agent.role == "storage"]
    assert storage
    assert all(isinstance(agent.policy, QPolicy) for agent in storage)
    assert storage[0].policy.learner.qtable.shape == (N_STATES, N_ACTIONS)
    assert storage[0].policy.learner.qtable[3, 1] == pytest.approx(0.75)

    with pytest.raises(FileNotFoundError, match="python -m ai.train"):
        build_agents(config, seed=0, qtable_path=tmp_path / "missing.npy")


def test_build_agents_rejects_conflicting_policy_sources(
    config: dict[str, Any], tmp_path: Any
) -> None:
    path = tmp_path / "qtable.npy"
    np.save(path, np.zeros((N_STATES, N_ACTIONS)))
    with pytest.raises(ValueError, match="either qtable_path or policy_factory"):
        build_agents(config, seed=0, qtable_path=path, policy_factory=lambda *args: None)
