"""Demand model (Team A2) - interface skeleton.

Owner: A2 (Environment).
Status: TODO. No demand mathematics is implemented in this skeleton.

Responsibilities to implement:

* hospital, residential and factory demand equations,
* one independent random stream per consumer,
* event demand multipliers applied without drawing new noise,
* expected-value forecast without noise.

The equations and parameters are documented in ``config/default.yaml`` and in
``docs/contracts.md``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.events import EnvironmentModifiers


class DemandModel:
    """Hourly stochastic demand for every consumer agent.

    TODO(A2): implement the demand equations and the per-consumer streams.
    """

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

        TODO(A2): initialise one random stream per consumer.
        """

        self._params = params
        self._consumers = list(consumers)
        self._seed = seed

    @property
    def consumer_ids(self) -> tuple[str, ...]:
        """Consumer agent ids in deterministic order."""

        raise NotImplementedError("TODO(A2): implement DemandModel.consumer_ids")

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
            modifiers: Optional event modifiers.

        TODO(A2): implement the three consumer demand equations and apply the
        demand multipliers without consuming extra random draws.
        """

        raise NotImplementedError("TODO(A2): implement DemandModel.update")

    def forecast(
        self,
        hours: Sequence[int],
        temperatures_c: Sequence[float],
    ) -> dict[str, list[float]]:
        """Forecast expected demand without noise or event knowledge.

        Args:
            hours: Hour of the day for each forecast step.
            temperatures_c: Forecast temperature for each step.

        TODO(A2): implement the noiseless forecast.
        """

        raise NotImplementedError("TODO(A2): implement DemandModel.forecast")
