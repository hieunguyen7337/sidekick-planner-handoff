"""The four dev arms of plan 2026-09-24 (R2.4, D2, D3, R7.1): configs, the no-op executor, registry.

All four are exploratory and dev only; none is a J10 arm (tests/unit/test_j10_configs.py pins that
set). Each config is its source with the listed keys changed. As in test_j10_configs, the list is
stated here rather than read from the headers, so a header edit that widens what may differ fails
a test instead of licensing the drift. Nothing here runs an arm: the registry cases take the
HJ12_GUARD_SELFTEST path of hj12_live.pbs, and the no-op episode runs on MockEnv.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from _pbs_arrays import read_bash_array
from sidekick.agents.executor import DEFAULT_EXECUTOR_SCRIPT, MockExecutor
from sidekick.agents.planner import CodexExecPlanner, MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.runner import make_executor, make_planner
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
HJ12_LIVE = REPO / "scripts" / "pbs" / "hj12_live.pbs"
HJ1B = REPO / "scripts" / "pbs" / "hj1b_planner_alone.pbs"
sys.path.insert(0, str(REPO / "scripts" / "setup"))
from verify_configs import validate_prompt_budget  # noqa: E402

DATE = "20260924"
LUNA = "gpt-5.6-luna"
# R7.1: executor: becomes the mock; every vLLM key goes, max_prompt_tokens stays (verify_configs).
NOOP_EXECUTOR = (
    "executor.type", "executor.script", "executor.model", "executor.base_url", "executor.lora_name",
    "executor.temperature", "executor.max_tokens", "executor.stop",
    "executor.chat_template_kwargs.enable_thinking", "executor.timeout_s",
)
# stem -> (source, fields that differ)
REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    "dev_advise_neutral_fixed_k_1_fullctx": (
        "configs/hj13_advise_fixed_k_1_fullctx.yaml", ("campaign_id", "planner.correct_prompt")),
    "dev_advise_structured_fixed_k_10_fullctx": (
        "configs/hj12_advise_fixed_k_10_fullctx.yaml", ("campaign_id", "planner.correct_prompt")),
    "dev_planner_alone_cap81_high": (
        "configs/hj13_planner_alone_cap81.yaml",
        ("campaign_id", "planner.reasoning_effort", "limits.per_step_timeout_s")),
    "dev_noop_complete": ("configs/hj8_executor_alone_bplus.yaml", ("campaign_id",) + NOOP_EXECUTOR),
}
# The value each changed key must hold, from the brief's table (plan §4, W3/W4).
VALUES: dict[str, dict[str, object]] = {
    "dev_advise_neutral_fixed_k_1_fullctx": {"planner.correct_prompt": "neutral"},
    "dev_advise_structured_fixed_k_10_fullctx": {"planner.correct_prompt": "structured"},
    "dev_planner_alone_cap81_high": {"planner.reasoning_effort": "high", "limits.per_step_timeout_s": 300},
    "dev_noop_complete": {"executor.type": "mock", "executor.script": ["COMPLETE"]},
}
# Hosted arms: expected calls as the header states them, marked as the plan's estimate.
EXPECTED_CALLS = {
    "dev_advise_neutral_fixed_k_1_fullctx": "≈ 2,170",
    "dev_advise_structured_fixed_k_10_fullctx": "≈ 300",
    "dev_planner_alone_cap81_high": "≈ 1,700",
}
REVIEW_ARMS = ["dev_advise_neutral_fixed_k_1_fullctx", "dev_advise_structured_fixed_k_10_fullctx"]
STEMS = sorted(REGISTRY)

SOURCE_RE = re.compile(r"^# Source: (configs/\S+\.yaml)(?:\s|$)")
DIFFERS_RE = re.compile(r"^# Differs from source in: (.+)$")
_MISSING = object()


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), path
    return data


def _cfg(stem: str) -> dict:
    return _load(CONFIGS / f"{stem}.yaml")


def _flatten(value: object, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict) and value:
        out: dict[str, object] = {}
        for key, child in value.items():
            out.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value}


def _diff(a: dict, b: dict) -> set[str]:
    """Dotted paths whose value differs, including a key present on one side only."""
    fa, fb = _flatten(a), _flatten(b)
    return {k for k in fa.keys() | fb.keys() if fa.get(k, _MISSING) != fb.get(k, _MISSING)}


def _header(stem: str) -> list[str]:
    """The leading comment block; the first non-comment line ends it."""
    header = []
    for line in (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    return header


def _declared(stem: str) -> tuple[str, list[str]]:
    header = _header(stem)
    sources = [m.group(1) for m in map(SOURCE_RE.match, header) if m]
    differs = [m.group(1) for m in map(DIFFERS_RE.match, header) if m]
    assert len(sources) == 1 and len(differs) == 1, f"{stem}: need one Source and one Differs line"
    return sources[0], [f.strip() for f in differs[0].split(",")]


def _header_text(stem: str) -> str:
    """The header as one line of prose, so a phrase may wrap across comment lines."""
    return " ".join(line.lstrip("#").strip() for line in _header(stem))


def _submit_lines(stem: str) -> list[str]:
    return [line[4:] for line in _header(stem) if line.startswith("#   ")]


# --- configs ------------------------------------------------------------------------------------


def test_the_dev_arms_are_not_j10_arms_and_are_named_after_their_stem():
    for stem in STEMS:
        assert not stem.startswith("j10_")
        assert _cfg(stem)["campaign_id"] == f"{stem}_{DATE}"


@pytest.mark.parametrize("stem", STEMS)
def test_header_declares_the_registered_source_and_fields(stem: str):
    source, fields = _declared(stem)
    assert len(fields) == len(set(fields)), fields
    assert (source, set(fields)) == (REGISTRY[stem][0], set(REGISTRY[stem][1]))


@pytest.mark.parametrize("stem", STEMS)
def test_differs_from_its_declared_source_only_in_the_declared_fields(stem: str):
    source, fields = _declared(stem)
    assert (REPO / source).is_file(), source
    # Equality, not subset: a declared field that no longer differs is a stale declaration.
    assert _diff(_load(REPO / source), _cfg(stem)) == set(fields)


@pytest.mark.parametrize("stem", STEMS)
def test_the_changed_keys_hold_the_planned_values(stem: str):
    flat = _flatten(_cfg(stem))
    for key, want in VALUES[stem].items():
        assert flat[key] == want, (stem, key)


@pytest.mark.parametrize("stem", STEMS)
def test_header_names_the_plan_and_says_dev_only(stem: str):
    text = _header_text(stem)
    assert "docs/plan_top_venue_20260924.md" in text
    assert "EXPLORATORY, DEV ONLY" in text


@pytest.mark.parametrize("stem", sorted(EXPECTED_CALLS))
def test_hosted_headers_state_expected_calls_and_the_ceiling(stem: str):
    text = _header_text(stem)
    assert f"Expected hosted calls: {EXPECTED_CALLS[stem]} [INFERRED from plan" in text
    assert "3,780" in text and "hj12_live.pbs:72" in text
    assert "covers R2.4 only if R2.4 runs alone in its job" in text


@pytest.mark.parametrize("stem", STEMS)
def test_no_split_key_and_dev_config_checks_pass(stem: str):
    cfg = _cfg(stem)
    # The split is a runner argument (--split, default "dev"); a split: key would be ignored.
    assert "split" not in cfg
    assert cfg["env"] == "appworld"
    assert validate_prompt_budget(cfg, f"configs/{stem}.yaml") == []


def test_hosted_arms_pin_luna_and_the_noop_arm_spends_nothing():
    for stem in EXPECTED_CALLS:
        planner = _cfg(stem)["planner"]
        assert (planner["type"], planner["model"]) == ("codex", LUNA), stem
    noop = _cfg("dev_noop_complete")
    assert noop["planner"] == {"type": "mock"}
    assert set(noop["executor"]) == {"type", "script", "max_prompt_tokens"}


def test_hosted_planners_build_with_the_new_values():
    # packet_source is dropped here only so the check does not read /scratch; it is covered above.
    for stem, key, want in (
        ("dev_advise_neutral_fixed_k_1_fullctx", "correct_prompt", "neutral"),
        ("dev_advise_structured_fixed_k_10_fullctx", "correct_prompt", "structured"),
        ("dev_planner_alone_cap81_high", "reasoning_effort", "high"),
    ):
        cfg = _cfg(stem)
        cfg["planner"] = {k: v for k, v in cfg["planner"].items() if not k.startswith("packet_")}
        planner = make_planner(cfg)
        assert isinstance(planner, CodexExecPlanner), stem
        assert getattr(planner.config, key) == want, stem
        assert planner.config.model == LUNA, stem


# --- the no-op executor (R7.1) ------------------------------------------------------------------


def test_make_executor_passes_a_mock_script_through():
    ex = make_executor({"executor": {"type": "mock", "script": ["COMPLETE"]}})
    assert type(ex) is MockExecutor and ex.script == ["COMPLETE"]
    # Once spent the mock keeps answering COMPLETE, so the one-entry script cannot run out.
    assert [ex.complete([])[0] for _ in range(3)] == ["COMPLETE", "COMPLETE", "COMPLETE"]


def test_without_a_script_the_mock_is_unchanged():
    for cfg in ({}, {"executor": {"type": "mock"}}, {"executor": {"type": "mock", "max_prompt_tokens": 30720}}):
        assert make_executor(cfg).script == DEFAULT_EXECUTOR_SCRIPT


def test_only_type_mock_reads_the_script():
    # Any other non-vllm type still falls through to the default mock, as before.
    ex = make_executor({"executor": {"type": "not_a_type", "script": ["COMPLETE"]}})
    assert type(ex) is MockExecutor and ex.script == DEFAULT_EXECUTOR_SCRIPT


@pytest.mark.parametrize("script", ["COMPLETE", [], ["COMPLETE", 1], {"a": "COMPLETE"}])
def test_a_malformed_script_raises(script):
    with pytest.raises(ValueError, match="executor.script"):
        make_executor({"executor": {"type": "mock", "script": script}})


def test_the_script_pass_through_reaches_no_j10_config():
    by_type: dict[str, list[str]] = {}
    for path in sorted(CONFIGS.glob("j10_*.yaml")):
        executor = _load(path).get("executor") or {}
        assert "script" not in executor, path
        by_type.setdefault(str(executor.get("type")), []).append(path.stem)
    assert sorted(by_type) == ["mock", "vllm"]
    assert by_type["mock"] == ["j10_planner_alone_cap81"]
    # The one mock J10 arm (planner_alone, which never calls it) builds the same executor as before.
    ex = make_executor(_load(CONFIGS / "j10_planner_alone_cap81.yaml"))
    assert type(ex) is MockExecutor and ex.script == DEFAULT_EXECUTOR_SCRIPT


class _NoCallPlanner(MockPlanner):
    def plan(self, *a, **kw):
        raise AssertionError("executor_alone called planner.plan")

    def correct(self, *a, **kw):
        raise AssertionError("executor_alone called planner.correct")

    def act(self, *a, **kw):
        raise AssertionError("executor_alone called planner.act")


def test_the_noop_config_ends_every_episode_at_step_one(tmp_path: Path):
    cfg = _cfg("dev_noop_complete")
    assert type(make_planner(cfg)) is MockPlanner
    executor = make_executor(cfg)
    log = EventLog(tmp_path, "noop")
    system = get_system("executor_alone", planner=_NoCallPlanner(), executor=executor, limits=RunLimits())
    try:
        result = system.run(MockEnv(), "copy_hello", 1, log, CostLedger(PriceSchedule({"models": {}, "local": {}})))
    finally:
        log.close()
    # By hand: one executor call answers COMPLETE at step 1; copy_hello needs outbox.txt written,
    # which never happens, so the episode fails with no planner call and no error.
    assert len(executor.complete_calls) == 1
    assert (result.steps, result.success, result.n_planner_calls, result.error_type) == (1, False, 0, None)


def test_the_noop_submit_line_is_a_cpu_dev_run_of_this_config():
    lines = _submit_lines("dev_noop_complete")
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("hpc --cpus 8 --mem 32gb --time 04:00:00 bash -c '")
    assert (
        "-m sidekick.runner --system executor_alone --split dev --tasks 57 --seeds 1,2 --env appworld"
        in line
    )
    assert "--config configs/dev_noop_complete.yaml --out /scratch/n12194778/sidekick/results" in line
    assert f"--campaign-id dev_noop_complete_{DATE}" in line
    assert "--gpu" not in line and "qsub" not in line


# --- registry: hj12_live.pbs (R2.4, D2) and hj1b_planner_alone.pbs (D3) --------------------------


def _select(**extra: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("ARMS", "ARMSET", "FULL_SEEDS", "DATE")}
    env.update(HJ12_GUARD_SELFTEST="1", GUARD_CASE="arms_select", DATE=DATE, **extra)
    return subprocess.run(
        ["timeout", "60", "bash", str(HJ12_LIVE)], cwd=str(REPO), env=env, text=True, capture_output=True
    )


def _rows(proc: subprocess.CompletedProcess[str]) -> list[list[str]]:
    return [line.split("|") for line in proc.stdout.splitlines() if line.count("|") == 2]


def test_review_arms_is_the_two_fixed_k_arms():
    assert read_bash_array(HJ12_LIVE, "REVIEW_ARMS") == [
        f"fixed_k|${{REPO}}/configs/{stem}.yaml|{stem}" for stem in REVIEW_ARMS
    ]


def test_arms_selects_the_review_stems():
    proc = _select(ARMS=" ".join(REVIEW_ARMS))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = _rows(proc)
    assert [row[2] for row in rows] == REVIEW_ARMS
    for system, cfg, stem in rows:
        assert system == "fixed_k"
        assert Path(cfg).name == f"{stem}.yaml" and (CONFIGS / Path(cfg).name).is_file()


@pytest.mark.parametrize("armset", ["live", "all"])
def test_no_armset_selects_a_review_stem(armset: str):
    proc = _select(ARMSET=armset)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    stems = [row[2] for row in _rows(proc)]
    assert stems and not set(stems) & set(REVIEW_ARMS)


def test_an_unknown_stem_is_still_refused():
    proc = _select(ARMS="dev_advise_not_an_arm")
    assert proc.returncode == 2 and "FATAL: unknown ARMS stem dev_advise_not_an_arm" in proc.stdout


@pytest.mark.parametrize("stem", REVIEW_ARMS)
def test_hosted_submit_lines_name_the_stem_and_date(stem: str):
    lines = _submit_lines(stem)
    assert len(lines) == 1
    assert lines[0].startswith(f'qsub -v ARMS="{stem}",DATE={DATE}')
    assert lines[0].endswith("/scripts/pbs/hj12_live.pbs")


def test_hj1b_takes_config_and_cid_unchanged_and_the_d3_line_uses_them():
    text = HJ1B.read_text(encoding="utf-8")
    assert 'CONFIG="${CONFIG:-' in text and 'CID="${CID:-' in text
    assert text.count('--config "${CONFIG}" --out "${OUT}" --campaign-id "${CID}"') == 2  # smoke, full
    assert text.count("--system planner_alone --split dev") == 2
    (line,) = _submit_lines("dev_planner_alone_cap81_high")
    assert "/configs/dev_planner_alone_cap81_high.yaml" in line
    assert f'CID="dev_planner_alone_cap81_high_{DATE}"' in line
    assert line.startswith("qsub -o ") and line.endswith("/scripts/pbs/hj1b_planner_alone.pbs")
