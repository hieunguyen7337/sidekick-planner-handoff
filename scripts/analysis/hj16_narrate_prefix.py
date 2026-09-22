#!/usr/bin/env python3
"""HJ-16 narrated prefix builder: write synthetic packets with planner actions as text plan steps."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sidekick.environments.mock_env import MockEnv
from sidekick.prefix_source import build_handoff_prefix
from sidekick.protocols.schemas import (
    DelegationPacket,
    Event,
    ExecutorAction,
    PlanStep,
    Usage,
    utc_now_iso,
)
from sidekick.replay import _action_from_payload, _events_of_last_attempt


def _get_git_commit() -> str | None:
    commit = os.environ.get("SIDEKICK_START_COMMIT") or os.environ.get("GIT_COMMIT")
    if commit:
        return commit.strip()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="HJ-16 narrated prefix: synthesize packet directory with planner actions in plan steps"
    )
    parser.add_argument(
        "--source-campaign",
        default="/scratch/n12194778/sidekick/results/hj1b_planner_20260915",
        help="Path to source campaign directory",
    )
    parser.add_argument(
        "--source-system",
        default="planner_alone",
        help="Source system subdirectory (default: planner_alone)",
    )
    parser.add_argument(
        "--m",
        type=int,
        default=9,
        help="Number of prefix actions to narrate (default: 9)",
    )
    parser.add_argument(
        "--seeds",
        default="1,2",
        help="Comma-separated seeds to process (default: 1,2)",
    )
    parser.add_argument(
        "--with-observations",
        action="store_true",
        default=False,
        help="Include matching observation text in expected_outcome (default: False, actions only)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output directory under artifacts/packets/",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite non-empty output directory",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out).resolve()
    out_str = str(out_path)

    # Refuse paths containing test_normal or test_challenge (held-out splits)
    if "test_normal" in out_str or "test_challenge" in out_str:
        sys.stderr.write("Refusing --out containing held-out split (test_normal/test_challenge)\n")
        return 1

    # Refuse paths under /scratch/n12194778/sidekick/results/
    results_root = Path("/scratch/n12194778/sidekick/results").resolve()
    try:
        out_path.relative_to(results_root)
        sys.stderr.write(f"Refusing --out under {results_root}\n")
        return 1
    except ValueError:
        pass

    # Refuse existing non-empty directory unless --force
    if out_path.is_dir() and any(out_path.iterdir()) and not args.force:
        sys.stderr.write(
            f"Refusing to overwrite existing non-empty directory {out_path} without --force\n"
        )
        return 1

    if isinstance(args.seeds, str):
        seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    elif isinstance(args.seeds, int):
        seeds = [args.seeds]
    else:
        seeds = [int(s) for s in args.seeds]

    source_campaign = Path(args.source_campaign)
    source_system = str(args.source_system)
    m = int(args.m)
    with_observations = bool(args.with_observations)

    per_seed_counts: dict[int, int] = {}
    per_seed_short: dict[int, int] = {}
    total_short_episodes = 0

    out_path.mkdir(parents=True, exist_ok=True)

    for seed in seeds:
        seed_dir = source_campaign / source_system / str(seed)
        if not seed_dir.is_dir():
            sys.stderr.write(f"Warning: seed directory {seed_dir} does not exist\n")
            per_seed_counts[seed] = 0
            per_seed_short[seed] = 0
            continue

        task_dirs = sorted(p for p in seed_dir.iterdir() if p.is_dir())
        n_written = 0
        n_short = 0

        for task_dir in task_dirs:
            task_id = task_dir.name
            events_path = task_dir / "events.jsonl"
            if not events_path.is_file():
                continue

            handoff = build_handoff_prefix(
                source_campaign=source_campaign,
                source_system=source_system,
                task_id=task_id,
                seed=seed,
                m=m,
                env=MockEnv(),
            )
            effective_m = handoff.effective_m
            if effective_m < m:
                n_short += 1
                total_short_episodes += 1

            events = _events_of_last_attempt(events_path)
            plan_event = next(
                (
                    e
                    for e in events
                    if e.event_type == "plan"
                    and isinstance(e.payload, dict)
                    and isinstance(e.payload.get("packet"), dict)
                ),
                None,
            )
            if plan_event is None:
                raise ValueError(f"No valid plan event found for task {task_id} in {events_path}")

            orig_packet = DelegationPacket.model_validate(plan_event.payload["packet"])
            source_model = str(
                plan_event.payload.get("model")
                or (plan_event.usage.model if plan_event.usage else "")
                or ""
            )

            selected_pairs: list[tuple[ExecutorAction, dict[str, Any]]] = []
            if handoff.prefix is not None:
                pending_action: ExecutorAction | None = None
                for ev in handoff.prefix.events:
                    if ev.event_type == "action":
                        pending_action = _action_from_payload(ev.payload)
                        continue
                    if ev.event_type == "observation" and pending_action is not None:
                        if pending_action.kind in ("CODE", "COMPLETE"):
                            selected_pairs.append((pending_action, ev.payload or {}))
                        pending_action = None

            orig_steps = list(orig_packet.plan_steps)
            start_index = (orig_steps[-1].index + 1) if orig_steps else 1
            new_steps = list(orig_steps)

            for k, (action, obs_payload) in enumerate(selected_pairs, start=1):
                step_idx = start_index + k - 1
                if action.kind == "CODE":
                    desc = (
                        f"Expert trajectory, step {k} of {effective_m} "
                        f"(code the planner actually ran on this task): {action.code}"
                    )
                else:
                    act_str = f"COMPLETE: {action.message}" if action.message else "COMPLETE"
                    desc = (
                        f"Expert trajectory, step {k} of {effective_m} "
                        f"(code the planner actually ran on this task): {act_str}"
                    )

                if with_observations:
                    expected_outcome = str(obs_payload.get("text") or "")
                else:
                    expected_outcome = ""

                new_steps.append(
                    PlanStep(
                        index=step_idx,
                        description=desc,
                        expected_outcome=expected_outcome,
                        apps=[],
                    )
                )

            new_packet = orig_packet.model_copy(update={"plan_steps": new_steps})
            DelegationPacket.model_validate(new_packet.model_dump())

            out_task_dir = out_path / source_system / str(seed) / task_id
            out_task_dir.mkdir(parents=True, exist_ok=True)
            out_events_file = out_task_dir / "events.jsonl"

            run_start_event = Event(
                run_id=f"{out_path.name}/{source_system}/{seed}/{task_id}",
                task_id=task_id,
                system=source_system,
                seed=seed,
                step=0,
                ts=utc_now_iso(),
                actor="system",
                event_type="run_start",
                payload={"limits": {}},
                error_type=None,
            )
            plan_payload = {
                "packet": new_packet.model_dump(),
                "model": source_model,
                "narrated_from": str(events_path.resolve()),
                "narrated_m": effective_m,
                "with_observations": with_observations,
            }
            plan_usage = Usage(
                model=source_model,
                provider="cache",
                input_tokens=0,
                cached_input_tokens=0,
                output_tokens=0,
                reasoning_output_tokens=0,
                latency_s=0.0,
                gpu_seconds=0.0,
                n_calls=0,
                raw={"cached_from": str(events_path.resolve()), "model": source_model},
            )
            out_plan_event = Event(
                run_id=f"{out_path.name}/{source_system}/{seed}/{task_id}",
                task_id=task_id,
                system=source_system,
                seed=seed,
                step=0,
                ts=utc_now_iso(),
                actor="planner",
                event_type="plan",
                payload=plan_payload,
                usage=plan_usage,
                error_type=None,
            )
            out_events_file.write_text(
                run_start_event.model_dump_json() + "\n" + out_plan_event.model_dump_json() + "\n",
                encoding="utf-8",
            )
            n_written += 1

        per_seed_counts[seed] = n_written
        per_seed_short[seed] = n_short
        print(f"seed {seed}: {n_written} episodes written ({n_short} shorter than m={m})")

    manifest = {
        "source_campaign": str(source_campaign),
        "source_system": source_system,
        "m": m,
        "seeds": seeds,
        "with_observations": with_observations,
        "per_seed_counts": {str(k): v for k, v in per_seed_counts.items()},
        "n_short_prefix": total_short_episodes,
        "git_commit": _get_git_commit(),
        "created_at": utc_now_iso(),
    }
    manifest_file = out_path / "manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
