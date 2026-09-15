import math

import pytest

from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule, UnknownModelError
from sidekick.protocols.schemas import Usage

CONFIG = "configs/cost/prices_2026-09.yaml"


@pytest.fixture(scope="module")
def prices():
    return PriceSchedule.load(CONFIG)


def luna(**kw):
    return Usage(model="gpt-5.6-luna", provider="codex", **kw)


def test_load_schedule(prices):
    assert prices.schedule_date == "2026-09-15"
    assert prices.usd_per_gpu_hour == 2.50
    assert set(prices.models) == {"gpt-5.6-luna", "gpt-5.6-terra"}


def test_luna_rates(prices):
    assert prices.models["gpt-5.6-luna"] == {"input": 0.20, "cached_input": 0.02, "output": 1.20}


def test_luna_uncached_only(prices):
    # 1_000_000 input tokens at $0.20/1M = $0.20
    assert prices.cost_usd(luna(input_tokens=1_000_000)) == pytest.approx(0.20)


def test_luna_cached_split(prices):
    # 500k input, 100k cached: 400k*0.20/1M + 100k*0.02/1M = 0.08 + 0.002 = 0.082
    u = luna(input_tokens=500_000, cached_input_tokens=100_000)
    assert prices.cost_usd(u) == pytest.approx(0.082)


def test_luna_output(prices):
    # 200k output at $1.20/1M = 0.24
    assert prices.cost_usd(luna(output_tokens=200_000)) == pytest.approx(0.24)


def test_reasoning_tokens_billed_as_output(prices):
    # 100k reasoning at $1.20/1M = 0.12, zero output tokens
    assert prices.cost_usd(luna(reasoning_output_tokens=100_000)) == pytest.approx(0.12)


def test_reasoning_plus_output_summed(prices):
    # 100k output + 50k reasoning = 150k at 1.20/1M = 0.18
    u = luna(output_tokens=100_000, reasoning_output_tokens=50_000)
    assert prices.cost_usd(u) == pytest.approx(0.18)


def test_full_mixed_call_hand_computed(prices):
    # input 1_200_000, cached 300_000, output 150_000, reasoning 50_000
    # = 900k*0.2/1M + 300k*0.02/1M + 200k*1.2/1M
    # = 0.18 + 0.006 + 0.24 = 0.426
    u = luna(input_tokens=1_200_000, cached_input_tokens=300_000,
             output_tokens=150_000, reasoning_output_tokens=50_000)
    assert prices.cost_usd(u) == pytest.approx(0.426)


def test_terra_rates(prices):
    # terra: input 2.00, cached 0.20, output 12.00 per 1M
    # 100k input, 50k cached, 10k output:
    # 50k*2/1M + 50k*0.2/1M + 10k*12/1M = 0.10 + 0.01 + 0.12 = 0.23
    u = Usage(model="gpt-5.6-terra", provider="codex",
              input_tokens=100_000, cached_input_tokens=50_000, output_tokens=10_000)
    assert prices.cost_usd(u) == pytest.approx(0.23)


def test_unknown_model_raises(prices):
    with pytest.raises(UnknownModelError):
        prices.cost_usd(Usage(model="gpt-99", provider="codex", input_tokens=10))


def test_vllm_billed_by_gpu_seconds(prices):
    # 1800 s at $2.50/h = 1.25
    u = Usage(model="local-h100", provider="vllm", gpu_seconds=1800.0)
    assert prices.cost_usd(u) == pytest.approx(1.25)


def test_vllm_no_token_cost(prices):
    u = Usage(model="local-h100", provider="vllm", input_tokens=10_000_000,
              output_tokens=10_000_000, gpu_seconds=0.0)
    assert prices.cost_usd(u) == 0.0


def test_mock_is_free(prices):
    u = Usage(model="mock-model", provider="mock", input_tokens=999_999,
              output_tokens=999_999, gpu_seconds=1e9)
    assert prices.cost_usd(u) == 0.0


def test_zero_usage_is_zero(prices):
    assert prices.cost_usd(luna()) == 0.0


# ---------- CostLedger ----------

def test_ledger_totals_keys(prices):
    led = CostLedger(prices)
    led.add("planner", luna(input_tokens=100))
    t = led.totals()
    assert set(t) == {
        "per_actor", "planner_tokens_total", "planner_calls_total",
        "executor_tokens_total", "gpu_seconds_total", "usd_total",
    }
    assert set(t["per_actor"]["planner"]) == {
        "input_tokens", "cached_input_tokens", "output_tokens",
        "reasoning_output_tokens", "n_calls", "gpu_seconds", "usd",
    }


def test_ledger_accumulates(prices):
    led = CostLedger(prices)
    led.add("planner", luna(input_tokens=1_000_000, n_calls=2))
    led.add("executor", Usage(model="local-h100", provider="vllm", gpu_seconds=3600.0, n_calls=1))
    t = led.totals()
    assert t["planner_tokens_total"] == 1_000_000
    assert t["planner_calls_total"] == 2
    assert t["executor_tokens_total"] == 0
    assert t["gpu_seconds_total"] == pytest.approx(3600.0)
    assert t["usd_total"] == pytest.approx(0.20 + 2.50)


def test_ledger_empty_totals(prices):
    t = CostLedger(prices).totals()
    assert t["planner_tokens_total"] == 0 and t["usd_total"] == 0.0
    assert t["per_actor"] == {}


def test_ledger_reasoning_in_planner_tokens(prices):
    led = CostLedger(prices)
    led.add("planner", luna(input_tokens=100, reasoning_output_tokens=50))
    assert led.totals()["planner_tokens_total"] == 150


# ---------- frontier displacement ----------

def test_fcd_basic():
    collab = {"planner_tokens_total": 400, "planner_calls_total": 5}
    base = {"planner_tokens_total": 1000, "planner_calls_total": 10}
    fcd = CostLedger.frontier_displacement(collab, base)
    assert fcd["fcd_tokens"] == pytest.approx(0.6)
    assert fcd["fcd_calls"] == pytest.approx(0.5)


def test_fcd_zero_baseline_is_nan():
    fcd = CostLedger.frontier_displacement(
        {"planner_tokens_total": 10, "planner_calls_total": 1},
        {"planner_tokens_total": 0, "planner_calls_total": 0},
    )
    assert math.isnan(fcd["fcd_tokens"])
    assert math.isnan(fcd["fcd_calls"])


def test_fcd_zero_displacement():
    fcd = CostLedger.frontier_displacement(
        {"planner_tokens_total": 100, "planner_calls_total": 4},
        {"planner_tokens_total": 100, "planner_calls_total": 4},
    )
    assert fcd["fcd_tokens"] == 0.0 and fcd["fcd_calls"] == 0.0


def test_fcd_negative_when_collab_exceeds_baseline():
    fcd = CostLedger.frontier_displacement(
        {"planner_tokens_total": 200, "planner_calls_total": 2},
        {"planner_tokens_total": 100, "planner_calls_total": 1},
    )
    assert fcd["fcd_tokens"] == pytest.approx(-1.0)
    assert fcd["fcd_calls"] == pytest.approx(-1.0)
