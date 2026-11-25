"""Experiment runner (Team D2).

Executes the official design: four systems x five scenarios x 30 seeds = 600
runs of 168 hourly steps. Every run uses exactly the same seed within a
scenario, so systems are compared on paired weather and demand noise.

Artefacts written to the output directory:

* ``raw.csv`` -- one row of metrics per run,
* ``steps.csv`` -- one row per simulated step across all runs,
* ``metrics_summary.csv`` -- mean, standard deviation and bootstrap interval,
* ``stats_pairwise.csv`` -- paired Wilcoxon tests with Bonferroni correction,
* ``figures/`` -- the six official report figures,
* ``run_metadata.json`` -- exact design and timing for reproducibility.

Usage::

    python -m experiments.runner --seeds 30
    python -m experiments.runner --seeds 2 --systems auction --scenarios normal
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from core.config import PROJECT_ROOT, load_config
from core.factory import DEFAULT_QTABLE_PATH, build_model
from experiments.metrics import compute_run_metrics
from experiments.plots import generate_all_figures
from experiments.report import write_report
from experiments.stats import pairwise_comparisons, summarise_runs

RESULTS_DIR = PROJECT_ROOT / "results"


@dataclass(frozen=True)
class ExperimentSpec:
    """One experiment of the official design.

    Attributes:
        system: Comparison system id.
        scenario: Official scenario key.
        seed: Simulation seed.
    """

    system: str
    scenario: str
    seed: int

    @property
    def experiment_id(self) -> str:
        """Stable identifier used for result folders and file names."""

        return f"{self.system}__{self.scenario}__seed{self.seed}"


def build_experiment_grid(config: Mapping[str, Any]) -> list[ExperimentSpec]:
    """Enumerate the official experiment grid deterministically.

    Args:
        config: Validated configuration containing the ``experiments`` section.

    Returns:
        The ``systems x scenarios x seeds`` experiment specifications in
        deterministic order (system, then scenario, then seed).
    """

    experiments = config["experiments"]
    systems = [str(system) for system in experiments["systems"]]
    scenarios = [str(scenario) for scenario in experiments["scenarios"]]
    count = int(experiments["seeds"])
    start = int(experiments.get("seed_start", 0))
    return [
        ExperimentSpec(system=system, scenario=scenario, seed=start + offset)
        for system in systems
        for scenario in scenarios
        for offset in range(count)
    ]


class ExperimentRunner:
    """Executes experiment specifications and persists their artefacts."""

    def __init__(
        self,
        config: Mapping[str, Any],
        output_dir: str | Path = "results",
        *,
        qtable_path: str | Path | None = None,
        report_path: str | Path | None = None,
        progress: bool = True,
    ) -> None:
        """Create the runner.

        Args:
            config: Validated configuration.
            output_dir: Root folder for artefacts.
            qtable_path: Q-table used by ``auction_q``. Defaults to
                ``qtable.npy`` in the project root.
            report_path: Optional Markdown report destination. The default
                keeps the official ``docs/report/REPORT.md`` for a complete
                official run and writes ``REPORT.md`` inside ``output_dir`` for
                filtered smoke runs, so a partial run cannot overwrite the
                delivered report.
            progress: Whether to print one progress line per run.
        """

        self._config = config
        self._output_dir = Path(output_dir)
        self._qtable_path = Path(qtable_path) if qtable_path is not None else DEFAULT_QTABLE_PATH
        self._report_path = Path(report_path) if report_path is not None else None
        self._progress = progress
        self._rows: list[dict[str, Any]] = []
        self._steps: list[pd.DataFrame] = []

    @property
    def grid(self) -> list[ExperimentSpec]:
        """The complete experiment grid defined by the configuration."""

        return build_experiment_grid(self._config)

    @property
    def output_dir(self) -> Path:
        """Root folder for artefacts."""

        return self._output_dir

    def select(
        self,
        *,
        seeds: int | None = None,
        seed_start: int | None = None,
        systems: Sequence[str] | None = None,
        scenarios: Sequence[str] | None = None,
    ) -> list[ExperimentSpec]:
        """Build a filtered grid for smoke runs and the dashboard.

        Args:
            seeds: Number of seeds to run. ``None`` means the configured 30.
            seed_start: First seed. ``None`` means ``experiments.seed_start``.
            systems: Optional subset of systems, preserving official order.
            scenarios: Optional subset of scenarios, preserving official order.

        Raises:
            ValueError: If a requested system or scenario is not official.
        """

        experiments = self._config["experiments"]
        official_systems = [str(value) for value in experiments["systems"]]
        official_scenarios = [str(value) for value in experiments["scenarios"]]
        selected_systems = list(systems) if systems is not None else official_systems
        selected_scenarios = list(scenarios) if scenarios is not None else official_scenarios
        unknown_systems = set(selected_systems) - set(official_systems)
        unknown_scenarios = set(selected_scenarios) - set(official_scenarios)
        if unknown_systems:
            raise ValueError(f"unknown systems: {sorted(unknown_systems)}")
        if unknown_scenarios:
            raise ValueError(f"unknown scenarios: {sorted(unknown_scenarios)}")
        count = int(experiments["seeds"]) if seeds is None else int(seeds)
        if count < 1:
            raise ValueError("seeds must be positive")
        start = int(experiments.get("seed_start", 0)) if seed_start is None else int(seed_start)
        return [
            ExperimentSpec(system=system, scenario=scenario, seed=start + offset)
            for system in selected_systems
            for scenario in selected_scenarios
            for offset in range(count)
        ]

    def run(self, spec: ExperimentSpec) -> Path:
        """Run one experiment and persist its step log.

        Returns:
            Path of the per-run step CSV under ``output_dir/runs``.
        """

        if spec.system == "auction_q" and not self._qtable_path.exists():
            raise FileNotFoundError(
                f"Q-table not found for auction_q: {self._qtable_path}. "
                "Run `python -m ai.train` first."
            )
        model = build_model(
            self._config,
            spec.seed,
            spec.system,
            spec.scenario,
            qtable_path=self._qtable_path if spec.system == "auction_q" else None,
        )
        while not model.clock.is_finished:
            model.step()

        log = model.logger.get_log()
        metrics = compute_run_metrics(log, self._config, spec.scenario)
        row: dict[str, Any] = {
            "system": spec.system,
            "scenario": spec.scenario,
            "seed": spec.seed,
            "experiment_id": spec.experiment_id,
        }
        row.update(metrics)
        self._rows.append(row)

        step_frame = log.copy()
        step_frame.insert(0, "seed", spec.seed)
        step_frame.insert(0, "scenario", spec.scenario)
        step_frame.insert(0, "system", spec.system)
        self._steps.append(step_frame)

        run_path = self._output_dir / "runs" / f"{spec.experiment_id}.csv"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        step_frame.to_csv(run_path, index=False)
        return run_path

    def run_all(self, specs: Sequence[ExperimentSpec] | None = None) -> list[Path]:
        """Run the selected grid and write every aggregate artefact.

        Args:
            specs: Experiments to execute. Defaults to the full 600-run grid.

        Returns:
            Paths of the per-run step CSVs.
        """

        selected = list(specs) if specs is not None else self.grid
        self._rows.clear()
        self._steps.clear()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        paths: list[Path] = []
        for index, spec in enumerate(selected, start=1):
            paths.append(self.run(spec))
            if self._progress:
                print(
                    f"[{index:4d}/{len(selected)}] {spec.experiment_id}",
                    flush=True,
                )
        elapsed = time.perf_counter() - started
        self._write_aggregates(selected, elapsed)
        return paths

    # ------------------------------------------------------------------
    # Aggregate artefacts
    # ------------------------------------------------------------------

    def _write_aggregates(self, specs: Sequence[ExperimentSpec], elapsed: float) -> None:
        metrics = pd.DataFrame(self._rows)
        steps = pd.concat(self._steps, ignore_index=True) if self._steps else pd.DataFrame()
        metrics.to_csv(self._output_dir / "raw.csv", index=False)
        steps.to_csv(self._output_dir / "steps.csv", index=False)

        summary = summarise_runs(metrics)
        summary.to_csv(self._output_dir / "metrics_summary.csv", index=False)
        pairwise = pairwise_comparisons(metrics)
        pairwise.to_csv(self._output_dir / "stats_pairwise.csv", index=False)

        curve_path, curve = _load_learning_curve(self._output_dir, RESULTS_DIR)
        qtable = _load_qtable(self._qtable_path)
        figures = generate_all_figures(
            metrics,
            steps,
            curve,
            qtable,
            self._output_dir / "figures",
            event_start=_event_start(self._config, "plant_outage"),
        )
        report_path = write_report(
            metrics,
            summary,
            pairwise,
            figures,
            config=self._config,
            output_path=self._report_destination(specs),
            results_dir=self._output_dir,
        )
        metadata = {
            "runs": len(specs),
            "systems": sorted({spec.system for spec in specs}),
            "scenarios": sorted({spec.scenario for spec in specs}),
            "seeds": sorted({spec.seed for spec in specs}),
            "steps_per_run": int(self._config["simulation"]["steps"]),
            "elapsed_seconds": round(elapsed, 3),
            "seconds_per_run": round(elapsed / max(1, len(specs)), 4),
            "qtable": str(self._qtable_path),
            "qtable_loaded": bool(np.any(qtable)),
            "learning_curve": str(curve_path) if curve_path is not None else None,
            "learning_curve_loaded": bool(not curve.empty),
            "report": str(report_path),
            "figures": [str(path) for path in figures],
        }
        (self._output_dir / "run_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

    def _report_destination(self, specs: Sequence[ExperimentSpec]) -> Path:
        """Return the report path appropriate for the selected grid.

        A filtered smoke run must never overwrite the delivered report under
        ``docs/report``; it writes its own report next to its artefacts.
        """

        if self._report_path is not None:
            return self._report_path
        official = {spec.experiment_id for spec in self.grid}
        selected = {spec.experiment_id for spec in specs}
        is_official = (
            selected == official
            and self._output_dir.resolve() == RESULTS_DIR.resolve()
        )
        if is_official:
            return PROJECT_ROOT / "docs" / "report" / "REPORT.md"
        return self._output_dir / "REPORT.md"


def _load_learning_curve(*directories: str | Path) -> tuple[Path | None, pd.DataFrame]:
    """Load the first learning curve found in the given directories."""

    seen: set[Path] = set()
    for directory in directories:
        path = Path(directory) / "learning_curve.csv"
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            return path, pd.read_csv(path)
    return None, pd.DataFrame()


def _load_qtable(path: Path) -> np.ndarray:
    if path.exists():
        return np.load(path, allow_pickle=False)
    return np.zeros((60, 3), dtype=float)


def _event_start(config: Mapping[str, Any], scenario: str) -> int:
    events = config.get("scenarios", {}).get(scenario, {}).get("events", []) or []
    if not events:
        return 0
    return int(min(int(event["start"]) for event in events))


def build_parser() -> argparse.ArgumentParser:
    """Return the command line parser for ``python -m experiments.runner``."""

    parser = argparse.ArgumentParser(
        prog="python -m experiments.runner",
        description="Run the GridMind experiment grid and generate the report.",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=None,
        help="Number of seeds per system/scenario (default: 30).",
    )
    parser.add_argument("--seed-start", type=int, default=None, help="First seed (default: 0).")
    parser.add_argument(
        "--systems",
        nargs="+",
        default=None,
        help="Optional subset of systems (central_6h central_1h auction auction_q).",
    )
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=None,
        help="Optional subset of scenarios.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_DIR,
        help="Artefact directory (default: results).",
    )
    parser.add_argument(
        "--qtable",
        type=Path,
        default=None,
        help="Q-table for auction_q (default: qtable.npy in the project root).",
    )
    parser.add_argument("--config", type=Path, default=None, help="Alternative config YAML.")
    parser.add_argument("--quiet", action="store_true", help="Disable per-run progress.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected grid size without executing it.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Command line entry point for the experiment runner."""

    args = build_parser().parse_args(argv)
    config = load_config(args.config) if args.config is not None else load_config()
    runner = ExperimentRunner(
        config,
        output_dir=args.output,
        qtable_path=args.qtable,
        progress=not args.quiet,
    )
    specs = runner.select(
        seeds=args.seeds,
        seed_start=args.seed_start,
        systems=args.systems,
        scenarios=args.scenarios,
    )
    print(
        f"Selected {len(specs)} experiments "
        f"({len({spec.system for spec in specs})} systems x "
        f"{len({spec.scenario for spec in specs})} scenarios x "
        f"{len({spec.seed for spec in specs})} seeds)."
    )
    if args.dry_run:
        return 0
    runner.run_all(specs)
    print(f"Artefacts written to {args.output.resolve()}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
