#!/usr/bin/env python3
"""BFCL dev read (exploratory): per-arm means and the paired contrasts of the BFCL dev prereg §6.

Implements §6 "The dev read" of docs/prereg_bfcl_dev_20260924.md over the arms of its §4. Nothing here
carries a decision rule: every interval is exploratory, and the numbers size the BFCL test prereg
(docs/prereg_bfcl_test_20260925.md, the E-prereg), whose power script is scripts/analysis/bfcl_power.py.

Inputs. The arm set is every configs/bfcl_<arm>.yaml; each config's campaign_id must be
bfcl_<arm>_dev_20260924, and the arm's episodes are every result.json under
<results root>/<campaign_id>/ (layout <system>/<seed>/<entry id>/{result.json, events.jsonl}).
A campaign that does not exist yet is normal: its arm, and every contrast that needs it, is written as
null with a "reason".

Pairing is by (entry id, seed). A pair is dropped, and counted, when either side is missing, either side
is error_type "crash", or either side lacks the metric. Any other error_type (e.g. "limit") is an outcome
and stays in the pair.

Clustering is by the entry id: all seeds of one entry are resampled together. hj1_gate.scenario_of must
never be used on BFCL ids: it strips the trailing "_n", so every multi_turn_base_<n> becomes one cluster
(scripts/setup/hj1_gate.py:45-47). Plain contrasts reuse j10_report.cluster_bootstrap_means (:2001) with
entry labels; the ratio (B1) and difference-in-differences bootstraps copy its draw sequence.

Dev only: any path naming test_normal, test_challenge or _test_ is refused, and so is any campaign id
without _dev_ (j16_robustness.refuse_heldout, :136-140, plus the _test_ marker).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

from scripts.analysis import handoff_control as hc  # noqa: E402
from scripts.analysis.j10_report import (  # noqa: E402
    bootstrap_pvalue,
    cluster_bootstrap_means,
    percentile_ci,
)

Key = tuple[str, int]  # (entry id, seed)

RESULTS = Path("/scratch/n12194778/sidekick/results")
CONFIGS_DIR = REPO_ROOT / "configs"
DEFAULT_OUT = REPO_ROOT / "campaign" / "results" / "bfcl_dev_20260924.report.json"
CAMPAIGN_SUFFIX = "_dev_20260924"
DEV_SEEDS = (1, 2, 3)  # dev prereg §4 (frozen f56bf32): every arm at seeds 1, 2, 3
N_DEV_ENTRIES = 50  # data/bfcl_split_20260924.json n_dev (dev prereg §1)
N_BOOT = 10_000
SEED = 20260925
NI_MARGIN = -0.07  # -7.00 pp, J9's and J10's margin (E-prereg §4)
HELD_OUT_MARKERS = ("test_normal", "test_challenge", "_test_")
CRASH = "crash"
LIMIT = "limit"
METRICS = ("goal_pass", "success")  # report name; the row field has the same name

# The arms of dev prereg §4, in its order. The arm set actually read is every configs/bfcl_<arm>.yaml;
# this tuple only names the arms the contrasts expect, so a missing config is reported, not guessed.
EXPECTED_ARMS = (
    "executor_alone_zs", "plan_zs", "takeover_k5", "advise_k5_fullctx", "advise_k5_neutral",
    "prefix_zs_m2", "prefix_zs_m4", "prefix_zs_m6",
    "executor_alone_bplus", "prefix_bplus_m2", "prefix_bplus_m4", "prefix_bplus_m6",
    "executor_alone_qzs", "plan_qzs", "takeover_k5_qzs", "advise_k5_fullctx_qzs", "advise_k5_neutral_qzs",
    "prefix_qzs_m2", "prefix_qzs_m4", "prefix_qzs_m6",
    "planner_alone_cap81",
)

# id -> spec. kind: plain | ni (non-inferiority at NI_MARGIN) | hstar / flag (handoff-only B1,
# Σd·h/Σh with h from the LEFT (prefix) arm) | depth (plain, with the m4 arm's mean beside it).
CONTRASTS: dict[str, dict[str, Any]] = {
    "P6": dict(left="takeover_k5", right="advise_k5_fullctx", kind="plain"),
    "CF1": dict(left="advise_k5_neutral", right="advise_k5_fullctx", kind="plain"),
    "CF3": dict(left="takeover_k5", right="advise_k5_neutral", kind="plain"),
    "P3_zs_m6": dict(left="prefix_zs_m6", right="planner_alone_cap81", kind="ni"),
    "P3_bplus_m6": dict(left="prefix_bplus_m6", right="planner_alone_cap81", kind="ni"),
    "B1_zs_m6_hstar": dict(left="prefix_zs_m6", right="planner_alone_cap81", kind="hstar"),
    "B1_bplus_m6_hstar": dict(left="prefix_bplus_m6", right="planner_alone_cap81", kind="hstar"),
    "B1_zs_m6_flag": dict(left="prefix_zs_m6", right="planner_alone_cap81", kind="flag"),
    "B1_bplus_m6_flag": dict(left="prefix_bplus_m6", right="planner_alone_cap81", kind="flag"),
    "depth_zs": dict(left="prefix_zs_m6", right="prefix_zs_m2", kind="depth", m4="prefix_zs_m4"),
    "depth_bplus": dict(left="prefix_bplus_m6", right="prefix_bplus_m2", kind="depth", m4="prefix_bplus_m4"),
    "depth_qzs": dict(left="prefix_qzs_m6", right="prefix_qzs_m2", kind="depth", m4="prefix_qzs_m4"),
    "tailor_bplus_zs": dict(left="executor_alone_bplus", right="executor_alone_zs", kind="plain"),
    "plan_zs": dict(left="plan_zs", right="executor_alone_zs", kind="plain"),
    "P6_qzs": dict(left="takeover_k5_qzs", right="advise_k5_fullctx_qzs", kind="plain"),
    "CF1_qzs": dict(left="advise_k5_neutral_qzs", right="advise_k5_fullctx_qzs", kind="plain"),
    "CF3_qzs": dict(left="takeover_k5_qzs", right="advise_k5_neutral_qzs", kind="plain"),
    "plan_qzs": dict(left="plan_qzs", right="executor_alone_qzs", kind="plain"),
    "P3_qzs_m6": dict(left="prefix_qzs_m6", right="planner_alone_cap81", kind="ni"),
}

# Receiver difference-in-differences: the zs contrast minus its qzs repeat, both recomputed per resample.
DID: dict[str, tuple[str, str]] = {
    "did_P6": ("P6", "P6_qzs"),
    "did_CF1": ("CF1", "CF1_qzs"),
    "did_depth": ("depth_zs", "depth_qzs"),
    "did_plan": ("plan_zs", "plan_qzs"),
}

DEFINITIONS = {
    "n": "readable result.json files of the arm at the requested seeds (meta.seeds), crashes included",
    "n_expected": "50 dev entries x the requested seeds (150 at seeds 1, 2, 3; dev prereg §4)",
    "complete": ("arm: non-crash episodes >= n_expected, n_crash == 0, and every requested seed holds 50; "
                 "contrast: every arm it reads is complete. Incomplete rows are still computed and labelled, "
                 "never refused"),
    "calls_live_reason": ("set, with calls_live_mean null, when any non-crash episode's ledger total minus its "
                          "cached-plan calls is negative; the count is not clamped"),
    "means": ("goal_pass_mean, success_mean, calls_*_mean and limit_rate are over the arm's non-crash "
              "episodes (n - n_crash); success is result.json success (tgc when success is absent)"),
    "limit_rate": "share of non-crash episodes with error_type 'limit'",
    "calls_ledger_mean": "result.json totals.planner_calls_total (the ledger key; a replayed plan adds 1)",
    "calls_live_mean": ("hosted planner calls: totals.planner_calls_total minus usage.n_calls (1 when absent) "
                        "of the episode's own planner events with usage.provider == 'cache', last attempt "
                        "(dev prereg §5; the cached-record rule of j12_cost_axes.cached_plan_usages :743 and "
                        "episode_cached_plan_attribution :812-815)"),
    "calls_attributed_mean": ("result.json n_planner_calls: the count as published, a replayed plan as one "
                              "call and a prefix arm charged its replayed prefix (j10_report A1_AM4_DEFINITIONS "
                              ":4055-4059, commit f690b6a)"),
    "hstar": hc.DEFINITION + "; counted over the arm's non-crash episodes; missing = no handoff record",
    "h_flag": hc.FLAG_DEFINITION,
    "pairing": ("(entry id, seed); a pair is dropped if either side is missing, either side is error_type "
                "'crash', or either side lacks the metric; n_dropped counts every dropped key of the union"),
    "cluster": "entry id; all seeds of an entry are resampled together (never hj1_gate.scenario_of)",
    "ci95_entry": "percentile 95% entry-cluster bootstrap, pp; EXPLORATORY",
    "sd_pp": "sample SD (n-1) of the per-pair differences, pp (B1: over the handoff pairs)",
    "p_two_sided": "j10_report.bootstrap_pvalue(means, 0, 'two-sided')",
    "p_ni": "j10_report.bootstrap_pvalue(means, -0.07, 'greater') = 2 x share of replicates <= -7.00 pp",
    "B1": ("Σd·h/Σh over the pairs of the P3 row, h from the prefix (left) arm; a missing h counts as 0 and "
           "is counted; bootstrap resamples entries and recomputes the ratio, replicates with Σh = 0 dropped"),
    "did": ("the zs contrast minus its qzs repeat, each over its own pairs; each resample draws entries from "
            "the union and recomputes both means; replicates where either side has no pair are dropped"),
}


# ---- refusals (dev only) -------------------------------------------------------------------------
def refuse_path(path: Path | str) -> None:
    """j16_robustness.refuse_heldout (:136-140) with the BFCL test marker `_test_` added."""
    text = str(path)
    for marker in HELD_OUT_MARKERS:
        if marker in text:
            raise RuntimeError(f"refusing held-out split path {path} (marker {marker!r})")


def refuse_campaign(campaign_id: str) -> None:
    refuse_path(campaign_id)
    if "_dev_" not in campaign_id:
        raise RuntimeError(f"refusing campaign id without _dev_: {campaign_id!r}")


# ---- configuration -------------------------------------------------------------------------------
def campaign_of(arm: str) -> str:
    return f"bfcl_{arm}{CAMPAIGN_SUFFIX}"


def configured_arms(configs_dir: Path = CONFIGS_DIR) -> dict[str, str]:
    """arm -> campaign id for every configs/bfcl_<arm>.yaml; each campaign_id must equal the arm's name."""
    out: dict[str, str] = {}
    for path in sorted(Path(configs_dir).glob("bfcl_*.yaml")):
        arm = path.stem[len("bfcl_"):]
        cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cid = cfg.get("campaign_id") if isinstance(cfg, dict) else None
        expected = campaign_of(arm)
        if cid != expected:
            raise ValueError(f"{path}: campaign_id {cid!r} != {expected!r}")
        refuse_campaign(cid)
        out[arm] = cid
    return out


# ---- loading -------------------------------------------------------------------------------------
def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int(value: Any) -> Optional[int]:
    v = _num(value)
    return None if v is None else int(v)


def cache_plan_calls(events: list[dict[str, Any]]) -> tuple[int, int]:
    """(n cached planner records, calls they were charged) in the last attempt.

    The rule of j12_cost_axes: planner events of the last attempt whose usage.provider is "cache"
    (cached_plan_usages :743-745, extract_events_usages :233-262), each charged usage.n_calls, 1 when
    absent (episode_cached_plan_attribution :812-815).
    """
    n_rec = calls = 0
    for ev in hc.last_attempt(events):
        usage = ev.get("usage")
        if ev.get("actor") == "planner" and isinstance(usage, dict) and usage.get("provider") == "cache":
            n_rec += 1
            n = usage.get("n_calls")
            calls += int(n) if n is not None else 1
    return n_rec, calls


def episode_row(result: dict[str, Any], ep_dir: Path) -> dict[str, Any]:
    events = hc.read_events(ep_dir / "events.jsonl") if (ep_dir / "events.jsonl").is_file() else []
    n_cached, cache_calls = cache_plan_calls(events)
    totals = result.get("totals") if isinstance(result.get("totals"), dict) else {}
    succ = result.get("success")
    success = float(bool(succ)) if isinstance(succ, bool) else _num(result.get("tgc"))
    error_type = result.get("error_type")
    return {
        "error_type": error_type,
        "crash": error_type == CRASH,
        "goal_pass": _num(result.get("goal_pass_rate")),
        "success": success,
        "n_planner_calls": _int(result.get("n_planner_calls")),
        "ledger_calls": _int(totals.get("planner_calls_total")),
        "n_cached_plan_events": n_cached,
        "cache_calls": cache_calls,
        "h_flag": hc.last_report_flag(events),
    }


def load_arm(root: Path, arm: str, campaign_id: Optional[str] = None,
             seeds: Iterable[int] = DEV_SEEDS) -> dict[str, Any]:
    """Every result.json of one arm's campaign at the requested seeds. The first result.json per key wins
    (sorted paths), as j10_report.a1_am4_episode_files and handoff_control.arm_control read them; later
    ones are counted."""
    allowed = {int(s) for s in seeds}
    cid = campaign_id or campaign_of(arm)
    refuse_campaign(cid)
    cdir = Path(root) / cid
    refuse_path(cdir)
    out: dict[str, Any] = {"arm": arm, "campaign_id": cid, "dir": str(cdir), "present": False,
                           "reason": None, "rows": {}, "diag": {}}
    if not cdir.is_dir():
        out["reason"] = f"campaign directory absent: {cdir}"
        return out
    rows: dict[Key, dict[str, Any]] = {}
    diag: Counter[str] = Counter()
    duplicates: list[str] = []
    for path in sorted(cdir.rglob("result.json")):
        refuse_path(path)
        result = _read_json(path)
        if not isinstance(result, dict):
            diag["n_unreadable"] += 1
            continue
        if result.get("task_id") is None or result.get("seed") is None:
            diag["n_missing_key"] += 1
            continue
        key = (str(result["task_id"]), int(result["seed"]))
        if key[1] not in allowed:
            diag["n_seed_filtered"] += 1
            continue
        if key in rows:
            diag["n_duplicates"] += 1
            duplicates.append(str(path))
            continue
        rows[key] = episode_row(result, path.parent)
    out["rows"] = rows
    out["diag"] = {**{k: int(diag.get(k, 0)) for k in ("n_unreadable", "n_missing_key", "n_seed_filtered",
                                                          "n_duplicates")}, "duplicates": duplicates}
    if rows:
        out["present"] = True
    else:
        out["reason"] = f"campaign directory holds no readable dev result.json: {cdir}"
    return out


def hstar_for(arm_data: dict[str, Any], seeds: Iterable[int] = DEV_SEEDS) -> dict[Key, Optional[bool]]:
    """h* of a prefix arm via handoff_control.hstar_flags (:278) on its campaign root."""
    if not arm_data.get("present"):
        return {}
    return hc.hstar_flags(Path(arm_data["dir"]), seeds=tuple(seeds))


# ---- per-arm block -------------------------------------------------------------------------------
def _mean(values: list[float]) -> Optional[float]:
    return round(statistics.fmean(values), 6) if values else None


ARM_KEYS = ("n", "n_crash", "seeds", "n_by_seed", "complete", "complete_reason", "goal_pass_mean",
            "success_mean", "n_goal_pass_missing", "limit_rate", "error_types", "calls_live_mean",
            "calls_live_reason", "calls_ledger_mean", "calls_attributed_mean", "n_cached_plan_events",
            "calls_attributed_reason")
HSTAR_KEYS = ("hstar_true", "hstar_false", "hstar_missing", "h_flag_true", "h_flag_false", "h_flag_missing")


def n_expected_for(seeds: Iterable[int]) -> int:
    return N_DEV_ENTRIES * len(tuple(seeds))


def completeness(n_scored: int, n_crash: int, by_seed: Counter, seeds: Iterable[int]) -> tuple[bool, Optional[str]]:
    """Dev prereg §4: every arm runs the 50 dev entries at every requested seed (150 at seeds 1-3).
    Complete = non-crashed episodes >= n_expected, no crash, and every requested seed holds 50."""
    seeds = tuple(seeds)
    why = []
    if n_scored < n_expected_for(seeds):
        why.append(f"{n_scored} non-crash episodes < {n_expected_for(seeds)} expected")
    if n_crash:
        why.append(f"{n_crash} crashed")
    short = [f"seed {s}: {by_seed.get(s, 0)}/{N_DEV_ENTRIES}" for s in seeds if by_seed.get(s, 0) < N_DEV_ENTRIES]
    if short:
        why.append("seeds short -- " + ", ".join(short))
    return (not why), ("; ".join(why) if why else None)


def arm_block(arm_data: dict[str, Any], hstar: Optional[dict[Key, Optional[bool]]] = None,
              seeds: Iterable[int] = DEV_SEEDS) -> dict[str, Any]:
    seeds = tuple(seeds)
    is_prefix = arm_data["arm"].startswith("prefix_")
    base: dict[str, Any] = {"campaign_id": arm_data["campaign_id"], "present": bool(arm_data.get("present")),
                            "reason": arm_data.get("reason"), "n_expected": n_expected_for(seeds)}
    if not arm_data.get("present"):
        base.update({k: None for k in ARM_KEYS})
        base.update({"complete": False, "complete_reason": arm_data.get("reason")})
        if is_prefix:
            base.update({k: None for k in HSTAR_KEYS})
        return base
    rows = arm_data["rows"]
    scored = {k: r for k, r in rows.items() if not r["crash"]}
    gp = [r["goal_pass"] for r in scored.values() if r["goal_pass"] is not None]
    sc = [r["success"] for r in scored.values() if r["success"] is not None]
    live = [float(r["ledger_calls"] - r["cache_calls"]) for r in scored.values() if r["ledger_calls"] is not None]
    # A negative live count means the cached records exceed the ledger: the convention does not hold
    # for this arm, so the mean is withheld rather than clamped.
    n_negative = sum(1 for v in live if v < 0)
    ledger = [float(r["ledger_calls"]) for r in scored.values() if r["ledger_calls"] is not None]
    attributed = [float(r["n_planner_calls"]) for r in scored.values() if r["n_planner_calls"] is not None]
    n_no_calls = sum(1 for r in scored.values() if r["n_planner_calls"] is None)
    by_seed = Counter(k[1] for k in rows)
    complete, complete_reason = completeness(len(scored), len(rows) - len(scored), by_seed, seeds)
    block = {
        **base,
        "n": len(rows),
        "n_crash": len(rows) - len(scored),
        "seeds": sorted(by_seed),
        "n_by_seed": {str(s): by_seed[s] for s in sorted(by_seed)},
        "complete": complete,
        "complete_reason": complete_reason,
        "goal_pass_mean": _mean(gp),
        "success_mean": _mean(sc),
        "n_goal_pass_missing": len(scored) - len(gp),
        "limit_rate": round(sum(1 for r in scored.values() if r["error_type"] == LIMIT) / len(scored), 6)
        if scored else None,
        "error_types": dict(sorted(Counter(str(r["error_type"] or "none") for r in rows.values()).items())),
        "calls_live_mean": None if n_negative else _mean(live),
        "calls_live_reason": (f"{n_negative} non-crash episodes have totals.planner_calls_total minus cached-plan "
                              f"calls < 0; not clamped" if n_negative else None),
        "calls_ledger_mean": _mean(ledger),
        "calls_attributed_mean": _mean(attributed),
        "n_cached_plan_events": sum(r["n_cached_plan_events"] for r in scored.values()),
        "calls_attributed_reason": (f"{n_no_calls} non-crash episodes lack n_planner_calls" if n_no_calls
                                    else None),
        "diagnostics": arm_data["diag"],
    }
    if is_prefix:
        hs = hstar or {}
        vals = [hs.get(k) for k in scored]
        flags = [r["h_flag"] for r in scored.values()]
        block.update({
            "hstar_true": sum(1 for v in vals if v is True),
            "hstar_false": sum(1 for v in vals if v is False),
            "hstar_missing": sum(1 for v in vals if v is None),
            "h_flag_true": sum(1 for v in flags if v is True),
            "h_flag_false": sum(1 for v in flags if v is False),
            "h_flag_missing": sum(1 for v in flags if v is None),
        })
    return block


# ---- pairing and bootstraps ----------------------------------------------------------------------
def paired_series(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]], field: str) -> dict[str, Any]:
    """Left − right by (entry, seed), in the manner of j10_report.a1_paired_series (:2073) with the
    crash and one-side-missing drops counted."""
    keys: list[Key] = []
    diffs: list[float] = []
    lvals: list[float] = []
    rvals: list[float] = []
    drops: Counter[str] = Counter()
    for key in sorted(set(left) | set(right)):
        a, b = left.get(key), right.get(key)
        if a is None:
            drops["left_missing"] += 1
            continue
        if b is None:
            drops["right_missing"] += 1
            continue
        if a["crash"] or b["crash"]:
            drops["crash"] += 1
            continue
        va, vb = a.get(field), b.get(field)
        if va is None or vb is None:
            drops["metric_missing"] += 1
            continue
        keys.append(key)
        diffs.append(float(va) - float(vb))
        lvals.append(float(va))
        rvals.append(float(vb))
    return {"keys": keys, "diffs": diffs, "left": lvals, "right": rvals, "n_dropped": sum(drops.values()),
            "dropped": {k: int(drops.get(k, 0)) for k in ("left_missing", "right_missing", "crash",
                                                           "metric_missing")}}


def entry_labels(keys: list[Key]) -> list[str]:
    """The cluster label of a pair is its entry id (never hj1_gate.scenario_of)."""
    return [k[0] for k in keys]


def cluster_bootstrap_stat(
    groups: dict[str, Any],
    stat: Callable[[list[str]], Optional[float]],
    *,
    n_boot: int,
    seed: int,
) -> list[float]:
    """Sorted replicate values of `stat` over entry resamples; replicates where it is None are dropped.

    The draw sequence is copied from j10_report.cluster_bootstrap_means (scripts/analysis/j10_report.py
    :2015-2029): labels sorted, one random.Random(seed), G draws of randrange(G) per replicate.
    """
    labels = sorted(groups)
    g = len(labels)
    rng = random.Random(seed)
    out: list[float] = []
    for _ in range(n_boot):
        drawn = [labels[rng.randrange(g)] for _ in range(g)]
        value = stat(drawn)
        if value is not None:
            out.append(value)
    out.sort()
    return out


def _pp(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x * 100, 2)


def _sd_pp(values: list[float]) -> Optional[float]:
    return round(statistics.stdev(values) * 100, 3) if len(values) >= 2 else None


def _ni_fields(lo: Optional[float], means: list[float]) -> dict[str, Any]:
    return {
        "margin_pp": round(NI_MARGIN * 100, 2),
        "lower_above_margin": None if lo is None else bool(lo > NI_MARGIN),
        "p_ni": round(bootstrap_pvalue(means, NI_MARGIN, "greater"), 6) if means else None,
    }


def plain_metric(series: dict[str, Any], *, n_boot: int, seed: int, ni: bool = False) -> Optional[dict[str, Any]]:
    """Paired mean with its entry-cluster percentile interval (j10_report.cluster_bootstrap_means)."""
    diffs = series["diffs"]
    if not diffs:
        return None
    clusters = entry_labels(series["keys"])
    n_clusters = len(set(clusters))
    assert n_clusters == len({k[0] for k in series["keys"]}), "cluster unit must be the entry id"
    means = cluster_bootstrap_means(diffs, clusters, n_boot=n_boot, seed=seed)
    lo, hi = percentile_ci(means)
    block = {
        "diff_pp": _pp(statistics.fmean(diffs)),
        "ci95_entry": [_pp(lo), _pp(hi)],
        "sd_pp": _sd_pp(diffs),
        "left_mean": round(statistics.fmean(series["left"]), 6),
        "right_mean": round(statistics.fmean(series["right"]), 6),
        "n_pairs": len(diffs),
        "n_clusters": n_clusters,
        "n_dropped": series["n_dropped"],
        "dropped": series["dropped"],
        "p_two_sided": round(bootstrap_pvalue(means, 0.0, "two-sided"), 6),
        "exploratory": True,
    }
    if ni:
        block.update(_ni_fields(lo, means))
    return block


def handoff_metric(
    series: dict[str, Any],
    h_by_key: dict[Key, Optional[bool]],
    *,
    n_boot: int,
    seed: int,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """B1: Σd·h/Σh over the pairs, h from the prefix arm (missing -> 0, counted), entry bootstrap."""
    if not series["diffs"]:
        return None, "no pairs"
    hs: list[float] = []
    n_missing = 0
    for key in series["keys"]:
        v = h_by_key.get(key)
        n_missing += int(v is None)
        hs.append(1.0 if v is True else 0.0)
    den = sum(hs)
    if den == 0:
        return None, "no handoff pair (sum of h = 0)"
    point = sum(d * h for d, h in zip(series["diffs"], hs)) / den
    groups: dict[str, list[float]] = {}
    for key, d, h in zip(series["keys"], series["diffs"], hs):
        g = groups.setdefault(key[0], [0.0, 0.0])
        g[0] += d * h
        g[1] += h

    def ratio(drawn: list[str]) -> Optional[float]:
        num = dn = 0.0
        for label in drawn:
            n_, d_ = groups[label]
            num += n_
            dn += d_
        return num / dn if dn > 0 else None

    means = cluster_bootstrap_stat(groups, ratio, n_boot=n_boot, seed=seed)
    lo, hi = percentile_ci(means) if means else (None, None)
    block = {
        "diff_pp": _pp(point),
        "ci95_entry": [_pp(lo), _pp(hi)],
        "sd_pp": _sd_pp([d for d, h in zip(series["diffs"], hs) if h]),
        "n_handoff": int(den),
        "n_h_missing": n_missing,
        "n_pairs": len(series["diffs"]),
        "n_clusters": len(groups),
        "n_dropped": series["n_dropped"],
        "dropped": series["dropped"],
        "n_boot_valid": len(means),
        "p_two_sided": round(bootstrap_pvalue(means, 0.0, "two-sided"), 6) if means else None,
        "exploratory": True,
        **_ni_fields(lo, means),
    }
    return block, None


def did_metric(
    zs: dict[str, Any],
    qzs: dict[str, Any],
    *,
    n_boot: int,
    seed: int,
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """(mean of zs diffs) − (mean of qzs diffs), each over its own pairs; entries resampled jointly."""
    if not zs["diffs"] or not qzs["diffs"]:
        return None, "a side has no pairs"
    groups: dict[str, list[float]] = {}
    for idx, series in ((0, zs), (2, qzs)):
        for key, d in zip(series["keys"], series["diffs"]):
            g = groups.setdefault(key[0], [0.0, 0.0, 0.0, 0.0])
            g[idx] += d
            g[idx + 1] += 1.0

    def did(drawn: list[str]) -> Optional[float]:
        s0 = n0 = s1 = n1 = 0.0
        for label in drawn:
            a, b, c, e = groups[label]
            s0 += a
            n0 += b
            s1 += c
            n1 += e
        return (s0 / n0 - s1 / n1) if n0 > 0 and n1 > 0 else None

    point = statistics.fmean(zs["diffs"]) - statistics.fmean(qzs["diffs"])
    means = cluster_bootstrap_stat(groups, did, n_boot=n_boot, seed=seed)
    lo, hi = percentile_ci(means) if means else (None, None)
    zs_entries = {k[0] for k in zs["keys"]}
    q_entries = {k[0] for k in qzs["keys"]}
    return {
        "diff_pp": _pp(point),
        "ci95_entry": [_pp(lo), _pp(hi)],
        "zs_diff_pp": _pp(statistics.fmean(zs["diffs"])),
        "qzs_diff_pp": _pp(statistics.fmean(qzs["diffs"])),
        "n_pairs_zs": len(zs["diffs"]),
        "n_pairs_qzs": len(qzs["diffs"]),
        "n_clusters": len(groups),
        "n_clusters_common": len(zs_entries & q_entries),
        "n_boot_valid": len(means),
        "p_two_sided": round(bootstrap_pvalue(means, 0.0, "two-sided"), 6) if means else None,
        "exploratory": True,
    }, None


# ---- contrasts -----------------------------------------------------------------------------------
def _absent_reason(arms: dict[str, dict[str, Any]], names: Iterable[str]) -> Optional[str]:
    parts = []
    for name in names:
        data = arms.get(name)
        if data is None:
            parts.append(f"{name}: no configs/bfcl_{name}.yaml")
        elif not data.get("present"):
            parts.append(f"{name}: {data.get('reason')}")
    return ("arm absent -- " + "; ".join(parts)) if parts else None


def contrast_block(
    cid: str,
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    hstars: dict[str, dict[Key, Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
    arm_blocks: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """One contrast's public block, and its per-metric paired series (kept for did_*)."""
    left, right, kind = spec["left"], spec["right"], spec["kind"]
    out: dict[str, Any] = {"left": left, "right": right, "kind": kind, "reason": None}
    series: dict[str, dict[str, Any]] = {}
    reason = _absent_reason(arms, (left, right))
    if kind == "depth":
        # Arm-level means (all non-crash episodes of each arm), with m4 printed between m2 and m6.
        blocks = arm_blocks or {}
        out["arm_means"] = {
            tag: {"arm": name,
                  "goal_pass_mean": (blocks.get(name) or {}).get("goal_pass_mean"),
                  "success_mean": (blocks.get(name) or {}).get("success_mean")}
            for tag, name in (("m2", right), ("m4", spec["m4"]), ("m6", left))
        }
        out["m4_reason"] = _absent_reason(arms, (spec["m4"],))
    if reason is not None:
        out["reason"] = reason
        out.update({m: None for m in METRICS})
        return out, series
    reasons = []
    for metric in METRICS:
        s = paired_series(arms[left]["rows"], arms[right]["rows"], metric)
        series[metric] = s
        if kind in ("hstar", "flag"):
            if kind == "hstar":
                h = hstars.get(left, {})
            else:
                h = {k: r["h_flag"] for k, r in arms[left]["rows"].items()}
            block, why = handoff_metric(s, h, n_boot=n_boot, seed=seed)
            if why:
                reasons.append(f"{metric}: {why}")
        else:
            block = plain_metric(s, n_boot=n_boot, seed=seed, ni=(kind == "ni"))
            if block is None:
                reasons.append(f"{metric}: no pairs (n_dropped {s['n_dropped']})")
        out[metric] = None if block is None else {"left": left, "right": right, **block}
    if kind in ("hstar", "flag"):
        out["h_source"] = ("handoff_control.hstar_flags on the prefix arm's campaign root" if kind == "hstar"
                           else "handoff_occurred of the prefix episode's last report event")
    out["reason"] = "; ".join(reasons) if reasons else None
    return out, series


def did_block(
    did_id: str,
    pair: tuple[str, str],
    blocks: dict[str, dict[str, Any]],
    series: dict[str, dict[str, dict[str, Any]]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    zs_id, q_id = pair
    out: dict[str, Any] = {"zs": zs_id, "qzs": q_id, "kind": "did", "reason": None}
    missing = [c for c in (zs_id, q_id) if not series.get(c)]
    if missing:
        out["reason"] = "; ".join(f"{c}: {blocks[c].get('reason')}" for c in missing)
        out.update({m: None for m in METRICS})
        return out
    reasons = []
    for metric in METRICS:
        block, why = did_metric(series[zs_id][metric], series[q_id][metric], n_boot=n_boot, seed=seed)
        out[metric] = None if block is None else {"left": zs_id, "right": q_id, **block}
        if why:
            reasons.append(f"{metric}: {why}")
    out["reason"] = "; ".join(reasons) if reasons else None
    return out


# ---- report --------------------------------------------------------------------------------------
def git_sha() -> Optional[str]:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                             timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    return res.stdout.strip() or None


def load_arms(root: Path, configs_dir: Path,
              seeds: Iterable[int] = DEV_SEEDS) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    refuse_path(root)
    configured = configured_arms(configs_dir)
    arms = {arm: load_arm(root, arm, cid, seeds) for arm, cid in configured.items()}
    return arms, configured


def contrast_completeness(arm_blocks: dict[str, dict[str, Any]], names: Iterable[str]) -> tuple[bool, Optional[str]]:
    """A contrast is complete iff every arm it reads is complete (the read runs regardless)."""
    why = []
    for name in names:
        b = arm_blocks.get(name) or {}
        if not b.get("complete"):
            why.append(f"{name}: {b.get('complete_reason') or b.get('reason') or 'not complete'}")
    return (not why), ("INCOMPLETE -- " + "; ".join(why) if why else None)


def build_report(root: Path = RESULTS, configs_dir: Path = CONFIGS_DIR, *, n_boot: int = N_BOOT,
                 seed: int = SEED, seeds: Iterable[int] = DEV_SEEDS) -> dict[str, Any]:
    seeds = tuple(sorted({int(s) for s in seeds}))
    arms, configured = load_arms(root, configs_dir, seeds)
    hstars = {arm: hstar_for(data, seeds) for arm, data in arms.items() if arm.startswith("prefix_")}
    arm_blocks = {arm: arm_block(data, hstars.get(arm), seeds) for arm, data in arms.items()}
    for arm in EXPECTED_ARMS:
        if arm not in arm_blocks:
            reason = f"no configs/bfcl_{arm}.yaml"
            arm_blocks[arm] = {"campaign_id": campaign_of(arm), "present": False, "reason": reason,
                               "n_expected": n_expected_for(seeds), **{k: None for k in ARM_KEYS},
                               "complete": False, "complete_reason": reason}
    contrasts: dict[str, Any] = {}
    series: dict[str, dict[str, dict[str, Any]]] = {}
    for cid, spec in CONTRASTS.items():
        contrasts[cid], series[cid] = contrast_block(cid, spec, arms, hstars, n_boot=n_boot, seed=seed,
                                                     arm_blocks=arm_blocks)
        ok, why = contrast_completeness(arm_blocks, (spec["left"], spec["right"]))
        contrasts[cid].update({"complete": ok, "complete_reason": why})
    for did_id, pair in DID.items():
        contrasts[did_id] = did_block(did_id, pair, contrasts, series, n_boot=n_boot, seed=seed)
        names = [a for c in pair for a in (CONTRASTS[c]["left"], CONTRASTS[c]["right"])]
        ok, why = contrast_completeness(arm_blocks, dict.fromkeys(names))
        contrasts[did_id].update({"complete": ok, "complete_reason": why})
    found = sorted(d["campaign_id"] for d in arms.values() if Path(d["dir"]).is_dir())
    absent = sorted(d["campaign_id"] for d in arms.values() if not Path(d["dir"]).is_dir())
    incomplete = sorted(a for a, b in arm_blocks.items() if not b.get("complete"))
    return {
        "meta": {
            "generated_by": "scripts/analysis/bfcl_dev_report.py",
            "prereg": "docs/prereg_bfcl_dev_20260924.md §6 (exploratory; no decision rule)",
            "split": "dev",
            "results_root": str(root),
            "configs_dir": str(configs_dir),
            "arms_configured": sorted(configured),
            "arms_expected_not_configured": sorted(set(EXPECTED_ARMS) - set(configured)),
            "arms_configured_not_expected": sorted(set(configured) - set(EXPECTED_ARMS)),
            "campaigns_found": found,
            "campaigns_absent": absent,
            "campaigns_empty": sorted(d["campaign_id"] for d in arms.values()
                                      if Path(d["dir"]).is_dir() and not d["present"]),
            "seeds": list(seeds),
            "n_dev_entries": N_DEV_ENTRIES,
            "n_expected_per_arm": n_expected_for(seeds),
            "all_arms_complete": not incomplete,
            "arms_incomplete": incomplete,
            "n_boot": n_boot,
            "seed": seed,
            "cluster_unit": "entry",
            "ci": "95% percentile entry-cluster bootstrap; every interval is EXPLORATORY",
            "ni_margin_pp": round(NI_MARGIN * 100, 2),
            "git_sha": git_sha(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "definitions": DEFINITIONS,
        },
        "arms": arm_blocks,
        "contrasts": contrasts,
    }


def _f(x: Any, width: int, digits: int = 3) -> str:
    if x is None:
        return "-".rjust(width)
    if isinstance(x, float):
        return f"{x:.{digits}f}".rjust(width)
    return str(x).rjust(width)


def summary_lines(report: dict[str, Any]) -> list[str]:
    meta = report["meta"]
    lines = [f"BFCL dev read (EXPLORATORY; entry-cluster bootstrap n_boot={meta['n_boot']} seed={meta['seed']})",
             f"campaigns found {len(meta['campaigns_found'])}, absent {len(meta['campaigns_absent'])}; seeds "
             f"{meta['seeds']}, n_expected {meta['n_expected_per_arm']} per arm; all arms complete: "
             f"{meta['all_arms_complete']}", "",
             f"{'arm':<24}{'n':>5}{'crash':>6}{'gp':>8}{'succ':>8}{'limit':>7}{'live':>7}{'attr':>7}"]
    absent = []
    for arm, b in report["arms"].items():
        if not b.get("present"):
            absent.append(arm)
            continue
        tag = "" if b.get("complete") else f"  INCOMPLETE ({b.get('complete_reason')})"
        lines.append(f"{arm:<24}{_f(b['n'], 5)}{_f(b['n_crash'], 6)}{_f(b['goal_pass_mean'], 8)}"
                     f"{_f(b['success_mean'], 8)}{_f(b['limit_rate'], 7, 2)}{_f(b['calls_live_mean'], 7, 2)}"
                     f"{_f(b['calls_attributed_mean'], 7, 2)}{tag}")
    lines.append(f"absent arms, INCOMPLETE ({len(absent)}): {', '.join(absent) if absent else 'none'}")
    lines += ["", f"{'contrast':<20}{'metric':<10}{'diff_pp':>8}  {'ci95_entry (exploratory)':<22}{'pairs':>6}"
              f"{'clus':>5}{'drop':>5}{'p2':>8}"]
    for cid, c in report["contrasts"].items():
        inc = "" if c.get("complete") else "  INCOMPLETE"
        for metric in METRICS:
            b = c.get(metric)
            if b is None:
                lines.append(f"{cid:<20}{metric:<10}{'null':>8}  INCOMPLETE  {(c.get('reason') or '')[:60]}")
                continue
            ci = b.get("ci95_entry") or [None, None]
            ci_s = f"[{_f(ci[0], 0, 2).strip()}, {_f(ci[1], 0, 2).strip()}]"
            n_pairs = b.get("n_pairs", b.get("n_pairs_zs"))
            extra = f"  NI>{b['margin_pp']}: {b['lower_above_margin']}" if "margin_pp" in b else ""
            lines.append(f"{cid:<20}{metric:<10}{_f(b['diff_pp'], 8, 2)}  {ci_s:<22}{_f(n_pairs, 6)}"
                         f"{_f(b.get('n_clusters'), 5)}{_f(b.get('n_dropped'), 5)}{_f(b.get('p_two_sided'), 8, 4)}"
                         f"{extra}{inc}")
    return lines


def parse_seeds(text: str) -> tuple[int, ...]:
    seeds = tuple(sorted({int(s) for s in text.split(",") if s.strip()}))
    if not seeds:
        raise argparse.ArgumentTypeError("--seeds needs at least one seed")
    return seeds


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=RESULTS)
    ap.add_argument("--configs", type=Path, default=CONFIGS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--n-boot", type=int, default=N_BOOT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--seeds", type=parse_seeds, default=DEV_SEEDS,
                    help="requested dev seeds, comma-separated (default 1,2,3 as dev prereg §4)")
    args = ap.parse_args(argv)
    refuse_path(args.out)
    refuse_path(args.root)
    report = build_report(args.root, args.configs, n_boot=args.n_boot, seed=args.seed, seeds=args.seeds)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("\n".join(summary_lines(report)))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
