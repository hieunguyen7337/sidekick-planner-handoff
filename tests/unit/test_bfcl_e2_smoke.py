"""Wave E dev design, CPU end-to-end smoke (unit BFCL-E2): zero hosted calls, no GPU.

One arm of each kind -- channel (takeover and advise), replay (prefix, both receivers) and plan -- runs through
`python -m sidekick.runner` on 2 BFCL dev entries x seed 1, with `--env bfcl`, the mock planner and the mock
executor. The replay arms replay a planner_alone campaign the mock planner produced in the same tmp dir, as the
real arms replay bfcl_planner_alone_cap81. Each config is the registered one with only `planner.type`, the
executor block (kept `lora_name`) and the source path changed, so the channel, replay and plan keys under test
are the committed ones.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from sidekick import runner
from sidekick.environments.bfcl_env import bfcl_task_ids

REPO = Path(__file__).resolve().parents[2]
SOURCE_CID = "bfcl_planner_alone_cap81_dev_20260924"
REGISTERED_SOURCE = f"/scratch/n12194778/sidekick/results/{SOURCE_CID}"
TASKS = 2
# Six CODE steps before the first COMPLETE, so step 5 (fixed_k = 5) falls inside turn 0 of every entry.
EXEC_SCRIPT = ["```python\nls()\n```"] * 6 + ["COMPLETE"]


def _summarize():
    spec = importlib.util.spec_from_file_location("campaign_summarize", REPO / "scripts/setup/campaign_summarize.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _mock_config(tmp: Path, out: Path, stem: str) -> Path:
    text = (REPO / "configs" / f"bfcl_{stem}.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(text.replace(REGISTERED_SOURCE, str(out / SOURCE_CID)))
    cfg["planner"] = {**cfg["planner"], "type": "mock"}
    executor = cfg["executor"]
    if executor.get("type") == "vllm":
        cfg["executor"] = {"type": "mock", "script": EXEC_SCRIPT, "lora_name": executor.get("lora_name"),
                           "max_prompt_tokens": executor["max_prompt_tokens"]}
    path = tmp / "cfg" / f"bfcl_{stem}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def _run(tmp: Path, out: Path, stem: str, system: str) -> dict[str, list[dict]]:
    """Run the arm; return {task_id: last-attempt events}, after checking every result.json."""
    cid = f"bfcl_{stem}_dev_20260924"
    rc = runner.main(["--system", system, "--split", "dev", "--tasks", str(TASKS), "--seeds", "1",
                      "--env", "bfcl", "--workers", "1", "--config", str(_mock_config(tmp, out, stem)),
                      "--out", str(out), "--campaign-id", cid])
    assert rc == 0
    episodes = {}
    for task in bfcl_task_ids("dev", TASKS):
        ep = out / cid / system / "1" / task
        result = json.loads((ep / "result.json").read_text(encoding="utf-8"))
        assert result["error_type"] is None, (stem, task, result["error_type"])
        events = [json.loads(l) for l in (ep / "events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        starts = [i for i, e in enumerate(events) if e["event_type"] == "run_start"]
        assert len(starts) == 1
        manifest = json.loads((ep / "manifest.json").read_text(encoding="utf-8"))
        assert (manifest["env"], manifest["provenance"]["split"]) == ("bfcl", "dev")
        episodes[task] = events
    return episodes


def _count(events: list[dict], event_type: str, actor: str | None = None) -> int:
    return sum(1 for e in events if e["event_type"] == event_type and (actor is None or e.get("actor") == actor))


def _plan_provider(events: list[dict]) -> str:
    plans = [e for e in events if e["event_type"] == "plan"]
    assert len(plans) == 1
    return plans[0]["usage"]["provider"]


def _executor_models(events: list[dict]) -> set[str]:
    return {e["usage"]["model"] for e in events if e["event_type"] == "action" and e.get("actor") == "executor"}


def _ends_done(events: list[dict]) -> bool:
    obs = [e for e in events if e["event_type"] == "observation"]
    return bool(obs) and obs[-1]["payload"].get("done") is True


@pytest.fixture(scope="module")
def smoke(tmp_path_factory) -> dict[str, dict[str, list[dict]]]:
    tmp = tmp_path_factory.mktemp("bfcl_e2_smoke")
    out = tmp / "out"
    arms = {"planner_alone_cap81": _run(tmp, out, "planner_alone_cap81", "planner_alone")}
    for stem, system in (("takeover_k5", "fixed_k"), ("advise_k5_fullctx", "fixed_k"),
                         ("advise_k5_neutral", "fixed_k"), ("plan_zs", "prompt_only"),
                         ("prefix_zs_m2", "prefix_handoff"), ("prefix_bplus_m4", "prefix_handoff")):
        arms[stem] = _run(tmp, out, stem, system)
    arms["_out"] = out  # type: ignore[assignment]
    return arms


def test_the_mock_planner_alone_source_is_a_replayable_campaign(smoke) -> None:
    for task, events in smoke["planner_alone_cap81"].items():
        assert _plan_provider(events) == "mock"          # a plan event the replay arms can read
        assert _count(events, "action", "planner") >= 3  # 2 CODE + >= 1 COMPLETE (one per turn)
        assert _count(events, "action", "executor") == 0
        assert _ends_done(events), task                  # every scripted user turn was reached


def test_channel_takeover_executes_the_planner_action_at_k5(smoke) -> None:
    for task, events in smoke["takeover_k5"].items():
        assert _plan_provider(events) == "cache"         # the source's first plan, replayed
        acts = [e for e in events if e["event_type"] == "action" and e.get("actor") == "planner"]
        assert acts and min(e["step"] for e in acts) == 5, task
        assert not any((e.get("payload") or {}).get("source") == "shown_action" for e in events)
        assert _ends_done(events)


@pytest.mark.parametrize("stem", ["advise_k5_fullctx", "advise_k5_neutral"])
def test_channel_advise_delivers_advice_and_never_acts(smoke, stem: str) -> None:
    for task, events in smoke[stem].items():
        assert _plan_provider(events) == "cache"
        forced = [e for e in events if e["event_type"] == "intervention" and (e.get("payload") or {}).get("forced")]
        assert forced and min(e["step"] for e in forced) == 5, task
        assert _count(events, "action", "planner") == 0
        assert _ends_done(events)


def test_plan_arm_replays_one_plan_to_the_base_receiver(smoke) -> None:
    for task, events in smoke["plan_zs"].items():
        assert _plan_provider(events) == "cache"
        # prompt_only sends no adapter: sft_plan would have sent model=sft_plan (sft_plan.py:18).
        assert _executor_models(events) == {"mock-executor"}
        assert _count(events, "action", "planner") == 0 and _count(events, "intervention") == 0
        assert _ends_done(events)


@pytest.mark.parametrize("stem, m, model", [("prefix_zs_m2", 2, "mock-executor"), ("prefix_bplus_m4", 4, "sft_b_plus")])
def test_replay_arm_hands_off_after_m_hash_checked_actions(smoke, stem: str, m: int, model: str) -> None:
    for task, events in smoke[stem].items():
        handoff = [e for e in events if e["event_type"] == "report" and "effective_m" in (e.get("payload") or {})]
        assert len(handoff) == 1 and handoff[0]["payload"]["effective_m"] == m, task
        # multi_turn_base_1 / _4 have 4 / 3 turns, so the mock source took 2 + 4 / 2 + 3 actions: > m.
        assert handoff[0]["payload"]["hash_ok"] is True and handoff[0]["payload"]["handoff_occurred"] is True
        assert not any("replay_divergence" in json.dumps(e) for e in events)
        # The receiver acts after the handoff, under the alias its config names.
        live = [e for e in events if e["event_type"] == "action" and e.get("actor") == "executor"]
        assert live and min(e["step"] for e in live) == m + 1
        assert _executor_models(events) == {model}
        assert _ends_done(events)


def _planner_records(out: Path, stem: str) -> list[dict]:
    return [json.loads(l)["usage"] for p in (out / f"bfcl_{stem}_dev_20260924").rglob("events.jsonl")
            for l in p.read_text(encoding="utf-8").splitlines()
            if l.strip() and json.loads(l).get("actor") == "planner" and json.loads(l).get("usage")]


def test_replay_and_plan_arms_make_zero_live_planner_calls(smoke) -> None:
    mod = _summarize()
    out = smoke["_out"]
    for stem in ("prefix_zs_m2", "prefix_bplus_m4"):
        summary = mod.summarise(out, f"bfcl_{stem}_dev_20260924")
        assert summary["n_runs"] == TASKS and summary["planner_calls_live_total"] == 0, stem
        assert mod.gate(summary, expect_planner=False, expect_model=None) == [], stem
    # plan_zs: the only planner record per episode is the replayed plan (provider "cache"). The ledger still
    # counts it as 1 call, because loop.py:465 rewrites n_calls to the attempt count; nothing was bought.
    records = _planner_records(out, "plan_zs")
    assert [r["provider"] for r in records] == ["cache"] * TASKS
    assert mod.summarise(out, "bfcl_plan_zs_dev_20260924")["planner_calls_live_total"] == TASKS
    # The channel arms did call the (mock) planner live: one review per 5 steps, beside the cached plan.
    for stem in ("takeover_k5", "advise_k5_fullctx"):
        providers = [r["provider"] for r in _planner_records(out, stem)]
        assert providers.count("cache") == TASKS and providers.count("mock") >= TASKS, stem
