"""W-1b counterfactual branching: focal estimand, CRN, δ-band, resume."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.agents.executor import MockExecutor, VLLMExecutor  # noqa: E402
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


def two_intervention_events(
    task_id: str = "copy_hello", seed: int = 1, n_corrections: int = 2
) -> list[Event]:
    """run_start, obs, plan, two CODE steps, then timer interventions.

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
    corrections = ("first correction", "second correction")[:n_corrections]
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
    n_int = sum(1 for ev in events if ev.event_type == "intervention")
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
        "n_interventions": n_int,
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
    seeds: list = field(default_factory=list)

    def complete(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        self.seeds.append(kw.get("seed"))
        return super().complete(messages, **kw)


class CountingPlanner:
    """MockPlanner wrapper that counts live correct() calls."""

    def __init__(self) -> None:
        self.inner = MockPlanner()
        self.n_correct = 0

    def plan(self, *args, **kwargs):
        return self.inner.plan(*args, **kwargs)

    def correct(self, packet, transcript_delta, timeout_s=None):
        self.n_correct += 1
        return self.inner.correct(packet, transcript_delta, timeout_s=timeout_s)

    def act(self, *args, **kwargs):
        return self.inner.act(*args, **kwargs)

    def close(self) -> None:
        return None


def _continue_from_focal(tmp_path, *, condition: str, sampling_seed: int = 101, run_id: str = "br"):
    events = two_intervention_events()
    i = 0
    prefix = bc.prefix_events_before_intervention(events, i)
    point = bc.enumerate_intervention_points(events)[i]
    executor = RecordingExecutor()
    planner = CountingPlanner()
    log = EventLog(tmp_path, run_id)
    ledger = CostLedger(PriceSchedule.load(PRICES))
    inject = point["correction"] if condition == "treated" else None
    try:
        run_episode(
            name="fixed_k",
            env=MockEnv(),
            planner=planner,
            executor=executor,
            verifier=None,
            policy=SystemPolicy(
                plan_first=False,
                planner_drives=False,
                allow_executor_ask=False,
                review_every_k=5,
                adapter_name="sft_b",
            ),
            limits=RunLimits(max_steps=40),
            task_id="copy_hello",
            seed=1,
            log=log,
            ledger=ledger,
            prefix=EpisodePrefix(
                events=prefix,
                start_step=int(point["step"]),
                inject_correction=inject,
                skip_review_at_start=True,
                local_eval_step=bc.next_scheduled_review_step(int(point["step"]), 5),
            ),
            sampling_seed=sampling_seed,
        )
    finally:
        log.close()
    out_events = list(EventLog.read(tmp_path / run_id / "events.jsonl"))
    return executor, planner, out_events, point


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
    assert points[0]["event_index"] == 7
    assert points[1]["event_index"] > points[0]["event_index"]
    k0 = bc.executed_prefix_k(bc.prefix_events_before_intervention(events, 0))
    k1 = bc.executed_prefix_k(bc.prefix_events_before_intervention(events, 1))
    assert k0 == 2
    assert k1 == 3


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


def test_untreated_omits_only_focal_later_review_fires(tmp_path):
    executor, planner, out_events, point = _continue_from_focal(tmp_path, condition="untreated")
    interventions = [e for e in out_events if e.event_type == "intervention"]
    texts = [str((e.payload or {}).get("correction") or "") for e in interventions]
    assert point["correction"] not in texts
    assert "second correction" not in texts
    later = [e for e in interventions if e.step > point["step"]]
    assert later, "a later scheduled review must still fire"
    assert any((e.payload or {}).get("source") == "live_policy" for e in later)
    assert planner.n_correct >= 1
    joined = json.dumps(executor.calls[0])
    assert "INTERVENTION: first correction" not in joined


def test_treated_keeps_focal_and_later_reviews(tmp_path):
    executor, planner, out_events, point = _continue_from_focal(
        tmp_path, condition="treated", run_id="br_t"
    )
    interventions = [e for e in out_events if e.event_type == "intervention"]
    focal = [e for e in interventions if (e.payload or {}).get("source") == "replayed_focal"]
    later = [e for e in interventions if (e.payload or {}).get("source") == "live_policy"]
    assert focal, "treated arm must inject intervention i"
    assert focal[0].payload["correction"] == point["correction"]
    assert focal[0].step == point["step"]
    assert later, "treated arm must keep later scheduled ticks"
    assert all(e.step > point["step"] for e in later)
    assert planner.n_correct >= 1
    joined = json.dumps(executor.calls[0])
    assert "INTERVENTION: first correction" in joined


def test_crn_same_branch_seed_enters_sampling(tmp_path):
    exec_t, _, events_t, _ = _continue_from_focal(
        tmp_path / "t", condition="treated", sampling_seed=101, run_id="t"
    )
    exec_u, _, events_u, _ = _continue_from_focal(
        tmp_path / "u", condition="untreated", sampling_seed=101, run_id="u"
    )
    assert exec_t.seeds
    assert exec_u.seeds
    assert exec_t.seeds == exec_u.seeds
    assert set(exec_t.seeds) == {101}
    assert (events_t[0].payload or {}).get("sampling_seed") == 101
    assert (events_u[0].payload or {}).get("sampling_seed") == 101
    campaign = tmp_path / "hj4_fake"
    write_episode(campaign)
    jobs = bc.collect_jobs(
        campaign_root=campaign,
        out_root=tmp_path / "out",
        split="train",
        branch_seeds=[101, 102],
        resume=False,
        limit=None,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
        adapter_fallback="sft_b",
    )
    pairs = {}
    for job in jobs:
        if job["i"] != 0:
            continue
        pairs.setdefault(job["branch_seed"], {})[job["condition"]] = job["branch_seed"]
    assert pairs[101]["treated"] == pairs[101]["untreated"] == 101
    assert pairs[102]["treated"] == pairs[102]["untreated"] == 102


def test_vllm_complete_forwards_seed():
    captured = {}

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "COMPLETE"}}], "usage": {"prompt_tokens": 1}}

    class _Client:
        def post(self, url, json=None):
            captured["payload"] = json
            return _Resp()

    ex = VLLMExecutor("test-model", "http://x", http_client=_Client())
    ex.complete([{"role": "user", "content": "hi"}], seed=101)
    assert captured["payload"]["seed"] == 101


@pytest.mark.parametrize(
    ("treated", "untreated", "band", "needed", "needless", "ambiguous", "harmful", "strict", "status"),
    [
        ([0.8, 0.8], [0.4, 0.4], 0.1, True, False, False, False, True, "complete"),
        ([0.5, 0.5], [0.5, 0.5], 0.1, False, False, True, False, False, "complete"),
        ([0.4, 0.4], [0.8, 0.8], 0.1, False, True, False, True, False, "complete"),
        ([0.55, 0.55], [0.50, 0.50], 0.1, False, False, True, False, True, "complete"),
        ([0.8, 0.2], [0.3, 0.1], 0.1, True, False, False, False, False, "complete"),
        ([0.5, None], [0.4, 0.4], 0.1, None, None, None, None, None, "incomplete"),
    ],
)
def test_label_rule(treated, untreated, band, needed, needless, ambiguous, harmful, strict, status):
    if any(g is None for g in list(treated) + list(untreated)):
        delta = None
    else:
        delta = ((treated[0] - untreated[0]) + (treated[1] - untreated[1])) / 2
    out = bc.label_focal(treated, untreated, delta, band)
    assert out["label_status"] == status
    assert out["needed"] is needed
    assert out["needless"] is needless
    assert out["ambiguous"] is ambiguous
    assert out["harmful"] is harmful
    assert out["needed_strict"] is strict


def test_delta_band_ambiguous_under_noise_floor_needed_at_zero():
    band = bc.compute_delta_band([(0.8, 0.7), (0.5, 0.4), (0.9, 0.5)])
    assert band == pytest.approx(0.25)
    delta = 0.05
    out = bc.label_focal([0.55, 0.55], [0.50, 0.50], delta, band)
    assert out["ambiguous"] is True
    assert out["needed"] is False
    assert delta > 0  # would have been needed at a zero threshold


def test_incomplete_when_any_of_four_samples_missing():
    out = bc.label_focal([0.8, 0.8], [0.1, None], 0.7, 0.1)
    assert out["label_status"] == "incomplete"
    assert out["needed"] is None
    assert out["needless"] is None
    assert out["ambiguous"] is None
    samples = {
        ("treated", 101): {"branch_gpr": 0.8},
        ("treated", 102): {"branch_gpr": 0.7},
        ("untreated", 101): {"branch_gpr": 0.1},
    }
    assert bc.point_complete_samples(samples, [101, 102]) is False
    samples[("untreated", 102)] = {"branch_gpr": 0.1}
    assert bc.point_complete_samples(samples, [101, 102]) is True


def test_factual_vs_treated_summary_on_fixture():
    rows = [
        {"actual_gpr": 0.5, "treated_gpr": [0.4, 0.6]},
        {"actual_gpr": 0.9, "treated_gpr": [0.1, 0.2]},
        {"actual_gpr": None, "treated_gpr": [0.3, 0.4]},
    ]
    summary = bc.factual_vs_treated_summary(rows)
    assert summary["n_points_compared"] == 2
    assert summary["mean_signed_difference"] == pytest.approx(0.375)
    assert summary["fraction_factual_outside_treated_range"] == pytest.approx(0.5)


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
    assert len(keys) == 8  # 2 points × 2 conditions × 2 seeds
    assert len(set(keys)) == 8
    assert keys.count(first_key) == 1
    assert events_path.read_text(encoding="utf-8") == first_text
    assert events_path.read_text(encoding="utf-8").splitlines() == first_lines
    assert second["n_finished"] == 7
    points = bc.load_jsonl(out1 / "branches.jsonl")
    assert len(points) == 2
    assert {p["i"] for p in points} == {0, 1}
    labels = json.loads((out1 / "oracle_labels.json").read_text(encoding="utf-8"))
    assert isinstance(labels, dict)


def test_resume_at_branch_granularity_missing_one_of_four(tmp_path):
    campaign = tmp_path / "hj4_one"
    write_episode(campaign, events=two_intervention_events(n_corrections=1), goal_pass_rate=1.0)
    out1 = tmp_path / "branches_one"
    first = bc.run_branches(
        campaign_root=campaign,
        out_root=out1,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=3,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
    )
    assert first["n_finished"] == 3
    assert len(bc.load_jsonl(out1 / "branch_runs.jsonl")) == 3
    assert bc.load_jsonl(out1 / "branches.jsonl") == []
    done = {r["key"] for r in bc.load_jsonl(out1 / "branch_runs.jsonl")}
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
    runs = bc.load_jsonl(out1 / "branch_runs.jsonl")
    keys = [r["key"] for r in runs]
    assert len(keys) == 4
    assert len(set(keys)) == 4
    assert second["n_finished"] == 1
    assert second["n_jobs"] == 1
    assert keys[3] not in done
    points = bc.load_jsonl(out1 / "branches.jsonl")
    assert len(points) == 1
    assert points[0]["label_status"] in {"complete", "incomplete"}
    for field in (
        "treated_gpr",
        "untreated_gpr",
        "treated_gpr_local",
        "untreated_gpr_local",
        "delta_mean",
        "delta_crn",
        "delta_local",
        "actual_gpr",
        "delta",
        "needed",
        "needless",
        "ambiguous",
        "harmful",
        "needed_strict",
        "label_status",
        "delta_band_delta",
        "n_later_reviews",
        "correction",
    ):
        assert field in points[0]


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


# ---------------------------------------------------------------------------
# W-15: crashed-branch recovery, planner-cost visibility, campaign budget
# ---------------------------------------------------------------------------


def _base_row(**over) -> dict:
    row = {
        "campaign": "camp",
        "seed": 1,
        "task_id": "copy_hello",
        "i": 0,
        "step": 5,
        "condition": "treated",
        "branch_seed": 101,
        "branch_gpr": 0.9,
        "branch_error_type": None,
        "branch_planner_calls": 4,
        "branch_planner_tokens": 6200,
        "run_id": "camp/fixed_k/1/copy_hello/b_treated_101_i0",
    }
    row.update(over)
    return row


def test_aggregation_last_row_wins_over_crashed_row():
    crashed = _base_row(branch_gpr=None, branch_error_type="crash", branch_steps=None, run_id="crash_run")
    ok = _base_row()
    _, samples = bc.group_branch_samples([crashed, ok])
    sample = samples["camp/1/copy_hello/0"][("treated", 101)]
    assert sample["branch_gpr"] == 0.9
    assert sample["branch_error_type"] is None
    # reversed order: the crash is the last row, so it wins (append-only semantics)
    _, samples2 = bc.group_branch_samples([ok, crashed])
    assert samples2["camp/1/copy_hello/0"][("treated", 101)]["branch_gpr"] is None
    assert bc.is_done_row(ok) is True
    assert bc.is_done_row(crashed) is False


def test_resume_retries_crashed_branch_unless_no_retry_errors(tmp_path):
    campaign = tmp_path / "hj15_retry"
    write_episode(campaign, goal_pass_rate=1.0)
    out1 = tmp_path / "branches_retry"
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
    good_row = bc.load_jsonl(out1 / "branch_runs.jsonl")[0]
    bc.append_jsonl(
        out1 / "branch_runs.jsonl",
        dict(
            good_row,
            branch_gpr=None,
            branch_error_type="crash",
            run_id=good_row["run_id"] + "_crash",
        ),
    )

    # default: the crashed branch is re-dispatched and superseded
    retried = bc.run_branches(
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
    assert retried["n_jobs"] >= 1
    rows = bc.load_jsonl(out1 / "branch_runs.jsonl")
    same_key = [r for r in rows if r["key"] == good_row["key"]]
    assert len(same_key) >= 3  # original + crash + new successful row
    assert bc.is_done_row(same_key[-1]) is True
    assert good_row["key"] in bc.completed_branch_keys(rows)

    # --no-retry-errors: the same crashed row still counts as done (old behaviour)
    out2 = tmp_path / "branches_noretry"
    bc.run_branches(
        campaign_root=campaign,
        out_root=out2,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=1,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
    )
    row2 = bc.load_jsonl(out2 / "branch_runs.jsonl")[0]
    bc.append_jsonl(
        out2 / "branch_runs.jsonl",
        dict(
            row2,
            branch_gpr=None,
            branch_error_type="crash",
            run_id=row2["run_id"] + "_crash",
        ),
    )
    kept = bc.run_branches(
        campaign_root=campaign,
        out_root=out2,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=None,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
        retry_errors=False,
    )
    # the 7 never-run branches are dispatched, but the crashed key is NOT retried
    assert kept["n_jobs"] == 7
    rows2 = bc.load_jsonl(out2 / "branch_runs.jsonl")
    assert sum(1 for r in rows2 if r["key"] == row2["key"]) == 2


def test_resume_never_redispatches_successful_branch(tmp_path):
    campaign = tmp_path / "hj15_over"
    write_episode(campaign, goal_pass_rate=1.0)
    out1 = tmp_path / "branches_over"
    bc.run_branches(
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
    n_rows = len(bc.load_jsonl(out1 / "branch_runs.jsonl"))
    again = bc.run_branches(
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
    assert again["n_jobs"] == 0
    assert again["n_finished"] == 0
    assert len(bc.load_jsonl(out1 / "branch_runs.jsonl")) == n_rows


def test_budget_stops_early_exits_cleanly_and_resume_continues(tmp_path, capsys):
    campaign = tmp_path / "hj15_budget"
    # review_every_k=2 so the branch episode actually reaches a live review and
    # spends >=1 planner call (the default k=5 fixture ends before any review)
    events = []
    for ev in two_intervention_events():
        if ev.event_type == "run_start":
            payload = dict(ev.payload or {})
            policy = dict(payload.get("policy") or {})
            policy["review_every_k"] = 2
            payload["policy"] = policy
            ev = ev.model_copy(update={"payload": payload})
        events.append(ev)
    write_episode(campaign, events=events, goal_pass_rate=1.0)
    out1 = tmp_path / "branches_budget"
    summary = bc.run_branches(
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
        max_planner_calls_total=1,
    )
    assert summary["budget_stopped"] is True
    assert summary["budget_max_planner_calls_total"] == 1
    assert summary["n_finished"] < summary["n_jobs"]
    assert (out1 / "branches.jsonl").is_file()
    assert (out1 / "manifest.json").is_file()
    out_text = capsys.readouterr().out
    assert "PLANNER_BUDGET_STOPPED" in out_text
    assert "PREFLIGHT" in out_text
    rows = bc.load_jsonl(out1 / "branch_runs.jsonl")
    assert rows and all(r["branch_planner_calls"] is not None for r in rows)
    n_rows = len(rows)

    # a resume with the budget unset continues from where the stop happened
    resumed = bc.run_branches(
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
    assert resumed["budget_stopped"] is False
    all_rows = bc.load_jsonl(out1 / "branch_runs.jsonl")
    assert len(all_rows) > n_rows
    assert len(bc.completed_branch_keys(all_rows)) == 8


def test_branch_rows_carry_planner_cost_and_null_when_unavailable(tmp_path):
    campaign = tmp_path / "hj15_cost"
    write_episode(campaign, goal_pass_rate=1.0)
    out1 = tmp_path / "branches_cost"
    bc.run_branches(
        campaign_root=campaign,
        out_root=out1,
        split="train",
        branch_seeds=[101, 102],
        workers=1,
        resume=True,
        limit=2,
        env_kind="mock",
        config={"executor_type": "mock"},
        prices_path=str(PRICES),
    )
    rows = bc.load_jsonl(out1 / "branch_runs.jsonl")
    assert len(rows) == 2
    for row in rows:
        assert "branch_planner_calls" in row
        assert "branch_planner_tokens" in row
        assert row["branch_planner_calls"] is not None and row["branch_planner_calls"] >= 0
        assert row["branch_planner_tokens"] is not None and row["branch_planner_tokens"] >= 0

    # unavailable -> None, never a silent 0: no result, no events
    job = {
        "out_root": str(tmp_path / "nowhere"),
        "run_id": "missing_run",
        "campaign": "camp",
        "seed": 1,
        "task_id": "copy_hello",
        "i": 0,
        "condition": "treated",
        "branch_seed": 101,
        "key": "k",
    }
    point = {"step": 5, "correction": "c"}
    row = bc._row_from_result(job, point, 3, None, "crash")
    assert row["branch_planner_calls"] is None
    assert row["branch_planner_tokens"] is None
    # result source wins when present (result.json carries n_planner_calls / totals)
    calls, tokens = bc.planner_cost_from_result(
        {"n_planner_calls": 7, "totals": {"planner_tokens_total": 999}}
    )
    assert (calls, tokens) == (7, 999)
    ev_calls, ev_tokens = bc.planner_cost_from_events(tmp_path / "nowhere" / "missing_run")
    assert ev_calls is None and ev_tokens is None


def test_planner_cost_from_events_matches_ledger_four_field_tokens(tmp_path):
    usage = {
        "model": "gpt-5.6-luna",
        "provider": "codex",
        "input_tokens": 11,
        "cached_input_tokens": 22,
        "output_tokens": 33,
        "reasoning_output_tokens": 44,
        "n_calls": 3,
    }
    planner_ev = _event(
        event_type="plan", step=0, actor="planner", payload={}, usage=usage
    )
    executor_ev = _event(
        event_type="action",
        step=1,
        actor="executor",
        payload={},
        usage={
            "model": "local",
            "provider": "vllm",
            "input_tokens": 999,
            "cached_input_tokens": 999,
            "output_tokens": 999,
            "reasoning_output_tokens": 999,
            "n_calls": 9,
        },
    )
    run_dir = tmp_path / "four_field"
    run_dir.mkdir()
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as fh:
        fh.write(planner_ev.model_dump_json() + "\n")
        fh.write(executor_ev.model_dump_json() + "\n")
    calls, tokens = bc.planner_cost_from_events(run_dir)
    led = CostLedger(PriceSchedule.load(PRICES))
    led.add("planner", planner_ev.usage)
    assert tokens == led.totals()["planner_tokens_total"]
    assert tokens == 11 + 22 + 33 + 44
    assert calls == 3


def test_planner_cost_from_events_n_calls_zero_stays_zero_missing_defaults_to_one(tmp_path):
    zero_dir = tmp_path / "n_calls_zero"
    zero_dir.mkdir()
    zero_ev = _event(
        event_type="plan",
        step=0,
        actor="planner",
        payload={},
        usage={
            "model": "gpt-5.6-luna",
            "provider": "codex",
            "input_tokens": 1,
            "output_tokens": 1,
            "n_calls": 0,
        },
    )
    (zero_dir / "events.jsonl").write_text(zero_ev.model_dump_json() + "\n", encoding="utf-8")
    calls, _ = bc.planner_cost_from_events(zero_dir)
    assert calls == 0

    missing_dir = tmp_path / "n_calls_missing"
    missing_dir.mkdir()
    raw = {
        "run_id": "camp/fixed_k/1/copy_hello",
        "task_id": "copy_hello",
        "system": "fixed_k",
        "seed": 1,
        "step": 0,
        "ts": "2023-05-18T12:00:00+00:00",
        "actor": "planner",
        "event_type": "plan",
        "payload": {},
        "usage": {
            "model": "gpt-5.6-luna",
            "provider": "codex",
            "input_tokens": 1,
            "output_tokens": 1,
        },
    }
    (missing_dir / "events.jsonl").write_text(json.dumps(raw) + "\n", encoding="utf-8")
    calls, _ = bc.planner_cost_from_events(missing_dir)
    assert calls == 1
