"""Suffix-handoff SFT: prefix tokens masked, suffix assistant tokens labelled."""
from __future__ import annotations

import json
from pathlib import Path

from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction
from sidekick.training.handoff_sft import (
    DROP_TOO_SHORT,
    _suffix_target_indices,
    build_handoff_dataset,
    row_from_events,
)
from sidekick.training.sft_data import tokenize_sft_row

INSTRUCTION = "Copy inbox.txt to outbox.txt"
API_DOCS = "list_files() -> list[str]\nread(name: str) -> str\n"
PACKET = DelegationPacket(
    packet_id="pkt-handoff-1",
    task_id="copy_hello",
    goal=INSTRUCTION,
    created_at="2026-09-16T00:00:00+00:00",
)
CODES = (
    "print(list_files())",
    "print(read('inbox.txt'))",
    "print(write('outbox.txt', 'hello world'))",
    "COMPLETE",
)


class CharChatTokenizer:
    """Character-level tokenizer whose chat template preserves the prefix property."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages)
        if tokenize:
            return self.encode(text)
        return text

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) for ch in text]


def _ev(*, step: int, event_type: str, actor: str, payload: dict) -> Event:
    return Event(
        run_id="camp/planner_alone/1/copy_hello",
        task_id="copy_hello",
        system="planner_alone",
        seed=1,
        step=step,
        ts="2023-05-18T12:00:00+00:00",
        actor=actor,  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        payload=payload,
    )


def _four_action_events() -> list[Event]:
    """Four executed planner actions (3 CODE + COMPLETE). Cut m=2 leaves a suffix."""
    events = [
        _ev(step=0, event_type="run_start", actor="system", payload={"limits": {}}),
        _ev(
            step=0,
            event_type="observation",
            actor="environment",
            payload={"text": INSTRUCTION, "done": False},
        ),
        _ev(
            step=0,
            event_type="plan",
            actor="planner",
            payload={"packet": PACKET.model_dump()},
        ),
    ]
    for i, code in enumerate(CODES[:3], start=1):
        action = ExecutorAction(kind="CODE", code=code, raw_output=code)
        events.append(
            _ev(step=i, event_type="action", actor="planner", payload=action.model_dump())
        )
        events.append(
            _ev(
                step=i,
                event_type="observation",
                actor="environment",
                payload={"text": f"OBS{i}", "done": False},
            )
        )
    complete = ExecutorAction(kind="COMPLETE", raw_output="COMPLETE")
    events.append(_ev(step=4, event_type="action", actor="planner", payload=complete.model_dump()))
    events.append(
        _ev(
            step=4,
            event_type="observation",
            actor="environment",
            payload={"text": "done", "done": True},
        )
    )
    return events


def _events_with_non_executed_prefix_action() -> list[Event]:
    """Five actions: 4 executed CODE/COMPLETE, 1 non-executed CODE in prefix.

    Action 1 (non-executed) is immediately followed by Action 2 without an intervening
    observation, flushing an assistant turn for Action 1 while _n_executed_actions
    counts only 4 executed actions.
    """
    events = [
        _ev(step=0, event_type="run_start", actor="system", payload={"limits": {}}),
        _ev(
            step=0,
            event_type="observation",
            actor="environment",
            payload={"text": INSTRUCTION, "done": False},
        ),
        _ev(
            step=0,
            event_type="plan",
            actor="planner",
            payload={"packet": PACKET.model_dump()},
        ),
    ]
    # Non-executed action: immediately followed by next action (no observation)
    non_exec_action = ExecutorAction(
        kind="CODE",
        code="print('non_executed_action()')",
        raw_output="print('non_executed_action()')",
    )
    events.append(
        _ev(step=1, event_type="action", actor="planner", payload=non_exec_action.model_dump())
    )

    # 3 executed CODE actions
    for i, code in enumerate(CODES[:3], start=1):
        action = ExecutorAction(kind="CODE", code=code, raw_output=code)
        events.append(
            _ev(step=i, event_type="action", actor="planner", payload=action.model_dump())
        )
        events.append(
            _ev(
                step=i,
                event_type="observation",
                actor="environment",
                payload={"text": f"OBS{i}", "done": False},
            )
        )
    # 1 executed COMPLETE action
    complete = ExecutorAction(kind="COMPLETE", raw_output="COMPLETE")
    events.append(_ev(step=4, event_type="action", actor="planner", payload=complete.model_dump()))
    events.append(
        _ev(
            step=4,
            event_type="observation",
            actor="environment",
            payload={"text": "done", "done": True},
        )
    )
    return events


def _labels_from_template(messages: list[dict], targets: set[int], tok: CharChatTokenizer) -> list[int]:
    expected: list[int] = []
    prev: list[int] = []
    for i, _msg in enumerate(messages):
        curr = tok.encode(tok.apply_chat_template(messages[: i + 1], tokenize=False))
        span = curr[len(prev) :]
        if i in targets:
            expected.extend(span)
        else:
            expected.extend([-100] * len(span))
        prev = curr
    return expected


def test_cut_m2_masks_exact_prefix_token_positions(monkeypatch) -> None:
    """Known 4-action trajectory, cut m=2: prefix tokens are -100, suffix ids are real.

    Asserts the exact position sets, not counts.
    """
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: API_DOCS
    )
    events = _four_action_events()
    row, reason, extras = row_from_events(events, m=2)
    assert reason is None
    assert extras["n_source_actions"] == 4
    assert extras["n_prefix_assistant_turns"] == 2
    assert row["meta"]["n_prefix_assistant_turns"] == 2
    messages = row["messages"]
    targets = set(row["meta"]["supervised_message_indices"])
    assistant_idx = [i for i, msg in enumerate(messages) if msg.get("role") == "assistant"]
    assert len(assistant_idx) == 4
    assert assistant_idx[:2]  # prefix assistants exist
    assert set(assistant_idx[:2]).isdisjoint(targets)
    assert set(assistant_idx[2:]) == targets

    tok = CharChatTokenizer()
    masked = tokenize_sft_row(row, tok, max_length=None)
    expected = _labels_from_template(messages, targets, tok)
    assert masked["labels"] == expected
    masked_pos = [i for i, lab in enumerate(masked["labels"]) if lab == -100]
    live_pos = [i for i, lab in enumerate(masked["labels"]) if lab != -100]
    expected_masked = [i for i, lab in enumerate(expected) if lab == -100]
    expected_live = [i for i, lab in enumerate(expected) if lab != -100]
    assert masked_pos == expected_masked
    assert live_pos == expected_live
    assert live_pos, "suffix must carry real ids"
    assert masked_pos, "prefix must carry -100"

    prev: list[int] = []
    for i, msg in enumerate(messages):
        curr = tok.encode(tok.apply_chat_template(messages[: i + 1], tokenize=False))
        span_labels = masked["labels"][len(prev) : len(curr)]
        span_ids = masked["input_ids"][len(prev) : len(curr)]
        if msg.get("role") != "assistant" or i not in targets:
            assert span_labels == [-100] * len(span_ids)
        else:
            assert span_labels == span_ids
            assert -100 not in span_labels
        prev = curr


def test_cut_with_non_executed_prefix_action_aligns_to_executed_actions(monkeypatch) -> None:
    """Prefix contains a non-executed action flushed to assistant turn.

    Asserts:
    1. Supervised target indices match executed-action cut, differing from assistant-message cut.
    2. Prefix assistant turns (including non-executed one) are masked with -100, suffix assistant
       turns match input_ids exactly on token positions.
    3. Trajectory with executed actions <= m is dropped too_short.
    """
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: API_DOCS
    )
    events = _events_with_non_executed_prefix_action()
    row, reason, extras = row_from_events(events, m=2)
    assert reason is None
    assert extras["n_source_actions"] == 4
    assert extras["cut_m"] == 2
    # 2 executed actions require skipping 3 assistant turns (1 non-executed + 2 executed)
    assert extras["n_prefix_assistant_turns"] == 3
    assert row["meta"]["cut_m"] == 2
    assert row["meta"]["n_prefix_assistant_turns"] == 3
    assert row["meta"]["n_source_actions"] == 4

    messages = row["messages"]
    targets = row["meta"]["supervised_message_indices"]
    assistant_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "assistant"]
    assert len(assistant_indices) == 5

    # Executed-action cut targets assistant turns after the 2nd executed action (i.e. assistant turns 4 and 5)
    expected_targets = assistant_indices[3:]
    assert targets == expected_targets

    # Old assistant-message cut would have cut after the 2nd assistant message (assistant turns 3, 4, 5)
    old_asst_targets = _suffix_target_indices(messages, m=2)
    assert old_asst_targets == assistant_indices[2:]
    assert targets != old_asst_targets, "executed-action cut must differ from assistant-message cut"

    # Token position masking check
    tok = CharChatTokenizer()
    masked = tokenize_sft_row(row, tok, max_length=None)
    expected = _labels_from_template(messages, set(targets), tok)
    assert masked["labels"] == expected

    masked_pos = [i for i, lab in enumerate(masked["labels"]) if lab == -100]
    live_pos = [i for i, lab in enumerate(masked["labels"]) if lab != -100]
    expected_masked = [i for i, lab in enumerate(expected) if lab == -100]
    expected_live = [i for i, lab in enumerate(expected) if lab != -100]
    assert masked_pos == expected_masked
    assert live_pos == expected_live
    assert live_pos, "suffix must carry real ids"
    assert masked_pos, "prefix must carry -100"

    prev: list[int] = []
    for i, msg in enumerate(messages):
        curr = tok.encode(tok.apply_chat_template(messages[: i + 1], tokenize=False))
        span_labels = masked["labels"][len(prev) : len(curr)]
        span_ids = masked["input_ids"][len(prev) : len(curr)]
        if msg.get("role") != "assistant" or i not in targets:
            assert span_labels == [-100] * len(span_ids)
        else:
            assert span_labels == span_ids
            assert -100 not in span_labels
        prev = curr

    # Drop gate on executed actions: m=4 with 4 executed actions is dropped too_short
    row_drop, reason_drop, extras_drop = row_from_events(events, m=4)
    assert row_drop is None
    assert reason_drop == DROP_TOO_SHORT
    assert extras_drop["n_source_actions"] == 4
    assert extras_drop["cut_m"] == 4


def test_episode_with_le_m_actions_is_dropped(monkeypatch) -> None:
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: API_DOCS
    )
    events = _four_action_events()
    row, reason, extras = row_from_events(events, m=4)
    assert row is None
    assert reason == DROP_TOO_SHORT
    assert extras["n_source_actions"] == 4


def _write_planner_run(root: Path, *, task_id: str, seed: int, events: list[Event]) -> None:
    dest = root / "planner_alone" / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": f"camp/planner_alone/{seed}/{task_id}",
        "task_id": task_id,
        "system": "planner_alone",
        "seed": seed,
        "success": True,
        "campaign_id": "camp",
    }
    (dest / "result.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
    (dest / "events.jsonl").write_text(
        "".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8"
    )


def test_builder_records_too_short_drops_per_m(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: API_DOCS
    )
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda *_a, **_k: None)
    camp = tmp_path / "camp"
    _write_planner_run(camp, task_id="copy_hello", seed=1, events=_four_action_events())
    out = tmp_path / "handoff.jsonl"
    summary = build_handoff_dataset(camp, out, cuts=(2, 4, 6), quiet=True)
    assert summary["rows_per_m"]["2"] == 1
    assert summary["rows_per_m"]["4"] == 0
    assert summary["rows_per_m"]["6"] == 0
    assert summary["dropped_too_short_per_m"]["2"] == 0
    assert summary["dropped_too_short_per_m"]["4"] == 1
    assert summary["dropped_too_short_per_m"]["6"] == 1
    assert summary["n_source_episodes"] == 1
    assert summary["n_rows_cut_offset"] == 0
    assert summary["n_prefix_assistant_turns"] == 2
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["meta"]["cut_m"] == 2
    assert rec["meta"]["n_prefix_assistant_turns"] == 2
    assert "HANDOFF:" not in json.dumps(rec)


def test_builder_records_cut_offset_when_non_executed_actions_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: API_DOCS
    )
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda *_a, **_k: None)
    camp = tmp_path / "camp"
    _write_planner_run(
        camp,
        task_id="copy_hello",
        seed=1,
        events=_events_with_non_executed_prefix_action(),
    )
    out = tmp_path / "handoff_offset.jsonl"
    summary = build_handoff_dataset(camp, out, cuts=(2, 4, 6), quiet=True)
    assert summary["rows_per_m"]["2"] == 1
    assert summary["rows_per_m"]["4"] == 0
    assert summary["rows_per_m"]["6"] == 0
    assert summary["n_rows_cut_offset"] == 1
    assert summary["n_prefix_assistant_turns"] == 3
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["meta"]["cut_m"] == 2
    assert rec["meta"]["n_prefix_assistant_turns"] == 3
