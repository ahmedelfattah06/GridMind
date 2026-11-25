# GridMind - Final Delivery Report

> **Historical record (pre-audit).** This delivery report was written on
> 18 November 2026 against the pre-fix code and artefacts. The current test suite
> is 151 passed, and the saved results predate the audit fixes. For the current
> defect log see [`../GRIDMIND_AUDIT_REPORT.md`](../GRIDMIND_AUDIT_REPORT.md); for
> the post-fix reference see
> [`../GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md`](../GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md).

**Status:** complete and runnable locally
**Date:** 18 November 2026
**Design:** 168 hourly steps (7 days), 15 agents (hard cap 20), 4 systems, 5 scenarios, 30 seeds, 600 experiments.

This report describes what was delivered, how it was verified, what the executed
experiments show, and how to run the project. Every experimental number below comes
from the generated artefacts in `results/`; the automatically generated companion
report is [`REPORT.md`](REPORT.md).

## 1. Executive summary

- The complete GridMind stack is implemented: environment, agents, double-auction
  market, bilateral negotiation, settlement, central LP planner, tabular Q-learning,
  experiment runner, statistics, figures, report generation and a four-page
  Streamlit dashboard.
- The full official grid completed: **600/600 runs**, each with 168 hourly steps.
  The aggregate artefacts contain **600 metric rows** and **100,800 step rows**, with
  no missing values.
- The test suite is green: **140 passed, 0 skipped**.
- Q-learning training completed: 2000 episodes, a `(60, 3)` Q-table with 180 non-zero
  entries, final mean reward **691.955**.
- The dashboard loads all four pages with **zero exceptions** in Streamlit's
  `AppTest` harness, including the demo button that switches to the `combined`
  scenario and starts playback.
- The experiments produce a nuanced result rather than a simple "decentralised wins"
  story. The auction is much more reliable and recovers from disruptions. Central-1h
  has the lowest modelled social cost, partly because the LP permanently sheds
  low-VOLL factory load; central-6h is cheaper than the auction in some scenarios but
  more expensive in `combined` and `weather_shift`. That calibration effect is
  documented explicitly below.

## 2. What was completed

### Simulation core

- **Environment (A2):** weather-driven solar and wind output, time-of-day and
  weekday demand profiles, synthetic noise, and the documented supply equations.
- **Events and scenarios (A3):** all five official scenarios with timings from the
  project guide: plant outage and demand spike at step 86, weather shift at step 72,
  and the combined scenario.
- **Agents (B1/B2):** hospital, residential and factory consumers with fixed and
  flexible bids, rebound and deferral; thermal, solar, wind and peaker producers with
  adaptive markups; battery storage with SoC limits and a policy plug-in. The fleet
  resolves to 15 agents by default and is capped at 20.
- **Market (B3):** uniform-price double auction with at most three rounds, partial
  matching, bilateral negotiation with consumer/producer counter-offers, and
  settlement that serves shortfall, then defers flexible energy, then reports the
  remainder as unserved. Deferred energy is re-bid in the next hour.
- **Central planning (C1):** a SciPy `linprog` cost-minimisation model plus a
  `CentralMarketAdapter` with 1-hour and 6-hour replanning modes.
- **Learning (C2):** tabular Q-learning over 60 storage states and 3 actions
  (wait/charge/discharge), trained with epsilon-greedy exploration and persisted as
  `qtable.npy`.
- **Assembly:** `core/factory.py` builds every official mode from real components;
  mocks are accepted only in the explicitly labelled `mock` mode.

### Experiments, reporting and dashboard

- `experiments/metrics.py`: social cost, generation cost, VOLL penalty, unserved
  energy by consumer type, hospital outage hours, price mean/volatility, PAR, Gini,
  recovery time, message count, renewable share, self-sufficiency and storage cycles.
- `experiments/stats.py`: per-cell summary with bootstrap intervals and paired
  Wilcoxon signed-rank tests with Bonferroni correction.
- `experiments/plots.py`: the six official figures.
- `experiments/runner.py`: the full 4 x 5 x 30 grid, per-run CSV logs and aggregate
  artefacts.
- `experiments/report.py`: the generated experimental report, including explicit
  hypothesis verdicts and calibration caveats.
- `ui/app.py`: four dashboard pages - Live Simulation, Market Board, Compare and
  Learning - reading real simulation state and persisted artefacts.

### Documentation

- `README.md`: setup, commands, architecture and roadmap.
- `docs/contracts.md`: frozen interfaces and status.
- `docs/architecture.md`: component and data-flow description.
- `docs/decision_log.md`: resolved pending decisions PD-01..PD-15.
- `docs/archive/IMPLEMENTATION_PROGRESS.md`: historical phase checklist and test log.
- `docs/report/REPORT.md`: generated experimental report.
- `docs/report/FINAL_REPORT.md`: this delivery report.

## 3. Verification results

| Check | Command | Result |
| --- | --- | --- |
| Test suite | `.venv\Scripts\python.exe -m pytest -q` | **140 passed, 0 skipped** in 10.01 s (latest run) |
| Q-learning | `.venv\Scripts\python.exe -m ai.train` | 2000 episodes, Q-table `(60, 3)`, 180 non-zero entries, final mean reward 691.955 |
| Full grid | `.venv\Scripts\python.exe -m experiments.runner --seeds 30` | 600/600 runs, 246.49 s total, 0.41 s/run |
| Data integrity | inspected `results/raw.csv` and `steps.csv` | 600 rows and 100,800 rows, zero missing values, every system/scenario cell has 30 seeds |
| Figures | inspected `results/figures/` | all six PNG figures regenerated and non-empty |
| Dashboard | Streamlit `AppTest` against `ui/app.py` | all four pages: 0 exceptions; demo button switches to `combined`, navigates to Live Simulation and autostarts |
| Report | `docs/report/REPORT.md` | regenerated from the 600-run artefacts |

The full grid run log is `results/grid_log.txt`. The run metadata, including the
exact design and timing, is `results/run_metadata.json`.

## 4. Experimental highlights

### Social cost

Mean social cost over 30 seeds (lower is better):

| Scenario | central_6h | central_1h | auction | auction_q |
| --- | ---: | ---: | ---: | ---: |
| Combined | 331,450 | 317,259 | 324,651 | 324,301 |
| Demand Spike | 323,704 | 308,206 | 320,469 | 319,487 |
| Normal | 314,988 | 302,450 | 315,657 | 315,213 |
| Plant Outage | 322,438 | 309,304 | 317,652 | 317,164 |
| Weather Shift | 339,215 | 314,812 | 323,510 | 322,694 |

Across all scenarios, mean social cost is 326,359 for `central_6h`, 310,406 for
`central_1h`, 320,388 for `auction` and 319,772 for `auction_q`.

### Reliability

- **Hospital load is fully served in every run:** hospital UE and hospital outage
  hours are exactly zero in all 20 system/scenario cells.
- The auction keeps total UE between **113 and 324 MWh** across the five scenarios.
  In event scenarios it returns to its pre-event price/UE band within **3.2-28.1 h**.
- `central_6h` and `central_1h` carry roughly **3,250 MWh** of unserved factory load
  even in `normal`, because the LP prefers to shed load whose VOLL (40) is below the
  thermal marginal cost (45). Their recovery times hit the end of the event window
  (82 h after the step-86 events, 96 h after the step-72 weather shift) in all eight
  event-system cells; those values are censored, not measured recovery times.

### Hypothesis verdicts

**H1 - central planning is cheaper in normal conditions.** Descriptively supported
for `central_6h`: 314,987.7 versus 315,657.2 for the auction, a 0.21% difference.
That difference is **not significant** after Bonferroni correction (adjusted
p = 1.00). `central_1h` is cheaper still at 302,449.8 (-4.18% versus the auction),
but most of that advantage comes from the standing factory-load shedding described
above. H1 holds for the modelled objective, not as proof of cheaper supply per MWh
actually served.

**H2 - the decentralised auction recovers better from disruptions.** Weakly
supported. In the plant-outage scenario the auction recovers in 26.07 h with
270.43 MWh UE, versus 82.00 h (censored) and 3,516.66 MWh for `central_6h`. In the
combined scenario the figures are 28.13 h / 324.12 MWh versus 82.00 h / 3,607.04 MWh.
The raw 4/4 vote favours the auction, but the central system's UE is dominated by a
time-invariant factory shortfall, so the cross-system comparison is not a clean
measure of outage response alone.

**H3 - Q-learning storage improves on the fixed rule.** Partially supported on social
cost only. Q lowers modelled social cost in **5/5 scenarios** by **0.11%-0.31%**, but
raises total UE in **5/5 scenarios** by **6.96%-15.76%**, concentrated in factory load.
PAR also worsens slightly (1.346 versus 1.344 in `normal`). The policy shifts unserved
energy toward the lowest-VOLL consumer; it is not a reliability improvement.

### Statistical comparison

- 360 paired Wilcoxon comparisons, Bonferroni corrected over all tests; 244 are
  significant at adjusted p < 0.05.
- The paired-seed design makes even small differences detectable. Significance
  measures consistency across seeds, not practical importance.
- The complete table is `results/stats_pairwise.csv`; the generated report shows the
  hypothesis-relevant subset.

### Learning

The reward curve improves from a negative start to a final mean reward of **691.955**
over 50-episode windows. The learned policy is dominated by discharge actions at high
SoC and selected charge actions in low-price states; the full table is
`results/learning_curve.csv` and the heatmap is
`results/figures/fig5_qtable_heatmap.png`.

## 5. Limitations

- **Capacity-only model.** There is no AC power flow, voltage, frequency or network
  topology; every MW is assumed transportable.
- **Synthetic data.** Weather, demand and supply are generated from documented
  equations. No external or real grid data are used.
- **VOLL calibration dominates central results.** The central LP minimises fuel cost
  plus configured VOLL. With factory VOLL 40 below the thermal marginal cost 45, it
  sheds about 3,250 MWh of factory load in every scenario. This lowers central
  generation cost and makes cross-system social-cost and UE comparisons sensitive to
  the VOLL calibration. It is an economic outcome, not a solver failure.
- **Censored recovery metric.** Recovery is censored when the stability criterion is
  never met. For the central systems, the standing factory shortfall means the
  criterion never clears after an event, so their recovery times equal the remaining
  window.
- **Limited learning scope.** Only the storage policy learns; consumers and producers
  follow fixed rules. A 60-state tabular Q-table is not general multi-agent
  reinforcement learning.
- **One configuration, 30 seeds.** Results are specific to the calibrated
  configuration and official seeds; they should not be extrapolated to real grids
  without validation.
- **Conservative statistics.** Bonferroni correction over 360 tests is conservative,
  but the paired seeds still make small differences statistically detectable.

## 6. How to run

From the repository root in PowerShell:

```bat
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

pytest
python -m ai.train
python -m experiments.runner --seeds 30
streamlit run ui/app.py
```

If PowerShell blocks activation, call the interpreter directly:

```bat
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ai.train
.venv\Scripts\python.exe -m experiments.runner --seeds 30
.venv\Scripts\python.exe -m streamlit run ui/app.py
```

Useful smaller runs:

```bat
:: Check the grid without executing it
.venv\Scripts\python.exe -m experiments.runner --dry-run

:: Two-seed smoke run in a separate directory
.venv\Scripts\python.exe -m experiments.runner --seeds 2 --systems auction --scenarios normal --output results/smoke
```

`auction_q` requires `qtable.npy`; `python -m ai.train` creates it. The runner
refuses to start `auction_q` without a Q-table rather than silently using an
untrained policy.

## 7. Artefacts

| Path | Contents |
| --- | --- |
| `results/raw.csv` | one metric row per run (600 rows) |
| `results/steps.csv` | one row per simulated hour across all runs (100,800 rows) |
| `results/metrics_summary.csv` | mean, standard deviation, bootstrap CI, min and max |
| `results/stats_pairwise.csv` | paired Wilcoxon tests and Bonferroni-adjusted p-values |
| `results/runs/` | per-experiment step logs |
| `results/figures/` | six report figures |
| `results/run_metadata.json` | design, timing and Q-table provenance |
| `results/learning_curve.csv` | Q-learning reward curve |
| `results/training_metadata.json` | training hyperparameters and final reward |
| `qtable.npy` | trained `(60, 3)` Q-table |
| `docs/report/REPORT.md` | generated experimental report |
| `docs/report/FINAL_REPORT.md` | this report |

## 8. Deliverable checklist

- [x] All production modules implemented with real logic; no `TODO`, `FIXME` or
      `NotImplementedError` remains in production code.
- [x] Frozen interfaces in `docs/contracts.md` preserved.
- [x] Acceptance tests activated; **140 passed, 0 skipped**.
- [x] Q-learning trained and persisted.
- [x] Full **600-experiment** grid completed with paired seeds.
- [x] Six figures and the generated experimental report produced from real output.
- [x] Four-page Streamlit dashboard verified with full artefacts.
- [x] Documentation and decision log updated.
- [ ] Git commit/push: intentionally not performed; the task prohibited Git writes
      and remote interaction. All changes remain uncommitted in the working tree.
