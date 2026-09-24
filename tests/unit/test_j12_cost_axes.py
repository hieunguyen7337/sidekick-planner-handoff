"""Unit tests for cost axes analysis (Brief X40 Unit A)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]

_SPEC = importlib.util.spec_from_file_location(
    "j12_cost_axes", REPO / "scripts" / "analysis" / "j12_cost_axes.py"
)
j12 = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(j12)


def test_cached_input_is_billed_at_the_cached_rate() -> None:
    """A scripted usage record with a known cached/fresh split prices to a hand-computed dollar figure."""
    models_prices = {
        "gpt-5.6-luna": {
            "input": 0.20,
            "cached_input": 0.02,
            "output": 1.20,
        }
    }
    diagnostics = {"n_usage_without_cache_split": 0}

    # 1M input total with 800k cached -> 200k fresh input, 800k cached input, 100k total output
    usage = {
        "model": "gpt-5.6-luna",
        "input_tokens": 1_000_000,
        "cached_input_tokens": 800_000,
        "output_tokens": 50_000,
        "reasoning_output_tokens": 50_000,
    }
    cost = j12.price_usage_record(usage, models_prices, diagnostics)

    # Hand calculation:
    # uncached input: 200,000 * ($0.20 / 1M) = $0.040000
    # cached input:   800,000 * ($0.02 / 1M) = $0.016000
    # output:         100,000 * ($1.20 / 1M) = $0.120000
    # expected total = $0.176000
    assert abs(cost - 0.176000) < 1e-9
    assert diagnostics["n_usage_without_cache_split"] == 0


def test_usage_without_cache_split_is_counted_not_assumed() -> None:
    """A usage record lacking cached_input_tokens is counted in diagnostics and billed at the fresh rate."""
    models_prices = {
        "gpt-5.6-luna": {
            "input": 0.20,
            "cached_input": 0.02,
            "output": 1.20,
        }
    }
    diagnostics = {"n_usage_without_cache_split": 0}

    usage = {
        "model": "gpt-5.6-luna",
        "input_tokens": 1_000_000,
        "output_tokens": 50_000,
        "reasoning_output_tokens": 0,
    }
    cost = j12.price_usage_record(usage, models_prices, diagnostics)

    # Hand calculation:
    # uncached input: 1,000,000 * ($0.20 / 1M) = $0.200000
    # output:           50,000 * ($1.20 / 1M) = $0.060000
    # expected total = $0.260000
    assert abs(cost - 0.260000) < 1e-9
    assert diagnostics["n_usage_without_cache_split"] == 1


def test_ordering_flip_is_detected() -> None:
    """Two scripted arms that swap rank between token and dollar axes produce non-empty ordering_flips."""
    # Arm A: high noncached tokens (1000 tokens), but all fresh input with 0 output -> 1000 * 0.20/1M = $0.00020
    # Arm B: low noncached tokens (500 tokens), but all expensive output tokens -> 500 * 1.20/1M = $0.00060
    # On token axis: Arm B (500) < Arm A (1000)
    # On dollar axis: Arm A ($0.00020) < Arm B ($0.00060)
    arm_summaries = [
        {
            "label": "arm_a",
            "noncached_tokens_per_episode": 1000.0,
            "usd_per_episode": 0.00020,
            "hosted_calls_per_episode": 1.0,
        },
        {
            "label": "arm_b",
            "noncached_tokens_per_episode": 500.0,
            "usd_per_episode": 0.00060,
            "hosted_calls_per_episode": 2.0,
        },
    ]

    ordering_by_axis, is_stable, flips = j12.compute_rankings_and_flips(arm_summaries)

    assert ordering_by_axis["noncached_tokens_per_episode"] == ["arm_b", "arm_a"]
    assert ordering_by_axis["usd_per_episode"] == ["arm_a", "arm_b"]
    assert is_stable is False
    assert len(flips) >= 1

    flip = flips[0]
    assert set(flip["pair"]) == {"arm_a", "arm_b"}
    assert flip["axis_a"] == "noncached_tokens_per_episode"
    assert flip["axis_b"] == "usd_per_episode"
    assert flip["order_in_axis_a"] == ["arm_b", "arm_a"]
    assert flip["order_in_axis_b"] == ["arm_a", "arm_b"]


def test_zero_priced_episodes_is_fatal() -> None:
    """An arm yielding zero priced episodes raises SystemExit."""
    arm = {
        "label": "unpriced_arm",
        "cleaned": {
            ("task_01", 1): {
                "planner_tokens_noncached_live": None,
                "replayed_planner_tokens": None,
                "sft_plan_replayed_plan_tokens": None,
            }
        },
    }
    price_card = {
        "models": {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}},
        "usd_per_gpu_hour": 2.50,
    }

    with pytest.raises(SystemExit, match="0 priced episodes"):
        j12.price_arm_episodes(arm, price_card, root=None, packet_source=None, packet_system="planner_alone")


def test_validate_output_path_refuses_forbidden_locations() -> None:
    """validate_output_path refuses paths under results directory or containing test splits."""
    with pytest.raises(ValueError, match="forbidden"):
        j12.validate_output_path(Path("/scratch/n12194778/sidekick/results/cost_report.json"))

    with pytest.raises(ValueError, match="forbidden"):
        j12.validate_output_path(Path("campaign/results/test_normal_cost.json"))

    with pytest.raises(ValueError, match="forbidden"):
        j12.validate_output_path(Path("campaign/results/test_challenge_cost.json"))

    # Valid paths do not raise
    j12.validate_output_path(Path("campaign/results/j12_cost_axes_report.json"))
    j12.validate_output_path(None)


def test_zero_hosted_call_arm_costs_zero_usd() -> None:
    """A scripted arm with no planner usage records yields usd_per_episode == 0.0 and noncached_tokens_per_episode == 0.0, not null."""
    arm = {
        "label": "executor_alone",
        "cleaned": {
            ("task_01", 1): {
                "n_planner_calls": 0,
                "planner_calls_live": 0,
                "planner_tokens_noncached_live": None,
                "replayed_planner_tokens": None,
                "sft_plan_replayed_plan_tokens": None,
            },
            ("task_02", 1): {
                "n_planner_calls": 0,
                "planner_calls_live": 0,
                "planner_tokens_noncached_live": None,
                "replayed_planner_tokens": None,
                "sft_plan_replayed_plan_tokens": None,
            },
        },
    }
    price_card = {
        "models": {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}},
        "usd_per_gpu_hour": 2.50,
    }
    summary = j12.price_arm_episodes(arm, price_card, root=None, packet_source=None, packet_system="planner_alone")
    assert summary["usd_per_episode"] == 0.0
    assert summary["noncached_tokens_per_episode"] == 0.0
    assert summary["hosted_calls_per_episode"] == 0.0
    assert summary["diagnostics"]["n_episodes_priced"] == 2
    assert summary["diagnostics"]["n_episodes_missing_usage"] == 0
    # Per-episode rows (j10_report's P2 ratio interval pairs on them), in key order.
    assert summary["episodes"] == [
        {"task_id": "task_01", "seed": 1, "noncached_tokens_per_episode": 0.0,
         "hosted_calls_per_episode": 0.0, "usd_per_episode": 0.0},
        {"task_id": "task_02", "seed": 1, "noncached_tokens_per_episode": 0.0,
         "hosted_calls_per_episode": 0.0, "usd_per_episode": 0.0},
    ]


def test_usd_is_monotone_in_tokens_at_a_fixed_mix() -> None:
    """Two scripted arms with identical cached/fresh/output proportions but one with 10x the tokens: the second must cost ~10x the first."""
    # Fixed mix: 60% fresh input, 30% cached input, 10% output
    models_prices = {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}}
    diagnostics_1 = {"n_usage_without_cache_split": 0}
    diagnostics_2 = {"n_usage_without_cache_split": 0}

    # Usage 1: 6,000 fresh input (9,000 total input - 3,000 cached), 3,000 cached, 1,000 output
    usage_1 = {
        "model": "gpt-5.6-luna",
        "input_tokens": 9_000,
        "cached_input_tokens": 3_000,
        "output_tokens": 1_000,
        "reasoning_output_tokens": 0,
    }
    # Usage 2: 60,000 fresh input (90,000 total input - 30,000 cached), 30,000 cached, 10,000 output (10x usage 1)
    usage_2 = {
        "model": "gpt-5.6-luna",
        "input_tokens": 90_000,
        "cached_input_tokens": 30_000,
        "output_tokens": 10_000,
        "reasoning_output_tokens": 0,
    }

    cost_1 = j12.price_usage_record(usage_1, models_prices, diagnostics_1)
    cost_2 = j12.price_usage_record(usage_2, models_prices, diagnostics_2)

    # Cost 2 must be strictly greater than Cost 1 and exactly 10x
    assert cost_2 > cost_1
    assert abs(cost_2 - 10.0 * cost_1) < 1e-9


def test_usd_matches_a_hand_computed_total() -> None:
    """One scripted episode with a known split priced against configs/cost/prices_2026-09.yaml equals the hand-computed dollar total."""
    prices_path = REPO / "configs" / "cost" / "prices_2026-09.yaml"
    price_card = j12.load_price_card(prices_path)
    diagnostics = {"n_usage_without_cache_split": 0}

    # 100,000 fresh input + 50,000 cached input -> raw input_tokens = 150,000, cached_input_tokens = 50,000
    # 10,000 output tokens
    usage = {
        "model": "gpt-5.6-luna",
        "input_tokens": 150_000,
        "cached_input_tokens": 50_000,
        "output_tokens": 10_000,
        "reasoning_output_tokens": 0,
    }
    cost = j12.price_usage_record(usage, price_card["models"], diagnostics)

    # Hand calculation:
    # Model: gpt-5.6-luna
    # fresh input rate:  $0.20 per 1M tokens ($0.20 / 1,000,000 = $0.00000020 per token)
    # cached input rate: $0.02 per 1M tokens ($0.02 / 1,000,000 = $0.00000002 per token)
    # output rate:       $1.20 per 1M tokens ($1.20 / 1,000,000 = $0.00000120 per token)
    #
    # fresh input:  100,000 tokens * ($0.20 / 1,000,000) = $0.020000
    # cached input:  50,000 tokens * ($0.02 / 1,000,000) = $0.001000
    # output:        10,000 tokens * ($1.20 / 1,000,000) = $0.012000
    # expected total = $0.020000 + $0.001000 + $0.012000 = $0.033000
    assert abs(cost - 0.033000) < 1e-9


def test_arms_block_is_keyed_by_arm_label() -> None:
    """The report's arms keys equal the labels passed on the CLI."""
    arm1 = {
        "label": "executor_alone",
        "cleaned": {
            ("task_01", 1): {
                "n_planner_calls": 0,
                "planner_calls_live": 0,
                "planner_tokens_noncached_live": None,
                "replayed_planner_tokens": None,
                "sft_plan_replayed_plan_tokens": None,
            }
        },
    }
    arm2 = {
        "label": "planner_alone",
        "cleaned": {
            ("task_01", 1): {
                "n_planner_calls": 1,
                "planner_calls_live": 1,
                "planner_tokens_noncached_live": 10000.0,
                "cached_input_tokens": 5000.0,
                "replayed_planner_tokens": None,
                "sft_plan_replayed_plan_tokens": None,
            }
        },
    }
    price_card = {
        "models": {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}},
        "usd_per_gpu_hour": 2.50,
    }
    summary1 = j12.price_arm_episodes(arm1, price_card, root=None, packet_source=None, packet_system="planner_alone")
    summary2 = j12.price_arm_episodes(arm2, price_card, root=None, packet_source=None, packet_system="planner_alone")

    arm_summaries = [summary1, summary2]
    report_arms = {a["label"]: a for a in arm_summaries}

    assert list(report_arms.keys()) == ["executor_alone", "planner_alone"]
    assert "0" not in report_arms
    assert "1" not in report_arms
    assert report_arms["executor_alone"]["label"] == "executor_alone"
    assert report_arms["planner_alone"]["label"] == "planner_alone"


def test_ordering_flips_are_empty_when_axes_agree() -> None:
    """Three scripted arms whose three axes give the same ordering produce ordering_flips == [] and ordering_is_stable_across_axes is True."""
    arm_summaries = [
        {
            "label": "arm_small",
            "noncached_tokens_per_episode": 100.0,
            "usd_per_episode": 0.0001,
            "hosted_calls_per_episode": 1.0,
        },
        {
            "label": "arm_medium",
            "noncached_tokens_per_episode": 500.0,
            "usd_per_episode": 0.0005,
            "hosted_calls_per_episode": 2.0,
        },
        {
            "label": "arm_large",
            "noncached_tokens_per_episode": 1000.0,
            "usd_per_episode": 0.0010,
            "hosted_calls_per_episode": 5.0,
        },
    ]

    ordering_by_axis, is_stable, flips = j12.compute_rankings_and_flips(arm_summaries)

    assert ordering_by_axis["noncached_tokens_per_episode"] == ["arm_small", "arm_medium", "arm_large"]
    assert ordering_by_axis["usd_per_episode"] == ["arm_small", "arm_medium", "arm_large"]
    assert ordering_by_axis["hosted_calls_per_episode"] == ["arm_small", "arm_medium", "arm_large"]
    assert is_stable is True
    assert flips == []


# ---- Full attribution of replayed plans (unit ATTRIB, 2026-09-25) ------------------------------------
PRICES = {"gpt-5.6-luna": {"input": 0.20, "cached_input": 0.02, "output": 1.20}}
PRICE_CARD = {"models": PRICES, "usd_per_gpu_hour": 2.50}
# The source plan event: 1,000 input of which 500 cached, 100 output, 50 reasoning.
#   non-cached tokens (usage_noncached_tokens) = 1,000 + 100 + 50 = 1,150
#   USD = 500 x 0.20e-6 + 500 x 0.02e-6 + 150 x 1.20e-6 = 0.000100 + 0.000010 + 0.000180 = 0.000290
SOURCE_PLAN_USAGE = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 1000,
                     "cached_input_tokens": 500, "output_tokens": 100, "reasoning_output_tokens": 50, "n_calls": 1}


def _write_events(path: Path, events: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


def _source_episode(campaign: Path, task_id: str = "t1", seed: int = 1) -> Path:
    """A planner_alone source: a dead attempt, then the plan event and a later action whose usage
    (90,000 fresh input) must never be the one priced."""
    stale = dict(SOURCE_PLAN_USAGE, input_tokens=7, cached_input_tokens=0)
    return _write_events(campaign / "planner_alone" / str(seed) / task_id / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "old"}}, "usage": stale},
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "g"}}, "usage": SOURCE_PLAN_USAGE},
        {"event_type": "action", "actor": "planner", "payload": {"kind": "CODE"},
         "usage": dict(SOURCE_PLAN_USAGE, input_tokens=90_000, cached_input_tokens=0)},
    ])


def _cached_plan_event(cached_from: Path | None) -> dict[str, Any]:
    usage = {"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0, "cached_input_tokens": 0,
             "output_tokens": 0, "reasoning_output_tokens": 0, "n_calls": 1}
    if cached_from is not None:
        usage["raw"] = {"cached_from": str(cached_from)}
    return {"event_type": "plan", "actor": "planner", "step": 0, "payload": {"packet": {"goal": "g"}}, "usage": usage}


def test_replayed_plan_is_priced_from_its_source_plan_event(tmp_path: Path) -> None:
    source = _source_episode(tmp_path / "src")
    episode = _write_events(tmp_path / "arm" / "1" / "t1" / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        _cached_plan_event(source),
        {"event_type": "intervention", "actor": "planner", "payload": {}, "usage": dict(SOURCE_PLAN_USAGE)},
    ])
    assert [u["provider"] for u in j12.cached_plan_usages(episode)] == ["cache"]
    assert j12.replayed_plan_usage(source) == SOURCE_PLAN_USAGE  # the last attempt's plan, not the action
    att = j12.episode_cached_plan_attribution(episode, PRICES, packet_source=tmp_path / "src")
    assert (att["n_cached_plan_events"], att["cache_calls"], att["n_source_missing"]) == (1, 1, 0)
    assert att["n_cached_from_outside_packet_source"] == 0
    assert att["noncached_tokens"] == 1150.0
    assert abs(att["usd"] - 0.000290) < 1e-12
    # cached_from outside the configured packet_source is counted, still priced from cached_from.
    elsewhere = j12.episode_cached_plan_attribution(episode, PRICES, packet_source=tmp_path / "other")
    assert elsewhere["n_cached_from_outside_packet_source"] == 1 and elsewhere["noncached_tokens"] == 1150.0


def test_cached_plan_without_cached_from_reads_the_packet_source_layout(tmp_path: Path) -> None:
    _source_episode(tmp_path / "src", task_id="t9", seed=2)
    episode = _write_events(tmp_path / "arm" / "2" / "t9" / "events.jsonl", [_cached_plan_event(None)])
    att = j12.episode_cached_plan_attribution(episode, PRICES, packet_source=tmp_path / "src",
                                              packet_system="planner_alone", task_id="t9", seed=2)
    assert (att["n_source_missing"], att["noncached_tokens"]) == (0, 1150.0)
    missing = j12.episode_cached_plan_attribution(episode, PRICES, packet_source=None, task_id="t9", seed=2)
    assert (missing["n_cached_plan_events"], missing["n_source_missing"], missing["usd"]) == (1, 1, 0.0)


def _attribution_arm(tmp_path: Path, source: Path) -> tuple[dict[str, Any], Path]:
    """Two channel episodes. t1 replays the source plan and makes one live review:
    300 input (100 cached), 50 output, 50 reasoning -> 200 x 0.20e-6 + 100 x 0.02e-6 + 100 x 1.20e-6
    = 0.000162, and the ledger's live non-cached tokens are 400. t2 planned live: 100 fresh input
    -> 0.000020, ledger 100 tokens."""
    root = tmp_path / "arm"
    review = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 300, "cached_input_tokens": 100,
              "output_tokens": 50, "reasoning_output_tokens": 50, "n_calls": 1}
    live_plan = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 100, "cached_input_tokens": 0,
                 "output_tokens": 0, "reasoning_output_tokens": 0, "n_calls": 1}
    _write_events(root / "1" / "t1" / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        _cached_plan_event(source),
        {"event_type": "intervention", "actor": "planner", "payload": {}, "usage": review},
    ])
    _write_events(root / "1" / "t2" / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {}}, "usage": live_plan},
    ])
    row = {"system": "fixed_k", "replayed_planner_tokens": None, "sft_plan_replayed_plan_tokens": None}
    arm = {"label": "takeover_k10", "cleaned": {
        ("t1", 1): dict(row, n_planner_calls=2, planner_tokens_noncached_live=400.0),
        ("t2", 1): dict(row, n_planner_calls=1, planner_tokens_noncached_live=100.0),
    }}
    return arm, root


def test_price_arm_episodes_attributed_by_hand(tmp_path: Path) -> None:
    source = _source_episode(tmp_path / "src")
    arm, root = _attribution_arm(tmp_path, source)
    copy = {"label": arm["label"], "cleaned": {k: dict(v) for k, v in arm["cleaned"].items()}}
    default = j12.price_arm_episodes(copy, PRICE_CARD, root=root, packet_source=tmp_path / "src",
                                     packet_system="planner_alone")
    # As published: the replayed plan is one call but 0 tokens and $0.
    # tokens (400 + 100) / 2 = 250; USD (0.000162 + 0.000020) / 2 = 0.000091; calls (2 + 1) / 2 = 1.5.
    assert (default["noncached_tokens_per_episode"], default["usd_per_episode"],
            default["hosted_calls_per_episode"]) == (250.0, 0.000091, 1.5)
    assert "cached_plan_attribution" not in default
    att = j12.price_arm_episodes_attributed(arm, PRICE_CARD, root=root, packet_source=tmp_path / "src",
                                            packet_system="planner_alone")
    # Attributed: t1 gains the source plan's 1,150 tokens and $0.000290.
    # tokens (1,550 + 100) / 2 = 825; USD (0.000452 + 0.000020) / 2 = 0.000236; calls unchanged.
    assert (att["noncached_tokens_per_episode"], att["usd_per_episode"], att["hosted_calls_per_episode"]) == (
        825.0, 0.000236, 1.5)
    assert att["episodes"][0]["noncached_tokens_per_episode"] == 1550.0
    assert abs(att["episodes"][0]["usd_per_episode"] - 0.000452) < 1e-12
    assert att["episodes"][1] == default["episodes"][1]
    info = att["cached_plan_attribution"]
    assert (info["applied"], info["route"], info["n_episodes_with_cached_plan"], info["n_cached_plan_events"]) == (
        True, "source_plan_event", 1, 1)
    assert (info["noncached_tokens_added_per_episode"], info["usd_added_per_episode"]) == (575.0, 0.000145)


def test_attribution_leaves_sft_plan_rows_and_partial_maps_as_priced(tmp_path: Path) -> None:
    source = _source_episode(tmp_path / "src")
    arm, root = _attribution_arm(tmp_path, source)
    arm["cleaned"][("t1", 1)]["system"] = "sft_plan"  # already charged its source by :361-367
    baseline = j12.price_arm_episodes({"label": arm["label"], "cleaned": {k: dict(v) for k, v in arm["cleaned"].items()}},
                                      PRICE_CARD, root=root, packet_source=tmp_path / "src", packet_system="planner_alone")
    sft = j12.price_arm_episodes_attributed(arm, PRICE_CARD, root=root, packet_source=tmp_path / "src",
                                            packet_system="planner_alone")
    assert sft["episodes"] == baseline["episodes"]
    assert sft["cached_plan_attribution"]["n_sft_plan_rows_left_as_priced"] == 1
    assert (sft["cached_plan_attribution"]["applied"], sft["cached_plan_attribution"]["route"]) == (
        False, "sft_plan_already_charged")
    # A replayed plan whose source cannot be read: nothing is applied, and the arm says so.
    arm2, root2 = _attribution_arm(tmp_path / "b", tmp_path / "nowhere" / "events.jsonl")
    partial = j12.price_arm_episodes_attributed(arm2, PRICE_CARD, root=root2, packet_source=None,
                                                packet_system="planner_alone")
    assert (partial["noncached_tokens_per_episode"], partial["usd_per_episode"]) == (250.0, 0.000091)
    info = partial["cached_plan_attribution"]
    assert (info["applied"], info["route"], info["n_source_missing"], info["missing_examples"]) == (
        False, "understatement", 1, ["t1/1"])


def test_sft_plan_is_charged_its_source_plan_event_not_the_source_last_usage(tmp_path: Path) -> None:
    """COSTFIX: the sft_plan branch (:361-367) prices the replayed plan event on USD, and the floor's tokens
    (j8_noncached_cost, summarise_arm) come from the same event, although the source's last planner usage
    is a later action (90,000 fresh input + 150 output = $0.018180, which the old [-1] priced)."""
    _source_episode(tmp_path / "src")
    root = tmp_path / "arm"
    _write_events(root / "1" / "t1" / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}}, _cached_plan_event(tmp_path / "src")])
    arm = {"label": "plan_only", "cleaned": {("t1", 1): {
        "system": "sft_plan", "n_planner_calls": 1, "planner_tokens_noncached_live": 0.0,
        "replayed_planner_tokens": None, "sft_plan_replayed_plan_tokens": None}}}
    info = j12.attach_sft_plan_source_plan_tokens(arm["cleaned"], "plan_only", tmp_path / "src", "planner_alone")
    assert info["applied"] is True and arm["cleaned"][("t1", 1)]["sft_plan_replayed_plan_tokens"] == 1150.0
    summary = j12.price_arm_episodes(arm, PRICE_CARD, root=root, packet_source=tmp_path / "src",
                                     packet_system="planner_alone")
    # tokens 0 live + 1,150 replayed plan; USD $0 for the cache record + $0.000290 for the plan event.
    assert summary["noncached_tokens_per_episode"] == 1150.0
    assert summary["usd_per_episode"] == 0.00029
    action = dict(SOURCE_PLAN_USAGE, input_tokens=90_000, cached_input_tokens=0)
    assert abs(j12.price_usage_record(action, PRICES, {"n_usage_without_cache_split": 0}) - 0.018180) < 1e-12
    # The attributed path leaves the row as the default branch priced it.
    att = j12.price_arm_episodes_attributed(arm, PRICE_CARD, root=root, packet_source=tmp_path / "src",
                                            packet_system="planner_alone")
    assert (att["noncached_tokens_per_episode"], att["usd_per_episode"]) == (1150.0, 0.00029)


def test_attribution_is_opt_in_and_the_default_report_is_unchanged() -> None:
    args = j12.parse_args(["--arm", "a=/nonexistent", "--out", "/tmp/x.json"])
    assert args.attribute_cached_plans is False
    assert j12._attribution_block(args, [{"label": "a"}]) == {}
    assert j12._attribution_title({"arms": {}}) == ""
    on = j12.parse_args(["--arm", "a=/nonexistent", "--out", "/tmp/x.json", "--attribute-cached-plans"])
    block = j12._attribution_block(on, [{"label": "a", "cached_plan_attribution": {"applied": True}}])
    assert block["cached_plan_attribution"]["per_arm"] == {"a": {"applied": True}}
    assert j12._attribution_title(block).endswith("replayed plans fully attributed")

