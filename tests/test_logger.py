"""Tests for the A1 Pandas logger and CSV export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from core.logger import DETAIL_COLUMNS, LOG_COLUMNS, SOC_PREFIX, UE_PREFIX, SimulationLogger
from core.model import StepResult
from market.orders import Order, Trade


def _result(t: int = 0, **overrides: object) -> StepResult:
    values: dict[str, object] = {
        "t": t,
        "price": 42.5,
        "supply_mw": 100.0,
        "demand_mw": 80.0,
        "unserved": {"hospital_1": 2.0, "factory_1": 1.0},
        "deferred": {"hospital_1": 0.0, "factory_1": 3.0},
        "trades": [Trade(buyer_id="hospital_1", seller_id="solar_1", qty_mw=4.0, price=42.5)],
        "orders": [
            Order(agent_id="hospital_1", side="buy", qty_mw=6.0, price=300.0, round=1),
            Order(agent_id="solar_1", side="sell", qty_mw=10.0, price=5.0, round=1),
        ],
        "messages": 2,
        "soc": {"battery_1": 0.5, "battery_2": 0.75},
        "generation": {"solar_1": 20.0, "wind_1": 15.0},
    }
    values.update(overrides)
    return StepResult(**values)  # type: ignore[arg-type]


def test_empty_log_has_stable_columns() -> None:
    logger = SimulationLogger()
    frame = logger.get_log()
    assert isinstance(frame, pd.DataFrame)
    assert frame.empty
    assert list(frame.columns) == list(LOG_COLUMNS)
    assert logger.get_detail_log().empty
    assert list(logger.get_detail_log().columns) == list(DETAIL_COLUMNS)
    assert len(logger) == 0
    assert logger.last_price() == 0.0


def test_log_records_official_and_per_agent_columns() -> None:
    logger = SimulationLogger()
    logger.record_step(_result())

    frame = logger.get_log()
    assert len(frame) == 1
    required = {"t", "price", "supply", "demand", "messages"}
    assert required.issubset(frame.columns)
    assert frame.loc[0, "t"] == 0
    assert frame.loc[0, "hour"] == 0
    assert frame.loc[0, "day"] == 0
    assert frame.loc[0, "price"] == pytest.approx(42.5)
    assert frame.loc[0, "supply"] == pytest.approx(100.0)
    assert frame.loc[0, "demand"] == pytest.approx(80.0)
    assert frame.loc[0, "messages"] == 2
    assert frame.loc[0, "unserved_mw"] == pytest.approx(3.0)
    assert frame.loc[0, "deferred_mw"] == pytest.approx(3.0)
    assert frame.loc[0, "generation_mw"] == pytest.approx(35.0)
    assert frame.loc[0, "soc_mean"] == pytest.approx(0.625)

    assert frame.loc[0, f"{UE_PREFIX}hospital_1"] == pytest.approx(2.0)
    assert frame.loc[0, f"{UE_PREFIX}factory_1"] == pytest.approx(1.0)
    assert frame.loc[0, f"{SOC_PREFIX}battery_1"] == pytest.approx(0.5)
    assert frame.loc[0, f"{SOC_PREFIX}battery_2"] == pytest.approx(0.75)


def test_new_dynamic_columns_are_zero_filled_for_older_rows() -> None:
    logger = SimulationLogger()
    logger.record_step(_result(t=0, unserved={"hospital_1": 1.0}, soc={}))
    logger.record_step(
        _result(
            t=1,
            unserved={"hospital_1": 0.0, "factory_1": 2.0},
            soc={"battery_1": 0.4},
        )
    )

    frame = logger.get_log()
    assert frame.loc[0, f"{UE_PREFIX}factory_1"] == pytest.approx(0.0)
    assert frame.loc[0, f"{SOC_PREFIX}battery_1"] == pytest.approx(0.0)
    assert frame.loc[1, f"{UE_PREFIX}hospital_1"] == pytest.approx(0.0)
    assert frame.loc[1, f"{UE_PREFIX}factory_1"] == pytest.approx(2.0)
    assert frame.loc[1, f"{SOC_PREFIX}battery_1"] == pytest.approx(0.4)


def test_detail_log_contains_every_agent_once_per_step() -> None:
    logger = SimulationLogger()
    logger.record_step(_result(t=0))
    logger.record_step(_result(t=1))
    detail = logger.get_detail_log()
    assert set(detail.columns) == set(DETAIL_COLUMNS)
    assert len(detail) == 12  # 2 steps x 6 distinct agents
    assert set(detail["agent_id"]) == {
        "battery_1",
        "battery_2",
        "factory_1",
        "hospital_1",
        "solar_1",
        "wind_1",
    }


def test_export_csv_round_trip(tmp_path: Path) -> None:
    logger = SimulationLogger()
    logger.record_step(_result(t=0))
    logger.record_step(_result(t=1))
    destination = logger.export_csv(tmp_path / "nested" / "steps.csv")
    assert destination.exists()

    frame = pd.read_csv(destination)
    assert len(frame) == 2
    assert list(frame.columns) == list(logger.get_log().columns)
    assert frame["t"].tolist() == [0, 1]
    assert f"{UE_PREFIX}hospital_1" in frame.columns
    assert f"{SOC_PREFIX}battery_1" in frame.columns


def test_export_detail_csv(tmp_path: Path) -> None:
    logger = SimulationLogger()
    logger.record_step(_result())
    destination = logger.export_detail_csv(tmp_path / "detail.csv")
    frame = pd.read_csv(destination)
    assert list(frame.columns) == list(DETAIL_COLUMNS)
    assert len(frame) == 6


def test_reset_clears_rows_and_dynamic_columns() -> None:
    logger = SimulationLogger()
    logger.record_step(_result())
    logger.reset()
    assert len(logger) == 0
    assert logger.columns == LOG_COLUMNS
    assert list(logger.get_log().columns) == list(LOG_COLUMNS)
