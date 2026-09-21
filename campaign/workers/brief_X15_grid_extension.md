# Brief X15 — four more prefix lengths to locate a threshold the first grid revealed

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Configs and one pre-registration amendment. No GPU jobs are running now, but **do not `qsub`** —
I submit. Do not edit `src/`, `scripts/`, or any existing config.

## Why

The first grid ran prefix lengths 2, 4, 6 and 9 against a plan-only floor of 0.7181 and a
planner-alone ceiling of 0.8284 on `goal_pass_rate` [OBSERVED
`campaign/results/hj12_prefix_frontier_20260922.report.json`]:

| prefix | goal_pass | tokens/ep | share of planner |
|---:|---:|---:|---:|
| 2 | 0.7187 | 78,346 | 11% |
| 4 | 0.7340 | 143,753 | 21% |
| 6 | 0.7145 | 221,043 | 32% |
| 9 | 0.8134 | 357,448 | 52% |

Flat through six, then most of the eleven-point gap closes by nine. The interesting region is
between six and nine and nothing was measured there. The registered gate assumed the useful prefix
would be six or shorter; it is not, and the gate failed.

Cost matters too. Claim C2 needs non-inferiority at **no more than about half** the planner's
non-cached tokens. The nine-step arm sits at 52%, just over. Seven and eight steps should land near
40% and 46%, so if quality plateaus before nine, C2 becomes reachable on cost rather than just
missed.

## Configs to create

Copy `configs/hj12_prefix_m9.yaml` exactly, changing only the header comment, the `campaign_id`, and
`handoff.m`. Everything else — the frozen executor block, `limits`, `prices`, and the
`source_campaign` / `source_system` pair — must be byte-identical to the existing prefix configs, so
these arms differ from the first grid in one number only.

| file | `campaign_id` | `m` |
|---|---|---:|
| `configs/hj12_prefix_m7.yaml` | `hj12_prefix_m7_20260922` | 7 |
| `configs/hj12_prefix_m8.yaml` | `hj12_prefix_m8_20260922` | 8 |
| `configs/hj12_prefix_m10.yaml` | `hj12_prefix_m10_20260922` | 10 |
| `configs/hj12_prefix_m11.yaml` | `hj12_prefix_m11_20260922` | 11 |

Verify none of those campaign ids already exists under `/scratch/n12194778/sidekick/results/`
(read-only `ls`) and paste the check. Then paste
`diff configs/hj12_prefix_m9.yaml configs/hj12_prefix_m7.yaml` — it must show only the comment, the
id and `m`.

Add each new arm to the `FREE_ARMS` list in `scripts/pbs/hj12_prefix.pbs`. That list is the only
thing you may change in that file; do not touch the port logic, the alias check, the teardown or the
`#PBS` directives.

## The amendment — this part matters more than the configs

Extend `docs/prereg_hj12_dev_20260922.md` with a **new, dated, clearly headed** amendment section.
Do not edit registered text above it.

It must say, plainly and without softening:

- These four prefix lengths were chosen **after seeing the first grid's results**, specifically
  because the jump between six and nine was unanticipated.
- They are therefore **exploratory, not confirmatory**. Their purpose is to locate where the
  threshold sits and whether quality plateaus before nine steps. No claim is established by them
  alone.
- **Gate G1 failed as registered.** Record both limbs and why each failed: no arm at six steps or
  fewer approached the seven-point non-inferiority margin, and the curve is not monotone because the
  six-step arm scored 0.7145 against the four-step arm's 0.7340. State that the two-point difference
  between those arms is well inside the paired intervals and is most likely sampling noise, and that
  this is an explanation, not a reason to treat the gate as passed.
- Any confirmatory claim about an optimal prefix length must be re-registered and tested on data not
  used to choose it. Name the test split as where that would happen, and note it needs explicit
  authorisation that has not been given.
- The honest population for any prefix arm is the handoff-only one. Record that at nine steps, 32 of
  114 episodes never handed off and scored identically to the planner, that the planner scores 0.8961
  on those against 0.8020 on the rest, and that the pooled figure is therefore optimistic.

Write it so a sceptical reader can see exactly which choices were made after seeing data. That
transparency is the point; a reader who cannot tell will discount everything.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there.
- `timeout` on every command. **Read-only** on `/scratch/n12194778/sidekick/results/`.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, every `hj8_*` and `hj11_*` config.
- `bash -n scripts/pbs/hj12_prefix.pbs` and paste the result.
- Run `scripts/setup/verify_configs.py` and paste the result.
- The suite is at **501 passed, 1 skipped** and must not fall.
- Dev only; never read `test_normal` or `test_challenge`.
- **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X15.md`, under 450 words: the collision check, the one config diff, the
`FREE_ARMS` line, the amendment's heading, and the pasted `bash -n`, `verify_configs.py` and suite
lines. Tag claims `[OBSERVED <path>:<line>]` or `[INFERRED]`.
