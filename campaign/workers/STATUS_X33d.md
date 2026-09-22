# STATUS X33d — Mechanism Handoff Flag Path Fix

Mirrored `events.jsonl` payload parsing from `scripts/analysis/j8_frontier.py:747-838` (`_handoff_facts_from_events_text`, `attach_handoff_fields`) [OBSERVED scripts/analysis/j8_frontier.py:747-838].

## Helper Before/After Hunk
```diff
- handoff_occurred = (res.get("handoff_occurred") is True)
+ handoff_facts = extract_handoff_facts(rec)
+ handoff_occurred = (handoff_facts["handoff_occurred"] is True)
```
[OBSERVED scripts/analysis/j13_mechanism.py:598-599,702-703]

Added shared helpers `load_handoff_flags` and `extract_handoff_facts` [OBSERVED scripts/analysis/j13_mechanism.py:238-309].

## Fatal-Check Hunk
```python
if not facts["has_report"] or facts["handoff_occurred"] is None:
    raise SystemExit(f"Fatal: arm {arm_name!r} episode task_id={task_id!r} seed={seed} is missing a report event in events.jsonl")
if n_handoff == 0 and n_exec_calls_gt_0 > 0:
    raise SystemExit(f"Fatal: arm {arm_name!r} has 0 handoff episodes (handoff_occurred is True) while {n_exec_calls_gt_0}/{n_total} episodes have executor n_calls > 0")
if (divergence_count / n_total) > 0.05:
    raise SystemExit(f"Fatal: arm {arm_name!r} divergence count {divergence_count}/{n_total} ({(divergence_count / n_total):.2%}) exceeds 5% threshold")
```
[OBSERVED scripts/analysis/j13_mechanism.py:333-364]

## Test Names
- `test_handoff_flag_is_read_from_report_event` [OBSERVED tests/unit/test_j13_mechanism.py:220]
- `test_empty_handoff_population_is_fatal` [OBSERVED tests/unit/test_j13_mechanism.py:269]
- `test_divergence_above_threshold_is_fatal` [OBSERVED tests/unit/test_j13_mechanism.py:299]
- `test_m2_compounding_error_and_handoff_occurred_filter` [OBSERVED tests/unit/test_j13_mechanism.py:110]
- `test_m3_handoff_population_and_divergence_diagnostic` [OBSERVED tests/unit/test_j13_mechanism.py:171]

## HPC Run Commands
```bash
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'python scripts/analysis/j13_mechanism.py --receiver tailored --out-report campaign/results/hj13_mechanism_tailored_20260923b.report.json --out-md campaign/results/hj13_mechanism_tailored_20260923b.md'
```
[INFERRED from AGENTS.md:10 and scripts/analysis/j13_mechanism.py:917-958]

```bash
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'python scripts/analysis/j13_mechanism.py --receiver zeroshot --out-report campaign/results/hj13_mechanism_zeroshot_20260923b.report.json --out-md campaign/results/hj13_mechanism_zeroshot_20260923b.md'
```
[INFERRED from AGENTS.md:10 and scripts/analysis/j13_mechanism.py:917-958]
