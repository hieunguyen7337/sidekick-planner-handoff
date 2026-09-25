#!/usr/bin/env python
"""J11: the registered read of the LP-2 planner (P27) on AppWorld test_normal.

Computes ``docs/prereg_j11_lp2_test_20260924.md`` §3-§4: LP's informativeness gate and L1-L5 with
Holm within the planner, POOL-04, the sign-flip sensitivity and the readings, at J11's matrix
(168 test_normal tasks x seeds 1, 2 = 336 pairs, 56 scenario clusters), plus the planless-key
sensitivity and the reporting-only additions of §4 (handoff-only companions of L3-L5, h = h* with the
handoff_occurred flag kept as a sensitivity, scripts/analysis/handoff_control.py; L1's limit
rates, limit split and limit-as-0), and prereg §2's executor-ask counts with J10 A1 Amendment 1 §I's
bound. It chooses nothing.

Every statistic is lp_report.py's, imported: the gate, the contrasts, Holm and the readings
(``evaluate_gate``, ``evaluate_contrast``, ``read_planner``), the key-exclusion sensitivity and its
boundary rule (``key_exclusion_sensitivity``, ``apply_key_exclusion``), and the loader
(``load_campaign``). lp_report reads its matrix size and its Amendment 4 key list from module
globals at call time, so ``lp_matrix`` sets them for the duration of one J11 read and restores them
after; lp_report.py itself is not edited, and its own dev read is unchanged. The reporting-only
additions are j10_report's Amendment 1 functions (``am1_handoff_ni``, ``am1_limit_rates``,
``am1_limit_split``, ``am1_limit_as_zero``), also imported.

Campaign ids are read from the J11 configs (``campaign_id``), never typed here; E is J10's arm 1b,
``j10_executor_alone_bplus_20260924``, as the prereg names it.

  --split test_normal --confirm-heldout-test-split   the registered read (B = 10,000, seed 20260924)
  --split dev --plumbing-check                       the dry-run campaigns (<id>_dryrun) only; a
                                                     plumbing check, never a result
  --split test_challenge                             always refused
  --j10-report PATH              the J10 read's JSON (split test_normal): prints §4's combined statement
                                 (not drawn when that report's status is NOT_RUN)
  --divergent-refill-confirmed   the operator confirms Amendment 2 §B.1's crash-only resumption run

Exit codes
  0  the gate and L1-L5 are complete; readings are drawn
  1  some gate or L contrast lacks its full matrix of non-crashed pairs (INCOMPLETE, counts only), a
     divergent key awaits the refill confirmation (INCOMPLETE), or the prereg §6 abort rule fired (more
     than 16 planless C keys, or C below 336 non-crashed: J11 is reported as not run, NOT_RUN, whichever
     campaigns exist)
  2  protocol error or refusal: split / flags, non-registered settings on test, a held-out marker
     where none may be, a (task_id, seed) key twice in one campaign, an output directory under
     /scratch or inside the results tree
  3  a registered campaign directory does not exist yet (the report names each one). On the registered read
     the report stops there, before any contrast is computed: after prereg §6's abort rule, which reads C
     alone, no other arm is loaded and the JSON names the missing and found campaigns only (R3). A plumbing
     check still computes what its dry-run campaigns allow.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import handoff_control as hc  # noqa: E402
from scripts.analysis import j10_report as j10  # noqa: E402
from scripts.analysis import lp_report as lp  # noqa: E402
from scripts.analysis import replay_divergence as rd  # noqa: E402

PREREG = "docs/prereg_j11_lp2_test_20260924.md"
RESULTS_ROOT = j10.RAW_RESULTS_ROOT
OUT_DIR = REPO_ROOT / "campaign" / "results"
OUT_STEM = {"test_normal": "j11_lp2_test_normal", "dev": "j11_lp2_dev_plumbing_check"}
SEEDS: tuple[int, ...] = (1, 2)
N_TASKS_TEST = 168  # prereg §2: all 168 test_normal tasks, 56 scenario clusters
N_BOOT = lp.N_BOOT
BOOTSTRAP_SEED = lp.BOOTSTRAP_SEED
PLANNER = "P27"  # lp_report's name for Qwen/Qwen3.8-27B-FP8
MODEL = lp.PLANNER_INFO[PLANNER]["model"]
DRYRUN_SUFFIX = "_dryrun"

# prereg §2 table. E is J10's arm 1b, read on the same split.
ARM_ORDER: tuple[str, ...] = ("C", "T", "A", "A1", "M_bplus_6", "M_bplus_11", "M_zs_6", "M_zs_11")
ARM_CONFIGS: dict[str, str] = {
    "C": "configs/j11_planner_alone_cap81_qwen38_27b.yaml",
    "T": "configs/j11_takeover_fixed_k_10.yaml",
    "A": "configs/j11_advise_fixed_k_10_fullctx.yaml",
    "A1": "configs/j11_advise_fixed_k_1_fullctx.yaml",
    "M_bplus_6": "configs/j11_prefix_bplus_m6.yaml",
    "M_bplus_11": "configs/j11_prefix_bplus_m11.yaml",
    "M_zs_6": "configs/j11_prefix_zs_m6.yaml",
    "M_zs_11": "configs/j11_prefix_zs_m11.yaml",
}
E_CAMPAIGN = "j10_executor_alone_bplus_20260924"
E_CONFIG = "configs/j10_executor_alone_bplus.yaml"
ALL_ARMS: tuple[str, ...] = (*ARM_ORDER, "E")

# prereg §4 "Reported beside the predictions": Σd·h / Σh with h from the prefix arm -- for the depth
# spans the deeper (m = 11) arm, as J10 A1 Amendment 1 §B4 reads S6's handoff-only rise. L4's companion
# is A1 Amendment 1 §B1's B1a form: M^bplus_11 − C, so L4's "upper < +7.00 pp" is its "lower > −7.00 pp",
# the margin am1_handoff_ni reads.
HANDOFF_COMPANIONS: tuple[dict[str, Any], ...] = (
    {"id": "L3_handoff_only", "companion_of": "L3", "left": "M_bplus_11", "right": "M_bplus_6",
     "flags_from": "M_bplus_11", "threshold_pp": 0.0, "orientation": "as L3: M^bplus_11 − M^bplus_6"},
    {"id": "L4_handoff_only", "companion_of": "L4", "left": "M_bplus_11", "right": "C",
     "flags_from": "M_bplus_11", "threshold_pp": j10.A1_AM1_NI_MARGIN_PP,
     "orientation": ("negated: M^bplus_11 − C. L4's upper bound < +7.00 pp is this lower bound > −7.00 pp "
                     "(J10 A1 Amendment 1 §B1, B1a)")},
    {"id": "L5_handoff_only", "companion_of": "L5", "left": "M_zs_11", "right": "M_zs_6",
     "flags_from": "M_zs_11", "threshold_pp": 0.0, "orientation": "as L5: M^zs_11 − M^zs_6"},
)
NOT_RUN = "none (J11 not run: more than 5 % of C's episodes are planless, prereg §6)"
NOT_RUN_C = "none (J11 not run: C did not reach 336 non-crashed episodes, prereg §6)"
# LP's texts, rewritten to cite the right documents in J11's output (lp_report.py itself is not edited):
# lp.NONE_GATE_BOUNDARY names "the Amendment 4 key", LP's; J11's planless-key rule is its own §3.
NONE_GATE_BOUNDARY = "none (informativeness gate on the boundary: its verdict differs without C's planless keys, J11 §3)"
HOLM_SCOPE = (f"L1-L5, one Holm family of m = 5 ({PREREG} §3); within this planner, no correction across planners, "
              f"as LP's family ({lp.PREREG}:81-82)")
# prereg §4:105-109: the combined statement with J10's P6 (takeover - correction advice at k = 10, gpt-5.6-luna).
J10_P6_DECIDED = ("supported", "not_supported", "reversed")
COMBINED_PENDING = "combined statement with J10 P6: pending the J10 read"
# A J10 report of this status carries every verdict as "not_run" (the J10 / J11 report contract): not drawn.
J10_NOT_RUN = "NOT_RUN"
COMBINED_J10_NOT_RUN = "combined statement with J10 P6: not drawn: J10 not run"
# Amendment 2 §B.1: a divergent key counts only after at least one crash-only resumption run after the crash was
# first recorded. The result files cannot show that; the operator confirms it (--divergent-refill-confirmed).
REFILL_HOW = (
    "confirm that each prefix arm with a divergent key had at least one crash-only resumption run after the crash "
    "first appeared: resubmit that arm's scripts/pbs/j11_arm.pbs line, which purges the crashed episodes and re-runs "
    "only them; a later job's '[j11] tally cid=... crashed=N' line must show the same keys still crashed. Then "
    "re-run this read with --divergent-refill-confirmed.")
# A1 §5.5 via J11 §3:75: the sign-flip p is set against the bootstrap's unadjusted 95 % interval at the matching
# level -- 0.05 two-sided, 0.025 one-sided (cluster_inference.registered_signflip does not double a one-sided p).
SIGNFLIP_LEVEL = {"two-sided": 0.05, "greater": 0.025, "less": 0.025}

# Amendment 2 (2026-09-25): a prefix replay whose rebuilt world fails its own hash check crashes with
# payload.reason "replay_divergence" on every attempt. The rule is J10 A1 Amendment 5 §B's, applied to the four
# M^r_m arms, the only J11 arms that replay the environment (T, A and A1 replay only C's first plan).
AM2 = f"{PREREG} Amendment 2"
PREFIX_ARMS: tuple[str, ...] = ("M_bplus_6", "M_bplus_11", "M_zs_6", "M_zs_11")

# prereg §2 "Executor asks ... counted and reported", read by J10 A1 Amendment 1 §I (ledger PROV-02): an ask
# answered live is part of the system and is kept; per arm the report gives the episodes that received a
# live answer, the answering calls, and the bound on the arm mean, that episode count / the matrix, in pp.
# A contrast whose bound reaches 1.00 pp has its reading printed with the bound. No reading changes.
ASK_RULE = (f"{PREREG} §2 'Executor asks'; docs/prereg_j10_amendment_20260924.md Amendment 1 §I "
            "(the ledger PROV-02 bound)")
ASK_BOUND_FLAG_PP = 1.00

AMBIGUITIES: list[dict[str, str]] = [
    {"id": "lp_machinery_at_336",
     "what": "The prereg applies LP §3-§4 at 336 pairs; lp_report.py is written for 114.",
     "script_behaviour": ("lp_report's own functions are called with its matrix globals (N_TASKS, SEEDS, "
                          "EXPECTED_PAIRS) and its key list (SENSITIVITY_EXCLUDE) set for the call and "
                          "restored after (j11_report.lp_matrix). lp_report's fixed '114' in two 'why' texts is "
                          "rewritten to 336 in this report; no number changes.")},
    {"id": "planless_sensitivity",
     "what": "prereg §3: every contrast and the gate are also reported with C's planless keys excluded.",
     "script_behaviour": ("The keys are sidekick.agents.planner.planless_source_keys over C (via "
                          "j10.a1_planless_keys), the same list j11_arm.pbs prints. They are dropped from every "
                          "arm and the family re-read by lp.key_exclusion_sensitivity; a gate verdict or reading "
                          "that differs is on the boundary (lp.apply_key_exclusion, LP Amendment 4's rule). No "
                          "planless key: no sensitivity block.")},
    {"id": "handoff_flags_for_depth_spans",
     "what": "'h from the prefix arm' does not say which arm when both sides are prefix arms (L3, L5).",
     "script_behaviour": ("The deeper arm (m = 11), as J10 A1 Amendment 1 §B4 reads S6's handoff-only rise. "
                          "For L3 and L5 the companion carries no NI reading (am1_handoff_ni's −7.00 pp reading "
                          "belongs to L4 only); their interval is reported against 0, descriptively.")},
    {"id": "limit_blocks_scope",
     "what": "L1's limit rate, limit split and limit-as-0 are reporting only (prereg §4).",
     "script_behaviour": "Computed only when L1 is complete; never change L1's reading."},
    {"id": "executor_asks",
     "what": ("prereg §2 says executor asks are 'counted and reported' without a form; J10 A1 Amendment 1 §I "
              "gives one (per arm, beside the contrasts, with the PROV-02 bound)."),
     "script_behaviour": ("Counted from events.jsonl of the attempt that wrote result.json: an intervention "
                          "event from actor planner with payload.forced false is one answered ask. The bound is "
                          "every matrix episode with one or more (crashed ones included, so it is conservative) / "
                          "the matrix, in pp, per arm; a contrast with a side at 1.00 pp or more has the bound "
                          "printed in its reading's sentence. No reading, verdict or completeness changes.")},
    {"id": "abort_rule",
     "what": ("prereg §6: J11 is reported as not run if more than 16 C episodes are planless, or if C cannot reach "
              "336 non-crashed episodes."),
     "script_behaviour": (f"The cap is int(0.05 x the matrix) (16 at 336), as j11_arm.pbs counts it. Above it the "
                          f"status is NOT_RUN (exit 1) and every L reads {NOT_RUN!r}; with C below the matrix of "
                          f"non-crashed episodes, NOT_RUN and {NOT_RUN_C!r}. NOT_RUN is decided before "
                          "MISSING_CAMPAIGNS: after the abort no replay arm starts, so their absence is expected.")},
    {"id": "lp_descriptive_delta_and_planner_strength",
     "what": ("§4:86 applies LP §4 verbatim, whose descriptive block (LP prereg:116-122) has the channel margin "
              "Δ_p = (T_p − A_p) − (T_luna − A_luna) on shared keys and planner strength, each ceiling's mean goal_pass."),
     "script_behaviour": ("Planner strength is reported for P27 only (descriptive.ceiling_goal_pass: C's mean, "
                          "lp_report._mean_block), with luna's test_normal ceiling (J10 arm 3's mean) copied from "
                          "--j10-report when given. Δ_p is NOT computed: lp_report.evaluate_delta needs luna's T and A "
                          "episodes on the same (task_id, seed) keys, which on test_normal are J10's takeover_k10 and "
                          "advise_k10_fullctx campaigns; J11 §2 names neither as a J11 read, so they are not loaded, "
                          "and the J10 report carries no per-episode rows.")},
    {"id": "plumbing_matrix",
     "what": "A dry run covers 3 dev tasks, not the registered matrix.",
     "script_behaviour": ("--plumbing-check reads the <id>_dryrun campaigns on dev at C's own task set; the "
                          "report is labelled PLUMBING CHECK, NOT A RESULT.")},
]


class ProtocolError(lp.ProtocolError):
    """A J11 read the script refuses (exit 2)."""


@contextlib.contextmanager
def lp_matrix(n_tasks: int, seeds: tuple[int, ...], exclude: tuple[tuple[str, int], ...] = ()) -> Iterator[None]:
    """lp_report's module globals at J11's matrix for the duration of one read, then restored."""
    names = ("N_TASKS", "SEEDS", "EXPECTED_PAIRS", "SENSITIVITY_EXCLUDE")
    saved = {name: getattr(lp, name) for name in names}
    try:
        lp.N_TASKS = n_tasks
        lp.SEEDS = tuple(seeds)
        lp.EXPECTED_PAIRS = n_tasks * len(seeds)
        lp.SENSITIVITY_EXCLUDE = {PLANNER: tuple(exclude)} if exclude else {}
        yield
    finally:
        for name, value in saved.items():
            setattr(lp, name, value)


def _rescale_text(obj: Any, expected: int) -> Any:
    """lp_report's texts say '114 non-crashed pairs'; at J11's matrix they mean `expected`."""
    if isinstance(obj, dict):
        return {k: _rescale_text(v, expected) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_rescale_text(v, expected) for v in obj]
    if isinstance(obj, str):
        return obj.replace("114 non-crashed", f"{expected} non-crashed")
    return obj


def protocol_guard(split: str, confirm: bool, plumbing: bool, n_boot: int, seed: int) -> Optional[str]:
    """The refusals that come before anything is read (exit 2)."""
    if split == "test_challenge":
        return f"refusing test_challenge: it stays sealed [{PREREG} §7]"
    if split not in OUT_STEM:
        return f"unknown split {split!r}; J11 reads test_normal (registered) or dev (--plumbing-check)"
    if split == "test_normal":
        if plumbing:
            return "refusing --plumbing-check on test_normal"
        if not confirm:
            return f"refusing test_normal without --confirm-heldout-test-split: J11 is a single read [{PREREG} §6]"
        if (n_boot, seed) != (N_BOOT, BOOTSTRAP_SEED):
            return (f"refusing test_normal with a non-registered bootstrap (n_boot={n_boot}, seed={seed}; "
                    f"registered {N_BOOT} at {BOOTSTRAP_SEED})")
        return None
    if confirm:
        return "--confirm-heldout-test-split names the held-out read; it is refused with --split dev"
    if not plumbing:
        return ("refusing --split dev without --plumbing-check: J11 has no dev read (LP-2's dev read is "
                "lp_report.py's); dev is for the dry-run campaigns only")
    return None


def resolve_campaigns(split: str, repo_root: Path = REPO_ROOT) -> dict[str, dict[str, str]]:
    """{arm code: {config, campaign}}, each campaign read from its config's campaign_id (+ _dryrun on dev)."""
    import yaml

    suffix = "" if split == "test_normal" else DRYRUN_SUFFIX
    out: dict[str, dict[str, str]] = {}
    for code, rel in (*ARM_CONFIGS.items(), ("E", E_CONFIG)):
        try:
            data = yaml.safe_load((repo_root / rel).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ProtocolError(f"{rel}: cannot read campaign_id ({type(exc).__name__}: {exc})") from exc
        cid = data.get("campaign_id") if isinstance(data, dict) else None
        if not isinstance(cid, str) or not cid.strip():
            raise ProtocolError(f"{rel}: no campaign_id")
        if code == "E" and cid != E_CAMPAIGN:
            raise ProtocolError(f"{rel}: campaign_id {cid!r}, but the prereg names E = {E_CAMPAIGN}")
        if code != "E" and not (cid.startswith("j11_") and cid.endswith("_20260924")):
            raise ProtocolError(f"{rel}: campaign_id {cid!r} is not a J11 campaign")
        out[code] = {"config": rel, "campaign": cid + suffix}
    names = [v["campaign"] for v in out.values()]
    if len(set(names)) != len(names):
        raise ProtocolError(f"two arms share a campaign id: {names}")
    return out


def planless_keys(c_dir: Path, seeds: tuple[int, ...] = SEEDS) -> list[tuple[str, int]]:
    """(task_id, seed) of C's episodes scored without a crash whose last attempt wrote no plan."""
    return j10.a1_planless_keys({j10.A1_PLAN_SOURCE_ARM: c_dir}, list(seeds)) or []


def abort_rule(planless: list[tuple[str, int]], c_arm: dict[str, Any], expected: int) -> dict[str, Any]:
    """prereg §6: J11 is not run above int(0.05 x the matrix) planless C keys, or with C below the matrix of
    non-crashed episodes. Reads C alone (its planless keys and its a1_arm_episodes counts)."""
    cap = int(expected * j10.A1_PLANLESS_CAP_FRACTION)
    abort = len(planless) > cap
    c_short = c_arm["n_scored"] < expected
    not_run: list[str] = []
    if abort:
        not_run.append(f"{len(planless)} planless C keys > cap {cap}")
    if c_short:
        not_run.append(f"C has {c_arm['n_scored']}/{expected} non-crashed episodes (crash {c_arm['n_crash']}, "
                       f"missing {c_arm['n_missing']})")
    return {"cap": cap, "abort": abort, "c_short": c_short, "not_run": not_run}


# R3 (2026-09-25): a registered read with a campaign missing stops before any contrast is computed. Its JSON holds
# these keys and nothing else: no gate, contrast, reading, Holm, sensitivity, descriptive or arm statistic.
EARLY_STOP_KEYS: tuple[str, ...] = ("protocol", "label", "split", "status", "headline", "missing_campaigns",
                                    "campaigns_found", "printed")


def stopped_early(report: dict[str, Any]) -> bool:
    """True for R3's early MISSING_CAMPAIGNS report (registered read, nothing computed)."""
    return report.get("status") == "MISSING_CAMPAIGNS" and set(report) <= set(EARLY_STOP_KEYS)


def missing_campaign_stop(report: dict[str, Any], campaigns: dict[str, dict[str, str]],
                          results_root: Path) -> Optional[tuple[dict[str, Any], int]]:
    """R3, on the registered read with a campaign missing: the early MISSING_CAMPAIGNS report (exit 3), built
    before any arm but C is loaded and before anything is computed; or None to continue with the full read.

    None in two cases. (1) prereg §6's abort rule fires: NOT_RUN decides before MISSING_CAMPAIGNS (after the
    abort no replay arm starts, so their absence is expected), and the full read reports it as before. The rule
    needs C alone, so C is loaded first -- the only arm loaded before the stop -- and its planless keys and
    non-crashed count are read exactly as the full read reads them: C's scored episodes lie in C's own tasks, so
    its count over C's tasks equals its count over every arm's (j10.discover_tasks is the union). (2) C's
    campaign holds a key twice: the full read reports that ERROR (exit 2) before computing anything. With C itself
    missing the abort rule has nothing to read and the read stops here."""
    missing = report["missing_campaigns"]
    missing_arms = {m["arm"] for m in missing}
    if "C" in missing_arms:
        c_note = "C's campaign is missing, so prereg §6's abort rule had nothing to read."
    else:
        c_dir = results_root / campaigns["C"]["campaign"]
        try:
            c_loaded = lp.load_campaign("C", c_dir)
        except lp.ProtocolError:
            return None
        c_arm = j10.a1_arm_episodes("C", c_loaded, j10.discover_tasks({"C": c_loaded}, list(SEEDS)), list(SEEDS))
        if abort_rule(planless_keys(c_dir), c_arm, N_TASKS_TEST * len(SEEDS))["not_run"]:
            return None
        c_note = ("C alone was loaded first, for prereg §6's abort rule, which decides before MISSING_CAMPAIGNS; "
                  "it did not fire.")
    names = ", ".join(f"{m['arm']}:{m['campaign']}" for m in missing)
    early = {
        "protocol": "J11",
        "label": report["label"],
        "split": report["split"],
        "status": "MISSING_CAMPAIGNS",
        "headline": f"MISSING CAMPAIGNS: {names}. Stopped before computing anything: no contrast was computed.",
        "missing_campaigns": missing,
        "campaigns_found": [{"arm": code, "campaign": arm["campaign"], "path": str(results_root / arm["campaign"])}
                            for code, arm in campaigns.items() if code not in missing_arms],
        "printed": ("No contrast was computed. The registered read stops when a campaign is missing, before any "
                    "other arm's episodes are loaded: this report carries no gate, contrast, reading, Holm, "
                    f"sensitivity, descriptive or arm statistic. {c_note} Re-run the registered read once every "
                    "campaign exists."),
    }
    return early, 3


def read_family(gate: dict[str, Any], records: dict[str, dict[str, Any]], expected: int) -> dict[str, Any]:
    """LP §3-§4's reading of L1-L5 (lp.read_planner: Holm across the five, m = 5), at J11's matrix. lp's Holm
    scope text cites "prereg:81-82", LP's line; here it names J11 §3 and LP's file."""
    read = _rescale_text(lp.read_planner(gate, records), expected)
    if read["holm"] is not None:
        read["holm"] = dict(read["holm"], scope=HOLM_SCOPE)
    return read


def _handoff_companion(spec: dict[str, Any], arms: dict[str, dict[str, Any]],
                       flags: dict[str, dict[tuple[str, int], Optional[bool]]], *, n_boot: int,
                       seed: int, h: str = hc.HSTAR_NAME) -> dict[str, Any]:
    """j10.am1_handoff_ni on one L contrast; for L3 / L5 its −7.00 pp NI reading is not theirs and is dropped.

    ``flags`` hold the indicator named by ``h``: h* (primary: the executor took control after the
    replayed prefix, scripts/analysis/handoff_control.py) or h_flag (handoff_occurred, the sensitivity)."""
    row = j10.am1_handoff_ni(spec, arms, flags, n_boot=n_boot, seed=seed)
    row["h"] = h
    if h == hc.HSTAR_NAME:
        row["estimand"] = j10.A1_HSTAR_ESTIMAND
    row["citation"] = f"{PREREG} §4 (J10 A1 Amendment 1 §B pattern)"
    if spec["threshold_pp"] != j10.A1_AM1_NI_MARGIN_PP:
        row["margin_pp"] = None
        blk = row.get("goal_pass") or {}
        blk.pop("ni", None)
        blk.pop("p_value_two_sided_at_margin", None)
        ci = (blk.get("handoff_only") or {}).get("ci95_pp_scenario")
        blk["vs_threshold"] = None if ci is None else {
            "threshold_pp": spec["threshold_pp"], "lower_above": bool(ci[0] > spec["threshold_pp"]),
            "descriptive": True}
    return row


def _l1_limits(arms: dict[str, dict[str, Any]], *, n_boot: int, seed: int) -> dict[str, Any]:
    """prereg §4: L1's per-arm limit rate, the either-arm / neither split, and limit-as-0 (J10 A1 Am. 1 §D)."""
    left, right = arms["T"]["episodes"], arms["A"]["episodes"]
    return {
        "reporting_only": True,
        "citation": f"{PREREG} §4 (J10 A1 Amendment 1 §D1-§D3)",
        "limit_rates": j10.am1_limit_rates({"T": arms["T"], "A": arms["A"]}),
        "limit_split": j10.am1_limit_split(left, right, lp.FIELD, n_boot=n_boot, seed=seed),
        "limit_as_zero": j10.am1_limit_as_zero(left, right, n_boot=n_boot, seed=seed),
    }


def _answered_asks_last_attempt(events_path: Path) -> Optional[int]:
    """Executor asks the planner answered live in the attempt that wrote result.json; None without a log.

    An answered ask is the `intervention` event the loop writes after planner.correct() returns: actor
    `planner`, payload.forced False (src/sidekick/systems/loop.py:1066-1079 at the arms' pin 6f40fec; the block
    has moved at HEAD). Every other intervention
    (takeover, a replayed focal correction) carries forced True and is not an ask. Events before the last
    run_start belong to an earlier attempt (as j10._last_report_handoff reads them).
    """
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            ev = json.loads(line) if line.strip() else None
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    start = max((i for i, ev in enumerate(events) if ev.get("event_type") == "run_start"), default=0)
    return sum(1 for ev in events[start:]
               if ev.get("event_type") == "intervention" and ev.get("actor") == "planner"
               and isinstance(ev.get("payload"), dict) and ev["payload"].get("forced") is False)


def answered_asks(root: Path, keys: set[tuple[str, int]]) -> dict[tuple[str, int], Optional[int]]:
    """(task_id, seed) -> live-answered asks, for every result.json of the matrix (first per key, as
    j10.a1_handoff_flags)."""
    out: dict[tuple[str, int], Optional[int]] = {}
    if not root.exists():
        return out
    for path in sorted(root.rglob("result.json")):
        row, _err = j10._read_result(path)
        if row is None or row.get("task_id") is None or row.get("seed") is None:
            continue
        key = (str(row["task_id"]), int(row["seed"]))
        if key in keys and key not in out:
            out[key] = _answered_asks_last_attempt(path.parent / "events.jsonl")
    return out


def executor_asks(arms: dict[str, dict[str, Any]], counts: dict[str, dict[tuple[str, int], Optional[int]]],
                  expected: int) -> dict[str, Any]:
    """Per arm: episodes with a live-answered ask, the calls, and Amendment 1 §I's bound; per contrast:
    the bound of each side. Reporting only."""
    per_arm: dict[str, dict[str, Any]] = {}
    for code in ALL_ARMS:
        by_key = counts.get(code, {})
        asked = {k: n for k, n in by_key.items() if n}
        per_arm[code] = {
            "n_episodes_with_answered_ask": len(asked),
            "n_scored_episodes_with_answered_ask": sum(1 for k in asked if k in arms[code]["episodes"]),
            "n_answered_ask_calls": sum(asked.values()),
            "n_episodes_without_event_log": sum(1 for n in by_key.values() if n is None),
            "bound_pp": round(100.0 * len(asked) / expected, 2) if expected else None,
            "episodes": [f"{s}/{t}" for t, s in sorted(asked)],
        }
    per_contrast: dict[str, dict[str, Any]] = {}
    for spec in (lp.GATE, *lp.CONTRASTS):
        sides = {side: {"arm": spec[side], "bound_pp": per_arm[spec[side]]["bound_pp"]} for side in ("left", "right")}
        worst = max((s["bound_pp"] or 0.0) for s in sides.values())
        per_contrast[spec["id"]] = {**sides, "max_bound_pp": worst, "bound_reaches_1pp": worst >= ASK_BOUND_FLAG_PP}
    return {
        "reporting_only": True,
        "rule": ASK_RULE,
        "definition": ("an intervention event from actor planner with payload.forced false in the attempt that "
                       "wrote result.json; bound = episodes with one or more / the matrix, in pp"),
        "denominator": expected,
        "per_arm": per_arm,
        "per_contrast": per_contrast,
    }


def am2_evaluate_contrast(spec: dict[str, Any], arms: dict[str, dict[str, Any]], *, n_boot: int,
                          seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """lp.evaluate_contrast under Amendment 2 §B.2-§B.3. A contrast that uses a prefix arm with divergent keys
    (j10.a1_am5_arms lists them on the arm) is read with them removed from both arms -- the union for L3 / L5 --
    against §3's 336 minus their number, if it removes at most 16; above that it is INCOMPLETE. Every statistic
    is lp_report's, unchanged. Without a divergent key: lp.evaluate_contrast itself."""
    left, right = spec["left"], spec["right"]
    excluded, verdict = j10.a1_am5_exclusion(arms, left, right)
    if not excluded:
        return lp.evaluate_contrast(spec, arms, n_boot=n_boot, seed=seed)
    if verdict != rd.VERDICT_OK:
        out, _record = lp.evaluate_contrast(spec, arms, n_boot=n_boot, seed=seed)
        why = f"{AM2} §B.3: {len(excluded)} divergent keys to remove > cap {rd.DIVERGENCE_CAP}"
        out = dict(out, status="INCOMPLETE", reason="; ".join(r for r in (out.get("reason"), why) if r))
        return out, {"status": "INCOMPLETE"}
    gone = set(excluded)
    view = dict(arms)
    for code in (left, right):
        episodes = {k: v for k, v in arms[code]["episodes"].items() if k not in gone}
        view[code] = dict(arms[code], episodes=episodes, n_scored=len(episodes))
    saved = lp.EXPECTED_PAIRS
    lp.EXPECTED_PAIRS = saved - len(excluded)
    try:
        return lp.evaluate_contrast(spec, view, n_boot=n_boot, seed=seed)
    finally:
        lp.EXPECTED_PAIRS = saved


def am2_block(arms: dict[str, dict[str, Any]], contrasts: dict[str, dict[str, Any]],
              companions: dict[str, dict[str, Any]], companions_flag: dict[str, dict[str, Any]], *,
              refill_confirmed: bool = False, confirmation_required: bool = False) -> dict[str, Any]:
    """Amendment 2 §B.5, reported regardless of outcome: each prefix arm's divergent keys and their count, zero
    included, and each affected contrast's (and handoff-only companion's) number of pairs.

    §B.1's resumption condition is not readable from the result files, so the operator confirms it
    (--divergent-refill-confirmed): `refill_confirmed_by_operator` is the flag when a divergent key exists, None
    when none does (the flag is then irrelevant)."""
    per_arm = {}
    for code in PREFIX_ARMS:
        if code in arms:
            keys = arms[code].get(j10.A1_AM5_PRIVATE) or []
            per_arm[code] = {"n_divergent": len(keys), "keys": [rd.key_label(k) for k in keys],
                             "n_crash_other": arms[code]["n_crash"] - len(keys), "arm_complete": arms[code]["complete"]}
    affected: dict[str, Any] = {}
    for spec in lp.CONTRASTS:
        excluded, verdict = j10.a1_am5_exclusion(arms, spec["left"], spec["right"])
        if excluded:
            c = contrasts.get(spec["id"]) or {}
            affected[spec["id"]] = {"left": spec["left"], "right": spec["right"], "n_excluded": len(excluded),
                                    "excluded_keys": [rd.key_label(k) for k in excluded], "verdict": verdict,
                                    "n_pairs": c.get("n_pairs"), "n_expected": c.get("n_expected"),
                                    "status": c.get("status")}
    comp: dict[str, Any] = {}
    for spec in HANDOFF_COMPANIONS:
        excluded, _verdict = j10.a1_am5_exclusion(arms, spec["left"], spec["right"])
        if excluded:
            comp[spec["id"]] = {"n_excluded": len(excluded),
                                "n_pairs": ((companions.get(spec["id"]) or {}).get("goal_pass") or {}).get("n_pairs"),
                                "n_pairs_h_flag": ((companions_flag.get(spec["id"]) or {}).get("goal_pass")
                                                   or {}).get("n_pairs")}
    non_replay = {code: [rd.key_label(k) for k in arm[j10.A1_AM5_NONREPLAY]]
                  for code, arm in arms.items() if arm.get(j10.A1_AM5_NONREPLAY)}
    n_total = sum(v["n_divergent"] for v in per_arm.values())
    return {
        "rule": f"{AM2} §B (J10 A1 Amendment 5 §B applied to J11)",
        "decision_bearing": "completeness only: every statistic, the Holm family and every threshold run as registered",
        "definition": rd.DEFINITION,
        "cap": rd.DIVERGENCE_CAP,
        "prefix_arms": list(PREFIX_ARMS),
        "per_arm": per_arm,
        "n_divergent_total": n_total,
        "refill_confirmed_by_operator": bool(refill_confirmed) if n_total else None,
        "resumption_condition": {
            "rule": (f"{AM2} §B.1: a divergent key counts only after at least one crash-only resumption run after "
                     "the crash was first recorded; the result files cannot show it"),
            "required": bool(confirmation_required and n_total),
            "how_to_confirm": REFILL_HOW,
        },
        "contrasts": affected,
        "handoff_only_companions": comp,
        "unaffected": "the gate (C - E) and L1 (T - A) use no prefix arm and keep every pair",
        "non_replay_divergent": {"keys": non_replay,
                                 "treated_as": "an ordinary crash (T, A and A1 replay only C's first plan)"},
        "notes": list(j10.A1_AM5_NOTES[:2]) + [
            "The planless-key sensitivity re-reads each complete contrast on the pairs both arms score, so the "
            "divergent keys are absent from it too.",
            "Not retroactive (§B.6): lp_report.py is not edited, and LP's registered read is unchanged."],
    }


# ---- the J10 read, and §4's combined statement --------------------------------------------------------------
def load_j10_report(path: Optional[Path]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """(the J10 read's JSON, None) or (None, refusal). None path: (None, None). Refused unless it is J10's A1
    report on test_normal with a `verdicts` block (prereg §4:105-109 combines with that read). A J10 report of status
    NOT_RUN (every verdict "not_run") is accepted: the combined statement is then not drawn (combined_statement).
    Any other status must also be the registered read (not_the_j10_result false) with a P6 verdict."""
    if path is None:
        return None, None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"refusing --j10-report {path}: cannot read it as JSON ({type(exc).__name__}: {exc})"
    if not isinstance(data, dict) or data.get("protocol") != "A1":
        protocol = data.get("protocol") if isinstance(data, dict) else None
        return None, f"refusing --j10-report {path}: not a J10 A1 report (protocol {protocol!r})"
    if data.get("split") != "test_normal":
        return None, (f"refusing --j10-report {path}: its split is {data.get('split')!r}; the combined statement "
                      f"needs the J10 read on test_normal [{PREREG} §4]")
    if not isinstance(data.get("verdicts"), dict):
        return None, f"refusing --j10-report {path}: no verdicts block"
    if data.get("status") == J10_NOT_RUN:
        return data, None
    if data.get("not_the_j10_result") is not False:
        return None, f"refusing --j10-report {path}: it declares itself not the J10 result (not_the_j10_result)"
    if "P6" not in data["verdicts"]:
        return None, f"refusing --j10-report {path}: no P6 verdict"
    return data, None


def combined_statement(j10_read: Optional[dict[str, Any]], l1_reading: Any, *, registered: bool,
                       j10_path: Optional[Path] = None) -> dict[str, Any]:
    """prereg §4:105-109. P6 holds iff J10's P6 is 'supported'; L1 holds iff it 'replicates'. Both, exactly one
    (named), or neither ('that is the generality result'). Drawn only when both sides are decided: P6 in
    J10_P6_DECIDED and L1 one of LP's four L1 readings; otherwise the statement says which side is undecided. A J10
    report of status NOT_RUN: not drawn, "J10 not run", whatever L1 reads."""
    rule = f"{PREREG} §4:105-109"
    if j10_read is None:
        return {"status": "pending", "rule": rule, "statement": COMBINED_PENDING}
    p6 = j10_read["verdicts"].get("P6")
    base = {"rule": rule, "j10_report": None if j10_path is None else str(j10_path),
            "j10_label": j10_read.get("label"), "j10_status": j10_read.get("status"), "j10_p6_verdict": p6,
            "j11_l1_reading": l1_reading}
    if j10_read.get("status") == J10_NOT_RUN:
        return base | {"status": "not_drawn", "j10_not_run": True,
                       "j10_not_run_reasons": j10_read.get("not_run_reasons"), "statement": COMBINED_J10_NOT_RUN}
    undecided = []
    if not registered:
        undecided.append("J11 is a plumbing check, not the registered read")
    if p6 not in J10_P6_DECIDED:
        undecided.append(f"J10 P6 is {p6!r}")
    if l1_reading not in lp.L1_READINGS:
        undecided.append(f"J11 L1 has no reading ({l1_reading!r})")
    if undecided:
        return base | {"status": "not_drawn", "statement": ("combined statement with J10 P6: not drawn, "
                                                            + "; ".join(undecided))}
    p6_holds, l1_holds = p6 == "supported", l1_reading == "replicates"
    if p6_holds and l1_holds:
        text = ("J10's P6 is supported (gpt-5.6-luna) and J11's L1 replicates (P27): the channel result holds on "
                "held-out data for two planners.")
    elif p6_holds:
        text = (f"Exactly one holds: J10's P6 is supported (gpt-5.6-luna); J11's L1 does not replicate (P27; "
                f"{l1_reading}).")
    elif l1_holds:
        text = f"Exactly one holds: J11's L1 replicates (P27); J10's P6 is not supported (gpt-5.6-luna; {p6})."
    else:
        text = (f"Neither holds (J10 P6 {p6}, gpt-5.6-luna; J11 L1 {l1_reading}, P27): that is the generality "
                "result.")
    return base | {"status": "drawn", "p6_holds": p6_holds, "l1_holds": l1_holds, "statement": text}


# ---- A1 §5.5 via §3:75: a disagreeing sign-flip goes in the verdict's sentence ----------------------------------
def signflip_disagreement(c: dict[str, Any], spec: dict[str, Any]) -> Optional[dict[str, Any]]:
    """The sign-flip p against the bootstrap verdict, like with like (the rule of j12_report.j12_signflip_disagreement):
    the bootstrap side is the unadjusted 95 % scenario interval's event against the threshold on the side(s) the
    sign-flip's alternative can reach; the sign-flip side is its p at SIGNFLIP_LEVEL, in the direction of the point
    estimate when two-sided. None for an incomplete contrast or without a p."""
    scen, p = c.get("scenario") or {}, (c.get("signflip") or {}).get("p_value")
    if c.get("status") != "COMPLETE" or p is None or scen.get("lo") is None:
        return None
    alt = spec["signflip_alternative"]
    level = SIGNFLIP_LEVEL.get(alt, 0.05)
    t = float(spec["threshold_pp"]) / 100.0
    lo, hi, point = float(scen["lo"]), float(scen["hi"]), float(scen["point"])
    boot = ("above" if lo > t and alt in ("two-sided", "greater")
            else "below" if hi < t and alt in ("two-sided", "less") else None)
    flip = None
    if float(p) <= level + 1e-12:
        flip = ("above" if alt == "greater" else "below" if alt == "less"
                else None if point == t else "above" if point > t else "below")
    out: dict[str, Any] = {
        "rule": "J10 A1 §5.5 (J11 §3:75): a disagreement is reported in the same sentence as the reading",
        "basis": (f"bootstrap: the unadjusted 95 % scenario interval against {spec['threshold_pp']:+.2f} pp; "
                  f"sign-flip: its p at {level} ({alt})"),
        "p_value": p, "alternative": alt, "level": level, "bootstrap_side": boot, "signflip_side": flip,
        "agrees": boot == flip, "sentence": None}
    if boot != flip:
        if boot and flip:
            what = f"rejects at {level} on the {flip} side while the bootstrap interval lies {boot} the threshold"
        elif boot:
            what = f"does not reject at {level} while the bootstrap interval excludes {spec['threshold_pp']:+.2f} pp"
        else:
            what = f"rejects at {level} while the bootstrap interval includes {spec['threshold_pp']:+.2f} pp"
        out["sentence"] = f"the scenario sign-flip p = {float(p):.4g} ({alt}) {what} (A1 §5.5; not decision-bearing)"
    return out


# ---- the planless-key sensitivity at J11's counts (prereg §3, Amendment 2 §B.2) --------------------------------
def sensitivity_expected(arms: dict[str, dict[str, Any]], planless: list[tuple[str, int]],
                         expected: int) -> dict[str, int]:
    """Per row, the pairs the sensitivity expects: the matrix minus C's planless keys and that contrast's divergent
    keys (their union). lp_report's single n_expected subtracts the planless keys only; the gate and L1 use no
    prefix arm, so theirs is that number."""
    gone = set(planless)
    out = {"gate": expected - len(gone)}
    for spec in lp.CONTRASTS:
        excluded, _verdict = j10.a1_am5_exclusion(arms, spec["left"], spec["right"])
        out[spec["id"]] = expected - len(gone | set(excluded))
    return out


def j11_boundary_texts(gate_before: dict[str, Any], read_before: dict[str, Any], gate: dict[str, Any],
                       read: dict[str, Any], sensitivity: Optional[dict[str, Any]],
                       contrasts: dict[str, dict[str, Any]], n_x: dict[str, int],
                       expected: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """lp.apply_key_exclusion decides which verdict or reading is on the boundary; its texts cite LP's Amendment 4
    and count every row against the matrix minus the planless keys. Rewritten here, per row, to cite J11 §3 and
    count each contrast's own pairs (with and without the keys), divergent keys removed. No decision changes."""
    if sensitivity is None:
        return gate, read
    keys = ", ".join(sensitivity["excluded_keys"])
    cite = f"{PREREG} §3"
    if gate.get("verdict") == lp.ON_BOUNDARY and gate_before.get("verdict") != lp.ON_BOUNDARY:
        why = (f"{cite}: the gate reads {gate_before.get('verdict')!r} on {expected} pairs but "
               f"{sensitivity['gate'].get('verdict')!r} without {keys} ({n_x['gate']} pairs)")
        gate = dict(gate, why=why)
        readings = {c: {"reading": NONE_GATE_BOUNDARY, "why": why + "; no reading is drawn from L1-L5"}
                    for c in lp.L_IDS}
        return gate, dict(read, readings=readings)
    readings = {c: dict(r) for c, r in read["readings"].items()}
    for c in lp.L_IDS:
        r_all = read_before["readings"][c]["reading"]
        if readings[c]["reading"] != lp.ON_BOUNDARY or r_all == lp.ON_BOUNDARY:
            continue
        r_x = sensitivity["contrasts"][c].get("reading")
        n_all = contrasts[c].get("n_expected", expected)
        readings[c] = {"reading": lp.ON_BOUNDARY,
                       "why": (f"{cite}: reads {r_all!r} on {n_all} pairs but {r_x!r} without {keys} "
                               f"({n_x[c]} pairs); on the boundary, never resolved")}
    return gate, dict(read, readings=readings)


def build_report(
    *,
    split: str,
    confirm_heldout_test_split: bool = False,
    plumbing_check: bool = False,
    results_root: Path = RESULTS_ROOT,
    n_boot: int = N_BOOT,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    repo_root: Path = REPO_ROOT,
    j10_report_path: Optional[Path] = None,
    divergent_refill_confirmed: bool = False,
) -> tuple[dict[str, Any], int]:
    report: dict[str, Any] = {
        "protocol": "J11",
        "prereg": PREREG,
        "replicates": lp.PREREG,
        "split": split,
        "planner": {"code": PLANNER, "model": MODEL},
        "plumbing_check": plumbing_check,
        "results_root": str(results_root),
    }
    refusal = protocol_guard(split, confirm_heldout_test_split, plumbing_check, n_boot, bootstrap_seed)
    j10_read, j10_refusal = load_j10_report(j10_report_path)
    refusal = refusal or j10_refusal
    if refusal:
        report.update(status="REFUSED", exit_code=2, headline=refusal, errors=[refusal])
        return report, 2
    registered = split == "test_normal"
    report["label"] = ("J11 registered read (test_normal)" if registered
                       else "PLUMBING CHECK, NOT A RESULT (dev dry-run campaigns)")
    errors: list[str] = []
    try:
        campaigns = resolve_campaigns(split, repo_root)
    except lp.ProtocolError as exc:
        errors.append(str(exc))
        campaigns = {}
    report["campaigns"] = campaigns
    for code, arm in campaigns.items():
        marker = j10.heldout_marker_in_path(results_root / arm["campaign"])
        if marker and (marker != "test_normal" or split != "test_normal"):
            errors.append(f"refusing campaign {arm['campaign']} of arm {code}: path contains {marker!r} "
                          f"while --split={split}")
    report["missing_campaigns"] = [
        {"arm": code, "campaign": arm["campaign"], "path": str(results_root / arm["campaign"])}
        for code, arm in campaigns.items() if not (results_root / arm["campaign"]).is_dir()]
    if errors:
        report.update(status="ERROR", exit_code=2, errors=errors, headline="ERROR: " + "; ".join(errors))
        return report, 2
    # R3: on the registered read a missing campaign stops here, before any contrast (after §6's C-only abort rule).
    if registered and report["missing_campaigns"]:
        early = missing_campaign_stop(report, campaigns, results_root)
        if early is not None:
            return early
    loaded: dict[str, dict[str, Any]] = {}
    for code in ALL_ARMS:
        try:
            loaded[code] = lp.load_campaign(code, results_root / campaigns[code]["campaign"])
        except lp.ProtocolError as exc:
            errors.append(str(exc))
    if errors:
        report.update(status="ERROR", exit_code=2, errors=errors, headline="ERROR: " + "; ".join(errors))
        return report, 2

    # The matrix: all 168 test tasks, or on a plumbing check C's own dry-run tasks.
    tasks = j10.discover_tasks(loaded if registered else {"C": loaded["C"]}, list(SEEDS))
    n_tasks = N_TASKS_TEST if registered else max(len(tasks), 1)
    expected = n_tasks * len(SEEDS)
    reasons: list[str] = []
    if len(tasks) != n_tasks:
        reasons.append(f"task_count_is_{len(tasks)}_expected_{n_tasks}")
    for code in ALL_ARMS:
        counts = loaded[code]["campaign"]["split_provenance"]
        wrong = {k: v for k, v in counts.items() if k not in {split, "unrecorded"}}
        if wrong:
            reasons.append(f"split_provenance_mismatch:{code}:{loaded[code]['campaign']['campaign']}={wrong}")
        if registered and counts.get("unrecorded"):
            reasons.append(f"split_provenance_unrecorded:{code}={counts['unrecorded']}")
    # Amendment 2 §B.1 / §B.3: a prefix arm whose only crashes are divergent keys is complete.
    arms = j10.a1_am5_arms({code: j10.a1_arm_episodes(code, loaded[code], tasks, list(SEEDS)) for code in ALL_ARMS},
                           {code: results_root / campaigns[code]["campaign"] for code in ALL_ARMS}, tasks,
                           list(SEEDS), replay_arms=PREFIX_ARMS)
    for arm in arms.values():
        # A matrix of the wrong size or from the wrong split cannot be complete at any count.
        arm["complete"] = bool(arm["complete"] and not reasons and arm["n_expected"] == expected)

    c_dir = results_root / campaigns["C"]["campaign"]
    planless = planless_keys(c_dir)
    # prereg §6:151: J11 is also not run if C cannot reach the matrix of non-crashed episodes (336 on test).
    rule = abort_rule(planless, arms["C"], expected)
    cap, abort, c_short, not_run = rule["cap"], rule["abort"], rule["c_short"], rule["not_run"]
    contingency = {"rule": f"{PREREG} §2, §3, §6", "source_arm": "C", "cap": cap,
                   "keys": [f"{s}/{t}" for t, s in planless], "n_keys": len(planless),
                   "abort_rule_fired": abort, "c_below_matrix": c_short}

    with lp_matrix(n_tasks, SEEDS, tuple(planless)):
        gate = lp.evaluate_gate(arms, n_boot=n_boot, seed=bootstrap_seed)
        contrasts: dict[str, dict[str, Any]] = {}
        records: dict[str, dict[str, Any]] = {}
        for spec in lp.CONTRASTS:
            contrasts[spec["id"]], records[spec["id"]] = am2_evaluate_contrast(
                spec, arms, n_boot=n_boot, seed=bootstrap_seed)
        read = read_family(gate, records, expected)
        sensitivity = lp.key_exclusion_sensitivity(PLANNER, arms, gate, records, n_boot=n_boot,
                                                   seed=bootstrap_seed)
        gate_before, read_before = gate, read
        gate, read = lp.apply_key_exclusion(gate, read, sensitivity)
    gate = _rescale_text(gate, expected)
    if sensitivity is not None:
        # Amendment 2 §B.2: a contrast's divergent keys are gone from the sensitivity too, so each row expects the
        # matrix minus the planless keys and its own divergent keys; the texts cite J11 §3, not LP's Amendment 4.
        n_x = sensitivity_expected(arms, planless, expected)
        gate, read = j11_boundary_texts(gate_before, read_before, gate, read, sensitivity, contrasts, n_x, expected)
        sensitivity = dict(
            sensitivity, citation=f"{PREREG} §3 (the rule lp_report.apply_key_exclusion applies)",
            label=("SENSITIVITY (C's planless keys excluded): not decision-bearing, except "
                   "that a verdict or reading that differs is on the boundary"),
            n_expected_note=("n_expected is the matrix minus the planless keys, the gate's and L1's count; a "
                             "contrast with divergent keys (Amendment 2) expects fewer: each row's n_expected"),
            gate=dict(sensitivity["gate"], n_expected=n_x["gate"]),
            contrasts={c: dict(row, n_expected=n_x[c]) for c, row in sensitivity["contrasts"].items()},
            holm=None if sensitivity.get("holm") is None else dict(sensitivity["holm"], scope=HOLM_SCOPE))
    if not_run:
        reading = NOT_RUN if abort else NOT_RUN_C
        read = dict(read, readings={c: {"reading": reading, "why": (
            "; ".join(not_run) + "; no replay arm was to start")} for c in lp.L_IDS})
    for c in lp.L_IDS:
        contrasts[c]["reading"] = read["readings"][c]["reading"]
        contrasts[c]["reading_why"] = read["readings"][c]["why"]
        if read["holm"] is not None:
            contrasts[c]["p_holm"] = read["holm"]["p"][c]["p_holm"]
            contrasts[c]["holm_rejects"] = read["holm"]["p"][c]["rejects_at_alpha"]
        # A1 §5.5: a disagreeing sign-flip p is stated in the reading's sentence (not decision-bearing).
        sf = None if not_run else signflip_disagreement(contrasts[c], lp.CONTRAST_BY_ID[c])
        contrasts[c]["signflip_disagreement"] = sf
        read["readings"][c]["signflip_disagreement"] = None if sf is None else sf["sentence"]
    contrasts = _rescale_text(contrasts, expected)

    # Reporting only (prereg §4): never changes a reading.
    # h* (the executor took control after the replayed prefix) is primary; the flag (handoff_occurred,
    # h_flag) is kept as a sensitivity (unit HSTAR, 2026-09-24).
    flags = {code: j10.a1_handoff_flags(results_root / campaigns[code]["campaign"])
             for code in {s["flags_from"] for s in HANDOFF_COMPANIONS}}
    controls = {code: hc.arm_control(results_root / campaigns[code]["campaign"]) for code in sorted(flags)}
    hstar = {code: {k: c[hc.HSTAR_NAME] for k, c in ctl.items()} for code, ctl in controls.items()}
    companions, companions_flag = {}, {}
    for spec in HANDOFF_COMPANIONS:
        if contrasts[spec["companion_of"]]["status"] != "COMPLETE":
            companions[spec["id"]] = companions_flag[spec["id"]] = {
                **spec, "status": "not_computed", "reason": f"{spec['companion_of']} is incomplete"}
        else:
            companions[spec["id"]] = _handoff_companion(spec, arms, hstar, n_boot=n_boot, seed=bootstrap_seed,
                                                        h=hc.HSTAR_NAME)
            companions_flag[spec["id"]] = _handoff_companion(spec, arms, flags, n_boot=n_boot,
                                                             seed=bootstrap_seed, h=hc.HFLAG_NAME)
    control_counts = {code: hc.control_counts(controls[code], keys=arms[code]["episodes"].keys())
                      for code in sorted(controls)}
    l1_limits = (_l1_limits(arms, n_boot=n_boot, seed=bootstrap_seed)
                 if contrasts["L1"]["status"] == "COMPLETE"
                 else {"status": "not_computed", "reason": "L1 is incomplete"})
    matrix = {(t, s) for t in tasks for s in SEEDS}
    asks = executor_asks(arms, {code: answered_asks(results_root / campaigns[code]["campaign"], matrix)
                                for code in ALL_ARMS}, expected)

    # Amendment 2 §B.1: on the registered read a divergent key needs the operator's confirmation of a crash-only
    # resumption run; without it the read is INCOMPLETE.
    am2 = am2_block(arms, contrasts, companions, companions_flag, refill_confirmed=divergent_refill_confirmed,
                    confirmation_required=registered)
    incomplete = list(reasons)
    if gate["status"] != "COMPLETE":
        incomplete.append(f"gate {gate['reason']}")
    incomplete += [f"{c} {contrasts[c]['reason']}" for c in lp.L_IDS if contrasts[c]["status"] != "COMPLETE"]
    if am2["resumption_condition"]["required"] and not divergent_refill_confirmed:
        incomplete.append(f"divergent_keys_need_refill_confirmation:{am2['n_divergent_total']}")
    summary = f"gate {gate['verdict']}, L1 {read['readings']['L1']['reading']}"
    missing = report["missing_campaigns"]
    # prereg §6: NOT_RUN is decided first. After the abort no replay arm starts (j11_arm.pbs refuses them), so
    # their campaigns are absent by design and MISSING_CAMPAIGNS would misname the outcome.
    if not_run:
        status, code = "NOT_RUN", 1
        headline = "NOT RUN (prereg §6 abort rule): " + "; ".join(not_run)
    elif missing:
        status, code = "MISSING_CAMPAIGNS", 3
        headline = "MISSING CAMPAIGNS: " + ", ".join(f"{m['arm']}:{m['campaign']}" for m in missing) + f". {summary}"
    elif incomplete:
        status, code = "INCOMPLETE", 1
        headline = "INCOMPLETE: " + "; ".join(incomplete) + f". {summary}"
    else:
        status, code = "COMPLETE", 0
        headline = f"COMPLETE: {summary}"
    if not registered:
        headline = "PLUMBING CHECK, NOT A RESULT. " + headline
    report.update(
        status=status,
        exit_code=code,
        headline=headline,
        errors=[],
        settings={
            "unit": "paired episode, key (task_id, seed)",
            "n_tasks": n_tasks,
            "seeds": list(SEEDS),
            "expected_pairs": expected,
            "metric": "goal_pass (field goal_pass_rate) decision-bearing; TGC secondary",
            "bootstrap": {"n": n_boot, "seed": bootstrap_seed,
                          "registered": (n_boot, bootstrap_seed) == (N_BOOT, BOOTSTRAP_SEED),
                          "primary_clustering": "scenario", "secondary_clustering": "task"},
            "multiplicity": {"method": "Holm step-down", "family": list(lp.L_IDS), "m": len(lp.L_IDS),
                             "alpha": lp.ALPHA},
            "pool04": {"window_pp": j10.POOL04_WINDOW_PP, "seeds": list(j10.POOL04_SEEDS)},
            "signflip": "j10.a1_permutation: scenario clusters; exact if 2^G <= 2^20, else 100,000 Monte Carlo patterns",
            "crash_convention": "drop only error_type == 'crash'; every other error_type is scored",
            "machinery": "scripts/analysis/lp_report.py functions, at this matrix (j11_report.lp_matrix)",
        },
        n_tasks_observed=len(tasks),
        incomplete=incomplete,
        not_run_reasons=not_run,
        planless=contingency,
        gate=gate,
        contrasts=contrasts,
        holm=read["holm"],
        readings=read["readings"],
        combined_with_j10=combined_statement(j10_read, read["readings"]["L1"]["reading"], registered=registered,
                                             j10_path=j10_report_path),
        sensitivity_planless=sensitivity,
        descriptive={
            "label": f"DESCRIPTIVE: no direction, no verdict ({PREREG} §4:86; {lp.PREREG}:116-122)",
            "ceiling_goal_pass": {"planner": PLANNER, **lp._mean_block(arms["C"], campaigns["C"]["campaign"])},
            "ceiling_goal_pass_luna": _luna_ceiling(j10_read),
            "delta_vs_luna": {"status": "not_computed", "reason": (
                "lp_report.evaluate_delta needs luna's T and A on the same keys (on test_normal J10's takeover_k10 "
                "and advise_k10_fullctx), which J11 does not read; see AMBIGUITIES "
                "lp_descriptive_delta_and_planner_strength")},
        },
        reporting_only={
            "label": "REPORTED BESIDE THE PREDICTIONS: not decision-bearing (prereg §4)",
            "handoff_only": companions,
            "handoff_only_h_flag": companions_flag,
            "handoff_indicator": {"primary": hc.HSTAR_NAME, "sensitivity": hc.HFLAG_NAME,
                                  "h_star": hc.DEFINITION, "h_flag": hc.FLAG_DEFINITION},
            "handoff_control_counts": control_counts,
            "L1_limit": l1_limits,
            "executor_asks": asks,
        },
        arms={code: {**{k: v for k, v in arms[code].items() if k != "episodes"},
                     "campaign": loaded[code]["campaign"]} for code in ALL_ARMS},
        ambiguities=AMBIGUITIES,
        j11_am2_divergence=am2,
    )
    return j10._strip_internal(report), code


def _luna_ceiling(j10_read: Optional[dict[str, Any]]) -> dict[str, Any]:
    """LP §4's planner strength for luna on test_normal: J10 arm 3's mean goal_pass, copied from the J10 read."""
    arm = ((j10_read or {}).get("arms") or {}).get(j10.A1_PLAN_SOURCE_ARM) or {}
    if not j10_read:
        return {"status": "not_available", "reason": "needs --j10-report (J10 arm 3's mean goal_pass)"}
    if arm.get("goal_pass_mean") is None:
        return {"status": "not_available", "reason": (f"the J10 report (status {j10_read.get('status')}) carries no "
                                                      f"goal_pass_mean for {j10.A1_PLAN_SOURCE_ARM}")}
    return {"planner": "gpt-5.6-luna", "arm": j10.A1_PLAN_SOURCE_ARM, "source": "--j10-report arms",
            **{k: arm.get(k) for k in ("goal_pass_mean", "n_scored", "n_expected", "complete")}}


# ---- markdown -----------------------------------------------------------------------
def render_markdown(report: dict[str, Any], json_path: Optional[Path] = None) -> str:
    """Every number below is read from `report` (the JSON), never recomputed."""
    L: list[str] = ["# J11: the LP-2 planner on test_normal", ""]
    if stopped_early(report):
        # R3: the registered read stopped at a missing campaign; nothing below the headline exists.
        return "\n".join(L + [f"**Status: {report['status']}** (exit 3). {report['headline']}"]) + "\n"
    L.append(f"Registered analysis of `{report['prereg']}` (replicating `{report['replicates']}`). Generated by "
             "`scripts/analysis/j11_report.py`" + (f"; JSON: `{json_path}`." if json_path else "."))
    L += ["", f"**Status: {report['status']}** (exit {report['exit_code']}). {report['headline']}", ""]
    if report.get("errors"):
        L.append("## Errors")
        L += [f"- {e}" for e in report["errors"]] + [""]
        return "\n".join(L) + "\n"
    L.append(f"Label: {report['label']}. Planner {report['planner']['code']} ({report['planner']['model']}).")
    if report.get("missing_campaigns"):
        L += ["", "## Missing campaigns"]
        L += [f"- {m['arm']}: `{m['campaign']}` (no directory at `{m['path']}`)" for m in report["missing_campaigns"]]
    s = report["settings"]
    g = report["gate"]
    ask_pc = ((report.get("reporting_only") or {}).get("executor_asks") or {}).get("per_contrast", {})

    def _ask_note(cid: str) -> str:
        """J10 A1 Amendment 1 §I: a bound of 1.00 pp or more is printed in the same sentence as the reading."""
        row = ask_pc.get(cid)
        if not row or not row["bound_reaches_1pp"]:
            return ""
        sides = ", ".join(f"{side['arm']} {side['bound_pp']:.2f} pp" for side in (row["left"], row["right"]))
        return (f"; live-answered executor asks bound the arm means at {sides} (J10 A1 Amendment 1 §I, "
                "no reading changes)")

    def _signflip_note(r: dict[str, Any]) -> str:
        """J10 A1 §5.5 (J11 §3:75): a disagreeing sign-flip p is stated in the reading's sentence."""
        return f"; {r['signflip_disagreement']}" if r.get("signflip_disagreement") else ""

    L += ["", "## Gate and L1-L5", ""]
    if g["status"] != "COMPLETE":
        L.append(f"**Gate** C - E: INCOMPLETE ({g['reason']}); {g['why']}.")
    else:
        L.append(f"**Gate** C - E: {g['point_pp']:+.2f} pp over {g['n_pairs']} pairs, scenario CI "
                 f"{lp._ci(g['scenario'])}, task CI {lp._ci(g['task'])}, sign-flip p ('greater') "
                 f"{lp._p(g['signflip'].get('p_value'))} -> **{g['verdict']}** ({g['why']}{_ask_note('gate')}).")
    L += ["", f"95% percentile intervals, B = {s['bootstrap']['n']:,}, seed {s['bootstrap']['seed']}; Holm across "
              "L1-L5 " + (f"(m = {report['holm']['m']})." if report["holm"] else "(not computed: family incomplete)."),
          "", "| L | contrast | predicted | n pairs | point (pp) | scenario CI (pp) | task CI (pp) | p raw | p Holm "
              "| POOL-04 | sign-flip p | reading |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cid, c in report["contrasts"].items():
        if c["status"] != "COMPLETE":
            L.append(f"| {cid} | {c['definition']} | {c['predicted']} | {c['n_pairs']}/{c['n_expected']} "
                     f"| INCOMPLETE: {c['reason']} | | | | | | | {c['reading']} |")
            continue
        L.append(f"| {cid} | {c['definition']} | {c['predicted']} | {c['n_pairs']} | {c['point_pp']:+.2f} "
                 f"| {lp._ci(c['scenario'])} | {lp._ci(c['task'])} | {lp._p(c['p_raw'])} | {lp._p(c.get('p_holm'))} "
                 f"| {lp._pool_txt(c['pool04'])} | {lp._p(c['signflip'].get('p_value'))} | {c['reading']} |")
    L += ["", "Readings:"] + [f"- {cid}: **{r['reading']}** ({r['why']}{_ask_note(cid)}{_signflip_note(r)})"
                              for cid, r in report["readings"].items()]
    comb = report.get("combined_with_j10") or {}
    L += ["", f"## Combined statement with J10 P6 ({comb.get('rule', PREREG + ' §4:105-109')})", "",
          comb.get("statement", COMBINED_PENDING)]
    p = report["planless"]
    L += ["", f"Planless C keys: {p['n_keys']} (cap {p['cap']})" + (f": {', '.join(p['keys'])}" if p["keys"] else "") + "."]
    sens = report.get("sensitivity_planless")
    if sens:
        L += ["", f"Sensitivity without {', '.join(sens['excluded_keys'])} ({sens['n_expected']} pairs). {sens['label']}. "
                  f"{sens['n_expected']} is the gate's and L1's count; each row's n expected also drops that contrast's "
                  f"divergent keys ({AM2} §B.2).",
              "", "| contrast | n pairs | n expected | point (pp) | scenario CI (pp) | reading without the keys |",
              "|---|---|---|---|---|---|"]
        sg = sens["gate"]
        if sg.get("status") == "COMPLETE":
            L.append(f"| gate C - E | {sg['n_pairs']} | {sg.get('n_expected', '-')} | {sg['point_pp']:+.2f} "
                     f"| {lp._ci(sg['scenario'])} | {sg['verdict']} |")
        for cid, c in sens["contrasts"].items():
            if c.get("status") == "COMPLETE":
                L.append(f"| {cid} | {c['n_pairs']} | {c.get('n_expected', '-')} | {c['point_pp']:+.2f} "
                         f"| {lp._ci(c['scenario'])} | {c['reading']} |")
            else:
                L.append(f"| {cid} | - | {c.get('n_expected', '-')} | - | - | incomplete |")
    ro = report["reporting_only"]
    L += ["", "## Reported beside the predictions (not decision-bearing)", "",
          "Handoff-only companions: h = h*, the executor took control after the replayed prefix "
          "(scripts/analysis/handoff_control.py), with the handoff_occurred version (h_flag, J11 Amendment 1) beside "
          "each; both are in the JSON under `reporting_only.handoff_only` and `reporting_only.handoff_only_h_flag`.", "",
          "| companion | orientation | h | n pairs | n handoff | handoff-only (pp) | scenario CI (pp) | reading |",
          "|---|---|---|---|---|---|---|---|"]
    flag_rows = ro.get("handoff_only_h_flag") or {}
    for cid, row in ro["handoff_only"].items():
        for h_name, row_ in (("h*", row), ("handoff_occurred", flag_rows.get(cid) or {})):
            gp = row_.get("goal_pass") or {}
            ho = gp.get("handoff_only") or {}
            if row_.get("status") == "not_computed" or not ho:
                L.append(f"| {cid} | {row['orientation']} | {h_name} | - | - | not computed "
                         f"({row_.get('reason', gp.get('error'))}) | | |")
                continue
            ci = ho.get("ci95_pp_scenario")
            reading = (gp.get("ni") or {}).get("reading") or (
                "lower > 0" if (gp.get("vs_threshold") or {}).get("lower_above") else "lower <= 0")
            L.append(f"| {cid} | {row['orientation']} | {h_name} | {gp['n_pairs']} | {gp['n_handoff']} "
                     f"| {ho['diff_pp']} | {ci} | {reading} |")
    lim = ro["L1_limit"]
    if lim.get("status") == "not_computed":
        L.append(f"\nL1 limit blocks: not computed ({lim['reason']}).")
    else:
        rates = lim["limit_rates"]
        split_ = lim["limit_split"]
        zero = lim["limit_as_zero"]
        L += ["", "L1 and the 40-step limit: " + ", ".join(
            f"{a} {r['n_limit']}/{r['n_scored']} limit" for a, r in rates.items())
              + f"; pairs where either arm hit the limit {split_.get('n_limit_pairs')}, neither {split_.get('n_neither')}"
              + (f"; mean on neither {split_['mean_on_neither']['diff_pp']} pp" if split_.get("status") == "ok" else "")
              + f"; limit-as-0 T - A {zero['scenario']['diff_pp']} pp, scenario CI {zero['scenario']['ci95_pp']}."]
    asks = ro.get("executor_asks")
    if asks:
        L += ["", f"Executor asks answered live ({asks['rule']}): kept and scored; bound = episodes / "
                  f"{asks['denominator']}, in pp. Reporting only.", "",
              "| arm | episodes with an answered ask (scored) | answering calls | bound (pp) | no event log |",
              "|---|---|---|---|---|"]
        for code, row in asks["per_arm"].items():
            L.append(f"| {code} | {row['n_episodes_with_answered_ask']} ({row['n_scored_episodes_with_answered_ask']}) "
                     f"| {row['n_answered_ask_calls']} | {row['bound_pp']} | {row['n_episodes_without_event_log']} |")
        L += ["", "Per contrast, the larger side's bound: " + ", ".join(
            f"{cid} {row['max_bound_pp']:.2f} pp" for cid, row in asks["per_contrast"].items()) + "."]
    desc = report.get("descriptive") or {}
    if desc:
        ceil, luna = desc.get("ceiling_goal_pass") or {}, desc.get("ceiling_goal_pass_luna") or {}
        L += ["", f"{desc['label']}: planner strength, P27's ceiling (C) mean goal_pass {lp._num(ceil.get('goal_pass_mean'))} "
                  f"({ceil.get('n_scored')}/{ceil.get('n_expected')} scored); luna's ceiling (J10 arm 3) "
                  + (f"{lp._num(luna.get('goal_pass_mean'))}" if luna.get("goal_pass_mean") is not None
                     else f"not available ({luna.get('reason')})")
                  + f". Δ_p (channel margin against luna): not computed ({(desc.get('delta_vs_luna') or {}).get('reason')})."]
    am2 = report.get("j11_am2_divergence") or {}
    if am2:
        L += ["", f"## Replay divergence ({AM2} §B.5)", "",
              f"Divergent keys over the prefix arms: {am2['n_divergent_total']} (cap {am2['cap']} per contrast).", "",
              "| arm | divergent keys | count | other crashes | arm complete |", "|---|---|---|---|---|"]
        for code, v in am2["per_arm"].items():
            L.append(f"| {code} | {', '.join(v['keys']) or '-'} | {v['n_divergent']} | {v['n_crash_other']} "
                     f"| {v['arm_complete']} |")
        L.append("")
        for cid, v in am2["contrasts"].items():
            L.append(f"- {cid}: {v['n_excluded']} key(s) removed from both arms ({v['verdict']}), {v['n_pairs']} pairs "
                     f"against {v['n_expected']}")
        cond = am2.get("resumption_condition") or {}
        if am2.get("refill_confirmed_by_operator"):
            L.append("- Crash-only resumption confirmed by the operator (--divergent-refill-confirmed).")
        elif cond.get("required"):
            L.append(f"- INCOMPLETE until confirmed: {cond['rule']}. How to confirm: {cond['how_to_confirm']}")
    L += ["", "| arm | campaign | scored / expected | crash | missing | error_type counts | goal_pass mean |",
          "|---|---|---|---|---|---|---|"]
    for code, arm in report["arms"].items():
        L.append(f"| {code} | `{arm['campaign']['campaign']}` | {arm['n_scored']}/{arm['n_expected']} | {arm['n_crash']} "
                 f"| {arm['n_missing']} | {json.dumps(arm['error_types'])} | {lp._num(arm['goal_pass_mean'])} |")
    L += ["", "## Ambiguities resolved in code", ""] + [f"- **{a['id']}**: {a['script_behaviour']}"
                                                       for a in report["ambiguities"]]
    return "\n".join(L) + "\n"


# ---- CLI ----------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="J11 registered read (docs/prereg_j11_lp2_test_20260924.md).")
    p.add_argument("--split", required=True, help="test_normal (registered) | dev (--plumbing-check only)")
    p.add_argument("--confirm-heldout-test-split", action="store_true", dest="confirm_heldout_test_split",
                   help="required for test_normal: J11 is read once")
    p.add_argument("--plumbing-check", action="store_true", dest="plumbing_check",
                   help="dev only: read the <id>_dryrun campaigns; the report is never a result")
    p.add_argument("--results-root", type=Path, default=RESULTS_ROOT,
                   help=f"root holding the campaign directories (read-only); default {RESULTS_ROOT}")
    p.add_argument("--out-dir", type=Path, default=OUT_DIR,
                   help=f"directory for the .report.json and .md (default {OUT_DIR.relative_to(REPO_ROOT)})")
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=BOOTSTRAP_SEED)
    p.add_argument("--j10-report", type=Path, default=None, dest="j10_report",
                   help=("the J10 read's report JSON (split test_normal): prints prereg §4:105-109's combined "
                         "statement with J10's P6; absent, the statement is 'pending the J10 read'"))
    p.add_argument("--divergent-refill-confirmed", action="store_true", dest="divergent_refill_confirmed",
                   help=("the operator confirms that every prefix arm with a replay_divergence key had a crash-only "
                         "resumption run after the crash first appeared (Amendment 2 §B.1); without it a "
                         "test_normal read with a divergent key is INCOMPLETE"))
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    refusal = (protocol_guard(args.split, args.confirm_heldout_test_split, args.plumbing_check, args.n_boot, args.seed)
               or lp._refuse_out(args.out_dir, args.results_root) or load_j10_report(args.j10_report)[1])
    if refusal:
        print(json.dumps({"protocol": "J11", "status": "REFUSED", "reason": refusal}))
        return 2
    report, code = build_report(split=args.split, confirm_heldout_test_split=args.confirm_heldout_test_split,
                                plumbing_check=args.plumbing_check, results_root=args.results_root,
                                n_boot=args.n_boot, bootstrap_seed=args.seed, j10_report_path=args.j10_report,
                                divergent_refill_confirmed=args.divergent_refill_confirmed)
    if not stopped_early(report):  # R3's early report holds EARLY_STOP_KEYS only
        report["date"] = _dt.date.today().strftime("%Y%m%d")
    out = args.out_dir / f"{OUT_STEM[args.split]}.report.json"
    md = args.out_dir / f"{OUT_STEM[args.split]}.md"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md.write_text(render_markdown(report, out), encoding="utf-8")
    print(json.dumps({"protocol": "J11", "status": report["status"], "exit_code": code,
                      "headline": report["headline"], "json": str(out), "md": str(md)}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
