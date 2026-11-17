"""Disruption events and environment modifiers (Team A3) - interface skeleton.

Owner: A3 (Events, Tests, Scope Guard).
Status: TODO. Event activation, modifier translation and scenario calibration
are not implemented in this skeleton.

Responsibilities to implement:

* activate an event on the half-open interval ``[t_start, t_start + duration)``,
* translate event parameters into :class:`EnvironmentModifiers`,
* merge the modifiers of several active events,
* restore normal conditions after the event ends,
* support runtime injection without notifying agents directly.

The official scenario catalogue lives in ``config/scenarios.yaml``. The
interface is frozen in ``docs/contracts.md`` (section "Event contract").
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

        TODO(A3): implement the lookup rule documented in ``docs/contracts.md``.
        """

        raise NotImplementedError("TODO(A3): implement EnvironmentModifiers.demand_factor_for")

    def capacity_factor_for(self, agent_id: str, agent_type: str) -> float:
        """Return the capacity factor for one producer.

        Agent specific entries take precedence over type wide entries.

        TODO(A3): implement the lookup rule documented in ``docs/contracts.md``.
        """

        raise NotImplementedError("TODO(A3): implement EnvironmentModifiers.capacity_factor_for")

    def merged(self, other: "EnvironmentModifiers") -> "EnvironmentModifiers":
        """Combine two modifier sets.

        TODO(A3): implement the merge rule (multipliers multiply, the last
        defined cloud override wins).
        """

        raise NotImplementedError("TODO(A3): implement EnvironmentModifiers.merged")


@dataclass(frozen=True)
class Event:
    """A scheduled disruption (frozen integration contract).

    Attributes:
        name: Human readable event name, unique within one simulation run.
        t_start: First simulation step on which the event is active.
        duration: Number of steps the event stays active.
        params: Environment modifiers, see :data:`SUPPORTED_EVENT_PARAMS`.

    TODO(A3): decide how invalid events are rejected (the skeleton performs no
    validation and defines no activation logic).
    """

    name: str
    t_start: int
    duration: int
    params: Mapping[str, Any] = field(default_factory=dict)

    @property
    def t_end(self) -> int:
        """First step after the event, i.e. the end of the active interval.

        TODO(A3): implement.
        """

        raise NotImplementedError("TODO(A3): implement Event.t_end")

    def is_active(self, t: int) -> bool:
        """Whether the event is active on step ``t``.

        TODO(A3): implement the half-open interval rule.
        """

        raise NotImplementedError("TODO(A3): implement Event.is_active")

    def modifiers(self) -> EnvironmentModifiers:
        """Translate the event parameters into environment modifiers.

        TODO(A3): implement the parameter translation and validation.
        """

        raise NotImplementedError("TODO(A3): implement Event.modifiers")

    def as_dict(self) -> dict[str, Any]:
        """Return a serialisable representation of the event.

        TODO(A3): implement. ``GridModel.snapshot`` consumes this method.
        """

        raise NotImplementedError("TODO(A3): implement Event.as_dict")


class EventManager:
    """Schedules events and exposes the modifiers that are active on a step.

    The constructor only stores the schedule so that the interface stays
    constructible. All scheduling and activation behaviour is owned by A3.
    """

    def __init__(self, events: Iterable[Event] = ()) -> None:
        """Store the initial schedule.

        Args:
            events: Events to schedule at start-up.
        """

        self._events: list[Event] = list(events)

    @property
    def events(self) -> tuple[Event, ...]:
        """All scheduled events, in scheduling order."""

        return tuple(self._events)

    @property
    def history(self) -> list[dict[str, Any]]:
        """Activation and expiry transitions observed so far.

        TODO(A3): implement the transition history.
        """

        raise NotImplementedError("TODO(A3): implement EventManager.history")

    def schedule(self, event: Event) -> None:
        """Add an event to the schedule.

        TODO(A3): implement duplicate name detection and scheduling.
        """

        raise NotImplementedError("TODO(A3): implement EventManager.schedule")

    def inject(self, name: str, t_start: int, duration: int, **params: Any) -> Event:
        """Create and schedule an event at runtime.

        TODO(A3): implement runtime injection.
        """

        raise NotImplementedError("TODO(A3): implement EventManager.inject")

    def active_events(self, t: int) -> list[Event]:
        """Return the events active on step ``t``, in scheduling order.

        TODO(A3): implement.
        """

        raise NotImplementedError("TODO(A3): implement EventManager.active_events")

    def apply(self, t: int) -> EnvironmentModifiers:
        """Record transitions for step ``t`` and merge active modifiers.

        TODO(A3): implement activation, expiry and modifier merging.
        """

        raise NotImplementedError("TODO(A3): implement EventManager.apply")


def build_scenario_events(
    config: Mapping[str, Any],
    scenario: str,
) -> list[Event]:
    """Build the scheduled events of one official scenario.

    This is a structural configuration loader only: it reads the entries of
    ``config/scenarios.yaml``. Event timing, intensity and behaviour are owned
    by A3 and are intentionally empty in the skeleton phase.

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
