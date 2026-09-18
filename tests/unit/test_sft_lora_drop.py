"""Trainer must count fully-masked / truncated SFT rows instead of skipping silently."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "sft_lora", REPO_ROOT / "scripts" / "train" / "sft_lora.py"
)
sft_lora = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(sft_lora)


class CharChatTokenizer:
    """Character-level tokenizer whose chat template preserves the prefix property."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, **kwargs):
        text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in messages)
        if tokenize:
            return self.encode(text)
        return text

    def encode(self, text, add_special_tokens=False):
        return [ord(ch) for ch in text]


def _n_tokens(messages: list[dict], tok: CharChatTokenizer) -> int:
    return len(tok.encode(tok.apply_chat_template(messages, tokenize=False)))


def _row(run_id: str, messages: list[dict], **meta) -> dict:
    return {
        "messages": messages,
        "meta": {"run_id": run_id, "task_id": run_id.split("/")[-1], **meta},
    }


def _keep_row(run_id: str) -> dict:
    return _row(
        run_id,
        [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
            {"role": "assistant", "content": "A"},
        ],
    )


def _fully_masked_row(run_id: str) -> dict:
    return _row(
        run_id,
        [
            {"role": "system", "content": "S"},
            {"role": "user", "content": "U"},
        ],
    )


def _truncated_past_labels_row(tok: CharChatTokenizer) -> tuple[dict, int]:
    messages = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
        {"role": "assistant", "content": "ONLY SUPERVISION"},
        {"role": "user", "content": "terminal"},
    ]
    anchors = [messages[0], messages[1], messages[-1]]
    max_length = _n_tokens(anchors, tok)
    assert _n_tokens(messages, tok) > max_length
    return _row("drop/trunc/past", messages), max_length


def _truncated_kept_row(tok: CharChatTokenizer) -> tuple[dict, int]:
    messages = [
        {"role": "system", "content": "SYSTEM framing"},
        {"role": "user", "content": "TASK framing"},
        {"role": "assistant", "content": "old action"},
        {"role": "user", "content": "old observation"},
        {"role": "assistant", "content": "FINAL COMPLETE"},
    ]
    retained = messages[:2] + messages[4:]
    max_length = _n_tokens(retained, tok)
    assert _n_tokens(messages, tok) > max_length
    return _row("keep/trunc/kept", messages), max_length


def _as_manifest(tokenized: list, stats: dict) -> dict:
    return {"n_sequences": len(tokenized), **stats}


def test_fully_masked_row_is_counted_as_dropped_not_silently_skipped(capsys):
    tok = CharChatTokenizer()
    rows = [_fully_masked_row("drop/masked/1"), _keep_row("keep/ok/1")]
    tokenized, stats = sft_lora.collect_tokenized_sft_rows(rows, tok, max_length=256)
    err = capsys.readouterr().err
    assert len(tokenized) == 1
    assert stats["n_dropped_no_supervised_tokens"] == 1
    assert stats["n_dropped_fully_masked_before_truncation"] == 1
    assert stats["n_dropped_truncated_past_labels"] == 0
    assert stats["dropped_run_ids"] == ["drop/masked/1"]
    assert stats["dropped_fully_masked_before_truncation_run_ids"] == ["drop/masked/1"]
    assert "WARNING: dropped 1/2" in err
    assert any(lab != -100 for lab in tokenized[0]["labels"])


def test_truncated_but_supervised_row_is_kept_and_counted(capsys):
    tok = CharChatTokenizer()
    row, max_length = _truncated_kept_row(tok)
    tokenized, stats = sft_lora.collect_tokenized_sft_rows([row], tok, max_length=max_length)
    err = capsys.readouterr().err
    assert len(tokenized) == 1
    assert stats["n_dropped_no_supervised_tokens"] == 0
    assert stats["n_truncated_kept"] == 1
    assert stats["truncated_kept_run_ids"] == ["keep/trunc/kept"]
    assert tokenized[0]["truncated"] is True
    assert any(lab != -100 for lab in tokenized[0]["labels"])
    assert "WARNING: kept 1/1" in err


def test_manifest_counts_and_n_sequences_equals_trained():
    tok = CharChatTokenizer()
    trunc_drop, max_drop = _truncated_past_labels_row(tok)
    rows = [
        _keep_row("keep/a"),
        _fully_masked_row("drop/masked"),
        trunc_drop,
        _keep_row("keep/b"),
    ]
    # max_drop is large enough for the short keep/masked rows, and tight
    # enough to strip the only assistant turn off the truncation-drop row.
    tokenized, stats = sft_lora.collect_tokenized_sft_rows(
        rows, tok, max_length=max_drop
    )
    manifest = _as_manifest(tokenized, stats)
    assert manifest["n_rows_in"] == 4
    assert manifest["n_dropped_no_supervised_tokens"] == 2
    assert manifest["n_dropped_fully_masked_before_truncation"] == 1
    assert manifest["n_dropped_truncated_past_labels"] == 1
    assert manifest["n_sequences"] == len(tokenized) == 2
    dumped = json.loads(json.dumps(manifest))
    assert dumped["n_sequences"] == 2
    assert "n_truncated_kept" in dumped
    assert dumped["dropped_run_ids"] == ["drop/masked", "drop/trunc/past"]
    assert dumped["dropped_truncated_past_labels_run_ids"] == ["drop/trunc/past"]


def test_known_answer_n_in_k_dropped_n_sequences():
    tok = CharChatTokenizer()
    n, k = 7, 3
    rows = [_keep_row(f"keep/{i}") for i in range(n - k)]
    rows.extend(_fully_masked_row(f"drop/{i}") for i in range(k))
    tokenized, stats = sft_lora.collect_tokenized_sft_rows(rows, tok, max_length=256)
    assert stats["n_dropped_no_supervised_tokens"] == k
    assert stats["n_rows_in"] == n
    assert len(tokenized) == n - k
    manifest = _as_manifest(tokenized, stats)
    assert manifest["n_sequences"] == n - k
    assert manifest["dropped_run_ids"] == [f"drop/{i}" for i in range(k)]
