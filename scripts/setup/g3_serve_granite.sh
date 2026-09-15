#!/bin/bash
# Serve granite-4.2-8b under vLLM with LoRA, probe OpenAI API, load smoke adapter.
# GPU job only.
set -uo pipefail

SCRATCH="${SIDEKICK_SCRATCH:-/scratch/n12194778/sidekick}"
VENV="${SIDEKICK_VENV:-${SCRATCH}/env}"
export HF_HOME="${HF_HOME:-/scratch/n12194778/hf}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export VLLM_ALLOW_RUNTIME_LORA_UPDATING=1
export PATH="${VENV}/bin:${HOME}/.local/bin:${PATH}"
# FlashInfer JIT during vLLM warmup needs nvcc. Prefer the pip-bundled CUDA 13 toolkit.
CU13="${VENV}/lib/python3.12/site-packages/nvidia/cu13"
if [[ -x "${CU13}/bin/nvcc" ]]; then
  export CUDA_HOME="${CU13}"
  export CUDA_PATH="${CU13}"
  export PATH="${CU13}/bin:${PATH}"
  export LD_LIBRARY_PATH="${CU13}/lib:${CU13}/lib64:${LD_LIBRARY_PATH:-}"
fi
if command -v module >/dev/null 2>&1; then
  module load CUDA/12.8.0 >/dev/null 2>&1 || module load CUDA/12.6.0 >/dev/null 2>&1 || true
  if [[ -z "${CUDA_HOME:-}" && -n "${EBROOTCUDA:-}" ]]; then
    export CUDA_HOME="${EBROOTCUDA}"
    export PATH="${CUDA_HOME}/bin:${PATH}"
  fi
fi
echo "[g3_serve] CUDA_HOME=${CUDA_HOME:-unset} nvcc=$(command -v nvcc || echo none)"
LOGDIR="${SCRATCH}/logs"
ADAPTER="${SIDEKICK_LORA_OUT:-${SCRATCH}/artifacts/adapters/smoke_lora}"
MODEL="${SIDEKICK_MODEL:-ibm-granite/granite-4.2-8b}"
SERVED_NAME="${SIDEKICK_SERVED_NAME:-granite-4.2-8b}"
PORT="${SIDEKICK_VLLM_PORT:-8000}"
HOST=127.0.0.1
mkdir -p "${LOGDIR}"
VLLM_LOG="${LOGDIR}/g3_vllm_server.log"
SERVE_JSON="${LOGDIR}/g3_serve.json"
PROBE_JSON="${LOGDIR}/g3_probe.json"
FLAG_LOG="${LOGDIR}/g3_vllm_flag_attempts.txt"
: > "${FLAG_LOG}"

echo "[g3_serve] host=$(hostname) job=${PBS_JOBID:-none} $(date -Iseconds)"
echo "[g3_serve] which vllm=$(command -v vllm || true)"
"${VENV}/bin/python" -c "import vllm,sys; print('vllm', vllm.__version__, file=sys.stderr)" || true
nvidia-smi || true

PARSER=""
if [[ -d "${HF_HOME}/hub/models--ibm-granite--granite-4.2-8b" ]]; then
  PARSER=$(find "${HF_HOME}/hub/models--ibm-granite--granite-4.2-8b" -name granite_thinking_parser.py 2>/dev/null | head -n 1 || true)
fi
echo "[g3_serve] parser_plugin=${PARSER:-none}"

start_vllm() {
  local extra=("$@")
  echo "[g3_serve] trying: vllm serve ${MODEL} ${extra[*]}" | tee -a "${FLAG_LOG}"
  : > "${VLLM_LOG}"
  "${VENV}/bin/vllm" serve "${MODEL}" "${extra[@]}" >"${VLLM_LOG}" 2>&1 &
  VLLM_PID=$!
  echo "[g3_serve] pid=${VLLM_PID}"
}

wait_ready() {
  local timeout_s="${1:-600}"
  local t0
  t0=$(date +%s)
  while true; do
    if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
      echo "[g3_serve] vLLM died before ready"
      return 2
    fi
    if curl -sf "http://${HOST}:${PORT}/v1/models" >/dev/null 2>&1; then
      local t1
      t1=$(date +%s)
      LOAD_S=$((t1 - t0))
      echo "[g3_serve] ready after ${LOAD_S}s"
      return 0
    fi
    local now
    now=$(date +%s)
    if (( now - t0 > timeout_s )); then
      echo "[g3_serve] timeout waiting for /v1/models"
      return 1
    fi
    sleep 5
  done
}

kill_vllm() {
  if [[ -n "${VLLM_PID:-}" ]] && kill -0 "${VLLM_PID}" 2>/dev/null; then
    kill "${VLLM_PID}" 2>/dev/null || true
    sleep 3
    kill -9 "${VLLM_PID}" 2>/dev/null || true
    wait "${VLLM_PID}" 2>/dev/null || true
  fi
  # stray children
  pkill -f "vllm serve ${MODEL}" 2>/dev/null || true
  sleep 2
}

COMMON=(
  --served-model-name "${SERVED_NAME}"
  --dtype bfloat16
  --max-model-len 32768
  --enable-lora
  --max-loras 4
  --max-lora-rank 64
  --host "${HOST}"
  --port "${PORT}"
  --gpu-memory-utilization 0.85
)

ATTEMPTS=(
  "plugin| --tool-call-parser qwen3_coder --enable-auto-tool-choice --reasoning-parser granite_thinking_parser --reasoning-parser-plugin ${PARSER}"
  "parser_only| --tool-call-parser qwen3_coder --enable-auto-tool-choice --reasoning-parser granite_thinking_parser"
  "auto| --tool-call-parser qwen3_coder --enable-auto-tool-choice --reasoning-parser auto"
  "tool_only| --tool-call-parser qwen3_coder --enable-auto-tool-choice"
  "lora_only|"
)

WORKING_FLAGS=""
LOAD_S=""
READY=0

for spec in "${ATTEMPTS[@]}"; do
  name="${spec%%|*}"
  rest="${spec#*|}"
  # skip plugin attempt if no parser file
  if [[ "${name}" == "plugin" && -z "${PARSER}" ]]; then
    echo "[g3_serve] skip plugin attempt (no granite_thinking_parser.py)" | tee -a "${FLAG_LOG}"
    continue
  fi
  # shellcheck disable=SC2206
  extra=( ${rest} )
  kill_vllm
  START_EPOCH=$(date +%s)
  start_vllm "${COMMON[@]}" "${extra[@]}"
  sleep 8
  if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
    echo "[g3_serve] ATTEMPT ${name} FAILED immediately" | tee -a "${FLAG_LOG}"
    tail -n 80 "${VLLM_LOG}" | tee -a "${FLAG_LOG}"
    continue
  fi
  if wait_ready 700; then
    WORKING_FLAGS="${rest}"
    READY=1
    echo "[g3_serve] WORKING attempt=${name} flags=${WORKING_FLAGS}" | tee -a "${FLAG_LOG}"
    break
  else
    echo "[g3_serve] ATTEMPT ${name} not ready; log tail:" | tee -a "${FLAG_LOG}"
    tail -n 80 "${VLLM_LOG}" | tee -a "${FLAG_LOG}"
    kill_vllm
  fi
done

GPU_SERVE=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || true)

if [[ "${READY}" -ne 1 ]]; then
  echo "[g3_serve] FATAL: could not start vLLM" | tee -a "${FLAG_LOG}"
  "${VENV}/bin/python" - <<PY
import json, os, pathlib
p = pathlib.Path("${SERVE_JSON}")
p.write_text(json.dumps({
    "ok": False,
    "ready": False,
    "host": os.uname().nodename,
    "job": os.environ.get("PBS_JOBID"),
    "log": "${VLLM_LOG}",
    "flag_log": "${FLAG_LOG}",
}, indent=2))
print(p.read_text())
PY
  exit 1
fi

# Probe: chat, tools, TTFT, concurrency 1 and 16, usage verbatim
"${VENV}/bin/python" - <<'PY'
import asyncio, json, os, time, traceback
from pathlib import Path
import httpx

HOST = os.environ.get("SIDEKICK_VLLM_HOST", "127.0.0.1")
PORT = int(os.environ.get("SIDEKICK_VLLM_PORT", "8000"))
BASE = f"http://{HOST}:{PORT}/v1"
MODEL = os.environ.get("SIDEKICK_SERVED_NAME", "granite-4.2-8b")
LOGDIR = Path("/scratch/n12194778/sidekick/logs")
ADAPTER = os.environ.get("SIDEKICK_LORA_OUT", "/scratch/n12194778/sidekick/artifacts/adapters/smoke_lora")
out = {
    "base": BASE,
    "model": MODEL,
    "failures": [],
}

def gpu():
    import subprocess
    p = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader"],
        capture_output=True, text=True,
    )
    return {"stdout": p.stdout.strip(), "stderr": p.stderr.strip()[-400:]}

out["gpu_at_probe"] = gpu()

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_current_weather",
        "description": "Get the current weather for a specified city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
}]

async def chat(client, model, messages, tools=None, stream=False, n=None, max_tokens=128):
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 1.0,
        "top_p": 0.95,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if stream:
        payload["stream_options"] = {"include_usage": True}
        t0 = time.perf_counter()
        ttft = None
        chunks = []
        usage = None
        text = []
        async with client.stream("POST", f"{BASE}/chat/completions", json=payload, timeout=180.0) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                chunks.append(obj)
                if ttft is None:
                    ttft = time.perf_counter() - t0
                if obj.get("usage"):
                    usage = obj["usage"]
                for ch in obj.get("choices") or []:
                    delta = (ch.get("delta") or {}).get("content") or ""
                    if delta:
                        text.append(delta)
        return {
            "ttft_s": ttft,
            "wall_s": time.perf_counter() - t0,
            "usage": usage,
            "text": "".join(text)[:2000],
            "n_chunks": len(chunks),
        }
    t0 = time.perf_counter()
    r = await client.post(f"{BASE}/chat/completions", json=payload, timeout=180.0)
    wall = time.perf_counter() - t0
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:4000]}
    return {"status": r.status_code, "wall_s": wall, "body": body}

async def measure_conc(client, n, max_tokens=64):
    msgs = [{"role": "user", "content": "Reply with the single word ping."}]
    t0 = time.perf_counter()
    results = await asyncio.gather(
        *[chat(client, MODEL, msgs, max_tokens=max_tokens) for _ in range(n)],
        return_exceptions=True,
    )
    wall = time.perf_counter() - t0
    ok = []
    errs = []
    for i, x in enumerate(results):
        if isinstance(x, Exception):
            errs.append(repr(x))
        else:
            ok.append(x)
    out_tok = 0
    for x in ok:
        usage = (x.get("body") or {}).get("usage") or {}
        out_tok += int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    return {
        "n": n,
        "ok": len(ok),
        "errors": errs[:8],
        "wall_s": wall,
        "output_tokens_sum": out_tok,
        "tokens_per_sec": (out_tok / wall) if wall > 0 else None,
        "sample_usage": (ok[0].get("body") or {}).get("usage") if ok else None,
        "sample_wall_s": ok[0]["wall_s"] if ok else None,
    }

async def main():
    async with httpx.AsyncClient() as client:
        try:
            models = (await client.get(f"{BASE}/models", timeout=30)).json()
            out["models_endpoint"] = models
        except Exception as e:
            out["failures"].append({"step": "models", "error": repr(e), "tb": traceback.format_exc()[-2000:]})

        try:
            chat_r = await chat(
                client, MODEL,
                [{"role": "user", "content": "Say hello in one short sentence."}],
                max_tokens=128,
            )
            out["chat"] = chat_r
            out["chat_usage_verbatim"] = (chat_r.get("body") or {}).get("usage")
        except Exception as e:
            out["failures"].append({"step": "chat", "error": repr(e), "tb": traceback.format_exc()[-3000:]})

        try:
            tool_r = await chat(
                client, MODEL,
                [{"role": "user", "content": "What is the weather in Boston right now?"}],
                tools=TOOLS,
                max_tokens=256,
            )
            out["tool_call"] = tool_r
            out["tool_usage_verbatim"] = (tool_r.get("body") or {}).get("usage")
        except Exception as e:
            out["failures"].append({"step": "tool_call", "error": repr(e), "tb": traceback.format_exc()[-3000:]})

        try:
            out["stream_ttft"] = await chat(
                client, MODEL,
                [{"role": "user", "content": "Count from 1 to 8, comma-separated."}],
                stream=True,
                max_tokens=64,
            )
        except Exception as e:
            out["failures"].append({"step": "stream_ttft", "error": repr(e), "tb": traceback.format_exc()[-3000:]})

        try:
            out["concurrency_1"] = await measure_conc(client, 1, max_tokens=32)
        except Exception as e:
            out["failures"].append({"step": "conc1", "error": repr(e), "tb": traceback.format_exc()[-2000:]})
        try:
            out["concurrency_16"] = await measure_conc(client, 16, max_tokens=32)
        except Exception as e:
            out["failures"].append({"step": "conc16", "error": repr(e), "tb": traceback.format_exc()[-2000:]})

        # Dynamic LoRA load
        adapter = Path(ADAPTER)
        out["adapter_path"] = str(adapter)
        out["adapter_exists"] = adapter.exists()
        out["adapter_files"] = sorted(p.name for p in adapter.iterdir()) if adapter.exists() else []
        if adapter.exists():
            try:
                r = await client.post(
                    f"{BASE}/load_lora_adapter",
                    json={"lora_name": "smoke_lora", "lora_path": str(adapter)},
                    timeout=120.0,
                )
                out["lora_load"] = {
                    "status": r.status_code,
                    "text": r.text[:4000],
                    "via": "POST /v1/load_lora_adapter",
                }
            except Exception as e:
                out["failures"].append({"step": "lora_load", "error": repr(e), "tb": traceback.format_exc()[-3000:]})
                out["lora_load"] = {"ok": False, "error": repr(e)}

            # request routed to adapter
            try:
                lora_r = await chat(
                    client, "smoke_lora",
                    [{"role": "user", "content": "Reply with the single word adapter."}],
                    max_tokens=64,
                )
                out["lora_chat"] = lora_r
                out["lora_chat_usage_verbatim"] = (lora_r.get("body") or {}).get("usage")
                body = lora_r.get("body") or {}
                text = ""
                try:
                    text = body["choices"][0]["message"].get("content") or ""
                except Exception:
                    text = str(body)[:500]
                out["lora_chat_text"] = text
                out["lora_served"] = lora_r.get("status") == 200 and bool(text)
            except Exception as e:
                out["failures"].append({"step": "lora_chat", "error": repr(e), "tb": traceback.format_exc()[-3000:]})
                out["lora_served"] = False
        else:
            out["lora_served"] = False
            out["failures"].append({"step": "adapter_missing", "error": f"no adapter at {adapter}"})

    out["gpu_end"] = gpu()
    path = LOGDIR / "g3_probe.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(path.read_text()[:12000])

asyncio.run(main())
PY
PROBE_RC=$?

# If dynamic LoRA failed, restart with --lora-modules
if [[ -d "${ADAPTER}" ]]; then
  LORA_OK=$("${VENV}/bin/python" -c "import json; print(json.load(open('${PROBE_JSON}')).get('lora_served', False))" 2>/dev/null || echo False)
  if [[ "${LORA_OK}" != "True" ]]; then
    echo "[g3_serve] dynamic LoRA did not serve; restarting with --lora-modules" | tee -a "${FLAG_LOG}"
    kill_vllm
    # shellcheck disable=SC2206
    extra=( ${WORKING_FLAGS} )
    start_vllm "${COMMON[@]}" "${extra[@]}" --lora-modules "smoke_lora=${ADAPTER}"
    if wait_ready 700; then
      "${VENV}/bin/python" - <<'PY'
import json, os, time
from pathlib import Path
import httpx
BASE = f"http://127.0.0.1:{os.environ.get('SIDEKICK_VLLM_PORT','8000')}/v1"
LOGDIR = Path("/scratch/n12194778/sidekick/logs")
probe = json.loads((LOGDIR / "g3_probe.json").read_text()) if (LOGDIR / "g3_probe.json").exists() else {}
with httpx.Client(timeout=180.0) as c:
    r = c.post(f"{BASE}/chat/completions", json={
        "model": "smoke_lora",
        "messages": [{"role": "user", "content": "Reply with the single word adapter."}],
        "max_tokens": 64,
        "temperature": 1.0,
        "top_p": 0.95,
    })
    probe["lora_restart"] = {"status": r.status_code, "body": r.json() if r.headers.get("content-type","").startswith("application/json") else r.text[:4000]}
    body = probe["lora_restart"]["body"]
    text = ""
    if isinstance(body, dict):
        try:
            text = body["choices"][0]["message"].get("content") or ""
        except Exception:
            text = str(body)[:500]
    probe["lora_restart_text"] = text
    probe["lora_served"] = r.status_code == 200 and bool(text)
    probe["lora_via"] = "restart --lora-modules"
(LOGDIR / "g3_probe.json").write_text(json.dumps(probe, indent=2, default=str))
print("lora_restart", json.dumps(probe.get("lora_restart"), default=str)[:3000])
PY
    else
      echo "[g3_serve] restart with lora-modules failed" | tee -a "${FLAG_LOG}"
      tail -n 80 "${VLLM_LOG}" | tee -a "${FLAG_LOG}"
    fi
  fi
fi

GPU_END=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader 2>/dev/null || true)
"${VENV}/bin/python" - <<PY
import json, os, pathlib
p = pathlib.Path("${SERVE_JSON}")
p.write_text(json.dumps({
    "ok": True,
    "ready": True,
    "host": os.uname().nodename,
    "job": os.environ.get("PBS_JOBID"),
    "model": "${MODEL}",
    "served_name": "${SERVED_NAME}",
    "working_flags": """${WORKING_FLAGS}""",
    "load_s": """${LOAD_S}""",
    "gpu_serve": """${GPU_SERVE}""",
    "gpu_end": """${GPU_END}""",
    "vllm_log": "${VLLM_LOG}",
    "parser": "${PARSER}",
    "probe_rc": ${PROBE_RC},
}, indent=2))
print(p.read_text())
PY

kill_vllm
echo "[g3_serve] done $(date -Iseconds)"
exit 0
