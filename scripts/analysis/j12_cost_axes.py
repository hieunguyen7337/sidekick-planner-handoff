#!/usr/bin/env python3
"""Cost axes analysis (Brief X40 Unit A / X44): noncached tokens, provider USD, hosted calls.

Evaluates whether the ordering of arms and non-inferiority conclusions survive
under three distinct cost currencies:
1. noncached_tokens_per_episode (standard non-cached token convention)
2. usd_per_episode (provider-priced dollars including cache billing)
3. hosted_calls_per_episode (n_planner_calls from result.json)

Also reports local_gpu_usd_per_episode as an assumption, not a measurement.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Import noncached cost helpers [OBSERVED scripts/analysis/j8_noncached_cost.py:16,27,76,150]
_NC_SPEC = importlib.util.spec_from_file_location(
    "j8_noncached_cost", Path(__file__).resolve().parent / "j8_noncached_cost.py"
)
_nc = importlib.util.module_from_spec(_NC_SPEC)
assert _NC_SPEC.loader is not None
_NC_SPEC.loader.exec_module(_nc)
usage_noncached_tokens = _nc.usage_noncached_tokens
last_plan_event_noncached_tokens = _nc.last_plan_event_noncached_tokens
attach_sft_plan_source_plan_tokens = _nc.attach_sft_plan_source_plan_tokens
noncached_episode_cost = _nc.noncached_episode_cost

# Import frontier helpers [OBSERVED scripts/analysis/j8_frontier.py:140,247,886,1045,1142]
_J8_SPEC = importlib.util.spec_from_file_location(
    "j8_frontier", Path(__file__).resolve().parent / "j8_frontier.py"
)
j8 = importlib.util.module_from_spec(_J8_SPEC)
assert _J8_SPEC.loader is not None
_J8_SPEC.loader.exec_module(j8)
parse_arm_spec = j8.parse_arm_spec
parse_seeds = j8.parse_seeds
summarise_arm = j8.summarise_arm
paired_contrast = j8.paired_contrast
paired_diff_scenario = j8.paired_diff_scenario

# Import j10 report loader [OBSERVED scripts/analysis/j10_report.py:355]
_J10_SPEC = importlib.util.spec_from_file_location(
    "j10_report", Path(__file__).resolve().parent / "j10_report.py"
)
j10 = importlib.util.module_from_spec(_J10_SPEC)
assert _J10_SPEC.loader is not None
_J10_SPEC.loader.exec_module(j10)

from scripts.setup.hj1_gate import (  # noqa: E402
    BOOTSTRAP,
    SEED,
    paired_diff,
    scenario_of,
)

DEFAULT_PRICES_PATH = REPO_ROOT / "configs" / "cost" / "prices_2026-09.yaml"
DEFAULT_SFT_PLAN_PACKET_SOURCE = Path(
    "/scratch/n12194778/sidekick/results/hj1b_planner_20260915"
)
DEFAULT_SFT_PLAN_PACKET_SYSTEM = "planner_alone"
COST_AXES = (
    "noncached_tokens_per_episode",
    "usd_per_episode",
    "hosted_calls_per_episode",
)
NONINFERIORITY_MARGIN_PP = 7.00


def validate_output_path(path: Path | str | None) -> None:
    """Refuse output paths inside raw results dir or containing test splits.
    
    [OBSERVED scripts/analysis/j13_mechanism.py:57-73]
    """
    if path is None:
        return
    p = Path(path).resolve()
    s = str(p)
    if "test_normal" in s or "test_challenge" in s:
        raise ValueError(
            f"Output path {path} forbidden: contains test_normal or test_challenge"
        )
    scratch_results = Path("/scratch/n12194778/sidekick/results").resolve()
    try:
        p.relative_to(scratch_results)
        raise ValueError(
            f"Output path {path} forbidden: cannot write under {scratch_results}"
        )
    except ValueError as e:
        if "cannot write under" in str(e):
            raise
        # Path is outside scratch results directory, which is valid.


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--arm",
        action="append",
        required=True,
        type=parse_arm_spec,
        metavar="LABEL=DIR",
        help="Named result tree; repeat for each arm.",
    )
    p.add_argument(
        "--prices",
        type=Path,
        default=DEFAULT_PRICES_PATH,
        help="Path to prices YAML config.",
    )
    p.add_argument("--out", type=Path, required=True, help="JSON report path.")
    p.add_argument(
        "--out-md",
        type=Path,
        default=None,
        help="Markdown report path (optional).",
    )
    p.add_argument(
        "--n-boot",
        type=int,
        default=10000,
        help="Number of bootstrap iterations (default: 10000).",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=20260915,
        help="Random seed for bootstrap (default: 20260915).",
    )
    p.add_argument(
        "--cluster",
        choices=["scenario", "task"],
        default="scenario",
        help="Bootstrap resample cluster unit (default: scenario).",
    )
    p.add_argument(
        "--seeds",
        default="1,2",
        help="Comma-separated seeds filter (default: 1,2).",
    )
    p.add_argument(
        "--reference-arm",
        default=None,
        help="Reference/ceiling arm label for non-inferiority (e.g. planner_alone).",
    )
    p.add_argument(
        "--packet-source",
        type=Path,
        default=DEFAULT_SFT_PLAN_PACKET_SOURCE,
        help="Campaign tree sft_plan replays from (default: hj1b_planner_20260915).",
    )
    p.add_argument(
        "--packet-system",
        default=DEFAULT_SFT_PLAN_PACKET_SYSTEM,
        help="System subdirectory under packet-source (default: planner_alone).",
    )
    return p.parse_args(argv)


def load_price_card(prices_path: Path) -> dict[str, Any]:
    """Load models price rates and local gpu hour cost from YAML."""
    import yaml

    with open(prices_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    models = dict(data.get("models", {}))
    local = dict(data.get("local", {}))
    usd_per_gpu_hour = float(local.get("usd_per_gpu_hour", 2.50))
    return {
        "schedule_date": data.get("schedule_date", ""),
        "source": data.get("source", ""),
        "models": models,
        "usd_per_gpu_hour": usd_per_gpu_hour,
    }


def price_usage_record(
    usage: dict[str, Any],
    models_prices: dict[str, dict[str, float]],
    diagnostics: dict[str, int],
) -> float:
    """Price a single usage record in USD.
    
    If cached_input_tokens is not distinguished (missing/None), it is counted as fresh input
    and n_usage_without_cache_split is incremented.
    """
    if usage.get("provider") == "mock":
        return 0.0
    model = str(usage.get("model") or "gpt-5.6-luna")
    rates = models_prices.get(
        model,
        models_prices.get("gpt-5.6-luna", {"input": 0.20, "cached_input": 0.02, "output": 1.20}),
    )
    rate_in = float(rates["input"]) / 1_000_000.0
    rate_cached = float(rates["cached_input"]) / 1_000_000.0
    rate_out = float(rates["output"]) / 1_000_000.0

    has_cache_split = "cached_input_tokens" in usage and usage["cached_input_tokens"] is not None
    if not has_cache_split:
        diagnostics["n_usage_without_cache_split"] += 1
        uncached_input = float(usage.get("input_tokens") or 0)
        cached_input = 0.0
    else:
        raw_input = float(usage.get("input_tokens") or 0)
        cached_input = float(usage.get("cached_input_tokens") or 0)
        uncached_input = max(0.0, raw_input - cached_input)

    out_tokens = float(usage.get("output_tokens") or 0) + float(
        usage.get("reasoning_output_tokens") or 0
    )
    return uncached_input * rate_in + cached_input * rate_cached + out_tokens * rate_out


def extract_events_usages(events_path: Path) -> list[dict[str, Any]]:
    """Extract usage dicts for planner events in events.jsonl after last run_start."""
    usages: list[dict[str, Any]] = []
    if not events_path.is_file():
        return usages
    try:
        text = events_path.read_text(encoding="utf-8")
    except OSError:
        return usages
    raw_events: list[dict[str, Any]] = []
    last_start = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        raw_events.append(ev)
        if ev.get("event_type") == "run_start":
            last_start = len(raw_events) - 1

    for ev in raw_events[last_start:]:
        u = ev.get("usage")
        if isinstance(u, dict) and ev.get("actor") == "planner":
            usages.append(u)
    return usages


def extract_prefix_replayed_usages(
    source_campaign: Path | str,
    source_system: str,
    task_id: str,
    seed: int,
    effective_m: int,
) -> list[dict[str, Any]]:
    """Extract usage records from source campaign for replayed prefix steps."""
    source_path = (
        Path(source_campaign) / source_system / str(seed) / str(task_id) / "events.jsonl"
    )
    if not source_path.is_file():
        return []
    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    last_start = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
            if ev.get("event_type") == "run_start":
                last_start = len(events) - 1
    attempt_events = events[last_start:]

    # Count executed actions up to effective_m
    prefix_usages: list[dict[str, Any]] = []
    action_count = 0
    for ev in attempt_events:
        if ev.get("actor") == "planner" and isinstance(ev.get("usage"), dict):
            prefix_usages.append(ev["usage"])
        if ev.get("event_type") == "action":
            payload = ev.get("payload") or {}
            kind = payload.get("kind")
            if kind in ("CODE", "COMPLETE"):
                action_count += 1
                if action_count >= effective_m:
                    break
    return prefix_usages


def price_arm_episodes(
    arm: dict[str, Any],
    price_card: dict[str, Any],
    root: Path | None,
    packet_source: Path | None,
    packet_system: str,
) -> dict[str, Any]:
    """Calculate prices for every episode in the arm across all three cost axes."""
    cleaned = arm["cleaned"]
    models_prices = price_card["models"]
    usd_per_gpu_hour = price_card["usd_per_gpu_hour"]

    diagnostics = {
        "n_usage_without_cache_split": 0,
        "n_episodes_priced": 0,
        "n_episodes_missing_usage": 0,
        "n_episodes_with_wall_time": 0,
    }

    arm_dir = Path(root) if root else None

    for key, row in cleaned.items():
        task_id, seed = key
        ep_dir = arm_dir / str(seed) / str(task_id) if arm_dir else None
        events_path = ep_dir / "events.jsonl" if ep_dir else None

        # 2. Hosted calls axis
        calls = row.get("planner_calls_replay_inclusive")
        if calls is None:
            calls = row.get("n_planner_calls")
        if calls is None:
            calls = row.get("planner_calls_live")
        row["hosted_calls_per_episode"] = float(calls) if calls is not None else None

        # 1. Non-cached tokens axis
        nc_tokens = noncached_episode_cost(row)
        if nc_tokens is None and (calls is not None and calls == 0):
            nc_tokens = 0.0
        row["noncached_tokens_per_episode"] = nc_tokens

        # 3. Provider USD axis
        # Collect all usage records contributing to this episode
        usage_records: list[dict[str, Any]] = []
        if events_path and events_path.is_file():
            usage_records.extend(extract_events_usages(events_path))

        # Check sft_plan source plan event
        if _nc.is_sft_plan_row(row, arm["label"]):
            ps = packet_source or DEFAULT_SFT_PLAN_PACKET_SOURCE
            sft_events = ps / packet_system / str(seed) / str(task_id) / "events.jsonl"
            if sft_events.is_file():
                sft_usages = extract_events_usages(sft_events)
                if sft_usages:
                    usage_records.append(sft_usages[-1])

        # Check prefix handoff replayed prefix usage
        eff_m = row.get("effective_m")
        if eff_m is not None and int(eff_m) > 0:
            src_camp = packet_source or DEFAULT_SFT_PLAN_PACKET_SOURCE
            prefix_usages = extract_prefix_replayed_usages(
                src_camp, "planner_alone", task_id, seed, int(eff_m)
            )
            usage_records.extend(prefix_usages)

        # Fallback to result.json totals if no live usage was found in events.jsonl
        if not usage_records and (calls is None or calls > 0):
            totals = (row.get("totals") or {}) if isinstance(row.get("totals"), dict) else {}
            per_actor = (totals.get("per_actor") or {}) if isinstance(totals.get("per_actor"), dict) else {}
            planner_bucket = per_actor.get("planner")
            if isinstance(planner_bucket, dict) and any(planner_bucket.get(k) for k in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")):
                cached = float(planner_bucket.get("cached_input_tokens") or 0)
                inp = float(planner_bucket.get("input_tokens") or 0)
                usage_records.append({
                    "model": "gpt-5.6-luna",
                    "input_tokens": inp + cached,
                    "cached_input_tokens": cached,
                    "output_tokens": float(planner_bucket.get("output_tokens") or 0),
                    "reasoning_output_tokens": float(planner_bucket.get("reasoning_output_tokens") or 0),
                })
            else:
                live_nc = row.get("planner_tokens_noncached_live")
                cached = row.get("cached_input_tokens")
                if live_nc is not None or cached is not None:
                    # Synthesize usage dict from ledger totals
                    usage_records.append({
                        "model": "gpt-5.6-luna",
                        "input_tokens": (live_nc or 0.0) + (cached or 0.0),
                        "cached_input_tokens": cached,
                        "output_tokens": 0.0,
                        "reasoning_output_tokens": 0.0,
                    })

        # Calculate USD cost
        if usage_records:
            total_usd = sum(
                price_usage_record(u, models_prices, diagnostics) for u in usage_records
            )
            row["usd_per_episode"] = total_usd
            diagnostics["n_episodes_priced"] += 1
        elif (calls is not None and calls == 0) or (nc_tokens is not None and nc_tokens == 0):
            row["usd_per_episode"] = 0.0
            diagnostics["n_episodes_priced"] += 1
        else:
            row["usd_per_episode"] = None
            diagnostics["n_episodes_missing_usage"] += 1

        # 4. Local GPU USD assumption (separate assumption)
        gpu_seconds = row.get("gpu_seconds")
        if gpu_seconds is None:
            # Check if duration/wall time is recorded in raw totals
            raw_totals = (row.get("totals") or {}) if isinstance(row.get("totals"), dict) else {}
            gpu_seconds = raw_totals.get("gpu_seconds_total")
        if gpu_seconds is not None:
            row["local_gpu_usd_per_episode"] = (float(gpu_seconds) / 3600.0) * usd_per_gpu_hour
            diagnostics["n_episodes_with_wall_time"] += 1
        else:
            row["local_gpu_usd_per_episode"] = None

    n_episodes = len(cleaned)
    n_priced = diagnostics["n_episodes_priced"]
    n_missing = diagnostics["n_episodes_missing_usage"]

    # Fatal checks as specified in Brief X40
    if n_episodes > 0 and n_priced == 0:
        raise SystemExit(
            f"Fatal: arm {arm['label']!r} yielded 0 priced episodes (out of {n_episodes})"
        )
    if n_episodes > 0 and (n_missing / n_episodes) > 0.05:
        raise SystemExit(
            f"Fatal: arm {arm['label']!r} has {n_missing}/{n_episodes} "
            f"({n_missing / n_episodes * 100:.1f}%) episodes lacking usage records (> 5%)"
        )

    # Compute arm-level means across the three axes
    nc_vals = [r["noncached_tokens_per_episode"] for r in cleaned.values() if r.get("noncached_tokens_per_episode") is not None]
    usd_vals = [r["usd_per_episode"] for r in cleaned.values() if r.get("usd_per_episode") is not None]
    call_vals = [r["hosted_calls_per_episode"] for r in cleaned.values() if r.get("hosted_calls_per_episode") is not None]
    gpu_vals = [r["local_gpu_usd_per_episode"] for r in cleaned.values() if r.get("local_gpu_usd_per_episode") is not None]

    return {
        "label": arm["label"],
        "n_episodes": n_episodes,
        "diagnostics": diagnostics,
        "noncached_tokens_per_episode": round(statistics.fmean(nc_vals), 6) if nc_vals else None,
        "usd_per_episode": round(statistics.fmean(usd_vals), 6) if usd_vals else None,
        "hosted_calls_per_episode": round(statistics.fmean(call_vals), 6) if call_vals else None,
        "local_gpu_usd_per_episode": round(statistics.fmean(gpu_vals), 6) if gpu_vals else None,
        "local_gpu_wall_time_note": (
            "documented assumption using local.usd_per_gpu_hour; null when wall time is unrecorded"
            if not gpu_vals
            else "calculated from recorded gpu_seconds and local.usd_per_gpu_hour assumption"
        ),
        # Per-episode values behind the means above. A ratio of two arms' means needs them
        # to carry an interval (j10_report's P2, A1 r2 §5.3), and re-pricing in the reader
        # would be a second implementation of this function.
        "episodes": [
            {
                "task_id": str(key[0]),
                "seed": int(key[1]),
                "noncached_tokens_per_episode": row.get("noncached_tokens_per_episode"),
                "hosted_calls_per_episode": row.get("hosted_calls_per_episode"),
                "usd_per_episode": row.get("usd_per_episode"),
            }
            for key, row in sorted(cleaned.items())
        ],
    }


def compute_rankings_and_flips(
    arm_summaries: list[dict[str, Any]] | dict[str, dict[str, Any]],
) -> tuple[dict[str, list[str]], bool, list[dict[str, Any]]]:
    """Rank arms on each cost axis (lowest cost first) and detect ordering flips."""
    ordering_by_axis: dict[str, list[str]] = {}
    summaries_list = (
        list(arm_summaries.values())
        if isinstance(arm_summaries, dict)
        else list(arm_summaries)
    )

    for axis in COST_AXES:
        valid_arms = [a for a in summaries_list if a.get(axis) is not None]
        sorted_arms = sorted(valid_arms, key=lambda a: (float(a[axis]), a["label"]))
        ordering_by_axis[axis] = [a["label"] for a in sorted_arms]

    # Check stability across all axes
    axis_list = list(COST_AXES)
    first_order = ordering_by_axis[axis_list[0]]
    is_stable = all(ordering_by_axis[ax] == first_order for ax in axis_list[1:])

    # Find pairwise rank flips
    flips: list[dict[str, Any]] = []
    labels = [a["label"] for a in summaries_list]

    for ax1, ax2 in combinations(COST_AXES, 2):
        order1 = ordering_by_axis[ax1]
        order2 = ordering_by_axis[ax2]
        rank1 = {lab: i for i, lab in enumerate(order1)}
        rank2 = {lab: i for i, lab in enumerate(order2)}

        for lab_a, lab_b in combinations(labels, 2):
            if lab_a not in rank1 or lab_b not in rank1 or lab_a not in rank2 or lab_b not in rank2:
                continue
            r1_a, r1_b = rank1[lab_a], rank1[lab_b]
            r2_a, r2_b = rank2[lab_a], rank2[lab_b]
            # Swap occurs if relative ordering flips
            if (r1_a < r1_b and r2_a > r2_b) or (r1_a > r1_b and r2_a < r2_b):
                flips.append({
                    "pair": [lab_a, lab_b],
                    "axis_a": ax1,
                    "axis_b": ax2,
                    "order_in_axis_a": [lab_a, lab_b] if r1_a < r1_b else [lab_b, lab_a],
                    "order_in_axis_b": [lab_a, lab_b] if r2_a < r2_b else [lab_b, lab_a],
                })

    return ordering_by_axis, is_stable, flips


def compute_noninferiority_across_axes(
    arms: dict[str, dict[str, Any]],
    ceiling_label: str,
    cluster: str = "scenario",
    n_boot: int = BOOTSTRAP,
    seed: int = SEED,
) -> dict[str, Any]:
    """Re-run non-inferiority against ceiling arm on each cost axis."""
    if ceiling_label not in arms:
        return {
            "evaluated": False,
            "ceiling_arm": ceiling_label,
            "reason": f"ceiling arm {ceiling_label!r} not in loaded arms ({sorted(arms)})",
            "ni_unchanged_across_axes": None,
            "comparisons": {},
        }

    ceiling_arm = arms[ceiling_label]
    comparisons: dict[str, Any] = {}
    verdicts_by_arm: dict[str, set[bool]] = {}

    for label, arm in arms.items():
        if label == ceiling_label:
            continue

        # Quality contrast (TGC within 7 pp margin)
        q_contrast = paired_contrast(arm, ceiling_arm, "tgc", cluster=cluster)
        q_ci = q_contrast.get("ci95_pp")
        q_pass = bool(q_ci is not None and float(q_ci[0]) >= -NONINFERIORITY_MARGIN_PP)

        cost_axes_results: dict[str, Any] = {}
        arm_verdicts: set[bool] = set()

        for axis in COST_AXES:
            # Clustered paired difference of cost: arm minus ceiling
            left_cleaned = arm["cleaned"]
            right_cleaned = ceiling_arm["cleaned"]
            c_contrast = paired_contrast(arm, ceiling_arm, axis, cluster=cluster)
            c_ci = c_contrast.get("ci95")
            c_diff = c_contrast.get("diff")
            # Cost reduction: arm has strictly lower cost than ceiling with CI upper < 0
            cost_reduced = bool(c_ci is not None and float(c_ci[1]) < 0.0)
            holds = bool(q_pass and cost_reduced)
            arm_verdicts.add(holds)

            cost_axes_results[axis] = {
                "diff": c_diff,
                "ci95": c_ci,
                "cost_reduced": cost_reduced,
                "holds": holds,
            }

        verdicts_by_arm[label] = arm_verdicts
        comparisons[label] = {
            "quality_tgc_contrast": q_contrast,
            "quality_within_7pp": q_pass,
            "axes": cost_axes_results,
            "consistent_across_axes": len(arm_verdicts) <= 1,
        }

    all_consistent = all(len(v) <= 1 for v in verdicts_by_arm.values()) if verdicts_by_arm else True
    return {
        "evaluated": True,
        "ceiling_arm": ceiling_label,
        "ni_unchanged_across_axes": all_consistent,
        "comparisons": comparisons,
    }


def generate_markdown_report(report: dict[str, Any]) -> str:
    """Generate summary Markdown report."""
    lines: list[str] = []
    lines.append("# Cost Axes Analysis Report (Brief X40 Unit A)")
    lines.append("")
    lines.append(f"- **Prices Card**: `{report['prices_source']}`")
    lines.append(f"- **Cluster**: `{report['cluster']}`")
    lines.append(f"- **Ordering Stable Across Axes**: `{'YES' if report['ordering_is_stable_across_axes'] else 'NO'}`")
    lines.append(f"- **Non-Inferiority Unchanged Across Axes**: `{'YES' if report['ni_unchanged_across_axes'] else 'NO'}`")
    lines.append("")
    lines.append("## Arm Cost Summary by Axis")
    lines.append("")
    lines.append("| Arm | Non-cached Tokens | Provider USD ($) | Hosted Calls | Local GPU USD (Assump.) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    arms_iterable = (
        report["arms"].values()
        if isinstance(report["arms"], dict)
        else report["arms"]
    )
    for a in arms_iterable:
        tok = f"{a['noncached_tokens_per_episode']:.1f}" if a['noncached_tokens_per_episode'] is not None else "n/a"
        usd = f"${a['usd_per_episode']:.4f}" if a['usd_per_episode'] is not None else "n/a"
        calls = f"{a['hosted_calls_per_episode']:.2f}" if a['hosted_calls_per_episode'] is not None else "n/a"
        gpu = f"${a['local_gpu_usd_per_episode']:.4f}" if a['local_gpu_usd_per_episode'] is not None else "null"
        lines.append(f"| `{a['label']}` | {tok} | {usd} | {calls} | {gpu} |")
    lines.append("")
    lines.append("## Ordering by Axis (Lowest Cost First)")
    lines.append("")
    for axis, order in report["ordering_by_axis"].items():
        lines.append(f"- **{axis}**: " + " < ".join(f"`{x}`" for x in order))
    lines.append("")
    if report["ordering_flips"]:
        lines.append("## Ordering Flips")
        lines.append("")
        for flip in report["ordering_flips"]:
            lines.append(f"- Swap between `{flip['axis_a']}` ({' < '.join(flip['order_in_axis_a'])}) and `{flip['axis_b']}` ({' < '.join(flip['order_in_axis_b'])})")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    validate_output_path(args.out)
    if args.out_md:
        validate_output_path(args.out_md)

    price_card = load_price_card(args.prices)
    seeds = parse_seeds(args.seeds)

    loaded_arms: dict[str, dict[str, Any]] = {}
    arm_summaries: list[dict[str, Any]] = []

    for label, root in args.arm:
        loaded = j10.load_arm_tree(root)
        arm = summarise_arm(
            label,
            loaded,
            seeds,
            root=root,
            packet_source=args.packet_source,
            packet_system=args.packet_system,
        )
        summary = price_arm_episodes(
            arm,
            price_card,
            root=root,
            packet_source=args.packet_source,
            packet_system=args.packet_system,
        )
        loaded_arms[label] = arm
        arm_summaries.append(summary)

    ordering_by_axis, is_stable, flips = compute_rankings_and_flips(arm_summaries)

    # Determine reference ceiling arm
    ref_arm = args.reference_arm
    if ref_arm is None:
        for candidate in ("planner_alone", "hj1b_planner_20260915"):
            if candidate in loaded_arms:
                ref_arm = candidate
                break

    ni_results = compute_noninferiority_across_axes(
        loaded_arms,
        ref_arm or "",
        cluster=args.cluster,
        n_boot=args.n_boot,
        seed=args.seed,
    )

    report: dict[str, Any] = {
        "prices_source": str(args.prices),
        "cluster": args.cluster,
        "n_boot": args.n_boot,
        "seed": args.seed,
        "seeds_filter": seeds,
        "n_usage_without_cache_split": sum(
            a["diagnostics"]["n_usage_without_cache_split"] for a in arm_summaries
        ),
        "arms": {a["label"]: a for a in arm_summaries},
        "ordering_by_axis": ordering_by_axis,
        "ordering_is_stable_across_axes": is_stable,
        "ordering_flips": flips,
        "non_inferiority": ni_results,
        "ni_unchanged_across_axes": ni_results.get("ni_unchanged_across_axes"),
    }

    # Write output JSON
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote report to {args.out}")

    # Write output Markdown
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        md_text = generate_markdown_report(report)
        args.out_md.write_text(md_text, encoding="utf-8")
        print(f"Wrote markdown to {args.out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
