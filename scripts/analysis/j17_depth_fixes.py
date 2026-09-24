#!/usr/bin/env python3
"""J17 depth fixes: the adversarial review's F1 numbers, with intervals, on the dev split.

What this module is for
-----------------------
The adversarial review (docs/review_paperA_adversarial_20260923.md §F1) found that the depth
result is mostly the planner finishing the task. The fix register
(docs/plan_review_fixes_20260923.md §1) asks for these numbers beside every pooled depth claim:

* R1.1  handoff-only and silenced means per depth, and the m6->m11 / m9->m11 rise split into
        the part earned on episodes that hand off and the part earned on silenced ones;
* R1.1  non-inferiority against the planner alone at -7 pp, all episodes and handoff-only;
* R1.2  the registered chord test (C2 / UF-07) at m9 and m11, both receivers;
* R1.3  Ganz-comparable quality recovery and savings retained;
* R1.4  depth's cost share: the hosted-calls fraction and the dollar saving retained;
* R7.2  scenario and task clusterings for every interval.

Everything is computed on the pooled cap-81 prefix family, seeds {1, 2, 3} (hj17 seeds 1-2 +
hj18 seed 3), against the planner alone at cap 81 (hj13 seeds 1-2 + seed 3). No model is called.

Reuse, not re-implementation
----------------------------
Depth pieces are j16_robustness's (handoff_only_block, decomposition, depth_counts,
paired_diffs, bootstrap_multi, cost_contrast, ni_holds, refuse_heldout). The chord is
j8_frontier.chord_residual. Cost rows are j8_frontier.summarise_arm rows priced by
j12_cost_axes.price_arm_episodes. p values come from the same resamples as the interval via
j10_report.bootstrap_pvalue, with cluster_inference.registered_signflip beside them.

Conventions (restated so the JSON is self-contained)
----------------------------------------------------
* Episode key (task_id, seed); dev split 57 tasks / 19 scenarios.
* Crashed episodes (error_type == "crash") are excluded from every pair and counted in
  ``inputs``; "limit" is scored on its merits. Pairs also need both rows j10-clean (j16).
* h is the prefix arm's handoff_occurred (payload of the last `report` event of the last
  attempt, as j13_mechanism / j16); a missing flag counts as silenced (h = 0) and is counted.
* Paired cluster percentile bootstrap, B = --n-boot, seed = --seed; scenario clusters (19)
  primary, task clusters (57) secondary; percentile indices int(0.025 B) / int(0.975 B).
* p_two_sided = 2 x the smaller tail share of the scenario-bootstrap statistic at
  threshold_pp (j10_report.bootstrap_pvalue); p_two_sided_task is the task analogue.

Interface:
  python scripts/analysis/j17_depth_fixes.py --out PATH [--n-boot 10000] [--seed 20260924]
      [--results-root /scratch/n12194778/sidekick/results]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scripts.setup.hj1_gate as hj1  # noqa: E402
from scripts.analysis import cluster_inference  # noqa: E402
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

# j12 loads its own j8_frontier and j10_report; this module uses those copies, so pricing, the
# chord and the p value run on one set of modules (j16 loads j12 the same way, :1678-1702).
j12 = j16._load_module("j12_cost_axes", "j12_cost_axes.py")
j8 = j12.j8
j10 = j12.j10

Key = tuple  # (task_id, seed)

RESULTS_DIR = j16.RESULTS_DIR
N_BOOT = 10_000
SEED = 20260924
NI_MARGIN_PP = j16.NI_MARGIN_PP
RECEIVERS = ("bplus", "zs")
DEPTHS = (6, 9, 11)
NI_DEPTHS = (9, 11)
CHORD_DEPTHS = (9, 11)
DEPTH_PAIRS = ((6, 11), (9, 11))
METRICS = (("goal_pass", "goal_pass_rate"), ("tgc", "tgc"))
# (numerator, denominator) indices into paired_components' vector.
CONTRAST_PARTS = {"all": (0, 1), "handoff_only": (2, 3), "silenced": (4, 5)}
COST_KEY = "planner_tokens_noncached"
PACKET_SYSTEM = "planner_alone"

CEILING_C81 = "hj13_planner_alone_cap81_20260923"
CEILING_C81_S3 = "hj13_planner_alone_cap81_seed3_20260924"
CEILING_LABEL = "planner_alone_cap81"
# The registered chord floor. docs/prereg_hj12_dev_20260922.md:40 (claim C2) draws the chord
# from `sft_plan` to `planner_alone`; ledger UF-07 (docs/claims_ledger.md:16) reports it from
# hj12_unified_frontier_20260922.report.json, whose chord block names floor_arm "sft_plan".
# That report's sft_plan rows are hj8_sft_plan_bplus_20260921iaware: j16_robustness maps them
# there (:101, "plan_only") and its F-e section reproduces the report's sft_plan numbers from
# them. J10 Amendment 1 B3 (docs/prereg_j10_amendment_20260924.md:739-742) registers the same
# floor, arm 2 `sft_plan` under sft_b_plus (:133), for prefix_zs_m9 / prefix_zs_m11 as well.
# j8 prices sft_plan rows by this label (j8_noncached_cost.is_sft_plan_row), so it must stay.
FLOOR_LABEL = "sft_plan"
FLOOR_CAMPAIGN = "hj8_sft_plan_bplus_20260921iaware"
FLOOR_PACKET_SOURCE = "hj1b_planner_20260915"
FLOOR_ARM_CITED = (
    "sft_plan (hj8_sft_plan_bplus_20260921iaware/sft_plan, seeds 1-2): the floor of the "
    "registered chord test C2, docs/prereg_hj12_dev_20260922.md:40; ledger UF-07, "
    "docs/claims_ledger.md:16"
)
FLOOR_REGISTRATION = {
    "bplus": "docs/prereg_hj12_dev_20260922.md:40 (C2: the chord joins sft_plan and planner_alone); "
             "docs/claims_ledger.md:16 (UF-07, chord.floor_arm 'sft_plan')",
    "zs": "docs/prereg_j10_amendment_20260924.md:739-742 (J10 Amendment 1 B3: prefix_zs_m9 and "
          "prefix_zs_m11 take floor arm 2 `sft_plan`, the sft_b_plus arm of :133). No dev "
          "registration names a zero-shot sft_plan floor.",
}


# --------------------------------------------------------------------------------------
# Inputs and refusal
# --------------------------------------------------------------------------------------


class RefusedPath(RuntimeError):
    """An input path names a held-out split or a J10 campaign."""


def refuse_path(path: Path | str) -> None:
    """j16's held-out refusal (test_normal / test_challenge, :136-140) plus any `j10_` path."""
    try:
        j16.refuse_heldout(path)
    except RuntimeError as exc:
        raise RefusedPath(str(exc)) from exc
    if "j10_" in str(path):
        raise RefusedPath(f"refusing J10 campaign path {path}")


def _source(results_root: Path, campaign: str, system: str, seeds: tuple[int, ...],
            packet_source: str) -> dict[str, Any]:
    return {"campaign": campaign, "root": Path(results_root) / campaign / system,
            "seeds": tuple(seeds), "packet_source": Path(results_root) / packet_source}


def family_sources(results_root: Path | str) -> dict[str, list[dict[str, Any]]]:
    """Every campaign root this analysis reads, per arm label, with the seeds taken from it
    and the planner sample its prefix / plan replays (the config's packet_source)."""
    r = Path(results_root)
    out: dict[str, list[dict[str, Any]]] = {
        "ceiling": [
            _source(r, CEILING_C81, "planner_alone", (1, 2), CEILING_C81),
            _source(r, CEILING_C81_S3, "planner_alone", (3,), CEILING_C81_S3),
        ],
        "floor": [_source(r, FLOOR_CAMPAIGN, "sft_plan", (1, 2), FLOOR_PACKET_SOURCE)],
    }
    for rx in RECEIVERS:
        for m in DEPTHS:
            out[f"{rx}_m{m}"] = [
                _source(r, f"hj17_prefix_c81_{rx}_m{m}_20260923", "prefix_handoff", (1, 2), CEILING_C81),
                _source(r, f"hj18_prefix_c81s3_{rx}_m{m}_20260924", "prefix_handoff", (3,), CEILING_C81_S3),
            ]
    return out


def refuse_inputs(results_root: Path | str, sources: dict[str, list[dict[str, Any]]]) -> None:
    refuse_path(results_root)
    for srcs in sources.values():
        for src in srcs:
            refuse_path(src["root"])
            refuse_path(src["packet_source"])


def load_depth_rows(sources: list[dict[str, Any]]) -> tuple[dict[Key, dict[str, Any]], list[dict[str, Any]]]:
    """j16 rows (result.json + last-attempt report facts) pooled over the sources.

    Returns every row, crashed ones included, and one inputs entry per campaign dir."""
    merged: dict[Key, dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    for src in sources:
        refuse_path(src["root"])
        rows, diag = j16.load_campaign_dir(src["root"], src["seeds"])
        clash = set(merged) & set(rows)
        if clash:
            raise ValueError(f"pooled arm: {len(clash)} colliding keys at {src['root']}")
        merged.update(rows)
        n_crash = sum(1 for r in rows.values() if j16.is_crash(r))
        entries.append({
            "campaign_dir": str(src["root"]),
            "seeds": list(src["seeds"]),
            "n_episodes": len(rows),
            "n_crash": n_crash,
            "n_crash_excluded_from_pairs": n_crash,
            "load_diagnostics": diag,
        })
    return merged, entries


def drop_crashed(rows: dict[Key, dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    return {k: r for k, r in rows.items() if not j16.is_crash(r)}


def load_cost_rows(label: str, sources: list[dict[str, Any]], price_card: dict[str, Any]
                   ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """j8_frontier.summarise_arm rows, priced by j12_cost_axes.price_arm_episodes, per source.

    Each source is priced against its own planner sample (hj17 -> the cap-81 seeds 1-2 run,
    hj18 -> the seed-3 run), because a prefix arm's hosted usage is the replayed prefix of that
    run. Crashed rows are kept here; callers drop them."""
    cleaned: dict[Key, dict[str, Any]] = {}
    per_root: list[dict[str, Any]] = []
    for src in sources:
        refuse_path(src["root"])
        refuse_path(src["packet_source"])
        if not Path(src["root"]).is_dir():
            raise FileNotFoundError(f"campaign directory does not exist: {src['root']}")
        loaded = j10.load_arm_tree(Path(src["root"]))
        arm = j8.summarise_arm(label, loaded, list(src["seeds"]), root=Path(src["root"]),
                               cost_key=COST_KEY, packet_source=src["packet_source"],
                               packet_system=PACKET_SYSTEM)
        priced = j12.price_arm_episodes(arm, price_card, root=Path(src["root"]),
                                        packet_source=src["packet_source"], packet_system=PACKET_SYSTEM)
        clash = set(cleaned) & set(arm["cleaned"])
        if clash:
            raise ValueError(f"pooled cost arm {label}: {len(clash)} colliding keys at {src['root']}")
        cleaned.update(arm["cleaned"])
        per_root.append({
            "packet_source": str(src["packet_source"]),
            "n_cost_rows": len(arm["cleaned"]),
            "means": {axis: priced[axis] for axis in j12.COST_AXES},
            "pricing_diagnostics": priced["diagnostics"],
            "sft_plan_floor_costing": arm["sft_plan_floor_costing"],
        })
    return {"label": label, "cleaned": cleaned}, per_root


def cost_survivors(arm: dict[str, Any]) -> dict[str, Any]:
    return {"label": arm["label"],
            "cleaned": {k: r for k, r in arm["cleaned"].items() if not j8.is_crashed(r)}}


def loader_agreement(depth_rows: dict[Key, dict[str, Any]], cost_rows: dict[Key, dict[str, Any]]) -> dict[str, Any]:
    """The two loaders read the same files; count where they disagree instead of assuming."""
    shared = set(depth_rows) & set(cost_rows)
    gp = sum(1 for k in shared
             if depth_rows[k].get("goal_pass_rate") != cost_rows[k].get("goal_pass_rate"))
    flag = sum(1 for k in shared
               if j16.handoff_flag(depth_rows[k]) != cost_rows[k].get("handoff_occurred"))
    return {"n_depth_rows": len(depth_rows), "n_cost_rows": len(cost_rows),
            "n_keys_only_in_depth_rows": len(set(depth_rows) - set(cost_rows)),
            "n_keys_only_in_cost_rows": len(set(cost_rows) - set(depth_rows)),
            "n_goal_pass_mismatch": gp, "n_handoff_flag_mismatch": flag}


# --------------------------------------------------------------------------------------
# Bootstrap settings and contrast objects
# --------------------------------------------------------------------------------------


@contextmanager
def bootstrap_settings(n_boot: int, seed: int) -> Iterator[None]:
    """Point every reused resampler at (n_boot, seed) and restore it afterwards.

    j16's handoff_only_block / decomposition read j16.SEED at call time; j8's chord reads
    j8.SEED / j8.BOOTSTRAP and hj1_gate.SEED / hj1_gate.BOOTSTRAP (j8_frontier :64-75)."""
    saved = (j16.SEED, j8.SEED, j8.BOOTSTRAP, hj1.SEED, hj1.BOOTSTRAP)
    j16.SEED = int(seed)
    j8.set_bootstrap_seed(int(seed))
    j8.BOOTSTRAP = int(n_boot)
    hj1.BOOTSTRAP = int(n_boot)
    try:
        yield
    finally:
        j16.SEED, j8.SEED, j8.BOOTSTRAP, hj1.SEED, hj1.BOOTSTRAP = saved


def _pp(x: Optional[float]) -> Optional[float]:
    return None if x is None else 100.0 * x


def _pp_ci(ci: Optional[list[float]]) -> Optional[list[float]]:
    return None if ci is None else [100.0 * ci[0], 100.0 * ci[1]]


def contrast_object(comps: dict[Key, tuple[float, ...]], num: int, den: int, *, metric: str,
                    threshold_pp: float, n_boot: int, seed: int) -> dict[str, Any]:
    """sum(c[num]) / sum(c[den]) with whole clusters resampled, both clusterings.

    The key set is a contract shared with unit S4-channel: diff_pp, ci95_pp_scenario,
    ci95_pp_task, p_two_sided (scenario bootstrap, two-sided, at threshold_pp), threshold_pp,
    n_pairs, metric. `den` must index a 0/1 indicator (or the constant 1), so the statistic is
    the mean paired difference over the pairs where it is 1.
    """
    thr = threshold_pp / 100.0
    out: dict[str, Any] = {
        "diff_pp": None,
        "ci95_pp_scenario": None,
        "ci95_pp_task": None,
        "p_two_sided": None,
        "threshold_pp": float(threshold_pp),
        "n_pairs": int(sum(1 for c in comps.values() if c[den] > 0)),
        "metric": metric,
    }
    stats = {"stat": j16.ratio(num, den)}
    for unit in ("scenario", "task"):
        b = j16.bootstrap_multi(comps, stats, unit, seed, n_boot, keep_samples=True)
        st = b["stats"]["stat"]
        samples = st.get("_samples") or []
        out["diff_pp"] = _pp(st["point"])
        out[f"ci95_pp_{unit}"] = _pp_ci(st["ci95"])
        p = j10.bootstrap_pvalue(samples, thr, "two-sided") if samples else None
        out["p_two_sided" if unit == "scenario" else "p_two_sided_task"] = p
        out[f"n_clusters_{unit}"] = b["n_clusters"]
        out[f"n_resamples_undefined_{unit}"] = st["n_undefined"]
    kept = [(k, c[num] / c[den]) for k, c in sorted(comps.items()) if c[den] > 0]
    if kept:
        sf = cluster_inference.registered_signflip(
            [d for _k, d in kept], [scenario_of(str(k[0])) for k, _d in kept],
            threshold=thr, alternative="two-sided", seed=seed)
        out["p_signflip_two_sided"] = sf["p"]
        out["signflip_method"] = sf["method"]
    else:
        out["p_signflip_two_sided"] = None
        out["signflip_method"] = None
    return out


def paired_components(base: dict[Key, dict[str, Any]], target: dict[Key, dict[str, Any]],
                      field: str) -> tuple[dict[Key, tuple[float, ...]], dict[str, Any]]:
    """Per pair (d, 1, d*h, h, d*(1-h), 1-h) with d = target - base and h from the target arm.

    Pairing is j16.paired_diffs' (both rows j10-clean, both scored); h is j16's `_h`
    (handoff_occurred true -> 1; false or missing -> 0)."""
    diffs, meta = j16.paired_diffs(target, base, field)
    comps: dict[Key, tuple[float, ...]] = {}
    for k, d in diffs.items():
        h = j16._h(target[k])
        comps[k] = (d, 1.0, d * h, h, d * (1.0 - h), 1.0 - h)
    meta = dict(meta)
    meta["n_handoff"] = int(sum(c[3] for c in comps.values()))
    meta["n_silenced"] = int(sum(c[5] for c in comps.values()))
    meta["n_silenced_flag_missing"] = sum(
        1 for k in comps if j16.handoff_flag(target[k]) is None)
    meta["handoff_flag_from"] = "target (prefix) arm"
    return comps, meta


# --------------------------------------------------------------------------------------
# R1.1  Handoff-only means, depth contrasts and their decomposition, non-inferiority
# --------------------------------------------------------------------------------------


def handoff_arm_block(rows: dict[Key, dict[str, Any]], n_boot: int) -> dict[str, Any]:
    """n, n_handoff, n_silenced and the all / handoff / silenced means for one prefix arm."""
    counts = j16.depth_counts(rows)
    out: dict[str, Any] = {
        "n": counts["n"],
        "n_handoff": counts["n_handoff_occurred_true"],
        "n_silenced": counts["n_handoff_occurred_false"] + counts["n_handoff_flag_missing"],
        "n_handoff_flag_missing": counts["n_handoff_flag_missing"],
        "n_handoff_occurred_false": counts["n_handoff_occurred_false"],
        "n_executor_never_acted": counts["n_executor_never_acted"],
        "n_handoff_false_but_executor_acted": counts["n_handoff_false_but_executor_acted"],
    }
    for metric, field in METRICS:
        b = j16.handoff_only_block(rows, field, n_boot)
        out[metric] = {
            "n_scored": b["n_handoff"] + b["n_silenced"],
            "n_handoff": b["n_handoff"],
            "n_silenced": b["n_silenced"],
            "mean_all": b["all"]["point"],
            "mean_handoff": b["handoff_only"]["point"],
            "mean_silenced": b["silenced"]["point"],
            "ci95_scenario": {"all": b["all"]["ci95_scenario"],
                              "handoff": b["handoff_only"]["ci95_scenario"],
                              "silenced": b["silenced"]["ci95_scenario"]},
            "ci95_task": {"all": b["all"]["ci95_task"],
                          "handoff": b["handoff_only"]["ci95_task"],
                          "silenced": b["silenced"]["ci95_task"]},
        }
    return out


def decomposition_object(dec: dict[str, Any], all_pp: Optional[float]) -> dict[str, Any]:
    """j16.decomposition in pp, keyed as the S4 contract asks."""

    def pp_block(name: str) -> dict[str, Any]:
        blk = dec[name]
        return {"point_pp": _pp(blk["point"]),
                "ci95_pp_scenario": _pp_ci(blk.get("ci95_scenario")),
                "ci95_pp_task": _pp_ci(blk.get("ci95_task"))}

    share = dec["share_of_rise_from_handoff"]
    ch, cs = pp_block("contribution_handoff"), pp_block("contribution_silenced")
    total = (None if ch["point_pp"] is None or cs["point_pp"] is None
             else ch["point_pp"] + cs["point_pp"])
    return {
        "contribution_handoff": ch,
        "contribution_silenced": cs,
        "share_handoff": {
            "point": share["point"],
            "point_raw": share.get("point_raw"),
            "ci95_scenario": share.get("ci95_scenario"),
            "ci95_task": share.get("ci95_task"),
            "n_resamples_rise_not_positive_scenario": share.get("n_resamples_rise_not_positive_scenario"),
            "n_resamples_rise_not_positive_task": share.get("n_resamples_rise_not_positive_task"),
        },
        "delta_total": pp_block("delta_total"),
        "contributions_sum_pp": total,
        "contributions_sum_to_all": (None if total is None or all_pp is None
                                     else bool(abs(total - all_pp) <= 1e-9)),
        "n": dec["n"],
        "handoff_count": dec["handoff_count"],
        "silenced_count": dec["silenced_count"],
        "share_interval_note": dec["share_interval_note"],
        "source": "j16_robustness.decomposition (the j13_mechanism.measure_m3 estimand); h from the target arm",
    }


def depth_contrast(base: dict[Key, dict[str, Any]], target: dict[Key, dict[str, Any]], field: str,
                   metric: str, n_boot: int, seed: int) -> dict[str, Any]:
    """Target depth minus base depth: all / handoff_only / silenced contrasts + decomposition."""
    comps, meta = paired_components(base, target, field)
    out: dict[str, Any] = {
        name: contrast_object(comps, i, j, metric=metric, threshold_pp=0.0, n_boot=n_boot, seed=seed)
        for name, (i, j) in CONTRAST_PARTS.items()
    }
    out["decomposition"] = decomposition_object(
        j16.decomposition(base, target, field, n_boot), out["all"]["diff_pp"])
    out["pairing"] = meta
    return out


def ni_block(prefix: dict[Key, dict[str, Any]], ceiling: dict[Key, dict[str, Any]], field: str,
             metric: str, n_boot: int, seed: int) -> dict[str, Any]:
    """Prefix arm minus the ceiling at -7 pp: all episodes, and handoff-only (sum d*h / sum h,
    h from the prefix arm, whole scenarios resampled), each with its reading."""
    comps, meta = paired_components(ceiling, prefix, field)
    out: dict[str, Any] = {}
    for name in ("all", "handoff_only"):
        i, j = CONTRAST_PARTS[name]
        c = contrast_object(comps, i, j, metric=metric, threshold_pp=-NI_MARGIN_PP, n_boot=n_boot, seed=seed)
        holds = j16.ni_holds(c["ci95_pp_scenario"], NI_MARGIN_PP)
        holds_task = j16.ni_holds(c["ci95_pp_task"], NI_MARGIN_PP)
        c["reading"] = None if holds is None else ("holds" if holds else "fails")
        c["reading_task"] = None if holds_task is None else ("holds" if holds_task else "fails")
        out[name] = c
    out["pairing"] = meta
    out["rule"] = ("prefix - planner_alone_cap81; holds iff round(scenario lower bound, 2) >= -7.00 "
                   "(j16_robustness.ni_holds, the j8_frontier rule), else fails")
    return out


# --------------------------------------------------------------------------------------
# R1.2  Chord
# --------------------------------------------------------------------------------------


def chord_residuals(arm: dict[str, Any], floor: dict[str, Any], reference: dict[str, Any],
                    field: str) -> tuple[dict[Key, float], Optional[float]]:
    """The per-pair residuals j8_frontier.chord_residual bootstraps (population "survivors"),
    recomputed here only so the same resamples can also give a p value; chord_residual returns
    the interval alone. The caller checks the two agree."""
    a, fl, r = arm["cleaned"], floor["cleaned"], reference["cleaned"]
    usable: list[tuple[Key, list[float], list[float]]] = []
    for k in sorted(set(a) & set(fl) & set(r)):
        rows = (a[k], fl[k], r[k])
        if any(j8.is_crashed(x) for x in rows):
            continue
        costs = [j8.episode_cost(x, COST_KEY) for x in rows]
        qs = [x.get(field) for x in rows]
        if any(c is None for c in costs) or any(q is None for q in qs):
            continue
        usable.append((k, [float(c) for c in costs], [float(q) for q in qs]))
    if not usable:
        return {}, None
    c_arm, c_floor, c_ref = (statistics.fmean(u[1][i] for u in usable) for i in range(3))
    if c_ref == c_floor:
        return {}, None
    f = (c_arm - c_floor) / (c_ref - c_floor)
    return {k: q[0] - (q[1] + f * (q[2] - q[1])) for k, _c, q in usable}, f


def chord_object(arm: dict[str, Any], floor: dict[str, Any], reference: dict[str, Any], field: str,
                 metric: str, n_boot: int, seed: int) -> dict[str, Any]:
    """Registered chord residual: q_arm - [q_floor + f (q_ref - q_floor)], scenario primary."""
    res = j8.chord_residual(arm, floor, reference, field, COST_KEY, "survivors", None, cluster="scenario")
    resid, f = chord_residuals(arm, floor, reference, field)
    out: dict[str, Any] = {
        "metric": metric,
        "residual_mean_pp": res.get("diff_pp"),
        "ci95_pp_scenario": res.get("ci95_pp_scenario"),
        "ci95_pp_task": res.get("ci95_pp_task"),
        "p_two_sided": None,
        "p_two_sided_task": None,
        "threshold_pp": 0.0,
        "n_pairs": res.get("n_pairs"),
        "f": res.get("cost_fraction"),
        "f_note": ("plug-in (c_arm - c_floor) / (c_ref - c_floor) from mean non-cached planner "
                   "tokens over the paired triples; not resampled"),
        "floor_arm": FLOOR_ARM_CITED,
        "floor_label": FLOOR_LABEL,
        "reference_arm": f"{CEILING_LABEL} ({CEILING_C81} seeds 1-2 + {CEILING_C81_S3} seed 3)",
        "cost_key": COST_KEY,
        "cost_arm": res.get("cost_arm"),
        "cost_floor": res.get("cost_floor"),
        "cost_reference": res.get("cost_reference"),
        "n_pairs_shared": res.get("n_pairs_shared"),
        "n_pairs_dropped_crash": res.get("n_pairs_dropped_crash"),
        "pairs_dropped_missing_cost": res.get("pairs_dropped_missing_cost"),
        "pairs_dropped_missing_quality": res.get("pairs_dropped_missing_quality"),
        "positive_means_above_chord": res.get("positive_means_above_chord"),
        "source": "j8_frontier.chord_residual(population='survivors', cluster='scenario')",
    }
    if res.get("note"):
        out["note"] = res["note"]
    if resid:
        keys = sorted(resid)
        vals = [resid[k] for k in keys]
        scen = j10.cluster_bootstrap_means(vals, [scenario_of(str(k[0])) for k in keys], n_boot=n_boot, seed=seed)
        task = j10.cluster_bootstrap_means(vals, [str(k[0]) for k in keys], n_boot=n_boot, seed=seed)
        out["p_two_sided"] = j10.bootstrap_pvalue(scen, 0.0, "two-sided")
        out["p_two_sided_task"] = j10.bootstrap_pvalue(task, 0.0, "two-sided")
        lo, hi = j10.percentile_ci(scen)
        tlo, thi = j10.percentile_ci(task)
        # The floor covers seeds 1-2 only, so the triples do too; say so beside n_pairs.
        out["seeds_paired"] = sorted({k[1] for k in keys})
        out["p_recomputation"] = {
            "residual_mean_pp_unrounded": _pp(statistics.fmean(vals)),
            "f_unrounded": f,
            "n_pairs": len(vals),
            "matches_j8": bool(
                len(vals) == res.get("n_pairs")
                and [round(100 * lo, 2), round(100 * hi, 2)] == res.get("ci95_pp_scenario")
                and [round(100 * tlo, 2), round(100 * thi, 2)] == res.get("ci95_pp_task")
                and round(100 * statistics.fmean(vals), 2) == res.get("diff_pp")
            ),
        }
    return out


def chord_entry(rx: str, arm: dict[str, Any], floor: dict[str, Any], reference: dict[str, Any],
                n_boot: int, seed: int) -> dict[str, Any]:
    """goal_pass (the registered metric) at the top level, tgc beside it."""
    out = chord_object(arm, floor, reference, "goal_pass_rate", "goal_pass", n_boot, seed)
    out["floor_registration"] = FLOOR_REGISTRATION[rx]
    out["tgc"] = chord_object(arm, floor, reference, "tgc", "tgc", n_boot, seed)
    return out


# --------------------------------------------------------------------------------------
# R1.3  Ganz-comparable metrics; R1.4  cost share
# --------------------------------------------------------------------------------------


def _diff_ratio(a: int, b: int, c: int, d: int) -> Callable[[list[float]], Optional[float]]:
    """(t[a] - t[b]) / (t[c] - t[d]) on summed components; undefined when the denominator is 0."""

    def fn(t: list[float]) -> Optional[float]:
        den = t[c] - t[d]
        if den == 0:
            return None
        return (t[a] - t[b]) / den

    return fn


# Component order: goal_pass, hosted calls, usd, each as (arm, floor, ceiling).
GANZ_FIELDS = ("goal_pass_rate", "hosted_calls_per_episode", "usd_per_episode")
GANZ_STATS = {
    "qrec": _diff_ratio(0, 1, 2, 1),                           # (q_arm - q_floor) / (q_ceil - q_floor)
    "savings_retained_hosted_calls": _diff_ratio(5, 3, 5, 4),  # (c_ceil - c_arm) / (c_ceil - c_floor)
    "savings_retained_usd": _diff_ratio(8, 6, 8, 7),
}


def ganz_metrics(arm: dict[Key, dict[str, Any]], floor: dict[Key, dict[str, Any]],
                 ceiling: dict[Key, dict[str, Any]], n_boot: int, seed: int) -> dict[str, Any]:
    """Ganz et al. quality recovery and savings retained on matched (task, seed) triples.

    Each is a ratio of means. Inside every resample the three arms' sums are re-formed from
    the resampled clusters (the n's cancel) and the ratio is taken from them."""
    comps: dict[Key, tuple[float, ...]] = {}
    missing = 0
    for k in sorted(set(arm) & set(floor) & set(ceiling)):
        vals = [rows[k].get(fld) for fld in GANZ_FIELDS for rows in (arm, floor, ceiling)]
        if any(v is None for v in vals):
            missing += 1
            continue
        comps[k] = tuple(float(v) for v in vals)
    blocks: dict[str, dict[str, Any]] = {}
    n_clusters: dict[str, int] = {}
    for unit in ("scenario", "task"):
        b = j16.bootstrap_multi(comps, GANZ_STATS, unit, seed, n_boot)
        n_clusters[unit] = b["n_clusters"]
        for name, st in b["stats"].items():
            blk = blocks.setdefault(name, {"point": st["point"]})
            blk[f"ci95_{unit}"] = st["ci95"]
            blk[f"n_resamples_undefined_{unit}"] = st["n_undefined"]
    n = len(comps)
    means: dict[str, Any] = {}
    for i, name in enumerate(("goal_pass", "hosted_calls", "usd")):
        means[name] = {role: (statistics.fmean(c[3 * i + j] for c in comps.values()) if n else None)
                       for j, role in enumerate(("arm", "floor", "ceiling"))}
    return {
        "qrec": blocks["qrec"],
        "savings_retained": {"hosted_calls": blocks["savings_retained_hosted_calls"],
                             "usd": blocks["savings_retained_usd"]},
        "means": means,
        "n_triples": n,
        "seeds": sorted({k[1] for k in comps}),
        "n_triples_dropped_missing": missing,
        "n_clusters": n_clusters,
        "definition": {"qrec": "(q_arm - q_floor) / (q_ceiling - q_floor) on goal_pass",
                       "savings_retained": "(c_ceiling - c_arm) / (c_ceiling - c_floor), per cost axis"},
        "floor_arm": FLOOR_ARM_CITED,
        "reference_arm": CEILING_LABEL,
    }


def cost_share(arm: dict[Key, dict[str, Any]], ceiling: dict[Key, dict[str, Any]], n_boot: int,
               seed: int) -> dict[str, Any]:
    """Arm hosted calls / ceiling hosted calls, and 1 - arm USD / ceiling USD, paired, with
    j16.cost_contrast's ratio-of-means intervals (both clusterings)."""
    boots = (("scenario", seed), ("task", seed))
    calls = j16.cost_contrast(arm, ceiling, "hosted_calls_per_episode", boots, n_boot)
    usd = j16.cost_contrast(arm, ceiling, "usd_per_episode", boots, n_boot)

    def ci(c: dict[str, Any], unit: str) -> Optional[list[float]]:
        return c[j16._boot_name(unit, seed)]["ratio_ci95"]

    def flip(v: Optional[list[float]]) -> Optional[list[float]]:
        return None if v is None else [1.0 - v[1], 1.0 - v[0]]

    ratio = usd["ratio_left_over_right"]
    return {
        "calls_fraction": {
            "point": calls["ratio_left_over_right"],
            "ci95_scenario": ci(calls, "scenario"),
            "ci95_task": ci(calls, "task"),
            "calls_arm": calls["mean_left"],
            "calls_ceiling": calls["mean_right"],
            "n_pairs": calls["n_pairs"],
            "n_dropped_missing": calls["n_dropped_missing"],
        },
        "dollar_saving_retained": {
            "point": None if ratio is None else 1.0 - ratio,
            "ci95_scenario": flip(ci(usd, "scenario")),
            "ci95_task": flip(ci(usd, "task")),
            "usd_fraction": ratio,
            "usd_arm": usd["mean_left"],
            "usd_ceiling": usd["mean_right"],
            "n_pairs": usd["n_pairs"],
            "n_dropped_missing": usd["n_dropped_missing"],
        },
        "reference_arm": CEILING_LABEL,
        "definition": {"calls_fraction": "mean arm hosted calls / mean ceiling hosted calls (replay-inclusive)",
                       "dollar_saving_retained": "(usd_ceiling - usd_arm) / usd_ceiling = 1 - usd ratio"},
    }


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------


def build_report(results_root: Path | str, n_boot: int = N_BOOT, seed: int = SEED) -> dict[str, Any]:
    results_root = Path(results_root)
    sources = family_sources(results_root)
    refuse_inputs(results_root, sources)
    price_card = j12.load_price_card(j16.PRICES)
    roles = {"ceiling": f"ceiling {CEILING_LABEL}", "floor": f"chord and Ganz floor {FLOOR_LABEL}"}
    for rx in RECEIVERS:
        for m in DEPTHS:
            roles[f"{rx}_m{m}"] = f"prefix {rx} m{m} (pooled cap-81 family)"

    with bootstrap_settings(n_boot, seed):
        depth: dict[str, dict[Key, dict[str, Any]]] = {}
        cost: dict[str, dict[str, Any]] = {}
        dirs: dict[str, Any] = {}
        agreement: dict[str, Any] = {}
        for label, srcs in sources.items():
            print(f"[j17] loading {label} ...", flush=True)
            rows, entries = load_depth_rows(srcs)
            depth[label] = drop_crashed(rows)
            cost_label = {"floor": FLOOR_LABEL, "ceiling": CEILING_LABEL}.get(label, f"prefix_c81_{label}")
            cost_arm, per_root = load_cost_rows(cost_label, srcs, price_card)
            cost[label] = cost_survivors(cost_arm)
            for entry, pr in zip(entries, per_root):
                entry["role"] = roles[label]
                entry["cost_rows"] = pr
                dirs[entry["campaign_dir"]] = entry
            agreement[label] = loader_agreement(rows, cost_arm["cleaned"])
        floor_src = sources["floor"][0]
        floor_costing = dirs[str(floor_src["root"])]["cost_rows"]["sft_plan_floor_costing"]
        inputs: dict[str, Any] = {
            "campaign_dirs": dirs,
            "n_campaign_dirs": len(dirs),
            "n_episodes_total": sum(e["n_episodes"] for e in dirs.values()),
            "n_crash_total": sum(e["n_crash"] for e in dirs.values()),
            "packet_sources": {
                str(floor_src["packet_source"]): {
                    "role": "the sft_plan floor's plan packet source: its plan-event tokens and USD only",
                    "n_plan_events_mapped": floor_costing.get("n_mapped"),
                    "n_missing": floor_costing.get("n_missing"),
                },
                "prefix arms": "each prefix root is priced against its own ceiling root (hj17 -> "
                               f"{CEILING_C81}, hj18 -> {CEILING_C81_S3}), listed under campaign_dirs",
            },
            "loader_agreement": agreement,
        }

        print("[j17] handoff-only blocks ...", flush=True)
        handoff_only = {rx: {f"m{m}": handoff_arm_block(depth[f"{rx}_m{m}"], n_boot) for m in DEPTHS}
                        for rx in RECEIVERS}
        print("[j17] depth contrasts ...", flush=True)
        contrasts = {
            rx: {f"m{a}_to_m{b}": {metric: depth_contrast(depth[f"{rx}_m{a}"], depth[f"{rx}_m{b}"],
                                                          field, metric, n_boot, seed)
                                   for metric, field in METRICS}
                 for a, b in DEPTH_PAIRS}
            for rx in RECEIVERS
        }
        print("[j17] non-inferiority ...", flush=True)
        ni = {rx: {f"m{m}": {metric: ni_block(depth[f"{rx}_m{m}"], depth["ceiling"], field, metric, n_boot, seed)
                             for metric, field in METRICS}
                   for m in NI_DEPTHS}
              for rx in RECEIVERS}
        print("[j17] chord ...", flush=True)
        chord = {rx: {f"m{m}": chord_entry(rx, cost[f"{rx}_m{m}"], cost["floor"], cost["ceiling"], n_boot, seed)
                      for m in CHORD_DEPTHS}
                 for rx in RECEIVERS}
        print("[j17] Ganz metrics and cost share ...", flush=True)
        ganz = {rx: {f"m{m}": ganz_metrics(cost[f"{rx}_m{m}"]["cleaned"], cost["floor"]["cleaned"],
                                           cost["ceiling"]["cleaned"], n_boot, seed)
                     for m in DEPTHS}
                for rx in RECEIVERS}
        shares = {rx: {f"m{m}": cost_share(cost[f"{rx}_m{m}"]["cleaned"], cost["ceiling"]["cleaned"], n_boot, seed)
                       for m in DEPTHS}
                  for rx in RECEIVERS}

    report: dict[str, Any] = {
        "generated_by": "scripts/analysis/j17_depth_fixes.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": ("Adversarial review F1 fixes R1.1-R1.4 and R7.2 on dev: handoff-only and silenced "
                    "numbers, their decomposition, NI at -7 pp, the registered chord, Ganz metrics and "
                    "cost shares, on the pooled cap-81 prefix family (seeds 1-3) against the planner "
                    "alone at cap 81."),
        "sources": {"review": "docs/review_paperA_adversarial_20260923.md §F1",
                    "fix_register": "docs/plan_review_fixes_20260923.md §1 (R1.1-R1.4, R7.2)",
                    "chord_registration": FLOOR_REGISTRATION},
        "conventions": {
            "population": "error_type == 'crash' excluded from every pair (counted in inputs); 'limit' scored",
            "pairing": "(task_id, seed); both rows j10-clean (j16_robustness.paired_diffs)",
            "handoff_flag": "the prefix arm's handoff_occurred; missing counts as silenced (h = 0) and is counted",
            "handoff_only_estimand": "sum(d*h) / sum(h), whole clusters resampled",
            "clusterings": "scenario (19) primary, task (57) secondary; percentile int(0.025 B), int(0.975 B)",
            "p_two_sided": ("2 x smaller tail share of the scenario bootstrap statistic at threshold_pp "
                            "(j10_report.bootstrap_pvalue); p_signflip_two_sided is "
                            "cluster_inference.registered_signflip over scenarios at the same threshold"),
            "ni_margin_pp": NI_MARGIN_PP,
            "units": "*_pp in percentage points; means, ratios, shares, qrec and savings in native units",
        },
        "handoff_only": handoff_only,
        "handoff_only_contrasts": contrasts,
        "ni": ni,
        "chord": chord,
        "ganz": ganz,
        "cost_share": shares,
        "inputs": inputs,
        "settings": {"n_boot": int(n_boot), "seed": int(seed), "results_root": str(results_root)},
    }
    return j16.round_floats(report)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--results-root", type=Path, default=RESULTS_DIR)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        refuse_path(args.out)
        refuse_inputs(args.results_root, family_sources(args.results_root))
        if str(Path(args.out).resolve()).startswith(str(Path(args.results_root).resolve())):
            raise RefusedPath(f"refusing to write under {args.results_root}")
        report = build_report(args.results_root, args.n_boot, args.seed)
    except RefusedPath as exc:
        print(f"[j17] {exc}", file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[j17] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
