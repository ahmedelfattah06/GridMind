# GridMind test suite - ownership and coverage

All official components are implemented, so the suite runs without skips. The
assertions that were originally written as acceptance criteria for each owner are
now active tests against the real modules.

Run everything:

```bat
pytest
```

## Ownership and status

| File | Owner | Status |
| --- | --- | --- |
| `conftest.py` | A3 (shared fixtures) | active |
| `test_config.py` | A1 config, A3 scope guard, D2 grid | active |
| `test_clock.py` | A1 | active |
| `test_contracts.py` | shared contracts | active |
| `test_environment.py` | A2, A3 for modifiers | active |
| `test_model.py` | A1, A3 for orchestration contracts | active |
| `test_reproducibility.py` | A1, A3 | active |
| `test_agents.py` | B1, B2 | active |
| `test_market.py` | B3, C1 adapter | active |
| `test_ai.py` | C1 planner, C2 Q-learning and training | active |
| `test_experiments.py` | D2 | active |
| `test_factory.py` | A1 factory and fleet resizing | active |

## Rules

1. Tests use the real production components; only `mock` mode is allowed to use
   the labelled orchestration doubles.
2. A failing assertion must be fixed in the implementation or raised as a
   decision-log entry, never silenced without agreement.
3. Contract changes require the approvals listed in `docs/contracts.md`.
4. Tests must not fabricate simulation or experiment results.

## Current scope

* Configuration, clock and the frozen `Order`, `Trade` and `StepResult`
  structures.
* Weather, demand, supply and event modifiers.
* Full `GridModel` orchestration and energy conservation with the real auction.
* Deterministic reproducibility of complete official-mode runs.
* Consumer, producer and storage behaviour, including SoC limits and policies.
* Double auction, settlement, negotiation validation and central LP dispatch.
* Q-table discretisation, updates, persistence and a short training run.
* Metrics, bootstrap intervals, Wilcoxon comparisons, grid construction, one
  end-to-end runner execution and report generation.
* Model factory wiring for all four official systems and fleet resizing.
