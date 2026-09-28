#!/usr/bin/env python
"""J17 dev arms: the exploratory dev read of the week-A arms R2.4, D2, X1, ctrl_self and ctrl_wrong.

Brief ``brief_devread.md`` unit DR-1 (/home/n12194778/.claude/jobs/91578989/tmp/devread_paper/,
2026-09-28), scout ``scout_devarms.md`` beside it. Dev only and exploratory: every contrast carries
"status": "exploratory" and "split": "dev"; nothing here decides a registered verdict.

Arms, seeds 1 and 2 only (57 tasks x 2 = 114 keys) for every arm AND comparator; a row at any other
seed is ignored and counted (`n_other_seed_rows_ignored`), even where a comparator is pooled with a
seed-3 campaign elsewhere (b2_decomposition.ARM_CAMPAIGNS; scout §0 item 6):
  neutral_k1       R2.4        dev_advise_neutral_fixed_k_1_fullctx_20260924
  structured_k1    X1          dev_advise_structured_fixed_k_1_fullctx_20260924
  structured_k10   D2          dev_advise_structured_fixed_k_10_fullctx_20260924
  self_plan        ctrl_self   dev_sft_plan_selfplan_bplus_20260924
  wrong_task_plan  ctrl_wrong  dev_sft_plan_wrongtask_bplus_20260924
  comparators      correction_k1 (hj13_advise_fixed_k_1_fullctx_20260923), correction_k10
                   (hj12_advise_fixed_k_10_fullctx_20260923), neutral_k10
                   (b2_advise_neutral_fixed_k_10_fullctx_20260923), takeover_k10
                   (hj12_takeover_fixed_k_10_20260923), show_k10 (b2_show_fixed_k_10_20260923),
                   prefix_m11 (hj12_prefix_m11_20260923: CHAN-PRICE-01's P2 arm, see PREFIX_M11_SOURCE),
                   floor (hj8_sft_plan_bplus_20260921iaware, the controls' matched floor) and
                   executor_alone (hj8_executor_alone_bplus_20260919, the 0919 adapter build).

Nothing statistical is new here; it is imported, so it cannot drift:
  - loading and scoring are j17_planning_lit.load_arm (b2.load_pooled_arm + j10.a1_arm_episodes: an
    error_type 'crash' is dropped and counted, 'limit' is scored); pairs are j17_planning_lit.common_keys;
  - goal_pass (primary) and TGC are j17_planning_lit.contrast_entry: j10.a1_interval, the pairs cluster
    bootstrap over scenarios (primary) and tasks, 95 % percentile; p_two_sided j10.bootstrap_pvalue;
    p_signflip_two_sided cluster_inference.registered_signflip. SGC is j17_channel_fixes
    .sgc_contrast_object; limit rates are j17_planning_lit.limit_rate;
  - hosted calls, planner tokens and USD are j12_cost_axes.price_arm_episodes (published) and
    price_arm_episodes_attributed (attributed), with the packet source hj1b_planner_20260915/planner_alone
    that j16_robustness.load_cost_rows prices with; paired cost ratios are j16_robustness.cost_contrast.
    The token axis keeps j12's inherited name `noncached_tokens` but INCLUDES cached prompt tokens:
    j8_noncached_cost.usage_noncached_tokens (:16-24) sums input + output + reasoning with input_tokens
    taken whole, while the usage records carry cached_input_tokens as a subset of input_tokens
    (price_usage_record prices input - cached at the input rate, j12_cost_axes.py:217-225). Quote the
    number with that convention named (DEFINITIONS["noncached_tokens"]);
  - advice content is j17_channel_fixes.content_block (the code path of ledger DEC-06);
  - BY-FDR is cluster_inference.by_fdr.
What this file adds: the arm and contrast lists, the pricing of the two controls, the X1 provenance
block and its exclusion sensitivity, ledger POOL-04's seven-seed probe of any goal_pass bound within
1 pp of zero (j10.POOL04_SEEDS, j10.a1_interval), the report layout and its markdown twin.

Pricing of the controls. j12_cost_axes.py is NOT changed (the registered reports use it), and neither
control is fed to it: price_arm_episodes charges every sft_plan row the hj1b luna plan of its OWN task
(j12_cost_axes.py:361-367) and bills any non-mock usage of an unknown model at luna rates (:206-212).
  - self_plan: the plan is the executor's own local (vllm) plan: $0 hosted, 0 hosted calls and 0 hosted
    tokens under both conventions; its local plan calls, events and tokens are reported separately.
  - wrong_task_plan: the replayed plan is the hj1b luna plan of the task named in the plan event's
    usage.raw.cached_from (map[t], not t). live convention: $0, 0 calls, 0 tokens (the live cost of
    the episode); attributed convention: that plan's tokens (the j12 convention above) and USD, priced
    by j12_cost_axes.episode_cached_plan_attribution, and its one call.
Replayed plan sources. Before any pricing reads a replayed plan's source, every usage.raw.cached_from
in every events file of every arm's campaign tree (all seeds: j12's attributed pricing reads them) is
passed through refuse_path, and tallied by <campaign>/<system>, with the count outside the packet
source and the count whose seed directory differs from the episode's (`replayed_plan_sources`).

Exit codes
  0  report written
  1  report written, but a campaign directory is missing (named in `warnings`)
  2  refused: a path containing test_normal, test_challenge or _test_, or a j10_/j11_/j12_ campaign
     component; an output under /scratch; a (task_id, seed) key twice within one arm; a replayed
     plan whose usage.raw.cached_from is such a path
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
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
from scripts.analysis import cluster_inference  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402  (the module b2 uses)
from scripts.analysis import j16_robustness as j16  # noqa: E402
from scripts.analysis import j17_channel_fixes as j17c  # noqa: E402
from scripts.analysis import j17_planning_lit as j17p  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

Key = tuple  # (task_id, seed)

PROTOCOL = "J17-dev-arms"
BRIEF = ("/home/n12194778/.claude/jobs/91578989/tmp/devread_paper/brief_devread.md, unit DR-1 "
         "(scout_devarms.md beside it)")
RESULTS_ROOT = j17p.RESULTS_ROOT
PRICES = j17p.PRICES
N_BOOT = j17p.N_BOOT
BOOTSTRAP_SEED = j17p.BOOTSTRAP_SEED  # 20260924: j17_planning_lit / j17_channel_fixes / j16_robustness.SEED
SEEDS: tuple[int, ...] = j17p.S12
DEV_N_TASKS = j17p.DEV_N_TASKS  # 57
LIMIT = j17p.LIMIT
CRASH = j17p.CRASH
# j17_planning_lit.refuse_path refuses test_normal, test_challenge and a ^j1[0-2]_ component; the brief
# adds the substring _test_ (the BFCL / J11 held-out campaign spelling).
EXTRA_HELDOUT_MARKERS = ("_test_",)
PACKET_SOURCE = "hj1b_planner_20260915"  # j16_robustness.HJ1B: the plan / prefix source of every arm here
PACKET_SYSTEM = "planner_alone"
CACHE_PROVIDER = "cache"
LOCAL_PROVIDERS = ("vllm", "mock")  # a served LoRA plan, and the planner error record of a failed parse
COST_KEY = "planner_tokens_noncached"  # as j17_planning_lit.cost_rows
X1_LABEL = "structured_k1"
X1_EARLY_SHA = "1f1f991"  # round 1's commit (dirty tree); round 2 ran at 72e00ce
X1_ROUND1_JOB = "25917052"
X1_ROUND1_LOG = REPO_ROOT / "campaign" / "workers" / "logs" / "hj12_live_live_20260924.25917052.aqua.out"
ADVICE_AT_PRICE = "campaign/results/hj13_advice_at_price_20260923.report.json"
COST_AXES_FIXED = "campaign/results/hj13_cost_axes_fixed_20260923.report.json"

_arm = j17p._arm
ARMS: dict[str, dict[str, Any]] = {
    "neutral_k1": _arm(("dev_advise_neutral_fixed_k_1_fullctx_20260924",), SEEDS, "executor"),
    "structured_k1": _arm(("dev_advise_structured_fixed_k_1_fullctx_20260924",), SEEDS, "executor"),
    "structured_k10": _arm(("dev_advise_structured_fixed_k_10_fullctx_20260924",), SEEDS, "executor"),
    "self_plan": _arm(("dev_sft_plan_selfplan_bplus_20260924",), SEEDS, "executor"),
    "wrong_task_plan": _arm(("dev_sft_plan_wrongtask_bplus_20260924",), SEEDS, "executor"),
    "correction_k1": _arm(("hj13_advise_fixed_k_1_fullctx_20260923",), SEEDS, "executor"),
    "correction_k10": _arm(("hj12_advise_fixed_k_10_fullctx_20260923",), SEEDS, "executor"),
    "neutral_k10": _arm(("b2_advise_neutral_fixed_k_10_fullctx_20260923",), SEEDS, "executor"),
    "takeover_k10": _arm(("hj12_takeover_fixed_k_10_20260923",), SEEDS, "executor"),
    "show_k10": _arm(("b2_show_fixed_k_10_20260923",), SEEDS, "executor"),
    "prefix_m11": _arm(("hj12_prefix_m11_20260923",), SEEDS, "prefix"),
    "floor": _arm(("hj8_sft_plan_bplus_20260921iaware",), SEEDS, "executor"),
    "executor_alone": _arm(("hj8_executor_alone_bplus_20260919",), SEEDS, "executor"),
}
ARM_INFO: dict[str, dict[str, Any]] = {
    "neutral_k1": {"dev_arm": "R2.4", "role": "dev arm", "kind": "advice", "prompt": "neutral", "k": 1,
                   "config": "configs/dev_advise_neutral_fixed_k_1_fullctx.yaml"},
    "structured_k1": {"dev_arm": "X1", "role": "dev arm", "kind": "advice", "prompt": "structured", "k": 1,
                      "config": "configs/dev_advise_structured_fixed_k_1_fullctx.yaml"},
    "structured_k10": {"dev_arm": "D2", "role": "dev arm", "kind": "advice", "prompt": "structured", "k": 10,
                       "config": "configs/dev_advise_structured_fixed_k_10_fullctx.yaml"},
    "self_plan": {"dev_arm": "ctrl_self", "role": "dev arm", "kind": "control", "prompt": None, "k": None,
                  "config": "configs/dev_sft_plan_selfplan_bplus.yaml"},
    "wrong_task_plan": {"dev_arm": "ctrl_wrong", "role": "dev arm", "kind": "control", "prompt": None, "k": None,
                        "config": "configs/dev_sft_plan_wrongtask_bplus.yaml"},
    "correction_k1": {"dev_arm": None, "role": "comparator", "kind": "advice", "prompt": "correction", "k": 1,
                      "config": "configs/hj13_advise_fixed_k_1_fullctx.yaml"},
    "correction_k10": {"dev_arm": None, "role": "comparator", "kind": "advice", "prompt": "correction", "k": 10,
                       "config": "configs/hj12_advise_fixed_k_10_fullctx.yaml"},
    "neutral_k10": {"dev_arm": None, "role": "comparator", "kind": "advice", "prompt": "neutral", "k": 10,
                    "config": "configs/b2_advise_neutral_fixed_k_10_fullctx.yaml"},
    "takeover_k10": {"dev_arm": None, "role": "comparator", "kind": "takeover", "prompt": None, "k": 10,
                     "config": "configs/hj12_takeover_fixed_k_10.yaml"},
    "show_k10": {"dev_arm": None, "role": "comparator", "kind": "show", "prompt": None, "k": 10,
                 "config": "configs/b2_show_fixed_k_10.yaml"},
    "prefix_m11": {"dev_arm": None, "role": "comparator", "kind": "prefix", "prompt": None, "k": None,
                   "config": "configs/hj12_prefix_m11.yaml"},
    "floor": {"dev_arm": None, "role": "comparator", "kind": "one_plan", "prompt": None, "k": None,
              "config": "configs/hj8_sft_plan_bplus.yaml"},
    "executor_alone": {"dev_arm": None, "role": "comparator", "kind": "no_plan", "prompt": None, "k": None,
                       "config": "configs/hj8_executor_alone_bplus.yaml"},
}
ADVICE_ARMS = tuple(label for label, info in ARM_INFO.items() if info["kind"] == "advice")
CONTROL_ARMS = ("self_plan", "wrong_task_plan")
J12_PRICED_ARMS = tuple(label for label in ARMS if label not in CONTROL_ARMS)
BUILD_CAVEAT = "0919 adapter build vs the controls' 0921iaware build"

# left - right. `group` names the question; the ids are the report keys.
CONTRASTS: tuple[dict[str, Any], ...] = (
    {"id": "neutral_k1_minus_correction_k1", "left": "neutral_k1", "right": "correction_k1", "group": "advice_prompt_k1",
     "question": "G3 / H2 'strawman': the neutral prompt against the terse correction prompt at k = 1 (R2.4)"},
    {"id": "structured_k1_minus_correction_k1", "left": "structured_k1", "right": "correction_k1",
     "group": "advice_prompt_k1", "question": "G3: structured direction against the correction prompt at k = 1 (X1)"},
    {"id": "structured_k1_minus_neutral_k1", "left": "structured_k1", "right": "neutral_k1", "group": "advice_prompt_k1",
     "question": "X1's matched arm (tests/unit/test_dev_arms.py:98-99): structured against neutral at k = 1"},
    {"id": "structured_k10_minus_correction_k10", "left": "structured_k10", "right": "correction_k10",
     "group": "advice_prompt_k10", "question": "G3 / G8: the ManagerWorker/Minions-style baseline (D2) against correction"},
    {"id": "structured_k10_minus_neutral_k10", "left": "structured_k10", "right": "neutral_k10",
     "group": "advice_prompt_k10", "question": "D2 against the neutral prompt at k = 10"},
    {"id": "takeover_k10_minus_structured_k10", "left": "takeover_k10", "right": "structured_k10",
     "group": "advice_prompt_k10", "question": "the action channel against D2 at a matched trigger (k = 10)"},
    {"id": "show_k10_minus_structured_k10", "left": "show_k10", "right": "structured_k10", "group": "advice_prompt_k10",
     "question": "shown actions against D2 at k = 10"},
    {"id": "neutral_k1_minus_neutral_k10", "left": "neutral_k1", "right": "neutral_k10", "group": "frequency",
     "question": "review frequency under the neutral prompt"},
    {"id": "structured_k1_minus_structured_k10", "left": "structured_k1", "right": "structured_k10",
     "group": "frequency", "question": "review frequency under the structured prompt"},
    {"id": "neutral_k1_minus_prefix_m11", "left": "neutral_k1", "right": "prefix_m11", "group": "advice_vs_prefix",
     "question": "dev analogue of J10 P1 / CHAN-PRICE-01 P2, neutral prompt"},
    {"id": "structured_k1_minus_prefix_m11", "left": "structured_k1", "right": "prefix_m11",
     "group": "advice_vs_prefix", "question": "dev analogue of J10 P1 / CHAN-PRICE-01 P2, structured prompt"},
    {"id": "self_plan_minus_floor", "left": "self_plan", "right": "floor", "group": "planning_controls",
     "question": "ctrl_self: the executor's own plan against one replayed luna plan (matched 0921iaware build)"},
    {"id": "wrong_task_plan_minus_floor", "left": "wrong_task_plan", "right": "floor", "group": "planning_controls",
     "question": "ctrl_wrong: a length-matched wrong-task luna plan against the task's own plan"},
    {"id": "self_plan_minus_executor_alone", "left": "self_plan", "right": "executor_alone",
     "group": "planning_controls", "question": "ctrl_self against no plan", "build_caveat": BUILD_CAVEAT},
    {"id": "wrong_task_plan_minus_executor_alone", "left": "wrong_task_plan", "right": "executor_alone",
     "group": "planning_controls", "question": "ctrl_wrong against no plan", "build_caveat": BUILD_CAVEAT},
)
COST_CONTRASTS: tuple[tuple[str, str], ...] = (("neutral_k1", "prefix_m11"), ("structured_k1", "prefix_m11"),
                                               ("structured_k10", "correction_k10"))
COST_AXES = ("hosted_calls_per_episode", "calls_live_per_episode", "noncached_tokens_per_episode", "usd_per_episode")
J12_CONVENTIONS = ("published", "attributed")
CALL_NAMES = ("ledger", "n_planner", "cached", "ledger_minus_cached", "live")
CONTROL_CONVENTIONS = ("live", "attributed")

# CHAN-PRICE-01 (docs/claims_ledger.md:117) reads P2 as contrasts.goal_pass_all_advise_k1_fullctx_minus_prefix_m11
# of ADVICE_AT_PRICE (-14.68 pp); its prereg names the arm `hj12_prefix_m11_20260923/prefix_handoff`
# (docs/prereg_h2_advice_at_price_20260923.md:50), n = 114 at seeds 1-2 (the report's `seeds` [1, 2]).
PREFIX_M11_SOURCE = {
    "ledger": "CHAN-PRICE-01",
    "artifact": ADVICE_AT_PRICE,
    "arm_key": "arms.prefix_m11.goal_pass_all",
    "p2_key": "contrasts.goal_pass_all_advise_k1_fullctx_minus_prefix_m11.diff_pp",
    "prereg": "docs/prereg_h2_advice_at_price_20260923.md:50 (`hj12_prefix_m11_20260923/prefix_handoff`)",
    "campaigns": ARMS["prefix_m11"]["campaigns"],
    "system": "prefix_handoff",
    "seeds": list(SEEDS),
}
LEDGER_CHECKS: tuple[dict[str, Any], ...] = (
    {"ledger": "CHAN-PRICE-01", "arm": "prefix_m11", "report": ADVICE_AT_PRICE, "key": "arms.prefix_m11.goal_pass_all",
     "seeds": SEEDS},
    {"ledger": "CHAN-PRICE-01", "arm": "correction_k1", "report": ADVICE_AT_PRICE,
     "key": "arms.advise_k1_fullctx.goal_pass_all", "seeds": SEEDS},
    {"ledger": "CHAN-PRICE-01", "arm": "correction_k10", "report": ADVICE_AT_PRICE,
     "key": "arms.advise_k10_fullctx.goal_pass_all", "seeds": SEEDS},
    {"ledger": "CHAN-PRICE-01", "arm": "floor", "report": ADVICE_AT_PRICE, "key": "arms.plan_floor.goal_pass_all",
     "seeds": SEEDS},
)
# The published pricing of three comparators, recomputed here, against the committed cost report.
COST_CHECKS: tuple[dict[str, Any], ...] = tuple(
    {"arm": arm, "report": COST_AXES_FIXED, "key": f"arms.{rkey}.{axis}", "axis": axis}
    for arm, rkey in (("prefix_m11", "prefix_m11"), ("correction_k10", "advise_k10_fullctx"),
                      ("takeover_k10", "takeover_k10"))
    for axis in ("hosted_calls_per_episode", "noncached_tokens_per_episode", "usd_per_episode"))
COST_MATCH_TOL = {"hosted_calls_per_episode": 1e-5, "noncached_tokens_per_episode": 1e-3, "usd_per_episode": 2e-6}

DEFINITIONS = {
    "pairing": ("seeds 1 and 2 only; a pair is a (task_id, seed) key scored (non-crash, goal_pass and TGC "
                "recorded) in both arms; n_dropped = the 57 x 2 matrix keys of either arm's tasks minus n_pairs"),
    "limit": "error_type == 'limit' (the step limit), a scored outcome; its rate is over non-crash episodes",
    "sgc": j17c.DEFINITIONS["sgc"],
    "success": "result.json success of the non-crash episodes (j10.a1_arm_episodes)",
    "calls_ledger": "result.json totals.planner_calls_total (the ledger key; a replayed plan adds 1)",
    "calls_n_planner": ("result.json n_planner_calls = j12's hosted_calls_per_episode axis (a replayed plan is one "
                        "call; a prefix arm is charged its replayed prefix)"),
    "calls_live": ("hosted calls: calls_ledger minus usage.n_calls (1 when absent) of the episode's planner events "
                   "with usage.provider 'cache' (j12_cost_axes.cached_plan_usages; bfcl_dev_report.py:141-144). "
                   "For the controls: the calls of hosted (non-local, non-cache) planner usages"),
    "noncached_tokens": ("j12_cost_axes noncached_tokens_per_episode = j8_noncached_cost.usage_noncached_tokens "
                         "(j8_noncached_cost.py:16-24): input_tokens + output_tokens + reasoning_output_tokens, with "
                         "input_tokens taken WHOLE. The usage records carry cached_input_tokens as a subset of "
                         "input_tokens (price_usage_record prices input - cached at the input rate and cached at the "
                         "cached rate, j12_cost_axes.py:217-225), so despite its inherited name this axis INCLUDES "
                         "cached prompt tokens; it is the convention of the registered cost reports, not "
                         "input - cached + output + reasoning. Name the convention wherever the number is quoted"),
    "usd": "j12_cost_axes usd_per_episode under configs/cost/prices_2026-09.yaml (price_usage_record)",
    "published": "j12_cost_axes.price_arm_episodes: a replayed (cache) plan costs 0 tokens and $0",
    "attributed": ("j12_cost_axes.price_arm_episodes_attributed (ATTRIBUTION_CONVENTION, j12_cost_axes.py:734-739): "
                   "a replayed plan is charged the tokens and USD of the source plan event it replays "
                   "(usage.raw.cached_from); calls unchanged; sft_plan and prefix rows left as priced"),
    "live": "controls only: the episode's own hosted planner usage (none in either control): $0, 0 calls",
    "interventions": "result.json n_interventions per non-crash episode",
    "x1_early": f"X1 episodes whose manifest provenance.git_sha starts with {X1_EARLY_SHA!r} (round 1, dirty tree)",
    "cost_ratio": ("mean left / mean right over the paired keys, whole clusters resampled "
                   "(j16_robustness.cost_contrast), scenario and task clusterings"),
}


# ---- paths ------------------------------------------------------------------
def refuse_path(path: Path | str) -> Optional[str]:
    """j17_planning_lit.refuse_path, plus the substring _test_."""
    if reason := j17p.refuse_path(path):
        return reason
    texts = {str(path)}
    try:
        texts.add(str(Path(path).resolve()))
    except OSError:
        pass
    for text in sorted(texts):
        for marker in EXTRA_HELDOUT_MARKERS:
            if marker in text:
                return f"refusing {path}: contains {marker!r} (dev only; held-out data are not read here)"
    return None


refuse_out = j17p.refuse_out
_rel = j17p._rel
_read_json = j17p._read_json


class HeldOutSourceError(ValueError):
    """A replayed plan's usage.raw.cached_from names a held-out path (exit 2)."""


def _cached_from(usage: dict[str, Any]) -> Optional[str]:
    raw = usage.get("raw") if isinstance(usage.get("raw"), dict) else {}
    value = raw.get("cached_from")
    return str(value) if value else None


def check_cached_from(source: str, where: str) -> None:
    """Refuse a replayed plan source under a held-out path, before anything reads it."""
    if reason := refuse_path(source):
        raise HeldOutSourceError(f"{where}: replayed plan source {reason}")


def source_dir(source: str) -> str:
    """<campaign>/<system> of a runner-layout events path <campaign>/<system>/<seed>/<task>/events.jsonl."""
    p = Path(source)
    return f"{p.parents[3].name}/{p.parents[2].name}" if len(p.parts) >= 5 else str(p.parent)


def replayed_plan_sources(label: str, dirs: list[Path], packet_source: Path) -> dict[str, Any]:
    """Every replayed plan's usage.raw.cached_from in the arm's campaign trees (every seed and events file,
    since j12's attributed pricing reads them), refused if held out, then tallied (module docstring)."""
    j12 = j17p._j12()
    root = Path(packet_source).resolve()
    by_source: Counter = Counter()
    out = {"n_events_files": 0, "n_cached_plan_usages": 0, "n_without_cached_from": 0,
           "n_outside_packet_source": 0, "n_seed_dir_mismatch": 0}
    for directory in dirs:
        if not Path(directory).is_dir():
            continue
        for ev in sorted(Path(directory).rglob("events.jsonl")):
            out["n_events_files"] += 1
            for usage in j12.cached_plan_usages(ev):
                out["n_cached_plan_usages"] += 1
                src = _cached_from(usage)
                if src is None:
                    out["n_without_cached_from"] += 1
                    continue
                check_cached_from(src, f"arm {label} {ev.parent.parent.name}/{ev.parent.name}")
                by_source[source_dir(src)] += 1
                if not Path(src).resolve().is_relative_to(root):
                    out["n_outside_packet_source"] += 1
                if Path(src).parent.parent.name != ev.parent.parent.name:
                    out["n_seed_dir_mismatch"] += 1
    return {**out, "by_source": dict(sorted(by_source.items()))}


def git_state() -> dict[str, Any]:
    def run(*args: str) -> Optional[str]:
        try:
            res = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        return res.stdout if res.returncode == 0 else None

    sha = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {"git_sha": sha.strip() if sha else None,
            "git_dirty": None if status is None else bool(status.strip()),
            "git_dirty_paths": None if status is None else sorted(line[3:] for line in status.splitlines() if line)}


# ---- one arm ------------------------------------------------------------------
def manifest_extra(path: Path) -> dict[str, Any]:
    """What load_arm's provenance does not keep: the prompt and planner the runner recorded."""
    man = _read_json(path)
    prov = man.get("provenance") if isinstance(man, dict) and isinstance(man.get("provenance"), dict) else {}
    return {"correct_prompt": prov.get("correct_prompt"), "planner_type": prov.get("planner_type"),
            "planner_model_requested": prov.get("planner_model_requested")}


def load_dev_arm(label: str, spec: dict[str, Any], results_root: Path) -> dict[str, Any]:
    """j17_planning_lit.load_arm, plus the raw rows at the arm's seeds and the events paths of its scored keys."""
    arm = j17p.load_arm(label, spec, results_root)
    dirs = [Path(results_root) / c for c in spec["campaigns"]]
    pooled = b2.load_pooled_arm(label, dirs)
    seeds = {int(s) for s in spec["seeds"]}
    arm["runs"] = {k: r for k, r in pooled["runs"].items() if k[1] in seeds}
    arm["n_other_seed_rows_ignored"] = sum(1 for k in pooled["runs"] if k[1] not in seeds)
    arm["tasks"] = sorted({t for t, _s in arm["runs"]})
    arm["event_paths"] = b2.s_event_paths(dirs, set(arm["episodes"]))
    arm["manifest_extra"] = {k: manifest_extra(p.parent / "manifest.json") for k, p in arm["event_paths"].items()}
    arm["dirs"] = dirs
    return arm


def _n_calls(usage: dict[str, Any]) -> int:
    n = usage.get("n_calls")
    return int(n) if n is not None else 1


def _int_or_none(value: Any) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def episode_calls(row: dict[str, Any], events_path: Optional[Path]) -> dict[str, Any]:
    """Ledger, published and live planner calls, interventions and asks of one episode."""
    totals = row.get("totals") if isinstance(row.get("totals"), dict) else {}
    ledger = _int_or_none(totals.get("planner_calls_total"))
    cached: Optional[int] = None
    if events_path is not None and events_path.is_file():
        cached = sum(_n_calls(u) for u in j17p._j12().cached_plan_usages(events_path))
    minus_cached = None if ledger is None or cached is None else ledger - cached
    return {
        "calls_ledger": ledger,
        "calls_n_planner": _int_or_none(row.get("n_planner_calls")),
        "calls_cached": cached,
        "calls_ledger_minus_cached": minus_cached,
        "calls_live": minus_cached,  # a control's is replaced by its hosted calls in build_report
        "interventions": _int_or_none(row.get("n_interventions")),
        "asks": _int_or_none(row.get("n_asks")),
        "runner_usd_total": None if totals.get("usd_total") is None else float(totals["usd_total"]),
    }


def _mean(values: list[Any]) -> Optional[float]:
    vals = [float(v) for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


# ---- pricing ------------------------------------------------------------------
def j12_cost_rows(label: str, system_dir: Path, packet_source: Path, card: dict[str, Any], keys: set[Key]
                  ) -> tuple[dict[str, dict[Key, dict[str, Any]]], dict[str, Any]]:
    """Per scored key, j12's three axes under both conventions (a fresh summarise_arm per convention,
    because either pricing function writes its values onto the arm's rows)."""
    j12 = j17p._j12()
    rows: dict[str, dict[Key, dict[str, Any]]] = {}
    info: dict[str, Any] = {"system_dir": str(system_dir), "packet_source": str(packet_source),
                            "packet_system": PACKET_SYSTEM}
    for conv, fn in (("published", j12.price_arm_episodes), ("attributed", j12.price_arm_episodes_attributed)):
        loaded = j12.j10.load_arm_tree(system_dir)
        arm = j12.summarise_arm(label, loaded, list(SEEDS), root=system_dir, cost_key=COST_KEY,
                                packet_source=packet_source, packet_system=PACKET_SYSTEM)
        try:
            priced = fn(arm, card, system_dir, packet_source, PACKET_SYSTEM)
        except SystemExit as exc:  # j12's fatal checks (0 priced, > 5 % without usage)
            rows[conv] = {}
            info[conv] = {"error": str(exc)}
            continue
        conv_rows: dict[Key, dict[str, Any]] = {}
        for key, row in arm["cleaned"].items():
            if key not in keys or j12.j8.is_crashed(row):
                continue
            conv_rows[key] = {axis: row.get(axis) for axis in ("hosted_calls_per_episode", "noncached_tokens_per_episode",
                                                                "usd_per_episode")}
        rows[conv] = conv_rows
        floor_costing = arm.get("sft_plan_floor_costing") or {}
        info[conv] = {"function": fn.__name__, "diagnostics": priced.get("diagnostics"), "n_rows": len(conv_rows),
                      "cached_plan_attribution": priced.get("cached_plan_attribution"),
                      "sft_plan_floor_costing": {k: floor_costing.get(k) for k in
                                                 ("applied", "route", "n_sft_plan_rows", "n_mapped", "n_missing",
                                                  "n_planless_live")}}
    return rows, info


def control_cost_row(events_path: Optional[Path], models_prices: dict[str, Any], *, packet_source: Path,
                     task_id: str, seed: int) -> dict[str, Any]:
    """One control episode under the live and attributed conventions (module docstring)."""
    j12 = j17p._j12()
    usages = j12.extract_events_usages(events_path) if events_path is not None and events_path.is_file() else []
    diag = {"n_usage_without_cache_split": 0}
    cached = [u for u in usages if u.get("provider") == CACHE_PROVIDER]
    local = [u for u in usages if u.get("provider") in LOCAL_PROVIDERS]
    hosted = [u for u in usages if u.get("provider") not in (CACHE_PROVIDER, *LOCAL_PROVIDERS)]
    live = {"hosted_calls": sum(_n_calls(u) for u in hosted),
            "noncached_tokens": float(sum(j12.usage_noncached_tokens(u) or 0.0 for u in hosted)),
            "usd": float(sum(j12.price_usage_record(u, models_prices, diag) for u in hosted))}
    sources: list[str] = []
    source_dirs: list[str] = []
    for u in cached:
        if src := _cached_from(u):
            check_cached_from(src, f"{task_id}/{seed}")  # before episode_cached_plan_attribution reads it
            sources.append(Path(src).parent.name)
            source_dirs.append(source_dir(src))
    att: dict[str, Any] = {"n_cached_plan_events": 0, "cache_calls": 0, "n_source_missing": 0,
                           "n_cached_from_outside_packet_source": 0, "noncached_tokens": 0.0, "usd": 0.0}
    if cached and events_path is not None:
        att = j12.episode_cached_plan_attribution(events_path, models_prices, packet_source=packet_source,
                                                  packet_system=PACKET_SYSTEM, task_id=task_id, seed=seed)
    vllm = [u for u in local if u.get("provider") == "vllm"]
    return {
        "live": live,
        "attributed": {"hosted_calls": live["hosted_calls"] + int(att["cache_calls"]),
                       "noncached_tokens": live["noncached_tokens"] + float(att["noncached_tokens"]),
                       "usd": live["usd"] + float(att["usd"])},
        "n_hosted_usage_records": len(hosted),
        "n_cached_plan_events": int(att["n_cached_plan_events"]),
        "n_source_missing": int(att["n_source_missing"]),
        "n_cached_from_outside_packet_source": int(att.get("n_cached_from_outside_packet_source") or 0),
        "replayed_from_tasks": sources,
        "replayed_from_source_dirs": source_dirs,
        "local_plan_calls": sum(_n_calls(u) for u in local),
        "n_local_plan_usages_vllm": len(vllm),
        "local_plan_noncached_tokens": float(sum(j12.usage_noncached_tokens(u) or 0.0 for u in vllm)),
    }


def control_pricing(label: str, arm: dict[str, Any], packet_source: Path, card: dict[str, Any]) -> dict[str, Any]:
    """Per-episode rows (keys: axis names as in COST_AXES) and the arm-level block for one control."""
    per: dict[Key, dict[str, Any]] = {}
    for key in sorted(arm["episodes"]):
        per[key] = control_cost_row(arm["event_paths"].get(key), card["models"], packet_source=packet_source,
                                    task_id=str(key[0]), seed=int(key[1]))
    rows = {conv: {k: {"hosted_calls_per_episode": float(r[conv]["hosted_calls"]),
                       "noncached_tokens_per_episode": r[conv]["noncached_tokens"],
                       "usd_per_episode": r[conv]["usd"]} for k, r in per.items()}
            for conv in CONTROL_CONVENTIONS}
    own = sum(1 for k, r in per.items() if k[0] in r["replayed_from_tasks"])
    other = sum(1 for k, r in per.items() if r["replayed_from_tasks"] and k[0] not in r["replayed_from_tasks"])
    same_scen = sum(1 for k, r in per.items() for t in r["replayed_from_tasks"]
                    if t != k[0] and scenario_of(t) == scenario_of(k[0]))
    runner_usd = [arm["runs"][k].get("totals", {}).get("usd_total") for k in per
                  if isinstance(arm["runs"].get(k, {}).get("totals"), dict)]
    block = {
        "n": len(per),
        **{conv: {"hosted_calls_per_episode": _mean([r[conv]["hosted_calls"] for r in per.values()]),
                  "noncached_tokens_per_episode": _mean([r[conv]["noncached_tokens"] for r in per.values()]),
                  "usd_per_episode": _mean([r[conv]["usd"] for r in per.values()]),
                  "usd_total": float(sum(r[conv]["usd"] for r in per.values()))} for conv in CONTROL_CONVENTIONS},
        "n_hosted_usage_records": sum(r["n_hosted_usage_records"] for r in per.values()),
        "n_cached_plan_events": sum(r["n_cached_plan_events"] for r in per.values()),
        "n_source_missing": sum(r["n_source_missing"] for r in per.values()),
        "n_cached_from_outside_packet_source": sum(r["n_cached_from_outside_packet_source"] for r in per.values()),
        "replayed_from_source_dirs": dict(sorted(Counter(d for r in per.values()
                                                         for d in r["replayed_from_source_dirs"]).items())),
        "n_replayed_from_own_task": own,
        "n_replayed_from_other_task": other,
        "n_replayed_from_same_scenario_other_task": same_scen,
        "local_plan_calls_total": sum(r["local_plan_calls"] for r in per.values()),
        "local_plan_calls_per_episode": _mean([r["local_plan_calls"] for r in per.values()]),
        "n_local_plan_usages_vllm": sum(r["n_local_plan_usages_vllm"] for r in per.values()),
        "n_episodes_without_local_plan_usage": sum(1 for r in per.values() if r["n_local_plan_usages_vllm"] == 0),
        "local_plan_noncached_tokens_per_episode": _mean([r["local_plan_noncached_tokens"] for r in per.values()]),
        "runner_usd_total_sum": float(sum(float(v) for v in runner_usd if v is not None)),
    }
    return {"rows": rows, "block": block, "per_episode": per}


# ---- inference --------------------------------------------------------------
def _limit_pair(eps: dict[str, dict[Key, dict[str, Any]]], label: str, keys: set[Key]) -> dict[str, Any]:
    return {"paired": j17p.limit_rate(eps[label], keys), "all_scored": j17p.limit_rate(eps[label])}


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def boundary_probe(series: dict[str, Any], ci_pp: dict[str, Any], *, n_boot: int,
                   window_pp: float = j10.POOL04_WINDOW_PP, seeds: tuple[int, ...] = j10.POOL04_SEEDS,
                   big_n: int = j10.POOL04_BIG_N, big_seed: int = j10.POOL04_BIG_SEED) -> Optional[dict[str, Any]]:
    """Ledger POOL-04's standing check on a goal_pass bound within window_pp of zero: the same interval
    (j10.a1_interval) at the seven POOL-04 seeds and once at big_n resamples. None if no bound is that close."""
    flagged = [(unit, side, bound) for unit in ("scenario", "task") for side, bound in zip(("lo", "hi"), ci_pp.get(unit) or ())
               if bound is not None and abs(round(float(bound), 2)) < window_pp]
    if not flagged or not series["diffs"]:
        return None
    rows = []
    for unit, side, bound in flagged:
        by_seed = {str(s): 100.0 * j10.a1_interval(series, unit, n_boot=n_boot, seed=s)[side] for s in seeds}
        big = 100.0 * j10.a1_interval(series, unit, n_boot=big_n, seed=big_seed)[side]
        rows.append({"clustering": unit, "side": side, "bound_pp": bound, "by_seed_pp": by_seed,
                     "big_n": big_n, "big_seed": big_seed, "bound_big_pp": big,
                     "sign_stable": len({_sign(v) for v in (*by_seed.values(), big)}) == 1})
    return {"status": "exploratory", "split": "dev",
            "rule": (f"ledger POOL-04: a goal_pass bound within {window_pp:.2f} pp of zero, re-run at seeds "
                     f"{list(seeds)} (B = {n_boot}) and at {big_n} resamples (seed {big_seed}); unresolved if the sign changes"),
            "bounds": rows}


def contrast_block(arms: dict[str, dict[str, Any]], c: dict[str, Any], *, n_boot: int, seed: int,
                   exclude: frozenset = frozenset(), probe_window_pp: float = j10.POOL04_WINDOW_PP,
                   probe_big_n: int = j10.POOL04_BIG_N) -> dict[str, Any]:
    """goal_pass (primary), TGC and SGC for left - right on the keys scored in both, minus `exclude`."""
    left, right = c["left"], c["right"]
    eps = {label: {k: v for k, v in arms[label]["episodes"].items() if k not in exclude} for label in (left, right)}
    keys = j17p.common_keys(eps, (left, right))
    entry = j17p.contrast_entry(eps, (left, right), keys, n_boot=n_boot, seed=seed)
    gp = entry["goal_pass"]
    probe = boundary_probe(j17p.combo_series(eps, (left, right), "goal_pass_rate", keys),
                           {"scenario": gp.get("ci95_pp_scenario"), "task": gp.get("ci95_pp_task")},
                           n_boot=n_boot, window_pp=probe_window_pp, big_n=probe_big_n)
    tasks = sorted(set(arms[left]["tasks"]) | set(arms[right]["tasks"]))
    entry["sgc"] = j17c.sgc_contrast_object(eps[left], eps[right], tasks, list(SEEDS), n_boot=n_boot, seed=seed)
    expected = {(t, s) for t in tasks for s in SEEDS} - set(exclude)
    n_pairs = entry["goal_pass"]["n_pairs"]
    dropped: dict[str, Any] = {}
    for side, label in (("left", left), ("right", right)):
        runs = arms[label]["runs"]
        dropped[side] = {
            "crash": sum(1 for k in expected if runs.get(k, {}).get("error_type") == CRASH),
            "missing": sum(1 for k in expected if k not in runs),
            "unscored_metric": sum(1 for k in expected if k in eps[label] and k not in j17p.scored_keys(eps[label])),
        }
    return {
        "status": "exploratory",
        "split": "dev",
        "group": c.get("group"),
        "question": c.get("question"),
        "definition": entry.pop("definition"),
        "left": {"label": left, "campaigns": list(arms[left]["spec"]["campaigns"])},
        "right": {"label": right, "campaigns": list(arms[right]["spec"]["campaigns"])},
        **({"build_caveat": c["build_caveat"]} if c.get("build_caveat") else {}),
        "n_pairs": n_pairs,
        "n_expected": len(expected),
        "n_dropped": len(expected) - n_pairs,
        "dropped": dropped,
        "limit_rate": {"left": _limit_pair(eps, left, keys), "right": _limit_pair(eps, right, keys)},
        **entry,
        "goal_pass_boundary_probe": probe,
    }


def cost_ratio_block(left_rows: dict[Key, dict[str, Any]], right_rows: dict[Key, dict[str, Any]], keys: set[Key], *,
                     n_boot: int, seed: int) -> dict[str, Any]:
    """Per axis: both means, left / right and left - right with scenario and task intervals."""
    a = {k: v for k, v in left_rows.items() if k in keys}
    b = {k: v for k, v in right_rows.items() if k in keys}
    out: dict[str, Any] = {}
    for axis in COST_AXES:
        c = j16.cost_contrast(a, b, axis, (("scenario", seed), ("task", seed)), n_boot)
        sc, tk = c[j16._boot_name("scenario", seed)], c[j16._boot_name("task", seed)]
        out[axis] = {"mean_left": c["mean_left"], "mean_right": c["mean_right"],
                     "ratio_left_over_right": c["ratio_left_over_right"],
                     "ratio_ci95_scenario": sc["ratio_ci95"], "ratio_ci95_task": tk["ratio_ci95"],
                     "diff_left_minus_right": c["diff"], "diff_ci95_scenario": sc["diff_ci95"],
                     "diff_ci95_task": tk["diff_ci95"], "n_pairs": c["n_pairs"],
                     "n_dropped_missing": c["n_dropped_missing"]}
    return out


def by_fdr_block(contrasts: dict[str, dict[str, Any]], alpha: float = j17c.ALPHA) -> dict[str, Any]:
    """Benjamini-Yekutieli over the goal_pass contrasts of `contrasts` (the CONTRASTS family), on the
    scenario bootstrap p and, beside it, on the sign-flip p."""
    ids = list(contrasts)
    out: dict[str, Any] = {
        "status": "exploratory", "split": "dev", "decision_bearing": False,
        "method": "Benjamini-Yekutieli, cluster_inference.by_fdr", "alpha": alpha,
        "family_rule": ("the goal_pass object of every contrast in `contrasts` (the brief's list), each once; "
                        "sensitivities and cost ratios are not in the family; one without a p is listed and not in m"),
    }
    rows = {cid: {"diff_pp": contrasts[cid]["goal_pass"].get("diff_pp"),
                  "p_two_sided": contrasts[cid]["goal_pass"].get("p_two_sided"),
                  "p_signflip_two_sided": contrasts[cid]["goal_pass"].get("p_signflip_two_sided")} for cid in ids}
    for p_key, tag in (("p_two_sided", "p_by"), ("p_signflip_two_sided", "p_by_signflip")):
        usable = [cid for cid in ids if rows[cid][p_key] is not None]
        adjusted = dict(zip(usable, cluster_inference.by_fdr([float(rows[cid][p_key]) for cid in usable])))
        for cid in ids:
            rows[cid][tag] = adjusted.get(cid)
            rows[cid][f"{tag}_survives_alpha"] = None if cid not in adjusted else bool(adjusted[cid] <= alpha)
        out[f"m_{p_key}"] = len(usable)
    out["rows"] = rows
    return out


# ---- per arm -----------------------------------------------------------------
def arm_block(label: str, arm: dict[str, Any], calls: dict[Key, dict[str, Any]],
              cost: dict[str, dict[Key, dict[str, Any]]]) -> dict[str, Any]:
    eps = arm["episodes"]
    keys = sorted(eps)
    summary = arm["summary"]
    units, unscored = j10.a1_sgc_units(eps, arm["tasks"], list(SEEDS))
    conventions = CONTROL_CONVENTIONS if label in CONTROL_ARMS else J12_CONVENTIONS
    prompts = Counter(str(arm["manifest_extra"].get(k, {}).get("correct_prompt")) for k in keys)
    out: dict[str, Any] = {
        **ARM_INFO.get(label, {}),
        "campaigns": list(arm["spec"]["campaigns"]),
        "seeds": list(arm["spec"]["seeds"]),
        "n_expected": summary["n_expected"],
        "n": summary["n_scored"],
        "n_crash": summary["n_crash"],
        "n_missing": summary["n_missing"],
        "n_other_seed_rows_ignored": arm["n_other_seed_rows_ignored"],
        "goal_pass": summary["goal_pass_mean"],
        "n_goal_pass_missing": summary["n_goal_pass_missing"],
        "tgc": summary["tgc_mean"],
        "sgc": {"mean": _mean(list(units.values())), "n_units": len(units), "n_units_unscored": unscored},
        "success_count": sum(1 for k in keys if eps[k].get("success")),
        "limit": j17p.limit_rate(eps),
        "error_types": summary["error_types"],
        "interventions_per_episode": _mean([calls[k]["interventions"] for k in keys if k in calls]),
        "interventions_total": sum(calls[k]["interventions"] or 0 for k in keys if k in calls),
        "asks_total": sum(calls[k]["asks"] or 0 for k in keys if k in calls),
        "calls": {name: _mean([calls[k][f"calls_{name}"] for k in keys if k in calls]) for name in CALL_NAMES},
        "calls_totals": {name: sum(calls[k][f"calls_{name}"] or 0 for k in keys if k in calls) for name in CALL_NAMES},
        "runner_usd_total_sum": float(sum(calls[k]["runner_usd_total"] or 0.0 for k in keys if k in calls)),
        "prompt_recorded": dict(sorted(prompts.items())),
        "cost": {conv: {axis: _mean([cost.get(conv, {}).get(k, {}).get(axis) for k in keys])
                        for axis in COST_AXES} for conv in conventions},
    }
    out["cost"]["n_keys_priced"] = {conv: len(cost.get(conv, {})) for conv in conventions}
    return out


def _with_calls_live(rows: dict[str, dict[Key, dict[str, Any]]], calls: dict[Key, dict[str, Any]],
                     control: bool) -> dict[str, dict[Key, dict[str, Any]]]:
    """Add calls_live_per_episode to every row (the controls' hosted calls are already live under `live`)."""
    out: dict[str, dict[Key, dict[str, Any]]] = {}
    for conv, conv_rows in rows.items():
        out[conv] = {}
        for k, r in conv_rows.items():
            live = (rows["live"][k]["hosted_calls_per_episode"] if control
                    else (calls.get(k) or {}).get("calls_live"))
            out[conv][k] = dict(r, calls_live_per_episode=None if live is None else float(live))
    return out


# ---- X1 provenance ------------------------------------------------------------
def parse_round1_log(path: Path, campaign: str) -> Optional[dict[str, Any]]:
    """The JSON summary block the hj12 runner prints after '---- summary + manifest (<campaign>) ----'."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    marker = f"---- summary + manifest ({campaign}) ----"
    for i, line in enumerate(lines):
        if marker not in line:
            continue
        start = next((j for j in range(i + 1, len(lines)) if lines[j].strip() == "{"), None)
        if start is None:
            return None
        end = next((j for j in range(start + 1, len(lines)) if lines[j].rstrip() == "}"), None)
        if end is None:
            return None
        try:
            block = json.loads("\n".join(lines[start:end + 1]))
        except json.JSONDecodeError:
            return None
        ledger = block.get("ledger_totals") or {}
        return {"source": f"{_rel(path)}:{start + 1}-{end + 1}", "campaign_id": block.get("campaign_id"),
                "errors": block.get("errors"), "n_broken": block.get("n_broken"),
                "planner_calls_live_total": block.get("planner_calls_live_total"),
                "ledger_planner_calls_total": ledger.get("planner_calls_total"),
                "ledger_usd_total": ledger.get("usd_total")}
    return None


def x1_provenance(arm: dict[str, Any], calls: dict[Key, dict[str, Any]], log_path: Path) -> dict[str, Any]:
    recs = arm["records"]
    early = sorted(k for k, r in recs.items() if str(r["provenance"].get("git_sha") or "").startswith(X1_EARLY_SHA))
    rows = []
    for k in early:
        path = arm["event_paths"].get(k)
        text = path.read_text(encoding="utf-8", errors="replace") if path is not None and path.is_file() else ""
        run = arm["runs"].get(k, {})
        rows.append({"task_id": k[0], "seed": k[1], "git_sha": recs[k]["provenance"].get("git_sha"),
                     "git_dirty": recs[k]["provenance"].get("git_dirty"), "error_type": run.get("error_type"),
                     "goal_pass_rate": run.get("goal_pass_rate"), "calls_ledger": calls.get(k, {}).get("calls_ledger"),
                     "runner_usd_total": calls.get(k, {}).get("runner_usd_total"),
                     "n_run_start": text.count('"run_start"'), "n_usage_limit_mentions": text.lower().count("usage_limit")})
    by_sha = Counter(f"{r['provenance'].get('git_sha')}|dirty={r['provenance'].get('git_dirty')}" for r in recs.values())
    round1 = parse_round1_log(log_path, arm["spec"]["campaigns"][0])
    early_calls = sum(r["calls_ledger"] or 0 for r in rows)
    early_usd = sum(r["runner_usd_total"] or 0.0 for r in rows)
    absent = None
    if round1 and round1.get("ledger_planner_calls_total") is not None and round1.get("ledger_usd_total") is not None:
        absent = {"calls": int(round1["ledger_planner_calls_total"]) - early_calls,
                  "usd": float(round1["ledger_usd_total"]) - early_usd,
                  "rule": ("round 1's ledger totals (all 114 of its rows, 104 of them crashes later purged) minus the "
                           "ledger calls and runner USD of the round-1 episodes that survive in result.json")}
    return {
        "status": "exploratory", "split": "dev",
        "definition": DEFINITIONS["x1_early"],
        "by_git_sha": dict(sorted(by_sha.items())),
        "n_early": len(early), "n_late": len(recs) - len(early),
        "early_keys": [f"{k[0]}/{k[1]}" for k in early],
        "early_episodes": rows,
        "early_calls_ledger_total": early_calls,
        "early_runner_usd_total": early_usd,
        "round1": {"job": X1_ROUND1_JOB, "log": _rel(log_path), "summary": round1,
                   "note": ("round 1 crashed 104 of 114 episodes when the 5 h quota hit 100 % (burn_driver.log:527-529); "
                            "those were purged and rerun in round 2 (25917129); its smoke campaign is not counted")},
        "round1_spend_not_in_result_json": absent,
    }


# ---- ledger confirmation -------------------------------------------------------
def prefix_m11_identity(arms: dict[str, dict[str, Any]], repo_root: Path) -> dict[str, Any]:
    """Recompute CHAN-PRICE-01's prefix_m11 arm mean and its P2 point from the campaigns named here."""
    report = _read_json(repo_root / ADVICE_AT_PRICE)
    out: dict[str, Any] = dict(PREFIX_M11_SOURCE, campaigns=list(PREFIX_M11_SOURCE["campaigns"]))
    if "prefix_m11" not in arms or "correction_k1" not in arms:
        return out
    eps = {label: arms[label]["episodes"] for label in ("correction_k1", "prefix_m11")}
    keys = j17p.common_keys(eps, ("correction_k1", "prefix_m11"))
    series = j10.a1_paired_series({k: eps["correction_k1"][k] for k in keys}, {k: eps["prefix_m11"][k] for k in keys},
                                  "goal_pass_rate")
    mine = 100.0 * statistics.fmean(series["diffs"]) if series["diffs"] else None
    reported = j17p._dig(report, PREFIX_M11_SOURCE["p2_key"])
    out.update(n_scored=arms["prefix_m11"]["summary"]["n_scored"],
               reported_p2_diff_pp=reported, recomputed_p2_diff_pp=mine, n_pairs_p2=len(series["diffs"]),
               p2_match_2dp=None if mine is None or not isinstance(reported, (int, float))
               else round(mine, 2) == round(float(reported), 2))
    return out


def cost_checks(arm_cost: dict[str, dict[str, Any]], repo_root: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    cache: dict[str, Any] = {}
    for chk in COST_CHECKS:
        if chk["arm"] not in arm_cost:
            continue
        rep = cache.setdefault(chk["report"], _read_json(repo_root / chk["report"]))
        reported = j17p._dig(rep, chk["key"])
        mine = arm_cost[chk["arm"]].get("published", {}).get(chk["axis"])
        tol = COST_MATCH_TOL[chk["axis"]]
        match = None if mine is None or not isinstance(reported, (int, float)) else abs(mine - float(reported)) <= tol
        out.append({"arm": chk["arm"], "report": chk["report"], "key": chk["key"], "reported": reported,
                    "recomputed_published": mine, "tolerance": tol, "match": match})
    return out


# ---- report -----------------------------------------------------------------
def build_report(*, results_root: Path = RESULTS_ROOT, arms_spec: Optional[dict[str, dict[str, Any]]] = None,
                 n_boot: int = N_BOOT, seed: int = BOOTSTRAP_SEED, prices: Path = PRICES,
                 x1_log: Path = X1_ROUND1_LOG, repo_root: Path = REPO_ROOT,
                 argv: Optional[list[str]] = None) -> tuple[dict[str, Any], int]:
    """The whole report and its exit code. Raises b2.PoolingError on a key twice in one arm and
    HeldOutSourceError on a replayed plan whose cached_from is a held-out path."""
    spec = dict(arms_spec or ARMS)
    results_root = Path(results_root)
    packet_source = results_root / PACKET_SOURCE
    arms: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for label, s in spec.items():
        print(f"[{PROTOCOL}] loading {label} ...", flush=True)
        arms[label] = load_dev_arm(label, s, results_root)
        sources = replayed_plan_sources(label, arms[label]["dirs"], packet_source)  # refuses before pricing
        arms[label]["replayed_plan_sources"] = sources
        if sources["n_outside_packet_source"]:
            warnings.append(f"arm {label}: {sources['n_outside_packet_source']} replayed plan(s) from outside "
                            f"{PACKET_SOURCE}/{PACKET_SYSTEM}: {sources['by_source']}")
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
    if not packet_source.exists():
        warnings.append(f"packet source {packet_source} is missing: attributed and sft_plan pricing understate")

    calls = {label: {k: episode_calls(a["runs"][k], a["event_paths"].get(k)) for k in a["episodes"]}
             for label, a in arms.items()}

    print(f"[{PROTOCOL}] pricing ...", flush=True)
    card = j17p._j12().load_price_card(prices)
    cost_rows: dict[str, dict[str, dict[Key, dict[str, Any]]]] = {}
    pricing_info: dict[str, Any] = {}
    controls: dict[str, Any] = {}
    for label, a in arms.items():
        if not a["episodes"]:
            cost_rows[label] = {}
            continue
        if label in CONTROL_ARMS:
            priced = control_pricing(label, a, packet_source, card)
            cost_rows[label] = _with_calls_live(priced["rows"], calls[label], control=True)
            controls[label] = priced["block"]
            for k, r in priced["per_episode"].items():  # a local plan call is not a hosted call
                if k in calls[label]:
                    calls[label][k]["calls_live"] = r["live"]["hosted_calls"]
        else:
            system = sorted(a["summary"]["systems_in_tree"])[0]
            rows, info = j12_cost_rows(label, results_root / a["spec"]["campaigns"][0] / system, packet_source, card,
                                       set(a["episodes"]))
            cost_rows[label] = _with_calls_live(rows, calls[label], control=False)
            pricing_info[label] = info
            for conv in J12_CONVENTIONS:
                if "error" in info.get(conv, {}):
                    warnings.append(f"arm {label}: {conv} pricing failed: {info[conv]['error']}")

    per_arm = {label: arm_block(label, a, calls[label], cost_rows.get(label, {})) for label, a in arms.items()}

    print(f"[{PROTOCOL}] contrasts ...", flush=True)
    contrasts = {c["id"]: contrast_block(arms, c, n_boot=n_boot, seed=seed) for c in CONTRASTS
                 if c["left"] in arms and c["right"] in arms}
    for cid, entry in contrasts.items():
        if entry["n_pairs"] != len(SEEDS) * DEV_N_TASKS:
            warnings.append(f"{cid}: {entry['n_pairs']} goal_pass pairs, not {len(SEEDS) * DEV_N_TASKS}")

    x1 = x1_provenance(arms[X1_LABEL], calls[X1_LABEL], x1_log) if X1_LABEL in arms else None
    early = frozenset((str(k.split("/")[0]), int(k.split("/")[1])) for k in (x1 or {}).get("early_keys", []))
    x1_ids = [c for c in CONTRASTS if X1_LABEL in (c["left"], c["right"]) and c["id"] in contrasts]
    x1_sens = {
        "status": "exploratory", "split": "dev", "decision_bearing": False,
        "rule": f"X1's contrasts with its {len(early)} round-1 keys ({X1_EARLY_SHA}, dirty tree) removed from both arms",
        "excluded_keys": sorted(f"{t}/{s}" for t, s in early),
        "contrasts": {c["id"]: contrast_block(arms, c, n_boot=n_boot, seed=seed, exclude=early) for c in x1_ids},
    }

    print(f"[{PROTOCOL}] cost ratios ...", flush=True)
    cost_contrasts: dict[str, Any] = {}
    for left, right in COST_CONTRASTS:
        if left not in arms or right not in arms:
            continue
        keys = j17p.common_keys({left: arms[left]["episodes"], right: arms[right]["episodes"]}, (left, right))
        eps = {left: arms[left]["episodes"], right: arms[right]["episodes"]}
        cost_contrasts[f"{left}_over_{right}"] = {
            "status": "exploratory", "split": "dev", "definition": f"{left} / {right} (and {left} - {right})",
            "n_keys": len(keys),
            "limit_rate": {"left": _limit_pair(eps, left, keys), "right": _limit_pair(eps, right, keys)},
            **{conv: cost_ratio_block(cost_rows[left].get(conv, {}), cost_rows[right].get(conv, {}), keys,
                                      n_boot=n_boot, seed=seed) for conv in J12_CONVENTIONS},
        }

    print(f"[{PROTOCOL}] advice content ...", flush=True)
    content = {}
    for label in ADVICE_ARMS:
        if label in arms:
            block = j17c.content_block(label, arms[label]["event_paths"], n_boot=n_boot, seed=seed)
            block["label"] = "EXPLORATORY (descriptive, as ledger DEC-06 for B2)"
            block["source_function"] = ("scripts/analysis/j17_channel_fixes.py content_block (:358; rows "
                                        "intervention_rows :339; advice copy rule _copied :327)")
            content[label] = block

    report: dict[str, Any] = {
        "protocol": PROTOCOL,
        "label": "EXPLORATORY dev read of the week-A dev arms (R2.4, D2, X1, ctrl_self, ctrl_wrong); nothing here "
                 "decides a registered verdict",
        "brief": BRIEF,
        "status": "INCOMPLETE" if missing else "COMPLETE",
        "warnings": warnings,
    }
    git = git_state()
    report["meta"] = {
        **git,
        "argv": list(argv) if argv is not None else list(sys.argv),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seeds": list(SEEDS),
        "n_boot": n_boot,
        "bootstrap_seed": seed,
        "bootstrap_seed_source": "j17_planning_lit.BOOTSTRAP_SEED = j17_channel_fixes.BOOTSTRAP_SEED = 20260924",
        "results_root": str(results_root),
        "packet_source": str(packet_source),
        "prices": _rel(prices),
        "price_schedule_date": card.get("schedule_date"),
        "status": "exploratory",
        "split": "dev",
    }
    report["arms"] = per_arm
    report["contrasts"] = contrasts
    report["x1_sensitivity"] = x1_sens
    report["x1_provenance"] = x1
    report["cost_contrasts"] = cost_contrasts
    report["controls_pricing"] = {
        "status": "exploratory", "split": "dev",
        "why": ("j12_cost_axes.price_arm_episodes would charge each control row the hj1b luna plan of its own task "
                "(j12_cost_axes.py:361-367) and bill local usage at luna rates (:206-212); j12_cost_axes.py is unchanged "
                "and neither control is fed to it"),
        "decisions": {
            "self_plan": ("the executor's own local (vllm sft_b_plus) plan: $0 hosted, 0 hosted calls and 0 hosted "
                          "tokens under both conventions; local plan calls (usage.n_calls of vllm/mock planner usages) "
                          "and local plan tokens are reported separately"),
            "wrong_task_plan": ("live: the episode's own hosted planner usage ($0, 0 calls, 0 tokens: 0 asks); "
                                "attributed: plus the tokens (j12's noncached_tokens convention, which includes cached "
                                "prompt tokens: settings.definitions.noncached_tokens) and USD of the hj1b plan event "
                                "named by usage.raw.cached_from (map[t]), "
                                "j12_cost_axes.episode_cached_plan_attribution, and its one call"),
        },
        **controls,
    }
    report["replayed_plan_sources"] = {
        "rule": ("every usage.raw.cached_from of a replayed (provider 'cache') plan in every events.jsonl of the arm's "
                 "campaign trees, all seeds; each passed through refuse_path before pricing reads it (a held-out "
                 "source exits 2); by_source is <campaign>/<system>; outside = not under the packet source "
                 f"{PACKET_SOURCE}; seed_dir_mismatch = the source's seed directory differs from the episode's"),
        "packet_source": str(packet_source),
        **{label: a["replayed_plan_sources"] for label, a in arms.items()},
    }
    report["advice_content"] = content
    report["by_fdr"] = by_fdr_block(contrasts)
    report["prefix_m11_identity"] = prefix_m11_identity(arms, repo_root)
    report["ledger_confirmation"] = j17p.ledger_checks(arms, LEDGER_CHECKS, repo_root)
    report["cost_confirmation"] = cost_checks({label: per_arm[label]["cost"] for label in per_arm}, repo_root)
    report["pricing_inputs"] = pricing_info
    report["provenance"] = {label: {"campaigns": a["campaigns"], "by_campaign": j17p.arm_provenance(a)}
                            for label, a in arms.items()}
    report["settings"] = {
        "n_boot": n_boot, "seed": seed, "seeds": list(SEEDS), "results_root": str(results_root),
        "clustering": "scenario (primary: every p and ci95_pp_scenario) and task (ci95_pp_task)",
        "interval": "95% percentile, j10.a1_interval (pairs cluster bootstrap, int(0.025 B), int(0.975 B))",
        "p_value": ("j10.bootstrap_pvalue(scenario means, 0, 'two-sided'); p_signflip_two_sided = "
                    "cluster_inference.registered_signflip over scenarios"),
        "crash_convention": "error_type == 'crash' is dropped from every pair and counted; 'limit' is scored",
        "precision": "floats rounded to 6 dp (j16_robustness.round_floats); `printed` blocks hold the 2 dp pp forms",
        "definitions": DEFINITIONS,
    }
    return j16.round_floats(report), (1 if missing else 0)


# ---- markdown ---------------------------------------------------------------
def _f(x: Any, nd: int = 4) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, (int, float)):
        return f"{x:.{nd}f}" if isinstance(x, float) else str(x)
    return str(x)


def _ci(ci: Any, nd: int = 2) -> str:
    if not ci or ci[0] is None:
        return "—"
    return f"[{ci[0]:+.{nd}f}, {ci[1]:+.{nd}f}]"


def _pp(x: Any) -> str:
    return "—" if x is None else f"{x:+.2f}"


def render_markdown(report: dict[str, Any], json_name: str) -> str:
    lines = [f"# {report['protocol']}: week-A dev arms (EXPLORATORY, dev split)", "",
             f"Source JSON: `{json_name}`. Status **{report['status']}**. git `{report['meta'].get('git_sha')}` "
             f"(dirty={report['meta'].get('git_dirty')}). Seeds {report['meta']['seeds']}; B = {report['meta']['n_boot']}, "
             f"bootstrap seed {report['meta']['bootstrap_seed']}; 95 % percentile intervals, scenario clustering "
             "primary, task secondary. Every contrast: status exploratory, split dev.", ""]
    if report["warnings"]:
        lines += ["**Warnings**", ""] + [f"- {w}" for w in report["warnings"]] + [""]
    lines += ["## Arms", "",
              "| arm | dev id | campaign | n | crash | goal_pass | TGC | SGC | success | limit n (rate) | "
              "interventions/ep | calls live/ep | calls n_planner/ep | tokens/ep (pub; att) | USD/ep (pub or live; att) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for label, a in report["arms"].items():
        cost = a["cost"]
        first = "published" if "published" in cost else "live"
        lines.append(
            f"| {label} | {a.get('dev_arm') or '—'} | `{', '.join(a['campaigns'])}` | {a['n']} | {a['n_crash']} | "
            f"{_f(a['goal_pass'])} | {_f(a['tgc'])} | {_f(a['sgc']['mean'])} | {a['success_count']} | "
            f"{a['limit']['n_limit']} ({_f(a['limit']['rate'])}) | {_f(a['interventions_per_episode'], 2)} | "
            f"{_f(a['calls']['live'], 2)} | {_f(a['calls']['n_planner'], 2)} | "
            f"{_f(cost[first]['noncached_tokens_per_episode'], 0)}; {_f(cost['attributed']['noncached_tokens_per_episode'], 0)} | "
            f"{_f(cost[first]['usd_per_episode'], 6)}; {_f(cost['attributed']['usd_per_episode'], 6)} |")
    lines += ["", "Tokens/ep here and in the cost ratios are j12's inherited `noncached_tokens` axis: input + output + "
              "reasoning with input_tokens taken whole, so cached prompt tokens ARE counted "
              "(`settings.definitions.noncached_tokens`); name that convention wherever the number is quoted."]
    lines += ["", "## Contrasts (left − right, pp)", "",
              "| id | n_pairs | n_dropped | goal_pass | scenario CI | task CI | p | p sign-flip | TGC | TGC scenario CI | "
              "SGC | SGC CI | limit rate L / R (paired) |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cid, c in report["contrasts"].items():
        gp, tg, sg = c["goal_pass"], c["tgc"], c["sgc"]
        lim = c["limit_rate"]
        lines.append(
            f"| {cid}{' ⚠ ' + c['build_caveat'] if c.get('build_caveat') else ''} | {c['n_pairs']} | {c['n_dropped']} | "
            f"{_pp(gp.get('diff_pp'))} | {_ci(gp.get('ci95_pp_scenario'))} | {_ci(gp.get('ci95_pp_task'))} | "
            f"{_f(gp.get('p_two_sided'))} | {_f(gp.get('p_signflip_two_sided'))} | {_pp(tg.get('diff_pp'))} | "
            f"{_ci(tg.get('ci95_pp_scenario'))} | {_pp(sg.get('diff_pp'))} | {_ci(sg.get('ci95_pp_scenario'))} | "
            f"{_f(lim['left']['paired']['rate'])} / {_f(lim['right']['paired']['rate'])} |")
    probes = [(cid, b) for cid, c in report["contrasts"].items() if c.get("goal_pass_boundary_probe")
              for b in c["goal_pass_boundary_probe"]["bounds"]]
    if probes:
        lines += ["", "POOL-04 boundary probes (a goal_pass bound within 1 pp of zero, re-run at the seven POOL-04 "
                  "seeds and at 200,000 resamples):", ""]
        for cid, b in probes:
            seeds = ", ".join(f"{s}: {v:+.2f}" for s, v in b["by_seed_pp"].items())
            lines.append(f"- {cid}, {b['clustering']} {b['side']} {b['bound_pp']:+.2f}: {seeds}; "
                         f"{b['big_n']} resamples {b['bound_big_pp']:+.2f}; sign stable {b['sign_stable']}")
    sens = report["x1_sensitivity"]
    lines += ["", "## X1 sensitivity: round-1 keys excluded", "", sens["rule"] + ".", "",
              "| id | n_pairs | goal_pass | scenario CI | task CI | TGC | TGC scenario CI |", "|---|---|---|---|---|---|---|"]
    for cid, c in sens["contrasts"].items():
        gp, tg = c["goal_pass"], c["tgc"]
        lines.append(f"| {cid} | {c['n_pairs']} | {_pp(gp.get('diff_pp'))} | {_ci(gp.get('ci95_pp_scenario'))} | "
                     f"{_ci(gp.get('ci95_pp_task'))} | {_pp(tg.get('diff_pp'))} | {_ci(tg.get('ci95_pp_scenario'))} |")
    x1 = report.get("x1_provenance") or {}
    r1 = (x1.get("round1") or {}).get("summary") or {}
    absent = x1.get("round1_spend_not_in_result_json") or {}
    lines += ["", "## X1 provenance", "",
              f"- {x1.get('n_early')} episodes at `{X1_EARLY_SHA}` (dirty) and {x1.get('n_late')} later: "
              f"{x1.get('by_git_sha')}.",
              f"- Round 1 (job {X1_ROUND1_JOB}): ledger calls {r1.get('ledger_planner_calls_total')}, USD "
              f"{r1.get('ledger_usd_total')}, errors {r1.get('errors')} [{r1.get('source')}].",
              f"- Of that, not carried by any result.json: {absent.get('calls')} calls, USD {_f(absent.get('usd'), 6)}."]
    lines += ["", "## Cost ratios (paired, left / right)", "",
              "| contrast | convention | axis | mean L | mean R | ratio | scenario CI | task CI | n |",
              "|---|---|---|---|---|---|---|---|---|"]
    for cid, c in report["cost_contrasts"].items():
        for conv in J12_CONVENTIONS:
            for axis, v in c[conv].items():
                lines.append(f"| {cid} | {conv} | {axis} | {_f(v['mean_left'], 6)} | {_f(v['mean_right'], 6)} | "
                             f"{_f(v['ratio_left_over_right'])} | {_ci(v['ratio_ci95_scenario'], 4)} | "
                             f"{_ci(v['ratio_ci95_task'], 4)} | {v['n_pairs']} |")
    cp = report["controls_pricing"]
    lines += ["", "## Controls pricing", ""] + [f"- **{k}**: {v}" for k, v in cp["decisions"].items()]
    for label in CONTROL_ARMS:
        if label in cp:
            b = cp[label]
            lines.append(f"- {label}: live USD/ep {_f(b['live']['usd_per_episode'], 6)}, calls/ep "
                         f"{_f(b['live']['hosted_calls_per_episode'], 2)}; attributed USD/ep "
                         f"{_f(b['attributed']['usd_per_episode'], 6)}, calls/ep {_f(b['attributed']['hosted_calls_per_episode'], 2)}; "
                         f"local plan calls {b['local_plan_calls_total']}; replayed from own task "
                         f"{b['n_replayed_from_own_task']}, other task {b['n_replayed_from_other_task']}; "
                         f"replayed plan sources {b['replayed_from_source_dirs']}, outside the packet source "
                         f"{b['n_cached_from_outside_packet_source']}.")
    rps = report["replayed_plan_sources"]
    lines += ["", "Replayed plan sources (every cached_from, all seeds, each refused if held out): " + "; ".join(
        f"{label} {v['by_source']} (outside {v['n_outside_packet_source']}, seed-dir mismatch "
        f"{v['n_seed_dir_mismatch']})" for label, v in rps.items() if isinstance(v, dict) and "by_source" in v) + "."]
    lines += ["", "## Advice content (descriptive)", "",
              "| arm | interventions | share fenced code | scenario CI | median chars | copy rate |", "|---|---|---|---|---|---|"]
    for label, b in report["advice_content"].items():
        s = b["share_fenced_code"]
        lines.append(f"| {label} | {b['n_interventions']} | {_f(s['share'])} | {_ci(s['ci95_scenario'], 4)} | "
                     f"{_f(b['median_chars'], 1)} | {_f(b['copy_rate'])} |")
    fdr = report["by_fdr"]
    lines += ["", f"## BY-FDR sensitivity (m = {fdr['m_p_two_sided']})", "",
              "| id | goal_pass | p | p_BY | p sign-flip | p_BY sign-flip |", "|---|---|---|---|---|---|"]
    for cid, r in fdr["rows"].items():
        lines.append(f"| {cid} | {_pp(r['diff_pp'])} | {_f(r['p_two_sided'])} | {_f(r['p_by'])} | "
                     f"{_f(r['p_signflip_two_sided'])} | {_f(r['p_by_signflip'])} |")
    pm = report["prefix_m11_identity"]
    lines += ["", "## prefix_m11 identity (CHAN-PRICE-01)", "",
              f"`{', '.join(pm['campaigns'])}` / {pm['system']}, seeds {pm['seeds']}: reported P2 "
              f"{pm.get('reported_p2_diff_pp')} pp, recomputed {_pp(pm.get('recomputed_p2_diff_pp'))} pp "
              f"(match {pm.get('p2_match_2dp')})."]
    lines += ["", "Ledger confirmation: " + "; ".join(
        f"{c['ledger']} {c['arm']} {c['key']} reported {c['reported']} recomputed {_f(c['recomputed_goal_pass_mean'], 6)} "
        f"match {c['match']}" for c in report["ledger_confirmation"]), ""]
    return "\n".join(lines) + "\n"


# ---- CLI ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J17 dev arms (week A): R2.4, D2, X1, ctrl_self, ctrl_wrong (dev, exploratory).")
    p.add_argument("--out", type=Path, required=True, help="report JSON path (the .md is written beside it)")
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    p.add_argument("--results-root", type=Path, default=RESULTS_ROOT,
                   help=f"root holding the campaign directories (default {RESULTS_ROOT})")
    p.add_argument("--prices", type=Path, default=PRICES)
    p.add_argument("--x1-round1-log", type=Path, default=X1_ROUND1_LOG,
                   help="the hj12 job log of X1's round 1 (its summary block holds the crashed round's spend)")
    return p


def _refused(reason: str) -> int:
    print(json.dumps({"protocol": PROTOCOL, "status": "REFUSED", "reason": reason}))
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    md_out = args.out.with_suffix(".md")
    named = [args.out, md_out, args.results_root, args.results_root / PACKET_SOURCE, args.prices, args.x1_round1_log]
    named += [args.results_root / c for s in ARMS.values() for c in s["campaigns"]]
    for path in named:
        if reason := refuse_path(path):
            return _refused(reason)
    for path in (args.out, md_out):
        if reason := refuse_out(path):
            return _refused(reason)
    try:
        report, code = build_report(results_root=args.results_root, n_boot=args.n_boot, seed=args.seed,
                                    prices=args.prices, x1_log=args.x1_round1_log,
                                    argv=["scripts/analysis/j17_dev_arms.py", *raw])
    except (b2.PoolingError, HeldOutSourceError) as exc:
        return _refused(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_out.write_text(render_markdown(report, args.out.name), encoding="utf-8")
    print(json.dumps({"protocol": PROTOCOL, "status": report["status"], "exit_code": code,
                      "warnings": report["warnings"], "by_fdr_m": report["by_fdr"]["m_p_two_sided"],
                      "json": str(args.out), "md": str(md_out)}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
