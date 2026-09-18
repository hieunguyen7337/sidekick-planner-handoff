# A10 (U-FIX) — two recorded defects, both silent-zero shaped

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `scripts/setup/state_probe.py`, `scripts/setup/hj1_gate.py`, and
tests under `tests/unit/`. **Do not touch** `configs/`, `scripts/pbs/`,
`scripts/setup/branch_counterfactual.py`, `src/sidekick/systems/loop.py`,
`scripts/setup/verify_configs.py` — other units own those this cycle.

**Create or edit the files within your first three actions, then iterate with tests.**

Both defects belong to the class this campaign has been bitten by repeatedly: **a harness that
returns a believable number instead of failing.** Nine of nineteen defects found here did that.
Treat "the metric is broken" as the default hypothesis, not "the model scored zero".

---

## Defect 1 — the probe's `hash_match` reports 0 unconditionally

`probe_granite8b.json` (job `25401677`, 300 points) reports `hash_match: 0` and
`hash_match_rate: 0.0` in **every** bucket, across 262 points where the metric is defined
[OBSERVED docs/FOLLOWUPS.md:275-278].

**It is provably not a true zero.** 18 of those points have `model_code` byte-identical to
`gold_code`. Identical code executed against an identically replayed prefix must produce an
identical `env_state_hash` [OBSERVED docs/FOLLOWUPS.md:279-281].

**Where to start** — from the filed note [OBSERVED docs/FOLLOWUPS.md:294-299]: `snapshot_hash`
hashes `environment_io` *including the input* (`appworld_env.py:134-146`), so the probe world's io
log and the gold run's io log must be **compared directly on one of those 18 identical-code
points before theorising.** The named candidates are an off-by-one in which step's hash is
compared, or the probe world carrying an extra io record (the replay itself, or a preflight) that
the gold run does not have.

🔺 **Diagnose before you fix.** Report what the two io logs actually differ by, with the evidence,
*then* fix. A fix that makes the number non-zero without a diagnosis is worse than the defect,
because it would look validated.

The relevant code is `scripts/setup/state_probe.py`: the bucket counters
[OBSERVED scripts/setup/state_probe.py:120-122], the accumulation
[OBSERVED :144-146], the rate computation [OBSERVED :171-172], and the per-record defaults
[OBSERVED :195-197].

⚠ **Scope discipline:** `hash_match` is the *strict secondary* metric. No decision taken so far
depends on it, `state_equivalent` (the secondary that does carry weight) is healthy at 0.676, and
the HJ-1.5 decision rule turns on primary agreement [OBSERVED docs/FOLLOWUPS.md:284-288]. So fix
the metric; **do not** re-run the probe, and **do not** revise any published number.

If the diagnosis shows the metric is measuring something that cannot be made meaningful, say so
and propose removing it rather than fixing it. That is an acceptable outcome.

---

## Defect 2 — `hj1_gate.py` coerces missing values to zero

```python
tgc   = [float(r.get("tgc") or 0.0) for r in runs.values()]
steps = [int(r.get("steps") or 0) for r in runs.values()]
calls = [int(r.get("n_planner_calls") or 0) for r in runs.values()]
```
[OBSERVED scripts/setup/hj1_gate.py:106-108], and the same pattern in a paired difference
[OBSERVED scripts/setup/hj1_gate.py:154].

`x or 0.0` maps **missing**, **None**, **0** and **0.0** to the same value. A run whose `tgc` was
never recorded is silently scored as a run that scored zero, and it is then averaged in as if it
were data. A gate can fail a healthy arm this way — that has already happened in this campaign.

**The distinction to enforce:** a recorded 0 is a measurement; a missing key is **not a
measurement** and must not become one. The project's own convention is explicit about this —
`p_ask: Optional[float] = None`, "None means 'not measured'… Never coerce None to 0.0"
[OBSERVED src/sidekick/protocols/schemas.py:37].

Decide, and state, the right behaviour per field: either **drop** the run from that statistic and
report how many were dropped, or **abort loudly**. Silently substituting a number is the one
option ruled out. Whichever you choose, the count of missing values must appear in the gate's
output — an invisible drop is the same defect wearing a different hat.

⚠ Check whether any current gate result would change under the fix. If one would, **say so
prominently in your report** — that is a finding, not a footnote.

---

## Tests

Both fixes need tests that fail before and pass after:

- `hash_match`: a case built so the answer is known by construction — identical code against an
  identically replayed prefix **must** match. That test is the whole point; without it the metric
  is unvalidated again.
- `hj1_gate`: a run dict with a **missing** field and one with a **recorded 0**, asserting the two
  are treated differently, and that the missing-count is reported.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. All computation in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job** — a training job is
  running and the GPU queue is congested. **Do not re-run the probe.**
- 🔺 **Do not modify anything under `/scratch/.../results/`.** Read the probe artifacts; never
  write them.
- **Do not commit.** Suite baseline **365 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_A_10.md` with resume state per milestone, updated as you go.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- For `hash_match`: **the diagnosis first** — what the two io logs differ by, on which point, with
  evidence — then the fix and the known-answer test.
- For `hj1_gate`: the policy you chose per field, why, and whether any existing gate result changes.
- The diff and test output as emitted.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
