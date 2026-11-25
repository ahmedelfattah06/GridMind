# GridMind Architecture

This document describes how the repository is organised, how one simulation
step flows through the components, and where each team plugs in. Integration
details are specified in [`contracts.md`](contracts.md); open questions are in
[`decision_log.md`](decision_log.md).

## 1. Purpose

GridMind simulates a small smart electricity city in which autonomous agents
trade energy. The research question is whether decentralised negotiation between
autonomous agents is more robust than centralised planning when power plants
fail or demand suddenly increases.

Four systems are compared over five scenarios and 30 seeds, giving 600
experiments:

| System | Mode id | Clearing authority |
| --- | --- | --- |
| Central-6h | `central_6h` | Team C1 LP with a 6 hour horizon |
| Central-1h | `central_1h` | Team C1 LP with a 1 hour horizon |
| Auction | `auction` | Team B3 double auction |
| Auction+Q | `auction_q` | Team B3 double auction + Team C2 storage Q-learning |

The simulation has 15 agents by default (maximum 20), 168 hourly steps (seven
days), a double auction with at most three rounds, and energy measured in MW /
MWh. All data is synthetic and generated from the equations in
`config/default.yaml`.

## 2. Current phase: complete

Every official component is implemented:

* **A1** (`core/clock.py`, `core/config.py`, `core/logger.py`, `core/model.py`,
  `core/environment.py`) provides the frozen orchestration layer.
* **A2/A3** implement weather, demand, supply and the event/scenario mechanism.
* **Team B** implements the agents, double auction, negotiation and settlement.
* **Team C** implements the central LP adapter and tabular Q-learning.
* **Team D** implements the experiment pipeline, figures, report and dashboard.
* `core/factory.py` assembles a complete run for every official mode.
* `mode="mock"` remains a labelled orchestration path only; it is never used for
  reported results. `MockAgent`, `MockAuction` and `StubNegotiation` delegate to
  real implementations or are used solely for the mock mode.

## 3. Layers

```
config/            YAML configuration and official scenario catalogue
core/              Clock, config, logger, environment composition, events, model
agents/            Agent contracts and agent implementations
market/            Order/trade contracts, clearing interface, negotiation
ai/                Central LP and tabular Q-learning
experiments/       Experiment grid, metrics, statistics, plots
ui/                Streamlit dashboard
tests/             Pytest suite (see tests/README.md)
docs/              Architecture, contracts, decisions, report
results/figures/   Generated artefacts
```

Dependency direction is one-way:

```
ui / experiments  ->  core.model  ->  core.environment, agents, market, ai
core.model        ->  core.clock, core.config, core.logger, core.events
core.environment  ->  core.weather, core.demand, core.supply, core.events
agents / market   ->  market.orders (and config)
```

`core.model` may import every component, but components never import
`core.model` at runtime. Market clearing and agent decision logic live
exclusively in their own modules.

`core/environment.py` is a composition module that did not appear in the
original file list; it exists so `core/model.py` only orchestrates. The
decision is recorded as PD-11 in the decision log.

## 4. One simulation step

```
t = clock.t
 1. environment.update(t)          weather -> demand -> generation
 2. events.apply(t)                active modifiers -> environment state
 3. agents observe                 same environment view + own snapshot
 4. round 1 decisions              one list[Order] per agent
 5. market.clear(..., round=1)     ClearingResult
 6. rounds 2..N                    decide -> negotiation.refine -> clear
 7. market.settle(...)             Settlement (price, trades, unserved, ...)
 8. agents update                  per-agent settlement dictionary
 9. logger.record_step(result)     Pandas log, then clock advances
```

The order is fixed by the specification and enforced in
`GridModel._execute_step` (A1). The environment is updated before events are
applied; an active event therefore modifies the environment state of the *same*
step before any agent observes it. Agents receive the environmental
consequences only, never the event names.

## 5. Component responsibilities and status

| Owner | Files | Responsibility | Status |
| --- | --- | --- | --- |
| A1 | `core/config.py`, `core/model.py`, `core/clock.py`, `core/logger.py`, `core/environment.py`, `core/factory.py` | Bootstrap, orchestration, frozen contracts, assembly | **done** |
| A2 | `core/weather.py`, `core/demand.py`, `core/supply.py` | Synthetic weather, demand and generation | **done** |
| A3 | `core/events.py`, `config/scenarios.yaml`, `tests/` (scope guard), `docs/decision_log.md` | Events, scenarios, test ownership, scope control | **done** |
| B1 | `agents/base.py`, `agents/consumer.py` | Agent contract and consumer bidding | **done** |
| B2 | `agents/producer.py`, `agents/storage.py` | Producer and storage behaviour | **done** |
| B3 | `market/orders.py`, `market/auction.py`, `market/negotiation.py` | Double auction, negotiation, settlement | **done** |
| C1 | `ai/central_lp.py` | Central LP and its `MarketInterface` adapter | **done** |
| C2 | `ai/qlearning.py`, `ai/train.py` | Tabular Q-learning for the storage agent | **done** |
| D1 | `ui/app.py` | Streamlit dashboard | **done** |
| D2 | `experiments/*` | 600-run grid, metrics, statistics, figures, report | **done** |

Components never fake results. `market/orders.py` defines and validates the
frozen `Order` and `Trade` structures used by every other component.

## 6. Dependency injection

`GridModel` accepts optional keyword-only components:

```python
model = GridModel(
    config,
    seed=0,
    mode="auction",
    scenario="demand_spike",
    agents=build_agents(config),
    market=DoubleAuction(config),
    negotiation=RaiseFactorNegotiation(config),
)
```

Every injected component must satisfy the interfaces in `contracts.md`. If an
official mode is requested without its components, the model raises
`RuntimeError` instead of silently substituting a fake implementation.

The `mode="mock"` orchestration path is a labelled test double and is not used
for experiments. Official modes are assembled by `core.factory.build_model`.

## 7. Reproducibility

* All randomness must come from `derive_rng(seed, stream)` in `core/config.py`,
  which wraps `numpy.random.SeedSequence([seed, stream])`.
* A2 owns the actual stream assignment for cloud, wind, temperature and each
  consumer. Independent streams must be used so wind and cloud never share
  draws.
* Forecasts must draw no random numbers.
* A1's model and logger are deterministic given a component implementation.
* `tests/test_reproducibility.py` verifies that complete official-mode runs are
  deterministic for a fixed seed and differ between seeds.

## 8. Configuration

`config/default.yaml` holds every tunable value. `config/scenarios.yaml` holds
the five official scenarios with calibrated event timings and intensities.
`load_config()` merges both into one dictionary and `validate_config()` enforces
the official boundaries (168 steps, 3 rounds, 4 systems, 5 scenarios, 30 seeds,
at most 20 agents). Unknown or missing values raise `ConfigError` with the
dotted path.

## 9. Testing strategy

The suite runs without skips (details in `tests/README.md`):

* configuration validation, clock arithmetic and the frozen `Order`, `Trade`
  and `StepResult` structures,
* environment equations, event modifiers and scenario calibration,
* full orchestration, energy conservation and reproducibility,
* agents, auction, settlement, negotiation and central LP,
* Q-learning and a short training run,
* metrics, statistics, the 600-run grid and one end-to-end runner execution,
* model-factory wiring for all four official systems.

Tests use the real production components; only the labelled `mock` mode may use
orchestration doubles. They must never fabricate results.

## 10. Non-goals and scope guard

* No Mesa, React, FastAPI, Flask, deep learning, DQN, PPO or MARL frameworks.
* No external data APIs or paid services; all data is synthetic.
* Tabular Q-learning is used only by the storage agent.
* A3 guards the scope: any new agent, scenario, system, seed count or external
  dependency requires a documented decision and team-lead approval.
* Frozen interfaces must not change without the approvals listed in
  `contracts.md`.
