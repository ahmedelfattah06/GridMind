"""Hourly synthetic demand model (Team A2).

Demand follows the project guide equations:

* residential: ``base * P_res(hour) * (1 + sensitivity * max(0, T - comfort))``;
* factory: ``base`` inside the configured working window, otherwise
  ``base * factory_off_factor``;
* hospital: flat ``base``.

Each consumer owns an independent random stream derived from the simulation
seed and applies multiplicative normal noise. Forecasts use expected values
only and never consume random numbers.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.config import derive_agent_rng
from core.events import EnvironmentModifiers


class DemandModel:
    """Hourly stochastic demand for every consumer agent."""

    def __init__(
        self,
        params: Mapping[str, Any],
        consumers: Sequence[Mapping[str, Any]],
        seed: int,
    ) -> None:
        """Create the demand model.

        Args:
            params: The ``environment.demand`` configuration section.
            consumers: Consumer agent specifications.
            seed: Main simulation seed.
        """

        self._params = dict(params)
        self._consumers = [dict(spec) for spec in consumers]
        self._seed = int(seed)
        self._rngs = {
            str(spec["id"]): derive_agent_rng(seed, str(spec["id"])) for spec in self._consumers
        }

    @property
    def consumer_ids(self) -> tuple[str, ...]:
        """Consumer agent ids in deterministic order."""

        return tuple(str(spec["id"]) for spec in self._consumers)

    def update(
        self,
        hour: int,
        temperature_c: float,
        modifiers: EnvironmentModifiers | None = None,
    ) -> dict[str, float]:
        """Draw the demand of one hour.

        Args:
            hour: Hour of the day, in ``[0, 23]``.
            temperature_c: Current air temperature in degrees Celsius.
            modifiers: Optional event modifiers. They scale the already drawn
                value without consuming additional random numbers.

        Returns:
            Demand per consumer agent, in MW.
        """

        _validate_hour(hour)
        demand: dict[str, float] = {}
        for spec in self._consumers:
            agent_id = str(spec["id"])
            consumer_type = str(spec["type"])
            std = float(self._params["noise_std"][consumer_type])
            noise = float(self._rngs[agent_id].normal(0.0, std)) if std > 0.0 else 0.0
            base = self._expected_value(spec, hour, temperature_c)
            value = max(0.0, base * (1.0 + noise))
            if modifiers is not None:
                value *= modifiers.demand_factor_for(agent_id, consumer_type)
            demand[agent_id] = float(max(0.0, value))
        return demand

    def forecast(
        self,
        hours: Sequence[int],
        temperatures_c: Sequence[float],
    ) -> dict[str, list[float]]:
        """Forecast expected demand without noise or event knowledge.

        Args:
            hours: Hour of the day for each forecast step.
            temperatures_c: Forecast temperature for each step.

        Returns:
            Per-consumer expected demand series.
        """

        if len(hours) != len(temperatures_c):
            raise ValueError("hours and temperatures_c must have the same length")
        forecast: dict[str, list[float]] = {}
        for spec in self._consumers:
            agent_id = str(spec["id"])
            forecast[agent_id] = [
                float(self._expected_value(spec, int(hour), float(temperature)))
                for hour, temperature in zip(hours, temperatures_c)
            ]
        return forecast

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _expected_value(
        self,
        spec: Mapping[str, Any],
        hour: int,
        temperature_c: float,
    ) -> float:
        _validate_hour(hour)
        base = float(spec["base_mw"])
        consumer_type = str(spec["type"])
        if consumer_type == "residential":
            profile = self._residential_profile(hour)
            comfort = float(self._params["comfort_temperature_c"])
            sensitivity = float(self._params["temperature_sensitivity"])
            temperature_factor = 1.0 + sensitivity * max(0.0, temperature_c - comfort)
            return base * profile * temperature_factor
        if consumer_type == "factory":
            return base * self._factory_profile(hour)
        if consumer_type == "hospital":
            return base
        raise ValueError(f"unsupported consumer type {consumer_type!r}")

    def _residential_profile(self, hour: int) -> float:
        profile = self._params["profile"]
        for name, window in self._params["windows"].items():
            start = int(window["start"])
            end = int(window["end"])
            inside = start <= hour < end if start < end else (hour >= start or hour < end)
            if inside:
                return float(profile[name])
        return float(profile["night"])

    def _factory_profile(self, hour: int) -> float:
        window = self._params["factory_work_window"]
        if int(window["start"]) <= hour < int(window["end"]):
            return 1.0
        return float(self._params["factory_off_factor"])


def _validate_hour(hour: int) -> None:
    if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
        raise ValueError(f"hour must be an integer in [0, 23], got {hour!r}")
