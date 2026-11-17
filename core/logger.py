"""Simulation logger built on Pandas.

The logger stores one row per simulation step plus a long format detail table
for per-agent values (unserved energy, deferred energy, generation and battery
state of charge). It is deliberately independent from the model so that it can
be tested and reused by the experiments team.

The step log always contains the official columns listed in
:data:`LOG_COLUMNS`. Per-consumer unserved energy is added as ``ue_<agent_id>``
and per-battery state of charge as ``soc_<agent_id>``. Those dynamic columns are
discovered from the :class:`~core.model.StepResult` of each step, so additional
metrics never break the stable interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from core.clock import HOURS_PER_DAY

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    from core.model import StepResult

# Stable columns present in every log, including an empty one.
LOG_COLUMNS: tuple[str, ...] = (
    "t",
    "hour",
    "day",
    "price",
    "supply",
    "demand",
    "messages",
    "unserved_mw",
    "deferred_mw",
    "generation_mw",
    "soc_mean",
)

# Dynamic per-agent columns. The logger never assumes a fixed fleet size.
UE_PREFIX = "ue_"
SOC_PREFIX = "soc_"

DETAIL_COLUMNS: tuple[str, ...] = (
    "t",
    "agent_id",
    "unserved_mw",
    "deferred_mw",
    "generation_mw",
    "soc",
)


class SimulationLogger:
    """Collects step level simulation records in Pandas data frames."""

    def __init__(self) -> None:
        self._rows: list[dict[str, Any]] = []
        self._details: list[dict[str, Any]] = []
        self._columns: list[str] = list(LOG_COLUMNS)

    @property
    def columns(self) -> tuple[str, ...]:
        """Columns of the step log, in stable order."""

        return tuple(self._columns)

    def record_step(self, result: "StepResult") -> None:
        """Append one completed step to the log.

        Missing optional per-agent values are treated as ``0.0``. New agent
        identifiers extend the dynamic columns without reordering the existing
        ones.

        Args:
            result: The :class:`core.model.StepResult` of the executed step.
        """

        row = self._build_row(result)
        self._register_columns(row)
        self._rows.append(row)
        self._record_details(result)

    def get_log(self) -> pd.DataFrame:
        """Return the full step log as a data frame.

        Returns:
            A data frame whose leading columns are always :data:`LOG_COLUMNS`.
            Dynamic ``ue_*`` and ``soc_*`` columns follow. An empty logger still
            returns the stable columns so that CSV export is always valid.
        """

        frame = pd.DataFrame(self._rows, columns=list(self._columns))
        return frame.fillna(0.0)

    def get_detail_log(self) -> pd.DataFrame:
        """Return the per-agent detail log in long format.

        Returns:
            A data frame with :data:`DETAIL_COLUMNS`, empty when no step has been
            recorded yet.
        """

        return pd.DataFrame(self._details, columns=list(DETAIL_COLUMNS))

    def export_csv(self, path: str | Path) -> Path:
        """Write the step log to a CSV file.

        Args:
            path: Destination file. Missing parent directories are created.

        Returns:
            The resolved destination path.
        """

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.get_log().to_csv(destination, index=False)
        return destination

    def export_detail_csv(self, path: str | Path) -> Path:
        """Write the per-agent detail log to a CSV file."""

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.get_detail_log().to_csv(destination, index=False)
        return destination

    def last_price(self) -> float:
        """Return the most recently logged price, or ``0.0`` when empty."""

        return float(self._rows[-1]["price"]) if self._rows else 0.0

    def reset(self) -> None:
        """Clear every recorded row and dynamic column."""

        self._rows.clear()
        self._details.clear()
        self._columns = list(LOG_COLUMNS)

    def __len__(self) -> int:
        return len(self._rows)

    def _build_row(self, result: "StepResult") -> dict[str, Any]:
        soc_values = [float(value) for value in result.soc.values()]
        row: dict[str, Any] = {
            "t": int(result.t),
            "hour": int(result.t % HOURS_PER_DAY),
            "day": int(result.t // HOURS_PER_DAY),
            "price": float(result.price),
            "supply": float(result.supply_mw),
            "demand": float(result.demand_mw),
            "messages": int(result.messages),
            "unserved_mw": float(sum(result.unserved.values())),
            "deferred_mw": float(sum(result.deferred.values())),
            "generation_mw": float(sum(result.generation.values())),
            "soc_mean": float(sum(soc_values) / len(soc_values)) if soc_values else 0.0,
        }
        for agent_id, value in result.unserved.items():
            row[f"{UE_PREFIX}{agent_id}"] = float(value)
        for agent_id, value in result.soc.items():
            row[f"{SOC_PREFIX}{agent_id}"] = float(value)
        return row

    def _register_columns(self, row: dict[str, Any]) -> None:
        for column in sorted(row):
            if column not in self._columns:
                self._columns.append(column)

    def _record_details(self, result: "StepResult") -> None:
        t = int(result.t)
        agent_ids = sorted(
            set(result.unserved) | set(result.deferred) | set(result.generation) | set(result.soc)
        )
        for agent_id in agent_ids:
            self._details.append(
                {
                    "t": t,
                    "agent_id": agent_id,
                    "unserved_mw": float(result.unserved.get(agent_id, 0.0)),
                    "deferred_mw": float(result.deferred.get(agent_id, 0.0)),
                    "generation_mw": float(result.generation.get(agent_id, 0.0)),
                    "soc": float(result.soc.get(agent_id, 0.0)),
                }
            )
