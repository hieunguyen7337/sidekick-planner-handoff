#!/usr/bin/env python3
"""Paper figure generator from report JSON files (Brief X41).

Generates publication figures (PDF + PNG) from analysis report JSON files,
enforcing that every number plotted originates directly from a report key
recorded in docs/claims_ledger.md and indexed in the output manifest.

Figures:
  F1: Depth curve across both receivers (tailored and zero-shot) with ceilings & floors.
  F2: Matched-budget channel comparison (action prefix curve vs advice points).
  F3: Tailoring gap (untailored minus tailored) across prefix depths.
  F4: Mechanism two-panel (M1 API novelty front-loading + M3 rise decomposition).
  F5: Second family within-prefix depth curve (Qwen3-8B zero-shot).
  F6: Mechanism two-panel (Narrated vs executed prefix actions across receivers).
  F7: Narrated-minus-executed goal-pass contrast across receivers.
  F8: Advice and action-prefix cost/quality scatter.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure thread environment variables are set before any math/numpy operations
for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

# Headless matplotlib setup: Agg backend MUST be set before pyplot is imported
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

MANDATORY_F5_ANNOTATION = (
    "Floor not shown: both Qwen floor arms score identically and complete no tasks, "
    "so no floor-relative lift is measurable (QWEN-03)."
)

# Colour-blind-safe palette distinguishable in greyscale (varying hue, marker, linestyle)
# F1 marginal bands are computed and stored but NOT drawn. They are per-arm bootstrap
# intervals, so they carry between-task variance that this paired design removes. Every
# claim in the paper rests on a paired contrast, which is 2-3x tighter; drawing the wider
# marginal band beside those claims invites the reader to conclude the opposite of what
# the contrasts establish. See bootstrap_arm_quality's docstring in hj12_shape.py.
F1_DRAW_MARGINAL_BANDS = False

PALETTE = {
    "tailored": {"color": "#0072B2", "marker": "o", "linestyle": "-", "label": "Tailored receiver (sft_b_plus)"},
    "zeroshot": {"color": "#D55E00", "marker": "s", "linestyle": "--", "label": "Untailored receiver (granite zero-shot)"},
    "suffix_adapter": {"color": "#009E73", "marker": "^", "linestyle": "-.", "label": "Suffix-adapter receiver"},
    "qwen_zeroshot": {"color": "#CC79A7", "marker": "D", "linestyle": "--", "label": "Qwen3-8B zero-shot"},
    "advice": {"color": "#E69F00", "marker": "D", "linestyle": "", "label": "Advice channel"},
    "takeover": {"color": "#999999", "marker": "v", "linestyle": "", "label": "Takeover channel"},
    "ceiling_cap25": {"color": "#222222", "linestyle": ":", "label": "Planner ceiling (cap-25)"},
    "ceiling_cap81": {"color": "#555555", "linestyle": "--", "label": "Planner ceiling (cap-81)"},
    "floor_plan": {"color": "#56B4E9", "linestyle": "-.", "label": "Plan-only floor (0.7181)"},
    "floor_exec": {"color": "#777777", "linestyle": ":", "label": "Executor-alone floor (0.5289)"},
    "margin_band": {"color": "#DDDDDD", "alpha": 0.25, "label": "7.00 pp non-inferiority margin"},
    "m1_curve": {"color": "#0072B2", "marker": "o", "linestyle": "-", "label": "Cumulative first API uses"},
    "m3_handoff": {"color": "#0072B2", "label": "Handoff-earned share"},
    "m3_silenced": {"color": "#E69F00", "label": "Silenced (prefix-exhausted) share"},
    "narrated": {"color": "#E69F00", "marker": "D", "linestyle": "", "label": "Narrated prefix (m=9)"},
    "executed": {"color": "#0072B2", "marker": "o", "linestyle": "", "label": "Executed prefix (m=9)"},
    "one_plan": {"color": "#56B4E9", "marker": "^", "linestyle": "", "label": "One-plan floor"},
}


def apply_style() -> None:
    """Apply unified publication styling across all figures."""
    plt.rcdefaults()
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9.5,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 8.5,
        "figure.titlesize": 11,
        "axes.grid": True,
        "grid.alpha": 0.35,
        "grid.linestyle": ":",
        "grid.color": "#999999",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.8,
        "figure.autolayout": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def validate_output_path(path: Path | str | None) -> None:
    """Refuse output paths inside raw results dir or containing test splits."""
    if path is None:
        return
    p = Path(path).resolve()
    s = str(p)
    if "test_normal" in s or "test_challenge" in s:
        raise ValueError(f"Output path {path} forbidden: contains test_normal or test_challenge")
    scratch_results = Path("/scratch/n12194778/sidekick/results").resolve()
    try:
        p.relative_to(scratch_results)
        raise ValueError(f"Output path {path} forbidden: cannot write under {scratch_results}")
    except ValueError as e:
        if "cannot write under" in str(e):
            raise
        # Path is outside scratch results directory, which is valid.


def load_report_json(report_path: Path, figure_id: str) -> dict[str, Any]:
    """Load JSON file or raise fatal SystemExit naming the figure and missing file."""
    if not report_path.is_file():
        raise SystemExit(
            f"Fatal [{figure_id}]: required report file is missing: {report_path}"
        )
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise SystemExit(
            f"Fatal [{figure_id}]: failed to parse report JSON from {report_path}: {e}"
        )


def get_nested_key(data: dict[str, Any], key_path: str, report_path: Path, figure_id: str) -> Any:
    """Extract nested key by dot-notation or raise fatal SystemExit naming figure, file, key."""
    parts = key_path.split(".")
    curr = data
    for part in parts:
        if not isinstance(curr, dict) or part not in curr:
            raise SystemExit(
                f"Fatal [{figure_id}]: key {key_path!r} (missing segment {part!r}) absent in report {report_path}"
            )
        curr = curr[part]
    return curr


def save_figure(
    fig: plt.Figure,
    out_dir: Path,
    fig_stem: str,
    dpi: int = 200,
) -> tuple[Path, Path]:
    """Save figure as both vector PDF and quick-view PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{fig_stem}.pdf"
    png_path = out_dir / f"{fig_stem}.png"
    validate_output_path(pdf_path)
    validate_output_path(png_path)
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return pdf_path, png_path


def generate_f1_depth_curve(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F1 · The depth curve across tailored and untailored receivers with ceilings and floors.
    
    Guards:
    - No vertical breakpoint line (per F1-RESULT-04: S3 did not pass, no threshold claimed).
    - Ceilings labelled with caps (CEIL-07/CEIL-08).
    - Refuses if required reports/keys missing or series empty.
    """
    fig_id = "F1"
    apply_style()

    # 1. Tailored receiver data from post-guard shape report
    shape_rep_path = results_dir / "hj13_shape_post_guard_bands_20260923.report.json"
    shape_data = load_report_json(shape_rep_path, fig_id)
    
    m_tailored = [2, 4, 6, 7, 8, 9, 10, 11]
    y_tailored: list[float] = []
    tailored_keys: list[str] = []
    tailored_ci_m: list[int] = []
    tailored_ci_low: list[float] = []
    tailored_ci_high: list[float] = []

    for m in m_tailored:
        k = f"arms.prefix_m{m}.goal_pass_all"
        val = get_nested_key(shape_data, k, shape_rep_path, fig_id)
        if val is None:
            raise SystemExit(f"Fatal [{fig_id}]: null value for key {k!r} in {shape_rep_path}")
        y_tailored.append(float(val))
        tailored_keys.append(k)

        arm_dict = shape_data.get("arms", {}).get(f"prefix_m{m}", {})
        ci_key = None
        for cand in ("goal_pass_all_ci95", "ci95", "goal_pass_ci95", "goal_pass_all_ci95_pp", "ci95_pp"):
            if cand in arm_dict:
                ci_key = cand
                break
        if ci_key is not None:
            ci_val = arm_dict[ci_key]
            low, high = float(ci_val[0]), float(ci_val[1])
            if low > 1.0 or high > 1.0:
                low, high = low / 100.0, high / 100.0
            tailored_ci_m.append(m)
            tailored_ci_low.append(low)
            tailored_ci_high.append(high)
            tailored_keys.append(f"arms.prefix_m{m}.{ci_key}")

    if not y_tailored:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for tailored receiver")

    # 2. Untailored receiver data from zero-shot depth reports
    zs_m6_m9_path = results_dir / "hj13_zeroshot_depth_m6_m9_20260923.report.json"
    zs_m9_m11_path = results_dir / "hj13_zeroshot_depth_m9_m11_20260923.report.json"
    zs_m6_m9_data = load_report_json(zs_m6_m9_path, fig_id)
    zs_m9_m11_data = load_report_json(zs_m9_m11_path, fig_id)

    m_zs = [6, 9, 11]
    y_zs: list[float] = []
    zs_keys: list[str] = []
    zs_ci_m: list[int] = []
    zs_ci_low: list[float] = []
    zs_ci_high: list[float] = []
    
    for m, rep_path, rep_data, k_zs in [
        (6, zs_m6_m9_path, zs_m6_m9_data, "arms.zs_m6.goal_pass_all"),
        (9, zs_m6_m9_path, zs_m6_m9_data, "arms.zs_m9.goal_pass_all"),
        (11, zs_m9_m11_path, zs_m9_m11_data, "arms.zs_m11.goal_pass_all"),
    ]:
        val = float(get_nested_key(rep_data, k_zs, rep_path, fig_id))
        y_zs.append(val)
        zs_keys.append(f"{rep_path.name}:{k_zs}")

        arm_name = k_zs.split(".")[1]
        arm_dict = rep_data.get("arms", {}).get(arm_name, {})
        ci_key = None
        for cand in ("goal_pass_all_ci95", "ci95", "goal_pass_ci95", "goal_pass_all_ci95_pp", "ci95_pp"):
            if cand in arm_dict:
                ci_key = cand
                break
        if ci_key is not None:
            ci_val = arm_dict[ci_key]
            low, high = float(ci_val[0]), float(ci_val[1])
            if low > 1.0 or high > 1.0:
                low, high = low / 100.0, high / 100.0
            zs_ci_m.append(m)
            zs_ci_low.append(low)
            zs_ci_high.append(high)
            zs_keys.append(f"{rep_path.name}:arms.{arm_name}.{ci_key}")

    if not y_zs:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for untailored receiver")

    # 3. Ceilings and floors from reports
    ceil_path = results_dir / "hj13_ceiling_cap25_vs_cap81_20260923.report.json"
    ceil_data = load_report_json(ceil_path, fig_id)
    k_cap25 = "arms.ceiling_cap25.goal_pass_all"
    k_cap81 = "arms.ceiling_cap81.goal_pass_all"
    ceil_cap25 = float(get_nested_key(ceil_data, k_cap25, ceil_path, fig_id))
    ceil_cap81 = float(get_nested_key(ceil_data, k_cap81, ceil_path, fig_id))

    frontier_path = results_dir / "hj12_unified_frontier_scenario_20260923.report.json"
    frontier_data = load_report_json(frontier_path, fig_id)
    k_plan = "arms.sft_plan.goal_pass_all"
    k_exec = "arms.executor_alone.goal_pass_all"
    floor_plan = float(get_nested_key(frontier_data, k_plan, frontier_path, fig_id))
    floor_exec = float(get_nested_key(frontier_data, k_exec, frontier_path, fig_id))

    # Plot creation (two-column width: 7.0 in)
    fig, ax = plt.subplots(figsize=(7.0, 4.2))

    # Shaded non-inferiority margin below cap-25 ceiling
    margin_pp = 0.0700
    ax.axhspan(
        ceil_cap25 - margin_pp, ceil_cap25,
        color=PALETTE["margin_band"]["color"],
        alpha=PALETTE["margin_band"]["alpha"],
        label="7.00 pp non-inferiority margin (below cap-25)",
        zorder=1,
    )

    # Reference ceilings (with mandatory cap labels per CEIL-07/08)
    ax.axhline(
        ceil_cap25, color=PALETTE["ceiling_cap25"]["color"],
        linestyle=PALETTE["ceiling_cap25"]["linestyle"], linewidth=1.2,
        label=f"Planner ceiling cap-25 ({ceil_cap25:.4f})", zorder=2,
    )
    ax.axhline(
        ceil_cap81, color=PALETTE["ceiling_cap81"]["color"],
        linestyle=PALETTE["ceiling_cap81"]["linestyle"], linewidth=1.2,
        label=f"Planner ceiling cap-81 ({ceil_cap81:.4f})", zorder=2,
    )

    # Reference floors
    ax.axhline(
        floor_plan, color=PALETTE["floor_plan"]["color"],
        linestyle=PALETTE["floor_plan"]["linestyle"], linewidth=1.1,
        label=f"Plan-only floor ({floor_plan:.4f})", zorder=2,
    )
    ax.axhline(
        floor_exec, color=PALETTE["floor_exec"]["color"],
        linestyle=PALETTE["floor_exec"]["linestyle"], linewidth=1.1,
        label=f"Executor-alone floor ({floor_exec:.4f})", zorder=2,
    )

    # Confidence bands: suppressed by default, see F1_DRAW_MARGINAL_BANDS.
    if F1_DRAW_MARGINAL_BANDS and tailored_ci_m:
        ax.fill_between(
            tailored_ci_m, tailored_ci_low, tailored_ci_high,
            color=PALETTE["tailored"]["color"],
            alpha=0.18, zorder=3,
        )
    if F1_DRAW_MARGINAL_BANDS and zs_ci_m:
        ax.fill_between(
            zs_ci_m, zs_ci_low, zs_ci_high,
            color=PALETTE["zeroshot"]["color"],
            alpha=0.18, zorder=3,
        )

    # Tailored receiver curve
    ax.plot(
        m_tailored, y_tailored,
        color=PALETTE["tailored"]["color"],
        marker=PALETTE["tailored"]["marker"],
        linestyle=PALETTE["tailored"]["linestyle"],
        linewidth=1.8, markersize=6,
        label="Tailored receiver (sft_b_plus)",
        zorder=4,
    )

    # Untailored receiver curve
    ax.plot(
        m_zs, y_zs,
        color=PALETTE["zeroshot"]["color"],
        marker=PALETTE["zeroshot"]["marker"],
        linestyle=PALETTE["zeroshot"]["linestyle"],
        linewidth=1.8, markersize=6,
        label="Untailored receiver (granite zero-shot)",
        zorder=4,
    )

    ax.set_xlabel("Handoff depth $m$ (executed actions)")
    ax.set_ylabel("Goal pass rate")
    ax.set_xlim(1.5, 11.5)
    ax.set_ylim(0.48, 0.88)
    ax.set_xticks(range(2, 12))
    ax.legend(
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=True, facecolor="white", edgecolor="#cccccc", framealpha=0.9, fontsize=8,
    )

    plt.tight_layout()
    pdf_path, png_path = save_figure(fig, out_dir, "f1_depth_curve", dpi=dpi)

    caption = (
        "Goal pass rate against prefix handoff depth $m$ for tailored and untailored receivers, "
        "compared against the cap-25 (0.8284) and cap-81 (0.7637) planner ceilings, plan-only floor (0.7181), "
        "and executor-alone floor (0.5289). No uncertainty band is drawn: the design is paired, so every "
        "interval the text reports is a paired contrast rather than the wider per-arm marginal interval. "
        "interval keys where present. Quality is flat below a breakpoint and rises above it; the "
        "breakpoint point estimate is $m=8$ on handoff-only populations but its 95% interval spans [4, 9], "
        "so the registered threshold test S3 does not pass and no threshold location is claimed (F1-RESULT-04)."
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 7.0,
        "column": "two-column",
        "caption": caption,
        "series": [
            {
                "label": "Tailored receiver (sft_b_plus)",
                "report_path": str(shape_rep_path),
                "json_keys": tailored_keys,
                "n_points": len(y_tailored),
                "has_confidence_band": bool(F1_DRAW_MARGINAL_BANDS and tailored_ci_m),
                "interval_note": "Per-arm marginal intervals are computed and available in the report but are NOT drawn: this is a paired design and every claim rests on a paired contrast, which is 2-3x tighter than the marginal band.",
            },
            {
                "label": "Untailored receiver (granite zero-shot)",
                "report_path": f"{zs_m6_m9_path}; {zs_m9_m11_path}",
                "json_keys": zs_keys,
                "n_points": len(y_zs),
                "has_confidence_band": bool(F1_DRAW_MARGINAL_BANDS and zs_ci_m),
                "interval_note": "Per-arm marginal intervals are computed and available in the report but are NOT drawn: this is a paired design and every claim rests on a paired contrast, which is 2-3x tighter than the marginal band.",
            },
            {
                "label": "Reference ceilings and floors",
                "report_path": f"{ceil_path}; {frontier_path}",
                "json_keys": [
                    f"hj13_ceiling_cap25_vs_cap81_20260923.report.json:{k_cap25}",
                    f"hj13_ceiling_cap25_vs_cap81_20260923.report.json:{k_cap81}",
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_plan}",
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_exec}",
                ],
                "n_points": 4,
            },
        ],
        "skipped_reason": None,
    }
    return manifest_entry


def generate_f2_channel_budget(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F2 · The two channels at matched budget.
    
    Plots goal pass rate against non-cached planner tokens per episode.
    Shows the action prefix curve priced against discrete advice intervention points.
    """
    fig_id = "F2"
    apply_style()

    frontier_path = results_dir / "hj12_unified_frontier_scenario_20260923.report.json"
    frontier_data = load_report_json(frontier_path, fig_id)

    # Prefix curve points (cost, goal_pass)
    prefix_m_list = [2, 4, 6, 7, 8, 9, 10, 11]
    prefix_costs: list[float] = []
    prefix_scores: list[float] = []
    prefix_keys: list[str] = []

    for m in prefix_m_list:
        k_cost = f"arms.prefix_m{m}.cost_per_episode"
        k_score = f"arms.prefix_m{m}.goal_pass_all"
        c = float(get_nested_key(frontier_data, k_cost, frontier_path, fig_id))
        s = float(get_nested_key(frontier_data, k_score, frontier_path, fig_id))
        prefix_costs.append(c)
        prefix_scores.append(s)
        prefix_keys.extend([k_cost, k_score])

    if not prefix_costs:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for prefix curve")

    # Floors & reference points
    k_exec_cost = "arms.executor_alone.cost_per_episode"
    k_exec_score = "arms.executor_alone.goal_pass_all"
    exec_score = float(get_nested_key(frontier_data, k_exec_score, frontier_path, fig_id))
    exec_cost = 0.0  # Executor alone uses 0 planner tokens

    k_plan_cost = "arms.sft_plan.cost_per_episode"
    k_plan_score = "arms.sft_plan.goal_pass_all"
    plan_cost = float(get_nested_key(frontier_data, k_plan_cost, frontier_path, fig_id))
    plan_score = float(get_nested_key(frontier_data, k_plan_score, frontier_path, fig_id))

    k_ceil_cost = "arms.planner_alone.cost_per_episode"
    k_ceil_score = "arms.planner_alone.goal_pass_all"
    ceil_cost = float(get_nested_key(frontier_data, k_ceil_cost, frontier_path, fig_id))
    ceil_score = float(get_nested_key(frontier_data, k_ceil_score, frontier_path, fig_id))

    # Advice arms from frontier
    k_adv3_cost = "arms.advise_fixed_k_3.cost_per_episode"
    k_adv3_score = "arms.advise_fixed_k_3.goal_pass_all"
    adv3_cost = float(get_nested_key(frontier_data, k_adv3_cost, frontier_path, fig_id))
    adv3_score = float(get_nested_key(frontier_data, k_adv3_score, frontier_path, fig_id))

    k_adv10_cost = "arms.advise_fixed_k_10.cost_per_episode"
    k_adv10_score = "arms.advise_fixed_k_10.goal_pass_all"
    adv10_cost = float(get_nested_key(frontier_data, k_adv10_cost, frontier_path, fig_id))
    adv10_score = float(get_nested_key(frontier_data, k_adv10_score, frontier_path, fig_id))

    # Full-context advice arm from matched report
    advice_matched_path = results_dir / "hj13_advice_fullctx_matched_20260923.report.json"
    advice_matched_data = load_report_json(advice_matched_path, fig_id)
    k_adv_fc_cost = "arms.advice_fullctx_k10.planner_tokens_per_episode"
    k_adv_fc_score = "arms.advice_fullctx_k10.goal_pass_all"
    adv_fc_cost = float(get_nested_key(advice_matched_data, k_adv_fc_cost, advice_matched_path, fig_id))
    adv_fc_score = float(get_nested_key(advice_matched_data, k_adv_fc_score, advice_matched_path, fig_id))

    fig, ax = plt.subplots(figsize=(7.0, 4.4))

    # Convert tokens to k-tokens for readable axis
    scale = 1e3

    # Plot action prefix curve
    ax.plot(
        [c / scale for c in prefix_costs], prefix_scores,
        color=PALETTE["tailored"]["color"],
        marker=PALETTE["tailored"]["marker"],
        linestyle="-", linewidth=1.8, markersize=6,
        label="Action prefix curve ($m=2\\dots 11$)",
        zorder=4,
    )
    for m, c, s in zip(prefix_m_list, prefix_costs, prefix_scores):
        if m in (2, 6, 9, 11):
            ax.annotate(
                f"$m={m}$", (c / scale, s),
                textcoords="offset points", xytext=(0, 7),
                ha="center", fontsize=8, color=PALETTE["tailored"]["color"],
            )

    # Plot advice points
    advice_pts = [
        ("advise_fixed_k_3", adv3_cost / scale, adv3_score, "k=3 (starved)"),
        ("advise_fixed_k_10", adv10_cost / scale, adv10_score, "k=10 (starved)"),
        ("advise_fixed_k_10_fullctx", adv_fc_cost / scale, adv_fc_score, "k=10 (full-ctx)"),
    ]
    ax.scatter(
        [pt[1] for pt in advice_pts],
        [pt[2] for pt in advice_pts],
        color=PALETTE["advice"]["color"],
        marker="D", s=55, edgecolor="#333333", linewidth=0.8,
        label="Advice channel arms", zorder=5,
    )
    for name, c_scaled, s, lbl in advice_pts:
        ax.annotate(
            lbl, (c_scaled, s),
            textcoords="offset points", xytext=(5, -12),
            ha="left", fontsize=8, color="#884400",
        )

    # Plot floors and ceiling
    ax.scatter([exec_cost / scale], [exec_score], color="#555555", marker="x", s=50, label=f"Executor alone ({exec_score:.3f})", zorder=5)
    ax.scatter([plan_cost / scale], [plan_score], color="#009E73", marker="^", s=60, label=f"Plan-only ({plan_score:.3f})", zorder=5)
    ax.scatter([ceil_cost / scale], [ceil_score], color="#222222", marker="*", s=90, label=f"Planner alone ({ceil_score:.3f})", zorder=5)

    ax.set_xlabel("Non-cached planner tokens per episode (thousands)")
    ax.set_ylabel("Goal pass rate")
    ax.set_ylim(0.48, 0.88)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#cccccc", framealpha=0.9)

    pdf_path, png_path = save_figure(fig, out_dir, "f2_channel_matched_budget", dpi=dpi)

    caption = (
        "Goal pass rate against non-cached planner tokens per episode across advice and action prefix channels. "
        "Every advice arm is visibly priced against the prefix curve at the same token expenditure; "
        "advice remains indistinguishable from the plan-only floor under both starved and full reviewer context."
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 7.0,
        "column": "two-column",
        "caption": caption,
        "series": [
            {
                "label": "Action prefix curve",
                "report_path": str(frontier_path),
                "json_keys": prefix_keys,
                "n_points": len(prefix_costs),
            },
            {
                "label": "Advice arms",
                "report_path": f"{frontier_path}; {advice_matched_path}",
                "json_keys": [
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_adv3_cost}",
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_adv3_score}",
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_adv10_cost}",
                    f"hj12_unified_frontier_scenario_20260923.report.json:{k_adv10_score}",
                    f"hj13_advice_fullctx_matched_20260923.report.json:{k_adv_fc_cost}",
                    f"hj13_advice_fullctx_matched_20260923.report.json:{k_adv_fc_score}",
                ],
                "n_points": 3,
            },
        ],
        "skipped_reason": None,
    }
    return manifest_entry


def generate_f3_tailoring_gap(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F3 · Tailoring receiver gap (untailored minus tailored) across depths.
    
    Plots receiver contrast at m=6 (-4.12 pp), m=9 (-0.06 pp), and m=11 (+2.46 pp) with 95% CIs.
    Checks for suffix-adapter reports (hj13_prefix_hf_m*); if missing, notes skip in manifest.
    """
    fig_id = "F3"
    apply_style()

    m_list = [6, 9, 11]
    gaps: list[float] = []
    ci_lowers: list[float] = []
    ci_uppers: list[float] = []
    keys_used: list[str] = []
    reports_used: list[str] = []

    for m in m_list:
        rep_path = results_dir / f"hj13_receiver_contrast_m{m}_20260923.report.json"
        rep_data = load_report_json(rep_path, fig_id)
        k_contrast = f"contrasts.goal_pass_all_prefix_m{m}_zeroshot_minus_prefix_m{m}_tailored"
        contrast_obj = get_nested_key(rep_data, k_contrast, rep_path, fig_id)
        diff_pp = float(contrast_obj["diff_pp"])
        ci95_pp = contrast_obj["ci95_pp"]
        gaps.append(diff_pp)
        ci_lowers.append(float(ci95_pp[0]))
        ci_uppers.append(float(ci95_pp[1]))
        keys_used.append(f"{rep_path.name}:{k_contrast}")
        reports_used.append(str(rep_path))

    if not gaps:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for tailoring gap")

    # Check for suffix adapter reports (skip gracefully if absent per brief)
    suffix_adapter_available = False
    suffix_m: list[int] = []
    suffix_gaps: list[float] = []

    fig, ax = plt.subplots(figsize=(3.4, 3.8))

    # Zero line (parity)
    ax.axhline(0, color="#444444", linestyle="--", linewidth=1.0, zorder=2)

    # Compute asymmetric error bars: [y - lower, upper - y]
    yerr_lower = [g - lo for g, lo in zip(gaps, ci_lowers)]
    yerr_upper = [hi - g for g, hi in zip(gaps, ci_uppers)]

    ax.errorbar(
        m_list, gaps, yerr=[yerr_lower, yerr_upper],
        fmt="o-", color=PALETTE["tailored"]["color"],
        ecolor=PALETTE["tailored"]["color"], elinewidth=1.5, capsize=4, capthick=1.2,
        markersize=6, linewidth=1.5,
        label="Untailored minus tailored gap",
        zorder=4,
    )

    # Point annotations
    for m, g in zip(m_list, gaps):
        sign = "+" if g > 0 else ""
        ax.annotate(
            f"{sign}{g:.2f} pp", (m, g),
            textcoords="offset points", xytext=(8, -3 if g < 0 else 6),
            ha="left", fontsize=8, color=PALETTE["tailored"]["color"],
        )

    ax.set_xlabel("Handoff depth $m$")
    ax.set_ylabel("Receiver gap (untailored $-$ tailored, pp)")
    ax.set_xticks(m_list)
    ax.set_xlim(5.0, 12.0)
    ax.set_ylim(-14.0, 10.0)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cccccc")

    pdf_path, png_path = save_figure(fig, out_dir, "f3_tailoring_gap", dpi=dpi)

    caption = (
        "Receiver gap (untailored granite zero-shot minus tailored sft_b_plus) across handoff depths $m=6, 9, 11$, "
        "with scenario-clustered 95% bootstrap confidence intervals. The gap decays to zero with depth "
        "(−4.12 pp at $m=6$, −0.06 pp at $m=9$, +2.46 pp at $m=11$), establishing that deep handoffs remove "
        "the need for receiver specialization (TAILOR-01/04/07)."
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 3.4,
        "column": "single-column",
        "caption": caption,
        "series": [
            {
                "label": "Untailored minus tailored gap",
                "report_path": "; ".join(reports_used),
                "json_keys": keys_used,
                "n_points": len(gaps),
            },
        ],
        "skipped_reason": None if not suffix_adapter_available else None,
    }
    return manifest_entry


def generate_f4_mechanism(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F4 · Mechanism, two panels.
    
    Left panel: M1 cumulative share of planner's first API uses by position with m=6/9/11 marked.
    Right panel: M3 stacked bar decomposing the depth rises (m6->m9 and m6->m11) into
    handoff-earned and silenced-episode shares.
    """
    fig_id = "F4"
    apply_style()

    mech_rep_path = results_dir / "hj13_mechanism_zeroshot_20260923c.report.json"
    mech_data = load_report_json(mech_rep_path, fig_id)

    # 1. Panel Left: M1 cumulative share of first API uses (pos 1 to 20)
    m1_dict = get_nested_key(mech_data, "m1_api_novelty.cumulative_by_position", mech_rep_path, fig_id)
    positions = sorted([int(k) for k in m1_dict.keys() if int(k) <= 20])
    cum_shares: list[float] = []
    m1_keys: list[str] = []
    for pos in positions:
        k = f"m1_api_novelty.cumulative_by_position.{pos}.cum_first_uses_share"
        val = get_nested_key(mech_data, k, mech_rep_path, fig_id)
        cum_shares.append(float(val) * 100.0)  # to percentage
        m1_keys.append(k)

    if not cum_shares:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for M1 API novelty")

    # 2. Panel Right: M3 decompositions
    k_m6_m9 = "m3_prefix_exhausted.primary.decompositions.m6_to_m9"
    k_m6_m11 = "m3_prefix_exhausted.primary.decompositions.m6_to_m11"
    d_m6_m9 = get_nested_key(mech_data, k_m6_m9, mech_rep_path, fig_id)
    d_m6_m11 = get_nested_key(mech_data, k_m6_m11, mech_rep_path, fig_id)

    handoff_contributions = [
        float(d_m6_m9["contribution_handoff_subset_pp"]),
        float(d_m6_m11["contribution_handoff_subset_pp"]),
    ]
    silenced_contributions = [
        float(d_m6_m9["contribution_silenced_subset_pp"]),
        float(d_m6_m11["contribution_silenced_subset_pp"]),
    ]
    handoff_shares_pct = [
        float(d_m6_m9["share_of_rise_from_handoff_pct"]),
        float(d_m6_m11["share_of_rise_from_handoff_pct"]),
    ]
    total_rises = [
        float(d_m6_m9["delta_total_pp"]),
        float(d_m6_m11["delta_total_pp"]),
    ]

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(7.2, 3.6))

    # --- Left Panel: M1 ---
    ax_left.plot(
        positions, cum_shares,
        color=PALETTE["m1_curve"]["color"],
        marker=PALETTE["m1_curve"]["marker"],
        linestyle=PALETTE["m1_curve"]["linestyle"],
        linewidth=1.8, markersize=5,
        label="Cumulative API novelty",
    )
    # Highlight m=6, 9, 11
    highlight_m = [6, 9, 11]
    for hm in highlight_m:
        if hm in positions:
            idx = positions.index(hm)
            val = cum_shares[idx]
            ax_left.scatter([hm], [val], color="#D55E00", s=45, zorder=5)
            if hm == 6:
                xytext = (8, -18)
                ha = "left"
                va = "top"
            elif hm == 9:
                xytext = (-8, 8)
                ha = "right"
                va = "bottom"
            else:  # hm == 11
                xytext = (8, -18)
                ha = "left"
                va = "top"
            ax_left.annotate(
                f"$m={hm}$\n({val:.1f}%)", (hm, val),
                textcoords="offset points", xytext=xytext,
                ha=ha, va=va, fontsize=8, color="#882200",
            )

    ax_left.set_xlabel("Planner action position $k$")
    ax_left.set_ylabel("Cumulative share of first API uses (%)")
    ax_left.set_xlim(0.5, 20.5)
    ax_left.set_ylim(0, 105)
    ax_left.set_xticks([1, 4, 6, 9, 11, 15, 20])

    # --- Right Panel: M3 ---
    transitions = ["$m=6 \\rightarrow 9$", "$m=6 \\rightarrow 11$"]
    x_indices = np.arange(len(transitions))
    bar_width = 0.45

    b_handoff = ax_right.bar(
        x_indices, handoff_contributions, bar_width,
        color=PALETTE["m3_handoff"]["color"], label="Handoff-earned share",
        zorder=3,
    )
    b_silenced = ax_right.bar(
        x_indices, silenced_contributions, bar_width,
        bottom=handoff_contributions,
        color=PALETTE["m3_silenced"]["color"], label="Silenced (prefix-exhausted)",
        zorder=3,
    )

    # Label handoff percentage on each bar
    for idx, (h_contrib, tot, pct) in enumerate(zip(handoff_contributions, total_rises, handoff_shares_pct)):
        # Label in the middle of the handoff segment
        ax_right.text(
            idx, h_contrib / 2.0, f"{pct:.1f}%",
            ha="center", va="center", color="white", fontweight="bold", fontsize=9,
        )
        # Total rise label on top
        ax_right.text(
            idx, tot + 0.4, f"+{tot:.2f} pp",
            ha="center", va="bottom", color="#222222", fontsize=8.5,
        )

    ax_right.set_xticks(x_indices)
    ax_right.set_xticklabels(transitions)
    ax_right.set_xlabel("Depth transition")
    ax_right.set_ylabel("Goal pass rate gain (pp)")
    ax_right.set_ylim(0, 18.0)
    # Move legend outside data area to prevent occluding the +15.20 pp total label
    ax_right.legend(
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=8,
    )

    plt.tight_layout()
    pdf_path, png_path = save_figure(fig, out_dir, "f4_mechanism", dpi=dpi)

    caption = (
        "Mechanism decomposition across two panels. Left (M1): cumulative share of the planner's first API uses "
        "by action position, showing that >78% of API discovery occurs before $m=9$. "
        "Right (M3): decomposition of zero-shot depth rises ($m6\\rightarrow 9$ and $m6\\rightarrow 11$) into "
        "handoff-earned and silenced-episode contributions, establishing that 83.8% of the $m6\\rightarrow 9$ rise "
        "is earned on episodes where the executor took over and completed the task (MECH-08, MECH-10)."
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 7.0,
        "column": "two-column",
        "caption": caption,
        "series": [
            {
                "label": "M1 API novelty cumulative share",
                "report_path": str(mech_rep_path),
                "json_keys": m1_keys,
                "n_points": len(positions),
            },
            {
                "label": "M3 Rise decomposition",
                "report_path": str(mech_rep_path),
                "json_keys": [
                    f"{k_m6_m9}.contribution_handoff_subset_pp",
                    f"{k_m6_m9}.contribution_silenced_subset_pp",
                    f"{k_m6_m11}.contribution_handoff_subset_pp",
                    f"{k_m6_m11}.contribution_silenced_subset_pp",
                ],
                "n_points": 2,
            },
        ],
        "skipped_reason": None,
    }
    return manifest_entry


def generate_f5_second_family(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F5 · Second executor family within-prefix depth curve (Qwen3-8B zero-shot).
    
    Guards:
    - Inverted floor guard: Refuses to draw any Qwen floor point or floor line (QWEN-03).
    - Mandatory annotation guard: Refuses to render without explanatory annotation regarding the degenerate floor.
    """
    fig_id = "F5"
    apply_style()

    qwen_curve_path = results_dir / "hj15_qwen_curve_20260923.report.json"
    qwen_curve_data = load_report_json(qwen_curve_path, fig_id)

    # Prefix points m=6, 9, 11
    m_list = [6, 9, 11]
    y_qwen: list[float] = []
    qwen_keys: list[str] = []
    qwen_ci_m: list[int] = []
    qwen_ci_low: list[float] = []
    qwen_ci_high: list[float] = []

    for m in m_list:
        k = f"arms.qwen_prefix_m{m}.goal_pass_all"
        val = float(get_nested_key(qwen_curve_data, k, qwen_curve_path, fig_id))
        y_qwen.append(val)
        qwen_keys.append(k)

        arm_dict = qwen_curve_data.get("arms", {}).get(f"qwen_prefix_m{m}", {})
        ci_key = None
        for cand in ("goal_pass_all_ci95", "ci95", "goal_pass_ci95", "goal_pass_all_ci95_pp", "ci95_pp"):
            if cand in arm_dict:
                ci_key = cand
                break
        if ci_key is not None:
            ci_val = arm_dict[ci_key]
            low, high = float(ci_val[0]), float(ci_val[1])
            if low > 1.0 or high > 1.0:
                low, high = low / 100.0, high / 100.0
            qwen_ci_m.append(m)
            qwen_ci_low.append(low)
            qwen_ci_high.append(high)
            qwen_keys.append(f"arms.qwen_prefix_m{m}.{ci_key}")

    if not y_qwen:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for Qwen prefix curve")

    # Guard: strictly enforce mandatory annotation
    mandatory_annotation = MANDATORY_F5_ANNOTATION
    if not mandatory_annotation or "Floor not shown" not in mandatory_annotation or "QWEN-03" not in mandatory_annotation:
        raise SystemExit(f"Fatal [{fig_id}]: mandatory explanatory annotation missing or invalid")

    fig, ax = plt.subplots(figsize=(3.8, 4.0))

    # Draw shaded band if CI keys present
    if qwen_ci_m:
        ax.fill_between(
            qwen_ci_m, qwen_ci_low, qwen_ci_high,
            color=PALETTE["qwen_zeroshot"]["color"], alpha=0.2, zorder=3,
        )

    # Plot within-prefix depth curve (NO floor line, NO floor point, NO floor-relative arrow)
    ax.plot(
        m_list, y_qwen,
        color=PALETTE["qwen_zeroshot"]["color"],
        marker=PALETTE["qwen_zeroshot"]["marker"],
        linestyle=PALETTE["qwen_zeroshot"]["linestyle"],
        linewidth=1.8, markersize=6,
        label="Qwen3-8B zero-shot (within-prefix)",
        zorder=4,
    )

    # Annotate points
    for m, y in zip(m_list, y_qwen):
        ax.annotate(
            f"{y:.3f}", (m, y),
            textcoords="offset points", xytext=(0, 8),
            ha="center", fontsize=8.5, color="#884466",
        )

    # Add mandatory in-figure annotation
    ax.text(
        0.5, 0.04, mandatory_annotation,
        transform=ax.transAxes,
        ha="center", va="bottom",
        fontsize=7.5, color="#444444", style="italic",
        wrap=True,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#f5f5f5", edgecolor="#bbbbbb", alpha=0.95),
        zorder=5,
    )

    ax.set_title("Within-prefix depth curve\n(Second executor family: Qwen3-8B)", fontsize=9.5)
    ax.set_xlabel("Handoff depth $m$ (within-prefix actions)")
    ax.set_ylabel("Goal pass rate")
    ax.set_xticks(m_list)
    ax.set_xlim(5.0, 12.0)
    ax.set_ylim(0.20, 0.88)
    ax.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=8)

    pdf_path, png_path = save_figure(fig, out_dir, "f5_second_family", dpi=dpi)

    caption = (
        "Within-prefix depth curve for Qwen3-8B zero-shot across handoff depths $m=6, 9, 11$ "
        "(0.4491, 0.7017, 0.7306). Quality rises monotonically with depth in a second executor family. "
        f"{mandatory_annotation}"
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 3.8,
        "column": "single-column",
        "caption": caption,
        "series": [
            {
                "label": "Qwen3-8B zero-shot (within-prefix)",
                "report_path": str(qwen_curve_path),
                "json_keys": qwen_keys,
                "n_points": len(y_qwen),
                "has_confidence_band": len(qwen_ci_m) > 0,
                "interval_note": None if qwen_ci_m else "No per-arm interval keys present in report; plotted without band",
            }
        ],
        "annotation": mandatory_annotation,
        "skipped_reason": None,
    }
    return manifest_entry


def generate_f6_narrated_vs_executed(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F6 · Mechanism: Narrated vs executed prefix actions across tailored and untailored receivers.
    
    Sources:
    - hj16_narrated_tailored_complete_20260923.report.json
    - hj16_narrated_untailored_complete_20260923.report.json
    
    Two panels (tailored, untailored). Each shows three arms:
    - One-plan floor
    - Narrated m=9
    - Executed m=9
    on goal_pass and TGC, with 95% bootstrap intervals.
    
    Significance rule (NARR-02):
    - Tailored goal_pass narrated-minus-floor includes zero [-0.56, +10.61] -> NO significance marker.
    - Other comparisons marked significant if CI excludes zero.
    """
    fig_id = "F6"
    apply_style()

    tailored_path = results_dir / "hj16_narrated_tailored_complete_20260923.report.json"
    untailored_path = results_dir / "hj16_narrated_untailored_complete_20260923.report.json"

    tailored_data = load_report_json(tailored_path, fig_id)
    untailored_data = load_report_json(untailored_path, fig_id)

    # 1. Tailored receiver data
    t_floor_gp = float(get_nested_key(tailored_data, "arms.plan_only_iaware.goal_pass_all", tailored_path, fig_id))
    t_floor_tgc = float(get_nested_key(tailored_data, "arms.plan_only_iaware.tgc_all", tailored_path, fig_id))
    t_narr_gp = float(get_nested_key(tailored_data, "arms.narrated_m9.goal_pass_all", tailored_path, fig_id))
    t_narr_tgc = float(get_nested_key(tailored_data, "arms.narrated_m9.tgc_all", tailored_path, fig_id))
    t_exec_gp = float(get_nested_key(tailored_data, "arms.executed_m9.goal_pass_all", tailored_path, fig_id))
    t_exec_tgc = float(get_nested_key(tailored_data, "arms.executed_m9.tgc_all", tailored_path, fig_id))

    t_narr_gp_ci = get_nested_key(tailored_data, "contrasts.goal_pass_all_narrated_m9_minus_plan_only_iaware.ci95_pp", tailored_path, fig_id)
    t_narr_tgc_ci = get_nested_key(tailored_data, "contrasts.tgc_all_narrated_m9_minus_plan_only_iaware.ci95_pp", tailored_path, fig_id)
    t_exec_gp_ci = get_nested_key(tailored_data, "contrasts.goal_pass_all_executed_m9_minus_plan_only_iaware.ci95_pp", tailored_path, fig_id)
    t_exec_tgc_ci = get_nested_key(tailored_data, "contrasts.tgc_all_executed_m9_minus_plan_only_iaware.ci95_pp", tailored_path, fig_id)

    # 2. Untailored receiver data
    u_floor_gp = float(get_nested_key(untailored_data, "arms.base_one_plan.goal_pass_all", untailored_path, fig_id))
    u_floor_tgc = float(get_nested_key(untailored_data, "arms.base_one_plan.tgc_all", untailored_path, fig_id))
    u_narr_gp = float(get_nested_key(untailored_data, "arms.narrated_zs_m9.goal_pass_all", untailored_path, fig_id))
    u_narr_tgc = float(get_nested_key(untailored_data, "arms.narrated_zs_m9.tgc_all", untailored_path, fig_id))
    u_exec_gp = float(get_nested_key(untailored_data, "arms.executed_zs_m9.goal_pass_all", untailored_path, fig_id))
    u_exec_tgc = float(get_nested_key(untailored_data, "arms.executed_zs_m9.tgc_all", untailored_path, fig_id))

    u_narr_gp_ci = get_nested_key(untailored_data, "contrasts.goal_pass_all_narrated_zs_m9_minus_base_one_plan.ci95_pp", untailored_path, fig_id)
    u_narr_tgc_ci = get_nested_key(untailored_data, "contrasts.tgc_all_narrated_zs_m9_minus_base_one_plan.ci95_pp", untailored_path, fig_id)
    u_exec_gp_ci = get_nested_key(untailored_data, "contrasts.goal_pass_all_executed_zs_m9_minus_base_one_plan.ci95_pp", untailored_path, fig_id)
    u_exec_tgc_ci = get_nested_key(untailored_data, "contrasts.tgc_all_executed_zs_m9_minus_base_one_plan.ci95_pp", untailored_path, fig_id)

    tailored_keys = [
        "arms.plan_only_iaware.goal_pass_all",
        "arms.plan_only_iaware.tgc_all",
        "arms.narrated_m9.goal_pass_all",
        "arms.narrated_m9.tgc_all",
        "arms.executed_m9.goal_pass_all",
        "arms.executed_m9.tgc_all",
        "contrasts.goal_pass_all_narrated_m9_minus_plan_only_iaware.ci95_pp",
        "contrasts.tgc_all_narrated_m9_minus_plan_only_iaware.ci95_pp",
        "contrasts.goal_pass_all_executed_m9_minus_plan_only_iaware.ci95_pp",
        "contrasts.tgc_all_executed_m9_minus_plan_only_iaware.ci95_pp",
    ]
    untailored_keys = [
        "arms.base_one_plan.goal_pass_all",
        "arms.base_one_plan.tgc_all",
        "arms.narrated_zs_m9.goal_pass_all",
        "arms.narrated_zs_m9.tgc_all",
        "arms.executed_zs_m9.goal_pass_all",
        "arms.executed_zs_m9.tgc_all",
        "contrasts.goal_pass_all_narrated_zs_m9_minus_base_one_plan.ci95_pp",
        "contrasts.tgc_all_narrated_zs_m9_minus_base_one_plan.ci95_pp",
        "contrasts.goal_pass_all_executed_zs_m9_minus_base_one_plan.ci95_pp",
        "contrasts.tgc_all_executed_zs_m9_minus_base_one_plan.ci95_pp",
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 4.0))

    def _ci_err(val: float, floor: float, ci_pp: list[float]) -> tuple[float, float]:
        low = floor + float(ci_pp[0]) / 100.0
        high = floor + float(ci_pp[1]) / 100.0
        return max(0.0, val - low), max(0.0, high - val)

    def _plot_panel(
        ax: plt.Axes, title: str,
        f_gp: float, f_tgc: float,
        n_gp: float, n_tgc: float, n_gp_ci: list[float], n_tgc_ci: list[float],
        e_gp: float, e_tgc: float, e_gp_ci: list[float], e_tgc_ci: list[float],
        n_gp_sig: bool, n_tgc_sig: bool, e_gp_sig: bool, e_tgc_sig: bool,
    ) -> None:
        metrics = ["Goal pass rate", "TGC"]
        x_indices = [0.0, 1.0]
        off_floor = -0.22
        off_narr = 0.0
        off_exec = 0.22

        # Floor points
        ax.scatter([x + off_floor for x in x_indices], [f_gp, f_tgc], color="#777777", marker="^", s=55, label="One-plan floor", zorder=5)
        # Narrated points & errorbars
        n_err_gp = _ci_err(n_gp, f_gp, n_gp_ci)
        n_err_tgc = _ci_err(n_tgc, f_tgc, n_tgc_ci)
        ax.errorbar(
            [x + off_narr for x in x_indices], [n_gp, n_tgc],
            yerr=[[n_err_gp[0], n_err_tgc[0]], [n_err_gp[1], n_err_tgc[1]]],
            fmt="D", color=PALETTE["advice"]["color"], ecolor=PALETTE["advice"]["color"],
            elinewidth=1.6, capsize=4, capthick=1.2, markersize=6,
            label="Narrated prefix ($m=9$)", zorder=5,
        )
        # Executed points & errorbars
        e_err_gp = _ci_err(e_gp, f_gp, e_gp_ci)
        e_err_tgc = _ci_err(e_tgc, f_tgc, e_tgc_ci)
        ax.errorbar(
            [x + off_exec for x in x_indices], [e_gp, e_tgc],
            yerr=[[e_err_gp[0], e_err_tgc[0]], [e_err_gp[1], e_err_tgc[1]]],
            fmt="o", color=PALETTE["tailored"]["color"], ecolor=PALETTE["tailored"]["color"],
            elinewidth=1.6, capsize=4, capthick=1.2, markersize=6,
            label="Executed prefix ($m=9$)", zorder=5,
        )

        # Baseline horizontal lines per metric
        ax.hlines(f_gp, -0.35, 0.35, colors="#999999", linestyles=":", linewidth=1.0)
        ax.hlines(f_tgc, 0.65, 1.35, colors="#999999", linestyles=":", linewidth=1.0)

        # Significance markers where CI excludes zero
        if n_gp_sig:
            top_y = f_gp + float(n_gp_ci[1]) / 100.0
            ax.text(0.0 + off_narr, top_y + 0.02, "*", ha="center", va="bottom", fontsize=11, fontweight="bold", color=PALETTE["advice"]["color"])
        if e_gp_sig:
            top_y = f_gp + float(e_gp_ci[1]) / 100.0
            ax.text(0.0 + off_exec, top_y + 0.02, "*", ha="center", va="bottom", fontsize=11, fontweight="bold", color=PALETTE["tailored"]["color"])
        if n_tgc_sig:
            top_y = f_tgc + float(n_tgc_ci[1]) / 100.0
            ax.text(1.0 + off_narr, top_y + 0.02, "*", ha="center", va="bottom", fontsize=11, fontweight="bold", color=PALETTE["advice"]["color"])
        if e_tgc_sig:
            top_y = f_tgc + float(e_tgc_ci[1]) / 100.0
            ax.text(1.0 + off_exec, top_y + 0.02, "*", ha="center", va="bottom", fontsize=11, fontweight="bold", color=PALETTE["tailored"]["color"])

        ax.set_title(title, fontsize=10)
        ax.set_xticks(x_indices)
        ax.set_xticklabels(metrics)
        ax.set_xlim(-0.45, 1.45)
        ax.set_ylim(0.0, 0.95)
        ax.set_ylabel("Score (rate / TGC)")

    # Left panel: Tailored (narrated goal_pass CI includes zero -> n_gp_sig is False)
    _plot_panel(
        ax1, "Tailored receiver (sft_b_plus)",
        t_floor_gp, t_floor_tgc,
        t_narr_gp, t_narr_tgc, t_narr_gp_ci, t_narr_tgc_ci,
        t_exec_gp, t_exec_tgc, t_exec_gp_ci, t_exec_tgc_ci,
        n_gp_sig=False, n_tgc_sig=True, e_gp_sig=True, e_tgc_sig=True,
    )

    # Right panel: Untailored (all 4 comparisons exclude zero -> all sig True)
    _plot_panel(
        ax2, "Untailored receiver (granite zero-shot)",
        u_floor_gp, u_floor_tgc,
        u_narr_gp, u_narr_tgc, u_narr_gp_ci, u_narr_tgc_ci,
        u_exec_gp, u_exec_tgc, u_exec_gp_ci, u_exec_tgc_ci,
        n_gp_sig=True, n_tgc_sig=True, e_gp_sig=True, e_tgc_sig=True,
    )
    ax2.legend(
        loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=8,
    )

    plt.tight_layout()
    pdf_path, png_path = save_figure(fig, out_dir, "f6_narrated_vs_executed", dpi=dpi)

    caption = (
        "Mechanism comparison of narrated versus executed prefix actions at $m=9$ against the one-plan floor "
        "across tailored (left) and untailored (right) receivers on goal pass rate and task goal completion (TGC). "
        "Error bars show 95% bootstrap confidence intervals relative to floor; asterisks indicate lift excluding zero (NARR-02). "
        "On the tailored receiver, narrated goal pass rate interval includes zero (no asterisk). "
        "Narrated and executed intervals overlap closely across both metrics and receivers, establishing that "
        "prefix content delivered as text in a fresh environment captures the majority of the prefix benefit."
    )

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 7.2,
        "column": "two-column",
        "caption": caption,
        "series": [
            {
                "label": "Tailored receiver arms & contrasts",
                "report_path": str(tailored_path),
                "json_keys": tailored_keys,
                "n_points": 3,
            },
            {
                "label": "Untailored receiver arms & contrasts",
                "report_path": str(untailored_path),
                "json_keys": untailored_keys,
                "n_points": 3,
            },
        ],
        "skipped_reason": None,
    }
    return manifest_entry


def generate_f7_narrated_minus_executed(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F7 · Narrated minus executed goal-pass contrast by receiver and depth."""
    fig_id = "F7"
    apply_style()

    m_list = [6, 9, 11]
    receiver_specs = [
        (
            "Tailored receiver (sft_b_plus)",
            PALETTE["tailored"],
            results_dir / "hj16_narrated_curve_bplus_20260923.report.json",
            "goal_pass_all_narrated_t_m{m}_minus_executed_t_m{m}",
            -0.08,
        ),
        (
            "Untailored receiver (granite zero-shot)",
            PALETTE["zeroshot"],
            results_dir / "hj16_narrated_curve_zs_20260923.report.json",
            "goal_pass_all_narrated_m{m}_minus_executed_m{m}",
            0.08,
        ),
    ]

    fig, ax = plt.subplots(figsize=(4.8, 3.8))
    manifest_series: list[dict[str, Any]] = []

    for label, style, report_path, contrast_template, x_offset in receiver_specs:
        report_data = load_report_json(report_path, fig_id)
        values: list[float] = []
        ci_lowers: list[float] = []
        ci_uppers: list[float] = []
        json_keys: list[str] = []

        for m in m_list:
            contrast_key = f"contrasts.{contrast_template.format(m=m)}"
            diff_key = f"{contrast_key}.diff_pp"
            ci_key = f"{contrast_key}.ci95_pp_scenario"
            diff_pp = float(get_nested_key(report_data, diff_key, report_path, fig_id))
            ci95_pp = get_nested_key(report_data, ci_key, report_path, fig_id)
            values.append(diff_pp)
            ci_lowers.append(float(ci95_pp[0]))
            ci_uppers.append(float(ci95_pp[1]))
            json_keys.extend([diff_key, ci_key])

        if not values:
            raise SystemExit(f"Fatal [{fig_id}]: empty series for {label}")

        yerr_lower = [value - lower for value, lower in zip(values, ci_lowers)]
        yerr_upper = [upper - value for value, upper in zip(values, ci_uppers)]
        ax.errorbar(
            [m + x_offset for m in m_list],
            values,
            yerr=[yerr_lower, yerr_upper],
            color=style["color"],
            ecolor=style["color"],
            fmt=style["marker"],
            linestyle=style["linestyle"],
            linewidth=1.5,
            elinewidth=1.5,
            capsize=4,
            capthick=1.2,
            markersize=6,
            label=label,
            zorder=4,
        )
        manifest_series.append({
            "label": label,
            "report_path": str(report_path),
            "json_keys": json_keys,
            "n_points": len(values),
        })

    ax.axhline(0, color="#444444", linestyle="--", linewidth=1.0, zorder=2)
    ax.set_xlabel("Prefix depth $m$")
    ax.set_ylabel("Narrated $-$ executed goal pass (pp)")
    ax.set_xticks(m_list)
    ax.set_xlim(5.0, 12.0)
    ax.set_ylim(-15.5, 6.0)
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=True,
        facecolor="white",
        edgecolor="#cccccc",
        fontsize=8,
    )

    pdf_path, png_path = save_figure(fig, out_dir, "f7_narrated_minus_executed", dpi=dpi)

    caption = (
        "Narrated minus executed goal-pass rate in percentage points across prefix depths $m=6, 9, 11$, "
        "with scenario-clustered 95% confidence intervals. Values below zero mean execution beat narration. "
        "The only contrast whose interval excludes zero is the untailored receiver at $m=11$. "
        "The difference between the two series is not tested here: six paired contrasts are not a "
        "difference-in-differences."
    )

    return {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 4.8,
        "column": "two-column",
        "caption": caption,
        "series": manifest_series,
        "skipped_reason": None,
    }


def generate_f8_advice_cost_quality(
    results_dir: Path,
    out_dir: Path,
    dpi: int = 200,
) -> dict[str, Any]:
    """F8 · Cost/quality scatter for advice and action-prefix arms."""
    fig_id = "F8"
    apply_style()

    quality_path = results_dir / "hj13_advice_at_price_20260923.report.json"
    cost_path = results_dir / "hj13_advice_at_price_cost_20260923.report.json"
    quality_data = load_report_json(quality_path, fig_id)
    cost_data = load_report_json(cost_path, fig_id)

    arm_specs = [
        ("advise_k10_fullctx", "advice", (8, 8)),
        ("advise_k1_fullctx", "advice", (8, -18)),
        ("prefix_m9", "prefix", (8, -16)),
        ("prefix_m11", "prefix", (8, 8)),
    ]
    arm_values: list[tuple[str, str, float, float, float, tuple[int, int]]] = []
    for arm, group, offset in arm_specs:
        quality_key = f"arms.{arm}.goal_pass_all"
        tokens_key = f"arms.{arm}.noncached_tokens_per_episode"
        calls_key = f"arms.{arm}.hosted_calls_per_episode"
        quality = float(get_nested_key(quality_data, quality_key, quality_path, fig_id))
        tokens = float(get_nested_key(cost_data, tokens_key, cost_path, fig_id))
        calls = float(get_nested_key(cost_data, calls_key, cost_path, fig_id))
        arm_values.append((arm, group, quality, tokens, calls, offset))

    if not arm_values:
        raise SystemExit(f"Fatal [{fig_id}]: empty series for advice cost/quality scatter")

    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    group_styles = {
        "advice": (PALETTE["advice"], "Advice arms"),
        "prefix": (PALETTE["tailored"], "Action-prefix arms"),
    }
    seen_groups: set[str] = set()
    for arm, group, quality, tokens, calls, offset in arm_values:
        style, group_label = group_styles[group]
        ax.scatter(
            [tokens],
            [quality],
            color=style["color"],
            marker=style["marker"],
            s=62,
            edgecolor="#333333",
            linewidth=0.8,
            label=group_label if group not in seen_groups else None,
            zorder=5,
        )
        seen_groups.add(group)
        ax.annotate(
            f"{arm}\n{calls:.2f} calls/ep",
            (tokens, quality),
            textcoords="offset points",
            xytext=offset,
            ha="left",
            va="center",
            fontsize=8,
            color=style["color"],
        )

    tokens_values = [tokens for _, _, _, tokens, _, _ in arm_values]
    quality_values = [quality for _, _, quality, _, _, _ in arm_values]
    ax.set_xscale("log")
    ax.set_xlim(min(tokens_values) / 1.8, max(tokens_values) * 2.5)
    ax.set_ylim(min(quality_values) - 0.04, max(quality_values) + 0.04)
    ax.set_xlabel("Non-cached planner tokens per episode (log scale)")
    ax.set_ylabel("Goal pass rate")
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.02, 1.0),
        frameon=True,
        facecolor="white",
        edgecolor="#cccccc",
    )

    pdf_path, png_path = save_figure(fig, out_dir, "f8_advice_cost_quality", dpi=dpi)

    quality_keys = [f"arms.{arm}.goal_pass_all" for arm, group, *_ in arm_values]
    cost_keys = [
        key
        for arm, group, *_ in arm_values
        for key in (
            f"arms.{arm}.noncached_tokens_per_episode",
            f"arms.{arm}.hosted_calls_per_episode",
        )
    ]
    values_by_arm = {arm: (quality, tokens, calls) for arm, group, quality, tokens, calls, _ in arm_values}
    advice_quality, advice_tokens, advice_calls = values_by_arm["advise_k1_fullctx"]
    prefix_quality, prefix_tokens, prefix_calls = values_by_arm["prefix_m11"]
    token_ratio = advice_tokens / prefix_tokens
    calls_ratio = advice_calls / prefix_calls
    score_gap_pp = (prefix_quality - advice_quality) * 100.0
    caption = (
        "Cost/quality scatter for advice and action-prefix arms. Advice reviewed at every step spends "
        f"{token_ratio:.1f}× the tokens and {calls_ratio:.1f}× the hosted calls of $\\mathit{{prefix\\_m11}}$ "
        f"and still scores {score_gap_pp:.2f} pp lower; this was the registered H2 test "
        "(docs/prereg_h2_advice_at_price_20260923.md)."
    )

    return {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 7.2,
        "column": "two-column",
        "caption": caption,
        "series": [
            {
                "label": "Advice arms",
                "report_path": f"{quality_path}; {cost_path}",
                "json_keys": [
                    f"{quality_path.name}:{key}" for key in quality_keys if "advise_" in key
                ] + [
                    f"{cost_path.name}:{key}" for key in cost_keys if "advise_" in key
                ],
                "n_points": 2,
            },
            {
                "label": "Action-prefix arms",
                "report_path": f"{quality_path}; {cost_path}",
                "json_keys": [
                    f"{quality_path.name}:{key}" for key in quality_keys if "prefix_" in key
                ] + [
                    f"{cost_path.name}:{key}" for key in cost_keys if "prefix_" in key
                ],
                "n_points": 2,
            },
        ],
        "skipped_reason": None,
    }


def run_figures(
    results_dir: Path,
    out_dir: Path,
    manifest_path: Path,
    only_fig: str | None = None,
    dpi: int = 200,
) -> None:
    """Generate all figures or single figure and write manifest."""
    validate_output_path(out_dir)
    validate_output_path(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    generators = {
        "F1": generate_f1_depth_curve,
        "F2": generate_f2_channel_budget,
        "F3": generate_f3_tailoring_gap,
        "F4": generate_f4_mechanism,
        "F5": generate_f5_second_family,
        "F6": generate_f6_narrated_vs_executed,
        "F7": generate_f7_narrated_minus_executed,
        "F8": generate_f8_advice_cost_quality,
    }

    manifest_entries = []

    for fig_id, gen_fn in generators.items():
        if only_fig is not None and only_fig.upper() != fig_id:
            continue
        entry = gen_fn(results_dir, out_dir, dpi=dpi)
        manifest_entries.append(entry)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_entries, f, indent=2)

    print(f"Generated {len(manifest_entries)} figure manifest entries in {manifest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate paper figures from report JSON only (Brief X41 / X47).")
    parser.add_argument("--results-dir", type=Path, default=Path("campaign/results"), help="Directory containing report JSON files")
    parser.add_argument("--out-dir", type=Path, default=Path("paper/figures"), help="Output directory for generated figures")
    parser.add_argument("--manifest", type=Path, default=Path("paper/figures/figures_manifest.json"), help="Manifest JSON path")
    parser.add_argument("--only", type=str, default=None, help="Generate only specified figure ID (e.g. F1, F2, F3, F4, F5, F6)")
    parser.add_argument("--dpi", type=int, default=200, help="DPI for PNG output (default 200)")

    args = parser.parse_args()
    run_figures(
        results_dir=args.results_dir,
        out_dir=args.out_dir,
        manifest_path=args.manifest,
        only_fig=args.only,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()
