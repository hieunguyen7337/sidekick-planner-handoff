#!/usr/bin/env python3
"""Threshold mechanism analysis (Brief X33): M1, M2, M3 measurements.

Analyzes why there is a threshold in prefix-handoff performance across m:
- M1: API novelty front-loading
- M2: Compounding error post-handoff
- M3: Prefix-exhausted population control & decomposition

Output:
- campaign/results/hj13_mechanism_20260923.report.json
- campaign/results/hj13_mechanism_20260923.md
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from sidekick.prefix_source import _n_executed_actions
from sidekick.replay import _events_of_last_attempt

_hj1_spec = importlib.util.spec_from_file_location(
    "hj1_gate", REPO / "scripts" / "setup" / "hj1_gate.py"
)
_hj1_mod = importlib.util.module_from_spec(_hj1_spec)
assert _hj1_spec is not None and _hj1_spec.loader is not None
_hj1_spec.loader.exec_module(_hj1_mod)
scenario_of = _hj1_mod.scenario_of
BOOTSTRAP = _hj1_mod.BOOTSTRAP
SEED = _hj1_mod.SEED

API_RE = re.compile(r"apis\.([a-z][a-z_0-9]*)\.([A-Za-z_][A-Za-z_0-9]*)\s*\(")
API_RE_STR = API_RE.pattern

RESULTS_DIR = Path("/scratch/n12194778/sidekick/results")
SOURCE_PLANNER_DIR = RESULTS_DIR / "hj1b_planner_20260915/planner_alone"
OUT_REPORT = REPO / "campaign/results/hj13_mechanism_20260923.report.json"
OUT_MD = REPO / "campaign/results/hj13_mechanism_20260923.md"


def quartiles(xs: list[float | int]) -> dict[str, float | int] | None:
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)

    def q(p: float) -> float | int:
        return xs[min(n - 1, int(round(p * (n - 1))))]

    return {
        "min": xs[0],
        "p25": q(0.25),
        "p50": q(0.50),
        "p75": q(0.75),
        "max": xs[-1],
        "mean": round(statistics.fmean(xs), 4) if xs else None,
    }


def paired_diff_task(
    base: dict[tuple[str, int], float],
    other: dict[tuple[str, int], float],
) -> dict[str, Any]:
    """Task-clustered paired bootstrap diff (other - base) in percentage points."""
    keys = sorted(set(base) & set(other))
    if not keys:
        return {"n_pairs": 0, "diff_pp": None, "ci95_pp": None}
    diffs = [other[k] - base[k] for k in keys]
    point = statistics.fmean(diffs)

    by_task: dict[str, list[float]] = {}
    for (t, _s), d in zip(keys, diffs):
        by_task.setdefault(t, []).append(d)
    tasks = sorted(by_task)

    rng = random.Random(SEED)
    means: list[float] = []
    for _ in range(BOOTSTRAP):
        sampled = [
            val
            for t in (tasks[rng.randrange(len(tasks))] for _ in range(len(tasks)))
            for val in by_task[t]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    lo = means[int(0.025 * BOOTSTRAP)]
    hi = means[int(0.975 * BOOTSTRAP)]
    return {
        "n_pairs": len(diffs),
        "n_clusters": len(tasks),
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
    }


def paired_diff_scenario(
    base: dict[tuple[str, int], float],
    other: dict[tuple[str, int], float],
) -> dict[str, Any]:
    """Scenario-clustered paired bootstrap diff (other - base) in percentage points."""
    keys = sorted(set(base) & set(other))
    if not keys:
        return {"n_pairs": 0, "diff_pp": None, "ci95_pp": None}
    diffs = [other[k] - base[k] for k in keys]
    point = statistics.fmean(diffs)

    by_scenario: dict[str, list[float]] = {}
    for (t, _s), d in zip(keys, diffs):
        by_scenario.setdefault(scenario_of(t), []).append(d)
    scenarios = sorted(by_scenario)

    rng = random.Random(SEED)
    means: list[float] = []
    for _ in range(BOOTSTRAP):
        sampled = [
            val
            for s in (scenarios[rng.randrange(len(scenarios))] for _ in range(len(scenarios)))
            for val in by_scenario[s]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    lo = means[int(0.025 * BOOTSTRAP)]
    hi = means[int(0.975 * BOOTSTRAP)]
    return {
        "n_pairs": len(diffs),
        "n_clusters": len(scenarios),
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
    }


def load_episode_records(root: Path):
    """Load all (task_id, seed) records from an arm directory."""
    records = {}
    for res_path in sorted(root.glob("*/*/*/result.json")):
        d = res_path.parent
        seed, task_id = int(d.parent.name), d.name
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        events_path = d / "events.jsonl"
        events = _events_of_last_attempt(events_path) if events_path.is_file() else []
        records[(task_id, seed)] = {
            "result": res,
            "events": events,
            "events_path": str(events_path),
            "task_id": task_id,
            "seed": seed,
        }
    return records


def load_source_planner(root: Path):
    """Load source planner episodes.
    
    Verified layout: <root>/<seed>/<task_id>/result.json
    where seed is parent dir (e.g. 1, 2) and task_id is leaf dir (e.g. 0d8a4ee_1).
    """
    records = {}
    for res_path in sorted(root.glob("*/*/result.json")):
        d = res_path.parent
        try:
            seed = int(d.parent.name)
            task_id = d.name
        except Exception:
            seed = 0
            task_id = d.name
        try:
            res = json.loads(res_path.read_text(encoding="utf-8"))
            task_id = str(res.get("task_id", task_id))
            seed = int(res.get("seed", seed))
        except Exception:
            continue
        events_path = d / "events.jsonl"
        events = _events_of_last_attempt(events_path) if events_path.is_file() else []
        records[(task_id, seed)] = {
            "result": res,
            "events": events,
            "events_path": str(events_path),
            "task_id": task_id,
            "seed": seed,
        }
    return records


def extract_actions_api_names(events: list[Any]) -> list[str | None]:
    out = []
    for e in events:
        if e.event_type != "action":
            continue
        code = (e.payload or {}).get("code") or ""
        m = API_RE.search(code)
        out.append(f"{m.group(1)}.{m.group(2)}" if m else None)
    return out


def measure_m1_api_novelty(source_records: dict[tuple[str, int], dict[str, Any]]):
    """M1 — API novelty is front-loaded.
    
    Measure, per episode, the position of each first use of a given API in the
    planner's action sequence, and build the distribution of those positions.
    """
    first_use_positions: list[int] = []
    per_pos_first_uses = Counter()
    per_pos_total_actions = Counter()
    per_pos_named_actions = Counter()
    episode_first_uses_count: list[int] = []

    for (task_id, seed), rec in sorted(source_records.items()):
        api_names = extract_actions_api_names(rec["events"])
        seen_apis = set()
        n_first_uses_ep = 0
        for i, name in enumerate(api_names):
            pos = i + 1  # 1-based position
            per_pos_total_actions[pos] += 1
            if name is not None:
                per_pos_named_actions[pos] += 1
                if name not in seen_apis:
                    seen_apis.add(name)
                    first_use_positions.append(pos)
                    per_pos_first_uses[pos] += 1
                    n_first_uses_ep += 1
        episode_first_uses_count.append(n_first_uses_ep)

    total_first_uses = len(first_use_positions)
    max_pos = max(per_pos_total_actions.keys()) if per_pos_total_actions else 0

    cumulative = {}
    cum_count = 0
    for pos in range(1, min(max_pos + 1, 21)):
        c = per_pos_first_uses[pos]
        cum_count += c
        cum_share = round(cum_count / total_first_uses, 4) if total_first_uses else 0.0
        novel_share_at_pos = round(c / per_pos_total_actions[pos], 4) if per_pos_total_actions[pos] else 0.0
        cumulative[pos] = {
            "first_uses_at_pos": c,
            "total_actions_at_pos": per_pos_total_actions[pos],
            "novel_share_at_pos": novel_share_at_pos,
            "cum_first_uses": cum_count,
            "cum_first_uses_share": cum_share,
        }

    binned = {}
    for lo, hi in ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 20)):
        fu = sum(per_pos_first_uses[p] for p in range(lo, hi + 1))
        tot = sum(per_pos_total_actions[p] for p in range(lo, hi + 1))
        binned[f"{lo}-{hi}"] = {
            "first_uses": fu,
            "total_actions": tot,
            "share_of_all_first_uses": round(fu / total_first_uses, 4) if total_first_uses else 0.0,
            "novel_share_in_bin": round(fu / tot, 4) if tot else 0.0,
        }

    return {
        "n_episodes": len(source_records),
        "total_first_uses": total_first_uses,
        "mean_first_uses_per_episode": round(statistics.fmean(episode_first_uses_count), 2) if episode_first_uses_count else None,
        "first_use_position_distribution": quartiles(first_use_positions),
        "cumulative_by_position": cumulative,
        "binned": binned,
    }


def measure_m2_compounding_error(arm_records: dict[str, dict[tuple[str, int], dict[str, Any]]], m_values: list[int]):
    """M2 — compounding error after handoff.
    
    Measure, per arm and per episode, the step index of the executor's first error
    after handoff, and the number of executor steps remaining.
    """
    results_by_arm = {}

    for m in m_values:
        arm_label = f"m{m}"
        records = arm_records.get(arm_label, {})
        if not records:
            continue

        n_episodes = len(records)
        handoff_episodes = 0
        silenced_episodes = 0
        error_episodes = 0

        first_error_rel_steps = []  # 1-based relative to executor start (1 = 1st executor step)
        executor_steps_taken_list = []
        executor_steps_success_list = []
        executor_steps_fail_list = []
        rows = []

        for (task_id, seed), rec in sorted(records.items()):
            res = rec["result"]
            totals = res.get("totals") or {}
            per_actor = totals.get("per_actor") or {}
            exec_actor = per_actor.get("executor") or {}
            n_calls = exec_actor.get("n_calls", 0)

            if n_calls == 0:
                silenced_episodes += 1
                continue

            handoff_episodes += 1
            events = rec["events"]

            # Identify executor events (after handoff)
            # Find the first error in executor observations
            first_err_rel = -1
            exec_action_count = 0

            # Count executor actions and find first error
            for e in events:
                if e.event_type == "action" and e.actor == "executor":
                    exec_action_count += 1
                elif e.event_type == "observation" and e.actor == "executor":
                    # Check if error
                    is_err = False
                    if e.error_type or None:
                        is_err = True
                    text = (e.payload or {}).get("text") or ""
                    if text.startswith("Execution failed"):
                        is_err = True
                    if is_err and first_err_rel < 0:
                        first_err_rel = exec_action_count

            executor_steps_taken_list.append(exec_action_count)
            is_success = (res.get("goal_pass_rate") == 1.0)
            if is_success:
                executor_steps_success_list.append(exec_action_count)
            else:
                executor_steps_fail_list.append(exec_action_count)

            if first_err_rel > 0:
                error_episodes += 1
                first_error_rel_steps.append(first_err_rel)

            rows.append({
                "task_id": task_id,
                "seed": seed,
                "exec_actions": exec_action_count,
                "first_error_rel_step": first_err_rel if first_err_rel > 0 else None,
                "success": is_success,
                "goal_pass_rate": res.get("goal_pass_rate"),
            })

        results_by_arm[arm_label] = {
            "m": m,
            "n_episodes": n_episodes,
            "silenced_episodes": silenced_episodes,
            "handoff_episodes": handoff_episodes,
            "error_episodes": error_episodes,
            "error_rate_on_handoff": round(error_episodes / handoff_episodes, 4) if handoff_episodes else None,
            "first_error_rel_step_dist": quartiles(first_error_rel_steps),
            "share_first_error_at_step_1": round(sum(1 for s in first_error_rel_steps if s == 1) / len(first_error_rel_steps), 4) if first_error_rel_steps else None,
            "share_first_error_in_steps_1_2": round(sum(1 for s in first_error_rel_steps if s <= 2) / len(first_error_rel_steps), 4) if first_error_rel_steps else None,
            "executor_steps_taken_all": quartiles(executor_steps_taken_list),
            "executor_steps_taken_success": quartiles(executor_steps_success_list),
            "executor_steps_taken_fail": quartiles(executor_steps_fail_list),
        }

    return results_by_arm


def measure_m3_prefix_exhausted(
    arm_records: dict[str, dict[tuple[str, int], dict[str, Any]]],
    source_records: dict[tuple[str, int], dict[str, Any]],
    m_values: list[int],
):
    """M3 — prefix-exhausted population control & decomposition."""
    # 1. Episode-level metrics for each arm
    # Extract goal_pass_rate and tgc maps
    gpr_by_arm: dict[str, dict[tuple[str, int], float]] = {}
    tgc_by_arm: dict[str, dict[tuple[str, int], float]] = {}
    silenced_keys_by_arm: dict[str, set[tuple[str, int]]] = {}
    handoff_keys_by_arm: dict[str, set[tuple[str, int]]] = {}

    for m in m_values:
        arm_label = f"m{m}"
        records = arm_records.get(arm_label, {})
        gpr_by_arm[arm_label] = {}
        tgc_by_arm[arm_label] = {}
        silenced_keys_by_arm[arm_label] = set()
        handoff_keys_by_arm[arm_label] = set()

        for k, rec in records.items():
            res = rec["result"]
            gpr = res.get("goal_pass_rate")
            tgc = res.get("tgc")
            if gpr is not None:
                gpr_by_arm[arm_label][k] = float(gpr)
            if tgc is not None:
                tgc_by_arm[arm_label][k] = float(tgc)

            exec_calls = (res.get("totals") or {}).get("per_actor", {}).get("executor", {}).get("n_calls", 0)
            if exec_calls == 0:
                silenced_keys_by_arm[arm_label].add(k)
            else:
                handoff_keys_by_arm[arm_label].add(k)

    # All episodes curve
    all_episodes_curve = {}
    for m in m_values:
        arm_label = f"m{m}"
        gpr_vals = list(gpr_by_arm[arm_label].values())
        tgc_vals = list(tgc_by_arm[arm_label].values())
        all_episodes_curve[arm_label] = {
            "m": m,
            "n": len(gpr_vals),
            "silenced_count": len(silenced_keys_by_arm[arm_label]),
            "handoff_count": len(handoff_keys_by_arm[arm_label]),
            "mean_goal_pass_rate": round(statistics.fmean(gpr_vals), 4) if gpr_vals else None,
            "mean_tgc": round(statistics.fmean(tgc_vals), 4) if tgc_vals else None,
        }

    # Arm-independent key set: derived from source planner trajectory n_executed_actions > max_m
    source_action_counts = {}
    for k, rec in source_records.items():
        source_action_counts[k] = _n_executed_actions(rec["events"])

    # Define key sets
    key_sets = {}

    # Pinned to m8 handoff set
    if "m8" in handoff_keys_by_arm:
        key_sets["pinned_m8"] = {
            "name": "common_handoff_m8",
            "description": "Episodes where m8 genuinely hands off (executor n_calls > 0)",
            "keys": handoff_keys_by_arm["m8"],
            "max_m_valid": 8,
        }

    # Pinned to m9 handoff set
    if "m9" in handoff_keys_by_arm:
        key_sets["pinned_m9"] = {
            "name": "common_handoff_m9",
            "description": "Episodes where m9 genuinely hands off (executor n_calls > 0)",
            "keys": handoff_keys_by_arm["m9"],
            "max_m_valid": 9,
        }

    # Pinned to m10 handoff set (largest completed post-guard arm)
    if "m10" in handoff_keys_by_arm:
        key_sets["pinned_m10"] = {
            "name": "common_handoff_m10",
            "description": "Episodes where m10 genuinely hands off (executor n_calls > 0)",
            "keys": handoff_keys_by_arm["m10"],
            "max_m_valid": 10,
        }

    # Arm-independent source-derived sets: n_source_actions > 9 and > 10
    keys_source_gt9 = {k for k, cnt in source_action_counts.items() if cnt > 9}
    key_sets["source_gt9"] = {
        "name": "source_planner_gt_9_actions",
        "description": "Episodes where source planner trajectory has > 9 executed actions [OBSERVED hj1b_planner_20260915]",
        "keys": keys_source_gt9,
        "max_m_valid": 9,
    }
    keys_source_gt10 = {k for k, cnt in source_action_counts.items() if cnt > 10}
    key_sets["source_gt10"] = {
        "name": "source_planner_gt_10_actions",
        "description": "Episodes where source planner trajectory has > 10 executed actions [OBSERVED hj1b_planner_20260915]",
        "keys": keys_source_gt10,
        "max_m_valid": 10,
    }

    # Evaluate each key set across valid arms
    controlled_curves = {}
    for set_id, set_info in key_sets.items():
        keys = set_info["keys"]
        max_m = set_info["max_m_valid"]
        valid_m = [m for m in m_values if m <= max_m]

        curve = {}
        for m in valid_m:
            arm_label = f"m{m}"
            gpr_subset = [gpr_by_arm[arm_label][k] for k in keys if k in gpr_by_arm[arm_label]]
            tgc_subset = [tgc_by_arm[arm_label][k] for k in keys if k in tgc_by_arm[arm_label]]
            curve[arm_label] = {
                "m": m,
                "n": len(gpr_subset),
                "mean_goal_pass_rate": round(statistics.fmean(gpr_subset), 4) if gpr_subset else None,
                "mean_tgc": round(statistics.fmean(tgc_subset), 4) if tgc_subset else None,
            }

        # Contrasts: adjacent pairs and baseline (m2) to max_m
        contrasts = {}
        for i in range(len(valid_m) - 1):
            m_a, m_b = valid_m[i], valid_m[i + 1]
            label_a, label_b = f"m{m_a}", f"m{m_b}"
            pair_name = f"{label_b}_minus_{label_a}"
            base_gpr = {k: gpr_by_arm[label_a][k] for k in keys if k in gpr_by_arm[label_a]}
            other_gpr = {k: gpr_by_arm[label_b][k] for k in keys if k in gpr_by_arm[label_b]}
            diff_task = paired_diff_task(base_gpr, other_gpr)
            diff_scen = paired_diff_scenario(base_gpr, other_gpr)
            contrasts[pair_name] = {
                "arm_a": label_a,
                "arm_b": label_b,
                "n_pairs": diff_task["n_pairs"],
                "diff_pp": diff_task["diff_pp"],
                "ci95_task_pp": diff_task["ci95_pp"],
                "ci95_scenario_pp": diff_scen["ci95_pp"],
            }

        # Overall contrast m2 to max_m
        if len(valid_m) > 1:
            m_first, m_last = valid_m[0], valid_m[-1]
            label_first, label_last = f"m{m_first}", f"m{m_last}"
            overall_name = f"{label_last}_minus_{label_first}"
            base_gpr = {k: gpr_by_arm[label_first][k] for k in keys if k in gpr_by_arm[label_first]}
            other_gpr = {k: gpr_by_arm[label_last][k] for k in keys if k in gpr_by_arm[label_last]}
            diff_task = paired_diff_task(base_gpr, other_gpr)
            diff_scen = paired_diff_scenario(base_gpr, other_gpr)
            contrasts[overall_name] = {
                "arm_a": label_first,
                "arm_b": label_last,
                "n_pairs": diff_task["n_pairs"],
                "diff_pp": diff_task["diff_pp"],
                "ci95_task_pp": diff_task["ci95_pp"],
                "ci95_scenario_pp": diff_scen["ci95_pp"],
            }

        controlled_curves[set_id] = {
            "name": set_info["name"],
            "description": set_info["description"],
            "n_keys": len(keys),
            "curve": curve,
            "contrasts": contrasts,
        }

    # Mathematical Decomposition: m=2 to m_max on all episodes
    # Let E be all 114 episodes.
    # S = silenced episodes in m_max
    # H = genuinely handed-off episodes in m_max
    # Total rise = w_S * (Y_{max, S} - Y_{2, S}) + w_H * (Y_{max, H} - Y_{2, H})
    decompositions = {}
    for target_m in [m for m in [9, 10] if f"m{target_m}" in gpr_by_arm]:
        target_label = f"m{target_m}"
        S = silenced_keys_by_arm[target_label]
        H = handoff_keys_by_arm[target_label]
        N = len(gpr_by_arm[target_label])
        w_S = len(S) / N
        w_H = len(H) / N

        gpr_2 = gpr_by_arm["m2"]
        gpr_tgt = gpr_by_arm[target_label]

        y_2_all = statistics.fmean(gpr_2.values())
        y_tgt_all = statistics.fmean(gpr_tgt.values())
        delta_total_pp = (y_tgt_all - y_2_all) * 100

        y_2_S = statistics.fmean([gpr_2[k] for k in S]) if S else 0.0
        y_tgt_S = statistics.fmean([gpr_tgt[k] for k in S]) if S else 0.0
        delta_S_pp = (y_tgt_S - y_2_S) * 100
        contrib_S_pp = w_S * delta_S_pp

        y_2_H = statistics.fmean([gpr_2[k] for k in H]) if H else 0.0
        y_tgt_H = statistics.fmean([gpr_tgt[k] for k in H]) if H else 0.0
        delta_H_pp = (y_tgt_H - y_2_H) * 100
        contrib_H_pp = w_H * delta_H_pp

        decompositions[f"m2_to_m{target_m}"] = {
            "m_base": 2,
            "m_target": target_m,
            "total_episodes": N,
            "silenced_count": len(S),
            "handoff_count": len(H),
            "weight_silenced": round(w_S, 4),
            "weight_handoff": round(w_H, 4),
            "y_base_all": round(y_2_all, 4),
            "y_target_all": round(y_tgt_all, 4),
            "delta_total_pp": round(delta_total_pp, 2),
            "y_base_silenced_subset": round(y_2_S, 4),
            "y_target_silenced_subset": round(y_tgt_S, 4),
            "gain_on_silenced_subset_pp": round(delta_S_pp, 2),
            "contribution_silenced_subset_pp": round(contrib_S_pp, 2),
            "share_of_rise_from_silenced_pct": round(contrib_S_pp / delta_total_pp * 100, 1) if delta_total_pp else None,
            "y_base_handoff_subset": round(y_2_H, 4),
            "y_target_handoff_subset": round(y_tgt_H, 4),
            "gain_on_handoff_subset_pp": round(delta_H_pp, 2),
            "contribution_handoff_subset_pp": round(contrib_H_pp, 2),
            "share_of_rise_from_handoff_pct": round(contrib_H_pp / delta_total_pp * 100, 1) if delta_total_pp else None,
            "arithmetic_identity_check_pp": round(contrib_S_pp + contrib_H_pp, 2),
        }

    return {
        "all_episodes_curve": all_episodes_curve,
        "controlled_curves": controlled_curves,
        "decompositions": decompositions,
    }


def run_full_analysis():
    print("Loading data...")
    source_records = load_source_planner(SOURCE_PLANNER_DIR)
    print(f"Source planner episodes: {len(source_records)}")

    # Post-guard arms
    post_guard_m = [2, 4, 6, 7, 8, 9, 10]
    post_guard_records = {}
    for m in post_guard_m:
        p = RESULTS_DIR / f"hj12_prefix_m{m}_20260923"
        post_guard_records[f"m{m}"] = load_episode_records(p)
        print(f"Loaded post-guard m{m}: {len(post_guard_records[f'm{m}'])} episodes")

    # Pre-guard arms
    pre_guard_m = [2, 4, 6, 7, 8, 9, 10, 11]
    pre_guard_records = {}
    for m in pre_guard_m:
        p = RESULTS_DIR / f"hj12_prefix_m{m}_20260922"
        pre_guard_records[f"m{m}"] = load_episode_records(p)
        print(f"Loaded pre-guard m{m}: {len(pre_guard_records[f'm{m}'])} episodes")

    print("\nMeasuring M1 (API Novelty Front-loaded)...")
    m1_res = measure_m1_api_novelty(source_records)

    print("\nMeasuring M2 (Compounding Error Post-Handoff)...")
    m2_post = measure_m2_compounding_error(post_guard_records, post_guard_m)
    m2_pre = measure_m2_compounding_error(pre_guard_records, pre_guard_m)

    print("\nMeasuring M3 (Prefix-Exhausted Population & Controlled Sets)...")
    m3_post = measure_m3_prefix_exhausted(post_guard_records, source_records, post_guard_m)
    m3_pre = measure_m3_prefix_exhausted(pre_guard_records, source_records, pre_guard_m)

    report = {
        "generated_by": "scripts/analysis/j13_mechanism.py",
        "description": "Brief X33 Threshold Mechanism Empirical Measurements",
        "arms_used": {
            "post_guard_primary": {f"m{m}": f"/scratch/n12194778/sidekick/results/hj12_prefix_m{m}_20260923" for m in post_guard_m},
            "pre_guard_comparison": {f"m{m}": f"/scratch/n12194778/sidekick/results/hj12_prefix_m{m}_20260922" for m in pre_guard_m},
            "source_planner": str(SOURCE_PLANNER_DIR),
            "incomplete_arms": ["hj12_prefix_m11_20260923_smoke (6 episodes, excluded from primary)"],
        },
        "m1_api_novelty": m1_res,
        "m2_compounding_error": {
            "post_guard": m2_post,
            "pre_guard": m2_pre,
        },
        "m3_prefix_exhausted": {
            "post_guard": m3_post,
            "pre_guard": m3_pre,
        },
    }

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote report to {OUT_REPORT}")
    return report


if __name__ == "__main__":
    run_full_analysis()
