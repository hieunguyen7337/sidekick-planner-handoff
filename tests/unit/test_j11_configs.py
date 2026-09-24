"""configs/j11_*.yaml against docs/prereg_j11_lp2_test_20260924.md §2.

Every J11 arm is an LP-2 dev config (configs/lp2_*.yaml) carried to test with a few fields changed.
The read replicates LP-2 only if nothing else moved: the same served planner in every arm, and every
replay arm replaying J11's own ceiling C rather than the dev ceiling or another planner run. Both
failures still produce believable numbers, so both are pinned here rather than left to review.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
C_STEM = "j11_planner_alone_cap81_qwen38_27b"
C_PATH = "/scratch/n12194778/sidekick/results/j11_planner_alone_cap81_qwen38_27b_20260924"
P27 = "Qwen/Qwen3.8-27B-FP8"
REPLAY = ("planner.packet_source", "planner.packet_source_pending")
# T, A and A1 lose the dev key (LP Amendment 4) and plan live only for a planless C key.
PLAN_REPLAY = REPLAY + ("planner.live_plan_keys", "planner.on_missing")
PREFIX = ("handoff.source_campaign",) + REPLAY

# Stated here rather than read from the headers, so a header edit that widens what may differ
# fails a test instead of silently licensing the drift. stem -> (source, fields that differ).
REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    C_STEM: ("configs/lp2_planner_alone_cap81_qwen38_27b.yaml", ("campaign_id",)),
    "j11_takeover_fixed_k_10": ("configs/lp2_hj12_takeover_fixed_k_10.yaml", ("campaign_id",) + PLAN_REPLAY),
    "j11_advise_fixed_k_10_fullctx": ("configs/lp2_hj12_advise_fixed_k_10_fullctx.yaml",
                                      ("campaign_id",) + PLAN_REPLAY),
    "j11_advise_fixed_k_1_fullctx": ("configs/lp2_hj13_advise_fixed_k_1_fullctx.yaml",
                                     ("campaign_id",) + PLAN_REPLAY),
    "j11_prefix_bplus_m6": ("configs/lp2_prefix_bplus_m6.yaml", ("campaign_id",) + PREFIX),
    "j11_prefix_bplus_m11": ("configs/lp2_prefix_bplus_m11.yaml", ("campaign_id",) + PREFIX),
    "j11_prefix_zs_m6": ("configs/lp2_prefix_zs_m6.yaml", ("campaign_id",) + PREFIX),
    "j11_prefix_zs_m11": ("configs/lp2_prefix_zs_m11.yaml", ("campaign_id",) + PREFIX),
}
STEMS = sorted(REGISTRY)
REPLAY_ARMS = sorted(set(REGISTRY) - {C_STEM})
PREFIX_ARMS = [s for s in STEMS if s.startswith("j11_prefix_")]
PLAN_ARMS = sorted(set(REPLAY_ARMS) - set(PREFIX_ARMS))
# prereg §2: C never constructs an executor; zs is base granite; every other receiver is sft_b_plus.
RECEIVER = {stem: "sft_b_plus" for stem in STEMS}
RECEIVER.update({C_STEM: "mock", "j11_prefix_zs_m6": None, "j11_prefix_zs_m11": None})

SOURCE_RE = re.compile(r"^# Source: (configs/\S+\.yaml)(?:\s|$)")
DIFFERS_RE = re.compile(r"^# Differs from source in: (.+)$")
NO_SPLIT_WARNING = "# ⚠ This config deliberately carries NO `split:` key."
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
    header = []
    for line in (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    return header


def _declared(stem: str) -> tuple[str, list[str]]:
    """The header's Source and Differs lines. Only the leading comment block counts."""
    header = _header(stem)
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
    assert sorted(p.stem for p in CONFIGS.glob("j11_*.yaml")) == STEMS
    assert len(STEMS) == 8  # C, T, A, A1, M^bplus_{6,11}, M^zs_{6,11}; E is J10's arm 1b


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
    src = {"env": "appworld", "planner": {"model": P27, "live_plan_keys": ["2/x_1"]}, "x": {}}
    assert _diff(src, src) == set()
    assert _diff(src, {"planner": {"model": P27}, "x": {}}) == {"env", "planner.live_plan_keys"}
    assert _diff(src, dict(src, split="test_normal", x={"y": 1})) == {"split", "x", "x.y"}


@pytest.mark.parametrize("stem", STEMS)
def test_b_the_planner_is_the_served_p27_everywhere(stem: str):
    planner = _cfg(stem)["planner"]
    assert (planner["type"], planner["model"]) == ("vllm", P27)
    assert planner["chat_template_kwargs"] == {"enable_thinking": False}
    assert (planner["temperature"], planner["max_tokens"]) == (0.7, 2048)


@pytest.mark.parametrize("stem", REPLAY_ARMS)
def test_c_every_replay_arm_replays_c(stem: str):
    planner = _cfg(stem)["planner"]
    assert planner["packet_source"] == C_PATH
    assert planner["packet_system"] == "planner_alone"
    assert str(planner.get("packet_source_pending") or "").strip()
    # A prefix arm never plans, so any miss aborts; T / A / A1 plan live only for a C episode scored
    # without a plan (J10 A1 §4.2's mechanism) -- an absent or crashed source still aborts.
    assert planner["on_missing"] == ("fail" if stem in PREFIX_ARMS else "call_if_planless")
    # The dev key of LP Amendment 4 names a dev episode; it has no meaning on test.
    assert "live_plan_keys" not in planner
    if stem in PREFIX_ARMS:
        handoff = _cfg(stem)["handoff"]
        assert (handoff["source_campaign"], handoff["source_system"]) == (C_PATH, "planner_alone")
        assert handoff["m"] == int(stem.rsplit("_m", 1)[1])


def test_c_is_the_only_arm_without_a_source_and_the_path_is_its_campaign():
    assert C_PATH.rsplit("/", 1)[1] == _cfg(C_STEM)["campaign_id"]
    replaying = {s for s in STEMS if _cfg(s)["planner"].get("packet_source")}
    assert replaying == set(REPLAY_ARMS)
    assert "handoff" not in _cfg(C_STEM) and "fixed_k" not in _cfg(C_STEM)
    assert {s: _cfg(s).get("fixed_k") for s in PLAN_ARMS} == {
        "j11_takeover_fixed_k_10": 10, "j11_advise_fixed_k_10_fullctx": 10, "j11_advise_fixed_k_1_fullctx": 1}
    assert _cfg("j11_takeover_fixed_k_10").get("takeover") is True
    assert {s: _cfg(s).get("correct_context") for s in PLAN_ARMS} == {
        "j11_takeover_fixed_k_10": None, "j11_advise_fixed_k_10_fullctx": "full",
        "j11_advise_fixed_k_1_fullctx": "full"}


@pytest.mark.parametrize("stem", STEMS)
def test_d_no_split_key_anywhere_and_the_header_says_why(stem: str):
    # The split is a runner CLI argument; a config key is inert and would run dev (A1 §10.2).
    assert "split" not in set(_keys(_cfg(stem)))
    header = "\n".join(_header(stem))
    assert NO_SPLIT_WARNING in header and "scripts/pbs/j11_arm.pbs" in header


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
    assert {stem: _cfg(stem).get("env") for stem in STEMS} == {stem: "appworld" for stem in STEMS}
