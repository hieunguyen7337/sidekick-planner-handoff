# U1b — fix the AppWorld install (Git LFS pointers) and finish gate G2 (owner: Cline, fresh session)

## What is broken, and the verified fix

Gate G2 failed in job 25384166 with:

```
Exception: File /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/appworld/.source/apps.bundle
is a Git LFS pointer and not a bundle file.
```

**Cause, diagnosed and confirmed.** AppWorld was installed with `uv pip install git+https://github.com/StonyBrookNLP/appworld@<commit>`. A pip-from-git install does **not** fetch Git LFS objects, and `git-lfs` is **not installed on this cluster** (`git lfs version` → "'lfs' is not a git command"). So the two encrypted data bundles arrived as 131-byte pointer stubs instead of the real files.

**The fix, already verified by HTTP HEAD — do not redesign it.** GitHub serves LFS content over plain HTTPS at `media.githubusercontent.com`. Both objects return HTTP 200 with the exact sizes the pointers declare:

| file | pointer says | media endpoint returns |
|---|---|---|
| `apps.bundle` | 193950 bytes | **200, content-length 193950** |
| `tests.bundle` | 204701 bytes | **200, content-length 204701** |

URL pattern (commit is pinned, do not change it):

```
https://media.githubusercontent.com/media/StonyBrookNLP/appworld/42b5bcf3cd334fee33f0c37c02070a9f5807add5/src/appworld/.source/<name>.bundle
```

Target directory to overwrite:

```
/scratch/n12194778/sidekick/env/lib/python3.12/site-packages/appworld/.source/
```

## What to do

Write `scripts/setup/fix_appworld_lfs.sh` (idempotent, safe to re-run) that, **inside a PBS job**:

1. For each of `apps.bundle` and `tests.bundle`: skip if the local file is already larger than 1000 bytes and is not an LFS pointer (first line is not `version https://git-lfs.github.com/spec/v1`); otherwise download from the media URL to a temporary file, **verify the sha256 matches the `oid sha256:` line in the pointer it replaces** (capture those before overwriting), verify the byte size matches, then move it into place.
   - expected sha256 for `apps.bundle`: `88d21fc526c1655bb3eee4adfca78ccac793921e4506f28f734ecdb19af77a62`
   - expected sha256 for `tests.bundle`: `7b93343db5efd81b542e68e68150dd5ea5d59d8dcd64137d41bde4027b235dc9`
   - **If a checksum does not match, stop and report. Do not install an unverified bundle.**
2. Check whether any other file under the installed `appworld` package is also an LFS pointer (grep the first line of small files) and handle those the same way. Report what you found.
3. Re-run `appworld install`, then `appworld download data`, then `appworld verify tasks`, with
   `APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld` and
   `HF_HOME=/scratch/n12194778/hf`. Report each result verbatim.
4. Then run the existing gate script `scripts/setup/g2_appworld_gate.py`, which is already written and
   does the real measurements. Do **not** rewrite it. Invoke it the way
   `scripts/pbs/g2_appworld.pbs` does.

The Python interpreter to use is `/scratch/n12194778/sidekick/env/bin/python`; the environment is
already built (vLLM 0.29.0, torch 2.13.0, AppWorld at the pinned commit).

## Report

Write `docs/feasibility/g2_appworld.md` with, at minimum:

- **Verdict** PASS / PARTIAL / FAIL on the first line.
- Whether the LFS fix worked, with the checksums you verified.
- `appworld verify tasks` output verbatim.
- The split sizes actually returned by `load_task_ids` for `train|dev|test_normal|test_challenge`
  (expected 105 / 60 / 168 / 417 — report what you got, and if it differs that is a finding).
- The structure of what `world.evaluate()` returns (the harness depends on it).
- Timings: first world load, later world load, mean `world.execute("print(1)")` over 20 calls.
- The 8-process parallel result: wall time, how many succeeded, peak RSS per process, and the maximum
  safe pool size for a 32-CPU node.
- The size of the API documentation in characters and rough tokens, raw and compressed.

## Constraints

- **Never run Python, `appworld`, downloads or installs on the login node `aquarius01`.** Everything
  goes in a job:
  `timeout 3000 hpc -c 8 -m 32gb -t 00:45:00 <script>` (that helper reaches the interactive queue),
  or `qsub` — but note that a batch `qsub` is routed to the contended `cpu_batch_exec`.
- `timeout <seconds>` in front of **every** command.
- **Do not run any `git` command.** Do not touch `.git/` or `.claude/worktrees/`.
- Walltime <= 01:00:00 on any job, and **submit nothing after 2026-09-16 03:00 AEST** (maintenance at
  ~08:00 stops jobs from starting).
- You own `scripts/setup/fix_appworld_lfs.sh`, `docs/feasibility/g2_appworld.md` and
  `campaign/workers/logs/U1b_STATUS.md`. Another agent may also be working on the same problem — if you
  find the bundles are already fixed, say so and move straight to step 3.
- Never print the value of a token or credential.

## Return contract

At most 15 lines: the verdict, whether the checksums matched, the `verify tasks` result, the split
sizes, the parallel-pool finding, and anything that would block the pilot campaign. Tag claims
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
