#!/bin/bash
# R1 static validation. Runs inside `hpc`, never on aquarius01.
set -euo pipefail
cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="src:${PYTHONPATH:-}"
PY="${PY:-/scratch/n12194778/sidekick/env/bin/python}"

echo "=== bash -n scripts/pbs/hj8_frontier.pbs ==="
bash -n scripts/pbs/hj8_frontier.pbs
echo "bash_n_rc=0"

echo "=== grep -c contract needles in hj8_frontier.pbs ==="
echo "grep_c_8000=$(grep -c 8000 scripts/pbs/hj8_frontier.pbs || true)"
echo "grep_c_pkill=$(grep -c pkill scripts/pbs/hj8_frontier.pbs || true)"
echo "grep_c_setsid=$(grep -c setsid scripts/pbs/hj8_frontier.pbs || true)"
echo "grep_c_trap=$(grep -c 'trap kill_vllm EXIT' scripts/pbs/hj8_frontier.pbs || true)"
echo "grep_c_walltime=$(grep -c 'walltime=10:00:00' scripts/pbs/hj8_frontier.pbs || true)"
echo "grep_c_vllm_port=$(grep -c 'VLLM_PORT' scripts/pbs/hj8_frontier.pbs || true)"

echo "=== guard harness ==="
"${PY}" campaign/workers/scratch_A20/test_r1_hj8_guards.py
echo "guards_rc=0"

echo "=== pytest suite ==="
"${PY}" -m pytest tests -q --import-mode=importlib
echo "pytest_rc=0"
