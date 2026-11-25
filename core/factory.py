"""Construction helpers for fully wired GridMind runs.

The frozen :class:`core.model.GridModel` deliberately receives its components
through dependency injection. This module is the single place that assembles a
complete run from the validated configuration:

* :class:`core.environment.Environment` (A2/A3),
* real consumer, producer and storage agents (B1/B2),
* the double auction and negotiation protocol (B3) for ``auction`` and
  ``auction_q``,
* the central LP market adapter (C1) for ``central``, ``central_6h`` and
  ``central_1h``,
* the learned storage policy (C2) for ``auction_q``.

Only the configuration and the main seed determine the assembled system, which
keeps runs reproducible and keeps the model free of construction logic.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Mapping

from agents.consumer import ConsumerAgent
from agents.producer import ProducerAgent
from agents.storage import RulePolicy, StorageAgent, StoragePolicy
from ai.central_lp import CentralMarketAdapter
from ai.qlearning import QPolicy, TabularQAgent
from core.config import (
    CENTRAL_MODES,
    PROJECT_ROOT,
    load_config,
    resolve_agent_specs,
    validate_config,
)
from core.environment import Environment
from core.model import GridModel
from market.auction import DoubleAuction
from market.negotiation import RaiseFactorNegotiation

DEFAULT_QTABLE_PATH = PROJECT_ROOT / "qtable.npy"

PolicyFactory = Callable[[Mapping[str, Any], Mapping[str, Any], int], StoragePolicy]


def default_fleet_counts(config: Mapping[str, Any]) -> dict[str, int]:
    """Return the configured count per consumer type and battery group."""

    consumers = {str(entry["type"]): int(entry["count"]) for entry in config["consumers"]}
    storage = int(sum(int(entry["count"]) for entry in config["storage"]))
    return {
        "hospital": consumers.get("hospital", 0),
        "residential": consumers.get("residential", 0),
        "factory": consumers.get("factory", 0),
        "battery": storage,
    }


def with_fleet(
    config: Mapping[str, Any],
    *,
    hospitals: int | None = None,
    residential: int | None = None,
    factories: int | None = None,
    batteries: int | None = None,
) -> dict[str, Any]:
    """Return a validated copy of ``config`` with a resized agent fleet.

    The dashboard uses this helper to rebuild a model when the user changes the
    number of agents. The official cap of 20 agents and the per-group minimum of
    one are still enforced by :func:`core.config.validate_config`.
    """

    updated = copy.deepcopy(dict(config))
    counts = {
        "hospital": hospitals,
        "residential": residential,
        "factory": factories,
    }
    for entry in updated["consumers"]:
        wanted = counts.get(str(entry["type"]))
        if wanted is not None:
            entry["count"] = int(wanted)
    if batteries is not None:
        if not updated["storage"]:
            raise ValueError("configuration defines no storage group")
        updated["storage"][0]["count"] = int(batteries)
    return validate_config(updated)


def build_agents(
    config: Mapping[str, Any],
    seed: int,
    *,
    qtable_path: str | Path | None = None,
    policy_factory: PolicyFactory | None = None,
) -> list[Any]:
    """Create the real agent fleet in deterministic configuration order.

    Args:
        config: Validated configuration.
        seed: Main simulation seed.
        qtable_path: Optional path to a trained Q-table. When given, every
            storage agent receives a Q-learning policy backed by one shared
            learner, which is what ``auction_q`` uses.
        policy_factory: Optional callable ``(spec, config, seed) -> policy`` used
            by the training loop to inject exploratory policies.

    Raises:
        FileNotFoundError: If ``qtable_path`` is given but the file is missing.
    """

    if qtable_path is not None and policy_factory is not None:
        raise ValueError("pass either qtable_path or policy_factory, not both")

    learner: TabularQAgent | None = None
    if qtable_path is not None:
        path = Path(qtable_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Q-table not found: {path}. Train the storage policy first with "
                "`python -m ai.train`."
            )
        learner = TabularQAgent(config, seed)
        learner.load(path)

    agents: list[Any] = []
    for spec in resolve_agent_specs(config):
        role = str(spec["role"])
        if role == "producer":
            agents.append(ProducerAgent(spec, config))
        elif role == "consumer":
            agents.append(ConsumerAgent(spec, config, seed=seed))
        elif role == "storage":
            if policy_factory is not None:
                policy = policy_factory(spec, config, seed)
            elif learner is not None:
                policy = QPolicy(learner, config)
            else:
                policy = RulePolicy(config)
            agents.append(StorageAgent(spec, config, seed=seed, policy=policy))
        else:  # pragma: no cover - validated configuration cannot reach this
            raise ValueError(f"unsupported agent role {role!r}")
    return agents


def build_market(
    config: Mapping[str, Any],
    mode: str,
    environment: Environment,
) -> Any:
    """Create the market implementation required by ``mode``."""

    if mode in CENTRAL_MODES:
        interval = 1 if mode == "central_1h" else int(config["simulation"]["horizon"])
        return CentralMarketAdapter(config, environment=environment, interval=interval)
    return DoubleAuction(config)


def build_model(
    config: Mapping[str, Any],
    seed: int,
    mode: str,
    scenario: str = "normal",
    *,
    qtable_path: str | Path | None = None,
    policy_factory: PolicyFactory | None = None,
) -> GridModel:
    """Assemble and return a fully wired :class:`core.model.GridModel`.

    Args:
        config: Validated configuration. Missing validation is performed by the
            model constructor and the component builders.
        seed: Main simulation seed.
        mode: Official comparison system id, ``central`` or ``mock``.
        scenario: Official scenario key or display name.
        qtable_path: Path to ``qtable.npy``. Required for ``auction_q``; a
            missing artefact raises a clear :class:`FileNotFoundError`.
        policy_factory: Optional storage policy factory, used by training.

    Returns:
        A runnable model. Call :meth:`GridModel.step` until the clock finishes.
    """

    environment = Environment(config, seed)
    if mode == "auction_q" and qtable_path is None and policy_factory is None:
        qtable_path = DEFAULT_QTABLE_PATH
    agents = build_agents(
        config,
        seed,
        qtable_path=qtable_path,
        policy_factory=policy_factory,
    )
    market = build_market(config, mode, environment)
    negotiation = None if mode in CENTRAL_MODES else RaiseFactorNegotiation(config)
    return GridModel(
        config,
        seed,
        mode=mode,
        scenario=scenario,
        environment=environment,
        agents=agents,
        market=market,
        negotiation=negotiation,
    )


def load_default_config() -> dict[str, Any]:
    """Load and validate the repository configuration."""

    return load_config()


__all__ = [
    "DEFAULT_QTABLE_PATH",
    "PolicyFactory",
    "build_agents",
    "build_market",
    "build_model",
    "default_fleet_counts",
    "load_default_config",
    "with_fleet",
]
