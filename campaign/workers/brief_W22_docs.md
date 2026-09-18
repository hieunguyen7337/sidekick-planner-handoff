# W-22 — apply two prepared documentation blocks

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

This is a **documentation unit only**. The prose is already written and reviewed. Your job is to
place it correctly, make it read as part of the surrounding document, and verify every
cross-reference. **Do not rewrite the analysis, do not change a single number, and do not add
findings of your own.**

## The two blocks

| source file (already in the repo) | destination |
|---|---|
| `campaign/workers/block_runs_delta.md` | append to `campaign/RUNS.md` |
| `campaign/workers/block_followups.md` | append to `docs/FOLLOWUPS.md` |

Both are complete Markdown with their own headings and a leading `---` rule. Append each to the
end of its destination file.

## What you must actually do (this is not a copy-paste unit)

1. **Append both blocks** to their destinations.
2. **Harmonise heading levels.** Read the destination's existing structure first. If `RUNS.md`
   uses `##` for top-level sections, the block's `##` headings are already right; if it nests
   differently, adjust the block's heading levels to match — *without changing the heading text*.
3. **Check every cross-reference in the appended text resolves.** The blocks refer to things like
   "the silent-zeros entries above" and "the root-cause entry above" in `FOLLOWUPS.md`. Verify
   such an entry actually exists earlier in that file. If one does not, say so in your report —
   **do not invent it and do not delete the reference**; leave it and flag it.
4. **Check for contradiction with what is already written.** `RUNS.md` already ends with a
   passage about interventions being rarely needed. The new δ and ceiling blocks must sit
   coherently after it. If the new block contradicts an earlier sentence in the same file, quote
   both in your report. Do not resolve a contradiction yourself — flag it.
5. **Remove the two staging files** `campaign/workers/block_runs_delta.md` and
   `campaign/workers/block_followups.md` once their content is in place, so the text lives in
   exactly one location.
6. **Table sanity.** Every Markdown table must render: matching column counts in the separator
   row and every body row. Several tables use right-aligned `---:` columns — keep them.

## Do not

- Do not change any number, any threshold, any count, or any file path in the blocks.
- Do not soften or strengthen any claim. The hedging is deliberate and was chosen carefully.
- Do not touch any file other than `campaign/RUNS.md`, `docs/FOLLOWUPS.md`, the two staging
  files (deleted), and your STATUS file.
- Do not commit.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. Do not run an interpreter, a package
  installer, `tar`, `rsync` or `ffmpeg` there. Any computation belongs in a PBS job via
  `timeout 900 hpc -c 2 -m 8gb -t 00:10:00 bash -lc '<cmd>'`. This unit should need none —
  it is reading and editing Markdown.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any GPU job.** The hosted-model
  quota is exhausted until 2026-09-19 ~21:13.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- Ignore `.claude/worktrees/` and `.git/`.
- Write `campaign/workers/STATUS_W_22.md` with resume state.

## Return contract

- The diff, as emitted.
- Confirmation that the two staging files are gone and their content appears exactly once.
- A list of every cross-reference you checked and whether it resolved, each with
  `[OBSERVED <path>:<line>]`.
- Any contradiction or heading-level problem you found, quoted, with both locations.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
