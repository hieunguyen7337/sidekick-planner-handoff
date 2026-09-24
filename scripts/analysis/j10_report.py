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
#     dropped from that contrast and counted [A1 §5.1, lines 208-217];
#   * percentile cluster bootstrap, B = 10,000, seed 20260924; scenario
#     clustering is PRIMARY and governs every decision, task clustering is
#     reported beside it [A1 §5.2, lines 221-226];
#   * the resampling algorithm is hj1_gate.paired_diff / j8_frontier.
#     paired_diff_scenario draw-for-draw (same RNG consumption, same percentile
#     indices), with the seed exposed -- j8_frontier hard-codes hj1_gate.SEED =
#     20260915, the seed of every A1 dev number not marked otherwise [A1 §5.2 F2,
#     lines 220-222];
#   * predictions are DATA (A1_PREDICTIONS); decision rules are a small table
#     (A1_RULES) the data refers to by name, so P7 is a list entry;
#   * Holm across the goal_pass predictions flagged holm_family=True -- those whose
#     support needs a rejection: P1, P3, P4, P6 and any P7 component [A1 §5.3, lines 237-238];
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
POOL04_BIG_N = 200_000  # A1:256-257, "and at 200,000 resamples at 20260924"
POOL04_BIG_SEED = 20260924
CLUSTER_INFERENCE_PATH = Path(__file__).resolve().parent / "cluster_inference.py"
RAW_RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")

# Registered arms [A1 r2 §4: 1, 1b, 2-12]. The value is the config that produces the
# arm (None: no J10 config exists yet); its campaign id is j10_<label>_20260924. The
# labels are what --arm accepts, so an arm missing here cannot be reported unless a
# prediction names it -- which executor_alone_bplus (1b) does not. show_k10 (11) and
# advise_k10_neutral (12) carry no prediction either: A1 r3 completed P7 from an
# unresolved B2, so they appear only in the exploratory rows E2-E5 [A1:441-444].
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


def _rule_positive_with_reversal(point: float, lo_above: bool, hi_below: bool) -> str:
    # P1's rule mirrored for a positive prediction (P6, A1:387-391). The events it receives
    # are P1's: the unadjusted scenario CI bound AND, inside the Holm family, the Holm-adjusted
    # two-sided p (a1_decide_family), so "reversed" needs the same evidence as "supported".
    if lo_above:
        return "supported"
    if hi_below:
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
    # Two-sided p, as P1's rule, so a reversal can reject too. Whenever the lower tail
    # (means <= t) is the smaller one, 2 x min(tails) equals the 'greater' p exactly, so the
    # change from 'greater' moves P6's p only when the effect points the wrong way.
    "positive_excludes_zero_with_reversal": {
        "decide": _rule_positive_with_reversal,
        "bounds": ("lo", "hi"),
        "direction": "two-sided",
        "text": "supported if CI lo > t; reversed if CI hi < t; else not_supported",
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
        "citation": f"{A1_PREREG}:326-336",
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
        "citation": f"{A1_PREREG}:338-359",
        "notes": (
            "Read from a scripts/analysis/j12_cost_axes.py report over the J10 arms "
            "(--cost-report), whose prefix arms are costed at their attributed source "
            "steps. Run j12 with --packet-source pointed at the J10 arm-3 campaign, not "
            "its hj1b default. If not supported, P1 is uninterpretable as a channel "
            "result [A1:313-314]."
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
        # A1 r2 §5.5 (A1:270): the sign-flip sensitivity is one-sided at the threshold for P3
        # only -- 'greater' on the differences shifted by +0.07 (cluster_inference.registered_signflip).
        "permutation_alternative": "greater",
        "statement": "prefix_m11 − planner_alone_cap81 on goal_pass has CI lower bound above −7.00 pp",
        "citation": f"{A1_PREREG}:361-382",
        "dev_reference": {
            "diff_pp": 4.75,
            "ci95_pp_scenario": [-1.16, 11.75],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_ceiling_c81_minus_c81_bp_m11 (negated here; A1 r2 quotes it stored, −4.75 [−11.75, +1.16], A1:322-323)",
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
        "citation": f"{A1_PREREG}:384-400",
        "dev_reference": {
            "diff_pp": 2.82,
            "ci95_pp_scenario": [-1.55, 7.16],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_c81_zs_m9_minus_c81_zs_m11 (stored −2.82 [−7.16, +1.55]; negated here, as r1 did silently -- A1 r2 quotes it stored, A1:346-347)",
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
        "citation": f"{A1_PREREG}:402-414",
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
        # A1:387-391 registers supported / not supported / reversed, as for P1.
        "rule": "positive_excludes_zero_with_reversal",
        "threshold_pp": 0.0,
        "holm_family": True,
        "statement": "takeover_k10 − advise_k10_fullctx on goal_pass is positive, 95% scenario CI excluding zero",
        "citation": f"{A1_PREREG}:416-443",
        "dev_reference": {
            "diff_pp": 6.69,
            # A1:377-378 (F4): 13.49 in the registered orientation; 13.48 was the reversed
            # contrast's bound negated, one order statistic away.
            "ci95_pp_scenario": [1.29, 13.49],
            "source": "campaign/results/hj13_c1_matched_trigger_20260923.report.json (CHAN-C1-02), "
                      "recomputed in the registered orientation by j8_frontier at seed 20260915",
            "key": "contrasts.goal_pass_all_advise_fullctx_k10_minus_takeover_k10 (stored reversed)",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
]

# A1 §6 "Supporting contrasts, registered but not decision-bearing" [A1:450-459], one
# row per line of r2's table, in its order and orientation. All on goal_pass, reported
# unadjusted and outside the Holm family [A1:250]. `kind` picks the estimand:
#   paired        left − right, paired on (task_id, seed), as every A1 contrast;
#   did           (left[0] − left[1]) − (right[0] − right[1]) per (task_id, seed), over
#                 the keys all four arms score;
#   handoff_depth per receiver, target − base restricted to episodes whose TARGET-depth
#                 episode handed off, as F-c: Σ d·h / Σ h with the whole scenario
#                 resampled (j16_robustness.decomposition, gain_on_handoff_subset).
A1_SUPPORTING: list[dict[str, Any]] = [
    # A1:454 "| `advise_k1 − prefix_m9` | −9.89 pp | [−17.79, −1.99] | dev basis |"
    {"id": "S1", "kind": "paired", "left": "advise_k1_fullctx", "right": "prefix_m9",
     "citation": f"{A1_PREREG}:499",
     "dev_reference": {"diff_pp": -9.89, "ci95_pp_scenario": [-17.79, -1.99], "source": "dev basis"}},
    # A1:455 "| `advise_k10 − prefix_m11` | −7.73 pp | [−12.60, −3.12] | dev basis |"
    {"id": "S2", "kind": "paired", "left": "advise_k10_fullctx", "right": "prefix_m11",
     "citation": f"{A1_PREREG}:500",
     "dev_reference": {"diff_pp": -7.73, "ci95_pp_scenario": [-12.60, -3.12], "source": "dev basis"}},
    # A1:456 "| `prefix_m11 − prefix_m9` (tailored depth) | +4.25 pp (171) | [+0.15, +8.75],
    # **on the boundary** (POOL-04) | j15 `t_depth_m9_m11` |"
    {"id": "S3", "kind": "paired", "left": "prefix_m11", "right": "prefix_m9",
     "label": "tailored depth", "citation": f"{A1_PREREG}:501",
     "dev_reference": {"diff_pp": 4.25, "ci95_pp_scenario": [0.15, 8.75], "n_pairs": 171,
                       "pool04": "on the boundary", "source": "j15 t_depth_m9_m11"}},
    # A1:457 "| `(m11 − m9)_tailored − (m11 − m9)_untailored` (R2) | +2.81 pp (171) |
    # [−2.57, +8.96] | POOL-03 |"
    {"id": "S4", "kind": "did", "left": ["prefix_m11", "prefix_m9"],
     "right": ["prefix_zs_m11", "prefix_zs_m9"], "label": "tailoring x depth (R2)",
     "citation": f"{A1_PREREG}:502",
     "dev_reference": {"diff_pp": 2.81, "ci95_pp_scenario": [-2.57, 8.96], "n_pairs": 171,
                       "source": "POOL-03"}},
    # A1:458 "| `prefix_m11 − executor_alone_bplus` (tailored floor → m11) | new arm | — | arm 1b |"
    {"id": "S5", "kind": "paired", "left": "prefix_m11", "right": "executor_alone_bplus",
     "label": "tailored floor -> m11", "citation": f"{A1_PREREG}:503", "dev_reference": None},
    # A1:459 "| handoff-only depth: m9 → m11 restricted to episodes where a handoff occurs at
    # m = 11 | reported for both receivers | — | F-c |"
    {"id": "S6", "kind": "handoff_depth", "label": "handoff-only depth m9 -> m11",
     "receivers": {"tailored": ["prefix_m11", "prefix_m9"],
                   "untailored": ["prefix_zs_m11", "prefix_zs_m9"]},
     "citation": f"{A1_PREREG}:504", "dev_reference": None},
]

# Not in r2's supporting table, so reported as exploratory [A1:250-251]. The ceiling −
# untailored m11 gap is the number behind the §4.1 sourcing correction [A1:191], which §7
# item 6 reports whether or not it helps [A1:480].
A1_EXPLORATORY: list[dict[str, Any]] = [
    {"id": "E1", "kind": "paired", "left": "planner_alone_cap81", "right": "prefix_zs_m11",
     "label": "ceiling − untailored m11 (sourcing correction)",
     "citation": f"{A1_PREREG}:191",
     "dev_reference": {"diff_pp": -2.95, "ci95_pp_scenario": [-8.65, 1.91], "n_pairs": 114}},
    # E2-E5: arms 11 and 12, exploratory because B2 was unresolved (A1 r3 §6 P7). Each is
    # B2's contrast in B2's orientation, with its dev value from
    # campaign/results/b2_decomposition_20260923.report.json `contrasts.D1`..`D4`.
    # A1:441 "| E2 | `takeover_k10 − show_k10` (D1) | +3.83 pp | [−1.56, +10.81] | `contrasts.D1` |"
    {"id": "E2", "kind": "paired", "left": "takeover_k10", "right": "show_k10",
     "label": "execution: takeover − show (B2 D1)", "citation": f"{A1_PREREG}:486",
     "dev_reference": {"diff_pp": 3.83, "ci95_pp_scenario": [-1.56, 10.81], "n_pairs": 171,
                       "source": "b2 contrasts.D1"}},
    # A1:442 "| E3 | `show_k10 − advise_k10_fullctx` (D2) | +2.30 pp | [−2.43, +7.31] | `contrasts.D2` |"
    {"id": "E3", "kind": "paired", "left": "show_k10", "right": "advise_k10_fullctx",
     "label": "prompt + content: show − advice (B2 D2)", "citation": f"{A1_PREREG}:487",
     "dev_reference": {"diff_pp": 2.30, "ci95_pp_scenario": [-2.43, 7.31], "n_pairs": 171,
                       "source": "b2 contrasts.D2"}},
    # A1:443 "| E4 | `advise_k10_neutral − advise_k10_fullctx` (D3) | +3.73 pp | [−0.06, +8.24] | `contrasts.D3` |"
    {"id": "E4", "kind": "paired", "left": "advise_k10_neutral", "right": "advise_k10_fullctx",
     "label": "advice prompt wording: neutral − registered (B2 D3)", "citation": f"{A1_PREREG}:488",
     "dev_reference": {"diff_pp": 3.73, "ci95_pp_scenario": [-0.06, 8.24], "n_pairs": 171,
                       "source": "b2 contrasts.D3"}},
    # A1:444 "| E5 | `takeover_k10 − advise_k10_neutral` (D4) | +2.40 pp | [−2.94, +8.89] | `contrasts.D4` |"
    {"id": "E5", "kind": "paired", "left": "takeover_k10", "right": "advise_k10_neutral",
     "label": "channel vs neutral advice: takeover − neutral (B2 D4)", "citation": f"{A1_PREREG}:489",
     "dev_reference": {"diff_pp": 2.40, "ci95_pp_scenario": [-2.94, 8.89], "n_pairs": 171,
                       "source": "b2 contrasts.D4"}},
]

# Prefix arms and their depth m, for §7 item 4's no-handoff counts [A1:475-478].
A1_PREFIX_ARMS: dict[str, int] = {"prefix_m9": 9, "prefix_m11": 11, "prefix_zs_m9": 9, "prefix_zs_m11": 11}

# §7 item 7: "SGC ... for P1 and P6, descriptive" [A1:481].
A1_SGC_PREDICTIONS = ("P1", "P6")

# Records of where A1's text and this script had to meet. `status` is
# "resolved_by_r2" when r2 now says what the script does (the r1 text that raised it
# is cited at A1_PREREG_R1). A record whose r2 text the script did not yet implement
# was "open" and is removed once the code implements it: P6 reversed, the P2 ratio
# interval, the POOL-04 200k bound, the §5.5 sign-flip rule and r2's supporting table
# all are now. r1's `p6_arm_not_registered` is gone: r2 registers arm 10 and P6
# [A1:137, 135, 364-381].
A1_AMBIGUITIES: list[dict[str, Any]] = [
    {
        "id": "bootstrap_seed_of_dev_references",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:271-274", f"{A1_PREREG_R1}:157", "scripts/setup/hj1_gate.py:29",
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
        "citations": [f"{A1_PREREG}:253-254", f"{A1_PREREG}:367-370", f"{A1_PREREG}:391-392",
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
        "citations": [f"{A1_PREREG}:282-283", f"{A1_PREREG}:290-294", f"{A1_PREREG_R1}:164"],
        "what": (
            "r1 §5.3 applied Holm 'across the five predictions on goal_pass', but P2 is a "
            "cost predicate, so P1-P5 contain four goal_pass predictions."
        ),
        "script_behaviour": (
            "Resolved by A1 r2 §5.3: family = the goal_pass predictions whose support needs a "
            "rejection (P1, P3, P4, P6 → m = 4; A1 r3 registers no P7 component, B2 being "
            "unresolved). P2 (cost) "
            "and P5 (support by non-rejection) are outside it."
        ),
    },
    {
        "id": "holm_vs_ci_rules",
        "status": "resolved_by_r2",
        "citations": [f"{A1_PREREG}:284-289", f"{A1_PREREG}:292-294", f"{A1_PREREG_R1}:164"],
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
        "citations": [f"{A1_PREREG}:259-262", f"{A1_PREREG}:574-576",
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
                # SGC's per-task pass, as hj1_gate.scenario_goal_completion reads it.
                "success": None if row.get("success") is None else bool(row["success"]),
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


def _p_two_sided(interval: dict[str, Any], threshold: float) -> Optional[float]:
    """Two-sided bootstrap p at `threshold` from an a1_interval block (None without pairs)."""
    means = interval.get("_means")
    return bootstrap_pvalue(means, threshold, "two-sided") if means else None


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
    """Lazy import of cluster_inference.registered_signflip, the A1 r2 §5.5 routine.

    Contract: registered_signflip(diffs, clusters, *, threshold, alternative, seed) ->
    {"p", "method", "n_patterns", "n_clusters", ...}. Returns None if absent.
    """
    if not CLUSTER_INFERENCE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("cluster_inference", CLUSTER_INFERENCE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "registered_signflip", None)


def a1_permutation(series: dict[str, Any], threshold: float,
                   alternative: str = "two-sided") -> dict[str, Any]:
    """Scenario-cluster sign-flip p at `threshold` (A1 r2 §5.5). Not decision-bearing.

    Exact over all 2^G sign patterns when G <= 20, else 100,000 Monte Carlo patterns at
    seed 20260924; two-sided unless the prediction registers one side (P3: 'greater').
    The formula is stated in cluster_inference.registered_signflip.
    """
    base = {
        "decision_bearing": False,
        "clusters": "scenario",
        "null": "cluster sums of (difference - threshold) symmetric about zero",
        "threshold": threshold,
        "seed": A1_BOOTSTRAP_SEED,
        "alternative": alternative,
        "rule": "A1 r2 §5.5: exact if 2^G <= 2^20, else Monte Carlo over 100,000 patterns",
    }
    if not series["diffs"]:
        return {**base, "status": "no_pairs", "p_value": None}
    try:
        fn = _load_cluster_signflip()
    except Exception as exc:  # never fatal: the p is reported beside the verdict, not in it
        return {**base, "status": "import_error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    if fn is None:
        return {**base, "status": "unavailable", "p_value": None,
                "reason": f"{CLUSTER_INFERENCE_PATH.name} or registered_signflip absent"}
    clusters = _cluster_labels(series["keys"], "scenario")
    try:
        details = fn(series["diffs"], clusters, threshold=threshold, alternative=alternative,
                     seed=A1_BOOTSTRAP_SEED)
    except Exception as exc:
        return {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    p = details.get("p") if isinstance(details, dict) else None
    return {
        **base,
        "status": "ok",
        "p_value": None if p is None else float(p),
        "method": details.get("method") if isinstance(details, dict) else None,
        "n_patterns": details.get("n_patterns") if isinstance(details, dict) else None,
        "n_clusters": details.get("n_clusters") if isinstance(details, dict) else None,
    }


# ---- ratio intervals, handoff facts, SGC (A1 §6 supporting, §7) ---------------
J16_ROBUSTNESS_PATH = Path(__file__).resolve().parent / "j16_robustness.py"
_J16_MODULE: Any = None


def _load_j16() -> Any:
    """Lazy import of j16_robustness, for bootstrap_multi / ratio (the F-c and F-f code).

    Lazy so that a module the J10 predictions never need cannot stop them being decided;
    the intervals built on it are information only.
    """
    global _J16_MODULE
    if _J16_MODULE is None:
        spec = importlib.util.spec_from_file_location("j16_robustness", J16_ROBUSTNESS_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(str(J16_ROBUSTNESS_PATH))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _J16_MODULE = module
    return _J16_MODULE


def a1_ratio_bootstrap(
    comps: dict[tuple[str, int], tuple[float, ...]],
    stats: dict[str, tuple[Any, ...]],
    units: tuple[str, ...],
    *,
    n_boot: int,
    seed: int,
    keep_samples: bool = False,
) -> dict[str, Any]:
    """Cluster percentile bootstrap of Σ comps[i] / Σ comps[j], via j16_robustness.bootstrap_multi.

    `stats` maps a name to its (numerator, denominator) component indices, with an optional
    third element True for a ratio defined only when the denominator is positive (a share of
    a rise). Whole clusters are resampled, so a ratio restricted to a subset (Σ d·h / Σ h)
    keeps the clusters that contribute nothing to it -- F-c's estimand, not a mean over a
    subset. keep_samples adds each statistic's sorted scenario resamples as `_samples_scenario`
    (internal; the caller strips it), from which a bootstrap p is read.
    """
    try:
        j16 = _load_j16()
    except Exception as exc:  # information only: never fatal
        return {"status": "import_error", "error": f"{type(exc).__name__}: {exc}"}
    fns = {name: j16.ratio(spec[0], spec[1], positive_denominator=bool(spec[2]) if len(spec) > 2 else False)
           for name, spec in stats.items()}
    out: dict[str, Any] = {"status": "ok", "n_boot": n_boot, "seed": seed, "n_units": len(comps)}
    for unit in units:
        keep = keep_samples and unit == "scenario"
        b = j16.bootstrap_multi(comps, fns, unit, seed, n_boot, keep_samples=keep)
        out[f"n_clusters_{unit}"] = b["n_clusters"]
        for name, st in b["stats"].items():
            blk = out.setdefault(name, {"point": st["point"]})
            blk[f"ci95_{unit}"] = st["ci95"]
            blk[f"n_undefined_{unit}"] = st["n_undefined"]
            if keep:
                blk["_samples_scenario"] = st.get("_samples")
    return out


def _as_pp(block: dict[str, Any], units: tuple[str, ...]) -> dict[str, Any]:
    out = {"diff_pp": None if block.get("point") is None else round(block["point"] * 100, 2)}
    for unit in units:
        ci = block.get(f"ci95_{unit}")
        out[f"ci95_pp_{unit}"] = None if ci is None else [round(ci[0] * 100, 2), round(ci[1] * 100, 2)]
        out[f"n_undefined_{unit}"] = block.get(f"n_undefined_{unit}")
    return out


def _last_report_handoff(events_path: Path) -> Optional[bool]:
    """handoff_occurred of the last `report` event after the last run_start, or None.

    The events of the attempt that wrote result.json, read as j16_robustness
    .events_last_attempt / episode_facts and j13_mechanism do. Kept here, not imported,
    because §7 item 4 is reported regardless of outcome and must not depend on j16.
    """
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    events: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    start = 0
    for i, ev in enumerate(events):
        if ev.get("event_type") == "run_start":
            start = i
    flag: Optional[bool] = None
    for ev in events[start:]:
        payload = ev.get("payload")
        if ev.get("event_type") == "report" and isinstance(payload, dict):
            value = payload.get("handoff_occurred")
            flag = None if value is None else bool(value)
    return flag


def a1_handoff_flags(root: Path) -> dict[tuple[str, int], Optional[bool]]:
    """(task_id, seed) -> handoff_occurred for every result.json under a prefix arm.

    The first result.json per key wins, as in load_arm_tree (a duplicate already makes
    the arm incomplete there).
    """
    flags: dict[tuple[str, int], Optional[bool]] = {}
    if not root.exists():
        return flags
    for path in sorted(root.rglob("result.json")):
        row, _err = _read_result(path)
        if row is None or row.get("task_id") is None or row.get("seed") is None:
            continue
        key = (str(row["task_id"]), int(row["seed"]))
        if key not in flags:
            flags[key] = _last_report_handoff(path.parent / "events.jsonl")
    return flags


def a1_no_handoff_counts(
    arm: dict[str, Any],
    flags: dict[tuple[str, int], Optional[bool]],
    m: Optional[int],
) -> dict[str, Any]:
    """§7 item 4 [A1:475-478]: over an arm's scored episodes, how many handed off at m."""
    values = [flags.get(k) for k in sorted(arm["episodes"])]
    return {
        "m": m,
        "n_scored": len(values),
        "n_handoff": sum(1 for v in values if v is True),
        # "arm 3 finished within m actions": the prefix exhausted the source trajectory.
        "n_no_handoff": sum(1 for v in values if v is False),
        "n_flag_missing": sum(1 for v in values if v is None),
        "citation": f"{A1_PREREG}:520-523",
    }


def a1_sgc_units(
    episodes: dict[tuple[str, int], dict[str, Any]],
    tasks: list[str],
    seeds: list[int],
) -> tuple[dict[tuple[str, int], float], int]:
    """(scenario, seed) -> 1.0 if every task of the scenario passed, else 0.0 [A1:481].

    A unit is scored only when all its registered tasks are scored episodes with a
    recorded `success` (hj1_gate.scenario_goal_completion's coverage rule); a crash is
    not an outcome under A1 (F6), so it leaves its unit unscored rather than failed.
    Returns (units, number of registered units left unscored).
    """
    expected = Counter(scenario_of(t) for t in tasks)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for (task_id, seed), ep in episodes.items():
        groups.setdefault((scenario_of(task_id), seed), []).append(ep)
    units: dict[tuple[str, int], float] = {}
    for unit, group in groups.items():
        if len(group) < expected.get(unit[0], 0) or any(ep.get("success") is None for ep in group):
            continue
        units[unit] = 1.0 if all(ep["success"] for ep in group) else 0.0
    return units, len(expected) * len(seeds) - len(units)


def a1_sgc(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    tasks: list[str],
    seeds: list[int],
) -> dict[str, Any]:
    """SGC of both sides of a prediction on shared (scenario, seed) units. Descriptive:
    r2 registers no interval or test for it [A1:481]."""
    ul, dropped_l = a1_sgc_units(left, tasks, seeds)
    ur, dropped_r = a1_sgc_units(right, tasks, seeds)
    shared = sorted(set(ul) & set(ur))
    sgc_l = statistics.fmean(ul[u] for u in shared) if shared else None
    sgc_r = statistics.fmean(ur[u] for u in shared) if shared else None
    return {
        "descriptive": True,
        "decision_bearing": False,
        "unit": "(scenario, seed); passes only if every task of the scenario passes (success)",
        "n_units_registered": len({scenario_of(t) for t in tasks}) * len(seeds),
        "n_units_shared": len(shared),
        "n_units_unscored_left": dropped_l,
        "n_units_unscored_right": dropped_r,
        "n_passed_left": int(sum(ul[u] for u in shared)),
        "n_passed_right": int(sum(ur[u] for u in shared)),
        "sgc_left": None if sgc_l is None else round(sgc_l, 6),
        "sgc_right": None if sgc_r is None else round(sgc_r, 6),
        "diff_pp": None if not shared else round((sgc_l - sgc_r) * 100, 2),
        "n_discordant_units": sum(1 for u in shared if ul[u] != ur[u]),
        "citation": f"{A1_PREREG}:526",
    }


def a1_did_series(
    arms4: list[dict[tuple[str, int], dict[str, Any]]],
    field: str,
) -> dict[str, Any]:
    """(a − b) − (c − d) per (task_id, seed), over the keys all four arms score."""
    shared = sorted(set(arms4[0]) & set(arms4[1]) & set(arms4[2]) & set(arms4[3]))
    keys: list[tuple[str, int]] = []
    diffs: list[float] = []
    missing = 0
    for key in shared:
        vals = [arm[key].get(field) for arm in arms4]
        if any(v is None for v in vals):
            missing += 1
            continue
        a, b, c, d = (float(v) for v in vals)
        keys.append(key)
        diffs.append((a - b) - (c - d))
    return {"keys": keys, "diffs": diffs, "n_shared": len(shared), "n_dropped_missing_field": missing}


def a1_handoff_depth(
    target: dict[tuple[str, int], dict[str, Any]],
    base: dict[tuple[str, int], dict[str, Any]],
    target_flags: dict[tuple[str, int], Optional[bool]],
    field: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """target − base on the target depth's handoff episodes and on all episodes [A1:459, 439-440].

    h = 1 only when the TARGET episode's report says handoff_occurred is true (F-c,
    j16_robustness.decomposition); a missing flag counts as h = 0 and is reported.
    """
    comps: dict[tuple[str, int], tuple[float, ...]] = {}
    n_missing_field = n_flag_missing = 0
    for key in sorted(set(target) & set(base)):
        yt, yb = target[key].get(field), base[key].get(field)
        if yt is None or yb is None:
            n_missing_field += 1
            continue
        flag = target_flags.get(key)
        n_flag_missing += int(flag is None)
        h = 1.0 if flag is True else 0.0
        d = float(yt) - float(yb)
        comps[key] = (d * h, h, d, 1.0)
    units = ("scenario", "task")
    boot = a1_ratio_bootstrap(comps, {"handoff_only": (0, 1), "all": (2, 3)}, units,
                              n_boot=n_boot, seed=seed)
    out: dict[str, Any] = {
        "n_pairs": len(comps),
        "n_handoff": int(sum(c[1] for c in comps.values())),
        "n_no_handoff_or_flag_missing": int(sum(1 - c[1] for c in comps.values())),
        "n_flag_missing": n_flag_missing,
        "n_dropped_missing_field": n_missing_field,
        "estimand": "Σ d·h / Σ h (handoff_only) and Σ d / n (all); d = target − base, h at the target depth",
        "status": boot["status"],
    }
    if boot["status"] != "ok":
        out["error"] = boot.get("error")
        return out
    out.update(n_boot=n_boot, seed=seed, n_clusters_scenario=boot["n_clusters_scenario"])
    for name in ("handoff_only", "all"):
        out[name] = _as_pp(boot[name], units)
    return out


def a1_evaluate_supporting(
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """One supporting or exploratory row on goal_pass (A1 §6 table). Not decision-bearing."""
    row = dict(spec)
    row["decision_bearing"] = False
    kind = spec.get("kind", "paired")
    field = A1_METRIC_FIELDS["goal_pass"]
    if kind == "handoff_depth":
        receivers = {}
        for name, (target, base) in spec["receivers"].items():
            if target not in arms or base not in arms:
                receivers[name] = {"target": target, "base": base, "status": "arm_absent"}
                continue
            receivers[name] = {"target": target, "base": base} | a1_handoff_depth(
                arms[target]["episodes"], arms[base]["episodes"], handoff_flags.get(target, {}),
                field, n_boot=n_boot, seed=seed)
        row["goal_pass"] = receivers
        # The handoff point is set by arm 3's trajectory, so both receivers should agree.
        targets = [t for t, _b in spec["receivers"].values() if t in handoff_flags]
        if len(targets) == 2:
            fa, fb = handoff_flags[targets[0]], handoff_flags[targets[1]]
            row["handoff_flag_mismatch_between_receivers"] = sum(
                1 for k in set(fa) & set(fb) if fa[k] != fb[k])
        return row
    if kind == "did":
        labels = list(spec["left"]) + list(spec["right"])
        absent = [a for a in labels if a not in arms]
        if absent:
            row.update(goal_pass=None, reason=f"arm absent: {absent}")
            return row
        series = a1_did_series([arms[a]["episodes"] for a in labels], field)
        scen = a1_interval(series, "scenario", n_boot=n_boot, seed=seed)
        row["goal_pass"] = {
            "field": field,
            "n_pairs": len(series["diffs"]),
            "n_shared": series["n_shared"],
            "n_dropped_missing_field": series["n_dropped_missing_field"],
            "scenario": _public(scen),
            "task": _public(a1_interval(series, "task", n_boot=n_boot, seed=seed)),
            "p_value_two_sided_at_0": _p_two_sided(scen, 0.0),
        }
        return row
    if kind != "paired":
        row.update(goal_pass=None, reason=f"unknown supporting kind {kind!r}")
        return row
    if spec["left"] in arms and spec["right"] in arms:
        cmp = a1_contrast(arms[spec["left"]]["episodes"], arms[spec["right"]]["episodes"], field,
                          n_boot=n_boot, seed=seed)
        row["goal_pass"] = _public_contrast(cmp) | {
            "p_value_two_sided_at_0": _p_two_sided(cmp["scenario"], 0.0)}
    else:
        row.update(goal_pass=None, reason="arm absent")
    return row


def a1_cost_ratio_interval(
    left: dict[str, Any],
    right: dict[str, Any],
    field: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """P2's token ratio with a scenario-clustered interval, as information [A1:245-246, 291].

    The verdict stays on the arm means [A1:296]. The interval is F-f's
    (j16_robustness.cost_contrast): Σ left / Σ right over episodes paired on
    (task_id, seed), whole scenarios resampled, from j12_cost_axes' per-episode rows.
    """
    base = {"information_only": True, "decision_bearing": False, "field": field,
            "clusters": "scenario", "estimand": "Σ left / Σ right over (task_id, seed) pairs"}

    def index(rows: Any) -> Optional[dict[tuple[str, int], Any]]:
        if not isinstance(rows, list):
            return None
        out: dict[tuple[str, int], Any] = {}
        for r in rows:
            if isinstance(r, dict) and r.get("task_id") is not None and r.get("seed") is not None:
                out.setdefault((str(r["task_id"]), int(r["seed"])), r.get(field))
        return out

    li, ri = index(left.get("episodes")), index(right.get("episodes"))
    if li is None or ri is None:
        return {**base, "status": "not_computed",
                "reason": "cost report has no per-episode rows (arms.<label>.episodes from j12_cost_axes)"}
    comps = {k: (float(li[k]), float(ri[k])) for k in sorted(set(li) & set(ri))
             if li[k] is not None and ri[k] is not None}
    if not comps:
        return {**base, "status": "no_pairs"}
    boot = a1_ratio_bootstrap(comps, {"ratio": (0, 1)}, ("scenario",), n_boot=n_boot, seed=seed)
    if boot["status"] != "ok":
        return {**base, "status": boot["status"], "error": boot.get("error")}
    st = boot["ratio"]
    ci = st.get("ci95_scenario")
    return {
        **base,
        "status": "ok",
        "n_pairs": len(comps),
        "n_clusters": boot["n_clusters_scenario"],
        "n_boot": n_boot,
        "seed": seed,
        "point": None if st["point"] is None else round(st["point"], 4),
        "ci95": None if ci is None else [round(ci[0], 4), round(ci[1], 4)],
        "n_undefined": st.get("n_undefined_scenario"),
    }


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
    # A1:255-260: the fired bound is also recomputed at 200,000 resamples at 20260924 and
    # reported with the seven. It is reported, not voted: "on the boundary" is decided by
    # the seven seeds alone.
    big_lo, big_hi = percentile_ci(
        cluster_bootstrap_means(series["diffs"], _cluster_labels(series["keys"], "scenario"),
                                n_boot=POOL04_BIG_N, seed=POOL04_BIG_SEED)
    )
    out["bound_200k"] = {
        "n_boot": POOL04_BIG_N,
        "seed": POOL04_BIG_SEED,
        "lo_pp": round(big_lo * 100, 2),
        "hi_pp": round(big_hi * 100, 2),
        "verdict": rule["decide"](primary["point"], *_events(big_lo, big_hi, t)),
        "decision_bearing": False,
    }
    return out


def a1_evaluate_contrast_prediction(
    pred: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
    stability: bool = True,
) -> dict[str, Any]:
    """One registered contrast. stability=False skips POOL-04, the permutation and the TGC
    secondary: the key-exclusion sensitivity (A1 §4.2) compares Holm verdicts only."""
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
        if pred["metric"] != "tgc" and stability
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
    # Amendment 1 §F: the BY-FDR sensitivity uses every contrast's two-sided p at its threshold.
    out["p_value_two_sided"] = bootstrap_pvalue(primary["_means"], t, "two-sided")
    if stability:
        out["pool04"] = a1_pool04(pred, cmp["_series"], primary, n_boot=n_boot, seed=seed)
        out["permutation_sensitivity"] = a1_permutation(
            cmp["_series"], t, pred.get("permutation_alternative", "two-sided"))
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
    *,
    n_boot: int = A1_BOOTSTRAP_N,
    seed: int = A1_BOOTSTRAP_SEED,
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
    out["ratio_interval"] = a1_cost_ratio_interval(left, right, tf, n_boot=n_boot, seed=seed)
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


# ---- A1 §4.2 contingency: arm-3 episodes scored without a crash that wrote no plan -----------
A1_PLAN_SOURCE_ARM = "planner_alone_cap81"  # arm 3, the only arm that plans
A1_PLANLESS_CAP_FRACTION = 0.05  # j10_arm.pbs refuses a replay arm above this (TARGET * 5 / 100)


def a1_planless_keys(arm_dirs: dict[str, Path], seeds: list[int]) -> Optional[list[tuple[str, int]]]:
    """(task_id, seed) of every arm-3 episode scored without a crash whose last attempt wrote no
    plan: the keys arms 2 and 8-12 planned live. None when arm 3 was not given.

    Reads the same definition the wrapper and the planner use (planless_source_keys).
    """
    root = arm_dirs.get(A1_PLAN_SOURCE_ARM)
    if root is None:
        return None
    from sidekick.agents.planner import planless_source_keys  # noqa: E402 (pydantic; lazy)

    keys = []
    for key in planless_source_keys(root, "planner_alone", seeds):
        seed, _, task_id = key.partition("/")
        keys.append((task_id, int(seed)))
    return sorted(keys)


def a1_key_exclusion_sensitivity(
    preds: list[dict[str, Any]],
    results: list[dict[str, Any]],
    arms: dict[str, dict[str, Any]],
    keys: list[tuple[str, int]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """A1 §4.2: every contrast prediction re-read with the planless keys dropped from every arm.

    Same bootstrap, same Holm family, same rule; POOL-04 and the permutation are not re-run.
    A prediction whose Holm verdict differs is listed in `differs`; the caller reports it as
    on_boundary. P2 (a cost ratio over arm totals) is not re-read: the live plan calls are real
    hosted spend and are counted in it like any other call.
    """
    excluded = set(keys)
    arms_x = {
        label: dict(arm, episodes={k: v for k, v in arm["episodes"].items() if k not in excluded})
        for label, arm in arms.items()
    }
    sens = [
        a1_evaluate_contrast_prediction(p, arms_x, n_boot=n_boot, seed=seed, stability=False)
        for p in preds
        if p.get("kind") != "cost_ratio"
    ]
    a1_decide_family(sens)
    by_id = {r["id"]: r for r in results}
    rows, differs = [], []
    for s in sens:
        r = by_id.get(s["id"], {})
        differ = bool(
            r.get("decidable") and s.get("decidable")
            and r.get("verdict_holm") != s.get("verdict_holm")
        )
        if differ:
            differs.append(s["id"])
        rows.append({
            "id": s["id"],
            "verdict_holm_all_pairs": r.get("verdict_holm"),
            "verdict_holm_without_keys": s.get("verdict_holm"),
            "differs": differ,
            "contrast_without_keys": s.get("contrast"),
        })
    return {"rows": rows, "differs": differs, "not_re_read": [p["id"] for p in preds
                                                              if p.get("kind") == "cost_ratio"]}


def a1_apply_key_exclusion(results: list[dict[str, Any]], differs: list[str]) -> None:
    """A verdict that changes without the planless keys is on the boundary (A1 §4.2, as §5.4)."""
    for r in results:
        if r["id"] in differs and r.get("verdict") != "on_boundary":
            r["verdict_before_key_exclusion"] = r.get("verdict")
            r["verdict"] = "on_boundary"
            r["on_boundary_reason"] = "A1 §4.2 key-exclusion sensitivity: the verdict differs without the planless keys"


# ---- Amendment 1: pre-data additions after the adversarial review ----------------------
# Appended below A1's end marker before any test_normal episode. Cited by section, never by
# line: nothing here depends on where the appended text falls in the file.
A1_AM1 = f"{A1_PREREG} Amendment 1"
A1_AM1_POWER = "campaign/results/am1_power_dev_20260923.report.json"
A1_AM1_B2_REPORT = "campaign/results/b2_decomposition_20260923.report.json"
A1_AM1_NI_MARGIN_PP = -7.00  # P3's margin; B1 reads the handoff-only estimand against it
A1_LIMIT_ERROR = "limit"  # j16_robustness.LIMIT: the 40-step limit, a scored outcome

# §C. CF1 is family CF's only decision-bearing member: a Holm family of one (a1_decide_family
# is run on CF's own list), outside P1-P6's family, so their α is unchanged. §4.2 (key
# exclusion), §5.4 (POOL-04) and §5.5 (sign-flip) apply to it as they apply to P6.
A1_AM1_CF: list[dict[str, Any]] = [
    {
        "id": "CF1",
        "role": "primary",
        "kind": "paired_contrast",
        "metric": "goal_pass",
        "left": "advise_k10_neutral",
        "right": "advise_k10_fullctx",
        "rule": "positive_excludes_zero_with_reversal",
        "threshold_pp": 0.0,
        "holm_family": True,
        "family": "CF",
        "same_contrast_as": "E4",
        "statement": ("advise_k10_neutral − advise_k10_fullctx on goal_pass is positive, "
                      "95% scenario CI excluding zero"),
        "citation": f"{A1_AM1} §C",
        "dev_reference": {"diff_pp": 3.73, "ci95_pp_scenario": [-0.06, 8.24], "n_pairs": 171,
                          "source": A1_AM1_B2_REPORT, "key": "contrasts.D3",
                          "bootstrap_seed": A1_BOOTSTRAP_SEED},
        "power": {"at_dev_effect": 0.722, "at_half_effect": 0.213, "source": A1_AM1_POWER},
        "readings": {
            "supported": ("advice written under a neutral prompt beats advice written under the "
                          "registered correction prompt; P6 is reported only as 'actions beat "
                          "correction-prompt advice', never as a channel effect"),
            "not_supported": ("the prompt effect is reported as not replicating at 336 pairs; P6 "
                              "is reported as built, with §6's qualification"),
            "reversed": "reported as a primary finding",
        },
    },
]

# §C secondaries: pre-specified, not decision-bearing, unadjusted, fixed readings. Each is an
# exploratory E-row's contrast, so the BY-FDR table (§F) counts it once, as that E-row.
A1_AM1_CF_SECONDARY: list[dict[str, Any]] = [
    {
        "id": "CF2", "left": "show_k10", "right": "advise_k10_fullctx", "same_contrast_as": "E3",
        "citation": f"{A1_AM1} §C",
        "dev_reference": {"diff_pp": 2.30, "ci95_pp_scenario": [-2.43, 7.31], "n_pairs": 171,
                          "source": A1_AM1_B2_REPORT, "key": "contrasts.D2"},
        "power_exclude_zero": {"at_dev_effect": 0.285, "source": A1_AM1_POWER},
        "readings": {
            "above": "the planner's action shown as text beats correction-prompt advice",
            "below": "correction-prompt advice beats the planner's action shown as text",
            "not_resolved": "not resolved",
        },
    },
    {
        "id": "CF3", "left": "takeover_k10", "right": "advise_k10_neutral", "same_contrast_as": "E5",
        "citation": f"{A1_AM1} §C",
        "dev_reference": {"diff_pp": 2.40, "ci95_pp_scenario": [-2.94, 8.89], "n_pairs": 171,
                          "source": A1_AM1_B2_REPORT, "key": "contrasts.D4"},
        "power_exclude_zero": {"at_dev_effect": 0.25, "source": A1_AM1_POWER},
        "readings": {
            "above": "executing the action adds to advice written under a neutral prompt",
            "below": "neutral-prompt advice beats takeover",
            "not_resolved": "the added effect of execution is not resolved at 336 pairs",
        },
        "never": "the paper never writes that execution adds nothing",
    },
]

# §B1: handoff-only non-inferiority, h from the PREFIX arm's report event.
A1_AM1_HANDOFF_NI: list[dict[str, Any]] = [
    {"id": "B1a", "left": "prefix_m11", "right": "planner_alone_cap81", "flags_from": "prefix_m11",
     "companion_of": "P3",
     "dev_reference": {"diff_pp": -0.94, "ci95_pp_scenario": [-9.51, 7.26], "n_handoff": 71,
                       "n_pairs": 171, "source": A1_AM1_POWER, "key": "dev.P3_handoff_only"}},
    {"id": "B1b", "left": "prefix_zs_m11", "right": "planner_alone_cap81", "flags_from": "prefix_zs_m11",
     "companion_of": "E1 (E1 is this contrast's all-episode value, negated)", "dev_reference": None},
]

# §B2: S6's receivers, split into handoff and silenced contributions.
A1_AM1_DECOMPOSITION = {"tailored": ("prefix_m11", "prefix_m9"),
                        "untailored": ("prefix_zs_m11", "prefix_zs_m9")}

# §B3: the chord test (dev prereg claim C2) for the four prefix arms.
A1_AM1_CHORD = {
    "arms": ("prefix_m9", "prefix_m11", "prefix_zs_m9", "prefix_zs_m11"),
    "floor": "sft_plan",
    "reference": "planner_alone_cap81",
    "cost_field": "noncached_tokens_per_episode",
}

# §B4: where each all-episode depth or NI number's handoff-only companion is printed.
A1_AM1_B4_COMPANIONS = {
    "P3": "amendment1.handoff_only_ni[B1a]",
    "P4": "supporting_contrasts[S6].goal_pass.untailored.handoff_only",
    "S3": "supporting_contrasts[S6].goal_pass.tailored.handoff_only",
    "S4": "amendment1.decomposition (both receivers)",
    "S5": "amendment1.b4_extra.S5_handoff_only",
    "E1": "amendment1.handoff_only_ni[B1b] (negated)",
}

# §D2 / §D3: the contrasts split by the step limit, and read with limit-as-0.
A1_AM1_LIMIT_IDS = ("P1", "P6", "CF1", "CF3")

# §E. H2's frozen rule for a failed P4 [docs/prereg_h2_advice_at_price_20260923.md §5]; P4 failed
# on dev (1,414,410 non-cached tokens per episode against the registered [300k, 700k]).
A1_AM1_P1_CONSTRAINT = {
    "applies_to": "P1",
    "citation": f"{A1_AM1} §E",
    "rule_quoted": ("If P4 fails: report the arm as a higher-frequency advice result only, and state "
                    "explicitly that advice remains unpriced at the action channel's budget."),
    "rule_source": "docs/prereg_h2_advice_at_price_20260923.md §5",
    "describe_as": "correction-prompt advice at every step, against the m = 11 prefix",
    "never_as": ["advice at matched budget", "ruling out a budget effect"],
    "decision_rule_changed": False,
}


def _cost_arms(cost_report: Optional[dict[str, Any]]) -> dict[str, Any]:
    arms = (cost_report or {}).get("arms") or {}
    if isinstance(arms, list):
        arms = {a.get("label"): a for a in arms if isinstance(a, dict)}
    return arms


def am1_evaluate_cf_secondary(
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """CF2 / CF3: an unadjusted goal_pass contrast and its fixed reading [Amendment 1 §C]."""
    row = dict(spec, decision_bearing=False, adjusted=False)
    missing = [a for a in (spec["left"], spec["right"]) if a not in arms]
    if missing:
        row.update(status="arm_absent", side=None, reading=None, reason=f"no --arm for {missing}")
        return row
    cmp = a1_contrast(arms[spec["left"]]["episodes"], arms[spec["right"]]["episodes"],
                      A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
    scen = cmp["scenario"]
    row["contrast"] = _public_contrast(cmp)
    if scen["point"] is None:
        row.update(status="no_pairs", side=None, reading=None)
        return row
    row["p_value_two_sided_at_0"] = _p_two_sided(scen, 0.0)
    side = "above" if scen["lo"] > 0 else "below" if scen["hi"] < 0 else "not_resolved"
    incomplete = [a for a in (spec["left"], spec["right"]) if not arms[a]["complete"]]
    if incomplete:
        row.update(status="refused_incomplete", side=side, reading=None,
                   reason=f"arm(s) below the registered non-crashed matrix: {incomplete}")
        return row
    row.update(status="ok", side=side, reading=spec["readings"][side])
    return row


def am1_handoff_comps(
    target: dict[tuple[str, int], dict[str, Any]],
    base: dict[tuple[str, int], dict[str, Any]],
    target_flags: dict[tuple[str, int], Optional[bool]],
    field: str,
) -> tuple[dict[tuple[str, int], tuple[float, ...]], int, int]:
    """Per (task_id, seed): (d·h, h, d·(1−h), 1−h, d, 1) with d = target − base and h the
    TARGET episode's handoff_occurred (a missing flag counts as h = 0 and is counted)."""
    comps: dict[tuple[str, int], tuple[float, ...]] = {}
    n_missing_field = n_flag_missing = 0
    for key in sorted(set(target) & set(base)):
        yt, yb = target[key].get(field), base[key].get(field)
        if yt is None or yb is None:
            n_missing_field += 1
            continue
        flag = target_flags.get(key)
        n_flag_missing += int(flag is None)
        h = 1.0 if flag is True else 0.0
        d = float(yt) - float(yb)
        comps[key] = (d * h, h, d * (1.0 - h), 1.0 - h, d, 1.0)
    return comps, n_missing_field, n_flag_missing


def am1_ni_reading(
    comps: dict[tuple[str, int], tuple[float, ...]],
    lo: float,
    *,
    margin_pp: float,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """holds / fails / on_boundary for a handoff-only lower bound against the margin, with
    §5.4 (POOL-04) applied as a1_pool04 applies it: a bound within 1.00 pp of the margin is
    recomputed at the seven seeds, and any change of reading is 'on_boundary'. The 200,000-
    resample bound is reported, not voted. Only (d·h, h) is resampled: the draw sequence
    depends on the cluster count and seed alone, so the bound is the one already computed."""
    t = margin_pp / 100.0
    base_reading = "holds" if lo > t else "fails"
    out: dict[str, Any] = {"margin_pp": margin_pp, "window_pp": POOL04_WINDOW_PP,
                           "lower_bound_pp": round(lo * 100, 2),
                           "fired": abs(lo - t) * 100.0 <= POOL04_WINDOW_PP + 1e-12}
    if not out["fired"]:
        out.update(stable=True, reading=base_reading)
        return out
    pair = {k: (c[0], c[1]) for k, c in comps.items()}
    per_seed = []
    for s in POOL04_SEEDS:
        if s == seed:
            lo_s = lo
        else:
            b = a1_ratio_bootstrap(pair, {"h": (0, 1)}, ("scenario",), n_boot=n_boot, seed=s)
            lo_s = b["h"]["ci95_scenario"][0]
        per_seed.append({"seed": s, "lo_pp": round(lo_s * 100, 2),
                         "reading": "holds" if lo_s > t else "fails"})
    big = a1_ratio_bootstrap(pair, {"h": (0, 1)}, ("scenario",), n_boot=POOL04_BIG_N, seed=POOL04_BIG_SEED)
    big_lo = big["h"]["ci95_scenario"][0]
    stable = all(r["reading"] == base_reading for r in per_seed)
    out.update(
        bounds_by_seed=per_seed,
        stable=stable,
        bound_200k={"n_boot": POOL04_BIG_N, "seed": POOL04_BIG_SEED, "lo_pp": round(big_lo * 100, 2),
                    "reading": "holds" if big_lo > t else "fails", "decision_bearing": False},
        reading=base_reading if stable else "on_boundary",
    )
    return out


def am1_handoff_ni(
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§B1: Σd·h / Σh for left − right on both metrics, h from the prefix arm, with the NI
    reading at −7.00 pp on goal_pass. Printed beside P3; never changes P3's verdict."""
    row = dict(spec, decision_bearing=False, margin_pp=A1_AM1_NI_MARGIN_PP, citation=f"{A1_AM1} §B1",
               estimand="Σ d·h / Σ h, d = left − right, h = handoff_occurred of the left (prefix) episode")
    missing = [a for a in (spec["left"], spec["right"]) if a not in arms]
    if missing:
        row.update(status="arm_absent", reason=f"no --arm for {missing}")
        return row
    flags = handoff_flags.get(spec["flags_from"], {})
    units = ("scenario", "task")
    for metric in ("goal_pass", "tgc"):
        comps, n_missing_field, n_flag_missing = am1_handoff_comps(
            arms[spec["left"]]["episodes"], arms[spec["right"]]["episodes"], flags, A1_METRIC_FIELDS[metric])
        blk: dict[str, Any] = {
            "field": A1_METRIC_FIELDS[metric],
            "n_pairs": len(comps),
            "n_handoff": int(sum(c[1] for c in comps.values())),
            "n_silenced": int(sum(c[3] for c in comps.values())),
            "n_flag_missing": n_flag_missing,
            "n_dropped_missing_field": n_missing_field,
        }
        boot = a1_ratio_bootstrap(comps, {"handoff_only": (0, 1), "silenced": (2, 3), "all": (4, 5)},
                                  units, n_boot=n_boot, seed=seed, keep_samples=True)
        blk["status"] = boot["status"]
        if boot["status"] != "ok":
            blk["error"] = boot.get("error")
            row[metric] = blk
            continue
        for name in ("handoff_only", "silenced", "all"):
            blk[name] = _as_pp(boot[name], units)
        ho = boot["handoff_only"]
        ci = ho.get("ci95_scenario")
        if metric == "goal_pass":
            if ho["point"] is None or ci is None:
                blk["ni"] = {"reading": "undefined", "reason": "no handoff episodes"}
            else:
                blk["ni"] = am1_ni_reading(comps, ci[0], margin_pp=A1_AM1_NI_MARGIN_PP,
                                           n_boot=n_boot, seed=seed)
                samples = ho.get("_samples_scenario") or []
                blk["p_value_two_sided_at_margin"] = (
                    bootstrap_pvalue(samples, A1_AM1_NI_MARGIN_PP / 100.0, "two-sided") if samples else None)
        row[metric] = blk
    return row


def am1_decomposition(
    target: dict[tuple[str, int], dict[str, Any]],
    base: dict[tuple[str, int], dict[str, Any]],
    target_flags: dict[tuple[str, int], Optional[bool]],
    field: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§B2: the all-episode rise base → target split into the part earned on episodes that hand
    off at the target depth and the part on silenced ones -- j16_robustness.decomposition's
    estimand (h from the target), at A1's bootstrap seed."""
    comps, n_missing_field, n_flag_missing = am1_handoff_comps(target, base, target_flags, field)
    units = ("scenario", "task")
    stats = {
        "delta_total": (4, 5),
        "contribution_handoff": (0, 5),
        "contribution_silenced": (2, 5),
        "share_of_rise_from_handoff": (0, 4, True),
        "gain_on_handoff_subset": (0, 1),
        "gain_on_silenced_subset": (2, 3),
    }
    out: dict[str, Any] = {
        "field": field,
        "n_pairs": len(comps),
        "n_handoff": int(sum(c[1] for c in comps.values())),
        "n_silenced": int(sum(c[3] for c in comps.values())),
        "n_flag_missing": n_flag_missing,
        "n_dropped_missing_field": n_missing_field,
    }
    boot = a1_ratio_bootstrap(comps, stats, units, n_boot=n_boot, seed=seed)
    out["status"] = boot["status"]
    if boot["status"] != "ok":
        out["error"] = boot.get("error")
        return out
    for name in stats:
        if name == "share_of_rise_from_handoff":
            st = boot[name]
            out[name] = {
                "point": None if st["point"] is None else round(st["point"], 4),
                "ci95_scenario": None if st.get("ci95_scenario") is None
                else [round(v, 4) for v in st["ci95_scenario"]],
                "ci95_task": None if st.get("ci95_task") is None else [round(v, 4) for v in st["ci95_task"]],
                "n_resamples_rise_not_positive_scenario": st.get("n_undefined_scenario"),
                "n_resamples_rise_not_positive_task": st.get("n_undefined_task"),
            }
        else:
            out[name] = _as_pp(boot[name], units)
    out["share_interval_note"] = (
        "Percentile interval over resamples whose total rise is > 0. If the count of resamples "
        "with a non-positive rise exceeds 2.5% of B, the rise itself is unresolved and the share "
        "interval is not read.")
    return out


def am1_chord(
    arms: dict[str, dict[str, Any]],
    cost_report: Optional[dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§B3: residual q_arm − [q_floor + f·(q_ref − q_floor)] per (task_id, seed) shared by all
    three arms; f = (c̄_arm − c̄_floor) / (c̄_ref − c̄_floor) from the P2 cost report's
    per-arm mean non-cached planner tokens, a plug-in that is not resampled. Positive = the
    arm lies above the straight line from the one-plan floor to the planner acting alone."""
    floor, ref, cfield = A1_AM1_CHORD["floor"], A1_AM1_CHORD["reference"], A1_AM1_CHORD["cost_field"]
    out: dict[str, Any] = {"decision_bearing": False, "citation": f"{A1_AM1} §B3", "floor": floor,
                           "reference": ref, "cost_field": cfield,
                           "dev_claim": "docs/prereg_hj12_dev_20260922.md:38-40 (C2)", "arms": {}}
    costs = _cost_arms(cost_report)
    for label in A1_AM1_CHORD["arms"]:
        row: dict[str, Any] = {}
        absent = [a for a in (label, floor, ref) if a not in arms]
        if absent:
            out["arms"][label] = {"status": "arm_absent", "reason": f"no --arm for {absent}"}
            continue
        c = {name: (costs.get(name) or {}).get(cfield) if isinstance(costs.get(name), dict) else None
             for name in (label, floor, ref)}
        if cost_report is None or any(v is None for v in c.values()):
            out["arms"][label] = {"status": "not_computed",
                                  "reason": f"the cost report lacks {cfield} for {[k for k, v in c.items() if v is None] or 'every arm'}"}
            continue
        c_arm, c_floor, c_ref = float(c[label]), float(c[floor]), float(c[ref])
        if c_ref == c_floor:
            out["arms"][label] = {"status": "fraction_undefined",
                                  "reason": "floor and reference have the same mean cost"}
            continue
        f = (c_arm - c_floor) / (c_ref - c_floor)
        row.update(status="ok", cost_fraction=round(f, 6), cost_arm=round(c_arm, 3),
                   cost_floor=round(c_floor, 3), cost_reference=round(c_ref, 3))
        for metric in ("goal_pass", "tgc"):
            field = A1_METRIC_FIELDS[metric]
            ea, ef, er = arms[label]["episodes"], arms[floor]["episodes"], arms[ref]["episodes"]
            keys, diffs, missing = [], [], 0
            for key in sorted(set(ea) & set(ef) & set(er)):
                qa, qf, qr = ea[key].get(field), ef[key].get(field), er[key].get(field)
                if qa is None or qf is None or qr is None:
                    missing += 1
                    continue
                keys.append(key)
                diffs.append(float(qa) - (float(qf) + f * (float(qr) - float(qf))))
            series = {"keys": keys, "diffs": diffs}
            scen = a1_interval(series, "scenario", n_boot=n_boot, seed=seed)
            row[metric] = {
                "n_triples": len(diffs),
                "n_dropped_missing_field": missing,
                "scenario": _public(scen),
                "task": _public(a1_interval(series, "task", n_boot=n_boot, seed=seed)),
                "positive_means_above_chord": None if scen["point"] is None else bool(scen["point"] > 0),
            }
        out["arms"][label] = row
    return out


def am1_limit_rates(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """§D1: per arm, scored episodes that hit the 40-step limit."""
    out = {}
    for label, arm in sorted(arms.items()):
        n = arm["n_scored"]
        k = sum(1 for e in arm["episodes"].values() if e.get("error_type") == A1_LIMIT_ERROR)
        out[label] = {"n_scored": n, "n_limit": k, "limit_rate": round(k / n, 6) if n else None}
    return out


def am1_limit_split(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    field: str,
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§D2: the mean paired difference split over pairs where either arm hit the limit and pairs
    where neither did. Post-treatment -- hitting the limit is an outcome of the arm -- so it is a
    mechanism reading, never a corrected estimate. The two contributions sum to the whole."""
    comps: dict[tuple[str, int], tuple[float, ...]] = {}
    for key in sorted(set(left) & set(right)):
        a, b = left[key].get(field), right[key].get(field)
        if a is None or b is None:
            continue
        lim = 1.0 if A1_LIMIT_ERROR in (left[key].get("error_type"), right[key].get("error_type")) else 0.0
        d = float(a) - float(b)
        comps[key] = (d * lim, lim, d * (1.0 - lim), 1.0 - lim, d, 1.0)
    units = ("scenario", "task")
    stats = {"all": (4, 5), "contribution_limit_pairs": (0, 5), "contribution_neither": (2, 5),
             "mean_on_limit_pairs": (0, 1), "mean_on_neither": (2, 3)}
    out: dict[str, Any] = {
        "post_treatment": True,
        "not_a_corrected_estimate": True,
        "n_pairs": len(comps),
        "n_limit_pairs": int(sum(c[1] for c in comps.values())),
        "n_neither": int(sum(c[3] for c in comps.values())),
        "n_limit_left": sum(1 for k in comps if left[k].get("error_type") == A1_LIMIT_ERROR),
        "n_limit_right": sum(1 for k in comps if right[k].get("error_type") == A1_LIMIT_ERROR),
    }
    boot = a1_ratio_bootstrap(comps, stats, units, n_boot=n_boot, seed=seed)
    out["status"] = boot["status"]
    if boot["status"] != "ok":
        out["error"] = boot.get("error")
        return out
    for name in stats:
        out[name] = _as_pp(boot[name], units)
    return out


def am1_limit_as_zero(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§D3: goal_pass of every `limit` episode set to 0 in both arms; the paired contrast again."""
    field = A1_METRIC_FIELDS["goal_pass"]

    def zeroed(eps: dict[tuple[str, int], dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
        return {k: (dict(e, **{field: 0.0}) if e.get("error_type") == A1_LIMIT_ERROR else e)
                for k, e in eps.items()}

    return {"sensitivity": True, "decision_bearing": False} | _public_contrast(
        a1_contrast(zeroed(left), zeroed(right), field, n_boot=n_boot, seed=seed))


def _load_by_fdr():
    """Lazy import of cluster_inference.by_fdr (Amendment 1 §F). None if absent."""
    if not CLUSTER_INFERENCE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("cluster_inference", CLUSTER_INFERENCE_PATH)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, "by_fdr", None)


def am1_by_fdr(entries: list[dict[str, Any]], alpha: float = A1_ALPHA) -> dict[str, Any]:
    """§F: Benjamini-Yekutieli over every printed goal_pass contrast's two-sided p at its
    threshold. A registered verdict carried by a rejection (supported or reversed) that the
    adjustment would withdraw is flagged in the same sentence; no verdict changes."""
    base = {"method": "Benjamini-Yekutieli", "alpha": alpha, "decision_bearing": False,
            "citation": f"{A1_AM1} §F"}
    usable = [e for e in entries if e.get("p") is not None]
    base["not_in_family"] = [e["id"] for e in entries if e.get("p") is None]
    try:
        fn = _load_by_fdr()
    except Exception as exc:  # a sensitivity: never fatal
        return {**base, "status": "import_error", "error": f"{type(exc).__name__}: {exc}"}
    if fn is None:
        return {**base, "status": "unavailable"}
    adjusted = fn([float(e["p"]) for e in usable])
    rows, flags = [], []
    for e, p_by in zip(usable, adjusted):
        row = {k: e[k] for k in ("id", "p", "threshold_pp", "source") if k in e} | {"p_by": p_by}
        verdict = e.get("verdict")
        if verdict is not None:
            row["registered_verdict"] = verdict
        if e.get("flaggable") and verdict in ("supported", "reversed"):
            survives = bool(p_by <= alpha)
            row["survives_by"] = survives
            flags.append({
                "id": e["id"],
                "survives_by": survives,
                "sentence": (f"{e['id']} {verdict}; "
                             + ("survives" if survives else "does NOT survive")
                             + f" Benjamini-Yekutieli across {len(usable)} contrasts (adjusted p = {p_by:.4f})."),
            })
        rows.append(row)
    return {**base, "status": "ok", "m": len(usable), "rows": rows, "flags": flags}


def am1_by_entries(
    results: list[dict[str, Any]],
    cf_results: list[dict[str, Any]],
    supporting_out: list[dict[str, Any]],
    exploratory_out: list[dict[str, Any]],
    handoff_ni: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """§F's family: P1, P3-P6 (and any other contrast prediction given), CF1, S1-S5, E1-E5 with
    each CF contrast counted once as its E-row, and the B1 contrasts at the −7.00 pp margin."""
    entries: list[dict[str, Any]] = []
    for r in results + cf_results:
        if r.get("kind") != "paired_contrast":
            continue
        entries.append({"id": r["id"], "p": r.get("p_value_two_sided"), "threshold_pp": r["threshold_pp"],
                        "verdict": r.get("verdict"), "source": "predictions",
                        # P5 is supported by a NON-rejection, so an adjusted p cannot withdraw it.
                        "flaggable": r.get("rule") != "not_positive_excluding_zero"})
    counted = {r.get("same_contrast_as") for r in cf_results}
    for rows, source in ((supporting_out, "supporting_contrasts"), (exploratory_out, "exploratory_contrasts")):
        for r in rows:
            if r.get("kind", "paired") == "handoff_depth" or r["id"] in counted:
                continue
            gp = r.get("goal_pass") if isinstance(r.get("goal_pass"), dict) else {}
            entries.append({"id": r["id"], "p": gp.get("p_value_two_sided_at_0"), "threshold_pp": 0.0,
                            "source": source})
    for r in handoff_ni:
        gp = r.get("goal_pass") if isinstance(r.get("goal_pass"), dict) else {}
        entries.append({"id": r["id"], "p": gp.get("p_value_two_sided_at_margin"),
                        "threshold_pp": A1_AM1_NI_MARGIN_PP, "source": "amendment1.handoff_only_ni"})
    return entries


def am1_block(
    *,
    preds: list[dict[str, Any]],
    results: list[dict[str, Any]],
    cf_results: list[dict[str, Any]],
    cf_multiplicity: dict[str, Any],
    cf_key_exclusion: Optional[dict[str, Any]],
    arms: dict[str, dict[str, Any]],
    handoff_flags: dict[str, dict[tuple[str, int], Optional[bool]]],
    supporting_out: list[dict[str, Any]],
    exploratory_out: list[dict[str, Any]],
    cost_report: Optional[dict[str, Any]],
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Everything Amendment 1 adds, in one report key. Only CF1 is decision-bearing."""
    secondary = [am1_evaluate_cf_secondary(s, arms, n_boot=n_boot, seed=seed) for s in A1_AM1_CF_SECONDARY]
    cf1 = cf_results[0] if cf_results else {}
    cf_arms = (cf1.get("left"), cf1.get("right"))
    not_run = any(a not in arms for a in cf_arms)
    for r in cf_results:
        r["reading"] = r.get("readings", {}).get(r.get("verdict"))
    cf = {
        "family": "CF",
        "citation": f"{A1_AM1} §C",
        "status": "not_run" if not_run else "run",
        "not_run_rule": "if arms 11 and 12 cannot complete (A1 §9 abort rule), CF is reported as not run",
        "multiplicity": cf_multiplicity,
        "key_exclusion": cf_key_exclusion,
        "predictions": cf_results,
        "verdicts": {r["id"]: r.get("verdict") for r in cf_results},
        "secondary": secondary,
    }
    handoff_ni = [am1_handoff_ni(s, arms, handoff_flags, n_boot=n_boot, seed=seed) for s in A1_AM1_HANDOFF_NI]
    decomposition = {}
    for receiver, (target, base) in A1_AM1_DECOMPOSITION.items():
        if target not in arms or base not in arms:
            decomposition[receiver] = {"target": target, "base": base, "status": "arm_absent"}
            continue
        decomposition[receiver] = {"target": target, "base": base} | {
            metric: am1_decomposition(arms[target]["episodes"], arms[base]["episodes"],
                                      handoff_flags.get(target, {}), A1_METRIC_FIELDS[metric],
                                      n_boot=n_boot, seed=seed)
            for metric in ("goal_pass", "tgc")}
    b4_extra: dict[str, Any] = {}
    s5 = next((s for s in A1_SUPPORTING if s["id"] == "S5"), None)
    if s5 and s5["left"] in arms and s5["right"] in arms:
        b4_extra["S5_handoff_only"] = {"target": s5["left"], "base": s5["right"]} | a1_handoff_depth(
            arms[s5["left"]]["episodes"], arms[s5["right"]]["episodes"], handoff_flags.get(s5["left"], {}),
            A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
    specs = {p["id"]: p for p in preds} | {p["id"]: p for p in A1_AM1_CF} | {
        s["id"]: s for s in A1_AM1_CF_SECONDARY}
    split, as_zero = {}, {}
    for cid in A1_AM1_LIMIT_IDS:
        spec = specs.get(cid)
        if spec is None or spec["left"] not in arms or spec["right"] not in arms:
            split[cid] = as_zero[cid] = {"status": "arm_absent"}
            continue
        le, re_ = arms[spec["left"]]["episodes"], arms[spec["right"]]["episodes"]
        split[cid] = {"left": spec["left"], "right": spec["right"]} | am1_limit_split(
            le, re_, A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
        as_zero[cid] = {"left": spec["left"], "right": spec["right"]} | am1_limit_as_zero(
            le, re_, n_boot=n_boot, seed=seed)
    return {
        "citation": A1_AM1,
        "what": "pre-data additions after the adversarial review; only CF1 is decision-bearing",
        "cf": cf,
        "handoff_only_ni": handoff_ni,
        "decomposition": decomposition,
        "chord": am1_chord(arms, cost_report, n_boot=n_boot, seed=seed),
        "b4_companions": A1_AM1_B4_COMPANIONS,
        "b4_extra": b4_extra,
        "limits": {"citation": f"{A1_AM1} §D", "rates": am1_limit_rates(arms),
                   "split": split, "limit_as_zero": as_zero},
        "p1_reporting_constraint": A1_AM1_P1_CONSTRAINT,
        "multiplicity_sensitivity": am1_by_fdr(
            am1_by_entries(results, cf_results, supporting_out, exploratory_out, handoff_ni)),
    }


def _strip_internal(obj: Any) -> Any:
    """Drop every key starting with '_' at any depth (bootstrap samples kept for p values)."""
    if isinstance(obj, dict):
        return {k: _strip_internal(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_strip_internal(v) for v in obj]
    return obj


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
        return "refusing test_challenge: it is not read under A1 [docs/prereg_j10_amendment_20260924.md:546]"
    if split not in A1_SPLIT_N_TASKS:
        return f"unknown split {split!r}; A1 analyses dev (dry runs) or test_normal"
    if split == "test_normal" and not confirm:
        return (
            "refusing test_normal without --confirm-heldout-test-split: A1 is a single "
            "read [docs/prereg_j10_amendment_20260924.md:534-547]"
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
        if p.get("permutation_alternative", "two-sided") not in ("two-sided", "greater", "less"):
            raise ValueError(f"{path}: {p['id']}: permutation_alternative must be two-sided, greater or less")
        p.setdefault("holm_family", False)
        p.setdefault("role", "secondary")
    for s in support:
        kind = s.get("kind", "paired")
        need = {"paired": ("id", "left", "right"), "did": ("id", "left", "right"),
                "handoff_depth": ("id", "receivers")}.get(kind)
        if need is None:
            raise ValueError(f"{path}: supporting {s.get('id')!r}: unknown kind {kind!r}")
        missing = [k for k in need if k not in s]
        if missing:
            raise ValueError(f"{path}: supporting {s.get('id')!r} missing {missing}")
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
    exploratory: Optional[list[dict[str, Any]]] = None,
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
            row = a1_evaluate_cost_prediction(pred, cost_report, expected_n_tasks * len(seeds),
                                              n_boot=n_boot, seed=bootstrap_seed)
            if blocking and row.get("decidable"):
                row.update(decidable=False, verdict="refused_incomplete",
                           reason="the matrix itself is refused: " + "; ".join(reasons))
            results.append(row)
        else:
            results.append(a1_evaluate_contrast_prediction(pred, arms, n_boot=n_boot, seed=bootstrap_seed))
    multiplicity = a1_decide_family(results)
    # Amendment 1 §C: family CF is decided on its own list, so CF1 is a Holm family of one and
    # P1-P6's family (and `multiplicity`) is untouched.
    cf_preds = [dict(p) for p in A1_AM1_CF]
    cf_results = [a1_evaluate_contrast_prediction(p, arms, n_boot=n_boot, seed=bootstrap_seed)
                  for p in cf_preds]
    cf_multiplicity = a1_decide_family(cf_results)
    cf_key_exclusion: Optional[dict[str, Any]] = None

    # A1 §4.2: the primary keeps every pair; the planless keys are dropped in a sensitivity, and
    # a verdict that changes is on the boundary.
    planless = a1_planless_keys(arm_dirs, seeds)
    planless_cap = int(expected_n_tasks * len(seeds) * A1_PLANLESS_CAP_FRACTION)
    contingency: dict[str, Any] = {
        "rule": "A1 §4.2", "source_arm": A1_PLAN_SOURCE_ARM, "cap": planless_cap,
        "keys": None if planless is None else [f"{s}/{t}" for t, s in planless],
        "n_keys": None if planless is None else len(planless),
        "sensitivity": None,
    }
    if planless is None:
        contingency["note"] = f"{A1_PLAN_SOURCE_ARM} not given; the planless keys cannot be listed"
    elif planless:
        if len(planless) > planless_cap:
            reasons.append(f"planless_keys_above_cap:{len(planless)}>{planless_cap}")
        contingency["sensitivity"] = a1_key_exclusion_sensitivity(
            preds, results, arms, planless, n_boot=n_boot, seed=bootstrap_seed)
        a1_apply_key_exclusion(results, contingency["sensitivity"]["differs"])
        # Amendment 1 §C: §4.2 applies to CF1 as it applies to P6.
        cf_key_exclusion = a1_key_exclusion_sensitivity(
            cf_preds, cf_results, arms, planless, n_boot=n_boot, seed=bootstrap_seed)
        a1_apply_key_exclusion(cf_results, cf_key_exclusion["differs"])
    for r in results + cf_results:
        for key in [k for k in r if k.startswith("_")]:
            r.pop(key)

    # Handoff flags for every prefix arm and every handoff_depth target that was given.
    flag_labels = {a for a in arm_dirs if a in A1_PREFIX_ARMS} | {
        target for s in support if s.get("kind") == "handoff_depth"
        for target, _base in s["receivers"].values() if target in arm_dirs
    }
    handoff_flags = {a: a1_handoff_flags(arm_dirs[a]) for a in sorted(flag_labels)}
    no_handoff = {a: a1_no_handoff_counts(arms[a], handoff_flags[a], A1_PREFIX_ARMS.get(a))
                  for a in sorted(flag_labels)}
    supporting_out = [a1_evaluate_supporting(s, arms, handoff_flags, n_boot=n_boot, seed=bootstrap_seed)
                      for s in support]
    exploratory_out = [
        a1_evaluate_supporting(s, arms, handoff_flags, n_boot=n_boot, seed=bootstrap_seed)
        | {"exploratory": True}
        for s in (exploratory if exploratory is not None else A1_EXPLORATORY)
    ]
    sgc_out = {
        p["id"]: {"left": p["left"], "right": p["right"]}
        | a1_sgc(arms[p["left"]]["episodes"], arms[p["right"]]["episodes"], tasks, seeds)
        for p in preds
        if p["id"] in A1_SGC_PREDICTIONS and p["left"] in arms and p["right"] in arms
    }
    amendment1 = _strip_internal(am1_block(
        preds=preds, results=results, cf_results=cf_results, cf_multiplicity=cf_multiplicity,
        cf_key_exclusion=cf_key_exclusion, arms=arms, handoff_flags=handoff_flags,
        supporting_out=supporting_out, exploratory_out=exploratory_out, cost_report=cost_report,
        n_boot=n_boot, seed=bootstrap_seed))

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
    # Amendment 1 §C: CF1 is decision-bearing but its own family; its verdict is stated beside the
    # headline and does not move the exit code (arms 11-12 may abort under §9: CF is then not run).
    headline += ("" if headline.endswith(".") else ".") + " Amendment 1 CF1: " + (
        "not run" if amendment1["cf"]["status"] == "not_run"
        else str(amendment1["cf"]["verdicts"].get("CF1"))) + "."
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
        "stability_rule": {"id": "POOL-04", "window_pp": POOL04_WINDOW_PP, "seeds": list(POOL04_SEEDS),
                           "reported_bound": {"n_boot": POOL04_BIG_N, "seed": POOL04_BIG_SEED}},
        "permutation_rule": {
            "id": "A1 §5.5", "decision_bearing": False, "clusters": "scenario",
            "exact_max_patterns": 2 ** 20, "monte_carlo_patterns": 100_000, "seed": A1_BOOTSTRAP_SEED,
            "one_sided": {p["id"]: p["permutation_alternative"] for p in preds
                          if p.get("permutation_alternative", "two-sided") != "two-sided"},
        },
        "multiplicity": multiplicity,
        "planless_contingency": contingency,
        "arms": {
            label_: {k: v for k, v in arm.items() if k != "episodes"} | {"split_provenance": provenance[label_]}
            for label_, arm in arms.items()
        },
        "predictions": results,
        "verdicts": {r["id"]: r.get("verdict") for r in results},
        "supporting_contrasts": supporting_out,
        "exploratory_contrasts": exploratory_out,
        # §7 item 4, second half [A1:475-478]: per prefix arm, episodes with no handoff.
        "no_handoff_counts": no_handoff,
        # §7 item 7 [A1:481]: SGC for P1 and P6, descriptive.
        "sgc": sgc_out,
        # Amendment 1 (pre-data): family CF, handoff-only NI, decomposition, chord, limits,
        # the P1 reporting constraint and the BY-FDR sensitivity.
        "amendment1": amendment1,
        "ambiguities": A1_AMBIGUITIES,
        "crash_convention": (
            "error_type == 'crash' is not an outcome (dropped, counted, arm incomplete); "
            "limit / timeout / parse_error / api_error are scored outcomes."
        ),
    }
    return a1_hstar_companions(report, arms, arm_dirs, n_boot=n_boot, seed=bootstrap_seed), (0 if all_decided and not reasons else 1)


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


# ---- h* companions of A1 Amendment 1 §B (unit HSTAR, 2026-09-24) ----------------------------------
# handoff_occurred (renamed h_flag in these companions) is `effective_m < n_source_actions`
# (src/sidekick/prefix_source.py:184); the loop skips its live phase only when the replayed prefix is
# terminal (src/sidekick/systems/loop.py:743-756). h* -- the executor took control after the prefix,
# scripts/analysis/handoff_control.py -- is computed beside every flag-based handoff number as a new
# `*_hstar` key; no existing key or value changes. The code sits at the end of the file and is called
# from build_report_a1's return line, so that no line this file's citations name moves.
A1_HSTAR_ESTIMAND = ("Σ d·h / Σ h, d = left − right, h = h* of the left (prefix) episode: the executor "
                     "took control after the replayed prefix (scripts/analysis/handoff_control.py)")
A1_AM1_B4_COMPANIONS_HSTAR = {
    "P3": "amendment1.handoff_only_ni_hstar[B1a]",
    "P4": "supporting_contrasts[S6].goal_pass_hstar.untailored.handoff_only",
    "S3": "supporting_contrasts[S6].goal_pass_hstar.tailored.handoff_only",
    "S4": "amendment1.decomposition_hstar (both receivers)",
    "S5": "amendment1.b4_extra.S5_handoff_only_hstar",
    "E1": "amendment1.handoff_only_ni_hstar[B1b] (negated)",
}


def a1_hstar_companions(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Add the h* companions to an A1 report in place and return it. Information only: an error
    here is recorded under amendment1.hstar and never stops the registered analysis."""
    if report.get("refused") or not isinstance(report.get("amendment1"), dict):
        return report
    try:
        _a1_add_hstar(report, arms, arm_dirs, n_boot=n_boot, seed=seed)
    except Exception as exc:  # information only: never fatal
        report["amendment1"]["hstar"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}",
                                         "decision_bearing": False}
    return report


def _a1_add_hstar(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    *,
    n_boot: int,
    seed: int,
) -> None:
    from scripts.analysis import handoff_control as hc

    am1 = report["amendment1"]
    labels = sorted(a for a in (report.get("no_handoff_counts") or {}) if a in arm_dirs)
    controls = {a: hc.arm_control(Path(arm_dirs[a])) for a in labels}
    hstar = {a: {k: c[hc.HSTAR_NAME] for k, c in ctl.items()} for a, ctl in controls.items()}
    # The per-arm count table: n h_flag true, n live-but-unflagged, n terminal (over scored episodes).
    am1["handoff_control_counts"] = {
        a: {"m": A1_PREFIX_ARMS.get(a)} | hc.control_counts(controls[a], keys=arms[a]["episodes"].keys())
        for a in labels if a in arms}
    # §B1: handoff-only NI with h*.
    handoff_ni = []
    for spec in A1_AM1_HANDOFF_NI:
        row = am1_handoff_ni(spec, arms, hstar, n_boot=n_boot, seed=seed)
        row.update(estimand=A1_HSTAR_ESTIMAND, h=hc.HSTAR_NAME, citation=f"{A1_AM1} §B1 (h* companion)")
        handoff_ni.append(row)
    am1["handoff_only_ni_hstar"] = _strip_internal(handoff_ni)
    # §B2: the decomposition with h*.
    decomposition = {}
    for receiver, (target, base) in A1_AM1_DECOMPOSITION.items():
        if target not in arms or base not in arms:
            decomposition[receiver] = {"target": target, "base": base, "status": "arm_absent"}
            continue
        decomposition[receiver] = {"target": target, "base": base, "h": hc.HSTAR_NAME} | {
            metric: am1_decomposition(arms[target]["episodes"], arms[base]["episodes"], hstar.get(target, {}),
                                      A1_METRIC_FIELDS[metric], n_boot=n_boot, seed=seed)
            for metric in ("goal_pass", "tgc")}
    am1["decomposition_hstar"] = _strip_internal(decomposition)
    # §B4: S5's handoff-only companion, and S6 (every handoff_depth row) with h*.
    s5 = next((s for s in A1_SUPPORTING if s["id"] == "S5"), None)
    if s5 and s5["left"] in arms and s5["right"] in arms:
        am1.setdefault("b4_extra", {})["S5_handoff_only_hstar"] = _strip_internal(
            {"target": s5["left"], "base": s5["right"], "h": hc.HSTAR_NAME} | a1_handoff_depth(
                arms[s5["left"]]["episodes"], arms[s5["right"]]["episodes"], hstar.get(s5["left"], {}),
                A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed))
    for rows in (report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or []):
        for row in rows:
            if row.get("kind") != "handoff_depth":
                continue
            receivers = {}
            for name, (target, base) in row["receivers"].items():
                if target not in arms or base not in arms:
                    receivers[name] = {"target": target, "base": base, "status": "arm_absent"}
                    continue
                receivers[name] = {"target": target, "base": base, "h": hc.HSTAR_NAME} | a1_handoff_depth(
                    arms[target]["episodes"], arms[base]["episodes"], hstar.get(target, {}),
                    A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
            row["goal_pass_hstar"] = _strip_internal(receivers)
            targets = [t for t, _b in row["receivers"].values() if t in hstar]
            if len(targets) == 2:
                fa, fb = hstar[targets[0]], hstar[targets[1]]
                row["hstar_mismatch_between_receivers"] = sum(1 for k in set(fa) & set(fb) if fa[k] != fb[k])
    am1["b4_companions_hstar"] = A1_AM1_B4_COMPANIONS_HSTAR
    # §F with the B1 entries read through h*; every other entry is as in multiplicity_sensitivity.
    am1["multiplicity_sensitivity_hstar"] = am1_by_fdr(am1_by_entries(
        report.get("predictions") or [], (am1.get("cf") or {}).get("predictions") or [],
        report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or [],
        am1["handoff_only_ni_hstar"]))
    am1["hstar"] = {
        "status": "ok", "decision_bearing": False, "h_star": hc.DEFINITION, "h_flag": hc.FLAG_DEFINITION,
        "keys": ["amendment1.handoff_control_counts", "amendment1.handoff_only_ni_hstar",
                 "amendment1.decomposition_hstar", "amendment1.b4_extra.S5_handoff_only_hstar",
                 "supporting_contrasts[S6].goal_pass_hstar", "amendment1.b4_companions_hstar",
                 "amendment1.multiplicity_sensitivity_hstar"],
        "unchanged": "every flag-based key (h_flag) keeps its name and value",
    }


if __name__ == "__main__":
    raise SystemExit(main())
