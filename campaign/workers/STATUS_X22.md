# STATUS X22

Created `configs/hj13_planner_alone_cap81.yaml` and `configs/hj13_advise_fixed_k_1_fullctx.yaml`; each source diff has exactly three changed regions. [OBSERVED configs/hj13_planner_alone_cap81.yaml:1] [OBSERVED configs/hj13_advise_fixed_k_1_fullctx.yaml:1]

```diff
--- configs/pilot_planner_alone.yaml
+++ configs/hj13_planner_alone_cap81.yaml
@@ -1 +1,4 @@
-# HJ-1 Class B — planner_alone on AppWorld dev.
+# HJ-13 uncapped re-run of the planner_alone ceiling arm on AppWorld dev.
+# The original 25-call cap understated the ceiling used by every campaign
+# non-inferiority comparison; this re-run raises that ceiling to 81 calls.
+# [OBSERVED campaign/workers/brief_X22_tierB_configs.md:18-27]
@@ -9 +12 @@
-campaign_id: hj1b_planner_20260915
+campaign_id: hj13_planner_alone_cap81_20260923
@@ -25 +28 @@
-  max_planner_calls: 25
+  max_planner_calls: 81
```

```diff
--- configs/hj12_advise_fixed_k_10_fullctx.yaml
+++ configs/hj13_advise_fixed_k_1_fullctx.yaml
@@ -1,5 +1,5 @@
-# HJ-12 context-matched advise control for Claim C1. Same executor/limits/prices
-# as configs/hj8_fixed_k_10.yaml (frozen; this file is a copy), differing only
-# in campaign_id and correct_context: full. Its purpose is to give the advising
-# planner the same transcript the takeover arm gets so a takeover win cannot
-# be explained by context.
+# HJ-13 full-context advice ceiling: review every step to price advice at or
+# above the budget where action channels win. Prior advice peaked near 204.5k
+# non-cached planner tokens per episode versus winning action arms at 357k and
+# 443k; this tests whether channel rather than budget determines quality.
+# [OBSERVED campaign/workers/brief_X22_tierB_configs.md:35-45]
@@ -7 +7 @@
-campaign_id: hj12_advise_fixed_k_10_fullctx_20260923
+campaign_id: hj13_advise_fixed_k_1_fullctx_20260923
@@ -9 +9 @@
-fixed_k: 10         # review every 10 steps; ~4 reviews + 1 cached plan over a 40-step episode
+fixed_k: 1          # review every step; the cached up-front plan remains free
```

Added `"fixed_k|${REPO}/configs/hj13_advise_fixed_k_1_fullctx.yaml|hj13_advise_fixed_k_1_fullctx"`. [OBSERVED scripts/pbs/hj12_live.pbs:158]

The planner-alone PBS now documents the override form and uses `CONFIG="${CONFIG:-${REPO}/configs/pilot_planner_alone.yaml}"` and `CID="${CID:-hj1b_planner_20260915}"` at every runner/summary call. With neither override, its config, campaign ID, and derived output path remain unchanged. [OBSERVED scripts/pbs/hj1b_planner_alone.pbs:14-16] [OBSERVED scripts/pbs/hj1b_planner_alone.pbs:35-39] [OBSERVED scripts/pbs/hj1b_planner_alone.pbs:68-100]

Verification: both `bash -n` commands exited 0. [INFERRED] Both configs directly specify `planner.type: codex`, `planner.model: gpt-5.6-luna`, and `max_planner_calls: 81`. [OBSERVED configs/hj13_planner_alone_cap81.yaml:13-16] [OBSERVED configs/hj13_planner_alone_cap81.yaml:28] [OBSERVED configs/hj13_advise_fixed_k_1_fullctx.yaml:10-12] [OBSERVED configs/hj13_advise_fixed_k_1_fullctx.yaml:43]

The required compute-side YAML parse could not run: both permitted `hpc` attempts returned `qsub: cannot connect to server aqua (errno=15008)` before issuing a job ID; no YAML-aware login-node binary was available. [INFERRED] No full Python suite ran because compute was unavailable and Python is forbidden on the login node. [INFERRED]

The read-only `find /scratch/n12194778/sidekick/results -maxdepth 1 -type d -name 'hj13_*'` check returned `NO_HJ13_RESULTS_DIRECTORIES`. [INFERRED]

I did not submit any job. [INFERRED]
