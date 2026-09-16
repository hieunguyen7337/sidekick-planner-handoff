#!/usr/bin/env python3
"""Estimate the seed count and non-inferiority margin for the HJ-7 test run.

The pilot input is a JSONL run log.  The simulation uses paired task-level TGC
differences and the same paired bootstrap implementation as ``hj1_gate.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from scripts.setup import hj1_gate as _hj1_gate  # noqa: E402


DEFAULT_INPUT = Path("campaign/results/hj1b_planner_20260915.runs.jsonl")
DEFAULT_OUTPUT = Path("campaign/results/hj7_power.json")
N_TASKS = 168
PLANNER_RATE = 0.68
SEED_COUNTS = (1, 2, 3, 4, 5)
SIDEKICK_RATES = (0.60, 0.64, 0.68)
MARGINS_PP = (3, 5, 7, 10)
LOGIT_CLIP = 1e-12
CALIBRATION_SAMPLES = 1_000_000
ZERO_VARIANCE_CROSSCHECKS = (
    "campaign/results/hj1a_exec8b_20260915.runs.jsonl",
    "campaign/results/hj1c_fixed_k_20260916.runs.jsonl",
    "campaign/results/hj1c_prompt_only_20260916.runs.jsonl",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_success(record: dict[str, Any]) -> bool:
    value = record.get("success")
    if isinstance(value, bool):
        return value
    return float(record.get("tgc") or 0.0) > 0.0


def as_tgc(record: dict[str, Any]) -> float:
    return float(record.get("tgc") or 0.0)


def load_planner_pairs(path: Path) -> tuple[
    dict[int, dict[str, dict[str, Any]]], int
]:
    by_seed: dict[int, dict[str, dict[str, Any]]] = {1: {}, 2: {}}
    duplicate_keys = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("system") != "planner_alone":
                continue
            seed = int(record.get("seed", 0))
            if seed not in by_seed:
                continue
            task_id = str(record["task_id"])
            if task_id in by_seed[seed]:
                duplicate_keys += 1
            by_seed[seed][task_id] = record
    return by_seed, duplicate_keys


def marginal_tgc(
    records: dict[str, dict[str, Any]],
) -> dict[str, int | float | None]:
    if not records:
        return {"n": 0, "mean": None}
    mean = sum(as_tgc(record) for record in records.values()) / len(records)
    return {"n": len(records), "mean": round(mean, 6)}


def measure_seed_noise(
    by_seed: dict[int, dict[str, dict[str, Any]]],
    duplicate_keys: int,
) -> dict[str, Any]:
    seed_1 = by_seed[1]
    seed_2 = by_seed[2]
    task_ids = sorted(set(seed_1) & set(seed_2))
    concordant_success = 0
    concordant_fail = 0
    discordant = 0
    for task_id in task_ids:
        first = as_success(seed_1[task_id])
        second = as_success(seed_2[task_id])
        if first and second:
            concordant_success += 1
        elif not first and not second:
            concordant_fail += 1
        else:
            discordant += 1

    n_pairs = len(task_ids)
    discordance_rate = discordant / n_pairs if n_pairs else None
    seed_1_mean = marginal_tgc(seed_1)
    seed_2_mean = marginal_tgc(seed_2)
    gap_pp = None
    if seed_1_mean["mean"] is not None and seed_2_mean["mean"] is not None:
        gap_pp = round((seed_1_mean["mean"] - seed_2_mean["mean"]) * 100, 4)
    return {
        "pairs": n_pairs,
        "concordant_success": concordant_success,
        "concordant_fail": concordant_fail,
        "discordant": discordant,
        "discordance_rate": None if discordance_rate is None else round(discordance_rate, 6),
        "discordance_rate_pp": (
            None if discordance_rate is None else round(discordance_rate * 100, 4)
        ),
        "per_seed_marginal_tgc": {"seed_1": seed_1_mean, "seed_2": seed_2_mean},
        "seed_1_minus_seed_2_gap_pp": gap_pp,
        "duplicate_task_seed_records": duplicate_keys,
        "unpaired_seed_1": len(seed_1) - n_pairs,
        "unpaired_seed_2": len(seed_2) - n_pairs,
    }


def fit_beta_calibration(discordance_rate: float | None) -> dict[str, float]:
    if discordance_rate is None:
        raise ValueError("cannot fit latent difficulty without two-seed pairs")
    mu = PLANNER_RATE
    sigma2 = mu * (1.0 - mu) - discordance_rate / 2.0
    if not 0.0 < sigma2 < mu * (1.0 - mu):
        raise ValueError(
            "observed discordance implies an invalid Beta variance: "
            f"sigma2={sigma2} for discordance={discordance_rate}"
        )
    assert 0.0 < sigma2 < mu * (1.0 - mu), (
        "observed discordance implies an invalid Beta variance: "
        f"sigma2={sigma2} for discordance={discordance_rate}"
    )
    total = mu * (1.0 - mu) / sigma2 - 1.0
    a = mu * total
    b = (1.0 - mu) * total
    sigma = float(np.sqrt(sigma2))
    implied = 2.0 * (mu * (1.0 - mu) - sigma2)
    return {
        "a": float(a),
        "b": float(b),
        "a_plus_b": float(total),
        "sigma2": float(sigma2),
        "sigma": sigma,
        "implied_two_seed_discordance": float(implied),
    }


def expit(values: np.ndarray) -> np.ndarray:
    """Numerically stable logistic function using only NumPy."""
    values = np.asarray(values, dtype=float)
    result = np.empty_like(values)
    positive = values >= 0.0
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    negative_exp = np.exp(values[~positive])
    result[~positive] = negative_exp / (1.0 + negative_exp)
    return result


def solve_logit_shift(
    p_samples: np.ndarray,
    target_rate: float,
    iterations: int = 80,
) -> float:
    """Solve E[expit(logit(p_i) + shift)] = target_rate by bisection."""
    assert 0.0 < target_rate < 1.0, "target rate must be strictly between zero and one"
    clipped = np.clip(np.asarray(p_samples, dtype=float), LOGIT_CLIP, 1.0 - LOGIT_CLIP)
    logits = np.log(clipped / (1.0 - clipped))
    lower = -64.0
    upper = 64.0
    for _ in range(iterations):
        middle = (lower + upper) / 2.0
        if float(np.mean(expit(logits + middle))) < target_rate:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2.0


def mixture_rho(discordance_rate: float | None) -> dict[str, float | bool | None]:
    independent_discordance = 2 * PLANNER_RATE * (1 - PLANNER_RATE)
    if discordance_rate is None:
        rho = 0.0
        clipped = True
    else:
        raw_rho = 1.0 - discordance_rate / independent_discordance
        rho = min(1.0, max(0.0, raw_rho))
        clipped = rho != raw_rho
    calibrated = (1.0 - rho) * independent_discordance
    return {
        "rho": float(rho),
        "independent_pair_discordance": float(independent_discordance),
        "implied_pair_discordance": float(calibrated),
        "rho_clipped_to_zero_or_one": clipped,
    }


def correlated_bernoulli(
    rng: np.random.Generator,
    rate: float,
    n_tasks: int,
    n_seeds: int,
    rho: float,
) -> np.ndarray:
    common_draw = rng.random(n_tasks) < rate
    independent_draws = rng.random((n_tasks, n_seeds)) < rate
    common_mode = rng.random(n_tasks) < rho
    return np.where(common_mode[:, None], common_draw[:, None], independent_draws)


def correlated_bernoulli_batch(
    rng: np.random.Generator,
    rate: float,
    n_reps: int,
    n_tasks: int,
    n_seeds: int,
    rho: float,
) -> np.ndarray:
    """Vectorized form of the original common-or-independent mixture."""
    common_draw = rng.random((n_reps, n_tasks)) < rate
    independent_draws = rng.random((n_reps, n_tasks, n_seeds)) < rate
    common_mode = rng.random((n_reps, n_tasks)) < rho
    return np.where(common_mode[:, :, None], common_draw[:, :, None], independent_draws)


def independent_seed_scores(
    rng: np.random.Generator,
    probabilities: np.ndarray,
    n_seeds: int,
) -> np.ndarray:
    draws = rng.random((probabilities.shape[0], probabilities.shape[1], n_seeds))
    return (draws < probabilities[:, :, None]).mean(axis=2)


def bootstrap_ci_pp(differences: np.ndarray, bootstrap_seed: int, reps: int) -> tuple[float, float]:
    """Return the imported gate's lower and upper bootstrap endpoints in pp.

    ``paired_diff`` computes base-minus-other.  Passing sidekick differences as
    the base arm and zeros as the other arm therefore gives the desired
    sidekick-minus-planner difference without duplicating its bootstrap.
    """
    synthetic_base = {
        (f"task_{index}", 0): {"tgc": float(value)}
        for index, value in enumerate(differences)
    }
    synthetic_other = {
        (f"task_{index}", 0): {"tgc": 0.0}
        for index in range(len(differences))
    }
    old_bootstrap = _hj1_gate.BOOTSTRAP
    old_seed = _hj1_gate.SEED
    _hj1_gate.BOOTSTRAP = reps
    _hj1_gate.SEED = bootstrap_seed
    try:
        result = _hj1_gate.paired_diff(synthetic_base, synthetic_other, "tgc")
    finally:
        _hj1_gate.BOOTSTRAP = old_bootstrap
        _hj1_gate.SEED = old_seed
    return float(result["ci95_pp"][0]), float(result["ci95_pp"][1])


def simulate_cells(
    rng: np.random.Generator,
    model_name: str,
    beta_a: float,
    beta_b: float,
    logit_shifts: dict[str, float],
    mixture_parameters: dict[str, float | bool | None],
    reps: int,
    bootstrap_reps: int,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for n_seeds in SEED_COUNTS:
        for sidekick_rate in SIDEKICK_RATES:
            half_widths: list[float] = []
            declarations = {margin: 0 for margin in MARGINS_PP}
            if model_name == "latent-difficulty":
                planner_probabilities = rng.beta(
                    beta_a, beta_b, size=(reps, N_TASKS)
                )
                clipped_probabilities = np.clip(
                    planner_probabilities, LOGIT_CLIP, 1.0 - LOGIT_CLIP
                )
                sidekick_probabilities = expit(
                    np.log(clipped_probabilities / (1.0 - clipped_probabilities))
                    + logit_shifts[f"{sidekick_rate:.2f}"]
                )
                planner_scores = independent_seed_scores(
                    rng, planner_probabilities, n_seeds
                )
                sidekick_scores = independent_seed_scores(
                    rng, sidekick_probabilities, n_seeds
                )
            else:
                planner_scores = correlated_bernoulli_batch(
                    rng,
                    PLANNER_RATE,
                    reps,
                    N_TASKS,
                    n_seeds,
                    float(mixture_parameters["rho"]),
                ).mean(axis=2)
                sidekick_scores = correlated_bernoulli_batch(
                    rng,
                    sidekick_rate,
                    reps,
                    N_TASKS,
                    n_seeds,
                    float(mixture_parameters["rho"]),
                ).mean(axis=2)
            differences_by_rep = sidekick_scores - planner_scores
            for differences in differences_by_rep:
                bootstrap_seed = int(rng.integers(0, 2**63 - 1))
                lower_pp, upper_pp = bootstrap_ci_pp(
                    differences, bootstrap_seed, bootstrap_reps
                )
                half_widths.append((upper_pp - lower_pp) / 2.0)
                for margin in MARGINS_PP:
                    if lower_pp >= -margin:
                        declarations[margin] += 1
            power = {}
            for margin in MARGINS_PP:
                estimate = declarations[margin] / reps
                mcse = float(np.sqrt(estimate * (1.0 - estimate) / reps))
                power[str(margin)] = {
                    "estimate": round(estimate, 6),
                    "mcse": round(mcse, 6),
                    "undetermined_at_80": bool(abs(estimate - 0.80) <= 2.0 * mcse),
                }
            cells.append(
                {
                    "n_seeds": n_seeds,
                    "sidekick_true_rate": sidekick_rate,
                    "planner_true_rate": PLANNER_RATE,
                    "mean_ci_half_width_pp": round(float(np.mean(half_widths)), 6),
                    "power_at_epsilon_pp": power,
                }
            )
    return cells


def smallest_equal_margin(cells: list[dict[str, Any]]) -> dict[str, int | None]:
    answer: dict[str, int | None] = {}
    for n_seeds in SEED_COUNTS:
        equal_cell = next(
            cell
            for cell in cells
            if cell["n_seeds"] == n_seeds
            and cell["sidekick_true_rate"] == PLANNER_RATE
        )
        powers = equal_cell["power_at_epsilon_pp"]
        answer[str(n_seeds)] = next(
            (
                margin
                for margin in MARGINS_PP
                if powers[str(margin)]["estimate"] >= 0.80
                and not powers[str(margin)]["undetermined_at_80"]
            ),
            None,
        )
    return answer


def print_table(report: dict[str, Any]) -> None:
    noise = report["observed_seed_noise"]
    print(
        "pairs={pairs} concordant_success={concordant_success} "
        "concordant_fail={concordant_fail} discordant={discordant} "
        "discordance={discordance_rate_pp}pp".format(**noise)
    )
    marginal = noise["per_seed_marginal_tgc"]
    print(
        "marginal_tgc seed1={:.4f} seed2={:.4f} gap={:.4f}pp".format(
            marginal["seed_1"]["mean"],
            marginal["seed_2"]["mean"],
            noise["seed_1_minus_seed_2_gap_pp"],
        )
    )
    print("zero-variance cross-check arms excluded from averaging: " + ", ".join(ZERO_VARIANCE_CROSSCHECKS))
    print("N  sidekick_rate  mean_half_width_pp  power@3  power@5  power@7  power@10")
    for cell in report["cells"]:
        power = cell["power_at_epsilon_pp"]

        def power_text(margin: int) -> str:
            estimate = power[str(margin)]["estimate"]
            mcse = power[str(margin)]["mcse"]
            marker = "?" if power[str(margin)]["undetermined_at_80"] else ""
            return f"{estimate:.3f}+/-{mcse:.3f}{marker}"

        print(
            "{}  {:.2f}           {:.3f}              {}  {}  {}  {}".format(
                cell["n_seeds"],
                cell["sidekick_true_rate"],
                cell["mean_ci_half_width_pp"],
                power_text(3),
                power_text(5),
                power_text(7),
                power_text(10),
            )
        )
    print(
        "smallest epsilon pp at >=80% power when equal: "
        + json.dumps(report["smallest_epsilon_pp_at_80_power"], sort_keys=True)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--reps",
        type=int,
        default=2000,
        help="Monte Carlo simulation replicates per cell (default: 2000)",
    )
    parser.add_argument(
        "--bootstrap-reps",
        type=int,
        default=200,
        help="paired bootstrap replicates per simulated experiment (default: 200)",
    )
    parser.add_argument(
        "--correlation-model",
        choices=("latent-difficulty", "mixture"),
        default="latent-difficulty",
    )
    parser.add_argument("--seed", type=int, default=20260916)
    args = parser.parse_args()
    if args.reps < 1:
        parser.error("--reps must be positive")
    if args.bootstrap_reps < 1:
        parser.error("--bootstrap-reps must be positive")
    return args


def main() -> int:
    args = parse_args()
    input_sha256 = sha256_file(args.input)
    by_seed, duplicate_keys = load_planner_pairs(args.input)
    observed = measure_seed_noise(by_seed, duplicate_keys)
    discordance_rate = observed["discordance_rate"]
    beta = fit_beta_calibration(discordance_rate)
    rng = np.random.default_rng(args.seed)
    calibration_sample = rng.beta(
        beta["a"], beta["b"], size=CALIBRATION_SAMPLES
    )
    logit_shifts = {
        f"{rate:.2f}": solve_logit_shift(calibration_sample, rate)
        for rate in SIDEKICK_RATES
    }
    mixture = mixture_rho(discordance_rate)
    correlation = {
        "model_used": args.correlation_model,
        "observed_discordance_rate": discordance_rate,
        "a": round(beta["a"], 6),
        "b": round(beta["b"], 6),
        "a_plus_b": round(beta["a_plus_b"], 6),
        "sigma2": round(beta["sigma2"], 6),
        "sigma": round(beta["sigma"], 6),
        "implied_two_seed_discordance": round(
            beta["implied_two_seed_discordance"], 6
        ),
        "logit_shift_by_target_rate": {
            key: round(value, 6) for key, value in logit_shifts.items()
        },
        "mixture_rho": round(float(mixture["rho"]), 6),
        "mixture_implied_pair_discordance": round(
            float(mixture["implied_pair_discordance"]), 6
        ),
        "mixture_rho_clipped_to_zero_or_one": mixture["rho_clipped_to_zero_or_one"],
        "description": (
            "latent-difficulty draws p_i ~ Beta(a,b) once per experiment; seeds "
            "are independent conditional on p_i, and sidekick q_i is a constant "
            "logit shift of the same p_i."
            if args.correlation_model == "latent-difficulty"
            else "common-or-independent mixture retained as the requested worst-case alternative."
        ),
        "logit_calibration_samples": CALIBRATION_SAMPLES,
    }

    cells = simulate_cells(
        rng,
        args.correlation_model,
        beta["a"],
        beta["b"],
        logit_shifts,
        mixture,
        args.reps,
        args.bootstrap_reps,
    )
    report: dict[str, Any] = {
        "schema": "hj7_power_v1",
        "input": {"path": str(args.input), "sha256": input_sha256},
        "seed": args.seed,
        "reps": args.reps,
        "bootstrap_reps": args.bootstrap_reps,
        "n_tasks": N_TASKS,
        "margins_pp": list(MARGINS_PP),
        "excluded_cross_checks": {
            "paths": list(ZERO_VARIANCE_CROSSCHECKS),
            "reason": "all-zero arms carry no usable variance and are not averaged in",
        },
        "observed_seed_noise": observed,
        "correlation_model": correlation,
        "bootstrap": {
            "source": "from scripts.setup import hj1_gate as _hj1_gate",
            "function": "_hj1_gate.paired_diff",
            "bootstrap_replicates_per_simulation": args.bootstrap_reps,
            "ni_rule": "lower endpoint ci95_pp[0] >= -epsilon_pp",
        },
        "power_resolution": {
            "target_power": 0.80,
            "undetermined_within_mcse": 2,
        },
        "cells": cells,
        "smallest_epsilon_pp_at_80_power": smallest_equal_margin(cells),
    }
    print_table(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
