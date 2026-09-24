# Plan: a defensible top-venue result, from the Amendment 1 freeze (2026-09-24)

Written 2026-09-24, right after J10 Amendment 1 was frozen (commit 138c285). This plan extends
`docs/plan_review_fixes_20260923.md`, whose fix register (§1) and R-item ids it reuses. It supersedes that
plan's §4 order of work from S3 onward.

The user's request: *"plan the full fixes needed and what jobs to run to set up for a full defensible top venue
tier result"*.

---

## 0. State at writing (checked 2026-09-24)

- **J10 registration.**
  - A1 was frozen at r4 (142e947). Amendment 1 was appended and frozen at 138c285: 217 lines added, 0 removed,
    one `**Status**` line.
  - The code computing every Amendment 1 item is at dbc52e9. The full unit suite passes: **1206**.
- **Test contact: none.** The only `j10_*` campaigns are the 13 `_dryrun` campaigns (dev, 3 tasks × 2 seeds).
  `test_normal` is unread, and `test_challenge` is sealed (standing rule).
- **LP-2 (Qwen3.8-27B-FP8 as the planner, dev).**
  - All 10 arms have 114 episodes.
  - `lp2_prefix_zs_m11_v2` and `lp2_prefix_bplus_m11_v2` have 2 crashed episodes each. They are being refilled
    in PBS 25832832.
  - `lp_report.py` has not run, so no LP-2 aggregate has been read.
- **Paper A.**
  - It is dev only: `paper/preprint_dev_20260923.md`, 14,068 words, 8,731 before the appendices.
  - The adversarial review's verdict: a workshop, Findings or TMLR paper after fixes; **rejected at a main
    track as it stands** (`docs/review_paperA_adversarial_20260923.md:13-16`).
- **Paper B** is the top-venue paper. It targets the ICML 2027 / ACL 2027 main track
  (`docs/plan_two_papers_20260923.md:214`).

## 1. What the top-venue paper must be able to defend

**Claim, as the design allows it to be stated.** On held-out tasks, and at a matched trigger:
- how a hosted planner's help is delivered to a small local executor decides whether the help lands;
- the decomposition says whether it is the planner's concrete code, or its execution, that carries the gain;
- handing off after an action prefix is non-inferior to the planner acting alone, **measured on episodes that
  actually hand off**;
- the pattern is tested in a second environment and with a second, open-weight planner.

**Outcome-robustness is the design goal, not a hope.** Every registered item has a reading fixed before its
data:
- J10's P1–P6 are fixed in A1 §5, and CF1–CF3, B1 and D in Amendment 1.
- So a null or reversed J10 result is still a paper: a registered held-out test with a decomposition.
- The plan below never gates a replication on a positive result. Wave E runs whatever J10 shows; this reverses
  `plan_two_papers:196-204`, which gated it on J10's P1.

## 2. Gap register: what a main-track reviewer would still hold, and the fix

Kind: **T** = registered on held-out data; **D** = dev, exploratory, reported with intervals; **P** = paper
text only.

| # | Objection | Now | Fix | Kind | Jobs (§4) |
|---|---|---|---|---|---|
| G1 | One environment | AppWorld only | Wave E, BFCL `multi_turn_base`: its own dev → prereg → test | T | E0–E4 |
| G2 | One planner on held-out data | LP-1 fails its gate; LP-2 dev done, unread | LP-2 read; **J11**, LP-2 on `test_normal`, if LP-2 is informative (decision DA) | D → T | L1, L2, J11-* |
| G3 | The advice arm is a strawman (terse correction prompt) | CF family on test (Am1 §C); nothing on dev at k = 1 | Dev neutral k = 1 (R2.4) | T + D | W3, W4 |
| | | | Dev structured-direction advice, ManagerWorker/Minions style (D2, now **recommended**) | | |
| G4 | Weak ceiling: 0.57–0.68 TGC in a minimal harness, against 85.1 % with a scaffold | Disclosed only | Dev planner-alone at high reasoning effort (D3, now **recommended**) | D + P | W4 |
| | | | Rename "ceiling" to "the planner alone in the same harness" | | |
| G5 | Depth gain is mostly the planner finishing (100/171 never hand off at m = 11) | Am1 §B registers handoff-only NI, decomposition and chord on test | Dev companions in j17 (R1.1–R1.4) | T + D | S4 |
| G6 | P6's gap sits in step-limit failures | Am1 §D registers limit rate, split and limit-as-0 | Dev limit decomposition in j17 (R2.2) | T + D | S4 |
| G7 | H2 rule breached (P1 is not budget-matched) | Am1 §E constrains how P1 is described | Paper rewrite (R3.1, R3.2) | T + P | S5 |
| G8 | Novelty against Ganz 2608.24358, Minions, ManagerWorker | Mis-described or missing | Positioning (R6.1–R6.4) | P + D | S4, S5, W4 |
| | | | Ganz-comparable metrics (R1.3) | | |
| | | | The D2 arm as the prior-work baseline | | |
| G9 | `goal_pass` gives partial credit for doing nothing (0.2481) | TGC reported in places | No-op dev arm (R7.1); TGC and SGC beside every headline | D + P | S4 |
| G10 | Registration outcomes omitted; thin multiplicity control; about 86 exploratory rows against 32 registered | `by_fdr` is committed; Am1 §F on test | Registration-outcome table (R4.1); BY-FDR over dev intervals (R4.3); census (R4.4) | P + D | S4, S5 |
| G11 | Second executor family on dev only; tailored Qwen adapter never emits COMPLETE | QWEN-* rows (dev) | Report as dev-exploratory with intervals, TGC leading. **No test arm**: A1 adds none, and the adapter defect makes a test arm uninformative | D | none |
| G12 | Cost realism | Calls and tokens | Dollars and calls with intervals (R1.4); latency from existing event timestamps | D | S4 |
| G13 | Reproducibility: proprietary planner, deprecation risk | Code and configs in repo | LP-2 open-weight replication (G2); release plan: code, configs, prompts, dev episodes | P | S5 |
| G14 | Length and format | 14,068 words | Main text ≈ 7,300 words (R8.1), then to venue format | P | S5, B3 |
| G15 | Privacy motivation not delivered | Stated | Qualify it (R8.2): the planner sees the task and the first m observations | P | S5 |

Already resolved in the J10 registration: R1.5, R2.5, R3.3, R5.5 and R8.5 (Am1 §B, §C, §E, §B and §G), and
R4.3's code (`cluster_inference.by_fdr`).

## 3. Registration map: what must be frozen before which data

| Data | Registration | Status |
|---|---|---|
| `test_normal`, luna arms 1–12 (J10) | A1 + Amendment 1 | **FROZEN** (142e947, 138c285) |
| `test_normal`, LP-2 planner arms (J11) | New prereg `docs/prereg_j11_lp2_test_*.md` | Only if DA = yes. It **must freeze before the first J10 submission**: freezing first keeps J11 blind to every `test_normal` outcome, including the limit counts J10's tally prints |
| BFCL dev | Short dev prereg: split, spike gates, depth grid | Written after spikes a–c, before E1 |
| BFCL test | E-prereg with predictions mirroring P6, CF1, P3 + B1; power from BFCL dev | Frozen after BFCL dev, before any BFCL test episode |
| `test_challenge` | none | Sealed (standing rule). Not proposed |

## 4. Jobs, in order

Every hosted arm is resubmitted until it is complete. The quota window is about 5,000 calls and invisible to
a batch job (A1:617-631).
- **Completeness.** An arm is complete only at its registered count of non-crashed pairs, checked with `jq`.
  It is never judged from an exit code.
- **Crash.** A crash is `error_type == "crash"` and nothing else.
- **Resources.** Compute goes through `qsub` or `hpc`, never the login node.
- **RPID.** Every job currently runs without an RPID ("allowed during the transition period"). Once the user
  supplies an RPID, add `-P <RPID>` to each line below.

### Phase 0: now, zero hosted calls

| id | Job | Command / owner | Accept when |
|---|---|---|---|
| L1 | LP-2 refill of 4 crashed episodes | PBS **25832832** (submitted): `qsub -l select=1:ncpus=12:ngpus=2:gpu_id=H100:mem=96gb -v "ARMS=lp2_prefix_zs_m11 lp2_prefix_bplus_m11" scripts/pbs/lp_live.pbs` | Both arms 114 non-crashed, 0 crash |
| L2 | LP-2 read | `hpc` → `scripts/analysis/lp_report.py` (default: both planners, P8 and P27; LP Amendment 4 read path) | Report written; ledger LP-04+ rows; **DA decided from the P27 gate and L1** |
| G0 | Gate check on the frozen file | `hpc` → pytest `test_j10_arm_pbs.py`, `test_j10_report.py`, `test_j10_configs.py` | **Done: 191 passed** against the committed, amended A1 (includes the wrapper selftest) |
| J11-0 | *(if DA = yes)* J11 prereg + configs | Claude: `configs/j11_*` from the `lp2_*` configs; `test_normal` support in `lp_live.pbs`, or a J11 wrapper with j10_arm.pbs's gates; power from LP-2 dev (`am1_power.py` pattern); tests | The user freezes J11 |
| | *J11 arms* | The LP arms needed for L1–L5: C, T, A (k10), A1 (k1), M^bplus_{6,11}, M^zs_{6,11}. E is J10's arm 1b | |
| | *Estimate* | 1–2 days of work; J10 waits for it | |

### Phase 1: J10 hosted arms (A1 §9 order), zero luna workers in these windows

Common variables: `SPLIT=test_normal,J10_CONFIRM=A1_FROZEN,EXPECTED_CODEX_VERSION=0.153.4`.
- **Before each submission:** check the quota reset with a cheap interactive codex call, and record it
  (A1:630-631).
- **Check after every arm:** 336 non-crashed pairs.
- **Additional check after arm 3:** at most 16 planless episodes, or no replay arm starts (A1 §4.2).

| Window | Arm(s) | Command | Hosted calls |
|---|---|---|---|
| W1 (+ spill) | 3 `planner_alone_cap81` | `qsub -l select=1:ncpus=12:mem=64gb -v CFG=configs/j10_planner_alone_cap81.yaml,<common> scripts/pbs/j10_arm.pbs` | 5,830 |
| W2 | 8 `advise_k1_fullctx` | `qsub -v CFG=configs/j10_advise_k1_fullctx.yaml,<common> scripts/pbs/j10_arm.pbs` | 6,391 |
| W3 | 9 `advise_k10_fullctx`, then 10 `takeover_k10` | same form | 1,607 |
| W3 | 11 `show_k10`, then 12 `advise_k10_neutral` (abandoned only as a pair) | same form | ≤ 1,607 |
| W3/W4 | Dev neutral advice at k = 1 (R2.4), `configs/dev_advise_neutral_fixed_k_1_fullctx.yaml`, via `hj12_live.pbs` with `MAX_PLANNER_CALLS=2700` | build first (S4) | ≈ 2,170 |
| W4 | Dev structured-direction advice at k10 (D2) | new prompt style; config plus `planner.correct_prompt` value; dev only | ≈ 300 |
| W4 | Dev planner-alone at high reasoning effort (D3) | `hj13_planner_alone_cap81` with `reasoning_effort: high`; dev only | ≈ 1,700 |
| after W3 | GPU arms 1, 1b, 2, 4, 5, 6, 7 | the same form, 7 jobs, parallel on H100 (default header). Arm 2 `sft_plan` is hosted-checked but budgeted at 0 | 0 (+ Am1 §I asks) |
| after W3 | *(if J11)* J11 arms | GPU only, 2 × H100 each, parallel with the J10 GPU arms | 0 |
| then | Cost report | `hpc` → `j12_cost_axes.py`, with `--arm` for arms 2, 3, 4–7, 8 and P2's arms, and `--packet-source` = arm 3's campaign (its default is hj1b, which is wrong here) | 0 |
| then | **J10 read** | `hpc` → `j10_report.py --split test_normal --confirm-heldout-test-split --arm <13 × LABEL=DIR> --cost-report <above> --out campaign/results/j10_a1_test_normal.report.json` | 0 |

**Luna total for Phase 1:** ≤ 15,627 (J10) + ≈ 4,170 (dev) ≈ **19.8k**, about four windows.

### Phase 1, in parallel: zero hosted calls

| id | Job | Owner | Accept when |
|---|---|---|---|
| S4a | `scripts/analysis/j17_review_fixes.py` + tests (dev only; refuses held-out paths) | Claude | Fixture tests pass; CPU job via `hpc` writes the report |
| | *Covers:* pooled cap-81 handoff-only curve and chord, both clusterings; Ganz metrics; cost shares; D0 limit decomposition; DEC-06 content stats; TGC and SGC columns; BY-FDR over the paper's dev intervals; census | | |
| S4b | No-op dev arm `configs/dev_noop_complete.yaml` (MockExecutor script `["COMPLETE"]`, CPU) | Claude | 114 episodes; floor recorded as NOOP-01 |
| S4c | Harden `preprint_number_audit.sh` (R7.8) + `tests/unit/test_number_audit.py` | Claude | Tests pass; audit exit 0 on Paper A v2 |
| S4d | Ledger rows | Claude | A10 corrections to QWEN-05 and NARR-04 |
| | *New row ids:* HO-\*, CHORD-\*, GANZ-\*, LIM-\*, DEC-06, NOOP-01, FDR-01, NEUTRAL-K1-\*, D2-\*, CEILHI-\*, LP-04+ | | |
| S5 | Paper A v2: every R-item in §2 marked P; ≈ 7,300 words; must-cites re-verified by WebFetch | Opus subagent per section (ledger rows pasted in); Claude integrates | Audit exit 0; the three reviewers re-run read-only; every R-item cites the line that resolves it |
| S6 | Paper A v2 to arXiv (**DD**) | the user | Timestamped before J10 lands |
| E0 | Wave E build: BFCL adapter (≈ 800–950 LOC), `make_env` branch, loader, loop break on `last_obs.done` + regression test (`docs/second_env_scoping_20260923.md:31-39`) | Opus subagents (Cursor is out of usage until about 2026-10-03) | Unit tests pass |
| E1 | Spikes (0 hosted) | CPU/GPU via `qsub` | All three pass |
| | *(a)* ground truth replays 200/200 with 100 % hash agreement | | |
| | *(b)* `executor_alone` ≤ 50 % | | |
| | *(c)* deepest m hands off in ≥ 70 % of entries | | |
| | *Fallbacks* if they fail: τ²-bench telecom, then WorkBench | | |
| F1 | Figures F6 and F7 (task #18) | Claude | Rendered from report keys only |

### Phase 2: second environment, hosted, after J10's hosted arms (whatever J10 shows)

| id | Job | Hosted calls |
|---|---|---|
| E2 | BFCL dev gate (E1 in the scoping doc) | ≈ 2,100 |
| E3 | BFCL dev lean design: ceiling, takeover and advise (correction and neutral), prefix grid from spike (c) | part of ≈ 5,050 (lean) |
| E-prereg | Frozen after E3, before any BFCL test episode | 0 |
| | *Predictions:* P6, CF1, and P3 with its B1 companion, mirrored, with power from BFCL dev | |
| E4 | BFCL test arms, then the registered read | rest of ≈ 5,050; ≈ 8,000 for the full design |

### Phase 3: Paper B

| id | Job | Owner |
|---|---|---|
| B1 | Ledger J10-\*, J11-\* (if run), BFCL-\* rows from the report keys | Claude |
| B2 | Paper B draft | Opus subagents per section; Claude integrates and owns the headline |
| | *Structure:* dev exploration (Paper A v2, condensed) → registered held-out test (J10 + Am1) → second planner → second environment → limits | |
| B3 | Adversarial regression review (three reviewers, as for Paper A); hardened audit exit 0; venue format | Claude + Opus |

## 5. Budget

- **Hosted luna.** Every call comes from the subscription the user approved.
  - J10: ≤ 15,627.
  - Dev (neutral k = 1, D2, D3): ≈ 4,170.
  - BFCL: ≈ 7,150 (lean) to ≈ 10,100 (full).
  - **Total:** ≈ 27k–30k calls, about 6–7 windows.
- **GPU.**
  - J10 GPU arms: 7 × 336 episodes.
  - J11, if run: about 8 arms × 336 episodes on 2 × H100 each. That is ≈ 3× the LP-2 dev jobs [INFERRED from
    336 vs 114 episodes per arm]; measure it from their walltime before sizing.
  - BFCL: ≈ 2,000 executor episodes (`docs/second_env_scoping_20260923.md:178`).
- **CPU.** Every report, the cost axes and the test suites run via `hpc`.

## 6. Decisions for the user (defaults apply unless the user says otherwise)

- **DA. J11 before J10?**
  - *Default:* hold J10's first submission until the LP-2 read (L2, hours away).
  - *Case 1:* if the P27 gate passes **and** L1 (T − A > 0) holds on dev, build and freeze J11 first. J10
    starts 1–2 days later, and "stable across planner strength" becomes a held-out claim.
  - *Case 2:* otherwise J10 starts at once, and planner strength stays dev-exploratory.
  - *Alternative the user may choose:* start J10 now, and read only crash counts from J10 until J11 freezes.
    That is weaker, because the wrapper's tally prints full `error_type` distributions to the log.
- **DB. Dev arms D2 (structured-direction advice, ≈ 300 calls) and D3 (high-effort ceiling, ≈ 1,700 calls).**
  - *Default:* **run both.** The 2026-09-23 plan skipped them.
  - At a main track, they answer the two objections most likely to be raised: the advice baseline and the
    ceiling.
- **DC. Wave E.**
  - *Default:* BFCL `multi_turn_base`, lean design. The build starts now.
  - Its hosted runs follow J10's hosted arms, and they run whatever J10 shows.
- **DD. Paper A venue.**
  - *Default:* arXiv, plus at most a **non-archival** workshop.
  - An archival Findings paper would make Paper B's dev material prior publication.
- **DE. Paper B target.**
  - *Default:* ICML 2027 main track; the deadline is usually late January [INFERRED; check the CFP].
  - The fallback is NeurIPS 2027 (May).
  - ICLR 2027's deadline is too close for J10 and BFCL.
- **DF. RPID.** Every job currently runs as ERR-NORPID, allowed only during the transition period. The user
  needs to supply the project code before the transition ends.

## 7. Timeline (judgement)

| When | What |
|---|---|
| Sep 24–26 | L1–L2, the LP-2 read, DA. J11 built and frozen if chosen. J10 W1 (arm 3) starts. S4 starts |
| Sep 27 – Oct 8 | J10 windows W2–W4 and the dev arms. S4 done. Paper A v2 and arXiv (S5–S6). Wave E build and spikes (E0–E1) |
| Oct 8–15 | J10 GPU arms, J11 arms, the cost report and the **J10 read**. BFCL dev (E2–E3) |
| Oct 15–31 | BFCL prereg frozen, BFCL test (E4). Ledger B1 |
| Nov | Paper B draft (B2) and the regression review (B3) |
| Dec – Jan | Slack for reruns, a fallback environment, or extra dev probes a reviewer might ask for; submission |

## 8. Risks and what is already in place

- **Quota or deprecation of `gpt-5.6-luna`.**
  - J10's hosted arms run first.
  - LP-2 and J11 give an open-weight replication that survives a deprecation.
  - The codex version is pinned to 0.153.4.
- **More than 16 of arm 3's episodes have no plan.** No replay arm starts. Diagnose under A1 §8 before
  anything else.
- **Executor asks in the replay arms.** Amendment 1 §I fixes the handling: kept, counted, bounded.
  - A smoke-gate stop for that reason alone is resubmitted unchanged.
  - The final gate's non-zero exit is recorded, not treated as a failed arm.
- **A null or reversed J10 result.** The readings are pre-fixed (A1 §5; Am1 §B–§D). The paper reports it as
  registered; nothing is re-analysed to rescue it.
- **BFCL spikes fail.** The fallbacks are τ²-bench telecom solo, then WorkBench. The spikes cost 0 hosted
  calls, so failing costs days, not quota.
- **Short BFCL episodes compress the depth range** (a mean of 7.8 calls in 15 entries). Spike (c) sets the
  grid before any hosted call.
- **Worker capacity.** Cursor is out of usage until about 2026-10-03, and Cline is unstable. Code units go to
  Claude or Opus subagents, and hosted arms never share a window with luna workers.

## 9. On approval, in this order

1. Finish L1 and L2. Decide DA from the LP-2 report.
2. Start S4 (j17, no-op arm, audit hardening) and E0 (BFCL build), both with zero hosted calls.
3. If DA leads to J11, build and freeze J11. Otherwise submit J10 arm 3 (W1).
4. Continue through Phase 1 window by window, verifying the count and `error_type` of every arm.
