# Brief X35 — scope the handoff-adapter registration to the arms that need it

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

A small, well-specified fix plus two verification runs. **Do NOT `qsub` an evaluation and do not touch
a GPU** — I submit every job myself. Two GPU jobs and a training job are in flight. Run tests through
`hpc` in the **foreground** under `timeout`; never background a command and exit.

## The defect

X34 added a second granite LoRA alias so the handoff-specialised adapter can be served beside
`sft_b_plus`. The configs it wrote are correct and are not in scope here. The wiring is not.

`register_lora` **exits 2 when the adapter path is not a directory**
[OBSERVED `scripts/pbs/hj12_prefix.pbs:352-355`], and the new registration is **unconditional for the
granite base model** [OBSERVED `:939-942`]:

```
  if [[ "${MODEL}" == "${MODEL_GRANITE}" ]]; then
    echo "[hj12] serving_record ... alias=${ALIAS_SFT_B_PLUS_HANDOFF} ..."
    register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"
  fi
```

So **every** granite job now requires `/scratch/n12194778/sidekick/artifacts/adapters/sft_b_plus_handoff_granite8b`
to exist, whether or not any handoff arm is in the group. That adapter does not exist yet — training
is in flight as job 25690949 — so as the tree stands, a new granite job of *any* kind dies at startup.
That includes re-running `hj12_prefix_*` and `hj13_prefix_zs_*`, which have nothing to do with the
handoff adapter. X34's own STATUS notes `register_lora` still fatals on a missing path, so this is a
known gap, not a surprise.

A missing adapter **should** fail loudly — for the arms that ask for it. Not for unrelated arms that
merely share a base model.

## The fix

Register the handoff adapter only when the group being served actually contains an arm whose
`executor.lora_name` equals `${ALIAS_SFT_B_PLUS_HANDOFF}`.

`GROUP_ARMS` is assembled immediately above the registration and `hj12_executor_fields` already yields
each arm's `lora_name`, so the condition needs no new machinery — do not add a filesystem existence
check as the condition, because that would silently skip a genuinely missing adapter and send those
requests to the base model, which is the exact failure this campaign must avoid.

Leave `ALLOWED_ALIASES` exactly as it is [OBSERVED `:910-913`]: an arm asking for either granite alias
must still be accepted, and one asking for anything else must still fail.

After the fix, an `hj13_prefix_hf_*` arm with a missing adapter must **still** reach `register_lora`
and still exit 2.

## Tests

Add to `tests/unit/test_hj13_prefix_hf.py`:

1. A granite group containing only `hj12_prefix_*` / `hj13_prefix_zs_*` arms **does not** require the
   handoff adapter. This is the case the current code gets wrong; the test must fail before your fix.
2. A granite group containing an `hj13_prefix_hf_*` arm **does** require it, and a missing adapter
   directory is still fatal.

## Also verify, and report honestly

X34 ran the suite as `pytest tests -q --import-mode=importlib --ignore=tests/unit/test_j8_frontier.py`
and reported **503 passed**, against a baseline of **543 passed, 1 skipped** from job 25689191.
Run the suite **without** that `--ignore` and paste the line. If `tests/unit/test_j8_frontier.py`
fails or errors, say so plainly and report the failure text — do not ignore it again and do not fix it
in this unit. `j8_frontier.py` is the tool the receiver contrast and the pinned curve both run through,
so its test state matters and I need to know it either way.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command; run tests via `hpc`; BLAS pinned to one thread.
- **Read-only** on `/scratch/n12194778/sidekick/results/`. Dev only; never read or list `test_normal`
  or `test_challenge`.
- Do not edit any `configs/hj13_prefix_hf_*.yaml`, any `docs/prereg_*.md`, any `hj8_*`/`hj11_*` config,
  `scripts/analysis/j8_frontier.py`, or anything under `src/sidekick/training/`.
- `scripts/setup/verify_configs.py` must still print "all configs OK", and `bash -n` on the PBS script
  must still exit 0.
- **Make your first edit within your first three actions. Never background a command and exit.**
- **Write `campaign/workers/STATUS_X35.md`** even if you finish only part, saying plainly what is
  missing. **Do not commit.** I review and commit.

## Return contract

`campaign/workers/STATUS_X35.md`, under 300 words: the diff hunk you changed with its line numbers,
the two test names, the pasted `verify_configs.py` line, the pasted `bash -n` exit, and the pasted
full-suite line **including** `test_j8_frontier.py`. Tag every claim `[OBSERVED <path>:<line>]` or
`[INFERRED]`.
