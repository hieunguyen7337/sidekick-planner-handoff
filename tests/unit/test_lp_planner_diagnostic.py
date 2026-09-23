"""scripts/analysis/lp_planner_diagnostic.py on a constructed tree with known counts."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.analysis import lp_planner_diagnostic as diag


def _ev(event_type, actor="planner", step=0, **payload):
    return {"event_type": event_type, "actor": actor, "step": step, "payload": payload}


def _write(root: Path, camp: str, seed: str, task: str, events) -> None:
    d = root / camp / "planner_alone" / seed / task
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _solved():
    return [
        _ev("run_start", "system", limits={}, policy={}),
        _ev("action", step=1, kind="CODE", code="p = apis.supervisor.show_account_passwords()"),
        _ev("observation", "environment", step=1, kind="CODE", text="[{...}]"),
        _ev("action", step=2, kind="COMPLETE"),
        _ev("run_end", "system", step=2, error_type=None, goal_pass_rate=1.0, steps=2),
    ]


def _stalled():
    evs = [
        _ev("run_start", "system", limits={}, policy={}),
        _ev("action", step=1, kind="CODE", code='apis.phone.login(username="user", password="password")'),
        _ev("observation", "environment", step=1, kind="CODE", text="Execution failed. Traceback: 401"),
    ]
    for s in range(2, 12):
        evs.append(_ev("action", step=s, kind="REPORT"))
        evs.append(_ev("report", "executor", step=s, message="Please verify the credentials."))
    evs.append(_ev("run_end", "system", step=40, error_type="limit", goal_pass_rate=0.2, steps=40))
    return evs


def test_counts_on_a_constructed_ceiling(tmp_path):
    _write(tmp_path, "c", "1", "t_solved", _solved())
    # A retried episode: only the attempt after the last run_start counts.
    _write(tmp_path, "c", "2", "t_stalled", _solved()[:2] + _stalled())
    _write(tmp_path, "c", "3", "t_other_seed", _solved())  # seed 3 is not read
    s = diag.summarise(str(tmp_path), "c", outcomes=True)
    assert s["n"] == 2
    assert (s["n_cred_lookup"], s["n_placeholder"], s["n_complete"], s["n_tail_no_code"]) == (1, 1, 1, 1)
    assert s["n_repeat_ge5"] == 1           # ten identical REPORTs
    assert s["code_fail_rate"] == 0.5       # one of two CODE observations failed
    assert s["error_type"] == {"None": 1, "limit": 1}
    assert s["goal_pass_mean"] == 0.6
    assert s["action_share"]["planner:REPORT"] == round(10 / 13, 3)
    samples = diag.stall_samples(str(tmp_path), "c")
    assert [x["episode"] for x in samples] == ["2/t_stalled"]
    assert samples[0]["last_messages"] == ["Please verify the credentials."] * 2


def test_masked_campaign_prints_no_outcome(tmp_path):
    _write(tmp_path, "c", "1", "t", _solved())
    s = diag.summarise(str(tmp_path), "c", outcomes=False)
    assert s["n_cred_lookup"] == 1 and s["outcomes_shown"] is False
    assert not {"goal_pass_mean", "error_type", "steps_mean"} & set(s)


def test_the_p27_ceiling_is_masked_in_the_registered_list():
    shown = {label: outcomes for label, _, outcomes in diag.CAMPAIGNS}
    assert shown["P27_C"] is False
    assert all(v for k, v in shown.items() if k != "P27_C")


def test_placeholder_heuristic():
    hit = diag.PLACEHOLDER.search
    assert hit('apis.phone.login(username="valid_username", password="valid_password")')
    assert hit("apis.spotify.login(username='user', password='password')")
    assert not hit("apis.phone.login(username=p['phone']['username'], password=p['phone']['password'])")
    assert not hit('apis.venmo.login(username="joe@x.com", password="Zk5!qP2r")')
