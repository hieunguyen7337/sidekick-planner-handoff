# A21 (U-B1PBS2) — resume-aware PREFLIGHT identity guard

**Unit**: A21 / U-B1PBS2
**State**: done (2026-09-19)
**Did not commit. Did not qsub the B1 GPU job. Did not invoke `codex`. Did not write under `/scratch/.../results/`.**
**Did not touch** `docs/prereg_b1_pilot.md`, `scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`, `src/`, `configs/`, or any other `scripts/pbs/` file.

Owned outputs:

- `scripts/pbs/b1_pilot.pbs` (edited)
- this file
- `campaign/workers/STATUS_A_21.md`
- harness (not pytest): `campaign/workers/scratch_A20/` (extended)

Validation job: **25499131.aqua** (cpu_inter, 95 s, not a crash). Full log: `/home/n12194778/.hpc-spool/20260919-173129-1208610.out`.

---

## What changed in `scripts/pbs/b1_pilot.pbs`

A20's guard aborted unless `branches_to_run == 1600` [OBSERVED campaign/workers/A20_B1_PBS.md:163]. That is correct for a **fresh** out-root and fatal for a **resume**: `collect_jobs` skips completed keys, so PREFLIGHT `branches_to_run` is the remainder [OBSERVED scripts/setup/branch_counterfactual.py:1177-1180, 1280]. The prereg requires resume (§13 `--resume`; §9 "resume after quota … until 1,600 have been dispatched") [OBSERVED docs/prereg_b1_pilot.md:207, 280].

The replacement is sample **identity by arithmetic**, not "anything that isn't 6216":

- **Fresh** (`completed_branch_keys` is 0: no `branch_runs.jsonl`, or none of its rows are completions): `branches_to_run` must be **exactly 1600**.
- **Resume** (a non-zero completed set): `branches_to_run` must be **< 1600**, and `completed + branches_to_run` must be **exactly 1600**.
- **`completed + to_run > 1600`**: abort with the **foreign-branches** message below, not the generic mismatch.
- **`branches_to_run == 6216`**: still the wrapper-not-used FATAL, fresh **and** resume.
- **`max_planner_calls_total != 10000`**: still FATAL, fresh **and** resume.

Completed count is `len(completed_branch_keys(load_jsonl(out_root / "branch_runs.jsonl"), retry_errors=True))` — the same helpers `collect_jobs` uses [OBSERVED scripts/setup/branch_counterfactual.py:485-508, 1142-1147; scripts/pbs/b1_pilot.pbs:102-127]. Raw jsonl lines are not counted (retried errors are not completions). The resume-pass fixture includes 5 `branch_error_type=timeout` rows; the guard still reported `completed_branch_keys=200` [OBSERVED /home/n12194778/.hpc-spool/20260919-173129-1208610.out preflight_resume_ok].

The live call is now `b1_assert_preflight_line "${pf_line}" "${OUT_CAMPAIGN}"` [OBSERVED scripts/pbs/b1_pilot.pbs:511]. The grep-for-`^PREFLIGHT ` loop is unchanged (still does not require that line at byte 0 of job stdout) [OBSERVED scripts/pbs/b1_pilot.pbs:507-508].

**OPERATOR_CONFIRM.** After a successful parse the guard prints one clearly-marked line so an operator following §13 can confirm values without reading the vLLM block:

```
[b1] OPERATOR_CONFIRM branches_to_run=… max_planner_calls_total=… completed_branch_keys=… completed_plus_to_run=…
```

[OBSERVED scripts/pbs/b1_pilot.pbs:136-137; job 25499131.aqua]. The prereg was not edited.

Selftest gained `preflight_fresh_1400`, `preflight_resume_ok`, `preflight_resume_1700`, `preflight_resume_foreign`, `preflight_bad_cap_resume`, `preflight_6216_resume`. Every preflight case now receives `GUARD_OUT_ROOT` (harness-written fixtures under `campaign/workers/scratch_A20/outroots/`, never `/scratch/.../results/`).

---

## `bash -n`

Login node (syntax only): `timeout 30 bash -n scripts/pbs/b1_pilot.pbs` → `bash_n_rc=0`.

Inside PBS job **25499131.aqua**: `bash_n_rc=0` [OBSERVED /home/n12194778/.hpc-spool/20260919-173129-1208610.out:4].

---

## Seven required cases (quoted from job 25499131.aqua)

Harness: `campaign/workers/scratch_A20/test_b1_pilot_guards.py`. Not under `tests/`.

**1. Fresh tree, `branches_to_run: 1600` → passes.**

```
[b1] PREFLIGHT parsed branches_to_run=1600 max_planner_calls_total=10000 completed_branch_keys=0
[b1] OPERATOR_CONFIRM branches_to_run=1600 max_planner_calls_total=10000 completed_branch_keys=0 completed_plus_to_run=1600
[b1] PREFLIGHT guard: sample identity holds (completed_branch_keys + branches_to_run == 1600) and max_planner_calls_total matches prereg §13
```

[OBSERVED /home/n12194778/.hpc-spool/20260919-173129-1208610.out]

**2. Fresh tree, `branches_to_run: 6216` → aborts.**

```
[b1] FATAL: PREFLIGHT branches_to_run is 6216, expected 1600 (6216 means the wrapper was not used)
```

[OBSERVED same file]

**3. Fresh tree, `branches_to_run: 1400` → aborts (a short fresh run is not a resume).**

```
[b1] FATAL: PREFLIGHT branches_to_run is 1400, expected 1600 on a fresh out-root (a short fresh run is not a resume; 6216 means the wrapper was not used)
```

[OBSERVED same file]

**4. Resume with 200 completed and `branches_to_run: 1400` → passes.**

```
[b1] PREFLIGHT parsed branches_to_run=1400 max_planner_calls_total=10000 completed_branch_keys=200
[b1] OPERATOR_CONFIRM branches_to_run=1400 max_planner_calls_total=10000 completed_branch_keys=200 completed_plus_to_run=1600
[b1] PREFLIGHT guard: sample identity holds (completed_branch_keys + branches_to_run == 1600) and max_planner_calls_total matches prereg §13
```

[OBSERVED same file]

**5. Resume with 200 completed and `branches_to_run: 1500` → aborts (1700 ≠ 1600).** Because 1700 **exceeds** 1600 this uses the foreign-branches message, not a generic mismatch.

```
[b1] FATAL: out-root already holds branches that are not from this frozen sample: completed_branch_keys=200 + branches_to_run=1500 = 1700, which exceeds 1600. This is not a resume of the B1 200-point sample.
```

[OBSERVED same file:29]

**6. Resume where `completed + to_run` exceeds 1600 → specific foreign-branches message (asserted, not just abort).** Fed 200 completed + `branches_to_run: 1600` = 1800.

```
[b1] FATAL: out-root already holds branches that are not from this frozen sample: completed_branch_keys=200 + branches_to_run=1600 = 1800, which exceeds 1600. This is not a resume of the B1 200-point sample.
```

[OBSERVED same file:33]

**7. `max_planner_calls_total` ≠ 10000 → aborts on both paths.**

Fresh (1600 jobs, cap 999999):

```
[b1] FATAL: PREFLIGHT max_planner_calls_total is 999999, expected 10000
```

Resume (200 completed + 1400 to_run, identity would pass, cap 999999):

```
[b1] FATAL: PREFLIGHT max_planner_calls_total is 999999, expected 10000
```

[OBSERVED same file]

Harness: `n_pass=18 n_fail=0` / `ALL_GUARDS_FIRED` [OBSERVED same file:70-71].

---

## Foreign-branches message, verbatim

Template [OBSERVED scripts/pbs/b1_pilot.pbs:167-170]:

```
[b1] FATAL: out-root already holds branches that are not from this frozen sample: completed_branch_keys={n} + branches_to_run={br} = {total}, which exceeds 1600. This is not a resume of the B1 200-point sample.
```

Case 6 instance [OBSERVED /home/n12194778/.hpc-spool/20260919-173129-1208610.out:33]:

```
[b1] FATAL: out-root already holds branches that are not from this frozen sample: completed_branch_keys=200 + branches_to_run=1600 = 1800, which exceeds 1600. This is not a resume of the B1 200-point sample.
```

---

## 6216 and a wrong cap are still fatal on both paths

| Path | Input | FATAL line |
|---|---|---|
| Fresh 6216 | to_run=6216, completed=0, cap=10000 | `PREFLIGHT branches_to_run is 6216, expected 1600 (6216 means the wrapper was not used)` |
| Resume 6216 | to_run=6216, completed=200, cap=10000 | same 6216 wrapper-not-used line (does **not** fall through to foreign-branches; 6216 is diagnosed as "wrapper was not used") |
| Fresh bad cap | to_run=1600, completed=0, cap=999999 | `max_planner_calls_total is 999999, expected 10000` |
| Resume bad cap | to_run=1400, completed=200, cap=999999 | same cap line; identity 200+1400=1600 would have passed |

[OBSERVED job 25499131.aqua]

A guard that only excluded 6216 would have passed case 3 (fresh 1400) and case 5 (200+1500). Those abort.

---

## On identity-by-arithmetic

The invariant `completed + to_run == 1600` is a **size** identity, not a **set** identity. It cannot tell "remainder of the frozen 200-point sample" from "some other 1600-branch population that happens to have this many completions in this out-root". A tree that already holds 1600 completed branches from a different campaign would pass as a finished B1 resume (`to_run=0`). Matching keys against `b1_pilot_points.txt` would be stronger; this unit must not touch that file or the wrapper. **Implemented as specified anyway.** It is still the right proxy relative to A20's `== 1600` (which made the prereg's own resume rule unexecutable) and relative to `!= 6216` (which would accept any other campaign root).

---

## Suite

Same job, after the harness:

```
413 passed, 1 skipped, 1 warning in 38.20s
```

[OBSERVED /home/n12194778/.hpc-spool/20260919-173129-1208610.out:86]. Interpreter `/scratch/n12194778/sidekick/env/bin/python`. Never fewer than 413 passed; zero failures.

---

## Not done, by instruction

- No `qsub` of `scripts/pbs/b1_pilot.pbs`.
- No GPU job.
- No `codex` / planner call.
- No commit.
- No writes under `/scratch/n12194778/sidekick/results/`.
- Prereg §13 confirmation text still says the job's stdout "begins with" PREFLIGHT; it will not (vLLM first). OPERATOR_CONFIRM is the operator-facing substitute. The prereg was not edited.
