# Archived HJ-1 results

One `result.json` per line, 114 lines per arm, 456 runs total — every scored episode of HJ-1
Classes A, B and C as run on 2026-09-15/16. Plus each campaign's `manifest.json`.

These live here because the working copies are on `/scratch/n12194778/sidekick/results`, which is
purge-prone, and because they are what every number in `../RUNS.md` and `../hj1_gate.json` was
computed from. They are small (≈ 224 KB total) and cost real GPU and planner time to produce.

| file | arm | TGC |
|---|---|---|
| `hj1b_planner_20260915.runs.jsonl` | `planner_alone` (gpt-5.6-luna) | 0.684 |
| `hj1a_exec8b_20260915.runs.jsonl` | `executor_alone` (granite-4.2-8b, zero-shot) | 0.000 |
| `hj1c_prompt_only_20260916.runs.jsonl` | `prompt_only` (luna plans once, 8b executes) | 0.000 |
| `hj1c_fixed_k_20260916.runs.jsonl` | `fixed_k` (luna reviews every 5 steps, 936 calls) | 0.000 |

**Not archived here: the per-step `events.jsonl` trajectories** (~30 MB across the three arms), which
stay on `/scratch` under the campaign ids in each manifest. They hold the actual actions and
environment responses and are the input M4 would train on, so back them up before any `/scratch`
purge — they are not reproducible without re-spending the GPU time and the planner quota.

⚠ `hj1c_fixed_k`'s manifest was written while the campaign gate still had the `codex-exec`
provenance bug, so the job log for it ends in `[gate] FAIL`. That verdict is wrong and is explained
in `../RUNS.md`; re-graded from these same files after the fix, all three planner-using arms gate
**PASS**.

⚠ Read each manifest's `git_commit_source` before trusting its `git_commit`. Two of these campaigns
predate `SIDEKICK_START_COMMIT` and self-label as `manifest time (MAY NOT be the code that ran)`;
`../RUNS.md` is the provenance of record and names the real commit per job.

⚠ Event logs written before 2026-09-16 for any *re-run* task contain the failed attempt and the
retry concatenated — `purge_broken` used to delete only `result.json`, not the directory. The
`result.json` rows archived here are unaffected, since each run rewrites its own.
