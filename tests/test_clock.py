"""Tests for the simulation clock."""

from __future__ import annotations

import pytest

from core.clock import SimulationClock, SimulationTime


def test_clock_starts_at_zero() -> None:
    clock = SimulationClock(168)
    assert clock.t == 0
    assert clock.hour == 0
    assert clock.day == 0
    assert clock.time == SimulationTime(t=0, hour=0, day=0)
    assert clock.remaining == 168
    assert not clock.is_finished


def test_clock_advances_one_hour_at_a_time() -> None:
    clock = SimulationClock(168)
    assert clock.advance() == SimulationTime(t=1, hour=1, day=0)
    assert clock.t == 1
    assert clock.advance() == SimulationTime(t=2, hour=2, day=0)


@pytest.mark.parametrize(
    ("advances", "expected"),
    [
        (23, SimulationTime(t=23, hour=23, day=0)),
        (24, SimulationTime(t=24, hour=0, day=1)),
        (47, SimulationTime(t=47, hour=23, day=1)),
        (48, SimulationTime(t=48, hour=0, day=2)),
        (167, SimulationTime(t=167, hour=23, day=6)),
    ],
)
def test_hour_and_day_are_derived_from_t(advances: int, expected: SimulationTime) -> None:
    clock = SimulationClock(168)
    for _ in range(advances):
        clock.advance()
    assert clock.time == expected
    assert clock.hour == expected.t % 24
    assert clock.day == expected.t // 24


def test_clock_finishes_after_all_steps() -> None:
    clock = SimulationClock(3)
    for _ in range(3):
        clock.advance()
    assert clock.is_finished
    assert clock.remaining == 0
    assert clock.progress == pytest.approx(1.0)


def test_clock_cannot_advance_past_the_end() -> None:
    clock = SimulationClock(1)
    clock.advance()
    with pytest.raises(RuntimeError, match="already finished"):
        clock.advance()


def test_clock_reset() -> None:
    clock = SimulationClock(5)
    clock.advance()
    clock.advance()
    clock.reset()
    assert clock.t == 0
    assert not clock.is_finished


def test_invalid_step_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        SimulationClock(0)
    with pytest.raises(ValueError, match="positive integer"):
        SimulationClock(-1)
