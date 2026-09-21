# STATUS_X15 — four exploratory prefix lengths

State: **done**. No commit, no `qsub`. PBS edit is `FREE_ARMS` only.

## Collision [OBSERVED login-node `ls`]

Exact ids `hj12_prefix_m{7,8,10,11}_20260922` are absent from `/scratch/n12194778/sidekick/results/` and nested `results/results/`. Present there: `hj12_prefix_m{2,4,6,9}_20260922` (nested also has `*_smoke` / `*smoke_smoke`).

```
ls: cannot access '/scratch/n12194778/sidekick/results/hj12_prefix_m7_20260922': No such file or directory
ls: cannot access '/scratch/n12194778/sidekick/results/results/hj12_prefix_m7_20260922': No such file or directory
```

Same miss for m8, m10, m11.

## Config diff [OBSERVED `timeout 15 diff`]

`diff configs/hj12_prefix_m9.yaml configs/hj12_prefix_m7.yaml`:

```
1c1
< # HJ-12 prefix-handoff m=9: replay the first 9 planner steps from HJ-1b, then
---
> # HJ-12 prefix-handoff m=7: replay the first 7 planner steps from HJ-1b, then
5c5
< campaign_id: hj12_prefix_m9_20260922
---
> campaign_id: hj12_prefix_m7_20260922
9c9
<   m: 9
---
>   m: 7
```

m8 / m10 / m11: the same three hunks only.

## FREE_ARMS [OBSERVED scripts/pbs/hj12_prefix.pbs:135-144]

```
FREE_ARMS=(
  "prefix_handoff|${REPO}/configs/hj12_prefix_m2.yaml|hj12_prefix_m2"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m4.yaml|hj12_prefix_m4"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m6.yaml|hj12_prefix_m6"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m7.yaml|hj12_prefix_m7"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m8.yaml|hj12_prefix_m8"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m9.yaml|hj12_prefix_m9"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m10.yaml|hj12_prefix_m10"
  "prefix_handoff|${REPO}/configs/hj12_prefix_m11.yaml|hj12_prefix_m11"
)
```

## Amendment heading [OBSERVED docs/prereg_hj12_dev_20260922.md:314]

`## Amendment 2026-09-22 — exploratory prefix lengths 7, 8, 10, 11 after seeing the first grid`

Appended after X13's P1/G1 section; registered text above it was not edited. Objection: X13 also names this file [INFERRED].

## bash -n [OBSERVED login-node]

```
bash -n scripts/pbs/hj12_prefix.pbs
bash -n exit=0
```

## verify_configs.py [OBSERVED hpc 25616223.aqua]

```
configs/hj12_prefix_m7.yaml
  packet subtree -> planner_alone
configs/hj12_prefix_m8.yaml
  packet subtree -> planner_alone
configs/hj12_prefix_m10.yaml
  packet subtree -> planner_alone
configs/hj12_prefix_m11.yaml
  packet subtree -> planner_alone
all configs OK
VERIFY_RC=0
```

## Suite [OBSERVED hpc 25616223.aqua]

```
501 passed, 1 skipped, 1 warning in 27.79s
PYTEST_RC=0
```
