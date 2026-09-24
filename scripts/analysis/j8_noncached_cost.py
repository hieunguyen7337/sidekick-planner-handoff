"""Non-cached planner-token helpers for the J8 prefix frontier axis.

Cached input is re-sent context, not new work. Every token budget in this
project excludes it. sft_plan's ledger is zeros because it replays a cached
plan packet; the honest floor charges the source plan event it actually
replays.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any, Optional


def usage_noncached_tokens(usage: Any) -> Optional[float]:
    """input + output + reasoning; cached_input_tokens excluded. Missing usage is None."""
    if not isinstance(usage, dict):
        return None
    return float(
        (usage.get("input_tokens") or 0)
        + (usage.get("output_tokens") or 0)
        + (usage.get("reasoning_output_tokens") or 0)
    )


def last_plan_event_noncached_tokens(events_path: Path) -> Optional[float]:
    """Non-cached tokens on the last plan event with a packet after last run_start.

    Matches CachedPacketPlanner._load_plan_event: file order, last run_start,
    last plan payload that contains a packet dict.
    """
    try:
        text = events_path.read_text(encoding="utf-8")
    except OSError:
        return None
    events: list[dict[str, Any]] = []
    last_start = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        events.append(ev)
        if ev.get("event_type") == "run_start":
            last_start = len(events) - 1
    tokens: Optional[float] = None
    found = False
    for ev in events[last_start:]:
        if ev.get("event_type") != "plan":
            continue
        payload = ev.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("packet"), dict):
            continue
        found = True
        tokens = usage_noncached_tokens(ev.get("usage"))
    if not found:
        return None
    return tokens


def is_sft_plan_row(row: dict[str, Any], label: str) -> bool:
    system = row.get("system")
    if system == "sft_plan":
        return True
    if system in (None, "") and label == "sft_plan":
        return True
    return False


def attach_sft_plan_source_plan_tokens(
    cleaned: dict[tuple[str, int], dict[str, Any]],
    label: str,
    packet_source: Path | None,
    packet_system: str,
) -> dict[str, Any]:
    """Charge sft_plan the non-cached plan-event tokens of the source it replays.

    Applied only when every sft_plan row maps onto one source episode. A partial
    map is left at zero and returned as an understatement rather than mixed in.

    A planless key (J10 A1 §4.2: the source was scored without a crash but its
    last attempt wrote no plan, src/sidekick/agents/planner.py planless_source_keys)
    is not a miss: arm 2 planned it live (on_missing="call_if_planless"), so that
    plan is already in the row's own planner_tokens_noncached_live and the row is
    charged 0.0 replayed tokens. Only when that live usage is 0 or absent is it a
    miss. n_mapped (plan events) + n_planless_live + n_missing == n_sft_plan_rows.
    """
    for row in cleaned.values():
        row.setdefault("sft_plan_replayed_plan_tokens", None)
    sft_keys = [key for key, row in cleaned.items() if is_sft_plan_row(row, label)]
    info: dict[str, Any] = {
        "applied": False,
        "route": None,
        "n_sft_plan_rows": len(sft_keys),
        "n_mapped": 0,
        "n_missing": 0,
        "n_planless_live": 0,
        "planless_keys": [],
        "mean_noncached_plan_tokens": None,
        "packet_source": str(packet_source) if packet_source is not None else None,
        "packet_system": packet_system,
        "understatement": None,
    }
    if not sft_keys:
        return info
    mapped: list[tuple[tuple[str, int], float]] = []
    planless: list[tuple[str, int]] = []
    missing: list[str] = []
    source_root = Path(packet_source) if packet_source is not None else None
    for key in sft_keys:
        task_id, seed = key
        if source_root is None:
            missing.append(f"{task_id}/{seed}: no packet_source")
            continue
        events_path = (
            source_root / packet_system / str(seed) / str(task_id) / "events.jsonl"
        )
        if not events_path.is_file():
            missing.append(f"{task_id}/{seed}: missing {events_path}")
            continue
        tokens = last_plan_event_noncached_tokens(events_path)
        if tokens is None:
            if _source_is_planless(events_path):
                live = cleaned[key].get("planner_tokens_noncached_live")
                if live is None or float(live) <= 0.0:
                    missing.append(
                        f"{task_id}/{seed}: planless source but no live plan in the episode "
                        f"(planner_tokens_noncached_live={live!r}) at {events_path}"
                    )
                    continue
                planless.append(key)
                continue
            missing.append(f"{task_id}/{seed}: no plan-event usage at {events_path}")
            continue
        mapped.append((key, float(tokens)))
    info["n_mapped"] = len(mapped)
    info["n_missing"] = len(missing)
    info["n_planless_live"] = len(planless)
    info["planless_keys"] = [f"{seed}/{task_id}" for task_id, seed in planless]
    mapped_mean = (
        round(statistics.fmean(t for _k, t in mapped), 6) if mapped else None
    )
    info["mean_noncached_plan_tokens"] = mapped_mean
    if missing:
        info["route"] = "understatement"
        info["understatement"] = {
            "arm": label,
            "reason": (
                "sft_plan packet cache did not map one-to-one onto a source "
                f"plan event ({len(missing)} of {len(sft_keys)} missing); "
                "left at zero rather than mixing a partial correction"
            ),
            "n_mapped": len(mapped),
            "n_missing": len(missing),
            "estimated_mean_noncached_plan_tokens": mapped_mean,
            "missing_examples": missing[:5],
        }
        return info
    for key, tokens in mapped:
        cleaned[key]["sft_plan_replayed_plan_tokens"] = tokens
    for key in planless:
        cleaned[key]["sft_plan_replayed_plan_tokens"] = 0.0
    info["applied"] = True
    info["route"] = "source_plan_event"
    return info


def _source_is_planless(events_path: Path) -> bool:
    """planner.py's planless definition for one source episode (J10 A1 §4.2).

    result.json beside events.jsonl scored without a crash AND no plan event with
    a packet after the last run_start. Reuses the planner's own readers.
    """
    # Lazy, as j12_cost_axes.replayed_plan_usage: planner.py pulls in pydantic.
    from sidekick.agents.planner import (  # noqa: E402
        _last_attempt_plan_event,
        _scored_without_crash,
    )

    if not _scored_without_crash(events_path.parent / "result.json"):
        return False
    try:
        payload, _usage = _last_attempt_plan_event(events_path)
    except (OSError, UnicodeDecodeError):
        return False
    return payload is None


def noncached_episode_cost(row: dict[str, Any]) -> Optional[float]:
    """live_noncached + replayed_planner_tokens + sft_plan source plan tokens.

    Never falls back to the cached-inclusive ledger total.
    """
    live = row.get("planner_tokens_noncached_live")
    replayed = row.get("replayed_planner_tokens")
    sft = row.get("sft_plan_replayed_plan_tokens")
    if live is None and replayed is None and sft is None:
        return None
    total = 0.0
    if live is not None:
        total += float(live)
    if replayed is not None:
        total += float(replayed)
    if sft is not None:
        total += float(sft)
    return total
