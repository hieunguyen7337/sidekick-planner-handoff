#!/usr/bin/env python3
"""J17 h*: the numbers behind ledger rows HO-01..HO-09 and HO-NI-01..03, with h* in place of the flag.

What this is for
----------------
Every handoff-only number on the dev cap-81 prefix family used h = the prefix arm's
``handoff_occurred`` (``effective_m < n_source_actions``, src/sidekick/prefix_source.py:184). That
flag is false whenever the source planner episode made at most m executed actions, but the loop
skips its live phase only when the replayed prefix is *terminal* (src/sidekick/systems/loop.py:
743-756). A source that stopped at a limit, repeated REPORT, or wrote no plan therefore gives a
false flag while the executor still takes control. h* (scripts/analysis/handoff_control.py) is
the indicator of what happened: the executor took control after the prefix.

This script recomputes, dev only, everything behind HO-01..09 and HO-NI-01..03 with h* in place
of the flag -- the per-arm handoff / silenced means, the m6 -> m11 and m9 -> m11 spans with their
decomposition, and non-inferiority against the planner alone at -7 pp, on `goal_pass` and TGC,
both receivers, scenario and task clusterings, 10,000 draws, seed 20260924 -- and reports:

* validation: (1) h_flag true => h* = 1 on every episode; (2) on every flag-false episode h*
  equals NOT prefix_is_terminal recomputed from the SOURCE episode through sidekick's own
  build_handoff_prefix and prefix_is_terminal (imported, not re-implemented), plus the same test on
  every episode; (3)-(4) the synthetic planless and terminal cases;
* the per-arm count table (h_flag true / live but unflagged / terminal);
* the rescued episodes at m = 11 (h* = 1, flag false): the arm's goal_pass against the source
  planner's on the same key, per receiver;
* every HO-row number that moves, old (the committed flag report) against new;
* ``cap25_counts`` (added 2026-09-24, unit V2INT): counts only, for the cap-25 prefix family behind
  SHAPE-06 and ROB-12 (hj12_prefix_m{2..11}_20260923, hj13_prefix_zs_m{6,9,11}_20260923, source
  hj1b_planner_20260915): per depth h_flag true / live but unflagged / terminal, SHAPE-06's
  executor-never-acted count, and h* against the source's own prefix_is_terminal. It is computed after
  every other block and changes none of their keys.

Reuse, not re-implementation
----------------------------
Loading, pairing, the bootstrap and every block are j17_depth_fixes' (family_sources,
load_depth_rows, drop_crashed, bootstrap_settings, handoff_arm_block, depth_contrast, ni_block),
which read h through j16_robustness.handoff_flag -> ``_facts.handoff_occurred``. The rows handed
to them are copies whose ``_facts.handoff_occurred`` holds h* (``_facts.h_flag`` keeps the flag);
nothing else about them changes. In this report's blocks every key name inherited from
j17_depth_fixes that says "handoff_occurred" or "handoff flag" therefore refers to h*. The
held-out refusal is j17_channel_fixes.refuse_path / _refuse_out, copied, with `j11_` and `j12_`
added to the refused markers.

Interface:
  python scripts/analysis/j17_hstar.py [--out campaign/results/j17_hstar_20260924.report.json]
      [--n-boot 10000] [--seed 20260924] [--results-root /scratch/n12194778/sidekick/results]
      [--flag-report campaign/results/j17_depth_fixes_20260924.report.json]
Exit 0: written and every validation holds; 1: written, a validation failed; 2: refused.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts.analysis import handoff_control as hc  # noqa: E402
from scripts.analysis import j17_depth_fixes as j17d  # noqa: E402
from scripts.setup.hj1_gate import scenario_of  # noqa: E402

j16 = j17d.j16
Key = tuple  # (task_id, seed)

PROTOCOL = "J17-HSTAR"
RESULTS_DIR = j17d.RESULTS_DIR
DEFAULT_OUT = REPO / "campaign" / "results" / "j17_hstar_20260924.report.json"
FLAG_REPORT = REPO / "campaign" / "results" / "j17_depth_fixes_20260924.report.json"
N_BOOT = j17d.N_BOOT  # 10,000
SEED = j17d.SEED  # 20260924
RECEIVERS = j17d.RECEIVERS
DEPTHS = j17d.DEPTHS
NI_DEPTHS = j17d.NI_DEPTHS
DEPTH_PAIRS = j17d.DEPTH_PAIRS
METRICS = j17d.METRICS
RESCUE_DEPTH = 11
SOURCE_SYSTEM = j17d.PACKET_SYSTEM  # the prefix arms replay planner_alone episodes
PREFIX_LABELS = tuple(f"{rx}_m{m}" for rx in RECEIVERS for m in DEPTHS)
# The forensics pass's counts of flag-false episodes by the source's terminality (brief HSTAR §Validation 2).
EXPECTED_FLAG_FALSE = {11: {"terminal": 83, "live": 17}, 9: {"terminal": 43, "live": 11}}

# ---- the held-out guard, copied from j17_channel_fixes.refuse_path / _refuse_out ----------------------
REFUSED_MARKERS = ("test_normal", "test_challenge", "j10_", "j11_", "j12_")
FORBIDDEN_OUT_ROOTS = (Path("/scratch"),)  # b2_decomposition.FORBIDDEN_OUT_ROOTS
# Dev campaigns whose names hold a refused marker as a substring ("hj12_" contains "j12_"): the cap-25
# family's tailored arms, dev runs of the hj12 series (57 dev tasks, seeds 1-2; SHAPE-06, j16_robustness
# "t_m*"), not J12 data. Exempt only as an exact path component, so every other path is checked as before.
DEV_NAMES_HOLDING_A_MARKER = frozenset(f"hj12_prefix_m{m}_20260923" for m in (2, 4, 6, 7, 8, 9, 10, 11))


def _marker_text(text: str) -> str:
    """The path text with each exempt dev campaign component blanked; every other component unchanged."""
    return "/".join("<dev>" if part in DEV_NAMES_HOLDING_A_MARKER else part for part in Path(text).parts)


def refuse_path(path: Path) -> Optional[str]:
    """A refusal message if the path (as given or resolved) names held-out or J10-J12 data."""
    texts = {str(path)}
    try:
        texts.add(str(Path(path).resolve()))
    except OSError:
        pass
    for text in sorted(texts):
        scan = _marker_text(text)
        for marker in REFUSED_MARKERS:
            if marker in scan:
                return f"refusing {path}: contains {marker!r} (dev only; held-out and J10-J12 data are not read here)"
    return None


def _refuse_out(path: Path) -> Optional[str]:
    resolved = Path(path).resolve()
    for root in FORBIDDEN_OUT_ROOTS:
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"refusing --out {path}: it is under {root}, which holds raw results (read-only)"
    return None


class RefusedPath(RuntimeError):
    pass


def _check(path: Path) -> None:
    reason = refuse_path(path)
    if reason:
        raise RefusedPath(reason)


# ---- loading -----------------------------------------------------------------------------------------
def load_controls(sources: list[dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    """handoff_control.arm_control pooled over one arm's campaign roots, seeds as j17 takes them."""
    merged: dict[Key, dict[str, Any]] = {}
    for src in sources:
        _check(src["root"])
        ctl = hc.arm_control(Path(src["root"]), src["seeds"])
        clash = set(merged) & set(ctl)
        if clash:
            raise ValueError(f"pooled arm: {len(clash)} colliding keys at {src['root']}")
        merged.update(ctl)
    return merged


def with_hstar(rows: dict[Key, dict[str, Any]], controls: dict[Key, dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    """Row copies whose ``_facts.handoff_occurred`` is h* (None when undefined); the flag is kept
    as ``_facts.h_flag``. Every j16 / j17 helper then reads h* where it read the flag."""
    out: dict[Key, dict[str, Any]] = {}
    for k, row in rows.items():
        facts = dict(row.get("_facts") or {})
        hs = (controls.get(k) or {}).get(hc.HSTAR_NAME)
        facts[hc.HFLAG_NAME] = facts.get("handoff_occurred")
        facts[hc.HSTAR_NAME] = hs
        facts["handoff_occurred"] = hs
        out[k] = dict(row, _facts=facts)
    return out


def _source_for(sources: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    for src in sources:
        if int(seed) in src["seeds"]:
            return src
    raise KeyError(f"no source campaign holds seed {seed}")


# ---- validation 2: the source episode's own prefix, through sidekick's code ---------------------------
class _NoopWorld:
    """A world that replays nothing. build_handoff_prefix needs only reset / step / snapshot_hash /
    close of its env (src/sidekick/replay.py:95-106, src/sidekick/prefix_source.py:142, :159) to
    return the prefix slice it hands the loop; the hash check it then fails is not read here."""

    def reset(self, task_id: str, seed: int) -> None:
        return None

    def step(self, action: Any) -> None:
        return None

    def snapshot_hash(self) -> str:
        return "noop-world"

    def close(self) -> None:
        return None


def source_prefix_facts(source_campaign: Path, task_id: str, seed: int, m: int) -> dict[str, Any]:
    """prefix_is_terminal of the source episode's m-prefix, computed as the loop computes it
    (loop.py:632 and :746) on the slice build_handoff_prefix returns (prefix_source.py:157, :178)."""
    from sidekick.prefix_source import build_handoff_prefix
    from sidekick.systems.loop import last_observation_from_events, prefix_is_terminal

    _check(source_campaign)
    built = build_handoff_prefix(source_campaign, SOURCE_SYSTEM, task_id, seed, m, _NoopWorld())
    out: dict[str, Any] = {"effective_m": built.effective_m, "n_source_actions": built.n_source_actions,
                           "handoff_occurred": built.handoff_occurred}
    if built.prefix is None:
        out.update(status=str(built.broken_reason), terminal=None)
        return out
    events = list(built.prefix.events)
    last_obs = last_observation_from_events(events)
    last_action = next((e for e in reversed(events) if e.event_type == "action"), None)
    out.update(status="ok", terminal=bool(prefix_is_terminal(events, last_obs)),
               last_obs_done=bool(last_obs.done), last_obs_step=int(last_obs.step),
               last_action_kind=None if last_action is None else (last_action.payload or {}).get("kind"),
               n_prefix_events=len(events))
    return out


def validate(raw: dict[str, dict[Key, dict[str, Any]]], controls: dict[str, dict[Key, dict[str, Any]]],
             sources: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], dict[tuple, dict[str, Any]]]:
    """Validation 1 and 2 on every episode of every prefix arm (crashes included), plus the
    agreement of the recomputed prefix facts with each arm's own handoff record."""
    cache: dict[tuple, dict[str, Any]] = {}
    v1: dict[str, Any] = {}
    v2: dict[str, Any] = {}
    v2_all: dict[str, Any] = {}
    record: dict[str, Any] = {}
    terminal_sets: dict[str, set] = {}
    hstar_sets: dict[str, set] = {}
    for rx in RECEIVERS:
        for m in DEPTHS:
            label = f"{rx}_m{m}"
            ctl = controls[label]
            keys = sorted(raw[label])
            flag_true = [k for k in keys if (ctl.get(k) or {}).get(hc.HFLAG_NAME) is True]
            viol1 = [list(k) for k in flag_true if (ctl.get(k) or {}).get(hc.HSTAR_NAME) is not True]
            v1[label] = {"n_h_flag_true": len(flag_true), "n_hstar_1_among_them": len(flag_true) - len(viol1),
                         "violations": viol1, "holds": not viol1}
            n_false = n_term = n_live = n_agree = n_agree_all = n_undef = 0
            dis, dis_all = [], []
            mism = {"effective_m": 0, "n_source_actions": 0, "handoff_occurred": 0, "source_campaign": 0}
            terms: set = set()
            for k in keys:
                c = ctl.get(k) or {}
                src = _source_for(sources[label], k[1])
                ck = (str(src["packet_source"]), k[0], int(k[1]), m)
                if ck not in cache:
                    cache[ck] = source_prefix_facts(Path(src["packet_source"]), k[0], int(k[1]), m)
                facts = cache[ck]
                term = facts.get("terminal")
                hs = c.get(hc.HSTAR_NAME)
                if term is None or hs is None:
                    n_undef += 1
                    continue
                if term:
                    terms.add(k)
                agree = hs is (not term)
                n_agree_all += int(agree)
                if not agree:
                    dis_all.append([k[0], k[1], hs, term])
                mism["effective_m"] += int(facts["effective_m"] != c.get("effective_m"))
                mism["n_source_actions"] += int(facts["n_source_actions"] != c.get("n_source_actions"))
                mism["handoff_occurred"] += int(facts["handoff_occurred"] is not c.get(hc.HFLAG_NAME))
                # The record names the campaign it replayed; the name must be the source used here.
                mism["source_campaign"] += int(Path(str(c.get("source_campaign"))).name
                                               != Path(str(src["packet_source"])).name)
                if c.get(hc.HFLAG_NAME) is False:
                    n_false += 1
                    n_term += int(term)
                    n_live += int(not term)
                    n_agree += int(agree)
                    if not agree:
                        dis.append([k[0], k[1], hs, term])
            terminal_sets[label] = terms
            hstar_sets[label] = {k for k in keys if (ctl.get(k) or {}).get(hc.HSTAR_NAME) is True}
            exp = EXPECTED_FLAG_FALSE.get(m)
            v2[label] = {"n_flag_false": n_false, "n_source_terminal": n_term, "n_source_live": n_live,
                         "n_hstar_equals_not_terminal": n_agree, "disagreements": dis,
                         "holds": not dis and n_agree == n_false,
                         "expected": exp,
                         "matches_expected": None if exp is None else (exp["terminal"], exp["live"]) == (n_term, n_live)}
            v2_all[label] = {"n": len(keys), "n_undefined": n_undef, "n_hstar_equals_not_terminal": n_agree_all,
                             "disagreements": dis_all, "holds": not dis_all and n_undef == 0}
            record[label] = {"n_mismatch": mism, "holds": not any(mism.values())}
    same = {f"m{m}": {"source_terminal_keys_identical": terminal_sets[f"bplus_m{m}"] == terminal_sets[f"zs_m{m}"],
                      "hstar_keys_identical": hstar_sets[f"bplus_m{m}"] == hstar_sets[f"zs_m{m}"]}
            for m in DEPTHS}
    synthetic = hc.check_synthetic_cases()
    all_hold = (all(v["holds"] for v in v1.values()) and all(v["holds"] for v in v2.values())
                and all(v["matches_expected"] is not False for v in v2.values())
                and all(v["holds"] for v in v2_all.values()) and all(v["holds"] for v in record.values())
                and all(all(s.values()) for s in same.values()) and synthetic["all_hold"])
    return {
        "v1_h_flag_true_implies_hstar": v1,
        "v2_flag_false_hstar_equals_not_source_terminal": v2,
        "v2_every_episode_hstar_equals_not_source_terminal": v2_all,
        "record_agreement": record,
        "receivers_agree": same,
        "v3_v4_synthetic": synthetic,
        "method_v2": ("sidekick.prefix_source.build_handoff_prefix(source planner_alone campaign, task, seed, m) "
                      "with a no-op world, then sidekick.systems.loop.last_observation_from_events and "
                      "prefix_is_terminal on its prefix events, as run_episode does (loop.py:632, :746)"),
        "all_hold": all_hold,
    }, cache


# ---- the h* blocks (HO-01..09, HO-NI-01..03 shapes) ---------------------------------------------------
def hstar_blocks(depth_h: dict[str, dict[Key, dict[str, Any]]], n_boot: int, seed: int) -> dict[str, Any]:
    """j17_depth_fixes' handoff_only / handoff_only_contrasts / ni blocks, on rows carrying h*."""
    with j17d.bootstrap_settings(n_boot, seed):
        print("[j17-hstar] handoff-only blocks ...", flush=True)
        handoff_only = {rx: {f"m{m}": j17d.handoff_arm_block(depth_h[f"{rx}_m{m}"], n_boot) for m in DEPTHS}
                        for rx in RECEIVERS}
        print("[j17-hstar] depth contrasts ...", flush=True)
        contrasts = {
            rx: {f"m{a}_to_m{b}": {metric: j17d.depth_contrast(depth_h[f"{rx}_m{a}"], depth_h[f"{rx}_m{b}"],
                                                               field, metric, n_boot, seed)
                                   for metric, field in METRICS}
                 for a, b in DEPTH_PAIRS}
            for rx in RECEIVERS}
        print("[j17-hstar] non-inferiority ...", flush=True)
        ni = {rx: {f"m{m}": {metric: j17d.ni_block(depth_h[f"{rx}_m{m}"], depth_h["ceiling"], field, metric,
                                                   n_boot, seed)
                             for metric, field in METRICS}
                   for m in NI_DEPTHS}
              for rx in RECEIVERS}
    return {"handoff_only": handoff_only, "handoff_only_contrasts": contrasts, "ni": ni}


# ---- rescued episodes -----------------------------------------------------------------------------------
def source_tail(source_campaign: Path, task_id: str, seed: int, after_step: int) -> dict[str, Any]:
    """What the source episode did after its replayed prefix: the kinds of the actions it recorded
    at steps after the prefix's last observation, and its last step (last attempt only)."""
    _check(source_campaign)
    path = Path(source_campaign) / SOURCE_SYSTEM / str(seed) / str(task_id) / "events.jsonl"
    evs = hc.last_attempt(hc.read_events(path))
    kinds: dict[str, int] = {}
    last_step = 0
    for ev in evs:
        step = ev.get("step")
        if isinstance(step, int) and not isinstance(step, bool):
            last_step = max(last_step, step)
            if ev.get("event_type") == "action" and step > int(after_step):
                kind = str((ev.get("payload") or {}).get("kind"))
                kinds[kind] = kinds.get(kind, 0) + 1
    return {"source_action_kinds_after_prefix": dict(sorted(kinds.items())), "source_last_step": last_step}


def rescued_block(rows: dict[Key, dict[str, Any]], controls: dict[Key, dict[str, Any]],
                  ceiling: dict[Key, dict[str, Any]], source_facts: dict[Key, dict[str, Any]],
                  n_boot: int, seed: int) -> dict[str, Any]:
    """Episodes with h* = 1 and the flag not true: the arm's outcome against the source planner's
    (planner_alone_cap81) on the same (task_id, seed), with the source facts behind the flag."""
    keys = sorted(k for k, c in controls.items()
                  if k in rows and c.get(hc.HSTAR_NAME) is True and c.get(hc.HFLAG_NAME) is not True)
    episodes = []
    diffs: dict[str, dict[Key, float]] = {"goal_pass": {}, "tgc": {}}
    for k in keys:
        arm, ref = rows[k], ceiling.get(k)
        c, sf = controls[k], source_facts.get(k) or {}
        ep: dict[str, Any] = {"task_id": k[0], "seed": k[1], "scenario": scenario_of(k[0]),
                              "effective_m": c.get("effective_m"), "n_source_actions": c.get("n_source_actions"),
                              "planless": c.get("n_source_actions") == 0,
                              "source_last_action_kind": sf.get("last_action_kind"),
                              "source_last_obs_done": sf.get("last_obs_done"),
                              "source_action_kinds_after_prefix": sf.get("source_action_kinds_after_prefix"),
                              "source_last_step": sf.get("source_last_step"),
                              "first_live_event": c.get("first_live_event"),
                              "arm_error_type": arm.get("error_type"),
                              "source_error_type": None if ref is None else ref.get("error_type"),
                              "source_steps": None if ref is None else ref.get("steps")}
        for metric, field in METRICS:
            a = j16.quality(arm, field)
            b = None if ref is None else j16.quality(ref, field)
            ep[f"arm_{metric}"], ep[f"source_{metric}"] = a, b
            if a is not None and b is not None:
                diffs[metric][k] = a - b
        episodes.append(ep)
    summary: dict[str, Any] = {}
    for metric, _field in METRICS:
        d = diffs[metric]
        arm_vals = [e[f"arm_{metric}"] for e in episodes if e[f"source_{metric}"] is not None and e[f"arm_{metric}"] is not None]
        src_vals = [e[f"source_{metric}"] for e in episodes if e[f"source_{metric}"] is not None and e[f"arm_{metric}"] is not None]
        blk: dict[str, Any] = {
            "n_pairs": len(d),
            "mean_arm": statistics.fmean(arm_vals) if arm_vals else None,
            "mean_source_planner": statistics.fmean(src_vals) if src_vals else None,
            "diff_pp": None if not d else 100.0 * statistics.fmean(d.values()),
            "n_arm_above": sum(1 for v in d.values() if v > 0),
            "n_equal": sum(1 for v in d.values() if v == 0),
            "n_arm_below": sum(1 for v in d.values() if v < 0),
        }
        for unit in ("scenario", "task"):
            b = j16.boot_mean(d, unit, seed, n_boot) if d else {"ci95": None, "n_clusters": 0}
            blk[f"ci95_pp_{unit}"] = None if b["ci95"] is None else [100.0 * b["ci95"][0], 100.0 * b["ci95"][1]]
            blk[f"n_clusters_{unit}"] = b["n_clusters"]
        summary[metric] = blk
    return {
        "n": len(keys),
        "n_planless": sum(1 for e in episodes if e["planless"]),
        "source_error_types": dict(sorted(_count(e["source_error_type"] for e in episodes).items())),
        "source_last_action_kinds": dict(sorted(_count(e["source_last_action_kind"] for e in episodes).items())),
        "source_action_kinds_after_prefix": _sum_kinds(e.get("source_action_kinds_after_prefix") for e in episodes),
        "n_sources_only_report_after_prefix": sum(
            1 for e in episodes if (e.get("source_action_kinds_after_prefix") or {})
            and set(e["source_action_kinds_after_prefix"]) == {"REPORT"}),
        "n_sources_ending_at_step_limit": sum(
            1 for e in episodes if e.get("source_error_type") == "limit" and e.get("source_steps") == 40),
        "arm_error_types": dict(sorted(_count(e["arm_error_type"] for e in episodes).items())),
        "first_live_event_types": dict(sorted(_count(
            f"{(e['first_live_event'] or {}).get('actor')}/{(e['first_live_event'] or {}).get('event_type')}"
            for e in episodes).items())),
        "summary": summary,
        "episodes": episodes,
        "comparison": "arm − planner_alone_cap81 on the same (task_id, seed); descriptive, scenario and task "
                      "cluster percentile intervals of the mean paired difference",
    }


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def _sum_kinds(dicts) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in dicts:
        for k, v in (d or {}).items():
            out[k] = out.get(k, 0) + int(v)
    return dict(sorted(out.items()))


# ---- the cap-25 prefix family: counts only (SHAPE-06, ROB-12) ------------------------------------------------
# The published cap-25 depth curve (SHAPE-06) and ROB-12's explanation of its flag / never-acted gap rest
# on the same `handoff_occurred` flag. These are the arms behind them (j16_robustness._arm_dirs "t_m*" and
# "zs_m*", FC_FAMILIES["cap25_source"]); they replay the cap-25 planner sample hj1b_planner_20260915, seeds 1-2.
CAP25_SOURCE = "hj1b_planner_20260915"
CAP25_SEEDS = (1, 2)
CAP25_ARMS: dict[str, dict[int, str]] = {
    "tailored": {m: f"hj12_prefix_m{m}_20260923" for m in (2, 4, 6, 7, 8, 9, 10, 11)},
    "untailored": {m: f"hj13_prefix_zs_m{m}_20260923" for m in (6, 9, 11)},
}
# SHAPE-06's "silenced" counts, tailored m = 2..11: result.json totals.per_actor.executor.n_calls == 0
# (GUARD-01's definition; j16_robustness.executor_calls). ROB-12's flag-false counts are in the j16 report.
SHAPE06_NEVER_ACTED = {2: 0, 4: 0, 6: 3, 7: 8, 8: 20, 9: 31, 10: 41, 11: 56}


def cap25_sources(results_root: Path | str) -> dict[str, dict[str, Any]]:
    r = Path(results_root)
    return {f"{rx}_m{m}": j17d._source(r, campaign, "prefix_handoff", CAP25_SEEDS, CAP25_SOURCE)
            for rx, arms in CAP25_ARMS.items() for m, campaign in arms.items()}


def cap25_counts(results_root: Path | str) -> dict[str, Any]:
    """Per cap-25 prefix arm: h_flag true / live but unflagged / terminal (h* = 0), the executor-never-acted
    count SHAPE-06 uses, and h* against the SOURCE episode's own prefix_is_terminal (sidekick's code, as in
    validation 2). Counts only: no bootstrap, no quality values. Crashed episodes are dropped and counted."""
    sources = cap25_sources(results_root)
    for src in sources.values():
        _check(src["root"])
        _check(src["packet_source"])
    cache: dict[tuple, dict[str, Any]] = {}
    arms: dict[str, Any] = {}
    for label, src in sources.items():
        m = int(label.rsplit("_m", 1)[1])
        print(f"[j17-hstar] cap-25 counts {label} ...", flush=True)
        rows, _diag = j16.load_campaign_dir(src["root"], src["seeds"])
        scored = j17d.drop_crashed(rows)
        ctl = hc.arm_control(src["root"], src["seeds"])
        counts = hc.control_counts(ctl, keys=scored.keys())
        never = {k for k, row in scored.items() if j16.executor_calls(row) == 0}
        terminal = {k for k in scored if (ctl.get(k) or {}).get(hc.HSTAR_NAME) is False}
        flag_not_true = {k for k in scored if (ctl.get(k) or {}).get(hc.HFLAG_NAME) is not True}
        n_src_term = n_src_live = n_src_undef = 0
        disagree: list[list[Any]] = []
        flag_false_acted: list[dict[str, Any]] = []
        for k in sorted(scored):
            ck = (str(src["packet_source"]), k[0], int(k[1]), m)
            if ck not in cache:
                cache[ck] = source_prefix_facts(Path(src["packet_source"]), k[0], int(k[1]), m)
            term = cache[ck].get("terminal")
            hs = (ctl.get(k) or {}).get(hc.HSTAR_NAME)
            if term is None or hs is None:
                n_src_undef += 1
                continue
            n_src_term += int(term)
            n_src_live += int(not term)
            if hs is term:  # h* must equal NOT terminal
                disagree.append([k[0], k[1], hs, term])
            if k in flag_not_true and k not in never:
                flag_false_acted.append({"task_id": k[0], "seed": k[1], "h_star": hs, "source_prefix_terminal": term,
                                         "effective_m": (ctl.get(k) or {}).get("effective_m"),
                                         "n_source_actions": (ctl.get(k) or {}).get("n_source_actions"),
                                         "source_last_action_kind": cache[ck].get("last_action_kind"),
                                         "source_last_obs_done": cache[ck].get("last_obs_done"),
                                         "executor_n_calls": j16.executor_calls(scored[k])})
        shape06 = SHAPE06_NEVER_ACTED.get(m) if label.startswith("tailored_") else None
        arms[label] = {
            "campaign": src["campaign"], "depth": m, "n_scored": len(scored), "n_crash": len(rows) - len(scored),
            "n_h_flag_true": counts["n_h_flag_true"],
            "n_live_but_unflagged": counts["n_live_but_unflagged"],
            "n_terminal": counts["n_terminal"],
            "n_hstar_true": counts["n_hstar_true"],
            "n_hstar_undefined": counts["n_hstar_undefined"],
            "n_h_flag_true_but_terminal": counts["n_h_flag_true_but_terminal"],
            "n_h_flag_not_true": len(flag_not_true),
            "n_executor_never_acted": len(never),
            "n_terminal_but_executor_acted": len(terminal - never),
            "n_hstar_true_but_executor_never_acted": len((set(scored) - terminal) & never),
            "terminal_equals_executor_never_acted": terminal == never,
            "n_source_prefix_terminal": n_src_term, "n_source_prefix_live": n_src_live,
            "n_source_undefined": n_src_undef,
            "hstar_equals_not_source_terminal": {"n_disagree": len(disagree), "disagreements": disagree,
                                                  "holds": not disagree and n_src_undef == 0},
            "flag_not_true_but_executor_acted": flag_false_acted,
            "shape06_never_acted": shape06,
            "matches_shape06_never_acted": None if shape06 is None else shape06 == len(never),
        }
    return {
        "source": CAP25_SOURCE, "seeds": list(CAP25_SEEDS),
        "arms_behind": "SHAPE-06 (tailored post-guard curve, m = 2..11) and ROB-12 (j16_robustness F_c cap25_source)",
        "definitions": {"h_star": hc.DEFINITION, "h_flag": hc.FLAG_DEFINITION,
                        "executor_never_acted": "result.json totals.per_actor.executor.n_calls == 0 (SHAPE-06, GUARD-01)",
                        "source_prefix_terminal": ("sidekick.systems.loop.prefix_is_terminal of the SOURCE episode's "
                                                   "m-prefix via build_handoff_prefix (as validation 2)")},
        "arms": arms,
        "all_hstar_equal_not_source_terminal": all(a["hstar_equals_not_source_terminal"]["holds"] for a in arms.values()),
    }


# ---- old against new -------------------------------------------------------------------------------------
def _ho_row(path: tuple[str, ...]) -> Optional[str]:
    """Which ledger row a leaf of the flag report's handoff blocks belongs to."""
    top = path[0]
    if top == "handoff_only":
        rx, rest = path[1], path[3:]
        if rest and rest[0] in ("goal_pass", "tgc"):
            return "HO-02" if rx == "bplus" else "HO-03"
        return "HO-01"
    if top == "handoff_only_contrasts":
        rx, pair, metric = path[1], path[2], path[3]
        if len(path) > 4 and path[4] == "decomposition":
            return "HO-08" if pair == "m9_to_m11" else "HO-09"
        return {("bplus", "goal_pass"): "HO-04", ("bplus", "tgc"): "HO-05",
                ("zs", "goal_pass"): "HO-06", ("zs", "tgc"): "HO-07"}[(rx, metric)]
    if top == "ni":
        rx, metric = path[1], path[3]
        if metric == "tgc":
            return "HO-NI-03"
        return "HO-NI-01" if rx == "bplus" else "HO-NI-02"
    return None


def _leaves(obj: Any, path: tuple[str, ...] = ()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, path + (str(k),))
    elif isinstance(obj, list) and obj and all(not isinstance(v, (dict, list)) for v in obj):
        yield path, obj
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, path + (str(i),))
    else:
        yield path, obj


def changes_vs_flag(new: dict[str, Any], flag: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Every leaf of the HO blocks whose value moves from the flag report to this one, by ledger row,
    and a check that no all-episode value moved (they do not depend on h)."""
    if flag is None:
        return {"status": "absent"}
    rows: dict[str, dict[str, Any]] = {}
    moved_all: list[str] = []
    missing: list[str] = []
    for top in ("handoff_only", "handoff_only_contrasts", "ni"):
        old_leaves = dict(_leaves(flag.get(top, {}), (top,)))
        new_leaves = dict(_leaves(new.get(top, {}), (top,)))
        for path, old in old_leaves.items():
            if path not in new_leaves:
                missing.append(".".join(path))
                continue
            val = new_leaves[path]
            if val == old:
                continue
            row = _ho_row(path)
            dotted = ".".join(path)
            # An all-episode value: a contrast or mean over every pair, or the decomposition's total.
            if "all" in path or path[-1] == "mean_all" or "delta_total" in path:
                moved_all.append(dotted)
            entry = {"old": old, "new": val}
            if isinstance(old, (int, float)) and isinstance(val, (int, float)) and not isinstance(old, bool):
                entry["delta"] = round(val - old, 6)
            blk = rows.setdefault(row or "other", {"n_changed": 0, "changes": {}})
            blk["n_changed"] += 1
            blk["changes"][dotted] = entry
    return {"status": "ok", "by_row": dict(sorted(rows.items())),
            "all_episode_values_unchanged": not moved_all, "all_episode_values_moved": moved_all,
            "paths_missing_in_new": missing}


# ---- report ----------------------------------------------------------------------------------------------
def build_report(results_root: Path | str, n_boot: int = N_BOOT, seed: int = SEED,
                 flag_report: Optional[dict[str, Any]] = None, flag_report_path: Optional[str] = None) -> dict[str, Any]:
    results_root = Path(results_root)
    sources = j17d.family_sources(results_root)
    labels = ("ceiling",) + PREFIX_LABELS
    for label in labels:
        for src in sources[label]:
            _check(src["root"])
            _check(src["packet_source"])
    raw: dict[str, dict[Key, dict[str, Any]]] = {}
    depth: dict[str, dict[Key, dict[str, Any]]] = {}
    controls: dict[str, dict[Key, dict[str, Any]]] = {}
    dirs: dict[str, Any] = {}
    for label in labels:
        print(f"[j17-hstar] loading {label} ...", flush=True)
        rows, entries = j17d.load_depth_rows(sources[label])
        raw[label] = rows
        depth[label] = j17d.drop_crashed(rows)
        for e in entries:
            dirs[e["campaign_dir"]] = dict(e, label=label)
        if label != "ceiling":
            controls[label] = load_controls(sources[label])
    print("[j17-hstar] validation ...", flush=True)
    validation, cache = validate(raw, controls, sources)
    depth_h = {"ceiling": depth["ceiling"]}
    counts: dict[str, dict[str, Any]] = {rx: {} for rx in RECEIVERS}
    for rx in RECEIVERS:
        for m in DEPTHS:
            label = f"{rx}_m{m}"
            depth_h[label] = with_hstar(depth[label], controls[label])
            counts[rx][f"m{m}"] = hc.control_counts(controls[label], keys=depth[label].keys())
    blocks = hstar_blocks(depth_h, n_boot, seed)
    rescued: dict[str, Any] = {}
    label_m = {rx: f"{rx}_m{RESCUE_DEPTH}" for rx in RECEIVERS}
    for rx, label in label_m.items():
        facts = {}
        for k in depth[label]:
            src = _source_for(sources[label], k[1])
            facts[k] = dict(cache.get((str(src["packet_source"]), k[0], int(k[1]), RESCUE_DEPTH)) or {})
            c = controls[label].get(k) or {}
            if c.get(hc.HSTAR_NAME) is True and c.get(hc.HFLAG_NAME) is not True:
                facts[k].update(source_tail(Path(src["packet_source"]), k[0], int(k[1]),
                                            facts[k].get("last_obs_step", 0)))
        rescued[rx] = rescued_block(depth[label], controls[label], depth["ceiling"], facts, n_boot, seed)
    report: dict[str, Any] = {
        "protocol": PROTOCOL,
        "generated_by": "scripts/analysis/j17_hstar.py",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "split": "dev",
        "purpose": ("HO-01..HO-09 and HO-NI-01..03 recomputed with h* (the executor took control after the "
                    "replayed prefix) in place of handoff_occurred, on the pooled cap-81 prefix family "
                    "(seeds 1-3), with the validation of h* and the rescued episodes at m = 11."),
        "definition": {"h_star": hc.DEFINITION, "h_flag": hc.FLAG_DEFINITION,
                       "module": "scripts/analysis/handoff_control.py",
                       "why": ("handoff_occurred = effective_m < n_source_actions (prefix_source.py:184) counts "
                               "only executed CODE/COMPLETE actions; the loop skips its live phase only when the "
                               "replayed prefix is terminal (loop.py:743-756, prefix_is_terminal :172-180), so a "
                               "source that made at most m executed actions and did not end with done/COMPLETE "
                               "gives a false flag while the executor takes control")},
        "conventions": {
            "population": "error_type == 'crash' excluded from every pair (counted in inputs); 'limit' scored",
            "pairing": "(task_id, seed); both rows j10-clean (j16_robustness.paired_diffs)",
            "handoff_indicator": ("h = h* of the prefix (target) arm; h* undefined counts as h = 0 and is counted. "
                                  "Key names inherited from j17_depth_fixes that say handoff_occurred / handoff "
                                  "flag refer to h* here"),
            "handoff_only_estimand": "sum(d*h) / sum(h), whole clusters resampled",
            "clusterings": "scenario (19) primary, task (57) secondary; percentile int(0.025 B), int(0.975 B)",
            "p_two_sided": "as j17_depth_fixes (j10_report.bootstrap_pvalue; sign-flip beside it)",
            "ni_margin_pp": j17d.NI_MARGIN_PP,
            "units": "*_pp in percentage points; means, ratios and shares in native units",
        },
        "validation": validation,
        "handoff_control_counts": counts,
        **blocks,
        "rescued_m11": rescued,
        "changes_vs_flag": changes_vs_flag(j16.round_floats(blocks), flag_report),
        "flag_report": flag_report_path,
        "inputs": {"campaign_dirs": dirs, "n_campaign_dirs": len(dirs),
                   "n_episodes_total": sum(e["n_episodes"] for e in dirs.values()),
                   "n_crash_total": sum(e["n_crash"] for e in dirs.values())},
        "settings": {"n_boot": int(n_boot), "seed": int(seed), "results_root": str(results_root)},
    }
    # Counts only, computed after every existing block so nothing above can depend on it.
    report["cap25_counts"] = cap25_counts(results_root)
    return j16.round_floats(report)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--n-boot", type=int, default=N_BOOT)
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--results-root", type=Path, default=RESULTS_DIR)
    p.add_argument("--flag-report", type=Path, default=FLAG_REPORT,
                   help="the committed flag-based j17_depth_fixes report the HO rows cite")
    return p.parse_args(argv)


def _refused(reason: str) -> int:
    print(json.dumps({"protocol": PROTOCOL, "status": "REFUSED", "reason": reason}))
    return 2


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    sources = j17d.family_sources(args.results_root)
    named = [args.out, args.results_root, args.flag_report]
    named += [p for label in ("ceiling",) + PREFIX_LABELS for s in sources[label] for p in (s["root"], s["packet_source"])]
    named += [p for s in cap25_sources(args.results_root).values() for p in (s["root"], s["packet_source"])]
    for path in named:
        if path is not None and (reason := refuse_path(path)):
            return _refused(reason)
    if reason := _refuse_out(args.out):
        return _refused(reason)
    flag = None
    if args.flag_report is not None and Path(args.flag_report).is_file():
        flag = json.loads(Path(args.flag_report).read_text(encoding="utf-8"))
    try:
        rel = str(Path(args.flag_report).resolve().relative_to(REPO))
    except (ValueError, OSError):
        rel = str(args.flag_report)
    try:
        report = build_report(args.results_root, args.n_boot, args.seed, flag, rel if flag is not None else None)
    except RefusedPath as exc:
        return _refused(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    ok = bool(report["validation"]["all_hold"])
    print(json.dumps({"protocol": PROTOCOL, "json": str(args.out), "validation_all_hold": ok,
                      "counts": {rx: {m: {k: v for k, v in c.items() if k.startswith("n_")}
                                      for m, c in report["handoff_control_counts"][rx].items()}
                                 for rx in RECEIVERS},
                      "cap25_counts": {label: {k: a[k] for k in ("n_h_flag_true", "n_live_but_unflagged", "n_terminal",
                                                                  "n_executor_never_acted")}
                                       for label, a in report["cap25_counts"]["arms"].items()},
                      "cap25_all_hstar_equal_not_source_terminal":
                          report["cap25_counts"]["all_hstar_equal_not_source_terminal"]}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
