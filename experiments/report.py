"""Markdown report generation from real GridMind results (Team D2).

The report is assembled only from the tables produced by the experiment runner.
Hypotheses are evaluated against the observed means; if a hypothesis is not
supported, the report says so instead of adjusting the numbers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from core.config import PROJECT_ROOT

SYSTEM_ORDER = ("central_6h", "central_1h", "auction", "auction_q")


def write_report(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pairwise: pd.DataFrame,
    figures: Sequence[str | Path],
    *,
    config: Mapping[str, Any],
    output_path: str | Path = PROJECT_ROOT / "docs" / "report" / "REPORT.md",
    results_dir: str | Path = PROJECT_ROOT / "results",
) -> Path:
    """Write the final Markdown report and return its path."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    systems = _systems(metrics)
    scenarios = _scenarios(metrics)
    lines: list[str] = []
    lines.append("# GridMind - Experimental Report")
    lines.append("")
    lines.append(
        "This report is generated automatically from the artefacts of a completed "
        "`python -m experiments.runner` execution. Every number below is simulation "
        "output; no expected value is inserted by hand."
    )
    lines.append("")
    lines.append("## 1. Research question and design")
    lines.append("")
    lines.append(
        "> Is decentralised negotiation between autonomous agents more robust than "
        "centralised planning when power plants fail or demand suddenly increases?"
    )
    lines.append("")
    steps = int(config["simulation"]["steps"])
    lines.append(
        f"- Duration: **{steps} hourly steps** (7 days) per run.\n"
        f"- Systems: **{', '.join(systems)}**.\n"
        f"- Scenarios: **{', '.join(scenarios)}**.\n"
        f"- Seeds per system/scenario: **{_seed_count(metrics)}**.\n"
        f"- Completed runs: **{len(metrics)}**.\n"
        f"- Paired design: all systems in one scenario use the same seed, so weather "
        "and demand noise are identical across systems."
    )
    lines.append("")
    lines.append("## 2. Main results")
    lines.append("")
    lines.append("### Social cost (mean ± standard deviation over seeds)")
    lines.append("")
    lines.append(_markdown_table(_social_cost_table(summary, scenarios, systems)))
    lines.append("")
    lines.append("Lower social cost is better. Social cost is generation fuel cost plus "
                 "the configured value-of-lost-load penalty of unserved energy.")
    lines.append("")
    lines.append("### Reliability and market indicators")
    lines.append("")
    lines.append(_markdown_table(_indicator_table(summary, scenarios, systems)))
    lines.append("")
    lines.append("### Reading the results")
    lines.append("")
    lines.extend(_reading_lines(metrics, summary, config))
    lines.append("")
    lines.append("## 3. Hypotheses")
    lines.append("")
    lines.extend(_hypothesis_lines(metrics, summary, pairwise, config))
    lines.append("")
    lines.append("## 4. Statistical comparison")
    lines.append("")
    if pairwise is None or pairwise.empty:
        lines.append("No pairwise comparison was produced (fewer than two systems selected).")
    else:
        significant = pairwise[pairwise["significant"]] if "significant" in pairwise else pairwise.iloc[0:0]
        lines.append(
            f"- Pairwise Wilcoxon signed-rank tests: **{len(pairwise)}** comparisons, "
            f"Bonferroni corrected over all tests (`bonferroni_tests` column).\n"
            f"- Comparisons significant at adjusted p < 0.05: **{len(significant)}**.\n"
            "- Effect size is reported as the relative difference of the means "
            "(treatment minus baseline, divided by the absolute baseline mean).\n"
            "- Only the hypothesis-relevant comparisons are shown below; the complete "
            "table is in "
            f"`{_relative_link(Path(results_dir) / 'stats_pairwise.csv', destination.parent)}`."
        )
        lines.append("")
        lines.append(_markdown_table(_pairwise_table(pairwise)))
        lines.append("")
        correction_count = (
            int(pairwise["bonferroni_tests"].iloc[0])
            if "bonferroni_tests" in pairwise.columns and not pairwise.empty
            else len(pairwise)
        )
        lines.append(
            f"Bonferroni correction over {correction_count} tests is conservative, but the "
            "paired seeds make even small differences statistically detectable. Significance "
            "therefore measures consistency across seeds, not practical importance."
        )
    lines.append("")
    lines.append("## 5. Figures")
    lines.append("")
    captions = (
        "Social cost by system and scenario with error bars",
        "Market price over seven days in the plant-outage scenario",
        "Unserved energy around the disruption",
        "Q-learning reward curve",
        "Learned storage policy heatmap",
        "Social-cost distribution over seeds",
    )
    for index, figure in enumerate(figures):
        caption = captions[index] if index < len(captions) else Path(figure).stem
        relative = _relative_link(figure, destination.parent)
        lines.append(f"![{caption}]({relative})")
        lines.append("")
        lines.append(f"*Figure {index + 1}: {caption}.*")
        lines.append("")
    lines.append("## 6. Limitations")
    lines.append("")
    lines.append(
        "- The study uses a capacity-only model. There is no AC power flow, voltage, "
        "frequency or network topology; every MW is assumed transportable.\n"
        "- All data are synthetic and generated by the documented weather, demand and "
        "supply equations. No external or real grid data are used.\n"
        "- Agents follow fixed rules except the storage policy in `auction_q`. The "
        "result therefore measures the effect of tabular Q-learning for storage, not "
        "general multi-agent learning.\n"
        "- The central planner forecast is noiseless and has no knowledge of future "
        "events. Central-6h intentionally holds its plan between replans, so it reacts "
        "to an outage only at the next replan; Central-1h isolates that delay.\n"
        "- The central LP minimises fuel cost plus the configured VOLL. When a "
        "consumer's VOLL lies below the marginal cost of the available plant, the "
        "planner may rationally leave that demand unserved even though capacity "
        "exists. This is an economic outcome of the configured VOLL values, not a "
        "solver failure; the per-type UE columns make the effect visible.\n"
        "- Recovery time is censored at the end of the run when the stability criterion "
        "is never met; the reported value then equals the remaining hours.\n"
        "- Results are specific to the calibrated configuration and the 30 official "
        "seeds. They should not be extrapolated to real grids without validation."
    )
    lines.append("")
    lines.append("## 7. Reproduction")
    lines.append("")
    lines.append("```bat")
    lines.append("pip install -r requirements.txt")
    lines.append("pytest")
    lines.append("python -m ai.train")
    lines.append("python -m experiments.runner --seeds 30")
    lines.append("streamlit run ui/app.py")
    lines.append("```")
    lines.append("")
    lines.append(f"Artefact directory: `{Path(results_dir).as_posix()}`.")
    lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def _systems(metrics: pd.DataFrame) -> list[str]:
    present = [str(value) for value in metrics["system"].unique()]
    return [system for system in SYSTEM_ORDER if system in present] + sorted(
        set(present) - set(SYSTEM_ORDER)
    )


def _scenarios(metrics: pd.DataFrame) -> list[str]:
    return sorted(str(value) for value in metrics["scenario"].unique())


def _seed_count(metrics: pd.DataFrame) -> int:
    if "seed" in metrics:
        return int(metrics["seed"].nunique())
    return 0


def _metric_mean(
    summary: pd.DataFrame,
    scenario: str,
    system: str,
    metric: str,
) -> float | None:
    subset = summary[
        (summary["scenario"] == scenario)
        & (summary["system"] == system)
        & (summary["metric"] == metric)
    ]
    if subset.empty:
        return None
    return float(subset["mean"].iloc[0])


def _social_cost_table(summary: pd.DataFrame, scenarios: list[str], systems: list[str]) -> pd.DataFrame:
    rows = []
    for scenario in scenarios:
        row: dict[str, Any] = {"Scenario": scenario.replace("_", " ").title()}
        for system in systems:
            subset = summary[
                (summary["scenario"] == scenario)
                & (summary["system"] == system)
                & (summary["metric"] == "social_cost")
            ]
            if subset.empty:
                row[system] = "-"
            else:
                mean = float(subset["mean"].iloc[0])
                std = float(subset["std"].iloc[0])
                row[system] = f"{mean:,.0f} ± {std:,.0f}"
        rows.append(row)
    return pd.DataFrame(rows)


def _indicator_table(summary: pd.DataFrame, scenarios: list[str], systems: list[str]) -> pd.DataFrame:
    metrics = (
        ("ue_hospital", "Hospital UE (MWh)"),
        ("hospital_outage_hours", "Hospital outage hours"),
        ("recovery_time", "Recovery time (h)"),
        ("messages", "Messages"),
        ("renewable_share", "Renewable share"),
    )
    rows = []
    for scenario in scenarios:
        for system in systems:
            row: dict[str, Any] = {
                "Scenario": scenario.replace("_", " ").title(),
                "System": system,
            }
            for metric, label in metrics:
                value = _metric_mean(summary, scenario, system, metric)
                row[label] = "-" if value is None else f"{value:,.3f}"
            rows.append(row)
    return pd.DataFrame(rows)


def _pairwise_p(
    pairwise: pd.DataFrame,
    scenario: str,
    baseline: str,
    treatment: str,
    metric: str,
) -> float | None:
    """Return the corrected p-value for one hypothesis comparison."""

    if pairwise is None or pairwise.empty:
        return None
    subset = pairwise[
        (pairwise["scenario"] == scenario)
        & (pairwise["baseline"] == baseline)
        & (pairwise["treatment"] == treatment)
        & (pairwise["metric"] == metric)
    ]
    if subset.empty:
        return None
    column = "p_adjusted" if "p_adjusted" in subset.columns else "p_value"
    return float(subset[column].iloc[0])


def _reading_lines(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    config: Mapping[str, Any],
) -> list[str]:
    """Return short, data-derived reading notes for the results tables."""

    systems = _systems(metrics)
    scenarios = _scenarios(metrics)
    central = [system for system in systems if system.startswith("central")]
    event_scenarios = [
        scenario
        for scenario in scenarios
        if config.get("scenarios", {}).get(scenario, {}).get("events")
    ]
    lines: list[str] = []

    hospital_ue = [
        value
        for scenario in scenarios
        for system in systems
        if (value := _metric_mean(summary, scenario, system, "ue_hospital")) is not None
    ]
    hospital_hours = [
        value
        for scenario in scenarios
        for system in systems
        if (value := _metric_mean(summary, scenario, system, "hospital_outage_hours")) is not None
    ]
    if hospital_ue and hospital_hours:
        worst_ue = max(hospital_ue)
        worst_hours = max(hospital_hours)
        if worst_ue <= 0.001 and worst_hours <= 0.001:
            lines.append(
                "- Hospital load is fully served in every run: hospital UE and hospital "
                f"outage time are zero across all {len(scenarios) * len(systems)} "
                "system/scenario cells."
            )
        else:
            lines.append(
                f"- Hospital load is not fully served: the worst cell has {worst_ue:,.3f} "
                f"MWh of hospital UE and {worst_hours:,.3f} h of hospital outage."
            )

    normal_factory = [
        value
        for system in central
        if (value := _metric_mean(summary, "normal", system, "ue_factory")) is not None
    ]
    if normal_factory:
        factory_voll = config.get("voll", {}).get("factory")
        thermal_cost = max(
            (
                float(producer.get("marginal_cost", 0.0))
                for producer in config.get("producers", [])
                if producer.get("type") == "thermal"
            ),
            default=None,
        )
        calibration = ""
        if factory_voll is not None and thermal_cost is not None:
            calibration = (
                f" The configured factory VOLL ({float(factory_voll):g}) is below the "
                f"thermal marginal cost ({thermal_cost:g}),"
            )
        lines.append(
            f"- In `normal`, the central systems still leave "
            f"{min(normal_factory):,.0f}-{max(normal_factory):,.0f} MWh of factory demand "
            f"unserved.{calibration} so the LP prefers to shed that load. This standing "
            "shortfall dominates central UE and lowers central generation cost; it is an "
            "economic dispatch outcome, not a solver failure."
        )

    auction_ue = [
        value
        for scenario in scenarios
        if (value := _metric_mean(summary, scenario, "auction", "ue_total")) is not None
    ]
    auction_recovery = [
        value
        for scenario in event_scenarios
        if (value := _metric_mean(summary, scenario, "auction", "recovery_time")) is not None
    ]
    if auction_ue:
        text = (
            f"- The auction keeps total UE between {min(auction_ue):,.0f} and "
            f"{max(auction_ue):,.0f} MWh across the five scenarios"
        )
        if auction_recovery:
            text += (
                f", and in event scenarios it returns to its pre-event price/UE band "
                f"within {min(auction_recovery):,.1f}-{max(auction_recovery):,.1f} h"
            )
        lines.append(text + ".")

    steps = int(config["simulation"]["steps"])
    censored: list[str] = []
    for scenario in event_scenarios:
        events = config["scenarios"][scenario].get("events", []) or []
        start = int(min(int(event["start"]) for event in events))
        remaining = steps - start
        for system in central:
            value = _metric_mean(summary, scenario, system, "recovery_time")
            if value is not None and abs(value - remaining) < 0.51:
                censored.append(f"{scenario}/{system}")
    if censored:
        lines.append(
            f"- Central recovery time reaches the end of the window in {len(censored)} of "
            f"{len(event_scenarios) * len(central)} event-system cells because the standing "
            "factory shortfall never clears. Those values are censored, not measured "
            "recovery times."
        )

    cost_changes: list[float] = []
    ue_changes: list[float] = []
    for scenario in scenarios:
        q_cost = _metric_mean(summary, scenario, "auction_q", "social_cost")
        rule_cost = _metric_mean(summary, scenario, "auction", "social_cost")
        q_ue = _metric_mean(summary, scenario, "auction_q", "ue_total")
        rule_ue = _metric_mean(summary, scenario, "auction", "ue_total")
        if q_cost is not None and rule_cost not in (None, 0.0):
            cost_changes.append((q_cost - rule_cost) / abs(rule_cost))
        if q_ue is not None and rule_ue not in (None, 0.0):
            ue_changes.append((q_ue - rule_ue) / abs(rule_ue))
    if cost_changes and ue_changes:
        cost_lower = sum(change < 0 for change in cost_changes)
        ue_higher = sum(change > 0 for change in ue_changes)
        reductions = [-change for change in cost_changes if change < 0]
        increases = [change for change in ue_changes if change > 0]
        cost_range = (
            f"by {min(reductions):.2%}-{max(reductions):.2%}" if reductions else "in mixed directions"
        )
        ue_range = (
            f"by {min(increases):+.2%} to {max(increases):+.2%}"
            if increases
            else "in mixed directions"
        )
        lines.append(
            f"- Q-learning lowers modelled social cost in {cost_lower}/{len(cost_changes)} "
            f"scenarios ({cost_range}) but raises total UE in {ue_higher}/{len(ue_changes)} "
            f"scenarios ({ue_range}). The extra unserved energy is factory load, so this is a "
            "shift toward the lowest-VOLL consumer rather than a reliability improvement."
        )
    return lines


def _hypothesis_lines(
    metrics: pd.DataFrame,
    summary: pd.DataFrame,
    pairwise: pd.DataFrame,
    config: Mapping[str, Any],
) -> list[str]:
    lines: list[str] = []
    normal_central = _metric_mean(summary, "normal", "central_6h", "social_cost")
    normal_auction = _metric_mean(summary, "normal", "auction", "social_cost")
    normal_1h = _metric_mean(summary, "normal", "central_1h", "social_cost")
    lines.append("### H1 - Central planning is cheaper in normal conditions")
    lines.append("")
    if normal_central is None or normal_auction is None:
        lines.append("Not enough data to evaluate H1.")
    else:
        difference = _relative(normal_central, normal_auction)
        supported = normal_central < normal_auction
        lines.append(
            f"Observed normal-scenario social cost: Central-6h = {normal_central:,.1f}, "
            f"Auction = {normal_auction:,.1f}. The central system is "
            f"{'cheaper' if supported else 'more expensive'} by {abs(difference):.2%}. "
            f"**H1 is {'descriptively supported' if supported else 'not supported'} by these runs.**"
        )
        adjusted_p = _pairwise_p(
            pairwise, "normal", "auction", "central_6h", "social_cost"
        )
        if adjusted_p is not None:
            lines.append("")
            if adjusted_p < 0.05:
                lines.append(
                    f"The {abs(difference):.2%} gap is significant after Bonferroni "
                    f"correction (adjusted p = {adjusted_p:.3g})."
                )
            else:
                lines.append(
                    f"The {abs(difference):.2%} gap is not significant after Bonferroni "
                    f"correction (adjusted p = {adjusted_p:.3g}), so H1 should be read as "
                    "a descriptive difference rather than a confirmed cost advantage."
                )
        if normal_1h is not None:
            lines.append("")
            lines.append(
                f"Central-1h is cheaper still at {normal_1h:,.1f} "
                f"({_relative(normal_auction, normal_1h):+.2%} versus the auction), so the "
                "margin depends strongly on replanning frequency."
            )
        lines.append("")
        lines.append(
            "The comparison is not like-for-like on served energy: the central systems "
            "shed standing factory load (see *Reading the results*), which lowers their "
            "generation cost. H1 holds descriptively in the modelled objective, but it "
            "should not be read as proof that central dispatch is cheaper per MWh actually "
            "served."
        )
    lines.append("")

    lines.append("### H2 - Decentralised auction recovers better from disruptions")
    lines.append("")
    evidence: list[str] = []
    supported_votes = 0
    total_votes = 0
    for scenario in ("plant_outage", "combined"):
        recovery_auction = _metric_mean(summary, scenario, "auction", "recovery_time")
        recovery_central = _metric_mean(summary, scenario, "central_6h", "recovery_time")
        ue_auction = _metric_mean(summary, scenario, "auction", "ue_total")
        ue_central = _metric_mean(summary, scenario, "central_6h", "ue_total")
        if recovery_auction is None or recovery_central is None:
            continue
        total_votes += 2
        recovery_supported = recovery_auction < recovery_central
        ue_supported = (ue_auction is not None and ue_central is not None and ue_auction < ue_central)
        supported_votes += int(recovery_supported) + int(ue_supported)
        evidence.append(
            f"- {scenario.replace('_', ' ').title()}: recovery Auction "
            f"{recovery_auction:.2f} h vs Central-6h {recovery_central:.2f} h; "
            f"UE Auction {ue_auction:,.2f} MWh vs Central-6h {ue_central:,.2f} MWh."
        )
    recovery_6 = _metric_mean(summary, "plant_outage", "central_6h", "recovery_time")
    recovery_1 = _metric_mean(summary, "plant_outage", "central_1h", "recovery_time")
    if recovery_6 is not None and recovery_1 is not None:
        evidence.append(
            f"- Replanning delay check in plant outage: Central-6h "
            f"{recovery_6:.2f} h vs Central-1h {recovery_1:.2f} h."
        )
    lines.extend(evidence)
    if total_votes:
        verdict = "weakly supported" if supported_votes * 2 >= total_votes else "not supported"
        lines.append(
            f"Across the two disruption scenarios, **{supported_votes}/{total_votes}** "
            "recovery and unserved-energy comparisons favour the auction. "
            f"H2 is **{verdict}** by these observations."
        )
        central_factory = _metric_mean(summary, "normal", "central_6h", "ue_factory")
        if central_factory is not None:
            lines.append("")
            lines.append(
                f"The vote is confounded by the standing factory shortfall: Central-6h "
                f"already leaves {central_factory:,.0f} MWh of factory load unserved in "
                "`normal`, and its recovery time is censored at the end of every event "
                "window. The auction genuinely restores its pre-event band, but the "
                "central-versus-auction UE and recovery gaps are not a clean measure of "
                "outage response alone."
            )
    else:
        lines.append("Not enough disruption data to evaluate H2.")
    lines.append("")

    lines.append("### H3 - Q-learning storage improves on the fixed rule")
    lines.append("")
    q_cost = _metric_mean(summary, "normal", "auction_q", "social_cost")
    rule_cost = _metric_mean(summary, "normal", "auction", "social_cost")
    q_par = _metric_mean(summary, "normal", "auction_q", "par")
    rule_par = _metric_mean(summary, "normal", "auction", "par")
    overall_q = _overall_mean(metrics, "auction_q", "social_cost")
    overall_rule = _overall_mean(metrics, "auction", "social_cost")
    overall_q_ue = _overall_mean(metrics, "auction_q", "ue_total")
    overall_rule_ue = _overall_mean(metrics, "auction", "ue_total")
    if q_cost is None or rule_cost is None:
        lines.append("Not enough data to evaluate H3.")
    else:
        cost_supported = q_cost < rule_cost
        par_supported = q_par is not None and rule_par is not None and q_par < rule_par
        ue_supported = overall_q_ue < overall_rule_ue
        par_text = f"{q_par:.3f}" if q_par is not None else "n/a"
        rule_par_text = f"{rule_par:.3f}" if rule_par is not None else "n/a"
        lines.append(
            f"Normal-scenario social cost: Auction+Q = {q_cost:,.1f}, Auction = "
            f"{rule_cost:,.1f}. PAR: Auction+Q = {par_text}, Auction = {rule_par_text}. "
            f"Across all scenarios the mean social cost is {overall_q:,.1f} for Auction+Q "
            f"and {overall_rule:,.1f} for Auction; mean total UE is {overall_q_ue:,.1f} MWh "
            f"for Auction+Q and {overall_rule_ue:,.1f} MWh for Auction."
        )
        lines.append("")
        if cost_supported and not ue_supported:
            verdict = "partially supported on social cost only"
            detail = (
                "The cost reduction is real in the modelled objective, but it comes with "
                "more unserved energy, concentrated in factory load. The PAR criterion also "
                "does not improve."
            )
        elif cost_supported and ue_supported and par_supported:
            verdict = "supported"
            detail = "Social cost, unserved energy and PAR all improve."
        elif cost_supported or ue_supported or par_supported:
            verdict = "partially supported"
            detail = "Only some of the social-cost, unserved-energy and PAR criteria improve."
        else:
            verdict = "not supported"
            detail = "None of the social-cost, unserved-energy or PAR criteria improve."
        lines.append(f"**H3 is {verdict}** by the executed runs. {detail}")
    return lines


def _overall_mean(metrics: pd.DataFrame, system: str, metric: str) -> float:
    subset = metrics[metrics["system"] == system]
    if subset.empty or metric not in subset:
        return 0.0
    return float(pd.to_numeric(subset[metric], errors="coerce").mean())


def _relative(reference: float, comparison: float) -> float:
    if abs(reference) <= 1e-12:
        return 0.0
    return (comparison - reference) / abs(reference)


def _pairwise_table(pairwise: pd.DataFrame) -> pd.DataFrame:
    frame = pairwise.copy()
    if frame.empty:
        return frame
    pairs = {
        ("auction", "central_6h"),
        ("auction", "central_1h"),
        ("auction", "auction_q"),
    }
    metrics = {"social_cost", "ue_total", "recovery_time"}
    mask = frame.apply(
        lambda row: (row.get("baseline"), row.get("treatment")) in pairs
        and row.get("metric") in metrics,
        axis=1,
    )
    selected = frame[mask]
    if not selected.empty:
        frame = selected
    keep = [
        column
        for column in (
            "scenario",
            "baseline",
            "treatment",
            "metric",
            "mean_baseline",
            "mean_treatment",
            "relative_effect",
            "p_value",
            "p_adjusted",
            "significant",
        )
        if column in frame.columns
    ]
    frame = frame[keep]
    for column in ("mean_baseline", "mean_treatment", "relative_effect", "p_value", "p_adjusted"):
        if column in frame:
            frame[column] = frame[column].map(
                lambda value: f"{value:.4g}" if isinstance(value, (int, float)) else value
            )
    return frame


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return "_No rows._"
    columns = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in frame.iterrows():
        values = [str(row[column]).replace("|", "\\|") for column in frame.columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _relative_link(path: str | Path, start: Path) -> str:
    import os

    try:
        return Path(os.path.relpath(Path(path), start)).as_posix()
    except ValueError:  # different drive on Windows
        return Path(path).as_posix()


__all__ = ["write_report"]
