import pytest
from pydantic import ValidationError

from sidekick.protocols.schemas import (
    SCHEMA_VERSION,
    ActionParseError,
    DelegationPacket,
    ExecutorAction,
    Event,
    Observation,
    PlanStep,
    PlannerResponse,
    RunResult,
    Usage,
    parse_executor_action,
    utc_now_iso,
)


def make_usage(**kw):
    base = dict(model="gpt-5.6-luna", provider="codex")
    base.update(kw)
    return Usage(**base)


# ---------- Usage ----------

def test_usage_defaults():
    u = make_usage()
    assert u.input_tokens == 0 and u.cached_input_tokens == 0
    assert u.output_tokens == 0 and u.reasoning_output_tokens == 0
    assert u.gpu_seconds == 0.0 and u.n_calls == 1
    assert u.raw == {}


def test_usage_accepts_any_raw_dict():
    u = make_usage(raw={"arbitrary": [1, 2, {"nested": True}]})
    assert u.raw["arbitrary"][2]["nested"] is True


def test_usage_rejects_bad_provider():
    with pytest.raises(ValidationError):
        make_usage(provider="openai")


def test_usage_negative_tokens_rejected():
    # ge=0 in the schema: negative token counts would silently corrupt cost
    # totals and displacement ratios, so they must raise ValidationError.
    with pytest.raises(ValidationError):
        make_usage(input_tokens=-5)


# ---------- PlanStep / DelegationPacket ----------

def test_plan_step_defaults():
    s = PlanStep(index=1, description="do thing")
    assert s.expected_outcome == "" and s.apps == []


def test_delegation_packet_roundtrip():
    p = DelegationPacket(
        packet_id="p1", task_id="t1", goal="g", created_at=utc_now_iso(),
        plan_steps=[PlanStep(index=0, description="x")],
    )
    p2 = DelegationPacket.model_validate_json(p.model_dump_json())
    assert p2.packet_id == "p1" and p2.plan_steps[0].description == "x"


def test_delegation_packet_forbids_extra():
    with pytest.raises(ValidationError):
        DelegationPacket(packet_id="p", task_id="t", goal="g", created_at="now", bogus=1)


# ---------- ExecutorAction ----------

def test_action_code_requires_code():
    with pytest.raises(ValidationError):
        ExecutorAction(kind="CODE", raw_output="x")
    with pytest.raises(ValidationError):
        ExecutorAction(kind="CODE", code="   ", raw_output="x")


def test_action_ask_planner_requires_reason():
    with pytest.raises(ValidationError):
        ExecutorAction(kind="ASK_PLANNER", raw_output="x")
    a = ExecutorAction(kind="ASK_PLANNER", ask_reason="why?", raw_output="x")
    assert a.ask_reason == "why?"


def test_action_report_and_complete_ok():
    assert ExecutorAction(kind="REPORT", message="done", raw_output="r").message == "done"
    assert ExecutorAction(kind="COMPLETE", raw_output="c").code is None


def test_action_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        ExecutorAction(kind="MAGIC", raw_output="x")


# ---------- PlannerResponse / Observation / Event / RunResult ----------

def test_planner_response_roundtrip():
    r = PlannerResponse(kind="PLAN", usage=make_usage(n_calls=2), raw_output="hi")
    r2 = PlannerResponse.model_validate_json(r.model_dump_json())
    assert r2.usage.n_calls == 2 and r2.kind == "PLAN"


def test_observation_defaults():
    o = Observation(text="ok", step=3)
    assert o.done is False and o.truncated is False and o.error_type is None


def test_event_payload_freeform():
    e = Event(run_id="r", task_id="t", system="sidekick", seed=1, step=0,
              ts=utc_now_iso(), actor="planner", event_type="plan",
              payload={"anything": {"deep": [1]}})
    assert e.payload["anything"]["deep"] == [1]


def test_event_rejects_bad_actor():
    with pytest.raises(ValidationError):
        Event(run_id="r", task_id="t", system="s", seed=1, step=0, ts="now",
              actor="ghost", event_type="plan")


def test_event_rejects_bad_event_type():
    with pytest.raises(ValidationError):
        Event(run_id="r", task_id="t", system="s", seed=1, step=0, ts="now",
              actor="planner", event_type="whatever")


def test_event_error_type_values():
    for et in ("parse_error", "timeout", "crash", "api_error", None):
        e = Event(run_id="r", task_id="t", system="s", seed=1, step=0, ts="now",
                  actor="executor", event_type="error", error_type=et)
        assert e.error_type == et


def test_run_result_defaults():
    r = RunResult(run_id="r", task_id="t", system="fixed_k", seed=7, success=True)
    assert r.steps == 0 and r.n_planner_calls == 0 and r.tgc is None


def test_run_result_rejects_extra():
    with pytest.raises(ValidationError):
        RunResult(run_id="r", task_id="t", system="s", seed=1, success=True, extra=1)


# ---------- helpers ----------

def test_utc_now_iso_is_utc():
    ts = utc_now_iso()
    assert ts.startswith(str(__import__("datetime").datetime.now(__import__("datetime").timezone.utc).year))
    assert "+00:00" in ts


def test_schema_version_constant():
    assert SCHEMA_VERSION == 1


# ---------- parse_executor_action ----------

def test_parse_fenced_code():
    raw = "Let me do it:\n```python\nprint('hi')\n```\n"
    a = parse_executor_action(raw)
    assert a.kind == "CODE" and a.code == "print('hi')"
    assert a.raw_output == raw


def test_parse_code_block_with_nested_fence():
    raw = "```python\nx = '''\n```\nnested marker\n```\n'''\nprint(x)\n```\n"
    a = parse_executor_action(raw)
    assert a.kind == "CODE"
    assert "print(x)" in a.code
    assert "nested marker" in a.code


def test_parse_ask_planner():
    a = parse_executor_action("ASK_PLANNER: I need the file path")
    assert a.kind == "ASK_PLANNER" and a.ask_reason == "I need the file path"


def test_parse_report():
    a = parse_executor_action("REPORT: task finished cleanly")
    assert a.kind == "REPORT" and a.message == "task finished cleanly"


def test_parse_complete():
    a = parse_executor_action("COMPLETE")
    assert a.kind == "COMPLETE"
    assert a.message is None


def test_parse_complete_carries_the_answer():
    """AppWorld scores question tasks on the answer, so it must survive parsing.

    Regression: the parser tested `stripped == "COMPLETE"`, so a real answer like
    "COMPLETE: Placeholder Song A, Placeholder Song B" raised ActionParseError and a
    solved task was recorded as a parse_error with tgc 0.0.
    """
    a = parse_executor_action("COMPLETE: Placeholder Song A, Placeholder Song B")
    assert a.kind == "COMPLETE"
    assert a.message == "Placeholder Song A, Placeholder Song B"
    assert a.raw_output == "COMPLETE: Placeholder Song A, Placeholder Song B"


def test_parse_complete_with_empty_answer_is_a_bare_complete():
    a = parse_executor_action("COMPLETE:")
    assert a.kind == "COMPLETE"
    assert a.message is None


def test_parse_priority_code_over_ask():
    raw = "ASK_PLANNER: first\n```python\ncode_here()\n```"
    a = parse_executor_action(raw)
    assert a.kind == "CODE"


def test_parse_raw_output_untouched_whitespace():
    raw = "  COMPLETE   "
    a = parse_executor_action(raw)
    assert a.kind == "COMPLETE" and a.raw_output == raw


def test_parse_error_raises_with_raw():
    raw = "I think I should try something else entirely."
    with pytest.raises(ActionParseError) as exc:
        parse_executor_action(raw)
    assert exc.value.raw_output == raw


def test_parse_empty_raises():
    with pytest.raises(ActionParseError):
        parse_executor_action("")


def test_parse_ask_planner_empty_reason_raises():
    # empty ask_reason fails the ExecutorAction validator -> treated as no match
    with pytest.raises(ActionParseError):
        parse_executor_action("ASK_PLANNER:")


def test_parsed_action_passes_model_validator():
    a = parse_executor_action("```python\nx = 1\n```")
    assert isinstance(a, ExecutorAction)
    assert a.code == "x = 1"


def test_parse_accepts_granites_py_tag():
    # Granite 4.2 with thinking off emits its native tool-call shape, not a fence.
    # Observed 2026-09-15: good code inside <py> scored parse_error on every episode.
    raw = "<tool_call>\n<py>\nsongs = apis.spotify.show_song_library()\n</py>\n</tool_call>"
    a = parse_executor_action(raw)
    assert a.kind == "CODE"
    assert a.code == "songs = apis.spotify.show_song_library()"


def test_parse_py_tag_survives_a_stop_sequence_eating_the_close():
    # The vLLM stop sequence is "</py>", so the close is absent from the text we see.
    raw = "<tool_call>\n<py>\nprint(apis.api_docs.show_app_descriptions())\n"
    a = parse_executor_action(raw)
    assert a.kind == "CODE"
    assert a.code == "print(apis.api_docs.show_app_descriptions())"


def test_parse_fence_is_not_greedy_across_two_blocks():
    # A greedy (.*) ran from the first opening fence to the LAST closing one, so the
    # "code" carried the prose between the blocks and could never compile.
    raw = "```python\nfirst = 1\n```\nthen I thought again\n```python\nsecond = 2\n```"
    a = parse_executor_action(raw)
    assert a.code == "first = 1"


def test_parse_salvages_a_fence_truncated_by_max_tokens():
    raw = "Here goes.\n```python\nsongs = apis.spotify.show_song_library()\nprint(songs)\n"
    a = parse_executor_action(raw)
    assert a.kind == "CODE"
    assert a.code.endswith("print(songs)")


def test_parse_recovers_a_fence_closed_with_two_backticks():
    # Observed 2026-09-15 in planner_alone 383cbac_3 seed 2: a correct answer discarded
    # because the model typed `` instead of ``` to close.
    raw = '```python\nprint(apis.supervisor.complete_task(answer=42, status="success"))\n``\n'
    a = parse_executor_action(raw)
    assert a.kind == "CODE"
    assert a.code.startswith("print(apis.supervisor.complete_task(")
    assert "`" not in a.code


def test_parse_refuses_a_truncated_fence_that_is_not_valid_python():
    # Half a statement is worse than no action: it would run against a live environment.
    with pytest.raises(ActionParseError):
        parse_executor_action("```python\nsongs = apis.spotify.show_song_library(")


def test_parse_takes_whichever_code_block_comes_first():
    fence_first = "```python\na = 1\n```\n<py>\nb = 2\n</py>"
    assert parse_executor_action(fence_first).code == "a = 1"
    tag_first = "<py>\nb = 2\n</py>\n```python\na = 1\n```"
    assert parse_executor_action(tag_first).code == "b = 2"
