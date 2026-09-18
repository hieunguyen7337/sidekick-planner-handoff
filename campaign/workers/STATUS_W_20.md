# STATUS_W_20

**Task:** brief_W20_ceiling — re-cut the estimand excluding ceiling points (analysis only)
**Status:** DONE (2026-09-18)
**Ownership:** only `campaign/workers/scratch_W20/`, `campaign/workers/W20_CEILING.md`, this file.

## What was done

- Script `campaign/workers/scratch_W20/analyze_ceiling.py`.
- Run in PBS job **25433129.aqua** (`cpu1n040`, exit 0, walltime 4s). Verbatim output saved to `campaign/workers/scratch_W20/w20_out.txt`.
- Full analysis report written to `campaign/workers/W20_CEILING.md`.

## Headline findings

1. **Ceiling point fraction:**
   - Train: **131 of 397 complete points (33.00%)** are ceiling points ($\text{mean}(\text{untreated}) \ge 1.0$). Float noise check at $\ge 0.999$ gives exactly 131.
   - Dev: **68 of 332 complete points (20.48%)** are ceiling points. Float noise check at $\ge 0.999$ gives exactly 68.
2. **Floor points:**
   - Train: 3 points (0.76%). All $\Delta = 0.000$, $help = 0.000$, $harm = 0.000$.
   - Dev: 0 points (0.00%).
3. **Strict invariant confirmation:**
   - Invariant verified: `needed` counts are strictly identical between All complete points, Non-ceiling points, and Contestable points.
   - Train $\delta = 0.166$: `needed = 25` (f: 25/397 = 0.0630 -> 25/263 = 0.0951).
   - Train $\delta = 0.100$: `needed = 54` (f: 54/397 = 0.1360 -> 54/263 = 0.2053).
   - Dev $\delta = 0.166$: `needed = 43` (f: 43/332 = 0.1295 -> 43/264 = 0.1629).
   - Dev $\delta = 0.100$: `needed = 72` (f: 72/332 = 0.2169 -> 72/264 = 0.2727).
4. **Mean $\Delta$ sign flip on train:**
   - Train ceiling points impose a drag of **$-0.016225$** on overall mean $\Delta$.
   - Excluding ceiling points flips train mean $\Delta$ from **$-0.014393$** (all) to **$+0.002766$** (contestable, $+0.017159$ shift) with help ($0.0515$) > harm ($0.0487$).
   - Dev mean $\Delta$ increases from **$+0.009702$** to **$+0.023686$** (contestable, $+0.013984$ shift).

## Resume state

Nothing pending. No production code touched, nothing committed, no `/scratch` data writes, zero live planner calls, no GPU used. Everything is reproducible via `campaign/workers/scratch_W20/analyze_ceiling.py`.
