# D1 — what was the executor actually trained on? (read-only)

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**READ-ONLY UNIT.** Do not modify, create or delete any file except the one STATUS file named below.
Do not run training, evaluation, or any multi-minute command. Do not run `python`, `pip`, `tar`,
`rsync` or `ffmpeg` — `aquarius01` is a shared HPC login node and compute belongs in a PBS job. You
should need only `grep`, `sed`, `head`, `wc` and `ls`, each under `timeout`. Do not run git. Do not
`qsub`.

## The question

The executor adapter `sft_b_plus_granite8b` follows a frozen planner's initial plan very well
(+27.19 pp task-goal-completion over the un-adapted executor) but gains nothing from mid-episode
planner interventions — even interventions chosen by an oracle. One candidate explanation is that
**the executor was never trained on trajectories that contain a mid-episode intervention**, so at
intervention time its context is off-distribution.

Establish, from the training-data build code and the dataset files, exactly what went into
`sft_b`/`sft_b_plus`, and answer these five questions:

1. **Does any training example contain a planner intervention in its context?** That is, an
   assistant/user turn injected mid-episode carrying planner advice, as opposed to the initial plan
   only. Give the count and the fraction of examples, and quote the code that constructs it.
2. **What is the mixture?** How many examples, from which source campaigns/splits, and what are the
   example types (plan-following, correction, ASK, anything else). A table of type → count.
3. **What exactly is an "ASK target"?** Where is it constructed, what does the target text look
   like, and how many exist in `sft_b` and in `sft_b_plus` respectively. If the count is zero for
   either, say so and cite the code path that would have produced them.
4. **Is the intervention text format at training time identical to the format used at evaluation
   time?** Compare the string/template the training builder emits against the template the runtime
   loop injects when the planner intervenes. If they differ in any way — role, prefix, ordering,
   whitespace — say precisely how. A mismatch here would be a decisive finding.
5. **How many distinct tasks and episodes underlie the training set?** The AppWorld train split is
   90 tasks; report how many episodes and steps that became, and whether any augmentation or
   resampling was applied.

## Where to look

Start from these and follow the imports; do not guess at file names:

- `src/sidekick/` — the runtime loop and prompt construction (the evaluation-time format lives here;
  look for where an intervention is injected into the message list, and for the prompt templates)
- `scripts/setup/` — the dataset builders
- `configs/` — the training configs naming the adapters
- `docs/PLAN.md` and `docs/prereg_v1.md` — the intended design, useful for spotting where intent and
  code diverge
- `campaign/RUNS.md` — the record of what was actually built and when

Dataset files may live under `/scratch/n12194778/sidekick/`. You may **read** anything there. Do not
write there. If a dataset file is large, use `wc -l` and `head -c` rather than reading it whole.

## Return contract

Write `campaign/workers/STATUS_D1.md` with the answers, then report back the same content in
**fifteen lines or fewer**.

Every factual claim must be tagged `[OBSERVED <path>:<line>]` or `[INFERRED]`. A claim about a file
format or a template must quote the literal string and cite the line that emits it. If you cannot
establish something, write `UNDETERMINED` and say what you looked at — do not supply a plausible
answer. Distinguish clearly between what the code does and what the documentation says it does;
where they disagree, that disagreement is the finding.
