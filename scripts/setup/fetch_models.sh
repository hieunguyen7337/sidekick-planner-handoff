#!/bin/bash
# Download pinned study models into HF_HOME. Run inside a PBS job.
set -euo pipefail

SCRATCH="${SIDEKICK_SCRATCH:-/scratch/n12194778/sidekick}"
VENV="${SIDEKICK_VENV:-${SCRATCH}/env}"
export HF_HOME="${HF_HOME:-/scratch/n12194778/hf}"
LOGDIR="${SCRATCH}/logs"
META="${LOGDIR}/fetch_models.json"
mkdir -p "${HF_HOME}" "${LOGDIR}"

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export PATH="${VENV}/bin:${HOME}/.local/bin:${PATH}"

echo "[fetch_models] host=$(hostname) job=${PBS_JOBID:-none} HF_HOME=${HF_HOME}"
BEFORE=$(du -sb "${HF_HOME}" 2>/dev/null | awk '{print $1}')
echo "[fetch_models] HF_HOME bytes before=${BEFORE:-0}"

HF_BIN="${VENV}/bin/hf"
if [[ ! -x "${HF_BIN}" ]]; then
  HF_BIN="${VENV}/bin/huggingface-cli"
fi
if [[ ! -x "${HF_BIN}" ]]; then
  echo "hf/huggingface-cli missing from ${VENV}" >&2
  exit 1
fi

MODELS=(
  "ibm-granite/granite-4.2-8b"
  "ibm-granite/granite-4.2-3b"
  "Qwen/Qwen3-1.7B"
)

download_one() {
  local repo="$1"
  echo "[fetch_models] downloading ${repo}"
  if [[ "$(basename "${HF_BIN}")" == "hf" ]]; then
    "${HF_BIN}" download "${repo}"
  else
    "${HF_BIN}" download "${repo}"
  fi
}

for repo in "${MODELS[@]}"; do
  download_one "${repo}"
done

AFTER=$(du -sb "${HF_HOME}" | awk '{print $1}')
DELTA=$((AFTER - ${BEFORE:-0}))
echo "[fetch_models] HF_HOME bytes after=${AFTER} delta=${DELTA}"

"${VENV}/bin/python" - <<PY
import json, os, pathlib
hf = pathlib.Path(os.environ["HF_HOME"])
hub = hf / "hub"
models = [
    "ibm-granite/granite-4.2-8b",
    "ibm-granite/granite-4.2-3b",
    "Qwen/Qwen3-1.7B",
]
out = {
    "host": os.uname().nodename,
    "job": os.environ.get("PBS_JOBID"),
    "hf_home": str(hf),
    "bytes_before": int("${BEFORE:-0}"),
    "bytes_after": int("${AFTER}"),
    "bytes_delta": int("${DELTA}"),
    "models": {},
}
for repo in models:
    dirname = "models--" + repo.replace("/", "--")
    root = hub / dirname
    rec = {"dir": str(root), "exists": root.exists()}
    ref = root / "refs" / "main"
    if ref.exists():
        rec["revision"] = ref.read_text().strip()
    snaps = root / "snapshots"
    if snaps.exists():
        rec["snapshots"] = sorted(p.name for p in snaps.iterdir() if p.is_dir())
    out["models"][repo] = rec
path = pathlib.Path("${META}")
path.write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
PY

echo "[fetch_models] done $(date -Iseconds)"
exit 0
