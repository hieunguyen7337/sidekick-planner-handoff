"""configs/j12_*.yaml against the J12 prereg (docs/prereg_j12_depth_test_20260924.md §2).

J12 adds the two m = 6 prefix arms whose m = 11 partners are J10 arms 5 and 7. Each is its J10
m = 9 source with the campaign id and the prefix depth changed and nothing else, so the m6 -> m11
contrast on test differs only in depth. As in test_j10_configs, the list of changed keys is stated
here rather than read from the headers, so a header edit that widens what may differ fails a test
instead of licensing the drift.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
sys.path.insert(0, str(REPO / "scripts" / "setup"))
from verify_configs import validate_prompt_budget  # noqa: E402

ARM3 = "/scratch/n12194778/sidekick/results/j10_planner_alone_cap81_20260924"
PREREG = "docs/prereg_j12_depth_test_20260924.md"
# stem -> (source, fields that differ)
REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    "j12_prefix_m6": ("configs/j10_prefix_m9.yaml", ("campaign_id", "handoff.m")),
    "j12_prefix_zs_m6": ("configs/j10_prefix_zs_m9.yaml", ("campaign_id", "handoff.m")),
}
# The m = 11 partner of each arm (J10 arm 5 / 7), whose receiver must be the same.
PARTNER = {"j12_prefix_m6": "configs/j10_prefix_m11.yaml", "j12_prefix_zs_m6": "configs/j10_prefix_zs_m11.yaml"}
# J12 §2: M^bplus_6 serves sft_b_plus, M^zs_6 the base model (lora_name null).
RECEIVER = {"j12_prefix_m6": "sft_b_plus", "j12_prefix_zs_m6": None}
STEMS = sorted(REGISTRY)
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


def _header_text(stem: str) -> str:
    """The header as one line of prose, so a phrase may wrap across comment lines."""
    return " ".join(line.lstrip("#").strip() for line in _header(stem))


def _declared(stem: str) -> tuple[str, list[str]]:
    header = _header(stem)
    sources = [line[len("# Source: "):].split()[0] for line in header if line.startswith("# Source: ")]
    differs = [line[len("# Differs from source in: "):] for line in header
               if line.startswith("# Differs from source in: ")]
    assert len(sources) == 1 and len(differs) == 1, f"{stem}: need one Source and one Differs line"
    return sources[0], [f.strip() for f in differs[0].split(",")]


def test_the_config_set_is_the_two_registered_arms():
    assert sorted(p.stem for p in CONFIGS.glob("j12_*.yaml")) == STEMS


@pytest.mark.parametrize("stem", STEMS)
def test_header_declares_the_registered_source_and_fields(stem: str):
    source, fields = _declared(stem)
    assert len(fields) == len(set(fields)), fields
    assert (source, set(fields)) == (REGISTRY[stem][0], set(REGISTRY[stem][1]))


@pytest.mark.parametrize("stem", STEMS)
def test_differs_from_its_source_only_in_the_declared_fields(stem: str):
    source, fields = _declared(stem)
    assert (REPO / source).is_file(), source
    # Equality, not subset: a declared field that no longer differs is a stale declaration.
    assert _diff(_load(REPO / source), _cfg(stem)) == set(fields)


def test_the_diff_sees_nested_changes_and_one_sided_keys():
    src = {"handoff": {"m": 9, "source_campaign": ARM3}, "x": {}}
    assert _diff(src, src) == set()
    assert _diff(src, {"handoff": {"m": 6, "source_campaign": ARM3}, "x": {}}) == {"handoff.m"}
    assert _diff(src, dict(src, split="test_normal")) == {"split"}


@pytest.mark.parametrize("stem", STEMS)
def test_prefix_depth_is_6_and_the_id_is_the_stem(stem: str):
    cfg = _cfg(stem)
    assert cfg["handoff"]["m"] == 6
    assert _load(REPO / REGISTRY[stem][0])["handoff"]["m"] == 9
    assert cfg["campaign_id"] == f"{stem}_20260924"


@pytest.mark.parametrize("stem", STEMS)
def test_the_source_is_j10_arm_3_for_the_handoff_and_the_packets(stem: str):
    cfg = _cfg(stem)
    assert (cfg["handoff"]["source_campaign"], cfg["handoff"]["source_system"]) == (ARM3, "planner_alone")
    planner = cfg["planner"]
    assert (planner["type"], planner["model"]) == ("codex", "gpt-5.6-luna")
    assert (planner["packet_source"], planner["packet_system"]) == (ARM3, "planner_alone")
    # A prefix arm never plans: any packet miss aborts rather than calling the planner (J10 arms 4-7).
    assert planner["on_missing"] == "fail"
    assert str(planner.get("packet_source_pending") or "").strip()


@pytest.mark.parametrize("stem", STEMS)
def test_executor_adapter_and_receiver_equal_the_source_and_the_m11_partner(stem: str):
    cfg = _cfg(stem)
    source = _load(REPO / REGISTRY[stem][0])
    partner = _load(REPO / PARTNER[stem])
    assert cfg["executor"] == source["executor"] == partner["executor"]
    assert (cfg["executor"]["type"], cfg["executor"]["model"]) == ("vllm", "ibm-granite/granite-4.2-8b")
    assert cfg["executor"]["lora_name"] == RECEIVER[stem]
    assert cfg["limits"] == source["limits"] == partner["limits"]
    # Everything but the depth and the id matches the m = 11 partner too.
    assert _diff(partner, cfg) == {"campaign_id", "handoff.m"}


@pytest.mark.parametrize("stem", STEMS)
def test_no_split_key_env_appworld_and_the_prompt_budget_check_passes(stem: str):
    cfg = _cfg(stem)
    # The split is a runner argument (--split, default "dev"); a split: key would be ignored.
    assert "split" not in cfg
    assert cfg["env"] == "appworld"
    assert validate_prompt_budget(cfg, f"configs/{stem}.yaml") == []


@pytest.mark.parametrize("stem", STEMS)
def test_header_carries_the_warning_the_prereg_and_the_hosted_call_wording(stem: str):
    text = _header_text(stem)
    assert "⚠ This config deliberately carries NO `split:` key." in text
    assert PREREG in text
    assert "scripts/pbs/j12_arm.pbs" in text
    # A prefix arm's executor ask is answered live (A1 Amendment 1 §I): never "zero hosted calls".
    assert "zero planned hosted calls; live executor asks as A1 Amendment 1 §I" in text
    body = (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8")
    assert "zero MARGINAL hosted calls" not in body
