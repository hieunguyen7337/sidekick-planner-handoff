"""Wrong-task plan control (dev arm WTP, brief 20260924_ctrl_planning_controls): replay a DIFFERENT
task's cached packet.

The sft_plan floor replays luna's HJ-1 packet for (task t, seed s). A reviewer asks whether that
plan helps through its information or merely through being plan-shaped text. This arm answers it
by replaying the packet of (pi(t), s) instead, where pi is a fixed permutation built once by
`scripts/setup/make_wrongtask_map.py`: a derangement whose source task is always from another
scenario, chosen to minimise the total plan-length gap. The executor still receives its own
task t (instruction and API docs); only the plan is swapped. The packet is replayed byte-for-byte,
so its `task_id` and `goal` name pi(t) -- that mismatch is the treatment, not a bug.

Three things are deliberate:

* **Composition, not a CachedPacketPlanner subclass.** `RemappedPacketPlanner.plan(t)` asks the
  wrapped replay for pi(t). The replay layer's own reading of the archive (last `run_start`,
  zero-token `provider="cache"` usage, the api-digest prepend on the first live call) is reused
  unchanged, so the only thing this arm changes is which key is read.
* **No fall-through to the right plan.** A task absent from the map raises
  `PacketTaskMapError`. It is deliberately not a `FileNotFoundError`, which the replay layer's
  `on_missing` modes can turn into a live plan -- a live plan would be for task t, the right
  task, and the arm would silently measure the floor. For the same reason the wrapper refuses
  any `on_missing` other than "fail" and any `live_plan_keys`.
* **Every plan says where it came from.** The source task goes into the plan's usage record as
  `packet_task_source`, and the episode loop copies it into the `plan` event's payload, so an
  analysis can check per episode that the remap happened.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from sidekick.agents.planner import CachedPacketPlanner
from sidekick.protocols.schemas import DelegationPacket, PlannerResponse

# The config key (planner.packet_task_map) and the plan-event payload key.
PACKET_TASK_MAP_KEY = "packet_task_map"
PACKET_TASK_SOURCE_KEY = "packet_task_source"
# A relative planner.packet_task_map resolves against the repository that holds configs/.
REPO_ROOT = Path(__file__).resolve().parents[3]


class PacketTaskMapError(KeyError):
    """The episode's task has no entry in the packet-task map. Never recoverable."""


def validate_packet_task_map(task_map: Mapping[str, str]) -> dict[str, str]:
    """The map as a plain dict, or ValueError unless it is a permutation with no fixed point.

    A permutation, so no two tasks share one source plan; a derangement, so no task is handed its
    own plan -- either failure would leave part of the arm measuring the floor.
    """
    out = {str(k): str(v) for k, v in task_map.items()}
    if not out:
        raise ValueError("packet-task map is empty")
    if sorted(out.values()) != sorted(out):
        raise ValueError("packet-task map is not a permutation of its own keys")
    fixed = sorted(t for t, s in out.items() if t == s)
    if fixed:
        raise ValueError(f"packet-task map sends {len(fixed)} task(s) to their own plan: {fixed[:3]}")
    return out


def resolve_map_path(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else REPO_ROOT / path


def load_packet_task_map(path: str | Path) -> dict[str, str]:
    """Read the "map" field of a make_wrongtask_map.py JSON, validated."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("map"), dict):
        raise ValueError(f"{path}: expected a JSON object with a 'map' object")
    return validate_packet_task_map(doc["map"])


class RemappedPacketPlanner:
    """Replays the cached packet of map[task_id] for task_id; everything else is the replay's."""

    name = "cached-packet-remapped"

    def __init__(self, cached: CachedPacketPlanner, task_map: Mapping[str, str]) -> None:
        if cached.on_missing != "fail" or cached.live_plan_keys:
            raise ValueError(
                "planner.packet_task_map requires on_missing: fail and no live_plan_keys; a live "
                f"plan would be for the episode's own task (on_missing={cached.on_missing!r}, "
                f"live_plan_keys={sorted(cached.live_plan_keys)})"
            )
        self.cached = cached
        self.task_map = validate_packet_task_map(task_map)
        # verify_configs.py prints the resolved producer subtree of every cached-packet planner.
        self.system = cached.system
        self.seed = cached.seed

    def source_task(self, task_id: str) -> str:
        try:
            return self.task_map[task_id]
        except KeyError:
            raise PacketTaskMapError(
                f"task {task_id!r} is not in planner.packet_task_map ({len(self.task_map)} tasks); "
                "refusing to replay its own plan"
            ) from None

    def plan(self, task_id: str, goal: str, context: str, timeout_s: float | None = None) -> PlannerResponse:
        source = self.source_task(task_id)
        # goal and context are the episode's own (task t); the replay only reads the archive key.
        resp = self.cached.plan(source, goal, context, timeout_s=timeout_s)
        resp.usage.raw[PACKET_TASK_SOURCE_KEY] = source
        return resp

    def correct(
        self,
        packet: DelegationPacket,
        transcript_delta: str,
        timeout_s: float | None = None,
    ) -> PlannerResponse:
        return self.cached.correct(packet, transcript_delta, timeout_s=timeout_s)

    def act(
        self,
        task_id: str,
        transcript: str,
        timeout_s: float | None = None,
        allow_handoff: bool = False,
    ) -> PlannerResponse:
        return self.cached.act(task_id, transcript, timeout_s=timeout_s, allow_handoff=allow_handoff)

    def close(self) -> None:
        self.cached.close()


def apply_packet_task_map(planner: Any, planner_cfg: Mapping[str, Any]) -> Any:
    """make_planner's last step: wrap the replay when planner.packet_task_map is set, else a no-op."""
    raw = planner_cfg.get(PACKET_TASK_MAP_KEY)
    if not raw:
        return planner
    if not isinstance(planner, CachedPacketPlanner):
        raise ValueError(
            "planner.packet_task_map needs planner.packet_source: it remaps which cached packet "
            f"is replayed, and this planner ({type(planner).__name__}) replays none"
        )
    return RemappedPacketPlanner(planner, load_packet_task_map(resolve_map_path(str(raw))))


def plan_event_fields(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """The plan-event payload fields carried on a plan's usage.raw: the WTP source task, else none."""
    source = (raw or {}).get(PACKET_TASK_SOURCE_KEY)
    return {} if source is None else {PACKET_TASK_SOURCE_KEY: source}
