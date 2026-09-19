#!/bin/bash
# Static validation for A20. Runs inside `hpc`, never on aquarius01.
set -euo pipefail
cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH="src:${PYTHONPATH:-}"
PY=/scratch/n12194778/sidekick/env/bin/python

echo "=== bash -n scripts/pbs/b1_pilot.pbs ==="
bash -n scripts/pbs/b1_pilot.pbs
echo "bash_n_rc=0"

echo "=== guard harness ==="
"${PY}" campaign/workers/scratch_A20/test_b1_pilot_guards.py
echo "guards_rc=0"

echo "=== pytest suite ==="
"${PY}" -m pytest tests -q --import-mode=importlib
echo "pytest_rc=0"
