# STATUS X44 — Cost Axes Defect Fixes

## 1. Actual Root Cause of Dollar Defect

[OBSERVED scripts/analysis/j12_cost_axes.py:258-262 (before)] `extract_events_usages` filtered events with `or "input_tokens" in u`. Because every usage dictionary contains `input_tokens`, this matched all local executor events (`actor == "executor"`) as well as hosted planner calls, pricing local executor tokens at the hosted `gpt-5.6-luna` rate ($0.20/1M) [OBSERVED scripts/analysis/j12_cost_axes.py:206-210]. In arms with 0 or few hosted calls (`executor_alone`, `plan_only`), the executor executed many steps with large prompt contexts, accumulating large spurious USD totals. In heavy-planner arms (`ceiling_cap25`), fewer executor steps occurred, causing dollar cost to decrease as planner calls increased [INFERRED].

**Before hunk** [OBSERVED scripts/analysis/j12_cost_axes.py:258-262]:
```python
    for ev in raw_events[last_start:]:
        u = ev.get("usage")
        if isinstance(u, dict) and (
            ev.get("actor") == "planner"
            or ev.get("event_type") in ("plan", "intervention", "action_review")
            or "input_tokens" in u
        ):
            usages.append(u)
```

**After hunk** [OBSERVED scripts/analysis/j12_cost_axes.py:258-261]:
```python
    for ev in raw_events[last_start:]:
        u = ev.get("usage")
        if isinstance(u, dict) and ev.get("actor") == "planner":
            usages.append(u)
```

In addition, zero-hosted-call arms now emit measured `0.0` for `noncached_tokens_per_episode` and `usd_per_episode` [OBSERVED scripts/analysis/j12_cost_axes.py:348-353, 412-416].

## 2. Construction Mirrored for Label Keying

Mirrored [OBSERVED scripts/analysis/j8_frontier.py:2809]:
`"arms": {label: _public_arm(arm) for label, arm in arms.items()}`.
In `scripts/analysis/j12_cost_axes.py:686` [OBSERVED], the report arms block is now keyed by arm label:
`"arms": {a["label"]: a for a in arm_summaries}`.

## 3. What Remains `null` and Why

- `noncached_tokens_per_episode` and `usd_per_episode` remain `null` only when planner usage/calls are completely unrecorded (missing ledger totals and missing event logs), distinguishing unmeasurable data from measured zero-call arms [OBSERVED scripts/analysis/j12_cost_axes.py:348-353, 417-418].
- `local_gpu_usd_per_episode` remains `null` when wall time / GPU duration is unrecorded [OBSERVED scripts/analysis/j12_cost_axes.py:420-431].

## 4. Tests Added

Added in [OBSERVED tests/unit/test_j12_cost_axes.py:151-320]:
1. `test_zero_hosted_call_arm_costs_zero_usd`
2. `test_usd_is_monotone_in_tokens_at_a_fixed_mix`
3. `test_usd_matches_a_hand_computed_total`
4. `test_arms_block_is_keyed_by_arm_label`
5. `test_ordering_flips_are_empty_when_axes_agree`
