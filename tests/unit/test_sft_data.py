"""SFT dataset reconstruction and assistant-token masking."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidekick.protocols.prompts import (
    EXECUTOR_SYSTEM_PROMPT,
    format_executor_action,
    render_executor_messages,
)
from sidekick.protocols.schemas import DelegationPacket, ExecutorAction
from sidekick.training.sft_data import (
    build_sft_dataset,
    tokenize_and_mask,
)


INSTRUCTION = "Copy inbox.txt to outbox.txt"
API_DOCS = "list_files() -> list[str]\nread(name: str) -> str\n"
PACKET = DelegationPacket(
    packet_id="pkt-1",
    task_id="copy_hello",
    goal=INSTRUCTION,
    created_at="2026-09-16T00:00:00+00:00",
)


def _event(
    *,
    event_type: str,
    step: int,
    actor: str,
    payload: dict,
    task_id: str = "copy_hello",
    seed: int = 1,
    run_id: str = "camp/planner_alone/1/copy_hello",
) -> dict:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "system": "planner_alone",
        "seed": seed,
        "step": step,
        "ts": "2023-05-18T12:00:00+00:00",
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
    }


def _code_payload(code: str) -> dict:
    return ExecutorAction(kind="CODE", code=code, raw_output=code).model_dump()


def _write_run(
    root: Path,
    *,
    task_id: str,
    seed: int,
    success: bool,
    events: list[dict],
    commit: str | None = "abc123",
    campaign: str = "camp",
) -> Path:
    run_dir = root / "planner_alone" / str(seed) / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": f"{campaign}/planner_alone/{seed}/{task_id}",
        "task_id": task_id,
        "system": "planner_alone",
        "seed": seed,
        "success": success,
        "tgc": 1.0 if success else 0.0,
        "sgc": None,
        "steps": 2,
        "n_planner_calls": 1,
        "n_asks": 0,
        "n_interventions": 0,
        "error_type": None,
        "totals": {},
        "campaign_id": campaign,
    }
    (run_dir / "result.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
    manifest = {"campaign_id": campaign, "task_id": task_id, "seed": seed}
    if commit:
        manifest["SIDEKICK_START_COMMIT"] = commit
    (run_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")
    return run_dir


def _live_attempt_events(
    task_id: str = "copy_hello",
    *,
    extra: list[dict] | None = None,
    include_ask_ignored: bool = True,
    include_report: bool = True,
) -> list[dict]:
    code1 = "print(read('inbox.txt'))"
    code2 = "print(write('outbox.txt', 'hello world'))"
    events = [
        _event(event_type="run_start", step=0, actor="system", payload={"limits": {}}, task_id=task_id),
        _event(
            event_type="observation",
            step=0,
            actor="environment",
            payload={"text": INSTRUCTION, "done": False},
            task_id=task_id,
        ),
        _event(
            event_type="plan",
            step=0,
            actor="planner",
            payload={"packet": PACKET.model_dump(), "api_docs_prompt": API_DOCS},
            task_id=task_id,
        ),
        _event(
            event_type="action",
            step=1,
            actor="planner",
            payload=_code_payload(code1),
            task_id=task_id,
        ),
        _event(
            event_type="observation",
            step=1,
            actor="environment",
            payload={"text": "hello world", "done": False, "kind": "CODE"},
            task_id=task_id,
        ),
    ]
    if include_report:
        events.extend(
            [
                _event(
                    event_type="action",
                    step=2,
                    actor="planner",
                    payload=ExecutorAction(
                        kind="REPORT", message="copied", raw_output="REPORT: copied"
                    ).model_dump(),
                    task_id=task_id,
                ),
                _event(
                    event_type="report",
                    step=2,
                    actor="executor",
                    payload={"message": "copied"},
                    task_id=task_id,
                ),
            ]
        )
    if include_ask_ignored:
        events.extend(
            [
                _event(
                    event_type="action",
                    step=3,
                    actor="planner",
                    payload=ExecutorAction(
                        kind="ASK_PLANNER",
                        ask_reason="which file?",
                        raw_output="ASK_PLANNER: which file?",
                    ).model_dump(),
                    task_id=task_id,
                ),
                _event(
                    event_type="ask",
                    step=3,
                    actor="executor",
                    payload={"ask_reason": "which file?", "gated": False, "honoured": False},
                    task_id=task_id,
                ),
            ]
        )
    events.extend(
        [
            _event(
                event_type="action",
                step=4,
                actor="planner",
                payload=_code_payload(code2),
                task_id=task_id,
            ),
            _event(
                event_type="observation",
                step=4,
                actor="environment",
                payload={"text": "ok", "done": False, "kind": "CODE"},
                task_id=task_id,
            ),
            _event(
                event_type="action",
                step=5,
                actor="planner",
                payload=ExecutorAction(kind="COMPLETE", raw_output="COMPLETE").model_dump(),
                task_id=task_id,
            ),
            _event(
                event_type="observation",
                step=5,
                actor="environment",
                payload={"text": "COMPLETE", "done": True, "kind": "COMPLETE"},
                task_id=task_id,
            ),
        ]
    )
    if extra:
        events.extend(extra)
    return events


def _dead_attempt_events(task_id: str = "copy_hello") -> list[dict]:
    poison = "print(delete_all())"
    return [
        _event(event_type="run_start", step=0, actor="system", payload={"limits": {}}, task_id=task_id),
        _event(
            event_type="observation",
            step=0,
            actor="environment",
            payload={"text": "DEAD_INSTRUCTION", "done": False},
            task_id=task_id,
        ),
        _event(
            event_type="action",
            step=1,
            actor="planner",
            payload=_code_payload(poison),
            task_id=task_id,
        ),
        _event(
            event_type="observation",
            step=1,
            actor="environment",
            payload={"text": "wiped", "done": False},
            task_id=task_id,
        ),
        _event(
            event_type="error",
            step=1,
            actor="system",
            payload={"detail": "crash"},
            task_id=task_id,
        ),
    ]


@pytest.fixture
def no_heldout(monkeypatch):
    monkeypatch.setattr("sidekick.training.sft_data._heldout_task_ids", lambda: ["held_out_task"])
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda: None)
    monkeypatch.setattr("sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "")


def test_jsonl_line_is_renderer_messages_plus_meta(tmp_path, no_heldout):
    root = tmp_path / "camp"
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=_live_attempt_events())
    out = tmp_path / "sft.jsonl"
    summary = build_sft_dataset(root, ["copy_hello"], out, system="planner_alone")
    assert summary["n_trajectories"] == 1
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert set(line) == {"messages", "meta"}
    meta = line["meta"]
    for key in ("task_id", "seed", "run_id", "n_turns", "source_campaign", "SIDEKICK_START_COMMIT"):
        assert key in meta
    assert meta["task_id"] == "copy_hello"
    assert meta["seed"] == 1
    assert meta["SIDEKICK_START_COMMIT"] == "abc123"
    messages = line["messages"]
    history = [
        {"role": "assistant", "content": format_executor_action(ExecutorAction(kind="CODE", code="print(read('inbox.txt'))", raw_output=""))},
        {"role": "user", "content": "OBS: hello world"},
        {"role": "assistant", "content": format_executor_action(ExecutorAction(kind="REPORT", message="copied", raw_output=""))},
        {"role": "assistant", "content": format_executor_action(ExecutorAction(kind="ASK_PLANNER", ask_reason="which file?", raw_output=""))},
        {"role": "user", "content": "ASK_IGNORED"},
        {"role": "assistant", "content": format_executor_action(ExecutorAction(kind="CODE", code="print(write('outbox.txt', 'hello world'))", raw_output=""))},
        {"role": "user", "content": "OBS: ok"},
        {"role": "assistant", "content": format_executor_action(ExecutorAction(kind="COMPLETE", raw_output=""))},
        {"role": "user", "content": "OBS: COMPLETE"},
    ]
    expected = render_executor_messages(
        instruction=INSTRUCTION,
        api_docs=API_DOCS,
        packet=PACKET,
        history=history,
    )
    assert messages == expected
    assert messages[0] == {"role": "system", "content": EXECUTOR_SYSTEM_PROMPT}
    assert messages[1]["content"].startswith(f"Task: {INSTRUCTION}\n")
    assert API_DOCS in messages[1]["content"]
    assert f"Plan: {PACKET.model_dump_json()}\n" in messages[1]["content"]
    manifest = json.loads((Path(str(out) + ".manifest.json")).read_text(encoding="utf-8"))
    assert manifest["sha256"]
    assert "p50" in manifest["token_length_percentiles"]
    assert "dropped_counts" in manifest
    assert manifest["n_truncated"] == 0
    assert manifest["n_messages_dropped_total"] == 0
    assert manifest["n_unrepresentable"] == 0
    assert manifest["truncated_run_ids"] == []


def test_only_events_after_last_run_start(tmp_path, no_heldout):
    root = tmp_path / "camp"
    events = _dead_attempt_events() + _live_attempt_events()
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=events)
    out = tmp_path / "sft.jsonl"
    build_sft_dataset(root, ["copy_hello"], out)
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    blob = json.dumps(line["messages"])
    assert "delete_all" not in blob
    assert "DEAD_INSTRUCTION" not in blob
    assert "print(read('inbox.txt'))" in blob


def test_file_order_not_timestamp(tmp_path, no_heldout):
    root = tmp_path / "camp"
    # Every event shares the freezegun timestamp; order must follow the file.
    events = _live_attempt_events()
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=events)
    out = tmp_path / "sft.jsonl"
    build_sft_dataset(root, ["copy_hello"], out)
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    joined = "\n".join(m["content"] for m in line["messages"] if m["role"] == "assistant")
    assert joined.index("print(read('inbox.txt'))") < joined.index("print(write('outbox.txt'")


def test_solved_only_skips_failures(tmp_path, no_heldout):
    root = tmp_path / "camp"
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=_live_attempt_events())
    _write_run(root, task_id="copy_fail", seed=1, success=False, events=_live_attempt_events("copy_fail"))
    out = tmp_path / "sft.jsonl"
    summary = build_sft_dataset(root, ["copy_hello", "copy_fail"], out, solved_only=True)
    assert summary["n_trajectories"] == 1
    assert summary["dropped_counts"]["unsolved"] == 1
    line = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert line["meta"]["task_id"] == "copy_hello"


def test_no_solved_only_keeps_failures(tmp_path, no_heldout):
    root = tmp_path / "camp"
    _write_run(root, task_id="copy_fail", seed=1, success=False, events=_live_attempt_events("copy_fail"))
    out = tmp_path / "sft.jsonl"
    summary = build_sft_dataset(root, ["copy_fail"], out, solved_only=False)
    assert summary["n_trajectories"] == 1


def test_not_in_split_is_dropped(tmp_path, no_heldout):
    root = tmp_path / "camp"
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=_live_attempt_events())
    out = tmp_path / "sft.jsonl"
    summary = build_sft_dataset(root, ["other_task"], out)
    assert summary["n_trajectories"] == 0
    assert summary["dropped_counts"]["not_in_split"] == 1


def test_leakage_raises_unconditionally(tmp_path, monkeypatch):
    monkeypatch.setattr("sidekick.training.sft_data._heldout_task_ids", lambda: ["copy_hello"])
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda: None)
    monkeypatch.setattr("sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "")
    root = tmp_path / "camp"
    _write_run(root, task_id="copy_hello", seed=1, success=True, events=_live_attempt_events())
    with pytest.raises(ValueError, match="copy_hello"):
        build_sft_dataset(root, ["copy_hello"], tmp_path / "sft.jsonl")


class CharChatTokenizer:
    """Character-level tokenizer whose chat template preserves the prefix property."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages)
        if tokenize:
            return self.encode(text)
        return text

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) for ch in text]


def test_masking_unmasked_positions_are_exactly_assistant_spans():
    # 3-turn example: system, user, assistant. Unmasked labels must be exactly
    # the tokens of the assistant turn, including that turn's role markers.
    messages = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "A"},
    ]
    tok = CharChatTokenizer()
    out = tokenize_and_mask(messages, tok, max_length=None)
    prefix = tok.apply_chat_template(messages[:2], tokenize=False)
    full = tok.apply_chat_template(messages, tokenize=False)
    assert full.startswith(prefix)
    prefix_ids = tok.encode(prefix)
    full_ids = tok.encode(full)
    assistant_ids = full_ids[len(prefix_ids) :]
    assert out["input_ids"] == full_ids
    assert out["n_messages_dropped"] == 0
    assert out["truncated"] is False
    assert out["representable"] is True
    assert out["labels"][: len(prefix_ids)] == [-100] * len(prefix_ids)
    assert out["labels"][len(prefix_ids) :] == assistant_ids
    assert assistant_ids == tok.encode("<assistant>A</assistant>")
    assert all(lab == -100 or lab == iid for lab, iid in zip(out["labels"], out["input_ids"]))
    assert any(lab != -100 for lab in out["labels"])
    # user/system content characters must stay masked
    for ch in "SU":
        idx = full.index(ch)
        assert out["labels"][idx] == -100
    assert out["labels"][full.index("A")] == ord("A")


def test_truncation_keeps_terminal_action_supervised_and_drops_whole_messages():
    messages = [
        {"role": "system", "content": "SYSTEM framing"},
        {"role": "user", "content": "TASK framing"},
        {"role": "assistant", "content": "old action"},
        {"role": "user", "content": "old observation"},
        {"role": "assistant", "content": "recent action"},
        {"role": "user", "content": "recent observation"},
        {"role": "assistant", "content": "FINAL COMPLETE"},
    ]
    tok = CharChatTokenizer()
    retained = messages[:2] + messages[4:]
    retained_ids = tok.encode(tok.apply_chat_template(retained, tokenize=False))

    out = tokenize_and_mask(messages, tok, max_length=len(retained_ids))

    assert out["truncated"] is True
    assert out["representable"] is True
    assert out["n_messages_dropped"] == 2
    # The output equals a complete rendering of the retained messages: neither a
    # partial old message nor a right-truncated terminal action can be present.
    assert out["input_ids"] == retained_ids
    rendered = "".join(chr(token) for token in out["input_ids"])
    assert "old action" not in rendered
    assert "FINAL COMPLETE" in rendered

    expected_labels = []
    previous_ids = []
    for message_index, message in enumerate(retained):
        current_ids = tok.encode(
            tok.apply_chat_template(retained[: message_index + 1], tokenize=False)
        )
        span = current_ids[len(previous_ids) :]
        expected_labels.extend(span if message["role"] == "assistant" else [-100] * len(span))
        previous_ids = current_ids
    assert out["labels"] == expected_labels

    final_prefix = tok.encode(tok.apply_chat_template(retained[:-1], tokenize=False))
    final_ids = retained_ids[len(final_prefix) :]
    assert final_ids
    assert out["labels"][-len(final_ids) :] == final_ids


def test_unrepresentable_example_is_not_silently_cut():
    messages = [
        {"role": "system", "content": "long system"},
        {"role": "user", "content": "long task"},
        {"role": "assistant", "content": "FINAL"},
    ]
    tok = CharChatTokenizer()
    full_ids = tok.encode(tok.apply_chat_template(messages, tokenize=False))

    out = tokenize_and_mask(messages, tok, max_length=1)

    assert out["representable"] is False
    assert out["truncated"] is False
    assert out["n_messages_dropped"] == 0
    assert out["input_ids"] == full_ids
