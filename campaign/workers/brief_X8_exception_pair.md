# Brief X8 — the exception pair shares a campaign id and does not test the channel

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Config-only, plus one test. **Two GPU jobs are running.** Do not `qsub`, do not touch a GPU, do not
run any evaluation. You may run the pytest suite through `hpc` as described below.

## Two defects, both found by the unit that built these files

### 1. A campaign-id collision that would destroy data

```
configs/hj12_takeover_exception.yaml:campaign_id: hj12_exception_20260923
configs/hj12_advise_exception.yaml:campaign_id:  hj12_exception_20260923
```

They are meant to be two different arms. Sharing an id means both write into
`/scratch/n12194778/sidekick/results/hj12_exception_20260923/`, and the second run silently
overwrites or interleaves with the first. This project's standing rule is **new arm, new prefix**.
Give them distinct ids: `hj12_takeover_exception_20260923` and `hj12_advise_exception_20260923`.

Then check **every** `configs/hj12_*.yaml` id against each other and against the directories already
present under `/scratch/n12194778/sidekick/results/` (read-only `ls`), and report the full list.
A collision with an existing tree is as destructive as a collision between two new arms.

### 2. The pair does not actually contrast the two channels

The two files differ only in `takeover: true`. But both select the **`action_review`** path, whose
gate already calls `planner.act` and executes the returned action
[OBSERVED src/sidekick/systems/action_review_gate.py]. The `takeover` flag only changes the
`force_review` branch of the episode loop [OBSERVED src/sidekick/systems/loop.py, the
`elif force_review` branch]. So `takeover: true` is inert here and **both arms act**. There is no
advise arm, and running them would spend hosted calls to compare a policy with itself.

The whole point of this pair is the label-free trigger version of Claim C1: at the same trigger and
the same call count, does a planner that **acts** beat a planner that **advises**?

**Rebuild both on the router path**, which routes an escalation into the ordinary
`force_review` branch where the `takeover` flag is live:

- `hj12_advise_exception.yaml`: system `router_seq`, `use_router: true`,
  `verifier: {kind: rule_trigger, rules: [on_exception], threshold: 0.5}`, **no** `takeover` key.
  An exception scores 1.0, exceeds the threshold, forces a review, and the planner's prose is
  injected as an `INTERVENTION:` turn.
- `hj12_takeover_exception.yaml`: byte-identical except `takeover: true`, so the planner's action is
  executed instead.

Confirm from the source that `RuleTriggerVerifier` returns 1.0 on an exception and that the router
escalates above its threshold; if the wiring does not work that way, **stop and say so in STATUS
rather than inventing a config that looks plausible**. A config that silently fails to escalate
would produce two identical arms and a null result that means nothing — this campaign has already
lost a full frontier to exactly that failure.

Keep every executor setting, `limits` block and `prices` path identical to the frozen
`configs/hj11_action_review_exception.yaml` they descend from, so the two arms differ from each
other in exactly one key. Paste the `diff` of the final pair into STATUS; it must show one line.

## Do not touch

`src/`, `scripts/`, the four `configs/hj12_prefix_m*.yaml`, `configs/hj12_takeover_fixed_k_{3,10}.yaml`
and `configs/hj12_planner_handoff.yaml` (those three are correct: `fixed_k` and `planner_drives`
both reach the `force_review` path where `takeover` is live), and any `hj8_*`/`hj11_*` config
(FROZEN).

## Test

Add one test asserting that the two exception configs differ in exactly one key and that their
`campaign_id` values are distinct — a cheap guard against this recurring. Put it wherever config
validation tests already live; if there is no such file, add it to the existing config test module
rather than creating a new one.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. Suite via
  `timeout 1800 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src:. /scratch/n12194778/sidekick/env/bin/python -m pytest tests -q --import-mode=importlib'`
- Suite is at **483 passed, 1 skipped** and must not fall.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Also run `scripts/setup/verify_configs.py` if it accepts the new configs, and paste the result.
- Dev only. **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X8.md`, under 450 words: the full `hj12_*` campaign-id list with the
collision check against `/scratch`, the one-line diff of the rebuilt pair, the evidence that
`rule_trigger` + router actually escalates (with `path:line`), the test name, and the pasted suite
line. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
