"""U-D1 state probe: can the executor act correctly given a correct history?

For each solved teacher trajectory and each step k, replay the first k executed
actions into a fresh world, render the gold history with the SAME renderer
inference uses (`render_executor_messages`), ask the executor for one action at
temperature 0, and score agreement / state_equivalence / hash_match.

Run inside a PBS job, never on the login node. BLAS pinned to 1 thread.
"""
from __future__ import annotations

import os

# BLAS stays at 1 thread: this is an I/O + one-GPU-request loop.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import json
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sidekick.agents.executor import LLMClient, VLLMExecutor  # noqa: E402
from sidekick.environments.base import BaseEnv  # noqa: E402
from sidekick.protocols.prompts import (  # noqa: E402
    format_executor_action,
    render_executor_messages,
)
from sidekick.protocols.schemas import Event, ExecutorAction  # noqa: E402
from sidekick.replay import replay_prefix  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402

# Single [OBSERVED]-able constant: every apis.<app>.<api> identifier in a code block.
API_ID_RE = re.compile(r"\bapis\.([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
# String literals of length >= 3 in code, for the value_forwarding subset.
STR_LITERAL_RE = re.compile(r"[\"']([A-Za-z0-9_@.\-]{3,})[\"']")

DEFAULT_CAMPAIGN = "/scratch/n12194778/sidekick/results/hj1b_planner_20260915"


def extract_api_ids(code: str) -> set[str]:
    """Set of ``app.api`` identifiers called in a code block."""
    return {f"{m.group(1)}.{m.group(2)}" for m in API_ID_RE.finditer(code)}


def is_value_forwarding(gold: ExecutorAction, prior_obs_texts: list[str]) -> bool:
    """True when the gold CODE action uses a string literal that first appeared
    in an earlier observation (a token, id, username...). That is exactly the
    carry-state-across-steps ability under test."""
    if gold.kind != "CODE" or not gold.code:
        return False
    prior = "\n".join(prior_obs_texts)
    return any(lit in prior for lit in STR_LITERAL_RE.findall(gold.code))


def action_errored(text: str, error_type: str | None) -> bool:
    """Environment-level failure signal. MockEnv prefixes 'ERROR:'; AppWorld
    execute() returns output text and Observation.error_type carries crashes."""
    return bool(error_type) or text.startswith("ERROR")


def bucket_for(k: int) -> str:
    if k <= 5:
        return "1-5"
    if k <= 10:
        return "6-10"
    return "11+"


def build_history(pairs: list[tuple[ExecutorAction, Event]]) -> list[dict]:
    """Gold history: executed action -> assistant turn (canonical form via the
    shared formatter), observation -> user turn ``OBS: {text}``."""
    history: list[dict] = []
    for action, obs_event in pairs:
        history.append({"role": "assistant", "content": format_executor_action(action)})
        history.append(
            {"role": "user", "content": f"OBS: {obs_event.payload.get('text', '')}"}
        )
    return history


def gold_next(pairs: list[tuple[ExecutorAction, Event]], i: int) -> tuple[ExecutorAction, Event] | None:
    """Deprecated alias kept for symmetry; probe_step indexes pairs directly."""
    return pairs[i + 1] if i + 1 < len(pairs) else None


def empty_counts() -> dict[str, Any]:
    return {
        "n": 0,
        "n_scorable": 0,
        "n_gold_noncode": 0,
        "gold_noncode_counts": defaultdict(int),
        "agreement": 0,
        "agreement_rate": 0.0,
        "agreement_rate_all_steps": 0.0,
        "state_equivalent": 0,
        "n_state_equivalent": 0,
        "state_equivalent_rate": 0.0,
        "hash_match": 0,
        "n_hash_match": 0,
        "hash_match_rate": 0.0,
        "error_type_counts": defaultdict(int),
    }


def record(bucket: dict[str, Any], step_record: dict[str, Any]) -> None:
    # Every metric is divided by the number of steps on which it was defined,
    # never by the number of steps attempted. Error steps remain failures in
    # each denominator they belong to.
    bucket["n"] += 1
    gold_kind = step_record.get("gold_kind", step_record.get("gold_action_kind"))
    if gold_kind == "CODE":
        bucket["n_scorable"] += 1
    elif gold_kind is not None:
        bucket["n_gold_noncode"] += 1
        bucket["gold_noncode_counts"][gold_kind] += 1
    if step_record.get("state_equivalent_defined", False):
        bucket["n_state_equivalent"] += 1
    if step_record.get("hash_match_defined", False):
        bucket["n_hash_match"] += 1
    for metric in ("agreement", "state_equivalent", "hash_match"):
        if step_record.get("error_type") is None and step_record[metric]:
            bucket[metric] += 1
    bucket["error_type_counts"][step_record.get("error_type") or "none"] += 1


def finalize(buckets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, b in buckets.items():
        b["error_type_counts"] = dict(b["error_type_counts"])
        b["gold_noncode_counts"] = dict(b["gold_noncode_counts"])
        b["agreement_rate"] = (
            b["agreement"] / b["n_scorable"] if b["n_scorable"] else 0.0
        )
        b["agreement_rate_all_steps"] = b["agreement"] / b["n"] if b["n"] else 0.0
        b["state_equivalent_rate"] = (
            b["state_equivalent"] / b["n_state_equivalent"]
            if b["n_state_equivalent"]
            else 0.0
        )
        b["hash_match_rate"] = (
            b["hash_match"] / b["n_hash_match"] if b["n_hash_match"] else 0.0
        )
        out[name] = b
    return out


def probe_step(
    executor: LLMClient,
    world: BaseEnv,
    pairs: list[tuple[ExecutorAction, Event]],
    k: int,
    instruction: str,
    api_docs: str,
) -> dict[str, Any]:
    """One probe: ``k`` gold steps are already replayed into ``world``; the model
    must produce step k+1 (= ``pairs[k]``, which it does NOT see — the history is
    ``pairs[:k]``). Every failure is recorded with an error_type, never dropped."""
    rec: dict[str, Any] = {
        "k": k + 1,
        "gold_kind": None,
        "agreement_defined": False,
        "state_equivalent_defined": False,
        "hash_match_defined": False,
        "agreement": False,
        "state_equivalent": False,
        "hash_match": False,
        "error_type": None,
        "model_raw": "",
        "model_code": None,
        "gold_code": None,
    }
    gold_action = pairs[k][0] if k < len(pairs) else None
    gnext = pairs[k + 1] if k + 1 < len(pairs) else None
    gold_obs = gnext[1] if gnext else None
    if gold_action is not None:
        rec["gold_kind"] = gold_action.kind
        rec["agreement_defined"] = gold_action.kind == "CODE"
        rec["gold_code"] = gold_action.code or gold_action.message
        rec["value_forwarding"] = is_value_forwarding(
            gold_action, [p[1].payload.get("text", "") for p in pairs[:k]]
        )
    else:
        rec["value_forwarding"] = False
    rec["state_equivalent_defined"] = gold_action is not None and gold_obs is not None
    rec["hash_match_defined"] = (
        gold_action is not None and gold_obs is not None and bool(gold_obs.env_state_hash)
    )
    try:
        messages = render_executor_messages(
            instruction=instruction,
            api_docs=api_docs,
            history=build_history(pairs[:k]),
        )
        raw, _usage = executor.complete(messages)
        rec["model_raw"] = raw
        from sidekick.protocols.schemas import ActionParseError, parse_executor_action

        try:
            action = parse_executor_action(raw)
        except ActionParseError:
            rec["error_type"] = "parse_error"
            return rec
    except Exception as exc:  # timeout / HTTP / renderer: recorded, not dropped
        rec["error_type"] = f"call_error:{type(exc).__name__}"
        return rec
    rec["model_code"] = action.code or action.message
    try:
        probe_obs = world.step(action)
    except Exception as exc:
        rec["error_type"] = f"exec_error:{type(exc).__name__}"
        return rec
    if action.kind == "CODE" and gold_action is not None and gold_action.kind == "CODE":
        # agreement: executed without error AND same apis.<app>.<api> identifier set
        no_error = not action_errored(probe_obs.text, probe_obs.error_type)
        rec["agreement"] = bool(
            no_error
            and extract_api_ids(action.code or "") == extract_api_ids(gold_action.code or "")
        )
    # state_equivalent: the GOLD NEXT action (step k+2) executed in the probe's
    # world must still return the gold next observation — "did the model leave
    # the world in a state where the teacher's plan still works".
    # Text compared whitespace-normalised: execute() output can differ from the
    # recorded text by a trailing newline only.
    if gnext is not None:
        gnext_action, gnext_obs = gnext
        try:
            gnext_in_probe = world.step(gnext_action)
            rec["state_equivalent"] = (
                gnext_in_probe.text.strip() == str(gnext_obs.payload.get("text", "")).strip()
                and not action_errored(gnext_in_probe.text, gnext_in_probe.error_type)
            )
        except Exception:
            rec["state_equivalent"] = False
    # strict hash_match. EXPECTED NEAR-ZERO AND NOT A FAILURE SIGNAL:
    # snapshot_hash hashes environment_io, which INCLUDES the input code
    # (src/sidekick/environments/appworld_env.py:134-146), so it can only match
    # when the model emits byte-identical code to the teacher. Reported, not gated.
    if gold_obs is not None and gold_obs.env_state_hash:
        rec["hash_match"] = probe_obs.env_state_hash == gold_obs.env_state_hash
    return rec


def executed_pairs(events: list[Event]) -> list[tuple[ExecutorAction, Event]]:
    """(CODE/COMPLETE action, its observation) pairs from the LAST attempt,
    in file order."""
    last_start = next(
        (i for i in range(len(events) - 1, -1, -1) if events[i].event_type == "run_start"),
        0,
    )
    pairs: list[tuple[ExecutorAction, Event]] = []
    pending: ExecutorAction | None = None
    for e in events[last_start:]:
        if e.event_type == "action":
            payload = e.payload
            pending = None
            if payload.get("kind") in ("CODE", "COMPLETE"):
                try:
                    pending = ExecutorAction(
                        kind=payload["kind"],
                        code=payload.get("code"),
                        message=payload.get("message"),
                        ask_reason=payload.get("ask_reason"),
                        confidence=payload.get("confidence"),
                        raw_output=payload.get("raw_output") or "",
                    )
                except Exception:
                    pending = None
            continue
        if e.event_type == "observation" and e.step > 0 and pending is not None:
            pairs.append((pending, e))
            pending = None
    return pairs


def find_solved_runs(campaign_root: Path, system: str, max_runs: int) -> list[Path]:
    """Run dirs with result.json success==true, under campaign_root/<system>/<seed>/<task>."""
    runs: list[Path] = []
    sys_root = campaign_root / system
    if not sys_root.is_dir():
        return runs
    for events in sorted(sys_root.glob("*/*/events.jsonl")):
        try:
            result = json.loads((events.parent / "result.json").read_text())
        except Exception:
            continue
        if result.get("success") is True:
            runs.append(events.parent)
            if max_runs and len(runs) >= max_runs:
                break
    return runs


DEPTH_BUCKETS = ("1-5", "6-10", "11+")


def _partial_path(out_path: Path) -> Path:
    return Path(f"{out_path}.partial.jsonl")


def _read_partial(path: Path) -> list[dict[str, Any]]:
    """Read completed probe records, tolerating an unfinished final line."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record_value = json.loads(line)
                if not isinstance(record_value, dict):
                    raise ValueError("record is not an object")
                if "run_id" not in record_value or "step_index" not in record_value:
                    raise ValueError("record has no run_id/step_index")
                record_value["step_index"] = int(record_value["step_index"])
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                print(
                    f"[state_probe] warning: ignoring invalid partial line "
                    f"{path}:{line_number} ({exc})",
                    file=sys.stderr,
                )
                continue
            records.append(record_value)
    return records


def _point_key(run_id: str, step_index: int) -> tuple[str, int]:
    return (run_id, step_index)


def _planned_points(
    campaign_root: Path,
    system: str,
    max_steps_per_run: int,
    max_runs: int,
) -> tuple[list[dict[str, Any]], int]:
    """Return candidate points in stable file/run order and trajectory count."""
    points: list[dict[str, Any]] = []
    n_trajectories = 0
    for run_dir in find_solved_runs(campaign_root, system, max_runs):
        events_path = run_dir / "events.jsonl"
        events = list(EventLog.read(events_path))
        pairs = executed_pairs(events)
        if not pairs:
            continue
        last_start = next(
            (event for event in reversed(events) if event.event_type == "run_start"),
            None,
        )
        n_trajectories += 1
        n_exec = len(pairs) if not max_steps_per_run else min(
            len(pairs), max_steps_per_run
        )
        # k counts replayed gold steps; the model replaces step k+1 = pairs[k].
        for k in range(1, min(n_exec, len(pairs) - 1) + 1):
            points.append(
                {
                    "run_dir": run_dir,
                    "pairs": pairs,
                    "run_id": last_start.run_id if last_start is not None else run_dir.name,
                    "task_id": last_start.task_id if last_start is not None else run_dir.parent.name,
                    "step_index": k,
                    "order": len(points),
                }
            )
    return points, n_trajectories


def select_sampled_points(
    points: list[dict[str, Any]], max_points: int, seed: int
) -> list[dict[str, Any]]:
    """Select a deterministic, depth-stratified subset of candidate points.

    Initial quotas are as equal as possible. If a bucket is short, its unused
    quota is redistributed round-robin to buckets that still have candidates.
    """
    if max_points <= 0 or max_points >= len(points):
        return list(points)

    by_bucket: dict[str, list[dict[str, Any]]] = {name: [] for name in DEPTH_BUCKETS}
    for point in points:
        by_bucket[bucket_for(point["step_index"])].append(point)

    rng = random.Random(seed)
    for bucket in DEPTH_BUCKETS:
        rng.shuffle(by_bucket[bucket])

    base, remainder = divmod(max_points, len(DEPTH_BUCKETS))
    quotas = [base + (1 if i < remainder else 0) for i in range(len(DEPTH_BUCKETS))]
    selected: list[dict[str, Any]] = []
    cursors = [0, 0, 0]
    for i, bucket in enumerate(DEPTH_BUCKETS):
        take = min(quotas[i], len(by_bucket[bucket]))
        selected.extend(by_bucket[bucket][:take])
        cursors[i] = take

    # Give every unfilled quota slot to the next bucket with capacity. A
    # round-robin pass keeps the redistribution as even as possible too.
    remaining = max_points - len(selected)
    while remaining:
        added = False
        for i, bucket in enumerate(DEPTH_BUCKETS):
            if cursors[i] < len(by_bucket[bucket]):
                selected.append(by_bucket[bucket][cursors[i]])
                cursors[i] += 1
                remaining -= 1
                added = True
                if not remaining:
                    break
        if not added:
            break

    return sorted(selected, key=lambda point: point["order"])


def _report_from_records(
    records: list[dict[str, Any]],
    sampled_points: list[dict[str, Any]],
    campaign_root: Path,
    system: str,
    n_trajectories: int,
    model: str,
    lora_name: str | None,
    budget_exhausted: bool,
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = defaultdict(empty_counts)
    for rec in records:
        for name in ("overall", bucket_for(int(rec["step_index"]))):
            record(buckets[name], rec)
        if rec.get("value_forwarding"):
            record(buckets["value_forwarding"], rec)
    return {
        "model": model,
        "lora_name": lora_name,
        "campaign_root": str(campaign_root),
        "system": system,
        "n_trajectories": n_trajectories,
        "n_steps": len(records),
        "n_planned": len(sampled_points),
        "n_completed": len(records),
        "budget_exhausted": budget_exhausted,
        "sampled_points": [
            {"run_id": point["run_id"], "step": point["step_index"]}
            for point in sampled_points
        ],
        "buckets": finalize(buckets),
        "steps": records,
    }


def run_probe(
    campaign_root: str,
    system: str,
    executor: LLMClient,
    max_steps_per_run: int,
    max_runs: int,
    out_path: str | Path | None = None,
    time_budget_s: int = 0,
    max_points: int = 0,
    seed: int = 0,
) -> dict[str, Any]:
    root = Path(campaign_root)
    points, n_trajectories = _planned_points(
        root, system, max_steps_per_run, max_runs
    )
    sampled_points = select_sampled_points(points, max_points, seed)
    sampled_keys = {
        _point_key(point["run_id"], point["step_index"])
        for point in sampled_points
    }

    partial_path = _partial_path(Path(out_path)) if out_path is not None else None
    partial_records = _read_partial(partial_path) if partial_path is not None else []
    completed_keys = {
        _point_key(str(rec["run_id"]), int(rec["step_index"]))
        for rec in partial_records
        if _point_key(str(rec["run_id"]), int(rec["step_index"])) in sampled_keys
    }
    new_records: list[dict[str, Any]] = []
    started = time.monotonic()
    budget_exhausted = False
    partial_handle = None
    if partial_path is not None:
        partial_path.parent.mkdir(parents=True, exist_ok=True)
        partial_handle = partial_path.open("a", encoding="utf-8")

    try:
        for point in sampled_points:
            point_key = _point_key(point["run_id"], point["step_index"])
            if point_key in completed_keys:
                continue
            if time_budget_s > 0 and time.monotonic() - started >= time_budget_s:
                budget_exhausted = True
                break

            events_path = point["run_dir"] / "events.jsonl"
            pairs = point["pairs"]
            k = point["step_index"]
            world, _remaining = replay_prefix(events_path, k)
            try:
                rec = probe_step(
                    executor,
                    world,
                    pairs,
                    k,
                    instruction=world.instruction,
                    api_docs=getattr(world, "api_docs_prompt", ""),
                )
            finally:
                world.close()  # caller owns the world; one AppWorld world per process
            rec["run_id"] = point["run_id"]
            rec["task_id"] = point["task_id"]
            rec["step_index"] = k
            if partial_handle is not None:
                partial_handle.write(json.dumps(rec, sort_keys=True) + "\n")
                partial_handle.flush()
            else:
                new_records.append(rec)
            completed_keys.add(point_key)
    finally:
        if partial_handle is not None:
            partial_handle.close()

    if partial_path is not None:
        all_partial_records = _read_partial(partial_path)
        # A report only includes points selected by this invocation. This makes
        # changing --max-points safe while preserving exact pair-based resume.
        records: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, int]] = set()
        for rec in all_partial_records:
            key = _point_key(str(rec["run_id"]), int(rec["step_index"]))
            if key in sampled_keys and key not in seen_keys:
                records.append(rec)
                seen_keys.add(key)
    else:
        records = new_records

    report = _report_from_records(
        records,
        sampled_points,
        root,
        system,
        n_trajectories,
        getattr(executor, "model", "unknown"),
        getattr(executor, "lora_name", None),
        budget_exhausted,
    )
    if out_path is not None:
        output_path = Path(out_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="state_probe")
    parser.add_argument("--campaign-root", default=DEFAULT_CAMPAIGN)
    parser.add_argument("--system", default="planner_alone")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lora-name", default=None)
    parser.add_argument("--max-steps-per-run", type=int, default=0)
    parser.add_argument("--max-runs", type=int, default=0)
    parser.add_argument(
        "--time-budget-s",
        type=int,
        default=0,
        help="stop before a probe point after this many seconds (0 = unlimited)",
    )
    parser.add_argument(
        "--max-points",
        type=int,
        default=0,
        help="maximum points to sample by depth (0 = unlimited)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seed for deterministic depth-stratified sampling",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    executor = VLLMExecutor(
        model=args.model,
        base_url=args.base_url,
        lora_name=args.lora_name,
        temperature=0.0,  # capability measurement, not a sample
        timeout_s=120.0,  # every model call bounded by this HTTP timeout
    )
    try:
        report = run_probe(
            args.campaign_root,
            args.system,
            executor,
            args.max_steps_per_run,
            args.max_runs,
            out_path=args.out,
            time_budget_s=args.time_budget_s,
            max_points=args.max_points,
            seed=args.seed,
        )
    finally:
        executor.close()
    if report["budget_exhausted"]:
        print(
            f"probe points done={report['n_completed']} "
            f"planned={report['n_planned']} (time budget exhausted)"
        )
    print(
        f"{'bucket':<18}{'n':>5}{'scorable':>9}"
        f"{'agree/sc':>10}{'agree/all':>10}{'state':>8}{'hash':>8}"
    )
    for name, b in report["buckets"].items():
        print(
            f"{name:<18}{b['n']:>5}{b['n_scorable']:>9}"
            f"{b['agreement_rate']:>10.3f}{b['agreement_rate_all_steps']:>10.3f}"
            f"{b['state_equivalent_rate']:>8.3f}{b['hash_match_rate']:>8.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
