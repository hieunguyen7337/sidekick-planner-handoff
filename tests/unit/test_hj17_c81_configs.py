"""Unit tests for HJ-15 Qwen zero-shot configs, HJ-17 cap-81 configs, and FREE_ARMS registration."""
from __future__ import annotations

from pathlib import Path
import pytest

from _pbs_arrays import read_bash_array
from sidekick.agents.planner import MockPlanner
from sidekick.runner import load_config, make_executor, system_kwargs
from sidekick.systems import get_system

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "hj12_prefix.pbs"
CAP81_CAMPAIGN = "/scratch/n12194778/sidekick/results/hj13_planner_alone_cap81_20260923"

HJ17_CONFIG_PATHS = {
    "zs_m6": (REPO / "configs" / "hj17_prefix_c81_zs_m6.yaml", 6),
    "zs_m9": (REPO / "configs" / "hj17_prefix_c81_zs_m9.yaml", 9),
    "zs_m11": (REPO / "configs" / "hj17_prefix_c81_zs_m11.yaml", 11),
    "bplus_m6": (REPO / "configs" / "hj17_prefix_c81_bplus_m6.yaml", 6),
    "bplus_m9": (REPO / "configs" / "hj17_prefix_c81_bplus_m9.yaml", 9),
    "bplus_m11": (REPO / "configs" / "hj17_prefix_c81_bplus_m11.yaml", 11),
}

HJ15_NEW_CONFIGS = [
    REPO / "configs" / "hj15_prefix_zsq_m11.yaml",
    REPO / "configs" / "hj15_executor_alone_zsq.yaml",
    REPO / "configs" / "hj15_prompt_only_zsq.yaml",
]


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


def _served_model(system_name: str, cfg: dict, executor) -> tuple[str, object, object]:
    """Issue one complete() the way run_episode does: lora_name=policy.adapter_name."""
    kw = system_kwargs(system_name, cfg, "copy_hello", 1)
    system = get_system(
        system_name,
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


def test_c81_configs_point_at_the_cap81_campaign() -> None:
    assert Path(CAP81_CAMPAIGN).exists(), f"Cap-81 campaign path {CAP81_CAMPAIGN} does not exist"
    for name, (path, _m) in HJ17_CONFIG_PATHS.items():
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        assert cfg["handoff"]["source_campaign"] == CAP81_CAMPAIGN, f"{path} source_campaign mismatch"
        assert cfg["planner"]["packet_source"] == CAP81_CAMPAIGN, f"{path} packet_source mismatch"


def test_c81_configs_preserve_template_m() -> None:
    for name, (path, expected_m) in HJ17_CONFIG_PATHS.items():
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        assert cfg["handoff"]["m"] == expected_m, f"{path} handoff.m expected {expected_m}, got {cfg['handoff']['m']}"


def test_qwen_zeroshot_configs_have_null_lora() -> None:
    for path in HJ15_NEW_CONFIGS:
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        assert cfg["executor"]["lora_name"] is None, f"{path} executor.lora_name should be None"
        assert cfg["executor"]["model"] == "Qwen/Qwen3-8B", f"{path} executor.model should be Qwen/Qwen3-8B"


def test_untailored_qwen_plan_arm_is_not_registered_under_sft_plan() -> None:
    lines = read_bash_array(PBS, "FREE_ARMS")
    qwen_lines = [l for l in lines if "hj15_prompt_only_zsq" in l]
    assert len(qwen_lines) == 1, f"Expected 1 FREE_ARMS line for hj15_prompt_only_zsq, found {len(qwen_lines)}"
    assert qwen_lines[0].startswith("prompt_only|"), f"hj15_prompt_only_zsq line must start with prompt_only|, got: {qwen_lines[0]}"

    cfg_path = REPO / "configs" / "hj15_prompt_only_zsq.yaml"
    cfg = load_config(str(cfg_path))
    ex = make_executor(cfg)
    model_sent, usage, adapter_name = _served_model("prompt_only", cfg, ex)
    assert adapter_name is None
    assert model_sent == "Qwen/Qwen3-8B"
    assert usage.model == "Qwen/Qwen3-8B"

    ex_sft = make_executor(cfg)
    model_sent_sft, _usage, adapter_name_sft = _served_model("sft_plan", cfg, ex_sft)
    assert adapter_name_sft == "sft_plan"
    assert model_sent_sft == "sft_plan"


def test_all_free_arms_configs_exist() -> None:
    lines = read_bash_array(PBS, "FREE_ARMS")
    assert len(lines) > 0, "No entries in FREE_ARMS"
    for line in lines:
        parts = line.split("|")
        assert len(parts) == 3, f"Line malformed in FREE_ARMS: {line}"
        system, raw_cfg_path, arm_name = parts
        cfg_path_str = raw_cfg_path.replace("${REPO}", str(REPO))
        p = Path(cfg_path_str)
        assert p.is_file(), f"Config path {p} for arm {arm_name} does not exist"
