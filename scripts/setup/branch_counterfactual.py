"""Counterfactual branches for fixed_k intervention points. No live campaign submit.

Re-run an episode from the observation before intervention i, without that
correction, to label whether the intervention was needed. Writes one JSONL line
per completed branch, flushed and fsynced, so a kill never discards finished work.

``replay_prefix``'s ``k`` is the number of executed CODE/COMPLETE actions
(replay.py:66-84, 97-106), not an event index and not an episode step. An
intervention index is converted by counting those executed actions in the
events *before* the i-th intervention.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import multiprocessing
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sidekick.agents.planner import MockPlanner  # noqa: E402
from sidekick.cost.ledger import CostLedger  # noqa: E402
from sidekick.cost.prices import PriceSchedule  # noqa: E402
from sidekick.environments.base import BaseEnv  # noqa: E402
from sidekick.protocols.prompts import render_executor_messages  # noqa: E402
from sidekick.protocols.schemas import Event, RunResult, utc_now_iso  # noqa: E402
from sidekick.replay import _events_of_last_attempt, replay_prefix  # noqa: E402
from sidekick.runner import DEFAULT_PRICES, load_config, make_env, make_executor  # noqa: E402
from sidekick.systems.loop import (  # noqa: E402
    DEFAULT_MAX_PLANNER_CALLS,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOKENS_PER_EPISODE,
    DEFAULT_PER_STEP_TIMEOUT_S,
    EpisodePrefix,
    RunLimits,
    SystemPolicy,
    run_episode,
)
from sidekick.training.sft_data import _history_from_events  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402

BRANCH_TEMPERATURE = 0.7
DEFAULT_BRANCH_SEEDS = (101, 102)
DEFAULT_ADAPTER = "sft_b"
SYSTEM_NAME = "fixed_k"


def utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSON objects; skip a trailing truncated line."""
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def enumerate_intervention_points(events: list[Event]) -> list[dict[str, Any]]:
    """i-th intervention event, 0-based, in file order."""
    points: list[dict[str, Any]] = []
    for idx, ev in enumerate(events):
        if ev.event_type != "intervention":
            continue
        payload = ev.payload or {}
        points.append(
            {
                "i": len(points),
                "step": int(ev.step),
                "event_index": idx,
                "correction": str(payload.get("correction") or ""),
                "forced": payload.get("forced"),
            }
        )
    return points


def prefix_events_before_intervention(events: list[Event], i: int) -> list[Event]:
    points = enumerate_intervention_points(events)
    if i < 0 or i >= len(points):
        raise IndexError(f"intervention index {i} out of range ({len(points)} points)")
    return list(events[: points[i]["event_index"]])


def executed_prefix_k(prefix_events: list[Event]) -> int:
    """Convert a prefix to ``replay_prefix``'s ``k`` (executed CODE/COMPLETE).

    [OBSERVED replay.py:66]: k is executed CODE/COMPLETE actions, not events.
    [OBSERVED replay.py:97-106]: an action counts only when a following
    observation is seen and kind is CODE or COMPLETE.
    """
    k = 0
    pending: Event | None = None
    for ev in prefix_events:
        if ev.event_type == "action":
            pending = ev
            continue
        if ev.event_type == "observation" and pending is not None:
            kind = (pending.payload or {}).get("kind")
            if kind in ("CODE", "COMPLETE"):
                k += 1
            pending = None
    return k


def render_branch_context(events: list[Event], i: int) -> list[dict]:
    """Byte-identical to the training renderer on the prefix before intervention i.

    Shared call: ``_history_from_events`` (sft_data.py) then
    ``render_executor_messages`` (prompts.py) — the same pair training uses.
    """
    prefix = prefix_events_before_intervention(events, i)
    instruction, packet, api_docs, history = _history_from_events(prefix)
    return render_executor_messages(
        instruction=instruction,
        api_docs=api_docs,
        packet=packet,
        history=history,
    )


def label_point(
    actual_gpr: float | None, branch_gpr: list[float | None]
) -> dict[str, Any]:
    """Pre-registered discrete labels. A None sample → incomplete, no impute."""
    if any(g is None for g in branch_gpr):
        return {
            "needed": None,
            "needed_strict": None,
            "harmful": None,
            "label_status": "incomplete",
        }
    values = [float(g) for g in branch_gpr]
    mean_g = sum(values) / len(values)
    actual = float(actual_gpr) if actual_gpr is not None else None
    if actual is None:
        return {
            "needed": None,
            "needed_strict": None,
            "harmful": None,
            "label_status": "incomplete",
        }
    needed = mean_g < actual
    return {
        "needed": needed,
        "needed_strict": all(g < actual for g in values),
        "harmful": mean_g > actual,
        "label_status": "complete",
    }


def branch_key(campaign: str, seed: int, task_id: str, i: int, branch_seed: int) -> str:
    return f"{campaign}/{seed}/{task_id}/{i}/{branch_seed}"


def point_key(campaign: str, seed: int, task_id: str, i: int) -> str:
    return f"{campaign}/{seed}/{task_id}/{i}"


def branch_run_id(seed: int, task_id: str, i: int, branch_seed: int) -> str:
    return f"{SYSTEM_NAME}/{seed}/{task_id}__b{i}_s{branch_seed}"


def limits_from_events(events: list[Event]) -> RunLimits:
    start = next((e for e in events if e.event_type == "run_start"), None)
    raw = (start.payload or {}).get("limits") or {} if start else {}
    return RunLimits(
        max_steps=int(raw.get("max_steps", DEFAULT_MAX_STEPS)),
        max_tokens_per_episode=int(
            raw.get("max_tokens_per_episode", DEFAULT_MAX_TOKENS_PER_EPISODE)
        ),
        per_step_timeout_s=float(raw.get("per_step_timeout_s", DEFAULT_PER_STEP_TIMEOUT_S)),
        max_planner_calls=int(raw.get("max_planner_calls", DEFAULT_MAX_PLANNER_CALLS)),
    )


def adapter_from_events(events: list[Event], fallback: str | None) -> str | None:
    start = next((e for e in events if e.event_type == "run_start"), None)
    policy = (start.payload or {}).get("policy") or {} if start else {}
    name = policy.get("adapter_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return fallback


def result_gpr(result: dict[str, Any]) -> float | None:
    gpr = result.get("goal_pass_rate")
    if gpr is None:
        return None
    try:
        return float(gpr)
    except (TypeError, ValueError):
        return None


def iter_episode_dirs(campaign_root: Path, system: str = SYSTEM_NAME) -> list[Path]:
    root = campaign_root / system
    if not root.is_dir():
        return []
    dirs: list[Path] = []
    for seed_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for task_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
            if "__b" in task_dir.name:
                continue
            if (task_dir / "events.jsonl").is_file():
                dirs.append(task_dir)
    return dirs


def load_split_filter(split: str | None) -> set[str] | None:
    if not split:
        return None
    try:
        from appworld import load_task_ids

        return {str(x) for x in load_task_ids(split)}
    except Exception:
        return None


def completed_branch_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        try:
            keys.add(
                branch_key(
                    str(row["campaign"]),
                    int(row["seed"]),
                    str(row["task_id"]),
                    int(row["i"]),
                    int(row["branch_seed"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return keys


def completed_point_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        try:
            keys.add(
                point_key(
                    str(row["campaign"]),
                    int(row["seed"]),
                    str(row["task_id"]),
                    int(row["i"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return keys


def assemble_point_record(
    meta: dict[str, Any],
    samples: dict[int, dict[str, Any]],
    branch_seeds: list[int],
) -> dict[str, Any]:
    gprs = [samples[s].get("branch_gpr") for s in branch_seeds]
    labels = label_point(meta.get("actual_gpr"), gprs)
    return {
        "campaign": meta["campaign"],
        "seed": meta["seed"],
        "task_id": meta["task_id"],
        "i": meta["i"],
        "step": meta["step"],
        "actual_gpr": meta.get("actual_gpr"),
        "actual_solved": meta.get("actual_solved"),
        "branch_gpr": gprs,
        "branch_solved": [samples[s].get("branch_solved") for s in branch_seeds],
        "branch_steps": [samples[s].get("branch_steps") for s in branch_seeds],
        "branch_error_type": [samples[s].get("branch_error_type") for s in branch_seeds],
        "needed": labels["needed"],
        "needed_strict": labels["needed_strict"],
        "harmful": labels["harmful"],
        "label_status": labels["label_status"],
        "correction": meta.get("correction") or "",
    }


def build_oracle_labels(point_rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    """``{"<task_id>/<seed>": [sorted steps where needed is true]}``."""
    by_episode: dict[str, list[int]] = {}
    for row in point_rows:
        if row.get("label_status") != "complete":
            continue
        seed = row.get("seed")
        task_id = row.get("task_id")
        if seed is None or task_id is None:
            continue
        key = f"{task_id}/{seed}"
        by_episode.setdefault(key, [])
        if row.get("needed") is True:
            by_episode[key].append(int(row["step"]))
    return {key: sorted(set(steps)) for key, steps in sorted(by_episode.items())}


def source_commit(campaign_root: Path) -> str:
    env = os.environ.get("SIDEKICK_START_COMMIT", "").strip()
    if env:
        return env
    for candidate in (
        campaign_root / "manifest.json",
        campaign_root.parent / "results" / campaign_root.name / "manifest.json",
    ):
        if not candidate.is_file():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("SIDEKICK_START_COMMIT", "start_commit", "git_commit"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return "unknown"


def write_manifest(
    out_root: Path,
    *,
    campaign_root: Path,
    split: str,
    branch_seeds: list[int],
    point_rows: list[dict[str, Any]],
    branch_rows: list[dict[str, Any]],
    adapter: str | None,
) -> None:
    branches_path = out_root / "branches.jsonl"
    n_complete = sum(1 for r in point_rows if r.get("label_status") == "complete")
    n_incomplete = sum(1 for r in point_rows if r.get("label_status") != "complete")
    n_needed = sum(1 for r in point_rows if r.get("needed") is True)
    n_needless = sum(
        1
        for r in point_rows
        if r.get("label_status") == "complete" and r.get("needed") is False
    )
    n_harmful = sum(1 for r in point_rows if r.get("harmful") is True)
    n_strict = sum(1 for r in point_rows if r.get("needed_strict") is True)
    write_json(
        out_root / "manifest.json",
        {
            "n_points": len(point_rows),
            "n_branches": len(branch_rows),
            "n_complete": n_complete,
            "n_incomplete": n_incomplete,
            "n_needed": n_needed,
            "n_needless": n_needless,
            "n_harmful": n_harmful,
            "n_needed_strict": n_strict,
            "source_campaign": str(campaign_root),
            "source_commit": source_commit(campaign_root),
            "branches_jsonl_sha256": (
                sha256_file(branches_path) if branches_path.is_file() else None
            ),
            "split": split,
            "branch_config": {
                "temperature": BRANCH_TEMPERATURE,
                "branch_seeds": list(branch_seeds),
                "max_steps_rule": (
                    "original max_steps counted from intervention step s "
                    "(branch takes steps s..max_steps, i.e. remaining includes s)"
                ),
                "review_every_k": None,
                "allow_executor_ask": False,
                "planner_drives": False,
                "adapter": adapter or DEFAULT_ADAPTER,
                "replay_prefix_k": (
                    "executed CODE/COMPLETE actions before the intervention "
                    "(not event index, not episode step)"
                ),
            },
        },
    )


def refresh_derived(out_root: Path, branch_seeds: list[int], campaign_root: Path, split: str, adapter: str | None) -> None:
    branch_rows = load_jsonl(out_root / "branch_runs.jsonl")
    point_rows = load_jsonl(out_root / "branches.jsonl")
    write_json(out_root / "oracle_labels.json", build_oracle_labels(point_rows))
    write_manifest(
        out_root,
        campaign_root=campaign_root,
        split=split,
        branch_seeds=branch_seeds,
        point_rows=point_rows,
        branch_rows=branch_rows,
        adapter=adapter,
    )


def maybe_write_point(
    out_root: Path,
    meta: dict[str, Any],
    branch_seeds: list[int],
    existing_points: set[str] | None = None,
) -> dict[str, Any] | None:
    """If both samples exist, append the point line once (locked)."""
    path = out_root / "branches.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    pk = point_key(meta["campaign"], meta["seed"], meta["task_id"], meta["i"])
    with open(path, "a+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        existing_rows: list[dict[str, Any]] = []
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                existing_rows.append(obj)
        if pk in completed_point_keys(existing_rows):
            return None
        rows = load_jsonl(out_root / "branch_runs.jsonl")
        samples: dict[int, dict[str, Any]] = {}
        for row in rows:
            try:
                if (
                    str(row["campaign"]) == meta["campaign"]
                    and int(row["seed"]) == int(meta["seed"])
                    and str(row["task_id"]) == meta["task_id"]
                    and int(row["i"]) == int(meta["i"])
                ):
                    samples[int(row["branch_seed"])] = row
            except (KeyError, TypeError, ValueError):
                continue
        if any(s not in samples for s in branch_seeds):
            return None
        record = assemble_point_record(meta, samples, branch_seeds)
        fh.write(json.dumps(record, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
        if existing_points is not None:
            existing_points.add(pk)
        return record


def repair_points(out_root: Path, branch_seeds: list[int]) -> None:
    """Write any point lines that both samples finished but the kill beat the point write."""
    branch_rows = load_jsonl(out_root / "branch_runs.jsonl")
    existing = completed_point_keys(load_jsonl(out_root / "branches.jsonl"))
    grouped: dict[str, dict[str, Any]] = {}
    samples: dict[str, dict[int, dict[str, Any]]] = {}
    for row in branch_rows:
        try:
            meta = {
                "campaign": str(row["campaign"]),
                "seed": int(row["seed"]),
                "task_id": str(row["task_id"]),
                "i": int(row["i"]),
                "step": int(row["step"]),
                "actual_gpr": row.get("actual_gpr"),
                "actual_solved": row.get("actual_solved"),
                "correction": row.get("correction") or "",
            }
            pk = point_key(meta["campaign"], meta["seed"], meta["task_id"], meta["i"])
            grouped[pk] = meta
            samples.setdefault(pk, {})[int(row["branch_seed"])] = row
        except (KeyError, TypeError, ValueError):
            continue
    for pk, meta in grouped.items():
        if pk in existing:
            continue
        seed_map = samples.get(pk) or {}
        if any(s not in seed_map for s in branch_seeds):
            continue
        append_jsonl(out_root / "branches.jsonl", assemble_point_record(meta, seed_map, branch_seeds))
        existing.add(pk)


def _make_env(job: dict[str, Any]) -> BaseEnv:
    return make_env(job["env_kind"], job["experiment_name"], job.get("config") or {})


def run_one_branch(job: dict[str, Any]) -> dict[str, Any]:
    out_root = Path(job["out_root"])
    key = job["key"]
    branch_path = out_root / "branch_runs.jsonl"
    if job.get("resume"):
        if key in completed_branch_keys(load_jsonl(branch_path)):
            return {"skipped": True, "key": key}
        result_file = out_root / job["run_id"] / "result.json"
        if result_file.is_file():
            return {"skipped": True, "key": key, "reason": "result_exists"}

    events = _events_of_last_attempt(job["events_path"])
    points = enumerate_intervention_points(events)
    point = points[int(job["i"])]
    prefix = prefix_events_before_intervention(events, int(job["i"]))
    k = executed_prefix_k(prefix)
    limits = limits_from_events(events)
    adapter = job.get("adapter")
    cfg = dict(job.get("config") or {})
    exec_cfg = dict(cfg.get("executor") or {})
    exec_cfg["temperature"] = BRANCH_TEMPERATURE
    if adapter:
        exec_cfg["lora_name"] = adapter
    if job["env_kind"] == "mock":
        cfg["executor"] = {"type": "mock", **{k: v for k, v in exec_cfg.items() if k == "lora_name"}}
        cfg["executor_type"] = "mock"
    else:
        cfg["executor"] = exec_cfg
    executor = make_executor(cfg)
    planner = MockPlanner()
    prices = PriceSchedule.load(job["prices_path"])
    ledger = CostLedger(prices)
    log = EventLog(out_root, job["run_id"])
    env: BaseEnv | None = None
    result: RunResult | None = None
    error_type: str | None = None
    try:
        env = _make_env(job)
        world, _remaining = replay_prefix(job["events_path"], k, env)
        env = world
        log.write_manifest(
            {
                "system": SYSTEM_NAME,
                "task_id": job["task_id"],
                "seed": job["seed"],
                "branch_seed": job["branch_seed"],
                "intervention_index": job["i"],
                "step": point["step"],
                "replay_k": k,
                "campaign": job["campaign"],
                "experiment_name": job["experiment_name"],
            }
        )
        result = run_episode(
            name=SYSTEM_NAME,
            env=world,
            planner=planner,
            executor=executor,
            verifier=None,
            policy=SystemPolicy(
                plan_first=False,
                planner_drives=False,
                allow_executor_ask=False,
                review_every_k=None,
                adapter_name=adapter,
            ),
            limits=limits,
            task_id=job["task_id"],
            seed=int(job["seed"]),
            log=log,
            ledger=ledger,
            prefix=EpisodePrefix(events=prefix, start_step=int(point["step"])),
        )
        env = None
    except Exception as exc:
        error_type = "crash"
        if env is not None:
            try:
                env.close()
            except Exception:
                pass
        log.append(
            Event(
                run_id=job["run_id"],
                task_id=job["task_id"],
                system=SYSTEM_NAME,
                seed=int(job["seed"]),
                step=int(point["step"]),
                ts=utc_now_iso(),
                actor="system",
                event_type="error",
                payload={"detail": str(exc), "exc_type": type(exc).__name__, "replay_k": k},
                error_type="crash",
            )
        )
    finally:
        log.close()
        closer = getattr(executor, "close", None)
        if callable(closer):
            closer()

    dumped = result.model_dump() if result is not None else None
    if dumped is not None:
        dest = out_root / job["run_id"] / "result.json"
        dest.write_text(json.dumps(dumped, sort_keys=True) + "\n", encoding="utf-8")
        gpr = dumped.get("goal_pass_rate")
        if dumped.get("error_type") == "crash":
            gpr = None
        branch_row = {
            "campaign": job["campaign"],
            "seed": job["seed"],
            "task_id": job["task_id"],
            "i": job["i"],
            "step": point["step"],
            "branch_seed": job["branch_seed"],
            "actual_gpr": job.get("actual_gpr"),
            "actual_solved": job.get("actual_solved"),
            "branch_gpr": gpr,
            "branch_solved": bool(dumped.get("success")) and dumped.get("error_type") is None,
            "branch_steps": dumped.get("steps"),
            "branch_error_type": dumped.get("error_type"),
            "correction": point["correction"],
            "run_id": job["run_id"],
            "replay_k": k,
            "key": key,
        }
    else:
        branch_row = {
            "campaign": job["campaign"],
            "seed": job["seed"],
            "task_id": job["task_id"],
            "i": job["i"],
            "step": point["step"],
            "branch_seed": job["branch_seed"],
            "actual_gpr": job.get("actual_gpr"),
            "actual_solved": job.get("actual_solved"),
            "branch_gpr": None,
            "branch_solved": False,
            "branch_steps": None,
            "branch_error_type": error_type or "crash",
            "correction": point["correction"],
            "run_id": job["run_id"],
            "replay_k": k,
            "key": key,
        }
    append_jsonl(branch_path, branch_row)
    maybe_write_point(
        out_root,
        {
            "campaign": job["campaign"],
            "seed": job["seed"],
            "task_id": job["task_id"],
            "i": job["i"],
            "step": point["step"],
            "actual_gpr": job.get("actual_gpr"),
            "actual_solved": job.get("actual_solved"),
            "correction": point["correction"],
        },
        list(job["branch_seeds"]),
    )
    refresh_derived(
        out_root,
        list(job["branch_seeds"]),
        Path(job["campaign_root"]),
        str(job["split"]),
        adapter,
    )
    return {"skipped": False, "key": key, "row": branch_row}


def _mp_worker(job: dict[str, Any]) -> dict[str, Any]:
    return run_one_branch(job)


def collect_jobs(
    *,
    campaign_root: Path,
    out_root: Path,
    split: str,
    branch_seeds: list[int],
    resume: bool,
    limit: int | None,
    env_kind: str,
    config: dict[str, Any],
    prices_path: str,
    adapter_fallback: str | None,
) -> list[dict[str, Any]]:
    campaign = campaign_root.name
    done = completed_branch_keys(load_jsonl(out_root / "branch_runs.jsonl")) if resume else set()
    split_ids = load_split_filter(split) if env_kind == "appworld" else None
    jobs: list[dict[str, Any]] = []
    for task_dir in iter_episode_dirs(campaign_root):
        try:
            seed = int(task_dir.parent.name)
        except ValueError:
            continue
        task_id = task_dir.name
        if split_ids is not None and task_id not in split_ids:
            continue
        events_path = task_dir / "events.jsonl"
        result_path = task_dir / "result.json"
        result = {}
        if result_path.is_file():
            try:
                loaded = json.loads(result_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    result = loaded
            except (OSError, json.JSONDecodeError):
                result = {}
        events = _events_of_last_attempt(events_path)
        adapter = adapter_from_events(events, adapter_fallback)
        actual_gpr = result_gpr(result)
        actual_solved = bool(result.get("success"))
        for point in enumerate_intervention_points(events):
            for bseed in branch_seeds:
                key = branch_key(campaign, seed, task_id, point["i"], bseed)
                run_id = branch_run_id(seed, task_id, point["i"], bseed)
                if resume and key in done:
                    continue
                if resume and (out_root / run_id / "result.json").is_file():
                    continue
                jobs.append(
                    {
                        "out_root": str(out_root),
                        "campaign_root": str(campaign_root),
                        "campaign": campaign,
                        "seed": seed,
                        "task_id": task_id,
                        "i": point["i"],
                        "step": point["step"],
                        "branch_seed": bseed,
                        "branch_seeds": list(branch_seeds),
                        "key": key,
                        "run_id": run_id,
                        "events_path": str(events_path),
                        "actual_gpr": actual_gpr,
                        "actual_solved": actual_solved,
                        "env_kind": env_kind,
                        "experiment_name": f"{out_root.name}/{run_id}",
                        "config": config,
                        "prices_path": prices_path,
                        "adapter": adapter,
                        "resume": resume,
                        "split": split,
                    }
                )
    if limit is not None:
        jobs = jobs[: max(0, int(limit))]
    return jobs


def run_branches(
    *,
    campaign_root: Path,
    out_root: Path,
    split: str,
    branch_seeds: list[int],
    workers: int,
    resume: bool,
    limit: int | None,
    env_kind: str,
    config: dict[str, Any] | None,
    prices_path: str | None,
) -> dict[str, Any]:
    out_root.mkdir(parents=True, exist_ok=True)
    cfg = dict(config or {})
    prices = str(prices_path or cfg.get("prices") or DEFAULT_PRICES)
    adapter_fallback = (cfg.get("executor") or {}).get("lora_name") or cfg.get("adapter_name") or DEFAULT_ADAPTER
    if resume:
        repair_points(out_root, branch_seeds)
    jobs = collect_jobs(
        campaign_root=campaign_root,
        out_root=out_root,
        split=split,
        branch_seeds=branch_seeds,
        resume=resume,
        limit=limit,
        env_kind=env_kind,
        config=cfg,
        prices_path=prices,
        adapter_fallback=adapter_fallback,
    )
    results: list[dict[str, Any]] = []
    n_workers = max(1, int(workers))
    if jobs:
        if n_workers <= 1 or len(jobs) == 1:
            results = [_mp_worker(job) for job in jobs]
        else:
            ctx = multiprocessing.get_context("fork")
            with ctx.Pool(min(n_workers, len(jobs))) as pool:
                results = list(pool.imap_unordered(_mp_worker, jobs))
    refresh_derived(out_root, branch_seeds, campaign_root, split, adapter_fallback)
    n_skipped = sum(1 for r in results if r.get("skipped"))
    return {
        "out_root": str(out_root),
        "n_jobs": len(jobs),
        "n_skipped": n_skipped,
        "n_finished": sum(1 for r in results if not r.get("skipped")),
        "n_branch_runs": len(load_jsonl(out_root / "branch_runs.jsonl")),
        "n_points": len(load_jsonl(out_root / "branches.jsonl")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="branch_counterfactual.py")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--out-root", required=True, help="Output campaign directory (hj6_branches_<split>_<date>)")
    parser.add_argument("--branch-seeds", nargs="+", type=int, default=list(DEFAULT_BRANCH_SEEDS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None, help="Max new branches this invocation (smoke/resume)")
    parser.add_argument("--resume", dest="resume", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument("--env", choices=["mock", "appworld"], default="appworld")
    parser.add_argument("--config")
    parser.add_argument("--prices")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_branches(
        campaign_root=Path(args.campaign_root),
        out_root=Path(args.out_root),
        split=str(args.split),
        branch_seeds=[int(s) for s in args.branch_seeds],
        workers=int(args.workers),
        resume=bool(args.resume),
        limit=args.limit,
        env_kind=str(args.env),
        config=load_config(args.config),
        prices_path=args.prices,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
