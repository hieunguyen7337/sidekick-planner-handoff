"""Integration-test path setup. Do not import AppWorld or the network."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sidekick.agents.executor import MockExecutor
from sidekick.agents.planner import MockPlanner
from sidekick.agents.verifier import ConstantVerifier
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.mock_env import MockEnv
from sidekick.systems import get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog


@pytest.fixture
def run_system(tmp_path: Path, prices_path: Path):
    def _run(name: str, **kwargs):
        return run_named_system(tmp_path, name, prices_path, **kwargs)

    return _run


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def prices_path(tmp_path: Path) -> Path:
    candidate = ROOT / "configs" / "cost" / "prices_2026-09.yaml"
    if candidate.exists():
        return candidate
    path = tmp_path / "prices.yaml"
    path.write_text(
        "schedule_date: '2026-09-15'\n"
        "source: test\n"
        "models:\n"
        "  gpt-5.6-luna: {input: 0.20, cached_input: 0.02, output: 1.20}\n"
        "local:\n"
        "  usd_per_gpu_hour: 2.50\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def ledger(prices_path: Path) -> CostLedger:
    return CostLedger(PriceSchedule.load(prices_path))


def run_named_system(
    tmp_path: Path,
    name: str,
    prices_path: Path,
    *,
    planner=None,
    executor=None,
    verifier=None,
    limits: RunLimits | None = None,
    run_id: str | None = None,
    task_id: str = "copy_hello",
    seed: int = 1,
    **system_kwargs,
):
    planner = planner or MockPlanner()
    executor = executor or MockExecutor()
    verifier = verifier or ConstantVerifier(0.5)
    env = MockEnv()
    log = EventLog(tmp_path, run_id or f"{name}_{task_id}_{seed}")
    ledger = CostLedger(PriceSchedule.load(prices_path))
    system = get_system(
        name,
        planner=planner,
        executor=executor,
        verifier=verifier,
        limits=limits or RunLimits(),
        **system_kwargs,
    )
    result = system.run(env, task_id, seed, log, ledger)
    log.close()
    events_file = tmp_path / (run_id or f"{name}_{task_id}_{seed}") / "events.jsonl"
    return result, events_file, ledger, planner, executor
