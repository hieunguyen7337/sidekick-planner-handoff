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
import subprocess
from collections import Counter
from pathlib import Path
from statistics import mean

BROKEN = {"api_error", "timeout", "crash"}


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
                if model and ev.get("actor") == "planner":
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
        "planner_calls_mean": round(planner_calls / len(rows), 2) if rows else None,
        "steps_mean": round(mean(steps), 2) if steps else None,
        "planner_models": dict(_planner_models(root)),
        "ledger_totals": {k: round(v, 6) for k, v in totals.items()},
    }


def gate(summary: dict, *, expect_planner: bool, expect_model: str | None) -> list[str]:
    fails = []
    if summary["n_runs"] == 0:
        fails.append("no result.json files were written at all")
    elif summary["n_broken"] == summary["n_runs"]:
        fails.append(f"every run failed with {summary['errors']}")

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
        if summary["planner_calls_total"] != 0:
            fails.append(
                f"expected zero planner calls but saw {summary['planner_calls_total']} "
                f"(models={models}) -- this arm was supposed to be free"
            )
    return fails


def purge_broken(out_root: Path, campaign_id: str) -> int:
    """Delete result.json for runs that failed in a way worth retrying.

    run_campaign skips any run whose result.json already exists. Without this, a run
    that crashed is never retried on resume -- so a maintenance kill mid-campaign
    would make those failures permanent instead of recoverable.
    """
    root = out_root / campaign_id
    removed = 0
    for path in sorted(root.rglob("result.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            path.unlink(missing_ok=True)
            removed += 1
            continue
        if (data.get("error_type") or "") in BROKEN:
            path.unlink(missing_ok=True)
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

    return {
        "campaign_id": campaign_id,
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
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
        print(f"[purge] removed {n} broken result.json (crash/timeout/api_error) so they retry")
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
