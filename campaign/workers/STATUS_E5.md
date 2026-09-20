# STATUS E5 — iaware vs baseline analysis

**Unit:** E5 **State:** done **Last update:** 2026-09-21
PBS **25582845.aqua**, 70s, cpu_inter. Report: `campaign/results/hj8_frontier_iaware_20260921.report.json`. Read-only on `/scratch/n12194778/sidekick/results/`. No eval, GPU, git, or frozen-config edits.

## Command

```
timeout 2400 hpc -c 4 -m 16gb -t 00:30:00 bash campaign/workers/run_E5_j8_frontier.sh
```

That script ran (BLAS=1, `PYTHONPATH=src:.`, `/scratch/n12194778/sidekick/env/bin/python`):

```
scripts/analysis/j8_frontier.py
  --arm oracle_escalation_iaware=/scratch/n12194778/sidekick/results/hj8_oracle_escalation_20260921iaware
  --arm sft_plan_iaware=…/hj8_sft_plan_bplus_20260921iaware
  --arm sft_plan_base=…/hj8_sft_plan_bplus_20260919
  --arm fixed_k_10_iaware=…/hj8_fixed_k_10_20260921iaware
  --arm fixed_k_10_base=…/hj8_fixed_k_10_20260920
  --arm fixed_k_3_iaware=…/hj8_fixed_k_3_20260921iaware
  --arm fixed_k_3_base=…/hj8_fixed_k_3_20260920
  --arm oracle_escalation_base=…/hj8_oracle_escalation_20260920
  --out campaign/results/hj8_frontier_iaware_20260921.report.json
```

exit=0. [OBSERVED hpc 25582845]

## Headline (verbatim)

`J8 frontier (dev): all named arms have ≥114 rows. Headline quality contrast uses all-episodes (crash = 0) for every metric; survivor population is reported alongside.`
[OBSERVED report.json:2; hpc stdout]

`headline_refused` false; `refusals` []. `h3` []. [OBSERVED report.json:3-4]

Contrasts: paired, task-clustered, bootstrap 10000. Path below = that report.

## Per-arm (n=114 each). live / replay-incl calls/ep; n_broken; n_crashed

| arm | gp_all | gp_surv | tgc_all | tgc_surv | live | replay | broken | crash |
|---|---|---|---|---|---|---|---|---|
| sft_plan_base | 0.700009 | 0.700009 | 0.403509 | 0.403509 | 1.0 | 1.0 | 0 | 0 |
| sft_plan_iaware | 0.718149 | 0.718149 | 0.394737 | 0.394737 | 1.0 | 1.0 | 0 | 0 |
| fixed_k_10_base | 0.644711 | 0.662135 | 0.385965 | 0.396396 | 2.754386 | 2.780702 | 3 | 3 |
| fixed_k_10_iaware | 0.69643 | 0.69643 | 0.412281 | 0.412281 | 2.421053 | 2.421053 | 1 | 0 |
| fixed_k_3_base | 0.514904 | 0.605144 | 0.298246 | 0.350515 | 6.736842 | 6.885965 | 17 | 17 |
| fixed_k_3_iaware | 0.701184 | 0.701184 | 0.45614 | 0.45614 | 6.824561 | 6.824561 | 0 | 0 |
| oracle_escalation_base | 0.666 | 0.666 | 0.377193 | 0.377193 | 1.298246 | 1.298246 | 1 | 0 |
| oracle_escalation_iaware | 0.709561 | 0.709561 | 0.429825 | 0.429825 | 1.280702 | 1.280702 | 1 | 0 |

[OBSERVED report.json:16-291] Totals live: 114, 114, 314, 276, 768, 778, 148, 146. Iaware crash=0 so all=surv on those arms. [OBSERVED report.json:28,63,131,200; stdout]

## 1. sft_plan_iaware − sft_plan_base

gp all=surv **+0.0181** CI95 [−0.0328, +0.07] n_pairs=114 drop=0. [OBSERVED :3306-3370]
TGC all=surv **−0.0088** [−0.0789, +0.0702]. [OBSERVED :3123-3126]

## 2. Dose contrasts (iaware − base)

**fixed_k_10:** gp_all **+0.0517** [−0.0243, +0.1268] n=114 drop=0. [OBSERVED :7717-7720] gp_surv **+0.0383** [−0.0377, +0.1138] n=111 drop=3. [OBSERVED :7778-7781] TGC_all **+0.0263** [−0.0789, +0.1316]. [OBSERVED :7534-7537] TGC_surv **+0.027** [−0.0796, +0.1339]. [OBSERVED :7595-7598]

**fixed_k_3:** gp_all **+0.1863** [+0.1125, +0.2582] n=114 drop=0. [OBSERVED :10524-10527] gp_surv **+0.1018** [+0.0267, +0.1743] n=97 drop=17. [OBSERVED :10585-10588] TGC_all **+0.1579** [+0.0526, +0.2632]. [OBSERVED :10341-10344] TGC_surv **+0.1237** [+0.0105, +0.236]. [OBSERVED :10402-10405]

## 3. Dose-response (survivor gp @ live calls/ep)

base: **0.700009 @ 1.0** → **0.662135 @ 2.754386** → **0.605144 @ 6.736842**. [OBSERVED :94-102, :160-171, :230-241]
iaware: **0.718149 @ 1.0** → **0.69643 @ 2.421053** → **0.701184 @ 6.824561**. [OBSERVED :60-68, :128-136, :198-206]

## 4. oracle_escalation_iaware − sft_plan_iaware

gp all=surv **−0.0086** [−0.0661, +0.0493] n=114 drop=0. [OBSERVED :499-502, :560-563]
TGC all=surv **+0.0351** [−0.0526, +0.1228]. [OBSERVED :316-319, :377-380]

## Oracle escalation count (n=114)

Script does not emit `n_escalations` for this arm (`h3` empty; label is not gated). [OBSERVED report.json h3; j8_frontier.py:253-255]
Ledger live=replay **1.280702**/ep, **146** total. [OBSERVED :28-34] vs sft_plan_iaware 114 total. Extra **32**. [INFERRED 146−114]
Smoke-definition (`actor==planner` and `usage.provider==codex`, same as `hj8_frontier.pbs:541-542`): **32** events in **22**/114 episodes (base: 34 in 24/114). [OBSERVED hpc spool 20260921-033218-2953193.out:118-119]
3-task smoke: `hj8_oracle_escalation | 3 | 0 | 0 | 0 | 10.67`. [OBSERVED campaign/workers/logs/hj8_frontier_live_20260921iawaresmoke.25579721.aqua.out:317]
