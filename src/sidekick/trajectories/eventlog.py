"""Append-only JSONL event log with run manifests."""
from __future__ import annotations

import json
import os
import socket
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from sidekick.protocols.schemas import SCHEMA_VERSION, Event


class EventLog:
    """Appends events to ``<root>/<run_id>/events.jsonl`` (one JSON object per line).

    Append-only: existing lines are never rewritten or deleted. Every write is
    flushed so a job killed at any moment leaves a file readable up to the last
    complete line.
    """

    def __init__(self, root: str | Path, run_id: str) -> None:
        self.root = Path(root)
        self.run_id = run_id
        self.dir = self.root / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self._path = self.dir / "events.jsonl"
        self._fh: TextIO = open(self._path, "a", encoding="utf-8")

    def append(self, event: Event) -> None:
        self._fh.write(event.model_dump_json())
        self._fh.write("\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def write_manifest(self, manifest: dict) -> None:
        data = dict(manifest)
        data.setdefault("run_id", self.run_id)
        data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        data.setdefault("hostname", socket.gethostname())
        data.setdefault("pid", os.getpid())
        data.setdefault("python_version", sys.version)
        data.setdefault("schema_version", SCHEMA_VERSION)
        path = self.dir / "manifest.json"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True))
            fh.write("\n")

    def close(self) -> None:
        if self._fh is not None and not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def read(path: str | Path) -> Iterator[Event]:
        """Yield validated Events; skip a trailing truncated (unparseable) line."""
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield Event.model_validate(json.loads(stripped))
                except Exception:
                    # Only the final line may be truncated; anything else is corruption
                    # but we still skip rather than raise so partial logs stay readable.
                    continue
