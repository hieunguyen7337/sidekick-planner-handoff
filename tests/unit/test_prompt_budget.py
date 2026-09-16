"""Unit U-H: one truncation policy shared by training (sft_data) and serving (VLLMExecutor)."""
from __future__ import annotations

import pytest

from sidekick.agents.executor import VLLMExecutor
from sidekick.protocols.prompts import fit_messages_to_budget
from sidekick.runner import make_executor
from sidekick.training.sft_data import tokenize_and_mask


class CharChatTokenizer:
    """Character-level tokenizer whose chat template preserves the prefix property."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        # Deliberately ignores add_generation_prompt: the stub's counter is then
        # identical for the training path and the serving path, so the anti-drift
        # test compares the two policies with the same length function.
        text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages)
        if tokenize:
            return self.encode(text)
        return text

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) for ch in text]


def _messages(n: int, tag: str = "m") -> list[dict]:
    msgs = [
        {"role": "system", "content": "SYSTEM framing"},
        {"role": "user", "content": "TASK framing"},
    ]
    for i in range(n - 3):
        role = "assistant" if i % 2 == 0 else "user"
        msgs.append({"role": role, "content": f"{tag}{i}"})
    msgs.append({"role": "assistant", "content": "FINAL COMPLETE"})
    return msgs


def _char_len(messages: list[dict]) -> int:
    return len(CharChatTokenizer().apply_chat_template(messages, add_generation_prompt=True))


def test_head_tail_retained_only_middle_dropped():
    messages = _messages(8)
    selected, dropped, representable = fit_messages_to_budget(
        messages, max_tokens=_char_len(messages) - 10, length_fn=_char_len
    )
    assert representable is True
    assert dropped == 1
    assert selected[0] == messages[0]
    assert selected[1] == messages[1]
    assert selected[-1] == messages[-1]
    assert "m0" not in [m["content"] for m in selected]
    assert "m1" in [m["content"] for m in selected]
    assert _char_len(selected) <= _char_len(messages) - 10


def test_never_splits_a_message():
    messages = _messages(6)
    tok = CharChatTokenizer()
    selected, dropped, representable = fit_messages_to_budget(
        messages, max_tokens=_char_len(messages) - 5, length_fn=_char_len
    )
    assert representable is True
    assert dropped == 1
    # every retained message appears whole; the dropped one is gone entirely
    for m in selected:
        assert any(x["content"] == m["content"] for x in messages)
    rendered = tok.apply_chat_template(selected)
    assert "m0" not in rendered


def test_unrepresentable_when_anchors_alone_over_budget():
    messages = _messages(8)
    original = [dict(m) for m in messages]
    selected, dropped, representable = fit_messages_to_budget(
        messages, max_tokens=1, length_fn=_char_len
    )
    assert representable is False
    assert dropped == 0
    assert selected == original  # unmodified list returned


def test_training_and_serving_select_identical_messages():
    messages = _messages(9)
    tok = CharChatTokenizer()
    budget = _char_len(messages) - 30

    serving_selected, serving_dropped, _ = fit_messages_to_budget(
        messages, max_tokens=budget, length_fn=_char_len
    )
    out = tokenize_and_mask(messages, tok, max_length=budget)
    assert out["truncated"] is True
    assert out["n_messages_dropped"] == serving_dropped
    # The rendered training prompt contains EXACTLY the serving-selected messages.
    serving_rendered = tok.apply_chat_template(serving_selected)
    training_rendered = "".join(chr(t) for t in out["input_ids"])
    assert training_rendered == serving_rendered


class _FakeResponse200:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "COMPLETE"}}], "usage": {}}


def test_executor_no_truncation_no_tokenizer_when_budget_none(monkeypatch):
    loads = {"count": 0}

    def _fail_load(*a, **kw):
        loads["count"] += 1
        raise AssertionError("tokenizer must not be loaded when max_prompt_tokens is None")

    captured = {}

    class FakeClient:
        def post(self, url, json=None):
            captured["payload"] = json
            return _FakeResponse200()

    ex = VLLMExecutor("test-model", "http://x", http_client=FakeClient())
    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", _fail_load)
    messages = _messages(6)
    text, usage = ex.complete(messages)
    assert text == "COMPLETE"
    assert captured["payload"]["messages"] == messages  # untouched
    assert loads["count"] == 0
    assert ex._tokenizer_loaded is False
    assert usage.raw["n_messages_dropped"] == 0
    assert usage.raw["n_400_retries"] == 0


def test_executor_400_backstop_retries_and_counts():
    statuses = [400, 400, 200]

    class FakeResponse:
        def __init__(self, status):
            self.status_code = status

        def raise_for_status(self):
            if self.status_code == 400:
                import httpx

                request = httpx.Request("POST", "http://x/v1/chat/completions")
                response = httpx.Response(400, request=request)
                raise httpx.HTTPStatusError("400", request=request, response=response)

        def json(self):
            return {"choices": [{"message": {"content": "COMPLETE"}}], "usage": {"prompt_tokens": 1}}

    class FakeClient:
        def __init__(self):
            self.calls = []
            self.i = 0

        def post(self, url, json=None):
            self.calls.append(len(json["messages"]))
            resp = FakeResponse(statuses[self.i])
            self.i += 1
            return resp

    client = FakeClient()
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    messages = _messages(6)
    text, usage = ex.complete(messages)
    assert text == "COMPLETE"
    assert client.calls == [len(messages), len(messages) - 1, len(messages) - 2]
    assert usage.raw["n_400_retries"] == 2


def test_executor_fits_to_budget_with_stub_tokenizer():
    class FakeClient:
        def __init__(self):
            self.payload = None

        def post(self, url, json=None):
            self.payload = json
            return _FakeResponse200()

    client = FakeClient()
    ex = VLLMExecutor("test-model", "http://x", http_client=client, max_prompt_tokens=100)
    # a stub tokenizer: the anchor set (94 chars) fits, each middle message does not
    ex._tokenizer = CharChatTokenizer()
    ex._tokenizer_loaded = True
    messages = _messages(6)
    ex.complete(messages)
    sent = client.payload["messages"]
    assert sent[0] == messages[0]
    assert sent[1] == messages[1]
    assert sent[-1] == messages[-1]
    assert len(sent) == 3


def test_runner_forwards_max_prompt_tokens():
    ex = make_executor(
        {
            "executor": {
                "type": "vllm",
                "model": "test-model",
                "max_prompt_tokens": 12345,
            }
        }
    )
    assert ex.max_prompt_tokens == 12345


def test_runner_defaults_max_prompt_tokens_to_none():
    ex = make_executor(
        {
            "executor": {
                "type": "vllm",
                "model": "test-model",
            }
        }
    )
    assert ex.max_prompt_tokens is None
