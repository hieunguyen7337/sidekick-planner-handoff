# Brief X20 — the systematic literature review for the pivoted thesis

Repo (absolute): `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

Documentation and retrieval only. **Do not `qsub`, do not touch a GPU, do not run any evaluation, do
not edit `src/`, `configs/`, `scripts/` or anything under `campaign/results/`.**

## Precondition — do this first and stop if it fails

Fetch `https://arxiv.org/abs/2608.24358` and print its title. If you cannot reach the network, write
`campaign/workers/STATUS_X20.md` saying so and **STOP**. I will fetch the sources and hand you
extracts instead. Do not proceed on memory: several of these papers are weeks old and your
recollection of them will be wrong.

## Read this before searching

`campaign/workers/lit/extracts_20260922.md` — verified extracts for ~30 papers, fetched 2026-09-22,
including complete abstracts, verbatim quotes, benchmark names, numbers and the novelty perimeter.
**Do not re-fetch those papers to establish facts already recorded there.** Re-fetch only to quote a
sentence not already quoted, or to fill a field marked `NOT ESTABLISHED`.

## Why this exists

The project pivoted. The executor no longer asks a hosted planner for *advice*; the planner *acts*
for the opening stretch of an episode and a tailored 8B local executor finishes it. The existing
`docs/literature_matrix.md` (15 entries), `docs/novelty_boundary.md` and
`RESEARCH_PROJECT_SPEC.md:220-352` were all written before that pivot and do not cover the
mid-trajectory model-handoff literature at all. A paper published on 2026-08-25 — The Handoff Tax —
is now the closest prior work and is not cited anywhere in the repo.

## The protocol — write it before you search

`docs/lit/PROTOCOL.md`, containing:

- **Sources**: arXiv (cs.CL, cs.AI, cs.LG), ACL Anthology, OpenReview (ICLR/NeurIPS/ICML 2024–2026),
  Semantic Scholar, Google Scholar.
- **Window**: 2022-01 to 2026-09, plus classic anchors outside it where a lineage demands one.
- **Snowballing**: backward and forward from twelve anchors — Handoff Tax (2608.24358), Reach-or-Solve
  (2609.19636), SwiftSage (2305.17390), ReOPD (2607.04763), Guided-OPD (2606.15912), MTRouter
  (2604.23530), harness-native agentic routing (2607.11399), AppWorld (2407.18901), CANOPY
  (2609.01245), ProST (2509.04508), AgentCARD (2606.20629), R2V-Agent (2605.16604).
- **Search strings**: at least fifteen, each recorded **verbatim with its hit count and date**. Start
  from: "model handoff agent trajectory"; "downshift cheaper model continue trajectory";
  "planner executor small model large model"; "step-level routing agent"; "turn-level routing";
  "fast slow agent small large"; "speculative planning agent"; "agent distillation small model
  trajectories"; "on-policy distillation multi-turn agent"; "teacher prefix replay";
  "advice critique small model cannot use feedback"; "compounding errors LLM agents long-horizon";
  "learning to defer sequential"; "AppWorld"; "non-inferiority bootstrap NLP".
- **Inclusion criteria** — a paper is included if it does any of: two models of different cost
  collaborating *within one episode*; small-model agent training from large-model trajectories;
  reports AppWorld results; proposes a replay or handoff *evaluation protocol*; studies whether
  advice or critique helps a smaller model; or supplies the statistical method we use.
- **Exclusion**: single-model efficiency work with no collaboration; pure serving/systems routing with
  no quality axis; position pieces with no evidence (may be cited as motivation, never as evidence).

## Outputs

1. **`docs/lit/screening_log.csv`** — columns: `key,title,year,venue,url,found_via,query,
   include,reason,theme`. Target **≥ 60 screened, ≥ 35 included**. Every excluded row needs a reason.

2. **`docs/literature_review_20260923.md`** — a narrative review in **nine themes**, each ending with a
   short subsection titled `What we add` (leave that subsection as the single line
   `TODO(claude): novelty verdict` — **I write those myself, do not attempt them**):
   1. Query-level cascades and routers
   2. Step- and turn-level routing, and mid-trajectory model switching (the Handoff Tax ring)
   3. Fast/slow agents and speculative planning
   4. Token-level collaboration (analogy only — say why it is not our setting)
   5. Role-factorised heterogeneous agent teams
   6. Distilling agents into small models, and the demonstration-prefix / reverse-curriculum lineage
   7. Advice, critique, and the limits of self-correction in small models
   8. Long-horizon failure mechanics and learning-to-defer
   9. AppWorld, its state of the art, and evaluation statistics

3. **`docs/literature_matrix_v2.md`** — same YAML-per-paper shape as the existing
   `docs/literature_matrix.md` (read it first and copy the key names and field names exactly:
   `key`, `title`, `venue_or_arxiv`, `year`, `url`, `what_it_does`, `relation_to_us`,
   `numbers_we_cite`). Carry all 15 existing entries forward unchanged except `relation_to_us`,
   which you update for the pivot. Every entry in `numbers_we_cite` must be tagged
   `[OBSERVED <url>]`. **Leave `docs/literature_matrix.md` itself untouched** — v2 is a new file.

4. **`docs/concurrent_work.md`** — the papers published within ~8 weeks of today that a reviewer will
   say we must distinguish ourselves from: Handoff Tax (2026-08-25), Reach-or-Solve (2026-09-17),
   ReOPD (2026-07), MTRouter, harness-native routing. For each: date, one-paragraph summary, and a
   factual "differs from ours in …" listing setup differences only. **No novelty claims** — facts only.

5. **`paper/bibliography.bib`** — a BibTeX entry for every included paper, with DOI or arXiv id.
   Create the `paper/` directory. Use the `key` values from the matrix as citation keys.

## Rules that decide whether this unit is usable

- **Every factual claim carries `[OBSERVED <url>]` or `[INFERRED]`.** A number, a benchmark name, a
  model name and a quoted sentence are all factual claims.
- **Never state a paper's result from memory.** If you did not fetch it and it is not in the extracts
  file, write `NOT ESTABLISHED` and move on. A confident wrong number here is worse than a gap: it
  will be repeated in a thesis and found by an examiner.
- Quoted sentences must be verbatim and in quotation marks. Paraphrase everything else.
- Where the extracts file already gives a quote or number, cite it and do not re-derive it.

## Constraints

- `aquarius01` is a **login node**: no interpreter, `pip`, `tar`, `rsync`, `ffmpeg` there. `timeout` on
  every command. You should not need any compute at all for this unit.
- Dev only; never read `test_normal` or `test_challenge` data.
- Frozen, read only: `docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`,
  `docs/prereg_j9_freeze_20260920.md`, `docs/prereg_hj12_dev_20260922.md`, every `hj8_*` and `hj11_*`
  config, and `docs/literature_matrix.md`.
- **Do not commit.** I review and commit.
- Size the unit to ≤ 10 hours and write STATUS as you go, with resume state per output file.

## Return contract

`campaign/workers/STATUS_X20.md`, under 600 words: the five output paths, the count of papers
screened and included, the fifteen-plus search strings with hit counts, the five papers you judge
closest to our setting with one line each on why, and any field you had to mark `NOT ESTABLISHED`.
Tag every claim `[OBSERVED <path-or-url>]` or `[INFERRED]`.
