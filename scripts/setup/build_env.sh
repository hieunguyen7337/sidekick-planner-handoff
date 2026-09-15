#!/bin/bash
# Idempotent Sidekick venv builder. Run inside a PBS job, never on aquarius01.
set -euo pipefail

SCRATCH="${SIDEKICK_SCRATCH:-/scratch/n12194778/sidekick}"
VENV="${SIDEKICK_VENV:-${SCRATCH}/env}"
UV="${UV_BIN:-${HOME}/.local/bin/uv}"
PYTHON_VER="${SIDEKICK_PYTHON:-3.12}"
APPWORLD_COMMIT="${APPWORLD_COMMIT:-42b5bcf3cd334fee33f0c37c02070a9f5807add5}"
LOGDIR="${SCRATCH}/logs"
FREEZE="${SCRATCH}/env-freeze.txt"
META="${LOGDIR}/env_build.json"
START_TS="$(date -Iseconds)"

mkdir -p "${SCRATCH}" "${LOGDIR}" "${SCRATCH}/artifacts"
export UV_CACHE_DIR="${SCRATCH}/uv-cache"
export UV_LINK_MODE=copy
export UV_PYTHON_PREFERENCE=only-managed
export HF_HOME="${HF_HOME:-/scratch/n12194778/hf}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
mkdir -p "${HF_HOME}" "${UV_CACHE_DIR}"

echo "[build_env] host=$(hostname) job=${PBS_JOBID:-none} start=${START_TS}"
echo "[build_env] scratch=${SCRATCH} venv=${VENV} uv=${UV}"
echo "[build_env] appworld_commit=${APPWORLD_COMMIT}"
command -v "${UV}" >/dev/null || { echo "uv not found at ${UV}" >&2; exit 1; }
"${UV}" --version

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "[build_env] creating venv Python ${PYTHON_VER}"
  "${UV}" venv --python "${PYTHON_VER}" "${VENV}"
else
  echo "[build_env] reusing existing venv"
fi
PY="${VENV}/bin/python"
"${PY}" -V

pip_install() {
  echo "[build_env] uv pip install $*"
  "${UV}" pip install --python "${PY}" "$@"
}

# 1. torch (default PyPI cu12x wheel)
pip_install torch

# 2. vllm >= 0.20
if ! pip_install 'vllm>=0.20'; then
  echo "[build_env] WARN: vllm>=0.20 failed; installing unpinned vllm" >&2
  pip_install vllm
fi

# 3. HF training stack
pip_install transformers accelerate peft trl datasets
if ! pip_install bitsandbytes; then
  echo "[build_env] WARN: bitsandbytes failed; continuing without it" >&2
fi

# 4. harness utilities
pip_install 'pydantic>=2' pyyaml pytest pandas pyarrow httpx

# 5. huggingface hub CLI
pip_install 'huggingface_hub[cli]'

# 6. AppWorld from git at pinned main HEAD (not PyPI)
pip_install "git+https://github.com/StonyBrookNLP/appworld@${APPWORLD_COMMIT}"

echo "[build_env] freezing"
"${UV}" pip freeze --python "${PY}" | tee "${FREEZE}"

echo "[build_env] recording versions"
"${PY}" - <<'PY'
import json, os, sys, pathlib, importlib.metadata as md
from datetime import datetime, timezone

out = {
    "python": sys.version,
    "executable": sys.executable,
    "when": datetime.now(timezone.utc).isoformat(),
    "host": os.uname().nodename,
    "job": os.environ.get("PBS_JOBID"),
    "packages": {},
    "torch": {},
}
for name in [
    "torch", "vllm", "transformers", "accelerate", "peft", "trl",
    "datasets", "bitsandbytes", "pydantic", "huggingface_hub", "appworld",
    "httpx", "pandas", "pyarrow", "pyyaml", "pytest",
]:
    try:
        dist = md.distribution(name)
        rec = {"version": dist.version}
        # RECORD lists installed files; pick the .whl origin if present
        try:
            for line in dist.read_text("direct_url.json").splitlines() if dist.read_text("direct_url.json") else []:
                rec["direct_url_line"] = line[:500]
        except Exception:
            pass
        try:
            du = dist.read_text("direct_url.json")
            rec["direct_url"] = du
        except Exception:
            rec["direct_url"] = None
        out["packages"][name] = rec
    except md.PackageNotFoundError:
        out["packages"][name] = {"version": None, "missing": True}

try:
    import torch
    out["torch"] = {
        "version": torch.__version__,
        "cuda": torch.version.cuda,
        "file": torch.__file__,
        "cuda_available": torch.cuda.is_available(),
    }
except Exception as e:
    out["torch"]["error"] = repr(e)

path = pathlib.Path(os.environ.get("SIDEKICK_SCRATCH", "/scratch/n12194778/sidekick")) / "logs" / "env_versions.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2)[:8000])
PY

echo "[build_env] disk usage"
du -sh "${VENV}" | tee "${LOGDIR}/venv_du.txt"
du -sh "${UV_CACHE_DIR}" | tee -a "${LOGDIR}/venv_du.txt"
echo "${APPWORLD_COMMIT}" > "${SCRATCH}/appworld.commit"
echo "[build_env] done $(date -Iseconds)"
exit 0
