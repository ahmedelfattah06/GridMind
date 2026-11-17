# GridMind test suite - ownership and activation

This directory is prepared for parallel development. Tests that depend on a
component which is still an interface skeleton are **skipped on purpose** with
an explicit reason naming the owning team. No test is hidden or silently
deleted: the assertions stay in place as the acceptance criteria for the owner.

Run everything:

```bat
pytest
```

Run only the currently active suites:

```bat
pytest tests/test_config.py tests/test_clock.py tests/test_contracts.py
```

## Ownership and status

| File | Owner | Status now | Activates when |
| --- | --- | --- | --- |
| `conftest.py` | A3 (shared fixtures) | active | - |
| `test_config.py` | A1 config, A3 scope guard | active | - (the D2 grid test is skipped) |
| `test_clock.py` | A1 | active | - |
| `test_contracts.py` | shared contracts | active | - |
| `test_environment.py` | A2, A3 for modifiers | skipped (`TODO(A2/A3)`) | weather, demand, supply and modifiers are implemented |
| `test_model.py` | A1, A3 for orchestration contracts | skipped (`TODO(A2/B1/B2/B3)`) | environment plus one injected agent/market stack exist |
| `test_reproducibility.py` | A1, A3 | skipped (`TODO(A2/B/C)`) | a complete official-mode run is available |

## Activation rules

1. The owning team implements its modules and replaces the `NotImplementedError`
   placeholders.
2. The owner removes the module-level `pytestmark` skip (or the single
   `@pytest.mark.skip` on the D2 grid test) and runs the suite locally.
3. The suite must pass without weakening assertions. If an assertion encodes an
   assumption that was not agreed, raise it as a decision-log entry instead of
   deleting the test.
4. Contract changes require the approvals listed in `docs/contracts.md`.

## What these tests must not do

* They must not use fake agents, auctions, LPs or Q-tables to make a run appear
  complete.
* They must not require unfinished Team B/C/D functionality.
* They must not change the frozen interfaces to fit an implementation.

## Current scope

* Active tests cover configuration loading/validation, clock arithmetic and the
  frozen `Order`, `Trade` and `StepResult` structures.
* Pending tests are the agreed acceptance criteria for A2, A3 and the
  orchestration path. They are intentionally not executed yet.
