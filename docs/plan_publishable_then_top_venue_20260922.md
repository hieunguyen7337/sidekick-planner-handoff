# Plan — publishable first, then top venue (2026-09-22, evening)

Supplements `/home/n12194778/.claude/plans/robust-dancing-sonnet.md` (the 2026-09-22 plan). That plan's
work packages stand; this note records the **decision on the job set** taken tonight, the **bar for a
publishable result**, and the **additional jobs a top venue needs**, in priority order with costs. Every
number here has a `docs/claims_ledger.md` row; nothing is quoted from memory.

## 0. Where the evidence stands tonight

Dev, 57 tasks × 2 seeds = 114 pairs, `goal_pass`, replayed prefixes from `hj1b_planner_20260915`.

| receiver | no prefix | + one plan | m=6 | m=9 | m=11 | rows |
|---|---:|---:|---:|---:|---:|---|
| untailored base granite | 0.1903 | 0.2885 | 0.6825 | 0.7845 | **0.8345** | CHAN-ZS-01, -04 |
| tailored `sft_b_plus` (post-guard) | 0.5289 | 0.7181 | 0.7237 | 0.7852 | 0.8098 | SHAPE-*, TAILOR-07 |
| replicate of tailored (same job, same code) | — | — | 0.7241 | *running* | — | NOISE-02 |
| planner alone, **25-call cap** (the run every prefix arm replays) | | | | | 0.8284 | CEIL-01 |
| planner alone, **cap 81** (fresh sample, 2026-09-22) | | | | | 0.7637 | CEIL-01: −6.47 pp [−11.68, −1.37] vs cap 25 |

Established (interval excludes zero on the primary, scenario-clustered):
- **Action channel ≫ advice channel on an untailored receiver**: +9.8 pp for one plan against +59.4 pp
  for m=9 actions, over executor-alone (CHAN-ZS-01). Two caveats travel with it: budgets unmatched
  and the action channel advances environment state (CHAN-ZS-02).
- **Depth buys quality, flat then rising**: S1 and S2 hold on 8/8 populations × guard settings; the
  zero-shot m6→m9 rise is +10.21 pp [+2.60, +18.20] and is the first contrast to exclude zero on both
  metrics (SHAPE-10); m9→m11 adds +4.99 pp, excluding zero on TGC (CHAN-ZS-04).
- **Tailoring and depth are substitutes**: +33.9 pp from tailoring with no prefix, yet the receivers are
  indistinguishable at m=9 (−0.06 pp) and m=11 (+2.46 pp for zero-shot), the gap closing monotonically
  −4.12 → −0.06 → +2.46 (TAILOR-06, -07).

Not established:
- **The breakpoint's location** (S3 fails 8/8; τ interval [4, 9]; F1-RESULT-01..04). Wording is fixed by
  F1-RESULT-04: "flat below a breakpoint and rising above it; the breakpoint is not located".
- **Non-inferiority to the ceiling**: the ceiling is the handicapped 25-cap run until H0 lands.
- **The registered C3 direction** is refuted (TAILOR-05); the suffix adapter (F4b) is the last C3 arm.

Two things resolve within hours: the m=9 replicate (NOISE-02: the m=6 half is 0.04 pp, so the
withdrawal bar of 3.075 pp now rests on m=9 alone) and the zero-shot Qwen3-8B second family (job
25696145; kill-condition 4's untested conjunct).

## 1. Decision on the job set: continue, with two changes

**Continue** every job in flight. All four are on the free lane and each serves the publishable result:

| job | what | why it stays |
|---|---|---|
| 25693138 | registered m6/m9 replicate | decides the tailored shape claim's withdrawal condition; registered text, no substitute |
| 25690949 → eval | suffix-handoff adapter, then `hj13_prefix_hf_m{6,9,11}` | the registered C3 arm; free; no longer critical-path (zero-shot already answered the core) |
| 25696145 | zero-shot Qwen3-8B m6/m9 | generality; kill-condition 4 |
| 25695952 | ceiling refill, cap 81 (tier B step 1) | every non-inferiority statement depends on it; ~27–80 hosted calls |

**Change 1 — insert a free arm ahead of the priced advice arm.** The channel claim's weak point is
the state-advancement confound (CHAN-ZS-02b). The decisive control is free: the same recorded m=9
planner actions rendered as **text** into the plan slot, executor acting from step 0 in a **fresh**
environment (unit **X38**, "narrated prefix"). It is information-matched to the executed prefix and
state-unmatched, so the two outcomes are both publishable:
- lands near the executed prefix (≈0.78) → the advantage is **encoding**: the channel claim is strong
  and H2 (advice at m=11's budget, ~1,600 calls) becomes worth its price;
- lands near plan-only (≈0.29) → the advantage is **state advancement**: the paper reframes as "execute
  the strong model's actions, do not describe them", and H2's value falls; H3 (live handoff) rises.
A second variant, **X38b** (actions *and* their observations as text), gives a three-way decomposition:
plan-only < narrated actions < narrated actions+observations < executed prefix separates information
from encoding from state. Zero hosted calls; two GPU jobs on the untailored receiver first (cleanest,
largest gap to fill), then the tailored one. **H2 is gated on X38's outcome; H1, H4 are not.**

**Change 2 — the headline order.** The most distinctive claim (a threshold at m\*) did not clear its
registered bar, so the paper leads with what did: (i) channel, (ii) monotone depth, flat-then-rising,
(iii) tailoring and depth as substitutes, (iv) generality across families. The threshold becomes a
secondary, exploratory finding stated in F1-RESULT-04's wording. This is a reframing, not a retreat:
(iii) is a positive result the plan did not predict, and (i) has the largest effect in the campaign.

Hosted order tonight therefore stays as the runbook has it — **H0 → H1 → H4** — and then **X38 decides
between H2 and H3** for the remaining tier B budget (~1,600 + ~1,100 fit inside the approved 5k).

## 2. The publishable bar (thesis + a dev-only workshop preprint)

Gate **G-P**: every headline number has a ledger row with both clusterings; H0 at 0 crash; H1 run;
X38 run on both receivers; second-family direction recorded either way; the noise floor reported under
both the registered (NOISE-02) and the substitute (NOISE-01) definitions; figures from report JSONs.

| unit | lane | cost | status |
|---|---|---|---|
| F1b replicate | GPU | 0 | running |
| F4b suffix adapter train + eval | GPU | 0 | training; eval tonight |
| F5' Qwen zero-shot m6/m9 (+ m11 addendum) | GPU | 0 | queued; m11 config to add |
| **X38 / X38b narrated prefix** (new) | Cline build, GPU run | 0 | scoping tonight, brief tomorrow |
| X33b / F3 mechanism (novelty-by-position, first-error step, prefix-exhausted population) | luna/Cline | 0 | `scripts/analysis/j13_mechanism.py` exists, unfinished |
| F6 figures, F7 external table, F2 cost axes | Cline / agy | 0 | not started |
| X16 git-sha provenance | luna | 0 | brief ready |
| H0 ceiling refill | hosted | ~27–80 | running |
| H1 full-context advice control | hosted | ~280 | next, after 0-crash gate |
| H4 registered matched-trigger pair | hosted | ~550 | after H1 |
| H2 *or* H3, chosen by X38 | hosted | ~1,100–1,600 | after X38 |

Estimated wall time to G-P: **8–10 working days** with the degraded worker roster (Cursor disabled to
~2026-10-03, Cline daily-capped, agy cannot wait on PBS, luna shares the hosted quota).

## 3. What a top venue needs beyond G-P, in priority order

| # | need | why a reviewer asks | unit | cost |
|---|---|---|---|---|
| T1 | **Power.** 57 tasks in **19 scenario clusters** leave S3 unresolved and the m=9 non-inferiority missing by 0.06 pp | "n=19 clusters" is the first thing a statistician sees | H5 seed 3 (~820) then **H7 test split** | ~820 + ~8–12k; H7 needs the J9 §8.1 authorisation and a committed prereg amendment |
| T2 | **Matched cost and matched information** for the channel claim | "actions executed vs prose is unfair by construction" | X38, X38b (free) + H2 | 0 + ~1,600 |
| T3 | **Deployability**: oracle replay → live handoff | attack 8 | H3 `planner_handoff` | ~900–1,300 |
| T4 | **Generality**: second receiver family with full curve; a second *planner sample* for the curve; limitation for one suite, one planner model | "one model pair, one planner run" | Qwen zs m6/m9/m11 (free); untailored curve on the cap-81 trajectories (free, CEIL-02 item 4); a second planner *model* is out of scope (rule: luna only) — stated as a limitation | 0 |
| T5 | **Mechanism**: why flat-then-rising; what the executor does at the first post-handoff error | descriptive curve vs explanation | F3 complete | 0 |
| T6 | **External anchoring**: AppWorld leaderboard, Handoff Tax's percentile-of-trajectory scale beside our step scale | "how does this relate to the field's numbers" | F7 + F1 percentile-scale | 0 |
| T7 | **Multiplicity and confirmation**: Holm across the depth-contrast family on dev; one pre-registered confirmatory read on test | post-hoc grid (attack 6) | analysis + H7 amendment | 0 (+H7) |

Total hosted for the top-venue set beyond tier B: **~9–13k calls**, dominated by H7. Everything else
is free. Realistic calendar: G-P in ~2 weeks, the top-venue additions in ~3–4 more, gated on the H7
authorisation.

## 4. What would change this plan

- ~~Replicate m=9 differs from 0.7852 by more than 3.075 pp~~ **Resolved 19:10: m=9 replicate 0.8033,
  gap 1.81 pp; larger replicate difference 1.81 pp; twice that is 3.62 pp < the 6.15 pp rise.** The
  registered withdrawal condition does not fire (NOISE-03). Under the substitute floor of NOISE-01
  (3.31 pp) it would have; both are reported and the registered one governs. The replicate pair's own
  rise is 7.92 pp, larger than the original's.
- **Qwen shows no m6→m9 rise** → kill-condition 4 fires; generality is stated as "one family"; the
  paper's claim (ii) becomes granite-specific. Check the first Qwen episodes for parse failures before
  believing any number (never-run family; silent-zero hazard).
- **X38 lands near plan-only** → H2 is dropped, H3 takes its budget, headline (i) is re-worded to the
  state-advancement mechanism.
- ~~H0 ceiling rises well above 0.83~~ **Resolved 19:10: the opposite happened.** The cap-81 sample
  scores 0.7637, significantly *below* the 25-cap run (CEIL-01). Every non-inferiority statement so
  far was against the higher ceiling, so none weakens. Two consequences: name the ceiling in every
  comparison (CEIL-02), and treat the 6.47 pp between planner runs as the planner's own noise, which
  the replay design removes from the depth curve (executor-side replicate noise: 0.04 pp at m=6).
- **New free robustness check**: re-run the untailored prefix curve (m6/m9/m11) on the cap-81
  trajectories — a second, weaker planner sample for the curve at zero hosted cost (goes into §3 T4).

## 5. Odds tonight (moved since this morning's 80–85 / 50–60)

| outcome | now | after G-P | after §3 |
|---|---|---|---|
| defensible, publishable thesis | ~88% | ~93% | ~95% |
| workshop preprint accepted | ~80% | ~90% | — |
| main-track top venue | ~55% | ~60% | ~70% |

What moved them: the m=6 replicate difference of 0.04 pp; the zero-shot m=11 arm at 0.8345 with a TGC
rise that excludes zero; X37 landing cleanly. What still caps the top-venue number: 19 clusters, one
suite, one planner, and the channel confound until X38.

## 6. Tonight's queue and tomorrow's first checks

Tonight, in order: replicate m=9 → NOISE-02 second half + withdrawal verdict; H0 gate (0 crash) → submit
H1; training ends → submit `hj13_prefix_hf_m6 hj13_prefix_hf_m9 hj13_prefix_hf_m11`; Qwen m6/m9 → first
five episodes inspected for parse failures, then aggregate.
Tomorrow: X38 brief (Cline), Qwen m11 config, F3 remainder, ledger rows for every new report, commit.

---

## 7. Outcome record — 2026-09-22, 20:10 (appended; earlier sections unchanged)

Six arms and four analysis units landed or were dispatched between 19:20 and 20:10. This section records
what resolved, what changed as a result, and what is now queued. Every number here has a ledger row.

### 7.1 The branch in §1 resolved: **narrated ≈ executed**

The narrated-prefix control (X38) was built precisely to decide between H2 and H3, and it decided.
Rendering the planner's first nine recorded actions as *text* into the plan slot, with the executor
starting from step 0 in a **fresh** environment, scores **0.7665** on the tailored receiver (n=113 of 114
at the time of writing) against the **executed** prefix's 0.7852 and the plan-only floor's 0.7181. Verified
on a live episode: the plan carries the task's five original planning steps followed by nine
`Expert trajectory, step k of 9 (code the planner actually ran on this task): <code>` steps, and the
executor took 40 actions from step 0 with no replayed state.

So roughly three quarters of what the action prefix buys is carried by **information**, not by the
environment state the prefix left behind. Consequences, per the §1 decision rule:

- **H2 (`advise_fixed_k_1_fullctx`, advice reviewed every step) is the decisive remaining control**, and is
  now pre-registered in `docs/prereg_h2_advice_at_price_20260923.md` (frozen before submission, with four
  numeric predictions and four decision rules including an explicit withdrawal condition). It is chained
  to submit the moment H4 releases the hosted quota.
- **H3 (live `planner_handoff`) drops to optional.** It remains the deployable-form arm and is worth
  running if quota allows, but it is no longer what the channel claim rests on.
- Budget: H0 ~1,650 + H1 ~280 + H4 ~550 + H2 ~1,600 ≈ **4,080 of the approved ~5,000**. No top-up needed.
  Adding H3 later would need roughly 900–1,300 more.

### 7.2 Two attacks closed outright

**Attack 3, the context-starved critic (ADV-FC-01).** H1 ran. Full-context advice at k=10 scores 0.7339:
**+1.57 pp** over the adapter-matched plan-only floor, scenario-clustered [−2.91, +5.91], and **+3.74 pp**
over the starved control [−1.39, +9.13]. Every interval includes zero. Advice does not leave the
plan-only floor even when the reviewer sees the whole transcript.

**Attack 1, "the rise is by construction" (MECH-03).** With the handoff flag read correctly, the zero-shot
m6→m9 rise of 10.21 pp decomposes into **8.55 pp (83.8 %) earned on episodes where the executor genuinely
took over** and 1.65 pp from prefix-exhausted episodes. Restricted to the handoff subset alone, deepening
6→9 raises goal-pass by **11.89 pp** and 6→11 by **19.41 pp**. The share falls to 60.5 % at m=11, so the
deepest claim must always carry it.

### 7.3 The mechanism is now measured, not conjectured

**M2 (MECH-05).** A deeper prefix roughly halves how often the executor errors at all. Tailored receiver:
85.1 % of handoff episodes contain a failed observation at m=2, 56.8 % at m=6, **42.7 % at m=9**, 42.6 % at
m=11. Untailored: 80.2 % → 64.6 % → 61.1 % over m=6/9/11 — the untailored executor errors far more often at
every depth, which is the error-side signature of tailoring. Conditional on erroring, the tailored
executor's first error moves *earlier* (20.6 % → 51.7 % at the first executor step), i.e. what failure
remains is concentrated at the seam. Descriptive only: the populations shrink with depth (114 → 54), so no
CI is attached.

### 7.4 Generality, in progress

- **Second family (QWEN-01).** Zero-shot Qwen3-8B rises **0.4491 → 0.7017 over m=6 → m=9, +25.25 pp**
  [scenario +16.46, +35.11] — steeper than granite's +10.21. No parse failures; the errors are step-limit
  exhaustion, falling from 74 of 114 episodes to 39. ⚠ Its own floor (`hj15_executor_alone_zsq`,
  `hj15_prompt_only_zsq`) is still running; until it lands, only the m6→m9 contrast may be quoted.
- **Second planner sample (CEIL-04).** Six `hj17_prefix_c81_*` arms replay the independent cap-81
  trajectories instead of cap-25. Viability confirmed first: 114/114 episodes carry ≥6 actions, 99 carry
  ≥9, 76 carry ≥11. The cap-81 planner also took **more** actions (mean 16.35 vs 13.42) while scoring
  6.47 pp **lower**, with the distributions identical through the median and diverging only in the upper
  tail — which favours the over-acting reading of CEIL-01 over run-to-run drift, without eliminating it.
- **Suffix adapter (HF-TRAIN-01).** Trained clean (final loss 0.0427, token accuracy 0.9903, 2 epochs,
  615 sequences) and comparable to the reference build (0.0503 / 0.982), so a null result on C3 cannot be
  explained away as a failed adapter. First arm in: `hj13_prefix_hf_m6` scores **0.7480** against the
  standard adapter's 0.7237 at the same depth. CIs pending the full set.

### 7.5 Three defects found and fixed, all of the same family

Each was a *believable number* rather than a crash, which is the failure mode this project keeps meeting.

1. **The handoff flag was read from `result.json`, where it does not exist** (MECH-02), so every M2/M3
   population was empty and the decompositions attributed 100 % of every rise to prefix-exhausted episodes
   by construction. Fixed (X33d) by reading the `report` event, as `j8_frontier.py` does.
2. **M2 filtered observations by `actor == "executor"`** (MECH-04), but observations are emitted by
   `environment`, so the error scan matched nothing and reported a 0.00 % error rate across all arms while
   17–32 % of those episodes were failing. Fixed (X33e).
3. **My own first H1 contrast paired iaware-build advice arms against an older-build plan-only floor**
   (ADV-FC-02), inflating the advice-over-plan gap from 1.57 pp to 3.39 pp — in the flattering direction.
   Three plan-only campaigns exist on disk spanning 0.7000 to 0.7181. Standing rule added: every
   cross-arm contrast names the adapter build of every arm in it.

The fatal-guard added in (1) fired on its first real run and was **right to** (GUARD-01): it caught
pre-F0 comparison arms where the executor acted after a replayed `COMPLETE`. That guard was then refined
from a blanket 5 % divergence threshold to the directional check that is genuinely impossible
(`handoff_occurred = True` with zero executor calls), with the benign pre-F0 direction recorded rather
than fatal.

### 7.6 Queued now

| unit | lane | state |
|---|---|---|
| H2 `advise_fixed_k_1_fullctx` | hosted | chained behind H4; prereg frozen |
| Narrated contrasts, both receivers | CPU | script ready, fires when both pairs land |
| Matched-pair decomposition, both receivers | CPU | running (`--decompose-pairs m6:m9,m6:m11`, X33f) |
| F2 cost axes + Holm multiplicity (X40) | worker | running (rerouted after the Cline daily cap) |
| F6 figures (X41) | worker | running |
| Qwen floor + m11; six cap-81 arms; suffix-adapter m9/m11 | GPU | running |

Not started: F7 external comparison table, X16 run provenance, the D5 preprint draft. H5 and H7 remain
unrequested and need explicit authorisation, H7 also the J9 §8.1 clause.

---

## 8. Outcome record — 2026-09-22, 20:15: the channel claim is established

### 8.1 C1, the contrast the prereg names as primary, is positive

`takeover_fixed_k_10` minus `advise_fixed_k_10_fullctx` on `goal_pass`: **+6.69 pp**, scenario-clustered
**[+1.29, +13.48]**, task-clustered **[+1.47, +12.35]**. Both exclude zero. Arms 0.8007 vs 0.7339, n = 114
paired, 0 crash. The two configs differ in exactly one field and **both pass the planner the whole
transcript** (verified in code, CHAN-C1-00), so this is not a context or trigger asymmetry.

**Red-team attack 4 is closed.** "Channel, not budget" is licensed **at matched trigger**. It is not yet
licensed at matched *token budget* — that is H2 (`advise_fixed_k_1_fullctx`, PBS 25701766), pre-registered
in `docs/prereg_h2_advice_at_price_20260923.md` with an explicit withdrawal condition, now running.

Supporting, same report: advice minus plan-only floor **+1.57 pp [−2.91, +5.91]** (advice buys nothing
over one plan even with full context); takeover minus plan-only **+8.26 pp [+3.84, +13.11]**; advice minus
`prefix_m11` **−7.60 pp [−12.56, −2.68]**.

### 8.2 The live arm matches the oracle prefix (attack 8 largely answered)

Takeover minus `prefix_m9` **+1.55 pp [−3.46, +7.04]**; minus `prefix_m11` **−0.91 pp [−6.74, +5.94]**.
A *live* arm, calling the planner during the episode, is indistinguishable at n = 114 from arms replaying
a recorded trajectory. State as "cannot distinguish", never "equal": the intervals would not exclude a
real 5 pp difference. The cost asymmetry remains and belongs in F2.

### 8.3 C3 answered: handoff-suffix training does not move the threshold

Three receivers on identical prefixes — untailored / standard adapter / handoff adapter: m=6 0.6825 /
0.7237 / **0.7480**; m=9 0.7845 / 0.7852 / 0.7840; m=11 **0.8345** / 0.8098 / 0.8033. All nine within-depth
intervals include zero, so no gap is individually resolved; the **pattern** is what matters. The trained
receivers lead at m=6, all three converge to within 0.12 pp at m=9 (tightest interval in the set, ±3.1 pp),
and the untailored receiver leads at m=11. Curve spans over m=6→11: untailored 15.20 pp, standard 8.61,
handoff 5.53. **Depth, tailoring and suffix training are partially substitutable and do not stack.**

### 8.4 An honest negative that constrains every claim: no single depth step is significant

Holm over the family of 8 adjacent-m contrasts gives **adjusted p = 1.0 for all eight**, every adjusted
interval spanning zero. The raw intervals already all spanned zero, so correction is not what kills them:
**no individual step was ever significant.** Segmented fit: τ = 4 post-guard, CI [4, 8], verdict "no
threshold established". The depth effect must therefore be reported as a rise **across a span** (m=6→m=9
is +6.15 pp tailored, +10.21 pp untailored) and never as a jump at a named depth. The figure generator
enforces this with a regression test that fails if a breakpoint marker is drawn.

### 8.5 A confound caught before it reached a claim

Qwen3-8B emits the harness's terminal action **0 times in 114 executor-alone and 0 times in 80 plan-only
episodes**, but 32–37 times once a replayed trajectory has demonstrated the format; granite under the
identical harness and byte-identical stop tokens completes 53 of 114 plan-only episodes. So the Qwen
**floor** mixes format acquisition with competence, and floor-relative lift claims for the second family
are unsupported. The m6→m9 depth contrast (+25.25 pp [+16.46, +35.16]) is unaffected because both arms
carry a demonstration. F5 must be stated as *"the depth effect replicates in a second family within
prefix arms"*. The figure generator refused to plot the Qwen curve at all with its floor missing.

### 8.6 Four analysis defects found today, all of one family

Each returned believable numbers rather than crashing: the handoff flag read from a file that does not
carry it (every mechanism population empty); the error scan filtered on the wrong actor (0.00 % error
rate everywhere while a third of episodes failed); an adapter-build mismatch in my own first contrast
(inflating advice-over-plan from 1.57 to 3.39 pp); and the cost script's usage filter matching **local
executor** tokens and pricing GPU work at the hosted rate, which inverted the dollar ordering so that
684k tokens appeared to cost less than zero calls. All four are fixed, each with a regression test, and
each has a ledger row. The fatal-guard added after the first fired correctly on its first run.

### 8.7 State

`docs/claims_ledger.md` 90 rows. Four of five paper figures generated from report JSON by key, with a
manifest tracing every mark to a key; the fifth correctly skipped. External comparison table written with
37 of 38 rows fetched and spot-checked by me against arXiv. Still running: H2, the Qwen m11 arm, the six
cap-81 arms, the narrated curve at m6/m11, and the two narrated with-observations variants.

Not started: X16 run provenance, the D5 preprint draft. H5 and H7 remain unrequested; H7 additionally
needs the J9 §8.1 authorisation.

---

## 9. Outcome record — 2026-09-22, 20:40: the narrated control selects the branch

### 9.1 The prefix conveys information, not state

The X38 narrated arms are complete on both receivers at n = 114. They render the planner's first nine
recorded actions as **text** and run the executor from step 0 in a **fresh environment** — same
information, no carried state. Executed minus narrated at m = 9:

| receiver | metric | diff | scenario 95 % CI | task 95 % CI |
|---|---|---|---|---|
| tailored | `goal_pass` | +1.84 pp | [−2.67, +6.76] | [−3.70, +7.75] |
| tailored | TGC | +3.51 pp | [−5.26, +11.40] | [−4.39, +11.40] |
| untailored | `goal_pass` | +1.69 pp | [−4.16, +7.11] | [−3.70, +7.38] |
| untailored | TGC | +6.14 pp | [−2.63, +14.91] | [−1.75, +14.91] |

**All eight intervals include zero.** The environment state a replayed prefix leaves behind contributes
nothing resolvable at this sample size once the same information reaches the executor as text. State
this as "cannot distinguish at n = 114", never as "narration is as good as execution" — the TGC point
estimates are consistently positive, which is the direction expected if state helps a little.

### 9.2 What text alone buys

Narrated minus the one-plan floor: untailored `goal_pass` **+47.92 pp [+38.67, +56.27]**, untailored TGC
**+43.86 pp [+30.70, +56.14]**, tailored TGC **+13.16 pp [+5.26, +21.93]** — three intervals excluding
zero. ⚠ The fourth does not: tailored `goal_pass` is **+4.86 pp [−0.56, +10.61]**, so on the tailored
receiver the narrated gain is established on TGC and **not** on `goal_pass`.

As a share of what execution achieves over the same floor: untailored **97 %** of the `goal_pass` gain
and **88 %** of TGC; tailored **73 %** and **79 %**. The receiver with more headroom gets proportionally
more from text, which is TAILOR-07 seen from a different angle.

### 9.3 The claim this sharpens, and the branch it selects

Put beside CHAN-C1-02 — prose advice at matched trigger and full context loses by 6.69 pp — the
mechanism claim becomes **content, not channel and not state**: concrete executable action sequences are
what the executor needs, whether or not they were ever executed in its environment, and prose *about*
what to do does not substitute.

Per the plan's §3 decision rule, narrated ≈ executed makes **H2 mandatory rather than optional**.
`hj13_advise_fixed_k_1_fullctx` (PBS 25701766) prices advice at the prefix's own token budget and is
already running, pre-registered in `docs/prereg_h2_advice_at_price_20260923.md` with an explicit
withdrawal condition. H3 (the live handoff) is **not** selected by this branch.

### 9.4 Also landed since §8

Cost is now priced in three currencies. On the matched pair the action channel **strictly dominates** —
cheaper on non-cached tokens, provider dollars and hosted calls simultaneously, while scoring 6.69 pp
higher — so the channel claim needs no "at a price" qualifier against its matched comparator (COST-01).
The single ordering flip involves the *starved* advice arm, off the critical path (COST-02).
Non-inferiority to the cap-81 ceiling is **currency-invariant**: the same two arms pass under all three
axes (COST-03).

The Qwen floor arms completed and are **degenerate** — both score 0.2481 with TGC exactly zero and zero
successes across 228 episodes, and a full plan moved the outcome in **no episode at all**. The number is
a constant of the task set, not a property of the model. The prefix arms are healthy and rise
monotonically through m = 11 on all five quantities, so the second-family claim survives in the
within-prefix form only (QWEN-03, QWEN-04).

Ledger 90 → 96 rows. Suite 578 passed. HEAD `f9909ad`.

### 9.5 Still running

H2 advice-at-price; the six cap-81 arms; the narrated curve at m6/m11; the two narrated
with-observations variants. Not started: X16 run provenance. H5 and H7 remain unrequested, and H7 needs
the J9 §8.1 authorisation.

---

## 10. Outcome record — 2026-09-22, 21:30: the narrated claim corrected, and a second planner sample

### 10.1 The correction, which matters more than the original result

§9 recorded narrated ≈ executed at m = 9 and used it to select the H2 branch. The rest of the narrated
curve has now landed and **m = 9 is the one depth at which the two curves cross.**

| m | `goal_pass` narrated − executed | scenario CI | TGC narrated − executed | scenario CI |
|---|---|---|---|---|
| 6 | −6.96 pp | [−13.67, +0.63] | **−13.16 pp** | **[−21.05, −5.26]** |
| 9 | −1.69 pp | [−7.10, +4.16] | −6.14 pp | [−14.91, +2.63] |
| 11 | **−6.58 pp** | **[−9.98, −3.64]** | **−11.40 pp** | **[−22.81, −2.63]** |

Execution beats narration **significantly at both outer depths**, on both clusterings. The claim
"the prefix works by what it tells, not the state it leaves behind" is **withdrawn as a general
statement**. What survives: *information carries the prefix benefit at moderate depth, and past
m ≈ 9 the executed environment state contributes something text does not.*

The mechanism behind the crossing is visible in the curves themselves. **Narration saturates**: the
narrated curve gains **+0.10 pp** from m = 9 to m = 11, scenario [−4.75, +5.14], while the executed
curve climbs 0.7845 → 0.8345. All of narration's rise is in m = 6 → m = 9 (+15.48 pp [+8.49, +22.59]).

One corollary survives at every depth measured and is the practically useful one: **narration at
m = 9 and m = 11 beats *execution* at m = 6** (+8.52 pp [+2.32, +14.75] and +8.62 pp [+2.24, +15.02]).
Deeper narration is worth more than shallower execution, and narration needs no environment setup.

**The H2 branch selection stands.** The information-level framing is still the right one at the depth
the channel arms operate at, so pricing advice at the prefix's token budget remains the decisive
control. H2 is at 72/114 and healthy.

### 10.2 The single-sample objection is answered

Six arms replay the **cap-81** planner trajectories rather than the cap-25 ones every other prefix arm
uses; the untailored three are complete. Curve 0.7201 / 0.7650 / 0.7932 at m = 6/9/11. Span m = 6 → 11
**+7.31 pp** [+2.07, +12.80] on `goal_pass` and **+9.65 pp** [+2.63, +16.67] on TGC, both excluding
zero, and — as MULT-01 requires of the original curve — **no single step individually significant**.

The endpoint is the result: at m = 11 the two samples' prefixes differ by **−4.13 pp**, scenario
[−8.84, +0.50], **including zero**, although the cap-81 planner itself scores 6.47 pp below the cap-25
planner. A materially weaker planner run yields a prefix of indistinguishable value at depth 11.
⚠ The curve is **compressed, not translated** — higher at m = 6, lower at m = 11, span 7.31 against
15.20 pp — so this replicates the *effect*, not the *curve*.

### 10.3 A worker invented three numbers and reported that it had not

The preprint draft's cost table had 3 of 11 TGC values wrong, and **every wrong one was a value absent
from the ledger** while the whole `goal_pass` column was right. One was a verbatim fill-down of the row
above. The brief had said to write `[TODO:` wherever the ledger had no number; the returned status
reported zero such markers and zero unsourced claims. **That instruction is not self-enforcing** — a
model that does not know it is guessing cannot comply with it. A **set-difference audit** (every numeric
literal in the draft must appear in the cited source) found all three in one command. That audit now runs
on the preprint after every edit and is the reason the later additions are clean. QUAL-03.

### 10.4 State

Ledger **101 rows**. Suite **581 passed**. Preprint drafted at ~5,300 words with F1–F6 referenced, every
`pp` figure ledger-sourced. HEAD `23ee9db`.

Still running: H2 (72/114); the tailored cap-81 arms; the tailored narrated curve at m6/m11; the two
narrated ±observation variants; and one worker adding per-arm bootstrap intervals so F1 can finally have
confidence bands.

Blocked, needing the user: the tailored **Qwen adapter** training (plan §6.3, free GPU, recommended) —
the `qsub` was refused by the permission layer. The Qwen floor defect makes this materially more
valuable than when the plan was written, since a tailored Qwen would have the action format trained in
and would give the second family a real floor.

---

## 11. Status at 2026-09-22 22:05 — what landed tonight, and two judgement calls

### 11.1 Landed

| result | what it says | ledger |
|---|---|---|
| **H2, registered primary** | Advice reviewed every step spends **1,414,410 non-cached tokens** and **19.02 hosted calls** per episode — 3.2× the tokens and 1.7× the calls of `prefix_m11` — and still scores **−14.68 pp** `goal_pass`, scenario [−22.09, −7.04]. P1, P2 and P3 held. Attack 4 is closed. | CHAN-PRICE-01 |
| **H2 cost prediction failed** | P4 predicted [300k, 700k] tokens; observed 1.41M. Recorded as a failure, see §11.2. | CHAN-PRICE-02 |
| **Narrated control completed on the tailored receiver** | All six same-depth contrasts include zero (`goal_pass` −2.51, −1.84, −0.49 pp). Non-inferior to execution at m = 9 and m = 11 against the 7.00 pp margin. The untailored receiver loses 6.58 pp at m = 11 and its narrated curve saturates after m = 9 (+0.10 pp) while the tailored one keeps climbing (+3.81 pp, excluding zero). | NARR-04 |
| **Abstract and contribution list rescoped** | Both asserted the superseded NARR-01 equivalence and the demoted TAILOR-07 substitutability. Corrected; H2 added as a fourth finding. | — |
| **`pytest tests/` had been aborting at collection since 2026-09-16** | `tests/unit` and `tests/integration` both held `test_limits_and_policy.py` and, with no `__init__.py`, the second import collided. Every "588 passed" this session was `tests/unit` alone. Renamed; the whole tree now runs: **625 passed, 1 skipped**. | — |
| **Trainer pinned to H100** | The A100/H100 coin flip killed two dry runs (granite 25690327, Qwen 25708421). `gpu_id=H100` moved into `scripts/pbs/train_sft.pbs`. | — |
| **Preprint number audit moved into the repo** | It lived only in a job temp directory that dies with the job, and it is the only thing that caught X46's three fabricated values. Now `scripts/analysis/preprint_number_audit.sh`. | QUAL-03 |

### 11.2 Judgement call 1 — a frozen prereg's remedy that did not fit its own failure

P4 failed, but **upward**: the arm spent 2× the top of the predicted range, not below the bottom of
it. The remedy attached to a P4 failure is written for under-pricing (*"P2 must be reported as not
tested"*), because the hazard being guarded against is declaring a channel win that is really a
budget win. That hazard is excluded a fortiori when advice is bought at 3.2× the action channel's
budget and still loses. P2 is therefore reported as **tested and supported**, the deviation is
recorded in CHAN-PRICE-02 and stated in the paper, and a reader who declines the judgement is
pointed at COST-01, which settles the same ordering at matched trigger with no budget question.
The frozen text is not edited.

### 11.3 Judgement call 2 — H3 is largely redundant and is not recommended

Wave 2 offered H3 (`planner_handoff` live, ~900–1,300 hosted calls) as the deployability arm. It is
now mostly redundant: **CHAN-C1-03 already establishes** that a live takeover loop calling the
planner online is statistically indistinguishable from replayed oracle prefixes at both m = 9
(+1.55 pp, scenario [−3.46, +7.04]) and m = 11 (−0.91 pp, [−6.74, +5.94]). Spending ~1,200 calls to
re-derive live-versus-replay equivalence buys little that the paper does not already have. **Not
recommended** unless the deployable loop is wanted as a headline artifact rather than as evidence.

### 11.4 Hosted spend against tier B (~5,000 approved)

H0 ≈ 1,650 + H1 ≈ 280 + H4 ≈ 550 + **H2 ≈ 2,168** (19.02 × 114, well over the ~1,600 estimated)
≈ **4,650 of ~5,000**. The user's 2026-09-22 instruction covers luna spend from the subscription, so
the constraint that bites is plan *quota*, not cost — hence the standing rule that hosted arms and
luna workers never run in the same window.

### 11.5 In flight

- `25710038` Qwen tailored adapter training, H100 `gpu1n007`, ~6 h. Then the Qwen tailored floor and
  prefix m6/m9/m11, which give the second family the non-degenerate floor QWEN-03 denied it.
- `25698250` untailored narrated ± observations, then the observation contrasts on both receivers.
- X49 (luna) drawing F7 (the narrated receiver × depth interaction) and F8 (advice at price).

### 11.6 Still unrequested

H5 (~820 hosted, seed 3 at cap 81) and H7 (the J10 test split, 8–12k hosted) remain unstarted. H7
additionally requires the explicit §8.1 authorisation in `docs/prereg_j9_freeze_20260920.md` and a
committed prereg amendment before any test-split file is read.
