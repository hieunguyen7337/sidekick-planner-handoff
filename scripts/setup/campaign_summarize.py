#!/usr/bin/env python
"""Summarise a Sidekick campaign, optionally gating on it or writing a manifest.

Layout produced by sidekick.runner:
    <out>/<campaign_id>/<system>/<seed>/<task_id>/result.json
    <out>/<campaign_id>/<system>/<seed>/<task_id>/events.jsonl

Gate mode exits non-zero when the campaign is broken in a way that makes continuing
a waste. A *low success rate is not a failure* -- an unaided small model scoring near
zero on AppWorld is an expected and meaningful result. Only crashes, a dead planner,
or the wrong model are gate failures.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from statistics import mean

# `parse_error` belongs here, and leaving it out cost a whole GPU job. A parse error is
# almost always the harness failing to read output the model produced correctly -- four of
# tonight's defects had that shape -- so it is exactly the kind of failure a resume after a
# fix must retry. Without it the stale results survived the purge, run_campaign skipped
# every smoke task (n_jobs=0, n_skipped=3), and the gate graded the *previous* build's
# output and failed an arm that was already fixed. `limit` is deliberately NOT here: an
# episode that spent its step budget is a real outcome, not a broken run.
BROKEN = {"api_error", "timeout", "crash", "parse_error"}


def _results(root: Path) -> list[dict]:
    out = []
    for path in sorted(root.rglob("result.json")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            try:
                out.append(json.loads(text))
            except json.JSONDecodeError:
                pass
    return out


_TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def _is_failed_call_placeholder(usage: dict) -> bool:
    """True for the zero-token bookkeeping record written when a call FAILED.

    `loop.py` charges a synthetic Usage on planner timeout / PacketParseError so the
    failed attempt still shows up in the ledger. Before 2026-09-16 it was labelled
    with the planner CLASS name ("codex-exec"), not a model id -- and reading that as
    model provenance failed `hj1c_fixed_k` on 2026-09-16 with "planner ran as
    ['codex-exec']" on an arm where all 931 real calls went to gpt-5.6-luna. Only 3
    of 114 runs carried one, so the gate turned 3 parse errors into a wrong-model
    verdict for the whole campaign.

    A genuine MockPlanner fallback is deliberately NOT filtered: its usage carries
    real token counts (15,378 input), so the mistyped-`planner.type` check this gate
    exists for still fires.
    """
    if (usage.get("provider") or "") != "mock":
        return False
    if any(int(usage.get(f) or 0) for f in _TOKEN_FIELDS):
        return False
    return bool((usage.get("raw") or {}).get("error_type"))


def _planner_models(root: Path) -> Counter:
    """Distinct model ids seen on planner-attributed usage records."""
    seen: Counter = Counter()
    for path in root.rglob("events.jsonl"):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or '"usage"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                usage = ev.get("usage") or {}
                model = usage.get("model")
                if not model or ev.get("actor") != "planner":
                    continue
                if _is_failed_call_placeholder(usage):
                    continue
                seen[model] += 1
        except OSError:
            continue
    return seen


def summarise(out_root: Path, campaign_id: str) -> dict:
    root = out_root / campaign_id
    rows = _results(root)
    by_seed: dict[str, dict] = {}
    for r in rows:
        key = str(r.get("seed"))
        b = by_seed.setdefault(key, {"n": 0, "success": 0, "tgc": []})
        b["n"] += 1
        b["success"] += 1 if r.get("success") else 0
        if r.get("tgc") is not None:
            b["tgc"].append(float(r["tgc"]))
    for b in by_seed.values():
        b["tgc_mean"] = round(mean(b["tgc"]), 4) if b["tgc"] else None
        b.pop("tgc")

    errors = Counter(r.get("error_type") or "none" for r in rows)
    planner_calls = sum(int(r.get("n_planner_calls") or 0) for r in rows)
    steps = [int(r.get("steps") or 0) for r in rows]
    goal_pass_rates = [
        float(r["goal_pass_rate"])
        for r in rows
        if r.get("goal_pass_rate") is not None
    ]

    totals: Counter = Counter()
    for r in rows:
        for k, v in (r.get("totals") or {}).items():
            if isinstance(v, (int, float)):
                totals[k] += v

    return {
        "campaign_id": campaign_id,
        "root": str(root),
        "n_runs": len(rows),
        "n_success": sum(1 for r in rows if r.get("success")),
        "success_rate": round(sum(1 for r in rows if r.get("success")) / len(rows), 4) if rows else None,
        "by_seed": by_seed,
        "errors": dict(errors),
        "n_broken": sum(errors[e] for e in BROKEN),
        "planner_calls_total": planner_calls,
        # Ledger spend (CostLedger.totals), not the replay-inclusive event count above.
        # Same split as j8_frontier.attach_ledger_fields (planner_calls_live vs
        # planner_calls_replay_inclusive). Do not rename planner_calls_total.
        "planner_calls_live_total": int(totals.get("planner_calls_total") or 0),
        "planner_calls_mean": round(planner_calls / len(rows), 2) if rows else None,
        "steps_mean": round(mean(steps), 2) if steps else None,
        "mean_goal_pass_rate": round(mean(goal_pass_rates), 4) if goal_pass_rates else None,
        "n_goal_pass_rate": len(goal_pass_rates),
        "planner_models": dict(_planner_models(root)),
        "ledger_totals": {k: round(v, 6) for k, v in totals.items()},
    }


def gate(summary: dict, *, expect_planner: bool, expect_model: str | None) -> list[str]:
    fails = []
    if summary["n_runs"] == 0:
        fails.append("no result.json files were written at all")
    elif summary["n_broken"] == summary["n_runs"]:
        fails.append(f"every run failed with {summary['errors']}")

    # A run that ends on `limit` after a couple of steps is degenerate: the episode
    # token budget ended the episode, not the task. That is a broken configuration,
    # not a low score, and it silently makes an arm score zero everywhere. Seen for
    # real on 2026-09-15: max_tokens_per_episode=32000 killed planner_alone at step 2,
    # because each codex call resends the transcript on ~15.4k of scaffolding.
    if summary["n_runs"]:
        n_limit = summary["errors"].get("limit", 0)
        frac = n_limit / summary["n_runs"]
        if frac >= 0.8 and (summary["steps_mean"] or 0) < 5:
            fails.append(
                f"{frac:.0%} of runs ended on 'limit' after only {summary['steps_mean']} "
                f"steps on average -- the episode token budget is ending episodes, not the task"
            )

    models = summary["planner_models"]
    if expect_planner:
        if summary["planner_calls_total"] == 0:
            fails.append(
                "zero planner calls recorded -- the planner was never invoked "
                "(a mistyped planner.type silently falls back to MockPlanner)"
            )
        if expect_model:
            wrong = [m for m in models if m != expect_model]
            if wrong:
                fails.append(f"planner ran as {wrong}, expected only {expect_model!r}")
            if not models:
                fails.append("no planner model id was recorded on any usage record")
    else:
        # prefix_handoff: live==0 with replay-inclusive>0 is the normal correct state, not a leak.
        live = int(summary.get("planner_calls_live_total") or 0)
        replay_inclusive = int(summary.get("planner_calls_total") or 0)
        if live != 0:
            fails.append(
                f"expected zero live planner calls but saw {live} "
                f"(replay-inclusive count {replay_inclusive}, models={models}) "
                f"-- this arm was supposed to be free"
            )
    return fails


def purge_broken(out_root: Path, campaign_id: str) -> int:
    """Delete the whole run directory for runs that failed in a way worth retrying.

    run_campaign skips any run whose result.json already exists. Without this, a run
    that crashed is never retried on resume -- so a maintenance kill mid-campaign
    would make those failures permanent instead of recoverable.

    ⚠ The whole directory, not just result.json. `EventLog` APPENDS, so deleting only the
    result left events.jsonl in place and the retry wrote its events after the failed
    attempt's. Observed 2026-09-15 in run 0d8a4ee_1: two `run_start` events and two
    step-0 observations in one file, the dead attempt and the live one concatenated with
    nothing marking the boundary. The headline metrics survived -- RunResult is rewritten
    each time -- but anything reading the event log double-counts, which includes the
    smoke gate's own `parseable_actions` tally and every future consumer of these
    trajectories as SFT data. A retried run must start from an empty directory.
    """
    root = out_root / campaign_id
    removed = 0
    for path in sorted(root.rglob("result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            shutil.rmtree(path.parent, ignore_errors=True)
            removed += 1
            continue
        if (data.get("error_type") or "") in BROKEN:
            shutil.rmtree(path.parent, ignore_errors=True)
            removed += 1
    return removed


def manifest(out_root: Path, campaign_id: str, config_path: Path, repo: Path) -> dict:
    def _run(cmd: list[str]) -> str:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=repo).stdout.strip()
        except Exception:
            return "unavailable"

    cfg_bytes = config_path.read_bytes() if config_path.exists() else b""
    appworld_commit = ""
    ac = Path("/scratch/n12194778/sidekick/appworld.commit")
    if ac.exists():
        appworld_commit = ac.read_text(encoding="utf-8").strip()

    # The manifest is written when the campaign FINISHES, which can be hours after it
    # started, and the tree may have moved on -- on 2026-09-15 four commits landed while
    # an arm was running. `git rev-parse HEAD` here would credit the results to code that
    # never produced them, which is worse than not recording a commit at all. The job
    # captures its SHA at start and exports it; fall back only when it did not.
    start_commit = os.environ.get("SIDEKICK_START_COMMIT", "").strip()
    return {
        "campaign_id": campaign_id,
        "git_commit": start_commit or _run(["git", "rev-parse", "HEAD"]),
        "git_commit_source": "job start" if start_commit else "manifest time (MAY NOT be the code that ran)",
        "git_branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_dirty": bool(_run(["git", "status", "--short"])),
        "config_path": str(config_path),
        "config_sha256": hashlib.sha256(cfg_bytes).hexdigest() if cfg_bytes else None,
        "appworld_commit": appworld_commit,
        "codex_version": _run(["codex", "--version"]),
        "hostname": platform.node(),
        "pbs_jobid": os.environ.get("PBS_JOBID", ""),
        "python": platform.python_version(),
        "summary": summarise(out_root, campaign_id),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--config")
    p.add_argument("--repo", default=".")
    p.add_argument("--gate", action="store_true")
    p.add_argument("--purge-broken", action="store_true",
                   help="delete result.json for crashed/timed-out runs so they are retried")
    p.add_argument("--expect-planner", action="store_true")
    p.add_argument("--expect-model")
    p.add_argument("--manifest", help="write a manifest.json here")
    a = p.parse_args()

    out_root = Path(a.out)
    if a.purge_broken:
        n = purge_broken(out_root, a.campaign_id)
        # Name the set from BROKEN rather than restating it, so the log cannot drift out
        # of step with what was actually deleted.
        print(f"[purge] removed {n} broken result.json ({'/'.join(sorted(BROKEN))}) so they retry")
    s = summarise(out_root, a.campaign_id)
    print(json.dumps(s, indent=2))

    if a.manifest:
        m = manifest(out_root, a.campaign_id, Path(a.config or ""), Path(a.repo))
        dest = Path(a.manifest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(m, indent=2), encoding="utf-8")
        print(f"[manifest] wrote {dest}")

    if a.gate:
        fails = gate(s, expect_planner=a.expect_planner, expect_model=a.expect_model)
        if fails:
            print("[gate] FAIL")
            for f in fails:
                print(f"  - {f}")
            return 1
        print("[gate] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
