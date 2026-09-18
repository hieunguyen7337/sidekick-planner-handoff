# A12 — J10 analysis script, written before the data

**Status:** done. Script validated on **dev** archives only.
**Do not commit** (this unit does not commit).
**These numbers are a plumbing check, not a result.** Dev has been inspected many times. Nothing below is evidence about the thesis.

## Deliverable

- Script: `scripts/analysis/j10_report.py`
- Tests: `tests/unit/test_j10_report.py` (16 cases, including refuse-rather-than-compute)
- Dev dry-run JSON: `campaign/workers/a12_dryrun/*.json`
- Driver used for the dry-run: `campaign/workers/a12_dryrun_dev.py`

Did not touch `src/`, `configs/`, `scripts/pbs/`, `scripts/setup/hj1_gate.py`,
`scripts/setup/branch_counterfactual.py`, `scripts/setup/state_probe.py`,
`scripts/setup/verify_configs.py`, `src/sidekick/systems/loop.py`,
`docs/prereg_v1.md`. Zero planner calls. No GPU job. No writes under
`/scratch/.../results/`. No `test_normal` / `test_challenge` archives read.

## Resampling unit

**The unit of resampling is the task.**

`hj1_gate.paired_diff(resample="task")` draws tasks with replacement and
carries every matched seed of that task together
[OBSERVED scripts/setup/hj1_gate.py:91-100, 161-174].
`branch_counterfactual.task_clustered_bootstrap` does the same
[OBSERVED scripts/setup/branch_counterfactual.py:299-338, 735-738].

Paired seeds on one task are not independent. Resampling `(task, seed)` pairs
as if they were would understate every interval in the J10 report.

Prereg §3.1 first averages TGC across the N seeds of a task and then bootstraps
the 168-vector of task differences [OBSERVED docs/prereg_v1.md:107-117].
With equal seed counts per task that estimand equals the clustered seed-level
mean that `paired_diff` reports. This script **refuses** a contrast rather than
mix cluster sizes, so the two writings coincide when a decision is emitted.

Bootstrap: 10,000 resamples, seed `20260915`, two-sided percentile endpoints
at 2.5 / 97.5 as implemented by `paired_diff`
[OBSERVED scripts/setup/hj1_gate.py:28-29, 129-136, 177-178].

## Missing and crashed runs

Surfaced in `missing_and_crashed` at the **top** of the JSON, not a footnote.

| Cell | What the script does |
|---|---|
| No `result.json` | `missing_run`. Arm incomplete. **Refuse** hypothesis decisions. Mean is `null`, not 0. |
| `tgc` is `None` and `error_type` not in the §6.1 set | `missing_metric`. **Refuse**. Mean is `null`. Never averaged as 0 [OBSERVED src/sidekick/protocols/schemas.py:35-37]. |
| `error_type` in `{limit, timeout, crash, parse_error, api_error}` and recorded `tgc` is `None` or `0.0` | `scored_failure`. Counted. TGC used as 0.0 per prereg §6.1 [OBSERVED docs/prereg_v1.md:175]. Not dropped. |
| §6.1 error but recorded `tgc` not in `{0.0, None}` | Disagreement. **Refuse** rather than pick. |
| Extra seeds/tasks outside `--seeds` × observed task list | Counted as `n_extra_runs_ignored`. Not analysed. |

`--split` is required. `test_normal` and `test_challenge` require
`--confirm-heldout-test-split` (alias `--i-understand-this-is-the-single-j10-look`).
A path containing `test_normal` / `test_challenge` is refused on `--split dev`.
`--plumbing-check` is refused on a held-out test split.

`--k-matched`, `--tau`, `--router-tau` are J9 inputs, not estimated here
[OBSERVED docs/prereg_v1.md:219-231].

## Unresolved prereg ambiguities (not resolved in code)

The script lists these on every run under `unresolved_ambiguities`. J9 must freeze them.

1. **One-sided vs two-sided 95% CI** — H2/H1 are described as one-sided 95% [OBSERVED docs/prereg_v1.md:36, 46] but §3.2 names `paired_diff`, which uses 2.5/97.5 percentiles [OBSERVED docs/prereg_v1.md:117-122; scripts/setup/hj1_gate.py:129-136]. Script uses `paired_diff` because §3.2 names it. Does not compute a one-sided interval.

2. **168 task-means vs 504 clustered seed-diffs** — §3.1 defines Δ_i on task means [OBSERVED docs/prereg_v1.md:107-117]; §1.1 counts 504 paired (task, seed) comparisons [OBSERVED docs/prereg_v1.md:36]. Script uses `paired_diff(resample="task")` and refuses unequal cluster sizes.

3. **Three-clause H2 vs RUNS.md H2a∧H2b** — prereg file still has the three-clause conjunction [OBSERVED docs/prereg_v1.md:35-40, 119-123]; `campaign/RUNS.md` later says that form is not satisfiable and replaces it at J9 [OBSERVED campaign/RUNS.md:1465-1470, 1541-1559]. Script computes the three-clause form in `docs/prereg_v1.md`. Does not apply H2a/H2b.

4. **§6.1 scores failures as TGC=0 vs never coerce None** — [OBSERVED docs/prereg_v1.md:175; scripts/setup/hj1_gate.py:15-16; src/sidekick/protocols/schemas.py:35-37; src/sidekick/systems/loop.py:954-968]. `loop.py` can write evaluate() TGC (including 1.0) on a limit run. Script: §6.1 error + recorded tgc None/0 → score 0 and count; recorded tgc not in {0, None} on a §6.1 error → refuse; None without those errors → missing, refuse.

5. **Complete accounting vs intersection pairing** — §6.1 forbids dropping cells [OBSERVED docs/prereg_v1.md:174]; `paired_diff` pairs on the intersection [OBSERVED scripts/setup/hj1_gate.py:132-152]. Script refuses if any required cell is missing, so `paired_diff` is only called on the full matrix.

6. **FCD: billed vs unweighted, pooled vs paired-by-task** — prereg §4.3 billed tokens `input + 0.10×cached + output + reasoning` as a pooled ratio [OBSERVED docs/prereg_v1.md:137-139]; PLAN.md says FCD is always paired by task [OBSERVED docs/PLAN.md:157-159]; `CostLedger.frontier_displacement` uses unweighted `planner_tokens_total` [OBSERVED src/sidekick/cost/ledger.py:40, 57-67]. Script reports all three. H1's FCD>0 conjunct is refused if they disagree on sign.

7. **H4 `p<0.05` at matched calls** — [OBSERVED docs/prereg_v1.md:48-49]. `paired_diff` has no p-value [OBSERVED scripts/setup/hj1_gate.py:124-192]. "Matched" is a J9 calibration. Script: if `router_seq` absent, skip (optional arm [OBSERVED docs/prereg_v1.md:86]); if present, report the TGC CI and call means; **no H4 pass/fail**.

8. **C_solved denominator** — "completed tasks" undefined [OBSERVED docs/prereg_v1.md:140-142]. Script reports `usd_total/n_success` and `usd_total/n_runs`. Does not pick one as the test.

9. **H3 and f_dev are not J10-archive quantities** — [OBSERVED docs/prereg_v1.md:50-53, 146-149]. Not computed from J10 arm directories.

10. **Unsafe irreversible violations** — no `RunResult` field [OBSERVED docs/prereg_v1.md:150-152; src/sidekick/protocols/schemas.py:129-145]. Reported as unmeasurable from `result.json`. This script does not invent an `events.jsonl` parser.

11. **`paired_diff` scales call differences as percentage points** — H2 clause 3 is in calls [OBSERVED docs/prereg_v1.md:122]; `paired_diff` always multiplies by 100 [OBSERVED scripts/setup/hj1_gate.py:189-190]. Script still uses that resampling; also reports native call units (`ci95 = ci95_pp/100`). The sign test against 0 is invariant to the scale.

## Tests [OBSERVED PBS job 25452369.aqua]

Command:

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

Verbatim:

```
390 passed, 1 skipped, 1 warning in 22.60s
```

Zero failures. Never fewer than the 365 passed / 1 skipped baseline. New file
`tests/unit/test_j10_report.py` is 16 cases, including constructed H2 pass/fail
and refuse-on-missing-metric / refuse-on-test-split-without-flag.

`tests/unit/test_j10_report.py` only, job 25452348.aqua:

```
16 passed in 8.71s
```

## Dev dry-run — plumbing check, not a result

Job `25452526.aqua`. Stand-in mapping because **no sidekick archive exists yet**:

| Report label | Archive (read-only) |
|---|---|
| `planner_alone` | `/scratch/n12194778/sidekick/results/hj1b_planner_20260915` |
| `executor_alone` | `.../hj1r_exec8b_20260916` |
| `prompt_only` | `.../hj1r_prompt_only_20260916` |
| `fixed_k` / `fixed_k_k5` | `.../hj4b_fixed_k_dev_20260917` (`--k-matched 5`) |
| `sft_plan` | `.../hj3_sft_plan_20260917` |
| `sidekick` | **same tree as `sft_plan`** (stand-in) |

`--split dev --seeds 1,2 --expected-n-tasks 57 --plumbing-check`.
57 tasks × 2 seeds = 114 cells/arm. Task-id sets match across these archives
[OBSERVED `find` unique-task counts, all 57, `comm` empty].

### A — complete stand-in matrix

Headline (verbatim):

```
PLUMBING CHECK, NOT A RESULT. COMPLETE matrix; hypothesis decisions follow.
```

exit 0. Full JSON: `campaign/workers/a12_dryrun/A_complete_standin.json`.

Arm TGC means (dev, plumbing):

| arm | tgc_mean | planner_calls_mean | n_ok | n_scored_failure |
|---|---|---|---|---|
| planner_alone | 0.684211 | 14.429825 | 101 | 13 (12 limit + 1 parse_error) |
| executor_alone | 0.017544 | 0.0 | 77 | 37 limit |
| prompt_only | 0.052632 | 1.008772 | 74 | 40 limit |
| fixed_k | 0.5 | 4.350877 | 107 | 7 limit |
| sft_plan / sidekick stand-in | 0.429825 | 1.0 | 99 | 15 limit |

These match previously recorded dev figures for planner 0.6842 and sft_plan
0.4298 [OBSERVED campaign/workers/a12_dryrun/A_complete_standin.summary.json;
docs/prereg_v1.md:57 cites 0.4298 vs 0.6842]. **Not a J10 finding.**

Registered contrasts (task-clustered, n_pairs=114, n_tasks=57):

| contrast | diff_pp | ci95_pp |
|---|---|---|
| sidekick − fixed_k TGC | −7.02 | [−15.79, 0.88] |
| sidekick − sft_plan TGC | 0.00 | [0.00, 0.00] (identical trees) |
| sidekick − planner_alone TGC | −25.44 | [−37.72, −13.16] |
| sidekick − executor_alone TGC | 41.23 | [29.82, 52.63] |
| sidekick − prompt_only TGC | 37.72 | [26.32, 49.12] |
| sidekick − fixed_k(k=5) **calls** | −3.3509 calls | ci95 [−3.7895, −2.9386] |

H2 (three-clause, plumbing): **holds = false**. Clause 1 fails (lower CI −15.79 ≱ −7);
clause 2 fails (0 ≯ 0, because sidekick was a stand-in for sft_plan); clause 3
holds (call CI upper −2.94 < 0).

H1: TGC non-inferiority fails; FCD billed/ledger/per-task all 1.0 (the sft_plan
archive records `planner_tokens_total: 0` — cached packets — so displacement
against planner_alone is 1.0 by arithmetic, not by a sidekick policy)
[OBSERVED campaign/workers/a12_dryrun/A_complete_standin.json H1.fcd_tokens].
H1 holds = false.

H4: `arm_absent`. H3 / f_dev / unsafe violations: not computed from these archives.

### B — missing arm

Headline (verbatim):

```
PLUMBING CHECK, NOT A RESULT. INCOMPLETE: missing_arm:sidekick
```

exit 1. H2 `refused`. Contrasts empty. Other arms still summarised.

### C — missing metric (`tgc` null, no `error_type`)

Mutated a **copy** of one cell:
`campaign/workers/a12_dryrun/stage_missing_metric/sft_plan/1/6bdbc26_3/result.json`
Scratch archives were not written.

Headline (verbatim):

```
PLUMBING CHECK, NOT A RESULT. INCOMPLETE: incomplete_arm:sidekick; unequal_cluster_sizes:sidekick
```

exit 1. `sidekick.n_missing_metric = 1`. `sidekick.tgc_mean = null` (not 0).
H2 refused.

### D — crashed episode (`tgc` null, `error_type=crash`)

Mutated copy:
`campaign/workers/a12_dryrun/stage_crash/sft_plan/1/0d8a4ee_2/result.json`

Headline (verbatim):

```
PLUMBING CHECK, NOT A RESULT. COMPLETE matrix; hypothesis decisions follow.
```

exit 0. `sidekick` error_types include `crash: 1`. `n_scored_failure` 16 vs 15
on the un-mutated stand-in. Mean stayed 0.429825 because that cell was already
TGC 0; the crash is counted, not dropped, not treated as missing.

## J10 invocation (after J9 freeze; once)

```
PYTHONPATH=src:. python scripts/analysis/j10_report.py \
  --split test_normal \
  --i-understand-this-is-the-single-j10-look \
  --seeds 1,2,3 \
  --k-matched <J9 value> \
  --tau <J9 value> \
  --arm planner_alone=... \
  --arm executor_alone=... \
  --arm prompt_only=... \
  --arm fixed_k=... \
  --arm sft_plan=... \
  --arm sidekick=... \
  [--arm fixed_k_k5=... if k_matched is not 5] \
  [--arm router_seq=...] \
  --out campaign/results/j10_report.json
```

Do not pass `--plumbing-check` on that look. If the script needs editing when it
first meets real test data, this unit has failed its purpose.
