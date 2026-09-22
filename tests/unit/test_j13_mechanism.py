"""Unit tests for threshold mechanism analysis (Brief X33b)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]

_SPEC = importlib.util.spec_from_file_location(
    "j13_mechanism", REPO / "scripts" / "analysis" / "j13_mechanism.py"
)
mech = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(mech)

from sidekick.protocols.schemas import Event


def _make_event(
    step: int,
    actor: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
    error_type: str | None = None,
    task_id: str = "task_01",
    seed: int = 1,
) -> Event:
    return Event(
        run_id="run_test",
        task_id=task_id,
        system="test_system",
        seed=seed,
        step=step,
        ts="2026-09-15T00:00:00Z",
        actor=actor,  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        payload=payload or {},
        error_type=error_type,
    )


def test_load_source_planner_prefers_result_json_over_directory_names(tmp_path: Path) -> None:
    """1. load_source_planner returns result.json fields when directory names disagree."""
    d = tmp_path / "wrong_seed_dir" / "wrong_task_dir"
    d.mkdir(parents=True)
    res_file = d / "result.json"
    res_file.write_text(
        json.dumps({"task_id": "true_task_abc", "seed": 42}),
        encoding="utf-8",
    )
    events_file = d / "events.jsonl"
    events_file.write_text("", encoding="utf-8")

    records = mech.load_source_planner(tmp_path)
    assert ("true_task_abc", 42) in records
    assert ("wrong_task_dir", 0) not in records
    assert ("wrong_task_dir", "wrong_seed_dir") not in records
    rec = records[("true_task_abc", 42)]
    assert rec["task_id"] == "true_task_abc"
    assert rec["seed"] == 42


def test_m1_api_novelty_cumulative_shares() -> None:
    """2. M1 on 3-episode synthetic source with known first-use positions returns expected cumulative table."""
    # Ep 1: pos 1 = gmail.search (novel), pos 2 = gmail.send (novel), pos 3 = gmail.search (repeat)
    ep1_events = [
        _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.gmail.search(query='foo')"}),
        _make_event(2, "planner", "action", {"kind": "CODE", "code": "apis.gmail.send(to='bar')"}),
        _make_event(3, "planner", "action", {"kind": "CODE", "code": "apis.gmail.search(query='baz')"}),
    ]
    # Ep 2: pos 1 = contacts.find (novel), pos 2 = contacts.find (repeat)
    ep2_events = [
        _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.contacts.find(name='alice')"}),
        _make_event(2, "planner", "action", {"kind": "CODE", "code": "apis.contacts.find(name='bob')"}),
    ]
    # Ep 3: pos 1 = notes.create (novel), pos 2 = notes.list (novel), pos 3 = notes.update (novel)
    ep3_events = [
        _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.notes.create(title='t')"}),
        _make_event(2, "planner", "action", {"kind": "CODE", "code": "apis.notes.list()"}),
        _make_event(3, "planner", "action", {"kind": "CODE", "code": "apis.notes.update(id=1)"}),
    ]

    source_records = {
        ("t1", 1): {"events": ep1_events, "result": {}, "task_id": "t1", "seed": 1},
        ("t2", 1): {"events": ep2_events, "result": {}, "task_id": "t2", "seed": 1},
        ("t3", 1): {"events": ep3_events, "result": {}, "task_id": "t3", "seed": 1},
    }

    m1_res = mech.measure_m1_api_novelty(source_records)
    # Total novel first uses = 3 (pos1) + 2 (pos2) + 1 (pos3) = 6
    assert m1_res["total_first_uses"] == 6
    cum = m1_res["cumulative_by_position"]
    assert cum[1]["first_uses_at_pos"] == 3
    assert cum[1]["cum_first_uses"] == 3
    assert cum[1]["cum_first_uses_share"] == round(3 / 6, 4)

    assert cum[2]["first_uses_at_pos"] == 2
    assert cum[2]["cum_first_uses"] == 5
    assert cum[2]["cum_first_uses_share"] == round(5 / 6, 4)

    assert cum[3]["first_uses_at_pos"] == 1
    assert cum[3]["cum_first_uses"] == 6
    assert cum[3]["cum_first_uses_share"] == 1.0


def test_m2_compounding_error_and_handoff_occurred_filter() -> None:
    """3. M2 on synthetic arm with executor error at step 2 reports step 2; handoff_occurred: False is silenced."""
    # Ep A: handoff_occurred=True, executor error at action 2
    ep_a_events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.gmail.read()"}),
        _make_event(1, "executor", "observation", {"text": "ok"}),
        _make_event(2, "executor", "action", {"kind": "CODE", "code": "apis.gmail.send()"}),
        _make_event(2, "executor", "observation", {"text": "Execution failed"}, error_type="ExecutionError"),
    ]
    rec_a = {
        "events": ep_a_events,
        "result": {
            "handoff_occurred": True,
            "goal_pass_rate": 0.0,
            "totals": {"per_actor": {"executor": {"n_calls": 2}}},
        },
        "task_id": "tA",
        "seed": 1,
    }

    # Ep B: handoff_occurred=False (silenced / prefix-exhausted)
    rec_b = {
        "events": [],
        "result": {
            "handoff_occurred": False,
            "goal_pass_rate": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 0}}},
        },
        "task_id": "tB",
        "seed": 1,
    }

    # Ep C: handoff_occurred=True, no errors
    ep_c_events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.notes.list()"}),
        _make_event(1, "executor", "observation", {"text": "ok"}),
    ]
    rec_c = {
        "events": ep_c_events,
        "result": {
            "handoff_occurred": True,
            "goal_pass_rate": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 1}}},
        },
        "task_id": "tC",
        "seed": 1,
    }

    arm_records = {"m4": {("tA", 1): rec_a, ("tB", 1): rec_b, ("tC", 1): rec_c}}
    m2_res = mech.measure_m2_compounding_error(arm_records, [4])

    m4 = m2_res["m4"]
    assert m4["n_episodes"] == 3
    assert m4["silenced_episodes"] == 1
    assert m4["handoff_episodes"] == 2
    assert m4["error_episodes"] == 1
    assert m4["first_error_rel_step_dist"]["min"] == 2


def test_m3_handoff_population_and_divergence_diagnostic() -> None:
    """4. M3 handoff-only equals handoff_occurred set; divergence counted when n_calls==0 and handoff_occurred==True."""
    # Ep 1: handoff_occurred: True, n_calls: 3 -> handoff
    rec1 = {
        "events": [_make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"})],
        "result": {"handoff_occurred": True, "goal_pass_rate": 1.0, "tgc": 1.0, "totals": {"per_actor": {"executor": {"n_calls": 3}}}},
        "task_id": "t1",
        "seed": 1,
    }
    # Ep 2: handoff_occurred: False, n_calls: 0 -> silenced
    rec2 = {
        "events": [_make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"})],
        "result": {"handoff_occurred": False, "goal_pass_rate": 1.0, "tgc": 1.0, "totals": {"per_actor": {"executor": {"n_calls": 0}}}},
        "task_id": "t2",
        "seed": 1,
    }
    # Ep 3: handoff_occurred: True, n_calls: 0 -> divergence!
    rec3 = {
        "events": [_make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"})],
        "result": {"handoff_occurred": True, "goal_pass_rate": 0.0, "tgc": 0.0, "totals": {"per_actor": {"executor": {"n_calls": 0}}}},
        "task_id": "t3",
        "seed": 1,
    }

    arm_records = {"m4": {("t1", 1): rec1, ("t2", 1): rec2, ("t3", 1): rec3}}
    source_records = {
        ("t1", 1): {"events": ep_actions(5), "task_id": "t1", "seed": 1},
        ("t2", 1): {"events": ep_actions(3), "task_id": "t2", "seed": 1},
        ("t3", 1): {"events": ep_actions(5), "task_id": "t3", "seed": 1},
    }

    m3_res = mech.measure_m3_prefix_exhausted(arm_records, source_records, [4])
    curve = m3_res["all_episodes_curve"]["m4"]
    assert curve["n"] == 3
    assert curve["handoff_count"] == 2
    assert curve["silenced_count"] == 1
    assert curve["divergence_count"] == 1
    assert curve["divergence_keys"] == [["t3", 1]]


def ep_actions(count: int) -> list[Event]:
    return [
        _make_event(i + 1, "planner", "action", {"kind": "CODE", "code": f"apis.app.action_{i}()"})
        for i in range(count)
    ]


def test_arm_discovery_requires_exact_114_results(tmp_path: Path) -> None:
    """5. Arm discovery includes only campaigns with exactly 114 result files and reports excluded ones."""
    # Create m=2 with 114 results
    d2 = tmp_path / "hj12_prefix_m2_20260923" / "prefix_handoff"
    for i in range(114):
        f = d2 / f"task_{i}" / "result.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}", encoding="utf-8")

    # Create m=4 with 6 results (incomplete)
    d4 = tmp_path / "hj12_prefix_m4_20260923" / "prefix_handoff"
    for i in range(6):
        f = d4 / f"task_{i}" / "result.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}", encoding="utf-8")

    # Create m=6 with 113 results (incomplete)
    d6 = tmp_path / "hj12_prefix_m6_20260923" / "prefix_handoff"
    for i in range(113):
        f = d6 / f"task_{i}" / "result.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}", encoding="utf-8")

    included_m, arm_paths, excluded = mech.discover_arms(
        tmp_path, receiver="tailored", m_range=[2, 4, 6]
    )
    assert included_m["primary"] == [2]
    assert "m2" in arm_paths["primary"]

    excl_m_primary = [e["m"] for e in excluded if e["group"] == "primary"]
    assert 4 in excl_m_primary
    assert 6 in excl_m_primary

    excl_dict = {e["m"]: e["result_count"] for e in excluded if e["group"] == "primary"}
    assert excl_dict[4] == 6
    assert excl_dict[6] == 113


def test_validate_output_path_refuses_forbidden_locations() -> None:
    """6. Output paths under results dir or containing test splits are refused before writing."""
    with pytest.raises(ValueError, match="forbidden"):
        mech.validate_output_path(Path("/scratch/n12194778/sidekick/results/report.json"))

    with pytest.raises(ValueError, match="forbidden"):
        mech.validate_output_path(Path("/scratch/n12194778/sidekick/results/sub/report.json"))

    with pytest.raises(ValueError, match="forbidden"):
        mech.validate_output_path(Path("campaign/results/test_normal_report.json"))

    with pytest.raises(ValueError, match="forbidden"):
        mech.validate_output_path(Path("campaign/results/test_challenge_report.json"))

    # Valid paths do not raise
    mech.validate_output_path(Path("campaign/results/hj13_mechanism.report.json"))
    mech.validate_output_path(None)


def test_bootstrap_is_deterministic_under_default_seed() -> None:
    """7. Bootstrap is deterministic under default seed (two runs give identical CIs)."""
    base: dict[tuple[str, int], float] = {}
    other: dict[tuple[str, int], float] = {}

    for i in range(20):
        t = f"task_{i:02d}_1"
        for s in (1, 2):
            base[(t, s)] = 0.50 + 0.01 * i
            other[(t, s)] = 0.55 + 0.01 * i

    run1_task = mech.paired_diff_task(base, other, n_boot=200, seed=mech.SEED)
    run2_task = mech.paired_diff_task(base, other, n_boot=200, seed=mech.SEED)
    assert run1_task == run2_task
    assert run1_task["ci95_pp"] is not None

    run1_scen = mech.paired_diff_scenario(base, other, n_boot=200, seed=mech.SEED)
    run2_scen = mech.paired_diff_scenario(base, other, n_boot=200, seed=mech.SEED)
    assert run1_scen == run2_scen
    assert run1_scen["ci95_pp"] is not None


def test_markdown_renders_none_as_na() -> None:
    """8. generate_markdown_report handles None values in M2 and elsewhere as 'n/a' without raising."""
    report = {
        "generated_by": "scripts/analysis/j13_mechanism.py",
        "receiver": "tailored",
        "arms_used": {
            "primary": {"m2": "/path/to/m2"},
            "comparison": {},
            "source_planner": "/path/to/source",
            "excluded_arms": [],
        },
        "m1_api_novelty": {
            "total_first_uses": None,
            "n_episodes": 0,
            "mean_first_uses_per_episode": None,
            "first_use_position_distribution": None,
            "binned": {
                "1-2": {
                    "first_uses": 0,
                    "total_actions": 0,
                    "share_of_all_first_uses": None,
                    "novel_share_in_bin": None,
                }
            },
        },
        "m2_compounding_error": {
            "primary": {
                "m2": {
                    "handoff_episodes": 0,
                    "silenced_episodes": 0,
                    "divergence_count": 0,
                    "error_rate_on_handoff": None,
                    "share_first_error_at_step_1": None,
                    "share_first_error_in_steps_1_2": None,
                }
            },
            "comparison": {},
        },
        "m3_prefix_exhausted": {
            "primary": {
                "decompositions": {
                    "m2_to_m10": {
                        "delta_total_pp": None,
                        "y_base_all": None,
                        "y_target_all": None,
                        "contribution_silenced_subset_pp": None,
                        "share_of_rise_from_silenced_pct": None,
                        "weight_silenced": None,
                        "contribution_handoff_subset_pp": None,
                        "share_of_rise_from_handoff_pct": None,
                        "weight_handoff": None,
                        "arithmetic_identity_check_pp": None,
                    }
                }
            },
            "comparison": {},
        },
    }

    out = mech.generate_markdown_report(report)
    assert isinstance(out, str)
    assert "n/a" in out

