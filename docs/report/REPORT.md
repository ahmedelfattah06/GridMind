# GridMind - Experimental Report

This report is generated automatically from the artefacts of a completed `python -m experiments.runner` execution. Every number below is simulation output; no expected value is inserted by hand.

## 1. Research question and design

> Is decentralised negotiation between autonomous agents more robust than centralised planning when power plants fail or demand suddenly increases?

- Duration: **168 hourly steps** (7 days) per run.
- Systems: **central_6h, central_1h, auction, auction_q**.
- Scenarios: **combined, demand_spike, normal, plant_outage, weather_shift**.
- Seeds per system/scenario: **30**.
- Completed runs: **600**.
- Paired design: all systems in one scenario use the same seed, so weather and demand noise are identical across systems.

## 2. Main results

### Social cost (mean ± standard deviation over seeds)

| Scenario | central_6h | central_1h | auction | auction_q |
| --- | --- | --- | --- | --- |
| Combined | 331,450 ± 5,555 | 317,259 ± 5,600 | 324,651 ± 5,018 | 324,301 ± 5,125 |
| Demand Spike | 323,704 ± 4,991 | 308,206 ± 4,837 | 320,469 ± 4,253 | 319,487 ± 4,203 |
| Normal | 314,988 ± 4,808 | 302,450 ± 4,626 | 315,657 ± 4,162 | 315,213 ± 4,113 |
| Plant Outage | 322,438 ± 5,407 | 309,304 ± 5,209 | 317,652 ± 4,604 | 317,164 ± 4,742 |
| Weather Shift | 339,215 ± 4,242 | 314,812 ± 4,277 | 323,510 ± 3,731 | 322,694 ± 3,686 |

Lower social cost is better. Social cost is generation fuel cost plus the configured value-of-lost-load penalty of unserved energy.

### Reliability and market indicators

| Scenario | System | Hospital UE (MWh) | Hospital outage hours | Recovery time (h) | Messages | Renewable share |
| --- | --- | --- | --- | --- | --- | --- |
| Combined | central_6h | 0.000 | 0.000 | 82.000 | 3,274.867 | 0.543 |
| Combined | central_1h | 0.000 | 0.000 | 82.000 | 3,316.600 | 0.539 |
| Combined | auction | 0.000 | 0.000 | 28.133 | 9,897.900 | 0.382 |
| Combined | auction_q | 0.000 | 0.000 | 21.000 | 9,837.000 | 0.383 |
| Demand Spike | central_6h | 0.000 | 0.000 | 82.000 | 3,274.867 | 0.532 |
| Demand Spike | central_1h | 0.000 | 0.000 | 82.000 | 3,280.000 | 0.532 |
| Demand Spike | auction | 0.000 | 0.000 | 10.367 | 9,867.900 | 0.372 |
| Demand Spike | auction_q | 0.000 | 0.000 | 10.367 | 9,823.400 | 0.373 |
| Normal | central_6h | 0.000 | 0.000 | 0.000 | 3,274.867 | 0.533 |
| Normal | central_1h | 0.000 | 0.000 | 0.000 | 3,280.133 | 0.539 |
| Normal | auction | 0.000 | 0.000 | 0.000 | 9,824.000 | 0.374 |
| Normal | auction_q | 0.000 | 0.000 | 0.000 | 9,819.000 | 0.375 |
| Plant Outage | central_6h | 0.000 | 0.000 | 82.000 | 3,274.867 | 0.543 |
| Plant Outage | central_1h | 0.000 | 0.000 | 82.000 | 3,313.733 | 0.543 |
| Plant Outage | auction | 0.000 | 0.000 | 26.067 | 9,887.900 | 0.383 |
| Plant Outage | auction_q | 0.000 | 0.000 | 21.000 | 9,837.000 | 0.384 |
| Weather Shift | central_6h | 0.000 | 0.000 | 96.000 | 3,274.333 | 0.509 |
| Weather Shift | central_1h | 0.000 | 0.000 | 96.000 | 3,278.533 | 0.495 |
| Weather Shift | auction | 0.000 | 0.000 | 3.200 | 9,877.500 | 0.349 |
| Weather Shift | auction_q | 0.000 | 0.000 | 3.200 | 9,853.600 | 0.350 |

### Reading the results

- Hospital load is fully served in every run: hospital UE and hospital outage time are zero across all 20 system/scenario cells.
- In `normal`, the central systems still leave 3,249-3,253 MWh of factory demand unserved. The configured factory VOLL (40) is below the thermal marginal cost (45), so the LP prefers to shed that load. This standing shortfall dominates central UE and lowers central generation cost; it is an economic dispatch outcome, not a solver failure.
- The auction keeps total UE between 113 and 324 MWh across the five scenarios, and in event scenarios it returns to its pre-event price/UE band within 3.2-28.1 h.
- Central recovery time reaches the end of the window in 8 of 8 event-system cells because the standing factory shortfall never clears. Those values are censored, not measured recovery times.
- Q-learning lowers modelled social cost in 5/5 scenarios (by 0.11%-0.31%) but raises total UE in 5/5 scenarios (by +6.96% to +15.76%). The extra unserved energy is factory load, so this is a shift toward the lowest-VOLL consumer rather than a reliability improvement.

## 3. Hypotheses

### H1 - Central planning is cheaper in normal conditions

Observed normal-scenario social cost: Central-6h = 314,987.7, Auction = 315,657.2. The central system is cheaper by 0.21%. **H1 is descriptively supported by these runs.**

The 0.21% gap is not significant after Bonferroni correction (adjusted p = 1), so H1 should be read as a descriptive difference rather than a confirmed cost advantage.

Central-1h is cheaper still at 302,449.8 (-4.18% versus the auction), so the margin depends strongly on replanning frequency.

The comparison is not like-for-like on served energy: the central systems shed standing factory load (see *Reading the results*), which lowers their generation cost. H1 holds descriptively in the modelled objective, but it should not be read as proof that central dispatch is cheaper per MWh actually served.

### H2 - Decentralised auction recovers better from disruptions

- Plant Outage: recovery Auction 26.07 h vs Central-6h 82.00 h; UE Auction 270.43 MWh vs Central-6h 3,516.66 MWh.
- Combined: recovery Auction 28.13 h vs Central-6h 82.00 h; UE Auction 324.12 MWh vs Central-6h 3,607.04 MWh.
- Replanning delay check in plant outage: Central-6h 82.00 h vs Central-1h 82.00 h.
Across the two disruption scenarios, **4/4** recovery and unserved-energy comparisons favour the auction. H2 is **weakly supported** by these observations.

The vote is confounded by the standing factory shortfall: Central-6h already leaves 3,249 MWh of factory load unserved in `normal`, and its recovery time is censored at the end of every event window. The auction genuinely restores its pre-event band, but the central-versus-auction UE and recovery gaps are not a clean measure of outage response alone.

### H3 - Q-learning storage improves on the fixed rule

Normal-scenario social cost: Auction+Q = 315,213.1, Auction = 315,657.2. PAR: Auction+Q = 1.346, Auction = 1.344. Across all scenarios the mean social cost is 319,771.8 for Auction+Q and 320,387.7 for Auction; mean total UE is 216.9 MWh for Auction+Q and 197.7 MWh for Auction.

**H3 is partially supported on social cost only** by the executed runs. The cost reduction is real in the modelled objective, but it comes with more unserved energy, concentrated in factory load. The PAR criterion also does not improve.

## 4. Statistical comparison

- Pairwise Wilcoxon signed-rank tests: **360** comparisons, Bonferroni corrected over all tests (`bonferroni_tests` column).
- Comparisons significant at adjusted p < 0.05: **244**.
- Effect size is reported as the relative difference of the means (treatment minus baseline, divided by the absolute baseline mean).
- Only the hypothesis-relevant comparisons are shown below; the complete table is in `../../results/stats_pairwise.csv`.

| scenario | baseline | treatment | metric | mean_baseline | mean_treatment | relative_effect | p_value | p_adjusted | significant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| combined | auction | auction_q | social_cost | 3.247e+05 | 3.243e+05 | -0.001078 | 0.009932 | 1 | False |
| combined | auction | auction_q | ue_total | 324.1 | 346.7 | 0.06956 | 1.863e-09 | 6.706e-07 | True |
| combined | auction | auction_q | recovery_time | 28.13 | 21 | -0.2536 | 0.0007457 | 0.2684 | False |
| demand_spike | auction | auction_q | social_cost | 3.205e+05 | 3.195e+05 | -0.003062 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | auction_q | ue_total | 121.7 | 140.9 | 0.1576 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | auction_q | recovery_time | 10.37 | 10.37 | 0 | 1 | 1 | False |
| normal | auction | auction_q | social_cost | 3.157e+05 | 3.152e+05 | -0.001407 | 1.863e-09 | 6.706e-07 | True |
| normal | auction | auction_q | ue_total | 113 | 122.5 | 0.08421 | 1.863e-09 | 6.706e-07 | True |
| normal | auction | auction_q | recovery_time | 0 | 0 | 0 | 1 | 1 | False |
| plant_outage | auction | auction_q | social_cost | 3.177e+05 | 3.172e+05 | -0.001537 | 0.0002091 | 0.07529 | False |
| plant_outage | auction | auction_q | ue_total | 270.4 | 293 | 0.08333 | 1.863e-09 | 6.706e-07 | True |
| plant_outage | auction | auction_q | recovery_time | 26.07 | 21 | -0.1944 | 0.001953 | 0.7031 | False |
| weather_shift | auction | auction_q | social_cost | 3.235e+05 | 3.227e+05 | -0.002522 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | auction_q | ue_total | 159.3 | 181.4 | 0.1386 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | auction_q | recovery_time | 3.2 | 3.2 | 0 | 1 | 1 | False |
| combined | auction | central_1h | social_cost | 3.247e+05 | 3.173e+05 | -0.02277 | 1.863e-09 | 6.706e-07 | True |
| combined | auction | central_1h | ue_total | 324.1 | 3344 | 9.318 | 1.863e-09 | 6.706e-07 | True |
| combined | auction | central_1h | recovery_time | 28.13 | 82 | 1.915 | 1.359e-06 | 0.0004892 | True |
| demand_spike | auction | central_1h | social_cost | 3.205e+05 | 3.082e+05 | -0.03827 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | central_1h | ue_total | 121.7 | 3255 | 25.74 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | central_1h | recovery_time | 10.37 | 82 | 6.91 | 7.87e-07 | 0.0002833 | True |
| normal | auction | central_1h | social_cost | 3.157e+05 | 3.024e+05 | -0.04184 | 1.863e-09 | 6.706e-07 | True |
| normal | auction | central_1h | ue_total | 113 | 3253 | 27.79 | 1.863e-09 | 6.706e-07 | True |
| normal | auction | central_1h | recovery_time | 0 | 0 | 0 | 1 | 1 | False |
| plant_outage | auction | central_1h | social_cost | 3.177e+05 | 3.093e+05 | -0.02628 | 1.863e-09 | 6.706e-07 | True |
| plant_outage | auction | central_1h | ue_total | 270.4 | 3303 | 11.21 | 1.863e-09 | 6.706e-07 | True |
| plant_outage | auction | central_1h | recovery_time | 26.07 | 82 | 2.146 | 1.231e-06 | 0.0004431 | True |
| weather_shift | auction | central_1h | social_cost | 3.235e+05 | 3.148e+05 | -0.02689 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | central_1h | ue_total | 159.3 | 3254 | 19.42 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | central_1h | recovery_time | 3.2 | 96 | 29 | 7.238e-08 | 2.606e-05 | True |
| combined | auction | central_6h | social_cost | 3.247e+05 | 3.314e+05 | 0.02094 | 1.863e-09 | 6.706e-07 | True |
| combined | auction | central_6h | ue_total | 324.1 | 3607 | 10.13 | 1.863e-09 | 6.706e-07 | True |
| combined | auction | central_6h | recovery_time | 28.13 | 82 | 1.915 | 1.359e-06 | 0.0004892 | True |
| demand_spike | auction | central_6h | social_cost | 3.205e+05 | 3.237e+05 | 0.01009 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | central_6h | ue_total | 121.7 | 3468 | 27.49 | 1.863e-09 | 6.706e-07 | True |
| demand_spike | auction | central_6h | recovery_time | 10.37 | 82 | 6.91 | 7.87e-07 | 0.0002833 | True |
| normal | auction | central_6h | social_cost | 3.157e+05 | 3.15e+05 | -0.002121 | 0.008705 | 1 | False |
| normal | auction | central_6h | ue_total | 113 | 3397 | 29.07 | 1.863e-09 | 6.706e-07 | True |
| normal | auction | central_6h | recovery_time | 0 | 0 | 0 | 1 | 1 | False |
| plant_outage | auction | central_6h | social_cost | 3.177e+05 | 3.224e+05 | 0.01507 | 1.863e-09 | 6.706e-07 | True |
| plant_outage | auction | central_6h | ue_total | 270.4 | 3517 | 12 | 1.863e-09 | 6.706e-07 | True |
| plant_outage | auction | central_6h | recovery_time | 26.07 | 82 | 2.146 | 1.231e-06 | 0.0004431 | True |
| weather_shift | auction | central_6h | social_cost | 3.235e+05 | 3.392e+05 | 0.04855 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | central_6h | ue_total | 159.3 | 3637 | 21.83 | 1.863e-09 | 6.706e-07 | True |
| weather_shift | auction | central_6h | recovery_time | 3.2 | 96 | 29 | 7.238e-08 | 2.606e-05 | True |

Bonferroni correction over 360 tests is conservative, but the paired seeds make even small differences statistically detectable. Significance therefore measures consistency across seeds, not practical importance.

## 5. Figures

![Social cost by system and scenario with error bars](../../results/figures/fig1_social_cost.png)

*Figure 1: Social cost by system and scenario with error bars.*

![Market price over seven days in the plant-outage scenario](../../results/figures/fig2_price_plant_outage.png)

*Figure 2: Market price over seven days in the plant-outage scenario.*

![Unserved energy around the disruption](../../results/figures/fig3_recovery_unserved.png)

*Figure 3: Unserved energy around the disruption.*

![Q-learning reward curve](../../results/figures/fig4_learning_curve.png)

*Figure 4: Q-learning reward curve.*

![Learned storage policy heatmap](../../results/figures/fig5_qtable_heatmap.png)

*Figure 5: Learned storage policy heatmap.*

![Social-cost distribution over seeds](../../results/figures/fig6_social_cost_box.png)

*Figure 6: Social-cost distribution over seeds.*

## 6. Limitations

- The study uses a capacity-only model. There is no AC power flow, voltage, frequency or network topology; every MW is assumed transportable.
- All data are synthetic and generated by the documented weather, demand and supply equations. No external or real grid data are used.
- Agents follow fixed rules except the storage policy in `auction_q`. The result therefore measures the effect of tabular Q-learning for storage, not general multi-agent learning.
- The central planner forecast is noiseless and has no knowledge of future events. Central-6h intentionally holds its plan between replans, so it reacts to an outage only at the next replan; Central-1h isolates that delay.
- The central LP minimises fuel cost plus the configured VOLL. When a consumer's VOLL lies below the marginal cost of the available plant, the planner may rationally leave that demand unserved even though capacity exists. This is an economic outcome of the configured VOLL values, not a solver failure; the per-type UE columns make the effect visible.
- Recovery time is censored at the end of the run when the stability criterion is never met; the reported value then equals the remaining hours.
- Results are specific to the calibrated configuration and the 30 official seeds. They should not be extrapolated to real grids without validation.

## 7. Reproduction

```bat
pip install -r requirements.txt
pytest
python -m ai.train
python -m experiments.runner --seeds 30
streamlit run ui/app.py
```

Artefact directory: `C:/Users/user/Documents/gridMind/results`.
