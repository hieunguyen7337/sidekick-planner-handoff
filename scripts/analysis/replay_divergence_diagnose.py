#!/usr/bin/env python
"""Diagnose the deterministic ``replay_divergence`` of dev prefix-replay keys (DIVDIAG, 2026-09-25).

Two subcommands:

``replay``  Reset an ``AppWorldEnv`` exactly as ``sidekick.replay.replay_prefix`` does and replay
            the first ``m`` executed (CODE/COMPLETE) actions of a source episode's LAST attempt,
            mirroring the loop at replay.py:97-106. After EACH executed action it compares
            (a) the live observation text with the recorded observation's ``payload.text`` and
            (b) the live ``env_state_hash`` with the recorded one. It also records a fingerprint of
            this process's string-hash seed so two fresh processes can be compared.

``scan``    No replay; pure text. For every seed/task of a source, over the observation events of
            the LAST attempt with ``step <= --max-step``, count episodes whose output prints a
            memory address (``object at 0x...``) and, separately, episodes whose output prints a
            Python set literal of >= 2 quoted strings.

Held-out guard: any ``--source`` whose path (raw or resolved) contains ``/j10_``, ``/j11_``,
``/j12_``, ``test_normal`` or ``test_challenge`` is refused with exit code 2 before anything is read.

Regex known misses (``scan``), documented here and echoed into the scan output:

* ``SET_LITERAL_RE`` only sees the *repr* of a set of single-quoted strings. It misses: sets whose
  strings contain an apostrophe (repr switches to double quotes) or a ``{``/``}`` character; sets of
  tuples of strings (``{('a', 1), ('b', 2)}``) or of mixed element types; set reprs truncated
  before the closing brace; and -- the large class -- output whose ORDER comes from iterating a set
  without printing the set itself (``list(s)``, ``for x in s: print(x)``, a dict or JSON built by
  iterating a set, ``', '.join(s)``). Single-element sets and sets of ints are not a hazard (no
  ordering freedom / int hashes are not randomised) and are correctly not counted.
* ``ADDRESS_RE`` (``object at 0x...``, as specified) misses reprs without the word ``object``
  (``<function f at 0x...>``, ``<built-in method ...>``) and addresses printed as numbers
  (``id(x)``, ``hex(id(x))``). ``ADDRESS_BROAD_RE`` (`` at 0x`` + >= 6 hex digits) is reported
  alongside to size the first miss.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

HELD_OUT_MARKERS = ("/j10_", "/j11_", "/j12_", "test_normal", "test_challenge")

HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
ADDRESS_RE = re.compile(r"object at 0x[0-9a-fA-F]+")
ADDRESS_BROAD_RE = re.compile(r" at 0x[0-9a-fA-F]{6,}")
# A dict repr has "': " after the first key, so it cannot match "'(, '...')+}".
SET_LITERAL_RE = re.compile(r"\{'[^'{}]*'(?:, '[^'{}]*')+\}")
# Brackets are tokens of their own: a reordered set repr moves "{"/"}" onto different elements,
# so a pure whitespace/comma split would call "{'a', 'b'}" vs "{'b', 'a'}" different.
TOKEN_RE = re.compile(r"[{}\[\]()]|[^\s,{}\[\]()]+")

REGION_HALF = 150  # region = up to 300 chars around the first differing character

REGEX_KNOWN_MISSES = [
    "set_literal: strings containing an apostrophe (repr uses double quotes) or a brace",
    "set_literal: sets of tuples / mixed element types, e.g. {('a', 1), ('b', 2)}",
    "set_literal: set reprs truncated before the closing brace",
    "set_literal: order derived from iterating a set without printing it (list(s), join, loops, dicts/JSON built from a set)",
    "address: '<function f at 0x..>' / '<bound method ..>' without 'object at' (see address_broad), id(x) integers, hex(id(x))",
]


# ----------------------------------------------------------------------------- pure helpers


def held_out_reason(source: str) -> str | None:
    """Return the held-out marker a source path contains (raw or resolved), else None."""
    candidates = [str(source)]
    try:
        candidates.append(os.path.realpath(str(source)))
    except Exception:
        pass
    for cand in candidates:
        for marker in HELD_OUT_MARKERS:
            if marker in cand:
                return marker
    return None


def guard_source(source: str) -> None:
    """Refuse (exit 2) any held-out source. Runs before anything under the source is read."""
    marker = held_out_reason(source)
    if marker is not None:
        sys.stderr.write(
            f"refused: --source {source!r} contains held-out marker {marker!r}; "
            "only dev sources are allowed\n"
        )
        raise SystemExit(2)


def _tokens(text: str) -> Counter:
    return Counter(TOKEN_RE.findall(text))


def classify_difference(recorded: str, live: str) -> str:
    """Classify how ``live`` differs from ``recorded``.

    ``"identical"``  the strings are equal (no difference to classify; the replay subcommand only
                     calls this on a step whose texts differ, so it never emits this value).
    ``"address"``    equal after replacing every ``0x[0-9a-fA-F]+`` by ``0xADDR``.
    ``"reordering"`` not address; the address-normalised strings are equal as multisets of tokens
                     (whitespace/comma separated, with each bracket character a token of its own).
    ``"other"``      anything else.
    """
    if recorded == live:
        return "identical"
    rec_n = HEX_RE.sub("0xADDR", recorded)
    live_n = HEX_RE.sub("0xADDR", live)
    if rec_n == live_n:
        return "address"
    if _tokens(rec_n) == _tokens(live_n):
        return "reordering"
    return "other"


def first_diff_index(a: str, b: str) -> int | None:
    """Index of the first differing character, or None if equal."""
    if a == b:
        return None
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def diff_region(recorded: str, live: str) -> dict[str, Any]:
    i = first_diff_index(recorded, live)
    if i is None:
        return {"first_diff_char": None, "recorded": "", "live": ""}
    lo = max(0, i - REGION_HALF)
    return {
        "first_diff_char": i,
        "region_start": lo,
        "recorded": recorded[lo : i + REGION_HALF],
        "live": live[lo : i + REGION_HALF],
        "recorded_len": len(recorded),
        "live_len": len(live),
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def process_fingerprint() -> dict[str, Any]:
    """Identify this Python process's string-hash randomisation state."""
    return {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "pbs_jobid": os.environ.get("PBS_JOBID"),
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "hash_randomization_flag": sys.flags.hash_randomization,
        # Differs between two processes iff str hashing is randomised per process.
        "hash_of_probe_string": hash("divdiag-probe"),
        "set_iteration_probe": list({"alpha", "bravo", "charlie", "delta", "echo"}),
        "python": sys.version.split()[0],
    }


def _episode_dirs(source: Path, system: str) -> list[tuple[str, str, Path]]:
    out: list[tuple[str, str, Path]] = []
    sys_dir = source / system
    for seed_dir in sorted(p for p in sys_dir.iterdir() if p.is_dir() and p.name.isdigit()):
        for task_dir in sorted(p for p in seed_dir.iterdir() if p.is_dir()):
            if (task_dir / "events.jsonl").is_file():
                out.append((seed_dir.name, task_dir.name, task_dir / "events.jsonl"))
    return out


# ----------------------------------------------------------------------------- replay


def cmd_replay(args: argparse.Namespace) -> dict[str, Any]:
    guard_source(args.source)
    from sidekick.environments.appworld_env import AppWorldEnv
    from sidekick.replay import _action_from_payload, _events_of_last_attempt

    events_path = Path(args.source) / args.system / str(args.seed) / args.task / "events.jsonl"
    fingerprint = process_fingerprint()
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    events = _events_of_last_attempt(events_path)
    start = next((e for e in reversed(events) if e.event_type == "run_start"), None)
    task_id = start.task_id if start is not None else ""
    seed = start.seed if start is not None else 0
    recorded_obs0 = next(
        (e for e in events if e.event_type == "observation" and e.step == 0), None
    )

    tag = f"p{os.getpid()}_{int(time.time())}"
    experiment = f"divdiag_20260925/{tag}/{args.system}/{args.seed}/{args.task}"
    world = AppWorldEnv(experiment_name=experiment)
    steps: list[dict[str, Any]] = []
    first_text: dict[str, Any] | None = None
    diff_steps: list[dict[str, Any]] = []
    final_hash_equal: bool | None = None
    last_recorded_hash: str | None = None
    error: str | None = None
    try:
        obs0 = world.reset(task_id, seed)
        if recorded_obs0 is not None:
            rec_text0 = str(recorded_obs0.payload.get("text", ""))
            steps.append(
                {
                    "step": 0,
                    "executed": 0,
                    "text_equal": obs0.text == rec_text0,
                    "hash_equal": obs0.env_state_hash == recorded_obs0.env_state_hash,
                    "live_text_sha256": _sha(obs0.text),
                    "live_hash": obs0.env_state_hash,
                }
            )
        # Mirror of replay.py:97-106 (replay_prefix), with a comparison after each step().
        executed = 0
        pending = None
        for event in events:
            if event.event_type == "action":
                pending = _action_from_payload(event.payload)
                continue
            if event.event_type == "observation" and pending is not None:
                if pending.kind in ("CODE", "COMPLETE") and executed < args.m:
                    obs = world.step(pending)
                    executed += 1
                    rec_text = str(event.payload.get("text", ""))
                    text_equal = obs.text == rec_text
                    rec = {
                        "step": event.step,
                        "executed": executed,
                        "text_equal": text_equal,
                        "hash_equal": obs.env_state_hash == event.env_state_hash,
                        "live_text_sha256": _sha(obs.text),
                        "live_hash": obs.env_state_hash,
                    }
                    steps.append(rec)
                    last_recorded_hash = event.env_state_hash
                    if not text_equal:
                        cls = classify_difference(rec_text, obs.text)
                        diff_steps.append({"step": event.step, "classification": cls})
                        if first_text is None:
                            first_text = {
                                "step": event.step,
                                "classification": cls,
                                "region": diff_region(rec_text, obs.text),
                            }
                pending = None
        live_final = world.snapshot_hash()
        final_hash_equal = (last_recorded_hash is not None) and live_final == last_recorded_hash
    except Exception as exc:  # recorded, not swallowed: the output says the replay errored
        error = f"{type(exc).__name__}: {exc}"
    finally:
        world.close()

    first_hash_step = next((s["step"] for s in steps if not s["hash_equal"]), None)
    return {
        "subcommand": "replay",
        "source": str(args.source),
        "system": args.system,
        "seed": args.seed,
        "task": args.task,
        "m": args.m,
        "events_path": str(events_path),
        "experiment_name": experiment,
        "started": started,
        "process": fingerprint,
        "n_executed": max((s["executed"] for s in steps), default=0),
        "steps": steps,
        "all_text_equal": all(s["text_equal"] for s in steps),
        "all_hash_equal": all(s["hash_equal"] for s in steps),
        "first_text_diff_step": first_text["step"] if first_text else None,
        "first_hash_diff_step": first_hash_step,
        "first_text_diff": first_text,
        "text_diff_steps": diff_steps,
        "final_snapshot_hash_equal_last_recorded": final_hash_equal,
        "error": error,
    }


# ----------------------------------------------------------------------------- scan


def cmd_scan(args: argparse.Namespace) -> dict[str, Any]:
    guard_source(args.source)
    from sidekick.replay import _events_of_last_attempt

    source = Path(args.source)
    address: dict[str, int] = {}
    address_broad: dict[str, int] = {}
    set_print: dict[str, int] = {}
    n_scanned = 0
    n_empty = 0
    for seed, task, path in _episode_dirs(source, args.system):
        key = f"{seed}/{task}"
        events = _events_of_last_attempt(path)
        if not events:
            n_empty += 1
            continue
        n_scanned += 1
        for e in events:
            if e.event_type != "observation" or e.step > args.max_step:
                continue
            text = str(e.payload.get("text", "") or "")
            if key not in address and ADDRESS_RE.search(text):
                address[key] = e.step
            if key not in address_broad and ADDRESS_BROAD_RE.search(text):
                address_broad[key] = e.step
            if key not in set_print and SET_LITERAL_RE.search(text):
                set_print[key] = e.step
    either = sorted(set(address) | set(set_print))
    return {
        "subcommand": "scan",
        "source": str(source),
        "system": args.system,
        "max_step": args.max_step,
        "n_episodes_scanned": n_scanned,
        "n_episodes_without_run_start": n_empty,
        "address": {"n": len(address), "first_step_by_key": dict(sorted(address.items()))},
        "address_broad": {
            "n": len(address_broad),
            "first_step_by_key": dict(sorted(address_broad.items())),
        },
        "set_print": {"n": len(set_print), "first_step_by_key": dict(sorted(set_print.items()))},
        "either_address_or_set": {"n": len(either), "keys": either},
        "regexes": {
            "address": ADDRESS_RE.pattern,
            "address_broad": ADDRESS_BROAD_RE.pattern,
            "set_print": SET_LITERAL_RE.pattern,
        },
        "regex_known_misses": REGEX_KNOWN_MISSES,
    }


# ----------------------------------------------------------------------------- CLI


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="replay a prefix and compare text/hash per step")
    r.add_argument("--source", required=True)
    r.add_argument("--system", required=True)
    r.add_argument("--seed", type=int, required=True)
    r.add_argument("--task", required=True)
    r.add_argument("--m", type=int, required=True)
    r.add_argument("--out", help="write JSON here (default stdout)")
    s = sub.add_parser("scan", help="pure-text scan for address / set prints")
    s.add_argument("--source", required=True)
    s.add_argument("--system", required=True)
    s.add_argument("--max-step", type=int, required=True)
    s.add_argument("--out", help="write JSON here (default stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Guard before dispatch too, so no subcommand can reach the filesystem first.
    guard_source(args.source)
    result = cmd_replay(args) if args.cmd == "replay" else cmd_scan(args)
    text = json.dumps(result, indent=2, sort_keys=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.cmd == "replay" and result.get("error"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
