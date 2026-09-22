# Preregistration Amendment A1 to the J9 Freeze — J10 on `test_normal`

**Status**: **DRAFT pending user review.** Becomes FROZEN on commit. Amends, and does not edit,
`docs/prereg_j9_freeze_20260920.md`.

**Written**: 2026-09-24.

**Gate assertion at time of writing**: the AppWorld `test_normal` split has **not** been read, loaded,
listed, or evaluated by this project, and no file under any `test_normal` or `test_challenge` path has
been opened. Every number in this document is a dev measurement at $n = 114$ paired episodes.

**Authorisation**: the user authorised the J10 test read and signed off J9 §8.1 explicitly on 2026-09-24,
in response to a cost and irreversibility statement quoting the figures in §9.

**Dev basis for every registered prediction**:
`campaign/results/j10_a1_registered_dev_basis_20260924.report.json` — one report computed specifically so
that no number registered below is a difference of means worked out by hand. All seven arms carry
`n_pairs = 114`, `dropped_crash = 0`, `shared = 114`.

---

## 1. Why this amendment exists

The J9 freeze registered a five-arm J10 built around **Claim F1: selective escalation** — does a learned
self-gate or sequential router spend planner calls better than a fixed review schedule? Its arm list was
`executor_alone`, `sft_plan`, `fixed_k_10`, `fixed_k_5`, `sidekick_tau05`
[OBSERVED docs/prereg_j9_freeze_20260920.md:136-144].

Two things happened after that freeze.

**First, J9 itself already recorded the null.** Its §6 claim 4 states that neither the linear verifier head
nor the sequential router discriminates outcome-critical intervention points (scored AUROC 0.3867–0.5082),
and that the executor self-gate's $p_{\text{ask}}$ never exceeds 0.0347 against thresholds of 0.3, 0.5 and
0.7. `sidekick_tau05` was registered only as a "pre-registered check that the self-gate remains
degenerate" [OBSERVED docs/prereg_j9_freeze_20260920.md:143].

**Second, dev work established a different and much larger effect.** The project's reportable finding is
now a **channel** result: help delivered to the executor as an *action prefix* outperforms the same
planner's help delivered as *prose advice*, and does so even when the advice arm is given several times
the budget. None of the five registered J10 arms measures this. `planner_alone` — needed both as the
ceiling and as the source of the prefix trajectories — was explicitly **dropped** from J10 to protect
quota [OBSERVED docs/prereg_j9_freeze_20260920.md:§5.2 item 1].

Running the registered arm list would spend the project's single, non-repeatable test read on a hypothesis
already known to be null on dev, and would not test the effect the paper reports.

**This amendment is honest about its own timing.** It is written *after* the dev results were known and
*before* any test observation exists. That is the only sense in which any preregistration is ever "pre":
it binds the analysis to a specification fixed before the data are seen. Readers should judge it on
whether the predictions below are falsifiable and were fixed before the read — not on whether the
hypothesis was chosen in ignorance of dev. It was not, and no preregistration claims otherwise.

---

## 2. What this amendment supersedes

| J9 section | Status under A1 |
|---|---|
| §4, Claim F1 (selective escalation) as the J10 primary | **Superseded.** Demoted to a dev-only negative result, reported as such. |
| §5.1, the five-arm J10 list | **Superseded** by §4 below. |
| §5.2 item 1, dropping `planner_alone` | **Reversed.** Reinstated as ceiling and trajectory source. |
| §9.1, three seeds | **Amended** to two seeds; rationale in §5.1. |
| §9.2, task-clustered bootstrap, 10,000 resamples | **Retained**, extended with scenario clustering. |
| §6, the dev-evidence claim ordering | **Retained** as a record of what was believed at J9. |
| §8.1, the sign-off gate | **Satisfied**; see the authorisation note above. |

Everything in J9 not listed here stands unchanged. J9 is not edited.

---

## 3. The hypothesis

**H-A1 (primary).** For a fixed frozen hosted planner and a fixed local executor, the *channel* through
which planner help reaches the executor determines outcome quality, and the advantage of the action
channel is not explained by the amount of planner compute spent. Specifically, an executor given the
planner's first 11 recorded actions as an executable prefix outperforms the same executor advised in prose
by the same planner at every step, **despite the advice arm spending strictly more hosted budget**.

This is a claim about *form*, not *quantity*. The budget asymmetry is deliberately in the advice arm's
favour, so that a positive result cannot be read as a compute artifact.

---

## 4. Registered arm list for J10

Split: AppWorld **`test_normal`**, 168 tasks [OBSERVED docs/prereg_j9_freeze_20260920.md:208].
Seeds: $s \in \{1, 2\}$. **336 paired episodes per arm.**

| # | Arm | Receiver | Planner role | Hosted calls/ep (dev) | On test |
|---|---|---|---|---:|---:|
| 1 | `executor_alone` | base granite, `lora_name: null` | none | 0 | **0** |
| 2 | `sft_plan` | `sft_b_plus` | one cached plan | 1.00 | **336** |
| 3 | `planner_alone` cap-81 | n/a (planner drives) | acts every step to completion | 17.35 | **5,830** |
| 4 | `prefix_m9` | `sft_b_plus` | replay, first 9 actions | 9.77 attributed | **0 marginal** |
| 5 | `prefix_m11` | `sft_b_plus` | replay, first 11 actions | 11.25 attributed | **0 marginal** |
| 6 | `prefix_zs_m9` | base granite | replay, first 9 actions | 9.77 attributed | **0 marginal** |
| 7 | `prefix_zs_m11` | base granite | replay, first 11 actions | 11.25 attributed | **0 marginal** |
| 8 | `advise_k1_fullctx` | `sft_b_plus` | full-context prose advice every step | 19.02 | **6,391** |
| 9 | `advise_k10_fullctx` *(droppable)* | `sft_b_plus` | full-context prose advice every 10 steps | 2.46 | **827** |

**Total: 12,557 hosted calls** for arms 1–8; **13,384** including arm 9.

### 4.1 One planner run, and why it is capped at 81

Arms 4–7 replay the trajectories generated by arm 3 and consume no *additional* hosted calls. Arm 3 is
counted once and serves three purposes: the ceiling comparator, the prefix source for all four prefix
arms, and the `planner_alone` reference J9 had to drop. `prefix_m9` and `prefix_m11` take the first 9 and
first 11 actions of the **same** recorded trajectory, so no separate generation is required.

⚠ **This is a deliberate change from the dev prefix arms, and it matters.** Every headline dev prefix
number published so far replays the **cap-25** planner campaign `hj1b_planner_20260915`
[OBSERVED configs/hj12_prefix_m11.yaml:7]. On test there are no recorded trajectories at all, so one
planner run must be generated, and using the **same** run for both the ceiling and the prefix source is
the only way the non-inferiority comparison is like-for-like. The alternative — sourcing prefixes from a
cap-25 run and comparing them against a cap-81 ceiling — compares a prefix drawn from one planner
configuration against a different planner configuration's score, which is not a fair ceiling test.

The change is not cosmetic. Re-measured on dev against cap-81-sourced prefixes:

| contrast | cap-25 sourced | cap-81 sourced |
|---|---|---|
| untailored m11 vs the cap-81 ceiling | −7.08 pp, CI **excludes** zero | **−2.95 pp, [−8.65, +1.91], includes zero** |
| untailored depth m9 → m11 | +4.99 pp | **+2.82 pp, [−1.55, +7.16], includes zero** |
| tailored m11 arm mean | 0.809825 | 0.811149 |

So the striking dev claim that an untailored prefix *significantly beats the planner that would have
produced it* is **sourcing-dependent**, and does not survive a like-for-like comparison. A1 registers the
conservative, like-for-like design and states this correction in the paper. The tailored m11 arm — which
carries the primary — is essentially unmoved (0.8111 vs 0.8098).

Arms 6 and 7 are free and test receiver-dependence on test at no hosted cost. They are secondary, not
primary, because the dev evidence for them is unresolved under this sourcing (see P4).

**Arm 9 is explicitly droppable.** If plan quota binds, it is cut first; it supports only the cost–quality
figure and no registered prediction.

---

## 5. Statistical protocol

### 5.1 Design and power

- 168 tasks × 2 seeds = **336 paired episodes per arm**, versus 114 on dev.
- Two seeds rather than J9's three: 336 pairs already narrows intervals by roughly
  $\sqrt{336/114} \approx 1.7\times$ relative to dev, while a third seed costs a further ~50% of hosted
  budget for a further $\sqrt{3/2} \approx 1.22\times$. A deliberate registered deviation from J9 §9.1,
  taken for cost, disclosed in the paper.
- All contrasts are **paired** on `(task_id, seed)`. An episode missing from either arm removes the pair
  from that contrast; per-contrast pair counts are reported.

### 5.2 Estimation

- Paired percentile bootstrap, **10,000 resamples**, via `scripts/analysis/j8_frontier.py`.
- **Two clusterings for every contrast**: `--cluster scenario` (primary) and `--cluster task` (secondary).
  The scenario-clustered interval governs every decision rule below, being the coarser and more
  conservative unit.
- Bootstrap seed **20260924**, fixed here before the read.
- Primary metric **`goal_pass`**; secondary metric **TGC**.
- **Marginal per-arm intervals are not reported beside paired contrasts** and appear in no decision rule;
  they carry between-task variance the paired design removes and run 2–3× wider.

### 5.3 Multiplicity

The registered family is P1–P5. Holm adjustment is applied **across the five predictions on `goal_pass`**.
Exploratory contrasts are reported unadjusted and labelled exploratory. **No exploratory contrast may be
promoted to a claim after the read.**

---

## 6. Registered predictions and decision rules

All intervals 95%, scenario-clustered, from the dev basis report named at the head of this document.

### P1 — PRIMARY. The channel effect survives at adverse budget.

`advise_k1_fullctx − prefix_m11` on `goal_pass` is **negative with a CI excluding zero**.

Dev: **−14.81 pp**, scenario **[−21.20, −7.96]**, task [−21.73, −8.02]. TGC −14.91, scenario
[−27.19, −2.63] [key `contrasts.goal_pass_all_advise_k1_minus_c81_bp_m11`].

- **Supported** — negative, CI excludes zero → H-A1 holds on test. This is the paper's headline.
- **Not supported** — CI includes zero → **the primary claim is withdrawn** and reported as failing to
  replicate at $n = 336$. The dev result is retained only as a dev-only observation. No reinterpretation,
  no subgroup rescue, no switch to TGC as the primary.
- **Reversed** — positive, CI excludes zero → the headline is withdrawn outright and the reversal is
  reported as the primary finding.

### P2 — PRIMARY. The budget asymmetry is real and runs against the prefix arm.

`advise_k1_fullctx` spends **at least 2× the non-cached planner tokens** of `prefix_m11`, and strictly
more hosted calls per episode.

Dev: **3.19×** tokens (1,414,410 vs 443,361 per episode) and **19.02 vs 11.25** hosted calls/ep
[OBSERVED campaign/results/hj13_advice_at_price_cost_20260923.report.json:
`arms.advise_k1_fullctx.noncached_tokens_per_episode`, `arms.prefix_m11.noncached_tokens_per_episode`].

The prefix arm's cost is attributed as **the $m$ planner steps required to produce its prefix**
(11.25 calls/ep, not zero and not the 17.35 calls/ep of a run to completion). Producing an 11-action
prefix requires running the planner 11 steps and stopping; the ceiling arm's extra cost buys the rest of
its own episode, which the prefix arm never uses. Reporting the prefix arm at zero would flatter it, and
charging it the full 17.35 would charge it for compute it does not consume.

⚠ **Registered correction to a dev mis-specification.** The dev prereg
(`docs/prereg_h2_advice_at_price_20260923.md`) specified this predicate as an absolute band of
[300k, 700k] non-cached tokens; the observed 1.41M failed it *upward* — advice was even more expensive
than registered. That prereg's written remedy addressed under-pricing only and was judged inapplicable
a fortiori (CHAN-PRICE-02). A1 replaces the absolute band with the **relative** predicate above, which is
what the hypothesis actually requires and which cannot fail in the harmless direction.

- **Supported** → the "it just bought more compute" objection is closed on test.
- **Not supported** — advice spends less than 2× the tokens → P1 is **uninterpretable as a channel
  result** and is reported as a budget-confounded comparison, whatever its sign.

### P3 — SECONDARY. The tailored prefix is non-inferior to the hosted planner acting alone.

`prefix_m11 − planner_alone_cap81` on `goal_pass` has a **lower bound above −7.00 pp** — the margin
carried unchanged from J9 and from every dev NI statement.

Dev: the computed contrast is `ceiling_c81 − c81_bp_m11` = **−4.75 pp**, scenario [−11.75, +1.16], so
`prefix_m11 − ceiling` = **+4.75 pp, scenario [−1.16, +11.75]**. The lower bound −1.16 sits well inside
the −7.00 margin; the prefix arm is nominally *above* the ceiling
[key `contrasts.goal_pass_all_ceiling_c81_minus_c81_bp_m11`].

- **Supported** → an 8B local executor replaying 11 recorded actions matches a hosted planner that acts
  every step to completion at up to 81 calls.
- **Not supported** → reported as a failure of non-inferiority at the registered margin. **P1 does not
  depend on P3.**

### P4 — SECONDARY, and registered as underpowered on dev. Depth helps an untailored receiver.

`prefix_zs_m11 − prefix_zs_m9` on `goal_pass` is **positive**.

Dev, cap-81 sourced: **+2.82 pp, scenario [−1.55, +7.16] — the interval includes zero**
[key `contrasts.goal_pass_all_c81_zs_m9_minus_c81_zs_m11`]. Under the cap-25 sourcing used by the earlier
published curve the same step was +4.99 pp; §4.1 explains why the cap-81 figure is the honest one for
this design.

This prediction is registered **knowing dev does not resolve it**. Test carries ~1.7× the power, so it may
resolve. Registering an unresolved effect before the read, rather than reporting whichever way it lands as
though it had been expected, is the point.

- **Supported** — positive with CI excluding zero → depth helps a receiver with no tailoring confound.
- **Directionally consistent** — positive, CI includes zero → reported as unresolved at both $n = 114$ and
  $n = 336$; no claim made.
- **Not supported** — negative → the depth effect is tailoring-dependent; reported as such.

⚠ The **interaction** (whether depth helps the untailored receiver *more* than the tailored one) is **not**
registered, because no difference-in-differences was ever run and A1 does not add one. Any interaction
statement after the read is exploratory and must carry that label. Note that the ordering *reverses*
between sourcings on dev — tailored m9→m11 is +4.92 pp under cap-81 sourcing against the untailored
+2.82 pp — which is itself a reason not to claim an interaction.

### P5 — SECONDARY. Prose advice does not beat a single up-front plan.

`advise_k1_fullctx − sft_plan` on `goal_pass` is **not positive with a CI excluding zero** — advising at
every step does not outperform one cached plan.

Dev: **−5.51 pp**, scenario [−13.15, +2.51]
[OBSERVED campaign/results/hj13_advice_at_price_20260923.report.json:
`contrasts.goal_pass_all_advise_k1_fullctx_minus_plan_floor`].

- **Supported** → the advice channel is flat in its own budget, independent of the prefix comparison.
- **Not supported** — advice significantly beats the plan floor → the advice channel does convert budget
  into quality, and P1's interpretation narrows to "the action channel is better at equal budget" rather
  than "prose advice does not convert budget into quality".

### Supporting contrasts, registered but not decision-bearing

| contrast | dev | scenario CI |
|---|---:|---|
| `advise_k1 − prefix_m9` | −9.89 pp | [−17.79, −1.99] |
| `advise_k10 − prefix_m11` | −7.73 pp | [−12.60, −3.12] |
| `prefix_m9 − prefix_m11` (tailored depth) | −4.92 pp | [−10.36, +0.43] |
| `ceiling − prefix_zs_m11` | −2.95 pp | [−8.65, +1.91] |

---

## 7. What is reported regardless of outcome

1. All nine arms' means with pair counts, both metrics.
2. All pairwise contrasts among registered arms, both clusterings, Holm-adjusted within the registered
   family and unadjusted elsewhere with the label attached.
3. The cost table: hosted calls and non-cached tokens per episode per arm, with the prefix arms' attributed
   source cost shown explicitly rather than as zero.
4. Every arm that crashed, was silenced, or lost pairs, with counts.
5. The J9 Claim F1 negative, as a dev-only result, with its AUROC range.
6. The sourcing correction in §4.1, whether or not it helps the paper.

---

## 8. One read, and what happens if it goes wrong

This is the project's **single** test evaluation. Registered now, so that no post-read judgement call is
unconstrained:

- **No second read for a better number.** If the campaign completes, its numbers are the reported numbers.
- **A bug discovered after the read** does not license a silent re-run. Any re-run is disclosed in the
  paper as a post-read re-run, with the defect, the date, and both sets of numbers. A re-run result is
  **not** reported as a clean preregistered outcome.
- **A crashed or quota-truncated campaign may be resumed** to completion. Resumption fills unwritten
  episodes and is not a re-read; the distinction is that resumption never overwrites an existing
  `result.json`.
- **`test_challenge` is not read.** It remains unread and out of scope under this amendment.
- **No arm is added after the read.** Arms 1–9 are the complete list; arm 9 may only be *removed*.

---

## 9. Cost and authorisation record

| item | value |
|---|---|
| Hosted calls, arms 1–8 | **12,557** |
| Including arm 9 | **13,384** |
| Measured basis | cap-81 ceiling 17.35 calls/ep (1,978 over 114 episodes); `advise_k1_fullctx` 19.02 calls/ep |
| Spent to date, tier B | ~4,650 |
| Quota context recorded at J9 | ~11,500 [OBSERVED docs/prereg_j9_freeze_20260920.md:§5.2 item 1] |
| Billing | ChatGPT-plan subscription, `gpt-5.6-luna`, no per-token billing |
| Authorised by | user, 2026-09-24, explicitly for the test read itself and J9 §8.1 |

The registered total exceeds the quota figure J9 recorded. If plan quota binds mid-campaign, the order of
sacrifice is: arm 9 first, then seed 2 of arm 9. **No reduction may touch arms 3 or 8**, since P1 and P2
depend on both at full pair count. A campaign that cannot complete arms 3 and 8 at 336 pairs each is
**aborted and reported as not run**, not reported at reduced power.

---

## 10. Implementation notes (not part of the registration)

- Test-split configs do not yet exist; each registered arm needs a config with `split: test_normal`,
  `seeds: 1,2`, campaign id `j10_<arm>_20260924`, and — for arms 4–7 —
  `handoff.source_campaign` pointing at arm 3's campaign directory. These are mechanical derivations of
  the existing dev configs and change no registered quantity.
- The phantom-alias hazard applies: any arm without a tailored adapter must run under `prompt_only`, never
  under `sft_plan`, or it silently receives the base model
  [OBSERVED src/sidekick/policies/sft_plan.py:18, src/sidekick/runner.py:256-258].
- **Arm 3 must complete before arms 4–7 start**, since they replay its trajectories.
- Arm 3 needs no GPU (`executor: mock`, planner drives); arms 1, 2, 4–9 need a vLLM server.

### 10.1 ⚠ The campaign cannot run as a single job

Measured 2026-09-22, while drafting this amendment. The hosted planner authenticates through a
ChatGPT plan whose quota window is **invisible to a batch job**: `codex exec` reports no
`rate_limits`. When the window is exhausted, episodes fail as `codex exec exited 1` /
`CodexExecError` at **step 0** with `planner_tokens_total: 0`, and **the PBS job still exits 0**.
Job 25713123 wrote 57 result files, 47 of them crashed this way, and reported `rc_full=0`.

Roughly 5,000 planner calls exhausted a window that day. At 12,557 registered calls, **J10 spans at
least three windows.** Consequences for the run, none of which touch the registration:

- The campaign is submitted **repeatedly**, relying on `--purge-broken` (deletes crashed results so
  they retry) plus the runner's skip-if-`result.json`-exists behaviour. Under §8 this is
  **resumption, not a re-read**: it only fills unwritten episodes and never overwrites a completed one.
- **No arm may be scored from a single job's exit code.** Before any arm is analysed, its episode
  count and `error_type` distribution are checked, and an arm is complete only at 336 non-crashed
  pairs.
- A cheap `mcp__codex__codex` call returns the current limit state and reset time in plain text; it is
  the only reliable way to see the window from here, and should be checked before each submission.
- Budget wall-clock in **days, not hours**. This does not weaken any prediction — it only means the
  abort rule in §9 is evaluated after the campaign stops making progress across windows, not after a
  single job ends.

---

*Amendment A1 ends. J9 remains frozen and unedited.*
