PASS

## LFS fix (scripts/setup/fix_appworld_lfs.sh, jobs 25384183 / 25384190)

Both Git LFS pointer stubs were replaced by downloads from
`https://media.githubusercontent.com/media/StonyBrookNLP/appworld/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/.source/<name>.bundle`,
with sha256 verified against the pointers before install:

- `apps.bundle`: 193,950 bytes, sha256 `88d21fc526c1655bb3eee4adfca78ccac793921e4506f28f734ecdb19af77a62` — matched.
- `tests.bundle`: 204,701 bytes, sha256 `7b93343db5efd81b542e68e68150dd5ea5d59d8dcd64137d41bde4027b235dc9` — matched.

A full scan of the installed `appworld` package found no other LFS pointers.

Important CLI gotcha [OBSERVED appworld/cli.py:367,523]: `appworld download data` and
`appworld verify tasks` take `--root` defaulting to `.` which **overrides** `APPWORLD_ROOT`
via `path_store.update_root`. Always pass `--root $APPWORLD_ROOT` explicitly.

## `appworld verify tasks` (verbatim)

```
🧪 Running end-to-end task verification ━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
✅ Passed 147/147 tasks
```

## Split sizes (`load_task_ids`, job 25384720)

| split | got | expected | |
|---|---|---|---|
| train | 90 | 105 | **differs — finding** |
| dev | 57 | 60 | **differs — finding** |
| test_normal | 168 | 168 | matches |
| test_challenge | 417 | 417 | matches |

The on-disk dataset files confirm 90/57/168/417 (`wc -l` on `…/appworld/data/datasets/*.txt`,
files have no trailing newline). [INFERRED] The 105/60 expectation likely comes from a different
AppWorld data release; the pinned commit's data bundle ships 90 train / 57 dev. Any per-split
task-count assumptions downstream must use 90/57.

## `world.evaluate()` structure (single task, ground_truth_mode="full")

```json
{"success": true, "difficulty": 1, "num_tests": 2,
 "passes": [{"requirement": "assert answers match.", "label": "no_op_fail"},
            {"requirement": "assert no model changes.", "label": "no_op_pass"}],
 "failures": []}
```

## Timings

- first world load: 2.283 s; later world load: 0.165 s [OBSERVED logs/g2_appworld_gate.json]
- mean `world.execute("print(1)")` over 20 calls: 0.01644 s (min 0.0119, max 0.0458)

## 8-process parallel result (spawn pool, 8 distinct train tasks)

- wall time: 4.72 s, all 8 succeeded (`all_ok: true`)
- peak RSS per process: 585–606 MB (max 606,192 KB)
- max safe pool on a 32-CPU node: CPU-bound → 32; memory-bound at 70 % of 256 GB → 309;
  **recommended pool = 32** (one world per process, freezegun time control)

## API docs size

- raw: 475,943 chars ≈ ~119k tokens (÷4 heuristic, [INFERRED])
- compressed (`compress_parameters()`): 228,378 chars ≈ ~57k tokens ([INFERRED])
- compression ratio ≈ 2.08×

## Caveats

- Two early jobs (25384179/25384183) raced on the shared `/scratch` data dir; the final clean
  gate run (25384720, `failures=0`) is authoritative. Concurrent gate jobs from other units
  against the same APPWORLD_ROOT will collide — serialize them.
- Full gate JSON: `/scratch/n12194778/sidekick/logs/g2_appworld_gate.json`.
