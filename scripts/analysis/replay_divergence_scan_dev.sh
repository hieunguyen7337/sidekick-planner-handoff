#!/bin/bash
# Dev-only scan: replay_divergence in prefix-replay campaigns (current result.json + error events), and
# how many refill logs purged crashes in those campaigns. Never touches j10_/j11_/j12_/bfcl_ campaigns.
R=/scratch/n12194778/sidekick/results
LOGS=/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/logs
for d in "${R}"/*; do
  c=$(basename "${d}")
  case "${c}" in j10_*|j11_*|j12_*|bfcl_*) continue;; esac
  [ -d "${d}/prefix_handoff" ] || continue
  n=$(ls -d "${d}"/prefix_handoff/*/* 2>/dev/null | wc -l)
  div=$(grep -l '"replay_divergence"' "${d}"/prefix_handoff/*/*/events.jsonl 2>/dev/null | wc -l)
  crash=$(grep -l '"error_type": *"crash"' "${d}"/prefix_handoff/*/*/result.json 2>/dev/null | wc -l)
  echo "${c} episodes=${n} with_divergence_event=${div} crash_now=${crash}"
done | awk '$3 != "with_divergence_event=0" || $4 != "crash_now=0"'
echo "--- refill logs mentioning replay_divergence (dev logs dir)"
grep -l 'replay_divergence' "${LOGS}"/*.out 2>/dev/null | grep -v 'j10_\|j11_\|j12_' | wc -l
echo "--- total dev prefix campaigns scanned"
ls -d "${R}"/*/prefix_handoff 2>/dev/null | grep -v '/j10_\|/j11_\|/j12_\|/bfcl_' | wc -l
