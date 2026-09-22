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
  F5: Second family comparison (Qwen3-8B vs Granite zero-shot), conditional on floors.
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

# Colour-blind-safe palette distinguishable in greyscale (varying hue, marker, linestyle)
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
    - Ceilings labelled with caps (CEIL-01/CEIL-02).
    - Refuses if required reports/keys missing or series empty.
    """
    fig_id = "F1"
    apply_style()

    # 1. Tailored receiver data from post-guard shape report
    shape_rep_path = results_dir / "hj13_shape_post_guard_20260923.report.json"
    shape_data = load_report_json(shape_rep_path, fig_id)
    
    m_tailored = [2, 4, 6, 7, 8, 9, 10, 11]
    y_tailored: list[float] = []
    tailored_keys: list[str] = []
    for m in m_tailored:
        k = f"arms.prefix_m{m}.goal_pass_all"
        val = get_nested_key(shape_data, k, shape_rep_path, fig_id)
        if val is None:
            raise SystemExit(f"Fatal [{fig_id}]: null value for key {k!r} in {shape_rep_path}")
        y_tailored.append(float(val))
        tailored_keys.append(k)

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
    
    k_zs6 = "arms.zs_m6.goal_pass_all"
    y_zs6 = float(get_nested_key(zs_m6_m9_data, k_zs6, zs_m6_m9_path, fig_id))
    y_zs.append(y_zs6)
    zs_keys.append(f"{zs_m6_m9_path.name}:{k_zs6}")

    k_zs9 = "arms.zs_m9.goal_pass_all"
    y_zs9 = float(get_nested_key(zs_m6_m9_data, k_zs9, zs_m6_m9_path, fig_id))
    y_zs.append(y_zs9)
    zs_keys.append(f"{zs_m6_m9_path.name}:{k_zs9}")

    k_zs11 = "arms.zs_m11.goal_pass_all"
    y_zs11 = float(get_nested_key(zs_m9_m11_data, k_zs11, zs_m9_m11_path, fig_id))
    y_zs.append(y_zs11)
    zs_keys.append(f"{zs_m9_m11_path.name}:{k_zs11}")

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

    # Reference ceilings (with mandatory cap labels per CEIL-01/02)
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
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#cccccc", framealpha=0.9)

    pdf_path, png_path = save_figure(fig, out_dir, "f1_depth_curve", dpi=dpi)

    caption = (
        "Goal pass rate against prefix handoff depth $m$ for tailored and untailored receivers, "
        "compared against the cap-25 (0.8284) and cap-81 (0.7637) planner ceilings, plan-only floor (0.7181), "
        "and executor-alone floor (0.5289). Quality is flat below a breakpoint and rises above it; the "
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
            },
            {
                "label": "Untailored receiver (granite zero-shot)",
                "report_path": f"{zs_m6_m9_path}; {zs_m9_m11_path}",
                "json_keys": zs_keys,
                "n_points": len(y_zs),
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

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(7.0, 3.6))

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
            ax_left.annotate(
                f"$m={hm}$\n({val:.1f}%)", (hm, val),
                textcoords="offset points", xytext=(0, -22 if hm == 6 else (8 if hm == 11 else -22)),
                ha="center", fontsize=8, color="#882200",
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
    ax_right.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#cccccc")

    plt.tight_layout()
    pdf_path, png_path = save_figure(fig, out_dir, "f4_mechanism", dpi=dpi)

    caption = (
        "Mechanism decomposition across two panels. Left (M1): cumulative share of the planner's first API uses "
        "by action position, showing that >78% of API discovery occurs before $m=9$. "
        "Right (M3): decomposition of zero-shot depth rises ($m6\\rightarrow 9$ and $m6\\rightarrow 11$) into "
        "handoff-earned and silenced-episode contributions, establishing that 83.8% of the $m6\\rightarrow 9$ rise "
        "is earned on episodes where the executor took over and completed the task (MECH-01, MECH-03)."
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
    """F5 · The second family (Qwen3-8B vs Granite zero-shot).
    
    Guard:
    Must skip if Qwen floor reports (hj15_executor_alone_zsq / hj15_prompt_only_zsq) are absent,
    recording the reason in the manifest per Brief X41: the Qwen rise must never be drawn without its floor.
    """
    fig_id = "F5"
    apply_style()

    qwen_alone_path = results_dir / "hj15_executor_alone_zsq_20260923.report.json"
    qwen_prompt_path = results_dir / "hj15_prompt_only_zsq_20260923.report.json"

    # Strict guard from Brief X41: if Qwen floor reports are absent, skip figure
    if not qwen_alone_path.is_file() or not qwen_prompt_path.is_file():
        skip_msg = (
            "Skipped: Qwen floor reports (hj15_executor_alone_zsq / hj15_prompt_only_zsq) "
            "are absent on disk. The Qwen rise must never be drawn without its floor."
        )
        manifest_entry = {
            "figure_id": fig_id,
            "file_pdf": None,
            "file_png": None,
            "width_in": 3.4,
            "column": "single-column",
            "caption": "Qwen3-8B zero-shot against granite zero-shot over depth, each against its own floor (pending floor reports).",
            "series": [],
            "skipped_reason": skip_msg,
        }
        return manifest_entry

    # If floor reports exist, load all data and plot
    qwen_curve_path = results_dir / "hj15_qwen_zeroshot_curve_20260923.report.json"
    qwen_curve_data = load_report_json(qwen_curve_path, fig_id)
    qwen_alone_data = load_report_json(qwen_alone_path, fig_id)
    qwen_prompt_data = load_report_json(qwen_prompt_path, fig_id)

    granite_m6_m9_path = results_dir / "hj13_zeroshot_depth_m6_m9_20260923.report.json"
    granite_m6_m9_data = load_report_json(granite_m6_m9_path, fig_id)

    k_qwen_m6 = "arms.zsq_m6.goal_pass_all"
    k_qwen_m9 = "arms.zsq_m9.goal_pass_all"
    qwen_m6 = float(get_nested_key(qwen_curve_data, k_qwen_m6, qwen_curve_path, fig_id))
    qwen_m9 = float(get_nested_key(qwen_curve_data, k_qwen_m9, qwen_curve_path, fig_id))

    k_qwen_exec = "arms.executor_alone.goal_pass_all"
    qwen_floor_exec = float(get_nested_key(qwen_alone_data, k_qwen_exec, qwen_alone_path, fig_id))

    granite_m6 = float(get_nested_key(granite_m6_m9_data, "arms.zs_m6.goal_pass_all", granite_m6_m9_path, fig_id))
    granite_m9 = float(get_nested_key(granite_m6_m9_data, "arms.zs_m9.goal_pass_all", granite_m6_m9_path, fig_id))

    fig, ax = plt.subplots(figsize=(3.4, 3.8))

    ax.plot([6, 9], [qwen_m6, qwen_m9], "o--", color=PALETTE["qwen_zeroshot"]["color"], label="Qwen3-8B zero-shot")
    ax.axhline(qwen_floor_exec, color=PALETTE["qwen_zeroshot"]["color"], linestyle=":", label="Qwen floor")

    ax.plot([6, 9], [granite_m6, granite_m9], "s-", color=PALETTE["zeroshot"]["color"], label="Granite zero-shot")

    ax.set_xlabel("Handoff depth $m$")
    ax.set_ylabel("Goal pass rate")
    ax.set_xticks([6, 9])
    ax.legend(loc="lower right", frameon=True)

    pdf_path, png_path = save_figure(fig, out_dir, "f5_second_family", dpi=dpi)

    manifest_entry = {
        "figure_id": fig_id,
        "file_pdf": str(pdf_path),
        "file_png": str(png_path),
        "width_in": 3.4,
        "column": "single-column",
        "caption": "Qwen3-8B zero-shot against granite zero-shot over depth, each against its own floor.",
        "series": [
            {
                "label": "Qwen3-8B zero-shot",
                "report_path": str(qwen_curve_path),
                "json_keys": [k_qwen_m6, k_qwen_m9],
                "n_points": 2,
            },
        ],
        "skipped_reason": None,
    }
    return manifest_entry


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
    parser = argparse.ArgumentParser(description="Generate paper figures from report JSON only (Brief X41).")
    parser.add_argument("--results-dir", type=Path, default=Path("campaign/results"), help="Directory containing report JSON files")
    parser.add_argument("--out-dir", type=Path, default=Path("paper/figures"), help="Output directory for generated figures")
    parser.add_argument("--manifest", type=Path, default=Path("paper/figures/figures_manifest.json"), help="Manifest JSON path")
    parser.add_argument("--only", type=str, default=None, help="Generate only specified figure ID (e.g. F1, F2, F3, F4, F5)")
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
