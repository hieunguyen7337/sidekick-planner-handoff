"""Tests for the locally-served second planner (U11).

The point of this backend is a generality claim — "the channel result is not a fact about
one planner family" — so the tests are weighted towards the things that would make that
claim unfalsifiable if they went wrong: prompts that silently differ from the hosted
planner's, a parse failure papered over with a default packet, or a local planner quietly
reporting provider dollars into the cost frontier.
"""

from __future__ import annotations

import json

import pytest

from sidekick.agents import planner as planner_mod
from sidekick.agents.vllm_planner import VllmPlanner, VllmPlannerError
from sidekick.protocols.schemas import DelegationPacket


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200, text: str = "") -> None:
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class FakeClient:
    """Records every request so prompts and payloads can be asserted on."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[dict] = []
        self.closed = False

    def post(self, url: str, json: dict) -> FakeResponse:  # noqa: A002 - mirrors httpx
        self.requests.append({"url": url, "json": json})
        if not self._responses:
            raise AssertionError("more requests than canned responses")
        return self._responses.pop(0)

    def close(self) -> None:
        self.closed = True


def chat_response(content: str, **usage) -> FakeResponse:
    return FakeResponse({
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": usage.get("prompt_tokens", 10),
                  "completion_tokens": usage.get("completion_tokens", 5)},
    })


# Built from the project's own default packet rather than hand-rolled, so the fixture
# cannot drift from DelegationPacket's required fields (packet_id, created_at and
# PlanStep-shaped plan_steps are all easy to get wrong by hand).
PACKET = json.loads(planner_mod._default_packet("t1", "g", "ctx").model_dump_json())


def make_planner(responses: list[FakeResponse], **kw) -> tuple[VllmPlanner, FakeClient]:
    client = FakeClient(responses)
    p = VllmPlanner(model="Qwen/Qwen3-32B", base_url="http://h:8001/v1", http_client=client, **kw)
    return p, client


def sent_prompt(client: FakeClient, i: int = 0) -> str:
    return client.requests[i]["json"]["messages"][-1]["content"]


# --- the prompts must be the hosted planner's, byte for byte ----------------------------


def test_plan_prompt_is_the_shared_one() -> None:
    p, client = make_planner([chat_response("```json\n" + json.dumps(PACKET) + "\n```")])

    p.plan("t1", "g", "ctx")

    assert sent_prompt(client) == planner_mod.build_plan_prompt("t1", "g", "ctx")


def test_act_prompt_is_the_shared_one_including_the_handoff_variant() -> None:
    p, client = make_planner([chat_response("```python\nx=1\n```"), chat_response("REPORT: done")])

    p.act("t1", "tr", allow_handoff=True)
    p.act("t1", "tr", allow_handoff=False)

    assert sent_prompt(client, 0) == planner_mod.build_act_prompt("t1", "tr", True)
    assert sent_prompt(client, 1) == planner_mod.build_act_prompt("t1", "tr", False)
    assert "HANDOFF" in sent_prompt(client, 0)
    assert "HANDOFF" not in sent_prompt(client, 1)


def test_correct_prompt_is_the_shared_one() -> None:
    packet = DelegationPacket(**PACKET)
    p, client = make_planner([chat_response("do X instead")])

    p.correct(packet, "delta")

    assert sent_prompt(client) == planner_mod.build_correct_prompt(packet, "delta")


# --- packet handling --------------------------------------------------------------------


def test_plan_parses_a_fenced_packet() -> None:
    p, _ = make_planner([chat_response("```json\n" + json.dumps(PACKET) + "\n```")])

    got = p.plan("t1", "g", "ctx")

    assert got.kind == "PLAN"
    assert got.packet.task_id == "t1"
    assert len(got.packet.plan_steps) == len(PACKET["plan_steps"])
    assert got.usage.raw["packet_parse_path"] == "fenced_json"


def test_an_unparseable_reply_is_retried_once_and_then_raises() -> None:
    """A planner that cannot produce a packet must fail loudly.

    Falling back to a default packet would let an arm run to completion while measuring
    nothing — the failure mode this project has already been bitten by.
    """
    p, client = make_planner([chat_response("no json here"), chat_response("still nothing")])

    with pytest.raises(planner_mod.PacketParseError):
        p.plan("t1", "g", "ctx")

    assert len(client.requests) == 2
    assert "could not be parsed" in sent_prompt(client, 1)


def test_a_successful_retry_is_billed_as_two_calls() -> None:
    p, _ = make_planner([
        chat_response("garbage", prompt_tokens=10, completion_tokens=3),
        chat_response("```json\n" + json.dumps(PACKET) + "\n```", prompt_tokens=12, completion_tokens=7),
    ])

    got = p.plan("t1", "g", "ctx")

    assert got.usage.n_calls == 2
    assert got.usage.input_tokens == 22
    assert got.usage.output_tokens == 10
    assert got.usage.raw["packet_parse_path"] == "fenced_json_retry"


def test_a_packet_without_a_task_id_inherits_it() -> None:
    body = {**PACKET, "task_id": ""}
    p, _ = make_planner([chat_response("```json\n" + json.dumps(body) + "\n```")])

    assert p.plan("t9", "g", "ctx").packet.task_id == "t9"


# --- act --------------------------------------------------------------------------------


def test_act_extracts_a_python_fence() -> None:
    p, _ = make_planner([chat_response("here:\n```python\nprint(1)\n```")])

    got = p.act("t1", "tr")

    assert got.kind == "ACTION"
    assert got.code is not None and "print(1)" in got.code


def test_act_with_no_fence_returns_no_code_but_keeps_the_text() -> None:
    p, _ = make_planner([chat_response("ASK_PLANNER: I am stuck")])

    got = p.act("t1", "tr")

    assert got.code is None
    assert "ASK_PLANNER" in got.raw_output


# --- cost accounting --------------------------------------------------------------------


def test_usage_is_reported_as_gpu_not_provider_dollars() -> None:
    """A local planner has no provider price; inventing one corrupts the cost frontier."""
    p, _ = make_planner([chat_response("REPORT: x")], gpu_fraction=0.5)

    usage = p.act("t1", "tr").usage

    assert usage.provider == "vllm"
    assert usage.gpu_seconds == pytest.approx(usage.latency_s * 0.5)
    assert usage.n_calls == 1


def test_reasoning_content_is_used_when_content_is_empty() -> None:
    """A reasoning parser can put the whole generation in reasoning_content."""
    client = FakeClient([FakeResponse({
        "choices": [{"message": {"content": "", "reasoning_content": "REPORT: thought"}}],
        "usage": {},
    })])
    p = VllmPlanner(model="m", base_url="http://h/v1", http_client=client)

    assert "REPORT: thought" in p.act("t1", "tr").raw_output


# --- transport ---------------------------------------------------------------------------


def test_a_server_error_raises_with_the_body_attached() -> None:
    client = FakeClient([FakeResponse(status_code=500, text="boom")])
    p = VllmPlanner(model="m", base_url="http://h/v1", http_client=client)

    with pytest.raises(VllmPlannerError) as exc:
        p.act("t1", "tr")

    assert "500" in str(exc.value)
    assert exc.value.body == "boom"


def test_chat_template_kwargs_are_forwarded() -> None:
    """Granite/Qwen templates default thinking on, which burns the budget silently."""
    p, client = make_planner([chat_response("REPORT: x")], chat_template_kwargs={"enable_thinking": False})

    p.act("t1", "tr")

    assert client.requests[0]["json"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_a_system_prompt_is_sent_first_when_configured() -> None:
    p, client = make_planner([chat_response("REPORT: x")], system_prompt="be terse")

    p.act("t1", "tr")

    messages = client.requests[0]["json"]["messages"]
    assert messages[0] == {"role": "system", "content": "be terse"}
    assert messages[-1]["role"] == "user"


def test_base_url_trailing_slash_does_not_double_up() -> None:
    client = FakeClient([chat_response("REPORT: x")])
    p = VllmPlanner(model="m", base_url="http://h:8001/v1/", http_client=client)

    p.act("t1", "tr")

    assert client.requests[0]["url"] == "http://h:8001/v1/chat/completions"


def test_close_closes_the_client() -> None:
    p, client = make_planner([])

    p.close()

    assert client.closed is True


# --- wiring ------------------------------------------------------------------------------


def test_make_planner_builds_the_vllm_backend_from_config() -> None:
    from sidekick.runner import make_planner

    got = make_planner({"planner": {
        "type": "vllm",
        "model": "Qwen/Qwen3-32B",
        "base_url": "http://127.0.0.1:8001/v1",
        "max_tokens": 4096,
    }})

    assert isinstance(got, VllmPlanner)
    assert got.model == "Qwen/Qwen3-32B"
    assert got.max_tokens == 4096


def test_make_planner_still_defaults_to_mock() -> None:
    from sidekick.agents.planner import MockPlanner
    from sidekick.runner import make_planner

    assert isinstance(make_planner({}), MockPlanner)
