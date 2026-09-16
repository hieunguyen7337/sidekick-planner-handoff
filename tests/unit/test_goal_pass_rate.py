from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.setup.backfill_goal_pass_rate import backfill_campaign
from scripts.setup.campaign_summarize import summarise
from sidekick.environments.appworld_env import AppWorldEnv


class _Tracker:
    success = False
    pass_percentage = 42.9

    def to_dict(self, *, stats_only: bool) -> dict:
        assert stats_only is True
        return {"success": self.success, "pass_percentage": self.pass_percentage}


class _World:
    def evaluate(self, *, suppress_errors: bool) -> _Tracker:
        assert suppress_errors is True
        return _Tracker()


def test_appworld_evaluate_surfaces_normalised_goal_pass_rate() -> None:
    env = object.__new__(AppWorldEnv)
    env._world = _World()

    result = env.evaluate()

    assert result["goal_pass_rate"] == pytest.approx(0.429)
    assert result["tgc"] == 0.0
    assert result["sgc"] is None


def test_summariser_excludes_none_goal_pass_rates(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    rows = [
        {"seed": 1, "success": False, "goal_pass_rate": 0.6},
        {"seed": 2, "success": False, "goal_pass_rate": None},
    ]
    for index, row in enumerate(rows):
        path = root / "system" / str(index) / "task" / "result.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    summary = summarise(tmp_path, "campaign")

    assert summary["mean_goal_pass_rate"] == 0.6
    assert summary["n_goal_pass_rate"] == 1


def test_backfill_is_idempotent_and_uses_last_run_start(tmp_path: Path) -> None:
    run_dir = tmp_path / "campaign" / "system" / "1" / "task"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps({"success": False}) + "\n", encoding="utf-8"
    )
    events = [
        {"event_type": "run_start", "ts": "later", "payload": {}},
        {"event_type": "evaluate", "ts": "earlier", "payload": {"report": {"pass_percentage": 10}}},
        {"event_type": "run_start", "ts": "earlier", "payload": {}},
        {"event_type": "evaluate", "ts": "later", "payload": {"report": {"pass_percentage": 42.9}}},
    ]
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )

    first = backfill_campaign(tmp_path / "campaign")
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    second = backfill_campaign(tmp_path / "campaign")

    assert first["n_backfilled"] == 1
    assert result["goal_pass_rate"] == pytest.approx(0.429)
    assert second["n_backfilled"] == 0
    assert second["n_already_present"] == 1
