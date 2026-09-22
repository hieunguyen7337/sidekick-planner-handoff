#!/usr/bin/env python3
"""Threshold mechanism analysis (Brief X33): M1, M2, M3 measurements.

Analyzes why there is a threshold in prefix-handoff performance across m:
- M1: API novelty front-loading
- M2: Compounding error post-handoff
- M3: Prefix-exhausted population control & decomposition

Output:
- JSON report: --out-report (default: campaign/results/hj13_mechanism_20260923.report.json)
- Markdown report: --out-md (default: campaign/results/hj13_mechanism_20260923.md)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

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

DEFAULT_RESULTS_DIR = Path("/scratch/n12194778/sidekick/results")
DEFAULT_SOURCE_DIR = DEFAULT_RESULTS_DIR / "hj1b_planner_20260915" / "planner_alone"
DEFAULT_OUT_REPORT = REPO / "campaign/results/hj13_mechanism_20260923.report.json"
DEFAULT_OUT_MD = REPO / "campaign/results/hj13_mechanism_20260923.md"


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


def parse_decompose_pairs(val: str | list[tuple[int, int]] | list[str] | None) -> list[tuple[int, int]] | None:
    """Parse comma-separated base:target decomposition pairs.
    
    Accepts:
    - String like 'm6:m9,m6:m11' or '6:9,6:11'
    - List of tuples/strings like [(6, 9), (6, 11)] or ['m6:m9', 'm6:m11']
    - None or empty string -> returns None
    """
    if val is None:
        return None
    if isinstance(val, list):
        pairs: list[tuple[int, int]] = []
        for item in val:
            if isinstance(item, str):
                p = parse_decompose_pairs(item)
                if p:
                    pairs.extend(p)
            elif isinstance(item, (tuple, list)) and len(item) == 2:
                b = int(str(item[0]).strip().lstrip("mM"))
                t = int(str(item[1]).strip().lstrip("mM"))
                pairs.append((b, t))
        return pairs if pairs else None
    val = val.strip()
    if not val:
        return None
    pairs = []
    for item in val.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"Invalid decomposition pair {item!r}, expected 'base:target'")
        b_str, t_str = item.split(":", 1)
        b = int(b_str.strip().lstrip("mM"))
        t = int(t_str.strip().lstrip("mM"))
        pairs.append((b, t))
    return pairs


def paired_diff_task(
    base: dict[tuple[str, int], float],
    other: dict[tuple[str, int], float],
    n_boot: int = BOOTSTRAP,
    seed: int = SEED,
) -> dict[str, Any]:
    """Task-clustered paired bootstrap diff (other - base) in percentage points."""
    keys = sorted(set(base) & set(other))
    if not keys:
        return {"n_pairs": 0, "n_clusters": 0, "diff_pp": None, "ci95_pp": None}
    diffs = [other[k] - base[k] for k in keys]
    point = statistics.fmean(diffs)

    by_task: dict[str, list[float]] = {}
    for (t, _s), d in zip(keys, diffs):
        by_task.setdefault(t, []).append(d)
    tasks = sorted(by_task)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [
            val
            for t in (tasks[rng.randrange(len(tasks))] for _ in range(len(tasks)))
            for val in by_task[t]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return {
        "n_pairs": len(diffs),
        "n_clusters": len(tasks),
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
    }


def paired_diff_scenario(
    base: dict[tuple[str, int], float],
    other: dict[tuple[str, int], float],
    n_boot: int = BOOTSTRAP,
    seed: int = SEED,
) -> dict[str, Any]:
    """Scenario-clustered paired bootstrap diff (other - base) in percentage points."""
    keys = sorted(set(base) & set(other))
    if not keys:
        return {"n_pairs": 0, "n_clusters": 0, "diff_pp": None, "ci95_pp": None}
    diffs = [other[k] - base[k] for k in keys]
    point = statistics.fmean(diffs)

    by_scenario: dict[str, list[float]] = {}
    for (t, _s), d in zip(keys, diffs):
        by_scenario.setdefault(scenario_of(t), []).append(d)
    scenarios = sorted(by_scenario)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [
            val
            for s in (scenarios[rng.randrange(len(scenarios))] for _ in range(len(scenarios)))
            for val in by_scenario[s]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return {
        "n_pairs": len(diffs),
        "n_clusters": len(scenarios),
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
    }


def _extract_report_facts_from_events_file(events_path: Path) -> dict[str, Any]:
    """Extract handoff facts from the last report event of the last attempt in events.jsonl.
    
    Mirrors scripts/analysis/j8_frontier.py:747-790 (_handoff_facts_from_events_text).
    """
    if not events_path.is_file():
        return {
            "has_report": False,
            "handoff_occurred": None,
            "effective_m": None,
            "n_source_actions": None,
        }
    try:
        events = _events_of_last_attempt(events_path)
    except Exception:
        events = []

    if not events:
        try:
            text = events_path.read_text(encoding="utf-8")
            raw_events = []
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            last_start = 0
            for idx, ev in enumerate(raw_events):
                if isinstance(ev, dict) and ev.get("event_type") == "run_start":
                    last_start = idx
            raw_events = raw_events[last_start:]
            for ev in reversed(raw_events):
                if isinstance(ev, dict) and ev.get("event_type") == "report":
                    payload = ev.get("payload") or {}
                    return {
                        "has_report": True,
                        "handoff_occurred": bool(payload["handoff_occurred"]) if payload.get("handoff_occurred") is not None else None,
                        "effective_m": int(payload["effective_m"]) if payload.get("effective_m") is not None else None,
                        "n_source_actions": int(payload["n_source_actions"]) if payload.get("n_source_actions") is not None else None,
                    }
        except Exception:
            pass

    for ev in reversed(events):
        ev_type = getattr(ev, "event_type", None) or (ev.get("event_type") if isinstance(ev, dict) else None)
        if ev_type == "report":
            payload = getattr(ev, "payload", None) or (ev.get("payload") if isinstance(ev, dict) else {}) or {}
            ho = payload.get("handoff_occurred")
            em = payload.get("effective_m")
            nsa = payload.get("n_source_actions")
            return {
                "has_report": True,
                "handoff_occurred": bool(ho) if ho is not None else None,
                "effective_m": int(em) if em is not None else None,
                "n_source_actions": int(nsa) if nsa is not None else None,
            }

    return {
        "has_report": False,
        "handoff_occurred": None,
        "effective_m": None,
        "n_source_actions": None,
    }


def load_handoff_flags(arm_root: Path | str) -> dict[tuple[str, int], dict[str, Any]]:
    """Load handoff flags from events.jsonl next to each result.json under arm_root.
    
    Mirrors scripts/analysis/j8_frontier.py:747-838 (_handoff_facts_from_events_text, attach_handoff_fields).
    Returns dict[(task_id, seed), {handoff_occurred, effective_m, n_source_actions, has_report}].
    """
    root = Path(arm_root)
    flags: dict[tuple[str, int], dict[str, Any]] = {}
    if not root.exists():
        return flags

    for res_path in sorted(root.rglob("result.json")):
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
            pass

        events_path = d / "events.jsonl"
        facts = _extract_report_facts_from_events_file(events_path)
        flags[(task_id, seed)] = facts

    return flags


def extract_handoff_facts(rec: dict[str, Any]) -> dict[str, Any]:
    """Extract handoff facts from an episode record dict.
    
    Checks rec fields first, then falls back to inspecting rec['events'] for a report event.
    """
    if "has_report" in rec:
        return {
            "has_report": bool(rec["has_report"]),
            "handoff_occurred": rec.get("handoff_occurred"),
            "effective_m": rec.get("effective_m"),
            "n_source_actions": rec.get("n_source_actions"),
        }
    events = rec.get("events") or []
    for ev in reversed(events):
        ev_type = getattr(ev, "event_type", None) or (ev.get("event_type") if isinstance(ev, dict) else None)
        if ev_type == "report":
            payload = getattr(ev, "payload", None) or (ev.get("payload") if isinstance(ev, dict) else {}) or {}
            ho = payload.get("handoff_occurred")
            em = payload.get("effective_m")
            nsa = payload.get("n_source_actions")
            return {
                "has_report": True,
                "handoff_occurred": bool(ho) if ho is not None else None,
                "effective_m": int(em) if em is not None else None,
                "n_source_actions": int(nsa) if nsa is not None else None,
            }
    if "handoff_occurred" in rec and rec["handoff_occurred"] is not None:
        return {
            "has_report": True,
            "handoff_occurred": bool(rec["handoff_occurred"]),
            "effective_m": rec.get("effective_m"),
            "n_source_actions": rec.get("n_source_actions"),
        }
    return {
        "has_report": False,
        "handoff_occurred": None,
        "effective_m": None,
        "n_source_actions": None,
    }


def validate_arm_population(
    records: dict[tuple[str, int], dict[str, Any]],
    arm_name: str = "",
) -> None:
    """Validate handoff population integrity for a loaded arm.
    
    Fatal conditions:
    1. A missing report event in any episode.
    2. Zero episodes with handoff_occurred is True while any episode has executor n_calls > 0.
    3. Any episode with handoff_occurred is True and executor n_calls == 0.
    """
    n_total = len(records)
    if n_total == 0:
        return

    n_handoff = 0
    n_exec_calls_gt_0 = 0
    handoff_true_zero_calls: list[tuple[str, int]] = []

    for (task_id, seed), rec in sorted(records.items()):
        facts = extract_handoff_facts(rec)
        if not facts["has_report"] or facts["handoff_occurred"] is None:
            raise SystemExit(
                f"Fatal: arm {arm_name!r} episode task_id={task_id!r} seed={seed} "
                f"is missing a report event in events.jsonl"
            )

        handoff_occurred = (facts["handoff_occurred"] is True)
        res = rec.get("result") or {}
        totals = res.get("totals") or {}
        per_actor = totals.get("per_actor") or {}
        exec_actor = per_actor.get("executor") or {}
        n_calls = exec_actor.get("n_calls", 0)

        if handoff_occurred:
            n_handoff += 1
            if n_calls == 0:
                handoff_true_zero_calls.append((task_id, seed))
        if n_calls > 0:
            n_exec_calls_gt_0 += 1

    if n_handoff == 0 and n_exec_calls_gt_0 > 0:
        raise SystemExit(
            f"Fatal: arm {arm_name!r} has 0 handoff episodes (handoff_occurred is True) "
            f"while {n_exec_calls_gt_0}/{n_total} episodes have executor n_calls > 0"
        )

    if handoff_true_zero_calls:
        raise SystemExit(
            f"Fatal: arm {arm_name!r} has {len(handoff_true_zero_calls)}/{n_total} episodes "
            f"with handoff_occurred is True but executor n_calls == 0: {handoff_true_zero_calls}"
        )


def load_episode_records(root: Path, arm_name: str = "") -> dict[tuple[str, int], dict[str, Any]]:
    """Load all (task_id, seed) records from an arm directory.
    
    Prefers result.json's task_id and seed when present.
    Loads handoff flags from events.jsonl via load_handoff_flags.
    Validates population integrity (raising SystemExit on violation).
    """
    flags = load_handoff_flags(root)
    records = {}
    for res_path in sorted(root.rglob("result.json")):
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
        ep_flags = flags.get((task_id, seed), {})
        records[(task_id, seed)] = {
            "result": res,
            "events": events,
            "events_path": str(events_path),
            "task_id": task_id,
            "seed": seed,
            "handoff_occurred": ep_flags.get("handoff_occurred"),
            "effective_m": ep_flags.get("effective_m"),
            "n_source_actions": ep_flags.get("n_source_actions"),
            "has_report": ep_flags.get("has_report", False),
        }
    validate_arm_population(records, arm_name=arm_name or root.name)
    return records


def load_source_planner(root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """Load source planner episodes.
    
    Verified layout: <root>/<seed>/<task_id>/result.json
    where seed is parent dir (e.g. 1, 2) and task_id is leaf dir (e.g. 0d8a4ee_1).
    Prefers result.json's task_id and seed when present.
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


def discover_arms(
    results_dir: Path,
    receiver: Literal["tailored", "zeroshot"] = "tailored",
    m_range: range | list[int] = range(2, 12),
) -> tuple[dict[str, list[int]], dict[str, dict[str, Path]], list[dict[str, Any]]]:
    """Discover completed arms having exactly 114 result.json files."""
    included_m: dict[str, list[int]] = {"primary": [], "comparison": []}
    arm_paths: dict[str, dict[str, Path]] = {"primary": {}, "comparison": {}}
    excluded: list[dict[str, Any]] = []

    if receiver == "tailored":
        primary_tmpl = "hj12_prefix_m{m}_20260923/prefix_handoff"
        comparison_tmpl = "hj12_prefix_m{m}_20260922/prefix_handoff"
    elif receiver == "zeroshot":
        primary_tmpl = "hj13_prefix_zs_m{m}_20260923/prefix_handoff"
        comparison_tmpl = "hj13_prefix_zs_m{m}_20260922/prefix_handoff"
    else:
        raise ValueError(f"Unknown receiver: {receiver}")

    for group_name, tmpl in [("primary", primary_tmpl), ("comparison", comparison_tmpl)]:
        for m in m_range:
            rel_path = tmpl.format(m=m)
            arm_dir = results_dir / rel_path
            n_results = 0
            if arm_dir.is_dir():
                n_results = len(list(arm_dir.rglob("result.json")))

            if n_results == 114:
                included_m[group_name].append(m)
                arm_paths[group_name][f"m{m}"] = arm_dir
            else:
                excluded.append({
                    "group": group_name,
                    "m": m,
                    "path": str(arm_dir),
                    "result_count": n_results,
                    "reason": f"result_count ({n_results}) != 114",
                })

    return included_m, arm_paths, excluded


def extract_actions_api_names(events: list[Any]) -> list[str | None]:
    out = []
    for e in events:
        if e.event_type != "action":
            continue
        code = (e.payload or {}).get("code") or ""
        m = API_RE.search(code)
        out.append(f"{m.group(1)}.{m.group(2)}" if m else None)
    return out


def measure_m1_api_novelty(source_records: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
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


def measure_m2_compounding_error(
    arm_records: dict[str, dict[tuple[str, int], dict[str, Any]]],
    m_values: list[int],
) -> dict[str, Any]:
    """M2 — compounding error after handoff.
    
    Measure, per arm and per episode, the step index of the executor's first error
    after handoff, and the number of executor steps remaining.
    Uses authoritative handoff_occurred flag with n_calls == 0 as diagnostic.
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
        divergent_keys: list[tuple[str, int]] = []
        post_complete_keys: list[tuple[str, int]] = []

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
            handoff_facts = extract_handoff_facts(rec)
            handoff_occurred = (handoff_facts["handoff_occurred"] is True)

            # Diagnostic: check disagreement between handoff_occurred and (n_calls > 0)
            if handoff_occurred != (n_calls > 0):
                divergent_keys.append((task_id, seed))
            if not handoff_occurred and n_calls > 0:
                post_complete_keys.append((task_id, seed))

            if not handoff_occurred:
                silenced_episodes += 1
                continue

            handoff_episodes += 1
            events = rec["events"]

            # Identify executor events (after handoff)
            # Find the first error in executor observations (emitted by environment)
            first_err_rel = -1
            exec_action_count = 0

            for e in events:
                if e.event_type == "action" and e.actor == "executor":
                    exec_action_count += 1
                elif e.event_type == "observation" and e.actor == "environment":
                    is_err = False
                    if e.error_type:
                        is_err = True
                    text = (e.payload or {}).get("text") or ""
                    if text.startswith("Execution failed"):
                        is_err = True
                    if is_err and first_err_rel < 0 and exec_action_count > 0:
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
            "divergence_count": len(divergent_keys),
            "divergence_keys": [list(k) for k in sorted(divergent_keys)],
            "post_complete_executor_actions": len(post_complete_keys),
            "post_complete_keys": [list(k) for k in sorted(post_complete_keys)],
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
    n_boot: int = BOOTSTRAP,
    seed: int = SEED,
    decompose_pairs: str | list[tuple[int, int]] | list[str] | None = None,
    receiver: str = "",
) -> dict[str, Any]:
    """M3 — prefix-exhausted population control & decomposition."""
    gpr_by_arm: dict[str, dict[tuple[str, int], float]] = {}
    tgc_by_arm: dict[str, dict[tuple[str, int], float]] = {}
    silenced_keys_by_arm: dict[str, set[tuple[str, int]]] = {}
    handoff_keys_by_arm: dict[str, set[tuple[str, int]]] = {}
    divergence_keys_by_arm: dict[str, list[tuple[str, int]]] = {}
    post_complete_keys_by_arm: dict[str, list[tuple[str, int]]] = {}

    for m in m_values:
        arm_label = f"m{m}"
        records = arm_records.get(arm_label, {})
        gpr_by_arm[arm_label] = {}
        tgc_by_arm[arm_label] = {}
        silenced_keys_by_arm[arm_label] = set()
        handoff_keys_by_arm[arm_label] = set()
        divergence_keys_by_arm[arm_label] = []
        post_complete_keys_by_arm[arm_label] = []

        for k, rec in records.items():
            res = rec["result"]
            gpr = res.get("goal_pass_rate")
            tgc = res.get("tgc")
            if gpr is not None:
                gpr_by_arm[arm_label][k] = float(gpr)
            if tgc is not None:
                tgc_by_arm[arm_label][k] = float(tgc)

            handoff_facts = extract_handoff_facts(rec)
            handoff_occurred = (handoff_facts["handoff_occurred"] is True)
            exec_calls = (res.get("totals") or {}).get("per_actor", {}).get("executor", {}).get("n_calls", 0)

            # Diagnostic divergence
            if handoff_occurred != (exec_calls > 0):
                divergence_keys_by_arm[arm_label].append(k)
            if not handoff_occurred and exec_calls > 0:
                post_complete_keys_by_arm[arm_label].append(k)

            if handoff_occurred:
                handoff_keys_by_arm[arm_label].add(k)
            else:
                silenced_keys_by_arm[arm_label].add(k)

    # All episodes curve
    all_episodes_curve = {}
    for m in m_values:
        arm_label = f"m{m}"
        gpr_vals = list(gpr_by_arm[arm_label].values())
        tgc_vals = list(tgc_by_arm[arm_label].values())
        divs = divergence_keys_by_arm[arm_label]
        pcs = post_complete_keys_by_arm[arm_label]
        all_episodes_curve[arm_label] = {
            "m": m,
            "n": len(gpr_vals),
            "silenced_count": len(silenced_keys_by_arm[arm_label]),
            "handoff_count": len(handoff_keys_by_arm[arm_label]),
            "divergence_count": len(divs),
            "divergence_keys": [list(k) for k in sorted(divs)],
            "post_complete_executor_actions": len(pcs),
            "post_complete_keys": [list(k) for k in sorted(pcs)],
            "mean_goal_pass_rate": round(statistics.fmean(gpr_vals), 4) if gpr_vals else None,
            "mean_tgc": round(statistics.fmean(tgc_vals), 4) if tgc_vals else None,
        }

    # Source planner action counts
    source_action_counts = {}
    for k, rec in source_records.items():
        source_action_counts[k] = _n_executed_actions(rec["events"])

    # Derive largest and second-largest discovered m for thresholds
    sorted_m = sorted(m_values)
    max_m_1 = sorted_m[-1] if sorted_m else None
    max_m_2 = sorted_m[-2] if len(sorted_m) >= 2 else None

    # Define key sets dynamically
    key_sets = {}

    # Pinned key sets for discovered arms
    for m in sorted_m:
        arm_label = f"m{m}"
        if arm_label in handoff_keys_by_arm:
            key_sets[f"pinned_m{m}"] = {
                "name": f"common_handoff_m{m}",
                "description": f"Episodes where m{m} genuinely hands off (handoff_occurred is True)",
                "keys": handoff_keys_by_arm[arm_label],
                "max_m_valid": m,
            }

    # Arm-independent source-derived sets: derived from largest and second-largest discovered m
    derived_thresholds: list[int] = []
    for t in (max_m_2, max_m_1):
        if t is not None and t not in derived_thresholds:
            derived_thresholds.append(t)

    for t in derived_thresholds:
        keys_source_gt = {k for k, cnt in source_action_counts.items() if cnt > t}
        key_sets[f"source_gt{t}"] = {
            "name": f"source_planner_gt_{t}_actions",
            "description": f"Episodes where source planner trajectory has > {t} executed actions [OBSERVED hj1b_planner_20260915]",
            "keys": keys_source_gt,
            "max_m_valid": t,
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

        # Contrasts: adjacent pairs and baseline (first discovered m) to max_m
        contrasts = {}
        for i in range(len(valid_m) - 1):
            m_a, m_b = valid_m[i], valid_m[i + 1]
            label_a, label_b = f"m{m_a}", f"m{m_b}"
            pair_name = f"{label_b}_minus_{label_a}"
            base_gpr = {k: gpr_by_arm[label_a][k] for k in keys if k in gpr_by_arm[label_a]}
            other_gpr = {k: gpr_by_arm[label_b][k] for k in keys if k in gpr_by_arm[label_b]}
            diff_task = paired_diff_task(base_gpr, other_gpr, n_boot=n_boot, seed=seed)
            diff_scen = paired_diff_scenario(base_gpr, other_gpr, n_boot=n_boot, seed=seed)
            contrasts[pair_name] = {
                "arm_a": label_a,
                "arm_b": label_b,
                "n_pairs": diff_task["n_pairs"],
                "diff_pp": diff_task["diff_pp"],
                "ci95_task_pp": diff_task["ci95_pp"],
                "ci95_scenario_pp": diff_scen["ci95_pp"],
            }

        # Overall contrast from first valid m to last valid m
        if len(valid_m) > 1:
            m_first, m_last = valid_m[0], valid_m[-1]
            label_first, label_last = f"m{m_first}", f"m{m_last}"
            overall_name = f"{label_last}_minus_{label_first}"
            base_gpr = {k: gpr_by_arm[label_first][k] for k in keys if k in gpr_by_arm[label_first]}
            other_gpr = {k: gpr_by_arm[label_last][k] for k in keys if k in gpr_by_arm[label_last]}
            diff_task = paired_diff_task(base_gpr, other_gpr, n_boot=n_boot, seed=seed)
            diff_scen = paired_diff_scenario(base_gpr, other_gpr, n_boot=n_boot, seed=seed)
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

    # Mathematical Decomposition: from baseline m (first discovered) to discovered target thresholds,
    # or explicitly requested decompose_pairs
    decompositions = {}
    parsed_pairs = parse_decompose_pairs(decompose_pairs)
    available_m = sorted(set(m_values))

    if parsed_pairs is not None:
        for b, t in parsed_pairs:
            if b not in available_m:
                raise SystemExit(
                    f"Fatal: requested decomposition base depth {b} for receiver {receiver!r} "
                    f"is not among available depths: {available_m}"
                )
            if t not in available_m:
                raise SystemExit(
                    f"Fatal: requested decomposition target depth {t} for receiver {receiver!r} "
                    f"is not among available depths: {available_m}"
                )
        computed_pairs = parsed_pairs
    else:
        m_base = sorted_m[0] if sorted_m else 2
        target_ms = [m for m in derived_thresholds if f"m{m}" in gpr_by_arm and m != m_base]
        computed_pairs = [(m_base, target_m) for target_m in target_ms]

    for base_m, target_m in computed_pairs:
        target_label = f"m{target_m}"
        base_label = f"m{base_m}"
        S = silenced_keys_by_arm.get(target_label, set())
        H = handoff_keys_by_arm.get(target_label, set())
        N = len(gpr_by_arm.get(target_label, {}))
        if N == 0:
            continue
        w_S = len(S) / N
        w_H = len(H) / N

        gpr_base = gpr_by_arm.get(base_label, {})
        gpr_tgt = gpr_by_arm.get(target_label, {})

        y_base_all = statistics.fmean(gpr_base.values()) if gpr_base else 0.0
        y_tgt_all = statistics.fmean(gpr_tgt.values()) if gpr_tgt else 0.0
        delta_total_pp = (y_tgt_all - y_base_all) * 100

        y_base_S = statistics.fmean([gpr_base[k] for k in S if k in gpr_base]) if S else 0.0
        y_tgt_S = statistics.fmean([gpr_tgt[k] for k in S if k in gpr_tgt]) if S else 0.0
        delta_S_pp = (y_tgt_S - y_base_S) * 100
        contrib_S_pp = w_S * delta_S_pp

        y_base_H = statistics.fmean([gpr_base[k] for k in H if k in gpr_base]) if H else 0.0
        y_tgt_H = statistics.fmean([gpr_tgt[k] for k in H if k in gpr_tgt]) if H else 0.0
        delta_H_pp = (y_tgt_H - y_base_H) * 100
        contrib_H_pp = w_H * delta_H_pp

        decompositions[f"m{base_m}_to_m{target_m}"] = {
            "m_base": base_m,
            "m_target": target_m,
            "total_episodes": N,
            "silenced_count": len(S),
            "handoff_count": len(H),
            "weight_silenced": round(w_S, 4),
            "weight_handoff": round(w_H, 4),
            "y_base_all": round(y_base_all, 4),
            "y_target_all": round(y_tgt_all, 4),
            "delta_total_pp": round(delta_total_pp, 2),
            "y_base_silenced_subset": round(y_base_S, 4),
            "y_target_silenced_subset": round(y_tgt_S, 4),
            "gain_on_silenced_subset_pp": round(delta_S_pp, 2),
            "contribution_silenced_subset_pp": round(contrib_S_pp, 2),
            "share_of_rise_from_silenced_pct": round(contrib_S_pp / delta_total_pp * 100, 1) if delta_total_pp else None,
            "y_base_handoff_subset": round(y_base_H, 4),
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


def _fmt(val: Any, spec: str = "") -> str:
    """Format a value with a format spec, rendering None as 'n/a'."""
    if val is None:
        return "n/a"
    if spec:
        return format(val, spec)
    return str(val)


def generate_markdown_report(report: dict[str, Any]) -> str:
    """Format report into human-readable markdown."""
    lines: list[str] = [
        "# HJ-13 Threshold Mechanism Empirical Measurements",
        "",
        f"Generated by `{report.get('generated_by')}` for receiver `{report.get('receiver')}`.",
        "",
        "## Arms Summary",
        "",
    ]
    arms_used = report.get("arms_used", {})
    lines.append(f"- **Primary arms**: {list(arms_used.get('primary', {}).keys())}")
    if arms_used.get("comparison"):
        lines.append(f"- **Comparison arms**: {list(arms_used.get('comparison', {}).keys())}")
    lines.append(f"- **Source planner**: `{arms_used.get('source_planner')}`")
    lines.append(f"- **Excluded arms**: {len(arms_used.get('excluded_arms', []))} entries")
    for excl in arms_used.get("excluded_arms", []):
        lines.append(f"  - `{excl.get('path')}` (results: {excl.get('result_count')}, reason: {excl.get('reason')})")

    lines.extend([
        "",
        "## M1: API Novelty Front-Loading",
        "",
    ])
    m1 = report.get("m1_api_novelty", {})
    lines.append(f"- Total first uses: {_fmt(m1.get('total_first_uses'))} across {_fmt(m1.get('n_episodes'))} episodes (mean {_fmt(m1.get('mean_first_uses_per_episode'))} per episode)")
    lines.append(f"- First use position distribution: {m1.get('first_use_position_distribution')}")
    lines.append("")
    lines.append("| Bin (Actions) | First Uses | Total Actions | Share of All First Uses | Novel Share in Bin |")
    lines.append("|---|---|---|---|---|")
    for b_name, b_val in m1.get("binned", {}).items():
        lines.append(f"| {b_name} | {_fmt(b_val.get('first_uses'))} | {_fmt(b_val.get('total_actions'))} | {_fmt(b_val.get('share_of_all_first_uses'), '.2%')} | {_fmt(b_val.get('novel_share_in_bin'), '.2%')} |")

    lines.extend([
        "",
        "## M2: Compounding Error Post-Handoff",
        "",
    ])
    m2_pri = report.get("m2_compounding_error", {}).get("primary", {})
    lines.append("| Arm | Handoff Episodes | Silenced | Divergence | Post-Complete Exec | Error Rate on Handoff | Error @ Step 1 | Error @ Steps 1-2 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for arm, data in m2_pri.items():
        lines.append(
            f"| {arm} | {_fmt(data.get('handoff_episodes'))} | {_fmt(data.get('silenced_episodes'))} | {_fmt(data.get('divergence_count'))} | "
            f"{_fmt(data.get('post_complete_executor_actions'))} | "
            f"{_fmt(data.get('error_rate_on_handoff'), '.2%')} | {_fmt(data.get('share_first_error_at_step_1'), '.2%')} | "
            f"{_fmt(data.get('share_first_error_in_steps_1_2'), '.2%')} |"
        )
    lines.append("")
    lines.append("*Note: `post_complete_executor_actions` records episodes with `handoff_occurred is False` and `n_calls > 0` (documented pre-F0(a) replay behaviour).*")

    lines.extend([
        "",
        "## M3: Mathematical Decomposition",
        "",
    ])
    m3_decomp = report.get("m3_prefix_exhausted", {}).get("primary", {}).get("decompositions", {})
    for decomp_name, d in m3_decomp.items():
        lines.append(f"### Decomposition `{decomp_name}`")
        lines.append(f"- Total rise: **{_fmt(d.get('delta_total_pp'))} pp** (from {_fmt(d.get('y_base_all'), '.4f')} to {_fmt(d.get('y_target_all'), '.4f')})")
        lines.append(f"- Silenced contribution: **{_fmt(d.get('contribution_silenced_subset_pp'))} pp** ({_fmt(d.get('share_of_rise_from_silenced_pct'))}% of rise, weight: {_fmt(d.get('weight_silenced'))})")
        lines.append(f"- Handoff contribution: **{_fmt(d.get('contribution_handoff_subset_pp'))} pp** ({_fmt(d.get('share_of_rise_from_handoff_pct'))}% of rise, weight: {_fmt(d.get('weight_handoff'))})")
        lines.append(f"- Arithmetic check (sum): {_fmt(d.get('arithmetic_identity_check_pp'))} pp")
        lines.append("")

    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="HJ13 Prefix Mechanism Analysis (M1, M2, M3)")
    p.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help=f"Base results directory (default: {DEFAULT_RESULTS_DIR})",
    )
    p.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Source planner directory (default: <results-dir>/hj1b_planner_20260915/planner_alone)",
    )
    p.add_argument(
        "--out-report",
        type=Path,
        default=DEFAULT_OUT_REPORT,
        help=f"Output report JSON path (default: {DEFAULT_OUT_REPORT})",
    )
    p.add_argument(
        "--out-md",
        type=Path,
        default=DEFAULT_OUT_MD,
        help=f"Output report markdown path (default: {DEFAULT_OUT_MD})",
    )
    p.add_argument(
        "--n-boot",
        type=int,
        default=BOOTSTRAP,
        help=f"Number of bootstrap resamples (default: {BOOTSTRAP})",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=SEED,
        help=f"Bootstrap random seed (default: {SEED})",
    )
    p.add_argument(
        "--receiver",
        choices=["tailored", "zeroshot"],
        default="tailored",
        help="Receiver type for arm discovery: tailored (hj12) or zeroshot (hj13_zs)",
    )
    p.add_argument(
        "--decompose-pairs",
        type=str,
        default=None,
        help="Comma-separated base:target pairs for M3 decomposition (e.g. 'm6:m9,m6:m11')",
    )
    return p.parse_args(argv)


def run_full_analysis(args: argparse.Namespace | None = None) -> dict[str, Any]:
    if args is None:
        args = parse_args()

    validate_output_path(args.out_report)
    validate_output_path(args.out_md)

    source_dir = args.source_dir or (args.results_dir / "hj1b_planner_20260915" / "planner_alone")

    print(f"Receiver: {args.receiver}")
    print(f"Results directory: {args.results_dir}")
    print(f"Source planner directory: {source_dir}")

    # Runtime arm discovery
    included_m, arm_paths, excluded = discover_arms(args.results_dir, receiver=args.receiver)
    print(f"\nDiscovered primary arms: {included_m['primary']}")
    print(f"Discovered comparison arms: {included_m['comparison']}")
    if excluded:
        print(f"Excluded {len(excluded)} candidate arms (count != 114)")

    # Load source planner records
    print("\nLoading source planner data...")
    source_records = load_source_planner(source_dir)
    print(f"Loaded source planner episodes: {len(source_records)}")

    # Load primary arm records
    primary_records = {}
    for arm_label, path in arm_paths["primary"].items():
        recs = load_episode_records(path, arm_name=arm_label)
        primary_records[arm_label] = recs
        print(f"Loaded primary {arm_label}: {len(recs)} episodes from {path}")

    # Load comparison arm records
    comparison_records = {}
    for arm_label, path in arm_paths["comparison"].items():
        recs = load_episode_records(path, arm_name=arm_label)
        comparison_records[arm_label] = recs
        print(f"Loaded comparison {arm_label}: {len(recs)} episodes from {path}")

    # Measure M1
    print("\nMeasuring M1 (API Novelty Front-loaded)...")
    m1_res = measure_m1_api_novelty(source_records)

    # Measure M2
    print("\nMeasuring M2 (Compounding Error Post-Handoff)...")
    m2_primary = measure_m2_compounding_error(primary_records, included_m["primary"])
    m2_comparison = measure_m2_compounding_error(comparison_records, included_m["comparison"]) if comparison_records else {}

    # Measure M3
    print("\nMeasuring M3 (Prefix-Exhausted Population & Controlled Sets)...")
    m3_primary = measure_m3_prefix_exhausted(
        primary_records,
        source_records,
        included_m["primary"],
        n_boot=args.n_boot,
        seed=args.seed,
        decompose_pairs=args.decompose_pairs,
        receiver=args.receiver,
    )
    m3_comparison = (
        measure_m3_prefix_exhausted(
            comparison_records,
            source_records,
            included_m["comparison"],
            n_boot=args.n_boot,
            seed=args.seed,
            decompose_pairs=args.decompose_pairs,
            receiver=args.receiver,
        )
        if comparison_records
        else {}
    )

    report = {
        "generated_by": "scripts/analysis/j13_mechanism.py",
        "description": "Brief X33 Threshold Mechanism Empirical Measurements",
        "receiver": args.receiver,
        "arms_used": {
            "primary": {f"m{m}": str(arm_paths["primary"][f"m{m}"]) for m in included_m["primary"]},
            "comparison": {f"m{m}": str(arm_paths["comparison"][f"m{m}"]) for m in included_m["comparison"]},
            "source_planner": str(source_dir),
            "excluded_arms": excluded,
        },
        "m1_api_novelty": m1_res,
        "m2_compounding_error": {
            "primary": m2_primary,
            "comparison": m2_comparison,
        },
        "m3_prefix_exhausted": {
            "primary": m3_primary,
            "comparison": m3_comparison,
        },
    }

    if args.out_report:
        args.out_report.parent.mkdir(parents=True, exist_ok=True)
        args.out_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote report JSON to {args.out_report}")

    if args.out_md:
        try:
            md_text = generate_markdown_report(report)
            args.out_md.parent.mkdir(parents=True, exist_ok=True)
            args.out_md.write_text(md_text, encoding="utf-8")
            print(f"Wrote report markdown to {args.out_md}")
        except Exception as e:
            print(f"Warning: failed to generate markdown report: {e}", file=sys.stderr)

    return report


if __name__ == "__main__":
    run_full_analysis(parse_args())
