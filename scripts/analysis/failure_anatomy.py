#!/usr/bin/env python3
"""Failure anatomy (brief X3): where the executor breaks and what "hard" means.

Read-only over three results trees; writes one JSON to
campaign/results/failure_anatomy_dev_20260921.json. Standard library only.
Uses sidekick.replay._events_of_last_attempt (events after the LAST run_start)
to avoid double-counting appended, dead attempts.
"""

from __future__ import annotations

import importlib.util
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from sidekick.replay import _events_of_last_attempt  # noqa: E402

_hj1_spec = importlib.util.spec_from_file_location(
    "hj1_gate", REPO / "scripts" / "setup" / "hj1_gate.py"
)
_hj1_mod = importlib.util.module_from_spec(_hj1_spec)
assert _hj1_spec is not None and _hj1_spec.loader is not None
_hj1_spec.loader.exec_module(_hj1_mod)
paired_diff = _hj1_mod.paired_diff

ARMS = {
    "sft_plan_iaware": Path(
        "/scratch/n12194778/sidekick/results/hj8_sft_plan_bplus_20260921iaware"
    ),
    "fixed_k_10_iaware": Path(
        "/scratch/n12194778/sidekick/results/hj8_fixed_k_10_20260921iaware"
    ),
    "planner_alone": Path(
        "/scratch/n12194778/sidekick/results/hj1b_planner_20260915"
    ),
}
OUT_PATH = REPO / "campaign/results/failure_anatomy_dev_20260921.json"

# Documented API-name extraction regex (brief section 4).
API_RE = re.compile(r"apis\.([a-z][a-z_0-9]*)\.([A-Za-z_][A-Za-z_0-9]*)\s*\(")
API_RE_STR = API_RE.pattern

EXECUTOR_ARMS = ("sft_plan_iaware", "fixed_k_10_iaware")

TERMINATION_KEYS = (
    "limit", "crash", "timeout", "parse_error", "api_error", "null",
)
TERMINATION_NOTE = (
    "limit is deliberately not treated as broken "
    "(scripts/setup/campaign_summarize.py:33: "
    'BROKEN = {"api_error", "timeout", "crash", "parse_error"} — '
    "an episode that spent its step budget is a real outcome, not a broken run)."
)


def quartiles(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)

    def q(p):
        return xs[min(n - 1, int(round(p * (n - 1))))]

    return {"min": xs[0], "p25": q(0.25), "p50": q(0.50),
            "p75": q(0.75), "max": xs[-1]}


def load_arm(arm: str):
    """({(task_id, seed): record}, exclusions)."""
    root = ARMS[arm]
    records, excluded = {}, []
    for res_file in sorted(root.glob("*/*/*/result.json")):
        d = res_file.parent
        seed, task_id = d.parent.name, d.name
        try:
            result = json.loads(res_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            excluded.append({"arm": arm, "task_id": task_id, "seed": seed,
                             "reason": f"result.json unreadable: {exc}"})
            continue
        events_file = d / "events.jsonl"
        if not events_file.is_file():
            excluded.append({"arm": arm, "task_id": task_id, "seed": seed,
                             "reason": "events.jsonl missing"})
            continue
        try:
            events = _events_of_last_attempt(events_file)
        except Exception as exc:  # noqa: BLE001
            excluded.append({"arm": arm, "task_id": task_id, "seed": seed,
                             "reason": f"events unreadable: {exc}"})
            continue
        n_rs = sum(1 for e in events if e.event_type == "run_start")
        records[(task_id, int(seed))] = {
            "result": result, "events": events,
            "n_run_start_in_last_attempt": n_rs,
        }
    return records, excluded


def outcome(res: dict) -> dict:
    return {
        "goal_pass": (res.get("goal_pass_rate") == 1.0),
        "tgc_pass": (res.get("tgc") == 1.0),
        "goal_pass_rate": res.get("goal_pass_rate"),
        "tgc": res.get("tgc"),
    }


def episode_steps(events):
    """(n_actions, first_error_step or -1, hit_max_steps, max_steps_limit).

    first_error = step of the first observation with a non-null error_type.
    """
    max_steps = None
    for e in events:
        if e.event_type == "run_start":
            lim = (e.payload or {}).get("limits") or {}
            if isinstance(lim.get("max_steps"), int):
                max_steps = lim["max_steps"]
    steps_taken = [e.step for e in events if e.event_type == "action"]
    n_actions = len(steps_taken)
    first_error, first_error_text, done_flags = -1, -1, []
    for e in events:
        if e.event_type == "observation":
            if (e.error_type or None) and first_error < 0:
                first_error = e.step
            text = (e.payload or {}).get("text") or ""
            if first_error_text < 0 and text.startswith("Execution failed"):
                first_error_text = e.step
            p = e.payload or {}
            if p.get("done") or p.get("truncated"):
                done_flags.append(e.step)
    hit_max = bool(max_steps is not None and n_actions >= max_steps
                   and not done_flags)
    return (n_actions, first_error, first_error_text, hit_max,
            (max_steps or 0))


def actions_with_names(events):
    """[api_name or None] in file order (position = index + 1)."""
    out = []
    for e in events:
        if e.event_type != "action":
            continue
        code = (e.payload or {}).get("code") or ""
        m = API_RE.search(code)
        out.append(f"{m.group(1)}.{m.group(2)}" if m else None)
    return out


def termination_counts(recs):
    counts = {k: 0 for k in TERMINATION_KEYS}
    for rec in recs.values():
        et = rec["result"].get("error_type")
        key = "null" if et is None or et == "" else str(et)
        if key not in counts:
            counts[key] = 0
        counts[key] += 1
    return counts


def novelty_curve(arms, data):
    """Per 1-based action position, share of actions whose API name appears
    for the FIRST time in that episode vs a repeat."""
    per_pos = defaultdict(lambda: [0, 0])  # pos -> [n_novel, n_total]
    n_named = n_miss = 0
    for arm in arms:
        for rec in data[arm].values():
            seen = set()
            for i, name in enumerate(actions_with_names(rec["events"])):
                pos = i + 1
                per_pos[pos][1] += 1
                if name is None:
                    n_miss += 1
                    continue
                n_named += 1
                if name not in seen:
                    seen.add(name)
                    per_pos[pos][0] += 1
    curve = {str(pos): {"n": t, "novel_share": round(nn / t, 4)}
             for pos, (nn, t) in sorted(per_pos.items()) if pos <= 20}
    binned = {}
    for lo, hi in ((1, 3), (4, 6), (7, 9), (10, 12), (13, 40)):
        nn = sum(per_pos[p][0] for p in per_pos if lo <= p <= hi)
        t = sum(per_pos[p][1] for p in per_pos if lo <= p <= hi)
        if t:
            binned[f"{lo}-{hi}"] = {"n": t, "novel_share": round(nn / t, 4)}
    total = sum(t for _, t in per_pos.values())
    return {
        "api_regex": API_RE_STR,
        "actions_total": total,
        "actions_with_name": n_named,
        "actions_without_name": n_miss,
        "miss_rate_no_name": round(n_miss / total, 4) if total else None,
        "curve_by_position_le_20": curve,
        "binned": binned,
        "note": (
            "Novelty is a PROXY: it takes only the first apis.<app>.<method>() "
            "match per action code, counts repetition within one episode only, "
            "and misses APIs reached via variables/getattr/returned objects "
            "(v = apis.x.y(); v.z() is invisible). A repeat can still be hard; "
            "a novel name can be trivial."
        ),
    }

def main():
    data, excluded = {}, {}
    for arm in ARMS:
        recs, exc = load_arm(arm)
        data[arm] = recs
        excluded[arm] = exc
    episodes = {arm: len(recs) for arm, recs in data.items()}
    n_excluded = {arm: len(exc) for arm, exc in excluded.items()}

    # Section 1: 2x2 opportunity tables.
    tables = {}
    for exec_arm in EXECUTOR_ARMS:
        pair_keys = sorted(set(data[exec_arm]) & set(data["planner_alone"]))
        for metric, out_key in (
            ("goal_pass", "tgc_from_goal_pass_eq_1"),
            ("tgc_pass", "tgc_pass"),
        ):
            cell = defaultdict(list)
            for k in pair_keys:
                p = outcome(data["planner_alone"][k]["result"])[metric]
                x = outcome(data[exec_arm][k]["result"])[metric]
                cell[("planner_pass" if p else "planner_fail",
                      "executor_pass" if x else "executor_fail")].append(k)
            opportunity = cell.get(("planner_pass", "executor_fail"), [])
            block = {
                "n_pairs": len(pair_keys),
                "cells": {f"{a}/{b}": len(v) for (a, b), v in sorted(cell.items())},
                "planner_pass_executor_fail": {
                    "n": len(opportunity),
                    "task_id_seed": [f"{t}@{s}" for (t, s) in opportunity],
                    "distinct_task_ids": sorted({t for (t, _s) in opportunity}),
                },
            }
            if out_key == "tgc_from_goal_pass_eq_1":
                block["note"] = (
                    "Identical to tgc_pass by construction: TGC is "
                    "goal_pass_rate binarised at 1.0."
                )
            tables.setdefault(exec_arm, {})[out_key] = block

    # Section 1b: continuous goal_pass_rate; bootstrap reused from hj1_gate.
    section1b = {}
    for exec_arm in EXECUTOR_ARMS:
        pair_keys = sorted(set(data[exec_arm]) & set(data["planner_alone"]))
        planner_field, executor_field = {}, {}
        n_p_gt = n_eq = n_e_gt = 0
        p_vals, e_vals = [], []
        for k in pair_keys:
            p = data["planner_alone"][k]["result"].get("goal_pass_rate")
            x = data[exec_arm][k]["result"].get("goal_pass_rate")
            planner_field[k] = {"goal_pass_rate": p}
            executor_field[k] = {"goal_pass_rate": x}
            if p is None or x is None:
                continue
            p_vals.append(float(p))
            e_vals.append(float(x))
            if p > x:
                n_p_gt += 1
            elif p == x:
                n_eq += 1
            else:
                n_e_gt += 1
        section1b[exec_arm] = {
            "n_pairs": len(pair_keys),
            "mean_goal_pass_rate_planner": (
                round(statistics.fmean(p_vals), 4) if p_vals else None),
            "mean_goal_pass_rate_executor": (
                round(statistics.fmean(e_vals), 4) if e_vals else None),
            "paired_mean_diff_planner_minus_executor": paired_diff(
                planner_field, executor_field, "goal_pass_rate",
                resample="task"),
            "n_planner_strictly_higher": n_p_gt,
            "n_equal": n_eq,
            "n_executor_strictly_higher": n_e_gt,
        }

    termination_reasons = {
        "note": TERMINATION_NOTE,
        "per_arm": {
            arm: termination_counts(recs) for arm, recs in data.items()
        },
    }

    # Section 2: first-error position, executor failures only.
    first_error = {}
    for exec_arm in EXECUTOR_ARMS:
        fracs, hit_max_count, n_fail = [], 0, 0
        rows = []
        for (task_id, seed), rec in sorted(data[exec_arm].items()):
            res = rec["result"]
            if outcome(res)["goal_pass"]:
                continue
            n_fail += 1
            n_actions, fe, fet, hit_max, mx = episode_steps(rec["events"])
            frac = round(fe / n_actions, 4) if (fe >= 0 and n_actions) else None
            frac_t = round(fet / n_actions, 4) if (fet >= 0 and n_actions) else None
            if frac_t is not None:
                fracs.append(frac_t)
            hit_max_count += int(hit_max)
            rows.append({"task_id": task_id, "seed": seed,
                         "first_error_step_by_text": fet if fet >= 0 else None,
                         "first_error_step_by_error_type": fe if fe >= 0 else None,
                         "steps_taken": n_actions, "hit_max_steps": hit_max,
                         "max_steps_limit": mx,
                         "first_error_fraction_by_text": frac_t,
                         "result_error_type": res.get("error_type"),
                         "tgc": res.get("tgc")})
        with_err = len(fracs)
        first_error[exec_arm] = {
            "executor_failures_n": n_fail,
            "with_first_error_by_text_marker": with_err,
            "with_first_error_by_error_type_field": 0,
            "error_type_note": (
                "Brief premise mismatch: across all 228 executor events.jsonl "
                "files in these two arms there are ZERO non-null error_type "
                "fields and zero observations whose text starts with 'ERROR' "
                "(grep counts 0/0). Environment failures instead surface as "
                "observation text beginning with 'Execution failed. Traceback:' "
                "(sample: 'Execution failed. Traceback:\\n  File "
                "\\\\\"<python-input>\\\\\", line 11...NameError'). First-error "
                "position below uses that text marker; the error_type field "
                "variant is reported as 0 because the field is never populated."
            ),
            "first_error_fraction_distribution": quartiles(fracs),
            "share_first_error_in_first_third": (
                round(sum(1 for f in fracs if f <= 1 / 3) / with_err, 4)
                if with_err else None),
            "share_hit_max_steps": (
                round(hit_max_count / n_fail, 4) if n_fail else None),
            "rows": rows,
        }

    # Section 3: planner step counts.
    step_counts = [
        sum(1 for e in rec["events"] if e.event_type == "action")
        for rec in data["planner_alone"].values()
    ]
    section3 = {
        "n": len(step_counts),
        "distribution": quartiles(step_counts),
        "share_shorter_than": {
            f"steps<{m}": round(sum(1 for s in step_counts if s < m)
                                / len(step_counts), 4)
            for m in (2, 4, 6, 9)
        },
    }

    # Section 5: per-app difficulty. Task ids are AppWorld task hashes
    # (e.g. `68ee2c9_3`); no app field is visible in result.json or the
    # events without reading AppWorld's own task metadata, which the brief
    # forbids.
    section5 = "not derivable"

    out = {
        "generated_by": "scripts/analysis/failure_anatomy.py",
        "inputs": {arm: str(p) for arm, p in ARMS.items()},
        "episode_counts": episodes,
        "excluded": {"counts": n_excluded, "details": excluded},
        "multi_run_start_files_in_last_attempt": {
            arm: sum(1 for r in data[arm].values()
                     if r["n_run_start_in_last_attempt"] > 1)
            for arm in ARMS
        },
        "termination_reasons": termination_reasons,
        "section1_opportunity_table": tables,
        "section1b_goal_pass_continuous": section1b,
        "section2_first_error_position": first_error,
        "section3_planner_step_counts": section3,
        "section4_api_novelty": {
            "planner": novelty_curve(["planner_alone"], data),
            "executor": novelty_curve(list(EXECUTOR_ARMS), data),
        },
        "section5_per_app_difficulty": section5,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n")
    print("wrote", OUT_PATH)
    print(json.dumps({
        "episode_counts": episodes, "excluded": n_excluded,
        "multi_run_start": out["multi_run_start_files_in_last_attempt"],
        "section3": section3,
        "planner_novelty": out["section4_api_novelty"]["planner"]["binned"],
        "executor_novelty": out["section4_api_novelty"]["executor"]["binned"],
        "planner_miss": out["section4_api_novelty"]["planner"]["miss_rate_no_name"],
        "executor_miss": out["section4_api_novelty"]["executor"]["miss_rate_no_name"],
        "opportunity": {
            arm: {k: {"n_pairs": v["n_pairs"], "cells": v["cells"]}
                  for k, v in blocks.items()}
            for arm, blocks in tables.items()
        },
        "section1b": {
            arm: {
                **{kk: vv for kk, vv in v.items()
                   if kk != "paired_mean_diff_planner_minus_executor"},
                "paired_diff": v["paired_mean_diff_planner_minus_executor"],
            }
            for arm, v in section1b.items()
        },
        "termination_reasons": termination_reasons["per_arm"],
        "first_error": {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                        for k, v in first_error.items()},
    }, indent=2))


if __name__ == "__main__":
    main()
