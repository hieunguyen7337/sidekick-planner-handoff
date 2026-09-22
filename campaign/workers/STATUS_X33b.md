# Status X33b — Mechanism Finish

All five defects in `scripts/analysis/j13_mechanism.py` fixed and unit test suite created in `tests/unit/test_j13_mechanism.py`. No tests or scripts were executed on the login node [OBSERVED AGENTS.md:9].

## Five Defects Fixed

1. **Population Definition** [OBSERVED scripts/analysis/j13_mechanism.py:307,404]
   - *Before*: Checked `n_calls == 0` from `totals.per_actor.executor.n_calls`.
   - *After*: Uses `handoff_occurred = (res.get("handoff_occurred") is True)` [OBSERVED src/sidekick/prefix_source.py:150,184]; logs divergence with `(n_calls > 0)` in `divergence_count` and `divergence_keys`.

2. **Hard-coded Arm Lists** [OBSERVED scripts/analysis/j13_mechanism.py:608,616]
   - *Before*: Fixed lists `post_guard_m = [2, 4, 6, 7, 8, 9, 10]` and `pre_guard_m = [2..11]`.
   - *After*: `discover_arms()` scans `m ∈ 2..11` for `hj12_prefix_m{m}_20260923/prefix_handoff` (tailored) or `hj13_prefix_zs_m{m}_20260923/prefix_handoff` (zeroshot), including arms iff exactly 114 `result.json` exist.

3. **Arm-independent Key Set Thresholds** [OBSERVED scripts/analysis/j13_mechanism.py:461,468,546]
   - *Before*: Hard-coded thresholds 9 and 10 in `source_gt9`, `source_gt10`, and decompositions.
   - *After*: Thresholds derived from the largest and second-largest discovered `m` values (`max_m_1`, `max_m_2`).

4. **CLI & Output Guards** [OBSERVED scripts/analysis/j13_mechanism.py:15,47-50]
   - *Before*: Unused `argparse`, fixed literal paths, no guards.
   - *After*: CLI with `--results-dir`, `--source-dir`, `--out-report`, `--out-md`, `--n-boot` (10000), `--seed` (20260915 matching `hj1_gate.py:59`), `--receiver {tailored,zeroshot}`. Added `validate_output_path()` refusing writes under `/scratch/n12194778/sidekick/results/` or containing `test_normal`/`test_challenge`.

5. **Unit Tests** [OBSERVED campaign/workers/brief_X33b_mechanism_finish.md:42]
   - *Before*: No unit tests for `j13_mechanism.py`.
   - *After*: Created `tests/unit/test_j13_mechanism.py` with 7 isolated synthetic tests.

## Discovery Rule & Derived Thresholds
- **Discovery Rule**: For `m ∈ 2..11`, include arm path iff `len(rglob("result.json")) == 114`; report excluded arms with counts [INFERRED].
- **Derived Thresholds**: Largest (`max_m_1`) and second-largest (`max_m_2`) discovered `m` determine `source_gt{t}` and decomposition targets [INFERRED].

## CLI Arguments
`--results-dir`, `--source-dir`, `--out-report`, `--out-md`, `--n-boot` (10000), `--seed` (20260915), `--receiver` (`tailored` | `zeroshot`).

## Test Names in `tests/unit/test_j13_mechanism.py`
1. `test_load_source_planner_prefers_result_json_over_directory_names`
2. `test_m1_api_novelty_cumulative_shares`
3. `test_m2_compounding_error_and_handoff_occurred_filter`
4. `test_m3_handoff_population_and_divergence_diagnostic`
5. `test_arm_discovery_requires_exact_114_results`
6. `test_validate_output_path_refuses_forbidden_locations`
7. `test_bootstrap_is_deterministic_under_default_seed`

## Unrun HPC Execution Commands

```bash
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/analysis/j13_mechanism.py --receiver tailored --out-report campaign/results/hj13_mechanism_tailored_20260923.report.json --out-md campaign/results/hj13_mechanism_tailored_20260923.md
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 python scripts/analysis/j13_mechanism.py --receiver zeroshot --out-report campaign/results/hj13_mechanism_zeroshot_20260923.report.json --out-md campaign/results/hj13_mechanism_zeroshot_20260923.md
```
