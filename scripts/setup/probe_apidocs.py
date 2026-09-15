#!/usr/bin/env python
"""Check the prompt digest AppWorldEnv now builds: content, size, and app coverage.

_digest_api_docs returns a sha256 fingerprint for manifests. _summarise_api_docs is
the thing that goes in the prompt. This prints the latter so its size and usefulness
are verified against a real task rather than assumed.
"""
from __future__ import annotations

import os

os.environ.setdefault("APPWORLD_ROOT", "/scratch/n12194778/sidekick/appworld")

from sidekick.environments.appworld_env import AppWorldEnv  # noqa: E402

env = AppWorldEnv(experiment_name="probe_apidocs")
obs = env.reset(task_id=__import__("appworld").load_task_ids("dev")[0], seed=1)

prompt = env.api_docs_prompt
digest = env.api_docs_digest

print(f"instruction: {obs.text[:120]}")
print(f"\nfingerprint (manifest only): {digest[:16]}... len={len(digest)}")
print(f"\nprompt digest: {len(prompt)} chars, ~{len(prompt)//4} tokens")

apps = [ln for ln in prompt.splitlines() if ln and not ln.startswith("  ")]
apis = [ln for ln in prompt.splitlines() if ln.startswith("  ")]
print(f"apps: {len(apps)} -> {[a.rstrip(':') for a in apps]}")
print(f"apis: {len(apis)}")

print("\n=== first 900 chars ===")
print(prompt[:900])

print("\n=== spotify section ===")
out, keep = [], False
for ln in prompt.splitlines():
    if ln.startswith("spotify:"):
        keep = True
    elif keep and not ln.startswith("  "):
        break
    if keep:
        out.append(ln)
print("\n".join(out[:18]))

env.close()
print("\nDONE")
