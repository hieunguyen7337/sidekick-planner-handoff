"""Why a local planner fails the LP informativeness gate: process statistics per campaign.

Descriptive and exploratory; nothing here is registered. Every statistic is read from the LAST attempt of
each episode (events after its last `run_start`), seeds 1 and 2, `<root>/<campaign>/<system>/<seed>/<task>/
events.jsonl`.

Per campaign: the share of each actor:kind among actions; how many episodes ever call
`apis.supervisor.show_account_passwords` (AppWorld's credential source, needed before nearly every login);
how many pass a placeholder-like literal credential (`password="password"`, `"valid_password"`, ... -- a
regex heuristic, so an approximate count); the share of CODE observations that are "Execution failed";
how many emit COMPLETE; how many end with ten consecutive actions that execute nothing; how many repeat one
identical action five or more times. Prefix arms also get the replayed prefix's start step and effective m.
In a prefix arm the replayed planner actions are not events, so every count there is the RECEIVER's.

LP prereg Amendment 4 has `lp_report.py` read every LP-2 aggregate first, so campaigns marked
`outcomes=False` (the P27 ceiling) print process statistics only: no goal_pass, error_type or steps.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import statistics
from collections import Counter
from typing import Any

DEFAULT_ROOT = "/scratch/n12194778/sidekick/results"
# (label, campaign, outcomes shown)
CAMPAIGNS = [
    ("luna_C", "hj13_planner_alone_cap81_20260923", True),
    ("P8_C", "lp1_planner_alone_cap81_qwen8b_v2_20260923", True),
    ("P27_C", "lp2_planner_alone_cap81_qwen38_27b_20260923", False),
    ("E_bplus", "hj8_executor_alone_bplus_20260919", True),
    ("P8_Mb6", "lp1_prefix_bplus_m6_v2_20260923", True),
    ("P8_Mb11", "lp1_prefix_bplus_m11_v2_20260923", True),
    ("P8_Mz11", "lp1_prefix_zs_m11_v2_20260923", True),
    ("luna_Mb11", "hj12_prefix_m11_20260923", True),
]
SEEDS = ("1", "2")
PLACEHOLDER = re.compile(
    r"""(password|username|access_token|email|phone_number)\s*=\s*["']"""
    r"""(password|username|user|token|access_token|your_[^"']*|valid_[^"']*|correct_[^"']*|"""
    r"""example[^"']*|placeholder[^"']*|dummy[^"']*|<[^"']*>|[a-z_]*_number|[a-z_]*_token)["']""",
    re.I)


def last_attempt(path: str) -> list[dict[str, Any]]:
    evs: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("event_type") == "run_start":
                evs = []
            evs.append(ev)
    return evs


def _kind(ev: dict[str, Any]) -> Any:
    return (ev.get("payload") or {}).get("kind")


def _text(ev: dict[str, Any]) -> str:
    p = ev.get("payload") or {}
    return str(p.get("code") or p.get("content") or p.get("message") or "")


def episode(evs: list[dict[str, Any]]) -> dict[str, Any]:
    acts = [e for e in evs if e.get("event_type") == "action"]
    obs = [e for e in evs if e.get("event_type") == "observation"]
    start = next((e.get("payload") or {} for e in evs if e.get("event_type") == "run_start"), {})
    prefix = start.get("prefix") or {}
    handoff = next((e.get("payload") or {} for e in evs
                    if e.get("event_type") == "report" and "effective_m" in (e.get("payload") or {})), {})
    end = next((e.get("payload") or {} for e in evs if e.get("event_type") == "run_end"), {})
    code = [_text(a) for a in acts if _kind(a) == "CODE"]
    tail = acts[-10:]
    repeats = Counter((_kind(a), _text(a)[:200]) for a in acts)
    return {
        "kinds": Counter(f"{a.get('actor')}:{_kind(a)}" for a in acts),
        "n_obs_code": sum(1 for o in obs if _kind(o) == "CODE"),
        "code_fail": sum(1 for o in obs
                         if str((o.get("payload") or {}).get("text", "")).startswith("Execution failed")),
        "cred_lookup": any("show_account_passwords" in c for c in code),
        "placeholder": any(PLACEHOLDER.search(c) for c in code),
        "complete": any(_kind(a) == "COMPLETE" for a in acts),
        "tail_no_code": len(tail) == 10 and not any(_kind(a) == "CODE" for a in tail),
        "max_repeat": max(repeats.values()) if repeats else 0,
        "start_step": prefix.get("start_step"),
        "effective_m": handoff.get("effective_m"),
        "handoff": handoff.get("handoff_occurred"),
        "error_type": end.get("error_type"),
        "goal_pass": end.get("goal_pass_rate"),
        "steps": end.get("steps"),
    }


def episode_paths(root: str, campaign: str, seeds=SEEDS) -> list[str]:
    paths = sorted(glob.glob(os.path.join(root, campaign, "*", "*", "*", "events.jsonl")))
    return [p for p in paths if p.split(os.sep)[-3] in seeds]


def summarise(root: str, campaign: str, outcomes: bool, seeds=SEEDS) -> dict[str, Any]:
    eps = [episode(last_attempt(p)) for p in episode_paths(root, campaign, seeds)]
    out: dict[str, Any] = {"campaign": campaign, "n": len(eps), "outcomes_shown": outcomes}
    if not eps:
        return out
    kinds: Counter = Counter()
    for e in eps:
        kinds.update(e["kinds"])
    total = sum(kinds.values())
    out["action_share"] = {k: round(v / total, 3) for k, v in kinds.most_common()}
    out["actions_per_episode"] = round(total / len(eps), 1)
    n_obs = sum(e["n_obs_code"] for e in eps)
    out["code_fail_rate"] = round(sum(e["code_fail"] for e in eps) / n_obs, 3) if n_obs else None
    for key in ("cred_lookup", "placeholder", "complete", "tail_no_code"):
        out[f"n_{key}"] = sum(1 for e in eps if e[key])
    out["n_repeat_ge5"] = sum(1 for e in eps if e["max_repeat"] >= 5)
    starts = [e["start_step"] for e in eps if e["start_step"] is not None]
    if starts:
        out["prefix_start_step_mean"] = round(statistics.mean(starts), 2)
        ms = [e["effective_m"] for e in eps if e["effective_m"] is not None]
        out["effective_m_mean"] = round(statistics.mean(ms), 2) if ms else None
        out["n_handoff"] = sum(1 for e in eps if e["handoff"])
    if outcomes:
        out["error_type"] = dict(sorted(Counter(str(e["error_type"]) for e in eps).items()))
        gp = [e["goal_pass"] for e in eps if e["goal_pass"] is not None]
        out["goal_pass_mean"] = round(statistics.mean(gp), 4) if gp else None
        steps = [e["steps"] for e in eps if e["steps"] is not None]
        out["steps_mean"] = round(statistics.mean(steps), 2) if steps else None
    return out


def stall_samples(root: str, campaign: str, k: int = 3, seeds=SEEDS) -> list[dict[str, Any]]:
    """The last actions and messages of the first k episodes whose last ten actions executed nothing."""
    out = []
    for p in episode_paths(root, campaign, seeds):
        evs = last_attempt(p)
        if not episode(evs)["tail_no_code"]:
            continue
        acts = [a for a in evs if a.get("event_type") == "action"]
        msgs = [str((x.get("payload") or {}).get("message") or (x.get("payload") or {}).get("ask_reason") or "")[:160]
                for x in evs if x.get("event_type") in ("report", "ask")]
        out.append({"episode": "/".join(p.split(os.sep)[-3:-1]),
                    "last_kinds": [_kind(a) for a in acts[-6:]], "last_messages": msgs[-2:]})
        if len(out) >= k:
            break
    return out


def build(root: str, campaigns=CAMPAIGNS) -> dict[str, Any]:
    report: dict[str, Any] = {
        "note": ("Descriptive, exploratory. Last attempt per episode, seeds 1-2. P27 outcomes masked "
                 "(LP prereg Amendment 4: lp_report.py reads LP-2 aggregates first). 'placeholder' is a regex "
                 "heuristic; prefix-arm counts are the receiver's actions only."),
        "campaigns": {label: summarise(root, camp, shown) for label, camp, shown in campaigns},
    }
    p8 = next((camp for label, camp, _ in campaigns if label == "P8_C"), None)
    if p8:
        report["P8_C_stall_samples"] = stall_samples(root, p8)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    report = build(args.root)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    main()
