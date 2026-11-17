"""Environment composition (Team A2).

This module combines :mod:`core.weather`, :mod:`core.demand` and
:mod:`core.supply` into the single Environment component that the model
coordinates. It owns the environment state of the current step and applies the
modifiers contributed by active events.

The module is not part of the file list of the official project tree; it exists
so that ``core/model.py`` only orchestrates and never contains environment
mathematics. The rationale is recorded in ``docs/decision_log.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.config import resolve_agent_specs
from core.demand import DemandModel
from core.events import EnvironmentModifiers
from core.supply import SupplyModel
from core.weather import WeatherModel, WeatherState


@dataclass(frozen=True)
class EnvironmentState:
    """Environment conditions of one simulation step.

    Attributes:
        t: Absolute simulation step.
        hour: Hour of the day.
        day: Day index.
        temperature_c: Air temperature in degrees Celsius.
        cloud_cover: Modelled cloud cover in ``[0, 1]``.
        effective_cloud_cover: Cloud cover after event overrides.
        wind_index: Normalised wind availability in ``[0, 1]``.
        solar_profile: Normalised clear-sky solar profile in ``[0, 1]``.
        demand_mw: Demand per consumer agent, in MW.
        generation_mw: Available generation per producer agent, in MW.
        active_events: Names of the events active on this step.
    """

    t: int
    hour: int
    day: int
    temperature_c: float
    cloud_cover: float
    effective_cloud_cover: float
    wind_index: float
    solar_profile: float
    demand_mw: Mapping[str, float] = field(default_factory=dict)
    generation_mw: Mapping[str, float] = field(default_factory=dict)
    active_events: tuple[str, ...] = ()

    @property
    def demand_total_mw(self) -> float:
        """Total requested demand in MW."""

        return float(sum(self.demand_mw.values()))

    @property
    def generation_total_mw(self) -> float:
        """Total available generation in MW."""

        return float(sum(self.generation_mw.values()))

    def as_dict(self) -> dict[str, Any]:
        """Return the environment state as a plain dictionary."""

        return {
            "t": self.t,
            "hour": self.hour,
            "day": self.day,
            "temperature_c": self.temperature_c,
            "cloud_cover": self.cloud_cover,
            "effective_cloud_cover": self.effective_cloud_cover,
            "wind_index": self.wind_index,
            "solar_profile": self.solar_profile,
            "demand_mw": dict(self.demand_mw),
            "generation_mw": dict(self.generation_mw),
            "demand_total_mw": self.demand_total_mw,
            "generation_total_mw": self.generation_total_mw,
            "active_events": list(self.active_events),
        }


class Environment:
    """Aggregated weather, demand and generation model."""

    def __init__(self, config: Mapping[str, Any], seed: int) -> None:
        """Create the environment from a validated configuration.

        Args:
            config: Validated GridMind configuration.
            seed: Main simulation seed.
        """

        agent_specs = resolve_agent_specs(config)
        consumers = [spec for spec in agent_specs if spec["role"] == "consumer"]
        producers = [spec for spec in agent_specs if spec["role"] == "producer"]
        environment_config = config["environment"]

        self._weather = WeatherModel(environment_config["weather"], seed)
        self._demand = DemandModel(environment_config["demand"], consumers, seed)
        self._supply = SupplyModel(producers)
        self._consumer_types = {str(spec["id"]): str(spec["type"]) for spec in consumers}
        self._state: EnvironmentState | None = None
        self._base_demand_mw: dict[str, float] = {}

    @property
    def state(self) -> EnvironmentState:
        """Environment state of the current step.

        Raises:
            RuntimeError: If :meth:`update` has not been called yet.
        """

        if self._state is None:
            raise RuntimeError("environment has not been updated yet; call update(t) first")
        return self._state

    @property
    def consumer_types(self) -> dict[str, str]:
        """Mapping of consumer agent id to consumer type."""

        return dict(self._consumer_types)

    def update(self, t: int) -> EnvironmentState:
        """Compute the environment for step ``t`` without event modifiers.

        If ``t`` lies ahead of the internal weather state, the weather process
        is advanced hour by hour so that the requested step is computed
        deterministically. Demand noise is drawn once, for ``t`` only.

        Args:
            t: Current simulation step.

        Returns:
            The environment state of step ``t``.
        """

        if self._state is not None and self._state.t == t:
            return self._state
        if t < self._weather.state.t:
            raise ValueError(
                f"cannot rewind the environment (current t={self._weather.state.t}, requested t={t})"
            )

        weather = self._weather.state
        for step in range(weather.t + 1, t + 1):
            weather = self._weather.update(step)

        base_demand = self._demand.update(weather.hour, weather.temperature_c)
        generation = self._supply.update(
            weather.solar_profile,
            weather.cloud_cover,
            weather.wind_index,
        )
        self._state = self._compose(weather, base_demand, generation, EnvironmentModifiers())
        self._base_demand_mw = dict(base_demand)
        return self._state

    def apply_modifiers(
        self,
        modifiers: EnvironmentModifiers,
        active_events: tuple[str, ...] = (),
    ) -> EnvironmentState:
        """Apply event modifiers on top of the current environment state.

        Demand multipliers are applied to the already drawn base demand, so no
        random number is consumed twice for the same step. A cloud override
        recomputes solar generation deterministically.

        Args:
            modifiers: Merged modifiers of the active events.
            active_events: Names of the events active on this step.

        Returns:
            The updated environment state.

        Raises:
            RuntimeError: If :meth:`update` has not been called yet.
        """

        state = self.state
        weather = WeatherState(
            t=state.t,
            hour=state.hour,
            day=state.day,
            temperature_c=state.temperature_c,
            cloud_cover=state.cloud_cover,
            wind_index=state.wind_index,
            solar_profile=state.solar_profile,
        )
        effective_cloud = (
            modifiers.cloud_override if modifiers.cloud_override is not None else state.cloud_cover
        )
        demand = {}
        for agent_id, base in self._base_demand_mw.items():
            consumer_type = self._consumer_types[agent_id]
            demand[agent_id] = max(0.0, base * modifiers.demand_factor_for(agent_id, consumer_type))
        generation = self._supply.update(
            weather.solar_profile,
            effective_cloud,
            weather.wind_index,
            modifiers,
        )
        self._state = EnvironmentState(
            t=state.t,
            hour=state.hour,
            day=state.day,
            temperature_c=state.temperature_c,
            cloud_cover=state.cloud_cover,
            effective_cloud_cover=float(effective_cloud),
            wind_index=state.wind_index,
            solar_profile=state.solar_profile,
            demand_mw=demand,
            generation_mw=generation,
            active_events=tuple(active_events),
        )
        return self._state

    def forecast(self, t: int, horizon: int) -> dict[str, Any]:
        """Forecast expected environment values for Team C's planner.

        The forecast contains no random noise and no knowledge of future
        events. It is expressed as a column oriented dictionary, ready to be
        converted into a :class:`pandas.DataFrame`.

        Args:
            t: Origin step, at or after the current step.
            horizon: Number of hourly values to produce.

        Returns:
            Dictionary with scalar columns (``t``, ``hour``, ``day``,
            ``temperature_c``, ``cloud_cover``, ``wind_index``) and mapping
            columns (``demand_mw``, ``generation_mw``) keyed by agent id, plus
            the totals ``demand_total_mw`` and ``generation_total_mw``.
        """

        weather_states = self._weather.forecast(t, horizon)
        hours = [state.hour for state in weather_states]
        temperatures = [state.temperature_c for state in weather_states]
        demand = self._demand.forecast(hours, temperatures)
        generation = self._supply.forecast(
            [state.solar_profile for state in weather_states],
            [state.cloud_cover for state in weather_states],
            [state.wind_index for state in weather_states],
        )
        return {
            "origin_t": t,
            "horizon": horizon,
            "t": [state.t for state in weather_states],
            "hour": hours,
            "day": [state.day for state in weather_states],
            "temperature_c": temperatures,
            "cloud_cover": [state.cloud_cover for state in weather_states],
            "wind_index": [state.wind_index for state in weather_states],
            "demand_mw": demand,
            "generation_mw": generation,
            "demand_total_mw": _row_totals(demand, horizon),
            "generation_total_mw": _row_totals(generation, horizon),
        }

    def _compose(
        self,
        weather: WeatherState,
        demand: Mapping[str, float],
        generation: Mapping[str, float],
        modifiers: EnvironmentModifiers,
    ) -> EnvironmentState:
        effective_cloud = (
            modifiers.cloud_override
            if modifiers.cloud_override is not None
            else weather.cloud_cover
        )
        return EnvironmentState(
            t=weather.t,
            hour=weather.hour,
            day=weather.day,
            temperature_c=weather.temperature_c,
            cloud_cover=weather.cloud_cover,
            effective_cloud_cover=float(effective_cloud),
            wind_index=weather.wind_index,
            solar_profile=weather.solar_profile,
            demand_mw=dict(demand),
            generation_mw=dict(generation),
        )


def _row_totals(series: Mapping[str, list[float]], horizon: int) -> list[float]:
    """Sum a mapping of per-agent series column wise."""

    return [float(sum(values[index] for values in series.values())) for index in range(horizon)]
