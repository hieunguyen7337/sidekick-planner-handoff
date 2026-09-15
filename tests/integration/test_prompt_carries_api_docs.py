"""The loop must hand the executor the API documentation, not its fingerprint.

The unit tests next to this one check that the environment can *render* docs. This one
checks the seam that actually broke: `loop._executor_messages` was being called with
`env.api_docs_digest`, so a correct renderer and a correct prompt builder still produced
a prompt containing 64 hex characters. The bug lived entirely in the call site, which is
why it has to be tested from a real run rather than from either piece alone.
"""
from __future__ import annotations

from sidekick.environments.mock_env import _API_DOCS


def _user_text(executor) -> str:
    assert executor.last_messages, "executor was never called"
    return "\n".join(
        m.get("content", "") for m in executor.last_messages if m.get("role") == "user"
    )


def test_executor_prompt_contains_the_api_docs(run_system):
    _, _, _, _, executor = run_system("executor_alone")
    text = _user_text(executor)
    for line in _API_DOCS.strip().splitlines():
        assert line.strip() in text, f"missing api doc line: {line!r}"


def test_executor_prompt_does_not_contain_the_digest(run_system):
    from sidekick.environments.mock_env import MockEnv

    _, _, _, _, executor = run_system("executor_alone")
    assert MockEnv().api_docs_digest not in _user_text(executor)


def test_planner_using_system_also_gets_the_docs(run_system):
    # prompt_only calls the planner once and then runs the executor; both sides need the
    # docs, and the planner call site was the one that was wrong.
    _, _, _, planner, executor = run_system("prompt_only")
    assert "read(name: str) -> str" in _user_text(executor)
