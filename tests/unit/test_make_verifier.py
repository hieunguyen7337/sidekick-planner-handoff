"""A4 / U-V1: make_verifier must return a Verifier with .score, not a ThresholdRouter."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.executor import ASK_TEMPLATE, MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.agents.verifier import (
    ConstantVerifier,
    FeatureVerifier,
    ScriptedVerifier,
    SelfVerifier,
    ThresholdRouter,
    feature_spec,
)
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.runner import make_verifier, system_kwargs
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits, SystemPolicy
from sidekick.trajectories.eventlog import EventLog

WRITE = '```python\nwrite("outbox.txt", "hello world")\n```'
ASK = ASK_TEMPLATE

REALISTIC_KEYS = (
    "step",
    "transcript",
    "last_action",
    "last_observation",
    "n_asks",
    "n_interventions",
    "p_ask",
)


def realistic_state(**over) -> dict:
    """Match loop.trajectory_state keys (loop.py:515-524)."""
    state = {
        "step": 3,
        "transcript": "INSTRUCTION: copy inbox to outbox\nPLAN: write outbox.txt",
        "last_action": {"kind": "CODE", "code": 'write("outbox.txt", "hello world")'},
        "last_observation": {"text": "ok", "step": 2, "done": False},
        "n_asks": 0,
        "n_interventions": 1,
        "p_ask": 0.4,
    }
    state.update(over)
    return state


def save_tiny_feature_lr(tmp_path: Path) -> Path:
    cols = feature_spec()["columns"]
    weights = {c: 0.0 for c in cols}
    weights["token_leak"] = 5.0
    path = tmp_path / "feature_lr.json"
    FeatureVerifier(weights=weights).save(path)
    return path


def _assert_callable_float_score(verifier, state: dict) -> float:
    assert set(state) == set(REALISTIC_KEYS)
    score_fn = getattr(verifier, "score", None)
    assert callable(score_fn)
    value = verifier.score(state)
    assert type(value) is float
    return value


def test_make_verifier_feature_lr_has_score(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    v = make_verifier({"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.7}})
    assert isinstance(v, FeatureVerifier)
    assert not isinstance(v, ThresholdRouter)
    value = _assert_callable_float_score(v, realistic_state())
    assert 0.0 <= value <= 1.0


def test_make_verifier_self_p_ask_has_score():
    v = make_verifier({"verifier": {"kind": "self_p_ask", "threshold": 0.3}})
    assert isinstance(v, SelfVerifier)
    assert _assert_callable_float_score(v, realistic_state(p_ask=0.4)) == 0.4


def test_make_verifier_scores_has_score():
    v = make_verifier({"verifier": {"scores": [0.2, 0.9]}})
    assert isinstance(v, ScriptedVerifier)
    assert _assert_callable_float_score(v, realistic_state()) == 0.2


def test_make_verifier_default_has_score():
    v = make_verifier({"verifier": {"value": 0.25}})
    assert isinstance(v, ConstantVerifier)
    assert _assert_callable_float_score(v, realistic_state()) == 0.25


def test_make_verifier_feature_lr_router_seq_wrap(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    cfg = {"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.5}}
    v = make_verifier(cfg)
    kw = system_kwargs("router_seq", cfg, "copy_hello")
    policy = SystemPolicy(use_router=True, verifier_threshold=kw["verifier_threshold"])
    # loop.py:247-249
    router = None
    if policy.use_router:
        router = ThresholdRouter(v or ConstantVerifier(), policy.verifier_threshold)
    decided = router.should_escalate(realistic_state())
    assert type(decided) is bool


def test_make_verifier_feature_lr_sidekick_ask_gate(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    cfg = {"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.5}}
    v = make_verifier(cfg)
    kw = system_kwargs("sidekick", cfg, "copy_hello")
    policy = SystemPolicy(
        allow_executor_ask=True,
        gate_ask_with_verifier=True,
        verifier_threshold=kw["verifier_threshold"],
    )
    allow = True
    # loop.py:784-788
    if allow and policy.gate_ask_with_verifier:
        scored = v or ConstantVerifier()
        if not (scored.score(realistic_state()) > policy.verifier_threshold):
            allow = False
    assert type(allow) is bool
    assert type(v.score(realistic_state()) > policy.verifier_threshold) is bool


def test_verifier_threshold_reaches_system_kwargs_unchanged(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    cfg = {"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.73}}
    make_verifier(cfg)
    assert system_kwargs("sidekick", cfg, "t")["verifier_threshold"] == 0.73
    assert system_kwargs("router_seq", cfg, "t")["verifier_threshold"] == 0.73


def test_router_seq_episode_with_make_verifier_feature_lr(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    v = make_verifier({"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.5}})
    log = EventLog(tmp_path, "a4_router")
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        "router_seq",
        planner=MockPlanner(),
        executor=MockExecutor(script=[WRITE, "COMPLETE"]),
        verifier=v,
        limits=RunLimits(),
        verifier_threshold=0.5,
    )
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()
    assert result.error_type != "crash"
    assert result.success is True


def test_sidekick_episode_with_make_verifier_feature_lr(tmp_path: Path):
    path = save_tiny_feature_lr(tmp_path)
    v = make_verifier({"verifier": {"kind": "feature_lr", "path": str(path), "threshold": 0.5}})
    log = EventLog(tmp_path, "a4_sidekick")
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        "sidekick",
        planner=MockPlanner(),
        executor=MockExecutor(script=[ASK, WRITE, "COMPLETE"]),
        verifier=v,
        limits=RunLimits(),
        verifier_threshold=0.5,
    )
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, ledger)
    finally:
        log.close()
    assert result.error_type != "crash"
    assert result.success is True
