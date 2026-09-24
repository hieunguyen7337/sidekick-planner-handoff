"""Helpers of the BFCL spike scripts (bfcl-env E1). Vendored data only; no model."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sidekick.environments.bfcl_env import BfclEnv, BfclWorld, load_entries, state_hash

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / "analysis" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


spike_a = _load("bfcl_spike_a")
spike_c = _load("bfcl_spike_c")
E0 = "multi_turn_base_0"


def test_share_above_fixtures() -> None:
    assert spike_c.share_above([3, 5, 7], 4) == 2 / 3
    assert spike_c.share_above([3, 5, 7], 7) == 0.0
    assert spike_c.share_above([3, 5, 7], 0) == 1.0


def test_propose_grid_fixtures() -> None:
    # Seven trajectories of 10 and three of 2: share is 1.0 below m=2, 0.7 for m=2..9, 0 from 10.
    assert spike_c.propose_grid([10] * 7 + [2] * 3) == (9, [3, 6, 9])
    # Nothing is longer than 1: only m=0 clears the gate.
    assert spike_c.propose_grid([1, 1, 1]) == (0, [0, 1])


def test_hash_sequence_entry_0() -> None:
    seq = spike_a.hash_sequence(E0)
    assert len(seq) == 15  # reset + 10 CODE + 4 COMPLETE
    assert seq[0] == BfclEnv().reset(E0, 1).env_state_hash
    assert seq == spike_a.hash_sequence(E0)


def test_upstream_ground_truth_matches_the_adapter_on_entry_0() -> None:
    entry = load_entries()[E0]
    results, up_hash = spike_a.upstream_ground_truth(entry)
    world = BfclWorld(entry)
    assert results == [world.run_all(turn) for turn in entry["ground_truth"]]
    assert up_hash == state_hash(world.instances)


def test_upstream_checker_on_entry_0() -> None:
    entry = load_entries()[E0]
    assert spike_a.upstream_checker(entry, [[[c] for c in t] for t in entry["ground_truth"]]) == {
        "valid": True,
        "error_type": None,
    }
    assert spike_a.upstream_checker(entry, [[], [], [], []]) == {
        "valid": False,
        "error_type": "multi_turn:empty_turn_model_response",
    }
    from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils

    assert [k for k in vars(multi_turn_utils) if k.startswith("spikea")] == []
