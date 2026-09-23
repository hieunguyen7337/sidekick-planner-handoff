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


def gate(
    summary: dict,
    *,
    expect_planner: bool,
    expect_model: str | None,
    allow_live_planner: bool = False,
) -> list[str]:
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
    elif allow_live_planner:
        # prefix_handoff with its planner SERVED (scripts/pbs/lp_live.pbs): the system honours
        # executor asks, so a stuck executor's ask is answered live and live > 0 is part of the
        # arm, while most episodes make no live call at all. Neither count is required. The model
        # check reads the planner-attributed usage records that exist -- vacuous at zero live
        # calls, and a mock fallback or a wrong server fails it as soon as one ask is answered.
        if expect_model:
            wrong = [m for m in models if m != expect_model]
            if wrong:
                fails.append(f"planner ran as {wrong}, expected only {expect_model!r}")
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


# The project crash convention (J10 / A1 §10.1): an episode is a crash ONLY when its
# result.json says `error_type == "crash"`. Everything else that wrote a readable result
# -- `limit`, `timeout`, `parse_error`, `api_error`, or no error at all -- is a scored
# outcome of the registered read and must never be deleted or re-run. `--purge-broken`
# (BROKEN above) is deliberately wider: it also retries timeout / parse_error / api_error,
# which is right for a dev resume after a harness fix and wrong for a confirmatory read,
# where re-running a scored episode is a second look at it.
CRASH_ERROR_TYPE = "crash"


def _campaign_root(out_root: Path, campaign_id: str) -> Path:
    """<out_root>/<campaign_id>, refusing any id that could resolve outside out_root."""
    cid = str(campaign_id or "").strip()
    if not cid or cid in {".", ".."} or "/" in cid or "\\" in cid:
        raise ValueError(f"refusing unsafe campaign id {campaign_id!r}")
    root = out_root / cid
    if root.resolve().parent != out_root.resolve():
        raise ValueError(f"refusing campaign id {campaign_id!r}: resolves outside {out_root}")
    return root


def purge_crashed(out_root: Path, campaign_id: str) -> dict[str, int]:
    """Delete ONLY the episode directories that are not scored outcomes.

    Removed, each as a whole directory (EventLog appends, see purge_broken):
      * ``crash``             -- result.json parses and ``error_type == "crash"``;
      * ``unreadable_result`` -- result.json is empty, not JSON, or not an object
        (a write killed mid-flight; the runner would otherwise skip it forever,
        because it only checks that the file exists);
      * ``no_result``         -- an attempt directory with events/manifest but no
        result.json (the job died mid-episode). The runner re-runs it anyway, but
        into the same events.jsonl, which it opens for APPEND
        [src/sidekick/trajectories/eventlog.py:30].
    Kept: every readable result.json whose error_type is anything but "crash",
    including ``limit`` / ``timeout`` / ``parse_error`` / ``api_error``.

    Only ``<out_root>/<campaign_id>`` is touched. Callers must not run this while
    another job is writing the same campaign (the J10 wrapper holds a lock).
    """
    counts = {"crash": 0, "unreadable_result": 0, "no_result": 0, "kept": 0}
    root = _campaign_root(out_root, campaign_id)
    if not root.is_dir():
        return counts
    doomed: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("result.json")):
        try:
            text = path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if not isinstance(data, dict):
            doomed.append((path.parent, "unreadable_result"))
        elif data.get("error_type") == CRASH_ERROR_TYPE:
            doomed.append((path.parent, "crash"))
        else:
            counts["kept"] += 1
    attempt_dirs: set[Path] = set()
    for name in ("events.jsonl", "manifest.json"):
        attempt_dirs.update(p.parent for p in root.rglob(name))
    for ep in sorted(attempt_dirs):
        if not (ep / "result.json").exists():
            doomed.append((ep, "no_result"))
    for ep, why in doomed:
        if ep == root or root not in ep.parents:
            continue  # never delete the campaign root itself or anything outside it
        shutil.rmtree(ep, ignore_errors=True)
        counts[why] += 1
    return counts


def split_check(
    out_root: Path,
    campaign_id: str,
    expect_split: str,
    dev_task_ids: set[str],
) -> list[str]:
    """A1 §10.2 (2): verify the campaign actually ran on the split it claims.

    The split is a CLI argument, so a campaign can silently evaluate dev tasks while
    every name says test. Dev and test share no task ids, so for a non-dev split any
    overlap with the dev list is fatal; for dev, every id must be a dev id. Each
    episode's manifest.json also records the split it was launched with
    (``provenance.split``); a recorded split that disagrees is fatal too.
    Returns failure strings (empty = pass). An empty campaign is a failure, not a
    vacuous pass.
    """
    root = _campaign_root(out_root, campaign_id)
    task_ids: set[str] = set()
    recorded: Counter = Counter()
    for path in sorted(root.rglob("result.json")) if root.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8").strip() or "null")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or data.get("task_id") is None:
            continue
        task_ids.add(str(data["task_id"]))
        split = None
        man = path.parent / "manifest.json"
        if man.exists():
            try:
                prov = (json.loads(man.read_text(encoding="utf-8")) or {}).get("provenance") or {}
                split = prov.get("split") if isinstance(prov, dict) else None
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                split = None
        recorded[str(split) if split is not None else "unrecorded"] += 1
    fails: list[str] = []
    if not task_ids:
        fails.append(f"no readable result.json under {root}; nothing to verify")
        return fails
    if expect_split == "dev":
        foreign = sorted(task_ids - set(dev_task_ids))
        if foreign:
            fails.append(f"{len(foreign)} task id(s) are not dev ids, e.g. {foreign[:3]}")
    else:
        overlap = sorted(task_ids & set(dev_task_ids))
        if overlap:
            fails.append(
                f"{len(overlap)} task id(s) are DEV ids in a campaign expected to be "
                f"{expect_split!r}, e.g. {overlap[:3]} -- the split flag did not take effect"
            )
    wrong = {k: v for k, v in recorded.items() if k not in {expect_split, "unrecorded"}}
    if wrong:
        fails.append(f"episode manifests record split(s) {wrong}, expected {expect_split!r}")
    return fails


def _load_dev_task_ids() -> set[str]:
    from appworld import load_task_ids  # lazy: only the compute node has AppWorld data

    return {str(t) for t in load_task_ids("dev")}


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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--campaign-id", required=True)
    p.add_argument("--config")
    p.add_argument("--repo", default=".")
    p.add_argument("--gate", action="store_true")
    purge = p.add_mutually_exclusive_group()
    purge.add_argument("--purge-broken", action="store_true",
                       help="delete the run dirs of api_error/timeout/crash/parse_error runs "
                            "(and unparseable result.json) so they are retried")
    purge.add_argument("--purge-crashed-only", action="store_true",
                       help="crash convention: delete ONLY run dirs whose result.json has "
                            "error_type == 'crash', plus unreadable result.json and "
                            "result-less attempt dirs. limit/timeout/parse_error/api_error "
                            "are scored outcomes and are kept.")
    p.add_argument("--expect-planner", action="store_true")
    p.add_argument("--expect-model")
    p.add_argument("--allow-live-planner", action="store_true",
                   help="without --expect-planner: live planner calls are part of the arm "
                        "(prefix_handoff with its planner served), so do not require zero; "
                        "--expect-model then checks every planner model id recorded")
    p.add_argument("--expect-split",
                   help="A1 §10.2: fail unless every task id matches this split "
                        "(dev ids for 'dev'; zero overlap with dev ids otherwise)")
    p.add_argument("--manifest", help="write a manifest.json here")
    a = p.parse_args(argv)

    out_root = Path(a.out)
    if a.purge_broken:
        n = purge_broken(out_root, a.campaign_id)
        # Name the set from BROKEN rather than restating it, so the log cannot drift out
        # of step with what was actually deleted.
        print(f"[purge] removed {n} broken result.json ({'/'.join(sorted(BROKEN))}) so they retry")
    if a.purge_crashed_only:
        c = purge_crashed(out_root, a.campaign_id)
        print(
            f"[purge-crashed-only] campaign={a.campaign_id} removed crash={c['crash']} "
            f"unreadable_result={c['unreadable_result']} no_result={c['no_result']} "
            f"kept={c['kept']} (limit/timeout/parse_error/api_error are kept)"
        )
    split_fails: list[str] = []
    if a.expect_split:
        split_fails = split_check(out_root, a.campaign_id, a.expect_split, _load_dev_task_ids())
        print(f"[split] {'FAIL' if split_fails else 'PASS'} expect={a.expect_split}")
        for f in split_fails:
            print(f"  - {f}")
    s = summarise(out_root, a.campaign_id)
    print(json.dumps(s, indent=2))

    if a.manifest:
        m = manifest(out_root, a.campaign_id, Path(a.config or ""), Path(a.repo))
        dest = Path(a.manifest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(m, indent=2), encoding="utf-8")
        print(f"[manifest] wrote {dest}")

    if a.gate:
        fails = gate(
            s,
            expect_planner=a.expect_planner,
            expect_model=a.expect_model,
            allow_live_planner=a.allow_live_planner,
        )
        if fails:
            print("[gate] FAIL")
            for f in fails:
                print(f"  - {f}")
            return 1
        print("[gate] PASS")
    if split_fails:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
