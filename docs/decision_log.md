# Decision Log

Every decision that is not fixed by the official specification is recorded here.
**Pending decisions** are placeholders that keep parallel development unblocked;
they must be resolved by the owning team before the final report. No pending
decision may be presented as a final research rule.

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

## Pending decisions

| ID | Owner | Status | Open question | Current placeholder |
| --- | --- | --- | --- | --- |
| PD-01 | A3 | pending | Event timing and intensity for the five scenarios (start steps, durations, multipliers). | `config/scenarios.yaml` ships the five official keys with `events: []`. No timing or intensity is defined; A3 must define and calibrate the scenarios. |
| PD-02 | B2 / A3 | pending | Initial battery state of charge. Not defined by the specification. | `storage.initial_soc: 0.5` (50 %). |
| PD-03 | A2 | pending | Exact boundary hours of the residential profile windows. | Half-open windows: night `[22, 7)`, morning `[7, 9)`, midday `[9, 18)`, evening `[18, 22)`; night wraps midnight. Values live in `config/default.yaml`. |
| PD-04 | A2 / C1 | pending | Forecast conventions: origin inclusion, persistence expectation, future day offsets. | Forecast includes the origin hour, uses expected AR(1) persistence without noise, and uses a zero day-temperature offset for future days. |
| PD-05 | B3 | pending | Split between deferred and unserved energy for flexible consumers. | No split is implemented. `market/auction.py` only documents the intent; B3 must agree the rule with A3. |
| PD-06 | A3 / B3 | pending | Semantics of runtime event injection when injected between steps. | `EventManager.schedule`/`inject` raise `TODO(A3)`. `GridModel.inject_event` documents `t_start` defaulting to the current step and `duration` to 1 step, but the path is not executable yet. |
| PD-07 | C1 | pending | How central modes adapt the LP to the market interface (dispatch → trades, prices, settlement). | Documented expectation: C1 provides a `MarketInterface` adapter; not implemented. |
| PD-08 | C2 | pending | Q-learning state discretisation, action set, reward function, learning rate, discount, exploration schedule, training episodes. | All parameters are open; `ai/qlearning.py` raises `NotImplementedError`. Tabular only. |
| PD-09 | D2 | pending | Metric formulas (`cost_total`, `voll_penalty`, price volatility), confidence intervals and artefact layout. | Names listed in `experiments/metrics.py`; no formulas implemented. |
| PD-10 | D1 / D2 | pending | Dashboard scope and how runs are selected and stored. | `results/` root with ignored CSV/parquet artefacts; placeholder UI only. |
| PD-11 | A1 | pending | Addition of `core/environment.py` to the official file list. | Composition module; rationale in `architecture.md`. Needs team-lead confirmation to become permanent. |
| PD-12 | A1 / B3 | pending | Whether `max_prices.flex` applies to storage bids only or to all flexible load. | Storage specs receive `max_price = max_prices.flex`; flexible consumers keep their type ceiling. |
| PD-13 | A3 | pending | Whether event `capacity_factor` may also represent weather-driven wind changes rather than plant availability. | No event modifier is implemented. The intended multiplicative application (by agent id or producer type) is documented in `core/events.py`. |
| PD-14 | D2 | pending | Whether per-run logs are stored as CSV, Parquet or both. | A1's logger exports CSV; Parquet is allowed by the approved stack but not implemented. |
| PD-15 | A1 / B1 | pending | Whether `mode="mock"` should be removed from the frozen `GridModel` signature or backed by a clearly labelled test double. | The previous mock agents/market/negotiation were removed by D-13. `MockAgent` raises on construction, so `mode="mock"` is currently unusable; orchestration tests are skipped. |

## Change process

1. Add a new row or update the status of an existing row.
2. Reference the row in the pull request that implements the change.
3. Obtain approval from the owning team lead; frozen interfaces additionally
   require A1, B1, C1 and D1 approval (see `contracts.md`).
