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
