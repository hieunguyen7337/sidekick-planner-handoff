"""The episode loop's end-of-episode seam (bfcl-env E0.4). MockEnv only; no AppWorld, no network.

The loop used to break on ``action.kind == "COMPLETE"`` whatever the environment said. BFCL
has scripted multi-turn users, so "end of this turn" must differ from "end of episode": its
adapter answers a non-final COMPLETE with the next user message and ``done=False``. The break
is therefore gated on ``env.complete_ends_episode`` (default True). Every environment that
keeps the default -- AppWorld, Mock, every test fake -- must produce the same event stream and
the same executor prompts as before.

``tests/fixtures/bfcl_loop_seam_golden.json`` was written by ``write_golden`` from the loop at
commit 377e4bc, before the gate existed. The cases include an env whose COMPLETE returns
``done=False``: an ungated switch to "break on done" would run past its COMPLETE, so that case
is what proves the gate is needed, not just harmless.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import (
    DelegationPacket,
    Event,
    ExecutorAction,
    Observation,
    PlannerResponse,
    PlanStep,
    Usage,
)
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits, prefix_is_terminal
from sidekick.trajectories.eventlog import EventLog

GOLDEN = Path(__file__).resolve().parents[1] / "fixtures" / "bfcl_loop_seam_golden.json"
TASK_ID = "copy_hello"
SEED = 1
TS = "2023-05-18T12:00:00+00:00"

LIST = "```python\nprint(list_files())\n```"
READ = '```python\nprint(read("inbox.txt"))\n```'
WRITE = '```python\nwrite("outbox.txt", "hello world")\n```'

# A fixed packet: MockPlanner's default one carries a uuid and a wall-clock timestamp, and
# both reach the executor prompt through "Plan: {packet json}".
PACKET = DelegationPacket(
    packet_id="pkt-seam-1",
    task_id=TASK_ID,
    goal="Copy inbox.txt contents into outbox.txt without calling delete_all().",
    plan_steps=[PlanStep(index=0, description="Read inbox.txt"), PlanStep(index=1, description="Write outbox.txt")],
    created_at=TS,
)


def _plan_response() -> PlannerResponse:
    usage = Usage(model="mock-planner", provider="mock", input_tokens=100, output_tokens=20)
    return PlannerResponse(kind="PLAN", packet=PACKET, raw_output=PACKET.model_dump_json(), usage=usage)


class DoneFalseOnCompleteEnv(MockEnv):
    """MockEnv whose COMPLETE does not set ``done``, like several test fakes in this suite."""

    def step(self, action: ExecutorAction) -> Observation:
        obs = super().step(action)
        if action.kind == "COMPLETE":
            return obs.model_copy(update={"done": False})
        return obs


@dataclass
class RecordingExecutor(MockExecutor):
    """MockExecutor that keeps a sha256 of every prompt it was sent."""

    prompt_hashes: list[str] | None = None

    def complete(self, messages: list[dict], **kw: Any):
        if self.prompt_hashes is None:
            self.prompt_hashes = []
        blob = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        self.prompt_hashes.append(hashlib.sha256(blob.encode("utf-8")).hexdigest())
        return super().complete(messages, **kw)


CASES: dict[str, dict[str, Any]] = {
    "executor_alone_mock": {"system": "executor_alone", "env": MockEnv, "script": [LIST, READ, WRITE, "COMPLETE"]},
    "executor_alone_answer": {"system": "executor_alone", "env": MockEnv, "script": [READ, WRITE, "COMPLETE: done"]},
    "fixed_k_advise_mock": {"system": "fixed_k", "env": MockEnv, "script": [LIST, READ, WRITE, "COMPLETE"], "kw": {"k": 2}},
    "fixed_k_takeover_mock": {
        "system": "fixed_k",
        "env": MockEnv,
        "script": [LIST, READ, WRITE, "COMPLETE"],
        "kw": {"k": 2, "takeover": True},
    },
    "planner_alone_mock": {"system": "planner_alone", "env": MockEnv, "script": []},
    # COMPLETE here returns done=False; the third action must never run.
    "executor_alone_done_false": {
        "system": "executor_alone",
        "env": DoneFalseOnCompleteEnv,
        "script": [WRITE, "COMPLETE", LIST, LIST],
    },
}


def _strip(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "ts"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def run_case(name: str) -> dict[str, Any]:
    case = CASES[name]
    planner = MockPlanner(scripts={("*", "plan"): [_plan_response()]})
    executor = RecordingExecutor(script=list(case["script"]))
    system = get_system(
        case["system"],
        planner=planner,
        executor=executor,
        verifier=None,
        limits=RunLimits(max_steps=12),
        **case.get("kw", {}),
    )
    env = case["env"]()
    with tempfile.TemporaryDirectory() as tmp:
        run_id = f"seam/{case['system']}/{SEED}/{TASK_ID}"
        log = EventLog(tmp, run_id)
        try:
            system.run(env, TASK_ID, SEED, log, CostLedger(PriceSchedule({"models": {}, "local": {}})))
        finally:
            log.close()
        lines = (Path(tmp) / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [_strip(json.loads(line)) for line in lines if line.strip()]
    return {"events": events, "executor_prompt_sha256": list(executor.prompt_hashes or [])}


def all_cases() -> dict[str, Any]:
    return json.loads(json.dumps({name: run_case(name) for name in CASES}, sort_keys=True))


def write_golden(path: str | Path = GOLDEN) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(all_cases(), indent=1, sort_keys=True) + "\n", encoding="utf-8")


def test_default_envs_match_the_pre_change_golden() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = all_cases()
    assert sorted(now) == sorted(golden)
    for name in golden:
        assert now[name] == golden[name], name


def test_done_false_env_still_stops_at_complete() -> None:
    # Hand count: WRITE is step 1, COMPLETE is step 2; LIST would be step 3 and must not run.
    events = run_case("executor_alone_done_false")["events"]
    kinds = [e["payload"].get("kind") for e in events if e["event_type"] == "action"]
    assert kinds == ["CODE", "COMPLETE"]
    run_end = events[-1]
    assert run_end["event_type"] == "run_end" and run_end["payload"]["steps"] == 2


# --- the gated side: an env that says COMPLETE ends a turn, not the episode -------------------


class TwoTurnEnv(MockEnv):
    """Two scripted user turns. COMPLETE on turn 0 returns turn 1's message with done=False."""

    complete_ends_episode = False

    def reset(self, task_id: str, seed: int) -> Observation:
        self._turn = 0
        return super().reset(task_id, seed)

    def step(self, action: ExecutorAction) -> Observation:
        if action.kind != "COMPLETE":
            return super().step(action)
        self._step += 1
        if self._turn == 0:
            self._turn = 1
            return Observation(text="next request: copy it again", step=self._step, done=False)
        return Observation(text="all requests done", step=self._step, done=True)


def _two_turn_events(script: list[str]) -> list[dict]:
    CASES["_two_turn"] = {"system": "executor_alone", "env": TwoTurnEnv, "script": script}
    try:
        return run_case("_two_turn")["events"]
    finally:
        del CASES["_two_turn"]


def test_multi_turn_env_continues_past_a_non_final_complete() -> None:
    events = _two_turn_events([WRITE, "COMPLETE", LIST, "COMPLETE", LIST])
    kinds = [e["payload"].get("kind") for e in events if e["event_type"] == "action"]
    # Hand count: turn 0 = WRITE, COMPLETE; turn 1 = LIST, COMPLETE (done=True). The fifth
    # scripted action is never requested.
    assert kinds == ["CODE", "COMPLETE", "CODE", "COMPLETE"]
    obs = [e for e in events if e["event_type"] == "observation"]
    assert [o["payload"]["done"] for o in obs] == [False, False, False, False, True]
    assert events[-1]["payload"]["steps"] == 4 and events[-1]["payload"]["error_type"] is None


def _ev(step: int, event_type: str, payload: dict) -> Event:
    return Event(
        run_id="r", task_id=TASK_ID, system="prefix_handoff", seed=SEED, step=step, ts=TS,
        actor="executor" if event_type == "action" else "environment",  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        payload=payload,
    )


def test_prefix_terminal_trailing_complete_is_gated() -> None:
    events = [_ev(1, "action", {"kind": "COMPLETE"}), _ev(1, "observation", {"text": "next", "done": False})]
    last = Observation(text="next", step=1, done=False)
    assert prefix_is_terminal(events, last) is True  # default: a trailing COMPLETE ends it
    assert prefix_is_terminal(events, last, complete_ends_episode=False) is False
    done = Observation(text="done", step=1, done=True)
    assert prefix_is_terminal(events, done, complete_ends_episode=False) is True


if __name__ == "__main__":
    write_golden(sys.argv[1] if len(sys.argv) > 1 else GOLDEN)
