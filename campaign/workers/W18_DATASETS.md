# W-18 — J5a/J5b datasets (`sft_b_plus` / `sft_c`)

**Unit:** W-18. Build-and-measure only. No training, no GPU, no planner calls, no commit.
**Date:** 2026-09-18
**Repo:** `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**One-line read:** Exactly **25 ASK targets** materialised in `sft_c`, equal to `n_needed`; `sft_b_plus` has **zero**. That is the whole of J5b's ASK supervision.

No builder or training code was changed. The brief's CLI was run as specified, with `APPWORLD_ROOT` and `HF_HOME` added after the as-written command failed (AppWorld looked for `data/tasks` under cwd).

---

## Commands and exit statuses

**Attempt 1 (brief command as written) — both failed.** `--split train` calls AppWorld `load_task_ids`, which uses cwd unless `APPWORLD_ROOT` is set.

```
timeout 1800 hpc -c 4 -m 32gb -t 00:30:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m sidekick.training.matched_sft --mode sft_b_plus --campaign-root /scratch/n12194778/sidekick/results/hj4_correction_train_20260917 --split train --out /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl'
```

| Job | PBS id | Host | Wall | Exit |
|---|---|---|---:|---:|
| J5a `sft_b_plus` | `25422278.aqua` | cpu1n049 | 45s | **1** |
| J5b `sft_c` | `25422279.aqua` | cpu1n024 | 45s | **1** |

Error: `The task directory (.../plan-2026-09-15/data/tasks) doesn't exist.` [OBSERVED /home/n12194778/.hpc-spool/20260918-131442-2974382.out:18] [OBSERVED /home/n12194778/.hpc-spool/20260918-131442-2974467.out:18]

**Attempt 2 — same CLI, env only.** Added `APPWORLD_ROOT=/scratch/n12194778/sidekick/appworld` and `HF_HOME=/scratch/n12194778/hf` (same exports as `scripts/pbs/*.pbs`).

| Build | PBS id | Host | Wall | Exit | Log |
|---|---|---|---:|---:|---|
| J5a `sft_b_plus` | `25422292.aqua` | cpu1n049 | 1070s | **0** | `/home/n12194778/.hpc-spool/20260918-131609-2993281.out` |
| J5b `sft_c` | `25422293.aqua` | cpu1n021 | 1405s | **0** | `/home/n12194778/.hpc-spool/20260918-131609-2993427.out` |

[OBSERVED /home/n12194778/.hpc-spool/20260918-131609-2993281.out:1,1060]
[OBSERVED /home/n12194778/.hpc-spool/20260918-131609-2993427.out:1,1068]

The CLI prints and writes the summary via `_write_manifest` (`<out>.manifest.json`); no wrapper script was added. [OBSERVED src/sidekick/training/sft_data.py:912-917]

---

## Output files

| File | Bytes | sha256 |
|---|---:|---|
| `/scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl` | 36,426,453 | `e557657e2aa594fc369d969fd14ba2cfb3c03b4bc1f16ca3b06451543025e4a6` |
| `/scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl` | 36,436,304 | `0e9283e40aa7053eadf0ad97a00eebf017a46a9e091920c18ebc5172bdb80290` |

Sidecars: `sft_b_plus_20260918.jsonl.manifest.json`, `sft_c_20260918.jsonl.manifest.json`.
Independent file hashes match the manifests. Teacher prefix of both outputs is the frozen teacher bytes. Frozen teacher was not overwritten. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:259-277]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl.manifest.json:954]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl.manifest.json:962]

Teacher sha256 `f56fe6ea21b0b6c55ee77a76af714b74ca63b4a93238191292f45e5f0f5ef812` matches the frozen `sft_b_s123_p075.jsonl`. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:276-277]

---

## Counts

Correction-half action/ASK counts are from reading the JSONL `meta` fields **and** from walking `supervised_message_indices` against assistant content. Those two file counts agree with each other and with the summary dicts (no silent reconciliation). [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:435-654]

| | `sft_b_plus` (J5a) | `sft_c` (J5b) |
|---|---:|---:|
| n sequences (file) | 497 | 497 |
| n teacher sequences | 230 | 230 |
| n correction sequences | 267 | 267 |
| n supervised **action** targets (correction `meta` / supervised idx) | 775 / 775 | 775 / 775 |
| n **ASK targets** (correction `meta` / supervised idx) | 0 / 0 | 25 / 25 |
| n dropped (summary) | 3 | 3 |
| n unrepresentable (summary) | 0 | 0 |
| n truncated / messages dropped (summary) | 21 / 484 | 21 / 484 |
| n interventions seen (summary) | 777 | 777 |
| n_needed / n_needless / n_ambiguous / n_incomplete (summary) | 0 / 777 / 0 / 0 (no labels; all treated needless) | **25** / 46 / 326 / 380 |

[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl.manifest.json:441-453]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl.manifest.json:444-461]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:435-654]

Independent recount of the label file (same classifier as `classify_branch_label`): 777 rows = 25 needed + 46 needless + 326 ambiguous + 380 incomplete. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:400-405,434]
[OBSERVED src/sidekick/training/matched_sft.py:81-95]

The 25 ASK targets sit on **23** correction episodes (21 with one ASK, two with two: `60d0b5b_1` seed 1 and `b7a9ee9_2` seed 1). Those 23 are the only correction sequences whose messages differ between the two files. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:80-90,169-177,432-433]

---

## Five pre-registered invariants

Checked by reading both JSONL files. Summary-vs-file disagreements: **none**. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:656-659]

| # | Invariant | Verdict | Settling number |
|---|---|---|---|
| 1 | Same episode set in both files | **PASS** | 497 sequences each; 267 shared correction `(task_id, seed)` keys; same order; 0 only-in-one. Teacher byte-prefix identical. |
| 2 | Same number of supervised action targets | **PASS** | **775** action targets in both (meta and supervised-idx content). 0 episodes with an action-count mismatch. |
| 3 | ASK targets in `sft_c` == `n_needed`; zero in `sft_b_plus` | **PASS** | File: `sft_c` 25 ASK targets, `sft_b_plus` 0. Summary `n_needed` = 25. Labels-file needed = 25. |
| 4 | No `INTERVENTION:` substring in either file | **PASS** | **0** occurrences in both files (message content and full-record JSON). |
| 5 | Unrepresentable drops, with reason | **PASS** (zero such drops) | `n_unrepresentable` = **0** in both summaries. Kept JSONL cannot show dropped rows; both manifests' `dropped_counts` are `correction_no_intervention: 3` only — no `unrepresentable` reason. |

[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:288-360]

### Invariant 3 — extra observation (not a fail)

The pre-registered claim is about **targets**, not about the substring `ASK_PLANNER:` appearing in context. Both files contain **10 unsupervised** `ASK_PLANNER:` assistant turns: 9 in the frozen teacher (`source` `solved`/`partial`) and 1 in a correction episode (`60d0b5b_2` seed 3) that was never a supervised target. `sft_c` therefore has 35 `ASK_PLANNER:` assistant strings = 25 supervised + those 10. That matches `n_ask_events: 1` / `n_ask_planner_targets: 1` on the correction half. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl.manifest.json:447-448]

A first-pass checker that required zero `ASK_PLANNER:` strings in `sft_b_plus` therefore marked invariant 3 fail; that is stricter than the pre-registered invariant. Target counts still match `n_needed`.

### Drops (invariant 5 detail)

Both builds dropped the same 3 correction episodes, reason `no_intervention`:

| seed | task_id |
|---:|---|
| 2 | `e85d92a_2` |
| 2 | `e85d92a_3` |
| 3 | `e85d92a_2` |

[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_b_plus_20260918.jsonl.manifest.json:438-439]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:338-360]

`n_unrepresentable` is summary-only (dropped rows are not in the JSONL). Both summaries report 0; `dropped_counts` contains no `unrepresentable` key.

---

## Provenance (`sft_c` summary)

| Field | Value |
|---|---|
| `delta_band_delta` | `0.16599999999999993` |
| `labels_sha256` | `0b5049ef53cb5e31b62701c4e7eb80e3a9a2508eb32b08a78e27783fb4af360b` |
| `labels_jsonl` | `/scratch/n12194778/sidekick/results/hj6_branches_train_20260917/branches.jsonl` |
| `campaign_sha256` | `d57e5b79e6e9fa7f5028f388761217d60deeadee152853e8d4075e2851f21774` |
| `source_commit` | `0faf8949a7878f63d03572ed3cc86c1187b11d5f` |

Independent sha256 of the labels file matches `labels_sha256`. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl.manifest.json:418,442-443]
[OBSERVED /scratch/n12194778/sidekick/artifacts/sft/w18_invariant_check_20260918.json:270-271]

`n_ambiguous_treated_as_needless` = 706 = 326 ambiguous + 380 incomplete. [OBSERVED /scratch/n12194778/sidekick/artifacts/sft/sft_c_20260918.jsonl.manifest.json:446]

---

## Implication for J5b

25 ASK targets is what the four-replicate train labels predicted. The builder did not lose needed points to unrepresentable drops. J5b is **trainable as coded** and **statistically thin**: ASK supervision is 25 turns on 23 of 267 correction episodes (plus a 230-sequence teacher half with no ASK targets). That is a CPU fact, not a GPU result. [INFERRED from the counts above]
