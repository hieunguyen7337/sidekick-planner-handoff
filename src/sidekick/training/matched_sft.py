"""Matched sft_b_plus / sft_c builders (W-3).

Teacher half is the frozen sft_b jsonl, copied unchanged. Correction half is
one sequence per episode with multi-target masks. ASK targets exist only in
sft_c, and only at complete ``needed`` labels.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sidekick.protocols.prompts import render_executor_messages
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction
from sidekick.training import assert_no_leakage
from sidekick.training import sft_data as _sft
from sidekick.training.sft_data import (
    ASK_REASON,
    ASK_TEMPLATE,
    DEFAULT_ADAPTER_MANIFEST,
    DEFAULT_CORRECTION_CAMPAIGN,
    DEFAULT_TEACHER_JSONL,
    DROP_ASK_PLANNER_TARGET,
    DROP_INTERVENTION_LEAK,
    DROP_MISSING_EVENTS,
    DROP_MISSING_RESULT,
    DROP_NO_INSTRUCTION,
    DROP_NO_INTERVENTION,
    DROP_NO_POST_INTERVENTION_ACTION,
    DROP_NOT_IN_SPLIT,
    DROP_UNREPRESENTABLE,
    load_split_ids,
)

__all__ = [
    "ASK_TEMPLATE",
    "DEFAULT_ADAPTER_MANIFEST",
    "DEFAULT_CORRECTION_CAMPAIGN",
    "DEFAULT_TEACHER_JSONL",
    "build_ask_dataset",
    "build_correction_dataset",
    "build_sft_b_plus",
    "classify_branch_label",
    "load_branch_labels",
]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sha256_campaign(campaign_root: Path, system: str = "fixed_k") -> str:
    """Fingerprint every ``events.jsonl`` under ``system/`` in sorted relative-path order."""
    h = hashlib.sha256()
    system_root = Path(campaign_root) / system
    if not system_root.is_dir():
        return h.hexdigest()
    for path in sorted(system_root.rglob("events.jsonl")):
        rel = path.relative_to(system_root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _load_jsonl_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"JSONL line is not an object in {path}")
        rows.append(obj)
    return rows


def classify_branch_label(row: dict[str, Any]) -> str:
    """Map one ``branches.jsonl`` row to needed / needless / ambiguous / incomplete.

    Addendum schema: ``label_status`` is ``complete`` (not ``ok``). Incomplete
    labels are trained as needless (no ASK), same as ``ambiguous``.
    """
    if str(row.get("label_status") or "") != "complete":
        return "incomplete"
    if row.get("needed") is True:
        return "needed"
    if row.get("needless") is True:
        return "needless"
    if row.get("ambiguous") is True:
        return "ambiguous"
    return "ambiguous"


def load_branch_labels(
    labels_jsonl: Path | str,
) -> tuple[dict[tuple[Any, str, int], dict[str, Any]], dict[str, Any]]:
    """Index labels by ``(seed, task_id, i)``. Last duplicate wins."""
    path = Path(labels_jsonl)
    by_key: dict[tuple[Any, str, int], dict[str, Any]] = {}
    delta_bands: list[Any] = []
    n_rows = 0
    for row in _load_jsonl_rows(path):
        n_rows += 1
        try:
            seed = int(row["seed"])
        except (KeyError, TypeError, ValueError):
            seed = row.get("seed")
        task_id = str(row.get("task_id") or "")
        try:
            i = int(row["i"])
        except (KeyError, TypeError, ValueError):
            continue
        by_key[(seed, task_id, i)] = row
        if "delta_band_delta" in row:
            delta_bands.append(row.get("delta_band_delta"))
    unique_bands: list[Any] = []
    seen: set[str] = set()
    for band in delta_bands:
        key = json.dumps(band, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique_bands.append(band)
    stats = {
        "n_label_rows": n_rows,
        "n_label_keys": len(by_key),
        "delta_band_delta": unique_bands[0] if len(unique_bands) == 1 else unique_bands,
        "labels_sha256": _sha256_file(path),
        "labels_path": str(path),
    }
    return by_key, stats


def _rewrite_needed_events(events: list[Event], needed_i: set[int]) -> list[Event]:
    """Insert an honoured ASK before each needed intervention.

    ``_history_from_events`` already turns that into ASK_PLANNER then ANSWER.
    """
    if not needed_i:
        return list(events)
    out: list[Event] = []
    iv_i = 0
    ask_action = ExecutorAction(
        kind="ASK_PLANNER",
        ask_reason=ASK_REASON,
        raw_output=ASK_TEMPLATE,
    )
    for ev in events:
        if ev.event_type != "intervention":
            out.append(ev)
            continue
        if iv_i in needed_i:
            out.append(
                ev.model_copy(
                    update={
                        "event_type": "action",
                        "actor": "executor",
                        "payload": ask_action.model_dump(),
                        "usage": None,
                    }
                )
            )
            out.append(
                ev.model_copy(
                    update={
                        "event_type": "ask",
                        "actor": "executor",
                        "payload": {
                            "honoured": True,
                            "ask_reason": ASK_REASON,
                            "n_asks": iv_i + 1,
                            "gated": False,
                        },
                        "usage": None,
                    }
                )
            )
            payload = dict(ev.payload or {})
            payload["forced"] = False
            out.append(ev.model_copy(update={"payload": payload}))
        else:
            out.append(ev)
        iv_i += 1
    return out


def _next_assistant(history: list[dict], start: int) -> dict | None:
    for later in history[start:]:
        if later.get("role") == "assistant":
            return later
    return None


def _collect_supervised_targets(
    history: list[dict],
) -> tuple[list[dict], list[dict], int, int]:
    """Identify ASK and post-intervention action turns in a rendered history."""
    action_targets: list[dict] = []
    ask_targets: list[dict] = []
    n_ask_post = 0
    n_no_post = 0
    i = 0
    n = len(history)
    while i < n:
        msg = history[i]
        content = str(msg.get("content") or "")
        if _sft._is_intervention_turn(msg):
            target = _next_assistant(history, i + 1)
            if target is None:
                n_no_post += 1
            elif _sft._is_ask_planner_content(str(target.get("content") or "")):
                n_ask_post += 1
            else:
                action_targets.append(target)
            i += 1
            continue
        if msg.get("role") == "assistant" and content == ASK_TEMPLATE:
            ask_targets.append(msg)
            j = i + 1
            if (
                j < n
                and history[j].get("role") == "user"
                and str(history[j].get("content") or "").startswith("ANSWER:")
            ):
                j += 1
            target = _next_assistant(history, j)
            if target is None:
                n_no_post += 1
            elif _sft._is_ask_planner_content(str(target.get("content") or "")):
                n_ask_post += 1
            else:
                action_targets.append(target)
            i = j
            continue
        i += 1
    return action_targets, ask_targets, n_ask_post, n_no_post


def _index_of_identity(messages: list[dict], target: dict) -> int:
    for i, msg in enumerate(messages):
        if msg is target:
            return i
    raise ValueError("supervised target is not in the rendered message list")


def _prepare_episode_messages(
    history: list[dict],
    *,
    instruction: str,
    api_docs: str,
    packet: DelegationPacket | None,
    strip_interventions: bool,
) -> tuple[list[dict], list[int], list[int], int, int] | None:
    """Render one episode. None when there is no action target (keeps the pair aligned)."""
    action_targets, ask_targets, n_ask_post, n_no_post = _collect_supervised_targets(history)
    if not action_targets:
        return None
    working = list(history)
    if strip_interventions:
        working = [m for m in working if not _sft._is_intervention_turn(m)]
    last = action_targets[-1]
    cut = None
    for i, msg in enumerate(working):
        if msg is last:
            cut = i
    if cut is None:
        return None
    working = working[: cut + 1]
    messages = render_executor_messages(
        instruction=instruction,
        api_docs=api_docs,
        packet=packet,
        history=working,
    )
    action_indices = [_index_of_identity(messages, t) for t in action_targets]
    ask_indices = [_index_of_identity(messages, t) for t in ask_targets]
    return messages, action_indices, ask_indices, n_ask_post, n_no_post


def _mask_meta(action_indices: list[int], ask_indices: list[int]) -> dict[str, Any]:
    indices = sorted(set(action_indices) | set(ask_indices))
    meta: dict[str, Any] = {
        "supervised_message_indices": indices,
        "n_action_targets": len(action_indices),
        "n_ask_targets": len(ask_indices),
    }
    if len(indices) == 1:
        meta["supervise_last_assistant_only"] = True
        meta["supervised_message_index"] = indices[0]
    return meta


def _label_for_point(
    labels: dict[tuple[Any, str, int], dict[str, Any]] | None,
    seed: Any,
    task_id: str,
    i: int,
) -> tuple[str, dict[str, Any] | None]:
    if labels is None:
        return "needless", None
    row = labels.get((seed, task_id, i))
    if row is None and isinstance(seed, int):
        row = labels.get((str(seed), task_id, i))
    if row is None:
        return "incomplete", None
    return classify_branch_label(row), row


def _build_correction_records(
    campaign_root,
    split_ids,
    *,
    strip_interventions: bool = True,
    system: str = "fixed_k",
    labels: dict[tuple[Any, str, int], dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    campaign_root = Path(campaign_root)
    train_ids = {str(x) for x in split_ids}
    heldout = _sft._heldout_task_ids()
    assert_no_leakage(train_ids, heldout)

    dropped: list[dict[str, Any]] = []
    dropped_counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    token_lengths: list[int] = []
    tokenizer = _sft._try_tokenizer()
    n_missing_api_docs = 0
    n_truncated = 0
    n_messages_dropped_total = 0
    n_unrepresentable = 0
    truncated_run_ids: list[str] = []
    n_interventions_seen = 0
    n_forced_true = 0
    n_ask_events = 0
    n_ask_planner_targets = 0
    n_action_targets = 0
    n_ask_targets = 0
    n_needed = 0
    n_needless = 0
    n_ambiguous = 0
    n_incomplete = 0
    n_ambiguous_treated_as_needless = 0

    def drop(task_id: str, seed: Any, reason: str, extra: str | None = None) -> None:
        dropped_counts[reason] = dropped_counts.get(reason, 0) + 1
        rec: dict[str, Any] = {"task_id": task_id, "seed": seed, "reason": reason}
        if extra:
            rec["detail"] = extra
        dropped.append(rec)

    system_root = campaign_root / system
    if system_root.is_dir():
        for seed_dir in sorted(p for p in system_root.iterdir() if p.is_dir()):
            try:
                seed = int(seed_dir.name)
            except ValueError:
                seed = seed_dir.name
            for task_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
                task_id = task_dir.name
                if task_id not in train_ids:
                    drop(task_id, seed, DROP_NOT_IN_SPLIT)
                    continue
                result_path = task_dir / "result.json"
                events_path = task_dir / "events.jsonl"
                if not result_path.is_file():
                    drop(task_id, seed, DROP_MISSING_RESULT)
                    continue
                result = _sft._read_json(result_path) or {}
                if not events_path.is_file():
                    drop(task_id, seed, DROP_MISSING_EVENTS)
                    continue
                events = _sft._events_after_last_run_start(events_path)
                n_ask_events += sum(1 for ev in events if ev.event_type == "ask")
                iv_events = [ev for ev in events if ev.event_type == "intervention"]
                n_iv = len(iv_events)
                n_forced_true += sum(1 for ev in iv_events if (ev.payload or {}).get("forced") is True)
                n_interventions_seen += n_iv
                if n_iv == 0:
                    drop(task_id, seed, DROP_NO_INTERVENTION)
                    continue
                needed_i: set[int] = set()
                for i in range(n_iv):
                    kind, _row = _label_for_point(labels, seed, task_id, i)
                    if kind == "needed":
                        n_needed += 1
                        needed_i.add(i)
                    elif kind == "needless":
                        n_needless += 1
                    elif kind == "ambiguous":
                        n_ambiguous += 1
                        n_ambiguous_treated_as_needless += 1
                    else:
                        n_incomplete += 1
                        n_ambiguous_treated_as_needless += 1
                use_events = events
                if labels is not None:
                    patched: list = []
                    iv_i = 0
                    for ev in events:
                        if ev.event_type != "intervention":
                            patched.append(ev)
                            continue
                        _kind, row = _label_for_point(labels, seed, task_id, iv_i)
                        if row and row.get("correction"):
                            payload = dict(ev.payload or {})
                            payload["correction"] = str(row["correction"])
                            ev = ev.model_copy(update={"payload": payload})
                        patched.append(ev)
                        iv_i += 1
                    use_events = _rewrite_needed_events(patched, needed_i)
                instruction, packet, api_docs, history = _sft._history_from_events(use_events)
                if not instruction:
                    drop(task_id, seed, DROP_NO_INSTRUCTION)
                    continue
                prepared = _prepare_episode_messages(
                    history,
                    instruction=instruction,
                    api_docs=api_docs,
                    packet=packet,
                    strip_interventions=strip_interventions,
                )
                if prepared is None:
                    # Distinguish ASK-only post-actions from missing post-actions.
                    _, _, n_ask_post, n_no_post = _collect_supervised_targets(history)
                    if n_ask_post and n_no_post == 0:
                        n_ask_planner_targets += n_ask_post
                        drop(task_id, seed, DROP_ASK_PLANNER_TARGET)
                    elif n_no_post:
                        drop(task_id, seed, DROP_NO_POST_INTERVENTION_ACTION)
                    else:
                        drop(task_id, seed, DROP_NO_POST_INTERVENTION_ACTION)
                    continue
                messages, action_indices, ask_indices, n_ask_post, n_no_post = prepared
                n_ask_planner_targets += n_ask_post
                if n_no_post:
                    drop(
                        task_id,
                        seed,
                        DROP_NO_POST_INTERVENTION_ACTION,
                        extra="partial_points_missing_post_action",
                    )
                if strip_interventions and _sft._contains_intervention_mark(messages):
                    drop(task_id, seed, DROP_INTERVENTION_LEAK)
                    continue
                if not api_docs:
                    n_missing_api_docs += 1
                run_id = str(
                    result.get("run_id") or f"{campaign_root.name}/{system}/{seed}/{task_id}"
                )
                commit = _sft._start_commit(task_dir, campaign_root, result)
                tokenized = _sft._check_budget(messages, tokenizer)
                if tokenized["truncated"]:
                    n_truncated += 1
                    n_messages_dropped_total += int(tokenized["n_messages_dropped"])
                    truncated_run_ids.append(run_id)
                if not tokenized["representable"] or not any(
                    lab != -100 for lab in tokenized["labels"]
                ):
                    n_unrepresentable += 1
                    drop(task_id, seed, DROP_UNREPRESENTABLE)
                    continue
                mask = _mask_meta(action_indices, ask_indices)
                meta = {
                    "task_id": task_id,
                    "seed": seed,
                    "run_id": run_id,
                    "n_turns": len(mask["supervised_message_indices"]),
                    "source_campaign": str(result.get("campaign_id") or campaign_root.name),
                    "SIDEKICK_START_COMMIT": commit,
                    "source": "correction",
                    "example_id": run_id,
                    "n_interventions": n_iv,
                    **mask,
                }
                records.append({"messages": messages, "meta": meta})
                token_lengths.append(_sft._conversation_token_length(messages, tokenizer))
                n_action_targets += len(action_indices)
                n_ask_targets += len(ask_indices)

    emitted_ids = [row["meta"]["task_id"] for row in records]
    assert_no_leakage(emitted_ids, heldout)
    summary = {
        "n_sequences": len(records),
        "n_dropped": len(dropped),
        "dropped_counts": dropped_counts,
        "dropped": dropped,
        "task_ids": sorted(set(emitted_ids)),
        "run_ids": [row["meta"]["run_id"] for row in records],
        "n_turns_total": sum(int(row["meta"]["n_turns"]) for row in records),
        "n_missing_api_docs": n_missing_api_docs,
        "n_truncated": n_truncated,
        "n_messages_dropped_total": n_messages_dropped_total,
        "n_unrepresentable": n_unrepresentable,
        "truncated_run_ids": truncated_run_ids,
        "source_campaign_root": str(campaign_root),
        "campaign_sha256": _sha256_campaign(campaign_root, system),
        "source_commit": next(
            (
                row["meta"]["SIDEKICK_START_COMMIT"]
                for row in records
                if row["meta"].get("SIDEKICK_START_COMMIT")
            ),
            None,
        ),
        "system": system,
        "strip_interventions": strip_interventions,
        "n_interventions_seen": n_interventions_seen,
        "n_forced_true": n_forced_true,
        "n_ask_events": n_ask_events,
        "n_ask_planner_targets": n_ask_planner_targets,
        "n_action_targets": n_action_targets,
        "n_ask_targets": n_ask_targets,
        "n_needed": n_needed,
        "n_needless": n_needless,
        "n_ambiguous": n_ambiguous,
        "n_incomplete": n_incomplete,
        "n_ambiguous_treated_as_needless": n_ambiguous_treated_as_needless,
        "_token_lengths": token_lengths,
        "_records": records,
    }
    return records, summary


def build_correction_dataset(
    campaign_root,
    split_ids,
    out_jsonl,
    *,
    strip_interventions: bool = True,
    system: str = "fixed_k",
    quiet: bool = False,
) -> dict:
    """Emit one JSONL line per episode, all post-intervention actions as targets."""
    records, summary = _build_correction_records(
        campaign_root,
        split_ids,
        strip_interventions=strip_interventions,
        system=system,
        labels=None,
    )
    out_path = Path(out_jsonl)
    digest = _sft._emit_jsonl(out_path, records)
    token_lengths = list(summary.pop("_token_lengths") or [])
    summary.pop("_records", None)
    tokenizer_name = "whitespace_fallback"
    if _sft._try_tokenizer() is not None:
        tokenizer_name = "ibm-granite/granite-4.2-8b"
    summary.update(
        {
            "out_jsonl": str(out_path),
            "sha256": digest,
            "token_length_percentiles": {
                "p50": _sft._percentile(token_lengths, 50),
                "p90": _sft._percentile(token_lengths, 90),
                "max": max(token_lengths) if token_lengths else 0,
                "tokenizer": tokenizer_name if token_lengths else tokenizer_name,
            },
        }
    )
    # Prefer the actual tokenizer used during the build if lengths were measured.
    tok = _sft._try_tokenizer()
    summary["token_length_percentiles"]["tokenizer"] = (
        "ibm-granite/granite-4.2-8b" if tok is not None else "whitespace_fallback"
    )
    _sft._write_manifest(out_path, summary, quiet=quiet)
    return summary


def _teacher_sha256_matches_adapter(
    teacher_jsonl: Path, adapter_manifest: Path
) -> tuple[str, str | None, bool]:
    teacher_hash = _sha256_file(teacher_jsonl)
    recorded = None
    if adapter_manifest.is_file():
        data = json.loads(adapter_manifest.read_text(encoding="utf-8"))
        recorded = data.get("data_sha256")
    return teacher_hash, recorded, recorded == teacher_hash if recorded else False


def _combine_teacher_and_correction(
    teacher_jsonl: Path,
    correction_records: list[dict[str, Any]],
    correction_summary: dict[str, Any],
    out_jsonl: Path,
    *,
    quiet: bool,
    extra_summary: dict[str, Any] | None = None,
    adapter_manifest: Path = DEFAULT_ADAPTER_MANIFEST,
) -> dict:
    teacher_rows = _load_jsonl_rows(teacher_jsonl)
    records = list(teacher_rows) + list(correction_records)
    allow_ask_targets = extra_summary is not None
    for row in records:
        if _sft._contains_intervention_mark(row.get("messages") or []):
            raise RuntimeError(
                "combined dataset contains an INTERVENTION: turn; refusing to write"
            )
        messages = row.get("messages") or []
        meta = row.get("meta") or {}
        if meta.get("source") == "correction" and not allow_ask_targets:
            for idx in meta.get("supervised_message_indices") or []:
                if 0 <= int(idx) < len(messages):
                    msg = messages[int(idx)]
                    if msg.get("role") == "assistant" and _sft._is_ask_planner_content(
                        str(msg.get("content") or "")
                    ):
                        raise RuntimeError(
                            "combined sft_b_plus contains an ASK_PLANNER correction target"
                        )
    heldout = _sft._heldout_task_ids()
    emitted_ids = [str((row.get("meta") or {}).get("task_id") or "") for row in records]
    assert_no_leakage([i for i in emitted_ids if i], heldout)
    out_jsonl = Path(out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    teacher_bytes = Path(teacher_jsonl).read_bytes()
    with open(out_jsonl, "wb") as fh:
        fh.write(teacher_bytes)
        if teacher_bytes and not teacher_bytes.endswith(b"\n"):
            fh.write(b"\n")
        for row in correction_records:
            fh.write((json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    digest = hashlib.sha256(out_jsonl.read_bytes()).hexdigest()
    tokenizer = _sft._try_tokenizer()
    token_lengths = [
        _sft._conversation_token_length(row["messages"], tokenizer) for row in records
    ]
    teacher_hash, adapter_hash, teacher_ok = _teacher_sha256_matches_adapter(
        teacher_jsonl, adapter_manifest
    )
    n_action = sum(
        int((row.get("meta") or {}).get("n_action_targets") or 0)
        for row in correction_records
    )
    n_ask = sum(
        int((row.get("meta") or {}).get("n_ask_targets") or 0)
        for row in correction_records
    )
    n_teacher_action = 0
    for row in teacher_rows:
        n_teacher_action += sum(
            1 for m in (row.get("messages") or []) if m.get("role") == "assistant"
        )
    dropped_counts: dict[str, int] = {}
    for key, val in (correction_summary.get("dropped_counts") or {}).items():
        dropped_counts[f"correction_{key}"] = int(val)
    slim_corr = {
        k: v
        for k, v in correction_summary.items()
        if k not in {"dropped", "_records", "_token_lengths"} and not str(k).startswith("_")
    }
    summary: dict[str, Any] = {
        "out_jsonl": str(out_jsonl),
        "n_sequences": len(records),
        "n_teacher_sequences": len(teacher_rows),
        "n_correction_sequences": len(correction_records),
        "n_dropped": int(correction_summary.get("n_dropped") or 0),
        "dropped_counts": dropped_counts,
        "dropped": [
            {**d, "part": "correction"} for d in (correction_summary.get("dropped") or [])
        ],
        "task_ids": sorted({i for i in emitted_ids if i}),
        "run_ids": [(row.get("meta") or {}).get("run_id") for row in records],
        "n_unrepresentable": int(correction_summary.get("n_unrepresentable") or 0),
        "n_truncated": int(correction_summary.get("n_truncated") or 0),
        "n_messages_dropped_total": int(
            correction_summary.get("n_messages_dropped_total") or 0
        ),
        "teacher_jsonl": str(teacher_jsonl),
        "teacher_sha256": teacher_hash,
        "adapter_manifest": str(adapter_manifest),
        "adapter_data_sha256": adapter_hash,
        "teacher_sha256_matches_adapter": teacher_ok,
        "campaign_sha256": correction_summary.get("campaign_sha256"),
        "correction_campaign_root": correction_summary.get("source_campaign_root"),
        "source_commit": correction_summary.get("source_commit"),
        "sha256": digest,
        "token_length_percentiles": {
            "p50": _sft._percentile(token_lengths, 50),
            "p90": _sft._percentile(token_lengths, 90),
            "max": max(token_lengths) if token_lengths else 0,
            "tokenizer": (
                "ibm-granite/granite-4.2-8b"
                if tokenizer is not None
                else "whitespace_fallback"
            ),
        },
        "n_ask_planner_targets": int(correction_summary.get("n_ask_planner_targets") or 0),
        "n_action_targets": n_action,
        "n_ask_targets": n_ask,
        "n_interventions_seen": int(correction_summary.get("n_interventions_seen") or 0),
        "n_forced_true": int(correction_summary.get("n_forced_true") or 0),
        "n_ask_events": int(correction_summary.get("n_ask_events") or 0),
        "correction": slim_corr,
    }
    if extra_summary:
        summary.update(extra_summary)
    _sft._write_manifest(out_jsonl, summary, quiet=quiet)
    return summary


def build_sft_b_plus(
    correction_campaign_root,
    split_ids,
    out_jsonl,
    *,
    teacher_jsonl: Path | str = DEFAULT_TEACHER_JSONL,
    correction_system: str = "fixed_k",
    strip_interventions: bool = True,
    quiet: bool = False,
    adapter_manifest: Path | str = DEFAULT_ADAPTER_MANIFEST,
    **_ignored: Any,
) -> dict:
    """Frozen teacher jsonl plus per-episode J4 correction sequences. No ASK targets."""
    teacher_path = Path(teacher_jsonl)
    if not teacher_path.is_file():
        raise FileNotFoundError(f"teacher jsonl not found: {teacher_path}")
    records, corr_summary = _build_correction_records(
        correction_campaign_root,
        split_ids,
        strip_interventions=strip_interventions,
        system=correction_system,
        labels=None,
    )
    corr_summary.pop("_token_lengths", None)
    corr_summary.pop("_records", None)
    return _combine_teacher_and_correction(
        teacher_path,
        records,
        corr_summary,
        Path(out_jsonl),
        quiet=quiet,
        extra_summary=None,
        adapter_manifest=Path(adapter_manifest),
    )


def build_ask_dataset(
    campaign_root,
    split_ids,
    labels_jsonl,
    out_jsonl,
    *,
    teacher_jsonl: Path | str = DEFAULT_TEACHER_JSONL,
    correction_system: str = "fixed_k",
    strip_interventions: bool = True,
    quiet: bool = False,
    adapter_manifest: Path | str = DEFAULT_ADAPTER_MANIFEST,
    **_ignored: Any,
) -> dict:
    """sft_c: same episodes as sft_b_plus; ASK only at complete needed points."""
    teacher_path = Path(teacher_jsonl)
    if not teacher_path.is_file():
        raise FileNotFoundError(f"teacher jsonl not found: {teacher_path}")
    labels, label_stats = load_branch_labels(labels_jsonl)
    records, corr_summary = _build_correction_records(
        campaign_root,
        split_ids,
        strip_interventions=strip_interventions,
        system=correction_system,
        labels=labels,
    )
    extra = {
        "n_needed": corr_summary.get("n_needed"),
        "n_needless": corr_summary.get("n_needless"),
        "n_ambiguous": corr_summary.get("n_ambiguous"),
        "n_incomplete": corr_summary.get("n_incomplete"),
        "n_ambiguous_treated_as_needless": corr_summary.get(
            "n_ambiguous_treated_as_needless"
        ),
        "delta_band_delta": label_stats.get("delta_band_delta"),
        "labels_jsonl": str(labels_jsonl),
        "labels_sha256": label_stats.get("labels_sha256"),
    }
    corr_summary.pop("_token_lengths", None)
    corr_summary.pop("_records", None)
    return _combine_teacher_and_correction(
        teacher_path,
        records,
        corr_summary,
        Path(out_jsonl),
        quiet=quiet,
        extra_summary=extra,
        adapter_manifest=Path(adapter_manifest),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build matched sft_b_plus / sft_c JSONL.")
    parser.add_argument("--mode", choices=("sft_b_plus", "sft_c"), default="sft_b_plus")
    parser.add_argument("--campaign-root", default=str(DEFAULT_CORRECTION_CAMPAIGN))
    parser.add_argument("--correction-campaign-root", default=None)
    parser.add_argument("--teacher-jsonl", default=str(DEFAULT_TEACHER_JSONL))
    parser.add_argument("--labels-jsonl", default=None)
    parser.add_argument("--split", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--correction-system", default="fixed_k")
    parser.add_argument("--no-strip-interventions", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    split_ids = load_split_ids(args.split)
    corr_root = args.correction_campaign_root or args.campaign_root
    strip = not args.no_strip_interventions
    if args.mode == "sft_c":
        if not args.labels_jsonl:
            parser.error("--mode sft_c requires --labels-jsonl")
        build_ask_dataset(
            corr_root,
            split_ids,
            args.labels_jsonl,
            args.out,
            teacher_jsonl=args.teacher_jsonl,
            correction_system=args.correction_system,
            strip_interventions=strip,
        )
        return 0
    build_sft_b_plus(
        corr_root,
        split_ids,
        args.out,
        teacher_jsonl=args.teacher_jsonl,
        correction_system=args.correction_system,
        strip_interventions=strip,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
