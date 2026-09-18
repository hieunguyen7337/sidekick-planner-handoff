# STATUS A-8 — clean-counterfactual branch mode (U-CF)

**unit:** A8 / U-CF
**state:** done (2026-09-19)
**ownership:** `scripts/setup/branch_counterfactual.py`, `src/sidekick/systems/loop.py`,
tests under `tests/unit/` (additions in `tests/unit/test_branch_counterfactual.py`),
this file. Did not touch `configs/`, `scripts/pbs/`, `scripts/setup/verify_configs.py`,
`scripts/setup/state_probe.py`, `scripts/setup/hj1_gate.py`. Did not commit.
Zero planner calls. No GPU job. No `/scratch/.../results/` writes.

## Design (locked)

- New `EpisodePrefix.skip_next_scheduled_review: bool = False` (appended after
  `local_eval_step`, default False). Combined with existing `skip_review_at_start`,
  default path is today's behaviour. `tests/unit/test_branch_counterfactual.py:335`
  still has `skip_review_at_start=True` and does not set the new field.
- `--untreated-mode {schedule_live, suppress_next}`; default `schedule_live`.
- `suppress_next` sets `skip_next_scheduled_review=True` on the **untreated**
  arm only. Treated arm unchanged in both modes.
- "Next scheduled review" = first step `t > s` at which `t % review_every_k == 0`,
  not `s + review_every_k`. If that tick is never reached, nothing extra is skipped.
- Router/oracle triggers are **not** suppressed: `skip_scheduled` only gates the
  `review_every_k` branch. Reason: they are not scheduled reviews
  [OBSERVED src/sidekick/systems/loop.py:715-724]. Branch runs set
  `planner_drives=False` and `allow_executor_ask=False`
  [OBSERVED scripts/setup/branch_counterfactual.py:1061-1064], so the scheduled
  tick is the live path in practice.

## Milestones

- [x] M0 brief read; design locked.
- [x] M1 `EpisodePrefix.skip_next_scheduled_review` + loop skip logic.
- [x] M2 `--untreated-mode`, mode-dependent `branch_config`, untreated-arm wiring.
- [x] M3 unit tests (synthetic/mock only).
- [x] M4 pytest via `hpc`: `389 passed, 1 skipped, 1 warning in 23.80s`
      (job 25452336.aqua). Baseline was 365 passed, 1 skipped; never fewer,
      never a failure.
- [x] M5 return contract below.

## pytest (verbatim)

Job `25452336.aqua` on `cpu1n040`, interpreter
`/scratch/n12194778/sidekick/env/bin/python`. Full log:
`/home/n12194778/.hpc-spool/20260919-012712-2237768.out`.

```
.....................................s.................................. [ 18%]
........................................................................ [ 36%]
........................................................................ [ 55%]
........................................................................ [ 73%]
........................................................................ [ 92%]
..............................                                           [100%]
=============================== warnings summary ===============================
tests/unit/test_feature_verifier.py::test_failed_join_is_dropped_not_fitted
  /scratch/n12194778/sidekick/env/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
389 passed, 1 skipped, 1 warning in 23.80s
```

## Return contract

### New prefix field

`EpisodePrefix.skip_next_scheduled_review: bool = False`
[OBSERVED src/sidekick/systems/loop.py:95].

Default False is backward compatible because the extra skip is a no-op unless
the field is True; existing constructors (including
`tests/unit/test_branch_counterfactual.py:335`) omit it and keep skip-at-s-only
behaviour. Field is appended so positional `local_eval_step` still binds.

### Router / oracle

**Not suppressed.** `skip_scheduled` only wraps the `review_every_k` trigger.
Router `should_escalate` and `step in policy.oracle_steps` still set
`force_review` [OBSERVED src/sidekick/systems/loop.py:715-724]. Locked by
`test_suppress_next_does_not_suppress_oracle_review`. Why: the brief defines
those as not scheduled reviews. A coincident oracle at the suppressed tick
would still fire; that is intentional.

### `branch_config` under each mode

Shared keys (unchanged except the two mode-dependent strings plus `untreated_mode`):
`temperature=0.7`, `conditions=["treated","untreated"]`, `allow_executor_ask=False`,
`planner_drives=False`, `sampling_seed="branch_seed passed to executor.complete(seed=...)"`,
`replay_prefix_k` and `max_steps_rule` as before.

**`schedule_live` (default, frozen estimand)** [OBSERVED
scripts/setup/branch_counterfactual.py:72-80, 786-793]:

```
untreated_mode: "schedule_live"
review_every_k: "live on the original schedule after the focal step; the scheduled tick at s is skipped and either injected (treated) or omitted (untreated)"
estimand: "Q(policy with intervention i present) - Q(policy with intervention i omitted); later reviews live"
```

**`suppress_next`** [OBSERVED scripts/setup/branch_counterfactual.py:81-91, 786-793]:

```
untreated_mode: "suppress_next"
review_every_k: "treated: live on the original schedule after the focal step; the scheduled tick at s is skipped and injected. untreated: the scheduled tick at s and the next scheduled tick the schedule would actually have fired after s are both omitted; later ticks after that stay live"
estimand: "Q(policy with intervention i present) - Q(policy with intervention i omitted and the next scheduled review after s also suppressed); later reviews after that stay live"
```

### Diff (files this unit changed; no commit)

- `src/sidekick/systems/loop.py` — `skip_next_scheduled_review`;
  `next_scheduled_review_step` helper; scheduled-only skip of that tick.
- `scripts/setup/branch_counterfactual.py` — `--untreated-mode`, plumbing
  through jobs/rows/manifest, untreated-arm prefix flag, mode-dependent
  `branch_config` strings. `next_scheduled_review_step` imported from loop.
- `tests/unit/test_branch_counterfactual.py` — A8 tests; existing
  `test_untreated_omits_only_focal_later_review_fires` untouched.
- `campaign/workers/STATUS_A_8.md` — this file.

## Resume

Nothing pending. Do not submit a rollout. Do not commit.
