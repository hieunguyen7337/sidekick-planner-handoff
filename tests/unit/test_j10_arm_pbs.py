"""scripts/pbs/j10_arm.pbs refusals and tally, via its J10_SELFTEST seam.

The self-test runs every refusal check and then exits before a lock, a vLLM server,
a purge or a runner. Nothing under /scratch/n12194778/sidekick/results is written:
J10_OUT / J10_LOGDIR point into tmp_path, and a stub `codex` replaces the real one.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "j10_arm.pbs"
FROZEN_LINE = "**Status**: **FROZEN** 2026-09-24, commit abc1234."
ARM3 = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
REGISTERED_ADAPTER = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b"
# Arms 2 and 8-12: they replay arm 3's first plan packet via planner.packet_source (A1 r2 §4.1).
PACKET_ARMS = ("j10_sft_plan.yaml", "j10_advise_k1_fullctx.yaml", "j10_advise_k10_fullctx.yaml",
               "j10_takeover_k10.yaml", "j10_show_k10.yaml", "j10_advise_k10_neutral.yaml")


def _stub_dir(tmp_path: Path, version: str = "codex-cli 9.9.9") -> Path:
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    codex = stub / "codex"
    codex.write_text(f"#!/bin/bash\necho '{version}'\n", encoding="utf-8")
    codex.chmod(0o755)
    return stub


def _prereg(tmp_path: Path, status_line: str) -> Path:
    path = tmp_path / "prereg.md"
    path.write_text(f"# A1\n\n{status_line}\n\nbody\n", encoding="utf-8")
    return path


def run_pbs(tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "DRYRUN", "SYSTEM", "EXPECTED_CODEX_VERSION",
                "J10_CONFIRM", "J10_PREREG", "J10_SELFTEST_STAGE", "PBS_JOBID",
                "ADAPTER_SFT_B_PLUS", "ALIAS_SFT_B_PLUS", "J10_GUARD_CID"):
        env.pop(key, None)
    env.update(
        J10_SELFTEST="1",
        J10_STUB_DIR=str(_stub_dir(tmp_path)),
        J10_OUT=str(tmp_path / "out"),
        J10_LOGDIR=str(tmp_path / "logs"),
        PY=sys.executable,
        OMP_NUM_THREADS="1",
        OPENBLAS_NUM_THREADS="1",
        MKL_NUM_THREADS="1",
    )
    env.update(env_extra)
    return subprocess.run(["timeout", "120", "bash", str(PBS)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


def _variant(tmp_path: Path, name: str, replace: tuple[str, str] | None = None,
             append: str = "") -> Path:
    text = (REPO / "configs" / name).read_text(encoding="utf-8")
    if replace:
        assert replace[0] in text
        text = text.replace(replace[0], replace[1])
    dest = tmp_path / "cfg" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text + append, encoding="utf-8")
    return dest


def _replay_variant(tmp_path: Path, name: str) -> tuple[Path, Path]:
    """The config with arm 3's registered path moved under tmp_path; returns (config, source).

    A config that replays nothing is copied unchanged, so one helper serves every arm.
    """
    src = tmp_path / "out" / "j10_planner_alone_cap81_20260924"
    text = (REPO / "configs" / name).read_text(encoding="utf-8").replace(ARM3, str(src))
    cfg = tmp_path / "cfg" / name
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text, encoding="utf-8")
    return cfg, src


def _complete(src: Path, n_tasks: int, seeds: tuple[int, ...] = (1, 2)) -> None:
    _write_results(src, [(f"t{i}", s, None) for i in range(n_tasks) for s in seeds], "planner_alone")


def test_bash_syntax():
    assert subprocess.run(["bash", "-n", str(PBS)]).returncode == 0


def test_select_line_pins_h100():
    head = PBS.read_text(encoding="utf-8").splitlines()[:6]
    assert any(line.startswith("#PBS -l select=") and "gpu_id=H100" in line for line in head)


def test_test_challenge_is_always_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", SPLIT="test_challenge",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, FROZEN_LINE)))
    assert proc.returncode == 2, _out(proc)
    assert "test_challenge" in _out(proc)


def test_the_draft_status_line_is_refused_although_it_contains_frozen(tmp_path: Path):
    # A1's DRAFT line (docs/prereg_j10_amendment_20260924.md:3 on 2026-09-23) reads
    # "... Becomes FROZEN on commit." -- a bare substring test would pass it.
    line = "**Status**: **DRAFT pending user review.** Becomes FROZEN on commit. Amends, and does not edit,"
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, line)))
    assert proc.returncode == 2, _out(proc)
    assert "not FROZEN" in _out(proc)


@pytest.mark.parametrize("line", [
    "**Status**: FROZEN, superseding the DRAFT of 2026-09-23.",
    "**Status**: **DRAFT pending user review.** Becomes FROZEN on commit.",
])
def test_status_line_must_begin_frozen_and_not_mention_draft(tmp_path: Path, line: str):
    proc = run_pbs(tmp_path, CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                   J10_CONFIRM="A1_FROZEN", J10_PREREG=str(_prereg(tmp_path, line)))
    assert proc.returncode == 2, _out(proc)


def test_frozen_prereg_still_needs_the_confirmation_token(tmp_path: Path):
    prereg = str(_prereg(tmp_path, FROZEN_LINE))
    # Arm 8 replays arm 3 (A1 r2 F1), so the accepting case needs a complete arm-3 tree.
    cfg, src = _replay_variant(tmp_path, "j10_advise_k1_fullctx.yaml")
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), SPLIT="test_normal",
                   J10_PREREG=prereg, J10_CONFIRM="yes")
    assert proc.returncode == 2 and "J10_CONFIRM=A1_FROZEN" in _out(proc)
    proc = run_pbs(tmp_path, CFG=str(cfg), SPLIT="test_normal",
                   J10_PREREG=prereg, J10_CONFIRM="A1_FROZEN")
    assert proc.returncode == 0, _out(proc)
    text = _out(proc)
    assert "selftest: preflight passed system=fixed_k cid=j10_advise_k1_fullctx_20260924 split=test_normal target=336" in text
    assert "--expect-planner --expect-model gpt-5.6-luna" in text
    assert "codex --version: codex-cli 9.9.9" in text
    assert "planner model from config: gpt-5.6-luna" in text


A1_PATH = REPO / "docs" / "prereg_j10_amendment_20260924.md"
AM1_DRAFT = REPO / "docs" / "prereg_j10_amendment1_draft_20260923.md"


def _a1_with_amendment1() -> str:
    """A1 as the Amendment 1 freeze commit leaves it: the draft's body appended after one blank
    line below A1's end marker -- or A1 itself, once that body is already in it."""
    a1 = A1_PATH.read_text(encoding="utf-8")
    draft = AM1_DRAFT.read_text(encoding="utf-8")
    body = draft.split("<!-- BEGIN APPENDED TEXT -->\n", 1)[1].split("<!-- END APPENDED TEXT -->", 1)[0]
    return a1 if body.strip() in a1 else a1 + "\n" + body


def test_amendment1_keeps_one_status_line_and_passes_the_gate(tmp_path: Path):
    text = _a1_with_amendment1()
    status = [line for line in text.splitlines() if line.startswith("**Status**")]
    assert len(status) == 1 and status[0].startswith("**Status**: **FROZEN**")
    assert "*Amendment A1 ends. J9 remains frozen and unedited.*\n\n## Amendment 1 " in text
    # Later amendments append below Amendment 1's end marker (Amendment 2, 3a97543), never above it.
    assert text.count("*Amendment 1 ends.*") == 1
    tail = text.split("*Amendment 1 ends.*", 1)[1].strip()
    assert tail == "" or (tail.startswith("## Amendment 2 ") and tail.endswith("*Amendment 2 ends.*"))
    prereg = tmp_path / "a1_with_amendment1.md"
    prereg.write_text(text, encoding="utf-8")
    cfg, src = _replay_variant(tmp_path, "j10_advise_k1_fullctx.yaml")
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), SPLIT="test_normal", J10_PREREG=str(prereg),
                   J10_CONFIRM="A1_FROZEN")
    assert proc.returncode == 0, _out(proc)
    assert "selftest: preflight passed system=fixed_k cid=j10_advise_k1_fullctx_20260924 split=test_normal" in _out(proc)


def test_test_normal_refuses_a_partial_or_renamed_read(tmp_path: Path):
    common = dict(CFG="configs/j10_advise_k1_fullctx.yaml", SPLIT="test_normal",
                  J10_PREREG=str(_prereg(tmp_path, FROZEN_LINE)), J10_CONFIRM="A1_FROZEN")
    assert run_pbs(tmp_path, TASKS="10", **common).returncode == 2
    assert run_pbs(tmp_path, SEEDS="1,2,3", **common).returncode == 2
    assert run_pbs(tmp_path, CID="j10_other", **common).returncode == 2


@pytest.mark.parametrize("expected,rc", [("9.9.9", 0), ("codex-cli 9.9.9", 0), ("0.1.0", 2)])
def test_expected_codex_version(tmp_path: Path, expected: str, rc: int):
    cfg, src = _replay_variant(tmp_path, "j10_advise_k1_fullctx.yaml")
    _complete(Path(str(src) + "_dryrun"), 2)
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2",
                   EXPECTED_CODEX_VERSION=expected)
    assert proc.returncode == rc, _out(proc)
    if rc:
        assert "expected '0.1.0'" in _out(proc)


def test_planner_model_must_be_exactly_luna(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_advise_k1_fullctx.yaml",
                   ("model: gpt-5.6-luna", "model: gpt-5.6-sol"))
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2, _out(proc)
    assert "registered planner is exactly gpt-5.6-luna" in _out(proc)


def test_hosted_arm_with_a_mock_planner_is_refused(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_sft_plan.yaml", ("type: codex", "type: mock"))
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2 and "silently runs MockPlanner" in _out(proc)


def test_config_split_key_and_system_mismatch_are_refused(tmp_path: Path):
    cfg = _variant(tmp_path, "j10_executor_alone.yaml", append="\nsplit: test_normal\n")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2 and "split: key" in _out(proc)
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", DRYRUN="1", SYSTEM="fixed_k")
    assert proc.returncode == 2 and "disagrees with the registered system" in _out(proc)


def test_dev_run_into_the_registered_campaign_id_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", SPLIT="dev")
    assert proc.returncode == 2 and "mix dev episodes into the test tree" in _out(proc)
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", DRYRUN="1")
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    assert "cid=j10_executor_alone_20260924_dryrun split=dev target=114" in line
    assert line.endswith("gate=--gate")  # a planner-free arm is gated on ZERO live calls


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str) -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps(
            {"task_id": task, "seed": seed, "error_type": err}) + "\n", encoding="utf-8")


def test_dryrun_prefix_arm_replays_the_dryrun_planner_and_requires_it_complete(tmp_path: Path):
    src = tmp_path / "out" / "j10_planner_alone_cap81_20260924"
    real = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
    text = (REPO / "configs" / "j10_prefix_m11.yaml").read_text(encoding="utf-8").replace(real, str(src))
    cfg = tmp_path / "cfg" / "j10_prefix_m11.yaml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(text, encoding="utf-8")
    dry = Path(str(src) + "_dryrun")
    # Incomplete source: 3 of 4 episodes, and the registered (non-dry-run) tree is ignored.
    _write_results(src, [(f"t{i}", s, None) for i in range(2) for s in (1, 2)], "planner_alone")
    _write_results(dry, [("t0", 1, None), ("t0", 2, None), ("t1", 1, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 2, _out(proc)
    assert "arm 3 must complete before arms 4-7 start" in _out(proc)
    _write_results(dry, [("t1", 2, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 0, _out(proc)
    derived = list((tmp_path / "logs" / "j10_dryrun_cfg").glob("j10_prefix_m11_20260924_dryrun.*.yaml"))
    assert derived
    for path in derived:
        body = path.read_text(encoding="utf-8")
        assert f"source_campaign: {dry}" in body and f"packet_source: {dry}" in body
        assert "campaign_id: j10_prefix_m11_20260924_dryrun" in body
    assert "system=prefix_handoff" in _out(proc)


def test_dev_prefix_run_without_dryrun_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j10_prefix_m9.yaml", SPLIT="dev", CID="j10_prefix_m9_devcheck")
    assert proc.returncode == 2 and "use DRYRUN=1" in _out(proc)


def test_tally_exits_nonzero_while_crashes_remain_and_zero_when_complete(tmp_path: Path):
    root = tmp_path / "out" / "j10_executor_alone_20260924_dryrun"
    _write_results(root, [("t0", 1, None), ("t0", 2, "limit"), ("t1", 1, None), ("t1", 2, "crash")],
                   "executor_alone")
    env = dict(CFG="configs/j10_executor_alone.yaml", DRYRUN="1", TASKS="2",
               J10_SELFTEST_STAGE="tally")
    proc = run_pbs(tmp_path, **env)
    text = _out(proc)
    assert proc.returncode == 3, text
    assert "target=4 non_crashed=3 crashed=1" in text
    assert "limit" in text and "crash" in text and "resubmit" in text
    _write_results(root, [("t1", 2, None)], "executor_alone")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "COMPLETE: 4/4 non-crashed, 0 crashed" in _out(proc)


# ---- A1 r2: arms 2 and 8-12 replay arm 3 (F1); the adapter is pinned (F8) -----------------

# Every registered J10 config and the runner --system the wrapper derives from its stem.
SYSTEM_OF = {
    "j10_executor_alone.yaml": "executor_alone",
    "j10_executor_alone_bplus.yaml": "executor_alone",
    "j10_sft_plan.yaml": "sft_plan",
    "j10_planner_alone_cap81.yaml": "planner_alone",
    "j10_prefix_m9.yaml": "prefix_handoff",
    "j10_prefix_m11.yaml": "prefix_handoff",
    "j10_prefix_zs_m9.yaml": "prefix_handoff",
    "j10_prefix_zs_m11.yaml": "prefix_handoff",
    "j10_advise_k1_fullctx.yaml": "fixed_k",
    "j10_advise_k10_fullctx.yaml": "fixed_k",
    "j10_takeover_k10.yaml": "fixed_k",
    "j10_show_k10.yaml": "fixed_k",
    "j10_advise_k10_neutral.yaml": "fixed_k",
}


def _test_normal(tmp_path: Path) -> dict[str, str]:
    return dict(SPLIT="test_normal", J10_CONFIRM="A1_FROZEN",
                J10_PREREG=str(_prereg(tmp_path, FROZEN_LINE)))


def test_system_table_covers_every_j10_config():
    assert sorted(p.name for p in (REPO / "configs").glob("j10_*.yaml")) == sorted(SYSTEM_OF)


@pytest.mark.parametrize("name", sorted(SYSTEM_OF))
def test_every_registered_config_passes_preflight_on_test_once_arm_3_is_complete(tmp_path: Path, name: str):
    # A stem the wrapper does not know is refused ("no registered system"), so this is also the
    # test that arms 1b, 10, 11 and 12 can be submitted at all.
    cfg, src = _replay_variant(tmp_path, name)
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    stem = name[: -len(".yaml")]
    assert f"system={SYSTEM_OF[name]} cid={stem}_20260924 split=test_normal target=336" in line
    if SYSTEM_OF[name] in ("executor_alone", "prefix_handoff"):
        assert line.endswith("gate=--gate")  # zero live planner calls
    else:
        assert line.endswith("gate=--gate --expect-planner --expect-model gpt-5.6-luna")


@pytest.mark.parametrize("name", PACKET_ARMS)
def test_packet_source_arm_is_refused_on_test_until_arm_3_is_complete(tmp_path: Path, name: str):
    cfg, src = _replay_variant(tmp_path, name)
    assert f"packet_source: {src}" in cfg.read_text(encoding="utf-8")
    env = dict(CFG=str(cfg), **_test_normal(tmp_path))
    wait = "planner.packet_source campaign is not complete; arm 3 must complete before arms 2 and 8-12 start"

    proc = run_pbs(tmp_path, **env)  # arm 3 not started
    assert proc.returncode == 2, _out(proc)
    assert wait in _out(proc) and f"planner.packet_source {src}: exists=0" in _out(proc)

    # One episode short of 168 x 2.
    _write_results(src, [(f"t{i}", s, None) for i in range(168) for s in (1, 2) if (i, s) != (167, 2)],
                   "planner_alone")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and wait in _out(proc) and "non_crashed=335" in _out(proc)

    # The missing episode written as a crash: resubmitting arm 3 would purge and re-plan it.
    _write_results(src, [("t167", 2, "crash")], "planner_alone")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and wait in _out(proc) and "crashed=1" in _out(proc)

    _write_results(src, [("t167", 2, None)], "planner_alone")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert f"planner.packet_source {src}: exists=1 non_crashed=336 crashed=0 unreadable=0" in _out(proc)


def _planless(src: Path, keys: list[tuple[str, int]]) -> None:
    """Give these (already scored) arm-3 episodes an events.jsonl whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = src / "planner_alone" / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "events.jsonl").write_text(
            json.dumps({"event_type": "run_start", "payload": {}}) + "\n"
            + json.dumps({"event_type": "parse_error", "payload": {"text": "?"}}) + "\n",
            encoding="utf-8")


def test_planless_arm_3_keys_are_listed_and_capped_at_5_percent(tmp_path: Path):
    # A1 §4.2: those keys get a live first plan; above 16 of 336 the replay arm is refused.
    cfg, src = _replay_variant(tmp_path, "j10_takeover_k10.yaml")
    _complete(src, 168)
    env = dict(CFG=str(cfg), **_test_normal(tmp_path))
    _planless(src, [("t3", 2), ("t7", 1)])
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "arm-3 episodes scored without a plan: 2 (cap 16, A1 §4.2): 1/t7 2/t3" in _out(proc)
    _planless(src, [(f"t{i}", 1) for i in range(20, 35)])  # 17 in all
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2, _out(proc)
    assert "17 arm-3 episodes wrote no plan, above A1 §4.2's cap of 16 (5 % of 336)" in _out(proc)


def test_a_replay_arm_that_would_abort_on_a_planless_key_is_refused(tmp_path: Path):
    cfg, src = _replay_variant(tmp_path, "j10_sft_plan.yaml")
    text = cfg.read_text(encoding="utf-8")
    assert "on_missing: call_if_planless" in text
    cfg.write_text(text.replace("on_missing: call_if_planless", "on_missing: fail"), encoding="utf-8")
    _complete(src, 168)
    _planless(src, [("t0", 1)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2, _out(proc)
    assert "planner.on_missing is 'fail', so the 1 arm-3 episode(s) without a plan would crash" in _out(proc)


def test_prefix_arms_do_not_count_planless_keys(tmp_path: Path):
    # A prefix arm never calls plan(); a planless source episode is a step-0 handoff (A1 §4.2).
    cfg, src = _replay_variant(tmp_path, "j10_prefix_m11.yaml")
    _complete(src, 168)
    _planless(src, [("t0", 1)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 0, _out(proc)
    assert "scored without a plan" not in _out(proc)


def test_dryrun_packet_source_arm_replays_the_dryrun_planner_and_requires_it_complete(tmp_path: Path):
    cfg, src = _replay_variant(tmp_path, "j10_sft_plan.yaml")
    dry = Path(str(src) + "_dryrun")
    _complete(src, 2)  # the registered tree is complete, and must not be what a dry run judges
    _write_results(dry, [("t0", 1, None), ("t0", 2, None), ("t1", 1, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 2, _out(proc)
    assert "arm 3 must complete before arms 2 and 8-12 start" in _out(proc)
    assert f"planner.packet_source {dry}: exists=1 non_crashed=3" in _out(proc)
    _write_results(dry, [("t1", 2, None)], "planner_alone")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 0, _out(proc)
    assert "system=sft_plan" in _out(proc)
    derived = list((tmp_path / "logs" / "j10_dryrun_cfg").glob("j10_sft_plan_20260924_dryrun.*.yaml"))
    assert derived
    for path in derived:
        body = path.read_text(encoding="utf-8")
        assert f"packet_source: {dry}" in body
        assert "campaign_id: j10_sft_plan_20260924_dryrun" in body


def test_test_normal_serves_sft_b_plus_only_from_the_registered_adapter(tmp_path: Path):
    common = dict(CFG="configs/j10_executor_alone_bplus.yaml", **_test_normal(tmp_path))
    older = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b"
    proc = run_pbs(tmp_path, ADAPTER_SFT_B_PLUS=older, **common)
    assert proc.returncode == 2, _out(proc)
    assert "only from the registered adapter" in _out(proc) and older in _out(proc)
    # Exact string: a trailing slash is refused rather than resolved, so the log can only ever
    # record the path A1 names.
    assert run_pbs(tmp_path, ADAPTER_SFT_B_PLUS=REGISTERED_ADAPTER + "/", **common).returncode == 2
    # Every arm on test, including a base-receiver arm that registers no LoRA.
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone.yaml", ADAPTER_SFT_B_PLUS=older,
                   **_test_normal(tmp_path))
    assert proc.returncode == 2, _out(proc)
    assert run_pbs(tmp_path, **common).returncode == 0  # the default is the registered adapter
    proc = run_pbs(tmp_path, ADAPTER_SFT_B_PLUS=REGISTERED_ADAPTER, **common)
    assert proc.returncode == 0, _out(proc)
    # A1 pins test only; a dev dry run keeps the override.
    proc = run_pbs(tmp_path, CFG="configs/j10_executor_alone_bplus.yaml", DRYRUN="1",
                   ADAPTER_SFT_B_PLUS=older)
    assert proc.returncode == 0, _out(proc)


# ---- (e2) smoke-time branch guards, ported from hj12_live.pbs ------------------------------

RUN_START = {"event_type": "run_start", "actor": "system"}
EXEC_ACT = {"event_type": "action", "actor": "executor"}
PLANNER_ACT = {"event_type": "action", "actor": "planner"}  # loop.py takeover branch
ADVICE = {"event_type": "intervention", "actor": "planner", "payload": {"forced": True}}
SHOWN = {"event_type": "intervention", "actor": "planner",
         "payload": {"forced": True, "source": "shown_action"}}  # loop.py advice_from_act branch


def _smoke(root: Path, episodes: list[tuple[int, list[dict]]]) -> None:
    """A smoke campaign in runner layout: one (steps, events) pair per episode."""
    for i, (steps, events) in enumerate(episodes):
        ep = root / "fixed_k" / "1" / f"t{i}"
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        (ep / "result.json").write_text(json.dumps(
            {"task_id": f"t{i}", "seed": 1, "steps": steps, "error_type": None}) + "\n", encoding="utf-8")


def _guard(tmp_path: Path, name: str, episodes, cfg: Path | None = None) -> subprocess.CompletedProcess[str]:
    if cfg is None:
        cfg, _src = _replay_variant(tmp_path, name)
    _complete(tmp_path / "out" / "j10_planner_alone_cap81_20260924_dryrun", 2)
    _smoke(tmp_path / "out" / "smoke_x", episodes)
    return run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2",
                   J10_SELFTEST_STAGE="branch_guard", J10_GUARD_CID="smoke_x")


REACHED = 12  # >= fixed_k: 10, so the review step was reached
SHORT = 4     # < 10: no review step was reached, the channel never had a chance to fire

BRANCH_CASES = [
    # takeover: zero planner actions is fatal once a review step was reached, a warning before.
    ("takeover-fire", "j10_takeover_k10.yaml", [(REACHED, [RUN_START, EXEC_ACT, ADVICE]), (SHORT, [RUN_START])],
     1, "0 planner-authored action events on smoke and at least one episode could have triggered"),
    ("takeover-warn", "j10_takeover_k10.yaml", [(SHORT, [RUN_START, EXEC_ACT]), (3, [RUN_START])],
     0, "WARN: takeover arm j10_takeover_k10 has 0 planner-authored action events on smoke"),
    ("takeover-pass", "j10_takeover_k10.yaml", [(REACHED, [RUN_START, EXEC_ACT, PLANNER_ACT])],
     0, "planner_actions=1 shown_action_interventions=0"),
    # an action from an attempt before the episode's last run_start does not count (hj12's rule)
    ("takeover-stale-attempt", "j10_takeover_k10.yaml",
     [(REACHED, [RUN_START, PLANNER_ACT, RUN_START, EXEC_ACT])], 1, "ran the advise path"),
    ("takeover-ran-show", "j10_takeover_k10.yaml", [(REACHED, [RUN_START, SHOWN, PLANNER_ACT])],
     1, "it ran the show channel"),
    # show: zero shown_action interventions is fatal once a review step was reached.
    ("show-fire", "j10_show_k10.yaml", [(REACHED, [RUN_START, EXEC_ACT, ADVICE])],
     1, "the advice_from_act branch did not run"),
    ("show-warn", "j10_show_k10.yaml", [(SHORT, [RUN_START, EXEC_ACT])],
     0, "WARN: show arm j10_show_k10 has 0 shown_action interventions on smoke"),
    ("show-pass", "j10_show_k10.yaml", [(REACHED, [RUN_START, SHOWN, EXEC_ACT])],
     0, "planner_actions=0 shown_action_interventions=1"),
    ("show-ran-takeover", "j10_show_k10.yaml", [(REACHED, [RUN_START, SHOWN, PLANNER_ACT])],
     1, "it executed the planner's actions"),
    # advise: any shown action or planner action is fatal, review step reached or not.
    ("advise-shown", "j10_advise_k10_fullctx.yaml", [(SHORT, [RUN_START, SHOWN])],
     1, "advise arm j10_advise_k10_fullctx has 0 planner-authored action events and 1 shown_action"),
    ("advise-takeover", "j10_advise_k1_fullctx.yaml", [(REACHED, [RUN_START, PLANNER_ACT])],
     1, "a takeover/advice_from_act setting made it another channel"),
    ("advise-neutral-shown", "j10_advise_k10_neutral.yaml", [(REACHED, [RUN_START, ADVICE, SHOWN])],
     1, "shown_action interventions on smoke"),
    ("advise-pass", "j10_advise_k10_fullctx.yaml", [(REACHED, [RUN_START, EXEC_ACT, ADVICE])],
     0, "planner_actions=0 shown_action_interventions=0"),
]


@pytest.mark.parametrize("name,episodes,rc,text", [c[1:] for c in BRANCH_CASES],
                         ids=[c[0] for c in BRANCH_CASES])
def test_branch_guard_on_constructed_smoke_trees(tmp_path: Path, name: str, episodes, rc: int, text: str):
    proc = _guard(tmp_path, name, episodes)
    assert proc.returncode == rc, _out(proc)
    assert text in _out(proc)
    if rc:
        assert "[j10] FATAL:" in _out(proc) and "not launching the full run" in _out(proc)
        assert "selftest: branch guard passed" not in _out(proc)
    else:
        assert "selftest: branch guard passed" in _out(proc)


def test_branch_guard_refuses_when_it_cannot_read_k(tmp_path: Path):
    # A smoke that would only warn must refuse when fixed_k cannot be read: a guard that cannot
    # tell whether the channel had a chance to fire does not wave the arm through.
    cfg, _src = _replay_variant(tmp_path, "j10_takeover_k10.yaml")
    text = cfg.read_text(encoding="utf-8")
    assert "\nfixed_k: 10" in text
    cfg.write_text(text.replace("\nfixed_k: 10", "\n"), encoding="utf-8")
    proc = _guard(tmp_path, "j10_takeover_k10.yaml", [(SHORT, [RUN_START, EXEC_ACT])], cfg=cfg)
    assert proc.returncode == 1, _out(proc)
    assert "could have triggered" in _out(proc)


def test_branch_guard_is_a_no_op_for_arms_without_a_review_channel(tmp_path: Path):
    proc = _guard(tmp_path, "j10_sft_plan.yaml", [(REACHED, [RUN_START, SHOWN, PLANNER_ACT])])
    assert proc.returncode == 0, _out(proc)
    assert "branch guard j10_sft_plan" not in _out(proc)
    assert "selftest: branch guard passed" in _out(proc)


def test_the_real_run_calls_the_branch_guard_on_the_smoke_before_the_dev_tree_is_deleted():
    text = PBS.read_text(encoding="utf-8")
    call = text.index('j10_branch_guard "${CFG_STEM}" "${SCID}" "${CFG_EFF}"')
    assert text.index("GATE_RC=$?") < call < text.index('rm -rf "${OUT:?}/${SCID:?}"')
    assert call < text.index("# ---- (f) the arm")
