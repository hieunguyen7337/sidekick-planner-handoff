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

_NC_SPEC = importlib.util.spec_from_file_location(
    "j8_noncached_cost", Path(__file__).resolve().parent / "j8_noncached_cost.py"
)
_nc = importlib.util.module_from_spec(_NC_SPEC)
assert _NC_SPEC.loader is not None
_NC_SPEC.loader.exec_module(_nc)
attach_sft_plan_source_plan_tokens = _nc.attach_sft_plan_source_plan_tokens
noncached_episode_cost = _nc.noncached_episode_cost

from scripts.setup.campaign_summarize import BROKEN  # noqa: E402
from scripts.setup.hj1_gate import paired_diff  # noqa: E402

MIN_ROWS = 114
F1_QUALITY_PP = 7.0
COST_KEY_DEFAULT = "planner_calls_live"
COST_KEYS = (
    "planner_calls_live",
    "planner_tokens_live",
    "replayed_planner_tokens",
    "planner_tokens_noncached",
)
DEFAULT_SFT_PLAN_PACKET_SOURCE = Path(
    "/scratch/n12194778/sidekick/results/hj1b_planner_20260915"
)
DEFAULT_SFT_PLAN_PACKET_SYSTEM = "planner_alone"
COST_KEY_NOTES = {
    "planner_calls_live": (
        "planner_calls_live counts ledger totals.planner_calls_total per episode."
    ),
    "planner_tokens_live": (
        "planner_tokens_live is ledger planner_tokens_total "
        "(input + cached_input + output + reasoning)."
    ),
    "replayed_planner_tokens": (
        "replayed_planner_tokens is the handoff payload sum excluding cached "
        "input, else ledger planner_tokens_total which includes cached input."
    ),
    "planner_tokens_noncached": (
        "planner_tokens_noncached is live planner input+output+reasoning plus "
        "replayed_planner_tokens (and sft_plan's matched source plan-event "
        "tokens); cached_input_tokens are excluded."
    ),
}
HANDOFF_KEYS = (
    "effective_m",
    "handoff_occurred",
    "hash_ok",
    "replayed_planner_tokens",
    "n_source_actions",
)
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
HANDOFF_ONLY_POPULATION = "handoff-only"
NO_HANDOFF_POPULATION = "no-handoff"
HANDOFF_ONLY_ALIASES = {HANDOFF_ONLY_POPULATION, "handoff_only"}
NO_HANDOFF_ALIASES = {NO_HANDOFF_POPULATION, "no_handoff", "complement"}
# Gap at which the reference is described as far higher on no-handoff
# than on handoff-only. Five points is inside the 7pp non-inferiority
# margin; it is a reporting threshold, not a preregistered test.
REFERENCE_FAR_HIGHER_PP = 5.0
POPULATION_PREAMBLE = (
    "Headline quality contrast uses all-episodes for every metric "
    "(crashed episode scores 0). Survivor columns/contrasts use episodes "
    "with error_type != 'crash'; a paired survivor contrast drops a "
    "(task_id, seed) pair if either side crashed. "
    "handoff-only restricts every arm in a contrast to the (task_id, seed) "
    "keys where the comparison arm's report event has handoff_occurred "
    "true (all-episodes scoring: crash = 0). no-handoff is the complement "
    "(handoff_occurred false) on those same keys."
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
    p.add_argument(
        "--cost-key",
        default=COST_KEY_DEFAULT,
        choices=list(COST_KEYS),
        help=(
            "Per-episode cost field for the frontier and chord axis. "
            "Default planner_calls_live (unchanged). Use "
            "planner_tokens_noncached for the prefix token axis (cached input "
            "excluded on every arm). A recorded 0 is a valid cost; arms are "
            "not dropped and crash/call is not divided by 0."
        ),
    )
    p.add_argument(
        "--packet-source",
        type=Path,
        default=DEFAULT_SFT_PLAN_PACKET_SOURCE,
        help=(
            "Campaign tree sft_plan replays, keyed "
            "<packet-source>/<packet-system>/<seed>/<task_id>/events.jsonl. "
            "Used to charge sft_plan the non-cached plan-event tokens it "
            "replays. Default is the HJ-1 planner_alone archive."
        ),
    )
    p.add_argument(
        "--packet-system",
        default=DEFAULT_SFT_PLAN_PACKET_SYSTEM,
        help="System subdirectory under --packet-source (default planner_alone).",
    )
    p.add_argument(
        "--reference-arm",
        default=None,
        help="Arm label for non-inferiority (and chord). Omit to skip.",
    )
    p.add_argument(
        "--floor-arm",
        default=None,
        help="Floor arm label for the chord test (typically sft_plan).",
    )
    p.add_argument(
        "--handoff-keys-from",
        default=None,
        metavar="ARM",
        help=(
            "Build every arm's handoff-only and no-handoff populations from "
            "this named arm's handoff_occurred flags, instead of each arm "
            "using its own. The reference and floor are restricted to the "
            "same keys. An unknown name is fatal and lists the valid arms. "
            "Omit to keep per-arm keys (default, unchanged)."
        ),
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


def handoff_flag_keys(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    occurred: bool,
) -> set[tuple[str, int]]:
    """Keys whose report payload has handoff_occurred is True/False.

    Missing (None) is neither: it does not enter handoff-only or no-handoff.
    """
    want = bool(occurred)
    return {
        key
        for key, row in cleaned.items()
        if row.get("handoff_occurred") is want
    }


def restrict_to_defining_handoff(
    defining: dict[tuple[str, int], dict[str, Any]],
    others: list[dict[tuple[str, int], dict[str, Any]]],
    occurred: bool,
) -> tuple[set[tuple[str, int]], int, int]:
    """Shared keys selected by the defining arm's handoff_occurred flag.

    Pairing stays honest: the subset is defined on `defining`, then every
    other map is restricted to that same (task_id, seed) set, never to
    each arm's own handoff flag.
    """
    shared = set(defining)
    for other in others:
        shared &= set(other)
    flag_keys = handoff_flag_keys(defining, occurred)
    kept = shared & flag_keys
    n_dropped_handoff = len(shared) - len(kept)
    return kept, len(shared), n_dropped_handoff


def resolve_handoff_keys_arm(
    arms: dict[str, dict[str, Any]],
    handoff_keys_from: str | None,
) -> dict[str, Any] | None:
    """Return the named arm, or None when the flag is omitted.

    An unknown name is fatal and lists the valid arms. Never fall back
    to per-arm keys: that is the misreading this flag exists to prevent.
    """
    if handoff_keys_from is None:
        return None
    if handoff_keys_from not in arms:
        valid = ", ".join(sorted(arms))
        raise ValueError(
            f"--handoff-keys-from {handoff_keys_from!r} is not among named "
            f"arms ({valid})"
        )
    return arms[handoff_keys_from]


def _defining_handoff_arm(
    arm: dict[str, Any],
    handoff_keys_arm: dict[str, Any] | None,
) -> dict[str, Any]:
    return arm if handoff_keys_arm is None else handoff_keys_arm


def _handoff_keep(
    arm_cleaned: dict[tuple[str, int], dict[str, Any]],
    other_cleaneds: list[dict[tuple[str, int], dict[str, Any]]],
    occurred: bool,
    handoff_keys_arm: dict[str, Any] | None,
) -> tuple[set[tuple[str, int]], int, int]:
    """Default path calls restrict_to_defining_handoff exactly as before."""
    if handoff_keys_arm is None:
        return restrict_to_defining_handoff(arm_cleaned, other_cleaneds, occurred)
    others = [arm_cleaned, *other_cleaneds]
    return restrict_to_defining_handoff(
        handoff_keys_arm["cleaned"], others, occurred
    )


def handoff_keys_record(defining: dict[str, Any]) -> dict[str, Any]:
    """Pinned-arm name and handoff-only key-set size for JSON readers."""
    cleaned = defining["cleaned"]
    return {
        "handoff_keys_from": defining["label"],
        "handoff_keys_n": len(handoff_flag_keys(cleaned, True)),
    }


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
        if arm.get("handoff_only_coincides_with_all"):
            notes.append(
                f"{label}: every episode handed off; "
                "handoff-only and all-episodes populations coincide"
            )
        else:
            n_nh = int(arm.get("n_no_handoff") or 0)
            if n_nh > 0:
                notes.append(
                    f"{label}: {n_nh} episodes did not hand off; "
                    f"handoff-only n={int(arm.get('n_handoff_occurred') or 0)}"
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
        row["system"] = raw.get("system")
        per_actor = totals.get("per_actor")
        planner = per_actor.get("planner") if isinstance(per_actor, dict) else None
        if isinstance(planner, dict):
            inp = float(planner.get("input_tokens") or 0)
            out = float(planner.get("output_tokens") or 0)
            reas = float(planner.get("reasoning_output_tokens") or 0)
            cached = float(planner.get("cached_input_tokens") or 0)
            live_nc = inp + out + reas
            inclusive = live_nc + cached
            row["planner_tokens_noncached_live"] = live_nc
            row["cached_input_tokens"] = cached
            row["cached_share_of_inclusive_total"] = (
                (cached / inclusive) if inclusive else None
            )
        else:
            row["planner_tokens_noncached_live"] = None
            row["cached_input_tokens"] = None
            row["cached_share_of_inclusive_total"] = None
        row.setdefault("sft_plan_replayed_plan_tokens", None)


def _handoff_facts_from_events_text(text: str) -> dict[str, Any]:
    facts: dict[str, Any] = {key: None for key in HANDOFF_KEYS}
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
        if not isinstance(ev, dict):
            continue
        events.append(ev)
        if ev.get("event_type") == "run_start":
            last_start = len(events) - 1
    for ev in events[last_start:]:
        payload = ev.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for key in HANDOFF_KEYS:
            if key in payload and payload[key] is not None:
                facts[key] = payload[key]
    if facts["effective_m"] is not None:
        try:
            facts["effective_m"] = int(facts["effective_m"])
        except (TypeError, ValueError):
            facts["effective_m"] = None
    if facts["n_source_actions"] is not None:
        try:
            facts["n_source_actions"] = int(facts["n_source_actions"])
        except (TypeError, ValueError):
            facts["n_source_actions"] = None
    if facts["replayed_planner_tokens"] is not None:
        try:
            facts["replayed_planner_tokens"] = float(facts["replayed_planner_tokens"])
        except (TypeError, ValueError):
            facts["replayed_planner_tokens"] = None
    if facts["handoff_occurred"] is not None:
        facts["handoff_occurred"] = bool(facts["handoff_occurred"])
    if facts["hash_ok"] is not None:
        facts["hash_ok"] = bool(facts["hash_ok"])
    return facts


def attach_handoff_fields(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    root: Path | None,
) -> None:
    """Copy handoff payload fields onto cleaned rows. Missing stays None."""
    for row in cleaned.values():
        for key in HANDOFF_KEYS:
            row.setdefault(key, None)
    if root is None or not Path(root).exists():
        return
    for path in sorted(Path(root).rglob("events.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        facts = _handoff_facts_from_events_text(text)
        task_id = None
        seed = None
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
            if ev.get("task_id") is not None:
                task_id = str(ev["task_id"])
            if ev.get("seed") is not None:
                try:
                    seed = int(ev["seed"])
                except (TypeError, ValueError):
                    seed = None
            if task_id is not None and seed is not None:
                break
        if task_id is None or seed is None:
            continue
        row = cleaned.get((task_id, seed))
        if row is None:
            continue
        for key, value in facts.items():
            if value is not None:
                row[key] = value


def episode_cost(row: dict[str, Any], cost_key: str) -> Optional[float]:
    """Per-episode cost. A recorded 0 is kept; missing stays None."""
    if cost_key not in COST_KEYS:
        raise ValueError(f"unknown cost-key {cost_key!r}")
    if cost_key == "planner_calls_live":
        value = row.get("planner_calls_live")
        return None if value is None else float(value)
    if cost_key == "planner_tokens_live":
        value = row.get("planner_tokens_live")
        return None if value is None else float(value)
    if cost_key == "planner_tokens_noncached":
        return noncached_episode_cost(row)
    value = row.get("replayed_planner_tokens")
    if value is not None:
        return float(value)
    live_tokens = row.get("planner_tokens_live")
    return None if live_tokens is None else float(live_tokens)


def _bool01(value: Any) -> Optional[float]:
    if value is None:
        return None
    return 1.0 if value else 0.0


def mean_present(values: list[Any]) -> Optional[float]:
    present = [float(v) for v in values if v is not None]
    if not present:
        return None
    return round(statistics.fmean(present), 6)


def sum_or_none(values: list[Any]) -> Optional[float]:
    if not values or any(v is None for v in values):
        return None
    return float(sum(float(v) for v in values))


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
    root: Path | None = None,
    cost_key: str = COST_KEY_DEFAULT,
    packet_source: Path | None = DEFAULT_SFT_PLAN_PACKET_SOURCE,
    packet_system: str = DEFAULT_SFT_PLAN_PACKET_SYSTEM,
) -> dict[str, Any]:
    runs: dict[tuple[str, int], dict[str, Any]] = loaded["runs"]
    n = len(runs)
    tasks = sorted({task_id for task_id, seed in runs if seed in set(seeds)})
    inv = j10.inventory_arm(label, loaded, tasks, seeds)
    attach_ledger_fields(inv["cleaned"], runs)
    attach_handoff_fields(inv["cleaned"], root)
    sft_plan_floor_costing = attach_sft_plan_source_plan_tokens(
        inv["cleaned"], label, packet_source, packet_system
    )
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
    for row in cleaned.values():
        row["cost_value"] = episode_cost(row, cost_key)
    cost_vals = [row.get("cost_value") for row in cleaned.values()]
    cost_vals_surv = [row.get("cost_value") for row in survivors]
    cached_vals = [row.get("cached_input_tokens") for row in cleaned.values()]
    cached_share_vals = [
        row.get("cached_share_of_inclusive_total") for row in cleaned.values()
    ]
    handoff_all = [_bool01(row.get("handoff_occurred")) for row in cleaned_rows]
    handoff_surv = [_bool01(row.get("handoff_occurred")) for row in survivors]
    hash_all = [_bool01(row.get("hash_ok")) for row in cleaned_rows]
    hash_surv = [_bool01(row.get("hash_ok")) for row in survivors]
    em_all = [row.get("effective_m") for row in cleaned_rows]
    em_surv = [row.get("effective_m") for row in survivors]
    n_handoff_record = sum(
        1
        for row in cleaned_rows
        if row.get("handoff_occurred") is not None
        or row.get("hash_ok") is not None
        or row.get("effective_m") is not None
    )
    handoff_rows = [
        row for row in cleaned_rows if row.get("handoff_occurred") is True
    ]
    no_handoff_rows = [
        row for row in cleaned_rows if row.get("handoff_occurred") is False
    ]
    n_no_handoff = len(no_handoff_rows)
    tgc_handoff_only = mean_quality(handoff_rows, "tgc", crash_as_zero=True)
    tgc_no_handoff = mean_quality(no_handoff_rows, "tgc", crash_as_zero=True)
    goal_pass_handoff_only = mean_quality(
        handoff_rows, "goal_pass_rate", crash_as_zero=True
    )
    goal_pass_no_handoff = mean_quality(
        no_handoff_rows, "goal_pass_rate", crash_as_zero=True
    )
    n_handoff_occurred = sum(
        1 for row in cleaned_rows if row.get("handoff_occurred") is True
    )
    handoff_only_coincides_with_all = bool(n > 0 and n_handoff_occurred == n)
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
        "tgc_handoff_only": tgc_handoff_only,
        "tgc_no_handoff": tgc_no_handoff,
        "goal_pass_handoff_only": goal_pass_handoff_only,
        "goal_pass_no_handoff": goal_pass_no_handoff,
        "n_no_handoff": n_no_handoff,
        "handoff_only_coincides_with_all": handoff_only_coincides_with_all,
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
        "cost_key": cost_key,
        "cost_per_episode": mean_or_none(cost_vals) if complete_n else None,
        "cost_per_episode_survivors": mean_present(cost_vals_surv),
        "cost_total": sum_or_none(cost_vals) if complete_n else None,
        "cached_input_tokens_per_episode": mean_present(cached_vals),
        "cached_share_of_inclusive_total": mean_present(cached_share_vals),
        "sft_plan_source_plan_tokens_mean": (
            sft_plan_floor_costing.get("mean_noncached_plan_tokens")
            if sft_plan_floor_costing.get("applied")
            else None
        ),
        "sft_plan_floor_costing": sft_plan_floor_costing,
        "cost_key_note": COST_KEY_NOTES.get(cost_key),
        "handoff_occurred_rate": mean_present(handoff_all),
        "handoff_occurred_rate_all": mean_present(handoff_all),
        "handoff_occurred_rate_survivors": mean_present(handoff_surv),
        "hash_ok_rate": mean_present(hash_all),
        "hash_ok_rate_all": mean_present(hash_all),
        "hash_ok_rate_survivors": mean_present(hash_surv),
        "effective_m_mean": mean_present(em_all),
        "effective_m_mean_all": mean_present(em_all),
        "effective_m_mean_survivors": mean_present(em_surv),
        "n_handoff_occurred": n_handoff_occurred,
        "n_hash_ok": sum(1 for row in cleaned_rows if row.get("hash_ok") is True),
        "n_with_handoff_record": n_handoff_record,
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
    handoff_keys_arm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Task-clustered paired bootstrap. Delegates to j10_report / hj1_gate.

    population='all': every shared (task_id, seed); crashed quality scores 0.
    population='survivors': drop a pair if either side crashed, and count it.
    population='handoff-only': shared keys where the defining arm's
    handoff_occurred is True; arm_b (and any later arm) is restricted to
    those same keys. The defining arm is arm_a unless handoff_keys_arm is
    set (CLI --handoff-keys-from).
    population='no-handoff': the complement (handoff_occurred is False).
    Handoff subsets use all-episodes scoring (crash = 0).
    """
    left = arm_a["cleaned"]
    right = arm_b["cleaned"]
    n_shared = len(set(left) & set(right))
    n_dropped_crash = 0
    n_dropped_handoff = 0
    if population in {"survivors", "survivor"}:
        left, right, n_dropped_crash, n_shared = both_survived_subset(left, right)
        pop_name = "survivors"
    elif population in {"all", "all-episodes"}:
        if field in {"tgc", "goal_pass_rate"}:
            left = coerce_crash_quality(left, field)
            right = coerce_crash_quality(right, field)
        pop_name = "all-episodes"
    elif population in HANDOFF_ONLY_ALIASES or population in NO_HANDOFF_ALIASES:
        occurred = population in HANDOFF_ONLY_ALIASES
        keep, n_shared, n_dropped_handoff = _handoff_keep(
            left, [right], occurred, handoff_keys_arm
        )
        left = {k: left[k] for k in keep}
        right = {k: right[k] for k in keep}
        if field in {"tgc", "goal_pass_rate"}:
            left = coerce_crash_quality(left, field)
            right = coerce_crash_quality(right, field)
        pop_name = (
            HANDOFF_ONLY_POPULATION if occurred else NO_HANDOFF_POPULATION
        )
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
    if pop_name in {HANDOFF_ONLY_POPULATION, NO_HANDOFF_POPULATION}:
        out["n_pairs_dropped_handoff"] = n_dropped_handoff
        defining = _defining_handoff_arm(arm_a, handoff_keys_arm)
        out["defining_arm"] = defining["label"]
        out["handoff_keys_from"] = defining["label"]
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
                "cost_key": arm.get("cost_key"),
                "cost_per_episode": arm.get("cost_per_episode"),
                "cached_input_tokens_per_episode": arm.get(
                    "cached_input_tokens_per_episode"
                ),
                "cached_share_of_inclusive_total": arm.get(
                    "cached_share_of_inclusive_total"
                ),
                "sft_plan_source_plan_tokens_mean": arm.get(
                    "sft_plan_source_plan_tokens_mean"
                ),
                "handoff_occurred_rate": arm.get("handoff_occurred_rate"),
                "hash_ok_rate": arm.get("hash_ok_rate"),
                "effective_m_mean": arm.get("effective_m_mean"),
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



NI_RULE = (
    "contrast is arm minus reference; non-inferior if ci95_pp[0] >= -7.00 "
    "(equivalently, deficit CI upper bound = -ci95_pp[0] <= 7.00). "
    "Primary metric goal_pass_rate; TGC always reported alongside."
)
NI_POPULATION_KEYS = (
    "goal_pass_all",
    "tgc_all",
    "goal_pass_survivors",
    "tgc_survivors",
    "goal_pass_handoff_only",
    "tgc_handoff_only",
    "goal_pass_no_handoff",
    "tgc_no_handoff",
)


def _attach_side_scores(
    out: dict[str, Any],
    arm: dict[str, Any],
    reference: dict[str, Any],
    field: str,
    keys: set[tuple[str, int]],
    floor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add arm/reference (and optional floor) means on the same key set."""
    arm_rows = [arm["cleaned"][k] for k in keys if k in arm["cleaned"]]
    ref_rows = [
        reference["cleaned"][k] for k in keys if k in reference["cleaned"]
    ]
    out["arm_score"] = mean_quality(arm_rows, field, crash_as_zero=True)
    out["reference_score"] = mean_quality(
        ref_rows, field, crash_as_zero=True
    )
    out["n_score_keys"] = len(keys)
    if floor is not None:
        floor_rows = [
            floor["cleaned"][k] for k in keys if k in floor["cleaned"]
        ]
        out["floor_score"] = mean_quality(
            floor_rows, field, crash_as_zero=True
        )
    return out


def handoff_reference_ease(
    arm: dict[str, Any],
    reference: dict[str, Any],
    handoff_keys_arm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare the reference on handoff-only vs no-handoff keys."""
    fields: dict[str, Any] = {}
    for field in ("goal_pass_rate", "tgc"):
        ho, _, _ = _handoff_keep(
            arm["cleaned"], [reference["cleaned"]], True, handoff_keys_arm
        )
        nh, _, _ = _handoff_keep(
            arm["cleaned"], [reference["cleaned"]], False, handoff_keys_arm
        )
        ref_ho = mean_quality(
            [reference["cleaned"][k] for k in ho], field, crash_as_zero=True
        )
        ref_nh = mean_quality(
            [reference["cleaned"][k] for k in nh], field, crash_as_zero=True
        )
        arm_ho = mean_quality(
            [arm["cleaned"][k] for k in ho], field, crash_as_zero=True
        )
        arm_nh = mean_quality(
            [arm["cleaned"][k] for k in nh], field, crash_as_zero=True
        )
        gap = None if ref_ho is None or ref_nh is None else round(ref_nh - ref_ho, 6)
        higher = None if gap is None else bool(gap > 0)
        far = None if gap is None else bool(gap >= REFERENCE_FAR_HIGHER_PP / 100.0)
        fields[field] = {
            "n_handoff_only": len(ho),
            "n_no_handoff": len(nh),
            "arm_score_handoff_only": arm_ho,
            "arm_score_no_handoff": arm_nh,
            "reference_score_handoff_only": ref_ho,
            "reference_score_no_handoff": ref_nh,
            "reference_higher_on_no_handoff": higher,
            "reference_gap_no_handoff_minus_handoff_only": gap,
            "reference_far_higher_on_no_handoff": far,
        }
    gp = fields["goal_pass_rate"]
    note = None
    if gp.get("n_no_handoff", 0) == 0:
        note = None
    elif gp.get("reference_far_higher_on_no_handoff"):
        gap_pp = None
        if gp.get("reference_gap_no_handoff_minus_handoff_only") is not None:
            gap_pp = round(
                100.0 * float(gp["reference_gap_no_handoff_minus_handoff_only"]), 2
            )
        note = (
            "reference scores far higher on no-handoff episodes than on "
            f"handoff-only (gap {gap_pp} pp); no-handoff tasks look easier "
            "for the reference, so the pooled all-episodes hybrid figure "
            "mixes planner-like scores on easy tasks with hybrid scores "
            "on the rest"
        )
    elif gp.get("reference_higher_on_no_handoff"):
        gap_pp = round(
            100.0 * float(gp["reference_gap_no_handoff_minus_handoff_only"]), 2
        )
        note = (
            "reference scores higher on no-handoff episodes than on "
            f"handoff-only (gap {gap_pp} pp)"
        )
    defining = _defining_handoff_arm(arm, handoff_keys_arm)
    return {
        "defining_arm": defining["label"],
        "reference_arm": reference["label"],
        "fields": fields,
        "note": note,
        "far_higher_threshold_pp": REFERENCE_FAR_HIGHER_PP,
    }


def noninferiority_row(
    arm: dict[str, Any],
    reference: dict[str, Any],
    field: str,
    population: str = "all",
    handoff_keys_arm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Paired task-clustered non-inferiority vs the reference arm."""
    contrast = paired_contrast(
        arm, reference, field, population, handoff_keys_arm=handoff_keys_arm
    )
    ci = contrast.get("ci95_pp")
    holds = None
    deficit_upper_pp = None
    if isinstance(ci, (list, tuple)) and len(ci) >= 2 and ci[0] is not None:
        deficit_upper_pp = round(-float(ci[0]), 6)
        holds = bool(float(ci[0]) >= -F1_QUALITY_PP)
    out = dict(contrast)
    out["holds"] = holds
    out["margin_pp"] = F1_QUALITY_PP
    out["deficit_ci_upper_pp"] = deficit_upper_pp
    out["rule"] = NI_RULE
    out["primary"] = field == "goal_pass_rate"
    pop_name = out.get("population")
    if pop_name in {HANDOFF_ONLY_POPULATION, NO_HANDOFF_POPULATION}:
        occurred = pop_name == HANDOFF_ONLY_POPULATION
        keys, _, _ = _handoff_keep(
            arm["cleaned"], [reference["cleaned"]], occurred, handoff_keys_arm
        )
        _attach_side_scores(out, arm, reference, field, keys)
    return out


def noninferiority_block(
    arms: dict[str, dict[str, Any]],
    reference_label: str | None,
    handoff_keys_from: str | None = None,
) -> dict[str, Any] | None:
    pinned = resolve_handoff_keys_arm(arms, handoff_keys_from)
    if not reference_label:
        return None
    if reference_label not in arms:
        return {
            "error": f"--reference-arm {reference_label!r} is not among named arms",
            "reference_arm": reference_label,
        }
    reference = arms[reference_label]
    if not reference.get("complete_n"):
        return {
            "error": (
                f"--reference-arm {reference_label!r} has "
                f"{reference.get('n')} rows (need {MIN_ROWS})"
            ),
            "reference_arm": reference_label,
        }
    rows: dict[str, Any] = {}
    for label, arm in arms.items():
        if label == reference_label or not arm.get("complete_n"):
            continue
        rows[label] = {
            "goal_pass_all": noninferiority_row(
                arm, reference, "goal_pass_rate", "all", pinned
            ),
            "goal_pass_survivors": noninferiority_row(
                arm, reference, "goal_pass_rate", "survivors", pinned
            ),
            "goal_pass_handoff_only": noninferiority_row(
                arm, reference, "goal_pass_rate", HANDOFF_ONLY_POPULATION, pinned
            ),
            "goal_pass_no_handoff": noninferiority_row(
                arm, reference, "goal_pass_rate", NO_HANDOFF_POPULATION, pinned
            ),
            "tgc_all": noninferiority_row(
                arm, reference, "tgc", "all", pinned
            ),
            "tgc_survivors": noninferiority_row(
                arm, reference, "tgc", "survivors", pinned
            ),
            "tgc_handoff_only": noninferiority_row(
                arm, reference, "tgc", HANDOFF_ONLY_POPULATION, pinned
            ),
            "tgc_no_handoff": noninferiority_row(
                arm, reference, "tgc", NO_HANDOFF_POPULATION, pinned
            ),
            "handoff_ease": handoff_reference_ease(arm, reference, pinned),
        }
    out = {
        "reference_arm": reference_label,
        "margin_pp": F1_QUALITY_PP,
        "primary_metric": "goal_pass_rate",
        "secondary_metric": "tgc",
        "rule": NI_RULE,
        "arms": rows,
    }
    if pinned is not None:
        out.update(handoff_keys_record(pinned))
    return out


def chord_residual(
    arm: dict[str, Any],
    floor: dict[str, Any],
    reference: dict[str, Any],
    quality_field: str,
    cost_key: str,
    population: str = "all",
    handoff_keys_arm: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Quality minus the floor-reference chord at this arm's cost fraction.

    Reuses paired_diff (task-clustered). The cost fraction is a plug-in from
    the paired mean costs so this is not a second bootstrap.
    """
    left = dict(arm["cleaned"])
    mid = dict(floor["cleaned"])
    right = dict(reference["cleaned"])
    n_dropped_crash = 0
    n_dropped_handoff = 0
    n_shared = len(set(left) & set(mid) & set(right))
    if population in {"survivors", "survivor"}:
        keys = set(left) & set(mid) & set(right)
        kept: list[tuple[str, int]] = []
        for key in keys:
            if is_crashed(left[key]) or is_crashed(mid[key]) or is_crashed(right[key]):
                n_dropped_crash += 1
                continue
            kept.append(key)
        left = {k: left[k] for k in kept}
        mid = {k: mid[k] for k in kept}
        right = {k: right[k] for k in kept}
        pop_name = "survivors"
        n_shared = len(keys)
    elif population in {"all", "all-episodes"}:
        if quality_field in {"tgc", "goal_pass_rate"}:
            left = coerce_crash_quality(left, quality_field)
            mid = coerce_crash_quality(mid, quality_field)
            right = coerce_crash_quality(right, quality_field)
        pop_name = "all-episodes"
    elif population in HANDOFF_ONLY_ALIASES or population in NO_HANDOFF_ALIASES:
        occurred = population in HANDOFF_ONLY_ALIASES
        keep, n_shared, n_dropped_handoff = _handoff_keep(
            left, [mid, right], occurred, handoff_keys_arm
        )
        left = {k: left[k] for k in keep}
        mid = {k: mid[k] for k in keep}
        right = {k: right[k] for k in keep}
        if quality_field in {"tgc", "goal_pass_rate"}:
            left = coerce_crash_quality(left, quality_field)
            mid = coerce_crash_quality(mid, quality_field)
            right = coerce_crash_quality(right, quality_field)
        pop_name = (
            HANDOFF_ONLY_POPULATION if occurred else NO_HANDOFF_POPULATION
        )
    else:
        raise ValueError(f"unknown population {population!r}")
    keys = sorted(set(left) & set(mid) & set(right))
    costs_arm: list[float] = []
    costs_floor: list[float] = []
    costs_ref: list[float] = []
    usable: list[tuple[str, int]] = []
    missing_cost = 0
    missing_quality = 0
    for key in keys:
        ca = episode_cost(left[key], cost_key)
        cf = episode_cost(mid[key], cost_key)
        cr = episode_cost(right[key], cost_key)
        qa = left[key].get(quality_field)
        qf = mid[key].get(quality_field)
        qr = right[key].get(quality_field)
        if ca is None or cf is None or cr is None:
            missing_cost += 1
            continue
        if qa is None or qf is None or qr is None:
            missing_quality += 1
            continue
        costs_arm.append(float(ca))
        costs_floor.append(float(cf))
        costs_ref.append(float(cr))
        usable.append(key)
    empty = {
        "field": quality_field,
        "population": pop_name,
        "left": arm["label"],
        "floor": floor["label"],
        "reference": reference["label"],
        "cost_key": cost_key,
        "n_pairs": 0,
        "n_pairs_dropped_crash": n_dropped_crash,
        "n_pairs_shared": n_shared,
        "n_pairs_dropped_handoff": n_dropped_handoff,
        "pairs_dropped_missing_cost": missing_cost,
        "pairs_dropped_missing_quality": missing_quality,
        "diff": None,
        "ci95": None,
        "ci95_pp": None,
        "cost_fraction": None,
        "note": "no overlapping triples with recorded quality and cost",
    }
    if not usable:
        return empty
    c_arm = statistics.fmean(costs_arm)
    c_floor = statistics.fmean(costs_floor)
    c_ref = statistics.fmean(costs_ref)
    denom = c_ref - c_floor
    if denom == 0:
        empty["note"] = (
            "floor and reference have identical mean cost; chord fraction undefined"
        )
        empty["cost_arm"] = c_arm
        empty["cost_floor"] = c_floor
        empty["cost_reference"] = c_ref
        return empty
    fraction = (c_arm - c_floor) / denom
    residual_left: dict[tuple[str, int], dict[str, Any]] = {}
    residual_right: dict[tuple[str, int], dict[str, Any]] = {}
    for key in usable:
        qa = float(left[key][quality_field])
        qf = float(mid[key][quality_field])
        qr = float(right[key][quality_field])
        residual = qa - (qf + fraction * (qr - qf))
        residual_left[key] = {"chord_residual": residual}
        residual_right[key] = {"chord_residual": 0.0}
    out = j10.native_from_paired_diff(
        paired_diff(residual_left, residual_right, "chord_residual", resample="task")
    )
    out["field"] = quality_field
    out["population"] = pop_name
    out["left"] = arm["label"]
    out["floor"] = floor["label"]
    out["reference"] = reference["label"]
    out["cost_key"] = cost_key
    out["cost_fraction"] = round(fraction, 6)
    out["cost_arm"] = round(c_arm, 6)
    out["cost_floor"] = round(c_floor, 6)
    out["cost_reference"] = round(c_ref, 6)
    out["n_pairs_dropped_crash"] = n_dropped_crash
    out["n_pairs_shared"] = n_shared
    if pop_name in {HANDOFF_ONLY_POPULATION, NO_HANDOFF_POPULATION}:
        out["n_pairs_dropped_handoff"] = n_dropped_handoff
        defining = _defining_handoff_arm(arm, handoff_keys_arm)
        out["defining_arm"] = defining["label"]
        out["handoff_keys_from"] = defining["label"]
        score_keys = set(usable)
        _attach_side_scores(
            out, arm, reference, quality_field, score_keys, floor=floor
        )
    out["pairs_dropped_missing_cost"] = missing_cost
    out["pairs_dropped_missing_quality"] = missing_quality
    out["positive_means_above_chord"] = (
        None if out.get("diff") is None else bool(float(out["diff"]) > 0)
    )
    return out


def chord_block(
    arms: dict[str, dict[str, Any]],
    reference_label: str | None,
    floor_label: str | None,
    cost_key: str,
    handoff_keys_from: str | None = None,
) -> dict[str, Any] | None:
    pinned = resolve_handoff_keys_arm(arms, handoff_keys_from)
    if not reference_label or not floor_label:
        return None
    missing = [
        name
        for name, label in (
            ("reference", reference_label),
            ("floor", floor_label),
        )
        if label not in arms
    ]
    if missing:
        return {
            "error": f"chord missing named arms: {missing}",
            "reference_arm": reference_label,
            "floor_arm": floor_label,
            "cost_key": cost_key,
        }
    reference = arms[reference_label]
    floor = arms[floor_label]
    if not reference.get("complete_n") or not floor.get("complete_n"):
        return {
            "error": "chord requires complete reference and floor arms",
            "reference_arm": reference_label,
            "floor_arm": floor_label,
            "cost_key": cost_key,
        }
    rows: dict[str, Any] = {}
    for label, arm in arms.items():
        if label in {reference_label, floor_label} or not arm.get("complete_n"):
            continue
        rows[label] = {
            "goal_pass_all": chord_residual(
                arm, floor, reference, "goal_pass_rate", cost_key, "all", pinned
            ),
            "goal_pass_survivors": chord_residual(
                arm, floor, reference, "goal_pass_rate", cost_key, "survivors", pinned
            ),
            "goal_pass_handoff_only": chord_residual(
                arm,
                floor,
                reference,
                "goal_pass_rate",
                cost_key,
                HANDOFF_ONLY_POPULATION,
                pinned,
            ),
            "goal_pass_no_handoff": chord_residual(
                arm,
                floor,
                reference,
                "goal_pass_rate",
                cost_key,
                NO_HANDOFF_POPULATION,
                pinned,
            ),
            "tgc_all": chord_residual(
                arm, floor, reference, "tgc", cost_key, "all", pinned
            ),
            "tgc_survivors": chord_residual(
                arm, floor, reference, "tgc", cost_key, "survivors", pinned
            ),
            "tgc_handoff_only": chord_residual(
                arm,
                floor,
                reference,
                "tgc",
                cost_key,
                HANDOFF_ONLY_POPULATION,
                pinned,
            ),
            "tgc_no_handoff": chord_residual(
                arm,
                floor,
                reference,
                "tgc",
                cost_key,
                NO_HANDOFF_POPULATION,
                pinned,
            ),
            "handoff_ease": handoff_reference_ease(arm, reference, pinned),
        }
    out = {
        "reference_arm": reference_label,
        "floor_arm": floor_label,
        "cost_key": cost_key,
        "arms": rows,
    }
    if pinned is not None:
        out.update(handoff_keys_record(pinned))
    return out


def format_handoff_table(arms: dict[str, dict[str, Any]]) -> str:
    lines = [
        "handoff diagnostics (missing records stay NA; a recorded 0 is kept)"
    ]
    header = (
        f"{'arm':<28} {'n':>5} {'n_crash':>8} {'cost/ep':>12} "
        f"{'cached/ep':>12} {'cache%':>8} "
        f"{'hand_all':>8} {'hand_surv':>9} {'hash_all':>8} {'hash_surv':>9} "
        f"{'m_all':>7} {'m_surv':>7}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for label, arm in arms.items():
        lines.append(
            f"{label:<28} {arm.get('n', 0):>5} {arm.get('n_crashed', 0):>8} "
            f"{_fmt_metric(arm.get('cost_per_episode'), 12)} "
            f"{_fmt_metric(arm.get('cached_input_tokens_per_episode'), 12, 1)} "
            f"{_fmt_metric(arm.get('cached_share_of_inclusive_total'), 8, 3)} "
            f"{_fmt_metric(arm.get('handoff_occurred_rate_all'), 8)} "
            f"{_fmt_metric(arm.get('handoff_occurred_rate_survivors'), 9)} "
            f"{_fmt_metric(arm.get('hash_ok_rate_all'), 8)} "
            f"{_fmt_metric(arm.get('hash_ok_rate_survivors'), 9)} "
            f"{_fmt_metric(arm.get('effective_m_mean_all'), 7, 2)} "
            f"{_fmt_metric(arm.get('effective_m_mean_survivors'), 7, 2)}"
        )
    return "\n".join(lines)


def format_noninferiority_table(block: dict[str, Any] | None) -> str:
    if not block:
        return ""
    if block.get("error"):
        return f"non-inferiority: {block['error']}"
    lines = [
        f"non-inferiority vs {block.get('reference_arm')} "
        f"(margin {block.get('margin_pp')} pp; primary {block.get('primary_metric')})",
        NI_RULE,
    ]
    if block.get("handoff_keys_from"):
        lines.append(
            f"handoff keys pinned to {block['handoff_keys_from']} "
            f"(handoff-only n={block.get('handoff_keys_n')})"
        )
    header = (
        f"{'arm':<24} {'metric':<16} {'pop':<13} {'holds':>6} "
        f"{'n':>5} {'diff_pp':>8} {'ci95_pp':>18} {'def_up':>8} "
        f"{'arm_sc':>8} {'ref_sc':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for label, rows in (block.get("arms") or {}).items():
        for key in NI_POPULATION_KEYS:
            row = rows.get(key) or {}
            ci = row.get("ci95_pp")
            ci_txt = "NA" if not ci else f"[{ci[0]}, {ci[1]}]"
            lines.append(
                f"{label:<24} {row.get('field', key):<16} "
                f"{str(row.get('population') or ''):<13} "
                f"{_fmt_metric(row.get('holds'), 6)} "
                f"{_fmt_metric(row.get('n_pairs'), 5, 0)} "
                f"{_fmt_metric(row.get('diff_pp'), 8, 2)} "
                f"{ci_txt:>18} "
                f"{_fmt_metric(row.get('deficit_ci_upper_pp'), 8, 2)} "
                f"{_fmt_metric(row.get('arm_score'), 8)} "
                f"{_fmt_metric(row.get('reference_score'), 8)}"
            )
        ease = (rows.get("handoff_ease") or {}).get("note")
        if ease:
            lines.append(f"  note: {ease}")
    return "\n".join(lines)


def format_chord_table(block: dict[str, Any] | None) -> str:
    if not block:
        return ""
    if block.get("error"):
        return f"chord: {block['error']}"
    lines = [
        f"chord test vs floor={block.get('floor_arm')} "
        f"reference={block.get('reference_arm')} "
        f"cost_key={block.get('cost_key')} "
        "(positive residual = above the chord)",
    ]
    if block.get("handoff_keys_from"):
        lines.append(
            f"handoff keys pinned to {block['handoff_keys_from']} "
            f"(handoff-only n={block.get('handoff_keys_n')})"
        )
    header = (
        f"{'arm':<24} {'metric':<16} {'pop':<13} {'frac':>8} "
        f"{'n':>5} {'diff_pp':>8} {'ci95_pp':>18} {'above':>6} "
        f"{'arm_sc':>8} {'ref_sc':>8}"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for label, rows in (block.get("arms") or {}).items():
        for key in NI_POPULATION_KEYS:
            row = rows.get(key) or {}
            ci = row.get("ci95_pp")
            ci_txt = "NA" if not ci else f"[{ci[0]}, {ci[1]}]"
            lines.append(
                f"{label:<24} {row.get('field', key):<16} "
                f"{str(row.get('population') or ''):<13} "
                f"{_fmt_metric(row.get('cost_fraction'), 8)} "
                f"{_fmt_metric(row.get('n_pairs'), 5, 0)} "
                f"{_fmt_metric(row.get('diff_pp'), 8, 2)} "
                f"{ci_txt:>18} "
                f"{_fmt_metric(row.get('positive_means_above_chord'), 6)} "
                f"{_fmt_metric(row.get('arm_score'), 8)} "
                f"{_fmt_metric(row.get('reference_score'), 8)}"
            )
    return "\n".join(lines)


def build_report(
    arm_dirs: dict[str, Path],
    seeds: list[int],
    oracle_labels: Path | None,
    *,
    cost_key: str = COST_KEY_DEFAULT,
    reference_arm: str | None = None,
    floor_arm: str | None = None,
    packet_source: Path | None = DEFAULT_SFT_PLAN_PACKET_SOURCE,
    packet_system: str = DEFAULT_SFT_PLAN_PACKET_SYSTEM,
    handoff_keys_from: str | None = None,
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
        arm = summarise_arm(
            label,
            loaded,
            seeds,
            root=arm_dirs[label],
            cost_key=cost_key,
            packet_source=packet_source,
            packet_system=packet_system,
        )
        arm["root"] = arm_dirs[label]
        arms[label] = arm

    pinned = resolve_handoff_keys_arm(arms, handoff_keys_from)
    arm_n = {label: arm["n"] for label, arm in arms.items()}
    refusals = refuse_partial_arms(arm_n)
    if reference_arm and reference_arm not in arms:
        refusals.append(
            f"REFUSE headline: --reference-arm {reference_arm!r} is not among named arms"
        )
    if floor_arm and floor_arm not in arms:
        refusals.append(
            f"REFUSE headline: --floor-arm {floor_arm!r} is not among named arms"
        )
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
    ni = noninferiority_block(complete, reference_arm, handoff_keys_from)
    chord = chord_block(
        complete, reference_arm, floor_arm, cost_key, handoff_keys_from
    )

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
        "cost_key": cost_key,
        "cost_key_note": COST_KEY_NOTES.get(cost_key),
        "known_cost_understatements": [
            costing["understatement"]
            for costing in (
                (arm.get("sft_plan_floor_costing") or {})
                for arm in arms.values()
            )
            if costing.get("understatement")
        ],
        "sft_plan_floor_costing": next(
            (
                arm.get("sft_plan_floor_costing")
                for arm in arms.values()
                if (arm.get("sft_plan_floor_costing") or {}).get("n_sft_plan_rows")
            ),
            None,
        ),
        "reference_arm": reference_arm,
        "floor_arm": floor_arm,
        "noninferiority_margin_pp": F1_QUALITY_PP,
        "noninferiority": ni,
        "chord": chord,
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
            "(task_id, seed) pair if either arm crashed. "
            "handoff-only / no-handoff are additional populations on the "
            "non-inferiority and chord tables: the comparison arm's "
            "handoff_occurred flag selects the (task_id, seed) keys, then "
            "every arm in the contrast is restricted to those same keys "
            "(all-episodes scoring: crash = 0)."
        ),
    }
    if pinned is not None:
        report.update(handoff_keys_record(pinned))
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
    if args.handoff_keys_from and args.handoff_keys_from not in arm_dirs:
        valid = ", ".join(sorted(arm_dirs))
        reason = (
            f"--handoff-keys-from {args.handoff_keys_from!r} is not among "
            f"named arms ({valid})"
        )
        print(json.dumps({"refused": True, "reason": reason}))
        return 2
    try:
        seeds = parse_seeds(args.seeds)
    except ValueError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}))
        return 2
    report, code = build_report(
        arm_dirs,
        seeds,
        args.oracle_labels,
        cost_key=args.cost_key,
        reference_arm=args.reference_arm,
        floor_arm=args.floor_arm,
        packet_source=args.packet_source,
        packet_system=args.packet_system,
        handoff_keys_from=args.handoff_keys_from,
    )
    if report.get("refused") and "arms" not in report:
        print(report.get("reason") or "refused")
        text = json.dumps(report, indent=2, default=str) + "\n"
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        return code
    table = format_table(report["arms"], report.get("refusals") or [])
    print(report.get("oracle_semantics") or "")
    print(table)
    print()
    print(format_handoff_table(report["arms"]))
    if report.get("cost_key_note"):
        print(report["cost_key_note"])
    sft_costing = report.get("sft_plan_floor_costing") or {}
    if sft_costing.get("applied"):
        print(
            "sft_plan floor route=source_plan_event "
            f"mean_noncached_plan_tokens={sft_costing.get('mean_noncached_plan_tokens')} "
            f"n={sft_costing.get('n_mapped')}"
        )
    for item in report.get("known_cost_understatements") or []:
        print(
            "known_cost_understatement "
            f"arm={item.get('arm')} reason={item.get('reason')} "
            f"estimated_mean={item.get('estimated_mean_noncached_plan_tokens')}"
        )
    ni_table = format_noninferiority_table(report.get("noninferiority"))
    if ni_table:
        print()
        print(ni_table)
    chord_table = format_chord_table(report.get("chord"))
    if chord_table:
        print()
        print(chord_table)
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
