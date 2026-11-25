"""Tests for metrics, statistics and the experiment runner (Team D2)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from core.config import PROJECT_ROOT, load_config
from experiments.metrics import compute_run_metrics
from experiments.report import write_report
from experiments.runner import (
    RESULTS_DIR,
    ExperimentRunner,
    ExperimentSpec,
    build_experiment_grid,
)
from experiments.stats import paired_comparison, pairwise_comparisons, summarise_runs


def _log() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "price": [10.0, 20.0],
            "demand": [100.0, 100.0],
            "unserved_mw": [0.0, 10.0],
            "deferred_mw": [0.0, 5.0],
            "messages": [6.0, 3.0],
            "ue_hospital_1": [0.0, 2.0],
            "ue_residential_1": [0.0, 8.0],
            "sold_solar_1": [60.0, 50.0],
            "sold_thermal_1": [40.0, 35.0],
            "bought_hospital_1": [30.0, 30.0],
            "paid_hospital_1": [300.0, 600.0],
            "bought_residential_1": [60.0, 40.0],
            "paid_residential_1": [600.0, 400.0],
        }
    )


def test_empty_log_returns_zero_metrics() -> None:
    metrics = compute_run_metrics(pd.DataFrame())
    assert metrics["social_cost"] == 0.0
    assert metrics["ue_total"] == 0.0
    assert metrics["storage_cycles"] == 0.0


def test_metrics_match_the_hand_computed_values(config: dict[str, Any]) -> None:
    metrics = compute_run_metrics(_log(), config, "normal")

    assert metrics["generation_cost"] == pytest.approx(5 * 110 + 45 * 75)
    assert metrics["voll_penalty"] == pytest.approx(1000 * 2 + 100 * 8)
    assert metrics["social_cost"] == pytest.approx(3925 + 2800)
    assert metrics["cost_total"] == pytest.approx(6725)
    assert metrics["cost_mean_per_mwh"] == pytest.approx(6725 / 185)
    assert metrics["unserved_energy_mwh"] == pytest.approx(10)
    assert metrics["deferred_energy_mwh"] == pytest.approx(5)
    assert metrics["ue_hospital"] == pytest.approx(2)
    assert metrics["ue_residential"] == pytest.approx(8)
    assert metrics["ue_factory"] == pytest.approx(0)
    assert metrics["hospital_outage_hours"] == 1
    assert metrics["price_mean"] == pytest.approx(15)
    assert metrics["price_volatility"] == pytest.approx(np.std([10.0, 20.0], ddof=1))
    assert metrics["par"] == pytest.approx(100.0 / 92.5)
    assert metrics["gini"] == pytest.approx(0.1)
    assert metrics["messages"] == pytest.approx(9)
    assert metrics["renewable_share"] == pytest.approx(110 / 185)
    assert metrics["self_sufficiency"] == pytest.approx(0.95)
    assert metrics["recovery_time"] == 0.0
    assert metrics["storage_cycles"] == 0.0


def _metric_frame() -> pd.DataFrame:
    rows = []
    for seed in range(5):
        base = 100.0 + seed
        rows.append(
            {
                "system": "auction",
                "scenario": "normal",
                "seed": seed,
                "social_cost": base,
                "ue_total": 10.0 + seed,
            }
        )
        rows.append(
            {
                "system": "auction_q",
                "scenario": "normal",
                "seed": seed,
                "social_cost": base + 2.0,
                "ue_total": 5.0 + seed,
            }
        )
    return pd.DataFrame(rows)


def test_summary_reports_mean_std_and_bootstrap_interval() -> None:
    summary = summarise_runs(_metric_frame(), ["social_cost"], bootstrap=200)
    auction = summary[(summary["system"] == "auction")].iloc[0]
    assert auction["count"] == 5
    assert auction["mean"] == pytest.approx(102.0)
    assert auction["std"] == pytest.approx(np.std([100, 101, 102, 103, 104], ddof=1))
    assert auction["ci_low"] <= auction["mean"] <= auction["ci_high"]
    assert auction["min"] == pytest.approx(100.0)
    assert auction["max"] == pytest.approx(104.0)


def test_paired_comparison_uses_paired_seeds() -> None:
    comparison = paired_comparison(_metric_frame(), "auction", "auction_q", ["social_cost"])
    row = comparison.iloc[0]
    assert row["n_pairs"] == 5
    assert row["mean_difference"] == pytest.approx(2.0)
    assert row["relative_effect"] == pytest.approx(2.0 / 102.0)
    assert 0.0 < row["p_value"] <= 1.0

    with pytest.raises(ValueError, match="unknown system"):
        paired_comparison(_metric_frame(), "auction", "missing")


def test_pairwise_comparison_applies_bonferroni_correction() -> None:
    pairwise = pairwise_comparisons(_metric_frame(), ["social_cost", "ue_total"])
    assert len(pairwise) == 2
    assert set(pairwise["bonferroni_tests"]) == {2}
    assert np.allclose(
        pairwise["p_adjusted"], np.minimum(1.0, pairwise["p_value"] * 2.0)
    )


def test_official_grid_has_600_unique_experiments(config: dict[str, Any]) -> None:
    grid = build_experiment_grid(config)
    assert len(grid) == 600
    assert len({spec.experiment_id for spec in grid}) == 600
    assert grid[0] == ExperimentSpec(system="central_6h", scenario="normal", seed=0)
    assert grid[-1].system == "auction_q"
    assert grid[-1].scenario == "combined"
    assert grid[-1].seed == 29


def test_runner_select_validates_and_filters(config: dict[str, Any]) -> None:
    runner = ExperimentRunner(config, output_dir="unused", progress=False)
    selected = runner.select(seeds=2, systems=["auction"], scenarios=["normal"])
    assert len(selected) == 2
    assert [spec.seed for spec in selected] == [0, 1]

    with pytest.raises(ValueError, match="unknown systems"):
        runner.select(systems=["nope"])
    with pytest.raises(ValueError, match="unknown scenarios"):
        runner.select(scenarios=["nope"])
    with pytest.raises(ValueError, match="seeds must be positive"):
        runner.select(seeds=0)


def test_runner_executes_one_real_experiment(config: dict[str, Any], tmp_path: Any) -> None:
    runner = ExperimentRunner(config, output_dir=tmp_path, progress=False)
    path = runner.run(ExperimentSpec(system="auction", scenario="normal", seed=0))

    assert path.exists()
    frame = pd.read_csv(path)
    assert len(frame) == config["simulation"]["steps"]
    assert list(frame.columns[:5]) == ["system", "scenario", "seed", "t", "hour"]
    assert frame["price"].notna().all()
    assert (frame["price"] >= 0.0).all()


def test_runner_requires_a_qtable_for_auction_q(config: dict[str, Any], tmp_path: Any) -> None:
    runner = ExperimentRunner(
        config, output_dir=tmp_path, qtable_path=tmp_path / "missing.npy", progress=False
    )
    with pytest.raises(FileNotFoundError, match="Run `python -m ai.train` first"):
        runner.run(ExperimentSpec(system="auction_q", scenario="normal", seed=0))


def test_partial_run_report_never_overwrites_the_official_report(
    config: dict[str, Any], tmp_path: Any
) -> None:
    runner = ExperimentRunner(config, output_dir=tmp_path, progress=False)
    partial = runner.select(seeds=1, systems=["auction"], scenarios=["normal"])

    assert runner._report_destination(partial) == tmp_path / "REPORT.md"

    official = ExperimentRunner(config, output_dir=RESULTS_DIR, progress=False)
    assert official._report_destination(official.grid) == (
        PROJECT_ROOT / "docs" / "report" / "REPORT.md"
    )
    assert official._report_destination(partial) == RESULTS_DIR / "REPORT.md"

    explicit = ExperimentRunner(
        config,
        output_dir=tmp_path,
        report_path=tmp_path / "custom.md",
        progress=False,
    )
    assert explicit._report_destination(partial) == tmp_path / "custom.md"


def test_report_generation_keeps_hypotheses_and_calibration_caveat(tmp_path: Any) -> None:
    rows = []
    for seed in range(3):
        rows.append(
            {
                "system": "auction",
                "scenario": "normal",
                "seed": seed,
                "social_cost": 100.0 + seed,
                "ue_total": 1.0,
                "ue_hospital": 0.0,
                "ue_residential": 0.5,
                "ue_factory": 0.5,
                "hospital_outage_hours": 0.0,
                "recovery_time": 0.0,
                "par": 1.1,
                "messages": 10.0,
                "renewable_share": 0.3,
            }
        )
        rows.append(
            {
                "system": "central_6h",
                "scenario": "normal",
                "seed": seed,
                "social_cost": 110.0 + seed,
                "ue_total": 50.0,
                "ue_hospital": 0.0,
                "ue_residential": 0.0,
                "ue_factory": 50.0,
                "hospital_outage_hours": 0.0,
                "recovery_time": 0.0,
                "par": 1.2,
                "messages": 5.0,
                "renewable_share": 0.4,
            }
        )
    metrics = pd.DataFrame(rows)
    summary = summarise_runs(metrics)
    pairwise = pairwise_comparisons(metrics)
    report_path = tmp_path / "REPORT.md"

    write_report(
        metrics,
        summary,
        pairwise,
        [],
        config=load_config(),
        output_path=report_path,
        results_dir=tmp_path,
    )

    text = report_path.read_text(encoding="utf-8")
    assert "### Reading the results" in text
    assert "factory" in text
    assert "## 3. Hypotheses" in text
    assert "## 6. Limitations" in text
    assert "## 7. Reproduction" in text
