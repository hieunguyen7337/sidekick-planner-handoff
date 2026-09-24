"""Unit tests for scripts/analysis/replay_divergence_diagnose.py (DIVDIAG, 2026-09-25). No AppWorld."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_SPEC = importlib.util.spec_from_file_location(
    "replay_divergence_diagnose", REPO / "scripts" / "analysis" / "replay_divergence_diagnose.py"
)
ddx = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(ddx)


def test_address_only_difference_is_address() -> None:
    rec = "(user = Depends(dependency=<a.LogInOutManager object at 0x14804efed640>, use_cache=True)) -> list[str]"
    live = "(user = Depends(dependency=<a.LogInOutManager object at 0x7f3a2b1c0d90>, use_cache=True)) -> list[str]"
    assert ddx.classify_difference(rec, live) == "address"


def test_reordered_set_repr_is_reordering() -> None:
    rec = "Friend emails: {'persona9@example.invalid', 'persona7@example.invalid', 'persona11@example.invalid'}\nTotal: 273"
    live = "Friend emails: {'persona11@example.invalid', 'persona9@example.invalid', 'persona7@example.invalid'}\nTotal: 273"
    assert ddx.classify_difference(rec, live) == "reordering"


def test_genuinely_different_text_is_other() -> None:
    rec = "Total transactions: 273\nCount to like: 24"
    live = "Total transactions: 274\nCount to like: 24"
    assert ddx.classify_difference(rec, live) == "other"


def test_extra_set_element_is_other_not_reordering() -> None:
    rec = "{'a@x.com', 'b@x.com'}"
    live = "{'b@x.com', 'a@x.com', 'c@x.com'}"
    assert ddx.classify_difference(rec, live) == "other"


def test_identical_text_is_identical() -> None:
    text = "Friend emails: {'a@x.com', 'b@x.com'}"
    assert ddx.classify_difference(text, text) == "identical"


def test_diff_region_is_bounded_and_located() -> None:
    rec = "x" * 1000 + "A" + "y" * 1000
    live = "x" * 1000 + "B" + "y" * 1000
    region = ddx.diff_region(rec, live)
    assert region["first_diff_char"] == 1000
    assert len(region["recorded"]) <= 300 and len(region["live"]) <= 300
    assert "A" in region["recorded"] and "B" in region["live"]


def test_set_regex_matches_sets_not_dicts() -> None:
    assert ddx.SET_LITERAL_RE.search("emails: {'a@x.com', 'b@x.com'}")
    assert not ddx.SET_LITERAL_RE.search("{'message': 'Liked transaction.'}")
    assert not ddx.SET_LITERAL_RE.search("{'a': 'b', 'c': 'd'}")
    assert not ddx.SET_LITERAL_RE.search("{'only_one'}")
    assert ddx.ADDRESS_RE.search("<m.LogInOutManager object at 0x14804efed640>")


@pytest.mark.parametrize(
    "source",
    [
        "/scratch/n12194778/sidekick/results/j11_prefix_zs_m11_20260924",
        "/scratch/n12194778/sidekick/results/j10_anything",
        "/scratch/n12194778/sidekick/results/j12_anything",
        "/data/test_normal/tasks",
        "/data/test_challenge/tasks",
    ],
)
def test_held_out_source_exits_2(source: str) -> None:
    with pytest.raises(SystemExit) as exc:
        ddx.main(["scan", "--source", source, "--system", "planner_alone", "--max-step", "11"])
    assert exc.value.code == 2


def test_held_out_guard_on_replay_exits_2() -> None:
    with pytest.raises(SystemExit) as exc:
        ddx.main(
            [
                "replay", "--source", "/scratch/x/results/j11_foo", "--system", "planner_alone",
                "--seed", "1", "--task", "68ee2c9_2", "--m", "11",
            ]
        )
    assert exc.value.code == 2


def test_dev_source_is_not_refused() -> None:
    assert ddx.held_out_reason(
        "/scratch/n12194778/sidekick/results/lp2_planner_alone_cap81_qwen38_27b_20260923"
    ) is None
