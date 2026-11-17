"""Tests for configuration loading, validation and agent resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import numpy as np

from core.config import (
    CENTRAL_MODES,
    DEFAULT_AGENT_COUNT,
    OFFICIAL_SCENARIOS,
    OFFICIAL_SYSTEMS,
    STREAM_DEMAND,
    STREAM_WEATHER_CLOUD,
    STREAM_WEATHER_WIND,
    SUPPORTED_MODES,
    ConfigError,
    agent_stream_index,
    count_agents,
    derive_agent_rng,
    derive_rng,
    load_config,
    resolve_agent_specs,
    validate_config,
)
from experiments.runner import build_experiment_grid


def test_default_configuration_loads(config: dict[str, Any]) -> None:
    assert config["project"]["name"] == "GridMind"
    assert config["simulation"]["steps"] == 168
    assert config["simulation"]["horizon"] == 6
    assert config["simulation"]["rounds"] == 3
    assert config["market"]["raise_factor"] == pytest.approx(1.2)
    assert config["market"]["producer_step"] == pytest.approx(0.05)
    assert config["market"]["initial_markup"] == pytest.approx(0.2)


def test_official_parameters_are_preserved(config: dict[str, Any]) -> None:
    assert config["voll"] == {"hospital": 1000, "residential": 100, "factory": 40}
    assert config["max_prices"] == {
        "hospital": 300,
        "residential": 120,
        "factory": 80,
        "flex": 50,
    }
    assert tuple(config["experiments"]["systems"]) == OFFICIAL_SYSTEMS
    assert tuple(config["experiments"]["scenarios"]) == OFFICIAL_SCENARIOS
    assert config["experiments"]["seeds"] == 30


def test_default_fleet_has_fifteen_agents(config: dict[str, Any]) -> None:
    specs = resolve_agent_specs(config)
    assert len(specs) == DEFAULT_AGENT_COUNT == 15
    assert count_agents(config) == 15
    assert sum(spec["role"] == "producer" for spec in specs) == 4
    assert sum(spec["role"] == "consumer" for spec in specs) == 9
    assert sum(spec["role"] == "storage" for spec in specs) == 2


def test_agent_ids_are_unique_and_stable(config: dict[str, Any]) -> None:
    ids = [spec["id"] for spec in resolve_agent_specs(config)]
    assert len(ids) == len(set(ids))
    assert ids[:4] == ["solar_1", "wind_1", "thermal_1", "peaker_1"]
    assert "hospital_1" in ids
    assert "factory_3" in ids
    assert "battery_2" in ids


def test_agent_specs_carry_contract_values(config: dict[str, Any]) -> None:
    specs = {spec["id"]: spec for spec in resolve_agent_specs(config)}
    assert specs["solar_1"]["capacity_mw"] == pytest.approx(40)
    assert specs["solar_1"]["marginal_cost"] == pytest.approx(5)
    assert specs["peaker_1"]["capacity_mw"] == pytest.approx(20)
    assert specs["hospital_1"]["flexibility"] == pytest.approx(0.0)
    assert specs["residential_1"]["flexibility"] == pytest.approx(0.1)
    assert specs["factory_1"]["flexibility"] == pytest.approx(0.2)
    assert specs["battery_1"]["capacity_mwh"] == pytest.approx(20)
    assert specs["battery_1"]["efficiency"] == pytest.approx(0.95)
    assert specs["battery_1"]["max_rate_mw"] == pytest.approx(5)


def test_scenario_catalogue_contains_five_official_scenarios(config: dict[str, Any]) -> None:
    assert tuple(config["scenarios"]) == OFFICIAL_SCENARIOS
    # TODO(A3): the event lists are intentionally empty in the skeleton phase.
    # Timing and intensity are open decision PD-01 in docs/decision_log.md.
    assert all(scenario["events"] == [] for scenario in config["scenarios"].values())


@pytest.mark.skip(reason="TODO(D2): experiment grid enumeration is owned by Team D2")
def test_experiment_grid_has_six_hundred_runs(config: dict[str, Any]) -> None:
    grid = build_experiment_grid(config)
    assert len(grid) == 600
    assert len({spec.experiment_id for spec in grid}) == 600


def test_configuration_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="file not found"):
        load_config(path=tmp_path / "missing.yaml")


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    broken = tmp_path / "default.yaml"
    broken.write_text("simulation: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(path=broken)


def test_missing_section_raises(config_copy: dict[str, Any]) -> None:
    del config_copy["market"]
    with pytest.raises(ConfigError, match="missing required section 'market'"):
        validate_config(config_copy)


def test_missing_nested_value_raises(config_copy: dict[str, Any]) -> None:
    del config_copy["environment"]["demand"]["noise_std"]["hospital"]
    with pytest.raises(ConfigError, match="demand.noise_std.hospital: missing required value"):
        validate_config(config_copy)


def test_simulation_duration_cannot_change(config_copy: dict[str, Any]) -> None:
    config_copy["simulation"]["steps"] = 100
    with pytest.raises(ConfigError, match="official duration is 168"):
        validate_config(config_copy)


def test_negotiation_rounds_are_bounded(config_copy: dict[str, Any]) -> None:
    config_copy["simulation"]["rounds"] = 4
    with pytest.raises(ConfigError, match="at most 3 rounds"):
        validate_config(config_copy)


def test_horizon_must_be_positive(config_copy: dict[str, Any]) -> None:
    config_copy["simulation"]["horizon"] = 0
    with pytest.raises(ConfigError, match="simulation.horizon"):
        validate_config(config_copy)


def test_seed_count_is_fixed(config_copy: dict[str, Any]) -> None:
    config_copy["experiments"]["seeds"] = 10
    with pytest.raises(ConfigError, match="official design uses 30"):
        validate_config(config_copy)


def test_system_list_is_fixed(config_copy: dict[str, Any]) -> None:
    config_copy["experiments"]["systems"] = ["auction"]
    with pytest.raises(ConfigError, match="experiments.systems"):
        validate_config(config_copy)


def test_non_positive_capacity_raises(config_copy: dict[str, Any]) -> None:
    config_copy["producers"][0]["capacity_mw"] = 0
    with pytest.raises(ConfigError, match="capacity_mw"):
        validate_config(config_copy)


def test_invalid_efficiency_raises(config_copy: dict[str, Any]) -> None:
    config_copy["storage"][0]["efficiency"] = 1.5
    with pytest.raises(ConfigError, match="storage\\[0\\].efficiency"):
        validate_config(config_copy)


def test_invalid_flexibility_raises(config_copy: dict[str, Any]) -> None:
    config_copy["consumers"][1]["flexibility"] = 1.2
    with pytest.raises(ConfigError, match="flexibility"):
        validate_config(config_copy)


def test_agent_limit_is_enforced(config_copy: dict[str, Any]) -> None:
    config_copy["producers"][0]["count"] = 10
    with pytest.raises(ConfigError, match="exceed simulation.max_agents=20"):
        validate_config(config_copy)


def test_unknown_producer_type_raises(config_copy: dict[str, Any]) -> None:
    config_copy["producers"][0]["type"] = "fusion"
    with pytest.raises(ConfigError, match="producers\\[0\\].type"):
        validate_config(config_copy)


def _set_single_event(config: dict[str, Any], scenario: str, **event: Any) -> None:
    """Install one valid event so that scenario validation can be exercised.

    The skeleton catalogue is empty on purpose; these tests only cover the
    configuration validation owned by A1, not A3's event behaviour.
    """

    entry: dict[str, Any] = {
        "name": "test_event",
        "start": 48,
        "duration": 12,
        "params": {"capacity_factor": {"thermal": 0.0}},
    }
    entry.update(event)
    config["scenarios"][scenario]["events"] = [entry]


def test_unknown_event_target_raises(config_copy: dict[str, Any]) -> None:
    _set_single_event(
        config_copy,
        "plant_outage",
        params={"capacity_factor": {"coal_1": 0.0}},
    )
    with pytest.raises(ConfigError, match="unknown producer type or agent id"):
        validate_config(config_copy)


def test_unsupported_event_parameter_raises(config_copy: dict[str, Any]) -> None:
    _set_single_event(
        config_copy,
        "demand_spike",
        params={"wind_multiplier": 2.0},
    )
    with pytest.raises(ConfigError, match="unsupported keys"):
        validate_config(config_copy)


def test_event_start_must_lie_inside_simulation(config_copy: dict[str, Any]) -> None:
    _set_single_event(config_copy, "plant_outage", start=168)
    with pytest.raises(ConfigError, match="must be smaller than simulation.steps"):
        validate_config(config_copy)


def test_boolean_is_not_accepted_as_number(config_copy: dict[str, Any]) -> None:
    config_copy["market"]["raise_factor"] = True
    with pytest.raises(ConfigError, match="expected a number"):
        validate_config(config_copy)


def test_central_mode_is_supported_without_changing_the_experiment_design() -> None:
    assert "central" in SUPPORTED_MODES
    assert set(CENTRAL_MODES) == {"central", "central_6h", "central_1h"}
    assert set(OFFICIAL_SYSTEMS).issubset(SUPPORTED_MODES)
    assert tuple(OFFICIAL_SYSTEMS) == ("central_6h", "central_1h", "auction", "auction_q")


def test_derive_rng_is_reproducible_and_independent() -> None:
    first = derive_rng(123, STREAM_WEATHER_CLOUD).random(8)
    second = derive_rng(123, STREAM_WEATHER_CLOUD).random(8)
    np.testing.assert_array_equal(first, second)

    other_stream = derive_rng(123, STREAM_WEATHER_WIND).random(8)
    assert not np.array_equal(first, other_stream)

    other_seed = derive_rng(124, STREAM_WEATHER_CLOUD).random(8)
    assert not np.array_equal(first, other_seed)


def test_consuming_one_stream_does_not_shift_another() -> None:
    first = derive_rng(7, STREAM_DEMAND).random(5)

    weather = derive_rng(7, STREAM_WEATHER_CLOUD)
    weather.random(1000)
    demand = derive_rng(7, STREAM_DEMAND)
    second = demand.random(5)

    np.testing.assert_array_equal(first, second)


def test_agent_streams_are_stable_unique_and_independent(config: dict[str, Any]) -> None:
    ids = [spec["id"] for spec in resolve_agent_specs(config)]
    indices = [agent_stream_index(agent_id) for agent_id in ids]
    assert len(indices) == len(set(indices))
    assert indices == [agent_stream_index(agent_id) for agent_id in ids]

    first = derive_agent_rng(42, ids[0]).random(16)
    second = derive_agent_rng(42, ids[1]).random(16)
    assert not np.array_equal(first, second)

    other_agent = derive_agent_rng(42, ids[1])
    other_agent.random(1000)
    repeated = derive_agent_rng(42, ids[0]).random(16)
    np.testing.assert_array_equal(first, repeated)


def test_global_numpy_state_does_not_affect_derived_streams() -> None:
    np.random.seed(1)
    first = derive_rng(9, STREAM_DEMAND).random(8)
    np.random.seed(999)
    np.random.random(100)
    second = derive_rng(9, STREAM_DEMAND).random(8)
    np.testing.assert_array_equal(first, second)


def test_invalid_seed_and_agent_id_are_rejected() -> None:
    with pytest.raises(ValueError, match="seed must be a non-negative integer"):
        derive_rng(-1, 0)
    with pytest.raises(ValueError, match="stream must be a non-negative integer"):
        derive_rng(0, -1)
    with pytest.raises(ValueError, match="agent_id must be a non-empty string"):
        agent_stream_index("")
    with pytest.raises(ValueError, match="agent_id must be a non-empty string"):
        derive_agent_rng(0, "")
