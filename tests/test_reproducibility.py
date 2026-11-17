"""Reproducibility tests for the A1 model.

The runs use the isolated doubles from ``tests/doubles.py``. They verify A1's
ownership of seed derivation and orchestration determinism; they do not claim
that the official A2/B/C components are implemented.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from core.model import GridModel
from tests.doubles import build_model


def _run(
    config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    seed: int,
    steps: int = 48,
) -> GridModel:
    model = build_model(config, monkeypatch, seed=seed, scenario="combined")
    for _ in range(steps):
        model.step()
    return model


def test_same_seed_and_config_produce_identical_logs(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _run(config, monkeypatch, seed=123)
    second = _run(config, monkeypatch, seed=123)

    assert_frame_equal(first.logger.get_log(), second.logger.get_log())
    assert_frame_equal(first.logger.get_detail_log(), second.logger.get_detail_log())
    assert [result.price for result in first.results] == [result.price for result in second.results]
    assert [result.unserved for result in first.results] == [
        result.unserved for result in second.results
    ]
    assert first.snapshot()["environment"] == second.snapshot()["environment"]


def test_different_seeds_produce_different_logs(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _run(config, monkeypatch, seed=1)
    second = _run(config, monkeypatch, seed=2)
    with pytest.raises(AssertionError):
        assert_frame_equal(first.logger.get_log(), second.logger.get_log())


def test_global_numpy_random_state_does_not_affect_runs(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    np.random.seed(1)
    first = _run(config, monkeypatch, seed=42, steps=12)
    np.random.seed(999)
    np.random.random(500)
    second = _run(config, monkeypatch, seed=42, steps=12)
    assert_frame_equal(first.logger.get_log(), second.logger.get_log())


def test_environment_forecast_is_reproducible(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = build_model(config, monkeypatch, seed=8)
    second = build_model(config, monkeypatch, seed=8)
    first.step()
    second.step()
    assert first.forecast(1, 6) == second.forecast(1, 6)


def test_logs_are_pandas_frames(config: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    model = _run(config, monkeypatch, seed=3, steps=2)
    assert isinstance(model.logger.get_log(), pd.DataFrame)
    assert len(model.logger.get_detail_log()) > 0


def test_same_seed_produces_identical_full_168_step_runs(
    config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _run(config, monkeypatch, seed=77, steps=168)
    second = _run(config, monkeypatch, seed=77, steps=168)

    assert len(first.results) == len(second.results) == 168
    assert_frame_equal(first.logger.get_log(), second.logger.get_log())
    assert first.results[-1].price == second.results[-1].price
    assert first.results[-1].unserved == second.results[-1].unserved
