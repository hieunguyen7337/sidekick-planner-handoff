# STATUS X33e

## 1. Actor Filter Before/After
Before `[OBSERVED scripts/analysis/j13_mechanism.py:619]` (pre-fix):
```python
elif e.event_type == "observation" and e.actor == "executor":
```
After `[OBSERVED scripts/analysis/j13_mechanism.py:622]`:
```python
elif e.event_type == "observation" and e.actor == "environment":
```

## 2. Action Counter Ordering Confirmation
In the event loop `[OBSERVED scripts/analysis/j13_mechanism.py:619-630]`:
```python
for e in events:
    if e.event_type == "action" and e.actor == "executor":
        exec_action_count += 1
    elif e.event_type == "observation" and e.actor == "environment":
        ...
        if is_err and first_err_rel < 0 and exec_action_count > 0:
            first_err_rel = exec_action_count
```
The counter `exec_action_count` increments on `action|executor` before the replying `observation|environment` is evaluated, yielding `first_error_rel_step == 1` for an error on the executor's 1st action `[INFERRED]`.

## 3. Directional Guard Before/After
Before `[OBSERVED scripts/analysis/j13_mechanism.py:359-364]` (pre-fix):
```python
divergence_rate = divergence_count / n_total
if divergence_rate > 0.05:
    raise SystemExit(f"Fatal: arm {arm_name!r} divergence count ...")
```
After `[OBSERVED scripts/analysis/j13_mechanism.py:359-363]`:
```python
if handoff_true_zero_calls:
    raise SystemExit(
        f"Fatal: arm {arm_name!r} has {len(handoff_true_zero_calls)}/{n_total} episodes "
        f"with handoff_occurred is True but executor n_calls == 0: {handoff_true_zero_calls}"
    )
```

## 4. New Report Field
`post_complete_executor_actions` records episodes with `handoff_occurred is False` and `n_calls > 0` `[INFERRED]`. Written to:
- `m2_compounding_error[arm]` `[OBSERVED scripts/analysis/j13_mechanism.py:659]`
- `m3_prefix_exhausted[arm]` `[OBSERVED scripts/analysis/j13_mechanism.py:732]`
- Markdown table in `generate_markdown_report` with explanatory footnote `[OBSERVED scripts/analysis/j13_mechanism.py:959-969]`.

## 5. Tests
Defined in `tests/unit/test_j13_mechanism.py`:
- `test_m2_counts_errors_from_environment_observations` `[OBSERVED tests/unit/test_j13_mechanism.py:171]`
- `test_m2_ignores_successful_observations` `[OBSERVED tests/unit/test_j13_mechanism.py:196]`
- `test_m2_first_error_step_is_one_based_on_executor_actions` `[OBSERVED tests/unit/test_j13_mechanism.py:221]`
- `test_handoff_true_with_zero_executor_calls_is_fatal` `[OBSERVED tests/unit/test_j13_mechanism.py:379]`
- `test_post_complete_actions_are_recorded_not_fatal` `[OBSERVED tests/unit/test_j13_mechanism.py:399]`
- `test_empty_handoff_population_is_fatal` `[OBSERVED tests/unit/test_j13_mechanism.py:270]`
- `test_handoff_flag_is_read_from_report_event` `[OBSERVED tests/unit/test_j13_mechanism.py:220]`
