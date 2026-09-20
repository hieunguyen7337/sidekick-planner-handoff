# STATUS E1 — retain interventions

**Unit:** E1 — `src/sidekick/training/matched_sft.py`, `tests/unit/test_matched_sft.py`
**State:** done
**Last update:** 2026-09-20

## Owned files

- `src/sidekick/training/matched_sft.py`
- `tests/unit/test_matched_sft.py`
- this STATUS

No training, no GPU, no `qsub` of campaign jobs, no git, no writes under `/scratch/.../results/`. Did not edit `sft_data.py`, `loop.py`, `configs/`, or frozen prereg docs.

## What changed

`_combine_teacher_and_correction` takes keyword-only `allow_interventions: bool = False`. The `INTERVENTION:` raise fires only when `not allow_interventions`. ASK guard is unchanged (`allow_ask_targets = extra_summary is not None`). [OBSERVED src/sidekick/training/matched_sft.py:584-616]

`build_sft_b_plus` and `build_ask_dataset` pass `allow_interventions=not strip_interventions`. `--no-strip-interventions` is unchanged. [OBSERVED src/sidekick/training/matched_sft.py:742, :793, :809]

Summary/manifest key `intervention_mode` is `"retain"` or `"strip"` in the combine dict (and nested correction summary). [OBSERVED src/sidekick/training/matched_sft.py:510, :701]

Default strip path: omitted `allow_interventions` still raises on an `INTERVENTION:` turn. [INFERRED from default False at :593 plus tests]

## Tests [OBSERVED tests/unit/test_matched_sft.py]

Synthetic records only, via `_combine_teacher_and_correction`.

1. `:493` default still raises `RuntimeError` matching `INTERVENTION:`.
2. `:498` `allow_interventions=True` writes rows that still contain `INTERVENTION:`.
3. `:511` ASK_PLANNER target still raises when `extra_summary is None`, with and without `allow_interventions=True`.
4. `:518` retain mode still raises `ValueError` matching `Split leakage` for `held_out_task`.
5. `:527` `intervention_mode` is `"strip"` / `"retain"` in the return dict and `.manifest.json`.

## Suite [OBSERVED hpc job 25573042.aqua]

Command:

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

Verbatim final line:

```
447 passed, 1 skipped, 1 warning in 37.37s
```

New-tests-only job 25573036.aqua: `5 passed, 11 deselected in 0.74s`. [OBSERVED that job stdout]

Did not build a real dataset or run `--no-strip-interventions` against campaign logs.
