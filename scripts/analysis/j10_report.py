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
POOL04_BIG_N = 200_000  # A1:301-302, "and at 200,000 resamples at 20260924"
POOL04_BIG_SEED = 20260924
CLUSTER_INFERENCE_PATH = Path(__file__).resolve().parent / "cluster_inference.py"
RAW_RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")

# Registered arms [A1 r2 §4: 1, 1b, 2-12]. The value is the config that produces the
# arm (None: no J10 config exists yet); its campaign id is j10_<label>_20260924. The
# labels are what --arm accepts, so an arm missing here cannot be reported unless a
# prediction names it -- which executor_alone_bplus (1b) does not. show_k10 (11) and
# advise_k10_neutral (12) carry no prediction either: A1 r3 completed P7 from an
# unresolved B2, so they appear only in the exploratory rows E2-E5 [A1:486-489].
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
    # P1's rule mirrored for a positive prediction (P6, A1:432-436). The events it receives
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
            "result [A1:358-359]."
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
        # A1 r2 §5.5 (A1:315): the sign-flip sensitivity is one-sided at the threshold for P3
        # only -- 'greater' on the differences shifted by +0.07 (cluster_inference.registered_signflip).
        "permutation_alternative": "greater",
        "statement": "prefix_m11 − planner_alone_cap81 on goal_pass has CI lower bound above −7.00 pp",
        "citation": f"{A1_PREREG}:361-382",
        "dev_reference": {
            "diff_pp": 4.75,
            "ci95_pp_scenario": [-1.16, 11.75],
            "source": A1_DEV_BASIS,
            "key": "contrasts.goal_pass_all_ceiling_c81_minus_c81_bp_m11 (negated here; A1 r2 quotes it stored, −4.75 [−11.75, +1.16], A1:367-368)",
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
            "key": "contrasts.goal_pass_all_c81_zs_m9_minus_c81_zs_m11 (stored −2.82 [−7.16, +1.55]; negated here, as r1 did silently -- A1 r2 quotes it stored, A1:391-392)",
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
        # A1:432-436 registers supported / not supported / reversed, as for P1.
        "rule": "positive_excludes_zero_with_reversal",
        "threshold_pp": 0.0,
        "holm_family": True,
        "statement": "takeover_k10 − advise_k10_fullctx on goal_pass is positive, 95% scenario CI excluding zero",
        "citation": f"{A1_PREREG}:416-443",
        "dev_reference": {
            "diff_pp": 6.69,
            # A1:422-423 (F4): 13.49 in the registered orientation; 13.48 was the reversed
            # contrast's bound negated, one order statistic away.
            "ci95_pp_scenario": [1.29, 13.49],
            "source": "campaign/results/hj13_c1_matched_trigger_20260923.report.json (CHAN-C1-02), "
                      "recomputed in the registered orientation by j8_frontier at seed 20260915",
            "key": "contrasts.goal_pass_all_advise_fullctx_k10_minus_takeover_k10 (stored reversed)",
            "bootstrap_seed": DEV_BASIS_BOOTSTRAP_SEED,
        },
    },
]

# A1 §6 "Supporting contrasts, registered but not decision-bearing" [A1:495-504], one
# row per line of r2's table, in its order and orientation. All on goal_pass, reported
# unadjusted and outside the Holm family [A1:295-296]. `kind` picks the estimand:
#   paired        left − right, paired on (task_id, seed), as every A1 contrast;
#   did           (left[0] − left[1]) − (right[0] − right[1]) per (task_id, seed), over
#                 the keys all four arms score;
#   handoff_depth per receiver, target − base restricted to episodes whose TARGET-depth
#                 episode handed off, as F-c: Σ d·h / Σ h with the whole scenario
#                 resampled (j16_robustness.decomposition, gain_on_handoff_subset).
A1_SUPPORTING: list[dict[str, Any]] = [
    # A1:499 "| `advise_k1 − prefix_m9` | −9.89 pp | [−17.79, −1.99] | dev basis |"
    {"id": "S1", "kind": "paired", "left": "advise_k1_fullctx", "right": "prefix_m9",
     "citation": f"{A1_PREREG}:499",
     "dev_reference": {"diff_pp": -9.89, "ci95_pp_scenario": [-17.79, -1.99], "source": "dev basis"}},
    # A1:500 "| `advise_k10 − prefix_m11` | −7.73 pp | [−12.60, −3.12] | dev basis |"
    {"id": "S2", "kind": "paired", "left": "advise_k10_fullctx", "right": "prefix_m11",
     "citation": f"{A1_PREREG}:500",
     "dev_reference": {"diff_pp": -7.73, "ci95_pp_scenario": [-12.60, -3.12], "source": "dev basis"}},
    # A1:501 "| `prefix_m11 − prefix_m9` (tailored depth) | +4.25 pp (171) | [+0.15, +8.75],
    # **on the boundary** (POOL-04) | j15 `t_depth_m9_m11` |"
    {"id": "S3", "kind": "paired", "left": "prefix_m11", "right": "prefix_m9",
     "label": "tailored depth", "citation": f"{A1_PREREG}:501",
     "dev_reference": {"diff_pp": 4.25, "ci95_pp_scenario": [0.15, 8.75], "n_pairs": 171,
                       "pool04": "on the boundary", "source": "j15 t_depth_m9_m11"}},
    # A1:502 "| `(m11 − m9)_tailored − (m11 − m9)_untailored` (R2) | +2.81 pp (171) |
    # [−2.57, +8.96] | POOL-03 |"
    {"id": "S4", "kind": "did", "left": ["prefix_m11", "prefix_m9"],
     "right": ["prefix_zs_m11", "prefix_zs_m9"], "label": "tailoring x depth (R2)",
     "citation": f"{A1_PREREG}:502",
     "dev_reference": {"diff_pp": 2.81, "ci95_pp_scenario": [-2.57, 8.96], "n_pairs": 171,
                       "source": "POOL-03"}},
    # A1:503 "| `prefix_m11 − executor_alone_bplus` (tailored floor → m11) | new arm | — | arm 1b |"
    {"id": "S5", "kind": "paired", "left": "prefix_m11", "right": "executor_alone_bplus",
     "label": "tailored floor -> m11", "citation": f"{A1_PREREG}:503", "dev_reference": None},
    # A1:504 "| handoff-only depth: m9 → m11 restricted to episodes where a handoff occurs at
    # m = 11 | reported for both receivers | — | F-c |"
    {"id": "S6", "kind": "handoff_depth", "label": "handoff-only depth m9 -> m11",
     "receivers": {"tailored": ["prefix_m11", "prefix_m9"],
                   "untailored": ["prefix_zs_m11", "prefix_zs_m9"]},
     "citation": f"{A1_PREREG}:504", "dev_reference": None},
]

# Not in r2's supporting table, so reported as exploratory [A1:295-296]. The ceiling −
# untailored m11 gap is the number behind the §4.1 sourcing correction [A1:191], which §7
# item 6 reports whether or not it helps [A1:525].
A1_EXPLORATORY: list[dict[str, Any]] = [
    {"id": "E1", "kind": "paired", "left": "planner_alone_cap81", "right": "prefix_zs_m11",
     "label": "ceiling − untailored m11 (sourcing correction)",
     "citation": f"{A1_PREREG}:191",
     "dev_reference": {"diff_pp": -2.95, "ci95_pp_scenario": [-8.65, 1.91], "n_pairs": 114}},
    # E2-E5: arms 11 and 12, exploratory because B2 was unresolved (A1 r3 §6 P7). Each is
    # B2's contrast in B2's orientation, with its dev value from
    # campaign/results/b2_decomposition_20260923.report.json `contrasts.D1`..`D4`.
    # A1:486 "| E2 | `takeover_k10 − show_k10` (D1) | +3.83 pp | [−1.56, +10.81] | `contrasts.D1` |"
    {"id": "E2", "kind": "paired", "left": "takeover_k10", "right": "show_k10",
     "label": "execution: takeover − show (B2 D1)", "citation": f"{A1_PREREG}:486",
     "dev_reference": {"diff_pp": 3.83, "ci95_pp_scenario": [-1.56, 10.81], "n_pairs": 171,
                       "source": "b2 contrasts.D1"}},
    # A1:487 "| E3 | `show_k10 − advise_k10_fullctx` (D2) | +2.30 pp | [−2.43, +7.31] | `contrasts.D2` |"
    {"id": "E3", "kind": "paired", "left": "show_k10", "right": "advise_k10_fullctx",
     "label": "prompt + content: show − advice (B2 D2)", "citation": f"{A1_PREREG}:487",
     "dev_reference": {"diff_pp": 2.30, "ci95_pp_scenario": [-2.43, 7.31], "n_pairs": 171,
                       "source": "b2 contrasts.D2"}},
    # A1:488 "| E4 | `advise_k10_neutral − advise_k10_fullctx` (D3) | +3.73 pp | [−0.06, +8.24] | `contrasts.D3` |"
    {"id": "E4", "kind": "paired", "left": "advise_k10_neutral", "right": "advise_k10_fullctx",
     "label": "advice prompt wording: neutral − registered (B2 D3)", "citation": f"{A1_PREREG}:488",
     "dev_reference": {"diff_pp": 3.73, "ci95_pp_scenario": [-0.06, 8.24], "n_pairs": 171,
                       "source": "b2 contrasts.D3"}},
    # A1:489 "| E5 | `takeover_k10 − advise_k10_neutral` (D4) | +2.40 pp | [−2.94, +8.89] | `contrasts.D4` |"
    {"id": "E5", "kind": "paired", "left": "takeover_k10", "right": "advise_k10_neutral",
     "label": "channel vs neutral advice: takeover − neutral (B2 D4)", "citation": f"{A1_PREREG}:489",
     "dev_reference": {"diff_pp": 2.40, "ci95_pp_scenario": [-2.94, 8.89], "n_pairs": 171,
                       "source": "b2 contrasts.D4"}},
]

# Prefix arms and their depth m, for §7 item 4's no-handoff counts [A1:520-523].
A1_PREFIX_ARMS: dict[str, int] = {"prefix_m9": 9, "prefix_m11": 11, "prefix_zs_m9": 9, "prefix_zs_m11": 11}

# §7 item 7: "SGC ... for P1 and P6, descriptive" [A1:526].
A1_SGC_PREDICTIONS = ("P1", "P6")

# Records of where A1's text and this script had to meet. `status` is
# "resolved_by_r2" when r2 now says what the script does (the r1 text that raised it
# is cited at A1_PREREG_R1). A record whose r2 text the script did not yet implement
# was "open" and is removed once the code implements it: P6 reversed, the P2 ratio
# interval, the POOL-04 200k bound, the §5.5 sign-flip rule and r2's supporting table
# all are now. r1's `p6_arm_not_registered` is gone: r2 registers arm 10 and P6
# [A1:141, 416-436].
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
    """§7 item 4 [A1:520-523]: over an arm's scored episodes, how many handed off at m."""
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
    """(scenario, seed) -> 1.0 if every task of the scenario passed, else 0.0 [A1:526].

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
    r2 registers no interval or test for it [A1:526]."""
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
    """target − base on the target depth's handoff episodes and on all episodes [A1:504, 521-523].

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
    """P2's token ratio with a scenario-clustered interval, as information [A1:343, 291].

    The verdict stays on the arm means [A1:341]. The interval is F-f's
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
    # A1:300-302: the fired bound is also recomputed at 200,000 resamples at 20260924 and
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
    left, right = a1_am5_pair(arms, pred["left"], pred["right"])
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
    incomplete = [a for a, arm in ((pred["left"], left), (pred["right"], right)) if not arm["complete"]]
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


def _a1_build_report_core(  # unit R2: the former build_report_a1, renamed in place; build_report_a1 is at the end
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
) -> tuple[Any, ...]:  # (report, exit code, arms); a refusal is (report, 2)
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
    arms = a1_am5_arms({label: a1_r2_scored_as_recorded(a1_arm_episodes(label, blob, tasks, seeds), blob) for label, blob in loaded.items()}, arm_dirs, tasks, seeds, preds, reasons)  # unit R2 B7
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
            row = a1_am5_cost_prediction(pred, cost_report, expected_n_tasks * len(seeds), arms,
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
        # §7 item 4, second half [A1:520-523]: per prefix arm, episodes with no handoff.
        "no_handoff_counts": no_handoff,
        # §7 item 7 [A1:526]: SGC for P1 and P6, descriptive.
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
    return a1_am5_divergence(a1_am4_calls(a1_hstar_companions(report, arms, arm_dirs, n_boot=n_boot, seed=bootstrap_seed), a1_am5_p2_arms(arms), arm_dirs, a1_am5_p2_cost(arms, cost_report)), arms, cost_report, n_boot=n_boot, seed=bootstrap_seed), (0 if all_decided and not reasons else 1), arms


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
        preds, support = load_predictions(a1_r2_predictions_path(args))  # unit R2 A2: none on test_normal
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
        print(json.dumps(_a1_r2_refused(args.split, str(exc))[0], indent=2))  # unit R2: status, split, verdicts
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


# The __main__ guard is the last statement of the file: the Amendment 4 companion below is appended
# after main() so that no line this file's citations name moves (unit ATTRIB, 2026-09-25).


# ---- Amendment 4 companion: planner calls live and attributed (unit ATTRIB, 2026-09-25) -------------
# A replayed plan (usage.provider "cache", src/sidekick/agents/planner.py:930-941) is charged one planner
# call (src/sidekick/systems/loop.py:383,465) and, in the j12 cost report, 0 tokens and $0. The prefix
# arms are charged their replayed prefix on every axis (A1:347-349). Amendment 4 reads P2's calls and
# tokens clauses under both conventions. The code sits at the end of the file and is called from build_report_a1's
# return line, as the h* companions are; no existing key or value changes, and an error here is recorded
# under a1_am4_calls and never stops the registered analysis.
A1_AM4_ARMS = (
    "sft_plan",  # arm 2
    "planner_alone_cap81",  # arm 3
    "prefix_m9", "prefix_m11", "prefix_zs_m9", "prefix_zs_m11",  # arms 4-7
    "advise_k1_fullctx", "advise_k10_fullctx", "takeover_k10", "show_k10", "advise_k10_neutral",  # arms 8-12
)
A1_AM4_P2 = ("advise_k1_fullctx", "prefix_m11")
A1_AM4_NOTE = "Amendment 4: P2's calls clause is supported only if it holds under both conventions"
A1_AM4_TOKENS_NOTE = ("Amendment 4: P2's tokens clause (at least min_ratio x prefix_m11's non-cached planner "
                      "tokens) is supported only if it holds under both conventions")
A1_AM4_DEFINITIONS = {
    "calls_attributed": "result.json n_planner_calls: the count as published (a replayed plan is one call)",
    "calls_live": ("calls_attributed minus usage.n_calls of the episode's own planner events with "
                   "usage.provider == 'cache', events after the last run_start"),
    "prefix_arm": "charged its replayed prefix under both conventions (A1:347-349)",
    "tokens_as_published": ("--cost-report arms.<arm>.noncached_tokens_per_episode (j12_cost_axes; a replayed "
                            "plan at 0 tokens); the 'live' convention of p2_tokens_clause"),
    "tokens_attributed": ("mean over the cost report's per-episode rows of noncached_tokens_per_episode plus "
                          "each replayed plan's source plan-event tokens (j12_cost_axes.episode_cached_plan_attribution)"),
    "usd_as_published": "--cost-report arms.<arm>.usd_per_episode (j12_cost_axes; a replayed plan at $0)",
    "usd_attributed": ("mean over the cost report's per-episode rows of usd_per_episode plus each replayed "
                       "plan priced from its source plan event (j12_cost_axes.episode_cached_plan_attribution)"),
    "sft_plan": "arm 2's rows already carry its source plan event in the cost report and get nothing added",
    "episodes": "calls over A1's scored episodes (crashes excluded); tokens and USD over the cost report's rows",
}
J12_COST_AXES_PATH = Path(__file__).resolve().parent / "j12_cost_axes.py"
_J12_MODULE: Any = None


def _load_j12() -> Any:
    """Lazy import of j12_cost_axes, for its replayed-plan reader and pricing (reused, not reimplemented)."""
    global _J12_MODULE
    if _J12_MODULE is None:
        spec = importlib.util.spec_from_file_location("j12_cost_axes", J12_COST_AXES_PATH)
        if spec is None or spec.loader is None:
            raise ImportError(str(J12_COST_AXES_PATH))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _J12_MODULE = module
    return _J12_MODULE


def a1_am4_episode_files(root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    """(task_id, seed) -> n_planner_calls, system and events path for every result.json under an arm.

    The first result.json per key wins, as in load_arm_tree and a1_handoff_flags.
    """
    files: dict[tuple[str, int], dict[str, Any]] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("result.json")):
        row, _err = _read_result(path)
        if row is None or row.get("task_id") is None or row.get("seed") is None:
            continue
        key = (str(row["task_id"]), int(row["seed"]))
        if key not in files:
            files[key] = {"n_planner_calls": optional_int(row, "n_planner_calls"), "system": row.get("system"),
                          "events": path.parent / "events.jsonl"}
    return files


def _a1_am4_price_card(j12: Any, cost_report: Optional[dict[str, Any]]) -> dict[str, Any]:
    """The cost report's own price card (prices_source), else j12's default."""
    source = (cost_report or {}).get("prices_source")
    path = Path(source) if source else j12.DEFAULT_PRICES_PATH
    if not path.is_absolute():
        path = j12.REPO_ROOT / path
    return j12.load_price_card(path if path.is_file() else j12.DEFAULT_PRICES_PATH)


def a1_am4_arm(
    label: str,
    arm: dict[str, Any],
    root: Path,
    cost_arm: Optional[dict[str, Any]],
    j12: Any,
    models_prices: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """One arm's per_arm block of a1_am4_calls, and the reasons any value in it is null."""
    files = a1_am4_episode_files(Path(root))
    cache: dict[tuple[str, int], dict[str, Any]] = {}
    notes: list[str] = []

    def attribution(key: tuple[str, int]) -> Optional[dict[str, Any]]:
        if key not in cache and key in files:
            cache[key] = j12.episode_cached_plan_attribution(files[key]["events"], models_prices,
                                                             task_id=key[0], seed=key[1])
        return cache.get(key)

    calls_attributed: list[float] = []
    calls_live: list[float] = []
    n_cached = 0
    for key in sorted(arm["episodes"]):
        att = attribution(key)
        calls = files.get(key, {}).get("n_planner_calls")
        if att is None or calls is None:
            notes.append(f"{key[0]}/{key[1]}: no n_planner_calls")
            continue
        n_cached += att["n_cached_plan_events"]
        calls_attributed.append(float(calls))
        calls_live.append(float(calls - att["cache_calls"]))
    rows = (cost_arm or {}).get("episodes")
    attributed: dict[str, Optional[float]] = {"tokens": None, "usd": None}
    if cost_arm is None:
        notes.append("no cost-report row for this arm")
    elif not isinstance(rows, list) or not rows:
        notes.append("cost report has no per-episode rows (arms.<arm>.episodes from j12_cost_axes)")
    else:
        for name, field, extra_key in (("tokens", "noncached_tokens_per_episode", "noncached_tokens"),
                                       ("usd", "usd_per_episode", "usd")):
            values: list[float] = []
            for r in rows:
                if r.get(field) is None:
                    continue
                key = (str(r["task_id"]), int(r["seed"]))
                extra = 0.0
                if not j12._nc.is_sft_plan_row({"system": files.get(key, {}).get("system")}, label):
                    att = attribution(key)
                    if att is None or att["n_source_missing"]:
                        notes.append(f"{key[0]}/{key[1]}: replayed plan without a readable source plan event")
                        values = []
                        break
                    extra = att[extra_key]
                values.append(float(r[field]) + extra)
            attributed[name] = round(statistics.fmean(values), 6) if values else None
    block = {
        "n_episodes": len(arm["episodes"]),
        "calls_attributed_mean": round(statistics.fmean(calls_attributed), 6) if calls_attributed else None,
        "calls_live_mean": round(statistics.fmean(calls_live), 6) if calls_live else None,
        "n_cached_plan_events": n_cached,
        "tokens_attributed_mean": attributed["tokens"],
        "tokens_as_published_mean": (cost_arm or {}).get("noncached_tokens_per_episode"),
        "usd_attributed_mean": attributed["usd"],
        "usd_as_published_mean": (cost_arm or {}).get("usd_per_episode"),
    }
    return block, list(dict.fromkeys(notes))


def a1_am4_p2_calls_clause(per_arm: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """P2's calls clause (advise_k1 strictly more hosted calls than prefix_m11) under both conventions."""
    left, right = A1_AM4_P2
    x = (per_arm.get(left) or {}).get("calls_attributed_mean")
    x_live = (per_arm.get(left) or {}).get("calls_live_mean")
    y = (per_arm.get(right) or {}).get("calls_attributed_mean")
    if x is None or x_live is None or y is None:
        return {"attributed": None, "live": None, "holds_both": None, "note": A1_AM4_NOTE,
                "status": f"not_computed: {left} or {right} absent or without calls"}
    return {
        "attributed": {"advise_k1": x, "prefix_m11": y, "holds": x > y},
        "live": {"advise_k1": x_live, "prefix_m11": y, "holds": x_live > y},
        "holds_both": bool(x > y and x_live > y),
        "note": A1_AM4_NOTE,
    }


def a1_am4_p2_tokens_clause(per_arm: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """P2's tokens clause (advise_k1 at least min_ratio x prefix_m11's non-cached planner tokens, A1:340)
    under both conventions: attributed, and live (as published: a replayed plan at 0 tokens). The prefix
    arm is charged its replayed prefix in both."""
    left, right = A1_AM4_P2
    min_ratio = float(next((p["min_ratio"] for p in A1_PREDICTIONS if p["id"] == "P2"), 2.0))
    x = (per_arm.get(left) or {}).get("tokens_attributed_mean")
    x_live = (per_arm.get(left) or {}).get("tokens_as_published_mean")
    y = (per_arm.get(right) or {}).get("tokens_attributed_mean")
    if x is None or x_live is None or not y:
        return {"attributed": None, "live": None, "holds_both": None, "min_ratio": min_ratio,
                "note": A1_AM4_TOKENS_NOTE,
                "status": f"not_computed: {left} or {right} absent or without per-episode token rows"}
    r_attr, r_live = x / y, x_live / y
    return {
        "attributed": {"advise_k1": x, "prefix_m11": y, "ratio": round(r_attr, 6), "holds": r_attr >= min_ratio},
        "live": {"advise_k1": x_live, "prefix_m11": y, "ratio": round(r_live, 6), "holds": r_live >= min_ratio},
        "holds_both": bool(r_attr >= min_ratio and r_live >= min_ratio),
        "min_ratio": min_ratio,
        "note": A1_AM4_TOKENS_NOTE,
    }


def a1_am4_calls(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    cost_report: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Add the top-level a1_am4_calls block to an A1 report in place and return it. Information for
    Amendment 4's reading of P2: an error here is recorded, never fatal, and no other key changes."""
    if report.get("refused"):
        return report
    try:
        j12 = _load_j12()
        models = _a1_am4_price_card(j12, cost_report)["models"]
        cost_arms = _cost_arms(cost_report)
        per_arm: dict[str, dict[str, Any]] = {}
        notes: dict[str, list[str]] = {}
        for label in A1_AM4_ARMS:
            if label not in arms or label not in arm_dirs:
                continue
            per_arm[label], arm_notes = a1_am4_arm(label, arms[label], Path(arm_dirs[label]),
                                                   cost_arms.get(label), j12, models)
            if arm_notes:
                notes[label] = arm_notes[:5] + ([f"... {len(arm_notes) - 5} more"] if len(arm_notes) > 5 else [])
        report["a1_am4_calls"] = {
            "status": "ok",
            "definitions": A1_AM4_DEFINITIONS,
            "per_arm": per_arm,
            "p2_calls_clause": a1_am4_p2_calls_clause(per_arm),
            "p2_tokens_clause": a1_am4_p2_tokens_clause(per_arm),
            "notes": notes,
        }
    except Exception as exc:  # information only: never fatal
        report["a1_am4_calls"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    return report


# ---- Amendment 5: a replay that cannot pass its own check (unit DIVRULE, 2026-09-25) ------------------------
# A prefix arm (4-7) whose replayed world fails its hash check crashes with payload.reason "replay_divergence"
# on every attempt (Amendment 5 §A). §B: such a key -- scripts/analysis/replay_divergence.py holds the one
# definition that J10, J11 and J12 read -- leaves BOTH arms of every contrast, companion and sensitivity that
# uses its arm (the union when both arms are replay arms); an arm whose only crashes are divergent keys is
# complete, and a contrast that removes at most 16 keys is read on its remaining pairs, above that it is
# incomplete. Everything else runs as registered. The code sits at the end of the file and is hooked in by
# editing existing lines in place -- build_report_a1's arms line, P2's call and its return line, and
# a1_evaluate_contrast_prediction's pair and completeness lines -- so no line this file's citations name moves.
# With no divergent key every hook hands back its input unchanged and only the a1_am5_divergence block is added.
A1_AM5 = f"{A1_PREREG} Amendment 5"
A1_AM5_PRIVATE = "_am5_divergent"  # on a replay arm's dict, and only when it has a divergent key
A1_AM5_NONREPLAY = "_am5_divergent_non_replay"  # impossible by construction; an ordinary crash if seen
A1_AM5_COST_FIELDS = ("noncached_tokens_per_episode", "hosted_calls_per_episode", "usd_per_episode")
A1_AM5_NOTES = (
    "Paired statistics pair on the (task_id, seed) keys both arms score, and a divergent key is a crash, "
    "which a1_arm_episodes already drops from its replay arm; so removing it from the other arm changes no "
    "paired statistic, only the counts of unpaired keys (n_left_only / n_right_only) and completeness.",
    "Amendment 5 §B.1's 'after at least one crash-only resumption' cannot be read from an arm's files: the "
    "refill deletes a crashed episode's directory whole (scripts/setup/campaign_summarize.py purge_crashed) "
    "and re-runs it, so a divergent key is read as a crash whose last attempt holds the divergence error; "
    "the wrapper's tally lines record the resumption.",
    "P2 and Amendment 4's P2 clauses are read from the cost report's per-episode rows without the removed "
    "keys; B3's cost plug-in likewise for a replay arm with divergent keys.",
)


def _load_replay_divergence() -> Any:
    """Lazy import of scripts/analysis/replay_divergence.py (an import at the top would move cited lines)."""
    from scripts.analysis import replay_divergence as rd  # noqa: E402

    return rd


def a1_am5_arms(
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    tasks: list[str],
    seeds: list[int],
    contrasts: Iterable[dict[str, Any]] = (),
    reasons: Optional[list[str]] = None,
    *,
    replay_arms: Iterable[str] = tuple(A1_PREFIX_ARMS),
) -> dict[str, dict[str, Any]]:
    """§B.1 and §B.3 on a1_arm_episodes' arms, in place; returns them.

    A replay arm with divergent keys in the registered matrix carries them as `_am5_divergent`, and is marked
    complete when they are its only crashes and nothing else keeps it incomplete (no missing episode; no
    empty, unreadable or duplicate result; its root exists). For each contrast in `contrasts` (id / left /
    right) that would remove more than the cap, one reason is appended to `reasons`. A divergent key in an arm
    not in `replay_arms` cannot occur; if one does it is kept as `_am5_divergent_non_replay`, reported, and
    stays an ordinary crash. An arm without a crash is not scanned."""
    rd = _load_replay_divergence()
    replay = set(replay_arms)
    matrix = {(t, s) for t in tasks for s in seeds}
    for label, arm in arms.items():
        if not arm.get("n_crash") or label not in arm_dirs:
            continue
        keys = [k for k in rd.divergent_keys(Path(arm_dirs[label])) if k in matrix and k not in arm["episodes"]]
        if not keys:
            continue
        if label not in replay:
            arm[A1_AM5_NONREPLAY] = keys
            continue
        arm[A1_AM5_PRIVATE] = keys
        if (arm["n_crash"] == len(keys) and arm["n_missing"] == 0 and not arm["n_empty_files"]
                and not arm["n_unreadable"] and not arm["n_duplicates"] and not arm["root_missing"]
                and arm["n_scored"] + len(keys) == arm["n_expected"]):
            arm["complete"] = True
    if reasons is not None:
        for spec in contrasts:
            left, right = spec.get("left"), spec.get("right")
            if not isinstance(left, str) or not isinstance(right, str) or left not in arms or right not in arms:
                continue
            excluded, verdict = a1_am5_exclusion(arms, left, right)
            if verdict != rd.VERDICT_OK:
                reasons.append(f"replay_divergence_above_cap:{spec.get('id')}={len(excluded)}>{rd.DIVERGENCE_CAP}")
    return arms


def a1_am5_exclusion(arms: dict[str, dict[str, Any]], left: str, right: str) -> tuple[list[tuple[str, int]], str]:
    """(keys that leave both arms of left − right, 'ok' | 'over_cap'), from the arms' `_am5_divergent` lists."""
    rd = _load_replay_divergence()
    divergent = {a: (arms.get(a) or {}).get(A1_AM5_PRIVATE) or [] for a in (left, right)}
    return rd.contrast_exclusion(divergent, left, right)


def a1_am5_pair(
    arms: dict[str, dict[str, Any]], left: str, right: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """§B.2-§B.3 for one contrast: both arms without the contrast's divergent keys. Above the cap every arm that
    contributes a key is incomplete for this contrast. With no divergent key: the two arm dicts themselves."""
    la, ra = arms[left], arms[right]
    if not la.get(A1_AM5_PRIVATE) and not ra.get(A1_AM5_PRIVATE):
        return la, ra
    excluded, verdict = a1_am5_exclusion(arms, left, right)
    gone = set(excluded)
    over = verdict != _load_replay_divergence().VERDICT_OK

    def view(arm: dict[str, Any]) -> dict[str, Any]:
        return dict(arm, episodes={k: v for k, v in arm["episodes"].items() if k not in gone},
                    complete=bool(arm["complete"] and not (over and arm.get(A1_AM5_PRIVATE))))

    return view(la), view(ra)


def _a1_am5_row_key(row: Any) -> Optional[tuple[str, int]]:
    try:
        return (str(row["task_id"]), int(row["seed"]))
    except (KeyError, TypeError, ValueError):
        return None


def a1_am5_cost_view(
    cost_report: Optional[dict[str, Any]],
    labels: Iterable[str],
    excluded: Iterable[tuple[str, int]],
) -> tuple[dict[str, Any], list[str]]:
    """The cost report with `labels`' per-episode rows minus `excluded` and their means recomputed from the rows
    kept (j12_cost_axes' rounding, 6 places); n_episodes is the rows kept. Also the labels that have no
    per-episode rows, whose values are left as published."""
    gone = set(excluded)
    arms_c = dict(_cost_arms(cost_report))
    no_rows: list[str] = []
    for label in labels:
        arm = arms_c.get(label)
        if not isinstance(arm, dict):
            continue
        rows = arm.get("episodes")
        if not isinstance(rows, list):
            no_rows.append(label)
            continue
        kept = [r for r in rows if _a1_am5_row_key(r) not in gone]
        new = dict(arm, episodes=kept, n_episodes=len(kept))
        for field in A1_AM5_COST_FIELDS:
            if field in arm and any(isinstance(r, dict) and field in r for r in rows):
                values = [float(r[field]) for r in kept if isinstance(r, dict) and r.get(field) is not None]
                new[field] = round(statistics.fmean(values), 6) if values else None
        arms_c[label] = new
    return dict(cost_report or {}, arms=arms_c), no_rows


def a1_am5_cost_prediction(
    pred: dict[str, Any],
    cost_report: Optional[dict[str, Any]],
    expected_n: int,
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int = A1_BOOTSTRAP_N,
    seed: int = A1_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """P2 under §B. With a divergent key in its arms, P2 is read on the cost report's per-episode rows without
    the removed keys, at expected_n minus their number; above the cap, or with no per-episode rows to remove
    them from, it is refused as incomplete. Without a divergent key: a1_evaluate_cost_prediction, unchanged."""
    excluded, verdict = a1_am5_exclusion(arms, pred.get("left"), pred.get("right"))
    if not excluded or cost_report is None:
        return a1_evaluate_cost_prediction(pred, cost_report, expected_n, n_boot=n_boot, seed=seed)
    rd = _load_replay_divergence()
    view, no_rows = a1_am5_cost_view(cost_report, (pred["left"], pred["right"]), excluded)
    if no_rows:
        row = a1_evaluate_cost_prediction(pred, cost_report, expected_n, n_boot=n_boot, seed=seed)
        why = (f"{A1_AM5} §B.2: {len(excluded)} divergent key(s) cannot be removed from {no_rows}: the cost "
               "report has no per-episode rows (arms.<label>.episodes from j12_cost_axes)")
    else:
        row = a1_evaluate_cost_prediction(pred, view, expected_n - len(excluded), n_boot=n_boot, seed=seed)
        why = (None if verdict == rd.VERDICT_OK
               else f"{A1_AM5} §B.3: {len(excluded)} divergent keys to remove > cap {rd.DIVERGENCE_CAP}")
    if why and row.get("decidable"):
        row.update(decidable=False, verdict="refused_incomplete", reason=why)
    return row


def a1_am5_p2_arms(arms: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Amendment 4's P2 reading under §B: P2's two arms without P2's divergent keys (`arms` itself without any)."""
    left, right = A1_AM4_P2
    if left not in arms or right not in arms:
        return arms
    excluded, _verdict = a1_am5_exclusion(arms, left, right)
    if not excluded:
        return arms
    gone = set(excluded)
    out = dict(arms)
    for label in (left, right):
        out[label] = dict(arms[label], episodes={k: v for k, v in arms[label]["episodes"].items() if k not in gone})
    return out


def a1_am5_p2_cost(
    arms: dict[str, dict[str, Any]], cost_report: Optional[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    """The cost report Amendment 4 reads under §B: P2's two arms without P2's divergent keys (unchanged without any)."""
    left, right = A1_AM4_P2
    excluded, _verdict = a1_am5_exclusion(arms, left, right)
    if not excluded or cost_report is None:
        return cost_report
    return a1_am5_cost_view(cost_report, (left, right), excluded)[0]


def _a1_am5_companion(entries: dict[str, Any], name: str, labels: Iterable[str], n_pairs: Any,
                      arms: dict[str, dict[str, Any]]) -> None:
    """One companion row of the block, if any of its arms has a divergent key."""
    labels = [a for a in labels if isinstance(a, str)]
    keys = sorted({k for a in labels for k in (arms.get(a) or {}).get(A1_AM5_PRIVATE) or []})
    if keys:
        entries[name] = {"arms": labels, "n_excluded": len(keys), "n_pairs": n_pairs}


def a1_am5_divergence(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    cost_report: Optional[dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """§B.5 (reported regardless of outcome): the top-level a1_am5_divergence block -- each replay arm's divergent
    keys and their count, zero included, and each affected contrast's pairs. Also re-reads B3's cost plug-in
    for a replay arm with divergent keys (the pairs are already without them), and drops the private per-arm
    lists from report['arms']. Returns the report."""
    if report.get("refused"):
        return report
    rd = _load_replay_divergence()
    for blk in (report.get("arms") or {}).values():
        if isinstance(blk, dict):
            blk.pop(A1_AM5_PRIVATE, None)
            blk.pop(A1_AM5_NONREPLAY, None)
    per_arm = {}
    for label in A1_PREFIX_ARMS:
        if label in arms:
            keys = arms[label].get(A1_AM5_PRIVATE) or []
            per_arm[label] = {"n_divergent": len(keys), "keys": [rd.key_label(k) for k in keys],
                              "n_crash_other": arms[label]["n_crash"] - len(keys),
                              "arm_complete": arms[label]["complete"]}
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else {}
    contrasts: dict[str, Any] = {}
    for row in list(report.get("predictions") or []) + list(((am1.get("cf") or {}).get("predictions")) or []):
        left, right = row.get("left"), row.get("right")
        if not isinstance(left, str) or not isinstance(right, str):
            continue
        excluded, verdict = a1_am5_exclusion(arms, left, right)
        if not excluded:
            continue
        n_pairs = ((row.get("contrast") or {}).get("n_pairs") if row.get("kind") != "cost_ratio"
                   else (row.get("ratio_interval") or {}).get("n_pairs"))
        contrasts[row["id"]] = {"left": left, "right": right, "n_excluded": len(excluded),
                                "excluded_keys": [rd.key_label(k) for k in excluded], "verdict": verdict,
                                "n_pairs": n_pairs, "decision": row.get("verdict")}
    companions: dict[str, Any] = {}
    for rows in (report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or []):
        for row in rows:
            kind = row.get("kind", "paired")
            if kind == "handoff_depth":
                for suffix, key in (("", "goal_pass"), ("_hstar", "goal_pass_hstar")):
                    for name, (target, base) in (row.get("receivers") or {}).items():
                        blk = (row.get(key) or {}).get(name) or {}
                        _a1_am5_companion(companions, f"{row['id']}.{name}{suffix}", (target, base),
                                          blk.get("n_pairs"), arms)
            else:
                labels = (list(row["left"]) + list(row["right"])) if kind == "did" else (row.get("left"), row.get("right"))
                _a1_am5_companion(companions, row["id"], labels, (row.get("goal_pass") or {}).get("n_pairs"), arms)
    for key, suffix in (("handoff_only_ni", ""), ("handoff_only_ni_hstar", "_hstar")):
        for row in am1.get(key) or []:
            _a1_am5_companion(companions, f"amendment1.{row.get('id')}{suffix}", (row.get("left"), row.get("right")),
                              (row.get("goal_pass") or {}).get("n_pairs"), arms)
    for key, suffix in (("decomposition", ""), ("decomposition_hstar", "_hstar")):
        for name, blk in (am1.get(key) or {}).items():
            _a1_am5_companion(companions, f"amendment1.decomposition.{name}{suffix}",
                              (blk.get("target"), blk.get("base")), (blk.get("goal_pass") or {}).get("n_pairs"), arms)
    for name, blk in (am1.get("b4_extra") or {}).items():
        _a1_am5_companion(companions, f"amendment1.b4_extra.{name}", (blk.get("target"), blk.get("base")),
                          blk.get("n_pairs"), arms)
    for part in ("split", "limit_as_zero"):
        for cid, blk in ((am1.get("limits") or {}).get(part) or {}).items():
            _a1_am5_companion(companions, f"amendment1.limits.{part}.{cid}", (blk.get("left"), blk.get("right")),
                              blk.get("n_pairs"), arms)
    chord = am1.get("chord") if isinstance(am1.get("chord"), dict) else None
    floor, ref = A1_AM1_CHORD["floor"], A1_AM1_CHORD["reference"]
    for label in A1_AM1_CHORD["arms"]:
        divergent = (arms.get(label) or {}).get(A1_AM5_PRIVATE)
        if not divergent or chord is None or any(a not in arms for a in (label, floor, ref)):
            continue
        note = "B3 cost plug-in not re-read: no cost report"
        if cost_report is not None:
            view, no_rows = a1_am5_cost_view(cost_report, (label, floor, ref), divergent)
            if no_rows:
                note = f"B3 cost plug-in not re-read: the cost report has no per-episode rows for {no_rows}"
            else:
                gone = set(divergent)
                sub = {a: dict(arms[a], episodes={k: v for k, v in arms[a]["episodes"].items() if k not in gone})
                       for a in (label, floor, ref)}
                chord["arms"][label] = _strip_internal(am1_chord(sub, view, n_boot=n_boot, seed=seed)["arms"][label])
                note = "B3 cost plug-in re-read on the cost report's rows without the arm's divergent keys"
        _a1_am5_companion(companions, f"amendment1.chord.{label}", (label, floor, ref),
                          ((chord["arms"].get(label) or {}).get("goal_pass") or {}).get("n_triples"), arms)
        companions[f"amendment1.chord.{label}"]["cost_plug_in"] = note
    non_replay = {label: [rd.key_label(k) for k in arm[A1_AM5_NONREPLAY]]
                  for label, arm in arms.items() if arm.get(A1_AM5_NONREPLAY)}
    report["a1_am5_divergence"] = {
        "rule": f"{A1_AM5} §B",
        "decision_bearing": "completeness only: every statistic, family, threshold and rule runs as registered",
        "definition": rd.DEFINITION,
        "cap": rd.DIVERGENCE_CAP,
        "replay_arms": list(A1_PREFIX_ARMS),
        "per_arm": per_arm,
        "n_divergent_total": sum(v["n_divergent"] for v in per_arm.values()),
        "contrasts": contrasts,
        "companions": companions,
        "non_replay_divergent": {
            "keys": non_replay,
            "treated_as": "an ordinary crash (impossible by construction: only arms 4-7 replay the environment)",
        },
        "notes": list(A1_AM5_NOTES),
    }
    return report


# ---- Unit R2: the J10 pre-read audit, Phase A (2026-09-25) -------------------------------------------------------
# The audit's findings that could change or hide a verdict, or print held-out numbers. The analysis itself is
# _a1_build_report_core, the former build_report_a1 renamed in place (:3627), so no line this file's citations name
# moves; build_report_a1 below is the public entry point (main_a1 and the tests call it). It runs, in order:
#   before the core -- the held-out manifest guard (A8), arm 3's layout (A1), the registered-read pins (A2, A10), the
#     P2 cost report's provenance (A3) and A1 §9's abort rule (A5), so that a refused or not-run read computes no
#     contrast;
#   after it -- P2 under both of Amendment 4's conventions (A4), no reading from a refused or incomplete row (A9), CF
#     and arms 11-12 not run as a pair (A6), supporting rows whose arms are incomplete (A10), Amendment 5's cap on B1
#     (A7), the h* B1a dev reference (A11), §F's BY-FDR re-read over the rows that keep a p, and the headline and exit
#     code recomputed from all of it.
A1_R2 = "unit R2, J10 pre-read audit (2026-09-25)"
A1_ABORT_ARMS = ("planner_alone_cap81", "advise_k1_fullctx", "advise_k10_fullctx", "takeover_k10")  # arms 3, 8, 9, 10
A1_PAIR_ARMS = ("show_k10", "advise_k10_neutral")  # arms 11 and 12: abandoned, and reported as not run, as a pair
A1_ABORT_CITATION = f"{A1_PREREG}:574-576"
A1_REGISTERED_SEEDS = (1, 2)
# What a refused or incomplete row must not carry (A1 §5.1 F6; Amendment 5 §B.3 "draws no reading").
A1_NO_READING_KEYS = ("verdict_unadjusted", "events_unadjusted", "p_value", "p_value_two_sided", "pool04",
                      "permutation_sensitivity")
# An arm's outcome values in report['arms'] (arm completeness counts are everything else).
A1_ARM_OUTCOME_KEYS = ("goal_pass_mean", "tgc_mean", "n_goal_pass_missing", "error_types")
A1_ARM_COUNT_KEYS = ("n_expected", "n_scored", "n_crash", "n_missing", "n_extra_ignored", "n_empty_files",
                     "n_unreadable", "n_duplicates", "root_missing", "systems_in_tree", "complete")
# The manifest fields a registered arm's config fixes (src/sidekick/provenance.py:86-106, 131-151);
# planner_cli_version is read from the binary at run time, not from the config, and is reported instead.
A1_PROVENANCE_FIELDS = ("config_campaign_id", "handoff_source_campaign", "handoff_m", "executor_model", "lora_name",
                        "takeover", "planner_type", "planner_model_requested", "planner_reasoning_effort",
                        "correct_prompt", "advice_from_act")
A1_R2_UNSTAMPED_TOP_LEVEL = ("takeover", "advice_from_act", "fixed_k", "correct_context")
# A11: Amendment 3 (A1:944-947) -- under h*, P3's handoff-only dev value (ledger HSTAR-11).
A1_HSTAR_B1A_DEV = {
    "diff_pp": 8.57, "ci95_pp_scenario": [-1.63, 18.25], "ci95_pp_task": [0.67, 16.30], "n_handoff": 88,
    "n_pairs": 171, "source": "campaign/results/j17_hstar_20260924.report.json",
    "key": "ni.bplus.m11.goal_pass.handoff_only", "bootstrap_seed": A1_BOOTSTRAP_SEED,
    "citation": f"{A1_PREREG}:944-947 (Amendment 3; ledger HSTAR-11)",
}


def _a1_r2_verdicts(preds: Optional[list[dict[str, Any]]], value: str) -> dict[str, str]:
    """The seam every J10 report carries (j11_report --j10-report reads it): one verdict per P row."""
    return {p["id"]: value for p in (preds if preds is not None else A1_PREDICTIONS) if isinstance(p, dict)}


def _a1_r2_refused(split: str, reason: str,
                   preds: Optional[list[dict[str, Any]]] = None) -> tuple[dict[str, Any], int]:
    return {"protocol": "A1", "label": "REFUSED", "status": "REFUSED", "refused": True, "reason": reason,
            "headline": reason, "split": split, "not_the_j10_result": True,
            "verdicts": _a1_r2_verdicts(preds, "refused")}, 2


def a1_r2_predictions_path(args: argparse.Namespace) -> Optional[Path]:
    """A2: the registered test_normal read uses this file's registry, so --predictions-json is refused there."""
    if args.split == "test_normal" and args.predictions_json is not None:
        raise ValueError("refusing --predictions-json on test_normal: the registered read uses the registry in "
                         f"{Path(__file__).name} (A1 §6; {A1_R2}, A2)")
    return args.predictions_json


def a1_r2_heldout_guard(split: str, registered_read: bool, arm_dirs: dict[str, Path]) -> Optional[str]:
    """A8: an episode whose manifest records test_normal is read only by the confirmed test_normal read, and one that
    records test_challenge never (A1 §8). Read from the manifests before anything else is loaded, so no contrast is
    computed first. (The path-marker check of a1_protocol_guard cannot see J10's campaign names.)"""
    for label, path in arm_dirs.items():
        counts = a1_split_provenance(Path(path))
        held = {k: v for k, v in counts.items()
                if k in HELDOUT_TEST_SPLITS and (k == "test_challenge" or not registered_read)}
        if held:
            what = "the confirmed test_normal read" if registered_read else f"--split {split}"
            return (f"refusing --arm {label}={path}: {held} episode manifest(s) record a held-out split and this is "
                    f"{what}; a test_normal episode is read only by the confirmed test_normal read, and "
                    f"test_challenge never [{A1_PREREG}:546] ({A1_R2}, A8)")
    return None


def a1_r2_layout_guard(arm_dirs: dict[str, Path]) -> Optional[str]:
    """A1: arm 3 is given as its campaign root, which holds planner_alone/. Any other directory would make
    planless_source_keys (src/sidekick/agents/planner.py:778-804) read no key at all and skip §4.2 silently."""
    root = arm_dirs.get(A1_PLAN_SOURCE_ARM)
    if root is None or (Path(root) / "planner_alone").is_dir():
        return None
    return (f"refusing --arm {A1_PLAN_SOURCE_ARM}={root}: it holds no planner_alone/ subdirectory, so A1 §4.2's "
            "planless keys would read as none. Expected layout: <arm-3 campaign>/planner_alone/<seed>/<task_id>/"
            "{result.json,events.jsonl}; pass the campaign directory (e.g. "
            f"{RAW_RESULTS_ROOT}/j10_planner_alone_cap81_20260924), not its system subdirectory ({A1_R2}, A1)")


def _a1_r2_config(label: str) -> dict[str, Any]:
    import yaml  # noqa: E402 (lazy: only the registered read needs it)

    rel = A1_ARMS.get(label)
    if rel is None:
        raise ValueError(f"no registered config for arm {label!r}")
    data = yaml.safe_load((REPO_ROOT / rel).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{rel} is not a mapping")
    return data


def a1_r2_expected_provenance(label: str) -> dict[str, Any]:
    """The provenance an episode manifest of registered arm `label` must stamp: the runner passes the raw config
    (src/sidekick/runner.py:47-57, 384-389) to run_provenance, so config_provenance on the same file gives the
    same values; the planner fields mirror planner_provenance (src/sidekick/provenance.py:131-151) without the
    CLI version, which comes from the binary."""
    from sidekick.provenance import config_provenance  # noqa: E402 (lazy)

    cfg = _a1_r2_config(label)
    prov = config_provenance(cfg, A1_ARMS[label])
    planner = cfg.get("planner") or {}
    defaults = cfg.get("policy_defaults") or {}
    return {
        **{k: prov.get(k) for k in A1_PROVENANCE_FIELDS if k in prov},
        "planner_type": str(planner.get("type") or "mock"),
        "planner_model_requested": planner.get("model"),
        "planner_reasoning_effort": planner.get("reasoning_effort"),
        "correct_prompt": planner.get("correct_prompt", "correction"),
        "advice_from_act": defaults.get("advice_from_act"),
    }


def _a1_r2_same(field: str, got: Any, want: Any) -> bool:
    if field == "handoff_source_campaign" and got is not None and want is not None:
        return os.path.normpath(str(got)) == os.path.normpath(str(want))
    return got == want


def a1_r2_manifest_check(root: Path, expected: dict[str, Any], campaign_id: str) -> dict[str, Any]:
    """Every episode manifest under an arm against its config: mismatches (refused), fields not stamped (reported),
    and the CLI versions seen (for the §9.1 provenance statement)."""
    mismatches: dict[str, dict[str, Any]] = {}
    unstamped: Counter[str] = Counter()
    cli: Counter[str] = Counter()
    n_manifests = n_without = 0
    want_all = dict(expected, campaign_id=campaign_id)
    for path in sorted(Path(root).rglob("result.json")):
        man = path.parent / "manifest.json"
        try:
            data = json.loads(man.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict):
            n_without += 1
            continue
        n_manifests += 1
        prov = data.get("provenance") if isinstance(data.get("provenance"), dict) else {}
        stamped = dict(prov)
        if "campaign_id" in data:
            stamped["campaign_id"] = data["campaign_id"]
        cli[str(prov.get("planner_cli_version"))] += 1
        for field, want in want_all.items():
            if field not in stamped:
                unstamped[field] += 1
                continue
            if not _a1_r2_same(field, stamped[field], want):
                m = mismatches.setdefault(field, {"n": 0, "registered": want, "stamped": [], "first": str(man)})
                m["n"] += 1
                if repr(stamped[field]) not in m["stamped"]:
                    m["stamped"].append(repr(stamped[field]))
    return {"n_manifests": n_manifests, "n_results_without_manifest": n_without, "mismatches": mismatches,
            "unstamped": dict(sorted(unstamped.items())), "planner_cli_version": dict(sorted(cli.items()))}


def _a1_r2_registry_is_registered(predictions: Any, supporting: Any, exploratory: Any) -> list[str]:
    def same(a: Any, b: Any) -> bool:
        return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)

    out = []
    if predictions is not None and not same(list(predictions), A1_PREDICTIONS):
        out.append("the predictions differ from A1_PREDICTIONS")
    if supporting is not None and not same(list(supporting), A1_SUPPORTING):
        out.append("the supporting rows differ from A1_SUPPORTING")
    if exploratory is not None and not same(list(exploratory), A1_EXPLORATORY):
        out.append("the exploratory rows differ from A1_EXPLORATORY")
    return out


def a1_r2_registered_read_guard(
    *,
    seeds: list[int],
    expected_n_tasks: int,
    arm_dirs: dict[str, Path],
    predictions: Any,
    supporting: Any,
    exploratory: Any,
) -> tuple[Optional[str], dict[str, Any]]:
    """A2 and A10, on the confirmed test_normal read: seeds exactly {1, 2}; 168 tasks; this file's registry; every
    registered arm given (A10's arms 1, 1b, prefix_m9, show_k10 and advise_k10_neutral included), each from the
    directory named by its config's campaign_id; and every episode manifest stamping what that config registers
    (adapter alias, replay source, depth, planner, prompt). Returns (refusal or None, the manifest check)."""
    problems: list[str] = []
    if sorted(seeds) != list(A1_REGISTERED_SEEDS):
        problems.append(f"seeds {seeds} are not exactly {{1, 2}} [{A1_PREREG}:127]")
    if expected_n_tasks != A1_SPLIT_N_TASKS["test_normal"]:
        problems.append(f"expected task count {expected_n_tasks} is not {A1_SPLIT_N_TASKS['test_normal']} "
                        f"[{A1_PREREG}:126]")
    problems += _a1_r2_registry_is_registered(predictions, supporting, exploratory)
    missing = [a for a in A1_ARMS if a not in arm_dirs]
    if missing:
        problems.append(f"registered arms not given as --arm: {missing} (every registered arm is read; A1 §4, §7 "
                        "items 1-2; A10)")
    unknown = sorted(a for a in arm_dirs if a not in A1_ARMS)
    if unknown:
        problems.append(f"arms not registered under A1: {unknown}")
    ids: dict[str, str] = {}
    for label in (a for a in A1_ARMS if a in arm_dirs):
        try:
            ids[label] = str(_a1_r2_config(label).get("campaign_id"))
        except (OSError, ValueError) as exc:
            problems.append(f"{label}: its config cannot be read ({exc})")
            continue
        if Path(arm_dirs[label]).name != ids[label]:
            problems.append(f"--arm {label}={arm_dirs[label]}: the directory is not the registered campaign "
                            f"{ids[label]} (configs' campaign_id, as scripts/pbs/j10_arm.pbs uses it)")
    checks: dict[str, Any] = {}
    if not problems:
        for label, cid in ids.items():
            chk = a1_r2_manifest_check(Path(arm_dirs[label]), a1_r2_expected_provenance(label), cid)
            checks[label] = chk
            for field, m in chk["mismatches"].items():
                problems.append(f"{label}: {m['n']} manifest(s) stamp {field}={', '.join(m['stamped'])} but "
                                f"{A1_ARMS[label]} registers {m['registered']!r} (first: {m['first']})")
    if problems:
        return ("refusing the registered test_normal read: " + "; ".join(problems) + f" ({A1_R2}, A2)"), checks
    channel = {}
    for label in ids:
        cfg = _a1_r2_config(label)
        keys = {k: cfg[k] for k in A1_R2_UNSTAMPED_TOP_LEVEL if k in cfg}
        if keys:
            channel[label] = keys
    return None, {
        "status": "ok",
        "per_arm": checks,
        "compared": list(A1_PROVENANCE_FIELDS) + ["campaign_id"],
        "not_shown_by_the_manifest": {
            "adapter_directory": ("a manifest stamps the adapter alias (lora_name) only, not the directory it is "
                                  "served from; scripts/pbs/j10_arm.pbs pins the directory (ADAPTER_SFT_B_PLUS, "
                                  f"A1 §4, F8) and this report cannot check it"),
            "channel_config_keys": {
                "per_arm": channel,
                "why": ("top-level config keys the runner reads (src/sidekick/runner.py:307-327); a manifest stamps "
                        "takeover and advice_from_act from policy_defaults only (src/sidekick/provenance.py:104, "
                        ":150), so for these arms it stamps None, and fixed_k / correct_context not at all -- the "
                        "comparison above matches None to None and cannot see the channel (the run_start event's "
                        "policy records takeover / advice_from_act, src/sidekick/systems/loop.py:686-688)"),
            },
            "served_model": "not observable (A1 §9.1): planner_model_requested is the request only",
        },
    }


def _a1_r2_same_dir(a: Any, b: Any) -> bool:
    try:
        return Path(str(a)).resolve() == Path(str(b)).resolve()
    except (OSError, RuntimeError):
        return os.path.normpath(str(a)) == os.path.normpath(str(b))


def a1_r2_cost_report_guard(
    cost_report: Optional[dict[str, Any]],
    arm_dirs: dict[str, Path],
    loaded: dict[str, dict[str, Any]],
) -> tuple[Optional[str], dict[str, Any]]:
    """A3, on the confirmed test_normal read: the P2 cost report must be over the arms given (A1:347-349, F9).
    scripts/analysis/j12_cost_axes.py records neither its split, nor its arm directories, nor --packet-source, so
    they are checked where the report carries them and otherwise through what it does carry: P2's arms' per-episode
    rows, each of which must be an episode (a result.json key) of the arm directory given -- which a report over any
    other split or campaign cannot satisfy (test_normal and dev share no task)."""
    info: dict[str, Any] = {
        "rule": f"{A1_PREREG}:347-349 (F9); {A1_R2}, A3",
        "not_recorded_by_j12_cost_axes": ["split", "arm directories", "packet_source"],
    }
    if cost_report is None:
        return None, info | {"status": "no cost report: P2 is not computed"}
    problems: list[str] = []
    split = cost_report.get("split")
    if split is not None and split != "test_normal":
        problems.append(f"its split is {split!r}")
    source = cost_report.get("packet_source")
    arm3 = arm_dirs.get(A1_PLAN_SOURCE_ARM)
    if source is not None and (arm3 is None or not _a1_r2_same_dir(source, arm3)):
        problems.append(f"its packet_source {source!r} is not --arm {A1_PLAN_SOURCE_ARM}={arm3}")
    arms_c = _cost_arms(cost_report)
    for label, blk in arms_c.items():
        root = next((blk.get(k) for k in ("root", "dir", "arm_dir", "path") if isinstance(blk, dict) and blk.get(k)),
                    None)
        if root is not None and (label not in arm_dirs or not _a1_r2_same_dir(root, arm_dirs[label])):
            problems.append(f"its arm {label!r} was read from {root!r}, not --arm {label}={arm_dirs.get(label)}")
    rows_checked: dict[str, Any] = {}
    for label in A1_AM4_P2:
        blk = arms_c.get(label)
        if not isinstance(blk, dict):
            continue  # P2 reports the arm as absent from the cost report
        rows = blk.get("episodes")
        if not isinstance(rows, list) or not rows:
            problems.append(f"{label} has no per-episode rows, so the report's split and arm directory cannot be "
                            "checked")
            continue
        present = set((loaded.get(label) or {}).get("runs") or {})
        keys = [_a1_am5_row_key(r) for r in rows]
        foreign = [k for k in keys if k is None or k not in present]
        rows_checked[label] = {"n_rows": len(rows), "n_not_episodes_of_the_arm_given": len(foreign)}
        if foreign:
            first = next((rd_k for rd_k in foreign if rd_k is not None), None)
            problems.append(f"{label}: {len(foreign)} of {len(rows)} per-episode rows are not episodes of --arm "
                            f"{label}={arm_dirs.get(label)}" + (f" (first: {first[1]}/{first[0]})" if first else ""))
    info["p2_rows"] = rows_checked
    if problems:
        return "refusing the P2 cost report on the registered test_normal read: " + "; ".join(problems), info
    return None, info | {"status": "ok"}


def _a1_r2_preload(
    arm_dirs: dict[str, Path], seeds: list[int], preds: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str], dict[str, dict[str, Any]]]:
    """The arms exactly as the core builds them (:3652-3657), for the checks that must run before any contrast."""
    loaded = {label: load_arm_tree(Path(path)) for label, path in arm_dirs.items()}
    tasks = discover_tasks(loaded, seeds)
    arms = a1_am5_arms({label: a1_r2_scored_as_recorded(a1_arm_episodes(label, blob, tasks, seeds), blob)
                        for label, blob in loaded.items()}, arm_dirs, tasks, seeds, preds, [])
    return loaded, tasks, arms


def a1_r2_abort_reasons(
    arms: dict[str, dict[str, Any]],
    expected_pairs: int,
    planless: Optional[list[tuple[str, int]]],
    cap: int,
) -> list[str]:
    """A5, A1 §9 (:574-576): J10 is reported as not run if arm 3, 8, 9 or 10 cannot complete the registered
    non-crashed matrix, and (A1 §4.2 item 5, :234) if more than the cap of arm 3's episodes are planless. An arm
    that is not given is absent, not incomplete (a dev subset); the registered read requires every arm (A10)."""
    why = []
    for label in A1_ABORT_ARMS:
        arm = arms.get(label)
        if arm is None:
            continue
        if not arm["complete"] or arm["n_expected"] != expected_pairs:
            why.append(f"arm {label} did not complete {expected_pairs} non-crashed pairs "
                       f"(scored={arm['n_scored']}, crash={arm['n_crash']}, missing={arm['n_missing']})")
    if planless is not None and len(planless) > cap:
        why.append(f"{len(planless)} of arm 3's episodes are planless, above the cap of {cap} [{A1_PREREG}:234-236]")
    return why


def a1_r2_not_run_report(
    *,
    split: str,
    seeds: list[int],
    expected_n_tasks: int,
    tasks: list[str],
    arms: dict[str, dict[str, Any]],
    planless: Optional[list[tuple[str, int]]],
    cap: int,
    why: list[str],
    registered: bool,
    plumbing_check: bool,
    preds: Optional[list[dict[str, Any]]] = None,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """A5: status NOT_RUN. Arm completeness counts only -- no P, S, E or CF verdict and no contrast value."""
    label = ("PLUMBING CHECK, NOT A RESULT" if plumbing_check
             else "A1 DRY RUN ON DEV, NOT THE J10 RESULT" if split == "dev" else "J10 A1 registered analysis")
    if not registered:
        label += " (NON-REGISTERED bootstrap settings)"
    report: dict[str, Any] = {
        "protocol": "A1",
        "prereg": A1_PREREG,
        "label": label,
        "status": "NOT_RUN",
        "headline": "J10 not run: " + "; ".join(why) + ".",
        "not_the_j10_result": plumbing_check or not registered or split != "test_normal",
        "split": split,
        "seeds": seeds,
        "expected_n_tasks": expected_n_tasks,
        "n_tasks_observed_union": len(tasks),
        "expected_pairs_per_arm": expected_n_tasks * len(seeds),
        "abort_rule": {"citation": A1_ABORT_CITATION, "arms": list(A1_ABORT_ARMS),
                       "planless_cap": {"citation": f"{A1_PREREG}:234-236", "cap": cap}},
        "not_run_reasons": why,
        "verdicts": _a1_r2_verdicts(preds, "not_run"),
        "printed": ("arm completeness counts only (A1 §9: J10 is reported as not run, never at reduced power): every "
                    "P verdict is 'not_run', and no S, E or CF row and no contrast value is printed"),
        "arms": {name: {k: arm[k] for k in A1_ARM_COUNT_KEYS if k in arm} for name, arm in arms.items()},
        "planless_contingency": {"rule": "A1 §4.2", "source_arm": A1_PLAN_SOURCE_ARM, "cap": cap,
                                 "keys": None if planless is None else [f"{s}/{t}" for t, s in planless],
                                 "n_keys": None if planless is None else len(planless)},
    }
    return a1_am5_divergence(report, arms, None, n_boot=n_boot, seed=seed)


def a1_r2_no_reading(row: dict[str, Any]) -> dict[str, Any]:
    """A9: a refused or incomplete row keeps its descriptive contrast but carries no verdict_unadjusted, p, POOL-04
    or sign-flip reading (A1 §5.1 F6; Amendment 5 §B.3)."""
    if row.get("decidable"):
        return row
    dropped = [k for k in A1_NO_READING_KEYS if k in row]
    for key in dropped:
        row.pop(key)
    if dropped or row.get("verdict") in ("refused_incomplete", "refused_no_pairs"):
        row["draws_no_reading"] = True
    return row


def a1_r2_p2_both_conventions(results: list[dict[str, Any]], am4: Any) -> Optional[str]:
    """A4, Amendment 4 §C (A1:1017-1024): P2 is supported only if its rule holds AND the calls clause holds under
    both conventions AND the tokens clause holds under both. A clause that cannot be read (holds_both None) leaves a
    supported P2 incomplete. It can only turn a supported P2 into not supported, never the reverse. Returns a reason
    for the headline when P2 is left incomplete."""
    am4 = am4 if isinstance(am4, dict) else {}
    calls = am4.get("p2_calls_clause") if isinstance(am4.get("p2_calls_clause"), dict) else {}
    tokens = am4.get("p2_tokens_clause") if isinstance(am4.get("p2_tokens_clause"), dict) else {}
    reason = None
    for r in results:
        if r.get("kind") != "cost_ratio" or (r.get("left"), r.get("right")) != A1_AM4_P2:
            continue
        hb_c, hb_t = calls.get("holds_both"), tokens.get("holds_both")
        blk: dict[str, Any] = {"citation": f"{A1_PREREG} Amendment 4 §C", "rule": f"{A1_AM4_NOTE}; {A1_AM4_TOKENS_NOTE}",
                               "calls_holds_both": hb_c, "tokens_holds_both": hb_t,
                               "a1_am4_calls_status": am4.get("status", "absent")}
        r["amendment4"] = blk
        if not r.get("decidable") or r.get("verdict") != "supported":
            continue
        if hb_c is False or hb_t is False:
            r["verdict_before_amendment4"] = r["verdict"]
            r["verdict"] = "not_supported"
            blk["changed"] = True
            blk["why"] = " and ".join(n for n, hb in (("calls", hb_c), ("tokens", hb_t)) if hb is False) + \
                " clause fails under one convention"
        elif hb_c is None or hb_t is None:
            unread = [n for n, hb in (("calls", hb_c), ("tokens", hb_t)) if hb is None]
            reason = f"p2_amendment4_clause_not_read:{','.join(unread)}"
            r.update(decidable=False, verdict="refused_incomplete",
                     reason=(f"Amendment 4 §C: P2 is supported only if its {' and '.join(unread)} clause holds under "
                             "both conventions, and a1_am4_calls cannot read it "
                             f"({calls.get('status') or tokens.get('status') or am4.get('status', 'absent')})"))
    return reason


def a1_r2_pair_not_run(arms: dict[str, dict[str, Any]]) -> list[str]:
    """A6: arms 11 and 12 are abandoned, and reported as not run, as a pair (A1:491, :575-576; Amendment 1 §C)."""
    why = []
    for label in A1_PAIR_ARMS:
        if label not in arms:
            why.append(f"{label} absent")
        elif not arms[label]["complete"]:
            arm = arms[label]
            why.append(f"{label} incomplete (scored={arm['n_scored']}/{arm['n_expected']}, crash={arm['n_crash']})")
    return why


def _a1_r2_row_arms(row: dict[str, Any]) -> list[str]:
    kind = row.get("kind", "paired")
    if kind == "did":
        labels = list(row.get("left") or []) + list(row.get("right") or [])
    elif kind == "handoff_depth":
        labels = [a for pair in (row.get("receivers") or {}).values() for a in pair]
    else:
        labels = [row.get("left"), row.get("right")]
    return [a for a in labels if isinstance(a, str)]


def a1_r2_apply_pair_not_run(report: dict[str, Any], why: list[str]) -> None:
    """A6: CF1-CF3 'not_run' and every row that uses arm 11 or 12 printed without values (never at reduced power).
    P1-P6 stand, and this alone moves neither the headline's completeness nor the exit code."""
    reason = ("arms 11-12 not run, as a pair (A1:491, :575-576; Amendment 1 §C 'CF is reported as not run'): "
              + "; ".join(why))
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else {}
    cf = am1.get("cf") if isinstance(am1.get("cf"), dict) else None
    if cf is not None:
        keep = ("id", "role", "kind", "metric", "left", "right", "rule", "threshold_pp", "holm_family", "family",
                "same_contrast_as", "statement", "citation", "dev_reference", "power", "readings", "rule_text",
                "direction")
        cf["predictions"] = [{k: r[k] for k in keep if k in r}
                             | {"decidable": False, "verdict": "not_run", "reading": None, "reason": reason}
                             for r in cf.get("predictions") or []]
        keep2 = ("id", "left", "right", "same_contrast_as", "citation", "dev_reference", "power_exclude_zero",
                 "readings", "never", "decision_bearing", "adjusted")
        cf["secondary"] = [{k: s[k] for k in keep2 if k in s}
                           | {"status": "not_run", "side": None, "reading": None, "reason": reason}
                           for s in cf.get("secondary") or []]
        cf["status"] = "not_run"
        cf["not_run_reason"] = reason
        cf["verdicts"] = {r["id"]: "not_run" for r in cf["predictions"]}
        if cf.get("key_exclusion") is not None:
            cf["key_exclusion"] = {"status": "not_run", "reason": reason}
    limits = am1.get("limits") if isinstance(am1.get("limits"), dict) else {}
    for part in ("split", "limit_as_zero"):
        for cid, blk in list((limits.get(part) or {}).items()):
            if isinstance(blk, dict) and any(blk.get(s) in A1_PAIR_ARMS for s in ("left", "right")):
                limits[part][cid] = {"left": blk.get("left"), "right": blk.get("right"), "status": "not_run",
                                     "reason": reason}
    for label in A1_PAIR_ARMS:
        if label in (limits.get("rates") or {}):
            limits["rates"][label] = {"status": "not_run"}
        blk = (report.get("arms") or {}).get(label)
        if isinstance(blk, dict):
            for key in A1_ARM_OUTCOME_KEYS:
                blk.pop(key, None)
            blk["not_run"] = True
        per_arm = (report.get("a1_am4_calls") or {}).get("per_arm")
        if isinstance(per_arm, dict) and label in per_arm:
            per_arm[label] = {"status": "not_run"}
    for rows in (report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or []):
        for row in rows:
            if any(a in A1_PAIR_ARMS for a in _a1_r2_row_arms(row)):
                for key in ("goal_pass", "goal_pass_hstar", "hstar_mismatch_between_receivers",
                            "handoff_flag_mismatch_between_receivers"):
                    row.pop(key, None)
                row.update(goal_pass=None, status="not_run", reason=reason)


def a1_r2_supporting_status(report: dict[str, Any], arms: dict[str, dict[str, Any]]) -> list[str]:
    """A10: an S or E row whose arm is incomplete, or whose arms' divergent keys exceed Amendment 5's cap, says
    'incomplete' and keeps no p (so §F leaves it out); an ok row says 'ok'. Returns the incomplete rows' ids."""
    rd = _load_replay_divergence()
    flagged = []
    for rows in (report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or []):
        for row in rows:
            if row.get("status") == "not_run":
                continue
            labels = _a1_r2_row_arms(row)
            if any(a not in arms for a in labels):
                row.setdefault("status", "arm_absent")
                continue
            incomplete = sorted({a for a in labels if not arms[a]["complete"]})
            divergent = {tuple(k) for a in labels for k in (arms[a].get(A1_AM5_PRIVATE) or [])}
            over = len(divergent) > rd.DIVERGENCE_CAP
            if not incomplete and not over:
                row["status"] = "ok"
                continue
            why = "; ".join(([f"arm(s) incomplete: {incomplete}"] if incomplete else [])
                            + ([f"{len(divergent)} divergent keys > cap {rd.DIVERGENCE_CAP} (Amendment 5 §B.3)"]
                               if over else []))
            row.update(status="incomplete", incomplete_arms=incomplete, reason=why, draws_no_reading=True)
            if isinstance(row.get("goal_pass"), dict):
                row["goal_pass"].pop("p_value_two_sided_at_0", None)
            if row.get("kind") == "handoff_depth":
                for key in ("goal_pass", "goal_pass_hstar"):
                    for name, (target, base) in (row.get("receivers") or {}).items():
                        blk = (row.get(key) or {}).get(name)
                        if isinstance(blk, dict) and (target in incomplete or base in incomplete or over):
                            blk["status"] = "incomplete"
            flagged.append(row["id"])
    return flagged


def a1_r2_b1_cap(row: dict[str, Any], arms: dict[str, dict[str, Any]]) -> None:
    """A7, Amendment 5 §B.3 (A1:1118-1120) on B1a / B1b: a contrast that removes more than 16 divergent keys, or an
    incomplete arm, draws no reading -- the NI reading becomes 'incomplete' and the p at the margin is dropped."""
    left, right = row.get("left"), row.get("right")
    if left not in arms or right not in arms:
        return
    rd = _load_replay_divergence()
    excluded, verdict = a1_am5_exclusion(arms, left, right)
    incomplete = [a for a in (left, right) if not arms[a]["complete"]]
    over = verdict != rd.VERDICT_OK
    if not incomplete and not over:
        return
    why = "; ".join(([f"arm(s) incomplete: {incomplete}"] if incomplete else [])
                    + ([f"{len(excluded)} divergent keys to remove > cap {rd.DIVERGENCE_CAP} (Amendment 5 §B.3)"]
                       if over else []))
    row.update(status="incomplete", reason=why, draws_no_reading=True)
    for metric in ("goal_pass", "tgc"):
        blk = row.get(metric)
        if isinstance(blk, dict):
            blk.pop("p_value_two_sided_at_margin", None)
            if "ni" in blk:
                blk["ni"] = {"reading": "incomplete", "reason": why}


def a1_r2_rebuild_by(report: dict[str, Any]) -> None:
    """§F re-read over the final rows: a row that lost its p (refused, incomplete, not run) is listed and left out
    of m, as §F says of a contrast without a p."""
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else None
    if am1 is None:
        return
    results = report.get("predictions") or []
    cf_results = (am1.get("cf") or {}).get("predictions") or []
    support = report.get("supporting_contrasts") or []
    explore = report.get("exploratory_contrasts") or []
    am1["multiplicity_sensitivity"] = am1_by_fdr(am1_by_entries(results, cf_results, support, explore,
                                                                am1.get("handoff_only_ni") or []))
    if "multiplicity_sensitivity_hstar" in am1:
        am1["multiplicity_sensitivity_hstar"] = am1_by_fdr(am1_by_entries(
            results, cf_results, support, explore, am1.get("handoff_only_ni_hstar") or []))


def a1_r2_finalize(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    preds: list[dict[str, Any]],
    checks: dict[str, Any],
    arms_as_read: Optional[dict[str, dict[str, Any]]] = None,
) -> tuple[dict[str, Any], int]:
    """Everything Phase A applies after the core, then the headline and exit code from the final rows."""
    results = report.get("predictions") or []
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else {}
    p2_reason = a1_r2_p2_both_conventions(results, report.get("a1_am4_calls"))  # A4
    for r in results + list((am1.get("cf") or {}).get("predictions") or []):  # A9
        a1_r2_no_reading(r)
    # A6 reads the arms as loaded: when the core refuses the whole matrix it marks every arm incomplete, and CF is
    # then refused along with P1-P6, not "not run".
    pair_why = a1_r2_pair_not_run(arms_as_read if arms_as_read is not None else arms)  # A6
    if pair_why:
        a1_r2_apply_pair_not_run(report, pair_why)
        report["arms_11_12_not_run"] = {"reasons": pair_why, "citation": f"{A1_PREREG}:575-576; Amendment 1 §C"}
    flagged = a1_r2_supporting_status(report, arms)  # A10
    for key in ("handoff_only_ni", "handoff_only_ni_hstar"):  # A7
        for row in am1.get(key) or []:
            a1_r2_b1_cap(row, arms)
    for row in am1.get("handoff_only_ni_hstar") or []:  # A11
        if row.get("id") == "B1a":
            row["dev_reference"] = dict(A1_HSTAR_B1A_DEV)
    a1_r2_rebuild_by(report)
    cf = am1.get("cf") if isinstance(am1.get("cf"), dict) else {}
    if cf:
        cf["verdicts"] = {r["id"]: r.get("verdict") for r in cf.get("predictions") or []}
    report["verdicts"] = {r["id"]: r.get("verdict") for r in results}
    final = {r["id"]: r.get("verdict") for r in results + list(cf.get("predictions") or [])}
    for cid, blk in ((report.get("a1_am5_divergence") or {}).get("contrasts") or {}).items():
        if cid in final:
            blk["decision"] = final[cid]
    # The headline and exit code: P1-P6 decide completeness. An incomplete arm that no prediction uses (1, 1b,
    # prefix_m9, 11, 12) is listed beside it, and CF1 after it; neither moves the exit code (A6, A10).
    p_arms = {a for p in preds for a in (p.get("left"), p.get("right")) if isinstance(a, str)}
    p_reasons, support_reasons = [], []
    for reason in report.get("incomplete_reasons") or []:
        label = reason[len("incomplete_arm:"):].split(" ", 1)[0] if reason.startswith("incomplete_arm:") else None
        (support_reasons if label is not None and label not in p_arms else p_reasons).append(reason)
    if p2_reason:
        p_reasons.append(p2_reason)
    decided = all(r.get("decidable") for r in results)
    code = 0 if decided and not p_reasons else 1
    headline = ("COMPLETE: every registered prediction decided." if code == 0
                else "INCOMPLETE: " + "; ".join(p_reasons or ["some predictions not decidable"]))
    support_arms = sorted({r[len("incomplete_arm:"):].split(" ", 1)[0] for r in support_reasons})
    if support_arms:
        headline += ("" if headline.endswith(".") else ".") + (
            f" Incomplete arms no prediction uses: {', '.join(support_arms)} (P1-P6 stand).")
    if flagged:
        headline += ("" if headline.endswith(".") else ".") + (
            f" Supporting / exploratory rows incomplete, drawing no reading: {', '.join(flagged)}.")
    cf1 = "not run" if cf.get("status") == "not_run" else str((cf.get("verdicts") or {}).get("CF1"))
    headline += ("" if headline.endswith(".") else ".") + " Amendment 1 CF1: " + cf1 + "."
    report.update(status="COMPLETE" if code == 0 else "INCOMPLETE", headline=headline,
                  incomplete_reasons=p_reasons, supporting_incomplete_reasons=support_reasons)
    if checks:
        report["registered_read_checks"] = checks
    report["unit_r2"] = {"what": A1_R2, "phase_a": ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9", "A10", "A11"]}
    return report, code


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
    pairwise: bool = True,
) -> tuple[dict[str, Any], int]:
    """The A1 report: the guards and the §9 abort rule, then _a1_build_report_core, then unit R2's readings.
    Exit 0 complete, 1 incomplete or not run, 2 refused. pairwise=False skips A1 §7 item 2's 78 pairwise contrasts
    on a dev read (the unit tests' default); the registered read computes them regardless."""
    preds = [dict(p) for p in (predictions if predictions is not None else A1_PREDICTIONS)]
    registered = n_boot == A1_BOOTSTRAP_N and bootstrap_seed == A1_BOOTSTRAP_SEED
    proto = a1_protocol_guard(split, confirm_heldout_test_split, plumbing_check, arm_dirs.values(), out_path,
                              registered)
    if proto:
        return _a1_r2_refused(split, proto, preds)
    registered_read = split == "test_normal"  # the guard above admits test_normal only confirmed and registered
    checks: dict[str, Any] = {}
    why = a1_r2_heldout_guard(split, registered_read, arm_dirs) or a1_r2_layout_guard(arm_dirs)
    if why is None and registered_read:
        why, checks["manifests"] = a1_r2_registered_read_guard(
            seeds=seeds, expected_n_tasks=expected_n_tasks, arm_dirs=arm_dirs, predictions=predictions,
            supporting=supporting, exploratory=exploratory)
    if why:
        return _a1_r2_refused(split, why, preds)
    loaded, tasks, arms0 = _a1_r2_preload(arm_dirs, seeds, preds)
    if registered_read:
        why, checks["cost_report"] = a1_r2_cost_report_guard(cost_report, arm_dirs, loaded)
        if why:
            return _a1_r2_refused(split, why, preds)
    expected_pairs = expected_n_tasks * len(seeds)
    planless = a1_planless_keys(arm_dirs, seeds)
    cap = int(expected_pairs * A1_PLANLESS_CAP_FRACTION)
    abort = a1_r2_abort_reasons(arms0, expected_pairs, planless, cap)
    if abort:
        return a1_r2_not_run_report(split=split, seeds=seeds, expected_n_tasks=expected_n_tasks, tasks=tasks,
                                    arms=arms0, planless=planless, cap=cap, why=abort, registered=registered,
                                    plumbing_check=plumbing_check, n_boot=n_boot, seed=bootstrap_seed,
                                    preds=preds), 1
    out = _a1_build_report_core(
        split=split, seeds=seeds, arm_dirs=arm_dirs, expected_n_tasks=expected_n_tasks,
        confirm_heldout_test_split=confirm_heldout_test_split, plumbing_check=plumbing_check,
        cost_report=cost_report, predictions=predictions, supporting=supporting, exploratory=exploratory,
        n_boot=n_boot, bootstrap_seed=bootstrap_seed, out_path=out_path)
    if len(out) == 2:
        return out[0], out[1]
    report, _code, arms = out
    report, code = a1_r2_finalize(report, arms, preds=preds, checks=checks, arms_as_read=arms0)
    # Phase B: rows and wording only. The registered read always prints A1 §7 item 2's pairwise contrasts.
    a1_r2_phase_b(report, arms, arm_dirs, tasks, seeds, pairwise=pairwise or registered_read, n_boot=n_boot,
                  seed=bootstrap_seed)
    return report, code


# ---- Unit R2: the J10 pre-read audit, Phase B (2026-09-25) -------------------------------------------------------
# Printed rows and wording only: no verdict, family, threshold or exit code moves. a1_r2_phase_b runs after Phase A's
# readings (build_report_a1). B7's scoring is the one in-place hook, on the core's arms line (:3657).
A1_R2_ASK_BOUND_FLAG_PP = 1.00  # Amendment 1 §I (A1:893), as scripts/analysis/j11_report.py:114 (at 9460b06)
A1_R2_REPLAY_ARMS = ("sft_plan", "prefix_m9", "prefix_m11", "prefix_zs_m9", "prefix_zs_m11")  # arms 2, 4-7
A1_R2_CONTENT_ARMS = ("advise_k10_fullctx", "takeover_k10", "show_k10", "advise_k10_neutral")  # arms 9-12
A1_R2_REGISTERED_TOTAL = {
    "hosted_calls": "<= 15,627",
    "breakdown": "13,828 for arms 1-10, arms 11 and 12 add <= 1,607, and §4.2 adds <= 192 only if it fires",
    "citation": f"{A1_PREREG}:561",
}
# Amendment 1 §C descriptives (arms 9-12). b2_decomposition defines the copy rate of a shown action
# (scripts/analysis/b2_decomposition.py:492-603: _normalise_ws :492, _render_action :496-504, read_events :507-530,
# shown_action_rows :534-557, copy_rate :560-603) but neither "fenced code" nor length; those, and the copy rate of
# advice (a ```python block inside the advice counts), are scripts/analysis/j17_channel_fixes.py:95-100 and
# :313-356 (ledger DEC-06), ported here.
A1_R2_FENCED_BLOCK = r"```[^`\n]*\n.*?```"  # j17_channel_fixes.py:98
A1_R2_PYTHON_BLOCK = r"```[ \t]*python[ \t]*\r?\n.*?```"  # j17_channel_fixes.py:100
# Amendment 2 (A1:914-918): the dev high-effort result cited beside P3 (ledger CEILHI-01, CEILHI-03).
A1_R2_CEILHI = {
    "source": "campaign/results/j17_planning_lit_20260924.report.json",
    "quality": {"key": "ceilhi.quality.goal_pass", "high_minus_medium_pp": 11.97, "ci95_pp_scenario": [6.14, 18.43],
                "high": 0.8834, "medium": 0.7637, "n_pairs": 114},
    "ni_reread": {"key": "ceilhi.ni_reread.{high,medium}_minus_prefix_c81_bplus_m11.goal_pass",
                  "rule": "ceiling - arm; holds iff round(scenario upper bound, 2) < +7.00",
                  "high": {"diff_pp": 7.22, "ci95_pp_scenario": [3.21, 11.47], "reading": "fails"},
                  "medium": {"diff_pp": -4.75, "ci95_pp_scenario": [-11.81, 1.16], "reading": "holds"}},
    "ledger": ["CEILHI-01", "CEILHI-03"],
    "exploratory": True,
}
# §7 item 5 (A1:524): the J9 Claim F1 negative, static text from A1:54-58.
A1_R2_J9_F1 = {
    "citation": f"{A1_PREREG}:524 (text at :54-58; docs/prereg_j9_freeze_20260920.md:143)",
    "dev_only": True,
    "statement": ("J9's Claim F1 (selective escalation) is reported as a dev-only negative: neither the linear verifier "
                  "head nor the sequential router discriminates outcome-critical intervention points (scored AUROC "
                  "0.3867-0.5082), and the executor self-gate's p_ask never exceeds 0.0347 against thresholds of "
                  "0.3, 0.5 and 0.7."),
    "auroc_range": [0.3867, 0.5082],
    "p_ask_max": 0.0347,
}
A1_R2_PIN = {"planner_model_requested": "gpt-5.6-luna", "planner_cli_version": "0.153.4",
             "citation": f"{A1_PREREG}:578-590 (§9.1)"}


def a1_r2_scored_as_recorded(arm: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    """B7, A1 §5.1 (:255-261): every error_type other than crash is an outcome of the arm and is scored as recorded.
    score_tgc (v1 §6.1) gives such an episode TGC None when its result.json records a non-zero TGC, which drops the
    pair from every TGC contrast; here it keeps the TGC it records. goal_pass is already read as recorded. A scored
    failure with no recorded TGC keeps score_tgc's 0 (nothing is recorded to keep) and is counted."""
    runs = loaded.get("runs") or {}
    changed: list[tuple[str, int]] = []
    unrecorded = 0
    for key, ep in arm["episodes"].items():
        row = runs.get(key) or {}
        if row.get("error_type") not in SCORED_FAILURE_TYPES:
            continue
        rec = recorded_tgc(row)
        if rec is None:
            unrecorded += 1
            continue
        if ep.get("tgc") != rec:
            ep["tgc"] = rec
            changed.append(key)
    if changed:
        tg = [e["tgc"] for e in arm["episodes"].values() if e["tgc"] is not None]
        arm["tgc_mean"] = round(statistics.fmean(tg), 6) if tg else None
    arm["tgc_scored_as_recorded"] = {
        "rule": f"{A1_PREREG}:255-261 (a non-crash failure is scored as recorded)",
        "n_changed": len(changed),
        "changed": [f"{s}/{t}" for t, s in sorted(changed)],
        "n_failure_without_recorded_tgc_scored_0": unrecorded,
    }
    return arm


def a1_r2_answered_asks_last_attempt(events_path: Path) -> Optional[int]:
    """Amendment 1 §I: executor asks the planner answered live in the attempt that wrote result.json; None without a
    log. Ported from scripts/analysis/j11_report.py:282-305 (at 9460b06): an answered ask is an `intervention` event
    from actor planner with payload.forced False (the loop writes forced True for scheduled advice and takeovers,
    src/sidekick/systems/loop.py:918, :962); events before the last run_start belong to an earlier attempt."""
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            ev = json.loads(line) if line.strip() else None
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    start = max((i for i, ev in enumerate(events) if ev.get("event_type") == "run_start"), default=0)
    return sum(1 for ev in events[start:]
               if ev.get("event_type") == "intervention" and ev.get("actor") == "planner"
               and isinstance(ev.get("payload"), dict) and ev["payload"].get("forced") is False)


def _a1_r2_contrast_rows(report: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[str]]]:
    """(id, row, arms) for every P, CF, S, E and B1 row (B1 by its flag and h* ids)."""
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else {}
    out = []
    for r in list(report.get("predictions") or []) + list((am1.get("cf") or {}).get("predictions") or []):
        out.append((r["id"], r, [a for a in (r.get("left"), r.get("right")) if isinstance(a, str)]))
    for rows in (report.get("supporting_contrasts") or [], report.get("exploratory_contrasts") or []):
        for r in rows:
            out.append((r["id"], r, _a1_r2_row_arms(r)))
    for key, suffix in (("handoff_only_ni", "_flag"), ("handoff_only_ni_hstar", "")):
        for r in am1.get(key) or []:
            out.append((f"{r['id']}{suffix}", r, [a for a in (r.get("left"), r.get("right")) if isinstance(a, str)]))
    return out


def a1_r2_executor_asks(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    tasks: list[str],
    seeds: list[int],
) -> dict[str, Any]:
    """B4, Amendment 1 §I (A1:867-896), as scripts/analysis/j11_report.py:308-350 (at 9460b06) implements it for J11:
    per arm, the episodes with a live-answered ask, the answering calls, and the bound on the arm mean (episodes
    with one or more / the registered matrix, in pp); per contrast that uses a replaying arm (2, 4-7), each side's
    bound. A bound of 1.00 pp or more is printed in the verdict's sentence. Reporting only: no verdict changes."""
    expected = len(tasks) * len(seeds)
    matrix = {(t, s) for t in tasks for s in seeds}
    per_arm: dict[str, dict[str, Any]] = {}
    for label in (a for a in A1_ARMS if a in arms and a in arm_dirs):
        files = a1_am4_episode_files(Path(arm_dirs[label]))
        by_key = {k: a1_r2_answered_asks_last_attempt(f["events"]) for k, f in files.items() if k in matrix}
        asked = {k: n for k, n in by_key.items() if n}
        per_arm[label] = {
            "n_episodes_with_answered_ask": len(asked),
            "n_scored_episodes_with_answered_ask": sum(1 for k in asked if k in arms[label]["episodes"]),
            "n_answered_ask_calls": sum(asked.values()),
            "n_episodes_without_event_log": sum(1 for n in by_key.values() if n is None),
            "bound_pp": round(100.0 * len(asked) / expected, 2) if expected else None,
            "episodes": [f"{s}/{t}" for t, s in sorted(asked)],
        }
    per_contrast: dict[str, dict[str, Any]] = {}
    for cid, _row, labels in _a1_r2_contrast_rows(report):
        if not any(a in A1_R2_REPLAY_ARMS for a in labels) or any(a not in per_arm for a in labels):
            continue
        sides = {a: per_arm[a]["bound_pp"] for a in dict.fromkeys(labels)}
        worst = max((b or 0.0) for b in sides.values())
        per_contrast[cid] = {"bound_pp": sides, "max_bound_pp": worst,
                             "bound_reaches_1pp": worst >= A1_R2_ASK_BOUND_FLAG_PP}
    return {
        "reporting_only": True,
        "rule": f"{A1_PREREG} Amendment 1 §I (:867-896; the ledger PROV-02 bound)",
        "implementation": "scripts/analysis/j11_report.py:282-350 (at 9460b06), ported",
        "definition": ("an intervention event from actor planner with payload.forced false in the attempt that "
                       "wrote result.json; bound = episodes with one or more / the matrix, in pp"),
        "denominator": expected,
        "per_arm": per_arm,
        "per_contrast": per_contrast,
        "n_answered_ask_calls_total": sum(v["n_answered_ask_calls"] for v in per_arm.values()),
        "registered_total": A1_R2_REGISTERED_TOTAL,
        "flag_pp": A1_R2_ASK_BOUND_FLAG_PP,
    }


def _a1_r2_next_executor_action(events: list[dict[str, Any]], i: int) -> Optional[dict[str, Any]]:
    """b2.shown_action_rows' next action (b2_decomposition.py:543-549; j17_channel_fixes.py:313-322)."""
    for later in events[i + 1:]:
        if later.get("event_type") == "intervention":
            return None
        if later.get("event_type") == "action" and later.get("actor") == "executor":
            return later
    return None


def a1_r2_content(arms: dict[str, dict[str, Any]], arm_dirs: dict[str, Path]) -> dict[str, Any]:
    """B5, Amendment 1 §C 'Descriptive' (arms 9-12): per arm, the share of interventions carrying a fenced code
    block, the median intervention length (characters of payload.correction) and the executor's copy rate --
    show_k10's by b2_decomposition.copy_rate (a shown action reproduced verbatim next, whitespace-normalised), the
    advice arms' by the same test widened to a ```python block inside the advice (j17_channel_fixes._copied,
    :325-336). Over the scored episodes' last attempt. Descriptive: not decision-bearing."""
    import re  # noqa: E402 (lazy: a top-level import would move cited lines)

    fenced_re = re.compile(A1_R2_FENCED_BLOCK, re.DOTALL)
    python_re = re.compile(A1_R2_PYTHON_BLOCK, re.DOTALL | re.IGNORECASE)
    out: dict[str, Any] = {
        "label": "DESCRIPTIVE (Amendment 1 §C; not decision-bearing)",
        "citation": f"{A1_PREREG} Amendment 1 §C (:802-803)",
        "definitions": {
            "fenced_code": "an opening ``` line (any info string), text, a closing ``` (j17_channel_fixes.py:95-98)",
            "length": "characters of the intervention's payload.correction (j17_channel_fixes.py:348)",
            "copy_rate_show": "b2_decomposition.copy_rate (:560-603): shown actions the executor reproduces next",
            "copy_rate_advice": ("interventions whose next executor action reproduces the advice, or a ```python "
                                 "block inside it (j17_channel_fixes.py:325-336)"),
            "copy_rate_takeover": "not applicable: the planner's action is executed, nothing is shown or advised",
        },
        "arms": {},
    }
    try:
        from scripts.analysis import b2_decomposition as b2  # noqa: E402
    except Exception as exc:  # descriptive only: never fatal
        out["status"] = f"error: {type(exc).__name__}: {exc}"
        return out
    for label in (a for a in A1_R2_CONTENT_ARMS if a in arms and a in arm_dirs):
        files = a1_am4_episode_files(Path(arm_dirs[label]))
        paths = {k: files[k]["events"] for k in sorted(arms[label]["episodes"]) if k in files}
        n_missing = n_bad = 0
        rows: list[dict[str, Any]] = []
        for key, path in paths.items():
            if not Path(path).is_file():
                n_missing += 1
                continue
            events, bad = b2.read_events(Path(path))
            n_bad += bad
            for i, ev in enumerate(events):
                if ev.get("event_type") != "intervention":
                    continue
                payload = ev.get("payload") or {}
                text = str(payload.get("correction") or "")
                nxt = _a1_r2_next_executor_action(events, i)
                rendered = b2._render_action(nxt.get("payload") or {}) if nxt is not None else None
                target = b2._normalise_ws(rendered) if rendered is not None else None
                candidates = [text, *(m.group(0) for m in python_re.finditer(text))]
                rows.append({"source": str(payload.get("source") or "advice"), "chars": len(text),
                             "fenced": fenced_re.search(text) is not None,
                             "copied": target is not None and any(b2._normalise_ws(c) == target for c in candidates)})
        chars = [r["chars"] for r in rows]
        n_fenced = sum(1 for r in rows if r["fenced"])
        blk: dict[str, Any] = {
            "n_episodes": len(arms[label]["episodes"]),
            "n_episodes_without_events": n_missing,
            "n_unparseable_event_lines": n_bad,
            "n_interventions": len(rows),
            "n_by_source": dict(sorted(Counter(r["source"] for r in rows).items())),
            "n_fenced_code": n_fenced,
            "share_fenced_code": round(n_fenced / len(rows), 6) if rows else None,
            "median_chars": statistics.median(chars) if chars else None,
        }
        if label == "show_k10":
            cr = b2.copy_rate({k: Path(p) for k, p in paths.items()})
            blk["copy_rate"] = cr["copy_rate"]
            blk["copy"] = {"definition": "copy_rate_show", "n_shown": cr["n_shown"], "n_copied": cr["n_copied"]}
        elif label == "takeover_k10":
            blk["copy_rate"] = None
            blk["copy"] = {"definition": "copy_rate_takeover"}
        else:
            n_copied = sum(1 for r in rows if r["copied"])
            blk["copy_rate"] = round(n_copied / len(rows), 6) if rows else None
            blk["copy"] = {"definition": "copy_rate_advice", "n_copied": n_copied}
        out["arms"][label] = blk
    out["status"] = "ok"
    return out


def a1_r2_limit_rates(report: dict[str, Any], arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """B6, Amendment 1 §D1: each arm's limit rate beside its mean and beside every contrast that uses it."""
    rates = {a: r["limit_rate"] for a, r in am1_limit_rates(arms).items()}
    for label, blk in (report.get("arms") or {}).items():
        if isinstance(blk, dict) and not blk.get("not_run") and label in rates:
            blk["limit_rate"] = rates[label]
    for _cid, row, labels in _a1_r2_contrast_rows(report):
        if row.get("status") == "not_run" or row.get("verdict") == "not_run":
            continue
        row["limit_rates"] = {a: rates.get(a) for a in dict.fromkeys(labels)}
    return rates


def a1_r2_pairwise(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    rates: dict[str, Any],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """B6, A1 §7 item 2 (:516-517): every pair of registered arms given, on goal_pass, both clusterings. A pair a
    registered row names keeps that row's orientation (and the row's Holm-adjusted p is quoted for P rows); any other
    pair is later arm − earlier arm in A1_ARMS order, unadjusted and labelled exploratory. An incomplete arm (or an
    Amendment 5 union above the cap) prints the pair without a p; arms 11-12 not run print no value."""
    registered: dict[tuple[str, str], dict[str, Any]] = {}
    for _cid, row, labels in _a1_r2_contrast_rows(report):
        if row.get("kind", "paired") in ("paired", "paired_contrast") and len(labels) == 2:
            registered.setdefault((labels[0], labels[1]), row)
    not_run = set(A1_PAIR_ARMS) if report.get("arms_11_12_not_run") else set()
    rd = _load_replay_divergence()
    labels = [a for a in A1_ARMS if a in arms]
    rows = []
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            left, right = (a, b) if (a, b) in registered else (b, a)
            reg = registered.get((left, right))
            row: dict[str, Any] = {"left": left, "right": right, "metric": "goal_pass",
                                   "registered_row": reg["id"] if reg else None,
                                   "label": (f"registered as {reg['id']}" if reg
                                             else "exploratory (A1 §7 item 2): unadjusted")}
            if reg is not None and isinstance(reg.get("holm"), dict):
                row["holm_p_adjusted_at_registered_threshold"] = reg["holm"].get("p_adjusted")
            if {left, right} & not_run:
                row.update(status="not_run", goal_pass=None)
                rows.append(row)
                continue
            la, ra = a1_am5_pair(arms, left, right)
            cmp = a1_contrast(la["episodes"], ra["episodes"], A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
            row["goal_pass"] = _public_contrast(cmp) | {"p_value_two_sided_at_0": _p_two_sided(cmp["scenario"], 0.0)}
            incomplete = [x for x, arm in ((left, la), (right, ra)) if not arm["complete"]]
            _excluded, verdict = a1_am5_exclusion(arms, left, right)
            if incomplete or verdict != rd.VERDICT_OK:
                row.update(status="incomplete", incomplete_arms=incomplete)
                row["goal_pass"].pop("p_value_two_sided_at_0", None)
            else:
                row["status"] = "ok"
            row["limit_rates"] = {left: rates.get(left), right: rates.get(right)}
            rows.append(row)
    return {"citation": f"{A1_PREREG}:516-517 (§7 item 2)", "n_pairs_of_arms": len(rows),
            "adjustment": "Holm within the family for P1, P3, P4, P6 (quoted from their rows); unadjusted elsewhere",
            "rows": rows}


def a1_r2_p3_limit_excluded(arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """B6, A1:378-382: P3's limit-excluded variant, reported only as a sensitivity -- the pairs whose reference
    (arm 3) episode hit the step limit are dropped (as scripts/analysis/j16_robustness.py:1622-1629 on dev). The
    caveat is A1's: exclusion selects on the reference arm's own failures."""
    left, right = "prefix_m11", A1_PLAN_SOURCE_ARM
    base = {"citation": f"{A1_PREREG}:378-382", "sensitivity_only": True, "decision_bearing": False,
            "left": left, "right": right,
            "caveat": ("exclusion selects on the reference arm's own failures: on dev the cap-81 ceiling's 18 dropped "
                       "episodes scored 0.179 against 0.873 for the 96 kept (campaign/results/"
                       "j16_robustness_20260923.report.json)")}
    if left not in arms or right not in arms:
        return base | {"status": "arm_absent"}
    la, ra = a1_am5_pair(arms, left, right)
    kept = {k for k, e in ra["episodes"].items() if e.get("error_type") != A1_LIMIT_ERROR}
    dropped = [k for k in ra["episodes"] if k not in kept]
    cmp = a1_contrast({k: v for k, v in la["episodes"].items() if k in kept},
                      {k: v for k, v in ra["episodes"].items() if k in kept},
                      A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
    lo = (cmp["scenario"].get("ci95_pp") or [None])[0]
    out = base | {"n_reference_dropped_limit": len(dropped), "n_reference_kept": len(kept),
                  "goal_pass": _public_contrast(cmp),
                  "reading_at_minus_7": (None if lo is None else "holds" if lo > -7.00 else "fails"),
                  "reading_rule": "unadjusted scenario lower bound above -7.00 pp (sensitivity; no Holm, no verdict)"}
    if not (la["complete"] and ra["complete"]):
        out.update(status="incomplete", reading_at_minus_7=None)
    else:
        out["status"] = "ok"
    return out


def _a1_r2_find(rows: Any, rid: str) -> Optional[dict[str, Any]]:
    return next((r for r in rows or [] if isinstance(r, dict) and r.get("id") == rid), None)


def _a1_r2_ho(blk: Any) -> Optional[dict[str, Any]]:
    """The handoff-only summary of a B1 / S6 / b4_extra block."""
    if not isinstance(blk, dict):
        return None
    ho = blk.get("handoff_only") if isinstance(blk.get("handoff_only"), dict) else None
    out = {k: blk.get(k) for k in ("n_pairs", "n_handoff", "n_silenced") if k in blk}
    if ho:
        out |= {k: ho.get(k) for k in ("diff_pp", "ci95_pp_scenario", "ci95_pp_task") if k in ho}
    if isinstance(blk.get("ni"), dict):
        out["ni_reading"] = blk["ni"].get("reading")
    if isinstance(blk.get("status"), str):
        out["status"] = blk["status"]
    return out or None


def a1_r2_b4_companion(report: dict[str, Any], pointer: str) -> Optional[dict[str, Any]]:
    """Resolve an A1_AM1_B4_COMPANIONS(_HSTAR) pointer to the handoff-only numbers it names."""
    am1 = report.get("amendment1") or {}
    negated = pointer.endswith("(negated)")
    if pointer.startswith("amendment1.handoff_only_ni"):
        key, rid = pointer.split("[", 1)[0].split(".", 1)[1], pointer.split("[", 1)[1].split("]", 1)[0]
        out = _a1_r2_ho((_a1_r2_find(am1.get(key), rid) or {}).get("goal_pass"))
    elif pointer.startswith("supporting_contrasts[S6]"):
        _, key, receiver, _ho = pointer.split(".")
        out = _a1_r2_ho(((_a1_r2_find(report.get("supporting_contrasts"), "S6") or {}).get(key) or {}).get(receiver))
    elif pointer.startswith("amendment1.b4_extra."):
        blk = (am1.get("b4_extra") or {}).get(pointer.rsplit(".", 1)[1]) or {}
        out = _a1_r2_ho(blk.get("goal_pass") if isinstance(blk.get("goal_pass"), dict) else blk)
    elif pointer.startswith("amendment1.decomposition"):
        key = pointer.split(" ", 1)[0].split(".", 1)[1]
        out = {}
        for name, blk in (am1.get(key) or {}).items():
            gp = blk.get("goal_pass") if isinstance(blk, dict) and isinstance(blk.get("goal_pass"), dict) else {}
            out[name] = {"n_handoff": gp.get("n_handoff"),
                         "contribution_handoff_pp": (gp.get("contribution_handoff") or {}).get("diff_pp"),
                         "contribution_silenced_pp": (gp.get("contribution_silenced") or {}).get("diff_pp")}
        out = out or None
    else:
        out = None
    if out is not None and negated:
        out = dict(out, orientation="the companion is the negated orientation of this row")
    return out


def a1_r2_hstar_labels(report: dict[str, Any]) -> None:
    """B3, Amendment 3 (A1:951-963): h* is the registered handoff indicator. The `*_hstar` rows are marked as the
    registered version and the unsuffixed ones as the handoff_occurred flag companion; P3's (and every) B4 entry
    points at the h* rows, the flag map kept as b4_companions_flag; the registered BY sentences are the h* ones.
    Key names are unchanged."""
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else None
    if am1 is None:
        return
    hstar_ok = (am1.get("hstar") or {}).get("status") == "ok"
    reg = "registered (Amendment 3: h*, the executor took control)"
    comp = "companion (Amendment 3: the handoff_occurred flag, printed as a sensitivity)"
    am1["registered_h"] = "hstar"
    am1["registered_h_note"] = (f"{A1_PREREG} Amendment 3 (:951-963): every handoff-only quantity is registered with "
                                "h*; the *_hstar keys hold it, the unsuffixed keys the flag companion")
    for key, label in (("handoff_only_ni_hstar", reg), ("handoff_only_ni", comp)):
        for row in am1.get(key) or []:
            row["version"] = label
            row["registered_h"] = "hstar"
    for key, label in (("decomposition_hstar", reg), ("decomposition", comp)):
        for blk in (am1.get(key) or {}).values():
            if isinstance(blk, dict):
                blk["version"] = label
    for key, label in (("multiplicity_sensitivity_hstar", reg), ("multiplicity_sensitivity", comp)):
        if isinstance(am1.get(key), dict):
            am1[key]["version"] = label
    s6 = _a1_r2_find(report.get("supporting_contrasts"), "S6")
    if s6 is not None:
        s6["registered_h"] = "hstar"
        s6["versions"] = {"goal_pass_hstar": reg, "goal_pass": comp}
    flag_map = dict(am1.get("b4_companions") or A1_AM1_B4_COMPANIONS)
    am1["b4_companions_flag"] = flag_map
    if hstar_ok:
        am1["b4_companions"] = dict(flag_map, **A1_AM1_B4_COMPANIONS_HSTAR)
        am1["multiplicity_sensitivity_registered"] = "amendment1.multiplicity_sensitivity_hstar"
    else:
        am1["b4_companions_note"] = "h* not computed: the B4 entries stay on the flag rows"
        am1["multiplicity_sensitivity_registered"] = "amendment1.multiplicity_sensitivity"
    for rows in (report.get("predictions") or [], report.get("supporting_contrasts") or [],
                 report.get("exploratory_contrasts") or []):
        for row in rows:
            pointer = am1["b4_companions"].get(row.get("id"))
            if pointer:
                row["b4_companion"] = {"key": pointer, "h": "hstar" if "hstar" in pointer else "flag",
                                       "handoff_only": a1_r2_b4_companion(report, pointer),
                                       "flag_key": flag_map.get(row["id"])}


def _a1_r2_pp(v: Any) -> str:
    return "n/a" if v is None else f"{v:+.2f}"


def _a1_r2_ci(ci: Any) -> str:
    return "n/a" if not ci or ci[0] is None else f"[{ci[0]:+.2f}, {ci[1]:+.2f}]"


def a1_r2_tgc_atom(row: dict[str, Any]) -> Optional[str]:
    """B1, A1 §5.2 (:275-277): TGC is binary, so its bounds sit on atoms (k / n); a bound on the threshold's nearest
    atom, round(t x n) / n, is reported as such, not as a pass or fail by a hair."""
    tgc = row.get("tgc_secondary")
    if not isinstance(tgc, dict) or not isinstance(tgc.get("scenario"), dict) or not tgc.get("n_pairs"):
        return None
    n = int(tgc["n_pairs"])
    t = float(row.get("threshold_pp") or 0.0) / 100.0
    k = round(t * n)
    atom_pp = round(100.0 * k / n, 2)
    ci = tgc["scenario"].get("ci95_pp")
    if not ci or ci[0] is None:
        return None
    on = [name for name, v in (("lower", ci[0]), ("upper", ci[1])) if round(v, 2) == atom_pp]
    if not on:
        return None
    note = (f"TGC's {' and '.join(on)} bound sits on the threshold's nearest atom ({k}/{n} = {atom_pp:+.2f} pp): "
            "on the atom, not a pass or fail by a hair (A1 §5.2)")
    tgc["atom_note"] = note
    return note


def a1_r2_signflip_disagreement(row: dict[str, Any]) -> Optional[str]:
    """B1, A1 §5.5 (:317-318): the cluster sign-flip p beside the bootstrap verdict; a disagreement is said in the
    verdict's sentence. For P5 (supported by a non-rejection) the bootstrap event is 'significantly positive'."""
    perm = row.get("permutation_sensitivity")
    v = row.get("verdict")
    if not row.get("decidable") or not isinstance(perm, dict) or perm.get("p_value") is None:
        return None
    if v not in ("supported", "not_supported", "reversed", "directionally_consistent"):
        return None
    p = float(perm["p_value"])
    point = ((row.get("contrast") or {}).get("scenario") or {}).get("diff_pp")
    if row.get("rule") == "not_positive_excluding_zero":
        boot, sign = v == "not_supported", p <= 0.05 and (point or 0) > 0
    else:
        boot, sign = v in ("supported", "reversed"), p <= 0.05
    if boot == sign:
        return None
    return (f"the cluster sign-flip p ({perm.get('method')}, {perm.get('alternative', 'two-sided')}) is {p:.4f}, "
            f"which {'rejects' if sign else 'does not reject'} at 0.05 and so disagrees with the bootstrap verdict "
            "(A1 §5.5; not decision-bearing)")


def a1_r2_sentences(report: dict[str, Any], asks: dict[str, Any]) -> dict[str, str]:
    """B1, B2, B4 and B3's BY: one sentence per P row and CF1 carrying what A1 says must share it."""
    am1 = report.get("amendment1") if isinstance(report.get("amendment1"), dict) else {}
    p = {r["id"]: r for r in report.get("predictions") or []}
    cf = am1.get("cf") if isinstance(am1.get("cf"), dict) else {}
    cf1 = _a1_r2_find(cf.get("predictions"), "CF1")
    by_key = "multiplicity_sensitivity_hstar" if am1.get("registered_h") == "hstar" and isinstance(
        am1.get("multiplicity_sensitivity_hstar"), dict) else "multiplicity_sensitivity"
    by_flags = {f["id"]: f for f in (am1.get(by_key) or {}).get("flags") or []}
    ask_pc = (asks or {}).get("per_contrast") or {}
    out: dict[str, str] = {}
    for row in list(p.values()) + ([cf1] if cf1 else []):
        rid, v = row["id"], row.get("verdict")
        parts: list[str] = []
        if row.get("kind") == "cost_ratio":
            head = (f"{rid} ({row.get('left')} vs {row.get('right')}, cost): {v}"
                    + (f", ratio {row['ratio']}" if row.get("ratio") is not None else ""))
            am4 = row.get("amendment4") or {}
            if am4:
                parts.append(f"Amendment 4: calls clause under both conventions {am4.get('calls_holds_both')}, "
                             f"tokens clause {am4.get('tokens_holds_both')}")
        else:
            sc = (row.get("contrast") or {}).get("scenario") or {}
            head = f"{rid} ({row.get('left')} − {row.get('right')}, goal_pass): {v}"
            if row.get("decidable"):
                holm = row.get("holm") or {}
                head += (f", {_a1_r2_pp(sc.get('diff_pp'))} pp, scenario {_a1_r2_ci(sc.get('ci95_pp'))}"
                         + (f", Holm-adjusted p {holm['p_adjusted']:.4f}" if holm.get("p_adjusted") is not None
                            else ""))
            elif row.get("reason"):
                head += f" ({row['reason']})"
            if row.get("decidable"):  # a refused row draws no reading (A9), so nothing is said about its bounds
                for note in (a1_r2_signflip_disagreement(row), a1_r2_tgc_atom(row)):
                    if note:
                        parts.append(note)
        if rid == "P1":
            parts.append("described only as correction-prompt advice at every step against the m = 11 prefix, never "
                         "as advice at matched budget or as ruling out a budget effect (Amendment 1 §E, A1:829-833)")
            v2 = (p.get("P2") or {}).get("verdict")
            if v2 == "not_supported":
                parts.append("P2 is not supported, so P1 is uninterpretable as a channel result and is reported as a "
                             f"budget-confounded comparison, whatever its sign [{A1_PREREG}:358-359]")
            elif v2 != "supported":
                parts.append(f"P2 is not decided ({v2}): P1 cannot be read as a channel result until it is "
                             f"[{A1_PREREG}:358-359]")
        if rid == "P3":
            parts.append("non-inferiority to the medium-effort planner in this harness, never to the planner at its "
                         "best effort (Amendment 2, A1:914-918); dev, exploratory: the high-effort planner alone "
                         "scores +11.97 pp goal_pass above the medium one on 114 keys [+6.14, +18.43], and against it "
                         "prefix_m11 is not non-inferior (ceiling − arm +7.22 [+3.21, +11.47]; CEILHI-01, CEILHI-03)")
            for key, what in (("handoff_only_ni_hstar", "handoff-only (h*, registered, Amendment 3)"),
                              ("handoff_only_ni", "flag companion")):
                b1 = _a1_r2_find(am1.get(key), "B1a")
                if b1 is None:
                    continue
                s = _a1_r2_ho(b1.get("goal_pass")) or {}
                parts.append(f"{what} B1a: {s.get('ni_reading', b1.get('status'))}, {_a1_r2_pp(s.get('diff_pp'))} pp "
                             f"over {s.get('n_handoff')} handoff pairs, scenario {_a1_r2_ci(s.get('ci95_pp_scenario'))} "
                             "(Amendment 1 §B1, A1:735; never changes P3's verdict)")
        if rid == "P6":
            e5 = _a1_r2_find(report.get("exploratory_contrasts"), "E5") or {}
            e5sc = (e5.get("goal_pass") or {}).get("scenario") if isinstance(e5.get("goal_pass"), dict) else None
            e5txt = ("not run" if e5.get("status") == "not_run" or e5sc is None
                     else f"{_a1_r2_pp(e5sc.get('diff_pp'))} pp {_a1_r2_ci(e5sc.get('ci95_pp'))}")
            cf1v = (cf1 or {}).get("verdict") if cf.get("status") != "not_run" else "not run"
            if v == "supported":
                parts.append(f'reported as "actions beat the registered advice prompt" [{A1_PREREG}:441-443], never '
                             "as a channel effect without that qualification")
            parts.append(f"E5 (takeover − neutral-prompt advice, exploratory): {e5txt}; CF1: {cf1v}")
            if cf1v == "supported":
                parts.append('CF1 is supported, so P6 is reported only as "actions beat correction-prompt advice", '
                             "never as a channel effect (Amendment 1 §C)")
        pc = ask_pc.get(rid)
        if pc and pc.get("bound_reaches_1pp"):
            sides = ", ".join(f"{a} {b:.2f} pp" for a, b in pc["bound_pp"].items() if b is not None)
            parts.append(f"live-answered executor asks bound the arm means at {sides} (Amendment 1 §I; no verdict "
                         "changes)")
        flag = by_flags.get(rid)
        if flag and flag.get("sentence"):
            parts.append(f"{flag['sentence']} ({'h*' if by_key.endswith('hstar') else 'flag'} BY family, "
                         "Amendment 1 §F)")
        out[rid] = head + ("; " + "; ".join(parts) if parts else "") + "."
        row["verdict_sentence"] = out[rid]
    return out


def a1_r2_provenance_statement(arm_dirs: dict[str, Path]) -> dict[str, Any]:
    """B7, §7 item 8 (A1:527-528) from the episode manifests: the model requested, the CLI version, and that the
    served model is not observable (A1 §9.1)."""
    per_arm: dict[str, Any] = {}
    models: Counter[str] = Counter()
    cli: Counter[str] = Counter()
    for label, root in arm_dirs.items():
        m_c: Counter[str] = Counter()
        c_c: Counter[str] = Counter()
        for path in sorted(Path(root).rglob("result.json")) if Path(root).exists() else []:
            try:
                prov = (json.loads((path.parent / "manifest.json").read_text(encoding="utf-8")) or {}).get("provenance")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                continue
            if not isinstance(prov, dict) or prov.get("planner_type") != "codex":
                continue
            m_c[str(prov.get("planner_model_requested"))] += 1
            c_c[str(prov.get("planner_cli_version"))] += 1
        if m_c:
            per_arm[label] = {"planner_model_requested": dict(m_c), "planner_cli_version": dict(c_c)}
        models.update(m_c)
        cli.update(c_c)
    seen_m = ", ".join(f"{m} ({n})" for m, n in sorted(models.items())) or "no hosted episode manifest"
    seen_c = ", ".join(f"{c} ({n})" for c, n in sorted(cli.items())) or "none"
    return {
        "citation": f"{A1_PREREG}:527-528 (§7 item 8), §9.1",
        "pinned": A1_R2_PIN,
        "per_arm": per_arm,
        "statement": (f"Hosted episodes requested {seen_m}, through codex CLI {seen_c} (pinned: gpt-5.6-luna at "
                      "0.153.4). The model that actually served a call is not observable: neither the codex exec "
                      "--json stream nor the session transcript carries a server-reported model id, so the "
                      "no-substitution rule is enforced on the request side only."),
    }


def a1_r2_phase_b(
    report: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    arm_dirs: dict[str, Path],
    tasks: list[str],
    seeds: list[int],
    *,
    pairwise: bool,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Phase B: rows and wording only; no verdict, family, threshold or exit code moves."""
    a1_r2_hstar_labels(report)  # B3 (before the sentences, which read the registered BY family)
    asks = a1_r2_executor_asks(report, arms, arm_dirs, tasks, seeds)  # B4
    report["executor_asks"] = asks
    rates = a1_r2_limit_rates(report, arms)  # B6 (§D1)
    report["p3_limit_excluded"] = a1_r2_p3_limit_excluded(arms, n_boot=n_boot, seed=seed)  # B6 (A1:378-382)
    if pairwise:
        report["pairwise_contrasts"] = a1_r2_pairwise(report, arms, rates, n_boot=n_boot, seed=seed)  # B6
    else:
        report["pairwise_contrasts"] = {"status": "not_computed", "reason": "pairwise=False (build_report_a1)"}
    report["content_descriptives"] = a1_r2_content(  # B5
        {a: arm for a, arm in arms.items() if not (report.get("arms_11_12_not_run") and a in A1_PAIR_ARMS)},
        arm_dirs)
    report["verdict_sentences"] = a1_r2_sentences(report, asks)  # B1, B2, B4, B3's BY
    report["j9_claim_f1"] = A1_R2_J9_F1  # B7 (§7 item 5)
    report["provenance_statement"] = a1_r2_provenance_statement(arm_dirs)  # B7 (§7 item 8)
    report["tgc_scored_as_recorded"] = {  # B7
        a: arm.get("tgc_scored_as_recorded") for a, arm in arms.items() if arm.get("tgc_scored_as_recorded")}
    report.setdefault("unit_r2", {})["phase_b"] = ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    return report


if __name__ == "__main__":
    raise SystemExit(main())
