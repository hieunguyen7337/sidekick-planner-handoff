#!/usr/bin/env python
"""J17 planning-literature analyses (dev): tailoring x plan, a termination census, the high-effort ceiling.

Brief ``campaign/workers/briefs/20260924_ana_planning_lit.md``. Dev only and exploratory: nothing
here decides a registered verdict.

A  PLANTAX  Does one external plan help a plan-trained (tailored) executor more than the base one
            (DiD1), and is the tailoring gap given a plan different from the gap given m executed
            planner actions (DiD2(m) = G_plan - G_act(m), m = 6, 9, 11)? Plus the zero-shot
            Qwen3-8B floor pair's plan gain as a third point.
B  TERM     Every non-crashed episode of each census arm classified, Fan-comparably, as
            no_handoff / limit / other / stopped_before_acting / completed_after_acting.
C  CEILHI   The luna planner alone at cap 81 with reasoning_effort high against the medium run on
            the same keys: quality, limit rates, per-episode cost and the high/medium cost ratios,
            and an exploratory re-reading of the prefix m = 11 non-inferiority against it.

Nothing statistical is new here; it is imported, so it cannot drift:
  - arms are b2_decomposition.load_pooled_arm (a key twice in one arm is an error), scored by
    j10_report.a1_arm_episodes (error_type == 'crash' is dropped and counted; 'limit' is scored);
  - paired and difference-in-differences series are j10.a1_paired_series / a1_did_series; their
    intervals are j10.a1_interval, the pairs cluster bootstrap over scenarios (primary) and tasks
    (secondary), percentile indices int(0.025 B) / int(0.975 B); p_two_sided is
    j10.bootstrap_pvalue (2 x the smaller tail) and p_signflip_two_sided is
    cluster_inference.registered_signflip over scenarios at the same threshold;
  - census shares resample whole clusters with j16_robustness.bootstrap_multi (the draw sequence
    of j10.cluster_bootstrap_means); cost ratios are j16_robustness.cost_contrast;
  - hosted calls and USD are j8_frontier.summarise_arm rows priced by
    j12_cost_axes.price_arm_episodes against configs/cost/prices_2026-09.yaml, as
    j17_depth_fixes prices them; token sums are j12_cost_axes.extract_events_usages records;
  - events are b2_decomposition.read_events (the episode's last run_start segment).

What an "action" is. The loop writes an agent's move as event_type 'action': the executor's at
src/sidekick/systems/loop.py:598-605 (actor 'executor', payload.kind CODE / REPORT / ASK_PLANNER /
COMPLETE), a planner-driven move at loop.py:998-1005 and a takeover move at loop.py:854-861 (both
actor 'planner'). Only CODE and COMPLETE reach env.step (loop.py:1141-1143) and COMPLETE ends the
episode (loop.py:1169-1170), so "acted" means at least one CODE action by the acting actor: the
executor, except in planner_alone arms, where the planner is the only actor. A prefix arm's
replayed actions are not logged in its own events (src/sidekick/systems/prefix_handoff.py:183-189
writes the handoff `report`); only actions after the handoff (step > effective_m) are counted.

Exit codes
  0  report written
  1  report written, but a campaign directory is missing (named in `warnings`)
  2  refused: a held-out or J10/J11/J12 path; an output under /scratch; a key twice in one arm
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import b2_decomposition as b2  # noqa: E402
from scripts.analysis import cluster_inference  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402  (the module b2 uses)
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

Key = tuple  # (task_id, seed)

PROTOCOL = "J17-planning-lit"
RESULTS_ROOT = j10.RAW_RESULTS_ROOT
PRICES = REPO_ROOT / "configs" / "cost" / "prices_2026-09.yaml"
N_BOOT = 10_000
BOOTSTRAP_SEED = 20260924
NI_MARGIN_PP = 7.00
CRASH = "crash"
LIMIT = j10.A1_LIMIT_ERROR  # "limit": the 40-step limit, a scored outcome
DEV_N_TASKS = j10.A1_SPLIT_N_TASKS["dev"]  # 57
# j17_channel_fixes.refuse_path's held-out markers, verbatim. Its third marker, the substring
# "j10_", is narrowed here to a path component and widened to J11 / J12 (brief: never any
# j10_* / j11_* / j12_* campaign): the substring would refuse every hj12_* dev campaign.
HELDOUT_MARKERS = ("test_normal", "test_challenge")
REFUSED_CAMPAIGN_RE = re.compile(r"^j1[0-2]_")
ACTED_KIND = "CODE"
CATEGORIES = ("no_handoff", "limit", "other", "stopped_before_acting", "completed_after_acting")
METRICS = (("goal_pass", "goal_pass_rate"), ("tgc", "tgc"))
DEPTHS = (6, 9, 11)


def _arm(campaigns: tuple[str, ...], seeds: tuple[int, ...], role: str) -> dict[str, Any]:
    """role: 'executor' (the executor acts), 'prefix' (it acts after a replayed handoff) or
    'planner' (planner_alone: the planner is the only actor)."""
    return {"campaigns": tuple(campaigns), "seeds": tuple(seeds), "role": role}


S12, S123 = (1, 2), (1, 2, 3)
ARMS: dict[str, dict[str, Any]] = {
    # A: tailored (sft_b_plus) and base granite executors, with and without one luna plan.
    "exec_alone_bplus": _arm(("hj8_executor_alone_bplus_20260919",), S12, "executor"),
    "sft_plan_bplus": _arm(("hj8_sft_plan_bplus_20260921iaware",), S12, "executor"),
    "exec_alone_base": _arm(("hj1r_exec8b_20260916",), S12, "executor"),
    "prompt_only_base": _arm(("hj1r_prompt_only_20260916",), S12, "executor"),
    # A sensitivity: the plan arm of the executor-alone arm's own adapter build (ledger ADV-FC-02).
    "sft_plan_bplus_0919": _arm(("hj8_sft_plan_bplus_20260919",), S12, "executor"),
    # A: the action channel, tailored (TAILOR-01/04/07's hj12) and untailored (hj13 zero-shot).
    **{f"prefix_bplus_m{m}": _arm((f"hj12_prefix_m{m}_20260923",), S12, "prefix") for m in DEPTHS},
    **{f"prefix_zs_m{m}": _arm((f"hj13_prefix_zs_m{m}_20260923",), S12, "prefix") for m in DEPTHS},
    # A3 / B: the zero-shot Qwen3-8B floor pair behind ledger QWEN-03.
    "qwen_exec_alone": _arm(("hj15_executor_alone_zsq_20260923",), S12, "executor"),
    "qwen_prompt_only": _arm(("hj15_prompt_only_zsq_20260923",), S12, "executor"),
    # B only.
    "noop": _arm(("dev_noop_complete_20260924",), S12, "executor"),
    "advise_k10": _arm(("hj12_advise_fixed_k_10_fullctx_20260923",), S12, "executor"),
    "takeover_k10": _arm(("hj12_takeover_fixed_k_10_20260923",), S12, "executor"),
    "advise_k10_neutral": _arm(b2.ARM_CAMPAIGNS["N"], S123, "executor"),  # ledger DEC-01
    "show_k10": _arm(b2.ARM_CAMPAIGNS["S"], S123, "executor"),  # ledger DEC-01
    **{f"prefix_c81_{rx}_m{m}": _arm((f"hj17_prefix_c81_{rx}_m{m}_20260923", f"hj18_prefix_c81s3_{rx}_m{m}_20260924"),
                                     S123, "prefix")
       for rx in ("bplus", "zs") for m in DEPTHS},
    # B and C: the planner alone at cap 81, medium effort (ledger CEIL-07; HO-NI pools seed 3) and high.
    "planner_alone_c81_medium": _arm(("hj13_planner_alone_cap81_20260923", "hj13_planner_alone_cap81_seed3_20260924"),
                                     S123, "planner"),
    "planner_alone_c81_high": _arm(("dev_planner_alone_cap81_high_20260924",), S12, "planner"),
}

PLANTAX_CORE = ("exec_alone_bplus", "sft_plan_bplus", "exec_alone_base", "prompt_only_base",
                *(f"prefix_bplus_m{m}" for m in DEPTHS), *(f"prefix_zs_m{m}" for m in DEPTHS))
# A 2-tuple is left - right (j10.a1_paired_series); a 4-tuple is (a - b) - (c - d) (j10.a1_did_series).
PLANTAX_CONTRASTS: dict[str, tuple[str, ...]] = {
    "plan_gain_tailored": ("sft_plan_bplus", "exec_alone_bplus"),
    "plan_gain_base": ("prompt_only_base", "exec_alone_base"),
    "did1": ("sft_plan_bplus", "exec_alone_bplus", "prompt_only_base", "exec_alone_base"),
    "g_plan": ("sft_plan_bplus", "prompt_only_base"),
    **{f"g_act_m{m}": (f"prefix_bplus_m{m}", f"prefix_zs_m{m}") for m in DEPTHS},
    **{f"did2_m{m}": ("sft_plan_bplus", "prompt_only_base", f"prefix_bplus_m{m}", f"prefix_zs_m{m}") for m in DEPTHS},
}
SAME_BUILD_CONTRASTS: dict[str, tuple[str, ...]] = {
    "plan_gain_tailored_same_build": ("sft_plan_bplus_0919", "exec_alone_bplus"),
    "did1_same_build": ("sft_plan_bplus_0919", "exec_alone_bplus", "prompt_only_base", "exec_alone_base"),
}
QWEN_CONTRAST = ("qwen_prompt_only", "qwen_exec_alone")
PLAN_IDENTITY_PAIRS = (("sft_plan_bplus", "prompt_only_base"), ("sft_plan_bplus_0919", "prompt_only_base"),
                       ("qwen_prompt_only", "prompt_only_base"))
CENSUS_ARMS = ("noop", "exec_alone_base", "exec_alone_bplus", "prompt_only_base", "sft_plan_bplus",
               "advise_k10", "takeover_k10", "advise_k10_neutral", "show_k10",
               *(f"prefix_c81_{rx}_m{m}" for rx in ("bplus", "zs") for m in DEPTHS),
               "qwen_exec_alone", "qwen_prompt_only", "planner_alone_c81_medium", "planner_alone_c81_high")
HIGH, MEDIUM = "planner_alone_c81_high", "planner_alone_c81_medium"
CEILHI_SEEDS = S12  # D3 has no seed 3
NI_ARMS = ("prefix_c81_bplus_m11", "prefix_c81_zs_m11")
COST_AXES = ("hosted_calls_per_episode", "input_tokens", "cached_input_tokens", "output_tokens",
             "reasoning_output_tokens", "usd_per_episode")
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")

# The ledger rows whose campaigns this report names: the report value is recomputed from the arm.
LEDGER_CHECKS: tuple[dict[str, Any], ...] = (
    *({"ledger": ledger, "arm": f"prefix_{rx}_m{m}",
       "report": f"campaign/results/hj13_receiver_contrast_m{m}_20260923.report.json",
       "key": f"arms.prefix_m{m}_{name}.goal_pass_all", "seeds": S12}
      for ledger, m in (("TAILOR-01", 6), ("TAILOR-04", 9), ("TAILOR-07", 11))
      for rx, name in (("bplus", "tailored"), ("zs", "zeroshot"))),
    {"ledger": "QWEN-03", "arm": "qwen_exec_alone", "report": "campaign/results/hj15_qwen_curve_20260923.report.json",
     "key": "arms.qwen_executor_alone.goal_pass_all", "seeds": S12},
    {"ledger": "QWEN-03", "arm": "qwen_prompt_only", "report": "campaign/results/hj15_qwen_curve_20260923.report.json",
     "key": "arms.qwen_plan_only.goal_pass_all", "seeds": S12},
    {"ledger": "CEIL-07", "arm": MEDIUM, "report": "campaign/results/hj13_ceiling_cap25_vs_cap81_20260923.report.json",
     "key": "arms.ceiling_cap81.goal_pass_all", "seeds": S12},
    {"ledger": "DEC-01", "arm": "advise_k10_neutral", "report": "campaign/results/b2_decomposition_20260923.report.json",
     "key": "arms.N.goal_pass_mean", "seeds": S123},
    {"ledger": "DEC-01", "arm": "show_k10", "report": "campaign/results/b2_decomposition_20260923.report.json",
     "key": "arms.S.goal_pass_mean", "seeds": S123},
)
LEDGER_MATCH_TOL = 6e-7  # the reports round means to 6 dp

DEFINITIONS = {
    "action": ("an event_type 'action' of the acting actor (loop.py:598-605 executor, :998-1005 planner "
               "driver); acting actor = executor, or planner in planner_alone arms"),
    "acted": ("at least one action with payload.kind == 'CODE' (CODE and COMPLETE reach env.step, "
              "loop.py:1141-1143; COMPLETE ends the episode, loop.py:1169-1170)"),
    "after_handoff": "prefix arms: only actions with step > the handoff report's effective_m",
    "categories": ("first rule that applies: no_handoff (prefix arm, handoff_occurred not true); limit "
                   "(error_type == 'limit'); other (any other non-null error_type, e.g. parse_error); "
                   "stopped_before_acting (clean end, zero CODE actions); completed_after_acting (clean "
                   "end, >= 1 CODE action). Crashes are dropped before classification"),
    "handoff_flag": ("handoff_occurred of the last `report` event carrying that key (the prefix system's "
                     "report, prefix_handoff.py:183-189); an executor REPORT action also writes a `report` "
                     "event, without the key"),
    "plan_source": ("first `plan` event: usage.provider 'cache' = replayed, from usage.raw.cached_from's "
                    "campaign; any other provider = live"),
    "plan_identity": "sha256 of the first plan event's payload.packet, canonical JSON (sort_keys)",
    "ni_reading": "ceiling - arm; holds iff round(scenario upper bound, 2) < +7.00, else fails",
}


# ---- paths ------------------------------------------------------------------
def refuse_path(path: Path | str) -> Optional[str]:
    """A refusal message if the path (as given or resolved) names held-out data or a J10/J11/J12 campaign."""
    texts = {str(path)}
    try:
        texts.add(str(Path(path).resolve()))
    except OSError:
        pass
    for text in sorted(texts):
        for marker in HELDOUT_MARKERS:
            if marker in text:
                return f"refusing {path}: contains {marker!r} (dev only; held-out data are not read here)"
        for part in Path(text).parts:
            if REFUSED_CAMPAIGN_RE.match(part):
                return f"refusing {path}: {part!r} is a J10/J11/J12 campaign (never read here)"
    return None


def refuse_out(path: Path) -> Optional[str]:
    """An output under b2.FORBIDDEN_OUT_ROOTS (/scratch, which holds raw results) is refused."""
    resolved = Path(path).resolve()
    for root in b2.FORBIDDEN_OUT_ROOTS:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"refusing --out {path}: it is under {root}, which holds raw results (read-only)"
    return None


def _rel(path: Path | str) -> str:
    try:
        return str(Path(path).relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _campaign_of(path_text: Any, depth: int) -> Optional[str]:
    """The campaign directory name `depth` levels above a recorded path (None if absent)."""
    if not path_text:
        return None
    parents = Path(str(path_text)).parents
    return parents[depth].name if len(parents) > depth else None


# ---- one episode --------------------------------------------------------------
def episode_facts(events: list[dict[str, Any]], role: str) -> dict[str, Any]:
    """Handoff, action counts, plan source and adapter of one episode's last run_start segment."""
    actor = "planner" if role == "planner" else "executor"
    handoff: Optional[bool] = None
    j10_flag: Optional[bool] = None
    effective_m: Optional[int] = None
    source_campaign: Optional[str] = None
    for ev in events:
        payload = ev.get("payload")
        if ev.get("event_type") != "report" or not isinstance(payload, dict):
            continue
        value = payload.get("handoff_occurred")
        j10_flag = None if value is None else bool(value)  # j10._last_report_handoff's reading
        if "handoff_occurred" in payload:
            handoff = None if value is None else bool(value)
            effective_m = None if payload.get("effective_m") is None else int(payload["effective_m"])
            source_campaign = None if not payload.get("source_campaign") else Path(str(payload["source_campaign"])).name
    after = effective_m if role == "prefix" else None
    kinds: Counter[str] = Counter()
    adapters: Counter[str] = Counter()
    for ev in events:
        usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else {}
        if ev.get("actor") == "executor" and ev.get("event_type") == "action" and usage:
            lora = (usage.get("raw") or {}).get("lora_name") if isinstance(usage.get("raw"), dict) else None
            adapters[f"{usage.get('model')}|lora={lora}"] += 1
        if ev.get("event_type") != "action" or ev.get("actor") != actor:
            continue
        if after is not None and int(ev.get("step") or 0) <= after:
            continue
        kinds[str((ev.get("payload") or {}).get("kind"))] += 1
    plan = next((ev for ev in events if ev.get("event_type") == "plan"), None)
    plan_source = plan_hash = plan_effort = None
    if plan is not None:
        usage = plan.get("usage") if isinstance(plan.get("usage"), dict) else {}
        provider = usage.get("provider")
        if provider == "cache":
            cached = (usage.get("raw") or {}).get("cached_from") if isinstance(usage.get("raw"), dict) else None
            plan_source = f"replayed:{_campaign_of(cached, 3)}"
        else:
            plan_source = f"live:{provider}"
        payload = plan.get("payload") if isinstance(plan.get("payload"), dict) else {}
        packet = payload.get("packet")
        if packet is not None:
            plan_hash = hashlib.sha256(json.dumps(packet, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        plan_effort = payload.get("model_reasoning_effort")
    start = next((ev for ev in events if ev.get("event_type") == "run_start"), None)
    limits = ((start or {}).get("payload") or {}).get("limits") or {}
    return {
        "acting_actor": actor,
        "handoff_occurred": handoff,
        "handoff_flag_j10_reader": j10_flag,
        "effective_m": effective_m,
        "prefix_source_campaign": source_campaign,
        "n_actions": sum(kinds.values()),
        "n_acted": kinds[ACTED_KIND],
        "action_kinds": dict(sorted(kinds.items())),
        "executor_adapters": dict(sorted(adapters.items())),
        "plan_source": plan_source,
        "plan_hash": plan_hash,
        "plan_effort": plan_effort,
        "max_planner_calls": limits.get("max_planner_calls"),
        "per_step_timeout_s": limits.get("per_step_timeout_s"),
    }


def classify(facts: dict[str, Any], error_type: Optional[str], role: str) -> str:
    """One of CATEGORIES, first rule that applies (DEFINITIONS['categories'])."""
    if role == "prefix" and facts.get("handoff_occurred") is not True:
        return "no_handoff"
    if error_type == LIMIT:
        return "limit"
    if error_type is not None:
        return "other"
    return "stopped_before_acting" if facts.get("n_acted", 0) == 0 else "completed_after_acting"


def manifest_provenance(manifest: Any) -> dict[str, Any]:
    """created_at plus the runner's provenance block (absent in campaigns older than X16)."""
    man = manifest if isinstance(manifest, dict) else {}
    prov = man.get("provenance") if isinstance(man.get("provenance"), dict) else {}
    return {
        "created_at": man.get("created_at"),
        "git_sha": prov.get("git_sha"),
        "git_dirty": prov.get("git_dirty"),
        "config_path": None if not prov.get("config_path") else _rel(prov["config_path"]),
        "lora_name": prov.get("lora_name"),
        "planner_reasoning_effort": prov.get("planner_reasoning_effort"),
        "split": prov.get("split"),
    }


def episode_record(row: dict[str, Any], events_path: Optional[Path], role: str) -> dict[str, Any]:
    """episode_facts + classification + manifest provenance for one scored episode."""
    events: list[dict[str, Any]] = []
    bad = 0
    has_events = events_path is not None and events_path.is_file()
    if has_events:
        events, bad = b2.read_events(events_path)
    rec = episode_facts(events, role)
    rec.update(
        steps=row.get("steps"),
        error_type=row.get("error_type"),
        has_events=has_events,
        n_unparseable_event_lines=bad,
        provenance=manifest_provenance(_read_json(events_path.parent / "manifest.json") if events_path else None),
    )
    rec["category"] = classify(rec, row.get("error_type"), role)
    return rec


# ---- one arm ------------------------------------------------------------------
def load_arm(label: str, spec: dict[str, Any], results_root: Path) -> dict[str, Any]:
    """Pooled result rows scored by j10.a1_arm_episodes, plus one record per scored episode."""
    dirs = [Path(results_root) / c for c in spec["campaigns"]]
    loaded = b2.load_pooled_arm(label, dirs)
    seeds = [int(s) for s in spec["seeds"]]
    tasks = sorted({t for t, s in loaded["runs"] if s in seeds})
    arm = j10.a1_arm_episodes(label, loaded, tasks, seeds)
    records: dict[Key, dict[str, Any]] = {}
    campaigns: list[dict[str, Any]] = []
    for directory, blob in zip(dirs, loaded["campaigns"]):
        paths = b2.s_event_paths([directory], set(arm["episodes"]))
        for key, path in paths.items():
            records[key] = dict(episode_record(loaded["runs"][key], path, spec["role"]), campaign=directory.name)
        own = j10.load_arm_tree(directory)["runs"]  # per-campaign crash count; the pool does not keep origins
        campaigns.append({
            "campaign": directory.name,
            "present": blob["present"],
            "n_results": blob["n_results"],
            "by_seed": blob["by_seed"],
            "n_scored": len(paths),
            "n_crash": sum(1 for (_t, s), r in own.items() if s in seeds and r.get("error_type") == CRASH),
            "split_provenance": blob["split_provenance"],
        })
    for key in arm["episodes"]:
        if key not in records:  # a scored result without an events file beside it
            records[key] = dict(episode_record(loaded["runs"][key], None, spec["role"]), campaign=None)
    summary = {k: v for k, v in arm.items() if k != "episodes"}
    return {"label": label, "spec": spec, "episodes": arm["episodes"], "records": records,
            "summary": summary, "campaigns": campaigns, "n_tasks": len(tasks)}


def _counter(values: list[Any]) -> dict[str, int]:
    return dict(sorted(Counter("unrecorded" if v is None else str(v) for v in values).items()))


def provenance_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """What one campaign's scored episodes recorded about how they were produced."""
    prov = [r["provenance"] for r in records]
    created = sorted(p["created_at"] for p in prov if p.get("created_at"))
    adapters: Counter[str] = Counter()
    for r in records:
        for name in r.get("executor_adapters") or {}:
            adapters[name] += 1  # episodes, not calls
    return {
        "n_episodes": len(records),
        "created_at_first": created[0] if created else None,
        "created_at_last": created[-1] if created else None,
        "git_sha": _counter([p.get("git_sha") for p in prov]),
        "git_dirty": _counter([p.get("git_dirty") for p in prov]),
        "config_path": _counter([p.get("config_path") for p in prov]),
        "planner_reasoning_effort": _counter([p.get("planner_reasoning_effort") for p in prov]),
        "split": _counter([p.get("split") for p in prov]),
        "executor_adapter_episodes": dict(sorted(adapters.items())),
        "plan_source": _counter([r.get("plan_source") or "no_plan_event" for r in records]),
        "plan_effort_recorded": _counter([r.get("plan_effort") for r in records if r.get("plan_source")]),
        "prefix_source_campaign": _counter([r.get("prefix_source_campaign") for r in records]),
        "max_planner_calls": _counter([r.get("max_planner_calls") for r in records]),
        "per_step_timeout_s": _counter([r.get("per_step_timeout_s") for r in records]),
    }


def arm_provenance(loaded_arm: dict[str, Any]) -> dict[str, Any]:
    by_campaign: dict[str, list[dict[str, Any]]] = {}
    for rec in loaded_arm["records"].values():
        by_campaign.setdefault(str(rec.get("campaign")), []).append(rec)
    return {c: provenance_summary(recs) for c, recs in sorted(by_campaign.items())}


# ---- inference --------------------------------------------------------------
def _pp(x: Optional[float]) -> Optional[float]:
    return None if x is None else 100.0 * x


def printed_pp(x: Optional[float]) -> Optional[str]:
    """Two decimals with an explicit sign, the ledger's printed form for pp."""
    return None if x is None else f"{round(x, 2):+.2f}"


def contrast_object(series: dict[str, Any], metric: str, *, n_boot: int, seed: int,
                    threshold_pp: float = 0.0) -> dict[str, Any]:
    """Mean of the per-key series with j10.a1_interval over scenarios and tasks, the two-sided
    bootstrap p at threshold_pp and the registered sign-flip p beside it. Unrounded; *_pp in pp."""
    thr = threshold_pp / 100.0
    out: dict[str, Any] = {"metric": metric, "diff_pp": None, "ci95_pp_scenario": None, "ci95_pp_task": None,
                           "p_two_sided": None, "threshold_pp": float(threshold_pp), "n_pairs": len(series["diffs"])}
    if not series["diffs"]:
        return out
    for unit in ("scenario", "task"):
        iv = j10.a1_interval(series, unit, n_boot=n_boot, seed=seed)
        out["diff_pp"] = _pp(iv["point"])
        out[f"ci95_pp_{unit}"] = [_pp(iv["lo"]), _pp(iv["hi"])]
        out["p_two_sided" if unit == "scenario" else "p_two_sided_task"] = j10.bootstrap_pvalue(
            iv["_means"], thr, "two-sided")
        out[f"n_clusters_{unit}"] = iv["n_clusters"]
    sf = cluster_inference.registered_signflip(series["diffs"], [scenario_of(k[0]) for k in series["keys"]],
                                               threshold=thr, alternative="two-sided", seed=seed)
    out["p_signflip_two_sided"] = sf["p"]
    out["signflip_method"] = sf["method"]
    out["printed"] = {
        "diff_pp": printed_pp(out["diff_pp"]),
        "ci95_pp_scenario": [printed_pp(v) for v in out["ci95_pp_scenario"]],
        "ci95_pp_task": [printed_pp(v) for v in out["ci95_pp_task"]],
        "p_two_sided": f"{out['p_two_sided']:.4f}",
        "p_signflip_two_sided": f"{sf['p']:.4f}",
    }
    return out


def combo_series(eps: dict[str, dict[Key, dict[str, Any]]], labels: tuple[str, ...], field: str,
                 keys: set[Key]) -> dict[str, Any]:
    """left - right (2 labels) or (a - b) - (c - d) (4 labels), on `keys` only."""
    arms = [{k: v for k, v in eps[label].items() if k in keys} for label in labels]
    if len(labels) == 2:
        return j10.a1_paired_series(arms[0], arms[1], field)
    if len(labels) == 4:
        return j10.a1_did_series(arms, field)
    raise ValueError(f"a contrast takes 2 or 4 arms, got {labels}")


def definition(labels: tuple[str, ...]) -> str:
    if len(labels) == 2:
        return f"{labels[0]} - {labels[1]}"
    return f"({labels[0]} - {labels[1]}) - ({labels[2]} - {labels[3]})"


def contrast_entry(eps: dict[str, dict[Key, dict[str, Any]]], labels: tuple[str, ...], keys: set[Key], *,
                   n_boot: int, seed: int, threshold_pp: float = 0.0) -> dict[str, Any]:
    """Both metrics of one contrast, each with the arm means on its own pairs."""
    out: dict[str, Any] = {"definition": definition(labels)}
    for metric, field in METRICS:
        series = combo_series(eps, labels, field, keys)
        obj = contrast_object(series, metric, n_boot=n_boot, seed=seed, threshold_pp=threshold_pp)
        obj["means_on_pairs"] = {label: (statistics.fmean(float(eps[label][k][field]) for k in series["keys"])
                                         if series["keys"] else None) for label in dict.fromkeys(labels)}
        obj["n_dropped_missing_field"] = series["n_dropped_missing_field"]
        out[metric] = obj
    return out


def scored_keys(eps: dict[Key, dict[str, Any]]) -> set[Key]:
    """Keys whose goal_pass and TGC are both scored (crashes are already out)."""
    return {k for k, e in eps.items() if all(e.get(f) is not None for _m, f in METRICS)}


def common_keys(eps: dict[str, dict[Key, dict[str, Any]]], labels: tuple[str, ...]) -> set[Key]:
    keys: Optional[set[Key]] = None
    for label in labels:
        ks = scored_keys(eps[label])
        keys = ks if keys is None else keys & ks
    return keys or set()


def plan_identity(left: dict[Key, dict[str, Any]], right: dict[Key, dict[str, Any]], keys: set[Key]) -> dict[str, Any]:
    """Did the two arms receive the same plan packet on each key?"""
    same = differ = missing = 0
    examples: list[str] = []
    for k in sorted(keys):
        a, b = (left.get(k) or {}).get("plan_hash"), (right.get(k) or {}).get("plan_hash")
        if a is None or b is None:
            missing += 1
        elif a == b:
            same += 1
        else:
            differ += 1
            if len(examples) < 5:
                examples.append(f"{k[0]}/{k[1]}")
    return {"n_keys": len(keys), "n_identical": same, "n_differ": differ, "n_missing_plan": missing,
            "differ_examples": examples}


def ni_reading(ci_pp: Optional[list[float]], margin_pp: float = NI_MARGIN_PP) -> Optional[str]:
    """ceiling - arm: non-inferior iff the upper bound, rounded to 2 dp, is below +margin."""
    if not ci_pp or ci_pp[1] is None:
        return None
    return "holds" if round(float(ci_pp[1]), 2) < margin_pp else "fails"


# ---- A: tailoring x plan ------------------------------------------------------
def plantax_section(arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    eps = {label: a["episodes"] for label, a in arms.items()}
    records = {label: a["records"] for label, a in arms.items()}
    keys = common_keys(eps, PLANTAX_CORE)
    contrasts = {cid: contrast_entry(eps, labels, keys, n_boot=n_boot, seed=seed)
                 for cid, labels in PLANTAX_CONTRASTS.items()}
    out: dict[str, Any] = {
        "label": "EXPLORATORY (planning literature: tailoring x plan)",
        "pairing": {"rule": "keys non-crashed with goal_pass and TGC scored in every PLANTAX_CORE arm",
                    "core_arms": list(PLANTAX_CORE), "n_keys": len(keys),
                    "seeds": sorted({k[1] for k in keys}), "n_tasks": len({k[0] for k in keys})},
        "contrasts": contrasts,
        "arm_means_on_keys": {label: {m: (statistics.fmean(float(eps[label][k][f]) for k in keys) if keys else None)
                                      for m, f in METRICS} for label in PLANTAX_CORE},
    }
    if "sft_plan_bplus_0919" in eps:
        sb_keys = keys & scored_keys(eps["sft_plan_bplus_0919"])
        out["sensitivity_same_build"] = {
            "why": ("exec_alone_bplus exists only as the 20260919 adapter build and sft_plan_bplus is the "
                    "iaware build (ledger ADV-FC-02), so plan_gain_tailored and did1 mix a build change "
                    "into the plan gain; these rows use the 20260919 sft_plan run instead"),
            "n_keys": len(sb_keys),
            **{cid: contrast_entry(eps, labels, sb_keys, n_boot=n_boot, seed=seed)
               for cid, labels in SAME_BUILD_CONTRASTS.items()},
        }
    if all(label in eps for label in QWEN_CONTRAST):
        q_keys = common_keys(eps, QWEN_CONTRAST)
        a, b = eps[QWEN_CONTRAST[0]], eps[QWEN_CONTRAST[1]]
        out["qwen_floor"] = {
            "why": "ledger QWEN-03's zero-shot Qwen3-8B floor pair: the plan gain as a third point, no DiD",
            "n_keys": len(q_keys),
            "plan_gain": contrast_entry(eps, QWEN_CONTRAST, q_keys, n_boot=n_boot, seed=seed),
            "n_keys_goal_pass_identical": sum(1 for k in q_keys if a[k]["goal_pass_rate"] == b[k]["goal_pass_rate"]),
        }
    out["plan_identity"] = {f"{l} vs {r}": plan_identity(records[l], records[r], keys & set(records[l]) & set(records[r]))
                            for l, r in PLAN_IDENTITY_PAIRS if l in records and r in records}
    return out


# ---- B: termination census ------------------------------------------------------
def census_block(records: dict[Key, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """Counts and shares (whole-cluster bootstrap, both clusterings) of CATEGORIES, with medians."""
    keys = sorted(records)
    k_all = len(CATEGORIES)
    comps = {k: tuple(1.0 if records[k]["category"] == c else 0.0 for c in CATEGORIES) + (1.0,) for k in keys}
    stats = {c: j16.ratio(i, k_all) for i, c in enumerate(CATEGORIES)}
    boots = {unit: j16.bootstrap_multi(comps, stats, unit, seed, n_boot) for unit in ("scenario", "task")}
    counts = Counter(records[k]["category"] for k in keys)
    shares: dict[str, Any] = {}
    for c in CATEGORIES:
        point = boots["scenario"]["stats"][c]["point"]
        shares[c] = {"n": counts.get(c, 0), "share": point,
                     "ci95_scenario": boots["scenario"]["stats"][c]["ci95"],
                     "ci95_task": boots["task"]["stats"][c]["ci95"],
                     "printed": None if point is None else f"{point:.4f}"}
    steps = [float(records[k]["steps"]) for k in keys if records[k].get("steps") is not None]
    acted = [float(records[k]["n_acted"]) for k in keys]
    actions = [float(records[k]["n_actions"]) for k in keys]
    kinds: Counter[str] = Counter()
    for k in keys:
        kinds.update(records[k]["action_kinds"])
    zero = [records[k] for k in keys if records[k]["n_acted"] == 0]
    return {
        "n_scored": len(keys),
        "acting_actor": _counter([records[k]["acting_actor"] for k in keys]),
        "categories": shares,
        "median_steps": statistics.median(steps) if steps else None,
        "mean_steps": statistics.fmean(steps) if steps else None,
        "median_acted": statistics.median(acted) if acted else None,
        "mean_acted": statistics.fmean(acted) if acted else None,
        "median_actions_any_kind": statistics.median(actions) if actions else None,
        "action_kinds_total": dict(sorted(kinds.items())),
        "zero_acted_by_error_type": _counter([r.get("error_type") or "none" for r in zero]),
        # handoff_occurred false means the replayed prefix used up the source trajectory; the
        # executor still acts when that trajectory did not end the episode, so count it.
        "n_no_handoff_acted": sum(1 for k in keys if records[k]["category"] == "no_handoff" and records[k]["n_acted"] > 0),
        "n_no_handoff_flag_missing": sum(1 for k in keys if records[k]["category"] == "no_handoff"
                                         and records[k]["handoff_occurred"] is None),
        "n_without_events": sum(1 for k in keys if not records[k]["has_events"]),
        "n_handoff_flag_differs_from_j10_reader": sum(
            1 for k in keys if records[k]["handoff_flag_j10_reader"] != records[k]["handoff_occurred"]),
        "n_clusters": {unit: b["n_clusters"] for unit, b in boots.items()},
    }


def census_section(arms: dict[str, dict[str, Any]], labels: tuple[str, ...], *, n_boot: int, seed: int) -> dict[str, Any]:
    per_arm: dict[str, Any] = {}
    for label in labels:
        if label not in arms:
            continue
        a = arms[label]
        per_arm[label] = {"campaigns": [c["campaign"] for c in a["campaigns"]], "seeds": list(a["spec"]["seeds"]),
                          "role": a["spec"]["role"], "n_crash_dropped": a["summary"]["n_crash"],
                          **census_block(a["records"], n_boot=n_boot, seed=seed)}
    return {"label": "EXPLORATORY (Fan et al. arXiv 2609.20804-comparable termination census)",
            "definitions": {k: DEFINITIONS[k] for k in ("action", "acted", "after_handoff", "categories", "handoff_flag")},
            "arms": per_arm}


# ---- C: the high-effort ceiling ---------------------------------------------------
@functools.lru_cache(maxsize=1)
def _j12() -> Any:
    """j12_cost_axes as j16 / j17_depth_fixes load it (it brings its own j8_frontier and j10_report)."""
    return j16._load_module("j12_cost_axes", "j12_cost_axes.py")


def planner_token_totals(events_path: Path) -> dict[str, float]:
    """Summed token fields of j12.extract_events_usages (planner usage, last run_start segment)."""
    usages = _j12().extract_events_usages(events_path)
    out = {f: float(sum(float(u.get(f) or 0) for u in usages)) for f in TOKEN_FIELDS}
    out["n_usage_records"] = float(len(usages))
    return out


def cost_rows(label: str, system_dir: Path, seeds: tuple[int, ...], price_card: dict[str, Any]
              ) -> tuple[dict[Key, dict[str, float]], dict[str, Any]]:
    """Per non-crashed episode: j8.summarise_arm's hosted calls and j12.price_arm_episodes' USD (as
    j17_depth_fixes.load_cost_rows prices them), plus planner token sums. Crashed rows are dropped."""
    j12 = _j12()
    loaded = j12.j10.load_arm_tree(system_dir)
    arm = j12.summarise_arm(label, loaded, list(seeds), root=system_dir, cost_key="planner_tokens_noncached",
                            packet_source=system_dir.parent, packet_system=system_dir.name)
    priced = j12.price_arm_episodes(arm, price_card, root=system_dir, packet_source=system_dir.parent,
                                    packet_system=system_dir.name)
    rows: dict[Key, dict[str, float]] = {}
    for key, row in sorted(arm["cleaned"].items()):
        if j12.j8.is_crashed(row):
            continue
        toks = planner_token_totals(system_dir / str(key[1]) / str(key[0]) / "events.jsonl")
        rows[key] = {"hosted_calls_per_episode": row.get("hosted_calls_per_episode"),
                     "usd_per_episode": row.get("usd_per_episode"), **toks}
    return rows, {"diagnostics": priced["diagnostics"], "n_rows": len(rows), "root": str(system_dir)}


def cost_block(high: dict[Key, dict[str, Any]], medium: dict[Key, dict[str, Any]], keys: set[Key], *,
               n_boot: int, seed: int) -> dict[str, Any]:
    """Per axis: both means on the paired keys, high - medium and high / medium with both clusterings."""
    a = {k: v for k, v in high.items() if k in keys}
    b = {k: v for k, v in medium.items() if k in keys}
    boots = (("scenario", seed), ("task", seed))
    out: dict[str, Any] = {}
    for axis in COST_AXES:
        c = j16.cost_contrast(a, b, axis, boots, n_boot)
        sc, tk = c[j16._boot_name("scenario", seed)], c[j16._boot_name("task", seed)]
        out[axis] = {"mean_high": c["mean_left"], "mean_medium": c["mean_right"],
                     "ratio_high_over_medium": c["ratio_left_over_right"],
                     "ratio_ci95_scenario": sc["ratio_ci95"], "ratio_ci95_task": tk["ratio_ci95"],
                     "diff_high_minus_medium": c["diff"], "diff_ci95_scenario": sc["diff_ci95"],
                     "diff_ci95_task": tk["diff_ci95"], "n_pairs": c["n_pairs"],
                     "n_dropped_missing": c["n_dropped_missing"]}
    return out


def limit_rate(eps: dict[Key, dict[str, Any]], keys: Optional[set[Key]] = None) -> dict[str, Any]:
    ks = sorted(eps if keys is None else set(eps) & keys)
    n_limit = sum(1 for k in ks if eps[k].get("error_type") == LIMIT)
    return {"n": len(ks), "n_limit": n_limit, "rate": (n_limit / len(ks)) if ks else None}


def _seeds_only(eps: dict[Key, dict[str, Any]], seeds: tuple[int, ...]) -> dict[Key, dict[str, Any]]:
    return {k: v for k, v in eps.items() if k[1] in seeds}


def ceilhi_section(arms: dict[str, dict[str, Any]], cost: Optional[dict[str, Any]], *, n_boot: int,
                   seed: int) -> dict[str, Any]:
    eps = {label: _seeds_only(arms[label]["episodes"], CEILHI_SEEDS) for label in (HIGH, MEDIUM, *NI_ARMS)
           if label in arms}
    q_keys = common_keys(eps, (HIGH, MEDIUM))
    out: dict[str, Any] = {
        "label": ("EXPLORATORY (D3): planner alone at cap 81, reasoning_effort high vs medium, seeds 1-2; the "
                  "prefix arms replay the MEDIUM-effort planner's trajectories"),
        "n_keys": len(q_keys),
        "quality": contrast_entry(eps, (HIGH, MEDIUM), q_keys, n_boot=n_boot, seed=seed),
        "limit_rates": {"high": {"all_scored": limit_rate(eps[HIGH]), "paired": limit_rate(eps[HIGH], q_keys)},
                        "medium": {"all_scored": limit_rate(eps[MEDIUM]), "paired": limit_rate(eps[MEDIUM], q_keys)}},
        "n_crash_seeds_1_2": {tag: sum(c["n_crash"] for c in arms[label]["campaigns"] if set(c["by_seed"]) <= {"1", "2"})
                              for tag, label in (("high", HIGH), ("medium", MEDIUM))},
        # What each run recorded about itself (run_start limits, the plan event's effort): the two
        # runs differ in more than effort if these differ.
        "run_settings": {tag: {field: _counter([r.get(key) for k, r in arms[label]["records"].items()
                                                if k[1] in CEILHI_SEEDS])
                               for field, key in (("plan_effort_recorded", "plan_effort"),
                                                  ("per_step_timeout_s", "per_step_timeout_s"),
                                                  ("max_planner_calls", "max_planner_calls"))}
                         for tag, label in (("high", HIGH), ("medium", MEDIUM))},
    }
    if cost is not None:
        c_keys = q_keys & set(cost["high"]) & set(cost["medium"])
        out["cost"] = {"n_keys": len(c_keys), "axes": cost_block(cost["high"], cost["medium"], c_keys,
                                                                  n_boot=n_boot, seed=seed),
                       "inputs": cost["inputs"],
                       "definition": ("hosted calls and USD per j8_frontier.summarise_arm / j12_cost_axes."
                                      "price_arm_episodes (output and reasoning_output tokens both billed at the "
                                      "output rate by j12.price_usage_record); token sums over "
                                      "j12.extract_events_usages; ratio = mean high / mean medium, whole "
                                      "clusters resampled (j16_robustness.cost_contrast)")}
    ni_keys = common_keys(eps, (HIGH, MEDIUM, *NI_ARMS))
    ni: dict[str, Any] = {"n_keys": len(ni_keys), "margin_pp": NI_MARGIN_PP, "rule": DEFINITIONS["ni_reading"],
                          "caveat": ("the registered NI is prefix_m11 against the medium-effort planner whose "
                                     "trajectories the prefixes replay; the high ceiling is an independent sample "
                                     "the prefixes never saw. Exploratory: nothing registered is re-labelled")}
    for arm in NI_ARMS:
        for ceiling, tag in ((HIGH, "high"), (MEDIUM, "medium")):
            entry = contrast_entry(eps, (ceiling, arm), ni_keys, n_boot=n_boot, seed=seed, threshold_pp=NI_MARGIN_PP)
            for metric, _f in METRICS:
                entry[metric]["reading"] = ni_reading(entry[metric]["ci95_pp_scenario"])
                entry[metric]["reading_task"] = ni_reading(entry[metric]["ci95_pp_task"])
            ni[f"{tag}_minus_{arm}"] = entry
    out["ni_reread"] = ni
    return out


# ---- ledger confirmation ---------------------------------------------------------
def _dig(tree: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if not isinstance(tree, dict) or part not in tree:
            return None
        tree = tree[part]
    return tree


def ledger_checks(arms: dict[str, dict[str, Any]], checks: tuple[dict[str, Any], ...], repo_root: Path) -> list[dict[str, Any]]:
    """Recompute each cited report's arm mean from the campaigns named here; match within 6e-7."""
    out: list[dict[str, Any]] = []
    for chk in checks:
        if chk["arm"] not in arms:
            continue
        eps = _seeds_only(arms[chk["arm"]]["episodes"], tuple(chk["seeds"]))
        vals = [float(e["goal_pass_rate"]) for e in eps.values() if e.get("goal_pass_rate") is not None]
        mine = statistics.fmean(vals) if vals else None
        reported = _dig(_read_json(repo_root / chk["report"]), chk["key"])
        match = None if mine is None or not isinstance(reported, (int, float)) else abs(mine - float(reported)) <= LEDGER_MATCH_TOL
        out.append({"ledger": chk["ledger"], "arm": chk["arm"], "campaigns": list(arms[chk["arm"]]["spec"]["campaigns"]),
                    "seeds": list(chk["seeds"]), "report": chk["report"], "key": chk["key"], "reported": reported,
                    "recomputed_goal_pass_mean": mine, "n": len(vals), "match": match})
    return out


# ---- report -----------------------------------------------------------------
def build_report(*, results_root: Path = RESULTS_ROOT, arms_spec: Optional[dict[str, dict[str, Any]]] = None,
                 n_boot: int = N_BOOT, seed: int = BOOTSTRAP_SEED, prices: Path = PRICES,
                 checks: tuple[dict[str, Any], ...] = LEDGER_CHECKS, repo_root: Path = REPO_ROOT) -> tuple[dict[str, Any], int]:
    """The whole report and its exit code. Raises b2.PoolingError on a key twice in one arm."""
    spec = dict(arms_spec or ARMS)
    arms: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for label, s in spec.items():
        print(f"[{PROTOCOL}] loading {label} ...", flush=True)
        arms[label] = load_arm(label, s, results_root)
        for camp in arms[label]["campaigns"]:
            if not camp["present"]:
                warnings.append(f"arm {label}: campaign {camp['campaign']} is missing")
        if arms[label]["n_tasks"] != DEV_N_TASKS:
            warnings.append(f"arm {label}: {arms[label]['n_tasks']} tasks observed, not {DEV_N_TASKS}")
        split = Counter(r["provenance"].get("split") or "unrecorded" for r in arms[label]["records"].values())
        wrong = {k: v for k, v in split.items() if k not in {"dev", "unrecorded"}}
        if wrong:
            warnings.append(f"arm {label}: manifests record split {wrong}")
    missing = any("is missing" in w for w in warnings)

    report: dict[str, Any] = {"protocol": PROTOCOL,
                              "label": "EXPLORATORY dev analyses prompted by the planning literature; nothing here "
                                       "decides a registered verdict",
                              "brief": "campaign/workers/briefs/20260924_ana_planning_lit.md",
                              "status": "INCOMPLETE" if missing else "COMPLETE", "warnings": warnings}
    if all(label in arms for label in PLANTAX_CORE):
        print(f"[{PROTOCOL}] A: tailoring x plan ...", flush=True)
        report["plantax"] = plantax_section(arms, n_boot=n_boot, seed=seed)
    print(f"[{PROTOCOL}] B: termination census ...", flush=True)
    report["term"] = census_section(arms, CENSUS_ARMS, n_boot=n_boot, seed=seed)
    if all(label in arms for label in (HIGH, MEDIUM, *NI_ARMS)):
        print(f"[{PROTOCOL}] C: high-effort ceiling ...", flush=True)
        card = _j12().load_price_card(prices)
        cost: dict[str, Any] = {"inputs": {"prices": _rel(prices), "schedule_date": card.get("schedule_date")}}
        for tag, label in (("high", HIGH), ("medium", MEDIUM)):
            camp = spec[label]["campaigns"][0]  # seeds 1-2 live in the first campaign of either arm
            system = sorted(arms[label]["summary"]["systems_in_tree"])[0]
            rows, info = cost_rows(label, Path(results_root) / camp / system, CEILHI_SEEDS, card)
            cost[tag] = rows
            cost["inputs"][tag] = info
        report["ceilhi"] = ceilhi_section(arms, cost, n_boot=n_boot, seed=seed)
    report["provenance"] = {label: {"campaigns": a["campaigns"], "seeds": list(a["spec"]["seeds"]),
                                    "role": a["spec"]["role"], "n_scored": a["summary"]["n_scored"],
                                    "n_crash": a["summary"]["n_crash"], "n_missing": a["summary"]["n_missing"],
                                    "error_types": a["summary"]["error_types"],
                                    "goal_pass_mean": a["summary"]["goal_pass_mean"],
                                    "tgc_mean": a["summary"]["tgc_mean"],
                                    "by_campaign": arm_provenance(a)}
                            for label, a in arms.items()}
    report["ledger_confirmation"] = ledger_checks(arms, checks, repo_root)
    report["settings"] = {
        "n_boot": n_boot, "seed": seed, "results_root": str(results_root),
        "clustering": "scenario (primary: every p and ci95_pp_scenario) and task (ci95_pp_task)",
        "interval": "95% percentile, j10.a1_interval (pairs cluster bootstrap, int(0.025 B), int(0.975 B))",
        "p_value": ("j10.bootstrap_pvalue(scenario means, threshold, 'two-sided'); p_signflip_two_sided = "
                    "cluster_inference.registered_signflip over scenarios"),
        "crash_convention": "error_type == 'crash' is dropped from every pair and counted; 'limit' is scored",
        "precision": "floats rounded to 6 dp (j16_robustness.round_floats); `printed` blocks hold the 2 dp pp forms",
        "definitions": DEFINITIONS,
    }
    return j16.round_floats(report), (1 if missing else 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J17 planning-literature analyses (dev): PLANTAX, TERM, CEILHI.")
    p.add_argument("--out", type=Path, required=True, help="report JSON path")
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
    named = [args.out, args.results_root]
    named += [args.results_root / c for s in ARMS.values() for c in s["campaigns"]]
    for path in named:
        if reason := refuse_path(path):
            return _refused(reason)
    if reason := refuse_out(args.out):
        return _refused(reason)
    try:
        report, code = build_report(results_root=args.results_root, n_boot=args.n_boot, seed=args.seed)
    except b2.PoolingError as exc:
        return _refused(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"protocol": PROTOCOL, "status": report["status"], "exit_code": code,
                      "warnings": report["warnings"], "json": str(args.out)}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
