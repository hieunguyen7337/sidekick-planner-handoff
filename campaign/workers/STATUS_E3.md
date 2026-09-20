# STATUS E3 — iaware adapter dev eval

**Unit:** E3 **State:** done **Last update:** 2026-09-21 03:26 AEST

E2 adapter present. No `hj8_*` config edits, no test-split reads, no git, no rewrite of existing `/scratch/.../results/` trees. Report: `campaign/results/hj8_frontier_iaware_20260921.report.json`. sft_plan **base** is `hj8_sft_plan_bplus_20260919` (no 20260920 tree). [OBSERVED `/scratch/n12194778/sidekick/results/`]

## Smoke 25579721.aqua

Exit_status **0**, walltime 00:08:40, gpu1n012. [OBSERVED `qstat -xf 25579721`]
```
[hj8] lora-module sft_b_plus=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b
```
[OBSERVED campaign/workers/logs/hj8_frontier_live_20260921iawaresmoke.25579721.aqua.out:98]
port=39721 pid=3325580; identity listen pid=3325580 pgid=3325580 matches VLLM_PID. [OBSERVED same:105-109]
Four arms `[gate] PASS` n_broken=0; live calls k10=2 vs k3=20. [OBSERVED same:158-317] job_rc=0. [OBSERVED same:320]

## Full 25580034.aqua

Exit_status **0**, walltime 01:36:09, gpu1n004, job_rc=0. [OBSERVED `qstat -xf 25580034`; log:16099]
```
[hj8] lora-module sft_b_plus=/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_granite8b
```
[OBSERVED campaign/workers/logs/hj8_frontier_live_20260921iaware.25580034.aqua.out:98]
port=20034 pid=1642638; identity listen pid=1642638 pgid=1642638 matches VLLM_PID. [OBSERVED same:105-109]
All four `[gate] PASS` campaign_rc=0. [OBSERVED same:4104-16096]
api_error=timeout=0 (quota-stall not triggered). [OBSERVED hpc 25582566 live counts]

| arm | n | n_broken (parse/api/timeout/crash) | ledger calls | live codex |
|---|---|---|---|---|
| sft_plan | 114 | 0 | 114 | 0 |
| fixed_k_10 | 114 | 1 parse_error | 276 | 162 |
| fixed_k_3 | 114 | 0 | 778 | 664 |
| oracle | 114 | 1 parse_error | 146 | 32 |

[OBSERVED hpc 25582566 stdout; report frontier] Live kept-tree spend **858**. [OBSERVED same] Expected ~1230 was ledger-like (base k10=314 k3=768 oracle=148). [OBSERVED report:314/768/148]

## Contrasts (task-clustered; iaware − base except #4)

1. **sft_plan_iaware − sft_plan_base** gp_all/surv **+0.0181** CI95 [−0.0328, +0.070] n=114 drop=0. TGC **−0.0088** [−0.0789, +0.0702]. CI includes 0 (no detected regression). [OBSERVED report:3285,:3346]
2. **k10_iaware − k10_base** gp_all **+0.0517** [−0.0243, +0.1268] n=114; gp_surv **+0.0383** [−0.0377, +0.1138] n=111 drop=3. TGC_all **+0.0263** [−0.0789, +0.1316]. CI includes 0. [OBSERVED report:7696,:7757]
3. **k3_iaware − k3_base** gp_all **+0.1863** [+0.1125, +0.2582] n=114; gp_surv **+0.1018** [+0.0267, +0.1743] n=97 drop=17 (base 17 crashes). TGC_all **+0.1579** [+0.0526, +0.2632]. CI excludes 0. [OBSERVED report:10503,:10564]
4. **oracle_iaware − sft_plan_iaware** gp **−0.0086** [−0.0661, +0.0493]; TGC **+0.0351** [−0.0526, +0.1228]. No detected headroom above plan-only. [OBSERVED report:478,:539]

## Dose-response (surv gp @ calls/ep)

base: **0.700 @ 1.00** → **0.662 @ 2.75** → **0.605 @ 6.74**. [OBSERVED report:95,:164,:233]
iaware: **0.718 @ 1.00** → **0.696 @ 2.42** → **0.701 @ 6.82**. [OBSERVED report:61,:129,:199]
Slope flattens. [INFERRED from those three points]

Iaware arms n_crashed=0 so all-ep = surv. [OBSERVED analysis stdout:28-32]
