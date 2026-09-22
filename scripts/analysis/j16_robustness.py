#!/usr/bin/env python3
"""J16 reviewer robustness analyses F-b .. F-g on the AppWorld dev split.

What this module is for
-----------------------
Six reviewer requests, each answered from episodes already on disk (no model calls):

* F-b  TGC / SGC intervals for the channel contrasts CHAN-C1-02 and CHAN-PRICE-01.
* F-c  Handoff-only depth curves for both receivers, silenced counts per depth, and the
       share of each depth gain earned inside handoff episodes (with intervals).
* F-d  Hinge vs linear fit of goal_pass on depth m, with a null-calibrated bootstrap.
* F-e  One non-inferiority table against BOTH ceilings (cap-25, cap-81) plus the CEIL-01
       limit-exclusion sensitivity and the selection it induces.
* F-f  Intervals on per-episode cost differences; local GPU-seconds derivability.
* F-g  The near-matched advice pair advise_k3 (starved) vs prefix_m6.

Reproduce before extending
--------------------------
Every section first recomputes the existing numbers it builds on and compares them with
the source report at the precision that report stores (arm means at 6 decimals, pp
contrasts and intervals at 2). A section whose reproduction fails is STOPPED and reported
as a discrepancy; it is not extended. Reproductions use the bootstrap seed the source
report was produced with (hj1_gate.SEED = 20260915); every NEW interval uses 20260924.

Conventions (restated so the JSON is self-contained)
----------------------------------------------------
* Episode key (task_id, seed); dev split 57 tasks / 19 scenarios, seeds 1-2 (the pooled
  cap-81 family adds seed 3).
* goal_pass_rate primary, tgc secondary. Population "all": error_type == "crash" scores 0
  and ONLY crash does; "limit" is scored on its merits and never dropped.
* A pair is formed only where both rows are j10-clean (the j8_frontier population, see
  ``j10_clean``); on every arm used here that drops nothing, and the drop is counted.
* Paired cluster percentile bootstrap, B = 10,000, scenario-clustered primary, task
  alongside. Percentile indices int(0.025 B) / int(0.975 B), as in hj1_gate.
* Non-inferiority margin 7.00 pp: arm - reference, holds iff round(lower, 2) >= -7.00
  (the j8_frontier rule).

Interface:
  python scripts/analysis/j16_robustness.py [--out-json PATH] [--out-md PATH]
      [--n-boot 10000] [--sections fb,fc,fd,fe,ff,fg]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import random
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.setup.hj1_gate import scenario_of  # noqa: E402

Key = tuple  # (task_id, seed)

RESULTS_DIR = Path("/scratch/n12194778/sidekick/results")
REPORTS_DIR = REPO / "campaign" / "results"
DEFAULT_OUT_JSON = REPORTS_DIR / "j16_robustness_20260923.report.json"
DEFAULT_OUT_MD = REPORTS_DIR / "j16_robustness_20260923.md"
N_BOOT = 10_000
SEED = 20260924
LEGACY_SEED = 20260915
NI_MARGIN_PP = 7.0
CRASH = "crash"
LIMIT = "limit"
# j10_report.SCORED_FAILURE_TYPES (scripts/analysis/j10_report.py:69), copied rather than
# imported so this module does not execute j10_report at import time.
SCORED_FAILURE_TYPES = frozenset({"limit", "timeout", "crash", "parse_error", "api_error"})
HELD_OUT_MARKERS = ("test_normal", "test_challenge")
BASE_SEEDS = frozenset({1, 2})
POOLED_SEEDS = frozenset({1, 2, 3})
HJ1B = RESULTS_DIR / "hj1b_planner_20260915"
PRICES = REPO / "configs" / "cost" / "prices_2026-09.yaml"
TAU_REGISTERED = (4, 6, 7, 8, 9)
TAU_EXPANDED = (2, 4, 6, 7, 8, 9, 10)
# Commit that introduced correct_context_lines; before it loop.py hard-coded
# `transcript[-8:]` on the advise path (git show 722e887 -- src/sidekick/systems/loop.py).
CONTEXT_COMMIT = "722e887"
CONTEXT_COMMIT_TIME = "2026-09-21T05:39:03+00:00"  # 2026-09-21 15:39:03 +1000


def _arm_dirs() -> dict[str, list[Path]]:
    r = RESULTS_DIR
    d: dict[str, list[Path]] = {
        "ceiling_cap25": [r / "hj1b_planner_20260915" / "planner_alone"],
        "ceiling_cap81": [r / "hj13_planner_alone_cap81_20260923" / "planner_alone"],
        "plan_only": [r / "hj8_sft_plan_bplus_20260921iaware" / "sft_plan"],
        "executor_alone": [r / "hj8_executor_alone_bplus_20260919" / "executor_alone"],
        "advise_k10_starved": [r / "hj8_fixed_k_10_20260921iaware" / "fixed_k"],
        "advise_k3_starved": [r / "hj8_fixed_k_3_20260921iaware" / "fixed_k"],
        "advise_oracle_esc_starved": [
            r / "hj8_oracle_escalation_20260921iaware" / "oracle_escalation"
        ],
        "advise_k10_fullctx": [r / "hj12_advise_fixed_k_10_fullctx_20260923" / "fixed_k"],
        "advise_k1_fullctx": [r / "hj13_advise_fixed_k_1_fullctx_20260923" / "fixed_k"],
        "takeover_k10": [r / "hj12_takeover_fixed_k_10_20260923" / "fixed_k"],
        "t_m6_rep": [r / "hj12_prefix_m6_20260923rep" / "prefix_handoff"],
        "t_m9_rep": [r / "hj12_prefix_m9_20260923rep" / "prefix_handoff"],
    }
    for m in (2, 4, 6, 7, 8, 9, 10, 11):
        d[f"t_m{m}"] = [r / f"hj12_prefix_m{m}_20260923" / "prefix_handoff"]
        d[f"t_pre_m{m}"] = [r / f"hj12_prefix_m{m}_20260922" / "prefix_handoff"]
    for m in (6, 9, 11):
        d[f"zs_m{m}"] = [r / f"hj13_prefix_zs_m{m}_20260923" / "prefix_handoff"]
        c81t = r / f"hj17_prefix_c81_bplus_m{m}_20260923" / "prefix_handoff"
        c81z = r / f"hj17_prefix_c81_zs_m{m}_20260923" / "prefix_handoff"
        d[f"c81_t_m{m}"] = [c81t]
        d[f"c81_zs_m{m}"] = [c81z]
        d[f"c81p_t_m{m}"] = [c81t, r / f"hj18_prefix_c81s3_bplus_m{m}_20260924" / "prefix_handoff"]
        d[f"c81p_zs_m{m}"] = [c81z, r / f"hj18_prefix_c81s3_zs_m{m}_20260924" / "prefix_handoff"]
    return d


ARM_DIRS = _arm_dirs()


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


def refuse_heldout(path: Path | str) -> None:
    text = str(path)
    for marker in HELD_OUT_MARKERS:
        if marker in text:
            raise RuntimeError(f"refusing held-out split path {path}")


def _read_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def events_last_attempt(path: Path) -> list[dict[str, Any]]:
    """Events after the last run_start (the attempt that produced result.json)."""
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    last = 0
    for i, ev in enumerate(events):
        if ev.get("event_type") == "run_start":
            last = i
    return events[last:]


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def episode_facts(
    result: dict[str, Any],
    events: list[dict[str, Any]],
    manifest: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Handoff flags (last `report` event, as j13_mechanism), executor usage, wall clock."""
    report: Optional[dict[str, Any]] = None
    for ev in events:
        if ev.get("event_type") == "report" and isinstance(ev.get("payload"), dict):
            report = ev["payload"]
    handoff = None
    eff_m = None
    n_src = None
    if report is not None:
        if report.get("handoff_occurred") is not None:
            handoff = bool(report["handoff_occurred"])
        if report.get("effective_m") is not None:
            eff_m = int(report["effective_m"])
        if report.get("n_source_actions") is not None:
            n_src = int(report["n_source_actions"])
    n_usage = 0
    lat_sum = 0.0
    gpu_sum = 0.0
    lat_pos = 0
    gpu_pos = 0
    lat_present = 0
    for ev in events:
        usage = ev.get("usage")
        if ev.get("actor") != "executor" or not isinstance(usage, dict):
            continue
        n_usage += 1
        lat = _num(usage.get("latency_s"))
        gpu = _num(usage.get("gpu_seconds"))
        if lat is not None:
            lat_present += 1
            lat_sum += lat
            lat_pos += int(lat > 0)
        if gpu is not None:
            gpu_sum += gpu
            gpu_pos += int(gpu > 0)
    run_end = None
    for ev in events:
        if ev.get("event_type") == "run_end":
            run_end = _parse_ts(ev.get("ts"))
    created = _parse_ts(manifest.get("created_at")) if isinstance(manifest, dict) else None
    wall = None
    if run_end is not None and created is not None:
        wall = (run_end - created).total_seconds()
    totals = result.get("totals") if isinstance(result.get("totals"), dict) else {}
    per_actor = totals.get("per_actor") if isinstance(totals.get("per_actor"), dict) else {}
    ex = per_actor.get("executor") if isinstance(per_actor.get("executor"), dict) else {}
    return {
        "has_report": report is not None,
        "handoff_occurred": handoff,
        "effective_m": eff_m,
        "n_source_actions": n_src,
        "executor_n_calls": int(ex.get("n_calls") or 0),
        "executor_tokens_total": _num(totals.get("executor_tokens_total")),
        "executor_gpu_seconds": _num(ex.get("gpu_seconds")),
        "gpu_seconds_total": _num(totals.get("gpu_seconds_total")),
        "executor_usage_records": n_usage,
        "executor_latency_present": lat_present,
        "executor_latency_s_sum": lat_sum,
        "executor_latency_positive": lat_pos,
        "executor_gpu_seconds_sum": gpu_sum,
        "executor_gpu_positive": gpu_pos,
        "wall_clock_s": wall,
        "created_at": manifest.get("created_at") if isinstance(manifest, dict) else None,
    }


def load_campaign_dir(
    root: Path, allowed_seeds: Iterable[int]
) -> tuple[dict[Key, dict[str, Any]], dict[str, int]]:
    """Every result.json under root (layout <system>/<seed>/<task>/), with episode facts."""
    refuse_heldout(root)
    if not root.is_dir():
        raise FileNotFoundError(f"campaign directory does not exist: {root}")
    allowed = set(int(s) for s in allowed_seeds)
    rows: dict[Key, dict[str, Any]] = {}
    diag: Counter[str] = Counter()
    for path in sorted(root.rglob("result.json")):
        refuse_heldout(path)
        result = _read_json_file(path)
        if not isinstance(result, dict):
            diag["empty_or_unreadable"] += 1
            continue
        if result.get("task_id") is None or result.get("seed") is None:
            diag["missing_key"] += 1
            continue
        key = (str(result["task_id"]), int(result["seed"]))
        if key[1] not in allowed:
            diag["seed_filtered"] += 1
            continue
        if key in rows:
            raise ValueError(f"duplicate episode {key} under {root}")
        ep_dir = path.parent
        manifest = _read_json_file(ep_dir / "manifest.json")
        events = events_last_attempt(ep_dir / "events.jsonl")
        row = dict(result)
        row["_facts"] = episode_facts(result, events, manifest if isinstance(manifest, dict) else None)
        rows[key] = row
    diag["loaded"] = len(rows)
    return rows, dict(diag)


class ArmStore:
    """Lazy, cached arm loader. Pooled arms refuse colliding episode keys."""

    def __init__(self, dirs: Optional[dict[str, list[Path]]] = None) -> None:
        self.dirs = dict(ARM_DIRS if dirs is None else dirs)
        self._cache: dict[str, dict[Key, dict[str, Any]]] = {}
        self.diagnostics: dict[str, Any] = {}

    def seeds_for(self, label: str) -> frozenset[int]:
        return POOLED_SEEDS if len(self.dirs[label]) > 1 else BASE_SEEDS

    def __call__(self, label: str) -> dict[Key, dict[str, Any]]:
        if label not in self._cache:
            if label not in self.dirs:
                raise KeyError(f"unknown arm {label!r}")
            merged: dict[Key, dict[str, Any]] = {}
            diags = []
            for root in self.dirs[label]:
                rows, diag = load_campaign_dir(root, self.seeds_for(label))
                clash = set(merged) & set(rows)
                if clash:
                    raise ValueError(f"pooled arm {label}: {len(clash)} colliding keys")
                merged.update(rows)
                diags.append({"root": str(root), **diag})
            self._cache[label] = merged
            self.diagnostics[label] = diags
        return self._cache[label]

    def loaded_labels(self) -> list[str]:
        return sorted(self._cache)


# --------------------------------------------------------------------------------------
# Scoring conventions
# --------------------------------------------------------------------------------------


def is_crash(row: dict[str, Any]) -> bool:
    return row.get("error_type") == CRASH


def quality(row: dict[str, Any], field: str) -> Optional[float]:
    """Population 'all': crash scores 0 (only crash). A scored failure with no recorded
    tgc scores 0 (j10_report.score_tgc). Otherwise the recorded value; missing is None."""
    if is_crash(row):
        return 0.0
    value = row.get(field)
    if value is None:
        if field == "tgc" and row.get("error_type") in SCORED_FAILURE_TYPES:
            return 0.0
        return None
    return float(value)


def j10_clean(row: dict[str, Any]) -> bool:
    """Would j10_report.inventory_arm keep this row in `cleaned` (the j8 population)?

    Dropped: a scored failure whose recorded tgc is non-zero (the two TGC writings
    disagree), a non-failure with no recorded tgc, and a row with no n_planner_calls.
    """
    err = row.get("error_type")
    rec = row.get("tgc")
    if err in SCORED_FAILURE_TYPES:
        if rec is not None and float(rec) != 0.0:
            return False
    elif rec is None:
        return False
    if row.get("n_planner_calls") is None:
        return False
    return True


def episode_success(row: dict[str, Any]) -> bool:
    return bool(row.get("success")) and not is_crash(row)


def handoff_flag(row: dict[str, Any]) -> Optional[bool]:
    return row.get("_facts", {}).get("handoff_occurred")


def executor_calls(row: dict[str, Any]) -> int:
    return int(row.get("_facts", {}).get("executor_n_calls") or 0)


def arm_mean(rows: dict[Key, dict[str, Any]], field: str) -> Optional[float]:
    vals = [quality(r, field) for r in rows.values()]
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else None


def arm_summary(rows: dict[Key, dict[str, Any]]) -> dict[str, Any]:
    return {
        "n": len(rows),
        "seeds": sorted({k[1] for k in rows}),
        "n_tasks": len({k[0] for k in rows}),
        "goal_pass_all": arm_mean(rows, "goal_pass_rate"),
        "tgc_all": arm_mean(rows, "tgc"),
        "n_crash": sum(1 for r in rows.values() if is_crash(r)),
        "n_limit": sum(1 for r in rows.values() if r.get("error_type") == LIMIT),
        "n_not_j10_clean": sum(1 for r in rows.values() if not j10_clean(r)),
        "error_types": dict(sorted(Counter(str(r.get("error_type") or "none") for r in rows.values()).items())),
    }


# --------------------------------------------------------------------------------------
# Cluster bootstrap
# --------------------------------------------------------------------------------------


def _cluster_fn(unit: str) -> Callable[[Any], Any]:
    if unit == "scenario":
        return lambda k: scenario_of(str(k[0]))
    if unit == "task":
        return lambda k: str(k[0])
    if unit == "first":  # keys whose first element already is the cluster id (SGC units)
        return lambda k: k[0]
    raise ValueError(f"unknown resample unit {unit!r}")


def ratio(i: int, j: int, *, positive_denominator: bool = False) -> Callable[[list[float]], Optional[float]]:
    def fn(t: list[float]) -> Optional[float]:
        den = t[j]
        if den == 0 or (positive_denominator and den <= 0):
            return None
        return t[i] / den

    return fn


def bootstrap_multi(
    comps: dict[Any, Sequence[float]],
    stats: dict[str, Callable[[list[float]], Optional[float]]],
    unit: str,
    seed: int = SEED,
    n_boot: int = N_BOOT,
    keep_samples: bool = False,
) -> dict[str, Any]:
    """Cluster percentile bootstrap of statistics of summed per-key component vectors.

    Clusters are sorted and drawn with rng.randrange(n_clusters) n_clusters times per
    resample -- the same draw sequence as hj1_gate.paired_diff / j8_frontier
    .paired_diff_scenario / j14_did._cluster_bootstrap, so a mean statistic reproduces
    their intervals exactly at the same seed. A statistic returning None on a resample
    (undefined, e.g. a ratio with a zero denominator) is counted and left out.
    """
    base = {"unit": unit, "seed": seed, "n_boot": n_boot, "n_units": len(comps)}
    if not comps:
        base["n_clusters"] = 0
        base["stats"] = {n: {"point": None, "ci95": None, "n_undefined": None} for n in stats}
        return base
    cof = _cluster_fn(unit)
    dim = len(next(iter(comps.values())))
    grouped: dict[Any, list[float]] = {}
    for k in sorted(comps):
        vec = grouped.setdefault(cof(k), [0.0] * dim)
        for j, v in enumerate(comps[k]):
            vec[j] += float(v)
    clusters = sorted(grouped)
    vecs = [grouped[c] for c in clusters]
    nc = len(vecs)
    total = [sum(v[j] for v in vecs) for j in range(dim)]
    samples: dict[str, list[float]] = {n: [] for n in stats}
    undefined: Counter[str] = Counter()
    rng = random.Random(seed)
    draw = rng.randrange
    rng_dim = range(dim)
    for _ in range(n_boot):
        tot = [0.0] * dim
        for _ in range(nc):
            v = vecs[draw(nc)]
            for j in rng_dim:
                tot[j] += v[j]
        for name, fn in stats.items():
            s = fn(tot)
            if s is None:
                undefined[name] += 1
            else:
                samples[name].append(s)
    out: dict[str, Any] = {}
    for name, fn in stats.items():
        xs = sorted(samples[name])
        ci = [xs[int(0.025 * len(xs))], xs[int(0.975 * len(xs))]] if xs else None
        out[name] = {"point": fn(total), "ci95": ci, "n_undefined": int(undefined[name])}
        if keep_samples:
            out[name]["_samples"] = xs
    base["n_clusters"] = nc
    base["stats"] = out
    return base


def mean_comps(values: dict[Any, float]) -> dict[Any, tuple[float, float]]:
    return {k: (float(v), 1.0) for k, v in values.items()}


def boot_mean(values: dict[Any, float], unit: str, seed: int = SEED, n_boot: int = N_BOOT) -> dict[str, Any]:
    b = bootstrap_multi(mean_comps(values), {"mean": ratio(0, 1)}, unit, seed, n_boot)
    st = b["stats"]["mean"]
    return {"point": st["point"], "ci95": st["ci95"], "n_clusters": b["n_clusters"], "unit": unit, "seed": seed}


def _boot_name(unit: str, seed: int) -> str:
    return unit if seed == SEED else f"{unit}_seed{seed}"


def excludes_zero(ci: Optional[Sequence[float]]) -> Optional[bool]:
    if not ci:
        return None
    return bool(ci[0] > 0 or ci[1] < 0)


# --------------------------------------------------------------------------------------
# Paired contrasts
# --------------------------------------------------------------------------------------


def paired_diffs(
    a_rows: dict[Key, dict[str, Any]],
    b_rows: dict[Key, dict[str, Any]],
    field: str,
    keys: Optional[Iterable[Key]] = None,
) -> tuple[dict[Key, float], dict[str, Any]]:
    shared = set(a_rows) & set(b_rows)
    if keys is not None:
        shared &= set(keys)
    diffs: dict[Key, float] = {}
    la: list[float] = []
    lb: list[float] = []
    unclean = 0
    missing = 0
    for k in sorted(shared):
        ra, rb = a_rows[k], b_rows[k]
        if not (j10_clean(ra) and j10_clean(rb)):
            unclean += 1
            continue
        va, vb = quality(ra, field), quality(rb, field)
        if va is None or vb is None:
            missing += 1
            continue
        diffs[k] = va - vb
        la.append(va)
        lb.append(vb)
    meta = {
        "n_shared": len(shared),
        "n_pairs": len(diffs),
        "n_dropped_not_j10_clean": unclean,
        "n_dropped_missing_field": missing,
        "mean_left": statistics.fmean(la) if la else None,
        "mean_right": statistics.fmean(lb) if lb else None,
    }
    return diffs, meta


DEFAULT_BOOTS: tuple[tuple[str, int], ...] = (("scenario", SEED), ("task", SEED))


def contrast_from_diffs(
    diffs: dict[Key, float],
    meta: dict[str, Any],
    boots: Sequence[tuple[str, int]],
    n_boot: int,
    scale: float = 100.0,
) -> dict[str, Any]:
    out = dict(meta)
    out["diff"] = statistics.fmean(diffs.values()) if diffs else None
    out["diff_pp" if scale == 100.0 else "diff_scaled"] = (
        None if out["diff"] is None else scale * out["diff"]
    )
    for unit, seed in boots:
        b = boot_mean(diffs, unit, seed, n_boot)
        ci = b["ci95"]
        out[_boot_name(unit, seed)] = {
            "ci95" if scale != 100.0 else "ci95_pp": None if ci is None else [scale * ci[0], scale * ci[1]],
            "n_clusters": b["n_clusters"],
            "seed": seed,
        }
    return out


def contrast(
    store: ArmStore,
    left: str,
    right: str,
    field: str,
    keys: Optional[Iterable[Key]] = None,
    boots: Sequence[tuple[str, int]] = DEFAULT_BOOTS,
    n_boot: int = N_BOOT,
) -> dict[str, Any]:
    diffs, meta = paired_diffs(store(left), store(right), field, keys)
    out = contrast_from_diffs(diffs, meta, boots, n_boot)
    out.update({"left": left, "right": right, "field": field})
    return out


def ni_holds(ci_pp: Optional[Sequence[float]], margin: float = NI_MARGIN_PP) -> Optional[bool]:
    """j8_frontier rule: arm - reference, non-inferior iff round(lower, 2) >= -margin."""
    if not ci_pp:
        return None
    return bool(round(float(ci_pp[0]), 2) >= -margin)


# --------------------------------------------------------------------------------------
# Reproduction bookkeeping
# --------------------------------------------------------------------------------------


class Repro:
    """Compare recomputed numbers with a stored report at the stored precision."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def check(
        self,
        item: str,
        source: str,
        key: str,
        expected: Any,
        computed: Any,
        decimals: int,
    ) -> bool:
        tol = 0.5 * 10 ** (-decimals) + 1e-9
        exp_list = expected if isinstance(expected, list) else [expected]
        comp_list = computed if isinstance(computed, list) else [computed]
        ok = (
            len(exp_list) == len(comp_list)
            and all(e is not None and c is not None for e, c in zip(exp_list, comp_list))
            and all(abs(float(c) - float(e)) <= tol for e, c in zip(exp_list, comp_list))
        )

        def rnd(x: Any) -> Any:
            return None if x is None else round(float(x), decimals + 2)

        self.rows.append(
            {
                "item": item,
                "source": source,
                "key": key,
                "expected": expected,
                "computed": [rnd(c) for c in comp_list] if isinstance(computed, list) else rnd(computed),
                "compared_at_decimals": decimals,
                "match": bool(ok),
            }
        )
        return ok

    def check_exact(self, item: str, source: str, key: str, expected: Any, computed: Any) -> bool:
        ok = expected == computed
        self.rows.append(
            {"item": item, "source": source, "key": key, "expected": expected,
             "computed": computed, "compared_at_decimals": "exact", "match": bool(ok)}
        )
        return ok

    @property
    def all_ok(self) -> bool:
        return all(r["match"] for r in self.rows)

    def failures(self) -> list[dict[str, Any]]:
        return [r for r in self.rows if not r["match"]]

    def block(self) -> dict[str, Any]:
        return {"n_checked": len(self.rows), "n_matched": sum(r["match"] for r in self.rows),
                "all_match": self.all_ok, "checks": self.rows}


def load_report(name: str) -> dict[str, Any]:
    return json.loads((REPORTS_DIR / name).read_text(encoding="utf-8"))


def rel(name: str) -> str:
    return f"campaign/results/{name}"


def stopped(section: str, repro: Repro) -> dict[str, Any]:
    return {
        "status": "stopped_reproduction_discrepancy",
        "note": (
            f"{section}: at least one existing number could not be reproduced at its stored "
            "precision, so this item was not extended. See reproduction.failures."
        ),
        "reproduction": repro.block(),
        "failures": repro.failures(),
    }


# --------------------------------------------------------------------------------------
# F-b  TGC / SGC for the channel contrasts
# --------------------------------------------------------------------------------------


def sgc_units(rows: dict[Key, dict[str, Any]]) -> dict[tuple[str, int], float]:
    """(scenario, seed) -> 1.0 if every task of that scenario succeeded (crash = failure).

    Mirrors hj1_gate.scenario_goal_completion: only scenarios whose tasks are all present
    are scored; the expected size is the largest task count seen for that scenario.
    """
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for (task_id, seed), row in rows.items():
        groups.setdefault((scenario_of(task_id), seed), []).append(row)
    expected: dict[str, int] = {}
    for (scen, _seed), g in groups.items():
        expected[scen] = max(expected.get(scen, 0), len(g))
    out: dict[tuple[str, int], float] = {}
    for (scen, seed), g in groups.items():
        if len(g) < expected[scen]:
            continue
        out[(scen, seed)] = 1.0 if all(episode_success(r) for r in g) else 0.0
    return out


def sgc_contrast(
    a_rows: dict[Key, dict[str, Any]],
    b_rows: dict[Key, dict[str, Any]],
    seed: int = SEED,
    n_boot: int = N_BOOT,
) -> dict[str, Any]:
    ua, ub = sgc_units(a_rows), sgc_units(b_rows)
    shared = sorted(set(ua) & set(ub))
    diffs = {u: ua[u] - ub[u] for u in shared}
    b = boot_mean(diffs, "first", seed, n_boot)
    return {
        "n_units_scenario_seed": len(shared),
        "sgc_left": statistics.fmean(ua[u] for u in shared) if shared else None,
        "sgc_right": statistics.fmean(ub[u] for u in shared) if shared else None,
        "n_complete_left": int(sum(ua[u] for u in shared)),
        "n_complete_right": int(sum(ub[u] for u in shared)),
        "n_discordant_units": sum(1 for u in shared if ua[u] != ub[u]),
        "diff_pp": None if b["point"] is None else 100 * b["point"],
        "scenario": {"ci95_pp": None if b["ci95"] is None else [100 * x for x in b["ci95"]],
                     "n_clusters": b["n_clusters"], "seed": seed},
        "resample_unit": "scenario (a (scenario, seed) unit belongs to its scenario)",
        "task_clustered": "not defined: SGC is a scenario-level quantity",
    }


def scored_failure_success_count(rows: dict[Key, dict[str, Any]]) -> int:
    return sum(
        1 for r in rows.values()
        if r.get("error_type") in SCORED_FAILURE_TYPES and bool(r.get("success"))
    )


def section_fb(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    c1_name = "hj13_c1_matched_trigger_20260923.report.json"
    h2_name = "hj13_advice_at_price_20260923.report.json"
    c1, h2 = load_report(c1_name), load_report(h2_name)
    arm_map = [
        (c1_name, c1, "takeover_k10", "takeover_k10"),
        (c1_name, c1, "advise_fullctx_k10", "advise_k10_fullctx"),
        (c1_name, c1, "plan_only_iaware", "plan_only"),
        (c1_name, c1, "prefix_m11", "t_m11"),
        (h2_name, h2, "advise_k1_fullctx", "advise_k1_fullctx"),
        (h2_name, h2, "plan_floor", "plan_only"),
        (h2_name, h2, "advise_k10_fullctx", "advise_k10_fullctx"),
        (h2_name, h2, "prefix_m9", "t_m9"),
        (h2_name, h2, "prefix_m11", "t_m11"),
    ]
    for name, rep, rkey, label in arm_map:
        for field, jf in (("goal_pass_rate", "goal_pass_all"), ("tgc", "tgc_all")):
            repro.check("arm mean", rel(name), f"arms.{rkey}.{jf}", rep["arms"][rkey][jf],
                        arm_mean(store(label), field), 6)
    specs = [
        ("CHAN-C1-02", c1_name, c1, "advise_fullctx_k10_minus_takeover_k10", "advise_k10_fullctx", "takeover_k10"),
        ("CHAN-C1-02 support", c1_name, c1, "takeover_k10_minus_plan_only_iaware", "takeover_k10", "plan_only"),
        ("CHAN-PRICE-01 P1", h2_name, h2, "advise_k1_fullctx_minus_plan_floor", "advise_k1_fullctx", "plan_only"),
        ("CHAN-PRICE-01 P2", h2_name, h2, "advise_k1_fullctx_minus_prefix_m11", "advise_k1_fullctx", "t_m11"),
        ("CHAN-PRICE-01 P2 (m9)", h2_name, h2, "advise_k1_fullctx_minus_prefix_m9", "advise_k1_fullctx", "t_m9"),
        ("CHAN-PRICE-01 P3", h2_name, h2, "advise_k1_fullctx_minus_advise_k10_fullctx", "advise_k1_fullctx", "advise_k10_fullctx"),
    ]
    existing: list[dict[str, Any]] = []
    legacy_boots = (("scenario", LEGACY_SEED), ("task", LEGACY_SEED))
    for claim, name, rep, suffix, left, right in specs:
        for field, pre in (("goal_pass_rate", "goal_pass_all"), ("tgc", "tgc_all")):
            key = f"{pre}_{suffix}"
            e = rep["contrasts"][key]
            c = contrast(store, left, right, field, boots=legacy_boots, n_boot=n_boot)
            src = rel(name)
            repro.check(claim, src, f"contrasts.{key}.diff_pp", e["diff_pp"], c["diff_pp"], 2)
            repro.check(claim, src, f"contrasts.{key}.ci95_pp", e["ci95_pp"],
                        c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"], 2)
            repro.check(claim, src, f"contrasts.{key}.ci95_pp_task", e["ci95_pp_task"],
                        c[_boot_name("task", LEGACY_SEED)]["ci95_pp"], 2)
            existing.append({
                "claim": claim, "field": field, "report": src, "key": f"contrasts.{key}",
                "definition": f"{left} - {right}", "diff_pp": e["diff_pp"],
                "ci95_pp_scenario": e["ci95_pp"], "ci95_pp_task": e["ci95_pp_task"],
                "n_pairs": e.get("n_pairs"), "bootstrap_seed": LEGACY_SEED,
            })
    if not repro.all_ok:
        return stopped("F-b", repro)

    # New: the same TGC contrasts at the registered seed, and SGC (not in any report).
    new_tgc: dict[str, Any] = {}
    sgc: dict[str, Any] = {}
    for claim, _name, _rep, suffix, left, right in specs:
        new_tgc[suffix] = contrast(store, left, right, "tgc", n_boot=n_boot)
        sgc[suffix] = sgc_contrast(store(left), store(right), SEED, n_boot)
        sgc[suffix].update({"claim": claim, "left": left, "right": right})
    # Present the C1 contrast in the paper's sign (takeover - advise) as well.
    c1_flip = {}
    for pre in ("goal_pass_all", "tgc_all"):
        e = c1["contrasts"][f"{pre}_advise_fullctx_k10_minus_takeover_k10"]
        c1_flip[pre] = {
            "definition": "takeover_k10 - advise_k10_fullctx (negation of the stored contrast)",
            "diff_pp": -e["diff_pp"],
            "ci95_pp_scenario": [-e["ci95_pp"][1], -e["ci95_pp"][0]],
            "ci95_pp_task": [-e["ci95_pp_task"][1], -e["ci95_pp_task"][0]],
        }
    diag = {label: scored_failure_success_count(store(label)) for label in
            ("takeover_k10", "advise_k10_fullctx", "advise_k1_fullctx", "plan_only", "t_m9", "t_m11")}
    sgc_levels = {}
    for label in ("takeover_k10", "advise_k10_fullctx", "advise_k1_fullctx", "plan_only", "t_m9", "t_m11"):
        u = sgc_units(store(label))
        sgc_levels[label] = {"sgc": statistics.fmean(u.values()) if u else None,
                             "n_units": len(u), "n_complete": int(sum(u.values()))}
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "existing_tgc_contrasts": existing,
        "c1_in_paper_sign": c1_flip,
        "tgc_at_registered_seed": new_tgc,
        "sgc_levels": sgc_levels,
        "sgc_contrasts": sgc,
        "sgc_definition": (
            "SGC unit = (scenario, seed); 1 iff all 3 tasks of that scenario have success "
            "true (crash = failure), hj1_gate.scenario_goal_completion. result.json carries "
            "sgc = null on every episode by construction, so SGC is aggregated here."
        ),
        "diagnostic_scored_failure_with_success_true": diag,
    }


# --------------------------------------------------------------------------------------
# F-c  Handoff-only depth curves and decompositions
# --------------------------------------------------------------------------------------

FC_FAMILIES: dict[str, dict[str, Any]] = {
    "cap25_source": {
        "source": "hj1b_planner_20260915 (cap-25 planner sample; the published curve)",
        "tailored": {m: f"t_m{m}" for m in (2, 4, 6, 7, 8, 9, 10, 11)},
        "untailored": {m: f"zs_m{m}" for m in (6, 9, 11)},
        "decompose": {"tailored": [(2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 11), (6, 9), (6, 11), (2, 11)],
                      "untailored": [(6, 9), (9, 11), (6, 11)]},
    },
    "cap81_source_seeds12": {
        "source": "hj13_planner_alone_cap81_20260923 (cap-81 sample, seeds 1-2)",
        "tailored": {m: f"c81_t_m{m}" for m in (6, 9, 11)},
        "untailored": {m: f"c81_zs_m{m}" for m in (6, 9, 11)},
        "decompose": {"tailored": [(6, 9), (9, 11), (6, 11)], "untailored": [(6, 9), (9, 11), (6, 11)]},
    },
    "cap81_source_pooled_seeds123": {
        "source": "cap-81 samples seeds 1-3 (hj17 + hj18 seed 3), 171 episodes",
        "tailored": {m: f"c81p_t_m{m}" for m in (6, 9, 11)},
        "untailored": {m: f"c81p_zs_m{m}" for m in (6, 9, 11)},
        "decompose": {"tailored": [(6, 9), (9, 11), (6, 11)], "untailored": [(6, 9), (9, 11), (6, 11)]},
    },
}


def depth_counts(rows: dict[Key, dict[str, Any]]) -> dict[str, Any]:
    n_true = n_false = n_none = n_exec0 = n_post = n_true_exec0 = 0
    post_keys: list[list[Any]] = []
    for k, row in sorted(rows.items()):
        h = handoff_flag(row)
        calls = executor_calls(row)
        if h is True:
            n_true += 1
            if calls == 0:
                n_true_exec0 += 1
        elif h is False:
            n_false += 1
            if calls > 0:
                n_post += 1
                post_keys.append([k[0], k[1]])
        else:
            n_none += 1
        if calls == 0:
            n_exec0 += 1
    return {
        "n": len(rows),
        "n_handoff_occurred_true": n_true,
        "n_handoff_occurred_false": n_false,
        "n_handoff_flag_missing": n_none,
        "n_executor_never_acted": n_exec0,
        "n_handoff_false_but_executor_acted": n_post,
        "n_handoff_true_but_executor_never_acted": n_true_exec0,
        "handoff_false_but_executor_acted_keys": post_keys,
    }


def _h(row: dict[str, Any]) -> float:
    return 1.0 if handoff_flag(row) is True else 0.0


def handoff_only_block(rows: dict[Key, dict[str, Any]], field: str, n_boot: int) -> dict[str, Any]:
    comps: dict[Key, tuple[float, ...]] = {}
    for k, row in rows.items():
        if not j10_clean(row):
            continue
        y = quality(row, field)
        if y is None:
            continue
        h = _h(row)
        comps[k] = (y * h, h, y * (1 - h), 1 - h, y, 1.0)
    stats = {"handoff_only": ratio(0, 1), "silenced": ratio(2, 3), "all": ratio(4, 5)}
    out: dict[str, Any] = {}
    for unit in ("scenario", "task"):
        b = bootstrap_multi(comps, stats, unit, SEED, n_boot)
        for name, st in b["stats"].items():
            blk = out.setdefault(name, {"point": st["point"]})
            blk[f"ci95_{unit}"] = st["ci95"]
    out["n_handoff"] = int(sum(c[1] for c in comps.values()))
    out["n_silenced"] = int(sum(c[3] for c in comps.values()))
    return out


def decomposition(
    base: dict[Key, dict[str, Any]],
    target: dict[Key, dict[str, Any]],
    field: str,
    n_boot: int,
) -> dict[str, Any]:
    """Split the all-episodes rise base -> target into the part earned on episodes that
    hand off at the TARGET depth and the part on episodes whose prefix exhausted the
    source trajectory (handoff_occurred not true), exactly as j13_mechanism.measure_m3.
    """
    comps: dict[Key, tuple[float, ...]] = {}
    for k in sorted(set(base) & set(target)):
        rb, rt = base[k], target[k]
        if not (j10_clean(rb) and j10_clean(rt)):
            continue
        yb, yt = quality(rb, field), quality(rt, field)
        if yb is None or yt is None:
            continue
        h = _h(rt)
        d = yt - yb
        comps[k] = (d * h, d, 1.0, h, yb * h, yt * h, d * (1 - h), 1 - h)
    stats = {
        "delta_total": ratio(1, 2),
        "contribution_handoff": ratio(0, 2),
        "contribution_silenced": ratio(6, 2),
        "share_of_rise_from_handoff": ratio(0, 1, positive_denominator=True),
        "gain_on_handoff_subset": ratio(0, 3),
        "y_base_handoff_subset": ratio(4, 3),
        "y_target_handoff_subset": ratio(5, 3),
        "gain_on_silenced_subset": ratio(6, 7),
    }
    out: dict[str, Any] = {
        "n": len(comps),
        "handoff_count": int(sum(c[3] for c in comps.values())),
        "silenced_count": int(sum(c[7] for c in comps.values())),
    }
    for unit in ("scenario", "task"):
        b = bootstrap_multi(comps, stats, unit, SEED, n_boot)
        for name, st in b["stats"].items():
            blk = out.setdefault(name, {"point": st["point"]})
            blk[f"ci95_{unit}"] = st["ci95"]
            if name == "share_of_rise_from_handoff":
                blk[f"n_resamples_rise_not_positive_{unit}"] = st["n_undefined"]
    tot = [sum(c[j] for c in comps.values()) for j in range(8)] if comps else [0.0] * 8
    out["share_of_rise_from_handoff"]["point_raw"] = (tot[0] / tot[1]) if tot[1] else None
    out["share_interval_note"] = (
        "Percentile interval over resamples whose total rise is > 0; the count of resamples "
        "with a non-positive rise is reported. If that count exceeds 2.5% of B the total rise "
        "itself is unresolved and the share interval should not be read."
    )
    return out


def pinned_curve(arms: dict[int, dict[Key, dict[str, Any]]], field: str, n_boot: int) -> dict[str, Any]:
    ms = sorted(arms)
    deepest = ms[-1]
    pinned = {k for k, r in arms[deepest].items() if handoff_flag(r) is True}
    violations = {m: sum(1 for k in pinned if k in arms[m] and handoff_flag(arms[m][k]) is not True) for m in ms}
    curve = {}
    for m in ms:
        vals = {k: quality(arms[m][k], field) for k in pinned if k in arms[m] and j10_clean(arms[m][k])}
        vals = {k: v for k, v in vals.items() if v is not None}
        b = boot_mean(vals, "scenario", SEED, n_boot)
        curve[f"m{m}"] = {"n": len(vals), "mean": b["point"], "ci95_scenario": b["ci95"]}
    contrasts = {}
    pairs = [(ms[i], ms[i + 1]) for i in range(len(ms) - 1)] + ([(ms[0], ms[-1])] if len(ms) > 2 else [])
    for a, b_ in pairs:
        diffs, meta = paired_diffs(arms[b_], arms[a], field, pinned)
        contrasts[f"m{b_}_minus_m{a}"] = contrast_from_diffs(diffs, meta, DEFAULT_BOOTS, n_boot)
    return {
        "pinned_to": f"handoff_occurred true at m{deepest}",
        "n_keys": len(pinned),
        "keys_not_handing_off_at_shallower_depth": {f"m{m}": v for m, v in violations.items()},
        "curve": curve,
        "contrasts": contrasts,
    }


def receiver_gap(
    t_base: dict[Key, dict[str, Any]],
    t_target: dict[Key, dict[str, Any]],
    u_base: dict[Key, dict[str, Any]],
    u_target: dict[Key, dict[str, Any]],
    field: str,
    n_boot: int,
) -> dict[str, Any]:
    """Tailored - untailored gap at base and target depth, and its change (DiD), on the
    target depth's handoff episodes and on all episodes; formed per episode then averaged."""
    shared = sorted(set(t_base) & set(t_target) & set(u_base) & set(u_target))
    flag_mismatch = sum(1 for k in shared if handoff_flag(t_target[k]) != handoff_flag(u_target[k]))
    out: dict[str, Any] = {"n_shared": len(shared), "handoff_flag_mismatch_between_receivers": flag_mismatch}
    for pop in ("handoff_at_target", "all"):
        comps: dict[Key, tuple[float, ...]] = {}
        for k in shared:
            if pop == "handoff_at_target" and handoff_flag(t_target[k]) is not True:
                continue
            rows = (t_base[k], t_target[k], u_base[k], u_target[k])
            if not all(j10_clean(r) for r in rows):
                continue
            vals = [quality(r, field) for r in rows]
            if any(v is None for v in vals):
                continue
            tb, tt, ub, ut = vals
            comps[k] = (tb - ub, tt - ut, (tt - ut) - (tb - ub), 1.0, tb, tt, ub, ut)
        stats = {"gap_at_base": ratio(0, 3), "gap_at_target": ratio(1, 3), "did_gap_change": ratio(2, 3),
                 "tailored_base": ratio(4, 3), "tailored_target": ratio(5, 3),
                 "untailored_base": ratio(6, 3), "untailored_target": ratio(7, 3)}
        blk: dict[str, Any] = {"n": len(comps)}
        for unit in ("scenario", "task"):
            b = bootstrap_multi(comps, stats, unit, SEED, n_boot)
            for name, st in b["stats"].items():
                s = blk.setdefault(name, {"point": st["point"]})
                if name in ("gap_at_base", "gap_at_target", "did_gap_change"):
                    s[f"ci95_{unit}"] = st["ci95"]
        out[pop] = blk
    return out


def section_fc(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    mech = {
        "tailored": ("hj13_mechanism_tailored_matched_20260923.report.json", "cap25_source"),
        "untailored": ("hj13_mechanism_zeroshot_matched_20260923.report.json", "cap25_source"),
    }
    fam = FC_FAMILIES["cap25_source"]
    for receiver, (name, _f) in mech.items():
        rep = load_report(name)
        prim = rep["m3_prefix_exhausted"]["primary"]
        for m, label in fam[receiver].items():
            rows = store(label)
            e = prim["all_episodes_curve"][f"m{m}"]
            cnt = depth_counts(rows)
            src = rel(name)
            base = f"m3_prefix_exhausted.primary.all_episodes_curve.m{m}"
            repro.check_exact(f"{receiver} counts", src, f"{base}.silenced_count", e["silenced_count"],
                              cnt["n_handoff_occurred_false"] + cnt["n_handoff_flag_missing"])
            repro.check_exact(f"{receiver} counts", src, f"{base}.handoff_count", e["handoff_count"],
                              cnt["n_handoff_occurred_true"])
            if e.get("post_complete_executor_actions") is not None:
                repro.check_exact(f"{receiver} counts", src, f"{base}.post_complete_executor_actions",
                                  e["post_complete_executor_actions"], cnt["n_handoff_false_but_executor_acted"])
            repro.check(f"{receiver} mean", src, f"{base}.mean_goal_pass_rate", e["mean_goal_pass_rate"],
                        arm_mean(rows, "goal_pass_rate"), 4)
        for dname, d in prim["decompositions"].items():
            b_m, t_m = d["m_base"], d["m_target"]
            dec = decomposition(store(fam[receiver][b_m]), store(fam[receiver][t_m]), "goal_pass_rate", 200)
            src = rel(name)
            base = f"m3_prefix_exhausted.primary.decompositions.{dname}"
            repro.check_exact("MECH-07", src, f"{base}.handoff_count", d["handoff_count"], dec["handoff_count"])
            repro.check_exact("MECH-07", src, f"{base}.silenced_count", d["silenced_count"], dec["silenced_count"])
            repro.check("MECH-07", src, f"{base}.delta_total_pp", d["delta_total_pp"], 100 * dec["delta_total"]["point"], 2)
            repro.check("MECH-07", src, f"{base}.y_base_handoff_subset", d["y_base_handoff_subset"],
                        dec["y_base_handoff_subset"]["point"], 4)
            repro.check("MECH-07", src, f"{base}.y_target_handoff_subset", d["y_target_handoff_subset"],
                        dec["y_target_handoff_subset"]["point"], 4)
            repro.check("MECH-07", src, f"{base}.gain_on_handoff_subset_pp", d["gain_on_handoff_subset_pp"],
                        100 * dec["gain_on_handoff_subset"]["point"], 2)
            repro.check("MECH-07", src, f"{base}.contribution_handoff_subset_pp", d["contribution_handoff_subset_pp"],
                        100 * dec["contribution_handoff"]["point"], 2)
            repro.check("MECH-07", src, f"{base}.share_of_rise_from_handoff_pct", d["share_of_rise_from_handoff_pct"],
                        100 * dec["share_of_rise_from_handoff"]["point_raw"], 1)
        pin = prim["controlled_curves"][f"pinned_m{max(fam[receiver])}"]
        pc = pinned_curve({m: store(l) for m, l in fam[receiver].items()}, "goal_pass_rate", 200)
        for mk, e in pin["curve"].items():
            repro.check("pinned curve", rel(name), f"m3_prefix_exhausted.primary.controlled_curves."
                        f"pinned_m{max(fam[receiver])}.curve.{mk}.mean_goal_pass_rate",
                        e["mean_goal_pass_rate"], pc["curve"][mk]["mean"], 4)
    # GUARD-01 (ledger line 32): executor never acted 0,0,3,8,20,31,41 at m=2..10.
    guard = {2: 0, 4: 0, 6: 3, 7: 8, 8: 20, 9: 31, 10: 41}
    for m, v in guard.items():
        repro.check_exact("GUARD-01", "docs/claims_ledger.md (GUARD-01, line 32)",
                          f"executor never acted at m={m}", v,
                          depth_counts(store(f"t_m{m}"))["n_executor_never_acted"])
    if not repro.all_ok:
        return stopped("F-c", repro)

    families: dict[str, Any] = {}
    for fam_name, spec in FC_FAMILIES.items():
        fam_out: dict[str, Any] = {"source": spec["source"], "receivers": {}}
        for receiver in ("tailored", "untailored"):
            arms = {m: store(label) for m, label in spec[receiver].items()}
            depth_rows = {}
            for m, rows in arms.items():
                row = {"arm": spec[receiver][m], **depth_counts(rows)}
                row["goal_pass"] = handoff_only_block(rows, "goal_pass_rate", n_boot)
                row["tgc"] = handoff_only_block(rows, "tgc", n_boot)
                depth_rows[f"m{m}"] = row
            decs = {}
            for b_m, t_m in spec["decompose"][receiver]:
                decs[f"m{b_m}_to_m{t_m}"] = decomposition(arms[b_m], arms[t_m], "goal_pass_rate", n_boot)
            fam_out["receivers"][receiver] = {
                "depths": depth_rows,
                "pinned_curve_goal_pass": pinned_curve(arms, "goal_pass_rate", n_boot),
                "decompositions_goal_pass": decs,
            }
        gaps = {}
        common = sorted(set(spec["tailored"]) & set(spec["untailored"]))
        for i in range(len(common)):
            for j in range(i + 1, len(common)):
                b_m, t_m = common[i], common[j]
                gaps[f"m{b_m}_to_m{t_m}"] = receiver_gap(
                    store(spec["tailored"][b_m]), store(spec["tailored"][t_m]),
                    store(spec["untailored"][b_m]), store(spec["untailored"][t_m]),
                    "goal_pass_rate", n_boot)
        fam_out["receiver_gap_goal_pass"] = gaps
        families[fam_name] = fam_out

    # The 31/32/56/60 question, from the data.
    src_rows = store("ceiling_cap25")
    resolution: dict[str, Any] = {}
    for receiver, lab in (("tailored", "t_m{m}"), ("untailored", "zs_m{m}")):
        for m in (6, 9, 11):
            rows = store(lab.format(m=m))
            cnt = depth_counts(rows)
            detail = []
            for task_id, seed in cnt["handoff_false_but_executor_acted_keys"]:
                r = rows[(task_id, seed)]
                s = src_rows.get((task_id, seed), {})
                detail.append({
                    "task_id": task_id, "seed": seed,
                    "effective_m": r["_facts"]["effective_m"],
                    "n_source_actions": r["_facts"]["n_source_actions"],
                    "executor_n_calls": executor_calls(r),
                    "source_error_type": s.get("error_type"),
                    "source_success": s.get("success"),
                })
            resolution[f"{receiver}_m{m}"] = {
                "handoff_occurred_false": cnt["n_handoff_occurred_false"],
                "executor_never_acted": cnt["n_executor_never_acted"],
                "handoff_false_but_executor_acted": cnt["n_handoff_false_but_executor_acted"],
                "detail_of_the_difference": detail,
            }
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "families": families,
        "silenced_count_resolution": resolution,
        "definitions": {
            "handoff_occurred": "payload.handoff_occurred of the last `report` event of the last attempt (j13_mechanism)",
            "silenced / prefix-exhausted": "handoff_occurred not true (the j13 decomposition's S set)",
            "executor_never_acted": "result.json totals.per_actor.executor.n_calls == 0 (GUARD-01's count)",
        },
    }


# --------------------------------------------------------------------------------------
# F-d  Hinge vs linear
# --------------------------------------------------------------------------------------


def _solve(a: list[list[float]], b: list[float]) -> Optional[list[float]]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        div = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


def ols_linear(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float]:
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b1 = sxy / sxx
    b0 = my - b1 * mx
    sse = sum((y - b0 - b1 * x) ** 2 for x, y in zip(xs, ys))
    return b0, b1, sse


def ols_hinge(xs: Sequence[float], ys: Sequence[float], tau: float) -> tuple[Optional[list[float]], float]:
    """q = b0 + b1 m + b2 (m - tau)_+ ; the hj12_shape.ols_segmented design."""
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0] * 3
    for x, y in zip(xs, ys):
        row = (1.0, float(x), max(float(x) - float(tau), 0.0))
        for i in range(3):
            xty[i] += row[i] * float(y)
            for j in range(3):
                xtx[i][j] += row[i] * row[j]
    beta = _solve(xtx, xty)
    if beta is None:
        return None, float("inf")
    sse = 0.0
    for x, y in zip(xs, ys):
        pred = beta[0] + beta[1] * x + beta[2] * max(x - tau, 0.0)
        sse += (float(y) - pred) ** 2
    return beta, sse


def fit_shape(ms: Sequence[float], qs: Sequence[float], taus: Sequence[float]) -> dict[str, Any]:
    """Linear and best-hinge fits on (m, q) points; ties take the smallest tau (hj12_shape)."""
    xs = [float(m) for m in ms]
    b0l, b1l, sse_l = ols_linear(xs, qs)
    ranked = []
    profile = {}
    for tau in taus:
        beta, sse = ols_hinge(xs, qs, float(tau))
        if beta is None:
            continue
        profile[tau] = sse
        ranked.append((sse, tau, beta))
    mean_q = sum(qs) / len(qs)
    tss = sum((q - mean_q) ** 2 for q in qs)
    tol = 1e-12 * max(tss, 1.0)
    best = min(r[0] for r in ranked)
    tied = sorted([r for r in ranked if r[0] <= best + tol], key=lambda r: (r[1], r[0]))
    sse_h, tau, beta = tied[0]
    n = len(qs)
    delta = sse_l - sse_h
    if delta <= tol:  # numerically no improvement (e.g. data exactly on a line)
        bic_pref = aic_pref = False
    elif sse_h <= tol:  # the hinge fits exactly and the line does not
        bic_pref = aic_pref = True
    else:
        lr = n * math.log(sse_l / sse_h)
        bic_pref = lr > 2 * math.log(n)  # two extra parameters: b2 and tau
        aic_pref = lr > 4.0
    return {
        "n_points": n,
        "linear": {"b0": b0l, "b1": b1l, "sse": sse_l,
                   "fitted": [b0l + b1l * x for x in xs]},
        "hinge": {"tau": tau, "b0": beta[0], "b1": beta[1], "b2": beta[2],
                  "b1_plus_b2": beta[1] + beta[2], "sse": sse_h},
        "delta_sse": delta,
        "hinge_preferred_bic": bool(bic_pref),
        "hinge_preferred_aic": bool(aic_pref),
        "sse_profile_by_tau": {str(t): s for t, s in profile.items()},
    }


def build_panel(
    store: ArmStore,
    labels_by_m: dict[int, str],
    field: str,
    restrict: Optional[set[Key]] = None,
) -> dict[int, dict[Key, float]]:
    arms = {m: store(label) for m, label in labels_by_m.items()}
    keys = None
    for rows in arms.values():
        ks = {k for k, r in rows.items() if j10_clean(r)}
        keys = ks if keys is None else keys & ks
    if restrict is not None and keys is not None:
        keys &= restrict
    panel: dict[int, dict[Key, float]] = {}
    for m, rows in arms.items():
        vals = {}
        for k in keys or set():
            v = quality(rows[k], field)
            if v is not None:
                vals[k] = v
        panel[int(m)] = vals
    return panel


def bootstrap_shape(
    panel: dict[int, dict[Key, float]],
    taus: Sequence[float],
    unit: str,
    seed: int,
    n_boot: int,
) -> dict[str, Any]:
    """Refit linear and hinge (tau profiled) in every cluster resample, and a null-calibrated
    copy: each depth's resample mean shifted by (linear fit - observed mean) at the point
    estimate, i.e. the same clustered noise around an exactly linear mean curve."""
    ms = sorted(panel)
    keys = sorted(set.intersection(*(set(panel[m]) for m in ms)))
    cof = _cluster_fn(unit)
    grouped: dict[Any, list[float]] = {}
    for k in keys:
        vec = grouped.setdefault(cof(k), [0.0] * (len(ms) + 1))
        for i, m in enumerate(ms):
            vec[i] += panel[m][k]
        vec[-1] += 1.0
    clusters = sorted(grouped)
    vecs = [grouped[c] for c in clusters]
    nc = len(vecs)
    total = [sum(v[j] for v in vecs) for j in range(len(ms) + 1)]
    qs = [total[i] / total[-1] for i in range(len(ms))]
    point = fit_shape(ms, qs, taus)
    shift = [point["linear"]["fitted"][i] - qs[i] for i in range(len(ms))]
    rng = random.Random(seed)
    draw = rng.randrange
    deltas, deltas_null, taus_b, slopes, b1s, b12s = [], [], [], [], [], []
    bic = aic = 0
    for _ in range(n_boot):
        tot = [0.0] * (len(ms) + 1)
        for _ in range(nc):
            v = vecs[draw(nc)]
            for j in range(len(ms) + 1):
                tot[j] += v[j]
        qb = [tot[i] / tot[-1] for i in range(len(ms))]
        fb = fit_shape(ms, qb, taus)
        fn = fit_shape(ms, [qb[i] + shift[i] for i in range(len(ms))], taus)
        deltas.append(fb["delta_sse"])
        deltas_null.append(fn["delta_sse"])
        taus_b.append(fb["hinge"]["tau"])
        slopes.append(fb["linear"]["b1"])
        b1s.append(fb["hinge"]["b1"])
        b12s.append(fb["hinge"]["b1_plus_b2"])
        bic += int(fb["hinge_preferred_bic"])
        aic += int(fb["hinge_preferred_aic"])

    def pct(xs: list[float]) -> list[float]:
        s = sorted(xs)
        return [s[int(0.025 * len(s))], s[int(0.975 * len(s))]]

    null_sorted = sorted(deltas_null)
    null95 = null_sorted[int(0.95 * len(null_sorted))]
    obs = point["delta_sse"]
    tau_counts = {str(int(t) if float(t).is_integer() else t): c
                  for t, c in sorted(Counter(taus_b).items())}
    modal_tau, modal_n = Counter(taus_b).most_common(1)[0]
    tau_ci = pct(taus_b)
    return {
        "unit": unit, "seed": seed, "n_boot": n_boot, "n_keys": len(keys), "n_clusters": nc,
        "means": {str(m): q for m, q in zip(ms, qs)},
        "point": point,
        "delta_sse_ci95": pct(deltas),
        "delta_sse_pp2": obs * 1e4,
        "delta_sse_pp2_ci95": [x * 1e4 for x in pct(deltas)],
        "share_hinge_sse_below_linear": sum(1 for d in deltas if d > 1e-15) / n_boot,
        "share_hinge_preferred_bic": bic / n_boot,
        "share_hinge_preferred_aic": aic / n_boot,
        "null_linear": {
            "delta_sse_null_median": null_sorted[len(null_sorted) // 2],
            "delta_sse_null_95th": null95,
            "p_value": (1 + sum(1 for d in deltas_null if d >= obs)) / (n_boot + 1),
            "share_resamples_delta_above_null95": sum(1 for d in deltas if d > null95) / n_boot,
        },
        "linear_slope_pp_per_step": point["linear"]["b1"] * 100,
        "linear_slope_pp_per_step_ci95": [x * 100 for x in pct(slopes)],
        "hinge_b1_ci95": pct(b1s),
        "hinge_b1_plus_b2_ci95": pct(b12s),
        "tau": point["hinge"]["tau"],
        "tau_counts": tau_counts,
        "tau_ci95": tau_ci,
        "tau_modal": modal_tau,
        "tau_modal_share": modal_n / n_boot,
        "breakpoint_localized": bool(tau_ci[0] == tau_ci[1] and modal_n / n_boot >= 0.8),
    }


def section_fd(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    post_name = "hj13_shape_post_guard_20260923.report.json"
    pre_name = "hj13_shape_pre_guard_20260923.report.json"
    post_pops = load_report(post_name)["populations"]
    post = post_pops["all_episodes"]
    pre = load_report(pre_name)["populations"]["all_episodes"]
    post_labels = {0: "plan_only", **{m: f"t_m{m}" for m in (2, 4, 6, 7, 8, 9, 10, 11)}}
    pre_labels = {0: "plan_only", **{m: f"t_pre_m{m}" for m in (2, 4, 6, 7, 8, 9, 10, 11)}}
    pin10 = {k for k, r in store("t_m10").items() if handoff_flag(r) is True}
    pin11 = {k for k, r in store("t_m11").items() if handoff_flag(r) is True}
    panels = {
        "post_guard_goal_pass": build_panel(store, post_labels, "goal_pass_rate"),
        "pre_guard_goal_pass": build_panel(store, pre_labels, "goal_pass_rate"),
        "post_guard_pinned_m10_goal_pass": build_panel(store, post_labels, "goal_pass_rate", pin10),
        "post_guard_pinned_m11_goal_pass": build_panel(store, post_labels, "goal_pass_rate", pin11),
    }
    for tag, rep, name, pop in (
        ("post_guard_goal_pass", post, post_name, "all_episodes"),
        ("pre_guard_goal_pass", pre, pre_name, "all_episodes"),
        ("post_guard_pinned_m10_goal_pass", post_pops["handoff_keys_m10"], post_name, "handoff_keys_m10"),
        ("post_guard_pinned_m11_goal_pass", post_pops["handoff_keys_m11"], post_name, "handoff_keys_m11"),
    ):
        panel = panels[tag]
        means = {m: statistics.fmean(panel[m].values()) for m in sorted(panel)}
        repro.check_exact(tag, rel(name), f"populations.{pop}.n_keys", rep["n_keys"], len(panel[0]))
        for row in rep["curve_goal_pass"]:
            repro.check(tag, rel(name), f"populations.{pop}.curve_goal_pass[m={row['m']}]",
                        row["goal_pass_rate"], means[int(row["m"])], 6)
        fit = fit_shape(sorted(means), [means[m] for m in sorted(means)], TAU_REGISTERED)
        pt = rep["scenario"]["point"]
        repro.check_exact(tag, rel(name), f"populations.{pop}.scenario.point.tau", pt["tau"], fit["hinge"]["tau"])
        for k_rep, k_mine in (("beta0", "b0"), ("beta1", "b1"), ("beta2", "b2"), ("rss", "sse")):
            repro.check(tag, rel(name), f"populations.{pop}.scenario.point.{k_rep}", pt[k_rep],
                        fit["hinge"][k_mine], 6)
    # The registered bootstrap itself: tau counts are an exact function of the draws.
    legacy = {}
    for tag, pop, units in (("post_guard_goal_pass", "all_episodes", ("scenario", "task")),
                            ("post_guard_pinned_m10_goal_pass", "handoff_keys_m10", ("scenario",)),
                            ("post_guard_pinned_m11_goal_pass", "handoff_keys_m11", ("scenario",))):
        for unit in units:
            b = bootstrap_shape(panels[tag], TAU_REGISTERED, unit, LEGACY_SEED, n_boot)
            legacy[f"{tag}__{unit}"] = b
            exp = post_pops[pop][unit]
            src = rel(post_name)
            repro.check_exact("registered shape bootstrap", src, f"populations.{pop}.{unit}.tau_counts",
                              {str(k): v for k, v in exp["tau_counts"].items()}, b["tau_counts"])
            repro.check("registered shape bootstrap", src, f"populations.{pop}.{unit}.tau_ci95",
                        exp["tau_ci95"], b["tau_ci95"], 6)
            repro.check("registered shape bootstrap", src, f"populations.{pop}.{unit}.beta1_plus_beta2_ci95",
                        exp["beta1_plus_beta2_ci95"], b["hinge_b1_plus_b2_ci95"], 6)
    if not repro.all_ok:
        return stopped("F-d", repro)

    panels["post_guard_tgc"] = build_panel(store, post_labels, "tgc")
    panels["post_guard_prefix_only_goal_pass"] = {m: v for m, v in panels["post_guard_goal_pass"].items() if m != 0}
    fits: dict[str, Any] = {}
    specs = [
        ("primary: post-guard m in {0(plan_only),2,4,6..11}, goal_pass, registered taus", "post_guard_goal_pass", TAU_REGISTERED),
        ("post-guard, goal_pass, expanded taus {2,4,6..10}", "post_guard_goal_pass", TAU_EXPANDED),
        ("post-guard prefix arms only m in {2,4,6..11}, goal_pass", "post_guard_prefix_only_goal_pass", TAU_REGISTERED),
        ("post-guard, TGC, registered taus", "post_guard_tgc", TAU_REGISTERED),
        ("pre-guard m in {0,2,4,6..11}, goal_pass, registered taus", "pre_guard_goal_pass", TAU_REGISTERED),
        ("post-guard pinned to m10 handoff keys (n=71), goal_pass", "post_guard_pinned_m10_goal_pass", TAU_REGISTERED),
        ("post-guard pinned to m11 handoff keys (n=54), goal_pass", "post_guard_pinned_m11_goal_pass", TAU_REGISTERED),
    ]
    for i, (desc, panel_name, taus) in enumerate(specs):
        tag = f"{panel_name}__taus_{'-'.join(str(t) for t in taus)}"
        blk = {"description": desc, "taus": list(taus)}
        for unit in ("scenario", "task"):
            blk[unit] = bootstrap_shape(panels[panel_name], taus, unit, SEED, n_boot)
        fits[tag] = blk
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "legacy_seed_bootstrap_post_guard": legacy,
        "fits": fits,
        "not_computable": {
            "untailored (zero-shot) receiver": (
                "only m in {6, 9, 11} exist (plus no untailored plan-only arm to serve as m=0): a "
                "hinge has 3 coefficients plus tau, so 3 points are fit exactly (SSE 0) for any "
                "interior tau and the comparison carries no information."
            ),
            "cap-81-sourced curves (both receivers, 2 or 3 seeds)": "only m in {6, 9, 11}; same reason.",
        },
        "method": (
            "OLS on the per-depth means over the shared keys (equal n per depth, so identical "
            "coefficients to episode-level OLS; episode-level SSE differences are n x these). "
            "delta_sse = SSE(linear) - SSE(best hinge); the hinge nests the line so delta_sse >= 0 "
            "by construction and 'hinge SSE below linear' is ~100% trivially. The informative "
            "tests are (i) the null-calibrated bootstrap p-value: depth means shifted onto the "
            "fitted line, same scenario resamples, share of null delta_sse >= observed; "
            "(ii) the share of resamples in which BIC (or AIC) on the 9 means prefers the hinge "
            "after charging it b2 and tau. Breakpoint 'localized' = the 95% bootstrap interval of "
            "tau is a single candidate AND the modal tau holds >= 80% of resamples (a threshold "
            "chosen here, not registered)."
        ),
    }


# --------------------------------------------------------------------------------------
# F-e  NI against both ceilings + CEIL-01 sensitivity + selection
# --------------------------------------------------------------------------------------

NI_ARMS = [
    "executor_alone", "plan_only", "advise_oracle_esc_starved", "advise_k10_starved",
    "advise_k3_starved", "advise_k10_fullctx", "advise_k1_fullctx", "takeover_k10",
    "t_m6", "t_m9", "t_m11", "t_pre_m9", "t_pre_m11", "zs_m6", "zs_m9", "zs_m11",
    "c81_t_m9", "c81_t_m11", "c81_zs_m9", "c81_zs_m11",
]
REFS = {"cap25": "ceiling_cap25", "cap81": "ceiling_cap81"}


def pairing_type(arm: str, ref: str) -> str:
    if arm.startswith(("t_", "zs_")):
        return "trajectory-paired" if ref == "ceiling_cap25" else "task-paired (different planner sample)"
    if arm.startswith("c81"):
        return "trajectory-paired" if ref == "ceiling_cap81" else "task-paired (different planner sample)"
    if arm in ("executor_alone",):
        return "task-paired"
    return ("plan-paired (replays the cap-25 run's cached plan packet)" if ref == "ceiling_cap25"
            else "task-paired (replays the cap-25 plan packet)")


def ni_entry(store: ArmStore, arm: str, ref: str, field: str, keys: Optional[set[Key]], n_boot: int) -> dict[str, Any]:
    c = contrast(store, arm, ref, field, keys=keys,
                 boots=(("scenario", SEED), ("task", SEED), ("scenario", LEGACY_SEED)), n_boot=n_boot)
    scen = c["scenario"]["ci95_pp"]
    task = c["task"]["ci95_pp"]
    leg = c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"]
    c["ni_holds_scenario"] = ni_holds(scen)
    c["ni_holds_task"] = ni_holds(task)
    c["ni_holds_scenario_seed20260915"] = ni_holds(leg)
    c["seed_fragile"] = c["ni_holds_scenario"] != c["ni_holds_scenario_seed20260915"]
    c["clustering_fragile"] = c["ni_holds_scenario"] != c["ni_holds_task"]
    c["excludes_zero_scenario"] = excludes_zero(scen)
    c["pairing"] = pairing_type(arm, ref)
    return c


def selection_block(store: ArmStore, ref_label: str, arm_labels: list[str], n_boot: int) -> dict[str, Any]:
    ref = store(ref_label)
    dropped = sorted(k for k, r in ref.items() if r.get("error_type") == LIMIT)
    dset = set(dropped)
    out: dict[str, Any] = {
        "reference": ref_label,
        "criterion": "reference error_type == 'limit' (episode ended at its binding planner-call/step limit)",
        "n_reference": len(ref), "n_dropped": len(dropped), "n_kept": len(ref) - len(dropped),
        "dropped_keys": [f"{k[0]}|{k[1]}" for k in dropped],
        "per_arm": {},
    }
    for label in [ref_label, *arm_labels]:
        rows = store(label)
        comps = {}
        for k in sorted(set(rows) & set(ref)):
            if not j10_clean(rows[k]):
                continue
            y = quality(rows[k], "goal_pass_rate")
            if y is None:
                continue
            d = 1.0 if k in dset else 0.0
            comps[k] = (y * (1 - d), 1 - d, y * d, d)

        def kept_minus_dropped(t: list[float]) -> Optional[float]:
            if t[1] == 0 or t[3] == 0:
                return None
            return t[0] / t[1] - t[2] / t[3]

        b = bootstrap_multi(comps, {"kept": ratio(0, 1), "dropped": ratio(2, 3),
                                    "kept_minus_dropped": kept_minus_dropped}, "scenario", SEED, n_boot)
        st = b["stats"]
        entry = {
            "goal_pass_kept": st["kept"]["point"], "goal_pass_dropped": st["dropped"]["point"],
            "kept_minus_dropped_pp": None if st["kept_minus_dropped"]["point"] is None else 100 * st["kept_minus_dropped"]["point"],
            "kept_minus_dropped_ci95_pp_scenario": None if st["kept_minus_dropped"]["ci95"] is None
            else [100 * x for x in st["kept_minus_dropped"]["ci95"]],
            "n_resamples_without_a_dropped_episode": st["kept_minus_dropped"]["n_undefined"],
        }
        if label != ref_label:
            full, _ = paired_diffs(rows, ref, "goal_pass_rate")
            keep_d = {k: v for k, v in full.items() if k not in dset}
            drop_d = {k: v for k, v in full.items() if k in dset}
            entry["arm_minus_ref_all_pp"] = 100 * statistics.fmean(full.values()) if full else None
            entry["arm_minus_ref_kept_pp"] = 100 * statistics.fmean(keep_d.values()) if keep_d else None
            entry["arm_minus_ref_dropped_pp"] = 100 * statistics.fmean(drop_d.values()) if drop_d else None
            entry["weight_dropped"] = len(drop_d) / len(full) if full else None
        out["per_arm"][label] = entry
    return out


def section_fe(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    uf_name = "hj12_unified_frontier_scenario_20260923.report.json"
    nl_name = "hj12_unified_frontier_scenario_nolimit_20260923.report.json"
    c81_name = "hj13_arms_vs_cap81_20260923.report.json"
    cc_name = "hj13_ceiling_cap25_vs_cap81_20260923.report.json"
    uf, nl, c81, cc = (load_report(n) for n in (uf_name, nl_name, c81_name, cc_name))
    leg = (("scenario", LEGACY_SEED), ("task", LEGACY_SEED))
    ref25 = store("ceiling_cap25")
    kept25 = {k for k, r in ref25.items() if r.get("error_type") != LIMIT}
    uf_map = {"prefix_m11": "t_pre_m11", "prefix_m9": "t_pre_m9", "sft_plan": "plan_only",
              "advise_fixed_k_3": "advise_k3_starved", "advise_fixed_k_10": "advise_k10_starved",
              "advise_oracle_esc": "advise_oracle_esc_starved", "executor_alone": "executor_alone"}
    for rkey, label in uf_map.items():
        for rep, name, keys, block in (
            (uf, uf_name, None, ("noninferiority", "arms")),
            (nl, nl_name, kept25, ("exclude_reference_limit_sensitivity", "noninferiority", "arms")),
        ):
            node = rep
            for part in block:
                node = node[part]
            for jf, field in (("goal_pass_all", "goal_pass_rate"), ("tgc_all", "tgc")):
                e = node[rkey][jf]
                c = contrast(store, label, "ceiling_cap25", field, keys=keys, boots=leg, n_boot=n_boot)
                path = ".".join(block) + f".{rkey}.{jf}"
                repro.check(f"NI cap25 {label}", rel(name), f"{path}.diff_pp", e["diff_pp"], c["diff_pp"], 2)
                repro.check(f"NI cap25 {label}", rel(name), f"{path}.ci95_pp", e["ci95_pp"],
                            c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"], 2)
                repro.check(f"NI cap25 {label}", rel(name), f"{path}.ci95_pp_task", e["ci95_pp_task"],
                            c[_boot_name("task", LEGACY_SEED)]["ci95_pp"], 2)
    repro.check_exact("CEIL-01", rel(nl_name), "reference_episodes_excluded_limit.n_excluded",
                      nl["reference_episodes_excluded_limit"]["n_excluded"], len(ref25) - len(kept25))
    for rkey, label in (("tailored_m11", "t_m11"), ("tailored_m9", "t_m9"), ("zs_m11", "zs_m11"), ("zs_m9", "zs_m9")):
        e = c81["noninferiority"]["arms"][rkey]["goal_pass_all"]
        c = contrast(store, label, "ceiling_cap81", "goal_pass_rate", boots=leg, n_boot=n_boot)
        path = f"noninferiority.arms.{rkey}.goal_pass_all"
        repro.check(f"NI cap81 {label}", rel(c81_name), f"{path}.diff_pp", e["diff_pp"], c["diff_pp"], 2)
        repro.check(f"NI cap81 {label}", rel(c81_name), f"{path}.ci95_pp", e["ci95_pp"],
                    c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"], 2)
    for jf, field in (("goal_pass_all", "goal_pass_rate"), ("tgc_all", "tgc")):
        key = f"{jf}_ceiling_cap25_minus_ceiling_cap81"
        e = cc["contrasts"][key]
        c = contrast(store, "ceiling_cap25", "ceiling_cap81", field, boots=leg, n_boot=n_boot)
        repro.check("CEIL-01 (cap-81 rerun)", rel(cc_name), f"contrasts.{key}.diff_pp", e["diff_pp"], c["diff_pp"], 2)
        repro.check("CEIL-01 (cap-81 rerun)", rel(cc_name), f"contrasts.{key}.ci95_pp", e["ci95_pp"],
                    c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"], 2)
    for label, rkey in (("ceiling_cap25", "planner_alone"),):
        repro.check("arm mean", rel(uf_name), f"arms.{rkey}.goal_pass_all", uf["arms"][rkey]["goal_pass_all"],
                    arm_mean(store(label), "goal_pass_rate"), 6)
    if not repro.all_ok:
        return stopped("F-e", repro)

    table: dict[str, Any] = {}
    for arm in NI_ARMS:
        table[arm] = {"campaigns": [str(p) for p in store.dirs[arm]], "goal_pass_all": arm_mean(store(arm), "goal_pass_rate"),
                      "tgc_all": arm_mean(store(arm), "tgc")}
        for tag, ref in REFS.items():
            for field in ("goal_pass_rate", "tgc"):
                table[arm][f"{tag}_{field}"] = ni_entry(store, arm, ref, field, None, n_boot)
    sensitivity: dict[str, Any] = {}
    for tag, ref in REFS.items():
        rrows = store(ref)
        kept = {k for k, r in rrows.items() if r.get("error_type") != LIMIT}
        blk: dict[str, Any] = {"reference": ref, "n_reference_kept": len(kept),
                               "n_reference_dropped_limit": len(rrows) - len(kept),
                               "reference_goal_pass_kept": statistics.fmean(
                                   quality(rrows[k], "goal_pass_rate") for k in kept),
                               "arms": {}}
        for arm in NI_ARMS:
            blk["arms"][arm] = {
                "goal_pass_rate": ni_entry(store, arm, ref, "goal_pass_rate", kept, n_boot),
                "tgc": ni_entry(store, arm, ref, "tgc", kept, n_boot),
            }
        sensitivity[tag] = blk
    selection = {tag: selection_block(store, ref, NI_ARMS, n_boot) for tag, ref in REFS.items()}
    flips = []
    for arm in NI_ARMS:
        for tag in REFS:
            for field in ("goal_pass_rate", "tgc"):
                full = table[arm][f"{tag}_{field}"]
                sens = sensitivity[tag]["arms"][arm][field]
                row = {"arm": arm, "reference": tag, "field": field,
                       "holds_as_run": full["ni_holds_scenario"], "holds_limit_excluded": sens["ni_holds_scenario"],
                       "seed_fragile_as_run": full["seed_fragile"], "seed_fragile_limit_excluded": sens["seed_fragile"],
                       "clustering_fragile_as_run": full["clustering_fragile"]}
                if (row["holds_as_run"] != row["holds_limit_excluded"] or row["seed_fragile_as_run"]
                        or row["seed_fragile_limit_excluded"] or row["clustering_fragile_as_run"]):
                    flips.append(row)
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "rule": "arm - reference; non-inferior iff round(scenario lower bound, 2) >= -7.00 (j8_frontier)",
        "ni_table": table,
        "limit_excluded_sensitivity": sensitivity,
        "selection_induced_by_limit_exclusion": selection,
        "verdict_changes_and_fragile_verdicts": flips,
    }


# --------------------------------------------------------------------------------------
# F-f  Cost-difference intervals, GPU seconds
# --------------------------------------------------------------------------------------

COST_AXES = ("noncached_tokens_per_episode", "usd_per_episode", "hosted_calls_per_episode")
FF_ARMS = ["takeover_k10", "advise_k10_fullctx", "advise_k1_fullctx", "t_m11", "t_m9",
           "ceiling_cap25", "ceiling_cap81", "advise_k3_starved", "t_pre_m6", "t_m6", "t_m6_rep"]
FF_PAIRS = [
    ("C1: takeover_k10 - advise_k10_fullctx", "takeover_k10", "advise_k10_fullctx"),
    ("H2 (P2): advise_k1_fullctx - prefix_m11", "advise_k1_fullctx", "t_m11"),
    ("H2: advise_k1_fullctx - prefix_m9", "advise_k1_fullctx", "t_m9"),
    ("prefix_m11 - ceiling_cap25", "t_m11", "ceiling_cap25"),
    ("prefix_m11 - ceiling_cap81", "t_m11", "ceiling_cap81"),
]


def _load_module(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / filename)
    if spec is None or spec.loader is None:
        raise ImportError(filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_cost_rows(labels: list[str], dirs: dict[str, list[Path]]) -> tuple[dict[str, dict[Key, dict[str, Any]]], dict[str, Any]]:
    """Per-episode cost axes exactly as j12_cost_axes.main computes them (reused, not reimplemented)."""
    j12 = _load_module("j12_cost_axes", "j12_cost_axes.py")
    card = j12.load_price_card(PRICES)
    rows: dict[str, dict[Key, dict[str, Any]]] = {}
    summaries: dict[str, Any] = {}
    for label in labels:
        roots = dirs[label]
        if len(roots) != 1:
            raise ValueError(f"cost rows need a single campaign root for {label}")
        root = roots[0]
        loaded = j12.j10.load_arm_tree(root)
        arm = j12.summarise_arm(label, loaded, [1, 2], root=root, packet_source=HJ1B, packet_system="planner_alone")
        summaries[label] = j12.price_arm_episodes(arm, card, root=root, packet_source=HJ1B, packet_system="planner_alone")
        rows[label] = arm["cleaned"]
    return rows, summaries


def cost_contrast(a: dict[Key, dict[str, Any]], b: dict[Key, dict[str, Any]], axis: str,
                  boots: Sequence[tuple[str, int]], n_boot: int) -> dict[str, Any]:
    diffs: dict[Key, float] = {}
    ratio_comps: dict[Key, tuple[float, float]] = {}
    missing = 0
    for k in sorted(set(a) & set(b)):
        va, vb = a[k].get(axis), b[k].get(axis)
        if va is None or vb is None:
            missing += 1
            continue
        diffs[k] = float(va) - float(vb)
        ratio_comps[k] = (float(va), float(vb))
    out: dict[str, Any] = {
        "axis": axis, "n_pairs": len(diffs), "n_dropped_missing": missing,
        "mean_left": statistics.fmean(v[0] for v in ratio_comps.values()) if ratio_comps else None,
        "mean_right": statistics.fmean(v[1] for v in ratio_comps.values()) if ratio_comps else None,
        "diff": statistics.fmean(diffs.values()) if diffs else None,
    }
    for unit, seed in boots:
        bm = boot_mean(diffs, unit, seed, n_boot)
        br = bootstrap_multi(ratio_comps, {"ratio": ratio(0, 1)}, unit, seed, n_boot)["stats"]["ratio"]
        out[_boot_name(unit, seed)] = {"diff_ci95": bm["ci95"], "ratio_ci95": br["ci95"], "n_clusters": bm["n_clusters"]}
    out["ratio_left_over_right"] = (out["mean_left"] / out["mean_right"]) if out["mean_right"] else None
    return out


def executor_token_rows(rows: dict[Key, dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    return {k: {"executor_tokens_per_episode": r["_facts"]["executor_tokens_total"]} for k, r in rows.items()}


def section_ff(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    try:
        cost_rows, summaries = load_cost_rows(FF_ARMS, store.dirs)
    except Exception as exc:  # j8/j10/j12 are edited concurrently; fail this item loudly, not the run
        return {"status": "not_computable", "note": f"j12_cost_axes pricing failed to load/run: {exc!r}"}
    fx_name = "hj13_cost_axes_fixed_20260923.report.json"
    ni_name = "hj13_cost_axes_ni_20260923.report.json"
    fx, nirep = load_report(fx_name), load_report(ni_name)
    name_map = {"takeover_k10": "takeover_k10", "advise_k10_fullctx": "advise_k10_fullctx", "t_m11": "prefix_m11",
                "t_m9": "prefix_m9", "ceiling_cap25": "ceiling_cap25", "ceiling_cap81": "ceiling_cap81",
                "advise_k3_starved": "advise_k3_starved", "t_m6": "prefix_m6"}
    for label, rkey in name_map.items():
        for axis in COST_AXES:
            repro.check("COST-01 arm cost", rel(fx_name), f"arms.{rkey}.{axis}", fx["arms"][rkey][axis],
                        summaries[label][axis], 6 if axis == "usd_per_episode" else 4)
    for axis in COST_AXES:
        e = nirep["non_inferiority"]["comparisons"]["prefix_m11"]["axes"][axis]
        c = cost_contrast(cost_rows["t_m11"], cost_rows["ceiling_cap81"], axis, (("scenario", LEGACY_SEED),), n_boot)
        # j8_frontier stores round(100 x value, 2) / 100 -> compare at 4 native decimals.
        repro.check("COST-03", rel(ni_name), f"non_inferiority.comparisons.prefix_m11.axes.{axis}.diff",
                    e["diff"], c["diff"], 4)
        repro.check("COST-03", rel(ni_name), f"non_inferiority.comparisons.prefix_m11.axes.{axis}.ci95",
                    e["ci95"], c[_boot_name("scenario", LEGACY_SEED)]["diff_ci95"], 4)
    if not repro.all_ok:
        return stopped("F-f", repro)

    pairs: dict[str, Any] = {}
    for name, left, right in FF_PAIRS:
        blk: dict[str, Any] = {"left": left, "right": right}
        for axis in COST_AXES:
            blk[axis] = cost_contrast(cost_rows[left], cost_rows[right], axis, DEFAULT_BOOTS, n_boot)
        blk["executor_tokens_per_episode"] = cost_contrast(
            executor_token_rows(store(left)), executor_token_rows(store(right)),
            "executor_tokens_per_episode", DEFAULT_BOOTS, n_boot)
        pairs[name] = blk
    gpu: dict[str, Any] = {}
    for label in FF_ARMS:
        facts = [r["_facts"] for r in store(label).values()]
        walls = sorted(f["wall_clock_s"] for f in facts if f["wall_clock_s"] is not None)
        gpu[label] = {
            "n_episodes": len(facts),
            "n_result_gpu_seconds_total_positive": sum(1 for f in facts if (f["gpu_seconds_total"] or 0) > 0),
            "n_result_executor_gpu_seconds_positive": sum(1 for f in facts if (f["executor_gpu_seconds"] or 0) > 0),
            "n_executor_usage_records": sum(f["executor_usage_records"] for f in facts),
            "n_executor_usage_latency_s_present": sum(f["executor_latency_present"] for f in facts),
            "n_executor_usage_latency_s_positive": sum(f["executor_latency_positive"] for f in facts),
            "n_executor_usage_gpu_seconds_positive": sum(f["executor_gpu_positive"] for f in facts),
            "executor_tokens_per_episode": statistics.fmean(
                f["executor_tokens_total"] for f in facts if f["executor_tokens_total"] is not None)
            if any(f["executor_tokens_total"] is not None for f in facts) else None,
            "wall_clock_s_median_PROXY_NOT_GPU": walls[len(walls) // 2] if walls else None,
            "wall_clock_s_mean_PROXY_NOT_GPU": statistics.fmean(walls) if walls else None,
        }
    derivable = any(v["n_executor_usage_latency_s_positive"] or v["n_result_gpu_seconds_total_positive"]
                    or v["n_executor_usage_gpu_seconds_positive"] for v in gpu.values())
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "arm_cost_means": {k: {a: summaries[k][a] for a in COST_AXES} for k in FF_ARMS},
        "pairs": pairs,
        "gpu_seconds": {
            "derivable": derivable,
            "fields_inspected": [
                "result.json totals.gpu_seconds_total",
                "result.json totals.per_actor.executor.gpu_seconds",
                "events.jsonl executor `usage.latency_s` and `usage.gpu_seconds` "
                "(usage.raw.gpu_seconds_formula = 'latency_s * gpu_fraction')",
            ],
            "per_arm": gpu,
            "proxy_note": (
                "wall_clock_s = events run_end.ts - manifest.json created_at. It includes hosted "
                "planner latency, AppWorld time and concurrency on a shared vLLM server, so it is "
                "NOT GPU-seconds; reported only as a descriptive proxy. executor tokens "
                "(result.json totals.executor_tokens_total) are the recorded local-compute quantity."
            ),
        },
        "units": "tokens and hosted calls per episode; USD per episode at configs/cost/prices_2026-09.yaml",
    }


# --------------------------------------------------------------------------------------
# F-g  advise_k3 (starved) vs prefix_m6
# --------------------------------------------------------------------------------------


def section_fg(store: ArmStore, n_boot: int) -> dict[str, Any]:
    repro = Repro()
    uf_name = "hj12_unified_frontier_scenario_20260923.report.json"
    uf = load_report(uf_name)
    leg = (("scenario", LEGACY_SEED), ("task", LEGACY_SEED))
    for rkey, label in (("advise_fixed_k_3", "advise_k3_starved"), ("prefix_m6", "t_pre_m6")):
        for jf, field in (("goal_pass_all", "goal_pass_rate"), ("tgc_all", "tgc")):
            repro.check("arm mean", rel(uf_name), f"arms.{rkey}.{jf}", uf["arms"][rkey][jf],
                        arm_mean(store(label), field), 6)
    for jf, field in (("goal_pass_all", "goal_pass_rate"), ("tgc_all", "tgc")):
        key = f"{jf}_advise_fixed_k_3_minus_prefix_m6"
        e = uf["contrasts"][key]
        c = contrast(store, "advise_k3_starved", "t_pre_m6", field, boots=leg, n_boot=n_boot)
        repro.check("unified frontier k3 vs m6", rel(uf_name), f"contrasts.{key}.diff_pp", e["diff_pp"], c["diff_pp"], 2)
        repro.check("unified frontier k3 vs m6", rel(uf_name), f"contrasts.{key}.ci95_pp", e["ci95_pp"],
                    c[_boot_name("scenario", LEGACY_SEED)]["ci95_pp"], 2)
        repro.check("unified frontier k3 vs m6", rel(uf_name), f"contrasts.{key}.ci95_pp_task", e["ci95_pp_task"],
                    c[_boot_name("task", LEGACY_SEED)]["ci95_pp"], 2)
    try:
        cost_rows, summaries = load_cost_rows(["advise_k3_starved", "t_pre_m6", "t_m6", "t_m6_rep"], store.dirs)
    except Exception as exc:
        cost_rows, summaries = None, {"error": repr(exc)}
    if cost_rows is not None:
        for rkey, label in (("advise_fixed_k_3", "advise_k3_starved"), ("prefix_m6", "t_pre_m6")):
            repro.check("unified frontier cost", rel(uf_name), f"arms.{rkey}.cost_per_episode",
                        uf["arms"][rkey]["cost_per_episode"], summaries[label]["noncached_tokens_per_episode"], 4)
    if not repro.all_ok:
        return stopped("F-g", repro)

    quality_contrasts: dict[str, Any] = {}
    for label, desc in (("t_pre_m6", "pre-guard hj12_prefix_m6_20260922 (the unified-frontier arm)"),
                        ("t_m6", "post-guard hj12_prefix_m6_20260923 (the published curve)"),
                        ("t_m6_rep", "post-guard replicate hj12_prefix_m6_20260923rep")):
        quality_contrasts[label] = {
            "description": desc,
            "goal_pass_rate": contrast(store, "advise_k3_starved", label, "goal_pass_rate", n_boot=n_boot),
            "tgc": contrast(store, "advise_k3_starved", label, "tgc", n_boot=n_boot),
        }
    costs: dict[str, Any] = {}
    if cost_rows is not None:
        for label in ("t_pre_m6", "t_m6", "t_m6_rep"):
            costs[label] = {axis: cost_contrast(cost_rows["advise_k3_starved"], cost_rows[label], axis,
                                                DEFAULT_BOOTS, n_boot) for axis in COST_AXES}
    cfg_text = (REPO / "configs" / "hj8_fixed_k_3.yaml").read_text(encoding="utf-8")
    created = sorted(f["created_at"] for f in (r["_facts"] for r in store("advise_k3_starved").values())
                     if f["created_at"])
    fullctx_campaigns = sorted(p.name for p in RESULTS_DIR.iterdir()
                               if p.is_dir() and "fullctx" in p.name)
    k3_campaigns = sorted(p.name for p in RESULTS_DIR.iterdir()
                          if p.is_dir() and ("fixed_k_3" in p.name or "k3" in p.name))
    return {
        "status": "computed",
        "reproduction": repro.block(),
        "arms": {"advise_k3_starved": str(store.dirs["advise_k3_starved"][0]),
                 "t_pre_m6": str(store.dirs["t_pre_m6"][0]), "t_m6": str(store.dirs["t_m6"][0]),
                 "t_m6_rep": str(store.dirs["t_m6_rep"][0])},
        "quality_contrasts_advise_k3_minus_prefix_m6": quality_contrasts,
        "cost_contrasts_advise_k3_minus_prefix_m6": costs,
        "starved_context_evidence": {
            "config_declares_correct_context": "correct_context" in cfg_text,
            "config": "configs/hj8_fixed_k_3.yaml",
            "campaign_first_created_at": created[0] if created else None,
            "campaign_last_created_at": created[-1] if created else None,
            "correct_context_commit": CONTEXT_COMMIT,
            "correct_context_commit_time_utc": CONTEXT_COMMIT_TIME,
            "campaign_predates_commit": bool(created and created[-1] < CONTEXT_COMMIT_TIME),
            "advise_path_before_commit": "delta = '\\n'.join(transcript[-8:])  (git show 722e887 -- src/sidekick/systems/loop.py)",
            "fullctx_campaigns_on_disk": fullctx_campaigns,
            "k3_campaigns_on_disk": k3_campaigns,
        },
    }


# --------------------------------------------------------------------------------------
# Report assembly
# --------------------------------------------------------------------------------------

SECTIONS: dict[str, tuple[str, Callable[[ArmStore, int], dict[str, Any]]]] = {
    "fb": ("F_b_channel_tgc_sgc", section_fb),
    "fc": ("F_c_handoff_depth_curves", section_fc),
    "fd": ("F_d_hinge_vs_linear", section_fd),
    "fe": ("F_e_ni_both_ceilings", section_fe),
    "ff": ("F_f_cost_differences", section_ff),
    "fg": ("F_g_near_matched_advice", section_fg),
}


def round_floats(obj: Any, nd: int = 6) -> Any:
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return round(obj, nd)
    if isinstance(obj, dict):
        return {str(k): round_floats(v, nd) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, nd) for v in obj]
    return obj


def build_report(store: ArmStore, sections: list[str], n_boot: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_by": "scripts/analysis/j16_robustness.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "bootstrap": {"B": n_boot, "seed_new_intervals": SEED, "seed_reproductions": LEGACY_SEED,
                      "primary_cluster": "scenario (19)", "secondary_cluster": "task (57)",
                      "percentile_indices": "int(0.025 B), int(0.975 B)"},
        "conventions": {
            "population": "all episodes; error_type == 'crash' scores 0 (only crash; 'limit' is scored)",
            "pairing": "(task_id, seed); pairs need both rows j10-clean (j8_frontier population)",
            "ni_margin_pp": NI_MARGIN_PP,
            "held_out": "no test_normal / test_challenge path is read (refused by the loader)",
        },
    }
    for code in sections:
        key, fn = SECTIONS[code]
        print(f"[j16] section {code} ...", flush=True)
        try:
            report[key] = fn(store, n_boot)
        except Exception as exc:  # report, do not hide
            import traceback
            report[key] = {"status": "error", "error": repr(exc), "traceback": traceback.format_exc()}
        print(f"[j16] section {code}: {report[key].get('status')}", flush=True)
    report["arm_sources"] = {label: [str(p) for p in store.dirs[label]] for label in store.loaded_labels()}
    report["arm_summaries"] = {label: arm_summary(store(label)) for label in store.loaded_labels()}
    report["load_diagnostics"] = store.diagnostics
    return round_floats(report)


# --------------------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------------------


def _f(x: Any, nd: int = 2, signed: bool = True) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def _ci(ci: Any, nd: int = 2) -> str:
    if not ci:
        return "n/a"
    return f"[{ci[0]:+.{nd}f}, {ci[1]:+.{nd}f}]"


def render_markdown(rep: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# J16 reviewer robustness analyses (F-b .. F-g)")
    L.append("")
    L.append(f"Generated by `{rep['generated_by']}` at {rep['generated_at']}. B = {rep['bootstrap']['B']}, "
             f"new intervals seed {rep['bootstrap']['seed_new_intervals']}, reproductions at seed "
             f"{rep['bootstrap']['seed_reproductions']}; scenario-clustered primary, task alongside. "
             "Population: all episodes, crash = 0 (limit scored). NI margin 7.00 pp.")
    L.append("")
    L.append("Every section first reproduces the existing numbers it builds on; the reproduction table "
             "is in the JSON under `<section>.reproduction`.")
    L.append("")
    for key in ("F_b_channel_tgc_sgc", "F_c_handoff_depth_curves", "F_d_hinge_vs_linear",
                "F_e_ni_both_ceilings", "F_f_cost_differences", "F_g_near_matched_advice"):
        sec = rep.get(key)
        if sec is None:
            continue
        L.append(f"## {key}")
        L.append("")
        repb = sec.get("reproduction")
        L.append(f"Status: **{sec.get('status')}**" + (
            f"; reproduction {repb['n_matched']}/{repb['n_checked']} checks matched." if repb else ""))
        L.append("")
        if sec.get("status") != "computed":
            for fl in sec.get("failures", [])[:20]:
                L.append(f"- MISMATCH {fl['source']} `{fl['key']}`: expected {fl['expected']}, computed {fl['computed']}")
            if sec.get("error") or sec.get("note"):
                L.append(f"- {sec.get('error') or sec.get('note')}")
            L.append("")
            continue
        if key == "F_b_channel_tgc_sgc":
            L.append("Existing TGC contrasts (reproduced, seed 20260915):")
            L.append("")
            L.append("| claim | contrast | TGC pp | scenario CI | task CI | report key |")
            L.append("|---|---|---:|---|---|---|")
            for e in sec["existing_tgc_contrasts"]:
                if e["field"] != "tgc":
                    continue
                L.append(f"| {e['claim']} | {e['definition']} | {_f(e['diff_pp'])} | {_ci(e['ci95_pp_scenario'])} | "
                         f"{_ci(e['ci95_pp_task'])} | `{e['key']}` |")
            L.append("")
            L.append("New: SGC (scenario goal completion; unit = scenario x seed, 38 units, 19 clusters), seed 20260924:")
            L.append("")
            L.append("| contrast | SGC left | SGC right | diff pp | scenario CI | discordant units |")
            L.append("|---|---:|---:|---:|---|---:|")
            for name, s in sec["sgc_contrasts"].items():
                L.append(f"| {s['left']} - {s['right']} | {_f(s['sgc_left'], 4, False)} | {_f(s['sgc_right'], 4, False)} | "
                         f"{_f(s['diff_pp'])} | {_ci(s['scenario']['ci95_pp'])} | {s['n_discordant_units']} |")
            L.append("")
        if key == "F_c_handoff_depth_curves":
            for fam, fo in sec["families"].items():
                L.append(f"### {fam} — {fo['source']}")
                L.append("")
                for rec, ro in fo["receivers"].items():
                    L.append(f"**{rec}** — per depth (goal_pass):")
                    L.append("")
                    L.append("| m | n | handoff | handoff_false | exec never acted | all | handoff-only [scen CI] | silenced |")
                    L.append("|---|---:|---:|---:|---:|---:|---|---:|")
                    for mk, d in ro["depths"].items():
                        g = d["goal_pass"]
                        L.append(f"| {mk} | {d['n']} | {d['n_handoff_occurred_true']} | {d['n_handoff_occurred_false']} | "
                                 f"{d['n_executor_never_acted']} | {_f(g['all']['point'], 4, False)} | "
                                 f"{_f(g['handoff_only']['point'], 4, False)} {_ci(g['handoff_only'].get('ci95_scenario'), 4)} | "
                                 f"{_f(g['silenced']['point'], 4, False)} |")
                    L.append("")
                    L.append("| decomposition | total pp [scen CI] | handoff contribution pp [scen CI] | share from handoff % [scen CI] | gain on handoff subset pp [scen CI] |")
                    L.append("|---|---|---|---|---|")
                    for dn, d in ro["decompositions_goal_pass"].items():
                        sh = d["share_of_rise_from_handoff"]
                        L.append(
                            f"| {dn} (H={d['handoff_count']}, S={d['silenced_count']}) | {_f(100*d['delta_total']['point'])} "
                            f"{_ci([100*x for x in d['delta_total']['ci95_scenario']])} | "
                            f"{_f(100*d['contribution_handoff']['point'])} {_ci([100*x for x in d['contribution_handoff']['ci95_scenario']])} | "
                            f"{_f(None if sh['point_raw'] is None else 100*sh['point_raw'], 1)} "
                            f"{_ci(None if not sh.get('ci95_scenario') else [100*x for x in sh['ci95_scenario']], 1)} "
                            f"(non-positive-rise resamples {sh.get('n_resamples_rise_not_positive_scenario')}) | "
                            f"{_f(100*d['gain_on_handoff_subset']['point'])} {_ci([100*x for x in d['gain_on_handoff_subset']['ci95_scenario']])} |")
                    L.append("")
                if fo.get("receiver_gap_goal_pass"):
                    L.append("Receiver gap (tailored - untailored) on the target depth's handoff episodes:")
                    L.append("")
                    L.append("| depths | n | gap at base pp [scen CI] | gap at target pp [scen CI] | change pp [scen CI] |")
                    L.append("|---|---:|---|---|---|")
                    for gn, g in fo["receiver_gap_goal_pass"].items():
                        h = g["handoff_at_target"]
                        L.append(f"| {gn} | {h['n']} | {_f(100*h['gap_at_base']['point'])} {_ci([100*x for x in h['gap_at_base']['ci95_scenario']])} | "
                                 f"{_f(100*h['gap_at_target']['point'])} {_ci([100*x for x in h['gap_at_target']['ci95_scenario']])} | "
                                 f"{_f(100*h['did_gap_change']['point'])} {_ci([100*x for x in h['did_gap_change']['ci95_scenario']])} |")
                    L.append("")
            L.append("Silenced-count resolution (cap-25 source):")
            L.append("")
            L.append("| arm | handoff_occurred false | executor never acted | handoff false but executor acted |")
            L.append("|---|---:|---:|---:|")
            for name, r in sec["silenced_count_resolution"].items():
                L.append(f"| {name} | {r['handoff_occurred_false']} | {r['executor_never_acted']} | {r['handoff_false_but_executor_acted']} |")
            L.append("")
        if key == "F_d_hinge_vs_linear":
            L.append("| fit | cluster | linear slope pp/step [CI] | tau | dSSE (pp^2) [CI] | null p | BIC share | AIC share | tau counts | tau CI | localized |")
            L.append("|---|---|---|---:|---|---:|---:|---:|---|---|---|")
            for tag, blk in sec["fits"].items():
                for unit in ("scenario", "task"):
                    b = blk[unit]
                    L.append(f"| {blk['description']} | {unit} | {_f(b['linear_slope_pp_per_step'], 3)} "
                             f"{_ci(b['linear_slope_pp_per_step_ci95'], 3)} | {b['tau']} | {_f(b['delta_sse_pp2'], 2, False)} "
                             f"{_ci(b['delta_sse_pp2_ci95'])} | {_f(b['null_linear']['p_value'], 4, False)} | "
                             f"{_f(b['share_hinge_preferred_bic'], 3, False)} | {_f(b['share_hinge_preferred_aic'], 3, False)} | "
                             f"{b['tau_counts']} | {b['tau_ci95']} | {b['breakpoint_localized']} |")
            L.append("")
        if key == "F_e_ni_both_ceilings":
            L.append("goal_pass, arm - ceiling, scenario CI (seed 20260924); NI holds iff lower >= -7.00:")
            L.append("")
            L.append("| arm | vs cap-25 pp [CI] | NI | vs cap-81 pp [CI] | NI | vs cap-25 limit-excl. | NI | vs cap-81 limit-excl. | NI |")
            L.append("|---|---|---|---|---|---|---|---|---|")
            for arm, t in sec["ni_table"].items():
                s25 = sec["limit_excluded_sensitivity"]["cap25"]["arms"][arm]["goal_pass_rate"]
                s81 = sec["limit_excluded_sensitivity"]["cap81"]["arms"][arm]["goal_pass_rate"]
                a25, a81 = t["cap25_goal_pass_rate"], t["cap81_goal_pass_rate"]
                L.append(f"| {arm} | {_f(a25['diff_pp'])} {_ci(a25['scenario']['ci95_pp'])} | {a25['ni_holds_scenario']} | "
                         f"{_f(a81['diff_pp'])} {_ci(a81['scenario']['ci95_pp'])} | {a81['ni_holds_scenario']} | "
                         f"{_f(s25['diff_pp'])} {_ci(s25['scenario']['ci95_pp'])} | {s25['ni_holds_scenario']} | "
                         f"{_f(s81['diff_pp'])} {_ci(s81['scenario']['ci95_pp'])} | {s81['ni_holds_scenario']} |")
            L.append("")
            L.append("TGC, arm - ceiling, scenario CI:")
            L.append("")
            L.append("| arm | vs cap-25 pp [CI] | NI | vs cap-81 pp [CI] | NI |")
            L.append("|---|---|---|---|---|")
            for arm, t in sec["ni_table"].items():
                a25, a81 = t["cap25_tgc"], t["cap81_tgc"]
                L.append(f"| {arm} | {_f(a25['diff_pp'])} {_ci(a25['scenario']['ci95_pp'])} | {a25['ni_holds_scenario']} | "
                         f"{_f(a81['diff_pp'])} {_ci(a81['scenario']['ci95_pp'])} | {a81['ni_holds_scenario']} |")
            L.append("")
            for tag, sel in sec["selection_induced_by_limit_exclusion"].items():
                L.append(f"Selection induced by dropping the {sel['n_dropped']} `limit` episodes of {sel['reference']}:")
                L.append("")
                L.append("| arm | goal_pass kept | goal_pass dropped | kept - dropped pp [scen CI] | arm - ref on kept | arm - ref on dropped |")
                L.append("|---|---:|---:|---|---:|---:|")
                for arm, e in sel["per_arm"].items():
                    L.append(f"| {arm} | {_f(e['goal_pass_kept'], 4, False)} | {_f(e['goal_pass_dropped'], 4, False)} | "
                             f"{_f(e['kept_minus_dropped_pp'])} {_ci(e['kept_minus_dropped_ci95_pp_scenario'])} | "
                             f"{_f(e.get('arm_minus_ref_kept_pp'))} | {_f(e.get('arm_minus_ref_dropped_pp'))} |")
                L.append("")
        if key == "F_f_cost_differences":
            L.append("| pair | axis | left | right | diff [scen CI] | ratio [scen CI] |")
            L.append("|---|---|---:|---:|---|---|")
            for name, blk in sec["pairs"].items():
                for axis in (*COST_AXES, "executor_tokens_per_episode"):
                    c = blk[axis]
                    nd = 6 if axis == "usd_per_episode" else 2
                    L.append(f"| {name} | {axis} | {_f(c['mean_left'], nd, False)} | {_f(c['mean_right'], nd, False)} | "
                             f"{_f(c['diff'], nd)} {_ci(c['scenario']['diff_ci95'], nd)} | "
                             f"{_f(c['ratio_left_over_right'], 3, False)} {_ci(c['scenario']['ratio_ci95'], 3)} |")
            L.append("")
            g = sec["gpu_seconds"]
            L.append(f"GPU-seconds derivable: **{g['derivable']}**. Fields inspected: " + "; ".join(g["fields_inspected"]) + ".")
            L.append("")
        if key == "F_g_near_matched_advice":
            L.append("| comparator | field | advise_k3 | prefix_m6 | diff pp [scen CI] | task CI |")
            L.append("|---|---|---:|---:|---|---|")
            for lab, q in sec["quality_contrasts_advise_k3_minus_prefix_m6"].items():
                for field in ("goal_pass_rate", "tgc"):
                    c = q[field]
                    L.append(f"| {lab} | {field} | {_f(c['mean_left'], 4, False)} | {_f(c['mean_right'], 4, False)} | "
                             f"{_f(c['diff_pp'])} {_ci(c['scenario']['ci95_pp'])} | {_ci(c['task']['ci95_pp'])} |")
            L.append("")
            for lab, axes in sec["cost_contrasts_advise_k3_minus_prefix_m6"].items():
                for axis, c in axes.items():
                    L.append(f"- {lab} {axis}: ratio advise_k3/prefix_m6 = {_f(c['ratio_left_over_right'], 4, False)} "
                             f"{_ci(c['scenario']['ratio_ci95'], 4)}; diff {_f(c['diff'], 6 if 'usd' in axis else 1)}")
            L.append("")
            ev = sec["starved_context_evidence"]
            L.append(f"Starved context: config declares correct_context = {ev['config_declares_correct_context']}; "
                     f"campaign created {ev['campaign_first_created_at']} .. {ev['campaign_last_created_at']}, "
                     f"before commit {ev['correct_context_commit']} ({ev['correct_context_commit_time_utc']}) = "
                     f"{ev['campaign_predates_commit']}; full-context advice campaigns on disk: {ev['fullctx_campaigns_on_disk']}.")
            L.append("")
    return "\n".join(L) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    p.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--sections", default=",".join(SECTIONS))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    for out in (args.out_json, args.out_md):
        refuse_heldout(out)
        if str(Path(out).resolve()).startswith(str(RESULTS_DIR)):
            raise SystemExit(f"refusing to write under {RESULTS_DIR}")
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    unknown = [s for s in sections if s not in SECTIONS]
    if unknown:
        raise SystemExit(f"unknown sections {unknown}; valid {sorted(SECTIONS)}")
    store = ArmStore()
    report = build_report(store, sections, args.n_boot)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"[j16] wrote {args.out_json} and {args.out_md}")
    bad = [SECTIONS[s][0] for s in sections if report[SECTIONS[s][0]].get("status") != "computed"]
    if bad:
        print(f"[j16] sections not computed: {bad}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
