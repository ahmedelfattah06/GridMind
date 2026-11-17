# GridMind Integration Contracts

**Version:** 1.0 (frozen at bootstrap; skeleton phase)
**Owner:** A1 (core model), in agreement with all four team leads
**Status:** frozen. Any change requires approval from A1, B1, C1 and D1 (one lead
per team) and a new version number in this document.

This document is the single reference for every interface that crosses a team
boundary. Code that violates these contracts is a bug even if it works locally.

---

## 1. Conventions

| Item | Rule |
| --- | --- |
| Simulation step | One hour. `t = 0 ... 167` for the official run. |
| Hour / day | `h = t % 24`, `d = t // 24`. Only `core.clock` defines this mapping. |
| Power | MW, always a finite float, never negative unless documented. |
| Energy per step | MWh, numerically equal to MW for a one hour step. |
| Money | Abstract currency units per MWh (no currency symbol, no external data). |
| Agent ids | `solar_1`, `wind_1`, `thermal_1`, `peaker_1`, `hospital_1..2`, `residential_1..4`, `factory_1..3`, `battery_1..2`. |
| Mappings | Agent level dictionaries are keyed by agent id. |
| Randomness | Every generator derives from `derive_rng(seed, stream)`. Global `np.random` calls are forbidden. |
| Missing values | Never silently defaulted. Configuration is validated by `core.config.validate_config`. |

`deferred` energy means flexible demand that is intentionally not served in the
current step. `unserved` energy means demand that could not be served at all and
is penalised with the consumer's VOLL. The exact settlement split is Team B3's
responsibility (see `docs/decision_log.md`, pending decision PD-05).

---

## 2. Agent contract (Team B1 / B2)

```python
class BaseAgent:
    agent_id: str          # unique, stable across the run
    role: str              # "consumer" | "producer" | "storage"
    agent_type: str        # "hospital" | "residential" | "factory" | "solar" | ...

    def observe(self, obs: dict) -> None: ...
    def decide(self, round: int) -> list[Order]: ...
    def update(self, result: dict) -> None: ...
    def snapshot(self) -> dict: ...
```

### `observe(obs)` — called once per step, before any decision

```python
{
    "t": 0,
    "hour": 0,
    "day": 0,
    "mode": "auction",                  # comparison system id, or "mock"
    "scenario": "normal",               # official scenario key
    "environment": {                    # EnvironmentState.as_dict()
        "temperature_c": 27.4,
        "cloud_cover": 0.81,
        "effective_cloud_cover": 0.81,
        "wind_index": 0.55,
        "solar_profile": 0.0,
        "demand_mw": {"hospital_1": 6.1, ...},        # MW per consumer
        "generation_mw": {"solar_1": 0.0, ...},       # MW available per producer
        "demand_total_mw": 43.8,
        "generation_total_mw": 85.0,
    },
    "last_price": 61.2,                 # previous clearing price, 0.0 at t=0
    "market": {"raise_factor": 1.2, "producer_step": 0.05, "initial_markup": 0.2},
    "own_agent": {...},                 # BaseAgent.snapshot() of this agent
}
```

Agents must not read other agents' private state and must not be notified
directly about events. Event names are deliberately **not** part of the
observation: only their environmental consequences (demand, generation, cloud,
temperature) are visible.

### `decide(round)` — called once per negotiation round

Returns `list[Order]`. `round` starts at `1` and never exceeds
`simulation.rounds` (maximum 3). `observe` is always called first. Orders must
carry the agent's own `agent_id` and the current `round`; the model rejects
mismatches.

### `update(result)` — called once per step, after settlement

```python
{
    "t": 0,
    "price": 61.2,              # final clearing price, currency/MWh
    "bought_mw": 6.0,           # energy bought this step, MW/MWh
    "sold_mw": 0.0,             # energy sold this step, MW/MWh
    "payment": 372.4,           # positive = paid, negative = received
    "unserved_mw": 0.0,
    "deferred_mw": 0.0,
    "generation_mw": 0.0,       # producers only, otherwise 0.0
    "soc": 0.5,                 # storage agents only, otherwise 0.0
}
```

### `snapshot()` — called for logging, `GridModel.snapshot()` and the UI

Must return a JSON-serialisable dictionary containing at least `agent_id`,
`role` and `type`. Storage agents should include `soc`.

**Ownership:** B1 owns `agents/base.py` and `agents/consumer.py`, B2 owns
`agents/producer.py` and `agents/storage.py`. `agents/base.py` ships as an
interface skeleton: the contract methods raise `NotImplementedError` with a
`TODO(B1)` note. `MockAgent` is kept only because `core/model.py` imports it; it
raises on construction, and real agents must be injected.

---

## 3. Order and Trade (Team B3)

```python
@dataclass(frozen=True)
class Order:
    agent_id: str
    side: Literal["buy", "sell"]
    qty_mw: float      # > 0
    price: float       # >= 0, currency per MWh
    priority: int = 0  # higher served first
    round: int = 1     # >= 1

@dataclass(frozen=True)
class Trade:
    buyer_id: str
    seller_id: str
    qty_mw: float      # > 0
    price: float       # >= 0
```

Both classes validate their fields in `__post_init__` and raise `ValueError` on
invalid values. Orders and trades are immutable.

---

## 4. Market contract (Team B3, C1 adapter)

```python
class MarketInterface:
    def clear(self, orders: Sequence[Order], round: int,
              context: MarketContext) -> ClearingResult: ...
    def settle(self, context: MarketContext, trades: Sequence[Trade],
               price: float) -> Settlement: ...
```

`MarketContext` fields (all read-only):

| Field | Type | Unit |
| --- | --- | --- |
| `t` | `int` | step |
| `demand_mw` | `Mapping[str, float]` | MW per consumer |
| `generation_mw` | `Mapping[str, float]` | MW available per producer |
| `flexibility` | `Mapping[str, float]` | ratio `[0, 1]` per consumer |
| `consumer_types` | `Mapping[str, str]` | consumer id → type |
| `producer_types` | `Mapping[str, str]` | producer id → type |
| `storage_soc` | `Mapping[str, float]` | ratio `[0, 1]` per battery |
| `voll` | `Mapping[str, float]` | currency/MWh per consumer |
| `max_price` | `Mapping[str, float]` | currency/MWh per consumer |
| `settings` | `Mapping[str, Any]` | `config["market"]` |

`ClearingResult` exposes `round`, `price`, `trades` and `cleared_mw`.
`Settlement` exposes `price`, `trades`, `unserved`, `deferred` and `payments`
(positive payment means the agent pays).

Market rules owned by B3: double auction, at most 3 rounds, `raise_factor`,
`producer_step`, `initial_markup`. `MockAuction` is kept only because
`core/model.py` imports it; it raises `NotImplementedError` and is **not** an
auction implementation.

Central modes (`central_6h`, `central_1h`) use the same interface: C1 provides
an adapter that turns its LP dispatch into trades and a settlement. This keeps
`GridModel` free of planning logic.

---

## 5. Negotiation contract (Team B3)

```python
class NegotiationProtocol:
    @property
    def rounds(self) -> int: ...

    def refine(self, round: int, orders: Sequence[Order],
               previous: ClearingResult | None,
               context: MarketContext) -> list[Order]: ...
```

`GridModel` calls `refine` for rounds `2..simulation.rounds` and then clears the
returned orders. `negotiation.rounds` must equal `simulation.rounds`.
`StubNegotiation` is kept only because `core/model.py` imports it; `refine`
raises `NotImplementedError` and is not a negotiation implementation.

---

## 6. GridModel contract (Team A1)

```python
GridModel(
    config: dict,
    seed: int,
    mode: str,                 # "central_6h" | "central_1h" | "auction" | "auction_q" | "mock"
    scenario: str = "normal",  # key or display name, e.g. "Plant Outage"
    *,
    environment: Environment | None = None,   # A2, defaults to the real model
    agents: Sequence[BaseAgent] | None = None, # B, required for official modes
    market: MarketInterface | None = None,     # B3/C1, required for official modes
    negotiation: NegotiationProtocol | None = None,  # B3, required for official modes
    logger: SimulationLogger | None = None,
)
```

Methods:

| Method | Returns | Notes |
| --- | --- | --- |
| `step()` | `StepResult` | Executes exactly one hour. |
| `inject_event(name, **kw)` | `None` | `t_start` defaults to the current step, `duration` to 1 step; accepts `demand_multiplier`, `capacity_factor`, `cloud_override`, or a `params` mapping. |
| `snapshot()` | `dict` | Full public state (clock, environment, agents, events, price, unserved/deferred totals). |
| `forecast(t, horizon)` | `dict` | Environment forecast, see section 8. |

Read-only properties: `clock`, `logger`, `results`, `events`, `mode`,
`scenario`, `agents`.

Step sequence (frozen, do not reorder):

1. `Environment.update(t)`
2. `Events.apply(t)` and `Environment.apply_modifiers(...)`
3. `Agent.observe(...)`
4. Round 1 decisions
5. Market clearing
6. Rounds 2..N negotiation (agent decisions, `refine`, clearing)
7. Settlement
8. Agent updates
9. Logging, then the clock advances

All four official modes require injected components and raise
`NotImplementedError` otherwise. `mode="mock"` remains part of the frozen
signature but is not usable in the skeleton phase because `MockAgent` raises;
reintroducing a labelled test double or removing the mode is open decision PD-15.

---

## 7. StepResult contract (frozen)

| Field | Type | Unit | Meaning |
| --- | --- | --- | --- |
| `t` | `int` | step | Absolute step index. |
| `price` | `float` | currency/MWh | Final clearing price. |
| `supply_mw` | `float` | MW | Total available generation. |
| `demand_mw` | `float` | MW | Total requested demand. |
| `unserved` | `dict[str, float]` | MW | Unserved energy per consumer. |
| `deferred` | `dict[str, float]` | MW | Deferred energy per consumer. |
| `trades` | `list[Trade]` | MWh, currency/MWh | Trades of the final round. |
| `orders` | `list[Order]` | MW, currency/MWh | All orders of all rounds. |
| `messages` | `int` | count | Number of orders exchanged in the step. |
| `soc` | `dict[str, float]` | ratio `[0, 1]` | State of charge per battery. |
| `generation` | `dict[str, float]` | MW | Available generation per producer. |

The dataclass is `frozen=True`. Renaming, removing or re-typing a field is a
breaking change.

---

## 8. Environment contract (Team A2)

```python
Environment(config, seed)
Environment.update(t) -> EnvironmentState
Environment.apply_modifiers(modifiers, active_events=()) -> EnvironmentState
Environment.forecast(t, horizon) -> dict
```

`EnvironmentState` exposes `t`, `hour`, `day`, `temperature_c`,
`cloud_cover`, `effective_cloud_cover`, `wind_index`, `solar_profile`,
`demand_mw`, `generation_mw`, `active_events`, plus the totals
`demand_total_mw` and `generation_total_mw`. `update` is idempotent for the
current step and can advance forward hour by hour; rewinding raises
`ValueError`.

`forecast(t, horizon)` is column oriented and contains **no random noise and no
future event knowledge**:

```python
{
    "origin_t": 12,
    "horizon": 6,
    "t": [...], "hour": [...], "day": [...],
    "temperature_c": [...],
    "cloud_cover": [...],
    "wind_index": [...],
    "demand_mw": {"hospital_1": [...], ...},     # MW per consumer
    "generation_mw": {"solar_1": [...], ...},    # MW per producer
    "demand_total_mw": [...],
    "generation_total_mw": [...],
    "mode": "central_6h",                        # added by GridModel.forecast
}
```

This structure is the input contract for Team C1's LP.

---

## 9. Event contract (Team A3)

```python
@dataclass(frozen=True)
class Event:
    name: str
    t_start: int
    duration: int
    params: Mapping[str, Any]

Event.is_active(t) -> bool       # t_start <= t < t_start + duration
Event.modifiers() -> EnvironmentModifiers
EventManager.schedule(event) / apply(t) / inject(...) / active_events(t)
```

Supported parameters: `demand_multiplier` (consumer type or id → factor),
`capacity_factor` (producer type or id → factor), `cloud_override` (`[0, 1]`).
Events never message agents. Scenario definitions live in
`config/scenarios.yaml` and are loaded by `build_scenario_events`. Event
activation, modifier merging and scenario calibration are `TODO(A3)`; the
catalogue currently ships the five official keys with empty event lists (PD-01).

---

## 10. Configuration contract (Team A1)

`core.config.load_config()` returns one validated dictionary with the sections
`project`, `simulation`, `market`, `voll`, `max_prices`, `producers`,
`consumers`, `storage`, `environment`, `experiments` and `scenarios`.

* `simulation.steps` must be 168, `rounds` at most 3, `horizon` positive.
* `experiments.systems` must list the four official systems, `scenarios` the
  five official scenarios, and `seeds` must be 30.
* Agent groups are validated and expanded by `resolve_agent_specs(config)`.
* Missing or invalid values raise `ConfigError` with a dotted path.

---

## 11. Change control

1. Propose the change in the relevant team channel with the reason.
2. Update this document and `docs/decision_log.md`.
3. Obtain approval from A1, B1, C1 and D1.
4. Update the affected tests in the same pull request.

Interfaces marked **frozen** in this document: `Agent`, `Order`, `Trade`,
`GridModel` public methods, `StepResult`, `MarketInterface`, `Settlement`,
`ClearingResult`, and the forecast dictionary.
