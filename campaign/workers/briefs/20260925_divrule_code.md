# Brief: report code for the replay-divergence rule (DIVRULE, 2026-09-25)

Worktree (absolute, the only cwd): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`
IGNORE `.claude/worktrees/` (other worktrees) and `.git/`.

## Goal

Implement, in the three held-out report scripts, the pre-data rule written in these three drafts (read them
first; they are the specification):
- `/home/n12194778/.claude/jobs/91578989/tmp/a1_amendment5_draft.md` (J10 A1 Amendment 5, §B is the rule),
- `/home/n12194778/.claude/jobs/91578989/tmp/j11_amendment2_draft.md` (J11 Amendment 2, §B),
- `/home/n12194778/.claude/jobs/91578989/tmp/j12_amendment2_draft.md` (J12 Amendment 2).

In one sentence: in a prefix-replay arm, a key whose residual crash carries `payload.reason ==
"replay_divergence"` (a "divergent key") is removed from BOTH arms of every contrast that uses that arm (union
when both arms are replay arms), the contrast is complete if it removes ≤ 16 keys and nothing else crashed, else
incomplete; everything else runs as registered on the remaining pairs; the report lists divergent keys per arm and
pairs per affected contrast.

## Files in scope

- `scripts/analysis/replay_divergence.py` (NEW): the ONE shared definition, used by all three reports:
  `divergent_keys(arm_dir: Path) -> list[tuple[str, int]]` — every `(task_id, seed)` under the arm whose
  `result.json` has `error_type == "crash"` and whose `events.jsonl`, restricted to the LAST attempt (events after
  the last `run_start`; reuse `sidekick.replay._events_of_last_attempt` or the same logic), contains an event with
  `event_type == "error"` and `payload.reason == "replay_divergence"`. Plus `DIVERGENCE_CAP = 16` and a small
  helper that, given two arms' divergent sets and a contrast, returns the excluded key set and the verdict
  (`ok` / `over_cap`). Pure, no pydantic at import if avoidable.
- `scripts/analysis/j10_report.py`: arms 4–7 (`prefix_m9`, `prefix_m11`, `prefix_zs_m9`, `prefix_zs_m11`) are the
  replay arms. Find where A1's arms are loaded (`a1_arm_episodes` :1932, `load_arm_tree` :355), where the crash
  rule makes an arm/contrast incomplete, and where pairs are formed (`a1_paired_series` :2073, `a1_contrast`).
  Hook the rule in so the registered P1–P6, CF, Amendment 1 (§B handoff companions, B3 chord, §D limits),
  Amendment 3 (h*) and the §4.2 key-exclusion sensitivity all see the exclusion. Add a top-level report block
  `a1_am5_divergence` with per-arm divergent keys and counts (including zero) and per affected contrast the
  pair count and excluded keys.
- `scripts/analysis/j11_report.py`: replay arms are the four M^r_m prefix arms (`j11_prefix_{bplus,zs}_m{6,11}`);
  find how it decides completeness (it may reuse lp_report / j10_report pieces) and apply the same rule to
  L2–L5, their h* companions and its planless-key sensitivity. Block `j11_am2_divergence`.
- `scripts/analysis/j12_report.py`: replay arms are its two M^r_6 arms and the J10 arms it reads
  (`prefix_m11`, `prefix_zs_m11`); its pair rule is `j12_apply_pair_rule` (:267) and it imports j10_report's
  loaders. Apply to D1–D4, D3/D4 handoff-only populations, h* companions, key-exclusion sensitivity. Block
  `j12_am2_divergence`.
- Tests: `tests/unit/test_replay_divergence.py` (new) plus additions to `tests/unit/test_j10_report.py`,
  `tests/unit/test_j11_report.py`, `tests/unit/test_j12_report.py` (use each file's existing synthetic-fixture
  helpers, e.g. `write_a1_matrix` in test_j10_report.py).

## Hard constraints

1. **No line that a prereg or test cites may move.** The frozen preregs cite `j10_report.py` lines (A1, its
   Amendments 1–4: e.g. :355, :1932, :2073, :2142, :2440-2484, :3829, :4038-4256) and `tests/unit/test_j10_report.py`
   has line-citation tests (≈:1046-1090) that must still pass. Therefore in `j10_report.py`: put all new
   functions AFTER the last function and BEFORE the final `if __name__ == "__main__":` guard (as the Amendment 4
   block at :4038-4256 did), and hook them in by editing EXISTING lines IN PLACE (same line count), e.g. wrapping
   a call on its existing line, as :3829 wraps `a1_hstar_companions`. Grep `docs/prereg_j1*.md docs/prereg_j10*.md
   tests/unit/test_j1*_report.py` for `j10_report.py:` / `j11_report.py:` / `j12_report.py:` citations before
   editing each file and apply the same rule to j11/j12_report if they are cited.
2. **Behaviour with zero divergent keys is byte-for-byte unchanged** in every existing key and value (only the new
   block is added). Prove it: run each report's existing test file unchanged, and on the committed dev basis that
   `j10_report` can run on (find how `campaign/results/j10_a1_registered_dev_basis_20260924.report.json` was
   produced, e.g. its header keys or `grep -rn dev_basis scripts/ docs/`), regenerate into
   `/home/n12194778/.claude/jobs/91578989/tmp/divrule/` and compare with the committed file (`jq -S` after deleting
   only the new block and any timestamp field; report which fields differed, expected none).
3. A non-divergence crash keeps today's behaviour exactly (incomplete). A divergent key in a NON-replay arm is
   impossible by construction; if one is seen, treat it as an ordinary crash and note it.
4. Tests with hand-computed answers, at least: (a) 0 divergent → unchanged; (b) 1 divergent key in a replay arm →
   excluded from both sides of its contrasts only, other contrasts keep all pairs, contrast complete, pair count
   n−1; (c) two replay arms with different divergent keys → union excluded; (d) 17 divergent keys → incomplete;
   (e) a divergent key plus an ordinary crash → incomplete; (f) last-attempt rule: a `replay_divergence` error in an
   EARLIER attempt followed by a successful last attempt is not divergent; (g) the report block lists keys.
   Mirror (b)–(e) for j11 and j12 at least once each.

## Rules

- HPC: never run python/pytest on the login node. Every run:
  `timeout 3000 hpc bash -c 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && export PYTHONPATH=$PWD/src:$PWD OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 && /scratch/n12194778/sidekick/env/bin/python -m pytest -q <files>'`
  (the worktree guard may refuse a long inline `hpc bash -c`; if so write a driver script under
  `campaign/workers/logs/divrule_20260925/` and run `hpc bash <script>`). `timeout` on every command.
- Do NOT read or list anything under `j10_*`, `j11_*`, `j12_*`, `bfcl_*` results or any test_normal /
  test_challenge data. Fixtures only, plus the committed dev basis in (2).
- Edit only the files listed above. Do not edit preregs, the ledger, the paper, `src/`, configs or PBS scripts.
  Do not commit.

## Return contract (≤ 40 lines)

Tag claims `[OBSERVED path:line]` or `[INFERRED]`. For each report: the hook lines (edited in place) and the new
function line ranges; the citation check you ran; test summary lines with PBS job ids; the dev-basis identity
result; anything in the drafts you found ambiguous or impossible to implement as written (quote the sentence).
