"""Unit tests for scripts/analysis/j8_noncached_cost.py (PLANLESSFLOOR, 2026-09-25).

attach_sft_plan_source_plan_tokens charges each sft_plan (J10 arm 2, "floor") row the non-cached tokens of
the source plan event it replays. A planless key (J10 A1 §4.2: the arm-3 source was scored without a crash
but wrote no plan, so arm 2 planned it live) must not send the whole arm down the all-or-nothing
understatement route: its live plan is already in the row's planner_tokens_noncached_live.

Fixture shapes follow tests/unit/test_j12_cost_axes.py (SOURCE_PLAN_USAGE, _write_events, _source_episode,
and the arm["cleaned"] rows of test_sft_plan_is_charged_its_source_plan_event_not_the_source_last_usage).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:  # the planless check imports sidekick.agents.planner lazily
    sys.path.insert(0, str(REPO / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "j8_noncached_cost", REPO / "scripts" / "analysis" / "j8_noncached_cost.py"
)
nc = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(nc)

LABEL = "plan_only"
SYSTEM = "planner_alone"

# t1's source plan event: 1,000 input (500 of it cached) + 100 output + 50 reasoning.
#   non-cached = input + output + reasoning (cached excluded) = 1,000 + 100 + 50 = 1,150
SOURCE_PLAN_USAGE = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 1000,
                     "cached_input_tokens": 500, "output_tokens": 100, "reasoning_output_tokens": 50, "n_calls": 1}
# t2's source plan event: 2,000 input + 300 output + 0 reasoning = 2,300 non-cached.
SOURCE_PLAN_USAGE_T2 = dict(SOURCE_PLAN_USAGE, input_tokens=2000, cached_input_tokens=0, output_tokens=300,
                            reasoning_output_tokens=0)
T1_TOKENS = 1150.0
T2_TOKENS = 2300.0
# mean over the two mapped plan events = (1,150 + 2,300) / 2 = 3,450 / 2 = 1,725
MAPPED_MEAN = 1725.0
# The planless key's own live planner usage (its live first plan and later calls), non-cached.
PLANLESS_LIVE = 4200.0


def _write_events(path: Path, events: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    return path


def _write_result(episode_dir: Path, error_type: str | None) -> None:
    episode_dir.mkdir(parents=True, exist_ok=True)
    (episode_dir / "result.json").write_text(
        json.dumps({"task_id": episode_dir.name, "tgc": 0.0, "error_type": error_type}), encoding="utf-8")


def _planned_source(campaign: Path, task_id: str, seed: int, usage: dict[str, Any]) -> Path:
    """A planner_alone source: a dead attempt, then the plan event, then a later action whose usage
    (90,000 fresh input) must never be the one charged."""
    stale = dict(usage, input_tokens=7, cached_input_tokens=0)
    return _write_events(campaign / SYSTEM / str(seed) / task_id / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "old"}}, "usage": stale},
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "g"}}, "usage": usage},
        {"event_type": "action", "actor": "planner", "payload": {"kind": "CODE"},
         "usage": dict(usage, input_tokens=90_000, cached_input_tokens=0)},
    ])


def _planless_source(campaign: Path, task_id: str, seed: int, error_type: str | None = None) -> Path:
    """A source whose dead attempt planned but whose LAST attempt wrote no plan, scored (result.json)."""
    events = _write_events(campaign / SYSTEM / str(seed) / task_id / "events.jsonl", [
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "old"}},
         "usage": SOURCE_PLAN_USAGE},
        {"event_type": "run_start", "actor": "system", "payload": {}},
        {"event_type": "action", "actor": "executor", "payload": {"kind": "CODE"}},
    ])
    _write_result(events.parent, error_type)
    return events


def _row(live: float | None) -> dict[str, Any]:
    return {"system": "sft_plan", "n_planner_calls": 1, "planner_tokens_noncached_live": live,
            "replayed_planner_tokens": None, "sft_plan_replayed_plan_tokens": None}


def _two_planned(tmp_path: Path) -> tuple[Path, dict[tuple[str, int], dict[str, Any]]]:
    src = tmp_path / "src"
    _planned_source(src, "t1", 1, SOURCE_PLAN_USAGE)
    _planned_source(src, "t2", 1, SOURCE_PLAN_USAGE_T2)
    return src, {("t1", 1): _row(0.0), ("t2", 1): _row(0.0)}


def test_all_keys_planned_is_unchanged(tmp_path: Path) -> None:
    src, cleaned = _two_planned(tmp_path)
    info = nc.attach_sft_plan_source_plan_tokens(cleaned, LABEL, src, SYSTEM)
    assert (info["applied"], info["route"]) == (True, "source_plan_event")
    assert (info["n_sft_plan_rows"], info["n_mapped"], info["n_missing"]) == (2, 2, 0)
    assert (info["n_planless_live"], info["planless_keys"]) == (0, [])
    assert info["mean_noncached_plan_tokens"] == MAPPED_MEAN
    assert cleaned[("t1", 1)]["sft_plan_replayed_plan_tokens"] == T1_TOKENS
    assert cleaned[("t2", 1)]["sft_plan_replayed_plan_tokens"] == T2_TOKENS
    # floor cost = 0 live + replayed plan: 1,150 and 2,300
    assert [nc.noncached_episode_cost(cleaned[k]) for k in (("t1", 1), ("t2", 1))] == [T1_TOKENS, T2_TOKENS]


def test_planless_key_with_a_live_plan_maps_at_zero_and_keeps_the_others(tmp_path: Path) -> None:
    src, cleaned = _two_planned(tmp_path)
    _planless_source(src, "t3", 2)
    cleaned[("t3", 2)] = _row(PLANLESS_LIVE)
    info = nc.attach_sft_plan_source_plan_tokens(cleaned, LABEL, src, SYSTEM)
    assert (info["applied"], info["route"], info["understatement"]) == (True, "source_plan_event", None)
    # n_mapped counts plan events; 2 mapped + 1 planless + 0 missing == 3 rows
    assert (info["n_sft_plan_rows"], info["n_mapped"], info["n_planless_live"], info["n_missing"]) == (3, 2, 1, 0)
    assert info["planless_keys"] == ["2/t3"]
    # the mean is over the two replayed plan events only: (1,150 + 2,300) / 2
    assert info["mean_noncached_plan_tokens"] == MAPPED_MEAN
    assert cleaned[("t1", 1)]["sft_plan_replayed_plan_tokens"] == T1_TOKENS
    assert cleaned[("t2", 1)]["sft_plan_replayed_plan_tokens"] == T2_TOKENS
    assert cleaned[("t3", 2)]["sft_plan_replayed_plan_tokens"] == 0.0
    # the planless row costs its own live usage only: 4,200 + 0 = 4,200
    costs = [nc.noncached_episode_cost(cleaned[k]) for k in (("t1", 1), ("t2", 1), ("t3", 2))]
    assert costs == [T1_TOKENS, T2_TOKENS, PLANLESS_LIVE]
    # arm mean = (1,150 + 2,300 + 4,200) / 3 = 7,650 / 3 = 2,550 (the old route gave (0 + 0 + 4,200) / 3 = 1,400)
    assert sum(costs) / len(costs) == 2550.0


@pytest.mark.parametrize("live", [0.0, None, "absent"])
def test_planless_key_without_a_live_plan_is_a_miss(tmp_path: Path, live: Any) -> None:
    src, cleaned = _two_planned(tmp_path)
    _planless_source(src, "t3", 2)
    row = _row(None if live == "absent" else live)
    if live == "absent":
        del row["planner_tokens_noncached_live"]
    cleaned[("t3", 2)] = row
    info = nc.attach_sft_plan_source_plan_tokens(cleaned, LABEL, src, SYSTEM)
    assert (info["applied"], info["route"]) == (False, "understatement")
    assert (info["n_mapped"], info["n_planless_live"], info["n_missing"], info["planless_keys"]) == (2, 0, 1, [])
    under = info["understatement"]
    assert (under["arm"], under["n_mapped"], under["n_missing"]) == (LABEL, 2, 1)
    assert under["estimated_mean_noncached_plan_tokens"] == MAPPED_MEAN
    assert len(under["missing_examples"]) == 1
    assert under["missing_examples"][0].startswith("t3/2: planless source but no live plan in the episode")
    # all-or-nothing: no row is charged anything
    assert all(r["sft_plan_replayed_plan_tokens"] is None for r in cleaned.values())


def test_missing_source_file_is_an_understatement_as_before(tmp_path: Path) -> None:
    src, cleaned = _two_planned(tmp_path)
    cleaned[("t9", 1)] = _row(PLANLESS_LIVE)
    info = nc.attach_sft_plan_source_plan_tokens(cleaned, LABEL, src, SYSTEM)
    assert (info["applied"], info["route"]) == (False, "understatement")
    assert (info["n_mapped"], info["n_planless_live"], info["n_missing"]) == (2, 0, 1)
    missing = info["understatement"]["missing_examples"]
    assert missing == [f"t9/1: missing {src / SYSTEM / '1' / 't9' / 'events.jsonl'}"]
    assert all(r["sft_plan_replayed_plan_tokens"] is None for r in cleaned.values())


@pytest.mark.parametrize("case", ["crashed", "no_result", "plan_without_usage"])
def test_non_planless_source_without_plan_usage_is_an_understatement(tmp_path: Path, case: str) -> None:
    """Not planless by planner.py: a crashed or unscored source, or a plan event that has no usage."""
    src, cleaned = _two_planned(tmp_path)
    if case == "crashed":
        _planless_source(src, "t3", 1, error_type="crash")
    elif case == "no_result":
        events = _planless_source(src, "t3", 1)
        (events.parent / "result.json").unlink()
    else:
        events = _write_events(src / SYSTEM / "1" / "t3" / "events.jsonl", [
            {"event_type": "run_start", "actor": "system", "payload": {}},
            {"event_type": "plan", "actor": "planner", "payload": {"packet": {"goal": "g"}}},
        ])
        _write_result(events.parent, None)
    cleaned[("t3", 1)] = _row(PLANLESS_LIVE)
    info = nc.attach_sft_plan_source_plan_tokens(cleaned, LABEL, src, SYSTEM)
    assert (info["applied"], info["route"]) == (False, "understatement")
    assert (info["n_mapped"], info["n_planless_live"], info["n_missing"]) == (2, 0, 1)
    assert info["understatement"]["missing_examples"][0].startswith("t3/1: no plan-event usage at ")
    assert all(r["sft_plan_replayed_plan_tokens"] is None for r in cleaned.values())
