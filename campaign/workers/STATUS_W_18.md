# STATUS W-18 — build J5a/J5b datasets (sft_b_plus / sft_c)

**Unit:** W-18. **CPU only. No train. No GPU. No live `codex`. Do not commit.**
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Resume state

- **Milestone:** complete. Both datasets built, five invariants checked against the JSONL files, report written. Waiting for orchestrator review.
- **Code changes:** none. Env-only retry after the brief command failed without `APPWORLD_ROOT`.
- **Do not touch (honoured):** `scripts/setup/branch_counterfactual.py`, `scripts/setup/fit_feature_verifier.py`, `src/sidekick/agents/planner.py`, `src/sidekick/training/matched_sft.py`. Frozen teacher `sft_b_s123_p075.jsonl` not overwritten. `/scratch/.../results/` not modified.

## Jobs [OBSERVED]

| What | PBS | Exit | Log |
|---|---|---:|---|
| J5a as-written (no `APPWORLD_ROOT`) | `25422278.aqua` | 1 | `/home/n12194778/.hpc-spool/20260918-131442-2974382.out` |
| J5b as-written | `25422279.aqua` | 1 | `/home/n12194778/.hpc-spool/20260918-131442-2974467.out` |
| J5a with `APPWORLD_ROOT` | `25422292.aqua` | 0 (1070s) | `/home/n12194778/.hpc-spool/20260918-131609-2993281.out` |
| J5b with `APPWORLD_ROOT` | `25422293.aqua` | 0 (1405s) | `/home/n12194778/.hpc-spool/20260918-131609-2993427.out` |
| File-level invariant check | `25422389.aqua` | 0 | `/home/n12194778/.hpc-spool/20260918-134302-3368994.out` |
| ASK-string attribution | `25422404.aqua` | 0 | `/home/n12194778/.hpc-spool/20260918-134459-3398513.out` |

## Owned files (this unit)

- `campaign/workers/STATUS_W_18.md` (this file)
- `campaign/workers/W18_DATASETS.md`
- scratch outputs (not repo):
  - `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl` sha256 `e557657e2aa594fc369d969fd14ba2cfb3c03b4bc1f16ca3b06451543025e4a6`
  - `/scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl` sha256 `0e9283e40aa7053eadf0ad97a00eebf017a46a9e091920c18ebc5172bdb80290`
  - `/scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json`

## Headline numbers

| | `sft_b_plus` | `sft_c` |
|---|---:|---:|
| sequences | 497 | 497 |
| action targets | 775 | 775 |
| ASK targets | **0** | **25** (= `n_needed`) |
| unrepresentable drops | 0 | 0 |
| other drops | 3 `no_intervention` | 3 `no_intervention` |

Invariants 1–5: all **PASS** on the pre-registered criteria. Full table in `campaign/workers/W18_DATASETS.md`.
