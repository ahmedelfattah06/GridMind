"""Generation model (Team A2) - interface skeleton.

Owner: A2 (Environment).
Status: TODO. No generation mathematics is implemented in this skeleton.

Responsibilities to implement:

* solar output driven by the solar profile and cloud cover,
* wind output driven by the wind index,
* thermal and peaker output driven by the configured capacity factor,
* event capacity factors applied multiplicatively,
* expected-value forecast without noise.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.events import EnvironmentModifiers


class SupplyModel:
    """Available generation of every producer agent.

    TODO(A2): implement the generation equations for all producer types.
    """

    def __init__(self, producers: Sequence[Mapping[str, Any]]) -> None:
        """Create the supply model.

        Args:
            producers: Producer agent specifications.
        """

        self._producers = list(producers)

    @property
    def producer_ids(self) -> tuple[str, ...]:
        """Producer agent ids in deterministic order."""

        raise NotImplementedError("TODO(A2): implement SupplyModel.producer_ids")

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

        TODO(A2): implement solar, wind, thermal and peaker output.
        """

        raise NotImplementedError("TODO(A2): implement SupplyModel.update")

    def forecast(
        self,
        solar_profiles: Sequence[float],
        cloud_covers: Sequence[float],
        wind_indices: Sequence[float],
    ) -> dict[str, list[float]]:
        """Forecast available generation without random noise.

        TODO(A2): implement the noiseless generation forecast.
        """

        raise NotImplementedError("TODO(A2): implement SupplyModel.forecast")
