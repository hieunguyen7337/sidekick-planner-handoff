"""Build the campaign provenance index that Appendix A.5 points readers at.

Appendix A.5 states that provenance is established "at campaign granularity through
`campaign/RUNS.md`" because per-episode `result.json` files do not yet carry a git SHA
(task X16). That promise was only half true: RUNS.md carried narrative sections for the
hj8/hj12 era and named none of the hj13-hj19 campaigns that most of the paper now rests
on. This script closes the gap mechanically, so the index cannot drift from the artifacts
the way a hand-maintained list does.

The index covers the campaigns that are actually *cited* - those named inside a report
JSON under `campaign/results/` - rather than every directory on scratch, which would bury
the ~60 load-bearing campaigns under smoke runs and superseded dates.

For each campaign it records what a reader needs to re-run or audit it: the config, the
system, the seeds, the episode count, the `error_type` distribution (so a reader can see
crashes rather than trust an exit code, per the standing rule that PBS exit 0 proves
nothing), the handoff source campaign where one exists - which is what makes a prefix arm
task-paired rather than trajectory-paired - and the reports that cite it.

Usage:
    python scripts/analysis/campaign_index.py --out campaign/campaign_index.json
    python scripts/analysis/campaign_index.py --out - --markdown
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

RESULTS_ROOT = Path("/scratch/n12194778/sidekick/results")
REPORTS_DIR = Path("campaign/results")
CONFIGS_DIR = Path("configs")

# A campaign id as it appears inside a report: the directory name under the results root.
# Anchored on the results root so a bare word in a note cannot be mistaken for a campaign.
CAMPAIGN_RE = re.compile(r"/scratch/[^\s\"']*/results/([A-Za-z0-9_.-]+)")

# Kept in sync with j8_frontier.CRASH_ERROR_TYPE by test_campaign_index, which asserts the
# two are equal rather than trusting this copy. `limit` is NOT a crash.
CRASH_ERROR_TYPE = "crash"


# A report records the arms it *rejected* as well as the ones it used: the mechanism
# reports carry an `arms_used.excluded_arms[]` list of candidate paths, most of which
# never existed. Counting those as citations reported 21 "missing" campaigns that nothing
# actually depends on - an index that invents a provenance gap is worse than none.
EXCLUSION_PATH_MARKERS = ("exclude", "candidate", "rejected", "skipped", "not_found")


def campaign_ids_in_text(text: str) -> set[str]:
    """Every campaign directory named anywhere in a blob of report JSON.

    Matching on the results root rather than on a name list means a report that starts
    citing a new campaign is picked up without editing this script.
    """
    return {m.group(1) for m in CAMPAIGN_RE.finditer(text)}


def walk_strings(node: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    """Yield (dotted_key_path, string_value) for every string in a parsed JSON tree."""
    if isinstance(node, str):
        yield prefix, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from walk_strings(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk_strings(value, f"{prefix}.{i}" if prefix else str(i))


def is_exclusion_path(key_path: str) -> bool:
    """True when this key path records a rejected candidate rather than a dependency."""
    lowered = key_path.lower()
    return any(marker in lowered for marker in EXCLUSION_PATH_MARKERS)


def collect_citations(reports_dir: Path) -> dict[str, dict[str, Any]]:
    """Map campaign id -> how it is referenced across the reports.

    Distinguishes a real dependency (the report read episodes from it) from a recorded
    rejection (the report noted it as a candidate it did not use), because only the first
    kind makes an absent campaign a problem.
    """
    used: dict[str, set[str]] = {}
    excluded: dict[str, set[str]] = {}
    for report in sorted(reports_dir.glob("*.json")):
        try:
            data = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key_path, value in walk_strings(data):
            for campaign in campaign_ids_in_text(value):
                bucket = excluded if is_exclusion_path(key_path) else used
                bucket.setdefault(campaign, set()).add(report.name)

    out: dict[str, dict[str, Any]] = {}
    for campaign in sorted(set(used) | set(excluded)):
        out[campaign] = {
            "used_by": sorted(used.get(campaign, set())),
            "listed_as_excluded_by": sorted(excluded.get(campaign, set())),
        }
    return out


def _first(values: Iterable[Any]) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def index_configs(configs_dir: Path) -> dict[str, dict[str, Any]]:
    """Map `campaign_id` -> the config that declares it.

    ⚠ This is a join through the *repository*, not through the run record. A campaign's
    episodes do not store the config that produced them, the adapter they served, or the
    planner campaign they replayed: `manifest.json` carries only campaign_id, run ids,
    host, env and python version. Everything below is therefore recovered by matching the
    `campaign_id` a config declares against the directory a run wrote to. It is reliable
    (the runner derives the directory from that field) but it is reconstruction, and it
    would break for a campaign whose config was edited after the run. Closing that
    properly is task X16, widened: the run record should carry config path, adapter,
    source campaign and git SHA.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - yaml ships with the project env
        return {}

    index: dict[str, dict[str, Any]] = {}
    for path in sorted(configs_dir.glob("*.yaml")):
        try:
            cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, Exception):  # noqa: BLE001 - a malformed config must not abort the index
            continue
        if not isinstance(cfg, dict):
            continue
        campaign_id = cfg.get("campaign_id")
        if not campaign_id:
            continue
        handoff = cfg.get("handoff") or {}
        defaults = cfg.get("policy_defaults") or {}
        executor = cfg.get("executor") or {}
        source = handoff.get("source_campaign") or handoff.get("packet_source")
        if not source:
            source = (cfg.get("planner") or {}).get("packet_source")
        index[str(campaign_id)] = {
            "config_path": str(path),
            "declared_campaign_id": str(campaign_id),
            "handoff_source_campaign": Path(str(source)).name if source else None,
            "handoff_m": handoff.get("m"),
            # The adapter alias lives on the executor block, not policy_defaults; reading
            # only the latter silently reported every arm as untailored.
            "lora_name": executor.get("lora_name") or defaults.get("lora_name"),
            "takeover": defaults.get("takeover"),
        }
    return index


# A campaign id is <stem>_<YYYYMMDD><optional suffix>. The date is what the PBS wrapper
# varies between re-runs of the same arm.
CAMPAIGN_DATE_SUFFIX = re.compile(r"_\d{8}[A-Za-z0-9]*$")


def campaign_stem(campaign_id: str) -> str:
    """The arm identity, with the run-date suffix removed."""
    return CAMPAIGN_DATE_SUFFIX.sub("", campaign_id)


def match_config(campaign: str, config_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Find the config behind a campaign, exactly or by arm stem.

    ⚠ The stem fallback exists because several of the paper's primary dev prefix arms ran
    under a campaign id their config does NOT declare: `scripts/pbs/hj12_prefix.pbs` takes
    the campaign id as an argument and overrides the file, so
    `configs/hj12_prefix_m11.yaml` says `hj12_prefix_m11_20260922` while the published arm
    is `hj12_prefix_m11_20260923`. Re-running that config verbatim writes to the *other*
    directory. The match method is recorded so this is visible rather than smoothed over.
    """
    exact = config_index.get(campaign)
    if exact:
        return {**exact, "config_match": "campaign_id"}

    stem = campaign_stem(campaign)
    candidates = [c for cid, c in config_index.items() if campaign_stem(cid) == stem]
    if len(candidates) == 1:
        return {
            **candidates[0],
            "config_match": "arm_stem",
            "config_declares_a_different_campaign_id": candidates[0]["declared_campaign_id"],
        }
    if len(candidates) > 1:
        return {"config_match": "ambiguous", "candidate_configs": sorted(c["config_path"] for c in candidates)}
    return {"config_match": "none"}


def read_run_manifest(campaign_dir: Path) -> dict[str, Any]:
    """Provenance the run itself recorded, from the first episode manifest."""
    manifests = sorted(campaign_dir.glob("*/*/*/manifest.json"))
    if not manifests:
        return {}
    try:
        m = json.loads(manifests[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        "campaign_id_recorded": m.get("campaign_id"),
        "created_at": m.get("created_at"),
        "env": m.get("env"),
        "python_version": m.get("python_version"),
        "schema_version": m.get("schema_version"),
    }


def summarise_campaign(campaign_dir: Path) -> dict[str, Any]:
    """Read one campaign's episodes into a provenance record.

    Deliberately tolerant: a campaign that is cited but absent from scratch is reported as
    missing rather than raising, because the index must still build on a machine where an
    old campaign has been cleaned up.
    """
    if not campaign_dir.is_dir():
        return {"present": False}

    results = sorted(campaign_dir.glob("*/*/*/result.json"))
    if not results:
        return {"present": True, "n_episodes": 0, "note": "directory exists but holds no result.json"}

    error_types: Counter[str] = Counter()
    seeds: set[int] = set()
    tasks: set[str] = set()
    systems: set[str] = set()
    configs: set[str] = set()
    sources: set[str] = set()
    adapters: set[str] = set()
    goal_pass_sum = 0.0
    tgc_sum = 0.0

    for path in results:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            error_types["UNREADABLE"] += 1
            continue

        error_types[row.get("error_type") or "none"] += 1

        seed = row.get("seed")
        if seed is not None:
            seeds.add(int(seed))
        if row.get("task_id"):
            tasks.add(str(row["task_id"]))

        # The per-episode record nests provenance under a few different keys across eras;
        # take the first that is populated rather than assuming one layout.
        config = _first([row.get("config_path"), (row.get("config") or {}).get("path")])
        if config:
            configs.add(str(config))
        system = _first([row.get("system"), (row.get("config") or {}).get("system")])
        if system:
            systems.add(str(system))
        source = _first([
            ((row.get("config") or {}).get("handoff") or {}).get("source_campaign"),
            row.get("source_campaign"),
        ])
        if source:
            sources.add(str(source))
        adapter = _first([
            ((row.get("config") or {}).get("policy_defaults") or {}).get("lora_name"),
            row.get("lora_name"),
        ])
        if adapter:
            adapters.add(str(adapter))

        # A crashed episode scores 0; `limit` keeps its recorded score (j8_frontier).
        if row.get("error_type") == CRASH_ERROR_TYPE:
            continue
        goal_pass_sum += float(row.get("goal_pass_rate") or 0.0)
        tgc_sum += float(row.get("tgc") or 0.0)

    n = len(results)
    n_crashed = error_types.get(CRASH_ERROR_TYPE, 0)
    return {
        "present": True,
        "n_episodes": n,
        "n_tasks": len(tasks),
        "seeds": sorted(seeds),
        "n_crashed": n_crashed,
        "error_types": dict(sorted(error_types.items())),
        "systems": sorted(systems),
        "configs": sorted(configs),
        "handoff_source_campaigns": sorted(sources),
        "adapters": sorted(adapters),
        # Reported to 6 dp to match the ledger's convention; these are provenance
        # aggregates for cross-checking a report, never a substitute for one.
        "goal_pass_mean": round(goal_pass_sum / n, 6) if n else None,
        "tgc_mean": round(tgc_sum / n, 6) if n else None,
    }


def build_index(reports_dir: Path, results_root: Path, configs_dir: Path | None = None) -> dict[str, Any]:
    citations = collect_citations(reports_dir)
    config_index = index_configs(configs_dir) if configs_dir else {}
    campaigns: dict[str, Any] = {}
    for campaign, refs in citations.items():
        campaign_dir = results_root / campaign
        record = summarise_campaign(campaign_dir)
        record.update(refs)
        record["is_dependency"] = bool(refs["used_by"])
        if record.get("present"):
            record["run_manifest"] = read_run_manifest(campaign_dir)
        # Recovered from the repo, NOT from the run record - see index_configs. Kept
        # under its own key so a reader can tell the two apart.
        record["from_config"] = match_config(campaign, config_index) if config_index else {}
        campaigns[campaign] = record

    deps = [c for c, r in campaigns.items() if r["is_dependency"]]
    missing_deps = sorted(c for c in deps if not campaigns[c].get("present"))
    # Campaigns whose config declares a different id than the run used: re-running the
    # config verbatim would write elsewhere. Surfaced, not smoothed over.
    id_mismatches = sorted(
        c for c in deps
        if campaigns[c].get("from_config", {}).get("config_declares_a_different_campaign_id")
    )
    return {
        "purpose": (
            "Campaign-granularity provenance for every campaign referenced by a report under "
            "campaign/results/. Generated by scripts/analysis/campaign_index.py; do not "
            "hand-edit. Per-episode git SHA is still missing (X16) and this index does not "
            "supply it."
        ),
        "results_root": str(results_root),
        "n_campaigns_referenced": len(campaigns),
        "n_dependencies": len(deps),
        "n_dependencies_present": len(deps) - len(missing_deps),
        "missing_dependencies": missing_deps,
        "config_id_mismatches": id_mismatches,
        "note_on_config_id_mismatches": (
            "These campaigns ran under an id their config does not declare, because the PBS "
            "wrapper passes the campaign id as an argument and overrides the file. Re-running "
            "such a config verbatim writes to the id in the file, not the published one."
        ),
        "note_on_excluded": (
            "A campaign listed only under a report's excluded/candidate keys was considered "
            "and not used; most such paths never existed. Those are reported for "
            "completeness and are NOT provenance gaps."
        ),
        "campaigns": campaigns,
    }


def to_markdown(index: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("## Campaign index (generated)")
    lines.append("")
    lines.append(
        "Generated by `scripts/analysis/campaign_index.py` from the episode records and the "
        "report JSONs that cite them. This is the campaign-granularity provenance that "
        "Appendix A.5 refers to. **Do not hand-edit**; re-run the script."
    )
    lines.append("")
    missing = index["missing_dependencies"]
    lines.append(
        f"{index['n_campaigns_referenced']} campaigns are referenced by a report. "
        f"**{index['n_dependencies']} are real dependencies** (a report read episodes from "
        f"them), of which {index['n_dependencies_present']} are present under "
        f"`{index['results_root']}`."
    )
    lines.append("")
    if missing:
        lines.append(
            "⚠ **Missing dependencies** — a report cites these for data and they are not on "
            "disk: " + ", ".join(f"`{c}`" for c in missing) + "."
        )
    else:
        lines.append(
            "Every campaign a report actually reads from is present. The remaining "
            "referenced campaigns appear only under reports' excluded/candidate keys — they "
            "were considered and not used, and most never existed, so their absence is not a "
            "provenance gap."
        )
    lines.append("")
    lines.append(
        "`crashed` counts `error_type == \"crash\"` only — `limit` is not a crash and keeps "
        "its recorded score. `source` is the replayed planner campaign for prefix arms, which "
        "is what makes an arm trajectory-paired rather than merely task-paired."
    )
    lines.append("")
    lines.append(
        "⚠ **`config`, `adapter` and `source` are recovered from the repository**, by matching "
        "the `campaign_id` a config declares against the directory the run wrote to. The run "
        "record does not carry them: an episode's `manifest.json` holds only campaign id, run "
        "id, host, env, python version and timestamp. That reconstruction is reliable — the "
        "runner derives the output directory from that same field — but it is not the same as "
        "the run having recorded it, and it would silently mislead for a campaign whose config "
        "was edited after the run. See the provenance note in the paper's appendix."
    )
    lines.append("")
    mismatches = index.get("config_id_mismatches") or []
    if mismatches:
        lines.append(
            "⚠ **Config/campaign id mismatch** — these campaigns ran under an id their config "
            "does not declare, because `scripts/pbs/hj12_prefix.pbs` takes the campaign id as "
            "an argument and overrides the file. Re-running such a config verbatim writes to "
            "the id *in the file*, not the published one, so a reproducer must pass the id "
            "explicitly: " + ", ".join(f"`{c}`" for c in mismatches) + "."
        )
        lines.append("")
    lines.append(
        "| campaign | role | n | tasks | seeds | crashed | error types | adapter | source campaign | config | goal_pass |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for campaign, rec in sorted(index["campaigns"].items()):
        role = "dependency" if rec["is_dependency"] else "excluded candidate"
        cfg = rec.get("from_config") or {}
        if not rec.get("present"):
            state = "*absent (never used)*" if not rec["is_dependency"] else "*absent — MISSING*"
            lines.append(f"| `{campaign}` | {role} | — | — | — | — | {state} | — | — | — | — |")
            continue
        errs = ", ".join(f"{k}:{v}" for k, v in rec.get("error_types", {}).items()) or "—"
        src = cfg.get("handoff_source_campaign")
        adapter = cfg.get("lora_name")
        config_path = cfg.get("config_path")
        seeds = ",".join(str(s) for s in rec.get("seeds", [])) or "—"
        gp = rec.get("goal_pass_mean")
        lines.append(
            f"| `{campaign}` | {role} | {rec.get('n_episodes', 0)} | {rec.get('n_tasks', 0)} "
            f"| {seeds} | {rec.get('n_crashed', 0)} | {errs} "
            f"| {'`' + adapter + '`' if adapter else '—'} "
            f"| {'`' + src + '`' if src else '—'} "
            f"| {'`' + config_path + '`' if config_path else '—'} "
            f"| {gp if gp is not None else '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    parser.add_argument("--results-root", type=Path, default=RESULTS_ROOT)
    parser.add_argument("--configs-dir", type=Path, default=CONFIGS_DIR)
    parser.add_argument("--out", required=True, help="output path, or - for stdout")
    parser.add_argument("--markdown", action="store_true", help="emit a markdown table instead of JSON")
    args = parser.parse_args(argv)

    index = build_index(args.reports_dir, args.results_root, args.configs_dir)
    text = to_markdown(index) if args.markdown else json.dumps(index, indent=2, sort_keys=True)

    if args.out == "-":
        sys.stdout.write(text + "\n")
    else:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(
            f"[campaign_index] wrote {out} "
            f"({index['n_dependencies_present']}/{index['n_dependencies']} dependencies present, "
            f"{index['n_campaigns_referenced']} campaigns referenced)"
        )
        if index["missing_dependencies"]:
            print(f"[campaign_index] WARNING missing dependencies: {', '.join(index['missing_dependencies'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
