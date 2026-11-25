# GridMind Project Guide

**A technical guide to the implemented system**

This document describes GridMind as it exists in this repository. It is not a
description of the original project idea, and it deliberately separates what the
code does from what the specification, report or dashboard prose says about it.
Every statement about behaviour is traceable to a module, configuration file,
test or persisted artefact. Where the implementation has a nuance or a visible
calibration caveat, that is called out rather than smoothed over.

The guide is aimed at a developer who has to run, extend, review or judge the
project, and at a competition judge who needs to understand the mechanics
without reading every source file first.

> **Post-audit note (2026-11-25).** This guide was written before the correctness
> audit. The audit fixed central-adapter execution, storage-policy timing,
> forecast random streams, per-hour LP objectives and report-path safety; see
> `docs/GRIDMIND_AUDIT_REPORT.md` for the defect list and
> `docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md` for the post-fix reference.
> Where this guide describes pre-fix behaviour, the audit report takes
> precedence. The 600-run artefacts and `qtable.npy` described below predate the
> fixes and are therefore stale for post-fix reporting.

**Inspection scope.** This guide was checked against the Python implementation,
the YAML configuration, the dashboard modules, the test ownership notes and the
persisted files in `qtable.npy` and `results/`. It does not treat report claims
as evidence unless the underlying code or generated artefact supports them. No
application source, experiment result or Git state was changed while preparing
it.

---

## Contents

1. [What GridMind is](#1-what-gridmind-is)
2. [Architecture and repository map](#2-architecture-and-repository-map)
3. [One simulation step, end to end](#3-one-simulation-step-end-to-end)
4. [Environment, scenarios and disruptions](#4-environment-scenarios-and-disruptions)
5. [Agents and their decision rules](#5-agents-and-their-decision-rules)
6. [The double auction, negotiation and settlement](#6-the-double-auction-negotiation-and-settlement)
7. [Central planning with a linear program](#7-central-planning-with-a-linear-program)
8. [Tabular Q-learning for the battery](#8-tabular-q-learning-for-the-battery)
9. [Experiments, metrics, statistics and artefacts](#9-experiments-metrics-statistics-and-artefacts)
10. [Dashboard shell and global controls](#10-dashboard-shell-and-global-controls)
11. [The four dashboard pages](#11-the-four-dashboard-pages)
12. [Installation, training, experiments and operation](#12-installation-training-experiments-and-operation)
13. [Limitations, implementation notes and glossary](#13-limitations-implementation-notes-and-glossary)

---

## 1. What GridMind is

GridMind is a discrete-time, agent-based simulation of a small electricity
market. A simulated city contains hospitals, households, factories, solar and
wind generators, a thermal plant, a peaker plant and batteries. Every simulated
hour, the agents submit bids and asks, a market clears, energy and money are
settled, and the agents update their state.

The research question is:

> Is decentralised negotiation between autonomous agents more robust than
> centralised planning when power plants fail or demand suddenly increases?

To answer it, the project compares four systems on the same five scenarios and
the same thirty seeds:

| System id | Display name | Clearing authority |
| --- | --- | --- |
| `central_6h` | Central · 6h | Linear-programming planner, replanned every 6 hours |
| `central_1h` | Central · 1h | Linear-programming planner, replanned every hour |
| `auction` | Double auction | Uniform-price double auction with up to three rounds |
| `auction_q` | Auction + Q-learning | The same auction, with a learned battery policy |

The official design is 4 systems × 5 scenarios × 30 seeds = **600 runs**, each
168 hourly steps. The default fleet has **15 agents** and the hard cap is **20**.
The units are MW for power and MWh for energy in one hourly step; because one
step is one hour, a sustained 1 MW is 1 MWh in that step.

### 1.1 What is implemented, and what is not

Implemented in real code:

* the core clock, configuration loader, validation, seed derivation and logger;
* synthetic weather, demand, generation, events and the five official scenarios;
* consumer, producer and storage agents with concrete bidding and update rules;
* a uniform-price double auction, three negotiation rounds and settlement;
* a central LP planner and a market adapter with 1-hour and 6-hour replanning;
* tabular Q-learning for the storage policy, a training CLI and a persisted
  Q-table;
* the 600-run experiment pipeline, metrics, bootstrap intervals, paired
  Wilcoxon tests, six figures, a generated report and a four-page Streamlit
  dashboard.

Not implemented, and not implied by this guide:

* AC power flow, voltage, frequency, congestion, network topology or line
  limits;
* real weather, demand or market data;
* multi-agent reinforcement learning, deep learning, DQN, PPO or any external
  RL framework;
* learning by consumers or producers (only the battery policy learns);
* a database, authentication, multi-user sessions or a deployed web service;
* automatic retraining from the dashboard (the Learning page reads persisted
  artefacts; its one fresh comparison runs models but does not train).

The repository documentation reported the verification status at the time this
guide was prepared: **140 tests passed, 0 skipped**, a completed 600-run grid, a
`(60, 3)` Q-table and all six report figures. The subsequent audit raised the
suite to **151 passed**; the 600-run grid and Q-table were not regenerated and
remain pre-fix artefacts. This guide does not rerun that campaign; it explains
the code and the artefacts that implement and record it.

---

## 2. Architecture and repository map

### 2.1 Design principle

`core/model.py` is an orchestrator, not a container for business logic. It owns
the clock, environment, agents, market, event manager and logger, but all of
those are injected. `core/factory.py` is the single place that assembles a
complete official run from the validated configuration:

* `Environment` from `core/environment.py`;
* real `ConsumerAgent`, `ProducerAgent` and `StorageAgent` instances from
  `agents/`;
* `DoubleAuction` and `RaiseFactorNegotiation` for auction modes;
* `CentralMarketAdapter` for central modes;
* `QPolicy` for `auction_q`.

`GridModel` therefore contains no LP code, no auction matching code and no agent
bidding rules. The separation is deliberate and is enforced by the frozen
interfaces in `docs/contracts.md`.

### 2.2 Repository tree

```text
gridMind/
├── config/
│   ├── default.yaml              official simulation parameters
│   └── scenarios.yaml            five official scenario definitions
├── core/
│   ├── clock.py                  SimulationClock, hour/day mapping
│   ├── config.py                 load_config, validate_config, seed streams
│   ├── logger.py                 SimulationLogger, stable and dynamic columns
│   ├── model.py                  GridModel, StepResult, step orchestration
│   ├── environment.py            Environment, EnvironmentState
│   ├── weather.py                WeatherModel, WeatherState
│   ├── demand.py                 DemandModel
│   ├── supply.py                 SupplyModel
│   ├── events.py                 Event, EventManager, EnvironmentModifiers
│   └── factory.py                build_model, build_agents, build_market
├── agents/
│   ├── base.py                   BaseAgent contract, MockAgent
│   ├── consumer.py               ConsumerAgent
│   ├── producer.py               ProducerAgent
│   └── storage.py                StorageAgent, StoragePolicy, RulePolicy
├── market/
│   ├── orders.py                 Order, Trade
│   ├── auction.py                DoubleAuction, MarketContext, Settlement
│   └── negotiation.py            RaiseFactorNegotiation
├── ai/
│   ├── central_lp.py             CentralLPPlanner, CentralMarketAdapter
│   ├── qlearning.py              TabularQAgent, QPolicy, state helpers
│   └── train.py                  training loop and CLI
├── experiments/
│   ├── runner.py                 ExperimentRunner, 600-run grid
│   ├── metrics.py                compute_run_metrics
│   ├── stats.py                  bootstrap and Wilcoxon comparisons
│   ├── plots.py                  six report figures
│   └── report.py                 generated Markdown report
├── ui/
│   ├── app.py                    entry point, shell, sidebar, dispatch
│   ├── theme.py                  tokens, CSS, Plotly styling
│   ├── components.py             headers, KPI cards, badges, tables, states
│   ├── charts.py                 all Plotly figures
│   ├── data.py                   labels, metric help, artefact loaders
│   ├── state.py                  model lifecycle and safe stepping
│   └── views/
│       ├── live.py               Live Simulation page
│       ├── market.py             Market Board page
│       ├── compare.py            Compare page
│       └── learning.py           Learning page
├── tests/                        pytest suite
├── results/                      generated artefacts (ignored by Git)
├── docs/                         architecture, contracts, decisions, reports
├── requirements.txt
├── pyproject.toml
├── .streamlit/config.toml
└── README.md
```

### 2.3 Layer responsibilities

| Layer | Main modules | Responsibility |
| --- | --- | --- |
| Configuration | `core/config.py`, `config/*.yaml` | Load, validate and constrain every tunable parameter; define official constants; derive independent random streams |
| Environment | `core/weather.py`, `core/demand.py`, `core/supply.py`, `core/environment.py` | Produce hourly weather, demand and available generation; apply event modifiers; provide a noiseless forecast |
| Agents | `agents/base.py`, `agents/consumer.py`, `agents/producer.py`, `agents/storage.py` | Observe the hour, submit orders, update after settlement, expose a snapshot |
| Market | `market/orders.py`, `market/auction.py`, `market/negotiation.py` | Define order/trade contracts, clear the auction, validate negotiation rounds, settle energy and money |
| Central AI | `ai/central_lp.py` | Solve the dispatch LP, cache a horizon plan, expose it through the market interface |
| Learning | `ai/qlearning.py`, `ai/train.py` | Discretise storage states, train a Q-table, expose a greedy policy |
| Experiments | `experiments/*.py` | Run the grid, compute metrics, summarise and test, draw figures, generate the report |
| Dashboard | `ui/*` | Render real snapshots and persisted artefacts; never fabricate values |
| Tests | `tests/*` | Check configuration, contracts, environment, agents, market, AI, experiments, reproducibility and factory assembly |

### 2.4 Configuration and reproducibility

`core/config.py` defines the official constants and validates the YAML files.
Important constants include:

```python
REQUIRED_SIMULATION_STEPS = 168
MAX_NEGOTIATION_ROUNDS = 3
REQUIRED_SEED_COUNT = 30
MAX_AGENT_COUNT = 20
DEFAULT_AGENT_COUNT = 15
OFFICIAL_SYSTEMS = ("central_6h", "central_1h", "auction", "auction_q")
OFFICIAL_SCENARIOS = ("normal", "plant_outage", "demand_spike",
                      "weather_shift", "combined")
```

A configuration that violates the official boundaries raises `ConfigError` with
the dotted path of the invalid value. The duration, rounds, system list,
scenario list, seed count and agent cap cannot be changed silently.

Randomness is reproducible through `derive_rng(seed, stream)` and
`derive_agent_rng(seed, agent_id)`. Weather cloud, wind and temperature use
separate streams; demand uses per-agent streams derived from the agent id with a
BLAKE2s digest. Adding, removing or reordering an agent therefore does not shift
another agent's draws. Forecast paths consume no random numbers.

### 2.5 Building a run

```python
from core.config import load_config
from core.factory import build_model

config = load_config()
model = build_model(config, seed=0, mode="auction", scenario="demand_spike")
while not model.clock.is_finished:
    model.step()
```

`build_model()` selects the market from the mode:

* `central`, `central_6h`, `central_1h` → `CentralMarketAdapter`, with interval
  1 for `central_1h` and 6 (the configured horizon) otherwise;
* `auction`, `auction_q` → `DoubleAuction` plus `RaiseFactorNegotiation`.

For `auction_q`, a missing Q-table raises `FileNotFoundError` rather than
silently using an untrained policy. `auction_q` loads the Q-table from
`qtable.npy` in the project root by default. Other auction modes use
`RulePolicy`.

---

## 3. One simulation step, end to end

`GridModel.step()` rejects a finished clock and is not re-entrant. A successful
step executes nine stages and then advances the clock:

| Stage | Code | What happens |
| --- | --- | --- |
| 1 | `Environment.update(t)` | Weather advances to step `t`; demand and available generation are computed |
| 2 | `EventManager.apply(t)` | Active events are merged; `Environment.apply_modifiers()` applies demand multipliers, capacity factors and cloud override |
| 3 | `Agent.observe(obs)` | Every agent receives the environment view, last price, market settings and its own snapshot |
| 4 | Round 1 decisions | Every agent returns orders with `round=1` |
| 5 | Market clearing | The injected market clears the order list |
| 6 | Rounds 2–3 | Auction modes collect counter-offers and clear again; central modes skip this |
| 7 | Settlement | The market turns final trades into unserved/deferred energy and payments |
| 8 | Agent updates | Every agent receives price, bought/sold, payment, unserved, deferred, generation and SoC |
| 9 | Logging | A frozen `StepResult` is recorded in `SimulationLogger` |

The clock is advanced only after the step completes. If any stage raises, the
exception propagates and `_in_step` is reset, so the model is not left in a
half-stepped state.

### 3.1 The observation

`GridModel._build_observations()` builds one dictionary per agent:

```python
{
    "t": t,
    "hour": t % 24,
    "day": t // 24,
    "mode": mode,
    "scenario": scenario,
    "environment": environment_state.as_dict(),
    "last_price": logger.last_price(),
    "market": config["market"],
    "own_agent": agent.snapshot(),
}
```

The `active_events` key is removed from the environment view before agents see
it. Agents learn about disruptions only through their consequences: changed
demand, reduced available generation and different prices. The UI snapshot keeps
the active event names for display.

### 3.2 The frozen `StepResult`

`StepResult` is the stable integration record for one step:

```python
@dataclass(frozen=True)
class StepResult:
    t: int
    price: float
    supply_mw: float
    demand_mw: float
    unserved: dict[str, float]
    deferred: dict[str, float]
    trades: list[Trade]
    orders: list[Order]
    messages: int
    soc: dict[str, float]
    generation: dict[str, float]
```

`orders` contains every order submitted in every round of that step.
`trades` contains the trades of the final round. `messages` is the number of
orders exchanged in all rounds. `supply_mw` and `demand_mw` are environment
totals, while `unserved` and `deferred` are per consumer.

### 3.3 The logger

`SimulationLogger` keeps one row per step. Its stable columns are:

```text
t, hour, day, price, supply, demand, messages,
unserved_mw, deferred_mw, generation_mw, soc_mean
```

Dynamic per-agent columns are added as they appear:

```text
ue_<agent_id>, deferred_<agent_id>, generation_<agent_id>,
soc_<agent_id>, bought_<agent_id>, sold_<agent_id>, paid_<agent_id>
```

It also keeps a long-format detail table with `t, agent_id, unserved_mw,
deferred_mw, generation_mw, soc`. `export_csv()` and `export_detail_csv()` write
the two tables. The experiment runner uses the step log directly; the metrics
module reads these columns.

### 3.4 Snapshot and forecast

`GridModel.snapshot()` returns a JSON-serialisable view used by the dashboard:
clock, environment, agent snapshots, active and scheduled events, last clearing
price, totals, per-agent unserved/deferred/SoC/generation, orders, trades and
message count.

`GridModel.forecast(t, horizon)` returns a column-oriented forecast from
`Environment.forecast()`. It is used by the central adapter. The forecast
contains no random noise and no knowledge of future events. The central
adapter replaces the first forecast hour with actual demand and generation, so
the plan starts from the observed state.

---

## 4. Environment, scenarios and disruptions

### 4.1 Weather

`WeatherModel` is a stochastic hourly process:

* temperature:
  `T(hour) = base + amplitude · sin(2π(hour − 9)/24) + day_offset`,
  with `day_offset ~ N(0, day_offset_std)` drawn once per simulated day;
* cloud:
  `cloud(t) = clip(persistence · cloud(t−1) + (1−persistence) · U(low, high), min, max)`;
* wind:
  `wind(t) = clip(persistence · wind(t−1) + (1−persistence) · U(0, 1), 0, 1)`;
* clear-sky solar:
  `solar_profile(hour) = max(0, sin(π(hour − 6)/12))` for `6 ≤ hour < 18`,
  otherwise zero.

With the official configuration:

```yaml
temperature: base 27 °C, amplitude 8 °C, peak shift 9, day offset SD 2 °C
cloud: persistence 0.8, noise [0.2, 1.0], initial 0.8, range [0.05, 1.0]
wind: persistence 0.9, noise [0.0, 1.0], initial 0.5
solar window: 6–18
```

The forecast uses expected AR(1) values for cloud and wind and a zero day offset
for future days. It never reads future event definitions.

### 4.2 Demand

`DemandModel` produces one value per consumer per hour:

* residential:
  `base · profile(hour) · (1 + sensitivity · max(0, T − comfort)) · (1 + noise)`;
* factory:
  `base` inside the working window and `base · factory_off_factor` outside it,
  times multiplicative noise;
* hospital:
  flat `base`, times multiplicative noise.

Official profile values are night `0.6` (22:00–07:00), morning `1.2`
(07:00–09:00), midday `0.8` (09:00–18:00) and evening `1.4` (18:00–22:00).
Comfort is 25 °C, sensitivity is 0.02 per °C, and the noise standard deviations
are 5 % residential, 3 % factory and 2 % hospital. Factories run at full base
from 08:00 to 18:00 and at 40 % otherwise.

`DemandModel.forecast()` uses expected values only. It consumes no random
numbers and does not know about future events.

### 4.3 Available generation

`SupplyModel` computes available generation per producer:

```text
solar   = capacity · max(0, solar_profile) · max(0, effective_cloud_cover)
wind    = capacity · max(0, wind_index)
thermal = capacity · capacity_factor
peaker  = capacity · capacity_factor
```

Event capacity factors are applied multiplicatively by producer id or producer
type. The official fleet is:

| Type | Count | Capacity each | Marginal cost | Notes |
| --- | ---: | ---: | ---: | --- |
| Solar | 1 | 40 MW | 5 | Weather driven |
| Wind | 1 | 30 MW | 8 | Weather driven |
| Thermal | 1 | 50 MW | 45 | Capacity factor 1.0 |
| Peaker | 1 | 20 MW | 90 | Capacity factor 1.0 |

**Implementation note.** The code multiplies solar output by the cloud-cover
value itself, as written in `core/supply.py`. The name and the scenario prose
call it cloud cover, but the implemented equation behaves as a multiplicative
transparency factor: a higher cloud value gives more solar output. The official
`weather_shift` event sets the override to `0.2`, which therefore reduces solar
output under this equation. This is a real calibration detail of the current
implementation, not a hidden physical model. Any future correction must be made
consistently in `core/supply.py`, the scenario calibration and the report.

### 4.4 Events and modifiers

`Event` is active on the half-open interval `[t_start, t_start + duration)`.
Supported parameters are:

* `demand_multiplier`: mapping from consumer type or agent id to a positive
  factor;
* `capacity_factor`: mapping from producer type or agent id to a factor in
  `[0, 1]`;
* `cloud_override`: a number in `[0, 1]` that replaces the modelled cloud cover.

Agent-specific entries take precedence over type-wide entries. Multiple active
events are merged: demand multipliers multiply, capacity factors multiply, and
the last defined cloud override wins. Events never message agents directly.
`GridModel.inject_event()` validates timing and parameters, then schedules the
event through the same `EventManager` used by scenario events.

### 4.5 The five official scenarios

`config/scenarios.yaml` defines exactly five scenarios:

| Scenario | Event(s) | Timing | Effect |
| --- | --- | --- | --- |
| `normal` | none | — | Baseline operation |
| `plant_outage` | `thermal_outage` | start 86, 12 h | Thermal capacity factor 0.3 |
| `demand_spike` | `residential_spike` | start 86, 6 h | Residential demand ×1.4 |
| `weather_shift` | `weather_shift` | start 72, 24 h | Cloud override 0.2, wind capacity ×0.5 |
| `combined` | `combined_outage`, `combined_spike` | start 86, 12 h / 6 h | Thermal ×0.3 and residential ×1.4 overlapping |

Step 86 is day 3 (steps 72–95), hour 14. Step 72 is the start of day 3, hour 0.
The timings and intensities are the calibrated official values, not runtime
guesses.

### 4.6 The default fleet

| Group | Count | Per-agent parameters |
| --- | ---: | --- |
| Hospital | 2 | 6 MW base, flexibility 0.0, VOLL 1000, ceiling 300 |
| Residential | 4 | 8 MW base, flexibility 0.1, VOLL 100, ceiling 120 |
| Factory | 3 | 10 MW base, flexibility 0.2, VOLL 40, ceiling 80 |
| Battery | 2 | 20 MWh, 5 MW rate, efficiency 0.95, initial SoC 0.5 |
| Producers | 4 | See the generation table above |

That is 2 + 4 + 3 + 2 + 4 = **15 agents**, the default count. The configured
maximum is 20. The dashboard exposes fleet sliders, but not every combination of
their individual maxima is valid: `validate_config()` rejects a total above 20
and the UI turns that into a readable model-build error.

---

## 5. Agents and their decision rules

### 5.1 The agent contract

Every agent implements the contract in `agents/base.py`:

```python
observe(obs)          # once per step, before any decision
decide(round)         # once per negotiation round
update(result)        # once per step, after settlement
snapshot()            # public state for logging and the dashboard
```

`BaseAgent` stores the observation, last result, last price and current
time. Concrete agents override `_on_observe()` and `_on_update()` rather than
the public methods. `snapshot()` always includes `agent_id`, `role` and `type`;
subclasses add their own fields.

### 5.2 Consumers

`ConsumerAgent` represents a hospital, residential block or factory.

On observation it reads its metered demand from the environment, applies its own
forecast error, and adds the previous hour's deferred energy:

```text
metered = environment_demand · (1 + forecast_noise)
demand  = metered + deferred_from_previous_step
```

The forecast noise is normal with standard deviation 0.03. For hospitals the
noise is clipped to non-negative, so a hospital never deliberately under-bids
below metered demand. For other consumers the noise can be negative.

A consumer splits demand into a fixed part and a flexible part:

```text
fixed_qty = demand · (1 − flexibility)
flex_qty  = demand · flexibility
```

and submits two bids:

| Part | Quantity | Price | Priority |
| --- | --- | --- | --- |
| Fixed | `demand · (1 − flexibility)` | `min(max_price, max_price · 1.2^(round−1))` | hospital 1, residential 2, factory 3 |
| Flexible | `demand · flexibility` | `min(50, 50 · 1.2^(round−1))` | 4 |

Hospitals have flexibility 0, so they submit only the fixed bid. Residential and
factory agents submit both. The ceiling is a hard cap: the negotiation protocol
also rejects any buy order above the published ceiling.

The previous deferred amount is added to the next hour's demand. If that amount
is deferred again, it rolls forward again; the implementation does not enforce a
single one-hour rebound beyond the next step. This is worth knowing when reading
the deferred-energy metric.

### 5.3 Producers

`ProducerAgent` offers its entire available generation in every round.

```text
base_price = marginal_cost · (1 + markup)
round 1:   ask = base_price
round >1:  ask = max(marginal_cost, base_price · 0.95^(round−1))
```

The markup starts at `initial_markup = 0.2`. After settlement:

* if at least 95 % of the available generation was sold, markup increases by
  0.05 (capped at 1.0);
* otherwise markup decreases by 0.05 (floored at 0.0).

The producer never asks below its marginal cost in a later round. All producers
use priority 4, so their asks are ordered by price and then by agent id.

### 5.4 Storage

`StorageAgent` is a battery with capacity, maximum charge/discharge rate,
round-trip efficiency and state of charge (SoC). The SoC update after settlement
is:

```text
soc(t+1) = soc(t) + (efficiency · bought − sold / efficiency) / capacity
```

with `soc` clipped to `[0, 1]`. `bought` and `sold` are MW for the hour, and
the division by capacity converts the net MWh into a ratio.

The policy abstraction is `StoragePolicy.act(obs) -> int`:

* `0` wait;
* `1` charge;
* `2` discharge.

The default `RulePolicy` uses the last price and the 24-hour average:

* if the average is not positive, wait;
* if `last_price < 0.85 · average`, charge;
* if `last_price > 1.15 · average`, discharge;
* otherwise wait.

`StorageAgent.decide()` turns the action into an order:

* charge quantity is `min(max_rate, (1 − soc) · capacity / efficiency)`;
* discharge quantity is `min(max_rate, soc · capacity · efficiency)`;
* charge price is `min(50, reference · 1.2^(round−1))`;
* discharge price is `reference · 0.95^(round−1)`;
* `reference` is the 24-hour average price, falling back to the last price and
  then to 1.0;
* storage orders use priority 4.

The agent asks its policy for an action in every negotiation round, so the
quantity limits and round-dependent prices are recomputed each round. A learned
`QPolicy` is greedy (`epsilon=0`) at run time and recomputes the discrete state
from each observation.

`StorageAgent.snapshot()` exposes `soc`, `soc_mwh`, `capacity_mwh`,
`max_rate_mw`, `efficiency`, `avg_price_24h`, `last_action`, `bought_mw`,
`sold_mw` and the policy class name.

---

## 6. The double auction, negotiation and settlement

### 6.1 Orders and trades

`market/orders.py` defines the frozen `Order` and `Trade` structures. An order
has an agent id, side (`buy` or `sell`), quantity in MW, limit price in currency
per MWh, priority and round. A trade has a buyer id, seller id, quantity and
price. Both enforce their field constraints at construction time.

### 6.2 Clearing

`DoubleAuction.clear()` implements a uniform-price double auction with partial
matching:

1. Bids are sorted by descending price, then ascending priority, then agent id.
2. Asks are sorted by ascending price, then ascending priority, then agent id.
3. The highest bid is matched with the cheapest ask while `bid_price >= ask_price`.
4. Each match uses the smaller remaining quantity, so partial fills are possible.
5. The uniform price is `(last_matched_bid + last_matched_ask) / 2`.
6. If no pair matches, the previous clearing price is kept.

The "last matched" values are the bid and ask of the final matched pair, not the
first pair and not a separate marginal-price calculation. All trades in the
round receive that same price. `ClearingResult` records the round, price, trades
and total cleared MW.

### 6.3 Negotiation rounds

`GridModel` collects round 1 orders, clears, then for auction modes runs rounds
`2..simulation.rounds` (three rounds by default). In each round:

* every agent calls `decide(round)` again;
* consumers raise their bid by `1.2^(round−1)`, capped at their ceiling;
* producers lower their ask by `0.95^(round−1)`, floored at marginal cost;
* storage adjusts its charge/discharge price by the same round factors;
* `RaiseFactorNegotiation.refine()` validates that each order belongs to the
  current round and that no buy order exceeds the published ceiling;
* the market clears the refined list again.

The protocol is stateless; agents own their own history and counter-offer logic.
The final settlement uses the trades and price of the last round.

Central modes do not run negotiation rounds. They still collect round-1 orders
from the agents (because the model's order collection is common), but the
central adapter ignores the order book and clears from the LP plan.

### 6.4 Settlement

`DoubleAuction.settle()` computes, for each consumer:

```text
shortfall = max(0, demand − bought)
flexible  = demand · flexibility
deferred  = min(shortfall, flexible)
unserved  = shortfall − deferred
```

`deferred` is flexible demand shifted to a later hour; `unserved` is the
inflexible remainder. Payments are:

```text
buyer payment  += trade.quantity · trade.price
seller payment −= trade.quantity · trade.price
```

Payments are net per agent and sum to zero across the trade set. Producers
receive a negative payment (they are paid), consumers pay positive amounts, and
storage can appear on either side depending on whether it charged or discharged.

### 6.5 What the `messages` count means

`StepResult.messages` is the number of orders submitted in all rounds of the
step, not the number of network packets or a separate chat protocol. It is the
project's proxy for negotiation activity. The Dashboard displays both the
current hour's count and the run total.

---

## 7. Central planning with a linear program

### 7.1 The planner

`CentralLPPlanner` solves the hourly dispatch problem with
`scipy.optimize.linprog(method="highs")`. Its objective is:

```text
min  Σ_τ [ Σ_k marginal_cost[k] · g[k,τ]
         + Σ_i VOLL[i] · u[i,τ] ]
```

where `g[k,τ]` is generation by producer `k` in hour `τ` and `u[i,τ]` is
unserved demand of consumer `i`. The variable block per hour is:

```text
g[producer], u[consumer], charge[storage], discharge[storage], soc[storage]
```

Bounds are:

```text
0 ≤ g[k,τ]      ≤ available_generation[k,τ]
0 ≤ u[i,τ]      ≤ demand[i,τ]
0 ≤ charge[s,τ] ≤ max_rate[s]
0 ≤ discharge[s,τ] ≤ max_rate[s]
0 ≤ soc[s,τ]    ≤ capacity[s]
```

Equality constraints are:

* energy balance for every hour:

  ```text
  Σ_k g[k,τ] + Σ_s discharge[s,τ] − Σ_s charge[s,τ]
      + Σ_i u[i,τ] = Σ_i demand[i,τ]
  ```

* battery dynamics for every storage unit:

  ```text
  soc[s,τ] − soc[s,τ−1] − efficiency[s] · charge[s,τ]
      + discharge[s,τ] / efficiency[s] = 0
  ```

  with the first hour using the current SoC (or configured initial SoC) as its
  right-hand side.

Charge and discharge have a tiny cost (`1e-6`) so the solver does not add
unnecessary cycling. There are no transmission, reserve, ramp-rate or
simultaneous charge/discharge constraints beyond these bounds and equalities.

### 7.2 Replanning and execution

`CentralMarketAdapter` exposes the planner through `MarketInterface`:

* `central_1h` replans every hour (`interval=1`);
* `central_6h` replans every six hours (`interval=6`, the configured horizon).

When a replan is due, the adapter builds a forecast, calls
`CentralLPPlanner.plan_horizon()`, and caches one `DispatchPlan` per forecast
hour. Between replans it executes the cached plan for the current hour. If the
current hour is missing from the cache, it replans.

Execution is not a blind copy of the LP plan:

* actual generation is capped by both the plan and the currently available
  generation;
* actual discharge is capped by the plan and by the energy currently in the
  battery;
* charging is allowed only from actual surplus after demand is covered, and the
  total charge is scaled down if the surplus is smaller than planned;
* if total supply is below demand, charging is zero;
* remaining energy is allocated to consumers in descending VOLL order, so
  hospitals are served first and factories last;
* unserved energy is the remainder after that allocation;
* central settlement reports zero deferred energy.

The execution price is the maximum marginal cost among the sellers actually
used (storage discharge is valued at the configured `max_prices.flex`, 50). If
no seller is used, the previous price is kept. This is an execution price, not
the LP dual variable.

### 7.3 Forecast path

The adapter uses `Environment.forecast(t, horizon)` when an environment is
available. If the forecast cannot be built, it falls back to repeating the
current demand and generation for the horizon. In both cases it replaces the
first hour with the actual demand and generation from the market context.

The forecast has no future-event knowledge. A 6-hour central plan therefore does
not anticipate an event that starts later; a 1-hour plan reacts to the current
hour. This is part of the comparison, not a hidden oracle.

### 7.4 A deliberate economic behaviour

The central LP minimises generation cost plus VOLL. The official VOLL for a
factory is 40, while the thermal marginal cost is 45. The LP can therefore find
it cheaper to leave factory demand unserved than to dispatch thermal generation
for it. This is visible in the results and is not a solver failure. It also
means that central social cost and unserved energy are not a clean like-for-like
reliability comparison with the auction, which serves load according to bids and
priorities rather than a VOLL objective.

---

## 8. Tabular Q-learning for the battery

### 8.1 State space

`ai/qlearning.py` discretises the battery state into exactly 60 states:

* 5 SoC bins, equal-width over battery capacity;
* 3 price bins: cheap (`price < 0.85 · 24h mean`), normal, expensive
  (`price > 1.15 · 24h mean`);
* 4 six-hour periods: night (00–06), morning (06–12), midday (12–18), evening
  (18–24).

The flat index is:

```text
state = (soc_bin · 3 + price_bin) · 4 + period
```

`state_from_observation()` reads capacity, SoC in MWh, last price, 24-hour
average price and hour from the model observation. It uses the configured
low/high price ratios and bin counts. `state_index()` is the lower-level helper
used by the dashboard's state explorer.

### 8.2 Actions and reward

There are three actions: wait (0), charge (1), discharge (2). During training,
`TrainingPolicy` computes the immediate reward after each settlement:

```text
throughput = bought_mw + sold_mw
reward = price · sold_mw − price · bought_mw
         − 0.5 · throughput
         − 0.5 · system_unserved_mw · 1[SoC < 1]
```

The last term uses the system-wide unserved energy from the settlement, not an
agent-specific share. It penalises leaving the battery empty when the system is
short. The factor 0.5 on throughput discourages unnecessary cycling.

The tabular update is:

```text
target = reward + γ · max_a' Q(next_state, a')   (or reward at terminal)
error  = target − Q(state, action)
Q(state, action) += α · error
```

with `α = 0.1` and `γ = 0.95` from `config/default.yaml`. The learner validates
state and action ranges and rejects non-finite rewards.

### 8.3 Training

`ai/train.py` provides `train_storage_policy()` and the CLI `python -m ai.train`.

Official training setup:

| Parameter | Value |
| --- | --- |
| Episodes | 2000 |
| Steps per episode | 168 |
| Scenario per episode | Uniformly drawn from the five official scenarios |
| Training seed per episode | `1000 + episode` |
| Exploration | ε-greedy, linear from 1.0 to 0.05 over 1500 episodes |
| Learning rate α | 0.1 |
| Discount γ | 0.95 |
| Q-table shape | `(60, 3)` |
| Default output | `qtable.npy` |
| Default curve | `results/learning_curve.csv` |

The training loop builds an `auction` model for each episode, injects a
`TrainingPolicy` for every battery through `policy_factory`, and runs all 168
hours. All other agents keep their fixed rules. At the end of an episode, each
policy closes its final transition with `done=True`. The learner is shared by
the battery policies; the reward recorded for the episode is the sum across
batteries, and the TD-error series is the mean absolute error across their
updates.

Outputs:

* `qtable.npy` (or the `--output` path);
* `results/learning_curve.csv` with one row per 50-episode window:
  `episode, mean_reward, std_reward, mean_td_error, epsilon`;
* `results/training_metadata.json` with episodes, seed, α, γ, epsilon schedule,
  Q-table path and shape, curve path and final mean reward.

The persisted metadata in this repository records 2000 episodes, a `(60, 3)`
table, a final mean reward of 691.9550733027537 and the official
hyperparameters. The current table has 180 non-zero entries (60 states × 3
actions).

### 8.4 Run-time policy

`QPolicy.from_file()` creates a `TabularQAgent`, loads the table, validates its
shape and exposes a greedy policy. `build_agents()` gives every storage agent a
`QPolicy` backed by one shared learner when a Q-table is supplied. During a run:

* `QPolicy.act(obs)` computes the discrete state and calls the learner with
  `epsilon=0.0`;
* `QPolicy.last_state` records the most recent state for tests and inspection;
* the storage agent still applies its physical limits and round-dependent
  prices.

The Q-table is **not** updated during normal runs or during the dashboard's
fresh comparison. Learning happens only in `ai/train.py`.

### 8.5 Why this is not deep RL

The state is a hand-designed 60-cell discretisation. The Q-table has one value
per state-action pair. There is no neural network, no replay buffer, no target
network and no multi-agent learning. Consumers and producers remain rule-based.
The project's claim is limited to a tabular storage policy, and the guide keeps
that scope explicit.

---

## 9. Experiments, metrics, statistics and artefacts

### 9.1 The experiment grid

`experiments/runner.py` enumerates the official grid deterministically:
systems in official order, then scenarios in official order, then seeds. Each
`ExperimentSpec` has a stable id:

```text
<system>__<scenario>__seed<seed>
```

For example: `auction__plant_outage__seed7`.

Every run builds a fresh model with `build_model()`, steps until the clock is
finished, computes metrics from the logger, and writes a per-run CSV to
`results/runs/<experiment_id>.csv` with `system`, `scenario` and `seed`
prepended. The full grid is 600 runs × 168 steps = 100,800 step rows.

The runner commands are:

```bat
.venv\Scripts\python.exe -m experiments.runner --seeds 30
.venv\Scripts\python.exe -m experiments.runner --dry-run
.venv\Scripts\python.exe -m experiments.runner --seeds 1 --systems auction central_6h --scenarios normal --output results/smoke
```

`--systems`, `--scenarios`, `--seed-start`, `--output`, `--qtable`, `--config`
and `--quiet` are supported. `--dry-run` prints the selected grid size without
executing it. `auction_q` refuses to run if its Q-table is missing.

### 9.2 Metrics

`experiments/metrics.py` computes metrics from the step log. When a
configuration is supplied, marginal costs, VOLL values, consumer types, storage
capacity and scenario timing come from it. An empty log returns zeros rather
than raising.

| Metric | Definition |
| --- | --- |
| `generation_cost` | `Σ_producer marginal_cost · sold_mw` over the run |
| `voll_penalty` | `Σ_consumer VOLL(type) · ue_mw` over the run |
| `social_cost`, `cost_total` | `generation_cost + voll_penalty` |
| `cost_mean_per_mwh` | `social_cost / served_energy`, where served is demand minus unserved minus deferred |
| `ue_total`, `unserved_energy_mwh` | Sum of `unserved_mw` over all steps |
| `deferred_energy_mwh` | Sum of `deferred_mw` over all steps |
| `ue_hospital`, `ue_residential`, `ue_factory` | Unserved energy summed by consumer type |
| `hospital_outage_hours` | Number of hours in which any hospital has UE > 0.001 |
| `price_mean` | Mean clearing price over the run |
| `price_volatility` | Sample standard deviation of the clearing price (`ddof=1`) |
| `par` | Peak served demand / mean served demand |
| `gini` | Gini coefficient of consumer average paid price per MWh |
| `recovery_time` | Hours until price and UE return to the pre-event band, or the remaining window if censored |
| `messages` | Sum of order messages over all steps |
| `renewable_share` | Solar + wind sold energy / total sold energy |
| `self_sufficiency` | `1 − ue_total / demand_total` |
| `storage_cycles` | `Σ_battery (bought + sold) / (2 · capacity)` |

`served` in the PAR calculation is `max(0, demand − unserved − deferred)`.
`gini` is computed over consumers with positive bought energy and positive
payments; it measures inequality of average paid price, not income. If fewer
than two consumers qualify, it returns 0.

`recovery_time` is worth understanding because it is easy to misread:

1. The event start is the minimum start over the scenario's events.
2. The baseline price is the mean of the 24 hours before the event (or the whole
   run mean if there is no such window).
3. The tolerance is 10 % of the absolute baseline.
4. A step is stable when the price is within tolerance and unserved energy is at
   most 0.001 MW.
5. The first run of three consecutive stable steps ends recovery; the returned
   value is `offset − start − 2`.
6. If the criterion is never met, the metric returns `steps − start`, which is
   the remaining window. That is a censored value, not a measured recovery
   time.

The central systems' standing factory shortfall means their UE condition can
never clear after an event, so their recovery values are censored at the window
end. The Compare page calls this out explicitly.

### 9.3 Statistics

`experiments/stats.py` implements:

* `summarise_runs()`: for each `(scenario, system, metric)`, mean, sample
  standard deviation (`ddof=1`), 95 % bootstrap interval, min and max. The
  bootstrap uses 1000 resamples, percentile 2.5/97.5, with a fixed RNG seed
  (`20_240_517`).
* `paired_comparison(baseline, treatment)`: merges the two systems on
  `(scenario, seed)`, computes treatment − baseline differences, the mean
  difference, the relative effect and a two-sided Wilcoxon signed-rank test.
  Zero differences are discarded; fewer than two non-zero differences produce
  `p=1`.
* `pairwise_comparisons()`: every unordered pair of systems, with Bonferroni
  correction over the total number of performed rows. `p_adjusted =
  min(1, p · number_of_tests)` and `significant = p_adjusted < 0.05`.

The default metric list has 12 metrics. With 4 systems there are 6 unordered
pairs, so the full grid produces 12 × 6 × 5 = **360 paired tests**. The
dashboard displays the Bonferroni family size alongside the filtered table. A
significant result means the paired difference survives the correction; it does
not by itself establish practical importance or a clean causal comparison.

### 9.4 Aggregates and figures

`ExperimentRunner.run_all()` writes:

| Artefact | Content |
| --- | --- |
| `results/raw.csv` | One metric row per run |
| `results/steps.csv` | One step row per simulated hour across all runs |
| `results/metrics_summary.csv` | Mean, SD, bootstrap interval, min and max per cell |
| `results/stats_pairwise.csv` | Paired Wilcoxon rows with Bonferroni adjustment |
| `results/runs/` | Per-experiment step logs |
| `results/figures/` | Six report figures |
| `results/run_metadata.json` | Design, timing, Q-table provenance and figure paths |
| `docs/report/REPORT.md` | Generated Markdown report |

The six figures produced by `experiments/plots.py` are:

1. social cost by scenario and system;
2. price response during the plant outage;
3. recovery and unserved energy;
4. Q-learning learning curve;
5. Q-table heatmap;
6. per-run social-cost distribution.

The runner loads `results/learning_curve.csv` and `qtable.npy` if present. If the
Q-table is absent it uses a zero table for figure generation, but `auction_q`
experiments still fail loudly because the run itself requires a trained table.

### 9.5 The 600-run artefacts in this repository

`results/run_metadata.json` records 600 runs, 168 steps per run, 30 seeds,
the four systems, the five scenarios, a loaded Q-table and the six figure
paths. `results/raw.csv` has one row per run and `results/steps.csv` has 100,800
rows. `results/training_metadata.json` records the Q-learning hyperparameters
and the final mean reward.

The final delivery report summarises the observed behaviour, including the
important caveats: hospital load is fully served in all runs; the auction
recovers from events while central recovery values are censored; the central LP
sheds factory load because factory VOLL is below thermal marginal cost; and the
learned battery lowers modelled social cost slightly but raises total unserved
energy in the saved experiments. Those are results of the current calibration,
not architectural guarantees.

---

## 10. Dashboard shell and global controls

### 10.1 Entry point

The dashboard is a Streamlit application with one entry point:

```bat
streamlit run ui/app.py
```

`ui/app.py` adds the repository root to `sys.path` before importing `core`, so
it works even when Streamlit is launched from another directory. It calls
`st.set_page_config(layout="wide")`, injects the theme, consumes any pending
navigation, renders the sidebar, renders the app header and dispatches to one of
the four views.

The shared dark theme is in `.streamlit/config.toml` and `ui/theme.py`:

```text
background  #070B10
surface     #0F151D
accent      #34D399
text        #E6EDF3
```

The CSS requests Inter for UI text and JetBrains Mono for data, with system
fallbacks. It hides the Streamlit toolbar and footer, styles the sidebar as a
navigation list, styles KPI cards, tables, badges, callouts and empty states,
and provides responsive rules:

* paired charts stack below 1180 px;
* KPI grids drop to three columns below 1180 px and two below 1024 px;
* the comparison matrix becomes labelled per-scenario rows on narrow screens;
* `prefers-reduced-motion` disables animations.

### 10.2 Sidebar controls

All global controls are rendered by `_sidebar()` in `ui/app.py`.

| Section | Control | Behaviour |
| --- | --- | --- |
| Workspace | Page radio | `Live Simulation`, `Market Board`, `Compare`, `Learning` |
| Run settings | System selectbox | One of the four official systems; labels come from `ui/data.py` |
| Run settings | Scenario selectbox | One of the five official scenarios; a caption shows its description |
| Run settings | Seed number input | 0–999,999, default 0, step 1 |
| Agent fleet | Hospitals slider | 1–4, default from config (2) |
| Agent fleet | Residential slider | 1–8, default 4 |
| Agent fleet | Factories slider | 1–6, default 3 |
| Agent fleet | Batteries slider | 1–4, default 2; caption notes the 20-agent cap |
| Playback | Speed (steps/s) | 1–20, default 4 |
| Playback | Demo script button | Sets scenario `combined`, navigates to Live Simulation, resets the model and autostarts |
| Runtime events | Trip thermal plant | Injects thermal capacity factor 0.3 for 12 hours at the current step |
| Runtime events | Demand spike (+40%) | Injects residential demand ×1.4 for 6 hours at the current step |
| Runtime events | Weather shift | Injects cloud override 0.2 and wind capacity ×0.5 for 24 hours at the current step |
| Reference | Captions | “4 official systems · 5 scenarios · 168-hour horizon” and a provenance note |

The event buttons are disabled when no model exists or the model has finished.
If no model exists, the sidebar says to open Live Simulation once. Event names
are made unique with a session counter, and the event is scheduled from the
current clock step. A validation failure is shown as a sidebar error; success
shows “Event queued at hour N.”

The fleet sliders are not independent in practice. The default combination
(2 hospitals + 4 residential + 3 factories + 2 batteries + 4 producers) is 15
agents. Some slider extremes would exceed the configured 20-agent cap; the
configuration validation rejects them and the Live page shows a model-build
error rather than starting an invalid run.

### 10.3 Run identity and model lifecycle

`ui/state.py` owns the session model. The model signature is:

```text
(mode, scenario, seed, hospitals, residential, factories, batteries)
```

`ensure_model()` rebuilds the model when any of these changes. Speed is not part
of the signature: changing speed only affects playback. The model is kept in
`st.session_state["gm_model"]`; the signature is kept separately.

`reset_model()` discards the model, pauses playback, clears the step error and
clears the saved fresh learning comparison. `safe_step()` catches any exception
from `model.step()`, pauses playback, records `gm_step_error`, and returns
`False`, so the page can render an error state instead of a traceback.

A model is built with `with_fleet()` to apply the sidebar counts, then
`build_model()` with the selected mode, scenario and seed. A missing Q-table,
an invalid fleet or a backend failure becomes a `ModelBuildError` or an error
state with a hint.

### 10.4 Runtime events

`_inject_event()` calls `model.inject_event()` with a unique name, the current
step, the requested duration and the event parameters. It uses the same
`EventManager` and the same validation as the scenario catalogue. The event is
visible in the Live page's scheduled/active event timeline and as vertical lines
on the history chart. Events cannot be injected into a finished run, and there
is no undo: reset the model to start over.

### 10.5 Data provenance and empty states

The UI never computes a simulated value itself. It calls `GridModel` for live
state and `ui/data.py` for persisted artefacts. `ui/data.py` loads:

```text
results/raw.csv
results/metrics_summary.csv
results/stats_pairwise.csv
results/learning_curve.csv
results/training_metadata.json
qtable.npy
results/figures/*.png
```

CSV, JSON and NPY loads are cached with `st.cache_data`, keyed by path and file
modification time. Required files raise `DataError` with an actionable message;
optional files return `None`. The views turn these into empty or error states
with the exact regeneration command, such as:

```bat
python -m ai.train
python -m experiments.runner --seeds 30
```

The dashboard does not invent placeholder numbers. If `qtable.npy` is missing,
the Learning page cannot load; if `raw.csv` is missing, Compare cannot render
its KPIs. Live Simulation and Market Board can still build a model because
they do not require saved experiments.

---

## 11. The four dashboard pages

### 11.1 Live Simulation

Module: `ui/views/live.py`.

**Purpose.** Step or play one official run, inspect the agent network,
environment, event timeline, market history, agent fleet, step log and run
manifest.

**Header.** Badges show the system label, scenario label and run status
(`Not started`, `Paused`, `Live · stepping`, `Run complete`). The page title is
“Live simulation”; the eyebrow is “Simulation console”.

**Playback card.** Contains:

* a clock panel: “Hour t / steps”, day number and `HH:00`, a `RUNNING`,
  `PAUSED` or `COMPLETE` badge and the current speed;
* `Play` / `Pause` button;
* `Step 1h`;
* `Run 10h` (stops early if the run finishes or a step fails);
* `Reset` (discards the model, then tries to rebuild it);
* a progress bar showing `t / steps` simulated hours;
* a caption with temperature, effective cloud, wind index and solar profile.

When playback is running, the page steps once, sleeps `1 / speed` seconds and
reruns. Playback stops automatically when the run finishes.

**KPI row.** Five cards:

| KPI | Value and detail |
| --- | --- |
| Simulation hour | `t` of `steps`, day and `HH:00`; sparkline of recent prices |
| Clearing price | Current price per MWh, system label, recent price sparkline |
| Generation | Total available MW, demand and `supply − demand`; info tone if supply ≥ demand, warning otherwise; recent supply sparkline |
| Unserved energy | Current MW, cumulative MWh from the log; danger tone if positive; recent sparkline |
| Deferred load | Current MW, cumulative MWh; recent deferred sparkline |

The sparklines use the last 48 log rows.

**Agent network.** A Plotly network with:

* producers as diamonds on top, consumers as circles along the bottom (two
  staggered rows), batteries as squares on the right;
* a hexagonal hub labelled `DOUBLE AUCTION` or `CENTRAL LP` with the current
  price;
* normal edges in muted grey; edges to consumers with positive unserved energy
  in red dotted style;
* node labels `S`, `W`, `T`, `P` for producer types and `H`, `R`, `F`, `B` for
  consumer/storage types, numbered within type;
* node size encodes output/capacity, SoC, or demand;
* hover text gives the full agent state (output, marginal cost, markup, SoC,
  last action, demand, unserved, bought).

**Latest environment.** Four labelled magnitude bars: temperature (scaled from
−5 to 40 °C), effective cloud cover, wind index and solar profile. These are
the A2/A3 values for the current hour.

**Disruption schedule.** Up to four events sorted active first, then upcoming,
then passed. Each row shows the start hour as `H###`, the event name, the step
range and duration, and a badge `Active now`, `in N h` or `Passed`. If the
scenario has no events, it shows an empty state.

**Market and storage over time.** A three-row Plotly figure:

1. clearing price and its 24-hour rolling mean;
2. supply, demand and unserved energy;
3. one line per battery state of charge.

Scheduled events appear as dashed vertical lines with labels in every row.

**Tabs.**

* **Agent fleet**: a table of agents with role, type, demand, available MW,
  capacity, SoC (progress column), bought/sold, deferred/unserved, markup, last
  action and policy. Columns are included only when present.
* **Step log**: the last 24 rows of `t`, price, supply, demand, unserved,
  deferred and messages. `t` is renamed to `hour` in the display.
* **Run manifest**: system, scenario, seed, horizon, progress, fleet counts,
  active events and number of scheduled events, plus a note that a new model is
  built when the run settings change and that runtime events are injected into
  the current model.

When the run finishes, a success callout says every scheduled hour is complete
and offers an `Open Compare` button that navigates to the Compare page.

### 11.2 Market Board

Module: `ui/views/market.py`.

**Purpose.** Inspect the final clearing hour: order depth, negotiation rounds,
net positions, supply/demand mix, message activity, orders and trades.

**Header.** Badges show system, scenario and `Hour N`. The page title is
“Market board”; the eyebrow is “Market microstructure”.

**Empty state.** If the model has no results yet, the page shows “The order book
is still empty” and an `Execute one hour` button. This is a real empty state,
not fabricated data.

**KPI row.**

| KPI | Meaning |
| --- | --- |
| Clearing price | Current price per MWh and simulated hour |
| Messages this hour | Orders in the final hour; detail shows the run total |
| Executed trades | Number of trades and total matched MW in the final round |
| Traded value | Sum of `quantity × price` over final trades |
| Hospital blackout | Hours in the log in which any hospital agent had UE > 0.001; accent tone if zero, danger if positive |

**Central callout.** If the mode starts with `central`, an info callout explains
that central LP dispatch clears by optimisation rather than by matching a
bid/ask book.

**Clearing diagnostics.** A definition grid with bid volume, ask volume,
negotiation rounds, order count, trade count, price change versus the first hour,
run messages and progress.

**Charts.**

* **Order depth**: cumulative bid and ask curves (volume on x, price on y) with
  a dotted clearing-price horizontal line.
* **Negotiation rounds**: grouped bars of ordered volume by round and side.
* **Net positions**: horizontal bars of bought minus sold per agent in the final
  hour; positive means net buyer, green for buyers and red for sellers.
* **Supply and demand mix**: two horizontal bar panels, generation by producer
  type and demand by consumer type.
* **Market activity**: message bars on the left axis and unserved MW on the
  right axis over the whole log; with only one hour it shows a large annotation
  and asks for a second hour.

**Tables.**

* **Orders of the final hour**: every order in the snapshot, with round, agent,
  side (Bid/Ask), quantity, limit price and priority. If the order list is
  empty, the page explains that the order book is empty or that central
  dispatch does not emit a book.
* **Executed trades**: buyer, seller, quantity and price for the final round. If
  no trade matched, an empty state explains that no buyer and seller overlapped.

**Important nuance.** In the current implementation, central modes still collect
round-1 orders from the agents and still record the central adapter's trades in
`StepResult`. The central adapter ignores the order book for clearing, so those
orders are not the cause of the dispatch. The page therefore shows real recorded
orders and trades even in central mode when they exist, while the callout says
the clearing mechanism is optimisation. Read the order table in central mode as
agent submissions, not as the central clearing mechanism.

### 11.3 Compare

Module: `ui/views/compare.py`.

**Purpose.** Read the persisted 600-run grid and compare systems on cost,
reliability, fairness, statistical tests and the exact report figures.

**Dependency.** Compare requires `results/raw.csv`. If it is missing or empty,
the page shows an empty state with the command
`python -m experiments.runner --seeds 30`.

**Header.** Badges show “Official grid”, the number of runs and the number of
system/scenario cells. The page title is “Compare systems”; the eyebrow is
“Evaluation workspace”.

**Experiment filter.** A bordered card with two multiselects:

* **Systems**: all systems present in `raw.csv`, in official order, default all;
* **Scenarios**: all scenarios present, in official order, default all.

If exactly one scenario is selected, its official description is shown. Every
chart, matrix and table below respects the filter except the global central
caveat and the report-figures tab (which are not filterable).

**KPI row.**

| KPI | Calculation |
| --- | --- |
| Runs selected | Number of filtered raw rows; detail shows distinct seeds and cells |
| Mean social cost | Mean of `social_cost`; detail names the lowest-mean system |
| Mean unserved | Mean `ue_total` in MWh; tone changes at 50 and 500 MWh |
| Mean recovery | Mean `recovery_time` in hours; detail counts censored central cells |
| Renewable share | Mean `renewable_share` as a percentage |

**Central caveat.** If any selected system starts with `central`, a warning
callout compares the mean factory UE of all auction rows and all central rows
in the full `raw.csv`, not just the filtered subset. It explains that factory
VOLL 40 is below thermal marginal cost 45, that central systems therefore shed
factory load, and that social cost and UE are not a clean like-for-like
reliability comparison. It also notes central recovery censoring.

**Mean social cost matrix.** A scenario-by-system HTML matrix. Each cell shows
the mean social cost; the best value in each row gets a `BEST` tag. A coloured
bar is scaled relative to the row maximum. Lower is better. The caption defines
social cost as generation cost plus VOLL penalty, averaged over selected seeds.

**Charts.**

* **Social cost**: grouped bars by scenario and system, one-standard-deviation
  error bars.
* **Reliability**: two stacked panels, unserved energy (MWh) and recovery time
  (hours), with standard-deviation error bars.
* **Fairness**: two stacked panels, peak-to-average ratio and Gini coefficient,
  averaged over the selected rows.
* **Cost versus reliability**: bubble scatter of mean social cost versus mean
  UE per system/scenario; bubble size reflects renewable share.
* **Per-run distribution**: box plot of every seed's social cost with all points
  shown.

**Tabs.**

* **Metric summary**: select one metric from
  `metrics_summary.csv`; the table shows scenario, system, n, mean, SD, 95 %
  low and high. The caption uses `ui/data.py` metric help. If the summary file
  is missing, an empty state gives the runner command.
* **Pairwise tests**: select one metric from `stats_pairwise.csv`; the table
  shows scenario, baseline, treatment, pairs, mean difference, relative effect,
  raw p, Bonferroni p and significance. The badge counts significant rows in
  the filtered table; the caption states the full correction family size. If
  the file is missing, an empty state gives the runner command.
* **Run data**: the filtered per-run table with system, scenario, seed, social
  cost, UE total/hospital/factory, hospital outage hours, recovery, messages,
  renewable share, PAR and Gini. A `Download filtered CSV` button exports the
  filtered rows.
* **Report figures**: every PNG in `results/figures`, sorted, in two columns,
  with captions for the six known names. These are the exact files written by
  the report pipeline; they are not regenerated in the dashboard. If no PNGs
  exist, an empty state gives the runner command.

### 11.4 Learning

Module: `ui/views/learning.py`.

**Purpose.** Read the persisted Q-table, training curve and metadata, inspect the
learned policy, and compare the saved rule-based and learned auction results.

**Dependency.** Learning requires `qtable.npy` with shape `(60, 3)` and finite
values. If it is missing, the page shows an error state with
`python -m ai.train`. `results/learning_curve.csv` and
`results/training_metadata.json` are optional; their absence produces smaller
KPI values or an empty curve, not a crash.

**Header.** Badges show “Tabular Q-learning”, episode count and final mean
reward, or the table shape when metadata is absent. The page title is
“Learning”; the eyebrow is “Learning laboratory”.

**KPI row.**

| KPI | Meaning |
| --- | --- |
| Training episodes | Metadata episodes; falls back to the last curve episode |
| Final mean reward | Metadata `final_mean_reward`; falls back to the last curve value |
| Final TD error | Last `mean_td_error` checkpoint |
| States visited | Rows of the Q-table with any non-zero value, out of 60 |
| Discharge states | States where the greedy action is discharge; detail gives charge and wait counts |

**Learning curve.** A three-row figure:

1. mean reward per 50-episode window with a ±1 SD band;
2. mean TD error;
3. exploration rate ε, with a dotted vertical line at the configured decay
   episode (1500).

**Tabs.**

* **Policy explorer**:
  * a `Heatmap layer` selectbox with `Greedy policy`, `Q(wait)`,
    `Q(charge)`, `Q(discharge)`;
  * a 5 × 12 heatmap representing 5 SoC rows × (3 price regimes × 4 periods);
    greedy policy cells show `W`, `C`, `D`; Q-value views show the numeric
    value with a colour scale;
  * a state explorer with three selectboxes: State of charge, Price regime and
    Period. It computes a representative state index from the production
    discretisation and shows the three Q-values, the greedy action and the
    state index;
  * a greedy action mix for all 60 states, as a stacked bar plus counts and
    percentages;
  * a definition grid with the algorithm, α, γ, ε schedule, decay episodes and
    reward description.
* **Rule vs Q**:
  * saved-evidence KPIs: mean rule-based and learned social cost, rule-based and
    learned UE, and the number of saved comparison pairs;
  * a two-panel bar chart of relative change from rule to Q for social cost and
    UE, with positive values meaning Q is higher;
  * a per-scenario table with rule cost, Q cost, cost delta, rule UE, Q UE, UE
    delta and mean Q cycles;
  * a **Fresh 168-hour comparison** card: scenario selectbox, current sidebar
    seed as a read-only metric, and a `Run 168-hour comparison` button. It builds
    `auction` and `auction_q` with the default configuration, runs both to
    completion, computes the standard metrics and displays social cost, UE,
    recovery, renewable share and storage cycles. It does not train, does not
    use the sidebar fleet sliders, and stores the result only in the session.
* **Training artefacts**: metadata grid with episodes, seed, α, γ, epsilon
  start/end, decay episodes, Q-table shape and final mean reward; a raw JSON
  expander; the static `fig4_learning_curve.png` and
  `fig5_qtable_heatmap.png` if they exist.

The saved evidence uses the full `raw.csv` (all 150 runs per auction variant on
the full grid), not the current Compare filter. The fresh comparison is a
one-seed diagnostic and is not part of the 600-run statistical evidence.

---

## 12. Installation, training, experiments and operation

### 12.1 Requirements

* Windows, macOS or Linux with Python 3.11 or newer.
* The approved stack only: NumPy, Pandas, SciPy, NetworkX, Streamlit, Plotly,
  Matplotlib, PyYAML and Pytest. Black is an optional development extra.
* No paid API, external data API, Mesa, React, FastAPI, Flask, deep-learning
  framework or RL framework is used.

### 12.2 Windows setup

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\Activate.ps1
```

The verified commands in this workspace use the interpreter directly:

```bat
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ai.train
.venv\Scripts\python.exe -m experiments.runner --seeds 30
.venv\Scripts\python.exe -m streamlit run ui/app.py
```

### 12.3 Test suite

```bat
.venv\Scripts\python.exe -m pytest -q
```

The post-audit suite reports **151 passed, 0 skipped**. The tests cover configuration,
clock arithmetic, frozen contracts, environment, model orchestration and energy
conservation, reproducibility, agents, auction and settlement, negotiation,
central LP, Q-learning, metrics, statistics, the runner, the report and the
factory. `tests/README.md` gives the file-by-file ownership and activation
notes.

### 12.4 Train the Q-learning policy

```bat
.venv\Scripts\python.exe -m ai.train
```

This writes `qtable.npy`, `results/learning_curve.csv` and
`results/training_metadata.json`. A short smoke training run is:

```bat
.venv\Scripts\python.exe -m ai.train --episodes 20 --output results/quick_qtable.npy --curve results/quick_curve.csv
```

The `auction_q` system and the Learning page require the trained table. The
runner refuses `auction_q` without it.

### 12.5 Run experiments

```bat
.venv\Scripts\python.exe -m experiments.runner --seeds 30
```

A quick subset:

```bat
.venv\Scripts\python.exe -m experiments.runner --seeds 1 --systems auction central_6h --scenarios normal --output results/smoke
```

Dry run:

```bat
.venv\Scripts\python.exe -m experiments.runner --dry-run
```

The full grid writes `raw.csv`, `steps.csv`, `metrics_summary.csv`,
`stats_pairwise.csv`, `runs/`, `figures/`, `run_metadata.json` and
`docs/report/REPORT.md`. The repository's recorded full run took 246.49 seconds
on the machine that produced `run_metadata.json`; runtime depends on hardware.

### 12.6 Start the dashboard

```bat
.venv\Scripts\python.exe -m streamlit run ui/app.py
```

Open the local Streamlit URL (by default port 8501) and use the sidebar. The
dashboard needs the repository root as its working context; `ui/app.py` repairs
`sys.path` if Streamlit is launched elsewhere.

A normal first session:

1. choose a system, scenario, seed and fleet;
2. open Live Simulation and press `Step 1h`, `Run 10h` or `Play`;
3. use the Market Board after at least one hour;
4. open Compare after the experiment grid exists;
5. open Learning after training, or after the full pipeline has produced the
   Q-table and training artefacts.

### 12.7 Regenerating artefacts

| Missing or stale artefact | Command |
| --- | --- |
| `qtable.npy`, learning curve, training metadata | `python -m ai.train` |
| `raw.csv`, summaries, pairwise tests, steps, figures, report | `python -m experiments.runner --seeds 30` |
| A subset for a quick check | `python -m experiments.runner --seeds 1 --systems auction --scenarios normal --output results/smoke` |
| A fresh one-seed dashboard comparison | Use the Learning page button; it is session-only |

The dashboard never writes the experiment artefacts. It reads them.

### 12.8 Git and results

`results/` artefacts, `qtable.npy` and local Streamlit secrets are ignored by
Git; `results/figures/.gitkeep` preserves the directory. The repository is a Git
repository, but this guide does not perform or require any Git operation.
Changes in the working tree, including this guide, remain uncommitted unless the
maintainer chooses to commit them.

---

## 13. Limitations, implementation notes and glossary

### 13.1 Architectural limitations

1. **Capacity-only electricity model.** There is no AC power flow, voltage,
   frequency, congestion, network topology or line limit. Every MW is assumed
   transportable to every consumer. This is a market/agent simulation, not a
   power-systems simulator.
2. **Synthetic data.** Weather, demand and generation are generated from
   documented equations with seeded noise. No external or real grid data are
   used. The results are specific to this calibration.
3. **VOLL calibration dominates central results.** Factory VOLL (40) is below
   thermal marginal cost (45), so the central LP can economically shed factory
   load. Central social cost and UE are therefore sensitive to the VOLL values
   and are not a clean reliability comparison with the auction.
4. **Censored recovery.** The recovery metric returns the remaining window when
   its stability criterion is never met. Central systems carry a standing
   factory shortfall, so their post-event recovery values are censored rather
   than measured.
5. **Solar/cloud implementation nuance.** `SupplyModel` multiplies solar output
   by the cloud-cover value rather than by one minus cloud cover. The
   `weather_shift` override of 0.2 therefore reduces solar output under the
   implemented equation. This should be documented in any comparison of
   weather scenarios and corrected consistently if the calibration is revised.
6. **Central order-book nuance.** Central modes still record agent orders and
   central dispatch trades in the step result, even though the adapter ignores
   the order book. The Market Board therefore shows recorded orders/trades in
   central mode; they are not the clearing mechanism.
7. **Only the battery learns.** Consumers and producers use fixed rules. The
   Q-learning state is a coarse 60-cell discretisation. This is not general
   multi-agent reinforcement learning and does not claim to be.
8. **One configuration, thirty seeds.** The reported grid uses one calibrated
   configuration and 30 seeds. Statistical significance across paired seeds does
   not establish external validity or practical importance.
9. **Conservative statistics.** Bonferroni correction over 360 tests is
   conservative. The paired-seed design makes small differences detectable;
   significance is not the same as a large effect.
10. **Dashboard scope.** The dashboard reads persisted artefacts and live
    session models. It does not retrain, persist a fresh comparison, provide
    authentication, or support multiple concurrent users. A new model is built
    when the run signature changes; runtime events live only in the current
    model.
11. **Fleet slider cap.** The individual slider ranges allow combinations above
    the 20-agent cap. Such combinations are rejected by configuration
    validation and produce a model-build error. The sliders are convenience
    controls, not a guarantee that every combination is runnable.
12. **Optional web fonts.** The stylesheet imports Inter and JetBrains Mono from
    Google Fonts. System fallbacks are configured, so the app remains usable
    without that request, but the exact typography may vary offline.

### 13.2 Behaviour that is easy to misread

* `messages` is the number of orders, not chat messages.
* `social_cost` is modelled generation cost plus VOLL penalty, not a market
  price or a bill.
* `deferred` energy is flexible load moved forward; `unserved` is the
  inflexible remainder. A consumer can defer again if it is short again.
* The auction price is the midpoint of the last matched bid and ask. It is not
  a marginal-cost price and not the LP dual.
* The central execution price is the maximum marginal cost of used sellers,
  with storage discharge valued at the flex ceiling.
* `recovery_time == steps − event_start` usually means censored, not recovered
  exactly at the end.
* The Q-table reward includes a system-wide unserved term when the battery is
  not full, not a per-agent reliability share.
* The Learning page's fresh comparison uses the default configuration and the
  current sidebar seed, not the fleet sliders, and does not train.
* The Compare page's “30 seeds per cell” badge is static; the actual seed count
  comes from the loaded `raw.csv`.

### 13.3 Troubleshooting

| Symptom | Cause | Action |
| --- | --- | --- |
| `No trained Q-table was found` | `qtable.npy` absent | `python -m ai.train` |
| `Q-table not found for auction_q` | Runner or model asked for `auction_q` without a table | Train first or choose another system |
| Compare says artefacts are missing | `results/raw.csv` absent or empty | `python -m experiments.runner --seeds 30` |
| Learning says artefacts are unavailable | Q-table missing or malformed | Retrain; check shape `(60, 3)` and finite values |
| A fleet combination will not start | Total agents exceed 20 | Reduce one or more sliders |
| Event buttons are disabled | No model yet or the run finished | Open Live Simulation to build a model, or reset |
| The simulation stopped during a step | Backend exception; details are in the UI and logs | Reset, check configuration/Q-table, inspect the error |
| Comparison filter changes nothing | Compare requires raw artefacts and a non-empty filter | Regenerate the grid; select at least one system and scenario |
| A central order table looks populated | Agent orders are recorded even though the LP clears | Read the central callout; orders are not the dispatch mechanism |

### 13.4 Glossary

| Term | Meaning in GridMind |
| --- | --- |
| **Agent** | A consumer, producer or storage unit with `observe`, `decide`, `update` and `snapshot` |
| **Ask** | A sell order; quantity in MW, limit price per MWh |
| **Auction** | The uniform-price double auction in `market/auction.py` |
| **Baseline** | In a paired test, the system subtracted from the treatment; also the pre-event price band in recovery |
| **Bid** | A buy order |
| **Central LP** | The linear-programming dispatch planner in `ai/central_lp.py` |
| **Clearing price** | The uniform price of the final auction round, or the central execution price |
| **Censored recovery** | A recovery value equal to the remaining window because the stability criterion was never met |
| **Deferred energy** | Flexible demand that was not served this hour and is added to the next hour |
| **Episode** | One 168-hour training run in `ai/train.py` |
| **ε (epsilon)** | Exploration probability in ε-greedy action selection |
| **Gini** | Inequality of consumer average paid price per MWh; 0 is equal, higher is more unequal |
| **LOLE / VOLL** | Value of lost load, the configured penalty per MWh of unserved demand |
| **Negotiation round** | One order-collection and clearing pass; up to three per auction hour |
| **PAR** | Peak-to-average ratio of served demand |
| **Q-table** | A `(60, 3)` table of action values for the battery |
| **Recovery time** | Hours until price is within 10 % of the pre-event baseline and UE is negligible for three consecutive hours |
| **Seed** | The integer that deterministically derives all random streams for a run |
| **Social cost** | Generation cost plus VOLL penalty |
| **SoC** | Battery state of charge as a ratio in `[0, 1]` |
| **TD error** | Temporal-difference error in the Q-learning update |
| **Uniform price** | One price applied to all trades in a clearing round |
| **Unserved energy** | Demand that remains unmet after deferral; the hard reliability failure |
| **VOLL** | Value of lost load, per consumer type |

---

### Final note on provenance

The implementation lives in the modules named throughout this guide. The
official parameters are in `config/default.yaml` and `config/scenarios.yaml`.
The experiment evidence is in `results/` and `docs/report/`. The dashboard reads
those files and the live `GridModel`; it does not contain a second simulation.
Where this guide describes a result, it is a result of the current code and
calibration, not a promise about a different configuration.
