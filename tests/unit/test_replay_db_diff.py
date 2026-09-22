"""Unit tests for database state consistency in replay (Brief X31).

Verifies the property that replay must reproduce the underlying database state,
and documents that observation-only hashing (snapshot_hash) is blind to hidden DB
mutations that do not appear in observation text.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sidekick.environments.base import BaseEnv
from sidekick.protocols.schemas import Event, ExecutorAction, Observation
from sidekick.replay import _events_of_last_attempt, replay_prefix


@dataclass
class StatefulMockEnv(BaseEnv):
    """Mock environment with both visible observation text and underlying DB tables."""
    experiment_name: str = "mock"
    task_id: str = ""
    seed: int = 0
    _step: int = 0
    _obs_history: list[str] = field(default_factory=list)
    db: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    simulate_hollow_replay: bool = False

    def reset(self, task_id: str, seed: int) -> Observation:
        self.task_id = task_id
        self.seed = seed
        self._step = 0
        self._obs_history = ["Task initialized."]
        # Initial DB state
        self.db = {
            "accounts": [
                {"id": 1, "owner": "alice", "balance": 100, "status": "active"},
                {"id": 2, "owner": "bob", "balance": 50, "status": "active"},
            ],
            "audit_log": [],
        }
        return Observation(text="Task initialized.", step=0, env_state_hash=self.snapshot_hash())

    def step(self, action: ExecutorAction) -> Observation:
        self._step += 1
        code = (action.code or "").strip()
        
        # In hollow replay mode, the environment returns the expected observation text
        # but fails to perform the underlying DB mutation.
        if self.simulate_hollow_replay:
            obs_text = "Transaction complete."
            self._obs_history.append(obs_text)
            return Observation(text=obs_text, step=self._step, env_state_hash=self.snapshot_hash())

        if "transfer" in code:
            # Mutate DB state
            self.db["accounts"][0]["balance"] -= 30
            self.db["accounts"][1]["balance"] += 30
            self.db["audit_log"].append({"tx_id": self._step, "amount": 30, "status": "SUCCESS"})
            obs_text = "Transaction complete."
        elif "close_account" in code:
            self.db["accounts"][1]["status"] = "closed"
            obs_text = "Account closed."
        else:
            obs_text = f"Executed: {code}"

        self._obs_history.append(obs_text)
        return Observation(text=obs_text, step=self._step, env_state_hash=self.snapshot_hash())

    def evaluate(self) -> dict:
        return {"success": True, "tgc": 1.0, "sgc": None, "report": {}}

    def snapshot_hash(self) -> str:
        """sha256 of observation history (environment_io) only, matching AppWorldEnv."""
        blob = json.dumps({"io": self._obs_history}, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def close(self) -> None:
        pass

    @property
    def instruction(self) -> str:
        return "Transfer funds from alice to bob."

    @property
    def api_docs_digest(self) -> str:
        return "mock_digest"


def diff_mock_db(db_a: dict, db_b: dict) -> list[dict[str, Any]]:
    """Compare two mock database states table by table and row by row."""
    diffs = []
    all_tables = sorted(set(db_a.keys()) | set(db_b.keys()))
    for table in all_tables:
        if table not in db_a or table not in db_b:
            diffs.append({"table": table, "type": "missing_table"})
            continue
        rows_a = db_a[table]
        rows_b = db_b[table]
        if len(rows_a) != len(rows_b):
            diffs.append({"table": table, "type": "row_count_mismatch", "a": len(rows_a), "b": len(rows_b)})
            continue
        for idx, (ra, rb) in enumerate(zip(rows_a, rows_b)):
            all_keys = set(ra.keys()) | set(rb.keys())
            for k in all_keys:
                if ra.get(k) != rb.get(k):
                    diffs.append({
                        "table": table,
                        "row_index": idx,
                        "field": k,
                        "val_a": ra.get(k),
                        "val_b": rb.get(k),
                    })
    return diffs


def _create_source_log(tmp_path: Path) -> Path:
    """Run a source episode and write its events.jsonl."""
    env = StatefulMockEnv()
    obs0 = env.reset("task-bank-1", 42)
    
    events = [
        Event(
            run_id="source-1",
            task_id="task-bank-1",
            system="planner_alone",
            seed=42,
            step=0,
            ts="2026-09-22T00:00:00Z",
            actor="system",
            event_type="run_start",
            payload={},
            env_state_hash=obs0.env_state_hash,
        )
    ]
    
    actions = [
        ExecutorAction(kind="CODE", code="apis.bank.transfer(from='alice', to='bob', amount=30)"),
        ExecutorAction(kind="CODE", code="apis.bank.close_account('bob')"),
    ]
    
    for i, act in enumerate(actions, 1):
        events.append(Event(
            run_id="source-1",
            task_id="task-bank-1",
            system="planner_alone",
            seed=42,
            step=i,
            ts="2026-09-22T00:00:00Z",
            actor="planner",
            event_type="action",
            payload=act.model_dump(),
        ))
        obs = env.step(act)
        events.append(Event(
            run_id="source-1",
            task_id="task-bank-1",
            system="planner_alone",
            seed=42,
            step=i,
            ts="2026-09-22T00:00:00Z",
            actor="environment",
            event_type="observation",
            payload={"text": obs.text},
            env_state_hash=obs.env_state_hash,
        ))
    
    log_path = tmp_path / "events.jsonl"
    log_path.write_text("".join(e.model_dump_json() + "\n" for e in events))
    return log_path


def test_snapshot_hash_blind_to_hidden_db_divergence():
    """Demonstrates that snapshot_hash (io-only) matches even when underlying DBs differ."""
    env1 = StatefulMockEnv()
    env1.reset("task-1", 1)
    # Normal execution mutating DB
    obs1 = env1.step(ExecutorAction(kind="CODE", code="apis.bank.transfer(from='alice', to='bob', amount=30)"))

    env2 = StatefulMockEnv(simulate_hollow_replay=True)
    env2.reset("task-1", 1)
    # Hollow execution returning same observation string but no DB mutation
    obs2 = env2.step(ExecutorAction(kind="CODE", code="apis.bank.transfer(from='alice', to='bob', amount=30)"))

    # 1. Observation text and hashes are identical
    assert obs1.text == obs2.text == "Transaction complete."
    assert obs1.env_state_hash == obs2.env_state_hash
    assert env1.snapshot_hash() == env2.snapshot_hash()

    # 2. But underlying database states diverge completely
    diffs = diff_mock_db(env1.db, env2.db)
    assert len(diffs) > 0
    # alice's balance: 70 vs 100
    balance_diff = next(d for d in diffs if d.get("field") == "balance")
    assert balance_diff["table"] == "accounts"
    assert balance_diff["val_a"] == 70
    assert balance_diff["val_b"] == 100


def test_faithful_replay_matches_db_state(tmp_path: Path):
    """Faithful replay reproduces both observation hash and full underlying DB state."""
    log_path = _create_source_log(tmp_path)
    
    # 1. Source simulation at k=1
    src_env = StatefulMockEnv()
    src_env.reset("task-bank-1", 42)
    src_env.step(ExecutorAction(kind="CODE", code="apis.bank.transfer(from='alice', to='bob', amount=30)"))
    src_db = src_env.db
    
    # 2. Replay prefix with faithful environment
    rep_env = StatefulMockEnv()
    world, remaining = replay_prefix(log_path, 1, rep_env)
    
    # Verify DB match
    diffs = diff_mock_db(src_db, world.db)
    assert len(diffs) == 0
    assert world.db["accounts"][0]["balance"] == 70
    assert world.db["accounts"][1]["balance"] == 80
    assert world.snapshot_hash() == src_env.snapshot_hash()


def test_db_diff_catches_divergent_underlying_state_when_hash_passes(tmp_path: Path):
    """A hollow replay passes observation hash checks but is caught by direct DB diffing."""
    log_path = _create_source_log(tmp_path)
    
    # 1. Source simulation at k=1
    src_env = StatefulMockEnv()
    src_env.reset("task-bank-1", 42)
    src_env.step(ExecutorAction(kind="CODE", code="apis.bank.transfer(from='alice', to='bob', amount=30)"))
    
    # 2. Hollow replay that fakes observation text
    rep_env = StatefulMockEnv(simulate_hollow_replay=True)
    world, remaining = replay_prefix(log_path, 1, rep_env)
    
    # Observation hash check falsely reports OK:
    assert world.snapshot_hash() == src_env.snapshot_hash()
    
    # Direct DB diffing successfully catches the divergence:
    diffs = diff_mock_db(src_env.db, world.db)
    assert len(diffs) == 3
    # Check that differences in accounts and audit_log are caught
    fields_diverged = {(d["table"], d.get("field", d.get("type"))) for d in diffs}
    assert ("accounts", "balance") in fields_diverged
    assert ("audit_log", "row_count_mismatch") in fields_diverged
