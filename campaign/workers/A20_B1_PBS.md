# A20 (U-B1PBS) — B1 pilot PBS harness

**Unit**: A20 / U-B1PBS  
**State**: done (2026-09-19)  
**Did not commit. Did not qsub this GPU job. Did not invoke `codex`. Did not write under `/scratch/.../results/`.**  
**Did not touch** `docs/prereg_b1_pilot.md`, `scripts/setup/branch_counterfactual.py`, `campaign/workers/scratch_A16/run_b1_pilot.py`, `src/`, `configs/`, or any other `scripts/pbs/` file.

Owned outputs:

- `scripts/pbs/b1_pilot.pbs`
- this file
- `campaign/workers/STATUS_A_20.md`
- harness (not pytest): `campaign/workers/scratch_A20/`

---

## What was built

`scripts/pbs/b1_pilot.pbs`, modelled on `scripts/pbs/hj6_branches.pbs`: same vLLM serve block, same static `--lora-modules` registration (`sft_b` → `sft_b_s123_granite8b`), same planner-auth preflight (`codex` on PATH, `~/.codex/auth.json` present, contents never printed).

The Python invocation is the committed prereg §13 command, not `scripts/setup/branch_counterfactual.py` directly [OBSERVED docs/prereg_b1_pilot.md:273-285]. Wrapper: `campaign/workers/scratch_A16/run_b1_pilot.py`.

`SMOKE_ONLY=1` (default `0`) runs that same wrapper against a **sibling** out-root `/scratch/n12194778/sidekick/results/${CID}_smoke`, waits for 16 `branch_runs.jsonl` rows (2 points × 2 conditions × 4 seeds), prints spend, and stops. It does not `--purge-broken` and does not mkdir/write the real `${CID}` tree [OBSERVED scripts/pbs/b1_pilot.pbs:226-232, 399-425]. Pattern taken from `SMOKE_ONLY` in `scripts/pbs/hj8_frontier.pbs` [OBSERVED scripts/pbs/hj8_frontier.pbs:45-47, 334-388].

---

## Sizing

| Item | Value | Why |
|---|---|---|
| `#PBS -q` | `gpu_inter` | Copied from hj6 [OBSERVED scripts/pbs/hj6_branches.pbs:3]. |
| `select` | `1:ncpus=16:ngpus=1:mem=128gb` | Copied from hj6 [OBSERVED scripts/pbs/hj6_branches.pbs:4]. **No** `qlist=gpu_inter_exec` [OBSERVED scripts/pbs/hj8_frontier.pbs:31-33]. |
| `walltime` | **`10:00:00`** | Wrapper carries `timeout 35100` (~9.75 h) [OBSERVED docs/prereg_b1_pilot.md:274]. 10 h = 36000 s, 900 s of PBS headroom over that timeout. Same walltime as hj6 [OBSERVED scripts/pbs/hj6_branches.pbs:5]. |
| Smoke wrapper timeout | 3600 s | Only when `SMOKE_ONLY=1`. Full run keeps 35100. |

---

## Flag-for-flag against committed prereg §13

Prereg block [OBSERVED docs/prereg_b1_pilot.md:259-285] vs assembled `PILOT_CMD` [OBSERVED scripts/pbs/b1_pilot.pbs:290-303] and the PBS defaults around it.

| §13 | PBS | Match |
|---|---|---|
| `SPLIT=train` | `SPLIT=train` (not overridable) | yes |
| `DATE=20260919` | `DATE="${DATE:-20260919}"` | yes (default frozen; hj6 used `date -u`) |
| `CID=b1_pilot_train_${DATE}` | `CID="b1_pilot_${SPLIT}_${DATE}"` | yes at default SPLIT/DATE |
| `REPO=.../plan-2026-09-15` | same | yes |
| `CAMPAIGN_ROOT=.../hj4_correction_train_20260917` | same default | yes |
| `CFG=${REPO}/configs/hj4_correction.yaml` | same default | yes |
| `OUT=/scratch/.../results/${CID}` | `OUT_CAMPAIGN="${OUT}/${CID}"` with `OUT=/scratch/.../results` | yes |
| `ADAPTER_SFT_B=.../sft_b_s123_granite8b` | same default | yes |
| `ALIAS_SFT_B=sft_b` | same default | yes |
| `PY=/scratch/.../env/bin/python` | `SIDEKICK_VENV/bin/python` | yes |
| `export PYTHONPATH="${REPO}/src:${REPO}/scripts/setup:..."` | both `src` and `scripts/setup` | yes (required: wrapper `import branch_counterfactual`) |
| `timeout 35100` | `PILOT_TIMEOUT_S=35100` on the full run | yes |
| `.../scratch_A16/run_b1_pilot.py` | `WRAPPER=.../scratch_A16/run_b1_pilot.py` | yes |
| `--campaign-root "${CAMPAIGN_ROOT}"` | same | yes |
| `--split train` | same | yes |
| `--out-root "${OUT}"` | `--out-root "${OUT_CAMPAIGN}"` | yes |
| `--branch-seeds 101 102 103 104` | same | yes |
| `--workers 10` | same | yes |
| `--resume` | same | yes |
| `--env appworld` | same | yes |
| `--config "${CFG}"` | same | yes |
| `--delta-band-delta 0.166` | same | yes |
| `--untreated-mode suppress_next` | same | yes |
| `--max-planner-calls-total 10000` | same | yes |

No `--limit`. `--limit` is walk-order prefix inside `collect_jobs`, applied **before** the A16 frozen-point filter [OBSERVED scripts/setup/branch_counterfactual.py:1211-1212; campaign/workers/A16_B1_PREREG.md:56]. Putting it on this command would be the wrong sample.

Static comparison also ran inside the harness (`flag_for_flag`) [OBSERVED job 25491633.aqua].

---

## `bash -n`

Login node (syntax only): `timeout 30 bash -n scripts/pbs/b1_pilot.pbs` → `bash_n_rc=0`.

Repeated inside PBS job **25491633.aqua** (cpu_inter → cpu_batch_exec, cpu1n040): `bash_n_rc=0` [OBSERVED /home/n12194778/.hpc-spool/20260919-150810-2949754.out:3-4].

---

## Three guards, each shown to fire

Guards are functions in the PBS script, invoked on the assembled command / out-root / the job’s own `PREFLIGHT` line — not comments, and not delegated to the wrapper. `B1_GUARD_SELFTEST=1` runs them without touching vLLM, scratch results, or the planner.

Harness: `campaign/workers/scratch_A20/test_b1_pilot_guards.py` (not under `tests/`; `pyproject.toml` `testpaths = ["tests"]` [OBSERVED pyproject.toml:22]). Why not the suite: these are bash-script guards. Putting them in `tests/` would change the 413-test baseline and still would not execute the PBS job. A selftest mode on the script plus a scratch harness fits the shape.

Verbatim from job **25491633.aqua**:

**1. PREFLIGHT `branches_to_run` ≠ 1600** (fed `6216`):

```
[b1] PREFLIGHT parsed branches_to_run=6216 max_planner_calls_total=10000
[b1] FATAL: PREFLIGHT branches_to_run is 6216, expected 1600 (6216 means the wrapper was not used)
```

[OBSERVED /home/n12194778/.hpc-spool/20260919-150810-2949754.out:11-12]

Cap mismatch also aborts (fed `1600` jobs but cap `999999`):

```
[b1] FATAL: PREFLIGHT max_planner_calls_total is 999999, expected 10000
```

[OBSERVED same file:15]

Good line (the A16 PREFLIGHT [OBSERVED docs/prereg_b1_pilot.md:181]) passes. On the live job, the same parser reads the wrapper’s flushed `PREFLIGHT ` JSON and **kills the wrapper** if it fails, before leaving dispatch running [OBSERVED scripts/pbs/b1_pilot.pbs:349-368, scripts/setup/branch_counterfactual.py:1276-1288].

**2. Out-root is / is inside `hj6_branches_train_20260917`:**

```
[b1] FATAL: out-root is or is inside /scratch/n12194778/sidekick/results/hj6_branches_train_20260917
[b1] FATAL: that tree holds the frozen J6 schedule_live data; writing it would destroy the mode-to-mode comparison
```

Root and a child path both aborted [OBSERVED same file:20-26]. Canonical form on this cluster is `/mnt/weka/scratch/...` [OBSERVED same file:22]; both sides are `realpath -m`’d before the prefix check. The real B1 out-root passed [OBSERVED same file:28]. Checked **before** `mkdir -p "${OUT_CAMPAIGN}"` [OBSERVED scripts/pbs/b1_pilot.pbs:241-244].

**3. Assembled command missing `--untreated-mode suppress_next`:**

```
[b1] FATAL: assembled command is missing --untreated-mode suppress_next
[b1] FATAL: defaulting to schedule_live would run the contaminated estimand under this campaign id
```

Fired when the flag is absent, and when the flag is present with `schedule_live` (the argparse default [OBSERVED scripts/setup/branch_counterfactual.py:70]). The §13 command with `suppress_next` passed [OBSERVED same file:29-38].

`n_pass=11 n_fail=0` / `ALL_GUARDS_FIRED` [OBSERVED same file:39-40].

---

## Suite

Same job, after the harness:

```
413 passed, 1 skipped, 1 warning in 29.48s
```

[OBSERVED /home/n12194778/.hpc-spool/20260919-150810-2949754.out:55]. Interpreter `/scratch/n12194778/sidekick/env/bin/python`. Never fewer than 413 passed; zero failures.

---

## Paths checked (existence only; nothing under `/scratch/.../results/` was written)

| Path | Result |
|---|---|
| `campaign/workers/scratch_A16/run_b1_pilot.py` | file [OBSERVED `test -f`] |
| `campaign/workers/scratch_A16/b1_pilot_points.txt` | file, 206 lines = header + 200 points [OBSERVED `wc -l`] |
| `configs/hj4_correction.yaml` | file [OBSERVED `test -f`] |
| `/scratch/.../results/hj4_correction_train_20260917` | directory [OBSERVED `test -d`] |
| `/scratch/.../artifacts/adapters/sft_b_s123_granite8b` | directory with `adapter_config.json` + `adapter_model.safetensors` [OBSERVED `ls`] |
| `/scratch/.../env/bin/python` | executable [OBSERVED `test -x`] |
| `/scratch/.../env/bin/vllm` | executable [OBSERVED `test -x`] |
| `/scratch/.../results/hj6_branches_train_20260917` | directory exists (the tree the out-root guard must refuse) [OBSERVED `test -d`] |

---

## Clashes with §13 / the brief (reported; implemented as specified)

1. **§13 says the job’s stdout “begins with” `PREFLIGHT`.** It will not. The PBS script echoes env/vLLM health first, and `run_branches` prints `PREFLIGHT` only after `collect_jobs` [OBSERVED docs/prereg_b1_pilot.md:288; scripts/setup/branch_counterfactual.py:1256-1288]. The guard parses the `PREFLIGHT` JSON line from the wrapper log and aborts on mismatch. It does not require that line to be byte 0 of stdout.

2. **`--resume` plus “FATAL if `branches_to_run` is not 1600”.** §13 includes `--resume` [OBSERVED docs/prereg_b1_pilot.md:280]. On a non-empty `branch_runs.jsonl`, `collect_jobs` skips completed keys, so PREFLIGHT `branches_to_run` is the remainder, not 1600 [OBSERVED scripts/setup/branch_counterfactual.py:1142-1180, 1280]. This harness still asserts `== 1600`, as the brief required. A **first** launch against an empty out-root is 1600 (A16’s filter [OBSERVED campaign/workers/scratch_A16/run_b1_pilot.py:53-57]). A resume of a partial B1 run will be killed by this guard until a later unit (or the orchestrator) widens it to “≠ 6216, and 1600 on a fresh tree”. Not weakened here.

3. **`--limit` is not a smoke selector for the frozen 200.** Smoke therefore does **not** add `--limit`. It uses the §13 wrapper so PREFLIGHT stays 1600, writes a sibling `_smoke` tree, and stops after 16 jsonl rows. `--workers 10` is unchanged, so a handful of extra in-flight branches may finish after the stop [INFERRED]. Spend is printed from the smoke jsonl, then vLLM is torn down.

4. **hj6 PYTHONPATH is `src` only.** §13 adds `scripts/setup`. Implemented §13. Without it the wrapper cannot `import branch_counterfactual`.

5. **hj6 default DATE is `date -u`.** §13 freezes `20260919`. Default DATE is `20260919`.

Nothing in §13 was changed to “fix” these. The PBS command string matches the committed block.

---

## Not done, by instruction

- No `qsub` of `scripts/pbs/b1_pilot.pbs`.
- No GPU job.
- No `codex` / planner call.
- No commit.
- No writes under `/scratch/n12194778/sidekick/results/`.
