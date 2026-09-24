#!/usr/bin/env python
"""J17 channel fixes: the dev analyses behind the channel claims (review F2, F4, F7).

Rows R2.1-R2.3, R4.3, R4.4 and R7.1 of ``docs/plan_review_fixes_20260923.md`` §1, plus the
G12 latency column, answering ``docs/review_paperA_adversarial_20260923.md`` §F2, §F4 and
§F7. Dev only and exploratory: nothing here decides a registered verdict.

Nothing statistical is new here; it is imported, so it cannot drift:
  - the arms are b2_decomposition's pooled arms (Amendment 1 §5: the union of two
    campaigns keyed (task_id, seed); a key twice is an error), scored by
    j10_report.a1_arm_episodes (a crash is dropped and counted; limit is scored);
  - every interval and p is the J10 A1 machinery: j10.a1_contrast (scenario-primary and
    task cluster bootstrap), j10.bootstrap_pvalue (two-sided, 2 x the smaller tail);
  - the limit split and the limit-as-0 zeroing are j10.am1_limit_split / am1_limit_as_zero
    (A1 Amendment 1 §D2/§D3); SGC is j10.a1_sgc_units; the show arm's copy rate is
    b2_decomposition.copy_rate; Benjamini-Yekutieli is cluster_inference.by_fdr.
What this file adds: the report layout (shared with unit S4-depth's j17_depth_fixes.py),
the content census of the interventions, the latency and census blocks, and the BY family.

Every contrast object carries diff_pp, ci95_pp_scenario, ci95_pp_task, p_two_sided (the
two-sided bootstrap p at threshold_pp, scenario clustering), threshold_pp, n_pairs, metric.

Exit codes
  0  report written
  1  report written, but an arm campaign directory is missing (named in `warnings`)
  2  refused: a path containing test_normal, test_challenge or j10_; an output under
     /scratch; a (task_id, seed) key twice within one arm; an unreadable --depth-report
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import b2_decomposition as b2  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402  (the module b2 uses)
from scripts.analysis.cluster_inference import by_fdr  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

PROTOCOL = "J17-channel"
RESULTS_ROOT = j10.RAW_RESULTS_ROOT
CAMPAIGN_INDEX = REPO_ROOT / "campaign" / "campaign_index.json"
CLAIMS_LEDGER = REPO_ROOT / "docs" / "claims_ledger.md"
N_BOOT = 10_000
BOOTSTRAP_SEED = 20260924
ALPHA = 0.05
SEEDS: tuple[int, ...] = b2.SEEDS  # dev seeds {1, 2} + {3}: 57 x 3 = 171 pairs
LIMIT = j10.A1_LIMIT_ERROR  # "limit": the 40-step limit, a scored outcome
CRASH = "crash"
REFUSED_MARKERS = ("test_normal", "test_challenge", "j10_")
DEV_N_TASKS = j10.A1_SPLIT_N_TASKS["dev"]  # 57

# The four channel arms are b2's own campaign pairs; advise_k1 has seeds 1-2 only (114 pairs).
ARM_CAMPAIGNS: dict[str, tuple[str, ...]] = {
    "takeover_k10": b2.ARM_CAMPAIGNS["T"],
    "advise_k10": b2.ARM_CAMPAIGNS["A"],  # the registered correction prompt
    "advise_k10_neutral": b2.ARM_CAMPAIGNS["N"],
    "show_k10": b2.ARM_CAMPAIGNS["S"],
    "advise_k1": ("hj13_advise_fixed_k_1_fullctx_20260923",),
}
CONTRASTS: dict[str, tuple[str, str]] = {  # id: (left, right), read left - right
    "D0": ("takeover_k10", "advise_k10"),
    "N": ("advise_k10_neutral", "advise_k10"),
    "S": ("show_k10", "advise_k10"),
    "TN": ("takeover_k10", "advise_k10_neutral"),
}
CONTENT_LABELS = ("advise_k10", "advise_k10_neutral", "show_k10")
SHOW_LABEL = "show_k10"
# R2.1: arms whose quality numbers the paper prints without a limit rate beside them.
LIMIT_ONLY_CAMPAIGNS: tuple[str, ...] = (
    "hj13_planner_alone_cap81_20260923",
    "hj17_prefix_c81_bplus_m6_20260923",
    "hj17_prefix_c81_bplus_m9_20260923",
    "hj17_prefix_c81_bplus_m11_20260923",
    "hj17_prefix_c81_zs_m6_20260923",
    "hj17_prefix_c81_zs_m9_20260923",
    "hj17_prefix_c81_zs_m11_20260923",
    "hj8_sft_plan_bplus_20260919",
    "hj8_executor_alone_bplus_20260919",
)
SPLIT_LABEL = "post-treatment mechanism, not a corrected estimate"
CONTRAST_KEYS = ("diff_pp", "ci95_pp_scenario", "ci95_pp_task", "p_two_sided", "threshold_pp", "n_pairs", "metric")

# b2_decomposition defines the copy rate (:561-603) but not "fenced code" or length, so they
# are fixed here. A fenced block is an opening ``` line (any info string, e.g. python or
# text), then text, then a closing ```; a ``` pair inside one line is not a block.
FENCED_BLOCK_RE = re.compile(r"```[^`\n]*\n.*?```", re.DOTALL)
# The executor's CODE spelling, the lazy form of sidekick/protocols/schemas.py:162.
PYTHON_BLOCK_RE = re.compile(r"```[ \t]*python[ \t]*\r?\n.*?```", re.DOTALL | re.IGNORECASE)
DATE_SUFFIX_RE = re.compile(r"_\d{8}[A-Za-z0-9]*$")  # hj8_fixed_k_10_20260921iaware -> hj8_fixed_k_10
SEPARATOR_CELL_RE = re.compile(r":?-{3,}:?")

DEFINITIONS = {
    "limit": "error_type == 'limit' (the 40-step limit), scored; only error_type == 'crash' is dropped",
    "tgc": "j10.a1_arm_episodes' tgc (j10.score_tgc: a scored failure is 0), per-task binary",
    "sgc": ("j10.a1_sgc_units [j10_report.py:2379-2400]: a (scenario, seed) unit passes iff every task "
            "of the scenario succeeded, scored only when all its tasks are non-crashed episodes; the "
            "rule of hj1_gate.scenario_goal_completion. Paired on shared units; scenario clusters"),
    "fenced_code": "the intervention text contains an opening ``` line, text and a closing ``` (FENCED_BLOCK_RE)",
    "chars": "len() of the intervention text (payload.correction), in characters",
    "interventions": ("every event_type == 'intervention' in the episode's last run_start segment "
                      "(b2.read_events), over the arm's non-crashed episodes"),
    "copy_rate_show": "b2_decomposition.copy_rate, the registered S definition, unchanged",
    "copy_rate_advice": ("b2's next-action rule, renderer and whitespace normalisation, with the "
                         "shown text widened to the advice text OR any ```python block inside it; "
                         "denominator every intervention"),
    "per_episode_wall_s": ("manifest.json created_at (written just before system.run, "
                           "src/sidekick/runner.py:369-388) to the run_end event's ts. Every other "
                           "event ts is AppWorld's freezegun clock (src/sidekick/replay.py:76)"),
    "planner_call_latency_s": ("usage.latency_s of live planner events (provider not 'cache', "
                               "n_calls >= 1); perf_counter runs under the same freezegun clock"),
}


# ---- paths ------------------------------------------------------------------
def refuse_path(path: Path) -> Optional[str]:
    """A refusal message if the path (as given or resolved) names held-out or J10 data."""
    texts = {str(path)}
    try:
        texts.add(str(Path(path).resolve()))
    except OSError:
        pass
    for text in sorted(texts):
        for marker in REFUSED_MARKERS:
            if marker in text:
                return f"refusing {path}: contains {marker!r} (dev only; held-out and J10 data are not read here)"
    return None


def _refuse_out(path: Path) -> Optional[str]:
    resolved = path.resolve()
    for root in b2.FORBIDDEN_OUT_ROOTS:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"refusing --out {path}: it is under {root}, which holds raw results (read-only)"
    return None


def _rel(path: Path) -> str:
    """A repo file as its repo-relative path, anything else as given."""
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


# ---- contrast objects -------------------------------------------------------
def contrast_object(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    metric: str,
    *,
    n_boot: int,
    seed: int,
    threshold_pp: float = 0.0,
) -> dict[str, Any]:
    """Paired left - right on `metric` (goal_pass | tgc): j10.a1_contrast plus its two-sided p."""
    field = j10.A1_METRIC_FIELDS[metric]
    cmp = j10.a1_contrast(left, right, field, n_boot=n_boot, seed=seed)
    scen, task = cmp["scenario"], cmp["task"]
    return {
        "metric": metric,
        "field": field,
        "diff_pp": scen["diff_pp"],
        "ci95_pp_scenario": scen["ci95_pp"],
        "ci95_pp_task": task["ci95_pp"],
        "p_two_sided": j10._p_two_sided(scen, threshold_pp / 100.0),
        "threshold_pp": threshold_pp,
        "n_pairs": cmp["n_pairs"],
        "n_clusters_scenario": scen["n_clusters"],
        "n_clusters_task": task["n_clusters"],
        "n_dropped_missing_field": cmp["n_dropped_missing_field"],
    }


def sgc_contrast_object(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    tasks: list[str],
    seeds: list[int],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """SGC paired on shared (scenario, seed) units, scored as j10.a1_sgc does [j10_report.py:2403-2431],
    with the same scenario cluster bootstrap and p as every other contrast. One value per
    (scenario, seed): a task clustering does not exist, so ci95_pp_task is None."""
    ul, unscored_l = j10.a1_sgc_units(left, tasks, seeds)
    ur, unscored_r = j10.a1_sgc_units(right, tasks, seeds)
    shared = sorted(set(ul) & set(ur))
    diffs = [ul[u] - ur[u] for u in shared]
    out: dict[str, Any] = {
        "metric": "sgc",
        "unit": "(scenario, seed); passes only if every task of the scenario succeeded",
        "diff_pp": None,
        "ci95_pp_scenario": None,
        "ci95_pp_task": None,
        "ci95_pp_task_note": "SGC is scenario-level: no task clustering exists",
        "p_two_sided": None,
        "threshold_pp": 0.0,
        "n_pairs": len(shared),
        "n_units_unscored_left": unscored_l,
        "n_units_unscored_right": unscored_r,
        "sgc_left": round(statistics.fmean(ul[u] for u in shared), 6) if shared else None,
        "sgc_right": round(statistics.fmean(ur[u] for u in shared), 6) if shared else None,
    }
    if not diffs:
        return out
    means = j10.cluster_bootstrap_means(diffs, [u[0] for u in shared], n_boot=n_boot, seed=seed)
    lo, hi = j10.percentile_ci(means)
    out.update(
        diff_pp=round(statistics.fmean(diffs) * 100, 2),
        ci95_pp_scenario=[round(lo * 100, 2), round(hi * 100, 2)],
        p_two_sided=j10.bootstrap_pvalue(means, 0.0, "two-sided"),
        n_clusters_scenario=len({u[0] for u in shared}),
    )
    return out


# ---- limits (R2.1, R2.2) ----------------------------------------------------
def limit_rates(arms: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """R2.1: j10.am1_limit_rates, re-keyed to this report's n / n_limit / rate."""
    return {label: {"n": r["n_scored"], "n_limit": r["n_limit"], "rate": r["limit_rate"]}
            for label, r in j10.am1_limit_rates(arms).items()}


def limit_split(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """R2.2: j10.am1_limit_split (A1 Amendment 1 §D2) on goal_pass, re-keyed. Either part's
    contribution is Σ d over its pairs / all pairs, so the two sum to the whole."""
    raw = j10.am1_limit_split(left, right, j10.A1_METRIC_FIELDS["goal_pass"], n_boot=n_boot, seed=seed)
    out: dict[str, Any] = {
        "label": SPLIT_LABEL,
        "metric": "goal_pass",
        "n_pairs": raw["n_pairs"],
        "n_limit_left": raw["n_limit_left"],
        "n_limit_right": raw["n_limit_right"],
        "status": raw["status"],
    }
    if raw["status"] != "ok":
        out["error"] = raw.get("error")
        return out

    def part(n: int, mean_key: str, contribution_key: str) -> dict[str, Any]:
        mean, contribution = raw[mean_key], raw[contribution_key]
        return {
            "n": n,
            "mean_diff_pp": mean["diff_pp"],
            "mean_diff_ci95_pp_scenario": mean["ci95_pp_scenario"],
            "mean_diff_ci95_pp_task": mean["ci95_pp_task"],
            "contribution_pp": contribution["diff_pp"],
            "contribution_ci95_pp_scenario": contribution["ci95_pp_scenario"],
            "contribution_ci95_pp_task": contribution["ci95_pp_task"],
        }

    out["either_limit"] = part(raw["n_limit_pairs"], "mean_on_limit_pairs", "contribution_limit_pairs")
    out["neither"] = part(raw["n_neither"], "mean_on_neither", "contribution_neither")
    whole = raw["all"]
    out["whole"] = {"diff_pp": whole["diff_pp"], "ci95_pp_scenario": whole["ci95_pp_scenario"],
                    "ci95_pp_task": whole["ci95_pp_task"]}
    parts = (out["either_limit"]["contribution_pp"], out["neither"]["contribution_pp"])
    out["contributions_sum_pp"] = None if None in parts else round(sum(parts), 2)
    return out


def limit_as_zero(
    left: dict[tuple[str, int], dict[str, Any]],
    right: dict[tuple[str, int], dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """R2.2 sensitivity: goal_pass of every limit episode set to 0 in both arms -- the zeroing of
    j10.am1_limit_as_zero (A1 Amendment 1 §D3) -- as a contrast object, so it keeps its p."""
    field = j10.A1_METRIC_FIELDS["goal_pass"]

    def zeroed(eps: dict[tuple[str, int], dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
        return {k: (dict(e, **{field: 0.0}) if e.get("error_type") == LIMIT else e) for k, e in eps.items()}

    return {"sensitivity": True, "decision_bearing": False,
            **contrast_object(zeroed(left), zeroed(right), "goal_pass", n_boot=n_boot, seed=seed)}


# ---- content (R2.3) ---------------------------------------------------------
def mean_block(values: list[float], clusters: dict[str, list[str]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """Mean of per-item values with a 95% percentile cluster-bootstrap CI per clustering.
    j10.cluster_bootstrap_means resamples whole clusters, so a share is Σ hits / Σ items."""
    out: dict[str, Any] = {"n": len(values), "mean": round(statistics.fmean(values), 6) if values else None}
    for name, labels in clusters.items():
        if not values:
            out[f"ci95_{name}"] = None
            continue
        lo, hi = j10.percentile_ci(j10.cluster_bootstrap_means(values, labels, n_boot=n_boot, seed=seed))
        out[f"ci95_{name}"] = [round(lo, 6), round(hi, 6)]
    return out


def _next_executor_action(events: list[dict[str, Any]], i: int) -> Optional[dict[str, Any]]:
    """b2.shown_action_rows' next action [b2_decomposition.py:543-549]: the first executor action
    after event i, and none if another intervention comes first."""
    for later in events[i + 1:]:
        if later.get("event_type") == "intervention":
            return None
        if later.get("event_type") == "action" and later.get("actor") == "executor":
            return later
    return None


def _copied(text: str, nxt: Optional[dict[str, Any]]) -> bool:
    """Does the executor's next action reproduce the text, or one ```python block inside it?"""
    if nxt is None:
        return False
    rendered = b2._render_action(nxt.get("payload") or {})
    if rendered is None:
        return False
    target = b2._normalise_ws(rendered)
    candidates = [text, *(m.group(0) for m in PYTHON_BLOCK_RE.finditer(text))]
    return any(b2._normalise_ws(c) == target for c in candidates)


def intervention_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per intervention of one episode segment: source, length, fenced code, copied."""
    rows: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        if ev.get("event_type") != "intervention":
            continue
        payload = ev.get("payload") or {}
        text = str(payload.get("correction") or "")
        rows.append({
            "step": ev.get("step"),
            "source": str(payload.get("source") or "advice"),
            "chars": len(text),
            "fenced": FENCED_BLOCK_RE.search(text) is not None,
            "fenced_python": PYTHON_BLOCK_RE.search(text) is not None,
            "copied": _copied(text, _next_executor_action(events, i)),
        })
    return rows


def content_block(
    label: str,
    event_paths: dict[tuple[str, int], Path],
    *,
    n_boot: int,
    seed: int,
) -> dict[str, Any]:
    """R2.3 / DEC-06: per arm, the share of interventions carrying fenced code, their length and
    the copy rate. The share's CI resamples scenarios (and, secondarily, tasks)."""
    n_missing = n_bad = n_with = 0
    flat: list[tuple[tuple[str, int], dict[str, Any]]] = []
    for key in sorted(event_paths):
        path = event_paths[key]
        if not path.is_file():
            n_missing += 1
            continue
        events, bad = b2.read_events(path)
        n_bad += bad
        rows = intervention_rows(events)
        n_with += bool(rows)
        flat.extend((key, row) for row in rows)
    fenced = [1.0 if row["fenced"] else 0.0 for _key, row in flat]
    share = mean_block(fenced, {"scenario": [scenario_of(k[0]) for k, _r in flat], "task": [k[0] for k, _r in flat]},
                       n_boot=n_boot, seed=seed)
    chars = [row["chars"] for _key, row in flat]
    out: dict[str, Any] = {
        "label": "EXPLORATORY (R2.3, ledger DEC-06)",
        "n_episodes": len(event_paths),
        "n_episodes_without_events": n_missing,
        "n_unparseable_event_lines": n_bad,
        "n_episodes_with_an_intervention": n_with,
        "n_interventions": len(flat),
        "n_by_source": dict(sorted(Counter(row["source"] for _key, row in flat).items())),
        "n_fenced_code": int(sum(fenced)),
        "share_fenced_code": {"share": share["mean"], "n_fenced": int(sum(fenced)), "n": share["n"],
                              "ci95_scenario": share["ci95_scenario"], "ci95_task": share["ci95_task"]},
        "n_fenced_python": sum(1 for _key, row in flat if row["fenced_python"]),
        "median_chars": statistics.median(chars) if chars else None,
        "mean_chars": round(statistics.fmean(chars), 2) if chars else None,
    }
    if label == SHOW_LABEL:
        cr = b2.copy_rate(event_paths)
        out["copy_rate"] = cr["copy_rate"]
        out["copy"] = {"definition": DEFINITIONS["copy_rate_show"],
                       **{k: cr[k] for k in ("n_shown", "n_followed_by_an_executor_action", "n_copied",
                                             "copy_rate_among_followed", "by_shown_kind")}}
    else:
        n_copied = sum(1 for _key, row in flat if row["copied"])
        out["copy_rate"] = round(n_copied / len(flat), 6) if flat else None
        out["copy"] = {"definition": DEFINITIONS["copy_rate_advice"], "n_copied": n_copied,
                       "n_copied_among_fenced_python": sum(1 for _k, r in flat if r["copied"] and r["fenced_python"])}
    return out


# ---- latency (G12) ----------------------------------------------------------
def _ts(value: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _manifest_start(path: Path) -> Optional[datetime]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return _ts(data.get("created_at")) if isinstance(data, dict) else None


def latency_block(event_paths: dict[tuple[str, int], Path]) -> dict[str, Any]:
    """Per-episode wall clock (median, mean) and per-planner-call latency (median). A part with
    no real-clock timestamp to read is {"status": "no_timestamps"} with the reason."""
    walls: list[float] = []
    n_no_start = n_no_end = n_negative = n_live = 0
    call_latency: list[float] = []
    for key in sorted(event_paths):
        path = event_paths[key]
        events = b2.read_events(path)[0] if path.is_file() else []
        start = _manifest_start(path.parent / "manifest.json")
        end = next((_ts(ev.get("ts")) for ev in reversed(events) if ev.get("event_type") == "run_end"), None)
        if start is None:
            n_no_start += 1
        elif end is None:
            n_no_end += 1
        elif end < start:
            n_negative += 1
        else:
            walls.append((end - start).total_seconds())
        for ev in events:
            usage = ev.get("usage") or {}
            if ev.get("actor") != "planner" or usage.get("provider") in (None, "cache") or not usage.get("n_calls"):
                continue
            n_live += 1
            lat = usage.get("latency_s")
            if isinstance(lat, (int, float)) and lat > 0:
                call_latency.append(float(lat))
    counts = {"n_episodes": len(event_paths), "n_without_manifest_start": n_no_start,
              "n_without_run_end": n_no_end, "n_end_before_start": n_negative}
    if walls:
        wall: dict[str, Any] = {"status": "ok", "n": len(walls), "median": round(statistics.median(walls), 3),
                                "mean": round(statistics.fmean(walls), 3), **counts,
                                "source": DEFINITIONS["per_episode_wall_s"]}
    else:
        wall = {"status": "no_timestamps", **counts, "source": DEFINITIONS["per_episode_wall_s"]}
    if call_latency:
        call: dict[str, Any] = {"status": "ok", "n_live_planner_events": n_live, "n": len(call_latency),
                                "n_zero_or_missing": n_live - len(call_latency),
                                "median": round(statistics.median(call_latency), 3)}
    else:
        call = {"status": "no_timestamps", "n_live_planner_events": n_live,
                "reason": ("every live planner event's ts is the frozen AppWorld clock and its "
                           "usage.latency_s is 0 or absent; no per-call timing was recorded")}
    call["source"] = DEFINITIONS["planner_call_latency_s"]
    return {"per_episode_wall_s": wall, "per_planner_call_latency_s": call}


# ---- no-op floor (R7.1) -----------------------------------------------------
def noop_floor(directory: Path, *, n_boot: int, seed: int) -> dict[str, Any]:
    """goal_pass, TGC and SGC means of a no-op arm (COMPLETE at step 0), with scenario CIs."""
    loaded = j10.load_arm_tree(directory)
    seeds = sorted({s for _t, s in loaded["runs"]})
    tasks = sorted({t for t, _s in loaded["runs"]})
    arm = j10.a1_arm_episodes("noop", loaded, tasks, seeds)
    eps = arm["episodes"]
    out: dict[str, Any] = {"campaign": str(directory), "present": not loaded["root_missing"], "seeds": seeds,
                           "n_tasks": len(tasks), "n_scored": arm["n_scored"], "n_crash": arm["n_crash"]}
    for metric in ("goal_pass", "tgc"):
        field = j10.A1_METRIC_FIELDS[metric]
        keys = [k for k in sorted(eps) if eps[k].get(field) is not None]
        out[metric] = mean_block([float(eps[k][field]) for k in keys],
                                 {"scenario": [scenario_of(k[0]) for k in keys]}, n_boot=n_boot, seed=seed)
    units, unscored = j10.a1_sgc_units(eps, tasks, seeds)
    order = sorted(units)
    out["sgc"] = {**mean_block([units[u] for u in order], {"scenario": [u[0] for u in order]},
                               n_boot=n_boot, seed=seed), "n_units_unscored": unscored}
    return out


# ---- census (R4.4) ----------------------------------------------------------
def _table_cells(line: str) -> list[str]:
    """Cells of one markdown table row, split on pipes outside backtick spans (`a|b` is one cell)."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    cells: list[str] = []
    buf: list[str] = []
    in_code = False
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and body[i + 1:i + 2] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf).strip())
    return cells


def ledger_rows(text: str) -> list[dict[str, str]]:
    """(claim_id, status) of every row of every claims table (a table whose header starts claim_id)."""
    rows: list[dict[str, str]] = []
    status_col: Optional[int] = None
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            status_col = None
            continue
        cells = _table_cells(line)
        if cells and cells[0] == "claim_id":
            status_col = cells.index("status") if "status" in cells else None
            continue
        if status_col is None or all(SEPARATOR_CELL_RE.fullmatch(c) for c in cells if c):
            continue
        rows.append({"claim_id": cells[0], "status": cells[status_col] if status_col < len(cells) else ""})
    return rows


def _status_text(status: str) -> str:
    return status.replace("*", "").replace("`", "").strip().lower()


def status_class(status: str) -> str:
    """registered | exploratory | other, from the status cell's leading word (emphasis stripped)."""
    text = _status_text(status)
    for name in ("registered", "exploratory"):
        if text.startswith(name):
            return name
    return "other"


def _arm_key(name: str, entry: dict[str, Any]) -> str:
    config = (entry.get("from_config") or {}).get("config_path")
    return Path(config).stem if config else DATE_SUFFIX_RE.sub("", name)


def census(index_path: Path, ledger_path: Path) -> dict[str, Any]:
    """R4.4: dev campaigns and distinct arms in the campaign index; ledger rows by status."""
    index = json.loads(index_path.read_text(encoding="utf-8"))
    camps: dict[str, dict[str, Any]] = index.get("campaigns") or {}
    dev = {n: c for n, c in camps.items() if c.get("present") and c.get("n_tasks") == DEV_N_TASKS}
    arms: dict[str, list[str]] = {}
    for name in sorted(dev):
        arms.setdefault(_arm_key(name, dev[name]), []).append(name)
    rows = ledger_rows(ledger_path.read_text(encoding="utf-8"))
    classes = Counter(status_class(r["status"]) for r in rows)
    other_words = Counter((re.findall(r"[a-z]+", _status_text(r["status"])) or ["(empty)"])[0]
                          for r in rows if status_class(r["status"]) == "other")
    return {
        "campaign_index": _rel(index_path),
        "index_scope": index.get("purpose"),
        "n_campaigns_in_index": len(camps),
        "n_not_present": sum(1 for c in camps.values() if not c.get("present")),
        "dev_rule": f"present and n_tasks == {DEV_N_TASKS} (the dev split)",
        "n_dev_campaigns": len(dev),
        "n_non_dev_present": sum(1 for n, c in camps.items() if c.get("present") and n not in dev),
        "arm_rule": "the config file's stem when the index records one, else the campaign name minus its _YYYYMMDD suffix",
        "n_distinct_dev_arms": len(arms),
        "dev_arms": arms,
        "ledger": {
            "path": _rel(ledger_path),
            "n_rows": len(rows),
            "status_rule": ("the status column of every table headed claim_id, cells split outside backtick "
                            "spans; the class is the cell's first word with ** and ` stripped"),
            "by_status": {k: classes.get(k, 0) for k in ("registered", "exploratory", "other")},
            "other_by_first_word": dict(sorted(other_words.items())),
        },
    }


# ---- multiplicity (R4.3) ----------------------------------------------------
def contrast_objects(tree: Any, path: tuple[str, ...] = ()) -> list[tuple[str, dict[str, Any]]]:
    """Every contrast object (a dict holding metric, diff_pp and p_two_sided) by dotted key path."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(tree, dict):
        if {"metric", "diff_pp", "p_two_sided"} <= tree.keys():
            found.append((".".join(path), tree))
        for key, value in tree.items():
            found.extend(contrast_objects(value, (*path, str(key))))
    elif isinstance(tree, list):
        for i, value in enumerate(tree):
            found.extend(contrast_objects(value, (*path, str(i))))
    return found


def by_fdr_family(
    report: dict[str, Any],
    depth_report: Optional[dict[str, Any]] = None,
    depth_source: Optional[str] = None,
    alpha: float = ALPHA,
) -> dict[str, Any]:
    """R4.3: Benjamini-Yekutieli (cluster_inference.by_fdr) over every goal_pass contrast object
    in this report and, if given, in unit S4-depth's report. One row per object; an object
    without a p is listed and left out of m. A report's own by_fdr block is never read."""
    entries: list[dict[str, Any]] = []
    for source, tree in ((PROTOCOL, report), (depth_source or "depth_report", depth_report)):
        if not isinstance(tree, dict):
            continue
        body = {k: v for k, v in tree.items() if k != "by_fdr"}
        for key, obj in contrast_objects(body):
            if obj.get("metric") == "goal_pass":
                entries.append({"id": key, "source": source, "diff_pp": obj.get("diff_pp"),
                                "p_two_sided": obj.get("p_two_sided")})
    usable = [i for i, e in enumerate(entries) if e["p_two_sided"] is not None]
    adjusted = dict(zip(usable, by_fdr([float(entries[i]["p_two_sided"]) for i in usable])))
    rows = [dict(e, p_by=adjusted.get(i), survives_0_05=None if i not in adjusted else bool(adjusted[i] <= alpha))
            for i, e in enumerate(entries)]
    return {
        "method": "Benjamini-Yekutieli, cluster_inference.by_fdr",
        "alpha": alpha,
        "decision_bearing": False,
        "family_rule": ("every contrast object with metric == 'goal_pass' in this report and in "
                        "--depth-report, each counted once; one without a p is listed and not in m"),
        "m": len(usable),
        "not_in_family": [e["id"] for i, e in enumerate(entries) if i not in adjusted],
        "rows": rows,
    }


# ---- report -----------------------------------------------------------------
def _campaign_counts(directory: Path) -> dict[str, Any]:
    loaded = j10.load_arm_tree(directory)
    runs = loaded["runs"]
    return {
        "campaign": directory.name,
        "path": str(directory),
        "present": not loaded["root_missing"],
        "n_results": len(runs),
        "n_crash": sum(1 for row in runs.values() if row.get("error_type") == CRASH),
        "by_seed": dict(sorted(Counter(str(s) for _t, s in runs).items())),
        "n_empty_files": len(loaded["empty_files"]),
        "n_unreadable": len(loaded["unreadable"]),
        "split_provenance": j10.a1_split_provenance(directory) if not loaded["root_missing"] else {},
    }


def build_report(
    *,
    results_root: Path = RESULTS_ROOT,
    arm_campaigns: Optional[dict[str, tuple[str, ...]]] = None,
    limit_campaigns: tuple[str, ...] = LIMIT_ONLY_CAMPAIGNS,
    n_boot: int = N_BOOT,
    seed: int = BOOTSTRAP_SEED,
    depth_report: Optional[dict[str, Any]] = None,
    depth_source: Optional[str] = None,
    noop_campaign: Optional[Path] = None,
    index_path: Path = CAMPAIGN_INDEX,
    ledger_path: Path = CLAIMS_LEDGER,
) -> tuple[dict[str, Any], int]:
    """The whole report and its exit code. Raises b2.PoolingError on a key twice in one arm."""
    campaigns = dict(arm_campaigns or ARM_CAMPAIGNS)
    seeds = list(SEEDS)
    pooled = {label: b2.load_pooled_arm(label, [results_root / n for n in names]) for label, names in campaigns.items()}
    tasks = j10.discover_tasks(pooled, seeds)
    arms = {label: j10.a1_arm_episodes(label, pooled[label], tasks, seeds) for label in campaigns}
    eps = {label: arm["episodes"] for label, arm in arms.items()}

    warnings: list[str] = []
    inputs_arms: dict[str, Any] = {}
    for label, names in campaigns.items():
        camps = [_campaign_counts(results_root / n) for n in names]
        for camp in camps:
            if not camp["present"]:
                warnings.append(f"arm {label}: campaign {camp['campaign']} is missing")
            wrong = {k: v for k, v in camp["split_provenance"].items() if k not in {"dev", "unrecorded"}}
            if wrong:
                warnings.append(f"arm {label}: campaign {camp['campaign']} records split {wrong}")
        inputs_arms[label] = {"campaigns": camps, "n_expected": arms[label]["n_expected"],
                              "n_scored": arms[label]["n_scored"], "n_crash": arms[label]["n_crash"],
                              "n_missing": arms[label]["n_missing"], "systems": arms[label]["systems_in_tree"]}
    missing_arm = any("is missing" in w for w in warnings)

    limit_arms = dict(arms)
    inputs_limit: dict[str, Any] = {}
    for name in limit_campaigns:
        directory = results_root / name
        loaded = j10.load_arm_tree(directory)
        c_seeds = sorted({s for _t, s in loaded["runs"]})
        c_tasks = sorted({t for t, _s in loaded["runs"]})
        limit_arms[name] = j10.a1_arm_episodes(name, loaded, c_tasks, c_seeds)
        inputs_limit[name] = _campaign_counts(directory)
        if loaded["root_missing"]:
            warnings.append(f"limit-rate campaign {name} is missing")

    metrics: dict[str, Any] = {}
    split: dict[str, Any] = {}
    as_zero: dict[str, Any] = {}
    for cid, (left, right) in CONTRASTS.items():
        l_eps, r_eps = eps[left], eps[right]
        metrics[cid] = {
            "definition": f"{left} - {right}",
            "goal_pass": contrast_object(l_eps, r_eps, "goal_pass", n_boot=n_boot, seed=seed),
            "tgc": contrast_object(l_eps, r_eps, "tgc", n_boot=n_boot, seed=seed),
            "sgc": sgc_contrast_object(l_eps, r_eps, tasks, seeds, n_boot=n_boot, seed=seed),
        }
        split[cid] = {"definition": f"{left} - {right}", **limit_split(l_eps, r_eps, n_boot=n_boot, seed=seed)}
        as_zero[cid] = {"definition": f"{left} - {right}", **limit_as_zero(l_eps, r_eps, n_boot=n_boot, seed=seed)}
        n_pairs = metrics[cid]["goal_pass"]["n_pairs"]
        if n_pairs != b2.EXPECTED_PAIRS:
            warnings.append(f"{cid}: {n_pairs} goal_pass pairs, not {b2.EXPECTED_PAIRS}")

    event_paths = {label: b2.s_event_paths([results_root / n for n in campaigns[label]], set(eps[label]))
                   for label in campaigns}
    content = {label: content_block(label, event_paths[label], n_boot=n_boot, seed=seed)
               for label in CONTENT_LABELS if label in campaigns}
    latency = {label: latency_block(event_paths[label]) for label in campaigns}

    report: dict[str, Any] = {
        "protocol": PROTOCOL,
        "label": "EXPLORATORY dev analyses for review F2/F4/F7; nothing here decides a registered verdict",
        "fix_rows": ["R2.1", "R2.2", "R2.3", "R4.3", "R4.4", "R7.1", "G12"],
        "status": "INCOMPLETE" if missing_arm else "COMPLETE",
        "warnings": warnings,
        "contrasts": {cid: f"{left} - {right}" for cid, (left, right) in CONTRASTS.items()},
        "limits": {"per_arm": limit_rates(limit_arms), "split": split, "as_zero": as_zero},
        "content": content,
        "metrics": metrics,
        "latency": latency,
        "noop_floor": None if noop_campaign is None else noop_floor(noop_campaign, n_boot=n_boot, seed=seed),
        "census": census(index_path, ledger_path),
        "inputs": {
            "results_root": str(results_root),
            "arms": inputs_arms,
            "limit_rate_campaigns": inputs_limit,
            "n_tasks_observed_union": len(tasks),
            "depth_report": depth_source,
            "noop_campaign": None if noop_campaign is None else str(noop_campaign),
        },
        "settings": {
            "n_boot": n_boot,
            "seed": seed,
            "seeds": seeds,
            "alpha": ALPHA,
            "expected_pairs": b2.EXPECTED_PAIRS,
            "clustering": "scenario (primary: every p and ci95_pp_scenario) and task (ci95_pp_task)",
            "interval": "95% percentile, j10.cluster_bootstrap_means / percentile_ci",
            "p_value": "j10.bootstrap_pvalue(scenario means, threshold, 'two-sided'): 2 x the smaller tail",
            "crash_convention": "error_type == 'crash' is dropped from every pair and counted in inputs",
            "definitions": DEFINITIONS,
        },
    }
    report["by_fdr"] = by_fdr_family(report, depth_report, depth_source)
    return report, (1 if missing_arm else 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J17 channel fixes (dev): review F2/F4/F7 rows R2.1-R2.3, R4.3, R4.4, R7.1.")
    p.add_argument("--out", type=Path, required=True, help="report JSON path")
    p.add_argument("--depth-report", type=Path, default=None,
                   help="unit S4-depth's report JSON; its goal_pass contrasts join the BY family")
    p.add_argument("--noop-campaign", type=Path, default=None, help="a no-op dev campaign directory (R7.1 floor)")
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    p.add_argument("--results-root", type=Path, default=RESULTS_ROOT,
                   help=f"root holding the campaign directories (default {RESULTS_ROOT})")
    return p


def _refused(reason: str) -> int:
    print(json.dumps({"protocol": PROTOCOL, "status": "REFUSED", "reason": reason}))
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    named = [args.out, args.results_root, args.depth_report, args.noop_campaign]
    named += [args.results_root / n for names in ARM_CAMPAIGNS.values() for n in names]
    named += [args.results_root / n for n in LIMIT_ONLY_CAMPAIGNS]
    for path in named:
        if path is not None and (reason := refuse_path(path)):
            return _refused(reason)
    if reason := _refuse_out(args.out):
        return _refused(reason)
    depth: Optional[dict[str, Any]] = None
    if args.depth_report is not None:
        try:
            depth = json.loads(args.depth_report.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return _refused(f"--depth-report {args.depth_report}: {type(exc).__name__}: {exc}")
        if not isinstance(depth, dict):
            return _refused(f"--depth-report {args.depth_report}: not a JSON object")
    try:
        report, code = build_report(
            results_root=args.results_root, n_boot=args.n_boot, seed=args.seed, depth_report=depth,
            depth_source=None if args.depth_report is None else _rel(args.depth_report),
            noop_campaign=args.noop_campaign,
        )
    except b2.PoolingError as exc:
        return _refused(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"protocol": PROTOCOL, "status": report["status"], "exit_code": code,
                      "warnings": report["warnings"], "by_fdr_m": report["by_fdr"]["m"], "json": str(args.out)},
                     indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
