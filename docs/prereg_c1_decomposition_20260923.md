# Pre-registration: decomposing the matched-trigger channel contrast (B2)

**Status**: **FROZEN on commit** (dev split only; no test data is read or touched). Authorised by the
approved plan of 2026-09-23 07:30, decision §8.2 ("may I freeze it on commit myself, since it touches no
test data — yes"). Amendments are appended below the end marker, never edited in.

**Written**: 2026-09-23, before any B2 episode ran. The two new arms (show, neutral advice) have produced
no data at the time of writing. Seeds 1–2 of the two existing arms (takeover, advice) are already known
(CHAN-C1-02); their seed-3 extensions (B1) have not run.

---

## 1. Why

CHAN-C1-02 is the paper's headline: at the same trigger (a forced review every 10 steps) and the same full
context, spending the hosted planner's budget as an executed action beats spending it as prose advice,
**+6.69 pp** `goal_pass`, scenario [+1.29, +13.48], n = 114.

The two arms differ in more than the channel. Advice is requested with *"The executor needs a correction.
Reply with concise correction text only."* (`build_correct_prompt`, `src/sidekick/agents/planner.py`),
which presumes an error and caps length; the action is requested with *"You are solving the task
yourself…"* (`build_act_prompt`). So C1 bundles three differences:

| difference | takeover | advice |
|---|---|---|
| prompt wording | act prompt | correction prompt (presumes error, "concise … text only") |
| content returned | an action (usually code) | prose |
| delivery | executed in the environment | shown to the executor as an `INTERVENTION:` turn |

Two arms separate them.

## 2. Arms

All four: system `fixed_k`, k = 10, granite-4.2-8b + `sft_b_plus` receiver, identical limits, executor
decoding and planner (`gpt-5.6-luna`, reasoning effort medium). Each replays the **first plan packet** of a
`planner_alone` campaign (`packet_source`): seeds 1–2 from `hj1b_planner_20260915` (cap-25), seed 3 from
`hj13_planner_alone_cap81_seed3_20260924` (cap-81). A plan packet is produced before any action, so the call
cap cannot affect it; the split is disclosed, not corrected.

| code | arm | configs | new? |
|---|---|---|---|
| **T** | takeover | `hj12_takeover_fixed_k_10` (s1–2), `b1_takeover_fixed_k_10_s3` | s3 new |
| **A** | advice, registered prompt, full context | `hj12_advise_fixed_k_10_fullctx` (s1–2), `b1_advise_fixed_k_10_fullctx_s3` | s3 new |
| **S** | **show, don't execute**: planner called exactly as in T; its parsed action is shown as an `INTERVENTION:` turn (rendered by `format_executor_action`) and never executed | `b2_show_fixed_k_10`, `b2_show_fixed_k_10_s3` | new |
| **N** | **neutral advice**: A with `planner.correct_prompt: neutral` — first prompt line *"Advise the executor on how to proceed with this task: say what it should do next. You may include code."*; packet and transcript lines byte-identical to A | `b2_advise_neutral_fixed_k_10_fullctx`, `…_s3` | new |

Implementation: `SystemPolicy.advice_from_act` and the `advice_from_act` branch of the forced-review block in
`src/sidekick/systems/loop.py`; `build_advice_prompt` in `src/sidekick/agents/planner.py`. Tests in
`tests/unit/test_c1_decomposition.py` pin: the default advice style is byte-identical to the registered
prompt; the neutral style differs in the first line only; S's first `planner.act` call receives arguments
identical to T's; nothing S shows reaches `env.step`; an unparseable act reply shows nothing (as T then
executes nothing). The launcher (`scripts/pbs/hj12_live.pbs`) voids an S smoke with zero `shown_action`
interventions when an episode could have reached a review, mirroring the existing takeover guard.

## 3. Estimation

- Unit: paired episode, key `(task_id, seed)`; 57 dev tasks × seeds {1, 2, 3} = **171 pairs** per contrast,
  pooled across campaigns exactly as POOL-01 pools.
- Metric: `goal_pass` primary; TGC secondary (reported, not decision-bearing).
- Interval: paired percentile bootstrap, **scenario-clustered primary** (19 clusters), task-clustered
  secondary, B = 10,000, seed 20260924.
- **POOL-04 applies**: any decision-bearing bound within 1.00 pp of zero is recomputed at bootstrap seeds
  {20260924, 1, 2, 3, 7, 101, 999}; if the verdict differs on any seed the contrast is reported
  **on the boundary**, never as resolved.
- Sensitivity (not decision-bearing): cluster sign-flip permutation p-value, scenario clusters.
- Multiplicity: Holm across the four decomposition contrasts D1–D4 on `goal_pass`.
- Crash convention: an episode is dropped only if `error_type == "crash"`; `limit` is scored. Crashed
  episodes are refilled by resubmission. A contrast is reported only when both arms have all 171 pairs
  non-crashed; otherwise it is reported as incomplete with the count.

## 4. Contrasts and decision rules

| id | contrast | isolates |
|---|---|---|
| D0 | T − A | C1 extended to 171 pairs (114 of them already seen — **reported as an extension, not a replication**) |
| D1 | T − S | **execution** (same prompt, same planner output; executed vs shown) |
| D2 | S − A | **prompt + content** at the same delivery (act prompt/action text vs correction prompt/prose) |
| D3 | N − A | **the advice prompt's wording** (same channel, same content type) |
| D4 | T − N | the channel gap that remains against a fairer advice prompt |

Outcomes, evaluated **in this order**; the first that applies is the headline reading, and every interval
is reported whatever the reading:

1. **Prompt artefact** — D4's scenario CI includes zero *and* D3 > 0 with CI excluding zero: the advice arm
   was handicapped by its wording. C1 is **withdrawn as a channel claim** and reported as a prompt effect.
2. **Execution matters** — D1 > 0 with CI excluding zero. The strong form of the title ("actions, not
   advice") stands, now against a same-content control.
3. **Content, not execution** — D1's CI includes zero *and* D2 > 0 with CI excluding zero. The result is
   re-framed as *code, not prose*: the planner's action text helps as much shown as executed. The title
   changes accordingly.
4. **Unresolved** — none of the above. Intervals reported; no decomposition claim.

Registered expectations (stated so that surprise is visible, not as predictions to be tested): D3 small
and positive; D1 positive but smaller than D0; D4 positive.

## 5. Exploratory (labelled as such wherever reported)

- **Copy rate**: share of S interventions whose shown code the executor reproduces verbatim (after
  whitespace normalisation) as its next action — a direct measure of whether "show" collapses into
  "execute".
- Per-arm hosted calls, non-cached tokens and cost per episode.
- D0–D4 on TGC.

## 6. Budget

Hosted calls, estimated from dev per-episode rates (takeover 2.32, advice 2.46; S assumed ≈ T and N ≈ A):
S 171 × 2.32 ≈ 397, N 171 × 2.46 ≈ 421, T s3 57 × 2.32 ≈ 132, A s3 57 × 2.46 ≈ 140 → **≈ 1,090**. Each job
runs with `MAX_PLANNER_CALLS` ≤ 1,400 so an overrun aborts before the next arm. No luna worker runs in the
same window.

## 7. What this does not do

It does not touch `test_normal` or `test_challenge`. Its dev results decide which arm(s) amendment A1
registers on test as P7 (plan §3, R6); that registration is a separate document the user freezes.

*Pre-registration ends. Amendments below this line, dated, append-only.*

### Amendment 1, 2026-09-23 ~08:55 AEST — how Holm and the interval rules combine (appended before any B2 episode)

Appended while jobs 25724312 and 25724313 were still queued: no `b1_*` or `b2_*` campaign directory existed
under the results root, and no B2 episode had been run. It fills a gap in §3–§4 without changing any arm,
contrast or rule. §3 applies Holm across D1–D4, and §4 phrases every rule as an interval condition, but
neither says how the two combine. The same gap was found in amendment A1 by review, and is resolved here the
same way (A1 r2 §5.3).

1. **p-values.** For each of D1–D4 on `goal_pass`, p is the two-sided-equivalent percentile-bootstrap p at 0,
   taken from the same scenario-clustered bootstrap as the interval: 2 × the share of resampled means on the
   far side of zero (`scripts/analysis/j10_report.py::bootstrap_pvalue`). Holm step-down is applied at
   family-wise α = 0.05 across D1–D4. D0 is not in the family; it is reported as an extension of C1.
2. **"> 0 with CI excluding zero"** (D1 in outcome 2, D2 in outcome 3, D3 in outcome 1) holds only if the
   unadjusted 95% scenario interval excludes zero on the positive side **and** the Holm-adjusted p ≤ 0.05.
3. **"CI includes zero"** (D4 in outcome 1, D1 in outcome 3) is evaluated on the **unadjusted** 95% scenario
   interval. A Holm adjustment would make a non-rejection *easier*, and hence make the prompt-artefact and
   content-not-execution readings easier to reach. Evaluating it unadjusted is the conservative direction for
   both.
4. **Boundary.** When POOL-04 reports a decision-bearing bound as *on the boundary*, that contrast satisfies
   neither "excludes zero" nor "includes zero". Any outcome that needs it cannot fire, and evaluation falls
   through to the next outcome, ending at *unresolved*.
5. **Pooling.** The 171 pairs per arm are the union, keyed by `(task_id, seed)`, of:
   - T: `hj12_takeover_fixed_k_10_20260923` (seeds 1–2) and `b1_takeover_fixed_k_10_s3_20260923` (seed 3);
   - A: `hj12_advise_fixed_k_10_fullctx_20260923` (seeds 1–2) and `b1_advise_fixed_k_10_fullctx_s3_20260923`
     (seed 3);
   - S: `b2_show_fixed_k_10_20260923` and `b2_show_fixed_k_10_s3_20260923`;
   - N: `b2_advise_neutral_fixed_k_10_fullctx_20260923` and `b2_advise_neutral_fixed_k_10_fullctx_s3_20260923`.

   A key present in more than one campaign of an arm is an error, not a choice.
