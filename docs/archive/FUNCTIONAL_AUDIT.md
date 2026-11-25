# GridMind Functional Audit

> **Historical record (pre-audit).** This document describes the repository as it
> was on 22 November 2026, before the correctness audit. Its test count and
> findings are superseded by
> [`docs/GRIDMIND_AUDIT_REPORT.md`](../GRIDMIND_AUDIT_REPORT.md). It is kept only
> as provenance for the earlier QA pass.

**Audit date:** 22 November 2026  
**Scope:** Functional QA of the implemented project; no application code or existing experiment artefacts were changed.  
**Testing environment:** Windows workspace, `.venv` Python 3.11 virtual environment, Streamlit 1.66.1.

---

## 1. Executive summary

GridMind is a substantially complete local research and demonstration project. The core 168-hour simulation, all three agent types, both auction variants, both central replanning modes, experiment metrics, generated artefacts, and all four Streamlit pages execute successfully in the available tests.

The existing test suite is green:

- `.venv\Scripts\python.exe -m pytest -q`
- **140 passed in 21.65 seconds**

Additional checks completed:

- 168-hour one-seed runs of `central_6h`, `central_1h`, `auction`, and `auction_q`
- runtime thermal-outage injection
- five-episode isolated Q-learning training in the session workspace
- official-grid dry run: 600 experiments
- filtered-grid dry run: 1 experiment
- Streamlit `AppTest` navigation of all four pages
- Live step, runtime-event, Market Board execute-hour, Compare filter, and Learning fresh-comparison interactions
- persistence and integrity checks for the existing 600-run artefacts

No existing project result was rewritten. The short training run wrote only to the Copilot session workspace.

**Competition-readiness conclusion: READY WITH DOCUMENTED LIMITATIONS, provided the Q-table and saved experiment artefacts are included.** The project is suitable for a competition demonstration in this repository's intended role as a synthetic, capacity-only simulation. It is not ready for claims of real-grid feasibility, real-world generalization, or a scientific advantage established beyond the calibrated 600-run model.

---

## 2. Status definitions

| Status | Meaning |
| --- | --- |
| **PASS** | The feature was executed successfully and produced expected real behavior or artefacts. |
| **PARTIAL** | The feature works, but a limitation, calibration issue, misleading label, or edge case reduces reliability or correctness. |
| **FAIL** | A required behavior failed. |
| **NOT VERIFIED** | Evidence was insufficient for an implementation-level conclusion. |
| **NOT IMPLEMENTED** | The requested capability does not exist. |

---

## 3. Detailed feature audit

| Area | Feature tested | Status | Actual result | Relevant file/function | Issue or limitation |
| --- | --- | --- | --- | --- | --- |
| Environment | Configuration and official-value validation | PASS | Configuration loads and fixed limits reject unsupported scope. | `core/config.py`, `load_config()`, `validate_config()` | None found. |
| Environment | Weather, demand, supply and independent seeds | PASS | Real weather/demand/supply calculations ran deterministically in the suite and smoke horizon. | `core/weather.py`, `core/demand.py`, `core/supply.py` | Synthetic capacity-only model. |
| Environment | Weather-shift scenario | PARTIAL | The scenario activates at step 72 for 24 hours and applies cloud override 0.2 and wind factor 0.5. | `config/scenarios.yaml`, `core/supply.py`, `core/events.py` | The implementation interprets `cloud_cover` directly as a solar multiplier. A 0.2 override is low cloud cover under this formula, not unambiguously the documented dense-cloud condition. |
| Environment | Scheduled and runtime events | PASS | Scenario events and a runtime thermal outage injected at hour 0 both affected the environment. Runtime smoke confirmed thermal generation fell from 50 MW to 15 MW. | `core/events.py`, `GridModel.inject_event()` | Runtime events exist only in the current session model. |
| Simulation | One-hour step orchestration | PASS | 168 one-hour steps completed for all four official systems in seed-0 smoke runs. | `core/model.py`, `GridModel._execute_step()` | None found in the smoke or test suite. |
| Simulation | Deterministic logging and snapshots | PASS | Each smoke run returned 168 rows and complete key log columns. | `core/logger.py`, `SimulationLogger.get_log()`, `GridModel.snapshot()` | Results are tied to one seed/configuration and should not be extrapolated. |
| Agents | Base contract | PASS | All official agents implement observe, decide, update and snapshot contracts. | `agents/base.py`, `BaseAgent` | None found. |
| Agents | Consumer bids and deferred/rebound load | PASS | Test suite covers hospital, residential and factory bidding, flexible load, forecast noise and rebound. | `agents/consumer.py`, `ConsumerAgent` | Deferred load is re-bid once in the following hour. |
| Agents | Producer bids and adaptive markup | PASS | Test suite and smoke runs exercised producer offers, marginal-cost floors and adaptive markup updates. | `agents/producer.py`, `ProducerAgent` | Markup can adapt only from each producer's amount sold. |
| Agents | Storage rule policy | PASS | Charge, discharge and wait behavior, SoC limits and efficiency dynamics execute successfully. | `agents/storage.py`, `RulePolicy`, `StorageAgent` | Rule policy depends on clearing-price history and fixed thresholds. |
| Auction | Uniform-price clearing | PASS | The suite validates descending bids, ascending asks, partial matching and uniform midpoint pricing. | `market/auction.py`, `DoubleAuction.clear()` | No bug found. |
| Auction | Settlement and payment conservation | PASS | Test suite validates trade settlement, zero-sum payments, deferral and unserved energy. | `market/auction.py`, `DoubleAuction.settle()` | Central and auction settlements intentionally differ in deferred-load handling. |
| Negotiation | Three-round counter-offers | PASS | One combined-hour smoke produced round-1 orders; the suite covers round validation and counter-offer limits. | `market/negotiation.py`, `RaiseFactorNegotiation` | Auction `messages` counts submitted orders, not a separate chat-message protocol. |
| Central LP | 6-hour and 1-hour planning | PASS | Both central modes completed 168 hours in the smoke run; the test suite covers planning and replanning. | `ai/central_lp.py`, `CentralLPPlanner`, `CentralMarketAdapter` | Forecast is noiseless and has no future-event knowledge. |
| Central LP | LP objective and shortage allocation | PARTIAL | The LP solves generation, unserved, charge and discharge variables with SciPy HiGHS. Central mode also intentionally allocates shortage by lowest VOLL. | `CentralLPPlanner._solve()`, `CentralMarketAdapter._execute()` | Factory VOLL 40 is below thermal marginal cost 45, so the LP produces standing factory shortfall. This is economically real for the calibration but can make central-versus-auction metrics misleading. |
| Central LP | Replanning intervals | PASS | `central_6h` uses a 6-hour interval and `central_1h` uses 1 hour. | `CentralMarketAdapter._needs_replan()` | No bug found. |
| Q-learning | State discretization | PASS | Five SoC bins, three price bins and four periods produce the expected 60-state index. | `ai/qlearning.py`, `state_index()`, `state_from_observation()` | Coarse discretization; only storage learns. |
| Q-learning | Training and epsilon-greedy updates | PASS | Full-suite tests and a five-episode isolated run executed successfully; the isolated table had shape `(60, 3)`. | `ai/train.py`, `TrainingPolicy`, `TabularQAgent.update()` | Short smoke does not establish policy quality. |
| Q-learning | Persisted Q-table loading | PASS | Existing `qtable.npy` loads as `(60, 3)` with finite values; malformed-shape and missing-file cases raise explicit errors. | `TabularQAgent.load()`, `QPolicy.from_file()` | `auction_q` requires the table before building. |
| Q-learning | `auction_q` execution | PASS | A 168-hour seed-0 smoke run completed. | `core/factory.py`, `build_model()`, `QPolicy` | Model quality is subject to the Q-learning reward and scenario calibration. |
| Simulation control | Play, pause, step, 10-hour run and reset | PASS | AppTest executed the Live Simulation step control and rendered reset/playback controls without exceptions. | `ui/views/live.py`, `ui/state.py` | Browser visual timing was not visually audited. |
| Runtime events | Trip thermal, demand spike and weather shift | PASS | Thermal injection was verified in backend smoke; all runtime buttons rendered and did not raise AppTest exceptions. | `ui/app.py`, `_inject_event()`, `GridModel.inject_event()` | Events are session-local and are not added to saved experiment grids. |
| Demo mode | Combined scenario navigation and autostart | PASS | AppTest switched to `combined`, navigated to Live Simulation and loaded with zero exceptions. | `ui/state.py`, `request_demo()`, `ui/app.py`, `gm_demo` | The demo repeatedly reruns live playback; an earlier 20-second AppTest timeout was cleared with a 60-second timeout. |
| Experiment runner | Official grid construction | PASS | Dry run confirmed 600 experiments: 4 systems × 5 scenarios × 30 seeds. | `experiments/runner.py`, `build_experiment_grid()` | The dry run does not execute them. |
| Experiment runner | Filtered and one-real-run execution | PASS | Existing test suite executes one real auction run and validates 168 rows. Filtered grid dry run produced 1 experiment. | `ExperimentRunner.run()`, `ExperimentRunner.run_all()` | The audit did not rerun all 600 experiments. |
| Experiment artefacts | Existing saved results | PASS | `raw.csv` has 600 rows, `steps.csv` 100,800 rows, summary 240 rows, pairwise table 360 rows, and no missing values. | `results/raw.csv`, `results/steps.csv`, `experiments/runner.py` | Existing artefacts may be stale if configuration changed after generation. |
| Metrics | Cost, UE, volatility, fairness and learning metrics | PASS | Test suite independently verifies hand-computed metrics, including social cost, VOLL, Gini and storage cycles. | `experiments/metrics.py`, `compute_run_metrics()` | Central factory shortfall and recovery censoring affect interpretation. |
| Statistics | Bootstrap and paired Wilcoxon | PASS | Test suite verifies 95% bootstrap summaries and Bonferroni-corrected paired tests. | `experiments/stats.py` | The correction and paired-seed design are conservative but make small differences statistically detectable. |
| Report | Markdown report generation | PASS | Test suite generated a report and verified calibration/hypothesis caveats. | `experiments/report.py`, `write_report()` | The report is only as valid as the generated metrics. |
| Dashboard | Live Simulation page | PASS | AppTest loaded the page with no exceptions; step and reset controls rendered. | `ui/views/live.py` | AppTest does not prove visual layout or browser rendering. |
| Dashboard | Market Board page | PASS | AppTest loaded the page and the execute-hour control returned a live snapshot with no exceptions. | `ui/views/market.py` | Central orders and trades are recorded snapshots, not auction clearing actions. |
| Dashboard | Compare page | PASS | AppTest loaded the page, filters rendered, and filtering to auction/normal returned no exceptions. | `ui/views/compare.py` | Static “30 seeds per cell” badge may be stale for smoke or custom subsets. |
| Dashboard | Learning page | PASS | AppTest loaded the page and the fresh 168-hour comparison control rendered and completed without exceptions. | `ui/views/learning.py` | Fresh comparison does not retrain and does not use the fleet sliders. |
| Dashboard | Charts | PASS | All four pages rendered without AppTest exceptions and generate Plotly figures from snapshots or loaded CSV/NPY files. | `ui/charts.py` | No pixel-level browser screenshot audit was performed. |
| Dashboard | Tables and downloads | PASS | AppTest exposed Streamlit dataframes and the Compare filter produced a two-row table state. | `ui/views/compare.py`, `_raw_tab()` | Download payload was not tested at browser-file level. |
| Dashboard | Missing-artifact handling | PARTIAL | Raw metrics and Q-table loaders raise explicit `DataError` messages; optional summary/pairwise/curve loaders return `None`. | `ui/data.py`, `_csv()`, `load_qtable()` | A custom/smoke experiment run can leave an incomplete or stale dashboard dataset. |
| Dashboard | Saved result provenance | PASS | Runtime KPIs come from `GridModel.snapshot()` and `SimulationLogger`; persisted pages load `raw.csv`, summary, pairwise, NPY and PNG files. | `ui/state.py`, `ui/data.py`, `ui/views/*.py` | There is no independent result hash or provenance banner beyond file metadata. |
| Dashboard | Hardcoded or mock values | PASS | No dashboard KPIs were found to be synthetic placeholders. Official labels and scenario descriptions are static text, while numerical values come from live or saved outputs. | `ui/data.py`, `ui/views/*.py`, `ui/charts.py` | Static labels, times and badge text describe configuration but are not substituted for measurements. |
| External systems | Real weather/grid data | NOT IMPLEMENTED | Synthetic equations and seeded noise only. | `core/weather.py`, `core/demand.py`, `core/supply.py` | No external data integration. |
| Security | Authentication and multi-user isolation | NOT IMPLEMENTED | Local Streamlit session only. | `ui/app.py` | Not intended for exposed multi-user deployment. |
| Power systems | AC power flow, voltage and topology | NOT IMPLEMENTED | Market and capacity dispatch operate without network constraints. | No corresponding module | This is outside the implemented capacity-only model. |
| Learning | Deep RL or multi-agent RL | NOT IMPLEMENTED | Only one tabular storage policy learns. | `ai/qlearning.py`, `ai/train.py` | No DQN, PPO or MARL implementation. |
| Browser visual QA | Pixel layout and responsive breakpoints | NOT VERIFIED | AppTest validated rendering state, but no screenshot or real-browser width matrix was run. | `ui/theme.py`, `ui/app.py` | A real visual check is recommended on target-screen sizes. |

---

## 4. Test results

### 4.1 Full automated suite

Command:

```bat
.venv\Scripts\python.exe -m pytest -q
```

Result:

- **140 passed**
- **0 failed**
- **21.65 seconds**

The suite covers configuration, clock, contracts, environment, orchestration, reproducibility, agents, auction, negotiation, central LP, Q-learning, experiment metrics/statistics/runner/report, and factory assembly.

### 4.2 Backend smoke matrix

One 168-hour seed-0 run was executed for each official system:

| System | Log rows | Completed hour | Mean clearing/dispatch price | Result |
| --- | ---: | ---: | ---: | --- |
| `central_6h` | 168 | 168 | 43.738095 | PASS |
| `central_1h` | 168 | 168 | 43.375000 | PASS |
| `auction` | 168 | 168 | 51.048718 | PASS |
| `auction_q` | 168 | 168 | 51.138004 | PASS |

All key log columns were non-null. The auction combined-scenario smoke returned round-1 orders and messages.

### 4.3 Runtime event smoke

A thermal-outage event was injected into an auction model at step 0 for 12 steps with thermal capacity factor 0.3.

- Event became active immediately.
- Thermal generation in the resulting snapshot was **15 MW**, as 50 MW × 0.3.
- Result: PASS.

### 4.4 Q-learning smoke

An isolated five-episode training run was executed in the session workspace, not in project `results/` or `qtable.npy`.

- Q-table shape: `(60, 3)`
- Finite values: yes
- Learning curve: 1 checkpoint
- Result: PASS.

The existing project Q-table was also loaded and validated:

- Shape: `(60, 3)`
- Finite values: yes

### 4.5 Experiment-grid checks

- Full official grid dry run: 600 experiments selected.
- Filtered auction/normal/1-seed dry run: 1 experiment selected.
- Existing per-run artefact integrity: 600 rows and 20 system/scenario cells.
- Existing steps: 100,800 rows.
- Existing seeds per cell: 30.
- Existing missing cells or values: none detected.

No full 600-run campaign was executed during this audit.

### 4.6 Streamlit AppTest

All four pages loaded with zero rendered AppTest exceptions:

| Page | Exception count |
| --- | ---: |
| Live Simulation | 0 |
| Market Board | 0 |
| Compare | 0 |
| Learning | 0 |

Additional controls produced no AppTest exception:

- Live Simulation `Step 1h`
- runtime `Trip thermal plant`
- Market Board `Execute one hour`
- Compare one-system/one-scenario filter
- Demo navigation and autostart
- Learning fresh auction versus auction-Q comparison

The isolated demo run initially exceeded AppTest's 20-second timeout because playback rerenders keep the script active. A 60-second rerun completed with:

- exception count: 0
- scenario: `combined`
- page: `Live Simulation`

---

## 5. Discovered bugs and risks

### 5.1 Weather-shift cloud-cover semantics

**Severity:** Medium to high for scientific interpretation.

**Evidence:**

- `config/scenarios.yaml` describes weather shift as dense cloud and weak wind.
- `core.events.py` sets `cloud_override: 0.2`.
- `core/supply.py` computes solar as `capacity * solar_profile * cloud_cover`.

Under the implementation, lower `cloud_cover` means greater solar availability. A value of 0.2 may therefore represent 20% cover, while the scenario description and weather name may imply dense cloud. The configuration can be scientifically corrected by choosing a cloud fraction plus a solar attenuation formula such as `1 - cloud_cover`, or by explicitly defining the override as a multiplier and updating all documentation. The audit did not change it.

**Status:** PARTIAL.

### 5.2 Static dashboard labels can misdescribe subset or smoke data

**Severity:** Low to medium.

**Evidence:**

- `ui/views/compare.py` displays a static `30 seeds per cell` badge.
- `ui/views/learning.py` describes saved evidence as `600-run evidence` even if a filtered or smoke `raw.csv` is loaded.

The actual KPI and table logic reads the loaded table, but static headings and badges do not adapt to a custom result directory or subset. They can mislead a judge or operator when smoke data is displayed.

**Recommended fix:** derive badge text from `experiment_counts(raw)` and require or display full-grid status explicitly.

### 5.3 Missing Q-table is silently converted to zeros by the experiment runner

**Severity:** Low to medium.

**Evidence:**

`experiments.runner._load_qtable()` returns `np.zeros((60, 3))` when `qtable.npy` is missing. This is safe for auction-only runs because the runner rejects `auction_q` before execution, but it can generate a misleading all-zero static Q-table figure for a subset that does not include `auction_q`.

**Recommended fix:** return an explicit missing-artefact state to plot/report code, or only attempt the Q-table figure when a usable table exists.

### 5.4 Central-planner calibration overwhelms reliability interpretation

**Severity:** Medium and deliberate in code.

**Evidence:**

- Factory VOLL is 40.
- Thermal marginal cost is 45.
- Central LP models unserved demand with VOLL cost.

The planner therefore rationally sheds standing factory load in normal and event scenarios. The current VOLL calibration makes central social cost and unserved-energy metrics sensitive to an economic threshold, not just disruption resilience.

**Recommended fix:** add sensitivity runs with a thermal marginal cost or VOLL calibration that separates standing-load economics from disruption response, or label every central result as model-calibration-dependent.

### 5.5 Central recovery metric is censoring rather than recovery in standing-shortfall cells

**Severity:** Medium.

**Evidence:**

`experiments.metrics._recovery_time()` returns the remaining window if the price/UE stability criterion is never met. The central systems can therefore report `steps - event_start` for standing factory shortfall instead of an observed recovery time.

**Recommended fix:** add separate columns for censored recovery and actual recovery, or plot them with censored markers instead of interpreting the value as elapsed recovery.

### 5.6 Browser-level visual QA is incomplete

**Severity:** Low.

All four pages passed AppTest and no backend exceptions were observed, but AppTest does not validate screenshot appearance, font loading, touch behavior or precise responsive layout.

**Recommended fix:** run a short real-browser screenshot pass at desktop and narrow widths.

---

## 6. Unverified features

The following features are not verified by the available evidence:

- Real-grid or real-market performance
- Browser screenshot fidelity and responsive CSS across all supported dimensions
- Downloaded CSV behavior at the OS/browser level
- Concurrent multi-user Streamlit behavior
- Deployment behind TLS, authentication or a reverse proxy
- Long-duration training convergence beyond the existing 2000-episode artefact
- External market, weather or demand API integration
- AC network constraints or congestion
- Cross-system behavior on configurations outside the official 15-agent, 168-hour calibration

---

## 7. Missing-feature assessment

The following requested or assumed product capabilities do not exist:

- AC power flow, voltage, frequency or line constraints
- Real weather, demand or market data
- Deep learning or multi-agent reinforcement learning
- Consumer or producer learning
- Authentication or database-backed multi-user sessions
- Automatic dashboard retraining
- Independent result provenance or cryptographic artifact hashes
- External deployment and operations controls

The dashboard's `Fresh 168-hour comparison` does run models, but it does not train or persist a new Q-table.

---

## 8. Dashboard data-provenance check

The audit found no evidence of fabricated numeric dashboard KPIs.

**Live Simulation**

- `GridModel.snapshot()` supplies clock, environment, agent, trade and unserved state.
- `SimulationLogger.get_log()` supplies history, so sparkline and step-table values come from executed steps.

**Market Board**

- Uses `snapshot["orders"]`, `snapshot["trades"]`, `snapshot["price"]`, `snapshot["messages"]` and the real step log.
- Central mode explicitly calls out the absence of an auction order book clearing mechanism.

**Compare**

- Uses `results/raw.csv` for KPIs and run data.
- Uses `metrics_summary.csv` and `stats_pairwise.csv` for summary/statistics.
- Uses `results/figures/*.png` exactly as generated.

**Learning**

- Loads `qtable.npy`, `learning_curve.csv`, `training_metadata.json` and the static learning figures.
- The fresh comparison executes real `auction` and `auction_q` models for 168 hours, but uses the persisted table and does not retrain.

Static text such as system labels, scenario descriptions and the 168-hour horizon is configuration/UX copy, not fabricated metric data.

---

## 9. Recommended fixes

### Priority 1

1. Resolve the weather-shift/cloud-cover convention and regenerate affected results if the equation or override is changed.
2. Make recovery-time output explicitly include a censored flag.
3. Add explicit missing-Q-table handling to the experiment plot/report pipeline.

### Priority 2

4. Derive the Compare “30 seeds” badge from loaded artefacts rather than hardcoding it.
5. Derive saved Learning evidence text from the actual system/scenario counts in `raw.csv`.
6. Add UI text that identifies filtered subsets, custom result directories and censored central results.

### Priority 3

7. Run a real-browser screenshot and narrow-width layout audit.
8. Add a persisted configuration fingerprint or artefact manifest to distinguish stale results from the current YAML.
9. Add optional result provenance/metadata to the dashboard header.

---

## 10. Final readiness assessment

GridMind is **ready for a competition demonstration as a complete, locally runnable synthetic simulation**.

The strongest evidence is:

- 140/140 existing tests pass.
- All official systems complete 168-hour smoke runs.
- Q-learning trains and loads through real code.
- The 600-run artefacts are present and internally complete.
- All dashboard pages pass AppTest navigation.
- Main live, market, compare, learning and demo controls execute without exceptions.
- Numeric dashboard values originate from snapshots or persisted simulation artefacts.

The main demonstration caveat is scientific honesty:

- This is a capacity-only synthetic model, not a real power-grid simulation.
- Central-LP results are strongly affected by VOLL calibration and standing factory shedding.
- Recovery values for central event scenarios can be censored.
- The weather-shift cloud convention needs a documented correction or explicit multiplier semantics.
- Q-learning improves only selected modelled cost outcomes and has not been proven as a general reliability improvement.

For a competition presentation, the project should be presented as a complete agent-based simulation and transparent experimental comparison, not as validated real-grid evidence.
