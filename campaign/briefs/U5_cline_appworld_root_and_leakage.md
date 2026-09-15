# U5 — make the AppWorld data root explicit, and add the split-leakage guard (owner: Cline)

Two small, well-specified changes. Both are about preventing a silent wrong answer later.

## Change 1 — `AppWorldEnv` must not silently use the working directory

AppWorld resolves its data root from the environment, with a dangerous default:

```python
# appworld/common/path_store.py:15
self.root = os.environ.get("APPWORLD_ROOT", os.getcwd())
```

`src/sidekick/environments/appworld_env.py` never sets or checks it. A campaign launched without that
variable would silently read from the current working directory, and AppWorld would report every task as
broken with "task directory doesn't exist" — a failure that looks like a data problem, not a
configuration one, and would waste a GPU allocation and real planner spend before anyone noticed.

**The installed data root is `/scratch/n12194778/sidekick/appworld`** (195 MB, 733 task directories,
verified tonight in gate G2).

Change `AppWorldEnv.__init__` to take `root: str | None = None` and, in this order:

1. resolve `root` → the argument, else `os.environ["APPWORLD_ROOT"]` if set, else the constant
   `DEFAULT_APPWORLD_ROOT = "/scratch/n12194778/sidekick/appworld"`. **Never fall through to `os.getcwd()`.**
2. raise `AppWorldRootError` (a new exception in that module) with a clear message if
   `<root>/data/tasks` does not exist. Fail at construction, not mid-campaign.
3. set `os.environ["APPWORLD_ROOT"] = root` **before** the lazy AppWorld import in `reset()`.
4. expose the resolved value as `self.root`, and add it to whatever dict the class already offers for
   manifest/metadata purposes (if there is none, add a `def manifest_fields(self) -> dict` returning
   `{"appworld_root": self.root, "experiment_name": self.experiment_name}`).

Add tests in `tests/unit/test_appworld_root.py` that do **not** require AppWorld to be installed:
explicit argument wins over the environment variable; the environment variable wins over the default;
a root whose `data/tasks` is missing raises `AppWorldRootError`; `os.getcwd()` is never used (point the
cwd at a temporary directory and assert the resolved root is not it).

## Change 2 — the split-leakage guard

`docs/PLAN.md` promises a CI test that fails if a dev or test task id ever appears in a training
manifest. It does not exist yet. Write `tests/reproducibility/test_split_leakage.py`:

- a function `assert_no_leakage(train_ids, heldout_ids)` in
  `src/sidekick/training/__init__.py` (create the package if absent) that raises on any intersection and
  names the offending ids;
- tests covering the clean case, a single overlapping id, and an empty-input case;
- a test that scans `artifacts/adapters/*/manifest.json` **if any exist** and asserts no held-out id
  appears, skipping cleanly when there are none (there are none yet — it must not fail on an empty tree).

Use the **measured** split sizes, not the published ones: train 90, dev 57, test_normal 168,
test_challenge 417.

## Files you own

`src/sidekick/environments/appworld_env.py`, `src/sidekick/training/__init__.py`,
`tests/unit/test_appworld_root.py`, `tests/reproducibility/test_split_leakage.py`,
`campaign/workers/logs/U5_STATUS.md`. **Nothing else.** Do not touch
`src/sidekick/protocols/schemas.py`, `src/sidekick/systems/`, `docs/` or `scripts/`.

Keep every name in `campaign/briefs/SEAM_CONTRACT.md` unchanged — `BaseEnv.reset/step/evaluate/
snapshot_hash/close` and the `Observation` type must keep their current signatures, because the systems
and the runner are already written against them and their tests pass.

## Constraints

- **Never run Python or pytest on the login node `aquarius01`.** Run the suite in a job with the ready
  script: `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 /home/n12194778/.claude/jobs/91578989/tmp/run_unit_tests.sh`
  (it runs `tests/unit`). For the whole tree use
  `timeout 900 hpc -c 4 -m 16gb -t 00:20:00 /home/n12194778/.claude/jobs/91578989/tmp/verify_all.sh`.
- `timeout <seconds>` in front of every command. **Do not run any `git` command.**
- The existing suite is **65 unit + 26 integration tests passing**. It must still pass when you are
  done — if your change breaks one, fix your change, do not edit the other test.
- Never print the value of a token or credential.

## Return contract

At most 12 lines: the verbatim final pytest lines for unit and integration from a **real run**, what the
root resolution now does, and confirmation that the previously passing tests still pass. Tag claims
`[OBSERVED <path>:<line>]` or `[INFERRED]`.
