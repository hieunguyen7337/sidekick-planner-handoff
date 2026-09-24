"""Spike (a): replay the ground truth of all 200 BFCL multi_turn_base entries through the adapter.

No model runs, so this is environment validation and covers dev and test ids alike (brief E1 (a),
docs/second_env_scoping_20260923.md:126-131). Per entry:

  (i)   The ground truth runs as an executor_alone episode (one CODE block per call, COMPLETE per
        turn) and must pass the adapter's scoring. Upstream's own ``multi_turn_checker`` must pass
        the same calls. The adapter's final state must hash equal to the state upstream's executor
        reaches on the ground truth (the possible-answer state), and every call must return the
        same string under both executors.
  (ii)  A no-op agent (COMPLETE on every turn) must fail.
  (iii) Every prefix m = 0..len must replay to its recorded hash (``build_handoff_prefix``), in two
        passes in this process; the per-step hash sequence must be identical when recomputed here
        twice and in a freshly spawned process, and equal to the recorded one.
  (iv)  Resetting the entry twice, with steps in between, must give the same initial hash.

Gate: 200/200 on (i), and 100 % hash agreement on (i), (iii) and (iv).
Output: campaign/results/bfcl_spike_a_20260924.report.json
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from sidekick.agents.executor import MockExecutor  # noqa: E402
from sidekick.agents.planner import MockPlanner  # noqa: E402
from sidekick.cost.ledger import CostLedger  # noqa: E402
from sidekick.cost.prices import PriceSchedule  # noqa: E402
from sidekick.environments.bfcl_env import (  # noqa: E402
    UPSTREAM_COMMIT,
    BfclEnv,
    BfclWorld,
    ensure_vendored,
    ground_truth_script,
    load_entries,
    state_hash,
)
from sidekick.prefix_source import build_handoff_prefix  # noqa: E402
from sidekick.protocols.schemas import parse_executor_action  # noqa: E402
from sidekick.systems import get_system  # noqa: E402
from sidekick.systems.loop import RunLimits  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402

DEFAULT_OUT = REPO / "campaign" / "results" / "bfcl_spike_a_20260924.report.json"
SEED = 1
SOURCE_SYSTEM = "executor_alone"


def _drop_upstream_globals(module: Any, tag: str) -> None:
    for key in [k for k in vars(module) if tag in k]:
        delattr(module, key)


def upstream_ground_truth(entry: dict[str, Any]) -> tuple[list[list[str]], str]:
    """Upstream's executor on the ground truth, under a fresh model name: per-turn results, state hash."""
    ensure_vendored()
    from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils

    tag = f"spikea_{uuid.uuid4().hex}"
    results: list[list[str]] = []
    instances: dict[str, Any] = {}
    try:
        for turn in entry["ground_truth"]:
            out, instances = multi_turn_utils.execute_multi_turn_func_call(
                turn, entry["initial_config"], entry["involved_classes"], tag, entry["id"]
            )
            results.append(list(out))
        return results, state_hash(instances)
    finally:
        _drop_upstream_globals(multi_turn_utils, tag)


def upstream_checker(entry: dict[str, Any], model_turns: list[list[list[str]]]) -> dict[str, Any]:
    ensure_vendored()
    from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import multi_turn_checker

    tag = f"spikeachk_{uuid.uuid4().hex}"
    test_entry = {k: entry[k] for k in ("id", "initial_config", "involved_classes")}
    try:
        out = multi_turn_checker(model_turns, entry["ground_truth"], test_entry, "multi_turn_base", tag)
        return {"valid": bool(out["valid"]), "error_type": out.get("error_type")}
    finally:
        _drop_upstream_globals(multi_turn_utils, tag)


def run_episode_scripted(out: Path, cid: str, task_id: str, script: list[str]) -> tuple[Any, list[dict]]:
    system = get_system(
        SOURCE_SYSTEM,
        planner=MockPlanner(),
        executor=MockExecutor(task_scripts={task_id: list(script)}),
        verifier=None,
        limits=RunLimits(max_steps=400, max_tokens_per_episode=10**9),
    )
    run_id = f"{cid}/{SOURCE_SYSTEM}/{SEED}/{task_id}"
    log = EventLog(out, run_id)
    try:
        result = system.run(BfclEnv(), task_id, SEED, log, CostLedger(PriceSchedule({"models": {}, "local": {}})))
    finally:
        log.close()
    events = [json.loads(x) for x in (out / run_id / "events.jsonl").read_text().splitlines() if x.strip()]
    return result, events


def hash_sequence(task_id: str) -> list[str]:
    """Initial hash, then the hash after each ground-truth action, on a fresh env."""
    entry = load_entries()[task_id]
    env = BfclEnv()
    seq = [str(env.reset(task_id, SEED).env_state_hash)]
    for raw in ground_truth_script(entry):
        seq.append(str(env.step(parse_executor_action(raw)).env_state_hash))
    return seq


def _spawned_sequences(ids: list[str]) -> dict[str, list[str]]:
    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(1) as pool:
        return dict(zip(ids, pool.map(hash_sequence, ids)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/analysis/bfcl_spike_a.py")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--limit", type=int, default=0, help="first N entries only (debugging)")
    args = parser.parse_args(argv)
    t0 = time.time()
    entries = load_entries()
    ids = sorted(entries, key=lambda s: int(s.rsplit("_", 1)[1]))
    if args.limit > 0:
        ids = ids[: args.limit]

    per_entry: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    n_prefix_total = n_prefix_ok = 0
    in_process: dict[str, list[str]] = {}
    with tempfile.TemporaryDirectory(prefix="bfcl_spike_a_") as tmp:
        out = Path(tmp)
        for task_id in ids:
            entry = entries[task_id]
            script = ground_truth_script(entry)
            row: dict[str, Any] = {"n_turns": len(entry["turns"]), "n_actions": len(script)}

            # (i) ground truth through the adapter, and through upstream.
            result, events = run_episode_scripted(out, "gt", task_id, script)
            report = next(e for e in events if e["event_type"] == "evaluate")["payload"]["report"]
            up_results, up_hash = upstream_ground_truth(entry)
            world = BfclWorld(entry)
            ours = [world.run_all(turn) for turn in entry["ground_truth"]]
            checker = upstream_checker(entry, [[[c] for c in turn] for turn in entry["ground_truth"]])
            row.update(
                adapter_success=bool(result.success and result.error_type is None),
                adapter_goal_pass_rate=result.goal_pass_rate,
                adapter_steps=result.steps,
                upstream_checker_valid=checker["valid"],
                upstream_checker_error_type=checker["error_type"],
                final_vs_upstream_hash=report["final_state_hash"] == up_hash,
                possible_answer_vs_upstream_hash=report["possible_answer_state_hash"] == up_hash,
                call_results_equal=ours == up_results,
                n_calls=sum(len(t) for t in entry["ground_truth"]),
            )

            # (ii) no-op agent.
            noop, _ = run_episode_scripted(out, "noop", task_id, ["COMPLETE"] * len(entry["turns"]))
            row.update(noop_success=bool(noop.success), noop_goal_pass_rate=noop.goal_pass_rate)

            # (iii) prefix replays against the recorded hashes, two passes.
            source = out / "gt"
            ok = 0
            for _pass in range(2):
                for m in range(len(script) + 1):
                    built = build_handoff_prefix(source, SOURCE_SYSTEM, task_id, SEED, m, BfclEnv())
                    n_prefix_total += 1
                    ok += int(bool(built.hash_ok))
            n_prefix_ok += ok
            row["prefix_replays_ok"] = ok == 2 * (len(script) + 1)
            recorded = [
                str(e["env_state_hash"])
                for e in events
                if e["event_type"] == "observation"
            ]
            first, second = hash_sequence(task_id), hash_sequence(task_id)
            in_process[task_id] = first
            row["same_process_sequences_equal"] = first == second
            row["recorded_vs_replayed_equal"] = recorded == first

            # (iv) reset twice, with steps in between.
            env = BfclEnv()
            h_a = env.reset(task_id, SEED).env_state_hash
            for raw in script[:3]:
                env.step(parse_executor_action(raw))
            row["reset_twice_equal"] = env.reset(task_id, SEED + 1).env_state_hash == h_a

            per_entry[task_id] = row
            bad = [
                k
                for k in (
                    "adapter_success",
                    "upstream_checker_valid",
                    "final_vs_upstream_hash",
                    "possible_answer_vs_upstream_hash",
                    "call_results_equal",
                    "prefix_replays_ok",
                    "same_process_sequences_equal",
                    "recorded_vs_replayed_equal",
                    "reset_twice_equal",
                )
                if not row[k]
            ]
            if row["noop_success"]:
                bad.append("noop_success")
            if bad:
                failures.append({"id": task_id, "failed": bad, "upstream_checker_error_type": checker["error_type"]})

    spawned = _spawned_sequences(ids)
    for task_id in ids:
        equal = spawned[task_id] == in_process[task_id]
        per_entry[task_id]["fresh_process_sequences_equal"] = equal
        if not equal:
            failures.append({"id": task_id, "failed": ["fresh_process_sequences_equal"]})

    rows = list(per_entry.values())

    def count(key: str) -> int:
        return sum(1 for r in rows if r[key])

    n = len(rows)
    counts = {
        k: count(k)
        for k in (
            "adapter_success",
            "upstream_checker_valid",
            "final_vs_upstream_hash",
            "possible_answer_vs_upstream_hash",
            "call_results_equal",
            "prefix_replays_ok",
            "same_process_sequences_equal",
            "fresh_process_sequences_equal",
            "recorded_vs_replayed_equal",
            "reset_twice_equal",
            "noop_success",
        )
    }
    gt_ok = counts["adapter_success"] == n and counts["upstream_checker_valid"] == n
    hash_ok = all(
        counts[k] == n
        for k in (
            "final_vs_upstream_hash",
            "possible_answer_vs_upstream_hash",
            "same_process_sequences_equal",
            "fresh_process_sequences_equal",
            "recorded_vs_replayed_equal",
            "reset_twice_equal",
        )
    ) and n_prefix_ok == n_prefix_total
    report_out = {
        "spike": "a",
        "unit": "bfcl-env",
        "upstream_commit": UPSTREAM_COMMIT,
        "category": "multi_turn_base",
        "n_entries": n,
        "counts": counts,
        "n_prefix_replays": n_prefix_total,
        "n_prefix_replays_hash_ok": n_prefix_ok,
        "noop_goal_pass_rate_mean": statistics.fmean(r["noop_goal_pass_rate"] or 0.0 for r in rows) if rows else None,
        "n_calls_total": sum(r["n_calls"] for r in rows),
        "n_actions_total": sum(r["n_actions"] for r in rows),
        "gate": {
            "ground_truth_passes_all": gt_ok,
            "hash_agreement_100pct": hash_ok,
            "noop_passes": counts["noop_success"],
            "pass": bool(gt_ok and hash_ok and n == 200),
        },
        "failures": failures,
        "per_entry": per_entry,
        "wall_s": round(time.time() - t0, 1),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report_out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: report_out[k] for k in ("n_entries", "counts", "gate", "n_prefix_replays", "n_prefix_replays_hash_ok", "wall_s")}, sort_keys=True))
    print(f"failures: {len(failures)}")
    return 0 if report_out["gate"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
