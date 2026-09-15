"""Split-leakage guard tests. Measured split sizes: train 90, dev 57,
test_normal 168, test_challenge 417 [OBSERVED brief U5]."""

from __future__ import annotations

import glob
import json

import pytest

from sidekick.training import assert_no_leakage

MEASURED_SPLITS = {
    "train": 90,
    "dev": 57,
    "test_normal": 168,
    "test_challenge": 417,
}


def test_clean_split_passes():
    train = [f"t{i}" for i in range(MEASURED_SPLITS["train"])]
    heldout = [f"h{i}" for i in range(MEASURED_SPLITS["test_normal"])]
    assert_no_leakage(train, heldout)


def test_single_overlap_raises():
    with pytest.raises(ValueError, match="h7"):
        assert_no_leakage(["t1", "t2", "h7"], ["h7", "h8"])


def test_empty_inputs_pass():
    assert_no_leakage([], [])
    assert_no_leakage(["t1"], [])


def test_manifests_have_no_leakage():
    manifests = sorted(glob.glob("artifacts/adapters/*/manifest.json"))
    if not manifests:
        pytest.skip("no adapter manifests yet")
    for path in manifests:
        with open(path) as f:
            manifest = json.load(f)
        train_ids = manifest.get("train_task_ids", [])
        heldout_ids = manifest.get("heldout_task_ids", [])
        assert_no_leakage(train_ids, heldout_ids)
