# BFCL `multi_turn_base` dev design (Wave E): dev preregistration

**Status**: FROZEN 2026-09-25, as revised (§8); amended only by appending below §8

Written 2026-09-24 by unit BFCL-E2 (`campaign/workers/briefs/20260924_bfcl_e2_build.md`) for review. It covers the
BFCL **dev** split only. The dev read is exploratory: it gives effect sizes and power for a BFCL test preregistration
(the E-prereg), and it makes no confirmatory claim.

Revised 2026-09-25, before any hosted or replay dev episode existed, to add a third receiver (`qzs`) and a third
seed. §8 is the revision and freeze record.

Sources: plan `docs/plan_top_venue_20260924.md:84-85` and `:146-162`; environment record `docs/bfcl_env_20260924.md`;
scoping `docs/second_env_scoping_20260923.md` §0, §2 and §3.

## 1. Environment and split

- **Environment.** BFCL v4 `multi_turn_base`, vendored from gorilla @ `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` into
  `third_party/bfcl/` (covered by `SHA256SUMS`). The adapter is `src/sidekick/environments/bfcl_env.py`.
  - One episode is one entry. A scripted user speaks in 1 to 6 turns on dev (spike c `turn_stats`).
  - Caps: `max_steps` 40, plus upstream's 20 CODE steps per turn.
- **Split file.** `data/bfcl_split_20260924.json`: keys `seed` = 20260924, `n_dev` = 50, `n_test` = 150.
- **How it was drawn.** `scripts/setup/bfcl_split.py` calls `build_split` (`bfcl_env.py`):
  - the 200 entry ids are put in numeric order and shuffled with `random.Random(20260924)`;
  - the first 50 become dev and the other 150 test, each re-sorted numerically.
- **Unstratified**, because the scoping doc names no stratum. `test_committed_split_is_the_builder_output`
  (`tests/unit/test_bfcl_env.py`) pins the file to the builder.
- **Metrics** (`BfclEnv.evaluate`):
  - `goal_pass_rate` is the share of checked turns that pass both of upstream's per-turn checks;
  - `success` (= `tgc`) is upstream's pass verdict for the whole entry, so it is binary per episode.
  - As in J10, `goal_pass_rate` is primary and `success` is secondary.

## 2. Spike gates (E1): all three passed, on dev only, with zero hosted calls

| spike | gate | result (report key) | artifact |
|---|---|---|---|
| a: environment fidelity | every ground-truth run reaches its expected state; hashes agree 100 %; a no-op passes nothing | `gate.pass` true; `counts.adapter_success` 200 of `n_entries` 200; `n_prefix_replays_hash_ok` 4,152 of `n_prefix_replays` 4,152; `noop_goal_pass_rate_mean` 0.0 | `campaign/results/bfcl_spike_a_20260924.report.json` |
| b: headroom | `executor_alone` (Granite 4.2, zero-shot) succeeds on ≤ 50 % of dev | 36 of 100 `success`, 0 `crash` (job 25838016) | `results/bfcl_executor_alone_zs_dev_20260924/runs.jsonl` under `/scratch/n12194778/sidekick/results/` |
| c: handoff depth | ≥ 70 % of dev entries still hand off at the deepest grid depth | `gate.pass` true at `gate.deepest_m` 7, `gate.share` 0.7 | `campaign/results/bfcl_spike_c_20260924.report.json` |

## 3. Depth grid: m ∈ {2, 4, 6}

This grid was decided by Claude on 2026-09-24 (`docs/bfcl_env_20260924.md`, "Decision").

- **What spike c's rule proposed.** `grid_rule` gave `proposed_grid` [2, 5, 7].
- **Why not m = 7.** At m = 7 the per-call share is exactly the 0.70 gate: 35 of 50 dev entries. A test split with
  slightly shorter trajectories would fail it.
- **Why {2, 4, 6}.** It is the scoping doc's example grid. Its per-call shares are 1.00, 0.96 and 0.84
  (`doc_example_grid_steps`), so 0.84 still hand off at its deepest depth.
- **The batched bound does not separate the grids.** Under `share_handing_off_by_m_batched` both grids fall to 0.5 at
  their deepest depth. The two grids differ only on the per-call count, and there {2, 4, 6} has the margin.
- **The cost** is one step less span.

## 4. The dev arms

Every arm runs on 50 dev entries × seeds 1, 2, 3 = **150 episodes**. Each has a config `configs/bfcl_<arm>.yaml`,
with `campaign_id` `bfcl_<arm>_dev_20260924`, and is submitted only through `scripts/pbs/bfcl_arm.pbs` with
`SEEDS=1,2,3`. Spike (b) already holds seeds 1 and 2 of `executor_alone_zs`, so only its seed 3 remains to run.

**The three receivers.**
- `zs` is the primary receiver: zero-shot `ibm-granite/granite-4.2-8b`. Its executor block is the one spike (b) ran.
- `bplus` is the AppWorld-tailored adapter `sft_b_plus`, served from
  `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b` (the J10 adapter). It runs out of
  domain, because BFCL has no train split.
- `qzs` is a second executor family: zero-shot `Qwen/Qwen3-8B`, with the executor block of AppWorld's zero-shot Qwen
  arms (`configs/hj15_executor_alone_zsq.yaml`). It is added on dev only. It asks whether the channel and depth
  contrasts hold across executor families in a second environment. On AppWorld, the Qwen family exists on dev only
  (QWEN-* rows).

| arm | runner system | receiver | k / m | replays | J10 template |
|---|---|---|---|---|---|
| executor_alone_zs | executor_alone | zs | — | — | `j10_executor_alone` (spike b; already complete) |
| executor_alone_bplus | executor_alone | bplus | — | — | `j10_executor_alone_bplus` |
| planner_alone_cap81 | planner_alone | — (no executor) | — | — (the only arm that plans) | `j10_planner_alone_cap81` |
| plan_zs | prompt_only | zs | — | first plan of planner_alone_cap81 | `j10_sft_plan` |
| takeover_k5 | fixed_k, `takeover: true` | zs | k = 5 | first plan | `j10_takeover_k10` |
| advise_k5_fullctx | fixed_k, correction prompt | zs | k = 5 | first plan | `j10_advise_k10_fullctx` |
| advise_k5_neutral | fixed_k, neutral prompt | zs | k = 5 | first plan | `j10_advise_k10_neutral` |
| prefix_zs_m2, _m4, _m6 | prefix_handoff | zs | m = 2, 4, 6 | first m actions of planner_alone_cap81 | `j10_prefix_zs_m9` |
| prefix_bplus_m2, _m4, _m6 | prefix_handoff | bplus | m = 2, 4, 6 | first m actions | `j10_prefix_m9` |
| executor_alone_qzs | executor_alone | qzs | — | — | its zs sibling |
| plan_qzs | prompt_only | qzs | — | first plan | `plan_zs` |
| takeover_k5_qzs, advise_k5_fullctx_qzs, advise_k5_neutral_qzs | fixed_k (as their zs siblings) | qzs | k = 5 | first plan | their zs siblings |
| prefix_qzs_m2, _m4, _m6 | prefix_handoff | qzs | m = 2, 4, 6 | first m actions | `prefix_zs_m*` |

- **Planner.** `gpt-5.6-luna` at medium effort, with a cap of 81 planner calls: the planner block of J10 arm 3.
- **The channel arms** run on `zs` and `qzs`, at k = 5. That is AppWorld's k = 10 rescaled for BFCL's shorter
  episodes (scoping §3). They do not run on `bplus`, as before.
- **plan_zs runs `prompt_only`, not `sft_plan`.**
  - `sft_plan.py:18` defaults `adapter_name` to `sft_plan` when `executor.lora_name` is null. That would request
    a model the server does not serve.
  - `prompt_only` is the same policy without that default. `configs/hj15_prompt_only_zsq.yaml` is the precedent.
- **Order.**
  1. planner_alone_cap81 runs first.
  2. The wrapper refuses a replay arm until that campaign holds 50 non-crashed episodes per requested seed (150
     for seeds 1, 2, 3), with 0 crashed and 0 unreadable.
  3. Past 5 % planless source episodes, the replay arm is refused (J10 A1 §4.2's rule).

## 5. Hosted-call budget

- **Per-episode figures** come from scoping §3: `planner_alone` 12, a channel arm 3, a prefix or `executor_alone`
  arm 0. `plan_zs` spends calls only on executor asks, costed at 1 per episode.
- **The dry run** is scoping §3's 100 calls, raised to 150 for the four `qzs` hosted arms. It covers the
  first-submission smokes of the hosted arms (2 episodes each).
- **The free arms** are 9 prefix arms × 150, `executor_alone_bplus` and `executor_alone_qzs` × 150, and seed 3 of
  `executor_alone_zs` (50; spike b holds its seeds 1 and 2): 1,700 episodes.
- **Retries** are 10 % of the arms plus the dry run, as in scoping §3.

| item | hosted calls / episode | episodes | hosted calls |
|---|---|---|---|
| planner_alone_cap81 | 12 | 150 | 1,800 |
| plan_zs | 1 | 150 | 150 |
| takeover_k5 | 3 | 150 | 450 |
| advise_k5_fullctx | 3 | 150 | 450 |
| advise_k5_neutral | 3 | 150 | 450 |
| plan_qzs | 1 | 150 | 150 |
| takeover_k5_qzs | 3 | 150 | 450 |
| advise_k5_fullctx_qzs | 3 | 150 | 450 |
| advise_k5_neutral_qzs | 3 | 150 | 450 |
| prefix arms (9) and executor_alone (zs seed 3, bplus, qzs) | 0 | 1,700 | 0 |
| subtotal, arms | | | 4,800 |
| dry run | | | 150 |
| retries, 10 % of 4,950 | | | 495 |
| **total** | | | **5,445** |

Beside scoping §3's E1 gate (≈ 2,100), this adds `advise_k5_neutral`, `plan_zs`, the `qzs` receiver and seed 3.
At ≈ $0.0020–0.0027 per call it is ≈ $11–15 of luna list-price usage, about a quarter of a Plus week
(`docs/plan_luna_reset_20260925.md` §0).

**Per-arm ceilings.** `bfcl_arm.pbs` stops a hosted arm when its live calls, plus a projection for its missing
episodes, would exceed `MAX_PLANNER_CALLS`. The default is the high end × the target episodes (150):
- planner_alone_cap81: 16 → 2,400;
- a channel arm: 4 → 600;
- plan_zs and plan_qzs: 2 → 300.

The replay arms are gated on zero live planner calls.

⚠ **The ledger counts a replayed plan as one call.** `loop.py:465` sets every planner response's `n_calls` to its
attempt count, so the cached plan (`provider` `cache`) adds 1 per episode to `ledger_totals.planner_calls_total` of
every plan-replay arm, although nothing was bought. The ceilings above count hosted calls, which is the ledger key
minus the cached records. The dev read reports hosted calls the same way.

## 6. The dev read (exploratory)

**Per arm.** `goal_pass_rate` (primary) and `success` (secondary), plus:
- the `limit` rate and the crash count;
- live planner calls per episode (`ledger_totals.planner_calls_total`).

**Pairing.** Contrasts are paired by (entry, seed). They use a cluster bootstrap over the 50 entries (3 seeds each),
because BFCL has no scenario grouping like AppWorld's.

**The contrasts it prepares, mirrored from J10.** Each gets a point estimate, a paired interval and the per-pair SD
that sizes the E-prereg's power.
- **P6**: `takeover_k5 − advise_k5_fullctx`. Does the action channel beat correction advice at a matched trigger?
- **CF1**: `advise_k5_neutral − advise_k5_fullctx`. The advice prompt, with the plan held fixed.
- **P3 and its handoff-only B1 companion**: `prefix_m6 − planner_alone_cap81`, non-inferiority.
  - J10's P3 is the tailored arm, so `prefix_bplus_m6` is the mirror. `prefix_zs_m6` is read beside it, because `zs`
    is BFCL's primary receiver.
  - The companion is the handoff-only estimand Σd·h*/Σh*, with h* taken from the target arm.
  - h* is read from each prefix episode's own `events.jsonl` by `scripts/analysis/handoff_control.py`, not from
    `handoff_occurred`.
- **Depth span, m2 → m6**: `prefix_m6 − prefix_m2`, per receiver, with the m4 arm reported between them.
- **Described, not tested**: `executor_alone_bplus − executor_alone_zs` (tailoring out of domain) and
  `plan_zs − executor_alone_zs` (one plan).
- **The second executor family (`qzs`), described.**
  - P6, CF1, the depth span and the no-plan floor are repeated on `qzs`.
  - Each receiver's contrast is reported beside the other's. The receiver difference is reported as a
    difference-in-differences with its interval.
  - Nothing on `qzs` is tested.

**What it does not decide.** No dev number carries a decision rule. The E-prereg fixes the following before any
test episode:
- the NI margin for P3;
- which receiver P3 registers;
- the Holm families;
- the bootstrap seed.

## 7. The test-contact rule

- **No BFCL `test` episode until a BFCL test prereg is committed with a FROZEN Status line.** That includes smokes
  and dry runs.
- **How this is enforced today.**
  - `bfcl_arm.pbs` refuses any `SPLIT` but `dev`, and any campaign id without `_dev_`.
  - `bfcl_task_ids` refuses any split name but `dev` and `test`.
- **When the E-prereg lands.** A test submission path is added to the wrapper then, gated on its FROZEN Status line
  as `j10_arm.pbs` gates on A1's.

## 8. Revision and freeze record

- **Revision (2026-09-25).** It added the `qzs` receiver and its 8 arms, and seed 3 on every arm. It also scaled §4's
  replay gate, §5's budget and ceilings, and §6's pairing, and added the `qzs` read in §6. The source is the user's
  decisions of 2026-09-25 ("Do all the recommended decisions", on `docs/plan_luna_reset_20260925.md` §5).
- **BFCL dev data that existed at freeze.** Spikes a and c are ground-truth and share checks with no executor. Spike
  b is `executor_alone_zs`, seeds 1 and 2, 100 episodes, 36 successes. Its aggregate appears in §2. No hosted, replay,
  prefix or `qzs` dev episode existed.
- **Freeze.** The Status line reads FROZEN from the commit that records this section. After that the document is
  amended only by appending below this section, never by editing above it.

## 9. Amendment 1: hosted-arm launch ceilings (2026-09-26, before any hosted BFCL episode)

- **What changes.** Only §5's per-arm launch brake `MAX_PLANNER_CALLS` changes, and only for these arms:
  - each of the six channel arms (`takeover_k5`, `advise_k5_fullctx`, `advise_k5_neutral`, on `zs` and on `qzs`):
    600 → **1,200** (8 per episode × 150);
  - `plan_zs` and `plan_qzs`: 300 → **600** (4 per episode × 150).

  `planner_alone_cap81` stays at 2,400. The value is passed per arm as `MAX_PLANNER_CALLS`, which `bfcl_arm.pbs:67,507`
  already accepts. Nothing else changes: the arms, §5's per-episode figures and budget table, the seeds, the replay
  gates, §6's dev read and §7's test-contact rule all stay as frozen.
- **Why.** `bfcl_arm.pbs` launches a hosted arm only if a 2-episode smoke keeps the projected spend under the
  ceiling (`bfcl_arm.pbs:552-567`). The smoke is the first two dev entries at seed 1; the projection is the smoke's
  live calls per episode × 150 × SAFETY 1.2.
  - In the executor-alone smokes, the two smoke entries averaged 21 steps (`qzs`) and 24 (`bplus`).
  - Across the full arms, episodes averaged 15.53 (`zs`), 18.49 (`bplus`) and 20.09 (`qzs`) steps.
  - 21 steps is BFCL's per-turn force-quit.
  - A k = 5 channel arm reviews at every 5th step, so its smoke would make about 8-10 live calls and project 720-900.
    Every channel arm would therefore be refused before its first scored episode.
  - A plan-replay arm spends live calls only on executor asks. Under the old 300 ceiling it is refused if its two
    smoke episodes ask the planner 4 times; under 600 it is refused at 7 asks.

  The ceiling is a brake against runaway spend, not the expected spend. §5's 3 calls per episode came from scoping
  §3, which did not model the force-quit length; at k = 5 that length makes about 4 reviews per episode typical.
- **Data seen.** Only executor-alone dev data: the three 150-episode arms and their smokes, from which the step
  counts above were read. No hosted, channel, plan-replay or prefix BFCL episode existed at this amendment, so no
  outcome it governs could inform it.
- **Cost.** At about 4 calls per channel episode, the six channel arms spend about 900 calls more than §5's 2,700.
  The new ceilings allow at most 4,200 more calls than the old ones. The luna allowance is a subscription whose spend
  the user approved on 2026-09-25.
- **Source.** The user, 2026-09-26: "follow the recommendation if you believe it can truly help". The recommendation
  came from a readiness audit of the week-A burn driver.

*Amendment 1 ends.*
