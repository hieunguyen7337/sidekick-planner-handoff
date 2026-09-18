"""Unit tests for the A7 value-function fitter (fit_value_function.py)."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from fit_value_function import (  # noqa: E402
    bootstrap_auroc_ci,
    fit_all_value,
    knn_ceiling,
    outcome_label,
    split_by_task,
    step_prior_baseline,
    step_states_from_events,
    value_xy,
)
from sidekick.protocols.schemas import Event  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402
from sidekick.replay import _events_of_last_attempt  # noqa: E402


def _ev(step, etype, payload=None, **kw):
    return Event(
        run_id="r", task_id=kw.pop("task_id", "t1"), system=kw.pop("system", "fixed_k"),
        seed=kw.pop("seed", 1), step=step, ts="2023-05-18T12:00:00+00:00",
        actor=kw.pop("actor", "executor"), event_type=etype, payload=payload or {},
    )


def _episode_events(success: bool, n_steps: int = 3) -> list[Event]:
    events = [_ev(0, "run_start", actor="system")]
    for s in range(1, n_steps + 1):
        code = "import os\n" if success else "raise RuntimeError('boom')\n"
        events.append(_ev(s, "action", {"kind": "CODE", "code": code}))
        events.append(
            _ev(s, "observation", {"text": "ok" if success else
                                   "Traceback (most recent call last):\n"
                                   "RuntimeError: boom",
                                   "done": s == n_steps},
                actor="environment", error_type=None if success else "exec_error")
        )
    events.append(_ev(n_steps, "evaluate", {"success": success}, actor="verifier"))
    return events


def test_known_answer_errors_predict_failure():
    """Right answer known by construction: error-run episodes vs clean ones."""
    rows: list[dict] = []
    for lab in (1, 1, 0, 0):
        events = _episode_events(success=bool(lab))
        got, dropped, _n_measured = step_states_from_events(events, lab)
        assert dropped == 0
        assert got, "no states reconstructed"
        rows.extend(got)
    assert all(r["p_ask"] is None for r in rows), "p_ask must stay None, not 0.0"
    X, y = value_xy(rows)
    train, dev = rows[::2], rows[1::2]
    verifier, report, dev_probs = fit_all_value(train, dev)
    assert 0.0 <= report["dev"]["auroc"] <= 1.0
    # Invariants of the temperature fit.
    assert report["dev_nll_after"] <= report["dev_nll_before"] + 1e-12
    assert report["dev"]["auroc"] == report["dev"]["auroc_before_temperature"]
    # Direction: error states should score lower than clean states.
    assert verifier.weights["last_obs_is_error"] < 0.0


def test_split_by_task_never_mixes():
    ids = [f"task{i:03d}" for i in range(50)]
    mapping = split_by_task(ids)
    assert len(mapping) == len(set(ids))
    assert sum(1 for v in mapping.values() if v == "dev") >= 1
    assert sum(1 for v in mapping.values() if v == "train") >= 1
    # Deterministic
    assert split_by_task(ids) == mapping


def test_appended_run_start_keeps_last_segment(tmp_path: Path):
    """Two attempts concatenated in one file: only the last segment counts."""
    path = tmp_path / "events.jsonl"
    first = _episode_events(success=True, n_steps=1)
    second = _episode_events(success=False, n_steps=2)
    with open(path, "w", encoding="utf-8") as fh:
        for ev in first + second:
            fh.write(ev.model_dump_json() + "\n")
    events = _events_of_last_attempt(path)
    assert events[0].event_type == "run_start"
    rows, dropped, _n_measured = step_states_from_events(events, 0)
    assert dropped == 0
    # Second attempt only: 2 steps, not 3, and error-labelled state text.
    assert len(rows) == 2
    assert all("Traceback" in r["transcript"] for r in rows)


def test_outcome_label_success_bool_and_fallback(tmp_path: Path):
    p = tmp_path / "r.json"
    p.write_text(json.dumps({"success": True, "goal_pass_rate": 0.5}))
    assert outcome_label(p) == (1, "success_bool")
    p.write_text(json.dumps({"goal_pass_rate": 0.25}))
    lab, src = outcome_label(p)
    assert (lab, src) == (0, "goal_pass_rate_eq_1")
    p.write_text(json.dumps({"nothing": 1}))
    assert outcome_label(p)[0] is None
    assert outcome_label(tmp_path / "missing.json")[0] is None


def test_bootstrap_auroc_ci_perfect_separation():
    episodes = {
        f"e{i}": ([1.0] * 2, [1, 1]) if i % 2 == 0 else ([0.0] * 2, [0, 0])
        for i in range(20)
    }
    out = bootstrap_auroc_ci(episodes, n_boot=500, seed=1)
    assert out["auroc"] == 1.0
    assert out["ci_low"] == 1.0 and out["ci_high"] == 1.0


def test_step_prior_baseline_and_knn_ceiling():
    rows_pos, rows_neg = [], []
    for lab in (1, 0):
        events = _episode_events(success=bool(lab))
        got, _dropped, _n_measured = step_states_from_events(events, lab)
        for r in got:
            r["task_id"] = "pos" if lab else "neg"
        (rows_pos if lab else rows_neg).extend(got)
    train = rows_pos + rows_neg
    prior = step_prior_baseline(train, train)
    assert prior is not None and math.isfinite(prior)
    X, y = value_xy(train)
    tasks = [r["task_id"] for r in train]
    ceiling = knn_ceiling(X, y, tasks, X, y, tasks, k=3)
    assert ceiling is None or 0.0 <= ceiling <= 1.0


def test_action_without_parse_is_dropped_not_default():
    events = [
        _ev(0, "run_start", actor="system"),
        _ev(1, "action", {"kind": "BOGUS"}),
        _ev(1, "observation", {"text": "x"}, actor="environment"),
    ]
    rows, dropped, _n_measured = step_states_from_events(events, 1)
    assert rows == [] and dropped == 0
