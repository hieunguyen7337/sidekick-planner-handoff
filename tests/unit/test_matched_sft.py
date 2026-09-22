"""W-3: multi-target masks, trainer spec, matched sft_b_plus / sft_c pair."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sidekick.training.matched_sft import (
    ASK_TEMPLATE,
    _combine_teacher_and_correction,
    build_ask_dataset,
    build_sft_b_plus,
    classify_branch_label,
)
from sidekick.training.sft_data import (
    _map_target_index_after_budget_fit,
    remask_to_message_index,
    tokenize_and_mask,
    tokenize_sft_row,
)


def _corr_helpers():
    path = Path(__file__).with_name("test_sft_correction.py")
    spec = importlib.util.spec_from_file_location("w3_sft_corr_helpers", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_C = _corr_helpers()
CharChatTokenizer = _C.CharChatTokenizer
J4_ARCHIVE = _C.J4_ARCHIVE
_j4_style_events = _C._j4_style_events
_load_runs = _C._load_runs
_write_fixed_k_run = _C._write_fixed_k_run
_write_teacher_run = _C._write_teacher_run
build_correction_dataset = _C.build_correction_dataset


@pytest.fixture
def no_heldout(monkeypatch):
    monkeypatch.setattr("sidekick.training.sft_data._heldout_task_ids", lambda: ["held_out_task"])
    monkeypatch.setattr("sidekick.training.sft_data._try_tokenizer", lambda *_a, **_k: None)
    monkeypatch.setattr("sidekick.training.sft_data._api_docs_from_appworld", lambda task_id: "")


def test_ask_template_byte_for_byte() -> None:
    assert ASK_TEMPLATE == (
        "ASK_PLANNER: Review my progress so far and tell me the next step."
    )


def _branch_row(
    *,
    task_id: str = "copy_hello",
    seed: int = 1,
    i: int = 0,
    needed: bool = False,
    needless: bool = False,
    ambiguous: bool = False,
    label_status: str = "complete",
    correction: str = "do the write step 0",
    delta_band_delta: float = 0.05,
) -> dict:
    return {
        "campaign": "j4",
        "seed": seed,
        "task_id": task_id,
        "i": i,
        "step": 2,
        "treated_gpr": [0.0],
        "untreated_gpr": [0.0],
        "delta_mean": 0.0,
        "delta_crn": 0.0,
        "delta_local": 0.0,
        "actual_gpr": 0.0,
        "delta": 0.0,
        "needed": needed,
        "needless": needless,
        "ambiguous": ambiguous,
        "harmful": False,
        "needed_strict": needed,
        "label_status": label_status,
        "delta_band_delta": delta_band_delta,
        "correction": correction,
    }


def _write_labels(path: Path, rows: list[dict]) -> Path:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _write_teacher_jsonl(tmp_path, no_heldout) -> Path:
    teacher = tmp_path / "j3"
    _write_teacher_run(teacher)
    teacher_jsonl = tmp_path / "teacher.jsonl"
    from sidekick.training.sft_data import build_sft_dataset

    build_sft_dataset(teacher, ["copy_hello"], teacher_jsonl)
    return teacher_jsonl


def test_classify_branch_label_addendum_schema() -> None:
    assert classify_branch_label({"label_status": "ok", "needed": True}) == "incomplete"
    assert classify_branch_label({"label_status": "complete", "needed": True}) == "needed"
    assert classify_branch_label({"label_status": "complete", "needless": True}) == "needless"
    assert classify_branch_label({"label_status": "complete", "ambiguous": True}) == "ambiguous"
    assert classify_branch_label({"label_status": "incomplete"}) == "incomplete"
    assert classify_branch_label({"label_status": "complete"}) == "ambiguous"


def test_map_target_index_identity_beats_equality() -> None:
    dup = {"role": "assistant", "content": "```python\nprint(login())\n```"}
    a1 = dict(dup)
    a2 = dict(dup)
    messages = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "task"},
        a1,
        {"role": "user", "content": "OBS: x"},
        a2,
    ]
    # Identity succeeds even though a1 == a2.
    assert _map_target_index_after_budget_fit(messages, messages, 4) == 4
    assert _map_target_index_after_budget_fit(messages, messages, 2) == 2
    # Copies: identity fails, positional count among value-equals.
    selected = [dict(m) for m in messages]
    assert all(m is not orig for m, orig in zip(selected, messages))
    assert _map_target_index_after_budget_fit(messages, selected, 4) == 4
    assert _map_target_index_after_budget_fit(messages, selected, 2) == 2
    # Dropping the first duplicate must not map the lost target onto the survivor.
    dropped = [messages[0], messages[1], messages[3], messages[4]]
    assert _map_target_index_after_budget_fit(messages, dropped, 4) == 3
    assert _map_target_index_after_budget_fit(messages, dropped, 2) is None


def test_remask_duplicate_assistant_supervises_the_second_turn() -> None:
    """Budget-fit keeps both identical assistant turns; loss must sit on the later one."""
    dup_content = "```python\nprint(login())\n```"
    a1 = {"role": "assistant", "content": dup_content}
    a2 = {"role": "assistant", "content": dup_content}
    long_user = {"role": "user", "content": "U" * 400}
    messages = [
        {"role": "system", "content": "s"},
        long_user,
        a1,
        {"role": "user", "content": "OBS: x"},
        a2,
    ]
    tok = CharChatTokenizer()
    full_len = len(tok.encode(tok.apply_chat_template(messages, tokenize=False)))
    # Small enough to force truncation/elision, large enough to keep both assistants.
    max_length = full_len - 50
    target_i = 4
    # Old bug: `m is orig or m == orig` would map target_i onto a1 (index 2).
    first_equal = next(k for k, m in enumerate(messages) if m == a2)
    assert first_equal == 2
    masked = remask_to_message_index(messages, tok, target_i, max_length=max_length)
    assert masked["representable"] is True
    # Reconstruct spans on the selected (possibly elided) conversation via the labels
    # that remask wrote: only the last assistant span may be unmasked.
    labeled = [i for i, lab in enumerate(masked["labels"]) if lab != -100]
    assert labeled, "expected some supervised tokens"
    # The first duplicate's tokens must be fully masked: compare against a remask of index 2.
    masked_first = remask_to_message_index(messages, tok, 2, max_length=max_length)
    first_labeled = [i for i, lab in enumerate(masked_first["labels"]) if lab != -100]
    if masked_first["representable"]:
        assert labeled != first_labeled
        assert not set(labeled) & set(first_labeled)
    else:
        assert not first_labeled


def test_tokenize_sft_row_no_spec_matches_tokenize_and_mask() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "```python\nprint(1)\n```"},
        {"role": "user", "content": "OBS: 1"},
        {"role": "assistant", "content": "COMPLETE"},
    ]
    tok = CharChatTokenizer()
    row = {"messages": messages, "meta": {"task_id": "copy_hello", "source": "solved"}}
    a = tokenize_sft_row(row, tok, max_length=None)
    b = tokenize_and_mask(messages, tok, max_length=None)
    assert a["labels"] == b["labels"]
    assert a["input_ids"] == b["input_ids"]


def test_tokenize_sft_row_honours_either_spelling() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "```python\nprint(1)\n```"},
        {"role": "user", "content": "OBS: 1"},
        {"role": "assistant", "content": "COMPLETE"},
    ]
    tok = CharChatTokenizer()
    plural = tokenize_sft_row(
        {"messages": messages, "meta": {"supervised_message_indices": [4]}},
        tok,
        max_length=None,
    )
    singular = tokenize_sft_row(
        {"messages": messages, "meta": {"supervised_message_index": 4}},
        tok,
        max_length=None,
    )
    last_only = tokenize_sft_row(
        {"messages": messages, "meta": {"supervise_last_assistant_only": True}},
        tok,
        max_length=None,
    )
    assert plural["labels"] == singular["labels"] == last_only["labels"]
    unmasked = tokenize_and_mask(messages, tok, max_length=None)
    assert plural["labels"] != unmasked["labels"]


def test_needless_pair_sequences_are_byte_identical(tmp_path, no_heldout):
    teacher_jsonl = _write_teacher_jsonl(tmp_path, no_heldout)
    corr = tmp_path / "j4"
    _write_fixed_k_run(
        corr, task_id="copy_hello", seed=1, events=_j4_style_events(n_interventions=2)
    )
    labels = _write_labels(
        tmp_path / "branches.jsonl",
        [
            _branch_row(i=0, needless=True),
            _branch_row(i=1, needless=True, correction="do the write step 1"),
        ],
    )
    plus = tmp_path / "sft_b_plus.jsonl"
    ask = tmp_path / "sft_c.jsonl"
    plus_sum = build_sft_b_plus(
        corr, ["copy_hello"], plus, teacher_jsonl=teacher_jsonl
    )
    ask_sum = build_ask_dataset(
        corr, ["copy_hello"], labels, ask, teacher_jsonl=teacher_jsonl
    )
    plus_rows = _load_runs(plus)
    ask_rows = _load_runs(ask)
    assert plus_sum["n_sequences"] == ask_sum["n_sequences"] == len(plus_rows) == len(ask_rows)
    assert [r["meta"]["task_id"] for r in plus_rows] == [r["meta"]["task_id"] for r in ask_rows]
    plus_corr = [r for r in plus_rows if r["meta"].get("source") == "correction"]
    ask_corr = [r for r in ask_rows if r["meta"].get("source") == "correction"]
    assert len(plus_corr) == len(ask_corr) == 1
    assert json.dumps(plus_corr[0]["messages"], sort_keys=True) == json.dumps(
        ask_corr[0]["messages"], sort_keys=True
    )
    plus_actions = sum(int(r["meta"].get("n_action_targets") or 0) for r in plus_corr)
    ask_actions = sum(int(r["meta"].get("n_action_targets") or 0) for r in ask_corr)
    assert plus_actions == ask_actions == 2
    assert ask_sum["n_ask_targets"] == 0
    assert plus_sum["n_ask_targets"] == 0
    for row in plus_rows + ask_rows:
        blob = json.dumps(row)
        assert "INTERVENTION:" not in blob
        for idx in row["meta"].get("supervised_message_indices") or []:
            content = row["messages"][int(idx)]["content"]
            assert not str(content).startswith("ASK_PLANNER:")


def test_needed_point_inserts_ask_and_keeps_action_count(tmp_path, no_heldout):
    teacher_jsonl = _write_teacher_jsonl(tmp_path, no_heldout)
    corr = tmp_path / "j4"
    _write_fixed_k_run(
        corr, task_id="copy_hello", seed=1, events=_j4_style_events(n_interventions=2)
    )
    labels = _write_labels(
        tmp_path / "branches.jsonl",
        [
            _branch_row(i=0, needed=True),
            _branch_row(i=1, needless=True, correction="do the write step 1"),
        ],
    )
    plus = tmp_path / "sft_b_plus.jsonl"
    ask = tmp_path / "sft_c.jsonl"
    plus_sum = build_sft_b_plus(
        corr, ["copy_hello"], plus, teacher_jsonl=teacher_jsonl
    )
    ask_sum = build_ask_dataset(
        corr, ["copy_hello"], labels, ask, teacher_jsonl=teacher_jsonl
    )
    plus_rows = _load_runs(plus)
    ask_rows = _load_runs(ask)
    assert plus_sum["n_sequences"] == ask_sum["n_sequences"]
    plus_corr = next(r for r in plus_rows if r["meta"].get("source") == "correction")
    ask_corr = next(r for r in ask_rows if r["meta"].get("source") == "correction")
    assert plus_corr["meta"]["n_action_targets"] == ask_corr["meta"]["n_action_targets"]
    assert plus_corr["meta"]["n_ask_targets"] == 0
    assert ask_corr["meta"]["n_ask_targets"] == 1
    assert ask_sum["n_needed"] == 1
    assert ask_sum["n_needless"] == 1
    assert ASK_TEMPLATE in [m["content"] for m in ask_corr["messages"]]
    assert ASK_TEMPLATE not in [m.get("content") for m in plus_corr["messages"]]
    ask_idxs = [
        i
        for i, m in enumerate(ask_corr["messages"])
        if m.get("role") == "assistant" and m.get("content") == ASK_TEMPLATE
    ]
    assert ask_idxs == [
        i
        for i in ask_corr["meta"]["supervised_message_indices"]
        if ask_corr["messages"][i]["content"] == ASK_TEMPLATE
    ]
    # ANSWER uses the recorded correction text.
    answers = [
        m["content"]
        for m in ask_corr["messages"]
        if m.get("role") == "user" and str(m.get("content") or "").startswith("ANSWER:")
    ]
    assert answers == ["ANSWER: do the write step 0"]
    for row in plus_rows + ask_rows:
        assert "INTERVENTION:" not in json.dumps(row)


def test_ambiguous_and_incomplete_match_needless(tmp_path, no_heldout):
    teacher_jsonl = _write_teacher_jsonl(tmp_path, no_heldout)
    corr = tmp_path / "j4"
    _write_fixed_k_run(
        corr, task_id="copy_hello", seed=1, events=_j4_style_events(n_interventions=2)
    )
    labels = _write_labels(
        tmp_path / "branches.jsonl",
        [
            _branch_row(i=0, ambiguous=True),
            _branch_row(i=1, label_status="incomplete"),
        ],
    )
    plus = tmp_path / "sft_b_plus.jsonl"
    ask = tmp_path / "sft_c.jsonl"
    plus_sum = build_sft_b_plus(
        corr, ["copy_hello"], plus, teacher_jsonl=teacher_jsonl
    )
    ask_sum = build_ask_dataset(
        corr, ["copy_hello"], labels, ask, teacher_jsonl=teacher_jsonl
    )
    plus_corr = next(
        r for r in _load_runs(plus) if r["meta"].get("source") == "correction"
    )
    ask_corr = next(r for r in _load_runs(ask) if r["meta"].get("source") == "correction")
    assert json.dumps(plus_corr["messages"], sort_keys=True) == json.dumps(
        ask_corr["messages"], sort_keys=True
    )
    assert ask_sum["n_ask_targets"] == 0
    assert plus_sum["n_ask_targets"] == 0
    assert ask_sum["n_ambiguous"] == 1
    assert ask_sum["n_incomplete"] == 1
    assert ask_sum["n_ambiguous_treated_as_needless"] == 2
    assert ask_sum["delta_band_delta"] == 0.05


def test_seeds_are_discovered_not_hardcoded(tmp_path, no_heldout):
    teacher_jsonl = _write_teacher_jsonl(tmp_path, no_heldout)
    corr = tmp_path / "j4"
    _write_fixed_k_run(
        corr, task_id="copy_hello", seed=1, events=_j4_style_events()
    )
    _write_fixed_k_run(
        corr, task_id="copy_hello", seed=7, events=_j4_style_events()
    )
    out = tmp_path / "plus.jsonl"
    summary = build_sft_b_plus(
        corr, ["copy_hello"], out, teacher_jsonl=teacher_jsonl
    )
    seeds = sorted(
        {
            r["meta"]["seed"]
            for r in _load_runs(out)
            if r["meta"].get("source") == "correction"
        }
    )
    assert seeds == [1, 7]
    assert summary["n_correction_sequences"] == 2


def test_real_j4_row_trainer_mask_covers_only_supervised_indices(tmp_path, no_heldout):
    from sidekick.training.sft_data import tokenize_sft_row

    assert J4_ARCHIVE.is_dir(), f"missing read-only J4 archive at {J4_ARCHIVE}"
    events = sorted(J4_ARCHIVE.glob("fixed_k/*/*/events.jsonl"))
    episode = events[0]
    task_id = episode.parent.name
    out = tmp_path / "real_j4_mask.jsonl"
    build_correction_dataset(J4_ARCHIVE, [task_id], out)
    line = _load_runs(out)[0]
    messages = line["messages"]
    targets = {int(x) for x in line["meta"]["supervised_message_indices"]}
    tok = CharChatTokenizer()
    masked = tokenize_sft_row(line, tok, max_length=None)
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
    assert masked["labels"] == expected
    assert any(lab != -100 for lab in masked["labels"])
    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant" or i in targets:
            continue
        prefix = tok.encode(tok.apply_chat_template(messages[:i], tokenize=False))
        full = tok.encode(tok.apply_chat_template(messages[: i + 1], tokenize=False))
        span_labels = masked["labels"][len(prefix) : len(full)]
        assert span_labels
        assert all(lab == -100 for lab in span_labels)


def _synthetic_teacher(tmp_path: Path) -> Path:
    path = tmp_path / "teacher.jsonl"
    path.write_text("", encoding="utf-8")
    return path


def _iv_record(*, task_id: str = "copy_hello") -> dict:
    return {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "```python\nprint(1)\n```"},
            {"role": "user", "content": "INTERVENTION: do the write"},
            {"role": "assistant", "content": "```python\nprint(2)\n```"},
        ],
        "meta": {
            "task_id": task_id,
            "source": "correction",
            "supervised_message_indices": [4],
            "n_action_targets": 1,
            "n_ask_targets": 0,
        },
    }


def _ask_record(*, task_id: str = "copy_hello") -> dict:
    return {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": ASK_TEMPLATE},
        ],
        "meta": {
            "task_id": task_id,
            "source": "correction",
            "supervised_message_indices": [2],
            "n_action_targets": 0,
            "n_ask_targets": 1,
        },
    }


def _clean_record(*, task_id: str = "copy_hello") -> dict:
    return {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "```python\nprint(1)\n```"},
        ],
        "meta": {
            "task_id": task_id,
            "source": "correction",
            "supervised_message_indices": [2],
            "n_action_targets": 1,
            "n_ask_targets": 0,
        },
    }


def _run_combine(tmp_path, records, **kwargs):
    teacher = _synthetic_teacher(tmp_path)
    out = kwargs.pop("out_jsonl", tmp_path / "combined.jsonl")
    return _combine_teacher_and_correction(
        teacher,
        records,
        {},
        Path(out),
        quiet=True,
        adapter_manifest=tmp_path / "no_adapter.json",
        **kwargs,
    )


def test_combine_default_raises_on_intervention_turn(tmp_path, no_heldout):
    with pytest.raises(RuntimeError, match="INTERVENTION:"):
        _run_combine(tmp_path, [_iv_record()])


def test_combine_retain_keeps_intervention_text(tmp_path, no_heldout):
    out = tmp_path / "retain.jsonl"
    _run_combine(tmp_path, [_iv_record()], allow_interventions=True, out_jsonl=out)
    blob = out.read_text(encoding="utf-8")
    assert "INTERVENTION:" in blob
    rows = [json.loads(line) for line in blob.splitlines() if line.strip()]
    assert any(
        "INTERVENTION:" in str(m.get("content") or "")
        for row in rows
        for m in row.get("messages") or []
    )


def test_combine_ask_guard_ignores_allow_interventions(tmp_path, no_heldout):
    with pytest.raises(RuntimeError, match="ASK_PLANNER"):
        _run_combine(tmp_path, [_ask_record()])
    with pytest.raises(RuntimeError, match="ASK_PLANNER"):
        _run_combine(tmp_path, [_ask_record()], allow_interventions=True)


def test_combine_retain_still_asserts_no_leakage(tmp_path, no_heldout):
    with pytest.raises(ValueError, match="Split leakage"):
        _run_combine(
            tmp_path,
            [_iv_record(task_id="held_out_task")],
            allow_interventions=True,
        )


def test_combine_reports_intervention_mode(tmp_path, no_heldout):
    strip_out = tmp_path / "strip.jsonl"
    strip_sum = _run_combine(tmp_path, [_clean_record()], out_jsonl=strip_out)
    assert strip_sum["intervention_mode"] == "strip"
    strip_manifest = json.loads(Path(str(strip_out) + ".manifest.json").read_text())
    assert strip_manifest["intervention_mode"] == "strip"

    retain_out = tmp_path / "retain.jsonl"
    retain_sum = _run_combine(
        tmp_path,
        [_iv_record()],
        allow_interventions=True,
        out_jsonl=retain_out,
    )
    assert retain_sum["intervention_mode"] == "retain"
    retain_manifest = json.loads(Path(str(retain_out) + ".manifest.json").read_text())
    assert retain_manifest["intervention_mode"] == "retain"
