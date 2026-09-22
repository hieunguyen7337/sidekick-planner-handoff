"""Tests for the locally-served second planner (U11).

The point of this backend is a generality claim — "the channel result is not a fact about
one planner family" — so the tests are weighted towards the things that would make that
claim unfalsifiable if they went wrong: prompts that silently differ from the hosted
planner's, a parse failure papered over with a default packet, or a local planner quietly
reporting provider dollars into the cost frontier.
"""

from __future__ import annotations

import itertools
import json

import pytest

from sidekick.agents import planner as planner_mod
from sidekick.agents import vllm_planner as vllm_mod
from sidekick.agents.planner import CachedPacketPlanner, PlannerContextOverflow
from sidekick.agents.vllm_planner import (
    VllmPlanner,
    VllmPlannerContextOverflow,
    VllmPlannerError,
    is_context_overflow,
)
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


def sent_messages(client: FakeClient, i: int) -> list[dict]:
    return client.requests[i]["json"]["messages"]


# vLLM 0.29's wording (renderers/params.py), wrapped the way its OpenAI server returns it.
OVERFLOW_BODY = json.dumps({
    "object": "error",
    "message": "This model's maximum context length is 32768 tokens. However, you requested "
               "2048 output tokens and your prompt contains 31000 input tokens, for a total of "
               "33048 tokens. Please reduce the length of the input prompt or the number of "
               "requested output tokens.",
    "type": "BadRequestError",
    "code": 400,
})


def overflow_response() -> FakeResponse:
    return FakeResponse(status_code=400, text=OVERFLOW_BODY)


PACKET_REPLY = "```json\n" + json.dumps(PACKET) + "\n```"


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


def test_planner_base_url_env_override_wins(monkeypatch) -> None:
    # A PBS job picks a free port at run time; the config's port is only the default.
    from sidekick.runner import make_planner, resolve_planner_base_url

    cfg = {"base_url": "http://127.0.0.1:8002/v1"}
    monkeypatch.delenv("SIDEKICK_PLANNER_BASE_URL", raising=False)
    assert resolve_planner_base_url(cfg) == "http://127.0.0.1:8002/v1"
    monkeypatch.setenv("SIDEKICK_PLANNER_BASE_URL", "http://127.0.0.1:23456/v1")
    assert resolve_planner_base_url(cfg) == "http://127.0.0.1:23456/v1"
    planner = make_planner({"planner": {"type": "vllm", "model": "m", **cfg}})
    assert planner.base_url == "http://127.0.0.1:23456/v1"


# --- the episode thread -------------------------------------------------------------------
#
# The hosted planner resumes one codex thread per episode, so it sees its plan prompt (the only
# prompt carrying the API docs) and every earlier prompt with its own reply. The loop's planner
# transcript records a CODE action only as OBS: <text>, so without the same thread the local
# planner would see observations without knowing what it ran. These pin that it gets the thread.


def _user(text: str) -> dict:
    return {"role": "user", "content": text}


def _assistant(text: str) -> dict:
    return {"role": "assistant", "content": text}


@pytest.mark.parametrize("system_prompt", [None, "be terse"])
def test_plan_act_act_sends_the_whole_thread_with_byte_identical_prompts(system_prompt) -> None:
    act1_reply = "```python\nprint(1)\n```"
    p, client = make_planner(
        [chat_response(PACKET_REPLY), chat_response(act1_reply), chat_response("REPORT: done")],
        system_prompt=system_prompt,
    )

    p.plan("t1", "g", "ctx")
    p.act("t1", "tr1")
    p.act("t1", "tr2", allow_handoff=True)

    head = [{"role": "system", "content": system_prompt}] if system_prompt else []
    assert sent_messages(client, 2) == head + [
        _user(planner_mod.build_plan_prompt("t1", "g", "ctx")),
        _assistant(PACKET_REPLY),
        _user(planner_mod.build_act_prompt("t1", "tr1", False)),
        _assistant(act1_reply),
        _user(planner_mod.build_act_prompt("t1", "tr2", True)),
    ]
    # Earlier requests carried exactly the thread as it stood then.
    assert sent_messages(client, 0) == head + [_user(planner_mod.build_plan_prompt("t1", "g", "ctx"))]
    assert len(sent_messages(client, 1)) == len(head) + 3


def test_a_correction_joins_the_thread_with_the_shared_prompt() -> None:
    packet = DelegationPacket(**PACKET)
    p, client = make_planner([chat_response(PACKET_REPLY), chat_response("do X"), chat_response("REPORT: x")])

    p.plan("t1", "g", "ctx")
    p.correct(packet, "delta")
    p.act("t1", "tr")

    assert sent_messages(client, 2)[2:4] == [
        _user(planner_mod.build_correct_prompt(packet, "delta")),
        _assistant("do X"),
    ]


def test_the_thread_keeps_the_reasoning_content_fallback_text() -> None:
    client = FakeClient([
        FakeResponse({"choices": [{"message": {"content": "", "reasoning_content": "REPORT: thought"}}]}),
        chat_response("REPORT: next"),
    ])
    p = VllmPlanner(model="m", base_url="http://h/v1", http_client=client)

    p.act("t1", "tr1")
    p.act("t1", "tr2")

    assert sent_messages(client, 1)[1] == _assistant("REPORT: thought")


def test_a_raising_call_appends_nothing() -> None:
    """The loop may retry a failed call; a half-recorded exchange would then be sent twice."""
    p, client = make_planner([
        chat_response("REPORT: a"),
        FakeResponse(status_code=500, text="boom"),
        chat_response("REPORT: b"),
    ])

    p.act("t1", "tr1")
    with pytest.raises(VllmPlannerError):
        p.act("t1", "tr2")
    p.act("t1", "tr3")

    assert sent_messages(client, 2) == [
        _user(planner_mod.build_act_prompt("t1", "tr1")),
        _assistant("REPORT: a"),
        _user(planner_mod.build_act_prompt("t1", "tr3")),
    ]


# --- compaction on a context overflow -------------------------------------------------------


def test_overflow_detection_is_the_400_with_vllms_wording_only() -> None:
    assert is_context_overflow(400, OVERFLOW_BODY)
    assert is_context_overflow(400, "THIS MODEL'S MAXIMUM CONTEXT LENGTH IS 8 TOKENS")
    assert not is_context_overflow(500, OVERFLOW_BODY)
    assert not is_context_overflow(400, '{"message": "temperature must be >= 0"}')
    assert not is_context_overflow(400, "")


def test_overflow_drops_the_oldest_non_anchor_exchange_for_good_and_resends(monkeypatch) -> None:
    # Every perf_counter() call advances one second, so each attempt measures 1.0s.
    clock = itertools.count()
    monkeypatch.setattr(vllm_mod.time, "perf_counter", lambda: float(next(clock)))
    p, client = make_planner(
        [
            chat_response(PACKET_REPLY),
            chat_response("REPORT: r1"),
            chat_response("REPORT: r2"),
            overflow_response(),
            chat_response("REPORT: r3", prompt_tokens=30, completion_tokens=4),
            chat_response("REPORT: r4"),
        ],
        gpu_fraction=0.5,
    )
    plan_prompt = planner_mod.build_plan_prompt("t1", "g", "ctx")
    act = [planner_mod.build_act_prompt("t1", f"tr{i}") for i in range(5)]

    p.plan("t1", "g", "ctx")
    p.act("t1", "tr1")
    p.act("t1", "tr2")
    got = p.act("t1", "tr3")
    later = p.act("t1", "tr4")

    # The refused request carried everything; the resend lost act1, the oldest non-anchor pair.
    assert [m["content"] for m in sent_messages(client, 3)] == [
        plan_prompt, PACKET_REPLY, act[1], "REPORT: r1", act[2], "REPORT: r2", act[3],
    ]
    assert [m["content"] for m in sent_messages(client, 4)] == [
        plan_prompt, PACKET_REPLY, act[2], "REPORT: r2", act[3],
    ]
    # The drop is permanent: the next call does not resend act1, and the anchor is still first.
    assert [m["content"] for m in sent_messages(client, 5)] == [
        plan_prompt, PACKET_REPLY, act[2], "REPORT: r2", act[3], "REPORT: r3", act[4],
    ]
    assert got.raw_output == "REPORT: r3"
    assert got.usage.raw["n_context_drops"] == 1
    assert got.usage.raw["n_context_drops_total"] == 1
    assert got.usage.raw["thread_exchanges"] == 2
    # A refused 400 generates nothing: one call, the successful one's tokens, both attempts' time.
    assert got.usage.n_calls == 1
    assert got.usage.input_tokens == 30
    assert got.usage.latency_s == pytest.approx(2.0)
    assert got.usage.gpu_seconds == pytest.approx(1.0)
    assert later.usage.raw["n_context_drops"] == 0
    assert later.usage.raw["n_context_drops_total"] == 1
    assert later.usage.raw["thread_exchanges"] == 3


def test_overflow_keeps_dropping_until_the_request_fits() -> None:
    p, client = make_planner([
        chat_response(PACKET_REPLY),
        chat_response("REPORT: r1"),
        chat_response("REPORT: r2"),
        overflow_response(),
        overflow_response(),
        chat_response("REPORT: r3"),
    ])

    p.plan("t1", "g", "ctx")
    p.act("t1", "tr1")
    p.act("t1", "tr2")
    got = p.act("t1", "tr3")

    assert [m["content"] for m in sent_messages(client, 5)] == [
        planner_mod.build_plan_prompt("t1", "g", "ctx"),
        PACKET_REPLY,
        planner_mod.build_act_prompt("t1", "tr3"),
    ]
    assert got.usage.raw["n_context_drops"] == 2
    assert got.usage.raw["thread_exchanges"] == 1


def test_overflow_with_only_the_anchor_left_raises_context_overflow() -> None:
    p, client = make_planner([
        chat_response(PACKET_REPLY),
        overflow_response(),
        chat_response("REPORT: fits"),
    ])

    p.plan("t1", "g", "ctx")
    with pytest.raises(PlannerContextOverflow) as exc:
        p.act("t1", "a transcript too long for the window")

    # Nothing was droppable, so nothing was resent.
    assert len(client.requests) == 2
    assert isinstance(exc.value, VllmPlannerContextOverflow)
    assert isinstance(exc.value, VllmPlannerError)
    assert exc.value.usage.provider == "vllm"
    assert exc.value.usage.raw["n_context_drops"] == 0
    assert exc.value.usage.raw["thread_exchanges"] == 1
    assert "maximum context length" in exc.value.body
    # The anchor survived and the refused prompt was not recorded.
    p.act("t1", "short")
    assert [m["content"] for m in sent_messages(client, 2)] == [
        planner_mod.build_plan_prompt("t1", "g", "ctx"),
        PACKET_REPLY,
        planner_mod.build_act_prompt("t1", "short"),
    ]


def test_overflow_inside_plan_raises_context_overflow() -> None:
    p, client = make_planner([overflow_response()])

    with pytest.raises(PlannerContextOverflow):
        p.plan("t1", "g", "api docs longer than the window")

    assert len(client.requests) == 1


def test_a_400_without_the_context_wording_is_a_plain_error_and_drops_nothing() -> None:
    p, client = make_planner([
        chat_response(PACKET_REPLY),
        chat_response("REPORT: r1"),
        FakeResponse(status_code=400, text='{"message": "temperature must be >= 0"}'),
        chat_response("REPORT: r2"),
    ])

    p.plan("t1", "g", "ctx")
    p.act("t1", "tr1")
    with pytest.raises(VllmPlannerError) as exc:
        p.act("t1", "tr2")
    assert not isinstance(exc.value, PlannerContextOverflow)
    assert "400" in str(exc.value)
    assert len(client.requests) == 3

    p.act("t1", "tr3")
    assert [m["content"] for m in sent_messages(client, 3)] == [
        planner_mod.build_plan_prompt("t1", "g", "ctx"),
        PACKET_REPLY,
        planner_mod.build_act_prompt("t1", "tr1"),
        "REPORT: r1",
        planner_mod.build_act_prompt("t1", "tr3"),
    ]


def test_a_plan_parse_retry_anchors_only_the_successful_exchange() -> None:
    """The failed reply is useless to the loop and its prompt is a second copy of the API docs."""
    p, client = make_planner([
        chat_response("no json here"),
        chat_response(PACKET_REPLY),
        chat_response("REPORT: r1"),
        overflow_response(),
        chat_response("REPORT: r2"),
    ])
    plan_prompt = planner_mod.build_plan_prompt("t1", "g", "ctx")

    p.plan("t1", "g", "ctx")
    p.act("t1", "tr1")
    p.act("t1", "tr2")

    retry_prompt = sent_prompt(client, 1)
    assert retry_prompt.startswith(plan_prompt) and "could not be parsed" in retry_prompt
    # The retry went out alone, without the failed exchange.
    assert sent_messages(client, 1) == [_user(retry_prompt)]
    # After the compaction only the successful plan exchange is left in front of the new prompt.
    assert [m["content"] for m in sent_messages(client, 4)] == [
        retry_prompt,
        PACKET_REPLY,
        planner_mod.build_act_prompt("t1", "tr2"),
    ]
    assert all("no json here" not in m["content"] for m in sent_messages(client, 2))


# --- a replayed plan: CachedPacketPlanner around the local planner --------------------------


DIGEST = "API-DOCS-DIGEST-7f3a"


def _cached_vllm(tmp_path, responses: list[FakeResponse]) -> tuple[CachedPacketPlanner, FakeClient]:
    archive = tmp_path / "planner_alone" / "1" / "t1" / "events.jsonl"
    archive.parent.mkdir(parents=True)
    plan_event = {"event_type": "plan", "payload": {"packet": PACKET, "model": "Qwen/Qwen3-8B"}, "usage": {}}
    archive.write_text(json.dumps(plan_event) + "\n", encoding="utf-8")
    inner, client = make_planner(responses)
    return CachedPacketPlanner(inner, tmp_path, system="planner_alone", seed=1), client


def test_a_replayed_plans_digest_is_the_anchor_and_survives_compaction(tmp_path) -> None:
    """With no plan() on the inner planner, the digest-bearing first exchange must persist."""
    cached, client = _cached_vllm(tmp_path, [
        chat_response("REPORT: r1"),
        chat_response("REPORT: r2"),
        overflow_response(),
        chat_response("REPORT: r3"),
    ])

    cached.plan("t1", "g", f"docs: {DIGEST}")
    assert client.requests == []  # the replayed plan buys nothing
    cached.act("t1", "tr1")
    cached.act("t1", "tr2")
    cached.act("t1", "tr3")

    assert len(client.requests) == 4
    for i in range(4):
        messages = sent_messages(client, i)
        assert sum(m["content"].count(DIGEST) for m in messages) == 1, i
        assert DIGEST in messages[0]["content"], i
        assert CachedPacketPlanner._DIGEST_BANNER in messages[0]["content"], i
    # The compaction dropped act2's exchange -- never the digest-bearing anchor.
    assert [m["content"] for m in sent_messages(client, 3)][1:] == [
        "REPORT: r1",
        planner_mod.build_act_prompt("t1", "tr3"),
    ]


def test_a_replayed_plan_with_only_the_digest_exchange_left_overflows(tmp_path) -> None:
    cached, client = _cached_vllm(tmp_path, [chat_response("REPORT: r1"), overflow_response()])

    cached.plan("t1", "g", f"docs: {DIGEST}")
    cached.act("t1", "tr1")
    with pytest.raises(PlannerContextOverflow):
        cached.act("t1", "tr2")

    assert len(client.requests) == 2
