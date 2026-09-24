"""scripts/pbs/bfcl_arm.pbs: refusals, the jq tally and the spend guard, through its self-test seams.

No GPU, no qsub. The self-test runs every refusal check and exits before a lock, a vLLM server, a purge or a
runner. BFCL_OUT / BFCL_LOGDIR point into tmp_path, a stub `codex` replaces the real one, and a replay arm's
registered source path is moved under BFCL_OUT, so nothing under /scratch/n12194778/sidekick/results is read
or written.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "bfcl_arm.pbs"
CFG = REPO / "configs" / "bfcl_executor_alone_zs.yaml"
SOURCE_CID = "bfcl_planner_alone_cap81_dev_20260924"
REGISTERED_SOURCE = f"/scratch/n12194778/sidekick/results/{SOURCE_CID}"
# Every config of the dev design, and the runner --system the wrapper derives from its stem.
SYSTEM_OF = {
    "bfcl_executor_alone_zs.yaml": "executor_alone",
    "bfcl_executor_alone_bplus.yaml": "executor_alone",
    "bfcl_planner_alone_cap81.yaml": "planner_alone",
    "bfcl_plan_zs.yaml": "prompt_only",
    "bfcl_takeover_k5.yaml": "fixed_k",
    "bfcl_advise_k5_fullctx.yaml": "fixed_k",
    "bfcl_advise_k5_neutral.yaml": "fixed_k",
    **{f"bfcl_prefix_{r}_m{m}.yaml": "prefix_handoff" for r in ("zs", "bplus") for m in (2, 4, 6)},
}
HOSTED = {"bfcl_planner_alone_cap81.yaml", "bfcl_plan_zs.yaml", "bfcl_takeover_k5.yaml",
          "bfcl_advise_k5_fullctx.yaml", "bfcl_advise_k5_neutral.yaml"}
CODEX_OK = {"EXPECTED_CODEX_VERSION": "0.153.4"}


def _stub_dir(tmp: Path, version: str = "codex-cli 0.153.4") -> Path:
    stub = tmp / "stub"
    stub.mkdir(exist_ok=True)
    codex = stub / "codex"
    codex.write_text(f"#!/bin/bash\necho '{version}'\n", encoding="utf-8")
    codex.chmod(0o755)
    return stub


def _adapter(tmp: Path, weights: bool = True) -> Path:
    path = tmp / "adapter"
    path.mkdir(exist_ok=True)
    (path / "adapter_config.json").write_text("{}", encoding="utf-8")
    if weights:
        (path / "adapter_model.safetensors").write_text("x", encoding="utf-8")
    return path


def _run(tmp: Path, **env: str) -> subprocess.CompletedProcess:
    full = dict(os.environ)
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "SYSTEM", "EXPECTED_CODEX_VERSION", "MAX_PLANNER_CALLS",
                "BFCL_SELFTEST_STAGE", "BFCL_SPEND_RATE_CID", "PBS_JOBID", "CFG"):
        full.pop(key, None)
    full.update({"BFCL_SELFTEST": "1", "BFCL_REPO": str(REPO), "BFCL_OUT": str(tmp / "out"),
                 "BFCL_LOGDIR": str(tmp / "logs"), "PY": sys.executable,
                 "BFCL_ADAPTER_SFT_B_PLUS": str(_adapter(tmp))})
    if "BFCL_STUB_DIR" not in env:
        full["BFCL_STUB_DIR"] = str(_stub_dir(tmp))
    full.update(env)
    return subprocess.run(["bash", str(PBS)], env=full, capture_output=True, text=True, timeout=120)


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def _variant(tmp: Path, name: str, edit: dict | None = None) -> Path:
    """The config under its own name in tmp, with the registered source moved under BFCL_OUT."""
    text = (REPO / "configs" / name).read_text(encoding="utf-8").replace(REGISTERED_SOURCE, str(tmp / "out" / SOURCE_CID))
    data = yaml.safe_load(text)
    for key, value in (edit or {}).items():
        if isinstance(value, dict):
            data[key] = {**data[key], **value}
        elif value is None:
            data.pop(key, None)
        else:
            data[key] = value
    cfg = tmp / "cfg" / name
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(yaml.safe_dump(data, sort_keys=False) if edit else text, encoding="utf-8")
    return cfg


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str, **extra) -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps({"task_id": task, "seed": seed, "error_type": err, **extra}) + "\n",
                                        encoding="utf-8")


def _complete_source(tmp: Path, n_tasks: int = 50, seeds: tuple[int, ...] = (1, 2)) -> Path:
    src = tmp / "out" / SOURCE_CID
    _write_results(src, [(f"multi_turn_base_{i}", s, None) for i in range(n_tasks) for s in seeds], "planner_alone")
    return src


def test_script_parses() -> None:
    assert subprocess.run(["bash", "-n", str(PBS)], capture_output=True).returncode == 0


def test_config_matches_the_j10_floor_receiver() -> None:
    ours = yaml.safe_load(CFG.read_text())
    j10 = yaml.safe_load((REPO / "configs" / "j10_executor_alone.yaml").read_text())
    assert ours["env"] == "bfcl" and ours["campaign_id"] == "bfcl_executor_alone_zs_dev_20260924"
    assert ours["executor"] == j10["executor"] and ours["limits"] == j10["limits"]
    assert "split" not in ours and ours["planner"] == {"type": "mock"}


def test_preflight_accepts_the_registered_config(tmp_path: Path) -> None:
    proc = _run(tmp_path)
    assert proc.returncode == 0, _out(proc)
    assert "selftest preflight ok" in proc.stdout
    assert "target=100 (50 tasks x 2 seeds)" in proc.stdout


@pytest.mark.parametrize(
    "env, message",
    [
        ({"SPLIT": "test"}, "SPLIT=test: this arm runs on the BFCL dev split only"),
        ({"SPLIT": "test_normal"}, "SPLIT=test_normal: this arm runs on the BFCL dev split only"),
        ({"CID": "bfcl_executor_alone_zs_test_x"}, "does not say _dev_"),
        ({"CID": "../bfcl_x_dev_y"}, "unsafe CID"),
        ({"SYSTEM": "planner_alone"}, "disagrees with the registered system executor_alone"),
        ({"TASKS": "51"}, "TASKS must be 0..50"),
        ({"SEEDS": "1;2"}, "SEEDS must look like 1,2"),
    ],
)
def test_preflight_refusals(tmp_path: Path, env: dict, message: str) -> None:
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


@pytest.mark.parametrize(
    "edit, message",
    [
        ({"executor": {"lora_name": "sft_b_plus"}}, "this arm is zero-shot"),
        ({"planner": {"type": "codex"}}, "must make zero hosted calls"),
        ({"env": "appworld"}, "config env is appworld, not bfcl"),
        ({"split": "dev"}, "carries a split: key"),
        ({"campaign_id": "bfcl_executor_alone_zs_dev_x"}, "is not bfcl_executor_alone_zs_dev_20260924"),
        ({"executor": {"model": "Qwen/Qwen3-8B"}}, "expected ibm-granite/granite-4.2-8b"),
    ],
)
def test_config_refusals(tmp_path: Path, edit: dict, message: str) -> None:
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_executor_alone_zs.yaml", edit)))
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


def test_a_stem_outside_the_dev_design_is_refused(tmp_path: Path) -> None:
    # A copy of a registered config under another name (the J10 show channel is not a BFCL arm).
    cfg = tmp_path / "cfg" / "bfcl_show_k5.yaml"
    cfg.parent.mkdir(parents=True)
    shutil.copy(REPO / "configs" / "bfcl_advise_k5_fullctx.yaml", cfg)
    proc = _run(tmp_path, CFG=str(cfg), **CODEX_OK)
    assert proc.returncode == 2 and "bfcl_show_k5.yaml is not an arm of the BFCL dev design" in proc.stdout


def test_the_system_table_covers_every_bfcl_config() -> None:
    assert sorted(p.name for p in (REPO / "configs").glob("bfcl_*.yaml")) == sorted(SYSTEM_OF)


@pytest.mark.parametrize("name", sorted(SYSTEM_OF))
def test_every_config_passes_preflight_once_planner_alone_is_complete(tmp_path: Path, name: str) -> None:
    _complete_source(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, name)), **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in proc.stdout.splitlines() if "selftest preflight ok" in l)
    stem = name[: -len(".yaml")]
    receiver = "none" if "planner_alone" in stem else ("bplus" if "bplus" in stem else "zs")
    assert f"system={SYSTEM_OF[name]} cid={stem}_dev_20260924 receiver={receiver} target=100" in line
    if name in HOSTED:
        assert line.endswith("gate=--gate --expect-planner --expect-model gpt-5.6-luna")
        assert "MAX_PLANNER_CALLS=" in proc.stdout
    else:
        assert line.endswith("gate=--gate")  # zero live planner calls
    if receiver == "bplus":
        assert "lora-module sft_b_plus=" in proc.stdout


def test_the_default_ceiling_is_the_high_end_per_episode_times_the_target(tmp_path: Path) -> None:
    _complete_source(tmp_path)
    # Hand values: planner_alone 16 x 100, a channel arm 4 x 100, plan_zs 2 x 100; 6 tasks x 1 seed: 16 x 6.
    for name, want in (("bfcl_planner_alone_cap81.yaml", 1600), ("bfcl_takeover_k5.yaml", 400),
                       ("bfcl_plan_zs.yaml", 200)):
        proc = _run(tmp_path, CFG=str(_variant(tmp_path, name)), **CODEX_OK)
        assert f"MAX_PLANNER_CALLS={want} " in proc.stdout, _out(proc)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_planner_alone_cap81.yaml")), TASKS="6", SEEDS="1", **CODEX_OK)
    assert "MAX_PLANNER_CALLS=96 " in proc.stdout, _out(proc)


# ---- hosted stems: codex only with EXPECTED_CODEX_VERSION=0.153.4 (as j10_arm.pbs) ---------------

@pytest.mark.parametrize(
    "expected, stub, rc, message",
    [
        (None, "codex-cli 0.153.4", 2, "needs EXPECTED_CODEX_VERSION=0.153.4 (got '<unset>')"),
        ("0.153.5", "codex-cli 0.153.5", 2, "needs EXPECTED_CODEX_VERSION=0.153.4 (got '0.153.5')"),
        ("0.153.4", "codex-cli 9.9.9", 2, "codex --version is 'codex-cli 9.9.9', expected '0.153.4'"),
        ("0.153.4", "codex-cli 0.153.4", 0, "codex version matches EXPECTED_CODEX_VERSION=0.153.4"),
    ],
)
def test_codex_planner_needs_the_registered_codex_version(tmp_path: Path, expected, stub, rc, message) -> None:
    env = {"CFG": str(_variant(tmp_path, "bfcl_planner_alone_cap81.yaml")),
           "BFCL_STUB_DIR": str(_stub_dir(tmp_path, stub))}
    if expected is not None:
        env["EXPECTED_CODEX_VERSION"] = expected
    proc = _run(tmp_path, **env)
    assert proc.returncode == rc and message in proc.stdout, _out(proc)


def test_a_prefix_arm_carrying_a_codex_planner_needs_the_version_too(tmp_path: Path) -> None:
    _complete_source(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_prefix_zs_m4.yaml")))
    assert proc.returncode == 2 and "needs EXPECTED_CODEX_VERSION=0.153.4" in proc.stdout


@pytest.mark.parametrize(
    "name, edit, message",
    [
        ("bfcl_planner_alone_cap81.yaml", {"planner": {"type": "mock"}}, "anything but codex silently runs MockPlanner"),
        ("bfcl_takeover_k5.yaml", {"planner": {"model": "gpt-5.6-sol"}}, "registered planner is exactly gpt-5.6-luna"),
        ("bfcl_planner_alone_cap81.yaml", {"executor": {"type": "vllm"}}, "planner_alone never constructs an executor"),
        ("bfcl_takeover_k5.yaml", {"fixed_k": 10}, "fixed_k=10, but takeover_k5 registers k=5"),
        ("bfcl_takeover_k5.yaml", {"takeover": None}, "takeover=0, but takeover_k5 registers takeover=1"),
        ("bfcl_advise_k5_fullctx.yaml", {"takeover": True}, "takeover=1, but advise_k5_fullctx registers takeover=0"),
        ("bfcl_advise_k5_fullctx.yaml", {"advice_from_act": True}, "no arm of the BFCL dev design is the show channel"),
        ("bfcl_advise_k5_neutral.yaml", {"planner": {"correct_prompt": "correction"}}, "registers neutral"),
        ("bfcl_prefix_zs_m4.yaml", {"handoff": {"m": 6}}, "handoff.m=6, but prefix_zs_m4 registers m=4"),
        ("bfcl_prefix_zs_m2.yaml", {"planner": {"on_missing": "call"}}, "needs packet_source and on_missing: fail"),
        ("bfcl_prefix_bplus_m2.yaml", {"executor": {"lora_name": None}}, "is not the served alias sft_b_plus"),
        ("bfcl_executor_alone_bplus.yaml", {"executor": {"lora_name": "sft_b_plus_v2"}}, "requests would silently hit BASE"),
    ],
)
def test_arm_fact_refusals(tmp_path: Path, name: str, edit: dict, message: str) -> None:
    _complete_source(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, name, edit)), **CODEX_OK)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


@pytest.mark.parametrize(
    "name, edit, message",
    [
        ("bfcl_executor_alone_zs.yaml", {"executor": {"type": "mock"}}, "executor.type=mock, expected vllm"),
        ("bfcl_prefix_zs_m6.yaml", {"handoff": {"source_campaign": None}}, "prefix arm without handoff.source_campaign"),
    ],
)
def test_more_arm_fact_refusals(tmp_path: Path, name: str, edit: dict, message: str) -> None:
    _complete_source(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, name, edit)), **CODEX_OK)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


def test_missing_and_unreadable_configs_are_refused(tmp_path: Path) -> None:
    proc = _run(tmp_path, CFG=str(tmp_path / "cfg" / "bfcl_takeover_k5.yaml"))
    assert proc.returncode == 2 and "config not found" in proc.stdout
    bad = tmp_path / "cfg" / "bfcl_takeover_k5.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("env: [bfcl\n", encoding="utf-8")
    proc = _run(tmp_path, CFG=str(bad))
    assert proc.returncode == 2 and "could not read" in proc.stdout


def test_an_empty_codex_version_and_a_non_integer_ceiling_are_refused(tmp_path: Path) -> None:
    cfg = str(_variant(tmp_path, "bfcl_planner_alone_cap81.yaml"))
    proc = _run(tmp_path, CFG=cfg, BFCL_STUB_DIR=str(_stub_dir(tmp_path, "")), **CODEX_OK)
    assert proc.returncode == 2 and "codex --version returned nothing" in proc.stdout, _out(proc)
    proc = _run(tmp_path, CFG=cfg, MAX_PLANNER_CALLS="lots", **CODEX_OK)
    assert proc.returncode == 2 and "MAX_PLANNER_CALLS must be an integer" in proc.stdout, _out(proc)


def test_an_adapter_without_its_config_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty_adapter"
    empty.mkdir()
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_executor_alone_bplus.yaml")),
                BFCL_ADAPTER_SFT_B_PLUS=str(empty))
    assert proc.returncode == 2 and "missing adapter_config.json" in proc.stdout


def test_a_planless_source_key_is_refused_when_the_arm_would_abort_on_it(tmp_path: Path) -> None:
    src = _complete_source(tmp_path)
    _planless(src, [("multi_turn_base_3", 1)])
    cfg = _variant(tmp_path, "bfcl_plan_zs.yaml", {"planner": {"on_missing": "fail"}})
    proc = _run(tmp_path, CFG=str(cfg), **CODEX_OK)
    assert proc.returncode == 2 and "planner.on_missing is 'fail', so the 1 planless source episode(s) would crash" in proc.stdout


def test_the_bplus_adapter_must_exist_with_weights(tmp_path: Path) -> None:
    cfg = str(_variant(tmp_path, "bfcl_executor_alone_bplus.yaml"))
    proc = _run(tmp_path, CFG=cfg, BFCL_ADAPTER_SFT_B_PLUS=str(tmp_path / "nowhere"))
    assert proc.returncode == 2 and "is not a directory" in proc.stdout
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "adapter_config.json").write_text("{}", encoding="utf-8")
    proc = _run(tmp_path, CFG=cfg, BFCL_ADAPTER_SFT_B_PLUS=str(bare))
    assert proc.returncode == 2 and "missing weights file" in proc.stdout


def test_a_real_submission_ignores_the_adapter_seam() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert 'if [[ "${SELFTEST}" == "1" && -n "${BFCL_ADAPTER_SFT_B_PLUS:-}" ]]; then' in text
    assert "REGISTERED_ADAPTER_SFT_B_PLUS=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b" in text


# ---- replay stems: the planner_alone campaign must be complete ------------------------------------

@pytest.mark.parametrize("name", ["bfcl_plan_zs.yaml", "bfcl_takeover_k5.yaml", "bfcl_prefix_bplus_m6.yaml"])
def test_a_replay_arm_waits_for_a_complete_non_crashed_source(tmp_path: Path, name: str) -> None:
    cfg = str(_variant(tmp_path, name))
    src = tmp_path / "out" / SOURCE_CID
    what = "prefix source" if "prefix" in name else "planner.packet_source"
    wait = f"{what} campaign is not complete; planner_alone_cap81 must complete before the replay arms start"
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)  # not started
    assert proc.returncode == 2 and wait in proc.stdout and f"{what} {src}: exists=0" in proc.stdout
    # One episode short of 50 x 2.
    _write_results(src, [(f"multi_turn_base_{i}", s, None) for i in range(50) for s in (1, 2) if (i, s) != (49, 2)],
                   "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 2 and "non_crashed=99" in proc.stdout
    _write_results(src, [("multi_turn_base_49", 2, "crash")], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 2 and "crashed=1" in proc.stdout
    _write_results(src, [("multi_turn_base_49", 2, None)], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert f"{what} {src}: exists=1 non_crashed=100 crashed=0 unreadable=0" in proc.stdout


def test_a_replay_source_other_than_planner_alone_is_refused(tmp_path: Path) -> None:
    _complete_source(tmp_path)
    other = str(tmp_path / "out" / "j10_planner_alone_cap81_20260924")
    cfg = _variant(tmp_path, "bfcl_takeover_k5.yaml", {"planner": {"packet_source": other}})
    proc = _run(tmp_path, CFG=str(cfg), **CODEX_OK)
    assert proc.returncode == 2 and f"replay source {other} is not" in proc.stdout


def _planless(src: Path, keys: list[tuple[str, int]]) -> None:
    """Give these (already scored) source episodes an events.jsonl whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = src / "planner_alone" / str(seed) / task
        (ep / "events.jsonl").write_text(json.dumps({"event_type": "run_start", "payload": {}}) + "\n",
                                         encoding="utf-8")


def test_planless_source_episodes_are_listed_and_capped_at_5_percent(tmp_path: Path) -> None:
    src = _complete_source(tmp_path)
    cfg = str(_variant(tmp_path, "bfcl_advise_k5_neutral.yaml"))
    _planless(src, [("multi_turn_base_3", 2), ("multi_turn_base_7", 1)])
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    # 5 % of 100 = 5, by hand.
    assert "planner_alone episodes scored without a plan: 2 (cap 5, as J10 A1 §4.2): 1/multi_turn_base_7 2/multi_turn_base_3" in proc.stdout
    _planless(src, [(f"multi_turn_base_{i}", 1) for i in range(20, 24)])  # 6 in all
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 2 and "6 planner_alone episodes wrote no plan, above the cap of 5" in proc.stdout


# ---- the tally ---------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_tally_counts_and_error_types(tmp_path: Path) -> None:
    cid = "bfcl_selftest_dev_x"
    rows = [
        ("multi_turn_base_1", {"error_type": None, "success": True, "tgc": 1.0, "goal_pass_rate": 1.0}),
        ("multi_turn_base_2", {"error_type": "parse_error", "success": False, "tgc": 0.0, "goal_pass_rate": 0.5}),
        ("multi_turn_base_3", {"error_type": "crash", "success": False, "tgc": None, "goal_pass_rate": None}),
    ]
    for task, row in rows:
        d = tmp_path / "out" / cid / "executor_alone" / "1" / task
        d.mkdir(parents=True)
        (d / "result.json").write_text(json.dumps({"seed": 1, "task_id": task, **row}))
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", CID=cid, TASKS="3", SEEDS="1")
    # Hand count: 3 files, 1 crash, so 2 non-crashed of a target of 3 -> incomplete (3).
    assert proc.returncode == 3, _out(proc)
    assert "result_files=3 non_crashed=2 crashed=1 target=3" in proc.stdout
    # tgc (1 + 0 + null->0) / 3; goal_pass_rate (1 + 0.5 + null->0) / 3 = 0.5. jq versions print
    # 1/3 with 16 or 17 digits, so only the stable prefix is checked.
    assert "n=3 success=1 tgc_mean=0.333" in proc.stdout
    assert "goal_pass_rate_mean=0.5 crashed=1" in proc.stdout
    for line in ("1\tcrash", "1\tnone", "1\tparse_error"):
        assert line in proc.stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_tally_counts_unreadable_other_seed_and_orphans_then_completes(tmp_path: Path) -> None:
    cid = "bfcl_selftest_dev_y"
    root = tmp_path / "out" / cid
    _write_results(root, [("t0", 1, None), ("t0", 2, "limit"), ("t1", 1, None), ("t9", 3, None)], "fixed_k")
    (root / "fixed_k" / "2" / "t1").mkdir(parents=True)
    (root / "fixed_k" / "2" / "t1" / "result.json").write_text("{trunc", encoding="utf-8")
    (root / "fixed_k" / "1" / "t2").mkdir(parents=True)
    (root / "fixed_k" / "1" / "t2" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    env = dict(BFCL_SELFTEST_STAGE="tally", CID=cid, TASKS="2")
    proc = _run(tmp_path, **env)
    # Hand count: 5 files; 1 unreadable; seeds 1,2 hold t0/1, t0/2 (limit is scored), t1/1 = 3; t9 seed 3 is
    # other_seed; t2/1 has events but no result.
    assert proc.returncode == 3, _out(proc)
    assert ("result_files=5 non_crashed=3 crashed=0 target=4 unreadable=1 other_seed=1 attempts_without_result=1"
            in proc.stdout)
    (root / "fixed_k" / "2" / "t1" / "result.json").write_text(json.dumps({"seed": 2, "error_type": None}))
    proc = _run(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "COMPLETE: 4/4 non-crashed, 0 crashed" in proc.stdout


# ---- MAX_PLANNER_CALLS (ported from hj12_live.pbs) ----------------------------------------------

def test_spend_guard_projects_from_the_rate_campaign(tmp_path: Path) -> None:
    cfg = str(_variant(tmp_path, "bfcl_planner_alone_cap81.yaml"))
    cid = "bfcl_planner_alone_cap81_dev_20260924"
    smoke = f"{cid}_smoke_1"
    # Smoke: 2 episodes, 30 live calls -> 15 per episode.
    _write_results(tmp_path / "out" / smoke, [("a", 1, None), ("b", 1, None)], "planner_alone",
                   totals={"planner_calls_total": 15})
    env = dict(CFG=cfg, BFCL_SELFTEST_STAGE="spend", BFCL_SPEND_RATE_CID=smoke, **CODEX_OK)
    # By hand: 0 spent + ceil(15 x 100 x 1.2) = 1800 > 1600 -> refused (exit 1).
    proc = _run(tmp_path, **env)
    assert proc.returncode == 1, _out(proc)
    assert "live_so_far=0 (ledger 0 minus cached plans) episodes=0 rate_from=" in proc.stdout
    assert "projection=1800 ceiling=1600" in proc.stdout
    # A raised ceiling passes: 1800 <= 2000.
    proc = _run(tmp_path, MAX_PLANNER_CALLS="2000", **env)
    assert proc.returncode == 0 and "selftest spend guard passed" in proc.stdout, _out(proc)
    # Resume: 90 episodes already spent 900 calls (10 each); 10 missing -> ceil(10 x 10 x 1.2) = 120; 1020 <= 1600.
    _write_results(tmp_path / "out" / cid, [(f"t{i}", s, None) for i in range(45) for s in (1, 2)],
                   "planner_alone", totals={"planner_calls_total": 10})
    proc = _run(tmp_path, CFG=cfg, BFCL_SELFTEST_STAGE="spend", **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert "live_so_far=900 (ledger 900 minus cached plans) episodes=90" in proc.stdout
    assert "missing=10 projection=120 ceiling=1600" in proc.stdout


def test_spend_guard_does_not_count_a_replayed_plan_as_a_hosted_call(tmp_path: Path) -> None:
    # loop.py:465 charges the cached plan as n_calls=1, so the ledger says 4 per episode where 3 were bought.
    _complete_source(tmp_path)
    cfg = str(_variant(tmp_path, "bfcl_takeover_k5.yaml"))
    smoke = "bfcl_takeover_k5_dev_20260924_smoke_1"
    root = tmp_path / "out" / smoke
    _write_results(root, [("a", 1, None), ("b", 1, None)], "fixed_k", totals={"planner_calls_total": 4})
    plan = {"event_type": "plan", "actor": "planner", "usage": {"provider": "cache", "model": "gpt-5.6-luna", "n_calls": 1}}
    for task in ("a", "b"):
        (root / "fixed_k" / "1" / task / "events.jsonl").write_text(json.dumps(plan) + "\n", encoding="utf-8")
    proc = _run(tmp_path, CFG=cfg, BFCL_SELFTEST_STAGE="spend", BFCL_SPEND_RATE_CID=smoke, **CODEX_OK)
    # By hand: (8 - 2) / 2 = 3 per episode; ceil(3 x 100 x 1.2) = 360 <= 400. The raw ledger would give 480.
    assert proc.returncode == 0, _out(proc)
    assert "rate=6/2 missing=100 projection=360 ceiling=400" in proc.stdout
