"""Offline tests for resumable, budgeted, depth-stratified state probes."""
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
from sidekick.replay import replay_prefix  # noqa: E402
import state_probe as sp  # noqa: E402


class StubProbeEnv(MockEnv):
    """Offline AppWorld-shaped stub for state-probe lifecycle tests."""

    def __init__(self, experiment_name: str = "", api_docs_prompt: str = "stub_api() -> str"):
        super().__init__()
        self.experiment_name = experiment_name
        self._stub_api_docs_prompt = api_docs_prompt

    @property
    def instruction(self) -> str:
        return "Use the available AppWorld API to complete this task."

    @property
    def api_docs_prompt(self) -> str:
        return self._stub_api_docs_prompt


@pytest.fixture(autouse=True)
def stub_appworld(monkeypatch):
    monkeypatch.setattr(sp, "AppWorldEnv", StubProbeEnv)


class StubExecutor:
    def __init__(self, model: str = "stub") -> None:
        self.model = model
        self.lora_name = None
        self.calls = 0

    def complete(self, messages, **kw):
        self.calls += 1
        return "```python\npass\n```", None


def test_replay_prefix_requires_env():
    with pytest.raises(TypeError):
        replay_prefix("unused-events.jsonl", 1)


def test_probe_rejects_mock_env():
    with pytest.raises(AssertionError, match="AppWorldEnv.*MockEnv"):
        sp.assert_probe_environment(MockEnv())


def test_probe_rejects_empty_api_docs():
    with pytest.raises(AssertionError, match="api_docs_prompt"):
        sp.assert_probe_environment(StubProbeEnv(api_docs_prompt=""))


def test_no_api_gold_is_excluded_from_agreement():
    world = StubProbeEnv()
    world.reset("task-1", 1)
    pairs = [
        (
            ExecutorAction(
                kind="CODE", code='print({"credential_count": len(passwords)})'
            ),
            _event("run-1", "task-1", 1, "observation", {"text": "ok"}),
        ),
        (
            ExecutorAction(kind="CODE", code="pass"),
            _event("run-1", "task-1", 2, "observation", {"text": "ok"}),
        ),
    ]
    try:
        rec = sp.probe_step(
            StubExecutor(),
            world,
            pairs,
            0,
            instruction=world.instruction,
            api_docs=world.api_docs_prompt,
        )
    finally:
        world.close()

    bucket = sp.empty_counts()
    sp.record(bucket, rec)
    summary = sp.finalize({"overall": bucket})["overall"]
    assert rec["gold_api_ids"] == []
    assert rec["pred_api_ids"] == []
    assert rec["agreement_defined"] is False
    assert rec["agreement"] is False
    assert summary["agreement"] == 0
    assert summary["n_scorable"] == 0
    assert summary["n_gold_no_api"] == 1


def _event(
    run_id: str,
    task_id: str,
    step: int,
    event_type: str,
    payload: dict | None = None,
) -> Event:
    return Event(
        run_id=run_id,
        task_id=task_id,
        system="planner_alone",
        seed=1,
        step=step,
        ts="2026-09-16T00:00:00+00:00",
        actor="planner" if event_type == "action" else "system",
        event_type=event_type,
        payload=payload or {},
    )


def _write_campaign(tmp_path: Path, n_pairs: int = 4) -> Path:
    root = tmp_path / "campaign"
    run_dir = root / "planner_alone" / "1" / "task-1"
    run_dir.mkdir(parents=True)
    events = [_event("run-1", "task-1", 0, "run_start")]
    for step in range(1, n_pairs + 1):
        events.append(
            _event(
                "run-1",
                "task-1",
                step,
                "action",
                {"kind": "CODE", "code": "pass", "raw_output": "pass"},
            )
        )
        events.append(
            _event(
                "run-1", "task-1", step, "observation", {"text": "ok"}
            )
        )
    (run_dir / "events.jsonl").write_text(
        "".join(event.model_dump_json() + "\n" for event in events)
    )
    (run_dir / "result.json").write_text(json.dumps({"success": True}))
    return root


def _points_by_bucket(points: list[dict]) -> dict[str, int]:
    counts = {bucket: 0 for bucket in sp.DEPTH_BUCKETS}
    for point in points:
        counts[sp.bucket_for(point["step_index"])] += 1
    return counts


def test_partial_jsonl_resumes_by_run_and_step(tmp_path):
    campaign = _write_campaign(tmp_path)
    out = tmp_path / "probe.json"

    first_executor = StubExecutor("granite")
    first = sp.run_probe(
        str(campaign), "planner_alone", first_executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )
    assert first["n_completed"] == 1
    assert first_executor.calls == 1
    partial = Path(f"{out}.partial.jsonl")
    assert len(partial.read_text().splitlines()) == 1

    resumed_executor = StubExecutor("qwen")
    resumed = sp.run_probe(
        str(campaign), "planner_alone", resumed_executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )
    assert resumed_executor.calls == 0
    assert resumed["n_completed"] == 1
    assert resumed["steps"][0]["run_id"] == "run-1"
    assert resumed["steps"][0]["step_index"] == resumed["sampled_points"][0]["step"]


def test_resume_discards_records_from_old_schema(tmp_path, capsys):
    campaign = _write_campaign(tmp_path)
    out = tmp_path / "old-schema.json"
    partial = Path(f"{out}.partial.jsonl")
    partial.write_text(
        json.dumps({"run_id": "run-1", "step_index": 1, "schema_version": 1}) + "\n"
    )

    executor = StubExecutor()
    report = sp.run_probe(
        str(campaign), "planner_alone", executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )

    assert executor.calls == 1
    assert report["n_completed"] == 1
    assert report["schema_version"] == sp.PROBE_SCHEMA_VERSION
    assert report["steps"][0]["schema_version"] == sp.PROBE_SCHEMA_VERSION
    assert "schema_version" in json.loads(partial.read_text().splitlines()[-1])
    assert "discarded 1 partial record" in capsys.readouterr().err


def test_resume_discards_records_with_no_schema_version(tmp_path, capsys):
    campaign = _write_campaign(tmp_path)
    out = tmp_path / "missing-schema.json"
    partial = Path(f"{out}.partial.jsonl")
    partial.write_text(json.dumps({"run_id": "run-1", "step_index": 1}) + "\n")

    executor = StubExecutor()
    report = sp.run_probe(
        str(campaign), "planner_alone", executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )

    assert executor.calls == 1
    assert report["n_completed"] == 1
    assert report["steps"][0]["schema_version"] == sp.PROBE_SCHEMA_VERSION
    assert "discarded 1 partial record" in capsys.readouterr().err


def test_resume_keeps_current_schema_records(tmp_path):
    campaign = _write_campaign(tmp_path)
    out = tmp_path / "current-schema.json"

    first_executor = StubExecutor("granite")
    first = sp.run_probe(
        str(campaign), "planner_alone", first_executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )
    assert first["steps"][0]["schema_version"] == sp.PROBE_SCHEMA_VERSION

    resumed_executor = StubExecutor("qwen")
    resumed = sp.run_probe(
        str(campaign), "planner_alone", resumed_executor, 0, 0,
        out_path=out, max_points=1, seed=0
    )

    assert resumed_executor.calls == 0
    assert resumed["n_completed"] == 1
    assert resumed["steps"][0]["schema_version"] == sp.PROBE_SCHEMA_VERSION


def test_time_budget_writes_clean_partial_report(tmp_path, monkeypatch):
    campaign = _write_campaign(tmp_path, n_pairs=4)
    out = tmp_path / "budget.json"
    ticks = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr(sp.time, "monotonic", lambda: next(ticks))

    executor = StubExecutor()
    report = sp.run_probe(
        str(campaign), "planner_alone", executor, 0, 0,
        out_path=out, time_budget_s=1, seed=0
    )

    assert report["budget_exhausted"] is True
    assert report["n_completed"] == 1
    assert report["n_completed"] < report["n_planned"]
    assert json.loads(out.read_text())["budget_exhausted"] is True
    assert executor.calls == 1


def test_same_seed_and_max_points_pair_models_on_same_points(tmp_path):
    campaign = _write_campaign(tmp_path, n_pairs=15)
    granite = sp.run_probe(
        str(campaign), "planner_alone", StubExecutor("granite"), 0, 0,
        out_path=tmp_path / "granite.json", max_points=6, seed=17
    )
    qwen = sp.run_probe(
        str(campaign), "planner_alone", StubExecutor("qwen"), 0, 0,
        out_path=tmp_path / "qwen.json", max_points=6, seed=17
    )

    assert granite["sampled_points"] == qwen["sampled_points"]
    assert granite["n_planned"] == granite["n_completed"] == 6
    assert _points_by_bucket(granite["steps"]) == {"1-5": 2, "6-10": 2, "11+": 2}


def test_depth_sampling_redistributes_short_bucket():
    points = [
        {"run_id": f"early-{i}", "step_index": i + 1, "order": i}
        for i in range(5)
    ]
    points.extend(
        {"run_id": "middle", "step_index": 6, "order": 5} for _ in range(1)
    )
    points.extend(
        {"run_id": f"late-{i}", "step_index": i + 11, "order": i + 6}
        for i in range(5)
    )

    selected = sp.select_sampled_points(points, max_points=6, seed=0)
    counts = _points_by_bucket(selected)
    assert len(selected) == 6
    assert counts["6-10"] == 1
    assert counts["1-5"] + counts["11+"] == 5
    assert abs(counts["1-5"] - counts["11+"]) <= 1
