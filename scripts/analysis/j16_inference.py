#!/usr/bin/env python3
"""J16: small-cluster inference beside the percentile bootstrap, plus POOL-04 probes.

What this does
--------------
1. For the headline set (CHAN-C1-02, CHAN-PRICE-01 P1-P3, POOL-01, POOL-02, DID-01, and
   COST-03 as a supplement) it rebuilds the per-episode paired differences through the
   SAME loaders and the SAME code path that produced each published number, and first
   reproduces the published point estimate and percentile interval exactly. Only if every
   reproduction passes does it add:
     * the cluster sign-flip randomization p-value (scenario: exact enumeration of all
       2**19 patterns; task: Monte Carlo), and
     * wild cluster bootstrap percentile intervals (Rademacher and Webb weights),
   on both the scenario (primary) and the task (secondary) clustering. For
   non-inferiority rows it also runs the one-sided sign-flip test at the 7.00 pp null.
2. POOL-04 seed-stability probes for two bounds the ledger reports within 1 pp of their
   thresholds and that are computed by ``j8_frontier`` (not ``j14_did``):
     (a) CHAN-PRICE-01 P3, task-clustered upper bound (+0.01 pp);
     (b) COST-03, ``prefix_m11 - ceiling_cap81`` TGC scenario lower bound (-6.14 vs -7.00).
   Each is re-run through ``j8_frontier.paired_contrast`` itself at the registered seed and
   the seven POOL-04 seeds; an RNG-identical re-implementation supplies 4-decimal bounds
   (asserted to round to the code path's 2-decimal value at every seed) and a 200,000
   resample run.

Nothing here is registered; every output is labelled exploratory. Dev split only: any path
containing ``test_normal`` / ``test_challenge`` is refused. Results under
/scratch/.../results are read, never written.
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
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_thread_env, "1")

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scripts.setup.hj1_gate as hj1  # noqa: E402
from scripts.analysis import j14_did  # noqa: E402
from scripts.analysis.cluster_inference import (  # noqa: E402
    signflip_details,
    wild_cluster_bootstrap_ci,
)

Key = tuple[str, int]

RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")
HELDOUT_MARKERS = ("test_normal", "test_challenge")
RESULTS_DIR = REPO / "campaign" / "results"

SEED = 20260924
N_BOOT = 10_000
N_PERM_SCENARIO = 1 << 19  # >= 2**19, so the 19-cluster scenario test is enumerated exactly
N_PERM_TASK = 100_000
PROBE_SEEDS = (20260924, 1, 2, 3, 7, 101, 999)
PROBE_BIG_B = 200_000
NI_MARGIN = 0.07
ALPHA_TWO_SIDED = 0.05
ALPHA_NI_ONE_SIDED = 0.025

# Arm roots for the j8_frontier-sourced reports. The reports do not record their roots, so
# each is identified by its arm means and verified against the report at run time
# (reproduce_j8_arm below refuses on any mismatch).
J8_ARM_ROOTS = {
    "hj13_advise_fixed_k_1_fullctx_20260923": RESULTS_ROOT / "hj13_advise_fixed_k_1_fullctx_20260923",
    "hj8_sft_plan_bplus_20260921iaware": RESULTS_ROOT / "hj8_sft_plan_bplus_20260921iaware",
    "hj12_advise_fixed_k_10_fullctx_20260923": RESULTS_ROOT / "hj12_advise_fixed_k_10_fullctx_20260923",
    "hj12_prefix_m9_20260923": RESULTS_ROOT / "hj12_prefix_m9_20260923",
    "hj12_prefix_m11_20260923": RESULTS_ROOT / "hj12_prefix_m11_20260923",
    "hj12_takeover_fixed_k_10_20260923": RESULTS_ROOT / "hj12_takeover_fixed_k_10_20260923",
    "hj13_planner_alone_cap81_20260923": RESULTS_ROOT / "hj13_planner_alone_cap81_20260923",
}

ADVICE_REPORT = "campaign/results/hj13_advice_at_price_20260923.report.json"
C1_REPORT = "campaign/results/hj13_c1_matched_trigger_20260923.report.json"
COST_NI_REPORT = "campaign/results/hj13_cost_axes_ni_20260923.report.json"
POOLED_REPORT = "campaign/results/j15_pooled_cap81_3seed_20260924.report.json"
DID_REPORT = "campaign/results/j14_did_narration_receiver_20260924.report.json"

# report label -> campaign directory name, per j8-sourced report
J8_REPORT_ARMS = {
    ADVICE_REPORT: {
        "advise_k1_fullctx": "hj13_advise_fixed_k_1_fullctx_20260923",
        "plan_floor": "hj8_sft_plan_bplus_20260921iaware",
        "advise_k10_fullctx": "hj12_advise_fixed_k_10_fullctx_20260923",
        "prefix_m9": "hj12_prefix_m9_20260923",
        "prefix_m11": "hj12_prefix_m11_20260923",
    },
    C1_REPORT: {
        "advise_fullctx_k10": "hj12_advise_fixed_k_10_fullctx_20260923",
        "takeover_k10": "hj12_takeover_fixed_k_10_20260923",
    },
    COST_NI_REPORT: {
        "prefix_m11": "hj12_prefix_m11_20260923",
        "ceiling_cap81": "hj13_planner_alone_cap81_20260923",
    },
}

FIELD_LABEL = {"goal_pass_rate": "goal_pass", "tgc": "TGC"}


# --------------------------------------------------------------------------- helpers


def refuse_heldout(path: Path | str) -> None:
    s = str(path)
    for marker in HELDOUT_MARKERS:
        if marker in s:
            raise SystemExit(f"refusing path {s}: contains {marker!r} (dev split only)")


def validate_output_path(path: Path) -> None:
    refuse_heldout(path)
    p = Path(path).resolve()
    try:
        p.relative_to(RESULTS_ROOT.resolve())
    except ValueError:
        return
    raise SystemExit(f"refusing to write under {RESULTS_ROOT}: {path}")


def load_json(rel: str) -> dict[str, Any]:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def dig(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        cur = cur[part]
    return cur


def pp4(x: float) -> float:
    return round(100.0 * x, 4)


def cluster_labels(keys: Iterable[Key], unit: str) -> list[str]:
    if unit == "scenario":
        return [hj1.scenario_of(k[0]) for k in keys]
    if unit == "task":
        return [k[0] for k in keys]
    raise ValueError(f"unknown clustering {unit!r}")


def parse_definition(defn: str) -> tuple[str, str]:
    """'A - B' -> (A, B), as written by j14_did.compute_contrast."""
    parts = [p.strip() for p in defn.split(" - ")]
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"cannot parse contrast definition {defn!r}")
    return parts[0], parts[1]


def negate_ci(ci: list[float]) -> list[float]:
    return [-ci[1], -ci[0]]


# ---------------------------------------------------------------- episode differences


def j14_contrast_diffs(
    arms: dict[str, dict[Key, dict[str, Any]]], a: str, b: str, field: str
) -> dict[Key, float]:
    """Per-episode a - b, exactly as j14_did.compute_contrast forms it."""
    shared = sorted(set(arms[a]) & set(arms[b]))
    ev = j14_did.episode_value
    return {k: ev(arms[a][k], field) - ev(arms[b][k], field) for k in shared}


def j14_did_diffs(
    arms: dict[str, dict[Key, dict[str, Any]]],
    a_pos: str,
    a_neg: str,
    b_pos: str,
    b_neg: str,
    field: str,
) -> dict[Key, float]:
    """Per-episode (a_pos - a_neg) - (b_pos - b_neg), exactly as j14_did.compute_did."""
    labels = [a_pos, a_neg, b_pos, b_neg]
    shared = sorted(set.intersection(*(set(arms[x]) for x in labels)))
    ev = j14_did.episode_value
    out: dict[Key, float] = {}
    for k in shared:
        ga = ev(arms[a_pos][k], field) - ev(arms[a_neg][k], field)
        gb = ev(arms[b_pos][k], field) - ev(arms[b_neg][k], field)
        out[k] = ga - gb
    return out


def j8_diffs(
    j8: Any, arm_a: dict[str, Any], arm_b: dict[str, Any], field: str
) -> dict[Key, float]:
    """Per-episode a - b on the all-episodes population, as j8_frontier.paired_contrast.

    Crash -> 0 via j8.coerce_crash_quality; a pair with a missing value on either side is
    dropped, as paired_diff / paired_diff_scenario / contrast_goal_pass_rate all do.
    """
    left = j8.coerce_crash_quality(arm_a["cleaned"], field)
    right = j8.coerce_crash_quality(arm_b["cleaned"], field)
    out: dict[Key, float] = {}
    for k in sorted(set(left) & set(right)):
        lv, rv = left[k].get(field), right[k].get(field)
        if lv is None or rv is None:
            continue
        out[k] = float(lv) - float(rv)
    return out


# ------------------------------------------- RNG-identical percentile replications


def replicate_task_bounds(diffs: dict[Key, float], seed: int, n_boot: int) -> tuple[float, float]:
    """hj1_gate.paired_diff(resample='task') without the 2-decimal rounding.

    Same key order, same cluster grouping, same RNG calls in the same order
    (scripts/setup/hj1_gate.py _draw_task_clusters / paired_diff), same index rule.
    """
    keys = sorted(diffs)
    by_task: dict[str, list[float]] = {}
    for k in keys:
        by_task.setdefault(k[0], []).append(diffs[k])
    tasks = sorted(by_task)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [
            value
            for task in (tasks[rng.randrange(len(tasks))] for _ in range(len(tasks)))
            for value in by_task[task]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def replicate_scenario_bounds(
    diffs: dict[Key, float], seed: int, n_boot: int
) -> tuple[float, float]:
    """j8_frontier.paired_diff_scenario without the 2-decimal rounding (same RNG path)."""
    keys = sorted(diffs)
    by_scenario: dict[str, list[float]] = {}
    for k in keys:
        by_scenario.setdefault(hj1.scenario_of(k[0]), []).append(diffs[k])
    scenarios = sorted(by_scenario)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [
            value
            for scenario in (
                scenarios[rng.randrange(len(scenarios))] for _ in range(len(scenarios))
            )
            for value in by_scenario[scenario]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    return means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


# ------------------------------------------------------------ alternative inference


def alternative_inference(
    diffs: dict[Key, float],
    *,
    seed: int = SEED,
    n_boot: int = N_BOOT,
    n_perm_scenario: int = N_PERM_SCENARIO,
    n_perm_task: int = N_PERM_TASK,
    ni: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Sign-flip p and wild cluster CIs on both clusterings for one diff series.

    ni: {"bound": "upper"|"lower", "margin": 0.07}. 'upper' means H0: mean >= +margin
    (ceiling-minus-arm rows, POOL-02); 'lower' means H0: mean <= -margin (arm-minus-
    ceiling rows, COST-03). The one-sided test is the sign-flip test applied to the
    shifted series, so it assumes cluster sums are symmetric about the null value.
    """
    keys = sorted(diffs)
    vals = [diffs[k] for k in keys]
    out: dict[str, Any] = {
        "n_pairs": len(vals),
        "point_pp": pp4(statistics.fmean(vals)),
    }
    for unit, n_perm in (("scenario", n_perm_scenario), ("task", n_perm_task)):
        labels = cluster_labels(keys, unit)
        sf = signflip_details(vals, labels, n_perm=n_perm, seed=seed)
        block: dict[str, Any] = {
            "n_clusters": sf["n_clusters"],
            "signflip_p_two_sided": sf["p"],
            "signflip_method": sf["method"],
            "signflip_n_patterns": sf["n_patterns"],
            "signflip_mc_se": (
                0.0
                if sf["method"] == "exact"
                else round(math.sqrt(sf["p"] * (1.0 - sf["p"]) / sf["n_patterns"]), 6)
            ),
            "signflip_rejects_zero_at_05": sf["p"] < ALPHA_TWO_SIDED,
        }
        for weights in ("rademacher", "webb"):
            lo, hi = wild_cluster_bootstrap_ci(
                vals, labels, n_boot=n_boot, seed=seed, weights=weights
            )
            block[f"wild_{weights}_ci95_pp"] = [pp4(lo), pp4(hi)]
            block[f"wild_{weights}_excludes_zero"] = bool(lo > 0.0 or hi < 0.0)
        if ni:
            margin = float(ni.get("margin", NI_MARGIN))
            if ni["bound"] == "upper":
                shifted = [v - margin for v in vals]
                alternative = "less"
            else:
                shifted = [v + margin for v in vals]
                alternative = "greater"
            sfn = signflip_details(
                shifted, labels, n_perm=n_perm, seed=seed, alternative=alternative
            )
            block["ni_null"] = (
                f"mean >= +{margin * 100:.2f} pp" if ni["bound"] == "upper"
                else f"mean <= -{margin * 100:.2f} pp"
            )
            block["ni_signflip_p_one_sided"] = sfn["p"]
            block["ni_signflip_method"] = sfn["method"]
            block["ni_holds_signflip"] = sfn["p"] < ALPHA_NI_ONE_SIDED
            for weights in ("rademacher", "webb"):
                lo_pp, hi_pp = block[f"wild_{weights}_ci95_pp"]
                block[f"ni_holds_wild_{weights}"] = ni_rule(ni["bound"], lo_pp, hi_pp, margin)
        out[unit] = block
    return out


def ni_rule(bound: str, lo_pp: float, hi_pp: float, margin: float = NI_MARGIN) -> bool:
    """The rules the source reports used: POOL-02 upper < +7.00 (j15 note);
    COST-03 lower >= -7.00 (j12_cost_axes.compute_noninferiority_across_axes)."""
    # 0.07 * 100.0 is 7.000000000000001 in floats; round so a bound of exactly 7.00
    # is judged against 7.00, not against a margin one ulp wider.
    m = round(margin * 100.0, 10)
    if bound == "upper":
        return bool(hi_pp < m)
    return bool(lo_pp >= -m)


def excludes_zero(ci: list[float]) -> bool:
    return bool(ci[0] > 0.0 or ci[1] < 0.0)


# ------------------------------------------------------------------- j8 plumbing


_J8_MODULE: Any = None


def load_j8() -> Any:
    global _J8_MODULE
    if _J8_MODULE is None:
        spec = importlib.util.spec_from_file_location(
            "j8_frontier", Path(__file__).resolve().parent / "j8_frontier.py"
        )
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        _J8_MODULE = module
    return _J8_MODULE


def load_j8_arm(j8: Any, label: str, campaign: str, seeds: list[int]) -> dict[str, Any]:
    root = J8_ARM_ROOTS[campaign]
    refuse_heldout(root)
    loaded = j8.j10.load_arm_tree(root)
    arm = j8.summarise_arm(label, loaded, seeds, root=root)
    arm["root"] = root
    return arm


class SeedOverride:
    """Temporarily re-seed j8_frontier (both its SEED and hj1_gate.SEED); always restore."""

    def __init__(self, j8: Any, seed: int):
        self.j8 = j8
        self.seed = seed

    def __enter__(self) -> None:
        self._saved = (self.j8.SEED, hj1.SEED)
        self.j8.set_bootstrap_seed(self.seed)

    def __exit__(self, *exc: Any) -> None:
        self.j8.SEED, hj1.SEED = self._saved


# --------------------------------------------------------------- headline rows


def headline_specs() -> list[dict[str, Any]]:
    """Every row: ledger id, source report + key, how to rebuild its diffs."""
    rows: list[dict[str, Any]] = []
    # CHAN-C1-02: presented as takeover - advise; the JSON key is advise - takeover.
    for field, prefix in (("goal_pass_rate", "goal_pass_all"), ("tgc", "tgc_all")):
        rows.append({
            "row": f"CHAN-C1-02.{FIELD_LABEL[field]}",
            "ledger_id": "CHAN-C1-02",
            "role": "headline" if field == "goal_pass_rate" else "supporting",
            "source": "j8",
            "report": C1_REPORT,
            "report_key": f"contrasts.{prefix}_advise_fullctx_k10_minus_takeover_k10",
            "report_left": "advise_fullctx_k10",
            "report_right": "takeover_k10",
            "presented_sign": -1,
            "presented": "takeover_k10 - advise_fullctx_k10",
            "field": field,
            "test": "zero",
        })
    for pred, other in (("P1", "plan_floor"), ("P2", "prefix_m11"), ("P3", "advise_k10_fullctx")):
        for field, prefix in (("goal_pass_rate", "goal_pass_all"), ("tgc", "tgc_all")):
            rows.append({
                "row": f"CHAN-PRICE-01.{pred}.{FIELD_LABEL[field]}",
                "ledger_id": "CHAN-PRICE-01",
                "role": "headline" if field == "goal_pass_rate" else "supporting",
                "source": "j8",
                "report": ADVICE_REPORT,
                "report_key": f"contrasts.{prefix}_advise_k1_fullctx_minus_{other}",
                "report_left": "advise_k1_fullctx",
                "report_right": other,
                "presented_sign": 1,
                "presented": f"advise_k1_fullctx - {other}",
                "field": field,
                "test": "zero",
            })
    for name, role in (
        ("zs_depth_m6_m11", "headline"),
        ("t_depth_m6_m11", "headline"),
        ("t_depth_m9_m11", "supplementary (POOL-04 boundary case)"),
        ("zs_depth_m9_m11", "supplementary"),
    ):
        for field in ("goal_pass_rate", "tgc"):
            rows.append({
                "row": f"POOL-01.{name}.{FIELD_LABEL[field]}",
                "ledger_id": "POOL-01",
                "role": role if field == "goal_pass_rate" else "supporting",
                "source": "j14_contrast",
                "report": POOLED_REPORT,
                "report_key": f"contrasts.{name}.{field}",
                "field": field,
                "test": "zero",
            })
    for name in ("ni_ceiling_minus_t_m11", "ni_ceiling_minus_zs_m11",
                 "ni_ceiling_minus_t_m9", "ni_ceiling_minus_zs_m9"):
        for field in ("goal_pass_rate", "tgc"):
            rows.append({
                "row": f"POOL-02.{name}.{FIELD_LABEL[field]}",
                "ledger_id": "POOL-02",
                "role": "headline (NI)",
                "source": "j14_contrast",
                "report": POOLED_REPORT,
                "report_key": f"contrasts.{name}.{field}",
                "field": field,
                "test": "ni",
                "ni": {"bound": "upper", "margin": NI_MARGIN},
            })
    for depth, role in (("m11", "headline"), ("m6", "supplementary"), ("m9", "supplementary")):
        for field in ("goal_pass_rate", "tgc"):
            rows.append({
                "row": f"DID-01.{depth}.{FIELD_LABEL[field]}",
                "ledger_id": "DID-01",
                "role": role,
                "source": "j14_did",
                "report": DID_REPORT,
                "report_key": f"dids.{depth}.{field}",
                "field": field,
                "test": "zero",
            })
    rows.append({
        "row": "COST-03.prefix_m11.TGC",
        "ledger_id": "COST-03",
        "role": "supplementary (NI; probe b)",
        "source": "j8",
        "report": COST_NI_REPORT,
        "report_key": "non_inferiority.comparisons.prefix_m11.quality_tgc_contrast",
        "report_left": "prefix_m11",
        "report_right": "ceiling_cap81",
        "presented_sign": 1,
        "presented": "prefix_m11 - ceiling_cap81",
        "field": "tgc",
        "test": "ni",
        "ni": {"bound": "lower", "margin": NI_MARGIN},
    })
    return rows


class Loader:
    """Caches arms so each campaign tree is read once."""

    def __init__(self) -> None:
        self._j8_arms: dict[tuple[str, str], dict[str, Any]] = {}
        self._j14_arms: dict[tuple[str, ...], dict[Key, dict[str, Any]]] = {}
        self.j8: Any = None
        self.arm_checks: list[dict[str, Any]] = []

    def j8_arm(self, report: str, label: str) -> dict[str, Any]:
        if self.j8 is None:
            self.j8 = load_j8()
        key = (report, label)
        if key not in self._j8_arms:
            rep = load_json(report)
            seeds = [int(s) for s in rep.get("seeds") or rep.get("seeds_filter") or [1, 2]]
            campaign = J8_REPORT_ARMS[report][label]
            arm = load_j8_arm(self.j8, label, campaign, seeds)
            check = {
                "report": report,
                "label": label,
                "campaign": campaign,
                "root": str(J8_ARM_ROOTS[campaign]),
                "n": arm["n"],
                "goal_pass_all": arm["goal_pass_all"],
                "tgc_all": arm["tgc_all"],
            }
            published = (rep.get("arms") or {}).get(label) or {}
            ok = True
            for fld in ("goal_pass_all", "tgc_all"):
                if fld in published:
                    same = round(float(arm[fld]), 6) == round(float(published[fld]), 6)
                    check[f"{fld}_published"] = published[fld]
                    ok = ok and same
            n_pub = published.get("n", published.get("n_episodes"))
            if n_pub is not None:
                check["n_published"] = n_pub
                ok = ok and int(n_pub) == int(arm["n"])
            if "error_types" in published:
                ok = ok and published["error_types"] == arm["error_types"]
                check["error_types_match"] = published["error_types"] == arm["error_types"]
            check["ok"] = ok
            self.arm_checks.append(check)
            self._j8_arms[key] = arm
        return self._j8_arms[key]

    def j14_arm(self, roots: list[str]) -> dict[Key, dict[str, Any]]:
        key = tuple(roots)
        if key not in self._j14_arms:
            for r in roots:
                refuse_heldout(r)
            self._j14_arms[key] = j14_did.load_pooled_arm([Path(r) for r in roots])
        return self._j14_arms[key]

    def j14_arms_for(self, report: dict[str, Any], labels: list[str]) -> dict[str, Any]:
        sources = report["arm_sources"]
        out = {}
        for label in labels:
            src = sources[label]
            roots = src if isinstance(src, list) else [src]
            out[label] = self.j14_arm(roots)
        return out


def reproduce_row(spec: dict[str, Any], loader: Loader) -> tuple[dict[str, Any], dict[Key, float]]:
    """Rebuild one row's diffs and reproduce its published numbers. Returns (check, diffs).

    diffs are in the PRESENTED orientation.
    """
    rep = load_json(spec["report"])
    published = dig(rep, spec["report_key"])
    check: dict[str, Any] = {"row": spec["row"], "report": spec["report"],
                             "report_key": spec["report_key"]}
    field = spec["field"]
    if spec["source"] == "j8":
        j8 = loader.j8 or load_j8()
        loader.j8 = j8
        arm_a = loader.j8_arm(spec["report"], spec["report_left"])
        arm_b = loader.j8_arm(spec["report"], spec["report_right"])
        cluster = rep.get("cluster", "task")
        # The registered code path at the registered seed (hj1_gate.SEED, untouched here).
        recomputed = j8.paired_contrast(arm_a, arm_b, field, "all", cluster=cluster)
        diffs = j8_diffs(j8, arm_a, arm_b, field)
        point_pp = pp4(statistics.fmean(diffs.values()))
        check.update({
            "code_path": "j8_frontier.paired_contrast (seed hj1_gate.SEED = %d)" % hj1.SEED,
            "published": {
                "diff_pp": published["diff_pp"],
                "ci95_pp_scenario": published.get("ci95_pp_scenario", published["ci95_pp"]),
                "ci95_pp_task": published.get("ci95_pp_task"),
                "n_pairs": published["n_pairs"],
            },
            "recomputed": {
                "diff_pp": recomputed["diff_pp"],
                "ci95_pp_scenario": recomputed.get("ci95_pp_scenario"),
                "ci95_pp_task": recomputed.get("ci95_pp_task"),
                "n_pairs": recomputed["n_pairs"],
            },
            "episode_diff_point_pp_4dp": point_pp,
        })
        ok = (
            recomputed["diff_pp"] == published["diff_pp"]
            and recomputed.get("ci95_pp_scenario") == check["published"]["ci95_pp_scenario"]
            and recomputed.get("ci95_pp_task") == published.get("ci95_pp_task")
            and recomputed["n_pairs"] == published["n_pairs"]
            and round(point_pp, 2) == published["diff_pp"]
            and len(diffs) == published["n_pairs"]
        )
        # 4-decimal check against the 6-decimal arm means where the report carries them.
        mean_key = "goal_pass_all" if field == "goal_pass_rate" else "tgc_all"
        pa = (rep.get("arms") or {}).get(spec["report_left"], {}).get(mean_key)
        pb = (rep.get("arms") or {}).get(spec["report_right"], {}).get(mean_key)
        if pa is not None and pb is not None and len(diffs) == published["n_pairs"]:
            from_means = pp4(float(pa) - float(pb))
            check["point_pp_from_published_arm_means"] = from_means
            # arm means are rounded to 6 dp, so their difference is good to +/-0.0001 pp
            ok = ok and abs(from_means - point_pp) <= 0.00011
        check["percentile_scenario_pp"] = check["published"]["ci95_pp_scenario"]
        check["percentile_task_pp"] = published.get("ci95_pp_task")
        check["point_pp_published_2dp"] = published["diff_pp"]
        sign = spec.get("presented_sign", 1)
        if sign == -1:
            diffs = {k: -v for k, v in diffs.items()}
            check["presented_negated"] = True
        check["ok"] = bool(ok)
        return check, diffs

    if spec["source"] == "j14_contrast":
        a, b = parse_definition(published["definition"])
        arms = loader.j14_arms_for(rep, [a, b])
        recomputed = j14_did.compute_contrast(
            arms, a, b, field, n_boot=int(rep["bootstrap"]), seed=int(rep["seed"])
        )
        diffs = j14_contrast_diffs(arms, a, b, field)
    elif spec["source"] == "j14_did":
        arm_names = published["arms"]
        labels = [arm_names[x] for x in ("a_pos", "a_neg", "b_pos", "b_neg")]
        arms = loader.j14_arms_for(rep, labels)
        recomputed = j14_did.compute_did(
            arms, *labels, field, n_boot=int(rep["bootstrap"]), seed=int(rep["seed"])
        )
        diffs = j14_did_diffs(arms, *labels, field)
    else:
        raise ValueError(spec["source"])
    point_pp = pp4(statistics.fmean(diffs.values()))
    check.update({
        "code_path": "j14_did (seed %d, B=%d)" % (int(rep["seed"]), int(rep["bootstrap"])),
        "published": {
            "point_pp": published["scenario"]["point_pp"],
            "ci95_pp_scenario": published["scenario"]["ci95_pp"],
            "ci95_pp_task": published["task"]["ci95_pp"],
            "n_pairs": published["n_pairs"],
            "arm_means": published.get("arm_means"),
        },
        "recomputed": {
            "point_pp": recomputed["scenario"]["point_pp"],
            "ci95_pp_scenario": recomputed["scenario"]["ci95_pp"],
            "ci95_pp_task": recomputed["task"]["ci95_pp"],
            "n_pairs": recomputed["n_pairs"],
            "arm_means": recomputed.get("arm_means"),
        },
        "episode_diff_point_pp_4dp": point_pp,
    })
    ok = (
        check["published"] == check["recomputed"]
        and point_pp == published["scenario"]["point_pp"]
        and len(diffs) == published["n_pairs"]
    )
    check["percentile_scenario_pp"] = published["scenario"]["ci95_pp"]
    check["percentile_task_pp"] = published["task"]["ci95_pp"]
    check["ok"] = bool(ok)
    return check, diffs


def verdicts(spec: dict[str, Any], check: dict[str, Any], alt: dict[str, Any]) -> dict[str, Any]:
    """Compare the published percentile verdict with each alternative, per clustering."""
    sign = spec.get("presented_sign", 1)
    out: dict[str, Any] = {}
    for unit in ("scenario", "task"):
        pct = check[f"percentile_{unit}_pp"]
        if pct is None:
            continue
        pct = negate_ci(pct) if sign == -1 else list(pct)
        blk = alt[unit]
        if spec["test"] == "zero":
            v = {
                "percentile_ci95_pp": pct,
                "percentile_excludes_zero": excludes_zero(pct),
                "signflip_rejects_zero": blk["signflip_rejects_zero_at_05"],
                "wild_rademacher_excludes_zero": blk["wild_rademacher_excludes_zero"],
                "wild_webb_excludes_zero": blk["wild_webb_excludes_zero"],
            }
            calls = [v["percentile_excludes_zero"], v["signflip_rejects_zero"],
                     v["wild_rademacher_excludes_zero"], v["wild_webb_excludes_zero"]]
        else:
            bound = spec["ni"]["bound"]
            v = {
                "percentile_ci95_pp": pct,
                "percentile_ni_holds": ni_rule(bound, pct[0], pct[1]),
                "signflip_ni_holds": blk["ni_holds_signflip"],
                "wild_rademacher_ni_holds": blk["ni_holds_wild_rademacher"],
                "wild_webb_ni_holds": blk["ni_holds_wild_webb"],
            }
            calls = [v["percentile_ni_holds"], v["signflip_ni_holds"],
                     v["wild_rademacher_ni_holds"], v["wild_webb_ni_holds"]]
        v["all_methods_agree"] = len(set(calls)) == 1
        out[unit] = v
    out["conclusion_changes_on_primary"] = not out["scenario"]["all_methods_agree"]
    out["conclusion_changes_on_task"] = (
        not out["task"]["all_methods_agree"] if "task" in out else None
    )
    return out


def run_headline(args: argparse.Namespace, loader: Loader) -> dict[str, Any]:
    specs = headline_specs()
    checks: list[dict[str, Any]] = []
    rows_diffs: list[tuple[dict[str, Any], dict[str, Any], dict[Key, float]]] = []
    for spec in specs:
        check, diffs = reproduce_row(spec, loader)
        checks.append(check)
        rows_diffs.append((spec, check, diffs))
        print(f"[j16] reproduce {spec['row']}: {'OK' if check['ok'] else 'MISMATCH'}")
    arm_ok = all(c["ok"] for c in loader.arm_checks)
    all_ok = arm_ok and all(c["ok"] for c in checks)
    block: dict[str, Any] = {
        "reproduction": {
            "all_ok": all_ok,
            "arm_checks": loader.arm_checks,
            "rows": checks,
            "rule": (
                "j14_did-sourced rows: point_pp, both 95% CIs, n_pairs and arm means must "
                "equal the published 4-decimal values exactly. j8_frontier-sourced rows: "
                "the published report stores only 2-decimal pp, so the registered code "
                "path is re-run at the registered seed and diff_pp and both CIs must match "
                "exactly, the 4-decimal point from the episode series must round to the "
                "published 2-decimal value, and must equal the difference of the published "
                "6-decimal arm means to within 0.0001 pp."
            ),
        },
    }
    if not all_ok:
        block["refused"] = (
            "at least one published number could not be reproduced; alternative inference "
            "was NOT computed (see reproduction.rows[*].ok and reproduction.arm_checks)"
        )
        return block
    rows_out: list[dict[str, Any]] = []
    for spec, check, diffs in rows_diffs:
        alt = alternative_inference(
            diffs,
            seed=args.seed,
            n_boot=args.n_boot,
            n_perm_scenario=args.n_perm_scenario,
            n_perm_task=args.n_perm_task,
            ni=spec.get("ni"),
        )
        sign = spec.get("presented_sign", 1)
        point_presented = check["episode_diff_point_pp_4dp"] * sign
        row = {
            "row": spec["row"],
            "ledger_id": spec["ledger_id"],
            "role": spec["role"],
            "contrast": spec.get("presented") or dig(
                load_json(spec["report"]), spec["report_key"]
            ).get("definition"),
            "field": spec["field"],
            "report": spec["report"],
            "report_key": spec["report_key"],
            "presented_negation_of_report_key": sign == -1,
            "point_pp": round(point_presented, 4),
            "alternative": alt,
            "verdicts": verdicts(spec, check, alt),
        }
        if spec.get("ni"):
            row["ni"] = spec["ni"]
        rows_out.append(row)
        print(
            f"[j16] {spec['row']}: {row['point_pp']:+.4f} pp  "
            f"p_scen={alt['scenario']['signflip_p_two_sided']:.5f} "
            f"p_task={alt['task']['signflip_p_two_sided']:.5f} "
            f"wildR_scen={alt['scenario']['wild_rademacher_ci95_pp']}"
        )
    # Keyed by row id so a ledger row can cite e.g.
    # headline.rows["CHAN-C1-02.goal_pass"].alternative.scenario.signflip_p_two_sided
    block["rows"] = {r["row"]: r for r in rows_out}
    block["conclusion_changes"] = [
        {"row": r["row"], "role": r["role"],
         "primary": r["verdicts"]["conclusion_changes_on_primary"],
         "task": r["verdicts"]["conclusion_changes_on_task"]}
        for r in rows_out
        if r["verdicts"]["conclusion_changes_on_primary"]
        or r["verdicts"]["conclusion_changes_on_task"]
    ]
    return block


# ---------------------------------------------------------------------- probes


def run_probe(
    *,
    name: str,
    loader: Loader,
    report: str,
    report_key: str,
    left: str,
    right: str,
    field: str,
    unit: str,
    side: str,
    threshold: float,
    passes: Callable[[float], bool],
    threshold_meaning: str,
    seeds: Iterable[int],
    big_b: int,
) -> dict[str, Any]:
    j8 = loader.j8 or load_j8()
    loader.j8 = j8
    arm_a = loader.j8_arm(report, left)
    arm_b = loader.j8_arm(report, right)
    rep = load_json(report)
    cluster = rep.get("cluster", "task")
    diffs = j8_diffs(j8, arm_a, arm_b, field)
    idx = 0 if side == "lower" else 1
    ci_key = "ci95_pp_task" if unit == "task" else "ci95_pp_scenario"
    replicate = replicate_task_bounds if unit == "task" else replicate_scenario_bounds
    registered = hj1.SEED
    published_ci = dig(rep, report_key)[ci_key]
    by_seed: dict[str, Any] = {}
    all_seeds = [registered] + [s for s in seeds if s != registered]
    for s in all_seeds:
        with SeedOverride(j8, s):
            out = j8.paired_contrast(arm_a, arm_b, field, "all", cluster=cluster)
        code_bound = out[ci_key][idx]
        rep_bound = replicate(diffs, s, N_BOOT)[idx] * 100.0
        by_seed[str(s)] = {
            "code_path_bound_pp_2dp": code_bound,
            "replicated_bound_pp_4dp": round(rep_bound, 4),
            "replication_matches_code_path": round(rep_bound, 2) == code_bound,
            "passes": passes(code_bound),
        }
        print(f"[j16] probe {name} seed {s}: {code_bound} (4dp {rep_bound:.4f})")
    # Restored? The context manager must leave the registered seed in place.
    assert hj1.SEED == registered and j8.SEED == registered
    big = replicate(diffs, registered, big_b)[idx] * 100.0
    probe_values = [by_seed[str(s)]["code_path_bound_pp_2dp"] for s in seeds]
    verdicts_seen = {by_seed[str(s)]["passes"] for s in seeds}
    return {
        "source_report": report,
        "report_key": f"{report_key}.{ci_key}",
        "estimand": f"{left} - {right}, {field}, all-episodes, {unit}-clustered percentile "
                    f"bootstrap, {side} bound",
        "code_path": "j8_frontier.paired_contrast(..., cluster=%r) with "
                     "j8_frontier.set_bootstrap_seed(seed)" % cluster,
        "registered_seed": registered,
        "published_bound_pp": published_ci[idx],
        "registered_seed_reproduces_published": by_seed[str(registered)]["code_path_bound_pp_2dp"]
        == published_ci[idx],
        "threshold_pp": threshold,
        "threshold_meaning": threshold_meaning,
        "n_pairs": len(diffs),
        "bootstrap": N_BOOT,
        "seeds_probed": list(seeds),
        "by_seed": by_seed,
        "range_over_probe_seeds_pp": [min(probe_values), max(probe_values)],
        "at_%dk_resamples_registered_seed_pp_4dp" % (big_b // 1000): round(big, 4),
        "all_replications_match_code_path": all(
            v["replication_matches_code_path"] for v in by_seed.values()
        ),
        "verdict_stable_across_probe_seeds": len(verdicts_seen) == 1,
        "passes_at_every_probe_seed": verdicts_seen == {True},
    }


def run_probes(args: argparse.Namespace, loader: Loader) -> dict[str, Any]:
    seeds = [int(s) for s in args.probe_seeds.split(",") if s.strip()]
    a = run_probe(
        name="CHAN-PRICE-01.P3.task_upper",
        loader=loader,
        report=ADVICE_REPORT,
        report_key="contrasts.goal_pass_all_advise_k1_fullctx_minus_advise_k10_fullctx",
        left="advise_k1_fullctx",
        right="advise_k10_fullctx",
        field="goal_pass_rate",
        unit="task",
        side="upper",
        threshold=0.0,
        passes=lambda ub: ub >= 0.0,
        threshold_meaning=(
            "P3 predicts the interval INCLUDES zero; on this bound that means upper >= 0. "
            "An upper bound < 0 would exclude zero, i.e. P3 would fail on the task "
            "clustering (the registered clustering is scenario)."
        ),
        seeds=seeds,
        big_b=args.probe_big_b,
    )
    b = run_probe(
        name="COST-03.prefix_m11.tgc.scenario_lower",
        loader=loader,
        report=COST_NI_REPORT,
        report_key="non_inferiority.comparisons.prefix_m11.quality_tgc_contrast",
        left="prefix_m11",
        right="ceiling_cap81",
        field="tgc",
        unit="scenario",
        side="lower",
        threshold=-7.0,
        passes=lambda lb: lb >= -7.0,
        threshold_meaning=(
            "NI holds if lower bound >= -7.00 pp (j12_cost_axes."
            "compute_noninferiority_across_axes: q_ci[0] >= -NONINFERIORITY_MARGIN_PP)."
        ),
        seeds=seeds,
        big_b=args.probe_big_b,
    )
    return {
        "rule": "POOL-04: seven bootstrap seeds, B = 10,000, same estimand and code path",
        "note_on_registered_seed": (
            "Both bounds come from j8_frontier, whose registered seed is hj1_gate.SEED = "
            "20260915, not the j14_did seed 20260924. The registered seed is run first so "
            "the published value is reproduced, then the seven POOL-04 seeds."
        ),
        "note_on_j12_seed_flag": (
            "j12_cost_axes records --seed/--n-boot in its report but never passes them to "
            "the bootstrap (compute_noninferiority_across_axes accepts seed and n_boot and "
            "does not use them), so COST-03 cannot be re-seeded through j12's own flag; "
            "this probe re-seeds the j8_frontier.paired_contrast call j12 makes."
        ),
        "CHAN-PRICE-01.P3.goal_pass.task_upper_bound": a,
        "COST-03.prefix_m11.tgc.scenario_lower_bound": b,
    }


# ---------------------------------------------------------------------- markdown


def _ci(ci: Optional[list[float]], digits: int = 2) -> str:
    if ci is None:
        return "—"
    return f"[{ci[0]:+.{digits}f}, {ci[1]:+.{digits}f}]"


def _p(p: float) -> str:
    if p < 0.0001:
        return f"{p:.1e}"
    return f"{p:.4f}"


def render_markdown(report: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# J16 — small-cluster inference beside the percentile bootstrap")
    L.append("")
    L.append(f"Exploratory, not registered. Generated by `scripts/analysis/j16_inference.py`; "
             f"JSON: `{report['out_json']}`.")
    L.append("")
    L.append("## Method")
    for line in report["method"]:
        L.append(f"- {line}")
    L.append("")
    head = report.get("headline") or {}
    rep = head.get("reproduction") or {}
    L.append("## Reproduction gate")
    L.append(f"All published point estimates and percentile intervals reproduced: "
             f"**{rep.get('all_ok')}** ({len(rep.get('rows', []))} rows, "
             f"{len(rep.get('arm_checks', []))} j8 arm-root checks). Rule: {rep.get('rule')}")
    L.append("")
    if head.get("refused"):
        L.append(f"**REFUSED:** {head['refused']}")
        for r in rep.get("rows", []):
            if not r["ok"]:
                L.append(f"- {r['row']}: published {r['published']} recomputed {r['recomputed']}")
        return "\n".join(L) + "\n"
    rows = head.get("rows", {})
    if isinstance(rows, dict):
        rows = list(rows.values())
    L.append("## Zero-null contrasts (pp; scenario = 19 clusters primary, task = 57 secondary)")
    L.append("")
    L.append("| row | role | n | point | pct CI scen | wild-R scen | wild-W scen | p sign-flip scen (exact) | pct CI task | wild-R task | p sign-flip task (MC) | any change? |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["verdicts"]["scenario"].get("percentile_excludes_zero") is None:
            continue
        a, v = r["alternative"], r["verdicts"]
        change = []
        if v["conclusion_changes_on_primary"]:
            change.append("scenario")
        if v["conclusion_changes_on_task"]:
            change.append("task")
        L.append(
            f"| {r['row']} | {r['role']} | {a['n_pairs']} | {r['point_pp']:+.2f} | "
            f"{_ci(v['scenario']['percentile_ci95_pp'])} | {_ci(a['scenario']['wild_rademacher_ci95_pp'])} | "
            f"{_ci(a['scenario']['wild_webb_ci95_pp'])} | {_p(a['scenario']['signflip_p_two_sided'])} | "
            f"{_ci(v['task']['percentile_ci95_pp'])} | {_ci(a['task']['wild_rademacher_ci95_pp'])} | "
            f"{_p(a['task']['signflip_p_two_sided'])} | {', '.join(change) or 'no'} |"
        )
    L.append("")
    L.append("## Non-inferiority contrasts (margin 7.00 pp)")
    L.append("")
    L.append("| row | point | pct CI scen | wild-R scen | wild-W scen | NI p sign-flip scen (one-sided) | NI p task | NI verdicts scen (pct / sf / wR / wW) | any change? |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        v = r["verdicts"]["scenario"]
        if "percentile_ni_holds" not in v:
            continue
        a = r["alternative"]
        vt = r["verdicts"]["task"]
        change = []
        if r["verdicts"]["conclusion_changes_on_primary"]:
            change.append("scenario")
        if r["verdicts"]["conclusion_changes_on_task"]:
            change.append("task")
        L.append(
            f"| {r['row']} | {r['point_pp']:+.2f} | {_ci(v['percentile_ci95_pp'])} | "
            f"{_ci(a['scenario']['wild_rademacher_ci95_pp'])} | {_ci(a['scenario']['wild_webb_ci95_pp'])} | "
            f"{_p(a['scenario']['ni_signflip_p_one_sided'])} | {_p(a['task']['ni_signflip_p_one_sided'])} | "
            f"{v['percentile_ni_holds']} / {v['signflip_ni_holds']} / {v['wild_rademacher_ni_holds']} / "
            f"{v['wild_webb_ni_holds']} | {', '.join(change) or 'no'} |"
        )
    L.append("")
    changes = head.get("conclusion_changes") or []
    L.append("## Rows whose conclusion depends on the inference method")
    if not changes:
        L.append("None: on every row every method agrees on both clusterings.")
    for c in changes:
        r = next(x for x in rows if x["row"] == c["row"])
        parts = []
        for unit in ("scenario", "task"):
            v = r["verdicts"].get(unit) or {}
            if v.get("all_methods_agree", True):
                continue
            calls = ", ".join(
                f"{k.replace('_', ' ')}={v[k]}"
                for k in v
                if k not in ("all_methods_agree", "percentile_ci95_pp")
            )
            parts.append(f"{unit}: {calls}")
        L.append(f"- **{c['row']}** ({c['role']}): " + "; ".join(parts))
    L.append("")
    probes = report.get("probes") or {}
    if probes:
        L.append("## POOL-04 seed-stability probes (j8_frontier code path)")
        L.append("")
        for key in ("CHAN-PRICE-01.P3.goal_pass.task_upper_bound",
                    "COST-03.prefix_m11.tgc.scenario_lower_bound"):
            pr = probes.get(key)
            if not pr:
                continue
            L.append(f"### {key}")
            L.append(f"- estimand: {pr['estimand']}; source `{pr['source_report']}` key `{pr['report_key']}`")
            L.append(f"- published {pr['published_bound_pp']:+.2f} pp at registered seed "
                     f"{pr['registered_seed']} (reproduced: {pr['registered_seed_reproduces_published']}); "
                     f"threshold {pr['threshold_pp']:+.2f} — {pr['threshold_meaning']}")
            L.append("")
            L.append("| seed | bound (code path, 2 dp) | bound (RNG-identical replication, 4 dp) | passes |")
            L.append("|---|---|---|---|")
            for s, v in pr["by_seed"].items():
                L.append(f"| {s} | {v['code_path_bound_pp_2dp']:+.2f} | {v['replicated_bound_pp_4dp']:+.4f} | {v['passes']} |")
            big_key = next(k for k in pr if k.startswith("at_") and k.endswith("_pp_4dp"))
            L.append("")
            L.append(f"- range over the seven probe seeds: {_ci(pr['range_over_probe_seeds_pp'])}; "
                     f"{big_key}: {pr[big_key]:+.4f}; verdict stable across probe seeds: "
                     f"**{pr['verdict_stable_across_probe_seeds']}**; passes at every probe seed: "
                     f"**{pr['passes_at_every_probe_seed']}**")
            L.append("")
        for k in ("note_on_registered_seed", "note_on_j12_seed_flag"):
            if probes.get(k):
                L.append(f"- {probes[k]}")
        L.append("")
    L.append("## Caveats")
    for line in report["caveats"]:
        L.append(f"- {line}")
    return "\n".join(L) + "\n"


METHOD = [
    "Per-episode paired differences are rebuilt with the loader and code path that produced "
    "each published number (j8_frontier for CHAN-C1-02 / CHAN-PRICE-01 / COST-03, j14_did for "
    "POOL-01 / POOL-02 / DID-01); each published point and percentile CI is reproduced first.",
    "Cluster sign-flip test: statistic = mean of per-episode differences; all differences in "
    "a cluster share one sign. Scenario clustering (G = 19) is enumerated exactly over all "
    "2^19 = 524,288 patterns; task clustering (G = 57) uses 100,000 random patterns "
    "(seed 20260924) with the +1 correction.",
    "Wild cluster bootstrap: B = 10,000, seed 20260924, cluster sums of (diff - mean) "
    "multiplied by Rademacher or Webb six-point weights; percentile interval of the "
    "resampled mean with the repo index rule.",
    "Non-inferiority rows (POOL-02 ceiling-minus-arm, COST-03 arm-minus-ceiling): one-sided "
    "sign-flip test of H0 at the 7.00 pp margin on the shifted series, alpha 0.025 "
    "(the one-sided level of a 95% two-sided interval).",
    "'Any change?' flags a row where the percentile interval, the sign-flip test and the two "
    "wild intervals do not all give the same verdict on that clustering.",
]

CAVEATS = [
    "The wild intervals are non-studentized with unrestricted residuals, so their variance "
    "is the CR0 cluster variance; they are symmetric about the point by construction and "
    "are a sensitivity reading, not a small-G correction. The sign-flip test is the "
    "component whose size does not depend on G being large (it assumes cluster sums are "
    "symmetric about the null and independent across clusters).",
    "For the NI rows the sign-flip test is applied at a non-zero null; symmetry of the "
    "shifted cluster sums about zero is an assumption, more fragile for bounded, discrete "
    "metrics such as TGC than at the zero null.",
    "POOL-01/POOL-02 pool three planner seeds (171 pairs) but still cluster on 19 "
    "scenarios; episodes of one task across seeds are correlated and share a cluster.",
    "Several rows (DID-01 m6/m9, POOL-01 m9->m11, CHAN-PRICE-01 TGC) are supplementary and "
    "carry the multiplicity caveats already in their ledger rows.",
    "TGC is 0/1 per episode, so TGC cluster sums are integers and every sign pattern keeps "
    "the parity of the observed total. An observed total of one episode (e.g. "
    "CHAN-PRICE-01 P3 TGC, +1/114 = +0.88 pp) therefore gets p = 1 exactly; that is the "
    "test's discreteness, not an error.",
    "Percentile bounds on TGC sit on atoms (multiples of 1/114 or 1/171), so a bound can be "
    "seed-stable and still sit one atom from its threshold (COST-03: -6.1404 = -7/114; the "
    "next atom, -8/114 = -7.0175, would fail the -7.00 margin).",
]


def build_report(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    loader = Loader()
    report: dict[str, Any] = {
        "analysis": "J16 small-cluster inference (sign-flip permutation, wild cluster "
                    "bootstrap) beside the percentile cluster bootstrap; POOL-04 probes",
        "not_a_registered_analysis": True,
        "out_json": str(args.out_json),
        "seed": args.seed,
        "bootstrap": args.n_boot,
        "n_perm_scenario": args.n_perm_scenario,
        "n_perm_task": args.n_perm_task,
        "method": METHOD,
        "caveats": CAVEATS,
    }
    code = 0
    if args.section in ("all", "headline"):
        report["headline"] = run_headline(args, loader)
        if report["headline"].get("refused"):
            code = 2
    if args.section in ("all", "probes") and code == 0:
        report["probes"] = run_probes(args, loader)
    return report, code


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out-json", type=Path,
                   default=Path("campaign/results/j16_inference_20260923.report.json"))
    p.add_argument("--out-md", type=Path, default=Path("campaign/results/j16_inference_20260923.md"))
    p.add_argument("--section", choices=["all", "headline", "probes"], default="all")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--n-perm-scenario", type=int, default=N_PERM_SCENARIO)
    p.add_argument("--n-perm-task", type=int, default=N_PERM_TASK)
    p.add_argument("--probe-seeds", default=",".join(str(s) for s in PROBE_SEEDS))
    p.add_argument("--probe-big-b", type=int, default=PROBE_BIG_B)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    validate_output_path(args.out_json)
    validate_output_path(args.out_md)
    report, code = build_report(args)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"[j16] wrote {args.out_json} and {args.out_md} (exit {code})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
