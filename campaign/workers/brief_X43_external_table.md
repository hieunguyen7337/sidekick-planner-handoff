# Brief X43 — the external comparison table and the limitations text it needs (F7)

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**DOCUMENT WRITING ONLY. Do NOT run `hpc`, `qsub`, `pytest`, `python`.** Do not edit any `.py`, `.yaml`
or `.pbs` file. Write your first file within your first three actions. **Do not commit.**

## Why

A reviewer's first instinct with an AppWorld paper is to compare our numbers to the leaderboard and ask
why ours are lower. Our headline dev figures sit near 0.72–0.83 goal-pass while published AppWorld
systems report higher test-split numbers. That gap has **four concrete, documentable causes** and none of
them is "our method is worse" — but unless the comparison is laid out honestly and precisely, the paper
reads as if we are hiding it. This unit writes that table and that paragraph.

**This is not a claim that we beat anyone.** Our numbers are dev-split, internal, paired, and measured
under a deliberately minimal loop. The table's job is to let a reader place us, and the text's job is to
say plainly what is and is not comparable.

## Output 1 — `docs/external_comparison_20260923.md`

A table of published AppWorld results with, for each row: system name, base model(s), split
(`test_normal` / `test_challenge` / dev), the metric as that paper reports it (goal-pass / TGC / SGC —
say which), the number, the year, and a full citation with a URL. Cover at least: the AppWorld paper's
own Table 3 baselines, LOOP, CANOPY (Qwen3-14B, ~86.9 on `test_normal`), ACE, Early Experience,
AppWorld-UL, and the public leaderboard entry for `gpt-5.6-luna` (85.1 / 73.2 on `test_normal` /
`test_challenge`).

🔺 **Every number must carry `[OBSERVED <url>]` with the URL you actually fetched.** If you cannot fetch a
source, write `[UNVERIFIED — could not fetch]` and leave the cell blank rather than filling it from
memory. A wrong external number in a comparison table is worse than a missing one, and this project has
already been burned by confidently-stated unverified claims. Seed material you may reuse, but must still
re-verify: `campaign/workers/lit/extracts_20260922.md`, `docs/literature_matrix.md`.

Beneath the table, a clearly separated block of **our** dev numbers, each with its `docs/claims_ledger.md`
claim id — do not retype any number that has no ledger row:

| arm | goal_pass | note |
|---|---|---|
| executor alone (granite 8B + adapter) | 0.5289 | cross-build floor, ADV-FC-02 |
| one plan (`sft_plan`, iaware build) | 0.7181 | |
| advice k=10, full context | 0.7339 | ADV-FC-01 |
| takeover k=10 (action channel, matched trigger) | 0.8007 | CHAN-C1-01, point estimate only |
| action prefix m=9 / m=11 | 0.7852 / 0.8098 | |
| ceiling, **cap-25** | 0.8284 | name the cap, CEIL-08 |
| ceiling, **cap-81** | 0.7637 | independent sample, CEIL-07 |

## Output 2 — `docs/limitations_external_20260923.md`

Four short, specific paragraphs. No hedging filler; each states a fact and its consequence.

1. **Scaffold.** Published AppWorld systems use the official scaffold; we use a deliberately minimal
   loop. Quote the measured difference in mean interactions per episode (about 9.3 for the official
   scaffold versus about 14.4 for ours) and cite where that is recorded. State that we chose the minimal
   loop to isolate the mechanism, citing `docs/PLAN.md:25` ("prove the mechanism, not beat the
   leaderboard"), and that a scaffold-calibration run was explicitly considered and declined.
2. **Split.** Everything we report is **dev**. No `test_normal` or `test_challenge` number is ours; the
   confirmatory test-split run is gated behind `docs/prereg_j9_freeze_20260920.md` §8.1 and has not been
   authorised. So our numbers and the leaderboard's are **not on the same axis** and no ranking between
   them is claimed.
3. **Task count.** The pinned data release ships **57 of the 60** dev tasks; cite
   `docs/feasibility/g2_appworld.md:30-37` for why. Say what that does to comparability.
4. **Effort and model.** Our planner is `gpt-5.6-luna` at `reasoning_effort: medium`, chosen and frozen
   for cost; the leaderboard entry for the same model family need not be at the same effort. Say so.

Add a fifth short paragraph on **what our numbers are good for**: they are paired within task and seed
across arms that share the same replayed planner trajectories, so *differences between our arms* are far
better resolved than any cross-paper comparison, and that is what every claim in this thesis rests on.

## Constraints

- `aquarius01` is a **login node**: no `python`, `pip`, `pytest`, `hpc`, `qsub`, `tar`, `rsync`. Never
  background anything. `timeout` on anything you do run.
- Never read or list `test_normal` / `test_challenge` **data**; citing published test-split numbers from
  papers is fine and is the point of this unit.
- Do not edit anything under `docs/prereg_*` (frozen), `src/**`, `configs/**`, `scripts/**`.
  **Do not commit.**
- Where a number of ours disagrees with `docs/claims_ledger.md`, **the ledger wins**; say so in STATUS.

## Return contract

`campaign/workers/STATUS_X43.md`, under 400 words: the two files written; how many external rows you
verified by fetching versus marked `[UNVERIFIED]`; the URLs fetched; every one of our numbers with its
ledger claim id. `[OBSERVED <url>]` / `[OBSERVED path:line]` / `[INFERRED]` on every claim.
