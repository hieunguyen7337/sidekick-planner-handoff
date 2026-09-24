"""scripts/pbs/j12_arm.pbs: J12's freeze gate and arm-3 order rule, and the hand-off to j10_arm.pbs.

The J12 self-test runs every J12 refusal and exits before j10_arm.pbs is started, so nothing is
submitted, served or written under /scratch/n12194778/sidekick/results. Arm 3 is always a synthetic
directory under tmp_path (a tmp copy of the config points at it), except in the one dry-run case that
reads the real `_dryrun` arm 3. The j10_arm.pbs cases run that script's own J10_SELFTEST path with
J10_OUT / J10_LOGDIR in tmp_path, as test_j10_arm_pbs does.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "j12_arm.pbs"
J10_PBS = REPO / "scripts" / "pbs" / "j10_arm.pbs"
J12_PREREG = REPO / "docs" / "prereg_j12_depth_test_20260924.md"
# A committed, unmodified prereg whose one Status line begins FROZEN: the stand-in for a frozen
# J12 prereg in the accepting cases (the J12 draft is not frozen, and no git write is made here).
A1_PREREG = REPO / "docs" / "prereg_j10_amendment_20260924.md"
FROZEN_LINE = "**Status**: **FROZEN** 2026-09-24, commit abc1234."
ARM3 = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
DRY_ARM3 = Path(ARM3 + "_dryrun")
J12_CFGS = ("configs/j12_prefix_m6.yaml", "configs/j12_prefix_zs_m6.yaml")
J12_NAMES = ("j12_prefix_m6.yaml", "j12_prefix_zs_m6.yaml")
HANDOFF = "J12_GATE_PASSED"
LINE_135 = ('[[ "${CFG_BASE}" == j10_*.yaml || ( "${CFG_BASE}" == j12_prefix_*.yaml && '
            '"${J12_HANDOFF:-}" == "J12_GATE_PASSED" ) ]] || fatal "CFG must be a j10_*.yaml config, '
            'or a j12_prefix_*.yaml handed off by scripts/pbs/j12_arm.pbs after J12\'s gate (J12_HANDOFF), '
            'got ${CFG_BASE}"')
REFUSED_135 = ("CFG must be a j10_*.yaml config, or a j12_prefix_*.yaml handed off by "
               "scripts/pbs/j12_arm.pbs after J12's gate (J12_HANDOFF), got ")


def _prereg(tmp_path: Path, *status_lines: str) -> Path:
    path = tmp_path / "prereg_j12.md"
    path.write_text("# J12\n\n" + "\n".join(status_lines) + "\n\nbody\n", encoding="utf-8")
    return path


def _clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "DRYRUN", "SYSTEM", "J12_CONFIRM", "J12_PREREG",
                "J12_REPO", "J12_SELFTEST", "J12_HANDOFF", "J10_CONFIRM", "PBS_JOBID",
                "EXPECTED_CODEX_VERSION"):
        env.pop(key, None)
    env.update(PY=sys.executable, PYTHONPATH=f"{REPO / 'src'}:{REPO}", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def run_pbs(tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    env = _clean_env()
    env.update(J12_SELFTEST="1", J12_REPO=str(REPO))
    env.update(env_extra)
    return subprocess.run(["timeout", "120", "bash", str(PBS)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)


def _out(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str = "planner_alone") -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps(
            {"task_id": task, "seed": seed, "error_type": err}) + "\n", encoding="utf-8")


def _complete(src: Path, n_tasks: int, seeds: tuple[int, ...] = (1, 2)) -> None:
    _write_results(src, [(f"t{i}", s, None) for i in range(n_tasks) for s in seeds])


def _planless(src: Path, keys: list[tuple[str, int]]) -> None:
    """As test_j10_arm_pbs._planless: scored arm-3 episodes whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = src / "planner_alone" / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "events.jsonl").write_text(
            json.dumps({"event_type": "run_start", "payload": {}}) + "\n"
            + json.dumps({"event_type": "parse_error", "payload": {"text": "?"}}) + "\n",
            encoding="utf-8")


def _j12_cfg(tmp_path: Path, name: str = J12_NAMES[0], arm3_id: str = "j10_planner_alone_cap81_20260924"
             ) -> tuple[Path, Path]:
    """A tmp copy of the J12 config with arm 3's registered path moved under tmp_path; (config, arm 3)."""
    src = tmp_path / "out" / arm3_id
    text = (REPO / "configs" / name).read_text(encoding="utf-8")
    assert text.count(ARM3) == 2  # handoff.source_campaign and planner.packet_source
    cfg = tmp_path / "cfg" / name
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text.replace(ARM3, str(src)), encoding="utf-8")
    return cfg, src


def _test_normal(**extra: str) -> dict[str, str]:
    env = dict(SPLIT="test_normal", J12_CONFIRM="J12_FROZEN", J12_PREREG=str(A1_PREREG),
               EXPECTED_CODEX_VERSION="0.153.4")
    env.update(extra)
    return env


def _code_lines(path: Path) -> list[str]:
    return [l for l in path.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]


def _heredocs(path: Path) -> list[str]:
    """Every <<'PY' heredoc body in a script."""
    bodies, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        if cur is None:
            if line.rstrip().endswith("<<'PY'"):
                cur = []
        elif line == "PY":
            bodies.append("\n".join(cur))
            cur = None
        else:
            cur.append(line)
    return bodies


# ---- the wrapper itself ------------------------------------------------------------------------

def test_bash_syntax():
    assert subprocess.run(["bash", "-n", str(PBS)]).returncode == 0


def test_select_line_is_j10s_prefix_arm_header():
    head = PBS.read_text(encoding="utf-8").splitlines()[:7]
    j10_head = J10_PBS.read_text(encoding="utf-8").splitlines()[:7]
    assert any(line.startswith("#PBS -l select=") and "ngpus=1:gpu_id=H100" in line for line in head)
    assert [l for l in head if l.startswith("#PBS -l")] == [l for l in j10_head if l.startswith("#PBS -l")]


def test_header_names_the_qsub_lines_for_the_dry_run_and_both_arms():
    text = PBS.read_text(encoding="utf-8")
    qsub = [l for l in text.splitlines() if "qsub -v CFG=" in l]
    for cfg in J12_CFGS:
        assert f"qsub -v CFG={cfg},DRYRUN=1,TASKS=3 scripts/pbs/j12_arm.pbs" in text
        assert f"qsub -v CFG={cfg},SPLIT=test_normal,J12_CONFIRM=J12_FROZEN," in text
    # The hand-off sets J10_CONFIRM itself; the test lines carry A1 §9.1's CLI pin.
    assert len(qsub) == 4 and not any("J10_CONFIRM" in l or "J12_HANDOFF" in l for l in qsub)
    assert sum("EXPECTED_CODEX_VERSION=0.153.4" in l for l in qsub) == 2
    assert "zero planned hosted calls; live executor asks as A1 Amendment 1 §I" in " ".join(
        line.lstrip("#").strip() for line in text.splitlines() if line.startswith("#"))


def test_the_real_j12_prereg_is_refused_while_it_is_a_draft():
    # No seam: the wrapper reads docs/prereg_j12_depth_test_20260924.md itself.
    status = [l for l in J12_PREREG.read_text(encoding="utf-8").splitlines() if l.startswith("**Status**")]
    assert len(status) == 1
    proc = run_pbs(Path("."), CFG=J12_CFGS[0], J12_CONFIRM="J12_FROZEN", J12_HANDOFF=HANDOFF)
    if "DRAFT" in status[0]:
        assert proc.returncode == 2, _out(proc)
        assert "J12 is not FROZEN" in _out(proc)
        assert "J12_HANDOFF" not in _out(proc)  # an inherited token never reaches the hand-off
    else:  # once frozen, this file must pass the Status check (commit state is judged below it)
        assert "is not FROZEN" not in _out(proc) and "mentions DRAFT" not in _out(proc), _out(proc)


@pytest.mark.parametrize("line", [
    "**Status**: DRAFT — becomes FROZEN on commit, before any `test_normal` episode of J10, J11 or J12 exists.",
    "**Status**: FROZEN, superseding the DRAFT of 2026-09-24.",
    "**Status**: frozen in spirit",
])
def test_a_draft_or_non_frozen_status_line_is_refused(tmp_path: Path, line: str):
    proc = run_pbs(tmp_path, CFG=J12_CFGS[0], J12_CONFIRM="J12_FROZEN",
                   J12_PREREG=str(_prereg(tmp_path, line)))
    assert proc.returncode == 2, _out(proc)
    assert "not FROZEN" in _out(proc) or "mentions DRAFT" in _out(proc)


def test_two_status_lines_are_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=J12_CFGS[0], J12_CONFIRM="J12_FROZEN",
                   J12_PREREG=str(_prereg(tmp_path, FROZEN_LINE, FROZEN_LINE)))
    assert proc.returncode == 2, _out(proc)
    assert "expected exactly one **Status** line" in _out(proc) and "found 2" in _out(proc)


def test_no_status_line_is_refused(tmp_path: Path):
    proc = run_pbs(tmp_path, CFG=J12_CFGS[0], J12_CONFIRM="J12_FROZEN", J12_PREREG=str(_prereg(tmp_path)))
    assert proc.returncode == 2 and "found 0" in _out(proc)


def test_an_uncommitted_frozen_prereg_is_refused(tmp_path: Path):
    # A FROZEN line in a file git does not track: the gate must not take the text's word for it.
    proc = run_pbs(tmp_path, CFG=J12_CFGS[0], J12_CONFIRM="J12_FROZEN",
                   J12_PREREG=str(_prereg(tmp_path, FROZEN_LINE)))
    assert proc.returncode == 2, _out(proc)
    assert "is not committed" in _out(proc)


@pytest.mark.parametrize("confirm", [None, "", "A1_FROZEN", "j12_frozen", "yes"])
def test_a_missing_or_wrong_confirmation_token_is_refused(tmp_path: Path, confirm):
    env = dict(CFG=J12_CFGS[0], J12_PREREG=str(A1_PREREG))
    if confirm is not None:
        env["J12_CONFIRM"] = confirm
    proc = run_pbs(tmp_path, **env)
    assert proc.returncode == 2, _out(proc)
    assert "J12_CONFIRM=J12_FROZEN" in _out(proc)


@pytest.mark.parametrize("version", [None, "", "0.153.3", "codex-cli 0.153.4"])
def test_test_normal_needs_a1s_pinned_codex_version(tmp_path: Path, version):
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    env = _test_normal()
    env.pop("EXPECTED_CODEX_VERSION")
    if version is not None:
        env["EXPECTED_CODEX_VERSION"] = version
    proc = run_pbs(tmp_path, CFG=str(cfg), **env)
    assert proc.returncode == 2, _out(proc)
    assert "J12 test_normal arms need EXPECTED_CODEX_VERSION=0.153.4 (A1 §9.1)" in _out(proc)


@pytest.mark.parametrize("extra, message", [
    (dict(SPLIT=""), "J12 arms run SPLIT=test_normal (or DRYRUN=1 on dev), got SPLIT=<unset>"),
    (dict(SPLIT="dev"), "J12 arms run SPLIT=test_normal (or DRYRUN=1 on dev), got SPLIT=dev"),
    (dict(SPLIT="test_challenge"), "got SPLIT=test_challenge"),
    (dict(TASKS="100"), "registered at 168 tasks x seeds 1,2 = 336 pairs (J12 §2), got TASKS=100 SEEDS=1,2"),
    (dict(SEEDS="1"), "got TASKS=168 SEEDS=1"),
])
def test_a_frozen_run_off_the_registered_design_is_refused(tmp_path: Path, extra, message):
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal(**extra))
    assert proc.returncode == 2, _out(proc)
    assert message in _out(proc)


@pytest.mark.parametrize("name", J12_NAMES)
def test_a_committed_frozen_prereg_with_the_token_and_a_complete_arm_3_hands_off_to_j10(tmp_path: Path, name: str):
    cfg, src = _j12_cfg(tmp_path, name)
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 0, _out(proc)
    out = _out(proc)
    assert f"arm 3 {src}: exists=1 non_crashed=336 crashed=0 unreadable=0 (need >= 336, 0 crashed)" in out
    assert "arm-3 episodes scored without a plan: 0 (cap 16, A1 §4.2 item 5)" in out
    line = next(l for l in out.splitlines() if "selftest: J12 gates passed" in l)
    assert f"cfg={cfg} dryrun=0;" in line
    assert f"would exec J12_HANDOFF={HANDOFF} J10_CONFIRM=A1_FROZEN J10_REPO={REPO} bash {J10_PBS}" in line


@pytest.mark.parametrize("cfg", [
    "configs/j10_prefix_m9.yaml", "configs/j10_prefix_m11.yaml", "configs/j12_prefix_m9.yaml",
    "configs/j11_prefix_bplus_m6.yaml", "",
])
def test_a_non_j12_config_is_refused_even_on_a_dry_run(tmp_path: Path, cfg: str):
    for extra in (dict(J12_CONFIRM="J12_FROZEN", J12_PREREG=str(A1_PREREG)), dict(DRYRUN="1")):
        proc = run_pbs(tmp_path, CFG=cfg, **extra)
        assert proc.returncode == 2, _out(proc)
        assert "CFG must be configs/j12_prefix_m6.yaml or configs/j12_prefix_zs_m6.yaml" in _out(proc)


# ---- J12 §6 order rule: arm 3 complete, planless keys within A1 §4.2 item 5's cap -----------------

def test_an_incomplete_arm_3_is_refused(tmp_path: Path):
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 167)
    _write_results(src, [("t167", 1, None)])  # 335 of 336
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert "non_crashed=335 crashed=0 unreadable=0 (need >= 336, 0 crashed)" in _out(proc)
    assert "arm 3 is not complete; J12 arms start only after arm 3 is complete (J12 §6)" in _out(proc)
    assert "J12_HANDOFF" not in _out(proc)


def test_a_missing_arm_3_is_refused(tmp_path: Path):
    cfg, _src = _j12_cfg(tmp_path)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert "exists=0 non_crashed=0" in _out(proc) and "arm 3 is not complete" in _out(proc)


def test_a_crashed_or_unreadable_arm_3_episode_is_refused_even_with_336_scored(tmp_path: Path):
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    _write_results(src, [("t999", 1, "crash")])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert "non_crashed=336 crashed=1 unreadable=0" in _out(proc) and "arm 3 is not complete" in _out(proc)
    (src / "planner_alone" / "1" / "t999" / "result.json").write_text("{not json", encoding="utf-8")
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert "non_crashed=336 crashed=0 unreadable=1" in _out(proc)


def test_planless_keys_are_capped_at_16_of_336(tmp_path: Path):
    # 16 = 336 * 5 // 100 (A1 §4.2 item 5): 16 passes, 17 refuses.
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    _planless(src, [(f"t{i}", 1) for i in range(16)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 0, _out(proc)
    assert "arm-3 episodes scored without a plan: 16 (cap 16, A1 §4.2 item 5): 1/t0 1/t1 " in _out(proc)
    _planless(src, [("t16", 2)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert ("17 arm-3 episodes wrote no plan, above A1 §4.2 item 5's cap of 16 (5 % of 336); "
            "no J12 arm starts (J12 §6)") in _out(proc)
    assert "J12_HANDOFF" not in _out(proc)


def test_a_planless_key_off_the_registered_seeds_is_not_counted(tmp_path: Path):
    # planless_source_keys counts only scored episodes of the requested seeds (1,2).
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    _planless(src, [("t0", 1), ("t0", 3)])
    _write_results(src, [("t0", 3, None)])
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 0, _out(proc)
    assert "arm-3 episodes scored without a plan: 1 (cap 16, A1 §4.2 item 5): 1/t0" in _out(proc)


def test_a_config_whose_source_is_not_arm_3_is_refused(tmp_path: Path):
    cfg, src = _j12_cfg(tmp_path, arm3_id="j10_planner_alone_cap81_20260923")
    _complete(src, 168)
    proc = run_pbs(tmp_path, CFG=str(cfg), **_test_normal())
    assert proc.returncode == 2, _out(proc)
    assert "handoff.source_campaign must be J10 arm 3 (j10_planner_alone_cap81_20260924)" in _out(proc)


@pytest.mark.parametrize("name", J12_NAMES)
def test_dryrun_skips_the_freeze_gate_and_judges_the_dryrun_arm_3_at_the_dry_run_target(tmp_path: Path, name: str):
    # The real J12 prereg is a DRAFT and no token is given: only DRYRUN=1 lets this through.
    cfg, src = _j12_cfg(tmp_path, name)
    dry = Path(str(src) + "_dryrun")
    _complete(src, 168)  # the registered arm 3 complete does not help a dry run
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 2, _out(proc)
    assert f"arm 3 {dry}: exists=0" in _out(proc)
    _complete(dry, 2)
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 0, _out(proc)
    out = _out(proc)
    assert "J12's freeze gate is skipped" in out
    assert f"arm 3 {dry}: exists=1 non_crashed=4 crashed=0 unreadable=0 (need >= 4, 0 crashed)" in out
    assert "arm-3 episodes scored without a plan: 0 (cap 0, A1 §4.2 item 5)" in out
    assert f"cfg={cfg} dryrun=1;" in out and f"would exec J12_HANDOFF={HANDOFF} " in out
    _planless(dry, [("t0", 1)])  # 4 * 5 // 100 = 0: one planless dry-run key is over the cap
    proc = run_pbs(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2")
    assert proc.returncode == 2, _out(proc)
    assert "1 arm-3 episodes wrote no plan, above A1 §4.2 item 5's cap of 0 (5 % of 4)" in _out(proc)


def test_the_arm_3_rules_are_j10_arm_pbs_heredocs_verbatim():
    # Completeness (require_complete_source) and the N_PLANLESS count (planless_source_keys):
    # the J12 check and j10_arm.pbs judge arm 3 by the same code, not a re-implementation.
    j12, j10 = _heredocs(PBS), _heredocs(J10_PBS)
    assert len(j12) == 3  # the config read, completeness, planless keys
    assert "root.rglob(\"result.json\")" in j12[1] and j12[1] in j10
    assert "planless_source_keys(sys.argv[1], sys.argv[2], seeds)" in j12[2] and j12[2] in j10


def test_the_handoff_token_is_exported_only_after_every_j12_check():
    code = _code_lines(PBS)
    uses = [i for i, l in enumerate(code) if "J12_HANDOFF" in l]
    sets = [i for i, l in enumerate(code) if re.search(r"\bJ12_HANDOFF=", l) and not l.lstrip().startswith("echo")]
    assert code[uses[0]].strip() == "unset J12_HANDOFF" and uses[0] < 5  # an inherited token is dropped first
    assert len(sets) == 1 and code[sets[0]].strip() == f"export J12_HANDOFF={HANDOFF}"
    gates = [i for i, l in enumerate(code) if "fatal" in l and "J10_PBS" not in l and not l.startswith("fatal ()")]
    assert gates and sets[0] > max(gates)  # below the last J12 refusal: nothing can fail after it but "not found"


def test_the_hand_off_sets_a1s_token_and_the_repo_and_clears_j10_seams():
    text = PBS.read_text(encoding="utf-8")
    body = _code_lines(PBS)
    assert 'exec bash "${J10_PBS}"' in body
    assert any(re.search(r"export CFG DRYRUN J10_CONFIRM=A1_FROZEN J10_REPO=\"\$\{REPO\}\"", l) for l in body)
    assert any(l.startswith("unset J10_SELFTEST ") and "J10_PREREG" in l and "J10_OUT" in l for l in body)
    assert 'REPO="${J12_REPO:-/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15}"' in text


# ---- the real exec path, into a stub j10_arm.pbs ------------------------------------------------

def _fake_repo(tmp_path: Path, prereg: Path = J12_PREREG) -> Path:
    """A J12_REPO whose scripts/pbs/j10_arm.pbs is a stub that prints what it inherited."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    shutil.copy(prereg, repo / "docs" / "prereg_j12_depth_test_20260924.md")
    stub = repo / "scripts" / "pbs" / "j10_arm.pbs"
    stub.parent.mkdir(parents=True)
    stub.write_text(
        "#!/bin/bash\n"
        'echo "stub-j10 J12_HANDOFF=${J12_HANDOFF:-<unset>} J10_CONFIRM=${J10_CONFIRM:-<unset>}'
        ' J10_REPO=${J10_REPO:-<unset>} J10_SELFTEST=${J10_SELFTEST:-<unset>} J10_OUT=${J10_OUT:-<unset>}'
        ' CFG=${CFG} DRYRUN=${DRYRUN}"\nexit 0\n', encoding="utf-8")
    return repo


def _run_real(repo: Path, **env_extra: str) -> tuple[int, str]:
    env = _clean_env()
    env.update(J12_REPO=str(repo), PBS_JOBID="t.1", J10_SELFTEST="1", J10_OUT="/nonexistent")
    env.update(env_extra)
    proc = subprocess.run(["timeout", "120", "bash", str(PBS)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)
    logs = sorted((repo / "campaign" / "workers" / "logs").glob("j12_arm.*.t.1.out"))
    return proc.returncode, proc.stdout + proc.stderr + "".join(p.read_text(encoding="utf-8") for p in logs)


def test_a_real_run_that_passes_execs_j10_with_the_token_and_without_j10_seams(tmp_path: Path):
    repo = _fake_repo(tmp_path)
    cfg, src = _j12_cfg(tmp_path)
    _complete(Path(str(src) + "_dryrun"), 3)
    rc, out = _run_real(repo, CFG=str(cfg), DRYRUN="1", TASKS="3")
    assert rc == 0, out
    stub = next(l for l in out.splitlines() if l.startswith("stub-j10 "))
    assert stub == (f"stub-j10 J12_HANDOFF={HANDOFF} J10_CONFIRM=A1_FROZEN J10_REPO={repo} "
                    f"J10_SELFTEST=<unset> J10_OUT=<unset> CFG={cfg} DRYRUN=1")


def test_a_real_run_with_the_draft_prereg_never_reaches_the_export(tmp_path: Path):
    # The real J12 draft, no DRYRUN, and a forged token in the environment: refused, j10 never started.
    status = [l for l in J12_PREREG.read_text(encoding="utf-8").splitlines() if l.startswith("**Status**")]
    if "DRAFT" not in status[0]:
        pytest.skip("the J12 prereg is no longer a DRAFT")
    repo = _fake_repo(tmp_path)
    cfg, src = _j12_cfg(tmp_path)
    _complete(src, 168)
    rc, out = _run_real(repo, CFG=str(cfg), **_test_normal(J12_PREREG="", J12_HANDOFF=HANDOFF))
    assert rc == 2, out
    assert "J12 is not FROZEN" in out and "stub-j10" not in out


def test_a_real_run_over_the_planless_cap_never_reaches_the_export(tmp_path: Path):
    repo = _fake_repo(tmp_path)
    cfg, src = _j12_cfg(tmp_path)
    dry = Path(str(src) + "_dryrun")
    _complete(dry, 3)
    _planless(dry, [("t0", 1)])
    rc, out = _run_real(repo, CFG=str(cfg), DRYRUN="1", TASKS="3", J12_HANDOFF=HANDOFF)
    assert rc == 2, out
    assert "above A1 §4.2 item 5's cap of 0" in out and "stub-j10" not in out


# ---- j10_arm.pbs: line 135 admits a j12_prefix config only with the token ------------------------

def _run_j10(tmp_path: Path, **env_extra: str) -> subprocess.CompletedProcess[str]:
    """j10_arm.pbs's own self-test, as tests/unit/test_j10_arm_pbs.py runs it."""
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    (stub / "codex").write_text("#!/bin/bash\necho 'codex-cli 9.9.9'\n", encoding="utf-8")
    (stub / "codex").chmod(0o755)
    env = os.environ.copy()
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "DRYRUN", "SYSTEM", "EXPECTED_CODEX_VERSION",
                "J10_CONFIRM", "J10_PREREG", "J10_SELFTEST_STAGE", "PBS_JOBID",
                "ADAPTER_SFT_B_PLUS", "ALIAS_SFT_B_PLUS", "J10_GUARD_CID", "J12_HANDOFF"):
        env.pop(key, None)
    env.update(J10_SELFTEST="1", J10_STUB_DIR=str(stub), J10_OUT=str(tmp_path / "j10out"),
               J10_LOGDIR=str(tmp_path / "logs"), PY=sys.executable, OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    env.update(env_extra)
    return subprocess.run(["timeout", "120", "bash", str(J10_PBS)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)


def test_j10_arm_pbs_edits_are_line_neutral():
    lines = J10_PBS.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 993
    assert lines[134] == LINE_135
    assert lines[202] == "  j10_prefix_*|j12_prefix_*) REG_SYSTEM=prefix_handoff;;"


def test_every_j10_arm_pbs_line_the_j12_wrapper_cites_holds_what_it_says():
    lines = J10_PBS.read_text(encoding="utf-8").splitlines()
    at = lambda a, b=None: "\n".join(lines[a - 1:(b or a)])  # noqa: E731
    assert "Self-test seams only" in at(76, 81) and "J10_PREREG" in at(76, 81)
    assert "J12_HANDOFF" in at(135)
    assert at(219).startswith("# ---- (a) split") and at(235) == "TARGET=$((TASKS * N_SEEDS))"
    assert 'if [[ -n "${EXPECTED_CODEX_VERSION}" ]]; then' == at(308) and "codex version matches" in at(314)
    assert at(385) == "import json" and at(405).startswith('print(f"{ok} {crash} {bad}')
    assert 'require_complete_source "prefix source" "${HANDOFF_SOURCE}" "arms 4-7"' in at(414, 416)
    assert '"${SYSTEM}" == "prefix_handoff" && "${PACKET_SOURCE}" == "${HANDOFF_SOURCE}"' in at(418)
    assert at(427).lstrip().startswith('PLANLESS="$(timeout 300') and at(434) == "PY"
    assert at(437).strip() == "PLANLESS_CAP=$(( TARGET * 5 / 100 ))"


@pytest.mark.parametrize("token", [None, "", "yes", "j12_gate_passed", "J12_FROZEN"])
def test_j10_arm_pbs_refuses_a_j12_config_without_the_handoff_token(tmp_path: Path, token):
    cfg, src = _j12_cfg(tmp_path)
    _complete(Path(str(src) + "_dryrun"), 2)
    env = dict(CFG=str(cfg), DRYRUN="1", TASKS="2")
    if token is not None:
        env["J12_HANDOFF"] = token
    proc = _run_j10(tmp_path, **env)
    assert proc.returncode == 2, _out(proc)
    assert REFUSED_135 + "j12_prefix_m6.yaml" in _out(proc)


def test_j10_arm_pbs_refuses_other_j12_stems_even_with_the_token(tmp_path: Path):
    cfg, src = _j12_cfg(tmp_path)
    other = cfg.with_name("j12_other_m6.yaml")
    other.write_text(cfg.read_text(encoding="utf-8"), encoding="utf-8")
    _complete(Path(str(src) + "_dryrun"), 2)
    proc = _run_j10(tmp_path, CFG=str(other), DRYRUN="1", TASKS="2", J12_HANDOFF=HANDOFF)
    assert proc.returncode == 2, _out(proc)
    assert REFUSED_135 + "j12_other_m6.yaml" in _out(proc)


@pytest.mark.parametrize("name", J12_NAMES)
def test_j10_arm_pbs_runs_the_j12_dry_run_preflight_with_the_token(tmp_path: Path, name: str):
    cfg, src = _j12_cfg(tmp_path, name)
    dry = Path(str(src) + "_dryrun")
    # Incomplete _dryrun arm 3 first: j10_arm.pbs's own arm-3-complete check still refuses.
    _write_results(dry, [("t0", 1, None), ("t0", 2, None), ("t1", 1, None)])
    proc = _run_j10(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2", J12_HANDOFF=HANDOFF)
    assert proc.returncode == 2 and "arm 3 must complete before arms 4-7 start" in _out(proc), _out(proc)
    _write_results(dry, [("t1", 2, None)])
    proc = _run_j10(tmp_path, CFG=str(cfg), DRYRUN="1", TASKS="2", J12_HANDOFF=HANDOFF)
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    stem = name[: -len(".yaml")]
    assert f"system=prefix_handoff cid={stem}_20260924_dryrun split=dev target=4" in line
    assert line.endswith("gate=--gate")  # zero live planner calls asserted, as for arms 4-7
    derived = list((tmp_path / "logs" / "j10_dryrun_cfg").glob(f"{stem}_20260924_dryrun.*.yaml"))
    assert derived
    for path in derived:
        body = path.read_text(encoding="utf-8")
        assert f"source_campaign: {dry}" in body and f"packet_source: {dry}" in body
        assert "  m: 6" in body


@pytest.mark.parametrize("name", J12_NAMES)
def test_j10_arm_pbs_test_normal_preflight_with_the_token_needs_arm_3_complete(tmp_path: Path, name: str):
    cfg, src = _j12_cfg(tmp_path, name)
    env = dict(CFG=str(cfg), SPLIT="test_normal", J10_CONFIRM="A1_FROZEN", J10_PREREG=str(A1_PREREG),
               J12_HANDOFF=HANDOFF)
    _complete(src, 167)
    _write_results(src, [("t167", 1, None)])
    proc = _run_j10(tmp_path, **env)
    assert proc.returncode == 2 and "arm 3 must complete before arms 4-7 start" in _out(proc), _out(proc)
    _write_results(src, [("t167", 2, None)])
    proc = _run_j10(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    assert f"system=prefix_handoff cid={name[:-5]}_20260924 split=test_normal target=336" in line
    _write_results(src, [("t999", 1, "crash")])
    proc = _run_j10(tmp_path, **env)
    assert proc.returncode == 2 and "crashed=1" in _out(proc), _out(proc)


@pytest.mark.skipif(not DRY_ARM3.is_dir(), reason="the J10 _dryrun arm 3 has not been run on this box")
@pytest.mark.parametrize("cfg", J12_CFGS)
def test_the_real_j12_dry_run_preflight_passes_against_the_real_dryrun_arm_3(tmp_path: Path, cfg: str):
    """The real configs, the real _dryrun arm 3 (read only), the real j10_arm.pbs (not a tmp copy)."""
    proc = run_pbs(tmp_path, CFG=cfg, DRYRUN="1", TASKS="3")
    assert proc.returncode == 0, _out(proc)
    assert f"arm 3 {DRY_ARM3}: exists=1 non_crashed=6 crashed=0 unreadable=0 (need >= 6, 0 crashed)" in _out(proc)
    proc = _run_j10(tmp_path, CFG=cfg, DRYRUN="1", TASKS="3", J12_HANDOFF=HANDOFF)
    assert proc.returncode == 0, _out(proc)
    stem = Path(cfg).stem
    assert f"[j10] prefix source {DRY_ARM3}: exists=1 non_crashed=6 crashed=0 unreadable=0" in _out(proc)
    line = next(l for l in _out(proc).splitlines() if "selftest: preflight passed" in l)
    assert f"system=prefix_handoff cid={stem}_20260924_dryrun split=dev target=6" in line
