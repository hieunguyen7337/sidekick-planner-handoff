# STATUS — W-23 (two corrections to `docs/FOLLOWUPS.md`)

Unit brief: `campaign/workers/brief_W23_docfix.md`

**Do not commit. Zero planner calls. No GPU qsub.**

## Resume state

- **Milestone:** complete. Applied two documentation corrections to `docs/FOLLOWUPS.md`.
- **Correction 1 (dangling cross-reference):** replaced dangling `(see the silent-zeros entries above)` parenthetical at `docs/FOLLOWUPS.md:822` with references resolving to the three prior entries in this file matching the broken-internal failure class.
- **Correction 2 (stale OPEN entry):** updated `docs/FOLLOWUPS.md:415` from `## OPEN` to `## RESOLVED 2026-09-18`, keeping the full original diagnostic body and appending a resolution paragraph recording the log directory `#PBS -o`, runtime `exec` redirection, and per-CID/jobtag `VLOG` verified against `scripts/pbs/hj6_branches.pbs`.

## Owned files

- `docs/FOLLOWUPS.md` (modified)
- `campaign/workers/STATUS_W_23.md` (created)

## Headings cited in Correction 1

1. `## OPEN 2026-09-17 — the probe's `hash_match` metric is broken (reports 0 unconditionally)` [OBSERVED docs/FOLLOWUPS.md:275]
2. `## RESOLVED 2026-09-17 — the recorded test counts silently omitted `tests/integration`` [OBSERVED docs/FOLLOWUPS.md:366]
3. `### Cause 1 — the Codex quota was exhausted, because J6 spent a budget of zero` [OBSERVED docs/FOLLOWUPS.md:676] (was line 664 prior to resolution block insertion above)

## Verified facts for Correction 2

1. `#PBS -o` is evaluated at submit time and cannot interpolate `${CID}` (computed inside script), so it specifies the directory `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs/` rather than a file. PBS writes `<job ID>.OU` there, preventing shared paths between train/dev/resume and preserving logs if a job dies before script startup [OBSERVED scripts/pbs/hj6_branches.pbs:7-15].
2. The script computes `${CID}` and `${JOBTAG}` and `exec`s redirection to `${CID_OUT}` (`${PBS_LOGDIR}/${CID}.${JOBTAG}.out`) at startup, so an early death after script startup leaves a campaign-id-named log [OBSERVED scripts/pbs/hj6_branches.pbs:33-43].
3. `VLOG` is set to `"${LOGDIR}/${CID}.${JOBTAG}_vllm.log"`, carrying both the campaign ID and job tag [OBSERVED scripts/pbs/hj6_branches.pbs:73].
4. The original entry notes the shared un-isolated logs caused two misdiagnoses during J6 investigations: ambiguity during wedged branch diagnosis where server appeared dead [OBSERVED docs/FOLLOWUPS.md:433-435] and throughput comparison between train and dev [OBSERVED docs/FOLLOWUPS.md:441-443].
