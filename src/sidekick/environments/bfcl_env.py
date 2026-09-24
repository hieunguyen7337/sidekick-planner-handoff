"""BFCL `multi_turn_base` as a sidekick environment (plan Wave E, E0).

One episode is one BFCL entry: a scripted user speaks in 1-7 turns, and the agent answers each
turn by calling the functions of the entry's backend classes (file system, trading bot, travel
booking, ...). The backend is upstream's own Python, vendored unmodified under
``third_party/bfcl/`` at the commit in ``UPSTREAM_COMMIT``.

How the harness's actions map onto BFCL:

- ``CODE``: a ```python block of function calls, one per line (upstream's bracketed list form
  ``[f(x=1), g()]`` is accepted too). The whole block is validated first; a line that is not a
  bare call executes nothing and comes back as an error. This is one BFCL "step".
- ``COMPLETE``: ends the current user turn, the analogue of upstream's model reply with no
  function call. On a non-final turn the observation is the next user message and
  ``done=False``; on the final turn ``done=True``. ``complete_ends_episode`` is False, so the
  loop keeps going until ``done``.
- ``REPORT`` / ``ASK_PLANNER`` never reach ``step``: the loop handles them.

Two hashes, for two different jobs:

- ``snapshot_hash()`` is for replay. It covers the public attributes of every backend instance
  in insertion order, the private state that decides future results (``_random``'s state and the
  file system's working directory), and the turn position. Unlike AppWorld's I/O-log hash it
  sees a state change that prints nothing.
- ``state_hash()`` is for scoring. It covers the public attributes only, with dict and set order
  ignored, which is what upstream's ``state_checker`` compares (it skips ``_``-prefixed
  attributes and compares with ``==``).

⚠ Upstream's ``execute_multi_turn_func_call`` keeps instances in module ``globals()`` keyed by
model name and entry id and builds one only when the key is absent, so replaying an entry in
the same process starts from the mutated instance. This adapter never calls it during an
episode: every ``reset`` builds fresh instances from the entry's ``initial_config``.

The ``seed`` passed to ``reset`` does not reach the backend. Upstream seeds each backend's RNG
from the scenario and fixes the clock, so the environment is deterministic per entry; the seed
only varies the executor's sampling.
"""
from __future__ import annotations

import ast
import copy
import datetime
import decimal
import functools
import hashlib
import importlib
import inspect
import json
import random
import sys
from pathlib import Path
from typing import Any

from sidekick.environments.base import BaseEnv
from sidekick.protocols.schemas import ExecutorAction, Observation

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BFCL_ROOT = REPO_ROOT / "third_party" / "bfcl"
DEFAULT_SPLIT_PATH = REPO_ROOT / "data" / "bfcl_split_20260924.json"
UPSTREAM_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
BFCL_CATEGORY = "multi_turn_base"
BFCL_SPLITS = ("dev", "test")
SPLIT_SEED = 20260924
N_DEV = 50

# bfcl_eval/constants/default_prompts.py:1. More steps than this in one user turn and upstream
# force-quits the entry, which then fails.
MAXIMUM_STEP_LIMIT = 20
# bfcl_eval/eval_checker/multi_turn_eval/multi_turn_utils.py: names upstream refuses to eval.
_BLOCKED_CALLS = ("kill", "exit", "quit", "remove", "unlink", "popen", "Popen", "run")

_API_USAGE_PREAMBLE = (
    "You are helping a user by calling the functions listed below, from a Python session.\n"
    "Call a function as a plain call with keyword arguments, one call per line, for example "
    "cd(folder='document'). Each line must be a single function call: no print, no "
    "variables, no other Python. The environment runs every call and shows you what it "
    "returned in the next observation.\n"
    "If no function can do what is asked, or the request lacks a value a function needs, say "
    "so with REPORT: instead of guessing.\n"
    "The user's requests arrive one at a time. When the current request is done, finish it "
    "with COMPLETE, or COMPLETE: <answer> when the user asked a question. The next request, "
    "if there is one, then arrives as an observation.\n"
    "Only the functions below exist. Each is given as its JSON schema.\n"
    "\nAvailable functions:\n"
)

# AppWorld's executor system prompt (protocols/prompts.py) with the example and the calling
# convention made BFCL's. Same four actions, same wording otherwise: one protocol, two envs.
BFCL_EXECUTOR_SYSTEM_PROMPT: str = (
    "You are an executor acting in a live environment. Each turn you emit exactly "
    "one action and nothing else.\n"
    "\n"
    "The four actions:\n"
    "  a ```python fenced block, to call functions\n"
    "  ASK_PLANNER: <what you need decided>\n"
    "  REPORT: <what you found>\n"
    "  COMPLETE, or COMPLETE: <answer> when the request asked a question\n"
    "\n"
    "A complete turn looks like this, in full:\n"
    "\n"
    "```python\n"
    "cd(folder='document')\n"
    "```\n"
    "\n"
    "That is the entire reply. Do not reason out loud first, do not emit more than "
    "one action, and do not write what you expect the output to be: the environment "
    "runs your calls and puts the real output in the transcript next turn. Everything "
    "after the first action is discarded. When you do not know what a function returns, "
    "call it and look rather than guessing.\n"
    "\n"
    "Both failure modes here are measured, on 2026-09-15 in another environment, and both "
    "scored 0.0 on tasks the model could otherwise do. granite-4.2-8b wrote a correct call, "
    "then invented a plausible result for it and reasoned over the invention until its "
    "budget ran out. granite-4.2-3b narrated its intentions for 1,661 tokens and never "
    "emitted a single line of code."
)


class BfclCallError(ValueError):
    """A CODE block that is not a list of bare function calls."""


# --- vendored upstream ------------------------------------------------------------------------


def ensure_vendored(root: str | Path = DEFAULT_BFCL_ROOT) -> None:
    """Put the vendored ``bfcl_eval`` package on sys.path (idempotent)."""
    path = str(Path(root).resolve())
    if path not in sys.path:
        sys.path.insert(0, path)


def backend_class(class_name: str, root: str | Path = DEFAULT_BFCL_ROOT) -> type:
    ensure_vendored(Path(root))
    from bfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING

    module = importlib.import_module(CLASS_FILE_PATH_MAPPING[class_name])
    return getattr(module, class_name)


def _stateless_classes(root: Path) -> tuple[str, ...]:
    ensure_vendored(root)
    from bfcl_eval.constants.executable_backend_config import STATELESS_CLASSES

    return tuple(STATELESS_CLASSES)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _id_order(entry_id: str) -> tuple[str, int]:
    prefix, _, num = entry_id.rpartition("_")
    return (prefix, int(num)) if num.isdigit() else (entry_id, -1)


@functools.lru_cache(maxsize=4)
def _load_entries_cached(root: str) -> dict[str, dict[str, Any]]:
    data = Path(root) / "bfcl_eval" / "data"
    questions = _read_jsonl(data / f"BFCL_v4_{BFCL_CATEGORY}.json")
    answers = {a["id"]: a["ground_truth"] for a in _read_jsonl(data / "possible_answer" / f"BFCL_v4_{BFCL_CATEGORY}.json")}
    entries: dict[str, dict[str, Any]] = {}
    for q in questions:
        turns = [
            "\n".join(str(m.get("content") or "") for m in turn if m.get("role") == "user")
            for turn in q["question"]
        ]
        gt = answers[q["id"]]
        if len(gt) != len(turns):
            raise ValueError(f"{q['id']}: {len(turns)} question turns but {len(gt)} ground-truth turns")
        entries[q["id"]] = {
            "id": q["id"],
            "turns": turns,
            "initial_config": q["initial_config"],
            "involved_classes": list(q["involved_classes"]),
            "ground_truth": [list(t) for t in gt],
        }
    return entries


def load_entries(root: str | Path = DEFAULT_BFCL_ROOT) -> dict[str, dict[str, Any]]:
    """All ``multi_turn_base`` entries keyed by id. Treat the result as read-only (it is cached)."""
    return _load_entries_cached(str(Path(root).resolve()))


def function_docs(involved_classes: list[str], root: str | Path = DEFAULT_BFCL_ROOT) -> list[dict]:
    """The function schemas shown to the model, as upstream's populate step builds them."""
    ensure_vendored(Path(root))
    from bfcl_eval.constants.executable_backend_config import MULTI_TURN_FUNC_DOC_FILE_MAPPING

    doc_dir = Path(root) / "bfcl_eval" / "data" / "multi_turn_func_doc"
    docs: list[dict] = []
    for class_name in involved_classes:
        docs.extend(_read_jsonl(doc_dir / MULTI_TURN_FUNC_DOC_FILE_MAPPING[class_name]))
    return docs


def render_api_docs(docs: list[dict]) -> str:
    """Preamble plus one compact JSON schema per line."""
    return _API_USAGE_PREAMBLE + "\n".join(json.dumps(d, ensure_ascii=False) for d in docs)


# --- split ------------------------------------------------------------------------------------


def build_split(ids: list[str], seed: int = SPLIT_SEED, n_dev: int = N_DEV) -> dict[str, Any]:
    """Seeded dev/test split of entry ids. Unstratified: the scoping doc names no stratum.

    Ids are put in numeric order first, so the result does not depend on file order.
    """
    ordered = sorted(set(ids), key=_id_order)
    shuffled = list(ordered)
    random.Random(seed).shuffle(shuffled)
    dev = sorted(shuffled[:n_dev], key=_id_order)
    test = sorted(shuffled[n_dev:], key=_id_order)
    return {
        "category": BFCL_CATEGORY,
        "seed": seed,
        "n_dev": len(dev),
        "n_test": len(test),
        "dev": dev,
        "test": test,
    }


def load_split(path: str | Path = DEFAULT_SPLIT_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bfcl_task_ids(split: str, n: int, path: str | Path = DEFAULT_SPLIT_PATH) -> list[str]:
    """Entry ids of ``split`` ("dev" or "test"); the first ``n`` when ``n > 0``.

    Any other split name raises: AppWorld's names (test_normal, train, ...) mean nothing here,
    and silently running dev under a test name is the mistake a confirmatory read cannot afford.
    """
    if split not in BFCL_SPLITS:
        raise ValueError(f"bfcl split must be one of {', '.join(BFCL_SPLITS)}; got {split!r}")
    ids = list(load_split(path)[split])
    if n > 0:
        ids = ids[:n]
    return ids


# --- calls ------------------------------------------------------------------------------------


def parse_calls(code: str) -> list[str]:
    """Split an executor code block into BFCL call strings, one per call.

    Accepts one bare call per statement, or a bracketed list/tuple of bare calls (upstream's
    output format). Anything else raises ``BfclCallError`` and nothing runs.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise BfclCallError(f"not valid Python: {exc.msg} (line {exc.lineno})") from exc
    calls: list[str] = []
    for stmt in tree.body:
        value = stmt.value if isinstance(stmt, ast.Expr) else None
        items = list(value.elts) if isinstance(value, (ast.List, ast.Tuple)) else [value]
        for node in items:
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                raise BfclCallError(
                    f"line {stmt.lineno} is not a single function call; write each call on its "
                    "own line, e.g. cd(folder='document'), with no print or assignment"
                )
            calls.append(ast.unparse(node))
    if not calls:
        raise BfclCallError("no function call found")
    return calls


def ground_truth_script(entry: dict[str, Any]) -> list[str]:
    """The entry's ground truth as executor replies: one CODE block per call, COMPLETE per turn.

    This is the trajectory spike (a) replays and spike (c) measures depth on. A model that
    batches several calls into one block takes fewer steps than this.
    """
    script: list[str] = []
    for turn in entry["ground_truth"]:
        script.extend(f"```python\n{call}\n```" for call in turn)
        script.append("COMPLETE")
    return script


def _format_result(result: Any) -> str:
    """Stringify a call's return value exactly as upstream's executor does."""
    if type(result) == str:  # noqa: E721 - upstream's check, kept verbatim
        return result
    if type(result) == dict:  # noqa: E721
        try:
            return json.dumps(result)
        except Exception:  # noqa: BLE001 - upstream falls back to str()
            return str(result)
    return str(result)


class BfclWorld:
    """Fresh backend instances for one entry, and the calls that run against them.

    Methods are bound by name across all involved classes, later classes winning a clash, as in
    upstream. Calls are evaluated against that name table only (no builtins, no module
    globals), so a call can reach the backend's public methods and nothing else.
    """

    def __init__(self, entry: dict[str, Any], root: str | Path = DEFAULT_BFCL_ROOT) -> None:
        root = Path(root)
        stateless = _stateless_classes(root)
        self.instances: dict[str, Any] = {}
        self.namespace: dict[str, Any] = {}
        for class_name in entry["involved_classes"]:
            instance = backend_class(class_name, root)()
            if class_name not in stateless:
                config = copy.deepcopy(entry["initial_config"].get(class_name, {}))
                instance._load_scenario(config, long_context=False)
            self.instances[class_name] = instance
            for name, method in inspect.getmembers(instance, predicate=inspect.ismethod):
                if not name.startswith("_"):
                    self.namespace[name] = method

    def run(self, call: str) -> str:
        name = call.split("(")[0].strip()
        try:
            if name in _BLOCKED_CALLS:
                raise Exception(f"Function call {name} is not allowed.")
            result = eval(call, {"__builtins__": {}}, self.namespace)  # noqa: S307
        except Exception as exc:  # noqa: BLE001 - every failure is an observation, as upstream
            return f"Error during execution: {exc}"
        return _format_result(result)

    def run_all(self, calls: list[str]) -> list[str]:
        return [self.run(c) for c in calls]


# --- hashing ----------------------------------------------------------------------------------


def canonical(obj: Any, *, ordered: bool, _stack: tuple[Any, ...] = ()) -> Any:
    """JSON-safe canonical form of backend state.

    Objects contribute their public attributes only (the ``_`` rule of upstream's checker; it
    also drops the file system's wall-clock ``_last_modified``). A back-reference to an object
    already being serialised (a directory's ``parent``) becomes a ``__ref__`` marker. With
    ``ordered=False`` dict entries are sorted, so two states upstream's ``==`` calls equal get
    one form.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        items = [canonical(x, ordered=ordered, _stack=_stack) for x in obj]
        return {"__tuple__": items} if isinstance(obj, tuple) else items
    if isinstance(obj, dict):
        pairs = [
            [canonical(k, ordered=ordered, _stack=_stack), canonical(v, ordered=ordered, _stack=_stack)]
            for k, v in obj.items()
        ]
        if not ordered:
            pairs.sort(key=lambda p: json.dumps(p[0], sort_keys=True))
        return {"__dict__": pairs}
    if isinstance(obj, (set, frozenset)):
        items = [canonical(x, ordered=ordered, _stack=_stack) for x in obj]
        return {"__set__": sorted(items, key=lambda x: json.dumps(x, sort_keys=True))}
    if isinstance(obj, (datetime.date, datetime.time)):
        return {"__datetime__": obj.isoformat()}
    if isinstance(obj, datetime.timedelta):
        return {"__timedelta__": obj.total_seconds()}
    if isinstance(obj, decimal.Decimal):
        return {"__decimal__": str(obj)}
    if hasattr(obj, "__dict__"):
        if any(obj is s for s in _stack):
            return {"__ref__": type(obj).__name__}
        attrs = {
            k: canonical(v, ordered=ordered, _stack=_stack + (obj,))
            for k, v in sorted(vars(obj).items())
            if not k.startswith("_")
        }
        return {"__obj__": type(obj).__name__, "attrs": attrs}
    return {"__repr__": repr(obj)}


def _sha(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def state_hash(instances: dict[str, Any]) -> str:
    """Scoring hash: public attributes, order-insensitive (what upstream's state_checker compares)."""
    return _sha({name: canonical(inst, ordered=False) for name, inst in instances.items()})


def _private_replay_state(instance: Any) -> dict[str, Any]:
    """The private attributes that decide future results: the RNG and the working directory."""
    extra: dict[str, Any] = {}
    rng = getattr(instance, "_random", None)
    if isinstance(rng, random.Random):
        extra["random"] = hashlib.sha256(repr(rng.getstate()).encode("utf-8")).hexdigest()
    cwd = getattr(instance, "_current_dir", None)
    if cwd is not None:
        path: list[str] = []
        node = cwd
        while node is not None:
            path.append(str(getattr(node, "name", "")))
            node = getattr(node, "parent", None)
        extra["cwd"] = list(reversed(path))
    return extra


# --- scoring ----------------------------------------------------------------------------------


def score_turns(
    entry: dict[str, Any],
    model_turns: list[list[list[str]]],
    root: str | Path = DEFAULT_BFCL_ROOT,
) -> dict[str, Any]:
    """Per-turn checks as upstream's ``multi_turn_checker`` defines them, without its early exit.

    ``model_turns[t]`` is the model's steps in turn t, each step the list of calls it ran.
    Both the model's calls and the ground truth are re-executed on fresh instances, turn by
    turn, exactly as the checker does. A turn whose ground truth is empty is not checked
    (upstream ``continue``s past it). A checked turn passes when the model ran at least one
    call in it, ``state_checker`` finds the public state equal to the ground truth's, and
    ``response_checker`` finds every ground-truth result of the turn among all the model's
    results so far. Upstream stops at the first failed turn; this keeps going so the per-turn
    pass fraction exists, and ``all_checked_pass`` is upstream's verdict.
    """
    ensure_vendored(Path(root))
    from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
        response_checker,
        state_checker,
    )

    gt_turns = entry["ground_truth"]
    model = BfclWorld(entry, root)
    truth = BfclWorld(entry, root)
    all_model_results: list[str] = []
    turns: list[dict[str, Any]] = []
    for t, gt_calls in enumerate(gt_turns):
        steps = model_turns[t] if t < len(model_turns) else []
        for calls in steps:
            all_model_results.extend(model.run_all(calls))
        gt_results = truth.run_all(gt_calls)
        if not gt_calls:
            turns.append({"turn": t, "checked": False, "valid": None, "error_type": None})
            continue
        if not steps:
            turns.append(
                {"turn": t, "checked": True, "valid": False, "error_type": "multi_turn:empty_turn_model_response"}
            )
            continue
        result = state_checker(model.instances, truth.instances)
        if result["valid"]:
            result = response_checker(all_model_results, gt_results, t)
        turns.append(
            {
                "turn": t,
                "checked": True,
                "valid": bool(result["valid"]),
                "error_type": None if result["valid"] else str(result.get("error_type")),
            }
        )
    checked = [x for x in turns if x["checked"]]
    return {
        "turns": turns,
        "n_checked": len(checked),
        "n_passed": sum(1 for x in checked if x["valid"]),
        "all_checked_pass": all(x["valid"] for x in checked),
        "model_state_hash": state_hash(model.instances),
        "truth_state_hash": state_hash(truth.instances),
    }


# --- the environment --------------------------------------------------------------------------


class BfclEnv(BaseEnv):
    """One BFCL ``multi_turn_base`` entry per episode. See the module docstring."""

    complete_ends_episode = False

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else DEFAULT_BFCL_ROOT
        if not (self.root / "bfcl_eval" / "data" / f"BFCL_v4_{BFCL_CATEGORY}.json").is_file():
            raise FileNotFoundError(f"no vendored BFCL data under {self.root}")
        ensure_vendored(self.root)
        self.task_id = ""
        self.seed = 0
        self._entry: dict[str, Any] | None = None
        self._world: BfclWorld | None = None
        self._step = 0
        self._turn = 0
        self._steps_in_turn = 0
        self._turn_calls: list[list[list[str]]] = []
        self._answers: list[str | None] = []
        self._force_quit = False
        self._done = False
        self._api_docs_prompt = ""
        self._api_docs_digest = ""

    def reset(self, task_id: str, seed: int) -> Observation:
        entries = load_entries(self.root)
        if task_id not in entries:
            raise KeyError(f"unknown BFCL {BFCL_CATEGORY} entry {task_id!r}")
        self.task_id = task_id
        self.seed = seed
        self._entry = entries[task_id]
        # Fresh instances every time: never upstream's globals() cache.
        self._world = BfclWorld(self._entry, self.root)
        self._step = 0
        self._turn = 0
        self._steps_in_turn = 0
        n_turns = len(self._entry["turns"])
        self._turn_calls = [[] for _ in range(n_turns)]
        self._answers = [None] * n_turns
        self._force_quit = False
        self._done = False
        docs = function_docs(self._entry["involved_classes"], self.root)
        self._api_docs_digest = _sha(docs)
        self._api_docs_prompt = render_api_docs(docs)
        return Observation(text=self.instruction, step=0, env_state_hash=self.snapshot_hash())

    def step(self, action: ExecutorAction) -> Observation:
        if self._entry is None or self._world is None:
            raise RuntimeError("BfclEnv.reset() must be called before step()")
        if self._done:
            text = "The episode is already over."
        elif action.kind == "CODE":
            self._steps_in_turn += 1
            try:
                calls = parse_calls(action.code or "")
            except BfclCallError as exc:
                text = f"Error: {exc}. Nothing was run."
            else:
                results = self._world.run_all(calls)
                self._turn_calls[self._turn].append(calls)
                text = "\n".join(f"{c} -> {r}" for c, r in zip(calls, results))
            if self._steps_in_turn > MAXIMUM_STEP_LIMIT:
                self._force_quit = True
                self._done = True
                text += f"\nForced to quit after {MAXIMUM_STEP_LIMIT} steps on one request."
        elif action.kind == "COMPLETE":
            self._answers[self._turn] = action.message
            if self._turn + 1 < len(self._entry["turns"]):
                self._turn += 1
                self._steps_in_turn = 0
                text = f"The user's next request: {self._entry['turns'][self._turn]}"
            else:
                self._done = True
                text = "All of the user's requests are finished."
        else:
            text = f"no-op kind={action.kind}"
        self._step += 1
        return Observation(text=text, step=self._step, done=self._done, env_state_hash=self.snapshot_hash())

    def evaluate(self) -> dict:
        """Score the episode. What the harness fields mean on BFCL:

        - ``success`` / ``tgc``: upstream's pass verdict for the entry. 1.0 iff the agent reached
          every user turn, was not force-quit (more than ``MAXIMUM_STEP_LIMIT`` CODE steps in one
          turn), and every checked turn passes both of upstream's per-turn checks -- the state of
          every backend instance equals the ground truth's after that turn, and every ground-truth
          result of that turn appears among the agent's results so far. Else 0.0.
        - ``goal_pass_rate``: the share of checked turns (turns with a non-empty ground truth)
          that pass those checks, each turn judged even after an earlier one failed. Turns never
          reached count as failed. Because the state check compares against the cumulative
          ground-truth state, a failed turn usually fails the turns after it too.
        - ``sgc``: None, as on AppWorld.
        - ``report.final_state_hash_match``: whether ``state_hash`` of the agent's final state
          equals that of the state the full ground truth reaches (the possible-answer state).
          Reported, not used for ``success``.
        """
        if self._entry is None:
            return {"success": False, "tgc": 0.0, "sgc": None, "goal_pass_rate": None, "report": {"error": "no episode"}}
        n_turns = len(self._entry["turns"])
        turns_reached = self._turn + 1
        model_turns = [self._turn_calls[t] if t < turns_reached else [] for t in range(n_turns)]
        scored = score_turns(self._entry, model_turns, self.root)
        success = bool(scored["all_checked_pass"] and turns_reached == n_turns and not self._force_quit)
        n_checked = scored["n_checked"]
        first_failure = next((t for t in scored["turns"] if t["checked"] and not t["valid"]), None)
        report = {
            "bfcl_id": self._entry["id"],
            "n_turns": n_turns,
            "turns_reached": turns_reached,
            "force_quit": self._force_quit,
            "n_checked_turns": n_checked,
            "n_turns_passed": scored["n_passed"],
            "turn_valid": [t["valid"] for t in scored["turns"]],
            "turn_error_type": [t["error_type"] for t in scored["turns"]],
            "first_failure": first_failure,
            "n_steps_per_turn": [len(s) for s in self._turn_calls],
            "answers": list(self._answers),
            "final_state_hash": scored["model_state_hash"],
            "possible_answer_state_hash": scored["truth_state_hash"],
            "final_state_hash_match": scored["model_state_hash"] == scored["truth_state_hash"],
        }
        return {
            "success": success,
            "tgc": 1.0 if success else 0.0,
            "sgc": None,
            "goal_pass_rate": (scored["n_passed"] / n_checked) if n_checked else None,
            "report": report,
        }

    def snapshot_hash(self) -> str:
        """Replay hash; see the module docstring."""
        if self._world is None:
            return _sha({"entry": None})
        payload = {
            "entry": self.task_id,
            "turn": self._turn,
            "steps_in_turn": self._steps_in_turn,
            "done": self._done,
            "force_quit": self._force_quit,
            "instances": {
                name: {"public": canonical(inst, ordered=True), "private": _private_replay_state(inst)}
                for name, inst in self._world.instances.items()
            },
        }
        return _sha(payload)

    def close(self) -> None:
        # State is kept until the next reset so the loop's run_end can still hash it; there is
        # no process, file or connection to release.
        return None

    @property
    def instruction(self) -> str:
        return self._entry["turns"][0] if self._entry else ""

    @property
    def api_docs_digest(self) -> str:
        return self._api_docs_digest

    @property
    def api_docs_prompt(self) -> str:
        return self._api_docs_prompt

    @property
    def executor_system_prompt(self) -> str:
        return BFCL_EXECUTOR_SYSTEM_PROMPT

    @property
    def turn_calls(self) -> list[list[list[str]]]:
        """The calls run so far: per turn, per step. A copy."""
        return [[list(s) for s in t] for t in self._turn_calls]

    def manifest_fields(self) -> dict:
        return {"bfcl_root": str(self.root), "bfcl_upstream_commit": UPSTREAM_COMMIT, "bfcl_category": BFCL_CATEGORY}
