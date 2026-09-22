"""campaign_summarize --purge-crashed-only: the J10 crash convention, exactly.

An episode is a crash ONLY if result.json has error_type == "crash". `limit` (and every
other readable outcome) is scored and must never be purged. Only the named campaign is
touched. Synthetic trees under tmp_path; nothing under /scratch is written.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "campaign_summarize_purge_test",
    Path(__file__).resolve().parents[2] / "scripts" / "setup" / "campaign_summarize.py",
)
cs = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(cs)


def _episode(root: Path, cid: str, task: str, seed: int = 1, *, error_type=None,
             result: str | None = "json", split: str | None = None, system: str = "fixed_k") -> Path:
    ep = root / cid / system / str(seed) / task
    ep.mkdir(parents=True, exist_ok=True)
    (ep / "events.jsonl").write_text('{"event_type": "run_start"}\n', encoding="utf-8")
    if split is not None:
        (ep / "manifest.json").write_text(json.dumps({"provenance": {"split": split}}), encoding="utf-8")
    if result == "json":
        row = {"task_id": task, "seed": seed, "system": system, "error_type": error_type,
               "goal_pass_rate": 0.5, "success": False}
        (ep / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    elif result == "empty":
        (ep / "result.json").write_text("", encoding="utf-8")
    elif result == "truncated":
        (ep / "result.json").write_text('{"task_id": "x", "err', encoding="utf-8")
    return ep


def test_purge_crashed_only_deletes_crashes_and_non_outcomes_and_keeps_every_scored_type(tmp_path: Path):
    cid = "j10_arm_x"
    kept = {
        "none": _episode(tmp_path, cid, "t_none"),
        "limit": _episode(tmp_path, cid, "t_limit", error_type="limit"),
        "timeout": _episode(tmp_path, cid, "t_timeout", error_type="timeout"),
        "parse_error": _episode(tmp_path, cid, "t_parse", error_type="parse_error"),
        "api_error": _episode(tmp_path, cid, "t_api", error_type="api_error"),
    }
    gone = {
        "crash": _episode(tmp_path, cid, "t_crash", error_type="crash"),
        "crash_seed2": _episode(tmp_path, cid, "t_crash", seed=2, error_type="crash"),
        "empty": _episode(tmp_path, cid, "t_empty", result="empty"),
        "truncated": _episode(tmp_path, cid, "t_trunc", result="truncated"),
        "no_result": _episode(tmp_path, cid, "t_killed", result=None),
    }
    counts = cs.purge_crashed(tmp_path, cid)
    assert counts == {"crash": 2, "unreadable_result": 2, "no_result": 1, "kept": 5}
    for ep in kept.values():
        assert (ep / "result.json").exists() and (ep / "events.jsonl").exists()
    for ep in gone.values():
        assert not ep.exists()
    assert (tmp_path / cid).is_dir()  # the campaign root itself survives
    # Idempotent: a second pass finds nothing.
    assert cs.purge_crashed(tmp_path, cid) == {"crash": 0, "unreadable_result": 0, "no_result": 0, "kept": 5}


def test_purge_crashed_only_never_touches_another_campaign(tmp_path: Path):
    mine = _episode(tmp_path, "j10_a", "t1", error_type="crash")
    other = _episode(tmp_path, "j10_a_smoke", "t1", error_type="crash")
    prefix_sibling = _episode(tmp_path, "j10_ab", "t1", error_type="crash")
    cs.purge_crashed(tmp_path, "j10_a")
    assert not mine.exists()
    assert (other / "result.json").exists()
    assert (prefix_sibling / "result.json").exists()


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "../x"])
def test_purge_crashed_only_refuses_unsafe_campaign_ids(tmp_path: Path, bad: str):
    with pytest.raises(ValueError):
        cs.purge_crashed(tmp_path, bad)


def test_purge_crashed_only_on_missing_campaign_is_a_no_op(tmp_path: Path):
    assert cs.purge_crashed(tmp_path, "absent")["kept"] == 0


def test_purge_broken_is_unchanged_and_wider(tmp_path: Path):
    """The existing flag still retries timeout/parse_error/api_error; the new one does not."""
    cid = "c"
    limit = _episode(tmp_path, cid, "t_limit", error_type="limit")
    timeout = _episode(tmp_path, cid, "t_timeout", error_type="timeout")
    assert cs.BROKEN == {"api_error", "timeout", "crash", "parse_error"}
    assert cs.purge_broken(tmp_path, cid) == 1
    assert limit.exists() and not timeout.exists()


def test_cli_flag_and_mutual_exclusion(tmp_path: Path, capsys):
    cid = "c"
    crash = _episode(tmp_path, cid, "t_crash", error_type="crash")
    limit = _episode(tmp_path, cid, "t_limit", error_type="limit")
    rc = cs.main(["--out", str(tmp_path), "--campaign-id", cid, "--purge-crashed-only"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[purge-crashed-only] campaign=c removed crash=1" in out
    assert not crash.exists() and limit.exists()
    with pytest.raises(SystemExit):
        cs.main(["--out", str(tmp_path), "--campaign-id", cid, "--purge-broken", "--purge-crashed-only"])


def test_split_check_overlap_with_dev_is_fatal(tmp_path: Path):
    dev_ids = {"dev_1", "dev_2"}
    _episode(tmp_path, "t", "test_a", split="test_normal")
    assert cs.split_check(tmp_path, "t", "test_normal", dev_ids) == []
    _episode(tmp_path, "t", "dev_1", split="test_normal")
    fails = cs.split_check(tmp_path, "t", "test_normal", dev_ids)
    assert fails and "DEV ids" in fails[0]


def test_split_check_dev_and_recorded_split_disagreement(tmp_path: Path):
    dev_ids = {"dev_1", "dev_2"}
    _episode(tmp_path, "d", "dev_1", split="dev")
    assert cs.split_check(tmp_path, "d", "dev", dev_ids) == []
    _episode(tmp_path, "d", "dev_2", split="test_normal")
    assert any("record split" in f for f in cs.split_check(tmp_path, "d", "dev", dev_ids))
    _episode(tmp_path, "e", "not_dev", split="dev")
    assert any("not dev ids" in f for f in cs.split_check(tmp_path, "e", "dev", dev_ids))
    assert cs.split_check(tmp_path, "empty", "dev", dev_ids)  # nothing to verify is a failure
