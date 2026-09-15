import pytest

from sidekick.protocols.schemas import (
    ActionParseError,
    Event,
    ExecutorAction,
    utc_now_iso,
)
from sidekick.trajectories.eventlog import EventLog


def make_event(step=0, event_type="action", **kw):
    base = dict(run_id="run1", task_id="t1", system="sidekick", seed=42, step=step,
                ts=utc_now_iso(), actor="executor", event_type=event_type)
    base.update(kw)
    return Event(**base)


def tmp_log(tmp_path):
    return EventLog(tmp_path, "run1")


def test_creates_directory_and_file(tmp_path):
    log = tmp_log(tmp_path)
    try:
        assert (tmp_path / "run1").is_dir()
        assert (tmp_path / "run1" / "events.jsonl").exists()
    finally:
        log.close()


def test_round_trip_single_event(tmp_path):
    with tmp_log(tmp_path) as log:
        log.append(make_event(payload={"k": "v"}))
    events = list(EventLog.read(tmp_path / "run1" / "events.jsonl"))
    assert len(events) == 1
    assert events[0].payload["k"] == "v"
    assert events[0].run_id == "run1" and events[0].seed == 42


def test_round_trip_many_events_ordered(tmp_path):
    with tmp_log(tmp_path) as log:
        for i in range(5):
            log.append(make_event(step=i))
    events = list(EventLog.read(tmp_path / "run1" / "events.jsonl"))
    assert [e.step for e in events] == [0, 1, 2, 3, 4]


def test_append_mode_preserves_existing_lines(tmp_path):
    log = EventLog(tmp_path, "run1")
    log.append(make_event(step=1))
    log.close()
    log2 = EventLog(tmp_path, "run1")
    log2.append(make_event(step=2))
    log2.close()
    events = list(EventLog.read(tmp_path / "run1" / "events.jsonl"))
    assert [e.step for e in events] == [1, 2]


def test_flushed_immediately(tmp_path):
    log = tmp_log(tmp_path)
    log.append(make_event())
    events = list(EventLog.read(tmp_path / "run1" / "events.jsonl"))
    assert len(events) == 1
    log.close()


def test_usage_round_trips_through_log(tmp_path):
    from sidekick.protocols.schemas import Usage

    with tmp_log(tmp_path) as log:
        log.append(make_event(usage=Usage(model="m", provider="codex", input_tokens=10, n_calls=3)))
    e = list(EventLog.read(tmp_path / "run1" / "events.jsonl"))[0]
    assert e.usage.input_tokens == 10 and e.usage.n_calls == 3


def test_truncated_last_line_skipped(tmp_path):
    with tmp_log(tmp_path) as log:
        log.append(make_event(step=1))
        log.append(make_event(step=2))
    path = tmp_path / "run1" / "events.jsonl"
    raw = path.read_text()
    path.write_text(raw[: len(raw) - 10])
    events = list(EventLog.read(path))
    assert len(events) == 1
    assert events[0].step == 1


def test_truncated_only_line_yields_nothing(tmp_path):
    with tmp_log(tmp_path) as log:
        log.append(make_event(step=1))
    path = tmp_path / "run1" / "events.jsonl"
    raw = path.read_text()
    path.write_text(raw[:20])
    assert list(EventLog.read(path)) == []


def test_read_is_iterator_of_events(tmp_path):
    with tmp_log(tmp_path) as log:
        log.append(make_event())
    it = EventLog.read(tmp_path / "run1" / "events.jsonl")
    assert isinstance(next(it), Event)
    it.close()


# ---------- manifest ----------

def test_manifest_contents(tmp_path):
    with tmp_log(tmp_path) as log:
        log.write_manifest({"system": "sidekick", "seed": 1})
    import json

    m = json.loads((tmp_path / "run1" / "manifest.json").read_text())
    assert m["system"] == "sidekick" and m["seed"] == 1
    assert m["run_id"] == "run1"
    assert "created_at" in m and "hostname" in m and "pid" in m
    assert "python_version" in m and m["schema_version"] == 1
    text = (tmp_path / "run1" / "manifest.json").read_text()
    assert text.strip().startswith("{") and "\n  " in text


def test_manifest_caller_values_win(tmp_path):
    with tmp_log(tmp_path) as log:
        log.write_manifest({"run_id": "explicit", "created_at": "fixed"})
    import json

    m = json.loads((tmp_path / "run1" / "manifest.json").read_text())
    assert m["run_id"] == "explicit" and m["created_at"] == "fixed"
