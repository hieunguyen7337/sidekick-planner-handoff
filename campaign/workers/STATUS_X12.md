# STATUS_X12 — records for the HJ-12 build wave, and two corrections

State: **done**. No code edited, no `qsub`, no GPU touched, no evaluation run, no `git` executed.

## Config Comment Diff

`configs/hj12_advise_fixed_k_10_fullctx.yaml` comment updated to describe the context-matched advise control for Claim C1 (diff proves only comment lines changed; no config keys moved) [OBSERVED configs/hj12_advise_fixed_k_10_fullctx.yaml:1-5]:

```diff
--- configs/hj12_advise_fixed_k_10_fullctx.yaml (previous)
+++ configs/hj12_advise_fixed_k_10_fullctx.yaml (current)
@@ -1,3 +1,5 @@
-# HJ-12 takeover channel: fixed_k (k=10). Same executor/limits/prices as
-# configs/hj8_fixed_k_10.yaml (frozen; this file is a copy). takeover: true is
-# the only experimental difference from the advise arm.
+# HJ-12 context-matched advise control for Claim C1. Same executor/limits/prices
+# as configs/hj8_fixed_k_10.yaml (frozen; this file is a copy), differing only
+# in campaign_id and correct_context: full. Its purpose is to give the advising
+# planner the same transcript the takeover arm gets so a takeover win cannot
+# be explained by context.
```

## Preregistration Amendment Extended

Extended existing section:
`## Amendment 2026-09-21 — C1 context-matched control` in `docs/prereg_hj12_dev_20260922.md` [OBSERVED docs/prereg_hj12_dev_20260922.md:234, 277-287].

Added rival explanation regarding shared `fixed_k` executor ASK channel (`allow_executor_ask: true` [OBSERVED /scratch/n12194778/sidekick/results/hj8_fixed_k_10_20260921iaware/fixed_k/1/0d8a4ee_1/events.jsonl]). The ASK path returns prose advice in both arms, which attenuates the C1 contrast without biasing it; per-arm ASK counts are required to be reported, and the C1 effect size is registered as a lower bound if ASK events dominate [INFERRED].

## RUNS.md Section Added

Added section:
`## 13. The HJ-12 build wave — 2026-09-21` in `campaign/RUNS.md` [OBSERVED campaign/RUNS.md:2429-2448].

Records commits `4bd6698`, `e405ed3`, `722e887`, and `808d445`, test suite status (**498 passed, 1 skipped**), **zero** hosted calls spent, and that Phase P1 jobs `25596786` and `25596787` are queued waiting on GPU availability with no results or verdicts stated.

## GAPs

No `[GAP]` markers left. All required facts, commit hashes, job IDs, and paths were specified in the brief or existing repo records.
