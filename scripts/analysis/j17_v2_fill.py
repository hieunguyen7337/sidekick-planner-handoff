#!/usr/bin/env python3
"""J17 v2 fill: the dev numbers behind Paper A v2's [[NEEDS LEDGER]] markers that no report holds.

What this module is for
-----------------------
paper/preprint_dev_v2_20260924.md carries fourteen [[NEEDS LEDGER]] markers. Most are sourced
from existing ledger rows or report keys. This module computes the rest, on dev data only:

* limits          step-limit counts for campaigns the paper prints without one (markers at
                  lines 94, 174, 345, 346), with each campaign's mean so it can be identified;
* d1              D1 = T - S (b2's execution contrast) on goal_pass, TGC and SGC with both
                  clusterings, through j17_channel_fixes' contrast objects (line 118);
* selection_task  the task-clustered companion of j16_robustness's kept-minus-dropped
                  intervals (ROB-17, ROB-21(a); line 323), same estimand as j16's
                  selection_block with the resample unit as a parameter;
* by_main_text    Benjamini-Yekutieli over every paired-contrast interval the abstract and
                  §1-§9 print (lines 273, 356; fix register R4.3). Candidates are enumerated in
                  main_text_specs; which of them the main text prints is read from the paper file at
                  build time (sha256 recorded), because other units move intervals between the main
                  text and the appendices;
* by_main_text_hstar  the same set with every handoff-split member (handoff-only or silenced, split
                  by the handoff_occurred flag) swapped for its h* value and p from
                  j17_hstar_20260924.report.json (review item 5); every other member kept;
* contrast_census a count of contrast objects across the dev report JSONs (line 376; R4.4).

Reuse, not re-implementation
----------------------------
Arms load through j17_depth_fixes.load_depth_rows (j16_robustness.load_campaign_dir) or, for
the b2 channel arms, b2_decomposition.load_pooled_arm + j10_report.a1_arm_episodes, exactly
as j17_depth_fixes and j17_channel_fixes load them. Every interval and p of the BY set is
j17_depth_fixes.contrast_object on per-pair components: j16_robustness.bootstrap_multi for
the scenario and task intervals (the draw sequence of hj1_gate / j8_frontier / j10_report, so
a mean statistic reproduces their intervals at the same seed), j10_report.bootstrap_pvalue
for the two-sided bootstrap p at the contrast's threshold, and
cluster_inference.registered_signflip (exact over 2^19 scenario sign patterns) beside it.
Benjamini-Yekutieli is cluster_inference.by_fdr.

Conventions (restated so the JSON is self-contained)
----------------------------------------------------
* Episode key (task_id, seed); dev split 57 tasks / 19 scenarios.
* error_type == "crash" is dropped from every pair and counted; "limit" is scored.
* Scenario clusters (19) primary, task clusters (57) secondary; B = --n-boot, seed = --seed;
  percentile indices int(0.025 B) / int(0.975 B). SGC units are (scenario, seed): no task
  clustering exists for them.
* p_two_sided: 2 x the smaller tail share of the scenario bootstrap statistic at threshold_pp
  (0, or -7.00 for a non-inferiority cell). p_signflip_two_sided: registered_signflip at the
  same threshold.

Interface:
  python scripts/analysis/j17_v2_fill.py --out PATH [--n-boot 10000] [--seed 20260924]
      [--results-root /scratch/n12194778/sidekick/results] [--paper-file PATH]
  python scripts/analysis/j17_v2_fill.py --out PATH --update EXISTING_REPORT
      (keeps every key of EXISTING_REPORT and recomputes only by_main_text_hstar; the paper and the
      results tree have moved since the report was built, so a full rebuild would not reproduce
      by_main_text or contrast_census unless --paper-file names the snapshot the report records)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import b2_decomposition as b2  # noqa: E402
from scripts.analysis import cluster_inference  # noqa: E402
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.analysis import j17_channel_fixes as chx  # noqa: E402
from scripts.analysis import j17_depth_fixes as dfx  # noqa: E402
from scripts.setup.hj1_gate import SEED as HJ1_SEED, scenario_of  # noqa: E402

j10 = chx.j10  # scripts.analysis.j10_report, the module b2 and j17_channel_fixes use

Key = tuple  # (task_id, seed), or (scenario, seed) for an SGC unit

RESULTS_DIR = j16.RESULTS_DIR
REPORTS_DIR = REPO / "campaign" / "results"
PAPER = "paper/preprint_dev_v2_20260924.md"
N_BOOT = 10_000
SEED = 20260924
ALPHA = 0.05
NI_MARGIN_PP = j16.NI_MARGIN_PP
LIMIT = "limit"
HELD_OUT_MARKERS = ("test_normal", "test_challenge")
# A J10/J11/J12 campaign or report is named j1{0,1,2}_...; "hj12_prefix_m9" is a dev campaign,
# so the match is anchored at the start of a path segment rather than anywhere in the text.
JX_SEGMENT_RE = re.compile(r"(^|[/\\])j1[012]_")
PRINT_TOL_PP = 0.011  # a printed 2-dp value reproduces if it is within rounding of ours


# --------------------------------------------------------------------------------------
# Refusal
# --------------------------------------------------------------------------------------


class RefusedPath(RuntimeError):
    """An input path names a held-out split or a J10/J11/J12 campaign or report."""


def refuse_path(path: Path | str) -> None:
    text = str(path)
    for marker in HELD_OUT_MARKERS:
        if marker in text:
            raise RefusedPath(f"refusing held-out split path {path}")
    if JX_SEGMENT_RE.search(text):
        raise RefusedPath(f"refusing J10/J11/J12 path {path}")


# --------------------------------------------------------------------------------------
# Arms
# --------------------------------------------------------------------------------------

# label -> ((campaign, system, seeds), ...). Pooled arms list one source per campaign.
ARM_SOURCES: dict[str, tuple[tuple[str, str, tuple[int, ...]], ...]] = {
    "advise_k1": (("hj13_advise_fixed_k_1_fullctx_20260923", "fixed_k", (1, 2)),),
    "advise_k10": (("hj12_advise_fixed_k_10_fullctx_20260923", "fixed_k", (1, 2)),),
    "takeover_k10": (("hj12_takeover_fixed_k_10_20260923", "fixed_k", (1, 2)),),
    "plan_floor": (("hj8_sft_plan_bplus_20260921iaware", "sft_plan", (1, 2)),),
    "executor_alone": (("hj8_executor_alone_bplus_20260919", "executor_alone", (1, 2)),),
    "ceiling_cap25": (("hj1b_planner_20260915", "planner_alone", (1, 2)),),
    "ceiling_cap81": (("hj13_planner_alone_cap81_20260923", "planner_alone", (1, 2)),),
    "ceiling_cap81_s3": (("hj13_planner_alone_cap81_seed3_20260924", "planner_alone", (3,)),),
    "t_pre_m9": (("hj12_prefix_m9_20260922", "prefix_handoff", (1, 2)),),
    "t_pre_m11": (("hj12_prefix_m11_20260922", "prefix_handoff", (1, 2)),),
    "t_m9": (("hj12_prefix_m9_20260923", "prefix_handoff", (1, 2)),),
    "t_m11": (("hj12_prefix_m11_20260923", "prefix_handoff", (1, 2)),),
    "zs_m9": (("hj13_prefix_zs_m9_20260923", "prefix_handoff", (1, 2)),),
    "zs_m11": (("hj13_prefix_zs_m11_20260923", "prefix_handoff", (1, 2)),),
    "narr_t_m9": (("hj16_narrated_m9_bplus_20260923", "sft_plan", (1, 2)),),
    "narr_t_m11": (("hj16_narrated_m11_bplus_20260923", "sft_plan", (1, 2)),),
    "narr_u_m9": (("hj16_narrated_m9_zs_20260923", "prompt_only", (1, 2)),),
    "narr_u_m11": (("hj16_narrated_m11_zs_20260923", "prompt_only", (1, 2)),),
}
# The pooled cap-81 prefix family is j17_depth_fixes' own (family_sources), under "c81_" labels.
C81_PREFIX = "c81_"
# Campaigns whose step-limit counts the paper prints as markers, with the marker lines.
LIMIT_LABELS: dict[str, str] = {
    "takeover_k10": "line 94: takeover_k10, seeds 1-2 (the 114-pair C1 arm)",
    "ceiling_cap81_s3": "line 174: planner_alone_cap81, seed 3",
    "ceiling_cap81": "LIM-01 cross-check: planner_alone_cap81, seeds 1-2 (18/114)",
    "t_m9": "line 345: prefix_m9 (post-guard, Table B1 0.7852)",
    "t_m11": "line 346: prefix_m11 (post-guard, Table B1 0.8098)",
    "t_pre_m9": "disambiguation: pre-guard prefix_m9",
    "t_pre_m11": "disambiguation: pre-guard prefix_m11",
}


def load_rows(results_root: Path, label: str) -> tuple[dict[Key, dict[str, Any]], list[dict[str, Any]]]:
    """Every row of one ARM_SOURCES arm (crashes included), via j17_depth_fixes.load_depth_rows."""
    sources = [dfx._source(results_root, c, s, seeds, c) for c, s, seeds in ARM_SOURCES[label]]
    for src in sources:
        refuse_path(src["root"])
    return dfx.load_depth_rows(sources)


def load_channel_arms(results_root: Path) -> tuple[dict[str, dict[Key, dict[str, Any]]], list[str]]:
    """b2's four channel arms (T, A, S, N) pooled over seeds 1-3, as j10 scored episodes."""
    pooled = {}
    for code, names in b2.ARM_CAMPAIGNS.items():
        dirs = [results_root / n for n in names]
        for d in dirs:
            refuse_path(d)
        pooled[code] = b2.load_pooled_arm(code, dirs)
    seeds = list(b2.SEEDS)
    tasks = j10.discover_tasks(pooled, seeds)
    eps = {code: j10.a1_arm_episodes(code, pooled[code], tasks, seeds)["episodes"] for code in pooled}
    return eps, tasks


def seed_subset(rows: dict[Key, Any], seeds: Iterable[int]) -> dict[Key, Any]:
    keep = set(seeds)
    return {k: v for k, v in rows.items() if k[1] in keep}


# --------------------------------------------------------------------------------------
# Step-limit counts
# --------------------------------------------------------------------------------------


def limit_counts(rows: dict[Key, dict[str, Any]]) -> dict[str, Any]:
    """n, crashes, scored episodes, error_type == 'limit' count and rate over the scored ones,
    and the scored goal_pass / TGC means that identify the campaign."""
    scored = {k: r for k, r in rows.items() if not j16.is_crash(r)}
    n_limit = sum(1 for r in scored.values() if r.get("error_type") == LIMIT)
    gp = [v for v in (j16.quality(r, "goal_pass_rate") for r in scored.values()) if v is not None]
    tg = [v for v in (j16.quality(r, "tgc") for r in scored.values()) if v is not None]
    by_seed: dict[str, dict[str, int]] = {}
    for (_t, seed), r in sorted(scored.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        cell = by_seed.setdefault(str(seed), {"n_scored": 0, "n_limit": 0})
        cell["n_scored"] += 1
        cell["n_limit"] += int(r.get("error_type") == LIMIT)
    return {
        "n": len(rows),
        "n_crash": len(rows) - len(scored),
        "n_scored": len(scored),
        "n_limit": n_limit,
        "rate": n_limit / len(scored) if scored else None,
        "goal_pass_mean": statistics.fmean(gp) if gp else None,
        "tgc_mean": statistics.fmean(tg) if tg else None,
        "by_seed": by_seed,
        "definition": "error_type == 'limit' among non-crash episodes; rate = n_limit / n_scored",
    }


# --------------------------------------------------------------------------------------
# Per-pair components
# --------------------------------------------------------------------------------------

# (numerator, denominator) per pair from the difference d and a 0/1 flag f; every statistic is
# sum(numerator) / sum(denominator) over whole resampled clusters.
PARTS: dict[str, Callable[[float, float], tuple[float, float]]] = {
    "all": lambda d, f: (d, 1.0),
    "subset": lambda d, f: (d * f, f),                 # mean over the flagged pairs
    "complement": lambda d, f: (d * (1.0 - f), 1.0 - f),  # mean over the unflagged pairs
    "contribution": lambda d, f: (d * f, 1.0),         # the flagged pairs' part of the whole mean
}


def components(diffs: dict[Key, float], flags: Optional[dict[Key, float]] = None,
               part: str = "all") -> dict[Key, tuple[float, float]]:
    if part not in PARTS:
        raise ValueError(f"part must be one of {sorted(PARTS)}, got {part!r}")
    if part != "all" and flags is None:
        raise ValueError(f"part {part!r} needs flags")
    fn = PARTS[part]
    return {k: fn(float(d), 1.0 if part == "all" else float(flags[k])) for k, d in sorted(diffs.items())}


def j10_diffs(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]], field: str) -> dict[Key, float]:
    """left - right on shared j10 episodes with both values recorded (j10.a1_paired_series)."""
    s = j10.a1_paired_series(left, right, field)
    return dict(zip(s["keys"], s["diffs"]))


def limit_flags(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]],
                keys: Iterable[Key]) -> dict[Key, float]:
    """1 where either arm's episode ended at the step limit (j10.am1_limit_split's split)."""
    return {k: 1.0 if LIMIT in (left[k].get("error_type"), right[k].get("error_type")) else 0.0 for k in keys}


def zero_limits(eps: dict[Key, dict[str, Any]], field: str) -> dict[Key, dict[str, Any]]:
    """j10.am1_limit_as_zero's zeroing: every limit episode's `field` set to 0."""
    return {k: (dict(e, **{field: 0.0}) if e.get("error_type") == LIMIT else e) for k, e in eps.items()}


def sgc_components(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]],
                   tasks: list[str], seeds: list[int]) -> tuple[dict[Key, tuple[float, float]], dict[str, int]]:
    """Per (scenario, seed) unit, left SGC - right SGC on the units both arms score
    (j10.a1_sgc_units: a unit passes iff every task of the scenario succeeded)."""
    ul, unscored_l = j10.a1_sgc_units(left, tasks, seeds)
    ur, unscored_r = j10.a1_sgc_units(right, tasks, seeds)
    shared = sorted(set(ul) & set(ur))
    comps = {u: (ul[u] - ur[u], 1.0) for u in shared}
    return comps, {"n_units_unscored_left": unscored_l, "n_units_unscored_right": unscored_r}


def _usable(row: Optional[dict[str, Any]], field: str) -> Optional[float]:
    if row is None or j16.is_crash(row) or not j16.j10_clean(row):
        return None
    return j16.quality(row, field)


def chord_components(arm: dict[Key, dict[str, Any]], floor: dict[Key, dict[str, Any]],
                     reference: dict[Key, dict[str, Any]], field: str, f: float) -> dict[Key, tuple[float, float]]:
    """Per triple, q_arm - [q_floor + f (q_ref - q_floor)] (j8_frontier.chord_residual's residual),
    with f the plug-in cost fraction; triples need all three rows non-crash, j10-clean, scored."""
    comps: dict[Key, tuple[float, float]] = {}
    for k in sorted(set(arm) & set(floor) & set(reference)):
        qa, qf, qr = (_usable(rows[k], field) for rows in (arm, floor, reference))
        if qa is None or qf is None or qr is None:
            continue
        comps[k] = (qa - (qf + f * (qr - qf)), 1.0)
    return comps


def cost_fraction(block: dict[str, Any]) -> float:
    """(c_arm - c_floor) / (c_ref - c_floor) from a chord block's recorded mean costs."""
    c_arm, c_floor, c_ref = (float(block[k]) for k in ("cost_arm", "cost_floor", "cost_reference"))
    return (c_arm - c_floor) / (c_ref - c_floor)


def did_components(a_pos: dict[Key, dict[str, Any]], a_neg: dict[Key, dict[str, Any]],
                   b_pos: dict[Key, dict[str, Any]], b_neg: dict[Key, dict[str, Any]],
                   field: str) -> dict[Key, tuple[float, float]]:
    """Per episode (a_pos - a_neg) - (b_pos - b_neg), formed before averaging (j14_did)."""
    comps: dict[Key, tuple[float, float]] = {}
    for k in sorted(set(a_pos) & set(a_neg) & set(b_pos) & set(b_neg)):
        vals = [_usable(rows[k], field) for rows in (a_pos, a_neg, b_pos, b_neg)]
        if any(v is None for v in vals):
            continue
        comps[k] = ((vals[0] - vals[1]) - (vals[2] - vals[3]), 1.0)
    return comps


def pair_diffs(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]], field: str) -> dict[Key, float]:
    """left - right via j16_robustness.paired_diffs (both rows j10-clean), crashes dropped first."""
    diffs, _meta = j16.paired_diffs(dfx.drop_crashed(left), dfx.drop_crashed(right), field)
    return diffs


# --------------------------------------------------------------------------------------
# Contrast entries and reproduction of the printed values
# --------------------------------------------------------------------------------------


def _signed(v: Optional[float], sign: int) -> Optional[float]:
    return None if v is None else sign * v


def _signed_ci(ci: Optional[list[float]], sign: int) -> Optional[list[float]]:
    if ci is None:
        return None
    return [sign * ci[0], sign * ci[1]] if sign > 0 else [sign * ci[1], sign * ci[0]]


def reproduces(printed: Optional[float | list[float]], ours: Optional[float | list[float]],
               tol: float = PRINT_TOL_PP) -> Optional[bool]:
    """True when every printed 2-dp number is within rounding of ours; None if nothing printed."""
    if printed is None:
        return None
    if ours is None:
        return False
    if isinstance(printed, (list, tuple)):
        return len(printed) == len(ours) and all(abs(float(p) - float(o)) <= tol for p, o in zip(printed, ours))
    return abs(float(printed) - float(ours)) <= tol


def _contrast(spec: dict[str, Any], comps: dict[Key, tuple[float, float]], n_boot: int, seed: int) -> dict[str, Any]:
    c = dfx.contrast_object(comps, 0, 1, metric=spec["metric"], threshold_pp=spec["threshold_pp"],
                            n_boot=n_boot, seed=seed)
    if spec.get("units") == "sgc":  # (scenario, seed) units: a task clustering does not exist
        c["ci95_pp_task"] = None
        c["p_two_sided_task"] = None
        c["n_clusters_task"] = None
        c["ci95_pp_task_note"] = "SGC is scenario-level: no task clustering exists"
    return c


def _as_printed(c: dict[str, Any], sign: int) -> dict[str, Any]:
    return {
        "diff_pp": _signed(c["diff_pp"], sign),
        "ci95_pp_scenario": _signed_ci(c["ci95_pp_scenario"], sign),
        "ci95_pp_task": _signed_ci(c["ci95_pp_task"], sign),
    }


def contrast_entry(spec: dict[str, Any], comps: dict[Key, tuple[float, float]], *,
                   n_boot: int, seed: int) -> dict[str, Any]:
    """j17_depth_fixes.contrast_object on sum(c[0]) / sum(c[1]), in the computed orientation,
    plus the printed orientation (sign) and whether the printed numbers reproduce.

    Every p is at `seed`. A printed interval that came from a report bootstrapped at another
    seed (spec["source_seed"]: the j8_frontier / hj1_gate default, 20260915) is checked against
    a second resample at that seed, so the check tests the data, not the RNG."""
    c = _contrast(spec, comps, n_boot, seed)
    sign = int(spec.get("sign", 1))
    shown = _as_printed(c, sign)
    check_seed = int(spec.get("source_seed") or seed)
    at_check = shown if check_seed == int(seed) else _as_printed(_contrast(spec, comps, n_boot, check_seed), sign)
    printed = spec.get("printed", {})
    checks = {
        "diff_pp": reproduces(printed.get("diff_pp"), at_check["diff_pp"]),
        "ci95_pp_scenario": reproduces(printed.get("scenario"), at_check["ci95_pp_scenario"]),
        "ci95_pp_task": reproduces(printed.get("task"), at_check["ci95_pp_task"]),
    }
    return {
        "id": spec["id"],
        "ledger": spec["ledger"],
        "paper_lines": spec["lines"],
        "definition": spec["definition"],
        "metric": spec["metric"],
        "population": spec["population"],
        "threshold_pp": spec["threshold_pp"],
        "n_pairs": c["n_pairs"],
        "n_units": len(comps),
        "computed": c,
        "sign_printed": sign,
        "as_printed": shown,
        "printed": printed,
        "anchor": spec.get("anchor"),
        "reproduction_seed": check_seed,
        "as_printed_at_reproduction_seed": at_check,
        "reproduces_printed": checks,
        "reproduces_all_printed": all(v for v in checks.values() if v is not None),
        "p_two_sided": c["p_two_sided"],
        "p_signflip_two_sided": c.get("p_signflip_two_sided"),
    }


# --------------------------------------------------------------------------------------
# The main-text interval set (R4.3, bounded to the abstract and §1-§9)
# --------------------------------------------------------------------------------------

SET_DEFINITION = (
    "Every interval printed in the abstract or §1-§9 of paper/preprint_dev_v2_20260924.md whose "
    "estimand is a mean of per-pair differences between arms paired on (task_id, seed) -- or on "
    "(scenario, seed) units for SGC -- including handoff-only and silenced subsets, the step-limit "
    "split's parts, the limit-as-0 sensitivity, chord residuals and per-episode "
    "difference-in-differences; one entry per distinct (contrast, population, metric), however "
    "often it is printed; D1's SGC, printed once its marker is filled, is included. Tested at 0, "
    "except the Table 6 non-inferiority cells, tested at the -7.00 pp margin as FDR-01 does. "
    "The candidates (main_text_specs) were enumerated by reading the paper; membership is then decided "
    "at build time from the paper file itself: a candidate is in the set if one of its printed intervals "
    "(absolute bounds at 2 dp, either clustering) or its anchor text appears on a line before the first "
    "'## Appendix' heading. The paper's sha256 is recorded, so the set is fixed by that hash."
)
MAIN_TEXT_END_RE = re.compile(r"^## Appendix\b")
INTERVAL_RE = re.compile(r"\[([−+-]?\d+(?:\.\d+)?)\s?%?, ([−+-]?\d+(?:\.\d+)?)\s?%?\]")
EXCLUDED_FROM_SET = {
    "ratio_or_share_estimands": [
        "ROB-19 cost ratios (§3.5: 3.19x tokens, 1.69x calls)",
        "HO-09 / HO-08 handoff shares (§4.2)", "ROB-13 share 16.7 % (§4.2)",
        "GANZ-01..03 QRec and savings retained (§4.5)", "COST-04 calls fraction and dollar saving (§4.5)",
    ],
    "not_a_paired_contrast": ["NOOP-01 arm mean (§2.4)", "DEC-06 content shares (Table 4)",
                              "ROB-15 slope +1.43 pp per step (§4.3)"],
    "printed_without_an_interval": ["every point estimate or p printed without an interval, e.g. "
                                    "LIM-06's S - A and T - N, the m9 -> m11 steps of §4.2, MULT-01"],
    "appendix": ["every interval printed in Appendices A-E (bounded scope)"],
}


def _p(diff: float, scen: Optional[list[float]] = None, task: Optional[list[float]] = None) -> dict[str, Any]:
    return {"diff_pp": diff, "scenario": scen, "task": task}


def main_text_lines(text: str) -> list[str]:
    """The abstract and §1-§9: every line before the first '## Appendix' heading."""
    out: list[str] = []
    for line in text.splitlines():
        if MAIN_TEXT_END_RE.match(line):
            break
        out.append(line)
    return out


def _bound(s: str) -> str:
    return f"{abs(float(s.replace('−', '-').replace('+', ''))):.2f}"


def _pairs(intervals: Iterable[Optional[list[float]]]) -> set[tuple[str, str]]:
    return {(f"{abs(float(iv[0])):.2f}", f"{abs(float(iv[1])):.2f}") for iv in intervals if iv}


def entry_pairs(entry: dict[str, Any]) -> set[tuple[str, str]]:
    """Absolute bounds at 2 dp of the entry's printed intervals, or, where nothing is printed yet (a
    marker), of its recomputed intervals in the printed orientation."""
    printed = entry.get("printed") or {}
    pairs = _pairs([printed.get("scenario"), printed.get("task")])
    if not pairs:
        shown = entry.get("as_printed") or {}
        pairs = _pairs([shown.get("ci95_pp_scenario"), shown.get("ci95_pp_task")])
    return pairs


def locate_in_main_text(entry: dict[str, Any], lines: list[str]) -> list[int]:
    """1-based main-text line numbers that print one of the entry's intervals or carry its anchor text.
    Bounds are compared as absolute values at 2 dp because the paper writes signs as +, − or nothing."""
    want = entry_pairs(entry)
    anchor = entry.get("anchor")
    hits = []
    for i, line in enumerate(lines, 1):
        if anchor and anchor in line:
            hits.append(i)
            continue
        if any((_bound(m.group(1)), _bound(m.group(2))) in want for m in INTERVAL_RE.finditer(line)):
            hits.append(i)
    return hits


def unmatched_intervals(lines: list[str], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every main-text interval that no candidate entry accounts for (ratios, shares, slopes, arm means,
    and anything added to the main text after the candidates were enumerated), for audit."""
    known: set[tuple[str, str]] = set()
    for e in entries:
        known |= entry_pairs(e)
    out = []
    for i, line in enumerate(lines, 1):
        for m in INTERVAL_RE.finditer(line):
            if (_bound(m.group(1)), _bound(m.group(2))) not in known:
                out.append({"line": i, "interval": m.group(0), "context": line[max(0, m.start() - 90):m.start()]})
    return out


def main_text_specs() -> list[dict[str, Any]]:
    """The set, in paper order. `build` names the data and component rule; `printed` is what the
    paper prints (used only to check that the recomputation is the printed contrast)."""
    s: list[dict[str, Any]] = []

    def add(id_: str, ledger: str, lines: str, definition: str, metric: str, population: str,
            build: tuple, printed: dict[str, Any], *, threshold_pp: float = 0.0, sign: int = 1,
            units: str = "pairs", source_seed: Optional[int] = None, anchor: Optional[str] = None) -> None:
        s.append({"id": id_, "ledger": ledger, "lines": lines, "definition": definition, "metric": metric,
                  "population": population, "build": build, "printed": printed,
                  "threshold_pp": threshold_pp, "sign": sign, "units": units, "source_seed": source_seed,
                  "anchor": anchor})

    # The printed intervals of these rows come from j8_frontier-schema reports (hj13_*, hj12_unified_frontier,
    # hj16_narrated_curve_*), which bootstrap at hj1_gate.SEED (20260915) unless --bootstrap-seed is passed.
    j8 = HJ1_SEED

    # §2.2 -- the cap change. Computed cap25 - cap81 as CEIL-07's report key, printed negated.
    add("CEIL07.gp", "CEIL-07", "46", "planner_alone_cap81 - planner_alone_cap25 (114)", "goal_pass", "all",
        ("pair", "ceiling_cap25", "ceiling_cap81", "goal_pass_rate"),
        _p(-6.47, [-11.68, -1.37], [-12.48, -0.46]), sign=-1, source_seed=j8)
    # §3.1 -- C1 at 114 pairs (seeds 1-2 of the b2 arms T and A).
    add("C1_114.gp", "CHAN-C1-02", "94", "T - A, seeds 1-2 (114); computed A - T as the report key "
        "(hj13_c1_matched_trigger goal_pass_all_advise_fullctx_k10_minus_takeover_k10)", "goal_pass", "all",
        ("channel", "A", "T", "goal_pass_rate", "all", (1, 2)), _p(6.69, [1.29, 13.48], [1.47, 12.35]), sign=-1,
        source_seed=j8)
    add("C1_114.tgc", "CHAN-C1-02, ROB-02", "94", "T - A, seeds 1-2 (114); computed A - T as the report key",
        "tgc", "all", ("channel", "A", "T", "tgc", "all", (1, 2)), _p(7.89, [1.75, 15.79]), sign=-1,
        source_seed=j8)
    add("C1_114.sgc", "ROB-11", "94", "A - T, seeds 1-2, (scenario, seed) units", "sgc", "all",
        ("channel_sgc", "A", "T", (1, 2)), _p(-7.89, [-21.05, 2.63]), units="sgc")
    # §3.1-3.2 -- the B2 contrasts at 171 pairs (Table 3), goal_pass, TGC, SGC.
    b2_rows = (
        ("D0", "T", "A", "DEC-02, METRIC-01, METRIC-02", "6, 96, 117",
         _p(6.13, [0.75, 12.71], [0.97, 11.73]), _p(5.26, [-0.58, 12.28], [-2.34, 13.45]), _p(3.51, [-3.51, 10.53])),
        ("D1", "T", "S", "DEC-04; this unit (D1 SGC)", "118",
         _p(3.83, [-1.56, 10.81]), _p(4.09, [-2.34, 10.53]), None),
        ("D2", "S", "A", "DEC-04, METRIC-01, METRIC-02", "119",
         _p(2.30, [-2.43, 7.31], [-1.58, 6.28]), _p(1.17, [-4.68, 8.19], [-5.26, 7.60]), _p(3.51, [-5.26, 12.28])),
        ("D3", "N", "A", "DEC-03, METRIC-01, METRIC-02", "6, 120",
         _p(3.73, [-0.06, 8.24], [0.04, 7.66]), _p(5.85, [-1.17, 14.04], [-0.58, 12.87]), _p(1.75, [-5.26, 8.77])),
        ("D4", "T", "N", "DEC-03, METRIC-01, METRIC-02", "121",
         _p(2.40, [-2.94, 8.89], [-1.97, 7.05]), _p(-0.58, [-8.77, 7.02], [-7.60, 6.43]), _p(1.75, [-5.26, 8.77])),
    )
    for cid, left, right, ledger, lines, gp, tg, sg in b2_rows:
        add(f"{cid}.gp", ledger, lines, f"{left} - {right} (171)", "goal_pass", "all",
            ("channel", left, right, "goal_pass_rate", "all", None), gp)
        add(f"{cid}.tgc", ledger, lines, f"{left} - {right} (171)", "tgc", "all",
            ("channel", left, right, "tgc", "all", None), tg)
        add(f"{cid}.sgc", ledger, lines, f"{left} - {right}, (scenario, seed) units", "sgc", "all",
            ("channel_sgc", left, right, None), sg or {}, units="sgc",
            anchor="NEEDS LEDGER: D1 SGC" if sg is None else None)
    # §3.3 -- the step-limit split (LIM-02, LIM-05) and the limit-as-0 sensitivity (LIM-06).
    add("D0.limit_either.contribution", "LIM-02", "127", "T - A: pairs where either arm hit the limit, "
        "sum over them / all 171 pairs", "goal_pass", "contribution (either arm at the limit)",
        ("channel", "T", "A", "goal_pass_rate", "contribution", None), _p(4.07, [0.93, 7.72], [1.52, 7.12]))
    add("D0.neither.mean", "LIM-02", "127", "T - A: mean over pairs where neither arm hit the limit",
        "goal_pass", "neither arm at the limit", ("channel", "T", "A", "goal_pass_rate", "complement", None),
        _p(2.37, [-0.59, 6.34], [-1.67, 6.86]))
    add("TN.limit_either.contribution", "LIM-05", "127", "T - N: pairs where either arm hit the limit, "
        "sum over them / all 171 pairs", "goal_pass", "contribution (either arm at the limit)",
        ("channel", "T", "N", "goal_pass_rate", "contribution", None), _p(3.55, [1.00, 7.03], [1.34, 6.19]))
    add("TN.neither.mean", "LIM-05", "127", "T - N: mean over pairs where neither arm hit the limit",
        "goal_pass", "neither arm at the limit", ("channel", "T", "N", "goal_pass_rate", "complement", None),
        _p(-1.26, [-6.04, 3.61], [-5.04, 2.59]))
    add("D0.limit_as_zero", "LIM-06", "129", "T - A, every limit episode scored 0 (171)", "goal_pass",
        "all, limit as 0", ("channel_zero", "T", "A"), _p(9.77, [2.60, 17.97], [3.51, 16.41]))
    add("N.limit_as_zero", "LIM-06", "129", "N - A, every limit episode scored 0 (171)", "goal_pass",
        "all, limit as 0", ("channel_zero", "N", "A"), _p(5.72, [1.26, 10.74], [0.87, 10.70]))
    # §3.5 -- advice at every step (114).
    add("H2.vs_prefix_m11.gp", "CHAN-PRICE-01", "152", "advise_k1 - prefix_m11 (post-guard, 114)", "goal_pass",
        "all", ("pair", "advise_k1", "t_m11", "goal_pass_rate"), _p(-14.68, [-22.09, -7.04], [-21.56, -7.79]),
        source_seed=j8)
    add("H2.vs_prefix_m11.tgc", "CHAN-PRICE-01", "152", "advise_k1 - prefix_m11 (post-guard, 114)", "tgc",
        "all", ("pair", "advise_k1", "t_m11", "tgc"), _p(-15.79, [-28.07, -3.51], [-25.44, -5.26]),
        source_seed=j8)
    add("H2.vs_plan_floor.gp", "CHAN-PRICE-01", "152", "advise_k1 - sft_plan floor (114)", "goal_pass", "all",
        ("pair", "advise_k1", "plan_floor", "goal_pass_rate"), _p(-5.51, [-13.15, 2.51], [-12.63, 1.72]),
        source_seed=j8)
    add("H2.vs_advise_k10.gp", "CHAN-PRICE-01, ROB-04", "152", "advise_k1 - advise_k10 full context (114)",
        "goal_pass", "all", ("pair", "advise_k1", "advise_k10", "goal_pass_rate"), _p(-7.08, [-14.78, 0.67]),
        source_seed=j8)
    # §4.2 Table 5 -- m6 -> m11 on the pooled cap-81 family (171), h from the m11 arm.
    t5 = {
        ("bplus", "goal_pass"): (_p(8.39, [4.20, 12.63], [4.09, 12.96]), _p(12.03, [5.49, 18.57], [5.07, 19.19]),
                                 _p(5.81, [1.00, 11.17], [0.51, 11.28])),
        ("bplus", "tgc"): (_p(15.79, [8.19, 23.98], [8.77, 23.39]), _p(15.49, [3.03, 30.16], [4.69, 27.40]),
                           _p(16.00, [7.45, 24.55], [7.14, 25.49])),
        ("zs", "goal_pass"): (_p(7.70, [3.69, 12.06], [3.14, 12.30]), _p(13.93, [5.12, 21.22], [5.48, 22.42]),
                              _p(3.27, [-1.71, 8.10], [-1.81, 8.51])),
        ("zs", "tgc"): (_p(11.70, [6.43, 16.96], [4.68, 18.71]), _p(15.49, [4.29, 26.47], [4.41, 26.92]),
                        _p(9.00, [1.05, 16.67], [0.00, 17.78])),
    }
    ho = {"bplus": {"goal_pass": "HO-04", "tgc": "HO-05"}, "zs": {"goal_pass": "HO-06", "tgc": "HO-07"}}
    for (rx, metric), cells in t5.items():
        field = "goal_pass_rate" if metric == "goal_pass" else "tgc"
        for part, printed in zip(("all", "handoff_only", "silenced"), cells):
            add(f"depth.{rx}.m6_to_m11.{metric}.{part}", ho[rx][metric], "182-185",
                f"c81 {rx} m11 - m6 (pooled seeds 1-3), {part}", metric, part,
                ("depth", rx, 6, 11, field, part), printed)
    # §4.4 -- chord residuals.
    add("chord.UF07.prefix_m9", "UF-07", "77, 199", "prefix_m9 (pre-guard, cap-25 source) - chord(sft_plan, "
        "planner_alone cap 25), 114 triples", "goal_pass", "chord residual",
        ("chord", "t_pre_m9", "plan_floor", "ceiling_cap25",
         "hj12_unified_frontier_20260922.report.json", ("chord", "arms", "prefix_m9", "goal_pass_all")),
        _p(3.96, None, [-0.49, 8.88]), source_seed=j8)
    chord_printed = {("bplus", 9): _p(3.02, [-1.48, 7.21], [-1.28, 7.26]),
                     ("bplus", 11): _p(7.56, [2.96, 12.35], [3.30, 11.98]),
                     ("zs", 11): _p(5.76, [2.15, 9.44], [2.17, 9.55])}
    for (rx, m), printed in chord_printed.items():
        add(f"chord.c81.{rx}.m{m}", "CHORD-01" if rx == "bplus" else "CHORD-02", "201",
            f"c81 {rx} m{m} - chord(sft_plan, planner_alone cap 81), 114 triples", "goal_pass", "chord residual",
            ("chord", f"{C81_PREFIX}{rx}_m{m}", f"{C81_PREFIX}floor", f"{C81_PREFIX}ceiling",
             "j17_depth_fixes_20260924.report.json", ("chord", rx, f"m{m}")), printed)
    # §4.6 Table 6 -- arm minus the pooled cap-81 planner alone, at the -7.00 pp margin.
    t6 = {
        ("bplus", 9): (_p(0.16, [-4.05, 4.65], [-4.29, 4.71]), _p(-4.21, [-8.83, 1.29], [-9.43, 0.93]),
                       _p(-6.43, [-12.28, -0.58], [-12.87, -0.58]), _p(-12.82, [-20.83, -4.35], [-21.14, -4.88])),
        ("bplus", 11): (_p(4.41, [-0.74, 10.67], [0.34, 8.65]), _p(-0.94, [-9.53, 7.45], [-7.87, 5.97]),
                        _p(0.58, [-5.85, 7.60], [-4.68, 5.85]), _p(-8.45, [-21.54, 3.53], [-18.46, 1.52])),
        ("zs", 9): (_p(0.50, [-3.02, 5.36], [-3.50, 4.80]), _p(-0.31, [-5.54, 6.72], [-6.02, 5.69]),
                    _p(-5.26, [-9.94, -0.58], [-10.53, 0.58]), _p(-8.55, [-15.79, -0.94], [-16.81, 0.00])),
        ("zs", 11): (_p(1.94, [-2.17, 6.40], [-1.66, 5.75]), _p(-4.36, [-11.89, 3.21], [-10.68, 2.43]),
                     _p(-2.92, [-7.02, 1.17], [-7.60, 1.75]), _p(-15.49, [-25.76, -5.80], [-24.64, -6.85])),
    }
    for (rx, m), cells in t6.items():
        for (metric, part), printed in zip((("goal_pass", "all"), ("goal_pass", "handoff_only"),
                                            ("tgc", "all"), ("tgc", "handoff_only")), cells):
            field = "goal_pass_rate" if metric == "goal_pass" else "tgc"
            ledger = "HO-NI-03" if metric == "tgc" else ("HO-NI-01" if rx == "bplus" else "HO-NI-02")
            add(f"ni.{rx}.m{m}.{metric}.{part}", ledger, "217-220",
                f"c81 {rx} m{m} - planner_alone_cap81 (pooled 171), {part}", metric, part,
                ("ni", rx, m, field, part), printed, threshold_pp=-NI_MARGIN_PP)
    # §5 -- the narrated control (114).
    add("narr.m9.tailored.exec_minus_narr", "NARR-01", "232", "executed t m9 - narrated t m9", "goal_pass", "all",
        ("pair", "t_m9", "narr_t_m9", "goal_pass_rate"), _p(1.84, [-2.67, 6.76], [-3.70, 7.75]), source_seed=j8)
    add("narr.m9.untailored.exec_minus_narr", "NARR-01", "232", "executed zs m9 - narrated zs m9", "goal_pass",
        "all", ("pair", "zs_m9", "narr_u_m9", "goal_pass_rate"), _p(1.69, [-4.16, 7.11], [-3.70, 7.38]),
        source_seed=j8)
    add("narr.m11.untailored.narr_minus_exec", "NARR-03", "234", "narrated zs m11 - executed zs m11",
        "goal_pass", "all", ("pair", "narr_u_m11", "zs_m11", "goal_pass_rate"),
        _p(-6.58, [-9.98, -3.64], [-10.95, -2.71]), source_seed=j8)
    add("narr.untailored.m9_to_m11", "NARR-03", "234", "narrated zs m11 - narrated zs m9; computed m9 - m11 "
        "as the report key", "goal_pass", "all", ("pair", "narr_u_m9", "narr_u_m11", "goal_pass_rate"),
        _p(0.10, [-4.75, 5.14]), sign=-1, source_seed=j8)
    add("narr.m11.tailored.narr_minus_exec", "NARR-04", "234", "narrated t m11 - executed t m11", "goal_pass",
        "all", ("pair", "narr_t_m11", "t_m11", "goal_pass_rate"), _p(-0.49, [-4.10, 3.21]), source_seed=j8)
    add("did.m11.gp", "DID-01", "234", "(narr_t - exec_t) - (narr_u - exec_u) at m11, per episode", "goal_pass",
        "all", ("did", "narr_t_m11", "t_m11", "narr_u_m11", "zs_m11", "goal_pass_rate"),
        _p(6.09, [1.56, 11.00], [0.63, 11.85]))
    add("did.m11.tgc", "DID-01, ROB-08", "234", "(narr_t - exec_t) - (narr_u - exec_u) at m11, per episode",
        "tgc", "all", ("did", "narr_t_m11", "t_m11", "narr_u_m11", "zs_m11", "tgc"),
        _p(12.28, [0.88, 26.32], [2.63, 22.81]))
    return s


N_MAIN_TEXT_INTERVALS = 68  # the count main_text_specs() must produce; a test pins it


def _dig(obj: Any, path: Iterable[str]) -> Any:
    for p in path:
        obj = obj[p]
    return obj


def build_components(spec: dict[str, Any], data: dict[str, Any]) -> tuple[dict[Key, tuple[float, float]], dict[str, Any]]:
    """The per-pair components one spec names, and what was used to form them."""
    b = spec["build"]
    kind = b[0]
    meta: dict[str, Any] = {"kind": kind}
    if kind == "channel":
        _k, left, right, field, part, seeds = b
        le, re_ = data["channel"][left], data["channel"][right]
        if seeds is not None:
            le, re_ = seed_subset(le, seeds), seed_subset(re_, seeds)
        diffs = j10_diffs(le, re_, field)
        flags = limit_flags(le, re_, diffs) if part != "all" else None
        if flags is not None:
            meta["n_flagged"] = int(sum(flags.values()))
        return components(diffs, flags, part), meta
    if kind == "channel_zero":
        _k, left, right = b
        field = "goal_pass_rate"
        diffs = j10_diffs(zero_limits(data["channel"][left], field), zero_limits(data["channel"][right], field), field)
        return components(diffs), meta
    if kind == "channel_sgc":
        _k, left, right, seeds = b
        le, re_ = data["channel"][left], data["channel"][right]
        use_seeds = list(b2.SEEDS) if seeds is None else list(seeds)
        if seeds is not None:
            le, re_ = seed_subset(le, seeds), seed_subset(re_, seeds)
        comps, unscored = sgc_components(le, re_, data["channel_tasks"], use_seeds)
        meta.update(unscored)
        return comps, meta
    if kind == "pair":
        _k, left, right, field = b
        return components(pair_diffs(data["rows"][left], data["rows"][right], field)), meta
    if kind == "depth":
        _k, rx, m_base, m_target, field, part = b
        comps, pairing = dfx.paired_components(dfx.drop_crashed(data["rows"][f"{C81_PREFIX}{rx}_m{m_base}"]),
                                               dfx.drop_crashed(data["rows"][f"{C81_PREFIX}{rx}_m{m_target}"]), field)
        i, j = dfx.CONTRAST_PARTS[part]
        meta["pairing"] = pairing
        return {k: (c[i], c[j]) for k, c in comps.items()}, meta
    if kind == "ni":
        _k, rx, m, field, part = b
        comps, pairing = dfx.paired_components(dfx.drop_crashed(data["rows"][f"{C81_PREFIX}ceiling"]),
                                               dfx.drop_crashed(data["rows"][f"{C81_PREFIX}{rx}_m{m}"]), field)
        i, j = dfx.CONTRAST_PARTS[part]
        meta["pairing"] = pairing
        return {k: (c[i], c[j]) for k, c in comps.items()}, meta
    if kind == "chord":
        _k, arm, floor, ref, report_name, path = b
        block = _dig(data["reports"][report_name], path)
        f = cost_fraction(block)
        meta.update(f=f, f_source=f"campaign/results/{report_name}: {'.'.join(path)}.{{cost_arm,cost_floor,cost_reference}}",
                    f_recorded=block.get("cost_fraction", block.get("f")))
        rows = data["rows"]
        return chord_components(rows[arm], rows[floor], rows[ref], "goal_pass_rate", f), meta
    if kind == "did":
        _k, a_pos, a_neg, b_pos, b_neg, field = b
        rows = data["rows"]
        return did_components(rows[a_pos], rows[a_neg], rows[b_pos], rows[b_neg], field), meta
    raise ValueError(f"unknown build kind {kind!r}")


def by_block(entries: list[dict[str, Any]], p_field: str, alpha: float = ALPHA) -> dict[str, Any]:
    """cluster_inference.by_fdr over the entries' `p_field`; an entry without a p is listed, not in m."""
    usable = [e for e in entries if e.get(p_field) is not None]
    adjusted = cluster_inference.by_fdr([float(e[p_field]) for e in usable]) if usable else []
    rows = [{"id": e["id"], "metric": e["metric"], "threshold_pp": e["threshold_pp"], "p": e[p_field],
             "p_by": p_by, "survives": bool(p_by <= alpha)} for e, p_by in zip(usable, adjusted)]
    return {
        "method": "Benjamini-Yekutieli, cluster_inference.by_fdr",
        "p_field": p_field,
        "alpha": alpha,
        "decision_bearing": False,
        "m": len(usable),
        "not_in_family": [e["id"] for e in entries if e.get(p_field) is None],
        "n_survive": sum(1 for r in rows if r["survives"]),
        "survivors": [r["id"] for r in rows if r["survives"]],
        "rows": rows,
    }


# --------------------------------------------------------------------------------------
# The same BY set with the handoff split read by h* (paper review item 5, R4.3)
# --------------------------------------------------------------------------------------

HSTAR_REPORT = "j17_hstar_20260924.report.json"
HANDOFF_PARTS = ("handoff_only", "silenced")  # the cells the handoff indicator splits
HSTAR_BY_DEFINITION = (
    "by_main_text's set, member for member (the same membership, read from the paper snapshot whose sha256 "
    "by_main_text.paper_snapshot records), with every handoff-split member -- population handoff_only or "
    "silenced, split by the prefix arm's handoff_occurred flag (HO-04..07, HO-NI-01..03) -- swapped for the "
    "same contrast split by h* ('the executor took control', HSTAR-01): its value, intervals and both p "
    "taken from campaign/results/j17_hstar_20260924.report.json. Every other member keeps its by_main_text p. "
    "BY as by_main_text (cluster_inference.by_fdr, alpha 0.05), over the bootstrap p and over the sign-flip p."
)


def hstar_key(entry_id: str) -> Optional[tuple[str, ...]]:
    """The j17_hstar path of a handoff-split member's h* counterpart, or None for any other member.

    depth.<rx>.m6_to_m11.<metric>.<part> -> handoff_only_contrasts.<rx>.m6_to_m11.<metric>.<part>
    ni.<rx>.m<m>.<metric>.handoff_only   -> ni.<rx>.m<m>.<metric>.handoff_only"""
    parts = entry_id.split(".")
    if len(parts) != 5 or parts[-1] not in HANDOFF_PARTS:
        return None
    kind, rx, span, metric, part = parts
    if kind == "depth":
        return ("handoff_only_contrasts", rx, span, metric, part)
    if kind == "ni":
        return ("ni", rx, span, metric, part)
    return None


def _all_episode_key(path: tuple[str, ...]) -> tuple[str, ...]:
    return path[:-1] + ("all",)


def hstar_by(by_main: dict[str, Any], hstar: dict[str, Any], alpha: float = ALPHA) -> dict[str, Any]:
    """BY over by_main_text's members with the handoff split read by h* (see HSTAR_BY_DEFINITION).

    The swap is only meaningful if the two reports' p are the same statistic on the same draws, so each
    swapped member's all-episode sibling is checked: its point and both p in j17_hstar must equal the
    all-episode member's in by_main_text (the indicator never moves an all-episode value, HSTAR-16)."""
    entries = {e["id"]: e for e in by_main["entries"]}
    members: list[dict[str, Any]] = []
    swapped: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for e in by_main["entries"]:
        if not e.get("in_main_text_now"):
            continue
        member = {"id": e["id"], "metric": e["metric"], "population": e["population"],
                  "threshold_pp": e["threshold_pp"], "indicator": None, "diff_pp": e["computed"]["diff_pp"],
                  "n_pairs": e["n_pairs"], "p_two_sided": e["p_two_sided"],
                  "p_signflip_two_sided": e["p_signflip_two_sided"]}
        path = hstar_key(e["id"])
        if path is not None:
            h = _dig(hstar, path)
            if float(h["threshold_pp"]) != float(e["threshold_pp"]):
                raise ValueError(f"{e['id']}: threshold {h['threshold_pp']} in j17_hstar, {e['threshold_pp']} here")
            member.update(indicator="h_star", diff_pp=h["diff_pp"], n_pairs=h["n_pairs"],
                          p_two_sided=h["p_two_sided"], p_signflip_two_sided=h["p_signflip_two_sided"])
            swapped.append({
                "id": e["id"], "hstar_key": ".".join(path),
                "flag": {"diff_pp": e["computed"]["diff_pp"], "n_pairs": e["n_pairs"],
                         "p_two_sided": e["p_two_sided"], "p_signflip_two_sided": e["p_signflip_two_sided"]},
                "hstar": {k: h.get(k) for k in ("diff_pp", "ci95_pp_scenario", "ci95_pp_task", "n_pairs",
                                                 "p_two_sided", "p_signflip_two_sided")},
            })
            sib_id = ".".join(e["id"].split(".")[:-1] + ["all"])
            sib, h_all = entries.get(sib_id), _dig(hstar, _all_episode_key(path))
            checks.append({
                "id": sib_id, "hstar_key": ".".join(_all_episode_key(path)),
                "equal": bool(sib is not None and all(
                    round(float(a), 6) == round(float(b), 6) for a, b in (
                        (sib["computed"]["diff_pp"], h_all["diff_pp"]),
                        (sib["p_two_sided"], h_all["p_two_sided"]),
                        (sib["p_signflip_two_sided"], h_all["p_signflip_two_sided"]))))})
        else:
            member["indicator"] = "flag" if e["population"] in HANDOFF_PARTS else None
        members.append(member)
    boot, flip = by_block(members, "p_two_sided", alpha), by_block(members, "p_signflip_two_sided", alpha)
    gp = [m for m in members if m["metric"] == "goal_pass"]
    before = {"bootstrap": set(by_main["bootstrap"]["survivors"]), "signflip": set(by_main["signflip"]["survivors"])}
    after = {"bootstrap": set(boot["survivors"]), "signflip": set(flip["survivors"])}
    by_row = {name: {r["id"]: r for r in blk["rows"]} for name, blk in (("bootstrap", boot), ("signflip", flip))}
    handoff_members = [{
        "id": s["id"], "diff_pp_flag": s["flag"]["diff_pp"], "diff_pp_hstar": s["hstar"]["diff_pp"],
        "n_pairs_flag": s["flag"]["n_pairs"], "n_pairs_hstar": s["hstar"]["n_pairs"],
        **{f"{name}_{what}": val for name in ("bootstrap", "signflip") for what, val in (
            ("p_by_hstar", by_row[name][s["id"]]["p_by"]),
            ("survives_flag", s["id"] in before[name]),
            ("survives_hstar", s["id"] in after[name]))},
    } for s in swapped]
    return {
        "definition": HSTAR_BY_DEFINITION,
        "decision_bearing": False,
        "hstar_report": {"path": f"campaign/results/{HSTAR_REPORT}", "generated_at": hstar.get("generated_at")},
        "paper_snapshot": by_main["paper_snapshot"],
        "m": len(members),
        "n_swapped": len(swapped),
        "swapped": swapped,
        "p_commensurable": {"rule": "each swapped member's all-episode sibling has the same point, bootstrap p and "
                                    "sign-flip p in both reports",
                            "all_equal": all(c["equal"] for c in checks), "checks": checks},
        "bootstrap": boot,
        "signflip": flip,
        "goal_pass_only": {"bootstrap": by_block(gp, "p_two_sided", alpha),
                           "signflip": by_block(gp, "p_signflip_two_sided", alpha)},
        "handoff_members": handoff_members,
        "changes_vs_by_main_text": {name: {"gained": sorted(after[name] - before[name]),
                                           "lost": sorted(before[name] - after[name])}
                                    for name in ("bootstrap", "signflip")},
    }


def add_hstar_block(report: dict[str, Any], hstar: dict[str, Any]) -> dict[str, Any]:
    """`report` with by_main_text_hstar placed after by_main_text (replacing an earlier one) and
    generated_at refreshed; every other key is carried over as it is."""
    block = j16.round_floats(hstar_by(report["by_main_text"], hstar))
    out: dict[str, Any] = {}
    for k, v in report.items():
        if k == "by_main_text_hstar":
            continue
        out[k] = datetime.now().astimezone().isoformat(timespec="seconds") if k == "generated_at" else v
        if k == "by_main_text":
            out["by_main_text_hstar"] = block
    return out


# --------------------------------------------------------------------------------------
# ROB-17 / ROB-21(a): kept - dropped with the resample unit as a parameter
# --------------------------------------------------------------------------------------


def kept_minus_dropped(rows: dict[Key, dict[str, Any]], ref: dict[Key, dict[str, Any]], unit: str,
                       n_boot: int, seed: int) -> dict[str, Any]:
    """j16_robustness.selection_block's estimand: over the arm's j10-clean rows paired with the
    reference, mean goal_pass where the REFERENCE did not end at its limit minus where it did,
    whole `unit` clusters resampled (j16 scores a crash 0 here, as selection_block does)."""
    dropped = {k for k, r in ref.items() if r.get("error_type") == LIMIT}
    comps: dict[Key, tuple[float, float, float, float]] = {}
    for k in sorted(set(rows) & set(ref)):
        if not j16.j10_clean(rows[k]):
            continue
        y = j16.quality(rows[k], "goal_pass_rate")
        if y is None:
            continue
        d = 1.0 if k in dropped else 0.0
        comps[k] = (y * (1 - d), 1 - d, y * d, d)

    def stat(t: list[float]) -> Optional[float]:
        if t[1] == 0 or t[3] == 0:
            return None
        return t[0] / t[1] - t[2] / t[3]

    b = j16.bootstrap_multi(comps, {"kept_minus_dropped": stat}, unit, seed, n_boot)
    st = b["stats"]["kept_minus_dropped"]
    return {
        "unit": unit,
        "n_pairs": len(comps),
        "n_kept": int(sum(c[1] for c in comps.values())),
        "n_dropped": int(sum(c[3] for c in comps.values())),
        "kept_minus_dropped_pp": None if st["point"] is None else 100 * st["point"],
        "ci95_pp": None if st["ci95"] is None else [100 * x for x in st["ci95"]],
        "n_resamples_without_a_dropped_episode": st["n_undefined"],
        "n_clusters": b["n_clusters"],
    }


# (reference label, arm labels, the j16_robustness report key it companions)
SELECTION = {
    "cap25": ("ceiling_cap25", ("ceiling_cap25", "plan_floor", "executor_alone"),
              "F_e_ni_both_ceilings.selection_induced_by_limit_exclusion.cap25.per_arm"),
    "cap81": ("ceiling_cap81", ("ceiling_cap81",),
              "F_e_ni_both_ceilings.selection_induced_by_limit_exclusion.cap81.per_arm"),
}
# j16's arm names for the report lookup.
J16_NAME = {"ceiling_cap25": "ceiling_cap25", "ceiling_cap81": "ceiling_cap81", "plan_floor": "plan_only",
            "executor_alone": "executor_alone"}


def selection_task(rows: dict[str, dict[Key, dict[str, Any]]], j16_report: Optional[dict[str, Any]],
                   n_boot: int, seed: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for tag, (ref, arms, key) in SELECTION.items():
        block: dict[str, Any] = {"reference": ref, "companion_of": f"campaign/results/j16_robustness_20260923.report.json: {key}"}
        per_arm = _dig(j16_report, key.split(".")) if j16_report else {}
        for arm in arms:
            scen = kept_minus_dropped(rows[arm], rows[ref], "scenario", n_boot, seed)
            task = kept_minus_dropped(rows[arm], rows[ref], "task", n_boot, seed)
            src = per_arm.get(J16_NAME[arm], {})
            rep_ci = src.get("kept_minus_dropped_ci95_pp_scenario")
            block[J16_NAME[arm]] = {
                "scenario": scen,
                "task": task,
                "report_scenario_ci95_pp": rep_ci,
                "scenario_reproduces_report": (None if rep_ci is None or scen["ci95_pp"] is None
                                               else all(abs(a - b) <= 1e-4 for a, b in zip(rep_ci, scen["ci95_pp"]))),
            }
        out[tag] = block
    return out


# --------------------------------------------------------------------------------------
# R4.4: contrast census over the dev report JSONs
# --------------------------------------------------------------------------------------

DIFF_KEYS = ("diff_pp", "diff", "point_pp", "diff_pp_scenario", "residual_mean_pp", "delta_pp")
# A {point, ci95...} object is a contrast only under a key that names one (a bare "point" with an
# interval is also how arm means are written).
POINT_PARENT_RE = re.compile(r"minus|_to_|delta|contribution|gain|did|diff|residual")


CHILD_BLOCKS = ("scenario", "task")  # the per-clustering sub-blocks a contrast may keep its numbers in


def _has_ci(obj: dict[str, Any]) -> bool:
    return any("ci95" in str(k) for k in obj)


def is_contrast_object(obj: Any, name: str = "") -> bool:
    """A paired-difference point with a 95 % interval, at this level or in its scenario / task
    sub-block, per the rule in CENSUS_RULE."""
    if not isinstance(obj, dict):
        return False
    children = [obj[k] for k in CHILD_BLOCKS if isinstance(obj.get(k), dict)]
    has_diff = any(k in obj for k in DIFF_KEYS) or any(any(k in c for k in DIFF_KEYS) for c in children)
    has_ci = _has_ci(obj) or any(_has_ci(c) for c in children)
    if has_diff and has_ci:
        return True
    return bool("point" in obj and _has_ci(obj) and POINT_PARENT_RE.search(name))


def _signature(obj: dict[str, Any]) -> tuple:
    """(point, first interval) rounded to 4 dp: identical contrasts reported twice collapse."""
    point = next((obj[k] for k in (*DIFF_KEYS, "point") if isinstance(obj.get(k), (int, float))), None)
    blocks = [obj] + [obj[k] for k in CHILD_BLOCKS if isinstance(obj.get(k), dict)]
    ci = None
    for blk in blocks:
        for k in sorted(blk):
            if "ci95" in str(k) and isinstance(blk[k], list):
                ci = blk[k]
                break
        if ci is not None:
            break
        if point is None:
            point = next((blk[k] for k in DIFF_KEYS if isinstance(blk.get(k), (int, float))), None)
    rnd = (lambda v: round(float(v), 4) if isinstance(v, (int, float)) else None)
    return (rnd(point), tuple(rnd(v) for v in ci) if ci else None)


def contrast_objects(tree: Any, path: tuple[str, ...] = ()) -> list[tuple[str, tuple]]:
    """Outermost contrast objects by dotted path: nothing inside a counted object is counted again."""
    found: list[tuple[str, tuple]] = []
    if isinstance(tree, dict):
        name = path[-1] if path else ""
        if is_contrast_object(tree, name):
            return [(".".join(path), _signature(tree))]
        for k, v in tree.items():
            found.extend(contrast_objects(v, (*path, str(k))))
    elif isinstance(tree, list):
        for i, v in enumerate(tree):
            found.extend(contrast_objects(v, (*path, str(i))))
    return found


CENSUS_SELF_PREFIX = "j17_v2_fill"  # this module's own report is not counted in its census

CENSUS_RULE = (
    "Files: every campaign/results/**/*.report.json except those named j10_*, j11_*, j12_* (the "
    "dev-only guard refuses those names) and this module's own j17_v2_fill_* report. A contrast "
    "object is a JSON object holding a "
    f"paired-difference point (one of {', '.join(DIFF_KEYS)}) and a key containing 'ci95', either at "
    "its own level or in its 'scenario' / 'task' sub-block, or a 'point' with a 'ci95' key under a "
    f"parent key matching /{POINT_PARENT_RE.pattern}/. Only the outermost such object "
    "counts. n_objects counts (file, path) pairs; n_distinct collapses objects whose (point, first "
    "interval), rounded to 4 dp, coincide, across files and populations. A lower bound on contrasts "
    "run: shares, ratios and tests printed without an interval are not counted, and every per-seed "
    "or per-population copy of one contrast is (n_objects) or is not (n_distinct) counted."
)


def contrast_census(paths: list[Path], root: Path) -> dict[str, Any]:
    per_file: dict[str, int] = {}
    excluded: list[str] = []
    signatures: set[tuple] = set()
    for path in sorted(paths):
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        try:
            refuse_path(path.name)
        except RefusedPath:
            excluded.append(rel)
            continue
        tree = json.loads(path.read_text(encoding="utf-8"))
        objs = contrast_objects(tree)
        per_file[rel] = len(objs)
        signatures.update((sig for _p, sig in objs))
    return {
        "rule": CENSUS_RULE,
        "n_files": len(per_file),
        "files_excluded_by_name": excluded,
        "n_objects": sum(per_file.values()),
        "n_distinct": len(signatures),
        "per_file": per_file,
    }


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------


def _read_report(name: str) -> dict[str, Any]:
    path = REPORTS_DIR / name
    refuse_path(path)
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(results_root: Path | str, n_boot: int = N_BOOT, seed: int = SEED,
                 paper_file: Optional[Path | str] = None) -> dict[str, Any]:
    """`paper_file` (default: the paper in this checkout) is the file whose bytes decide which candidates
    the main text prints; pass an earlier snapshot of the paper to rebuild the set that snapshot decided."""
    results_root = Path(results_root)
    refuse_path(results_root)
    rows: dict[str, dict[Key, dict[str, Any]]] = {}
    inputs: dict[str, Any] = {}
    for label in ARM_SOURCES:
        print(f"[fill] loading {label} ...", flush=True)
        rows[label], inputs[label] = load_rows(results_root, label)
    for label, srcs in dfx.family_sources(results_root).items():
        print(f"[fill] loading {C81_PREFIX}{label} ...", flush=True)
        rows[f"{C81_PREFIX}{label}"], inputs[f"{C81_PREFIX}{label}"] = dfx.load_depth_rows(srcs)
    print("[fill] loading channel arms ...", flush=True)
    channel, tasks = load_channel_arms(results_root)
    reports = {name: _read_report(name) for name in ("hj12_unified_frontier_20260922.report.json",
                                                     "j17_depth_fixes_20260924.report.json",
                                                     "j16_robustness_20260923.report.json")}
    data = {"rows": rows, "channel": channel, "channel_tasks": tasks, "reports": reports}

    print("[fill] limits ...", flush=True)
    limits = {label: {"campaigns": [c for c, _s, _seeds in ARM_SOURCES[label]], "why": why,
                      **limit_counts(rows[label])} for label, why in LIMIT_LABELS.items()}

    print("[fill] D1 ...", flush=True)
    d1 = {"definition": "T - S (b2 D1: takeover_k10 - show_k10), 171 pairs, seeds 1-3",
          "goal_pass": chx.contrast_object(channel["T"], channel["S"], "goal_pass", n_boot=n_boot, seed=seed),
          "tgc": chx.contrast_object(channel["T"], channel["S"], "tgc", n_boot=n_boot, seed=seed),
          "sgc": chx.sgc_contrast_object(channel["T"], channel["S"], tasks, list(b2.SEEDS), n_boot=n_boot, seed=seed),
          "source": "j17_channel_fixes.contrast_object / sgc_contrast_object (j10.a1_contrast, j10.a1_sgc_units)"}

    print("[fill] selection companions ...", flush=True)
    selection = selection_task(rows, reports["j16_robustness_20260923.report.json"], n_boot, seed)

    print("[fill] main-text set ...", flush=True)
    entries: list[dict[str, Any]] = []
    for spec in main_text_specs():
        comps, meta = build_components(spec, data)
        entry = contrast_entry(spec, comps, n_boot=n_boot, seed=seed)
        entry["components"] = meta
        entries.append(entry)
        print(f"[fill]   {spec['id']}: {entry['as_printed']['diff_pp']} pp, n {entry['n_pairs']}, "
              f"p {entry['p_two_sided']}, reproduces {entry['reproduces_all_printed']}", flush=True)
    failures = [{"id": e["id"], "checks": e["reproduces_printed"], "reproduction_seed": e["reproduction_seed"],
                 "as_printed_at_reproduction_seed": e["as_printed_at_reproduction_seed"], "printed": e["printed"]}
                for e in entries if not e["reproduces_all_printed"]]
    reseeded = [e["id"] for e in entries if e["reproduction_seed"] != seed]
    paper_bytes = Path(paper_file or REPO / PAPER).read_bytes()
    main_lines = main_text_lines(paper_bytes.decode("utf-8"))
    for e in entries:
        e["main_text_lines_now"] = locate_in_main_text(e, main_lines)
        e["in_main_text_now"] = bool(e["main_text_lines_now"])
    now = [e for e in entries if e["in_main_text_now"]]
    gp = [e for e in now if e["metric"] == "goal_pass"]
    unmatched = unmatched_intervals(main_lines, entries)
    by_main = {
        "set_definition": SET_DEFINITION,
        "excluded": EXCLUDED_FROM_SET,
        "paper_snapshot": {"path": PAPER, "sha256": hashlib.sha256(paper_bytes).hexdigest(),
                           "n_main_text_lines": len(main_lines),
                           "main_text_end": "first line matching ^## Appendix"},
        "n_candidates": len(entries),
        "n_entries": len(now),
        "not_in_main_text_now": [e["id"] for e in entries if not e["in_main_text_now"]],
        "n_by_metric": {m: sum(1 for e in now if e["metric"] == m) for m in ("goal_pass", "tgc", "sgc")},
        "n_ni_cells_at_margin": sum(1 for e in now if e["threshold_pp"] != 0.0),
        "main_text_intervals_not_in_the_candidates": {
            "n_intervals_in_main_text": sum(len(INTERVAL_RE.findall(line)) for line in main_lines),
            "n_unmatched": len(unmatched), "unmatched": unmatched,
            "note": "intervals no candidate accounts for; each should fall under `excluded` (ratios, shares, "
                    "slopes, arm means) -- anything else is a paired contrast added after the candidates "
                    "were enumerated, and the set must be extended"},
        "all_candidates": {
            "note": "BY over every candidate, i.e. the main-text set as enumerated before other units moved "
                    "some intervals to the appendices; a sensitivity, not the primary set",
            "bootstrap": by_block(entries, "p_two_sided"), "signflip": by_block(entries, "p_signflip_two_sided")},
        "reproduction": {"n_entries": len(entries), "n_reproduce_all_printed": len(entries) - len(failures),
                         "failures": failures,
                         "checked_at_source_seed": reseeded,
                         "checked_at_source_seed_note": (
                             f"these rows' printed intervals come from j8_frontier-schema reports, which bootstrap at "
                             f"hj1_gate.SEED = {HJ1_SEED} (j8_frontier.py SEED import; --bootstrap-seed not passed), "
                             f"not the {seed} that paper section 2.5 states; each is checked against a resample at "
                             f"{HJ1_SEED}; every p and every BY input here is at {seed}")},
        "bootstrap": by_block(now, "p_two_sided"),
        "signflip": by_block(now, "p_signflip_two_sided"),
        "goal_pass_only": {"bootstrap": by_block(gp, "p_two_sided"), "signflip": by_block(gp, "p_signflip_two_sided")},
        "entries": entries,
    }

    print("[fill] contrast census ...", flush=True)
    census = contrast_census(sorted(p for p in REPORTS_DIR.rglob("*.report.json")
                                    if not p.name.startswith(CENSUS_SELF_PREFIX)), REPO)

    report: dict[str, Any] = {
        "generated_by": "scripts/analysis/j17_v2_fill.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": ("Dev numbers for the [[NEEDS LEDGER]] markers of paper/preprint_dev_v2_20260924.md that no "
                    "report holds: step-limit counts, D1's companions, the task-clustered kept-minus-dropped "
                    "companions, BY over the main text's paired-contrast intervals (R4.3), and a contrast census "
                    "(R4.4). Exploratory; nothing here decides a registered verdict."),
        "paper": PAPER,
        "conventions": {
            "population": "error_type == 'crash' dropped from every pair (counted in inputs); 'limit' scored",
            "pairing": "(task_id, seed); j16 rows need both j10-clean (j16_robustness.paired_diffs); b2 channel "
                       "arms pair as j10.a1_paired_series; SGC pairs (scenario, seed) units",
            "clusterings": "scenario (19) primary, task (57) secondary; percentile int(0.025 B), int(0.975 B)",
            "p_two_sided": "2 x smaller tail share of the scenario bootstrap statistic at threshold_pp "
                           "(j10_report.bootstrap_pvalue)",
            "p_signflip_two_sided": "cluster_inference.registered_signflip over scenarios at threshold_pp "
                                    "(exact over 2^19 patterns)",
            "chord_f": "plug-in cost fraction from the source report's recorded mean costs; not resampled",
            "units": "*_pp in percentage points",
        },
        "limits": limits,
        "d1": d1,
        "selection_task": selection,
        "by_main_text": by_main,
        "contrast_census": census,
        "inputs": {"arms": inputs, "channel_campaigns": {k: list(v) for k, v in b2.ARM_CAMPAIGNS.items()},
                   "n_channel_tasks": len(tasks)},
        "settings": {"n_boot": int(n_boot), "seed": int(seed), "alpha": ALPHA, "results_root": str(results_root)},
    }
    print("[fill] main-text set with the h* handoff split ...", flush=True)
    return add_hstar_block(j16.round_floats(report), _read_report(HSTAR_REPORT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--results-root", type=Path, default=RESULTS_DIR)
    p.add_argument("--paper-file", type=Path, default=None,
                   help="the paper file whose bytes decide the main-text set (default: the paper in this checkout)")
    p.add_argument("--update", type=Path, default=None,
                   help="an existing report: keep every key of it as it is and (re)compute only "
                        "by_main_text_hstar from its by_main_text and the j17_hstar report; no arm is loaded")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        refuse_path(args.out)
        refuse_path(args.results_root)
        if str(Path(args.out).resolve()).startswith(str(Path(args.results_root).resolve())):
            raise RefusedPath(f"refusing to write under {args.results_root}")
        if args.update is not None:
            refuse_path(args.update)
            report = add_hstar_block(json.loads(args.update.read_text(encoding="utf-8")), _read_report(HSTAR_REPORT))
        else:
            report = build_report(args.results_root, args.n_boot, args.seed, args.paper_file)
    except RefusedPath as exc:
        print(f"[fill] {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[fill] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
