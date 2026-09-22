"""Provenance stamped into every episode's manifest (task X16).

Until now an episode's `manifest.json` recorded campaign id, run id, host, pid, env,
python version and timestamp — and nothing about *what was run*. Four facts that the
analysis depends on were recoverable only by reconstruction from the repository, and one
was not recoverable at all:

* **git SHA** — the original X16: which code produced this episode.
* **config path** — the run stored the config's *contents* nowhere and its *path* nowhere.
* **campaign id declared by the config** — `runner.run_campaign` resolves the id as
  `campaign_id or cfg["campaign_id"]`, so the CLI flag silently overrides the file. Ten
  campaigns, including every published dev prefix arm, ran under an id their config does
  not declare; re-running such a config verbatim writes to a different directory.
* **split** — `--split` is a command-line argument only (`runner.build_parser`). No config
  carries it, so a `split:` key in a config is inert. Nothing in the artifacts recorded
  whether an episode came from dev or test, which is precisely the fact a confirmatory
  read must not get wrong.

Also stamped: the adapter alias and the replayed source campaign, because those are what
distinguish a tailored arm from an untailored one and a trajectory-paired contrast from a
merely task-paired one.

Everything here is best-effort: a missing git binary, a results directory outside a
checkout, or an odd config shape yields `None` for that field rather than aborting a
campaign. Provenance that can break a run is provenance that gets removed.
"""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path
from typing import Any

GIT_TIMEOUT_S = 5


def _git(args: list[str], cwd: Path) -> str | None:
    """Run a git command. `None` means the call failed; `""` means it succeeded silently.

    That distinction is the whole point: `git status --porcelain` prints nothing for a
    clean tree, so collapsing empty output to `None` would report every clean checkout as
    "could not determine" — and, worse, an earlier version of this function did exactly
    that, which is why `git_dirty` is tested against a real repository.
    """
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


@functools.lru_cache(maxsize=8)
def git_provenance(repo_hint: str | None = None) -> dict[str, Any]:
    """SHA, branch and dirty flag for the tree this code was imported from.

    Cached: a campaign forks one worker per episode, and shelling out to git 114 times to
    learn the same SHA is waste. The cache key is the hint so tests can vary it.

    `dirty` matters as much as the SHA. A clean SHA identifies the code exactly; a dirty
    one means the working tree held uncommitted changes and the SHA alone does not.
    """
    cwd = Path(repo_hint) if repo_hint else Path(__file__).resolve().parent
    sha = _git(["rev-parse", "HEAD"], cwd)
    if not sha:  # None (failed) or "" (no HEAD yet) - neither identifies any code
        return {"git_sha": None, "git_branch": None, "git_dirty": None}
    status = _git(["status", "--porcelain"], cwd)
    return {
        "git_sha": sha,
        "git_branch": _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd) or None,
        # `status` is "" when clean; None means the call failed, which is not the same as
        # clean and must not be reported as clean.
        "git_dirty": None if status is None else bool(status),
    }


def config_provenance(cfg: dict[str, Any] | None, config_path: str | None) -> dict[str, Any]:
    """What the config said, recorded at run time rather than reconstructed later."""
    cfg = cfg or {}
    handoff = cfg.get("handoff") or {}
    executor = cfg.get("executor") or {}
    defaults = cfg.get("policy_defaults") or {}
    planner = cfg.get("planner") or {}

    source = handoff.get("source_campaign") or planner.get("packet_source")
    return {
        "config_path": str(config_path) if config_path else None,
        # Recorded even when it equals the resolved id, so a reader never has to guess
        # whether --campaign-id was used.
        "config_campaign_id": cfg.get("campaign_id"),
        "handoff_source_campaign": str(source) if source else None,
        "handoff_m": handoff.get("m"),
        "executor_model": executor.get("model"),
        "lora_name": executor.get("lora_name") or defaults.get("lora_name"),
        "takeover": defaults.get("takeover"),
    }


def run_provenance(
    *,
    cfg: dict[str, Any] | None,
    config_path: str | None,
    split: str | None,
    resolved_campaign_id: str | None = None,
    repo_hint: str | None = None,
) -> dict[str, Any]:
    """The full provenance block written into each episode manifest."""
    block: dict[str, Any] = {"split": split}
    block.update(git_provenance(repo_hint))
    block.update(config_provenance(cfg, config_path))

    declared = block.get("config_campaign_id")
    if resolved_campaign_id is not None:
        block["campaign_id_overridden"] = bool(declared) and declared != resolved_campaign_id
    return block
