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
        _make_event(1, "environment", "observation", {"text": "ok"}),
        _make_event(2, "executor", "action", {"kind": "CODE", "code": "apis.gmail.send()"}),
        _make_event(2, "environment", "observation", {"text": "Execution failed"}, error_type="ExecutionError"),
        _make_event(3, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec_a = {
        "events": ep_a_events,
        "result": {
            "goal_pass_rate": 0.0,
            "totals": {"per_actor": {"executor": {"n_calls": 2}}},
        },
        "task_id": "tA",
        "seed": 1,
    }

    # Ep B: handoff_occurred=False (silenced / prefix-exhausted)
    ep_b_events = [
        _make_event(1, "system", "report", {"handoff_occurred": False, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec_b = {
        "events": ep_b_events,
        "result": {
            "goal_pass_rate": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 0}}},
        },
        "task_id": "tB",
        "seed": 1,
    }

    # Ep C: handoff_occurred=True, no errors
    ep_c_events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.notes.list()"}),
        _make_event(1, "environment", "observation", {"text": "ok"}),
        _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec_c = {
        "events": ep_c_events,
        "result": {
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


def test_m2_counts_errors_from_environment_observations() -> None:
    """Scripted handoff episode with executor action followed by observation|environment starting 'Execution failed. Traceback:' yields error_rate_on_handoff == 1.0 and first_error_rel_step == 1."""
    events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.gmail.send()"}),
        _make_event(1, "environment", "observation", {"text": "Execution failed. Traceback: KeyError: 'id'"}),
        _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec = {
        "events": events,
        "result": {
            "goal_pass_rate": 0.0,
            "totals": {"per_actor": {"executor": {"n_calls": 1}}},
        },
        "task_id": "t1",
        "seed": 1,
    }
    arm_records = {"m4": {("t1", 1): rec}}
    res = mech.measure_m2_compounding_error(arm_records, [4])
    m4 = res["m4"]
    assert m4["handoff_episodes"] == 1
    assert m4["error_episodes"] == 1
    assert m4["error_rate_on_handoff"] == 1.0
    assert m4["first_error_rel_step_dist"]["min"] == 1


def test_m2_ignores_successful_observations() -> None:
    """Scripted handoff episode with text 'Execution successful.' yields no error."""
    events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.gmail.send()"}),
        _make_event(1, "environment", "observation", {"text": "Execution successful. Result: 200"}),
        _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec = {
        "events": events,
        "result": {
            "goal_pass_rate": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 1}}},
        },
        "task_id": "t1",
        "seed": 1,
    }
    arm_records = {"m4": {("t1", 1): rec}}
    res = mech.measure_m2_compounding_error(arm_records, [4])
    m4 = res["m4"]
    assert m4["handoff_episodes"] == 1
    assert m4["error_episodes"] == 0
    assert m4["error_rate_on_handoff"] == 0.0
    assert m4["first_error_rel_step_dist"] is None


def test_m2_first_error_step_is_one_based_on_executor_actions() -> None:
    """Error in reply to 3rd executor action yields first_error_rel_step == 3."""
    events = [
        _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.a()"}),
        _make_event(1, "environment", "observation", {"text": "Execution successful."}),
        _make_event(2, "executor", "action", {"kind": "CODE", "code": "apis.b()"}),
        _make_event(2, "environment", "observation", {"text": "Execution successful."}),
        _make_event(3, "executor", "action", {"kind": "CODE", "code": "apis.c()"}),
        _make_event(3, "environment", "observation", {"text": "Execution failed. Traceback: ..."}, error_type="ExecutionError"),
        _make_event(4, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
    ]
    rec = {
        "events": events,
        "result": {
            "goal_pass_rate": 0.0,
            "totals": {"per_actor": {"executor": {"n_calls": 3}}},
        },
        "task_id": "t1",
        "seed": 1,
    }
    arm_records = {"m4": {("t1", 1): rec}}
    res = mech.measure_m2_compounding_error(arm_records, [4])
    m4 = res["m4"]
    assert m4["handoff_episodes"] == 1
    assert m4["error_episodes"] == 1
    assert m4["first_error_rel_step_dist"]["min"] == 3
    assert m4["share_first_error_at_step_1"] == 0.0
    assert m4["share_first_error_in_steps_1_2"] == 0.0


def test_m3_handoff_population_and_divergence_diagnostic() -> None:
    """4. M3 handoff-only equals handoff_occurred set; divergence counted when n_calls==0 and handoff_occurred==True."""
    # Ep 1: handoff_occurred: True, n_calls: 3 -> handoff
    rec1 = {
        "events": [
            _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"}),
            _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
        ],
        "result": {"goal_pass_rate": 1.0, "tgc": 1.0, "totals": {"per_actor": {"executor": {"n_calls": 3}}}},
        "task_id": "t1",
        "seed": 1,
    }
    # Ep 2: handoff_occurred: False, n_calls: 0 -> silenced
    rec2 = {
        "events": [
            _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"}),
            _make_event(2, "system", "report", {"handoff_occurred": False, "effective_m": 4, "n_source_actions": 5}),
        ],
        "result": {"goal_pass_rate": 1.0, "tgc": 1.0, "totals": {"per_actor": {"executor": {"n_calls": 0}}}},
        "task_id": "t2",
        "seed": 1,
    }
    # Ep 3: handoff_occurred: True, n_calls: 0 -> divergence!
    rec3 = {
        "events": [
            _make_event(1, "planner", "action", {"kind": "CODE", "code": "apis.a.b()"}),
            _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
        ],
        "result": {"goal_pass_rate": 0.0, "tgc": 0.0, "totals": {"per_actor": {"executor": {"n_calls": 0}}}},
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


def test_handoff_flag_is_read_from_report_event(tmp_path: Path) -> None:
    """Handoff flag is read from report event in events.jsonl, not result.json."""
    ep_dir = tmp_path / "hj12_prefix_m9_20260923" / "prefix_handoff" / "1" / "task_01"
    ep_dir.mkdir(parents=True)
    res_file = ep_dir / "result.json"
    res_file.write_text(
        json.dumps({
            "task_id": "task_01",
            "seed": 1,
            "goal_pass_rate": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 2}}},
        }),
        encoding="utf-8",
    )
    events_file = ep_dir / "events.jsonl"
    events_content = (
        json.dumps({
            "run_id": "r1", "task_id": "task_01", "system": "test", "seed": 1,
            "step": 0, "ts": "2026-09-15T00:00:00Z", "actor": "system",
            "event_type": "run_start", "payload": {},
        }) + "\n" +
        json.dumps({
            "run_id": "r1", "task_id": "task_01", "system": "test", "seed": 1,
            "step": 1, "ts": "2026-09-15T00:00:00Z", "actor": "system",
            "event_type": "report", "payload": {
                "handoff_occurred": True,
                "effective_m": 9,
                "n_source_actions": 10,
                "replayed_planner_tokens": 318026,
            },
        }) + "\n"
    )
    events_file.write_text(events_content, encoding="utf-8")

    arm_root = tmp_path / "hj12_prefix_m9_20260923" / "prefix_handoff"
    flags = mech.load_handoff_flags(arm_root)
    assert ("task_01", 1) in flags
    assert flags[("task_01", 1)]["handoff_occurred"] is True
    assert flags[("task_01", 1)]["effective_m"] == 9
    assert flags[("task_01", 1)]["n_source_actions"] == 10

    records = mech.load_episode_records(arm_root)
    assert records[("task_01", 1)]["handoff_occurred"] is True

    m2_res = mech.measure_m2_compounding_error({"m9": records}, [9])
    assert m2_res["m9"]["handoff_episodes"] == 1
    assert m2_res["m9"]["silenced_episodes"] == 0


def test_empty_handoff_population_is_fatal(tmp_path: Path) -> None:
    """Fixture arm where every result.json lacks the key and no report event exists raises SystemExit."""
    ep_dir = tmp_path / "hj12_prefix_m9_20260923" / "prefix_handoff" / "1" / "task_01"
    ep_dir.mkdir(parents=True)
    res_file = ep_dir / "result.json"
    res_file.write_text(
        json.dumps({
            "task_id": "task_01",
            "seed": 1,
            "goal_pass_rate": 0.0,
            "totals": {"per_actor": {"executor": {"n_calls": 2}}},
        }),
        encoding="utf-8",
    )
    # No report event in events.jsonl
    events_file = ep_dir / "events.jsonl"
    events_file.write_text(
        json.dumps({
            "run_id": "r1", "task_id": "task_01", "system": "test", "seed": 1,
            "step": 0, "ts": "2026-09-15T00:00:00Z", "actor": "system",
            "event_type": "run_start", "payload": {},
        }) + "\n",
        encoding="utf-8",
    )

    arm_root = tmp_path / "hj12_prefix_m9_20260923" / "prefix_handoff"
    with pytest.raises(SystemExit, match="missing a report event"):
        mech.load_episode_records(arm_root)


def test_handoff_true_with_zero_executor_calls_is_fatal(tmp_path: Path) -> None:
    """handoff_occurred is True but executor n_calls == 0 is fatal (SystemExit)."""
    records = {
        ("task_01", 1): {
            "events": [
                _make_event(1, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
            ],
            "result": {
                "task_id": "task_01",
                "seed": 1,
                "totals": {"per_actor": {"executor": {"n_calls": 0}}},
            },
            "task_id": "task_01",
            "seed": 1,
        }
    }
    with pytest.raises(SystemExit, match="with handoff_occurred is True but executor n_calls == 0"):
        mech.validate_arm_population(records, arm_name="m4")


def test_post_complete_actions_are_recorded_not_fatal() -> None:
    """Arm where 10% of episodes have handoff_occurred False and n_calls > 0 completes and reports post_complete_executor_actions."""
    records = {}
    # 9 episodes: handoff_occurred=True, n_calls=2 (handoff)
    for i in range(9):
        records[(f"task_{i}", 1)] = {
            "events": [
                _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.a()"}),
                _make_event(1, "environment", "observation", {"text": "Execution successful."}),
                _make_event(2, "system", "report", {"handoff_occurred": True, "effective_m": 4, "n_source_actions": 5}),
            ],
            "result": {
                "task_id": f"task_{i}",
                "seed": 1,
                "goal_pass_rate": 1.0,
                "tgc": 1.0,
                "totals": {"per_actor": {"executor": {"n_calls": 2}}},
            },
            "task_id": f"task_{i}",
            "seed": 1,
        }
    # 1 episode (1/10 = 10%): handoff_occurred=False, n_calls=2 (post-complete executor action)
    records[("task_post_complete", 1)] = {
        "events": [
            _make_event(1, "executor", "action", {"kind": "CODE", "code": "apis.a()"}),
            _make_event(1, "environment", "observation", {"text": "Execution successful."}),
            _make_event(2, "system", "report", {"handoff_occurred": False, "effective_m": 4, "n_source_actions": 5}),
        ],
        "result": {
            "task_id": "task_post_complete",
            "seed": 1,
            "goal_pass_rate": 1.0,
            "tgc": 1.0,
            "totals": {"per_actor": {"executor": {"n_calls": 2}}},
        },
        "task_id": "task_post_complete",
        "seed": 1,
    }

    # Should not raise SystemExit
    mech.validate_arm_population(records, arm_name="m4")

    # Check measure_m2_compounding_error reports post_complete_executor_actions == 1
    m2_res = mech.measure_m2_compounding_error({"m4": records}, [4])
    assert m2_res["m4"]["post_complete_executor_actions"] == 1
    assert m2_res["m4"]["divergence_count"] == 1
    assert m2_res["m4"]["silenced_episodes"] == 1
    assert m2_res["m4"]["handoff_episodes"] == 9

    # Check measure_m3_prefix_exhausted reports post_complete_executor_actions == 1
    source_records = {k: {"events": ep_actions(5), "task_id": k[0], "seed": k[1]} for k in records}
    m3_res = mech.measure_m3_prefix_exhausted({"m4": records}, source_records, [4])
    assert m3_res["all_episodes_curve"]["m4"]["post_complete_executor_actions"] == 1
    assert m3_res["all_episodes_curve"]["m4"]["divergence_count"] == 1


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
                    "post_complete_executor_actions": 0,
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


def _make_arm_record(
    task_id: str,
    seed: int,
    gpr: float,
    handoff: bool,
    m: int = 6,
    n_source_actions: int = 15,
) -> dict[str, Any]:
    events = [
        _make_event(1, "executor" if handoff else "planner", "action", {"kind": "CODE", "code": "apis.a.b()"}),
        _make_event(2, "system", "report", {"handoff_occurred": handoff, "effective_m": m, "n_source_actions": n_source_actions}),
    ]
    return {
        "events": events,
        "result": {
            "task_id": task_id,
            "seed": seed,
            "goal_pass_rate": gpr,
            "tgc": gpr,
            "totals": {"per_actor": {"executor": {"n_calls": 1 if handoff else 0}}},
        },
        "task_id": task_id,
        "seed": seed,
        "handoff_occurred": handoff,
        "effective_m": m,
        "n_source_actions": n_source_actions,
        "has_report": True,
    }


def test_decompose_pairs_emits_exactly_the_requested_pairs() -> None:
    """Parse 'm6:m9,m6:m11' against scripted arm set containing m6, m9, m11; assert decomposition keys are {'m6_to_m9', 'm6_to_m11'}."""
    arm_records = {
        "m6": {
            ("t1", 1): _make_arm_record("t1", 1, 0.2, True, 6),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 6),
        },
        "m9": {
            ("t1", 1): _make_arm_record("t1", 1, 0.4, True, 9),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 9),
        },
        "m11": {
            ("t1", 1): _make_arm_record("t1", 1, 0.6, True, 11),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 11),
        },
    }
    source_records = {
        ("t1", 1): {"events": ep_actions(15), "task_id": "t1", "seed": 1},
        ("t2", 1): {"events": ep_actions(5), "task_id": "t2", "seed": 1},
    }
    m3_res = mech.measure_m3_prefix_exhausted(
        arm_records, source_records, [6, 9, 11], decompose_pairs="m6:m9,m6:m11", receiver="zeroshot"
    )
    assert set(m3_res["decompositions"].keys()) == {"m6_to_m9", "m6_to_m11"}
    assert "m6_to_m9" in m3_res["decompositions"]
    assert "m6_to_m11" in m3_res["decompositions"]
    assert m3_res["decompositions"]["m6_to_m9"]["m_base"] == 6
    assert m3_res["decompositions"]["m6_to_m9"]["m_target"] == 9
    assert m3_res["decompositions"]["m6_to_m11"]["m_base"] == 6
    assert m3_res["decompositions"]["m6_to_m11"]["m_target"] == 11


def test_decompose_pairs_missing_depth_is_fatal() -> None:
    """Requesting 'm6:m9' against an arm set with only m6 and m11 raises SystemExit naming 9."""
    arm_records = {
        "m6": {
            ("t1", 1): _make_arm_record("t1", 1, 0.2, True, 6),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 6),
        },
        "m11": {
            ("t1", 1): _make_arm_record("t1", 1, 0.6, True, 11),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 11),
        },
    }
    source_records = {
        ("t1", 1): {"events": ep_actions(15), "task_id": "t1", "seed": 1},
        ("t2", 1): {"events": ep_actions(5), "task_id": "t2", "seed": 1},
    }
    with pytest.raises(SystemExit, match="9"):
        mech.measure_m3_prefix_exhausted(
            arm_records, source_records, [6, 11], decompose_pairs="m6:m9", receiver="zeroshot"
        )


def test_decompose_pairs_default_is_unchanged() -> None:
    """Omitting the option reproduces the current key set on a scripted grid."""
    arm_records = {
        "m2": {
            ("t1", 1): _make_arm_record("t1", 1, 0.2, True, 2),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 2),
        },
        "m10": {
            ("t1", 1): _make_arm_record("t1", 1, 0.4, True, 10),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 10),
        },
        "m11": {
            ("t1", 1): _make_arm_record("t1", 1, 0.6, True, 11),
            ("t2", 1): _make_arm_record("t2", 1, 0.5, False, 11),
        },
    }
    source_records = {
        ("t1", 1): {"events": ep_actions(15), "task_id": "t1", "seed": 1},
        ("t2", 1): {"events": ep_actions(5), "task_id": "t2", "seed": 1},
    }
    m3_res = mech.measure_m3_prefix_exhausted(
        arm_records, source_records, [2, 10, 11], decompose_pairs=None, receiver="tailored"
    )
    assert set(m3_res["decompositions"].keys()) == {"m2_to_m10", "m2_to_m11"}


