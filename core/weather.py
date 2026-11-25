"""Hourly synthetic weather model (Team A2).

The process follows the equations fixed by the project guide:

* temperature ``T = base + amplitude * sin(2*pi*(hour-9)/24) + day_offset``
  with a daily offset drawn from ``N(0, day_offset_std)``;
* cloud cover ``cloud = clip(persistence*cloud_prev + (1-persistence)*U(low, high))``;
* wind index ``wind = clip(persistence*wind_prev + (1-persistence)*U(low, high), 0, 1)``;
* clear-sky solar profile ``max(0, sin(pi*(hour-6)/12))`` inside the configured window.

Every random source uses its own stream derived from the simulation seed, so
adding a component never shifts another component's draws. Forecasts contain no
randomness and no knowledge of future events.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi, sin
from typing import Any, Mapping

import numpy as np

from core.config import (
    STREAM_WEATHER_CLOUD,
    STREAM_WEATHER_TEMPERATURE,
    STREAM_WEATHER_WIND,
    derive_rng,
)


@dataclass(frozen=True)
class WeatherState:
    """Weather conditions for one simulation hour (integration contract).

    Attributes:
        t: Absolute simulation step.
        hour: Hour of the day.
        day: Day index.
        temperature_c: Air temperature in degrees Celsius.
        cloud_cover: Cloud cover in ``[0, 1]``.
        wind_index: Normalised wind availability in ``[0, 1]``.
        solar_profile: Normalised clear-sky solar profile in ``[0, 1]``.
    """

    t: int
    hour: int
    day: int
    temperature_c: float
    cloud_cover: float
    wind_index: float
    solar_profile: float


class WeatherModel:
    """Hourly stochastic weather process with a noiseless forecast."""

    def __init__(self, params: Mapping[str, Any], seed: int) -> None:
        """Create the weather model.

        Args:
            params: The ``environment.weather`` configuration section.
            seed: Main simulation seed.
        """

        self._params = dict(params)
        self._seed = int(seed)
        self._temperature_params = dict(self._params["temperature"])
        self._cloud_params = dict(self._params["cloud"])
        self._wind_params = dict(self._params["wind"])
        self._window = dict(self._params["solar_window"])

        self._cloud_rng = derive_rng(seed, STREAM_WEATHER_CLOUD)
        self._wind_rng = derive_rng(seed, STREAM_WEATHER_WIND)
        self._temperature_rng = derive_rng(seed, STREAM_WEATHER_TEMPERATURE)
        self._day_offsets: dict[int, float] = {}
        self._state = self._initial_state()

    @property
    def state(self) -> WeatherState:
        """Current weather state."""

        return self._state

    def update(self, t: int) -> WeatherState:
        """Advance the weather to step ``t`` one hour at a time.

        Args:
            t: Absolute step to compute.

        Returns:
            The weather state of step ``t``.

        Raises:
            ValueError: If ``t`` lies before the current step.
        """

        if isinstance(t, bool) or not isinstance(t, int) or t < 0:
            raise ValueError(f"t must be a non-negative integer, got {t!r}")
        if t < self._state.t:
            raise ValueError(
                f"cannot rewind the weather (current t={self._state.t}, requested t={t})"
            )
        for step in range(self._state.t + 1, t + 1):
            self._state = self._step(step)
        return self._state

    def forecast(self, t: int, horizon: int) -> list[WeatherState]:
        """Forecast expected weather for ``horizon`` hours without noise.

        The origin hour is included. Future cloud and wind values use the
        expected value of the AR(1) process, temperature uses the deterministic
        seasonal term with a zero day offset for future days (PD-04).

        Args:
            t: Origin step, at or after the current step.
            horizon: Number of hourly values to produce.

        Returns:
            A list of expected :class:`WeatherState` values.

        Raises:
            ValueError: If ``t`` is in the past or ``horizon`` is not positive.
        """

        if isinstance(t, bool) or not isinstance(t, int) or t < 0:
            raise ValueError(f"t must be a non-negative integer, got {t!r}")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
            raise ValueError(f"horizon must be a positive integer, got {horizon!r}")
        if t < self._state.t:
            raise ValueError(
                f"cannot forecast from the past (current t={self._state.t}, requested t={t})"
            )

        current = self._state
        while current.t < t:
            current = self._expected_step(current)

        forecast: list[WeatherState] = []
        cursor = current
        for _ in range(horizon):
            forecast.append(cursor)
            cursor = self._expected_step(cursor)
        return forecast

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _initial_state(self) -> WeatherState:
        day_offset = self._draw_day_offset(0)
        temperature = self._temperature(0, day_offset)
        return WeatherState(
            t=0,
            hour=0,
            day=0,
            temperature_c=temperature,
            cloud_cover=float(np.clip(self._cloud_params["initial"], self._cloud_params["min"], self._cloud_params["max"])),
            wind_index=float(np.clip(self._wind_params["initial"], 0.0, 1.0)),
            solar_profile=self._solar_profile(0),
        )

    def _step(self, t: int) -> WeatherState:
        hour = t % 24
        day = t // 24
        previous = self._state
        cloud = self._cloud_step(previous.cloud_cover)
        wind = self._wind_step(previous.wind_index)
        temperature = self._temperature(hour, self._day_offset(day))
        return WeatherState(
            t=t,
            hour=hour,
            day=day,
            temperature_c=temperature,
            cloud_cover=cloud,
            wind_index=wind,
            solar_profile=self._solar_profile(hour),
        )

    def _expected_step(self, state: WeatherState) -> WeatherState:
        t = state.t + 1
        hour = t % 24
        day = t // 24
        cloud_params = self._cloud_params
        wind_params = self._wind_params
        cloud_mean = 0.5 * (float(cloud_params["noise_low"]) + float(cloud_params["noise_high"]))
        wind_mean = 0.5 * (float(wind_params["noise_low"]) + float(wind_params["noise_high"]))
        cloud = float(
            np.clip(
                float(cloud_params["persistence"]) * state.cloud_cover
                + (1.0 - float(cloud_params["persistence"])) * cloud_mean,
                float(cloud_params["min"]),
                float(cloud_params["max"]),
            )
        )
        wind = float(
            np.clip(
                float(wind_params["persistence"]) * state.wind_index
                + (1.0 - float(wind_params["persistence"])) * wind_mean,
                0.0,
                1.0,
            )
        )
        offset = self._day_offsets.get(day, 0.0) if day == self._state.day else 0.0
        return WeatherState(
            t=t,
            hour=hour,
            day=day,
            temperature_c=self._temperature(hour, offset),
            cloud_cover=cloud,
            wind_index=wind,
            solar_profile=self._solar_profile(hour),
        )

    def _cloud_step(self, previous: float) -> float:
        params = self._cloud_params
        noise = float(self._cloud_rng.uniform(params["noise_low"], params["noise_high"]))
        value = float(params["persistence"]) * previous + (1.0 - float(params["persistence"])) * noise
        return float(np.clip(value, params["min"], params["max"]))

    def _wind_step(self, previous: float) -> float:
        params = self._wind_params
        noise = float(self._wind_rng.uniform(params["noise_low"], params["noise_high"]))
        value = float(params["persistence"]) * previous + (1.0 - float(params["persistence"])) * noise
        return float(np.clip(value, 0.0, 1.0))

    def _temperature(self, hour: int, day_offset: float) -> float:
        params = self._temperature_params
        seasonal = float(params["amplitude_c"]) * sin(
            2.0 * pi * (hour - float(params["peak_shift_hour"])) / 24.0
        )
        return float(params["base_c"]) + seasonal + float(day_offset)

    def _day_offset(self, day: int) -> float:
        if day not in self._day_offsets:
            self._day_offsets[day] = self._draw_day_offset(day)
        return self._day_offsets[day]

    def _draw_day_offset(self, day: int) -> float:
        std = float(self._temperature_params["day_offset_std_c"])
        if std <= 0.0:
            value = 0.0
        else:
            value = float(self._temperature_rng.normal(0.0, std))
        self._day_offsets[day] = value
        return value

    def _solar_profile(self, hour: int) -> float:
        start = int(self._window["start_hour"])
        duration = int(self._window["duration_hours"])
        if start <= hour < start + duration:
            return max(0.0, sin(pi * (hour - start) / duration))
        return 0.0
