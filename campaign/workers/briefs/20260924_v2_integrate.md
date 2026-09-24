# Unit V2INT: integrate the new ledger rows into Paper A v2, and rewrite §4 under h*

WT = /mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15. Written by Claude, 2026-09-24.
Edit only `paper/preprint_dev_v2_20260924.md` and `paper/bibliography.bib`, plus the small code
extension in §5 below. Numbers come only from ledger rows in `docs/claims_ledger.md`. No exploratory result
may be called registered. `scripts/analysis/preprint_number_audit.sh paper/preprint_dev_v2_20260924.md` must
exit 0 at the end. The main text (from `## 1.` to `## Appendix A.`) must be ≤ 7,300 words by `wc -w`. Do not
commit.

## 1. Fill every `[[NEEDS LEDGER: ...]]` marker (`grep -n 'NEEDS LEDGER'`)
- Rows added 2026-09-24:
  - CEIL-10, NOISE-06, UF-09, DEC-07, LIM-07, LIM-08, MECH-11, ROB-22..27, NARR-06, UF-10, FDR-02, CENSUS-02;
  - PLANTAX-01..06, TERM-01..04, CEILHI-01..03;
  - HSTAR-01..16.
- Staging files that map markers to rows:
  - `campaign/workers/staging/ledger_rows_20260924_v2fill.md`;
  - `.../ledger_rows_20260924_planning.md`;
  - `.../ledger_rows_20260924_hstar.md`.
- CEIL-10: say "a leaderboard entry whose method learns context assets on train", not "full scaffold".
- FDR-02 replaces FDR-01's scope wherever the paper describes BY over what it prints: 13 of the 60 main-text
  intervals survive.

## 2. Corrections the new rows force
- **§2.5 seed.** 13 printed intervals were drawn at seed 20260915 (the `j8_frontier` default), not 20260924.
  Source: `campaign/results/j17_v2_fill_20260924.report.json` key `by_main_text.reproduction.checked_at_source_seed`.
  - State in §2.5: "seed 20260924 unless the ledger row states 20260915".
  - List the 13 in Appendix A.4.
- **Task clustering.**
  - The hinge test's p is 0.036 on scenarios and 0.054 on tasks (ROB-24). Say it does not survive task clustering.
  - The tailored m = 9 narration non-inferiority fails on tasks, and the tailored m9 → m11 rise includes 0 on
    tasks (NARR-06). Correct §5 and D.5 accordingly.
- **§4 under h\* (the largest change).** The handoff indicator in every dev handoff-only number is now h*, "the
  executor took control" (HSTAR-01). HO-02..HO-NI-03 become the flag sensitivity (Appendix only).
  - §4.1: at m = 11 the replayed prefix ends the episode in 83 of 171 (HSTAR-02). In 17 more, the source planner
    ran out of steps without finishing, and the executor took over and beat it by +48.29 pp (HSTAR-14).
    - Rewrite the claim that "on those episodes the arm scores what the planner scored" accordingly.
    - One sentence on why the flag misled (A11 note on HO-01), in Appendix E.1 as a defect found and repaired.
  - §4.2 and Table 5: handoff-only values from HSTAR-05..10.
    - m6 → m11, `goal_pass`: +7.66 tailored, +7.81 untailored, n = 88.
    - Handoff and silenced rises are now of similar size.
    - TGC handoff-only m6 → m11 no longer resolves.
  - §4.6 and the abstract's NI bullet: over handoff episodes, `goal_pass` NI now **holds** at m9 and m11 on both
    receivers (HSTAR-11, HSTAR-12). TGC handoff-only still fails (HSTAR-13).
    - Beside it, CEILHI-03: against the high-effort planner alone, neither m11 prefix is non-inferior.
    - The honest sentence is: "non-inferior to the medium-effort planner in this harness, including over the
      episodes the executor actually took over; not to the same planner at high effort".
  - Abstract "Depth" bullet and §1: remove "larger over handoff episodes". State the corrected counts.
- **Held-out tests paragraph (line ~30) and Appendix C.3.**
  - J12's D3/D4 now use h* (J12 Amendment 1); power at the dev effect is 0.866 / 0.819, and 0.733 for all four
    (HSTAR-15).
  - J10's handoff-only companions use h* (A1 Amendment 3).
  - Name the amendments; there are no new commits to cite beyond what the ledger rows give.
- **§4.7 (CEILHI):** replace the placeholder with CEILHI-01..03.
  - +11.97 pp `goal_pass` and +19.30 TGC over medium effort.
  - Fewer hosted calls (0.7867×).
  - The NI re-read.
  - Keep the heading, but drop "(pending dev arm)".
- **§3.3 (TERM):** our executors never stop before acting. They run to the limit (TERM-02), the opposite of the
  failure Fan et al. report. Use TERM-01..04.
- **§7 Table 7 paragraph (PLANTAX):**
  - DiD1 goal_pass +9.11 does not resolve; TGC +22.81 does.
  - Tailoring is worth +42.97 pp with a plan, and nothing detectable with executed actions (DiD2 +38.85..+45.43).
  - Qwen gives no third point (PLANTAX-06).
  - This is the paper's best evidence that plan-following is learned and that the action channel bypasses it. Say
    so once, in §7 or §3.4, labelled exploratory.

## 3. The cap-25 source (small code extension; do it before §2's §4 edits cite SHAPE-06 / ROB-12)
- §4.1 cites SHAPE-06: "on the cap-25 source the executor never acted in 56 of 114".
- ROB-12's explanation may carry the same flag error, since the code is the same.
- Extend `scripts/analysis/j17_hstar.py` with a counts-only block for the cap-25 prefix family (the arms behind
  SHAPE-06 / ROB-12; find them from those rows' artifact keys): per depth, flag-true, live-but-unflagged and
  terminal.
  - Add a test.
  - Re-run the report in a PBS job via `hpc`. The existing keys must not change: diff the JSON before and after,
    excluding the new block and `generated_at`.
- Draft rows HSTAR-17.. in `campaign/workers/staging/ledger_rows_20260924_hstar.md`, below the existing ones.
- Tell Claude whether SHAPE-06's "never acted" count is right. Do not write a ledger row into
  `docs/claims_ledger.md`; Claude appends it. Until then, cite the new staging row id with a
  `[[NEEDS LEDGER: HSTAR-17]]` marker, which is Claude's to resolve.

## 4. Length
Main text ≤ 7,300 words (`wc -w`). Move detail to the appendices.

## Constraints
- aquarius01 is a login node: no python/pytest there. Compute via `hpc bash -c '...'`, with `OMP_NUM_THREADS=1`,
  `/scratch/n12194778/sidekick/env/bin/python` and `PYTHONPATH=src:.`. Put a timeout on everything.
- No held-out reads, no `j10_`/`j11_`/`j12_` results. No git writes. No codex workers: a hosted test arm owns the
  quota window.
- Read narrowly: `grep -n` first, then offset/limit reads.

## Report (≤ 300 words)
- word count and the audit's last lines;
- each marker and the row that filled it;
- each §2 correction with its paper line;
- the cap-25 counts and SHAPE-06's verdict;
- files changed.
