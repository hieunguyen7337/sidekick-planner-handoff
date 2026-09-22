"""LP arm configs: rendered from their hosted sources, differing only where declared, each driving
the locally served planner of its LP ceiling -- plus the refusals in scripts/pbs/lp_live.pbs.

The LP arms test whether the channel result holds across planner strength. They answer that only
if each is its source with the planner swapped and nothing else moved, and only if the planner it
builds is the one the ceiling ran. Both failure modes still produce believable numbers, so both
are pinned here rather than left to review.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from _pbs_arrays import read_bash_array
from sidekick.agents.planner import CachedPacketPlanner
from sidekick.agents.vllm_planner import VllmPlanner
from sidekick.runner import load_config, make_executor, make_planner

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "lp_live.pbs"
RESULTS = "/scratch/n12194778/sidekick/results"

# Stated here rather than read from the ceiling configs, so a ceiling edit that changes the
# planner shows up as a failing test instead of silently re-pointing twenty arms.
EXPECTED_MODEL = {"lp1": "Qwen/Qwen3-8B", "lp2": "Qwen/Qwen3.8-27B-FP8"}
LIVE_SOURCE_STEMS = (
    "hj12_takeover_fixed_k_10",
    "hj12_advise_fixed_k_10_fullctx",
    "hj13_advise_fixed_k_1_fullctx",
    "hj8_sft_plan_bplus",
)


def _module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass resolves string annotations through sys.modules[cls.__module__].
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


mk = _module("make_lp_configs", "scripts/setup/make_lp_configs.py")
verify_configs = _module("verify_configs", "scripts/setup/verify_configs.py")

SPECS = mk.all_specs()
LIVE = [s for s in SPECS if s.kind == "live"]
PREFIX = [s for s in SPECS if s.kind == "prefix"]


def _cfg(spec) -> dict:
    return load_config(str(REPO / spec.out))


def test_the_set_is_twenty_configs_named_after_their_sources() -> None:
    assert {s.out for s in LIVE} == {
        f"configs/lp{n}_{src}.yaml" for n in (1, 2) for src in LIVE_SOURCE_STEMS
    }
    assert {(s.out, s.source) for s in PREFIX} == {
        (f"configs/lp{n}_prefix_{rx}_m{m}.yaml", f"configs/hj17_prefix_c81_{rx}_m{m}.yaml")
        for n in (1, 2)
        for rx in ("zs", "bplus")
        for m in (6, 9, 11)
    }


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_committed_config_is_the_generators_output_and_differs_only_where_declared(spec) -> None:
    assert mk.check(spec) == []


def test_the_diff_check_catches_an_undeclared_change_and_a_change_that_did_not_happen() -> None:
    spec = LIVE[0]
    src = mk.load(spec.source)
    drifted = yaml.safe_load(mk.render(spec))
    drifted["executor"]["temperature"] = 0.0
    assert "executor.temperature" in mk.changed_paths(src, drifted) - spec.declared

    stale = yaml.safe_load(mk.render(spec))
    stale["planner"]["packet_source"] = src["planner"]["packet_source"]
    assert "planner.packet_source" in spec.declared - mk.changed_paths(src, stale)


def test_the_diff_check_is_type_aware() -> None:
    # YAML 1 and true are == in Python; a knob flipping between them must still count.
    assert mk.changed_paths({"a": 1}, {"a": True}) == {"a"}


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_every_lp_config_builds_its_ceilings_local_planner(spec, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_PLANNER_BASE_URL", raising=False)
    cfg = _cfg(spec)
    ceiling = load_config(str(REPO / mk.CEILINGS[spec.lp]))["planner"]
    assert cfg["planner"]["type"] == "vllm"
    assert cfg["planner"]["model"] == ceiling["model"] == EXPECTED_MODEL[spec.lp]
    for codex_only in mk.CODEX_ONLY_KEYS:
        assert codex_only not in cfg["planner"]
    # The real replay source may not exist yet (the LP ceilings are still running), so build
    # against a stand-in archive with the same producer subtree.
    (tmp_path / cfg["planner"]["packet_system"]).mkdir()
    cfg["planner"]["packet_source"] = str(tmp_path)
    planner = make_planner(cfg, seed=1)
    assert isinstance(planner, CachedPacketPlanner)
    assert planner.on_missing == "fail"
    inner = planner.inner
    assert isinstance(inner, VllmPlanner)
    assert inner.model == EXPECTED_MODEL[spec.lp]
    assert inner.base_url == ceiling["base_url"].rstrip("/")
    assert (inner.temperature, inner.max_tokens, inner.timeout_s) == (
        ceiling["temperature"],
        ceiling["max_tokens"],
        ceiling["timeout_s"],
    )
    assert inner.chat_template_kwargs == {"enable_thinking": False}


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_replay_sources_name_the_matching_lp_ceiling(spec) -> None:
    cfg = _cfg(spec)
    ceiling_cid = load_config(str(REPO / mk.CEILINGS[spec.lp]))["campaign_id"]
    # An lp1 arm replaying the lp2 ceiling would compare one planner's reviews with another's plans.
    assert ceiling_cid.startswith(f"{spec.lp}_planner_alone_")
    want = f"{RESULTS}/{ceiling_cid}"
    assert cfg["planner"]["packet_source"] == want
    if spec.kind == "prefix":
        assert cfg["handoff"]["source_campaign"] == want
    assert cfg["campaign_id"] == f"{spec.stem}_{mk.DATE}"
    # verify_configs.py gates every PBS job on all configs: while the ceiling is absent the arm
    # must carry a pending reason, or every job on the box would refuse to start.
    assert verify_configs.pending_packet_source(cfg["planner"]) is not None or Path(want).exists()


@pytest.mark.parametrize("spec", LIVE, ids=[s.stem for s in LIVE])
def test_live_arms_keep_their_sources_channel_and_receiver(spec) -> None:
    cfg, src = _cfg(spec), mk.load(spec.source)
    assert cfg["executor"] == src["executor"]
    assert make_executor(cfg).lora_name == "sft_b_plus"
    for knob in ("takeover", "correct_context", "fixed_k", "limits", "prices"):
        assert cfg.get(knob) == src.get(knob), knob


@pytest.mark.parametrize("spec", PREFIX, ids=[s.stem for s in PREFIX])
def test_prefix_arms_keep_their_sources_receiver_and_depth(spec) -> None:
    cfg, src = _cfg(spec), mk.load(spec.source)
    assert cfg["executor"] == src["executor"]
    m = int(re.search(r"_m(\d+)$", spec.stem).group(1))
    assert cfg["handoff"]["m"] == src["handoff"]["m"] == m
    want_lora = None if "_zs_" in spec.stem else "sft_b_plus"
    assert cfg["executor"]["lora_name"] == want_lora
    assert make_executor(cfg).lora_name == want_lora


@pytest.mark.parametrize("spec", PREFIX, ids=[s.stem for s in PREFIX])
def test_prefix_arms_are_registered_once_in_the_hj12_free_set(spec) -> None:
    # The cid stem must be the config's own stem: campaign_id is <stem>_<date> on both sides.
    want = f"prefix_handoff|${{REPO}}/{spec.out}|{spec.stem}"
    assert read_bash_array(REPO / "scripts" / "pbs" / "hj12_prefix.pbs", "FREE_ARMS").count(want) == 1
    assert Path(spec.out).stem == spec.stem


# ---- scripts/pbs/lp_live.pbs ---------------------------------------------------------------


def _pbs(**env_extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PY": sys.executable, "ARMSET": "", "ARMS": "", **env_extra}
    return subprocess.run(["bash", str(PBS)], env=env, capture_output=True, text=True, timeout=180)


def test_lp_live_pbs_parses() -> None:
    subprocess.run(["bash", "-n", str(PBS)], check=True)


@pytest.mark.parametrize("lp", ["lp1", "lp2"])
def test_armset_selects_exactly_that_lps_live_configs(lp) -> None:
    r = _pbs(LP_SELFTEST="select", ARMSET=lp)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [row.split("|") for row in r.stdout.split()]
    assert {stem for _sys, _cfg, stem in rows} == {s.stem for s in LIVE if s.lp == lp}
    for system, cfg, stem in rows:
        assert Path(cfg).name == f"{stem}.yaml" and (REPO / "configs" / Path(cfg).name).is_file()
        assert system == ("sft_plan" if "sft_plan" in stem else "fixed_k")


def test_no_armset_is_refused_rather_than_defaulted() -> None:
    r = _pbs(LP_SELFTEST="select")
    assert r.returncode == 2 and "FATAL" in r.stdout


def test_an_unknown_stem_is_refused() -> None:
    r = _pbs(LP_SELFTEST="select", ARMS="lp1_not_an_arm")
    assert r.returncode == 2 and "FATAL" in r.stdout


def _guard(*rels: str) -> subprocess.CompletedProcess:
    return _pbs(LP_SELFTEST="guard", LP_GUARD_CONFIGS=" ".join(str(REPO / rel) for rel in rels))


@pytest.mark.parametrize("lp", ["lp1", "lp2"])
def test_guard_accepts_the_live_configs_and_names_the_planner_to_serve(lp) -> None:
    r = _guard(*[s.out for s in LIVE if s.lp == lp])
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert f"PLANNER_MODEL|{EXPECTED_MODEL[lp]}" in lines
    assert sum(line.startswith("ARM|") for line in lines) == 4


def test_guard_refuses_a_hosted_codex_arm() -> None:
    r = _guard("configs/lp1_hj12_takeover_fixed_k_10.yaml", "configs/hj12_takeover_fixed_k_10.yaml")
    assert r.returncode != 0
    assert "need 'vllm'" in r.stdout
    assert not any(line.startswith("PLANNER_MODEL|") for line in r.stdout.splitlines())


def test_guard_refuses_two_planners_in_one_job() -> None:
    r = _guard("configs/lp1_hj12_takeover_fixed_k_10.yaml", "configs/lp2_hj12_takeover_fixed_k_10.yaml")
    assert r.returncode != 0 and "one job serves one planner" in r.stdout


def test_guard_refuses_a_receiver_the_job_does_not_serve() -> None:
    # A zero-shot prefix config asks for the base model; lp_live registers only sft_b_plus.
    r = _guard("configs/lp1_prefix_zs_m9.yaml")
    assert r.returncode != 0 and "silently hits the BASE model" in r.stdout
