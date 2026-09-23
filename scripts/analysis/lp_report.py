#!/usr/bin/env python
"""LP: the registered analysis of the channel result across planner strength (LP-1, LP-2).

Computes ``docs/prereg_lp_planner_strength_20260923.md`` §3-§4 so that every reading is
mechanical when the LP arms land: the informativeness gate, L1-L5 with Holm within each
planner, POOL-04, the sign-flip sensitivity, the §4 overall claim, and the descriptive block
(Δ_p against luna, planner strength, the plan-only arm F_p). It chooses nothing. Every
statistic comes from the J10 A1 machinery in ``scripts/analysis/j10_report.py`` -- the same
cluster bootstrap, bootstrap p, Holm step-down, POOL-04 re-check and sign-flip wrapper that
B2 (``scripts/analysis/b2_decomposition.py``) imports -- so LP cannot drift from how A1 and
B2 read an interval.

Campaign ids of the LP arms are read from each arm's config (``campaign_id``), never typed
here. The reference arms (E and luna's) are the campaigns the registration names.

Exit codes
  0  the gate and L1-L5 are complete for every analysed planner; readings are drawn
  1  some gate or L contrast lacks 114 non-crashed pairs: it is reported INCOMPLETE with
     counts and no reading is drawn from it
  2  protocol error: a (task_id, seed) key twice within one campaign, a held-out path, a
     VOID / unreadable / non-LP campaign_id in a config, or an output directory under
     /scratch or inside the results tree
  3  a registered campaign directory does not exist yet (the report names each one)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Imported as a module (not name by name) so a test can monkeypatch the bootstrap in ONE
# place and have the primary interval and the POOL-04 re-draws both see it (as B2 does).
from scripts.analysis import j10_report as j10  # noqa: E402

PREREG = "docs/prereg_lp_planner_strength_20260923.md"
RESULTS_ROOT = j10.RAW_RESULTS_ROOT
OUT_DIR = REPO_ROOT / "campaign" / "results"
OUT_STEM = "lp_planner_strength"
# Nothing under /scratch is ever written: it holds the raw episodes this script reads.
FORBIDDEN_OUT_ROOTS = (Path("/scratch"),)

SEEDS: tuple[int, ...] = (1, 2)  # §2 [prereg:49-50]: seeds 1-2, the 57 dev tasks
N_TASKS = 57
EXPECTED_PAIRS = N_TASKS * len(SEEDS)  # 114
N_BOOT = 10_000
BOOTSTRAP_SEED = 20260924
ALPHA = 0.05
FIELD = "goal_pass_rate"
NI_MARGIN_PP = 7.00  # L4 [prereg:95]: the J9 non-inferiority margin
# A mean of paired float differences can land at +-1e-17 when the exact mean is zero; the
# gate's "point estimate <= 0" is read on the point rounded past that noise.
GATE_ZERO_TOL = 1e-9

PLANNERS: tuple[str, ...] = ("P8", "P27")
PLANNER_INFO: dict[str, dict[str, Any]] = {
    "P8": {"lp": 1, "model": "Qwen/Qwen3-8B"},
    "P27": {"lp": 2, "model": "Qwen/Qwen3.8-27B-FP8"},
}
_CEILING_CONFIG = {
    "P8": "configs/lp1_planner_alone_cap81_qwen8b.yaml",
    "P27": "configs/lp2_planner_alone_cap81_qwen38_27b.yaml",
}
PLANNER_ARM_ORDER: tuple[str, ...] = (
    "C", "T", "A", "A1", "F",
    "M_bplus_6", "M_bplus_9", "M_bplus_11", "M_zs_6", "M_zs_9", "M_zs_11",
)


def _arm_configs(planner: str) -> dict[str, str]:
    """§2 table [prereg:52-59]: the config of every arm of one local planner."""
    n = PLANNER_INFO[planner]["lp"]
    cfg = {
        "C": _CEILING_CONFIG[planner],
        "T": f"configs/lp{n}_hj12_takeover_fixed_k_10.yaml",
        "A": f"configs/lp{n}_hj12_advise_fixed_k_10_fullctx.yaml",
        "A1": f"configs/lp{n}_hj13_advise_fixed_k_1_fullctx.yaml",
        "F": f"configs/lp{n}_hj8_sft_plan_bplus.yaml",
    }
    for receiver in ("bplus", "zs"):
        for m in (6, 9, 11):
            cfg[f"M_{receiver}_{m}"] = f"configs/lp{n}_prefix_{receiver}_m{m}.yaml"
    return cfg


ARM_CONFIGS: dict[str, dict[str, str]] = {p: _arm_configs(p) for p in PLANNERS}

# Named by the registration itself: E [prereg:98-99], the CHAN-C1-02 pair [prereg:62] and
# luna's cap-81 ceiling [prereg:64] (planner strength is "each ceiling's mean" [prereg:119]).
REFERENCE_CAMPAIGNS: dict[str, str] = {
    "E": "hj8_executor_alone_bplus_20260919",
    "T_luna": "hj12_takeover_fixed_k_10_20260923",
    "A_luna": "hj12_advise_fixed_k_10_fullctx_20260923",
    "C_luna": "hj13_planner_alone_cap81_20260923",
}
REFERENCE_ORDER: tuple[str, ...] = tuple(REFERENCE_CAMPAIGNS)
# [prereg:15-16]: "VOID ... It is never analysed."
_VOID_LP1_CEILING = "lp1_planner_alone_cap81_qwen8b_20260923"
# The first LP prefix-replay ids. They ran under scripts/pbs/hj12_prefix.pbs, which serves no
# planner, so every executor ask prefix_handoff honours hit a closed port and crashed (PBS
# 25725094). Executors ask when stuck, so those crashes are outcome-linked; the arms are re-run
# whole under <stem>_v2_20260923 (scripts/setup/make_lp_configs.py) and these ids are never analysed.
_VOID_LP_PREFIX = tuple(
    f"lp{n}_prefix_{receiver}_m{m}_20260923" for n in (1, 2) for receiver in ("zs", "bplus") for m in (6, 9, 11)
)
VOID_CAMPAIGNS: tuple[str, ...] = (_VOID_LP1_CEILING, *_VOID_LP_PREFIX)


def _void_reason(cid: str) -> str:
    if cid == _VOID_LP1_CEILING:
        return f"[{PREREG}:15-16]"
    return "(run with no planner server; honoured executor asks crashed on a closed port, PBS 25725094)"

ARM_NAMES = {
    "C": "planner alone, cap 81 (ceiling)",
    "T": "takeover at k = 10",
    "A": "prose advice at k = 10, full context",
    "A1": "prose advice at every step, full context",
    "F": "plan only, tailored receiver (descriptive)",
    "M_bplus_6": "prefix m = 6, tailored receiver",
    "M_bplus_9": "prefix m = 9, tailored receiver (no registered contrast)",
    "M_bplus_11": "prefix m = 11, tailored receiver",
    "M_zs_6": "prefix m = 6, untailored receiver",
    "M_zs_9": "prefix m = 9, untailored receiver (no registered contrast)",
    "M_zs_11": "prefix m = 11, untailored receiver",
    "E": "tailored executor alone (gate reference)",
    "T_luna": "luna takeover at k = 10 (Δ_p reference)",
    "A_luna": "luna advice at k = 10, full context (Δ_p reference)",
    "C_luna": "luna planner alone, cap 81 (planner-strength reference)",
}

# ---- rules ----------------------------------------------------------------------
# L1 is read three ways, so both bounds are decision-bearing: A1's P6 rule, reused.
THREE_WAY = "positive_excludes_zero_with_reversal"
# L3 / L5 are read only as "lower > 0": A1's lower-bound rule, reused.
LOWER = "lower_bound_above_threshold"
# L2 (upper < 0) and L4 (upper < +7.00) are read on the upper bound alone. A1 has no rule
# whose only decision-bearing bound is the upper one, and j10.a1_pool04 looks rules up by
# name, so one is added -- additively, under an LP-prefixed name -- to reuse A1's POOL-04
# window arithmetic, seven re-draws and 200k bound unchanged.
UPPER = "lp_upper_bound_below_threshold"


def _rule_upper_bound_below(point: float, lo_above: bool, hi_below: bool) -> str:
    return "supported" if hi_below else "not_supported"


j10.A1_RULES.setdefault(UPPER, {
    "decide": _rule_upper_bound_below,
    "bounds": ("hi",),
    "direction": "less",
    "text": "supported if CI hi < t; else not_supported",
})

POOL04_VERDICT_NAMES = {
    THREE_WAY: {
        "supported": "excludes_zero_positive",
        "reversed": "excludes_zero_negative",
        "not_supported": "includes_zero",
    },
    LOWER: {"supported": "lower_above_threshold", "not_supported": "lower_not_above_threshold"},
    UPPER: {"supported": "upper_below_threshold", "not_supported": "upper_not_below_threshold"},
}

GATE: dict[str, Any] = {
    "id": "gate", "left": "C", "right": "E",
    "rule": "point estimate of C_p - E <= 0 => too_weak; > 0 => passes",
    "citation": f"{PREREG}:98-101",
}

# §4 [prereg:90-96] with §3's p-value and reading rules [prereg:83-86].
CONTRASTS: tuple[dict[str, Any], ...] = (
    {"id": "L1", "left": "T", "right": "A", "predicted": "> 0", "kind": "three_way",
     "threshold_pp": 0.0, "p_direction": "two-sided", "signflip_alternative": "two-sided",
     "pool04_rule": THREE_WAY,
     "claim": "action beats advice at a matched trigger",
     "rule_text": ("replicates: lo > 0 and Holm p <= .05; reversed: hi < 0 and Holm p <= .05; "
                   "fails_to_replicate: unadjusted interval includes 0; else not_resolved"),
     "p_text": "two-sided: 2 x min(share of draws <= 0, share >= 0)",
     "citation": f"{PREREG}:92,104-106"},
    {"id": "L2", "left": "A1", "right": "M_bplus_11", "predicted": "< 0", "kind": "upper_below",
     "threshold_pp": 0.0, "p_direction": "less", "signflip_alternative": "less",
     "pool04_rule": UPPER,
     "claim": "advice at every step does not reach the 11-action prefix",
     "rule_text": "supported iff hi < 0 and Holm p <= .05",
     "p_text": "2 x share of draws >= 0",
     "citation": f"{PREREG}:93"},
    {"id": "L3", "left": "M_bplus_11", "right": "M_bplus_6", "predicted": "> 0", "kind": "lower_above",
     "threshold_pp": 0.0, "p_direction": "greater", "signflip_alternative": "greater",
     "pool04_rule": LOWER,
     "claim": "depth span, tailored receiver",
     "rule_text": "supported iff lo > 0 and Holm p <= .05",
     "p_text": "2 x share of draws <= 0",
     "citation": f"{PREREG}:94"},
    {"id": "L4", "left": "C", "right": "M_bplus_11", "predicted": "upper bound < +7.00 pp",
     "kind": "upper_below", "threshold_pp": NI_MARGIN_PP, "p_direction": "less",
     "signflip_alternative": "less", "pool04_rule": UPPER,
     "claim": "non-inferiority of the 11-action prefix to the ceiling at the J9 margin",
     "rule_text": "supported iff hi < +7.00 pp and Holm p <= .05",
     "p_text": "2 x share of draws >= +7.00 pp",
     "citation": f"{PREREG}:95"},
    {"id": "L5", "left": "M_zs_11", "right": "M_zs_6", "predicted": "> 0", "kind": "lower_above",
     "threshold_pp": 0.0, "p_direction": "greater", "signflip_alternative": "greater",
     "pool04_rule": LOWER,
     "claim": "depth span, untailored receiver",
     "rule_text": "supported iff lo > 0 and Holm p <= .05",
     "p_text": "2 x share of draws <= 0",
     "citation": f"{PREREG}:96"},
)
CONTRAST_BY_ID = {c["id"]: c for c in CONTRASTS}
L_IDS: tuple[str, ...] = tuple(c["id"] for c in CONTRASTS)

NONE_GATE = "none (planner failed the informativeness gate)"
NONE_GATE_UNEVALUABLE = "none (informativeness gate not evaluable: C_p - E incomplete)"
NONE_FAMILY = "none (Holm family incomplete)"
INCOMPLETE = "incomplete"
ON_BOUNDARY = "on_the_boundary"
L1_READINGS = ("replicates", "fails_to_replicate", "reversed", "not_resolved")

CLAIM_TEXT = {
    "generalises": "The channel claim generalises across planner strength: L1 replicates for both local planners.",
    "bounded": "The channel claim is bounded: L1 replicates for exactly one local planner.",
    "luna_specific": ("The channel claim is luna-specific: L1 replicates for neither local planner. "
                      "Reported as the generality result, not as a failure to be explained away."),
    "not_registered_case": "No registered overall claim applies.",
}

AMBIGUITIES: list[dict[str, str]] = [
    {"id": "holm_family_incomplete",
     "what": ("§3 makes an incomplete contrast yield no reading, and Holm runs across L1-L5 (m = 5); "
              "it does not say what the other four read when one member is incomplete."),
     "script_behaviour": ("B2's convention: Holm is computed only when all five are complete, because a "
                          "smaller family would change every adjusted p. Until then every complete L reads "
                          f"{NONE_FAMILY!r} and the incomplete one reads {INCOMPLETE!r}.")},
    {"id": "gate_incomplete",
     "what": "§4 defines the gate by the point estimate of C_p - E but not what happens when C_p or E lacks 114 pairs.",
     "script_behaviour": ("The gate is a paired contrast and follows §3: below 114 non-crashed pairs it is "
                          f"INCOMPLETE, every L reads {NONE_GATE_UNEVALUABLE!r}, and the planner does not "
                          "count as passing for the overall claim.")},
    {"id": "gate_estimator",
     "what": "'C_p - E has a point estimate <= 0' does not name the estimator or say whether POOL-04 applies.",
     "script_behaviour": ("The paired mean over the 114 (task_id, seed) keys (reported with its scenario and "
                          "task intervals). The decision is on a point, not a bound, so POOL-04 does not apply. "
                          f"A point within {GATE_ZERO_TOL:g} of zero (float noise) counts as zero.")},
    {"id": "point_on_predicted_side",
     "what": "'L1 replicates: > 0 with the interval excluding zero' names a sign and an interval.",
     "script_behaviour": ("As B2: every 'supported' / 'replicates' / 'reversed' also needs the point estimate on "
                          "the predicted side of the threshold. With a percentile interval this binds only in "
                          "a degenerate case.")},
    {"id": "l1_not_resolved",
     "what": ("An L1 interval can exclude zero while its Holm p exceeds .05; §4 names no reading for it, "
              "and §4's overall claim counts only 'replicates'."),
     "script_behaviour": ("'not_resolved'. For the overall claim it is a reading that does not replicate "
                          "(as are fails_to_replicate and reversed).")},
    {"id": "overall_claim_scope",
     "what": ("§4's claims are stated for 'both local planners that pass the gate'; fewer than two passing, "
              "or an unread L1, is not covered."),
     "script_behaviour": ("'not_registered_case' with the reason whenever a planner is not analysed "
                          "(--planners), fewer than two pass the gate, or a passing planner's L1 is incomplete, "
                          "on_the_boundary or unread. L1 of a planner that fails the gate is never consulted.")},
    {"id": "pool04_decision_bearing_bounds",
     "what": "POOL-04 re-checks 'any decision-bearing bound' without listing them.",
     "script_behaviour": ("L1: both bounds against 0 (three-way, A1's P6 rule). L2: the upper bound against 0. "
                          "L3, L5: the lower bound against 0. L4: the upper bound against +7.00 pp. The seven "
                          "re-draws are classified on the unadjusted interval, as j10.a1_pool04 does for A1 and "
                          "B2. The gate has no bound.")},
    {"id": "signflip_direction",
     "what": "§3 names the sign-flip p as sensitivity without a side per contrast.",
     "script_behaviour": ("The contrast's own p side, at its own threshold: L1 two-sided at 0; L2 'less' at 0; "
                          "L3, L5 'greater' at 0; L4 'less' at +7.00 pp; the gate 'greater' at 0 (informational). "
                          "19 scenario clusters: exact enumeration of 2^19 patterns.")},
    {"id": "planner_strength_luna",
     "what": "'Planner strength ... is indexed by each ceiling's mean goal_pass' [prereg:119].",
     "script_behaviour": ("C_P8, C_P27 and luna's ceiling hj13_planner_alone_cap81_20260923 [prereg:64], each "
                          "on the 57 x {1, 2} matrix. Descriptive: no direction, no verdict.")},
    {"id": "delta_scope",
     "what": "Δ_p is 'on the shared (task_id, seed) keys' but §3's completeness rule is stated for contrasts.",
     "script_behaviour": ("B2's exploratory convention: Δ_p is estimated only when T_p, A_p, T_luna and A_luna "
                          "are each complete and share all 114 keys; otherwise counts only.")},
    {"id": "m9_arms",
     "what": "The m = 9 prefix arms are registered [prereg:59] but no contrast reads them.",
     "script_behaviour": "They are loaded and inventoried (counts, means) only.",
     },
    {"id": "missing_goal_pass_rate",
     "what": "The registration does not say how a non-crashed episode without goal_pass_rate counts.",
     "script_behaviour": ("As B2: it is never coerced to 0; the pair is dropped and counted, which leaves the "
                          "contrast below 114 and so INCOMPLETE.")},
    {"id": "duplicate_within_one_campaign",
     "what": "The registration is silent on a (task_id, seed) key present twice inside one campaign.",
     "script_behaviour": "As B2: a protocol error (exit 2), since keeping either copy would be a choice."},
    {"id": "analysis_code",
     "what": "§5 names 'j8_frontier.py / the pooled-contrast code with the settings in §3'.",
     "script_behaviour": ("The J10 A1 functions B2 uses; j10.cluster_bootstrap_means is draw-for-draw "
                          "j8_frontier.paired_diff_scenario's algorithm (its docstring), at §3's settings.")},
]


# ---- loading ----------------------------------------------------------------------
class ProtocolError(ValueError):
    """A registration the script refuses to read (exit 2)."""


def resolve_campaigns(planners: tuple[str, ...] = PLANNERS,
                      repo_root: Path = REPO_ROOT) -> dict[str, dict[str, dict[str, str]]]:
    """{planner: {arm code: {config, campaign}}}, the campaign read from each config's campaign_id."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - yaml ships with the project env
        raise ProtocolError(f"PyYAML is needed to read campaign_id from the configs: {exc}") from exc
    out: dict[str, dict[str, dict[str, str]]] = {}
    seen: dict[str, str] = {}
    for planner in planners:
        n = PLANNER_INFO[planner]["lp"]
        arms: dict[str, dict[str, str]] = {}
        for code in PLANNER_ARM_ORDER:
            rel = ARM_CONFIGS[planner][code]
            try:
                data = yaml.safe_load((repo_root / rel).read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as exc:
                raise ProtocolError(f"{rel}: cannot read campaign_id ({type(exc).__name__}: {exc})") from exc
            cid = data.get("campaign_id") if isinstance(data, dict) else None
            if not isinstance(cid, str) or not cid.strip():
                raise ProtocolError(f"{rel}: no campaign_id")
            if cid in VOID_CAMPAIGNS:
                raise ProtocolError(f"{rel}: campaign_id {cid!r} is VOID {_void_reason(cid)} and is never analysed")
            if not cid.startswith(f"lp{n}_"):
                raise ProtocolError(f"{rel}: campaign_id {cid!r} is not an LP-{n} campaign")
            if cid in seen:
                raise ProtocolError(f"{rel}: campaign_id {cid!r} is also the campaign of {seen[cid]}")
            seen[cid] = rel
            arms[code] = {"config": rel, "campaign": cid}
        out[planner] = arms
    return out


def load_campaign(code: str, directory: Path) -> dict[str, Any]:
    """One arm = one campaign, shaped for j10.a1_arm_episodes; a key twice is an error (as B2)."""
    loaded = j10.load_arm_tree(directory)
    if loaded["duplicates"]:
        raise ProtocolError(
            f"arm {code}: campaign {directory.name} holds a (task_id, seed) key twice "
            f"({loaded['duplicates'][:3]}); keeping either copy would be a choice"
        )
    present = not loaded["root_missing"]
    loaded["campaign"] = {
        "campaign": directory.name,
        "path": str(directory),
        "present": present,
        "n_results": len(loaded["runs"]),
        "by_seed": dict(sorted(Counter(str(s) for _t, s in loaded["runs"]).items())),
        "systems": sorted(loaded["systems"]),
        "n_empty_files": len(loaded["empty_files"]),
        "n_unreadable": len(loaded["unreadable"]),
        "split_provenance": j10.a1_split_provenance(directory) if present else {},
    }
    return loaded


# ---- one contrast -------------------------------------------------------------------
def _translate_pool04(pool: dict[str, Any], rule: str) -> dict[str, Any]:
    """Rename A1's verdict words ('supported', 'reversed', ...) into what they mean for LP (B2's helper)."""
    names = POOL04_VERDICT_NAMES[rule]
    out = dict(pool)
    if "bounds_by_seed" in out:
        out["bounds_by_seed"] = [dict(row, verdict=names[row["verdict"]]) for row in out["bounds_by_seed"]]
        out["verdicts_by_seed"] = sorted({names[v] for v in out["verdicts_by_seed"]})
    if isinstance(out.get("bound_200k"), dict):
        out["bound_200k"] = dict(out["bound_200k"], verdict=names[out["bound_200k"]["verdict"]])
    out["on_boundary"] = bool(out["fired"] and not out.get("stable", True))
    out["status"] = "on_boundary" if out["on_boundary"] else ("stable" if out["fired"] else "not_fired")
    return out


def _arm_count(code: str, arm: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": code,
        "complete": arm["complete"],
        "n_scored": arm["n_scored"],
        "n_expected": EXPECTED_PAIRS,
        "n_crash": arm["n_crash"],
        "n_missing": arm["n_missing"],
    }


def _paired(codes: tuple[str, ...], arms: dict[str, dict[str, Any]],
            series: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    counts = [_arm_count(c, arms[c]) for c in codes]
    problems = [
        f"{c['arm']} {c['n_scored']}/{EXPECTED_PAIRS} non-crashed "
        f"(crash {c['n_crash']}, missing {c['n_missing']})"
        for c in counts if not c["complete"]
    ]
    if len(series["diffs"]) != EXPECTED_PAIRS:
        problems.append(f"{len(series['diffs'])}/{EXPECTED_PAIRS} pairs scored on all sides")
    return counts, problems


def _tgc(left: dict[str, Any], right: dict[str, Any], *, n_boot: int, seed: int) -> dict[str, Any]:
    """TGC, scored as j10 scores it (score_tgc inside a1_arm_episodes): reported, not decision-bearing."""
    cmp = j10._public_contrast(j10.a1_contrast(left["episodes"], right["episodes"], "tgc",
                                               n_boot=n_boot, seed=seed))
    return {"label": "secondary: reported, not decision-bearing (prereg §3)",
            "point_pp": cmp["scenario"]["diff_pp"], **cmp}


def evaluate_gate(arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """§4's informativeness gate: C_p - E, read on its point estimate."""
    left, right = arms[GATE["left"]], arms[GATE["right"]]
    series = j10.a1_paired_series(left["episodes"], right["episodes"], FIELD)
    counts, problems = _paired((GATE["left"], GATE["right"]), arms, series)
    out: dict[str, Any] = {
        "id": "gate",
        "definition": "C - E",
        "left": GATE["left"],
        "right": GATE["right"],
        "rule": GATE["rule"],
        "citation": GATE["citation"],
        "metric": "goal_pass",
        "field": FIELD,
        "n_pairs": len(series["diffs"]),
        "n_expected": EXPECTED_PAIRS,
        "n_dropped_missing_field": series["n_dropped_missing_field"],
        "counts": counts,
    }
    if problems:
        out.update(status="INCOMPLETE", reason="; ".join(problems), verdict="incomplete",
                   why="C_p - E lacks 114 non-crashed pairs; the gate is not evaluable (§3)")
        return out
    cmp = j10.a1_contrast(left["episodes"], right["episodes"], FIELD, n_boot=n_boot, seed=seed)
    primary = cmp["scenario"]
    point = float(primary["point"])
    passes = point > GATE_ZERO_TOL
    out.update(
        status="COMPLETE",
        point_pp=primary["diff_pp"],
        scenario=j10._public(primary),
        task=j10._public(cmp["task"]),
        verdict="passes" if passes else "too_weak",
        why=(f"point estimate {point * 100:+.2f} pp "
             + ("> 0: the planner is informative" if passes
                else "<= 0: too weak to test the channel; L1-L5 are reported and no reading is drawn")),
        signflip=j10.a1_permutation(cmp["_series"], 0.0, "greater"),
        tgc_secondary=_tgc(left, right, n_boot=n_boot, seed=seed),
    )
    return out


def evaluate_contrast(
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(public block, decision record). Incomplete: counts only (§3)."""
    left, right = arms[spec["left"]], arms[spec["right"]]
    series = j10.a1_paired_series(left["episodes"], right["episodes"], FIELD)
    counts, problems = _paired((spec["left"], spec["right"]), arms, series)
    out: dict[str, Any] = {
        "id": spec["id"],
        "definition": f"{spec['left']} - {spec['right']}",
        "left": spec["left"],
        "right": spec["right"],
        "claim": spec["claim"],
        "predicted": spec["predicted"],
        "threshold_pp": spec["threshold_pp"],
        "rule_text": spec["rule_text"],
        "citation": spec["citation"],
        "metric": "goal_pass",
        "field": FIELD,
        "n_pairs": len(series["diffs"]),
        "n_expected": EXPECTED_PAIRS,
        "n_dropped_missing_field": series["n_dropped_missing_field"],
        "counts": counts,
    }
    if problems:
        out.update(status="INCOMPLETE", reason="; ".join(problems))
        return out, {"status": "INCOMPLETE"}

    cmp = j10.a1_contrast(left["episodes"], right["episodes"], FIELD, n_boot=n_boot, seed=seed)
    primary = cmp["scenario"]
    t = float(spec["threshold_pp"]) / 100.0
    p_raw = j10.bootstrap_pvalue(primary["_means"], t, spec["p_direction"])
    pool = _translate_pool04(
        j10.a1_pool04({"rule": spec["pool04_rule"], "threshold_pp": spec["threshold_pp"]},
                      cmp["_series"], primary, n_boot=n_boot, seed=seed),
        spec["pool04_rule"],
    )
    out.update(
        status="COMPLETE",
        point_pp=primary["diff_pp"],
        scenario=j10._public(primary),
        task=j10._public(cmp["task"]),
        p_raw=p_raw,
        p_raw_direction=spec["p_direction"],
        p_raw_text=spec["p_text"],
        pool04=pool,
        signflip=j10.a1_permutation(cmp["_series"], t, spec["signflip_alternative"]),
        tgc_secondary=_tgc(left, right, n_boot=n_boot, seed=seed),
    )
    record = {
        "status": "COMPLETE",
        "point": primary["point"],
        "lo": primary["lo"],
        "hi": primary["hi"],
        "p_raw": p_raw,
        "boundary": pool["on_boundary"],
    }
    return out, record


def evaluate_delta(arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """Descriptive Δ_p = (T_p - A_p) - (T_luna - A_luna) on the shared keys [prereg:117-118]."""
    codes = ("T", "A", "T_luna", "A_luna")
    series = j10.a1_did_series([arms[c]["episodes"] for c in codes], FIELD)
    counts, problems = _paired(codes, arms, series)
    out: dict[str, Any] = {
        "label": "DESCRIPTIVE: no direction, no verdict (prereg:116-122)",
        "definition": "(T_p - A_p) - (T_luna - A_luna)",
        "unit": "shared (task_id, seed) keys",
        "n_pairs": len(series["diffs"]),
        "n_shared": series["n_shared"],
        "n_expected": EXPECTED_PAIRS,
        "n_dropped_missing_field": series["n_dropped_missing_field"],
        "counts": counts,
    }
    if problems:
        out.update(status="INCOMPLETE", reason="; ".join(problems))
        return out
    scen = j10.a1_interval(series, "scenario", n_boot=n_boot, seed=seed)
    task = j10.a1_interval(series, "task", n_boot=n_boot, seed=seed)
    out.update(status="COMPLETE", point_pp=scen["diff_pp"], scenario=j10._public(scen), task=j10._public(task))
    return out


# ---- the registered reading ---------------------------------------------------------
def _pp(x: float) -> str:
    return f"{x * 100:+.2f}"


def rule_reading(contrast_id: str, rec: dict[str, Any], p_holm: float,
                 alpha: float = ALPHA) -> tuple[str, str]:
    """The registered reading of one complete contrast, given its Holm-adjusted p."""
    spec = CONTRAST_BY_ID[contrast_id]
    t = float(spec["threshold_pp"]) / 100.0
    lo, hi, point = float(rec["lo"]), float(rec["hi"]), float(rec["point"])
    ci = f"scenario CI [{_pp(lo)}, {_pp(hi)}] pp, point {_pp(point)} pp"
    holm = f"Holm p = {p_holm:.4g}"
    holm_ok = p_holm <= alpha
    if rec.get("boundary"):
        return ON_BOUNDARY, ("POOL-04: the verdict differs across the seven bootstrap seeds, so it is on "
                             "the boundary, never resolved (§3)")
    if spec["kind"] == "three_way":
        if lo > 0 and point > 0 and holm_ok:
            return "replicates", f"{ci}: lower > 0 and {holm} <= {alpha}"
        if hi < 0 and point < 0 and holm_ok:
            return "reversed", f"{ci}: upper < 0 and {holm} <= {alpha}; a primary finding"
        if lo <= 0.0 <= hi:
            return "fails_to_replicate", f"unadjusted {ci} includes zero"
        return "not_resolved", f"{ci} excludes zero but {holm} > {alpha} (or the point disagrees in sign)"
    if spec["kind"] == "lower_above":
        if lo > t and point > t and holm_ok:
            return "supported", f"{ci}: lower > {t * 100:+.2f} pp and {holm} <= {alpha}"
        if lo > t:
            return "not_supported", f"{ci}: lower > {t * 100:+.2f} pp but {holm} > {alpha}"
        return "not_supported", f"{ci}: lower <= {t * 100:+.2f} pp"
    if spec["kind"] == "upper_below":
        if hi < t and point < t and holm_ok:
            return "supported", f"{ci}: upper < {t * 100:+.2f} pp and {holm} <= {alpha}"
        if hi < t:
            return "not_supported", f"{ci}: upper < {t * 100:+.2f} pp but {holm} > {alpha}"
        return "not_supported", f"{ci}: upper >= {t * 100:+.2f} pp"
    raise ValueError(f"unknown kind {spec['kind']!r}")


def read_planner(gate: dict[str, Any], records: dict[str, dict[str, Any]],
                 alpha: float = ALPHA) -> dict[str, Any]:
    """Holm across L1-L5 of ONE planner, then each L's reading.

    Pure over the gate verdict and per-contrast records {status, point, lo, hi, p_raw,
    boundary} (fractions), so the multiplicity logic is testable without a bootstrap.
    Holm is per planner by construction: nothing from another planner enters (§3).
    """
    verdict = gate.get("verdict")
    incomplete = [c for c in L_IDS if (records.get(c) or {}).get("status") != "COMPLETE"]
    holm: Optional[dict[str, Any]] = None
    if not incomplete:
        raw = [float(records[c]["p_raw"]) for c in L_IDS]
        adjusted = j10.holm_adjust(raw)
        holm = {
            "method": "Holm step-down",
            "alpha": alpha,
            "family": list(L_IDS),
            "m": len(L_IDS),
            "scope": "within this planner; no correction across planners (prereg:81-82)",
            "p": {c: {"p_raw": r, "p_holm": a, "rejects_at_alpha": bool(a <= alpha)}
                  for c, r, a in zip(L_IDS, raw, adjusted)},
        }
    readings: dict[str, dict[str, str]] = {}
    for c in L_IDS:
        rec = records.get(c) or {}
        if verdict == "too_weak":
            readings[c] = {"reading": NONE_GATE,
                           "why": "C_p - E point estimate <= 0: L1-L5 are reported and no reading is drawn (§4)"}
        elif verdict != "passes":
            readings[c] = {"reading": NONE_GATE_UNEVALUABLE,
                           "why": "the gate is evaluated first and C_p - E lacks 114 non-crashed pairs"}
        elif rec.get("status") != "COMPLETE":
            readings[c] = {"reading": INCOMPLETE,
                           "why": "its arms lack 114 non-crashed pairs; no reading is drawn from it (§3)"}
        elif holm is None:
            readings[c] = {"reading": NONE_FAMILY,
                           "why": (f"{', '.join(incomplete)} incomplete: Holm (m = 5) is not computed on a "
                                   "partial family")}
        else:
            reading, why = rule_reading(c, rec, holm["p"][c]["p_holm"], alpha)
            readings[c] = {"reading": reading, "why": why}
    return {"holm": holm, "readings": readings, "incomplete_contrasts": incomplete}


def overall_claim(summary: dict[str, dict[str, str]]) -> dict[str, Any]:
    """§4's overall claim from L1 among planners that pass the gate [prereg:109-114].

    `summary`: {planner: {"gate": verdict, "L1": reading}} for the analysed planners.
    """
    base: dict[str, Any] = {"citation": f"{PREREG}:109-114",
                            "computed_from": "L1 among local planners that pass the gate"}

    def not_registered(reason: str) -> dict[str, Any]:
        return {**base, "claim": "not_registered_case", "which": None, "reason": reason,
                "text": CLAIM_TEXT["not_registered_case"]}

    absent = [p for p in PLANNERS if p not in summary]
    if absent:
        return not_registered(f"{', '.join(absent)} not analysed (--planners); the claim is registered "
                              "over both local planners")
    gates = {p: summary[p]["gate"] for p in PLANNERS}
    passing = [p for p in PLANNERS if gates[p] == "passes"]
    if len(passing) < 2:
        return not_registered("fewer than two planners pass the informativeness gate ("
                              + ", ".join(f"{p}: {gates[p]}" for p in PLANNERS) + ")")
    l1 = {p: summary[p]["L1"] for p in passing}
    unread = {p: r for p, r in l1.items() if r not in L1_READINGS}
    if unread:
        return not_registered("L1 has no registered reading for "
                              + ", ".join(f"{p} ({r})" for p, r in unread.items()))
    replicates = [p for p in passing if l1[p] == "replicates"]
    if len(replicates) == 2:
        claim, which = "generalises", None
    elif len(replicates) == 1:
        claim, which = "bounded", replicates[0]
    else:
        claim, which = "luna_specific", None
    text = CLAIM_TEXT[claim] + (f" It replicates for {which}." if which else "")
    return {**base, "claim": claim, "which": which, "reason": None, "text": text,
            "l1_readings": l1}


# ---- report -------------------------------------------------------------------------
def _arm_summary(code: str, arm: dict[str, Any], blob: dict[str, Any]) -> dict[str, Any]:
    return {"name": ARM_NAMES[code], **{k: v for k, v in arm.items() if k != "episodes"},
            "campaign": blob["campaign"]}


def _mean_block(arm: dict[str, Any], campaign: str) -> dict[str, Any]:
    return {"campaign": campaign, "goal_pass_mean": arm["goal_pass_mean"], "n_scored": arm["n_scored"],
            "n_expected": arm["n_expected"], "n_goal_pass_missing": arm["n_goal_pass_missing"],
            "complete": arm["complete"]}


def _planner_block(
    planner: str,
    campaigns: dict[str, dict[str, str]],
    own: dict[str, dict[str, Any]],
    reference: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    every = {**own, **reference}
    tasks = j10.discover_tasks(every, list(SEEDS))
    reasons: list[str] = []
    warnings: list[str] = []
    if len(tasks) != N_TASKS:
        reasons.append(f"task_count_is_{len(tasks)}_expected_{N_TASKS}")
    for code, blob in every.items():
        camp = blob["campaign"]
        wrong = {k: v for k, v in camp["split_provenance"].items() if k not in {"dev", "unrecorded"}}
        if wrong:
            reasons.append(f"split_provenance_not_dev:{code}:{camp['campaign']}={wrong}")
        if len(blob["systems"]) > 1:
            warnings.append(f"arm {code} carries system labels {sorted(blob['systems'])}")
    arms = {code: j10.a1_arm_episodes(code, every[code], tasks, list(SEEDS)) for code in every}
    for arm in arms.values():
        # A matrix of the wrong size or from the wrong split cannot be complete at any count.
        arm["complete"] = bool(arm["complete"] and not reasons and arm["n_expected"] == EXPECTED_PAIRS)

    gate = evaluate_gate(arms, n_boot=n_boot, seed=seed)
    contrasts: dict[str, dict[str, Any]] = {}
    records: dict[str, dict[str, Any]] = {}
    for spec in CONTRASTS:
        contrasts[spec["id"]], records[spec["id"]] = evaluate_contrast(spec, arms, n_boot=n_boot, seed=seed)
    read = read_planner(gate, records)
    for c in L_IDS:
        contrasts[c]["reading"] = read["readings"][c]["reading"]
        contrasts[c]["reading_why"] = read["readings"][c]["why"]
        if read["holm"] is not None:
            contrasts[c]["p_holm"] = read["holm"]["p"][c]["p_holm"]
            contrasts[c]["holm_rejects"] = read["holm"]["p"][c]["rejects_at_alpha"]
    incomplete = ([f"gate {gate['reason']}"] if gate["status"] != "COMPLETE" else []) + [
        f"{c} {contrasts[c]['reason']}" for c in L_IDS if contrasts[c]["status"] != "COMPLETE"]
    return {
        "planner": planner,
        "model": PLANNER_INFO[planner]["model"],
        "campaigns": campaigns,
        "n_tasks_observed_union": len(tasks),
        "incomplete_reasons": reasons,
        "warnings": warnings,
        "incomplete": reasons + incomplete,
        "gate": gate,
        "contrasts": contrasts,
        "holm": read["holm"],
        "readings": read["readings"],
        "descriptive": {
            "label": "DESCRIPTIVE: no direction, no verdict (prereg:116-122)",
            "delta_vs_luna": evaluate_delta(arms, n_boot=n_boot, seed=seed),
            "ceiling_goal_pass": _mean_block(arms["C"], campaigns["C"]["campaign"]),
            "F_goal_pass": _mean_block(arms["F"], campaigns["F"]["campaign"]),
        },
        "arms": {code: _arm_summary(code, arms[code], every[code]) for code in (*PLANNER_ARM_ORDER, *REFERENCE_ORDER)},
    }


def build_report(
    *,
    planners: tuple[str, ...] = PLANNERS,
    results_root: Path = RESULTS_ROOT,
    n_boot: int = N_BOOT,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    repo_root: Path = REPO_ROOT,
) -> tuple[dict[str, Any], int]:
    analysed = tuple(p for p in PLANNERS if p in set(planners))
    registered = analysed == PLANNERS and n_boot == N_BOOT and bootstrap_seed == BOOTSTRAP_SEED
    report: dict[str, Any] = {
        "protocol": "LP",
        "prereg": PREREG,
        "amendments": ["Amendment 1, 2026-09-23 (disclosure of a harness check; no registered item changes)"],
        "label": ("LP registered analysis (dev)" if registered
                  else "NON-REGISTERED settings or planner subset: not the LP result"),
        "results_root": str(results_root),
        "analysed_planners": list(analysed),
        "reference_campaigns": dict(REFERENCE_CAMPAIGNS),
        "settings": {
            "unit": "paired episode, key (task_id, seed)",
            "expected_pairs": EXPECTED_PAIRS,
            "seeds": list(SEEDS),
            "n_tasks": N_TASKS,
            "metric": "goal_pass (field goal_pass_rate) decision-bearing; TGC secondary (j10.score_tgc)",
            "bootstrap": {"n": n_boot, "seed": bootstrap_seed, "registered": registered,
                          "primary_clustering": "scenario", "secondary_clustering": "task",
                          "interval": "95% percentile, j10.cluster_bootstrap_means / percentile_ci"},
            "p_values": {c["id"]: f"{c['p_text']} (j10.bootstrap_pvalue {c['p_direction']!r} at "
                                  f"{c['threshold_pp']:+.2f} pp)" for c in CONTRASTS},
            "multiplicity": {"method": "Holm step-down", "family": list(L_IDS), "m": len(L_IDS),
                             "scope": "within each planner; none across planners", "alpha": ALPHA},
            "reading_excludes": ("unadjusted scenario interval meets the condition AND Holm-adjusted p <= 0.05; "
                                 "'includes zero' judged on the unadjusted interval (§3)"),
            "pool04": {"window_pp": j10.POOL04_WINDOW_PP, "seeds": list(j10.POOL04_SEEDS)},
            "signflip": ("j10.a1_permutation (cluster_inference.registered_signflip): scenario clusters, "
                         "exact over 2^G patterns when 2^G <= 2^20 (2^19 here), in each contrast's direction"),
            "crash_convention": ("drop only error_type == 'crash'; limit (incl. planner_context), parse_error, "
                                 "timeout and every other error_type are scored"),
        },
        "ambiguities": AMBIGUITIES,
    }
    errors: list[str] = []
    try:
        campaigns = resolve_campaigns(analysed, repo_root)
    except ProtocolError as exc:
        errors.append(str(exc))
        campaigns = {}
    report["campaigns"] = campaigns
    named = [(p, code, arm["campaign"]) for p in campaigns for code, arm in campaigns[p].items()]
    named += [("reference", code, name) for code, name in REFERENCE_CAMPAIGNS.items()]
    for _owner, _code, name in named:
        marker = j10.heldout_marker_in_path(results_root / name)
        if marker:
            errors.append(f"refusing campaign {name}: contains held-out marker {marker!r} (LP is dev only)")
    report["missing_campaigns"] = [
        {"owner": owner, "arm": code, "campaign": name, "path": str(results_root / name)}
        for owner, code, name in named if not (results_root / name).is_dir()
    ]
    loaded: dict[tuple[str, str], dict[str, Any]] = {}
    if not errors:
        for owner, code, name in named:
            try:
                loaded[(owner, code)] = load_campaign(code, results_root / name)
            except ProtocolError as exc:
                errors.append(str(exc))
    if errors:
        report.update(status="ERROR", exit_code=2, errors=errors, headline="ERROR: " + "; ".join(errors),
                      planners={}, overall_claim=None, descriptive=None)
        return report, 2

    reference = {code: loaded[("reference", code)] for code in REFERENCE_ORDER}
    blocks: dict[str, dict[str, Any]] = {}
    for p in analysed:
        own = {code: loaded[(p, code)] for code in PLANNER_ARM_ORDER}
        blocks[p] = _planner_block(p, campaigns[p], own, reference, n_boot=n_boot, seed=bootstrap_seed)

    ref_tasks = j10.discover_tasks(reference, list(SEEDS))
    luna_c = j10.a1_arm_episodes("C_luna", reference["C_luna"], ref_tasks, list(SEEDS))
    luna_c["complete"] = bool(luna_c["complete"] and len(ref_tasks) == N_TASKS)
    strength = {"luna": _mean_block(luna_c, REFERENCE_CAMPAIGNS["C_luna"])}
    for p in analysed:
        strength[p] = blocks[p]["descriptive"]["ceiling_goal_pass"]
    claim = overall_claim({p: {"gate": blocks[p]["gate"]["verdict"],
                               "L1": blocks[p]["readings"]["L1"]["reading"]} for p in analysed})

    incomplete = [f"{p}: {why}" for p in analysed for why in blocks[p]["incomplete"]]
    per_planner = "; ".join(
        f"{p} gate {blocks[p]['gate']['verdict']}, L1 {blocks[p]['readings']['L1']['reading']}"
        for p in analysed)
    missing = report["missing_campaigns"]
    if missing:
        status, code = "MISSING_CAMPAIGNS", 3
        headline = ("MISSING CAMPAIGNS: " + ", ".join(f"{m['owner']}:{m['arm']}:{m['campaign']}" for m in missing)
                    + f". {per_planner}. Overall: {claim['claim']}")
    elif incomplete:
        status, code = "INCOMPLETE", 1
        headline = "INCOMPLETE: " + "; ".join(incomplete) + f". {per_planner}. Overall: {claim['claim']}"
    else:
        status, code = "COMPLETE", 0
        headline = f"COMPLETE: {per_planner}. Overall: {claim['claim']}. {claim['text']}"
        if claim.get("reason"):
            headline += f" ({claim['reason']})"
    report.update(
        status=status,
        exit_code=code,
        headline=headline,
        errors=[],
        planners=blocks,
        overall_claim=claim,
        descriptive={
            "label": "DESCRIPTIVE: no direction, no verdict (prereg:116-122)",
            "planner_strength": {"index": "each ceiling's mean goal_pass_rate on the 57 x {1, 2} matrix",
                                 "by_planner": strength},
            "note": "Three planners cannot establish a trend; no direction is registered for Δ_p.",
        },
    )
    return report, code


# ---- markdown -----------------------------------------------------------------------
def _ci(block: Optional[dict[str, Any]]) -> str:
    if not block or block.get("ci95_pp") is None:
        return "-"
    lo, hi = block["ci95_pp"]
    return f"[{lo:+.2f}, {hi:+.2f}]"


def _p(value: Any) -> str:
    return "-" if value is None else f"{float(value):.4g}"


def _num(value: Any) -> str:
    return "-" if value is None else f"{value}"


def _pool_txt(pool: dict[str, Any]) -> str:
    txt = pool["status"]
    if pool.get("bounds_by_seed"):
        txt += " (" + ", ".join(f"{b['seed']}: [{b['lo_pp']:+.2f}, {b['hi_pp']:+.2f}] {b['verdict']}"
                                for b in pool["bounds_by_seed"]) + ")"
    return txt


def render_markdown(report: dict[str, Any], json_path: Optional[Path] = None) -> str:
    """Every number below is read from `report` (the JSON), never recomputed."""
    L: list[str] = ["# LP: the channel result across planner strength", ""]
    L.append(f"Registered analysis of `{report['prereg']}` (Amendment 1 is a disclosure; no registered item "
             "changes). Generated by `scripts/analysis/lp_report.py`"
             + (f"; JSON: `{json_path}`." if json_path else "."))
    L.append(f"Label: {report['label']}. Planners analysed: {', '.join(report['analysed_planners'])}.")
    L += ["", f"**Status: {report['status']}** (exit {report['exit_code']}). {report['headline']}", ""]
    if report.get("errors"):
        L.append("## Errors")
        L += [f"- {e}" for e in report["errors"]] + [""]
        return "\n".join(L) + "\n"
    if report.get("missing_campaigns"):
        L.append("## Missing campaigns")
        L += [f"- {m['owner']} {m['arm']}: `{m['campaign']}` (no directory at `{m['path']}`)"
              for m in report["missing_campaigns"]] + [""]

    claim = report["overall_claim"]
    L += ["## Overall claim (§4)", "", f"**{claim['claim']}**. {claim['text']}"]
    if claim.get("reason"):
        L.append(f"Reason: {claim['reason']}.")
    L.append("")

    settings = report["settings"]
    for p, b in report["planners"].items():
        L += [f"## {p} ({b['model']})", ""]
        g = b["gate"]
        if g["status"] != "COMPLETE":
            L.append(f"**Gate** C - E: INCOMPLETE ({g['reason']}); {g['why']}.")
        else:
            L.append(f"**Gate** C - E: {g['point_pp']:+.2f} pp over {g['n_pairs']} pairs, scenario CI "
                     f"{_ci(g['scenario'])}, task CI {_ci(g['task'])}, sign-flip p ('greater') "
                     f"{_p(g['signflip'].get('p_value'))} -> **{g['verdict']}** ({g['why']}).")
        L += ["", f"Contrasts on goal_pass. 95% percentile intervals, B = {settings['bootstrap']['n']:,}, "
                  f"seed {settings['bootstrap']['seed']}; Holm within {p} "
                  + (f"(m = {b['holm']['m']})." if b["holm"] else "(not computed: family incomplete)."), "",
              "| L | contrast | predicted | n pairs | point (pp) | scenario CI (pp) | task CI (pp) | p raw | p Holm "
              "| POOL-04 | sign-flip p | reading |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for cid, c in b["contrasts"].items():
            if c["status"] != "COMPLETE":
                L.append(f"| {cid} | {c['definition']} | {c['predicted']} | {c['n_pairs']}/{c['n_expected']} "
                         f"| INCOMPLETE: {c['reason']} | | | | | | | {c['reading']} |")
                continue
            L.append(f"| {cid} | {c['definition']} | {c['predicted']} | {c['n_pairs']} | {c['point_pp']:+.2f} "
                     f"| {_ci(c['scenario'])} | {_ci(c['task'])} | {_p(c['p_raw'])} ({c['p_raw_text']}) "
                     f"| {_p(c.get('p_holm'))} | {_pool_txt(c['pool04'])} "
                     f"| {_p(c['signflip'].get('p_value'))} ({c['signflip'].get('alternative')}) | {c['reading']} |")
        L += ["", "Readings:"]
        L += [f"- {cid}: **{r['reading']}** ({r['why']})" for cid, r in b["readings"].items()]
        L.append("")

        d = b["descriptive"]
        delta = d["delta_vs_luna"]
        L.append("Descriptive (no direction, no verdict):")
        if delta["status"] == "COMPLETE":
            L.append(f"- Δ_{p} = {delta['definition']}: {delta['point_pp']:+.2f} pp over {delta['n_pairs']} "
                     f"shared keys, scenario CI {_ci(delta['scenario'])}, task CI {_ci(delta['task'])}.")
        else:
            L.append(f"- Δ_{p}: INCOMPLETE ({delta['reason']}); {delta['n_pairs']} shared keys.")
        for name, block in (("ceiling C", d["ceiling_goal_pass"]), ("plan-only F", d["F_goal_pass"])):
            L.append(f"- {name} mean goal_pass_rate: {_num(block['goal_pass_mean'])} "
                     f"({block['n_scored']}/{block['n_expected']} scored, complete {block['complete']}).")
        L += ["", "TGC (secondary, not decision-bearing):", "",
              "| contrast | point (pp) | scenario CI (pp) | task CI (pp) |", "|---|---|---|---|"]
        for cid, c in [("gate", g), *b["contrasts"].items()]:
            t = c.get("tgc_secondary")
            if c["status"] != "COMPLETE" or not t or t.get("point_pp") is None:
                L.append(f"| {cid} {c['definition']} | INCOMPLETE | | |")
            else:
                L.append(f"| {cid} {c['definition']} | {t['point_pp']:+.2f} | {_ci(t['scenario'])} "
                         f"| {_ci(t['task'])} |")
        L += ["", "| arm | campaign (results) | scored / 114 | crash | missing | error_type counts | goal_pass mean |",
              "|---|---|---|---|---|---|---|"]
        for code, arm in b["arms"].items():
            camp = arm["campaign"]
            where = camp["n_results"] if camp["present"] else "absent"
            L.append(f"| {code} ({arm['name']}) | `{camp['campaign']}` ({where}) | {arm['n_scored']} "
                     f"| {arm['n_crash']} | {arm['n_missing']} | {json.dumps(arm['error_types'])} "
                     f"| {_num(arm['goal_pass_mean'])} |")
        if b["incomplete_reasons"]:
            L += [""] + [f"- incomplete: {r}" for r in b["incomplete_reasons"]]
        if b["warnings"]:
            L += [""] + [f"- warning: {w}" for w in b["warnings"]]
        L.append("")

    strength = report["descriptive"]["planner_strength"]
    L += ["## Planner strength (descriptive)", "", f"Index: {strength['index']}.", "",
          "| planner | ceiling campaign | mean goal_pass_rate | scored / expected | complete |",
          "|---|---|---|---|---|"]
    for p, s in strength["by_planner"].items():
        L.append(f"| {p} | `{s['campaign']}` | {_num(s['goal_pass_mean'])} | {s['n_scored']}/{s['n_expected']} "
                 f"| {s['complete']} |")
    L += ["", report["descriptive"]["note"], "", "## Ambiguities resolved in code", ""]
    L += [f"- **{a['id']}**: {a['script_behaviour']}" for a in report["ambiguities"]]
    return "\n".join(L) + "\n"


# ---- CLI ----------------------------------------------------------------------------
def _parse_planners(raw: str) -> tuple[str, ...]:
    names = [n.strip() for n in raw.split(",") if n.strip()]
    if not names:
        raise ValueError("--planners is empty")
    unknown = [n for n in names if n not in PLANNERS]
    if unknown:
        raise ValueError(f"unknown planner(s) {unknown}; allowed {list(PLANNERS)}")
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate planner in {raw!r}")
    return tuple(p for p in PLANNERS if p in names)


def _refuse_out(out_dir: Path, results_root: Path) -> Optional[str]:
    resolved = out_dir.resolve()
    for root in (*FORBIDDEN_OUT_ROOTS, results_root):
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"refusing --out-dir {out_dir}: it is under {root}, which holds raw results (read-only)"
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="LP registered analysis (prereg_lp_planner_strength_20260923).")
    p.add_argument("--planners", default=",".join(PLANNERS),
                   help=f"comma-separated subset of {list(PLANNERS)} (default both; a subset is non-registered)")
    p.add_argument("--date", default=None, help="YYYYMMDD in the output names (default: today)")
    p.add_argument("--out-dir", type=Path, default=OUT_DIR,
                   help=f"directory for {OUT_STEM}_<date>.report.json and .md "
                        f"(default {OUT_DIR.relative_to(REPO_ROOT)})")
    p.add_argument("--results-root", type=Path, default=RESULTS_ROOT,
                   help=f"root holding the campaign directories (read-only); default {RESULTS_ROOT}")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        date = args.date or _dt.date.today().strftime("%Y%m%d")
        if len(date) != 8 or not date.isdigit():
            raise ValueError(f"--date must be YYYYMMDD, got {date!r}")
        planners = _parse_planners(args.planners)
    except ValueError as exc:
        print(json.dumps({"protocol": "LP", "status": "REFUSED", "reason": str(exc)}))
        return 2
    # Refused before anything is read or written.
    refusal = _refuse_out(args.out_dir, args.results_root)
    if refusal:
        print(json.dumps({"protocol": "LP", "status": "REFUSED", "reason": refusal}))
        return 2
    report, code = build_report(planners=planners, results_root=args.results_root)
    report["date"] = date
    out = args.out_dir / f"{OUT_STEM}_{date}.report.json"
    md = args.out_dir / f"{OUT_STEM}_{date}.md"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md.write_text(render_markdown(report, out), encoding="utf-8")
    print(json.dumps({"protocol": "LP", "status": report["status"], "exit_code": code,
                      "headline": report["headline"], "json": str(out), "md": str(md)}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
