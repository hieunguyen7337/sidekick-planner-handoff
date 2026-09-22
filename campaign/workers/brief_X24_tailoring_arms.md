# Brief X24 — is the rise caused by the prefix, or by the executor being tailored to it?

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Code, configs and training data only. **Do NOT `qsub` anything. I submit every job myself.** Two GPU
jobs (25681670, 25681674) and one CPU job (25681706) are running; they do not import the files you
will touch, but do not disturb them.

## Why this unit is the most important one left

The campaign's headline is that a small executor tailored to one frozen planner finishes that
planner's opening actions well enough to approach its quality at a fraction of its hosted cost.

**Nothing on disk isolates the word "tailored."** The closest published work continues one model's
trajectory with another model **prompted zero-shot**, and reports that it works. If our zero-shot
executor shows the same rise across prefix depth that our tailored one does, then tailoring is not
what makes the action channel work, our central claim collapses into that prior work, and the thesis
must say so. That experiment does not exist yet. It is task A.

Task B asks the complementary question: if we train the executor specifically on the thing it is
asked to do at serving time — finish a trajectory the planner started — does the curve move?

Both are pre-registered in `docs/prereg_hj13_shape_20260923.md` §5, **including the predictions and
the falsification conditions**. Read that section before you start. Neither task may be tuned toward
the predicted outcome; a clean negative is a publishable result here and a fudged positive is not.

## Task A — the zero-shot receiver arms

Create `configs/hj13_prefix_zs_m6.yaml`, `hj13_prefix_zs_m9.yaml`, `hj13_prefix_zs_m11.yaml`.

Each is a copy of the corresponding `configs/hj12_prefix_m<k>.yaml` differing **only** in:

1. the header comment, stating this is the untailored control for Claim C3;
2. `campaign_id: hj13_prefix_zs_m<k>_20260923`;
3. the executor resolving to the **base model with no adapter**.

Point 3 is the one that must be right, and it is the classic silent failure in this repo: the vLLM
alias comment at `configs/hj12_prefix_m9.yaml` warns that a `lora_name` mismatch means requests
"silently hit the BASE model" while still producing plausible numbers. Here we *want* the base model —
so make that explicit and verifiable rather than implicit. Determine from
`src/sidekick/agents/` (the vLLM executor client) and `scripts/pbs/hj12_prefix.pbs:104-213` how a
request selects base versus adapter, and choose the representation that is **checkable in the run
record**. Then state in STATUS exactly how a reader of an episode's events can confirm which weights
served it.

Register the three arms in `FREE_ARMS` in `scripts/pbs/hj12_prefix.pbs`, matching the existing line
format. Change nothing else in that file.

**Add a test** that the zero-shot config resolves to an executor with no adapter, and that the
tailored config resolves to one with the `sft_b_plus` alias. A test that cannot tell these apart is
worthless here.

## Task B — the suffix-trained adapter

Build the training data and the training entry point for `sft_b_plus_handoff_granite8b`.

**Source**: the 270 recorded planner trajectories at
`/scratch/n12194778/sidekick/results/hj2b_planner_train_20260916/planner_alone`. These are the
**train** split. Read-only — never write under any `/scratch/.../results/` tree.

**Construction**: for each trajectory and each cut point $m \in \{6, 9, 11\}$, emit one training row
in which the first $m$ planner actions and their observations are **context with labels masked**, and
every assistant turn after the cut is a **supervised target**. This mirrors at training time what the
executor faces at serving time.

Reuse, do not reimplement:
- `_history_from_events` in `src/sidekick/training/sft_data.py:186-258` already renders recorded
  events into the alternating turn format, keyed on event type and never on `actor` — which is
  exactly why a planner-authored prefix is on-distribution for the executor.
- the target-collection and tokenisation path in `src/sidekick/training/matched_sft.py`
  (`_next_assistant`, `_collect_supervised_targets`, `_tokenize_messages`), which already sets
  `-100` for non-target positions.

**Masking is the thing to get right.** A row whose prefix turns are supervised trains the executor to
imitate the planner, which is a different experiment and a much worse one. Write a test that takes a
known short trajectory, cuts at $m=2$, and asserts the exact set of token positions carrying label
`-100` versus real ids. Assert on positions, not on counts.

**Short trajectories**: a source episode with $\le m$ actions has no suffix to supervise. Drop those
rows and **record how many were dropped per $m$** — if most trajectories are shorter than 11 the
$m=11$ adapter is trained on very little and that must be visible, not inferred later.

**No handoff note.** v1 introduces no new token class. A `HANDOFF: <note>` user turn would have to be
trained and served together, and serving is not changing in this unit.

**Output**: the JSONL under `/scratch/n12194778/sidekick/artifacts/` (a new path you choose and
report; not under `results/`), plus a small manifest recording rows per $m$, rows dropped, the source
campaign, and the cut points.

**Training entry point**: reuse `scripts/pbs/train_sft.pbs` via its existing `DATA_JSONL` /
`ADAPTER_OUT` / `BASE_MODEL` environment variables [OBSERVED `scripts/pbs/train_sft.pbs:39-41`].
Hyper-parameters must be **identical** to the `iaware` adapter's run so that training data is the only
difference between the two adapters — find them, state them in STATUS, and do not change them. Write
the exact `qsub` line I should run, but **do not run it**.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. Run the data builder and the test suite through `hpc`, never on the login node.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Never write under
  `hj6_branches_train_20260917` or any existing results tree.
- Dev/train only; **never read, list or load `test_normal` or `test_challenge`.**
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, `docs/prereg_hj12_dev_20260922.md`,
  `docs/prereg_hj13_shape_20260923.md`, every `hj8_*` and `hj11_*` config, and
  `configs/hj12_prefix_m*.yaml` (copy them, never modify).
- The suite must not fall. It currently reports failures in `scripts/analysis/j8_frontier.py` from
  another unit in flight — ignore that file when you measure, and say so.
- **Do not commit.** I review and commit.
- Size this to ≤ 10 hours; write STATUS as you go with resume state per task.

## Return contract

`campaign/workers/STATUS_X24.md`, under 700 words:

- the three zero-shot config paths and **how a reader verifies from the run record which weights
  served an episode**;
- the `FREE_ARMS` lines added;
- the training JSONL path, rows per $m$, and rows dropped per $m$ for being too short;
- the masking test's name and what exactly it asserts;
- the hyper-parameters you matched and where you read them from;
- the exact `qsub` line for the training job, unrun;
- the suite line.

Tag every claim `[OBSERVED <path>:<line>]` or `[INFERRED]`. State plainly: **you submitted nothing.**
