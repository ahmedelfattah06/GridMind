"""Configuration loading, validation and shared seed derivation for GridMind.

The configuration is the single source of truth for every tunable parameter of
the simulation. :func:`load_config` reads ``config/default.yaml`` and
``config/scenarios.yaml`` and :func:`validate_config` enforces the official
project boundaries before any simulation object is created.

Typical usage::

    config = load_config()
    specs = resolve_agent_specs(config)
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"
DEFAULT_SCENARIOS_PATH = PROJECT_ROOT / "config" / "scenarios.yaml"

# Official specification constants. They are duplicated here on purpose so that
# an invalid configuration fails loudly instead of silently changing the study.
REQUIRED_SIMULATION_STEPS = 168
MAX_NEGOTIATION_ROUNDS = 3
REQUIRED_SEED_COUNT = 30
MAX_AGENT_COUNT = 20
DEFAULT_AGENT_COUNT = 15
OFFICIAL_SYSTEMS: tuple[str, ...] = ("central_6h", "central_1h", "auction", "auction_q")
OFFICIAL_SCENARIOS: tuple[str, ...] = (
    "normal",
    "plant_outage",
    "demand_spike",
    "weather_shift",
    "combined",
)
PRODUCER_TYPES: tuple[str, ...] = ("solar", "wind", "thermal", "peaker")
CONSUMER_TYPES: tuple[str, ...] = ("hospital", "residential", "factory")
STORAGE_TYPES: tuple[str, ...] = ("battery",)
VOLL_KEYS: tuple[str, ...] = CONSUMER_TYPES
MAX_PRICE_KEYS: tuple[str, ...] = (*CONSUMER_TYPES, "flex")

# Execution modes understood by :class:`core.model.GridModel`.
#
# ``central`` is the generic central-planning mode required by the A1
# specification ("mode='central'"). The official experiment design additionally
# distinguishes the replanning interval as ``central_6h`` and ``central_1h``.
# All three delegate the actual LP to the injected C1 adapter; ``GridModel``
# never contains planning logic.
MODE_AUCTION = "auction"
MODE_CENTRAL = "central"
CENTRAL_MODES: tuple[str, ...] = ("central", "central_6h", "central_1h")
AUCTION_MODES: tuple[str, ...] = ("auction", "auction_q")

# "mock" is orchestration-only and must never be used to produce experimental
# results. It is kept for the frozen constructor signature (see PD-15).
MOCK_MODE = "mock"
SUPPORTED_MODES: tuple[str, ...] = (*OFFICIAL_SYSTEMS, MODE_CENTRAL, MOCK_MODE)

# Deterministic random streams. Each independent component owns one index so
# that adding a new component never shifts the random draws of another one.
STREAM_WEATHER_CLOUD = 0
STREAM_WEATHER_WIND = 1
STREAM_WEATHER_TEMPERATURE = 2
STREAM_DEMAND = 100
STREAM_AGENT_BASE = 1_000
AGENT_STREAM_RANGE = 1_000_000

REQUIRED_SECTIONS: tuple[str, ...] = (
    "project",
    "simulation",
    "market",
    "voll",
    "max_prices",
    "producers",
    "consumers",
    "storage",
    "environment",
    "experiments",
    "scenarios",
)


class ConfigError(ValueError):
    """Raised when the GridMind configuration is missing or invalid."""


def derive_rng(seed: int, stream: int) -> np.random.Generator:
    """Create an independent, reproducible random generator.

    Args:
        seed: Main simulation seed. Must be a non-negative integer.
        stream: Stream identifier owned by a single component (see the
            ``STREAM_*`` constants). Different streams never share draws.

    Returns:
        A NumPy generator seeded from ``SeedSequence([seed, stream])``.
    """

    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    if isinstance(stream, bool) or not isinstance(stream, int) or stream < 0:
        raise ValueError(f"stream must be a non-negative integer, got {stream!r}")
    return np.random.default_rng(np.random.SeedSequence([seed, stream]))


def agent_stream_index(agent_id: str) -> int:
    """Return the stable random-stream index owned by one agent.

    The index is derived from the agent id with a cryptographic digest instead
    of an ordinal position. Consequently, adding, removing or reordering agents
    never shifts another agent's random stream.

    Args:
        agent_id: Stable agent identifier, for example ``"hospital_1"``.

    Returns:
        A non-negative stream index in the agent range.

    Raises:
        ValueError: If ``agent_id`` is not a non-empty string.
    """

    if not isinstance(agent_id, str) or not agent_id.strip():
        raise ValueError(f"agent_id must be a non-empty string, got {agent_id!r}")
    digest = hashlib.blake2s(agent_id.encode("utf-8"), digest_size=8).digest()
    return STREAM_AGENT_BASE + int.from_bytes(digest, "big") % AGENT_STREAM_RANGE


def derive_agent_rng(seed: int, agent_id: str) -> np.random.Generator:
    """Create the independent random generator owned by one agent.

    Teams B1, B2 and C2 should use this helper instead of Python's global
    ``random`` module or the global NumPy random state. Random consumption of
    one agent never changes the sequence of another agent.

    Args:
        seed: Main simulation seed.
        agent_id: Stable agent identifier.

    Returns:
        A NumPy generator seeded from the agent's own stream index.

    Raises:
        ValueError: If ``seed`` or ``agent_id`` is invalid.
    """

    return derive_rng(seed, agent_stream_index(agent_id))


def load_config(
    path: str | Path | None = None,
    scenarios_path: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate the GridMind configuration.

    Args:
        path: Optional path to the main YAML file. Defaults to
            ``config/default.yaml``.
        scenarios_path: Optional path to the scenario catalogue. Defaults to
            ``config/scenarios.yaml``.

    Returns:
        A validated configuration dictionary. Scenario definitions are exposed
        under the ``"scenarios"`` key so a single object can be handed to the
        model.

    Raises:
        ConfigError: If a file is missing, empty or does not validate.
    """

    main_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    scenario_file = Path(scenarios_path) if scenarios_path is not None else DEFAULT_SCENARIOS_PATH
    config = _read_yaml_mapping(main_path, "configuration")
    scenario_document = _read_yaml_mapping(scenario_file, "scenario catalogue")

    if "scenarios" not in scenario_document:
        raise ConfigError(f"{scenario_file}: missing required section 'scenarios'")
    config["scenarios"] = scenario_document["scenarios"]
    validate_config(config)
    return config


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a complete GridMind configuration.

    Args:
        config: Configuration mapping containing every required section,
            including the scenario catalogue.

    Returns:
        The same configuration as a plain ``dict``.

    Raises:
        ConfigError: If a section, value or boundary is invalid. Error messages
            include the dotted path of the offending value.
    """

    if not isinstance(config, Mapping):
        raise ConfigError("configuration must be a mapping")
    cfg = dict(config)

    for section in REQUIRED_SECTIONS:
        if section not in cfg:
            raise ConfigError(f"missing required section '{section}'")

    _validate_project(_section(cfg, "project"))
    simulations = _validate_simulation(_section(cfg, "simulation"))
    _validate_market(_section(cfg, "market"))
    _validate_rates(_section(cfg, "voll"), "voll", VOLL_KEYS)
    _validate_rates(_section(cfg, "max_prices"), "max_prices", MAX_PRICE_KEYS)
    producers = _validate_producers(_section(cfg, "producers"))
    consumers = _validate_consumers(_section(cfg, "consumers"))
    storage = _validate_storage(_section(cfg, "storage"))
    _validate_environment(_section(cfg, "environment"))
    _validate_experiments(_section(cfg, "experiments"))

    agent_count = (
        sum(item["count"] for item in producers)
        + sum(item["count"] for item in consumers)
        + sum(item["count"] for item in storage)
    )
    if agent_count > simulations["max_agents"]:
        raise ConfigError(
            f"agents: {agent_count} configured agents exceed simulation.max_agents="
            f"{simulations['max_agents']}"
        )
    if agent_count < 2:
        raise ConfigError("agents: at least two agents are required")

    _validate_scenarios(
        _section(cfg, "scenarios"),
        steps=simulations["steps"],
        producer_ids=_producer_ids(producers),
        consumer_ids=_consumer_ids(consumers),
    )
    return cfg


def resolve_agent_specs(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand grouped agent definitions into concrete agent specifications.

    Args:
        config: A validated configuration.

    Returns:
        One dictionary per agent in deterministic order: producers, then
        consumers, then storage. Each dictionary contains ``id``, ``role``,
        ``type`` and the role specific parameters.
    """

    specs: list[dict[str, Any]] = []
    for entry in _section(config, "producers"):
        for index in range(1, int(entry["count"]) + 1):
            specs.append(
                {
                    "id": f"{entry['type']}_{index}",
                    "role": "producer",
                    "type": entry["type"],
                    "capacity_mw": float(entry["capacity_mw"]),
                    "marginal_cost": float(entry["marginal_cost"]),
                    "capacity_factor": (
                        None
                        if entry["type"] in ("solar", "wind")
                        else float(entry["capacity_factor"])
                    ),
                }
            )
    for entry in _section(config, "consumers"):
        consumer_type = entry["type"]
        for index in range(1, int(entry["count"]) + 1):
            specs.append(
                {
                    "id": f"{consumer_type}_{index}",
                    "role": "consumer",
                    "type": consumer_type,
                    "base_mw": float(entry["base_mw"]),
                    "flexibility": float(entry["flexibility"]),
                    "voll": float(_section(config, "voll")[consumer_type]),
                    "max_price": float(_section(config, "max_prices")[consumer_type]),
                }
            )
    for entry in _section(config, "storage"):
        for index in range(1, int(entry["count"]) + 1):
            specs.append(
                {
                    "id": f"battery_{index}",
                    "role": "storage",
                    "type": entry["type"],
                    "capacity_mwh": float(entry["capacity_mwh"]),
                    "max_rate_mw": float(entry["max_rate_mw"]),
                    "efficiency": float(entry["efficiency"]),
                    "initial_soc": float(entry["initial_soc"]),
                    "max_price": float(_section(config, "max_prices")["flex"]),
                }
            )
    return specs


def count_agents(config: Mapping[str, Any]) -> int:
    """Return the number of agents defined by a validated configuration."""

    return len(resolve_agent_specs(config))


# ---------------------------------------------------------------------------
# Internal section validators
# ---------------------------------------------------------------------------


def _validate_project(section: Mapping[str, Any]) -> None:
    name = _as_str(_value(section, "project", "name"), "project.name")
    if name != "GridMind":
        raise ConfigError(f"project.name: expected 'GridMind', got {name!r}")
    _as_str(_value(section, "project", "version"), "project.version")


def _validate_simulation(section: Mapping[str, Any]) -> dict[str, int]:
    steps = _as_int(_value(section, "simulation", "steps"), "simulation.steps", minimum=1)
    if steps != REQUIRED_SIMULATION_STEPS:
        raise ConfigError(
            f"simulation.steps: the official duration is {REQUIRED_SIMULATION_STEPS}, got {steps}"
        )
    horizon = _as_int(_value(section, "simulation", "horizon"), "simulation.horizon", minimum=1)
    if horizon > steps:
        raise ConfigError("simulation.horizon: cannot exceed simulation.steps")
    rounds = _as_int(_value(section, "simulation", "rounds"), "simulation.rounds", minimum=1)
    if rounds > MAX_NEGOTIATION_ROUNDS:
        raise ConfigError(
            f"simulation.rounds: at most {MAX_NEGOTIATION_ROUNDS} rounds are allowed, got {rounds}"
        )
    max_agents = _as_int(
        _value(section, "simulation", "max_agents"), "simulation.max_agents", minimum=1
    )
    if max_agents > MAX_AGENT_COUNT:
        raise ConfigError(
            f"simulation.max_agents: the official maximum is {MAX_AGENT_COUNT}, got {max_agents}"
        )
    return {"steps": steps, "horizon": horizon, "rounds": rounds, "max_agents": max_agents}


def _validate_market(section: Mapping[str, Any]) -> None:
    mechanism = _as_str(_value(section, "market", "mechanism"), "market.mechanism")
    if mechanism != "double_auction":
        raise ConfigError(f"market.mechanism: expected 'double_auction', got {mechanism!r}")
    _as_float(
        _value(section, "market", "raise_factor"),
        "market.raise_factor",
        minimum=0.0,
        exclusive=True,
    )
    _as_float(
        _value(section, "market", "producer_step"),
        "market.producer_step",
        minimum=0.0,
        exclusive=True,
    )
    _as_float(_value(section, "market", "initial_markup"), "market.initial_markup", minimum=0.0)


def _validate_rates(section: Mapping[str, Any], path: str, keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in section:
            raise ConfigError(f"{path}.{key}: missing required value")
        _as_float(section[key], f"{path}.{key}", minimum=0.0, exclusive=True)


def _validate_producers(section: Any) -> list[dict[str, Any]]:
    entries = _as_list(section, "producers")
    if not entries:
        raise ConfigError("producers: at least one producer group is required")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"producers[{index}]"
        mapping = _as_mapping(entry, path)
        producer_type = _as_str(_value(mapping, path, "type"), f"{path}.type")
        if producer_type not in PRODUCER_TYPES:
            raise ConfigError(
                f"{path}.type: expected one of {PRODUCER_TYPES}, got {producer_type!r}"
            )
        if producer_type in seen:
            raise ConfigError(f"producers: duplicate producer type {producer_type!r}")
        seen.add(producer_type)
        _as_int(_value(mapping, path, "count"), f"{path}.count", minimum=1)
        _as_float(
            _value(mapping, path, "capacity_mw"), f"{path}.capacity_mw", minimum=0.0, exclusive=True
        )
        _as_float(_value(mapping, path, "marginal_cost"), f"{path}.marginal_cost", minimum=0.0)
        if producer_type in ("thermal", "peaker"):
            _as_float(
                _value(mapping, path, "capacity_factor"),
                f"{path}.capacity_factor",
                minimum=0.0,
                maximum=1.0,
                exclusive=True,
            )
    return [dict(_as_mapping(entry, f"producers[{index}]")) for index, entry in enumerate(entries)]


def _validate_consumers(section: Any) -> list[dict[str, Any]]:
    entries = _as_list(section, "consumers")
    if not entries:
        raise ConfigError("consumers: at least one consumer group is required")
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"consumers[{index}]"
        mapping = _as_mapping(entry, path)
        consumer_type = _as_str(_value(mapping, path, "type"), f"{path}.type")
        if consumer_type not in CONSUMER_TYPES:
            raise ConfigError(
                f"{path}.type: expected one of {CONSUMER_TYPES}, got {consumer_type!r}"
            )
        if consumer_type in seen:
            raise ConfigError(f"consumers: duplicate consumer type {consumer_type!r}")
        seen.add(consumer_type)
        _as_int(_value(mapping, path, "count"), f"{path}.count", minimum=1)
        _as_float(_value(mapping, path, "base_mw"), f"{path}.base_mw", minimum=0.0, exclusive=True)
        _as_float(
            _value(mapping, path, "flexibility"),
            f"{path}.flexibility",
            minimum=0.0,
            maximum=1.0,
        )
    return [dict(_as_mapping(entry, f"consumers[{index}]")) for index, entry in enumerate(entries)]


def _validate_storage(section: Any) -> list[dict[str, Any]]:
    entries = _as_list(section, "storage")
    if not entries:
        raise ConfigError("storage: at least one storage group is required")
    for index, entry in enumerate(entries):
        path = f"storage[{index}]"
        mapping = _as_mapping(entry, path)
        storage_type = _as_str(_value(mapping, path, "type"), f"{path}.type")
        if storage_type not in STORAGE_TYPES:
            raise ConfigError(f"{path}.type: expected one of {STORAGE_TYPES}, got {storage_type!r}")
        _as_int(_value(mapping, path, "count"), f"{path}.count", minimum=1)
        _as_float(
            _value(mapping, path, "capacity_mwh"),
            f"{path}.capacity_mwh",
            minimum=0.0,
            exclusive=True,
        )
        _as_float(
            _value(mapping, path, "max_rate_mw"),
            f"{path}.max_rate_mw",
            minimum=0.0,
            exclusive=True,
        )
        _as_float(
            _value(mapping, path, "efficiency"),
            f"{path}.efficiency",
            minimum=0.0,
            maximum=1.0,
            exclusive=True,
        )
        _as_float(
            _value(mapping, path, "initial_soc"),
            f"{path}.initial_soc",
            minimum=0.0,
            maximum=1.0,
        )
    return [dict(_as_mapping(entry, f"storage[{index}]")) for index, entry in enumerate(entries)]


def _validate_environment(section: Any) -> None:
    environment = _as_mapping(section, "environment")
    weather = _as_mapping(_value(environment, "environment", "weather"), "environment.weather")
    temperature = _as_mapping(
        _value(weather, "environment.weather", "temperature"), "environment.weather.temperature"
    )
    _as_float(_value(temperature, "temperature", "base_c"), "temperature.base_c")
    _as_float(
        _value(temperature, "temperature", "amplitude_c"), "temperature.amplitude_c", minimum=0.0
    )
    _as_float(_value(temperature, "temperature", "peak_shift_hour"), "temperature.peak_shift_hour")
    _as_float(
        _value(temperature, "temperature", "day_offset_std_c"),
        "temperature.day_offset_std_c",
        minimum=0.0,
    )

    cloud = _as_mapping(
        _value(weather, "environment.weather", "cloud"), "environment.weather.cloud"
    )
    cloud_min = _as_float(_value(cloud, "cloud", "min"), "cloud.min", minimum=0.0, maximum=1.0)
    cloud_max = _as_float(_value(cloud, "cloud", "max"), "cloud.max", minimum=0.0, maximum=1.0)
    if cloud_min >= cloud_max:
        raise ConfigError("cloud.min: must be smaller than cloud.max")
    _as_float(_value(cloud, "cloud", "persistence"), "cloud.persistence", minimum=0.0, maximum=1.0)
    noise_low = _as_float(
        _value(cloud, "cloud", "noise_low"), "cloud.noise_low", minimum=0.0, maximum=1.0
    )
    noise_high = _as_float(
        _value(cloud, "cloud", "noise_high"), "cloud.noise_high", minimum=0.0, maximum=1.0
    )
    if noise_low >= noise_high:
        raise ConfigError("cloud.noise_low: must be smaller than cloud.noise_high")
    initial = _as_float(
        _value(cloud, "cloud", "initial"), "cloud.initial", minimum=0.0, maximum=1.0
    )
    if not cloud_min <= initial <= cloud_max:
        raise ConfigError("cloud.initial: must lie within [cloud.min, cloud.max]")

    wind = _as_mapping(_value(weather, "environment.weather", "wind"), "environment.weather.wind")
    _as_float(_value(wind, "wind", "persistence"), "wind.persistence", minimum=0.0, maximum=1.0)
    wind_low = _as_float(
        _value(wind, "wind", "noise_low"), "wind.noise_low", minimum=0.0, maximum=1.0
    )
    wind_high = _as_float(
        _value(wind, "wind", "noise_high"), "wind.noise_high", minimum=0.0, maximum=1.0
    )
    if wind_low >= wind_high:
        raise ConfigError("wind.noise_low: must be smaller than wind.noise_high")
    _as_float(_value(wind, "wind", "initial"), "wind.initial", minimum=0.0, maximum=1.0)

    window = _as_mapping(
        _value(weather, "environment.weather", "solar_window"), "environment.weather.solar_window"
    )
    start_hour = _as_int(
        _value(window, "solar_window", "start_hour"),
        "solar_window.start_hour",
        minimum=0,
        maximum=23,
    )
    duration = _as_int(
        _value(window, "solar_window", "duration_hours"),
        "solar_window.duration_hours",
        minimum=1,
        maximum=24,
    )
    if start_hour + duration > 24:
        raise ConfigError("solar_window: start_hour + duration_hours must not exceed 24")

    demand = _as_mapping(_value(environment, "environment", "demand"), "environment.demand")
    profile = _as_mapping(_value(demand, "environment.demand", "profile"), "demand.profile")
    for key in ("night", "morning", "midday", "evening"):
        _as_float(
            _value(profile, "demand.profile", key),
            f"demand.profile.{key}",
            minimum=0.0,
            exclusive=True,
        )
    windows = _as_mapping(_value(demand, "environment.demand", "windows"), "demand.windows")
    for key in ("night", "morning", "midday", "evening"):
        window_path = f"demand.windows.{key}"
        window_mapping = _as_mapping(_value(windows, "demand.windows", key), window_path)
        _as_int(
            _value(window_mapping, window_path, "start"),
            f"{window_path}.start",
            minimum=0,
            maximum=23,
        )
        _as_int(
            _value(window_mapping, window_path, "end"), f"{window_path}.end", minimum=0, maximum=24
        )
    _as_float(
        _value(demand, "environment.demand", "comfort_temperature_c"),
        "demand.comfort_temperature_c",
    )
    _as_float(
        _value(demand, "environment.demand", "temperature_sensitivity"),
        "demand.temperature_sensitivity",
        minimum=0.0,
    )
    noise = _as_mapping(_value(demand, "environment.demand", "noise_std"), "demand.noise_std")
    for consumer_type in CONSUMER_TYPES:
        _as_float(
            _value(noise, "demand.noise_std", consumer_type),
            f"demand.noise_std.{consumer_type}",
            minimum=0.0,
        )
    work_window = _as_mapping(
        _value(demand, "environment.demand", "factory_work_window"), "demand.factory_work_window"
    )
    _as_int(
        _value(work_window, "factory_work_window", "start"),
        "factory_work_window.start",
        minimum=0,
        maximum=23,
    )
    _as_int(
        _value(work_window, "factory_work_window", "end"),
        "factory_work_window.end",
        minimum=0,
        maximum=24,
    )
    _as_float(
        _value(demand, "environment.demand", "factory_off_factor"),
        "demand.factory_off_factor",
        minimum=0.0,
        maximum=1.0,
    )


def _validate_experiments(section: Mapping[str, Any]) -> None:
    systems = _as_list(_value(section, "experiments", "systems"), "experiments.systems")
    if tuple(systems) != OFFICIAL_SYSTEMS:
        raise ConfigError(
            f"experiments.systems: expected {list(OFFICIAL_SYSTEMS)}, got {list(systems)}"
        )
    scenarios = _as_list(_value(section, "experiments", "scenarios"), "experiments.scenarios")
    if tuple(scenarios) != OFFICIAL_SCENARIOS:
        raise ConfigError(
            f"experiments.scenarios: expected {list(OFFICIAL_SCENARIOS)}, got {list(scenarios)}"
        )
    seeds = _as_int(_value(section, "experiments", "seeds"), "experiments.seeds", minimum=1)
    if seeds != REQUIRED_SEED_COUNT:
        raise ConfigError(
            f"experiments.seeds: the official design uses {REQUIRED_SEED_COUNT}, got {seeds}"
        )
    _as_int(_value(section, "experiments", "seed_start"), "experiments.seed_start", minimum=0)


def _validate_scenarios(
    section: Any,
    *,
    steps: int,
    producer_ids: set[str],
    consumer_ids: set[str],
) -> None:
    scenarios = _as_mapping(section, "scenarios")
    if tuple(scenarios) != OFFICIAL_SCENARIOS:
        raise ConfigError(
            f"scenarios: expected the five official scenarios {list(OFFICIAL_SCENARIOS)}, "
            f"got {list(scenarios)}"
        )
    for name, scenario in scenarios.items():
        path = f"scenarios.{name}"
        scenario_mapping = _as_mapping(scenario, path)
        description = _as_str(_value(scenario_mapping, path, "description"), f"{path}.description")
        if not description:
            raise ConfigError(f"{path}.description: must not be empty")
        events = _as_list(_value(scenario_mapping, path, "events"), f"{path}.events")
        for index, event in enumerate(events):
            event_path = f"{path}.events[{index}]"
            _validate_event(
                _as_mapping(event, event_path),
                event_path,
                steps=steps,
                producer_ids=producer_ids,
                consumer_ids=consumer_ids,
            )


def _validate_event(
    event: Mapping[str, Any],
    path: str,
    *,
    steps: int,
    producer_ids: set[str],
    consumer_ids: set[str],
) -> None:
    name = _as_str(_value(event, path, "name"), f"{path}.name")
    if not name:
        raise ConfigError(f"{path}.name: must not be empty")
    start = _as_int(_value(event, path, "start"), f"{path}.start", minimum=0)
    if start >= steps:
        raise ConfigError(f"{path}.start: must be smaller than simulation.steps")
    _as_int(_value(event, path, "duration"), f"{path}.duration", minimum=1)
    params = _as_mapping(event.get("params", {}), f"{path}.params")
    allowed = {"demand_multiplier", "capacity_factor", "cloud_override"}
    unknown = set(params) - allowed
    if unknown:
        raise ConfigError(f"{path}.params: unsupported keys {sorted(unknown)}")
    if "cloud_override" in params:
        _as_float(
            params["cloud_override"], f"{path}.params.cloud_override", minimum=0.0, maximum=1.0
        )

    demand_multiplier = _as_mapping(
        params.get("demand_multiplier", {}), f"{path}.params.demand_multiplier"
    )
    for target, factor in demand_multiplier.items():
        target_path = f"{path}.params.demand_multiplier.{target}"
        if target not in CONSUMER_TYPES and target not in consumer_ids:
            raise ConfigError(f"{target_path}: unknown consumer type or agent id")
        _as_float(factor, target_path, minimum=0.0, exclusive=True)

    capacity_factor = _as_mapping(
        params.get("capacity_factor", {}), f"{path}.params.capacity_factor"
    )
    for target, factor in capacity_factor.items():
        target_path = f"{path}.params.capacity_factor.{target}"
        if target not in PRODUCER_TYPES and target not in producer_ids:
            raise ConfigError(f"{target_path}: unknown producer type or agent id")
        _as_float(factor, target_path, minimum=0.0, maximum=1.0)


# ---------------------------------------------------------------------------
# Low level helpers
# ---------------------------------------------------------------------------


def _read_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"{path}: {label} file not found")
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML ({exc})") from exc
    if not isinstance(data, Mapping):
        raise ConfigError(f"{path}: {label} must contain a mapping at the top level")
    return dict(data)


def _section(config: Mapping[str, Any], name: str) -> Any:
    if name not in config:
        raise ConfigError(f"missing required section '{name}'")
    return config[name]


def _value(mapping: Mapping[str, Any], path: str, key: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"{path}.{key}: missing required value")
    return mapping[key]


def _as_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{path}: expected a mapping, got {type(value).__name__}")
    return value


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConfigError(f"{path}: expected a list, got {type(value).__name__}")
    return value


def _as_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{path}: expected a string, got {type(value).__name__}")
    return value


def _as_int(
    value: Any,
    path: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: expected an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"{path}: must be >= {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ConfigError(f"{path}: must be <= {maximum}, got {value}")
    return value


def _as_float(
    value: Any,
    path: str,
    minimum: float | None = None,
    maximum: float | None = None,
    exclusive: bool = False,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: expected a number, got {value!r}")
    result = float(value)
    if result != result or result in (float("inf"), float("-inf")):
        raise ConfigError(f"{path}: expected a finite number, got {value!r}")
    if minimum is not None:
        if exclusive and result <= minimum:
            raise ConfigError(f"{path}: must be > {minimum}, got {result}")
        if not exclusive and result < minimum:
            raise ConfigError(f"{path}: must be >= {minimum}, got {result}")
    if maximum is not None and result > maximum:
        raise ConfigError(f"{path}: must be <= {maximum}, got {result}")
    return result


def _producer_ids(producers: list[Mapping[str, Any]]) -> set[str]:
    return {
        f"{entry['type']}_{index}"
        for entry in producers
        for index in range(1, int(entry["count"]) + 1)
    }


def _consumer_ids(consumers: list[Mapping[str, Any]]) -> set[str]:
    return {
        f"{entry['type']}_{index}"
        for entry in consumers
        for index in range(1, int(entry["count"]) + 1)
    }
