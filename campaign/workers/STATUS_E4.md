# STATUS E4 — action-reviewing planner (retry of E4)

**Unit:** E4 — `rule_trigger` verifier + `action_review` system. BUILD AND UNIT TESTS ONLY.
**State:** done
**Last update:** 2026-09-20

## Owned files (added / changed)

- `src/sidekick/agents/verifier.py` — `RuleTriggerVerifier` `:96`, marker `Execution failed. Traceback:` `:56`, default rules `[on_exception]` `:57`
- `src/sidekick/systems/action_review.py` — `ActionReview` `:9` (`review_proposed_action=True`)
- `src/sidekick/systems/action_review_gate.py` — `run_action_review` `:15` (planner.correct seam)
- `src/sidekick/systems/loop.py` — `SystemPolicy.review_proposed_action` `:65`; run_start flag only when True `:602-603`; post-proposal hook `:815-828`
- `src/sidekick/systems/__init__.py` — registered ninth name `action_review` `:23,:35`
- `src/sidekick/runner.py` — `kind == "rule_trigger"` `:217`; `system_kwargs` `:242,:246`
- `src/sidekick/protocols/schemas.py` — `EventType` includes `"action_review"` `:108`
- `configs/hj11_action_review_exception.yaml` — on_exception only
- `configs/hj11_action_review_exception_irreversible.yaml` — both rules
- `tests/unit/test_action_review.py` — nine tests `:58-:196`
- `tests/integration/test_eight_systems_mock.py` — tuple includes `action_review` `:18`
- this STATUS

No GPU, no planner API, no eval, no qsub, no git, no `/scratch/.../results/`, no `hj8_*`, no frozen prereg. Did not touch E2 STATUS or artifacts.

## Behaviour

Gate is `verifier.score > threshold`. `on_exception` reads `last_observation`; `on_irreversible` reads `proposed_action`. [OBSERVED src/sidekick/agents/verifier.py:114-120] [OBSERVED src/sidekick/systems/action_review_gate.py:40-42]

Verdict fits existing `PlannerResponse`: non-empty differing `resp.code` → replace and execute; else approve and execute the proposal. [OBSERVED src/sidekick/systems/action_review_gate.py:53-61] A review is one `call_planner("correct", ...)`. [OBSERVED src/sidekick/systems/action_review_gate.py:46-50]

run_start policy keys for the original eight systems are unchanged; the new flag is appended only when True. [OBSERVED src/sidekick/systems/loop.py:602-603] [OBSERVED tests/unit/test_action_review.py:221-224]

## Suite [OBSERVED hpc job 25573530.aqua]

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15 && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'
```

Verbatim final line:

```
456 passed, 1 skipped, 1 warning in 29.04s
```

Baseline was 447 passed + 9 new tests. [INFERRED 447+9=456]

## Objections (implemented anyway)

- Seam contract lists eight `SYSTEM_NAMES` and no `action_review` EventType. Markdown contract not edited. [OBSERVED campaign/briefs/SEAM_CONTRACT.md:70-73, :185]
- `run_episode` has no `action_reviewer` argument; the planner is the reviewer via `correct()`. [OBSERVED src/sidekick/systems/loop.py:234, :815]

## Not done

Evaluation of this arm. Resume: `--system action_review` with a `hj11_action_review_*.yaml`; do not submit that from this unit.
