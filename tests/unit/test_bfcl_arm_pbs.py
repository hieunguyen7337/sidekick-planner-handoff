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
import tempfile
from pathlib import Path

import pytest
import yaml

from sidekick.environments.bfcl_env import bfcl_task_ids

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "bfcl_arm.pbs"
CFG = REPO / "configs" / "bfcl_executor_alone_zs.yaml"
SOURCE_CID = "bfcl_planner_alone_cap81_dev_20260924"
REGISTERED_SOURCE = f"/scratch/n12194778/sidekick/results/{SOURCE_CID}"
# The 50 dev entries in the order the runner takes them; the source gate checks these (seed, task) keys.
DEV_IDS = bfcl_task_ids("dev", 0)
QWEN = "Qwen/Qwen3-8B"
MIB = 1024 * 1024
# The third receiver, zero-shot Qwen3-8B: new stem -> its zs sibling.
QZS_SIBLING = {
    "bfcl_executor_alone_qzs.yaml": "bfcl_executor_alone_zs.yaml",
    "bfcl_plan_qzs.yaml": "bfcl_plan_zs.yaml",
    "bfcl_takeover_k5_qzs.yaml": "bfcl_takeover_k5.yaml",
    "bfcl_advise_k5_fullctx_qzs.yaml": "bfcl_advise_k5_fullctx.yaml",
    "bfcl_advise_k5_neutral_qzs.yaml": "bfcl_advise_k5_neutral.yaml",
    **{f"bfcl_prefix_qzs_m{m}.yaml": f"bfcl_prefix_zs_m{m}.yaml" for m in (2, 4, 6)},
}
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
SYSTEM_OF.update({qzs: SYSTEM_OF[zs] for qzs, zs in QZS_SIBLING.items()})
HOSTED = {"bfcl_planner_alone_cap81.yaml", "bfcl_plan_zs.yaml", "bfcl_takeover_k5.yaml",
          "bfcl_advise_k5_fullctx.yaml", "bfcl_advise_k5_neutral.yaml"}
HOSTED |= {qzs for qzs, zs in QZS_SIBLING.items() if zs in HOSTED}
CODEX_OK = {"EXPECTED_CODEX_VERSION": "0.153.4"}


def _receiver(name: str) -> str:
    if "planner_alone" in name:
        return "none"
    return "qzs" if "qzs" in name else ("bplus" if "bplus" in name else "zs")


def _qwen_cache(root: Path, shard: str = "real", ref: str = "b968826d") -> Path:
    """An HF_HOME holding Qwen/Qwen3-8B as the hub lays it out: refs/main -> snapshot -> symlink -> blob.

    shard: "real" (1 MiB written, fsynced), "stub" (a 512-byte pointer), "sparse" (8 MiB apparent, nothing
    allocated) or "none" (no *.safetensors).
    """
    repo = root / "hub" / "models--Qwen--Qwen3-8B"
    snap = repo / "snapshots" / ref
    if (snap / "config.json").is_file():
        return root
    (repo / "refs").mkdir(parents=True)
    (repo / "blobs").mkdir()
    snap.mkdir(parents=True)
    (repo / "refs" / "main").write_text(ref, encoding="utf-8")
    (snap / "config.json").write_text("{}", encoding="utf-8")
    if shard != "none":
        blob = repo / "blobs" / "0123abcd"
        with open(blob, "wb") as fh:
            if shard == "sparse":
                fh.truncate(8 * MIB)
            else:
                fh.write(os.urandom(512 if shard == "stub" else MIB))
                fh.flush()
                os.fsync(fh.fileno())
        (snap / "model-00001-of-00001.safetensors").symlink_to(blob)
    return root


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
                "BFCL_SELFTEST_STAGE", "BFCL_SPEND_RATE_CID", "PBS_JOBID", "CFG", "SMOKE_TASKS", "HF_HUB_OFFLINE"):
        full.pop(key, None)
    full.update({"BFCL_SELFTEST": "1", "BFCL_REPO": str(REPO), "BFCL_OUT": str(tmp / "out"),
                 "BFCL_LOGDIR": str(tmp / "logs"), "PY": sys.executable,
                 "BFCL_ADAPTER_SFT_B_PLUS": str(_adapter(tmp)),
                 "BFCL_QWEN_HF_HOME": str(_qwen_cache(tmp / "qwen_hf"))})
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
    _write_results(src, [(t, s, None) for t in DEV_IDS[:n_tasks] for s in seeds], "planner_alone")
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
        # The test split is gated (tests/unit/test_bfcl_arm_pbs_test_path.py); without the token it is refused.
        ({"SPLIT": "test"}, "SPLIT=test needs BFCL_CONFIRM=E_FROZEN (got '<unset>'"),
        ({"SPLIT": "test_normal"}, "SPLIT=test_normal is not a BFCL split: dev, or test behind BFCL_CONFIRM=E_FROZEN"),
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
    receiver = _receiver(name)
    assert f"system={SYSTEM_OF[name]} cid={stem}_dev_20260924 receiver={receiver} target=100" in line
    if name in HOSTED:
        assert line.endswith("gate=--gate --expect-planner --expect-model gpt-5.6-luna")
        assert "MAX_PLANNER_CALLS=" in proc.stdout
    else:
        assert line.endswith("gate=--gate")  # zero live planner calls
    if receiver == "bplus":
        assert "lora-module sft_b_plus=" in proc.stdout
    else:
        assert "lora-module" not in proc.stdout
    if receiver == "qzs":
        assert f"qzs receiver: HF_HOME={tmp_path / 'qwen_hf'} HF_HUB_OFFLINE=1" in proc.stdout
        assert f"{QWEN} weights: 1 shards, {MIB} bytes" in proc.stdout
    else:
        assert "qzs receiver" not in proc.stdout and f"{QWEN} weights" not in proc.stdout


# ---- the third receiver, qzs: zero-shot Qwen3-8B ---------------------------------------------------

@pytest.mark.parametrize("name", sorted(QZS_SIBLING))
def test_a_qzs_stem_registers_what_its_zs_sibling_does(tmp_path: Path, name: str) -> None:
    # Same system, hosted gate and default ceiling as the sibling; only the receiver differs.
    _complete_source(tmp_path)
    got = {}
    for cfg in (name, QZS_SIBLING[name]):
        proc = _run(tmp_path, CFG=str(_variant(tmp_path, cfg)), **CODEX_OK)
        assert proc.returncode == 0, _out(proc)
        line = next(l for l in proc.stdout.splitlines() if "selftest preflight ok" in l)
        ceiling = [l.split("MAX_PLANNER_CALLS=")[1].split()[0] for l in proc.stdout.splitlines()
                   if l.startswith("[bfcl] MAX_PLANNER_CALLS=")]
        got[cfg] = (line.replace(cfg[5:-5], "<stem>").replace("receiver=qzs", "receiver=zs"), ceiling)
    assert got[name] == got[QZS_SIBLING[name]]


@pytest.mark.parametrize(
    "name, edit, message",
    [
        # The refusal the brief names: a qzs config whose model is granite.
        ("bfcl_executor_alone_qzs.yaml", {"executor": {"model": "ibm-granite/granite-4.2-8b"}},
         "executor.model=ibm-granite/granite-4.2-8b, expected Qwen/Qwen3-8B: executor_alone_qzs is the zero-shot Qwen3-8B receiver"),
        ("bfcl_plan_qzs.yaml", {"executor": {"model": "ibm-granite/granite-4.2-8b"}}, "expected Qwen/Qwen3-8B"),
        ("bfcl_prefix_qzs_m4.yaml", {"executor": {"model": "Qwen/Qwen3-32B"}}, "expected Qwen/Qwen3-8B"),
        ("bfcl_takeover_k5_qzs.yaml", {"executor": {"lora_name": "sft_b_plus_qwen8b"}}, "this arm is zero-shot (null)"),
        ("bfcl_executor_alone_qzs.yaml", {"executor": {"type": "mock"}}, "executor.type=mock, expected vllm"),
        # The zs receiver still refuses Qwen, and qzs keeps its sibling's channel facts.
        ("bfcl_prefix_zs_m2.yaml", {"executor": {"model": QWEN}}, "expected ibm-granite/granite-4.2-8b"),
        ("bfcl_advise_k5_neutral_qzs.yaml", {"planner": {"correct_prompt": "correction"}}, "registers neutral"),
        ("bfcl_takeover_k5_qzs.yaml", {"takeover": None}, "takeover=0, but takeover_k5_qzs registers takeover=1"),
        ("bfcl_prefix_qzs_m6.yaml", {"handoff": {"m": 2}}, "handoff.m=2, but prefix_qzs_m6 registers m=6"),
        ("bfcl_executor_alone_qzs.yaml", {"campaign_id": "bfcl_executor_alone_zs_dev_20260924"},
         "is not bfcl_executor_alone_qzs_dev_20260924"),
    ],
)
def test_qzs_receiver_refusals(tmp_path: Path, name: str, edit: dict, message: str) -> None:
    _complete_source(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, name, edit)), **CODEX_OK)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


@pytest.mark.parametrize(
    "shard, message",
    [
        ("stub", "is 512 bytes: an LFS pointer stub, not weights"),
        ("none", "holds no *.safetensors"),
    ],
)
def test_qwen_weights_must_be_real_in_the_hf_cache(tmp_path: Path, shard: str, message: str) -> None:
    bad = _qwen_cache(tmp_path / f"hf_{shard}", shard=shard)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_executor_alone_qzs.yaml")), BFCL_QWEN_HF_HOME=str(bad))
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


@pytest.fixture
def hole_dir(tmp_path: Path):
    """A directory whose filesystem reports a hole as unallocated. /tmp on the compute nodes is wekafs, which
    reports a truncated 8 MiB file as 8 MiB allocated (job 25867829), so /dev/shm (tmpfs) is tried first."""
    made = None
    candidates = [tmp_path]
    if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
        made = Path(tempfile.mkdtemp(prefix="bfcl_hole_", dir="/dev/shm"))
        candidates.insert(0, made)
    try:
        for d in candidates:
            probe = d / "probe"
            with open(probe, "wb") as fh:
                fh.truncate(8 * MIB)
            holey = probe.stat().st_blocks * 512 * 2 < 8 * MIB
            probe.unlink()
            if holey:
                yield d
                return
        pytest.skip("no writable filesystem here reports a hole as unallocated")
    finally:
        if made is not None:
            shutil.rmtree(made, ignore_errors=True)


def test_sparse_qwen_weights_are_refused(tmp_path: Path, hole_dir: Path) -> None:
    # An 8 MiB hole: nothing (or a metadata block or two) allocated, well under half.
    bad = _qwen_cache(hole_dir / "hf_sparse", shard="sparse")
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_executor_alone_qzs.yaml")), BFCL_QWEN_HF_HOME=str(bad))
    assert proc.returncode == 2 and "are sparse: " in proc.stdout, _out(proc)
    assert f"of {8 * MIB} bytes allocated; they would load as zeros" in proc.stdout


def test_qwen_must_be_cached_at_all(tmp_path: Path) -> None:
    empty = tmp_path / "empty_hf"
    empty.mkdir()
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_executor_alone_qzs.yaml")), BFCL_QWEN_HF_HOME=str(empty))
    assert proc.returncode == 2 and f"Qwen/Qwen3-8B is not cached under HF_HOME={empty}" in proc.stdout, _out(proc)
    # A granite arm never looks at the Qwen cache.
    proc = _run(tmp_path, BFCL_QWEN_HF_HOME=str(empty))
    assert proc.returncode == 0, _out(proc)


def test_a_real_submission_serves_qwen_from_the_home_cache() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert 'if [[ "${SELFTEST}" == "1" && -n "${BFCL_QWEN_HF_HOME:-}" ]]; then' in text
    assert 'REGISTERED_QWEN_HF_HOME="${HOME}/.cache/huggingface"' in text
    assert "MODEL_QWEN=Qwen/Qwen3-8B" in text
    # The serve line is the one hj12_prefix.pbs gives AppWorld's zero-shot Qwen arms, flag for flag.
    serve = ('--served-model-name "${MODEL}" \\\n    --dtype bfloat16 \\\n    --max-model-len 32768 \\\n'
             '    --host 127.0.0.1 --port "${VLLM_PORT}" \\\n    --gpu-memory-utilization 0.85 \\\n')
    assert serve in text and serve in (REPO / "scripts" / "pbs" / "hj12_prefix.pbs").read_text(encoding="utf-8")
    assert "reasoning-parser" not in text.replace("Do NOT add reasoning-parser flags", "")


# ---- seeds 1,2,3 -------------------------------------------------------------------------------

def test_seeds_1_2_3_scale_the_target_and_the_smoke_keeps_the_first_seed(tmp_path: Path) -> None:
    proc = _run(tmp_path, SEEDS="1,2,3")
    assert proc.returncode == 0, _out(proc)
    # By hand: 50 tasks x 3 seeds = 150; the smoke is 2 entries at seed 1.
    assert "target=150 (50 tasks x 3 seeds) seeds=1,2,3 smoke=2 tasks x seed 1" in proc.stdout
    assert "target=150 gate=--gate" in proc.stdout
    proc = _run(tmp_path, SEEDS="3,1,2", TASKS="1")
    assert proc.returncode == 0, _out(proc)
    # 1 task x 3 seeds = 3; the default 2-entry smoke is capped at the 1 task run, at the first listed seed.
    assert "SMOKE_TASKS=2 exceeds the 1 tasks run; smoke capped at 1" in proc.stdout
    assert "target=3 (1 tasks x 3 seeds) seeds=3,1,2 smoke=1 tasks x seed 3" in proc.stdout


@pytest.mark.parametrize(
    "env, message",
    [
        ({"SEEDS": "1,2,2"}, "SEEDS=1,2,2 repeats a seed"),
        ({"SEEDS": "01,2,3"}, "SEEDS must look like 1,2 or 1,2,3 (comma-separated, no leading zeros)"),
        ({"SEEDS": "1,2,"}, "SEEDS must look like"),
        ({"SMOKE_TASKS": "0"}, "SMOKE_TASKS must be a positive integer, got 0"),
    ],
)
def test_seed_and_smoke_refusals(tmp_path: Path, env: dict, message: str) -> None:
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)


def test_the_default_ceiling_scales_with_seeds_1_2_3(tmp_path: Path) -> None:
    _complete_source(tmp_path, seeds=(1, 2, 3))
    # Hand values at 150 episodes: planner_alone 16 x 150, a channel arm 4 x 150, a plan arm 2 x 150.
    for name, want in (("bfcl_planner_alone_cap81.yaml", 2400), ("bfcl_takeover_k5.yaml", 600),
                       ("bfcl_advise_k5_neutral_qzs.yaml", 600), ("bfcl_plan_zs.yaml", 300),
                       ("bfcl_plan_qzs.yaml", 300)):
        proc = _run(tmp_path, CFG=str(_variant(tmp_path, name)), SEEDS="1,2,3", **CODEX_OK)
        assert proc.returncode == 0, _out(proc)
        assert f"MAX_PLANNER_CALLS={want} " in proc.stdout and "x 150) safety=1.2" in proc.stdout, _out(proc)


@pytest.mark.parametrize("name", ["bfcl_plan_qzs.yaml", "bfcl_prefix_qzs_m2.yaml", "bfcl_advise_k5_fullctx.yaml"])
def test_the_source_gate_counts_the_requested_seeds(tmp_path: Path, name: str) -> None:
    cfg = str(_variant(tmp_path, name))
    src = tmp_path / "out" / SOURCE_CID
    what = "prefix source" if "prefix" in name else "planner.packet_source"
    _complete_source(tmp_path, seeds=(1, 2))
    # A source complete at seeds 1,2 serves SEEDS=1,2 but not 1,2,3: 100 < 150 and no seed-3 key.
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert f"{what} {src}: exists=1 non_crashed=100 crashed=0 unreadable=0 missing_keys=0/100 (need >= 100" in proc.stdout
    proc = _run(tmp_path, CFG=cfg, SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 2, _out(proc)
    assert "non_crashed=100 crashed=0 unreadable=0 missing_keys=50/150 (need >= 150 non-crashed for seeds 1,2,3" in proc.stdout
    assert "first missing <seed>/<task> keys: 3/" in proc.stdout
    assert "planner_alone_cap81 must complete before the replay arms start" in proc.stdout
    # Seed 3 run for 49 of the 50 entries: 149, still refused; the 50th completes it.
    _write_results(src, [(t, 3, None) for t in DEV_IDS[:49]], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 2 and "non_crashed=149 crashed=0 unreadable=0 missing_keys=1/150" in proc.stdout
    assert f"first missing <seed>/<task> keys: 3/{DEV_IDS[49]}" in proc.stdout
    _write_results(src, [(DEV_IDS[49], 3, None)], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert "non_crashed=150 crashed=0 unreadable=0 missing_keys=0/150 (need >= 150" in proc.stdout


def test_a_count_that_covers_the_target_does_not_excuse_a_missing_seed(tmp_path: Path) -> None:
    # TASKS=30 SEEDS=1,2,3 needs 90 episodes; a 1,2 source holds 100 of seeds {1,2,3}, so the count
    # alone passes, but none of the 30 seed-3 keys exists and every one of those episodes would abort.
    _complete_source(tmp_path, seeds=(1, 2))
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_takeover_k5_qzs.yaml")), TASKS="30", SEEDS="1,2,3",
                **CODEX_OK)
    assert proc.returncode == 2, _out(proc)
    assert "non_crashed=100 crashed=0 unreadable=0 missing_keys=30/90 (need >= 90" in proc.stdout


def test_the_planless_cap_is_5_percent_of_150_at_seeds_1_2_3(tmp_path: Path) -> None:
    src = _complete_source(tmp_path, seeds=(1, 2, 3))
    cfg = str(_variant(tmp_path, "bfcl_advise_k5_fullctx_qzs.yaml"))
    # 5 % of 150 = 7.5, so 7 planless keys pass and the 8th is refused ("more than 5 %"). Seed 3 counts.
    _planless(src, [(t, 3) for t in DEV_IDS[:7]])
    proc = _run(tmp_path, CFG=cfg, SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert "planner_alone episodes scored without a plan: 7 (cap 7, as J10 A1 §4.2)" in proc.stdout
    # The same source at the default seeds 1,2: cap 5, and the seed-3 keys are not this arm's.
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0 and "scored without a plan: 0 (cap 5," in proc.stdout, _out(proc)
    _planless(src, [(DEV_IDS[7], 1)])
    proc = _run(tmp_path, CFG=cfg, SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 2
    assert "8 planner_alone episodes wrote no plan, above the cap of 7 (5 % of 150)" in proc.stdout


def test_the_planless_count_ignores_keys_outside_the_tasks_run(tmp_path: Path) -> None:
    src = _complete_source(tmp_path, seeds=(1, 2, 3))
    _planless(src, [(DEV_IDS[40], 1), (DEV_IDS[41], 2), (DEV_IDS[2], 3)])
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, "bfcl_plan_qzs.yaml")), TASKS="10", SEEDS="1,2,3", **CODEX_OK)
    # 10 tasks x 3 seeds = 30, cap 1; only DEV_IDS[2] at seed 3 is one of this arm's keys.
    assert proc.returncode == 0, _out(proc)
    assert f"scored without a plan: 1 (cap 1, as J10 A1 §4.2): 3/{DEV_IDS[2]}" in proc.stdout


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
    _planless(src, [(DEV_IDS[3], 1)])
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
    _write_results(src, [(t, s, None) for i, t in enumerate(DEV_IDS) for s in (1, 2) if (i, s) != (49, 2)],
                   "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 2 and "non_crashed=99" in proc.stdout and "missing_keys=1/100" in proc.stdout
    _write_results(src, [(DEV_IDS[49], 2, "crash")], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 2 and "crashed=1" in proc.stdout
    _write_results(src, [(DEV_IDS[49], 2, None)], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert f"{what} {src}: exists=1 non_crashed=100 crashed=0 unreadable=0 missing_keys=0/100" in proc.stdout


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
    _planless(src, [(DEV_IDS[3], 2), (DEV_IDS[7], 1)])
    proc = _run(tmp_path, CFG=cfg, **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    # 5 % of 100 = 5, by hand. Listed seed-first, as planless_source_keys sorts the paths.
    assert (f"planner_alone episodes scored without a plan: 2 (cap 5, as J10 A1 §4.2): 1/{DEV_IDS[7]} 2/{DEV_IDS[3]}"
            in proc.stdout)
    _planless(src, [(t, 1) for t in DEV_IDS[20:24]])  # 6 in all
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


def test_spend_guard_at_seeds_1_2_3_projects_150_episodes_against_2400(tmp_path: Path) -> None:
    cfg = str(_variant(tmp_path, "bfcl_planner_alone_cap81.yaml"))
    cid = "bfcl_planner_alone_cap81_dev_20260924"
    smoke = f"{cid}_smoke_1"
    _write_results(tmp_path / "out" / smoke, [("a", 1, None), ("b", 1, None)], "planner_alone",
                   totals={"planner_calls_total": 15})
    env = dict(CFG=cfg, BFCL_SELFTEST_STAGE="spend", BFCL_SPEND_RATE_CID=smoke, SEEDS="1,2,3", **CODEX_OK)
    # By hand: 15/episode; ceil(15 x 150 x 1.2) = 2700 > 16 x 150 = 2400 -> refused.
    proc = _run(tmp_path, **env)
    assert proc.returncode == 1 and "missing=150 projection=2700 ceiling=2400" in proc.stdout, _out(proc)
    # Extending a finished 1,2 campaign to 1,2,3: 100 episodes spent 1000 (10 each); 50 missing ->
    # ceil(10 x 50 x 1.2) = 600; 1000 + 600 = 1600 <= 2400.
    _write_results(tmp_path / "out" / cid, [(t, s, None) for t in DEV_IDS for s in (1, 2)],
                   "planner_alone", totals={"planner_calls_total": 10})
    proc = _run(tmp_path, CFG=cfg, BFCL_SELFTEST_STAGE="spend", SEEDS="1,2,3", **CODEX_OK)
    assert proc.returncode == 0, _out(proc)
    assert "live_so_far=1000 (ledger 1000 minus cached plans) episodes=100" in proc.stdout
    assert "missing=50 projection=600 ceiling=2400" in proc.stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_tally_completes_at_seeds_1_2_3_and_calls_seed_3_other_at_the_default(tmp_path: Path) -> None:
    cid = "bfcl_selftest_dev_s3"
    _write_results(tmp_path / "out" / cid, [(t, s, None) for t in ("t0", "t1") for s in (1, 2, 3)], "executor_alone")
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", CID=cid, TASKS="2", SEEDS="1,2,3")
    assert proc.returncode == 0, _out(proc)
    assert "result_files=6 non_crashed=6 crashed=0 target=6 unreadable=0 other_seed=0" in proc.stdout
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", CID=cid, TASKS="2")
    assert proc.returncode == 0, _out(proc)
    assert "result_files=6 non_crashed=4 crashed=0 target=4 unreadable=0 other_seed=2" in proc.stdout
