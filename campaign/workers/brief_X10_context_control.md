# Brief X10 — the channel contrast currently confounds channel with context

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Two GPU jobs are queued.** Do not `qsub`, do not touch a GPU, do not run any evaluation.
You may run the pytest suite through `hpc` as described at the bottom.

## The problem

Claim C1 asks: *at the same trigger and the same call count, does a planner that **acts** beat a
planner that **advises**?* As built, the two arms differ in a second way as well.

- Takeover: `joined = "\n".join(transcript)` — the **whole** transcript
  [OBSERVED src/sidekick/systems/loop.py:770].
- Advise: `delta = "\n".join(transcript[-8:])` — the **last eight lines**
  [OBSERVED src/sidekick/systems/loop.py:805].

So a win for the takeover arm would be explainable as "we gave that planner more context", and the
claim would not survive review. The confound flatters the hypothesis, which is the direction that
matters.

The full transcript is the right input for an acting planner: it matches `planner_alone`
[OBSERVED src/sidekick/systems/loop.py:843] and it is what a deployed system would do. So the fix is
**not** to starve the takeover arm. It is to add the missing control.

## What to build

### 1. A policy knob for the advise path's context window

Add `SystemPolicy.correct_context_lines: int | None = 8`. `None` means the whole transcript; an
integer means that many trailing lines. Apply it at **line 805 only** — the forced-review advise
path.

**Do not touch line 939**, the executor-ASK path. That trigger belongs to the `sidekick` arms, which
are not in this phase and which nobody has reasoned about here. Changing them to chase symmetry
would put already-understood arms at risk for no gain — the same call that was made deliberately for
the `expect_planner` branch in commit 7564cc8.

The default of `8` must reproduce every existing arm byte for byte. Forward a config key
`correct_context` through `system_kwargs` for the systems that already receive `takeover`:
`full` (or `all`) maps to `None`, an integer maps to itself. Reject anything else loudly rather than
falling back to the default — a silently ignored key here would produce a control arm that is
secretly a duplicate of the arm it controls.

### 2. The context-matched control arm

`configs/hj12_advise_fixed_k_10_fullctx.yaml`: a copy of frozen `configs/hj8_fixed_k_10.yaml` with a
new `campaign_id: hj12_advise_fixed_k_10_fullctx_20260923`, `correct_context: full`, and **no**
`takeover` key. Everything else — executor, `limits`, `prices`, `packet_source` — identical, so it
differs from `configs/hj12_takeover_fixed_k_10.yaml` in exactly the channel.

Confirm by pasting `diff configs/hj12_takeover_fixed_k_10.yaml configs/hj12_advise_fixed_k_10_fullctx.yaml`
into STATUS. It should show the campaign id, `takeover: true`, and `correct_context: full`, and
nothing else.

### 3. Record the three readings this now supports

Amend `docs/prereg_hj12_dev_20260922.md`. It is **not** frozen, but P1 is already running against it,
so add a clearly headed, dated amendment section rather than editing registered text. State:

- **C1 primary becomes** `takeover_fixed_k_10 − advise_fixed_k_10_fullctx`: the channel isolated at
  matched trigger, matched call count and matched context.
- **C1 secondary, as deployed**, stays `takeover_fixed_k_10 − fixed_k_10_iaware`, the arm that
  already exists, and is reported as the as-deployed comparison rather than as the channel effect.
- **The context effect itself** is `advise_fixed_k_10_fullctx − fixed_k_10_iaware`, which was never
  measured and is interesting on its own: it says whether the advice channel was simply starved.
- Why the takeover arm keeps the full transcript, and why line 939 was deliberately left alone.

Same statistical treatment as the rest of the document: paired, task-clustered, 10,000 resamples,
`goal_pass_rate` primary. Do not invent a new test.

### 4. If `scripts/pbs/hj12_live.pbs` exists by the time you start

Another unit is creating it. If it is present, add the new arm to its arm list and adjust the spend
ceiling for roughly 280 more calls. If it is absent, say so in STATUS and change nothing else — do
not create it yourself.

## Tests

- Default policy sends exactly the last 8 lines (guards every existing arm).
- `correct_context: full` sends the whole transcript on the forced-review advise path.
- The ASK path at line 939 is unaffected by the knob.
- An unrecognised `correct_context` value raises.
- `system_kwargs` forwards the key for the same systems that receive `takeover`.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Suite via
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- The suite is at **484 passed, 1 skipped** and must not fall.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, `docs/prereg_j9_freeze_20260920.md`,
  every `hj8_*` and `hj11_*` config.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X10.md`, under 500 words: the knob's exact semantics and where it is
applied, the pasted config diff, the amendment's section heading, the test names, what you found at
`hj12_live.pbs`, and the pasted suite line. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
