"""The WTP control's task permutation: scripts/setup/make_wrongtask_map.py and the committed map.

The rule is a minimum-total-cost assignment on |plan-length gap|, with a task's own plan and its
own scenario forbidden. The solver and the builder are tested on hand-checked inputs; the
committed configs/dev_wrongtask_plan_map.json is tested for being a permutation, a derangement and
scenario-distinct, for its recorded length-match metadata, for being deterministic, and for a
median gap below the cyclic-shift rule it replaced (573.5 chars). The cases that re-read the dev
packet source are skipped where /scratch is not mounted.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "setup"))
import make_wrongtask_map as mwm  # noqa: E402
from hj1_gate import scenario_of  # noqa: E402

from sidekick.agents.packet_remap import RemappedPacketPlanner  # noqa: E402
from sidekick.runner import load_config, make_planner  # noqa: E402

MAP_PATH = REPO / "configs" / "dev_wrongtask_plan_map.json"
WTP_CONFIG = REPO / "configs" / "dev_sft_plan_wrongtask_bplus.yaml"
HJ1B = Path("/scratch/n12194778/sidekick/results/hj1b_planner_20260915")
needs_hj1b = pytest.mark.skipif(not (HJ1B / "planner_alone").is_dir(), reason="dev packet source not mounted")


def _doc() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


# --- the builder, on hand-built inputs ----------------------------------------------------------


CYCLIC_RULE_MEDIAN_GAP = 573.5  # the k = 16 cyclic shift this rule replaced


def test_the_solver_on_a_hand_checked_4x4():
    cost = [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]]
    # By hand, over all 24 permutations: rows -> columns (1, 0, 2, 3) cost 2 + 6 + 1 + 4 = 13, the
    # unique minimum (next best 14: (1, 2, 0, 3)).
    assert mwm.min_cost_assignment(cost) == [1, 0, 2, 3]
    totals = sorted(sum(cost[i][p[i]] for i in range(4)) for p in itertools.permutations(range(4)))
    assert totals[:2] == [13, 14]


def test_the_solver_takes_square_integer_matrices_only():
    assert mwm.min_cost_assignment([]) == []
    for bad in ([[1, 2]], [[1.5, 2], [3, 4]]):
        with pytest.raises(ValueError, match="square matrix of ints"):
            mwm.min_cost_assignment(bad)


def test_equal_lengths_pair_up_as_swaps():
    doc = mwm.build_wrongtask_map({"a_1": 10, "b_1": 10, "c_1": 20, "d_1": 20})
    # By hand: the only zero-cost derangement swaps a with b and c with d.
    assert doc["map"] == {"a_1": "b_1", "b_1": "a_1", "c_1": "d_1", "d_1": "c_1"}
    assert doc["plan_chars"] == {"a_1": 10.0, "b_1": 10.0, "c_1": 20.0, "d_1": 20.0}
    meta = doc["metadata"]
    assert meta["rule"] == "min_cost_length_assignment"
    assert (meta["total_cost_chars"], meta["median_abs_gap_chars"], meta["max_abs_gap_chars"]) == (0.0, 0.0, 0.0)
    assert (meta["min_length_ratio"], meta["max_length_ratio"], meta["n_two_cycles"]) == (1.0, 1.0, 2)


def test_the_own_scenario_is_forbidden_and_ties_go_to_the_sorted_sources():
    chars = {"s1_1": 10, "s1_2": 11, "s2_1": 20, "s2_2": 21}
    doc = mwm.build_wrongtask_map(chars)
    # By hand: the cheapest pairs (s1_1/s1_2 and s2_1/s2_2, gap 1) share a scenario, so s1 tasks
    # take s2 plans and back. Both ways cost 20 on each side (10 + 10 or 11 + 9), total 40; the
    # tie goes to the source sequence smallest in sorted task_id order: s2_1, s2_2, s1_1, s1_2.
    assert doc["map"] == {"s1_1": "s2_1", "s1_2": "s2_2", "s2_1": "s1_1", "s2_2": "s1_2"}
    meta = doc["metadata"]
    assert (meta["total_cost_chars"], meta["median_abs_gap_chars"], meta["max_abs_gap_chars"]) == (40.0, 10.0, 10.0)
    assert (meta["min_length_ratio"], meta["max_length_ratio"]) == (0.5, 2.0)
    # Deterministic, whatever order the lengths arrive in.
    assert mwm.build_wrongtask_map(dict(reversed(list(chars.items())))) == doc


def test_half_character_lengths_are_costed_exactly():
    doc = mwm.build_wrongtask_map({"a_1": 10.5, "b_1": 10.0, "c_1": 30.0})
    # By hand: the two 3-cycles cost 0.5 + 20 + 19.5 = 40 either way; the tie goes to a -> b.
    assert doc["map"] == {"a_1": "b_1", "b_1": "c_1", "c_1": "a_1"}
    assert doc["metadata"]["total_cost_chars"] == 40.0


def test_one_scenario_has_no_valid_assignment():
    with pytest.raises(ValueError, match="no assignment"):
        mwm.build_wrongtask_map({"a_1": 1, "a_2": 2, "a_3": 3})


def _events(path: Path, packets: list[dict]) -> None:
    """One attempt per packet, each a run_start then a plan event (a retried run appends)."""
    lines = []
    for packet in packets:
        lines.append({"event_type": "run_start", "payload": {}})
        lines.append({"event_type": "plan", "actor": "planner", "payload": {"packet": packet}})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


def _packet(goal: str) -> dict:
    return {"packet_id": "p", "task_id": "t", "goal": goal, "created_at": "c"}


def test_plan_text_is_the_rendered_packet_of_the_last_attempt(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    _events(path, [_packet("first attempt, discarded"), _packet("g")])
    # By hand: DelegationPacket.model_dump_json() of the LAST attempt's packet, defaults filled in.
    rendered = ('{"packet_id":"p","task_id":"t","goal":"g","plan_steps":[],"constraints":[],'
                '"success_criteria":[],"forbidden_actions":[],"context_digest":"","created_at":"c"}')
    assert mwm.plan_text_chars(path) == len(rendered) == 157


def test_plan_chars_are_the_mean_over_seeds(tmp_path: Path):
    _events(tmp_path / "planner_alone" / "1" / "x_1" / "events.jsonl", [_packet("g")])
    _events(tmp_path / "planner_alone" / "2" / "x_1" / "events.jsonl", [_packet("gggg")])
    # By hand: 157 and 160 characters (three more in the goal), mean 158.5.
    assert mwm.plan_chars_by_task(tmp_path, "planner_alone", ["x_1"], [1, 2]) == {"x_1": 158.5}
    with pytest.raises(FileNotFoundError, match="seed 3"):
        mwm.plan_chars_by_task(tmp_path, "planner_alone", ["x_1"], [1, 3])


def test_a_non_dev_split_is_refused_before_anything_is_read(tmp_path: Path, monkeypatch):
    import sidekick.runner as runner

    def _no_read(*a, **kw):
        raise AssertionError("task ids were read for a non-dev split")

    monkeypatch.setattr(runner, "appworld_task_ids", _no_read)
    out = tmp_path / "map.json"
    for split in ("test_normal", "test_challenge", "train"):
        assert mwm.main(["--split", split, "--out", str(out)]) == 2
    assert not out.exists()


# --- the committed map --------------------------------------------------------------------------


def test_the_map_has_its_three_fields_over_57_tasks():
    doc = _doc()
    assert set(doc) == {"map", "plan_chars", "metadata"}
    assert len(doc["map"]) == 57 and set(doc["map"]) == set(doc["plan_chars"])
    assert doc["metadata"]["rule"] == "min_cost_length_assignment"


def test_the_map_is_a_permutation_and_a_derangement():
    m = _doc()["map"]
    assert sorted(m.values()) == sorted(m)
    assert all(t != s for t, s in m.items())


def test_no_task_gets_a_plan_from_its_own_scenario():
    m = _doc()["map"]
    assert all(scenario_of(t) != scenario_of(s) for t, s in m.items())


def test_the_recorded_length_match_is_the_maps_own():
    doc = _doc()
    m, chars, meta = doc["map"], doc["plan_chars"], doc["metadata"]
    gaps = sorted(abs(chars[s] - chars[t]) for t, s in m.items())
    ratios = [chars[s] / chars[t] for t, s in m.items()]
    assert meta["n_tasks"] == 57
    assert meta["total_cost_chars"] == sum(abs(chars[s] - chars[t]) for t, s in m.items())
    assert meta["median_abs_gap_chars"] == gaps[28] and meta["max_abs_gap_chars"] == gaps[-1]
    assert (meta["min_length_ratio"], meta["max_length_ratio"]) == (min(ratios), max(ratios))
    assert meta["median_abs_gap_chars"] < CYCLIC_RULE_MEDIAN_GAP


def test_no_swap_of_two_sources_lowers_the_total_gap():
    # A check independent of the solver: at the optimum, exchanging the sources of any two tasks
    # either breaks a constraint or does not reduce the total gap.
    m, chars = _doc()["map"], _doc()["plan_chars"]

    def ok(t: str, s: str) -> bool:
        return t != s and scenario_of(t) != scenario_of(s)

    for a, b in itertools.combinations(sorted(m), 2):
        sa, sb = m[a], m[b]
        if ok(a, sb) and ok(b, sa):
            before = abs(chars[sa] - chars[a]) + abs(chars[sb] - chars[b])
            after = abs(chars[sb] - chars[a]) + abs(chars[sa] - chars[b])
            assert after >= before, (a, b)


def test_rebuilding_from_the_recorded_lengths_reproduces_the_map():
    doc = _doc()
    assert mwm.build_wrongtask_map(doc["plan_chars"]) == doc
    assert mwm.build_wrongtask_map(dict(reversed(list(doc["plan_chars"].items())))) == doc


@needs_hj1b
def test_the_recorded_lengths_are_the_archives():
    doc = _doc()
    tasks = sorted(doc["map"])
    for seed in (1, 2):
        assert sorted(p.name for p in (HJ1B / "planner_alone" / str(seed)).iterdir()) == tasks
    assert mwm.plan_chars_by_task(HJ1B, "planner_alone", tasks, [1, 2]) == doc["plan_chars"]


@needs_hj1b
def test_the_wtp_config_builds_a_remap_with_exactly_this_map():
    planner = make_planner(load_config(str(WTP_CONFIG)), seed=1)
    assert isinstance(planner, RemappedPacketPlanner)
    assert planner.task_map == _doc()["map"]
    assert planner.cached.packet_source == HJ1B and planner.cached.on_missing == "fail"
