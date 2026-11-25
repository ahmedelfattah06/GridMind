# GridMind — Academic Presentation & Defence Guide

**Purpose:** Prepare for a thesis-style defence, conference talk or supervisory review of the GridMind simulation.
**Grounding:** Every answer is traceable to the code, configuration or executed tests of this repository. Numbers quoted as *executed* were produced during the audit (`151 passed`, smoke pipeline) — not invented.
**Companion documents:** `docs/GRIDMIND_COMPLETE_TECHNICAL_DOCUMENTATION.md` (reference), `docs/GRIDMIND_AUDIT_REPORT.md` (defect log).

---

## 0. How to present this project

A defensible 10-minute narrative:

1. **Question (1 min).** Decentralised negotiation vs central planning under disruption, in a small synthetic electricity city.
2. **Design (2 min).** Four systems, five scenarios, 30 paired seeds, 168 hourly steps, identical physics and fleet. Only the market mechanism and the storage policy change.
3. **Mechanism (2 min).** Auction = uniform-price double auction with at most three negotiation rounds. Central = rolling-horizon LP with 1 h or 6 h replanning.
4. **Learning (1 min).** A 60-state tabular Q-learner tunes the battery policy; it is trained offline and frozen for evaluation.
5. **Evidence (3 min).** Social cost, unserved energy, hospital outage hours, price volatility, recovery time, PAR, Gini, messages, renewable share, storage cycles; paired Wilcoxon with Bonferroni correction.
6. **Honesty (1 min).** State the model's limits and the two intentional asymmetries (central factory shedding, censored central recovery). A defence is stronger when you name the caveats before the examiner does.

**One-sentence claim to defend:** *Under the configured VOLL ordering and rolling-horizon LP, decentralised auction outcomes differ from central dispatch mainly through who bears unserved energy and how fast price/UE return to baseline after a shock.*

Do **not** claim: real-grid validity, optimality of the auction, superiority of RL, or statistical significance you did not compute.

---

## Part A — Framing and experimental design

### Q1. What exactly is the research question, and what would falsify it?

The implemented question is whether decentralised negotiation between autonomous agents is more robust than centralised planning when plants fail or demand spikes. Robustness is operationalised as lower unserved energy (UE), fewer hospital outage hours, and faster recovery of price/UE to the pre-event band. The hypothesis would be falsified if, across the paired seeds and event scenarios, the auction does **not** improve those indicators relative to `central_6h`/`central_1h`, or if any apparent improvement disappears under the paired test and Bonferroni correction. The report generator prints descriptive verdicts and explicitly says when a difference is not significant (`experiments/report.py`).

### Q2. Why four systems rather than two?

Two dimensions are being separated:

| System | Mechanism | Storage policy | Purpose |
| --- | --- | --- | --- |
| `central_6h` | LP, replan every 6 h | LP-managed | Central planning with forecast staleness |
| `central_1h` | LP, replan every hour | LP-managed | Central planning with fresh information |
| `auction` | Double auction, 3 rounds | Rule-based | Decentralised benchmark |
| `auction_q` | Double auction, 3 rounds | Learned Q-policy | Effect of learning inside the same market |

This gives a 2×2 logic: mechanism effect (auction vs central at equal information) and learning effect (auction vs auction_q at equal mechanism). `central_6h` vs `central_1h` isolates the value of replanning frequency.

### Q3. Why 30 seeds and 168 steps?

168 steps = 7 days × 24 h, enough to include a full event window, the pre-event baseline and post-event recovery. Thirty seeds per cell give a paired sample large enough for a two-sided Wilcoxon signed-rank test and a 95 % bootstrap interval, while keeping the full grid at `4 × 5 × 30 = 600` runs (`config/default.yaml:166-179`). Seeds are identical across systems, so every comparison is paired by seed.

### Q4. What is held constant across systems?

The fleet (15 agents, up to 20), demand and weather draws for a given seed, event schedule, VOLL values, price ceilings, battery physics and the 168-hour horizon. `core.factory.build_model()` assembles the same environment and agents; only the market adapter and the storage policy differ. This is what licenses a causal reading of the system comparison — within the model.

### Q5. Is this a digital twin?

No. It is a stylised model: one copper-plate market, no network, no unit commitment, no ramping, no reserves, no frequency dynamics, no measured weather or market data. It is appropriate for mechanism comparison and teaching, not for operational forecasting. Say this explicitly; it is a strength of scope control, not a hidden weakness.

---

## Part B — Autonomy and agent behaviour

### Q6. In what sense are the agents autonomous?

Each agent owns its own decision rule and only sees a local observation: the environment view, the last clearing price, market settings, and its own snapshot. `GridModel._build_observations()` deliberately removes `active_events`, so agents never see event names or the future. The model orchestrates but contains no bidding logic. Autonomy here means *decentralised decision authority with local information*, not independent learning in the multi-agent RL sense (only the battery learns).

### Q7. How does a consumer construct its bid?

A consumer takes metered demand for the hour, applies its own forecast error `η ~ N(0, 0.03²)`, clips hospital noise to be non-negative, then adds any deferred energy from the previous hour:

$$
\hat D_i(t) = \max(0, D_i(t)(1+\eta_i)) + \text{deferred}_i(t-1).
$$

It splits `D̂` into fixed `(1-f)` and flexible `f` parts. Fixed demand is bid at the type ceiling (hospital 300, residential 120, factory 80); flexible demand at the common flex ceiling of 50. In round `r` the limit is `min(ceiling, ceiling · 1.2^{r-1})`. Priorities are hospital 1, residential 2, factory 3, flexible 4 (`agents/consumer.py`).

### Q8. Why do hospitals never under-bid?

`noise = max(0, noise)` for hospitals. Under-bidding critical load would create avoidable outages for the agent with VOLL 1000. Positive forecast error is still allowed, giving a safety margin. This is a deliberate behavioural assumption, documented in the code, not a numerical trick.

### Q9. How do producers adapt?

Each producer offers its full available generation at `mc · (1 + m)`, with initial markup `m = 0.2`. After settlement, if at least 95 % of the offer sold, `m` rises by 0.05 (capped at 1.0); otherwise it falls by 0.05 (floored at 0). Later rounds lower the ask by 5 % per round but never below marginal cost. So the market has a simple supply-side learning channel even without RL (`agents/producer.py`).

### Q10. What does the battery do without learning?

The rule policy compares the last price with its own 24-hour average: charge if `last < 0.85 · avg`, discharge if `last > 1.15 · avg`, otherwise wait. Charge/discharge are then clipped by power rate, efficiency and available headroom/energy. The same `StoragePolicy` interface is used by the rule policy, the Q-policy and the training policy, which is why the four systems are comparable.

---

## Part C — Market clearing and settlement

### Q11. Describe the auction algorithm precisely.

Bids are sorted by `(-price, priority, agent_id)`; asks by `(price, priority, agent_id)`. The algorithm walks both lists while the best remaining bid price is at least the best remaining ask price, matching `min(remaining bid, remaining ask)` at each step. If at least one match occurs, the round price is the midpoint of the **last matched** bid and ask:

$$
p = \frac{p^{\text{last bid}} + p^{\text{last ask}}}{2}.
$$

All trades in the round use this uniform price. If nothing matches, the previous clearing price is kept (`market/auction.py::DoubleAuction.clear`). Note that lower priority numbers mean more important load; this is documented in `market/orders.py` and `docs/contracts.md`.

### Q12. Is this a Vickrey auction, a pay-as-bid auction, or something else?

Neither. It is a **uniform-price midpoint double auction**: one price per round, computed from the marginal matched pair, applied to every trade. It is not incentive-compatible in the Vickrey sense, and it is not pay-as-bid. The midpoint rule is a modelling choice that avoids a full demand/supply curve intersection and keeps the implementation auditable.

### Q13. Why three negotiation rounds, and what changes between them?

Round 1 establishes the initial orders. Rounds 2 and 3 let agents submit counter-offers: consumers escalate up to their ceiling (`×1.2` per round), producers shade down toward marginal cost (`×0.95` per round). `RaiseFactorNegotiation.refine()` validates round membership and ceilings and orders orders deterministically. The **last** round's trades are settled; earlier rounds only shape the final outcome and contribute to the `messages` metric.

### Q14. How is unserved energy defined at settlement?

For each consumer, against that hour's metered demand:

$$
\text{shortfall}_i = \max(0, D_i - \text{bought}_i),
$$

$$
\text{deferred}_i = \min(\text{shortfall}_i,\; f_i D_i),
\qquad
\text{unserved}_i = \text{shortfall}_i - \text{deferred}_i.
$$

So flexible demand is first deferred (re-bid once next hour), and only the remainder counts as unserved. Payments are zero-sum: buyer pays `q·p`, seller receives `q·p`.

### Q15. Is deferred energy double-counted when it fails to clear again?

No — and this needs a careful answer. Deferred energy is re-bid once in the next hour, but `settle()` computes the shortfall against the **environment's metered demand**, which does not include the re-bid. Therefore a failed rebound is not re-counted in that hour's `unserved`; it simply disappears from the accounting after one attempt. This is a documented modelling limitation of the settlement definition, not a hidden double count. It slightly understates persistence of shortage and is listed in the technical documentation and audit report.

### Q16. Why does the auction sometimes clear at a price with no relation to marginal cost?

Because the uniform price is a midpoint of the last matched pair, not a marginal-cost or dual price. If the marginal matched ask is cheap (e.g. solar at 6) and the marginal bid is high (e.g. a hospital at 300), the midpoint can be well above the marginal cost of the marginal unit. This is a property of the mechanism, not a bug. It also means auction and central prices are not directly comparable as "the" price of electricity; comparisons should rely on cost, UE and recovery metrics, with price treated as a mechanism-specific signal.

---

## Part D — Central optimisation

### Q17. Write the central LP.

For a horizon of `H` hours, the planner minimises

$$
\min \sum_{\tau=1}^{H}\left[
\sum_k mc_k g_{k,\tau}
+ \sum_i \mathrm{VOLL}_i u_{i,\tau}
+ 10^{-6}\sum_s (ch_{s,\tau}+dis_{s,\tau})
\right]
$$

subject to, for every hour,

$$
\sum_k g_{k,\tau} + \sum_s dis_{s,\tau} - \sum_s ch_{s,\tau} + \sum_i u_{i,\tau}
= \sum_i D_{i,\tau},
$$

$$
0 \le g_{k,\tau} \le \text{availability}_{k,\tau},\quad
0 \le u_{i,\tau} \le D_{i,\tau},
$$

and battery dynamics

$$
soc_{s,\tau} - soc_{s,\tau-1} - \eta_s ch_{s,\tau} + \frac{dis_{s,\tau}}{\eta_s} = 0,
\qquad soc_{s,-1} = soc_s^{init} C_s,
$$

with charge/discharge bounded by the power rate and `soc ∈ [0, C_s]`. The tiny throughput term only breaks ties (`ai/central_lp.py`).

### Q18. Why does central dispatch deliberately leave factory load unserved?

Because VOLL ordering is hospital 1000 > residential 100 > factory 40, while thermal marginal cost is 45. When thermal is the marginal source, serving a factory MWh costs 45 but avoids only 40 of penalty, so the LP prefers to shed it. This is **economically rational under the configured VOLLs**, not an accounting bug. It is an intentional model behaviour and it means central and auction systems are not compared on identical served energy — a caveat that must be stated when interpreting social cost.

### Q19. What is the difference between `central_1h` and `central_6h`?

Both solve the same LP. `central_1h` replans every hour; `central_6h` replans every 6 hours and executes the cached plan in between, clipping it against realised availability. The comparison isolates the value of forecast freshness and replanning frequency. In the code, `CentralMarketAdapter._needs_replan()` checks the interval and the cached horizon.

### Q20. How is a cached plan executed when reality differs from the forecast?

The adapter reconciles at execution time: generation is `min(planned, actual available)`; discharge is clipped by `min(rate, soc·η)`; planned charge is clipped by `min(rate, headroom/η)`. Then, with `supply = Σgen + Σdis` and `demand = Σactual demand`, if `demand ≥ supply` charging is forced to zero; otherwise charging consumes only the surplus and `available = supply - total charge`. Consumers are served in **descending VOLL** order, then batteries charge from what is left. This guarantees that a stale plan cannot starve load to charge a battery — the core post-audit fix.

### Q21. How is the central price computed, and is it the LP dual?

The uniform central price is the **maximum marginal cost among sellers that actually matched**, not among all dispatched or available units. It is a marginal-cost proxy; it is neither the LP dual variable nor a market-clearing intersection. It is internally consistent, and it prevents curtailed or unsold generation from setting the price, but it should not be interpreted as an equilibrium price.

---

## Part E — Reinforcement learning

### Q22. Why tabular Q-learning rather than deep RL?

The actionable decision is small and discrete: wait, charge, or discharge, given a coarse state. A 60-state table is interpretable, trainable on a laptop, and auditable — every number in `qtable.npy` can be inspected. Deep RL would add variance, compute and a second layer of unexplainable behaviour without a clear benefit for this decision problem. The project explicitly avoids a deep-RL dependency.

### Q23. Define the state and action spaces.

State = `(SoC bin, price bin, period bin)`:

* SoC: 5 equal bins over battery capacity, `floor(soc_mwh / (C/5))`, clipped to `0..4`;
* price: cheap if `last/avg < 0.85`, expensive if `> 1.15`, otherwise normal;
* period: `hour // 6`, i.e. four six-hour blocks.

Flat index:

$$
s = (\,soc\_bin \cdot 3 + price\_bin\,)\cdot 4 + period\_bin \in [0,59].
$$

Actions: `0 = wait`, `1 = charge`, `2 = discharge`. Hence the table is `(60, 3)`.

### Q24. Write the reward and the update rule.

Per hour and per battery:

$$
r = p\,\text{sold} - p\,\text{bought} - 0.5(\text{bought}+\text{sold})
- 0.5\cdot\text{system\_unserved}\cdot\mathbb{1}[soc<1].
$$

The throughput term discourages pointless cycling; the unserved term penalises hoarding while the system is short, but only when the battery is not full, so a full battery is not punished for a shortage it cannot alleviate.

Update:

$$
Q(s,a) \leftarrow Q(s,a) + \alpha\left[r + \gamma \max_{a'}Q(s',a') - Q(s,a)\right],
$$

with `α = 0.1`, `γ = 0.95`, terminal bootstrap zero. Exploration is ε-greedy with a linear schedule `1.0 → 0.05` over 1500 episodes; training runs 2000 episodes of 168 steps, sampling one official scenario per episode (`ai/qlearning.py`, `ai/train.py`).

### Q25. How is the learned policy evaluated without contaminating the experiment?

Training is a separate offline process that writes `qtable.npy` and `results/learning_curve.csv`. Evaluation (`auction_q`) loads the frozen table and acts **greedily** (`epsilon = 0`). No learning updates occur during evaluation. This separation is essential: otherwise the reported performance would depend on the order of evaluation runs and would not be reproducible.

### Q26. Why query the policy once per hour rather than once per negotiation round?

Because the environment transition is hourly. If the policy were queried in every round, one hour would close two or three transitions from the same state and attribute the whole step reward to the last action, biasing the Q-table. The audit fixed this by caching the action per hour (`StorageAgent._step_action`). This is both a learning-correctness and a reproducibility requirement.

### Q27. Is `auction_q` better than `auction`?

Only the experiment can answer that, and only under the frozen Q-table. The design compares them per scenario with paired seeds. Do not assert superiority from the training curve: a higher training reward is not the same as lower social cost or UE, because the reward is battery-local and includes a throughput penalty. Report the paired metrics and the test result, not the training curve alone.

---

## Part F — Energy balance and storage physics

### Q28. How is energy conserved in the model?

The environment sets available generation and metered demand. The market can only allocate traded energy; anything unmatched becomes unserved or deferred. The tests include `test_energy_is_conserved_in_every_step` and a real-market conservation test (`tests/test_model.py`). The LP enforces an explicit hourly balance equality. At the system level, `supply_mw` is **available** generation, not dispatched generation — do not confuse the two when reading the log.

### Q29. Write the battery transition and its limits.

$$
soc_{t+1} = \operatorname{clip}\!\left(soc_t + \frac{\eta\,\text{bought}_t - \text{sold}_t/\eta}{C},\,0,\,1\right),
$$

$$
\text{max charge} = \min\!\left(P_{\max},\, \frac{(1-soc)C}{\eta}\right),
\qquad
\text{max discharge} = \min\!\left(P_{\max},\, soc\,C\,\eta\right).
$$

Default: `C = 20 MWh`, `P_max = 5 MW`, `η = 0.95`, initial SoC 0.5. There is no degradation, temperature dependence, or reserve band.

### Q30. Where does the round-trip loss appear in the metrics?

In `social_cost` only indirectly: generation cost is charged on sold producer energy, and the battery pays the clearing price for charging. The loss means the battery must buy more MWh than it later sells, so it raises generation cost relative to a lossless battery. There is no separate "loss" line item; the effect is embedded in the flows.

---

## Part G — Scenarios and events

### Q31. How are events represented and applied?

An event is a named interval `[start, start+duration)` with parameters: `demand_multiplier` (by consumer type or id), `capacity_factor` (by producer type or id), and `cloud_override`. `EventManager.apply(t)` returns merged `EnvironmentModifiers`; the environment applies them to realised demand, generation and cloud. Events are never messaged to agents by name.

### Q32. List the five official scenarios and their timing.

| Scenario | Window | Effect |
| --- | --- | --- |
| `normal` | — | No disruption |
| `plant_outage` | steps 86–97 | Thermal capacity factor 0.3 |
| `demand_spike` | steps 86–91 | Residential demand ×1.4 |
| `weather_shift` | steps 72–95 | Cloud override 0.2, wind capacity factor 0.5 |
| `combined` | 86–97 and 86–91 | Thermal 0.3 plus residential ×1.4 |

Day 3 begins at step 72, hour 14 at step 86, matching the project guide.

### Q33. Why does `weather_shift` reduce solar output if it sets cloud to 0.2?

Because the implemented solar equation is `capacity · solar_profile · cloud_cover`, so a lower cloud value multiplies output down. The variable is best read as a **solar availability factor**, not a meteorological cloud fraction. This is a documented calibration nuance; changing the equation would change the scenario's calibrated meaning, so the audit documented it instead of "fixing" it.

### Q34. Are forecasts event-aware?

No. Forecasts are noiseless and use expected weather/demand; they contain no future-event knowledge. This is deliberate: it prevents the central planner from being unrealistically clairvoyant and makes the `central_6h` vs `central_1h` comparison meaningful.

---

## Part H — Metrics and statistics

### Q35. Define social cost and cost per MWh.

$$
\text{generation cost} = \sum_k mc_k \sum_t \text{sold}_{k,t},
\qquad
\text{VOLL penalty} = \sum_i \mathrm{VOLL}_i \sum_t ue_{i,t},
$$

$$
\text{social cost} = \text{generation cost} + \text{VOLL penalty},
\qquad
\text{cost per MWh} = \frac{\text{social cost}}{\sum_t \text{served}_t},
$$

with `served_t = max(0, demand_t - unserved_t - deferred_t)`. Deferred energy is excluded from served energy in the denominator because it was not consumed in that hour.

### Q36. Define recovery time and explain censoring.

Baseline is the mean price over the 24 hours before the earliest event start. Recovery is the first run of **three consecutive hours** with `|price - baseline| ≤ 10 % · |baseline|` and total UE ≤ 0.001 MW. The returned value is `offset - start - 2`, so the first stable hour counts as hour 0. If no such run occurs, the metric is `steps - start`, i.e. the remaining window — a **censored** observation, not a measured recovery.

### Q37. Why is central recovery often censored?

Because the LP may leave a standing factory shortfall after the event (VOLL 40 < thermal cost 45), so total UE never returns to ≤ 0.001. The recovery criterion therefore never fires and the metric saturates at the window length. This is a consequence of the intentional VOLL/fuel-cost ordering, and it must be reported as censoring rather than as "central never recovers".

### Q38. What do PAR, Gini and self-sufficiency measure?

* **PAR** = `max served / mean served`: peak-to-average ratio of served demand; higher means a peakier load profile.
* **Gini** = `Σ_i Σ_j |p_i - p_j| / (2 n² mean(p))` over consumer unit prices `p_i = paid_i / bought_i`: dispersion of effective prices paid by consumers, a fairness proxy, not income inequality.
* **Self-sufficiency** = `1 - ue_total / demand_total`: share of metered demand served.

Each has a precise denominator in `experiments/metrics.py`; quote the formula when asked, because "Gini" alone is ambiguous.

### Q39. How are systems compared statistically?

Mean and sample SD (`ddof=1`) over 30 seeds; 95 % bootstrap CI with 1000 resamples and fixed seed `20_240_517`; paired two-sided Wilcoxon signed-rank test on non-zero differences; Bonferroni correction `p_adj = min(1, p·m)` over all pairwise rows; effect size `(mean_treatment - mean_baseline)/|mean_baseline|`. Pairing by seed is essential because the same weather/demand draws are used across systems.

### Q40. What does Bonferroni control, and what is its cost?

It controls the family-wise error rate: the probability of at least one false positive across the `m` comparisons. The cost is low power, especially with many metrics. That is why the report should distinguish "significant after correction" from "consistent but not significant", and why effect sizes are reported alongside p-values.

### Q41. Why not use a t-test?

The per-run metrics are not guaranteed normal (UE is bounded at zero, recovery time is censored), and the sample is paired by seed. The Wilcoxon signed-rank test is distribution-free and uses the pairing; it is a more defensible default. The bootstrap interval communicates uncertainty without a normality assumption.

---

## Part I — Reproducibility and engineering

### Q42. How is reproducibility guaranteed?

Every stochastic component owns a derived stream: `default_rng(SeedSequence([seed, stream]))`. Agent streams are derived from a hash of the agent id, so adding or reordering agents does not shift another agent's draws. Forecasts consume no randomness. The Q-table is an external artefact, so `auction_q` reproducibility requires the exact `qtable.npy`. Tests verify identical 168-step logs for the same seed and different logs across seeds (`tests/test_reproducibility.py`).

### Q43. Why does the audit care about which random stream a draw comes from?

Because sharing a stream creates spurious correlation. Before the audit, a consumer's forecast error used the same stream base as the realised-demand noise for that agent, so the "forecast" partly knew the shock. The fix gives forecasts their own stream (`STREAM_AGENT_FORECAST_BASE`), which is both more realistic and required for a clean information story: agents react to private forecasts, not to the environment's draw.

### Q44. What happens if the simulation is interrupted mid-grid?

Per-run CSVs and the aggregate files in the chosen output directory may be incomplete. The audit added report-path safety so a filtered or interrupted run cannot overwrite the official `docs/report/REPORT.md`; the runner records its selected systems, scenarios and seeds in `run_metadata.json`. A partial run is still an operational caveat for `raw.csv`/`steps.csv`, which are rewritten in the output directory — always verify `run_metadata.json` before quoting aggregates.

### Q45. How do you know the tests are meaningful?

The suite covers config validation, weather/demand/supply equations, event windows, the frozen step order, energy conservation with a real market, auction matching and settlement, negotiation validation, central LP balance and adapter execution, Q-updates, logger schema, runner filtering, report generation and reproducibility. The audit added 11 regression tests for the specific defects it fixed, each of which fails on the pre-fix code. Tests are necessary but not sufficient: they do not validate the economic realism of the assumptions.

---

## Part J — Limitations and defence traps

### Q46. What are the three most important limitations?

1. **No network or unit commitment.** A copper-plate market with instantly dispatchable thermal units overstates flexibility and cannot represent congestion, reserves or start-up constraints.
2. **Intentional asymmetry between systems.** Central dispatch sheds factory load because VOLL 40 < thermal cost 45, and central recovery is often censored. Central and auction are therefore not compared on identical served energy.
3. **Synthetic data and a single model family.** Weather and demand are equations, not measured traces; results are internally valid, not externally valid.

### Q47. Is the comparison fair if central sheds factory load on purpose?

It is *internally consistent* but not *like-for-like on served energy*. The correct framing is: under the configured VOLLs, a social-cost-minimising central planner chooses to shed low-VOLL load, whereas the auction's priority and price rules produce a different allocation. The comparison is about mechanisms under a common preference specification, not about who can serve the most MWh. Report UE by consumer type and hospital outage hours alongside social cost, and never present social cost alone as a welfare ranking.

### Q48. Why not simply set VOLL(factory) above 45 to remove the asymmetry?

That would change the economic specification and invalidate the official scenario calibration. It is a legitimate sensitivity experiment, but it is a *new* experiment, not a bug fix. The audit's rule was: do not silently change definitions. If you run it, label it as a sensitivity analysis and regenerate the artefacts.

### Q49. Can the Q-learning results be trusted?

They are reproducible given the frozen table, and the training/evaluation separation is sound. But the state space is coarse, the reward is battery-local with an ad-hoc unserved term, there is no hyperparameter sweep, and one shared learner is used across batteries. Treat `auction_q` as a bounded policy-improvement experiment, not as evidence that RL is generally superior.

### Q50. What would you do with more time?

Priority order: (1) regenerate the 600-run grid and Q-table after the audit fixes so all artefacts match the code; (2) add a VOLL sensitivity study to quantify the factory-shedding effect; (3) add a network/ramping extension or at least a flexibility sensitivity; (4) improve the deferred-energy accounting so failed rebounds are traced explicitly; (5) add a proper multi-agent learning baseline.

---

## Appendix A — Claim-to-evidence map

| Claim | Evidence in repository |
| --- | --- |
| 168 hourly steps, 600 runs | `config/default.yaml`, `experiments/runner.py`, `tests/test_experiments.py` |
| Four systems, five scenarios | `core/config.py` constants, `config/scenarios.yaml` |
| Frozen step order | `core/model.py::_execute_step`, `tests/test_model.py::test_step_follows_the_frozen_execution_order` |
| Energy conservation | `tests/test_model.py::test_energy_is_conserved_in_every_step`, `test_energy_conservation_with_real_market` |
| Auction rule | `market/auction.py::DoubleAuction.clear`, `tests/test_market.py` |
| Settlement rule | `market/auction.py::DoubleAuction.settle`, `tests/test_market.py` |
| Central LP and execution | `ai/central_lp.py`, `tests/test_market.py::test_central_*` |
| Q-learning state/reward/update | `ai/qlearning.py`, `ai/train.py`, `tests/test_ai.py` |
| Metrics formulas | `experiments/metrics.py`, `tests/test_experiments.py::test_metrics_match_the_hand_computed_values` |
| Statistics | `experiments/stats.py`, `tests/test_experiments.py::test_pairwise_comparison_applies_bonferroni_correction` |
| Reproducibility | `tests/test_reproducibility.py` |
| Repaired defects | `docs/GRIDMIND_AUDIT_REPORT.md`, 11 regression tests |

## Appendix B — Numbers you may quote

Only these executed numbers are safe to quote without re-running:

* Test suite after the audit: **151 passed**, 0 skipped, ~4 s.
* Official grid size: **600 runs**, **100,800 step rows** (design arithmetic, confirmed by the existing artefact shape).
* Q-table shape: **(60, 3)**; the existing table has **180** non-zero entries.
* Smoke pipeline executed during the audit: 2 runs (`auction`, `central_1h`; `normal`; seed 0), 168 steps, all artefacts produced, report kept inside the temporary output directory.

Anything else — social-cost rankings, significance, recovery times — must come from a fresh post-fix run. The existing `results/` and `qtable.npy` predate the audit fixes.

## Appendix C — Likely hostile questions and one-line answers

| Question | Answer |
| --- | --- |
| "Isn't your auction just a midpoint heuristic?" | Yes; it is a uniform-price midpoint double auction, documented as such, not claimed to be incentive-compatible. |
| "Why does central shed factories?" | VOLL 40 < thermal cost 45, so shedding is optimal under the configured preferences; it is intentional and reported. |
| "Aren't your central prices wrong?" | They are a maximum-matched-marginal-cost proxy, not LP duals; the limitation is documented. |
| "Did you tune the Q-learning to win?" | No; hyperparameters are fixed by the specification and training is separate from evaluation. |
| "Is 30 seeds enough?" | Enough for paired non-parametric tests and bootstrap CIs; power is limited and Bonferroni is conservative, which we state. |
| "Why not use real data?" | Scope: the contribution is mechanism comparison in a controlled synthetic environment; external validity is explicitly out of scope. |
| "Did you change definitions to make results look better?" | No; the audit documents intentional modelling choices instead of altering them, and lists every code change with a failing-before regression test. |
