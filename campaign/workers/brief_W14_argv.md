# W-14 — pass the planner prompt on stdin, not in argv

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## The defect

`src/sidekick/agents/planner.py:101` — `build_codex_argv` puts the whole prompt into the
argument vector. Both branches do it; the resume branch at `:131` is:

```python
cmd.extend([thread_id, prompt])
```

Linux caps a **single** argument at `MAX_ARG_STRLEN` = 32 pages = **128 KiB**, independently
of the much larger total `ARG_MAX`. A `fixed_k` prompt is the rendered transcript plus the API
digest; on the train split these reach ~19k tokens and cross the limit on long episodes.
`execve` then fails with `E2BIG`, which surfaces as:

```
OSError: [Errno 7] Argument list too long: 'codex'
```

Measured across J6: **38 branches** died this way (25 train, 13 dev). It is small but **not
random** — it fires on the longest transcripts, so the episodes it removes are the long,
struggling ones, and any statistic conditioned on episode length inherits a selection bias.

## The fix

`codex exec --help` states, verbatim:

> `[PROMPT]` … instructions are read from stdin. If stdin is piped and a prompt is also
> provided, stdin is appended as a `<stdin>` block

So the prompt goes to the child's **stdin**.

🔺 **Read that second sentence carefully.** Passing a prompt argument *and* piping stdin
**appends** rather than replaces — it would send the prompt twice, once as argv (still over
the limit) and once as a `<stdin>` block. So when piping you must **drop the prompt argument
entirely**. For the resume branch that means the argv ends at `thread_id` with no prompt
after it.

Requirements:

- `build_codex_argv` no longer places `prompt` in the returned argv. Decide whether it still
  takes `prompt` as a parameter; if it does not, update every caller.
- The subprocess call that currently runs the argv must write the prompt to the child's stdin
  and close it. Today the call site passes `< /dev/null` semantics or similar — find it
  (around `planner.py:389-450`) and change it deliberately; do not leave stdin inherited,
  because a child that blocks reading stdin forever is the failure this trades into.
- Encoding is UTF-8. Prompts contain code, tracebacks and non-ASCII.
- Keep everything else identical: the model, `model_reasoning_effort`, `--json`,
  `--skip-git-repo-check`, `--disable shell_tool`, `--output-schema`, sandbox, and the
  never-`--ephemeral` rule at `:112`. This changes **how the prompt is delivered** and nothing
  else.

## Tests

- `build_codex_argv` output contains **no** element longer than 128 KiB, asserted for both
  the fresh and the resume branch, including with a deliberately huge prompt (say 300 KiB);
- the resume argv ends with `thread_id` and does **not** contain the prompt;
- a fake `codex` binary (a small script already in the test style used here, or a new one)
  receives the prompt on stdin and echoes it back, and the client parses the result;
- a 300 KiB prompt round-trips without raising `OSError`, which is the regression test for
  this defect — it must fail against the current code;
- existing planner tests stay green.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Everything that computes goes in a PBS job:
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc '<cmd>'`, BLAS pinned to one thread,
  interpreter `/scratch/n12194778/sidekick/env/bin/python`.
- 🔺 **Do not make a real `codex` call, and do not submit any GPU job.** The Codex quota is
  exhausted until 2026-09-19 ~21:13 — that exhaustion is what this investigation was about.
  Every test must use a fake binary. A real call will fail and tell you nothing.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Run the suite as `PYTHONPATH=src:. python -m pytest tests -q --import-mode=importlib`.
  Current state to match or beat: **335 passed, 1 skipped, 0 failures.**
- Write `campaign/workers/STATUS_W_14.md` with resume state.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- One line with `path:line` for where the prompt is now written to stdin.
- Confirmation, with the test name, that the 300 KiB regression test fails on the old code
  and passes on the new.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
