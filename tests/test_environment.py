"""Tests for weather, demand, supply and the environment composition.

Owner: A2 (Environment), with A3 for the event modifiers.
Status: PENDING. A2 and A3 currently ship interface skeletons, so this suite is
skipped until they implement their modules. The assertions are kept as the
agreed acceptance criteria for that work.

Activation: remove ``pytestmark`` below once A2/A3 report the modules ready.
See ``tests/README.md``.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.config import resolve_agent_specs
from core.demand import DemandModel
from core.environment import Environment
from core.events import EnvironmentModifiers

pytestmark = pytest.mark.skip(
    reason=(
        "TODO(A2/A3): weather, demand, supply and event modifiers are interface "
        "skeletons; see tests/README.md for the activation conditions"
    )
)


def _specs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {spec["id"]: spec for spec in resolve_agent_specs(config)}


def _residential_profile_means(config: dict[str, Any]) -> dict[str, float]:
    consumer = {
        "id": "residential_1",
        "role": "consumer",
        "type": "residential",
        "base_mw": 8.0,
        "flexibility": 0.1,
    }
    model = DemandModel(config["environment"]["demand"], [consumer], seed=1)
    hours = list(range(24))
    forecast = model.forecast(hours, [27.0] * 24)["residential_1"]

    windows = config["environment"]["demand"]["windows"]
    means: dict[str, float] = {}
    for name, window in windows.items():
        members = [hour for hour in hours if _in_window(hour, window["start"], window["end"])]
        means[name] = sum(forecast[hour] for hour in members) / len(members)
    return means


def _in_window(hour: int, start: int, end: int) -> bool:
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


def test_environment_updates_successfully(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=4)
    state = environment.update(0)
    assert state.t == 0
    assert state.hour == 0
    assert state.day == 0
    assert state.demand_total_mw > 0.0
    assert state.generation_total_mw > 0.0
    assert set(state.demand_mw) == {
        spec["id"] for spec in resolve_agent_specs(config) if spec["role"] == "consumer"
    }
    assert set(state.generation_mw) == {
        spec["id"] for spec in resolve_agent_specs(config) if spec["role"] == "producer"
    }
    assert 0.0 <= state.cloud_cover <= 1.0
    assert 0.0 <= state.wind_index <= 1.0


def test_environment_requires_update_before_state(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=4)
    with pytest.raises(RuntimeError, match="not been updated"):
        _ = environment.state


def test_solar_generation_is_zero_at_night(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=11)
    night_hours = set(range(0, 6)) | set(range(19, 24))
    for t in range(24):
        state = environment.update(t)
        if state.hour in night_hours:
            assert state.generation_mw["solar_1"] == pytest.approx(0.0)


def test_solar_generation_peaks_around_midday(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=11)
    generation = {}
    for t in range(24):
        generation[t] = environment.update(t).generation_mw["solar_1"]
    assert generation[12] > generation[7]
    assert generation[12] > generation[17]
    assert generation[12] > 0.0


def test_wind_generation_follows_wind_index(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=8)
    state = environment.update(3)
    capacity = _specs(config)["wind_1"]["capacity_mw"]
    assert state.generation_mw["wind_1"] == pytest.approx(capacity * state.wind_index)


def test_thermal_and_peaker_use_capacity_factor(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=8)
    state = environment.update(4)
    specs = _specs(config)
    assert state.generation_mw["thermal_1"] == pytest.approx(
        specs["thermal_1"]["capacity_mw"] * specs["thermal_1"]["capacity_factor"]
    )
    assert state.generation_mw["peaker_1"] == pytest.approx(
        specs["peaker_1"]["capacity_mw"] * specs["peaker_1"]["capacity_factor"]
    )


def test_residential_demand_has_morning_and_evening_peaks(config: dict[str, Any]) -> None:
    means = _residential_profile_means(config)
    assert means["evening"] > means["midday"]
    assert means["morning"] > means["night"]
    assert means["evening"] == pytest.approx(1.4 * 8.0 * 1.04)
    assert means["night"] == pytest.approx(0.6 * 8.0 * 1.04)


def test_factory_demand_drops_outside_working_hours(config: dict[str, Any]) -> None:
    consumer = {
        "id": "factory_1",
        "role": "consumer",
        "type": "factory",
        "base_mw": 10.0,
        "flexibility": 0.2,
    }
    model = DemandModel(config["environment"]["demand"], [consumer], seed=2)
    forecast = model.forecast(list(range(24)), [25.0] * 24)["factory_1"]
    assert forecast[12] == pytest.approx(10.0)
    assert forecast[2] == pytest.approx(4.0)


def test_hospital_demand_is_flat(config: dict[str, Any]) -> None:
    consumer = {
        "id": "hospital_1",
        "role": "consumer",
        "type": "hospital",
        "base_mw": 6.0,
        "flexibility": 0.0,
    }
    model = DemandModel(config["environment"]["demand"], [consumer], seed=3)
    forecast = model.forecast(list(range(24)), [25.0] * 24)["hospital_1"]
    assert set(forecast) == {6.0}


def test_demand_multiplier_scales_only_the_target(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=21)
    base = environment.update(72)
    modified = environment.apply_modifiers(
        EnvironmentModifiers(demand_multiplier={"residential": 1.5}),
        active_events=("test_spike",),
    )
    specs = _specs(config)
    for agent_id, demand in modified.demand_mw.items():
        if specs[agent_id]["type"] == "residential":
            assert demand == pytest.approx(base.demand_mw[agent_id] * 1.5)
        else:
            assert demand == pytest.approx(base.demand_mw[agent_id])
    assert modified.active_events == ("test_spike",)


def test_capacity_factor_modifier_can_disable_a_plant(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=22)
    environment.update(5)
    modified = environment.apply_modifiers(EnvironmentModifiers(capacity_factor={"thermal_1": 0.0}))
    assert modified.generation_mw["thermal_1"] == pytest.approx(0.0)
    assert modified.generation_mw["wind_1"] > 0.0


def test_cloud_override_changes_solar_generation(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=23)
    environment.update(12)
    sunny = environment.apply_modifiers(EnvironmentModifiers(cloud_override=1.0))
    dark = environment.apply_modifiers(EnvironmentModifiers(cloud_override=0.1))
    assert sunny.generation_mw["solar_1"] > dark.generation_mw["solar_1"]
    assert dark.effective_cloud_cover == pytest.approx(0.1)


def test_environment_is_reproducible(config: dict[str, Any]) -> None:
    first = Environment(config, seed=99)
    second = Environment(config, seed=99)
    for t in range(48):
        state_a = first.update(t)
        state_b = second.update(t)
        assert state_a.demand_mw == pytest.approx(state_b.demand_mw)
        assert state_a.generation_mw == pytest.approx(state_b.generation_mw)
        assert state_a.temperature_c == pytest.approx(state_b.temperature_c)


def test_environment_streams_differ_between_seeds(config: dict[str, Any]) -> None:
    first = Environment(config, seed=1)
    second = Environment(config, seed=2)
    state_a = first.update(0)
    state_b = second.update(0)
    assert state_a.temperature_c != pytest.approx(state_b.temperature_c)


def test_forecast_returns_column_oriented_horizon(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=5)
    environment.update(0)
    forecast = environment.forecast(0, 6)
    assert forecast["origin_t"] == 0
    assert forecast["horizon"] == 6
    assert len(forecast["t"]) == 6
    assert len(forecast["hour"]) == 6
    assert forecast["t"] == list(range(6))
    assert len(forecast["demand_total_mw"]) == 6
    assert len(forecast["generation_total_mw"]) == 6
    assert set(forecast["demand_mw"]) == set(environment.consumer_types)
    assert all(len(values) == 6 for values in forecast["demand_mw"].values())
    assert all(len(values) == 6 for values in forecast["generation_mw"].values())


def test_forecast_contains_no_noise(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=5)
    environment.update(3)
    first = environment.forecast(3, 6)
    second = environment.forecast(3, 6)
    assert first == second


def test_forecast_solar_is_zero_at_night(config: dict[str, Any]) -> None:
    environment = Environment(config, seed=5)
    environment.update(0)
    forecast = environment.forecast(0, 6)
    assert all(value == pytest.approx(0.0) for value in forecast["generation_mw"]["solar_1"])
