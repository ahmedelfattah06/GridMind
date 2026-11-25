# Decision Log

Every decision that is not fixed by the official specification is recorded here.
The original pending decisions were resolved during implementation; the final
rules are listed in "Resolved implementation decisions" and are reflected in the
code and configuration.

Date format: ISO 8601. Status values: `accepted`, `pending`, `superseded`.

## Bootstrap decisions

| ID | Date | Owner | Status | Decision | Rationale |
| --- | --- | --- | --- | --- | --- |
| D-01 | 2026-10-30 | A1 | accepted | The repository root *is* the project root: `core/`, `agents/`, `market/`, `ai/`, `experiments/`, `ui/`, `tests/`, `config/`, `docs/` are top-level packages/folders, matching the official tree. | Avoids an unnecessary nested `gridmind/gridmind/` package and keeps imports short. |
| D-02 | 2026-10-30 | A1 | accepted | One hour equals one step, so 1 MW sustained for one step equals 1 MWh. `StepResult` values are MW and MWh in the same number. | Specification defines hourly steps and MW/MWh units. |
| D-03 | 2026-10-30 | A1 | accepted | `StepResult.messages` counts the orders exchanged in all negotiation rounds of the step. | The specification does not define a separate message object. B3 may refine the count without changing the field type. |
| D-04 | 2026-10-30 | A1 | accepted | `StepResult.trades` contains the trades of the **final** negotiation round; `orders` contains every order of every round. | Avoids double counting during settlement. |
| D-05 | 2026-10-30 | A1 | superseded | Agents are injected into `GridModel`; official modes fail explicitly when components are missing. The bootstrap `mode="mock"` orchestration path was removed in the skeleton phase. | Superseded by D-13: placeholder components must not be usable as if they were finished work. |
| D-06 | 2026-10-30 | A1 | accepted | Random streams are derived with `SeedSequence([seed, stream])`; cloud = 0, wind = 1, temperature = 2, consumer *i* = 100 + *i*. | Independent, reproducible streams that survive component changes. |
| D-07 | 2026-10-30 | A1 | accepted | Agent ids are generated deterministically from type and 1-based index (`solar_1`, `residential_3`, `battery_2`). | Stable ids for logs, trades, tests and the UI. |
| D-08 | 2026-10-30 | A1 | accepted | Event active interval is half-open: `t_start <= t < t_start + duration`. | Prevents double activation at boundaries. |
| D-09 | 2026-10-30 | A1 | accepted | Experimental seeds run from `seed_start = 0` to `29`, i.e. `0..29` per system/scenario pair. | Specification fixes 30 seeds but not their values. Configurable via `experiments.seed_start`. |
| D-10 | 2026-10-30 | A1 | accepted | Fixed specification values (168 steps, 3 rounds, 4 systems, 5 scenarios, 30 seeds, maximum 20 agents) are validated and cannot be overridden by configuration. | Protects the study from accidental scope drift. |
| D-11 | 2026-10-30 | A1 | accepted | `config/default.yaml` may add parameter sections (`environment`, `experiments`, `project`) not listed in the original prompt, provided the official defaults are preserved. | The prompt requires all mathematical parameters to be configurable. |
| D-12 | 2026-10-30 | A1 | accepted | A storage agent that is idle in a step keeps its state of charge; only Team B2's implementation will change it. | The bootstrap must not implement storage decisions. |
| D-13 | 2026-10-30 | A1 | accepted | Skeleton phase scope reset: every non-A1 implementation (A2, A3, B, C, D) is replaced by a documented interface skeleton. Modules keep their frozen signatures and raise `NotImplementedError` with a `TODO(<owner>)` note. The implementation existing before the reset is preserved in Git history at commit `20c26ff`. | Establishes clear ownership and prevents accidental or premature implementation of another team's logic. |
| D-14 | 2026-10-30 | A1 | accepted | The A1 files (`core/clock.py`, `core/config.py`, `core/logger.py`, `core/model.py`, `core/environment.py`) are kept fully intact and labelled `MY WORK`. | A1 is implemented by the project owner; any change requires A1's explicit approval. |

## Resolved implementation decisions

The bootstrap placeholders below were resolved during implementation. The
"Decision" column records the rule that the code now applies.

| ID | Owner | Status | Decision |
| --- | --- | --- | --- |
| PD-01 | A3 | accepted | Five scenarios calibrated from guide section 8: plant outage at step 86 for 12 h (thermal 30 %), demand spike at 86 for 6 h (residential +40 %), weather shift at 72 for 24 h (cloud 0.2, wind 50 %), and a combined outage-plus-spike scenario. |
| PD-02 | B2 / A3 | accepted | Initial battery state of charge is 0.5 (50 %) in `storage.initial_soc`. |
| PD-03 | A2 | accepted | Half-open windows: night `[22, 7)`, morning `[7, 9)`, midday `[9, 18)`, evening `[18, 22)`; night wraps midnight. |
| PD-04 | A2 / C1 | accepted | Forecasts include the origin hour, use expected AR(1) persistence without noise, and use a zero future day-temperature offset; repeated calls are identical. |
| PD-05 | B3 | accepted | Settlement defers `min(shortfall, demand * flexibility)` and reports the remainder as unserved; deferred flexible energy is re-bid once in the next hour. |
| PD-06 | A3 / B3 | accepted | `GridModel.inject_event` schedules at the current step by default with duration 1; active intervals are half-open and parameters are validated at the model boundary. |
| PD-07 | C1 | accepted | `CentralMarketAdapter` solves the LP, caches plans for the replanning interval, caps dispatch by actual availability, allocates shortage by lowest VOLL first, and settles trades zero-sum. |
| PD-08 | C2 | accepted | 60 states (5 SoC bins x 3 price bins x 4 periods), 3 actions, reward `revenue - cost - 0.5*throughput - 0.5*UE*1[SoC<1]`, alpha 0.1, gamma 0.95, linear epsilon 1.0 to 0.05 over 1500 episodes, 2000 training episodes. |
| PD-09 | D2 | accepted | Metrics follow guide section 9.2; bootstrap uses 1000 resamples and 95 % intervals; pairwise Wilcoxon tests are Bonferroni corrected over all tests; artefacts are `raw.csv`, `steps.csv`, summary, pairwise table and figures. |
| PD-10 | D1 / D2 | accepted | Four-page Streamlit dashboard (Live Simulation, Market Board, Compare, Learning) reading live models and persisted `results/` artefacts. |
| PD-11 | A1 | accepted | `core/environment.py` remains the composition module; `core/factory.py` assembles full runs. |
| PD-12 | A1 / B3 | accepted | Flexible consumer load bids at `max_prices.flex`; storage bids also use the flex ceiling; fixed load keeps the consumer-type ceiling. |
| PD-13 | A3 | accepted | `capacity_factor` is a multiplicative availability modifier by producer type or agent id; the weather scenario combines it with a cloud override. |
| PD-14 | D2 | accepted | Per-run step logs and aggregate tables are CSV (`results/runs/`, `results/raw.csv`, `results/steps.csv`). |
| PD-15 | A1 / B1 | accepted | `mode="mock"` is backed by clearly labelled orchestration doubles and is never used for experimental results. |

## Change process

1. Add a new row or update the status of an existing row.
2. Reference the row in the pull request that implements the change.
3. Obtain approval from the owning team lead; frozen interfaces additionally
   require A1, B1, C1 and D1 approval (see `contracts.md`).
