"""Handoff-specialised prefix configs: field-equal to hj12 except adapter alias."""
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
ZS = {
    6: REPO / "configs" / "hj13_prefix_zs_m6.yaml",
    9: REPO / "configs" / "hj13_prefix_zs_m9.yaml",
    11: REPO / "configs" / "hj13_prefix_zs_m11.yaml",
}
TAILORED = {
    6: REPO / "configs" / "hj12_prefix_m6.yaml",
    9: REPO / "configs" / "hj12_prefix_m9.yaml",
    11: REPO / "configs" / "hj12_prefix_m11.yaml",
}
HANDOFF = {
    6: REPO / "configs" / "hj13_prefix_hf_m6.yaml",
    9: REPO / "configs" / "hj13_prefix_hf_m9.yaml",
    11: REPO / "configs" / "hj13_prefix_hf_m11.yaml",
}
BASE_MODEL = "ibm-granite/granite-4.2-8b"
TAILORED_ALIAS = "sft_b_plus"
HANDOFF_ALIAS = "sft_b_plus_handoff"
HANDOFF_ADAPTER = (
    "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_handoff_granite8b"
)


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
    # run_start.payload.policy.adapter_name is this value [loop.py:627].
    return http.payloads[0]["model"], usage, system.policy.adapter_name


def test_hj13_prefix_hf_matches_hj12_except_campaign_id_and_lora_name() -> None:
    for m in (6, 9, 11):
        hf = load_config(str(HANDOFF[m]))
        ref = load_config(str(TAILORED[m]))
        assert hf["campaign_id"] == f"hj13_prefix_hf_m{m}_20260923"
        assert hf["executor"]["lora_name"] == HANDOFF_ALIAS
        assert hf["handoff"]["m"] == m
        assert ref["campaign_id"] == f"hj12_prefix_m{m}_20260922"
        assert ref["executor"]["lora_name"] == TAILORED_ALIAS
        hf_norm = deepcopy(hf)
        ref_norm = deepcopy(ref)
        hf_norm["campaign_id"] = ref_norm["campaign_id"]
        hf_norm["executor"]["lora_name"] = ref_norm["executor"]["lora_name"]
        assert hf_norm == ref_norm


def test_handoff_configs_resolve_to_sft_b_plus_handoff_alias() -> None:
    for m, path in HANDOFF.items():
        cfg = load_config(str(path))
        assert cfg["executor"]["lora_name"] == HANDOFF_ALIAS
        ex = make_executor(cfg)
        assert ex.lora_name == HANDOFF_ALIAS
        request_model, usage, policy_adapter = _served_model(cfg, ex)
        assert policy_adapter == HANDOFF_ALIAS
        assert request_model == HANDOFF_ALIAS
        assert usage.model == HANDOFF_ALIAS
        assert usage.raw.get("lora_name") == HANDOFF_ALIAS
        assert request_model != BASE_MODEL
        assert request_model != TAILORED_ALIAS


def test_three_receivers_are_distinguishable_on_request_model_and_run_start() -> None:
    zs_cfg = load_config(str(ZS[6]))
    tailored_cfg = load_config(str(TAILORED[6]))
    handoff_cfg = load_config(str(HANDOFF[6]))
    zs_model, zs_usage, zs_adapter = _served_model(zs_cfg, make_executor(zs_cfg))
    t_model, t_usage, t_adapter = _served_model(tailored_cfg, make_executor(tailored_cfg))
    h_model, h_usage, h_adapter = _served_model(handoff_cfg, make_executor(handoff_cfg))
    assert (zs_model, t_model, h_model) == (BASE_MODEL, TAILORED_ALIAS, HANDOFF_ALIAS)
    assert (zs_adapter, t_adapter, h_adapter) == (None, TAILORED_ALIAS, HANDOFF_ALIAS)
    assert len({zs_model, t_model, h_model}) == 3
    assert len({zs_adapter, t_adapter, h_adapter}) == 3
    assert zs_usage.raw.get("lora_name") is None
    assert t_usage.raw.get("lora_name") == TAILORED_ALIAS
    assert h_usage.raw.get("lora_name") == HANDOFF_ALIAS


def test_hj13_pbs_registers_handoff_alias_alongside_sft_b_plus() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert (
        f'ALIAS_SFT_B_PLUS_HANDOFF="${{ALIAS_SFT_B_PLUS_HANDOFF:-{HANDOFF_ALIAS}}}"'
        in text
    )
    assert HANDOFF_ADAPTER in text
    assert (
        'register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"'
        in text
    )
    assert 'ALIAS_SFT_B_PLUS="${ALIAS_SFT_B_PLUS:-sft_b_plus}"' in text
    assert "not in served aliases" in text


def test_hj13_hf_free_arms_lines_match_existing_format() -> None:
    text = PBS.read_text(encoding="utf-8")
    for m in (6, 9, 11):
        line = (
            f'  "prefix_handoff|${{REPO}}/configs/hj13_prefix_hf_m{m}.yaml|'
            f'hj13_prefix_hf_m{m}"'
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


def _run_group_register(tmp_path: Path, stems: list[str]) -> subprocess.CompletedProcess[str]:
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
    arms_lines = "\n".join(
        f'  PENDING_ARMS+=("prefix_handoff|${{REPO}}/configs/{stem}.yaml|{stem}")'
        for stem in stems
    )
    header = "\n".join(
        [
            "#!/bin/bash",
            f"REPO={REPO}",
            f"PY={sys.executable}",
            f'MODEL_GRANITE="{BASE_MODEL}"',
            'MODEL_QWEN="Qwen/Qwen3-8B"',
            'MODEL="${MODEL_GRANITE}"',
            f'ALIAS_SFT_B_PLUS="{TAILORED_ALIAS}"',
            f'ADAPTER_SFT_B_PLUS="{sft_dir}"',
            f'ALIAS_SFT_B_PLUS_HANDOFF="{HANDOFF_ALIAS}"',
            f'ADAPTER_SFT_B_PLUS_HANDOFF="{handoff_dir}"',
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


def test_granite_prefix_zs_group_does_not_require_handoff_adapter(tmp_path: Path) -> None:
    proc = _run_group_register(tmp_path, ["hj12_prefix_m6", "hj13_prefix_zs_m6"])
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out
    assert f"lora-module {TAILORED_ALIAS}=" in out, out
    assert f"lora-module {HANDOFF_ALIAS}=" not in out, out
    assert f"FATAL: adapter path for alias {HANDOFF_ALIAS}" not in out, out


def test_granite_hf_group_missing_handoff_adapter_is_fatal(tmp_path: Path) -> None:
    proc = _run_group_register(
        tmp_path, ["hj12_prefix_m6", "hj13_prefix_hf_m6"]
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 2, out
    assert f"FATAL: adapter path for alias {HANDOFF_ALIAS} is not a directory" in out, out
    assert f"lora-module {HANDOFF_ALIAS}=" not in out, out
