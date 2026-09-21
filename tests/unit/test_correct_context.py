"""Advise-path context window (X10). MockEnv only; stub planners; no network."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.runner import load_config, system_kwargs
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits, SystemPolicy
from sidekick.trajectories.eventlog import EventLog

READ = '```python\nprint(read("inbox.txt"))\n```'
WRITE = '```python\nwrite("outbox.txt", "hello world")\n```'
COMPLETE = "COMPLETE"
ASK = "ASK_PLANNER: which file?"

_TAKEOVER_SYSTEMS = (
    "fixed_k",
    "sidekick",
    "router_seq",
    "oracle_escalation",
    "action_review",
    "planner_handoff",
)
_OTHER_SYSTEMS = (
    "planner_alone",
    "executor_alone",
    "prompt_only",
    "sft_plan",
    "prefix_handoff",
)

ROOT = Path(__file__).resolve().parents[2]


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


@dataclass
class _RecordingPlanner(MockPlanner):
    deltas: list[str] = field(default_factory=list)

    def correct(self, packet, transcript_delta, timeout_s=None):
        self.deltas.append(transcript_delta)
        return super().correct(packet, transcript_delta, timeout_s=timeout_s)


def _run(tmp_path: Path, *, name: str, planner, executor, run_id: str, **system_kw):
    log = EventLog(tmp_path, run_id)
    system = get_system(
        name,
        planner=planner,
        executor=executor,
        limits=RunLimits(),
        **system_kw,
    )
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, _ledger())
    finally:
        log.close()
    return result, planner


def _nine_reads_then(*tail: str) -> list[str]:
    return [READ] * 9 + list(tail)


def test_default_forced_review_sends_last_eight_lines(tmp_path: Path):
    planner = _RecordingPlanner()
    result, planner = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=_nine_reads_then(WRITE, COMPLETE)),
        run_id="ctx_default8",
        k=10,
    )
    assert result.error_type is None
    assert planner.deltas, "forced-review advise path must call correct()"
    delta = planner.deltas[0]
    assert "INSTRUCTION:" not in delta
    assert delta.count("OBS:") == 8


def test_full_context_forced_review_sends_whole_transcript(tmp_path: Path):
    planner = _RecordingPlanner()
    result, planner = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=_nine_reads_then(WRITE, COMPLETE)),
        run_id="ctx_full",
        k=10,
        correct_context_lines=None,
    )
    assert result.error_type is None
    assert planner.deltas
    delta = planner.deltas[0]
    assert delta.startswith("INSTRUCTION:")
    assert "PLAN:" in delta
    assert delta.count("OBS:") >= 9


def test_ask_path_ignores_correct_context_lines(tmp_path: Path):
    planner = _RecordingPlanner()
    result, planner = _run(
        tmp_path,
        name="fixed_k",
        planner=planner,
        executor=MockExecutor(script=_nine_reads_then(ASK, WRITE, COMPLETE)),
        run_id="ctx_ask",
        k=100,
        correct_context_lines=None,
    )
    assert result.n_asks == 1
    assert planner.deltas
    delta = planner.deltas[0]
    assert delta.endswith("ASK: which file?")
    assert "INSTRUCTION:" not in delta
    assert delta.count("OBS:") == 8


def test_unrecognised_correct_context_raises():
    with pytest.raises(ValueError, match="unrecognised correct_context"):
        system_kwargs("fixed_k", {"correct_context": "last8"}, "t")
    with pytest.raises(ValueError, match="unrecognised correct_context"):
        system_kwargs("fixed_k", {"correct_context": True}, "t")
    with pytest.raises(ValueError, match="unrecognised correct_context"):
        system_kwargs("router_seq", {"correct_context": -1}, "t")


def test_system_kwargs_forwards_correct_context_with_takeover_systems():
    for name in _TAKEOVER_SYSTEMS:
        assert system_kwargs(name, {"correct_context": "full"}, "t")["correct_context_lines"] is None
        assert system_kwargs(name, {"correct_context": "all"}, "t")["correct_context_lines"] is None
        assert system_kwargs(name, {"correct_context": 12}, "t")["correct_context_lines"] == 12
        assert "correct_context_lines" not in system_kwargs(name, {}, "t")
    for name in _OTHER_SYSTEMS:
        assert "correct_context_lines" not in system_kwargs(
            name, {"correct_context": "full"}, "t"
        )


def test_none_overlay_survives_configurable_system_default():
    planner = MockPlanner()
    system = get_system(
        "fixed_k",
        planner=planner,
        executor=MockExecutor(),
        correct_context_lines=None,
    )
    assert system.policy.correct_context_lines is None
    defaulted = get_system("fixed_k", planner=planner, executor=MockExecutor())
    assert defaulted.policy.correct_context_lines == 8
    assert SystemPolicy().correct_context_lines == 8


def test_hj12_fullctx_differs_from_takeover_only_in_channel():
    takeover = load_config(str(ROOT / "configs/hj12_takeover_fixed_k_10.yaml"))
    advise = load_config(str(ROOT / "configs/hj12_advise_fixed_k_10_fullctx.yaml"))
    assert advise["campaign_id"] == "hj12_advise_fixed_k_10_fullctx_20260923"
    assert advise["correct_context"] == "full"
    assert "takeover" not in advise
    assert takeover["takeover"] is True
    drop = {"campaign_id", "takeover", "correct_context"}
    assert {k: v for k, v in takeover.items() if k not in drop} == {
        k: v for k, v in advise.items() if k not in drop
    }
