"""Regression tests for task-clustered paired bootstrap resampling."""

import importlib.util
import random
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "hj1_gate",
    Path(__file__).resolve().parents[2] / "scripts" / "setup" / "hj1_gate.py",
)
gate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gate)


def _arms(diffs_by_task):
    base = {}
    other = {}
    for task, diffs in diffs_by_task.items():
        for seed, diff in enumerate(diffs):
            base[(task, seed)] = {"tgc": diff}
            other[(task, seed)] = {"tgc": 0.0}
    return base, other


def test_zero_within_task_correlation_has_similar_intervals():
    rng = random.Random(17)
    base, other = _arms(
        {
            f"task_{task}": [rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)]
            for task in range(300)
        }
    )
    pair = gate.paired_diff(base, other, "tgc", resample="pair")
    task = gate.paired_diff(base, other, "tgc", resample="task")

    assert abs(pair["ci95_pp"][0] - task["ci95_pp"][0]) < 2.0
    assert abs(pair["ci95_pp"][1] - task["ci95_pp"][1]) < 2.0


def test_strong_within_task_correlation_widens_task_interval():
    rng = random.Random(23)
    base, other = _arms(
        {f"task_{task}": [rng.uniform(-1.0, 1.0)] * 2 for task in range(120)}
    )
    pair = gate.paired_diff(base, other, "tgc", resample="pair")
    task = gate.paired_diff(base, other, "tgc", resample="task")

    pair_width = pair["ci95_pp"][1] - pair["ci95_pp"][0]
    task_width = task["ci95_pp"][1] - task["ci95_pp"][0]
    assert task_width > pair_width * 1.25


def test_task_draw_carries_all_seeds_and_pairing_together():
    by_task = {"task_a": [("task_a", 1), ("task_a", 2)], "task_b": [("task_b", 1)]}
    draw_rng = random.Random(101)
    selected = [sorted(by_task)[draw_rng.randrange(len(by_task))] for _ in by_task]
    expected = [value for task in selected for value in by_task[task]]
    assert gate._draw_task_clusters(by_task, random.Random(101)) == expected


def test_pairing_is_built_from_the_same_task_seed_key():
    base = {
        ("task_a", 1): {"tgc": 0.91},
        ("task_a", 2): {"tgc": 0.82},
        ("task_b", 1): {"tgc": 0.73},
    }
    other = {
        ("task_a", 1): {"tgc": 0.11},
        ("task_a", 2): {"tgc": 0.22},
        ("task_b", 1): {"tgc": 0.33},
    }

    result = gate.paired_diff(base, other, "tgc", resample="task")

    assert result["diff_pp"] == pytest.approx((80 + 60 + 40) / 3)


def test_unequal_seed_coverage_drops_unmatched_keys():
    base = {
        ("task_a", 1): {"tgc": 1.0},
        ("task_a", 2): {"tgc": 1.0},
        ("task_b", 1): {"tgc": 0.5},
    }
    other = {
        ("task_a", 1): {"tgc": 0.0},
        ("task_b", 1): {"tgc": 0.0},
        ("task_b", 2): {"tgc": 0.0},
    }
    result = gate.paired_diff(base, other, "tgc")

    assert result["n_pairs"] == 2
    assert result["n_tasks"] == 2
    assert result["resample"] == "task"
    assert result["n_clusters"] == 2
    assert result["mean_cluster_size"] == 1.0
    assert result["dropped_unmatched_keys"] == {"base": 1, "other": 1, "total": 2}
    assert result["dropped_from_base"] == 1
    assert result["dropped_from_other"] == 1


def test_seeded_task_bootstrap_reproduces_interval():
    base, other = _arms({f"task_{task}": [task / 100, task / 100] for task in range(20)})

    first = gate.paired_diff(base, other, "tgc")
    second = gate.paired_diff(base, other, "tgc")

    assert first["ci95_pp"] == second["ci95_pp"]
    assert first["diff_pp"] == second["diff_pp"]


@pytest.mark.parametrize("bad_unit", ["seed", "cluster", ""])
def test_unknown_resampling_unit_is_rejected(bad_unit):
    base, other = _arms({"task_a": [1.0]})
    with pytest.raises(ValueError, match="unknown resampling unit"):
        gate.paired_diff(base, other, "tgc", resample=bad_unit)
