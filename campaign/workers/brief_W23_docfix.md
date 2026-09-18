# W-23 — two corrections to `docs/FOLLOWUPS.md`

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation only. Two precise edits, both found in review of W-22's work. **Do not touch any
other file. Do not commit. Do not change any number.**

## Correction 1 — a dangling cross-reference

At `docs/FOLLOWUPS.md:800-801` the text currently reads:

```
not scale, and it is now the fourth defect in this campaign to return believable numbers from
broken internals (see the silent-zeros entries above).
```

**The parenthetical does not resolve.** There is no entry in this file titled "silent zeros";
`grep -in "silent.zero" docs/FOLLOWUPS.md` matches that line and nothing else. The phrase was
written against a different document.

Replace the parenthetical so it names entries that **do** exist in this file. The three prior
instances of the same failure class — a broken internal returning a believable number — are:

- `## OPEN 2026-09-17 — the probe's `hash_match` metric is broken (reports 0 unconditionally)`
- `## RESOLVED 2026-09-17 — the recorded test counts silently omitted `tests/integration``
- `### Cause 1 — the Codex quota was exhausted, because J6 spent a budget of zero`

Verify each heading exists and get its real line number before you write the reference. Keep the
sentence's meaning and register exactly; change only the parenthetical. Do not renumber "fourth".

## Correction 2 — an OPEN entry that is now fixed

`docs/FOLLOWUPS.md:415` is headed:

```
## OPEN — the J6 branch job writes its server log and PBS stdout to paths that carry no campaign id
```

**This was fixed in commit `2216a0b`** and the entry is now stale. Mark it resolved, matching the
house style of the other resolved entries in this file (read two of them first and follow their
form — heading prefix, date, and a short closing paragraph).

The closing paragraph must record, accurately:

- `#PBS -o` is evaluated at **submit** time and cannot interpolate `${CID}`, which is computed
  inside the script — so the directive names the **log directory** rather than a file. PBS then
  writes a unique `<job ID>.OU` there, so train, dev and a resume cannot share a path, and a job
  that dies before the script runs still leaves a findable log.
  [verify against `scripts/pbs/hj6_branches.pbs`, the `#PBS -o` line]
- The script additionally `exec`s a `${CID}.${PBS_JOBID}.out` log as soon as the campaign id is
  known, so an early death *after* startup still leaves a campaign-id-named log.
  [verify against `scripts/pbs/hj6_branches.pbs`]
- `VLOG` now carries the campaign id and job tag.
  [verify against `scripts/pbs/hj6_branches.pbs`]
- The original entry notes this cost two misdiagnoses during the J6 crash investigation; keep
  that fact.

**Verify every one of those against the file as it stands now** and cite `path:line`. If any
claim does not match what the script actually does, report the discrepancy and do not write it.

## Do not

- Do not edit `campaign/RUNS.md` or any code, config or PBS file.
- Do not delete the original body of entry `:415` — it is the record of what was wrong. Mark it
  resolved and append the resolution; do not replace it.
- Do not commit.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. Do not run an interpreter, a package
  installer, `tar`, `rsync` or `ffmpeg` there. This unit needs none — it reads and edits Markdown.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any job.** The hosted-model quota
  is exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- Ignore `.claude/worktrees/` and `.git/`.
- Write `campaign/workers/STATUS_W_23.md` with resume state.

## Return contract

- The diff, as emitted.
- The real line number of each of the three headings you cited in Correction 1.
- For Correction 2, a `[OBSERVED scripts/pbs/hj6_branches.pbs:<line>]` for each of the four facts.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
