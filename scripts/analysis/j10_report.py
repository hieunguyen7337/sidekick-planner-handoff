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


def main(argv: Optional[list[str]] = None) -> int:
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


if __name__ == "__main__":
    raise SystemExit(main())
