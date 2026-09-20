#!/usr/bin/env python3
"""J8 dev-split frontier: quality vs planner calls, oracle headroom, H3, F1.

Analyse completed J8 arms on the 114-row dev split (57 tasks × 2 seeds).
Pairing and the task-clustered bootstrap are imported from j10_report; they
are not reimplemented here.

Interface:
  python scripts/analysis/j8_frontier.py --arm LABEL=DIR [--arm LABEL=DIR ...]
      --out report.json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
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

_J10_SPEC = importlib.util.spec_from_file_location(
    "j10_report", Path(__file__).resolve().parent / "j10_report.py"
)
j10 = importlib.util.module_from_spec(_J10_SPEC)
assert _J10_SPEC.loader is not None
_J10_SPEC.loader.exec_module(j10)

from scripts.setup.campaign_summarize import BROKEN  # noqa: E402
from scripts.setup.hj1_gate import paired_diff  # noqa: E402

MIN_ROWS = 114
F1_QUALITY_PP = 7.0
FIXED_K_REFERENCE = 5
DEFAULT_SEEDS = "1,2"
DEFAULT_ORACLE_LABELS = Path(
    "/scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/oracle_labels.json"
)
TICK_K = 5
TICK_MAX = 40
FIXED_K_LABEL = re.compile(
    r"(?:^|_)fixed_k(?:_k|_|=)?(?P<k>3|5|7|10)$", re.IGNORECASE
)
CRASH_ERROR_TYPE = "crash"
HEADLINE_POPULATION = "all-episodes"
POPULATION_PREAMBLE = (
    "Headline quality contrast uses all-episodes for every metric "
    "(crashed episode scores 0). Survivor columns/contrasts use episodes "
    "with error_type != 'crash'; a paired survivor contrast drops a "
    "(task_id, seed) pair if either side crashed."
)
H3_HEADLINE_POPULATION = "scored"
H3_POPULATIONS = (
    "scored is the primary H3 population: ticks at or before the episode's "
    "final step (decision points that existed). grid retains the published "
    "5,10,...,40 tick grid, including post-episode filler scored as 0.0. "
    "Headline H3 uses scored."
)
H3_EXCLUDED_REASON = "past_episode_end"


def parse_arm_spec(spec: str) -> tuple[str, Path]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"arm spec must be LABEL=DIR, got {spec!r}")
    label, raw = spec.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError(f"empty label in arm spec {spec!r}")
    return label, Path(raw).expanduser()


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
    p.add_argument("--out", type=Path, required=True, help="JSON report path.")
    p.add_argument(
        "--seeds",
        default=DEFAULT_SEEDS,
        help="Comma-separated seeds (J8 default 1,2).",
    )
    p.add_argument(
        "--oracle-labels",
        type=Path,
        default=DEFAULT_ORACLE_LABELS,
        help="Path to oracle_labels.json (H3 calibration). Read-only.",
    )
    return p.parse_args(argv)


def parse_seeds(raw: str) -> list[int]:
    return j10.parse_seeds(raw)


def auroc(y_true: list[int], scores: list[float]) -> float:
    """Tie-aware rank-statistic AUROC; 0.5 when only one class is present.

    Copied from scripts/setup/fit_feature_verifier.py:387-406 so this script
    does not import that module's branch-counterfactual dependency.
    """
    pairs = sorted(zip(scores, y_true), key=lambda t: t[0])
    pos = sum(y_true)
    neg = len(y_true) - pos
    if pos == 0 or neg == 0:
        return 0.5
    rank_sum = 0.0
    i = 0
    n = len(pairs)
    while i < n:
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            if pairs[k][1]:
                rank_sum += avg_rank
        i = j
    return (rank_sum - pos * (pos + 1) / 2.0) / (pos * neg)


def expected_calibration_error(
    y_true: list[int], probs: list[float], bins: int = 10
) -> float:
    """Copied from scripts/setup/fit_feature_verifier.py:415-432."""
    if not y_true:
        return 0.0
    ece = 0.0
    n = len(y_true)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [
            (p, t)
            for p, t in zip(probs, y_true)
            if lo <= p < hi or (b == bins - 1 and p == 1.0)
        ]
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(t for _, t in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(acc - conf)
    return ece


def _json_number(value: Any) -> Any:
    return j10._json_number(value)


def establish_oracle_semantics() -> dict[str, Any]:
    """Decide replay-vs-free from source, not from the arm's name.

    J8 `oracle_escalation` is selected by configs/hj8_oracle_escalation.yaml
    (`executor` + `oracle_labels` + CachedPacketPlanner). The runner never
    passes an EpisodePrefix; the loop therefore resets and plan_firsts, and
    oracle_steps only force a review on that free-running episode.
    """
    runner = REPO_ROOT / "src" / "sidekick" / "runner.py"
    loop = REPO_ROOT / "src" / "sidekick" / "systems" / "loop.py"
    oe = REPO_ROOT / "src" / "sidekick" / "systems" / "oracle_escalation.py"
    cfg = REPO_ROOT / "configs" / "hj8_oracle_escalation.yaml"
    citations: list[str] = []
    reasons: list[str] = []

    run_line = None
    run_has_prefix = False
    for i, line in enumerate(runner.read_text(encoding="utf-8").splitlines(), 1):
        if "result = system.run(" in line:
            run_line = i
            run_has_prefix = "prefix" in line
            citations.append(f"src/sidekick/runner.py:{i}")
            break
    if run_line is None:
        reasons.append("could not find system.run call in runner.py")
    elif run_has_prefix:
        reasons.append("runner.py passes prefix into system.run")

    plan_first_line = None
    oracle_step_line = None
    for i, line in enumerate(loop.read_text(encoding="utf-8").splitlines(), 1):
        if "prefix is None and policy.plan_first" in line:
            plan_first_line = i
            citations.append(f"src/sidekick/systems/loop.py:{i}")
        if "step in policy.oracle_steps" in line:
            oracle_step_line = i
            citations.append(f"src/sidekick/systems/loop.py:{i}")
    if plan_first_line is None:
        reasons.append("could not find prefix is None and policy.plan_first")
    if oracle_step_line is None:
        reasons.append("could not find step in policy.oracle_steps")

    oe_text = oe.read_text(encoding="utf-8")
    if "EpisodePrefix" in oe_text or "replay_prefix" in oe_text:
        reasons.append("OracleEscalation mentions a prefix/replay path")
    citations.append("src/sidekick/systems/oracle_escalation.py:9-18")

    cfg_text = cfg.read_text(encoding="utf-8")
    if "oracle_labels" not in cfg_text:
        reasons.append("hj8_oracle_escalation.yaml has no oracle_labels")
    citations.append("configs/hj8_oracle_escalation.yaml:37-38")

    if reasons:
        return {
            "established": False,
            "semantics": None,
            "line": "oracle semantics: unestablished; refusing headroom row",
            "citation": "; ".join(citations),
            "reasons": reasons,
        }
    citation = "; ".join(citations)
    return {
        "established": True,
        "semantics": "runs free",
        "line": f"oracle semantics: runs free  ({citation})",
        "citation": citation,
        "reasons": [],
    }


def oracle_semantics_line() -> tuple[str, str]:
    info = establish_oracle_semantics()
    if not info["established"]:
        return ("unestablished", info["citation"])
    return (str(info["semantics"]), str(info["citation"]))


def k_from_label(label: str) -> Optional[int]:
    match = FIXED_K_LABEL.search(label.strip())
    if not match:
        return None
    return int(match.group("k"))


def is_gated_label(label: str) -> bool:
    lower = label.lower()
    return lower.startswith("sidekick") or lower.startswith("router_seq")


def is_oracle_label(label: str) -> bool:
    return label.lower().startswith("oracle_escalation")


def is_crashed(row: dict[str, Any]) -> bool:
    return row.get("error_type") == CRASH_ERROR_TYPE


def _sign_label(value: Any) -> str:
    if value is None:
        return "none"
    number = float(value)
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "zero"


def ci_excludes_zero(ci: Any) -> Optional[bool]:
    if not ci or len(ci) < 2 or ci[0] is None or ci[1] is None:
        return None
    lo, hi = float(ci[0]), float(ci[1])
    return bool(lo > 0.0 or hi < 0.0)


def coerce_crash_quality(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    field: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    """All-episodes view: a crashed episode scores 0 on quality fields."""
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for key, row in cleaned.items():
        copy = dict(row)
        if is_crashed(copy) and field in {"tgc", "goal_pass_rate"}:
            copy[field] = 0.0
        out[key] = copy
    return out


def both_survived_subset(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
) -> tuple[
    dict[tuple[str, int], dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
    int,
    int,
]:
    """Keep only shared (task_id, seed) pairs where neither side crashed."""
    shared = set(left) & set(right)
    n_dropped_crash = 0
    left_ok: dict[tuple[str, int], dict[str, Any]] = {}
    right_ok: dict[tuple[str, int], dict[str, Any]] = {}
    for key in shared:
        if is_crashed(left[key]) or is_crashed(right[key]):
            n_dropped_crash += 1
            continue
        left_ok[key] = left[key]
        right_ok[key] = right[key]
    return left_ok, right_ok, n_dropped_crash, len(shared)


def total_planner_calls(
    cleaned: dict[tuple[str, int], dict[str, Any]],
) -> Optional[int]:
    live = [row.get("planner_calls_live") for row in cleaned.values()]
    if live and all(v is not None for v in live):
        return int(sum(int(v) for v in live))
    replay = [row.get("n_planner_calls") for row in cleaned.values()]
    if replay and all(v is not None for v in replay):
        return int(sum(int(v) for v in replay))
    return None


def mean_quality(
    rows: list[dict[str, Any]],
    field: str,
    *,
    crash_as_zero: bool,
) -> Optional[float]:
    values: list[float] = []
    missing_noncrash = 0
    for row in rows:
        if crash_as_zero and is_crashed(row):
            values.append(0.0)
            continue
        raw = row.get(field)
        if raw is None:
            missing_noncrash += 1
            continue
        values.append(float(raw))
    if crash_as_zero and missing_noncrash:
        return None
    if not values:
        return None
    return round(statistics.fmean(values), 6)


def population_contrast_disagreement(
    all_c: dict[str, Any],
    surv_c: dict[str, Any],
) -> dict[str, Any]:
    all_diff = all_c.get("diff")
    surv_diff = surv_c.get("diff")
    sign_disagree = _sign_label(all_diff) != _sign_label(surv_diff)
    all_excl = ci_excludes_zero(all_c.get("ci95"))
    surv_excl = ci_excludes_zero(surv_c.get("ci95"))
    ci_disagree = all_excl is not None and surv_excl is not None and all_excl != surv_excl
    return {
        "disagree": bool(sign_disagree or ci_disagree),
        "sign_disagree": sign_disagree,
        "ci_excludes_zero_disagree": ci_disagree,
        "all_diff": all_diff,
        "surv_diff": surv_diff,
        "all_ci95": all_c.get("ci95"),
        "surv_ci95": surv_c.get("ci95"),
        "all_ci_excludes_zero": all_excl,
        "surv_ci_excludes_zero": surv_excl,
        "n_pairs_all": all_c.get("n_pairs"),
        "n_pairs_survivors": surv_c.get("n_pairs"),
        "n_pairs_dropped_crash": surv_c.get("n_pairs_dropped_crash"),
        "field": all_c.get("field") or surv_c.get("field"),
        "left": all_c.get("left") or surv_c.get("left"),
        "right": all_c.get("right") or surv_c.get("right"),
    }


def population_notes(arms: dict[str, dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    rates: list[tuple[str, float]] = []
    for label, arm in arms.items():
        if not arm.get("complete_n"):
            continue
        if int(arm.get("n_crashed") or 0) == 0:
            notes.append(
                f"{label}: 0 crashes; all-episodes and survivor populations coincide"
            )
        pct = arm.get("crash_per_call_pct")
        if pct is not None:
            rates.append((label, float(pct)))
    if len(rates) >= 2 and len({p for _, p in rates}) > 1:
        bits = ", ".join(f"{lab}={pct:.2f}%" for lab, pct in rates)
        notes.append(
            f"per-call crash rate is not constant across arms ({bits}). "
            "A fixed independent per-call failure probability would be flat."
        )
    return notes


def disagreement_lines(items: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in items:
        parts: list[str] = []
        if item.get("sign_disagree"):
            all_d = item.get("all_diff")
            surv_d = item.get("surv_diff")
            all_txt = "None" if all_d is None else f"{float(all_d):+.4f}"
            surv_txt = "None" if surv_d is None else f"{float(surv_d):+.4f}"
            parts.append(
                f"sign differs (all-episodes {all_txt}, survivors {surv_txt})"
            )
        if item.get("ci_excludes_zero_disagree"):
            parts.append(
                "CI-excludes-zero differs "
                f"(all-episodes {item.get('all_ci_excludes_zero')}, "
                f"survivors {item.get('surv_ci_excludes_zero')})"
            )
        dropped = item.get("n_pairs_dropped_crash")
        lines.append(
            "CONTRAST DISAGREEMENT: "
            f"{item.get('field')} {item.get('left')} minus {item.get('right')}: "
            + "; ".join(parts)
            + f". Survivor contrast dropped {dropped} pairs where either side crashed."
        )
    return lines


def contrast_accounting_lines(contrasts: dict[str, Any]) -> list[str]:
    lines = [
        "survivor contrast pair accounting (a pair is dropped if either side crashed):"
    ]
    n_lines = 0
    for name, row in contrasts.items():
        if not isinstance(row, dict):
            continue
        if row.get("population") != "survivors":
            continue
        if row.get("field") not in {"tgc", "goal_pass_rate"}:
            continue
        lines.append(
            f"  {name}: n_pairs={row.get('n_pairs')} "
            f"dropped_crash={row.get('n_pairs_dropped_crash')} "
            f"shared={row.get('n_pairs_shared')}"
        )
        n_lines += 1
    if n_lines == 0:
        return []
    return lines


def refuse_partial_arms(arm_n: dict[str, int], min_rows: int | None = None) -> list[str]:
    """Return refusal messages for arms with fewer than min_rows episodes."""
    if min_rows is None:
        min_rows = MIN_ROWS
    messages: list[str] = []
    for label, n in arm_n.items():
        if n < min_rows:
            messages.append(
                f"REFUSE headline: arm {label!r} has {n} rows (need {min_rows})"
            )
    return messages


def attach_ledger_fields(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    runs: dict[tuple[str, int], dict[str, Any]],
) -> None:
    """Add ledger live call/token fields; never coerce missing to 0."""
    for key, row in cleaned.items():
        raw = runs.get(key) or {}
        totals = raw.get("totals")
        if not isinstance(totals, dict):
            totals = {}
        live = totals.get("planner_calls_total")
        tokens = totals.get("planner_tokens_total")
        row["planner_calls_live"] = None if live is None else int(live)
        row["planner_tokens_live"] = None if tokens is None else float(tokens)
        replay = row.get("n_planner_calls")
        row["planner_calls_replay_inclusive"] = replay
        row["calls_live_differs_from_replay"] = (
            live is not None and replay is not None and int(live) != int(replay)
        )


def mean_or_none(values: list[Any]) -> Optional[float]:
    present = [float(v) for v in values if v is not None]
    missing = sum(1 for v in values if v is None)
    if missing or not present:
        return None
    return round(statistics.fmean(present), 6)


def summarise_arm(
    label: str,
    loaded: dict[str, Any],
    seeds: list[int],
) -> dict[str, Any]:
    runs: dict[tuple[str, int], dict[str, Any]] = loaded["runs"]
    n = len(runs)
    tasks = sorted({task_id for task_id, seed in runs if seed in set(seeds)})
    inv = j10.inventory_arm(label, loaded, tasks, seeds)
    attach_ledger_fields(inv["cleaned"], runs)
    n_broken = 0
    for row in runs.values():
        err = row.get("error_type")
        if err in BROKEN:
            n_broken += 1
    cleaned = inv["cleaned"]
    live_vals = [row.get("planner_calls_live") for row in cleaned.values()]
    replay_vals = [row.get("planner_calls_replay_inclusive") for row in cleaned.values()]
    token_vals = [row.get("planner_tokens_live") for row in cleaned.values()]
    n_calls_differ = sum(
        1 for row in cleaned.values() if row.get("calls_live_differs_from_replay")
    )
    cleaned_rows = list(cleaned.values())
    survivors = [row for row in cleaned_rows if not is_crashed(row)]
    n_crashed = sum(1 for row in runs.values() if is_crashed(row))
    tgc_all = mean_quality(cleaned_rows, "tgc", crash_as_zero=True)
    tgc_survivors = mean_quality(survivors, "tgc", crash_as_zero=False)
    goal_pass_all = mean_quality(cleaned_rows, "goal_pass_rate", crash_as_zero=True)
    goal_pass_survivors = mean_quality(
        survivors, "goal_pass_rate", crash_as_zero=False
    )
    calls_total = total_planner_calls(cleaned)
    crash_per_call = None
    crash_per_call_pct = None
    if calls_total is not None and calls_total > 0:
        crash_per_call = n_crashed / calls_total
        crash_per_call_pct = round(100.0 * crash_per_call, 2)
    complete_n = n >= MIN_ROWS
    populations_coincide = n_crashed == 0
    return {
        "label": label,
        "n": n,
        "n_broken": n_broken,
        "n_crashed": n_crashed,
        "n_survivors": n - n_crashed,
        "n_cleaned": len(cleaned),
        "tgc_all": tgc_all,
        "tgc_survivors": tgc_survivors,
        "goal_pass_all": goal_pass_all,
        "goal_pass_survivors": goal_pass_survivors,
        "populations_coincide": populations_coincide,
        "planner_calls_total": calls_total,
        "crash_per_call": crash_per_call,
        "crash_per_call_pct": crash_per_call_pct,
        "tgc": tgc_all if complete_n else None,
        "goal_pass": goal_pass_all if complete_n else None,
        "planner_calls_per_episode": mean_or_none(live_vals) if complete_n else None,
        "planner_calls_replay_inclusive_per_episode": mean_or_none(replay_vals)
        if complete_n
        else None,
        "planner_tokens_per_episode": mean_or_none(token_vals) if complete_n else None,
        "n_episodes_live_differs_from_replay": n_calls_differ,
        "k": k_from_label(label),
        "gated": is_gated_label(label),
        "oracle": is_oracle_label(label),
        "complete_n": complete_n,
        "error_types": dict(
            sorted(
                Counter(str(r.get("error_type") or "none") for r in runs.values()).items()
            )
        ),
        "n_empty_files": len(loaded.get("empty_files") or []),
        "n_unreadable": len(loaded.get("unreadable") or []),
        "n_duplicates": len(loaded.get("duplicates") or []),
        "root_missing": bool(loaded.get("root_missing")),
        "cleaned": cleaned,
        "loaded": loaded,
    }


def paired_contrast(
    arm_a: dict[str, Any],
    arm_b: dict[str, Any],
    field: str,
    population: str = "all",
) -> dict[str, Any]:
    """Task-clustered paired bootstrap. Delegates to j10_report / hj1_gate.

    population='all': every shared (task_id, seed); crashed quality scores 0.
    population='survivors': drop a pair if either side crashed, and count it.
    """
    left = arm_a["cleaned"]
    right = arm_b["cleaned"]
    n_shared = len(set(left) & set(right))
    n_dropped_crash = 0
    if population in {"survivors", "survivor"}:
        left, right, n_dropped_crash, n_shared = both_survived_subset(left, right)
        pop_name = "survivors"
    elif population in {"all", "all-episodes"}:
        if field in {"tgc", "goal_pass_rate"}:
            left = coerce_crash_quality(left, field)
            right = coerce_crash_quality(right, field)
        pop_name = "all-episodes"
    else:
        raise ValueError(f"unknown population {population!r}")
    if field == "tgc":
        out = j10.contrast_tgc(left, right)
    elif field == "goal_pass_rate":
        out = j10.contrast_goal_pass_rate(left, right)
    elif field in {"planner_calls_live", "n_planner_calls"}:
        task = paired_diff(left, right, field, resample="task")
        out = j10.native_from_paired_diff(task)
        out["units"] = (
            "planner_calls (ci95); paired_diff also reports ci95_pp = 100×calls"
        )
        out["resample_unit_for_decision"] = j10.RESAMPLE_UNIT
    else:
        task = paired_diff(left, right, field, resample="task")
        out = j10.native_from_paired_diff(task)
        out["resample_unit_for_decision"] = j10.RESAMPLE_UNIT
    out["field"] = field
    out["left"] = arm_a["label"]
    out["right"] = arm_b["label"]
    out["population"] = pop_name
    out["n_pairs_dropped_crash"] = n_dropped_crash
    out["n_pairs_shared"] = n_shared
    return out


def choose_k_matched(
    arm: dict[str, Any],
    fixed_k_arms: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Pick the fixed_k arm whose live calls/episode is closest to `arm`."""
    target = arm.get("planner_calls_per_episode")
    available = {
        k: fk
        for k, fk in fixed_k_arms.items()
        if fk.get("planner_calls_per_episode") is not None and fk.get("complete_n")
    }
    if target is None or not available:
        return {
            "k_matched": None,
            "label": None,
            "reason": "missing calls/episode on the arm or on every fixed_k arm",
        }
    distances = {
        k: abs(float(fk["planner_calls_per_episode"]) - float(target))
        for k, fk in available.items()
    }
    best = min(distances.values())
    tied = sorted(k for k, d in distances.items() if math.isclose(d, best))
    if set(tied) == {5, 10} or (5 in tied and 10 in tied and len(tied) == 2):
        if 7 in available:
            chosen = 7
            note = "k=5 and k=10 tied; interpolated to k=7 [docs/prereg_v1.md:14]"
        else:
            return {
                "k_matched": None,
                "label": None,
                "tied": tied,
                "reason": "k=5 and k=10 tied; k=7 arm not present, refusing interpolate",
            }
    else:
        chosen = tied[0]
        note = None
    return {
        "k_matched": chosen,
        "label": available[chosen]["label"],
        "tied": tied,
        "distances": {str(k): distances[k] for k in sorted(distances)},
        "note": note,
    }


def frontier_table(arms: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Quality against calls/episode; fixed_k {3,5,10} as the reference curve."""
    rows: list[dict[str, Any]] = []
    for label, arm in arms.items():
        if not arm.get("complete_n"):
            continue
        role = "other"
        if arm.get("k") in {3, 5, 10}:
            role = "fixed_k_reference"
        elif arm.get("gated"):
            role = "gated"
        elif arm.get("oracle"):
            role = "oracle"
        rows.append(
            {
                "label": label,
                "role": role,
                "k": arm.get("k"),
                "n": arm.get("n"),
                "n_crashed": arm.get("n_crashed"),
                "tgc_all": arm.get("tgc_all"),
                "tgc_survivors": arm.get("tgc_survivors"),
                "goal_pass_all": arm.get("goal_pass_all"),
                "goal_pass_survivors": arm.get("goal_pass_survivors"),
                "planner_calls_total": arm.get("planner_calls_total"),
                "crash_per_call_pct": arm.get("crash_per_call_pct"),
                "tgc": arm.get("tgc_all"),
                "goal_pass": arm.get("goal_pass_all"),
                "planner_calls_per_episode": arm.get("planner_calls_per_episode"),
                "planner_calls_replay_inclusive_per_episode": arm.get(
                    "planner_calls_replay_inclusive_per_episode"
                ),
                "n": arm.get("n"),
            }
        )
    role_order = {"fixed_k_reference": 0, "gated": 1, "oracle": 2, "other": 3}
    rows.sort(key=lambda r: (role_order.get(r["role"], 9), r.get("k") or 99, r["label"]))
    return rows


def oracle_headroom(
    arms: dict[str, dict[str, Any]],
    oracle_info: dict[str, Any],
) -> dict[str, Any]:
    """oracle_escalation minus fixed_k(k_matched) on quality and calls."""
    if not oracle_info.get("established"):
        return {"error": "oracle semantics unestablished; refusing headroom row"}
    oracle_arms = [a for a in arms.values() if a.get("oracle") and a.get("complete_n")]
    if not oracle_arms:
        return {"error": "no complete oracle_escalation arm"}
    oracle = oracle_arms[0]
    fixed = {
        int(a["k"]): a
        for a in arms.values()
        if a.get("k") in {3, 5, 7, 10} and a.get("complete_n")
    }
    choice = choose_k_matched(oracle, fixed)
    if choice.get("k_matched") is None:
        return {"error": "k_matched unestablished", "choice": choice}
    matched = fixed[choice["k_matched"]]
    return {
        "oracle_arm": oracle["label"],
        "k_matched": choice,
        "quality_oracle_minus_fixed_k": paired_contrast(oracle, matched, "tgc"),
        "calls_oracle_minus_fixed_k": paired_contrast(
            oracle, matched, "planner_calls_live"
        ),
        "oracle_semantics": oracle_info["line"],
    }


def f1_test(
    quality_contrast: dict[str, Any],
    calls_vs_k5: dict[str, Any],
) -> dict[str, Any]:
    """Boolean: within 7pp of k_matched on quality AND fewer calls than fixed_k(5).

    Quality: upper CI bound on the deficit (fixed_k − arm) is ≤ 7 pp, i.e.
    ci95_pp[0] of (arm − k_matched) ≥ −7. Same writing as j10 H2 clause 1
    [OBSERVED scripts/analysis/j10_report.py:935-938, docs/prereg_v1.md:37].

    Calls: strictly fewer than fixed_k(5) with a CI excluding zero, i.e.
    ci95[1] of (arm − fixed_k_5) < 0 [OBSERVED j10_report.py:945-949].
    """
    q_ci = quality_contrast.get("ci95_pp")
    c_ci = calls_vs_k5.get("ci95")
    if not q_ci or not c_ci or len(q_ci) < 2 or len(c_ci) < 2:
        return {
            "holds": None,
            "reason": "a contrast CI is missing",
            "quality_within_7pp": None,
            "fewer_calls_than_fixed_k_5": None,
        }
    deficit_upper_pp = round(-float(q_ci[0]), 6)
    quality_ok = bool(float(q_ci[0]) >= -F1_QUALITY_PP)
    calls_ok = bool(float(c_ci[1]) < 0.0)
    return {
        "holds": bool(quality_ok and calls_ok),
        "quality_within_7pp": quality_ok,
        "fewer_calls_than_fixed_k_5": calls_ok,
        "deficit_ci_upper_pp": deficit_upper_pp,
        "quality_ci95_pp": list(q_ci),
        "quality_diff": quality_contrast.get("diff"),
        "calls_ci95": list(c_ci),
        "calls_diff": calls_vs_k5.get("diff"),
        "n_pairs_quality": quality_contrast.get("n_pairs"),
        "n_pairs_calls": calls_vs_k5.get("n_pairs"),
        "rule": (
            "ci95_pp[0] >= -7.00 vs fixed_k(k_matched) AND "
            "ci95[1] < 0 calls vs fixed_k(5)"
        ),
    }


def h3_row(
    label: str,
    scores: list[float],
    y: list[int],
    n_escalations: int,
) -> dict[str, Any]:
    """One H3 calibration row. Degenerate gates stay as rows, never a ZeroDivision."""
    n_positive = int(sum(y))
    n = len(y)
    degenerate = n_escalations == 0 or (scores and all(s == 0.0 for s in scores))
    if not scores or not y:
        return {
            "label": label,
            "auroc": 0.5 if degenerate else None,
            "ece": None,
            "n": 0,
            "n_positive": n_positive,
            "n_escalations": n_escalations,
            "degenerate": True,
            "note": "zero scored ticks" if not y else "no scores",
        }
    probs = [min(max(float(s), 0.0), 1.0) for s in scores]
    return {
        "label": label,
        "auroc": _json_number(auroc(y, scores)),
        "ece": _json_number(expected_calibration_error(y, probs)),
        "n": n,
        "n_positive": n_positive,
        "n_escalations": n_escalations,
        "degenerate": degenerate,
        "note": "degenerate gate (zero escalations)" if degenerate else None,
    }


def tick_grid() -> list[int]:
    return list(range(TICK_K, TICK_MAX + 1, TICK_K))


def slot_score(slot: dict[str, Any] | None) -> float:
    if slot is None:
        return 0.0
    if slot.get("score") is not None:
        return float(slot["score"])
    return 1.0 if slot.get("escalated") else 0.0


def _linear_quantile(sorted_xs: list[float], p: float) -> float:
    """Hyndman-Fan R7 (linear, numpy default): h = 1 + (n-1)p, 1-indexed."""
    n = len(sorted_xs)
    if n == 1:
        return float(sorted_xs[0])
    h = 1.0 + (n - 1) * float(p)
    lo = max(1, min(n, math.floor(h)))
    hi = max(1, min(n, math.ceil(h)))
    a = float(sorted_xs[lo - 1])
    b = float(sorted_xs[hi - 1])
    if lo == hi:
        return a
    return a + (h - lo) * (b - a)


def score_quantiles(scores: list[float]) -> dict[str, Any]:
    """Quantiles of real gate p_ask values (not the 0/1 escalation fallback)."""
    if not scores:
        return {
            "n": 0,
            "mean": None,
            "min": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
        }
    xs = sorted(float(s) for s in scores)
    return {
        "n": len(xs),
        "mean": _json_number(statistics.fmean(xs)),
        "min": _json_number(xs[0]),
        "median": _json_number(_linear_quantile(xs, 0.5)),
        "p90": _json_number(_linear_quantile(xs, 0.90)),
        "p95": _json_number(_linear_quantile(xs, 0.95)),
        "p99": _json_number(_linear_quantile(xs, 0.99)),
        "max": _json_number(xs[-1]),
    }


def _h3_pop_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "auroc": row.get("auroc"),
        "ece": row.get("ece"),
        "n": row.get("n"),
        "n_positive": row.get("n_positive"),
    }


def auroc_exceeds_chance(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(float(value) > 0.5)


def h3_auroc_chance_disagreement(grid_auroc: Any, scored_auroc: Any) -> bool:
    grid_above = auroc_exceeds_chance(grid_auroc)
    scored_above = auroc_exceeds_chance(scored_auroc)
    if grid_above is None or scored_above is None:
        return False
    return bool(grid_above != scored_above)


def _events_path_for_result(result_path: Path) -> Path:
    return result_path.parent / "events.jsonl"


def gate_scores_from_events(events_path: Path) -> dict[int, dict[str, Any]]:
    """Per-step gate score and whether the step escalated."""
    by_step: dict[int, dict[str, Any]] = {}
    if not events_path.is_file():
        return by_step
    try:
        text = events_path.read_text(encoding="utf-8")
    except OSError:
        return by_step
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
        step = ev.get("step")
        if step is None:
            continue
        step = int(step)
        slot = by_step.setdefault(step, {"score": None, "escalated": False})
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        if payload.get("p_ask") is not None:
            try:
                slot["score"] = float(payload["p_ask"])
            except (TypeError, ValueError):
                pass
        et = ev.get("event_type")
        if et == "ask" and payload.get("gated") is not True and payload.get("honoured") is not False:
            slot["escalated"] = True
        if et == "intervention" and payload.get("source") != "replayed_focal":
            slot["escalated"] = True
    return by_step


def collect_h3_for_arm(
    arm: dict[str, Any],
    labels: dict[str, list[int]],
) -> dict[str, Any]:
    grid_scores: list[float] = []
    grid_y: list[int] = []
    scored_scores: list[float] = []
    scored_y: list[int] = []
    real_p_ask: list[float] = []
    n_escalations = 0
    n_excluded_past_end = 0
    n_within_missing = 0
    loaded = arm["loaded"]
    runs: dict[tuple[str, int], dict[str, Any]] = loaded["runs"]
    # Locate events.jsonl beside each result.json via a second walk of the tree.
    events_index: dict[tuple[str, int], Path] = {}
    root = None
    # inventory does not keep paths; recover from rglob of the arm root stored
    # on loaded only if we stashed it. Fall back: caller sets arm["root"].
    root = arm.get("root")
    if root is not None:
        for path in Path(root).rglob("result.json"):
            row, err = j10._read_result(path)
            if row is None or err:
                continue
            task_id, seed = row.get("task_id"), row.get("seed")
            if task_id is None or seed is None:
                continue
            events_index[(str(task_id), int(seed))] = path.parent / "events.jsonl"

    for key, row in runs.items():
        task_id, seed = key
        lab_key = f"{task_id}/{seed}"
        if lab_key not in labels:
            continue
        positives = {int(s) for s in labels[lab_key]}
        steps = int(row.get("steps") or 0)
        by_step = gate_scores_from_events(events_index.get(key, Path()))
        n_escalations += sum(1 for slot in by_step.values() if slot.get("escalated"))
        for tick in tick_grid():
            slot = by_step.get(tick)
            grid_scores.append(slot_score(slot))
            grid_y.append(1 if tick in positives else 0)
            if tick > steps:
                n_excluded_past_end += 1
                continue
            if slot is None:
                n_within_missing += 1
            elif slot.get("score") is not None:
                real_p_ask.append(float(slot["score"]))
            scored_scores.append(slot_score(slot))
            scored_y.append(1 if tick in positives else 0)
    label = arm["label"]
    grid = h3_row(label, grid_scores, grid_y, n_escalations)
    scored = h3_row(label, scored_scores, scored_y, n_escalations)
    coincide = (
        scored.get("n") == grid.get("n")
        and scored.get("auroc") == grid.get("auroc")
        and scored.get("ece") == grid.get("ece")
        and scored.get("n_positive") == grid.get("n_positive")
    )
    chance_disagree = h3_auroc_chance_disagreement(
        grid.get("auroc"), scored.get("auroc")
    )
    return {
        "label": label,
        "headline_population": H3_HEADLINE_POPULATION,
        "auroc": scored.get("auroc"),
        "ece": scored.get("ece"),
        "n": scored.get("n"),
        "n_positive": scored.get("n_positive"),
        "n_escalations": n_escalations,
        "degenerate": scored.get("degenerate"),
        "note": scored.get("note"),
        "n_excluded_from_scored": n_excluded_past_end,
        "excluded_from_scored_reason": H3_EXCLUDED_REASON,
        "excluded_counts": {
            H3_EXCLUDED_REASON: n_excluded_past_end,
            "within_episode_missing_slot": n_within_missing,
        },
        "populations": {
            "scored": _h3_pop_fields(scored),
            "grid": _h3_pop_fields(grid),
        },
        "populations_coincide": coincide,
        "auroc_chance_disagreement": chance_disagree,
        "score_quantiles": score_quantiles(real_p_ask),
    }


def h3_calibration(
    arms: dict[str, dict[str, Any]],
    labels_path: Path | None,
) -> list[dict[str, Any]]:
    """AUROC and ECE of gate scores vs oracle labels. Degenerate gates stay as rows."""
    gated = [a for a in arms.values() if a.get("gated")]
    if not gated:
        return []
    if labels_path is None or not Path(labels_path).is_file():
        return [
            {
                "label": a["label"],
                "auroc": None,
                "ece": None,
                "n": None,
                "n_positive": None,
                "n_escalations": None,
                "degenerate": None,
                "note": f"oracle labels missing at {labels_path}",
            }
            for a in gated
        ]
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))
    if not isinstance(labels, dict):
        return [
            {
                "label": a["label"],
                "note": "oracle_labels.json is not an object",
                "auroc": None,
                "ece": None,
                "n_positive": None,
                "degenerate": None,
            }
            for a in gated
        ]
    return [collect_h3_for_arm(arm, labels) for arm in gated]


def _public_arm(arm: dict[str, Any]) -> dict[str, Any]:
    skip = {"cleaned", "loaded", "root"}
    return {k: v for k, v in arm.items() if k not in skip}


def format_table(arms: dict[str, dict[str, Any]], refusals: list[str]) -> str:
    lines: list[str] = []
    if refusals:
        lines.extend(refusals)
        lines.append("")
    lines.append(POPULATION_PREAMBLE)
    header = (
        f"{'arm':<28} {'n':>5} {'n_crashed':>10} "
        f"{'tgc_all':>8} {'tgc_surv':>8} {'gp_all':>8} {'gp_surv':>8} "
        f"{'calls':>8} {'crash/call%':>12}"
    )
    lines.append(header)
    lines.append("-" * len(header))

    def fmt(v: Any, width: int, digits: int = 4) -> str:
        if v is None:
            return f"{'NA':>{width}}"
        if isinstance(v, float):
            return f"{v:>{width}.{digits}f}"
        return f"{v:>{width}}"

    for label, arm in arms.items():
        if not arm.get("complete_n"):
            lines.append(
                f"{label:<28} {arm['n']:>5} {arm.get('n_crashed', 0):>10} "
                f"{'REFUSED':>8} {'—':>8} {'—':>8} {'—':>8} "
                f"{'—':>8} {'—':>12}"
            )
            continue
        crash_pct = arm.get("crash_per_call_pct")
        lines.append(
            f"{label:<28} {arm['n']:>5} {arm.get('n_crashed', 0):>10} "
            f"{fmt(arm.get('tgc_all'), 8)} {fmt(arm.get('tgc_survivors'), 8)} "
            f"{fmt(arm.get('goal_pass_all'), 8)} "
            f"{fmt(arm.get('goal_pass_survivors'), 8)} "
            f"{fmt(arm.get('planner_calls_total'), 8, 0)} "
            f"{fmt(crash_pct, 12, 2)}"
        )
    return "\n".join(lines)


def _fmt_metric(v: Any, width: int, digits: int = 4) -> str:
    if v is None:
        return f"{'NA':>{width}}"
    if isinstance(v, float):
        return f"{v:>{width}.{digits}f}"
    if isinstance(v, bool):
        return f"{str(v):>{width}}"
    return f"{v:>{width}}"


def h3_disagreement_lines(h3_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for row in h3_rows:
        if not row.get("auroc_chance_disagreement"):
            continue
        pops = row.get("populations") or {}
        grid_auroc = (pops.get("grid") or {}).get("auroc")
        scored_auroc = (pops.get("scored") or {}).get("auroc")
        grid_txt = "None" if grid_auroc is None else f"{float(grid_auroc):.4f}"
        scored_txt = "None" if scored_auroc is None else f"{float(scored_auroc):.4f}"
        lines.append(
            "CONTRAST DISAGREEMENT: "
            f"H3 AUROC {row.get('label')}: grid {grid_txt} vs scored "
            f"{scored_txt} disagree on whether AUROC exceeds 0.5."
        )
    return lines


def h3_population_notes(h3_rows: list[dict[str, Any]]) -> list[str]:
    notes: list[str] = []
    for row in h3_rows:
        label = row.get("label")
        if row.get("populations_coincide"):
            notes.append(
                f"{label}: scored and grid H3 populations coincide"
            )
        reason = row.get("excluded_from_scored_reason")
        n_ex = row.get("n_excluded_from_scored")
        if n_ex:
            notes.append(
                f"{label}: excluded {n_ex} ticks from scored ({reason})"
            )
    return notes


def format_h3_table(h3_rows: list[dict[str, Any]]) -> str:
    if not h3_rows:
        return ""
    lines: list[str] = [
        H3_POPULATIONS,
        f"headline H3 population: {H3_HEADLINE_POPULATION} (primary)",
    ]
    header = (
        f"{'gate':<22} {'pop':<16} {'AUROC':>8} {'ECE':>8} "
        f"{'n':>6} {'n_pos':>6} {'excl':>6} {'esc':>6} {'degen':>6}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for row in h3_rows:
        pops = row.get("populations")
        if not pops:
            lines.append(
                f"{str(row.get('label')):<22} "
                f"{'NA':<16} {'NA':>8} {'NA':>8} "
                f"{'NA':>6} {'NA':>6} {'NA':>6} "
                f"{_fmt_metric(row.get('n_escalations'), 6, 0)} "
                f"{_fmt_metric(row.get('degenerate'), 6)} "
                f"  {row.get('note') or ''}".rstrip()
            )
            continue
        for pop_name, primary in (("scored", True), ("grid", False)):
            pop = pops.get(pop_name) or {}
            pop_label = "scored (primary)" if primary else "grid"
            excl = row.get("n_excluded_from_scored") if primary else 0
            lines.append(
                f"{str(row.get('label')):<22} {pop_label:<16} "
                f"{_fmt_metric(pop.get('auroc'), 8)} "
                f"{_fmt_metric(pop.get('ece'), 8)} "
                f"{_fmt_metric(pop.get('n'), 6, 0)} "
                f"{_fmt_metric(pop.get('n_positive'), 6, 0)} "
                f"{_fmt_metric(excl, 6, 0)} "
                f"{_fmt_metric(row.get('n_escalations'), 6, 0)} "
                f"{_fmt_metric(row.get('degenerate'), 6)}"
            )
    for note in h3_population_notes(h3_rows):
        lines.append(note)
    for line in h3_disagreement_lines(h3_rows):
        lines.append(line)
    return "\n".join(lines)


def format_score_quantile_table(h3_rows: list[dict[str, Any]]) -> str:
    if not h3_rows:
        return ""
    lines: list[str] = [
        "real p_ask quantiles (scored ticks that emitted a probability; "
        "excludes the 0/1 escalation fallback)"
    ]
    header = (
        f"{'gate':<22} {'n':>6} {'mean':>10} {'min':>10} {'median':>10} "
        f"{'p90':>10} {'p95':>10} {'p99':>10} {'max':>10}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for row in h3_rows:
        q = row.get("score_quantiles") or {}
        lines.append(
            f"{str(row.get('label')):<22} "
            f"{_fmt_metric(q.get('n'), 6, 0)} "
            f"{_fmt_metric(q.get('mean'), 10, 6)} "
            f"{_fmt_metric(q.get('min'), 10, 6)} "
            f"{_fmt_metric(q.get('median'), 10, 6)} "
            f"{_fmt_metric(q.get('p90'), 10, 6)} "
            f"{_fmt_metric(q.get('p95'), 10, 6)} "
            f"{_fmt_metric(q.get('p99'), 10, 6)} "
            f"{_fmt_metric(q.get('max'), 10, 6)}"
        )
    return "\n".join(lines)


def build_report(
    arm_dirs: dict[str, Path],
    seeds: list[int],
    oracle_labels: Path | None,
) -> tuple[dict[str, Any], int]:
    for directory in arm_dirs.values():
        marker = j10.heldout_marker_in_path(directory)
        if marker:
            reason = (
                f"refusing path {directory} because it contains {marker!r}; "
                "j8_frontier is a dev-split script"
            )
            report = {
                "refused": True,
                "headline": None,
                "reason": reason,
            }
            return report, 2

    oracle_info = establish_oracle_semantics()
    loaded_by_arm = {label: j10.load_arm_tree(path) for label, path in arm_dirs.items()}
    arms: dict[str, dict[str, Any]] = {}
    for label, loaded in loaded_by_arm.items():
        arm = summarise_arm(label, loaded, seeds)
        arm["root"] = arm_dirs[label]
        arms[label] = arm

    arm_n = {label: arm["n"] for label, arm in arms.items()}
    refusals = refuse_partial_arms(arm_n)
    headline_ok = not refusals
    headline = None
    if headline_ok:
        headline = (
            "J8 frontier (dev): all named arms have ≥114 rows. "
            "Headline quality contrast uses all-episodes (crash = 0) for every "
            "metric; survivor population is reported alongside."
        )
    else:
        headline = None

    complete = {k: v for k, v in arms.items() if v.get("complete_n")}
    contrasts: dict[str, Any] = {}
    disagreements: list[dict[str, Any]] = []
    if complete:
        for a, b in combinations(complete.keys(), 2):
            tgc_all_c = paired_contrast(complete[a], complete[b], "tgc", "all")
            tgc_surv_c = paired_contrast(
                complete[a], complete[b], "tgc", "survivors"
            )
            gp_all_c = paired_contrast(
                complete[a], complete[b], "goal_pass_rate", "all"
            )
            gp_surv_c = paired_contrast(
                complete[a], complete[b], "goal_pass_rate", "survivors"
            )
            contrasts[f"tgc_all_{a}_minus_{b}"] = tgc_all_c
            contrasts[f"tgc_survivors_{a}_minus_{b}"] = tgc_surv_c
            contrasts[f"tgc_{a}_minus_{b}"] = tgc_all_c
            contrasts[f"goal_pass_all_{a}_minus_{b}"] = gp_all_c
            contrasts[f"goal_pass_survivors_{a}_minus_{b}"] = gp_surv_c
            contrasts[f"goal_pass_rate_{a}_minus_{b}"] = gp_all_c
            contrasts[f"calls_live_{a}_minus_{b}"] = paired_contrast(
                complete[a], complete[b], "planner_calls_live"
            )
            for all_c, surv_c in ((tgc_all_c, tgc_surv_c), (gp_all_c, gp_surv_c)):
                info = population_contrast_disagreement(all_c, surv_c)
                if info["disagree"]:
                    disagreements.append(info)

    frontier = frontier_table(arms)
    headroom = oracle_headroom(arms, oracle_info) if headline_ok else {
        "error": "headline refused; not emitting headroom"
    }

    fixed = {
        int(a["k"]): a
        for a in complete.values()
        if a.get("k") in {3, 5, 7, 10}
    }
    f1_rows: dict[str, Any] = {}
    k5 = fixed.get(FIXED_K_REFERENCE)
    for label, arm in complete.items():
        if not arm.get("gated"):
            continue
        choice = choose_k_matched(arm, fixed)
        if choice.get("k_matched") is None or k5 is None:
            f1_rows[label] = {
                "holds": None,
                "reason": "k_matched or fixed_k(5) unavailable",
                "k_matched": choice,
            }
            continue
        matched = fixed[choice["k_matched"]]
        quality = paired_contrast(arm, matched, "tgc")
        calls = paired_contrast(arm, k5, "planner_calls_live")
        row = f1_test(quality, calls)
        row["k_matched"] = choice
        row["fixed_k_5_label"] = k5["label"]
        f1_rows[label] = row

    h3 = h3_calibration(arms, oracle_labels)

    report: dict[str, Any] = {
        "headline": headline,
        "headline_refused": not headline_ok,
        "refusals": refusals,
        "oracle_semantics": oracle_info["line"],
        "oracle_semantics_citation": oracle_info["citation"],
        "oracle_semantics_established": oracle_info["established"],
        "min_rows": MIN_ROWS,
        "seeds": seeds,
        "resample_unit": j10.RESAMPLE_UNIT,
        "planner_calls_definition": (
            "planner_calls_per_episode is the mean of ledger live "
            "totals.planner_calls_total; planner_calls_replay_inclusive_"
            "per_episode is the mean of RunResult.n_planner_calls. "
            "The live count is never silently replaced by the replay count."
        ),
        "arms": {label: _public_arm(arm) for label, arm in arms.items()},
        "contrasts": contrasts,
        "frontier": frontier,
        "oracle_headroom": headroom,
        "f1": f1_rows,
        "h3": h3,
        "h3_headline_population": H3_HEADLINE_POPULATION,
        "h3_populations": H3_POPULATIONS,
        "h3_score_quantiles": {
            row["label"]: row.get("score_quantiles")
            for row in h3
            if isinstance(row, dict) and row.get("label") is not None
        },
        "headline_population": HEADLINE_POPULATION,
        "population_preamble": POPULATION_PREAMBLE,
        "population_notes": population_notes(arms),
        "population_disagreements": disagreements,
        "population_disagreements_text": disagreement_lines(disagreements),
        "contrast_accounting": contrast_accounting_lines(contrasts),
        "quality_populations": (
            "tgc_all and goal_pass_all average every episode (crash scores 0). "
            "tgc_survivors and goal_pass_survivors average episodes with "
            "error_type != 'crash'. Headline contrast uses all-episodes for "
            "every quality metric. Survivor paired contrasts drop a "
            "(task_id, seed) pair if either arm crashed."
        ),
    }
    code = 0 if headline_ok else 1
    return report, code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    arm_dirs: dict[str, Path] = {}
    for label, path in args.arm:
        if label in arm_dirs:
            print(
                json.dumps({"refused": True, "reason": f"duplicate --arm {label}"}),
                file=sys.stderr,
            )
            return 2
        arm_dirs[label] = path
    try:
        seeds = parse_seeds(args.seeds)
    except ValueError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}))
        return 2
    report, code = build_report(arm_dirs, seeds, args.oracle_labels)
    table = format_table(report["arms"], report.get("refusals") or [])
    print(report.get("oracle_semantics") or "")
    print(table)
    for line in report.get("population_notes") or []:
        print(line)
    for line in report.get("contrast_accounting") or []:
        print(line)
    for line in report.get("population_disagreements_text") or []:
        print(line)
    h3_table = format_h3_table(report.get("h3") or [])
    if h3_table:
        print()
        print(h3_table)
    q_table = format_score_quantile_table(report.get("h3") or [])
    if q_table:
        print()
        print(q_table)
    if report.get("headline"):
        print(f"\nheadline: {report['headline']}")
    else:
        print("\nheadline: (refused)")
    text = json.dumps(report, indent=2, default=str) + "\n"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
