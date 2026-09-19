# STATUS A17 (U-CF2) — symmetric `suppress_next`

**unit:** A17 / U-CF2
**state:** done (2026-09-19)
**ownership:** `scripts/setup/branch_counterfactual.py`, `src/sidekick/systems/loop.py`,
`tests/unit/test_branch_counterfactual.py`, this file,
`campaign/workers/scratch_A17/residual_n_later.py` (read-only residual count).
Did not touch `configs/`, `scripts/pbs/`, `scripts/analysis/`, `docs/prereg_b1_pilot.md`,
`campaign/RUNS.md`. Did not commit. Zero planner calls. No GPU job. No
`/scratch/.../results/` writes.

## Design (as specified)

Redefined `suppress_next` in place. Both arms set `skip_next_scheduled_review=True`.
`schedule_live` strings and skip-at-s-only default are frozen.

I do **not** believe the symmetric design is wrong. The previous untreated-only skip
confounded `i` with an extra treated-arm review; suppressing `t` in both arms is the
contrast the estimand names. Later ticks after `t` stay live in both — that is
intended, and it is why `n_later = 0` is still not true by construction.

## Code

`skip_next` is now mode-only, not condition-gated
[OBSERVED scripts/setup/branch_counterfactual.py:1022]:

```
skip_next = untreated_mode == UNTREATED_MODE_SUPPRESS_NEXT
```

Loop skip logic unchanged: the flag is already arm-agnostic
[OBSERVED src/sidekick/systems/loop.py:709-714].

## Provenance strings (verbatim)

Frozen `schedule_live` (untouched):

```
_REVIEW_EVERY_K_SCHEDULE_LIVE = (
    "live on the original schedule after the focal step; "
    "the scheduled tick at s is skipped and either injected "
    "(treated) or omitted (untreated)"
)
_ESTIMAND_SCHEDULE_LIVE = (
    "Q(policy with intervention i present) - "
    "Q(policy with intervention i omitted); later reviews live"
)
```

[OBSERVED scripts/setup/branch_counterfactual.py:73-80]

Corrected `suppress_next`:

```
_REVIEW_EVERY_K_SUPPRESS_NEXT = (
    "both arms skip the scheduled tick at s and the next scheduled tick "
    "the schedule would actually have fired after s; treated injects at s, "
    "untreated omits at s; later ticks after that stay live in both arms"
)
_ESTIMAND_SUPPRESS_NEXT = (
    "Q(policy with intervention i present) - "
    "Q(policy with intervention i omitted); "
    "the next scheduled review after s is suppressed in both arms; "
    "later reviews after that stay live"
)
```

[OBSERVED scripts/setup/branch_counterfactual.py:82-92]

## pytest (verbatim)

PBS **25465050.aqua**, interpreter `/scratch/n12194778/sidekick/env/bin/python`.
Full log: `/home/n12194778/.hpc-spool/20260919-063316-2756014.out`.

```
.....................................s.................................. [ 17%]
........................................................................ [ 35%]
........................................................................ [ 52%]
........................................................................ [ 70%]
........................................................................ [ 88%]
.................................................                        [100%]
=============================== warnings summary ===============================
tests/unit/test_feature_verifier.py::test_failed_join_is_dropped_not_fitted
  /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
408 passed, 1 skipped, 1 warning in 40.13s
```

[OBSERVED job 25465050.aqua]. Baseline was 406 passed, 1 skipped; this unit added 2 tests
(`test_suppress_next_treated_arm_skips_tick_t`,
`test_suppress_next_arms_differ_only_by_injection_at_s`). Never fewer, never a failure.

## Treated-arm skip at `t` (quoted)

[OBSERVED tests/unit/test_branch_counterfactual.py:1309-1334]

```
def test_suppress_next_treated_arm_skips_tick_t(tmp_path):
    """Treated arm must skip t under suppress_next; that was the asymmetric bug."""
    start_step = 7
    k = 5
    t = bc.next_scheduled_review_step(start_step, k)
    assert t == 10
    _, planner, events, _ = _focal_branch(
        tmp_path,
        condition="treated",
        skip_next_scheduled_review=True,
        start_step=start_step,
        review_every_k=k,
        max_steps=16,
        executor=RecordingExecutor(script=[NOOP_CODE] * 20),
        run_id="treated_skip_t",
    )
    live_steps = [e.step for e in _live_reviews(events)]
    assert t not in live_steps
    ...
    assert 15 in live_steps
```

`test_treated_identical_between_untreated_modes` still hardcodes
`skip_next_scheduled_review=False` on treated and still passes: that is the
`schedule_live` treated path, left untouched.
`test_run_branches_records_untreated_mode` no longer asserts treated `n_later`
equal across modes; that assertion was the bug. It now asserts later-review
counts match across arms *within* each mode, and that treated `n_later` is
strictly smaller under `suppress_next` than under `schedule_live`.

## Residual `n_later` under the fixed mode

From frozen B1 points (`campaign/workers/scratch_A16/b1_pilot_points.txt`, n=200,
all present in J6 train last-row-wins) and J6 untreated replicates
[OBSERVED job 25465050.aqua residual script stdout].

**Typical residual is 0 later ticks**, if episode length stays as observed in J6.

- Point-level median of `max(0, n_later − 1)` on the frozen 200:
  **median 0.0**, mean 0.235, min 0, max 4; buckets 0: **161/200**, (0,1): 17, 1: 7, 2: 3, 3+: 12.
- Same quantity at replicate level (800 untreated rows): median 0.0, mean 0.47125;
  607/800 have residual 0.
- Schedule remainder using observed `branch_steps` as horizon: point-level median **0.0**,
  mean 0.3225 (almost the same as the `n_later − 1` proxy).

**If the branch ran to `max_steps=40`**, the live schedule after `t` still has a
median of **5** remaining ticks (mean 4.51, 174/200 points have 3+). That is the
policy remainder, not what J6 actually lived long enough to receive.

J6 itself (contaminated estimand) already has point-level median `n_later` = 0.5
on this sample (76/200 are 0). Suppressing `t` does not make `n_later = 0` by
construction: ticks at `t+k, t+2k, …` stay live in both arms. Design not changed
to chase `n_later = 0`.

Caveat [INFERRED]: if skipping `t` changes when the episode ends, J6 `n_later − 1`
is only a length-held-fixed proxy, not a post-intervention observation. No
`suppress_next` data exists yet.

## Diff (no git; changed regions)

- `scripts/setup/branch_counterfactual.py`: module docstring 11-13; provenance
  82-92; `skip_next` at 1022; CLI help 1447.
- `src/sidekick/systems/loop.py`: `EpisodePrefix` docstring 78-82.
- `tests/unit/test_branch_counterfactual.py`: two new tests; exact-match
  `suppress_next` strings; `test_run_branches_records_untreated_mode` later-count
  assertions.
