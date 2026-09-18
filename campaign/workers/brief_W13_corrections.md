# W-13 — are the harmful corrections WRONG, or merely UNNECESSARY?

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## The question, and why it is the only one that matters here

A fixed five-step expert review measurably hurts about one call in six on the train split.
The quantitative work is already done and it points at **allocation** rather than **format**:
a third of all review calls fire at points where the episode was already going to succeed,
and at those points a review can only do damage.

But that analysis cannot see the *text*. So the discriminating question is:

- **Merely unnecessary** — the correction is sound advice that the executor did not need, and
  the damage comes from it perturbing a trajectory that was already working. This supports
  the allocation reading: fix *when* the reviewer is called.
- **Actually wrong** — the correction misreads the state, contradicts work already done, or
  gives advice that is incorrect for the task. This supports the format reading: fix *what*
  the reviewer is shown and asked.

Both may be present. Your job is to say **in what proportion**, with evidence.

## Input — one file

`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/harm_sample_corrections.jsonl`

JSONL. The first 40 records are the **most harmful** intervention points (most negative
`delta`), then a literal separator line `=== MOST HELPFUL BELOW ===`, then the 40 **most
helpful**. Fields: `delta`, `step`, `i`, `replay_k`, `n_later`, `task_id`, `seed`, `corr`
(the correction text the expert injected).

🔺 **Read both halves.** You are calibrating, not just describing. A property you find in the
harmful corrections only counts if it is *rarer* in the helpful ones. Report the rate in both
groups for every claim. This is the single most important instruction in this brief — a list
of features of harmful corrections with no helpful-group baseline is worthless and I will
discard it.

## Context you need to judge "wrong"

The environment is AppWorld: an executor writes Python that calls `apis.<app>.<method>(...)`
against simulated apps (venmo, file_system, gmail, spotify, …), and finishes with
`apis.supervisor.complete_task(...)`. The reviewer is a hosted planner that sees **only the
last 8 lines of the transcript** plus an instruction — it does **not** see the full history,
and it never sees the action the executor was about to take. Its correction is then injected
**unconditionally**: the executor is forced to follow it.

That limited view is the mechanism most likely to produce genuinely wrong advice, so look
specifically for corrections that:

- re-instruct the executor to do something the transcript shows it **already did**;
- contradict an earlier established fact (a path, an id, a credential, a filter);
- assume a state the episode is not in;
- prescribe a specific API call or argument that looks mistaken for the stated task;
- are vague or generic enough to be unactionable.

## Classify every one of the 80

Give each record exactly one primary label:

1. `redundant` — sound, but restates or reinforces what the executor was already doing.
2. `sound_but_unneeded` — sound and new, but addresses something that was not the problem.
3. `contradicts_history` — conflicts with what the transcript already established.
4. `wrong_for_task` — incorrect advice on its face.
5. `vague` — too unspecific to act on.
6. `unclear` — you genuinely cannot tell from the text alone. Use this honestly; do not
   guess to fill a category.

Then report, as a table: the count of each label in the **harmful 40** and in the **helpful
40**, side by side.

## Also report

- Any correction that is **near-duplicated** across records for the same `task_id` — the same
  advice being re-injected at successive reviews. Give counts. This bears directly on a
  measured effect (harm rises with the number of reviews still to come), so it matters
  whether the reviewer repeats itself.
- The mean `corr` length in each group.
- Three verbatim examples that best illustrate the dominant harmful pattern, quoted exactly,
  each with its `delta` and `task_id`.
- Your own one-paragraph verdict on the allocation-vs-format question, stated as a
  proportion, not an impression.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. **Read and report only.** Do not run
  training, evaluation, or any multi-minute command. You should need no compute beyond
  reading one 30 KB file.
- No `python`, `pip`, `tar`, `rsync` or `ffmpeg` on the login node. If you want to count
  something, count it by reading, or use
  `env TMPDIR=/tmp HPC_SPOOL=/tmp/hpc-w13-spool timeout 300 hpc -c 2 -m 8gb -t 00:10:00 bash -lc '<cmd>'`.
- **Do not submit any GPU job.** Two J6 jobs are live.
- **Do not commit.** Write your findings to `campaign/workers/W13_CORRECTIONS.md` and change
  nothing else.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

Short and quantitative. The classification table, the duplicate counts, the three quotes, the
verdict. Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`; reproduce any
quoted correction text with a literal `grep -c` in the same run so a fabricated quote is
caught.
