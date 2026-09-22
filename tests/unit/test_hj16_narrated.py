"""Unit tests for HJ-16 narrated prefix generation, configs, and harness integration."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import pytest

from _pbs_arrays import read_bash_array
from sidekick.agents.planner import CachedPacketPlanner, MockPlanner
from sidekick.environments.mock_env import MockEnv
from sidekick.prefix_source import build_handoff_prefix
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction, PlanStep, Usage
from sidekick.runner import load_config, make_executor, system_kwargs
from sidekick.systems import get_system
import scripts.analysis.hj16_narrate_prefix as hj16_narrate

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "hj12_prefix.pbs"
TEMPLATE_CONFIG = REPO / "configs" / "hj8_sft_plan_bplus.yaml"

CONFIG_PATHS = {
    "zs_m9": REPO / "configs" / "hj16_narrated_m9_zs.yaml",
    "obs_zs_m9": REPO / "configs" / "hj16_narrated_obs_m9_zs.yaml",
    "bplus_m9": REPO / "configs" / "hj16_narrated_m9_bplus.yaml",
    "obs_bplus_m9": REPO / "configs" / "hj16_narrated_obs_m9_bplus.yaml",
}

CURVE_CONFIG_PATHS = {
    "zs_m6": REPO / "configs" / "hj16_narrated_m6_zs.yaml",
    "bplus_m6": REPO / "configs" / "hj16_narrated_m6_bplus.yaml",
    "zs_m11": REPO / "configs" / "hj16_narrated_m11_zs.yaml",
    "bplus_m11": REPO / "configs" / "hj16_narrated_m11_bplus.yaml",
}

BASE_MODEL_GRANITE = "ibm-granite/granite-4.2-8b"
LORA_ALIAS_BPLUS = "sft_b_plus"
TASK_ID = "copy_hello"
SEED = 1
SOURCE_SYSTEM = "planner_alone"
TS = "2026-09-15T12:00:00+00:00"

CODE_ACTIONS = [
    'print(list_files())',
    'print(read("inbox.txt"))',
    'write("outbox.txt", "hello world")',
    'print(read("outbox.txt"))',
]


def _make_source_episode(
    camp_dir: Path,
    *,
    task_id: str = TASK_ID,
    seed: int = SEED,
    system: str = SOURCE_SYSTEM,
    n_code_actions: int = 4,
    include_ask: bool = True,
    end_complete: bool = True,
) -> Path:
    dest = camp_dir / system / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    world = MockEnv()
    reset_obs = world.reset(task_id, seed)

    orig_packet = DelegationPacket(
        packet_id=f"pkt-{task_id}",
        task_id=task_id,
        goal="Copy inbox.txt to outbox.txt",
        plan_steps=[
            PlanStep(index=1, description="inspect files", expected_outcome="file list", apps=[]),
            PlanStep(index=2, description="perform copy", expected_outcome="copied", apps=[]),
        ],
        constraints=[],
        success_criteria=[],
        forbidden_actions=[],
        context_digest="digest_abc",
        created_at=TS,
    )

    plan_usage = Usage(
        model="gpt-5.6-luna",
        provider="codex",
        input_tokens=1000,
        cached_input_tokens=0,
        output_tokens=100,
        reasoning_output_tokens=20,
    )

    events: list[Event] = [
        Event(
            run_id=f"src/{system}/{seed}/{task_id}",
            task_id=task_id,
            system=system,
            seed=seed,
            step=0,
            ts=TS,
            actor="system",
            event_type="run_start",
            payload={"limits": {}},
            env_state_hash=reset_obs.env_state_hash,
        ),
        Event(
            run_id=f"src/{system}/{seed}/{task_id}",
            task_id=task_id,
            system=system,
            seed=seed,
            step=0,
            ts=TS,
            actor="environment",
            event_type="observation",
            payload={"text": reset_obs.text, "done": False},
            env_state_hash=reset_obs.env_state_hash,
        ),
        Event(
            run_id=f"src/{system}/{seed}/{task_id}",
            task_id=task_id,
            system=system,
            seed=seed,
            step=0,
            ts=TS,
            actor="planner",
            event_type="plan",
            payload={"packet": orig_packet.model_dump(), "model": "gpt-5.6-luna"},
            usage=plan_usage,
        ),
    ]

    step = 0
    if include_ask:
        step += 1
        ask_action = ExecutorAction(kind="ASK_PLANNER", ask_reason="Clarify instructions", raw_output="ASK_PLANNER: Clarify instructions")
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="executor",
                event_type="action",
                payload=ask_action.model_dump(),
            )
        )
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="executor",
                event_type="ask",
                payload={"ask_reason": ask_action.ask_reason, "honoured": True},
            )
        )
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="planner",
                event_type="intervention",
                payload={"correction": "Proceed with copy", "forced": False},
            )
        )

    for i in range(min(n_code_actions, len(CODE_ACTIONS))):
        step += 1
        code = CODE_ACTIONS[i]
        action = ExecutorAction(kind="CODE", code=code, raw_output=code)
        obs = world.step(action)
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="planner",
                event_type="action",
                payload=action.model_dump(),
                usage=Usage(model="gpt-5.6-luna", provider="codex", input_tokens=100, output_tokens=10),
            )
        )
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="environment",
                event_type="observation",
                payload={"text": obs.text, "done": obs.done},
                env_state_hash=obs.env_state_hash,
            )
        )

    if end_complete:
        step += 1
        complete_act = ExecutorAction(kind="COMPLETE", message="Task finished successfully", raw_output="COMPLETE: Task finished successfully")
        obs = world.step(complete_act)
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="planner",
                event_type="action",
                payload=complete_act.model_dump(),
                usage=Usage(model="gpt-5.6-luna", provider="codex", input_tokens=50, output_tokens=5),
            )
        )
        events.append(
            Event(
                run_id=f"src/{system}/{seed}/{task_id}",
                task_id=task_id,
                system=system,
                seed=seed,
                step=step,
                ts=TS,
                actor="environment",
                event_type="observation",
                payload={"text": obs.text, "done": True},
                env_state_hash=obs.env_state_hash,
            )
        )

    world.close()
    events_path = dest / "events.jsonl"
    events_path.write_text("".join(e.model_dump_json() + "\n" for e in events), encoding="utf-8")
    return events_path


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
    kw = system_kwargs(system_name, cfg, TASK_ID, SEED)
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


def test_action_selection_parity(tmp_path: Path) -> None:
    camp = tmp_path / "camp"
    _make_source_episode(camp, n_code_actions=4, include_ask=True, end_complete=True)

    out = tmp_path / "out_m3"
    rc = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--source-system", SOURCE_SYSTEM,
        "--m", "3",
        "--seeds", str(SEED),
        "--out", str(out),
    ])
    assert rc == 0

    handoff = build_handoff_prefix(
        source_campaign=camp,
        source_system=SOURCE_SYSTEM,
        task_id=TASK_ID,
        seed=SEED,
        m=3,
        env=MockEnv(),
    )
    assert handoff.effective_m == 3

    # Load narrated packet
    events_file = out / SOURCE_SYSTEM / str(SEED) / TASK_ID / "events.jsonl"
    lines = events_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    plan_event = json.loads(lines[1])
    narrated_packet = DelegationPacket.model_validate(plan_event["payload"]["packet"])

    # 2 original + 3 narrated steps
    assert len(narrated_packet.plan_steps) == 5
    appended_steps = narrated_packet.plan_steps[2:]
    assert len(appended_steps) == 3

    # Verify that the 3 actions in the packet match build_handoff_prefix's actions
    assert handoff.prefix is not None
    replayed_actions = [
        ExecutorAction.model_validate(e.payload)
        for e in handoff.prefix.events
        if e.event_type == "action" and (e.payload or {}).get("kind") in ("CODE", "COMPLETE")
    ]
    assert len(replayed_actions) == 3

    for k, (step_obj, act) in enumerate(zip(appended_steps, replayed_actions), start=1):
        assert step_obj.index == 2 + k
        if act.kind == "CODE":
            assert act.code in step_obj.description
            assert f"step {k} of 3" in step_obj.description
        else:
            assert "COMPLETE" in step_obj.description


def test_cached_packet_planner_loading(tmp_path: Path) -> None:
    camp = tmp_path / "camp"
    _make_source_episode(camp, n_code_actions=4, include_ask=True, end_complete=True)

    out = tmp_path / "packets"
    rc = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--source-system", SOURCE_SYSTEM,
        "--m", "3",
        "--seeds", str(SEED),
        "--out", str(out),
    ])
    assert rc == 0

    planner = CachedPacketPlanner(
        inner=MockPlanner(),
        packet_source=out,
        system=SOURCE_SYSTEM,
        seed=SEED,
        on_missing="fail",
    )
    resp = planner.plan(TASK_ID, "goal", "context")
    assert resp.packet is not None
    assert len(resp.packet.plan_steps) == 5
    assert resp.packet.plan_steps[0].index == 1
    assert resp.packet.plan_steps[0].description == "inspect files"
    assert resp.packet.plan_steps[1].index == 2
    assert resp.packet.plan_steps[1].description == "perform copy"
    assert resp.usage.model == "gpt-5.6-luna"
    assert resp.usage.provider == "cache"


def test_with_observations_flag(tmp_path: Path) -> None:
    camp = tmp_path / "camp"
    _make_source_episode(camp, n_code_actions=2, include_ask=False, end_complete=False)

    out_no_obs = tmp_path / "out_no_obs"
    rc1 = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--source-system", SOURCE_SYSTEM,
        "--m", "2",
        "--seeds", str(SEED),
        "--out", str(out_no_obs),
    ])
    assert rc1 == 0

    out_with_obs = tmp_path / "out_with_obs"
    rc2 = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--source-system", SOURCE_SYSTEM,
        "--m", "2",
        "--seeds", str(SEED),
        "--with-observations",
        "--out", str(out_with_obs),
    ])
    assert rc2 == 0

    # Without observations: expected_outcome is empty string
    p1 = json.loads((out_no_obs / SOURCE_SYSTEM / str(SEED) / TASK_ID / "events.jsonl").read_text(encoding="utf-8").splitlines()[1])
    pkt1 = DelegationPacket.model_validate(p1["payload"]["packet"])
    for step in pkt1.plan_steps[2:]:
        assert step.expected_outcome == ""

    # With observations: expected_outcome is non-empty
    p2 = json.loads((out_with_obs / SOURCE_SYSTEM / str(SEED) / TASK_ID / "events.jsonl").read_text(encoding="utf-8").splitlines()[1])
    pkt2 = DelegationPacket.model_validate(p2["payload"]["packet"])
    for step in pkt2.plan_steps[2:]:
        assert step.expected_outcome != ""


def test_effective_m_short_prefix_and_manifest(tmp_path: Path) -> None:
    camp = tmp_path / "camp"
    # Create source with only 2 CODE actions (total 2 executed actions)
    _make_source_episode(camp, n_code_actions=2, include_ask=False, end_complete=False)

    out = tmp_path / "out_short"
    rc = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--source-system", SOURCE_SYSTEM,
        "--m", "9",
        "--seeds", str(SEED),
        "--out", str(out),
    ])
    assert rc == 0

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["n_short_prefix"] == 1
    assert manifest["m"] == 9
    assert manifest["per_seed_counts"][str(SEED)] == 1

    p = json.loads((out / SOURCE_SYSTEM / str(SEED) / TASK_ID / "events.jsonl").read_text(encoding="utf-8").splitlines()[1])
    pkt = DelegationPacket.model_validate(p["payload"]["packet"])
    # 2 original + 2 effective = 4 steps (clamped from 9)
    assert len(pkt.plan_steps) == 4
    assert p["payload"]["narrated_m"] == 2


def test_hj16_configs_diff_and_lora_resolution() -> None:
    template = load_config(str(TEMPLATE_CONFIG))

    for key, path in CONFIG_PATHS.items():
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        assert cfg["env"] == "appworld"
        assert cfg["limits"] == template["limits"]
        assert cfg["prices"] == template["prices"]
        assert cfg["planner"]["type"] == template["planner"]["type"]
        assert cfg["planner"]["model"] == template["planner"]["model"]
        assert cfg["planner"]["on_missing"] == "fail"
        assert cfg["planner"]["packet_system"] == "planner_alone"
        assert cfg["executor"]["type"] == "vllm"
        assert cfg["executor"]["model"] == BASE_MODEL_GRANITE

        if "zs" in key:
            assert cfg["executor"]["lora_name"] is None
            ex = make_executor(cfg)
            assert ex.lora_name is None
            assert ex.model == BASE_MODEL_GRANITE
            model_sent, usage, adapter_name = _served_model("prompt_only", cfg, ex)
            assert adapter_name is None
            assert model_sent == BASE_MODEL_GRANITE
            assert usage.model == BASE_MODEL_GRANITE
            assert usage.raw.get("lora_name") is None
        else:
            assert cfg["executor"]["lora_name"] == LORA_ALIAS_BPLUS
            ex = make_executor(cfg)
            assert ex.lora_name == LORA_ALIAS_BPLUS
            assert ex.model == BASE_MODEL_GRANITE
            model_sent, usage, adapter_name = _served_model("sft_plan", cfg, ex)
            assert adapter_name == LORA_ALIAS_BPLUS
            assert model_sent == LORA_ALIAS_BPLUS
            assert usage.model == LORA_ALIAS_BPLUS
            assert usage.raw.get("lora_name") == LORA_ALIAS_BPLUS

        if "obs" in key:
            assert "hj16_narrated_obs_m9" in cfg["planner"]["packet_source"]
        else:
            assert "hj16_narrated_m9" in cfg["planner"]["packet_source"]


def test_zs_config_under_sft_plan_would_request_phantom_alias() -> None:
    for key in ("zs_m9", "obs_zs_m9"):
        cfg = load_config(str(CONFIG_PATHS[key]))
        ex = make_executor(cfg)
        model_sent, _usage, adapter_name = _served_model("sft_plan", cfg, ex)
        assert adapter_name == "sft_plan"
        assert model_sent == "sft_plan"


def test_out_under_scratch_results_and_heldout_splits_refused(tmp_path: Path) -> None:
    camp = tmp_path / "camp"
    _make_source_episode(camp, n_code_actions=1, include_ask=False, end_complete=False)

    # 1. Under /scratch/n12194778/sidekick/results
    rc1 = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--m", "1",
        "--seeds", str(SEED),
        "--out", "/scratch/n12194778/sidekick/results/forbidden_narrated",
    ])
    assert rc1 != 0

    # 2. Path containing test_normal
    rc2 = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--m", "1",
        "--seeds", str(SEED),
        "--out", str(tmp_path / "test_normal_packets"),
    ])
    assert rc2 != 0

    # 3. Path containing test_challenge
    rc3 = hj16_narrate.main([
        "--source-campaign", str(camp),
        "--m", "1",
        "--seeds", str(SEED),
        "--out", str(tmp_path / "test_challenge_packets"),
    ])
    assert rc3 != 0


def test_pbs_free_arms_lines() -> None:
    text = PBS.read_text(encoding="utf-8")
    expected_lines = [
        '  "prompt_only|${REPO}/configs/hj16_narrated_m9_zs.yaml|hj16_narrated_m9_zs"',
        '  "prompt_only|${REPO}/configs/hj16_narrated_obs_m9_zs.yaml|hj16_narrated_obs_m9_zs"',
        '  "sft_plan|${REPO}/configs/hj16_narrated_m9_bplus.yaml|hj16_narrated_m9_bplus"',
        '  "sft_plan|${REPO}/configs/hj16_narrated_obs_m9_bplus.yaml|hj16_narrated_obs_m9_bplus"',
    ]
    for line in expected_lines:
        assert line in text, f"Line missing from {PBS}:\n{line}"


def test_narrated_curve_configs_point_at_their_own_packet_dir() -> None:
    for key, path in CURVE_CONFIG_PATHS.items():
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        packet_source = Path(cfg["planner"]["packet_source"])
        m_tag = "m6" if "m6" in key else "m11"
        assert packet_source.name == f"hj16_narrated_{m_tag}", f"Expected packet source ending in hj16_narrated_{m_tag}, got {packet_source}"
        assert packet_source.is_dir(), f"Packet directory {packet_source} must exist"


def test_narrated_curve_untailored_runs_under_prompt_only() -> None:
    arms = {}
    for line in read_bash_array(PBS, "FREE_ARMS"):
        parts = line.split("|")
        assert len(parts) == 3, f"malformed FREE_ARMS entry: {line}"
        arms[parts[2]] = (parts[0], parts[1])

    for m in (6, 11):
        zs_stem = f"hj16_narrated_m{m}_zs"
        bplus_stem = f"hj16_narrated_m{m}_bplus"
        assert zs_stem in arms, f"{zs_stem} not in FREE_ARMS"
        assert arms[zs_stem][0] == "prompt_only", f"{zs_stem} must run under prompt_only, got {arms[zs_stem][0]}"
        assert bplus_stem in arms, f"{bplus_stem} not in FREE_ARMS"
        assert arms[bplus_stem][0] == "sft_plan", f"{bplus_stem} must run under sft_plan, got {arms[bplus_stem][0]}"


def test_narrated_curve_configs_have_expected_lora() -> None:
    for key, path in CURVE_CONFIG_PATHS.items():
        assert path.is_file(), f"Config {path} must exist"
        cfg = load_config(str(path))
        if "zs" in key:
            assert cfg["executor"]["lora_name"] is None
            ex = make_executor(cfg)
            assert ex.lora_name is None
            assert ex.model == BASE_MODEL_GRANITE
            model_sent, usage, adapter_name = _served_model("prompt_only", cfg, ex)
            assert adapter_name is None
            assert model_sent == BASE_MODEL_GRANITE
            assert usage.model == BASE_MODEL_GRANITE
            assert usage.raw.get("lora_name") is None
        else:
            assert cfg["executor"]["lora_name"] == LORA_ALIAS_BPLUS
            ex = make_executor(cfg)
            assert ex.lora_name == LORA_ALIAS_BPLUS
            assert ex.model == BASE_MODEL_GRANITE
            model_sent, usage, adapter_name = _served_model("sft_plan", cfg, ex)
            assert adapter_name == LORA_ALIAS_BPLUS
            assert model_sent == LORA_ALIAS_BPLUS
            assert usage.model == LORA_ALIAS_BPLUS
            assert usage.raw.get("lora_name") == LORA_ALIAS_BPLUS

