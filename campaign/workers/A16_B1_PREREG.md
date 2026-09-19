# A16 (U-B1PRE) — report

**Unit**: A16 / U-B1PRE  
**State**: done (2026-09-19)  
**Did not commit. Did not submit the pilot. Did not invoke `codex`. Did not write under `/scratch/.../results/`.**  
**Did not touch** `src/`, `configs/`, `scripts/setup/branch_counterfactual.py`, `docs/prereg_v1.md`, `campaign/RUNS.md`.

Owned outputs:

- `docs/prereg_b1_pilot.md` — the frozen analysis plan
- this file
- `campaign/workers/STATUS_A_16.md`
- helpers for PREFLIGHT and the orchestrator (not a rollout): `campaign/workers/scratch_A16/`

---

## Prereg written

`docs/prereg_b1_pilot.md` sections:

1. The claim being tested  
2. Design (decided; do not reopen)  
3. Point selection (deterministic, frozen before the run)  
4. Primary population  
5. Primary hypotheses (both must hold)  
6. Decision rule (fixed now), **including the inconclusive branch**  
7. Secondary outcomes (labelled secondary)  
8. Cost: PREFLIGHT, expected spend, and the hard cap  
9. Stopping, resume, and truncation  
10. What would falsify it  
11. What this licenses  
12. Threats, and clashes with the unit brief  
13. Submission command (orchestrator only)  
Appendix. Frozen 200-point list  

Primary hypotheses, copied from the brief, not softened:

- **B1a** — mean Δ > 0 and one-sided paired sign-flip **p < 0.05** on the primary population.
- **B1b** — (`needed` − `needless`) > 0, two-sided **p < 0.05**, same null, δ = **0.166**.
- Both hold → `sft_c` trainable, H4 returns. Neither → negative result with a mechanism, H4 stays closed. Exactly one → **inconclusive**, no further quota without a new plan.

Permutation: 10,000 paired sign-flips, `numpy.random.default_rng(20260918)`, W-24 code path [OBSERVED campaign/workers/scratch_W24/permnull.py:25, 273-277, 365].

Primary population: complete points with `mean(untreated) < 1.000`. All-complete always reported alongside.

---

## Point selection

Rule, frozen: unique `(seed, task_id, i)` in J6 train `branch_runs.jsonl` (777 points; none previously used for clean-mode), sorted, shuffled with `random.Random(20260916)` on CPython 3.12.13, first 200.

PBS **25463506.aqua**: `unique_points=777`, `j6_complete_points=397`, `existing_suppress_next_manifests=[]`, `sample_n=200`, `sample_j6_complete=100`, `sample_j6_incomplete=100`, `sample_sha256=4ec6fa2733a141da4335240c215b605ff466e2d85a0a0f7ce55179a6ef5b1017` [OBSERVED that job’s stdout].

List: `campaign/workers/scratch_A16/b1_pilot_points.txt` and the prereg appendix.

The frozen CLI cannot subset points (`--limit` is walk-order prefix, not this draw) [OBSERVED scripts/setup/branch_counterfactual.py:1211-1212, 1395-1449]. Orchestrator entrypoint: `campaign/workers/scratch_A16/run_b1_pilot.py` (monkey-patches `collect_jobs`, refuses anything other than 200 unique points). **Not executed** by this unit.

---

## PREFLIGHT and cap

Read-only `collect_jobs` + filter, PBS **25463680.aqua**, zero branches executed, zero planner calls. Verbatim:

```
python=3.12.13 (main, May 10 2026, 19:30:01) [Clang 22.1.3 ]
frozen_points=200
collect_jobs_unfiltered=6216
collect_jobs_filtered=1600
filtered_unique_points=200
frozen_keys_missing_from_collect=0
untreated_modes=['suppress_next']
PREFLIGHT {"branches_to_run": 1600, "factor_source": "config limits.max_planner_calls (per-episode cap)", "max_planner_calls_total": 10000, "per_branch_planner_call_factor": 81, "projected_planner_calls": 129600}
no_branches_executed=True
```

[OBSERVED job 25463680.aqua]. Factor 81 is `limits.max_planner_calls` in `configs/hj4_correction.yaml` [OBSERVED configs/hj4_correction.yaml:42] [OBSERVED scripts/setup/branch_counterfactual.py:1273-1284]. Unfiltered PREFLIGHT would be 6216 × 81 = 503,496 [INFERRED].

**Proposed `--max-planner-calls-total 10000`.** Script projection 129,600 is the per-episode cap times jobs, not a realistic spend. J6 train: 23,769 calls / 6,216 branches [OBSERVED docs/FOLLOWUPS.md:688] → expected 1,600 × 23769/6216 = **6,118** [INFERRED]. Cap is ~1.63× that centre and far below J6’s 37,368 [OBSERVED docs/FOLLOWUPS.md:690]. If it binds before 1,600 dispatched, the prereg forbids analysing the prefix as the planned sample.

---

## Recommended submission command (orchestrator, after ~21:13 today)

Do not run this from a worker. Do not reuse `hj6_branches_train_20260917` as `--out-root`.

```bash
SPLIT=train
DATE=20260919
CID=b1_pilot_train_${DATE}
REPO=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
CAMPAIGN_ROOT=/scratch/n12194778/sidekick/results/hj4_correction_train_20260917
CFG=${REPO}/configs/hj4_correction.yaml
OUT=/scratch/n12194778/sidekick/results/${CID}
PY=/scratch/n12194778/sidekick/env/bin/python

# PBS copy of scripts/pbs/hj6_branches.pbs (vLLM + LoRA as there), then:
export PYTHONPATH="${REPO}/src:${REPO}/scripts/setup:${PYTHONPATH:-}"
timeout 35100 "${PY}" "${REPO}/campaign/workers/scratch_A16/run_b1_pilot.py" \
  --campaign-root "${CAMPAIGN_ROOT}" \
  --split train \
  --out-root "${OUT}" \
  --branch-seeds 101 102 103 104 \
  --workers 10 \
  --resume \
  --env appworld \
  --config "${CFG}" \
  --delta-band-delta 0.166 \
  --untreated-mode suppress_next \
  --max-planner-calls-total 10000
```

Kill the job if PREFLIGHT `branches_to_run` is not 1600.

---

## Clashes with the specification (said, not silently adjusted)

1. **`n_later = 0` by construction is false of A8.** `suppress_next` omits the next scheduled tick after `s`; later ticks stay live [OBSERVED scripts/setup/branch_counterfactual.py:81-91, 88-91]. The prereg keeps B1a/B1b as specified and adds `n_later` as a **secondary** manipulation check. The frozen script was not changed.
2. **Train split recomputes δ.** `freeze_from_train=(split == "train")` overwrites `--delta-band-delta` from this run’s treated pairs [OBSERVED scripts/setup/branch_counterfactual.py:816-818, 1356-1358]. Labels for the decision rule are computed at **0.166** from raw GPR, ignoring the pilot manifest.
3. **No point-list CLI.** A raw `branch_counterfactual.py` on this campaign-root is 6,216 branches. The wrapper is mandatory. `--limit 1600` is the wrong sample.
4. **“Contestable” ≠ W-20.** Brief: `mean(untreated) < 1.000`. W-20 also drops floors (3 J6-train points) [OBSERVED job 25463506.aqua `j6_complete_contestable_A16_mean_u_lt_1=266` vs `W20 ...=263`]. Primary follows the brief; W-20 contestable is not substituted.
5. **PREFLIGHT 129,600 is not a budget.** It is `1600 × 81`. The cap that actually bounds spend is 10,000.
6. **Half the frozen sample is J6-incomplete.** Sampling all 777 rather than the 397 complete points avoids selecting on the contaminated estimand. Realised primary `n` may be small; that is not a licence to redraw.

---

## Tests (docs-only unit; suite must not move)

PBS **25463681.aqua**, interpreter `/scratch/n12194778/sidekick/env/bin/python`. Verbatim:

```
.....................................s.................................. [ 17%]
........................................................................ [ 35%]
........................................................................ [ 53%]
........................................................................ [ 70%]
........................................................................ [ 88%]
...............................................                          [100%]
=============================== warnings summary ===============================
tests/unit/test_feature_verifier.py::test_failed_join_is_dropped_not_fitted
  /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
406 passed, 1 skipped, 1 warning in 38.76s
```

[OBSERVED job 25463681.aqua / spool `20260919-061040-2376925.out`]. Baseline in the brief was 406 passed, 1 skipped; this unit did not change it.
