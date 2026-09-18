# STATUS — A10 (U-FIX): two silent-zero defects

## Resume state
- [x] Read brief, state_probe.py, hj1_gate.py, FOLLOWUPS.md notes.
- [ ] Defect 1 diagnosis: compare probe-world vs gold io logs on an identical-code point (PBS job, read-only on results).
- [ ] Fix state_probe.py hash_match + known-answer test.
- [ ] Fix hj1_gate.py missing-value policy + test (missing != recorded-0, missing count reported).
- [ ] Full unit suite in PBS job; baseline 365 passed, 1 skipped must hold.
- Owned: scripts/setup/state_probe.py, scripts/setup/hj1_gate.py, tests/unit/*.
- Constraints honored: no planner calls, no GPU jobs, no probe re-run, no writes under /scratch/.../results/, no commits.
