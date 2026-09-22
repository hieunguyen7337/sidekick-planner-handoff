"""Difference-in-differences with a cluster bootstrap interval.

Why this exists
---------------
Two of the paper's readings are interaction claims that were argued from *which of two
contrasts happened to exclude zero*. That is not a test of an interaction: two contrasts
can differ in significance while the difference between them is indistinguishable from
zero. ``paper/preprint_dev_20260923.md`` says so about itself, in Limitation 5:

    "No resolved gap on the tailored receiver" is a weaker statement than "a significantly
    smaller gap than on the untailored receiver", and we do not make the stronger one.

This module computes the estimand those claims actually need, so the paper can either make
the stronger statement or bound it honestly.

The two interactions
--------------------
DiD-1, narration x receiver, at each depth m separately::

    (narrated_tailored - executed_tailored) - (narrated_untailored - executed_untailored)

DiD-2, tailoring x depth, on each planner sample separately::

    (tailored_m11 - tailored_m9) - (untailored_m11 - untailored_m9)

Design note that matters for correctness
----------------------------------------
All four arms of a DiD are replays over the SAME (task_id, seed) episodes, so the DiD is
itself a per-episode quantity: form it inside the episode first, then average. The
bootstrap then resamples whole clusters of that single derived series.

Do NOT bootstrap the two gaps separately and subtract their intervals. That discards the
episode-level pairing between the two gaps and yields an interval that is too wide, which
would make a real interaction look unresolved. Constructing the DiD per episode keeps every
level of pairing the design bought.

Populations and crashes follow the project convention used everywhere else: population
"all", a crashed episode scores 0 -- where "crashed" means ``error_type == "crash"`` and
only that, matching every arm mean already published (see ``episode_value``) -- and an
episode missing from any of the four arms is dropped from that DiD and counted.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.setup.hj1_gate import load_arm, scenario_of  # noqa: E402

# Kept in sync with j8_frontier.CRASH_ERROR_TYPE (:110) by test_j14_did, which asserts the
# two are equal rather than trusting this copy. Importing j8_frontier here would drag in
# its whole module-load side effects for one string.
CRASH_ERROR_TYPE = "crash"

# The registered settings for this analysis. The seed is deliberately NOT hj1_gate.SEED:
# these reports were produced on 2026-09-24 and carry their own seed so a rerun is
# reproducible independently of whatever the gate's constant happens to be.
BOOTSTRAP = 10_000
DID_SEED = 20260924
FIELDS = ("goal_pass_rate", "tgc")


def episode_value(row: dict[str, Any], field: str) -> float:
    """Population 'all': a crashed episode contributes 0, not a missing value.

    ⚠ "Crashed" here means ``error_type == "crash"`` and nothing else, matching
    ``j8_frontier.is_crashed`` (:398, ``CRASH_ERROR_TYPE = "crash"``) and therefore
    ``mean_quality(crash_as_zero=True)``, which is what produced every arm mean already in
    the ledger and the paper.

    This is deliberately NARROWER than ``campaign_summarize.BROKEN``
    (``{api_error, timeout, crash, parse_error}``), which is used for *counting* unusable
    runs, not for scoring them. The distinction is load-bearing and was found the hard way:
    zeroing on ``BROKEN`` instead moves the untailored m=11 arm from 0.834456 to 0.826781,
    because that arm contains exactly one ``parse_error`` episode. The DiD would then have
    been internally consistent but irreconcilable with CHAN-ZS-04 and every other published
    arm mean, and the discrepancy would have looked like an arithmetic error in the paper
    rather than a convention mismatch.

    ``error_type == "limit"`` is likewise NOT a crash: the episode ran out of steps or
    tokens with a real, scored transcript and is scored on its merits.
    """
    if row.get("error_type") == CRASH_ERROR_TYPE:
        return 0.0
    value = row.get(field)
    return 0.0 if value is None else float(value)


def _cluster_bootstrap(
    values: dict[tuple[str, int], float],
    unit: str,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """Percentile interval, resampling whole clusters with replacement.

    unit='scenario' groups on scenario_of(task_id); unit='task' groups on task_id. A
    scenario contributes all of its episodes whenever it is drawn, which is what makes
    this a cluster bootstrap rather than an episode bootstrap.
    """
    if not values:
        return {"point_pp": None, "ci95_pp": None, "n_clusters": 0, "resample_unit": unit}

    grouped: dict[str, list[float]] = {}
    for (task_id, _seed), value in values.items():
        key = scenario_of(task_id) if unit == "scenario" else task_id
        grouped.setdefault(key, []).append(value)

    clusters = sorted(grouped)
    point = statistics.fmean(values.values())
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        pooled: list[float] = []
        for _ in range(len(clusters)):
            pooled.extend(grouped[clusters[rng.randrange(len(clusters))]])
        means.append(sum(pooled) / len(pooled))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return {
        "point_pp": round(100.0 * point, 4),
        "ci95_pp": [round(100.0 * lo, 4), round(100.0 * hi, 4)],
        "n_clusters": len(clusters),
        "resample_unit": unit,
        "bootstrap": n_boot,
        "seed": seed,
    }


def compute_did(
    arms: dict[str, dict[tuple[str, int], dict[str, Any]]],
    a_pos: str,
    a_neg: str,
    b_pos: str,
    b_neg: str,
    field: str,
    n_boot: int = BOOTSTRAP,
    seed: int = DID_SEED,
) -> dict[str, Any]:
    """((a_pos - a_neg) - (b_pos - b_neg)), formed per episode then averaged."""
    labels = [a_pos, a_neg, b_pos, b_neg]
    for label in labels:
        if label not in arms:
            raise KeyError(f"arm {label!r} was not loaded; have {sorted(arms)}")

    key_sets = [set(arms[label]) for label in labels]
    shared = sorted(set.intersection(*key_sets))
    union = sorted(set.union(*key_sets))
    dropped = len(union) - len(shared)

    gap_a: dict[tuple[str, int], float] = {}
    gap_b: dict[tuple[str, int], float] = {}
    did: dict[tuple[str, int], float] = {}
    for key in shared:
        ga = episode_value(arms[a_pos][key], field) - episode_value(arms[a_neg][key], field)
        gb = episode_value(arms[b_pos][key], field) - episode_value(arms[b_neg][key], field)
        gap_a[key] = ga
        gap_b[key] = gb
        did[key] = ga - gb

    def arm_mean(label: str) -> float | None:
        if not shared:
            return None
        return round(
            statistics.fmean(episode_value(arms[label][k], field) for k in shared), 6
        )

    def crashed(label: str) -> int:
        return sum(
            1 for k in shared if arms[label][k].get("error_type") == CRASH_ERROR_TYPE
        )

    return {
        "field": field,
        "definition": f"({a_pos} - {a_neg}) - ({b_pos} - {b_neg})",
        "arms": {
            "a_pos": a_pos,
            "a_neg": a_neg,
            "b_pos": b_pos,
            "b_neg": b_neg,
        },
        "n_pairs": len(shared),
        "n_dropped_not_in_all_four": dropped,
        "arm_means": {label: arm_mean(label) for label in labels},
        "crashed_episodes": {label: crashed(label) for label in labels},
        "gap_a_pp": round(100.0 * statistics.fmean(gap_a.values()), 4) if gap_a else None,
        "gap_b_pp": round(100.0 * statistics.fmean(gap_b.values()), 4) if gap_b else None,
        "scenario": _cluster_bootstrap(did, "scenario", n_boot, seed),
        "task": _cluster_bootstrap(did, "task", n_boot, seed),
    }


def excludes_zero(block: dict[str, Any]) -> bool | None:
    ci = block.get("ci95_pp")
    if not ci:
        return None
    return ci[0] > 0.0 or ci[1] < 0.0


def parse_arm_spec(spec: str) -> tuple[str, list[Path]]:
    """LABEL=DIR[,DIR...], extending j8_frontier.parse_arm_spec with pooling.

    Several directories pool into one logical arm. This exists so a depth contrast can be
    computed over three planner seeds at once: the seeds-1,2 campaign and the seed-3
    campaign are separate directories, and episode keys are ``(task_id, seed)``, so they
    cannot collide. Pooling raises a contrast from 114 to 171 paired episodes without
    re-running anything.

    ⚠ Only pool campaigns that differ in SEED. Pooling two campaigns that share a seed
    silently drops one of every colliding episode, which ``compute_contrast`` cannot detect
    because the result still looks like a well-formed arm. The loader refuses that case.
    """
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"arm spec must be LABEL=DIR[,DIR...], got {spec!r}")
    label, raw = spec.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError(f"empty label in arm spec {spec!r}")
    paths = [Path(p.strip()).expanduser() for p in raw.split(",") if p.strip()]
    if not paths:
        raise argparse.ArgumentTypeError(f"no directory in arm spec {spec!r}")
    return label, paths


def load_pooled_arm(roots: list[Path]) -> dict[tuple[str, int], dict[str, Any]]:
    """Load one or more campaign directories into a single arm, refusing key collisions."""
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for root in roots:
        loaded = load_arm(root)
        clash = set(merged) & set(loaded)
        if clash:
            example = sorted(clash)[:3]
            raise ValueError(
                f"pooled campaigns share {len(clash)} episode keys (e.g. {example}); "
                "pool only campaigns that differ in seed, or one episode of each "
                "colliding pair is silently discarded"
            )
        merged.update(loaded)
    return merged


def compute_contrast(
    arms: dict[str, dict[tuple[str, int], dict[str, Any]]],
    a: str,
    b: str,
    field: str,
    n_boot: int = BOOTSTRAP,
    seed: int = DID_SEED,
) -> dict[str, Any]:
    """Plain paired contrast (a - b), same estimator and clustering as the DiD."""
    for label in (a, b):
        if label not in arms:
            raise KeyError(f"arm {label!r} was not loaded; have {sorted(arms)}")
    shared = sorted(set(arms[a]) & set(arms[b]))
    union = sorted(set(arms[a]) | set(arms[b]))
    diffs = {
        k: episode_value(arms[a][k], field) - episode_value(arms[b][k], field)
        for k in shared
    }

    def arm_mean(label: str) -> float | None:
        if not shared:
            return None
        return round(
            statistics.fmean(episode_value(arms[label][k], field) for k in shared), 6
        )

    return {
        "field": field,
        "definition": f"{a} - {b}",
        "n_pairs": len(shared),
        "n_dropped_not_in_both": len(union) - len(shared),
        "n_seeds": len({s for _, s in shared}),
        "arm_means": {a: arm_mean(a), b: arm_mean(b)},
        "scenario": _cluster_bootstrap(diffs, "scenario", n_boot, seed),
        "task": _cluster_bootstrap(diffs, "task", n_boot, seed),
    }


def parse_contrast_spec(spec: str) -> tuple[str, str, str]:
    """NAME:A,B"""
    if ":" not in spec:
        raise argparse.ArgumentTypeError(f"contrast spec must be NAME:A,B, got {spec!r}")
    name, rest = spec.split(":", 1)
    parts = [p.strip() for p in rest.split(",")]
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"contrast spec needs exactly two arm labels, got {spec!r}"
        )
    return (name.strip(), parts[0], parts[1])


def parse_did_spec(spec: str) -> tuple[str, str, str, str, str]:
    """NAME:A_POS,A_NEG,B_POS,B_NEG"""
    if ":" not in spec:
        raise argparse.ArgumentTypeError(f"did spec must be NAME:A,B,C,D, got {spec!r}")
    name, rest = spec.split(":", 1)
    parts = [p.strip() for p in rest.split(",")]
    if len(parts) != 4 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"did spec needs exactly four arm labels, got {spec!r}"
        )
    return (name.strip(), *parts)  # type: ignore[return-value]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arm", action="append", default=[], type=parse_arm_spec,
                   metavar="LABEL=DIR[,DIR]",
                   help="repeatable; several comma-separated dirs pool into one arm")
    p.add_argument("--did", action="append", default=[], type=parse_did_spec,
                   metavar="NAME:A_POS,A_NEG,B_POS,B_NEG", help="repeatable")
    p.add_argument("--contrast", action="append", default=[], type=parse_contrast_spec,
                   metavar="NAME:A,B", help="repeatable; plain paired contrast a - b")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--bootstrap", type=int, default=BOOTSTRAP)
    p.add_argument("--seed", type=int, default=DID_SEED)
    p.add_argument("--note", default="")
    a = p.parse_args(argv)

    if not a.arm:
        print("FATAL: at least one --arm is required", file=sys.stderr)
        return 2
    if not a.did and not a.contrast:
        print("FATAL: at least one --did or --contrast is required", file=sys.stderr)
        return 2

    arms: dict[str, dict[tuple[str, int], dict[str, Any]]] = {}
    sources: dict[str, list[str]] = {}
    for label, roots in a.arm:
        for root in roots:
            if not root.is_dir():
                print(f"FATAL: arm {label} directory does not exist: {root}",
                      file=sys.stderr)
                return 2
        try:
            loaded = load_pooled_arm(roots)
        except ValueError as exc:
            print(f"FATAL: arm {label}: {exc}", file=sys.stderr)
            return 2
        if not loaded:
            print(f"FATAL: arm {label} loaded 0 episodes from {roots}", file=sys.stderr)
            return 2
        arms[label] = loaded
        sources[label] = [str(r) for r in roots]
        seeds = sorted({s for _, s in loaded})
        print(f"[j14] {label}: {len(loaded)} episodes, seeds {seeds}, "
              f"from {len(roots)} campaign(s)")

    report: dict[str, Any] = {
        "analysis": "difference-in-differences, cluster bootstrap",
        "note": a.note,
        "bootstrap": a.bootstrap,
        "seed": a.seed,
        "population": "all (crashed episode scores 0; error_type 'limit' is not a crash)",
        "primary_resample_unit": "scenario",
        "arm_sources": sources,
        "arm_n_loaded": {k: len(v) for k, v in arms.items()},
        "arm_seeds": {k: sorted({s for _, s in v}) for k, v in arms.items()},
        "contrasts": {},
        "dids": {},
    }

    rc = 0
    for name, left, right in a.contrast:
        report["contrasts"][name] = {}
        for field in FIELDS:
            try:
                block = compute_contrast(
                    arms, left, right, field, n_boot=a.bootstrap, seed=a.seed,
                )
            except KeyError as exc:
                print(f"FATAL: {exc}", file=sys.stderr)
                return 2
            block["scenario"]["excludes_zero"] = excludes_zero(block["scenario"])
            block["task"]["excludes_zero"] = excludes_zero(block["task"])
            report["contrasts"][name][field] = block
            print(
                f"[j14] {name} {field}: {block['scenario']['point_pp']} pp "
                f"scenario {block['scenario']['ci95_pp']} "
                f"task {block['task']['ci95_pp']} "
                f"(n={block['n_pairs']}, seeds={block['n_seeds']})"
            )

    for name, a_pos, a_neg, b_pos, b_neg in a.did:
        report["dids"][name] = {}
        for field in FIELDS:
            try:
                block = compute_did(
                    arms, a_pos, a_neg, b_pos, b_neg, field,
                    n_boot=a.bootstrap, seed=a.seed,
                )
            except KeyError as exc:
                print(f"FATAL: {exc}", file=sys.stderr)
                return 2
            block["scenario"]["excludes_zero"] = excludes_zero(block["scenario"])
            block["task"]["excludes_zero"] = excludes_zero(block["task"])
            report["dids"][name][field] = block
            if block["n_dropped_not_in_all_four"]:
                print(
                    f"[j14] WARNING {name}/{field}: "
                    f"{block['n_dropped_not_in_all_four']} episodes were not present in "
                    "all four arms and were dropped",
                    file=sys.stderr,
                )
            ci = block["scenario"]["ci95_pp"]
            print(
                f"[j14] {name} {field}: DiD {block['scenario']['point_pp']} pp "
                f"scenario {ci} task {block['task']['ci95_pp']} "
                f"(n={block['n_pairs']}, gaps {block['gap_a_pp']} vs {block['gap_b_pp']})"
            )

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[j14] wrote {a.out}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
