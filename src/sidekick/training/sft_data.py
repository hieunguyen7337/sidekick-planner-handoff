"""Build an SFT JSONL from campaign event logs, using the shared executor renderer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
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


def _tokenize_messages(messages: list[dict], tokenizer: Any | None) -> dict[str, list[int]]:
    """Tokenise a complete, already-selected conversation and apply assistant masking."""
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
        if msg.get("role") == "assistant":
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


def _try_tokenizer() -> Any | None:
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(
            _DEFAULT_TOKENIZER_ID,
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


def build_sft_dataset(
    campaign_root,
    split_ids,
    out_jsonl,
    *,
    system="planner_alone",
    solved_only=True,
    min_goal_pass_rate: float | None = None,
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
    tokenizer = _try_tokenizer()
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
                tokenized = tokenize_and_mask(messages, tokenizer)
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    summary = {
        "out_jsonl": str(out_path),
        "n_trajectories": len(records),
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
    }
    manifest_path = Path(str(out_path) + ".manifest.json")
    manifest_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


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
    args = parser.parse_args(list(argv) if argv is not None else None)
    split_ids = load_split_ids(args.split)
    build_sft_dataset(
        args.campaign_root,
        split_ids,
        args.out,
        system=args.system,
        solved_only=not args.no_solved_only,
        min_goal_pass_rate=args.min_goal_pass_rate,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
