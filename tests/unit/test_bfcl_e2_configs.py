"""configs/bfcl_*.yaml: the Wave E dev design (docs/prereg_bfcl_dev_20260924.md §4) and its budget (§5).

Every BFCL arm is a J10 config carried to BFCL with a few fields changed, as every J10 arm is a dev config
carried to test. The dev read mirrors J10's contrasts only if nothing else moved, and only if every replay arm
replays the one planner run, planner_alone_cap81. Both failures still produce believable numbers, so both are
pinned here, in the style of tests/unit/test_j10_configs.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
PREREG = REPO / "docs" / "prereg_bfcl_dev_20260924.md"
SOURCE_STEM = "bfcl_planner_alone_cap81"
SOURCE = "/scratch/n12194778/sidekick/results/bfcl_planner_alone_cap81_dev_20260924"
LUNA = "gpt-5.6-luna"
BPLUS_ADAPTER = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b"
REPLAY = ("planner.packet_source", "planner.packet_source_pending")
PLAN_REPLAY = ("env", "campaign_id") + REPLAY + ("executor.lora_name",)
CHANNEL = PLAN_REPLAY + ("fixed_k",)
PREFIX = ("env", "campaign_id", "handoff.source_campaign", "handoff.m") + REPLAY
# The third receiver, qzs = zero-shot Qwen3-8B: each stem is its zs sibling with only the receiver's model changed.
QZS = ("campaign_id", "executor.model")
QWEN = "Qwen/Qwen3-8B"
# stem -> zs sibling.
QZS_SIBLING = {
    "bfcl_executor_alone_qzs": "bfcl_executor_alone_zs",
    "bfcl_plan_qzs": "bfcl_plan_zs",
    "bfcl_takeover_k5_qzs": "bfcl_takeover_k5",
    "bfcl_advise_k5_fullctx_qzs": "bfcl_advise_k5_fullctx",
    "bfcl_advise_k5_neutral_qzs": "bfcl_advise_k5_neutral",
    **{f"bfcl_prefix_qzs_m{m}": f"bfcl_prefix_zs_m{m}" for m in (2, 4, 6)},
}
# AppWorld's zero-shot Qwen3-8B configs (hj15_*_zsq); the qzs executor block is copied from them.
ZSQ = ["hj15_executor_alone_zsq", "hj15_prompt_only_zsq", "hj15_prefix_zsq_m6", "hj15_prefix_zsq_m9",
       "hj15_prefix_zsq_m11"]

# Stated here rather than read from the headers, so a header edit that widens what may differ fails a
# test instead of silently licensing the drift. stem -> (J10 template, fields that differ).
REGISTRY: dict[str, tuple[str, tuple[str, ...]]] = {
    "bfcl_executor_alone_bplus": ("configs/j10_executor_alone_bplus.yaml", ("env", "campaign_id")),
    "bfcl_planner_alone_cap81": ("configs/j10_planner_alone_cap81.yaml", ("env", "campaign_id")),
    "bfcl_plan_zs": ("configs/j10_sft_plan.yaml", PLAN_REPLAY),
    "bfcl_takeover_k5": ("configs/j10_takeover_k10.yaml", CHANNEL),
    "bfcl_advise_k5_fullctx": ("configs/j10_advise_k10_fullctx.yaml", CHANNEL),
    "bfcl_advise_k5_neutral": ("configs/j10_advise_k10_neutral.yaml", CHANNEL),
    **{f"bfcl_prefix_zs_m{m}": ("configs/j10_prefix_zs_m9.yaml", PREFIX) for m in (2, 4, 6)},
    **{f"bfcl_prefix_bplus_m{m}": ("configs/j10_prefix_m9.yaml", PREFIX) for m in (2, 4, 6)},
    # qzs: the template is the zs sibling itself, not J10.
    **{qzs: (f"configs/{zs}.yaml", QZS) for qzs, zs in QZS_SIBLING.items()},
}
STEMS = sorted(REGISTRY)
PREFIX_ARMS = [s for s in STEMS if s.startswith("bfcl_prefix_")]
CHANNEL_ARMS = ["bfcl_advise_k5_fullctx", "bfcl_advise_k5_neutral", "bfcl_takeover_k5",
                "bfcl_advise_k5_fullctx_qzs", "bfcl_advise_k5_neutral_qzs", "bfcl_takeover_k5_qzs"]
REPLAY_ARMS = sorted(PREFIX_ARMS + CHANNEL_ARMS + ["bfcl_plan_zs", "bfcl_plan_qzs"])
# The brief's receiver column: None is zero-shot granite; the planner_alone executor is never built.
RECEIVER = {s: None for s in STEMS}
RECEIVER.update({s: "sft_b_plus" for s in STEMS if "bplus" in s})
RECEIVER.update({s: "qzs" for s in QZS_SIBLING})
RECEIVER[SOURCE_STEM] = "mock"

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


def test_the_config_set_is_the_dev_design_plus_spike_b():
    # 12 arms of the unit brief's table A, the 8 qzs arms of unit S2, plus the spike (b) arm bfcl_executor_alone_zs.
    assert len(STEMS) == 12 + 8 and len(QZS_SIBLING) == 8
    assert sorted(p.stem for p in CONFIGS.glob("bfcl_*.yaml")) == sorted(STEMS + ["bfcl_executor_alone_zs"])


@pytest.mark.parametrize("stem", STEMS)
def test_header_declares_the_registered_template_and_fields(stem: str):
    source, fields = _declared(stem)
    assert len(fields) == len(set(fields)), fields
    assert (source, set(fields)) == (REGISTRY[stem][0], set(REGISTRY[stem][1]))


@pytest.mark.parametrize("stem", STEMS)
def test_differs_from_its_template_only_in_the_declared_fields(stem: str):
    source, fields = _declared(stem)
    # Equality, not subset: a declared field that no longer differs is a stale declaration.
    assert _diff(_load(REPO / source), _cfg(stem)) == set(fields)


def test_the_diff_sees_nested_changes_and_one_sided_keys():
    src = {"env": "appworld", "handoff": {"m": 9, "source_campaign": "a"}, "x": {}}
    assert _diff(src, src) == set()
    assert _diff(src, {"env": "bfcl", "handoff": {"m": 2, "source_campaign": "a"}, "x": {}}) == {"env", "handoff.m"}
    assert _diff(src, dict(src, fixed_k=5, x={"y": 1})) == {"fixed_k", "x", "x.y"}


@pytest.mark.parametrize("stem", STEMS)
def test_env_split_and_campaign_id(stem: str):
    cfg = _cfg(stem)
    assert cfg["env"] == "bfcl" and "split" not in cfg
    assert cfg["campaign_id"] == f"{stem}_dev_20260924" and "_dev_" in cfg["campaign_id"]


def test_campaign_ids_are_unique_and_the_source_path_is_the_planner_alone_campaign():
    ids = [_cfg(s)["campaign_id"] for s in STEMS] + [_cfg("bfcl_executor_alone_zs")["campaign_id"]]
    assert len(ids) == len(set(ids)) == 21
    assert SOURCE.rsplit("/", 1)[1] == _cfg(SOURCE_STEM)["campaign_id"]


@pytest.mark.parametrize("stem", STEMS)
def test_receiver(stem: str):
    executor = _cfg(stem)["executor"]
    if RECEIVER[stem] == "mock":
        assert executor["type"] == "mock"
        return
    # zs: spike (b)'s executor block verbatim; bplus: the same block under the sft_b_plus alias; qzs: the
    # same block with Qwen3-8B as the model.
    zs = _cfg("bfcl_executor_alone_zs")["executor"]
    if RECEIVER[stem] == "qzs":
        assert executor == dict(zs, model=QWEN)
    else:
        assert executor == dict(zs, lora_name=RECEIVER[stem])


@pytest.mark.parametrize("stem", sorted(QZS_SIBLING))
def test_qzs_executor_is_appworlds_zero_shot_qwen_block(stem: str):
    # Copied from AppWorld's zero-shot Qwen3-8B configs: model id, sampling, stop, thinking off, prompt budget.
    blocks = [_cfg(z)["executor"] for z in ZSQ]
    assert all(b == blocks[0] for b in blocks), "the hj15 zsq executor blocks disagree"
    executor = _cfg(stem)["executor"]
    assert executor == blocks[0]
    assert (executor["model"], executor["lora_name"], executor["temperature"]) == (QWEN, None, 0.7)
    assert executor["chat_template_kwargs"] == {"enable_thinking": False}
    # Everything but the receiver's model is the zs sibling's, so a qzs - zs contrast is the receiver alone.
    assert _diff(_cfg(QZS_SIBLING[stem]), _cfg(stem)) == {"campaign_id", "executor.model"}


def test_bplus_comments_name_the_j10_adapter():
    for stem in STEMS:
        if RECEIVER[stem] == "sft_b_plus":
            assert f"sft_b_plus={BPLUS_ADAPTER}" in (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8"), stem


@pytest.mark.parametrize("stem", STEMS)
def test_fixed_k_takeover_and_advice_prompt(stem: str):
    cfg = _cfg(stem)
    if stem in CHANNEL_ARMS:
        assert cfg["fixed_k"] == 5 and cfg["executor"]["lora_name"] is None
    else:
        assert "fixed_k" not in cfg
    assert cfg.get("takeover") is (True if stem in ("bfcl_takeover_k5", "bfcl_takeover_k5_qzs") else None)
    assert "advice_from_act" not in cfg
    prompt = (cfg.get("planner") or {}).get("correct_prompt")
    assert prompt == ("neutral" if stem in ("bfcl_advise_k5_neutral", "bfcl_advise_k5_neutral_qzs") else None)
    assert cfg.get("correct_context") == ("full" if stem.startswith("bfcl_advise_") else None)


def test_the_depth_grid_is_exactly_2_4_6_on_every_receiver():
    grid = {}
    for stem in PREFIX_ARMS:
        grid.setdefault(RECEIVER[stem], set()).add(_cfg(stem)["handoff"]["m"])
    assert grid == {None: {2, 4, 6}, "sft_b_plus": {2, 4, 6}, "qzs": {2, 4, 6}}
    for stem in PREFIX_ARMS:
        assert stem.endswith(f"_m{_cfg(stem)['handoff']['m']}")


@pytest.mark.parametrize("stem", REPLAY_ARMS)
def test_every_replay_arm_replays_the_planner_alone_campaign(stem: str):
    planner = _cfg(stem)["planner"]
    assert (planner["type"], planner["model"]) == ("codex", LUNA)
    assert (planner["packet_source"], planner["packet_system"]) == (SOURCE, "planner_alone")
    assert str(planner.get("packet_source_pending") or "").strip()
    # A prefix arm never plans live, so any miss aborts; a plan-replay arm plans live only for a
    # scored source episode with no plan (J10 A1 §4.2).
    assert planner["on_missing"] == ("fail" if stem in PREFIX_ARMS else "call_if_planless")
    if stem in PREFIX_ARMS:
        handoff = _cfg(stem)["handoff"]
        assert (handoff["source_campaign"], handoff["source_system"]) == (SOURCE, "planner_alone")


def test_planner_alone_is_the_only_live_planner_and_pins_luna_at_medium():
    codex = {s for s in STEMS if (_cfg(s).get("planner") or {}).get("type") == "codex"}
    replaying = {s for s in STEMS if (_cfg(s).get("planner") or {}).get("packet_source")}
    assert codex - replaying == {SOURCE_STEM}
    assert replaying == set(REPLAY_ARMS)
    for stem in codex:
        planner = _cfg(stem)["planner"]
        assert (planner["model"], planner["reasoning_effort"]) == (LUNA, "medium")
    assert _cfg(SOURCE_STEM)["limits"]["max_planner_calls"] == 81
    assert (_cfg("bfcl_executor_alone_bplus")["planner"]) == {"type": "mock"}


# ---- the budget in the draft prereg (§5) -----------------------------------------------------------

def _budget_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    in_table = False
    for line in PREREG.read_text(encoding="utf-8").splitlines():
        if line.startswith("| item | hosted calls / episode | episodes | hosted calls |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            cells = [c.strip().strip("*") for c in line.strip("|").split("|")]
            if set(cells[0]) <= {"-"}:
                continue
            rows[cells[0]] = cells[1:]
    return rows


def _n(cell: str) -> int:
    return int(cell.replace(",", "").strip("*"))


def test_prereg_is_frozen_with_one_status_line():
    # Frozen 2026-09-25 as revised (§8); later amendments append below §8 and add no Status line.
    status = [l for l in PREREG.read_text(encoding="utf-8").splitlines() if l.startswith("**Status**")]
    assert len(status) == 1 and status[0].startswith("**Status**: FROZEN 2026-09-25")


def test_prereg_budget_arithmetic():
    rows = _budget_rows()
    arms = {k: v for k, v in rows.items() if v[0]}
    # Hand check (revision of 2026-09-25, 150 episodes per arm): 12x150 + 2 x (1x150) + 6 x (3x150) + 0
    # = 1,800 + 300 + 2,700 = 4,800; dry run 150; 10 % of 4,950 = 495; 5,445.
    for item, (cpe, n, calls) in arms.items():
        assert _n(cpe) * _n(n) == _n(calls), item
    subtotal = sum(_n(v[2]) for v in arms.values())
    assert subtotal == _n(rows["subtotal, arms"][2]) == 4800
    dry = _n(rows["dry run"][2])
    assert dry == 150
    assert _n(rows["retries, 10 % of 4,950"][2]) == (subtotal + dry) // 10 == 495
    assert _n(rows["total"][2]) == subtotal + dry + 495 == 5445
    # Every hosted arm of the design, on zs and on qzs, is costed at 150 episodes. The free arms are 9 prefix
    # arms x 150, executor_alone_bplus and _qzs x 150, and seed 3 of executor_alone_zs (spike b holds 1 and 2).
    hosted = {"planner_alone_cap81", "plan_zs", "takeover_k5", "advise_k5_fullctx", "advise_k5_neutral",
              "plan_qzs", "takeover_k5_qzs", "advise_k5_fullctx_qzs", "advise_k5_neutral_qzs"}
    assert hosted <= set(arms)
    assert all(_n(arms[a][1]) == 150 for a in hosted)
    free = arms["prefix arms (9) and executor_alone (zs seed 3, bplus, qzs)"]
    assert (_n(free[0]), _n(free[1])) == (0, 9 * 150 + 2 * 150 + 50)


def test_prereg_spike_numbers_are_the_report_keys():
    text = PREREG.read_text(encoding="utf-8")
    a = json.loads((REPO / "campaign/results/bfcl_spike_a_20260924.report.json").read_text(encoding="utf-8"))
    c = json.loads((REPO / "campaign/results/bfcl_spike_c_20260924.report.json").read_text(encoding="utf-8"))
    assert a["gate"]["pass"] is True and c["gate"]["pass"] is True
    assert (a["counts"]["adapter_success"], a["n_entries"]) == (200, 200)
    assert a["n_prefix_replays_hash_ok"] == a["n_prefix_replays"] == 4152 and "4,152 of" in text
    assert a["noop_goal_pass_rate_mean"] == 0.0
    assert (c["gate"]["deepest_m"], c["gate"]["share"]) == (7, 0.7) and c["proposed_grid"] == [2, 5, 7]
    assert c["doc_example_grid_steps"] == {"2": 1.0, "4": 0.96, "6": 0.84} and "1.00, 0.96 and 0.84" in text
    assert c["share_handing_off_by_m_batched"]["6"] == 0.5 and c["turn_stats"]["max"] == 6
