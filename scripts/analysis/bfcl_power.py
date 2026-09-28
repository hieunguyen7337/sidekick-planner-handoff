#!/usr/bin/env python3
"""Power of the BFCL test predictions at the test design, from BFCL dev data only (E-prereg §6).

Implements §6 "Power" of docs/prereg_bfcl_test_20260925.md. It mirrors scripts/analysis/am1_power.py
function by function, and reuses its simulation core unchanged (`draw_design`, `cluster_sums`,
`bootstrap_means`, `percentile_ci`, `pvalue`, `interval_decision`, `simulate`, am1_power.py:143-302).
The one change of substance is the cluster: the entry id, not hj1_gate.scenario_of (which collapses every
BFCL id to one cluster, scripts/setup/hj1_gate.py:45-47). Each dev entry is therefore passed to
am1_power.simulate as a "scenario" holding exactly one task, itself.

Method. A simulated read draws 150 entries with replacement from the dev entries, and each drawn entry
takes 2 of seeds {1, 2, 3} without replacement (am1_power.draw_design; an entry that lacks a drawn seed
in some contrast falls back to the seeds it has, am1_power.cluster_sums :184-186). The same draw is used
by every contrast of the read. Each read is analysed as the E-prereg registers it: a percentile
entry-cluster bootstrap interval, and Holm within a family through the bootstrap p-value.

Decision rules (E-prereg §4): P6 and CF1 are supported when the interval excludes 0 on the positive side
and the Holm-adjusted p is <= 0.05 (H = {P6, P3}, m = 2; CF = {CF1}, m = 1). P3 is supported when its
lower bound is above -7.00 pp and its adjusted p is <= 0.05. B1 (handoff-only, h* from the prefix arm)
and S3 hold when the lower bound is above -7.00 pp (no family). CF3 is two-sided (interval excludes 0).
P6_alone is P6 in a family of its own, so the cost of adding P3 to H is visible (E-prereg §6).

Family D (depth, added 2026-09-28 before the E-prereg froze, its §9.5): D1 = prefix_bplus_m6 − prefix_bplus_m2
and D2 = prefix_zs_m6 − prefix_zs_m2 on all pairs, D3 / D4 the same contrasts handoff-only (Σd·h*/Σh*, h* of
the LEFT, m6 arm); each is supported when its interval lies above 0 and its Holm-adjusted p (m = 4, within D)
is <= 0.05. D is simulated in a pass of its own (am1_power.simulate with the same --seed, and --seed + 1 at
the half effect), so it consumes none of the random draws of the rows before it, and every earlier value of
this report is unchanged. D's reads are therefore independent of H's and CF's; no joint rate is reported.

Power is given at the dev effect and at half of it: every per-pair difference is shifted by half the dev
effect measured from the prediction's threshold (am1_power.py:336-340), i.e. by half the dev mean for the
rows judged at 0, and half-way to the margin for the non-inferiority rows.

The dev values are recomputed with bfcl_dev_report's own functions at its defaults (10,000 draws, seed
20260925), so every `dev.<id>` block matches that report's `contrasts.<dev_id>.goal_pass`.

Dev only: bfcl_dev_report.refuse_path / refuse_campaign refuse test_normal, test_challenge and _test_.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import am1_power as am1  # noqa: E402
from scripts.analysis import bfcl_dev_report as dr  # noqa: E402

ALPHA = am1.ALPHA
TEST_ENTRIES = 150
TEST_SEEDS_PER_ENTRY = am1.TEST_SEEDS_PER_TASK  # 2, drawn from dev seeds {1, 2, 3} (am1_power.draw_design)
DEFAULT_R = 1000  # E-prereg §6 settings: R = 1,000 reads, B = 2,000 each, seed 20260924
DEFAULT_B = 2000
DEFAULT_SEED = 20260924
DEFAULT_OUT = REPO_ROOT / "campaign" / "results" / "bfcl_power_20260924.report.json"
MARGIN = dr.NI_MARGIN

# id: left, right, direction, threshold, family (Holm), handoff_only, the rate reported as power, and
# the bfcl_dev_report contrast whose goal_pass block is its dev value.
CONTRASTS: dict[str, dict[str, Any]] = {
    "P6": dict(left="takeover_k5", right="advise_k5_fullctx", direction="greater", threshold=0.0,
               family="H", power_key="holm_supported", dev_id="P6"),
    "P3": dict(left="prefix_zs_m6", right="planner_alone_cap81", direction="greater", threshold=MARGIN,
               family="H", power_key="holm_supported", dev_id="P3_zs_m6"),
    "P6_alone": dict(left="takeover_k5", right="advise_k5_fullctx", direction="greater", threshold=0.0,
                     family="P6_alone", power_key="holm_supported", dev_id="P6"),
    "CF1": dict(left="advise_k5_neutral", right="advise_k5_fullctx", direction="greater", threshold=0.0,
                family="CF", power_key="holm_supported", dev_id="CF1"),
    "CF3": dict(left="takeover_k5", right="advise_k5_neutral", direction="two-sided", threshold=0.0,
                family=None, power_key="excludes_on_predicted_side", dev_id="CF3"),
    "B1_zs": dict(left="prefix_zs_m6", right="planner_alone_cap81", direction="greater", threshold=MARGIN,
                  family=None, handoff_only=True, power_key="lower_above", dev_id="B1_zs_m6_hstar"),
    "B1_bplus": dict(left="prefix_bplus_m6", right="planner_alone_cap81", direction="greater",
                     threshold=MARGIN, family=None, handoff_only=True, power_key="lower_above",
                     dev_id="B1_bplus_m6_hstar"),
    "S3": dict(left="prefix_bplus_m6", right="planner_alone_cap81", direction="greater", threshold=MARGIN,
               family=None, power_key="lower_above", dev_id="P3_bplus_m6"),
    # Family D (E-prereg §4, §9.5): depth m6 − m2, Holm within D (m = 4), simulated in its own pass.
    "D1": dict(left="prefix_bplus_m6", right="prefix_bplus_m2", direction="greater", threshold=0.0,
               family="D", power_key="holm_supported", dev_id="depth_bplus"),
    "D2": dict(left="prefix_zs_m6", right="prefix_zs_m2", direction="greater", threshold=0.0,
               family="D", power_key="holm_supported", dev_id="depth_zs"),
    "D3": dict(left="prefix_bplus_m6", right="prefix_bplus_m2", direction="greater", threshold=0.0,
               family="D", handoff_only=True, power_key="holm_supported", dev_id="depth_bplus_hstar"),
    "D4": dict(left="prefix_zs_m6", right="prefix_zs_m2", direction="greater", threshold=0.0,
               family="D", handoff_only=True, power_key="holm_supported", dev_id="depth_zs_hstar"),
}

# Families simulated in a pass of their own, after the main pass, so they draw nothing from its RNG.
SEPARATE_PASS_FAMILIES = ("D",)

RULES = {
    "holm_supported": "interval excludes the threshold on the predicted side AND Holm-adjusted p <= 0.05",
    "lower_above": "lower bound of the 95% entry interval above -7.00 pp (no family)",
    "excludes_on_predicted_side": "two-sided: the 95% entry interval excludes 0 (no family)",
}


# ---- loading (dev only) --------------------------------------------------------------------------
def load_arms(root: Path, configs_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict]]:
    """Every configured BFCL dev arm (bfcl_dev_report.load_arms) and h* of each prefix arm."""
    arms, _configured = dr.load_arms(root, configs_dir)
    hstars = {arm: dr.hstar_for(data) for arm, data in arms.items() if arm.startswith("prefix_")}
    return arms, hstars


def paired_rows(
    arms: dict[str, dict[str, Any]],
    hstars: dict[str, dict],
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    """am1_power.paired_rows with the entry id as the cluster label and h* of the left (prefix) arm.

    Pairing, crash drops and missing-side drops are bfcl_dev_report.paired_series on goal_pass_rate.
    A missing h* counts as 0 (E-prereg §4, B1).
    """
    series = dr.paired_series(arms[spec["left"]]["rows"], arms[spec["right"]]["rows"], "goal_pass")
    h = hstars.get(spec["left"], {})
    return [{"task": key[0], "seed": key[1], "scenario": key[0], "d": d, "h": 1.0 if h.get(key) is True else 0.0}
            for key, d in zip(series["keys"], series["diffs"])]


def availability(arms: dict[str, dict[str, Any]], rows: dict[str, Optional[list[dict[str, Any]]]]) -> dict[str, Optional[str]]:
    """id -> None if the row can be simulated, else the reason it is null. A family with an unavailable
    member is dropped whole, because Holm at a smaller m would not be the registered rule."""
    reasons: dict[str, Optional[str]] = {}
    for name, spec in CONTRASTS.items():
        why = dr._absent_reason(arms, (spec["left"], spec["right"]))
        if why is None and not rows.get(name):
            why = "no dev pairs"
        if why is None and spec.get("handoff_only") and am1.handoff_ratio(rows[name]) is None:
            why = "no handoff pair on dev (sum of h* = 0)"
        reasons[name] = why
    for fam in sorted({s["family"] for s in CONTRASTS.values() if s.get("family")}):
        members = [n for n, s in CONTRASTS.items() if s.get("family") == fam]
        bad = [n for n in members if reasons[n] is not None]
        if bad:
            for n in members:
                if reasons[n] is None:
                    reasons[n] = f"family {fam} incomplete: " + "; ".join(f"{b} ({reasons[b]})" for b in bad)
    return reasons


# ---- dev values ----------------------------------------------------------------------------------
def dev_values(arms, hstars, *, n_boot: int, seed: int) -> dict[str, Any]:
    """The goal_pass block of each row's bfcl_dev_report contrast, at that report's settings."""
    out: dict[str, Any] = {}
    cache: dict[str, dict[str, Any]] = {}
    for name, spec in CONTRASTS.items():
        dev_id = spec["dev_id"]
        if dev_id not in cache:
            cache[dev_id], _series = dr.contrast_block(dev_id, dr.CONTRASTS[dev_id], arms, hstars,
                                                       n_boot=n_boot, seed=seed)
        block = cache[dev_id]
        out[name] = {"dev_id": dev_id, "goal_pass": block.get("goal_pass"), "reason": block.get("reason")}
    return out


def half_shifts(rows: dict[str, list[dict[str, Any]]], names: list[str]) -> dict[str, float]:
    """am1_power.build's half-effect shift (:336-340): half the effect relative to the threshold."""
    out = {}
    for name in names:
        spec = CONTRASTS[name]
        point = am1.handoff_ratio(rows[name]) if spec.get("handoff_only") else statistics.fmean(r["d"] for r in rows[name])
        out[name] = (point - spec["threshold"]) / 2.0 if spec["direction"] != "two-sided" else point / 2.0
    return out


# ---- build ---------------------------------------------------------------------------------------
def build(
    root: Path = dr.RESULTS,
    configs_dir: Path = dr.CONFIGS_DIR,
    *,
    n_sims: int = DEFAULT_R,
    n_boot: int = DEFAULT_B,
    seed: int = DEFAULT_SEED,
    n_entries: int = TEST_ENTRIES,
    dev_n_boot: int = dr.N_BOOT,
    dev_seed: int = dr.SEED,
) -> dict[str, Any]:
    t0 = time.monotonic()
    dr.refuse_path(root)
    arms, hstars = load_arms(root, configs_dir)
    rows: dict[str, Optional[list[dict[str, Any]]]] = {}
    for name, spec in CONTRASTS.items():
        ok = dr._absent_reason(arms, (spec["left"], spec["right"])) is None
        rows[name] = paired_rows(arms, hstars, spec) if ok else None
    reasons = availability(arms, rows)
    live = [n for n in CONTRASTS if reasons[n] is None]
    indices = {n: am1.index_by_scenario(rows[n]) for n in live}
    full_shift = {n: 0.0 for n in live}
    half_shift = half_shifts(rows, live)  # type: ignore[arg-type]
    # The main pass sees only its own rows' indices: simulate draws its entries from the union of the
    # indices it is given, so a separate-pass row must not enter it.
    specs = {n: CONTRASTS[n] for n in live if CONTRASTS[n].get("family") not in SEPARATE_PASS_FAMILIES}
    if specs:
        main_idx = {n: indices[n] for n in specs}
        at_dev = am1.simulate(main_idx, specs, full_shift, n_sims=n_sims, n_boot=n_boot, seed=seed,
                              n_scenarios=n_entries)
        at_half = am1.simulate(main_idx, specs, half_shift, n_sims=n_sims, n_boot=n_boot, seed=seed + 1,
                               n_scenarios=n_entries)
    else:
        at_dev = {"per_contrast": {}, "families_all_supported": {}, "cf_readings": {}}
        at_half = {"per_contrast": {}, "families_all_supported": {}, "cf_readings": {}}
    separate: dict[str, Any] = {}
    for fam in SEPARATE_PASS_FAMILIES:
        fam_specs = {n: CONTRASTS[n] for n in live if CONTRASTS[n].get("family") == fam}
        separate[fam] = {"members": [n for n, s in CONTRASTS.items() if s.get("family") == fam],
                         "seed": seed, "seed_half": seed + 1, "run": bool(fam_specs)}
        if not fam_specs:
            continue
        fam_idx = {n: indices[n] for n in fam_specs}
        for target, shift, s in ((at_dev, full_shift, seed), (at_half, half_shift, seed + 1)):
            res = am1.simulate(fam_idx, fam_specs, shift, n_sims=n_sims, n_boot=n_boot, seed=s,
                               n_scenarios=n_entries)
            target["per_contrast"].update(res["per_contrast"])
            target["families_all_supported"].update(res["families_all_supported"])
    power: dict[str, Any] = {}
    for name, spec in CONTRASTS.items():
        key = spec["power_key"]
        if reasons[name] is not None:
            power[name] = {"full": None, "half": None, "key": key, "rule": RULES[key], "reason": reasons[name]}
        else:
            power[name] = {"full": at_dev["per_contrast"][name][key], "half": at_half["per_contrast"][name][key],
                           "key": key, "rule": RULES[key], "reason": None}
    families: dict[str, Any] = {}
    for fam in sorted({s["family"] for s in CONTRASTS.values() if s.get("family")}):
        members = [n for n, s in CONTRASTS.items() if s.get("family") == fam]
        if fam in at_dev["families_all_supported"]:
            families[fam] = {"members": members, "full": at_dev["families_all_supported"][fam],
                             "half": at_half["families_all_supported"][fam], "reason": None}
        else:
            families[fam] = {"members": members, "full": None, "half": None,
                             "reason": "; ".join(f"{n}: {reasons[n]}" for n in members if reasons[n])}
    campaigns = {d["campaign_id"]: Path(d["dir"]).is_dir() for d in arms.values()}
    report = {
        "meta": {
            "generated_by": "scripts/analysis/bfcl_power.py",
            "prereg": "docs/prereg_bfcl_test_20260925.md §6 (power is reported, not used as a gate)",
            "split": "dev",
            "results_root": str(root),
            "campaigns_found": sorted(c for c, ok in campaigns.items() if ok),
            "campaigns_absent": sorted(c for c, ok in campaigns.items() if not ok),
            "n_sim": n_sims,
            "n_boot": n_boot,
            "seed": seed,
            "seed_half": seed + 1,
            "alpha": ALPHA,
            "design": {"n_entries": n_entries, "seeds_per_entry": TEST_SEEDS_PER_ENTRY,
                       "dev_seeds_available": [1, 2, 3], "entries_drawn": "with replacement from the dev entries",
                       "seeds_drawn": "without replacement within an entry"},
            "cluster_unit": "entry",
            "margin_pp": round(MARGIN * 100, 2),
            "dev_n_boot": dev_n_boot,
            "dev_seed": dev_seed,
            "separate_pass_families": {
                **separate,
                "note": ("each family here is simulated in its own am1_power.simulate pass after the main one, "
                         "seeded with --seed (--seed + 1 at the half effect), so the main pass's draws and "
                         "every row before it are unchanged; its reads are independent of the other families'"),
            },
            "git_sha": dr.git_sha(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "contrasts": {n: dict(s) for n, s in CONTRASTS.items()},
        "dev": dev_values(arms, hstars, n_boot=dev_n_boot, seed=dev_seed),
        "power": power,
        "families_all_supported": families,
        "half_effect_shift_pp": {k: round(v * 100, 3) for k, v in half_shift.items()},
        "power_at_dev_effect": at_dev,
        "power_at_half_effect": at_half,
        "caveats": [
            "Resampling dev entries treats the dev effect as the truth; the half-effect rows guard against that optimism.",
            "B per simulated read is below the registered 10,000; interval endpoints carry Monte Carlo error.",
            "Half effect: shift = (dev point - threshold) / 2 (am1_power.py:336-340), so the NI rows move half-way "
            "to -7.00 pp, and the rows at 0 move by half the dev mean.",
            "Every row is on goal_pass_rate, the E-prereg's primary metric.",
        ],
    }
    report["meta"]["runtime_s"] = round(time.monotonic() - t0, 1)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=dr.RESULTS)
    ap.add_argument("--configs", type=Path, default=dr.CONFIGS_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--sims", type=int, default=DEFAULT_R)
    ap.add_argument("--boot", type=int, default=DEFAULT_B)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--entries", type=int, default=TEST_ENTRIES)
    ap.add_argument("--dev-n-boot", type=int, default=dr.N_BOOT)
    ap.add_argument("--dev-seed", type=int, default=dr.SEED)
    args = ap.parse_args(argv)
    dr.refuse_path(args.out)
    report = build(args.root, args.configs, n_sims=args.sims, n_boot=args.boot, seed=args.seed,
                   n_entries=args.entries, dev_n_boot=args.dev_n_boot, dev_seed=args.dev_seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"BFCL power (dev -> test design {args.entries} entries x 2 seeds; n_sim={args.sims} "
          f"n_boot={args.boot} seed={args.seed}; runtime {report['meta']['runtime_s']} s)")
    for name, p in report["power"].items():
        print(f"  {name:<10} full {p['full']!s:>7}  half {p['half']!s:>7}  [{p['key']}]"
              f"{'  ' + p['reason'][:80] if p['reason'] else ''}")
    for fam, f in report["families_all_supported"].items():
        print(f"  all of {fam:<8} full {f['full']!s:>7}  half {f['half']!s:>7}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
