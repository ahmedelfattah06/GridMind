"""Simulation clock for GridMind.

One simulation step represents one hour. The simulation starts at ``t = 0``
and runs for a configurable number of steps (168 by default, i.e. seven days).
The clock is the only component allowed to define how ``t`` maps to an hour of
the day and a day index.
"""

from __future__ import annotations

from dataclasses import dataclass

HOURS_PER_DAY = 24


@dataclass(frozen=True)
class SimulationTime:
    """Immutable description of one simulation step.

    Attributes:
        t: Absolute step index, starting at zero.
        hour: Hour of the day, in ``[0, 23]``.
        day: Day index, starting at zero.
    """

    t: int
    hour: int
    day: int

    def as_dict(self) -> dict[str, int]:
        """Return the simulation time as a plain dictionary."""

        return {"t": self.t, "hour": self.hour, "day": self.day}


class SimulationClock:
    """Monotonic hour based clock for one GridMind simulation run."""

    def __init__(self, steps: int) -> None:
        """Create a clock.

        Args:
            steps: Total number of hourly steps. Must be positive.

        Raises:
            ValueError: If ``steps`` is not a positive integer.
        """

        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError(f"steps must be a positive integer, got {steps!r}")
        self._steps = steps
        self._t = 0

    @property
    def steps(self) -> int:
        """Total number of steps in the simulation."""

        return self._steps

    @property
    def t(self) -> int:
        """Current absolute step index."""

        return self._t

    @property
    def hour(self) -> int:
        """Current hour of the day, ``t % 24``."""

        return self._t % HOURS_PER_DAY

    @property
    def day(self) -> int:
        """Current day index, ``t // 24``."""

        return self._t // HOURS_PER_DAY

    @property
    def time(self) -> SimulationTime:
        """Current simulation time as a :class:`SimulationTime` value."""

        return SimulationTime(t=self._t, hour=self.hour, day=self.day)

    @property
    def is_finished(self) -> bool:
        """Whether every configured step has been executed."""

        return self._t >= self._steps

    @property
    def remaining(self) -> int:
        """Number of steps that still have to be executed."""

        return max(0, self._steps - self._t)

    @property
    def progress(self) -> float:
        """Fraction of the simulation that has been executed, in ``[0, 1]``."""

        return self._t / self._steps

    def advance(self) -> SimulationTime:
        """Move the clock one hour forward.

        Returns:
            The new simulation time.

        Raises:
            RuntimeError: If the simulation has already finished.
        """

        if self.is_finished:
            raise RuntimeError(
                f"simulation already finished after {self._steps} steps; cannot advance"
            )
        self._t += 1
        return self.time

    def reset(self) -> None:
        """Return the clock to the first step, ``t = 0``."""

        self._t = 0

    def __repr__(self) -> str:
        return (
            f"SimulationClock(t={self._t}, hour={self.hour}, day={self.day}, "
            f"steps={self._steps})"
        )
