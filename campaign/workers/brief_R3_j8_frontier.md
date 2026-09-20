# R3 — `scripts/analysis/j8_frontier.py`: the dev frontier, oracle headroom, gate calibration

Repo (absolute, a git worktree — work here, do not cd elsewhere):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this unit exists

Ten live J8 arms are about to run on the dev split (114 paired episodes each: 57 tasks × 2
seeds). There is **no script that can analyse them.** `scripts/analysis/j10_report.py` handles
the J10 test-split matrix only, and the one J8 analysis written before
(`campaign/workers/scratch_A15/`) was a throwaway for a single contrast. Without this script the
run produces directories nobody can turn into a result.

The thesis [`docs/prereg_v1.md:29`] is that a small local executor specialised to a frozen hosted
planner performs better **while selectively requesting planner assistance to displace hosted
planner compute**. The evidence for the displacement half lives entirely in the quality-versus-
calls frontier this script draws.

## Deliverable

New file `scripts/analysis/j8_frontier.py`. Nothing else in `scripts/analysis/` may change.

**Reuse, do not reimplement:** `j10_report.py` already contains the task-clustered paired
bootstrap and the pairing/alignment logic. Import from it or factor the shared function out into
a module both import. Two independent bootstrap implementations in one paper is a defect.

### Interface

`--arm LABEL=DIR` repeated, the same shape `j10_report.py` uses. `--out <path>` for the JSON;
a readable table on stdout.

### Per-arm columns

`n`, `n_broken`, TGC, goal_pass, planner calls per episode, planner tokens per episode.
Planner calls must be reported from the **ledger live count** (`totals.planner_calls_total`),
and where a replay-inclusive count differs it must be labelled as a separate column, never
silently substituted. Confusing these two is an error this campaign has already made.

### Contrasts and tables

1. **Paired contrasts** between any two named arms: point estimate, task-clustered bootstrap CI,
   n pairs. Pairing is by `(task_id, seed)`.
2. **Frontier table** — quality against calls per episode, with the three `fixed_k` arms (k=3,5,10)
   as the reference curve and every gated arm plotted against it.
3. **Oracle headroom** — `oracle_escalation` minus `fixed_k(k_matched)` on **both** axes
   (quality and calls). `k_matched` is the `fixed_k` arm whose calls/episode is closest to the
   arm under test; state which one was chosen in the output.
4. **H3 calibration** — AUROC and ECE of each gate's escalation scores against the dev oracle
   labels in `hj6_branches_dev_20260917/oracle_labels.json`. Report `n_positive` alongside; a
   degenerate gate that never escalates must be visible as such, not as a missing row.
5. **The F1 test**, per gated arm, as a boolean plus the numbers behind it: the arm is within
   **7 pp** of `fixed_k(k_matched)` on quality (upper CI bound on the deficit below 7 pp) **and**
   makes strictly fewer calls per episode than `fixed_k(5)` with a CI excluding zero. This is
   the paper's primary reportable claim on dev; get its definition exactly right.

### A semantic question you must answer in the output, not guess

Read `configs/hj8_oracle_escalation.yaml` and the system code it selects. The oracle labels were
derived from J6 dev branches run in `schedule_live` mode and are **step-indexed**. Whether the
`oracle_escalation` arm replays the source prefix or runs free determines what "oracle" means
and therefore what the headroom number bounds. Print the answer as a line in the report
(`oracle semantics: replays source prefix | runs free`) with a `path:line` citation, and refuse
to emit the headroom row if you cannot establish it. Do not infer it from the arm's name.

### Refusals

The script must **refuse to print a headline** if any arm has fewer than 114 rows, and must say
which arm and how many. A partial arm silently averaged is how a previous result in this
campaign went wrong.

### Dry run

Exercise it on what exists today, inside a PBS job:
- the two completed free arms from `hj8_frontier_free_20260919` (executor_alone, sft_plan)
- the 2026-09-19 live smoke trees (`hj8_*_20260919livesmoke_smoke`) — these are 3-row **crashed**
  trees kept only as malformed input; the script must refuse them cleanly rather than crash or
  emit numbers. That is the test.

Read result trees **read-only**. Never write anything under `/scratch/.../results/`.

## Tests

Unit tests with small synthetic arm directories: pairing, the bootstrap agreeing with
`j10_report.py`'s on identical input, the `< 114 rows` refusal, a degenerate gate (zero
escalations) producing a labelled row rather than a division error, and the F1 boolean on
constructed numbers that sit just inside and just outside each of its two conditions.

## Constraints (these are not optional)

- `aquarius01` is a **login node — steering only**. Never run python, pip, tar, rsync or any
  multi-minute command there. Every execution goes in a PBS job: `hpc <cmd>` or
  `hpc bash -c '...'`. Pin BLAS to 1 thread. Put `timeout` on every command.
- Do **not** commit and do **not** run git. The orchestrator reads the diff and commits.
- Do not touch `test_normal` or `test_challenge` data — this is a dev-split script only.
- Do not modify anything under `/scratch/.../results/`, ever. Never write under
  `hj6_branches_train_20260917`.
- Out of scope, owned by other workers running right now: `scripts/pbs/*`, `src/sidekick/*`,
  `scripts/setup/branch_counterfactual.py`, `docs/*`, `campaign/RUNS.md`, `README.md`.
  `j10_report.py` may only be touched to extract a shared helper — if you do, say so explicitly
  and keep its behaviour identical.
- The full suite must still pass: baseline **413 passed, 1 skipped**, run inside a job with
  `-m pytest tests -q --import-mode=importlib` (the import mode flag is required or collection
  fails). Report the exact final line.

## Return contract

**Create the file within your first three actions, then iterate with tests.** Write
`campaign/workers/STATUS_R3.md` after every milestone — if the session dies it is the only
record, and it must say how to resume. Tag every factual claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`.

Final report, ten lines or fewer: the file, the oracle-semantics answer with its citation, what
the dry run printed on the free arms, confirmation that the crashed smoke trees were refused,
the suite's final line, and anything you could not do.

---

## Addendum — 2026-09-20, second attempt

A first attempt at this unit (Cline, `z-ai/glm-5.3-flash`) died with
`Upstream idle timeout exceeded` after gathering all its context and immediately before
writing anything. It produced **zero files**: no analysis script, no tests, no STATUS file.
Nothing from it survives, so start clean; there is nothing to resume.

The operational lesson, which is now a requirement of this unit:

- **Write the analysis file to disk within your first three actions**, even as a skeleton with
  the argument parser and stub functions. Then iterate on it with tests. A worker that spends
  its whole session planning and dies before its first write leaves nothing behind.
- Write `campaign/workers/STATUS_R3.md` immediately after that first file, then update it after
  every milestone. It is the only thing that survives a kill.
