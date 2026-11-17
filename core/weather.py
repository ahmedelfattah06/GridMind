"""Weather model (Team A2) - interface skeleton.

Owner: A2 (Environment).
Status: TODO. No weather mathematics is implemented in this skeleton.

Responsibilities to implement:

* hourly temperature, cloud cover and wind processes,
* deterministic initial state at ``t = 0``,
* expected-value forecast without noise,
* dedicated NumPy generators derived from the simulation seed.

The equations and parameters are documented in ``config/default.yaml`` and in
``docs/contracts.md``. Do not change the public signatures below without the
approval of A1, A2 and C1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


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
    """Hourly stochastic weather process.

    TODO(A2): implement the temperature, cloud and wind processes, the
    one-step-at-a-time update rule and the noiseless forecast.
    """

    def __init__(self, params: Mapping[str, Any], seed: int) -> None:
        """Create the weather model.

        Args:
            params: The ``environment.weather`` configuration section.
            seed: Main simulation seed.

        TODO(A2): initialise the dedicated random streams and the ``t = 0``
        state. Storing the inputs only keeps the interface constructible.
        """

        self._params = params
        self._seed = seed

    @property
    def state(self) -> WeatherState:
        """Current weather state.

        TODO(A2): return the state of the current step.
        """

        raise NotImplementedError("TODO(A2): implement WeatherModel.state")

    def update(self, t: int) -> WeatherState:
        """Advance the weather by one hour.

        Args:
            t: Absolute step to compute.

        TODO(A2): implement the recursive cloud and wind processes and the
        temperature equation.
        """

        raise NotImplementedError("TODO(A2): implement WeatherModel.update")

    def forecast(self, t: int, horizon: int) -> list[WeatherState]:
        """Forecast expected weather for ``horizon`` hours.

        Args:
            t: Origin step.
            horizon: Number of hourly values to produce.

        TODO(A2): implement expected-value forecasting without random draws and
        without knowledge of future events.
        """

        raise NotImplementedError("TODO(A2): implement WeatherModel.forecast")
