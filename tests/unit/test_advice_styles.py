"""Advice-prompt styles after D2 (plan 2026-09-24): "structured" is added; the B2 styles do not move.

J10 arms 8 and 9 run the "correction" style (configs/j10_advise_k1_fullctx.yaml and
configs/j10_advise_k10_fullctx.yaml set no correct_prompt) and arm 12 runs "neutral"
(configs/j10_advise_k10_neutral.yaml). Their prompts are compared here against literal text
typed from the prompt as registered, not against the builder, so a change to either wording
fails even if every call site moved with it. No network: the Codex planner's subprocess call is
replaced by a stub.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import sidekick.agents.planner as planner_mod
from sidekick.agents.advice_styles import build_structured_advice_prompt
from sidekick.agents.planner import (
    CORRECT_PROMPT_STYLES,
    CodexExecConfig,
    CodexExecPlanner,
    build_advice_prompt,
    build_correct_prompt,
)
from sidekick.agents.vllm_planner import VllmPlanner
from sidekick.protocols.schemas import Usage
from sidekick.runner import make_planner

REPO = Path(__file__).resolve().parents[2]
PACKET = planner_mod._default_packet("copy_hello", "copy the file", "ctx")
DELTA = "line a\nline b"
# The two lines every style shares, typed out.
TAIL = f"packet:\n{PACKET.model_dump_json()}\n" "transcript_delta:\nline a\nline b\n"
CORRECTION = "The executor needs a correction. Reply with concise correction text only.\n" + TAIL
NEUTRAL = (
    "Advise the executor on how to proceed with this task: say what it should do next. "
    "You may include code.\n" + TAIL
)
STRUCTURED = (
    "Direct the executor's next steps, as a manager directs a worker. Reply in exactly this structure:\n"
    "GOAL: the subgoal the executor should complete next.\n"
    "STEPS: numbered concrete steps to reach it; include code where it helps.\n"
    "CHECK: how the executor can tell the subgoal is done.\n" + TAIL
)


def _usage() -> Usage:
    return Usage(model="mock-planner", provider="mock", input_tokens=10, output_tokens=8)


def test_correction_and_neutral_are_byte_identical_to_the_registered_text():
    assert build_advice_prompt(PACKET, DELTA) == CORRECTION
    assert build_advice_prompt(PACKET, DELTA, "correction") == CORRECTION
    assert build_correct_prompt(PACKET, DELTA) == CORRECTION
    assert build_advice_prompt(PACKET, DELTA, "neutral") == NEUTRAL


def test_the_j10_advise_arms_use_the_styles_pinned_above():
    def style(stem: str) -> str:
        cfg = yaml.safe_load((REPO / "configs" / f"{stem}.yaml").read_text(encoding="utf-8"))
        return str((cfg.get("planner") or {}).get("correct_prompt", "correction"))

    assert style("j10_advise_k1_fullctx") == "correction"
    assert style("j10_advise_k10_fullctx") == "correction"
    assert style("j10_advise_k10_neutral") == "neutral"


def test_structured_is_the_fixed_text():
    assert build_advice_prompt(PACKET, DELTA, "structured") == STRUCTURED
    assert build_structured_advice_prompt(PACKET, DELTA) == STRUCTURED


def test_structured_differs_from_neutral_in_its_instruction_lines_only():
    neutral = build_advice_prompt(PACKET, DELTA, "neutral").splitlines()
    structured = build_advice_prompt(PACKET, DELTA, "structured").splitlines()
    # neutral has one instruction line, structured four; packet + 2 delta lines follow in both.
    assert structured[4:] == neutral[1:]
    assert len(structured[4:]) == 5  # "packet:", the json, "transcript_delta:", "line a", "line b"
    assert [line.split(":")[0] for line in structured[1:4]] == ["GOAL", "STEPS", "CHECK"]


def test_the_style_list_gained_structured_and_nothing_else():
    assert CORRECT_PROMPT_STYLES == ("correction", "neutral", "structured")


@pytest.mark.parametrize("style", ["friendly", "Structured", ""])
def test_an_unknown_style_still_raises(style: str):
    with pytest.raises(ValueError, match="unknown correct_prompt style"):
        build_advice_prompt(PACKET, "d", style)
    with pytest.raises(ValueError):
        VllmPlanner(model="m", base_url="http://127.0.0.1:1/v1", correct_prompt=style)
    with pytest.raises(ValueError):
        make_planner({"planner": {"type": "mock", "correct_prompt": style}})


def test_structured_flows_through_the_runner_into_both_backends(tmp_path: Path):
    # runner.make_planner and VllmPlanner validate against CORRECT_PROMPT_STYLES; neither changed.
    assert make_planner({"planner": {"type": "codex", "correct_prompt": "structured"}}).config.correct_prompt == "structured"
    local = make_planner({"planner": {"type": "vllm", "model": "m", "correct_prompt": "structured"}})
    assert local.correct_prompt == "structured"

    captured: list[str] = []

    def fake_invoke(prompt, schema_path=None, timeout_s=None, scratch=None):
        captured.append(prompt)
        return "advice", _usage(), None

    codex = CodexExecPlanner(CodexExecConfig(scratch_parent=str(tmp_path), correct_prompt="structured"))
    codex._invoke = fake_invoke  # type: ignore[method-assign]
    codex.correct(PACKET, DELTA)
    assert captured == [STRUCTURED]
