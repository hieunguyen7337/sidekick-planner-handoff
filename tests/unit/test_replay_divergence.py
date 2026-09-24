"""scripts/analysis/replay_divergence.py: the one definition of a divergent key (J10 A1 Amendment 5 §B,
J11 Amendment 2, J12 Amendment 2), on hand-built episode trees whose answers are known by inspection."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.analysis import replay_divergence as rd

REPO = Path(__file__).resolve().parents[2]


def _event(event_type: str, *, step: int = 0, actor: str = "system", payload: dict | None = None,
           task: str = "t1", seed: int = 1, error_type: str | None = None) -> dict:
    """A schema-valid Event (sidekick.protocols.schemas.Event), so sidekick.replay can read the same file."""
    return {"run_id": f"synth/{task}/{seed}", "task_id": task, "system": "prefix_handoff", "seed": seed,
            "step": step, "ts": "2026-09-25T00:00:00Z", "actor": actor, "event_type": event_type,
            "payload": payload or {}, "error_type": error_type}


def _divergence(step: int = 11, **kw) -> dict:
    return _event("error", step=step, payload={"reason": "replay_divergence", "detail": "hash mismatch"},
                  error_type="crash", **kw)


def _episode(root: Path, task: str, seed: int, *, error_type, events: list | None, system: str = "prefix_handoff",
             sub: str = "") -> Path:
    dest = root / sub / system / str(seed) / task if sub else root / system / str(seed) / task
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "result.json").write_text(json.dumps(
        {"task_id": task, "seed": seed, "system": system, "error_type": error_type, "goal_pass_rate": 0.0}) + "\n",
        encoding="utf-8")
    if events is not None:
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return dest


def test_a_crash_whose_last_attempt_diverged_is_divergent_and_nothing_else_is(tmp_path: Path):
    arm = tmp_path / "arm"
    # divergent: crash + the error event in the only attempt.
    _episode(arm, "t1", 1, error_type="crash", events=[_event("run_start"), _divergence()])
    # an ordinary crash (another reason): not divergent.
    _episode(arm, "t2", 1, error_type="crash", events=[
        _event("run_start"), _event("error", payload={"reason": "replay_error"}, error_type="crash")])
    # a crash with no events file, and one whose file has no run_start: not divergent.
    _episode(arm, "t3", 1, error_type="crash", events=None)
    _episode(arm, "t4", 1, error_type="crash", events=[_divergence()])
    # a scored (non-crash) episode with the event: not divergent (error_type decides first).
    _episode(arm, "t5", 1, error_type="limit", events=[_event("run_start"), _divergence()])
    # an error event of another type that carries the reason: not divergent.
    _episode(arm, "t6", 1, error_type="crash", events=[
        _event("run_start"), _event("report", payload={"reason": "replay_divergence"})])
    _episode(arm, "t7", 2, error_type="crash", events=[_event("run_start", seed=2), _divergence(seed=2)])
    assert rd.divergent_keys(arm) == [("t1", 1), ("t7", 2)]
    assert rd.divergent_keys(tmp_path / "absent") == []


def test_last_attempt_rule_matches_sidekick_replay(tmp_path: Path):
    """Case (f): a divergence in an EARLIER attempt followed by a successful last attempt is not divergent;
    nor is it when the last attempt crashed for another reason. A divergence in the last attempt is."""
    arm = tmp_path / "arm"
    earlier = [_event("run_start"), _divergence()]
    ok_last = [_event("run_start"), _event("report", step=11, payload={"handoff_occurred": True}),
               _event("evaluate", step=12, actor="environment")]
    other_crash_last = [_event("run_start"), _event("error", payload={"reason": "replay_error"}, error_type="crash")]
    d1 = _episode(arm, "ok_after", 1, error_type=None, events=earlier + ok_last)
    d2 = _episode(arm, "other_after", 1, error_type="crash", events=earlier + other_crash_last)
    d3 = _episode(arm, "div_after_ok", 1, error_type="crash", events=ok_last + earlier)
    # A trailing truncated line is skipped, as EventLog.read skips it.
    with (d3 / "events.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"event_type": "err')
    assert rd.divergent_keys(arm) == [("div_after_ok", 1)]
    assert [rd.last_attempt_diverged(d / "events.jsonl") for d in (d1, d2, d3)] == [False, False, True]
    # Same slice as sidekick.replay._events_of_last_attempt (events from the last run_start on).
    from sidekick.replay import _events_of_last_attempt

    for d in (d1, d2, d3):
        ours = rd.events_of_last_attempt(d / "events.jsonl")
        theirs = [e.model_dump(mode="json") for e in _events_of_last_attempt(d / "events.jsonl")]
        assert [(e["event_type"], e["step"], e.get("payload")) for e in ours] == [
            (e["event_type"], e["step"], e["payload"]) for e in theirs]
    no_start = _episode(arm, "no_start", 1, error_type="crash", events=[_divergence()])
    assert rd.events_of_last_attempt(no_start / "events.jsonl") == [] == _events_of_last_attempt(
        no_start / "events.jsonl")


def test_the_first_result_per_key_wins_as_in_load_arm_tree(tmp_path: Path):
    arm = tmp_path / "arm"
    # sorted rglob: "a/..." before "b/...". The first copy is scored, so the key is not divergent.
    _episode(arm, "t1", 1, error_type=None, events=[_event("run_start")], sub="a")
    _episode(arm, "t1", 1, error_type="crash", events=[_event("run_start"), _divergence()], sub="b")
    assert rd.divergent_keys(arm) == []
    _episode(arm, "t2", 1, error_type="crash", events=[_event("run_start"), _divergence()], sub="a")
    _episode(arm, "t2", 1, error_type=None, events=[_event("run_start")], sub="b")
    assert rd.divergent_keys(arm) == [("t2", 1)]


def test_contrast_exclusion_union_and_cap_by_hand():
    a = [("t1", 1), ("t2", 1)]
    b = [("t2", 1), ("t3", 2)]
    # A replay arm against a non-replay arm: its own keys. Two replay arms: the union (3, not 4).
    assert rd.contrast_exclusion({"m11": a}, "adv", "m11") == ([("t1", 1), ("t2", 1)], "ok")
    assert rd.contrast_exclusion({"m11": a, "m9": b}, "m11", "m9") == ([("t1", 1), ("t2", 1), ("t3", 2)], "ok")
    assert rd.contrast_exclusion({"m11": a}, "adv", "sft") == ([], "ok")
    sixteen = [(f"t{i:02d}", 1) for i in range(16)]
    assert rd.contrast_exclusion({"x": sixteen}, "x", "y") == (sixteen, "ok")  # 16 = 5 % of 336: still read
    seventeen = sixteen + [("t99", 2)]
    assert rd.contrast_exclusion({"x": seventeen}, "x", "y")[1] == "over_cap"
    # 9 + 9 disjoint: each arm under the cap, the union (18) over it.
    nine_a = [(f"a{i}", 1) for i in range(9)]
    nine_b = [(f"b{i}", 1) for i in range(9)]
    assert rd.contrast_exclusion({"x": nine_a, "y": nine_b}, "x", "y")[1] == "over_cap"
    assert rd.DIVERGENCE_CAP == 16 and rd.key_label(("t1", 2)) == "2/t1"


def test_import_is_pure_no_pydantic():
    code = "import sys; import scripts.analysis.replay_divergence; print('pydantic' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, timeout=120,
                         env={"PYTHONPATH": f"{REPO}:{REPO / 'src'}", "PATH": "/usr/bin:/bin"})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False"
