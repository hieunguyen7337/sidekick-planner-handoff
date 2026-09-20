# STATUS_D3 — train/serve intervention mismatch (done)
Wrote `docs/FOLLOWUPS.md:889-946` and `campaign/RUNS.md:2335-2374`.
No code and no frozen document (`docs/prereg_v1.md`, `docs/prereg_b1_pilot.md`, `docs/prereg_j9_freeze_20260920.md`) was touched.
Existing results recorded as correct of the system as built; not described as wrong.
Did not run git, python, or qsub. Objection: `:255` is `strip_interventions: bool` without default; `:316` carries `= True`. Citations used unchanged.
[OBSERVED src/sidekick/training/matched_sft.py:255] [OBSERVED src/sidekick/training/matched_sft.py:316] [OBSERVED src/sidekick/training/matched_sft.py:262] [OBSERVED src/sidekick/training/matched_sft.py:445-446] [OBSERVED src/sidekick/training/matched_sft.py:597-600] [OBSERVED src/sidekick/training/sft_data.py:48] [OBSERVED src/sidekick/training/sft_data.py:46] [OBSERVED src/sidekick/systems/loop.py:748] [OBSERVED src/sidekick/systems/loop.py:775] [OBSERVED src/sidekick/systems/loop.py:856] [OBSERVED src/sidekick/systems/loop.py:881] [OBSERVED src/sidekick/systems/loop.py:898] [OBSERVED src/sidekick/training/matched_sft.py:806]
