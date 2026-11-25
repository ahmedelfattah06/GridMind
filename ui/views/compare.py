"""Compare page: saved experiments, statistics and report figures."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd
import streamlit as st

from ui import charts, components, data, theme
from ui.data import FIGURES_DIR, METRIC_LABELS

FIGURE_CAPTIONS = {
    "fig1_social_cost.png": "Social cost by scenario and system",
    "fig2_price_plant_outage.png": "Price response during the plant outage",
    "fig3_recovery_unserved.png": "Recovery and unserved energy",
    "fig4_learning_curve.png": "Q-learning reward curve",
    "fig5_qtable_heatmap.png": "Learned storage policy",
    "fig6_social_cost_box.png": "Per-run social cost distribution",
}


def _header(raw: pd.DataFrame | None = None) -> None:
    badges: list[str] = [components.badge("Official grid", tone="accent")]
    if raw is not None and not raw.empty:
        counts = data.experiment_counts(raw)
        badges.extend(
            [
                components.badge(f"{counts['runs']:,} runs"),
                components.badge(f"{counts['cells']} cells"),
            ]
        )
    components.page_header(
        "Evaluation workspace",
        "Compare systems",
        "Read the persisted 4-system experiment grid. Costs, reliability, fairness "
        "and the paired statistical tests all come from results/raw.csv and the "
        "artefacts written by experiments.runner.",
        badges=badges,
    )


def _filters(raw: pd.DataFrame) -> tuple[list[str], list[str]]:
    systems = data.available_systems(raw)
    scenarios = data.available_scenarios(raw)
    with st.container(border=True, key="gm-pair-compare-filters"):
        components.card_header(
            "Experiment filter",
            "Every chart, matrix and table below respects this selection.",
            right_html=components.badge("30 seeds per cell"),
        )
        columns = st.columns([1.1, 1.2])
        selected_systems = columns[0].multiselect(
            "Systems",
            systems,
            default=systems,
            format_func=data.system_label,
            key="compare_systems",
        )
        selected_scenarios = columns[1].multiselect(
            "Scenarios",
            scenarios,
            default=scenarios,
            format_func=data.scenario_label,
            key="compare_scenarios",
        )
        if len(selected_scenarios) == 1:
            st.caption(data.scenario_description(selected_scenarios[0]))
    return selected_systems, selected_scenarios


def _kpis(subset: pd.DataFrame, raw: pd.DataFrame, systems: Sequence[str]) -> None:
    mean_cost = float(subset["social_cost"].mean())
    mean_ue = float(subset["ue_total"].mean())
    mean_recovery = float(subset["recovery_time"].mean())
    best_system = (
        subset.groupby("system")["social_cost"].mean().idxmin() if not subset.empty else "—"
    )
    censored = data.censored_recovery_count(raw)
    items = [
        components.Kpi(
            label="Runs selected",
            value=f"{len(subset):,}",
            unit="runs",
            detail=(
                f"<strong>{subset['seed'].nunique()}</strong> seeds · "
                f"<strong>{subset[['system', 'scenario']].drop_duplicates().shape[0]}</strong> cells"
            ),
        ),
        components.Kpi(
            label="Mean social cost",
            value=components.fmt_compact(mean_cost),
            unit="currency",
            detail=f"Lowest mean: <strong>{data.system_label(str(best_system))}</strong>",
            tone="accent",
            help_text=data.metric_help("social_cost"),
        ),
        components.Kpi(
            label="Mean unserved",
            value=f"{mean_ue:,.1f}",
            unit="MWh",
            detail="Per run across selected cells",
            tone="danger" if mean_ue > 500 else "warning" if mean_ue > 50 else "default",
            help_text=data.metric_help("ue_total"),
        ),
        components.Kpi(
            label="Mean recovery",
            value=f"{mean_recovery:,.1f}",
            unit="hours",
            detail=(
                f"<strong>{censored} central cells censored</strong>"
                if censored
                else "No censored central cells"
            ),
            tone="warning" if mean_recovery > 24 else "default",
            help_text=data.metric_help("recovery_time"),
        ),
        components.Kpi(
            label="Renewable share",
            value=f"{float(subset['renewable_share'].mean()) * 100:,.1f}",
            unit="%",
            detail="Share of served energy from solar and wind",
            tone="info",
            help_text=data.metric_help("renewable_share"),
        ),
    ]
    components.kpi_grid(items)


def _caveats(raw: pd.DataFrame, systems: Sequence[str]) -> None:
    if not any(str(system).startswith("central") for system in systems):
        return
    auctions = raw[raw["system"].isin(["auction", "auction_q"])]
    central = raw[raw["system"].astype(str).str.startswith("central")]
    if auctions.empty or central.empty:
        return
    auction_factory = float(auctions["ue_factory"].mean())
    central_factory = float(central["ue_factory"].mean())
    components.callout(
        f"Central LP systems shed on average <strong>{central_factory:,.0f} MWh</strong> "
        f"of factory load per run, compared with <strong>{auction_factory:,.0f} MWh</strong> "
        "for the auction systems. Factory VOLL (40) sits below the thermal marginal cost "
        "(45), so the planner leaves that load unserved. Social cost and unserved energy "
        "are therefore not a clean like-for-like reliability comparison. Central recovery "
        "times are also censored at the end of the event window.",
        tone="warning",
        title="Interpret central LP results carefully.",
    )


def _summary(
    subset: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> None:
    """Best system per headline metric, next to the relative-profile radar."""

    wanted = ["social_cost", "ue_total", "recovery_time", "gini"]
    columns = [column for column in wanted if column in subset.columns]
    means = subset.groupby("system")[columns].mean() if columns else pd.DataFrame()
    if len(means) < 2:
        return
    specs = (
        ("social_cost", "Lowest social cost", lambda v: f"{components.fmt_compact(v)} currency"),
        ("ue_total", "Least unserved energy", lambda v: f"{v:,.1f} MWh"),
        ("recovery_time", "Fastest recovery", lambda v: f"{v:,.1f} h"),
        ("gini", "Most even outcomes", lambda v: f"{v:.4f} Gini"),
    )
    rows: list[tuple[str, str, str, str, str]] = []
    for column, label, fmt in specs:
        if column not in means:
            continue
        winner = str(means[column].idxmin())
        rows.append(
            (
                label,
                data.system_label(winner),
                theme.SYSTEM_COLORS.get(winner, theme.ACCENT),
                fmt(float(means.loc[winner, column])),
                f"best of {len(means)} systems",
            )
        )
    with st.container(key="gm-pair-compare-summary"):
        left, right = st.columns((1.0, 1.0), gap="medium")
        with left:
            with st.container(border=True):
                components.card_header(
                    "Result summary",
                    "Best system per metric inside the current filter.",
                    right_html=components.badge("Relative to selection", tone="accent"),
                )
                components.winner_grid(rows)
                st.caption(
                    "Read together with the central-LP caveat above: low social cost for "
                    "central dispatch partly reflects shed factory load."
                )
        with right:
            with st.container(border=True):
                components.card_header(
                    "System profile",
                    "Each axis is scaled between the worst (centre) and best (edge) system.",
                )
                st.plotly_chart(
                    charts.radar_figure(subset, systems, scenarios),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )


def _matrix_card(
    subset: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]
) -> None:
    with st.container(border=True):
        components.card_header(
            "Mean social cost matrix",
            "Scenario by system; the best value in each row is tagged.",
            right_html=components.badge("Lower is better", tone="accent"),
        )
        pivot = subset.pivot_table(
            index="scenario",
            columns="system",
            values="social_cost",
            aggfunc="mean",
        )
        values = {
            (scenario, system): (
                float(pivot.loc[scenario, system])
                if scenario in pivot.index and system in pivot.columns
                else None
            )
            for scenario in scenarios
            for system in systems
        }
        components.comparison_matrix(
            scenarios,
            systems,
            values,
            scenario_labels=data.SCENARIO_LABELS,
            system_labels=data.SYSTEM_LABELS,
            system_colors=theme.SYSTEM_COLORS,
            lower_is_better=True,
        )
        st.caption(
            "Social cost = generation cost + VOLL penalty, averaged over the selected "
            "seeds. The raw per-run distribution is available in the Run data tab."
        )


def _metric_summary(tab: Any, systems: Sequence[str], scenarios: Sequence[str]) -> None:
    with tab:
        summaries = data.load_summary()
        if summaries is None or summaries.empty:
            components.empty_state(
                "No bootstrap summary",
                "results/metrics_summary.csv is missing, so the confidence intervals "
                "cannot be displayed.",
                hint="Run: python -m experiments.runner --seeds 30",
                icon="database",
            )
            return
        table = summaries[
            summaries["scenario"].isin(scenarios) & summaries["system"].isin(systems)
        ].copy()
        if table.empty:
            components.empty_state(
                "No summaries for this filter",
                "The summary table does not contain any of the selected cells.",
                icon="table",
            )
            return
        with st.container(border=True):
            components.card_header(
                "Metric summary",
                "Mean, standard deviation and 95% bootstrap interval per cell.",
            )
            metric = st.selectbox(
                "Metric",
                sorted(table["metric"].unique()),
                format_func=data.metric_label,
                key="compare_metric",
                help="Each metric is summarised independently for every scenario and system.",
            )
            view = table[table["metric"] == metric][
                ["scenario", "system", "count", "mean", "std", "ci_low", "ci_high"]
            ].copy()
            view["scenario"] = view["scenario"].map(data.scenario_label)
            view["system"] = view["system"].map(data.system_label)
            st.dataframe(
                view,
                width="stretch",
                hide_index=True,
                column_config={
                    "scenario": st.column_config.TextColumn("Scenario"),
                    "system": st.column_config.TextColumn("System"),
                    "count": st.column_config.NumberColumn("n", format="%d"),
                    "mean": st.column_config.NumberColumn("Mean", format="%.3f"),
                    "std": st.column_config.NumberColumn("SD", format="%.3f"),
                    "ci_low": st.column_config.NumberColumn("95% low", format="%.3f"),
                    "ci_high": st.column_config.NumberColumn("95% high", format="%.3f"),
                },
            )
            st.caption(data.metric_help(metric))


def _pairwise_tab(tab: Any, systems: Sequence[str], scenarios: Sequence[str]) -> None:
    with tab:
        pairwise = data.load_pairwise()
        if pairwise is None or pairwise.empty:
            components.empty_state(
                "No paired tests",
                "results/stats_pairwise.csv is missing or empty.",
                hint="Run: python -m experiments.runner --seeds 30",
                icon="database",
            )
            return
        table = pairwise[
            pairwise["scenario"].isin(scenarios)
            & pairwise["baseline"].isin(systems)
            & pairwise["treatment"].isin(systems)
        ].copy()
        if table.empty:
            components.empty_state(
                "No tests for this filter",
                "The paired tests do not contain any selected scenario and system pair.",
                icon="table",
            )
            return
        with st.container(border=True):
            components.card_header(
                "Paired Wilcoxon tests",
                "Bonferroni-adjusted p-values over the full test family.",
                right_html=components.badge(f"{int(table['significant'].sum())} significant", tone="accent"),
            )
            metric = st.selectbox(
                "Metric",
                sorted(table["metric"].unique()),
                format_func=data.metric_label,
                key="compare_pairwise_metric",
            )
            view = table[table["metric"] == metric].copy()
            view["scenario"] = view["scenario"].map(data.scenario_label)
            view["baseline"] = view["baseline"].map(data.system_label)
            view["treatment"] = view["treatment"].map(data.system_label)
            view["relative_effect"] = view["relative_effect"].map(lambda value: f"{value * 100:+.2f}%")
            view["significant"] = view["significant"].map(lambda value: "Yes" if bool(value) else "No")
            st.dataframe(
                view[
                    [
                        "scenario",
                        "baseline",
                        "treatment",
                        "n_pairs",
                        "mean_difference",
                        "relative_effect",
                        "p_value",
                        "p_adjusted",
                        "significant",
                    ]
                ],
                width="stretch",
                hide_index=True,
                column_config={
                    "scenario": st.column_config.TextColumn("Scenario"),
                    "baseline": st.column_config.TextColumn("Baseline"),
                    "treatment": st.column_config.TextColumn("Treatment"),
                    "n_pairs": st.column_config.NumberColumn("Pairs", format="%d"),
                    "mean_difference": st.column_config.NumberColumn("Mean diff.", format="%.4f"),
                    "relative_effect": st.column_config.TextColumn("Relative effect"),
                    "p_value": st.column_config.NumberColumn("p", format="%.2e"),
                    "p_adjusted": st.column_config.NumberColumn("p (Bonferroni)", format="%.2e"),
                    "significant": st.column_config.TextColumn("Significant"),
                },
            )
            st.caption(
                f"{int(table['bonferroni_tests'].max())} tests in the correction family. "
                "A significant result means the paired difference survives the correction; "
                "it does not by itself establish a like-for-like reliability comparison."
            )


def _raw_tab(tab: Any, subset: pd.DataFrame) -> None:
    with tab:
        with st.container(border=True):
            components.card_header(
                "Per-run metrics",
                "One row per system, scenario and seed.",
                right_html=components.badge(f"{len(subset):,} rows"),
            )
            columns = [
                column
                for column in (
                    "system",
                    "scenario",
                    "seed",
                    "social_cost",
                    "ue_total",
                    "ue_hospital",
                    "ue_factory",
                    "hospital_outage_hours",
                    "recovery_time",
                    "messages",
                    "renewable_share",
                    "par",
                    "gini",
                )
                if column in subset.columns
            ]
            view = subset[columns].copy()
            view["system"] = view["system"].map(data.system_label)
            view["scenario"] = view["scenario"].map(data.scenario_label)
            st.dataframe(
                view,
                width="stretch",
                hide_index=True,
                column_config={
                    "system": st.column_config.TextColumn("System"),
                    "scenario": st.column_config.TextColumn("Scenario"),
                    "seed": st.column_config.NumberColumn("Seed", format="%d"),
                    "social_cost": st.column_config.NumberColumn("Social cost", format="%.0f"),
                    "ue_total": st.column_config.NumberColumn("UE (MWh)", format="%.2f"),
                    "ue_hospital": st.column_config.NumberColumn("UE hospital", format="%.2f"),
                    "ue_factory": st.column_config.NumberColumn("UE factory", format="%.2f"),
                    "hospital_outage_hours": st.column_config.NumberColumn(
                        "Hospital outage (h)", format="%d"
                    ),
                    "recovery_time": st.column_config.NumberColumn("Recovery (h)", format="%.1f"),
                    "messages": st.column_config.NumberColumn("Messages", format="%d"),
                    "renewable_share": st.column_config.NumberColumn("Renewable", format="percent"),
                    "par": st.column_config.NumberColumn("PAR", format="%.3f"),
                    "gini": st.column_config.NumberColumn("Gini", format="%.4f"),
                },
            )
            st.download_button(
                "Download filtered CSV",
                data=subset[columns].to_csv(index=False).encode("utf-8"),
                file_name="gridmind_filtered_metrics.csv",
                mime="text/csv",
                key="compare_download",
                width="stretch",
            )


def _figures_tab(tab: Any) -> None:
    with tab:
        figure_files = sorted(FIGURES_DIR.glob("*.png"))
        if not figure_files:
            components.empty_state(
                "No report figures",
                "results/figures does not contain any PNG files.",
                hint="Run: python -m experiments.runner --seeds 30",
                icon="database",
            )
            return
        with st.container(key="gm-pair-compare-figures"):
            columns = st.columns(2)
            for index, path in enumerate(figure_files):
                with columns[index % 2]:
                    st.image(
                        str(path),
                        caption=FIGURE_CAPTIONS.get(path.name, path.stem.replace("_", " ").title()),
                        width="stretch",
                    )
        st.caption(
            "These are the exact figures written by the experiment report pipeline; "
            "they are not regenerated in the dashboard."
        )


def _charts(subset: pd.DataFrame, systems: Sequence[str], scenarios: Sequence[str]) -> None:
    with st.container(border=True):
        components.card_header(
            "Social cost",
            "Mean per scenario with one-standard-deviation whiskers.",
            right_html=components.badge("Grouped by system"),
        )
        st.plotly_chart(
            charts.compare_cost_figure(subset, systems, scenarios),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    with st.container(border=True):
        components.card_header(
            "Reliability",
            "Unserved energy and recovery time by scenario and system.",
            right_html=components.badge("Lower is better", tone="accent"),
        )
        st.plotly_chart(
            charts.reliability_figure(subset, systems, scenarios),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    with st.container(border=True):
        components.card_header(
            "Fairness",
            "Peak-to-average ratio and Gini coefficient by system.",
        )
        st.plotly_chart(
            charts.fairness_figure(subset, systems, scenarios),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )

    with st.container(key="gm-pair-compare-distribution"):
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                components.card_header(
                    "Cost versus reliability",
                    "Bubble size reflects the renewable share.",
                )
                st.plotly_chart(
                    charts.tradeoff_figure(subset, systems, scenarios),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )
        with right:
            with st.container(border=True):
                components.card_header(
                    "Per-run distribution",
                    "Every seed is shown; the box marks the quartiles.",
                )
                st.plotly_chart(
                    charts.social_cost_box_figure(subset, systems),
                    width="stretch",
                    theme=None,
                    config=theme.PLOTLY_CONFIG,
                )


def render() -> None:
    """Render the Compare page."""

    try:
        raw = data.require_experiment_artefacts()
    except data.DataError as exc:
        _header()
        components.empty_state(
            "Experiment artefacts are missing",
            str(exc),
            hint="Run: python -m experiments.runner --seeds 30",
            icon="database",
        )
        return

    _header(raw)
    selected_systems, selected_scenarios = _filters(raw)
    if not selected_systems or not selected_scenarios:
        components.empty_state(
            "No runs selected",
            "Choose at least one system and one scenario to compare.",
            hint="The defaults select the complete official grid.",
            icon="table",
        )
        return
    subset = raw[
        raw["system"].isin(selected_systems) & raw["scenario"].isin(selected_scenarios)
    ]
    if subset.empty:
        components.empty_state(
            "No runs match this filter",
            "The selected systems and scenarios do not overlap in results/raw.csv.",
            icon="table",
        )
        return

    _kpis(subset, raw, selected_systems)
    _caveats(raw, selected_systems)
    _summary(subset, selected_systems, selected_scenarios)
    _matrix_card(subset, selected_systems, selected_scenarios)
    _charts(subset, selected_systems, selected_scenarios)

    tabs = st.tabs(["Metric summary", "Pairwise tests", "Run data", "Report figures"])
    _metric_summary(tabs[0], selected_systems, selected_scenarios)
    _pairwise_tab(tabs[1], selected_systems, selected_scenarios)
    _raw_tab(tabs[2], subset)
    _figures_tab(tabs[3])