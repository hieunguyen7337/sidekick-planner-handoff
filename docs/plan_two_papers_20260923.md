# Plan: the next job set — Paper A to submission, Paper B to top-venue strength

Written 2026-09-23 07:30. Supersedes the 00:45 plan of the same day, whose job set has landed (its §9 outcome
record is condensed in §0 below; step E0 commits the full superseded text to `docs/`). Worktree
`plan-2026-09-15`, HEAD `b48e58b`, tree clean, suite 700 passed / 1 skipped, ledger 116 rows, preprint
~12,200 words, number audit exit 0. **No PBS jobs running. Nothing touches a test file.**

## Context

The user asked for the situation so far, a review of the publishable result first, the next job set, and the
additional jobs that make a top-venue result — and noted that **luna 6 is out with similar capability; keep
using `gpt-5.6-luna`**. Routing rule still in force: luna's plan quota is for research (hosted planner
calls); large worker units go to Claude or an Opus subagent.

---

## 0. Situation

**Established on dev** (57 tasks; goal_pass primary; scenario- and task-clustered paired bootstrap; NI 7.00 pp):

| claim | evidence | n |
|---|---|---|
| Actions beat prose advice at matched trigger + full context, and cost less | CHAN-C1-02 +6.69 pp [+1.29, +13.48]; COST-01 | 114 |
| Advice does not catch up at 3.2× the tokens | CHAN-PRICE-01 −14.68 pp [−22.09, −7.04] | 114 |
| Live takeover ≈ oracle replay | CHAN-C1-03 | 114 |
| Depth is a **span**, not a threshold | m6→m11 +7.70 / +8.39 pp, lower bounds 3–4 pp clear (POOL-01); every adjacent step Holm-null (MULT-01) | 171 |
| NI to the planner acting alone holds on goal_pass (all four) | POOL-02; untailored-m11 TGC undetermined at a discrete atom | 171 |
| Narration ≈ execution on the tailored receiver; receiver × narration interaction resolves at m11 | NARR-03..05, DID-01 | 114 |
| Mechanism: front-loaded API discovery; error suppression | MECH-01/05/07 | 114 |
| Tailoring × depth: unresolved at 171 | DID-02, POOL-03 | 171 |
| Second executor family: zero-shot curve real, both floors unusable (termination failure, measured cause) | QWEN-01..07 | 114 |

**Not established / open**: the tailored m9→m11 step (flips on 1 of 7 bootstrap seeds, POOL-04); two thin
bounds unprobed (H2 P3 +0.01 pp; TGC NI −6.14 vs −7.00); **C1's prompt asymmetry (§1.1)**; everything is
dev-only, one hosted planner, one environment.

**Built but not run**: LP-1 (local Qwen3-8B planner, zero hosted); the nine J10 configs.
**Not built**: the J10 run wrapper (`runner.py` has no `--purge-broken`), `j10_report.py` alignment to A1 §5
(the file mentions neither the 20260924 bootstrap seed, Holm, nor P1–P5), the U10 dev dry run.

---

## 1. Review of the publishable result (Paper A)

A hostile Reviewer-2 pass (Opus subagent, read-only) scored it **6/10 as arXiv + workshop/Findings today, 3/10
as top-venue main track today**. I verified its load-bearing claims against the files before adopting them;
the ones below are confirmed, and I agree with the verdict.

### 1.1 The one objection that could move the headline — C1 compares two prompts, not only two channels

The matched-trigger configs differ in one field, but the arms use different prompt builders. Advice:
*"The executor needs a correction. Reply with concise correction text only."* (`planner.py:108`) — it presumes
an error and caps length. Action: *"You are solving the task yourself…"* (`planner.py:117`). A reviewer will
say the advice channel was handicapped by its prompt, and that "code vs prose" (not execution) is the real
variable — the narrated control already shows code-as-text ≈ execution on the tailored receiver at m ≥ 9.
This is closable, cheaply, and it is the experiment that most raises novelty if the headline survives it:
**the C1 decomposition (Wave B2)** — a neutral-advice arm, and a *show-don't-execute* arm that calls the
planner with the byte-identical act prompt and hands its action to the executor as advice text. Same prompt,
same output; only execution differs.

### 1.2 Confirmed defects to fix in writing (no jobs)

| where | defect |
|---|---|
| P:306 vs P:331 | "execution beats narration significantly at both [m6, m11], on both clusterings" — m6 goal_pass is −6.96 [−13.67, +0.63], includes zero (only TGC resolves at m6) |
| P:502 | "+2.90 pp ([−7.03, +1.61])" — interval excludes its own point; negation error, should be [−1.61, +7.03] (verify against the QWEN-05 key) |
| P:306 vs P:342 | the same +0.10 pp carries [−4.75, +5.14] and [−5.14, +4.75] |
| §10 | **Ganz et al. is cited 0 times in the body** (only in `bibliography.bib`); Reach-or-Solve and SwiftSage likewise. No handoff / routing / cascade / critique literature. Related work needs ~+400 words. |
| whole paper | the **J9 primary (selective escalation) null is not reported**, though A1 §2 says it will be |
| NI claims | **CEIL-01** (NI fails, −5.92 [−9.80, −2.57], when the reference is restricted to non-cap-hit episodes) appears 0 times; report it with its caveat — restricting on the reference arm's own outcome favours the reference |
| P:486 | silenced-episode counts (31/32/56) disagree with the ledger (32/60); report handoff-only shares for both receivers, not only the zero-shot 83.8 % |
| P:42 vs P:6/350 | two different descriptions of the tailored adapter's training data |
| P:123, 281, 578, 589 | wrong section refs ("Section 4", "§3.3"), broken `ightarrow` |
| §5 framing | "continuous, not threshold" reads as a positive; say the data **cannot localize a breakpoint** |
| P:19, 613 | "grounded in a pre-registered ledger" overstates: SHAPE-10, CHAN-C1-03, NARR-03/04, DID-01 are exploratory — label them |

### 1.3 Form: it is a lab notebook, not a paper

Main text ~10,950 words against ~7,300 for 8 pages. Cuts (reviewer's table, I agree): abstract → 200; §5.5 →
150 words (stability protocol to A.4); §5.4 folded into §5.3; §6.2, §9.2, P4 deliberation to appendix; §7 to
one paragraph; §11 compressed. Retire every confession-framed title ("The Honest Negative", "A Correction",
"A Pattern That Does Not Replicate", "Crucial Methodological Limitation") — integrate the corrections into the
argument; move the defect record (test-suite collection defect, worker-invented TGC) to the appendix; drop ⚠
glyphs and "has since completed" narration. **Title decided after B2** (if show ≈ takeover, the paper is
about code vs prose, not execution).

### 1.4 Free analyses the review asks for (CPU jobs, no hosted calls)

F-a cluster sign-flip permutation p-values + wild-cluster bootstrap for every headline (19 scenario clusters
is few for percentile intervals) · F-b C1 and H2 on TGC with intervals · F-c handoff-only depth curves, both
receivers · F-d hinge-vs-linear fit under the cluster bootstrap · F-e both ceilings (cap-25, cap-81) in every NI
table · F-f intervals on cost differences + GPU-seconds from logs · F-g the near-matched advice pair already on
disk (`advise_k3` 204k tokens vs `prefix_m6` 221k) to answer "H2 is a strawman".

---

## 2. What luna 6 changes: nothing in the science, three things in the protocol

Verified this morning: all **86** codex-planner configs pin `model: gpt-5.6-luna`, the planner passes it as
`-m` (`src/sidekick/agents/planner.py:177`), and the code fallback is also luna 5.6 (`planner.py:23`). So no
arm can drift to luna 6 — which matters, because `~/.codex/config.toml` defaults to **`gpt-5.6-sol`**, and a
config that omitted the model would not even get luna. Three protocol changes follow anyway:

1. **Deprecation risk becomes a scheduling rule.** A newer luna makes retirement of `gpt-5.6-luna` more likely
   inside the J10 window. Replay arms are immune (they replay recorded packets); **live hosted arms are not.**
   So J10 runs its hosted arms (3, 8, 9, 10, and 11–12 if registered — §3) **first**, in consecutive windows,
   and every GPU replay arm after. A1 registers: *"all hosted arms run on `gpt-5.6-luna` only; if it is
   withdrawn before arms 3, 8, 9, 10 complete, J10 is reported as not run; no substitution by a later model."*
2. **Record what was served, not only what was asked.** `resolved_model` is currently an echo of the config
   (`planner.py:482`), and the codex-cli version (now **0.153.4**) is logged only in some PBS stdout. Extend
   X16 provenance with `planner_cli_version`, and run a **one-call probe** that dumps the full `codex exec
   --json` event stream to see whether any event reports the served model; if one does, stamp it per call.
3. **Freeze the CLI for the read.** No `codex` upgrade between the J10 dry run and the last hosted arm; the
   version is written into A1 at freeze time.

---

## 3. A1 must be revised before it is frozen (it is still DRAFT — revise in place, then freeze)

| # | problem found this morning | fix | hosted cost |
|---|---|---|---|
| R1 | **The paper's headline is not on test.** P1 tests the at-price contrast (`advise_k1_fullctx − prefix_m11`). No arm tests the matched-trigger live pair CHAN-C1-02 (`takeover_k10` vs `advise_k10_fullctx`); arm 9 exists but is "droppable". | Add **arm 10 `takeover_k10`** (2.32 calls/ep on dev) and make arm 9 non-droppable; register the pair as **P6, primary** (Holm family grows to six). | +778 calls |
| R2 | P4's note says "no difference-in-differences was ever run" (A1 lines 247–251). DID-01/02 now exist, and all four arms of the tailoring × depth DiD are already in A1. | Register `(m11−m9)_tailored − (m11−m9)_untailored` as a **supporting, non-decision-bearing** contrast with its dev value (DID-02 / POOL-03), so it is pre-specified, not exploratory. Update the dev reference values to the 171-pair figures where they exist. | 0 |
| R3 | The seven-seed stability rule (POOL-04) is not registered. Applying it after the read would look like a rescue. | Register: any test bound within 1 pp of its threshold is re-run at seeds {20260924,1,2,3,7,101,999}; if the verdict flips on any seed it is reported **"on the boundary"**, never as supported. | 0 |
| R4 | Arm 1 `executor_alone` uses the BASE receiver (`lora_name: null`), conflating "no plan" with "no tailoring". | Add a tailored floor (`sft_b_plus`, no plan) as arm 1b, or relabel arm 1 as the zero-shot floor. | 0 |
| R5 | Luna 6 (§2). | Register model id, CLI version, and the no-substitution rule. | 0 |
| R6 | The C1 prompt confound (§1.1). | After B2 lands on dev, register its decisive arm(s) on test as arm 11 `show_k10` (and arm 12 `advise_k10_neutral` if B2 shows the prompt matters), with P7 = the decomposition, decision rules written from the dev values. | ≤ +1,600 |
| R7 | 19 scenario clusters is few for percentile intervals (§1.4 F-a). | Register the cluster sign-flip permutation p-value as a **sensitivity** reported beside every P-verdict (the bootstrap stays decision-bearing). | 0 |

New registered budget: 12,557 (arms 1–8) + 827 (arm 9) + 778 (arm 10) + ≤ 1,600 (R6) = **≤ ~15,800 hosted
calls**, ≈ 3–4 windows at the measured ~5,000/window. **Sequencing consequence:** A1 is frozen *after* B2, not
now — about one extra window of latency, in exchange for a registered read that can confirm the headline
*and* its decomposition. (Alternative if speed matters more: freeze now with R1–R5, R7 only; B2 stays dev-only.)

---

## 4. The job set

Hosted-call budget across everything below: **~17k** (J10 ≤ 15.8k incl. R6 + Wave B ~1.2k). Every
luna call here is research; worker units go to Claude / Opus subagents. Every
other job is free GPU/CPU. Luna workers never run inside a hosted window.

### Wave A — free, start now (no hosted calls except one probe; no test contact)

| # | unit | detail | who | cost |
|---|---|---|---|---|
| A1 | **Submit LP-1** | `qsub scripts/pbs/lp1_planner_alone.pbs` (Qwen3-8B planner_alone cap-81, dev, seeds 1,2; smoke gate built in). Verify 114 non-crashed by `error_type`, never the exit code. | Claude submits | ~4 H100-h |
| A2 | **Get a real mid-size planner** | CPU job with egress: download `Qwen/Qwen3.8-27B-FP8` (~30 GB) into the home HF cache; verify blob sizes (not `du` of the dir — the stubs fooled that once); GPU smoke-serve under vLLM 0.29.0 (`qwen3_5.py` is present). Fallback `Qwen/Qwen3-32B` bf16 (~65 GB, TP=2). | Claude submits | ~1 CPU-h + 0.5 GPU-h |
| A3 | **Local-planner live arms** | New `scripts/pbs/lp_live.pbs`: planner on 8001 + granite executor on 8000 (2 GPUs for the 27B), running `sft_plan`, `takeover_k10`, `advise_k10_fullctx`, `advise_k1_fullctx` with `planner.type: vllm`. Configs `lp{1,2}_*` derived from `hj12_*` by changing only the planner block; prefix-replay configs `lp{1,2}_prefix_{zs,bplus}_m{6,9,11}` with `source_campaign` = the LP ceiling. Reuse `hj12_prefix.pbs` for replays. | Claude / Opus subagent (code); Claude reviews + submits | 0 |
| A4 | **J10 machinery** (U9/U10, never built) | (i) purge-broken + resubmit wrapper `scripts/pbs/j10_arm.pbs` (skip-if-exists, crash detector = `error_type == "crash"` only, per-window quota probe); (ii) align `scripts/analysis/j10_report.py` to revised A1 §5: bootstrap seed 20260924, Holm across P1–P6, scenario primary, POOL-04 seven-seed probe built in; tests on `campaign/results/j10_a1_registered_dev_basis_20260924.report.json`; (iii) dev dry run of the exact J10 configs with `--split dev --tasks 3` (≈100 hosted calls, run inside Wave B's window). | Opus subagent (code + tests); Claude reviews | ≈100 calls |
| A5 | **Protocol hardening** | `planner_cli_version` into X16 provenance; one-call served-model probe (dump every `codex exec --json` event type); `make_env` / task loader raise on an unknown `env:` instead of falling back to `MockEnv` (`runner.py:242-250, 400-405`). | Claude | 1 call |
| A6 | **Thin-bound probes under POOL-04** (task #43 + one new) | Add `--seed` to `j8_frontier.py` bootstrap (or a thin wrapper); seven seeds for H2 P3's **+0.01 pp** bound and for the **TGC NI lower bound −6.14** at P:167 (0.86 pp from the −7.00 margin — found in this review). Record ranges. | Claude | ~1 CPU-h |
| A7 | **Free analyses F-a … F-g** (§1.4) | one script `scripts/analysis/j16_robustness.py` + tests on fixtures; reports to `campaign/results/j16_*`; ledger rows ROB-*. Permutation code reused by `j10_report.py` (R7). | Opus subagent (code); Claude verifies numbers | ~2 CPU-h |
| A8 | **B2 code + dev prereg** | (i) loop change: config key `advice_from_act: true` routes the planner's `act` output (byte-identical `build_act_prompt`) to the executor as advice text, never executed; `correct_prompt: neutral` selects a neutral advice builder (no presumed error, no length cap). Tests assert prompt identity with the takeover arm. (ii) `docs/prereg_c1_decomposition_<date>.md` — predictions and decision rules written **before** B2 runs (below). | Claude (code, ~120 LOC + tests); Claude drafts prereg, **user freezes** | 0 |
| A9 | **Paper A writing** (§1.2, §1.3) — everything not dependent on B2: consistency fixes, related work (+Ganz, Reach-or-Solve, SwiftSage, routing/cascade/critique), J9 null, CEIL-01, restructure to ~7,300 words, LaTeX build | Opus subagent per section with ledger rows pasted in; Claude integrates; `preprint_number_audit.sh` exit 0 after each pass | 0 |

### Wave B — dev, hosted, one window (~1.2k calls): test the headline before registering it

Runs after A8's prereg is frozen, in one window with the A4 dry run (~100) and the A5 probe (1).

| # | unit | detail | calls |
|---|---|---|---|
| B2 | **C1 decomposition** (§1.1) — the most important new experiment | `show_k10` (act prompt, output shown as advice, not executed) and `advise_k10_neutral`, each 57 tasks × seeds 1–3 = 171 pairs, same `packet_source` plans as the C1 pair. Registered rules (A8): **execution matters** if `takeover − show` > 0 with CI excluding zero; **content, not execution** if that CI includes zero and `show − advise_k10_fullctx` > 0 → retitle "code, not prose"; **prompt artefact** if `advise_neutral` closes the gap to takeover (CI of `takeover − advise_neutral` includes zero) → C1 withdrawn as a channel claim and reported as such. | ~820 |
| B1 | Dev seed 3 of the matched-trigger pair | `takeover_k10` s3 + `advise_k10_fullctx` s3, derived from `hj12_*` with `packet_source` → `hj13_planner_alone_cap81_seed3_20260924` (the pair replays a planner_alone campaign's first plan packet, which is cap-independent — so seed-3 plans already exist, free). Lifts CHAN-C1-02 from 114 to **171 pairs**; its lower bound (+1.29) is close enough to the POOL-04 line that the power is worth buying. Disclose that seeds 1–2 draw plans from the cap-25 campaign and seed 3 from the cap-81 one. | ≤ 272 |
| — | declined: dev planner seeds 4–5 (~2,000 calls) to resolve the m9→m11 step | the step is not a claim, the span is; spend the quota on J10 | 0 |

### Wave C — the registered test read (only after the user freezes revised A1)

Order is set by the luna-6 deprecation risk (§2) and by dependencies: **hosted first, replays after.**

| step | arms | hosted calls | note |
|---|---|---|---|
| C1 | arm 3 `planner_alone` cap-81 | 5,830 | ≥ 1 window; prefix source for arms 4–7 **and** plan-packet source for arms 9–10 |
| C2 | arm 8 `advise_k1_fullctx` | 6,391 | ≥ 1 window |
| C3 | arm 10 `takeover_k10` + arm 9 `advise_k10_fullctx` | ≤ 1,605 | the P6 pair; replays arm 3's plan packets, so the marginal cost is likely lower |
| C4 | arms 11 (`show_k10`) ± 12 (`advise_k10_neutral`) per R6 | ≤ 1,600 | the P7 decomposition on test |
| C4b | arm 2 `sft_plan` | 336 | cheap; last of the hosted arms |
| C5 | arms 1, 1b, 4–7 (GPU replays) | 0 | 2 GPU jobs; immune to model retirement |
| C6 | `j10_report.py` → P1–P6 verdicts, reported regardless; ledger J10-*; one-read rule | 0 | — |

Rules: an arm is complete only at 336 non-crashed pairs; a campaign that cannot complete arms 3, 8, 9, 10 is
reported as not run, never at reduced power; record each window's reset time so the weekly cap becomes a
measured number. Calendar: ≥ 3 windows, 1–2 weeks.

### Wave D — a second planner family, zero hosted (top-venue; overlaps Wave C because it spends no luna)

| # | unit | detail |
|---|---|---|
| D1 | LP-1 chain (Qwen3-8B) | ceiling (A1) → free replays, both receivers, m6/9/11 → live channel pair + advice-at-price (A3) |
| D2 | LP-2 chain (Qwen3.8-27B-FP8) | same chain once A2 lands |
| D3 | Analysis | the same report scripts; ledger LP-01..; **new result: the channel advantage as a function of planner strength** across three planners (Qwen-8B, Qwen-27B, luna). If the action channel's margin holds or grows as the planner weakens, the claim is about the channel, not about luna; if it vanishes, that bounds it — either way publishable. |

GPU budget ≈ 40–50 H100-h, queue-bound, free. Decision rule unchanged: if the channel contrast and the NI
verdicts reproduce, Limitation 2 closes; if not, that is the generality result.

### Wave E — second environment (decision gate: after J10's P1 lands)

- **E0, now, cheap:** a read-only scoping unit (Opus subagent, web allowed) to pick the environment. Criterion
  from this morning's coupling scan: prefix replay needs a deterministic `reset` + replay that reproduces
  `snapshot_hash`; τ²-bench's LLM user simulator breaks that unless its turns are cached, so prefer an
  environment with **scripted user turns and Python-backed state** (e.g. a BFCL-style multi-turn suite) or
  price the caching. The adapter is ~650–1,050 LOC (`BaseEnv` at `src/sidekick/environments/base.py:9`,
  plus scoring, task loader, executor prompt variant, tests); loop, channel arms and handoff code carry over.
- **E1, after the gate:** build + zero-shot receiver only; ~5k hosted calls; 1–2 weeks.

---

## 5. Paper B (top venue) — what the job set above buys it

1 Intro · 2 Setup + registration lineage (J9 → A1, dev preregs) · **3 Channel**: dev C1 + decomposition (B2) +
H2, then the registered test read P1/P6/P7 · **4 Depth and NI**: dev 171-pair span, test P3/P4 · **5 What the
prefix conveys + mechanism** · **6 Generality**: the planner-strength axis (Qwen3-8B, Qwen3.8-27B, luna — D3),
the second executor family, ± second environment (Wave E) · 7 Related · 8 Limitations · 9 Conclusion.
Target ICML 2027 / ACL 2027 main track (verify deadlines before planning around them). Paper A goes to arXiv
first, so the finding is timestamped against Ganz et al. (2026-08-25).

The novelty claim a top venue will accept, if it holds: *for a fixed hosted budget, having the planner act
beats having it advise — confirmed on held-out tasks, decomposed into content vs execution, and stable
across planner strength.* Each clause is one wave: C (held-out), B2 (decomposition), D (planner strength).

---

## 6. Calendar and odds (judgement, not measurement)

| days | what |
|---|---|
| 0–2 | Wave A (free) · A8 decomposition prereg drafted → frozen · LP-1 running · 27B download |
| 2–3 | Wave B window (~1.2k calls): B1, B2, J10 dry run, served-model probe |
| 3–5 | B2 analysed · Paper A finalised → arXiv · A1 revised (R1–R7) → **user freezes** |
| 5–16 | J10, 3–4 windows (hosted first, then replays) · Wave D on GPU in parallel |
| ~16 | J10 report (P1–P7) · Wave E gate · Paper B drafting |

Paper A at a workshop/Findings venue after §1 fixes: ~85–90 % if C1 survives B2; ~70 % if B2 reframes it
(a careful decomposition is still a paper). Paper B top-venue: ~55–65 % with J10 + B2 + D; ~70 % adding a
second environment; ~35 % if J10's P1/P6 fail to replicate (then it is an honest non-replication paper).

---

## 7. Verification (unchanged rules, plus two new)

- Every arm: count + `error_type` by `jq`, never the exit code; crash = `error_type == "crash"` only.
- Every new script tested on a fixture with a known answer; full suite in PBS ≥ 700 passed after each commit.
- Every number: ledger row → report key; `preprint_number_audit.sh` exit 0 after every paper edit.
- **POOL-04** on every bound within 1 pp of its threshold, before its verdict is written.
- **New:** B2's loop change ships with a test asserting the `show_k10` planner prompt is byte-identical to
  `takeover_k10`'s, and that nothing from a `show` action reaches the environment.
- **New:** every hosted job logs `codex --version` and the requested model; J10 refuses to start if the CLI
  version differs from the one A1 registers.
- Frozen texts amended by appending; new arm → new campaign id; nothing written under `/scratch/.../results/`;
  no `test_normal` / `test_challenge` contact until the user freezes revised A1; `test_challenge` never.

---

## 8. Decisions needed from the user (recommended default in bold)

1. **A1 sequencing**: revise with R1–R7 and freeze **after B2** (**recommended** — one extra window buys a test
   read that confirms the headline and its decomposition), or freeze now with R1–R5 + R7 and keep B2 dev-only.
2. **The B2 decomposition prereg (dev-only)**: may I freeze it on commit myself, since it touches no test data
   (**yes**), or do you want to review it first?
3. **Paper A timing**: arXiv **after B2 + the §1 rewrite (~4–5 days)** (**recommended** — the prompt asymmetry is
   visible to anyone who reads the released code), or now as-is.
4. **Second environment**: approve the free E0 scoping now, and **defer the build decision to after J10's P1**.

---

## 9. Execution order once approved

E0 commit the superseded 00:45 plan text to `docs/plan_two_papers_20260923.md` → A1 submit LP-1 + A2 download
(both free, immediately) → A5, A6 (small, Claude) → A8 code + prereg → A4 J10 machinery → A7 analyses → A3
LP live arms → Wave B window → B2 analysis → A9 Paper A → revised A1 for the user → Wave C → Wave D alongside.

---

## Appendix — condensed outcome record of the superseded 00:45 plan

Commits `8fcc848` (U4 pooled 171 pairs; the tailored m9→m11 step read +4.25 [+0.15, +8.75] and flips on 1 of
7 bootstrap seeds → POOL-04 rule), `ae4696f` (campaign provenance index: 49/49 dependencies present; 10
campaigns incl. all 8 published dev prefix arms ran under a CLI-overridden campaign id), `9b545d6` (X16
provenance incl. split), `b48e58b` (VllmPlanner + LP-1; Qwen3-32B/3.6-27B are pointer stubs, only Qwen3-8B
is real). Open from it: A1 freeze; LP-1 submission; P3 +0.01 pp probe; `verify_configs.py` red on the four
`j10_prefix_*` configs until arm 3 exists (expected).
