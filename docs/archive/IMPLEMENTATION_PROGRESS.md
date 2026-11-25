# GridMind implementation progress

> **Historical record (pre-audit).** This checklist records the build up to
> 140 passing tests. The post-audit suite is 151 tests; see
> [`docs/GRIDMIND_AUDIT_REPORT.md`](../GRIDMIND_AUDIT_REPORT.md). The file is kept
> for provenance and is not maintained.

Local working checklist for the autonomous implementation. Status values:
`todo`, `in-progress`, `done`, `blocked`.

| Phase | Scope | Status | Notes |
| --- | --- | --- | --- |
| 0 | Repository audit, guide extraction, baseline tests | done | 79 passed, 19 skipped at baseline |
| 1 | A2 weather, demand, supply | done | equations from project guide 4.3 |
| 2 | A3 events, scenario catalogue, event manager | done | timings from guide section 8 |
| 3 | B1 base/consumer agents | done | fixed + flexible bids, rebound, deferral |
| 4 | B2 producer/storage agents and rule policy | done | adaptive markup, SoC limits, policy plug-in |
| 5 | B3 double auction, negotiation, settlement | done | uniform price, partial matching, UE/deferred split |
| 6 | C1 central LP and market adapter | done | scipy linprog highs, 1h/6h replanning |
| 7 | C2 tabular Q-learning, training, qtable.npy | done | 60 states, 3 actions, eps-greedy |
| 8 | D2 experiment grid, metrics, statistics, plots, report | done | 600 runs, bootstrap, Wilcoxon |
| 9 | D1 Streamlit dashboard (4 pages) | done | live, market board, compare, learning |
| 10 | Integration, unskip acceptance tests, full run | done | pytest, 600-run full grid, dashboard check |

## Test log

- Baseline: `pytest -q` -> 79 passed, 19 skipped.
- Acceptance suites activated: `pytest -q` -> 140 passed, 0 skipped.
- New suites: `test_agents.py`, `test_market.py`, `test_ai.py`,
  `test_experiments.py`, `test_factory.py`.
- Integration: real-auction energy conservation, central LP energy balance,
  Q-table training and one end-to-end runner execution.
- Full Q-training: 2000 episodes, `qtable.npy` shape `(60, 3)`, 180 non-zero entries,
  final mean reward 691.955.
- Full experiment grid: 4 systems x 5 scenarios x 30 seeds = 600 runs.
- Final grid verification: `raw.csv` has 600 rows, `steps.csv` has 100,800 rows,
  zero missing values, and six figures were regenerated.
- Final test run after the grid: `pytest -q` -> 140 passed, 0 skipped.
- Dashboard: Streamlit `AppTest` loaded all four pages with zero exceptions; the
  demo button switches to `combined`, navigates to Live Simulation and autostarts.
- Cross-system comparison caveat: the central LP sheds standing factory load because
  the configured factory VOLL (40) is below the thermal marginal cost (45). This is
  documented in `docs/report/REPORT.md` and `docs/report/FINAL_REPORT.md`.

## Artefacts

- `qtable.npy`, `results/learning_curve.csv`, `results/training_metadata.json`.
- `results/raw.csv`, `results/steps.csv`, `results/metrics_summary.csv`,
  `results/stats_pairwise.csv`, `results/run_metadata.json`.
- `results/figures/fig1..fig6`, `results/runs/` (600 per-run step logs).
- `docs/report/REPORT.md` (generated experimental report).
- `docs/report/FINAL_REPORT.md` (final delivery report).
