"""Zero-shot prefix configs must serve the base model, not the sft_b_plus alias."""
from __future__ import annotations

from pathlib import Path

from sidekick.agents.planner import MockPlanner
from sidekick.runner import load_config, make_executor, system_kwargs
from sidekick.systems import get_system

REPO = Path(__file__).resolve().parents[2]
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
BASE_MODEL = "ibm-granite/granite-4.2-8b"
ADAPTER_ALIAS = "sft_b_plus"


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


def _served_model(cfg: dict, executor) -> tuple[str, object, dict]:
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
    # Budget fitting loads the granite tokenizer; this test is about the model id.
    executor.max_prompt_tokens = None
    _text, usage = executor.complete(
        [{"role": "user", "content": "hi"}],
        lora_name=system.policy.adapter_name,
    )
    assert http.payloads, "executor.complete must POST a payload"
    return http.payloads[0]["model"], usage, system.policy.adapter_name


def test_zero_shot_configs_resolve_to_base_not_sft_b_plus_alias() -> None:
    for m, path in ZS.items():
        cfg = load_config(str(path))
        assert cfg["campaign_id"] == f"hj13_prefix_zs_m{m}_20260923"
        assert cfg["handoff"]["m"] == m
        assert cfg["executor"]["lora_name"] is None
        ex = make_executor(cfg)
        assert ex.lora_name is None
        assert ex.model == BASE_MODEL
        request_model, usage, policy_adapter = _served_model(cfg, ex)
        assert policy_adapter is None
        assert request_model == BASE_MODEL
        assert usage.model == BASE_MODEL
        assert usage.raw.get("lora_name") is None
        assert request_model != ADAPTER_ALIAS
        assert usage.model != ADAPTER_ALIAS


def test_tailored_prefix_configs_resolve_to_sft_b_plus_alias() -> None:
    for m, path in TAILORED.items():
        cfg = load_config(str(path))
        assert cfg["executor"]["lora_name"] == ADAPTER_ALIAS
        ex = make_executor(cfg)
        assert ex.lora_name == ADAPTER_ALIAS
        request_model, usage, policy_adapter = _served_model(cfg, ex)
        assert policy_adapter == ADAPTER_ALIAS
        assert request_model == ADAPTER_ALIAS
        assert usage.model == ADAPTER_ALIAS
        assert usage.raw.get("lora_name") == ADAPTER_ALIAS
        assert request_model != BASE_MODEL


def test_zero_shot_and_tailored_are_distinguished_on_the_request_model() -> None:
    zs = make_executor(load_config(str(ZS[6])))
    tailored = make_executor(load_config(str(TAILORED[6])))
    zs_model, zs_usage, _ = _served_model(load_config(str(ZS[6])), zs)
    t_model, t_usage, _ = _served_model(load_config(str(TAILORED[6])), tailored)
    assert zs_model != t_model
    assert zs_usage.raw.get("lora_name") != t_usage.raw.get("lora_name")
    assert (zs_model, t_model) == (BASE_MODEL, ADAPTER_ALIAS)
