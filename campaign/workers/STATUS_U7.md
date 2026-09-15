# STATUS_U7 — HJ-1 Class A `executor_alone` (Cline)

Unit: U7. Brief: `campaign/briefs/U7_cline_hj1a_executor_alone.md`.
Host: aquarius01 (login node — no compute here, all work in PBS). Date: 2026-09-15.
Deadline: submit with walltime=05:00:00 before 23:30 (cluster maintenance ~08:00 2026-09-16).

## Milestones

- [x] 2026-09-15 — configs written: `configs/pilot_exec_8b.yaml`, `configs/pilot_exec_3b.yaml`
      (planner.type: mock, temperature 0.7, exactly as briefed; 3B differs only in campaign_id+model).
- [x] PBS script `scripts/pbs/hj1a_executor_alone.pbs` written (bash -n OK; vLLM flags reuse the
      proven g3_serve_granite.sh working set [OBSERVED /scratch/n12194778/sidekick/logs/g3_serve.json]).
- [x] Submitted 2026-09-15 22:14 AEST — job id **25385589.aqua** (walltime 05:00:00, gpu_inter).
- [ ] 8B smoke gate (3 tasks × seed 1, workers 3).
- [ ] 8B campaign (57 tasks × seeds 1,2, workers 10).
- [ ] 3B smoke gate.
- [ ] 3B campaign.
- [ ] Manifests written + verification (result.json counts 114+3 each, planner calls == 0,
      per-seed task goal completion, mean steps/tokens per episode, seeds differ).
- [ ] Committed on current branch (no push, no merge).

## How to resume

- Outputs: `/scratch/n12194778/sidekick/results/results/<campaign_id>/` where campaign_id is
  `hj1a_exec8b_20260915` / `hj1a_exec3b_20260915`.
- vLLM logs: `/scratch/n12194778/sidekick/logs/hj1a_vllm_{8b,3b}.log`.
- PBS stdout: `campaign/workers/logs/U7_hj1a.out`.
- If a campaign is partially done, re-running the runner command for that model resumes/overwrites
  per-run results; check result.json count first.

## Notes / obstacles

- (none yet)
