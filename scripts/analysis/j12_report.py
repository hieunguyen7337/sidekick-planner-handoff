#!/usr/bin/env python
"""J12: the prefix-depth test on test_normal, analysed as docs/prereg_j12_depth_test_20260924.md registers it.

Four predictions on goal_pass, one Holm family of m = 4, J12's own, all predicted > 0: the lower
bound of the scenario-clustered 95 % interval above 0 and the Holm-adjusted p <= 0.05 (J12 §3-§4).

  D1  J10 prefix_m11    − J12 prefix_m6     all pairs
  D2  J10 prefix_zs_m11 − J12 prefix_zs_m6  all pairs
  D3  as D1, handoff-only: Σ d·h / Σ h, h = the m = 11 episode's handoff_occurred
  D4  as D2, handoff-only

Reuse, not re-implementation
----------------------------
Every statistical piece is scripts/analysis/j10_report.py's, imported: the loaders and the crash rule
(load_arm_tree, a1_arm_episodes), the paired contrast with its scenario-clustered primary and
task-clustered secondary intervals, POOL-04 and the registered sign-flip sensitivity
(a1_evaluate_contrast_prediction), the cluster ratio bootstrap (a1_ratio_bootstrap), the bootstrap p
(bootstrap_pvalue), Holm (a1_decide_family), the handoff flags and the handoff-depth helper
(a1_handoff_flags, a1_handoff_depth, am1_handoff_comps), POOL-04 for a ratio bound (am1_ni_reading at
a margin of 0), the decomposition (am1_decomposition), the silenced counts (a1_no_handoff_counts),
the limit rates (am1_limit_rates), the planless keys and their verdict rule (a1_planless_keys,
a1_apply_key_exclusion) and the protocol guard (a1_protocol_guard). 10,000 draws, seed 20260924.

The handoff-only estimand mirrors scripts/analysis/j17_depth_fixes.py:329-350 (paired_components):
d = m11 − m6 per (task_id, seed), h from the m11 arm, a missing flag counted as h = 0, whole clusters
resampled. j17 is not imported: it refuses held-out paths by design.

Two pieces have no j10_report helper and are written here: A1 Amendment 1 §I's live-ask count and
bound (j12_live_asks), and A1 §4.2's key-exclusion re-read for a family that mixes a ratio estimand
with paired contrasts (j12_key_exclusion_sensitivity mirrors a1_key_exclusion_sensitivity, which
would read D3 / D4 as plain paired contrasts).

Conventions: pairs are (task_id, seed); error_type == "crash" is dropped and counted, every other
error is a scored outcome; a contrast whose arms lack the registered non-crashed pairs (336 on
test_normal) is incomplete and draws no reading.

Interface:
  python scripts/analysis/j12_report.py --split test_normal --confirm-heldout-test-split \\
      --arm prefix_m6=DIR --arm prefix_zs_m6=DIR --arm prefix_m11=DIR --arm prefix_zs_m11=DIR \\
      [--arm planner_alone_cap81=DIR] [--out campaign/results/j12_depth_test_normal.report.json]
  --plumbing-check is accepted only on dev, and only over *_dryrun campaigns; test_challenge is
  always refused.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import j10_report as j10  # noqa: E402
from scripts.analysis import j16_robustness as j16  # noqa: E402

J12_PREREG = "docs/prereg_j12_depth_test_20260924.md"
J12_DEV_REPORT = "campaign/results/j17_depth_fixes_20260924.report.json"
J12_DEFAULT_OUT = "campaign/results/j12_depth_test_normal.report.json"
A1_AM1_I = "docs/prereg_j10_amendment_20260924.md Amendment 1 §I"

# The four contrast arms. The m = 6 arms are J12's; the m = 11 arms are J10 arms 5 and 7, read here.
J12_ARMS: dict[str, str] = {
    "prefix_m6": "configs/j12_prefix_m6.yaml",
    "prefix_zs_m6": "configs/j12_prefix_zs_m6.yaml",
    "prefix_m11": "configs/j10_prefix_m11.yaml",
    "prefix_zs_m11": "configs/j10_prefix_zs_m11.yaml",
}
# Optional: J10 arm 3, read only for A1 §4.2's planless keys (J12 §3). Never a contrast arm.
J12_PLAN_SOURCE_ARM = j10.A1_PLAN_SOURCE_ARM
J12_PREFIX_M = {"prefix_m6": 6, "prefix_zs_m6": 6, "prefix_m11": 11, "prefix_zs_m11": 11}
J12_RECEIVERS = {"bplus": ("prefix_m11", "prefix_m6"), "zs": ("prefix_zs_m11", "prefix_zs_m6")}
J12_RULE = "lower_bound_above_threshold"  # A1_RULES: supported iff CI lo > t; p in the "greater" direction
J12_BOUND_FLAG_PP = 1.00  # A1 Amendment 1 §I: a bound reaching 1.00 pp is printed with the verdict
# A registered J10 / J12 test campaign id; its dev dry-run twin ends in _dryrun and does not match.
REGISTERED_TEST_ID = re.compile(r"^j1[02]_[A-Za-z0-9_]+_20260924$")


def _dev(key: str, diff_pp: float, ci: list[float], n_pairs: int, n_handoff: Optional[int] = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"diff_pp": diff_pp, "ci95_pp_scenario": ci, "n_pairs": n_pairs}
    if n_handoff is not None:
        ref["n_handoff"] = n_handoff
    return ref | {"source": J12_DEV_REPORT, "key": key, "bootstrap_seed": j10.A1_BOOTSTRAP_SEED,
                  "population": "pooled cap-81 dev family, seeds 1-3 (hj17 + hj18)"}


# J12 §4, as data. dev_reference is j17's value rounded to 2 dp (tests/unit/test_j12_report.py
# checks it against the JSON).
J12_PREDICTIONS: list[dict[str, Any]] = [
    {"id": "D1", "kind": "paired_contrast", "receiver": "bplus", "population": "all", "metric": "goal_pass",
     "left": "prefix_m11", "right": "prefix_m6", "rule": J12_RULE, "threshold_pp": 0.0, "holm_family": True,
     "statement": "J10 prefix_m11 − J12 prefix_m6 on goal_pass, all pairs, is > 0 (scenario CI lower bound above 0 after Holm)",
     "citation": f"{J12_PREREG} §4",
     "dev_reference": _dev("handoff_only_contrasts.bplus.m6_to_m11.goal_pass.all", 8.39, [4.20, 12.63], 171)},
    {"id": "D2", "kind": "paired_contrast", "receiver": "zs", "population": "all", "metric": "goal_pass",
     "left": "prefix_zs_m11", "right": "prefix_zs_m6", "rule": J12_RULE, "threshold_pp": 0.0, "holm_family": True,
     "statement": "J10 prefix_zs_m11 − J12 prefix_zs_m6 on goal_pass, all pairs, is > 0",
     "citation": f"{J12_PREREG} §4",
     "dev_reference": _dev("handoff_only_contrasts.zs.m6_to_m11.goal_pass.all", 7.70, [3.69, 12.06], 171)},
    {"id": "D3", "kind": "handoff_only", "receiver": "bplus", "population": "handoff_only", "metric": "goal_pass",
     "left": "prefix_m11", "right": "prefix_m6", "flags_from": "prefix_m11", "rule": J12_RULE,
     "threshold_pp": 0.0, "holm_family": True,
     "statement": "as D1 on handoff episodes: Σ d·h / Σ h > 0, h from the prefix_m11 episode",
     "citation": f"{J12_PREREG} §3-§4",
     "dev_reference": _dev("handoff_only_contrasts.bplus.m6_to_m11.goal_pass.handoff_only", 12.03,
                           [5.49, 18.57], 171, n_handoff=71)},
    {"id": "D4", "kind": "handoff_only", "receiver": "zs", "population": "handoff_only", "metric": "goal_pass",
     "left": "prefix_zs_m11", "right": "prefix_zs_m6", "flags_from": "prefix_zs_m11", "rule": J12_RULE,
     "threshold_pp": 0.0, "holm_family": True,
     "statement": "as D2 on handoff episodes: Σ d·h / Σ h > 0, h from the prefix_zs_m11 episode",
     "citation": f"{J12_PREREG} §3-§4",
     "dev_reference": _dev("handoff_only_contrasts.zs.m6_to_m11.goal_pass.handoff_only", 13.93,
                           [5.12, 21.22], 171, n_handoff=71)},
]
# J12 §4 "Readings, fixed now": per receiver, (all-episode id, handoff-only id).
J12_READING_PAIRS = {"bplus": ("D1", "D3"), "zs": ("D2", "D4")}
J12_RECEIVER_WORD = {"bplus": "tailored", "zs": "untailored"}
J12_READINGS = {
    "all_and_handoff": ("on held-out tasks, a later handoff raises the {receiver} executor's quality, and not "
                        "only through episodes the planner finishes itself"),
    "all_not_handoff": ("the held-out depth gain is not shown on real handoffs; it may rest on the planner "
                        "finishing"),
    "all_not": "the dev depth span does not replicate on held-out tasks for the {receiver} executor",
}


# ---- one prediction ------------------------------------------------------------------------------
def j12_evaluate_handoff_only(
    pred: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
    stability: bool = True,
) -> dict[str, Any]:
    """D3 / D4: Σ d·h / Σ h with d = left − right per (task_id, seed) and h the `flags_from` (m11)
    episode's handoff_occurred, whole clusters resampled. Returns the keys
    a1_evaluate_contrast_prediction returns, so a1_decide_family decides it unchanged.

    The interval and the p come from one set of scenario resamples (keep_samples); a resample with
    Σ h = 0 is undefined, left out and counted. stability=False skips POOL-04, the sign-flip and the
    TGC companion, as a1_evaluate_contrast_prediction does for the key-exclusion re-read."""
    rule = j10.A1_RULES[pred["rule"]]
    out: dict[str, Any] = dict(pred)
    out["rule_text"] = rule["text"]
    out["direction"] = rule["direction"]
    missing = [a for a in (pred["left"], pred["right"]) if a not in arms]
    if missing:
        out.update(decidable=False, verdict="arm_absent", reason=f"no --arm for {missing}")
        return out
    left, right = arms[pred["left"]]["episodes"], arms[pred["right"]]["episodes"]
    flags = handoff_flags.get(pred["flags_from"], {})
    field = j10.A1_METRIC_FIELDS[pred["metric"]]
    t = float(pred["threshold_pp"]) / 100.0
    comps, n_missing_field, n_flag_missing = j10.am1_handoff_comps(left, right, flags, field)
    units = ("scenario", "task")
    boot = j10.a1_ratio_bootstrap(comps, {"handoff_only": (0, 1)}, units, n_boot=n_boot, seed=seed,
                                  keep_samples=True)
    contrast: dict[str, Any] = {
        "field": field,
        "estimand": f"Σ d·h / Σ h, d = {pred['left']} − {pred['right']}, h = {pred['flags_from']}'s handoff_occurred",
        "n_shared": len(set(left) & set(right)),
        "n_pairs": len(comps),
        "n_handoff": int(sum(c[1] for c in comps.values())),
        "n_silenced": int(sum(c[3] for c in comps.values())),
        "n_flag_missing": n_flag_missing,
        "n_dropped_missing_field": n_missing_field,
        "status": boot["status"],
    }
    out["contrast"] = contrast
    if boot["status"] != "ok":
        out.update(decidable=False, verdict="refused_bootstrap", reason=boot.get("error"))
        return out
    st = boot["handoff_only"]
    for unit in units:
        ci = st.get(f"ci95_{unit}")
        contrast[unit] = {
            "clustering": unit,
            "n_clusters": boot[f"n_clusters_{unit}"],
            "diff_pp": None if st["point"] is None else round(st["point"] * 100, 2),
            "ci95_pp": None if ci is None else [round(ci[0] * 100, 2), round(ci[1] * 100, 2)],
            "n_resamples_undefined": st.get(f"n_undefined_{unit}"),
            "n_boot": n_boot,
            "seed": seed,
        }
    samples = st.get("_samples_scenario") or []
    ci = st.get("ci95_scenario")
    if st["point"] is None or ci is None or not samples:
        out.update(decidable=False, verdict="refused_no_pairs", reason="no handoff pairs")
        return out
    lo, hi = float(ci[0]), float(ci[1])
    lo_above, hi_below = j10._events(lo, hi, t)
    out["events_unadjusted"] = {"lo_above_threshold": lo_above, "hi_below_threshold": hi_below}
    out["verdict_unadjusted"] = rule["decide"](st["point"], lo_above, hi_below)
    out["p_value"] = j10.bootstrap_pvalue(samples, t, rule["direction"])
    out["p_value_two_sided"] = j10.bootstrap_pvalue(samples, t, "two-sided")
    if stability:
        # TGC beside it, through the handoff-depth helper (handoff-only and all-episode).
        out["tgc_secondary"] = j10.a1_handoff_depth(left, right, flags, j10.A1_METRIC_FIELDS["tgc"],
                                                    n_boot=n_boot, seed=seed)
        # POOL-04 for a ratio lower bound: am1_ni_reading reads "holds" iff lo > margin, which is
        # this rule's "supported"; with margin 0 it is a1_pool04 for the handoff-only estimand.
        out["pool04"] = {"rule": "POOL-04", "via": "j10_report.am1_ni_reading, margin = threshold"} | \
            j10.am1_ni_reading(comps, lo, margin_pp=float(pred["threshold_pp"]), n_boot=n_boot, seed=seed)
        # Sign-flip over the handoff pairs' d: its statistic is then Σ d·h / Σ h (j17 contrast_object).
        keys = [k for k, c in sorted(comps.items()) if c[1] > 0]
        out["permutation_sensitivity"] = j10.a1_permutation(
            {"keys": keys, "diffs": [comps[k][0] for k in keys]}, t, pred.get("permutation_alternative", "two-sided"))
    out["_point"], out["_lo"], out["_hi"] = st["point"], lo, hi
    incomplete = [a for a in (pred["left"], pred["right"]) if not arms[a]["complete"]]
    if incomplete:
        out.update(decidable=False, verdict="refused_incomplete",
                   reason=f"arm(s) below the registered non-crashed matrix: {incomplete}")
        return out
    out["decidable"] = True
    return out


def j12_evaluate(
    pred: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
    stability: bool = True,
) -> dict[str, Any]:
    if pred["kind"] == "handoff_only":
        return j12_evaluate_handoff_only(pred, arms, handoff_flags, n_boot=n_boot, seed=seed, stability=stability)
    return j10.a1_evaluate_contrast_prediction(pred, arms, n_boot=n_boot, seed=seed, stability=stability)


def j12_apply_pair_rule(r: dict[str, Any], arms: dict[str, dict[str, Any]], expected_pairs: int) -> None:
    """J12 §3 / A1 §9: a contrast whose arms lack `expected_pairs` non-crashed pairs is incomplete."""
    if r["left"] not in arms or r["right"] not in arms:
        return
    shared = len(set(arms[r["left"]]["episodes"]) & set(arms[r["right"]]["episodes"]))
    r["n_noncrashed_pairs"] = shared
    r["expected_pairs"] = expected_pairs
    if shared < expected_pairs and r.get("decidable"):
        r.update(decidable=False, verdict="refused_incomplete",
                 reason=f"{shared} non-crashed pairs, below the registered {expected_pairs}")


def j12_decide_family(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Holm over D1-D4 through a1_decide_family, then the unadjusted reversal flag (J12 §4: an upper
    bound below 0 is reported as a primary finding; the "greater" p cannot reject for it)."""
    multiplicity = j10.a1_decide_family(results)
    for r in results:
        ev = r.get("events_unadjusted") or {}
        r["reversal_unadjusted"] = bool(ev.get("hi_below_threshold")) if ev else None
    return multiplicity | {"family_id": "J12", "citation": f"{J12_PREREG} §3"}


# ---- A1 §4.2: the key-exclusion sensitivity -------------------------------------------------------
def j12_key_exclusion_sensitivity(
    results: list[dict[str, Any]],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    keys: list[tuple[str, int]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """A1 §4.2 item 4 for J12: D1-D4 re-read with the planless keys dropped from every arm, same
    bootstrap, same Holm family of 4, same rule; POOL-04 and the sign-flip not re-run. The shape of
    j10_report.a1_key_exclusion_sensitivity, with D3 / D4 read through their own estimand."""
    excluded = set(keys)
    arms_x = {label: dict(arm, episodes={k: v for k, v in arm["episodes"].items() if k not in excluded})
              for label, arm in arms.items()}
    sens = [j12_evaluate(dict(p), arms_x, handoff_flags, n_boot=n_boot, seed=seed, stability=False)
            for p in J12_PREDICTIONS]
    j10.a1_decide_family(sens)
    by_id = {r["id"]: r for r in results}
    rows, differs = [], []
    for s in sens:
        r = by_id.get(s["id"], {})
        differ = bool(r.get("decidable") and s.get("decidable") and r.get("verdict_holm") != s.get("verdict_holm"))
        if differ:
            differs.append(s["id"])
        rows.append({"id": s["id"], "verdict_holm_all_pairs": r.get("verdict_holm"),
                     "verdict_holm_without_keys": s.get("verdict_holm"), "differs": differ,
                     "contrast_without_keys": s.get("contrast")})
    return {"rows": rows, "differs": differs}


# ---- A1 Amendment 1 §I: live answers to executor asks --------------------------------------------
def _is_live_answer(ev: dict[str, Any]) -> bool:
    usage = ev.get("usage")
    return ev.get("event_type") == "intervention" and isinstance(usage, dict) and usage.get("provider") == "codex"


def j12_live_asks(root: Path, arm: dict[str, Any]) -> dict[str, Any]:
    """§I for one arm, over its scored episodes: episodes whose executor ask was answered live and
    the most that help could move the arm mean, that count / the registered pairs (336), in pp.

    A live answer is a planner `intervention` event with usage.provider == "codex" in the attempt
    that wrote result.json -- ledger PROV-02's definition. result.json's totals.planner_calls_total
    (the ledger count campaign_summarize --gate reads) is tallied beside it, and the episodes where
    the two disagree on "any live call" are counted, not assumed away."""
    scored = arm["episodes"]
    calls: dict[tuple[str, int], int] = {}
    ledger: dict[tuple[str, int], int] = {}
    if root.exists():
        for path in sorted(root.rglob("result.json")):
            row, _err = j10._read_result(path)
            if row is None or row.get("task_id") is None or row.get("seed") is None:
                continue
            key = (str(row["task_id"]), int(row["seed"]))
            if key not in scored or key in calls:
                continue
            calls[key] = sum(1 for ev in j16.events_last_attempt(path.parent / "events.jsonl") if _is_live_answer(ev))
            totals = row.get("totals") if isinstance(row.get("totals"), dict) else {}
            ledger[key] = int(totals.get("planner_calls_total") or 0)
    affected = sorted(k for k, n in calls.items() if n > 0)
    denom = arm["n_expected"]
    bound = 100.0 * len(affected) / denom if denom else None
    return {
        "n_scored": len(scored),
        "n_episodes_live_answer": len(affected),
        "n_live_answer_calls": sum(calls.values()),
        "n_ledger_live_planner_calls": sum(ledger.values()),
        "n_episodes_events_and_ledger_disagree": sum(1 for k in calls if (calls[k] > 0) != (ledger.get(k, 0) > 0)),
        "bound_pp": None if bound is None else round(bound, 2),
        "bound_denominator": denom,
        "reaches_1pp": None if bound is None else bool(bound >= J12_BOUND_FLAG_PP - 1e-12),
        "episodes": [f"{s}/{t}" for t, s in affected],
        "definition": ("planner intervention events with usage.provider == 'codex' in the last attempt "
                       "(ledger PROV-02); bound = episodes with a live answer / registered pairs"),
        "citation": A1_AM1_I,
    }


def j12_bound_rows(results: list[dict[str, Any]], live: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """§I beside each D: both arms' counts and bounds, and the sentence a bound >= 1.00 pp requires."""
    out = {}
    for r in results:
        per = {a: {"n_episodes_live_answer": live[a]["n_episodes_live_answer"], "bound_pp": live[a]["bound_pp"]}
               for a in (r["left"], r["right"]) if a in live}
        reach = [a for a, v in per.items() if v["bound_pp"] is not None and v["bound_pp"] >= J12_BOUND_FLAG_PP - 1e-12]
        sentence = None
        if reach:
            sentence = (f"{r['id']} {r.get('verdict')}; " + "; ".join(
                f"{a}: {per[a]['n_episodes_live_answer']} episode(s) got a live answer to an executor ask, "
                f"bounding its mean at {per[a]['bound_pp']:.2f} pp" for a in reach)
                + f" ({A1_AM1_I}; no verdict changes).")
        out[r["id"]] = {"arms": per, "any_bound_reaches_1pp": bool(reach), "sentence": sentence}
    return out


# ---- readings ----------------------------------------------------------------------------------
def j12_readings(results: list[dict[str, Any]]) -> dict[str, Any]:
    """J12 §4's fixed readings, per receiver, from the final verdicts."""
    by_id = {r["id"]: r for r in results}
    out = {}
    for receiver, (all_id, ho_id) in J12_READING_PAIRS.items():
        va, vh = by_id[all_id].get("verdict"), by_id[ho_id].get("verdict")
        word = J12_RECEIVER_WORD[receiver]
        if va == "supported" and vh == "supported":
            key = "all_and_handoff"
        elif va == "supported" and vh == "not_supported":
            key = "all_not_handoff"
        elif va == "not_supported":
            key = "all_not"
        else:
            key = None
        reversals = [i for i in (all_id, ho_id) if by_id[i].get("reversal_unadjusted")]
        out[receiver] = {
            "ids": [all_id, ho_id],
            "verdicts": {all_id: va, ho_id: vh},
            "reading_key": key,
            "reading": None if key is None else J12_READINGS[key].format(receiver=word),
            "no_reading_reason": None if key is not None else f"no fixed reading for {all_id}={va}, {ho_id}={vh}",
            "not_supported_is_reported_as": "not replicated, never as evidence of no effect",
            "reversals_unadjusted": reversals,
        }
    return out


# ---- protocol ------------------------------------------------------------------------------------
def j12_protocol_guard(
    split: str,
    confirm: bool,
    plumbing: bool,
    arm_dirs: dict[str, Path],
    out_path: Optional[Path],
    registered_settings: bool,
) -> Optional[str]:
    """A1's guard (test_normal needs the flag; no plumbing on test; held-out markers; no --out under
    the raw results; registered bootstrap on test), plus J12's: test_challenge is never read; a
    registered J10 / J12 test campaign id is read only on test_normal and a *_dryrun one never
    there; --plumbing-check reads only *_dryrun campaigns on dev."""
    if split == "test_challenge":
        return f"refusing test_challenge: J12 never reads it [{J12_PREREG} §7]"
    proto = j10.a1_protocol_guard(split, confirm, plumbing, arm_dirs.values(), out_path, registered_settings)
    if proto:
        return proto
    if plumbing and split != "dev":
        return "refusing --plumbing-check off dev: it is a dry-run check over *_dryrun campaigns"
    for label, directory in sorted(arm_dirs.items()):
        parts = Path(directory).parts
        dry = [p for p in parts if p.endswith("_dryrun")]
        registered = [p for p in parts if REGISTERED_TEST_ID.match(p)]
        if split == "test_normal" and dry:
            return f"refusing {label}={directory}: a *_dryrun campaign is dev data, never the J12 test read"
        if split != "test_normal" and registered:
            return (f"refusing {label}={directory}: {registered[0]} is a registered J10/J12 test campaign; "
                    f"on {split} only its *_dryrun twin may be read")
        if plumbing and not dry:
            return f"refusing --plumbing-check over {label}={directory}: plumbing checks read only *_dryrun campaigns"
    return None


# ---- report ------------------------------------------------------------------------------------
def build_report_j12(
    *,
    split: str,
    seeds: list[int],
    arm_dirs: dict[str, Path],
    expected_n_tasks: int,
    confirm_heldout_test_split: bool = False,
    plumbing_check: bool = False,
    n_boot: int = j10.A1_BOOTSTRAP_N,
    bootstrap_seed: int = j10.A1_BOOTSTRAP_SEED,
    out_path: Optional[Path] = None,
) -> tuple[dict[str, Any], int]:
    registered = n_boot == j10.A1_BOOTSTRAP_N and bootstrap_seed == j10.A1_BOOTSTRAP_SEED
    proto = j12_protocol_guard(split, confirm_heldout_test_split, plumbing_check, arm_dirs, out_path, registered)
    if proto:
        return ({"protocol": "J12", "label": "REFUSED", "refused": True, "reason": proto,
                 "headline": proto, "split": split}, 2)

    contrast_dirs = {a: p for a, p in arm_dirs.items() if a in J12_ARMS}
    loaded = {label: j10.load_arm_tree(path) for label, path in contrast_dirs.items()}
    tasks = j10.discover_tasks(loaded, seeds)
    expected_pairs = expected_n_tasks * len(seeds)
    reasons: list[str] = []
    if len(tasks) != expected_n_tasks:
        reasons.append(f"task_count_is_{len(tasks)}_expected_{expected_n_tasks}")
    absent = sorted(set(J12_ARMS) - set(contrast_dirs))
    if absent:
        reasons.append(f"arm_absent:{absent}")
    arms = {label: j10.a1_arm_episodes(label, blob, tasks, seeds) for label, blob in loaded.items()}
    provenance = {label: j10.a1_split_provenance(path) for label, path in contrast_dirs.items()}
    split_problems = []
    for label, counts in provenance.items():
        wrong = {k: v for k, v in counts.items() if k not in {split, "unrecorded"}}
        if wrong:
            split_problems.append(f"{label}:{wrong}")
        if split != "dev" and counts.get("unrecorded"):
            split_problems.append(f"{label}:unrecorded={counts['unrecorded']}")
    if split_problems:
        reasons.append("split_provenance_mismatch:" + ";".join(split_problems))
    for label, arm in arms.items():
        if len(arm["systems_in_tree"]) > 1:
            reasons.append(f"mixed_systems:{label}={arm['systems_in_tree']}")
        if not arm["complete"]:
            reasons.append(f"incomplete_arm:{label} scored={arm['n_scored']}/{arm['n_expected']} "
                           f"crash={arm['n_crash']} missing={arm['n_missing']}")
    if bool(split_problems) or len(tasks) != expected_n_tasks or any(r.startswith("mixed_systems") for r in reasons):
        for arm in arms.values():
            arm["complete"] = False

    handoff_flags = {a: j10.a1_handoff_flags(contrast_dirs[a]) for a in sorted(contrast_dirs)}
    results = [j12_evaluate(dict(p), arms, handoff_flags, n_boot=n_boot, seed=bootstrap_seed)
               for p in J12_PREDICTIONS]
    for r in results:
        j12_apply_pair_rule(r, arms, expected_pairs)
    multiplicity = j12_decide_family(results)

    # A1 §4.2 (J12 §3): the primary keeps every pair; a verdict that changes without arm 3's
    # planless keys is on the boundary. The cap is A1's 5 % of the matrix.
    planless = j10.a1_planless_keys(arm_dirs, seeds)
    planless_cap = int(expected_pairs * j10.A1_PLANLESS_CAP_FRACTION)
    contingency: dict[str, Any] = {
        "rule": "A1 §4.2 (J12 §3)", "source_arm": J12_PLAN_SOURCE_ARM, "cap": planless_cap,
        "keys": None if planless is None else [f"{s}/{t}" for t, s in planless],
        "n_keys": None if planless is None else len(planless), "sensitivity": None,
    }
    if planless is None:
        contingency["note"] = f"{J12_PLAN_SOURCE_ARM} not given; the planless keys cannot be listed"
    elif planless:
        if len(planless) > planless_cap:
            reasons.append(f"planless_keys_above_cap:{len(planless)}>{planless_cap}")
        contingency["sensitivity"] = j12_key_exclusion_sensitivity(
            results, arms, handoff_flags, planless, n_boot=n_boot, seed=bootstrap_seed)
        j10.a1_apply_key_exclusion(results, contingency["sensitivity"]["differs"])
    for r in results:
        for key in [k for k in r if k.startswith("_")]:
            r.pop(key)

    live = {a: j12_live_asks(contrast_dirs[a], arms[a]) for a in sorted(arms)}
    bounds = j12_bound_rows(results, live)
    for r in results:
        r["live_ask_bound"] = bounds[r["id"]]
    readings = j12_readings(results)
    decomposition = {}
    for receiver, (target, base) in J12_RECEIVERS.items():
        if target not in arms or base not in arms:
            decomposition[receiver] = {"target": target, "base": base, "status": "arm_absent"}
            continue
        decomposition[receiver] = {"target": target, "base": base} | {
            metric: j10.am1_decomposition(arms[target]["episodes"], arms[base]["episodes"],
                                          handoff_flags.get(target, {}), j10.A1_METRIC_FIELDS[metric],
                                          n_boot=n_boot, seed=bootstrap_seed)
            for metric in ("goal_pass", "tgc")}
    silenced = {a: j10.a1_no_handoff_counts(arms[a], handoff_flags.get(a, {}), J12_PREFIX_M.get(a))
                | {"citation": f"{J12_PREREG} §4 (silenced count: episodes with no handoff)"}
                for a in sorted(arms)}

    decided = [r for r in results if r.get("decidable")]
    all_decided = len(decided) == len(results)
    label = ("PLUMBING CHECK, NOT A RESULT" if plumbing_check
             else "J12 DRY RUN ON DEV, NOT THE J12 RESULT" if split == "dev"
             else "J12 registered analysis")
    if not registered:
        label += " (NON-REGISTERED bootstrap settings)"
    headline = ("COMPLETE: D1-D4 decided." if all_decided and not reasons
                else "INCOMPLETE: " + "; ".join(reasons or ["some predictions not decidable"]) + ".")
    headline += " Verdicts: " + ", ".join(f"{r['id']} {r.get('verdict')}" for r in results) + "."
    sentences = [b["sentence"] for b in bounds.values() if b["sentence"]]
    if sentences:
        headline += " " + " ".join(sentences)
    report: dict[str, Any] = {
        "protocol": "J12",
        "prereg": J12_PREREG,
        "generated_by": "scripts/analysis/j12_report.py",
        "label": label,
        "headline": headline,
        "not_the_j12_result": plumbing_check or not registered or split != "test_normal",
        "split": split,
        "seeds": seeds,
        "expected_n_tasks": expected_n_tasks,
        "n_tasks_observed_union": len(tasks),
        "expected_pairs_per_contrast": expected_pairs,
        "incomplete_reasons": reasons,
        "arm_dirs": {a: str(p) for a, p in sorted(arm_dirs.items())},
        "bootstrap": {
            "n": n_boot, "seed": bootstrap_seed, "registered": registered,
            "primary_clustering": "scenario", "secondary_clustering": "task",
            "interval": "95% percentile; lo = means[int(0.025 B)], hi = means[int(0.975 B)]",
            "paired_on": "(task_id, seed)",
            "p": "j10_report.bootstrap_pvalue, direction 'greater' at 0 (J12 §3)",
        },
        "stability_rule": {"id": "POOL-04", "window_pp": j10.POOL04_WINDOW_PP, "seeds": list(j10.POOL04_SEEDS),
                           "reported_bound": {"n_boot": j10.POOL04_BIG_N, "seed": j10.POOL04_BIG_SEED}},
        "permutation_rule": {"id": "A1 §5.5", "decision_bearing": False, "clusters": "scenario",
                             "alternative": "two-sided", "handoff_only": "over the handoff pairs' d"},
        "multiplicity": multiplicity,
        "planless_contingency": contingency,
        "arms": {a: {k: v for k, v in arm.items() if k != "episodes"}
                 | {"split_provenance": provenance[a], "config": J12_ARMS[a], "m": J12_PREFIX_M[a]}
                 for a, arm in sorted(arms.items())},
        "predictions": results,
        "verdicts": {r["id"]: r.get("verdict") for r in results},
        "readings": readings,
        # Reported beside the family, not decision-bearing (J12 §4).
        "beside": {
            "decision_bearing": False,
            "tgc": {r["id"]: r.get("tgc_secondary") for r in results},
            "silenced_counts": silenced,
            "decomposition": decomposition,
            "limit_rates": j10.am1_limit_rates(arms),
            "sign_flip_p": {r["id"]: (r.get("permutation_sensitivity") or {}).get("p_value") for r in results},
            "live_asks": live,
        },
        "crash_convention": ("error_type == 'crash' is not an outcome (dropped, counted, arm incomplete); "
                             "limit / timeout / parse_error / api_error are scored outcomes."),
    }
    report = j10._strip_internal(report)
    return report, (0 if all_decided and not reasons else 1)


def _fmt(value: Any) -> str:
    return "—" if value is None else str(value)


def render_markdown(report: dict[str, Any], json_name: str) -> str:
    """The .md beside the JSON. Every number is copied from the report dict; none is typed."""
    lines = [f"# J12 prefix-depth test — {report['label']}", "",
             f"Generated by `scripts/analysis/j12_report.py` beside `{json_name}`; every number here is a key "
             f"of that JSON. Prereg: `{report['prereg']}`.", "", report["headline"], "",
             "| id | contrast | population | diff (pp) | 95% CI scenario | 95% CI task | p (greater) | Holm p | verdict |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in report["predictions"]:
        c = r.get("contrast") or {}
        scen, task = c.get("scenario") or {}, c.get("task") or {}
        lines.append(
            f"| {r['id']} | {r['left']} − {r['right']} | {r['population']} | {_fmt(scen.get('diff_pp'))} | "
            f"{_fmt(scen.get('ci95_pp'))} | {_fmt(task.get('ci95_pp'))} | {_fmt(r.get('p_value'))} | "
            f"{_fmt((r.get('holm') or {}).get('p_adjusted'))} | {r.get('verdict')} |")
    lines += ["", "## Readings (J12 §4)", ""]
    for receiver, rd in report["readings"].items():
        lines.append(f"- {receiver}: {rd['reading'] or rd['no_reading_reason']}"
                     + (f" Reversal (unadjusted) in {rd['reversals_unadjusted']}: reported as a primary finding."
                        if rd["reversals_unadjusted"] else ""))
    lines += ["", "## Live executor asks (A1 Amendment 1 §I)", ""]
    for arm, v in report["beside"]["live_asks"].items():
        lines.append(f"- {arm}: {v['n_episodes_live_answer']} episode(s), {v['n_live_answer_calls']} call(s); "
                     f"bound {_fmt(v['bound_pp'])} pp of {v['bound_denominator']}")
    for r in report["predictions"]:
        if (r.get("live_ask_bound") or {}).get("sentence"):
            lines.append(f"- {r['live_ask_bound']['sentence']}")
    lines += ["", "## Beside the family (not decision-bearing)", ""]
    for arm, v in report["beside"]["limit_rates"].items():
        lines.append(f"- limit rate {arm}: {v['n_limit']}/{v['n_scored']} = {_fmt(v['limit_rate'])}")
    for arm, v in report["beside"]["silenced_counts"].items():
        lines.append(f"- {arm} (m = {v['m']}): handoff {v['n_handoff']}, no handoff {v['n_no_handoff']}, "
                     f"flag missing {v['n_flag_missing']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J12 prefix-depth test (docs/prereg_j12_depth_test_20260924.md).")
    p.add_argument("--split", required=True, choices=["dev", "test_normal", "test_challenge"])
    p.add_argument("--confirm-heldout-test-split", dest="confirm_heldout_test_split", action="store_true")
    p.add_argument("--plumbing-check", action="store_true", help="dev only, over *_dryrun campaigns only")
    p.add_argument("--seeds", default=j10.A1_DEFAULT_SEEDS, help="registered seeds (1,2)")
    p.add_argument("--expected-n-tasks", type=int, default=None, help="default: dev 57, test_normal 168")
    p.add_argument("--arm", action="append", required=True, metavar="LABEL=DIR",
                   help=f"repeatable; labels {sorted(J12_ARMS)} and, optionally, {J12_PLAN_SOURCE_ARM}")
    p.add_argument("--bootstrap-seed", type=int, default=j10.A1_BOOTSTRAP_SEED)
    p.add_argument("--n-boot", type=int, default=j10.A1_BOOTSTRAP_N)
    p.add_argument("--out", type=Path, default=None,
                   help=f"report JSON; a .md is written beside it. Default on test_normal: {J12_DEFAULT_OUT}")
    return p


def parse_arms(specs: Iterable[str]) -> dict[str, Path]:
    allowed = set(J12_ARMS) | {J12_PLAN_SOURCE_ARM}
    arm_dirs: dict[str, Path] = {}
    for spec in specs:
        label, sep, directory = spec.partition("=")
        if not sep or not label or not directory:
            raise ValueError(f"expected LABEL=DIR, got {spec!r}")
        if label not in allowed:
            raise ValueError(f"unknown arm label {label!r}; allowed: {sorted(allowed)}")
        if label in arm_dirs:
            raise ValueError(f"duplicate --arm {label}")
        arm_dirs[label] = Path(directory)
    return arm_dirs


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        seeds = j10.parse_seeds(args.seeds)
        arm_dirs = parse_arms(args.arm)
    except ValueError as exc:
        print(json.dumps({"protocol": "J12", "refused": True, "reason": str(exc)}, indent=2))
        return 2
    expected = args.expected_n_tasks
    if expected is None:
        expected = j10.A1_SPLIT_N_TASKS.get(args.split, 0)
    out = args.out
    if out is None and args.split == "test_normal":
        out = REPO_ROOT / J12_DEFAULT_OUT
    report, code = build_report_j12(
        split=args.split, seeds=seeds, arm_dirs=arm_dirs, expected_n_tasks=expected,
        confirm_heldout_test_split=args.confirm_heldout_test_split, plumbing_check=args.plumbing_check,
        n_boot=args.n_boot, bootstrap_seed=args.bootstrap_seed, out_path=out)
    text = json.dumps(report, indent=2, default=str) + "\n"
    print(text, end="")
    if out is not None and code != 2:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        out.with_suffix(".md").write_text(render_markdown(report, out.name), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
