# GridMind

**Multi-Agent Smart Energy Trading & Optimization Simulation**

GridMind simulates a small smart electricity city in which autonomous agents
trade energy hour by hour. It compares decentralised negotiation with centralised
planning when power plants fail or demand suddenly increases.

> **Research question:** Is decentralized negotiation between autonomous agents
> more robust than centralized planning when power plants fail or demand
> suddenly increases?

---

## 1. Current phase: structure-only skeleton

This repository is in the **skeleton phase**. It contains the official project
structure, the configuration, the frozen integration contracts and the complete
A1 core model. Every file owned by A2, A3, Team B, Team C and Team D is a
documented interface skeleton that raises `NotImplementedError` with a
`TODO(<owner>)` note.

* **A1 (`core/model.py`, `core/clock.py`, `core/config.py`, `core/logger.py`,
  `core/environment.py`) is implemented and reserved for the A1 lead.** It is
  marked `MY WORK` and must not be changed without A1's approval.
* **No other team's business logic is implemented.** There is no working
  auction, agent policy, LP, Q-learning, dashboard, metric or experiment runner.
* **The previous pre-skeleton implementation is preserved in Git history** on
  this branch (commit `20c26ff`). Nothing was deleted from the repository
  history.
* **The project is not fully functional.** Only the active test suites pass;
  full simulations are pending the component owners.

This document describes the intended architecture. Interfaces are frozen in
[`docs/contracts.md`](docs/contracts.md); open questions are tracked in
[`docs/decision_log.md`](docs/decision_log.md).

---

## 2. Key facts

| Item | Value |
| --- | --- |
| Horizon | 168 hourly steps (7 days) per run |
| Agents | 15 by default, maximum 20 |
| Market | Double auction, at most 3 negotiation rounds |
| Systems | Central-6h, Central-1h, Auction, Auction+Q |
| Scenarios | Normal, Plant Outage, Demand Spike, Weather Shift, Combined |
| Seeds | 30 per system/scenario pair |
| Experiments | 4 × 5 × 30 = **600** |
| Units | MW for power, MWh for energy per hourly step |
| Data | 100 % synthetic, generated from mathematical equations |

---

## 3. Architecture overview

```
config  ->  core.model  ->  environment (weather, demand, supply)
                         ->  agents (consumer, producer, storage)
                         ->  market (orders, clearing, negotiation)
                         ->  ai (central LP, tabular Q-learning)
                         ->  logger (Pandas)
```

One simulation step follows a fixed order:

1. Environment update
2. Event modifiers applied
3. Agents observe
4. Round 1 decisions
5. Market clearing
6. Rounds 2 and 3 negotiation
7. Settlement
8. Agent updates
9. Logging

`GridModel` only orchestrates; its constructor accepts injected environment,
agents, market, negotiation and logger components. Market clearing and agent
decision logic belong to their owning modules, never to `core/model.py`. See
[`docs/architecture.md`](docs/architecture.md) for details.

---

## 4. Technologies

Approved stack only:

* Python 3.11+
* NumPy, Pandas, SciPy, NetworkX
* Streamlit, Plotly, Matplotlib
* PyYAML
* Pytest (and Black for formatting)

**Not used:** Mesa, React, FastAPI, Flask, deep learning, DQN, PPO, multi-agent
RL frameworks, paid APIs or external data APIs. The only learning algorithm
allowed is tabular Q-learning for the storage agent (later phase).

---

## 5. Project structure

```
gridMind/
├── config/
│   ├── default.yaml           # official parameters
│   └── scenarios.yaml         # five official scenarios (events TODO A3)
├── core/
│   ├── clock.py               # MY WORK - simulation clock
│   ├── config.py              # MY WORK - loader, validation, seed streams
│   ├── logger.py              # MY WORK - Pandas step log and CSV export
│   ├── model.py               # MY WORK - GridModel and frozen StepResult
│   ├── environment.py         # MY WORK - A2 composition (see PD-11)
│   ├── weather.py             # TODO (A2) - interface skeleton
│   ├── demand.py              # TODO (A2) - interface skeleton
│   ├── supply.py              # TODO (A2) - interface skeleton
│   └── events.py              # TODO (A3) - interface skeleton
├── agents/
│   ├── base.py                # TODO (B1) - BaseAgent contract
│   ├── consumer.py            # TODO (B1) - consumer agent
│   ├── producer.py            # TODO (B2) - producer agent
│   └── storage.py             # TODO (B2) - storage agent
├── market/
│   ├── orders.py              # CONTRACT ONLY - Order / Trade
│   ├── auction.py             # TODO (B3) - market interface and clearing
│   └── negotiation.py         # TODO (B3) - negotiation protocol
├── ai/
│   ├── central_lp.py          # TODO (C1) - central LP
│   ├── qlearning.py           # TODO (C2) - tabular Q-learning
│   └── train.py               # TODO (C2) - training entry point
├── experiments/
│   ├── runner.py              # TODO (D2) - 600-run grid and execution
│   ├── metrics.py             # TODO (D2) - metrics
│   ├── stats.py               # TODO (D2) - statistics
│   └── plots.py               # TODO (D2) - figures
├── ui/
│   ├── app.py                 # TODO (D1) - Streamlit dashboard
│   └── pages/                 # TODO (D1)
├── results/
│   └── figures/               # generated artefacts (ignored by Git)
├── tests/
│   ├── README.md              # ownership and activation rules
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_clock.py
│   ├── test_contracts.py
│   ├── test_environment.py    # skipped until A2/A3
│   ├── test_model.py          # skipped until A2/B
│   └── test_reproducibility.py# skipped until A2/B/C
├── docs/
│   ├── architecture.md
│   ├── contracts.md
│   ├── decision_log.md
│   └── report/
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

---

## 6. Team ownership

| Team | Members | Owned files |
| --- | --- | --- |
| **A - Environment** | A1 (lead): core model | `core/model.py`, `core/config.py`, `core/clock.py`, `core/logger.py`, `core/environment.py` |
| | A2: weather, demand, supply | `core/weather.py`, `core/demand.py`, `core/supply.py` |
| | A3: events, tests, scope guard | `core/events.py`, `config/scenarios.yaml`, test ownership, `docs/decision_log.md` |
| **B - Agents & Market** | B1: consumer agents | `agents/base.py`, `agents/consumer.py` |
| | B2: producer and storage | `agents/producer.py`, `agents/storage.py` |
| | B3: market and auction | `market/orders.py`, `market/auction.py`, `market/negotiation.py` |
| **C - AI** | C1: central LP | `ai/central_lp.py` |
| | C2: tabular Q-learning | `ai/qlearning.py`, `ai/train.py` |
| **D - Demo & Evaluation** | D1: Streamlit | `ui/app.py`, `ui/pages/` |
| | D2: experiments and report | `experiments/*`, `results/figures/`, `docs/report/` |

Rules:

* Only edit files owned by your team. Contract changes require all four team
  leads (see `docs/contracts.md`).
* Placeholders raise `NotImplementedError` with `TODO(<owner>)`. Do not replace
  a placeholder with a fake result or a stub that could be mistaken for the
  real component.
* Keep `MY WORK` files untouched unless you are the A1 lead.
* Never commit experimental results produced by a placeholder component.

---

## 7. Installation (Windows)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Optional development extras (Black):

```bat
pip install -e ".[dev]"
```

If PowerShell blocks the activation script:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

Python 3.11 or newer is required. No paid or external data service is used.

---

## 8. Running the tests

```bat
pytest
```

Run only the active suites:

```bat
pytest tests/test_config.py tests/test_clock.py tests/test_contracts.py
```

At the time of writing: **38 passed, 45 skipped**. The skipped suites are
documented pending work, not hidden failures. Each skip names the owning team
and the activation condition; see [`tests/README.md`](tests/README.md).

Active coverage:

* configuration loading, validation and agent resolution (A1),
* clock arithmetic and hour/day mapping (A1),
* frozen `Order`, `Trade` and `StepResult` structures (shared contract).

Pending coverage, kept as acceptance criteria:

* environment equations and event modifiers (A2/A3),
* `GridModel` orchestration (A1 with B1/B2/B3),
* reproducibility of full runs (A1 with A2/B/C),
* the 600-run experiment grid (D2).

---

## 9. Running the simulation

Not available yet. Official modes require the environment (A2), the agents
(B1/B2), the market and negotiation (B3) and, for the central modes, the C1
adapter. Until those exist, constructing a run with an official mode raises
`NotImplementedError` instead of substituting a fake component.

Once the components are implemented, the intended entry point is:

```python
from core.config import load_config
from core.model import GridModel

config = load_config()
model = GridModel(
    config,
    seed=0,
    mode="auction",                 # central_6h | central_1h | auction | auction_q
    scenario="demand_spike",
    agents=my_agents,               # Team B
    market=my_market,               # Team B3 (or the C1 adapter)
    negotiation=my_negotiation,     # Team B3
)

for _ in range(model.clock.steps):
    model.step()
model.logger.export_csv("results/run.csv")
```

The dashboard entry point is also pending:

```bat
streamlit run ui/app.py
```

---

## 10. Git workflow

* `main` is the protected integration branch. **Never push directly to main.**
* Every task uses a dedicated branch in the official naming convention:

```
A/environment-bootstrap   (current skeleton branch)
A/core-model
A/environment-model
A/events-testing
B/agent-base
B/auction-clear
C/lp-horizon
D/streamlit-dashboard
```

* Use conventional commits, one topic per commit:

```
feat(core): add simulation clock
feat(environment): add weather model
test(core): add reproducibility tests
docs(architecture): document integration contracts
```

* Merge through a pull request with at least one reviewer from another team.
* Do not push to any remote repository without explicit authorisation.
* Never rewrite or delete existing branches or other members' files.
* Rebase on `main` before opening a pull request; keep history linear.

Example:

```bat
git switch main
git pull
git switch -c A/environment-model
git add core/weather.py core/demand.py core/supply.py tests/test_environment.py
git commit -m "feat(environment): add weather, demand and supply models"
git push -u origin A/environment-model
```

---

## 11. Development roadmap

| Phase | Scope | Owner | Status |
| --- | --- | --- | --- |
| 0 | Repository skeleton, configuration, clock, logger, model, contracts, test structure | A1 + A2/A3 | **done** |
| 1 | Weather, demand and supply models | A2 | TODO |
| 2 | Event mechanism and scenario calibration | A3 | TODO |
| 3 | Agent base, consumer bidding, producer and storage agents | B1, B2 | TODO |
| 4 | Double auction, negotiation rounds, settlement | B3 | TODO |
| 5 | Central LP (6h and 1h) and market adapter | C1 | TODO |
| 6 | Tabular Q-learning for storage, training pipeline | C2 | TODO |
| 7 | 600-run experiment grid, metrics, statistics | D2 | TODO |
| 8 | Streamlit dashboard and report figures | D1 | TODO |
| 9 | Final report and reproducibility package | all | TODO |

---

## 12. Configuration notes

* Every tunable parameter lives in `config/default.yaml`; scenario events live
  in `config/scenarios.yaml`.
* `core.config.load_config()` validates both files and raises `ConfigError` with
  the dotted path of any invalid value.
* The simulation duration (168), negotiation rounds (max 3), four systems, five
  scenarios, 30 seeds and maximum 20 agents are validated against the official
  specification and cannot be changed silently.
* `config/scenarios.yaml` currently contains the five official keys with empty
  event lists. Event timing and intensity are A3's work and open decision PD-01.
* Initial battery state of charge, profile boundaries, forecast conventions and
  other open points are tracked in [`docs/decision_log.md`](docs/decision_log.md).

---

## 13. Coding standards

* Python 3.11+, type hints everywhere, docstrings on every module and public
  class/function.
* English names, comments and commit messages.
* Black formatting (`black .`, line length 100).
* No global random calls; use `derive_rng(seed, stream)`.
* No magic numbers in business logic; read from configuration.
* No duplicated business logic; no unnecessary abstractions.
* Explicit exceptions (`ConfigError`, `ValueError`, `RuntimeError`,
  `NotImplementedError`).
* Never hide a failing test. Skipped tests must state the missing dependency and
  owning team.

---

## 14. Documentation

* [`docs/architecture.md`](docs/architecture.md) - layers, step flow, ownership.
* [`docs/contracts.md`](docs/contracts.md) - frozen integration interfaces.
* [`docs/decision_log.md`](docs/decision_log.md) - accepted, superseded and
  pending decisions.
* [`tests/README.md`](tests/README.md) - test ownership and activation rules.
