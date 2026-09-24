"""The WTP control's replay remap (src/sidekick/agents/packet_remap.py) and its plan-event field.

Offline: archives are tiny events.jsonl files under tmp_path in the replay layout
<packet_source>/<system>/<seed>/<task_id>/events.jsonl, and the episode runs on MockEnv.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidekick.agents.executor import MockExecutor
from sidekick.agents.packet_remap import (
    PACKET_TASK_SOURCE_KEY,
    PacketTaskMapError,
    RemappedPacketPlanner,
    apply_packet_task_map,
    load_packet_task_map,
    plan_event_fields,
    resolve_map_path,
    validate_packet_task_map,
)
from sidekick.agents.planner import CachedPacketPlanner, MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import DelegationPacket, PlannerResponse, Usage
from sidekick.runner import make_planner
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

REPO = Path(__file__).resolve().parents[2]


def _packet(task_id: str) -> dict:
    return {
        "packet_id": f"pkt-{task_id}",
        "task_id": task_id,
        "goal": f"goal of {task_id}",
        "plan_steps": [{"index": 1, "description": f"step for {task_id}", "expected_outcome": "x", "apps": []}],
        "constraints": [],
        "success_criteria": [],
        "forbidden_actions": [],
        "context_digest": "abc",
        "created_at": "2026-09-15T00:00:00+00:00",
    }


def _write_archive(root: Path, task_id: str, seed: int = 1) -> Path:
    usage = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 10, "output_tokens": 2, "n_calls": 1,
             "raw": {"model": "gpt-5.6-luna"}}
    lines = [
        {"run_id": "r", "task_id": task_id, "system": "planner_alone", "seed": seed, "step": 0, "ts": "t",
         "actor": "system", "event_type": "run_start", "payload": {}, "usage": None, "error_type": None},
        {"run_id": "r", "task_id": task_id, "system": "planner_alone", "seed": seed, "step": 0, "ts": "t",
         "actor": "planner", "event_type": "plan", "payload": {"packet": _packet(task_id), "model": "gpt-5.6-luna"},
         "usage": usage, "error_type": None},
    ]
    path = root / "planner_alone" / str(seed) / task_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


class _NoLiveInner(MockPlanner):
    """The hosted planner behind the replay: any plan() here would be a live, right-task plan."""

    def plan(self, *a, **kw):
        raise AssertionError("the remap fell through to a live plan")


def _source(tmp_path: Path, tasks=("a_1", "b_1", "c_1")) -> Path:
    root = tmp_path / "src"
    for t in tasks:
        _write_archive(root, t)
    return root


def _remapped(tmp_path: Path, task_map: dict[str, str], **cached_kw) -> RemappedPacketPlanner:
    cached = CachedPacketPlanner(_NoLiveInner(), _source(tmp_path), system="planner_alone", seed=1, **cached_kw)
    return RemappedPacketPlanner(cached, task_map)


# --- the map ------------------------------------------------------------------------------------


def test_validate_accepts_a_derangement_and_returns_a_plain_dict():
    assert validate_packet_task_map({"a_1": "b_1", "b_1": "a_1"}) == {"a_1": "b_1", "b_1": "a_1"}


@pytest.mark.parametrize(
    "bad, why",
    [
        ({}, "empty"),
        ({"a_1": "b_1", "b_1": "b_1"}, "not a permutation"),  # b_1 used twice, a_1 never
        ({"a_1": "a_1", "b_1": "c_1", "c_1": "b_1"}, "own plan"),  # a fixed point
        ({"a_1": "z_9"}, "not a permutation"),  # a source outside the task set
    ],
)
def test_validate_refuses_a_map_that_would_replay_a_right_or_shared_plan(bad, why):
    with pytest.raises(ValueError, match=why):
        validate_packet_task_map(bad)


def test_load_reads_the_map_field_of_the_builder_json(tmp_path: Path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"map": {"a_1": "b_1", "b_1": "a_1"}, "plan_chars": {"a_1": 1.0, "b_1": 2.0},
                                "metadata": {"rule": "min_cost_length_assignment"}}), encoding="utf-8")
    assert load_packet_task_map(path) == {"a_1": "b_1", "b_1": "a_1"}
    path.write_text(json.dumps({"a_1": "b_1"}), encoding="utf-8")
    with pytest.raises(ValueError, match="'map'"):
        load_packet_task_map(path)


def test_a_relative_map_path_resolves_against_the_repo():
    assert resolve_map_path("configs/x.json") == REPO / "configs" / "x.json"
    assert resolve_map_path("/abs/x.json") == Path("/abs/x.json")


# --- the remap ----------------------------------------------------------------------------------


def test_plan_replays_the_mapped_tasks_packet_and_records_its_source(tmp_path: Path):
    planner = _remapped(tmp_path, {"a_1": "b_1", "b_1": "c_1", "c_1": "a_1"})
    resp = planner.plan("a_1", "goal of a_1", "api docs of a_1")
    # By hand: a_1 -> b_1, so the packet is b_1's, byte-for-byte, and nothing was bought.
    assert resp.packet == DelegationPacket.model_validate(_packet("b_1"))
    assert resp.usage.provider == "cache" and resp.usage.n_calls == 0
    assert resp.usage.raw[PACKET_TASK_SOURCE_KEY] == "b_1"
    assert resp.usage.raw["cached_from"].endswith("planner_alone/1/b_1/events.jsonl")


def test_a_task_missing_from_the_map_is_a_hard_error_not_a_live_plan(tmp_path: Path):
    planner = _remapped(tmp_path, {"a_1": "b_1", "b_1": "a_1"})
    with pytest.raises(PacketTaskMapError, match="c_1"):
        planner.plan("c_1", "g", "ctx")
    # Not a FileNotFoundError, so no on_missing mode of the replay layer can turn it into a plan.
    assert not issubclass(PacketTaskMapError, FileNotFoundError)


def test_a_mapped_source_with_no_archive_still_aborts(tmp_path: Path):
    planner = _remapped(tmp_path, {"a_1": "d_1", "d_1": "a_1"})
    with pytest.raises(FileNotFoundError, match="d_1"):
        planner.plan("a_1", "g", "ctx")


@pytest.mark.parametrize(
    "cached_kw",
    [{"on_missing": "call"}, {"on_missing": "call_if_planless"}, {"live_plan_keys": ["1/a_1"]}],
)
def test_the_remap_refuses_every_mode_that_can_plan_live(tmp_path: Path, cached_kw):
    with pytest.raises(ValueError, match="on_missing: fail"):
        _remapped(tmp_path, {"a_1": "b_1", "b_1": "a_1"}, **cached_kw)


def test_correct_act_and_close_are_the_replays(tmp_path: Path):
    calls: list[str] = []

    class Inner(_NoLiveInner):
        def correct(self, packet, transcript_delta, timeout_s=None):
            calls.append("correct")
            return PlannerResponse(kind="CORRECTION", packet=packet, correction="ok",
                                   usage=Usage(model="gpt-5.6-luna", provider="codex"))

        def close(self):
            calls.append("close")

    cached = CachedPacketPlanner(Inner(), _source(tmp_path), system="planner_alone", seed=1)
    planner = RemappedPacketPlanner(cached, {"a_1": "b_1", "b_1": "a_1"})
    resp = planner.plan("a_1", "g", "CTX-A")
    planner.correct(resp.packet, "delta")
    planner.close()
    assert calls == ["correct", "close"]
    assert (planner.system, planner.seed) == ("planner_alone", 1)


# --- make_planner ------------------------------------------------------------------------------


def _cfg(source: Path, **planner_extra) -> dict:
    return {"planner": {"type": "codex", "packet_source": str(source), "packet_system": "planner_alone",
                        "on_missing": "fail", **planner_extra}}


def test_make_planner_wraps_the_replay_only_when_the_key_is_set(tmp_path: Path):
    source = _source(tmp_path)
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"map": {"a_1": "c_1", "b_1": "a_1", "c_1": "b_1"}}), encoding="utf-8")
    assert type(make_planner(_cfg(source), seed=1)) is CachedPacketPlanner
    planner = make_planner(_cfg(source, packet_task_map=str(map_path)), seed=1)
    assert isinstance(planner, RemappedPacketPlanner)
    assert planner.plan("a_1", "g", "ctx").packet.task_id == "c_1"


def test_a_map_without_a_packet_source_is_refused():
    with pytest.raises(ValueError, match="packet_source"):
        make_planner({"planner": {"type": "mock", "packet_task_map": "configs/dev_wrongtask_plan_map.json"}})
    assert apply_packet_task_map("unchanged", {}) == "unchanged"


# --- the plan event ----------------------------------------------------------------------------


def test_plan_event_fields_carries_only_the_source_task():
    assert plan_event_fields({PACKET_TASK_SOURCE_KEY: "b_1", "cached_from": "x"}) == {PACKET_TASK_SOURCE_KEY: "b_1"}
    assert plan_event_fields({"cached_from": "x"}) == {}
    assert plan_event_fields(None) == {}


def _run_episode(tmp_path: Path, planner, task_id: str) -> list[dict]:
    log = EventLog(tmp_path / "out", "ep")
    system = get_system(
        "sft_plan",
        planner=planner,
        executor=MockExecutor.from_config({"type": "mock", "script": ["COMPLETE"]}),
        limits=RunLimits(),
    )
    try:
        system.run(MockEnv(), task_id, 1, log, CostLedger(PriceSchedule({"models": {}, "local": {}})))
    finally:
        log.close()
    lines = (tmp_path / "out" / "ep" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_the_plan_event_payload_names_the_source_task(tmp_path: Path):
    planner = _remapped(tmp_path, {"a_1": "b_1", "b_1": "c_1", "c_1": "a_1"})
    (plan,) = [ev for ev in _run_episode(tmp_path, planner, "c_1") if ev["event_type"] == "plan"]
    # By hand: c_1 -> a_1. The episode is c_1's; the packet and its recorded source are a_1's.
    assert plan["task_id"] == "c_1"
    assert plan["payload"][PACKET_TASK_SOURCE_KEY] == "a_1"
    assert plan["payload"]["packet"]["task_id"] == "a_1"


def test_an_unmapped_replay_keeps_its_plan_event_shape(tmp_path: Path):
    cached = CachedPacketPlanner(_NoLiveInner(), _source(tmp_path), system="planner_alone", seed=1)
    (plan,) = [ev for ev in _run_episode(tmp_path, cached, "a_1") if ev["event_type"] == "plan"]
    assert set(plan["payload"]) == {"packet", "parse_path", "model", "model_reasoning_effort", "thread_id"}
