"""W-5: executor P(ASK) from first-token logprobs, SelfVerifier gate, one re-decode."""
from __future__ import annotations

import json
import math
from pathlib import Path

from sidekick.agents.executor import (
    ASK_TEMPLATE,
    LOGIT_BIAS_BAN,
    MockExecutor,
    VLLMExecutor,
    ask_opening_logit_bias,
    p_ask_from_choice,
    token_matches_ask_opening,
)
from sidekick.agents.planner import MockPlanner
from sidekick.agents.verifier import ConstantVerifier, SelfVerifier
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.protocols.schemas import Event, Usage, utc_now_iso
from sidekick.runner import make_executor, make_verifier, system_kwargs
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

WRITE = '```python\nwrite("outbox.txt", "hello world")\n```'
ASK = ASK_TEMPLATE


class PrefixTokenizer:
    unk_token_id = 0
    table = {
        "A": 10,
        "AS": 11,
        "ASK": 12,
        "ASK_": 13,
        "ASK_PLANNER": 20,
        "ASK_PLANNER:": 21,
    }

    def convert_tokens_to_ids(self, token):
        return self.table.get(token, self.unk_token_id)

    def encode(self, text, add_special_tokens=False):
        if text in self.table:
            return [self.table[text]]
        return [self.unk_token_id]


class _FakeResponse:
    def __init__(self, body):
        self.status_code = 200
        self._body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self, bodies):
        self.bodies = list(bodies)
        self.calls: list[tuple[str, dict]] = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        body = self.bodies.pop(0) if len(self.bodies) == 1 else self.bodies.pop(0)
        if not self.bodies:
            self.bodies = [body]
        return _FakeResponse(body)

    def close(self):
        return None


def _choice(content: str, top: list[dict] | None) -> dict:
    choice: dict = {"message": {"content": content}}
    if top is not None:
        choice["logprobs"] = {
            "content": [
                {
                    "token": top[0]["token"] if top else "",
                    "logprob": top[0]["logprob"] if top else 0.0,
                    "top_logprobs": top,
                }
            ]
        }
    return choice


def _body(content: str, top: list[dict] | None) -> dict:
    return {"choices": [_choice(content, top)], "usage": {"prompt_tokens": 1, "completion_tokens": 2}}


def _run(tmp_path: Path, name: str, executor, verifier=None, run_id: str = "pask", **kwargs):
    log = EventLog(tmp_path, run_id)
    ledger = CostLedger(PriceSchedule({"models": {}, "local": {}}))
    system = get_system(
        name,
        planner=MockPlanner(),
        executor=executor,
        verifier=verifier if verifier is not None else ConstantVerifier(0.5),
        limits=RunLimits(),
        **kwargs,
    )
    result = system.run(MockEnv(), "copy_hello", 1, log, ledger)
    log.close()
    events_path = tmp_path / run_id / "events.jsonl"
    events = list(EventLog.read(events_path))
    return result, events, events_path


def test_token_prefix_match_covers_split_openings():
    assert token_matches_ask_opening("ASK") is True
    assert token_matches_ask_opening("ASK_PLANNER") is True
    assert token_matches_ask_opening("ASK_PLANNER:") is True
    assert token_matches_ask_opening("ĠASK") is True
    assert token_matches_ask_opening("COMPLETE") is False
    assert token_matches_ask_opening("") is False


def test_p_ask_from_choice_sums_split_opening_tokens():
    top = [
        {"token": "ASK", "logprob": math.log(0.4)},
        {"token": "ASK_PLANNER", "logprob": math.log(0.25)},
        {"token": "```", "logprob": math.log(0.2)},
    ]
    mass = p_ask_from_choice(_choice(ASK, top))
    assert mass == math.exp(math.log(0.4)) + math.exp(math.log(0.25))
    assert abs(mass - 0.65) < 1e-12


def test_p_ask_from_choice_missing_logprobs_is_none():
    assert p_ask_from_choice(_choice(ASK, None)) is None
    assert p_ask_from_choice({}) is None
    assert p_ask_from_choice(None) is None


def test_p_ask_from_choice_zero_mass_is_zero():
    top = [
        {"token": "COMPLETE", "logprob": math.log(0.7)},
        {"token": "```", "logprob": math.log(0.2)},
    ]
    mass = p_ask_from_choice(_choice("COMPLETE", top))
    assert mass == 0.0
    assert mass is not None


def test_vllm_logprobs_yield_expected_p_ask():
    top = [
        {"token": "ASK", "logprob": math.log(0.4)},
        {"token": "ASK_PLANNER", "logprob": math.log(0.25)},
        {"token": "```", "logprob": math.log(0.2)},
    ]
    client = _FakeClient([_body(ASK, top)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    text, usage = ex.complete([{"role": "user", "content": "go"}], logprobs=True)
    assert text == ASK
    assert usage.p_ask is not None
    assert abs(usage.p_ask - 0.65) < 1e-12
    payload = client.calls[0][1]
    assert payload["logprobs"] is True
    assert payload["top_logprobs"] == 20


def test_vllm_no_logprobs_yields_none_not_zero():
    client = _FakeClient([_body(ASK, None)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    _, usage = ex.complete([{"role": "user", "content": "go"}])
    assert usage.p_ask is None


def test_vllm_zero_mass_preserved():
    top = [{"token": "COMPLETE", "logprob": math.log(0.9)}]
    client = _FakeClient([_body("COMPLETE", top)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    _, usage = ex.complete([{"role": "user", "content": "go"}])
    assert usage.p_ask == 0.0
    assert usage.p_ask is not None


def test_vllm_ban_ask_prefix_sends_logit_bias():
    client = _FakeClient([_body(WRITE, None)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    ex._tokenizer = PrefixTokenizer()
    ex._tokenizer_loaded = True
    ex.complete([{"role": "user", "content": "go"}], ban_ask_prefix=True)
    bias = client.calls[0][1]["logit_bias"]
    assert bias["12"] == LOGIT_BIAS_BAN
    assert bias["20"] == LOGIT_BIAS_BAN
    assert str(PrefixTokenizer.unk_token_id) not in bias


def test_ask_opening_logit_bias_none_tokenizer():
    assert ask_opening_logit_bias(None) == {}


def test_self_verifier_none_allows_zero_vetoes():
    v = SelfVerifier()
    assert v.score({"p_ask": None}) == float("inf")
    assert v.score({}) == float("inf")
    assert v.score({"p_ask": 0.0}) == 0.0
    assert v.score({"p_ask": 0.0}) is not None
    assert v.score({"p_ask": 0.9}) == 0.9


def test_self_verifier_matches_strict_greater_than():
    v = SelfVerifier()
    threshold = 0.5
    assert (v.score({"p_ask": 0.5}) > threshold) is False
    assert (v.score({"p_ask": 0.51}) > threshold) is True
    assert (v.score({"p_ask": 0.0}) > threshold) is False
    assert (v.score({"p_ask": None}) > threshold) is True


def test_make_verifier_self_p_ask_and_threshold():
    v = make_verifier({"verifier": {"kind": "self_p_ask", "threshold": 0.3}})
    assert isinstance(v, SelfVerifier)
    kw = system_kwargs("sidekick", {"verifier": {"kind": "self_p_ask", "threshold": 0.3}}, "t")
    assert kw["verifier_threshold"] == 0.3


def test_usage_p_ask_none_is_not_zero():
    none = Usage(model="m", provider="mock")
    zero = Usage(model="m", provider="mock", p_ask=0.0)
    assert none.p_ask is None
    assert zero.p_ask == 0.0
    assert zero.p_ask is not None
    assert none.model_dump()["p_ask"] is None
    assert zero.model_dump()["p_ask"] == 0.0


def test_p_ask_zero_survives_eventlog_roundtrip(tmp_path: Path):
    log = EventLog(tmp_path, "pask_rt")
    log.append(
        Event(
            run_id="pask_rt",
            task_id="t",
            system="sidekick",
            seed=1,
            step=1,
            ts=utc_now_iso(),
            actor="executor",
            event_type="action",
            payload={"kind": "CODE", "p_ask": 0.0},
            usage=Usage(model="m", provider="vllm", p_ask=0.0),
        )
    )
    log.append(
        Event(
            run_id="pask_rt",
            task_id="t",
            system="sidekick",
            seed=1,
            step=2,
            ts=utc_now_iso(),
            actor="executor",
            event_type="action",
            payload={"kind": "CODE", "p_ask": None},
            usage=Usage(model="m", provider="vllm", p_ask=None),
        )
    )
    log.close()
    path = tmp_path / "pask_rt" / "events.jsonl"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    zero_obj = json.loads(lines[0])
    none_obj = json.loads(lines[1])
    assert zero_obj["payload"]["p_ask"] == 0.0
    assert zero_obj["payload"]["p_ask"] is not None
    assert zero_obj["usage"]["p_ask"] == 0.0
    assert zero_obj["usage"]["p_ask"] is not None
    assert none_obj["payload"]["p_ask"] is None
    assert none_obj["usage"]["p_ask"] is None
    events = list(EventLog.read(path))
    assert events[0].payload["p_ask"] == 0.0
    assert events[0].usage.p_ask == 0.0
    assert events[0].usage.p_ask is not None
    assert events[1].payload["p_ask"] is None
    assert events[1].usage.p_ask is None


def test_missing_p_ask_allows_ask_and_records_fallback(tmp_path: Path):
    executor = MockExecutor(script=[ASK, WRITE, "COMPLETE"])
    result, events, path = _run(
        tmp_path, "sidekick", executor, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="fb"
    )
    assert result.success is True
    assert result.n_asks == 1
    actions = [e for e in events if e.event_type == "action" and e.actor == "executor"]
    assert actions[0].payload["p_ask"] is None
    assert actions[0].payload.get("p_ask_fallback") is True
    assert actions[0].usage is not None
    assert actions[0].usage.p_ask is None
    raw = path.read_text(encoding="utf-8")
    assert '"p_ask": null' in raw or '"p_ask":null' in raw
    assert not any(c.get("ban_ask_prefix") for c in executor.complete_calls)
    assert all(c.get("logprobs") is True for c in executor.complete_calls)


def test_p_ask_zero_is_preserved_on_action_event(tmp_path: Path):
    executor = MockExecutor(
        script=[ASK, WRITE, "COMPLETE"],
        p_ask_script=[0.0, None, None],
    )
    result, events, path = _run(
        tmp_path, "sidekick", executor, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="zero"
    )
    assert result.n_asks == 0
    actions = [e for e in events if e.event_type == "action" and e.actor == "executor"]
    assert actions[0].payload["p_ask"] == 0.0
    assert actions[0].payload["p_ask"] is not None
    assert actions[0].usage is not None
    assert actions[0].usage.p_ask == 0.0
    found_zero = False
    for line in path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        if obj.get("event_type") == "action" and obj.get("actor") == "executor":
            assert obj["payload"]["p_ask"] == 0.0
            assert obj["usage"]["p_ask"] == 0.0
            found_zero = True
            break
    assert found_zero


def test_gate_vetoes_exactly_on_strict_greater_than(tmp_path: Path):
    eq = MockExecutor(script=[ASK, WRITE, "COMPLETE"], p_ask=0.5)
    result_eq, _, _ = _run(
        tmp_path, "sidekick", eq, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="eq"
    )
    assert result_eq.n_asks == 0

    above = MockExecutor(script=[ASK, WRITE, "COMPLETE"], p_ask=0.51)
    result_above, _, _ = _run(
        tmp_path, "sidekick", above, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="above"
    )
    assert result_above.n_asks == 1
    assert result_above.success is True


def test_veto_redecodes_once_with_ban(tmp_path: Path):
    executor = MockExecutor(
        script=[ASK, WRITE, "COMPLETE"],
        p_ask_script=[0.1, None, None],
    )
    result, events, _ = _run(
        tmp_path, "sidekick", executor, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="rd"
    )
    assert result.success is True
    assert result.n_asks == 0
    bans = [c for c in executor.complete_calls if c.get("ban_ask_prefix")]
    assert len(bans) == 1
    asks = [e for e in events if e.event_type == "ask"]
    assert asks and asks[0].payload.get("redecode") is True
    kinds = [
        e.payload.get("kind")
        for e in events
        if e.event_type == "action" and e.actor == "executor"
    ]
    assert kinds[0] == "ASK_PLANNER"
    assert "CODE" in kinds


def test_second_ask_falls_back_to_ask_ignored(tmp_path: Path):
    executor = MockExecutor(
        script=[ASK, ASK, WRITE, "COMPLETE"],
        p_ask_script=[0.1, 0.9, None, None],
    )
    result, events, _ = _run(
        tmp_path, "sidekick", executor, verifier=SelfVerifier(), verifier_threshold=0.5, run_id="loop"
    )
    assert result.success is True
    assert result.n_asks == 0
    bans = [c for c in executor.complete_calls if c.get("ban_ask_prefix")]
    assert len(bans) == 1
    assert len(executor.complete_calls) == 4
    assert not any(e.event_type == "ask" and e.payload.get("n_asks") for e in events)


def test_constant_verifier_gate_does_not_redecode(tmp_path: Path):
    executor = MockExecutor(script=[ASK, WRITE, "COMPLETE"])
    result, events, _ = _run(
        tmp_path,
        "sidekick",
        executor,
        verifier=ConstantVerifier(0.5),
        verifier_threshold=0.5,
        run_id="const",
    )
    assert result.n_asks == 0
    assert not any(c.get("ban_ask_prefix") for c in executor.complete_calls)
    assert not any(e.event_type == "ask" and e.payload.get("redecode") for e in events)


def test_gate_disabled_does_not_redecode(tmp_path: Path):
    executor = MockExecutor(script=[ASK, WRITE, "COMPLETE"])
    result, events, _ = _run(tmp_path, "prompt_only", executor, run_id="ungated")
    assert result.success is True
    assert result.n_asks == 1
    assert not any(c.get("ban_ask_prefix") for c in executor.complete_calls)
    assert not any(e.payload.get("redecode") for e in events if e.event_type == "ask")


def test_router_seq_ask_ignored_without_redecode(tmp_path: Path):
    executor = MockExecutor(script=[ASK, WRITE, "COMPLETE"])
    result, events, _ = _run(tmp_path, "router_seq", executor, run_id="router")
    assert result.n_asks == 0
    assert not any(c.get("ban_ask_prefix") for c in executor.complete_calls)
    kinds = [e.event_type for e in events]
    assert "ask" in kinds
    assert not any(e.payload.get("redecode") for e in events)
    assert result.success is True


def test_default_complete_omits_logprobs_keys():
    client = _FakeClient([_body("COMPLETE", None)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    ex.complete([{"role": "user", "content": "go"}])
    payload = client.calls[0][1]
    assert "logprobs" not in payload
    assert "top_logprobs" not in payload


def test_complete_logprobs_true_includes_both_keys():
    client = _FakeClient([_body("COMPLETE", None)])
    ex = VLLMExecutor("test-model", "http://x", http_client=client)
    ex.complete([{"role": "user", "content": "go"}], logprobs=True)
    payload = client.calls[0][1]
    assert payload["logprobs"] is True
    assert payload["top_logprobs"] == 20


def test_self_gate_off_action_events_omit_p_ask_keys(tmp_path: Path):
    executor = MockExecutor(script=[ASK, WRITE, "COMPLETE"])
    _, events, path = _run(
        tmp_path,
        "sidekick",
        executor,
        verifier=ConstantVerifier(0.5),
        verifier_threshold=0.5,
        run_id="omit",
    )
    assert not any(c.get("logprobs") for c in executor.complete_calls)
    found_action = False
    for line in path.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        payload = obj.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        assert "p_ask" not in payload
        assert "p_ask_fallback" not in payload
        if obj.get("event_type") == "action" and obj.get("actor") == "executor":
            found_action = True
            assert "p_ask" not in payload.keys()
            assert "p_ask_fallback" not in payload.keys()
    assert found_action
    for e in events:
        if e.event_type == "action" and e.actor == "executor":
            assert "p_ask" not in e.payload
            assert "p_ask_fallback" not in e.payload


def test_self_p_ask_config_enables_executor_logprobs():
    cfg = {
        "executor": {"type": "vllm", "model": "test-model", "base_url": "http://x"},
        "verifier": {"kind": "self_p_ask", "threshold": 0.3},
    }
    ex = make_executor(cfg)
    assert ex.logprobs is True
    client = _FakeClient([_body("COMPLETE", None)])
    ex._http = client
    ex.complete([{"role": "user", "content": "go"}])
    payload = client.calls[0][1]
    assert payload["logprobs"] is True
    assert "top_logprobs" in payload
    off = make_executor({"executor": {"type": "vllm", "model": "test-model", "base_url": "http://x"}})
    assert off.logprobs is False
