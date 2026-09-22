#!/usr/bin/env python
"""B2: the registered decomposition of the matched-trigger channel contrast (C1).

Computes ``docs/prereg_c1_decomposition_20260923.md`` §3-§5 and its Amendment 1, so that
the verdict is mechanical when the Wave B campaigns land. It chooses nothing. Every
statistic comes from the J10 A1 machinery in ``scripts/analysis/j10_report.py`` -- the
same cluster bootstrap, bootstrap p, Holm step-down, POOL-04 re-check and sign-flip
wrapper -- imported rather than copied, so B2 cannot drift from how A1 reads an interval
(Amendment 1 says the gap it fills is resolved "the same way" as A1 r2 §5.3).

What this file adds is only what B2 registers and A1 does not: four arms pooled from two
campaigns each, the contrasts D0-D4, Amendment 1's reading of "excludes zero" and
"includes zero", the four outcomes in their registered order, and the exploratory block
(D0-D4 on TGC, the copy rate, per-arm cost).

Exit codes
  0  every contrast complete; an outcome is read
  1  some contrast lacks 171 non-crashed pairs: it is reported INCOMPLETE with counts and
     no outcome is decided
  2  protocol error: a (task_id, seed) key twice within one arm, a held-out path, or an
     output path under /scratch
  3  a registered campaign directory does not exist yet (the report names each one)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Imported as a module (not name by name) so a test can monkeypatch the bootstrap in ONE
# place and have the primary interval and the POOL-04 re-draws both see it.
from scripts.analysis import j10_report as j10  # noqa: E402
from scripts.analysis.j8_noncached_cost import usage_noncached_tokens  # noqa: E402
from sidekick.protocols.prompts import format_executor_action  # noqa: E402
from sidekick.protocols.schemas import ExecutorAction  # noqa: E402

PREREG = "docs/prereg_c1_decomposition_20260923.md"
RESULTS_ROOT = j10.RAW_RESULTS_ROOT
OUT_DIR = REPO_ROOT / "campaign" / "results"
OUT_STEM = "b2_decomposition"
# Nothing under /scratch is ever written: it holds the raw episodes this script reads.
FORBIDDEN_OUT_ROOTS = (Path("/scratch"),)

SEEDS: tuple[int, ...] = (1, 2, 3)  # §3: 57 dev tasks x seeds {1, 2, 3}
N_TASKS = 57
EXPECTED_PAIRS = N_TASKS * len(SEEDS)  # 171
N_BOOT = 10_000
BOOTSTRAP_SEED = 20260924
ALPHA = 0.05
FIELD = "goal_pass_rate"
# Every rule that reads a Holm-adjusted p asks whether a contrast is "> 0 with CI
# excluding zero", so "the far side of zero" (Amendment 1 §1) is the share of bootstrap
# means <= 0: j10.bootstrap_pvalue(direction="greater"), as A1 r2 §5.3 does for predictions with no reversed outcome (P3, P4).
P_DIRECTION = "greater"

ARM_ORDER = ("T", "A", "S", "N")
ARM_NAMES = {
    "T": "takeover",
    "A": "advice, registered prompt, full context",
    "S": "show, don't execute",
    "N": "neutral advice",
}
# Amendment 1 §5 [prereg:139-144]: the union, keyed (task_id, seed), of these campaigns.
ARM_CAMPAIGNS: dict[str, tuple[str, ...]] = {
    "T": ("hj12_takeover_fixed_k_10_20260923", "b1_takeover_fixed_k_10_s3_20260923"),
    "A": ("hj12_advise_fixed_k_10_fullctx_20260923", "b1_advise_fixed_k_10_fullctx_s3_20260923"),
    "S": ("b2_show_fixed_k_10_20260923", "b2_show_fixed_k_10_s3_20260923"),
    "N": (
        "b2_advise_neutral_fixed_k_10_fullctx_20260923",
        "b2_advise_neutral_fixed_k_10_fullctx_s3_20260923",
    ),
}

# POOL-04 re-checks the bounds whose position against zero can change a reading, and
# classifies each re-drawn interval with an A1 rule (reused, so the window arithmetic and
# the seven re-draws are A1's own). D1 and D4 are read both as "excludes zero" and as
# "includes zero", so both bounds matter and the interval is classified three ways. D2 and
# D3 are only ever asked whether they exclude zero on the positive side, which the lower
# bound alone decides.
THREE_WAY = "negative_excludes_zero_with_reversal"
LOWER_ONLY = "lower_bound_above_threshold"
POOL04_VERDICT_NAMES = {
    THREE_WAY: {
        "supported": "excludes_zero_negative",
        "reversed": "excludes_zero_positive",
        "not_supported": "includes_zero",
    },
    LOWER_ONLY: {
        "supported": "excludes_zero_positive",
        "not_supported": "does_not_exclude_zero_positive",
    },
}

# §4 [prereg:73-79]. D0 is outside the Holm family (Amendment 1 §1) and no outcome reads it.
CONTRASTS: tuple[dict[str, Any], ...] = (
    {"id": "D0", "left": "T", "right": "A", "holm_family": False, "decision_bearing": False,
     "pool04_rule": THREE_WAY,
     "isolates": "C1 extended to 171 pairs (114 already seen): an extension, not a replication"},
    {"id": "D1", "left": "T", "right": "S", "holm_family": True, "decision_bearing": True,
     "pool04_rule": THREE_WAY,
     "isolates": "execution (same prompt, same planner output; executed vs shown)"},
    {"id": "D2", "left": "S", "right": "A", "holm_family": True, "decision_bearing": True,
     "pool04_rule": LOWER_ONLY,
     "isolates": "prompt + content at the same delivery"},
    {"id": "D3", "left": "N", "right": "A", "holm_family": True, "decision_bearing": True,
     "pool04_rule": LOWER_ONLY,
     "isolates": "the advice prompt's wording"},
    {"id": "D4", "left": "T", "right": "N", "holm_family": True, "decision_bearing": True,
     "pool04_rule": THREE_WAY,
     "isolates": "the channel gap that remains against a fairer advice prompt"},
)
CONTRAST_BY_ID = {c["id"]: c for c in CONTRASTS}
HOLM_FAMILY = tuple(c["id"] for c in CONTRASTS if c["holm_family"])

REQUIREMENT_TEXT = {
    "excludes_zero_positive": (
        "> 0 with CI excluding zero: unadjusted 95% scenario CI lo > 0 AND Holm-adjusted "
        "p <= 0.05 (Amendment 1 §2)"
    ),
    "includes_zero": "CI includes zero: unadjusted 95% scenario CI (Amendment 1 §3)",
}

# §4, evaluated in this order; the first that applies is the headline [prereg:81-91].
OUTCOMES: tuple[dict[str, Any], ...] = (
    {"id": "prompt_artefact", "order": 1, "title": "Prompt artefact",
     "requires": (("D4", "includes_zero"), ("D3", "excludes_zero_positive")),
     "reading": ("The advice arm was handicapped by its wording. C1 is withdrawn as a "
                 "channel claim and reported as a prompt effect."),
     "citation": f"{PREREG}:84-85"},
    {"id": "execution_matters", "order": 2, "title": "Execution matters",
     "requires": (("D1", "excludes_zero_positive"),),
     "reading": ('The strong form of the title ("actions, not advice") stands, now against '
                 "a same-content control."),
     "citation": f"{PREREG}:86-87"},
    {"id": "content_not_execution", "order": 3, "title": "Content, not execution",
     "requires": (("D1", "includes_zero"), ("D2", "excludes_zero_positive")),
     "reading": ("Re-framed as code, not prose: the planner's action text helps as much "
                 "shown as executed. The title changes accordingly."),
     "citation": f"{PREREG}:88-90"},
    {"id": "unresolved", "order": 4, "title": "Unresolved",
     "requires": (),
     "reading": "None of the above. Intervals reported; no decomposition claim.",
     "citation": f"{PREREG}:91"},
)
OUTCOME_BY_ID = {o["id"]: o for o in OUTCOMES}

# §4 [prereg:93-94]: "stated so that surprise is visible, not as predictions to be tested".
EXPECTATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("D3 small and positive", ("D3",)),
    ("D1 positive but smaller than D0", ("D1", "D0")),
    ("D4 positive", ("D4",)),
)

AMBIGUITIES: list[dict[str, str]] = [
    {"id": "holm_p_direction",
     "what": ("Amendment 1 §1 calls p 'two-sided-equivalent' and '2 x the share of resampled "
              "means on the far side of zero' without naming a side."),
     "script_behaviour": ("Every rule that consumes the adjusted p is a '> 0' claim, so p = 2 x "
                          "share of scenario-bootstrap means <= 0 (j10.bootstrap_pvalue "
                          "'greater', as A1 r2 §5.3 does for predictions with no reversed outcome). The 2 x min-tail p is reported beside "
                          "it as p_two_sided; the two coincide whenever the point estimate is "
                          "positive.")},
    {"id": "pool04_decision_bearing_bounds",
     "what": "POOL-04 re-checks 'any decision-bearing bound' but the registration does not list them.",
     "script_behaviour": ("D1 and D4 (read as both 'excludes' and 'includes' zero): both bounds, "
                          "each re-drawn interval classified excludes-positive / includes / "
                          "excludes-negative. D2 and D3 (read only as 'excludes zero, positive "
                          "side'): the lower bound. D0 is checked the D1 way for information only.")},
    {"id": "incomplete_contrast_estimates",
     "what": ("§3: 'A contrast is reported only when both arms have all 171 pairs non-crashed; "
              "otherwise it is reported as incomplete with the count.'"),
     "script_behaviour": ("An incomplete contrast carries counts only: no point estimate, "
                          "interval or p. Holm is computed only when all of D1-D4 are complete, "
                          "because a smaller family would change every adjusted p.")},
    {"id": "positive_point_estimate",
     "what": "'D > 0 with CI excluding zero' names a sign and an interval.",
     "script_behaviour": "Both are required: point > 0, lo > 0, and Holm-adjusted p <= 0.05."},
    {"id": "missing_goal_pass_rate",
     "what": "The registration does not say how a non-crashed episode without goal_pass_rate counts.",
     "script_behaviour": ("It is never coerced to 0: the pair is dropped and counted, which "
                          "leaves the contrast below 171 and so INCOMPLETE.")},
    {"id": "duplicate_within_one_campaign",
     "what": "Amendment 1 §5 makes a key in two campaigns of one arm an error; it is silent on a key twice inside one campaign.",
     "script_behaviour": ("Also an error: j10.load_arm_tree would otherwise keep whichever copy "
                          "sorts first, which is the silent choice §5 forbids.")},
    {"id": "copy_rate_definition",
     "what": ("§5: 'shown code the executor reproduces verbatim (after whitespace normalisation) "
              "as its next action' fixes neither the denominator, 'next action', nor the "
              "normalisation."),
     "script_behaviour": ("Denominator: every intervention with payload source == 'shown_action' "
                          "in a non-crashed S episode of the registered matrix, events after the "
                          "episode's last run_start. Next action: the first executor 'action' "
                          "event after it and before any further intervention. Comparison: the "
                          "executor's action rendered by format_executor_action (the renderer "
                          "that produced the shown text) against the shown text, both with every "
                          "run of whitespace collapsed to one space. Non-CODE shows are counted "
                          "and broken out by shown_kind.")},
    {"id": "cost_axes",
     "what": "§5 names hosted calls, non-cached tokens and cost per episode without fields.",
     "script_behaviour": ("hosted calls = n_planner_calls (j12_cost_axes' convention; it counts "
                          "the one zero-token cached plan replay every arm makes); non-cached "
                          "tokens = live planner input + output + reasoning "
                          "(j8_noncached_cost.usage_noncached_tokens); cost = totals.usd_total.")},
    {"id": "signflip_resolution",
     "what": "§3 names a scenario-cluster sign-flip p without a permutation count.",
     "script_behaviour": ("Amendment 3: j10.a1_permutation -> cluster_inference.registered_signflip, "
                          "the routine A1 r2 §5.5 uses. 19 clusters give 2^19 <= 2^20 patterns, so the "
                          "p is exact enumeration, two-sided at 0.")},
    {"id": "system_labels",
     "what": "Arms are defined by campaign names; the runner also records a system label.",
     "script_behaviour": "More than one system label inside an arm is reported as a warning, not a refusal."},
    {"id": "out_root",
     "what": "The brief's --out-root is the runner's name for the directory campaigns are written to.",
     "script_behaviour": ("--out-root is read as the root holding the campaign directories "
                          "(default the raw results root); outputs go to --out, default "
                          "campaign/results/b2_decomposition_<date>.report.json.")},
]


# ---- loading ----------------------------------------------------------------
class PoolingError(ValueError):
    """A (task_id, seed) key found twice within one arm."""


def load_pooled_arm(code: str, campaign_dirs: list[Path]) -> dict[str, Any]:
    """One arm: the union of its campaigns keyed (task_id, seed), shaped for j10.a1_arm_episodes.

    Mirrors j14_did.load_pooled_arm's refusal of colliding keys, but loads each campaign
    with j10.load_arm_tree so that empty and unreadable result files are counted instead of
    skipped. Amendment 1 §5: a key present in more than one campaign of an arm is an error,
    not a choice -- keeping either copy would silently choose which episode counts.
    """
    runs: dict[tuple[str, int], dict[str, Any]] = {}
    origin: dict[tuple[str, int], str] = {}
    blob: dict[str, Any] = {
        "runs": runs,
        "empty_files": [],
        "unreadable": [],
        "duplicates": [],
        "systems": set(),
        "root_missing": False,
        "campaigns": [],
    }
    for directory in campaign_dirs:
        loaded = j10.load_arm_tree(directory)
        if loaded["duplicates"]:
            raise PoolingError(
                f"arm {code}: campaign {directory.name} holds a (task_id, seed) key twice "
                f"({loaded['duplicates'][:3]}); keeping either copy would be a choice"
            )
        clash = sorted(set(runs) & set(loaded["runs"]))
        if clash:
            raise PoolingError(
                f"arm {code}: {len(clash)} (task_id, seed) key(s) present in both "
                f"{origin[clash[0]]} and {directory.name} (e.g. {clash[:3]}); Amendment 1 §5 "
                "makes this an error, not a choice"
            )
        for key in loaded["runs"]:
            origin[key] = directory.name
        runs.update(loaded["runs"])
        blob["empty_files"].extend(loaded["empty_files"])
        blob["unreadable"].extend(loaded["unreadable"])
        blob["systems"] |= loaded["systems"]
        blob["root_missing"] = blob["root_missing"] or loaded["root_missing"]
        present = not loaded["root_missing"]
        blob["campaigns"].append({
            "campaign": directory.name,
            "path": str(directory),
            "present": present,
            "n_results": len(loaded["runs"]),
            "by_seed": dict(sorted(Counter(str(s) for _t, s in loaded["runs"]).items())),
            "systems": sorted(loaded["systems"]),
            "n_empty_files": len(loaded["empty_files"]),
            "n_unreadable": len(loaded["unreadable"]),
            "split_provenance": j10.a1_split_provenance(directory) if present else {},
        })
    return blob


# ---- one contrast -----------------------------------------------------------
def _translate_pool04(pool: dict[str, Any], rule: str) -> dict[str, Any]:
    """Rename A1's verdict words ('supported', 'reversed', ...) into what they mean for B2."""
    names = POOL04_VERDICT_NAMES[rule]
    out = dict(pool)
    if "bounds_by_seed" in out:
        out["bounds_by_seed"] = [dict(row, verdict=names[row["verdict"]]) for row in out["bounds_by_seed"]]
        out["verdicts_by_seed"] = sorted({names[v] for v in out["verdicts_by_seed"]})
    if isinstance(out.get("bound_200k"), dict):
        out["bound_200k"] = dict(out["bound_200k"], verdict=names[out["bound_200k"]["verdict"]])
    out["on_boundary"] = bool(out["fired"] and not out.get("stable", True))
    out["status"] = "on_boundary" if out["on_boundary"] else ("stable" if out["fired"] else "not_fired")
    return out


def _arm_count(code: str, arm: dict[str, Any]) -> dict[str, Any]:
    return {
        "arm": code,
        "complete": arm["complete"],
        "n_scored": arm["n_scored"],
        "n_expected": EXPECTED_PAIRS,
        "n_crash": arm["n_crash"],
        "n_missing": arm["n_missing"],
    }


def evaluate_contrast(
    spec: dict[str, Any],
    arms: dict[str, dict[str, Any]],
    *,
    n_boot: int,
    seed: int,
) -> tuple[dict[str, Any], Optional[dict[str, Any]]]:
    """(public block, decision record or None). Incomplete: counts only (§3)."""
    left, right = arms[spec["left"]], arms[spec["right"]]
    series = j10.a1_paired_series(left["episodes"], right["episodes"], FIELD)
    out: dict[str, Any] = {
        "id": spec["id"],
        "definition": f"{spec['left']} - {spec['right']}",
        "left": spec["left"],
        "right": spec["right"],
        "isolates": spec["isolates"],
        "decision_bearing": spec["decision_bearing"],
        "holm_family": spec["holm_family"],
        "metric": "goal_pass",
        "field": FIELD,
        "n_pairs": len(series["diffs"]),
        "n_expected": EXPECTED_PAIRS,
        "n_dropped_missing_field": series["n_dropped_missing_field"],
        "counts": [_arm_count(spec["left"], left), _arm_count(spec["right"], right)],
    }
    problems = [
        f"{c['arm']} {c['n_scored']}/{EXPECTED_PAIRS} non-crashed "
        f"(crash {c['n_crash']}, missing {c['n_missing']})"
        for c in out["counts"] if not c["complete"]
    ]
    if len(series["diffs"]) != EXPECTED_PAIRS:
        problems.append(f"{len(series['diffs'])}/{EXPECTED_PAIRS} pairs scored on both sides")
    if problems:
        out.update(status="INCOMPLETE", reason="; ".join(problems))
        return out, None

    cmp = j10.a1_contrast(left["episodes"], right["episodes"], FIELD, n_boot=n_boot, seed=seed)
    primary = cmp["scenario"]
    p_raw = j10.bootstrap_pvalue(primary["_means"], 0.0, P_DIRECTION)
    pool = _translate_pool04(
        j10.a1_pool04({"rule": spec["pool04_rule"], "threshold_pp": 0.0}, cmp["_series"], primary,
                      n_boot=n_boot, seed=seed),
        spec["pool04_rule"],
    )
    if not spec["decision_bearing"]:
        pool["note"] = "informational: D0 is not decision-bearing"
    out.update(
        status="COMPLETE",
        point_pp=primary["diff_pp"],
        scenario=j10._public(primary),
        task=j10._public(cmp["task"]),
        p_raw=p_raw,
        p_raw_direction=P_DIRECTION,
        p_two_sided=j10.bootstrap_pvalue(primary["_means"], 0.0, "two-sided"),
        pool04=pool,
        signflip=j10.a1_permutation(cmp["_series"], 0.0),
    )
    record = {
        "status": "COMPLETE",
        "point": primary["point"],
        "lo": primary["lo"],
        "hi": primary["hi"],
        "p_raw": p_raw,
        "boundary": pool["on_boundary"],
    }
    return out, record


# ---- the registered reading -------------------------------------------------
def _pp(x: float) -> str:
    return f"{x * 100:+.2f}"


def contrast_events(rec: dict[str, Any], p_holm: float, alpha: float = ALPHA) -> dict[str, Any]:
    """Amendment 1 §2-§4 for one contrast: does it 'exclude zero (> 0)', does it 'include zero'?"""
    lo, hi, point = float(rec["lo"]), float(rec["hi"]), float(rec["point"])
    ci = f"scenario CI [{_pp(lo)}, {_pp(hi)}] pp"
    if rec.get("boundary"):
        why = ("on the boundary (POOL-04: the verdict differs across the seven bootstrap "
               "seeds), so it satisfies neither 'excludes zero' nor 'includes zero' "
               "(Amendment 1 §4)")
        return {
            "boundary": True,
            "excludes_zero_positive_unadjusted": lo > 0,
            "excludes_zero_positive": {"held": False, "why": why},
            "includes_zero": {"held": False, "why": why},
        }
    if lo <= 0:
        excl, why = False, f"{ci} does not exclude zero on the positive side (lo <= 0)"
    elif point <= 0:
        excl, why = False, f"point estimate {_pp(point)} pp is not > 0"
    elif p_holm > alpha:
        excl, why = False, (f"{ci} excludes zero (lo > 0) but the Holm-adjusted p = {p_holm:.4g} "
                            f"> {alpha} (Amendment 1 §2)")
    else:
        excl, why = True, f"{ci} excludes zero (lo > 0) and the Holm-adjusted p = {p_holm:.4g} <= {alpha}"
    incl = lo <= 0.0 <= hi
    # Judged unadjusted (Amendment 1 §3): Holm would make a non-rejection easier to reach.
    incl_why = f"unadjusted {ci} {'includes' if incl else 'excludes'} zero"
    return {
        "boundary": False,
        "excludes_zero_positive_unadjusted": lo > 0,
        "excludes_zero_positive": {"held": excl, "why": why},
        "includes_zero": {"held": incl, "why": incl_why},
    }


def decide_outcome(records: dict[str, dict[str, Any]], alpha: float = ALPHA) -> dict[str, Any]:
    """Holm across D1-D4, then the four outcomes in registered order, with a full trace.

    Pure over per-contrast records {status, point, lo, hi, p_raw, boundary} (fractions),
    so the multiplicity and ordering logic is testable without a bootstrap.
    """
    incomplete = [d for d in HOLM_FAMILY if (records.get(d) or {}).get("status") != "COMPLETE"]
    if incomplete:
        return {
            "decided": False,
            "reading": None,
            "title": "No outcome decided",
            "text": (f"{', '.join(incomplete)} lack {EXPECTED_PAIRS} non-crashed pairs; no outcome "
                     "is decided (§3) and Holm is not computed on a partial family."),
            "incomplete_contrasts": incomplete,
            "holm": None,
            "events": {},
            "trace": [],
        }
    raw = [float(records[d]["p_raw"]) for d in HOLM_FAMILY]
    adjusted = j10.holm_adjust(raw)
    holm = {
        d: {"p_raw": r, "p_holm": a, "rejects_at_alpha": bool(a <= alpha)}
        for d, r, a in zip(HOLM_FAMILY, raw, adjusted)
    }
    events = {d: contrast_events(records[d], holm[d]["p_holm"], alpha) for d in HOLM_FAMILY}
    trace: list[dict[str, Any]] = []
    reading: Optional[str] = None
    for outcome in OUTCOMES:
        if outcome["requires"]:
            conditions = [
                {"contrast": d, "requires": need, "requirement": REQUIREMENT_TEXT[need],
                 "held": events[d][need]["held"], "why": events[d][need]["why"]}
                for d, need in outcome["requires"]
            ]
            fires = all(c["held"] for c in conditions)
        else:
            fires = reading is None
            conditions = [{
                "contrast": None, "requires": "none of the above", "held": fires,
                "why": ("no earlier outcome fired" if fires
                        else f"{OUTCOME_BY_ID[reading]['title']} already fired"),
            }]
        headline = fires and reading is None
        if headline:
            reading = outcome["id"]
        trace.append({
            "order": outcome["order"],
            "outcome": outcome["id"],
            "title": outcome["title"],
            "fires": fires,
            "headline": headline,
            "conditions": conditions,
            "citation": outcome["citation"],
        })
    assert reading is not None  # 'unresolved' always fires when nothing earlier did
    return {
        "decided": True,
        "reading": reading,
        "title": OUTCOME_BY_ID[reading]["title"],
        "text": OUTCOME_BY_ID[reading]["reading"],
        "holm": {"method": "Holm step-down", "alpha": alpha, "family": list(HOLM_FAMILY),
                 "m": len(HOLM_FAMILY), "p": holm},
        "events": events,
        "trace": trace,
    }


# ---- exploratory ------------------------------------------------------------
def _normalise_ws(text: str) -> str:
    return " ".join(text.split())


def _render_action(payload: dict[str, Any]) -> Optional[str]:
    """The executor's action in the one spelling the shown text was rendered in."""
    fields = {k: payload[k] for k in ExecutorAction.model_fields if k in payload}
    if fields.get("raw_output") is None:
        fields.pop("raw_output", None)
    try:
        return format_executor_action(ExecutorAction(**fields))
    except (ValueError, TypeError):  # pydantic's ValidationError is a ValueError
        return None


def read_events(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Events of the episode's LAST run_start segment, and the count of unparseable lines.

    A resumed episode appends a new run_start; only the last segment produced the result
    (the convention of j8_noncached_cost.last_plan_event_noncached_tokens).
    """
    events: list[dict[str, Any]] = []
    bad = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if not isinstance(ev, dict):
            bad += 1
            continue
        if ev.get("event_type") == "run_start":
            events = []
        events.append(ev)
    return events, bad


def shown_action_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per S intervention: was the shown action reproduced as the next action?"""
    rows: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        if ev.get("event_type") != "intervention":
            continue
        payload = ev.get("payload") or {}
        if payload.get("source") != "shown_action":
            continue
        shown = str(payload.get("correction") or "")
        nxt = None
        for later in events[i + 1:]:
            if later.get("event_type") == "intervention":
                break
            if later.get("event_type") == "action" and later.get("actor") == "executor":
                nxt = later
                break
        row: dict[str, Any] = {"step": ev.get("step"), "shown_kind": payload.get("shown_kind"),
                               "followed": nxt is not None, "copied": False}
        if nxt is not None:
            rendered = _render_action(nxt.get("payload") or {})
            row["next_kind"] = (nxt.get("payload") or {}).get("kind")
            row["renderable"] = rendered is not None
            row["copied"] = rendered is not None and _normalise_ws(rendered) == _normalise_ws(shown)
        rows.append(row)
    return rows


def copy_rate(event_paths: dict[tuple[str, int], Path]) -> dict[str, Any]:
    """Exploratory (§5): share of S interventions the executor reproduces verbatim next."""
    base: dict[str, Any] = {
        "label": "EXPLORATORY: not decision-bearing (prereg §5)",
        "definition": next(a["script_behaviour"] for a in AMBIGUITIES if a["id"] == "copy_rate_definition"),
        "normalisation": "' '.join(text.split()): every run of whitespace -> one space, ends stripped",
    }
    n_missing = n_bad = n_with_shown = 0
    rows: list[dict[str, Any]] = []
    for key in sorted(event_paths):
        path = event_paths[key]
        if not path.is_file():
            n_missing += 1
            continue
        events, bad = read_events(path)
        n_bad += bad
        ep_rows = shown_action_rows(events)
        n_with_shown += bool(ep_rows)
        rows.extend(ep_rows)
    by_kind: dict[str, dict[str, int]] = {}
    for row in rows:
        k = by_kind.setdefault(str(row["shown_kind"]), {"n_shown": 0, "n_followed": 0, "n_copied": 0})
        k["n_shown"] += 1
        k["n_followed"] += row["followed"]
        k["n_copied"] += row["copied"]
    n_shown = len(rows)
    n_followed = sum(r["followed"] for r in rows)
    n_copied = sum(r["copied"] for r in rows)
    return {
        **base,
        "n_episodes": len(event_paths),
        "n_episodes_without_events": n_missing,
        "n_episodes_with_a_shown_action": n_with_shown,
        "n_unparseable_event_lines": n_bad,
        "n_shown": n_shown,
        "n_followed_by_an_executor_action": n_followed,
        "n_unrenderable_next_action": sum(1 for r in rows if r["followed"] and not r.get("renderable")),
        "n_copied": n_copied,
        "copy_rate": round(n_copied / n_shown, 6) if n_shown else None,
        "copy_rate_among_followed": round(n_copied / n_followed, 6) if n_followed else None,
        "by_shown_kind": dict(sorted(by_kind.items())),
    }


def s_event_paths(campaign_dirs: list[Path], keys: set[tuple[str, int]]) -> dict[tuple[str, int], Path]:
    """events.jsonl beside each scored S result.json (the runner writes them side by side)."""
    paths: dict[tuple[str, int], Path] = {}
    for directory in campaign_dirs:
        if not directory.exists():
            continue
        for result in sorted(directory.rglob("result.json")):
            row, _err = j10._read_result(result)
            if row is None or row.get("task_id") is None or row.get("seed") is None:
                continue
            key = (str(row["task_id"]), int(row["seed"]))
            if key in keys:
                paths[key] = result.parent / "events.jsonl"
    return paths


def _mean(values: list[float]) -> Optional[float]:
    return round(statistics.fmean(values), 6) if values else None


def arm_cost(runs: dict[tuple[str, int], dict[str, Any]], keys: list[tuple[str, int]]) -> dict[str, Any]:
    """Exploratory (§5): per-episode hosted calls, non-cached planner tokens and USD."""
    calls: list[float] = []
    tokens: list[float] = []
    usd: list[float] = []
    for key in keys:
        row = runs[key]
        n_calls = j10.optional_int(row, "n_planner_calls")
        if n_calls is not None:
            calls.append(float(n_calls))
        actor = j10.planner_actor(row)
        if actor:
            value = usage_noncached_tokens(actor)
            if value is not None:
                tokens.append(value)
        elif actor == {} and n_calls == 0:
            tokens.append(0.0)  # no planner actor and no call: genuinely zero, not missing
        cost = j10.usd_total(row)
        if cost is not None:
            usd.append(cost)
    return {
        "n_episodes": len(keys),
        "hosted_calls_per_episode": _mean(calls),
        "n_calls_missing": len(keys) - len(calls),
        "noncached_tokens_per_episode": _mean(tokens),
        "n_tokens_missing": len(keys) - len(tokens),
        "usd_per_episode": _mean(usd),
        "n_usd_missing": len(keys) - len(usd),
    }


# ---- report -----------------------------------------------------------------
def _registered_expectations(contrasts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    points = {d: c.get("point_pp") for d, c in contrasts.items()}
    out = []
    for text, needs in EXPECTATIONS:
        if any(points.get(d) is None for d in needs):
            observed = None
        elif needs == ("D1", "D0"):
            observed = 0 < points["D1"] < points["D0"]
        else:
            observed = points[needs[0]] > 0
        out.append({"expectation": text, "on_point_estimates": observed,
                    "note": "stated so that surprise is visible, not a prediction to be tested"})
    return out


def build_report(
    *,
    results_root: Path = RESULTS_ROOT,
    arm_campaigns: Optional[dict[str, tuple[str, ...]]] = None,
    n_boot: int = N_BOOT,
    bootstrap_seed: int = BOOTSTRAP_SEED,
) -> tuple[dict[str, Any], int]:
    campaigns = {code: tuple(names) for code, names in (arm_campaigns or ARM_CAMPAIGNS).items()}
    registered = campaigns == ARM_CAMPAIGNS and n_boot == N_BOOT and bootstrap_seed == BOOTSTRAP_SEED
    report: dict[str, Any] = {
        "protocol": "B2",
        "prereg": PREREG,
        "amendments": ["Amendment 1, 2026-09-23 (Holm x interval rules; pooling)"],
        "label": ("B2 registered decomposition (dev)" if registered
                  else "NON-REGISTERED settings or campaigns: not the B2 result"),
        "results_root": str(results_root),
        "arm_campaigns": {code: list(names) for code, names in campaigns.items()},
        "settings": {
            "unit": "paired episode, key (task_id, seed), pooled across an arm's campaigns",
            "expected_pairs": EXPECTED_PAIRS,
            "seeds": list(SEEDS),
            "n_tasks": N_TASKS,
            "metric": "goal_pass (field goal_pass_rate); TGC exploratory",
            "bootstrap": {"n": n_boot, "seed": bootstrap_seed, "registered": registered,
                          "primary_clustering": "scenario", "secondary_clustering": "task",
                          "interval": "95% percentile, j10.cluster_bootstrap_means / percentile_ci"},
            "p_value": f"j10.bootstrap_pvalue(scenario means, 0, {P_DIRECTION!r})",
            "multiplicity": {"method": "Holm step-down", "family": list(HOLM_FAMILY), "alpha": ALPHA},
            "pool04": {"window_pp": j10.POOL04_WINDOW_PP, "seeds": list(j10.POOL04_SEEDS)},
            "signflip": ("j10.a1_permutation (cluster_inference.registered_signflip): scenario clusters, "
                         "exact over 2^G patterns when 2^G <= 2^20 (2^19 here), two-sided at 0"),
            "crash_convention": "drop only error_type == 'crash'; limit and every other error_type is scored",
        },
        "ambiguities": AMBIGUITIES,
    }
    errors: list[str] = []
    for names in campaigns.values():
        for name in names:
            marker = j10.heldout_marker_in_path(results_root / name)
            if marker:
                errors.append(f"refusing campaign {name}: contains held-out marker {marker!r} (B2 is dev only)")
    missing = [
        {"arm": code, "campaign": name, "path": str(results_root / name)}
        for code in ARM_ORDER for name in campaigns[code]
        if not (results_root / name).is_dir()
    ]
    report["missing_campaigns"] = missing

    pooled: dict[str, dict[str, Any]] = {}
    if not errors:
        for code in ARM_ORDER:
            try:
                pooled[code] = load_pooled_arm(code, [results_root / n for n in campaigns[code]])
            except PoolingError as exc:
                errors.append(str(exc))
    if errors:
        report.update(status="ERROR", exit_code=2, errors=errors,
                      headline="ERROR: " + "; ".join(errors), contrasts={}, outcome=None)
        return report, 2

    tasks = j10.discover_tasks(pooled, list(SEEDS))
    reasons: list[str] = []
    warnings: list[str] = []
    if len(tasks) != N_TASKS:
        reasons.append(f"task_count_is_{len(tasks)}_expected_{N_TASKS}")
    for code, blob in pooled.items():
        for camp in blob["campaigns"]:
            wrong = {k: v for k, v in camp["split_provenance"].items() if k not in {"dev", "unrecorded"}}
            if wrong:
                reasons.append(f"split_provenance_not_dev:{code}:{camp['campaign']}={wrong}")
        if len(blob["systems"]) > 1:
            warnings.append(f"arm {code} carries system labels {sorted(blob['systems'])}")
    arms = {code: j10.a1_arm_episodes(code, pooled[code], tasks, list(SEEDS)) for code in ARM_ORDER}
    for arm in arms.values():
        # A matrix of the wrong size or from the wrong split cannot be complete at any count.
        arm["complete"] = bool(arm["complete"] and not reasons and arm["n_expected"] == EXPECTED_PAIRS)

    contrasts: dict[str, dict[str, Any]] = {}
    records: dict[str, dict[str, Any]] = {}
    for spec in CONTRASTS:
        block, record = evaluate_contrast(spec, arms, n_boot=n_boot, seed=bootstrap_seed)
        contrasts[spec["id"]] = block
        if record is not None:
            records[spec["id"]] = record
    outcome = decide_outcome(records)
    if outcome["decided"]:
        for d in HOLM_FAMILY:
            contrasts[d]["p_holm"] = outcome["holm"]["p"][d]["p_holm"]
            contrasts[d]["holm_rejects"] = outcome["holm"]["p"][d]["rejects_at_alpha"]
            contrasts[d]["events"] = outcome["events"][d]

    tgc: dict[str, Any] = {}
    for spec in CONTRASTS:
        left, right = arms[spec["left"]], arms[spec["right"]]
        if contrasts[spec["id"]]["status"] != "COMPLETE":
            tgc[spec["id"]] = {"status": "INCOMPLETE", "reason": contrasts[spec["id"]]["reason"]}
            continue
        cmp = j10._public_contrast(j10.a1_contrast(left["episodes"], right["episodes"], "tgc",
                                                   n_boot=n_boot, seed=bootstrap_seed))
        tgc[spec["id"]] = {"status": "COMPLETE", "definition": contrasts[spec["id"]]["definition"],
                           "point_pp": cmp["scenario"]["diff_pp"], **cmp}
    s_keys = set(arms["S"]["episodes"])
    exploratory = {
        "label": "EXPLORATORY: not decision-bearing (prereg §5)",
        "tgc_contrasts": tgc,
        "copy_rate": copy_rate(s_event_paths([results_root / n for n in campaigns["S"]], s_keys)),
        "cost_per_episode": {
            code: arm_cost(pooled[code]["runs"], sorted(arms[code]["episodes"])) for code in ARM_ORDER
        },
        "cost_note": next(a["script_behaviour"] for a in AMBIGUITIES if a["id"] == "cost_axes"),
    }

    incomplete = [d for d, c in contrasts.items() if c["status"] != "COMPLETE"]
    if missing:
        status, code = "MISSING_CAMPAIGNS", 3
        headline = ("MISSING CAMPAIGNS: " + ", ".join(f"{m['arm']}:{m['campaign']}" for m in missing)
                    + "; no outcome decided")
    elif incomplete or reasons:
        status, code = "INCOMPLETE", 1
        headline = ("INCOMPLETE: " + "; ".join(reasons + [f"{d} {contrasts[d]['reason']}" for d in incomplete])
                    + "; no outcome decided")
    else:
        status, code = "COMPLETE", 0
        headline = f"COMPLETE: {outcome['title']}. {outcome['text']}"
    report.update(
        status=status,
        exit_code=code,
        headline=headline,
        errors=[],
        incomplete_reasons=reasons,
        warnings=warnings,
        n_tasks_observed_union=len(tasks),
        arms={
            c: {"name": ARM_NAMES[c], **{k: v for k, v in arms[c].items() if k != "episodes"},
                "campaigns": pooled[c]["campaigns"]}
            for c in ARM_ORDER
        },
        contrasts=contrasts,
        outcome=outcome,
        registered_expectations=_registered_expectations(contrasts),
        exploratory=exploratory,
    )
    return report, code


# ---- markdown ---------------------------------------------------------------
def _ci(block: Optional[dict[str, Any]]) -> str:
    if not block or block.get("ci95_pp") is None:
        return "-"
    lo, hi = block["ci95_pp"]
    return f"[{lo:+.2f}, {hi:+.2f}]"


def _p(value: Any) -> str:
    return "-" if value is None else f"{float(value):.4g}"


def render_markdown(report: dict[str, Any], json_path: Optional[Path] = None) -> str:
    L: list[str] = ["# B2: decomposing the matched-trigger channel contrast", ""]
    L.append(f"Registered analysis of `{PREREG}` with Amendment 1. Generated by "
             f"`scripts/analysis/b2_decomposition.py`"
             + (f"; JSON: `{json_path}`." if json_path else "."))
    L.append(f"Label: {report['label']}.")
    L += ["", f"**Status: {report['status']}** (exit {report['exit_code']}). {report['headline']}", ""]
    if report.get("errors"):
        L.append("## Errors")
        L += [f"- {e}" for e in report["errors"]] + [""]
        return "\n".join(L) + "\n"
    if report.get("missing_campaigns"):
        L.append("## Missing campaigns")
        L += [f"- {m['arm']}: `{m['campaign']}` (no directory at `{m['path']}`)"
              for m in report["missing_campaigns"]] + [""]

    L += ["## Contrasts on goal_pass", "",
          "D1-D4 are decision-bearing (Holm family); D0 is reported as an extension of C1, not a "
          "replication. Intervals are 95% percentile, B = "
          f"{report['settings']['bootstrap']['n']:,}, seed {report['settings']['bootstrap']['seed']}.", "",
          "| D | contrast | isolates | n pairs | point (pp) | scenario CI (pp) | task CI (pp) | p raw | p Holm | POOL-04 | sign-flip p |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, c in report["contrasts"].items():
        if c["status"] != "COMPLETE":
            L.append(f"| {d} | {c['definition']} | {c['isolates']} | {c['n_pairs']}/{c['n_expected']} "
                     f"| INCOMPLETE: {c['reason']} | | | | | | |")
            continue
        pool = c["pool04"]
        pool_txt = pool["status"]
        if pool.get("bounds_by_seed"):
            pool_txt += " (" + ", ".join(f"{b['seed']}: [{b['lo_pp']:+.2f}, {b['hi_pp']:+.2f}]"
                                         for b in pool["bounds_by_seed"]) + ")"
        L.append(f"| {d} | {c['definition']} | {c['isolates']} | {c['n_pairs']} | {c['point_pp']:+.2f} "
                 f"| {_ci(c['scenario'])} | {_ci(c['task'])} | {_p(c['p_raw'])} | {_p(c.get('p_holm'))} "
                 f"| {pool_txt} | {_p(c['signflip'].get('p_value'))} |")
    L.append("")

    outcome = report.get("outcome") or {}
    L.append("## Outcome")
    if not outcome.get("decided"):
        L += [f"**{outcome.get('title', 'No outcome decided')}.** {outcome.get('text', '')}", ""]
    else:
        L += [f"**{outcome['title']}.** {outcome['text']}", "",
              "Rule trace (registered order; the first that fires is the headline):", ""]
        for step in outcome["trace"]:
            mark = "HEADLINE" if step["headline"] else ("fires" if step["fires"] else "does not fire")
            L.append(f"{step['order']}. **{step['title']}**: {mark}")
            for cond in step["conditions"]:
                name = f"{cond['contrast']} {cond['requires']}" if cond["contrast"] else cond["requires"]
                L.append(f"   - {name}: {'held' if cond['held'] else 'failed'} ({cond['why']})")
        L.append("")
    if report.get("registered_expectations"):
        L.append("Registered expectations (not predictions): " + "; ".join(
            f"{e['expectation']}: {e['on_point_estimates']}" for e in report["registered_expectations"]))
        L.append("")

    L += ["## Arms", "", "| arm | campaigns (results) | scored / 171 | crash | missing | error_type counts |",
          "|---|---|---|---|---|---|"]
    for code, arm in report["arms"].items():
        camps = ", ".join(f"`{c['campaign']}` ({c['n_results'] if c['present'] else 'absent'})"
                          for c in arm["campaigns"])
        L.append(f"| {code} ({arm['name']}) | {camps} | {arm['n_scored']} | {arm['n_crash']} "
                 f"| {arm['n_missing']} | {json.dumps(arm['error_types'])} |")
    if report.get("warnings"):
        L += [""] + [f"- warning: {w}" for w in report["warnings"]]
    L.append("")

    ex = report["exploratory"]
    L += ["## Exploratory (not decision-bearing; prereg §5)", "", "### D0-D4 on TGC", "",
          "| D | contrast | n pairs | point (pp) | scenario CI (pp) | task CI (pp) |", "|---|---|---|---|---|---|"]
    for d, t in ex["tgc_contrasts"].items():
        if t["status"] != "COMPLETE":
            L.append(f"| {d} | | | INCOMPLETE | | |")
        else:
            L.append(f"| {d} | {t['definition']} | {t['n_pairs']} | {t['point_pp']:+.2f} "
                     f"| {_ci(t['scenario'])} | {_ci(t['task'])} |")
    cr = ex["copy_rate"]
    L += ["", "### Copy rate (S)", "",
          f"{cr['n_copied']} of {cr['n_shown']} shown actions reproduced verbatim as the executor's next "
          f"action (copy rate {cr['copy_rate']}; among the {cr['n_followed_by_an_executor_action']} "
          f"followed by an executor action: {cr['copy_rate_among_followed']}). By shown kind: "
          f"{json.dumps(cr['by_shown_kind'])}. Episodes read {cr['n_episodes']}, without events "
          f"{cr['n_episodes_without_events']}.", "",
          "### Cost per episode", "",
          "| arm | episodes | hosted calls | non-cached planner tokens | USD |", "|---|---|---|---|---|"]
    for code, c in ex["cost_per_episode"].items():
        L.append(f"| {code} | {c['n_episodes']} | {c['hosted_calls_per_episode']} "
                 f"| {c['noncached_tokens_per_episode']} | {c['usd_per_episode']} |")
    L += ["", ex["cost_note"], "", "## Ambiguities resolved in code", ""]
    L += [f"- **{a['id']}**: {a['script_behaviour']}" for a in report["ambiguities"]]
    return "\n".join(L) + "\n"


# ---- CLI --------------------------------------------------------------------
def _parse_arm_override(specs: Optional[list[str]]) -> Optional[dict[str, tuple[str, ...]]]:
    if not specs:
        return None
    out = dict(ARM_CAMPAIGNS)
    for spec in specs:
        code, sep, raw = spec.partition("=")
        names = tuple(n.strip() for n in raw.split(",") if n.strip())
        if not sep or code not in ARM_CAMPAIGNS or not names:
            raise ValueError(f"expected CODE=CAMPAIGN[,CAMPAIGN] with CODE in {list(ARM_ORDER)}, got {spec!r}")
        out[code] = names
    return out


def _md_path(json_path: Path) -> Path:
    name = json_path.name
    if name.endswith(".report.json"):
        return json_path.with_name(name[: -len(".report.json")] + ".md")
    return json_path.with_suffix(".md")


def _refuse_out(path: Path, out_root: Path) -> Optional[str]:
    resolved = path.resolve()
    for root in (*FORBIDDEN_OUT_ROOTS, out_root):
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"refusing --out {path}: it is under {root}, which holds raw results (read-only)"
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="B2 registered decomposition (prereg_c1_decomposition_20260923 + A1).")
    p.add_argument("--out-root", type=Path, default=RESULTS_ROOT,
                   help="root holding the campaign directories (the runner's --out-root); "
                        f"default {RESULTS_ROOT}")
    p.add_argument("--date", default=None, help="YYYYMMDD in the output names (default: today)")
    p.add_argument("--out", type=Path, default=None,
                   help=f"report JSON (default {OUT_DIR.relative_to(REPO_ROOT)}/{OUT_STEM}_<date>.report.json); "
                        "the .md summary is written beside it")
    p.add_argument("--arm", action="append", default=None, metavar="CODE=CAMPAIGN[,CAMPAIGN]",
                   help="override one arm's campaigns (default: Amendment 1 §5); marks the report non-registered")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        date = args.date or _dt.date.today().strftime("%Y%m%d")
        if len(date) != 8 or not date.isdigit():
            raise ValueError(f"--date must be YYYYMMDD, got {date!r}")
        arm_campaigns = _parse_arm_override(args.arm)
    except ValueError as exc:
        print(json.dumps({"protocol": "B2", "status": "REFUSED", "reason": str(exc)}))
        return 2
    out = args.out or OUT_DIR / f"{OUT_STEM}_{date}.report.json"
    refusal = _refuse_out(out, args.out_root)
    if refusal:
        print(json.dumps({"protocol": "B2", "status": "REFUSED", "reason": refusal}))
        return 2
    report, code = build_report(results_root=args.out_root, arm_campaigns=arm_campaigns)
    report["date"] = date
    md = _md_path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    md.write_text(render_markdown(report, out), encoding="utf-8")
    print(json.dumps({"protocol": "B2", "status": report["status"], "exit_code": code,
                      "headline": report["headline"], "json": str(out), "md": str(md)}, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
