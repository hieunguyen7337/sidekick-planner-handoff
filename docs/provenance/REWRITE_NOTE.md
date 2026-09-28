# History rewrite of 2026-09-28

On 2026-09-28, the git history of this repository was rewritten using `git filter-repo` in a single pass.
The rewrite operated on a fresh single-branch clone of the private working branch `worktree-plan-2026-09-15`.
The tip commit of the original history (CUT_SHA) was `67ea249072e5ceb7bd427f128e2f0b564857454e`.
The original history comprised 333 commits, of which 327 commits were kept and 6 were pruned because the rewrite left them empty (they changed only removed paths).
The rewritten single branch was renamed `trunk`, and its last rewritten commit corresponding to the original branch tip is `898e61f78b6d2acb2ad9074a77f5f6abeb6ed737`.
All commits appearing after `898e61f78b6d2acb2ad9074a77f5f6abeb6ed737` on `trunk` are forward commits added after the rewrite.

## Why the history was rewritten

In the 6th commit of the repository history, AppWorld protected benchmark data was committed, and it was deleted 3.5 minutes later.
That data included evaluation ground truth for held-out tasks.
Under AppWorld's licence terms, public redistribution of this portion of benchmark data is permitted only in encrypted form.
Publishing the repository as a flat single-commit snapshot would have eliminated the public record of the development timeline, commit lineage, and preregistration sequence.
The history was therefore rewritten using `git filter-repo` to excise protected paths and scrub a small set of literal tokens while preserving commit dates, author and committer identities, commit ordering, and the diffs of all kept paths outside the replaced spans.

## What was removed

The filter-repo pass removed specific paths across all commits in the history using `--invert-paths`:

| Path | Why removed | State in public repository |
|---|---|---|
| `data/tasks/`, `data/api_docs/`, `data/base_dbs/`, `data/datasets/` | AppWorld protected data, added in the 6th commit and deleted 3.5 minutes later; includes evaluation ground truth for held-out tasks. AppWorld's licence allows public redistribution of this portion only in encrypted form. | Not present |
| `campaign/workers/harm_sample_corrections.jsonl` | Quoted AppWorld train content (correction texts quoting environment data). | If a file exists at this path, it is a forward-added aggregate with no correction text, not the original. |
| `tests/fixtures/hj6_branches_dev_sample.jsonl` | AppWorld dev rows with environment data and a dev answer. | If a file exists at this path, it is a forward-added synthetic fixture, not the original. |
| `paper/release/` | Private release notes: submission checklist, arXiv metadata and acknowledgement drafts, and the internal AI-use inventory with confirmation notes. | `paper/release/ai_use.md` is a cleaned public copy, added forward. |
| `docs/plan_luna_reset_20260925.md` | Operational notes on planner quota. | A one-paragraph stub at the same path, because frozen preregistrations cite it. |
| `campaign/workers/logs/` (19 tracked files) and root files `u2b_test_run.log`, `u2b_test_run2.log` | Raw worker terminal streams carrying cluster account details, home paths and held-out task identifiers. The 19 files included 7 status files (`U1`, `U1b`, `U2`, `U2b`, `U3`, `U4`, `U5` `_STATUS.md`). | Not present. The 134 `campaign/workers/STATUS_*.md` files and all worker briefs outside `logs/` are kept. |

## Literal replacements

Literal text replacements were applied across file contents in every commit and to commit messages using `--replace-text` and `--replace-message` with a 24-rule replacement file. The replacements fall into five classes:

| Class | What was replaced | Replacement | Rules | Original commits touched |
|---|---|---|---|---|
| c | AppWorld persona e-mail addresses (in a dev diagnosis JSON and its test, and in train-derived worker files) | `personaN@example.invalid` | 12 | 36 |
| d | One dev ground-truth answer value used in examples | A placeholder number | 1 | 1 |
| e | Two song titles (a partial dev answer) used in examples | `Placeholder Song A`, `Placeholder Song B` | 2 | 9 |
| f | One quoted AppWorld train task instruction in `docs/feasibility/m0_gates.md` | `[instruction omitted: AppWorld protected content]` | 1 | 1 |
| g | Quoted correction strings in `campaign/workers/W13_CORRECTIONS.md` | `[correction text omitted]` | 8 | 11 |

Total: 24 rules. Three commit messages contained class d or e literals and were modified with the same replacements. No commit that touches any frozen document touches any replaced literal. The literals themselves are not published anywhere in the repository.

## What did not change

The history rewrite preserved the following properties without alteration:
- Author and committer names, email addresses, and timestamps (no mailmap was used; 154 commits carry the `aquarius01` login address and 173 the `aquarius02` one).
- Commit ordering. Parent links are unchanged, except that the child of a pruned commit now points to the pruned commit's nearest kept ancestor.
- The `Co-Authored-By` and `Claude-Session` trailers, wherever they were present.
- The first 4 commits in the repository keep their exact original git hashes because they predate the AppWorld protected data and contain no removed path and no replaced literal (the 5th commit also predates the data but changed, because its tree held removed worker logs under `campaign/workers/logs/` and the two root `u2b_test_run*.log` files):
  - `b150c7314d18c6ad30b76dc5d593e45c588bde8f` (root)
  - `1af2b3b940a9c56264d2630adba941154f0090a7`
  - `d231fed093e40871f184d279907f759b2d71420c`
  - `8d44e8a4eee0e3bed87b917dbe21629696bedbf9`
- Every subsequent commit received a new hash.
- Frozen document invariance: all 140 path and blob-ID pairs for `docs/prereg_*.md`, `docs/claims_ledger.md`, and `paper/preprint_*.md` across history are identical before and after the rewrite (0 differences). Consequently, git blob IDs and cryptographic hashes (such as the claims ledger's SHA-256 pin on `paper/preprint_dev_v2_20260924.md`) are unchanged.
- The content of every kept file outside the replaced spans is identical byte-for-byte.

## Resolving commit hashes cited in this repository

Commit hashes written inside files across the repository are original pre-rewrite hashes, whereas hashes in commit messages were translated by `git filter-repo` to new hashes.
Of the 34 distinct hexadecimal tokens of 7 to 40 characters in the rewritten commit messages, 29 are prefixes of new hashes, none is a prefix of an original hash only, and 5 are not commit hashes.
Tracked files contain 25 distinct 40-character hexadecimal strings:
- 18 are kept original commits;
- 1 is a pruned commit (`cce3bbf6d4ec70f90e47f18eca94ab2bd7e08557`);
- 6 are not commits of this repository (for example an upstream AppWorld commit, the upstream BFCL commit and a Hugging Face model revision).

To resolve an original hash cited in a file or document to its rewritten commit, search `docs/provenance/commit_map.tsv`:
```bash
grep '^<prefix>' docs/provenance/commit_map.tsv
```
Column 1 is the original full hash, column 2 is the rewritten full hash, and column 3 contains status notes (`unchanged` or `pruned: touched only removed paths; tree-equivalent: ...`).
Forward commits created after `898e61f78b6d2acb2ad9074a77f5f6abeb6ed737` do not appear in the map.

### Manifest fields

The 13 tracked `*.manifest.json` files contain 14 commit fields naming repository commits:
- 10 `git_commit` fields in `campaign/results/*.manifest.json`;
- 4 `source_commit` fields in `data/interim/*.manifest.json`.

These fields name 8 distinct kept commits, all of which are present in `docs/provenance/commit_map.tsv`.
Upstream fields (`appworld_commit` in 10 manifests and `hf_revision` in 1 manifest) refer to external revisions and are not in the commit map by design.

### Ambiguous short hash 9460b06

Two original commits share the short hash prefix `9460b06`:
1. `9460b06b554f6bc2015ab85ee7bdcccdd14b2837` (committed 2026-09-25 12:28 +10:00, "BFCL dev read (bfcl_dev_report.py) and BFCL power (bfcl_power.py)"), rewritten as `8622794f7c3e37032fd148f61eab311c827326f9`.
2. `9460b06ebf65eaa371113165f19cdbc6a1ff7497` (committed 2026-09-24 18:28 +10:00, "Dev arms R2.4, D2, D3 and the R7.1 no-op floor"), rewritten as `e8ec919e662d5d021ce62faa8292336b85261031`.

Citations resolve as follows:
- `scripts/analysis/j10_report.py` (lines 5295, 5370, 5413, 5443) and `campaign/results/j10_a1_test_normal.report.json:6721` cite `scripts/analysis/j11_report.py` "at 9460b06". That script exists only in the tree of `9460b06b554f6bc2015ab85ee7bdcccdd14b2837`, so they refer to that commit.
- `campaign/workers/briefs/20260924_ctrl_planning_controls.md:56`, `docs/claims_ledger.md:272` ("high ran on 2026-09-24 at git `9460b06`"), and `campaign/workers/staging/ledger_rows_20260924_planning.md:27` date from 2026-09-24, before the 2026-09-25 commit existed; they refer to `9460b06ebf65eaa371113165f19cdbc6a1ff7497`. `campaign/results/j17_planning_lit_20260924.report.json` records the full hash directly.

### Pruned commits

Six commits were pruned during rewrite because they modified only removed paths. Their trees outside removed paths are identical to specific kept commits:

| Old (pruned) | Date | Description | Tree-equivalent: new (old) |
|---|---|---|---|
| `27a21c1a4619d7ebc0b0f752047125d62c44404c` | 2026-09-28 | Release kit for the arXiv v1 (paper/release/ only) | `34bc2b68ca19aa153861f7ae968173e3ef881281` (`32acb7d9885015e4d24af515312d137fa6c0dc14`) |
| `b15f52e540e1ee1e7e2409e59dd4ab035a2b69de` | 2026-09-28 | AI-use inventory revision (paper/release/ only) | `34bc2b68ca19aa153861f7ae968173e3ef881281` (`32acb7d9885015e4d24af515312d137fa6c0dc14`) |
| `4bba38f207a4b369ad76d2f041129929eabd5248` | 2026-09-28 | AI-use inventory revision (paper/release/ only) | `34bc2b68ca19aa153861f7ae968173e3ef881281` (`32acb7d9885015e4d24af515312d137fa6c0dc14`) |
| `63be0d8bccbbf5e83bc075000454a8baba07db93` | 2026-09-28 | AI-use inventory revision (paper/release/ only) | `34bc2b68ca19aa153861f7ae968173e3ef881281` (`32acb7d9885015e4d24af515312d137fa6c0dc14`) |
| `cce3bbf6d4ec70f90e47f18eca94ab2bd7e08557` | 2026-09-28 | AI-use inventory revision (paper/release/ only) | `34bc2b68ca19aa153861f7ae968173e3ef881281` (`32acb7d9885015e4d24af515312d137fa6c0dc14`) |
| `bd0e1dd2c9249d6f7e4d20deec343a14a113b256` | 2026-09-25 | Planner usage-plan note (docs/plan_luna_reset_20260925.md only) | `58fb33cc02aef9c7ecf36757d6871e9489241a6d` (`bec0aac11e1924524004c121679a5144788f5ee3`) |

One pruned commit is cited in records: `docs/claims_ledger.md:313`, `campaign/results/j17_dev_arms_20260928.report.json:8` (`git_sha` field), and `campaign/results/j17_dev_arms_20260928.report.md:3` record that the j17 dev report was generated at `cce3bbf6d4ec70f90e47f18eca94ab2bd7e08557` with a dirty working tree.
Because `cce3bbf6d4ec70f90e47f18eca94ab2bd7e08557` changed only `paper/release/`, its underlying code tree equals `34bc2b68ca19aa153861f7ae968173e3ef881281` (original `32acb7d9885015e4d24af515312d137fa6c0dc14`).
No preregistration or freeze citation in the claims ledger cites a pruned commit.

## References left dangling

Several references to removed or unpublished assets were accepted and left dangling:
- At the last rewritten commit, 69 tracked files mention `campaign/workers/logs/` (worker briefs, STATUS files, PBS scripts designating log output destinations, `.gitignore`, 4 lines in `docs/claims_ledger.md`, 2 lines in `docs/prereg_j10_amendment_20260924.md`, and 1 line in `docs/prereg_j11_lp2_test_20260924.md`). Worker execution logs are not published. The log files cited in those frozen documents (the `.out` and `.aqua.out` PBS logs and the `quarantine_j11_premature_20260925/` directory) were never tracked in git, because `.gitignore` excludes `campaign/workers/logs/`; they are not among the 19 tracked files the rewrite removed.
- 7 tracked files cite `docs/plan_luna_reset_20260925.md` by section or line number (`docs/prereg_bfcl_dev_20260924.md:127,191` §0 and §5; `docs/prereg_bfcl_test_20260925.md:31` line 104; `configs/dev_advise_structured_fixed_k_1_fullctx.yaml`, `configs/dev_planner_alone_cap81_low.yaml` and `tests/unit/test_dev_arms.py:57` lines 106 and 108; `scripts/pbs/hj12_live.pbs:184,193` by arm name; `scripts/analysis/bfcl_test_report.py:1566` line 180). The file path resolves to the stub, but specific sections and line numbers are not reproduced.
- `paper/arxiv/metadata_template.md` (lines 4-5 and 88) refers to `paper/release/metadata.md`, which is not published; a forward commit replaced the absolute `file:///` links with a plain "not published" note.
- `paper/release/ai_use.md` cites worker logs (`logs/…`), a local classification file `log_classes.txt`, and local counting scripts, none of which are published.
- The commit bodies of the 6 pruned commits are not present in the public git history.

## Verifying the original history

An unredacted private bundle of the original repository history is preserved:
- Bundle file: `original_67ea249072e5ceb7bd427f128e2f0b564857454e.bundle`
- Size: 46,024,293 bytes
- SHA-256: `1accf201948c1eda4fc560cb2031c796a57cd827eb86ec4671afe359c100c2d7`
- Branch contained: `worktree-plan-2026-09-15`

The bundle is not published because it contains AppWorld protected data. The author retains an encrypted copy and can share it privately with an authorized verifier upon request.

To verify the original history and compare it with the public rewritten repository:
```bash
# 1. Verify bundle SHA-256 checksum
sha256sum original_67ea249072e5ceb7bd427f128e2f0b564857454e.bundle

# 2. Verify git bundle integrity
git bundle verify original_67ea249072e5ceb7bd427f128e2f0b564857454e.bundle

# 3. Clone the original branch from the bundle
git clone -b worktree-plan-2026-09-15 original_67ea249072e5ceb7bd427f128e2f0b564857454e.bundle original

# 4. Verify original branch tip matches CUT_SHA
git -C original rev-parse HEAD

# 5. Check existence and type of any original commit from docs/provenance/commit_map.tsv
git -C original cat-file -t <old_full>

# 6. Fetch the public repository trunk and compare trees
git -C original fetch <path-to-public-clone> trunk
git -C original diff --stat <old_full> <new_full>
```
The diff between `<old_full>` and `<new_full>` will show only removed paths and replaced literal spans.

## Checks run on the rewritten history

Before any forward commits were added, the following validation checks were executed against the rewritten history:
- V1: 0 objects under the four AppWorld `data/` paths (`data/tasks/`, `data/api_docs/`, `data/base_dbs/`, `data/datasets/`) and 0 objects under any other removed path across all commits.
- V2: Largest blob size is 31,266,416 bytes (a `hj13_shape_*` report file); total git pack size is 17.18 MiB.
- V3: 0 occurrences of any replaced literal token in any git tree object or commit message across history.
- V4: Exact blob-ID identity across all 140 frozen-document path/blob-ID pairs (140/140 matched, 0 differences).
- V5: Author and committer identities preserved (154 commits on `aquarius01`, 173 on `aquarius02`); 325 `Claude-Session` trailers and 326 `Co-Authored-By` trailers; commit map accounts for all 333 original rows (327 kept, 6 pruned).
- V6 (no commit cited in the preregistrations or the ledger may be pruned): one is, `cce3bbf6d4ec70f90e47f18eca94ab2bd7e08557`, cited as the build commit of a dev report, not as a freeze. It resolves to the tree-equivalent kept commit `34bc2b68ca19aa153861f7ae968173e3ef881281` (old `32acb7d9885015e4d24af515312d137fa6c0dc14`).
