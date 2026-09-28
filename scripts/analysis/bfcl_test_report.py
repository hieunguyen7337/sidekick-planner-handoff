#!/usr/bin/env python3
"""BFCL test read: the one registered read of docs/prereg_bfcl_test_20260925.md (the E-prereg, FROZEN 8802a95).

Cited below as E:n (line n of the E-prereg); "seams" are the S1-S8 contract shared with the wrapper's test path
(scripts/pbs/bfcl_arm.pbs).

What it reads (S1, S4). Exactly the 13 registered campaigns ``bfcl_<stem>_test_20260925`` under ``--results-root``,
each laid out ``<cid>/<system>/<seed>/<entry id>/{result.json, events.jsonl, manifest.json}`` (the layout
``bfcl_dev_report.load_arm`` globs, scripts/analysis/bfcl_dev_report.py:284). Smoke trees (``<cid>_smoke_<job>``),
dry runs, dev, qzs, test_normal and test_challenge campaigns are never opened: only the 13 exact directory names are.
Seeds are exactly {1, 2}; the entries are exactly the 150 ids of the split file's ``test`` list (E:26, E:31), so each
arm has 300 (entry, seed) pairs.

Guards (G1-G9) run before anything is computed or written; any failure exits 2 and writes nothing:
G1 the prereg is committed, unmodified and FROZEN; G2 ``--confirm E_FROZEN``; G3 the out path is outside the results
root and, one read only (E:309-310), no prior read exists (the --out file, the registered default report, or a line
of the read ledger ``campaign/results/bfcl_test_20260925.reads.jsonl`` in --repo-root) unless ``--disclosed-rerun``;
G4 the split (150 test ids, dev and test disjoint); G5 the campaigns and their keys, and ``--cannot-complete`` naming
exactly the incomplete arms a report would treat as final (E:303-307); G6 the episode manifests (split, stamps, codex
pin, config identity); G7 the derived test configs (S2, S7), and all 13 campaign directories on a read (L14); G8 no
non-crash episode without goal_pass_rate (L2); G9 the packet-replay arms' plan events against the planless set (S7,
L4).

Abort (E:303-307). planner_alone_cap81, takeover_k5 or advise_k5_fullctx below 300 pairs: the test is reported as not
run, with per-arm completeness tallies only. advise_k5_neutral incomplete: CF1 and CF3 are not run. A contrast on an
incomplete arm is not read; an unread D member counts p = 1 in Holm, which stays at m = 4. More than 15 planless keys:
no replaying-arm contrast is read.

Inference (E:195-221, S8). Pairs are (entry, seed); the cluster is the entry id (never hj1_gate.scenario_of, E:200-202)
and the design has 150 clusters. j10_report.cluster_bootstrap_means (:2001) at 10,000 resamples, seed 20260925; 95 %
percentile intervals; bootstrap_pvalue (:2038); holm_adjust (:2061) within H = {P6}, N = {P3}, CF = {CF1},
D = {D1..D4} through a1_decide_family (:2788), once per family. The boundary rule recomputes EVERY member of a fired
row's family at the seven seeds and re-runs Holm (lesson L1); the 200,000-resample run is reported, not voted.

Every contrast, companion, sensitivity and BY input takes its pairs from ONE function, ``pair_view``: it intersects the
two arms' keys, removes the union of their divergent keys (S6: a replay-divergence crash that the wrapper's refill log
records as purged at least once), applies the cap of 15 (over it the row is incomplete and draws no reading), and
reports n_pairs, n_divergent_excluded and the excluded keys. No statistic reads an arm's episodes directly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

for _thread_env in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_thread_env] = "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(REPO_ROOT), str(REPO_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import yaml  # noqa: E402

from scripts.analysis import bfcl_dev_report as dr  # noqa: E402
from scripts.analysis import handoff_control as hc  # noqa: E402
from scripts.analysis import replay_divergence as rd  # noqa: E402
from scripts.analysis.j10_report import (  # noqa: E402
    A1_R2_FENCED_BLOCK,
    A1_R2_PYTHON_BLOCK,
    A1_RULES,
    _a1_r2_next_executor_action,
    a1_decide_family,
    a1_r2_answered_asks_last_attempt,
    am1_by_fdr,
    bootstrap_pvalue,
    cluster_bootstrap_means,
    percentile_ci,
)

Key = tuple[str, int]  # (entry id, seed)

# ---- registered constants (E-prereg; seams S1-S8) ------------------------------------------------
PREREG_REL = "docs/prereg_bfcl_test_20260925.md"
CONFIRM_TOKEN = "E_FROZEN"  # E:313-314
STATUS_LINE_RE = re.compile(r"^\*\*Status\*\*")
FROZEN_RE = re.compile(r"^\*\*Status\*\*:\s*(\*\*)?\s*FROZEN")  # scripts/pbs/j10_arm.pbs:244
DEFAULT_RESULTS = Path("/scratch/n12194778/sidekick/results")
DEFAULT_CONFIG_DIR = Path("/scratch/n12194778/sidekick/logs/bfcl_test_configs")  # S2
DEFAULT_REFILL_DIR = Path("/scratch/n12194778/sidekick/logs/bfcl_refills")  # S3
DEFAULT_SPLIT = REPO_ROOT / "data" / "bfcl_split_20260924.json"
DEFAULT_OUT_REL = "campaign/results/bfcl_test_20260925.report.json"
DEFAULT_OUT = REPO_ROOT / DEFAULT_OUT_REL
READ_LEDGER_REL = "campaign/results/bfcl_test_20260925.reads.jsonl"  # every read, appended before the report
DEV_REPORT_REL = "campaign/results/bfcl_dev_20260924.report.json"

CAMPAIGN_SUFFIX = "_test_20260925"  # E:40
CEILING = "planner_alone_cap81"
TEST_CEILING_CID = "bfcl_planner_alone_cap81_test_20260925"  # S1: the only plan and prefix source (E:44)
DEV_CEILING_CID = "bfcl_planner_alone_cap81_dev_20260924"
DEV_MARKER = "_dev_20260924"
ARMS = (  # S1, E:42-53
    "planner_alone_cap81", "takeover_k5", "advise_k5_fullctx", "advise_k5_neutral", "plan_zs",
    "executor_alone_zs", "executor_alone_bplus",
    "prefix_zs_m2", "prefix_zs_m4", "prefix_zs_m6",
    "prefix_bplus_m2", "prefix_bplus_m4", "prefix_bplus_m6",
)
PACKET_REPLAY_ARMS = ("takeover_k5", "advise_k5_fullctx", "advise_k5_neutral", "plan_zs")
PREFIX_ARMS = ("prefix_zs_m2", "prefix_zs_m4", "prefix_zs_m6", "prefix_bplus_m2", "prefix_bplus_m4", "prefix_bplus_m6")
REPLAYING_ARMS = PACKET_REPLAY_ARMS + PREFIX_ARMS
CHANNEL_ARMS = ("takeover_k5", "advise_k5_fullctx", "advise_k5_neutral")
ABORT_ARMS = ("planner_alone_cap81", "takeover_k5", "advise_k5_fullctx")  # E:303-304
CF_ARM = "advise_k5_neutral"  # E:304-305
FORBIDDEN_CAMPAIGN_MARKERS = ("_smoke_", "_dryrun", "_dev_", "qzs", "test_normal", "test_challenge")
SEEDS = (1, 2)
N_TEST_ENTRIES = 150
N_BOOT = 10_000
SEED = 20260925
POOL_SEEDS = (20260925, 1, 2, 3, 7, 101, 999)  # S8; the seven vote
BIG_N = 200_000  # reported, not voted
BIG_SEED = 20260925
SIGNFLIP_PATTERNS = 100_000  # cluster_inference.REGISTERED_MC_PATTERNS, used when 2^G > 2^20
ALPHA = 0.05
BOUNDARY_WINDOW_PP = 1.00
NI_MARGIN_PP = -7.00
DIVERGENCE_CAP = 15  # E:297 (not replay_divergence.DIVERGENCE_CAP = 16)
PLANLESS_CAP = 15  # E:286
ASK_FLAG_PP = 1.00
CODEX_CLI_PIN = "0.153.4"
MODEL_PIN = "gpt-5.6-luna"
HOSTED_CEILINGS = {"planner_alone_cap81": 6000, "takeover_k5": 2400, "advise_k5_fullctx": 2400,
                   "advise_k5_neutral": 2400, "plan_zs": 1200}  # S5, E:432-442
REFILL_HEADER = ("cid", "seed", "task_id", "error_type", "reason", "job_id", "utc")  # S3
DIVERGENCE_READER = ("handoff_control.last_attempt + replay_divergence.is_divergence_event (a log without run_start "
                     "is one attempt); not replay_divergence.divergent_keys, whose events_of_last_attempt returns [] "
                     "without a run_start (replay_divergence.py:66-69)")
CRASH = "crash"
LIMIT = "limit"
METRICS = ("goal_pass", "success")
BPLUS_DESC = "the AppWorld-tailored adapter, out of domain"  # E:181, E:335
P3_QUALIFIER = "non-inferiority to the medium-effort planner in this harness (E:333)"  # L13: wherever P3 is printed
VERDICT_WORDS = {"supported": "supported", "not_supported": "not supported", "reversed": "reversed",
                 "on_boundary": "on the boundary", "not_read": "not read", "not_run": "not run",
                 "holds": "holds", "fails": "fails"}

# The registered predictions (E:114-118, E:150-179). rule: j10_report.A1_RULES name (direction from there).
PRED_SPECS: dict[str, dict[str, Any]] = {
    "P6": dict(family="H", left="takeover_k5", right="advise_k5_fullctx", kind="plain",
               rule="positive_excludes_zero_with_reversal", threshold_pp=0.0, reversal="holm",
               signflip=("two-sided", 0.0), cite="E:116, E:123-125"),
    "P3": dict(family="N", left="prefix_zs_m6", right=CEILING, kind="plain",
               rule="lower_bound_above_threshold", threshold_pp=NI_MARGIN_PP, reversal=None,
               signflip=("greater", NI_MARGIN_PP / 100.0), cite="E:117, E:126, E:129-132"),
    "CF1": dict(family="CF", left="advise_k5_neutral", right="advise_k5_fullctx", kind="plain",
                rule="positive_excludes_zero_with_reversal", threshold_pp=0.0, reversal="holm",
                signflip=("two-sided", 0.0), cite="E:118, E:127, E:133"),
    "D1": dict(family="D", left="prefix_bplus_m6", right="prefix_bplus_m2", kind="plain",
               rule="lower_bound_above_threshold", threshold_pp=0.0, reversal="interval",
               signflip=("greater", 0.0), cite="E:152, E:157-161, E:176-179"),
    "D2": dict(family="D", left="prefix_zs_m6", right="prefix_zs_m2", kind="plain",
               rule="lower_bound_above_threshold", threshold_pp=0.0, reversal="interval",
               signflip=("greater", 0.0), cite="E:153, E:157-161, E:176-179"),
    "D3": dict(family="D", left="prefix_bplus_m6", right="prefix_bplus_m2", kind="hstar",
               rule="lower_bound_above_threshold", threshold_pp=0.0, reversal="interval",
               signflip=None, cite="E:154, E:157-163, E:176-179"),
    "D4": dict(family="D", left="prefix_zs_m6", right="prefix_zs_m2", kind="hstar",
               rule="lower_bound_above_threshold", threshold_pp=0.0, reversal="interval",
               signflip=None, cite="E:155, E:157-163, E:176-179"),
}
FAMILIES: dict[str, tuple[str, ...]] = {"H": ("P6",), "N": ("P3",), "CF": ("CF1",), "D": ("D1", "D2", "D3", "D4")}
PRED_ORDER = ("P6", "P3", "CF1", "D1", "D2", "D3", "D4")

# B1, P3's handoff-only companion (E:135-144); the *_flag rows use handoff_occurred.
B1_SPECS: dict[str, dict[str, Any]] = {
    "B1_zs": dict(left="prefix_zs_m6", right=CEILING, h="hstar", reading=True),
    "B1_bplus": dict(left="prefix_bplus_m6", right=CEILING, h="hstar", reading=True),
    "B1_zs_flag": dict(left="prefix_zs_m6", right=CEILING, h="flag", reading=True),
    "B1_bplus_flag": dict(left="prefix_bplus_m6", right=CEILING, h="flag", reading=True),
}
D_FLAG_SPECS = {  # E:162-163, E:325-326: not decision-bearing
    "D3_flag": dict(left="prefix_bplus_m6", right="prefix_bplus_m2", h="flag"),
    "D4_flag": dict(left="prefix_zs_m6", right="prefix_zs_m2", h="flag"),
}
SUPPORT_SPECS = {  # E:183-191: pre-specified, unadjusted, not decision-bearing
    "S3": dict(left="prefix_bplus_m6", right=CEILING, threshold_pp=NI_MARGIN_PP, note="the literal J10 P3 receiver"),
    "S4": dict(left="executor_alone_bplus", right="executor_alone_zs", threshold_pp=0.0,
               note="tailoring, out of domain"),
    "S5": dict(left="plan_zs", right="executor_alone_zs", threshold_pp=0.0, note="one plan"),
    "CF3": dict(left="takeover_k5", right="advise_k5_neutral", threshold_pp=0.0,
                note="readings as J10 Am1 §C (:795-801); never 'execution adds nothing'"),
}
M4_SPECS = {  # E:49, E:187, E:328: exploratory, printed between the D rows
    "m4_bplus_m4_minus_m2": ("prefix_bplus_m4", "prefix_bplus_m2"),
    "m4_bplus_m6_minus_m4": ("prefix_bplus_m6", "prefix_bplus_m4"),
    "m4_zs_m4_minus_m2": ("prefix_zs_m4", "prefix_zs_m2"),
    "m4_zs_m6_minus_m4": ("prefix_zs_m6", "prefix_zs_m4"),
}
BY_ROWS = (  # E:218-220: 13 rows, each counted once, two-sided p at its threshold
    ("P6", 0.0), ("P3", NI_MARGIN_PP), ("CF1", 0.0), ("B1_zs", NI_MARGIN_PP), ("B1_bplus", NI_MARGIN_PP),
    ("D1", 0.0), ("D2", 0.0), ("D3", 0.0), ("D4", 0.0), ("S3", NI_MARGIN_PP), ("S4", 0.0), ("S5", 0.0),
    ("CF3", 0.0),
)
BY_FLAGGABLE = frozenset({"P6", "P3", "CF1", "D1", "D2", "D3", "D4", "B1_zs", "B1_bplus"})
LIMIT_SPLIT_ROWS = ("P6", "CF1", "CF3")  # E:321-322
CLASS_SET_ROWS = ("P6", "P3", "CF1", "D1", "D2", "D3", "D4")  # E:203-204

# dev_reference (L6): the frozen prereg's values in the registered orientation, never negated.
DEV_META = {"n_pairs": 150, "n_clusters": 50, "seeds": [1, 2, 3], "n_boot": 10_000, "seed": 20260925,
            "exploratory": True, "source": "dev report " + DEV_REPORT_REL + " (E:120-121)"}
DEV_REFERENCE: dict[str, dict[str, Any]] = {
    "P6": {"diff_pp": 11.12, "ci95_entry": [4.16, 18.22], "sd_pp": 38.055, "p_two_sided": 0.0026,
           "dev_report_key": "contrasts.P6.goal_pass", "prereg_line": "E:116"},
    "P3": {"diff_pp": -6.58, "ci95_entry": [-10.99, -2.46], "sd_pp": 19.646, "p_ni": 0.802,
           "lower_above_margin": False, "dev_report_key": "contrasts.P3_zs_m6.goal_pass", "prereg_line": "E:117"},
    "CF1": {"diff_pp": 4.38, "ci95_entry": [-0.29, 9.42], "sd_pp": 30.419, "p_two_sided": 0.0658,
            "dev_report_key": "contrasts.CF1.goal_pass", "prereg_line": "E:118"},
    "B1_zs": {"diff_pp": -7.71, "ci95_entry": [-12.68, -2.90], "n_handoff": 128, "lower_above_margin": False,
              "dev_report_key": "contrasts.B1_zs_m6_hstar.goal_pass", "prereg_line": "E:142"},
    "B1_bplus": {"diff_pp": -11.46, "ci95_entry": [-18.40, -5.04], "n_handoff": 128, "lower_above_margin": False,
                 "dev_report_key": "contrasts.B1_bplus_m6_hstar.goal_pass", "prereg_line": "E:143"},
    "D1": {"diff_pp": 12.38, "ci95_entry": [7.16, 17.73], "sd_pp": 36.365,
           "dev_report_key": "contrasts.depth_bplus.goal_pass", "prereg_line": "E:152"},
    "D2": {"diff_pp": 2.53, "ci95_entry": [-3.88, 8.48], "sd_pp": 30.12,
           "dev_report_key": "contrasts.depth_zs.goal_pass", "prereg_line": "E:153"},
    "D3": {"diff_pp": 14.24, "ci95_entry": [8.41, 20.22], "sd_pp": 35.45, "n_handoff": 128,
           "dev_report_key": "contrasts.depth_bplus_hstar.goal_pass", "prereg_line": "E:154"},
    "D4": {"diff_pp": 4.14, "ci95_entry": [-2.54, 10.65], "sd_pp": 30.923, "n_handoff": 128,
           "dev_report_key": "contrasts.depth_zs_hstar.goal_pass", "prereg_line": "E:155"},
}
DEV_REPORT_ONLY: dict[str, dict[str, Any]] = {  # not quoted in the prereg
    "S3": {"diff_pp": -9.78, "ci95_entry": [-15.88, -4.21], "sd_pp": 25.849,
           "dev_report_key": "contrasts.P3_bplus_m6.goal_pass"},
    "S4": {"diff_pp": -29.82, "ci95_entry": [-40.17, -20.13], "sd_pp": 47.793,
           "dev_report_key": "contrasts.tailor_bplus_zs.goal_pass"},
    "S5": {"diff_pp": 12.14, "ci95_entry": [2.79, 21.97], "sd_pp": 44.642,
           "dev_report_key": "contrasts.plan_zs.goal_pass"},
    "CF3": {"diff_pp": 6.74, "ci95_entry": [0.79, 12.67], "sd_pp": 35.153,
            "dev_report_key": "contrasts.CF3.goal_pass"},
}

DEFINITIONS = {
    "pair": "(entry id, seed); 150 entries x seeds {1, 2} = 300 pairs per arm (E:195)",
    "cluster": "entry id; both seeds of an entry are resampled together; never hj1_gate.scenario_of (E:196-202)",
    "complete_arm": ("all 300 keys present and every crash is a divergent key (S6): non-crashed + divergent = 300 "
                     "(E:291, J10 Am5 §B)"),
    "divergent_key": ("a key of a replaying arm whose result.json has error_type 'crash' and whose last attempt "
                      "holds an error event with payload.reason 'replay_divergence' (S6), the last attempt read by "
                      "handoff_control.last_attempt (from the last run_start on, EVERY event when there is none: "
                      "the runner's broken-replay path writes one system error event and no run_start), AND listed "
                      "in that campaign's refill log <refill-dir>/<cid>.tsv (S3, S6); a divergent-reason crash not "
                      "yet in the refill log is an ordinary crash"),
    "pair_view": ("the one pairing path: both arms' non-crashed keys intersected, the union of both arms' "
                  "divergent keys removed, cap 15 (over it: incomplete, no reading, not in BY)"),
    "estimand": "mean of left - right over the pairs, pp; D3, D4 and B1: sum(d*h*)/sum(h*), h* from the LEFT arm",
    "hstar": hc.DEFINITION + "; a missing h* counts as 0 and is counted (n_h_missing)",
    "h_flag": hc.FLAG_DEFINITION,
    "sd_pp": "sample SD (n-1) of the per-pair differences, pp (ratio rows: over the handoff pairs)",
    "limit_rate": "share of the arm's non-crash episodes with error_type == 'limit' (force-quit is not counted)",
    "force_quit_count": ("episodes whose final evaluate event payload.report.force_quit is true "
                         "(src/sidekick/environments/bfcl_env.py:585; E:429-431); reported only"),
    "calls_live": ("result.json totals.planner_calls_total minus the charged calls of the episode's own planner "
                   "events with usage.provider == 'cache' in the last attempt (bfcl_dev_report.cache_plan_calls)"),
    "calls_attributed": "result.json n_planner_calls (J10 Am4 attributed convention)",
    "executor_asks": ("an intervention event from actor planner with payload.forced false in the last attempt "
                      "(j10_report.a1_r2_answered_asks_last_attempt :5368); bound = episodes with one or more / "
                      "300, in pp (E:300-301)"),
    "planless_key": ("sidekick.agents.planner.planless_source_keys on the test ceiling (planner.py:778-804), "
                     "restricted to the 300 test keys; computed only when the ceiling holds 300 non-crashed results"),
    "live_plan_event": ("a planner event at step 0 of the last attempt with event_type 'plan' or 'error' and "
                        "usage.provider not 'cache' (loop.py:715-748)"),
}


class GuardError(Exception):
    """A registered-read guard refused: exit 2, nothing written."""

    def __init__(self, guard: str, message: str) -> None:
        super().__init__(message)
        self.guard = guard


# ---- small helpers --------------------------------------------------------------------------------
def campaign_of(stem: str) -> str:
    return f"bfcl_{stem}{CAMPAIGN_SUFFIX}"


def key_label(key: Key) -> str:
    return rd.key_label(key)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> Optional[str]:
    try:
        return sha256_bytes(Path(path).read_bytes())
    except OSError:
        return None


def git_blob_sha(data: bytes) -> str:
    """`git hash-object` of a file's bytes, without a subprocess."""
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def _git(args: list[str], cwd: Path) -> tuple[Optional[int], str]:
    try:
        res = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    return res.returncode, (res.stdout or "").strip()


def _is_under(path: Path, root: Path) -> bool:
    path, root = Path(os.path.realpath(path)), Path(os.path.realpath(root))
    return path == root or root in path.parents


def _same_path(a: Any, b: Path) -> bool:
    return isinstance(a, str) and bool(a) and os.path.realpath(a) == os.path.realpath(str(b))


def _pp_s(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:+.2f}"


def _ci_s(ci: Any) -> str:
    return "n/a" if not ci or ci[0] is None else f"[{ci[0]:+.2f}, {ci[1]:+.2f}]"


def _p_s(p: Any) -> str:
    return "n/a" if p is None else f"{float(p):.4f}"


def md_path(out: Path) -> Path:
    name = out.name[:-len(".json")] if out.name.endswith(".json") else out.name
    return out.with_name(name + ".md")


# ---- G1-G3 (main-level guards) ----------------------------------------------------------------------
def guard_prereg(repo_root: Path) -> dict[str, Any]:
    """G1: exactly one Status line, beginning with FROZEN (j10_arm.pbs:244), no DRAFT; tracked, unmodified vs HEAD."""
    path = Path(repo_root) / PREREG_REL
    if not path.is_file():
        raise GuardError("G1", f"prereg not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    status = [ln for ln in lines if STATUS_LINE_RE.match(ln)]
    if len(status) != 1:
        raise GuardError("G1", f"expected exactly one **Status** line in {path}, found {len(status)}")
    line = status[0]
    if not FROZEN_RE.match(line):
        raise GuardError("G1", "the E-prereg is not FROZEN: the **Status** value must begin with FROZEN")
    if "draft" in line.lower():
        raise GuardError("G1", "the E-prereg's Status line mentions DRAFT")
    rc, out = _git(["ls-files", "--error-unmatch", PREREG_REL], repo_root)
    if rc != 0:
        raise GuardError("G1", f"{PREREG_REL} is not tracked in {repo_root} (FROZEN means committed): {out}")
    rc, out = _git(["diff", "--quiet", "HEAD", "--", PREREG_REL], repo_root)
    if rc != 0:
        raise GuardError("G1", f"{PREREG_REL} differs from HEAD in {repo_root}; the frozen text is the committed text")
    _rc, commit = _git(["log", "-1", "--format=%H", "--", PREREG_REL], repo_root)
    _rc, head = _git(["rev-parse", "HEAD"], repo_root)
    return {"path": str(path), "sha256": sha256_file(path), "commit": commit or None, "repo_head": head or None,
            "status_line": line, "check": "one Status line, FROZEN regex of scripts/pbs/j10_arm.pbs:244, no DRAFT, "
                                          "git ls-files --error-unmatch, git diff --quiet HEAD"}


def guard_confirm(confirm: Optional[str]) -> None:
    """G2."""
    if confirm != CONFIRM_TOKEN:
        raise GuardError("G2", f"the registered read needs --confirm {CONFIRM_TOKEN} (E:313-314)")


def read_ledger(repo_root: Path) -> list[dict[str, Any]]:
    """Every read this script has written from ``repo_root`` (one JSON object per line; unreadable lines count)."""
    path = Path(repo_root) / READ_LEDGER_REL
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            row = {"unreadable_line": line[:200]}
        out.append(row if isinstance(row, dict) else {"unreadable_line": line[:200]})
    return out


def guard_out(out: Path, results_root: Path, disclosed: Optional[str],
              repo_root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    """G3: out not under the results root; one read (E:309-310) unless a disclosed re-run. A prior read is the
    --out file, the registered default report in ``repo_root``, or any line of the read ledger there (so a second
    read to another --out path is refused too)."""
    for p in (out, md_path(out)):
        if _is_under(p, results_root):
            raise GuardError("G3", f"--out {p} is under the results root {results_root}")
    if disclosed is not None and not disclosed.strip():
        raise GuardError("G3", "--disclosed-rerun needs a non-empty reason")
    candidates = [out, md_path(out)]
    ledger: list[dict[str, Any]] = []
    if repo_root is not None:
        default = Path(repo_root) / DEFAULT_OUT_REL
        candidates += [default, md_path(default)]
        ledger = read_ledger(repo_root)
    existing = list(dict.fromkeys(str(p) for p in candidates if p.exists()))
    if ledger:
        existing.append(f"{len(ledger)} prior read(s) in {Path(repo_root) / READ_LEDGER_REL} (last: "
                        f"{ledger[-1].get('out')})")
    if existing and disclosed is None:
        raise GuardError("G3", f"one read only (E:309-310): {', '.join(existing)} exists; a post-read "
                               "fix is a disclosed re-run (--disclosed-rerun \"<reason>\"), reported with both sets")
    if disclosed is None:
        return None
    prior_path = out
    if not out.exists():
        for cand in [Path(str(r.get("out"))) for r in reversed(ledger) if r.get("out")] + \
                    ([Path(repo_root) / DEFAULT_OUT_REL] if repo_root is not None else []):
            if cand.exists():
                prior_path = cand
                break
    prior: dict[str, Any] = {"reason": disclosed.strip(), "prior_report": str(prior_path),
                             "prior_report_exists": prior_path.exists(),
                             "prior_sha256": sha256_file(prior_path) if prior_path.exists() else None,
                             "prior_md_sha256": sha256_file(md_path(prior_path)) if md_path(prior_path).exists()
                             else None, "prior_predictions": None, "prior_status": None, "prior_reads": ledger,
                             "rule": "E:309-310: a post-read fix is a disclosed re-run, reported with both sets"}
    out = prior_path
    if out.exists():
        data = dr._read_json(out)
        if isinstance(data, dict):
            prior["prior_predictions"] = data.get("predictions")
            prior["prior_status"] = (data.get("meta") or {}).get("status")
            prior["prior_sentences"] = data.get("sentences")
        else:
            prior["prior_unreadable"] = True
    return prior


# ---- G4 split -------------------------------------------------------------------------------------
def load_split(split_file: Path, n_test_entries: int) -> dict[str, Any]:
    data = dr._read_json(Path(split_file))
    if not isinstance(data, dict):
        raise GuardError("G4", f"split file unreadable: {split_file}")
    test, dev = data.get("test"), data.get("dev")
    if not isinstance(test, list) or not isinstance(dev, list):
        raise GuardError("G4", f"split file lacks a test or dev list: {split_file}")
    test = [str(t) for t in test]
    dev = [str(t) for t in dev]
    if len(test) != n_test_entries or len(set(test)) != len(test):
        raise GuardError("G4", f"the test list must hold {n_test_entries} distinct ids; it holds {len(test)} "
                               f"({len(set(test))} distinct) (E:26)")
    if data.get("n_test") is not None and int(data["n_test"]) != len(test):
        raise GuardError("G4", f"split n_test {data['n_test']} != len(test) {len(test)}")
    overlap = sorted(set(dev) & set(test))
    if overlap:
        raise GuardError("G4", f"dev and test overlap on {len(overlap)} ids, e.g. {overlap[:3]} (L3)")
    return {"path": str(split_file), "sha256": sha256_file(Path(split_file)), "test": test, "n_test": len(test),
            "n_dev": len(dev), "dev_test_overlap": 0}


# ---- episodes -------------------------------------------------------------------------------------
def _usage(ev: dict[str, Any]) -> dict[str, Any]:
    u = ev.get("usage")
    return u if isinstance(u, dict) else {}


def _payload(ev: dict[str, Any]) -> dict[str, Any]:
    p = ev.get("payload")
    return p if isinstance(p, dict) else {}


def final_evaluate(events: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Payload of the last attempt's final environment evaluate event (not an in-loop horizon='local' one,
    loop.py:806-812 vs :1218-1224)."""
    out = None
    for ev in hc.last_attempt(events):
        if ev.get("actor") == "environment" and ev.get("event_type") == "evaluate":
            payload = _payload(ev)
            if payload.get("horizon") == "local":
                continue
            out = payload
    return out


def episode_row(result: dict[str, Any], result_path: Path) -> dict[str, Any]:
    """One episode. The fields bfcl_dev_report.episode_row reads (:246-263), by the same helpers, plus what the test
    read needs from the same events: force-quit, per-turn validity, plan events, asks."""
    ep_dir = result_path.parent
    events_path = ep_dir / "events.jsonl"
    has_events = events_path.is_file()
    events = hc.read_events(events_path) if has_events else []
    last = hc.last_attempt(events)
    n_cached, cache_calls = dr.cache_plan_calls(events)
    totals = result.get("totals") if isinstance(result.get("totals"), dict) else {}
    succ = result.get("success")
    success = float(bool(succ)) if isinstance(succ, bool) else dr._num(result.get("tgc"))
    error_type = result.get("error_type")
    ev_final = final_evaluate(events)
    report = ev_final.get("report") if isinstance(ev_final, dict) and isinstance(ev_final.get("report"), dict) else None
    fq = report.get("force_quit") if report is not None else None
    turn_valid = report.get("turn_valid") if report is not None and isinstance(report.get("turn_valid"), list) else None
    n_plan_cache = n_plan_live = 0
    has_plan_packet = False
    cached_from: list[str] = []
    for ev in last:
        if ev.get("actor") != "planner":
            continue
        etype, usage = ev.get("event_type"), _usage(ev)
        if etype == "plan" and isinstance(_payload(ev).get("packet"), dict):
            has_plan_packet = True
        if etype == "plan" and usage.get("provider") == "cache":
            n_plan_cache += 1
            raw = usage.get("raw") if isinstance(usage.get("raw"), dict) else {}
            if raw.get("cached_from"):
                cached_from.append(str(raw["cached_from"]))
        elif etype in ("plan", "error") and ev.get("step") == 0 and usage and usage.get("provider") != "cache":
            n_plan_live += 1
    return {
        "error_type": error_type,
        "crash": error_type == CRASH,
        "goal_pass": dr._num(result.get("goal_pass_rate")),
        "success": success,
        "n_planner_calls": dr._int(result.get("n_planner_calls")),
        "ledger_calls": dr._int(totals.get("planner_calls_total")),
        "n_cached_plan_events": n_cached,
        "cache_calls": cache_calls,
        "h_flag": hc.last_report_flag(events),
        "steps": dr._int(result.get("steps")),
        "planner_tokens": dr._num(totals.get("planner_tokens_total")),
        "executor_tokens": dr._num(totals.get("executor_tokens_total")),
        "usd": dr._num(totals.get("usd_total")),
        "has_events": has_events,
        "force_quit": None if fq is None else bool(fq),
        "turn_valid": turn_valid,
        "n_plan_cache": n_plan_cache,
        "n_plan_live": n_plan_live,
        "has_plan_packet": has_plan_packet,
        "cached_from": cached_from,
        "asks": a1_r2_answered_asks_last_attempt(events_path) if has_events else None,
        "events_path": str(events_path),
        # S6's "last-attempt error event with payload.reason 'replay_divergence'", read with handoff_control's
        # last-attempt rule (every event when the log has no run_start). prefix_handoff._broken_result writes ONE
        # system error event and returns before run_episode (src/sidekick/systems/prefix_handoff.py:119-130,
        # :173-174), the loop is the only run_start writer (src/sidekick/systems/loop.py:703), and a refill deletes
        # the dead attempt (J10 :1108-1109): replay_divergence.events_of_last_attempt (:66-69) returns [] there.
        "divergence_reason": any(rd.is_divergence_event(ev) for ev in last),
        "has_run_start": any(ev.get("event_type") == "run_start" for ev in events),
    }


def load_arm(results_root: Path, stem: str, matrix: set[Key]) -> dict[str, Any]:
    """G5: one arm's campaign, exactly `bfcl_<stem>_test_20260925`; every key must be a test key at seed 1 or 2."""
    cid = campaign_of(stem)
    if stem not in ARMS or cid != f"bfcl_{stem}_test_20260925":
        raise GuardError("G5", f"not a registered arm: {stem!r}")
    for marker in FORBIDDEN_CAMPAIGN_MARKERS:
        if marker in cid:
            raise GuardError("G5", f"campaign id {cid!r} carries the forbidden marker {marker!r}")
    cdir = Path(results_root) / cid
    out: dict[str, Any] = {"stem": stem, "cid": cid, "dir": str(cdir), "present": cdir.is_dir(), "rows": {},
                           "manifests": {}, "result_paths": {}, "systems": []}
    if not out["present"]:
        return out
    rows: dict[Key, dict[str, Any]] = {}
    systems: set[str] = set()
    for path in sorted(cdir.rglob("result.json")):
        rel = path.relative_to(cdir).parts
        if len(rel) != 4:
            raise GuardError("G5", f"{path}: not <system>/<seed>/<entry>/result.json under {cid} (S4)")
        result = dr._read_json(path)
        if not isinstance(result, dict):
            raise GuardError("G5", f"unreadable result.json: {path}")
        if result.get("task_id") is None or result.get("seed") is None:
            raise GuardError("G5", f"result.json without task_id or seed: {path}")
        try:
            key = (str(result["task_id"]), int(result["seed"]))
        except (TypeError, ValueError):
            raise GuardError("G5", f"result.json with a malformed key: {path}") from None
        if rel[1] != str(key[1]) or rel[2] != key[0]:
            raise GuardError("G5", f"{path}: its key {key} does not match its directory")
        if key[1] not in SEEDS:
            raise GuardError("G5", f"{path}: seed {key[1]} is not one of {list(SEEDS)} (E:31)")
        if key not in matrix:
            raise GuardError("G5", f"{path}: entry {key[0]!r} is not a test id (E:26)")
        if key in rows:
            raise GuardError("G5", f"{path}: a second result.json for {key_label(key)}")
        systems.add(rel[0])
        rows[key] = episode_row(result, path)
        out["result_paths"][key] = str(path)
        out["manifests"][key] = dr._read_json(path.parent / "manifest.json")
    if len(systems) > 1:
        raise GuardError("G5", f"{cid} holds results under more than one system directory: {sorted(systems)}")
    out["rows"] = rows
    out["systems"] = sorted(systems)
    return out


# ---- refill log and divergent keys (S3, S6) -----------------------------------------------------------
def read_refill_log(refill_dir: Path, cid: str) -> dict[str, Any]:
    path = Path(refill_dir) / f"{cid}.tsv"
    out: dict[str, Any] = {"path": str(path), "exists": path.is_file(), "n_lines": 0, "n_malformed": 0,
                           "n_other_cid": 0, "header_ok": None, "keys": set()}
    if not out["exists"]:
        return out
    with path.open(encoding="utf-8", newline="") as fh:
        for i, row in enumerate(csv.reader(fh, delimiter="\t")):
            if i == 0:
                out["header_ok"] = tuple(row) == REFILL_HEADER
                if out["header_ok"]:
                    continue
            if not row or not any(c.strip() for c in row):
                continue
            out["n_lines"] += 1
            if len(row) != len(REFILL_HEADER):
                out["n_malformed"] += 1
                continue
            if row[0] != cid:
                out["n_other_cid"] += 1
                continue
            try:
                out["keys"].add((row[2], int(row[1])))
            except ValueError:
                out["n_malformed"] += 1
    return out


# ---- G7 derived configs (S2, S7) -------------------------------------------------------------------
_MISSING = object()


def _diff_leaves(a: Any, b: Any, path: tuple = ()) -> list[tuple[tuple, Any, Any]]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[tuple[tuple, Any, Any]] = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a:
                out.append((path + (k,), _MISSING, b[k]))
            elif k not in b:
                out.append((path + (k,), a[k], _MISSING))
            else:
                out.extend(_diff_leaves(a[k], b[k], path + (k,)))
        return out
    return [] if a == b else [(path, a, b)]


def _leading_comments(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        if line.startswith("#"):
            out.append(line)
        elif line.strip():
            break
    return out


def check_derived_config(stem: str, config_dir: Path, repo_root: Path, results_root: Path,
                         planless: Optional[list[Key]]) -> dict[str, Any]:
    """G7 for one arm: the derived config exists, carries no dev id, equals the committed config except the S2
    rewrites (and, on a prefix arm, the S7 planless mechanism), and its replay sources are the test ceiling."""
    cid = campaign_of(stem)
    path = Path(config_dir) / f"{cid}.yaml"
    if not path.is_file():
        raise GuardError("G7", f"derived test config absent: {path} (S2)")
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    if DEV_MARKER in text:
        raise GuardError("G7", f"{path} contains {DEV_MARKER!r} (S2 tripwire)")
    derived = yaml.safe_load(text)
    if not isinstance(derived, dict):
        raise GuardError("G7", f"{path} does not parse to a mapping")
    if derived.get("campaign_id") != cid:
        raise GuardError("G7", f"{path}: campaign_id {derived.get('campaign_id')!r} != directory name {cid!r}")
    committed_path = Path(repo_root) / "configs" / f"bfcl_{stem}.yaml"
    if not committed_path.is_file():
        raise GuardError("G7", f"committed config absent: {committed_path}")
    committed_bytes = committed_path.read_bytes()
    committed = yaml.safe_load(committed_bytes.decode("utf-8"))
    if not isinstance(committed, dict):
        raise GuardError("G7", f"{committed_path} does not parse to a mapping")
    blob = git_blob_sha(committed_bytes)
    comments = _leading_comments(text)
    if blob not in "\n".join(comments):
        raise GuardError("G7", f"{path}: its leading comments do not record the committed config's blob sha {blob} "
                               f"({committed_path}; S2)")
    ceiling_dir = Path(results_root) / TEST_CEILING_CID
    rewritten: list[str] = []
    mechanism = "committed"
    planless_labels = None if planless is None else {key_label(k) for k in planless}
    for kpath, a, b in _diff_leaves(committed, derived):
        dotted = ".".join(map(str, kpath))
        if kpath == ("campaign_id",):
            continue
        if isinstance(a, str) and Path(a).name == DEV_CEILING_CID:
            want = str(Path(a).parent / TEST_CEILING_CID)
            if b != want or not _same_path(b, ceiling_dir):
                raise GuardError("G7", f"{path}: {dotted} = {b!r}; S2 requires {want!r}, the test ceiling "
                                       f"{ceiling_dir} being read")
            rewritten.append(dotted)
            continue
        if stem in PREFIX_ARMS and kpath == ("planner", "on_missing") and b == "call_if_planless":
            mechanism = "on_missing: call_if_planless"
            continue
        if stem in PREFIX_ARMS and kpath == ("planner", "live_plan_keys") and a is _MISSING and isinstance(b, list):
            bad = [k for k in b if planless_labels is not None and str(k) not in planless_labels]
            if bad:
                raise GuardError("G7", f"{path}: planner.live_plan_keys {bad[:3]} are not planless keys (S7)")
            mechanism = f"planner.live_plan_keys ({len(b)})"
            continue
        raise GuardError("G7", f"{path}: {dotted} differs from {committed_path} ({a!r} -> "
                               f"{'<absent>' if b is _MISSING else repr(b)}); S2 allows only the rewritten keys")
    planner = derived.get("planner") if isinstance(derived.get("planner"), dict) else {}
    handoff = derived.get("handoff") if isinstance(derived.get("handoff"), dict) else {}
    sources = {k: v for k, v in (("planner.packet_source", planner.get("packet_source")),
                                 ("handoff.source_campaign", handoff.get("source_campaign"))) if v}
    if stem in REPLAYING_ARMS:
        if not sources:
            raise GuardError("G7", f"{path}: a replaying arm with no packet_source / source_campaign")
        for name, value in sources.items():
            if not _same_path(value, ceiling_dir):
                raise GuardError("G7", f"{path}: {name} = {value!r} is not the test ceiling {ceiling_dir} (L4)")
    elif sources:
        raise GuardError("G7", f"{path}: a non-replaying arm names a replay source {sources}")
    committed_on_missing = ((committed.get("planner") or {}) if isinstance(committed.get("planner"), dict)
                            else {}).get("on_missing")
    on_missing = planner.get("on_missing")
    if stem in PACKET_REPLAY_ARMS and on_missing != "call_if_planless":
        raise GuardError("G7", f"{path}: packet-replay arm on_missing {on_missing!r} != 'call_if_planless' (E:294)")
    if stem not in PREFIX_ARMS and on_missing != committed_on_missing:
        raise GuardError("G7", f"{path}: on_missing {on_missing!r} != committed {committed_on_missing!r}")
    return {
        "path": str(path), "sha256": sha256_bytes(raw), "committed_config": str(committed_path),
        "committed_blob_sha": blob, "leading_comments": comments, "rewritten_keys": rewritten,
        "on_missing": on_missing, "on_missing_committed": committed_on_missing, "planless_mechanism": mechanism,
        "live_plan_keys": planner.get("live_plan_keys"), "planner_type": str(planner.get("type") or "mock"),
        "planner_model": planner.get("model"), "reasoning_effort": planner.get("reasoning_effort"),
        "replay_sources": sources,
    }


# ---- G6 manifests (L5) -----------------------------------------------------------------------------
def check_manifests(arm: dict[str, Any], cfg: dict[str, Any], results_root: Path) -> dict[str, Any]:
    stem, cid = arm["stem"], arm["cid"]
    ceiling_dir = Path(results_root) / TEST_CEILING_CID
    derived_path = Path(cfg["path"])
    n_sha_unstamped = n_sha_checked = 0
    git_shas: Counter[str] = Counter()
    cli: Counter[str] = Counter()
    dirty: Counter[str] = Counter()
    for key in sorted(arm["rows"]):
        where = arm["result_paths"][key]
        man = arm["manifests"].get(key)

        def bad(msg: str) -> GuardError:
            return GuardError("G6", f"{cid} {key_label(key)} ({where}): {msg}")

        if not isinstance(man, dict):
            raise bad("no readable manifest.json beside result.json (L5)")
        if man.get("campaign_id") != cid:
            raise bad(f"manifest campaign_id {man.get('campaign_id')!r} != {cid!r}")
        if str(man.get("task_id")) != key[0] or man.get("seed") != key[1]:
            raise bad("manifest task_id/seed differ from result.json")
        prov = man.get("provenance")
        if not isinstance(prov, dict):
            raise bad("manifest has no provenance block (X16)")
        if prov.get("split") != "test":
            raise bad(f"provenance.split {prov.get('split')!r} != 'test'")
        if not prov.get("git_sha"):
            raise bad("provenance.git_sha unstamped")
        git_shas[str(prov["git_sha"])] += 1
        dirty[str(prov.get("git_dirty"))] += 1
        if not _same_path(prov.get("config_path"), derived_path):
            raise bad(f"provenance.config_path {prov.get('config_path')!r} is not the derived config {derived_path}")
        if prov.get("config_campaign_id") != cid:
            raise bad(f"provenance.config_campaign_id {prov.get('config_campaign_id')!r} != {cid!r}")
        stamped_sha = man.get("config_sha256", prov.get("config_sha256"))
        if stamped_sha is None:
            n_sha_unstamped += 1
        else:
            n_sha_checked += 1
            if stamped_sha != cfg["sha256"]:
                raise bad(f"config_sha256 {stamped_sha} != sha256 of {derived_path} {cfg['sha256']} (S2)")
        ptype = str(prov.get("planner_type") or "mock")
        if ptype != cfg["planner_type"]:
            raise bad(f"provenance.planner_type {ptype!r} != derived config planner.type {cfg['planner_type']!r}")
        if ptype == "codex":
            version = prov.get("planner_cli_version")
            token = str(version).split()[-1] if isinstance(version, str) and version.split() else None
            cli[str(version)] += 1
            if token != CODEX_CLI_PIN:
                raise bad(f"planner_cli_version {version!r}: last token {token!r} != {CODEX_CLI_PIN}")
            if prov.get("planner_model_requested") != MODEL_PIN:
                raise bad(f"planner_model_requested {prov.get('planner_model_requested')!r} != {MODEL_PIN}")
            if prov.get("planner_reasoning_effort") != cfg["reasoning_effort"]:
                raise bad(f"planner_reasoning_effort {prov.get('planner_reasoning_effort')!r} != the derived "
                          f"config's {cfg['reasoning_effort']!r}")
        source = prov.get("handoff_source_campaign")
        if stem in REPLAYING_ARMS:
            if not _same_path(source, ceiling_dir):
                raise bad(f"handoff_source_campaign {source!r} is not the test ceiling {ceiling_dir}")
        elif source:
            raise bad(f"a non-replaying arm stamps handoff_source_campaign {source!r}")
    return {"n_manifests": len(arm["rows"]), "git_sha": dict(sorted(git_shas.items())),
            "git_dirty": dict(sorted(dirty.items())), "planner_cli_version": dict(sorted(cli.items())),
            "n_config_sha256_checked": n_sha_checked, "n_config_sha256_unstamped": n_sha_unstamped,
            "n_distinct_git_sha": len(git_shas), "n_git_dirty_true": dirty.get("True", 0),
            "config_sha256_check": ("compared on every manifest" if n_sha_unstamped == 0 else
                                    f"not possible on {n_sha_unstamped} of {len(arm['rows'])} manifests: the runner "
                                    "stamps no config_sha256 (src/sidekick/provenance.py:86-105 stamps config_path "
                                    "and config_campaign_id only; runner.py:384-389), so brief G6's sha comparison "
                                    "cannot run where it is absent"),
            "config_identity": ("provenance.config_path == the derived config path and provenance.config_campaign_id "
                                "== cid on every manifest, plus config_sha256 where stamped; the derived file's CONTENT "
                                "at read time is checked by G7 (committed config + S2 rewrites only, its blob sha in "
                                "its leading comments). That the content that ran is the content read rests on the "
                                "wrapper's S2 tripwire (an existing derived file with different content is fatal; "
                                "derived files are never deleted), not on a stamp"),
            "git_state": ("reported, not refused: the distinct provenance.git_sha values and git_dirty counts above "
                          "(no registered rule refuses a dirty tree)"),
            "served_model": "not observable: the CLI does not report the model it served (provenance.py:134-136)"}


# ---- planless keys (S7) ------------------------------------------------------------------------------
def planless_keys(results_root: Path, ceiling: dict[str, Any], matrix: set[Key]) -> dict[str, Any]:
    """planless_source_keys on the test ceiling, only when it holds all 300 keys non-crashed (S7)."""
    rows = ceiling["rows"]
    n_noncrash = sum(1 for k in matrix if k in rows and not rows[k]["crash"])
    base = {"source": str(Path(results_root) / TEST_CEILING_CID), "cap": PLANLESS_CAP,
            "definition": DEFINITIONS["planless_key"], "n_ceiling_noncrash": n_noncrash, "n_expected": len(matrix)}
    if n_noncrash != len(matrix):
        return {**base, "status": "not_computed", "keys": None, "n": None,
                "reason": f"the ceiling holds {n_noncrash} of {len(matrix)} non-crashed results; a count from an "
                          "incomplete ceiling is never reported as 0 (S7)"}
    if ceiling["systems"] != ["planner_alone"]:
        raise GuardError("G9", f"the ceiling's system directory is {ceiling['systems']}, not ['planner_alone']: "
                               "planless_source_keys would find nothing (L14)")
    from sidekick.agents.planner import planless_source_keys  # noqa: E402 (pydantic; lazy)

    keys = []
    for label in planless_source_keys(Path(results_root) / TEST_CEILING_CID, "planner_alone", seeds=SEEDS):
        seed, _, task = label.partition("/")
        key = (task, int(seed))
        if key in matrix:
            keys.append(key)
    keys = sorted(keys)
    own = sorted(k for k in matrix if not rows[k]["has_plan_packet"])
    if own != keys:
        raise GuardError("G9", f"planless_source_keys ({len(keys)}) disagrees with the ceiling's own plan events "
                               f"({len(own)} without a plan packet): refusing rather than guessing (L14)")
    return {**base, "status": "ok", "keys": [key_label(k) for k in keys], "n": len(keys),
            "n_with_plan_event": len(matrix) - len(keys), "over_cap": len(keys) > PLANLESS_CAP, "_keys": keys}


# ---- G8, G9 -------------------------------------------------------------------------------------------
def guard_metrics(arms: dict[str, dict[str, Any]]) -> None:
    for stem, arm in arms.items():
        bad = sorted(k for k, r in arm["rows"].items() if not r["crash"] and r["goal_pass"] is None)
        if bad:
            raise GuardError("G8", f"{arm['cid']}: {len(bad)} non-crash episodes have goal_pass_rate None, e.g. "
                                   f"{[key_label(k) for k in bad[:3]]}; a pair is never dropped silently (L2)")


def guard_plan_events(arms: dict[str, dict[str, Any]], planless: Optional[list[Key]], matrix: set[Key],
                      results_root: Path) -> dict[str, Any]:
    """G9 (L4, S7): per packet-replay arm, every non-crash episode replays a cached plan from the test ceiling or,
    on a planless key only, plans live; cached + live-planned planless = 300 on a complete arm. A live plan call on
    a key that is not planless refuses on every replaying arm."""
    ceiling_dir = Path(os.path.realpath(Path(results_root) / TEST_CEILING_CID))
    pl = None if planless is None else set(planless)
    out: dict[str, Any] = {}
    for stem in REPLAYING_ARMS:
        arm = arms[stem]
        scored = {k: r for k, r in arm["rows"].items() if not r["crash"]}
        live_keys = sorted(k for k, r in scored.items() if r["n_plan_live"] > 0)
        blk: dict[str, Any] = {"n_live_plan_events": sum(r["n_plan_live"] for r in scored.values()),
                               "live_plan_keys": [key_label(k) for k in live_keys], "n_live_plan_keys": len(live_keys)}
        if pl is None:
            blk["status"] = "not_checked: planless set not computed (ceiling incomplete)"
            out[stem] = blk
            continue
        off = [k for k in live_keys if k not in pl]
        if off:
            raise GuardError("G9", f"{arm['cid']}: live plan call on keys that are not planless: "
                                   f"{[key_label(k) for k in off[:5]]} (S7)")
        if stem in PACKET_REPLAY_ARMS:
            cached = [k for k, r in scored.items() if r["n_plan_cache"] > 0]
            both = [k for k, r in scored.items() if r["n_plan_cache"] > 0 and r["n_plan_live"] > 0]
            neither = [k for k, r in scored.items() if r["n_plan_cache"] == 0 and r["n_plan_live"] == 0]
            if both:
                raise GuardError("G9", f"{arm['cid']}: both a cached and a live plan on {key_label(both[0])}")
            if neither:
                raise GuardError("G9", f"{arm['cid']}: no plan event (cached or live) on "
                                       f"{[key_label(k) for k in neither[:5]]}")
            outside, unrecorded = 0, 0
            for k, r in scored.items():
                if r["n_plan_cache"] and not r["cached_from"]:
                    unrecorded += 1
                for src in r["cached_from"]:
                    if not _is_under(Path(src), ceiling_dir):
                        outside += 1
            if outside:
                raise GuardError("G9", f"{arm['cid']}: {outside} cached plans come from outside the test ceiling "
                                       f"{ceiling_dir} (L12)")
            complete_keys = all(k in scored for k in matrix)
            if complete_keys and len(cached) + len(live_keys) != len(matrix):
                raise GuardError("G9", f"{arm['cid']}: cached {len(cached)} + live-planned {len(live_keys)} != "
                                       f"{len(matrix)}")
            blk.update(n_cached_plan_keys=len(cached), n_cached_from_outside_packet_source=outside,
                       n_cached_from_unrecorded=unrecorded,
                       sum_cached_plus_live=len(cached) + len(live_keys))
        blk["status"] = "ok"
        out[stem] = blk
    return out


# ---- per-arm completeness ------------------------------------------------------------------------------
def arm_completeness(arm: dict[str, Any], matrix: set[Key], refill_dir: Path) -> None:
    rows = arm["rows"]
    stem = arm["stem"]
    refill = read_refill_log(refill_dir, arm["cid"])
    # A divergent-reason crash: result.json error_type 'crash' and a last-attempt replay_divergence error event,
    # the last attempt read as handoff_control.last_attempt does (the whole log when it has no run_start: the
    # shape the runner's broken-replay path writes). replay_divergence.divergent_keys is NOT used: it reads a log
    # without run_start as empty (:66-69) and so can never see a real BFCL divergence (see episode_row).
    div_reason = ({k for k, r in rows.items() if r["crash"] and r["divergence_reason"]} & matrix
                  if stem in REPLAYING_ARMS else set())
    divergent = sorted(k for k in div_reason if k in refill["keys"])
    not_refilled = sorted(div_reason - set(divergent))
    no_run_start = sorted(k for k in div_reason if not rows[k]["has_run_start"])
    missing = sorted(matrix - set(rows))
    crash = sorted(k for k, r in rows.items() if r["crash"])
    ordinary = sorted(set(crash) - set(divergent))
    n_noncrash = len(rows) - len(crash)
    why = []
    if not arm["present"]:
        why.append(f"campaign directory absent: {arm['dir']}")
    if missing:
        why.append(f"{len(missing)} of {len(matrix)} keys missing")
    if ordinary:
        why.append(f"{len(ordinary)} crashed (not divergent keys)")
    arm.update(
        refill={k: v for k, v in refill.items() if k != "keys"} | {"n_keys": len(refill["keys"])},
        divergent=divergent, divergent_reason_not_refilled=not_refilled, divergent_reason_no_run_start=no_run_start,
        missing=missing, crash=crash,
        ordinary_crash=ordinary, n_noncrash=n_noncrash, n_expected=len(matrix),
        complete=not why, complete_reason="; ".join(why) if why else None,
    )


def tallies(arm: dict[str, Any]) -> dict[str, Any]:
    return {"campaign_id": arm["cid"], "present": arm["present"], "n_expected": arm["n_expected"],
            "n_noncrash": arm["n_noncrash"], "n_crash": len(arm["crash"]), "n_divergent": len(arm["divergent"]),
            "n_missing": len(arm["missing"]), "complete": arm["complete"], "complete_reason": arm["complete_reason"],
            "divergent_keys": [key_label(k) for k in arm["divergent"]],
            "n_divergent_reason_not_refilled": len(arm["divergent_reason_not_refilled"]),
            "n_divergent_reason_without_run_start": len(arm["divergent_reason_no_run_start"]),
            "divergence_reader": DIVERGENCE_READER,
            "refill_log": arm["refill"]}


def guard_cannot_complete(arms: dict[str, dict[str, Any]], below: list[str],
                          cannot_complete: Optional[Iterable[str]]) -> Any:
    """G5 (L14, E:303-307, E:309-310): an incomplete arm is read as 'cannot complete' only when the operator says so.

    The script cannot tell 'cannot complete' (E:305-307, a final judgement) from 'not finished yet' (E:305: GPU arms
    are resumed until complete), and the read happens once. So a not-run report needs ``--cannot-complete`` naming
    exactly the abort arms below 300 pairs, and a read with any incomplete arm needs it naming exactly those arms."""
    if cannot_complete is None:
        return "not enforced (build_report called directly, not through main)"
    acked = sorted({str(s).strip() for s in cannot_complete if str(s).strip()})
    unknown = [s for s in acked if s not in ARMS]
    if unknown:
        raise GuardError("G5", f"--cannot-complete names arms that are not registered: {unknown} (S1)")
    need = sorted(below) if below else sorted(s for s in ARMS if not arms[s]["complete"])
    if acked != need:
        why = "; ".join(f"{s}: {arms[s]['complete_reason']}" for s in need) or "every arm is complete"
        raise GuardError("G5", f"--cannot-complete {','.join(acked) or '<none>'} must name exactly the "
                               f"{'abort arms below 300 pairs (E:303-304)' if below else 'incomplete arms (E:305-307)'}"
                               f": {','.join(need) or '<none>'} ({why}). 'Cannot complete' is a final judgement; an "
                               "arm still running is resumed, not read (E:305), and there is one read (E:309-310)")
    return acked


# ---- the one pair view (L9, L10) -------------------------------------------------------------------------
def pair_view(ctx: dict[str, Any], left: str, right: str, field: str = "goal_pass", *,
              exclude: Iterable[Key] = (), keep: Optional[Callable[[Key, dict, dict], bool]] = None,
              variant: str = "primary") -> dict[str, Any]:
    """Every contrast's pairs. Keys: both arms' non-crashed keys of the design; the union of both arms' divergent
    keys removed (S6), cap 15; `exclude` removes further keys (the planless sensitivity) and `keep` filters pairs
    (P3's limit-excluded variant). Complete iff both arms are complete, the cap holds and the planless cap does."""
    L, R = ctx["arms"][left], ctx["arms"][right]
    div = sorted(set(L["divergent"]) | set(R["divergent"]))
    reasons = []
    for name, a in ((left, L), (right, R)):
        if not a["complete"]:
            reasons.append(f"{name} incomplete ({a['complete_reason']})")
    over = len(div) > DIVERGENCE_CAP
    if over:
        reasons.append(f"over cap: {len(div)} divergent keys > {DIVERGENCE_CAP} (E:297)")
    if ctx.get("planless_blocked") and (left in REPLAYING_ARMS or right in REPLAYING_ARMS):
        reasons.append(f"more than {PLANLESS_CAP} planless keys: no replaying arm is read (E:286)")
    excl, divset = set(exclude), set(div)
    keys: list[Key] = []
    diffs: list[float] = []
    lv: list[float] = []
    rv: list[float] = []
    le: list[Any] = []
    re_: list[Any] = []
    n_missing = n_excl = n_filtered = 0
    for k in sorted(ctx["matrix"]):
        a, b = L["rows"].get(k), R["rows"].get(k)
        if a is None or b is None or a["crash"] or b["crash"] or k in divset:
            continue
        if k in excl:
            n_excl += 1
            continue
        if keep is not None and not keep(k, a, b):
            n_filtered += 1
            continue
        va, vb = a.get(field), b.get(field)
        if va is None or vb is None:
            n_missing += 1
            continue
        keys.append(k)
        diffs.append(float(va) - float(vb))
        lv.append(float(va))
        rv.append(float(vb))
        le.append(a["error_type"])
        re_.append(b["error_type"])
    if field == "goal_pass" and n_missing:
        raise AssertionError(f"{left} - {right}: {n_missing} goal_pass pairs missing after G8")
    hst = ctx["hstar"].get(left)
    return {
        "left": left, "right": right, "field": field, "variant": variant,
        "keys": keys, "diffs": diffs, "left_values": lv, "right_values": rv,
        "left_error": le, "right_error": re_,
        "left_hstar": [hst.get(k) for k in keys] if hst is not None else None,
        "left_hflag": [L["rows"][k]["h_flag"] for k in keys],
        "n_pairs": len(keys), "n_divergent_excluded": len(div), "divergent_excluded": [key_label(k) for k in div],
        "n_excluded_keys": n_excl, "n_filtered": n_filtered, "n_metric_missing": n_missing,
        "n_removed": len(div) + n_excl + n_filtered, "over_cap": over, "complete": not reasons,
        "incomplete_reason": "; ".join(reasons) if reasons else None,
        "n_design_entries": ctx["n_entries"],
    }


def subset_view(view: dict[str, Any], idx: list[int], variant: str) -> dict[str, Any]:
    out = dict(view)
    for name in ("keys", "diffs", "left_values", "right_values", "left_error", "right_error", "left_hflag"):
        out[name] = [view[name][i] for i in idx]
    if view.get("left_hstar") is not None:
        out["left_hstar"] = [view["left_hstar"][i] for i in idx]
    out["n_pairs"] = len(idx)
    out["n_filtered"] = view["n_filtered"] + (view["n_pairs"] - len(idx))
    out["n_removed"] = view["n_removed"] + (view["n_pairs"] - len(idx))
    out["variant"] = variant
    return out


def view_frame(view: dict[str, Any]) -> dict[str, Any]:
    """What every printed row carries (L10)."""
    return {"left": view["left"], "right": view["right"], "n_pairs": view["n_pairs"],
            "n_divergent_excluded": view["n_divergent_excluded"], "divergent_excluded": view["divergent_excluded"],
            "n_metric_missing": view["n_metric_missing"], "complete": view["complete"],
            "incomplete_reason": view["incomplete_reason"]}


# ---- estimation ----------------------------------------------------------------------------------------
def _member_means(row_id: str, kind: str, diffs: list[float], hs: Optional[list[float]], labels: list[str], *,
                  n_boot: int, seed: int) -> list[float]:
    """Sorted bootstrap replicates: plain rows by j10_report.cluster_bootstrap_means; ratio rows (Σd·h/Σh) by
    bfcl_dev_report.cluster_bootstrap_stat, the same draw sequence, whole clusters resampled."""
    if kind == "plain":
        return cluster_bootstrap_means(diffs, labels, n_boot=n_boot, seed=seed)
    groups: dict[str, list[float]] = {}
    for lab, d, h in zip(labels, diffs, hs or []):
        g = groups.setdefault(lab, [0.0, 0.0])
        g[0] += d * h
        g[1] += h

    def ratio(drawn: list[str]) -> Optional[float]:
        num = den = 0.0
        for lab in drawn:
            a, b = groups[lab]
            num += a
            den += b
        return num / den if den > 0 else None

    return dr.cluster_bootstrap_stat(groups, ratio, n_boot=n_boot, seed=seed)


def _labels(keys: list[Key], clustering: str, classes: Optional[dict[str, str]]) -> list[str]:
    if clustering == "entry":
        return [k[0] for k in keys]
    if clustering == "class_set":
        return [(classes or {})[k[0]] for k in keys]
    raise ValueError(f"unknown clustering {clustering!r} (scenario clustering is never used on BFCL)")


def estimate(ctx: dict[str, Any], row_id: str, view: dict[str, Any], *, kind: str = "plain",
             h: Optional[list[Any]] = None, threshold_pp: float = 0.0, direction: str = "two-sided",
             n_boot: Optional[int] = None, seed: Optional[int] = None, clustering: str = "entry") -> dict[str, Any]:
    n_boot = ctx["n_boot"] if n_boot is None else n_boot
    seed = ctx["seed"] if seed is None else seed
    keys, diffs = view["keys"], view["diffs"]
    if not keys:
        return {"status": "no_pairs", "n_pairs": 0}
    labels = _labels(keys, clustering, ctx.get("classes"))
    n_clusters = len(set(labels))
    if clustering == "entry":
        assert n_clusters == len({k[0] for k in keys}), "cluster unit must be the entry id"
        if view["field"] == "goal_pass" and view["n_removed"] == 0 and n_clusters != view["n_design_entries"]:
            raise AssertionError(f"{row_id}: {n_clusters} entry clusters on a full view; the design has "
                                 f"{view['n_design_entries']} (E:201-202)")
    out: dict[str, Any] = {"status": "ok", "n_pairs": len(keys), "n_clusters": n_clusters, "cluster_unit": clustering}
    hs = None
    if kind == "plain":
        point = statistics.fmean(diffs)
        out["sd_pp"] = dr._sd_pp(diffs)
    else:
        if h is None:
            raise ValueError(f"{row_id}: a ratio row needs h")
        hs = [1.0 if v is True else 0.0 for v in h]
        den = sum(hs)
        out.update(n_handoff=int(den), n_h_missing=sum(1 for v in h if v is None))
        if den == 0:
            return {**out, "status": "no_handoff_pair"}
        point = sum(d * x for d, x in zip(diffs, hs)) / den
        out["sd_pp"] = dr._sd_pp([d for d, x in zip(diffs, hs) if x])
    ck = (row_id, view["variant"], view["field"], kind, clustering, n_boot, seed)
    cache = ctx.setdefault("cache", {})
    if ck not in cache:
        cache[ck] = _member_means(row_id, kind, diffs, hs, labels, n_boot=n_boot, seed=seed)
    means = cache[ck]
    if not means:
        return {**out, "status": "no_valid_replicate"}
    lo, hi = percentile_ci(means)
    t = threshold_pp / 100.0
    out.update(point=point, lo=lo, hi=hi, _means=means, diff_pp=dr._pp(point), ci95_entry=[dr._pp(lo), dr._pp(hi)],
               threshold_pp=threshold_pp, direction=direction, p_registered=round(bootstrap_pvalue(means, t, direction), 6),
               p_two_sided_at_threshold=round(bootstrap_pvalue(means, t, "two-sided"), 6),
               n_boot=n_boot, seed=seed, n_boot_valid=len(means))
    if clustering != "entry":
        out["ci95"] = out.pop("ci95_entry")
    return out


def public(est: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if est is None:
        return None
    return {k: v for k, v in est.items() if not k.startswith("_") and k not in ("point", "lo", "hi")}


def tgc_atom_note(blk: Optional[dict[str, Any]], threshold_pp: float) -> Optional[str]:
    """J10 :275-277 (a1_r2_tgc_atom :5741-5760, ported): a success bound on the threshold's nearest atom k/n is
    reported as such, not as a pass or fail by a hair."""
    if not blk or blk.get("status") != "ok" or not blk.get("n_pairs"):
        return None
    n = int(blk.get("n_handoff") or blk["n_pairs"])
    k = round(threshold_pp / 100.0 * n)
    atom_pp = round(100.0 * k / n, 2)
    ci = blk.get("ci95_entry") or [None, None]
    on = [name for name, v in (("lower", ci[0]), ("upper", ci[1])) if v is not None and round(v, 2) == atom_pp]
    if not on:
        return None
    return (f"success's {' and '.join(on)} bound sits on the threshold's nearest atom ({k}/{n} = {atom_pp:+.2f} pp): "
            "on the atom, not a pass or fail by a hair (J10 :275-277)")


# ---- families, boundary, key exclusion ------------------------------------------------------------------
def _blocked(ctx: dict[str, Any], pid_or_row: str, left: str, right: str, view: dict[str, Any]) \
        -> Optional[tuple[str, str]]:
    arms = ctx["arms"]
    if CF_ARM in (left, right) and not arms[CF_ARM]["complete"] and pid_or_row in ("CF1", "CF3"):
        return "not_run", f"advise_k5_neutral could not complete 300 pairs: CF1 and CF3 are not run (E:304-305)"
    if ctx.get("planless_blocked") and (left in REPLAYING_ARMS or right in REPLAYING_ARMS):
        return "not_run", f"more than {PLANLESS_CAP} planless keys: no replaying arm is read (E:286)"
    if not view["complete"]:
        return "not_read", view["incomplete_reason"]
    return None


def evaluate_family(ctx: dict[str, Any], fam: str, views: dict[str, dict[str, Any]], *, n_boot: int,
                    seed: int) -> dict[str, dict[str, Any]]:
    """Every member's interval and registered p at one (n_boot, seed), Holm within the family by
    j10_report.a1_decide_family (an unread member's p is 1, :2796-2807), then the rule; a D member whose upper
    bound is below 0 is reversed, read from the interval alone (E:176-179)."""
    results = []
    for pid in FAMILIES[fam]:
        spec = PRED_SPECS[pid]
        view = views[pid]
        rule = A1_RULES[spec["rule"]]
        r: dict[str, Any] = {"id": pid, "holm_family": True, "kind": spec["kind"], "rule": spec["rule"],
                             "threshold_pp": spec["threshold_pp"]}
        why = _blocked(ctx, pid, spec["left"], spec["right"], view)
        if why:
            r.update(decidable=False, verdict=why[0], reason=why[1])
        else:
            est = estimate(ctx, pid, view, kind="plain" if spec["kind"] == "plain" else "ratio",
                           h=view["left_hstar"] if spec["kind"] == "hstar" else None,
                           threshold_pp=spec["threshold_pp"], direction=rule["direction"], n_boot=n_boot, seed=seed)
            if est["status"] != "ok":
                r.update(decidable=False, verdict="not_read", reason=f"estimate: {est['status']}", _est=est)
            else:
                r.update(decidable=True, p_value=est["p_registered"], _point=est["point"], _lo=est["lo"],
                         _hi=est["hi"], _est=est)
        results.append(r)
    a1_decide_family(results, ALPHA)
    for r in results:
        if r.get("decidable"):
            v = r["verdict_holm"]
            if PRED_SPECS[r["id"]]["reversal"] == "interval" and r["_hi"] < 0:
                v = "reversed"
            r["verdict_rule"] = v
    return {r["id"]: r for r in results}


def _bounds_checked(pid: str) -> tuple[str, ...]:
    spec = PRED_SPECS[pid]
    if spec["reversal"] is not None:
        return ("lo", "hi")
    return tuple(A1_RULES[spec["rule"]]["bounds"])


def boundary_family(ctx: dict[str, Any], fam: str, views: dict[str, dict[str, Any]],
                    base: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """L1: a decision-bearing bound within 1.00 pp of its threshold (either bound, either side) recomputes EVERY
    member of its family at each of the seven seeds, Holm re-run, and re-decides; any seed whose verdict differs
    makes the row on the boundary. 200,000 resamples at 20260925 are reported, not voted."""
    out: dict[str, dict[str, Any]] = {}
    fired_any = False
    for pid in FAMILIES[fam]:
        r = base[pid]
        spec = PRED_SPECS[pid]
        blk: dict[str, Any] = {"rule": "boundary (E:213-215; J10 :300-308; Holm-aware, L1)",
                               "window_pp": BOUNDARY_WINDOW_PP, "threshold_pp": spec["threshold_pp"],
                               "seeds": list(ctx["pool_seeds"]), "n_boot": ctx["n_boot"]}
        if not r.get("decidable"):
            out[pid] = {**blk, "fired": False, "reason": "not read"}
            continue
        names = _bounds_checked(pid)
        near = {n: abs(r[f"_{n}"] * 100.0 - spec["threshold_pp"]) <= BOUNDARY_WINDOW_PP + 1e-12 for n in names}
        fired = any(near.values())
        fired_any = fired_any or fired
        out[pid] = {**blk, "bounds_checked": list(names), "within_window": near, "fired": fired}
    if not fired_any:
        for pid in out:
            out[pid].setdefault("stable", True)
        return out
    per_seed = {s: evaluate_family(ctx, fam, views, n_boot=ctx["n_boot"], seed=s) for s in ctx["pool_seeds"]}
    big = evaluate_family(ctx, fam, views, n_boot=ctx["big_n"], seed=ctx["big_seed"])
    fired_by = [q for q in FAMILIES[fam] if out[q].get("fired")]
    for pid in FAMILIES[fam]:
        if not out[pid].get("fired"):
            # E:213-215 fires on a bound within 1.00 pp; this member's bounds are not, so its verdict stands. It was
            # re-decided with its family all the same, and a seed where that differs is disclosed, not voted.
            out[pid].setdefault("stable", True)
            if base[pid].get("decidable"):
                base_v = base[pid]["verdict_rule"]
                by_seed = [(s, res[pid].get("verdict_rule", res[pid].get("verdict"))) for s, res in per_seed.items()]
                out[pid].update(
                    recomputed_with_family=True, family_fired_by=fired_by,
                    verdicts_by_seed_not_voted=[{"seed": s, "verdict": v,
                                                 "p_holm": (per_seed[s][pid].get("holm") or {}).get("p_adjusted")}
                                                for s, v in by_seed],
                    flipping_seeds_not_voted=[s for s, v in by_seed if v != base_v],
                    not_voted_rule=("E:213-215 fires on a bound within 1.00 pp of the threshold; this member's "
                                    "bounds are not, so a re-decided seed that differs is disclosed, not voted"))
            continue
        base_v = base[pid]["verdict_rule"]
        rows = []
        for s, res in per_seed.items():
            m = res[pid]
            rows.append({"seed": s, "lo_pp": dr._pp(m.get("_lo")), "hi_pp": dr._pp(m.get("_hi")),
                         "p": m.get("p_value"), "p_holm": (m.get("holm") or {}).get("p_adjusted"),
                         "verdict": m.get("verdict_rule", m.get("verdict")),
                         "family_p_holm": {q: (res[q].get("holm") or {}).get("p_adjusted") for q in FAMILIES[fam]}})
        b = big[pid]
        out[pid].update(
            bounds_by_seed=rows, verdicts_by_seed=sorted({row["verdict"] for row in rows}),
            stable=all(row["verdict"] == base_v for row in rows),
            flipping_seeds=[row["seed"] for row in rows if row["verdict"] != base_v],
            bound_200k={"n_boot": ctx["big_n"], "seed": ctx["big_seed"], "lo_pp": dr._pp(b.get("_lo")),
                        "hi_pp": dr._pp(b.get("_hi")), "p": b.get("p_value"),
                        "p_holm": (b.get("holm") or {}).get("p_adjusted"),
                        "verdict": b.get("verdict_rule", b.get("verdict")), "decision_bearing": False},
        )
    return out


# ---- sign-flip (E:216-217) ------------------------------------------------------------------------------
def signflip(view: dict[str, Any], threshold: float, alternative: str, seed: int) -> dict[str, Any]:
    base = {"decision_bearing": False, "clusters": "entry", "threshold": threshold, "alternative": alternative,
            "seed": seed, "rule": "cluster_inference.registered_signflip: exact if 2^G <= 2^20, else Monte Carlo "
                                  f"over {SIGNFLIP_PATTERNS:,} patterns (E:216-217)"}
    if not view["diffs"]:
        return {**base, "status": "no_pairs", "p_value": None}
    try:
        from scripts.analysis import cluster_inference as ci  # noqa: E402
        fn = ci.registered_signflip
    except Exception as exc:  # reported in the verdict's sentence, never fatal
        return {**base, "status": "import_error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    try:
        d = fn(view["diffs"], [k[0] for k in view["keys"]], threshold=threshold, alternative=alternative, seed=seed)
    except Exception as exc:
        return {**base, "status": "error", "error": f"{type(exc).__name__}: {exc}", "p_value": None}
    n_entries = len({k[0] for k in view["keys"]})
    if d.get("n_clusters") != n_entries:  # L1b: the sign-flip's clusters are the entries, never scenarios
        raise AssertionError(f"sign-flip on {view['left']} - {view['right']}: {d.get('n_clusters')} clusters, "
                             f"{n_entries} entries (E:200-202)")
    return {**base, "status": "ok", "p_value": float(d["p"]), "method": d.get("method"),
            "n_patterns": d.get("n_patterns"), "n_clusters": d.get("n_clusters")}


def signflip_note(pid: str, verdict: str, sf: Optional[dict[str, Any]],
                  p_boot: Optional[float] = None) -> Optional[str]:
    """A sign-flip disagreement for the verdict's sentence (E:216-217). In H, N and CF (m = 1) the sign-flip is set
    against the bootstrap verdict. In D (m = 4) it is set against the UNADJUSTED bootstrap p (``p_boot``, 2 x share
    <= 0), because the sign-flip p is unadjusted: a member that fails only on Holm is not a disagreement."""
    if sf is None or sf.get("status") == "not_applicable":
        return None
    if sf.get("status") != "ok":
        return (f"the cluster sign-flip p is unavailable ({sf.get('status')}: {sf.get('error', '')}); "
                "not decision-bearing (E:216-217)")
    if verdict not in ("supported", "not_supported", "reversed"):
        return None
    p = float(sf["p_value"])
    fam = PRED_SPECS[pid]["family"]
    if fam == "D":
        if p_boot is None:
            return None
        boot = float(p_boot) <= ALPHA
        against = (f"the unadjusted bootstrap p ({float(p_boot):.4f}, 2 × share ≤ 0; compared unadjusted, since D's "
                   "Holm step is not applied to the sign-flip)")
    else:
        boot = verdict == "supported" if fam == "N" else verdict in ("supported", "reversed")
        against = "the bootstrap verdict"
    sign = p <= ALPHA
    if boot == sign:
        return None
    return (f"the cluster sign-flip p ({sf.get('method')}, {sf.get('alternative')}) is {p:.4f}, which "
            f"{'rejects' if sign else 'does not reject'} at 0.05 and so disagrees with {against} "
            "(E:217; not decision-bearing)")


# ---- the report --------------------------------------------------------------------------------------------
def _entry_classes(entry_classes: Optional[dict[str, Iterable[str]]], test_ids: list[str]) -> dict[str, Any]:
    try:
        if entry_classes is None:
            from sidekick.environments.bfcl_env import load_entries  # noqa: E402
            entry_classes = {k: v["involved_classes"] for k, v in load_entries().items()}
        missing = [t for t in test_ids if t not in entry_classes]
        if missing:
            return {"status": "error", "error": f"{len(missing)} test ids have no involved_classes, e.g. {missing[:3]}"}
        labels = {t: "+".join(sorted(str(c) for c in entry_classes[t])) for t in test_ids}
        return {"status": "ok", "labels": labels, "n_class_sets_design": len(set(labels.values())),
                "source": "sidekick.environments.bfcl_env.load_entries (:181) involved_classes (task definitions)"}
    except Exception as exc:  # a sensitivity: never fatal, reported
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def arm_block(ctx: dict[str, Any], stem: str) -> dict[str, Any]:
    arm = ctx["arms"][stem]
    rows = arm["rows"]
    scored = {k: r for k, r in rows.items() if not r["crash"]}
    gp = [r["goal_pass"] for r in scored.values() if r["goal_pass"] is not None]
    sc = [r["success"] for r in scored.values() if r["success"] is not None]
    n_lim = sum(1 for r in scored.values() if r["error_type"] == LIMIT)
    live = [float(r["ledger_calls"] - r["cache_calls"]) for r in scored.values() if r["ledger_calls"] is not None]
    n_negative = sum(1 for v in live if v < 0)
    attributed = [float(r["n_planner_calls"]) for r in scored.values() if r["n_planner_calls"] is not None]
    ledger = [float(r["ledger_calls"]) for r in scored.values() if r["ledger_calls"] is not None]

    def total(name: str, pool: Iterable[dict[str, Any]]) -> Optional[float]:
        vals = [r[name] for r in pool if r[name] is not None]
        return round(sum(vals), 6) if vals else None

    blk = {
        **tallies(arm),
        "systems": arm["systems"],
        "n_pairs": len(scored),
        "goal_pass_mean": dr._mean(gp),
        "success_mean": dr._mean(sc),
        "n_success_missing": len(scored) - len(sc),
        "error_types": dict(sorted(Counter(str(r["error_type"] or "none") for r in rows.values()).items())),
        "n_limit": n_lim,
        "limit_rate": round(n_lim / len(scored), 6) if scored else None,
        "force_quit_count": sum(1 for r in scored.values() if r["force_quit"] is True),
        "force_quit_count_all_episodes": sum(1 for r in rows.values() if r["force_quit"] is True),
        "n_force_quit_unrecorded": sum(1 for r in scored.values() if r["force_quit"] is None),
        "n_steps_zero": sum(1 for r in scored.values() if r["steps"] == 0),
        "missing_keys": [key_label(k) for k in arm["missing"][:50]],
        "ordinary_crash_keys": [key_label(k) for k in arm["ordinary_crash"]],
        "cost": {
            "calls_live_mean": None if n_negative else dr._mean(live),
            "calls_live_total": None if n_negative else (round(sum(live), 6) if live else None),
            "calls_live_reason": (f"{n_negative} non-crash episodes have a negative ledger - cache" if n_negative
                                  else None),
            "calls_attributed_mean": dr._mean(attributed),
            "calls_attributed_total": round(sum(attributed), 6) if attributed else None,
            "calls_ledger_mean": dr._mean(ledger),
            "calls_ledger_total": round(sum(ledger), 6) if ledger else None,
            "calls_ledger_total_all_episodes": total("ledger_calls", rows.values()),
            "n_cached_plan_events": sum(r["n_cached_plan_events"] for r in scored.values()),
            "planner_tokens_total": total("planner_tokens", scored.values()),
            "executor_tokens_total": total("executor_tokens", scored.values()),
            "usd_total": total("usd", scored.values()),
            "usd_total_all_episodes": total("usd", rows.values()),
            "hosted_ceiling": HOSTED_CEILINGS.get(stem),
            "conventions": "calls_live = ledger - cache; calls_attributed = n_planner_calls (E:96-97, J10 :1006-1015)",
        },
    }
    if stem in PREFIX_ARMS:
        controls = ctx["controls"].get(stem) or {}
        cc = hc.control_counts(controls, keys=sorted(scored))
        hs = ctx["hstar"].get(stem) or {}
        blk["hstar"] = {"n_hstar": sum(1 for k in scored if hs.get(k) is True),
                        "n_h_missing": sum(1 for k in scored if hs.get(k) is None),
                        "n_h_flag_true": cc["n_h_flag_true"], "n_live_but_unflagged": cc["n_live_but_unflagged"],
                        "n_terminal": cc["n_terminal"], "n_h_flag_true_but_terminal": cc["n_h_flag_true_but_terminal"],
                        "n_pre_loop_limit": cc["n_pre_loop_limit"],
                        "source_campaigns": dict(sorted(Counter(str(controls[k].get("source_campaign"))
                                                                for k in scored if k in controls).items()))}
    return blk


def executor_asks(ctx: dict[str, Any]) -> dict[str, Any]:
    per_arm = {}
    for stem in ARMS:
        rows = ctx["arms"][stem]["rows"]
        asked = {k: r["asks"] for k, r in rows.items() if r["asks"]}
        per_arm[stem] = {
            "n_episodes_with_answered_ask": len(asked),
            "n_scored_episodes_with_answered_ask": sum(1 for k in asked if not rows[k]["crash"]),
            "n_answered_ask_calls": sum(asked.values()),
            "n_episodes_without_event_log": sum(1 for r in rows.values() if r["asks"] is None),
            "bound_pp": round(100.0 * len(asked) / ctx["n_expected"], 2),
            "episodes": [key_label(k) for k in sorted(asked)],
        }
    return {"reporting_only": True, "rule": "E:300-301, E:324 (J10 Am1 §I :881-894)",
            "definition": DEFINITIONS["executor_asks"], "denominator": ctx["n_expected"], "flag_pp": ASK_FLAG_PP,
            "per_arm": per_arm, "per_contrast": {}}


def _contrast_side_info(ctx: dict[str, Any], row_id: str, left: str, right: str) -> dict[str, Any]:
    asks = ctx["asks"]["per_arm"]
    lim = {a: ctx["arm_blocks"][a].get("limit_rate") for a in dict.fromkeys((left, right))}
    bounds = {a: asks[a]["bound_pp"] for a in dict.fromkeys((left, right))}
    worst = max(bounds.values())
    ctx["asks"]["per_contrast"][row_id] = {"bound_pp": bounds, "max_bound_pp": worst,
                                           "bound_reaches_1pp": worst >= ASK_FLAG_PP}
    return {"limit_rates": lim, "ask_bounds_pp": bounds, "ask_bound_reaches_1pp": worst >= ASK_FLAG_PP}


def metric_blocks(ctx: dict[str, Any], row_id: str, left: str, right: str, *, kind: str = "plain",
                  h: str = "hstar", threshold_pp: float = 0.0, direction: str = "two-sided",
                  gp_est: Optional[dict[str, Any]] = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Both metrics of one row through pair_view: goal_pass (or the given primary estimate) and success."""
    out: dict[str, Any] = {}
    views: dict[str, Any] = {}
    for metric in METRICS:
        view = pair_view(ctx, left, right, metric)
        views[metric] = view
        if metric == "goal_pass" and gp_est is not None:
            out[metric] = public(gp_est)
            continue
        why = _blocked(ctx, row_id, left, right, view)
        if why:
            out[metric] = None
            continue
        hv = None
        if kind == "ratio":
            hv = view["left_hstar"] if h == "hstar" else view["left_hflag"]
        est = estimate(ctx, row_id, view, kind=kind, h=hv, threshold_pp=threshold_pp, direction=direction)
        blk = public(est)
        if metric == "success" and blk is not None:
            blk["n_success_missing_dropped"] = view["n_metric_missing"]
            blk["rule"] = "none (same intervals, no rule; E:221)"
            note = tgc_atom_note(blk, threshold_pp)
            if note:
                blk["atom_note"] = note
        out[metric] = blk
        if metric == "goal_pass":
            out["_est"] = est
    return out, views


def build_report(results_root: Path = DEFAULT_RESULTS, config_dir: Path = DEFAULT_CONFIG_DIR,
                 refill_dir: Path = DEFAULT_REFILL_DIR, split_file: Path = DEFAULT_SPLIT,
                 repo_root: Path = REPO_ROOT, *, n_boot: int = N_BOOT, seed: int = SEED,
                 pool_seeds: Iterable[int] = POOL_SEEDS, big_n: int = BIG_N, big_seed: int = BIG_SEED,
                 n_test_entries: int = N_TEST_ENTRIES,
                 entry_classes: Optional[dict[str, Iterable[str]]] = None,
                 cannot_complete: Optional[Iterable[str]] = None) -> dict[str, Any]:
    """Data guards G4-G9 (GuardError), the abort rules, then every registered row. Writes nothing.

    ``cannot_complete``: the arms the operator has judged unable to complete 300 pairs (E:303-307). main() always
    passes it (``--cannot-complete``), so the registered read enforces it; None skips that one check (unit tests of
    the statistics call build_report directly)."""
    results_root, config_dir, refill_dir = Path(results_root), Path(config_dir), Path(refill_dir)
    for marker in ("test_normal", "test_challenge"):
        if marker in str(results_root):
            raise GuardError("G5", f"results root {results_root} names {marker!r}")
    split = load_split(Path(split_file), n_test_entries)  # G4
    test_ids = split["test"]
    matrix = {(t, s) for t in test_ids for s in SEEDS}
    n_clusters_design = len(set(test_ids))
    assert n_clusters_design == n_test_entries, "the design has one cluster per test entry (E:196-202)"
    arms = {stem: load_arm(results_root, stem, matrix) for stem in ARMS}  # G5
    for arm in arms.values():
        arm_completeness(arm, matrix, refill_dir)
    below = [s for s in ABORT_ARMS if not arms[s]["complete"]]
    absent = [s for s in ARMS if not arms[s]["present"]]
    if absent and not below:  # L14: all 13 arms of E:42-53 are given, none is optional (G7: configs for all 13)
        raise GuardError("G7", f"campaign directory absent for {absent} under {results_root}: a read needs all 13 "
                               "registered arms and their derived configs (L14, E:42-53); an arm may be absent only "
                               "on the not-run path (E:303-304)")
    ack = guard_cannot_complete(arms, below, cannot_complete)  # G5: 'cannot complete' is a final judgement
    guard_metrics(arms)  # G8
    pl = planless_keys(results_root, arms[CEILING], matrix)
    planless = pl.pop("_keys", None)
    configs: dict[str, dict[str, Any]] = {}
    manifests: dict[str, dict[str, Any]] = {}
    for stem in ARMS:  # G7 then G6, for every arm that has a campaign directory
        if not arms[stem]["present"]:
            configs[stem] = {"status": "not_checked: campaign directory absent (no episodes to attribute)"}
            continue
        configs[stem] = check_derived_config(stem, config_dir, repo_root, results_root, planless)
        manifests[stem] = check_manifests(arms[stem], configs[stem], results_root)
    plan_events = guard_plan_events(arms, planless, matrix, results_root)  # G9
    # h* and controls, from what actually ran (handoff_control.hstar_flags :278 / arm_control :261)
    hstar = {s: hc.hstar_flags(Path(arms[s]["dir"]), seeds=SEEDS) if arms[s]["present"] else {} for s in PREFIX_ARMS}
    controls = {s: hc.arm_control(Path(arms[s]["dir"]), seeds=SEEDS) if arms[s]["present"] else {} for s in PREFIX_ARMS}
    for stem in PREFIX_ARMS:  # L4: the prefix actually replayed came from the test ceiling
        ceiling_dir = results_root / TEST_CEILING_CID
        for k, c in controls[stem].items():
            if k in arms[stem]["rows"] and not arms[stem]["rows"][k]["crash"] and c.get("status") == "ok":
                if not _same_path(c.get("source_campaign"), ceiling_dir):
                    raise GuardError("G7", f"{arms[stem]['cid']} {key_label(k)}: the handoff record's "
                                           f"source_campaign {c.get('source_campaign')!r} is not {ceiling_dir} (L4)")
    script_path = Path(__file__).resolve()
    _rc, script_git = _git(["rev-parse", "HEAD"], REPO_ROOT)
    _rc, script_dirty = _git(["status", "--porcelain", "--", str(script_path)], REPO_ROOT)
    meta: dict[str, Any] = {
        "generated_by": "scripts/analysis/bfcl_test_report.py",
        "prereg": f"{PREREG_REL} (the E-prereg, FROZEN 8802a95)",
        "split": "test",
        "status": None,
        "script": {"path": str(script_path), "sha256": sha256_file(script_path), "git_sha": script_git or None,
                   "git_dirty": None if script_dirty is None else bool(script_dirty)},
        "split_file": {k: v for k, v in split.items() if k != "test"},
        "n_boot": n_boot, "seed": seed, "pool_seeds": list(pool_seeds), "boundary_window_pp": BOUNDARY_WINDOW_PP,
        "big_n": big_n, "big_seed": big_seed, "big_n_voted": False,
        "sign_flip": {"patterns": SIGNFLIP_PATTERNS, "seed": SEED, "clusters": "entry"},
        "alpha": ALPHA, "ci": "95% percentile entry-cluster bootstrap", "cluster_unit": "entry",
        "n_clusters": n_clusters_design, "n_clusters_design_registered": N_TEST_ENTRIES,
        "seeds": list(SEEDS), "n_entries": n_test_entries, "n_pairs_per_arm": len(matrix),
        "divergence_cap": DIVERGENCE_CAP, "planless_cap": PLANLESS_CAP, "ask_flag_pp": ASK_FLAG_PP,
        "ni_margin_pp": NI_MARGIN_PP,
        "codex_pin": {"cli_version_last_token": CODEX_CLI_PIN, "model_requested": MODEL_PIN,
                      "source": "scripts/pbs/bfcl_arm.pbs:72; docs/plan_luna_reset_20260925.md:180",
                      "served_model": "not observable"},
        "campaigns": {s: arms[s]["cid"] for s in ARMS},
        "paths_read": {"results_root": str(results_root), "config_dir": str(config_dir),
                       "refill_dir": str(refill_dir), "split_file": str(split_file), "repo_root": str(repo_root),
                       "campaign_dirs": {s: arms[s]["dir"] for s in ARMS},
                       "derived_configs": {s: configs[s].get("path") for s in ARMS},
                       "refill_logs": {s: arms[s]["refill"]["path"] for s in ARMS}},
        "pooling": "BFCL is reported beside J10, never pooled (E:336)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "definitions": DEFINITIONS,
    }
    meta["cannot_complete_acknowledged"] = ack
    guards = {"G4": "ok", "G5": {"status": "ok", "cannot_complete": ack}, "G6": manifests, "G7": configs,
              "G8": "ok", "G9": plan_events}
    if below:  # E:303-304: not run, never read at reduced power
        meta["status"] = "not_run"
        meta["not_run_reason"] = (f"{', '.join(below)} could not complete {len(matrix)} pairs: the test is reported "
                                  "as not run, never at reduced power (E:303-304)")
        return {"meta": meta, "guards": guards, "arms": {s: tallies(arms[s]) for s in ARMS},
                "planless_keys": pl, "predictions": None,
                "not_run": {"rule": "E:303-304", "arms_below_300": below,
                            "content": "per-arm completeness tallies only; no contrasts, no p-values"},
                "sentences": {"headline": f"The BFCL test is reported as not run: {meta['not_run_reason']}."}}

    meta["status"] = "read"
    classes = _entry_classes(entry_classes, test_ids)
    ctx: dict[str, Any] = {
        "arms": arms, "matrix": matrix, "n_expected": len(matrix), "n_entries": n_test_entries, "hstar": hstar,
        "controls": controls, "planless": planless or [],
        "planless_blocked": bool(planless is not None and len(planless) > PLANLESS_CAP),
        "n_boot": n_boot, "seed": seed, "pool_seeds": tuple(pool_seeds), "big_n": big_n, "big_seed": big_seed,
        "classes": classes.get("labels"), "cache": {},
    }
    ctx["arm_blocks"] = {s: arm_block(ctx, s) for s in ARMS}
    ctx["asks"] = executor_asks(ctx)

    # ---- registered predictions -----------------------------------------------------------------------
    views = {pid: pair_view(ctx, s["left"], s["right"]) for pid, s in PRED_SPECS.items()}
    base: dict[str, dict[str, Any]] = {}
    boundary: dict[str, dict[str, Any]] = {}
    for fam in FAMILIES:
        res = evaluate_family(ctx, fam, views, n_boot=n_boot, seed=seed)
        base.update(res)
        boundary.update(boundary_family(ctx, fam, views, res))
    key_excl = key_exclusion(ctx, base, views)
    predictions: dict[str, dict[str, Any]] = {}
    families: dict[str, Any] = {}
    for fam, members in FAMILIES.items():
        families[fam] = {"members": list(members), "m": len(members), "alpha": ALPHA, "method": "Holm step-down "
                         "(j10_report.holm_adjust :2061 via a1_decide_family :2788)",
                         "p_raw": {p: (base[p].get("holm") or {}).get("p_raw") for p in members},
                         "p_holm": {p: (base[p].get("holm") or {}).get("p_adjusted") for p in members},
                         "p_raw_substituted_as_1": [p for p in members
                                                    if (base[p].get("holm") or {}).get("p_raw_substituted")]}
    for pid in PRED_ORDER:
        spec = PRED_SPECS[pid]
        r = base[pid]
        view = views[pid]
        verdict = r.get("verdict_rule", r.get("verdict"))
        blk: dict[str, Any] = {
            "id": pid, "family": spec["family"], "left": spec["left"], "right": spec["right"],
            "estimand": ("Σd·h*/Σh*, h* from the left arm " + spec["left"]) if spec["kind"] == "hstar"
            else "mean of left − right over the pairs",
            "rule": spec["rule"], "rule_text": A1_RULES[spec["rule"]]["text"], "threshold_pp": spec["threshold_pp"],
            "direction": A1_RULES[spec["rule"]]["direction"], "cite": spec["cite"], "decision_bearing": True,
            "status": "read" if r.get("decidable") else r.get("verdict"), "reason": r.get("reason"),
            **view_frame(view),
            "goal_pass": public(r.get("_est")) if r.get("decidable") else None,
            "holm": r.get("holm"), "verdict_holm": r.get("verdict_holm"),
            "boundary": boundary[pid], "key_exclusion": key_excl["rows"].get(pid),
        }
        if spec["kind"] == "hstar":
            blk["h_arm"] = spec["left"]
        if pid == "P3":
            blk["reading_qualifier"] = P3_QUALIFIER
        if r.get("decidable"):
            est = r["_est"]
            if spec["reversal"] == "interval":
                blk["reversal"] = {"upper_below_0": bool(r["_hi"] < 0),
                                   "p_less": round(bootstrap_pvalue(est["_means"], 0.0, "less"), 6),
                                   "p_less_adjusted": False, "rule": "E:176-179: read from the interval alone"}
            elif spec["reversal"] == "holm":
                blk["reversal"] = {"upper_below_0": bool(r["_hi"] < 0), "reversed": verdict == "reversed",
                                   "rule": "a primary finding (E:125, E:127)"}
            b = boundary[pid]
            if b.get("fired") and not b.get("stable", True):
                blk["verdict_before_boundary"] = verdict
                verdict = "on_boundary"
            kx = key_excl["rows"].get(pid) or {}
            if kx.get("differs") and verdict != "on_boundary":
                blk["verdict_before_key_exclusion"] = verdict
                verdict = "on_boundary"
            sf_spec = spec["signflip"]
            blk["sign_flip"] = (signflip(view, sf_spec[1], sf_spec[0], SEED) if sf_spec is not None else
                                {"status": "not_applicable", "reason": "not applicable (ratio estimand)",
                                 "decision_bearing": False})
        else:
            blk["sign_flip"] = None
        blk["verdict"] = verdict
        blk.update(_contrast_side_info(ctx, pid, spec["left"], spec["right"]))
        sm, _ = metric_blocks(ctx, pid, spec["left"], spec["right"],
                              kind="plain" if spec["kind"] == "plain" else "ratio", threshold_pp=spec["threshold_pp"],
                              gp_est=r.get("_est") if r.get("decidable") else {"status": "not_read"})
        blk["success"] = sm["success"]
        predictions[pid] = blk

    # ---- B1, D flags, supporting rows, m4 rows ----------------------------------------------------------
    b1: dict[str, Any] = {}
    for rid, spec in B1_SPECS.items():
        b1[rid] = handoff_row(ctx, rid, spec["left"], spec["right"], spec["h"], NI_MARGIN_PP, reading=True,
                              boundary=spec["h"] == "hstar")
    d_flags = {rid: handoff_row(ctx, rid, s["left"], s["right"], s["h"], 0.0, reading=False, boundary=False)
               for rid, s in D_FLAG_SPECS.items()}
    supporting: dict[str, Any] = {}
    for rid, spec in SUPPORT_SPECS.items():
        supporting[rid] = plain_row(ctx, rid, spec["left"], spec["right"], spec["threshold_pp"], spec["note"])
    m4_rows: dict[str, Any] = {}
    for rid, (left, right) in M4_SPECS.items():
        m4_rows[rid] = {"exploratory": True, "label": "EXPLORATORY: m4 (E:49, E:187, E:328)",
                        "all_pairs": plain_row(ctx, rid, left, right, 0.0, "all pairs", exploratory=True),
                        "hstar_from_left": handoff_row(ctx, rid + "_hstar", left, right, "hstar", 0.0,
                                                       reading=False, boundary=False, exploratory=True)}

    # ---- sensitivities ----------------------------------------------------------------------------------
    sensitivity = {
        "key_exclusion": {k: v for k, v in key_excl.items() if k != "rows"} | {"rows": key_excl["rows"]},
        "p3_limit_excluded": p3_limit_excluded(ctx, views["P3"], predictions["P3"]),
        "limit_split": {rid: limit_split(ctx, rid) for rid in LIMIT_SPLIT_ROWS},
        "limit_as_0": {rid: limit_as_zero(ctx, rid) for rid in LIMIT_SPLIT_ROWS},
        "involved_classes": class_set_sensitivity(ctx, views, predictions, classes),
    }

    # ---- BY-FDR (E:218-220) ----------------------------------------------------------------------------
    by = by_fdr(predictions, b1, supporting)

    # ---- exploratory -------------------------------------------------------------------------------------
    exploratory = {
        "label": "EXPLORATORY (E:327-328); not decision-bearing",
        "per_turn": per_turn(ctx),
        "per_class_set": per_class_set(ctx),
        "channel_content": channel_content(ctx),
        "m4_rows": "see m4_rows",
    }

    report = {
        "meta": meta, "guards": guards,
        "arms": ctx["arm_blocks"],
        "planless_keys": pl,
        "divergent_keys": {"cap": DIVERGENCE_CAP, "definition": DEFINITIONS["divergent_key"],
                           "source": f"results ({DIVERGENCE_READER}) + refill logs (S3)",
                           "per_arm": {s: {"n": len(arms[s]["divergent"]),
                                           "keys": [key_label(k) for k in arms[s]["divergent"]],
                                           "n_divergent_reason_not_refilled":
                                               len(arms[s]["divergent_reason_not_refilled"]),
                                           "divergent_reason_not_refilled":
                                               [key_label(k) for k in arms[s]["divergent_reason_not_refilled"]],
                                           "n_divergent_reason_without_run_start":
                                               len(arms[s]["divergent_reason_no_run_start"]),
                                           "refill_log": arms[s]["refill"]} for s in ARMS}},
        "predictions": predictions,
        "families": families,
        "b1": b1,
        "d_flags": d_flags,
        "m4_rows": m4_rows,
        "supporting": supporting,
        "sensitivity": sensitivity,
        "by_fdr": by,
        "executor_asks": ctx["asks"],
        "hstar_counts": {s: ctx["arm_blocks"][s].get("hstar") for s in PREFIX_ARMS},
        "cost": {s: ctx["arm_blocks"][s]["cost"] for s in ARMS},
        "exploratory": exploratory,
        "dev_reference": dev_reference(),
    }
    report["sentences"] = build_sentences(report)
    for pid, text in report["sentences"].items():
        if pid in report["predictions"]:
            report["predictions"][pid]["sentence"] = text
    return report


def handoff_row(ctx: dict[str, Any], rid: str, left: str, right: str, h: str, threshold_pp: float, *, reading: bool,
                boundary: bool, exploratory: bool = False) -> dict[str, Any]:
    """A Σd·h/Σh row on both metrics; h from the LEFT arm (h* via hstar_flags, or the handoff_occurred flag).
    reading: holds iff the unadjusted lower bound is above the threshold (B1, E:140); boundary as E:140."""
    blocks, views = metric_blocks(ctx, rid, left, right, kind="ratio", h=h, threshold_pp=threshold_pp,
                                  direction="greater")
    view = views["goal_pass"]
    est = blocks.pop("_est", None)
    why = _blocked(ctx, rid, left, right, view)
    out: dict[str, Any] = {"id": rid, "left": left, "right": right, "h_arm": left,
                           "h": "h* (handoff_control.hstar_flags)" if h == "hstar" else "h_flag (handoff_occurred)",
                           "threshold_pp": threshold_pp, "decision_bearing": False, **view_frame(view),
                           "status": why[0] if why else "read", "reason": why[1] if why else None,
                           "goal_pass": blocks.get("goal_pass"), "success": blocks.get("success")}
    if exploratory:
        out["exploratory"] = True
    out.update(_contrast_side_info(ctx, rid, left, right))
    if why or est is None or est.get("status") != "ok":
        out["reading"] = None if why else f"no reading ({(est or {}).get('status')})"
        return out
    if reading:
        rd_ = "holds" if est["lo"] > threshold_pp / 100.0 else "fails"
        out["reading"] = rd_
        out["reading_rule"] = f"holds iff the unadjusted entry lower bound is above {threshold_pp:+.2f} pp (E:140)"
        if boundary:
            near = abs(est["lo"] * 100.0 - threshold_pp) <= BOUNDARY_WINDOW_PP + 1e-12
            bl: dict[str, Any] = {"rule": "boundary (E:140, E:213-215)", "fired": near, "window_pp": BOUNDARY_WINDOW_PP}
            if near:
                rows = []
                for s in ctx["pool_seeds"]:
                    e = estimate(ctx, rid, view, kind="ratio", h=view["left_hstar"], threshold_pp=threshold_pp,
                                 direction="greater", seed=s)
                    rows.append({"seed": s, "lo_pp": dr._pp(e.get("lo")), "hi_pp": dr._pp(e.get("hi")),
                                 "reading": "holds" if e.get("lo") is not None and e["lo"] > threshold_pp / 100.0
                                 else "fails"})
                big = estimate(ctx, rid, view, kind="ratio", h=view["left_hstar"], threshold_pp=threshold_pp,
                               direction="greater", n_boot=ctx["big_n"], seed=ctx["big_seed"])
                bl.update(bounds_by_seed=rows, stable=all(x["reading"] == rd_ for x in rows),
                          bound_200k={"n_boot": ctx["big_n"], "seed": ctx["big_seed"], "lo_pp": dr._pp(big.get("lo")),
                                      "hi_pp": dr._pp(big.get("hi")), "decision_bearing": False})
                if not bl["stable"]:
                    out["reading_before_boundary"] = rd_
                    out["reading"] = "on_boundary"
            else:
                bl["stable"] = True
            out["boundary"] = bl
    return out


def plain_row(ctx: dict[str, Any], rid: str, left: str, right: str, threshold_pp: float, note: str, *,
              exploratory: bool = False) -> dict[str, Any]:
    blocks, views = metric_blocks(ctx, rid, left, right, kind="plain", threshold_pp=threshold_pp,
                                  direction="two-sided")
    view = views["goal_pass"]
    est = blocks.pop("_est", None)
    why = _blocked(ctx, rid, left, right, view)
    out: dict[str, Any] = {"id": rid, "left": left, "right": right, "note": note, "threshold_pp": threshold_pp,
                           "decision_bearing": False, "adjusted": False, **view_frame(view),
                           "status": why[0] if why else "read", "reason": why[1] if why else None,
                           "goal_pass": blocks.get("goal_pass"), "success": blocks.get("success")}
    if exploratory:
        out["exploratory"] = True
    else:
        out["label"] = "supporting: pre-specified, unadjusted, not decision-bearing (E:183)"
    out.update(_contrast_side_info(ctx, rid, left, right))
    if why or est is None or est.get("status") != "ok":
        return out
    if rid == "S3":
        out["reading_at_minus_7"] = "holds" if est["lo"] > NI_MARGIN_PP / 100.0 else "fails"
        out["p_ni"] = round(bootstrap_pvalue(est["_means"], NI_MARGIN_PP / 100.0, "greater"), 6)
    if rid == "CF3":
        if est["lo"] > 0:
            out["reading"] = "executing the action adds to advice written under a neutral prompt"
        elif est["hi"] < 0:
            out["reading"] = "neutral-prompt advice beats takeover"
        else:
            out["reading"] = f"the added effect of execution is not resolved at {ctx['n_expected']} pairs"
        out["reading_rule"] = "J10 Am1 §C (:795-801), adapted to 300 pairs; never 'execution adds nothing'"
    return out


def key_exclusion(ctx: dict[str, Any], base: dict[str, dict[str, Any]],
                  base_views: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """E:295-296 (J10 :228-232): the planless keys removed from every arm; same bootstrap, family (D re-Holmed over
    all four, an unread member at p = 1) and rule. A verdict that moves is on the boundary."""
    keys = ctx["planless"]
    out: dict[str, Any] = {"rule": "E:295-296", "n_keys": len(keys), "keys": [key_label(k) for k in keys]}
    if not keys:
        out["status"] = "no planless keys: every verdict is unchanged by construction"
        out["rows"] = {pid: {**view_frame(base_views[pid]), "differs": False, "n_keys_excluded": 0}
                       for pid in PRED_ORDER}
        out["rows"]["P3"]["reading_qualifier"] = P3_QUALIFIER
        return out
    views = {pid: pair_view(ctx, s["left"], s["right"], exclude=keys, variant="planless_excluded")
             for pid, s in PRED_SPECS.items()}
    rows = {}
    for fam in FAMILIES:
        res = evaluate_family(ctx, fam, views, n_boot=ctx["n_boot"], seed=ctx["seed"])
        for pid, s in res.items():
            b = base[pid]
            v_all = b.get("verdict_rule") if b.get("decidable") else None
            v_x = s.get("verdict_rule") if s.get("decidable") else None
            rows[pid] = {**view_frame(views[pid]), "verdict_all_pairs": v_all, "verdict_without_keys": v_x,
                         "differs": bool(v_all is not None and v_x is not None and v_all != v_x),
                         "n_pairs_without_keys": views[pid]["n_pairs"],
                         "n_keys_excluded": views[pid]["n_excluded_keys"],
                         "goal_pass_without_keys": public(s.get("_est")),
                         "p_holm_without_keys": (s.get("holm") or {}).get("p_adjusted")}
    rows["P3"]["reading_qualifier"] = P3_QUALIFIER
    out["status"] = "ok"
    out["rows"] = rows
    return out


def p3_limit_excluded(ctx: dict[str, Any], view: dict[str, Any], p3: dict[str, Any]) -> dict[str, Any]:
    base = {"sensitivity_only": True, "decision_bearing": False, "cite": "E:131-132; J10 :378-382",
            "rule": "pairs whose ceiling (planner_alone_cap81) episode hit `limit` are dropped",
            "caveat": "exclusion selects on the ceiling's own failures (J10 :378-382)",
            "reading_qualifier": P3_QUALIFIER}
    if p3.get("status") != "read":
        return {**base, **view_frame(view), "status": p3.get("status"), "reason": p3.get("reason")}
    kept = [i for i, e in enumerate(view["right_error"]) if e != LIMIT]
    dropped = [i for i, e in enumerate(view["right_error"]) if e == LIMIT]
    sub = subset_view(view, kept, "p3_limit_excluded")
    est = estimate(ctx, "P3_limit_excluded", sub, threshold_pp=NI_MARGIN_PP, direction="greater")

    def mean_of(vals: list[float]) -> Optional[float]:
        return round(statistics.fmean(vals), 6) if vals else None

    out = {**base, **view_frame(sub), "status": "ok", "n_kept": len(kept), "n_dropped": len(dropped),
           "ceiling_mean_kept": mean_of([view["right_values"][i] for i in kept]),
           "ceiling_mean_dropped": mean_of([view["right_values"][i] for i in dropped]),
           "prefix_mean_kept": mean_of([view["left_values"][i] for i in kept]),
           "prefix_mean_dropped": mean_of([view["left_values"][i] for i in dropped]),
           "goal_pass": public(est)}
    if est.get("status") == "ok":
        out["reading_at_minus_7"] = "holds" if est["lo"] > NI_MARGIN_PP / 100.0 else "fails"
    return out


def cluster_bootstrap_multi(groups: dict[str, list[float]], stats: dict[str, tuple[int, int]], *, n_boot: int,
                            seed: int) -> dict[str, list[float]]:
    """Σ comp[num] / Σ comp[den] for several statistics from ONE draw sequence (j10_report.cluster_bootstrap_means's:
    labels sorted, one random.Random(seed), G draws of randrange(G) per replicate); a replicate with a zero
    denominator is dropped for that statistic."""
    labels = sorted(groups)
    g = len(labels)
    width = len(next(iter(groups.values()))) if groups else 0
    rng = random.Random(seed)
    out: dict[str, list[float]] = {name: [] for name in stats}
    for _ in range(n_boot):
        tot = [0.0] * width
        for _ in range(g):
            comp = groups[labels[rng.randrange(g)]]
            for i in range(width):
                tot[i] += comp[i]
        for name, (num, den) in stats.items():
            if tot[den] > 0:
                out[name].append(tot[num] / tot[den])
    for v in out.values():
        v.sort()
    return out


def limit_split(ctx: dict[str, Any], rid: str) -> dict[str, Any]:
    """J10 Am1 §D2 (am1_limit_split :3318-3356, ported with entry clusters): pairs where either arm hit `limit` vs
    neither; the two contributions sum to the whole. Post-treatment; never a corrected estimate."""
    left, right = (PRED_SPECS[rid]["left"], PRED_SPECS[rid]["right"]) if rid in PRED_SPECS else \
        (SUPPORT_SPECS[rid]["left"], SUPPORT_SPECS[rid]["right"])
    view = pair_view(ctx, left, right)
    base = {"post_treatment": True, "not_a_corrected_estimate": True, "decision_bearing": False,
            "cite": "E:321-322; J10 :812-820", **view_frame(view)}
    why = _blocked(ctx, rid, left, right, view)
    if why:
        return {**base, "status": why[0], "reason": why[1]}
    groups: dict[str, list[float]] = {}
    n_lim = 0
    for k, d, le, re_ in zip(view["keys"], view["diffs"], view["left_error"], view["right_error"]):
        lim = 1.0 if LIMIT in (le, re_) else 0.0
        n_lim += int(lim)
        g = groups.setdefault(k[0], [0.0] * 6)
        for i, v in enumerate((d * lim, lim, d * (1.0 - lim), 1.0 - lim, d, 1.0)):
            g[i] += v
    stats = {"all": (4, 5), "contribution_limit_pairs": (0, 5), "contribution_neither": (2, 5),
             "mean_on_limit_pairs": (0, 1), "mean_on_neither": (2, 3)}
    tot = [sum(g[i] for g in groups.values()) for i in range(6)]
    boot = cluster_bootstrap_multi(groups, stats, n_boot=ctx["n_boot"], seed=ctx["seed"])
    out = {**base, "status": "ok", "n_limit_pairs": n_lim, "n_neither": view["n_pairs"] - n_lim,
           "n_limit_left": sum(1 for e in view["left_error"] if e == LIMIT),
           "n_limit_right": sum(1 for e in view["right_error"] if e == LIMIT)}
    for name, (num, den) in stats.items():
        means = boot[name]
        lo, hi = percentile_ci(means) if means else (None, None)
        out[name] = {"point_pp": dr._pp(tot[num] / tot[den]) if tot[den] > 0 else None,
                     "ci95_entry": [dr._pp(lo), dr._pp(hi)], "n_boot_valid": len(means)}
    return out


def limit_as_zero(ctx: dict[str, Any], rid: str) -> dict[str, Any]:
    """J10 Am1 §D3: every `limit` episode's goal_pass set to 0 in both arms; the paired contrast again."""
    left, right = (PRED_SPECS[rid]["left"], PRED_SPECS[rid]["right"]) if rid in PRED_SPECS else \
        (SUPPORT_SPECS[rid]["left"], SUPPORT_SPECS[rid]["right"])
    view = pair_view(ctx, left, right)
    base = {"sensitivity": True, "decision_bearing": False, "cite": "E:321-322; J10 :821-822", **view_frame(view)}
    why = _blocked(ctx, rid, left, right, view)
    if why:
        return {**base, "status": why[0], "reason": why[1]}
    lv = [0.0 if e == LIMIT else v for v, e in zip(view["left_values"], view["left_error"])]
    rv = [0.0 if e == LIMIT else v for v, e in zip(view["right_values"], view["right_error"])]
    zv = dict(view, diffs=[a - b for a, b in zip(lv, rv)], left_values=lv, right_values=rv, variant="limit_as_0")
    est = estimate(ctx, rid + "_limit_as_0", zv)
    return {**base, "status": "ok", "goal_pass": public(est)}


def class_set_sensitivity(ctx: dict[str, Any], views: dict[str, dict[str, Any]], predictions: dict[str, Any],
                          classes: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"decision_bearing": False, "cite": "E:203-204, E:359-362",
                           "cluster": "the entry's sorted involved_classes set; cluster count as found"}
    if classes.get("status") != "ok":
        return {**out, "status": "not_computed", "reason": classes.get("error")}
    out.update(status="ok", n_class_sets_design=classes["n_class_sets_design"], source=classes["source"], rows={})
    for pid in CLASS_SET_ROWS:
        spec = PRED_SPECS[pid]
        view = views[pid]
        if predictions[pid]["status"] != "read":
            out["rows"][pid] = {**view_frame(view), "status": predictions[pid]["status"]}
            continue
        est = estimate(ctx, pid, view, kind="plain" if spec["kind"] == "plain" else "ratio",
                       h=view["left_hstar"] if spec["kind"] == "hstar" else None, threshold_pp=spec["threshold_pp"],
                       direction=A1_RULES[spec["rule"]]["direction"], clustering="class_set")
        out["rows"][pid] = {**view_frame(view), **public(est)}
    return out


def by_fdr(predictions: dict[str, Any], b1: dict[str, Any], supporting: dict[str, Any]) -> dict[str, Any]:
    """E:218-220 via j10_report.am1_by_fdr (:3389, cluster_inference.by_fdr): 13 rows, two-sided p at each row's
    threshold; a row without a p is listed and left out of m; flags only, no verdict changes."""
    entries = []
    for rid, t in BY_ROWS:
        if rid in predictions:
            row = predictions[rid]
            verdict = row["verdict"]
        elif rid in b1:
            row = b1[rid]
            verdict = row.get("reading")
        else:
            row = supporting[rid]
            verdict = None
        gp = row.get("goal_pass") if row.get("status") == "read" else None
        p = gp.get("p_two_sided_at_threshold") if isinstance(gp, dict) else None
        entries.append({"id": rid, "p": p, "threshold_pp": t, "verdict": verdict, "flaggable": rid in BY_FLAGGABLE,
                        "source": f"{row.get('left')} − {row.get('right')}, two-sided p at {t:+.2f} pp"})
    out = am1_by_fdr(entries, ALPHA)
    out["citation"] = "E:218-220 (J10 Am1 §F)"
    out["n_rows_registered"] = len(BY_ROWS)
    if out.get("status") == "ok":  # B1's "holds" is a rejection at -7.00: flag it too (am1_by_fdr flags supported)
        for row, e in zip(out["rows"], [e for e in entries if e["p"] is not None]):
            if e["flaggable"] and e["verdict"] == "holds":
                survives = bool(row["p_by"] <= ALPHA)
                row["survives_by"] = survives
                out["flags"].append({"id": e["id"], "survives_by": survives,
                                     "sentence": (f"{e['id']} holds; " + ("survives" if survives else
                                                                          "does NOT survive")
                                                  + f" Benjamini-Yekutieli across {out['m']} contrasts (adjusted "
                                                    f"p = {row['p_by']:.4f}).")})
    for row in out.get("rows") or []:  # L13: wherever P3's verdict is printed
        if row.get("id") == "P3":
            row["reading_qualifier"] = P3_QUALIFIER
    for f in out.get("flags") or []:
        if f.get("id") == "P3" and isinstance(f.get("sentence"), str) and f["sentence"].startswith("P3 "):
            f["reading_qualifier"] = P3_QUALIFIER
            f["sentence"] = f"P3 ({P3_QUALIFIER}) " + f["sentence"][len("P3 "):]
    return out


def per_turn(ctx: dict[str, Any]) -> dict[str, Any]:
    """Per user turn: the share of checked turns passed, from the final evaluate event's report.turn_valid
    (src/sidekick/environments/bfcl_env.py:588)."""
    out: dict[str, Any] = {"source": "final evaluate event payload.report.turn_valid (bfcl_env.py:588)",
                           "exploratory": True, "arms": {}}
    for stem in ARMS:
        rows = [r for r in ctx["arms"][stem]["rows"].values() if not r["crash"]]
        turns: dict[int, list[int]] = {}
        n_without = 0
        for r in rows:
            tv = r["turn_valid"]
            if tv is None:
                n_without += 1
                continue
            for i, v in enumerate(tv):
                if v is None:
                    continue
                t = turns.setdefault(i, [0, 0])
                t[0] += 1
                t[1] += int(bool(v))
        out["arms"][stem] = {"n_episodes_without_turn_record": n_without,
                             "turns": {str(i): {"n_checked": c, "n_passed": p, "share": round(p / c, 6) if c else None}
                                       for i, (c, p) in sorted(turns.items())}}
    return out


def per_class_set(ctx: dict[str, Any]) -> dict[str, Any]:
    classes = ctx.get("classes")
    if not classes:
        return {"status": "not_computed", "reason": "involved_classes unavailable (see sensitivity.involved_classes)"}
    out: dict[str, Any] = {"status": "ok", "exploratory": True, "arms": {}}
    for stem in ARMS:
        by: dict[str, list[float]] = {}
        for k, r in ctx["arms"][stem]["rows"].items():
            if not r["crash"] and r["goal_pass"] is not None:
                by.setdefault(classes[k[0]], []).append(r["goal_pass"])
        out["arms"][stem] = {c: {"n": len(v), "goal_pass_mean": round(statistics.fmean(v), 6)}
                             for c, v in sorted(by.items())}
    return out


def channel_content(ctx: dict[str, Any]) -> dict[str, Any]:
    """J10 Am1 §C descriptives (j10_report.a1_r2_content :5465-5541, ported to the BFCL channel arms): the share of
    interventions with a fenced code block, median length, and the executor's copy rate of advised code."""
    out: dict[str, Any] = {"label": "DESCRIPTIVE / EXPLORATORY (E:327-328); not decision-bearing",
                           "implementation": "j10_report.a1_r2_content (:5465-5541) with b2_decomposition helpers",
                           "arms": {}}
    try:
        from scripts.analysis import b2_decomposition as b2  # noqa: E402
    except Exception as exc:
        return {**out, "status": "not_computed", "reason": f"b2_decomposition import: {type(exc).__name__}: {exc}"}
    fenced_re = re.compile(A1_R2_FENCED_BLOCK, re.DOTALL)
    python_re = re.compile(A1_R2_PYTHON_BLOCK, re.DOTALL | re.IGNORECASE)
    for stem in CHANNEL_ARMS:
        rows_out: list[dict[str, Any]] = []
        n_missing = n_bad = 0
        eps = {k: r for k, r in ctx["arms"][stem]["rows"].items() if not r["crash"]}
        for k in sorted(eps):
            path = Path(eps[k]["events_path"])
            if not path.is_file():
                n_missing += 1
                continue
            events, bad = b2.read_events(path)
            n_bad += bad
            for i, ev in enumerate(events):
                if ev.get("event_type") != "intervention":
                    continue
                payload = ev.get("payload") or {}
                text = str(payload.get("correction") or "")
                nxt = _a1_r2_next_executor_action(events, i)
                rendered = b2._render_action(nxt.get("payload") or {}) if nxt is not None else None
                target = b2._normalise_ws(rendered) if rendered is not None else None
                cands = [text, *(m.group(0) for m in python_re.finditer(text))]
                rows_out.append({"chars": len(text), "fenced": fenced_re.search(text) is not None,
                                 "copied": target is not None and any(b2._normalise_ws(c) == target for c in cands)})
        chars = [r["chars"] for r in rows_out]
        n_fenced = sum(1 for r in rows_out if r["fenced"])
        blk = {"n_episodes": len(eps), "n_episodes_without_events": n_missing, "n_unparseable_event_lines": n_bad,
               "n_interventions": len(rows_out), "n_fenced_code": n_fenced,
               "share_fenced_code": round(n_fenced / len(rows_out), 6) if rows_out else None,
               "median_chars": statistics.median(chars) if chars else None}
        if stem == "takeover_k5":
            blk["copy_rate"] = None
            blk["copy"] = "not applicable: the planner's action is executed, nothing is advised"
        else:
            n_copied = sum(1 for r in rows_out if r["copied"])
            blk["copy_rate"] = round(n_copied / len(rows_out), 6) if rows_out else None
            blk["copy"] = {"n_copied": n_copied, "definition": "advice (or a ```python block in it) reproduced next"}
        out["arms"][stem] = blk
    out["status"] = "ok"
    return out


def dev_reference() -> dict[str, Any]:
    out: dict[str, Any] = {"label": "registered dev values, in the registered orientation (never negated); L6",
                           "meta": DEV_META, "rows": {}}
    for rid, vals in DEV_REFERENCE.items():
        out["rows"][rid] = dict(vals)
    for rid, vals in DEV_REPORT_ONLY.items():
        out["rows"][rid] = {**vals, "label": "dev report value; not quoted in the prereg"}
    return out


# ---- sentences (L7, L13) --------------------------------------------------------------------------------------
def _num_part(row: dict[str, Any], p_label: str) -> str:
    gp = row.get("goal_pass") or {}
    if not gp or gp.get("status") not in (None, "ok"):
        return ""
    s = f", {_pp_s(gp.get('diff_pp'))} pp, entry 95% CI {_ci_s(gp.get('ci95_entry'))}, {p_label} {_p_s(gp.get('p_registered'))}"
    holm = row.get("holm") or {}
    if holm.get("p_adjusted") is not None:
        s += f" (Holm, m = {holm.get('m')}: {_p_s(holm.get('p_adjusted'))})"
    if gp.get("n_handoff") is not None:
        s += f", over {gp['n_handoff']} handoff pairs (n_h_missing {gp.get('n_h_missing')}, counted as 0)"
    return s


def _extras(report: dict[str, Any], rid: str, row: dict[str, Any]) -> list[str]:
    parts: list[str] = []
    b = row.get("boundary") or {}
    if b.get("fired") and b.get("stable") is False:
        parts.append(f"on the boundary: the Holm-aware verdict differs at seed(s) {b.get('flipping_seeds')} of "
                     f"{b.get('seeds')} (B = {b.get('n_boot')}; E:213-215), so it is neither supported nor not "
                     "supported")
    kx = row.get("key_exclusion") or {}
    if kx.get("differs"):
        parts.append(f"the verdict moves without the {kx.get('n_keys_excluded')} planless keys "
                     f"({kx.get('verdict_all_pairs')} -> {kx.get('verdict_without_keys')}), so it is on the boundary "
                     "(E:295-296)")
    if b.get("flipping_seeds_not_voted"):
        parts.append(f"re-decided with its family when {', '.join(b.get('family_fired_by') or [])} fired the "
                     f"boundary rule, its verdict differs at seed(s) {b['flipping_seeds_not_voted']}; its own bounds "
                     f"are more than {BOUNDARY_WINDOW_PP:.2f} pp from the threshold, so the rule (E:213-215) does not "
                     "fire for it and the verdict stands (disclosed, not voted)")
    note = signflip_note(rid, row.get("verdict_before_boundary", row.get("verdict_before_key_exclusion",
                                                                          row.get("verdict"))), row.get("sign_flip"),
                         (row.get("goal_pass") or {}).get("p_registered"))
    if (row.get("sign_flip") or {}).get("status") == "not_applicable":
        note = None
    if note:
        parts.append(note)
    for f in (report.get("by_fdr") or {}).get("flags") or []:
        if f.get("id") == rid and f.get("survives_by") is False:
            parts.append(f"{f['sentence']} (BY flag, E:220; no verdict changes)")
    parts.extend(_side_disclosures(row))
    return parts


def _side_disclosures(row: dict[str, Any], *, divergent: bool = True) -> list[str]:
    """What every contrast row's sentence carries about its two arms (L8, L10): an ask bound >= 1.00 pp (live arms
    included) and, where a replaying arm is involved, the divergent-key count (0 included)."""
    parts: list[str] = []
    if row.get("ask_bound_reaches_1pp"):
        sides = ", ".join(f"{a} {v:.2f} pp" for a, v in (row.get("ask_bounds_pp") or {}).items())
        parts.append(f"live-answered executor asks bound the arm means at {sides} (E:300-301; no verdict changes)")
    if divergent and (row.get("left") in REPLAYING_ARMS or row.get("right") in REPLAYING_ARMS):
        parts.append(f"{row.get('n_divergent_excluded', 0)} divergent replay keys excluded (cap {DIVERGENCE_CAP}, "
                     "E:297)")
    return parts


def _vw(v: Optional[str]) -> str:
    return VERDICT_WORDS.get(v or "", str(v))


NOT_REPLICATED = "not replicated, never evidence of no effect"


def _d_pair_reading(all_v: Optional[str], h_v: Optional[str], zs: bool, all_id: str = "D1",
                    h_id: str = "D3") -> Optional[str]:
    """The E:169-174 table, only for the outcomes it registers: both supported (E:171), all-pairs supported with
    handoff-only NOT SUPPORTED (E:172), all-pairs not supported (E:173). Any other outcome (on the boundary, not
    read, reversed) draws no joint reading, and the sentence says which member stops it."""
    z = "; E:174 for the zero-shot receiver" if zs else ""

    def no_joint(mid: str, v: Optional[str]) -> str:
        if v == "reversed":
            return (f"{mid} is reversed, a primary finding (E:176-179); the E:169-174 table registers no joint "
                    "reading for a reversal")
        if v == "on_boundary":
            return (f"{mid} is on the boundary, neither supported nor not supported (E:213-215): no joint reading "
                    "from the E:169-174 table")
        return f"{mid} is {_vw(v)}: no joint reading from the E:169-174 table"

    if all_v is None:
        return None
    if all_v == "supported" and h_v == "supported":
        if zs:
            return ("the same reading for the zero-shot receiver (E:174): on BFCL, a later handoff raises the "
                    "zero-shot receiver's quality, and not only through episodes the planner finishes itself")
        return ("on BFCL, a later handoff raises the out-of-domain adapter's quality, and not only through episodes "
                "the planner finishes itself (E:171)")
    if all_v == "supported" and h_v == "not_supported":
        return f"the depth gain is not shown on real handoffs (E:172{z})"
    if all_v == "supported":
        return no_joint(h_id, h_v)
    if all_v == "not_supported":
        return f"the dev depth span does not replicate on BFCL test for this receiver (E:173{z}); {NOT_REPLICATED}"
    return no_joint(all_id, all_v)


def build_sentences(report: dict[str, Any]) -> dict[str, str]:
    """One sentence per decision row, B1 row and supporting reading, carrying what the prereg says must share it:
    the registered reading for the actual outcome (E:123-127, E:169-179), the B1 reading (P3), sign-flip
    disagreement, BY flag, ask bound >= 1 pp, on the boundary, divergent-key count."""
    preds = report.get("predictions") or {}
    b1 = report.get("b1") or {}
    sup = report.get("supporting") or {}
    out: dict[str, str] = {}

    def row_of(rid: str) -> dict[str, Any]:
        return preds.get(rid) or {}

    cf1 = row_of("CF1")
    cf1v = cf1.get("verdict")
    for rid in PRED_ORDER:
        row = row_of(rid)
        if not row:
            continue
        v = row.get("verdict")
        spec = PRED_SPECS[rid]
        p_label = ("two-sided p at 0" if spec["rule"].startswith("positive") else  # bootstrap_pvalue (E:158-159)
                   "p = 2 × share ≤ −7.00 ('greater')" if rid == "P3" else "p = 2 × share ≤ 0 ('greater')")
        head = f"{rid} ({row.get('left')} − {row.get('right')}"
        if rid in ("D3", "D4"):
            head += f", handoff-only Σd·h*/Σh*, h* from {row.get('left')} (the left, deeper arm)"
        elif rid in ("D1", "D2"):
            head += ", all pairs"
        elif rid == "P3":
            head += ", all episodes, margin −7.00 pp"
        head += f", goal_pass, family {spec['family']}): {_vw(v)}"
        if row.get("status") == "read":
            head += _num_part(row, p_label)
        elif row.get("reason"):
            head += f" ({row['reason']})"
        parts: list[str] = []
        if rid == "P6":
            parts.append("P6 is the prediction that actions beat the registered correction-prompt advice "
                         "(E:331-332)")
            core = row.get("verdict_before_boundary", row.get("verdict_before_key_exclusion", v))
            if v == "supported":
                parts.append("J10's H-A1b replicates on BFCL (E:125)")
            elif v == "not_supported":
                parts.append(f"fails to replicate; TGC and CF1 do not rescue it (E:125); {NOT_REPLICATED}")
            elif v == "reversed":
                parts.append("reversed: a primary finding (E:125): the registered correction-prompt advice beats "
                             "actions on BFCL test")
            elif v == "on_boundary":
                parts.append(f"on the boundary (the unperturbed verdict was {_vw(core)}); neither supported nor not "
                             "supported")
            cf1_num = _num_part(cf1, "two-sided p at 0") if cf1.get("status") == "read" else \
                (f" ({cf1.get('reason')})" if cf1.get("reason") else "")
            parts.append(f"CF1 (advise_k5_neutral − advise_k5_fullctx), in the same paragraph: {_vw(cf1v)}{cf1_num}")
            if cf1v == "supported":
                parts.append('CF1 is supported, so P6 is reported only as "actions beat correction-prompt advice" '
                             "(E:127)")
        elif rid == "P3":
            parts.append(P3_QUALIFIER)
            if v == "supported":
                parts.append("non-inferior at −7.00 pp to the planner acting alone (E:126)")
            elif v == "not_supported":
                parts.append("fails non-inferiority; P6 and CF1 do not depend on P3 (E:126)")
            elif v == "on_boundary":
                parts.append("on the boundary: neither supported nor not supported; no reversal is registered")
            bz = b1.get("B1_zs") or {}
            gz = bz.get("goal_pass") or {}
            parts.append(f"B1 zs (handoff-only companion, h* from prefix_zs_m6): {_vw(bz.get('reading')) if bz.get('reading') else bz.get('status')}"
                         + (f", {_pp_s(gz.get('diff_pp'))} pp {_ci_s(gz.get('ci95_entry'))} over {gz.get('n_handoff')} "
                            f"handoff pairs (n_h_missing {gz.get('n_h_missing')})" if gz else "")
                         + "; it never changes P3 (E:141)")
        elif rid == "CF1":
            if v == "supported":
                parts.append('P6 is reported only as "actions beat correction-prompt advice" (E:127)')
            elif v == "not_supported":
                parts.append("the prompt effect does not replicate; P6 carries §8's qualification (E:127); not "
                             "replicated, never evidence of no effect")
            elif v == "reversed":
                parts.append("reversed: a primary finding (E:127)")
            elif v == "not_run":
                parts.append("advise_k5_neutral could not complete 300 pairs; P6 and P3 stand (E:304-305)")
            elif v == "on_boundary":
                parts.append("on the boundary: neither supported nor not supported")
            parts.append("printed beside P6; it has no bearing on whether P6 or P3 is complete (E:133)")
        else:  # D1-D4
            zs = rid in ("D2", "D4")
            all_id, h_id = ("D2", "D4") if zs else ("D1", "D3")
            reading = _d_pair_reading(row_of(all_id).get("verdict"), row_of(h_id).get("verdict"), zs, all_id, h_id)
            if not zs:
                parts.append(f'bplus is "{BPLUS_DESC}" (E:181)')
            if v == "not_supported":
                if NOT_REPLICATED not in (reading or ""):
                    parts.append(NOT_REPLICATED)
            elif v == "reversed":
                rev = row.get("reversal") or {}
                parts.append(f"reversed: a primary finding (upper bound below 0; direction 'less' p at 0, "
                             f"2 × share ≥ 0, = {_p_s(rev.get('p_less'))}, unadjusted; E:176-179)")
            elif v in ("not_read", "not_run"):
                parts.append("its p counts as 1 in Holm, which stays at m = 4 (E:305-307)")
            elif v == "on_boundary":
                parts.append("on the boundary: neither supported nor not supported")
            if rid == all_id:  # E:334, B38: an all-episode depth number is printed with its h* companion
                hrow = row_of(h_id)
                gh = hrow.get("goal_pass") or {}
                hv = hrow.get("verdict")
                comp = (f"printed with its h* companion {h_id} (handoff-only Σd·h*/Σh*, h* from "
                        f"{hrow.get('left') or PRED_SPECS[h_id]['left']}): {_vw(hv)}")
                if hrow.get("status") == "read" and gh.get("status") in (None, "ok") and gh.get("diff_pp") is not None:
                    comp += (f", {_pp_s(gh.get('diff_pp'))} pp {_ci_s(gh.get('ci95_entry'))} over "
                             f"{gh.get('n_handoff')} handoff pairs (n_h_missing {gh.get('n_h_missing')}, counted as 0)")
                elif hrow.get("reason"):
                    comp += f" ({hrow['reason']})"
                parts.append(comp + " (E:334)")
            if reading:
                parts.append(f"{all_id} with {h_id}: {reading}")
        parts.extend(_extras(report, rid, row))
        out[rid] = head + ("; " + "; ".join(parts) if parts else "") + "."
    for rid in ("B1_zs", "B1_bplus"):
        row = b1.get(rid) or {}
        if not row:
            continue
        gp = row.get("goal_pass") or {}
        head = (f"{rid} ({row.get('left')} − {row.get('right')}, handoff-only Σd·h*/Σh*, h* from {row.get('left')}"
                f", not decision-bearing): {_vw(row.get('reading')) if row.get('reading') else row.get('status')} at "
                "−7.00 pp")
        if gp:
            head += (f", {_pp_s(gp.get('diff_pp'))} pp {_ci_s(gp.get('ci95_entry'))} over {gp.get('n_handoff')} "
                     f"handoff pairs (n_h_missing {gp.get('n_h_missing')}, counted as 0)")
        elif row.get("reason"):
            head += f" ({row['reason']})"
        parts = ["never changes P3 (E:141)"]
        if rid == "B1_bplus":
            parts.insert(0, f'bplus is "{BPLUS_DESC}" (E:335)')
            s3 = sup.get("S3") or {}
            g3 = s3.get("goal_pass") or {}
            parts.append(f"printed with S3 (prefix_bplus_m6 − planner_alone_cap81 at −7.00, supporting): "
                         + (f"{_pp_s(g3.get('diff_pp'))} pp {_ci_s(g3.get('ci95_entry'))}, "
                            f"{s3.get('reading_at_minus_7')}" if g3 else str(s3.get("status"))))
        bl = row.get("boundary") or {}
        if row.get("reading") == "on_boundary":
            parts.append(f"on the boundary: the reading differs across the seeds {bl.get('seeds') or ''} (E:140)")
        for f in (report.get("by_fdr") or {}).get("flags") or []:
            if f.get("id") == rid and f.get("survives_by") is False:
                parts.append(f"{f['sentence']} (BY flag, E:220)")
        if row.get("ask_bound_reaches_1pp"):
            sides = ", ".join(f"{a} {v:.2f} pp" for a, v in (row.get("ask_bounds_pp") or {}).items())
            parts.append(f"live-answered executor asks bound the arm means at {sides} (E:300-301)")
        parts.append(f"{row.get('n_divergent_excluded', 0)} divergent replay keys excluded (cap {DIVERGENCE_CAP})")
        out[rid] = head + "; " + "; ".join(parts) + "."
    cf3 = sup.get("CF3") or {}
    if cf3:  # the J10 Am1 §C reading (:795-801); the phrase it forbids stays in reading_rule, never in the sentence
        g = cf3.get("goal_pass") or {}
        parts = [(f"{_pp_s(g.get('diff_pp'))} pp {_ci_s(g.get('ci95_entry'))}; {cf3.get('reading')} (J10 :795-801)"
                  if g else f"{cf3.get('status')} ({cf3.get('reason')})")]
        parts.extend(_side_disclosures(cf3))
        out["CF3"] = "CF3 (takeover_k5 − advise_k5_neutral, two-sided, unadjusted, supporting): " + "; ".join(parts) \
            + "."
    out["pooling"] = "BFCL is reported beside J10, never pooled (E:336)."
    return out


# ---- markdown summary ------------------------------------------------------------------------------------------
def render_markdown(report: dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [f"# BFCL test read ({meta['status']})", "",
             f"- prereg: {meta['prereg']}; script {meta['script']['git_sha']} (sha256 {meta['script']['sha256']})",
             f"- entry-cluster bootstrap n_boot={meta['n_boot']} seed={meta['seed']}; boundary seeds "
             f"{meta['pool_seeds']}; 200k reported, not voted; n_clusters={meta['n_clusters']}",
             f"- {meta['pooling']}", ""]
    if meta["status"] == "not_run":
        lines += [report["sentences"]["headline"], "", "| arm | non-crash | crash | divergent | missing | complete |",
                  "|---|---|---|---|---|---|"]
        for stem, a in report["arms"].items():
            lines.append(f"| {stem} | {a['n_noncrash']} | {a['n_crash']} | {a['n_divergent']} | {a['n_missing']} | "
                         f"{a['complete']} |")
        return "\n".join(lines) + "\n"
    s = report["sentences"]
    lines += ["## Registered predictions", ""]
    for rid in ("P6", "P3", "CF1", "D1", "D2"):
        lines += [f"- {s[rid]}"]
    lines += ["", "### m4 rows (EXPLORATORY, between the D rows)", ""]
    for rid, row in report["m4_rows"].items():
        a, h = row["all_pairs"].get("goal_pass") or {}, row["hstar_from_left"].get("goal_pass") or {}
        lines.append(f"- {rid}: all pairs {_pp_s(a.get('diff_pp'))} {_ci_s(a.get('ci95_entry'))}; h* from left "
                     f"{_pp_s(h.get('diff_pp'))} {_ci_s(h.get('ci95_entry'))}")
    lines += [""]
    for rid in ("D3", "D4"):
        lines += [f"- {s[rid]}"]
    lines += ["", "## Companions and supporting rows", ""]
    for rid in ("B1_zs", "B1_bplus", "CF3"):
        if rid in s:
            lines.append(f"- {s[rid]}")
    for rid, row in report["supporting"].items():
        g = row.get("goal_pass") or {}
        asks = "".join(f"; {x}" for x in _side_disclosures(row, divergent=False))  # L8: bound >= 1 pp in the row
        lines.append(f"- {rid} ({row['left']} − {row['right']}): {_pp_s(g.get('diff_pp'))} pp "
                     f"{_ci_s(g.get('ci95_entry'))}, two-sided p at threshold {_p_s(g.get('p_two_sided_at_threshold'))}"
                     f"; n_pairs {row['n_pairs']}, divergent excluded {row['n_divergent_excluded']}; {row['status']}"
                     f"{asks}")
    lines += ["", "## Arms", "", "| arm | n_pairs | crash | divergent | gp | succ | limit | force-quit | asks bound pp "
              "| live/ep | attr/ep |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for stem, a in report["arms"].items():
        asks = report["executor_asks"]["per_arm"][stem]["bound_pp"]
        c = a["cost"]
        lines.append(f"| {stem} | {a['n_pairs']} | {a['n_crash']} | {a['n_divergent']} | {a['goal_pass_mean']} | "
                     f"{a['success_mean']} | {a['limit_rate']} | {a['force_quit_count']} | {asks} | "
                     f"{c['calls_live_mean']} | {c['calls_attributed_mean']} |")
    pl = report["planless_keys"]
    lines += ["", f"Planless keys: {pl.get('n')} ({pl.get('status')}); BY-FDR m = {report['by_fdr'].get('m')}, "
                  f"not in family: {report['by_fdr'].get('not_in_family')}."]
    return "\n".join(lines) + "\n"


# ---- main ------------------------------------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--config-dir", type=Path, default=DEFAULT_CONFIG_DIR)
    ap.add_argument("--refill-dir", type=Path, default=DEFAULT_REFILL_DIR)
    ap.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--confirm", default=None, help=f"must equal {CONFIRM_TOKEN}")
    ap.add_argument("--disclosed-rerun", default=None, metavar="REASON",
                    help="a post-read fix: re-run with both sets reported (E:309-310)")
    ap.add_argument("--cannot-complete", default="", metavar="ARM[,ARM...]",
                    help="the arms judged unable to complete 300 pairs (E:303-307); required, naming exactly those "
                         "arms, before a not-run report or a read with an incomplete arm")
    args = ap.parse_args(argv)
    try:
        prereg = guard_prereg(args.repo_root)  # G1
        guard_confirm(args.confirm)  # G2
        rerun = guard_out(args.out, args.results_root, args.disclosed_rerun, args.repo_root)  # G3
        # The registered S8 constants, fixed here (no flag changes them).
        report = build_report(args.results_root, args.config_dir, args.refill_dir, args.split_file, args.repo_root,
                              n_boot=N_BOOT, seed=SEED, pool_seeds=POOL_SEEDS, big_n=BIG_N, big_seed=BIG_SEED,
                              n_test_entries=N_TEST_ENTRIES,
                              cannot_complete=[s for s in args.cannot_complete.split(",") if s.strip()])
    except GuardError as exc:
        print(f"REFUSED ({exc.guard}): {exc}", file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        return 1
    try:
        report["meta"]["prereg_stamp"] = prereg
        report["meta"]["confirm"] = CONFIRM_TOKEN
        report["meta"]["out"] = str(args.out)
        report["meta"]["disclosed_rerun"] = rerun
        report["meta"]["read_ledger"] = str(Path(args.repo_root) / READ_LEDGER_REL)
        text = json.dumps(report, indent=2, default=str) + "\n"
        ledger = Path(args.repo_root) / READ_LEDGER_REL
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:  # the read is recorded before its report is written
            fh.write(json.dumps({"out": str(Path(os.path.realpath(args.out))), "status": report["meta"]["status"],
                                 "report_sha256": sha256_bytes(text.encode("utf-8")),
                                 "generated_at": report["meta"]["generated_at"],
                                 "script_sha256": report["meta"]["script"]["sha256"],
                                 "disclosed_rerun": None if rerun is None else rerun["reason"]}) + "\n")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        md_path(args.out).write_text(render_markdown(report), encoding="utf-8")
    except Exception:
        traceback.print_exc()
        return 1
    print(render_markdown(report))
    print(f"wrote {args.out} and {md_path(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
