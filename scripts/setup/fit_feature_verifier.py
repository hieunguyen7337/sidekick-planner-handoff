"""Fit and temperature-scale the FeatureVerifier (feature_lr_v1). CPU-only.

Run inside a PBS job (`hpc -c 4 -m 16gb -t 00:20:00 python scripts/setup/
fit_feature_verifier.py ...`), never on the login node. No numpy/sklearn
dependency: pure-stdlib logistic regression via batch gradient descent with
early stopping, and dev-set temperature scaling by 1-D Newton steps.

Input: J6 branches.jsonl — one row per intervention point, label column
`needed` (bool/int). Rows with `label_status == "incomplete"` are dropped,
never imputed. Rows with `label_status == "ambiguous"` are excluded from the
fit and reported separately. Fit on the train split; temperature-scale on dev;
never fit on dev.

CAUTION: real branches.jsonl does not exist yet (J6 running). Test against
synthetic rows only; do not point this at live J6 output.
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

from sidekick.agents.verifier import (  # noqa: E402
    FEATURE_SPEC_VERSION,
    FeatureVerifier,
    _extractor_features,
    feature_spec,
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


def build_xy(rows: list[dict]) -> tuple[list[list[float]], list[int]]:
    """Feature matrix in frozen spec order and integer labels."""
    columns = feature_spec()["columns"]
    X: list[list[float]] = []
    y: list[int] = []
    for row in rows:
        feats = _extractor_features(row)
        X.append([float(feats[c]) for c in columns])
        y.append(1 if row["needed"] else 0)
    return X, y


def prepare_dataset(rows: list[dict]) -> tuple[list[dict], dict]:
    """Split rows by label_status; incomplete is dropped, never imputed."""
    kept: list[dict] = []
    counts = {"incomplete_dropped": 0, "ambiguous_excluded": 0, "missing_label_dropped": 0}
    for row in rows:
        status = str(row.get("label_status") or "").strip().lower()
        needed = _as_bool(row.get("needed"))
        if status == "incomplete" or needed is None:
            counts["incomplete_dropped" if status == "incomplete" else "missing_label_dropped"] += 1
            continue
        if status == "ambiguous":
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


def fit_temperature(probs: list[float], y: list[int], iterations: int = 100) -> float:
    """Temperature T minimising dev NLL of p^(1/T); 1-D Newton, T clamped."""
    logit = [math.log(max(p, 1e-12) / max(1.0 - p, 1e-12)) for p in probs]
    T = 1.0
    for _ in range(iterations):
        num = 0.0
        den = 1e-12
        for zi, yi in zip(logit, y):
            z = zi / T
            p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
            num += (1.0 / T - (yi - p)) * z * z / (T * T)
            den += z * z / (T * T)
        if den <= 1e-12:
            break
        new_T = T - num / den
        if not math.isfinite(new_T) or new_T <= 0:
            break
        done = abs(new_T - T) < 1e-8
        T = max(new_T, 0.05)
        if done:
            break
    return float(T)

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

    def rescale(probs: list[float]) -> list[float]:
        out = []
        for p in probs:
            p = min(max(p, 1e-12), 1.0 - 1e-12)
            z = math.log(p / (1.0 - p)) / temperature
            out.append(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z)))))
        return out

    dev_probs = rescale(dev_probs_raw)

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
        }
        if y:
            out["auroc_all_states"] = auroc(y, probs)
            y_tick = [y[i] for i in tick_idx]
            p_tick = [probs[i] for i in tick_idx]
            out["auroc_tick_states"] = auroc(y_tick, p_tick) if y_tick else None
        return out

    report["train"] = block(train_rows, train_probs, ytr)
    report["dev"] = block(dev_rows, dev_probs, ydev) if dev_rows else {"n": 0}
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
    ]
    return verifier, report


def run_fit(
    branches_path: str | Path,
    out_dir: str | Path,
    *,
    l2: float = 1.0,
    date: str | None = None,
) -> dict:
    rows = read_rows(branches_path)
    train_rows, train_report = prepare_dataset(
        [r for r in rows if str(r.get("split") or "train") == "train"]
    )
    dev_rows, dev_report = prepare_dataset(
        [r for r in rows if str(r.get("split") or "train") == "dev"]
    )
    verifier, report = fit_all(train_rows, dev_rows, l2=l2)
    report["train_filter"] = train_report
    report["dev_filter"] = dev_report
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
    parser.add_argument("--branches", required=True, help="J6 branches.jsonl path")
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "verifiers"))
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--date", default=None, help="artifact dir stamp (YYYYMMDD)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_fit(args.branches, args.out, l2=args.l2, date=args.date)
    print(json.dumps(result["report"], indent=2))
    print(f"artifact: {result['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
