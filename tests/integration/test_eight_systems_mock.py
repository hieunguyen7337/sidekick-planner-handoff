from __future__ import annotations

from sidekick.replay import replay
from sidekick.systems import SYSTEM_NAMES
from sidekick.trajectories.eventlog import EventLog


def test_all_eight_systems_complete_on_mock(run_system) -> None:
    assert SYSTEM_NAMES == (
        "planner_alone",
        "executor_alone",
        "prompt_only",
        "fixed_k",
        "sft_plan",
        "router_seq",
        "sidekick",
        "oracle_escalation",
        "action_review",
        "prefix_handoff",
    )
    for name in SYSTEM_NAMES:
        extra = {}
        if name == "oracle_escalation":
            extra["oracle_steps"] = [1]
        if name == "fixed_k":
            extra["k"] = 5
        result, events_file, ledger, _planner, executor = run_system(
            name, run_id=f"e2e/{name}/1/copy_hello", **extra
        )
        assert events_file.is_file(), name
        events = list(EventLog.read(events_file))
        types = [e.event_type for e in events]
        assert types[0] == "run_start", name
        assert "evaluate" in types, name
        assert types[-1] == "run_end", name
        assert result.success is True, (name, result.error_type, result.model_dump())
        assert result.error_type is None, name
        assert result.system == name
        assert result.totals["planner_tokens_total"] >= 0
        assert "usd_total" in result.totals
        assert result.totals == ledger.totals()
        if name == "planner_alone":
            assert result.n_planner_calls >= 3
        if name == "sft_plan":
            assert executor.last_lora_name == "sft_plan"
        if name == "oracle_escalation":
            assert result.n_interventions >= 1
            assert any(e.event_type == "intervention" for e in events)


def test_replay_matches_mock_hashes(run_system) -> None:
    result, events_file, _ledger, _p, _e = run_system("prompt_only", run_id="replay_prompt")
    assert result.success is True
    report = replay(events_file)
    assert report.ok, report.mismatches
    assert report.n_compared >= 2


def test_replay_matches_planner_alone(run_system) -> None:
    result, events_file, *_ = run_system("planner_alone", run_id="replay_planner")
    assert result.success is True
    report = replay(events_file)
    assert report.ok, report.mismatches
