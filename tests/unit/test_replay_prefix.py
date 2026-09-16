"""Offline tests for replay_prefix (U-D1). MockEnv only: no AppWorld, no vLLM,
no network."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.environments.mock_env import MockEnv  # noqa: E402
from sidekick.protocols.schemas import Event, ExecutorAction  # noqa: E402
from sidekick.replay import replay, replay_prefix  # noqa: E402
import state_probe as sp  # noqa: E402


def ev(step: int, event_type: str, payload: dict | None = None, **kw) -> Event:
    return Event(
        run_id="r1",
        task_id="t1",
        system="planner_alone",
        seed=1,
        step=step,
        ts="2023-05-18T12:00:00+00:00",  # frozen by freezegun, identical across events
        actor="planner" if event_type == "action" else "system",
        event_type=event_type,
        payload=payload or {},
        env_state_hash=kw.get("env_state_hash"),
    )


def code_ev(step: int, code: str) -> Event:
    return ev(step, "action", {"kind": "CODE", "code": code, "raw_output": code})


def obs_ev(step: int, text: str) -> Event:
    # env_state_hash left None: fake hashes would fail replay()'s comparison.
    return ev(step, "observation", {"kind": "observation", "text": text})


GOLD_A = 'print(read("inbox.txt"))'
GOLD_B = 'write("outbox.txt", "hello world")'
COMPLETE = {"kind": "COMPLETE", "message": "done", "raw_output": "COMPLETE: done"}


def write_log(tmp_path: Path, events: list[Event]) -> Path:
    path = tmp_path / "events.jsonl"
    path.write_text("".join(e.model_dump_json() + "\n" for e in events))
    return path


def gold_log() -> list[Event]:
    return [
        ev(0, "run_start", {"limits": {}}),
        code_ev(1, GOLD_A),
        obs_ev(1, "hello world"),
        code_ev(2, GOLD_B),
        obs_ev(2, "wrote outbox.txt"),
        code_ev(3, 'print(read("outbox.txt"))'),
        obs_ev(3, "hello world"),
        ev(4, "action", COMPLETE),
        obs_ev(4, "COMPLETE"),
    ]


class TestReplayPrefix:
    def test_steps_exactly_k_and_world_open(self, tmp_path):
        path = write_log(tmp_path, gold_log())
        world, remaining = replay_prefix(path, 1)
        try:
            assert world._step == 1  # one executed action stepped
            assert world._files["inbox.txt"] == "hello world"
            assert world._closed is False  # caller owns closing
            kinds = [(e.event_type, e.payload.get("kind")) for e in remaining]
            assert kinds[0] == ("action", "CODE")  # gold action for step k+1
            assert GOLD_B in remaining[0].payload["code"]
        finally:
            world.close()
        assert world._closed is True

    def test_ignores_non_executing_kinds(self, tmp_path):
        events = [
            ev(0, "run_start", {}),
            ev(1, "action", {"kind": "ASK_PLANNER", "ask_reason": "which file?"}),
            obs_ev(1, "no-op"),
            code_ev(2, GOLD_A),
            obs_ev(2, "hello world"),
        ]
        path = write_log(tmp_path, events)
        world, remaining = replay_prefix(path, 1)
        world.close()
        assert world._step == 1  # only the CODE action counted
        assert world._files["inbox.txt"] == "hello world"
        assert remaining == []

    def test_two_run_starts_uses_last_attempt_only(self, tmp_path):
        events = [
            ev(0, "run_start", {}),
            code_ev(1, 'write("outbox.txt", "WRONG")'),
            obs_ev(1, "wrote outbox.txt"),
            # retried run appended to the dead attempt's log, no marker but run_start
            ev(0, "run_start", {}),
            code_ev(1, GOLD_A),
            obs_ev(1, "hello world"),
        ]
        path = write_log(tmp_path, events)
        world, _ = replay_prefix(path, 1)
        world.close()
        assert world._files["inbox.txt"] == "hello world"  # second attempt's action
        assert world._files["outbox.txt"] == ""  # the dead attempt's write never happened

    def test_k_larger_than_trajectory_clamps(self, tmp_path):
        # Documented choice: CLAMP, don't raise. gold_log has 4 executed actions
        # (3 CODE + 1 COMPLETE); asking for k=99 steps all of them.
        path = write_log(tmp_path, gold_log())
        world, remaining = replay_prefix(path, 99)
        world.close()
        assert world._step == 4
        assert remaining == []

    def test_replay_unchanged(self, tmp_path):
        path = write_log(tmp_path, gold_log())
        report = replay(path)
        assert report.ok is True
        assert report.n_compared >= 3


class TestProbeMetrics:
    def test_extract_api_ids(self):
        code = 'print(apis.spotify.show_song_library())\napis.phone.search_contacts(x)'
        assert sp.extract_api_ids(code) == {
            "spotify.show_song_library",
            "phone.search_contacts",
        }
        assert sp.extract_api_ids("print(read('inbox.txt'))") == set()

    def test_bucket_for(self):
        assert sp.bucket_for(1) == "1-5"
        assert sp.bucket_for(5) == "1-5"
        assert sp.bucket_for(6) == "6-10"
        assert sp.bucket_for(11) == "11+"

    def test_is_value_forwarding(self):
        gold = ExecutorAction(kind="CODE", code='print(apis.spotify.get_token("tok_abc"))')
        assert sp.is_value_forwarding(gold, ["your token is tok_abc"]) is True
        assert sp.is_value_forwarding(gold, ["nothing relevant here"]) is False
        assert sp.is_value_forwarding(
            ExecutorAction(kind="COMPLETE", message="tok_abc"), ["tok_abc"]
        ) is False

    def test_record_and_finalize_arithmetic(self):
        b = sp.empty_counts()
        ok = {
            "gold_kind": "CODE",
            "state_equivalent_defined": True,
            "hash_match_defined": True,
            "agreement": True,
            "state_equivalent": True,
            "hash_match": False,
            "error_type": None,
        }
        fail = {
            "gold_kind": "CODE",
            "state_equivalent_defined": True,
            "hash_match_defined": True,
            "agreement": False,
            "state_equivalent": False,
            "hash_match": False,
            "error_type": "parse_error",
        }
        for r in (ok, ok, fail):
            sp.record(b, r)
        out = sp.finalize({"overall": b})
        assert out["overall"]["n"] == 3
        assert out["overall"]["n_scorable"] == 3
        assert out["overall"]["agreement"] == 2
        assert out["overall"]["agreement_rate"] == pytest.approx(2 / 3)
        assert out["overall"]["agreement_rate_all_steps"] == pytest.approx(2 / 3)
        assert out["overall"]["state_equivalent_rate"] == pytest.approx(2 / 3)
        assert out["overall"]["hash_match_rate"] == 0.0
        assert out["overall"]["error_type_counts"] == {"none": 2, "parse_error": 1}

    def test_denominators_exclude_gold_complete_and_count_errors(self):
        b = sp.empty_counts()
        records = [
            {
                "gold_kind": "CODE",
                "state_equivalent_defined": True,
                "hash_match_defined": True,
                "agreement": True,
                "state_equivalent": True,
                "hash_match": False,
                "error_type": None,
            },
            {
                "gold_kind": "CODE",
                "state_equivalent_defined": True,
                "hash_match_defined": True,
                # record() must treat an error as a failure even if a caller
                # accidentally supplies truthy metric flags.
                "agreement": True,
                "state_equivalent": True,
                "hash_match": True,
                "error_type": "parse_error",
            },
            {
                "gold_kind": "COMPLETE",
                "state_equivalent_defined": False,
                "hash_match_defined": False,
                "agreement": False,
                "state_equivalent": False,
                "hash_match": False,
                "error_type": None,
            },
        ]
        for rec in records:
            sp.record(b, rec)
        out = sp.finalize({"overall": b})["overall"]
        assert out["n"] == 3
        assert out["n_scorable"] == out["n"] - 1
        assert out["agreement_rate"] == pytest.approx(1 / 2)
        assert out["agreement_rate"] > out["agreement_rate_all_steps"]
        assert out["n_gold_noncode"] == 1
        assert out["gold_noncode_counts"] == {"COMPLETE": 1}
        assert out["n_state_equivalent"] == 2
        assert out["state_equivalent"] == 1
        assert out["n_hash_match"] == 2
        assert out["hash_match"] == 0
        assert out["error_type_counts"] == {"none": 2, "parse_error": 1}

    def test_find_solved_runs(self, tmp_path):
        for name, success in [("a", True), ("b", False)]:
            d = tmp_path / "sys" / "1" / name
            d.mkdir(parents=True)
            (d / "events.jsonl").write_text("")
            (d / "result.json").write_text(json.dumps({"success": success}))
        runs = sp.find_solved_runs(tmp_path, "sys", 0)
        assert [r.name for r in runs] == ["a"]


class StubExecutor:
    """Scripted raw outputs; no network."""

    def __init__(self, raws: list[str]):
        self.raws = list(raws)
        self.model = "stub"
        self.lora_name = None

    def complete(self, messages, **kw):
        return self.raws.pop(0), None


def gold_pairs() -> list[tuple[ExecutorAction, Event]]:
    return [
        (ExecutorAction(kind="CODE", code=GOLD_A), obs_ev(1, "hello world")),
        (ExecutorAction(kind="CODE", code=GOLD_B), obs_ev(2, "wrote outbox.txt")),
        (ExecutorAction(kind="CODE", code='print(read("outbox.txt"))'), obs_ev(3, "hello world")),
        (ExecutorAction(kind="COMPLETE", message="done"), obs_ev(4, "COMPLETE")),
    ]


def test_probe_step_agreement_and_state_equivalent(tmp_path):
    path = write_log(tmp_path, gold_log())
    # k=1: gold step 1 replayed; model must replace step 2 (GOLD_B).
    # agreement True (no error, same id set), state_equivalent True: the gold
    # step-3 action (read outbox) then reproduces the gold observation.
    world, _ = replay_prefix(path, 1)
    try:
        rec = sp.probe_step(
            StubExecutor([f"```python\n{GOLD_B}\n```"]), world, gold_pairs(), 1, "x", ""
        )
    finally:
        world.close()
    assert rec["error_type"] is None
    assert rec["agreement"] is True
    assert rec["state_equivalent"] is True
    # history must NOT leak the gold action under test
    assert rec["model_raw"].startswith("```python")


def test_probe_step_wrong_action_fails_state_equivalent(tmp_path):
    path = write_log(tmp_path, gold_log())
    world, _ = replay_prefix(path, 1)
    try:
        rec = sp.probe_step(
            StubExecutor(['```python\nwrite("outbox.txt", "WRONG")\n```']),
            world,
            gold_pairs(),
            1,
            "x",
            "",
        )
    finally:
        world.close()
    assert rec["error_type"] is None
    assert rec["state_equivalent"] is False  # gold step 3 now reads "WRONG", not "hello world"


def test_probe_step_parse_error_recorded(tmp_path):
    path = write_log(tmp_path, gold_log())
    world, _ = replay_prefix(path, 1)
    try:
        rec = sp.probe_step(StubExecutor(["I will think about it."]), world, gold_pairs(), 1, "x", "")
    finally:
        world.close()
    assert rec["error_type"] == "parse_error"  # failure is a data point, not dropped
    assert rec["gold_kind"] == "CODE"
    assert rec["agreement_defined"] is True
