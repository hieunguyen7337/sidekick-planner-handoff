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
| planner alone, **25-call cap** (handicapped) | | | | | 0.8284 | attack 2; H0 refills |

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
| T4 | **Generality**: second receiver family with full curve; limitation for one suite, one planner | "one model pair" | Qwen zs m6/m9/m11 (free); a second *planner* is out of scope (rule: luna only) — stated as a limitation | 0 |
| T5 | **Mechanism**: why flat-then-rising; what the executor does at the first post-handoff error | descriptive curve vs explanation | F3 complete | 0 |
| T6 | **External anchoring**: AppWorld leaderboard, Handoff Tax's percentile-of-trajectory scale beside our step scale | "how does this relate to the field's numbers" | F7 + F1 percentile-scale | 0 |
| T7 | **Multiplicity and confirmation**: Holm across the depth-contrast family on dev; one pre-registered confirmatory read on test | post-hoc grid (attack 6) | analysis + H7 amendment | 0 (+H7) |

Total hosted for the top-venue set beyond tier B: **~9–13k calls**, dominated by H7. Everything else
is free. Realistic calendar: G-P in ~2 weeks, the top-venue additions in ~3–4 more, gated on the H7
authorisation.

## 4. What would change this plan

- **Replicate m=9 differs from 0.7852 by more than 3.075 pp** → the tailored shape claim is withdrawn
  under the registered floor (reported beside the zero-shot rise, which has a 5.1 pp bar and stands).
- **Qwen shows no m6→m9 rise** → kill-condition 4 fires; generality is stated as "one family"; the
  paper's claim (ii) becomes granite-specific. Check the first Qwen episodes for parse failures before
  believing any number (never-run family; silent-zero hazard).
- **X38 lands near plan-only** → H2 is dropped, H3 takes its budget, headline (i) is re-worded to the
  state-advancement mechanism.
- **H0 ceiling rises well above 0.83** → no arm is non-inferior on dev; non-inferiority moves to H7.

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
