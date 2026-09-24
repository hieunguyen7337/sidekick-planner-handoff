"""scripts/analysis/dev_planning_controls.py on a hand-built campaign tree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "analysis"))
import dev_planning_controls as dpc  # noqa: E402


def _ev(event_type: str, *, actor: str = "system", step: int = 0, payload: dict | None = None,
        error_type: str | None = None) -> dict:
    return {"event_type": event_type, "actor": actor, "step": step, "payload": payload or {}, "error_type": error_type}


def _plan(packet_task: str, source: str | None, steps: int = 1) -> dict:
    payload = {"packet": {"task_id": packet_task, "plan_steps": [{"index": 1}] * steps}}
    if source is not None:
        payload["packet_task_source"] = source
    return _ev("plan", actor="planner", payload=payload)


def _episode(root: Path, task_id: str, events: list[dict], seed: int = 1) -> None:
    path = root / "sft_plan" / str(seed) / task_id / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


START = _ev("run_start")
MAP = {"a_1": "b_1", "b_1": "c_1", "c_1": "a_1", "d_1": "e_1", "e_1": "f_1", "f_1": "d_1"}


def _tree(tmp_path: Path) -> Path:
    root = tmp_path / "cid"
    _episode(root, "a_1", [START, _plan("b_1", "b_1")])                      # remapped as planned
    _episode(root, "b_1", [START, _plan("c_1", None)])                       # source not recorded
    _episode(root, "c_1", [START, _plan("c_1", "a_1")])                      # packet is not the source's
    _episode(root, "d_1", [START, _ev("error", actor="planner", error_type="parse_error")])  # plan failed
    _episode(root, "e_1", [START, _plan("f_1", "f_1", steps=0),              # empty, remapped, one ask
                           _ev("ask", actor="executor", step=3), _ev("intervention", actor="planner", step=3)])
    # A retried episode: only the second attempt counts, and it wrote no plan and no error.
    _episode(root, "f_1", [START, _plan("d_1", "d_1"), START])
    return root


def test_counts_by_hand(tmp_path: Path):
    got = dpc.campaign_counts(_tree(tmp_path), MAP)
    assert got == {
        "root": str(tmp_path / "cid"),
        "n_episodes": 6,
        "n_plan": 4,               # a, b, c, e
        "n_plan_empty": 1,         # e
        "n_no_plan": 2,            # d, f (f's plan is in the discarded first attempt)
        "n_plan_failed_parse_error": 1,  # d
        "n_remap_ok": 2,           # a, e
        "n_remap_unrecorded": 1,   # b
        "n_remap_wrong": 1,        # c
        "n_ask_events": 1,
        "n_intervention_events": 1,
    }


def test_without_a_map_no_remap_counts(tmp_path: Path):
    got = dpc.campaign_counts(_tree(tmp_path))
    assert not any(k.startswith("n_remap") for k in got)
    assert (got["n_plan"], got["n_no_plan"]) == (4, 2)


def test_an_empty_campaign_reports_zeros_not_missing_keys(tmp_path: Path):
    got = dpc.campaign_counts(tmp_path / "nothing", {"a_1": "b_1"})
    assert got == {"root": str(tmp_path / "nothing"), "n_episodes": 0, "n_plan": 0, "n_no_plan": 0,
                   "n_plan_empty": 0, "n_ask_events": 0, "n_intervention_events": 0,
                   "n_remap_ok": 0, "n_remap_unrecorded": 0, "n_remap_wrong": 0}


def test_last_attempt_events_skips_a_truncated_line(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(START) + "\n" + json.dumps(_plan("x_1", None)) + "\n{\"trunc", encoding="utf-8")
    assert [e["event_type"] for e in dpc.last_attempt_events(path)] == ["plan"]


def test_main_writes_the_same_json_it_prints(tmp_path: Path, capsys):
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"map": MAP}), encoding="utf-8")
    out = tmp_path / "counts.json"
    assert dpc.main(["--campaign-root", str(_tree(tmp_path)), "--map", str(map_path), "--out", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(out.read_text(encoding="utf-8"))
    assert printed["n_remap_ok"] == 2
