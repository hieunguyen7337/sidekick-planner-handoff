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

Exit codes
  0  the gate and L1-L5 are complete; readings are drawn
  1  some gate or L contrast lacks its full matrix of non-crashed pairs (INCOMPLETE, counts only),
     or the prereg §6 abort rule fired (more than 16 planless C keys: J11 is reported as not run)
  2  protocol error or refusal: split / flags, non-registered settings on test, a held-out marker
     where none may be, a (task_id, seed) key twice in one campaign, an output directory under
     /scratch or inside the results tree
  3  a registered campaign directory does not exist yet (the report names each one)
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
     "what": "prereg §6: J11 is reported as not run if more than 16 C episodes are planless.",
     "script_behaviour": (f"The cap is int(0.05 x the matrix) (16 at 336), as j11_arm.pbs counts it. Above it the "
                          f"status is NOT_RUN (exit 1) and every L reads {NOT_RUN!r}.")},
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


def read_family(gate: dict[str, Any], records: dict[str, dict[str, Any]], expected: int) -> dict[str, Any]:
    """LP §3-§4's reading of L1-L5 (lp.read_planner: Holm across the five, m = 5), at J11's matrix."""
    return _rescale_text(lp.read_planner(gate, records), expected)


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
    `planner`, payload.forced False (src/sidekick/systems/loop.py:1066-1079). Every other intervention
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
              companions: dict[str, dict[str, Any]], companions_flag: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Amendment 2 §B.5, reported regardless of outcome: each prefix arm's divergent keys and their count, zero
    included, and each affected contrast's (and handoff-only companion's) number of pairs."""
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
    return {
        "rule": f"{AM2} §B (J10 A1 Amendment 5 §B applied to J11)",
        "decision_bearing": "completeness only: every statistic, the Holm family and every threshold run as registered",
        "definition": rd.DEFINITION,
        "cap": rd.DIVERGENCE_CAP,
        "prefix_arms": list(PREFIX_ARMS),
        "per_arm": per_arm,
        "n_divergent_total": sum(v["n_divergent"] for v in per_arm.values()),
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


def build_report(
    *,
    split: str,
    confirm_heldout_test_split: bool = False,
    plumbing_check: bool = False,
    results_root: Path = RESULTS_ROOT,
    n_boot: int = N_BOOT,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    repo_root: Path = REPO_ROOT,
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
    loaded: dict[str, dict[str, Any]] = {}
    if not errors:
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
    cap = int(expected * j10.A1_PLANLESS_CAP_FRACTION)
    abort = len(planless) > cap
    contingency = {"rule": f"{PREREG} §2, §3, §6", "source_arm": "C", "cap": cap,
                   "keys": [f"{s}/{t}" for t, s in planless], "n_keys": len(planless),
                   "abort_rule_fired": abort}

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
        gate, read = lp.apply_key_exclusion(gate, read, sensitivity)
    gate = _rescale_text(gate, expected)
    if sensitivity is not None:
        sensitivity = dict(sensitivity, citation=f"{PREREG} §3 (LP Amendment 4's rule)",
                           label=("SENSITIVITY (C's planless keys excluded): not decision-bearing, except "
                                  "that a verdict or reading that differs is on the boundary"))
    if abort:
        read = dict(read, readings={c: {"reading": NOT_RUN, "why": (
            f"{len(planless)} planless C keys > cap {cap}; no replay arm was to start")} for c in lp.L_IDS})
    for c in lp.L_IDS:
        contrasts[c]["reading"] = read["readings"][c]["reading"]
        contrasts[c]["reading_why"] = read["readings"][c]["why"]
        if read["holm"] is not None:
            contrasts[c]["p_holm"] = read["holm"]["p"][c]["p_holm"]
            contrasts[c]["holm_rejects"] = read["holm"]["p"][c]["rejects_at_alpha"]
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

    incomplete = list(reasons)
    if gate["status"] != "COMPLETE":
        incomplete.append(f"gate {gate['reason']}")
    incomplete += [f"{c} {contrasts[c]['reason']}" for c in lp.L_IDS if contrasts[c]["status"] != "COMPLETE"]
    summary = f"gate {gate['verdict']}, L1 {read['readings']['L1']['reading']}"
    missing = report["missing_campaigns"]
    if missing:
        status, code = "MISSING_CAMPAIGNS", 3
        headline = "MISSING CAMPAIGNS: " + ", ".join(f"{m['arm']}:{m['campaign']}" for m in missing) + f". {summary}"
    elif abort:
        status, code = "NOT_RUN", 1
        headline = f"NOT RUN (prereg §6 abort rule): {len(planless)} planless C keys > cap {cap}"
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
        planless=contingency,
        gate=gate,
        contrasts=contrasts,
        holm=read["holm"],
        readings=read["readings"],
        sensitivity_planless=sensitivity,
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
        j11_am2_divergence=am2_block(arms, contrasts, companions, companions_flag),
    )
    return j10._strip_internal(report), code


# ---- markdown -----------------------------------------------------------------------
def render_markdown(report: dict[str, Any], json_path: Optional[Path] = None) -> str:
    """Every number below is read from `report` (the JSON), never recomputed."""
    L: list[str] = ["# J11: the LP-2 planner on test_normal", ""]
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
        """Amendment 1 §I: a bound of 1.00 pp or more is printed in the same sentence as the reading."""
        row = ask_pc.get(cid)
        if not row or not row["bound_reaches_1pp"]:
            return ""
        sides = ", ".join(f"{side['arm']} {side['bound_pp']:.2f} pp" for side in (row["left"], row["right"]))
        return f"; live-answered executor asks bound the arm means at {sides} (Amendment 1 §I, no reading changes)"

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
    L += ["", "Readings:"] + [f"- {cid}: **{r['reading']}** ({r['why']}{_ask_note(cid)})"
                              for cid, r in report["readings"].items()]
    p = report["planless"]
    L += ["", f"Planless C keys: {p['n_keys']} (cap {p['cap']})" + (f": {', '.join(p['keys'])}" if p["keys"] else "") + "."]
    sens = report.get("sensitivity_planless")
    if sens:
        L += ["", f"Sensitivity without {', '.join(sens['excluded_keys'])} ({sens['n_expected']} pairs). {sens['label']}.",
              "", "| contrast | n pairs | point (pp) | scenario CI (pp) | reading without the keys |", "|---|---|---|---|---|"]
        sg = sens["gate"]
        if sg.get("status") == "COMPLETE":
            L.append(f"| gate C - E | {sg['n_pairs']} | {sg['point_pp']:+.2f} | {lp._ci(sg['scenario'])} | {sg['verdict']} |")
        for cid, c in sens["contrasts"].items():
            if c.get("status") == "COMPLETE":
                L.append(f"| {cid} | {c['n_pairs']} | {c['point_pp']:+.2f} | {lp._ci(c['scenario'])} | {c['reading']} |")
            else:
                L.append(f"| {cid} | - | - | - | incomplete |")
    ro = report["reporting_only"]
    L += ["", "## Reported beside the predictions (not decision-bearing)", "",
          "Handoff-only companions: h = h*, the executor took control after the replayed prefix "
          "(scripts/analysis/handoff_control.py); the flag version (handoff_occurred, h_flag) is in the JSON "
          "under `reporting_only.handoff_only_h_flag`.", "",
          "| companion | orientation | n pairs | n handoff | handoff-only (pp) | scenario CI (pp) | reading |",
          "|---|---|---|---|---|---|---|"]
    for cid, row in ro["handoff_only"].items():
        gp = row.get("goal_pass") or {}
        ho = gp.get("handoff_only") or {}
        if row.get("status") == "not_computed" or not ho:
            L.append(f"| {cid} | {row['orientation']} | - | - | not computed ({row.get('reason', gp.get('error'))}) | | |")
            continue
        ci = ho.get("ci95_pp_scenario")
        reading = (gp.get("ni") or {}).get("reading") or (
            "lower > 0" if (gp.get("vs_threshold") or {}).get("lower_above") else "lower <= 0")
        L.append(f"| {cid} | {row['orientation']} | {gp['n_pairs']} | {gp['n_handoff']} | {ho['diff_pp']} "
                 f"| {ci} | {reading} |")
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
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    refusal = protocol_guard(args.split, args.confirm_heldout_test_split, args.plumbing_check,
                             args.n_boot, args.seed) or lp._refuse_out(args.out_dir, args.results_root)
    if refusal:
        print(json.dumps({"protocol": "J11", "status": "REFUSED", "reason": refusal}))
        return 2
    report, code = build_report(split=args.split, confirm_heldout_test_split=args.confirm_heldout_test_split,
                                plumbing_check=args.plumbing_check, results_root=args.results_root,
                                n_boot=args.n_boot, bootstrap_seed=args.seed)
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
