"""Fit a value function V(state) = P(episode ends successfully | state). CPU-only.

A7 (U-VF). Run inside a PBS job (`hpc -c 4 -m 16gb -t 00:30:00 python
scripts/setup/fit_value_function.py ...`), never on the login node. Zero
planner calls, no GPU.

Every step of every already-run episode is a labelled example: the episode's
outcome is known and is back-propagated to each step. The fitted artifact is a
``FeatureVerifier`` over the SAME frozen feature_lr_v1 spec — ``V(state)`` is
scored with the shared ``_extractor_features`` extractor, so fitting and
serving share one feature extractor (mirrors fit_feature_verifier.py).

Three traps handled explicitly (brief A7):
1. appended event logs: events after the LAST ``run_start`` only (replay.py
   ``_events_of_last_attempt`` rule, planner.py:688-708); every campaign,
   with a count of multi-``run_start`` files.
2. ``evaluate`` is terminal-only: labels come from per-episode ``result.json``
   ``success`` (boolean; fallback ``goal_pass_rate == 1.0``), never from the
   campaign ``runs.jsonl`` (no ``goal_pass_rate`` in older campaigns).
3. train/dev split is BY TASK ID (tasks recur across seeds and all steps of an
   episode share a label); a step-level split would leak.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.agents.verifier import (  # noqa: E402
    FEATURE_SPEC_VERSION,
    FeatureVerifier,
    _extractor_features,
    feature_spec,
)
from sidekick.replay import _events_of_last_attempt  # noqa: E402
from sidekick.systems.loop import (  # noqa: E402
    counters_from_events,
    last_observation_from_events,
)
from sidekick.trajectories.eventlog import EventLog  # noqa: E402
from sidekick.training.sft_data import (  # noqa: E402
    _action_from_payload,
    _history_from_events,
)
from fit_feature_verifier import (  # noqa: E402
    apply_standardize,
    auroc,
    brier,
    compute_nll,
    expected_calibration_error,
    fit_logistic,
    fit_temperature,
    predict_probs,
    rescale_probs,
    standardize_fit,
)

# Fit pool (class-balanced, ~50% positive) and excluded zero-success campaigns.
FIT_CAMPAIGNS = (
    "hj1b_planner_20260915",
    "hj2b_planner_train_20260916",
    "hj3_sft_b_exec_20260917",
    "hj3_sft_plan_20260917",
    "hj4_correction_train_20260917",
    "hj4b_fixed_k_dev_20260917",
)
EXCLUDED_ZERO_SUCCESS_PREFIXES = (
    "hj1a_exec3b_",
    "hj1a_exec8b_",
    "hj1c_fixed_k_",
    "hj1c_prompt_only_",
)
EXCLUDED_ALWAYS = ("hj6_branches_",)  # counterfactual branches, not episodes
SPLIT_SEED = 20260919
DEV_FRACTION = 0.20


def outcome_label(result_path: Path) -> tuple[int | None, str]:
    """Label from per-episode result.json: ``success`` bool, else goal_pass_rate.

    ``runs.jsonl`` is never consulted: older campaigns' runs.jsonl has no
    ``goal_pass_rate`` column, but every episode dir has a result.json.
    """
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return None, "unreadable_result_json"
    success = data.get("success")
    if isinstance(success, bool):
        return int(success), "success_bool"
    gpr = data.get("goal_pass_rate")
    if isinstance(gpr, (int, float)):
        return int(float(gpr) == 1.0), "goal_pass_rate_eq_1"
    return None, "no_outcome_field"


def _state_from_prefix(prefix: list, step: int) -> dict | None:
    """Rebuild the 7 trajectory_state keys from an event prefix.

    Same reconstruction fit_feature_verifier.trajectory_state_from_prefix
    uses (which mirrors loop.py:515-524 and the transcript assembly the loop
    uses when hydrating a prefix), plus ``p_ask=None``.
    """
    try:
        instruction, packet, _api_docs, history = _history_from_events(prefix)
        lines = [f"INSTRUCTION: {instruction}"]
        if packet is not None:
            lines.append(f"PLAN: {packet.model_dump_json()}")
        for turn in history:
            if turn.get("role") != "user":
                continue
            content = str(turn.get("content") or "")
            if content.startswith(("OBS:", "INTERVENTION:", "ANSWER:", "ASK_IGNORED")):
                lines.append(content)
        _tokens, n_asks, n_interventions, _n_planner = counters_from_events(prefix)
        last_obs = last_observation_from_events(prefix)
        last_action = None
        for ev in reversed(prefix):
            if ev.event_type == "action":
                parsed = _action_from_payload(ev.payload or {})
                last_action = None if parsed is None else parsed.model_dump()
                break
        return {
            "step": int(step),
            "transcript": "\n".join(lines),
            "last_action": last_action,
            "last_observation": last_obs.model_dump(),
            "n_asks": n_asks,
            "n_interventions": n_interventions,
            "p_ask": None,
        }
    except Exception:
        return None


def step_states_from_events(events: list, label: int) -> tuple[list[dict], int]:
    """One example per executed step: rebuild the loop's trajectory_state.

    A state exists at each step that has an executed action followed by its
    observation (the same state the verifier/serving path scores). ``p_ask``
    is None for historical episodes — per brief A7 this is correct and is NOT
    coerced to 0.0 (the frozen extractor does not read it: verifier.py:137-181
    has no p_ask term, so None is inert at serving too). Action payloads that
    DID carry a measured p_ask are counted for the report (n_p_ask_measured).
    Returns (rows, n_dropped).
    """
    rows: list[dict] = []
    dropped = 0
    n_p_ask_measured = 0
    pending_step: int | None = None
    for idx, ev in enumerate(events):
        if ev.event_type == "action":
            parsed = _action_from_payload(ev.payload or {})
            pending_step = ev.step if parsed is not None else None
            if pending_step is not None and isinstance(
                (ev.payload or {}).get("p_ask"), (int, float)
            ):
                n_p_ask_measured += 1
            continue
        if ev.event_type != "observation":
            pending_step = None
            continue
        if pending_step is None or ev.step != pending_step:
            pending_step = None
            continue
        state = _state_from_prefix(events[: idx + 1], ev.step)
        if state is None:
            dropped += 1
            pending_step = None
            continue
        row = dict(state)
        row["label"] = label
        rows.append(row)
        pending_step = None
    return rows, dropped, n_p_ask_measured




def value_xy(rows: list[dict]) -> tuple[list[list[float]], list[int]]:
    """Feature matrix in frozen spec order using the SHARED extractor."""
    columns = feature_spec()["columns"]
    X: list[list[float]] = []
    y: list[int] = []
    for row in rows:
        if "transcript" not in row:
            raise ValueError(
                "row has no transcript; never fit default features for a "
                "failed state reconstruction"
            )
        feats = _extractor_features(row)
        X.append([float(feats[c]) for c in columns])
        y.append(1 if row["label"] else 0)
    return X, y




def split_by_task(task_ids: list[str]) -> dict[str, str]:
    """Deterministic task-level split: sorted then shuffled by fixed seed."""
    ids = sorted(set(task_ids))
    random.Random(SPLIT_SEED).shuffle(ids)
    n_dev = int(round(len(ids) * DEV_FRACTION))
    dev = set(ids[:n_dev])
    return {t: ("dev" if t in dev else "train") for t in ids}


def _bisect_left_f(a: list[float], x: float) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        m = (lo + hi) // 2
        if a[m] < x:
            lo = m + 1
        else:
            hi = m
    return lo


def _bisect_right_f(a: list[float], x: float) -> int:
    lo, hi = 0, len(a)
    while lo < hi:
        m = (lo + hi) // 2
        if x < a[m]:
            hi = m
        else:
            lo = m + 1
    return lo


def bootstrap_auroc_ci(
    episodes: dict[str, tuple[list[float], list[int]]],
    n_boot: int = 10_000,
    seed: int = SPLIT_SEED,
) -> dict:
    """Task-level bootstrap CI for pooled-step AUROC (10,000 resamples).

    Episodes are the resampling unit (steps within an episode share a label,
    so a step-level resample would understate variance). Pair-count AUROC is
    precomputed per episode pair so each resample is O(#episodes).
    """
    names = sorted(episodes)
    pos_c = {e: sum(1 for t in episodes[e][1] if t) for e in names}
    neg_c = {e: len(episodes[e][1]) - pos_c[e] for e in names}
    wins: dict[tuple[str, str], float] = {}
    for a in names:
        sa, ya = episodes[a]
        pa = [s for s, t in zip(sa, ya) if t]
        if not pa:
            continue
        for b in names:
            sb, yb = episodes[b]
            nb = sorted(s for s, t in zip(sb, yb) if not t)
            if not nb:
                continue
            w = 0.0
            for s in pa:
                lo = _bisect_left_f(nb, s)
                hi = _bisect_right_f(nb, s)
                w += lo + 0.5 * (hi - lo)
            wins[(a, b)] = w

    def auroc_of(sample: list[str]) -> float:
        npos = sum(pos_c[e] for e in sample)
        nneg = sum(neg_c[e] for e in sample)
        if npos == 0 or nneg == 0:
            return float("nan")
        s = 0.0
        for a in sample:
            for b in sample:
                s += wins.get((a, b), 0.0)
        return s / (npos * nneg)

    rng = random.Random(seed)
    point = auroc_of(names)
    stats = sorted(
        v for v in (
            auroc_of(rng.choices(names, k=len(names))) for _ in range(n_boot)
        )
        if not math.isnan(v)
    )
    if not stats:
        return {"auroc": point, "ci_low": None, "ci_high": None, "n_boot": n_boot}
    return {
        "auroc": point,
        "ci_low": stats[int(0.025 * len(stats))],
        "ci_high": stats[min(len(stats) - 1, int(0.975 * len(stats)))],
        "n_boot": n_boot,
    }


def knn_ceiling(
    Xtr: list[list[float]], ytr: list[int], task_ids_tr: list[str],
    Xdev: list[list[float]], ydev: list[int], task_ids_dev: list[str],
    k: int = 5, max_refs: int = 3000,
) -> float | None:
    """Empirical attenuation-ceiling proxy [INFERRED]: k-NN over the SAME
    standardized features, never scoring a dev state against its own task.
    A heavier, higher-capacity function of exactly these features approximates
    the best AUROC any scorer of these features could reach — a proxy, not a
    mathematical bound; stated as such in the report."""
    idx = list(range(len(Xtr)))
    if len(idx) > max_refs:
        random.Random(SPLIT_SEED).shuffle(idx)
        idx = idx[:max_refs]
    refs = [(Xtr[i], ytr[i], task_ids_tr[i]) for i in idx if ytr[i] in (0, 1)]
    n_pos_ref = sum(1 for _, t, _ in refs if t == 1)
    n_neg_ref = len(refs) - n_pos_ref
    if n_pos_ref == 0 or n_neg_ref == 0:
        return None
    scores: list[float] = []
    labels: list[int] = []
    for x, t, yv in zip(Xdev, task_ids_dev, ydev):
        dists = []
        for xr, yr, tr in refs:
            if tr == t:
                continue
            d = sum((a - b) ** 2 for a, b in zip(x, xr))
            dists.append((d, yr))
        dists.sort(key=lambda p: p[0])
        top = dists[:k]
        if not top:
            continue
        scores.append(sum(tt for _, tt in top) / len(top))
        labels.append(yv)
    if not scores or len(set(labels)) < 2:
        return None
    return auroc(labels, scores)


def step_prior_baseline(train_rows: list[dict], dev_rows: list[dict]) -> float | None:
    """AUROC of the train per-step-index positive rate applied to dev — the
    attenuation floor reference: a feature-blind scorer knowing only step."""
    by_step: dict[int, list[int]] = {}
    for r in train_rows:
        by_step.setdefault(int(r["step"]), []).append(int(r["label"]))
    prior = {s: sum(v) / len(v) for s, v in by_step.items() if v}
    global_prior = sum(int(r["label"]) for r in train_rows) / len(train_rows)
    scores = [prior.get(int(r["step"]), global_prior) for r in dev_rows]
    labels = [int(r["label"]) for r in dev_rows]
    if not scores or len(set(labels)) < 2:
        return None
    return auroc(labels, scores)


def discover_episodes(results_root: Path) -> tuple[list[dict], dict]:
    """Enumerate episode dirs; count multi-run_start files per campaign.

    Read-only on /scratch results. Returns (episodes, counts_report).
    """
    episodes: list[dict] = []
    excluded = {}
    multi_run_start_files = 0
    multi_files_detail: dict[str, int] = {}
    for campaign in sorted(FIT_CAMPAIGNS):
        croot = results_root / campaign
        found = 0
        for events_path in sorted(croot.glob("*/*/*/events.jsonl")):
            found += 1
            ep_dir = events_path.parent
            result_path = ep_dir / "result.json"
            label, label_src = outcome_label(result_path)
            # Count run_start occurrences from file order (trap 1 applies to
            # every campaign, not just hj1a_exec8b).
            with open(events_path, "r", encoding="utf-8") as fh:
                n_rs = sum(1 for line in fh if '"run_start"' in line)
            if n_rs > 1:
                multi_run_start_files += 1
                multi_files_detail[campaign] = multi_files_detail.get(campaign, 0) + 1
            if label is None:
                continue
            episodes.append({
                "campaign": campaign,
                "events_path": str(events_path),
                "result_path": str(result_path),
                "task_id": ep_dir.name,
                "seed": ep_dir.parent.name,
                "system": ep_dir.parent.parent.name,
                "label": label,
                "label_source": label_src,
                "n_run_start": n_rs,
            })
        excluded[campaign] = {
            "episodes_found": found,
            "labelled": sum(1 for e in episodes if e["campaign"] == campaign),
        }
    # Excluded zero-success campaigns: counted and named, never silent.
    zero_success_report = {}
    for prefix in EXCLUDED_ZERO_SUCCESS_PREFIXES:
        dirs = [p for p in sorted(results_root.glob(f"{prefix}*"))
                if not p.name.endswith("_smoke") and p.is_dir()]
        for d in dirs:
            eps = sorted(d.glob("*/*/*/result.json"))
            n_pos = 0
            for rp in eps:
                lab, _ = outcome_label(rp)
                n_pos += int(bool(lab))
            # Trap 1 applies to every campaign: count multi-run_start files
            # here too (hj1a_exec8b_20260915 is the known offender).
            n_multi = 0
            for ev_path in d.glob("*/*/*/events.jsonl"):
                with open(ev_path, "r", encoding="utf-8") as fh:
                    n_rs = sum(1 for line in fh if '"run_start"' in line)
                if n_rs > 1:
                    n_multi += 1
            multi_files_detail[d.name] = n_multi
            multi_run_start_files += n_multi
            zero_success_report[d.name] = {
                "episodes": len(eps),
                "successes": n_pos,
                "multi_run_start_files": n_multi,
                "excluded_reason": (
                    "zero successes across all episodes; all-negative labels "
                    "carry no within-campaign signal for a P(success) head"
                ),
            }
    report = {
        "fit_campaigns": excluded,
        "multi_run_start_files": multi_run_start_files,
        "multi_run_start_by_campaign": multi_files_detail,
        "excluded_zero_success_campaigns": zero_success_report,
        "excluded_by_rule": {
            "hj6_branches_*": "counterfactual branches, not episodes (brief)",
        },
    }
    return episodes, report


def collect_examples(episodes: list[dict], split_map: dict[str, str]) -> tuple[list[dict], list[dict], dict]:
    """Load each episode once (in memory), split last-attempt events, emit rows."""
    train_rows: list[dict] = []
    dev_rows: list[dict] = []
    drops = {
        "episodes_missing_result": 0,
        "episodes_empty_after_last_run_start": 0,
        "episodes_load_error": 0,
        "steps_dropped_reconstruction": 0,
        "episodes_no_steps": 0,
    }
    per_campaign: dict[str, dict] = {}
    for ep in episodes:
        try:
            events = _events_of_last_attempt(Path(ep["events_path"]))
        except Exception:
            drops["episodes_load_error"] += 1
            continue
        if not events:
            drops["episodes_empty_after_last_run_start"] += 1
            continue
        rows, n_drop, n_measured = step_states_from_events(events, ep["label"])
        drops["steps_dropped_reconstruction"] += n_drop
        drops["n_p_ask_measured"] = drops.get("n_p_ask_measured", 0) + n_measured
        if not rows:
            drops["episodes_no_steps"] += 1
            continue
        split = split_map[ep["task_id"]]
        target = train_rows if split == "train" else dev_rows
        for r in rows:
            r["task_id"] = ep["task_id"]
            r["campaign"] = ep["campaign"]
        target.extend(rows)
        c = per_campaign.setdefault(
            ep["campaign"], {"episodes": 0, "steps": 0, "positives": 0}
        )
        c["episodes"] += 1
        c["steps"] += len(rows)
        c["positives"] += sum(int(r["label"]) for r in rows)
    counts = {
        "episodes_read": len(episodes),
        **drops,
        "per_campaign": per_campaign,
        "n_train_steps": len(train_rows),
        "n_dev_steps": len(dev_rows),
        "n_train_positive": sum(int(r["label"]) for r in train_rows),
        "n_dev_positive": sum(int(r["label"]) for r in dev_rows),
    }
    return train_rows, dev_rows, counts


def fit_all_value(
    train_rows: list[dict], dev_rows: list[dict], *, l2: float = 1.0
) -> tuple[FeatureVerifier, dict, list[float]]:
    """LR on train steps, temperature-scale on dev steps. Same shape, and the
    same hard-won invariants, as fit_feature_verifier.fit_all (commit 957ec7a).
    Returns (verifier, report, dev_probs)."""
    report: dict = {"l2": l2}
    Xtr_raw, ytr = value_xy(train_rows)
    Xdev_raw, ydev = value_xy(dev_rows)
    if not Xtr_raw or len(set(ytr)) < 2:
        raise ValueError("train split needs rows of both classes after filtering")
    if not Xdev_raw or len(set(ydev)) < 2:
        raise ValueError(
            "dev split needs rows of both classes after filtering; refusing "
            "silent temperature scaling"
        )
    means, stds = standardize_fit(Xtr_raw)
    Xtr = apply_standardize(Xtr_raw, means, stds)
    Xdev = apply_standardize(Xdev_raw, means, stds)
    params = fit_logistic(Xtr, ytr, l2=l2)
    train_probs = predict_probs(params, Xtr)
    dev_probs_raw = predict_probs(params, Xdev)
    temperature = fit_temperature(dev_probs_raw, ydev)
    dev_probs = rescale_probs(dev_probs_raw, temperature)

    # Invariant 1: calibration must never increase dev NLL.
    nll_before = compute_nll(ydev, dev_probs_raw)
    nll_after = compute_nll(ydev, dev_probs)
    assert nll_after <= nll_before + 1e-12, (
        f"temperature scaling increased dev NLL: {nll_before} -> {nll_after}"
    )
    # Invariant 2: monotone scaling must leave AUROC bit-identical.
    auroc_raw = auroc(ydev, dev_probs_raw)
    auroc_scaled = auroc(ydev, dev_probs)
    assert auroc_raw == auroc_scaled, (
        f"AUROC changed under temperature scaling: {auroc_raw} -> {auroc_scaled}"
    )

    columns = feature_spec()["columns"]
    weights = {c: params[i] / stds[i] for i, c in enumerate(columns)}
    intercept = params[-1] - sum(
        params[i] * means[i] / stds[i] for i in range(len(columns))
    )
    verifier = FeatureVerifier(
        weights=weights, intercept=intercept, temperature=temperature,
        spec=feature_spec(),
    )

    def block(rows, probs, y):
        return {
            "n": len(rows),
            "positive_rate": (sum(y) / len(y)) if y else None,
            "brier": brier(y, probs) if y else None,
            "ece": expected_calibration_error(y, probs) if y else None,
            "nll": compute_nll(y, probs) if y else None,
            "auroc": auroc(y, probs) if y else None,
        }

    report["train"] = block(train_rows, train_probs, ytr)
    report["dev"] = block(dev_rows, dev_probs, ydev)
    report["dev_nll_before"] = nll_before
    report["dev_nll_after"] = nll_after
    report["dev"]["auroc_before_temperature"] = auroc_raw
    report["temperature"] = temperature
    report["feature_spec_version"] = FEATURE_SPEC_VERSION
    report["attenuation_note"] = (
        "labels are episode outcomes back-propagated to steps; early steps are "
        "only weakly determined by the outcome, so AUROC is judged against "
        "ceiling proxies (attenuation_ceiling_knn_proxy) and a feature-blind "
        "step-prior floor (attenuation_floor_step_prior_auroc), not 0.50 alone"
    )
    return verifier, report, dev_probs


def run_fit(results_root: str | Path, out_dir: str | Path, *, l2: float = 1.0,
            date: str | None = None, n_boot: int = 10_000) -> dict:
    results = Path(results_root)
    episodes, discovery = discover_episodes(results)
    task_ids = [e["task_id"] for e in episodes]
    if not task_ids:
        raise ValueError("no episodes discovered under " + str(results))
    split_map = split_by_task(task_ids)
    n_split = {
        "tasks_total": len(split_map),
        "tasks_train": sum(1 for v in split_map.values() if v == "train"),
        "tasks_dev": sum(1 for v in split_map.values() if v == "dev"),
    }
    train_rows, dev_rows, counts = collect_examples(episodes, split_map)
    if not train_rows or not dev_rows:
        raise ValueError("empty train or dev split after step extraction")

    verifier, fit_report, dev_probs = fit_all_value(train_rows, dev_rows, l2=l2)

    Xtr_raw, ytr = value_xy(train_rows)
    Xdev_raw, ydev = value_xy(dev_rows)
    means, stds = standardize_fit(Xtr_raw)
    task_ids_tr = [r["task_id"] for r in train_rows]
    task_ids_dev = [r["task_id"] for r in dev_rows]
    ceiling = knn_ceiling(
        apply_standardize(Xtr_raw, means, stds), ytr, task_ids_tr,
        apply_standardize(Xdev_raw, means, stds), ydev, task_ids_dev,
    )
    prior = step_prior_baseline(train_rows, dev_rows)

    # Task-level bootstrap CI over dev episodes (episodes are the unit).
    ep_scores: dict[str, tuple[list[float], list[int]]] = {}
    for r, p in zip(dev_rows, dev_probs):
        sc, lab = ep_scores.setdefault(r["task_id"], ([], []))
        sc.append(float(p))
        lab.append(int(r["label"]))
    boot = bootstrap_auroc_ci(ep_scores, n_boot=n_boot)

    report = {
        "artifact": "value_fn (FeatureVerifier head over feature_lr_v1 spec)",
        "discovery": discovery,
        "split": {
            **n_split,
            "rule": "by task_id, sorted then deterministically shuffled with "
                    f"random.Random({SPLIT_SEED}); last {int(DEV_FRACTION*100)}% to dev",
        },
        "step_counts": counts,
        "outcome_field": "result.json success (bool); goal_pass_rate fallback "
                         "applies only if success is absent; runs.jsonl never "
                         "used (older campaigns lack goal_pass_rate there)",
        **fit_report,
        "auroc_bootstrap_task_level": boot,
        "attenuation_ceiling_knn_proxy": ceiling,
        "attenuation_floor_step_prior_auroc": prior,
        "fit_invariants": {
            "nll_never_increased": fit_report["dev_nll_after"]
            <= fit_report["dev_nll_before"] + 1e-12,
            "auroc_bit_identical": True,
            "nlls_written_to_artifact": True,
        },
    }
    stamp = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = Path(out_dir) / f"value_fn_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    verifier.save(dest / "weights.json")
    (dest / "feature_spec.json").write_text(
        json.dumps(verifier.spec, indent=2), encoding="utf-8"
    )
    (dest / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"artifact_dir": str(dest), "report": report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/setup/fit_value_function.py",
        description="Fit + temperature-scale the A7 value function (CPU-only).",
    )
    parser.add_argument(
        "--results-root", default="/scratch/n12194778/sidekick/results",
        help="campaign results root (READ-ONLY)",
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "verifiers"))
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--date", default=None, help="artifact dir stamp (YYYYMMDD)")
    parser.add_argument("--n-boot", type=int, default=10_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_fit(
        args.results_root, args.out, l2=args.l2, date=args.date, n_boot=args.n_boot
    )
    scratch = REPO_ROOT / "campaign" / "workers" / "scratch_A7"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "fit_report.json").write_text(
        json.dumps(result["report"], indent=2), encoding="utf-8"
    )
    print(json.dumps(result["report"], indent=2))
    print(f"artifact: {result['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

