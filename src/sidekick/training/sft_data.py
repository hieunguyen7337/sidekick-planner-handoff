"""Build an SFT JSONL from campaign event logs, using the shared executor renderer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from sidekick.protocols.prompts import (
    EXECUTOR_SYSTEM_PROMPT,
    format_executor_action,
    fit_messages_to_budget,
    render_executor_messages,
)
from sidekick.protocols.schemas import (
    ActionParseError,
    DelegationPacket,
    Event,
    ExecutorAction,
    parse_executor_action,
)
from sidekick.training import assert_no_leakage

HELDOUT_SPLITS = ("dev", "test_normal", "test_challenge")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_DEFAULT_TOKENIZER_ID = "ibm-granite/granite-4.2-8b"


def resolve_tokenizer_id(name: str | None = None) -> str:
    """Single source for the tokenizer / base-model identifier.

    An explicit ``name`` wins, then ``SIDEKICK_TOKENIZER_ID``, then granite.
    A run that sets nothing keeps today's granite default.
    """
    if isinstance(name, str) and name.strip():
        return name.strip()
    env = os.environ.get("SIDEKICK_TOKENIZER_ID", "").strip()
    if env:
        return env
    return _DEFAULT_TOKENIZER_ID


def tokenizer_label(tokenizer: Any | None, name: str | None = None) -> str:
    if tokenizer is None:
        return "whitespace_fallback"
    return resolve_tokenizer_id(name)

# Trajectories dropped for these reasons are counted in the manifest.
DROP_UNSOLVED = "unsolved"
DROP_BELOW_GOAL_PASS_RATE = "below_goal_pass_rate"
DROP_MISSING_RESULT = "missing_result"
DROP_MISSING_EVENTS = "missing_events"
DROP_NOT_IN_SPLIT = "not_in_split"
DROP_NO_INSTRUCTION = "no_instruction"
DROP_NO_ACTIONS = "no_actions"
DROP_BAD_RESULT = "bad_result"
DROP_UNREPRESENTABLE = "unrepresentable"
DROP_NO_INTERVENTION = "no_intervention"
DROP_NO_POST_INTERVENTION_ACTION = "no_post_intervention_action"
DROP_ASK_PLANNER_TARGET = "ask_planner_target"
DROP_INTERVENTION_LEAK = "intervention_in_context"

INTERVENTION_MARK = "INTERVENTION:"
ASK_REASON = "Review my progress so far and tell me the next step."
ASK_TEMPLATE = f"ASK_PLANNER: {ASK_REASON}"

class SidekickRootError(RuntimeError):
    """A default run-tree path was needed but SIDEKICK_ROOT is not set."""


# Relative to SIDEKICK_ROOT. The original runs used SIDEKICK_ROOT=/scratch/<user>/sidekick on QUT Aqua.
TEACHER_JSONL_REL = "artifacts/sft/sft_b_s123_p075.jsonl"
ADAPTER_MANIFEST_REL = "artifacts/adapters/sft_b_s123_granite8b/manifest.json"
CORRECTION_CAMPAIGN_REL = "results/hj4_correction_train_20260917"


def sidekick_root() -> Path:
    """The run tree that holds artifacts/ and results/, read from SIDEKICK_ROOT at call time."""
    raw = os.environ.get("SIDEKICK_ROOT")
    if not raw:
        raise SidekickRootError(
            "SIDEKICK_ROOT is not set. Export SIDEKICK_ROOT=<dir> pointing at the run tree that "
            "holds artifacts/ and results/, or pass the path explicitly."
        )
    return Path(raw)


def default_teacher_jsonl() -> Path:
    return sidekick_root() / TEACHER_JSONL_REL


def default_adapter_manifest() -> Path:
    return sidekick_root() / ADAPTER_MANIFEST_REL


def default_correction_campaign() -> Path:
    return sidekick_root() / CORRECTION_CAMPAIGN_REL


def _heldout_task_ids() -> list[str]:
    """Load AppWorld held-out splits. Must not be skipped: a silent leak invalidates every number."""
    from appworld import load_task_ids

    ids: list[str] = []
    for split in HELDOUT_SPLITS:
        ids.extend(str(x) for x in load_task_ids(split))
    if not ids:
        raise RuntimeError(
            "held-out split ids were empty; refusing to skip the leakage check"
        )
    return ids


def load_split_ids(spec: str) -> list[str]:
    """Load train task ids from a file, a comma-separated list, or an AppWorld split name."""
    path = Path(spec)
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x) for x in data]
            if isinstance(data, dict):
                raw = data.get("task_ids") or data.get("ids") or data.get("train")
                if isinstance(raw, list):
                    return [str(x) for x in raw]
            raise ValueError(f"unrecognised JSON split file: {path}")
        return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if "," in spec:
        return [part.strip() for part in spec.split(",") if part.strip()]
    from appworld import load_task_ids

    return [str(x) for x in load_task_ids(spec)]


def _events_after_last_run_start(path: Path) -> list[Event]:
    """Keep only events after the LAST run_start, in file order (never by ts).

    A retried run appends to the dead attempt's log (docs/FOLLOWUPS.md). AppWorld
    freezes time with freezegun, so Event.ts is identical across events.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    last_run_start = -1
    parsed: list[tuple[int, dict[str, Any]]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        parsed.append((i, obj))
        if obj.get("event_type") == "run_start":
            last_run_start = i
    events: list[Event] = []
    for i, obj in parsed:
        if i <= last_run_start:
            continue
        try:
            events.append(Event.model_validate(obj))
        except Exception:
            continue
    return events


def _action_from_payload(payload: dict[str, Any]) -> ExecutorAction | None:
    if not isinstance(payload, dict):
        return None
    try:
        return ExecutorAction.model_validate(payload)
    except Exception:
        keep = {
            k: payload[k]
            for k in ("kind", "code", "message", "ask_reason", "confidence", "raw_output")
            if k in payload
        }
        keep.setdefault("raw_output", "")
        try:
            return ExecutorAction.model_validate(keep)
        except Exception:
            return None


def _looks_like_docs(text: str) -> bool:
    s = text.strip()
    return bool(s) and not _SHA256_HEX.match(s)


def _api_docs_from_appworld(task_id: str) -> str:
    """Rebuild the inference-time API listing. Events do not store api_docs_prompt."""
    try:
        from appworld.task import Task
        from sidekick.environments.appworld_env import _summarise_api_docs

        task = Task.load(task_id)
        docs = _summarise_api_docs(getattr(task, "api_docs", "") or "")
        if isinstance(docs, str) and _looks_like_docs(docs):
            return docs
    except Exception:
        return ""
    return ""


def _recover_api_docs(events: list[Event], task_id: str) -> str:
    for ev in events:
        payload = ev.payload or {}
        for key in ("api_docs_prompt", "api_docs"):
            val = payload.get(key)
            if isinstance(val, str) and _looks_like_docs(val):
                return val
        packet = payload.get("packet")
        if isinstance(packet, dict):
            for key in ("api_docs_prompt", "api_docs"):
                val = packet.get(key)
                if isinstance(val, str) and _looks_like_docs(val):
                    return val
    return _api_docs_from_appworld(task_id)


def _history_from_events(events: list[Event]) -> tuple[str, DelegationPacket | None, str, list[dict]]:
    """Replay loop.py exec_turns construction from the live attempt's events."""
    instruction = ""
    packet: DelegationPacket | None = None
    api_docs = ""
    history: list[dict] = []
    pending: ExecutorAction | None = None
    awaiting_ask_outcome = False
    seen_initial_obs = False

    def flush_assistant(action: ExecutorAction) -> None:
        history.append({"role": "assistant", "content": format_executor_action(action)})

    for ev in events:
        payload = ev.payload or {}
        if ev.event_type == "plan" and isinstance(payload.get("packet"), dict):
            try:
                packet = DelegationPacket.model_validate(payload["packet"])
            except Exception:
                packet = packet
            continue
        if ev.event_type == "observation":
            if pending is None and not seen_initial_obs:
                seen_initial_obs = True
                text = payload.get("text")
                if isinstance(text, str) and text:
                    instruction = text
                continue
            if pending is not None:
                flush_assistant(pending)
                history.append({"role": "user", "content": f"OBS: {payload.get('text', '')}"})
                pending = None
                awaiting_ask_outcome = False
            continue
        if ev.event_type == "action":
            if pending is not None:
                flush_assistant(pending)
                pending = None
                awaiting_ask_outcome = False
            pending = _action_from_payload(payload)
            continue
        if ev.event_type == "report":
            if pending is not None:
                flush_assistant(pending)
                pending = None
                awaiting_ask_outcome = False
            continue
        if ev.event_type == "ask":
            if pending is None:
                continue
            if payload.get("honoured") is False:
                flush_assistant(pending)
                history.append({"role": "user", "content": "ASK_IGNORED"})
                pending = None
                awaiting_ask_outcome = False
            else:
                awaiting_ask_outcome = True
            continue
        if ev.event_type == "intervention":
            correction = str(payload.get("correction") or "")
            if payload.get("forced"):
                history.append({"role": "user", "content": f"INTERVENTION: {correction}"})
            elif awaiting_ask_outcome and pending is not None:
                flush_assistant(pending)
                history.append({"role": "user", "content": f"ANSWER: {correction}"})
                pending = None
                awaiting_ask_outcome = False
            else:
                history.append({"role": "user", "content": f"INTERVENTION: {correction}"})
            continue

    api_docs = _recover_api_docs(events, events[0].task_id if events else "")
    return instruction, packet, api_docs, history


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _start_commit(run_dir: Path, campaign_root: Path, result: dict[str, Any]) -> str | None:
    keys = ("SIDEKICK_START_COMMIT", "start_commit", "git_commit")
    for candidate in (
        run_dir / "manifest.json",
        campaign_root / "manifest.json",
        campaign_root.parent / "results" / campaign_root.name / "manifest.json",
    ):
        data = _read_json(candidate)
        if not data:
            continue
        for key in keys:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    for key in keys:
        val = result.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    env = os.environ.get("SIDEKICK_START_COMMIT", "").strip()
    return env or None


def _encode_text(tokenizer: Any | None, text: str) -> list[int]:
    if tokenizer is None:
        # The builder uses this only when the local model tokenizer is unavailable.  The
        # ids are placeholders, but preserving one id per whitespace token still lets it
        # account for truncation without downloading a tokenizer.
        return list(range(len(text.split())))
    encode = getattr(tokenizer, "encode", None)
    if callable(encode):
        try:
            ids = encode(text, add_special_tokens=False)
        except TypeError:
            ids = encode(text)
        if isinstance(ids, list) and (not ids or isinstance(ids[0], int)):
            return list(ids)
    out = tokenizer(text, add_special_tokens=False)
    if isinstance(out, dict):
        return list(out["input_ids"])
    return list(out.input_ids)


def _tokenize_messages(
    messages: list[dict],
    tokenizer: Any | None,
    *,
    supervised_indices: set[int] | None = None,
) -> dict[str, list[int]]:
    """Tokenise a complete, already-selected conversation and apply assistant masking.

    When ``supervised_indices`` is None, every assistant turn is supervised (teacher
    SFT). When it is a set, only those message indices receive labels — used for
    correction examples where loss is restricted to the post-intervention action.
    """
    input_ids: list[int] = []
    labels: list[int] = []
    prev_ids: list[int] = []
    apply = getattr(tokenizer, "apply_chat_template", None)
    for i, msg in enumerate(messages):
        prefix = messages[: i + 1]
        if callable(apply):
            text = apply(prefix, tokenize=False, add_generation_prompt=False)
        else:
            text = "".join(f"<{m['role']}>{m.get('content', '')}</{m['role']}>" for m in prefix)
        curr = _encode_text(tokenizer, text)
        if curr[: len(prev_ids)] == prev_ids:
            new_ids = curr[len(prev_ids) :]
            keep = len(prev_ids)
        else:
            keep = 0
            for a, b in zip(prev_ids, curr):
                if a != b:
                    break
                keep += 1
            labels = labels[:keep]
            new_ids = curr[keep:]
        is_supervised = msg.get("role") == "assistant" and (
            supervised_indices is None or i in supervised_indices
        )
        if is_supervised:
            labels.extend(new_ids)
        else:
            labels.extend([-100] * len(new_ids))
        input_ids = curr
        prev_ids = curr
    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


def tokenize_and_mask(
    messages: list[dict],
    tokenizer: Any | None,
    *,
    max_length: int | None = 32768,
) -> dict[str, Any]:
    """Tokenise turn by turn; labels are -100 everywhere except assistant-turn tokens.

    Does not use chat-template ``{% generation %}`` markers. Assistant spans are the
    token delta between ``apply_chat_template(messages[:i])`` and
    ``apply_chat_template(messages[:i+1])`` for each assistant message.
    """
    full = _tokenize_messages(messages, tokenizer)
    if max_length is None or len(full["input_ids"]) <= max_length:
        return {
            **full,
            "n_messages_dropped": 0,
            "n_chars_elided": 0,
            "truncated": False,
            "representable": True,
        }

    # Keep the framing messages and the terminal message as indivisible anchors.  The
    # only messages eligible for removal are the oldest messages between the framing
    # pair and the final message.  Oversized anchor *content* is middle-elided by the
    # same helper serving uses, so the SFT prompt matches inference.
    def _length_fn(ms: list[dict]) -> int:
        return len(_tokenize_messages(ms, tokenizer)["input_ids"])

    fit = fit_messages_to_budget(
        messages, max_tokens=max_length, length_fn=_length_fn
    )
    selected = fit.selected
    n_messages_dropped = fit.n_messages_dropped
    representable = fit.representable
    n_chars_elided = fit.n_chars_elided
    if not representable:
        # No valid under-budget representation exists.  Return the unmodified tokenisation
        # so the caller can drop it explicitly instead of receiving a damaged target.
        return {
            **full,
            "n_messages_dropped": 0,
            "n_chars_elided": 0,
            "truncated": False,
            "representable": False,
        }

    selected_output = (
        _tokenize_messages(selected, tokenizer)
        if n_messages_dropped or n_chars_elided
        else full
    )
    return {
        **selected_output,
        "n_messages_dropped": n_messages_dropped,
        "n_chars_elided": n_chars_elided,
        "truncated": n_messages_dropped > 0 or n_chars_elided > 0,
        "representable": True,
    }



def _check_budget(
    messages: list[dict],
    tokenizer: Any | None,
    *,
    max_length: int | None = 32768,
) -> dict[str, Any]:
    """Representable/truncated flags without prefix-walking every in-budget example.

    Under-budget conversations need only one full ``apply_chat_template``; that is
    the same first branch as ``tokenize_and_mask``. Over-budget examples still go
    through ``tokenize_and_mask`` / ``fit_messages_to_budget`` unchanged.
    """
    n_tokens = _conversation_token_length(messages, tokenizer)
    if max_length is None or n_tokens <= max_length:
        return {
            "representable": True,
            "truncated": False,
            "n_messages_dropped": 0,
            "n_tokens": n_tokens,
            "labels": [0],
        }
    tokenized = tokenize_and_mask(messages, tokenizer, max_length=max_length)
    tokenized = dict(tokenized)
    tokenized["n_tokens"] = n_tokens
    return tokenized


def _try_tokenizer(name: str | None = None) -> Any | None:
    ident = resolve_tokenizer_id(name)
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(
            ident,
            trust_remote_code=True,
            local_files_only=True,
        )
    except Exception:
        return None


def _conversation_token_length(messages: list[dict], tokenizer: Any | None) -> int:
    if tokenizer is not None:
        try:
            apply = getattr(tokenizer, "apply_chat_template", None)
            if callable(apply):
                text = apply(messages, tokenize=False, add_generation_prompt=False)
            else:
                text = "\n".join(str(m.get("content", "")) for m in messages)
            return len(_encode_text(tokenizer, text))
        except Exception:
            pass
    blob = " ".join(str(m.get("content", "")) for m in messages)
    return len(blob.split())


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    k = max(1, int(math.ceil((p / 100.0) * len(ordered))))
    return ordered[k - 1]


def _emit_jsonl(out_path: Path, records: list[dict[str, Any]]) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")
    return hashlib.sha256(out_path.read_bytes()).hexdigest()


def build_sft_dataset(
    campaign_root,
    split_ids,
    out_jsonl,
    *,
    system="planner_alone",
    solved_only=True,
    min_goal_pass_rate: float | None = None,
    quiet: bool = False,
    tokenizer_id: str | None = None,
) -> dict:
    """Emit one JSONL line per solved trajectory, rendered with ``render_executor_messages``.

    ``min_goal_pass_rate`` adds partial-credit trajectories on top of the solved
    ones: an unsolved trajectory is included when its ``goal_pass_rate`` is not
    None and >= the threshold. A ``None`` goal_pass_rate is never a pass and is
    never compared with ``>=``. Included partials have their terminal COMPLETE
    assistant turn removed before tokenisation, so the model is never trained to
    declare victory on an unfinished task.
    """
    campaign_root = Path(campaign_root)
    out_path = Path(out_jsonl)
    train_ids = {str(x) for x in split_ids}
    heldout = _heldout_task_ids()
    # Unconditional: never hide this behind a flag.
    assert_no_leakage(train_ids, heldout)

    dropped: list[dict[str, Any]] = []
    dropped_counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    token_lengths: list[int] = []
    tokenizer = _try_tokenizer(tokenizer_id)
    system_root = campaign_root / system
    n_missing_api_docs = 0
    n_truncated = 0
    n_messages_dropped_total = 0
    n_unrepresentable = 0
    truncated_run_ids: list[str] = []
    n_solved = 0
    n_partial = 0
    n_terminal_actions_removed = 0
    n_trailing_observations_removed = 0
    partial_goal_pass_rates: list[float] = []
    goal_pass_rate_histogram_unsolved: dict[str, int] = {f"{i / 10:.1f}": 0 for i in range(10)}
    goal_pass_rate_histogram_unsolved["none"] = 0

    def drop(task_id: str, seed: Any, reason: str, extra: str | None = None) -> None:
        dropped_counts[reason] = dropped_counts.get(reason, 0) + 1
        rec: dict[str, Any] = {"task_id": task_id, "seed": seed, "reason": reason}
        if extra:
            rec["detail"] = extra
        dropped.append(rec)

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
                result = _read_json(result_path)
                if result is None:
                    drop(task_id, seed, DROP_BAD_RESULT)
                    continue
                success = bool(result.get("success"))
                goal_pass_rate = result.get("goal_pass_rate")
                is_partial = False
                if not success:
                    # Histogram counts EVERY in-split unsolved trajectory, whether
                    # or not the threshold includes it, so the next threshold can
                    # be chosen empirically. Nulls get their own bucket.
                    if goal_pass_rate is None:
                        goal_pass_rate_histogram_unsolved["none"] += 1
                    else:
                        bin_key = f"{min(int(goal_pass_rate * 10), 9) / 10:.1f}"
                        goal_pass_rate_histogram_unsolved[bin_key] += 1
                    if solved_only:
                        if min_goal_pass_rate is None:
                            drop(task_id, seed, DROP_UNSOLVED)
                            continue
                        if goal_pass_rate is None:
                            drop(task_id, seed, DROP_UNSOLVED, "goal_pass_rate null")
                            continue
                        if not (goal_pass_rate >= min_goal_pass_rate):
                            drop(task_id, seed, DROP_BELOW_GOAL_PASS_RATE, f"goal_pass_rate={goal_pass_rate}")
                            continue
                        is_partial = True
                if not events_path.is_file():
                    drop(task_id, seed, DROP_MISSING_EVENTS)
                    continue
                events = _events_after_last_run_start(events_path)
                instruction, packet, api_docs, history = _history_from_events(events)
                if not instruction:
                    drop(task_id, seed, DROP_NO_INSTRUCTION)
                    continue
                if is_partial:
                    # Unfinished tasks often end in a terminal COMPLETE for a task
                    # that was NOT completed. Train on that and you teach early
                    # victory. Remove the final COMPLETE assistant turn (the turn,
                    # not a mask) for partials ONLY; solved trajectories keep it.
                    # Match on the parsed action kind, never on rendered text. The
                    # last history entry may be the user OBS turn that followed the
                    # terminal action, so scan backwards for the last assistant turn.
                    for _i in range(len(history) - 1, -1, -1):
                        if history[_i].get("role") != "assistant":
                            continue
                        try:
                            last_kind = parse_executor_action(str(history[_i].get("content") or "")).kind
                        except ActionParseError:
                            last_kind = None
                        if last_kind == "COMPLETE":
                            del history[_i]
                            n_terminal_actions_removed += 1
                            if _i < len(history) and history[_i].get("role") == "user":
                                del history[_i]
                                n_trailing_observations_removed += 1
                        break
                    n_assistant = sum(1 for m in history if m.get("role") == "assistant")
                else:
                    n_assistant = sum(1 for m in history if m.get("role") == "assistant")
                if n_assistant == 0:
                    drop(task_id, seed, DROP_NO_ACTIONS)
                    continue
                if not api_docs:
                    n_missing_api_docs += 1
                messages = render_executor_messages(
                    instruction=instruction,
                    api_docs=api_docs,
                    packet=packet,
                    history=history,
                )
                run_id = str(result.get("run_id") or f"{campaign_root.name}/{system}/{seed}/{task_id}")
                commit = _start_commit(task_dir, campaign_root, result)
                meta = {
                    "task_id": task_id,
                    "seed": seed,
                    "run_id": run_id,
                    "n_turns": n_assistant,
                    "source_campaign": str(result.get("campaign_id") or campaign_root.name),
                    "SIDEKICK_START_COMMIT": commit,
                    "source": "partial" if is_partial else "solved",
                    "goal_pass_rate": goal_pass_rate,
                }
                tokenized = _check_budget(messages, tokenizer)
                if tokenized["truncated"]:
                    n_truncated += 1
                    n_messages_dropped_total += int(tokenized["n_messages_dropped"])
                    truncated_run_ids.append(run_id)
                if not tokenized["representable"]:
                    n_unrepresentable += 1
                    drop(task_id, seed, DROP_UNREPRESENTABLE)
                    continue
                if is_partial:
                    n_partial += 1
                    if goal_pass_rate is not None:
                        partial_goal_pass_rates.append(float(goal_pass_rate))
                else:
                    n_solved += 1
                records.append({"messages": messages, "meta": meta})
                token_lengths.append(_conversation_token_length(messages, tokenizer))

    emitted_ids = [row["meta"]["task_id"] for row in records]
    assert_no_leakage(emitted_ids, heldout)

    digest = _emit_jsonl(out_path, records)
    summary = {
        "out_jsonl": str(out_path),
        "n_trajectories": len(records),
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
        "source_commit": next(
            (row["meta"]["SIDEKICK_START_COMMIT"] for row in records if row["meta"].get("SIDEKICK_START_COMMIT")),
            None,
        ),
        "sha256": digest,
        "token_length_percentiles": {
            "p50": _percentile(token_lengths, 50),
            "p90": _percentile(token_lengths, 90),
            "max": max(token_lengths) if token_lengths else 0,
            "tokenizer": tokenizer_label(tokenizer, tokenizer_id),
        },
        "system": system,
        "solved_only": solved_only,
        "min_goal_pass_rate": min_goal_pass_rate,
        "n_solved": n_solved,
        "n_partial": n_partial,
        "n_terminal_actions_removed": n_terminal_actions_removed,
        "n_trailing_observations_removed": n_trailing_observations_removed,
        "mean_goal_pass_rate_partial": (
            sum(partial_goal_pass_rates) / len(partial_goal_pass_rates)
            if partial_goal_pass_rates
            else None
        ),
        "goal_pass_rate_histogram_unsolved": goal_pass_rate_histogram_unsolved,
        "_token_lengths": token_lengths,
    }
    public = {k: v for k, v in summary.items() if not str(k).startswith("_")}
    manifest_path = Path(str(out_path) + ".manifest.json")
    manifest_path.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not quiet:
        print(json.dumps(public, indent=2, sort_keys=True))
    return summary


def _is_intervention_turn(msg: dict) -> bool:
    if not isinstance(msg, dict):
        return False
    if msg.get("role") != "user":
        return False
    return str(msg.get("content") or "").startswith(INTERVENTION_MARK)


def _contains_intervention_mark(messages: Iterable[dict]) -> bool:
    return any(INTERVENTION_MARK in str(m.get("content") or "") for m in messages)


def _is_ask_planner_content(content: str) -> bool:
    text = str(content or "")
    try:
        return parse_executor_action(text).kind == "ASK_PLANNER"
    except ActionParseError:
        return text.startswith("ASK_PLANNER:")


def _iter_correction_histories(
    history: list[dict],
    *,
    strip_interventions: bool = True,
) -> Iterable[tuple[str, list[dict] | None]]:
    """Yield ``(status, example_history)`` for each intervention in rendered history.

    Status is ``ok``, ``no_post_intervention_action``, or ``ask_planner_target``.
    On ``ok``, ``example_history`` is the surrounding turns as ``_history_from_events``
    rendered them, with ``INTERVENTION:`` turns stripped when requested, ending on
    the post-intervention assistant action.
    """
    for i, msg in enumerate(history):
        if not _is_intervention_turn(msg):
            continue
        target: dict | None = None
        for later in history[i + 1 :]:
            if later.get("role") == "assistant":
                target = later
                break
        if target is None:
            yield DROP_NO_POST_INTERVENTION_ACTION, None
            continue
        if _is_ask_planner_content(str(target.get("content") or "")):
            yield DROP_ASK_PLANNER_TARGET, None
            continue
        prefix = list(history[:i])
        if strip_interventions:
            prefix = [m for m in prefix if not _is_intervention_turn(m)]
        yield "ok", prefix + [dict(target)]


def _map_target_index_after_budget_fit(
    messages: list[dict], selected: list[dict], target_index: int
) -> int | None:
    """Re-find ``messages[target_index]`` inside the budget-fitted ``selected`` list.

    Matching must be by **object identity first**; this executor is documented to
    repeat the same action verbatim (e.g. a second login call after the first), so
    value-equality alone maps the target onto the first of several identical
    turns and silently supervises the wrong one. If identity fails (the caller
    reconstructed the message), fall back to counting positions among
    value-equal messages rather than comparing values alone.
    """
    if target_index < 0 or target_index >= len(messages):
        return None
    orig = messages[target_index]
    hit = next((k for k, m in enumerate(selected) if m is orig), None)
    if hit is not None:
        return hit
    orig_ids = {id(m): i for i, m in enumerate(messages)}
    mapping: dict[int, int] = {}
    taken: set[int] = set()
    unmatched_sel: list[int] = []
    for k, m in enumerate(selected):
        oi = orig_ids.get(id(m))
        if oi is not None and oi not in taken:
            mapping[oi] = k
            taken.add(oi)
        else:
            unmatched_sel.append(k)
    unmatched_orig = [i for i in range(len(messages)) if i not in taken]
    for k, oi in zip(unmatched_sel, unmatched_orig):
        mapping[oi] = k
    return mapping.get(target_index)


def remask_to_message_indices(
    messages: list[dict],
    tokenizer: Any | None,
    target_indices: set[int],
    *,
    max_length: int | None = 32768,
) -> dict[str, Any]:
    """Call ``tokenize_and_mask``, then keep labels only on ``target_indices``.

    ``tokenize_and_mask`` itself is unchanged: it still labels every assistant turn.
    Correction examples remask afterwards so loss sits only on the supervised
    turns. If budget-fitting drops any target, the example is marked
    unrepresentable rather than silently supervising a different turn.
    """
    tokenized = tokenize_and_mask(messages, tokenizer, max_length=max_length)
    if not tokenized["representable"]:
        return tokenized
    selected = messages
    mapped: set[int] = set(target_indices)
    if tokenized["truncated"] and max_length is not None:
        def _length_fn(ms: list[dict]) -> int:
            return len(_tokenize_messages(ms, tokenizer)["input_ids"])

        fit = fit_messages_to_budget(
            messages, max_tokens=max_length, length_fn=_length_fn
        )
        selected = fit.selected
        remapped: set[int] = set()
        for idx in sorted(target_indices):
            k = _map_target_index_after_budget_fit(messages, selected, idx)
            if k is None:
                out = dict(tokenized)
                out["representable"] = False
                out["labels"] = [-100] * len(out.get("labels") or [])
                return out
            remapped.add(k)
        mapped = remapped
    labeled = _tokenize_messages(
        selected, tokenizer, supervised_indices=mapped
    )
    out = dict(tokenized)
    out["input_ids"] = labeled["input_ids"]
    out["labels"] = labeled["labels"]
    out["attention_mask"] = [1] * len(labeled["input_ids"])
    return out


def remask_to_message_index(
    messages: list[dict],
    tokenizer: Any | None,
    target_index: int,
    *,
    max_length: int | None = 32768,
) -> dict[str, Any]:
    """Call ``tokenize_and_mask``, then keep labels only on ``messages[target_index]``.

    ``tokenize_and_mask`` itself is unchanged: it still labels every assistant turn.
    Correction examples remask afterwards so loss sits only on the post-intervention
    action. If budget-fitting drops that target, the example is marked unrepresentable.
    """
    return remask_to_message_indices(
        messages, tokenizer, {target_index}, max_length=max_length
    )


def supervised_indices_from_meta(
    meta: dict[str, Any] | None, messages: list[dict]
) -> set[int] | None:
    """Return supervised message indices, or None to label every assistant turn.

    Accepts either spelling of the mask spec. A row carrying neither key (and
    without ``supervise_last_assistant_only``) returns None so teacher / ``sft_b``
    rows train exactly as they do today.
    """
    if not meta:
        return None
    if "supervised_message_indices" in meta:
        raw = meta.get("supervised_message_indices")
        if raw is None:
            return None
        return {int(x) for x in raw}
    if "supervised_message_index" in meta and meta.get("supervised_message_index") is not None:
        return {int(meta["supervised_message_index"])}
    if meta.get("supervise_last_assistant_only"):
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                return {i}
        return set()
    return None


def tokenize_sft_row(
    row: dict[str, Any],
    tokenizer: Any | None,
    *,
    max_length: int | None = 32768,
) -> dict[str, Any]:
    """Tokenise one JSONL SFT record, honouring an explicit mask spec when present."""
    messages = list(row["messages"])
    indices = supervised_indices_from_meta(row.get("meta") or {}, messages)
    if indices is None:
        return tokenize_and_mask(messages, tokenizer, max_length=max_length)
    return remask_to_message_indices(
        messages, tokenizer, indices, max_length=max_length
    )


def _write_manifest(out_path: Path, summary: dict[str, Any], *, quiet: bool) -> None:
    public = {k: v for k, v in summary.items() if not str(k).startswith("_")}
    manifest_path = Path(str(out_path) + ".manifest.json")
    manifest_path.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not quiet:
        print(json.dumps(public, indent=2, sort_keys=True))


def build_correction_dataset(
    campaign_root,
    split_ids,
    out_jsonl,
    *,
    strip_interventions: bool = True,
    system: str = "fixed_k",
    quiet: bool = False,
    tokenizer_id: str | None = None,
) -> dict:
    """Emit one JSONL line per episode; every post-intervention action is a target.

    ``INTERVENTION:`` user turns are stripped. ASK_PLANNER post-actions are never
    supervised. Implemented in ``matched_sft`` (per-episode multi-target masks).
    """
    from sidekick.training.matched_sft import build_correction_dataset as _impl

    return _impl(
        campaign_root,
        split_ids,
        out_jsonl,
        strip_interventions=strip_interventions,
        system=system,
        quiet=quiet,
        tokenizer_id=tokenizer_id,
    )
    campaign_root = Path(campaign_root)  # pragma: no cover — unreachable, kept for the old body
    out_path = Path(out_jsonl)
    train_ids = {str(x) for x in split_ids}
    heldout = _heldout_task_ids()
    assert_no_leakage(train_ids, heldout)

    dropped: list[dict[str, Any]] = []
    dropped_counts: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    token_lengths: list[int] = []
    tokenizer = _try_tokenizer()
    n_missing_api_docs = 0
    n_truncated = 0
    n_messages_dropped_total = 0
    n_unrepresentable = 0
    truncated_run_ids: list[str] = []
    n_interventions_seen = 0
    n_forced_true = 0
    n_ask_events = 0
    n_ask_planner_targets = 0

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
                result = _read_json(result_path) or {}
                if not events_path.is_file():
                    drop(task_id, seed, DROP_MISSING_EVENTS)
                    continue
                events = _events_after_last_run_start(events_path)
                n_ask_events += sum(1 for ev in events if ev.event_type == "ask")
                n_iv = 0
                n_forced = 0
                for ev in events:
                    if ev.event_type != "intervention":
                        continue
                    n_iv += 1
                    if (ev.payload or {}).get("forced") is True:
                        n_forced += 1
                n_interventions_seen += n_iv
                n_forced_true += n_forced
                instruction, packet, api_docs, history = _history_from_events(events)
                if not instruction:
                    drop(task_id, seed, DROP_NO_INSTRUCTION)
                    continue
                pairs = list(
                    _iter_correction_histories(
                        history, strip_interventions=strip_interventions
                    )
                )
                if n_iv == 0 and not pairs:
                    drop(task_id, seed, DROP_NO_INTERVENTION)
                    continue
                if not api_docs:
                    n_missing_api_docs += 1
                run_id = str(
                    result.get("run_id")
                    or f"{campaign_root.name}/{system}/{seed}/{task_id}"
                )
                commit = _start_commit(task_dir, campaign_root, result)
                emitted_from_episode = 0
                for corr_i, (status, example_history) in enumerate(pairs):
                    if status != "ok" or example_history is None:
                        if status == DROP_ASK_PLANNER_TARGET:
                            n_ask_planner_targets += 1
                        drop(task_id, seed, status, f"intervention_index={corr_i}")
                        continue
                    messages = render_executor_messages(
                        instruction=instruction,
                        api_docs=api_docs,
                        packet=packet,
                        history=example_history,
                    )
                    if strip_interventions and _contains_intervention_mark(messages):
                        drop(task_id, seed, DROP_INTERVENTION_LEAK, f"intervention_index={corr_i}")
                        continue
                    target_index = len(messages) - 1
                    if messages[target_index].get("role") != "assistant":
                        drop(
                            task_id,
                            seed,
                            DROP_NO_POST_INTERVENTION_ACTION,
                            f"intervention_index={corr_i}",
                        )
                        continue
                    if _is_ask_planner_content(str(messages[target_index].get("content") or "")):
                        n_ask_planner_targets += 1
                        drop(task_id, seed, DROP_ASK_PLANNER_TARGET, f"intervention_index={corr_i}")
                        continue
                    tokenized = _check_budget(messages, tokenizer)
                    if tokenized["truncated"]:
                        n_truncated += 1
                        n_messages_dropped_total += int(tokenized["n_messages_dropped"])
                        truncated_run_ids.append(f"{run_id}#corr{corr_i}")
                    if not tokenized["representable"] or not any(
                        lab != -100 for lab in tokenized["labels"]
                    ):
                        n_unrepresentable += 1
                        drop(task_id, seed, DROP_UNREPRESENTABLE, f"intervention_index={corr_i}")
                        continue
                    meta = {
                        "task_id": task_id,
                        "seed": seed,
                        "run_id": run_id,
                        "n_turns": 1,
                        "source_campaign": str(result.get("campaign_id") or campaign_root.name),
                        "SIDEKICK_START_COMMIT": commit,
                        "source": "correction",
                        "supervise_last_assistant_only": True,
                        "supervised_message_index": target_index,
                        "intervention_index": corr_i,
                        "example_id": f"{run_id}#corr{corr_i}",
                    }
                    records.append({"messages": messages, "meta": meta})
                    token_lengths.append(_conversation_token_length(messages, tokenizer))
                    emitted_from_episode += 1
                if n_iv > 0 and emitted_from_episode == 0 and not any(
                    d["task_id"] == task_id and d["seed"] == seed for d in dropped
                ):
                    drop(task_id, seed, DROP_NO_POST_INTERVENTION_ACTION)

    emitted_ids = [row["meta"]["task_id"] for row in records]
    assert_no_leakage(emitted_ids, heldout)

    digest = _emit_jsonl(out_path, records)
    summary = {
        "out_jsonl": str(out_path),
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
        "source_commit": next(
            (row["meta"]["SIDEKICK_START_COMMIT"] for row in records if row["meta"].get("SIDEKICK_START_COMMIT")),
            None,
        ),
        "sha256": digest,
        "token_length_percentiles": {
            "p50": _percentile(token_lengths, 50),
            "p90": _percentile(token_lengths, 90),
            "max": max(token_lengths) if token_lengths else 0,
            "tokenizer": _DEFAULT_TOKENIZER_ID if tokenizer is not None else "whitespace_fallback",
        },
        "system": system,
        "strip_interventions": strip_interventions,
        "n_interventions_seen": n_interventions_seen,
        "n_forced_true": n_forced_true,
        "n_ask_events": n_ask_events,
        "n_ask_planner_targets": n_ask_planner_targets,
        "_token_lengths": token_lengths,
    }
    _write_manifest(out_path, summary, quiet=quiet)
    return summary


def _slim_part_summary(summary: dict[str, Any]) -> dict[str, Any]:
    skip = {"dropped"}
    return {k: v for k, v in summary.items() if k not in skip and not str(k).startswith("_")}


def build_sft_b_plus(
    correction_campaign_root,
    split_ids,
    out_jsonl,
    *,
    teacher_jsonl: Path | str | None = None,
    teacher_system: str = "planner_alone",
    correction_system: str = "fixed_k",
    strip_interventions: bool = True,
    solved_only: bool = True,
    quiet: bool = False,
    **kwargs: Any,
) -> dict:
    """Frozen teacher jsonl plus per-episode J4 correction sequences. No ASK targets."""
    from sidekick.training.matched_sft import build_sft_b_plus as _impl

    tokenizer_id = kwargs.get("tokenizer_id")
    _ = (teacher_system, solved_only, kwargs)
    return _impl(
        correction_campaign_root,
        split_ids,
        out_jsonl,
        teacher_jsonl=teacher_jsonl,
        adapter_manifest=kwargs.get("adapter_manifest"),
        correction_system=correction_system,
        strip_interventions=strip_interventions,
        tokenizer_id=tokenizer_id,
        quiet=quiet,
    )
    out_path = Path(out_jsonl)  # pragma: no cover — unreachable, kept for the old body
    tmp_root = Path(os.environ.get("TMPDIR") or "/tmp") / f"sft-b-plus-{os.getpid()}"
    tmp_root.mkdir(parents=True, exist_ok=True)
    try:
        teacher_path = tmp_root / "teacher.jsonl"
        correction_path = tmp_root / "correction.jsonl"
        teacher_summary = build_sft_dataset(
            teacher_campaign_root,
            split_ids,
            teacher_path,
            system=teacher_system,
            solved_only=solved_only,
            quiet=True,
        )
        correction_summary = build_correction_dataset(
            correction_campaign_root,
            split_ids,
            correction_path,
            strip_interventions=strip_interventions,
            system=correction_system,
            quiet=True,
        )
        records: list[dict[str, Any]] = []
        for path in (teacher_path, correction_path):
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    records.append(json.loads(line))
        for row in records:
            if _contains_intervention_mark(row.get("messages") or []):
                raise RuntimeError(
                    "combined sft_b_plus contains an INTERVENTION: turn; refusing to write"
                )
            messages = row.get("messages") or []
            meta = row.get("meta") or {}
            if meta.get("source") == "correction" and messages:
                last = messages[-1]
                if last.get("role") == "assistant" and _is_ask_planner_content(
                    str(last.get("content") or "")
                ):
                    raise RuntimeError(
                        "combined sft_b_plus contains an ASK_PLANNER correction target"
                    )
        heldout = _heldout_task_ids()
        emitted_ids = [str(row["meta"]["task_id"]) for row in records]
        assert_no_leakage(emitted_ids, heldout)
        digest = _emit_jsonl(out_path, records)
        token_lengths = list(teacher_summary.get("_token_lengths") or []) + list(
            correction_summary.get("_token_lengths") or []
        )
        tokenizer = None
        if not token_lengths:
            tokenizer = _try_tokenizer()
            token_lengths = [
                _conversation_token_length(row["messages"], tokenizer) for row in records
            ]
        n_teacher = int(teacher_summary.get("n_sequences") or teacher_summary.get("n_trajectories") or 0)
        n_correction = int(correction_summary.get("n_sequences") or 0)
        dropped_counts: dict[str, int] = {}
        for prefix, part in (
            ("teacher", teacher_summary.get("dropped_counts") or {}),
            ("correction", correction_summary.get("dropped_counts") or {}),
        ):
            for key, val in part.items():
                dropped_counts[f"{prefix}_{key}"] = int(val)
        summary = {
            "out_jsonl": str(out_path),
            "n_sequences": len(records),
            "n_teacher_sequences": n_teacher,
            "n_correction_sequences": n_correction,
            "n_dropped": int(teacher_summary.get("n_dropped") or 0)
            + int(correction_summary.get("n_dropped") or 0),
            "dropped_counts": dropped_counts,
            "dropped": [
                {**d, "part": "teacher"} for d in (teacher_summary.get("dropped") or [])
            ]
            + [
                {**d, "part": "correction"}
                for d in (correction_summary.get("dropped") or [])
            ],
            "task_ids": sorted(set(emitted_ids)),
            "run_ids": [row["meta"]["run_id"] for row in records],
            "n_unrepresentable": int(teacher_summary.get("n_unrepresentable") or 0)
            + int(correction_summary.get("n_unrepresentable") or 0),
            "n_truncated": int(teacher_summary.get("n_truncated") or 0)
            + int(correction_summary.get("n_truncated") or 0),
            "n_messages_dropped_total": int(teacher_summary.get("n_messages_dropped_total") or 0)
            + int(correction_summary.get("n_messages_dropped_total") or 0),
            "source_campaign_root": str(teacher_campaign_root),
            "correction_campaign_root": str(correction_campaign_root),
            "source_commit": teacher_summary.get("source_commit")
            or correction_summary.get("source_commit"),
            "source_commits": {
                "teacher": teacher_summary.get("source_commit"),
                "correction": correction_summary.get("source_commit"),
            },
            "sha256": digest,
            "token_length_percentiles": {
                "p50": _percentile(token_lengths, 50),
                "p90": _percentile(token_lengths, 90),
                "max": max(token_lengths) if token_lengths else 0,
                "tokenizer": (
                (teacher_summary.get("token_length_percentiles") or {}).get("tokenizer")
                or (correction_summary.get("token_length_percentiles") or {}).get("tokenizer")
                or (_DEFAULT_TOKENIZER_ID if tokenizer is not None else "whitespace_fallback")
            ),
            },
            "n_ask_planner_targets": int(correction_summary.get("n_ask_planner_targets") or 0),
            "n_interventions_seen": int(correction_summary.get("n_interventions_seen") or 0),
            "n_forced_true": int(correction_summary.get("n_forced_true") or 0),
            "n_ask_events": int(correction_summary.get("n_ask_events") or 0),
            "strip_interventions": strip_interventions,
            "teacher": _slim_part_summary(teacher_summary),
            "correction": _slim_part_summary(correction_summary),
        }
        _write_manifest(out_path, summary, quiet=quiet)
        return summary
    finally:
        for leftover in tmp_root.glob("*"):
            try:
                leftover.unlink()
            except OSError:
                pass
        try:
            tmp_root.rmdir()
        except OSError:
            pass


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an SFT JSONL from Sidekick campaign runs.")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--split", required=True, help="Train ids: AppWorld split name, file, or comma-separated list")
    parser.add_argument("--system", default="planner_alone")
    parser.add_argument("--no-solved-only", action="store_true")
    parser.add_argument(
        "--min-goal-pass-rate",
        type=float,
        default=None,
        help="Also include unsolved trajectories whose goal_pass_rate >= this threshold.",
    )
    parser.add_argument(
        "--mode",
        choices=("teacher", "correction", "sft_b_plus", "sft_c"),
        default="teacher",
        help="teacher=build_sft_dataset; correction=J4 DAgger; sft_b_plus/sft_c=matched pair.",
    )
    parser.add_argument("--correction-campaign-root", default=None)
    parser.add_argument("--correction-system", default="fixed_k")
    parser.add_argument(
        "--no-strip-interventions",
        action="store_true",
        help="Keep INTERVENTION: turns in correction context (default: strip them).",
    )
    parser.add_argument(
        "--tokenizer-id",
        default=None,
        help="Tokenizer / base-model id. Default: ibm-granite/granite-4.2-8b.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    split_ids = load_split_ids(args.split)
    strip = not args.no_strip_interventions
    if args.mode == "sft_b_plus":
        corr_root = args.correction_campaign_root or args.campaign_root
        build_sft_b_plus(
            corr_root,
            split_ids,
            args.out,
            teacher_jsonl=getattr(args, "teacher_jsonl", None),
            correction_system=args.correction_system,
            strip_interventions=strip,
            solved_only=not args.no_solved_only,
            tokenizer_id=args.tokenizer_id,
        )
        return 0
    if args.mode == "correction":
        build_correction_dataset(
            args.campaign_root,
            split_ids,
            args.out,
            strip_interventions=strip,
            system=args.correction_system,
            tokenizer_id=args.tokenizer_id,
        )
        return 0
    build_sft_dataset(
        args.campaign_root,
        split_ids,
        args.out,
        system=args.system,
        solved_only=not args.no_solved_only,
        min_goal_pass_rate=args.min_goal_pass_rate,
        tokenizer_id=args.tokenizer_id,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
