# STATUS_X33f

## Task 1: Broken Test Assertion
- **Before:** `assert m4["first_error_rel_step_dist"]["min"] is None` raised `TypeError` when `quartiles()` returned `None` [OBSERVED scripts/analysis/j13_mechanism.py:75-78].
- **After:** `assert m4["first_error_rel_step_dist"] is None` [OBSERVED tests/unit/test_j13_mechanism.py:218].
- **Other sites:** Scanned `tests/unit/test_j13_mechanism.py` [OBSERVED tests/unit/test_j13_mechanism.py:1-714]; no other `None`-subscript sites exist (other `first_error_rel_step_dist` accesses occur in non-empty error scenarios).

## Task 2: Matched Decomposition Pairs
- **CLI Option & Parser:** Added `--decompose-pairs` in `parse_args` [OBSERVED scripts/analysis/j13_mechanism.py:1093-1097] and `parse_decompose_pairs` [OBSERVED scripts/analysis/j13_mechanism.py:94-130] supporting format `'m6:m9,m6:m11'`.
- **Fatal Branch:** `measure_m3_prefix_exhausted` validates requested base/target depths against `available_m`, raising `SystemExit` if any depth is missing [OBSERVED scripts/analysis/j13_mechanism.py:894-905].
- **Decomposition:** Computes and emits exactly the requested pair keys `m<base>_to_m<target>` [OBSERVED scripts/analysis/j13_mechanism.py:906-957].

## Tests Added
In `tests/unit/test_j13_mechanism.py` [OBSERVED tests/unit/test_j13_mechanism.py:636-714]:
1. `test_decompose_pairs_emits_exactly_the_requested_pairs` [OBSERVED tests/unit/test_j13_mechanism.py:636-666]
2. `test_decompose_pairs_missing_depth_is_fatal` [OBSERVED tests/unit/test_j13_mechanism.py:668-688]
3. `test_decompose_pairs_default_is_unchanged` [OBSERVED tests/unit/test_j13_mechanism.py:690-713]
