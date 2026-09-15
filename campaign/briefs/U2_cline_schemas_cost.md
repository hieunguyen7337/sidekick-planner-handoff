# U2 — Sidekick schemas, event log, cost ledger and unit tests (owner: Cline)

## Goal (what "done" means)

The data spine of the study exists and is tested, with no GPU, no network and no model calls:
pydantic schemas, an append-only JSONL event log with run manifests, a price schedule and a cost ledger,
and a unit test suite that passes. Create the files **within your first three actions**, then iterate
with tests.

## Files you own — do not create or edit anything else

| path | content |
|---|---|
| `pyproject.toml` | project `sidekick`, requires-python `>=3.11`, deps: `pydantic>=2`, `pyyaml`; optional-dependency group `dev`: `pytest`. src layout (`[tool.setuptools] package-dir = {"" = "src"}` or hatchling equivalent) |
| `src/sidekick/__init__.py` | version string only |
| `src/sidekick/protocols/__init__.py`, `schemas.py` | every type in the seam contract, verbatim names and fields |
| `src/sidekick/trajectories/__init__.py`, `eventlog.py` | `EventLog` per the contract |
| `src/sidekick/cost/__init__.py`, `prices.py`, `ledger.py` | `PriceSchedule`, `CostLedger` per the contract |
| `configs/cost/prices_2026-09.yaml` | the rate table below |
| `tests/unit/test_schemas.py`, `test_eventlog.py`, `test_cost.py` | >= 30 tests total |
| `campaign/workers/logs/U2_STATUS.md` | STATUS file, updated per milestone |

**Do NOT create or edit** `src/sidekick/agents/`, `src/sidekick/environments/`,
`src/sidekick/systems/`, `src/sidekick/runner.py`, `scripts/`, `docs/`, or anything under
`campaign/briefs/`. Another worker owns those and is editing them right now.

## The seam contract is non-negotiable

Read `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/briefs/SEAM_CONTRACT.md`
and implement the types with **exactly** those names and field names. Another worker is writing code
against them in parallel, so a renamed field breaks the build. If you believe a field is wrong, write
the objection in STATUS.md and implement the contract anyway.

## Specifics beyond the contract

**`schemas.py`**
- Use `model_config = ConfigDict(extra="forbid")` on every model except `Usage.raw` and `Event.payload`,
  which are free-form dicts.
- `ExecutorAction` gets a model validator: `kind=="CODE"` requires non-empty `code`;
  `kind=="ASK_PLANNER"` requires non-empty `ask_reason`. Raise `ValueError` otherwise.
- Add a module-level helper `parse_executor_action(raw: str) -> ExecutorAction` that extracts an action
  from model text. Accept, in priority order: a fenced ```python block (→ `CODE`), a line starting with
  `ASK_PLANNER:` (→ `ASK_PLANNER`, remainder is `ask_reason`), `REPORT:` (→ `REPORT`), `COMPLETE`
  (→ `COMPLETE`). Always set `raw_output` to the untouched input. On no match raise
  `ActionParseError(raw_output=raw)` — a custom exception carrying the raw text, so the caller can log a
  `parse_error` event. Unit-test each branch including a code block with a nested fence.
- `utc_now_iso()` helper returning `datetime.now(timezone.utc).isoformat()`.

**`eventlog.py`**
- `EventLog(root, run_id)` creates `<root>/<run_id>/` and opens `events.jsonl` in append mode.
- `append()` writes `event.model_dump_json()` plus `\n` and **flushes every write** (a job can be killed
  at any moment; a partial file must still be readable up to the last complete line).
- `write_manifest(dict)` writes `<root>/<run_id>/manifest.json` with `json.dumps(..., indent=2,
  sort_keys=True)`. Include whatever the caller passes, plus automatically: `run_id`, `created_at`,
  `hostname`, `pid`, `python_version`, and `schema_version` (a constant in `schemas.py`).
- `EventLog.read(path)` is a static method yielding validated `Event` objects and **skipping a trailing
  truncated line** without raising (test this explicitly by truncating a file mid-line).
- Never rewrite or delete an existing line.

**`prices.py` / `ledger.py`**
- YAML shape:
  ```yaml
  schedule_date: "2026-09-15"
  source: "developers.openai.com/api/docs/models/gpt-5.6-luna (list price, 2026-09-15)"
  models:
    gpt-5.6-luna:      {input: 0.20, cached_input: 0.02, output: 1.20}   # USD per 1M tokens
    gpt-5.6-terra:     {input: 2.00, cached_input: 0.20, output: 12.00}
  local:
    usd_per_gpu_hour: 2.50    # assumption for amortised H100; documented, not a measurement
  ```
- `cost_usd(usage)`: for `provider=="codex"` bill
  `(input_tokens - cached_input_tokens)` at `input`, `cached_input_tokens` at `cached_input`, and
  `(output_tokens + reasoning_output_tokens)` at `output`. **Reasoning tokens are billed as output** —
  test that. For `provider=="vllm"` bill `gpu_seconds/3600 * usd_per_gpu_hour` and no token cost. For
  `provider=="mock"` return 0.0. An unknown model name raises `UnknownModelError` (do not silently
  return 0).
- `CostLedger.totals()` returns exactly the keys in the contract. Add
  `frontier_displacement(collab_totals, baseline_totals) -> dict` computing
  `1 - collab.planner_tokens_total / baseline.planner_tokens_total` and the same ratio for
  `planner_calls_total`, returning `{"fcd_tokens": float, "fcd_calls": float}`; guard divide-by-zero by
  returning `float("nan")` and test it.

## Tests

`tests/unit/`, pytest, no network, no GPU, must run in under 30 seconds. Cover: every validator branch;
`parse_executor_action` on at least 8 inputs including malformed ones; event log round-trip; truncated
last line; manifest contents; cost arithmetic against **hand-computed numbers written as literals in the
test** (not recomputed by the same code path); unknown model raising; FCD including the zero case.

## Running tests — read this before you run anything

This is a shared HPC login node with a hard rule: **never run Python, `pytest` or any package install on
the login node `aquarius01`.** Run them inside a PBS job:

```
timeout 900 hpc -c 4 -m 16gb -t 00:20:00 bash -lc 'cd <repo> && uv run --python 3.12 --with pydantic --with pyyaml --with pytest pytest tests/unit -q'
```

Put `timeout <seconds>` in front of **every** command you run. Do not run any `git` command — Claude
commits. Do not print the value of any token or credential.

## Return contract

Update `campaign/workers/logs/U2_STATUS.md` after each milestone (schemas / eventlog / cost / tests)
with what is done and how to resume. Finish with a summary of at most 20 lines: the files created, the
test count and the **verbatim final pytest line** (e.g. `34 passed in 2.11s`), any place you deviated
from the seam contract and why, and anything you could not verify. Tag factual claims
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
