# Brief X12 — records for the HJ-12 build wave, and two small corrections

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation and one comment line. **Two GPU jobs are queued.** Do not `qsub`, do not touch a GPU,
do not run any evaluation. Do not edit `src/`, `scripts/`, or any config other than the one named
below, and change nothing in that config except its header comment.

**Invent nothing.** Every number and file path you need is in this brief or in the commits named
below. If you find yourself about to state a figure that is not here, stop and leave a `[GAP]`
marker instead. A fabricated citation has already cost this campaign a correction, so an
acknowledged gap is strictly better than a plausible sentence.

## 1. A stale comment that describes the wrong arm

`configs/hj12_advise_fixed_k_10_fullctx.yaml` opens with a comment copied from the takeover arm it
was derived from. It currently reads, in substance, "HJ-12 takeover channel ... `takeover: true` is
the only experimental difference from the advise arm." That file has **no** `takeover` key — it is
the advise side of the contrast.

Replace the header comment so it says what the file actually is: the context-matched advise control
for Claim C1, a copy of frozen `configs/hj8_fixed_k_10.yaml` differing only in `campaign_id` and
`correct_context: full`, and that its purpose is to give the advising planner the same transcript the
takeover arm gets so a takeover win cannot be explained by context. Change **only** comment lines.
Paste `diff` against the previous version into STATUS to prove no key moved.

## 2. A rival explanation the pre-registration does not yet record

Add to the existing amendment section `## Amendment 2026-09-21 — C1 context-matched control` in
`docs/prereg_hj12_dev_20260922.md` — extend it, do not start a second section, and do not rewrite
registered text above it.

Both C1 arms run the `fixed_k` system with `allow_executor_ask: true`, confirmed from the recorded
policy of the arm already on disk [OBSERVED
`/scratch/n12194778/sidekick/results/hj8_fixed_k_10_20260921iaware/fixed_k/1/0d8a4ee_1/events.jsonl`,
the `run_start` event]. The `takeover` flag governs only the forced-review branch, so an
executor-initiated ASK still returns planner **prose** in both arms.

Record that this is a shared component, not a confound: it is identical on both sides, so it does not
bias the contrast, but it **attenuates** it, because part of each arm's planner contact is on the
advice channel in both cases. Require the analysis to report per-arm ASK counts alongside the
contrast so the size of any attenuation is visible rather than assumed away. State plainly that if
ASK events turn out to dominate planner contact, the C1 effect size is a lower bound on the channel
difference.

## 3. `campaign/RUNS.md` — a section for this wave

Add a new section for the HJ-12 build wave. It must be readable by someone who was not here. Use
exactly these facts:

- Commit `4bd6698` — the takeover channel and the repair of the action-review gate. The gate had been
  inert against the hosted planner: it tested a response field that the planner's correction method
  never sets, so every review would have approved and spent a call doing so. It now calls the
  planner's act method, which does return a fenced action.
- Commit `e405ed3` — the exception pair rebuilt. It previously shared one `campaign_id` across two
  arms and selected a path where the `takeover` flag is inert, making the two arms one policy.
- Commit `722e887` — the context-matched advise control, and the policy field for the advise path's
  transcript window. Default 8 lines, unchanged for every existing arm.
- Commit `808d445` — the live-arm harness, its between-arm spend ceiling, its post-smoke projection
  guard, and the removal of a swallowed type error in the cached planner.
- Suite: **498 passed, 1 skipped**, verified in an independent job.
- Hosted calls spent by this wave: **zero**.
- Phase P1 (the four prefix arms) was submitted as jobs `25596786` and `25596787` and was still
  queued when this section was written, waiting on GPU availability.

Do **not** state any result for P1, any goal-pass figure, or any gate verdict. None exists yet.
Match the file's existing section style and heading depth.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- Dev only; never read `test_normal` or `test_challenge`.
- The suite is at **498 passed, 1 skipped**. You should not be changing code, but if you touch
  anything that could affect it, run it through `hpc` and paste the line.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X12.md`, under 400 words: the config comment `diff`, the heading you
extended, the RUNS.md section heading, and any `[GAP]` markers you left and why. Tag claims
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
