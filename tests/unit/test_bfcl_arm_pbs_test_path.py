"""scripts/pbs/bfcl_arm.pbs on SPLIT=test: the gated path of docs/prereg_bfcl_test_20260925.md (E:312-314).

Self-test only (BFCL_SELFTEST=1): every gate runs and the wrapper exits before a lock, a vLLM server, a purge, a
smoke or a runner. BFCL_OUT / BFCL_LOGDIR point into tmp_path, a stub `codex` replaces the real one, and a replay
arm's registered dev source is moved under BFCL_OUT, so the derived config rewrites it to a SYNTHETIC test ceiling
under tmp_path, keyed on bfcl_task_ids("test", 0) (the split file's test list). No /scratch path is read or written.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from sidekick.environments.bfcl_env import bfcl_task_ids

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "bfcl_arm.pbs"
DEV_SOURCE_CID = "bfcl_planner_alone_cap81_dev_20260924"
TEST_SOURCE_CID = "bfcl_planner_alone_cap81_test_20260925"
REGISTERED_DEV_SOURCE = f"/scratch/n12194778/sidekick/results/{DEV_SOURCE_CID}"
TEST_IDS = bfcl_task_ids("test", 0)
DEV_IDS = bfcl_task_ids("dev", 0)
FROZEN_LINE = "**Status**: **FROZEN** on commit, 2026-09-28."
# E §2's 13 arms (E:42-53): runner system, receiver, registered MAX_PLANNER_CALLS (E:432-442; None = HOSTED=0).
ARMS = {
    "planner_alone_cap81": ("planner_alone", "none", 6000),
    "takeover_k5": ("fixed_k", "zs", 2400),
    "advise_k5_fullctx": ("fixed_k", "zs", 2400),
    "advise_k5_neutral": ("fixed_k", "zs", 2400),
    "plan_zs": ("prompt_only", "zs", 1200),
    "executor_alone_zs": ("executor_alone", "zs", None),
    "executor_alone_bplus": ("executor_alone", "bplus", None),
    **{f"prefix_{r}_m{m}": ("prefix_handoff", r, None) for r in ("zs", "bplus") for m in (2, 4, 6)},
}
PACKET_ARMS = {"takeover_k5", "advise_k5_fullctx", "advise_k5_neutral", "plan_zs"}
PREFIX_ARMS = {stem for stem in ARMS if stem.startswith("prefix_")}
QZS_CONFIGS = sorted(p.name for p in (REPO / "configs").glob("bfcl_*qzs*.yaml"))
GO = {"SPLIT": "test", "BFCL_CONFIRM": "E_FROZEN", "EXPECTED_CODEX_VERSION": "0.153.4"}
REFILL_HEADER = "cid\tseed\ttask_id\terror_type\treason\tjob_id\tutc"


def _cid(stem: str) -> str:
    return f"bfcl_{stem}_test_20260925"


def _stub_dir(tmp: Path) -> Path:
    stub = tmp / "stub"
    stub.mkdir(parents=True, exist_ok=True)
    codex = stub / "codex"
    codex.write_text("#!/bin/bash\necho 'codex-cli 0.153.4'\n", encoding="utf-8")
    codex.chmod(0o755)
    return stub


def _adapter(tmp: Path) -> Path:
    path = tmp / "adapter"
    path.mkdir(parents=True, exist_ok=True)
    (path / "adapter_config.json").write_text("{}", encoding="utf-8")
    (path / "adapter_model.safetensors").write_text("x", encoding="utf-8")
    return path


def _run(tmp: Path, _script: Path = PBS, **env: str | None) -> subprocess.CompletedProcess:
    """The wrapper (or `_script`, a copy of it) in self-test; an env value of None removes that variable."""
    full = dict(os.environ)
    for key in ("SPLIT", "TASKS", "SEEDS", "CID", "SYSTEM", "EXPECTED_CODEX_VERSION", "MAX_PLANNER_CALLS",
                "BFCL_SELFTEST_STAGE", "BFCL_SPEND_RATE_CID", "PBS_JOBID", "CFG", "SMOKE_TASKS", "HF_HUB_OFFLINE",
                "SAFETY", "BFCL_CONFIRM", "BFCL_PREREG", "BFCL_GIT_ROOT", "BFCL_QWEN_HF_HOME"):
        full.pop(key, None)
    full.update({"BFCL_SELFTEST": "1", "BFCL_REPO": str(REPO), "BFCL_OUT": str(tmp / "out"),
                 "BFCL_LOGDIR": str(tmp / "logs"), "PY": sys.executable,
                 "BFCL_ADAPTER_SFT_B_PLUS": str(_adapter(tmp)), "BFCL_STUB_DIR": str(_stub_dir(tmp))})
    for key, value in env.items():
        if value is None:
            full.pop(key, None)
        else:
            full[key] = str(value)
    return subprocess.run(["bash", str(_script)], env=full, capture_output=True, text=True, timeout=180)


def _out(proc: subprocess.CompletedProcess) -> str:
    return proc.stdout + proc.stderr


def _ok_line(proc: subprocess.CompletedProcess) -> str:
    return next(line for line in proc.stdout.splitlines() if "selftest preflight ok" in line)


def _variant(tmp: Path, stem: str, edit: dict | None = None) -> Path:
    """configs/bfcl_<stem>.yaml under its own name in tmp, with the registered dev source moved under BFCL_OUT."""
    text = (REPO / "configs" / f"bfcl_{stem}.yaml").read_text(encoding="utf-8")
    text = text.replace(REGISTERED_DEV_SOURCE, str(tmp / "out" / DEV_SOURCE_CID))
    if edit:
        data = yaml.safe_load(text)
        for key, value in edit.items():
            if isinstance(value, dict):
                data[key] = {**data[key], **value}
            else:
                data[key] = value
        text = yaml.safe_dump(data, sort_keys=False)
    cfg = tmp / "cfg" / f"bfcl_{stem}.yaml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text, encoding="utf-8")
    return cfg


def _derived(tmp: Path, stem: str) -> Path:
    return tmp / "logs" / "bfcl_test_configs" / f"{_cid(stem)}.yaml"


def _ceiling(tmp: Path) -> Path:
    return tmp / "out" / TEST_SOURCE_CID


def _write_results(root: Path, rows: list[tuple[str, int, str | None]], system: str, **extra) -> None:
    for task, seed, err in rows:
        ep = root / system / str(seed) / task
        ep.mkdir(parents=True, exist_ok=True)
        (ep / "result.json").write_text(json.dumps({"task_id": task, "seed": seed, "error_type": err, **extra}) + "\n",
                                        encoding="utf-8")


def _complete_ceiling(tmp: Path) -> Path:
    """A synthetic test ceiling: all 150 test entries x seeds 1, 2 scored, none crashed."""
    src = _ceiling(tmp)
    _write_results(src, [(t, s, None) for t in TEST_IDS for s in (1, 2)], "planner_alone")
    return src


def _planless(src: Path, keys: list[tuple[str, int]]) -> None:
    """Give these (already scored) ceiling episodes an events.jsonl whose last attempt wrote no plan."""
    for task, seed in keys:
        ep = src / "planner_alone" / str(seed) / task
        (ep / "events.jsonl").write_text(json.dumps({"event_type": "run_start", "payload": {}}) + "\n",
                                         encoding="utf-8")


def _events(ep: Path, *attempts: list[dict]) -> None:
    lines = []
    for attempt in attempts:
        lines.append({"event_type": "run_start", "payload": {}})
        lines.extend(attempt)
    (ep / "events.jsonl").write_text("".join(json.dumps(ev) + "\n" for ev in lines), encoding="utf-8")


DIVERGED = {"event_type": "error", "actor": "system", "error_type": "crash", "payload": {"reason": "replay_divergence"}}


def _diverge(arm: Path, system: str, keys: list[tuple[str, int]]) -> None:
    """Crashed episodes whose last attempt logged a replay_divergence error (prefix_handoff.py _broken_result)."""
    _write_results(arm, [(t, s, "crash") for t, s in keys], system)
    for task, seed in keys:
        _events(arm / system / str(seed) / task, [DIVERGED])


def _flatten(node, path: str = "", out: dict | None = None) -> dict:
    out = {} if out is None else out
    if isinstance(node, dict) and node:
        for key, value in node.items():
            _flatten(value, f"{path}.{key}" if path else str(key), out)
    elif isinstance(node, list) and node:
        for i, value in enumerate(node):
            _flatten(value, f"{path}[{i}]", out)
    else:
        out[path] = node
    return out


def _nothing_started(tmp: Path) -> None:
    """No lock, no refill log, no results/ dir and no test campaign directory: the self-test stopped before them."""
    assert not (tmp / "logs" / "bfcl_locks").exists()
    assert not (tmp / "logs" / "bfcl_refills").exists()
    made = sorted(p.name for p in (tmp / "out").glob("*")) if (tmp / "out").is_dir() else []
    assert [name for name in made if name not in (TEST_SOURCE_CID, DEV_SOURCE_CID)] == []


# ---- fixtures and documentation ----------------------------------------------------------------

def test_the_synthetic_keys_are_the_split_files_150_test_entries() -> None:
    split = json.loads((REPO / "data" / "bfcl_split_20260924.json").read_text(encoding="utf-8"))
    assert len(TEST_IDS) == 150 == split["n_test"] and sorted(TEST_IDS) == sorted(split["test"])
    assert not set(TEST_IDS) & set(DEV_IDS)


def test_the_wrapper_registers_exactly_e2s_13_arms_and_no_qzs_stem() -> None:
    text = PBS.read_text(encoding="utf-8")
    stems = re.search(r'^TEST_STEMS="([^"]*)"$', text, re.M).group(1).split()
    assert sorted(stems) == sorted(ARMS) and len(stems) == 13
    assert not any("qzs" in s for s in stems)
    assert len(QZS_CONFIGS) == 8


def test_the_header_documents_the_test_path() -> None:
    header = PBS.read_text(encoding="utf-8").split("set -uo pipefail", 1)[0]
    assert "dev only; anything else is refused" not in header and "no BFCL test prereg is frozen" not in header
    for needle in ("SPLIT=test", "BFCL_CONFIRM=E_FROZEN", "bfcl_test_configs/bfcl_<stem>_test_20260925.yaml",
                   "bfcl_refills/<cid>.tsv", "complete under Am5 §B", "over cap: N divergent keys > 15",
                   "BFCL_PREREG", "BFCL_GIT_ROOT", "Planless keys (S7)", "loop.py:715", "J10 :224-225",
                   "unless BFCL_OUT and BFCL_LOGDIR", "data/bfcl_split_20260924.json", "third_party/bfcl/",
                   "the FIRST writer's", "a PY passed in is refused"):
        assert needle in header, needle


def test_the_prereg_and_git_seams_are_honoured_only_in_a_selftest() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert 'PREREG="${REPO}/docs/prereg_bfcl_test_20260925.md"' in text and 'GIT_ROOT="${REPO}"' in text
    block = text.split('if [[ "${SELFTEST}" == "1" ]]; then', 1)[1].split("\nfi\n", 1)[0]
    assert 'PREREG="${BFCL_PREREG:-${PREREG}}"' in block and 'GIT_ROOT="${BFCL_GIT_ROOT:-}"' in block
    assert text.count("BFCL_PREREG:-") == 1 and text.count("BFCL_GIT_ROOT:-") == 1


# ---- gates (a)-(f): refusals, all before a lock, a purge or a model --------------------------------

@pytest.mark.parametrize(
    "env, message",
    [
        ({"BFCL_CONFIRM": None}, "SPLIT=test needs BFCL_CONFIRM=E_FROZEN (got '<unset>'; E:313-314)"),
        ({"BFCL_CONFIRM": "e_frozen"}, "SPLIT=test needs BFCL_CONFIRM=E_FROZEN (got 'e_frozen'"),
        ({"BFCL_CONFIRM": "J10_FROZEN"}, "SPLIT=test needs BFCL_CONFIRM=E_FROZEN (got 'J10_FROZEN'"),
        ({"SEEDS": "1,2,3"}, "SPLIT=test is registered at SEEDS=1,2 only (got 1,2,3; E:31, E:314)"),
        ({"SEEDS": "2,1"}, "SPLIT=test is registered at SEEDS=1,2 only (got 2,1;"),
        ({"SEEDS": "1"}, "SPLIT=test is registered at SEEDS=1,2 only (got 1;"),
        ({"TASKS": "5"}, "SPLIT=test runs all 150 test entries: TASKS=0 only (got 5; E:26)"),
        ({"TASKS": "150"}, "TASKS=0 only (got 150;"),
        ({"TASKS": "151"}, "TASKS must be 0..150 (0 = all), got 151"),
        ({"SMOKE_TASKS": "3"}, "SPLIT=test smokes 2 entries at seed 1 (SMOKE_TASKS=2, got 3"),
        ({"CID": "bfcl_executor_alone_zs_test_x"},
         "CID=bfcl_executor_alone_zs_test_x: a BFCL test campaign is exactly bfcl_executor_alone_zs_test_20260925 (E:40)"),
        ({"CID": "bfcl_executor_alone_zs_dev_20260924"}, "a BFCL test campaign is exactly bfcl_executor_alone_zs_test_20260925"),
        ({"CID": "bfcl_executor_alone_bplus_test_20260925"},
         "a BFCL test campaign is exactly bfcl_executor_alone_zs_test_20260925"),
        ({"MAX_PLANNER_CALLS": "100"},
         "MAX_PLANNER_CALLS=100: executor_alone_zs runs at HOSTED=0 on test, with no MAX_PLANNER_CALLS brake"),
        ({"SAFETY": "1.0"}, "SAFETY=1.0: the test launch check is registered at SAFETY 1.2"),
        ({"SPLIT": "test_normal"}, "SPLIT=test_normal is not a BFCL split: dev, or test behind BFCL_CONFIRM=E_FROZEN"),
        ({"SPLIT": "test_challenge"}, "SPLIT=test_challenge is not a BFCL split"),
        ({"SPLIT": "TEST"}, "SPLIT=TEST is not a BFCL split"),
    ],
)
def test_test_path_refusals(tmp_path: Path, env: dict, message: str) -> None:
    proc = _run(tmp_path, **{**GO, **env})
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)
    assert "selftest preflight ok" not in proc.stdout
    _nothing_started(tmp_path)


def _prereg(tmp: Path, body: str) -> Path:
    path = tmp / "prereg" / "prereg_bfcl_test_20260925.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# BFCL test prereg\n\n{body}\n\nbody\n", encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "status, message",
    [
        # DRAFT, including the DRAFT line that also says FROZEN: the value must BEGIN with FROZEN.
        ("**Status**: DRAFT -- becomes FROZEN on commit", "the E-prereg is not FROZEN: its **Status** value must begin with FROZEN"),
        ("**Status**: **DRAFT** for review; FROZEN after", "the E-prereg is not FROZEN"),
        # FROZEN first, but DRAFT still on the line (any case).
        ("**Status**: **FROZEN** on commit (supersedes the DRAFT)", "the E-prereg's status line still mentions DRAFT"),
        ("**Status**: FROZEN, formerly a draft", "the E-prereg's status line still mentions DRAFT"),
        # Exactly one Status line.
        (f"{FROZEN_LINE}\n\n{FROZEN_LINE}", "has 2 **Status** lines; the E-prereg has exactly one"),
        ("Status: FROZEN", "has 0 **Status** lines; the E-prereg has exactly one"),
        # A second, DRAFT status line counts wherever it sits: indented, a list item, quoted, any case.
        (f"{FROZEN_LINE}\n\n  **Status**: DRAFT", "has 2 **Status** lines; the E-prereg has exactly one"),
        (f"{FROZEN_LINE}\n\n- **Status**: DRAFT", "has 2 **Status** lines"),
        (f"{FROZEN_LINE}\n\n> **status**: draft", "has 2 **Status** lines"),
        # The one status line must start in column 0.
        ("  **Status**: **FROZEN** on commit", "the E-prereg is not FROZEN: its **Status** value must begin with FROZEN"),
    ],
)
def test_the_prereg_must_be_frozen(tmp_path: Path, status: str, message: str) -> None:
    proc = _run(tmp_path, BFCL_PREREG=str(_prereg(tmp_path, status)), **GO)
    assert proc.returncode == 2 and message in proc.stdout, _out(proc)
    _nothing_started(tmp_path)


def test_a_frozen_prereg_passes_and_a_missing_one_is_refused(tmp_path: Path) -> None:
    proc = _run(tmp_path, BFCL_PREREG=str(_prereg(tmp_path, FROZEN_LINE)), **GO)
    assert proc.returncode == 0, _out(proc)
    assert "test gate: BFCL_CONFIRM=E_FROZEN" in proc.stdout
    proc = _run(tmp_path, BFCL_PREREG=str(tmp_path / "nowhere.md"), **GO)
    assert proc.returncode == 2 and f"the E-prereg {tmp_path / 'nowhere.md'} does not exist" in proc.stdout
    # The committed E-prereg (the default path) is FROZEN.
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 0 and "prereg_bfcl_test_20260925.md: **Status**: **FROZEN**" in proc.stdout, _out(proc)


@pytest.mark.parametrize("name", QZS_CONFIGS)
def test_no_qzs_stem_runs_on_test(tmp_path: Path, name: str) -> None:
    proc = _run(tmp_path, CFG=str(REPO / "configs" / name), **GO)
    assert proc.returncode == 2, _out(proc)
    assert f"{name}: no qzs stem runs on the BFCL test split (docs/prereg_bfcl_test_20260925.md §2" in proc.stdout
    _nothing_started(tmp_path)


def test_a_stem_outside_the_test_design_is_refused(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg" / "bfcl_show_k5.yaml"
    cfg.parent.mkdir(parents=True)
    shutil.copy(REPO / "configs" / "bfcl_advise_k5_fullctx.yaml", cfg)
    proc = _run(tmp_path, CFG=str(cfg), **GO)
    assert proc.returncode == 2, _out(proc)
    assert ("bfcl_show_k5.yaml is not one of the 13 arms of the BFCL test design "
            "(docs/prereg_bfcl_test_20260925.md §2)") in proc.stdout


def test_the_gates_fire_in_the_registered_order(tmp_path: Path) -> None:
    # Every gate is broken at once; mending them one at a time exposes the next, in the order (a)..(h). Gate (c)
    # runs against a throwaway tree (BFCL_GIT_ROOT) whose src/ is dirty; both halves of (g) are ordered: the codex
    # version (unset at first) before the registered MAX_PLANNER_CALLS.
    root, prereg, _cfg = _git_tree(tmp_path)
    qzs, takeover = root / "configs" / "bfcl_prefix_qzs_m6.yaml", root / "configs" / "bfcl_takeover_k5.yaml"
    shutil.copy(REPO / "configs" / "bfcl_prefix_qzs_m6.yaml", qzs)
    shutil.copy(_variant(tmp_path, "takeover_k5"), takeover)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "the two arms")
    (root / "src" / "keep.txt").write_text("edited\n", encoding="utf-8")  # a dirty src/
    env = dict(SPLIT="test", CFG=str(qzs), BFCL_GIT_ROOT=str(root),
               BFCL_PREREG=str(_prereg(tmp_path, "**Status**: DRAFT")), SEEDS="1,2,3", CID="bfcl_x_test_y",
               MAX_PLANNER_CALLS="1", EXPECTED_CODEX_VERSION=None)
    steps = [
        ({}, "SPLIT=test needs BFCL_CONFIRM=E_FROZEN"),                                               # (a)
        ({"BFCL_CONFIRM": "E_FROZEN"}, "the E-prereg is not FROZEN"),                                  # (b)
        ({"BFCL_PREREG": str(prereg)}, "has uncommitted changes under src/, scripts/, configs/"),      # (c)
        (lambda: _git(root, "checkout", "--", "src/keep.txt"), "no qzs stem runs on the BFCL test split"),  # (d)
        ({"CFG": str(takeover)}, "registered at SEEDS=1,2 only"),                                      # (e)
        ({"SEEDS": None}, "a BFCL test campaign is exactly bfcl_takeover_k5_test_20260925"),           # (f)
        ({"CID": None}, "planner.type codex needs EXPECTED_CODEX_VERSION=0.153.4 (got '<unset>')"),   # (g) codex
        ({"EXPECTED_CODEX_VERSION": "0.153.4"}, "the registered test ceiling of takeover_k5 is 2400"),  # (g) ceiling
        ({"MAX_PLANNER_CALLS": None}, "planner_alone_cap81 must complete before the replay arms start"),  # (h)
    ]
    seen = []
    for change, message in steps:
        if callable(change):
            change()
        else:
            env.update(change)
        proc = _run(tmp_path, **env)
        assert proc.returncode == 2 and message in proc.stdout, (message, _out(proc))
        assert "selftest preflight ok" not in proc.stdout
        seen.append(message)
    assert len(seen) == 9
    _complete_ceiling(tmp_path)
    proc = _run(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert f"git checks passed against {root}" in proc.stdout
    _nothing_started(tmp_path)


# ---- gate (c): git, against a throwaway tree (j11 style) --------------------------------------------

def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def _git_tree(tmp: Path) -> tuple[Path, Path, Path]:
    root = tmp / "repo"
    for sub in ("docs", "src", "scripts", "configs"):
        (root / sub).mkdir(parents=True)
    prereg = root / "docs" / "prereg_bfcl_test_20260925.md"
    prereg.write_text(f"# E\n\n{FROZEN_LINE}\n\nbody\n", encoding="utf-8")
    for sub in ("src", "scripts"):
        (root / sub / "keep.txt").write_text("x\n", encoding="utf-8")
    cfg = root / "configs" / "bfcl_executor_alone_zs.yaml"
    shutil.copy(REPO / "configs" / "bfcl_executor_alone_zs.yaml", cfg)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "freeze")
    return root, prereg, cfg


def test_the_git_checks_refuse_an_uncommitted_prereg_a_dirty_tree_or_a_config_elsewhere(tmp_path: Path) -> None:
    root, prereg, cfg = _git_tree(tmp_path)
    env = dict(GO, CFG=str(cfg), BFCL_PREREG=str(prereg), BFCL_GIT_ROOT=str(root))
    proc = _run(tmp_path, **env)
    assert proc.returncode == 0, _out(proc)
    assert f"git checks passed against {root}" in proc.stdout and "git checks skipped" not in proc.stdout
    # The derived config records the committed config's blob and the tree's HEAD.
    text = _derived(tmp_path, "executor_alone_zs").read_text(encoding="utf-8")
    assert f"# git rev-parse HEAD: {_git(root, 'rev-parse', 'HEAD')}" in text
    assert f"# committed config git blob (git hash-object): {_git(root, 'hash-object', str(cfg))}" in text

    dirty = ("has uncommitted changes under src/, scripts/, configs/, data/bfcl_split_20260924.json or "
             "third_party/bfcl/; the test split runs only committed code and data")
    (root / "src" / "keep.txt").write_text("edited\n", encoding="utf-8")  # a dirty src/
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and dirty in proc.stdout, _out(proc)
    _git(root, "checkout", "--", "src/keep.txt")

    (root / "configs" / "new.yaml").write_text("x: 1\n", encoding="utf-8")  # an untracked config
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and dirty in proc.stdout
    (root / "configs" / "new.yaml").unlink()

    # The split file (the 150 test entries, E:26) and the vendored checker (E:24) are gated too.
    split = root / "data" / "bfcl_split_20260924.json"
    readme = root / "third_party" / "bfcl" / "README.md"
    for dst in (split, readme):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / dst.relative_to(root), dst)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "split and checker")
    assert _run(tmp_path, **env).returncode == 0
    for path in (split, readme):
        rel = str(path.relative_to(root))
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")  # an edit after the freeze
        proc = _run(tmp_path, **env)
        assert proc.returncode == 2 and dirty in proc.stdout, (rel, _out(proc))
        _git(root, "checkout", "--", rel)
    extra = root / "third_party" / "bfcl" / "bfcl_eval.py"  # an untracked file beside the checker
    extra.write_text("x = 1\n", encoding="utf-8")
    proc = _run(tmp_path, **env)
    assert proc.returncode == 2 and dirty in proc.stdout, _out(proc)
    extra.unlink()
    other = root / "data" / "unrelated.json"  # the rest of data/ is not gated
    other.write_text("{}\n", encoding="utf-8")
    assert _run(tmp_path, **env).returncode == 0
    other.unlink()

    prereg.write_text(prereg.read_text(encoding="utf-8") + "an edit after the freeze\n", encoding="utf-8")
    proc = _run(tmp_path, **env)  # a modified prereg (still FROZEN on disk)
    assert proc.returncode == 2 and "has uncommitted changes; the frozen text is the committed text" in proc.stdout
    _git(root, "checkout", "--", "docs/prereg_bfcl_test_20260925.md")

    untracked = root / "docs" / "prereg_other.md"  # FROZEN on disk but never committed
    untracked.write_text(f"{FROZEN_LINE}\n", encoding="utf-8")
    proc = _run(tmp_path, **dict(env, BFCL_PREREG=str(untracked)))
    assert proc.returncode == 2 and "is not committed; FROZEN means committed" in proc.stdout, _out(proc)
    untracked.unlink()

    elsewhere = _variant(tmp_path, "executor_alone_zs")  # the same config, outside <root>/configs
    proc = _run(tmp_path, **dict(env, CFG=str(elsewhere)))
    assert proc.returncode == 2 and f"CFG must live in {root}/configs on SPLIT=test (got {elsewhere})" in proc.stdout
    proc = _run(tmp_path, **dict(env, CFG=str(REPO / "configs" / "bfcl_executor_alone_zs.yaml")))
    assert proc.returncode == 2 and f"CFG must live in {root}/configs" in proc.stdout

    assert _run(tmp_path, **env).returncode == 0
    proc = _run(tmp_path, **dict(env, BFCL_GIT_ROOT=None))
    assert proc.returncode == 0 and "selftest: git checks skipped (BFCL_GIT_ROOT unset)" in proc.stdout


# ---- OK paths: all 13 arms, with the derived config (S2) --------------------------------------------

@pytest.mark.parametrize("stem", sorted(ARMS))
def test_every_test_arm_passes_preflight_with_a_complete_test_ceiling(tmp_path: Path, stem: str) -> None:
    _complete_ceiling(tmp_path)
    cfg = _variant(tmp_path, stem)
    proc = _run(tmp_path, CFG=str(cfg), **GO)
    assert proc.returncode == 0, _out(proc)
    system, receiver, ceiling = ARMS[stem]
    derived = _derived(tmp_path, stem)
    line = _ok_line(proc)
    assert (f"system={system} cid={_cid(stem)} receiver={receiver} target=300 split=test config={derived} "
            f"ceiling={_ceiling(tmp_path)} max_planner_calls={ceiling or 'none'} gate=--gate") in line
    assert "target=300 (150 tasks x 2 seeds) seeds=1,2 smoke=2 tasks x seed 1" in proc.stdout
    if ceiling:
        assert line.endswith("gate=--gate --expect-planner --expect-model gpt-5.6-luna")
        assert (f"MAX_PLANNER_CALLS={ceiling} (hosted planner calls of {_cid(stem)}; the registered test ceiling"
                in proc.stdout)
    else:
        assert line.endswith(" gate=--gate") and "[bfcl] MAX_PLANNER_CALLS=" not in proc.stdout
    replaying = stem in PACKET_ARMS | PREFIX_ARMS
    if replaying:
        what = "prefix source" if stem in PREFIX_ARMS else "planner.packet_source"
        assert (f"{what} {_ceiling(tmp_path)}: exists=1 non_crashed=300 crashed=0 unreadable=0 missing_keys=0/300 "
                "(need >= 300 non-crashed for seeds 1,2") in proc.stdout
        assert "planner_alone episodes scored without a plan: 0 (cap 15, as J10 A1 §4.2)" in proc.stdout
    else:
        assert "missing_keys" not in proc.stdout and "scored without a plan" not in proc.stdout
    # The derived config: the committed mapping with only campaign_id and the ceiling path rewritten.
    committed = _flatten(yaml.safe_load(cfg.read_text(encoding="utf-8")))
    text = derived.read_text(encoding="utf-8")
    got = _flatten(yaml.safe_load(text))
    assert set(got) == set(committed)
    rewritten = {"campaign_id"}
    if replaying:
        rewritten.add("planner.packet_source")
    if stem in PREFIX_ARMS:
        rewritten.add("handoff.source_campaign")
    assert {k for k in committed if committed[k] != got[k]} == rewritten
    assert committed["campaign_id"] == f"bfcl_{stem}_dev_20260924" and got["campaign_id"] == _cid(stem)
    for key in rewritten - {"campaign_id"}:
        assert committed[key] == str(tmp_path / "out" / DEV_SOURCE_CID) and got[key] == str(_ceiling(tmp_path))
    # on_missing is the committed one: call_if_planless on a packet arm, fail on a prefix arm (seam S7).
    if replaying:
        assert got["planner.on_missing"] == ("fail" if stem in PREFIX_ARMS else "call_if_planless")
    assert "_dev_20260924" not in text
    lines = text.splitlines()
    assert all(l.startswith("#") for l in lines[:7]) and not lines[7].startswith("#")
    assert "# HEAD and time are the first writer's: a later job with the same mapping reuses this file unchanged" in text
    assert f"# committed config: {cfg}" in lines
    blob = subprocess.run(["git", "hash-object", str(cfg)], capture_output=True, text=True).stdout.strip()
    assert f"# committed config git blob (git hash-object): {blob}" in lines
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert f"# git rev-parse HEAD: {head}" in lines
    assert any(re.fullmatch(r"# written \(UTC\): \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", l) for l in lines)
    assert f"derived test config {derived} (written)" in proc.stdout
    _nothing_started(tmp_path)


def test_an_identical_derived_config_is_reused_and_never_rewritten(tmp_path: Path) -> None:
    derived = _derived(tmp_path, "executor_alone_zs")
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 0 and f"derived test config {derived} (written)" in proc.stdout, _out(proc)
    before = derived.read_text(encoding="utf-8")
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 0 and f"derived test config {derived} (reused)" in proc.stdout, _out(proc)
    assert derived.read_text(encoding="utf-8") == before
    # The reused file keeps its first writer's HEAD; the log line names this job's own.
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert f"this job's HEAD {head} (the file's HEAD comment is its first writer's)" in proc.stdout
    # The same mapping under other comments is the same config: reused, and left as it is.
    other = "# written by hand\n" + yaml.safe_dump(yaml.safe_load(before), sort_keys=True)
    derived.write_text(other, encoding="utf-8")
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 0 and "(reused)" in proc.stdout, _out(proc)
    assert derived.read_text(encoding="utf-8") == other


def test_a_different_derived_config_already_there_is_fatal(tmp_path: Path) -> None:
    derived = _derived(tmp_path, "executor_alone_zs")
    derived.parent.mkdir(parents=True)
    stale = f"campaign_id: {_cid('executor_alone_zs')}\nenv: bfcl\n"
    derived.write_text(stale, encoding="utf-8")
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 2, _out(proc)
    assert f"{derived} already exists with different content; derived configs are never rewritten" in proc.stdout
    assert derived.read_text(encoding="utf-8") == stale
    # The right mapping, but a comment still naming the dev campaign: the substring tripwire.
    proc_ok = _run(tmp_path / "fresh", **GO)
    assert proc_ok.returncode == 0, _out(proc_ok)
    good = _derived(tmp_path / "fresh", "executor_alone_zs").read_text(encoding="utf-8")
    derived.write_text("# copied from bfcl_executor_alone_zs_dev_20260924\n" + good, encoding="utf-8")
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 2 and "contains _dev_20260924" in proc.stdout, _out(proc)


@pytest.mark.parametrize("case", ["committed_prefix_config", "extra_dev_value"])
def test_a_dev_id_left_in_the_derived_config_is_fatal_and_nothing_is_written(tmp_path: Path, case: str) -> None:
    if case == "committed_prefix_config":
        # Its source is /scratch/.../bfcl_planner_alone_cap81_dev_20260924, not ${OUT}/... (OUT is tmp here), so
        # the rewrite does not touch it and the tripwire fires.
        stem, cfg = "prefix_zs_m6", REPO / "configs" / "bfcl_prefix_zs_m6.yaml"
    else:
        stem = "executor_alone_zs"
        cfg = _variant(tmp_path, stem, {"notes": "compare bfcl_executor_alone_zs_dev_20260924"})
    proc = _run(tmp_path, CFG=str(cfg), **GO)
    assert proc.returncode == 2, _out(proc)
    assert "contains _dev_20260924: a dev campaign id or dev source survived the rewrite" in proc.stdout
    assert not _derived(tmp_path, stem).exists()
    _nothing_started(tmp_path)


# ---- gate (g): the registered hosted-call ceilings (S5) ---------------------------------------------

@pytest.mark.parametrize(
    "stem, value, ok",
    [
        ("planner_alone_cap81", "6000", True),
        ("planner_alone_cap81", "4800", False),  # the dev default rate, 16 x 300
        ("takeover_k5", "2400", True),
        ("advise_k5_fullctx", "1200", False),     # 4 x 300, the dev default rate
        ("advise_k5_neutral", "2401", False),
        ("plan_zs", "1200", True),
        ("plan_zs", "600", False),
    ],
)
def test_a_passed_max_planner_calls_must_be_the_registered_ceiling(tmp_path: Path, stem: str, value: str, ok: bool) -> None:
    _complete_ceiling(tmp_path)
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, stem)), MAX_PLANNER_CALLS=value, **GO)
    if ok:
        assert proc.returncode == 0 and f"max_planner_calls={value} " in _ok_line(proc), _out(proc)
    else:
        assert proc.returncode == 2, _out(proc)
        assert (f"MAX_PLANNER_CALLS={value}: the registered test ceiling of {stem} is {ARMS[stem][2]} (E:432-442)"
                in proc.stdout)


@pytest.mark.parametrize(
    "stem, per_episode, ok",
    [
        # E:446-455: refused when the 2-episode smoke averages more than ceiling / (300 x 1.2) live calls.
        ("planner_alone_cap81", 16, True),    # ceil(16 x 300 x 1.2) = 5760 <= 6000
        ("planner_alone_cap81", 17, False),   # 6120 > 6000
        ("takeover_k5", 6, True),             # 2160 <= 2400
        ("takeover_k5", 7, False),            # 2520 > 2400
        ("plan_zs", 3, True),                 # 1080 <= 1200
        ("plan_zs", 4, False),                # 1440 > 1200
    ],
)
def test_the_launch_check_projects_the_smoke_against_the_test_ceiling(tmp_path: Path, stem: str, per_episode: int,
                                                                       ok: bool) -> None:
    if stem != "planner_alone_cap81":  # the ceiling IS planner_alone's own campaign: nothing would be missing
        _complete_ceiling(tmp_path)
    smoke = f"{_cid(stem)}_smoke_1"
    _write_results(tmp_path / "out" / smoke, [("a", 1, None), ("b", 1, None)], ARMS[stem][0],
                   totals={"planner_calls_total": per_episode})
    proc = _run(tmp_path, CFG=str(_variant(tmp_path, stem)), BFCL_SELFTEST_STAGE="spend", BFCL_SPEND_RATE_CID=smoke, **GO)
    want = -(-per_episode * 300 * 12 // 10)  # ceil(rate x 300 x 1.2), by hand
    assert f"missing=300 projection={want} ceiling={ARMS[stem][2]}" in proc.stdout, _out(proc)
    assert proc.returncode == (0 if ok else 1), _out(proc)


# ---- gate (h): the test ceiling and the planless cap (S1, S7) ---------------------------------------

@pytest.mark.parametrize("stem", ["takeover_k5", "prefix_bplus_m6"])
def test_a_replaying_arm_needs_all_300_keys_of_the_test_ceiling(tmp_path: Path, stem: str) -> None:
    cfg = str(_variant(tmp_path, stem))
    what = "prefix source" if stem in PREFIX_ARMS else "planner.packet_source"
    src = _ceiling(tmp_path)
    wait = f"{what} campaign is not complete; planner_alone_cap81 must complete before the replay arms start"
    # A complete DEV ceiling is not the test ceiling.
    _write_results(tmp_path / "out" / DEV_SOURCE_CID, [(t, s, None) for t in DEV_IDS for s in (1, 2)], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **GO)
    assert proc.returncode == 2 and wait in proc.stdout and f"{what} {src}: exists=0" in proc.stdout, _out(proc)
    # 299 of the 300 keys.
    _write_results(src, [(t, s, None) for i, t in enumerate(TEST_IDS) for s in (1, 2) if (i, s) != (149, 2)],
                   "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **GO)
    assert proc.returncode == 2 and wait in proc.stdout, _out(proc)
    assert "non_crashed=299 crashed=0 unreadable=0 missing_keys=1/300 (need >= 300" in proc.stdout
    assert f"first missing <seed>/<task> keys: 2/{TEST_IDS[149]}" in proc.stdout
    # The 300th key crashed.
    _write_results(src, [(TEST_IDS[149], 2, "crash")], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **GO)
    assert proc.returncode == 2 and "non_crashed=299 crashed=1 unreadable=0 missing_keys=1/300" in proc.stdout
    _write_results(src, [(TEST_IDS[149], 2, None)], "planner_alone")
    proc = _run(tmp_path, CFG=cfg, **GO)
    assert proc.returncode == 0, _out(proc)
    assert "non_crashed=300 crashed=0 unreadable=0 missing_keys=0/300" in proc.stdout


@pytest.mark.parametrize("stem", ["takeover_k5", "plan_zs", "prefix_zs_m6", "prefix_bplus_m2"])
def test_15_planless_keys_pass_and_16_stop_every_replaying_arm(tmp_path: Path, stem: str) -> None:
    src = _complete_ceiling(tmp_path)
    cfg = str(_variant(tmp_path, stem))
    keys = [(t, 1) for t in TEST_IDS[:8]] + [(t, 2) for t in TEST_IDS[100:107]]
    _planless(src, keys)
    proc = _run(tmp_path, CFG=cfg, **GO)
    # By hand: 5 % of 300 = 15, so 15 pass ("more than 15" stops, E:286).
    assert proc.returncode == 0, _out(proc)
    assert "planner_alone episodes scored without a plan: 15 (cap 15, as J10 A1 §4.2): 1/" in proc.stdout
    s7 = "prefix arm: the 15 planless key(s) replay at effective depth 0 with no plan call (J10 :224-225; seam S7)"
    assert (s7 in proc.stdout) == (stem in PREFIX_ARMS)
    # S7 needs no config key: the derived config holds the committed keys only.
    committed = _flatten(yaml.safe_load(Path(cfg).read_text(encoding="utf-8")))
    assert set(_flatten(yaml.safe_load(_derived(tmp_path, stem).read_text(encoding="utf-8")))) == set(committed)
    _planless(src, [(TEST_IDS[149], 2)])  # 16
    proc = _run(tmp_path, CFG=cfg, **GO)
    assert proc.returncode == 2, _out(proc)
    assert ("16 planner_alone episodes wrote no plan, above the cap of 15 (5 % of 300); diagnose before any "
            "replay arm runs") in proc.stdout


def test_a_packet_arm_that_would_abort_on_a_planless_key_is_refused(tmp_path: Path) -> None:
    src = _complete_ceiling(tmp_path)
    _planless(src, [(TEST_IDS[3], 1)])
    cfg = _variant(tmp_path, "plan_zs", {"planner": {"on_missing": "fail"}})
    proc = _run(tmp_path, CFG=str(cfg), **GO)
    assert proc.returncode == 2, _out(proc)
    assert "planner.on_missing is 'fail', so the 1 planless source episode(s) would crash" in proc.stdout


# ---- the dev path never touches a test name (the j10_arm.pbs:369 analogue) --------------------------

def test_a_dev_run_never_writes_a_test_campaign_or_replays_a_test_source(tmp_path: Path) -> None:
    proc = _run(tmp_path, CID="bfcl_executor_alone_zs_dev_test_x")
    assert proc.returncode == 2, _out(proc)
    assert "CID=bfcl_executor_alone_zs_dev_test_x says _test_; a dev run must never look like a test campaign" in proc.stdout
    src = _complete_ceiling(tmp_path)  # complete, so only its name refuses it
    cfg = _variant(tmp_path, "takeover_k5", {"planner": {"packet_source": str(src)}})
    proc = _run(tmp_path, CFG=str(cfg), EXPECTED_CODEX_VERSION="0.153.4")
    assert proc.returncode == 2, _out(proc)
    assert f"replay source {src} is a test campaign; a dev run must never replay a test source" in proc.stdout
    # BFCL_CONFIRM does not turn a dev run into anything else.
    proc = _run(tmp_path, BFCL_CONFIRM="E_FROZEN")
    assert proc.returncode == 0, _out(proc)
    line = _ok_line(proc)
    assert "cid=bfcl_executor_alone_zs_dev_20260924" in line and "split=test" not in line
    assert "derived test config" not in proc.stdout and not (tmp_path / "logs" / "bfcl_test_configs").exists()


# ---- the refill log (S3) and the tally (S6) ---------------------------------------------------------

def test_the_refill_log_records_every_crash_about_to_be_purged(tmp_path: Path) -> None:
    cid = _cid("executor_alone_zs")
    arm = tmp_path / "out" / cid
    _write_results(arm, [(TEST_IDS[0], 1, None), (TEST_IDS[1], 1, "crash"), (TEST_IDS[2], 2, "crash"),
                         (TEST_IDS[3], 2, "limit")], "executor_alone")
    _events(arm / "executor_alone" / "1" / TEST_IDS[1], [DIVERGED])
    # A crash whose FIRST attempt diverged but whose last attempt's error carries no reason: reason is empty.
    _events(arm / "executor_alone" / "2" / TEST_IDS[2], [DIVERGED],
            [{"event_type": "error", "actor": "executor", "error_type": "crash", "payload": {"detail": "boom"}}])
    bad = arm / "executor_alone" / "1" / TEST_IDS[4]
    bad.mkdir(parents=True)
    (bad / "result.json").write_text("{trunc", encoding="utf-8")  # unreadable: purged, but not a crashed episode
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="refill", PBS_JOBID="4242.aqua", **GO)
    assert proc.returncode == 0, _out(proc)
    log = tmp_path / "logs" / "bfcl_refills" / f"{cid}.tsv"
    assert f"refill log {log}: 2 crashed episode(s) of {cid} recorded before the crash-only purge" in proc.stdout
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines[0] == REFILL_HEADER
    rows = [line.split("\t") for line in lines[1:]]
    assert [r[:6] for r in rows] == [[cid, "1", TEST_IDS[1], "crash", "replay_divergence", "4242.aqua"],
                                     [cid, "2", TEST_IDS[2], "crash", "", "4242.aqua"]]
    assert all(len(r) == 7 and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", r[6]) for r in rows)
    # Append-only, one header; the stage purges nothing.
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="refill", **GO)
    assert proc.returncode == 0, _out(proc)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert lines.count(REFILL_HEADER) == 1 and len(lines) == 5
    assert [line.split("\t")[5] for line in lines[3:]] == ["none", "none"]
    assert (arm / "executor_alone" / "1" / TEST_IDS[1] / "result.json").is_file()
    # No refill log on dev.
    proc = _run(tmp_path / "dev", BFCL_SELFTEST_STAGE="refill")
    assert proc.returncode == 0 and "no refill log on SPLIT=dev" in proc.stdout, _out(proc)
    assert not (tmp_path / "dev" / "logs" / "bfcl_refills").exists()


def test_the_refill_reason_is_the_last_error_event_of_the_last_attempt(tmp_path: Path) -> None:
    # S3: "reason is the last-attempt error event's payload.reason (empty if none)": the LAST error event decides,
    # so a reasonless error after the divergence leaves it empty, and a divergence after a reasonless error sets it.
    cid = _cid("executor_alone_zs")
    arm = tmp_path / "out" / cid
    reasonless = {"event_type": "error", "actor": "executor", "error_type": "crash", "payload": {"detail": "boom"}}
    step = {"event_type": "step", "actor": "executor", "payload": {}}
    _write_results(arm, [(TEST_IDS[0], 1, "crash"), (TEST_IDS[1], 1, "crash"), (TEST_IDS[2], 1, "crash")],
                   "executor_alone")
    _events(arm / "executor_alone" / "1" / TEST_IDS[0], [DIVERGED, reasonless])
    _events(arm / "executor_alone" / "1" / TEST_IDS[1], [reasonless, DIVERGED, step])
    _events(arm / "executor_alone" / "1" / TEST_IDS[2], [{**DIVERGED, "payload": "not a mapping"}])
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="refill", **GO)
    assert proc.returncode == 0, _out(proc)
    rows = [line.split("\t") for line in
            (tmp_path / "logs" / "bfcl_refills" / f"{cid}.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    assert {r[2]: r[4] for r in rows} == {TEST_IDS[0]: "", TEST_IDS[1]: "replay_divergence", TEST_IDS[2]: ""}


# ---- a self-test on SPLIT=test never falls back to the real /scratch trees --------------------------
# Every case also leaves BFCL_CONFIRM unset: were the guard missing, gate (a) would still stop the run before
# anything is read or written, and the test would fail on the message rather than touch /scratch.

@pytest.mark.parametrize("stage", [None, "refill", "tally", "spend"])
@pytest.mark.parametrize("unset", ["BFCL_LOGDIR", "BFCL_OUT"])
def test_a_test_selftest_needs_both_scratch_seams(tmp_path: Path, stage: str | None, unset: str) -> None:
    proc = _run(tmp_path, **{**GO, "BFCL_CONFIRM": None, "BFCL_SELFTEST_STAGE": stage, unset: None})
    assert proc.returncode == 2, _out(proc)
    assert (f"selftest on SPLIT=test needs {unset} set to a scratch directory: unset, it defaults to the real "
            "/scratch/n12194778/sidekick/results / /scratch/n12194778/sidekick/logs") in proc.stdout, _out(proc)
    assert "BFCL_CONFIRM" not in proc.stdout and "selftest preflight ok" not in proc.stdout
    assert "config env=" not in proc.stdout  # refused before the config is even read


@pytest.mark.parametrize(
    "seam, value, real",
    [
        ("BFCL_LOGDIR", "/scratch/n12194778/sidekick/logs", "/scratch/n12194778/sidekick/logs"),
        ("BFCL_LOGDIR", "/scratch/n12194778/sidekick/logs/", "/scratch/n12194778/sidekick/logs"),
        ("BFCL_LOGDIR", "/scratch/n12194778/sidekick/logs/../logs/selftest", "/scratch/n12194778/sidekick/logs"),
        ("BFCL_OUT", "/scratch/n12194778/sidekick/results", "/scratch/n12194778/sidekick/results"),
        ("BFCL_OUT", "/scratch/n12194778/sidekick//results/x", "/scratch/n12194778/sidekick/results"),
        ("BFCL_OUT", "/scratch/n12194778/sidekick/logs", "/scratch/n12194778/sidekick/logs"),  # the other real tree
        ("BFCL_LOGDIR", "/scratch/n12194778/sidekick/results", "/scratch/n12194778/sidekick/results"),
    ],
)
def test_a_test_selftest_refuses_the_real_trees(tmp_path: Path, seam: str, value: str, real: str) -> None:
    proc = _run(tmp_path, **{**GO, "BFCL_CONFIRM": None, "BFCL_SELFTEST_STAGE": "refill", seam: value})
    assert proc.returncode == 2, _out(proc)
    want = f"selftest on SPLIT=test: {seam}={value} is (under) the real {os.path.realpath(real)}; point it at a scratch"
    assert want in proc.stdout and "BFCL_CONFIRM" not in proc.stdout, _out(proc)


def test_a_test_selftest_refuses_a_link_into_the_real_logs_and_a_relative_seam(tmp_path: Path) -> None:
    link = tmp_path / "link"
    link.symlink_to("/scratch/n12194778/sidekick/logs")  # a link in tmp; nothing is created under /scratch
    proc = _run(tmp_path, **{**GO, "BFCL_CONFIRM": None, "BFCL_SELFTEST_STAGE": "refill", "BFCL_LOGDIR": str(link / "x")})
    assert proc.returncode == 2 and f"BFCL_LOGDIR={link / 'x'} is (under) the real" in proc.stdout, _out(proc)
    proc = _run(tmp_path, **{**GO, "BFCL_CONFIRM": None, "BFCL_OUT": "out"})
    assert proc.returncode == 2 and "BFCL_OUT=out must be an absolute path" in proc.stdout, _out(proc)
    # With both seams in tmp the same run reaches gate (a): the guard stops only a fallback to the real trees.
    proc = _run(tmp_path, **{**GO, "BFCL_CONFIRM": None, "BFCL_SELFTEST_STAGE": "refill"})
    assert proc.returncode == 2 and "SPLIT=test needs BFCL_CONFIRM=E_FROZEN" in proc.stdout, _out(proc)
    assert "selftest on SPLIT=test" not in proc.stdout


def test_the_scratch_guard_runs_first_and_only_on_a_test_selftest() -> None:
    text = PBS.read_text(encoding="utf-8")
    guard = text.index('if [[ "${SELFTEST}" == "1" && "${SPLIT}" == "test" ]]; then')
    assert text.index("fatal () {") < guard < text.index('cd "${REPO}" || exit 1') < text.index("# ---- config ---")
    assert 'REAL_OUT=/scratch/n12194778/sidekick/results' in text and 'REAL_LOGDIR=/scratch/n12194778/sidekick/logs' in text


def test_the_running_wrapper_is_logged_beside_the_committed_one(tmp_path: Path) -> None:
    proc = _run(tmp_path, **GO)
    assert proc.returncode == 0, _out(proc)
    running = hashlib.sha256(PBS.read_bytes()).hexdigest()
    shown = subprocess.run(["git", "-C", str(REPO), "show", "HEAD:scripts/pbs/bfcl_arm.pbs"], capture_output=True)
    committed = hashlib.sha256(shown.stdout).hexdigest() if shown.returncode == 0 else "unknown"
    assert (f"[bfcl] wrapper running sha256={running} ({PBS}); {REPO} HEAD:scripts/pbs/bfcl_arm.pbs "
            f"sha256={committed}") in proc.stdout, _out(proc)
    warned = "WARN: the running wrapper is not (or could not be compared with) the committed" in proc.stdout
    assert warned == (running != committed)  # logged, never refused
    # An edited copy run from elsewhere against the same BFCL_REPO: its own hash, a WARN, and no refusal.
    copy = tmp_path / "elsewhere" / "bfcl_arm.pbs"
    copy.parent.mkdir()
    copy.write_text(PBS.read_text(encoding="utf-8") + "# an edit no commit records\n", encoding="utf-8")
    proc = _run(tmp_path, _script=copy, **GO)
    assert proc.returncode == 0, _out(proc)
    assert f"[bfcl] wrapper running sha256={hashlib.sha256(copy.read_bytes()).hexdigest()} ({copy});" in proc.stdout
    assert "WARN: the running wrapper is not (or could not be compared with) the committed" in proc.stdout


def test_a_real_test_submission_runs_only_the_registered_python() -> None:
    # Not executable here (it is the non-self-test path): the pin must sit before the first use of PY.
    text = PBS.read_text(encoding="utf-8")
    default = 'REGISTERED_PY="${SIDEKICK_VENV}/bin/python"\nPY="${PY:-${REGISTERED_PY}}"\n'
    pin = ('\nif [[ "${SPLIT}" == "test" && "${SELFTEST}" != "1" && "${PY}" != "${REGISTERED_PY}" ]]; then\n'
           '  fatal "SPLIT=test runs only ${REGISTERED_PY} (got PY=${PY})"\nfi\n')
    assert text.count(default) == 1 and text.count(pin) == 1 and text.count('PY="${PY:-') == 1
    assert text.index(default) < text.index(pin) < text.index('"${PY}" -')


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_the_test_tally_reads_divergent_keys_under_am5_b(tmp_path: Path) -> None:
    _complete_ceiling(tmp_path)
    stem, system = "prefix_zs_m6", "prefix_handoff"
    cid = _cid(stem)
    arm = tmp_path / "out" / cid
    env = dict(GO, CFG=str(_variant(tmp_path, stem)))
    keys = [(t, s) for t in TEST_IDS for s in (1, 2)]
    _write_results(arm, [(t, s, None) for t, s in keys], system)
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 0, _out(proc)
    assert "COMPLETE: 300/300 non-crashed, 0 crashed" in proc.stdout
    assert "complete under Am5 §B: 0 divergent keys" in proc.stdout

    # Three replay_divergence crashes never refilled are ordinary crashes: resubmit (3).
    _diverge(arm, system, keys[:3])
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 3, _out(proc)
    assert ": 0 (cap 15); replay_divergence crashes not yet refilled: 3" in proc.stdout
    assert "INCOMPLETE: 297/300 non-crashed, 3 crashed" in proc.stdout

    # A crash-only resumption logs them before its purge; crashing again, they are divergent keys: complete (0).
    assert _run(tmp_path, BFCL_SELFTEST_STAGE="refill", **env).returncode == 0
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 0, _out(proc)
    labels = " ".join(f"{s}/{t}" for t, s in sorted(keys[:3]))
    assert f": 3 (cap 15); replay_divergence crashes not yet refilled: 0; keys: {labels}" in proc.stdout
    assert "complete under Am5 §B: 3 divergent keys" in proc.stdout and "COMPLETE: 297/300" not in proc.stdout

    # An ordinary crash beside them is not excused.
    _write_results(arm, [(keys[3][0], keys[3][1], "crash")], system)
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 3 and "INCOMPLETE: 296/300 non-crashed, 4 crashed" in proc.stdout, _out(proc)
    assert "complete under Am5 §B" not in proc.stdout

    # 16 refilled divergent keys: over the cap (1); 15: complete.
    _diverge(arm, system, keys[3:16])
    assert _run(tmp_path, BFCL_SELFTEST_STAGE="refill", **env).returncode == 0
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 1, _out(proc)
    assert "over cap: 16 divergent keys > 15" in proc.stdout
    _write_results(arm, [(keys[15][0], keys[15][1], None)], system)
    (arm / system / str(keys[15][1]) / keys[15][0] / "events.jsonl").unlink()
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **env)
    assert proc.returncode == 0, _out(proc)
    assert "complete under Am5 §B: 15 divergent keys" in proc.stdout


@pytest.mark.skipif(shutil.which("jq") is None, reason="jq not on PATH")
def test_a_non_replaying_test_arm_has_no_divergent_keys(tmp_path: Path) -> None:
    cid = _cid("executor_alone_zs")
    arm = tmp_path / "out" / cid
    keys = [(t, s) for t in TEST_IDS for s in (1, 2)]
    _write_results(arm, [(t, s, None) for t, s in keys[2:]], "executor_alone")
    _diverge(arm, "executor_alone", keys[:2])
    assert _run(tmp_path, BFCL_SELFTEST_STAGE="refill", **GO).returncode == 0
    proc = _run(tmp_path, BFCL_SELFTEST_STAGE="tally", **GO)
    assert proc.returncode == 3, _out(proc)
    assert "INCOMPLETE: 298/300 non-crashed, 2 crashed" in proc.stdout and "divergent keys" not in proc.stdout


# ---- the run path (not executable here: it would create held-out episodes) ---------------------------

def test_the_run_path_uses_the_derived_config_and_logs_refills_before_the_purge() -> None:
    text = PBS.read_text(encoding="utf-8")
    run = text.split("# ---- purge crashed episodes of THIS campaign only", 1)[1]
    assert run.index('[[ "${SPLIT}" == "test" ]] && bfcl_refill_log') < run.index("--purge-crashed-only")
    # Smoke runner, smoke gate, arm runner and final gate all get the derived config on test.
    assert run.count('--config "${RUN_CFG}"') == 4 and '--config "${CFG}"' not in run
    assert '--system "${SYSTEM}" --split "${SPLIT}" --tasks "${SMOKE_TASKS}" --seeds "${SMOKE_SEED}"' in run
    assert 'SCID="${CID}_smoke_${JOBNUM}"' in run
    smoke = run.split("# ---- the arm", 1)[0]
    assert "rm " not in smoke  # the smoke tree is never deleted
    # The gate flags are the dev ones: no --expect-split (split_check compares against AppWorld dev ids).
    assert "--expect-split" not in text.replace("# No --expect-split", "")
    assert 'RUN_CFG="${CFG}"' in text and 'RUN_CFG="${DERIVED_DIR}/${CID}.yaml"' in text
