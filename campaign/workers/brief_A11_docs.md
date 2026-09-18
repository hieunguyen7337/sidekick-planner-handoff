# A11 (U-DOC) — bring the record in line with what we now know

Repo: `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

**Do not commit.** Your files: `campaign/RUNS.md`, `docs/PLAN.md`, `docs/HEAVY_JOBS.md`,
`docs/prereg_v1.md`, `docs/FOLLOWUPS.md`, and `src/sidekick/agents/verifier.py` **only** for the
one stale comment reference named below.
**Do not touch** anything else under `src/`, `configs/`, `scripts/`, or `tests/`. No code changes
beyond that single comment. No refits, no re-runs.

🔺 **Mechanics — the previous docs-lane unit died on these.** Do not background a task and exit;
this unit needs **no PBS job at all**, so run nothing heavy. Write
`campaign/workers/STATUS_A_11.md` in your first three actions and update it per milestone, and
save each document edit as you make it rather than batching everything to the end.

## Why this matters

This is the document set a reviewer reads. Several entries in it are now **wrong**, and two of
them are wrong in the direction that flatters us. Fixing that is the unit.

## 1. Fold in the results that have landed since the record was last updated

Each has a committed report; read it rather than working from this summary. Cite `path:line`.

- **W-24 — the train ASK labels are indistinguishable from noise.** Paired sign-flip permutation
  null, 10,000 permutations. Train `needed` 25 vs null mean 26.97, **p = 0.712** at δ = 0.166 —
  *below* the null mean; **p = 0.412** at δ = 0.100. Widening the band recovers more noise, not
  more signal. Dev differs: `needed` p = 0.0204 and `needless` p = 0.0225 are *both* elevated with
  asymmetry exactly 0. See `campaign/workers/W24_PERMNULL.md`, commit `41938fa`.
- **W-25 — that null is largely an artefact of the estimand.** The reviewer was left live in both
  arms, so the untreated arm gets a substitute ~5 steps later; Δ measured timing, not value. Train
  Spearman ρ(`n_later`, Δ) = −0.163, p = 0.0007. On the clean subset (`n_later = 0`, 175 train
  points) `needed` clears its null at p = 0.0051. ⚠ **Doubly post-hoc, and dev does not reproduce
  the dose-response** (ρ = +0.095, n.s.). Record it as licensing a pilot, **not** a claim. See
  `campaign/workers/W25_SUBSTITUTION.md`, commit `113b249`.
- **A7 — the value function is no better than a step counter.** Dev AUROC 0.6212, task-level
  bootstrap CI [0.546, 0.689], against a feature-blind step-prior floor of **0.6245** and a k-NN
  ceiling proxy of 0.6356. It lands *below the floor*. Commit `b6af8f4`.
- **A9 — the J7 threshold was meetable, and 0.59 is a real miss.** Commit `0499d01`. See §3.
- **A10 — `hash_match` was an off-by-one**, not a model failure: `gold_obs` was the observation
  after the *next* action, and since `snapshot_hash` covers a growing io log a match was
  arithmetically impossible. Probe schema version 3 → 4; **every version-3 `hash_match` value is
  False and meaningless.** `state_equivalent` (0.676) is unaffected. Commit `5511775`.
- **A4/A5/A6/A8/A12/A13** — the J8 harness, the twelve configs, the `feature_lr` wiring fix, the
  `suppress_next` branch mode, the J10 analysis script, and the adapter/SMOKE_ONLY guards.
  Commits `c9e1733`, `be4d2d6`, `da4c115`, `a25d8c9`, `0105d9e`, `8c64881`.

## 2. The reordering

The critical path **J6 → J5b → J8 → J10** is dead. J6 exhausted the hosted quota, and W-24 showed
the labels it produces are noise, so `sft_c` cannot be trained on them and **J5b stays paused**.

The replacement: the thesis (adaptive allocation of expensive expert calls beats fixed schedules
at matched cost) never required counterfactual branching. `oracle_escalation` bounds the headroom,
`router_seq` and the P(ASK) self-gate test whether it is capturable, `fixed_k` is the baseline —
and **none of those need ASK labels**. Only H4 (ASK trained *into* the policy) needs `sft_c`.

Update `docs/PLAN.md §8` and `docs/HEAVY_JOBS.md` accordingly, and restructure
`docs/prereg_v1.md` so **H2b and H3 are reachable without `sft_c`** and **H4 is explicitly
conditional** on the clean-counterfactual pilot. J6 recovery is **demoted**, to be revisited only
if that pilot fails.

🔺 Record one scope change: **the value-function escalator is dropped from the J8 live arms.** A7
showed it carries no information beyond a step counter, so spending post-reset quota on it would
buy a known-uninformative signal. It stays in the record as a completed negative result.

## 3. The correction that matters most — write it against our own earlier claim

The working record has carried the argument that J7's pre-registered AUROC threshold was
**unmeetable by construction**, on the grounds that with label reliability ~0.45 a perfect
predictor correlates with the observed labels at only √0.45 ≈ 0.67.

**That argument is wrong and must be retracted in the document, not quietly dropped.** The
reliability figure holds (0.4504 for the 4-replicate mean). The error is the *scale*: √ρ bounds a
**Pearson correlation**, and AUROC is a rank statistic that does not inherit that bound. Under the
same model a perfect predictor scores **AUROC 0.962** against these band labels, and a split-half
empirical proxy on J7's own subset gives **mean 0.9285** (splits 0.839, 0.969, 0.978) — the worst
split still clears 0.70. So the threshold was reachable and **0.59 is a genuine miss.**

Keep both caveats visible: the fit is thin (dev **n = 86**, 95% CI **[0.4677, 0.7111]**, which
includes 0.50, 0.65 *and* 0.70, so the result is statistically unresolved), and the fitted head
does **not** beat its own best single feature (`transcript_chars` 0.610, `step` 0.600, vs the
head's 0.5917).

🔺 **Do not lower the pre-registered threshold.** Record the miss as a miss. Adopt A9's proposal:
keep the original absolute threshold, add mandatory floor/ceiling/interval reporting, and
**disclose in the document that the reporting rule was written with knowledge of 0.5917.** A
reviewer who finds an undisclosed post-hoc loosening will discard the campaign.

⚠ **Also resolve a live discrepancy**: `docs/prereg_v1.md` specifies **0.70** while the working
briefs have carried **0.65**. Establish which is the registered value from the document's own
history and make the record consistent. If you cannot establish it from the tree, **say so
explicitly** rather than picking one.

## 4. Note the emerging pattern, once, where it belongs

Two independent estimators now fail the same way: the value function lands below a step prior, and
the J7 verifier fails to beat univariate `transcript_chars`. On both, **the feature representation
is what binds, not the head or the labels.** That is a more defensible and more mechanistic
negative result than "the labels are noise", and it points at the next experiment. State it once,
in the analysis narrative — do not scatter it.

## 5. Stale references to fix

- `campaign/RUNS.md:1355-1357` cites `loop.py:589-593` for the ASK gate — now **`:783-788`**.
- `src/sidekick/agents/verifier.py:57-62` cites `loop.py:492-500` for `trajectory_state` — now
  **`:515-524`**. This is the one code file you may touch, comment only.
- `docs/FOLLOWUPS.md:362` says `verify_configs.py` exits non-zero. **It exits 0** on the current
  tree with the script unmodified [OBSERVED, confirmed by me and by A5b]. Mark it resolved.
- `docs/FOLLOWUPS.md:275` (the `hash_match` entry) is now **resolved** by A10 — close it with the
  diagnosis, and make sure the "do not quote a `hash_match` number" warning is updated to say that
  version-3 values specifically are meaningless.

🔺 **Verify every cross-reference you write by opening the target and checking the line.** A
previous docs unit reported "all cross-references resolve" without checking, and a quoted phrase
turned out to match nothing in the file it cited. **Missing citations were the tell.** Every
claim you write gets a `path:line` you have actually opened.

## Constraints — you are NOT covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No interpreter, package installer, `tar`,
  `rsync` or `ffmpeg` there. This unit should need no computation at all.
- 🔺 **Zero planner calls. Do not invoke `codex`. Do not submit any job** — a training job and a
  harness smoke are both on the GPU queue.
- 🔺 **Do not modify anything under `/scratch/.../results/`.**
- **Do not commit.** Suite baseline **402 passed, 1 skipped**; a comment-only code edit must not
  change it.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- Every file changed, with a one-line summary each.
- The retraction in §3, quoted as written into the document.
- What you established about 0.65 vs 0.70, and on what evidence.
- The list of cross-references you checked, each with the `path:line` you opened. If any does not
  resolve, say so — **do not report a clean sweep you did not perform.**
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
