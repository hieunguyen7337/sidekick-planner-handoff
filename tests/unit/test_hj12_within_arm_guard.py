"""Within-arm spend projection and smoke takeover FATAL in hj12_live.pbs.

Invokes HJ12_GUARD_SELFTEST cases. No live planner, no GPU, no writes under
/scratch/n12194778/sidekick/results/.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
PBS = REPO / "scripts/pbs/hj12_live.pbs"
N_FULL_TASKS = 57
N_FULL_SEEDS = 2
SAFETY = 1.2
MARKER = "Execution failed. Traceback:"


def _write_run(root: Path, *, system: str, task_id: str, live_calls: int, steps: int, events: list[dict] | None = None) -> None:
    dest = root / system / "1" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": f"synth/{system}/1/{task_id}",
        "task_id": task_id,
        "system": system,
        "seed": 1,
        "success": False,
        "steps": steps,
        "n_planner_calls": live_calls,
        "totals": {"planner_calls_total": live_calls, "planner_tokens_total": 0},
    }
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    if events is not None:
        (dest / "events.jsonl").write_text(
            "".join(json.dumps(ev) + "\n" for ev in events),
            encoding="utf-8",
        )


def _run_case(case: str, out_root: Path, cid: str, extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HJ12_GUARD_SELFTEST"] = "1"
    env["GUARD_CASE"] = case
    env["GUARD_OUT"] = str(out_root)
    env["GUARD_CID"] = cid
    env["PY"] = sys.executable
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    if extra:
        env.update(extra)
    return subprocess.run(
        ["timeout", "60", "bash", str(PBS)],
        cwd=str(REPO),
        env=env,
        text=True,
        capture_output=True,
    )


def _smoke_tree(tmp_path: Path, cid: str, *, live_each: int, steps: int, n: int = 3, system: str = "fixed_k", events=None) -> Path:
    root = tmp_path / cid
    for i in range(n):
        _write_run(
            root,
            system=system,
            task_id=f"t{i}",
            live_calls=live_each,
            steps=steps,
            events=events,
        )
    return root


def _fixed_k_cfg(tmp_path: Path, k: int = 10) -> str:
    path = tmp_path / f"fixed_k_{k}.yaml"
    path.write_text(f"fixed_k: {k}\n", encoding="utf-8")
    return str(path)


def test_project_over_ceiling_fatals_before_full_run(tmp_path):
    cid = "smoke_over"
    _smoke_tree(tmp_path, cid, live_each=41, steps=40)
    proc = _run_case("project_over", tmp_path, cid, extra={"GUARD_STEM": "hj12_planner_handoff"})
    live = 41 * 3
    cpe = live / 3
    proj = math.ceil(cpe * N_FULL_TASKS * N_FULL_SEEDS * SAFETY)
    project_line = (
        f"[hj12] project hj12_planner_handoff: smoke_key=ledger_totals.planner_calls_total "
        f"smoke_live={live} n_episodes=3 calls_per_episode={cpe:.2f} n_full_tasks={N_FULL_TASKS} "
        f"n_seeds={N_FULL_SEEDS} safety={SAFETY} projection={proj} running=0 ceiling=3780"
    )
    fatal_line = (
        f"[hj12] FATAL: arm hj12_planner_handoff projected {proj} live planner calls "
        f"({cpe:.2f} calls/ep from smoke) plus running 0 exceed MAX_PLANNER_CALLS=3780; "
        "not launching the full run"
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert project_line in out, out
    assert fatal_line in out, out
    assert "UNREACHABLE" not in out


def test_project_under_ceiling_prints_and_continues(tmp_path):
    cid = "smoke_ok"
    _smoke_tree(tmp_path, cid, live_each=5, steps=12)
    proc = _run_case("project_ok", tmp_path, cid, extra={"GUARD_STEM": "hj12_takeover_fixed_k_10"})
    live = 5 * 3
    cpe = live / 3
    proj = math.ceil(cpe * N_FULL_TASKS * N_FULL_SEEDS * SAFETY)
    project_line = (
        f"[hj12] project hj12_takeover_fixed_k_10: smoke_key=ledger_totals.planner_calls_total "
        f"smoke_live={live} n_episodes=3 calls_per_episode={cpe:.2f} n_full_tasks={N_FULL_TASKS} "
        f"n_seeds={N_FULL_SEEDS} safety={SAFETY} projection={proj} running=0 ceiling=3780"
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert project_line in out, out
    assert "project_ok reached" in out
    assert "FATAL: arm" not in out


def test_takeover_smoke_fatals_when_steps_reach_k(tmp_path):
    cid = "tk_fatal"
    _smoke_tree(tmp_path, cid, live_each=4, steps=10, events=[{"event_type": "action", "actor": "executor"}])
    cfg = _fixed_k_cfg(tmp_path, 10)
    proc = _run_case(
        "takeover_smoke_fatal",
        tmp_path,
        cid,
        extra={"GUARD_SYSTEM": "fixed_k", "GUARD_CFG": cfg},
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert (
        "[hj12] FATAL: takeover arm hj12_takeover_fixed_k_10 has 0 planner-authored action events on smoke "
        "and at least one episode could have triggered the fixed_k steps>=k gate; ran the advise path; "
        "not launching the full run"
    ) in out, out
    assert "UNREACHABLE" not in out


def test_takeover_smoke_warns_when_no_episode_reached_k(tmp_path):
    cid = "tk_warn"
    _smoke_tree(tmp_path, cid, live_each=1, steps=4, events=[{"event_type": "action", "actor": "executor"}])
    cfg = _fixed_k_cfg(tmp_path, 10)
    proc = _run_case(
        "takeover_smoke_uninformative",
        tmp_path,
        cid,
        extra={"GUARD_SYSTEM": "fixed_k", "GUARD_CFG": cfg},
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert (
        "[hj12] WARN: takeover arm hj12_takeover_fixed_k_10 has 0 planner-authored action events on smoke "
        "— smoke was uninformative (no episode reached the fixed_k steps>=k gate)"
    ) in out, out
    assert "takeover_smoke_uninformative reached" in out


def test_exception_smoke_fatals_when_marker_present(tmp_path):
    cid = "ex_fatal"
    events = [
        {"event_type": "observation", "payload": {"text": f"{MARKER}\nboom"}},
        {"event_type": "action", "actor": "executor"},
    ]
    _smoke_tree(tmp_path, cid, live_each=2, steps=3, system="router_seq", events=events)
    proc = _run_case(
        "takeover_smoke_exception_fatal",
        tmp_path,
        cid,
        extra={"GUARD_SYSTEM": "router_seq", "GUARD_CFG": ""},
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 1, out
    assert (
        "[hj12] FATAL: takeover arm hj12_takeover_exception has 0 planner-authored action events on smoke "
        "and at least one episode could have triggered the exception marker gate; ran the advise path; "
        "not launching the full run"
    ) in out, out


def test_exception_smoke_warns_without_marker(tmp_path):
    cid = "ex_warn"
    events = [
        {"event_type": "observation", "payload": {"text": "ok"}},
        {"event_type": "action", "actor": "executor"},
    ]
    _smoke_tree(tmp_path, cid, live_each=2, steps=20, system="router_seq", events=events)
    proc = _run_case(
        "takeover_smoke_exception_uninformative",
        tmp_path,
        cid,
        extra={"GUARD_SYSTEM": "router_seq", "GUARD_CFG": ""},
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert (
        "[hj12] WARN: takeover arm hj12_takeover_exception has 0 planner-authored action events on smoke "
        "— smoke was uninformative (no episode reached the exception marker gate)"
    ) in out, out
    assert "takeover_smoke_exception_uninformative reached" in out
