# E0 — Scoping a second agentic environment (2026-09-23)

Read-only scoping unit for Wave E of `docs/plan_two_papers_20260923.md:196-204`. Nothing was
installed, downloaded, run or submitted; no hosted model was called. Sources are benchmark papers,
READMEs, dataset cards and raw source files read through web fetch, plus the local worktree.

**Tag convention.** Every claim carries `[OBSERVED <key>]` or `[INFERRED]`. Keys resolve to a URL or a
`path:line` in §4. Web pages were read through a summarising fetcher, so a number marked OBSERVED was
seen in the fetched text but not re-derived by hand unless stated; §5 lists what could not be verified.

---

## 0. What the second environment has to carry

The replication targets the three AppWorld findings (channel: ACT beats ADVISE at a matched trigger;
depth: prefix handoff improves with m; non-inferiority of handoff arms to `planner_alone`). The local
code fixes what "an adapter" means:

- `BaseEnv` requires `reset(task_id, seed) -> Observation`, `step(ExecutorAction) -> Observation`,
  `evaluate() -> dict`, `snapshot_hash() -> str`, `close()`, `instruction`, `api_docs_digest`, and an
  optional `api_docs_prompt` [OBSERVED L1].
- The AppWorld adapter is 254 lines; `snapshot_hash()` hashes the execute I/O log, not the app
  databases, so "a hidden DB mutation that does not appear in execute() output will not change the
  hash" [OBSERVED L2]. `prefix_source.py` repeats that the hash check "detects **visible** divergence
  only" and marks a mismatch `replay_divergence` [OBSERVED L3]. **A second environment whose state can
  be hashed directly would give a strictly stronger replay check than the one the AppWorld results
  rest on** [INFERRED].
- `make_env` raises on an unknown kind rather than falling through to the mock [OBSERVED L4], so a new
  kind needs a branch there plus a task-id loader analogous to `appworld_task_ids` [OBSERVED L4].
- ⚠ **The loop assumes a single-instruction episode.** It breaks on `action.kind == "COMPLETE"`
  regardless of the environment's `done` [OBSERVED L5b], and `prefix_is_terminal` treats a trailing
  COMPLETE as terminal [OBSERVED L5a]. Any environment with scripted multi-turn user messages needs
  "end of this turn" to be distinguishable from "end of episode". Both existing envs set `done=True` on
  COMPLETE [OBSERVED L6], so changing the break to `last_obs.done` is behaviour-preserving for them
  [INFERRED] — but it is a change to frozen loop code and needs a regression test.
- Step cap is 40 by default [OBSERVED L7]. AppWorld dev is 57 tasks in 19 scenario clusters, run at
  n = 114 pairs [OBSERVED L8c].
- Cost calibration from AppWorld, hosted calls per episode: `ceiling_cap25` 14.43 ($0.035479),
  `ceiling_cap81` 17.35, `takeover_k10` 2.32 ($0.004820), `advise_k10_fullctx` 2.46 ($0.005494)
  [OBSERVED L8b]; prefix arms make **zero live planner calls** (pure replay) [OBSERVED L8a].
- Site constraint: Apptainer only, **no Docker daemon, no `--fakeroot`** [OBSERVED M1]. Any benchmark
  that drives containers through the Docker API is a porting project here, not an adapter.

---

## 1. Ranked table

Score = fit to the replay mechanism first (deterministic reset + deterministic action execution +
feasible state hash + no simulated user), then split/headroom fit, then weight.

| # | Candidate | Action space | State held in | Reset / replay determinism; snapshot hash | User simulation | Tasks and splits | Scoring signal | License | Setup weight | Typical episode | Adapter LOC vs `BaseEnv` (adapter + scoring + loader + prompt + tests) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **BFCL v3/v4 multi-turn (`multi_turn_base`)** | Python call expressions `f(x=..)` executed by `eval` over class instances, light blacklist [OBSERVED W6] | Plain Python class instances (dicts, lists, ints; one `set`) loaded from a per-entry `initial_config` by `_load_scenario` [OBSERVED W4, W5, W6] | **Deterministic**: RNG seeded from the scenario (`random.Random(scenario.get("random_seed", ...))`), fixed `CURRENT_TIME = datetime(2024, 9, 1, 10, 30)` [OBSERVED W4, W5]. **Hash feasible and strong**: sha256 of public attributes, the same ones BFCL's own `state_checker` compares (it skips `_`-prefixed attrs) [OBSERVED W7]; add `_random.getstate()` for strict replay [INFERRED]. ⚠ BFCL's executor caches instances in `globals()` keyed `{model_name}_{test_entry_id}_{class}` and only builds one `if instance_name not in globals()` [OBSERVED W6] — re-running an entry in one process would start from a mutated instance; the adapter must own its instances [INFERRED] | **None — user turns are scripted in the dataset** [OBSERVED W1] | 200 per category; leaderboard scores Base / Miss Func / Miss Param / Long Context [OBSERVED W1, W9]. No official dev/test split → **dev 50 / test 150** from Base [INFERRED] | Per turn: state check + response check (GT results a subsequence); entry passes only if both pass in **all** turns; >20 steps in a turn = force-terminated and wrong [OBSERVED W1, W7]. Per-turn pass fraction as partial credit [INFERRED] | Apache-2.0 [OBSERVED W2] | Light: pure Python; `bfcl-eval` on PyPI, Python 3.10 [OBSERVED W2]; GPU only for our own executor; no docker | 15-entry sample: mean **3.5 user turns, 7.8 GT calls** (range 2–5 turns, 3–12 calls) [OBSERVED W8, sample only]; ≈ 10–16 agent steps incl. turn-ending replies [INFERRED] | **~800–950** [INFERRED]: adapter 280–350, scoring wrapper 100–150, loader/splits 60, API-doc prompt 60, executor prompt 80, loop turn seam 30, tests 200–250 |
| **2** | **τ²-bench, telecom domain in solo (no-user) mode** | JSON tool calls; in solo mode the agent also holds the user's device tools [OBSERVED T2, T3] | Python domain DBs (`db.toml`, `user_db.toml`) behind tool functions [OBSERVED T6] | **Deterministic tools**; built-in `get_db_hash()` / `get_user_db_hash()` and `set_state(...)` that replays a message history, re-executing mutating calls and checking outputs (`strict`) [OBSERVED T5]. Hash already provided | **None in solo mode** ("the agent works independently on the ticket", initial observation empty) [OBSERVED T3]; solo agent requires a task `ticket` [OBSERVED T4] | Telecom 114 evaluated tasks drawn from a 2,285-task pool [OBSERVED T2]; `split_tasks.json` has `small`/`train`/`test`/`full` [OBSERVED T7] (counts unverified, §5) | Assertion functions on final state only ("In telecom, only assertion functions are used") [OBSERVED T2]; binary | MIT [OBSERVED T1] | Light: `uv`, core text domains minimal [OBSERVED T1] | Expected actions mean 2.31 / 4.31 / 6.00 by issue type, max 12 [OBSERVED T2]; agent steps higher once reads are counted [INFERRED] | **~800–950** [INFERRED]: adapter 300, reuse tau2 evaluator 80, loader 60, policy/manual prompt 120, tests 250 |
| 3 | WorkBench | ReAct text or native tool calls, 26 read/write tools [OBSERVED WB1, WB2] | Five sandbox DBs as CSV/pandas (calendar 300 events, email 500, analytics 500, CRM 200, PM 300) [OBSERVED WB1] | Deterministic; fixed "today" 2023-11-30 [OBSERVED WB1]. Hash = sha256 of the five frames [INFERRED] | None (single instruction) [OBSERVED WB2] | 690 tasks = 69 templates × 10; no official split [OBSERVED WB1, WB2]. Template-clustered dev 19×3 = 57 mirrors AppWorld's 19×3 [INFERRED] | Outcome-centric DB comparison plus harmful-side-effect rate [OBSERVED WB1, WB2]; binary | MIT [OBSERVED WB2] | Light, Python 3.12 + uv [OBSERVED WB2] | 0–12 actions, **18 % need none** [OBSERVED WB1] — too short for a three-point depth curve [INFERRED] | ~650–750 [INFERRED] |
| 4 | Gaia2 on Meta ARE | Tool calls over simulated apps [OBSERVED G1, G3] | Python apps in ARE [OBSERVED G3] | **Asynchronous**: timed events arrive during the run ("Gaia2 runs asynchronously") [OBSERVED G1, G3]; leaderboard asks for 3 runs/scenario for variance [OBSERVED G4]. Replay determinism unproven [INFERRED] | Agent2Agent scenarios use other LLM agents [OBSERVED G2] | 800 validation scenarios with oracle events, 200 "mini" [OBSERVED G2] (blog says 1,000 [OBSERVED G3]) | Mix of exact match and **LLM judge (Llama 3.3 70B)** [OBSERVED G3] | ARE MIT, Gaia2 CC-BY-4.0 [OBSERVED G3] | Medium: pip package [OBSERVED G3] + a 70B judge to serve | Long [INFERRED, unverified] | ~1,200–1,600 [INFERRED] |
| 5 | ToolSandbox | Tool calls, 34 tools [OBSERVED S1] | Execution-context DBs (settings, contacts, messages, reminders) [OBSERVED S2] | Only 44 % of tools stateful; the rest are **RapidAPI** endpoints needing a key [OBSERVED S1, S2] — live web, not replayable | **LLM user (GPT-4o)** [OBSERVED S1] | 1,032 scenarios [OBSERVED S1] | Milestone/minefield similarity (partial) [OBSERVED S1, S2] | not verified (§5) | Light Python, but API key | 13.9 turns, **3.80 tool calls** per scenario [OBSERVED S1] | ~1,100–1,400 incl. user caching + API stubs [INFERRED] |
| 6 | τ²/τ³-bench retail + airline (default, cached user) | JSON tool calls | Python DBs, same `get_db_hash`/`set_state` [OBSERVED T5] | Tools deterministic; **user is an LLM** (gpt-4.1 in the paper) [OBSERVED T2]; caching fixes only the replayed prefix, every post-handoff user turn is live [INFERRED] | LLM user; Redis caching exists "for cost optimization" [OBSERVED T8] | airline 50, retail 115 [OBSERVED T2]; train/test splits since v0.2.1 [OBSERVED T8] | Assertions + action/communicate checks, pass^k [OBSERVED T1, T2] | MIT [OBSERVED T1] | Light | Multi-turn dialogue [INFERRED] | ~1,000–1,200 incl. user-turn cache [INFERRED] |
| 7 | ALFWorld | Admissible **text commands** (not code) [OBSERVED AW1] | TextWorld games [OBSERVED AW1] | Deterministic engine [INFERRED] | None | 134 unseen-test games [INFERRED, unverified] | Binary success [INFERRED] | MIT (+ GPL-3 Fast Downward) [OBSERVED AW1] | Light (text-only install) [OBSERVED AW1] | up to ~50 steps [INFERRED] | ~500 [INFERRED]; channel contrast becomes "text command vs prose", a weaker analogue |
| 8 | WebShop | `search[..]` / `click[..]` text actions | Product index (1.18 M products) [OBSERVED WS1] | Deterministic given fixed index [INFERRED] | None | 12,087 instructions [OBSERVED WS1] | Attribute-match reward in [0,1] [INFERRED, unverified] | not verified | Heavy data + Java search backend [INFERRED] | ~5–15 steps [INFERRED] | ~600 + data infra [INFERRED] |
| 9 | ScienceWorld | Text templates | Scala simulator via py4j, **needs Java 1.8+** [OBSERVED SW2] | Seeded variations [INFERRED] | None | many variations per task [OBSERVED SW2] (counts disputed, §5) | 0–100 partial score [INFERRED, unverified] | Apache-2.0 [OBSERVED SW2] | Medium (JVM) | long (50–100+) [INFERRED] | ~600 [INFERRED] |
| 10 | InterCode (Bash/SQL) | Bash / SQL code [OBSERVED I1] | Docker containers [OBSERVED I1, I2] | Reproducible **via Docker** [OBSERVED I1]; needs a running daemon [OBSERVED I2] — absent here [OBSERVED M1] | None | from NL2Bash / Spider / MBPP [OBSERVED I1]; sizes unverified | success = score 1.0 [OBSERVED I2] | MIT [OBSERVED I2] | **Blocked**: Docker daemon | short [INFERRED] | ~700 + container port [INFERRED] |
| 11 | OfficeBench | App operations in a Linux container [OBSERVED O2] | Files in docker [OBSERVED O2] | Docker-bound [OBSERVED O2] | None | 300 (93 / 95 / 112 by #apps) [OBSERVED O2] | exact / fuzzy / execution checks [OBSERVED O2]; GPT-4o 47 % [OBSERVED O1] | Apache-2.0 [OBSERVED O2] | **Blocked**: Docker | long-horizon [OBSERVED O2] | ~900 + container port [INFERRED] |
| 12 | NESTFUL | One nested call sequence per query | Stateless executable functions [INFERRED] | Deterministic but **not interactive** — no steps to hand off [INFERRED] | None | 1,800+ sequences [OBSERVED N1] | full-sequence match, win-rate [OBSERVED N1] | not verified | Light | 1 generation | ~400, but the mechanism has nothing to act on [INFERRED] |
| 13 | TheAgentCompany | Browser + code + chat | Self-hosted company services [OBSERVED TAC1] | Service stack, no cheap reset [INFERRED] | LLM coworkers [OBSERVED TAC1] | 175 [INFERRED, unverified] | checkpoints; best agent 30 % [OBSERVED TAC1] | not verified | **Too heavy** | very long | >2,000 [INFERRED] |
| 14 | SWE-style repos | Shell/edit | Per-task containers | Docker [INFERRED] | None | e.g. 500 (Verified) [INFERRED, unverified] | unit tests | varies | **Too heavy** | 30–100+ steps [INFERRED] | >1,500 [INFERRED] |

Also looked at and set aside: **ToolTalk** — scripted-style dialogues with simulated executable tools,
28 tools / 7 plugins [OBSERVED TT1], but too few conversations for a 50/150 split [INFERRED, count not
verified]; **TravelPlanner** — deterministic read-only sandbox, 1,225 intents, GPT-4 success 0.6 %
[OBSERVED TP1]: floor effect, and the output is a plan, not a state [INFERRED].

---

## 2. Recommendation

### First choice: BFCL multi-turn, `multi_turn_base` category

Decisive reasons, in order of weight:

1. **It is the only candidate with all three of: Python-backed state, scripted multi-turn user
   messages, and execution-based state scoring.** No user simulator, so no caching problem
   [OBSERVED W1]; state is plain class instances [OBSERVED W4, W5]; the checker executes ground truth
   and compares instance state per turn [OBSERVED W7].
2. **The replay check gets stronger than AppWorld's.** Randomness is seeded from the scenario and time
   is a constant [OBSERVED W4, W5], so `reset(task, seed)` is exact; `snapshot_hash()` can hash the
   same public attributes that BFCL's scoring compares [OBSERVED W7], closing the "hidden DB mutation"
   gap the AppWorld adapter documents [OBSERVED L2, L3].
3. **Split and headroom fit.** 200 Base entries give dev 50 / test 150 [OBSERVED W1; split INFERRED].
   On the public leaderboard, frontier models score 64.5–81.0 % on Multi Turn Base, Qwen3-8B 41.5–50.5 %,
   and Granite-3.x-8B 9.5–11.5 % [OBSERVED W9]. A planner/executor gap of 20–40 pp is likely
   [INFERRED], comparable to AppWorld's 43.86 pp TGC gap between `executor_alone` and the ceiling
   [OBSERVED L8c].
4. **Action format matches the harness.** The executor already emits Python; a BFCL action is a list of
   Python call expressions [OBSERVED W6]. ACT = execute the planner's call list; ADVISE = show it as
   prose. Nothing in the channel/handoff code needs to know which env is underneath [INFERRED].
5. **Light and licensable.** Pure Python, Apache-2.0 [OBSERVED W2]; no Docker, which this cluster
   cannot run [OBSERVED M1]. The backend classes live in one directory [OBSERVED W3] and can be vendored
   at a pinned commit [INFERRED].

Use Base only. Miss Func needs functions revealed mid-episode, Miss Param tests abstention, and Long
Context is a bigger state for the same kind of task [OBSERVED W1]. They measure different skills, and
may share tasks with Base (not verified, §5), so they are a leakage risk if split separately [INFERRED].

### Fallback: τ²-bench telecom in solo (no-user) mode

Switch to it if the spike fails gate (b) or (c) below. Reasons: replay infrastructure is **built in**
(`get_db_hash`, `get_user_db_hash`, and `set_state` re-executing mutating calls with a `strict` output
check) [OBSERVED T5]; solo mode removes the user simulator entirely [OBSERVED T3]; tools are Python
over TOML DBs [OBSERVED T6]; MIT, light [OBSERVED T1]; a 2,285-task pool gives room for any split
[OBSERVED T2]. Costs of choosing it: one narrow domain; solo mode is not the headline τ² setting, so
there are fewer published comparators [INFERRED]; episodes are short (mean 2.3–6.0 expected actions
by issue type) [OBSERVED T2]; and the action is a JSON tool call, not code [OBSERVED T2]. Second
fallback: WorkBench, whose template structure mirrors AppWorld's scenario clusters but whose
0–12-action tasks (18 % zero) leave little depth to vary [OBSERVED WB1].

### The three biggest risks for BFCL, and a one-day spike for each

The spike uses no hosted calls. (a) and (c) are CPU jobs; (b) is one GPU job. Everything goes through
PBS, not the login node.

1. **Replay determinism has a trap in BFCL's own executor.** `execute_multi_turn_func_call` keeps
   instances in module `globals()` and builds one only if the key is absent [OBSERVED W6]. Replaying an
   entry in the same process under the same `model_name` would therefore start from the mutated
   instance: a silent replay error that could still produce believable numbers [INFERRED].
   **Spike (a):** the adapter builds fresh instances from `initial_config` on each `reset`. For all 200
   Base entries: (i) execute the ground truth turn by turn and require **200/200 pass** under BFCL's
   `multi_turn_checker` (any GT failure is a benchmark defect to exclude and record); (ii) run a no-op
   agent and require near-zero pass; (iii) replay every GT prefix m = 0..len twice, in the same process
   and in a fresh one, and require identical `snapshot_hash` at every m; (iv) reset the same entry
   twice in one process and require an identical initial hash. Gate: 100 % hash agreement.
2. **Headroom and contamination.** The data has been public since the v3 release [OBSERVED W1].
   Granite-4.2-8b reports BFCL v4 overall 52.39 [OBSERVED L9], so it was probably tuned toward BFCL
   [INFERRED], and the executor–planner gap may be narrower than on AppWorld [INFERRED].
   **Spike (b):** one PBS GPU job runs `executor_alone` (zero-shot granite, the E1 receiver) on the 50
   dev entries with the adapter from (a). Priors for the planner side come from the leaderboard: 64.5–81 %
   frontier Base [OBSERVED W9]. Gate: executor_alone Base ≤ 50 %, so the expected gap is ≥ 15–20 pp.
   Failing this gate is the trigger for the fallback.
3. **Protocol seam and a compressed depth range.** Multi-turn episodes need "end of turn ≠ end of
   episode", but the loop breaks on COMPLETE [OBSERVED L5b] and replay treats a trailing COMPLETE as
   terminal [OBSERVED L5a]. BFCL episodes are also short (sample mean 7.8 GT calls) [OBSERVED W8]. The
   AppWorld depths m = 6/9/11 would often hand off after the planner has already finished, and per-turn
   partial credit cascades after a failed turn because the checker compares against cumulative GT
   state [INFERRED from W7].
   **Spike (c):** (i) change the loop to break on `last_obs.done` and have the BFCL adapter return the
   next scripted user message with `done=False` on a non-final COMPLETE. Regression-test this by
   re-scoring recorded AppWorld and Mock episodes; both envs set `done=True` on COMPLETE [OBSERVED L6],
   so outcomes must be byte-identical. (ii) From the GT call-count distribution and from (b)'s executor
   step lengths, choose three depths, e.g. m ∈ {2, 4, 6} steps or turn-aligned {1, 2, 3} turns
   [INFERRED], such that the deepest m still hands off in ≥ 70 % of entries (`handoff_occurred`,
   [OBSERVED L3]). Gate: that fraction, measured on GT trajectories as a proxy.

---

## 3. Hosted-call cost estimate (BFCL `multi_turn_base`)

Per-episode assumptions:

| arm | hosted calls / episode | basis |
|---|---|---|
| `planner_alone` (ceiling + prefix source) | **12** (range 10–16) | 7.8 GT calls + 3.5 turn-ending replies + some exploration [OBSERVED W8 sample; rest INFERRED]; AppWorld's analogue is 14.43 [OBSERVED L8b] |
| `takeover_k` (channel, ACT) | **3** (2–4) | AppWorld k=10: 2.32 [OBSERVED L8b]; k rescaled to ~5 for shorter episodes [INFERRED] |
| `advise_k_fullctx` (channel, ADVISE) | **3** (2–4) | AppWorld k=10: 2.46 [OBSERVED L8b] |
| 3 prefix depths × 2 receivers (6 arms) | **0 live** | pure replay of the `planner_alone` trajectories, as on AppWorld [OBSERVED L8a]; their cost is the source run's, amortised |
| `executor_alone` × 2 receivers | 0 | local |
| user simulator | 0 | scripted turns [OBSERVED W1] |

| design | episodes per arm | planner_alone | channel pair | prefix arms | dry run | +10 % retries | **total hosted calls** | ≈ USD at $0.0021–0.0025/call [INFERRED from L8b] |
|---|---|---|---|---|---|---|---|---|
| **E1 gate, dev only** (50 tasks × 2 seeds) | 100 | 1,200 | 600 | 0 | 100 | 190 | **≈ 2,100** | ≈ $5 |
| **Lean replication** (dev 50 × 2 seeds + test 150 × 1 seed) | 250 | 3,000 | 1,500 | 0 | 100 | 460 | **≈ 5,050** | ≈ $11–13 |
| Full (dev and test both × 2 seeds) | 400 | 4,800 | 2,400 | 0 | 100 | 730 | ≈ 8,000 | ≈ $17–20 |
| Lean, high-end assumptions (16 / 4 / 4) | 250 | 4,000 | 2,000 | 0 | 100 | 610 | ≈ 6,700 | ≈ $14–17 |

The lean design meets the ~5k budget. Its test arm has n = 150 pairs, more than AppWorld's n = 114
[OBSERVED L8c]. If the channel pair is run on **both** receivers instead of the zero-shot one only, add
≈ 1,500 calls. Dollars are negligible; the binding constraint is the per-window call quota
[INFERRED]. Local GPU load: 6 prefix arms + 2 `executor_alone` = 8 × 250 = 2,000 executor episodes
[INFERRED].

**Pricing the τ² hazard, for comparison.** In default τ² every arm, including the free local ones, needs
live user-simulator turns after handoff; caching covers only the replayed prefix [INFERRED]. At roughly
8 user turns per episode [INFERRED] across 10 arms × 250 episodes, that adds about 20,000 user-sim calls,
or about 15,500 after caching prefix turns — roughly 4× the whole BFCL budget if the simulator is hosted
(the paper uses gpt-4.1 [OBSERVED T2]). The alternative, a local user simulator, costs fidelity and GPU
hours [INFERRED]. Telecom in solo mode avoids all of this [OBSERVED T3], which is why it is the fallback
and default τ² ranks 6th.

---

## 4. Citations

Local (worktree `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`):

- L1 `src/sidekick/environments/base.py:9-42`
- L2 `src/sidekick/environments/appworld_env.py:19-34` (docstring: hash weakens replay), `:147-158` (`snapshot_hash`)
- L3 `src/sidekick/prefix_source.py:1-11` (visible divergence only), `:155-173` (hash check, `replay_divergence`), `:28-37` (`handoff_occurred`)
- L4 `src/sidekick/runner.py:71-77` (`appworld_task_ids`), `:273-286` (`make_env`, raises on unknown kind)
- L5a `src/sidekick/systems/loop.py:167-175` (`prefix_is_terminal`); L5b `src/sidekick/systems/loop.py:1112-1141` (break on COMPLETE)
- L6 `src/sidekick/environments/appworld_env.py:89-101` and `src/sidekick/environments/mock_env.py:55-62` (COMPLETE → `done=True`)
- L7 `src/sidekick/runner.py:95` (`max_steps` default 40)
- L8a `docs/claims_ledger.md:41` (TAILOR-03, prefix arms zero live calls); L8b `docs/claims_ledger.md:100` (COST-01 per-arm calls/USD); L8c `docs/claims_ledger.md:102` (COST-03: n = 114 pairs / 57 tasks / 19 clusters; executor_alone −43.86 pp TGC)
- L9 `docs/literature_matrix_v2.md:198` (granite-4.2-8b model card: BFCL v4 52.39)
- M1 `/home/n12194778/.claude/projects/-mnt-hpccs01-home-n12194778/memory/hpc-aqua-resources.md:17` (Apptainer, no Docker daemon, no fakeroot)

BFCL:
- W1 BFCL v3 multi-turn blog — https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html
- W2 BFCL repo README — https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard
- W3 backend directory — https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/func_source_code
- W4 `message_api.py` — https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/func_source_code/message_api.py
- W5 `trading_bot.py` — https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/func_source_code/trading_bot.py
- W6 `multi_turn_utils.py` — https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/multi_turn_utils.py
- W7 `multi_turn_checker.py` — https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/multi_turn_checker.py
- W8 Base ground truth — https://raw.githubusercontent.com/ShishirPatil/gorilla/main/berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/BFCL_v4_multi_turn_base.json
- W9 leaderboard CSV — https://gorilla.cs.berkeley.edu/data_overall.csv
- W10 paper (ICML 2025, PMLR 267) — https://proceedings.mlr.press/v267/patil25a.html · https://openreview.net/forum?id=2GmDdhBdDk

τ-bench family:
- T1 repo — https://github.com/sierra-research/tau2-bench
- T2 paper — https://arxiv.org/abs/2506.07982 (HTML: https://arxiv.org/html/2506.07982)
- T3 gym README — https://github.com/sierra-research/tau2-bench/blob/main/src/tau2/gym/README.md
- T4 `llm_agent.py` (LLMSoloAgent) — https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/agent/llm_agent.py
- T5 `environment.py` — https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/environment/environment.py
- T6 telecom domain files — https://github.com/sierra-research/tau2-bench/tree/main/data/tau2/domains/telecom
- T7 telecom splits — https://raw.githubusercontent.com/sierra-research/tau2-bench/main/data/tau2/domains/telecom/split_tasks.json
- T8 release notes — https://github.com/sierra-research/tau2-bench/blob/main/RELEASE_NOTES.md
- τ³ (search result only, not read) — https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice

Others:
- WB1 WorkBench paper — https://arxiv.org/abs/2405.00823 (HTML: https://arxiv.org/html/2405.00823); WB2 repo — https://github.com/olly-styles/WorkBench
- S1 ToolSandbox paper — https://arxiv.org/abs/2408.04682 (HTML: https://arxiv.org/html/2408.04682); S2 repo — https://github.com/apple/ToolSandbox
- G1 ARE paper — https://arxiv.org/abs/2509.17158; G2 Gaia2 dataset card — https://huggingface.co/datasets/meta-agents-research-environments/gaia2; G3 HF blog — https://huggingface.co/blog/gaia2; G4 ARE Gaia2 docs — https://facebookresearch.github.io/meta-agents-research-environments/user_guide/gaia2_evaluation.html
- AW1 ALFWorld repo — https://github.com/alfworld/alfworld (paper https://arxiv.org/abs/2010.03768, not read)
- WS1 WebShop — https://arxiv.org/abs/2207.01206
- SW1 ScienceWorld — https://arxiv.org/abs/2203.07540; SW2 repo — https://github.com/allenai/ScienceWorld
- I1 InterCode — https://arxiv.org/abs/2306.14898; I2 repo — https://github.com/princeton-nlp/intercode
- O1 OfficeBench — https://arxiv.org/abs/2407.19056; O2 repo — https://github.com/zlwang-cs/OfficeBench
- N1 NESTFUL — https://arxiv.org/abs/2409.03797
- TAC1 TheAgentCompany — https://arxiv.org/abs/2412.14161
- AP1 AppWorld — https://arxiv.org/abs/2407.18901
- TP1 TravelPlanner — https://arxiv.org/abs/2402.01622
- TT1 ToolTalk — https://arxiv.org/abs/2311.10775

---

## 5. What could not be verified

- **BFCL episode length** comes from the first 15 Base entries only, read through the fetch summariser;
  I re-added its per-entry figures by hand (53 turns and 117 calls over 15 entries, i.e. 3.53 and 7.8).
  The full 200-entry distribution is spike item (c)(ii).
- The **BFCL paper PDF** came back as binary and could not be parsed, so no paper-level multi-turn
  statistics are cited.
- Whether **Miss Func / Miss Param / Long Context entries are derived from the same Base tasks** was not
  checked. It only matters if those categories are used.
- **granite-4.2-8b's multi-turn score** is not in the leaderboard CSV. Only older Granite-3.x rows were
  seen [W9], and the CSV snapshot may predate newer models.
- **τ² telecom split sizes.** The summariser reported small 20 / train 63 / test 39, which does not sum
  to the 114 in the paper; treat these as unverified. Also unverified: whether any domain other than
  telecom has `ticket`s. The solo agent requires one [T4], and only telecom ships `*_solo.md` policy
  files [T6].
- The τ² no-user vs dual-control pass¹ figures (gpt-4.1 52→34, o4-mini 59→34, claude-3.7 49→49) came
  through the summariser [T2] and are not relied on above.
- **ToolSandbox's license**: the repo LICENSE text was not seen. **InterCode per-env sizes, ALFWorld 134
  games, WebShop's reward form, ScienceWorld task/variation counts** (the repo summary said about 4,846
  variations; the paper is usually cited at 30 tasks), **TheAgentCompany's 175 tasks, SWE-bench
  Verified's 500**, and **Gaia2 episode lengths** are from memory or unparsed pages and are all marked
  INFERRED.
- The **per-call dollar rate** assumes BFCL calls cost no more than AppWorld calls. BFCL prompts carry
  fewer API docs (1–2 classes) but the same planner, so this is plausible, but it is not measured.
- **Adapter LOC** figures are estimates against the 254-line AppWorld adapter and the plan's
  650–1,050 LOC envelope (`docs/plan_two_papers_20260923.md:202-203`). They were not built.
