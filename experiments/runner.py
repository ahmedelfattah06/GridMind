"""Experiment runner (Team D2) - interface skeleton.

Owner: D2 (Experiments, Metrics and Reports).
Status: TODO. The experiment grid and the execution loop are not implemented in
this skeleton. The official design is 4 systems x 5 scenarios x 30 seeds = 600
experiments; the counts themselves are validated in ``core.config``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


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
    """Enumerate the official experiment grid.

    Args:
        config: Validated configuration containing the ``experiments`` section.

    Returns:
        The ``4 * 5 * 30 = 600`` experiment specifications in a deterministic
        order (systems, then scenarios, then seeds).

    Raises:
        NotImplementedError: Always, until Team D2 implements the grid.

    TODO(D2): implement the deterministic enumeration and its counters.
    """

    raise NotImplementedError("TODO(D2): build_experiment_grid is not implemented")


class ExperimentRunner:
    """Executes the experiment grid (Team D2)."""

    def __init__(self, config: Mapping[str, Any], output_dir: str | Path = "results") -> None:
        """Create the runner.

        Args:
            config: Validated configuration.
            output_dir: Root folder for run artefacts.

        TODO(D2): validate the output layout (see PD-14).
        """

        self._config = config
        self._output_dir = Path(output_dir)

    @property
    def grid(self) -> list[ExperimentSpec]:
        """The 600 experiment specifications.

        TODO(D2): return ``build_experiment_grid(self._config)`` once implemented.
        """

        raise NotImplementedError("TODO(D2): ExperimentRunner.grid is not implemented")

    def run(self, spec: ExperimentSpec) -> Path:
        """Run one experiment and persist its artefacts.

        Raises:
            NotImplementedError: Always, until Team D2 implements the runner.

        TODO(D2): implement one run and its artefact output.
        """

        raise NotImplementedError("TODO(D2): ExperimentRunner.run is not implemented")

    def run_all(self) -> list[Path]:
        """Run the complete experiment grid.

        Raises:
            NotImplementedError: Always, until Team D2 implements the runner.

        TODO(D2): implement the batch execution.
        """

        raise NotImplementedError("TODO(D2): ExperimentRunner.run_all is not implemented")
