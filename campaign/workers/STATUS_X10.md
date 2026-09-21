# STATUS_X10 — context-matched advise control

State: **done**. No commit, no `qsub`, no GPU, no eval, no `/scratch/.../results` writes.

## Knob

`SystemPolicy.correct_context_lines: int | None = 8`. `None` = whole transcript; a non-negative int = that many trailing lines. Applied **only** on the forced-review advise path [OBSERVED src/sidekick/systems/loop.py:70, :807-815]. Takeover still joins the full transcript [OBSERVED :773]. Executor-ASK still hardcodes `transcript[-8:] + ASK` [OBSERVED :949] (was :939; inserts shifted the line, code unchanged). Default 8 reproduces existing advise arms.

YAML `correct_context` is parsed in `parse_correct_context`: `full`/`all` → `None`, non-negative int → itself, else `ValueError` [OBSERVED src/sidekick/runner.py:238-248]. Forwarded via `system_kwargs` for the same six systems as `takeover` [OBSERVED :265-271]. `ConfigurableSystem` must overlay `None` or `full` would silently stay 8 [OBSERVED src/sidekick/systems/loop.py:211].

SEAM_CONTRACT lists `takeover`/`handoff_allowed` only [OBSERVED campaign/briefs/SEAM_CONTRACT.md:197-198]. Recorded; implemented the brief anyway.

## Config diff

`timeout 15 diff configs/hj12_takeover_fixed_k_10.yaml configs/hj12_advise_fixed_k_10_fullctx.yaml` [OBSERVED]:

```
5,6c5,6
< campaign_id: hj12_takeover_fixed_k_10_20260923
< takeover: true
---
> campaign_id: hj12_advise_fixed_k_10_fullctx_20260923
> correct_context: full
```

## Amendment heading

`## Amendment 2026-09-21 — C1 context-matched control` [OBSERVED docs/prereg_hj12_dev_20260922.md:234]. Registered G2 text not rewritten.

## Tests (`tests/unit/test_correct_context.py`)

`test_default_forced_review_sends_last_eight_lines`, `test_full_context_forced_review_sends_whole_transcript`, `test_ask_path_ignores_correct_context_lines`, `test_unrecognised_correct_context_raises`, `test_system_kwargs_forwards_correct_context_with_takeover_systems`, `test_none_overlay_survives_configurable_system_default`, `test_hj12_fullctx_differs_from_takeover_only_in_channel`.

## `hj12_live.pbs`

Present. Added `hj12_advise_fixed_k_10_fullctx` to `LIVE_ARMS` after takeover k=10 [OBSERVED scripts/pbs/hj12_live.pbs:147]. `MAX_PLANNER_CALLS` default 3500 → **3780** (+~280) [OBSERVED :68]. `timeout 15 bash -n`: empty stdout, `bash_n_exit=0`.

## Suite [OBSERVED hpc 25607467.aqua]

```
492 passed, 1 skipped, 1 warning in 30.00s
```

Floor 484 not breached. Seven new tests vs X9's 485 [INFERRED].
