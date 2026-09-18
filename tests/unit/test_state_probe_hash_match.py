"""A10 defect 1: the probe's hash_match off-by-one (known-answer test).

Before the fix, probe_step compared the probe world's hash after the model's
step against the gold observation of the NEXT step (pairs[k+1][1]); a true
match was impossible and every recorded hash_match was False. The known
answer here is built by construction: identical code executed against an
identically replayed prefix MUST match.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "setup"))

from sidekick.environments.mock_env import MockEnv  # noqa: E402
from sidekick.protocols.schemas import Event, ExecutorAction  # noqa: E402
import state_probe as sp  # noqa: E402

ACTIONS = [
    ExecutorAction(kind="CODE", code='write("notes.txt", "a")'),
    ExecutorAction(kind="CODE", code='write("outbox.txt", "hello world")'),
    ExecutorAction(kind="CODE", code="pass"),
]


class FixedExecutor:
    """Always returns one fixed action body, temperature-0 shaped."""

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def complete(self, messages, **kw):
        return self.raw, None


def _gold_pairs() -> list[tuple[ExecutorAction, Event]]:
    """Build (action, its observation) pairs by executing every action in a
    fresh gold world -- the same shape state_probe.executed_pairs produces
    from a real run's events.jsonl: the observation Event carries the recorded
    env_state_hash and the observation text in its payload."""
    world = MockEnv()
    world.reset("task-1", 1)
    pairs = []
    for i, action in enumerate(ACTIONS, start=1):
        obs = world.step(action)
        event = Event(
            run_id="run-1",
            task_id="task-1",
            system="planner_alone",
            seed=1,
            step=i,
            ts="2026-09-19T00:00:00+00:00",
            actor="system",
            event_type="observation",
            payload={"text": obs.text},
            env_state_hash=obs.env_state_hash,
        )
        pairs.append((action, event))
    world.close()
    return pairs


def _replay_prefix(world: MockEnv, pairs, k: int) -> None:
    world.reset("task-1", 1)
    for i in range(k):
        world.step(pairs[i][0])


def test_identical_code_on_replayed_prefix_hash_must_match():
    pairs = _gold_pairs()
    world = MockEnv()
    try:
        _replay_prefix(world, pairs, 1)
        raw = "```python\n" + pairs[1][0].code + "\n```"
        rec = sp.probe_step(
            FixedExecutor(raw), world, pairs, 1,
            instruction="instr", api_docs="docs",
        )
    finally:
        world.close()
    assert rec["hash_match_defined"] is True
    # The known answer: byte-identical code against an identically replayed
    # prefix produced the same env_state_hash in the gold world, so it MUST
    # match here. Before the A10 fix this asserted-True value was False.
    assert rec["hash_match"] is True


def test_different_code_does_not_hash_match():
    pairs = _gold_pairs()
    world = MockEnv()
    try:
        _replay_prefix(world, pairs, 1)
        rec = sp.probe_step(
            FixedExecutor('```python\nwrite("outbox.txt", "wrong")\n```'),
            world, pairs, 1,
            instruction="instr", api_docs="docs",
        )
    finally:
        world.close()
    assert rec["hash_match_defined"] is True
    assert rec["hash_match"] is False


def test_hash_match_compares_step_just_executed_not_next():
    """The pre-fix bug in one assertion: the probe world's hash equals the gold
    observation of the step just executed (pairs[k][1]); it can never equal the
    observation AFTER the next gold step (pairs[k+1][1]) because the io log
    only grows."""
    pairs = _gold_pairs()
    k = 0
    probe_world = MockEnv()
    try:
        _replay_prefix(probe_world, pairs, k)
        rec = sp.probe_step(
            FixedExecutor("```python\n" + pairs[k][0].code + "\n```"),
            probe_world, pairs, k,
            instruction="instr", api_docs="docs",
        )
    finally:
        probe_world.close()
    executed_obs_hash = pairs[k][1].env_state_hash
    next_obs_hash = pairs[k + 1][1].env_state_hash
    assert executed_obs_hash != next_obs_hash  # the two targets really differ
    assert rec["hash_match"] is True  # ...and the metric now aims at the right one


def test_last_step_has_no_next_gold_pair_but_hash_still_defined():
    pairs = _gold_pairs()
    k = len(pairs) - 1
    world = MockEnv()
    try:
        _replay_prefix(world, pairs, k)
        rec = sp.probe_step(
            FixedExecutor("```python\n" + pairs[k][0].code + "\n```"),
            world, pairs, k,
            instruction="instr", api_docs="docs",
        )
    finally:
        world.close()
    # No next step -> state_equivalent undefined, but hash_match is defined
    # (its target is the observation of the step just executed).
    assert rec["state_equivalent_defined"] is False
    assert rec["hash_match_defined"] is True
    assert rec["hash_match"] is True
