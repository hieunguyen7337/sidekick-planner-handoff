# C1 — record the J8 dev frontier in campaign/RUNS.md

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

You own **`campaign/RUNS.md`** only. Do not touch any other file. **Do not commit, do not run git,
do not `qsub`, do not run python.** A live GPU job (B1, `25560367`) is running; leave it alone.

`aquarius01` is a login node — steering only. No python, pip, tar, rsync. `timeout` on any command.
You should not need to run anything: every number you need is in this brief.

## Goal

Append a new section **`## 10. J8 dev frontier — 2026-09-20 (twelve arms, n=114 each)`** to
`campaign/RUNS.md`, recording the result below. Match the prose style of the existing sections
(plain declarative sentences, numbers inline, no bullet-point soup, no marketing adjectives).

## Provenance (state this in the section)

- Report: `scripts/analysis/j8_frontier.py`, run 2026-09-20 17:23, output JSON
  `frontier_full.json` (session scratch, not durable — the numbers below are the record).
- Live arms from PBS jobs `25560358` (fixed_k_3, fixed_k_10, oracle_escalation, sidekick_tau03,
  sidekick_tau07; rc=0, 2h19) and `25560363` (fixed_k_5, router_seq_tau03/05/07, sidekick_tau05;
  rc=0). Free arms `executor_alone` / `sft_plan` from the 2026-09-19 `_bplus` trees.
- Split: dev, 57 tasks × 2 seeds = 114 pairs. Resample unit: task. Adapter `sft_b_plus_granite8b`.
- `planner_calls` throughout is the **live** ledger count (`totals.planner_calls_total`), not the
  replay-inclusive tick count.
- Oracle semantics: **runs free** (not replayed from a source prefix).
- Headline population: all-episodes, a crashed episode scoring 0. Survivor columns reported
  alongside; a paired survivor contrast drops a (task_id, seed) pair if either side crashed.

## The arm table (reproduce exactly)

```
arm                  n  n_crashed  tgc_all  tgc_surv   gp_all   gp_surv  calls  crash/call%
executor_alone     114          0   0.1316    0.1316   0.5289    0.5289      0          NA
sft_plan           114          0   0.4035    0.4035   0.7000    0.7000    114        0.00
fixed_k_3          114         17   0.2982    0.3505   0.5149    0.6051    768        2.21
fixed_k_5          114         10   0.3772    0.4135   0.6238    0.6838    566        1.77
fixed_k_10         114          3   0.3860    0.3964   0.6447    0.6621    314        0.96
oracle_escalation  114          0   0.3772    0.3772   0.6660    0.6660    148        0.00
router_seq_tau03   114         21   0.2719    0.3333   0.4924    0.6036   1754        1.20
router_seq_tau05   114          0   0.4211    0.4211   0.7121    0.7121    126        0.00
router_seq_tau07   114          0   0.3772    0.3772   0.6837    0.6837    114        0.00
sidekick_tau03     114          0   0.3596    0.3596   0.6694    0.6694    114        0.00
sidekick_tau05     114          0   0.3860    0.3860   0.6694    0.6694    114        0.00
sidekick_tau07     114          0   0.3947    0.3947   0.6601    0.6601    114        0.00
```

`calls` is the arm total over 114 episodes. Per-episode: fixed_k_3 6.74, fixed_k_5 4.96,
fixed_k_10 2.75, oracle 1.30, router_seq_tau03 15.39, router_seq_tau05 1.11, everything else 1.00.

Planner token spend, ledger totals: router_seq_tau03 203,504,742 tokens and USD 4.68 —
7.8× fixed_k_3 (47,289,426) and 136× oracle_escalation (1,496,956). fixed_k_5 26,185,136;
fixed_k_10 10,329,506; router_seq_tau05 6,608,437. The four zero-escalation arms spent 0 planner
tokens (their single plan call per episode was served from cache).

## F1 (rule: `ci95_pp[0] >= -7.00` vs `fixed_k(k_matched)` AND `ci95[1] < 0` calls vs `fixed_k(5)`)

```
arm               holds    k_matched   q_pp     q_ci95_pp   calls_d      calls_ci95   fewer<k5
router_seq_tau03  False    fixed_k_3  -2.63  [-14.91,9.65]   +10.42    [8.45,12.52]      False
router_seq_tau05   True   fixed_k_10  +3.51   [-6.14,13.16]    -3.86   [-4.32,-3.39]       True
router_seq_tau07  False   fixed_k_10  -0.88  [-10.53,8.77]    -3.96   [-4.41,-3.53]       True
sidekick_tau03    False   fixed_k_10  -2.63  [-13.16,7.89]    -3.96   [-4.41,-3.53]       True
sidekick_tau05    False   fixed_k_10   0.00   [-8.77,9.65]    -3.96   [-4.41,-3.53]       True
sidekick_tau07    False   fixed_k_10  +0.88  [-9.65,12.28]    -3.96   [-4.41,-3.53]       True
```

Record the reading plainly: **only `router_seq_tau05` passes, and it passes by 0.86 pp of CI lower
bound.** `sidekick_tau05` has a point estimate of exactly 0.00 pp and fails, because its interval is
wider. At n=114 the F1 verdict is decided by bootstrap interval width, not by measured quality.
State that F1 is therefore not resolvable on dev and must be evaluated on test.

## Oracle headroom (F2)

`oracle_escalation` vs `fixed_k_10` (its k_matched), 114 pairs:
- quality (tgc): diff −0.88 pp, CI95 [−10.53, +9.65] — **no detectable difference**
- live calls: diff −1.46 per episode, CI95 [−1.75, −1.18] — **significantly cheaper**

So F2 as originally framed (oracle *dominates* fixed_k on both axes) is **not established**. What is
established is equal quality at 47 % of the calls (1.30 vs 2.75 per episode) and 14 % of the planner
tokens. Write it that way; do not write "dominates".

## H3 — gate calibration against dev oracle labels (n=848 steps, 43 positive)

```
gate               AUROC    ECE    n_escalations  degenerate
router_seq_tau03  0.6294  0.3066           1533       false
router_seq_tau05  0.4988  0.0531             12       false
router_seq_tau07  0.5000  0.0507              0        true
sidekick_tau03    0.5983  0.0488              0        true
sidekick_tau05    0.6311  0.0488              0        true
sidekick_tau07    0.6759  0.0488              0        true
```

This is the section's most important finding and it must be stated precisely: AUROC is computed on
the gate's **scores** and is therefore well-defined even when the gate never fires. The `sidekick`
self-gate reaches **AUROC 0.6759**, the highest of any gate measured in this project — above A7's
value-function router at 0.6212 and above that router's feature-blind floor of 0.6245 — **while
escalating zero times at every tested τ**. The scores discriminate; the operating point is in the
wrong place. Record this as a **calibration failure, not a discrimination failure**, and note the
caveat that the labels are J6 dev `schedule_live` (a contaminated estimand) with only 43 positives.

## The replicate-noise measurement (new, unplanned, and load-bearing)

`configs/hj8_sidekick_tau03.yaml`, `…tau05.yaml` and `…tau07.yaml` differ **only** in
`verifier.threshold` (0.3 / 0.5 / 0.7) — verified by diff. Decoding is `temperature: 0.7`. All three
escalated zero times and made exactly 114 live calls, so τ had **no causal effect** on behaviour.
The three arms are therefore three stochastic replicates of one policy, and their spread is a direct
estimate of run-to-run noise on this split:

- TGC 0.3596 / 0.3860 / 0.3947 → range **3.5 pp**
- goal_pass 0.6694 / 0.6694 / 0.6601 → range **0.9 pp**

State the consequence: the 7 pp non-inferiority band is only about twice the TGC replicate noise,
and every quality difference among the non-degenerate arms (fixed_k_5 0.3772, fixed_k_10 0.3860,
oracle 0.3772, router_seq_tau05 0.4211, sft_plan 0.4035) lies within or near that range. Note that
goal_pass is the substantially more stable of the two metrics here.

## What the frontier shows about cost

Two arms are genuinely worse on quality and both are the high-call arms: `fixed_k_3`
(0.2982, 17 crashes) and `router_seq_tau03` (0.2719, 21 crashes, 15.39 calls/episode). Per-call
crash rate is not constant across arms (2.21, 1.77, 1.20, 0.96, 0.00 %), which a fixed independent
per-call failure probability would not produce; report the numbers and offer no cause.
`executor_alone` at TGC 0.1316 is far below every other arm and is the one large, unambiguous effect
in the table.

## Constraints

- Append only. Do not renumber, reword or delete any existing section of `RUNS.md`.
- No claim beyond what is in this brief. If a number here looks wrong to you, say so in STATUS
  rather than "correcting" it.
- Do not use the words "dominates", "proves", or "state-of-the-art".

## Return contract

Write `campaign/workers/STATUS_C1.md` as you go. Final report, six lines or fewer: the section
heading you added, its line range in `RUNS.md`, the four sub-findings you recorded (frontier, F1,
headroom, H3+noise), and anything in the brief you declined to write and why. Tag any claim about
the repo `[OBSERVED <path>:<line>]`.
