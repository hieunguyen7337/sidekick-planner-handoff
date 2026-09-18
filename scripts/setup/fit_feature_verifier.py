"""Fit and temperature-scale the FeatureVerifier (feature_lr_v1). CPU-only.

Run inside a PBS job (`hpc -c 4 -m 16gb -t 00:20:00 python scripts/setup/
fit_feature_verifier.py ...`), never on the login node. No numpy/sklearn
dependency: pure-stdlib logistic regression via batch gradient descent with
early stopping, and dev-set temperature scaling by 1-D golden-section search.

Input: two J6 ``branches.jsonl`` files (train and dev are separate explicit
inputs — real rows have no ``split`` key) plus the two campaign roots whose
``events.jsonl`` files reconstruct ``trajectory_state``. Label column ``needed``
(bool/int). Rows with ``label_status == "incomplete"`` are dropped, never
imputed. Rows with boolean ``ambiguous`` true are excluded from the fit and
reported separately. Fit on the train split; temperature-scale on dev; never
fit on dev.

Do not point this at live J6 train output until that job has finished writing
``branches.jsonl``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

import branch_counterfactual as _bc  # noqa: E402
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
from sidekick.training.sft_data import (  # noqa: E402
    _action_from_payload,
    _history_from_events,
)

ALLOWED_LABEL_STATUS = frozenset({"complete", "incomplete"})
TRAJECTORY_STATE_KEYS = (
    "step",
    "transcript",
    "last_action",
    "last_observation",
    "n_asks",
    "n_interventions",
)


def read_rows(path: str | Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "1", "yes"):
            return True
        if low in ("false", "0", "no"):
            return False
    return None


def episode_events_path(campaign_root: str | Path, seed: int, task_id: str) -> Path:
    """``{campaign}/{SYSTEM_NAME}/{seed}/{task_id}/events.jsonl`` as J6 uses."""
    return Path(campaign_root) / _bc.SYSTEM_NAME / str(seed) / str(task_id) / "events.jsonl"


def trajectory_state_from_prefix(events: list, i: int, expected_step: int) -> dict | None:
    """Rebuild loop.trajectory_state at intervention ``i`` from the prefix.

    Uses J6's ``prefix_events_before_intervention`` / ``_history_from_events``
    and the same transcript assembly the loop uses when hydrating a prefix
    (loop.py:540-548), plus the live counters and last observation helpers.
    A step mismatch or out-of-range ``i`` is a failed join, not a default state.
    """
    try:
        points = _bc.enumerate_intervention_points(events)
        if i < 0 or i >= len(points):
            return None
        if int(points[i]["step"]) != int(expected_step):
            return None
        prefix = _bc.prefix_events_before_intervention(events, i)
    except (IndexError, TypeError, ValueError):
        return None
    instruction, packet, _api_docs, history = _history_from_events(prefix)
    lines = [f"INSTRUCTION: {instruction}"]
    if packet is not None:
        lines.append(f"PLAN: {packet.model_dump_json()}")
    for turn in history:
        content = str(turn.get("content") or "")
        if turn.get("role") != "user":
            continue
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
        "step": int(expected_step),
        "transcript": "\n".join(lines),
        "last_action": last_action,
        "last_observation": last_obs.model_dump(),
        "n_asks": n_asks,
        "n_interventions": n_interventions,
    }


def join_episode_features(
    rows: list[dict],
    campaign_root: str | Path | None,
    *,
    split: str | None = None,
) -> tuple[list[dict], dict]:
    """Attach trajectory_state from campaign events. Failed joins are dropped.

    ``split`` is attached from which file the rows came from, never read off
    a field that real J6 rows do not have. When ``campaign_root`` is None
    (synthetic tests that already carry trajectory_state), no join is attempted.
    """
    joined: list[dict] = []
    n_dropped = 0
    cache: dict[tuple[int, str], list | None] = {}
    root = None if campaign_root is None else Path(campaign_root)
    for row in rows:
        out = dict(row)
        if split is not None:
            out["split"] = split
        if root is None:
            joined.append(out)
            continue
        try:
            seed = int(row["seed"])
            task_id = str(row["task_id"])
            i = int(row["i"])
            step = int(row["step"])
        except (KeyError, TypeError, ValueError):
            n_dropped += 1
            continue
        key = (seed, task_id)
        if key not in cache:
            path = episode_events_path(root, seed, task_id)
            if not path.is_file():
                cache[key] = None
            else:
                events = _events_of_last_attempt(path)
                cache[key] = events or None
        events = cache[key]
        if events is None:
            n_dropped += 1
            continue
        state = trajectory_state_from_prefix(events, i, step)
        if state is None:
            n_dropped += 1
            continue
        out.update(state)
        joined.append(out)
    report = {
        "n_rows_read": len(rows),
        "n_join_dropped": n_dropped,
        "n_joined": len(joined),
    }
    return joined, report


def build_xy(rows: list[dict]) -> tuple[list[list[float]], list[int]]:
    """Feature matrix in frozen spec order and integer labels.

    Requires a reconstructed ``transcript``. Fitting default features for a
    row that never joined to an episode is the defect this guards against.
    """
    columns = feature_spec()["columns"]
    X: list[list[float]] = []
    y: list[int] = []
    for row in rows:
        if "transcript" not in row:
            raise ValueError(
                "label row has no transcript; reconstruct trajectory_state from "
                "campaign events before build_xy (never fit default features "
                "for a failed join)"
            )
        feats = _extractor_features(row)
        X.append([float(feats[c]) for c in columns])
        y.append(1 if row["needed"] else 0)
    return X, y


def prepare_dataset(rows: list[dict]) -> tuple[list[dict], dict]:
    """Filter by label_status and the boolean ambiguous column.

    ``label_status`` is only ever ``complete`` or ``incomplete`` on real rows;
    ``ambiguous`` is a separate boolean. Incomplete is dropped, never imputed.
    Unexpected status values raise rather than falling through.
    """
    kept: list[dict] = []
    counts = {"incomplete_dropped": 0, "ambiguous_excluded": 0, "missing_label_dropped": 0}
    for row in rows:
        status = str(row.get("label_status") or "").strip().lower()
        if status not in ALLOWED_LABEL_STATUS:
            raise ValueError(
                f"unexpected label_status={row.get('label_status')!r}; "
                f"expected one of {sorted(ALLOWED_LABEL_STATUS)}"
            )
        needed = _as_bool(row.get("needed"))
        if status == "incomplete" or needed is None:
            counts["incomplete_dropped" if status == "incomplete" else "missing_label_dropped"] += 1
            continue
        if _as_bool(row.get("ambiguous")) is True:
            counts["ambiguous_excluded"] += 1
            continue
        kept.append(row)
    report = {
        "n_rows_read": len(rows),
        "n_kept_for_fit": len(kept),
        **counts,
        "n_positive_kept": sum(1 for r in kept if _as_bool(r.get("needed"))),
        "n_negative_kept": sum(1 for r in kept if not _as_bool(r.get("needed"))),
    }
    return kept, report


def standardize_fit(X: list[list[float]]) -> tuple[list[float], list[float]]:
    n = len(X)
    d = len(X[0]) if n else 0
    means = [sum(row[j] for row in X) / n for j in range(d)] if n else [0.0] * d
    stds: list[float] = []
    for j in range(d):
        var = sum((row[j] - means[j]) ** 2 for row in X) / n if n else 0.0
        stds.append(math.sqrt(var) if var > 1e-12 else 1.0)
    return means, stds


def apply_standardize(
    X: list[list[float]], means: list[float], stds: list[float]
) -> list[list[float]]:
    return [[(row[j] - means[j]) / stds[j] for j in range(len(means))] for row in X]


def fit_logistic(
    X: list[list[float]],
    y: list[int],
    *,
    l2: float = 1.0,
    lr: float = 0.1,
    epochs: int = 3000,
) -> list[float]:
    """Batch-GD logistic regression with early stopping; returns [w..., b]."""
    n = len(X)
    d = len(X[0]) if n else 0
    params = [0.0] * (d + 1)
    if n == 0:
        return params
    prev_ll = -math.inf
    for _ in range(epochs):
        grad = [0.0] * (d + 1)
        ll = 0.0
        for i in range(n):
            z = params[d] + sum(params[j] * X[i][j] for j in range(d))
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            err = p - y[i]
            for j in range(d):
                grad[j] += err * X[i][j]
            grad[d] += err
            ll += math.log(max(p, 1e-12)) if y[i] else math.log(max(1.0 - p, 1e-12))
        for j in range(d):
            grad[j] = grad[j] / n + l2 * params[j]
        grad[d] /= n
        step = lr / (1.0 + 0.002 * max(ll, 0.0))  # mild decay on improvement
        for j in range(d + 1):
            params[j] -= step * grad[j]
        if abs(ll - prev_ll) < 1e-7:
            break
        prev_ll = ll
    return params


def predict_probs(params: list[float], X: list[list[float]]) -> list[float]:
    d = len(params) - 1
    out = []
    for row in X:
        z = params[d] + sum(params[j] * row[j] for j in range(d))
        out.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))))
    return out


def compute_nll(y_true: list[int], probs: list[float]) -> float:
    """Mean binary negative log-likelihood (cross-entropy in nats)."""
    if not y_true or len(y_true) != len(probs):
        return 0.0
    tot = 0.0
    for yi, p in zip(y_true, probs):
        p = min(max(p, 1e-12), 1.0 - 1e-12)
        tot -= yi * math.log(p) + (1 - yi) * math.log(1.0 - p)
    return tot / len(y_true)


nll = compute_nll


def fit_temperature(
    probs: list[float],
    y: list[int],
    min_t: float = 0.05,
    max_t: float = 20.0,
    iterations: int = 80,
) -> float:
    """Temperature T minimising dev NLL of p^(1/T); 1-D golden-section search.

    Searches over log(T) in [log(min_t), log(max_t)]. Guards against making
    calibration worse than uncalibrated (T=1.0) by returning 1.0 if the
    optimum does not strictly improve dev NLL.
    """
    if not probs or not y or len(probs) != len(y) or len(set(y)) < 2:
        return 1.0

    logits = [
        math.log(min(max(p, 1e-12), 1.0 - 1e-12) / (1.0 - min(max(p, 1e-12), 1.0 - 1e-12)))
        for p in probs
    ]

    def _nll_at_t(t: float) -> float:
        tot = 0.0
        for z, yi in zip(logits, y):
            scaled_z = max(-30.0, min(30.0, z / t))
            q = 1.0 / (1.0 + math.exp(-scaled_z))
            q = min(max(q, 1e-12), 1.0 - 1e-12)
            tot -= yi * math.log(q) + (1 - yi) * math.log(1.0 - q)
        return tot / len(y)

    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0  # ~0.618033988749895
    a = math.log(min_t)
    b = math.log(max_t)
    c = b - inv_phi * (b - a)
    d = a + inv_phi * (b - a)
    fc = _nll_at_t(math.exp(c))
    fd = _nll_at_t(math.exp(d))

    for _ in range(iterations):
        if fc < fd:
            b = d
            d = c
            fd = fc
            c = b - inv_phi * (b - a)
            fc = _nll_at_t(math.exp(c))
        else:
            a = c
            c = d
            fc = fd
            d = a + inv_phi * (b - a)
            fd = _nll_at_t(math.exp(d))

    opt_t = math.exp((a + b) / 2.0)
    nll_opt = _nll_at_t(opt_t)
    nll_1 = _nll_at_t(1.0)

    # Invariant: calibration may never make things worse than T = 1.0
    if nll_opt >= nll_1:
        return 1.0
    return float(opt_t)


def auroc(y_true: list[int], scores: list[float]) -> float:
    """Tie-aware rank-statistic AUROC; 0.5 when only one class is present."""
    pairs = sorted(zip(scores, y_true), key=lambda t: t[0])
    pos = sum(y_true)
    neg = len(y_true) - pos
    if pos == 0 or neg == 0:
        return 0.5
    rank_sum = 0.0
    i = 0
    n = len(pairs)
    while i < n:
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            if pairs[k][1]:
                rank_sum += avg_rank
        i = j
    return (rank_sum - pos * (pos + 1) / 2.0) / (pos * neg)


def brier(y_true: list[int], probs: list[float]) -> float:
    if not y_true:
        return 0.0
    return sum((p - t) ** 2 for p, t in zip(probs, y_true)) / len(y_true)


def expected_calibration_error(y_true: list[int], probs: list[float], bins: int = 10) -> float:
    if not y_true:
        return 0.0
    ece = 0.0
    n = len(y_true)
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [
            (p, t)
            for p, t in zip(probs, y_true)
            if lo <= p < hi or (b == bins - 1 and p == 1.0)
        ]
        if not bucket:
            continue
        conf = sum(p for p, _ in bucket) / len(bucket)
        acc = sum(t for _, t in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(acc - conf)
    return ece


def is_tick_state(row: dict) -> bool:
    """J4 reviewer fired at steps 5, 10, 15, ... — timer-tick states."""
    try:
        return int(row.get("step", 0)) % 5 == 0
    except (TypeError, ValueError):
        return False


def rescale_probs(probs: list[float], temperature: float) -> list[float]:
    """Scale probabilities by temperature: sigmoid(logit(p) / T)."""
    out = []
    for p in probs:
        p = min(max(p, 1e-12), 1.0 - 1e-12)
        z = math.log(p / (1.0 - p)) / temperature
        out.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))))
    return out


def fit_all(
    train_rows: list[dict],
    dev_rows: list[dict],
    *,
    l2: float = 1.0,
) -> tuple[FeatureVerifier, dict]:
    """Fit LR on train, temperature-scale on dev; return artifact + metrics."""
    report: dict = {"l2": l2}
    Xtr_raw, ytr = build_xy(train_rows)
    Xdev_raw, ydev = build_xy(dev_rows)
    if not Xtr_raw or len(set(ytr)) < 2:
        raise ValueError("train split needs rows of both classes after filtering")
    means, stds = standardize_fit(Xtr_raw)
    Xtr = apply_standardize(Xtr_raw, means, stds)
    Xdev = apply_standardize(Xdev_raw, means, stds)
    params = fit_logistic(Xtr, ytr, l2=l2)
    train_probs = predict_probs(params, Xtr)
    dev_probs_raw = predict_probs(params, Xdev)
    temperature = fit_temperature(dev_probs_raw, ydev) if ydev else 1.0
    dev_probs = rescale_probs(dev_probs_raw, temperature)

    columns = feature_spec()["columns"]
    weights = {c: params[i] / stds[i] for i, c in enumerate(columns)}
    intercept = params[-1] - sum(params[i] * means[i] / stds[i] for i in range(len(columns)))
    verifier = FeatureVerifier(
        weights=weights, intercept=intercept, temperature=temperature, spec=feature_spec()
    )

    def block(rows: list[dict], probs: list[float], y: list[int]) -> dict:
        idx_all = list(range(len(rows)))
        tick_idx = [i for i in idx_all if is_tick_state(rows[i])]
        out = {
            "n": len(rows),
            "n_tick_states": len(tick_idx),
            "positive_rate": (sum(y) / len(y)) if y else None,
            "brier": brier(y, probs) if y else None,
            "ece": expected_calibration_error(y, probs) if y else None,
            "nll": compute_nll(y, probs) if y else None,
        }
        if y:
            out["auroc_all_states"] = auroc(y, probs)
            y_tick = [y[i] for i in tick_idx]
            p_tick = [probs[i] for i in tick_idx]
            out["auroc_tick_states"] = auroc(y_tick, p_tick) if y_tick else None
        return out

    report["train"] = block(train_rows, train_probs, ytr)
    report["dev"] = block(dev_rows, dev_probs, ydev) if dev_rows else {"n": 0}
    if dev_rows and ydev:
        report["dev"]["nll_before"] = compute_nll(ydev, dev_probs_raw)
        report["dev"]["nll_after"] = compute_nll(ydev, dev_probs)
    report["dev_nll_before"] = compute_nll(ydev, dev_probs_raw) if ydev else None
    report["dev_nll_after"] = compute_nll(ydev, dev_probs) if ydev else None
    report["temperature"] = temperature
    report["feature_spec_version"] = FEATURE_SPEC_VERSION
    report["threats_to_validity"] = [
        "train/serve distribution shift: J4 labels exist only at timer-tick "
        "states (steps 5, 10, 15, ...) but the router and the sidekick gate "
        "score every step; auroc_tick_states and auroc_all_states are reported "
        "separately to expose this.",
        "labels are noisy: measured 2026-09-17 on partial J6 data, split-half "
        "reliability of the underlying effect is 0.17-0.20 per replicate, so "
        "the two-replicate mean the labels are cut from has reliability ~0.29. "
        "An AUROC near 0.5 is a plausible and reportable outcome, not "
        "necessarily a bug. Do not tune against dev metrics.",
        "ambiguous label rows (~69% of points on partial data) are excluded "
        "from fitting and reported separately; treating them as negatives "
        "would fit mostly noise.",
        "temperature is fit on dev: dev calibration metrics (brier, ece, nll) "
        "are evaluated on the same dev split used for temperature fitting, so "
        "reported dev calibration is in-sample and optimistic.",
    ]
    return verifier, report


def run_fit(
    train_branches: str | Path,
    dev_branches: str | Path,
    out_dir: str | Path,
    *,
    train_campaign: str | Path | None = None,
    dev_campaign: str | Path | None = None,
    l2: float = 1.0,
    date: str | None = None,
) -> dict:
    """Fit from two label files. Split is which file a row came from."""
    train_raw = read_rows(train_branches)
    dev_raw = read_rows(dev_branches)
    train_joined, train_join = join_episode_features(
        train_raw, train_campaign, split="train"
    )
    dev_joined, dev_join = join_episode_features(dev_raw, dev_campaign, split="dev")
    if not dev_joined:
        raise ValueError(
            "dev split is empty after partitioning; refusing to temperature-scale "
            "on an empty set (real branches.jsonl rows have no split key)"
        )
    train_rows, train_report = prepare_dataset(train_joined)
    dev_rows, dev_report = prepare_dataset(dev_joined)
    if not train_rows:
        raise ValueError("train split is empty after filtering")
    if not dev_rows:
        raise ValueError(
            "dev split is empty after filtering; refusing silent temperature scaling"
        )
    verifier, report = fit_all(train_rows, dev_rows, l2=l2)
    report["train_filter"] = train_report
    report["dev_filter"] = dev_report
    report["train_join"] = train_join
    report["dev_join"] = dev_join
    stamp = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    dest = Path(out_dir) / f"feature_lr_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    verifier.save(dest / "weights.json")
    (dest / "feature_spec.json").write_text(
        json.dumps(verifier.spec, indent=2), encoding="utf-8"
    )
    (dest / "metrics.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return {"artifact_dir": str(dest), "report": report}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/setup/fit_feature_verifier.py",
        description="Fit + temperature-scale the feature_lr verifier (CPU-only).",
    )
    parser.add_argument(
        "--train-branches",
        required=True,
        help="J6 train branches.jsonl (split is this file, not a row field)",
    )
    parser.add_argument(
        "--dev-branches",
        required=True,
        help="J6 dev branches.jsonl (split is this file, not a row field)",
    )
    parser.add_argument(
        "--train-campaign",
        required=True,
        help="Campaign root with fixed_k/{seed}/{task_id}/events.jsonl for train",
    )
    parser.add_argument(
        "--dev-campaign",
        required=True,
        help="Campaign root with fixed_k/{seed}/{task_id}/events.jsonl for dev",
    )
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "verifiers"))
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--date", default=None, help="artifact dir stamp (YYYYMMDD)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_fit(
        args.train_branches,
        args.dev_branches,
        args.out,
        train_campaign=args.train_campaign,
        dev_campaign=args.dev_campaign,
        l2=args.l2,
        date=args.date,
    )
    print(json.dumps(result["report"], indent=2))
    print(f"artifact: {result['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
