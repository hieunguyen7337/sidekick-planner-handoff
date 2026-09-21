# STATUS_X2 — takeover channel

State: **done**. No commit (brief). No GPU, no eval, no hosted planner, no `/scratch/.../results` writes.

## Files / signatures

Modify:
- `src/sidekick/protocols/schemas.py` — `ExecutorAction.kind` appends `"HANDOFF"`; `EventType` appends `"handoff"`. [OBSERVED src/sidekick/protocols/schemas.py:67, :106-108]
- `src/sidekick/systems/loop.py` — `SystemPolicy.takeover: bool = False`, `handoff_allowed: bool = False`; `action_from_planner(resp, step, *, fatal_parse=True)`; takeover on the `force_review` branch calls `planner.act` on the full transcript; `driver_is_planner` + `HANDOFF` consume the step; `run_end` payload adds `n_planner_actions`, `handoff_step`. [OBSERVED src/sidekick/systems/loop.py:66-67, :409-415, :614-617, :769-785, :842-886, :1108]
- `src/sidekick/agents/planner.py` — `act(..., allow_handoff: bool = False)` on Protocol, `CodexExecPlanner`, `MockPlanner`, `CachedPacketPlanner`. [OBSERVED src/sidekick/agents/planner.py:343-349]
- `src/sidekick/systems/action_review_gate.py` — `run_action_review(..., task_id: str)`; transport `planner.act`. [OBSERVED src/sidekick/systems/action_review_gate.py:28-41, :62]
- `src/sidekick/systems/__init__.py` — append `planner_handoff` after `prefix_handoff`.
- `src/sidekick/runner.py` — `system_kwargs` forwards `takeover`/`handoff_allowed`; `adapter_name` for `planner_handoff`. [OBSERVED src/sidekick/runner.py:242, :252-254]
- `src/sidekick/systems/prefix_handoff.py` — `m == 0` may fall through; else `RuntimeError` naming `source_campaign`. [OBSERVED src/sidekick/systems/prefix_handoff.py:153-157]
- `scripts/pbs/hj12_prefix.pbs` — directory `#PBS -o/-e`. [OBSERVED scripts/pbs/hj12_prefix.pbs:15-16]
- `src/sidekick/protocols/prompts.py` — `format_executor_action` for `HANDOFF` (not listed; needed once the kind exists). [OBSERVED src/sidekick/protocols/prompts.py:200-201]
- `tests/unit/test_action_review.py` — replacement scripts `act`; added real-planner stub test.
- `tests/integration/test_eight_systems_mock.py` — exact `SYSTEM_NAMES` tuple includes `planner_handoff` (equality, not prefix). [OBSERVED tests/integration/test_eight_systems_mock.py:9-21]
- `tests/unit/test_executor_prompt.py` — `_RecordingPlanner.act` accepts `allow_handoff`.

Create: `src/sidekick/systems/planner_handoff.py` (`class PlannerHandoff(PlannerAlone)`, `policy_defaults = replace(PlannerAlone.policy_defaults, handoff_allowed=True)`); `tests/unit/test_takeover.py`; five `configs/hj12_*.yaml`.

## Exception-config diff

```
5d4
< takeover: true
```

[OBSERVED `timeout 15 diff configs/hj12_takeover_exception.yaml configs/hj12_advise_exception.yaml`] Same `campaign_id` so they differ by that one key; operators must pass `--campaign-id`.

## Takeover channel

`test_takeover_appends_no_intervention_turn` — `n_interventions == 0`, no `event_type=="intervention"`, no `INTERVENTION:` in payloads, `n_planner_actions == 1`. [OBSERVED tests/unit/test_takeover.py:127-145] Advise path still appends `INTERVENTION:` at the non-takeover branch. [OBSERVED src/sidekick/systems/loop.py:829-830]

## Suite

```
timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

Verbatim final line [OBSERVED /home/n12194778/.hpc-spool/20260921-144505-1271053.out:16]:

```
483 passed, 1 skipped, 1 warning in 39.27s
```

Job `25597133.aqua`. Brief's 472 floor not breached. `bash -n` on `hj12_prefix.pbs` OK. [OBSERVED login-node `bash -n`]

## Brief vs code

- Review trigger is the `elif force_review` branch; brief said `:752`, it was `:753` and is now `:768` after inserts. [OBSERVED src/sidekick/systems/loop.py:768]
- Exception pair is still `action_review` (gate via `review_proposed_action`). `takeover` only changes the scheduled/router/oracle `force_review` branch, so that YAML key does not switch the exception gate from advise to act-execute. [INFERRED] The gate already calls `act` for approve/replace. [OBSERVED src/sidekick/systems/action_review_gate.py:62]
- `act` gained `allow_handoff` on Protocol, MockPlanner, CachedPacketPlanner as well as CodexExecPlanner; loop always passes it. [OBSERVED src/sidekick/systems/loop.py:777, :850]
- Unscripted `MockPlanner.act` with `PROPOSED_ACTION:` in the transcript returns no code so `test_approval_executes_proposal` still approves. [OBSERVED src/sidekick/agents/planner.py after the canned pop]
