# Plan: resolve every finding of the adversarial review before the J10 test read

Written 2026-09-23 ~19:20. It supersedes the 07:30 job-set plan, which is already committed as
`docs/plan_two_papers_20260923.md` (its Waves A, B and D1 have landed and D2/LP-2 is running).
Worktree `plan-2026-09-15`, HEAD `968fd7b`.

## Context

The user asked for an adversarial review of the paper, then: *"from the adversarial review confirm all the
fixes needed and plan in detail how to resolve all of them"*.

The review is `docs/review_paperA_adversarial_20260923.md` (968fd7b). It used three Opus reviewers plus Claude,
and Claude re-checked every load-bearing count against the files. Its verdict:
- Paper A (dev only) is a workshop, Findings or TMLR paper after fixes.
- It would be rejected at a top-venue main track as it stands.
- **J10 as frozen would not fix its central flaws.** P6 tests "takeover beats *terse correction* advice" as built.
  P1 repeats a comparison that breaks the H2 prereg's own P4 rule. Nothing in A1 separates "the planner
  finished the task" from a real handoff.

State of play:
- A1 is FROZEN (142e947).
- The J10 dev dry run is clean on **13/13 arms**: 6/6 non-crashed each, codex 0.153.4 on every hosted arm, and
  every replay sourced from `_dryrun`.
- The `test_normal` read is **on hold**. No `j10_*` test campaign exists.
- LP-2 is running (25748167 live, 25748168 replay; 0 crashes).

Hard constraints this plan respects:
- **A1 edits.** A1 can only grow by appending below its end marker (A1:679). The appended text must **not** add
  a second line starting `**Status**` (the `j10_arm.pbs:239-240` gate demands exactly one). Appending shifts no
  `j10_report.py` citation (the highest cited line is 576).
- **No new arms.** A1 says "No arm is added after freeze" (A1:548). New hosted comparisons are dev-only.
- **No test contact** until Amendment 1 is committed and the user has frozen it.
- **Files that stay untouched:**
  - `test_challenge` is never read;
  - nothing under `/scratch/.../results/` is edited by hand;
  - frozen preregs are append-only;
  - the A1-cited file `campaign/results/j10_a1_registered_dev_basis_20260924.report.json` is **not renamed**
    (A1 and the tests cite it).
- **Division of labour.** Claude writes the amendment and small code. Opus subagents take the paper-section
  rewrites (ledger rows pasted into their briefs). Luna calls are for research arms only. Compute goes through
  `hpc` / `qsub`, never on aquarius01.

---

## 1. Fix register: every finding, its fix, and where it lands

Status column: ✔ = verified by Claude against files; (r) = reviewer-reported and re-checked before use.

### F1 (FATAL): the depth result is mostly the planner finishing
At m = 11, 100/171 episodes never hand off; the registered handoff-only rule and chord test are missing; Ganz
et al. already report the downshift-timing effect.

| id | fix | where / reuse |
|---|---|---|
| R1.1 ✔ | Put handoff-only and silenced numbers **beside every pooled depth and NI number**: abstract, §5.1–5.5, Table 4, §8.3 | Reuse `j16_robustness.handoff_only_block` / `decomposition` / `depth_counts` (:861-968). Add a pooled **cap-81 3-seed** family (hj17 + hj18, seeds {1,2,3}) in a new dev script `scripts/analysis/j17_review_fixes.py` |
| R1.2 ✔ | Report the registered chord test C2 / UF-07 (m9 +3.96 [−0.49, +8.88], task-clustered), and add m11, both receivers and both clusterings | `j8_frontier.chord_block` / `chord_residual` (:2161-2469) with `--cluster scenario` and `--packet-source` |
| R1.3 ✔ | Reframe depth as a **replication and extension of Ganz et al.'s downshift-timing result** with an 8B local receiver; add Ganz-comparable metrics with cluster-bootstrap CIs (next row) | new `ganz_metrics()` in j17 plus a test |
| | *Ganz-comparable metrics:* quality recovery QRec = (arm − floor)/(ceiling − floor); savings retained = (c_ceiling − c_arm)/(c_ceiling − c_floor) | |
| R1.4 ✔ | Report depth's cost share with intervals: calls fraction (m11 ≈ 78 % of cap-25's calls) and dollar saving retained (≈ 25 %) | reuse `j16_robustness.cost_contrast` logic (:1705-1729) generalised in j17 |
| R1.5 | **J10:** Amendment 1 §B registers handoff-only companions for P3/P4 and a chord test for prefix_m9/m11 | `j10_report.a1_handoff_depth` (:2440-2484) is extended to P3 and TGC; chord via an imported `j8_frontier.chord_residual` |

### F2 (FATAL): the channel headline is fragile and sits in step-limit failures
Advice hits the step limit in 20/171 episodes against 2/171 for takeover; those pairs carry 4.36 of the 6.13 pp.
Neutral advice contains code in 132/141 interventions.

| id | fix | where / reuse |
|---|---|---|
| R2.1 ✔ | **Per-arm limit rate beside every quality number** (§3, Tables 1, 1a, 1b), as prereg_hj12:183-187 required | `j16_robustness.arm_summary` n_limit (:391-402) |
| R2.2 ✔ | **Limit decomposition of D0**, with intervals. Label it a post-treatment *mechanism*, not a corrected estimate: pairs where either arm hit the limit vs neither | new `limit_decomposition()` in j17 plus a test. No script re-scores limit today (explorer 1 §3) |
| | *Limit-as-0 sensitivity* (it widens the gap) | same function |
| R2.3 ✔ | **Content evidence**, as new ledger row DEC-06: per arm, the share of interventions carrying fenced code, their length, and the copy rate | extend `b2_decomposition.py` exploratory block (:561-603 pattern) or j17 |
| | *Values:* registered advice 2/167, neutral 132/141; show carries an action by construction | |
| R2.4 | **Dev arm `dev_advise_neutral_fixed_k_1_fullctx`**, neutral prompt at k = 1: removes the H2 strawman | derive from `configs/hj13_advise_fixed_k_1_fullctx.yaml` + `planner.correct_prompt: neutral`; register its stem in `hj12_live.pbs` WAVE_B_ARMS (:174-181); run with `MAX_PLANNER_CALLS=2700` |
| | *Size:* 57×2 = 114 episodes, ≈ 2,170 luna calls | never name it `j10_*` (`test_j10_configs.py:109` pins that set) |
| R2.5 | **J10:** Amendment 1 §C registers a **content family** on arms 9/10/11/12 (defined in §3) | j10_report new family |
| R2.6 | Headline rewritten: "a small executor benefits from the planner's *concrete code*, executed or shown; terse correction prose leaves it stuck" | exploratory on dev; confirmatory only through Amendment 1 on test |

### F3 (FATAL, credibility): the paper breaks the frozen H2 rule
The rule: *"If P4 fails: report the arm as a higher-frequency advice result only…"*

| id | fix | where |
|---|---|---|
| R3.1 ✔ | Abstract, §1 L21, §3.2 L140-142 and §12 L519 report H2's arm as **higher-frequency correction advice**, stating that advice remains unpriced at the action channel's budget. The "remedy written for the opposite case" argument moves to B.1 as a **declared deviation discussion**, never as the result | paper |
| R3.2 | The neutral k = 1 dev arm (R2.4) becomes the exploratory at-price comparison, reported beside it | paper §3.2 |
| R3.3 | **J10:** Amendment 1 §E adds a reporting constraint. P1 keeps its decision rule but is described only as higher-frequency correction advice vs prefix_m11, never as budget-matched | prereg text + j10_report note string |

### F4 (MAJOR): registration outcomes are missing and exploratory status is blurred

| id | fix | where |
|---|---|---|
| R4.1 ✔ | New **registration-outcome table** (main-text §2.5, one table), listing every registered item with its outcome and whether its data were seen before registration | paper, sourced from the preregs |
| | *Rows:* v1 H1/H2; J9 ESC null; hj12 G1 **fail** (both clauses), C1, C2 **fail**, C3 negative; hj13 S1–S3 and replicate floor; H2 P1–P4 (P4 **fail**); B2 unresolved; A1 pending; m ∈ {7,8,10,11} post hoc | |
| R4.2 ✔ | Label each abstract and intro claim as registered or exploratory. Fix L192 ("pre-registered" → "registered after the curve was seen; exploratory") and L462-463 ("central contrasts are pre-registered") | paper |
| R4.3 | **Paper-wide multiplicity sensitivity:** Benjamini–Yekutieli across every interval the paper prints; an appendix table flags claims that do not survive | new `by_fdr()` in `cluster_inference.py` plus a test (no FDR helper exists) |
| R4.4 | **Census table:** the number of dev campaigns, arms and contrasts run | `campaign/campaign_index.json` |

### F5 (MAJOR): margin of convenience, diluted NI, weak ceiling

| id | fix | where |
|---|---|---|
| R5.1 ✔ | State δ's origin wherever NI appears: power-derived for TGC on 168 test tasks (prereg_v1:88-95), moved to goal_pass by J9 | paper §2.4 |
| R5.2 | **Handoff-only NI companions** in Table 4 | `j8_frontier.noninferiority_block` `*_handoff_only` rows (:2077-2145) |
| R5.3 ✔ | The abstract NI claim gets its qualifiers: goal_pass only; the exact test fails prefix_m11 TGC (p = 0.0264); two of the three passing arms are only task-paired with cap-81 | paper |
| R5.4 ✔ | "Ceiling" → "the planner acting alone in the same minimal harness". Disclose the leaderboard's 85.1 % TGC for the same model with a scaffold, and the cap inversion | paper §2.2, §5.5, §11 |
| R5.5 | **J10:** P3's handoff-only companion (in R1.5) | Amendment 1 §B |

### F6 (MAJOR): novelty and positioning

| id | fix | where |
|---|---|---|
| R6.1 ✔ | Describe Ganz correctly: 3 benchmarks, both families, **luna is their low-cost model**; quote App. B.2 after checking the PDF | §10, abstract, §1 |
| R6.2 ✔ | Rewrite Intro L13, which is contradicted by §10 | paper |
| R6.3 | Add must-cites. **Each is re-verified by WebFetch before writing.** Resolve all 17 uncited bib keys (cite where relevant, else drop) | `paper/bibliography.bib` |
| | *Must-cite list:* Minions (ICML 2025) ✔, ManagerWorker 2603.26458 ✔, Torrey & Taylor 2013, Sumers et al. 2023, TACIT-Switch 2608.27911, Prefix-GRPO 2607.19395, COTA 2608.21027, Sinha et al. 2509.09677, COPE 2506.11578, Do Not Restart 2609.13800 ✔ (with the corrected description) | |
| R6.4 | Positioning paragraph: what is new is the matched-trigger act/show/neutral/correction decomposition, the narrated control and the null learned gates, with an 8B tailored receiver | §1, §10 |

### F7 (MAJOR): metric and reporting choices

| id | fix | where / reuse |
|---|---|---|
| R7.1 ✔ | **TGC and SGC beside every goal_pass headline.** Measure the metric's floor with a **no-op dev arm**: the executor emits COMPLETE at step 0, CPU only, 114 episodes, 0 hosted calls | new config `configs/dev_noop_complete.yaml` using MockExecutor with script `["COMPLETE"]` (`src/sidekick/agents/executor.py:17`); if a script cannot be configured, add a 5-line option plus a test |
| R7.2 ✔ | Both clusterings for every interval. First case: L201 m9→11, scenario [−0.23, +9.74] | paper, plus an audit check (R7.8) |
| R7.3 ✔ | Equivalence language → "not distinguishable at n = …", plus the NI verdict | L22, L24, L213, L354 |
| R7.4 ✔ | Report NOISE-01's 3.31 pp (m2/m4 reruns, with the code-change caveat). Replace the stale 0.04 at L63 and L203 | paper |
| | "Monotonically increasing" (L180) → "non-decreasing in point estimates; no adjacent step resolves" | |
| R7.5 | Mechanism: "explain" → "descriptive correlates"; add intervals (the tailored 36.0 % share has CI [−254 %, +77 %]); include m = 11 error incidence (42.59 %) | L6, L376, L392, L398 |
| R7.6 | Fix internal inconsistencies | paper |
| | *Items:* L174 +7.89 vs L244 +8.77 (pick one key; say which); unify CEIL-05 orientation at L219 and Table 4; L172 −1.33 → post-guard −2.25 (ROB-20); delete L801-803 substitutability; L742 "undetermined" → "fails (ROB-07)"; L15 "(scenario clustering only)"; Qwen L415/L521 wording | |
| R7.7 ✔ | Ledger: correct QWEN-05 and NARR-04 with an "A10 (date) →" note, in the existing A9 style. New rows for every new analysis: HO-\*, CHORD-\*, GANZ-\*, LIM-\*, DEC-06, NOOP-01, FDR-01, NEUTRAL-K1-\* | `docs/claims_ledger.md` |
| R7.8 ✔ | **Harden `preprint_number_audit.sh`** (it checks only unsigned magnitudes); plus a fixture test via subprocess | script plus `tests/unit/test_number_audit.py` |
| | *New checks:* signed values; CI tuples `[a, b]` must appear as a tuple in the ledger; forbidden wording ("matches", "indistinguishable", "explain", "establishes", "pre-registered" beside an exploratory id); every abstract ledger id marked exploratory must be labelled; the paper's stated counts come from the script's output | |

### F8 (MINOR)

| id | fix |
|---|---|
| R8.1 | Cut the main text to about 7,300 words (8 pages); the rest goes to appendices; drop lab-notebook narration |
| R8.2 | Privacy motivation (L13): qualify it. The hosted planner sees the task and the first m observations |
| R8.3 | L851: delete "excluding 3 multi-party synchronization tasks"; say "the pinned release ships 57 dev tasks" |
| R8.4 | The dev-basis file name: keep the name. Add a ledger and paper note that it holds dev data only |
| R8.5 | Stale pointer `src/sidekick/policies/sft_plan.py` (A1:611 and paper L574): fix in the paper, disclose in Amendment 1 §G |

### F9: external validity (one planner, one environment)

| id | fix |
|---|---|
| R9.1 | Finish the LP-2 chain (running): verify 114/arm, run `lp_report.py` for both planners, ledger LP-04+ |
| R9.2 | **Wave E, second environment:** start the build now from the existing `docs/second_env_scoping_20260923.md`. It uses zero luna (Opus subagents). Hosted runs only after J10's hosted arms. **Decision point D4** |

---

## 2. Amendment 1 to A1 (pre-data): exact contents

Appended after A1:679. Heading style:

`## Amendment 1 — pre-data additions after the adversarial review (2026-09-2x, appended before any test_normal episode; no arm, registered prediction, Holm family, margin, seed, order or budget above the end marker changes)`

It contains no line starting `**Status**`.

- **§A Disclosure.**
  - Why: the review doc and its commit.
  - What was known: every dev value quoted.
  - The check that no `j10_*` non-dryrun campaign exists at commit time.
- **§B Handoff-only and chord (pre-specified, not decision-bearing).**
  - For P3, P4 and S1–S6: the handoff-only estimand Σd·h/Σh (h from the target arm), silenced count, decomposition share, both clusterings, goal_pass and TGC.
  - A chord residual for prefix_m9 and prefix_m11 (both receivers): floor arm 2 `sft_plan` → reference arm 3; non-cached tokens; cost fraction as plug-in; scenario primary.
- **§C Content family CF (registered, its own Holm family, m = 3).**
  - It does not enter P1–P6's family, so their α is unchanged. It is registered **before** the read, so A1's "no E-row promoted after the read" is respected.
  - A1's P7 statement ("none registered") stays true; CF is a separate family added pre-data.
  - Each prediction below carries its power from §4's simulation.

  | prediction | contrast | predicted | dev value |
  |---|---|---|---|
  | CF1 | `advise_k10_neutral − advise_k10_fullctx` | > 0, CI excluding 0 | +3.73 [−0.06, +8.24] |
  | CF2 | `show_k10 − advise_k10_fullctx` | > 0, CI excluding 0 | +2.30 [−2.43, +7.31] |
  | CF3 | `takeover_k10 − advise_k10_neutral` | two-sided | +2.40 [−2.94, +8.89] |

  - CF3's reading: "execution adds beyond code-as-text" only if its CI excludes 0 on the positive side, otherwise "not distinguishable". No equivalence claim either way.
  - Interpretation table, fixed now:

  | outcome | reading |
  |---|---|
  | CF1 ✓ and CF3 includes 0 | "code content, not execution, carries the advantage over correction prose" |
  | CF1 ✓ and CF3 > 0 | "both content and execution matter" |
  | CF1 ✗ | "the prompt effect does not replicate; P6 stands as built" |

  - If arms 11/12 cannot complete, CF is reported as not run.
- **§D Limits (reporting, not decision-bearing).**
  - The per-arm limit rate beside every quality number.
  - For P6 and CF: a decomposition over pairs where either arm hit the limit vs neither, labelled post-treatment.
  - A limit-as-0 sensitivity.
- **§E P1 reporting constraint** (H2 §5). Described only as higher-frequency correction advice vs prefix_m11, never as budget-matched or as ruling out a budget effect. The decision rule is unchanged.
- **§F Multiplicity sensitivity.** Benjamini–Yekutieli across every test contrast printed.
- **§G Corrections of pointers only.**
  - A1:611 path.
  - Clarification that `j10_a1_registered_dev_basis_20260924.report.json` is dev data.

The user reviews the diff and freezes it on commit. `j10_arm.pbs`'s gate then passes: one Status line, committed, no diff.

---

## 3. Code changes (all tested on fixtures with known answers)

| file | change | reuse |
|---|---|---|
| `scripts/analysis/j10_report.py` | New `A1_AM1_CONTENT` (CF1–CF3) with Holm m = 3 via `holm_adjust` (:2061) | `a1_contrast` (:2142), `a1_interval`, `a1_pool04`, `a1_permutation`, `a1_arm_episodes` |
| | Extend `a1_handoff_depth` to P3 and TGC; add silenced share | `j16.decomposition` |
| | Chord for m9/m11 | import `j8_frontier.chord_residual` |
| | `limit_decomposition` + limit-as-0 | |
| | BY-FDR table | |
| | P1 description string per §E | |
| `tests/unit/test_j10_report.py` | Synthetic `write_a1_matrix` fixtures (:630-706) extended with limit episodes and handoff flags; assert CF Holm, handoff-only, chord and limit numbers against hand-computed values | |
| `scripts/analysis/cluster_inference.py` (+test) | `by_fdr(pvals)` | |
| `scripts/analysis/j17_review_fixes.py` (+test), new, dev only, refuses held-out paths like j16 (:136-140) | Pooled cap-81 handoff-only curve; Ganz metrics; cost shares; D0 limit decomposition; DEC-06 content stats; TGC/SGC columns; no-op floor; BY-FDR over the paper's dev intervals | pure functions from j16 / j8 |
| `scripts/analysis/j10_power_am1.py` (+test), new | Resamples dev per-episode paired differences by scenario to 56 clusters × 2 seeds; power for P6, CF1–CF3 and P3 handoff-only | `a1_paired_series`, `cluster_bootstrap_means`, `bootstrap_pvalue` |
| `configs/dev_advise_neutral_fixed_k_1_fullctx.yaml`, `configs/dev_noop_complete.yaml` | New dev arms (never `j10_*`); `hj12_live.pbs` registry entry for the first | existing config patterns |
| `scripts/analysis/preprint_number_audit.sh` (+ `tests/unit/test_number_audit.py`) | Hardened checks (R7.8) | |

---

## 4. Order of work (critical path first)

| step | what | hosted calls | who |
|---|---|---|---|
| **S0** (≈ ½ day) | `j10_power_am1.py` + test → CPU job via `hpc` → power numbers for §C | 0 | Claude |
| **S1** (≈ 1 day) | Amendment 1 text, j10_report extension + tests; full suite in PBS (≥ current 1158 pass); gate selftest (`J10_PREREG` override) and a grep check for exactly one `**Status**` line | 0 | Claude |
| **S2** | **The user reviews and freezes Amendment 1**; commit; check again that no `j10_*` test campaign exists | 0 | user |
| **S3** | J10 in A1 §9 order: arm 3 → 8, 9, 10 → 11, 12 → 2 → GPU arms 1, 1b, 4–7 | ≤ 15,627 | Claude submits; count-verify every arm |
| | The dev neutral k = 1 arm (R2.4) rides in the arms 11/12 window: 1.6k + 2.2k < ~5k per window | +2,170 | |
| **S4** (parallel with S3, 0 hosted) | j17 analyses + no-op arm (CPU job) + FDR helper + audit hardening + ledger rows | 0 | Claude (code), CPU via `hpc` |
| **S5** (after S4, J10-independent) | **Paper A v2 rewrite:** every R-item above, main text ≈ 7,300 words | 0 | Opus subagent per section (ledger rows pasted in); Claude integrates |
| | *Gates:* hardened audit exit 0; then re-run the three reviewers read-only as a regression; every R-item marked resolved with line refs | | |
| **S6** | Paper A v2 → arXiv (**decision D5**), timestamped against Ganz / concurrent work | 0 | user |
| **S7** | LP-2 chain → `lp_report.py` → ledger LP-04+ (R9.1) | 0 | Claude |
| **S8** | Wave E build (R9.2, **D4**) in parallel; its hosted runs follow J10's hosted arms | 0 until then | Opus subagents |
| **S9** | `j10_report.py` → P1–P6 + CF + §B/§D/§F → ledger J10-\* → Paper B draft | 0 | Claude |

Calendar (judgement):
- day 0–1: S0–S1;
- day 1: S2;
- days 1–10: S3 (3–4 windows);
- days 1–5: S4–S5;
- ≈ day 6: S6;
- days 10–14: S9;
- Wave E: 2–3 weeks.

The one-day hold on the test read is worth it. Luna-6 deprecation risk only affects the hosted arms, and those still run first.

---

## 5. Decision points (defaults; approving the plan accepts them)

- **D1** Amendment 1 as in §2: **yes** (the user freezes it at S2).
- **D2** A ManagerWorker-style structured-direction advice arm on dev (~300 calls, new prompt style): **skip for now**. Neutral k = 1 answers "strawman"; add it only if a reviewer presses.
- **D3** Planner-alone at high reasoning effort on dev (~1.7k calls) to probe the weak ceiling: **skip**; disclose instead (R5.4).
- **D4** Start the Wave E build now (zero luna): **yes**, because it is the top-venue norm (Ganz has 3 benchmarks, Reach-or-Solve 2 environments).
- **D5** Paper A v2 to arXiv before J10 lands: **yes**.

---

## 6. Verification

- **Tests.** Every new or extended function has a fixture test with a hand-computed answer. Full suite in PBS via `hpc` after each commit; the pass count must not drop.
- **Amendment.**
  - `grep -c '^\*\*Status\*\*'` on A1 = 1;
  - `git diff --quiet HEAD -- A1`;
  - j10_arm.pbs selftest passes against the amended file;
  - `j10_report` line-citation tests (test_j10_report.py:1046-1090) still pass.
- **Test contact.** Before S2 and before each S3 submission: `ls results | grep '^j10_' | grep -v _dryrun` is empty until arm 3 is submitted. No script opens `test_normal` before `j10_report` runs at S9.
- **Arms.** Every arm, dev and test: count and `error_type` via jq; crash = `error_type == "crash"` only; 336 (test) or 114 (dev) non-crashed pairs; never judged from the exit code.
- **Numbers.**
  - Each number: ledger row → report key; the hardened `preprint_number_audit.sh` exits 0.
  - POOL-04 on any bound within 1 pp of its threshold.
- **Regression review.** The three read-only reviewers are re-run on Paper A v2. The fix register (§1) is closed only when each R-item cites the paper line that resolves it.
