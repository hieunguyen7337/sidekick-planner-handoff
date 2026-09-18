# A14 (U-TRAIN) — the trainer silently drops sequences; make the drop visible

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/train/sft_lora.py` and a test under `tests/unit/`.
**Do not touch** `configs/`, `scripts/pbs/`, `scripts/setup/`, `scripts/analysis/`, `src/`,
`docs/`, `campaign/RUNS.md` — other units own those.

🔺 **Do not retrain anything. Do not submit any GPU job.** A GPU harness job is running right now
and the adapter this concerns is already trained and in use. This unit is instrumentation only.

## The defect, measured tonight

J5a trained the `sft_b_plus` control adapter and finished clean (exit 0, 2h01m, final train loss
0.1085). But its run manifest records **`n_sequences: 479`**
[OBSERVED /scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_granite8b/manifest.json] while
the input file has **497 lines**
[OBSERVED `wc -l /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl`].

**Eighteen sequences vanished and nothing records that they did.** The cause is here:

```python
example = tokenize_sft_row(row, tokenizer, max_length=MAX_LENGTH)
if not any(lab != -100 for lab in example["labels"]):
    continue
tokenized.append(example)
```
[OBSERVED scripts/train/sft_lora.py:127-131]

A row is truncated to `MAX_LENGTH = 32768` [OBSERVED scripts/train/sft_lora.py:35] and then, if
truncation has cut away the whole supervised span so every label is `-100`, the row is skipped by
a bare `continue`. No warning, no count. The manifest then reports `len(tokenized)`
[OBSERVED scripts/train/sft_lora.py:245] — the number that **survived**, which is silently not the
number that went in.

This is the defect class this campaign keeps hitting: a pipeline that reports a believable number
instead of reporting what it discarded. It is also non-random — the rows that lose their labels are
systematically the **longest** episodes, so the exclusion is correlated with difficulty.

For context, the data-build step gets this right: `sft_b_plus.jsonl.manifest.json` records
`correction.n_truncated = 21` **and lists the truncated run ids**
[OBSERVED data/interim/sft_b_plus.jsonl.manifest.json]. The trainer should be at least as
honest as the step feeding it.

## What to do

**Count and record, do not change what is trained.** The drop itself is correct behaviour: a row
with no supervised tokens teaches nothing, and these sequences run to ~102k tokens against a vLLM
`max_model_len` of 32768, so they cannot be served at inference either. Truncation is unavoidable
and dropping a fully-masked row is right. **The silence is the bug.**

So:

1. Count the rows skipped by that `continue`, and record it in the manifest — a count at minimum,
   and the **row identifiers** if the input carries one (the data-build manifest lists run ids, so
   check whether the same identifier is available on the row and use it if so).
2. Distinguish the **reasons** if they are distinguishable: a row that was fully masked *before*
   truncation is a different problem from one truncated past its labels. Report them separately if
   you can tell them apart; if you cannot, say so rather than guessing.
3. Also record how many rows were **truncated but kept** — those still lost content, and right now
   nothing downstream can tell.
4. Print a visible warning when anything is dropped. A silent 3.6% loss should not require
   arithmetic on two files to notice.
5. Keep `n_sequences` meaning what it means today (rows actually trained on) so nothing downstream
   breaks — **add** fields, do not repurpose existing ones.

## Tests

- A synthetic row whose labels are entirely masked is counted as dropped, not silently skipped.
- A row that is truncated but retains supervised tokens is kept **and** counted as truncated.
- The manifest contains the new counts, and `n_sequences` still equals the number trained on.
- A known-answer case: N rows in, k droppable by construction, assert `dropped == k` and
  `n_sequences == N - k`.

## Report the retrospective number

Determine, and state in your report, how many of the 497 rows in
`/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl` would be dropped under the
current rule, and whether that equals the 18 implied by the manifest arithmetic. Tokenising 497
rows is CPU work — run it **in a PBS job**, synchronously, and do not load the model, only the
tokenizer. If that is too heavy, say so and explain what you did instead rather than asserting a
number you did not compute.

⚠ This is the control adapter for the whole J8 frontier, so whether the answer is 18 or something
else is worth knowing precisely. **Do not retrain it** — the finding is a caveat to record, not a
reason to redo two GPU-hours.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job, **synchronously**:
  `timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`. A job that returns in ~1 second has
  crashed; read its output before believing it.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job. Do not retrain.**
- 🔺 **Do not modify anything under `/scratch/.../results/` or `/scratch/.../adapters/`.** Read the
  manifest and the data file; never write them.
- **Do not commit.** Suite baseline **402 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_14.md` in your first three actions, updated per milestone.
- Report → `campaign/workers/A14_SILENT_DROP.md`.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff and the test output as emitted.
- The retrospective count for `sft_b_plus_20260918.jsonl`, and whether it matches 18.
- Which drop reasons you could separate, and which you could not.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
