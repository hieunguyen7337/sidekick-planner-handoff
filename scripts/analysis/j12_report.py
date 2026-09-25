#!/usr/bin/env python
"""J12: the prefix-depth test on test_normal, analysed as docs/prereg_j12_depth_test_20260924.md registers it.

Four predictions on goal_pass, one Holm family of m = 4, J12's own, all predicted > 0: the lower
bound of the scenario-clustered 95 % interval above 0 and the Holm-adjusted p <= 0.05 (J12 §3-§4).

  D1  J10 prefix_m11    − J12 prefix_m6     all pairs
  D2  J10 prefix_zs_m11 − J12 prefix_zs_m6  all pairs
  D3  as D1, handoff-only: Σ d·h / Σ h, h = the m = 11 episode's h* (the executor took control)
  D4  as D2, handoff-only

h* (scripts/analysis/handoff_control.py) is 1 iff the loop ran live after the replayed prefix. It
replaces handoff_occurred (effective_m < n_source_actions, src/sidekick/prefix_source.py:184), which is
false whenever the source made at most m executed actions even if its prefix was not terminal and the
executor then took control (src/sidekick/systems/loop.py:743-756 at the arms' pin 6f40fec; the block has
moved at HEAD); J12 Amendment 1 (committed) makes h* the registered D3 / D4 estimand. The flag versions
are kept as the sensitivity keys D3_flag / D4_flag (``sensitivity_h_flag``), re-read in their own Holm
family of four (D1, D2, D3_flag, D4_flag), apart from the registered family; D1 / D2 do not use h.

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

The handoff-only estimand mirrors scripts/analysis/j17_depth_fixes.py:329-346 (paired_components):
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
      --arm planner_alone_cap81=DIR [--divergent-refill-confirmed] \\
      [--out campaign/results/j12_depth_test_normal.report.json]
  On test_normal every DIR's name must be its arm's registered campaign id (§2; arm 3's is J10's), arm 3
  is required, and --seeds / --expected-n-tasks must be the registered 1,2 / 168. Arm 3 incomplete or its
  planless keys above the cap: J12 is reported NOT RUN (§6). --plumbing-check is accepted only on dev, and
  only over *_dryrun campaigns; test_challenge is always refused.
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

from scripts.analysis import handoff_control as hc  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.analysis import replay_divergence as rd  # noqa: E402

J12_PREREG = "docs/prereg_j12_depth_test_20260924.md"
J12_DEV_REPORT = "campaign/results/j17_depth_fixes_20260924.report.json"
# D3 / D4's dev values with h* (scripts/analysis/j17_hstar.py; same key paths as J12_DEV_REPORT).
J12_DEV_REPORT_HSTAR = "campaign/results/j17_hstar_20260924.report.json"
J12_H_DESCRIPTION = {hc.HSTAR_NAME: "h* (the executor took control after the replayed prefix)",
                     hc.HFLAG_NAME: "handoff_occurred"}
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
# J12 Amendment 2 (2026-09-25): J10 A1 Amendment 5 §B unchanged. Every J12 arm replays arm 3's environment
# prefix (the two M^r_6 arms and J10's prefix_m11 / prefix_zs_m11), so D1-D4 each remove the union of
# their two arms' divergent keys (scripts/analysis/replay_divergence.py), up to 16.
J12_AM2 = f"{J12_PREREG} Amendment 2"
# The registered read (J12 §2, §6:164): seeds 1, 2 over all 168 test_normal tasks, the four contrast arms and
# J10 arm 3, each under its registered campaign id, read from its config's campaign_id (never typed here).
J12_TEST_SEEDS: tuple[int, ...] = (1, 2)
J12_TEST_N_TASKS = j10.A1_SPLIT_N_TASKS["test_normal"]  # 168
J12_ARM_CONFIGS: dict[str, str] = {**J12_ARMS, J12_PLAN_SOURCE_ARM: str(j10.A1_ARMS[J12_PLAN_SOURCE_ARM])}
# J12 §4:103: a D that is not supported is reported as "not replicated". Display only: the JSON verdict stays.
J12_VERDICT_WORDS = {"not_supported": "not replicated", "not_run": "not run"}
# A1 §5.5 (A1:317-318): the sign-flip p is set against the bootstrap's unadjusted 95 % interval at the matching
# level -- 0.05 two-sided, 0.025 one-sided (cluster_inference.registered_signflip does not double a one-sided p).
J12_SIGNFLIP_LEVEL = {"two-sided": 0.05, "greater": 0.025, "less": 0.025}
# A1 Amendment 5 §B.1 (J12 Amendment 2): a divergent key counts only after at least one crash-only resumption
# run after the crash first appeared. The result files cannot show that; the operator confirms it.
J12_REFILL_HOW = (
    "confirm that each arm with a divergent key had at least one crash-only resumption run after the crash first "
    "appeared: resubmit that arm's job line (scripts/pbs/j12_arm.pbs for a J12 arm, scripts/pbs/j10_arm.pbs for "
    "J10's prefix_m11 / prefix_zs_m11), which purges the crashed episodes and re-runs only them; a later job's "
    "'[j10] resume:' and '[j10] tally cid=... crashed=N' lines must show the same keys still crashed. Then re-run "
    "this read with --divergent-refill-confirmed.")


def _dev(key: str, diff_pp: float, ci: list[float], n_pairs: int, n_handoff: Optional[int] = None,
         source: str = J12_DEV_REPORT, h: Optional[str] = None) -> dict[str, Any]:
    ref: dict[str, Any] = {"diff_pp": diff_pp, "ci95_pp_scenario": ci, "n_pairs": n_pairs}
    if n_handoff is not None:
        ref["n_handoff"] = n_handoff
    if h is not None:
        ref["h"] = h
    return ref | {"source": source, "key": key, "bootstrap_seed": j10.A1_BOOTSTRAP_SEED,
                  "population": "pooled cap-81 dev family, seeds 1-3 (hj17 + hj18)"}


# J12 §4, as data. dev_reference is the dev value rounded to 2 dp, from the report its `source` names
# (tests/unit/test_j12_report.py checks it against that JSON): j17_depth_fixes for D1 / D2, j17_hstar
# for D3 / D4 (h*). dev_reference_flag keeps D3 / D4's flag-based dev value, the frozen text's number.
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
     "left": "prefix_m11", "right": "prefix_m6", "flags_from": "prefix_m11", "h": hc.HSTAR_NAME, "rule": J12_RULE,
     "threshold_pp": 0.0, "holm_family": True,
     "statement": ("as D1 on handoff episodes: Σ d·h / Σ h > 0, h = h* of the prefix_m11 episode (the "
                   "executor took control after the replayed prefix)"),
     "citation": f"{J12_PREREG} §3-§4; h* per J12 Amendment 1",
     "dev_reference": _dev("handoff_only_contrasts.bplus.m6_to_m11.goal_pass.handoff_only", 7.66,
                           [1.19, 14.06], 171, n_handoff=88, source=J12_DEV_REPORT_HSTAR, h=hc.HSTAR_NAME),
     "dev_reference_flag": _dev("handoff_only_contrasts.bplus.m6_to_m11.goal_pass.handoff_only", 12.03,
                                [5.49, 18.57], 171, n_handoff=71, h=hc.HFLAG_NAME)},
    {"id": "D4", "kind": "handoff_only", "receiver": "zs", "population": "handoff_only", "metric": "goal_pass",
     "left": "prefix_zs_m11", "right": "prefix_zs_m6", "flags_from": "prefix_zs_m11", "h": hc.HSTAR_NAME,
     "rule": J12_RULE, "threshold_pp": 0.0, "holm_family": True,
     "statement": ("as D2 on handoff episodes: Σ d·h / Σ h > 0, h = h* of the prefix_zs_m11 episode (the "
                   "executor took control after the replayed prefix)"),
     "citation": f"{J12_PREREG} §3-§4; h* per J12 Amendment 1",
     "dev_reference": _dev("handoff_only_contrasts.zs.m6_to_m11.goal_pass.handoff_only", 7.81,
                           [0.79, 13.95], 171, n_handoff=88, source=J12_DEV_REPORT_HSTAR, h=hc.HSTAR_NAME),
     "dev_reference_flag": _dev("handoff_only_contrasts.zs.m6_to_m11.goal_pass.handoff_only", 13.93,
                                [5.12, 21.22], 171, n_handoff=71, h=hc.HFLAG_NAME)},
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
    episode's indicator in ``handoff_flags`` -- h* for the registered read, handoff_occurred for the
    D3_flag / D4_flag sensitivity (``pred["h"]`` names which) -- whole clusters resampled. Returns the keys
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
    # J12 Amendment 2: both arms without the pair's divergent keys (the two arms themselves without any).
    left_arm, right_arm = j10.a1_am5_pair(arms, pred["left"], pred["right"])
    left, right = left_arm["episodes"], right_arm["episodes"]
    flags = handoff_flags.get(pred["flags_from"], {})
    field = j10.A1_METRIC_FIELDS[pred["metric"]]
    t = float(pred["threshold_pp"]) / 100.0
    comps, n_missing_field, n_flag_missing = j10.am1_handoff_comps(left, right, flags, field)
    units = ("scenario", "task")
    boot = j10.a1_ratio_bootstrap(comps, {"handoff_only": (0, 1)}, units, n_boot=n_boot, seed=seed,
                                  keep_samples=True)
    contrast: dict[str, Any] = {
        "field": field,
        "estimand": (f"Σ d·h / Σ h, d = {pred['left']} − {pred['right']}, h = {pred['flags_from']}'s "
                     f"{J12_H_DESCRIPTION.get(pred.get('h', hc.HSTAR_NAME), pred.get('h'))}"),
        "h": pred.get("h", hc.HSTAR_NAME),
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
    # J12 §4:104-106: a reversal prints its one-sided "less" p, unadjusted; internal until one is read.
    out["_p_less"] = j10.bootstrap_pvalue(samples, t, "less")
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
    incomplete = [a for a, arm in ((pred["left"], left_arm), (pred["right"], right_arm)) if not arm["complete"]]
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
    out = j10.a1_evaluate_contrast_prediction(pred, arms, n_boot=n_boot, seed=seed, stability=stability)
    if stability and (out.get("events_unadjusted") or {}).get("hi_below_threshold"):
        out["_p_less"] = j12_p_less_paired(pred, arms, n_boot=n_boot, seed=seed)
    return out


def j12_p_less_paired(pred: dict[str, Any], arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> float:
    """J12 §4:104-106 for D1 / D2: j10_report.bootstrap_pvalue(..., direction="less") at the threshold, on the
    scenario resamples a1_evaluate_contrast_prediction drew (the same arms, series, B and seed, so the same
    draws); that function keeps only the 'greater' and two-sided p, so the resamples are drawn again here."""
    left, right = j10.a1_am5_pair(arms, pred["left"], pred["right"])
    series = j10.a1_paired_series(left["episodes"], right["episodes"], j10.A1_METRIC_FIELDS[pred["metric"]])
    means = j10.a1_interval(series, "scenario", n_boot=n_boot, seed=seed)["_means"]
    return j10.bootstrap_pvalue(means, float(pred["threshold_pp"]) / 100.0, "less")


def j12_apply_pair_rule(r: dict[str, Any], arms: dict[str, dict[str, Any]], expected_pairs: int) -> None:
    """J12 §3 / A1 §9: a contrast whose arms lack `expected_pairs` non-crashed pairs is incomplete.

    J12 Amendment 2 (A1 Amendment 5 §B.3): read with the pair's divergent keys removed -- the pairs counted
    without them, against `expected_pairs` minus their number -- up to 16; above that the D is incomplete."""
    if r["left"] not in arms or r["right"] not in arms:
        return
    excluded, verdict = j10.a1_am5_exclusion(arms, r["left"], r["right"])
    shared = len((set(arms[r["left"]]["episodes"]) & set(arms[r["right"]]["episodes"])) - set(excluded))
    expected = expected_pairs - len(excluded) if verdict == rd.VERDICT_OK else expected_pairs
    r["n_noncrashed_pairs"] = shared
    r["expected_pairs"] = expected
    if verdict != rd.VERDICT_OK:
        why = f"{J12_AM2}: {len(excluded)} divergent keys to remove > cap {rd.DIVERGENCE_CAP}"
        r.update(decidable=False, verdict="refused_incomplete",
                 reason="; ".join(x for x in (r.get("reason"), why) if x))
        return
    if shared < expected and r.get("decidable"):
        r.update(decidable=False, verdict="refused_incomplete",
                 reason=f"{shared} non-crashed pairs, below the registered {expected}")


def j12_decide_family(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Holm over D1-D4 through a1_decide_family, then the unadjusted reversal flag (J12 §4: an upper
    bound below 0 is reported as a primary finding; the "greater" p cannot reject for it).

    J12 §3:77-78: an incomplete contrast draws no reading, so the flag is read only for a decidable D
    (None otherwise). A reversal carries its one-sided "less" p, unadjusted (§4:104-106)."""
    multiplicity = j10.a1_decide_family(results)
    for r in results:
        ev = r.get("events_unadjusted") or {}
        r["reversal_unadjusted"] = bool(ev.get("hi_below_threshold")) if ev and r.get("decidable") else None
        if r["reversal_unadjusted"]:
            r["p_value_less_unadjusted"] = r.get("_p_less")
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


# ---- the handoff_occurred sensitivity: D3_flag / D4_flag ------------------------------------------
def j12_flag_sensitivity(
    results: list[dict[str, Any]],
    arms: dict[str, dict[str, Any]],
    flag_handoff: dict[str, dict[tuple[str, int], Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
    expected_pairs: Optional[int] = None,
) -> dict[str, Any]:
    """D3 / D4 re-read with h = handoff_occurred (h_flag) in place of h*, reported as D3_flag / D4_flag.
    Same bootstrap, the same Holm family of four (D1, D2 and the two flag reads), the same rule and pair
    rule; POOL-04 and the sign-flip not re-run, as in the key-exclusion re-read. Not decision-bearing."""
    sens = [j12_evaluate(dict(p, h=hc.HFLAG_NAME) if p["kind"] == "handoff_only" else dict(p), arms,
                         flag_handoff, n_boot=n_boot, seed=seed, stability=False)
            for p in J12_PREDICTIONS]
    if expected_pairs is not None:
        for s in sens:
            j12_apply_pair_rule(s, arms, expected_pairs)
    j10.a1_decide_family(sens)
    by_id = {r["id"]: r for r in results}
    out: dict[str, Any] = {
        "decision_bearing": False,
        "what": ("D3 / D4 with h = the m = 11 episode's handoff_occurred (h_flag) in place of h*; Holm over "
                 "D1, D2, D3_flag, D4_flag; POOL-04 and the sign-flip not re-run"),
        "h_flag": hc.FLAG_DEFINITION,
    }
    differs = []
    for s in sens:
        if s["kind"] != "handoff_only":
            continue
        r = by_id.get(s["id"], {})
        differ = bool(r.get("decidable") and s.get("decidable") and r.get("verdict_holm") != s.get("verdict_holm"))
        if differ:
            differs.append(s["id"])
        out[f"{s['id']}_flag"] = {
            "id": f"{s['id']}_flag", "sensitivity_of": s["id"], "h": hc.HFLAG_NAME,
            "contrast": s.get("contrast"), "p_value": s.get("p_value"),
            "verdict_unadjusted": s.get("verdict_unadjusted"), "holm": s.get("holm"),
            "verdict_holm": s.get("verdict_holm"), "verdict_holm_with_hstar": r.get("verdict_holm"),
            "differs_from_hstar": differ, "decidable": s.get("decidable"), "reason": s.get("reason")}
    out["verdict_holm_differs"] = differs
    return out


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
            sentence = (f"{r['id']} {j12_word(r.get('verdict'))}; " + "; ".join(
                f"{a}: {per[a]['n_episodes_live_answer']} episode(s) got a live answer to an executor ask, "
                f"bounding its mean at {per[a]['bound_pp']:.2f} pp" for a in reach)
                + f" ({A1_AM1_I}; no verdict changes).")
        out[r["id"]] = {"arms": per, "any_bound_reaches_1pp": bool(reach), "sentence": sentence}
    return out


# ---- the verdict's sentence ----------------------------------------------------------------------
def j12_word(verdict: Any) -> str:
    """J12 §4:103: not_supported is printed "not replicated" wherever a verdict is printed; the JSON keeps the code."""
    return J12_VERDICT_WORDS.get(verdict, str(verdict))


def j12_signflip_disagreement(r: dict[str, Any]) -> Optional[dict[str, Any]]:
    """A1 §5.5 (A1:317-318, via J12 §3:71): a sign-flip p that disagrees with the bootstrap verdict is reported in
    the verdict's sentence. Not decision-bearing.

    Like is set against like: the bootstrap side is the unadjusted 95 % scenario interval's event against the
    threshold (lo above / hi below, the events every verdict here is read from); the sign-flip side is its p at the
    matching level (J12_SIGNFLIP_LEVEL), in the direction of the point estimate when the test is two-sided. A
    one-sided test reaches only its own side. None when the D is not decidable or either p or events is absent."""
    perm = r.get("permutation_sensitivity") or {}
    p, ev = perm.get("p_value"), r.get("events_unadjusted")
    if not r.get("decidable") or p is None or not ev:
        return None
    alt = perm.get("alternative", "two-sided")
    level = J12_SIGNFLIP_LEVEL.get(alt, 0.05)
    t_pp = float(r["threshold_pp"])
    point_pp = ((r.get("contrast") or {}).get("scenario") or {}).get("diff_pp")
    boot = ("above" if ev.get("lo_above_threshold") and alt in ("two-sided", "greater")
            else "below" if ev.get("hi_below_threshold") and alt in ("two-sided", "less") else None)
    flip = None
    if float(p) <= level + 1e-12:
        flip = ("above" if alt == "greater" else "below" if alt == "less"
                else None if point_pp is None or point_pp == t_pp else "above" if point_pp > t_pp else "below")
    out: dict[str, Any] = {
        "rule": "A1 §5.5: a disagreement is reported in the same sentence as the verdict; not decision-bearing",
        "basis": (f"bootstrap: the unadjusted 95 % scenario interval against {t_pp:+.2f} pp; sign-flip: its p at "
                  f"{level} ({alt})"),
        "p_value": p, "alternative": alt, "level": level, "bootstrap_side": boot, "signflip_side": flip,
        "agrees": boot == flip, "sentence": None}
    if boot != flip:
        if boot and flip:
            what = f"rejects at {level} on the {flip} side while the bootstrap interval lies {boot} {t_pp:+.2f} pp"
        elif boot:
            what = f"does not reject at {level} while the bootstrap interval excludes {t_pp:+.2f} pp"
        else:
            what = f"rejects at {level} while the bootstrap interval includes {t_pp:+.2f} pp"
        out["sentence"] = f"the scenario sign-flip p = {float(p):.4g} ({alt}) {what} (A1 §5.5; not decision-bearing)"
    return out


def j12_tgc_atom_notes(r: dict[str, Any]) -> Optional[str]:
    """A1 §5.2 (A1:275-277, via J12 §3:70): TGC is binary per episode, so its percentile bounds sit on atoms of the
    paired-difference distribution; a bound equal to its threshold's nearest atom is reported as such, not as a
    pass or fail by a hair. Every D's threshold is 0, itself an atom (k / n with k = 0 at any resample size n), so
    a bound on it is one within 0.005 pp of 0. D1 / D2: tgc_secondary's scenario and task intervals; D3 / D4: its
    handoff_only and all rows (a1_handoff_depth). At most one note per D's TGC row, naming every bound on the atom;
    None when no bound is on it."""
    t = float(r.get("threshold_pp", 0.0))
    tgc = r.get("tgc_secondary") or {}
    if t != 0.0 or not tgc:
        return None
    rows: list[tuple[str, Any]] = []
    if r.get("kind") == "handoff_only":
        for pop, name in (("handoff_only", "handoff-only"), ("all", "all-episode")):
            for unit in ("scenario", "task"):
                rows.append((f"{name} {unit}", (tgc.get(pop) or {}).get(f"ci95_pp_{unit}")))
    else:
        for unit in ("scenario", "task"):
            rows.append((unit, (tgc.get(unit) or {}).get("ci95_pp")))
    groups, n_bounds = [], 0
    for where, ci in rows:
        sides = [side for side, b in zip(("lower", "upper"), ci or ()) if b is not None and abs(float(b) - t) < 0.005]
        if sides:
            groups.append(f"the {where} {' and '.join(sides)}")
            n_bounds += len(sides)
    if not groups:
        return None
    named = groups[0] if len(groups) == 1 else ", ".join(groups[:-1]) + " and " + groups[-1]
    verb = "bound sits" if n_bounds == 1 else "bounds sit"
    return f"{r['id']} TGC: {named} {verb} on the atom at the threshold {t:g} (A1 §5.2)"


def j12_verdict_sentence(r: dict[str, Any]) -> str:
    """One D's verdict as printed: the J12 §4 word, a reversal's unadjusted 'less' p, and a disagreeing sign-flip."""
    parts = [f"{r['id']} {j12_word(r.get('verdict'))}"]
    if r.get("reversal_unadjusted"):
        p_less = r.get("p_value_less_unadjusted")
        parts.append("reversal (the unadjusted scenario interval's upper bound is below 0), a primary finding; "
                     f"one-sided p (less) = {'—' if p_less is None else f'{float(p_less):.4g}'}, unadjusted")
    note = (r.get("signflip_disagreement") or {}).get("sentence")
    if note:
        parts.append(note)
    return "; ".join(parts)


# ---- readings ----------------------------------------------------------------------------------
def j12_readings(results: list[dict[str, Any]], not_run: Optional[str] = None) -> dict[str, Any]:
    """J12 §4's fixed readings, per receiver, from the final verdicts. When the D1 / D3 (D2 / D4) pattern cannot
    apply -- the handoff-only D on the boundary or incomplete, or the all-episode D undecided -- the reason is
    one explicit line. With `not_run` (§6's abort rule) no reading is drawn."""
    by_id = {r["id"]: r for r in results}
    out = {}
    for receiver, (all_id, ho_id) in J12_READING_PAIRS.items():
        va, vh = by_id[all_id].get("verdict"), by_id[ho_id].get("verdict")
        word = J12_RECEIVER_WORD[receiver]
        if not_run:
            key = None
        elif va == "supported" and vh == "supported":
            key = "all_and_handoff"
        elif va == "supported" and vh == "not_supported":
            key = "all_not_handoff"
        elif va == "not_supported":
            key = "all_not"
        else:
            key = None
        if not_run:
            reason: Optional[str] = f"J12 not run: {not_run}; no reading is drawn (J12 §6)"
        elif key is not None:
            reason = None
        elif va == "supported":
            reason = (f"{all_id} supported, but the {all_id} / {ho_id} pattern reading cannot apply: {ho_id} is "
                      f"{j12_word(vh)}, and J12 §4 fixes readings only for {ho_id} supported or not replicated")
        else:
            reason = (f"no fixed reading: {all_id} is {j12_word(va)}, and J12 §4 fixes readings only for {all_id} "
                      "supported or not replicated")
        reversals = [] if not_run else [i for i in (all_id, ho_id) if by_id[i].get("reversal_unadjusted")]
        out[receiver] = {
            "ids": [all_id, ho_id],
            "verdicts": {all_id: va, ho_id: vh},
            "reading_key": key,
            "reading": None if key is None else J12_READINGS[key].format(receiver=word),
            "no_reading_reason": reason,
            "not_supported_is_reported_as": "not replicated, never as evidence of no effect",
            "reversals_unadjusted": reversals,
        }
    return out


# ---- protocol ------------------------------------------------------------------------------------
def j12_registered_campaigns(repo_root: Path = REPO_ROOT) -> dict[str, str]:
    """label -> the campaign id its config declares (J12 §2): the two J12 arms, J10's two m = 11 arms and J10
    arm 3 (J12_ARM_CONFIGS). Raises ValueError if a config cannot be read or its id is not a registered one."""
    import yaml  # lazy, as j11_report.resolve_campaigns

    out: dict[str, str] = {}
    for label, rel in J12_ARM_CONFIGS.items():
        try:
            data = yaml.safe_load((repo_root / rel).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"{rel}: cannot read campaign_id ({type(exc).__name__}: {exc})") from exc
        cid = data.get("campaign_id") if isinstance(data, dict) else None
        if not isinstance(cid, str) or not REGISTERED_TEST_ID.match(cid):
            raise ValueError(f"{rel}: campaign_id {cid!r} is not a registered J10/J12 test campaign id")
        out[label] = cid
    return out


def j12_read_command(campaigns: dict[str, str], root: Path = j10.RAW_RESULTS_ROOT) -> str:
    """The registered read (J12 §6:164) with every arm J12 reads, arm 3 included, at its campaign directory."""
    arms = " ".join(f"--arm {label}={root / campaigns[label]}" for label in J12_ARM_CONFIGS)
    return f"python scripts/analysis/j12_report.py --split test_normal --confirm-heldout-test-split {arms}"


def j12_protocol_guard(
    split: str,
    confirm: bool,
    plumbing: bool,
    arm_dirs: dict[str, Path],
    out_path: Optional[Path],
    registered_settings: bool,
    *,
    seeds: Optional[list[int]] = None,
    expected_n_tasks: Optional[int] = None,
) -> Optional[str]:
    """A1's guard (test_normal needs the flag; no plumbing on test; held-out markers; no --out under
    the raw results; registered bootstrap on test), plus J12's: test_challenge is never read; a
    registered J10 / J12 test campaign id is read only on test_normal and a *_dryrun one never
    there; --plumbing-check reads only *_dryrun campaigns on dev. On test_normal, the registered read
    only: seeds 1, 2 and 168 tasks (§2); every --arm directory named by its arm's registered campaign id
    (§2, from the configs); and J10 arm 3 given (§3's planless keys, §6's abort rule)."""
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
    if split == "test_normal":
        if seeds is not None and sorted(seeds) != list(J12_TEST_SEEDS):
            return (f"refusing test_normal with seeds {sorted(seeds)}: the registered read is seeds "
                    f"{', '.join(map(str, J12_TEST_SEEDS))} [{J12_PREREG} §2]")
        if expected_n_tasks is not None and expected_n_tasks != J12_TEST_N_TASKS:
            return (f"refusing test_normal with --expected-n-tasks {expected_n_tasks}: the registered read is all "
                    f"{J12_TEST_N_TASKS} test_normal tasks [{J12_PREREG} §2]")
        try:
            campaigns = j12_registered_campaigns()
        except ValueError as exc:
            return f"refusing test_normal: {exc}"
        for label, directory in sorted(arm_dirs.items()):
            want = campaigns.get(label)
            if want is not None and Path(directory).name != want:
                return (f"refusing {label}={directory}: on test_normal {label} is the registered campaign {want} "
                        f"[{J12_PREREG} §2], not {Path(directory).name!r}")
        if J12_PLAN_SOURCE_ARM not in arm_dirs:
            return (f"refusing test_normal without --arm {J12_PLAN_SOURCE_ARM}=DIR: J10 arm 3 is required on the "
                    f"registered read, for its planless keys ({J12_PREREG} §3; A1 §4.2) and the §6 abort rule. "
                    f"The registered read is: {j12_read_command(campaigns)}")
    return None


def j12_am2_block(
    arms: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
    flag_sensitivity: dict[str, Any],
    decomposition: dict[str, Any],
    *,
    refill_confirmed: bool = False,
    confirmation_required: bool = False,
) -> dict[str, Any]:
    """J12 Amendment 2 (A1 Amendment 5 §B.5), reported regardless of outcome: each J12 arm's divergent keys and
    their count, zero included, and each affected D's (and companion's) number of pairs.

    §B.1's resumption condition (a key counts only after >= 1 crash-only resumption run) is not readable from the
    result files, so the operator confirms it (--divergent-refill-confirmed): `refill_confirmed_by_operator` is
    the flag when a divergent key exists, None when none does (the flag is then irrelevant)."""
    per_arm = {}
    for label in J12_ARMS:
        if label in arms:
            keys = arms[label].get(j10.A1_AM5_PRIVATE) or []
            per_arm[label] = {"n_divergent": len(keys), "keys": [rd.key_label(k) for k in keys],
                              "n_crash_other": arms[label]["n_crash"] - len(keys),
                              "arm_complete": arms[label]["complete"]}
    contrasts: dict[str, Any] = {}
    for r in results:
        if r["left"] not in arms or r["right"] not in arms:
            continue
        excluded, verdict = j10.a1_am5_exclusion(arms, r["left"], r["right"])
        if excluded:
            flag = flag_sensitivity.get(f"{r['id']}_flag") or {}
            contrasts[r["id"]] = {
                "left": r["left"], "right": r["right"], "population": r.get("population"),
                "n_excluded": len(excluded), "excluded_keys": [rd.key_label(k) for k in excluded],
                "verdict": verdict, "n_pairs": (r.get("contrast") or {}).get("n_pairs"),
                "n_noncrashed_pairs": r.get("n_noncrashed_pairs"), "expected_pairs": r.get("expected_pairs"),
                "decision": r.get("verdict")}
            if flag:
                contrasts[r["id"]]["n_pairs_h_flag"] = (flag.get("contrast") or {}).get("n_pairs")
    companions: dict[str, Any] = {}
    for receiver, blk in decomposition.items():
        excluded, _verdict = j10.a1_am5_exclusion(arms, blk.get("target"), blk.get("base"))
        if excluded:
            companions[f"decomposition.{receiver}"] = {
                "n_excluded": len(excluded), "n_pairs": (blk.get("goal_pass") or {}).get("n_pairs")}
    non_replay = {label: [rd.key_label(k) for k in arm[j10.A1_AM5_NONREPLAY]]
                  for label, arm in arms.items() if arm.get(j10.A1_AM5_NONREPLAY)}
    n_total = sum(v["n_divergent"] for v in per_arm.values())
    return {
        "rule": f"{J12_AM2} (J10 A1 Amendment 5 §B, unchanged)",
        "decision_bearing": "completeness only: every statistic, the Holm family and every threshold run as registered",
        "definition": rd.DEFINITION,
        "cap": rd.DIVERGENCE_CAP,
        "replay_arms": list(J12_ARMS),
        "per_arm": per_arm,
        "n_divergent_total": n_total,
        "refill_confirmed_by_operator": bool(refill_confirmed) if n_total else None,
        "resumption_condition": {
            "rule": ("A1 Amendment 5 §B.1: a divergent key counts only after at least one crash-only resumption run "
                     "after the crash was first recorded; the result files cannot show it"),
            "required": bool(confirmation_required and n_total),
            "how_to_confirm": J12_REFILL_HOW,
        },
        "contrasts": contrasts,
        "companions": companions,
        "non_replay_divergent": {"keys": non_replay, "treated_as": "an ordinary crash"},
        "notes": list(j10.A1_AM5_NOTES[:2]) + [
            "D3 / D4's handoff-only populations, their h_flag sensitivity, the decomposition and the planless-key "
            "sensitivity are all read on the pairs left after the removal."],
    }


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
    divergent_refill_confirmed: bool = False,
) -> tuple[dict[str, Any], int]:
    registered = n_boot == j10.A1_BOOTSTRAP_N and bootstrap_seed == j10.A1_BOOTSTRAP_SEED
    proto = j12_protocol_guard(split, confirm_heldout_test_split, plumbing_check, arm_dirs, out_path, registered,
                               seeds=seeds, expected_n_tasks=expected_n_tasks)
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
    # J12 Amendment 2 (A1 Amendment 5 §B.1 / §B.3): an arm whose only crashes are divergent keys is complete;
    # a D whose two arms would lose more than 16 keys is named in the reasons.
    arms = j10.a1_am5_arms({label: j10.a1_arm_episodes(label, blob, tasks, seeds) for label, blob in loaded.items()},
                           contrast_dirs, tasks, seeds, J12_PREDICTIONS, reasons, replay_arms=tuple(J12_PREFIX_M))
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
    # J12 §6:148: J12 is reported NOT RUN if arm 3 cannot complete (336 non-crashed, 0 crashed on the registered
    # matrix) or its planless keys exceed the cap. Arm 3 is read over the contrast arms' matrix; never a contrast arm.
    not_run: list[str] = []
    plan_dir = arm_dirs.get(J12_PLAN_SOURCE_ARM)
    plan_arm = (None if plan_dir is None
                else j10.a1_arm_episodes(J12_PLAN_SOURCE_ARM, j10.load_arm_tree(plan_dir), tasks, seeds))
    if plan_arm is not None and not plan_arm["complete"]:
        not_run.append(f"J10 arm 3 ({J12_PLAN_SOURCE_ARM}) is incomplete: {plan_arm['n_scored']}/"
                       f"{plan_arm['n_expected']} non-crashed, crash {plan_arm['n_crash']}, missing "
                       f"{plan_arm['n_missing']}")

    # h* is D3 / D4's indicator; the flag (handoff_occurred, h_flag) is kept for the sensitivity.
    flag_handoff = {a: j10.a1_handoff_flags(contrast_dirs[a]) for a in sorted(contrast_dirs)}
    controls = {a: hc.arm_control(contrast_dirs[a]) for a in sorted(contrast_dirs)}
    handoff_flags = {a: {k: c[hc.HSTAR_NAME] for k, c in ctl.items()} for a, ctl in controls.items()}
    results = [j12_evaluate(dict(p), arms, handoff_flags, n_boot=n_boot, seed=bootstrap_seed)
               for p in J12_PREDICTIONS]
    for r in results:
        j12_apply_pair_rule(r, arms, expected_pairs)
    multiplicity = j12_decide_family(results)
    flag_sensitivity = j12_flag_sensitivity(results, arms, flag_handoff, n_boot=n_boot, seed=bootstrap_seed,
                                            expected_pairs=expected_pairs)

    # A1 §4.2 (J12 §3): the primary keeps every pair; a verdict that changes without arm 3's
    # planless keys is on the boundary. The cap is A1's 5 % of the matrix.
    planless = j10.a1_planless_keys(arm_dirs, seeds)
    planless_cap = int(expected_pairs * j10.A1_PLANLESS_CAP_FRACTION)
    contingency: dict[str, Any] = {
        "rule": "A1 §4.2 (J12 §3)", "source_arm": J12_PLAN_SOURCE_ARM, "cap": planless_cap,
        "keys": None if planless is None else [f"{s}/{t}" for t, s in planless],
        "n_keys": None if planless is None else len(planless), "sensitivity": None,
        "plan_source_arm": None if plan_arm is None else {
            k: plan_arm[k] for k in ("n_expected", "n_scored", "n_crash", "n_missing", "complete")}
        | {"dir": str(plan_dir), "rule": f"{J12_PREREG} §6:148 (not run if arm 3 cannot complete)"},
    }
    if planless is None:
        contingency["note"] = f"{J12_PLAN_SOURCE_ARM} not given; the planless keys cannot be listed"
    elif planless:
        if len(planless) > planless_cap:
            reasons.append(f"planless_keys_above_cap:{len(planless)}>{planless_cap}")
            not_run.append(f"{len(planless)} planless arm-3 keys > cap {planless_cap}")
        contingency["sensitivity"] = j12_key_exclusion_sensitivity(
            results, arms, handoff_flags, planless, n_boot=n_boot, seed=bootstrap_seed)
        j10.a1_apply_key_exclusion(results, contingency["sensitivity"]["differs"])
    for r in results:
        for key in [k for k in r if k.startswith("_")]:
            r.pop(key)
    not_run_why = "; ".join(not_run) + f" ({J12_PREREG} §6:148)" if not_run else None
    if not_run_why:
        # No D verdict is a registered result: each is kept, for diagnosis only, under computed_not_registered.
        for r in results:
            r["computed_not_registered"] = {k: r.pop(k) for k in ("verdict", "verdict_holm", "verdict_unadjusted")
                                            if k in r} | {"why": f"J12 not run: {not_run_why}"}
            r["verdict"] = "not_run"
            r["reversal_unadjusted"] = None
            r.pop("p_value_less_unadjusted", None)
    for r in results:
        r["signflip_disagreement"] = None if not_run_why else j12_signflip_disagreement(r)
        r["verdict_sentence"] = j12_verdict_sentence(r)

    live = {a: j12_live_asks(contrast_dirs[a], arms[a]) for a in sorted(arms)}
    bounds = j12_bound_rows(results, live)
    for r in results:
        r["live_ask_bound"] = bounds[r["id"]]
    readings = j12_readings(results, not_run_why)
    decomposition, decomposition_flag = {}, {}
    for receiver, (target, base) in J12_RECEIVERS.items():
        if target not in arms or base not in arms:
            decomposition[receiver] = decomposition_flag[receiver] = {
                "target": target, "base": base, "status": "arm_absent"}
            continue
        for out_, flags_, h in ((decomposition, handoff_flags, hc.HSTAR_NAME),
                                (decomposition_flag, flag_handoff, hc.HFLAG_NAME)):
            out_[receiver] = {"target": target, "base": base, "h": h} | {
                metric: j10.am1_decomposition(arms[target]["episodes"], arms[base]["episodes"],
                                              flags_.get(target, {}), j10.A1_METRIC_FIELDS[metric],
                                              n_boot=n_boot, seed=bootstrap_seed)
                for metric in ("goal_pass", "tgc")}
    # silenced_counts keep the flag (h_flag) as before; silenced_counts_h_star count the same with h* (J12 §4:110,
    # Amendment 1), and handoff_control_counts cross the two.
    silenced = {a: j10.a1_no_handoff_counts(arms[a], flag_handoff.get(a, {}), J12_PREFIX_M.get(a))
                | {"citation": f"{J12_PREREG} §4 (silenced count: episodes with no handoff)", "h": hc.HFLAG_NAME}
                for a in sorted(arms)}
    silenced_hstar = {a: j10.a1_no_handoff_counts(arms[a], handoff_flags.get(a, {}), J12_PREFIX_M.get(a))
                      | {"citation": f"{J12_PREREG} §4 and Amendment 1 (silenced count with h*)", "h": hc.HSTAR_NAME}
                      for a in sorted(arms)}
    control_counts = {a: {"m": J12_PREFIX_M.get(a)} | hc.control_counts(controls[a], keys=arms[a]["episodes"].keys())
                      for a in sorted(arms) if a in controls}

    # J12 Amendment 2 / A1 Amendment 5 §B.1: on the registered read a divergent key needs the operator's
    # confirmation of a crash-only resumption run; without it the read is INCOMPLETE.
    registered_read = split == "test_normal" and registered and not plumbing_check
    am2 = j12_am2_block(arms, results, flag_sensitivity, decomposition, refill_confirmed=divergent_refill_confirmed,
                        confirmation_required=registered_read)
    if registered_read and am2["n_divergent_total"] and not divergent_refill_confirmed:
        reasons.append(f"divergent_keys_need_refill_confirmation:{am2['n_divergent_total']}")

    decided = [r for r in results if r.get("decidable")]
    all_decided = len(decided) == len(results)
    label = ("PLUMBING CHECK, NOT A RESULT" if plumbing_check
             else "J12 DRY RUN ON DEV, NOT THE J12 RESULT" if split == "dev"
             else "J12 NOT RUN (§6 abort rule), NOT A RESULT" if not_run_why
             else "J12 registered analysis")
    if not registered:
        label += " (NON-REGISTERED bootstrap settings)"
    if not_run_why:
        status = "NOT_RUN"
        headline = f"J12 not run: {not_run_why}."
    else:
        status = "COMPLETE" if all_decided and not reasons else "INCOMPLETE"
        headline = ("COMPLETE: D1-D4 decided." if status == "COMPLETE"
                    else "INCOMPLETE: " + "; ".join(reasons or ["some predictions not decidable"]) + ".")
        headline += " Verdicts: " + "; ".join(r["verdict_sentence"] for r in results) + "."
        sentences = [b["sentence"] for b in bounds.values() if b["sentence"]]
        if sentences:
            headline += " " + " ".join(sentences)
    report: dict[str, Any] = {
        "protocol": "J12",
        "prereg": J12_PREREG,
        "generated_by": "scripts/analysis/j12_report.py",
        "label": label,
        "status": status,
        "headline": headline,
        "not_the_j12_result": bool(plumbing_check or not registered or split != "test_normal" or not_run_why),
        "not_run_reasons": not_run,
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
            "p_reversal": ("p_value_less_unadjusted: direction 'less' at 0, unadjusted, for a decidable D whose "
                           "unadjusted scenario upper bound is below 0 (J12 §4:104-106)"),
        },
        "stability_rule": {"id": "POOL-04", "window_pp": j10.POOL04_WINDOW_PP, "seeds": list(j10.POOL04_SEEDS),
                           "reported_bound": {"n_boot": j10.POOL04_BIG_N, "seed": j10.POOL04_BIG_SEED}},
        "permutation_rule": {"id": "A1 §5.5", "decision_bearing": False, "clusters": "scenario",
                             "alternative": "two-sided", "handoff_only": "over the handoff pairs' d",
                             "disagreement": ("signflip_disagreement per D: its p at 0.05 (two-sided) against the "
                                              "unadjusted 95 % scenario interval; a disagreement is in verdict_sentence")},
        "multiplicity": multiplicity,
        "planless_contingency": contingency,
        "arms": {a: {k: v for k, v in arm.items() if k != "episodes"}
                 | {"split_provenance": provenance[a], "config": J12_ARMS[a], "m": J12_PREFIX_M[a]}
                 for a, arm in sorted(arms.items())},
        "predictions": results,
        "verdicts": {r["id"]: r.get("verdict") for r in results},
        "readings": readings,
        "handoff_indicator": {"D3_D4": hc.HSTAR_NAME, "h_star": hc.DEFINITION, "h_flag": hc.FLAG_DEFINITION,
                              "sensitivity": "sensitivity_h_flag (D3_flag, D4_flag)"},
        "sensitivity_h_flag": flag_sensitivity,
        # Reported beside the family, not decision-bearing (J12 §4).
        "beside": {
            "decision_bearing": False,
            "tgc": {r["id"]: r.get("tgc_secondary") for r in results},
            "tgc_atom_notes": {r["id"]: j12_tgc_atom_notes(r) for r in results},
            "silenced_counts": silenced,
            "silenced_counts_h_star": silenced_hstar,
            "handoff_control_counts": control_counts,
            "decomposition": decomposition,
            "decomposition_h_flag": decomposition_flag,
            "limit_rates": j10.am1_limit_rates(arms),
            "sign_flip_p": {r["id"]: (r.get("permutation_sensitivity") or {}).get("p_value") for r in results},
            "live_asks": live,
        },
        "crash_convention": ("error_type == 'crash' is not an outcome (dropped, counted, arm incomplete); "
                             "limit / timeout / parse_error / api_error are scored outcomes."),
        "j12_am2_divergence": am2,
    }
    report = j10._strip_internal(report)
    return report, (0 if status == "COMPLETE" else 1)


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
            f"{_fmt((r.get('holm') or {}).get('p_adjusted'))} | {j12_word(r.get('verdict'))} |")
    not_run = report.get("status") == "NOT_RUN"
    lines += ["", "Verdicts (J12 §4: not supported is reported as not replicated):", ""]
    lines += [f"- {r.get('verdict_sentence') or r['id']}" for r in report["predictions"]]
    sens = report.get("sensitivity_h_flag") or {}
    lines += ["", "D3 / D4: h = h*, the executor took control after the replayed prefix "
              "(scripts/analysis/handoff_control.py). Sensitivity with h = handoff_occurred (not decision-bearing):", ""]
    for sid in ("D3_flag", "D4_flag"):
        if not_run:
            lines.append(f"- {sid}: not printed (J12 not run)")
            continue
        s = sens.get(sid) or {}
        scen = (s.get("contrast") or {}).get("scenario") or {}
        lines.append(f"- {sid}: {_fmt(scen.get('diff_pp'))} pp {_fmt(scen.get('ci95_pp'))}, n handoff "
                     f"{_fmt((s.get('contrast') or {}).get('n_handoff'))}, Holm p "
                     f"{_fmt((s.get('holm') or {}).get('p_adjusted'))}, verdict {j12_word(s.get('verdict_holm'))} "
                     f"(h*: {j12_word(s.get('verdict_holm_with_hstar'))})")
    by_pid = {r["id"]: r for r in report["predictions"]}
    lines += ["", "## Readings (J12 §4)", ""]
    for receiver, rd in report["readings"].items():
        rev = rd["reversals_unadjusted"]
        p_less = ", ".join(f"{i} {_fmt(by_pid[i].get('p_value_less_unadjusted'))}" for i in rev)
        lines.append(f"- {receiver}: {rd['reading'] or rd['no_reading_reason']}"
                     + (f". Reversal (unadjusted) in {rev}: reported as a primary finding; one-sided p (less), "
                        f"unadjusted: {p_less}." if rev else ""))
    lines += ["", "## Live executor asks (A1 Amendment 1 §I)", ""]
    for arm, v in report["beside"]["live_asks"].items():
        lines.append(f"- {arm}: {v['n_episodes_live_answer']} episode(s), {v['n_live_answer_calls']} call(s); "
                     f"bound {_fmt(v['bound_pp'])} pp of {v['bound_denominator']}")
    for r in report["predictions"]:
        if (r.get("live_ask_bound") or {}).get("sentence"):
            lines.append(f"- {r['live_ask_bound']['sentence']}")
    lines += ["", "## Beside the family (not decision-bearing)", ""]
    for pid, t in (report["beside"].get("tgc") or {}).items():
        t = t or {}
        if by_pid.get(pid, {}).get("kind") == "handoff_only":
            ho = t.get("handoff_only") or {}
            txt = (f"handoff-only {_fmt(ho.get('diff_pp'))} pp, scenario CI {_fmt(ho.get('ci95_pp_scenario'))}, "
                   f"task CI {_fmt(ho.get('ci95_pp_task'))}")
        else:
            scen, task = t.get("scenario") or {}, t.get("task") or {}
            txt = (f"{_fmt(scen.get('diff_pp'))} pp, scenario CI {_fmt(scen.get('ci95_pp'))}, "
                   f"task CI {_fmt(task.get('ci95_pp'))}")
        note = (report["beside"].get("tgc_atom_notes") or {}).get(pid)
        lines.append(f"- TGC {pid}: {txt}" + (f"; {note}" if note else ""))
    for arm, v in report["beside"]["limit_rates"].items():
        lines.append(f"- limit rate {arm}: {v['n_limit']}/{v['n_scored']} = {_fmt(v['limit_rate'])}")
    hstar_counts = report["beside"].get("silenced_counts_h_star") or {}
    for arm, v in report["beside"]["silenced_counts"].items():
        h = hstar_counts.get(arm) or {}
        lines.append(f"- silenced count {arm} (m = {v['m']}), by handoff_occurred: handoff {v['n_handoff']}, no handoff "
                     f"{v['n_no_handoff']}, flag missing {v['n_flag_missing']}; by h*: handoff {_fmt(h.get('n_handoff'))}, "
                     f"no handoff {_fmt(h.get('n_no_handoff'))}, h* undefined {_fmt(h.get('n_flag_missing'))}")
    for arm, v in (report["beside"].get("handoff_control_counts") or {}).items():
        lines.append(f"- {arm} (m = {v['m']}): h_flag true {v['n_h_flag_true']}, live but unflagged "
                     f"{v['n_live_but_unflagged']}, terminal {v['n_terminal']}, h* undefined {v['n_hstar_undefined']}")
    am2 = report.get("j12_am2_divergence") or {}
    if am2:
        lines += ["", "## Replay divergence (J12 Amendment 2)", "",
                  f"Divergent keys: {am2['n_divergent_total']} (cap {am2['cap']} per D). "
                  + ", ".join(f"{a} {v['n_divergent']}" + (f" ({', '.join(v['keys'])})" if v["keys"] else "")
                              for a, v in am2["per_arm"].items()) + "."]
        cond = am2.get("resumption_condition") or {}
        if am2.get("refill_confirmed_by_operator"):
            lines.append("Crash-only resumption confirmed by the operator (--divergent-refill-confirmed).")
        elif cond.get("required"):
            lines.append(f"INCOMPLETE until confirmed: {cond['rule']}. How to confirm: {cond['how_to_confirm']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J12 prefix-depth test (docs/prereg_j12_depth_test_20260924.md).")
    p.add_argument("--split", required=True, choices=["dev", "test_normal", "test_challenge"])
    p.add_argument("--confirm-heldout-test-split", dest="confirm_heldout_test_split", action="store_true")
    p.add_argument("--plumbing-check", action="store_true", help="dev only, over *_dryrun campaigns only")
    p.add_argument("--seeds", default=j10.A1_DEFAULT_SEEDS, help="registered seeds (1,2)")
    p.add_argument("--expected-n-tasks", type=int, default=None, help="default: dev 57, test_normal 168")
    p.add_argument("--arm", action="append", required=True, metavar="LABEL=DIR",
                   help=(f"repeatable; labels {sorted(J12_ARMS)} and {J12_PLAN_SOURCE_ARM} (J10 arm 3: required on "
                         "test_normal, optional on dev); on test_normal each DIR is named by its registered campaign id"))
    p.add_argument("--bootstrap-seed", type=int, default=j10.A1_BOOTSTRAP_SEED)
    p.add_argument("--n-boot", type=int, default=j10.A1_BOOTSTRAP_N)
    p.add_argument("--divergent-refill-confirmed", dest="divergent_refill_confirmed", action="store_true",
                   help=("the operator confirms that every arm with a replay_divergence key had a crash-only "
                         "resumption run after the crash first appeared (A1 Amendment 5 §B.1); without it a "
                         "test_normal read with a divergent key is INCOMPLETE"))
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
        n_boot=args.n_boot, bootstrap_seed=args.bootstrap_seed, out_path=out,
        divergent_refill_confirmed=args.divergent_refill_confirmed)
    text = json.dumps(report, indent=2, default=str) + "\n"
    print(text, end="")
    if out is not None and code != 2:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        out.with_suffix(".md").write_text(render_markdown(report, out.name), encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
