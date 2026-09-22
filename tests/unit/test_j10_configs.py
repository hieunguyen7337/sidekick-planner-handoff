"""configs/j10_*.yaml against Amendment A1 r2 (docs/prereg_j10_amendment_20260924.md §4, §4.1, §10).

Every J10 arm is a dev config carried to test with a few fields changed. The read is the dev
design on test only if nothing else moved, and only if every planner-involving arm replays the one
planner run, arm 3: r1 left arms 2, 8 and 9 live, which would have drawn a fresh plan per arm and
put plan-sampling noise back into the paired contrasts (F1). Both failures still produce believable
numbers, so both are pinned here rather than left to review.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
ARM3_STEM = "j10_planner_alone_cap81"
ARM3 = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
LUNA = "gpt-5.6-luna"
REPLAY = ("planner.packet_source", "planner.packet_source_pending")
PREFIX = ("handoff.source_campaign",) + REPLAY

# Stated here rather than read from the headers, so a header edit that widens what may differ
# fails a test instead of silently licensing the drift. stem -> (source, fields that differ).
REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    "j10_executor_alone": ("configs/hj8_executor_alone_bplus.yaml", ("campaign_id", "executor.lora_name")),
    "j10_executor_alone_bplus": ("configs/hj8_executor_alone_bplus.yaml", ("campaign_id",)),
    "j10_sft_plan": ("configs/hj8_sft_plan_bplus.yaml", ("campaign_id",) + REPLAY),
    "j10_planner_alone_cap81": ("configs/hj13_planner_alone_cap81.yaml", ("campaign_id",)),
    "j10_prefix_m9": ("configs/hj12_prefix_m9.yaml", ("campaign_id",) + PREFIX),
    "j10_prefix_m11": ("configs/hj12_prefix_m11.yaml", ("campaign_id",) + PREFIX),
    "j10_prefix_zs_m9": ("configs/hj13_prefix_zs_m9.yaml", ("campaign_id",) + PREFIX),
    "j10_prefix_zs_m11": ("configs/hj13_prefix_zs_m11.yaml", ("campaign_id",) + PREFIX),
    "j10_advise_k1_fullctx": ("configs/hj13_advise_fixed_k_1_fullctx.yaml", ("campaign_id",) + REPLAY),
    "j10_advise_k10_fullctx": ("configs/hj12_advise_fixed_k_10_fullctx.yaml", ("campaign_id",) + REPLAY),
    "j10_takeover_k10": ("configs/hj12_takeover_fixed_k_10.yaml", ("campaign_id",) + REPLAY),
    "j10_show_k10": ("configs/b2_show_fixed_k_10.yaml", ("campaign_id",) + REPLAY),
    "j10_advise_k10_neutral": ("configs/b2_advise_neutral_fixed_k_10_fullctx.yaml", ("campaign_id",) + REPLAY),
}
STEMS = sorted(REGISTRY)
# Arms 2 and 4-12 (A1 r2 §4.1): everything but the two floors and arm 3, which is the source.
PLANNER_INVOLVING = sorted(set(REGISTRY) - {"j10_executor_alone", "j10_executor_alone_bplus", ARM3_STEM})
PREFIX_ARMS = [s for s in STEMS if s.startswith("j10_prefix_")]
# A1 r2 §4 "Receiver" column: None is base granite; arm 3's executor is never constructed.
RECEIVER = {stem: "sft_b_plus" for stem in STEMS}
RECEIVER.update({"j10_executor_alone": None, "j10_prefix_zs_m9": None, "j10_prefix_zs_m11": None,
                 ARM3_STEM: "mock"})

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


def _declared(stem: str) -> tuple[str, list[str]]:
    """The header's Source and Differs lines. Only the leading comment block counts."""
    header = []
    for line in (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    sources = [m.group(1) for m in map(SOURCE_RE.match, header) if m]
    differs = [m.group(1) for m in map(DIFFERS_RE.match, header) if m]
    assert len(sources) == 1 and len(differs) == 1, f"{stem}: need one Source and one Differs line"
    return sources[0], [f.strip() for f in differs[0].split(",")]


def _keys(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def test_the_config_set_is_the_registered_arm_list():
    assert sorted(p.stem for p in CONFIGS.glob("j10_*.yaml")) == STEMS
    assert len(STEMS) == 13  # arms 1, 1b, 2-12


@pytest.mark.parametrize("stem", STEMS)
def test_header_declares_the_registered_source_and_fields(stem: str):
    source, fields = _declared(stem)
    assert len(fields) == len(set(fields)), fields
    assert (source, set(fields)) == (REGISTRY[stem][0], set(REGISTRY[stem][1]))


@pytest.mark.parametrize("stem", STEMS)
def test_a_differs_from_its_declared_source_only_in_the_declared_fields(stem: str):
    source, fields = _declared(stem)
    assert (REPO / source).is_file(), source
    # Equality, not subset: a declared field that no longer differs is a stale declaration.
    assert _diff(_load(REPO / source), _cfg(stem)) == set(fields)


def test_the_diff_sees_nested_changes_and_one_sided_keys():
    src = {"env": "appworld", "planner": {"model": LUNA, "stop": ["a"]}, "x": {}}
    assert _diff(src, src) == set()
    assert _diff(src, {"planner": {"model": "gpt-5.6-sol", "stop": ["a", "b"]}, "x": {}}) == {
        "env", "planner.model", "planner.stop"}
    assert _diff(src, dict(src, split="test_normal", x={"y": 1})) == {"split", "x", "x.y"}


@pytest.mark.parametrize("stem", PLANNER_INVOLVING)
def test_b_every_planner_involving_arm_replays_arm_3(stem: str):
    planner = _cfg(stem)["planner"]
    assert planner["type"] == "codex"
    assert planner["packet_source"] == ARM3
    assert planner["packet_system"] == "planner_alone"
    assert planner["on_missing"] == "fail"  # a missing packet aborts; it never buys a live plan
    assert str(planner.get("packet_source_pending") or "").strip()
    if stem in PREFIX_ARMS:
        handoff = _cfg(stem)["handoff"]
        assert (handoff["source_campaign"], handoff["source_system"]) == (ARM3, "planner_alone")


def test_b_arm_3_is_the_only_live_planner_and_the_path_is_its_campaign():
    assert ARM3.rsplit("/", 1)[1] == _cfg(ARM3_STEM)["campaign_id"]
    codex = {s for s in STEMS if (_cfg(s).get("planner") or {}).get("type") == "codex"}
    replaying = {s for s in STEMS if (_cfg(s).get("planner") or {}).get("packet_source")}
    assert codex - replaying == {ARM3_STEM}
    assert replaying == set(PLANNER_INVOLVING)


@pytest.mark.parametrize("stem", STEMS)
def test_c_no_split_key_anywhere(stem: str):
    # The split is a runner CLI argument; a config key is inert and would run dev (A1 §10.2).
    assert "split" not in set(_keys(_cfg(stem)))


def test_d_every_codex_planner_pins_luna():
    codex = [s for s in STEMS if (_cfg(s).get("planner") or {}).get("type") == "codex"]
    assert len(codex) == len(PLANNER_INVOLVING) + 1  # + arm 3
    assert {s: _cfg(s)["planner"].get("model") for s in codex} == {s: LUNA for s in codex}


def test_e_campaign_ids_are_unique_and_named_after_the_stem():
    ids = {stem: _cfg(stem)["campaign_id"] for stem in STEMS}
    assert len(set(ids.values())) == len(ids)
    assert ids == {stem: f"{stem}_20260924" for stem in STEMS}


@pytest.mark.parametrize("stem", STEMS)
def test_receiver_is_the_registered_one(stem: str):
    executor = _cfg(stem)["executor"]
    if RECEIVER[stem] == "mock":
        assert executor["type"] == "mock"
        return
    assert (executor["type"], executor["model"]) == ("vllm", "ibm-granite/granite-4.2-8b")
    assert executor["lora_name"] == RECEIVER[stem]


def test_every_arm_has_env_appworld():
    # r1's prefix_m9 / prefix_m11 had lost it (F9).
    assert {stem: _cfg(stem).get("env") for stem in STEMS} == {stem: "appworld" for stem in STEMS}


def test_j10_report_registers_every_arm_under_its_config():
    spec = importlib.util.spec_from_file_location(
        "j10_report_for_configs", REPO / "scripts" / "analysis" / "j10_report.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.A1_ARMS == {stem[len("j10_"):]: f"configs/{stem}.yaml" for stem in STEMS}
