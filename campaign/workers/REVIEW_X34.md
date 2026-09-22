# Review of X34 — one defect to fix before this is committed

Reviewed by Claude, 2026-09-22 17:10, against the working tree.

## What is correct

The three configs differ from their `hj12_prefix_m{6,9,11}` counterparts in exactly three places —
the header comment, `campaign_id`, and `executor.lora_name` — and in nothing else. Verified by
`diff` on all three pairs. That is the whole experiment, and it is right.

`MAX_LORAS` is 4 and granite now registers 2, so the count guard at `scripts/pbs/hj12_prefix.pbs:947`
passes. `ALLOWED_ALIASES` correctly becomes `(sft_b_plus sft_b_plus_handoff)` for granite, so an arm
asking for either alias is accepted and one asking for anything else still fails loudly.

## The defect

`register_lora` **exits 2 when the adapter path is not a directory**
[OBSERVED `scripts/pbs/hj12_prefix.pbs:352-355`], and the new handoff registration is
**unconditional for granite** [OBSERVED `:939-942`]:

```
  if [[ "${MODEL}" == "${MODEL_GRANITE}" ]]; then
    echo "[hj12] serving_record ... alias=${ALIAS_SFT_B_PLUS_HANDOFF} ..."
    register_lora "${ALIAS_SFT_B_PLUS_HANDOFF}" "${ADAPTER_SFT_B_PLUS_HANDOFF}"
  fi
```

So **every** granite job now requires `sft_b_plus_handoff_granite8b` to exist, whether or not any
handoff arm is in the group. The adapter does not exist yet — training is in flight as job 25690949 —
so as the tree stands, a new granite job of *any* kind dies at startup. That includes re-running the
`hj12_prefix_*` and `hj13_prefix_zs_*` arms, which have nothing to do with this unit.

The brief did say a missing adapter should fail loudly. It should fail loudly **for the arms that
need it**, not for unrelated arms that happen to share a base model.

## The fix

Register the handoff adapter only when the group actually contains an arm whose `executor.lora_name`
is `${ALIAS_SFT_B_PLUS_HANDOFF}`. `GROUP_ARMS` is already assembled just above, and
`hj12_executor_fields` already yields each arm's `lora_name`, so the condition is available without
new machinery. Keep `ALLOWED_ALIASES` as it is.

That preserves the loud failure where it belongs: an `hj13_prefix_hf_*` arm still reaches
`register_lora` with a missing path and still exits 2.

Add a test for the case the current code gets wrong: a granite group containing **only**
`hj12_prefix_*` / `hj13_prefix_zs_*` arms must not require the handoff adapter.

## Not blocking

Two running jobs (25681998, 25687449) read the pre-edit script and are unaffected.
