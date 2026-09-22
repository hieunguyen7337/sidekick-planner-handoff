# Runbook — hosted tier B, after the quota window reopens (2026-09-22 18:46)

Tier B was approved by the user at ~5,000 hosted planner calls. Everything below runs
`gpt-5.6-luna` at `reasoning_effort: medium` on the **ChatGPT plan subscription**, so there is no
per-token billing — the binding constraint is **plan quota**, and quota is *not observable from
inside a batch job*. That is exactly how the first ceiling attempt was contaminated.

## What went wrong last time, so it is not repeated

`hj13_planner_alone_cap81_20260923` finished as **70 clean / 17 limit / 27 crash**, every crash
`codex exec exited 1`, concurrent with an interactive quota error. A crashed episode still writes a
`result.json`, so a plain resume skips it forever — hence `--purge-broken`, already wired into
`scripts/pbs/hj1b_planner_alone.pbs:67-68`.

**Do not analyse that campaign until the 27 are refilled.** It is not a valid ceiling.

⚠ **Do not run hosted arms and Codex/luna workers in the same window.** They draw on the same quota.
While anything below is in flight, do not dispatch a `codex` worker.

## Order of submission — cheapest first, verify before escalating

Submit **one at a time** and check the error-type distribution before submitting the next. The whole
point of the ordering is that a quota exhaustion costs the smallest arm, not the largest.

### Step 1 — refill the ceiling (~27-80 calls). Do this first: every NI claim depends on it.

```
qsub -v CONFIG="/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/configs/hj13_planner_alone_cap81.yaml",CID="hj13_planner_alone_cap81_20260923" scripts/pbs/hj1b_planner_alone.pbs
```

CPU-only queue (`planner_drives=True`, so no executor and no vLLM). The script purges the 27 broken
runs and re-runs only those; the 87 good ones are skipped.

**Gate:** afterwards the campaign must be **0 crash**. Check with:

```
find /scratch/n12194778/sidekick/results/hj13_planner_alone_cap81_20260923/planner_alone -name result.json -exec cat {} + | jq -s -r 'group_by(.error_type // "none") | map("\(.[0].error_type // "none")=\(length)") | join("  ")'
```

If crashes remain, quota is still short — **stop and wait**, do not submit anything below.

### Step 2 — H1, the registered full-context advice control (~280 calls)

Cheapest arm with the highest yield: it removes reviewer attack #5 (the advice reviewer saw only the
last 8 transcript lines while the acting planner sees everything). Until it runs, "advice is flat at
any price" may only be "starved advice is flat".

```
qsub -v ARMS="hj12_advise_fixed_k_10_fullctx",DATE=20260923 scripts/pbs/hj12_live.pbs
```

### Step 3 — H4, the registered matched-trigger channel pair (~550 calls)

```
qsub -v ARMS="hj12_takeover_fixed_k_10",DATE=20260923 scripts/pbs/hj12_live.pbs
```

### Step 4 — H3, the deployable live handoff (~900-1,300 calls)

```
qsub -v ARMS="hj12_planner_handoff",DATE=20260923 scripts/pbs/hj12_live.pbs
```

### Step 5 — H2, advice priced at m11's budget (~1,600 calls). Largest, so last.

This is the arm that turns "channel, not budget" from a slogan into a result: it prices the advice
channel at the budget where the action channel actually rises.

```
qsub -v ARMS="hj13_advise_fixed_k_1_fullctx",DATE=20260923 scripts/pbs/hj12_live.pbs
```

## After each arm

1. Error types must be `limit` and `none` only — **any `crash` means quota trouble**; stop.
2. 114 episodes (57 tasks x 2 seeds) per arm.
3. Re-run the unified frontier so the new arm enters the report with both task- and scenario-clustered
   intervals.

## Standing constraints that apply to every command above

- Submit from the **login node**; never from a worker. `scripts/pbs/hj1b_planner_alone.pbs:14` says so
  in its own header.
- Planner is always `gpt-5.6-luna`. Never `gpt-5.6-sol` or `gpt-5.6-terra`. `hj12_live.pbs` verifies
  `model:gpt-5.6-luna` before any episode; do not weaken that check.
- Dev split only. **No `test_normal` or `test_challenge`** — J10 needs explicit user authorisation per
  the frozen J9 freeze §8.1, which has not been given.
- Never write under `/scratch/n12194778/sidekick/results/` by hand; `--purge-broken` is the harness
  repairing its own campaign and is the only sanctioned path.

## Addendum 2026-09-22 17:05 — Step 1 is now decisive, not merely tidy

Since this runbook was written, the ceiling sensitivity was measured and it **breaks
non-inferiority**. Against a reference restricted to the 102 episodes where the capped planner did
not hit its 25-call cap, `prefix_m11 − planner_alone` is **−5.92 pp** [−10.16, −1.98] task-clustered
and [−9.80, −2.57] scenario-clustered — a fail, where the same contrast against the reference as run
is **+0.23 pp** and holds (CEIL-01, CEIL-02 in `docs/claims_ledger.md`).

That exclusion is not neutral either: dropping the 12 cap-censored episodes removes the tasks the
planner found hardest, which are plausibly where the prefix arms looked best, so −5.92 pp is
pessimistic for the arm and optimistic for the ceiling.

So dev non-inferiority is currently **unresolved, bracketed between +0.23 pp and −5.92 pp**, and the
cap-81 ceiling re-run is the only thing that collapses the bracket. Nothing downstream — the headline
NI claim, the chord results, the frontier figure — can be written until it does. Run Step 1 first and
do not skip it because it is small.

**Worker scheduling for the window:** `agy` (Gemini) and `cursor-agent` (Grok) do **not** touch the
luna quota and may keep running. Only `codex`/`gpt-5.6-luna` workers conflict, and those must stay
parked until every hosted arm above has finished.
