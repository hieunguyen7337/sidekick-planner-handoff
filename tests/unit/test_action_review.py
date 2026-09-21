"""E4: rule_trigger verifier and action_review system (mock planner only)."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.agents.verifier import (
    ConstantVerifier,
    EXCEPTION_MARKER,
    RuleTriggerVerifier,
    ScriptedVerifier,
)
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import PlannerResponse, Usage
from sidekick.runner import load_config, make_verifier, system_kwargs
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

REPO = Path(__file__).resolve().parents[2]
WRITE = '```python\nwrite("outbox.txt", "hello world")\n```'
DELETE = '```python\nfiles.delete_all()\n```'
COMPLETE = "COMPLETE"


def _usage(**kw) -> Usage:
    base = dict(model="mock-planner", provider="mock", input_tokens=10, output_tokens=8)
    base.update(kw)
    return Usage(**base)


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


def _run(tmp_path: Path, *, planner, executor, verifier, run_id: str, adapter_name: str | None = "sft_plan"):
    log = EventLog(tmp_path, run_id)
    ledger = _ledger()
    system = get_system(
        "action_review",
        planner=planner,
        executor=executor,
        verifier=verifier,
        limits=RunLimits(),
        adapter_name=adapter_name,
    )
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return result, events, ledger


def test_rule_trigger_fires_on_exception_marker_not_clean():
    v = RuleTriggerVerifier()
    dirty = {"last_observation": {"text": f"{EXCEPTION_MARKER}\nboom"}}
    clean = {"last_observation": {"text": "ok"}}
    assert v.score(dirty) == 1.0
    assert v.score(clean) == 0.0
    traceback_only = {"last_observation": {"text": "Traceback (most recent call last): nope"}}
    assert v.score(traceback_only) == 0.0


def test_on_irreversible_fires_on_matching_proposed_action():
    v = RuleTriggerVerifier(rules=["on_irreversible"])
    hit = {"proposed_action": {"kind": "CODE", "code": "apis.gmail.send_email(to='x')"}}
    miss = {"proposed_action": {"kind": "CODE", "code": "print(apis.spotify.show_library())"}}
    assert v.score(hit) == 1.0
    assert v.score(miss) == 0.0


def test_rules_toggle_independently_default_is_on_exception():
    default = RuleTriggerVerifier()
    assert default.rules == ["on_exception"]
    irreversible_only_state = {
        "last_observation": {"text": "ok"},
        "proposed_action": {"code": "x.delete_thing()"},
    }
    exception_state = {
        "last_observation": {"text": f"{EXCEPTION_MARKER} x"},
        "proposed_action": {"code": "print(1)"},
    }
    assert default.score(irreversible_only_state) == 0.0
    assert default.score(exception_state) == 1.0

    irr = RuleTriggerVerifier(rules=["on_irreversible"])
    assert irr.score(exception_state) == 0.0
    assert irr.score(irreversible_only_state) == 1.0

    both = RuleTriggerVerifier(rules=["on_exception", "on_irreversible"])
    assert both.score(exception_state) == 1.0
    assert both.score(irreversible_only_state) == 1.0
    assert both.score({"last_observation": {"text": "ok"}, "proposed_action": {"code": "print(1)"}}) == 0.0

    none = RuleTriggerVerifier(rules=[])
    assert none.score(exception_state) == 0.0
    assert none.score(irreversible_only_state) == 0.0


def test_unknown_verifier_kind_falls_through_to_constant():
    v = make_verifier({"verifier": {"kind": "not_a_real_kind", "value": 0.25}})
    assert isinstance(v, ConstantVerifier)
    assert v.score({"step": 1}) == 0.25


def test_make_verifier_rule_trigger_from_config():
    absent_rules = make_verifier({"verifier": {"kind": "rule_trigger"}})
    assert isinstance(absent_rules, RuleTriggerVerifier)
    assert absent_rules.rules == ["on_exception"]
    both = make_verifier(
        {
            "verifier": {
                "kind": "rule_trigger",
                "rules": ["on_exception", "on_irreversible"],
                "irreversible_patterns": [r"\.send_"],
            }
        }
    )
    assert isinstance(both, RuleTriggerVerifier)
    assert both.rules == ["on_exception", "on_irreversible"]
    assert both.score({"proposed_action": {"code": "api.send_mail()"}}) == 1.0


def test_hj11_configs_build_rule_trigger():
    exc = load_config(str(REPO / "configs/hj11_action_review_exception.yaml"))
    v1 = make_verifier(exc)
    assert isinstance(v1, RuleTriggerVerifier)
    assert v1.rules == ["on_exception"]
    both = load_config(str(REPO / "configs/hj11_action_review_exception_irreversible.yaml"))
    v2 = make_verifier(both)
    assert isinstance(v2, RuleTriggerVerifier)
    assert v2.rules == ["on_exception", "on_irreversible"]
    kw = system_kwargs("action_review", exc, "t")
    assert kw["adapter_name"] == "sft_b_plus"


def test_approval_executes_proposal(tmp_path: Path):
    # Gate fires once; MockPlanner.correct has no code → approve.
    result, events, _ledger = _run(
        tmp_path,
        planner=MockPlanner(),
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        verifier=ScriptedVerifier([1.0, 0.0]),
        run_id="ar_approve",
    )
    reviews = [e for e in events if e.event_type == "action_review"]
    assert len(reviews) == 1
    assert reviews[0].payload["verdict"] == "approve"
    assert reviews[0].payload["replacement"] is None
    assert 'write("outbox.txt", "hello world")' in (reviews[0].payload["proposed"].get("code") or "")
    assert result.success is True
    assert result.error_type is None
    evals = [e for e in events if e.event_type == "evaluate"]
    assert evals[-1].payload["report"]["outbox"] == "hello world"
    assert evals[-1].payload["report"]["deleted"] is False


def test_replacement_executes_replacement_not_proposal(tmp_path: Path):
    planner = MockPlanner(
        scripts={
            ("copy_hello", "act"): [
                PlannerResponse(
                    kind="ACTION",
                    code='write("outbox.txt", "hello world")',
                    raw_output='```python\nwrite("outbox.txt", "hello world")\n```',
                    usage=_usage(),
                )
            ]
        }
    )
    result, events, _ledger = _run(
        tmp_path,
        planner=planner,
        executor=MockExecutor(script=[DELETE, COMPLETE]),
        verifier=RuleTriggerVerifier(rules=["on_irreversible"]),
        run_id="ar_replace",
    )
    reviews = [e for e in events if e.event_type == "action_review"]
    assert len(reviews) == 1
    assert reviews[0].payload["verdict"] == "replace"
    assert reviews[0].payload["proposed"]["code"] == "files.delete_all()"
    assert reviews[0].payload["replacement"]["code"] == 'write("outbox.txt", "hello world")'
    assert result.success is True
    assert result.error_type is None
    evals = [e for e in events if e.event_type == "evaluate"]
    assert evals[-1].payload["report"]["outbox"] == "hello world"
    assert evals[-1].payload["report"]["deleted"] is False
    obs_texts = [e.payload.get("text") or "" for e in events if e.event_type == "observation"]
    assert not any("deleted all files" in t for t in obs_texts)


def test_review_stub_mirrors_real_planner_prose_correct_fenced_act(tmp_path: Path):
    """correct() returns prose with code=None; act() returns a fenced action.

    A stub that is more capable than the hosted planner (correct() setting code)
    is how the always-approve defect survived.
    """
    planner = MockPlanner(
        scripts={
            ("copy_hello", "correct"): [
                PlannerResponse(
                    kind="CORRECTION",
                    correction="do not delete; write outbox instead",
                    code=None,
                    raw_output="do not delete; write outbox instead",
                    usage=_usage(),
                )
            ],
            ("copy_hello", "act"): [
                PlannerResponse(
                    kind="ACTION",
                    code='write("outbox.txt", "hello world")',
                    raw_output='```python\nwrite("outbox.txt", "hello world")\n```',
                    usage=_usage(),
                )
            ],
        }
    )
    result, events, _ledger = _run(
        tmp_path,
        planner=planner,
        executor=MockExecutor(script=[DELETE, COMPLETE]),
        verifier=RuleTriggerVerifier(rules=["on_irreversible"]),
        run_id="ar_real_stub",
    )
    reviews = [e for e in events if e.event_type == "action_review"]
    assert len(reviews) == 1
    assert reviews[0].payload["verdict"] == "replace"
    assert reviews[0].payload["replacement"]["code"] == 'write("outbox.txt", "hello world")'
    assert result.success is True
    assert result.error_type is None
    evals = [e for e in events if e.event_type == "evaluate"]
    assert evals[-1].payload["report"]["outbox"] == "hello world"
    assert evals[-1].payload["report"]["deleted"] is False


def test_review_increments_planner_call_count_by_exactly_one(tmp_path: Path):
    no_gate = _run(
        tmp_path,
        planner=MockPlanner(),
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        verifier=ConstantVerifier(0.0),
        run_id="ar_calls_off",
    )
    one_gate = _run(
        tmp_path,
        planner=MockPlanner(),
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        verifier=ScriptedVerifier([1.0, 0.0]),
        run_id="ar_calls_on",
    )
    result_off, events_off, ledger_off = no_gate
    result_on, events_on, ledger_on = one_gate
    assert result_off.n_planner_calls == 1  # plan only
    assert result_on.n_planner_calls == result_off.n_planner_calls + 1
    assert ledger_on.totals()["planner_calls_total"] == ledger_off.totals()["planner_calls_total"] + 1
    assert sum(1 for e in events_on if e.event_type == "action_review") == 1
    assert sum(1 for e in events_off if e.event_type == "action_review") == 0
    start = next(e for e in events_on if e.event_type == "run_start")
    assert start.payload["policy"]["review_proposed_action"] is True
    start_off = next(e for e in events_off if e.event_type == "run_start")
    assert start_off.payload["policy"]["review_proposed_action"] is True
    sft, events_sft, _ = _run_sft(tmp_path)
    sft_start = next(e for e in events_sft if e.event_type == "run_start")
    assert "review_proposed_action" not in sft_start.payload["policy"]


def _run_sft(tmp_path: Path):
    log = EventLog(tmp_path, "sft_policy_shape")
    ledger = _ledger()
    system = get_system(
        "sft_plan",
        planner=MockPlanner(),
        executor=MockExecutor(script=[WRITE, COMPLETE]),
        verifier=ConstantVerifier(0.5),
        limits=RunLimits(),
    )
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / "sft_policy_shape" / "events.jsonl"))
    return result, events, ledger
