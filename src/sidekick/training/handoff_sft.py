"""Suffix-handoff SFT: planner prefix is context; suffix assistant turns are targets.

Training-time analogue of prefix_handoff serving: the first m executed planner
actions (and their observations) stay in context with labels masked; every
assistant turn after the cut is supervised. No HANDOFF note; no new token class.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sidekick.prefix_source import _n_executed_actions
from sidekick.protocols.prompts import render_executor_messages
from sidekick.training.matched_sft import (
    _index_of_identity,
    _next_assistant,
    _sha256_campaign,
)
from sidekick.training.sft_data import (
    DROP_MISSING_EVENTS,
    DROP_MISSING_RESULT,
    DROP_NO_INSTRUCTION,
    _action_from_payload,
    _check_budget,
    _conversation_token_length,
    _emit_jsonl,
    _events_after_last_run_start,
    _history_from_events,
    _percentile,
    _read_json,
    _start_commit,
    _try_tokenizer,
    _write_manifest,
)

DEFAULT_SOURCE = Path(
    "/scratch/n12194778/sidekick/results/hj2b_planner_train_20260916"
)
DEFAULT_SYSTEM = "planner_alone"
DEFAULT_CUTS: tuple[int, ...] = (6, 9, 11)
DROP_TOO_SHORT = "too_short"
DROP_NO_SUFFIX_TARGETS = "no_suffix_targets"


def _prefix_assistant_turns_for_executed_cut(events: list[Any], m: int) -> int | None:
    """Ordinal among flushed assistant turns corresponding to the m-th executed action.

    Walks events with the same pending/flush rules _history_from_events uses and returns
    the 1-based assistant turn count at the m-th executed CODE or COMPLETE action.
    """
    if m <= 0:
        return 0
    pending = None
    awaiting_ask_outcome = False
    seen_initial_obs = False
    n_asst = 0
    n_executed = 0

    for ev in events:
        event_type = (
            getattr(ev, "event_type", None)
            if not isinstance(ev, dict)
            else ev.get("event_type")
        )
        payload = (
            getattr(ev, "payload", None)
            if not isinstance(ev, dict)
            else ev.get("payload")
        )
        payload = payload or {}
        if event_type == "plan" and isinstance(payload.get("packet"), dict):
            continue
        if event_type == "observation":
            if pending is None and not seen_initial_obs:
                seen_initial_obs = True
                continue
            if pending is not None:
                n_asst += 1
                if pending.kind in ("CODE", "COMPLETE"):
                    n_executed += 1
                    if n_executed == m:
                        return n_asst
                pending = None
                awaiting_ask_outcome = False
            continue
        if event_type == "action":
            if pending is not None:
                n_asst += 1
                pending = None
                awaiting_ask_outcome = False
            pending = _action_from_payload(payload)
            continue
        if event_type == "report":
            if pending is not None:
                n_asst += 1
                pending = None
                awaiting_ask_outcome = False
            continue
        if event_type == "ask":
            if pending is None:
                continue
            if payload.get("honoured") is False:
                n_asst += 1
                pending = None
                awaiting_ask_outcome = False
            else:
                awaiting_ask_outcome = True
            continue
        if event_type == "intervention":
            if payload.get("forced"):
                pass
            elif awaiting_ask_outcome and pending is not None:
                n_asst += 1
                pending = None
                awaiting_ask_outcome = False
            continue

    return None


def _suffix_target_indices(messages: list[dict], m: int) -> list[int]:
    """Message indices of assistant turns after the first ``m`` assistant turns.

    Walks with ``_next_assistant`` so target collection is the matched-SFT helper,
    not a second scan. Prefix assistant turns are omitted from the returned list
    and therefore receive label ``-100`` in ``_tokenize_messages``.
    """
    n_asst = 0
    start = 0
    found = False
    for i, msg in enumerate(messages):
        if msg.get("role") != "assistant":
            continue
        n_asst += 1
        if n_asst == m:
            start = i + 1
            found = True
            break
    if not found:
        return []
    targets: list[int] = []
    idx = start
    while True:
        nxt = _next_assistant(messages, idx)
        if nxt is None:
            break
        pos = _index_of_identity(messages, nxt)
        targets.append(pos)
        idx = pos + 1
    return targets


def row_from_events(
    events: list,
    *,
    m: int,
    instruction: str | None = None,
    packet: Any | None = None,
    api_docs: str | None = None,
    history: list[dict] | None = None,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any]]:
    """Cut one rendered trajectory at ``m``. ``(row, drop_reason, stats)``."""
    n_actions = _n_executed_actions(events)
    extras: dict[str, Any] = {"n_source_actions": n_actions, "cut_m": m}
    if n_actions <= m:
        return None, DROP_TOO_SHORT, extras
    n_prefix_asst = _prefix_assistant_turns_for_executed_cut(events, m)
    if n_prefix_asst is None:
        return None, DROP_TOO_SHORT, extras
    extras["n_prefix_assistant_turns"] = n_prefix_asst
    if history is None or instruction is None:
        instruction, packet, api_docs, history = _history_from_events(events)
    if not instruction:
        return None, DROP_NO_INSTRUCTION, extras
    messages = render_executor_messages(
        instruction=instruction,
        api_docs=api_docs or "",
        packet=packet,
        history=history,
    )
    targets = _suffix_target_indices(messages, n_prefix_asst)
    if not targets:
        return None, DROP_NO_SUFFIX_TARGETS, extras
    extras["supervised_message_indices"] = list(targets)
    extras["n_action_targets"] = len(targets)
    row = {
        "messages": messages,
        "meta": {
            "cut_m": m,
            "n_prefix_assistant_turns": n_prefix_asst,
            "n_source_actions": n_actions,
            "n_action_targets": len(targets),
            "n_ask_targets": 0,
            "source": "handoff_suffix",
            "supervised_message_indices": list(targets),
        },
    }
    return row, None, extras


def build_handoff_dataset(
    campaign_root: Path | str,
    out_jsonl: Path | str,
    *,
    system: str = DEFAULT_SYSTEM,
    cuts: tuple[int, ...] = DEFAULT_CUTS,
    quiet: bool = False,
) -> dict[str, Any]:
    """Emit one JSONL row per (episode, cut) that has a suffix to supervise."""
    campaign_root = Path(campaign_root)
    out_path = Path(out_jsonl)
    system_root = campaign_root / system
    records: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    dropped_counts: dict[str, int] = {}
    dropped_too_short_per_m: dict[str, int] = {str(m): 0 for m in cuts}
    rows_per_m: dict[str, int] = {str(m): 0 for m in cuts}
    n_source_episodes = 0
    n_missing_api_docs = 0
    n_truncated = 0
    n_unrepresentable = 0
    token_lengths: list[int] = []
    tokenizer = _try_tokenizer()

    def drop(task_id: str, seed: Any, reason: str, *, m: int | None = None) -> None:
        dropped_counts[reason] = dropped_counts.get(reason, 0) + 1
        rec: dict[str, Any] = {"task_id": task_id, "seed": seed, "reason": reason}
        if m is not None:
            rec["cut_m"] = m
            if reason == DROP_TOO_SHORT:
                dropped_too_short_per_m[str(m)] = dropped_too_short_per_m.get(str(m), 0) + 1
        dropped.append(rec)

    if system_root.is_dir():
        for seed_dir in sorted(p for p in system_root.iterdir() if p.is_dir()):
            try:
                seed: Any = int(seed_dir.name)
            except ValueError:
                seed = seed_dir.name
            for task_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
                task_id = task_dir.name
                n_source_episodes += 1
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
                instruction, packet, api_docs, history = _history_from_events(events)
                if not instruction:
                    drop(task_id, seed, DROP_NO_INSTRUCTION)
                    continue
                if not api_docs:
                    n_missing_api_docs += 1
                run_id = str(
                    result.get("run_id") or f"{campaign_root.name}/{system}/{seed}/{task_id}"
                )
                commit = _start_commit(task_dir, campaign_root, result)
                for m in cuts:
                    row, reason, extras = row_from_events(
                        events,
                        m=m,
                        instruction=instruction,
                        packet=packet,
                        api_docs=api_docs,
                        history=history,
                    )
                    if reason is not None:
                        drop(task_id, seed, reason, m=m)
                        continue
                    assert row is not None
                    tokenized = _check_budget(row["messages"], tokenizer)
                    if tokenized["truncated"]:
                        n_truncated += 1
                    if not tokenized["representable"]:
                        n_unrepresentable += 1
                        drop(task_id, seed, "unrepresentable", m=m)
                        continue
                    row["meta"].update(
                        {
                            "task_id": task_id,
                            "seed": seed,
                            "run_id": run_id,
                            "example_id": f"{run_id}:m{m}",
                            "source_campaign": str(
                                result.get("campaign_id") or campaign_root.name
                            ),
                            "SIDEKICK_START_COMMIT": commit,
                            "n_turns": len(row["meta"]["supervised_message_indices"]),
                        }
                    )
                    records.append(row)
                    rows_per_m[str(m)] = rows_per_m.get(str(m), 0) + 1
                    token_lengths.append(
                        _conversation_token_length(row["messages"], tokenizer)
                    )

    digest = _emit_jsonl(out_path, records)
    tokenizer_name = (
        "ibm-granite/granite-4.2-8b" if tokenizer is not None else "whitespace_fallback"
    )
    n_rows_cut_offset = sum(
        1
        for r in records
        if (r.get("meta") or {}).get("n_prefix_assistant_turns")
        != (r.get("meta") or {}).get("cut_m")
    )
    n_prefix_assistant_turns = sum(
        int((r.get("meta") or {}).get("n_prefix_assistant_turns") or 0)
        for r in records
    )
    summary: dict[str, Any] = {
        "out_jsonl": str(out_path),
        "sha256": digest,
        "source_campaign": str(campaign_root),
        "source_system": system,
        "campaign_sha256": _sha256_campaign(campaign_root, system),
        "cut_points": list(cuts),
        "n_source_episodes": n_source_episodes,
        "n_sequences": len(records),
        "rows_per_m": rows_per_m,
        "dropped_too_short_per_m": dropped_too_short_per_m,
        "n_dropped": len(dropped),
        "dropped_counts": dropped_counts,
        "n_missing_api_docs": n_missing_api_docs,
        "n_truncated": n_truncated,
        "n_unrepresentable": n_unrepresentable,
        "n_prefix_assistant_turns": n_prefix_assistant_turns,
        "n_rows_cut_offset": n_rows_cut_offset,
        "token_length_percentiles": {
            "p50": _percentile(token_lengths, 50),
            "p90": _percentile(token_lengths, 90),
            "max": max(token_lengths) if token_lengths else 0,
            "tokenizer": tokenizer_name,
        },
        "task_ids": sorted({str((r.get("meta") or {}).get("task_id") or "") for r in records}),
        "run_ids": [(r.get("meta") or {}).get("run_id") for r in records],
        "no_handoff_note": True,
    }
    _write_manifest(out_path, summary, quiet=quiet)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build suffix-handoff SFT JSONL from planner trajectories."
    )
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--system", default=DEFAULT_SYSTEM)
    parser.add_argument("--cuts", default=",".join(str(m) for m in DEFAULT_CUTS))
    parser.add_argument("--out", required=True)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    cuts = tuple(int(part.strip()) for part in str(args.cuts).split(",") if part.strip())
    build_handoff_dataset(
        args.source,
        args.out,
        system=args.system,
        cuts=cuts,
        quiet=args.quiet,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
