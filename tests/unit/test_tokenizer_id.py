"""Default tokenizer id is granite; an explicit granite id must emit identical JSONL."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sidekick.protocols.schemas import Event, ExecutorAction
from sidekick.training.sft_data import (
    _DEFAULT_TOKENIZER_ID,
    _history_from_events,
    _try_tokenizer,
    build_sft_dataset,
    resolve_tokenizer_id,
    tokenizer_label,
)

GRANITE = "ibm-granite/granite-4.2-8b"


def _campaign_helpers():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("test_sft_data.py")
    spec = importlib.util.spec_from_file_location("x27_sft_data_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class _FakeTok:
    def __init__(self, ident: str) -> None:
        self.name_or_path = ident

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        blob = self.name_or_path + "".join(
            f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages
        )
        if tokenize:
            return self.encode(blob)
        return blob

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) % 97 for ch in text]


@pytest.fixture
def fake_auto_tokenizer(monkeypatch):
    requested: list[str] = []

    def from_pretrained(ident, **kwargs):
        requested.append(ident)
        assert kwargs.get("local_files_only") is True
        return _FakeTok(ident)

    monkeypatch.setitem(
        __import__("sys").modules,
        "transformers",
        SimpleNamespace(AutoTokenizer=SimpleNamespace(from_pretrained=from_pretrained)),
    )
    # If transformers is already imported, patch the attribute too.
    try:
        import transformers

        monkeypatch.setattr(
            transformers.AutoTokenizer, "from_pretrained", from_pretrained, raising=False
        )
    except Exception:
        pass
    return requested


def test_resolve_tokenizer_id_defaults_to_granite(monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_TOKENIZER_ID", raising=False)
    assert _DEFAULT_TOKENIZER_ID == GRANITE
    assert resolve_tokenizer_id() == GRANITE
    assert resolve_tokenizer_id(None) == GRANITE
    assert resolve_tokenizer_id(GRANITE) == GRANITE
    assert resolve_tokenizer_id("Qwen/Qwen3-8B") == "Qwen/Qwen3-8B"
    assert tokenizer_label(None) == "whitespace_fallback"
    assert tokenizer_label(object(), GRANITE) == GRANITE


def test_try_tokenizer_default_requests_granite(fake_auto_tokenizer, monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_TOKENIZER_ID", raising=False)
    tok = _try_tokenizer()
    explicit = _try_tokenizer(GRANITE)
    assert fake_auto_tokenizer == [GRANITE, GRANITE]
    assert tok.name_or_path == explicit.name_or_path == GRANITE


def test_default_and_explicit_granite_jsonl_are_byte_identical(
    tmp_path, monkeypatch, fake_auto_tokenizer
) -> None:
    monkeypatch.delenv("SIDEKICK_TOKENIZER_ID", raising=False)
    monkeypatch.setattr(
        "sidekick.training.sft_data._heldout_task_ids", lambda: ["held_out_task"]
    )
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: ""
    )
    root = tmp_path / "camp"
    helpers = _campaign_helpers()
    helpers._write_run(
        root, task_id="copy_hello", seed=1, success=True, events=helpers._live_attempt_events()
    )
    out_default = tmp_path / "default.jsonl"
    out_explicit = tmp_path / "explicit.jsonl"
    s_default = build_sft_dataset(root, ["copy_hello"], out_default, quiet=True)
    s_explicit = build_sft_dataset(
        root, ["copy_hello"], out_explicit, quiet=True, tokenizer_id=GRANITE
    )
    assert out_default.read_bytes() == out_explicit.read_bytes()
    assert s_default["sha256"] == s_explicit["sha256"]
    assert s_default["token_length_percentiles"] == s_explicit["token_length_percentiles"]
    assert s_default["token_length_percentiles"]["tokenizer"] == GRANITE
    assert fake_auto_tokenizer == [GRANITE, GRANITE]
    row = json.loads(out_default.read_text(encoding="utf-8").splitlines()[0])
    assert "messages" in row


def test_history_from_events_keys_on_event_type_not_actor(monkeypatch) -> None:
    monkeypatch.setattr(
        "sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "docs"
    )
    code = ExecutorAction(
        kind="CODE", code="print(1)", raw_output="print(1)"
    ).model_dump()
    events = [
        Event.model_validate(
            {
                "run_id": "r",
                "task_id": "t",
                "system": "planner_alone",
                "seed": 1,
                "step": 0,
                "ts": "2023-05-18T12:00:00+00:00",
                "actor": "environment",
                "event_type": "observation",
                "payload": {"text": "do the thing", "done": False},
            }
        ),
        Event.model_validate(
            {
                "run_id": "r",
                "task_id": "t",
                "system": "planner_alone",
                "seed": 1,
                "step": 1,
                "ts": "2023-05-18T12:00:01+00:00",
                "actor": "planner",
                "event_type": "action",
                "payload": code,
            }
        ),
        Event.model_validate(
            {
                "run_id": "r",
                "task_id": "t",
                "system": "planner_alone",
                "seed": 1,
                "step": 1,
                "ts": "2023-05-18T12:00:02+00:00",
                "actor": "environment",
                "event_type": "observation",
                "payload": {"text": "ok", "done": False},
            }
        ),
    ]
    instruction, _packet, _docs, history = _history_from_events(events)
    assert instruction == "do the thing"
    assert any(h.get("role") == "assistant" for h in history)
    assert any("print(1)" in str(h.get("content") or "") for h in history)
    assert any(str(h.get("content") or "").startswith("OBS:") for h in history)
