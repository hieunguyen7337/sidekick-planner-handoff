#!/usr/bin/env python3
"""A16 read-only frame enumeration and PREFLIGHT arithmetic.

Does not call the planner. Does not write under /scratch/.../results/.
Does not submit branches.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

J6_TRAIN = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branch_runs.jsonl")
J6_MANIFEST = Path("/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/manifest.json")
J4_ROOT = Path("/scratch/n12194778/sidekick/results/hj4_correction_train_20260917")
RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")
CFG = Path(
    "/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/configs/hj4_correction.yaml"
)
SEEDS = (101, 102, 103, 104)
SELECT_SEED = 20260916
N_SAMPLE = 200
CONDITIONS = ("treated", "untreated")


def last_rows(path: Path) -> dict[tuple, dict]:
    last: dict[tuple, dict] = {}
    n_lines = 0
    with path.open() as fh:
        for line in fh:
            n_lines += 1
            r = json.loads(line)
            key = (
                str(r["campaign"]),
                int(r["seed"]),
                str(r["task_id"]),
                int(r["i"]),
                str(r["condition"]),
                int(r["branch_seed"]),
            )
            last[key] = r
    return last, n_lines


def point_id(row: dict) -> tuple[int, str, int]:
    return (int(row["seed"]), str(row["task_id"]), int(row["i"]))


def main() -> None:
    print("=== A16 FRAME / PREFLIGHT ===")
    print(f"j6_train={J6_TRAIN}")
    print(f"j6_exists={J6_TRAIN.is_file()}")
    print(f"j4_root_exists={J4_ROOT.is_dir()}")
    print(f"select_seed={SELECT_SEED} n_sample={N_SAMPLE}")

    last, n_lines = last_rows(J6_TRAIN)
    print(f"j6_jsonl_lines={n_lines} last_row_keys={len(last)}")

    by_point: dict[tuple[int, str, int], dict] = defaultdict(dict)
    calls: list[int] = []
    n_null_calls = 0
    for (_c, seed, task_id, i, cond, bseed), r in last.items():
        pid = (seed, task_id, i)
        by_point[pid][(cond, bseed)] = r
        raw = r.get("branch_planner_calls")
        if raw is None:
            n_null_calls += 1
        else:
            calls.append(int(raw))

    points = sorted(by_point.keys())
    n_points = len(points)
    print(f"unique_points={n_points}")

    complete = []
    for pid in points:
        d = by_point[pid]
        ok = all(
            d.get((c, s)) is not None and d[(c, s)].get("branch_gpr") is not None
            for c in CONDITIONS
            for s in SEEDS
        )
        if ok:
            complete.append(pid)
    print(f"j6_complete_points={len(complete)}")

    n_ceil = n_floor = n_cont_a16 = n_cont_w20 = 0
    for pid in complete:
        d = by_point[pid]
        t = [float(d[("treated", s)]["branch_gpr"]) for s in SEEDS]
        u = [float(d[("untreated", s)]["branch_gpr"]) for s in SEEDS]
        mean_t = sum(t) / 4.0
        mean_u = sum(u) / 4.0
        is_ceil = mean_u >= 1.0
        is_floor = (mean_u <= 0.0) and (mean_t <= 0.0)
        if is_ceil:
            n_ceil += 1
        if is_floor:
            n_floor += 1
        if mean_u < 1.000:
            n_cont_a16 += 1
        if (not is_ceil) and (not is_floor):
            n_cont_w20 += 1
    print(f"j6_complete_ceiling={n_ceil} floor={n_floor}")
    print(f"j6_complete_contestable_A16_mean_u_lt_1={n_cont_a16}")
    print(f"j6_complete_contestable_W20_nonceil_nonfloor={n_cont_w20}")

    if calls:
        s = sorted(calls)
        n = len(s)
        mean_c = sum(s) / n
        def pct(p):
            if n == 1:
                return s[0]
            k = (n - 1) * p
            lo = int(k)
            hi = min(lo + 1, n - 1)
            frac = k - lo
            return s[lo] + frac * (s[hi] - s[lo])
        print(
            "j6_train_branch_planner_calls "
            + json.dumps(
                {
                    "n": n,
                    "n_null": n_null_calls,
                    "sum": int(sum(s)),
                    "mean": mean_c,
                    "min": s[0],
                    "p50": pct(0.50),
                    "p90": pct(0.90),
                    "p95": pct(0.95),
                    "p99": pct(0.99),
                    "max": s[-1],
                },
                sort_keys=True,
            )
        )
        print(f"j6_mean_calls_per_branch={mean_c:.10f}")
        print(f"arith_expected_200pts={200 * 2 * 4 * mean_c:.6f}")

    # suppress_next campaigns already on disk?
    sn_hits = []
    if RESULTS_ROOT.is_dir():
        for man in sorted(RESULTS_ROOT.glob("*/manifest.json")):
            try:
                data = json.loads(man.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            cfg = data.get("branch_config") or {}
            mode = cfg.get("untreated_mode") or data.get("untreated_mode")
            if mode == "suppress_next":
                sn_hits.append(str(man))
    print(f"existing_suppress_next_manifests={sn_hits}")

    if J6_MANIFEST.is_file():
        man = json.loads(J6_MANIFEST.read_text())
        print(
            "j6_manifest "
            + json.dumps(
                {
                    "n_points": man.get("n_points"),
                    "n_complete": man.get("n_complete"),
                    "delta_band_delta": man.get("delta_band_delta"),
                    "untreated_mode": (man.get("branch_config") or {}).get("untreated_mode"),
                    "source_campaign": man.get("source_campaign"),
                },
                sort_keys=True,
            )
        )

    cfg_text = CFG.read_text()
    factor = None
    for line in cfg_text.splitlines():
        if "max_planner_calls:" in line and not line.strip().startswith("#"):
            factor = int(line.split(":")[1].split()[0])
            break
    print(f"hj4_correction_max_planner_calls={factor}")

    # Frozen draw
    eligible = list(points)  # no suppress_next exclusions (none)
    rng = random.Random(SELECT_SEED)
    rng.shuffle(eligible)
    sample = eligible[:N_SAMPLE]
    sample_sorted = sorted(sample)
    blob = "\n".join(f"{s}\t{t}\t{i}" for s, t, i in sample_sorted) + "\n"
    digest = hashlib.sha256(blob.encode()).hexdigest()
    n_sample_complete = sum(1 for p in sample if p in set(complete))
    print(f"sample_n={len(sample)}")
    print(f"sample_sha256={digest}")
    print(f"sample_j6_complete={n_sample_complete}")
    print(f"sample_j6_incomplete={len(sample) - n_sample_complete}")

    n_jobs = len(sample) * 2 * 4
    print(
        "PREFLIGHT_ARITH "
        + json.dumps(
            {
                "branches_to_run": n_jobs,
                "per_branch_planner_call_factor": factor,
                "projected_planner_calls": n_jobs * int(factor),
                "factor_source": "config limits.max_planner_calls (per-episode cap)",
                "max_planner_calls_total": None,
                "n_points": len(sample),
                "conditions": 2,
                "branch_seeds": 4,
                "note": "same formula as branch_counterfactual.run_branches PREFLIGHT",
            },
            sort_keys=True,
        )
    )

    print("SAMPLE_KEYS_BEGIN")
    for s, t, i in sample_sorted:
        print(f"{s}/{t}/{i}")
    print("SAMPLE_KEYS_END")


if __name__ == "__main__":
    main()
