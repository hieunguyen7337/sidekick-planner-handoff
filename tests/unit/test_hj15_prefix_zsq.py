"""Zero-shot Qwen prefix configs and harness adapter resolution tests."""
from __future__ import annotations

import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

from sidekick.agents.planner import MockPlanner
from sidekick.runner import load_config, make_executor, system_kwargs
from sidekick.systems import get_system

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "hj12_prefix.pbs"
ZSQ = {
    6: REPO / "configs" / "hj15_prefix_zsq_m6.yaml",
    9: REPO / "configs" / "hj15_prefix_zsq_m9.yaml",
}
HJ14 = {
    6: REPO / "configs" / "hj14_prefix_m6.yaml",
    9: REPO / "configs" / "hj14_prefix_m9.yaml",
}
BASE_MODEL_GRANITE = "ibm-granite/granite-4.2-8b"
BASE_MODEL_QWEN = "Qwen/Qwen3-8B"
TAILORED_GRANITE_ALIAS = "sft_b_plus"
HANDOFF_GRANITE_ALIAS = "sft_b_plus_handoff"
QWEN_ALIAS = "sft_b_plus_qwen8b"


class _Resp:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "COMPLETE"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


class _Http:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def post(self, url: str, json: dict) -> _Resp:
        self.payloads.append(json)
        return _Resp()


def _served_model(cfg: dict, executor) -> tuple[str, object, object]:
    """Issue one complete() the way run_episode does: lora_name=policy.adapter_name."""
    kw = system_kwargs("prefix_handoff", cfg, "copy_hello", 1)
    system = get_system(
        "prefix_handoff",
        planner=MockPlanner(),
        executor=executor,
        **kw,
    )
    http = _Http()
    executor._http = http
    executor.max_prompt_tokens = None
    _text, usage = executor.complete(
        [{"role": "user", "content": "hi"}],
        lora_name=system.policy.adapter_name,
    )
    assert http.payloads, "executor.complete must POST a payload"
    return http.payloads[0]["model"], usage, system.policy.adapter_name


def test_hj15_prefix_zsq_matches_hj14_except_campaign_id_and_lora_name() -> None:
    for m in (6, 9):
        zsq = load_config(str(ZSQ[m]))
        ref = load_config(str(HJ14[m]))
        assert zsq["campaign_id"] == f"hj15_prefix_zsq_m{m}_20260923"
        assert zsq["executor"]["lora_name"] is None
        assert zsq["executor"]["model"] == BASE_MODEL_QWEN
        assert zsq["handoff"]["m"] == m
        assert ref["campaign_id"] == f"hj14_prefix_m{m}_20260924"
        assert ref["executor"]["lora_name"] == QWEN_ALIAS
        assert ref["executor"]["model"] == BASE_MODEL_QWEN
        zsq_norm = deepcopy(zsq)
        ref_norm = deepcopy(ref)
        zsq_norm["campaign_id"] = ref_norm["campaign_id"]
        zsq_norm["executor"]["lora_name"] = ref_norm["executor"]["lora_name"]
        assert zsq_norm == ref_norm


def test_hj15_prefix_zsq_configs_resolve_to_base_qwen_without_lora() -> None:
    for m, path in ZSQ.items():
        cfg = load_config(str(path))
        assert cfg["executor"]["lora_name"] is None
        assert cfg["executor"]["model"] == BASE_MODEL_QWEN
        ex = make_executor(cfg)
        assert ex.lora_name is None
        assert ex.model == BASE_MODEL_QWEN
        request_model, usage, policy_adapter = _served_model(cfg, ex)
        assert policy_adapter is None
        assert request_model == BASE_MODEL_QWEN
        assert usage.model == BASE_MODEL_QWEN
        assert usage.raw.get("lora_name") is None
        assert request_model != QWEN_ALIAS


def test_hj15_zsq_free_arms_lines_match_existing_format() -> None:
    text = PBS.read_text(encoding="utf-8")
    for m in (6, 9):
        line = (
            f'  "prefix_handoff|${{REPO}}/configs/hj15_prefix_zsq_m{m}.yaml|'
            f'hj15_prefix_zsq_m{m}"'
        )
        assert line in text, line


def _extract(text: str, start: str, end: str, *, include_end: bool = False) -> str:
    i = text.index(start)
    j = text.index(end, i)
    if include_end:
        j += len(end)
    return text[i:j]


def _peft_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "adapter_config.json").write_text("{}\n", encoding="utf-8")
    (path / "adapter_model.safetensors").write_bytes(b"x")
    return path


def _run_group_register(
    tmp_path: Path,
    stems: list[str],
    *,
    model: str = BASE_MODEL_QWEN,
    create_qwen_adapter: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute the PBS group-assembly + register_lora block against tmp adapter paths."""
    text = PBS.read_text(encoding="utf-8")
    register_fn = _extract(text, "register_lora () {", "hj12_executor_fields () {")
    fields_fn = _extract(text, "hj12_executor_fields () {", "hj12_alias_adapter_for_model () {")
    alias_fn = _extract(
        text, "hj12_alias_adapter_for_model () {", "hj12_hf_home_for_model () {"
    )
    block = _extract(
        text,
        "  LORA_MODULES=()\n  GROUP_ARMS=()\n",
        '  echo "[hj12] lora count ${#LORA_MODULES[@]} <= max-loras ${MAX_LORAS}"\n',
        include_end=True,
    )
    sft_dir = _peft_dir(tmp_path / "sft_b_plus")
    handoff_dir = tmp_path / "sft_b_plus_handoff"  # deliberately not created
    qwen_dir = tmp_path / "sft_b_plus_iaware_qwen8b"
    if create_qwen_adapter:
        _peft_dir(qwen_dir)

    arms_lines = "\n".join(
        f'  PENDING_ARMS+=("prefix_handoff|${{REPO}}/configs/{stem}.yaml|{stem}")'
        for stem in stems
    )
    header = "\n".join(
        [
            "#!/bin/bash",
            f"REPO={REPO}",
            f"PY={sys.executable}",
            f'MODEL_GRANITE="{BASE_MODEL_GRANITE}"',
            f'MODEL_QWEN="{BASE_MODEL_QWEN}"',
            f'MODEL="{model}"',
            f'ALIAS_SFT_B_PLUS="{TAILORED_GRANITE_ALIAS}"',
            f'ADAPTER_SFT_B_PLUS="{sft_dir}"',
            f'ALIAS_SFT_B_PLUS_HANDOFF="{HANDOFF_GRANITE_ALIAS}"',
            f'ADAPTER_SFT_B_PLUS_HANDOFF="{handoff_dir}"',
            f'ALIAS_SFT_B_PLUS_QWEN="{QWEN_ALIAS}"',
            f'ADAPTER_SFT_B_PLUS_QWEN="{qwen_dir}"',
            "MAX_LORAS=4",
            "",
        ]
    )
    footer = (
        'hj12_alias_adapter_for_model "${MODEL}"\n'
        "PENDING_ARMS=()\n"
        + arms_lines
        + "\n"
        + block
        + 'echo "[hj12] test LORA_MODULES=${LORA_MODULES[*]}"\n'
    )
    script = tmp_path / "register_group.sh"
    script.write_text(
        header + register_fn + fields_fn + alias_fn + footer,
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    return subprocess.run(
        ["timeout", "60", "bash", str(script)],
        cwd=str(REPO),
        env=env,
        text=True,
        capture_output=True,
    )


def test_qwen_zero_shot_group_does_not_require_qwen_adapter(tmp_path: Path) -> None:
    proc = _run_group_register(
        tmp_path, ["hj15_prefix_zsq_m6", "hj15_prefix_zsq_m9"], model=BASE_MODEL_QWEN
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"lora-module {QWEN_ALIAS}=" not in out, out
    assert f"FATAL: adapter path for alias {QWEN_ALIAS}" not in out, out
    assert "[hj12] test LORA_MODULES=" in out, out


def test_qwen_group_containing_hj14_prefix_m6_missing_adapter_is_fatal(tmp_path: Path) -> None:
    proc = _run_group_register(
        tmp_path, ["hj15_prefix_zsq_m6", "hj14_prefix_m6"], model=BASE_MODEL_QWEN
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert f"FATAL: adapter path for alias {QWEN_ALIAS} is not a directory" in out, out
    assert f"lora-module {QWEN_ALIAS}=" not in out, out


def test_qwen_group_containing_hj14_prefix_m6_with_adapter_succeeds(tmp_path: Path) -> None:
    proc = _run_group_register(
        tmp_path,
        ["hj15_prefix_zsq_m6", "hj14_prefix_m6"],
        model=BASE_MODEL_QWEN,
        create_qwen_adapter=True,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"lora-module {QWEN_ALIAS}=" in out, out
    assert f"test LORA_MODULES={QWEN_ALIAS}=" in out, out
