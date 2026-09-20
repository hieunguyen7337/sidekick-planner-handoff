# R5 — B1's LoRA identity check rejects a healthy server (heredoc eats the piped body)

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
This is a narrow, urgent fix on the critical path. Do only what is below.

## What happened (observed, job `25558683`, 2026-09-20)

The B1 smoke reached a **healthy** vLLM server and then killed itself:

```
[b1] vllm port answered after 85s
[b1] FATAL: /v1/models JSON did not parse: Expecting value: line 1 column 1 (char 0)
[b1] FATAL: lora identity check failed
```

The server was fine. Its own log shows `GET /v1/models HTTP/1.1" 200 OK` **twice**
[`/scratch/n12194778/sidekick/logs/b1_pilot_train_20260920.25558683.aqua_vllm.log`], once for the
port probe and once for this very check. The 200 response was produced and then thrown away.

## The cause

`b1_vllm_require_lora_ids` at `scripts/pbs/b1_pilot.pbs:604-627` does:

```
printf '%s\n' "${body}" | "${PY}" - "$@" <<'PY'
...
body = sys.stdin.read()
PY
```

`python -` means *read the program from stdin*, and the heredoc is a later stdin redirection, so it
wins over the pipe. The interpreter consumes the heredoc as its program, `sys.stdin.read()` then
returns the empty string, and `json.loads("")` raises exactly
`Expecting value: line 1 column 1 (char 0)`. The body was never readable by that process.

The sibling implementation in `scripts/pbs/hj8_frontier.pbs` (`hj8_vllm_identity_check`) does not
have this bug because it passes the program with `-c` and leaves stdin free for the pipe. That job
is running correctly right now. **Do not touch `hj8_frontier.pbs`.**

## Fix

In `scripts/pbs/b1_pilot.pbs` only, make the body actually reach the parser. Either:
- pass the program via `"${PY}" -c '...'` so stdin stays connected to the pipe (what hj8 does), or
- write `${body}` to a `mktemp` file and pass that path as `sys.argv[1]`, reading the file.

Keep the check's behaviour otherwise identical: it still prints the ids and the required aliases,
still FATALs when a required alias is absent, and still FATALs when the body is genuinely not JSON.
Preserve the existing message strings so the post-mortem's citations stay true.

## The part that matters more than the fix

**This guard was only ever tested on bad input.** R2 verified that it fails when an alias is
missing; nobody verified that it *passes* when the server is correct. That is how a check that
rejects every healthy server reached a live job. It is the same failure shape as the smoke gate
this campaign just repaired: a gate whose passing path was never exercised.

So the regression test must cover **both directions**:
1. a well-formed `/v1/models` body containing the required alias → the function **succeeds** and
   prints the ids (this is the case that was missing and that broke the run)
2. a well-formed body missing the required alias → FATAL naming the missing alias
3. a body that is genuinely not JSON (e.g. an HTML error page) → FATAL with the parse message
4. an empty body → FATAL, and the message must make clear the body was empty rather than
   blaming the server's JSON

Add these to the existing harness `campaign/workers/scratch_A20/test_b1_pilot_guards.py`, which
you own, and keep every currently-passing case passing.

Then audit the rest of `b1_pilot.pbs` for the **same `| "${PY}" - ... <<'PY'` pattern** and report
every other occurrence you find, whether or not it is reachable. If any other block pipes data into
a heredoc-fed interpreter, it has the same defect; fix it the same way and say so.

## Constraints

- `aquarius01` is a login node — steering only. No python, pip, tar, rsync there. Tests and any
  interpreter run go in a PBS job via `hpc bash -c '...'`. `timeout` on every command. BLAS 1 thread.
- Do not commit, do not run git, do not `qsub` any GPU job.
- Do not edit `scripts/pbs/hj8_frontier.pbs`, `src/sidekick/runner.py`, or anything under
  `scripts/analysis/`. `docs/prereg_b1_pilot.md` is frozen.
- Do not write under `/scratch/.../results/`.
- Full suite must stay at **433 passed, 1 skipped**: `-m pytest tests -q --import-mode=importlib`.
  `bash -n scripts/pbs/b1_pilot.pbs` must be clean. Report the exact final line.

## Return contract

Write `campaign/workers/STATUS_R5.md` as you go. Tag claims `[OBSERVED <path>:<line>]` or
`[INFERRED]`. Final report, eight lines or fewer: the fix, the four test cases and the evidence
each behaved correctly, every other occurrence of the heredoc-stdin pattern you found, the suite's
final line.
