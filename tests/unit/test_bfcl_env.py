"""BFCL multi_turn_base adapter (bfcl-env E0). Vendored upstream data only; no network, no model."""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.bfcl_env import (
    BFCL_EXECUTOR_SYSTEM_PROMPT,
    DEFAULT_SPLIT_PATH,
    MAXIMUM_STEP_LIMIT,
    SPLIT_SEED,
    BfclCallError,
    BfclEnv,
    BfclWorld,
    _format_result,
    bfcl_task_ids,
    build_split,
    canonical,
    function_docs,
    ground_truth_script,
    load_entries,
    load_split,
    parse_calls,
    render_api_docs,
    score_turns,
    state_hash,
)
from sidekick.environments.mock_env import MockEnv
from sidekick.prefix_source import build_handoff_prefix
from sidekick.protocols.prompts import EXECUTOR_SYSTEM_PROMPT
from sidekick.protocols.schemas import ExecutorAction
from sidekick.runner import ENV_KINDS, build_parser, make_env
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits, last_observation_from_events, prefix_is_terminal
from sidekick.trajectories.eventlog import EventLog

E0 = "multi_turn_base_0"
# multi_turn_base_0, hand-copied from third_party/bfcl/bfcl_eval/data: 4 turns of 3, 2, 1 and 4
# ground-truth calls over GorillaFileSystem + TwitterAPI.
E0_TURN0 = (
    "Move 'final_report.pdf' within document directory to 'temp' directory in document. "
    "Make sure to create the directory"
)
E0_CALLS_PER_TURN = [3, 2, 1, 4]


def code(call: str) -> ExecutorAction:
    return ExecutorAction(kind="CODE", code=call, raw_output=call)


COMPLETE = ExecutorAction(kind="COMPLETE", raw_output="COMPLETE")


def _ledger() -> CostLedger:
    return CostLedger(PriceSchedule({"models": {}, "local": {}}))


def _run(tmp: Path, system: str, script: list[str], task_id: str = E0, seed: int = 1, cid: str = "c", **kw):
    executor = MockExecutor(task_scripts={task_id: list(script)})
    sys_obj = get_system(
        system, planner=MockPlanner(), executor=executor, verifier=None, limits=RunLimits(max_steps=40), **kw
    )
    run_id = f"{cid}/{system}/{seed}/{task_id}"
    log = EventLog(tmp, run_id)
    try:
        result = sys_obj.run(BfclEnv(), task_id, seed, log, _ledger())
    finally:
        log.close()
    events = [json.loads(x) for x in (tmp / run_id / "events.jsonl").read_text().splitlines() if x.strip()]
    return result, events


# --- data, split ------------------------------------------------------------------------------


def test_entries_load_with_matching_turns() -> None:
    entries = load_entries()
    assert len(entries) == 200
    e0 = entries[E0]
    assert e0["turns"][0] == E0_TURN0
    assert [len(t) for t in e0["ground_truth"]] == E0_CALLS_PER_TURN
    assert e0["involved_classes"] == ["TwitterAPI", "GorillaFileSystem"]


def test_build_split_small_fixtures() -> None:
    ids = ["a_10", "a_2", "a_1", "a_0"]
    # n_dev=0: everything is test, in numeric (not string) order.
    assert build_split(ids, seed=7, n_dev=0)["test"] == ["a_0", "a_1", "a_2", "a_10"]
    assert build_split(ids, seed=7, n_dev=4)["dev"] == ["a_0", "a_1", "a_2", "a_10"]
    two = build_split(ids, seed=7, n_dev=2)
    assert len(two["dev"]) == 2 and len(two["test"]) == 2
    assert sorted(two["dev"] + two["test"]) == sorted(ids)
    # Input order does not matter, and duplicates collapse.
    assert build_split(list(reversed(ids)) + ["a_2"], seed=7, n_dev=2) == two


def test_committed_split_is_the_builder_output() -> None:
    split = load_split(DEFAULT_SPLIT_PATH)
    assert split == build_split(list(load_entries()), seed=SPLIT_SEED, n_dev=50)
    assert split["seed"] == 20260924 and split["n_dev"] == 50 and split["n_test"] == 150
    assert not set(split["dev"]) & set(split["test"])
    assert set(split["dev"]) | set(split["test"]) == set(load_entries())


def test_bfcl_task_ids_reads_the_split_and_refuses_other_names() -> None:
    dev = load_split()["dev"]
    assert bfcl_task_ids("dev", 3) == dev[:3]
    assert bfcl_task_ids("dev", 0) == dev
    assert len(bfcl_task_ids("test", 0)) == 150
    for bad in ("test_normal", "train", "dev_50"):
        with pytest.raises(ValueError, match="bfcl split must be one of dev, test"):
            bfcl_task_ids(bad, 0)


# --- calls ------------------------------------------------------------------------------------


def test_parse_calls_fixtures() -> None:
    assert parse_calls("cd(folder='document')\nls()") == ["cd(folder='document')", "ls()"]
    assert parse_calls("[cd(folder=\"a\"), ls(a=True)]") == ["cd(folder='a')", "ls(a=True)"]
    assert parse_calls("mv(source='x', destination=ls())") == ["mv(source='x', destination=ls())"]
    for bad in ("x = ls()", "", "cd(", "apis.x.y()", "3"):
        with pytest.raises(BfclCallError):
            parse_calls(bad)


def test_format_result_matches_upstream() -> None:
    assert _format_result("a") == "a"
    assert _format_result({"k": 1}) == '{"k": 1}'
    assert _format_result(None) == "None"
    assert _format_result([1, 2]) == "[1, 2]"


def test_world_runs_calls_and_blocks_upstream_blacklist() -> None:
    world = BfclWorld(load_entries()[E0])
    assert world.run("cd(folder='document')") == '{"current_working_directory": "document"}'
    assert world.run("mkdir(dir_name='temp')") == "None"
    assert world.run("mkdir(dir_name='temp')") == (
        '{"error": "mkdir: cannot create directory \'temp\': File exists"}'
    )
    assert world.run("kill()") == "Error during execution: Function call kill is not allowed."
    assert world.run("open('x')") == "Error during execution: name 'open' is not defined"


def test_ground_truth_script_entry_0() -> None:
    script = ground_truth_script(load_entries()[E0])
    # 3 + 2 + 1 + 4 = 10 CODE blocks and 4 COMPLETEs.
    assert len(script) == 14
    assert script[0] == "```python\ncd(folder='document')\n```"
    assert [i for i, s in enumerate(script) if s == "COMPLETE"] == [3, 6, 8, 13]


# --- hashing ----------------------------------------------------------------------------------


class _Node:
    def __init__(self, name: str, parent: "_Node | None" = None) -> None:
        self.name = name
        self.parent = parent
        self._secret = object()


def test_canonical_fixtures() -> None:
    d = {"b": 1, "a": [1, (2, 3)]}
    assert canonical(d, ordered=True) == {"__dict__": [["b", 1], ["a", [1, {"__tuple__": [2, 3]}]]]}
    assert canonical(d, ordered=False) == {"__dict__": [["a", [1, {"__tuple__": [2, 3]}]], ["b", 1]]}
    assert canonical({3, 1}, ordered=True) == {"__set__": [1, 3]}
    assert canonical(datetime.datetime(2024, 9, 1, 10, 30), ordered=True) == {"__datetime__": "2024-09-01T10:30:00"}
    root = _Node("r")
    root.kids = {"c": _Node("c", root)}  # type: ignore[attr-defined]
    assert canonical(root, ordered=False) == {
        "__obj__": "_Node",
        "attrs": {
            "kids": {"__dict__": [["c", {"__obj__": "_Node", "attrs": {"name": "c", "parent": {"__ref__": "_Node"}}}]]},
            "name": "r",
            "parent": None,
        },
    }


def test_state_hash_fixture() -> None:
    node = _Node("n")
    blob = '{"X":{"__obj__":"_Node","attrs":{"name":"n","parent":null}}}'
    assert state_hash({"X": node}) == hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- the env ----------------------------------------------------------------------------------


def test_reset_prompt_and_docs() -> None:
    env = BfclEnv()
    obs = env.reset(E0, 1)
    assert obs.text == E0_TURN0 and env.instruction == E0_TURN0 and obs.done is False
    docs = function_docs(["TwitterAPI", "GorillaFileSystem"])
    # posting_api.json has 14 schemas, gorilla_file_system.json 18 (one per line upstream).
    assert len(docs) == 14 + 18
    assert env.api_docs_prompt == render_api_docs(docs)
    assert env.api_docs_prompt.count('{"name": ') == 32
    assert env.executor_system_prompt == BFCL_EXECUTOR_SYSTEM_PROMPT
    assert MockEnv().executor_system_prompt == EXECUTOR_SYSTEM_PROMPT


def test_complete_advances_turns_then_ends() -> None:
    env = BfclEnv()
    env.reset(E0, 1)
    texts, dones = [], []
    for _ in range(4):
        obs = env.step(COMPLETE)
        texts.append(obs.text)
        dones.append(obs.done)
    assert dones == [False, False, False, True]
    assert texts[0].startswith("The user's next request: Perform a detailed search using grep")
    assert texts[3] == "All of the user's requests are finished."


def test_invalid_block_runs_nothing() -> None:
    env = BfclEnv()
    env.reset(E0, 1)
    before = env.snapshot_hash()
    obs = env.step(code("mkdir(dir_name='zz')\nx = 1"))
    assert obs.text.startswith("Error: line 2 is not a single function call")
    assert env.turn_calls == [[], [], [], []]
    # Only the step counter moved (steps_in_turn is part of the replay hash).
    env2 = BfclEnv()
    env2.reset(E0, 1)
    assert state_hash(env._world.instances) == state_hash(env2._world.instances)
    assert before != env.snapshot_hash()


def test_force_quit_after_the_upstream_step_limit() -> None:
    env = BfclEnv()
    env.reset(E0, 1)
    for i in range(MAXIMUM_STEP_LIMIT):
        assert env.step(code("pwd()")).done is False, i
    obs = env.step(code("pwd()"))  # the 21st step on one request
    assert obs.done is True and "Forced to quit after 20 steps" in obs.text
    result = env.evaluate()
    assert result["success"] is False and result["report"]["force_quit"] is True


def test_score_turns_ground_truth_passes_every_turn() -> None:
    entry = load_entries()[E0]
    model_turns = [[[c] for c in turn] for turn in entry["ground_truth"]]
    scored = score_turns(entry, model_turns)
    assert (scored["n_checked"], scored["n_passed"], scored["all_checked_pass"]) == (4, 4, True)
    assert scored["model_state_hash"] == scored["truth_state_hash"]
    nothing = score_turns(entry, [[], [], [], []])
    assert (nothing["n_checked"], nothing["n_passed"]) == (4, 0)
    assert nothing["turns"][0]["error_type"] == "multi_turn:empty_turn_model_response"


# --- episodes through the loop ----------------------------------------------------------------


def test_ground_truth_episode_breaks_on_done_not_on_complete(tmp_path: Path) -> None:
    result, events = _run(tmp_path, "executor_alone", ground_truth_script(load_entries()[E0]))
    # Hand count: 10 CODE + 4 COMPLETE = 14 steps; the first three COMPLETEs do not end it.
    assert result.steps == 14 and result.error_type is None
    assert result.success is True and result.tgc == 1.0 and result.goal_pass_rate == 1.0
    completes = [e for e in events if e["event_type"] == "observation" and e["payload"].get("kind") == "COMPLETE"]
    assert [c["payload"]["done"] for c in completes] == [False, False, False, True]
    report = [e for e in events if e["event_type"] == "evaluate"][0]["payload"]["report"]
    assert report["final_state_hash_match"] is True and report["n_steps_per_turn"] == [3, 2, 1, 4]


def test_noop_and_partial_episodes_score_by_turn(tmp_path: Path) -> None:
    noop, _ = _run(tmp_path, "executor_alone", ["COMPLETE"] * 4, cid="noop")
    assert (noop.success, noop.goal_pass_rate, noop.steps) == (False, 0.0, 4)
    gt = load_entries()[E0]["ground_truth"]
    first_turn_only = [f"```python\n{c}\n```" for c in gt[0]] + ["COMPLETE"] * 4
    part, _ = _run(tmp_path, "executor_alone", first_turn_only, cid="part")
    # Turn 0 passes; turns 1-3 ran no call. 1 of 4 checked turns.
    assert (part.success, part.goal_pass_rate) == (False, 0.25)


def test_prefix_handoff_replays_across_a_turn_boundary(tmp_path: Path) -> None:
    script = ground_truth_script(load_entries()[E0])
    _run(tmp_path, "executor_alone", script, cid="src")
    source = tmp_path / "src"
    # m = 4 ends on turn 0's COMPLETE, which does not end a BFCL episode.
    built = build_handoff_prefix(source, "executor_alone", E0, 1, 4, BfclEnv())
    assert (built.hash_ok, built.effective_m, built.n_source_actions, built.handoff_occurred) == (True, 4, 14, True)
    last = last_observation_from_events(list(built.prefix.events))
    assert last.done is False
    assert prefix_is_terminal(list(built.prefix.events), last, complete_ends_episode=False) is False
    # Every prefix depth replays to the recorded hash.
    for m in range(0, 15):
        assert build_handoff_prefix(source, "executor_alone", E0, 1, m, BfclEnv()).hash_ok, m
    # The whole prefix_handoff system: replay 4 actions, executor finishes turns 1-3.
    result, events = _run(
        tmp_path, "prefix_handoff", script[4:], cid="ph",
        source_campaign=str(source), source_system="executor_alone", m=4,
    )
    assert result.success is True and result.error_type is None


# --- the globals() replay trap ----------------------------------------------------------------


def test_two_episodes_in_one_process_cannot_see_each_other() -> None:
    env_a, env_b = BfclEnv(), BfclEnv()
    h0 = env_a.reset(E0, 1).env_state_hash
    assert env_a.step(code("mkdir(dir_name='zz_trap')")).text == "mkdir(dir_name='zz_trap') -> None"
    assert env_a.snapshot_hash() != h0
    # A second live env on the same entry starts clean, and so does a re-reset of the first.
    assert env_b.reset(E0, 1).env_state_hash == h0
    assert env_b.step(code("mkdir(dir_name='zz_trap')")).text == "mkdir(dir_name='zz_trap') -> None"
    assert env_a.reset(E0, 2).env_state_hash == h0
    assert env_a.step(code("mkdir(dir_name='zz_trap')")).text == "mkdir(dir_name='zz_trap') -> None"
    # The adapter never populates upstream's globals() cache.
    from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils

    assert [k for k in vars(multi_turn_utils) if k.endswith("_instance")] == []


def test_upstream_executor_does_leak_state_between_calls() -> None:
    """The trap itself, so the test above is known to be testing something real."""
    BfclEnv()  # puts the vendored package on sys.path
    from bfcl_eval.eval_checker.multi_turn_eval import multi_turn_utils

    entry = load_entries()[E0]
    name = f"trap_{uuid.uuid4().hex}"
    call = ["mkdir(dir_name='zz_trap')"]
    try:
        first, _ = multi_turn_utils.execute_multi_turn_func_call(
            call, entry["initial_config"], entry["involved_classes"], name, E0
        )
        second, _ = multi_turn_utils.execute_multi_turn_func_call(
            call, entry["initial_config"], entry["involved_classes"], name, E0
        )
    finally:
        for key in [k for k in vars(multi_turn_utils) if name in k]:
            delattr(multi_turn_utils, key)
    assert first == ["None"]
    assert second == ['{"error": "mkdir: cannot create directory \'zz_trap\': File exists"}']


# --- runner wiring ----------------------------------------------------------------------------


def test_runner_knows_bfcl() -> None:
    assert "bfcl" in ENV_KINDS
    assert isinstance(make_env("bfcl", "x", {}), BfclEnv)
    args = build_parser().parse_args(["--system", "executor_alone", "--out", "/tmp/x", "--env", "bfcl"])
    assert args.env == "bfcl"
