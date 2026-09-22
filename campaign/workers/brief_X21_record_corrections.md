# Brief X21 — correct the record, and build the claims ledger

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation only. **Do not `qsub`, do not touch a GPU, do not run any evaluation, do not edit
`src/`, `configs/`, `scripts/` or anything under `campaign/results/`.**

## The rule that governs this whole unit

**Registered text is corrected by appending, never by editing.** You may add a new dated section at
the end of a pre-registration or a new subsection to the run ledger. You may **not** alter a
sentence, number or heading that is already there. If you think an existing line is wrong, quote it
in your correction and say why — do not touch it.

## Task 1 — the mechanism claim in the committed record is false

`docs/prereg_hj12_dev_20260922.md` (amendment beginning at `:314`) and `campaign/RUNS.md` §14
(subsection "The Mechanism Claim", at `:2528`) both state that in episodes where no handoff occurred
the executor contributed nothing.

That is false, and it was verified false by direct event counting:

- `hj12_prefix_m9_20260922`: 32 episodes with `handoff_occurred: false`; the executor took **38
  actions** across them.
- `hj12_prefix_m11_20260922`: 60 such episodes; the executor took **113 actions** across them.

At m9 the outcome happened to be identical anyway, so the conclusion survived by accident. At m10 and
m11 it does not: on m11's 60 such episodes the arm scores **0.8685** against the planner's **0.8507**,
+1.78 pp — which is not a bonus but an artefact, because after a replayed prefix that already ended
in `COMPLETE` the live loop still let the executor act with fresh step budget.

Append to **both** files a section headed `## Correction 2026-09-23 — the executor acted in every
"no-handoff" episode` stating: the counts above; that the population name "no-handoff" is wrong and
these episodes are renamed **prefix-exhausted**; that the +1.78 pp is a second attempt under extra
budget, not evidence the executor improves on the planner; and that the runtime defect is being fixed
under X18, after which the affected arms are re-run. Quote the sentences you are correcting.

## Task 2 — record the unified frontier

Add `## 15. The unified frontier — both channels on one cost axis — 2026-09-22` to
`campaign/RUNS.md`, following the house style of §14 (read `campaign/RUNS.md:2451-2540` first and
match its structure: an arm table, then numbered contrasts, then a verdict).

Every number comes from `campaign/results/hj12_unified_frontier_20260922.report.json` and must be
tagged `[OBSERVED campaign/results/hj12_unified_frontier_20260922.report.json:<line-or-key>]`. Read
the JSON; do not copy numbers from this brief without checking them.

The arms in cost order, `goal_pass_rate` and non-cached planner tokens per episode:
`executor_alone` 0.5289 / ~0; `sft_plan` 0.7181 / 23,906; `advise_fixed_k_10` 0.6964 / 43,823;
`advise_oracle_esc` 0.7096; `advise_fixed_k_3` 0.7012 / 204,500; `prefix_m2`, `m4` 0.7340, `m6`
0.7145 / 221k, `m7`, `m8`, `m9` 0.8134 / 357,448, `m10`, `m11` 0.8307 / 443,361;
`planner_alone` 0.8284 / 684,453.

Contrasts to record: `executor_alone − sft_plan` = −18.93 [−25.95, −12.07];
`advise_fixed_k_10 − advise_fixed_k_3` = −0.48 [−7.2, 6.15];
`advise_fixed_k_3 − prefix_m9` = −11.23 [−16.86, −5.76];
`advise_fixed_k_3 − prefix_m11` = −12.95 [−18.92, −7.12];
`advise_fixed_k_3 − prefix_m4` = −3.28 [−9.82, 3.26];
`prefix_m11 − planner_alone` = +0.23 [−5.27, +6.34], `holds` true;
chord test m9 +3.96 [−0.49, 8.88], m11 +4.25 [−0.01, 9.11].

## Task 3 — the honesty section, verbatim

Close §15 with a subsection `### What this section may not be used to claim`, containing exactly
these six qualifications (reword only for grammar):

1. `planner_alone` ran under `max_planner_calls: 25` [OBSERVED `configs/pilot_planner_alone.yaml:25`]
   while every later arm used 81 [OBSERVED `configs/hj8_fixed_k_3.yaml:39-41`]. Every non-inferiority
   statement here is against an understated comparator until that re-run happens.
2. The advice arms' reviewer saw only the last 8 transcript lines
   [OBSERVED `src/sidekick/systems/loop.py:70`, `correct_context_lines: int | None = 8`] while an
   acting planner sees the whole transcript. "Advice is flat" may be "starved advice is flat" until
   `configs/hj12_advise_fixed_k_10_fullctx.yaml` runs.
3. At **matched** budget the two channels are indistinguishable: `advise_fixed_k_3` at 204.5k (30%)
   versus `prefix_m6` at ~221k (32%) is 0.7012 versus 0.7145. The action channel is only observed to
   win at 52–65%, where advice has never been priced.
4. No advice arm is *below* the plan-only floor — `advise_fixed_k_3 − sft_plan` is about −1.7 pp with
   a CI including zero. The correct phrase is **indistinguishable from the floor**, never "never
   reaches it".
5. `prefix_m11`'s non-inferiority holds on all-episodes `goal_pass_rate` only. On TGC it is −7.02
   [−14.04, +0.88] and fails. 53% of its pairs replay the comparator's own recording.
6. m7, m8, m10 and m11 were chosen after seeing the first grid and are exploratory; Gate G1 failed as
   registered.

## Task 4 — the claims ledger

Create `docs/claims_ledger.md`: a table with one row per claim the thesis will make, columns
`claim_id | claim (one sentence) | artifact path | JSON key or line | status | figure`. `status` is
one of `registered`, `amended`, `exploratory`, `pending`. Seed it with every contrast in Task 2 plus
the six qualifications in Task 3. Head the file with the rule: *no number may appear in the thesis
without a row here.*

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. You should need no compute; use `jq` to read the report JSON.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read `test_normal` or
  `test_challenge`.
- Frozen, edit **only by appending a new dated section**: `docs/prereg_hj12_dev_20260922.md`.
  Frozen, **read only, no appends**: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X21.md`, under 500 words: the four files you changed or created, the exact
heading text of each appended section, confirmation that you added no line above any existing
content, and any number in this brief that did **not** match the report JSON when you checked it —
that last point matters more than the rest. Tag every claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
