"""AppWorld wrapper. AppWorld is imported lazily inside reset()."""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from sidekick.environments.base import BaseEnv
from sidekick.protocols.schemas import ExecutorAction, Observation

DEFAULT_APPWORLD_ROOT = "/scratch/n12194778/sidekick/appworld"


class AppWorldRootError(Exception):
    """Raised when the resolved AppWorld data root has no data/tasks directory."""


class AppWorldEnv(BaseEnv):
    """Thin wrapper around `appworld.AppWorld`.

    snapshot_hash() hashes `environment_io` (the execute input/output log),
    `num_interactions`, and `task_completed()`. AppWorld does not expose a
    stable public serialisation of the underlying SQLite app databases without
    writing a checkpoint via `save_state()`. Observation-history hashing
    **weakens replay**: a hidden DB mutation that does not appear in execute()
    output will not change the hash. Replay of recorded CODE/COMPLETE actions
    against a fresh world with the same task_id should still match when
    `execute()` is deterministic.

    One world per process — AppWorld mocks time with freezegun. Never create
    two worlds in one process and never use threads. The runner parallelises
    with multiprocessing.Pool (one world per worker).
    """

    def __init__(
        self,
        experiment_name: str = "sidekick",
        extra_kwargs: dict[str, Any] | None = None,
        root: str | None = None,
    ) -> None:
        # Resolve the data root: explicit argument > APPWORLD_ROOT env var >
        # installed default. Never fall through to os.getcwd() (AppWorld's own
        # dangerous default in appworld/common/path_store.py).
        self.root = root or os.environ.get("APPWORLD_ROOT") or DEFAULT_APPWORLD_ROOT
        self.root = os.path.abspath(self.root)
        if not os.path.isdir(os.path.join(self.root, "data", "tasks")):
            raise AppWorldRootError(
                f"AppWorld data root {self.root!r} has no data/tasks directory. "
                f"Pass root=..., set APPWORLD_ROOT, or check {DEFAULT_APPWORLD_ROOT!r}."
            )
        # Set before the lazy AppWorld import in reset(): appworld resolves its
        # root from this variable and would otherwise use os.getcwd().
        os.environ["APPWORLD_ROOT"] = self.root
        self.experiment_name = experiment_name
        self.extra_kwargs = extra_kwargs or {}
        self.task_id = ""
        self.seed = 0
        self._world: Any = None
        self._step = 0
        self._obs_history: list[str] = []
        self._instruction = ""
        self._api_docs_digest = ""
        self._api_docs_prompt = ""

    def reset(self, task_id: str, seed: int) -> Observation:
        self.close()
        # Lazy import so this module loads on machines without AppWorld.
        from appworld import AppWorld

        self.task_id = task_id
        self.seed = seed
        self._step = 0
        self._obs_history = []
        kwargs = dict(self.extra_kwargs)
        kwargs.setdefault("random_seed", seed)
        self._world = AppWorld(task_id=task_id, experiment_name=self.experiment_name, **kwargs)
        self._instruction = str(self._world.task.instruction)
        raw_api_docs = getattr(self._world.task, "api_docs", "")
        self._api_docs_digest = _digest_api_docs(raw_api_docs)
        self._api_docs_prompt = _summarise_api_docs(raw_api_docs)
        text = self._instruction
        self._obs_history.append(text)
        return Observation(text=text, step=0, env_state_hash=self.snapshot_hash())

    def step(self, action: ExecutorAction) -> Observation:
        if self._world is None:
            raise RuntimeError("AppWorldEnv.reset() must be called before step()")
        if action.kind == "COMPLETE":
            # AppWorld scores answer-returning tasks ("Give me a list of ...") on the
            # answer passed here, and its own doc says to pass it "if and only if the
            # task requests an answer". Calling complete_task() bare made every such
            # task unscoreable no matter how well the agent had done.
            answer = (action.message or "").strip()
            if answer:
                text = self._world.execute(
                    f"apis.supervisor.complete_task(answer={answer!r})"
                )
            else:
                text = self._world.execute("apis.supervisor.complete_task()")
            done = True
        elif action.kind == "CODE":
            text = self._world.execute(action.code or "")
            done = bool(self._world.task_completed())
        else:
            text = f"no-op kind={action.kind}"
            done = False
        self._step += 1
        self._obs_history.append(str(text))
        return Observation(
            text=str(text),
            step=self._step,
            done=done,
            env_state_hash=self.snapshot_hash(),
        )

    def evaluate(self) -> dict:
        if self._world is None:
            return {
                "success": False,
                "tgc": 0.0,
                "sgc": None,
                "goal_pass_rate": None,
                "report": {"error": "no world"},
            }
        tracker = self._world.evaluate(suppress_errors=True)
        success = bool(getattr(tracker, "success", False))
        report: dict[str, Any]
        if hasattr(tracker, "to_dict"):
            report = tracker.to_dict(stats_only=True)
        else:
            report = {"success": success}
        pass_pct = getattr(tracker, "pass_percentage", None)
        tgc = 1.0 if success else 0.0
        if pass_pct is not None:
            report = dict(report)
            report["pass_percentage"] = pass_pct
        goal_pass_rate = float(pass_pct) / 100.0 if pass_pct is not None else None
        return {
            "success": success,
            "tgc": tgc,
            "sgc": None,
            "goal_pass_rate": goal_pass_rate,
            "report": report,
        }

    def snapshot_hash(self) -> str:
        """sha256 of concatenated execute I/O, not a DB dump. Weakens replay (see class docstring)."""
        if self._world is None:
            blob = json.dumps({"io": self._obs_history}, sort_keys=True, default=str)
        else:
            payload = {
                "environment_io": getattr(self._world, "environment_io", self._obs_history),
                "num_interactions": getattr(self._world, "num_interactions", self._step),
                "task_completed": bool(self._world.task_completed()),
            }
            blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def close(self) -> None:
        if self._world is not None:
            closer = getattr(self._world, "close", None)
            if callable(closer):
                closer()
            self._world = None

    @property
    def instruction(self) -> str:
        return self._instruction

    @property
    def api_docs_digest(self) -> str:
        """sha256 fingerprint of the API surface, for manifests. NOT for prompts."""
        return self._api_docs_digest

    @property
    def api_docs_prompt(self) -> str:
        """Model-readable listing of the available apps and APIs."""
        return self._api_docs_prompt

    def manifest_fields(self) -> dict:
        return {"appworld_root": self.root, "experiment_name": self.experiment_name}


def _digest_api_docs(api_docs: Any) -> str:
    try:
        blob = json.dumps(api_docs, sort_keys=True, default=str)
    except TypeError:
        blob = str(api_docs)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_API_USAGE_PREAMBLE = (
    "You are controlling an AppWorld environment from a Python session.\n"
    "Call APIs as apis.<app>.<api>(...), for example "
    "apis.spotify.show_song_library().\n"
    "Your code runs at module level: use print(...) to see a value. `return` "
    "outside a function and top-level `await` are syntax errors here.\n"
    "Only the APIs listed below exist. For full parameter details call "
    "apis.api_docs.show_api_doc(app_name=..., api_name=...).\n"
    "When the task asks a question, finish with `COMPLETE: <answer>` and keep the "
    "answer concise (a number, a yes/no, or a comma-separated list of names). When "
    "the task is an action rather than a question, finish with a bare `COMPLETE`.\n"
    "\nAvailable APIs:\n"
)


def _summarise_api_docs(api_docs: Any) -> str:
    """Render AppWorld's api_docs as a compact one-line-per-API listing.

    ``task.api_docs`` is an ApiDocCollection keyed by app name ("spotify", "gmail",
    …), each mapping api_name -> {description, parameters, response_schemas}.
    ``compress_parameters()`` collapses the parameter blocks, which is what PLAN.md
    asks for in the prompt prefix; full detail stays available to the agent at
    runtime through ``apis.api_docs.show_api_doc(...)``.

    ⚠ Attribute access on these objects raises fastapi HTTPException rather than
    AttributeError for an unknown key, so this only ever uses ``.keys()`` and
    ``[key]`` and never ``hasattr``/``getattr`` probing.
    """
    try:
        compressed = api_docs.compress_parameters()
    except Exception:  # noqa: BLE001 - fall back to the uncompressed collection
        compressed = api_docs

    lines: list[str] = []
    try:
        app_names = sorted(compressed.keys())
    except Exception:  # noqa: BLE001 - not a mapping; nothing useful to show
        return ""

    for app_name in app_names:
        try:
            app_apis = compressed[app_name]
            api_names = sorted(app_apis.keys())
        except Exception:  # noqa: BLE001 - skip an app we cannot read
            continue
        lines.append(f"{app_name}:")
        for api_name in api_names:
            description = ""
            try:
                entry = app_apis[api_name]
                if isinstance(entry, dict):
                    description = str(entry.get("description") or "").strip()
            except Exception:  # noqa: BLE001
                description = ""
            # Fully qualified on purpose. Listing a bare `show_song_library` under a
            # `spotify:` heading invites `spotify.show_song_library()`, which fails
            # with NameError: name 'spotify' is not defined -- observed 2026-09-15.
            call = f"  apis.{app_name}.{api_name}"
            lines.append(f"{call}: {description}" if description else call)
    if not lines:
        return ""
    return _API_USAGE_PREAMBLE + "\n".join(lines)
