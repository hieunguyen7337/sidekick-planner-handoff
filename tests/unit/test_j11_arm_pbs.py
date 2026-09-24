"""scripts/pbs/j11_arm.pbs refusals, smoke guard and tally, via its J11_SELFTEST seam.

The self-test runs every refusal check and then exits before a lock, a vLLM server, a purge or a
runner. Nothing under /scratch/n12194778/sidekick/results is read or written: J11_OUT / J11_LOGDIR
point into tmp_path, every config that names C's registered path is copied with that path moved
under tmp_path, and the git checks run against a throwaway repository (J11_GIT_ROOT).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "j11_arm.pbs"
FROZEN_LINE = "**Status**: **FROZEN** 2026-09-25, commit abc1234."
# The J11 prereg's own DRAFT line (docs/prereg_j11_lp2_test_20260924.md:3 on 2026-09-24).
DRAFT_LINE = ("**Status**: DRAFT — becomes FROZEN on commit, before any `test_normal` episode of "
              "J10 or J11 exists.")
C_NAME = "j11_planner_alone_cap81_qwen38_27b_20260924"
C_REAL = f"/scratch/n12194778/sidekick/results/{C_NAME}"
C_CFG = "j11_planner_alone_cap81_qwen38_27b.yaml"
P27 = "Qwen/Qwen3.8-27B-FP8"
REGISTERED_ADAPTER = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b"
PLAN_ARMS = ("j11_takeover_fixed_k_10.yaml", "j11_advise_fixed_k_10_fullctx.yaml",
             "j11_advise_fixed_k_1_fullctx.yaml")
PREFIX_ARMS = ("j11_prefix_bplus_m6.yaml", "j11_prefix_bplus_m11.yaml", "j11_prefix_zs_m6.yaml",
               "j11_prefix_zs_m11.yaml")
SYSTEM_OF = {C_CFG: "planner_alone", **{n: "fixed_k" for n in PLAN_ARMS},
             **{n: "prefix_handoff" for n in PREFIX_ARMS}}
EXPECT = f"--expect-model {P27}"


def run_pbs(tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "DRYRUN", "SYSTEM", "J11_CONFIRM", "J11_PREREG",
                "J11_GIT_ROOT", "J11_SELFTEST_STAGE", "J11_GUARD_CID", "PBS_JOBID",
                "ADAPTER_SFT_B_PLUS", "ALIAS_SFT_B_PLUS", "CUDA_VISIBLE_DEVICES"):
        env.pop(key, None)
    env.update(
        J11_SELFTEST="1",
        J11_REPO=str(REPO),
        J11_OUT=str(tmp_path / "out"),
        J11_LOGDIR=str(tmp_path / "logs"),
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


def _preflight(proc: subprocess.CompletedProcess[str]) -> str:
    return next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)


def _prereg(tmp_path: Path, *status_lines: str) -> Path:
    path = tmp_path / "prereg.md"
    path.write_text("# J11\n\n" + "\n".join(status_lines) + "\n\nbody\n", encoding="utf-8")
    return path


def _test_normal(tmp_path: Path, line: str = FROZEN_LINE) -> dict[str, str]:
    return dict(SPLIT="test_normal", J11_CONFIRM="J11_FROZEN", J11_PREREG=str(_prereg(tmp_path, line)))


def _relocated(tmp_path: Path, name: str, replace: tuple[str, str] | None = None) -> tuple[Path, Path]:
    """The config with C's registered path moved under tmp_path; returns (config, C's directory)."""
    src = tmp_path / "out" / C_NAME
    text = (REPO / "configs" / name).read_text(encoding="utf-8").replace(C_REAL, str(src))
    if replace:
        assert replace[0] in text
        text = text.replace(replace[0], replace[1])
    cfg = tmp_path / "cfg" / name
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text, encoding="utf-8")
    return cfg, src


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str = "planner_alone") -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps(
            {"task_id": task, "seed": seed, "error_type": err}) + "\n", encoding="utf-8")


def _complete(src: Path, n_tasks: int, seeds: tuple[int, ...] = (1, 2)) -> None:
    _write_results(src, [(f"t{i}", s, None) for i in range(n_tasks) for s in seeds])


def _planless(src: Path, keys: list[tuple[str, int]]) -> None:
    """Give these (already scored) C episodes an events.jsonl whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = src / "planner_alone" / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "events.jsonl").write_text(
            json.dumps({"event_type": "run_start", "payload": {}}) + "\n"
            + json.dumps({"event_type": "parse_error", "payload": {"text": "?"}}) + "\n",
            encoding="utf-8")


# ---- the file itself ------------------------------------------------------------------------

def test_bash_syntax():
    assert subprocess.run(["bash", "-n", str(PBS)]).returncode == 0


def test_select_line_and_header_qsub_lines():
    text = PBS.read_text(encoding="utf-8")
    head = text.splitlines()[:7]
    # The #PBS default is the replay arms' two cards; C's lines ask for one.
    assert "#PBS -l select=1:ncpus=12:ngpus=2:gpu_id=H100:mem=96gb" in head
    assert "#PBS -l walltime=10:00:00" in head
    one, two = (f"-l select=1:ncpus=12:ngpus={n}:gpu_id=H100:mem=96gb" for n in (1, 2))
    tail = ",SPLIT=test_normal,J11_CONFIRM=J11_FROZEN scripts/pbs/j11_arm.pbs"
    assert f"#     qsub {one} -l walltime=10:00:00 -v CFG=configs/{C_CFG}{tail}" in text
    assert f"#     qsub {one} -v CFG=configs/{C_CFG},DRYRUN=1 scripts/pbs/j11_arm.pbs" in text
    assert f"#     qsub {two} -l walltime=10:00:00 -v CFG=configs/j11_takeover_fixed_k_10.yaml{tail}" in text
    assert "#     qsub -v CFG=configs/j11_takeover_fixed_k_10.yaml,DRYRUN=1 scripts/pbs/j11_arm.pbs" in text
    qsubs = [l for l in text.splitlines() if l.startswith("#     qsub ")]
    assert all(("ngpus=1" in l) == (C_CFG in l) for l in qsubs), qsubs


def test_system_table_covers_every_j11_config():
    assert sorted(p.name for p in (REPO / "configs").glob("j11_*.yaml")) == sorted(SYSTEM_OF)


# ---- (a) the split and the freeze -----------------------------------------------------------

def test_test_challenge_is_always_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", SPLIT="test_challenge", J11_CONFIRM="J11_FROZEN",
                   J11_PREREG=str(_prereg(tmp_path, FROZEN_LINE)))
    assert proc.returncode == 2, _out(proc)
    assert "test_challenge is never read" in _out(proc)


def test_the_j11_draft_status_line_is_refused_although_it_contains_frozen(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", **_test_normal(tmp_path, DRAFT_LINE))
    assert proc.returncode == 2, _out(proc)
    assert "J11 is not FROZEN" in _out(proc)


def test_a_frozen_line_that_mentions_draft_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}",
                   **_test_normal(tmp_path, "**Status**: FROZEN, superseding the DRAFT of 2026-09-24."))
    assert proc.returncode == 2 and "still mentions DRAFT" in _out(proc), _out(proc)


def test_a_second_status_line_is_refused(tmp_path: Path):
    prereg = _prereg(tmp_path, FROZEN_LINE, "**Status**: FROZEN again")
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", SPLIT="test_normal", J11_CONFIRM="J11_FROZEN",
                   J11_PREREG=str(prereg))
    assert proc.returncode == 2, _out(proc)
    assert "expected exactly one **Status** line" in _out(proc) and "found 2" in _out(proc)


def test_frozen_prereg_still_needs_the_confirmation_token(tmp_path: Path):
    prereg = str(_prereg(tmp_path, FROZEN_LINE))
    for token in ("", "yes", "A1_FROZEN"):
        proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", SPLIT="test_normal", J11_PREREG=prereg,
                       J11_CONFIRM=token)
        assert proc.returncode == 2 and "J11_CONFIRM=J11_FROZEN" in _out(proc), _out(proc)
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", SPLIT="test_normal", J11_PREREG=prereg,
                   J11_CONFIRM="J11_FROZEN")
    assert proc.returncode == 0, _out(proc)
    line = _preflight(proc)
    assert f"system=planner_alone cid={C_NAME} split=test_normal target=336" in line
    assert line.endswith(f"gate=--gate --expect-planner {EXPECT}")
    assert f"planner model from config: {P27}" in _out(proc)


@pytest.mark.parametrize("extra,why", [
    ({"TASKS": "10"}, "registered at all 168 tasks"),
    ({"TASKS": "167"}, "registered at all 168 tasks"),
    ({"SEEDS": "1,2,3"}, "registered at seeds 1,2"),
    ({"SEEDS": "1"}, "registered at seeds 1,2"),
    ({"SEEDS": "2,1"}, "registered at seeds 1,2"),
    ({"CID": "j11_other"}, "must write the registered campaign id"),
])
def test_test_normal_refuses_a_partial_or_renamed_read(tmp_path: Path, extra: dict, why: str):
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", **_test_normal(tmp_path), **extra)
    assert proc.returncode == 2, _out(proc)
    assert why in _out(proc)


def test_test_normal_serves_sft_b_plus_only_from_the_registered_adapter(tmp_path: Path):
    older = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b"
    for adapter in (older, REGISTERED_ADAPTER + "/"):
        proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", ADAPTER_SFT_B_PLUS=adapter, **_test_normal(tmp_path))
        assert proc.returncode == 2 and "only from the registered adapter" in _out(proc), _out(proc)
    assert run_pbs(tmp_path, CFG=f"configs/{C_CFG}", ADAPTER_SFT_B_PLUS=REGISTERED_ADAPTER,
                   **_test_normal(tmp_path)).returncode == 0
    # A dev dry run keeps the override.
    assert run_pbs(tmp_path, CFG=f"configs/{C_CFG}", DRYRUN="1", ADAPTER_SFT_B_PLUS=older).returncode == 0


# ---- a dirty tree ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                    *args], check=True, capture_output=True, text=True)


def _git_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    for sub in ("docs", "src", "scripts", "configs"):
        (root / sub).mkdir(parents=True)
    prereg = root / "docs" / "prereg_j11.md"
    prereg.write_text(f"# J11\n\n{FROZEN_LINE}\n\nbody\n", encoding="utf-8")
    for sub in ("src", "scripts", "configs"):
        (root / sub / "keep.txt").write_text("x\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "freeze")
    return root, prereg


def test_the_git_checks_refuse_an_uncommitted_prereg_or_a_dirty_tree(tmp_path: Path):
    root, prereg = _git_tree(tmp_path)
    env = dict(CFG=f"configs/{C_CFG}", SPLIT="test_normal", J11_CONFIRM="J11_FROZEN",
               J11_PREREG=str(prereg), J11_GIT_ROOT=str(root))
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "git checks skipped" not in _out(proc)

    (root / "src" / "keep.txt").write_text("edited\n", encoding="utf-8")  # a modified tracked file
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and "uncommitted changes under src/, scripts/ or configs/" in _out(proc)
    _git(root, "checkout", "--", "src/keep.txt")

    (root / "configs" / "new.yaml").write_text("x: 1\n", encoding="utf-8")  # an untracked file
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and "uncommitted changes under src/" in _out(proc)
    (root / "configs" / "new.yaml").unlink()

    prereg.write_text(prereg.read_text(encoding="utf-8") + "an edit after the freeze\n", encoding="utf-8")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and "has uncommitted changes; the frozen text is the committed text" in _out(proc)
    _git(root, "checkout", "--", "docs/prereg_j11.md")

    other = root / "docs" / "prereg_other.md"  # FROZEN on disk but never committed
    other.write_text(f"{FROZEN_LINE}\n", encoding="utf-8")
    proc = run_pbs(tmp_path, **dict(env, J11_PREREG=str(other)))
    assert proc.returncode == 2 and "is not committed; FROZEN means committed" in _out(proc)
    assert run_pbs(tmp_path, **env).returncode == 0


# ---- (b) planner, receiver, source ----------------------------------------------------------

@pytest.mark.parametrize("replace,why", [
    ((f"model: {P27}", "model: Qwen/Qwen3-8B"), "registered planner is exactly Qwen/Qwen3.8-27B-FP8"),
    (("type: vllm\n  model: Qwen", "type: codex\n  model: Qwen"), "need vllm"),
    (("on_missing: call_if_planless", "on_missing: call_if_planless\n  live_plan_keys:\n  - 2/6171bbc_3"),
     "LP Amendment 4's key is a dev key"),
    (("lora_name: sft_b_plus", "lora_name: sft_b"), "is not the served alias"),
])
def test_planner_and_receiver_refusals(tmp_path: Path, replace, why: str):
    cfg, src = _relocated(tmp_path, "j11_takeover_fixed_k_10.yaml", replace)
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2, _out(proc)
    assert why in _out(proc)


def test_a_replay_arm_must_replay_c_and_nothing_else(tmp_path: Path):
    dev_ceiling = "/scratch/n12194778/sidekick/results/lp2_planner_alone_cap81_qwen38_27b_20260923"
    cfg, _src = _relocated(tmp_path, "j11_prefix_bplus_m11.yaml")
    text = cfg.read_text(encoding="utf-8")
    cfg.write_text(text.replace(f"packet_source: {tmp_path / 'out' / C_NAME}", f"packet_source: {dev_ceiling}"),
                   encoding="utf-8")
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2 and "every J11 replay arm replays C" in _out(proc), _out(proc)
    cfg.write_text(text.replace(f"source_campaign: {tmp_path / 'out' / C_NAME}", f"source_campaign: {dev_ceiling}"),
                   encoding="utf-8")
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2 and "every J11 prefix arm replays C" in _out(proc), _out(proc)


def test_c_must_not_construct_an_executor(tmp_path: Path):
    cfg, _src = _relocated(tmp_path, C_CFG, ("type: mock", "type: vllm\n  model: ibm-granite/granite-4.2-8b"))
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2 and "C must not construct an executor" in _out(proc), _out(proc)


def test_config_split_key_and_system_mismatch_are_refused(tmp_path: Path):
    cfg, _src = _relocated(tmp_path, C_CFG)
    cfg.write_text(cfg.read_text(encoding="utf-8") + "\nsplit: test_normal\n", encoding="utf-8")
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2 and "split: key" in _out(proc)
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", DRYRUN="1", SYSTEM="fixed_k")
    assert proc.returncode == 2 and "disagrees with the registered system" in _out(proc)


# ---- (c) C complete, planless keys ------------------------------------------------------------

@pytest.mark.parametrize("name", PLAN_ARMS + PREFIX_ARMS)
def test_a_replay_arm_is_refused_on_test_until_c_is_complete(tmp_path: Path, name: str):
    cfg, src = _relocated(tmp_path, name)
    env = dict(CFG=str(cfg), **_test_normal(tmp_path))
    wait = "C is not complete; C must complete before any replay arm starts"

    proc = run_pbs(tmp_path, **env)  # C not started
    assert proc.returncode == 2 and wait in _out(proc) and f"C {src}: exists=0" in _out(proc), _out(proc)

    # 336 non-crashed in all, but 169 at seed 1 and 167 at seed 2: a pooled count would pass.
    _write_results(src, [(f"t{i}", 1, None) for i in range(169)] + [(f"t{i}", 2, None) for i in range(167)])
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and wait in _out(proc) and "short_seeds=seed2:167" in _out(proc), _out(proc)

    _write_results(src, [("t167", 2, "crash")])  # a crash: C's next resubmission would re-plan it
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2 and wait in _out(proc) and "crashed=1" in _out(proc)

    _write_results(src, [("t167", 2, None)])
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "non_crashed=337 crashed=0 unreadable=0 short_seeds=-" in _out(proc)


def test_planless_c_keys_are_listed_and_capped_at_5_percent_for_every_replay_arm(tmp_path: Path):
    for name in ("j11_takeover_fixed_k_10.yaml", "j11_prefix_zs_m11.yaml"):
        cfg, src = _relocated(tmp_path, name)
        if not (src / "planner_alone").is_dir():
            _complete(src, 168)
        env = dict(CFG=str(cfg), **_test_normal(tmp_path))
        _planless(src, [("t3", 2), ("t7", 1)])
        proc = run_pbs(tmp_path, **env)
        assert proc.returncode == 0, _out(proc)
        assert "C episodes scored without a plan: 2 (cap 16, prereg §2): 1/t7 2/t3" in _out(proc)
        assert "planless=2" in _preflight(proc)
        if "prefix" in name:
            assert "replay an empty prefix (effective_m 0) and run" in _out(proc)
    _planless(src, [(f"t{i}", 1) for i in range(20, 35)])  # 17 in all
    for name in ("j11_takeover_fixed_k_10.yaml", "j11_prefix_zs_m11.yaml"):
        cfg, _src = _relocated(tmp_path, name)
        proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
        assert proc.returncode == 2, _out(proc)
        assert "17 C episodes wrote no plan, above the cap of 16 (5 % of 336); no replay arm starts" in _out(proc)


def test_a_plan_replay_arm_that_would_abort_on_a_planless_key_is_refused(tmp_path: Path):
    cfg, src = _relocated(tmp_path, "j11_advise_fixed_k_1_fullctx.yaml",
                          ("on_missing: call_if_planless", "on_missing: fail"))
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 0, _out(proc)  # no planless key: nothing to abort on
    _planless(src, [("t0", 1)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 2, _out(proc)
    assert "planner.on_missing is 'fail', so the 1 C episode(s) without a plan would crash" in _out(proc)


@pytest.mark.parametrize("name", sorted(SYSTEM_OF))
def test_every_registered_config_passes_preflight_on_test_once_c_is_complete(tmp_path: Path, name: str):
    cfg, src = _relocated(tmp_path, name)
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(tmp_path))
    assert proc.returncode == 0, _out(proc)
    line = _preflight(proc)
    stem = name[: -len(".yaml")]
    assert f"system={SYSTEM_OF[name]} cid={stem}_20260924 split=test_normal target=336" in line
    if SYSTEM_OF[name] == "prefix_handoff":
        assert line.endswith(f"gate=--gate --allow-live-planner {EXPECT}")
    else:
        assert line.endswith(f"gate=--gate --expect-planner {EXPECT}")


# ---- placement: C on one card, every replay arm on two ---------------------------------------

@pytest.mark.parametrize("name", sorted(SYSTEM_OF))
def test_placement_c_runs_on_one_card_and_a_replay_arm_needs_two(tmp_path: Path, name: str):
    cfg, src = _relocated(tmp_path, name)
    _complete(src, 168)
    env = dict(_test_normal(tmp_path), CFG=str(cfg), J11_SELFTEST_STAGE="placement")
    one = run_pbs(tmp_path, CUDA_VISIBLE_DEVICES="GPU-a", **env)
    two = run_pbs(tmp_path, CUDA_VISIBLE_DEVICES="GPU-a,GPU-b", **env)
    if name == C_CFG:
        assert one.returncode == 0, _out(one)
        assert "placement executor@none util=0.85 planner@GPU-a util=0.85 visible=1" in _out(one)
        assert "WARN" not in _out(one)
        assert two.returncode == 0 and "planner@GPU-a" in _out(two) and "1 idle (C's line asks for ngpus=1)" in _out(two)
    else:
        assert one.returncode == 2, _out(one)
        assert "is a replay arm: it serves granite AND the 27B planner, one card each; submit with ngpus=2 (1 visible)" in _out(one)
        assert two.returncode == 0, _out(two)
        assert "placement executor@GPU-a util=0.85 planner@GPU-b util=0.85 visible=2" in _out(two)


# ---- DRYRUN ---------------------------------------------------------------------------------

def test_dryrun_renames_c_forces_dev_and_three_tasks(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", DRYRUN="1", SPLIT="test_normal")
    assert proc.returncode == 0, _out(proc)
    assert "DRYRUN=1 forces SPLIT=dev (was test_normal)" in _out(proc)
    assert f"cid={C_NAME}_dryrun split=dev target=6" in _preflight(proc)
    # Without DRYRUN a dev run into the registered id is refused.
    proc = run_pbs(tmp_path, CFG=f"configs/{C_CFG}", SPLIT="dev")
    assert proc.returncode == 2 and "mix dev episodes into the test tree" in _out(proc)


def test_dryrun_replay_arm_replays_the_dryrun_c_and_requires_it_complete(tmp_path: Path):
    cfg, src = _relocated(tmp_path, "j11_prefix_bplus_m6.yaml")
    dry = Path(str(src) + "_dryrun")
    _complete(src, 3)  # the registered tree is complete, and must not be what a dry run judges
    _write_results(dry, [("t0", 1, None), ("t0", 2, None), ("t1", 1, None), ("t1", 2, None), ("t2", 1, None)])
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 2, _out(proc)
    assert f"C {dry}: exists=1 non_crashed=5" in _out(proc) and "short_seeds=seed2:2" in _out(proc)
    _write_results(dry, [("t2", 2, None)])
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1")
    assert proc.returncode == 0, _out(proc)
    assert "cid=j11_prefix_bplus_m6_20260924_dryrun split=dev target=6" in _preflight(proc)
    derived = list((tmp_path / "logs" / "j11_dryrun_cfg").glob("j11_prefix_bplus_m6_20260924_dryrun.*.yaml"))
    assert derived
    for path in derived:
        body = path.read_text(encoding="utf-8")
        assert f"source_campaign: {dry}" in body and f"packet_source: {dry}" in body
        assert "campaign_id: j11_prefix_bplus_m6_20260924_dryrun" in body


def test_dev_replay_run_without_dryrun_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG="configs/j11_takeover_fixed_k_10.yaml", SPLIT="dev", CID="j11_devcheck")
    assert proc.returncode == 2 and "use DRYRUN=1" in _out(proc), _out(proc)


# ---- smoke guard and tally ------------------------------------------------------------------

RUN_START = {"event_type": "run_start", "actor": "system"}
EXEC_ACT = {"event_type": "action", "actor": "executor"}
PLANNER_ACT = {"event_type": "action", "actor": "planner"}
SHOWN = {"event_type": "intervention", "actor": "planner", "payload": {"source": "shown_action"}}
PLAN_PARSE = {"event_type": "error", "error_type": "parse_error", "payload": {"method": "plan"}}


def _smoke(root: Path, episodes: list[tuple[int, str | None, list[dict]]]) -> None:
    for i, (steps, err, events) in enumerate(episodes):
        ep = root / "arm" / "1" / f"t{i}"
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
        (ep / "result.json").write_text(json.dumps(
            {"task_id": f"t{i}", "seed": 1, "steps": steps, "error_type": err}) + "\n", encoding="utf-8")


def _guard(tmp_path: Path, name: str, episodes) -> subprocess.CompletedProcess[str]:
    cfg, src = _relocated(tmp_path, name)
    _complete(Path(str(src) + "_dryrun"), 3)
    _smoke(tmp_path / "out" / "smoke_x", episodes)
    return run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", J11_SELFTEST_STAGE="smoke_guard", J11_GUARD_CID="smoke_x")


R, S = 12, 4  # reached / short of fixed_k = 10
GUARD_CASES = [
    ("takeover-pass", "j11_takeover_fixed_k_10.yaml", [(R, None, [RUN_START, PLANNER_ACT])] * 3, 0,
     "planner_actions=3 shown_action_interventions=0"),
    ("takeover-advise-path", "j11_takeover_fixed_k_10.yaml", [(R, None, [RUN_START, EXEC_ACT])] * 3, 1,
     "it ran the advise path"),
    ("takeover-stale-attempt", "j11_takeover_fixed_k_10.yaml",
     [(R, None, [RUN_START, PLANNER_ACT, RUN_START, EXEC_ACT])] * 3, 1, "authored 0 planner actions"),
    ("takeover-short", "j11_takeover_fixed_k_10.yaml", [(S, None, [RUN_START, EXEC_ACT])] * 3, 0,
     "smoke uninformative"),
    ("advise-pass", "j11_advise_fixed_k_10_fullctx.yaml", [(R, None, [RUN_START, EXEC_ACT])] * 3, 0,
     "planner_actions=0 shown_action_interventions=0"),
    ("advise-takeover", "j11_advise_fixed_k_1_fullctx.yaml", [(R, None, [RUN_START, PLANNER_ACT])] * 3, 1,
     "made it another channel"),
    ("c-plan-parse", C_CFG, [(0, "parse_error", [RUN_START, PLAN_PARSE])] + [(9, None, [RUN_START])] * 2, 1,
     "parse_error in the plan call"),
    ("c-all-zero", C_CFG, [(0, "limit", [RUN_START])] * 3, 1, "ran nothing past the plan"),
    ("c-pass", C_CFG, [(0, "parse_error", [RUN_START])] + [(9, None, [RUN_START])] * 2, 0,
     "plan_parse_errors=0 steps_zero=1"),
    ("crash", "j11_prefix_zs_m6.yaml", [(5, "crash", [RUN_START])] + [(9, None, [RUN_START])] * 2, 1,
     "with 1 crash(es)"),
    ("short-smoke", "j11_prefix_zs_m6.yaml", [(9, None, [RUN_START])] * 2, 1, "smoke wrote 2/3 results"),
    ("prefix-pass", "j11_prefix_bplus_m11.yaml", [(9, None, [RUN_START, SHOWN])] * 3, 0, "results=3 crashed=0"),
]


@pytest.mark.parametrize("name,episodes,rc,text", [c[1:] for c in GUARD_CASES], ids=[c[0] for c in GUARD_CASES])
def test_smoke_guard_on_constructed_smoke_trees(tmp_path: Path, name: str, episodes, rc: int, text: str):
    proc = _guard(tmp_path, name, episodes)
    assert proc.returncode == rc, _out(proc)
    assert text in _out(proc)
    assert ("selftest: smoke guard passed" in _out(proc)) == (rc == 0)


def test_the_real_run_guards_the_smoke_before_the_dev_tree_is_deleted():
    text = PBS.read_text(encoding="utf-8")
    call = text.index('j11_smoke_guard "${CFG_STEM}" "${SCID}"')
    assert text.index("GATE_RC=$?") < call < text.index('rm -rf "${OUT:?}/${SCID:?}"')
    assert call < text.index("# ---- (f) the arm")


def test_tally_exits_3_while_crashes_remain_and_0_when_complete(tmp_path: Path):
    root = tmp_path / "out" / f"{C_NAME}_dryrun"
    _write_results(root, [("t0", 1, None), ("t0", 2, "limit"), ("t1", 1, None), ("t1", 2, "crash")])
    env = dict(CFG=f"configs/{C_CFG}", DRYRUN="1", TASKS="2", J11_SELFTEST_STAGE="tally")
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 3, _out(proc)
    assert "target=4 non_crashed=3 crashed=1" in _out(proc) and "resubmit" in _out(proc)
    _write_results(root, [("t1", 2, None)])
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert "COMPLETE: 4/4 non-crashed, 0 crashed" in _out(proc)
