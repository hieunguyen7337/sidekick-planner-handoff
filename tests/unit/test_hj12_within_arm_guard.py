"""Within-arm spend projection and smoke takeover FATAL in hj12_live.pbs, and the
replay-source completeness refusal in hj12_prefix.pbs.

Invokes HJ12_GUARD_SELFTEST cases. No live planner, no GPU, no writes under
/scratch/n12194778/sidekick/results/ (the real-source cases only read it).
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
PBS = REPO / "scripts/pbs/hj12_live.pbs"
PREFIX_PBS = REPO / "scripts/pbs/hj12_prefix.pbs"
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


# ---- hj12_prefix.pbs: every selected prefix_handoff arm's replay source must be complete ----------

SOURCE_TASKS = 57  # N_FULL_TASKS in hj12_prefix.pbs
CAP81_SOURCE = Path("/scratch/n12194778/sidekick/results/hj13_planner_alone_cap81_20260923")


def _source_tree(root: Path, *, seeds=(1, 2), n: int = SOURCE_TASKS, system: str = "planner_alone") -> Path:
    for seed in seeds:
        for i in range(n):
            _write_source_row(root, system=system, seed=seed, task_id=f"t{i:03d}")
    return root


def _write_source_row(root: Path, *, system: str, seed: int, task_id: str, error_type: str | None = None) -> None:
    dest = root / system / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {"task_id": task_id, "system": system, "seed": seed, "success": True, "error_type": error_type}
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")


def _prefix_spec(tmp_path: Path, source: Path | None, stem: str = "synth_prefix_m6", system: str = "prefix_handoff") -> str:
    cfg = tmp_path / f"{stem}.yaml"
    handoff = f"handoff:\n  m: 6\n  source_campaign: {source}\n" if source is not None else "handoff:\n  m: 6\n"
    cfg.write_text(handoff, encoding="utf-8")
    return f"{system}|{cfg}|{stem}"


def _run_source_check(extra: dict[str, str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("ARMS", "ARMSET", "SEEDS", "SYSTEM", "GUARD_SPECS", "SMOKE_ONLY"):
        env.pop(key, None)
    env.update(
        {
            "HJ12_GUARD_SELFTEST": "1",
            "GUARD_CASE": "source_check",
            "PY": sys.executable,
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    env.update(extra)
    return subprocess.run(
        ["timeout", str(timeout), "bash", str(PREFIX_PBS)],
        cwd=str(REPO),
        env=env,
        text=True,
        capture_output=True,
    )


def test_prefix_source_complete_passes(tmp_path):
    src = _source_tree(tmp_path / "src")
    proc = _run_source_check({"GUARD_SPECS": _prefix_spec(tmp_path, src)})
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert (
        f"[hj12] replay source ok: arm synth_prefix_m6 source {src} "
        "exists=1 non_crashed=seed1:57,seed2:57 crashed=0 unreadable=0"
    ) in out, out
    assert "[hj12] selftest: source_check passed (1 selected arms)" in out, out
    assert "FATAL" not in out, out


def _prepare_missing(src: Path) -> None:
    pass  # the directory is never created


def _prepare_one_short(src: Path) -> None:
    _source_tree(src, seeds=(1,))
    _source_tree(src, seeds=(2,), n=SOURCE_TASKS - 1)


def _prepare_one_crash(src: Path) -> None:
    # Counts are otherwise met, so only the crash can be what refuses.
    _source_tree(src)
    _write_source_row(src, system="planner_alone", seed=1, task_id="t999", error_type="crash")


def _prepare_unreadable(src: Path) -> None:
    _source_tree(src)
    bad = src / "planner_alone" / "1" / "t998"
    bad.mkdir(parents=True)
    (bad / "result.json").write_text("{not json", encoding="utf-8")


def _prepare_pooled_only(src: Path) -> None:
    # 114 rows in total, all seed 1: a pooled ">= 57 x 2" count would pass with seed 2 absent.
    _source_tree(src, seeds=(1,), n=2 * SOURCE_TASKS)


@pytest.mark.parametrize(
    "prepare, counts",
    [
        (_prepare_missing, "exists=0 non_crashed=seed1:0,seed2:0 crashed=0 unreadable=0"),
        (_prepare_one_short, "exists=1 non_crashed=seed1:57,seed2:56 crashed=0 unreadable=0"),
        (_prepare_one_crash, "exists=1 non_crashed=seed1:57,seed2:57 crashed=1 unreadable=0"),
        (_prepare_unreadable, "exists=1 non_crashed=seed1:57,seed2:57 crashed=0 unreadable=1"),
        (_prepare_pooled_only, "exists=1 non_crashed=seed1:114,seed2:0 crashed=0 unreadable=0"),
    ],
    ids=["missing_dir", "one_episode_short", "one_crash", "one_unreadable", "one_seed_only"],
)
def test_prefix_source_incomplete_refuses_with_one_fatal_line(tmp_path, prepare, counts):
    src = tmp_path / "src"
    prepare(src)
    proc = _run_source_check({"GUARD_SPECS": _prefix_spec(tmp_path, src)})
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert (
        f"[hj12] FATAL: arm synth_prefix_m6 replay source {src} is not complete: {counts} "
        "(need >= 57 non-crashed per seed for SEEDS=1,2, 0 crashed, 0 unreadable); not starting vLLM"
    ) in out, out
    assert out.count("[hj12] FATAL") == 1, out
    assert "source_check passed" not in out, out


def test_prefix_source_judged_for_the_requested_seeds(tmp_path):
    # HJ-18's source holds seed 3 only: it passes under SEEDS=3 and refuses under the default.
    src = _source_tree(tmp_path / "src", seeds=(3,))
    spec = _prefix_spec(tmp_path, src)
    ok = _run_source_check({"GUARD_SPECS": spec, "SEEDS": "3"})
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "non_crashed=seed3:57 crashed=0" in ok.stdout, ok.stdout
    refused = _run_source_check({"GUARD_SPECS": spec})
    assert refused.returncode == 2, refused.stdout + refused.stderr
    assert "non_crashed=seed1:0,seed2:0" in refused.stdout, refused.stdout


def test_prefix_arm_without_source_campaign_refuses(tmp_path):
    proc = _run_source_check({"GUARD_SPECS": _prefix_spec(tmp_path, None)})
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert "[hj12] FATAL: arm synth_prefix_m6 config" in out and "has no handoff.source_campaign" in out, out


def test_non_prefix_arms_are_not_judged(tmp_path):
    spec = _prefix_spec(tmp_path, None, stem="synth_sft_plan", system="sft_plan")
    proc = _run_source_check({"GUARD_SPECS": spec})
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert "[hj12] replay sources: no selected prefix_handoff arm; nothing to check" in out, out


def test_default_free_armset_refuses_before_vllm():
    # The default selection includes the HJ-18 arms, whose source holds seed 3 only, so under the
    # default SEEDS=1,2 it can never pass -- whatever state the LP ceilings are in.
    proc = _run_source_check({}, timeout=240)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert "[hj12] FATAL: arm hj18_prefix_c81s3_zs_m6 replay source " in out, out
    assert "source_check passed" not in out, out


def test_real_cap81_source_passes_for_its_hj17_arm():
    # A healthy arm must not be refused: HJ-17 replays the complete cap-81 planner sample.
    if not CAP81_SOURCE.is_dir():
        pytest.skip(f"{CAP81_SOURCE} not present on this machine")
    proc = _run_source_check({"ARMS": "hj17_prefix_c81_zs_m6"}, timeout=120)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"[hj12] replay source ok: arm hj17_prefix_c81_zs_m6 source {CAP81_SOURCE} exists=1" in out, out
