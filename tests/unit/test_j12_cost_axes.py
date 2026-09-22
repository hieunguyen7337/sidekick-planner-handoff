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

