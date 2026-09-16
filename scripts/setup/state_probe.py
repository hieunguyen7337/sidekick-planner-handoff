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
import re
import sys
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
    in file order — the caller has already sliced after the last run_start."""
    pairs: list[tuple[ExecutorAction, Event]] = []
    pending: ExecutorAction | None = None
    for e in events:
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


def run_probe(
    campaign_root: str,
    system: str,
    executor: LLMClient,
    max_steps_per_run: int,
    max_runs: int,
) -> dict[str, Any]:
    root = Path(campaign_root)
    buckets: dict[str, dict[str, Any]] = defaultdict(empty_counts)
    step_records: list[dict[str, Any]] = []
    n_traj = 0
    n_steps = 0
    for run_dir in find_solved_runs(root, system, max_runs):
        events_path = run_dir / "events.jsonl"
        events = list(EventLog.read(events_path))
        pairs = executed_pairs(events)
        if not pairs:
            continue
        n_traj += 1
        n_exec = len(pairs) if not max_steps_per_run else min(len(pairs), max_steps_per_run)
        # k counts replayed gold steps; the model replaces step k+1 = pairs[k],
        # so k can reach len(pairs)-1 at most.
        for k in range(1, min(n_exec, len(pairs) - 1) + 1):
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
            rec["run_id"] = run_dir.name
            rec["task_id"] = run_dir.parent.name
            for name in ("overall", bucket_for(k)):
                record(buckets[name], rec)
            if rec.get("value_forwarding"):
                record(buckets["value_forwarding"], rec)
            step_records.append(rec)
            n_steps += 1
    return {
        "model": getattr(executor, "model", "unknown"),
        "lora_name": getattr(executor, "lora_name", None),
        "campaign_root": str(root),
        "system": system,
        "n_trajectories": n_traj,
        "n_steps": n_steps,
        "buckets": finalize(buckets),
        "steps": step_records,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="state_probe")
    parser.add_argument("--campaign-root", default=DEFAULT_CAMPAIGN)
    parser.add_argument("--system", default="planner_alone")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lora-name", default=None)
    parser.add_argument("--max-steps-per-run", type=int, default=0)
    parser.add_argument("--max-runs", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    executor = VLLMExecutor(
        model=args.model,
        base_url=args.base_url,
        lora_name=args.lora_name,
        temperature=0.0,  # capability measurement, not a sample
        timeout_s=120.0,  # every model call bounded by this HTTP timeout
    )
    report = run_probe(
        args.campaign_root,
        args.system,
        executor,
        args.max_steps_per_run,
        args.max_runs,
    )
    executor.close()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
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
