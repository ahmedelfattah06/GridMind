"""Learning page: Q-table, training evidence and rule-vs-Q comparison."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import streamlit as st

from ai.qlearning import N_ACTIONS, N_STATES, state_index
from core.config import OFFICIAL_SCENARIOS, load_config
from core.factory import build_model
from experiments.metrics import compute_run_metrics
from ui import charts, components, data, state, theme

SOC_LABELS = ("0–20%", "20–40%", "40–60%", "60–80%", "80–100%")
PRICE_LABELS = ("Cheap", "Normal", "Expensive")
PERIOD_LABELS = ("Night · 00–06", "Morning · 06–12", "Midday · 12–18", "Evening · 18–24")
VIEW_LABELS = {
    "Greedy policy": "policy",
    "Q(wait)": "wait",
    "Q(charge)": "charge",
    "Q(discharge)": "discharge",
}
FRESH_COLUMNS = (
    "system",
    "social_cost",
    "ue_total",
    "ue_hospital",
    "price_volatility",
    "par",
    "gini",
    "recovery_time",
    "renewable_share",
    "storage_cycles",
)


def _header(
    metadata: Mapping[str, Any] | None = None,
    qtable: np.ndarray | None = None,
) -> None:
    badges = [components.badge("Tabular Q-learning", tone="accent")]
    if metadata:
        badges.append(components.badge(f"{int(metadata.get('episodes', 0)):,} episodes"))
        final = metadata.get("final_mean_reward")
        if final is not None:
            badges.append(components.badge(f"Final reward {float(final):,.1f}"))
    elif qtable is not None:
        badges.append(components.badge(f"{qtable.shape[0]} states × {qtable.shape[1]} actions"))
    components.page_header(
        "Learning laboratory",
        "Learning",
        "The storage policy is trained offline with tabular Q-learning and persisted as "
        "qtable.npy. This page reads that table, the training curve and the saved "
        "auction-versus-auction_q experiment evidence.",
        badges=badges,
    )


def _kpis(
    metadata: Mapping[str, Any] | None,
    curve: pd.DataFrame | None,
    qtable: np.ndarray,
) -> None:
    greedy = np.argmax(qtable, axis=1)
    counts = {action: int((greedy == action).sum()) for action in range(N_ACTIONS)}
    episodes = int(metadata.get("episodes", 0)) if metadata else 0
    if not episodes and curve is not None and not curve.empty:
        episodes = int(curve["episode"].max())
    reward = metadata.get("final_mean_reward") if metadata else None
    if reward is None and curve is not None and not curve.empty:
        reward = float(curve["mean_reward"].iloc[-1])
    td_error = (
        float(curve["mean_td_error"].iloc[-1])
        if curve is not None and not curve.empty and "mean_td_error" in curve
        else None
    )
    updated = int((np.abs(qtable) > 1e-12).sum())
    visited = int((np.abs(qtable).sum(axis=1) > 1e-12).sum())
    items = [
        components.Kpi(
            label="Training episodes",
            value=f"{episodes:,}" if episodes else "—",
            detail="168-hour episodes on official scenarios"
            if episodes
            else "Training metadata unavailable",
            spark=curve["mean_reward"].tolist() if curve is not None and not curve.empty else None,
            help_text="Training runs offline in ai.train; the dashboard does not retrain.",
        ),
        components.Kpi(
            label="Final mean reward",
            value=components.fmt_number(reward, 1),
            detail="Last 50-episode window" if reward is not None else "No reward record",
            tone="accent",
            spark=curve["mean_reward"].tolist() if curve is not None and not curve.empty else None,
        ),
        components.Kpi(
            label="Final TD error",
            value=components.fmt_number(td_error, 2),
            detail="Mean absolute error at the last checkpoint",
            tone="info",
            spark=curve["mean_td_error"].tolist()
            if curve is not None and not curve.empty and "mean_td_error" in curve
            else None,
        ),
        components.Kpi(
            label="States visited",
            value=f"{visited}",
            unit=f"/ {N_STATES}",
            detail=f"<strong>{updated}</strong> Q-values updated",
            help_text="A state is visited when at least one of its three Q-values is non-zero.",
        ),
        components.Kpi(
            label="Discharge states",
            value=f"{counts.get(2, 0)}",
            unit=f"/ {N_STATES}",
            detail=(
                f"Charge <strong>{counts.get(1, 0)}</strong> · "
                f"Wait <strong>{counts.get(0, 0)}</strong>"
            ),
            tone="warning",
            help_text="States where the greedy action is discharge.",
        ),
    ]
    components.kpi_grid(items)


def _policy_tab(tab: Any, metadata: Mapping[str, Any] | None, qtable: np.ndarray) -> None:
    with tab:
        with st.container(border=True):
            components.card_header(
                "Learned policy heatmap",
                "60 states: 5 SoC bins × 3 price bins × 4 periods. "
                "W wait · C charge · D discharge.",
                right_html=components.badge("Hover for all Q-values", tone="accent"),
            )
            layer = st.selectbox(
                "Heatmap layer",
                list(VIEW_LABELS),
                key="learning_q_view",
                help="The policy view colours each state by its greedy action.",
            )
            st.plotly_chart(
                charts.q_heatmap_figure(qtable, VIEW_LABELS[layer]),
                width="stretch",
                theme=None,
                config=theme.PLOTLY_CONFIG,
            )

        with st.container(key="gm-pair-learning-explorer"):
            left, right = st.columns((1.2, 1.0), gap="medium")
            with left:
                with st.container(border=True):
                    components.card_header(
                        "State explorer",
                        "Inspect the three learned action values for any discrete state.",
                    )
                    columns = st.columns(3)
                    soc_choice = columns[0].selectbox(
                        "State of charge",
                        options=list(range(5)),
                        index=4,
                        format_func=lambda value: SOC_LABELS[value],
                        key="learning_soc",
                    )
                    price_choice = columns[1].selectbox(
                        "Price regime",
                        options=list(range(3)),
                        index=1,
                        format_func=lambda value: PRICE_LABELS[value],
                        key="learning_price",
                    )
                    period_choice = columns[2].selectbox(
                        "Period",
                        options=list(range(4)),
                        index=3,
                        format_func=lambda value: PERIOD_LABELS[value],
                        key="learning_period",
                    )
                    representative_price = (80.0, 100.0, 120.0)[price_choice]
                    state_number = state_index(
                        (soc_choice + 0.5) * 4.0,
                        representative_price,
                        100.0,
                        period_choice * 6,
                        capacity_mwh=20.0,
                    )
                    values = qtable[state_number]
                    greedy = int(np.argmax(values))
                    components.definition_grid(
                        [
                            ("State index", str(state_number)),
                            ("SoC bin", f"{soc_choice} · {SOC_LABELS[soc_choice]}"),
                            ("Price bin", f"{price_choice} · {PRICE_LABELS[price_choice]}"),
                            ("Period bin", f"{period_choice} · {PERIOD_LABELS[period_choice]}"),
                        ]
                    )
                    components.q_value_rows(values, greedy)
                    st.caption(
                        "The state index follows the production discretisation: "
                        "(SoC bin × 3 + price bin) × 4 + period."
                    )
            with right:
                with st.container(border=True):
                    components.card_header(
                        "Greedy action mix",
                        "Action chosen in the 60 discrete states.",
                    )
                    greedy = np.argmax(qtable, axis=1)
                    counts = {action: int((greedy == action).sum()) for action in range(N_ACTIONS)}
                    components.action_distribution(counts)
                    st.divider()
                    config = load_config().get("qlearning", {}) or {}
                    components.definition_grid(
                        [
                            ("Algorithm", "Tabular Q-learning"),
                            ("Learning rate α", f"{float(config.get('alpha', 0.1)):.2f}"),
                            ("Discount γ", f"{float(config.get('gamma', 0.95)):.2f}"),
                            ("Epsilon", f"{float(config.get('epsilon_start', 1.0)):.2f} → {float(config.get('epsilon_end', 0.05)):.2f}"),
                            ("Decay episodes", f"{int(metadata.get('epsilon_decay_episodes', config.get('epsilon_decay_episodes', 1500)))}" if metadata else f"{int(config.get('epsilon_decay_episodes', 1500))}"),
                            ("Reward", "revenue − cost − 0.5 × throughput − 0.5 × UE"),
                        ]
                    )


def _saved_evidence() -> None:
    try:
        raw = data.load_raw_metrics()
    except data.DataError as exc:
        components.empty_state(
            "No saved rule-vs-Q evidence",
            str(exc),
            hint="Run: python -m experiments.runner --seeds 30",
            icon="database",
        )
        return
    if not {"auction", "auction_q"}.issubset(set(raw["system"])):
        components.empty_state(
            "Both auction variants are required",
            "results/raw.csv does not contain both auction and auction_q runs.",
            icon="table",
        )
        return

    components.kpi_grid(
        [
            components.Kpi(
                label="Rule-based cost",
                value=components.fmt_compact(float(raw[raw["system"] == "auction"]["social_cost"].mean())),
                unit="currency",
                detail="Auction with the rule-based battery",
            ),
            components.Kpi(
                label="Learned cost",
                value=components.fmt_compact(float(raw[raw["system"] == "auction_q"]["social_cost"].mean())),
                unit="currency",
                detail="Auction with the persisted Q-table",
                tone="accent",
            ),
            components.Kpi(
                label="Rule-based UE",
                value=f"{float(raw[raw['system'] == 'auction']['ue_total'].mean()):,.1f}",
                unit="MWh",
                detail="Mean per run across 150 auction runs",
            ),
            components.Kpi(
                label="Learned UE",
                value=f"{float(raw[raw['system'] == 'auction_q']['ue_total'].mean()):,.1f}",
                unit="MWh",
                detail="Mean per run across 150 learned runs",
                tone="warning",
            ),
            components.Kpi(
                label="Saved comparisons",
                value=f"{len(raw[raw['system'] == 'auction']):,}",
                unit="pairs",
                detail="Same scenario and seed in both systems",
            ),
        ]
    )

    rows = []
    for scenario in OFFICIAL_SCENARIOS:
        rule = raw[(raw["scenario"] == scenario) & (raw["system"] == "auction")]
        learned = raw[(raw["scenario"] == scenario) & (raw["system"] == "auction_q")]
        if rule.empty or learned.empty:
            continue
        rule_cost = float(rule["social_cost"].mean())
        learned_cost = float(learned["social_cost"].mean())
        rule_ue = float(rule["ue_total"].mean())
        learned_ue = float(learned["ue_total"].mean())
        rows.append(
            {
                "scenario": data.scenario_label(scenario),
                "Rule cost": rule_cost,
                "Q cost": learned_cost,
                "Cost Δ": f"{100.0 * (learned_cost - rule_cost) / rule_cost:+.2f}%",
                "Rule UE": rule_ue,
                "Q UE": learned_ue,
                "UE Δ": f"{100.0 * (learned_ue - rule_ue) / rule_ue:+.2f}%",
                "Q cycles": float(learned["storage_cycles"].mean()),
            }
        )
    frame = pd.DataFrame(rows)

    with st.container(border=True):
        components.card_header(
            "Saved 600-run evidence",
            "Auction versus auction_q, grouped by scenario.",
            right_html=components.badge("30 seeds per cell", tone="accent"),
        )
        st.plotly_chart(
            charts.rule_vs_q_delta_figure(raw),
            width="stretch",
            theme=None,
            config=theme.PLOTLY_CONFIG,
        )
        if not frame.empty:
            st.dataframe(
                frame,
                width="stretch",
                hide_index=True,
                column_config={
                    "scenario": st.column_config.TextColumn("Scenario"),
                    "Rule cost": st.column_config.NumberColumn("Rule cost", format="%.0f"),
                    "Q cost": st.column_config.NumberColumn("Q cost", format="%.0f"),
                    "Cost Δ": st.column_config.TextColumn("Cost Δ"),
                    "Rule UE": st.column_config.NumberColumn("Rule UE (MWh)", format="%.1f"),
                    "Q UE": st.column_config.NumberColumn("Q UE (MWh)", format="%.1f"),
                    "UE Δ": st.column_config.TextColumn("UE Δ"),
                    "Q cycles": st.column_config.NumberColumn("Q cycles", format="%.2f"),
                },
            )
        st.caption(
            "Positive Δ means the learned policy is higher than the rule-based policy. "
            "These are paired saved results, not a new training run."
        )


def _fresh_comparison() -> None:
    with st.container(border=True):
        components.card_header(
            "Fresh 168-hour comparison",
            "Build both auction models on one scenario and seed, run them to completion "
            "and compute the standard metrics. Nothing is trained here.",
            right_html=components.badge("One seed", tone="warning"),
        )
        columns = st.columns([2, 1])
        scenario = columns[0].selectbox(
            "Scenario",
            OFFICIAL_SCENARIOS,
            index=OFFICIAL_SCENARIOS.index(st.session_state.get("ui_scenario", "normal"))
            if st.session_state.get("ui_scenario") in OFFICIAL_SCENARIOS
            else 0,
            format_func=data.scenario_label,
            key="learning_compare_scenario",
        )
        seed = int(st.session_state.get("ui_seed", 0))
        columns[1].metric("Seed", seed)
        run = st.button(
            "Run 168-hour comparison",
            key="learning_compare_run",
            type="primary",
            width="stretch",
        )
        if run:
            config = load_config()
            rows: list[dict[str, Any]] = []
            progress = st.progress(0.0, text="Running auction and auction_q...")
            try:
                for index, system in enumerate(("auction", "auction_q"), start=1):
                    model = build_model(config, seed, system, scenario)
                    while not model.clock.is_finished:
                        model.step()
                    metrics = compute_run_metrics(model.logger.get_log(), config, scenario)
                    rows.append({"system": system, **metrics})
                    progress.progress(index / 2, text=f"Completed {data.system_label(system)}")
            except Exception as exc:  # noqa: BLE001 - surface backend failures in the UI
                components.error_state(
                    "The comparison could not finish",
                    f"{type(exc).__name__}: {exc}",
                )
                return
            st.session_state["gm_learning_compare"] = {
                "scenario": scenario,
                "seed": seed,
                "rows": rows,
            }
        saved = st.session_state.get("gm_learning_compare")
        if saved:
            frame = pd.DataFrame(saved["rows"])
            columns_present = [column for column in FRESH_COLUMNS if column in frame]
            view = frame[columns_present].copy()
            if "system" in view:
                view["system"] = view["system"].map(data.system_label)
            st.caption(
                f"Scenario {data.scenario_label(str(saved['scenario']))} · seed {saved['seed']} · "
                "both runs completed 168 hours."
            )
            st.dataframe(
                view,
                width="stretch",
                hide_index=True,
                column_config={
                    "system": st.column_config.TextColumn("System"),
                    "social_cost": st.column_config.NumberColumn("Social cost", format="%.0f"),
                    "ue_total": st.column_config.NumberColumn("UE (MWh)", format="%.2f"),
                    "recovery_time": st.column_config.NumberColumn("Recovery (h)", format="%.1f"),
                    "renewable_share": st.column_config.NumberColumn("Renewable", format="percent"),
                    "storage_cycles": st.column_config.NumberColumn("Cycles", format="%.2f"),
                },
            )
            st.caption(
                "This one-seed diagnostic uses the persisted Q-table; the 600-run grid in "
                "Compare remains the statistical evidence."
            )


def _artefacts_tab(tab: Any, metadata: Mapping[str, Any] | None) -> None:
    with tab:
        if not metadata:
            components.empty_state(
                "No training metadata",
                "results/training_metadata.json is missing.",
                hint="Run: python -m ai.train",
                icon="database",
            )
        else:
            with st.container(border=True):
                components.card_header(
                    "Training metadata",
                    "The exact hyperparameters persisted by ai.train.",
                )
                components.definition_grid(
                    [
                        ("Episodes", f"{int(metadata.get('episodes', 0)):,}"),
                        ("Training seed", str(metadata.get("seed", "—"))),
                        ("Learning rate α", f"{float(metadata.get('alpha', 0.0)):.2f}"),
                        ("Discount γ", f"{float(metadata.get('gamma', 0.0)):.2f}"),
                        ("Epsilon start", f"{float(metadata.get('epsilon_start', 0.0)):.2f}"),
                        ("Epsilon end", f"{float(metadata.get('epsilon_end', 0.0)):.2f}"),
                        ("Decay episodes", str(metadata.get("epsilon_decay_episodes", "—"))),
                        ("Q-table shape", str(tuple(metadata.get("qtable_shape", ())) or "—")),
                        ("Final mean reward", components.fmt_number(metadata.get("final_mean_reward"), 3)),
                    ]
                )
                with st.expander("Raw metadata JSON", expanded=False):
                    st.json(metadata)

        figures = [
            (data.FIGURES_DIR / "fig4_learning_curve.png", "Learning curve"),
            (data.FIGURES_DIR / "fig5_qtable_heatmap.png", "Static Q-table heatmap"),
        ]
        available = [(path, caption) for path, caption in figures if path.exists()]
        if not available:
            components.empty_state(
                "No static learning figures",
                "The report's learning figures have not been generated.",
                hint="Run: python -m experiments.runner --seeds 30",
                icon="database",
            )
            return
        with st.container(key="gm-pair-learning-figures"):
            columns = st.columns(len(available))
            for column, (path, caption) in zip(columns, available):
                with column:
                    st.image(str(path), caption=caption, width="stretch")


def render() -> None:
    """Render the Learning page."""

    try:
        metadata = data.load_training_metadata()
        curve = data.load_learning_curve()
        qtable = data.load_qtable()
    except data.DataError as exc:
        _header()
        components.error_state(
            "Learning artefacts are unavailable",
            str(exc),
            hint="Run: python -m ai.train",
        )
        return

    _header(metadata, qtable)
    _kpis(metadata, curve, qtable)

    with st.container(border=True):
        components.card_header(
            "Learning curve",
            "Reward, temporal-difference error and exploration across training.",
            right_html=components.badge(
                f"{len(curve):,} checkpoints" if curve is not None and not curve.empty else "No curve"
            ),
        )
        if curve is None or curve.empty:
            components.empty_state(
                "No learning curve",
                "results/learning_curve.csv is missing or empty.",
                hint="Run: python -m ai.train",
                icon="database",
            )
        else:
            st.plotly_chart(
                charts.learning_curve_figure(curve, metadata),
                width="stretch",
                theme=None,
                config=theme.PLOTLY_CONFIG,
            )

    tabs = st.tabs(["Policy explorer", "Rule vs Q", "Training artefacts"])
    _policy_tab(tabs[0], metadata, qtable)
    with tabs[1]:
        _saved_evidence()
        _fresh_comparison()
    _artefacts_tab(tabs[2], metadata)
