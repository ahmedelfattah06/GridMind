# GridMind

**A multi-agent smart-energy trading and optimisation simulation.**

GridMind models a small synthetic city in which autonomous consumers, producers
and batteries trade electricity hour by hour. The same physical scenario is run
under centralised planning and under decentralised negotiation so the two market
mechanisms can be compared when a power plant fails or demand suddenly rises.

> **Research question:** Is decentralised negotiation between autonomous agents
> more robust than centralised planning when power plants fail or demand suddenly
> increases?

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-151%20passed-brightgreen)
![Data](https://img.shields.io/badge/data-100%25%20synthetic-informational)

---

## 1. Status

The full stack is implemented and locally runnable:

* the simulation core, synthetic weather, demand and generation models;
* consumer, producer and storage agents;
* a uniform-price double auction, negotiation rounds and settlement;
* a rolling-horizon central LP planner and a tabular Q-learning battery policy;
* a 600-run experiment pipeline with metrics, statistics, figures and a report;
* a four-page Streamlit dashboard.

**Verification:** `151 passed` in the automated test suite. The post-audit
technical reference, defence guide and defect log are in
[`docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md`](docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md),
[`docs/GRIDMIND_ACADEMIC_PRESENTATION_GUIDE.md`](docs/GRIDMIND_ACADEMIC_PRESENTATION_GUIDE.md)
and [`docs/GRIDMIND_AUDIT_REPORT.md`](docs/GRIDMIND_AUDIT_REPORT.md).

> **Artefact warning.** The saved files in `results/`, `qtable.npy` and
> `docs/report/` were generated **before** the audit fixes. Re-run training and
> the grid before quoting their numbers; see [§8](#8-reproducing-the-results).

---

## 2. Key facts

| Item | Value |
| --- | --- |
| Horizon | 168 hourly steps (7 days) per run |
| Agents | 15 by default, maximum 20 |
| Auction market | Uniform-price double auction, at most 3 negotiation rounds |
| Systems | `central_6h`, `central_1h`, `auction`, `auction_q` |
| Scenarios | `normal`, `plant_outage`, `demand_spike`, `weather_shift`, `combined` |
| Seeds | 30 per system/scenario pair |
| Experiments | 4 × 5 × 30 = **600** |
| Units | MW for power, MWh for energy per hourly step |
| Data | 100 % synthetic, generated from mathematical equations |

### The four comparison systems

| System | Market mechanism | Battery policy |
| --- | --- | --- |
| `central_6h` | LP dispatch, replanned every 6 h | Managed by the LP |
| `central_1h` | LP dispatch, replanned every hour | Managed by the LP |
| `auction` | Double auction with negotiation | Rule-based price threshold |
| `auction_q` | Same auction | Learned Q-table (`qtable.npy`) |

---

## 3. Quick start (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Python 3.11 or newer is required. No paid API, external data service or deep-RL
framework is used.

Run the dashboard:

```bat
.venv\Scripts\streamlit.exe run ui/app.py
```

---

## 4. Repository layout

```text
gridMind/
├── config/
│   ├── default.yaml            # fleet, prices, VOLL, environment, experiment grid
│   └── scenarios.yaml          # the five official disruption scenarios
├── core/
│   ├── config.py               # YAML validation, official constants, seed streams
│   ├── clock.py                # 168-hour clock and hour/day mapping
│   ├── logger.py               # Pandas step log and CSV export
│   ├── model.py                # GridModel orchestration and frozen StepResult
│   ├── environment.py          # composition of weather, demand and supply
│   ├── weather.py              # temperature, cloud, wind, solar profile
│   ├── demand.py               # residential, factory and hospital demand
│   ├── supply.py               # solar, wind, thermal and peaker availability
│   ├── events.py               # event manager and environment modifiers
│   └── factory.py              # full model assembly for every system
├── agents/
│   ├── base.py                 # BaseAgent contract
│   ├── consumer.py             # hospital, residential and factory agents
│   ├── producer.py             # solar, wind, thermal and peaker agents
│   └── storage.py              # battery physics and policy interface
├── market/
│   ├── orders.py               # Order / Trade value objects
│   ├── auction.py              # uniform-price double auction and settlement
│   └── negotiation.py          # validated negotiation rounds
├── ai/
│   ├── central_lp.py           # LP planner, dispatch plan and market adapter
│   ├── qlearning.py            # 60-state tabular Q-learning
│   └── train.py                # offline training entry point
├── experiments/
│   ├── runner.py               # 600-run grid and artefact writer
│   ├── metrics.py              # official per-run metrics
│   ├── stats.py                # bootstrap, Wilcoxon and Bonferroni
│   ├── plots.py                # six report figures
│   └── report.py               # Markdown report generation
├── ui/
│   ├── app.py                  # Streamlit entry point
│   ├── theme.py                # design tokens and global CSS
│   ├── components.py           # KPI cards, headers, badges, empty states
│   ├── charts.py               # Plotly figures
│   ├── data.py                 # artefact loaders and label catalogues
│   ├── state.py                # live-model lifecycle
│   └── views/                  # live, market, compare, learning
├── results/                    # generated artefacts (Git-ignored)
├── tests/                      # 151 automated tests
├── docs/                       # guides, contracts, audit and generated report
├── qtable.npy                  # learned storage policy
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 5. How one hour works

`GridModel` orchestrates; it contains no bidding or market mathematics.

1. The environment draws weather and realised demand and computes available generation.
2. Active events modify demand, generation and cloud cover.
3. Every agent receives a local observation. Agents never see event names.
4. Round 1 orders are collected.
5. The market clears round 1.
6. Auction modes run rounds 2–3 of counter-offers; central modes skip negotiation.
7. Settlement converts unmatched demand into deferred or unserved energy.
8. Agents update their state from the settlement.
9. The immutable `StepResult` is logged.

Component graph and equations are documented in
[`docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md`](docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md).

---

## 6. Running the tests

```bat
.venv\Scripts\python.exe -m pytest -q
```

```text
151 passed
```

The suite covers configuration validation, clock arithmetic, frozen contracts,
weather/demand/supply, event windows, full model orchestration, energy
conservation, reproducibility, agents, auction and settlement, negotiation,
central LP and adapter execution, Q-learning, metrics, statistics, runner
artefacts, report generation and model assembly.

The audit added 11 regression tests for the defects it fixed; each fails on the
pre-fix code. See [`tests/README.md`](tests/README.md) and
[`docs/GRIDMIND_AUDIT_REPORT.md`](docs/GRIDMIND_AUDIT_REPORT.md).

---

## 7. Running experiments

Train the Q-table, run the official 600-run grid, then open the dashboard:

```bat
.venv\Scripts\python.exe -m ai.train
.venv\Scripts\python.exe -m experiments.runner --seeds 30
.venv\Scripts\streamlit.exe run ui/app.py
```

Quick smoke checks (write to a temporary directory, never to `results/`):

```bat
.venv\Scripts\python.exe -m ai.train --episodes 20 ^
  --output "%TEMP%\gridmind\quick_qtable.npy" ^
  --curve "%TEMP%\gridmind\quick_curve.csv"

.venv\Scripts\python.exe -m experiments.runner --seeds 1 ^
  --systems auction central_1h --scenarios normal ^
  --output "%TEMP%\gridmind\smoke" --quiet
```

`auction_q` reads `qtable.npy`. A quick training run writes a *different* table
and does not replace the evaluation artefact unless you point `--output` at it.

Programmatic use:

```python
from core.config import load_config
from core.factory import build_model

config = load_config()
model = build_model(config, seed=0, mode="auction", scenario="demand_spike")
while not model.clock.is_finished:
    model.step()
model.logger.export_csv("results/run.csv")
```

Official modes are `central_6h`, `central_1h`, `auction` and `auction_q`.

### Runner outputs

| File | Content |
| --- | --- |
| `runs/<experiment_id>.csv` | One run's step log |
| `raw.csv` | One metrics row per run |
| `steps.csv` | All step rows with system/scenario/seed |
| `metrics_summary.csv` | Mean, SD, bootstrap CI, min, max |
| `stats_pairwise.csv` | Paired Wilcoxon tests with Bonferroni correction |
| `figures/fig1..fig6*.png` | Six report figures |
| `run_metadata.json` | Selected grid, timings, Q-table and curve provenance |
| `REPORT.md` | Markdown report |

A full official grid written to `results/` updates `docs/report/REPORT.md`. A
filtered or alternative-output run writes `REPORT.md` inside its own output
directory; an explicit `report_path` overrides both. Aggregate files
(`raw.csv`, `steps.csv`, …) are still rewritten in whichever output directory is
chosen, so use a temporary directory for smoke runs.

---

## 8. Reproducing the results

A run is determined by `(config, seed, mode, scenario, qtable)`. All randomness
uses `derive_rng(seed, stream)`; there are no global random calls, forecasts
consume no randomness, and per-agent streams are derived from stable agent ids.
The test suite verifies identical 168-step logs for the same seed.

Regenerate the delivered artefacts in this order:

```bat
.venv\Scripts\python.exe -m ai.train
.venv\Scripts\python.exe -m experiments.runner --seeds 30
```

This overwrites `qtable.npy`, `results/*` and `docs/report/REPORT.md`. Archive the
current pre-audit artefacts first if they are cited anywhere. Do not mix pre-fix
and post-fix numbers in one table.

---

## 9. Dashboard

```bat
.venv\Scripts\streamlit.exe run ui/app.py
```

| Page | What it shows |
| --- | --- |
| **Live Simulation** | Step/play/reset the selected system and scenario; network, environment, event timeline, price/supply/demand/SoC history |
| **Market Board** | Final clearing hour: order depth, negotiation rounds, net positions, supply mix, messages and trades |
| **Compare Systems** | Filtered experiment grid: cost, reliability and fairness KPIs, matrices, Wilcoxon tests, figures |
| **Learning** | Q-table heatmap, learning curve, state explorer, rule-vs-Q evidence and an optional fresh comparison |

The dashboard only reads model snapshots and persisted artefacts; it never
invents values. Missing files produce an explicit empty/error state with the
command needed to regenerate them.

`snapshot()["t"]` is the **next** hour to execute while `price` and `unserved`
describe the **last completed** hour. The UI labels this as progress plus the
last clearing result; the behaviour is intentional and tested.

---

## 10. Documentation

| Document | Purpose |
| --- | --- |
| [`docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md`](docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md) | Post-audit reference: architecture, equations, modules, metrics, limitations |
| [`docs/GRIDMIND_ACADEMIC_PRESENTATION_GUIDE.md`](docs/GRIDMIND_ACADEMIC_PRESENTATION_GUIDE.md) | 50 defence questions, presentation outline, claim-to-evidence map |
| [`docs/GRIDMIND_AUDIT_REPORT.md`](docs/GRIDMIND_AUDIT_REPORT.md) | Scope, confirmed defects, fixes, tests, residual risks |
| [`docs/PROJECT_GUIDE.md`](docs/PROJECT_GUIDE.md) | Source-grounded architecture guide (written before the audit) |
| [`docs/architecture.md`](docs/architecture.md) | Layers, step flow and ownership |
| [`docs/contracts.md`](docs/contracts.md) | Frozen integration interfaces |
| [`docs/decision_log.md`](docs/decision_log.md) | Accepted, superseded and pending decisions |
| [`docs/report/REPORT.md`](docs/report/REPORT.md) | Generated experimental report |
| [`docs/report/FINAL_REPORT.md`](docs/report/FINAL_REPORT.md) | Final delivery report |
| [`tests/README.md`](tests/README.md) | Test ownership and activation notes |
| [`docs/archive/`](docs/archive/) | Historical pre-audit QA and progress notes |

---

## 11. Configuration

* Every tunable parameter lives in `config/default.yaml`; scenario events live in
  `config/scenarios.yaml`.
* `core.config.load_config()` validates both files and raises `ConfigError` with
  the dotted path of an invalid value.
* The 168-step horizon, 3-round cap, four systems, five scenarios, 30 seeds and
  20-agent cap are validated against the official design and cannot change
  silently.
* Randomness is stream-based: adding a component or an agent does not shift
  another component's draws.

---

## 12. Limitations

GridMind is a stylised model, not a digital twin:

* one copper-plate market, no network, losses or locational prices;
* no unit commitment, ramping, reserves or frequency dynamics;
* synthetic weather and demand, not measured traces;
* central dispatch may rationally shed factory load because `VOLL(factory)=40`
  is below the thermal marginal cost `45`, so central and auction systems are not
  compared on identical served energy;
* the auction's deferred-energy settlement can lose a failed rebound from the
  unserved accounting;
* the central price is a marginal-cost proxy, not the LP dual;
* tabular Q-learning is coarse and trained offline; no deep RL is used.

The technical documentation and audit report state each of these explicitly.
Do not claim external validity or a welfare ranking from social cost alone.

---

## 13. Coding standards

* Python 3.11+, type hints, docstrings on modules and public APIs.
* English names, comments and commit messages.
* Black, line length 100 (`black .`).
* No global random calls; use `derive_rng(seed, stream)`.
* No magic numbers in business logic; read from configuration.
* Explicit exceptions (`ConfigError`, `ValueError`, `RuntimeError`).

---

## 14. Development notes

* Contracts are frozen in [`docs/contracts.md`](docs/contracts.md); contract
  changes require agreement across the owning modules.
* Official modes contain no placeholders. `mode="mock"` exists only for
  orchestration tests and must never be used for reported results.
* The working tree contains uncommitted changes from the audit; run the tests
  before and after any edit.

Historical team ownership, branch workflow and phase checklist were removed from
this README during the post-audit cleanup. The pre-audit QA and progress records
are preserved under [`docs/archive/`](docs/archive/).
