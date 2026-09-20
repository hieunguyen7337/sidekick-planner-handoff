"""Counterfactual branches for fixed_k: ablate only the FOCAL intervention.

Two conditions continue from the same replayed prefix (state just before
intervention i). The treated arm injects the recorded correction; the untreated
arm omits it.

``--untreated-mode schedule_live`` (default, frozen estimand): both arms skip
the scheduled tick at s, then the reviewer stays live on its normal schedule
and calls planner.correct() on the branch's own state.

``--untreated-mode suppress_next``: both arms also skip the next scheduled
tick after s (the substitute). The arms then differ only by the injected
correction at s.

Resume keys on (point, condition, branch_seed). Derived files are rebuilt from
``branch_runs.jsonl`` so a kill never drops a finished branch.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import multiprocessing
import os
import random
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
from sidekick.runner import DEFAULT_PRICES, load_config, make_env, make_executor, make_planner  # noqa: E402
from sidekick.systems.loop import (  # noqa: E402
    DEFAULT_MAX_PLANNER_CALLS,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOKENS_PER_EPISODE,
    DEFAULT_PER_STEP_TIMEOUT_S,
    EpisodePrefix,
    RunLimits,
    SystemPolicy,
    next_scheduled_review_step,
    run_episode,
)
from sidekick.training.sft_data import _history_from_events  # noqa: E402
from sidekick.trajectories.eventlog import EventLog  # noqa: E402

BRANCH_TEMPERATURE = 0.7
DEFAULT_BRANCH_SEEDS = (101, 102)
DEFAULT_ADAPTER = "sft_b"
DEFAULT_REVIEW_EVERY_K = 5
SYSTEM_NAME = "fixed_k"
CONDITIONS = ("treated", "untreated")
UNTREATED_MODE_SCHEDULE_LIVE = "schedule_live"
UNTREATED_MODE_SUPPRESS_NEXT = "suppress_next"
UNTREATED_MODES = (UNTREATED_MODE_SCHEDULE_LIVE, UNTREATED_MODE_SUPPRESS_NEXT)
DEFAULT_UNTREATED_MODE = UNTREATED_MODE_SCHEDULE_LIVE

# Frozen schedule_live strings. Do not paraphrase: existing manifests quote them.
_REVIEW_EVERY_K_SCHEDULE_LIVE = (
    "live on the original schedule after the focal step; "
    "the scheduled tick at s is skipped and either injected "
    "(treated) or omitted (untreated)"
)
_ESTIMAND_SCHEDULE_LIVE = (
    "Q(policy with intervention i present) - "
    "Q(policy with intervention i omitted); later reviews live"
)
_REVIEW_EVERY_K_SUPPRESS_NEXT = (
    "both arms skip the scheduled tick at s and the next scheduled tick "
    "the schedule would actually have fired after s; treated injects at s, "
    "untreated omits at s; later ticks after that stay live in both arms"
)
_ESTIMAND_SUPPRESS_NEXT = (
    "Q(policy with intervention i present) - "
    "Q(policy with intervention i omitted); "
    "the next scheduled review after s is suppressed in both arms; "
    "later reviews after that stay live"
)


def resolve_untreated_mode(value: str | None) -> str:
    mode = DEFAULT_UNTREATED_MODE if value is None else str(value)
    if mode not in UNTREATED_MODES:
        raise ValueError(f"untreated_mode must be one of {list(UNTREATED_MODES)}, got {mode!r}")
    return mode


def untreated_mode_strings(untreated_mode: str | None) -> tuple[str, str]:
    """``(review_every_k, estimand)`` texts for the ``branch_config`` block."""
    if resolve_untreated_mode(untreated_mode) == UNTREATED_MODE_SUPPRESS_NEXT:
        return _REVIEW_EVERY_K_SUPPRESS_NEXT, _ESTIMAND_SUPPRESS_NEXT
    return _REVIEW_EVERY_K_SCHEDULE_LIVE, _ESTIMAND_SCHEDULE_LIVE


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


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
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


def review_every_k_from_events(events: list[Event], default: int = DEFAULT_REVIEW_EVERY_K) -> int:
    start = next((e for e in events if e.event_type == "run_start"), None)
    policy = (start.payload or {}).get("policy") or {} if start else {}
    raw = policy.get("review_every_k", default)
    if raw is None:
        return int(default)
    return int(raw)


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile. ``p=0.75`` is the third quartile."""
    xs = sorted(float(v) for v in values)
    if not xs:
        raise ValueError("percentile of empty sample")
    if len(xs) == 1:
        return xs[0]
    k = p * (len(xs) - 1)
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    frac = k - lo
    return xs[lo] + frac * (xs[hi] - xs[lo])


def mean_or_none(values: list[float | None]) -> float | None:
    if any(v is None for v in values) or not values:
        return None
    return sum(float(v) for v in values) / len(values)  # type: ignore[arg-type]


def label_focal(
    treated_gpr: list[float | None],
    untreated_gpr: list[float | None],
    delta: float | None,
    delta_band: float | None,
) -> dict[str, Any]:
    """Pre-registered band labels. Any missing sample → incomplete, never imputed."""
    samples = list(treated_gpr) + list(untreated_gpr)
    if (
        any(g is None for g in samples)
        or len(treated_gpr) < 1
        or len(untreated_gpr) < 1
        or delta is None
        or delta_band is None
    ):
        return {
            "needed": None,
            "needless": None,
            "ambiguous": None,
            "needed_strict": None,
            "harmful": None,
            "label_status": "incomplete",
        }
    treated_f = [float(g) for g in treated_gpr]  # type: ignore[arg-type]
    untreated_f = [float(g) for g in untreated_gpr]  # type: ignore[arg-type]
    needed = bool(delta > delta_band)
    needless = bool(delta < -delta_band)
    ambiguous = bool(abs(delta) <= delta_band)
    return {
        "needed": needed,
        "needless": needless,
        "ambiguous": ambiguous,
        "needed_strict": min(treated_f) > max(untreated_f),
        "harmful": needless,
        "label_status": "complete",
    }


def compute_delta_band(treated_pairs: list[tuple[float, float]]) -> float | None:
    """δ := 75th percentile of |treated[101] − treated[102]| over train points."""
    if not treated_pairs:
        return None
    diffs = [abs(a - b) for a, b in treated_pairs]
    return percentile(diffs, 0.75)


def factual_vs_treated_summary(point_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Factual episode is a draw from treated; it should sit in treated_gpr's spread."""
    signed: list[float] = []
    n_outside = 0
    for row in point_rows:
        actual = row.get("actual_gpr")
        treated = row.get("treated_gpr")
        if actual is None or not isinstance(treated, list) or not treated:
            continue
        if any(g is None for g in treated):
            continue
        vals = [float(g) for g in treated]
        actual_f = float(actual)
        signed.append(actual_f - (sum(vals) / len(vals)))
        if actual_f < min(vals) or actual_f > max(vals):
            n_outside += 1
    n = len(signed)
    return {
        "n_points_compared": n,
        "mean_signed_difference": (sum(signed) / n) if n else None,
        "fraction_factual_outside_treated_range": (n_outside / n) if n else None,
        "note": (
            "signed difference is actual_gpr - mean(treated_gpr); "
            "factual is a treated-condition draw and should lie inside treated_gpr"
        ),
    }


def task_clustered_bootstrap(
    point_rows: list[dict[str, Any]],
    stat_fn,
    *,
    n_boot: int = 1000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any] | None:
    """Resample whole tasks (all seeds and points of a task travel together)."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in point_rows:
        if row.get("label_status") != "complete":
            continue
        task_id = row.get("task_id")
        if task_id is None:
            continue
        groups.setdefault(str(task_id), []).append(row)
    if not groups:
        return None
    rng = random.Random(seed)
    keys = list(groups)
    stats: list[float] = []
    for _ in range(int(n_boot)):
        sample: list[dict[str, Any]] = []
        for key in rng.choices(keys, k=len(keys)):
            sample.extend(groups[key])
        val = stat_fn(sample)
        if val is not None:
            stats.append(float(val))
    if not stats:
        return None
    stats.sort()
    lo_i = int((alpha / 2) * (len(stats) - 1))
    hi_i = int((1.0 - alpha / 2) * (len(stats) - 1))
    return {
        "low": stats[lo_i],
        "high": stats[hi_i],
        "n_boot": int(n_boot),
        "clustering": "task",
    }


def needed_fraction(rows: list[dict[str, Any]]) -> float | None:
    complete = [r for r in rows if r.get("label_status") == "complete"]
    if not complete:
        return None
    return sum(1 for r in complete if r.get("needed") is True) / len(complete)


def mean_delta_crn(rows: list[dict[str, Any]]) -> float | None:
    vals = [
        r.get("delta_crn")
        for r in rows
        if r.get("label_status") == "complete" and r.get("delta_crn") is not None
    ]
    if not vals:
        return None
    return sum(float(v) for v in vals) / len(vals)


def branch_key(
    campaign: str, seed: int, task_id: str, i: int, condition: str, branch_seed: int
) -> str:
    return f"{campaign}/{seed}/{task_id}/{i}/{condition}/{branch_seed}"


def point_key(campaign: str, seed: int, task_id: str, i: int) -> str:
    return f"{campaign}/{seed}/{task_id}/{i}"


def branch_run_id(seed: int, task_id: str, i: int, condition: str, branch_seed: int) -> str:
    return f"{SYSTEM_NAME}/{seed}/{task_id}__b{i}_{condition}_s{branch_seed}"


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


def result_gpr(result: dict[str, Any] | None) -> float | None:
    if not result:
        return None
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


def is_done_row(row: dict[str, Any]) -> bool:
    """A row is done only if it represents a usable result, not a crashed one.

    ``branch_error_type`` must be falsy, and the row must carry a usable metric:
    ``branch_gpr is not None`` (the brief's criterion; every production crash row
    has ``branch_gpr: null`` and ``branch_error_type: "crash"`` [OBSERVED
    scripts/setup/branch_counterfactual.py:980-985]) or, for environments that
    return no GPR at all (e.g. the mock env used by the suite), a recorded
    ``branch_steps``. Rows failing this are retried on the next resume;
    ``branch_runs.jsonl`` stays append-only and superseding happens at
    aggregation time (last row per key wins, matching ``group_branch_samples``
    [OBSERVED :631]).
    """
    if row.get("branch_error_type"):
        return False
    return row.get("branch_gpr") is not None or row.get("branch_steps") is not None


def completed_branch_keys(rows: list[dict[str, Any]], *, retry_errors: bool = True) -> set[str]:
    """Keys whose last row represents a usable (done) result.

    Last row per key wins, mirroring the aggregation's ``setdefault`` overwrite
    [OBSERVED :631]. With ``retry_errors=False`` the pre-W15 behaviour is restored:
    every row counts, including crashed ones, so a run can be reproduced exactly.
    """
    last: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            key = branch_key(
                str(row["campaign"]),
                int(row["seed"]),
                str(row["task_id"]),
                int(row["i"]),
                str(row["condition"]),
                int(row["branch_seed"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        last[key] = row
    if not retry_errors:
        return set(last)
    return {key for key, row in last.items() if is_done_row(row)}


def aux_from_branch_events(run_dir: Path, fallback_gpr: float | None) -> tuple[float | None, int]:
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return fallback_gpr, 0
    try:
        events = list(EventLog.read(path))
    except Exception:
        return fallback_gpr, 0
    local: float | None = None
    n_later = 0
    for ev in events:
        payload = ev.payload or {}
        if ev.event_type == "intervention" and payload.get("source") == "live_policy":
            n_later += 1
        if ev.event_type == "evaluate" and payload.get("horizon") == "local":
            local = result_gpr(payload)
    if local is None:
        local = fallback_gpr
    return local, n_later


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


def load_frozen_delta_band(path: Path | None) -> float | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("delta_band_delta")
    if raw is None:
        raw = (data.get("branch_config") or {}).get("delta_band_delta")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def default_train_manifest(out_root: Path, split: str) -> Path | None:
    name = out_root.name
    token = f"_{split}_"
    if token not in name:
        return None
    sibling = out_root.parent / name.replace(token, "_train_", 1) / "manifest.json"
    return sibling if sibling.is_file() else None


def assemble_point_record(
    meta: dict[str, Any],
    samples: dict[tuple[str, int], dict[str, Any]],
    branch_seeds: list[int],
    delta_band: float | None,
) -> dict[str, Any]:
    treated = [samples.get(("treated", s), {}).get("branch_gpr") for s in branch_seeds]
    untreated = [samples.get(("untreated", s), {}).get("branch_gpr") for s in branch_seeds]
    treated_local = [samples.get(("treated", s), {}).get("branch_gpr_local") for s in branch_seeds]
    untreated_local = [
        samples.get(("untreated", s), {}).get("branch_gpr_local") for s in branch_seeds
    ]
    delta_mean = None
    mean_t = mean_or_none(treated)
    mean_u = mean_or_none(untreated)
    if mean_t is not None and mean_u is not None:
        delta_mean = mean_t - mean_u
    paired: list[float] = []
    for seed in branch_seeds:
        t = samples.get(("treated", seed), {}).get("branch_gpr")
        u = samples.get(("untreated", seed), {}).get("branch_gpr")
        if t is None or u is None:
            paired = []
            break
        paired.append(float(t) - float(u))
    delta_crn = (sum(paired) / len(paired)) if paired else None
    paired_local: list[float] = []
    for seed in branch_seeds:
        t = samples.get(("treated", seed), {}).get("branch_gpr_local")
        u = samples.get(("untreated", seed), {}).get("branch_gpr_local")
        if t is None or u is None:
            paired_local = []
            break
        paired_local.append(float(t) - float(u))
    delta_local = (sum(paired_local) / len(paired_local)) if paired_local else None
    delta = delta_crn
    labels = label_focal(treated, untreated, delta, delta_band)
    return {
        "campaign": meta["campaign"],
        "seed": meta["seed"],
        "task_id": meta["task_id"],
        "i": meta["i"],
        "step": meta["step"],
        "actual_gpr": meta.get("actual_gpr"),
        "actual_solved": meta.get("actual_solved"),
        "treated_gpr": treated,
        "untreated_gpr": untreated,
        "treated_gpr_local": treated_local,
        "untreated_gpr_local": untreated_local,
        "delta_mean": delta_mean,
        "delta_crn": delta_crn,
        "delta_local": delta_local,
        "delta": delta,
        "needed": labels["needed"],
        "needless": labels["needless"],
        "ambiguous": labels["ambiguous"],
        "needed_strict": labels["needed_strict"],
        "harmful": labels["harmful"],
        "label_status": labels["label_status"],
        "delta_band_delta": delta_band,
        "n_later_reviews": {
            "treated": [samples.get(("treated", s), {}).get("n_later_reviews") for s in branch_seeds],
            "untreated": [
                samples.get(("untreated", s), {}).get("n_later_reviews") for s in branch_seeds
            ],
        },
        "correction": meta.get("correction") or "",
        "branch_seeds": list(branch_seeds),
    }


def treated_pairs_from_samples(
    grouped: dict[str, dict[tuple[str, int], dict[str, Any]]],
    branch_seeds: list[int],
) -> list[tuple[float, float]]:
    if len(branch_seeds) < 2:
        return []
    s0, s1 = int(branch_seeds[0]), int(branch_seeds[1])
    pairs: list[tuple[float, float]] = []
    for samples in grouped.values():
        a = samples.get(("treated", s0), {}).get("branch_gpr")
        b = samples.get(("treated", s1), {}).get("branch_gpr")
        if a is None or b is None:
            continue
        pairs.append((float(a), float(b)))
    return pairs


def group_branch_samples(
    branch_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[tuple[str, int], dict[str, Any]]]]:
    grouped_meta: dict[str, dict[str, Any]] = {}
    samples: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
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
            grouped_meta[pk] = meta
            samples.setdefault(pk, {})[(str(row["condition"]), int(row["branch_seed"]))] = row
        except (KeyError, TypeError, ValueError):
            continue
    return grouped_meta, samples


def point_complete_samples(
    seed_map: dict[tuple[str, int], dict[str, Any]], branch_seeds: list[int]
) -> bool:
    for condition in CONDITIONS:
        for seed in branch_seeds:
            if (condition, int(seed)) not in seed_map:
                return False
    return True


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


def write_manifest(
    out_root: Path,
    *,
    campaign_root: Path,
    split: str,
    branch_seeds: list[int],
    point_rows: list[dict[str, Any]],
    branch_rows: list[dict[str, Any]],
    adapter: str | None,
    delta_band: float | None,
    untreated_mode: str = DEFAULT_UNTREATED_MODE,
) -> None:
    untreated_mode = resolve_untreated_mode(untreated_mode)
    review_every_k_text, estimand_text = untreated_mode_strings(untreated_mode)
    branches_path = out_root / "branches.jsonl"
    n_complete = sum(1 for r in point_rows if r.get("label_status") == "complete")
    n_incomplete = sum(1 for r in point_rows if r.get("label_status") != "complete")
    n_needed = sum(1 for r in point_rows if r.get("needed") is True)
    n_needless = sum(1 for r in point_rows if r.get("needless") is True)
    n_ambiguous = sum(1 for r in point_rows if r.get("ambiguous") is True)
    n_harmful = sum(1 for r in point_rows if r.get("harmful") is True)
    n_strict = sum(1 for r in point_rows if r.get("needed_strict") is True)
    factual = factual_vs_treated_summary(point_rows)
    write_json(
        out_root / "manifest.json",
        {
            "n_points": len(point_rows),
            "n_branches": len(branch_rows),
            "n_complete": n_complete,
            "n_incomplete": n_incomplete,
            "n_needed": n_needed,
            "n_needless": n_needless,
            "n_ambiguous": n_ambiguous,
            "n_harmful": n_harmful,
            "n_needed_strict": n_strict,
            "delta_band_delta": delta_band,
            "delta_band_rule": (
                "75th percentile of |treated_gpr[101]-treated_gpr[102]| "
                "over train-split points with both treated replicates"
            ),
            "delta_band_frozen_on": "train",
            "source_campaign": str(campaign_root),
            "source_commit": source_commit(campaign_root),
            "branches_jsonl_sha256": (
                sha256_file(branches_path) if branches_path.is_file() else None
            ),
            "split": split,
            "factual_vs_treated": factual,
            "needed_fraction": needed_fraction(point_rows),
            "needed_fraction_ci": task_clustered_bootstrap(point_rows, needed_fraction),
            "mean_delta_crn": mean_delta_crn(point_rows),
            "mean_delta_crn_ci": task_clustered_bootstrap(point_rows, mean_delta_crn),
            "ci_clustering": "task",
            "branch_config": {
                "temperature": BRANCH_TEMPERATURE,
                "branch_seeds": list(branch_seeds),
                "conditions": list(CONDITIONS),
                "replicates_per_condition": len(branch_seeds),
                "max_steps_rule": (
                    "original max_steps counted from intervention step s "
                    "(branch takes steps s..max_steps, i.e. remaining includes s)"
                ),
                "review_every_k": review_every_k_text,
                "untreated_mode": untreated_mode,
                "allow_executor_ask": False,
                "planner_drives": False,
                "adapter": adapter or DEFAULT_ADAPTER,
                "sampling_seed": "branch_seed passed to executor.complete(seed=...)",
                "delta_band_delta": delta_band,
                "estimand": estimand_text,
                "replay_prefix_k": (
                    "executed CODE/COMPLETE actions before the intervention "
                    "(not event index, not episode step)"
                ),
            },
        },
    )


def rebuild_derived(
    out_root: Path,
    branch_seeds: list[int],
    campaign_root: Path,
    split: str,
    adapter: str | None,
    *,
    delta_band: float | None = None,
    freeze_from_train: bool = False,
    untreated_mode: str = DEFAULT_UNTREATED_MODE,
) -> float | None:
    branch_rows = load_jsonl(out_root / "branch_runs.jsonl")
    grouped_meta, samples = group_branch_samples(branch_rows)
    if freeze_from_train and split == "train":
        computed = compute_delta_band(treated_pairs_from_samples(samples, branch_seeds))
        delta_band = computed if computed is not None else delta_band
    elif delta_band is None and split == "train":
        delta_band = compute_delta_band(treated_pairs_from_samples(samples, branch_seeds))
    point_rows: list[dict[str, Any]] = []
    for pk, meta in grouped_meta.items():
        seed_map = samples.get(pk) or {}
        if not point_complete_samples(seed_map, branch_seeds):
            continue
        point_rows.append(assemble_point_record(meta, seed_map, branch_seeds, delta_band))
    write_jsonl_atomic(out_root / "branches.jsonl", point_rows)
    write_json(out_root / "oracle_labels.json", build_oracle_labels(point_rows))
    write_manifest(
        out_root,
        campaign_root=campaign_root,
        split=split,
        branch_seeds=branch_seeds,
        point_rows=point_rows,
        branch_rows=branch_rows,
        adapter=adapter,
        delta_band=delta_band,
        untreated_mode=untreated_mode,
    )
    return delta_band


def _make_env(job: dict[str, Any]) -> BaseEnv:
    return make_env(job["env_kind"], job["experiment_name"], job.get("config") or {})


def _make_planner(job: dict[str, Any]):
    if job.get("env_kind") == "mock":
        return MockPlanner()
    cfg = dict(job.get("config") or {})
    return make_planner(cfg)


def planner_cost_from_events(run_dir: Path) -> tuple[int | None, int | None]:
    """(planner calls, planner tokens) from a branch run's own events.jsonl.

    Sums ``usage`` over events whose actor is the planner. Returns ``(None, None)``
    when the log is missing or carries no planner usage — never a silent 0.
    """
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return None, None
    try:
        events = list(EventLog.read(path))
    except Exception:
        return None, None
    calls = 0
    tokens = 0
    seen = False
    for ev in events:
        if ev.actor != "planner" or ev.usage is None:
            continue
        seen = True
        # Usage.n_calls is Field(1, ge=0): missing/None may default to 1, but a
        # recorded 0 is measured-zero and must not be coerced [schemas.py:34-36].
        n_calls = ev.usage.n_calls
        calls += 1 if n_calls is None else int(n_calls)
        # Same four fields as CostLedger._tokens [ledger.py:47-53].
        tokens += CostLedger._tokens(ev.usage.model_dump())
    return (calls, tokens) if seen else (None, None)


def planner_cost_from_result(
    dumped: dict[str, Any] | None,
) -> tuple[int | None, int | None, int | None]:
    """(replay-inclusive calls, live tokens, live calls) from a result.

    Primary source: ``RunResult.n_planner_calls`` (replay-inclusive prefix
    counters) [OBSERVED src/sidekick/protocols/schemas.py:141],
    ``totals["planner_tokens_total"]``, and ``totals["planner_calls_total"]``
    (ledger live-only) [OBSERVED src/sidekick/cost/ledger.py:40-41].
    """
    if dumped is None:
        return None, None, None
    calls = dumped.get("n_planner_calls")
    if calls is not None:
        try:
            calls = int(calls)
        except (TypeError, ValueError):
            calls = None
    totals = dumped.get("totals") or {}
    tokens = totals.get("planner_tokens_total")
    if tokens is not None:
        try:
            tokens = int(tokens)
        except (TypeError, ValueError):
            tokens = None
    live_calls = totals.get("planner_calls_total")
    if live_calls is not None:
        try:
            live_calls = int(live_calls)
        except (TypeError, ValueError):
            live_calls = None
    return calls, tokens, live_calls


def error_detail_from_events(run_dir: Path) -> str | None:
    """First error event's ``exc_type`` plus the first 200 chars of ``detail``."""
    path = run_dir / "events.jsonl"
    if not path.is_file():
        return None
    try:
        events = list(EventLog.read(path))
    except Exception:
        return None
    for ev in events:
        if ev.event_type != "error":
            continue
        payload = ev.payload or {}
        detail = str(payload.get("detail") or "")[:200]
        exc_type = str(payload.get("exc_type") or "")
        if exc_type and detail:
            return f"{exc_type}: {detail}"
        if exc_type:
            return exc_type
        if detail:
            return detail
        return None
    return None


def live_planner_calls_charged(row: dict[str, Any], unknown_factor: int) -> int:
    """Live hosted-planner calls for the budget cap.

    Missing field or ``None`` is charged at ``unknown_factor`` (the per-branch
    cap, 81 in the B1 prereg), never silently 0. A recorded 0 (replayed ticks
    only) is measured-zero and must stay 0.
    """
    if "branch_live_planner_calls" not in row:
        return int(unknown_factor)
    calls = row.get("branch_live_planner_calls")
    if calls is None:
        return int(unknown_factor)
    return int(calls)


def spent_from_rows(rows: list[dict[str, Any]], unknown_factor: int) -> int:
    """Sum live planner calls over the last row per branch key."""
    last: dict[str, dict[str, Any]] = {}
    for row in rows:
        if all(k in row for k in ("campaign", "seed", "task_id", "i", "condition", "branch_seed")):
            try:
                key = branch_key(
                    str(row["campaign"]),
                    int(row["seed"]),
                    str(row["task_id"]),
                    int(row["i"]),
                    str(row["condition"]),
                    int(row["branch_seed"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            last[key] = row
    spent = 0
    for row in last.values():
        spent += live_planner_calls_charged(row, unknown_factor)
    return spent


def _row_from_result(
    job: dict[str, Any],
    point: dict[str, Any],
    k: int,
    dumped: dict[str, Any] | None,
    error_type: str | None,
) -> dict[str, Any]:
    gpr = None
    solved = False
    steps = None
    err = error_type
    if dumped is not None:
        gpr = dumped.get("goal_pass_rate")
        if dumped.get("error_type") == "crash":
            gpr = None
        solved = bool(dumped.get("success")) and dumped.get("error_type") is None
        steps = dumped.get("steps")
        err = dumped.get("error_type")
    local, n_later = aux_from_branch_events(
        Path(job["out_root"]) / job["run_id"], result_gpr({"goal_pass_rate": gpr})
    )
    run_dir = Path(job["out_root"]) / job["run_id"]
    calls, tokens, live_calls = planner_cost_from_result(dumped)
    if calls is None or tokens is None:
        ev_calls, ev_tokens = planner_cost_from_events(run_dir)
        if calls is None:
            calls = ev_calls
        if tokens is None:
            tokens = ev_tokens
    err_final = err if dumped is not None else (error_type or "crash")
    err_detail = error_detail_from_events(run_dir) if err_final else None
    return {
        "campaign": job["campaign"],
        "seed": job["seed"],
        "task_id": job["task_id"],
        "i": job["i"],
        "step": point["step"],
        "condition": job["condition"],
        "branch_seed": job["branch_seed"],
        "actual_gpr": job.get("actual_gpr"),
        "actual_solved": job.get("actual_solved"),
        "branch_gpr": gpr if dumped is not None else None,
        "branch_gpr_local": local,
        "branch_solved": solved,
        "branch_steps": steps,
        "branch_error_type": err_final,
        "branch_error_detail": err_detail,
        "branch_planner_calls": calls,
        "branch_planner_tokens": tokens,
        "branch_live_planner_calls": live_calls,
        "n_later_reviews": n_later,
        "correction": point["correction"],
        "run_id": job["run_id"],
        "replay_k": k,
        "key": job["key"],
        "sampling_seed": job["branch_seed"],
        "review_every_k": job.get("review_every_k"),
        "untreated_mode": resolve_untreated_mode(job.get("untreated_mode")),
    }


def run_one_branch(job: dict[str, Any]) -> dict[str, Any]:
    out_root = Path(job["out_root"])
    key = job["key"]
    branch_path = out_root / "branch_runs.jsonl"
    if job.get("resume"):
        if key in completed_branch_keys(
            load_jsonl(branch_path), retry_errors=bool(job.get("retry_errors", True))
        ):
            return {"skipped": True, "key": key}
        result_file = out_root / job["run_id"] / "result.json"
        if result_file.is_file():
            events = _events_of_last_attempt(job["events_path"])
            points = enumerate_intervention_points(events)
            point = points[int(job["i"])]
            prefix = prefix_events_before_intervention(events, int(job["i"]))
            k = executed_prefix_k(prefix)
            try:
                dumped = json.loads(result_file.read_text(encoding="utf-8"))
                if not isinstance(dumped, dict):
                    dumped = None
            except (OSError, json.JSONDecodeError):
                dumped = None
            row = _row_from_result(job, point, k, dumped, None if dumped else "crash")
            append_jsonl(branch_path, row)
            return {"skipped": True, "key": key, "reason": "result_exists", "row": row}

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
        cfg["executor"] = {
            "type": "mock",
            **{kk: v for kk, v in exec_cfg.items() if kk == "lora_name"},
        }
        cfg["executor_type"] = "mock"
    else:
        cfg["executor"] = exec_cfg
    executor = make_executor(cfg)
    planner = _make_planner(job)
    prices = PriceSchedule.load(job["prices_path"])
    ledger = CostLedger(prices)
    log = EventLog(out_root, job["run_id"])
    env: BaseEnv | None = None
    result: RunResult | None = None
    error_type: str | None = None
    review_k = int(job.get("review_every_k") or review_every_k_from_events(events))
    untreated_mode = resolve_untreated_mode(job.get("untreated_mode"))
    inject = point["correction"] if job["condition"] == "treated" else None
    skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT
    local_step = next_scheduled_review_step(int(point["step"]), review_k)
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
                "condition": job["condition"],
                "intervention_index": job["i"],
                "step": point["step"],
                "replay_k": k,
                "campaign": job["campaign"],
                "experiment_name": job["experiment_name"],
                "sampling_seed": job["branch_seed"],
                "review_every_k": review_k,
                "untreated_mode": untreated_mode,
                "skip_next_scheduled_review": skip_next,
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
                review_every_k=review_k,
                adapter_name=adapter,
            ),
            limits=limits,
            task_id=job["task_id"],
            seed=int(job["seed"]),
            log=log,
            ledger=ledger,
            prefix=EpisodePrefix(
                events=prefix,
                start_step=int(point["step"]),
                inject_correction=inject,
                skip_review_at_start=True,
                local_eval_step=local_step,
                skip_next_scheduled_review=skip_next,
            ),
            sampling_seed=int(job["branch_seed"]),
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
        closer_p = getattr(planner, "close", None)
        if callable(closer_p):
            closer_p()

    dumped = result.model_dump() if result is not None else None
    if dumped is not None:
        dest = out_root / job["run_id"] / "result.json"
        dest.write_text(json.dumps(dumped, sort_keys=True) + "\n", encoding="utf-8")
        branch_row = _row_from_result(job, point, k, dumped, dumped.get("error_type"))
        if dumped.get("error_type") == "crash":
            branch_row["branch_gpr"] = None
    else:
        branch_row = _row_from_result(job, point, k, None, error_type or "crash")
        branch_row["branch_gpr"] = None
        branch_row["branch_solved"] = False
        branch_row["branch_steps"] = None
    append_jsonl(branch_path, branch_row)
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
    retry_errors: bool = True,
    untreated_mode: str = DEFAULT_UNTREATED_MODE,
) -> list[dict[str, Any]]:
    untreated_mode = resolve_untreated_mode(untreated_mode)
    campaign = campaign_root.name
    done = (
        completed_branch_keys(
            load_jsonl(out_root / "branch_runs.jsonl"), retry_errors=retry_errors
        )
        if resume
        else set()
    )
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
        result: dict[str, Any] = {}
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
        review_k = review_every_k_from_events(events)
        for point in enumerate_intervention_points(events):
            for condition in CONDITIONS:
                for bseed in branch_seeds:
                    key = branch_key(campaign, seed, task_id, point["i"], condition, bseed)
                    run_id = branch_run_id(seed, task_id, point["i"], condition, bseed)
                    if resume and key in done:
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
                            "condition": condition,
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
                            "retry_errors": retry_errors,
                            "split": split,
                            "review_every_k": review_k,
                            "correction": point["correction"],
                            "untreated_mode": untreated_mode,
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
    delta_band_delta: float | None = None,
    train_manifest: str | Path | None = None,
    retry_errors: bool = True,
    max_planner_calls_total: int | None = None,
    untreated_mode: str = DEFAULT_UNTREATED_MODE,
) -> dict[str, Any]:
    out_root.mkdir(parents=True, exist_ok=True)
    untreated_mode = resolve_untreated_mode(untreated_mode)
    cfg = dict(config or {})
    prices = str(prices_path or cfg.get("prices") or DEFAULT_PRICES)
    adapter_fallback = (
        (cfg.get("executor") or {}).get("lora_name") or cfg.get("adapter_name") or DEFAULT_ADAPTER
    )
    frozen = delta_band_delta
    train_path = Path(train_manifest) if train_manifest else default_train_manifest(out_root, split)
    if frozen is None and split != "train":
        frozen = load_frozen_delta_band(train_path)
    if resume:
        rebuild_derived(
            out_root,
            branch_seeds,
            campaign_root,
            split,
            adapter_fallback,
            delta_band=frozen,
            freeze_from_train=(split == "train"),
            untreated_mode=untreated_mode,
        )
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
        retry_errors=retry_errors,
        untreated_mode=untreated_mode,
    )
    # Per-branch planner-call factor, stated explicitly: the per-episode cap from
    # config (the same `max_planner_calls` the loop enforces per branch). It is an
    # upper bound, not a hidden constant — the projection line names it.
    planner_factor = int(
        ((cfg.get("limits") or {}).get("max_planner_calls")) or DEFAULT_MAX_PLANNER_CALLS
    )
    print(
        "PREFLIGHT "
        + json.dumps(
            {
                "branches_to_run": len(jobs),
                "per_branch_planner_call_factor": planner_factor,
                "projected_planner_calls": len(jobs) * planner_factor,
                "factor_source": "config limits.max_planner_calls (per-episode cap)",
                "max_planner_calls_total": max_planner_calls_total,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    def _row_planner_calls(res: dict[str, Any]) -> int:
        row = res.get("row") or {}
        # Unknown live cost is charged at the per-branch factor, never silently 0.
        return live_planner_calls_charged(row, planner_factor)

    def _spent_from_rows(rows: list[dict[str, Any]]) -> int:
        return spent_from_rows(rows, planner_factor)

    spent = _spent_from_rows(load_jsonl(out_root / "branch_runs.jsonl"))
    results: list[dict[str, Any]] = []
    budget_stopped = False
    n_workers = max(1, int(workers))
    if jobs:
        if n_workers <= 1 or len(jobs) == 1:
            for job in jobs:
                if max_planner_calls_total is not None and spent >= max_planner_calls_total:
                    budget_stopped = True
                    break
                res = _mp_worker(job)
                results.append(res)
                spent += _row_planner_calls(res)
        else:
            # Wave dispatch: in-flight branches always finish normally; the budget
            # is only checked between waves, before new branches are dispatched.
            ctx = multiprocessing.get_context("fork")
            with ctx.Pool(min(n_workers, len(jobs))) as pool:
                idx = 0
                while idx < len(jobs):
                    if max_planner_calls_total is not None and spent >= max_planner_calls_total:
                        budget_stopped = True
                        break
                    wave = jobs[idx : idx + n_workers]
                    idx += len(wave)
                    asyncs = [pool.apply_async(_mp_worker, (j,)) for j in wave]
                    for a in asyncs:
                        res = a.get()
                        results.append(res)
                        spent += _row_planner_calls(res)
    used_delta = rebuild_derived(
        out_root,
        branch_seeds,
        campaign_root,
        split,
        adapter_fallback,
        delta_band=frozen,
        freeze_from_train=(split == "train"),
        untreated_mode=untreated_mode,
    )
    point_rows = load_jsonl(out_root / "branches.jsonl")
    factual = factual_vs_treated_summary(point_rows)
    print("FACTUAL_VS_TREATED " + json.dumps(factual, sort_keys=True), flush=True)
    print("DELTA_BAND_DELTA " + json.dumps(used_delta), flush=True)
    n_skipped = sum(1 for r in results if r.get("skipped"))
    if budget_stopped:
        print(
            "PLANNER_BUDGET_STOPPED "
            + json.dumps(
                {
                    "max_planner_calls_total": max_planner_calls_total,
                    "planner_calls_spent": spent,
                    "n_branches_run": sum(1 for r in results if not r.get("skipped")),
                    "n_branches_remaining": len(jobs) - len(results),
                    "note": "resume with --resume continues from where this stopped",
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return {
        "out_root": str(out_root),
        "n_jobs": len(jobs),
        "n_skipped": n_skipped,
        "n_finished": sum(1 for r in results if not r.get("skipped")),
        "n_branch_runs": len(load_jsonl(out_root / "branch_runs.jsonl")),
        "n_points": len(point_rows),
        "delta_band_delta": used_delta,
        "factual_vs_treated": factual,
        "budget_max_planner_calls_total": max_planner_calls_total,
        "budget_stopped": budget_stopped,
        "planner_calls_spent": spent,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="branch_counterfactual.py")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument(
        "--out-root", required=True, help="Output campaign directory (hj6_branches_<split>_<date>)"
    )
    parser.add_argument("--branch-seeds", nargs="+", type=int, default=list(DEFAULT_BRANCH_SEEDS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None, help="Max new branches this invocation (smoke/resume)")
    parser.add_argument("--resume", dest="resume", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument("--env", choices=["mock", "appworld"], default="appworld")
    parser.add_argument("--config")
    parser.add_argument("--prices")
    parser.add_argument(
        "--delta-band-delta",
        type=float,
        default=None,
        help="Frozen δ from the train split. Required for a faithful dev labelling.",
    )
    parser.add_argument(
        "--train-manifest",
        default=None,
        help="Train-split manifest.json to read frozen delta_band_delta from.",
    )
    parser.add_argument(
        "--no-retry-errors",
        dest="retry_errors",
        action="store_false",
        help=(
            "Pre-W15 resume behaviour: crashed/error rows still count as done, "
            "so a run can be reproduced exactly as it was."
        ),
    )
    parser.set_defaults(retry_errors=True)
    parser.add_argument(
        "--max-planner-calls-total",
        type=int,
        default=None,
        help=(
            "Campaign-level planner-call budget. Once observed total crosses N, "
            "stop dispatching new branches, aggregate, and exit 0 (resume continues)."
        ),
    )
    parser.add_argument(
        "--untreated-mode",
        choices=list(UNTREATED_MODES),
        default=DEFAULT_UNTREATED_MODE,
        help=(
            "schedule_live (default, frozen estimand): later reviews stay live. "
            "suppress_next: both arms omit the next scheduled review after s."
        ),
    )
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
        delta_band_delta=args.delta_band_delta,
        train_manifest=args.train_manifest,
        retry_errors=bool(args.retry_errors),
        max_planner_calls_total=args.max_planner_calls_total,
        untreated_mode=str(args.untreated_mode),
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
