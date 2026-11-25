"""Disruption events and environment modifiers (Team A3).

Events are active on the half-open step interval ``[t_start, t_start + duration)``.
They never message agents directly: only their environmental consequences
(cloud cover, demand multipliers and capacity factors) reach the agents.

The official scenario catalogue lives in ``config/scenarios.yaml``. Its timings
and intensities follow section 8 of the project guide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

SUPPORTED_EVENT_PARAMS: tuple[str, ...] = (
    "demand_multiplier",
    "capacity_factor",
    "cloud_override",
)


@dataclass(frozen=True)
class EnvironmentModifiers:
    """Additive modifiers applied on top of the normal environment.

    Attributes:
        demand_multiplier: Maps a consumer type or agent id to a demand
            multiplier. Missing entries mean ``1.0``. Dimensionless.
        capacity_factor: Maps a producer type or agent id to a capacity
            multiplier, in ``[0, 1]``. Missing entries mean ``1.0``.
        cloud_override: When set, replaces the modelled cloud cover, in
            ``[0, 1]``. Solar generation follows this value.
    """

    demand_multiplier: Mapping[str, float] = field(default_factory=dict)
    capacity_factor: Mapping[str, float] = field(default_factory=dict)
    cloud_override: float | None = None

    def demand_factor_for(self, agent_id: str, agent_type: str) -> float:
        """Return the demand multiplier for one consumer.

        Agent specific entries take precedence over type wide entries.

        Args:
            agent_id: Consumer agent id.
            agent_type: Consumer type (hospital, residential, factory).

        Returns:
            A positive multiplier, ``1.0`` when no entry exists.
        """

        if agent_id in self.demand_multiplier:
            return float(self.demand_multiplier[agent_id])
        if agent_type in self.demand_multiplier:
            return float(self.demand_multiplier[agent_type])
        return 1.0

    def capacity_factor_for(self, agent_id: str, agent_type: str) -> float:
        """Return the capacity factor for one producer.

        Agent specific entries take precedence over type wide entries.

        Args:
            agent_id: Producer agent id.
            agent_type: Producer type (solar, wind, thermal, peaker).

        Returns:
            A capacity factor in ``[0, 1]``, ``1.0`` when no entry exists.
        """

        if agent_id in self.capacity_factor:
            return float(self.capacity_factor[agent_id])
        if agent_type in self.capacity_factor:
            return float(self.capacity_factor[agent_type])
        return 1.0

    def merged(self, other: "EnvironmentModifiers") -> "EnvironmentModifiers":
        """Combine two modifier sets.

        Multipliers multiply for every target and the last defined cloud
        override wins.

        Args:
            other: Modifiers applied on top of this set.

        Returns:
            The merged modifier set.
        """

        demand = dict(self.demand_multiplier)
        for key, value in other.demand_multiplier.items():
            demand[key] = float(demand.get(key, 1.0)) * float(value)
        capacity = dict(self.capacity_factor)
        for key, value in other.capacity_factor.items():
            capacity[key] = float(capacity.get(key, 1.0)) * float(value)
        cloud = self.cloud_override if other.cloud_override is None else other.cloud_override
        return EnvironmentModifiers(
            demand_multiplier=demand,
            capacity_factor=capacity,
            cloud_override=cloud,
        )


@dataclass(frozen=True)
class Event:
    """A scheduled disruption (frozen integration contract).

    Attributes:
        name: Human readable event name, unique within one simulation run.
        t_start: First simulation step on which the event is active.
        duration: Number of steps the event stays active.
        params: Environment modifiers, see :data:`SUPPORTED_EVENT_PARAMS`.
    """

    name: str
    t_start: int
    duration: int
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"event name must be a non-empty string, got {self.name!r}")
        if isinstance(self.t_start, bool) or not isinstance(self.t_start, int) or self.t_start < 0:
            raise ValueError(f"event t_start must be a non-negative integer, got {self.t_start!r}")
        if isinstance(self.duration, bool) or not isinstance(self.duration, int) or self.duration < 1:
            raise ValueError(f"event duration must be a positive integer, got {self.duration!r}")
        if not isinstance(self.params, Mapping):
            raise ValueError("event params must be a mapping")
        unknown = set(self.params) - set(SUPPORTED_EVENT_PARAMS)
        if unknown:
            raise ValueError(f"unsupported event parameters: {sorted(unknown)}")
        for key in ("demand_multiplier", "capacity_factor"):
            if key in self.params and not isinstance(self.params[key], Mapping):
                raise ValueError(f"event {key} must be a mapping")
        for target, value in dict(self.params.get("demand_multiplier", {})).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"demand multiplier for {target!r} must be a number")
            if float(value) <= 0.0:
                raise ValueError(f"demand multiplier for {target!r} must be positive")
        for target, value in dict(self.params.get("capacity_factor", {})).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"capacity factor for {target!r} must be a number")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"capacity factor for {target!r} must lie in [0, 1]")
        if "cloud_override" in self.params:
            value = self.params["cloud_override"]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("cloud_override must be a number")
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError("cloud_override must lie within [0, 1]")

    @property
    def t_end(self) -> int:
        """First step after the event, i.e. the end of the active interval."""

        return self.t_start + self.duration

    def is_active(self, t: int) -> bool:
        """Whether the event is active on step ``t``."""

        return self.t_start <= t < self.t_end

    def modifiers(self) -> EnvironmentModifiers:
        """Translate the event parameters into environment modifiers."""

        demand = {
            str(key): float(value)
            for key, value in dict(self.params.get("demand_multiplier", {})).items()
        }
        capacity = {
            str(key): float(value)
            for key, value in dict(self.params.get("capacity_factor", {})).items()
        }
        cloud = self.params.get("cloud_override")
        return EnvironmentModifiers(
            demand_multiplier=demand,
            capacity_factor=capacity,
            cloud_override=None if cloud is None else float(cloud),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation of the event."""

        return {
            "name": self.name,
            "t_start": int(self.t_start),
            "t_end": int(self.t_end),
            "duration": int(self.duration),
            "params": dict(self.params),
            "active": False,
        }


class EventManager:
    """Schedules events and exposes the modifiers active on a step."""

    def __init__(self, events: Iterable[Event] = ()) -> None:
        """Store the initial schedule.

        Args:
            events: Events to schedule at start-up.
        """

        self._events: list[Event] = []
        self._history: list[dict[str, Any]] = []
        self._last_applied_t: int | None = None
        self._last_active: set[str] = set()
        for event in events:
            self.schedule(event)

    @property
    def events(self) -> tuple[Event, ...]:
        """All scheduled events, in scheduling order."""

        return tuple(self._events)

    @property
    def history(self) -> list[dict[str, Any]]:
        """Activation and expiry transitions observed so far."""

        return [dict(entry) for entry in self._history]

    def schedule(self, event: Event) -> None:
        """Add an event to the schedule.

        Args:
            event: Event to schedule.

        Raises:
            TypeError: If ``event`` is not an :class:`Event`.
            ValueError: If the name is already scheduled.
        """

        if not isinstance(event, Event):
            raise TypeError(f"expected Event, got {type(event).__name__}")
        if any(existing.name == event.name for existing in self._events):
            raise ValueError(f"event {event.name!r} is already scheduled")
        self._events.append(event)

    def inject(self, name: str, t_start: int, duration: int, **params: Any) -> Event:
        """Create and schedule an event at runtime.

        Args:
            name: Event name, unique within the run.
            t_start: First active step.
            duration: Number of active steps.
            **params: Demand, capacity or cloud modifiers.

        Returns:
            The scheduled event.
        """

        event = Event(name=name, t_start=t_start, duration=duration, params=dict(params))
        self.schedule(event)
        return event

    def active_events(self, t: int) -> list[Event]:
        """Return the events active on step ``t``, in scheduling order."""

        return [event for event in self._events if event.is_active(t)]

    def apply(self, t: int) -> EnvironmentModifiers:
        """Record transitions for step ``t`` and merge active modifiers.

        Args:
            t: Current simulation step.

        Returns:
            The merged modifiers of every active event.
        """

        active = self.active_events(t)
        active_names = {event.name for event in active}
        if self._last_applied_t is None or t != self._last_applied_t:
            for name in sorted(self._last_active - active_names):
                self._history.append({"t": int(t), "event": name, "state": "expired"})
            for name in sorted(active_names - self._last_active):
                self._history.append({"t": int(t), "event": name, "state": "active"})
            self._last_active = active_names
            self._last_applied_t = int(t)

        merged = EnvironmentModifiers()
        for event in active:
            merged = merged.merged(event.modifiers())
        return merged


def build_scenario_events(
    config: Mapping[str, Any],
    scenario: str,
) -> list[Event]:
    """Build the scheduled events of one official scenario.

    Args:
        config: Validated configuration containing the ``scenarios`` section.
        scenario: Official scenario key, for example ``"plant_outage"``.

    Returns:
        The events defined by the scenario, in catalogue order.

    Raises:
        ValueError: If the scenario is unknown or the catalogue is malformed.
    """

    key = normalise_scenario(scenario)
    catalogue = config.get("scenarios")
    if not isinstance(catalogue, Mapping) or key not in catalogue:
        raise ValueError(
            f"unknown scenario {scenario!r}; expected one of {sorted(catalogue or {})}"
        )
    definition = catalogue[key]
    events: list[Event] = []
    for entry in definition.get("events", []):
        events.append(
            Event(
                name=str(entry["name"]),
                t_start=int(entry["start"]),
                duration=int(entry["duration"]),
                params=dict(entry.get("params", {})),
            )
        )
    return events


def normalise_scenario(scenario: str) -> str:
    """Normalise an official scenario name to its configuration key.

    ``"Plant Outage"``, ``"plant-outage"`` and ``"plant_outage"`` all map to
    ``"plant_outage"``. This pure string helper is part of the frozen
    integration contract used by ``GridModel``.

    Args:
        scenario: Scenario name provided by a team mate or the CLI.

    Returns:
        The normalised scenario key.

    Raises:
        ValueError: If the name is empty.
    """

    if not isinstance(scenario, str) or not scenario.strip():
        raise ValueError("scenario must be a non-empty string")
    return scenario.strip().lower().replace(" ", "_").replace("-", "_")
