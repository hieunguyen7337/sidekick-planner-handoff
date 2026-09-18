# W-17 — `fit_temperature` does not minimise NLL; fix it and re-run J7

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**One production file in scope: `scripts/setup/fit_feature_verifier.py`.**
Other workers own `scripts/setup/branch_counterfactual.py` and
`src/sidekick/agents/planner.py` — **do not touch either.**

## The defect

`fit_temperature` [OBSERVED scripts/setup/fit_feature_verifier.py:311-333] claims to find the
temperature `T` minimising dev NLL of `sigmoid(z/T)`, by 1-D Newton steps. It does not.

Write `z_i` for the raw logit and `p_i = sigmoid(z_i / T)`. Then

```
dNLL/dT = (1/T^2) * sum_i (y_i - p_i) * z_i
```

so the stationary condition is `sum_i (y_i - p_i) * z_i = 0`. The implementation instead
accumulates

```
num += (1.0 / T - (yi - p)) * z * z / (T * T)     [OBSERVED :320-322]
den += z * z / (T * T)
```

which carries a spurious `1/T` term and weights by `z^2` rather than `z`. Its fixed point is
`sum (y-p) z^2 / sum z^2 = 1/T`, which is not NLL stationarity.

### Measured, not merely derived

A check on synthetic data where the correct `T` is known by construction, run 2026-09-18:

| case | true T | `fit_temperature` returned | NLL at that T | NLL at the grid optimum |
|---|---|---|---|---|
| labels drawn from the model | 1.0 | **0.0500** (the clamp floor) | 3.4772 | 0.5101 |
| logits 3x too large | ~3 | **0.0500** | 5.6441 | 0.5101 |
| uninformative scores, random labels | large | **1.0000** (never moved) | 2.0121 | 0.7020 |

In every regime it either pins to the clamp floor or fails to move, and it is **worse than
doing nothing at all** (`T = 1.0`). The reproduction script is
`/home/n12194778/.claude/jobs/91578989/tmp/check_temp.py`; read it, and re-run it if you want
to see the failure yourself before changing anything.

### What this corrupted in the J7 artifact

`artifacts/verifiers/feature_lr_20260918/metrics.json` reports `temperature: 0.129`, dev
`brier: 0.480`, dev `ece: 0.490`. The temperature is an optimiser artifact, and because
`rescale` [OBSERVED :411-417] divides the logit by it, the reported calibration metrics measure
miscalibration that the calibration step itself introduced.

🔺 **Dev AUROC 0.5917 is NOT affected and must not change.** AUROC is a rank statistic and
dividing every logit by a positive constant is monotone, so it is invariant. Treat an AUROC
that moves after your fix as evidence you broke something else.

## Requirements

1. Replace the Newton iteration with a **robust 1-D minimiser of the dev NLL** over `T` — a
   golden-section search or a bisection on the derivative over a wide bracket (e.g. `[0.05, 20]`)
   is entirely sufficient and easy to get right. Minimise over `log T` if you prefer. Do not
   hand-roll another Newton step.
2. **Enforce the invariant that calibration may never make things worse:** if the NLL at the
   chosen `T` is not below the NLL at `T = 1.0`, return `1.0`. State in the report where this
   guard lives.
3. Record in `metrics.json` the dev NLL **before** and **after** scaling, so this failure mode
   is visible in the artifact next time rather than needing a derivation to find.
4. Add a threat-to-validity line noting that the temperature is fit on dev and the dev
   calibration metrics are then reported on that same dev split, so they are in-sample and
   optimistic. (This is what the plan pre-registered; we are recording it, not changing it.)
5. Re-run J7 with the command below and report the new numbers.

## Tests (pytest, in the existing style/location for this script)

- The three cases in the table above, as regression tests: well-specified data recovers
  `T ≈ 1` (assert a band, say 0.7–1.4); logits scaled by 3 recover `T ≈ 3` (band 2.2–4.0);
  uninformative scores against random labels drive `T` large (assert `T >= 5`).
- The invariant: on all three, `NLL(T_fit) <= NLL(1.0)`.
- A degenerate input (single class, or empty) returns `1.0` and does not raise.

## The J7 re-run

```
timeout 1800 hpc -c 4 -m 16gb -t 00:30:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python scripts/setup/fit_feature_verifier.py --train-branches /scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl --dev-branches /scratch/n12194778/sidekick/results/hj6_branches_dev_20260917/branches.jsonl --train-campaign /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --dev-campaign /scratch/n12194778/sidekick/results/hj4b_fixed_k_dev_20260917 --out artifacts/verifiers --date 20260918'
```

Report old vs new side by side: temperature, dev NLL before/after, dev Brier, dev ECE, and dev
AUROC (which must be unchanged at 0.5917).

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Everything that computes goes in a PBS job as shown. Keep BLAS at one thread.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit a GPU job.** The Codex quota is
  exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`** — frozen evidence.
- 🔺 **Do not tune anything against dev metrics.** You are fixing an optimiser, not improving a
  score. If the fixed calibration makes dev Brier worse than the broken one did, report that;
  do not chase a number.
- **Do not commit.**
- Suite: `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`, currently
  **339 passed, 1 skipped** — never fewer, never a failure.
- Write `campaign/workers/STATUS_W_17.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- `path:line` for the new minimiser and for the never-worse-than-T=1 guard.
- The old-vs-new table described above.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
