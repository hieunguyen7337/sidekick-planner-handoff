# Brief X27 — does the threshold exist for a second executor family, or only for granite?

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Code, configs and one training job. **Do NOT `qsub` the training or evaluation jobs — write the exact
commands and I run them.** Other jobs are running; do not disturb them.

## Why this unit decides whether we have a finding or an anecdote

Everything measured so far uses one executor: `ibm-granite/granite-4.2-8b`. The campaign's central
empirical claim is that quality is flat across the first third of a planner episode and then rises —
a *threshold*, not a gradual accrual. As it stands that is a statement about one model.

`docs/prereg_hj13_shape_20260923.md` §4 registers this as the **confirmatory** replication, with the
prediction written down before the data exist: the threshold holds and the breakpoint lands within
±2 steps of granite's. §4 also states the falsification — if the second family rises smoothly from
$m=2$, or does not rise at all, then "threshold" is a property of one model and the thesis says so.

Because the planner trajectories are already recorded, this costs **zero hosted calls**. It is the
cheapest confirmatory evidence available to this project.

## Task A — let the training pipeline take a base model

Four places hard-code the granite identifier:

- `src/sidekick/training/matched_sft.py:551`, `:567`, `:689`
- `src/sidekick/training/sft_data.py:31` (`_DEFAULT_TOKENIZER_ID`)

`scripts/pbs/train_sft.pbs:41` already reads `BASE_MODEL` from the environment [OBSERVED], so the
seam exists at the job level and stops at the Python.

Thread the base-model / tokenizer identifier through so it is set in one place and defaults to the
current granite value. **Default behaviour must be byte-identical**: a run that sets nothing must
produce the same tokenisation and the same rows as today. Prove that with a test, not an assertion in
prose — the risk here is a silent tokenizer change that alters every training row while still
producing plausible output.

## Task B — train the second family

Base model: **`Qwen/Qwen3-8B`**, already in the local HF cache. Confirm the exact cached identifier
before using it — do not assume the string. If it is absent, stop and report rather than triggering a
download.

Train the `sft_b_plus` recipe on the **same data** the granite `iaware` adapter used, with the **same
hyper-parameters**. The only difference between the two adapters must be the base model. Find the
`iaware` run's hyper-parameters, state them in STATUS with where you read them, and change nothing.

Adapter output: `sft_b_plus_iaware_qwen8b` under
`/scratch/n12194778/sidekick/artifacts/adapters/`. Never write under any `results/` tree.

Write the exact `qsub` line, **unrun**.

## Task C — the evaluation arms

Create `hj14_*` configs for: `executor_alone`, `sft_plan`, and the prefix grid
$m \in \{2, 4, 6, 7, 8, 9, 10, 11\}$ — copies of the corresponding granite configs differing only in
header comment, `campaign_id` (`hj14_*_20260924`), the executor `model`, and the LoRA alias/path.

Register them in `scripts/pbs/hj12_prefix.pbs` `FREE_ARMS`, matching the existing line format.

**The serving hazard, which has bitten this project before**: the vLLM alias launched via
`--lora-modules <alias>=<path>` must equal `executor.lora_name`, or requests silently hit the base
model and the whole evaluation measures nothing while still producing plausible numbers
[OBSERVED the warning comment in `configs/hj12_prefix_m9.yaml`]. A second base model means a second
alias and a second adapter path in `scripts/pbs/hj12_prefix.pbs:104-213`. Work out how that script
must change to serve a Qwen base with its own adapter, make the change, and **state in STATUS how a
reader verifies from the run record which base model and which adapter served a given episode.**

Also check: does the prefix replay path assume anything about the executor's tokenizer or chat
template? `_history_from_events` in `src/sidekick/training/sft_data.py:186-258` renders recorded
events and keys on event type, never on `actor` — confirm that still holds for a different chat
template, and say so explicitly. A template mismatch here would confound the replication with a
formatting artefact, which is exactly the failure the E-series already cost this project a retrain to
learn.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run tests through `hpc`.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev/train only; **never read, list or load
  `test_normal` or `test_challenge`.**
- Frozen, read only: every `docs/prereg_*.md`, every `hj8_*` and `hj11_*` config, and every
  `configs/hj12_*` (copy, never modify).
- Do not download any model. If a weight is not cached, stop and report.
- The suite must not fall; ignore `scripts/analysis/j8_frontier.py` if another unit is mid-edit, and
  say so.
- **Do not commit.** I review and commit.
- Size to ≤ 10 hours; STATUS with resume state per task.

## Return contract

`campaign/workers/STATUS_X27.md`, under 700 words: the parameterisation and the byte-identical-default
test; the confirmed cached Qwen identifier; the matched hyper-parameters and their source; the exact
unrun `qsub` line for training; the config paths and `FREE_ARMS` lines; **how a reader verifies which
base model and adapter served an episode**; your finding on chat-template independence of the replay
path; and the suite line.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. State plainly: **you submitted nothing and
downloaded nothing.**
