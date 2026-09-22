"""Correction-SFT (sft_b_plus) dataset: DAgger targets, no INTERVENTION crutch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sidekick.protocols.prompts import format_executor_action
from sidekick.protocols.schemas import DelegationPacket, ExecutorAction, parse_executor_action
from sidekick.training import assert_no_leakage
from sidekick.training.sft_data import (
    DROP_ASK_PLANNER_TARGET,
    build_correction_dataset,
    build_sft_b_plus,
    remask_to_message_index,
    remask_to_message_indices,
)


INSTRUCTION = "Copy inbox.txt to outbox.txt"
API_DOCS = "list_files() -> list[str]\nread(name: str) -> str\n"
PACKET = DelegationPacket(
    packet_id="pkt-1",
    task_id="copy_hello",
    goal=INSTRUCTION,
    created_at="2026-09-16T00:00:00+00:00",
)
CODE_BEFORE = "print(read('inbox.txt'))"
CODE_AFTER = "print(write('outbox.txt', 'hello world'))"
CODE_AFTER_2 = "print(write('outbox.txt', 'corrected twice'))"
J4_ARCHIVE = Path.home() / "sidekick_data" / "hj4_correction_train_20260917"


def _event(
    *,
    event_type: str,
    step: int,
    actor: str,
    payload: dict,
    task_id: str = "copy_hello",
    seed: int = 1,
    run_id: str = "j4/fixed_k/1/copy_hello",
    system: str = "fixed_k",
) -> dict:
    return {
        "run_id": run_id,
        "task_id": task_id,
        "system": system,
        "seed": seed,
        "step": step,
        "ts": "2023-05-18T12:00:00+00:00",
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
    }


def _code_payload(code: str) -> dict:
    return ExecutorAction(kind="CODE", code=code, raw_output=code).model_dump()


def _write_fixed_k_run(
    root: Path,
    *,
    task_id: str,
    seed: int,
    events: list[dict],
    success: bool = True,
    commit: str | None = "abc123",
    campaign: str = "j4",
) -> Path:
    run_dir = root / "fixed_k" / str(seed) / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": f"{campaign}/fixed_k/{seed}/{task_id}",
        "task_id": task_id,
        "system": "fixed_k",
        "seed": seed,
        "success": success,
        "tgc": 1.0 if success else 0.0,
        "sgc": None,
        "steps": 2,
        "n_planner_calls": 1,
        "n_asks": 0,
        "n_interventions": sum(1 for e in events if e.get("event_type") == "intervention"),
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


def _intervention_payload(correction: str, n: int = 1) -> dict:
    return {"correction": correction, "forced": True, "n_interventions": n}


def _j4_style_events(
    task_id: str = "copy_hello",
    *,
    n_interventions: int = 1,
    post_kinds: list[str] | None = None,
) -> list[dict]:
    """run_start, observation, plan, (action, observation)* with timer interventions.

    Matches J4 order: action, observation, INTERVENTION, action.
    """
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
            actor="executor",
            payload=_code_payload(CODE_BEFORE),
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
    kinds = post_kinds or ["CODE"] * n_interventions
    after_codes = [CODE_AFTER, CODE_AFTER_2]
    step = 2
    for i in range(n_interventions):
        events.append(
            _event(
                event_type="intervention",
                step=step,
                actor="planner",
                payload=_intervention_payload(f"do the write step {i}", n=i + 1),
                task_id=task_id,
            )
        )
        kind = kinds[i] if i < len(kinds) else "CODE"
        if kind == "ASK_PLANNER":
            payload = ExecutorAction(
                kind="ASK_PLANNER",
                ask_reason="which file?",
                raw_output="ASK_PLANNER: which file?",
            ).model_dump()
        else:
            payload = _code_payload(after_codes[i] if i < len(after_codes) else f"print({i})")
        events.append(
            _event(event_type="action", step=step, actor="executor", payload=payload, task_id=task_id)
        )
        events.append(
            _event(
                event_type="observation",
                step=step,
                actor="environment",
                payload={"text": f"obs-{i}", "done": False, "kind": kind},
                task_id=task_id,
            )
        )
        step += 1
    events.extend(
        [
            _event(
                event_type="action",
                step=step,
                actor="executor",
                payload=ExecutorAction(kind="COMPLETE", raw_output="COMPLETE").model_dump(),
                task_id=task_id,
            ),
            _event(
                event_type="observation",
                step=step,
                actor="environment",
                payload={"text": "COMPLETE", "done": True, "kind": "COMPLETE"},
                task_id=task_id,
            ),
        ]
    )
    return events


def _write_teacher_run(root: Path, task_id: str = "copy_hello") -> None:
    run_dir = root / "planner_alone" / "1" / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    events = [
        _event(
            event_type="run_start",
            step=0,
            actor="system",
            payload={},
            task_id=task_id,
            system="planner_alone",
            run_id=f"j3/planner_alone/1/{task_id}",
        ),
        _event(
            event_type="observation",
            step=0,
            actor="environment",
            payload={"text": INSTRUCTION, "done": False},
            task_id=task_id,
            system="planner_alone",
        ),
        _event(
            event_type="plan",
            step=0,
            actor="planner",
            payload={"packet": PACKET.model_dump(), "api_docs_prompt": API_DOCS},
            task_id=task_id,
            system="planner_alone",
        ),
        _event(
            event_type="action",
            step=1,
            actor="planner",
            payload=_code_payload(CODE_BEFORE),
            task_id=task_id,
            system="planner_alone",
        ),
        _event(
            event_type="observation",
            step=1,
            actor="environment",
            payload={"text": "hello world", "done": False, "kind": "CODE"},
            task_id=task_id,
            system="planner_alone",
        ),
        _event(
            event_type="action",
            step=2,
            actor="planner",
            payload=ExecutorAction(kind="COMPLETE", raw_output="COMPLETE").model_dump(),
            task_id=task_id,
            system="planner_alone",
        ),
        _event(
            event_type="observation",
            step=2,
            actor="environment",
            payload={"text": "COMPLETE", "done": True, "kind": "COMPLETE"},
            task_id=task_id,
            system="planner_alone",
        ),
    ]
    result = {
        "run_id": f"j3/planner_alone/1/{task_id}",
        "task_id": task_id,
        "system": "planner_alone",
        "seed": 1,
        "success": True,
        "campaign_id": "j3",
        "SIDEKICK_START_COMMIT": "abc123",
    }
    (run_dir / "result.json").write_text(json.dumps(result) + "\n", encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"SIDEKICK_START_COMMIT": "abc123"}) + "\n", encoding="utf-8"
    )
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


@pytest.fixture
def no_heldout(monkeypatch):
    monkeypatch.setattr("sidekick.training.sft_data._heldout_task_ids", lambda: ["held_out_task"])
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda *_a, **_k: None)
    monkeypatch.setattr("sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "")


class CharChatTokenizer:
    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages)
        if tokenize:
            return self.encode(text)
        return text

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) for ch in text]


def _load_runs(out: Path) -> list[dict]:
    return [json.loads(ln) for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_one_intervention_one_post_action_target(tmp_path, no_heldout):
    root = tmp_path / "j4"
    _write_fixed_k_run(root, task_id="copy_hello", seed=1, events=_j4_style_events())
    out = tmp_path / "corr.jsonl"
    summary = build_correction_dataset(root, ["copy_hello"], out)
    assert summary["n_sequences"] == 1
    assert summary["n_ask_planner_targets"] == 0
    line = _load_runs(out)[0]
    assistants = [m for m in line["messages"] if m["role"] == "assistant"]
    assert len(assistants) >= 2
    assert CODE_BEFORE in assistants[0]["content"]
    assert parse_executor_action(assistants[-1]["content"]).kind == "CODE"
    assert CODE_AFTER in assistants[-1]["content"]
    assert CODE_AFTER in format_executor_action(
        ExecutorAction(kind="CODE", code=CODE_AFTER, raw_output="")
    )
    assert line["messages"][-1]["role"] == "assistant"
    assert line["meta"]["source"] == "correction"
    assert line["meta"]["supervise_last_assistant_only"] is True
    assert line["meta"]["supervised_message_indices"] == [
        line["meta"]["supervised_message_index"]
    ]
    assert line["meta"]["n_action_targets"] == 1


def test_no_emitted_example_contains_intervention_mark(tmp_path, no_heldout):
    root = tmp_path / "j4"
    _write_fixed_k_run(
        root,
        task_id="copy_hello",
        seed=1,
        events=_j4_style_events(n_interventions=2),
    )
    out = tmp_path / "corr.jsonl"
    summary = build_correction_dataset(root, ["copy_hello"], out)
    assert summary["n_sequences"] == 1
    line = _load_runs(out)[0]
    assert line["meta"]["n_action_targets"] == 2
    assert len(line["meta"]["supervised_message_indices"]) == 2
    for line in _load_runs(out):
        for msg in line["messages"]:
            assert "INTERVENTION:" not in str(msg.get("content") or "")


def test_label_mask_covers_only_target_assistant_turn(tmp_path, no_heldout):
    root = tmp_path / "j4"
    _write_fixed_k_run(root, task_id="copy_hello", seed=1, events=_j4_style_events())
    out = tmp_path / "corr.jsonl"
    build_correction_dataset(root, ["copy_hello"], out)
    line = _load_runs(out)[0]
    messages = line["messages"]
    target_indices = [int(x) for x in line["meta"]["supervised_message_indices"]]
    target_i = int(line["meta"]["supervised_message_index"])
    assert target_indices == [target_i]
    assert messages[target_i]["role"] == "assistant"
    assert CODE_AFTER in messages[target_i]["content"]
    tok = CharChatTokenizer()
    masked = remask_to_message_indices(messages, tok, set(target_indices), max_length=None)
    also = remask_to_message_index(messages, tok, target_i, max_length=None)
    assert masked["labels"] == also["labels"]
    expected: list[int] = []
    prev: list[int] = []
    for i, msg in enumerate(messages):
        curr = tok.encode(tok.apply_chat_template(messages[: i + 1], tokenize=False))
        span = curr[len(prev) :]
        if i in target_indices:
            expected.extend(span)
        else:
            expected.extend([-100] * len(span))
        prev = curr
    assert masked["labels"] == expected
    assert any(lab != -100 for lab in masked["labels"])
    assistant_idxs = [i for i, m in enumerate(messages) if m["role"] == "assistant"]
    assert assistant_idxs[-1] == target_i
    for idx in assistant_idxs[:-1]:
        prefix = tok.encode(tok.apply_chat_template(messages[:idx], tokenize=False))
        full = tok.encode(tok.apply_chat_template(messages[: idx + 1], tokenize=False))
        span_labels = masked["labels"][len(prefix) : len(full)]
        assert span_labels
        assert all(lab == -100 for lab in span_labels)


def test_leakage_passes_and_fails_when_given_a_dev_id(tmp_path, monkeypatch):
    heldout = ["dev_task", "test_task"]
    monkeypatch.setattr("sidekick.training.sft_data._heldout_task_ids", lambda: list(heldout))
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda *_a, **_k: None)
    monkeypatch.setattr("sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "")
    train_ids = ["copy_hello"]
    assert_no_leakage(train_ids, heldout)
    with pytest.raises(ValueError, match="dev_task"):
        assert_no_leakage([*train_ids, "dev_task"], heldout)

    root = tmp_path / "j4"
    _write_fixed_k_run(root, task_id="copy_hello", seed=1, events=_j4_style_events())
    out = tmp_path / "corr.jsonl"
    build_correction_dataset(root, ["copy_hello"], out)
    with pytest.raises(ValueError, match="dev_task"):
        build_correction_dataset(root, ["copy_hello", "dev_task"], tmp_path / "leaky.jsonl")


def test_real_j4_episode_builds_without_error(tmp_path, no_heldout):
    assert J4_ARCHIVE.is_dir(), f"missing read-only J4 archive at {J4_ARCHIVE}"
    events = sorted(J4_ARCHIVE.glob("fixed_k/*/*/events.jsonl"))
    assert events, f"no events.jsonl under {J4_ARCHIVE}"
    episode = events[0]
    task_id = episode.parent.name
    summary = build_correction_dataset(
        J4_ARCHIVE, [task_id], tmp_path / "real_j4.jsonl"
    )
    assert summary["n_ask_planner_targets"] == 0
    assert summary["n_ask_events"] == 0
    runs = _load_runs(tmp_path / "real_j4.jsonl")
    assert summary["n_sequences"] == len(runs)
    assert summary["n_sequences"] >= 1
    for line in runs:
        for msg in line["messages"]:
            assert "INTERVENTION:" not in str(msg.get("content") or "")
        last = line["messages"][-1]
        assert last["role"] == "assistant"
        assert parse_executor_action(last["content"]).kind != "ASK_PLANNER"


def test_ask_planner_after_intervention_is_not_a_target(tmp_path, no_heldout):
    root = tmp_path / "j4"
    _write_fixed_k_run(
        root,
        task_id="copy_hello",
        seed=1,
        events=_j4_style_events(n_interventions=1, post_kinds=["ASK_PLANNER"]),
    )
    out = tmp_path / "corr.jsonl"
    summary = build_correction_dataset(root, ["copy_hello"], out)
    assert summary["n_sequences"] == 0
    assert summary["n_ask_planner_targets"] == 1
    assert summary["dropped_counts"][DROP_ASK_PLANNER_TARGET] == 1
    assert _load_runs(out) == []


def test_sft_b_plus_combines_teacher_and_correction(tmp_path, no_heldout):
    teacher = tmp_path / "j3"
    correction = tmp_path / "j4"
    _write_teacher_run(teacher)
    _write_fixed_k_run(correction, task_id="copy_hello", seed=1, events=_j4_style_events())
    teacher_jsonl = tmp_path / "teacher.jsonl"
    from sidekick.training.sft_data import build_sft_dataset

    build_sft_dataset(teacher, ["copy_hello"], teacher_jsonl)
    out = tmp_path / "sft_b_plus.jsonl"
    summary = build_sft_b_plus(
        correction, ["copy_hello"], out, teacher_jsonl=teacher_jsonl
    )
    assert summary["n_teacher_sequences"] == 1
    assert summary["n_correction_sequences"] == 1
    assert summary["n_sequences"] == 2
    assert summary["n_ask_planner_targets"] == 0
    assert summary["n_ask_targets"] == 0
    lines = _load_runs(out)
    assert len(lines) == 2
    sources = [ln["meta"]["source"] for ln in lines]
    assert "solved" in sources
    assert "correction" in sources
    for ln in lines:
        for msg in ln["messages"]:
            assert "INTERVENTION:" not in str(msg.get("content") or "")
    corr = next(ln for ln in lines if ln["meta"]["source"] == "correction")
    assert parse_executor_action(corr["messages"][-1]["content"]).kind != "ASK_PLANNER"
    teacher_bytes = teacher_jsonl.read_bytes()
    combined = out.read_bytes()
    assert combined.startswith(teacher_bytes if teacher_bytes.endswith(b"\n") else teacher_bytes + b"\n")
