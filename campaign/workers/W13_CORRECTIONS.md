# W-13 Analysis: Harmful Corrections Classification

Analysis of the 40 most harmful and 40 most helpful review corrections from `/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15/campaign/workers/harm_sample_corrections.jsonl` (lines 1–40 harmful, line 41 separator, lines 42–81 helpful). [OBSERVED campaign/workers/harm_sample_corrections.jsonl:1-81]

> **Public copy (2026-09-28).** The correction texts are AppWorld train content, so they are not published. The public `harm_sample_corrections.jsonl` keeps only `delta`, `step`, `replay_k`, `n_later`, `task_id` and `seed` for each record, in the same line layout (line 41 is still the separator), so every line citation below still points at the same record. Verbatim quotes of corrections read `[correction text omitted]`, and the analysis around them is paraphrased. Evidence tags that rest on the correction text (the text-length figures, the grep checks and the per-record readings) refer to the pre-release file and cannot be re-run on the public one.

## 1. Classification Table

Every record was assigned exactly one primary label according to the brief criteria. [INFERRED]

| Label | Harmful 40 Count | Helpful 40 Count | Harmful Rate | Helpful Rate |
|---|---:|---:|---:|---:|
| `redundant` | 17 | 32 | 42.5% | 80.0% |
| `sound_but_unneeded` | 0 | 6 | 0.0% | 15.0% |
| `contradicts_history` | 4 | 0 | 10.0% | 0.0% |
| `wrong_for_task` | 18 | 2 | 45.0% | 5.0% |
| `vague` | 1 | 0 | 2.5% | 0.0% |
| `unclear` | 0 | 0 | 0.0% | 0.0% |
| **Total** | **40** | **40** | **100.0%** | **100.0%** |

### Group Summary
- **Genuinely Wrong / Conflicting (`wrong_for_task` + `contradicts_history`)**: **55.0% (22/40)** in harmful vs **5.0% (2/40)** in helpful. [INFERRED]
- **Sound Advice / Redundant (`redundant` + `sound_but_unneeded`)**: **42.5% (17/40)** in harmful vs **95.0% (38/40)** in helpful. [INFERRED]
- **Vague / Unactionable (`vague`)**: **2.5% (1/40)** in harmful vs **0.0% (0/40)** in helpful. [INFERRED]

## 2. Text Length Metrics

Computed across all 40 records in each group: [OBSERVED /home/n12194778/.hpc-spool/20260918-104040-1048879.out:5-10]

- **Harmful 40**: Mean character length = **252.90** chars; Mean word count = **33.67** words. [OBSERVED /home/n12194778/.hpc-spool/20260918-104040-1048879.out:7,9]
- **Helpful 40**: Mean character length = **251.15** chars; Mean word count = **32.60** words. [OBSERVED /home/n12194778/.hpc-spool/20260918-104040-1048879.out:8,10]

The text length distributions between harmful and helpful corrections are virtually identical (<1% difference), showing that verbose vs concise phrasing does not explain review harm. [INFERRED]

## 3. Near-Duplicates Across Records for Same `task_id`

- **Harmful Group**: 9 tasks have multiple records (22 of 40 total records). [OBSERVED /home/n12194778/.hpc-spool/20260918-103830-1022163.out:3-65]
  - `3c13f5a_1`: 4 records (lines 1, 7, 8, 35)
  - `7d7fbf6_1`: 3 records (lines 2, 10, 39)
  - `7d7fbf6_2`: 3 records (lines 11, 30, 40)
  - `2a163ab_3`: 2 records (lines 17, 36)
  - `6104387_1`: 2 records (lines 4, 26)
  - `76f2c72_1`: 2 records (lines 18, 22)
  - `7d7fbf6_3`: 2 records (lines 19, 29)
  - `c901732_3`: 2 records (lines 3, 21)
  - `e3d6c94_3`: 2 records (lines 13, 27)
  
  **Identified Re-injection Loops in Harmful Records**:
  - `7d7fbf6_3` (seed 2): At step 15 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:29], the reviewer told the agent that the sub-directories of one of the user's photo folders must not be processed, and to finish with `COMPLETE`. At step 20 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:19], the reviewer re-injected the same abort instruction almost word for word (text omitted).
  - `2a163ab_3` (seed 2): At step 10 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:36], the reviewer wrongly treated the password list as positional; at step 20 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:17], it re-injected a hard-coded positional index into that list to pick the phone account.
  - `76f2c72_1` (seeds 2 & 3): In both runs at step 20 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:18,22], the reviewer asserted a false premise about the task's data (text omitted). Acting on it, it ordered the agent to report an incomplete sum in seed 2 and an outright task failure in seed 3.

- **Helpful Group**: 9 tasks have multiple records (19 of 40 total records), but multi-step records reflect constructive refinement (e.g. correcting a positional index to an exact account name lookup in `6ea6792_1` [OBSERVED campaign/workers/harm_sample_corrections.jsonl:47,58] and refining password extraction in `ccb4494_1` [OBSERVED campaign/workers/harm_sample_corrections.jsonl:55,79]), with 0 abort re-injections. [INFERRED]

## 4. Dominant Harmful Patterns: Three Examples

The original analysis quoted each correction verbatim. The public copy gives a paraphrase instead.

### Example 1: State & Schema Hallucination (`wrong_for_task`)
- **`task_id`**: `3c13f5a_1` | **`delta`**: `-0.75` | **Line**: 1 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:1]
- **Quote**: `[correction text omitted]`
- **Paraphrase**: the reviewer asserted that the supervisor's credential list was redacted, forbade looking accounts up by name, and told the agent to pair accounts and passwords by position.
- **Grep Verification**: the quoted text matched exactly **1** line of the pre-release file [OBSERVED /tmp/grep_check.out:1].
- **Why Harmful**: The reviewer hallucinated that the supervisor credential list was redacted and forbade name-based lookup, forcing positional pairing that broke authentication. [INFERRED]

### Example 2: Premature Task Abort / Fake Completion (`wrong_for_task`)
- **`task_id`**: `7d7fbf6_3` | **`delta`**: `-0.5` | **Line**: 19 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:19]
- **Quote**: `[correction text omitted]`
- **Paraphrase**: the reviewer declared some of the task's source directories to be protected and off limits, and ordered the executor to stop all work at once and return `COMPLETE`.
- **Grep Verification**: the quoted text matched exactly **1** line of the pre-release file [OBSERVED /tmp/grep_check.out:1].
- **Why Harmful**: Because the reviewer only sees an 8-line local window, it misidentified legitimate source directories as protected output files and commanded the executor to halt all work immediately and return `COMPLETE` with 0 work done. [INFERRED]

### Example 3: Environment API Hallucination (`wrong_for_task`)
- **`task_id`**: `6104387_1` | **`delta`**: `-0.6499999999999999` | **Line**: 4 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:4]
- **Quote**: `[correction text omitted]`
- **Paraphrase**: the reviewer ordered the agent to write the output with `csv.writer` and forbade escaping the rows by hand.
- **Grep Verification**: the quoted text matched exactly **1** line of the pre-release file [OBSERVED /tmp/grep_check.out:1].
- **Why Harmful**: The reviewer ordered the agent to use `csv.writer` and prohibited manual row escaping, but `csv.writer` is unavailable in AppWorld (as established in record 78 [OBSERVED campaign/workers/harm_sample_corrections.jsonl:78]), trapping the executor in an import/runtime error. [INFERRED]

## 5. Verdict on the Allocation-vs-Format Question

Among the most harmful reviews, **55.0% (22/40)** are driven by **format failure** (`wrong_for_task` at 45.0% and `contradicts_history` at 10.0%), where the truncated 8-line context causes the reviewer to hallucinate schema redactions, forbid valid environment APIs, or order premature task abandonment. The remaining **45.0% (18/40)** are driven by **allocation failure** (`redundant` at 42.5% and `vague` at 2.5%), where sound advice unconditionally derails an already-succeeding trajectory. In stark contrast, format failure occurs in only **5.0% (2/40)** of the helpful group (where **95.0%** is sound or oracle advice). Thus, while allocation determines whether a review is needlessly triggered on a winning path, format blindness (the restricted transcript window) is the primary driver (**55:45 ratio**) of catastrophic negative delta. [INFERRED]
