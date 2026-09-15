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
      **FAILED 22:19**: FlashInfer JIT build of the `sampling` op died in both vLLM attempts for
      both models — `#error "CUDA compiler and CUDA toolkit headers are incompatible"` from
      flashinfer's bundled libcudacxx vs nvcc 13.4 (CU13) on PATH
      [OBSERVED /scratch/n12194778/sidekick/logs/hj1a_vllm_8b.log].
- [x] Fix applied to PBS script: `VLLM_USE_FLASHINFER_SAMPLER=0` (PyTorch sampling fallback,
      avoids the JIT entirely), `FLASHINFER_CACHE_DIR` moved to /scratch, kill_vllm also kills
      EngineCore children. Note for analysis: sampling backend is PyTorch, not FlashInfer.
- [x] Resubmitted 22:21 — job **25385758.aqua** (also resubmitted independently by another session
- [x] Job 25385758 was deleted without running (substate 91, 22:25). Resubmitted as 25385779, but a
      parallel session had already submitted 25385774 (same fixed script). To avoid two identical
      campaigns racing on the same /scratch experiment dirs I deleted my 25385779 and left
      **25385774.aqua** as the single active job. **Coordination note: 25385774 is the canonical
      hj1a-exec job — do not submit another hj1a_executor_alone.pbs and do not delete 25385774.**
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
