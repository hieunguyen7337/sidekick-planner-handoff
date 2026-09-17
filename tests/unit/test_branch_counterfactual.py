"""W-1 counterfactual branching: points, renderer identity, labels, resume, oracle."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.agents.executor import MockExecutor  # noqa: E402
from sidekick.agents.planner import MockPlanner  # noqa: E402
from sidekick.cost.ledger import CostLedger  # noqa: E402
from sidekick.cost.prices import PriceSchedule  # noqa: E402
from sidekick.environments.mock_env import MockEnv  # noqa: E402
from sidekick.protocols.prompts import render_executor_messages  # noqa: E402
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction  # noqa: E402
from sidekick.replay import replay_prefix  # noqa: E402
from sidekick.runner import system_kwargs  # noqa: E402
from sidekick.systems.loop import EpisodePrefix, RunLimits, SystemPolicy, run_episode  # noqa: E402
from sidekick.training.sft_data import _history_from_events  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402
import branch_counterfactual as bc  # noqa: E402

INSTRUCTION = "Copy inbox.txt to outbox.txt"
API_DOCS = (
    "list_files() -> list[str]\n"
    "read(name: str) -> str\n"
    "write(name: str, content: str) -> str\n"
    "delete_all() -> str  # IRREVERSIBLE: wipes every file and fails the task\n"
)
PACKET = DelegationPacket(
    packet_id="pkt-1",
    task_id="copy_hello",
    goal=INSTRUCTION,
    created_at="2026-09-16T00:00:00+00:00",
)
READ_CODE = 'print(read("inbox.txt"))'
WRITE_CODE = 'write("outbox.txt", "hello world")'
PRICES = REPO_ROOT / "configs" / "cost" / "prices_2026-09.yaml"


def _event(
    *,
    event_type: str,
    step: int,
    actor: str,
    payload: dict,
    task_id: str = "copy_hello",
    seed: int = 1,
    run_id: str = "camp/fixed_k/1/copy_hello",
    usage: dict | None = None,
) -> Event:
    data = {
        "run_id": run_id,
        "task_id": task_id,
        "system": "fixed_k",
        "seed": seed,
        "step": step,
        "ts": "2023-05-18T12:00:00+00:00",
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
    }
    if usage is not None:
        data["usage"] = usage
    return Event.model_validate(data)


def _code_payload(code: str) -> dict:
    return ExecutorAction(kind="CODE", code=code, raw_output=code).model_dump()


def two_intervention_events(task_id: str = "copy_hello", seed: int = 1) -> list[Event]:
    """run_start, obs, plan, two CODE steps, then two timer interventions.

    Matches loop.py: intervention at step s is emitted *before* the action at s.
    """
    run_id = f"camp/fixed_k/{seed}/{task_id}"
    usage = {
        "model": "mock",
        "provider": "mock",
        "input_tokens": 10,
        "output_tokens": 5,
        "n_calls": 1,
    }
    events = [
        _event(
            event_type="run_start",
            step=0,
            actor="system",
            payload={
                "limits": {
                    "max_steps": 40,
                    "max_tokens_per_episode": 32000,
                    "per_step_timeout_s": 120,
                    "max_planner_calls": 25,
                },
                "policy": {"adapter_name": "sft_b", "review_every_k": 5},
            },
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        ),
        _event(
            event_type="observation",
            step=0,
            actor="environment",
            payload={"text": INSTRUCTION, "done": False},
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        ),
        _event(
            event_type="plan",
            step=0,
            actor="planner",
            payload={"packet": PACKET.model_dump(), "api_docs_prompt": API_DOCS},
            task_id=task_id,
            seed=seed,
            run_id=run_id,
            usage=usage,
        ),
        _event(
            event_type="action",
            step=1,
            actor="executor",
            payload=_code_payload(READ_CODE),
            task_id=task_id,
            seed=seed,
            run_id=run_id,
            usage=usage,
        ),
        _event(
            event_type="observation",
            step=1,
            actor="environment",
            payload={"text": "hello world", "done": False, "kind": "CODE"},
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        ),
        _event(
            event_type="action",
            step=2,
            actor="executor",
            payload=_code_payload(WRITE_CODE),
            task_id=task_id,
            seed=seed,
            run_id=run_id,
            usage=usage,
        ),
        _event(
            event_type="observation",
            step=2,
            actor="environment",
            payload={"text": "wrote outbox.txt", "done": False, "kind": "CODE"},
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        ),
    ]
    corrections = ("first correction", "second correction")
    step = 3
    for i, correction in enumerate(corrections):
        events.append(
            _event(
                event_type="intervention",
                step=step,
                actor="planner",
                payload={"correction": correction, "forced": True, "n_interventions": i + 1},
                task_id=task_id,
                seed=seed,
                run_id=run_id,
                usage=usage,
            )
        )
        events.append(
            _event(
                event_type="action",
                step=step,
                actor="executor",
                payload=_code_payload("pass"),
                task_id=task_id,
                seed=seed,
                run_id=run_id,
                usage=usage,
            )
        )
        events.append(
            _event(
                event_type="observation",
                step=step,
                actor="environment",
                payload={"text": f"obs-{i}", "done": False, "kind": "CODE"},
                task_id=task_id,
                seed=seed,
                run_id=run_id,
            )
        )
        step += 1
    events.append(
        _event(
            event_type="action",
            step=step,
            actor="executor",
            payload=ExecutorAction(kind="COMPLETE", raw_output="COMPLETE").model_dump(),
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        )
    )
    events.append(
        _event(
            event_type="observation",
            step=step,
            actor="environment",
            payload={"text": "COMPLETE", "done": True, "kind": "COMPLETE"},
            task_id=task_id,
            seed=seed,
            run_id=run_id,
        )
    )
    return events


def write_episode(
    root: Path,
    *,
    task_id: str = "copy_hello",
    seed: int = 1,
    events: list[Event] | None = None,
    success: bool = True,
    goal_pass_rate: float | None = 1.0,
    campaign: str = "camp",
) -> Path:
    events = events or two_intervention_events(task_id=task_id, seed=seed)
    run_dir = root / "fixed_k" / str(seed) / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": f"{campaign}/fixed_k/{seed}/{task_id}",
        "task_id": task_id,
        "system": "fixed_k",
        "seed": seed,
        "success": success,
        "tgc": 1.0 if success else 0.0,
        "sgc": None,
        "goal_pass_rate": goal_pass_rate,
        "steps": 5,
        "n_planner_calls": 3,
        "n_asks": 0,
        "n_interventions": 2,
        "error_type": None,
        "totals": {},
    }
    (run_dir / "result.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(ev.model_dump_json() + "\n")
    return run_dir


@dataclass
class RecordingExecutor(MockExecutor):
    calls: list = field(default_factory=list)

    def complete(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        return super().complete(messages, **kw)


def test_two_interventions_yield_two_points_at_event_indices():
    events = two_intervention_events()
    points = bc.enumerate_intervention_points(events)
    assert len(points) == 2
    assert points[0]["i"] == 0
    assert points[1]["i"] == 1
    assert points[0]["step"] == 3
    assert points[1]["step"] == 4
    assert events[points[0]["event_index"]].event_type == "intervention"
    assert events[points[1]["event_index"]].event_type == "intervention"
    assert events[points[0]["event_index"]].payload["correction"] == "first correction"
    assert events[points[1]["event_index"]].payload["correction"] == "second correction"
    # Prefix for i is everything strictly before that intervention event.
    assert points[0]["event_index"] == 7  # after run_start,obs,plan,a,o,a,o
    assert points[1]["event_index"] > points[0]["event_index"]
    k0 = bc.executed_prefix_k(bc.prefix_events_before_intervention(events, 0))
    k1 = bc.executed_prefix_k(bc.prefix_events_before_intervention(events, 1))
    assert k0 == 2  # two CODE actions before the first intervention
    assert k1 == 3  # those two plus the CODE that followed intervention 0


def test_branch_context_keeps_prior_interventions_and_matches_training_renderer():
    events = two_intervention_events()
    for i in (0, 1):
        prefix = bc.prefix_events_before_intervention(events, i)
        instruction, packet, api_docs, history = _history_from_events(prefix)
        expected = render_executor_messages(
            instruction=instruction, api_docs=api_docs, packet=packet, history=history
        )
        got = bc.render_branch_context(events, i)
        assert got == expected
        joined = json.dumps(got)
        if i == 0:
            assert "INTERVENTION:" not in joined
        else:
            assert "INTERVENTION: first correction" in joined
            assert "INTERVENTION: second correction" not in joined


def test_branch_loop_first_call_matches_training_renderer(tmp_path):
    events = two_intervention_events()
    path = tmp_path / "events.jsonl"
    path.write_text("".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8")
    i = 1
    prefix = bc.prefix_events_before_intervention(events, i)
    k = bc.executed_prefix_k(prefix)
    expected = bc.render_branch_context(events, i)
    world = replay_prefix(path, k, MockEnv())[0]
    executor = RecordingExecutor()
    log = EventLog(tmp_path, "branch_ctx")
    ledger = CostLedger(PriceSchedule.load(PRICES))
    try:
        run_episode(
            name="fixed_k",
            env=world,
            planner=MockPlanner(),
            executor=executor,
            verifier=None,
            policy=SystemPolicy(
                plan_first=False,
                planner_drives=False,
                allow_executor_ask=False,
                review_every_k=None,
                adapter_name="sft_b",
            ),
            limits=RunLimits(max_steps=40),
            task_id="copy_hello",
            seed=1,
            log=log,
            ledger=ledger,
            prefix=EpisodePrefix(events=prefix, start_step=4),
        )
    finally:
        log.close()
    assert executor.calls, "executor was never called"
    assert executor.calls[0] == expected
    assert executor.last_lora_name == "sft_b"
    branch_events = list(EventLog.read(tmp_path / "branch_ctx" / "events.jsonl"))
    action_steps = [e.step for e in branch_events if e.event_type == "action"]
    assert action_steps[0] == 4


@pytest.mark.parametrize(
    ("actual", "branches", "needed", "needed_strict", "harmful", "status"),
    [
        (0.8, [0.4, 0.4], True, True, False, "complete"),
        (0.5, [0.5, 0.5], False, False, False, "complete"),  # mean == actual → needless
        (0.4, [0.8, 0.6], False, False, True, "complete"),
        (0.7, [0.5, 0.8], True, False, False, "complete"),  # mean 0.65 < 0.7, not both
        (0.9, [0.1, None], None, None, None, "incomplete"),
        (None, [0.1, 0.2], None, None, None, "incomplete"),
    ],
)
def test_label_rule(actual, branches, needed, needed_strict, harmful, status):
    out = bc.label_point(actual, branches)
    assert out["label_status"] == status
    assert out["needed"] is needed
    assert out["needed_strict"] is needed_strict
    assert out["harmful"] is harmful


def test_resume_skips_completed_branches_and_fills_the_rest(tmp_path):
    campaign = tmp_path / "hj4_fake"
    write_episode(campaign, goal_pass_rate=1.0)
    out1 = tmp_path / "branches_out"
    first = bc.run_branches(
        campaign_root=campaign,
        out_root=out1,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=1,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
    )
    assert first["n_finished"] == 1
    runs = bc.load_jsonl(out1 / "branch_runs.jsonl")
    assert len(runs) == 1
    first_key = runs[0]["key"]
    first_run_id = runs[0]["run_id"]
    events_path = out1 / first_run_id / "events.jsonl"
    first_text = events_path.read_text(encoding="utf-8")
    first_lines = first_text.splitlines()

    second = bc.run_branches(
        campaign_root=campaign,
        out_root=out1,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=None,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
    )
    runs2 = bc.load_jsonl(out1 / "branch_runs.jsonl")
    keys = [r["key"] for r in runs2]
    assert len(keys) == 4  # 2 points × 2 seeds
    assert len(set(keys)) == 4
    assert keys.count(first_key) == 1
    assert events_path.read_text(encoding="utf-8") == first_text
    assert events_path.read_text(encoding="utf-8").splitlines() == first_lines
    assert second["n_finished"] == 3
    points = bc.load_jsonl(out1 / "branches.jsonl")
    assert len(points) == 2
    assert {p["i"] for p in points} == {0, 1}
    labels = json.loads((out1 / "oracle_labels.json").read_text(encoding="utf-8"))
    assert isinstance(labels, dict)


def test_oracle_labels_round_trip_through_runner():
    labels = {
        "copy_hello/1": [5, 15],
        "copy_hello": [3],
    }
    cfg = {"oracle_labels": labels, "executor": {"lora_name": "sft_b"}}
    keyed = system_kwargs("oracle_escalation", cfg, "copy_hello", 1)
    assert keyed["oracle_steps"] == [5, 15]
    assert keyed["adapter_name"] == "sft_b"
    fallback = system_kwargs("oracle_escalation", cfg, "copy_hello", 9)
    assert fallback["oracle_steps"] == [3]
    assert fallback["adapter_name"] == "sft_b"
    # File shape emitted by the script.
    built = bc.build_oracle_labels(
        [
            {
                "task_id": "copy_hello",
                "seed": 1,
                "step": 15,
                "needed": True,
                "label_status": "complete",
            },
            {
                "task_id": "copy_hello",
                "seed": 1,
                "step": 5,
                "needed": True,
                "label_status": "complete",
            },
            {
                "task_id": "copy_hello",
                "seed": 1,
                "step": 10,
                "needed": False,
                "label_status": "complete",
            },
            {
                "task_id": "other",
                "seed": 2,
                "step": 5,
                "needed": True,
                "label_status": "incomplete",
            },
        ]
    )
    assert built == {"copy_hello/1": [5, 15]}
    through = system_kwargs(
        "oracle_escalation",
        {"oracle_labels": built, "executor": {"lora_name": "sft_b"}},
        "copy_hello",
        1,
    )
    assert through["oracle_steps"] == [5, 15]


def test_default_run_episode_still_starts_at_step_one(tmp_path):
    log = EventLog(tmp_path, "no_prefix")
    ledger = CostLedger(PriceSchedule.load(PRICES))
    try:
        result = run_episode(
            name="prompt_only",
            env=MockEnv(),
            planner=MockPlanner(),
            executor=MockExecutor(),
            verifier=None,
            policy=SystemPolicy(plan_first=True, review_every_k=None),
            limits=RunLimits(max_steps=40),
            task_id="copy_hello",
            seed=1,
            log=log,
            ledger=ledger,
        )
    finally:
        log.close()
    events = list(EventLog.read(tmp_path / "no_prefix" / "events.jsonl"))
    assert events[0].event_type == "run_start"
    assert "prefix" not in (events[0].payload or {})
    action_steps = [e.step for e in events if e.event_type == "action"]
    assert action_steps[0] == 1
    assert result.error_type is None
