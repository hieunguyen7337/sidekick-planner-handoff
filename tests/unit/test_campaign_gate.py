"""The campaign gate's model-provenance check.

Regression for 2026-09-16: `hj1c_fixed_k` finished 114/114 with every real planner
call going to gpt-5.6-luna, and the gate still reported

    planner ran as ['codex-exec'], expected only 'gpt-5.6-luna'

because 3 of the 114 runs hit a `PacketParseError`, and the loop's bookkeeping Usage
for a failed call was labelled with the planner CLASS name. The gate must ignore that
placeholder without going blind to the mistyped-`planner.type` fallback it exists for.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "campaign_summarize",
    Path(__file__).resolve().parents[2] / "scripts" / "setup" / "campaign_summarize.py",
)
cs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cs)


def _usage(model, provider, *, input_tokens=0, error_type=None):
    u = {
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "n_calls": 1,
        "raw": {},
    }
    if error_type:
        u["raw"]["error_type"] = error_type
    return u


# The record shapes as actually written to events.jsonl on 2026-09-16.
REAL_LUNA = _usage("gpt-5.6-luna", "codex", input_tokens=26007)
PARSE_PLACEHOLDER = _usage("codex-exec", "mock", error_type="parse_error")
TIMEOUT_PLACEHOLDER = _usage("codex-exec", "mock", error_type="timeout")
MOCK_FALLBACK = _usage("mock-planner", "mock", input_tokens=15378)


def _write(root: Path, records):
    run = root / "fixed_k" / "1" / "task_1"
    run.mkdir(parents=True)
    with (run / "events.jsonl").open("w", encoding="utf-8") as fh:
        for u in records:
            fh.write(json.dumps({"actor": "planner", "event_type": "x", "usage": u}) + "\n")
    return root


@pytest.mark.parametrize("placeholder", [PARSE_PLACEHOLDER, TIMEOUT_PLACEHOLDER])
def test_failed_call_placeholder_is_not_model_provenance(tmp_path, placeholder):
    _write(tmp_path, [REAL_LUNA, placeholder, REAL_LUNA])
    assert dict(cs._planner_models(tmp_path)) == {"gpt-5.6-luna": 2}


def test_mock_planner_fallback_is_still_caught(tmp_path):
    """The check's whole purpose: a mistyped planner.type falls back to MockPlanner.

    Its usage carries REAL token counts, so the placeholder filter must not hide it.
    """
    _write(tmp_path, [MOCK_FALLBACK, MOCK_FALLBACK])
    assert dict(cs._planner_models(tmp_path)) == {"mock-planner": 2}


def test_a_genuinely_wrong_model_is_still_caught(tmp_path):
    _write(tmp_path, [REAL_LUNA, _usage("gpt-5.6-sol", "codex", input_tokens=900)])
    assert dict(cs._planner_models(tmp_path)) == {"gpt-5.6-luna": 1, "gpt-5.6-sol": 1}


def _summary(models, planner_calls=934, planner_calls_live_total=None):
    if planner_calls_live_total is None:
        planner_calls_live_total = planner_calls
    return {
        "n_runs": 114,
        "n_broken": 16,
        "errors": {"limit": 96, "parse_error": 12, "crash": 4},
        "steps_mean": 36.2,
        "planner_models": models,
        "planner_calls_total": planner_calls,
        "planner_calls_live_total": planner_calls_live_total,
    }


def test_gate_passes_for_the_fixed_k_arm_as_it_actually_ran():
    fails = cs.gate(
        _summary({"gpt-5.6-luna": 931}),
        expect_planner=True,
        expect_model="gpt-5.6-luna",
    )
    assert fails == []


def test_gate_still_fails_on_a_wrong_model():
    fails = cs.gate(
        _summary({"gpt-5.6-luna": 900, "mock-planner": 31}),
        expect_planner=True,
        expect_model="gpt-5.6-luna",
    )
    assert any("mock-planner" in f for f in fails)


def test_gate_still_fails_when_the_planner_was_never_invoked():
    fails = cs.gate(
        _summary({}, planner_calls=0),
        expect_planner=True,
        expect_model="gpt-5.6-luna",
    )
    assert any("zero planner calls" in f for f in fails)


def test_free_arm_prefix_handoff_replay_is_not_spend():
    """prefix_handoff: 3 smoke eps × (2 replayed actions + 1 plan) at m=2 → 9 replay, 0 live."""
    fails = cs.gate(
        _summary({}, planner_calls=9, planner_calls_live_total=0),
        expect_planner=False,
        expect_model=None,
    )
    assert fails == []


def test_free_arm_live_spend_fails_with_both_counts():
    fails = cs.gate(
        _summary({}, planner_calls=9, planner_calls_live_total=4),
        expect_planner=False,
        expect_model=None,
    )
    assert len(fails) == 1
    msg = fails[0]
    assert "expected zero live planner calls but saw 4" in msg
    assert "replay-inclusive count 9" in msg
    assert "models={}" in msg


def test_non_free_arm_zero_calls_still_fails_expect_planner():
    """Guards MockPlanner-fallback detection; ledger 0 must not change this branch."""
    fails = cs.gate(
        _summary({}, planner_calls=0, planner_calls_live_total=0),
        expect_planner=True,
        expect_model="gpt-5.6-luna",
    )
    assert any(
        "zero planner calls recorded -- the planner was never invoked" in f
        for f in fails
    )


def test_summary_keeps_replay_inclusive_planner_calls_total(tmp_path):
    root = tmp_path / "campaign"
    for i in range(3):
        path = root / "prefix_handoff" / "1" / f"task_{i}" / "result.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "seed": 1,
                    "success": True,
                    "n_planner_calls": 3,
                    "totals": {"planner_calls_total": 0, "planner_tokens_total": 0},
                }
            )
            + "\n",
            encoding="utf-8",
        )

    summary = cs.summarise(tmp_path, "campaign")
    assert summary["planner_calls_total"] == 9
    assert summary["planner_calls_live_total"] == 0
    assert summary["ledger_totals"]["planner_calls_total"] == 0.0
