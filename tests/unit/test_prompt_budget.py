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
    selected, dropped, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=_char_len(messages) - 10, length_fn=_char_len
    )
    assert n_elided == 0
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
    selected, dropped, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=_char_len(messages) - 5, length_fn=_char_len
    )
    assert n_elided == 0
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
    selected, dropped, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=1, length_fn=_char_len
    )
    assert representable is False
    assert dropped == 0
    assert n_elided == 0
    assert selected == original  # unmodified list returned


def test_training_and_serving_select_identical_messages():
    messages = _messages(9)
    tok = CharChatTokenizer()
    budget = _char_len(messages) - 30

    serving_selected, serving_dropped, _, serving_elided = fit_messages_to_budget(
        messages, max_tokens=budget, length_fn=_char_len
    )
    assert serving_elided == 0
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


# ---------------------------------------------------------------------------
# U-Z: middle-elide an oversized last observation (defect #19)
# ---------------------------------------------------------------------------

_OVERSIZE_HEAD = 'BEGIN_SHAPE_[{"id": 1'
_OVERSIZE_TAIL = '"id": 999}]_END'


def _oversize_last_messages() -> tuple[list[dict], str]:
    huge = _OVERSIZE_HEAD + ("M" * 8000) + _OVERSIZE_TAIL
    messages = [
        {"role": "system", "content": "SYSTEM framing"},
        {"role": "user", "content": "TASK framing"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": huge},
    ]
    return messages, huge


def test_oversize_last_message_fits_after_elision():
    messages, huge = _oversize_last_messages()
    anchors = [messages[0], messages[1], messages[-1]]
    budget = _char_len(anchors) - 2000
    assert _char_len(anchors) > budget
    selected, dropped, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=budget, length_fn=_char_len
    )
    assert representable is True
    assert n_elided > 0
    assert dropped == 1
    assert _char_len(selected) <= budget
    assert selected[0]["content"] == messages[0]["content"]
    assert selected[1]["content"] == messages[1]["content"]
    assert selected[-1]["content"] != huge
    assert all(m["content"] != "ok" for m in selected)


def test_elision_keeps_head_tail_and_marker():
    messages, huge = _oversize_last_messages()
    budget = _char_len([messages[0], messages[1], messages[-1]]) - 2000
    selected, _, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=budget, length_fn=_char_len
    )
    assert representable is True
    content = selected[-1]["content"]
    assert content.startswith(_OVERSIZE_HEAD)
    assert content.endswith(_OVERSIZE_TAIL)
    assert f"[{n_elided} characters elided]" in content
    marker = f"\n... [{n_elided} characters elided] ...\n"
    assert marker in content
    head, tail = content.split(marker, 1)
    assert huge.startswith(head)
    assert huge.endswith(tail)
    assert n_elided == len(huge) - len(head) - len(tail)


def test_elided_character_count_is_nonzero():
    messages, huge = _oversize_last_messages()
    budget = _char_len([messages[0], messages[1], messages[-1]]) - 2000
    _, _, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=budget, length_fn=_char_len
    )
    assert representable is True
    assert n_elided > 0
    assert n_elided < len(huge)


def test_already_fitting_unchanged_zero_elided():
    messages = _messages(6)
    original = [dict(m) for m in messages]
    selected, dropped, representable, n_elided = fit_messages_to_budget(
        messages, max_tokens=_char_len(messages) + 10, length_fn=_char_len
    )
    assert representable is True
    assert dropped == 0
    assert n_elided == 0
    assert selected == original
    assert [m["content"] for m in selected] == [m["content"] for m in messages]


def test_executor_records_elision_count_and_representable():
    messages, _huge = _oversize_last_messages()
    budget = _char_len([messages[0], messages[1], messages[-1]]) - 2000

    class FakeClient:
        def __init__(self):
            self.payload = None

        def post(self, url, json=None):
            self.payload = json
            return _FakeResponse200()

    client = FakeClient()
    ex = VLLMExecutor(
        "test-model", "http://x", http_client=client, max_prompt_tokens=budget
    )
    ex._tokenizer = CharChatTokenizer()
    ex._tokenizer_loaded = True
    _text, usage = ex.complete(messages)
    assert usage.raw["n_chars_elided"] > 0
    assert usage.raw["representable"] is True
    assert usage.raw["n_messages_dropped"] >= 0
    sent = client.payload["messages"]
    assert "characters elided" in sent[-1]["content"]
    assert _char_len(sent) <= budget


def test_training_and_serving_elide_identically():
    messages, _huge = _oversize_last_messages()
    tok = CharChatTokenizer()
    budget = _char_len([messages[0], messages[1], messages[-1]]) - 2000

    serving_selected, serving_dropped, representable, serving_elided = (
        fit_messages_to_budget(messages, max_tokens=budget, length_fn=_char_len)
    )
    assert representable is True
    assert serving_elided > 0
    out = tokenize_and_mask(messages, tok, max_length=budget)
    assert out["representable"] is True
    assert out["n_chars_elided"] == serving_elided
    assert out["n_messages_dropped"] == serving_dropped
    serving_rendered = tok.apply_chat_template(serving_selected)
    training_rendered = "".join(chr(t) for t in out["input_ids"])
    assert training_rendered == serving_rendered
    assert serving_selected[-1]["content"] in training_rendered

