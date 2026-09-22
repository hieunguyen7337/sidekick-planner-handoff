#!/usr/bin/env python
"""J10 analysis — finished before test_normal is ever read.

This script implements the contrasts and decision rules written in
``docs/prereg_v1.md``. It does not choose among them. Where that document is
ambiguous, internally inconsistent, or in conflict with ``campaign/RUNS.md``
(the J9 freeze has not happened), the script **refuses the affected decision**
and lists the ambiguity with a ``path:line`` citation.

It is a protocol error to run this on ``test_normal`` or ``test_challenge``
without an explicit confirmation flag. Dev archives are the only intended
validation target until J10.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = REPO_ROOT / "src"
for _p in (str(REPO_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.setup.hj1_gate import (  # noqa: E402
    BOOTSTRAP,
    SEED,
    paired_diff,
    scenario_goal_completion,
)
from sidekick.cost.ledger import CostLedger  # noqa: E402

SplitName = Literal["train", "dev", "test_normal", "test_challenge"]

SPLIT_N_TASKS = {
    "train": 90,
    "dev": 57,
    "test_normal": 168,
    "test_challenge": 417,
}
HELDOUT_TEST_SPLITS = {"test_normal", "test_challenge"}
HELDOUT_MARKERS = ("test_normal", "test_challenge")

# Pinned J10 arm list minus the optional router [OBSERVED docs/prereg_v1.md:79-86].
REQUIRED_ARMS = (
    "planner_alone",
    "executor_alone",
    "prompt_only",
    "fixed_k",
    "sft_plan",
    "sidekick",
)
OPTIONAL_ARMS = ("router_seq", "fixed_k_k5")
ALLOWED_ARMS = set(REQUIRED_ARMS) | set(OPTIONAL_ARMS)

# Failure types that prereg §6.1 scores as TGC = 0 / SGC = 0
# [OBSERVED docs/prereg_v1.md:175].
SCORED_FAILURE_TYPES = {"limit", "timeout", "crash", "parse_error", "api_error"}
QUOTA_STALL_TYPES = {"api_error", "timeout"}
QUOTA_STALL_FRAC = 0.05
NONINFERIORITY_MARGIN_PP = 7.00
CACHED_BILLING_WEIGHT = 0.10  # prereg §4.3: 0.10 × cached input
K_MATCHED_ALLOWED = {3, 5, 7, 10}

# Resampling unit for every official CI. See RESAMPLE_JUSTIFICATION.
RESAMPLE_UNIT: Literal["task"] = "task"

RESAMPLE_JUSTIFICATION = (
    "The unit of resampling is the task. "
    "scripts/setup/hj1_gate.py:paired_diff(resample='task') draws tasks with "
    "replacement and carries every matched seed of that task together "
    "[OBSERVED scripts/setup/hj1_gate.py:91-100, 161-174]; "
    "scripts/setup/branch_counterfactual.py:task_clustered_bootstrap does the "
    "same [OBSERVED scripts/setup/branch_counterfactual.py:299-338, 735-738]. "
    "Paired seeds on one task are not independent samples; treating "
    "(task, seed) pairs as the resample unit would understate every interval. "
    "Prereg §3.1 first averages TGC across the N seeds of a task and then "
    "bootstraps the task-difference vector [OBSERVED docs/prereg_v1.md:107-117]. "
    "With equal seed counts per task that estimand equals the clustered "
    "seed-level mean that paired_diff reports. This script refuses a contrast "
    "rather than mix cluster sizes, so the two writings coincide when a "
    "decision is emitted."
)

# Ambiguities found in the prereg. The script does not pick a winner.
# A list of these is a deliverable; silently coding a choice is an
# unregistered analysis decision [OBSERVED campaign/workers/brief_A12_j10_analysis.md:37-41].
UNRESOLVED_AMBIGUITIES: list[dict[str, Any]] = [
    {
        "id": "one_sided_vs_two_sided_bootstrap",
        "citations": [
            "docs/prereg_v1.md:36",
            "docs/prereg_v1.md:46",
            "docs/prereg_v1.md:117-122",
            "scripts/setup/hj1_gate.py:129-136",
        ],
        "what": (
            "H2 and H1 are described as a one-sided 95% paired bootstrap, but "
            "§3.2 names hj1_gate.paired_diff as the exact procedure, and that "
            "function uses two-sided percentile endpoints at 2.5% and 97.5%."
        ),
        "script_behaviour": (
            "Official CIs are hj1_gate.paired_diff two-sided 95% intervals "
            "because §3.2 names that function. A one-sided interval is not "
            "computed. J9 must freeze which one is the test."
        ),
    },
    {
        "id": "task_mean_vector_vs_clustered_seed_diffs",
        "citations": [
            "docs/prereg_v1.md:107-117",
            "docs/prereg_v1.md:36",
            "scripts/setup/hj1_gate.py:153-175",
        ],
        "what": (
            "§3.1 defines Δ_i as the difference of per-task seed-means (168 "
            "numbers) and bootstraps that vector. §1.1 counts 504 paired "
            "(task, seed) comparisons. paired_diff computes seed-level diffs "
            "and then clusters the bootstrap by task. These coincide only "
            "when every task has the same number of seeds."
        ),
        "script_behaviour": (
            "Uses paired_diff(resample='task') as the named §3.2 procedure, "
            "and refuses the contrast if cluster sizes would be unequal "
            "(incomplete seed coverage). J9 should say whether the estimand "
            "is the 168-vector or the clustered 504-vector."
        ),
    },
    {
        "id": "h2_three_clause_vs_h2a_h2b",
        "citations": [
            "docs/prereg_v1.md:35-40",
            "docs/prereg_v1.md:119-123",
            "campaign/RUNS.md:1465-1470",
            "campaign/RUNS.md:1541-1559",
        ],
        "what": (
            "The prereg file still states a three-clause conjunctive H2 "
            "(vs fixed_k(k_matched) at −7 pp; vs sft_plan CI>0; fewer calls "
            "than fixed_k(k=5)). campaign/RUNS.md later says that form is "
            "not satisfiable as written and replaces it at J9 with H2a∧H2b."
        ),
        "script_behaviour": (
            "Computes the three-clause form written in docs/prereg_v1.md. "
            "Does not replace it with H2a/H2b. J9 must freeze the primary."
        ),
    },
    {
        "id": "failure_scoring_vs_never_coerce_none",
        "citations": [
            "docs/prereg_v1.md:175",
            "scripts/setup/hj1_gate.py:15-16",
            "src/sidekick/protocols/schemas.py:35-37",
            "src/sidekick/systems/loop.py:954-968",
        ],
        "what": (
            "§6.1 scores limit/timeout/crash/parse_error/api_error as TGC=0. "
            "loop.py still writes evaluate()'s tgc (which can be 1.0) on a "
            "limit run, and the campaign convention is that None means not "
            "measured and must never be coerced to 0."
        ),
        "script_behaviour": (
            "error_type in the §6.1 set with recorded tgc None or 0.0 is "
            "scored 0 and counted as a scored failure (not dropped). "
            "tgc is None and error_type is not in that set → missing metric, "
            "refuse. recorded tgc not in {0, None} on a §6.1 failure → "
            "recorded-vs-6.1 disagreement, refuse. J9 should say whether "
            "evaluate() TGC on a limit/timeout run is kept."
        ),
    },
    {
        "id": "complete_accounting_vs_intersection_pairing",
        "citations": [
            "docs/prereg_v1.md:174",
            "scripts/setup/hj1_gate.py:132-152",
        ],
        "what": (
            "§6.1 forbids dropping any initialized (task, seed) from the "
            "denominator. paired_diff pairs on the intersection of keys and "
            "drops unmatched runs."
        ),
        "script_behaviour": (
            "If any required cell is missing, hypothesis decisions are "
            "refused. paired_diff is only called when the intersection is "
            "the full registered matrix, so nothing is dropped."
        ),
    },
    {
        "id": "fcd_pooled_vs_paired_and_billed_vs_unweighted",
        "citations": [
            "docs/prereg_v1.md:137-139",
            "docs/PLAN.md:157-159",
            "src/sidekick/cost/ledger.py:40, 57-67",
        ],
        "what": (
            "Prereg §4.3 defines C_P as billed planner tokens "
            "(input + 0.10×cached + output + reasoning) and FCD as "
            "1 − C_P,sidekick / C_P,planner_alone. PLAN.md says FCD is "
            "always paired by task. CostLedger.planner_tokens_total is an "
            "unweighted sum and frontier_displacement uses that."
        ),
        "script_behaviour": (
            "Reports billed-pooled, ledger-unweighted-pooled, and mean of "
            "per-task billed ratios. H1's FCD>0 conjunct is refused if those "
            "definitions disagree on the sign of (FCD>0) or any is undefined."
        ),
    },
    {
        "id": "h4_pvalue_and_matched_calls",
        "citations": [
            "docs/prereg_v1.md:48-49",
            "scripts/setup/hj1_gate.py:124-192",
        ],
        "what": (
            "H4 asks for p<0.05 at matched planner calls. paired_diff does "
            "not return a p-value. 'Matched' is a J9 calibration of router "
            "τ* on dev; the prereg does not say what to do if test call "
            "counts then differ."
        ),
        "script_behaviour": (
            "If router_seq is absent, H4 is skipped (optional arm). If "
            "present, the TGC contrast CI is reported and no p-value is "
            "invented. No H4 pass/fail is emitted; J9 must define 'matched' "
            "and the p-value."
        ),
    },
    {
        "id": "c_solved_denominator",
        "citations": ["docs/prereg_v1.md:140-142"],
        "what": (
            "'Number of completed tasks' is not defined (successes vs. "
            "finished episodes vs. initialized cells)."
        ),
        "script_behaviour": (
            "Reports usd_total / n_success per arm and usd_total / n_runs. "
            "Does not pick one as C_solved for a test."
        ),
    },
    {
        "id": "h3_and_f_dev_are_not_j10_archive_quantities",
        "citations": [
            "docs/prereg_v1.md:50-53",
            "docs/prereg_v1.md:146-149",
        ],
        "what": (
            "H3 (AUROC/ECE vs oracle labels) and f_dev are defined on dev "
            "counterfactual branches (J6/J7), not on the J10 test_normal "
            "matrix."
        ),
        "script_behaviour": (
            "These are not computed from J10 arm archives. The report "
            "states that rather than inventing a test-set calibration."
        ),
    },
    {
        "id": "unsafe_irreversible_not_in_schema",
        "citations": [
            "docs/prereg_v1.md:150-152",
            "src/sidekick/protocols/schemas.py:129-145",
        ],
        "what": (
            "Unsafe irreversible-action violations have no field on "
            "RunResult, and this script does not design an events.jsonl "
            "parser to recover them."
        ),
        "script_behaviour": "Reported as unmeasurable from result.json.",
    },
    {
        "id": "paired_diff_scales_calls_as_percentage_points",
        "citations": [
            "docs/prereg_v1.md:122",
            "scripts/setup/hj1_gate.py:189-190",
        ],
        "what": (
            "H2 clause 3 is in units of planner calls, but paired_diff "
            "always multiplies the mean difference by 100 and labels it pp."
        ),
        "script_behaviour": (
            "The resampling is still paired_diff. Call contrasts are also "
            "reported in native units (pp/100). The sign test against 0 is "
            "invariant to that scale. J9 should say the call CI is not in pp."
        ),
    },
]


def _json_number(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def heldout_marker_in_path(path: Path) -> Optional[str]:
    text = str(path)
    for marker in HELDOUT_MARKERS:
        if marker in text:
            return marker
    return None


def parse_arm_specs(specs: list[str]) -> dict[str, Path]:
    arms: dict[str, Path] = {}
    for spec in specs:
        label, sep, directory = spec.partition("=")
        if not sep or not label or not directory:
            raise ValueError(f"expected LABEL=DIR, got {spec!r}")
        if label not in ALLOWED_ARMS:
            raise ValueError(
                f"unknown arm label {label!r}; allowed: {sorted(ALLOWED_ARMS)}"
            )
        if label in arms:
            raise ValueError(f"duplicate --arm {label}")
        arms[label] = Path(directory)
    return arms


def parse_seeds(raw: str) -> list[int]:
    seeds = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not seeds:
        raise ValueError("--seeds is empty")
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"duplicate seeds in {raw!r}")
    return seeds


def _read_result(path: Path) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        return None, f"unreadable:{exc.__class__.__name__}"
    if not text:
        return None, "empty_file"
    try:
        row = json.loads(text)
    except json.JSONDecodeError:
        return None, "invalid_json"
    if not isinstance(row, dict):
        return None, "not_an_object"
    return row, None


def load_arm_tree(root: Path) -> dict[str, Any]:
    """Load every result.json under root. Empty/invalid files are not runs."""
    runs: dict[tuple[str, int], dict[str, Any]] = {}
    empty_files: list[str] = []
    unreadable: list[str] = []
    duplicates: list[str] = []
    systems: set[str] = set()
    if not root.exists():
        return {
            "runs": runs,
            "empty_files": empty_files,
            "unreadable": unreadable,
            "duplicates": duplicates,
            "systems": systems,
            "root_missing": True,
        }
    for path in sorted(root.rglob("result.json")):
        row, err = _read_result(path)
        if err == "empty_file":
            empty_files.append(str(path))
            continue
        if row is None:
            unreadable.append(f"{path}:{err}")
            continue
        task_id = row.get("task_id")
        seed = row.get("seed")
        if task_id is None or seed is None:
            unreadable.append(f"{path}:missing_task_id_or_seed")
            continue
        key = (str(task_id), int(seed))
        if key in runs:
            duplicates.append(f"{path}:duplicate_{key[0]}_{key[1]}")
            continue
        runs[key] = row
        if row.get("system") is not None:
            systems.add(str(row["system"]))
    return {
        "runs": runs,
        "empty_files": empty_files,
        "unreadable": unreadable,
        "duplicates": duplicates,
        "systems": systems,
        "root_missing": False,
    }


def recorded_tgc(row: dict[str, Any]) -> Optional[float]:
    if "tgc" not in row:
        return None
    value = row["tgc"]
    if value is None:
        return None
    return float(value)


def score_tgc(row: dict[str, Any]) -> dict[str, Any]:
    """Apply the two TGC writings without collapsing them into one number.

    Returns a status used by the inventory. Official TGC for a contrast is
    only taken from cells whose two writings agree.
    """
    err = row.get("error_type")
    rec = recorded_tgc(row)
    scored_failure = err in SCORED_FAILURE_TYPES
    if scored_failure:
        prereg_61 = 0.0
        if rec is None or rec == 0.0:
            return {
                "status": "scored_failure",
                "tgc": 0.0,
                "recorded_tgc": rec,
                "error_type": err,
            }
        return {
            "status": "scored_failure_disagrees_with_recorded_tgc",
            "tgc": None,
            "recorded_tgc": rec,
            "prereg_6_1_tgc": prereg_61,
            "error_type": err,
        }
    if rec is None:
        return {
            "status": "missing_metric",
            "tgc": None,
            "recorded_tgc": None,
            "error_type": err,
        }
    return {
        "status": "ok",
        "tgc": rec,
        "recorded_tgc": rec,
        "error_type": err,
    }


def optional_int(row: dict[str, Any], field: str) -> Optional[int]:
    if field not in row or row[field] is None:
        return None
    return int(row[field])


def optional_float(row: dict[str, Any], field: str) -> Optional[float]:
    if field not in row or row[field] is None:
        return None
    return float(row[field])


def planner_actor(row: dict[str, Any]) -> Optional[dict[str, Any]]:
    totals = row.get("totals")
    if not isinstance(totals, dict):
        return None
    per_actor = totals.get("per_actor")
    if not isinstance(per_actor, dict):
        return None
    actor = per_actor.get("planner")
    if actor is None:
        return {}
    if not isinstance(actor, dict):
        return None
    return actor


def billed_planner_tokens(row: dict[str, Any]) -> Optional[float]:
    actor = planner_actor(row)
    if actor is None:
        return None
    if actor == {}:
        calls = optional_int(row, "n_planner_calls")
        if calls == 0:
            return 0.0
        return None
    fields = (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_output_tokens",
    )
    values: list[float] = []
    for name in fields:
        if name not in actor:
            values.append(0.0)
            continue
        if actor[name] is None:
            return None
        values.append(float(actor[name]))
    inp, cached, out, reason = values
    return inp + CACHED_BILLING_WEIGHT * cached + out + reason


def ledger_planner_tokens(row: dict[str, Any]) -> Optional[float]:
    totals = row.get("totals")
    if not isinstance(totals, dict):
        return None
    if "planner_tokens_total" not in totals:
        actor = planner_actor(row)
        if actor is None:
            return None
        if actor == {}:
            calls = optional_int(row, "n_planner_calls")
            return 0.0 if calls == 0 else None
        fields = (
            "input_tokens",
            "cached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
        )
        total = 0.0
        for name in fields:
            if name not in actor:
                continue
            if actor[name] is None:
                return None
            total += float(actor[name])
        return total
    value = totals["planner_tokens_total"]
    if value is None:
        return None
    return float(value)


def usd_total(row: dict[str, Any]) -> Optional[float]:
    totals = row.get("totals")
    if not isinstance(totals, dict) or "usd_total" not in totals:
        return None
    if totals["usd_total"] is None:
        return None
    return float(totals["usd_total"])


def inventory_arm(
    label: str,
    loaded: dict[str, Any],
    tasks: list[str],
    seeds: list[int],
) -> dict[str, Any]:
    runs: dict[tuple[str, int], dict[str, Any]] = loaded["runs"]
    cells: dict[str, Any] = {}
    counts: Counter[str] = Counter()
    cleaned: dict[tuple[str, int], dict[str, Any]] = {}
    extra_keys = [key for key in runs if key[1] not in seeds or key[0] not in set(tasks)]
    # Extra seeds/tasks relative to the registered matrix: counted, not analysed.
    extra_runs = []
    task_set = set(tasks)
    seed_set = set(seeds)
    for key, row in runs.items():
        if key[0] not in task_set or key[1] not in seed_set:
            extra_runs.append({"task_id": key[0], "seed": key[1]})

    disagree = []
    missing_calls = []
    for task_id in tasks:
        for seed in seeds:
            key = (task_id, seed)
            slot = {"task_id": task_id, "seed": seed}
            if key not in runs:
                slot["status"] = "missing_run"
                counts["missing_run"] += 1
                cells[f"{task_id}/{seed}"] = slot
                continue
            row = runs[key]
            scored = score_tgc(row)
            slot.update(scored)
            slot["goal_pass_rate"] = optional_float(row, "goal_pass_rate")
            counts[scored["status"]] += 1
            if scored["status"] == "scored_failure_disagrees_with_recorded_tgc":
                disagree.append(slot)
            if scored["status"] == "missing_metric":
                cells[f"{task_id}/{seed}"] = slot
                continue
            if scored["status"] == "scored_failure_disagrees_with_recorded_tgc":
                cells[f"{task_id}/{seed}"] = slot
                continue
            calls = optional_int(row, "n_planner_calls")
            steps = optional_int(row, "steps")
            n_asks = optional_int(row, "n_asks")
            if calls is None:
                missing_calls.append(key)
                slot["status"] = "missing_metric"
                counts["missing_metric"] += 1
                counts[scored["status"]] -= 1
                cells[f"{task_id}/{seed}"] = slot
                continue
            tgc = scored["tgc"]
            assert tgc is not None
            success = bool(row.get("success")) and scored["status"] == "ok"
            if scored["status"] == "scored_failure":
                success = False
            cleaned[key] = {
                "task_id": task_id,
                "seed": seed,
                "tgc": tgc,
                "goal_pass_rate": slot["goal_pass_rate"],
                "success": success,
                "n_planner_calls": calls,
                "steps": 0 if steps is None else steps,
                "steps_missing": steps is None,
                "n_asks": 0 if n_asks is None else n_asks,
                "n_asks_missing": n_asks is None,
                "error_type": row.get("error_type"),
                "billed_planner_tokens": billed_planner_tokens(row),
                "ledger_planner_tokens": ledger_planner_tokens(row),
                "usd_total": usd_total(row),
            }
            cells[f"{task_id}/{seed}"] = slot

    expected_n = len(tasks) * len(seeds)
    n_missing_run = counts["missing_run"]
    n_missing_metric = counts["missing_metric"]
    n_disagree = counts["scored_failure_disagrees_with_recorded_tgc"]
    n_ok = counts["ok"]
    n_scored_failure = counts["scored_failure"]
    complete = (
        n_missing_run == 0
        and n_missing_metric == 0
        and n_disagree == 0
        and not loaded["empty_files"]
        and not loaded["unreadable"]
        and not loaded["duplicates"]
        and not loaded["root_missing"]
        and len(cleaned) == expected_n
    )
    quota_n = 0
    for row in (runs[k] for k in runs if k[0] in task_set and k[1] in seed_set):
        if row.get("error_type") in QUOTA_STALL_TYPES:
            quota_n += 1
    quota_frac = (quota_n / expected_n) if expected_n else None

    tgc_values = [row["tgc"] for row in cleaned.values()]
    call_values = [row["n_planner_calls"] for row in cleaned.values()]
    gpr_values = [
        row["goal_pass_rate"]
        for row in cleaned.values()
        if row["goal_pass_rate"] is not None
    ]
    n_gpr_missing = sum(
        1 for row in cleaned.values() if row["goal_pass_rate"] is None
    )
    return {
        "label": label,
        "n_expected": expected_n,
        "n_cleaned": len(cleaned),
        "n_ok": n_ok,
        "n_scored_failure": n_scored_failure,
        "n_missing_run": n_missing_run,
        "n_missing_metric": n_missing_metric,
        "n_scored_failure_disagrees_with_recorded_tgc": n_disagree,
        "n_empty_files": len(loaded["empty_files"]),
        "n_unreadable": len(loaded["unreadable"]),
        "n_duplicates": len(loaded["duplicates"]),
        "n_extra_runs_ignored": len(extra_runs),
        "systems_in_tree": sorted(loaded["systems"]),
        "root_missing": loaded["root_missing"],
        "complete": complete,
        "tgc_mean": (
            round(statistics.fmean(tgc_values), 6) if tgc_values and complete else None
        ),
        "goal_pass_rate_mean": (
            round(statistics.fmean(gpr_values), 6) if gpr_values else None
        ),
        "n_goal_pass_rate_recorded": len(gpr_values),
        "n_goal_pass_rate_missing": n_gpr_missing,
        "n_success": sum(1 for row in cleaned.values() if row["success"]),
        "planner_calls_mean": (
            round(statistics.fmean(call_values), 6) if call_values and complete else None
        ),
        "quota_stall_n": quota_n,
        "quota_stall_frac": _json_number(quota_frac),
        "quota_stall": bool(quota_frac is not None and quota_frac > QUOTA_STALL_FRAC),
        "error_types": dict(
            sorted(
                Counter(
                    str(runs[k].get("error_type") or "none")
                    for k in runs
                    if k[0] in task_set and k[1] in seed_set
                ).items()
            )
        ),
        "disagreements": disagree,
        "empty_files": loaded["empty_files"],
        "unreadable": loaded["unreadable"],
        "duplicates": loaded["duplicates"],
        "extra_runs_ignored": extra_runs[:20],
        "cleaned": cleaned,
        "n_cells_shown_in_detail": 0,
        "_extra_keys": extra_keys,
    }


def discover_tasks(loaded_by_arm: dict[str, dict[str, Any]], seeds: list[int]) -> list[str]:
    tasks: set[str] = set()
    seed_set = set(seeds)
    for loaded in loaded_by_arm.values():
        for task_id, seed in loaded["runs"]:
            if seed in seed_set:
                tasks.add(task_id)
    return sorted(tasks)


def cluster_sizes_equal(cleaned: dict[tuple[str, int], dict[str, Any]], n_seeds: int) -> bool:
    by_task: Counter[str] = Counter(task_id for task_id, _seed in cleaned)
    return bool(by_task) and all(n == n_seeds for n in by_task.values())


def native_from_paired_diff(cmp: dict[str, Any]) -> dict[str, Any]:
    out = dict(cmp)
    if "diff_pp" in cmp:
        out["diff"] = round(cmp["diff_pp"] / 100.0, 6)
    if "ci95_pp" in cmp:
        out["ci95"] = [round(v / 100.0, 6) for v in cmp["ci95_pp"]]
    return out


def contrast_tgc(
    sidekick: dict[tuple[str, int], dict[str, Any]],
    other: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    task = paired_diff(sidekick, other, "tgc", resample="task")
    pair = paired_diff(sidekick, other, "tgc", resample="pair")
    out = native_from_paired_diff(task)
    out["diagnostic_pair_resample"] = native_from_paired_diff(pair)
    out["resample_unit_for_decision"] = RESAMPLE_UNIT
    return out


def contrast_calls(
    sidekick: dict[tuple[str, int], dict[str, Any]],
    other: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    task = paired_diff(sidekick, other, "n_planner_calls", resample="task")
    out = native_from_paired_diff(task)
    out["units"] = "planner_calls (ci95); paired_diff also reports ci95_pp = 100×calls"
    out["resample_unit_for_decision"] = RESAMPLE_UNIT
    return out


def contrast_goal_pass_rate(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    """Task-clustered contrast on recorded goal_pass_rate only.

    Missing/null values are dropped and counted, never coerced to 0.0.
    paired_diff skips None then zips the unfiltered key list against the
    filtered diffs [OBSERVED scripts/setup/hj1_gate.py:180-207], so this
    wrapper keeps only pairs with a recorded value before calling it.
    """
    field = "goal_pass_rate"
    shared = set(left) & set(right)
    unmatched = {
        "base": len(left) - len(shared),
        "other": len(right) - len(shared),
        "total": (len(left) - len(shared)) + (len(right) - len(shared)),
    }
    left_ok: dict[tuple[str, int], dict[str, Any]] = {}
    right_ok: dict[tuple[str, int], dict[str, Any]] = {}
    missing_field = 0
    for key in shared:
        lv = left[key].get(field)
        rv = right[key].get(field)
        if lv is None or rv is None:
            missing_field += 1
            continue
        left_ok[key] = left[key]
        right_ok[key] = right[key]
    empty = {
        "field": field,
        "n_pairs": 0,
        "n_tasks": 0,
        "n_clusters": 0,
        "mean_cluster_size": None,
        "resample": RESAMPLE_UNIT,
        "resample_unit": RESAMPLE_UNIT,
        "resample_unit_for_decision": RESAMPLE_UNIT,
        "pairs_dropped_missing_field": missing_field,
        "dropped_unmatched_keys": unmatched,
        "dropped_from_base": unmatched["base"],
        "dropped_from_other": unmatched["other"],
        "note": "no pairs with a recorded goal_pass_rate value",
        "ci95": None,
        "ci95_pp": None,
        "diff": None,
        "diff_pp": None,
    }
    if not left_ok:
        return empty
    task = paired_diff(left_ok, right_ok, field, resample="task")
    pair = paired_diff(left_ok, right_ok, field, resample="pair")
    out = native_from_paired_diff(task)
    out["diagnostic_pair_resample"] = native_from_paired_diff(pair)
    out["resample_unit_for_decision"] = RESAMPLE_UNIT
    out["field"] = field
    out["pairs_dropped_missing_field"] = missing_field
    out["dropped_unmatched_keys"] = unmatched
    out["dropped_from_base"] = unmatched["base"]
    out["dropped_from_other"] = unmatched["other"]
    return out


def fcd_bundle(
    sidekick: dict[tuple[str, int], dict[str, Any]],
    planner: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    keys = sorted(set(sidekick) & set(planner))
    billed_s = [sidekick[k]["billed_planner_tokens"] for k in keys]
    billed_p = [planner[k]["billed_planner_tokens"] for k in keys]
    led_s = [sidekick[k]["ledger_planner_tokens"] for k in keys]
    led_p = [planner[k]["ledger_planner_tokens"] for k in keys]
    if any(v is None for v in billed_s + billed_p + led_s + led_p):
        return {
            "status": "refused",
            "reason": "a planner-token field is None; not coerced to 0",
        }
    sum_billed_s = sum(billed_s)  # type: ignore[arg-type]
    sum_billed_p = sum(billed_p)  # type: ignore[arg-type]
    sum_led_s = sum(led_s)  # type: ignore[arg-type]
    sum_led_p = sum(led_p)  # type: ignore[arg-type]
    billed_pooled = (
        1.0 - sum_billed_s / sum_billed_p if sum_billed_p else float("nan")
    )
    ledger_pooled = CostLedger.frontier_displacement(
        {"planner_tokens_total": sum_led_s, "planner_calls_total": 0},
        {"planner_tokens_total": sum_led_p, "planner_calls_total": 0},
    )["fcd_tokens"]
    # Mean of per-task ratios of seed-sums (PLAN.md "paired by task").
    by_task_s: dict[str, list[float]] = {}
    by_task_p: dict[str, list[float]] = {}
    for (task_id, _seed), row in sidekick.items():
        by_task_s.setdefault(task_id, []).append(row["billed_planner_tokens"])
    for (task_id, _seed), row in planner.items():
        by_task_p.setdefault(task_id, []).append(row["billed_planner_tokens"])
    per_task: list[float] = []
    skipped_zero_baseline = 0
    for task_id in sorted(set(by_task_s) & set(by_task_p)):
        base = sum(by_task_p[task_id])
        if base == 0:
            skipped_zero_baseline += 1
            continue
        per_task.append(1.0 - sum(by_task_s[task_id]) / base)
    paired_mean = statistics.fmean(per_task) if per_task else float("nan")

    def _pos(value: float) -> Optional[bool]:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        return bool(value > 0)

    signs = {
        "billed_pooled": _pos(billed_pooled),
        "ledger_unweighted_pooled": _pos(ledger_pooled),
        "mean_of_per_task_billed_ratios": _pos(paired_mean),
    }
    defined_signs = [v for v in signs.values() if v is not None]
    agree = bool(defined_signs) and len(set(defined_signs)) == 1
    return {
        "status": "ok" if agree else "definitions_disagree_or_undefined",
        "billed_pooled": _json_number(round(billed_pooled, 6) if not math.isnan(billed_pooled) else float("nan")),
        "ledger_unweighted_pooled": _json_number(
            round(ledger_pooled, 6) if not math.isnan(ledger_pooled) else float("nan")
        ),
        "mean_of_per_task_billed_ratios": _json_number(
            round(paired_mean, 6) if not math.isnan(paired_mean) else float("nan")
        ),
        "n_tasks_in_paired_mean": len(per_task),
        "n_tasks_skipped_zero_planner_baseline": skipped_zero_baseline,
        "strictly_positive": signs,
        "all_defined_agree_strictly_positive": (
            defined_signs[0] if agree else None
        ),
    }


def arm_secondary(cleaned: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    if not cleaned:
        return {"n": 0}
    asks_missing = any(row["n_asks_missing"] for row in cleaned.values())
    steps_missing = any(row["steps_missing"] for row in cleaned.values())
    n_asks = sum(row["n_asks"] for row in cleaned.values())
    n_steps = sum(row["steps"] for row in cleaned.values())
    usd_vals = [row["usd_total"] for row in cleaned.values()]
    usd_missing = any(v is None for v in usd_vals)
    n_success = sum(1 for row in cleaned.values() if row["success"])
    usd_sum = None if usd_missing else float(sum(usd_vals))  # type: ignore[arg-type]
    sgc = scenario_goal_completion(cleaned)
    return {
        "n": len(cleaned),
        "sgc": sgc,
        "n_asks_total": None if asks_missing else n_asks,
        "n_steps_total": None if steps_missing else n_steps,
        "r_ask": (
            None
            if asks_missing or steps_missing or n_steps == 0
            else round(n_asks / n_steps, 6)
        ),
        "usd_total": _json_number(usd_sum),
        "n_success": n_success,
        "usd_per_success": (
            None
            if usd_sum is None or n_success == 0
            else round(usd_sum / n_success, 6)
        ),
        "usd_per_run": (
            None if usd_sum is None else round(usd_sum / len(cleaned), 6)
        ),
        "unsafe_irreversible_violations": {
            "value": None,
            "reason": "RunResult has no such field [OBSERVED src/sidekick/protocols/schemas.py:129-145]",
        },
    }


def apply_h2_rules(
    tgc_vs_fixed_k: dict[str, Any],
    tgc_vs_sft: dict[str, Any],
    calls_vs_k5: dict[str, Any],
) -> dict[str, Any]:
    """Decision rules as written in prereg §3.2, not redesigned."""
    c1 = tgc_vs_fixed_k.get("ci95_pp")
    c2 = tgc_vs_sft.get("ci95_pp")
    c3 = calls_vs_k5.get("ci95")
    if not c1 or not c2 or not c3:
        return {"holds": None, "reason": "a contrast CI is missing", "clauses": {}}
    clause1 = {
        "rule": "ci95_pp[0] >= -7.00 against fixed_k(k_matched) [OBSERVED docs/prereg_v1.md:120]",
        "ci95_pp": c1,
        "holds": bool(c1[0] >= -NONINFERIORITY_MARGIN_PP),
    }
    clause2 = {
        "rule": "ci95_pp[0] > 0.00 against sft_plan(sft_b_plus) [OBSERVED docs/prereg_v1.md:121]",
        "ci95_pp": c2,
        "holds": bool(c2[0] > 0.00),
    }
    clause3 = {
        "rule": "ci95[1] < 0.00 calls against fixed_k(k=5) [OBSERVED docs/prereg_v1.md:122]",
        "ci95_calls": c3,
        "ci95_pp_from_paired_diff": calls_vs_k5.get("ci95_pp"),
        "holds": bool(c3[1] < 0.00),
    }
    return {
        "holds": bool(clause1["holds"] and clause2["holds"] and clause3["holds"]),
        "clauses": {"1_vs_fixed_k_k_matched": clause1, "2_vs_sft_plan": clause2, "3_calls_vs_fixed_k_5": clause3},
        "conjunctive": True,
    }


def protocol_guard(
    split: str,
    confirm: bool,
    arm_dirs: Iterable[Path],
    plumbing: bool,
) -> Optional[str]:
    if split not in SPLIT_N_TASKS:
        return f"unknown split {split!r}"
    if split in HELDOUT_TEST_SPLITS and not confirm:
        return (
            f"refusing to analyse split {split!r} without "
            "--confirm-heldout-test-split (alias "
            "--i-understand-this-is-the-single-j10-look). "
            "J10 is a single look; an accidental test run cannot be undone "
            "[OBSERVED docs/prereg_v1.md:70, 193]."
        )
    if plumbing and split in HELDOUT_TEST_SPLITS:
        return "refusing --plumbing-check on a held-out test split"
    for directory in arm_dirs:
        marker = heldout_marker_in_path(directory)
        if marker and split not in HELDOUT_TEST_SPLITS:
            return (
                f"refusing path {directory} because it contains {marker!r} "
                f"while --split={split}. Pass a held-out split and the "
                "confirmation flag if and only if this is the registered look."
            )
        if marker and split in HELDOUT_TEST_SPLITS and not confirm:
            return (
                f"refusing path {directory} containing {marker!r} without "
                "the confirmation flag"
            )
    return None


def build_report(
    *,
    split: str,
    seeds: list[int],
    arm_dirs: dict[str, Path],
    k_matched: Optional[int],
    expected_n_tasks: int,
    plumbing_check: bool,
    tau: Optional[str],
    router_tau: Optional[str],
    confirm_heldout_test_split: bool,
    partial_matrix: bool = False,
) -> tuple[dict[str, Any], int]:
    requested_arm_labels = list(arm_dirs.keys())
    if partial_matrix:
        plumbing_check = True
    proto = protocol_guard(
        split, confirm_heldout_test_split, arm_dirs.values(), plumbing_check
    )
    if proto:
        return (
            {
                "label": "REFUSED",
                "headline": proto,
                "incomplete": True,
                "hypothesis_decisions_refused": True,
                "refused": True,
                "reason": proto,
                "split": split,
            },
            2,
        )

    loaded = {label: load_arm_tree(path) for label, path in arm_dirs.items()}
    mixed = [
        label
        for label, blob in loaded.items()
        if len(blob["systems"]) > 1
    ]
    tasks = discover_tasks(loaded, seeds)
    reasons: list[str] = []
    if mixed:
        reasons.append(
            "mixed_systems_in_arm_tree:" + ",".join(f"{l}={loaded[l]['systems']}" for l in mixed)
        )
    if len(tasks) != expected_n_tasks:
        reasons.append(
            f"task_count_is_{len(tasks)}_expected_{expected_n_tasks}"
        )
    if k_matched is not None and k_matched not in K_MATCHED_ALLOWED:
        reasons.append(f"k_matched_{k_matched}_not_in_{sorted(K_MATCHED_ALLOWED)}")

    # Alias k=5 onto the matched timer arm when the caller did not pass a second tree.
    if (
        not partial_matrix
        and "fixed_k" in arm_dirs
        and "fixed_k_k5" not in arm_dirs
        and k_matched == 5
    ):
        loaded["fixed_k_k5"] = loaded["fixed_k"]
        arm_dirs = dict(arm_dirs)
        arm_dirs["fixed_k_k5"] = arm_dirs["fixed_k"]

    if not partial_matrix:
        missing_required = [name for name in REQUIRED_ARMS if name not in arm_dirs]
        if missing_required:
            reasons.append("missing_arm:" + ",".join(missing_required))
        if k_matched is not None and k_matched != 5 and "fixed_k_k5" not in arm_dirs:
            reasons.append("missing_arm:fixed_k_k5 (needed for H2 clause 3 when k_matched≠5)")
        if k_matched is None:
            reasons.append("k_matched_not_supplied (J9 parameter; cannot decide H2)")

    inventories = {
        label: inventory_arm(label, blob, tasks, seeds) for label, blob in loaded.items()
    }
    for label, inv in inventories.items():
        if not inv["complete"]:
            reasons.append(f"incomplete_arm:{label}")
        if inv["quota_stall"]:
            reasons.append(
                f"quota_stall:{label} api_error+timeout="
                f"{inv['quota_stall_frac']} > {QUOTA_STALL_FRAC}"
            )
        if len(inv["systems_in_tree"]) > 1:
            reasons.append(f"mixed_systems:{label}")

    sidekick_inv = inventories.get("sidekick")
    if sidekick_inv and sidekick_inv["cleaned"]:
        if not cluster_sizes_equal(sidekick_inv["cleaned"], len(seeds)):
            reasons.append("unequal_cluster_sizes:sidekick")

    incomplete = bool(reasons)
    decisions_refused = incomplete
    if partial_matrix:
        # Pairwise plumbing contrasts are not H1/H2. Never decide those here.
        decisions_refused = True

    missing_table = {
        label: {
            "n_expected": inv["n_expected"],
            "n_ok": inv["n_ok"],
            "n_scored_failure": inv["n_scored_failure"],
            "n_missing_run": inv["n_missing_run"],
            "n_missing_metric": inv["n_missing_metric"],
            "n_scored_failure_disagrees_with_recorded_tgc": inv[
                "n_scored_failure_disagrees_with_recorded_tgc"
            ],
            "n_empty_files": inv["n_empty_files"],
            "n_unreadable": inv["n_unreadable"],
            "n_duplicates": inv["n_duplicates"],
            "n_extra_runs_ignored": inv["n_extra_runs_ignored"],
            "n_goal_pass_rate_missing": inv["n_goal_pass_rate_missing"],
            "n_goal_pass_rate_recorded": inv["n_goal_pass_rate_recorded"],
            "complete": inv["complete"],
            "quota_stall": inv["quota_stall"],
            "error_types": inv["error_types"],
        }
        for label, inv in inventories.items()
    }

    if partial_matrix:
        label = (
            "PLUMBING CHECK, NOT A RESULT — partial matrix among named arms; "
            "these numbers are not the J10 result."
        )
        if incomplete:
            headline = "INCOMPLETE: " + "; ".join(reasons)
        else:
            headline = "PARTIAL MATRIX: pairwise contrasts among named arms only."
        headline = "PLUMBING CHECK, NOT A RESULT. " + headline
    else:
        label = (
            "PLUMBING CHECK, NOT A RESULT — dev has been inspected; these numbers "
            "are not evidence about the thesis."
            if plumbing_check
            else "J10 analysis"
        )
        if incomplete:
            headline = "INCOMPLETE: " + "; ".join(reasons)
        else:
            headline = "COMPLETE matrix; hypothesis decisions follow."
        if plumbing_check:
            headline = "PLUMBING CHECK, NOT A RESULT. " + headline

    contrasts: dict[str, Any] = {}
    hypotheses: dict[str, Any] = {
        "H2": {"status": "refused", "reason": "incomplete or unresolved input"},
        "H1": {"status": "refused", "reason": "incomplete or unresolved input"},
        "H4": {"status": "not_emitted", "reason": "see unresolved_ambiguities:h4_pvalue_and_matched_calls"},
        "H3": {
            "status": "not_a_j10_archive_quantity",
            "reason": (
                "H3 is AUROC/ECE against dev oracle labels "
                "[OBSERVED docs/prereg_v1.md:50-51, 146-147]"
            ),
        },
    }

    if partial_matrix:
        named = [n for n in requested_arm_labels if n in inventories]
        for a, b in combinations(named, 2):
            left = inventories[a]["cleaned"]
            right = inventories[b]["cleaned"]
            contrasts[f"tgc_{a}_minus_{b}"] = contrast_tgc(left, right)
            contrasts[f"goal_pass_rate_{a}_minus_{b}"] = contrast_goal_pass_rate(
                left, right
            )
    elif not decisions_refused:
        sk = inventories["sidekick"]["cleaned"]
        contrasts["tgc_sidekick_minus_fixed_k"] = contrast_tgc(
            sk, inventories["fixed_k"]["cleaned"]
        )
        contrasts["tgc_sidekick_minus_sft_plan"] = contrast_tgc(
            sk, inventories["sft_plan"]["cleaned"]
        )
        contrasts["calls_sidekick_minus_fixed_k_k5"] = contrast_calls(
            sk, inventories["fixed_k_k5"]["cleaned"]
        )
        contrasts["tgc_sidekick_minus_planner_alone"] = contrast_tgc(
            sk, inventories["planner_alone"]["cleaned"]
        )
        for name in ("executor_alone", "prompt_only", "router_seq"):
            if name in inventories and inventories[name]["complete"]:
                contrasts[f"tgc_sidekick_minus_{name}"] = contrast_tgc(
                    sk, inventories[name]["cleaned"]
                )
        contrasts["goal_pass_rate_sidekick_minus_fixed_k"] = contrast_goal_pass_rate(
            sk, inventories["fixed_k"]["cleaned"]
        )
        contrasts["goal_pass_rate_sidekick_minus_sft_plan"] = contrast_goal_pass_rate(
            sk, inventories["sft_plan"]["cleaned"]
        )
        contrasts["goal_pass_rate_sidekick_minus_planner_alone"] = (
            contrast_goal_pass_rate(sk, inventories["planner_alone"]["cleaned"])
        )
        for name in ("executor_alone", "prompt_only", "router_seq"):
            if name in inventories and inventories[name]["complete"]:
                contrasts[f"goal_pass_rate_sidekick_minus_{name}"] = (
                    contrast_goal_pass_rate(sk, inventories[name]["cleaned"])
                )
        # Refuse if paired_diff dropped anything (should be impossible here).
        # goal_pass_rate contrasts may drop missing-field cells; that is counted,
        # not a matrix refusal.
        drop_problems = []
        for cname, cmp in contrasts.items():
            if cname.startswith("goal_pass_rate_"):
                continue
            dropped = cmp.get("dropped_unmatched_keys") or {}
            if dropped.get("total"):
                drop_problems.append(cname)
            if cmp.get("n_pairs") != len(seeds) * len(tasks):
                drop_problems.append(f"{cname}:n_pairs")
        if drop_problems:
            decisions_refused = True
            reasons.append("paired_diff_dropped_or_shrank:" + ",".join(drop_problems))
            headline = (
                ("PLUMBING CHECK, NOT A RESULT. " if plumbing_check else "")
                + "INCOMPLETE: "
                + "; ".join(reasons)
            )
        else:
            h2 = apply_h2_rules(
                contrasts["tgc_sidekick_minus_fixed_k"],
                contrasts["tgc_sidekick_minus_sft_plan"],
                contrasts["calls_sidekick_minus_fixed_k_k5"],
            )
            hypotheses["H2"] = {
                "status": "decided",
                "holds": h2["holds"],
                "detail": h2,
                "note": (
                    "Three-clause form in docs/prereg_v1.md; RUNS.md H2a/H2b "
                    "replacement is listed under unresolved_ambiguities and is "
                    "not applied."
                ),
            }
            h1_tgc = contrasts["tgc_sidekick_minus_planner_alone"]
            h1_tgc_holds = bool(
                h1_tgc.get("ci95_pp") and h1_tgc["ci95_pp"][0] >= -NONINFERIORITY_MARGIN_PP
            )
            fcd = fcd_bundle(sk, inventories["planner_alone"]["cleaned"])
            fcd_pos = fcd.get("all_defined_agree_strictly_positive")
            if fcd.get("status") != "ok" or fcd_pos is None:
                hypotheses["H1"] = {
                    "status": "refused",
                    "reason": "FCD definition disagreement or undefined token totals",
                    "tgc_noninferiority": {
                        "rule": "ci95_pp[0] >= -7.00 vs planner_alone [OBSERVED docs/prereg_v1.md:46]",
                        "ci95_pp": h1_tgc.get("ci95_pp"),
                        "holds": h1_tgc_holds,
                    },
                    "fcd_tokens": fcd,
                    "holds": None,
                }
            else:
                hypotheses["H1"] = {
                    "status": "decided",
                    "tgc_noninferiority": {
                        "rule": "ci95_pp[0] >= -7.00 vs planner_alone [OBSERVED docs/prereg_v1.md:46]",
                        "ci95_pp": h1_tgc.get("ci95_pp"),
                        "holds": h1_tgc_holds,
                    },
                    "fcd_tokens": fcd,
                    "holds": bool(h1_tgc_holds and fcd_pos),
                    "note": "Secondary; reported whatever it shows [OBSERVED docs/prereg_v1.md:47].",
                }
            if "router_seq" in inventories:
                hypotheses["H4"] = {
                    "status": "contrast_only",
                    "tgc_contrast": contrasts.get("tgc_sidekick_minus_router_seq"),
                    "sidekick_planner_calls_mean": inventories["sidekick"]["planner_calls_mean"],
                    "router_seq_planner_calls_mean": inventories["router_seq"]["planner_calls_mean"],
                    "holds": None,
                    "reason": (
                        "No p-value in paired_diff; 'matched calls' is a J9 "
                        "calibration. See unresolved_ambiguities."
                    ),
                }
            else:
                hypotheses["H4"] = {
                    "status": "arm_absent",
                    "reason": "router_seq is optional [OBSERVED docs/prereg_v1.md:86]",
                    "holds": None,
                }

    public_arms = {}
    for label_arm, inv in inventories.items():
        public_arms[label_arm] = {
            k: v
            for k, v in inv.items()
            if k not in {"cleaned", "disagreements", "empty_files", "unreadable", "duplicates", "extra_runs_ignored", "_extra_keys", "n_cells_shown_in_detail"}
        }
        public_arms[label_arm]["disagreements_n"] = len(inv["disagreements"])
        public_arms[label_arm]["secondary"] = arm_secondary(inv["cleaned"])

    report: dict[str, Any] = {
        "label": label,
        "headline": headline,
        "incomplete": incomplete,
        "incomplete_reasons": reasons,
        "hypothesis_decisions_refused": decisions_refused,
        "split": split,
        "plumbing_check": plumbing_check,
        "partial_matrix": partial_matrix,
        "named_arms": requested_arm_labels,
        "not_the_j10_result": bool(partial_matrix or plumbing_check),
        "resample_unit": RESAMPLE_UNIT,
        "resample_unit_justification": RESAMPLE_JUSTIFICATION,
        "bootstrap": {"n": BOOTSTRAP, "seed": SEED, "source": "scripts/setup/hj1_gate.py"},
        "j9_parameters": {
            "k_matched": k_matched,
            "tau": tau,
            "router_tau": router_tau,
            "note": "These are frozen on dev at J9 and are inputs here, not estimated [OBSERVED docs/prereg_v1.md:219-231].",
        },
        "expected": {
            "n_tasks": expected_n_tasks,
            "n_tasks_observed_union": len(tasks),
            "seeds": seeds,
            "n_cells_per_arm": expected_n_tasks * len(seeds),
        },
        "missing_and_crashed": missing_table,
        "arms": public_arms,
        "contrasts": contrasts,
        "hypotheses": hypotheses,
        "secondary_not_computed_from_j10_archives": {
            "H3_auroc_ece": "dev oracle labels, not J10 [OBSERVED docs/prereg_v1.md:50-51]",
            "f_dev": "Gate B / J6 on dev [OBSERVED docs/prereg_v1.md:52-53, 148-149]",
            "unsafe_irreversible_violations": "no RunResult field [OBSERVED src/sidekick/protocols/schemas.py:129-145]",
        },
        "unresolved_ambiguities": UNRESOLVED_AMBIGUITIES,
        "none_means_not_measured": (
            "tgc None with error_type not in "
            f"{sorted(SCORED_FAILURE_TYPES)} is a missing metric and is never "
            "averaged as 0 [OBSERVED src/sidekick/protocols/schemas.py:35-37]. "
            "goal_pass_rate missing or null is dropped from the goal-pass "
            "contrast and counted, never read as 0.0 "
            "[OBSERVED src/sidekick/protocols/schemas.py:139]."
        ),
    }
    exit_code = 1 if report["hypothesis_decisions_refused"] else 0
    return report, exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--split",
        required=True,
        choices=sorted(SPLIT_N_TASKS),
        help="Must be passed explicitly. test_normal/test_challenge require --confirm-heldout-test-split.",
    )
    p.add_argument(
        "--confirm-heldout-test-split",
        "--i-understand-this-is-the-single-j10-look",
        dest="confirm_heldout_test_split",
        action="store_true",
        help="Required to analyse test_normal or test_challenge. J10 runs once.",
    )
    p.add_argument(
        "--seeds",
        required=True,
        help="Comma-separated seed list for the registered matrix, e.g. 1,2,3. No default: guessing 3 on a 2-seed dry-run would mark every arm incomplete.",
    )
    p.add_argument(
        "--expected-n-tasks",
        type=int,
        default=None,
        help="Defaults to the measured split size (dev 57, test_normal 168, ...).",
    )
    p.add_argument(
        "--arm",
        action="append",
        required=True,
        metavar="LABEL=DIR",
        help="Arm results directory (campaign root or system subdirectory). Repeatable.",
    )
    p.add_argument(
        "--k-matched",
        type=int,
        default=None,
        help="J9-frozen k in {3,5,10} or 7 on the registered tie. Required to decide H2.",
    )
    p.add_argument("--tau", default=None, help="J9-frozen sidekick τ* (label only).")
    p.add_argument("--router-tau", default=None, help="J9-frozen router τ* (label only).")
    p.add_argument(
        "--plumbing-check",
        action="store_true",
        help="Stamp the report as a plumbing check, not a result. Required for any pre-J10 dry-run.",
    )
    p.add_argument(
        "--partial-matrix",
        action="store_true",
        help=(
            "Inventory only the named --arm labels and emit pairwise TGC and "
            "goal_pass_rate contrasts. Not the J10 result. Always stamps "
            "PLUMBING CHECK, NOT A RESULT. Does not relax the default "
            "full-matrix missing_arm / k_matched_not_supplied refusals."
        ),
    )
    p.add_argument("--out", default=None, help="Write the JSON report here.")
    return p


def main_v1(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        arm_dirs = parse_arm_specs(args.arm)
        seeds = parse_seeds(args.seeds)
    except ValueError as exc:
        print(json.dumps({"refused": True, "reason": str(exc)}, indent=2), file=sys.stderr)
        print(json.dumps({"refused": True, "headline": str(exc), "reason": str(exc)}, indent=2))
        return 2
    expected = args.expected_n_tasks
    if expected is None:
        expected = SPLIT_N_TASKS[args.split]
    report, code = build_report(
        split=args.split,
        seeds=seeds,
        arm_dirs=arm_dirs,
        k_matched=args.k_matched,
        expected_n_tasks=expected,
        plumbing_check=args.plumbing_check,
        tau=args.tau,
        router_tau=args.router_tau,
        confirm_heldout_test_split=args.confirm_heldout_test_split,
        partial_matrix=args.partial_matrix,
    )
    text = json.dumps(report, indent=2, default=str) + "\n"
    print(text, end="")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    return code


# ===========================================================================
# A1 protocol -- docs/prereg_j10_amendment_20260924.md r2 §5-§6 (the J10 default).
# Every `A1_PREREG:<lines>` citation below is to the r2 text; r1 text is cited
# as A1_PREREG_R1 (the file at commit a8532b2, before r2 rewrote it).
#
# Everything above this line is the prereg_v1 (J9-era, H1-H4) analysis. It is
# kept verbatim because j8_frontier / hj12_shape / j12_cost_axes import its
# loaders and contrast helpers, and is reachable as `--protocol v1`. A1
# supersedes that arm list and those hypotheses [A1 §2]; `main()` now runs A1
# unless `--protocol v1` is passed.
#
# Registered here, before the read:
#   * paired on (task_id, seed); a pair missing or crashed on either side is
#     dropped from that contrast and counted [A1 §5.1, lines 201-210];
#   * percentile cluster bootstrap, B = 10,000, seed 20260924; scenario
#     clustering is PRIMARY and governs every decision, task clustering is
#     reported beside it [A1 §5.2, lines 214-219];
#   * the resampling algorithm is hj1_gate.paired_diff / j8_frontier.
#     paired_diff_scenario draw-for-draw (same RNG consumption, same percentile
#     indices), with the seed exposed -- j8_frontier hard-codes hj1_gate.SEED =
#     20260915, the seed of every A1 dev number not marked otherwise [A1 §5.2 F2,
#     lines 220-222];
#   * predictions are DATA (A1_PREDICTIONS); decision rules are a small table
#     (A1_RULES) the data refers to by name, so P7 is a list entry;
#   * Holm across the goal_pass predictions flagged holm_family=True -- those whose
#     support needs a rejection: P1, P3, P4, P6 and any P7 component [A1 §5.3, lines 230-231];
#   * POOL-04 boundary-stability rule [A1 §5.4]; a cluster sign-flip permutation p
#     is reported beside each verdict and is not decision-bearing [A1 §5.5].
# ===========================================================================

import bisect  # noqa: E402
import importlib.util  # noqa: E402
import random  # noqa: E402

from scripts.setup.hj1_gate import scenario_of  # noqa: E402

A1_PREREG = "docs/prereg_j10_amendment_20260924.md"
# r1, as the ambiguity records below found it. r2 rewrote the file, so r1 line numbers
# resolve only against this commit.
A1_PREREG_R1 = "docs/prereg_j10_amendment_20260924.md@a8532b2"
A1_DEV_BASIS = "campaign/results/j10_a1_registered_dev_basis_20260924.report.json"
A1_BOOTSTRAP_N = 10_000
A1_BOOTSTRAP_SEED = 20260924
DEV_BASIS_BOOTSTRAP_SEED = SEED  # 20260915 [scripts/setup/hj1_gate.py:29]
A1_ALPHA = 0.05
A1_SPLIT_N_TASKS = {"dev": 57, "test_normal": 168}
A1_DEFAULT_SEEDS = "1,2"
POOL04_WINDOW_PP = 1.00
POOL04_SEEDS = (20260924, 1, 2, 3, 7, 101, 999)
PERMUTATION_N = 10_000
CLUSTER_INFERENCE_PATH = Path(__file__).resolve().parent / "cluster_inference.py"
RAW_RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")

# Registered arms [A1 r2 §4: 1, 1b, 2-12]. The value is the config that produces the
# arm (None: no J10 config exists yet); its campaign id is j10_<label>_20260924. The
# labels are what --arm accepts, so an arm missing here cannot be reported unless a
# prediction names it -- which executor_alone_bplus (1b) and, until P7 is completed
# at freeze, show_k10 (11) and advise_k10_neutral (12) do not.
A1_ARMS: dict[str, Optional[str]] = {
    "executor_alone": "configs/j10_executor_alone.yaml",
    "executor_alone_bplus": "configs/j10_executor_alone_bplus.yaml",
    "sft_plan": "configs/j10_sft_plan.yaml",
    "planner_alone_cap81": "configs/j10_planner_alone_cap81.yaml",
    "prefix_m9": "configs/j10_prefix_m9.yaml",
    "prefix_m11": "configs/j10_prefix_m11.yaml",
    "prefix_zs_m9": "configs/j10_prefix_zs_m9.yaml",
    "prefix_zs_m11": "configs/j10_prefix_zs_m11.yaml",
    "advise_k1_fullctx": "configs/j10_advise_k1_fullctx.yaml",
    "advise_k10_fullctx": "configs/j10_advise_k10_fullctx.yaml",
    "takeover_k10": "configs/j10_takeover_k10.yaml",
    "show_k10": "configs/j10_show_k10.yaml",
    "advise_k10_neutral": "configs/j10_advise_k10_neutral.yaml",
}

A1_METRIC_FIELDS = {"goal_pass": "goal_pass_rate", "tgc": "tgc"}


# ---- decision rules (code), referenced by name from the prediction data -----
def _rule_negative_with_reversal(point: float, lo_above: bool, hi_below: bool) -> str:
    if hi_below:
        return "supported"
    if lo_above:
        return "reversed"
    return "not_supported"


def _rule_lower_bound_above(point: float, lo_above: bool, hi_below: bool) -> str:
    return "supported" if lo_above else "not_supported"


def _rule_positive_graded(point: float, lo_above: bool, hi_below: bool) -> str:
    if lo_above:
        return "supported"
    if point > 0:
        return "directionally_consistent"
    return "not_supported"


def _rule_not_positive_excluding(point: float, lo_above: bool, hi_below: bool) -> str:
    return "not_supported" if lo_above else "supported"


# `bounds`: the interval ends whose position against the threshold can change the
# verdict -- the ones POOL-04 re-checks. `direction`: the alternative the
# bootstrap p (and hence Holm) is computed for.
A1_RULES: dict[str, dict[str, Any]] = {
    "negative_excludes_zero_with_reversal": {
        "decide": _rule_negative_with_reversal,
        "bounds": ("hi", "lo"),
        "direction": "two-sided",
        "text": "supported if CI hi < t; reversed if CI lo > t; else not_supported",
    },
    "lower_bound_above_threshold": {
        "decide": _rule_lower_bound_above,
        "bounds": ("lo",),
        "direction": "greater",
        "text": "supported if CI lo > t; else not_supported",
    },
    "positive_graded": {
        "decide": _rule_positive_graded,
        "bounds": ("lo",),
        "direction": "greater",
        "text": (
            "supported if CI lo > t; directionally_consistent if point > t and CI "
            "includes t; else not_supported"
        ),
    },
    "not_positive_excluding_zero": {
        "decide": _rule_not_positive_excluding,
        "bounds": ("lo",),
        "direction": "greater",
        "text": "not_supported if CI lo > t; else supported",
    },
    "cost_ratio_at_least": {
        "decide": None,
        "bounds": (),
        "direction": None,
        "text": "supported if left/right tokens >= min_ratio AND left calls > right calls",
    },
}

# ---- the registered predictions, as data ------------------------------------
A1_PREDICTIONS: list[dict[str, Any]] = [
    {
        "id": "P1",
        "role": "primary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "advise_k1_fullctx",
        "right": "prefix_m11",
        "rule": "negative_excludes_zero_with_reversal",
        "threshold_pp": 0.0,
        "holm_family": True,
        "statement": "advise_k1_fullctx − prefix_m11 on goal_pass is negative, CI excluding zero",
        "citation": f"{A1_PREREG}:274-284",
        "dev_reference": {
            "diff_pp": -14.81,
            "ci95_pp_scenario": [-21.20, -7.96],
            "ci95_pp_task": [-21.73, -8.02],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_advise_k1_minus_c81_bp_m11",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
    {
        "id": "P2",
        "role": "primary",
        "kind": "cost_ratio",
        "metric": "noncached_tokens_per_episode",
        "left": "advise_k1_fullctx",
        "right": "prefix_m11",
        "rule": "cost_ratio_at_least",
        "min_ratio": 2.0,
        "tokens_field": "noncached_tokens_per_episode",
        "calls_field": "hosted_calls_per_episode",
        "holm_family": False,
        "statement": (
            "advise_k1_fullctx spends >= 2x the non-cached planner tokens of prefix_m11 "
            "and strictly more hosted calls per episode"
        ),
        "citation": f"{A1_PREREG}:286-307",
        "notes": (
            "Read from a scripts/analysis/j12_cost_axes.py report over the J10 arms "
            "(--cost-report), whose prefix arms are costed at their attributed source "
            "steps. Run j12 with --packet-source pointed at the J10 arm-3 campaign, not "
            "its hj1b default. If not supported, P1 is uninterpretable as a channel "
            "result [A1:306-307]."
        ),
        "dev_reference": {
            "ratio": 3.19,
            "left_tokens_per_episode": 1414410.035088,
            "right_tokens_per_episode": 443361.412281,
            "left_calls_per_episode": 19.017544,
            "right_calls_per_episode": 11.254386,
            "source": "campaign/results/hj13_advice_at_price_cost_20260923.report.json",
        },
    },
    {
        "id": "P3",
        "role": "secondary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "prefix_m11",
        "right": "planner_alone_cap81",
        "rule": "lower_bound_above_threshold",
        "threshold_pp": -7.00,
        "holm_family": True,
        "statement": "prefix_m11 − planner_alone_cap81 on goal_pass has CI lower bound above −7.00 pp",
        "citation": f"{A1_PREREG}:309-330",
        "dev_reference": {
            "diff_pp": 4.75,
            "ci95_pp_scenario": [-1.16, 11.75],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_ceiling_c81_minus_c81_bp_m11 (negated here; A1 r2 quotes it stored, −4.75 [−11.75, +1.16], A1:315-316)",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
    {
        "id": "P4",
        "role": "secondary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "prefix_zs_m11",
        "right": "prefix_zs_m9",
        "rule": "positive_graded",
        "threshold_pp": 0.0,
        "holm_family": True,
        "statement": "prefix_zs_m11 − prefix_zs_m9 on goal_pass is positive (registered underpowered)",
        "citation": f"{A1_PREREG}:332-348",
        "dev_reference": {
            "diff_pp": 2.82,
            "ci95_pp_scenario": [-1.55, 7.16],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_c81_zs_m9_minus_c81_zs_m11 (stored −2.82 [−7.16, +1.55]; negated here, as r1 did silently -- A1 r2 quotes it stored, A1:339-340)",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
    {
        "id": "P5",
        "role": "secondary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "advise_k1_fullctx",
        "right": "sft_plan",
        "rule": "not_positive_excluding_zero",
        "threshold_pp": 0.0,
        # A1 r2 §5.3: outside the Holm family. P5 is SUPPORTED by a non-rejection, so a Holm
        # adjustment would make it easier to support; it is judged on the unadjusted interval.
        "holm_family": False,
        "statement": "advise_k1_fullctx − sft_plan on goal_pass is NOT positive with a CI excluding zero",
        "citation": f"{A1_PREREG}:350-362",
        "dev_reference": {
            "diff_pp": -5.51,
            "ci95_pp_scenario": [-13.15, 2.51],
            "source": "campaign/results/hj13_advice_at_price_20260923.report.json",
            "key": "contrasts.goal_pass_all_advise_k1_fullctx_minus_plan_floor",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
    {
        "id": "P6",
        "role": "primary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "takeover_k10",
        "right": "advise_k10_fullctx",
        "rule": "lower_bound_above_threshold",
        "threshold_pp": 0.0,
        "holm_family": True,
        "statement": "takeover_k10 − advise_k10_fullctx on goal_pass is positive, 95% scenario CI excluding zero",
        "citation": f"{A1_PREREG}:364-381",
        "dev_reference": {
            "diff_pp": 6.69,
            "ci95_pp_scenario": [1.29, 13.48],
            "source": "caller brief 2026-09-23; j8_frontier at seed 20260915 gives [1.29, 13.49]",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
]

# A1 §6 "Supporting contrasts, registered but not decision-bearing" [A1:412-426].
# r2's table differs from this list; see the supporting_contrasts_differ_from_r2
# record below. The list is left as it was: which contrasts are registered is the
# freeze's decision, not this script's.
A1_SUPPORTING: list[dict[str, Any]] = [
    {"id": "S1", "left": "advise_k1_fullctx", "right": "prefix_m9",
     "dev_reference": {"diff_pp": -9.89, "ci95_pp_scenario": [-17.79, -1.99]}},
    {"id": "S2", "left": "advise_k10_fullctx", "right": "prefix_m11",
     "dev_reference": {"diff_pp": -7.73, "ci95_pp_scenario": [-12.60, -3.12]}},
    {"id": "S3", "left": "prefix_m9", "right": "prefix_m11",
     "dev_reference": {"diff_pp": -4.92, "ci95_pp_scenario": [-10.36, 0.43]}},
    {"id": "S4", "left": "planner_alone_cap81", "right": "prefix_zs_m11",
     "dev_reference": {"diff_pp": -2.95, "ci95_pp_scenario": [-8.65, 1.91]}},
]

# Records of where A1's text and this script had to meet. `status` is
# "resolved_by_r2" when r2 now says what the script does (the r1 text that raised it
# is cited at A1_PREREG_R1), and "open" when r2 says something the script does not
# yet do -- reported, not changed, since the statistics are frozen with the text.
# r1's `p6_arm_not_registered` is gone: r2 registers arm 10 and P6 [A1:131, 135, 364-381].
A1_AMBIGUITIES: list[dict[str, Any]] = [
    {
        "id": "bootstrap_seed_of_dev_references",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:219-222", f"{A1_PREREG_R1}:157", "scripts/setup/hj1_gate.py:29",
                      "scripts/analysis/j8_frontier.py:55-59,1184"],
        "what": (
            "r1 fixed bootstrap seed 20260924 without saying that its dev intervals were "
            "produced by j8_frontier, which always uses hj1_gate.SEED = 20260915. r2 §5.2 "
            "(F2) states it: dev values are at 20260915 unless marked."
        ),
        "script_behaviour": (
            "Test verdicts use 20260924. dev_reference blocks carry the 20260915 seed "
            "they were computed under; the regression test reproduces P1 at 20260915."
        ),
    },
    {
        "id": "negated_dev_references",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:201-202", f"{A1_PREREG}:315-318", f"{A1_PREREG}:339-340",
                      f"{A1_PREREG_R1}:219-222", f"{A1_PREREG_R1}:233-234"],
        "what": (
            "r1 quoted P3 and P4 intervals obtained by negating the stored contrast, and for "
            "P4 without saying so. Under the percentile convention (lo = means[250], hi = "
            "means[9750]) negation is not exactly the direct interval: one end moves by one "
            "order statistic (≈0.01 pp). r2 (F4) quotes both in their stored orientation and "
            "registers direct computation in the registered orientation."
        ),
        "script_behaviour": (
            "Every contrast is computed directly in the registered orientation (left − right). "
            "The P3 / P4 dev_reference blocks still hold the negated 114-pair values, labelled so."
        ),
    },
    {
        "id": "holm_family_size",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:230-231", f"{A1_PREREG}:238-242", f"{A1_PREREG_R1}:164"],
        "what": (
            "r1 §5.3 applied Holm 'across the five predictions on goal_pass', but P2 is a "
            "cost predicate, so P1-P5 contain four goal_pass predictions."
        ),
        "script_behaviour": (
            "Resolved by A1 r2 §5.3: family = the goal_pass predictions whose support needs a "
            "rejection (P1, P3, P4, P6 → m = 4, plus any registered P7 component). P2 (cost) "
            "and P5 (support by non-rejection) are outside it."
        ),
    },
    {
        "id": "holm_vs_ci_rules",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:232-237", f"{A1_PREREG}:240-242", f"{A1_PREREG_R1}:164"],
        "what": (
            "r1's decision rules were CI conditions while Holm needs p-values; r1 did not say "
            "how the two combine, nor that for P5 a Holm adjustment makes 'supported' EASIER "
            "(its support event is a non-rejection). r2 §5.3 (F3) registers both, as below."
        ),
        "script_behaviour": (
            "p = two-sided-equivalent percentile-bootstrap p for the rule's direction at "
            "its threshold (2 x tail share of the scenario-clustered bootstrap means). An "
            "exclusion event counts only if the CI excludes the threshold AND the Holm-"
            "adjusted p <= 0.05. Unadjusted and adjusted verdicts are both reported."
        ),
    },
    {
        "id": "residual_crash_scoring",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:207-210", f"{A1_PREREG}:488-490",
                      f"{A1_PREREG_R1}:148-149", f"{A1_PREREG_R1}:352-355",
                      "scripts/analysis/j8_frontier.py:419-430"],
        "what": (
            "r1 required 336 non-crashed pairs per arm but did not say how a crash left in "
            "the tree is scored; the dev basis used j8's all-episodes view (crash = 0), with "
            "zero crashes, so the choice never mattered on dev. r2 §5.1 (F6): a residual crash "
            "removes the pair from every contrast and leaves the arm incomplete."
        ),
        "script_behaviour": (
            "A crashed episode is not an outcome: it is dropped from every pair and counted, "
            "and an arm with any crash or missing episode is incomplete, which refuses every "
            "prediction that uses it."
        ),
    },
    {
        "id": "p6_has_no_reversed_outcome",
        "status": "open",
        "citations": [f"{A1_PREREG}:374-378"],
        "what": "r2 registers three P6 outcomes: supported, not supported, and reversed (withdrawn).",
        "script_behaviour": (
            "P6 uses lower_bound_above_threshold, which returns supported or not_supported; "
            "an interval entirely below zero is reported as not_supported, never reversed."
        ),
    },
    {
        "id": "p2_ratio_interval_not_reported",
        "status": "open",
        "citations": [f"{A1_PREREG}:238-239", f"{A1_PREREG}:291"],
        "what": "r2 reports P2's token ratio with its scenario-clustered interval beside the point verdict.",
        "script_behaviour": "a1_evaluate_cost_prediction reports the point ratio and calls only; no interval.",
    },
    {
        "id": "pool04_200k_bound_not_computed",
        "status": "open",
        "citations": [f"{A1_PREREG}:248-253"],
        "what": (
            "r2 §5.4 recomputes a near-threshold bound at seven seeds AND at 200,000 "
            "resamples at 20260924, and reports the 200k bound with the seven."
        ),
        "script_behaviour": "a1_pool04 recomputes the seven seeds only.",
    },
    {
        "id": "permutation_p_differs_from_r2",
        "status": "open",
        "citations": [f"{A1_PREREG}:260-263", "scripts/analysis/cluster_inference.py:137"],
        "what": (
            "r2 §5.5: exact if the scenario count gives <= 2^20 sign patterns, otherwise Monte "
            "Carlo over 100,000 patterns at seed 20260924; one-sided at the threshold for P3."
        ),
        "script_behaviour": (
            f"a1_permutation passes n_perm = {PERMUTATION_N} and alternative='two-sided' for "
            "every prediction, so it enumerates exactly only up to 2^13 patterns and P3 is "
            "two-sided. Not decision-bearing under either text."
        ),
    },
    {
        "id": "supporting_contrasts_differ_from_r2",
        "status": "open",
        "citations": [f"{A1_PREREG}:414-421", f"{A1_PREREG}:201-202"],
        "what": (
            "r2's table: advise_k1 − prefix_m9; advise_k10 − prefix_m11; prefix_m11 − prefix_m9 "
            "(tailored depth); the tailoring x depth DiD (R2); prefix_m11 − executor_alone_bplus; "
            "handoff-only depth for both receivers."
        ),
        "script_behaviour": (
            "A1_SUPPORTING is S1 and S2 as r2, S3 = prefix_m9 − prefix_m11 (the reverse of r2's "
            "orientation), and S4 = planner_alone_cap81 − prefix_zs_m11, which r2 does not list. "
            "The DiD, the 1b row and handoff-only depth are not computed."
        ),
    },
]


# ---- loading ----------------------------------------------------------------
def a1_split_provenance(root: Path) -> dict[str, int]:
    """Count episodes by the split their manifest.json recorded (A1 §10.2)."""
    counts: Counter[str] = Counter()
    if not root.exists():
        return {}
    for path in sorted(root.rglob("result.json")):
        man = path.parent / "manifest.json"
        split: Optional[str] = None
        if man.exists():
            try:
                prov = (json.loads(man.read_text(encoding="utf-8")) or {}).get("provenance")
                if isinstance(prov, dict) and prov.get("split") is not None:
                    split = str(prov["split"])
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                split = None
        counts[split or "unrecorded"] += 1
    return dict(sorted(counts.items()))


def a1_arm_episodes(
    label: str,
    loaded: dict[str, Any],
    tasks: list[str],
    seeds: list[int],
) -> dict[str, Any]:
    """Scored episodes of one arm over the registered (task, seed) matrix.

    A crash is not an outcome and is excluded; every other readable result
    (including limit / timeout / parse_error) is scored. None metrics are kept
    as None and dropped per contrast, never coerced to 0.
    """
    runs: dict[tuple[str, int], dict[str, Any]] = loaded["runs"]
    task_set, seed_set = set(tasks), set(seeds)
    episodes: dict[tuple[str, int], dict[str, Any]] = {}
    n_missing = n_crash = 0
    for task_id in tasks:
        for seed in seeds:
            row = runs.get((task_id, seed))
            if row is None:
                n_missing += 1
                continue
            if row.get("error_type") == "crash":
                n_crash += 1
                continue
            episodes[(task_id, seed)] = {
                "goal_pass_rate": optional_float(row, "goal_pass_rate"),
                "tgc": score_tgc(row)["tgc"],
                "error_type": row.get("error_type"),
            }
    n_expected = len(tasks) * len(seeds)
    in_matrix = [k for k in runs if k[0] in task_set and k[1] in seed_set]
    gp = [e["goal_pass_rate"] for e in episodes.values() if e["goal_pass_rate"] is not None]
    tg = [e["tgc"] for e in episodes.values() if e["tgc"] is not None]
    complete = (
        n_missing == 0
        and n_crash == 0
        and len(episodes) == n_expected
        and not loaded["empty_files"]
        and not loaded["unreadable"]
        and not loaded["duplicates"]
        and not loaded["root_missing"]
    )
    return {
        "label": label,
        "episodes": episodes,
        "n_expected": n_expected,
        "n_scored": len(episodes),
        "n_crash": n_crash,
        "n_missing": n_missing,
        "n_extra_ignored": len(runs) - len(in_matrix),
        "n_empty_files": len(loaded["empty_files"]),
        "n_unreadable": len(loaded["unreadable"]),
        "n_duplicates": len(loaded["duplicates"]),
        "root_missing": loaded["root_missing"],
        "systems_in_tree": sorted(loaded["systems"]),
        "error_types": dict(
            sorted(Counter(str(runs[k].get("error_type") or "none") for k in in_matrix).items())
        ),
        "goal_pass_mean": round(statistics.fmean(gp), 6) if gp else None,
        "n_goal_pass_missing": len(episodes) - len(gp),
        "tgc_mean": round(statistics.fmean(tg), 6) if tg else None,
        "complete": complete,
    }


# ---- bootstrap --------------------------------------------------------------
def cluster_bootstrap_means(
    diffs: list[float],
    clusters: list[str],
    *,
    n_boot: int = A1_BOOTSTRAP_N,
    seed: int = A1_BOOTSTRAP_SEED,
) -> list[float]:
    """Sorted bootstrap means, clusters drawn with replacement.

    Draw-for-draw the algorithm of hj1_gate._draw_task_clusters and
    j8_frontier.paired_diff_scenario: clusters sorted by label, one
    random.Random(seed), G draws of randrange(G) per replicate, and the mean of
    the concatenated values (sum / len, in draw order).
    """
    by_cluster: dict[str, list[float]] = {}
    for diff, cluster in zip(diffs, clusters):
        by_cluster.setdefault(cluster, []).append(diff)
    labels = sorted(by_cluster)
    n_clusters = len(labels)
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [
            value
            for label in (labels[rng.randrange(n_clusters)] for _ in range(n_clusters))
            for value in by_cluster[label]
        ]
        means.append(sum(sampled) / len(sampled))
    means.sort()
    return means


def percentile_ci(means: list[float]) -> tuple[float, float]:
    n = len(means)
    return means[int(0.025 * n)], means[int(0.975 * n)]


def bootstrap_pvalue(means: list[float], threshold: float, direction: str) -> float:
    """Two-sided-equivalent percentile p at `threshold` (native units).

    greater: evidence the effect exceeds t   -> 2 x share of means <= t
    less:    evidence the effect is below t   -> 2 x share of means >= t
    two-sided: 2 x the smaller tail. Capped at 1. Consistent with the 95%
    percentile CI: the CI excludes t (on that side) iff p <= 0.05, up to one
    order statistic at the boundary.
    """
    n = len(means)
    share_le = bisect.bisect_right(means, threshold) / n
    share_ge = (n - bisect.bisect_left(means, threshold)) / n
    if direction == "greater":
        p = 2.0 * share_le
    elif direction == "less":
        p = 2.0 * share_ge
    elif direction == "two-sided":
        p = 2.0 * min(share_le, share_ge)
    else:
        raise ValueError(f"unknown direction {direction!r}")
    return min(1.0, p)


def holm_adjust(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in input order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: (pvalues[i], i))
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[idx]))
        adjusted[idx] = running
    return adjusted


def a1_paired_series(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    field: str,
) -> dict[str, Any]:
    shared = sorted(set(left) & set(right))
    keys: list[tuple[str, int]] = []
    diffs: list[float] = []
    missing = 0
    for key in shared:
        a, b = left[key].get(field), right[key].get(field)
        if a is None or b is None:
            missing += 1
            continue
        keys.append(key)
        diffs.append(float(a) - float(b))
    return {
        "keys": keys,
        "diffs": diffs,
        "n_shared": len(shared),
        "n_left_only": len(left) - len(shared),
        "n_right_only": len(right) - len(shared),
        "n_dropped_missing_field": missing,
    }


def _cluster_labels(keys: list[tuple[str, int]], clustering: str) -> list[str]:
    if clustering == "scenario":
        return [scenario_of(k[0]) for k in keys]
    if clustering == "task":
        return [k[0] for k in keys]
    raise ValueError(f"unknown clustering {clustering!r}")


def a1_interval(
    series: dict[str, Any],
    clustering: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """One clustered interval. `_means` is internal (stripped before output)."""
    diffs = series["diffs"]
    if not diffs:
        return {"clustering": clustering, "n_pairs": 0, "point": None, "lo": None,
                "hi": None, "diff_pp": None, "ci95_pp": None, "n_clusters": 0}
    clusters = _cluster_labels(series["keys"], clustering)
    means = cluster_bootstrap_means(diffs, clusters, n_boot=n_boot, seed=seed)
    lo, hi = percentile_ci(means)
    point = statistics.fmean(diffs)
    return {
        "clustering": clustering,
        "n_pairs": len(diffs),
        "n_clusters": len(set(clusters)),
        "point": point,
        "lo": lo,
        "hi": hi,
        "diff_pp": round(point * 100, 2),
        "ci95_pp": [round(lo * 100, 2), round(hi * 100, 2)],
        "n_boot": n_boot,
        "seed": seed,
        "_means": means,
    }


def _public(block: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in block.items() if not k.startswith("_")}


def a1_contrast(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    field: str,
    *,
    n_boot: int = A1_BOOTSTRAP_N,
    seed: int = A1_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Paired contrast left − right: scenario (primary) and task intervals."""
    series = a1_paired_series(left, right, field)
    return {
        "field": field,
        "n_pairs": len(series["diffs"]),
        "n_shared": series["n_shared"],
        "n_left_only": series["n_left_only"],
        "n_right_only": series["n_right_only"],
        "n_dropped_missing_field": series["n_dropped_missing_field"],
        "scenario": a1_interval(series, "scenario", n_boot=n_boot, seed=seed),
        "task": a1_interval(series, "task", n_boot=n_boot, seed=seed),
        "_series": series,
    }


def _public_contrast(cmp: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in cmp.items() if not k.startswith("_")}
    for name in ("scenario", "task"):
        if isinstance(out.get(name), dict):
            out[name] = _public(out[name])
    return out


def _load_cluster_signflip():
    """Lazy import of cluster_signflip_pvalue (owned by another unit).

    Contract: cluster_signflip_pvalue(diffs, clusters, *, n_perm=10000,
    seed=20260924, alternative="two-sided") -> float. Returns None if absent.
    """
    if not CLUSTER_INFERENCE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("cluster_inference", CLUSTER_INFERENCE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "cluster_signflip_pvalue", None)


def a1_permutation(series: dict[str, Any], threshold: float) -> dict[str, Any]:
    """Scenario-cluster sign-flip p for H0: effect == threshold. Not decision-bearing."""
    base = {
        "decision_bearing": False,
        "clusters": "scenario",
        "null": "paired differences symmetric about the threshold",
        "n_perm": PERMUTATION_N,
        "seed": A1_BOOTSTRAP_SEED,
        "alternative": "two-sided",
    }
    if not series["diffs"]:
        return {**base, "status": "no_pairs", "p_value": None}
    try:
        fn = _load_cluster_signflip()
    except Exception as exc:  # the module is written concurrently; never fatal
        return {**base, "status": "import_error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    if fn is None:
        return {**base, "status": "unavailable", "p_value": None,
                "reason": f"{CLUSTER_INFERENCE_PATH.name} or cluster_signflip_pvalue absent"}
    shifted = [d - threshold for d in series["diffs"]]
    clusters = _cluster_labels(series["keys"], "scenario")
    try:
        p = fn(shifted, clusters, n_perm=PERMUTATION_N, seed=A1_BOOTSTRAP_SEED,
               alternative="two-sided")
    except Exception as exc:
        return {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    return {**base, "status": "ok", "p_value": None if p is None else float(p)}


# ---- evaluating one prediction ---------------------------------------------
def _events(lo: float, hi: float, threshold: float) -> tuple[bool, bool]:
    return bool(lo > threshold), bool(hi < threshold)


def a1_pool04(
    pred: dict[str, Any],
    series: dict[str, Any],
    primary: dict[str, Any],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """POOL-04: a decision-bearing bound within 1.00 pp of its threshold is
    recomputed at seven bootstrap seeds; any change of verdict -> on_boundary."""
    rule = A1_RULES[pred["rule"]]
    t = float(pred["threshold_pp"]) / 100.0
    near = {}
    for name in rule["bounds"]:
        value = primary[name]
        near[name] = abs(value - t) * 100.0 <= POOL04_WINDOW_PP + 1e-12
    fired = any(near.values())
    out: dict[str, Any] = {
        "rule": "POOL-04",
        "window_pp": POOL04_WINDOW_PP,
        "threshold_pp": pred["threshold_pp"],
        "bounds_checked": list(rule["bounds"]),
        "within_window": near,
        "fired": fired,
        "seeds": list(POOL04_SEEDS),
    }
    if not fired:
        out["stable"] = True
        return out
    base_verdict = rule["decide"](primary["point"], *_events(primary["lo"], primary["hi"], t))
    per_seed = []
    for s in POOL04_SEEDS:
        if s == seed:
            lo, hi = primary["lo"], primary["hi"]
        else:
            lo, hi = percentile_ci(
                cluster_bootstrap_means(series["diffs"], _cluster_labels(series["keys"], "scenario"),
                                        n_boot=n_boot, seed=s)
            )
        verdict = rule["decide"](primary["point"], *_events(lo, hi, t))
        per_seed.append({"seed": s, "lo_pp": round(lo * 100, 2), "hi_pp": round(hi * 100, 2),
                         "verdict": verdict})
    out["bounds_by_seed"] = per_seed
    out["verdicts_by_seed"] = sorted({row["verdict"] for row in per_seed})
    out["stable"] = all(row["verdict"] == base_verdict for row in per_seed)
    return out


def a1_evaluate_contrast_prediction(
    pred: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    rule = A1_RULES[pred["rule"]]
    out: dict[str, Any] = {k: v for k, v in pred.items()}
    out["rule_text"] = rule["text"]
    out["direction"] = rule["direction"]
    missing = [a for a in (pred["left"], pred["right"]) if a not in arms]
    if missing:
        out.update(decidable=False, verdict="arm_absent", reason=f"no --arm for {missing}")
        return out
    left, right = arms[pred["left"]], arms[pred["right"]]
    field = A1_METRIC_FIELDS[pred["metric"]]
    cmp = a1_contrast(left["episodes"], right["episodes"], field, n_boot=n_boot, seed=seed)
    primary = cmp["scenario"]
    out["contrast"] = _public_contrast(cmp)
    out["tgc_secondary"] = (
        _public_contrast(a1_contrast(left["episodes"], right["episodes"], "tgc",
                                     n_boot=n_boot, seed=seed))
        if pred["metric"] != "tgc"
        else None
    )
    incomplete = [a for a in (pred["left"], pred["right"]) if not arms[a]["complete"]]
    if primary["point"] is None:
        out.update(decidable=False, verdict="refused_no_pairs", reason="no scored pairs")
        return out
    t = float(pred["threshold_pp"]) / 100.0
    lo_above, hi_below = _events(primary["lo"], primary["hi"], t)
    out["events_unadjusted"] = {"lo_above_threshold": lo_above, "hi_below_threshold": hi_below}
    out["verdict_unadjusted"] = rule["decide"](primary["point"], lo_above, hi_below)
    out["p_value"] = bootstrap_pvalue(primary["_means"], t, rule["direction"])
    out["pool04"] = a1_pool04(pred, cmp["_series"], primary, n_boot=n_boot, seed=seed)
    out["permutation_sensitivity"] = a1_permutation(cmp["_series"], t)
    out["_point"], out["_lo"], out["_hi"] = primary["point"], primary["lo"], primary["hi"]
    if incomplete:
        out.update(decidable=False, verdict="refused_incomplete",
                   reason=f"arm(s) below the registered non-crashed matrix: {incomplete}")
        return out
    out["decidable"] = True
    return out


def a1_evaluate_cost_prediction(
    pred: dict[str, Any],
    cost_report: Optional[dict[str, Any]],
    expected_n: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {k: v for k, v in pred.items()}
    out["rule_text"] = A1_RULES[pred["rule"]]["text"]
    if cost_report is None:
        out.update(decidable=False, verdict="not_computed",
                   reason="no --cost-report (scripts/analysis/j12_cost_axes.py JSON over the J10 arms)")
        return out
    arms = cost_report.get("arms") or {}
    if isinstance(arms, list):
        arms = {a.get("label"): a for a in arms if isinstance(a, dict)}
    left, right = arms.get(pred["left"]), arms.get(pred["right"])
    if not isinstance(left, dict) or not isinstance(right, dict):
        out.update(decidable=False, verdict="arm_absent",
                   reason=f"cost report lacks {pred['left']!r} or {pred['right']!r}")
        return out
    tf, cf = pred["tokens_field"], pred["calls_field"]
    values = {
        "left_tokens_per_episode": left.get(tf),
        "right_tokens_per_episode": right.get(tf),
        "left_calls_per_episode": left.get(cf),
        "right_calls_per_episode": right.get(cf),
        "left_n_episodes": left.get("n_episodes"),
        "right_n_episodes": right.get("n_episodes"),
    }
    out["observed"] = values
    if any(values[k] is None for k in values if not k.endswith("n_episodes")):
        out.update(decidable=False, verdict="not_computed", reason="a cost value is null")
        return out
    short = [s for s in ("left", "right") if (values[f"{s}_n_episodes"] or 0) < expected_n]
    lt, rt = float(values["left_tokens_per_episode"]), float(values["right_tokens_per_episode"])
    ratio = (lt / rt) if rt > 0 else math.inf
    out["ratio"] = None if math.isinf(ratio) else round(ratio, 4)
    calls_more = float(values["left_calls_per_episode"]) > float(values["right_calls_per_episode"])
    out["calls_strictly_more"] = calls_more
    verdict = "supported" if (ratio >= float(pred["min_ratio"]) and calls_more) else "not_supported"
    out["verdict_unadjusted"] = verdict
    if short:
        out.update(decidable=False, verdict="refused_incomplete",
                   reason=f"cost report covers fewer than {expected_n} episodes for {short}")
        return out
    out["decidable"] = True
    out["verdict"] = verdict
    return out


def a1_decide_family(results: list[dict[str, Any]], alpha: float = A1_ALPHA) -> dict[str, Any]:
    """Holm across the goal_pass family, then POOL-04, then the final verdict.

    Pure over the per-prediction dicts (p_value, _point/_lo/_hi, rule,
    threshold_pp, pool04, decidable), so the multiplicity logic is testable
    without a bootstrap.
    """
    family = [r for r in results if r.get("holm_family")]
    raw = [
        float(r["p_value"]) if r.get("decidable") and r.get("p_value") is not None else 1.0
        for r in family
    ]
    adjusted = holm_adjust(raw) if family else []
    for r, p_raw, p_adj in zip(family, raw, adjusted):
        r["holm"] = {
            "m": len(family),
            "p_raw": p_raw,
            "p_adjusted": p_adj,
            "rejects_at_alpha": bool(p_adj <= alpha),
            "p_raw_substituted": not (r.get("decidable") and r.get("p_value") is not None),
        }
    for r in results:
        if r.get("kind") == "cost_ratio" or not r.get("decidable"):
            r.setdefault("verdict", r.get("verdict") or "refused")
            continue
        rule = A1_RULES[r["rule"]]
        t = float(r["threshold_pp"]) / 100.0
        lo_above, hi_below = _events(r["_lo"], r["_hi"], t)
        if r.get("holm_family"):
            ok = r["holm"]["rejects_at_alpha"]
            lo_above, hi_below = lo_above and ok, hi_below and ok
        r["verdict_holm"] = rule["decide"](r["_point"], lo_above, hi_below)
        pool = r.get("pool04") or {}
        if pool.get("fired") and not pool.get("stable", True):
            r["verdict"] = "on_boundary"
        else:
            r["verdict"] = r["verdict_holm"]
    return {
        "method": "Holm step-down",
        "alpha": alpha,
        "family": [r["id"] for r in family],
        "m": len(family),
    }


# ---- report -----------------------------------------------------------------
def a1_protocol_guard(
    split: str,
    confirm: bool,
    plumbing: bool,
    arm_dirs: Iterable[Path],
    out_path: Optional[Path],
    registered_settings: bool,
) -> Optional[str]:
    if split == "test_challenge":
        return "refusing test_challenge: it is not read under A1 [docs/prereg_j10_amendment_20260924.md:461]"
    if split not in A1_SPLIT_N_TASKS:
        return f"unknown split {split!r}; A1 analyses dev (dry runs) or test_normal"
    if split == "test_normal" and not confirm:
        return (
            "refusing test_normal without --confirm-heldout-test-split: A1 is a single "
            "read [docs/prereg_j10_amendment_20260924.md:449-462]"
        )
    if split == "test_normal" and plumbing:
        return "refusing --plumbing-check on test_normal"
    if split == "test_normal" and not registered_settings:
        return "refusing test_normal with a non-registered bootstrap seed or resample count"
    for directory in arm_dirs:
        marker = heldout_marker_in_path(directory)
        if marker and split != marker:
            return f"refusing path {directory}: contains {marker!r} while --split={split}"
    if out_path is not None:
        resolved = out_path.resolve()
        try:
            resolved.relative_to(RAW_RESULTS_ROOT.resolve())
            return f"refusing --out under {RAW_RESULTS_ROOT} (raw results are read-only)"
        except ValueError:
            pass
    return None


def load_predictions(path: Optional[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Registry override: a JSON list of predictions, or {predictions, supporting}."""
    if path is None:
        return [dict(p) for p in A1_PREDICTIONS], [dict(s) for s in A1_SUPPORTING]
    data = json.loads(path.read_text(encoding="utf-8"))
    preds = data if isinstance(data, list) else data.get("predictions")
    support = [] if isinstance(data, list) else list(data.get("supporting") or [])
    if not isinstance(preds, list) or not preds:
        raise ValueError(f"{path}: no predictions")
    ids = set()
    for p in preds:
        for key in ("id", "kind", "left", "right", "rule"):
            if key not in p:
                raise ValueError(f"{path}: prediction missing {key!r}: {p}")
        if p["id"] in ids:
            raise ValueError(f"{path}: duplicate prediction id {p['id']!r}")
        ids.add(p["id"])
        if p["rule"] not in A1_RULES:
            raise ValueError(f"{path}: unknown rule {p['rule']!r}; known {sorted(A1_RULES)}")
        if (p["kind"] == "cost_ratio") != (p["rule"] == "cost_ratio_at_least"):
            raise ValueError(f"{path}: {p['id']}: rule {p['rule']!r} does not fit kind {p['kind']!r}")
        if p["kind"] == "paired_contrast":
            if p.get("metric") not in A1_METRIC_FIELDS or "threshold_pp" not in p:
                raise ValueError(f"{path}: {p['id']} needs metric in {sorted(A1_METRIC_FIELDS)} and threshold_pp")
        elif p["kind"] == "cost_ratio":
            for key in ("min_ratio", "tokens_field", "calls_field"):
                if key not in p:
                    raise ValueError(f"{path}: {p['id']} missing {key!r}")
        else:
            raise ValueError(f"{path}: unknown kind {p['kind']!r}")
        p.setdefault("holm_family", False)
        p.setdefault("role", "secondary")
    return preds, support


def build_report_a1(
    *,
    split: str,
    seeds: list[int],
    arm_dirs: dict[str, Path],
    expected_n_tasks: int,
    confirm_heldout_test_split: bool = False,
    plumbing_check: bool = False,
    cost_report: Optional[dict[str, Any]] = None,
    predictions: Optional[list[dict[str, Any]]] = None,
    supporting: Optional[list[dict[str, Any]]] = None,
    n_boot: int = A1_BOOTSTRAP_N,
    bootstrap_seed: int = A1_BOOTSTRAP_SEED,
    out_path: Optional[Path] = None,
) -> tuple[dict[str, Any], int]:
    preds = [dict(p) for p in (predictions if predictions is not None else A1_PREDICTIONS)]
    support = [dict(s) for s in (supporting if supporting is not None else A1_SUPPORTING)]
    registered = n_boot == A1_BOOTSTRAP_N and bootstrap_seed == A1_BOOTSTRAP_SEED
    proto = a1_protocol_guard(split, confirm_heldout_test_split, plumbing_check,
                              arm_dirs.values(), out_path, registered)
    if proto:
        return ({"protocol": "A1", "label": "REFUSED", "refused": True, "reason": proto,
                 "headline": proto, "split": split}, 2)

    loaded = {label: load_arm_tree(path) for label, path in arm_dirs.items()}
    tasks = discover_tasks(loaded, seeds)
    reasons: list[str] = []
    if len(tasks) != expected_n_tasks:
        reasons.append(f"task_count_is_{len(tasks)}_expected_{expected_n_tasks}")
    arms = {label: a1_arm_episodes(label, blob, tasks, seeds) for label, blob in loaded.items()}
    provenance = {label: a1_split_provenance(path) for label, path in arm_dirs.items()}
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
            reasons.append(
                f"incomplete_arm:{label} scored={arm['n_scored']}/{arm['n_expected']} "
                f"crash={arm['n_crash']} missing={arm['n_missing']}"
            )
    blocking = bool(split_problems) or len(tasks) != expected_n_tasks or any(
        r.startswith("mixed_systems") for r in reasons
    )
    if blocking:
        for arm in arms.values():
            arm["complete"] = False

    results: list[dict[str, Any]] = []
    for pred in preds:
        if pred["kind"] == "cost_ratio":
            row = a1_evaluate_cost_prediction(pred, cost_report, expected_n_tasks * len(seeds))
            if blocking and row.get("decidable"):
                row.update(decidable=False, verdict="refused_incomplete",
                           reason="the matrix itself is refused: " + "; ".join(reasons))
            results.append(row)
        else:
            results.append(a1_evaluate_contrast_prediction(pred, arms, n_boot=n_boot, seed=bootstrap_seed))
    multiplicity = a1_decide_family(results)
    for r in results:
        for key in [k for k in r if k.startswith("_")]:
            r.pop(key)

    supporting_out = []
    for s in support:
        row = dict(s)
        row["decision_bearing"] = False
        if s["left"] in arms and s["right"] in arms:
            row["goal_pass"] = _public_contrast(a1_contrast(
                arms[s["left"]]["episodes"], arms[s["right"]]["episodes"], "goal_pass_rate",
                n_boot=n_boot, seed=bootstrap_seed))
        else:
            row["goal_pass"] = None
            row["reason"] = "arm absent"
        supporting_out.append(row)

    decided = [r for r in results if r.get("decidable")]
    all_decided = len(decided) == len(results)
    not_result = plumbing_check or not registered or split != "test_normal"
    label = (
        "PLUMBING CHECK, NOT A RESULT" if plumbing_check
        else "A1 DRY RUN ON DEV, NOT THE J10 RESULT" if split == "dev"
        else "J10 A1 registered analysis"
    )
    if not registered:
        label += " (NON-REGISTERED bootstrap settings)"
    headline = (
        "COMPLETE: every registered prediction decided."
        if all_decided and not reasons
        else "INCOMPLETE: " + "; ".join(reasons or ["some predictions not decidable"])
    )
    report: dict[str, Any] = {
        "protocol": "A1",
        "prereg": A1_PREREG,
        "label": label,
        "headline": headline,
        "not_the_j10_result": not_result,
        "split": split,
        "seeds": seeds,
        "expected_n_tasks": expected_n_tasks,
        "n_tasks_observed_union": len(tasks),
        "expected_pairs_per_arm": expected_n_tasks * len(seeds),
        "incomplete_reasons": reasons,
        "bootstrap": {
            "n": n_boot,
            "seed": bootstrap_seed,
            "registered": registered,
            "primary_clustering": "scenario",
            "secondary_clustering": "task",
            "interval": "95% percentile; lo = means[int(0.025 B)], hi = means[int(0.975 B)]",
            "paired_on": "(task_id, seed)",
            "algorithm": "hj1_gate._draw_task_clusters / j8_frontier.paired_diff_scenario, seed exposed",
        },
        "stability_rule": {"id": "POOL-04", "window_pp": POOL04_WINDOW_PP, "seeds": list(POOL04_SEEDS)},
        "multiplicity": multiplicity,
        "arms": {
            label_: {k: v for k, v in arm.items() if k != "episodes"} | {"split_provenance": provenance[label_]}
            for label_, arm in arms.items()
        },
        "predictions": results,
        "verdicts": {r["id"]: r.get("verdict") for r in results},
        "supporting_contrasts": supporting_out,
        "ambiguities": A1_AMBIGUITIES,
        "crash_convention": (
            "error_type == 'crash' is not an outcome (dropped, counted, arm incomplete); "
            "limit / timeout / parse_error / api_error are scored outcomes."
        ),
    }
    return report, (0 if all_decided and not reasons else 1)


def build_parser_a1() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J10 analysis under Amendment A1 (default protocol).")
    p.add_argument("--split", required=True, choices=["dev", "test_normal", "test_challenge"])
    p.add_argument("--confirm-heldout-test-split", "--i-understand-this-is-the-single-j10-look",
                   dest="confirm_heldout_test_split", action="store_true")
    p.add_argument("--seeds", default=A1_DEFAULT_SEEDS, help="registered seeds (A1: 1,2)")
    p.add_argument("--expected-n-tasks", type=int, default=None,
                   help="default: dev 57, test_normal 168")
    p.add_argument("--arm", action="append", required=True, metavar="LABEL=DIR",
                   help=f"repeatable; labels {sorted(A1_ARMS)} (or any label a --predictions-json names)")
    p.add_argument("--cost-report", type=Path, default=None,
                   help="scripts/analysis/j12_cost_axes.py JSON over the J10 arms (P2)")
    p.add_argument("--predictions-json", type=Path, default=None,
                   help="override the prediction registry (a JSON list, or {predictions, supporting})")
    p.add_argument("--bootstrap-seed", type=int, default=A1_BOOTSTRAP_SEED)
    p.add_argument("--n-boot", type=int, default=A1_BOOTSTRAP_N)
    p.add_argument("--plumbing-check", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    return p


def main_a1(argv: Optional[list[str]] = None) -> int:
    args = build_parser_a1().parse_args(argv)
    try:
        seeds = parse_seeds(args.seeds)
        preds, support = load_predictions(args.predictions_json)
        allowed = set(A1_ARMS) | {p[k] for p in preds for k in ("left", "right")}
        arm_dirs: dict[str, Path] = {}
        for spec in args.arm:
            label, sep, directory = spec.partition("=")
            if not sep or not label or not directory:
                raise ValueError(f"expected LABEL=DIR, got {spec!r}")
            if label not in allowed:
                raise ValueError(f"unknown arm label {label!r}; allowed: {sorted(allowed)}")
            if label in arm_dirs:
                raise ValueError(f"duplicate --arm {label}")
            arm_dirs[label] = Path(directory)
        cost = json.loads(args.cost_report.read_text(encoding="utf-8")) if args.cost_report else None
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"protocol": "A1", "refused": True, "reason": str(exc)}, indent=2))
        return 2
    expected = args.expected_n_tasks
    if expected is None:
        expected = A1_SPLIT_N_TASKS.get(args.split, 0)
    report, code = build_report_a1(
        split=args.split,
        seeds=seeds,
        arm_dirs=arm_dirs,
        expected_n_tasks=expected,
        confirm_heldout_test_split=args.confirm_heldout_test_split,
        plumbing_check=args.plumbing_check,
        cost_report=cost,
        predictions=preds,
        supporting=support,
        n_boot=args.n_boot,
        bootstrap_seed=args.bootstrap_seed,
        out_path=args.out,
    )
    text = json.dumps(report, indent=2, default=str) + "\n"
    print(text, end="")
    if args.out and code != 2:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return code


def main(argv: Optional[list[str]] = None) -> int:
    """`--protocol a1` (default) or `--protocol v1` (the prereg_v1 H1-H4 report)."""
    args = list(sys.argv[1:] if argv is None else argv)
    protocol = "a1"
    for i, token in enumerate(args):
        if token == "--protocol" and i + 1 < len(args):
            protocol = args[i + 1]
            del args[i : i + 2]
            break
        if token.startswith("--protocol="):
            protocol = token.split("=", 1)[1]
            del args[i]
            break
    if protocol == "v1":
        return main_v1(args)
    if protocol != "a1":
        print(json.dumps({"refused": True, "reason": f"unknown --protocol {protocol!r} (a1|v1)"}))
        return 2
    return main_a1(args)


if __name__ == "__main__":
    raise SystemExit(main())
