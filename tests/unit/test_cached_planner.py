"""Unit tests for CachedPacketPlanner (U-C): replay archived planner packets.

Offline, fast, no network, no GPU, no AppWorld import. Fixtures are tiny
events.jsonl files written under tmp_path in the archive layout
<packet_source>/<system>/<seed>/<task_id>/events.jsonl.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidekick.agents.planner import CachedPacketPlanner, MockPlanner
from sidekick.protocols.schemas import DelegationPacket, PlannerResponse, Usage
from sidekick.runner import make_planner


def _packet(task_id: str = "copy_hello", goal: str = "copy inbox to outbox") -> dict:
    return {
        "packet_id": f"pkt-{task_id}",
        "task_id": task_id,
        "goal": goal,
        "plan_steps": [{"index": 1, "description": "read inbox", "expected_outcome": "text", "apps": []}],
        "constraints": [],
        "success_criteria": [],
        "forbidden_actions": [],
        "context_digest": "abc",
        "created_at": "2026-09-15T00:00:00+00:00",
    }


def _event(run_id: str, event_type: str, payload: dict, usage: dict | None = None, task_id: str = "copy_hello") -> dict:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "system": "planner_alone",
        "seed": 1,
        "step": 0,
        "ts": "2026-09-15T12:00:00+00:00",  # frozen by freezegun; identical everywhere
        "actor": "planner" if event_type == "plan" else "system",
        "event_type": event_type,
        "payload": payload,
        "usage": usage,
        "error_type": None,
    }


def _write_archive(
    root: Path,
    lines: list[dict],
    seed: int = 1,
    task_id: str = "copy_hello",
    *,
    system: str = "planner_alone",
) -> Path:
    path = root / system / str(seed) / task_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def _plan_line(model: str = "gpt-5.6-luna", thread_id: str | None = "th-123", task_id: str = "copy_hello") -> dict:
    usage = {
        "model": model,
        "provider": "codex",
        "input_tokens": 15000,
        "cached_input_tokens": 0,
        "output_tokens": 200,
        "reasoning_output_tokens": 40,
        "latency_s": 1.0,
        "gpu_seconds": 0.0,
        "n_calls": 1,
        "raw": {"model": model},
    }
    payload: dict = {"packet": _packet(task_id), "model": model}
    if thread_id is not None:
        payload["thread_id"] = thread_id
    return _event("r1", "plan", payload, usage, task_id=task_id)


class RecordingInner:
    """Stub inner planner that records the prompts it was handed."""

    name = "recording"

    def __init__(self) -> None:
        self.correct_prompts: list[str] = []
        self.act_prompts: list[str] = []
        self.plan_calls: list[str] = []
        self.closed = False

    def plan(self, task_id: str, goal: str, context: str, timeout_s=None) -> PlannerResponse:
        self.plan_calls.append(context)
        packet = DelegationPacket.model_validate(_packet(task_id))
        return PlannerResponse(
            kind="PLAN",
            packet=packet,
            usage=Usage(model="gpt-5.6-luna", provider="codex", input_tokens=10, output_tokens=2, n_calls=1),
        )

    def correct(self, packet: DelegationPacket, transcript_delta: str, timeout_s=None) -> PlannerResponse:
        self.correct_prompts.append(transcript_delta)
        return PlannerResponse(
            kind="CORRECTION",
            packet=packet,
            correction="ok",
            usage=Usage(model="gpt-5.6-luna", provider="codex", input_tokens=10, output_tokens=2, n_calls=1),
        )

    def act(self, task_id: str, transcript: str, timeout_s=None) -> PlannerResponse:
        self.act_prompts.append(transcript)
        return PlannerResponse(
            kind="ACTION",
            code="print(1)",
            usage=Usage(model="gpt-5.6-luna", provider="codex", input_tokens=10, output_tokens=2, n_calls=1),
        )

    def close(self) -> None:
        self.closed = True


def test_cache_hit_returns_archived_packet_with_zero_token_cache_usage(tmp_path):
    _write_archive(tmp_path, [_event("r1", "run_start", {}), _plan_line()])
    inner = RecordingInner()
    planner = CachedPacketPlanner(inner, tmp_path, system="planner_alone", seed=1)
    resp = planner.plan("copy_hello", "copy inbox to outbox", "api docs prompt")
    assert resp.kind == "PLAN"
    assert resp.packet is not None and resp.packet.packet_id == "pkt-copy_hello"
    assert resp.usage.provider == "cache"
    assert resp.usage.model == "gpt-5.6-luna"
    assert resp.usage.n_calls == 0
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
        assert getattr(resp.usage, field) == 0
    assert resp.usage.raw["cached_from"].endswith("events.jsonl")
    assert resp.usage.raw["cached_thread_id"] == "th-123"
    assert resp.thread_id == "th-123"
    assert inner.plan_calls == []  # no live call was made


def test_cache_hit_falls_back_to_event_usage_model(tmp_path):
    lines = [_event("r1", "run_start", {}), _plan_line()]
    lines[1]["payload"].pop("model")  # no payload["model"]; usage.model must be used
    _write_archive(tmp_path, lines)
    planner = CachedPacketPlanner(RecordingInner(), tmp_path, seed=1)
    resp = planner.plan("copy_hello", "g", "c")
    assert resp.usage.model == "gpt-5.6-luna"


def test_miss_under_on_missing_fail_raises_naming_path(tmp_path):
    planner = CachedPacketPlanner(RecordingInner(), tmp_path, system="planner_alone", seed=1)
    with pytest.raises(FileNotFoundError) as err:
        planner.plan("copy_hello", "g", "c")
    assert "planner_alone/1/copy_hello/events.jsonl" in str(err.value)


def test_miss_under_on_missing_call_falls_through(tmp_path):
    inner = RecordingInner()
    planner = CachedPacketPlanner(inner, tmp_path, seed=1, on_missing="call")
    resp = planner.plan("copy_hello", "g", "c")
    assert inner.plan_calls == ["c"]
    assert resp.usage.provider == "codex" and resp.usage.n_calls == 1


def test_two_run_starts_yields_packet_from_second_later_attempt(tmp_path):
    dead = _plan_line(thread_id="th-dead")
    dead["payload"]["packet"]["packet_id"] = "pkt-dead"
    live = _plan_line(thread_id="th-live")
    live["payload"]["packet"]["packet_id"] = "pkt-live"
    # Two concatenated attempts, identical `ts`; only file order distinguishes them.
    _write_archive(
        tmp_path,
        [
            _event("r-dead", "run_start", {}),
            dead,
            _event("r-live", "run_start", {}),
            live,
        ],
    )
    planner = CachedPacketPlanner(RecordingInner(), tmp_path, seed=1)
    resp = planner.plan("copy_hello", "g", "c")
    assert resp.packet.packet_id == "pkt-live"
    assert resp.usage.raw["cached_thread_id"] == "th-live"


def test_first_live_call_gets_digest_only_once(tmp_path):
    _write_archive(tmp_path, [_event("r1", "run_start", {}), _plan_line()])
    inner = RecordingInner()
    planner = CachedPacketPlanner(inner, tmp_path, seed=1)
    packet = DelegationPacket.model_validate(_packet())
    planner.plan("copy_hello", "g", "THE-API-DIGEST")
    planner.correct(packet, "delta-1")
    planner.correct(packet, "delta-2")
    planner.act("copy_hello", "transcript-1")
    assert inner.correct_prompts[0].startswith("=== api digest (plan was replayed; no prior session) ===")
    assert "THE-API-DIGEST" in inner.correct_prompts[0]
    assert inner.correct_prompts[0].endswith("delta-1")
    assert "THE-API-DIGEST" not in inner.correct_prompts[1]
    assert inner.act_prompts[0] == "transcript-1"  # digest already spent on the first correct
    planner.close()
    assert inner.closed


def test_make_planner_without_packet_source_returns_unwrapped_planner():
    planner = make_planner({"planner": {"type": "mock"}}, seed=3, system_name="prompt_only")
    assert isinstance(planner, MockPlanner)


def test_make_planner_with_packet_source_wraps_and_threads_seed_and_system(tmp_path):
    (tmp_path / "planner_alone").mkdir()
    planner = make_planner(
        {
            "planner": {
                "type": "mock",
                "packet_source": str(tmp_path),
                "packet_system": "planner_alone",
            }
        },
        seed=7,
        system_name="prompt_only",
    )
    assert isinstance(planner, CachedPacketPlanner)
    assert planner.seed == 7
    assert planner.system == "planner_alone"


def test_explicit_packet_system_wins_over_available_subtrees_and_consuming_arm(tmp_path):
    lines = [_event("r1", "run_start", {}), _plan_line()]
    _write_archive(tmp_path, lines, system="planner_alone")
    _write_archive(tmp_path, lines, system="prompt_only")
    planner = make_planner(
        {
            "planner": {
                "type": "mock",
                "packet_source": str(tmp_path),
                "packet_system": "planner_alone",
            }
        },
        seed=1,
        system_name="prompt_only",
    )
    assert planner.system == "planner_alone"


def test_single_packet_subdirectory_is_autodetected(tmp_path):
    _write_archive(tmp_path, [_event("r1", "run_start", {}), _plan_line()])
    planner = make_planner(
        {"planner": {"type": "mock", "packet_source": str(tmp_path)}},
        seed=1,
        system_name="prompt_only",
    )
    assert planner.system == "planner_alone"


def test_multiple_packet_subdirectories_without_packet_system_raise_with_available_names(tmp_path):
    lines = [_event("r1", "run_start", {}), _plan_line()]
    _write_archive(tmp_path, lines, system="planner_alone")
    _write_archive(tmp_path, lines, system="planner_other")
    with pytest.raises(ValueError) as err:
        make_planner(
            {"planner": {"type": "mock", "packet_source": str(tmp_path)}},
            seed=1,
            system_name="prompt_only",
        )
    message = str(err.value)
    assert "planner_alone" in message
    assert "planner_other" in message


def test_consuming_arm_system_name_does_not_select_cached_subtree(tmp_path):
    _write_archive(tmp_path, [_event("r1", "run_start", {}), _plan_line()])
    planner = make_planner(
        {"planner": {"type": "mock", "packet_source": str(tmp_path)}},
        seed=1,
        system_name="sft_plan",
    )
    assert planner.system == "planner_alone"
