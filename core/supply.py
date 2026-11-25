"""Available generation model (Team A2).

Generation equations from the project guide:

* solar: ``capacity * solar_profile * cloud_cover``;
* wind: ``capacity * wind_index``;
* thermal / peaker: ``capacity * capacity_factor``.

Event capacity factors are applied multiplicatively by producer id or producer
type. The forecast path is noiseless and ignores future events.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.events import EnvironmentModifiers


class SupplyModel:
    """Available generation of every producer agent."""

    def __init__(self, producers: Sequence[Mapping[str, Any]]) -> None:
        """Create the supply model.

        Args:
            producers: Producer agent specifications.
        """

        self._producers = [dict(spec) for spec in producers]

    @property
    def producer_ids(self) -> tuple[str, ...]:
        """Producer agent ids in deterministic order."""

        return tuple(str(spec["id"]) for spec in self._producers)

    def update(
        self,
        solar_profile: float,
        cloud_cover: float,
        wind_index: float,
        modifiers: EnvironmentModifiers | None = None,
    ) -> dict[str, float]:
        """Compute available generation for one hour.

        Args:
            solar_profile: Clear-sky solar profile in ``[0, 1]``.
            cloud_cover: Effective cloud cover in ``[0, 1]``.
            wind_index: Normalised wind availability in ``[0, 1]``.
            modifiers: Optional event modifiers.

        Returns:
            Available generation per producer agent, in MW.
        """

        generation: dict[str, float] = {}
        for spec in self._producers:
            agent_id = str(spec["id"])
            producer_type = str(spec["type"])
            capacity = float(spec["capacity_mw"])
            if producer_type == "solar":
                value = capacity * max(0.0, float(solar_profile)) * max(0.0, float(cloud_cover))
            elif producer_type == "wind":
                value = capacity * max(0.0, float(wind_index))
            elif producer_type in ("thermal", "peaker"):
                factor = spec.get("capacity_factor")
                value = capacity * (1.0 if factor is None else float(factor))
            else:
                raise ValueError(f"unsupported producer type {producer_type!r}")
            if modifiers is not None:
                value *= modifiers.capacity_factor_for(agent_id, producer_type)
            generation[agent_id] = float(max(0.0, value))
        return generation

    def forecast(
        self,
        solar_profiles: Sequence[float],
        cloud_covers: Sequence[float],
        wind_indices: Sequence[float],
    ) -> dict[str, list[float]]:
        """Forecast available generation without random noise.

        Args:
            solar_profiles: Expected clear-sky profile per step.
            cloud_covers: Expected cloud cover per step.
            wind_indices: Expected wind index per step.

        Returns:
            Per-producer expected generation series.
        """

        if not (len(solar_profiles) == len(cloud_covers) == len(wind_indices)):
            raise ValueError("solar_profiles, cloud_covers and wind_indices must have equal lengths")
        forecast: dict[str, list[float]] = {}
        for spec in self._producers:
            values: list[float] = []
            for solar_profile, cloud_cover, wind_index in zip(
                solar_profiles, cloud_covers, wind_indices
            ):
                values.append(
                    float(
                        self._value(
                            spec,
                            float(solar_profile),
                            float(cloud_cover),
                            float(wind_index),
                        )
                    )
                )
            forecast[str(spec["id"])] = values
        return forecast

    def _value(
        self,
        spec: Mapping[str, Any],
        solar_profile: float,
        cloud_cover: float,
        wind_index: float,
    ) -> float:
        capacity = float(spec["capacity_mw"])
        producer_type = str(spec["type"])
        if producer_type == "solar":
            return capacity * max(0.0, solar_profile) * max(0.0, cloud_cover)
        if producer_type == "wind":
            return capacity * max(0.0, wind_index)
        if producer_type in ("thermal", "peaker"):
            factor = spec.get("capacity_factor")
            return capacity * (1.0 if factor is None else float(factor))
        raise ValueError(f"unsupported producer type {producer_type!r}")
