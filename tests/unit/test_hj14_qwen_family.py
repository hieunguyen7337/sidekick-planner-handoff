"""HJ-14 Qwen3-8B confirmatory arms: configs, alias, FREE_ARMS."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.planner import MockPlanner
from sidekick.runner import load_config, make_executor, system_kwargs
from sidekick.systems import get_system

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "hj12_prefix.pbs"
QWEN = "Qwen/Qwen3-8B"
ALIAS = "sft_b_plus_qwen8b"
PREFIX_MS = (2, 4, 6, 7, 8, 9, 10, 11)
ADAPTER_PATH = "/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_iaware_qwen8b"


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


def test_hj14_prefix_configs_resolve_to_qwen_alias() -> None:
    for m in PREFIX_MS:
        path = REPO / "configs" / f"hj14_prefix_m{m}.yaml"
        cfg = load_config(str(path))
        assert cfg["campaign_id"] == f"hj14_prefix_m{m}_20260924"
        assert cfg["handoff"]["m"] == m
        ex = cfg["executor"]
        assert ex["model"] == QWEN
        assert ex["lora_name"] == ALIAS
        executor = make_executor(cfg)
        assert executor.model == QWEN
        assert executor.lora_name == ALIAS
        request_model, usage, policy_adapter = _served_model("prefix_handoff", cfg, executor)
        assert policy_adapter == ALIAS
        assert request_model == ALIAS
        assert usage.model == ALIAS
        assert usage.raw.get("lora_name") == ALIAS
        assert request_model != QWEN


def test_hj14_executor_alone_and_sft_plan_resolve_to_qwen_alias() -> None:
    alone = load_config(str(REPO / "configs" / "hj14_executor_alone.yaml"))
    plan = load_config(str(REPO / "configs" / "hj14_sft_plan.yaml"))
    assert alone["campaign_id"] == "hj14_executor_alone_20260924"
    assert plan["campaign_id"] == "hj14_sft_plan_20260924"
    for cfg, system_name, expect_policy_alias in (
        (alone, "executor_alone", None),
        (plan, "sft_plan", ALIAS),
    ):
        assert cfg["executor"]["model"] == QWEN
        assert cfg["executor"]["lora_name"] == ALIAS
        executor = make_executor(cfg)
        assert executor.model == QWEN
        assert executor.lora_name == ALIAS
        request_model, usage, policy_adapter = _served_model(system_name, cfg, executor)
        assert policy_adapter == expect_policy_alias
        # complete() still sends the YAML lora_name when policy.adapter_name is None.
        expected_request = expect_policy_alias or ALIAS
        assert request_model == expected_request
        assert usage.raw.get("lora_name") == ALIAS


def test_hj14_pbs_registers_qwen_alias_and_adapter() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert f'ALIAS_SFT_B_PLUS_QWEN="${{ALIAS_SFT_B_PLUS_QWEN:-{ALIAS}}}"' in text
    assert ADAPTER_PATH in text
    assert 'MODEL_QWEN="${MODEL_QWEN:-Qwen/Qwen3-8B}"' in text
    assert "serving_record base_model=" in text


def test_hj14_free_arms_lines_match_existing_format() -> None:
    text = PBS.read_text(encoding="utf-8")
    expected = [
        '  "executor_alone|${REPO}/configs/hj14_executor_alone.yaml|hj14_executor_alone"',
        '  "sft_plan|${REPO}/configs/hj14_sft_plan.yaml|hj14_sft_plan"',
    ]
    expected += [
        f'  "prefix_handoff|${{REPO}}/configs/hj14_prefix_m{m}.yaml|hj14_prefix_m{m}"'
        for m in PREFIX_MS
    ]
    for line in expected:
        assert line in text, line


def test_hj12_granite_configs_untouched() -> None:
    cfg = load_config(str(REPO / "configs" / "hj12_prefix_m9.yaml"))
    assert cfg["campaign_id"] == "hj12_prefix_m9_20260922"
    assert cfg["executor"]["model"] == "ibm-granite/granite-4.2-8b"
    assert cfg["executor"]["lora_name"] == "sft_b_plus"
