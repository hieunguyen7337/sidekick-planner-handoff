"""CLI runner: mock or AppWorld episodes, multiprocessing, resumable results."""
from __future__ import annotations

import argparse
import json
import multiprocessing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sidekick.agents.executor import MockExecutor, VLLMExecutor
from sidekick.agents.planner import CodexExecConfig, CodexExecPlanner, MockPlanner
from sidekick.agents.verifier import ConstantVerifier, ScriptedVerifier
from sidekick.cost.ledger import CostLedger
from sidekick.cost.prices import PriceSchedule
from sidekick.environments.appworld_env import AppWorldEnv
from sidekick.environments.base import BaseEnv
from sidekick.environments.mock_env import MockEnv
from sidekick.systems import SYSTEM_NAMES, get_system
from sidekick.systems.loop import RunLimits
from sidekick.trajectories.eventlog import EventLog

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICES = REPO_ROOT / "configs" / "cost" / "prices_2026-09.yaml"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml

        data = yaml.safe_load(text) or {}
    except Exception:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("config must be a mapping")
    return data


def parse_seeds(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def mock_task_ids(n: int) -> list[str]:
    if n <= 1:
        return ["copy_hello"]
    return [f"copy_hello_{i:03d}" for i in range(n)]


def appworld_task_ids(split: str, n: int) -> list[str]:
    from appworld import load_task_ids

    ids = list(load_task_ids(split))
    if n > 0:
        ids = ids[:n]
    return ids


def result_path(out: Path, run_id: str) -> Path:
    return out / run_id / "result.json"


def events_path(out: Path, run_id: str) -> Path:
    return out / run_id / "events.jsonl"


def make_run_id(campaign_id: str, system: str, seed: int, task_id: str) -> str:
    return f"{campaign_id}/{system}/{seed}/{task_id}"


def make_limits(cfg: dict[str, Any]) -> RunLimits:
    limits = cfg.get("limits") or {}
    return RunLimits(
        max_steps=int(limits.get("max_steps", 40)),
        max_tokens_per_episode=int(limits.get("max_tokens_per_episode", 32000)),
        per_step_timeout_s=float(limits.get("per_step_timeout_s", 120)),
        max_planner_calls=int(limits.get("max_planner_calls", 25)),
    )


def make_planner(cfg: dict[str, Any]) -> Any:
    planner_cfg = cfg.get("planner") or {}
    kind = str(planner_cfg.get("type") or cfg.get("planner_type") or "mock")
    if kind == "codex":
        return CodexExecPlanner(
            CodexExecConfig(
                binary=str(planner_cfg.get("binary", "codex")),
                model=str(planner_cfg.get("model", "gpt-5.6-luna")),
                reasoning_effort=str(planner_cfg.get("reasoning_effort", "medium")),
                timeout_s=float(planner_cfg.get("timeout_s", 300)),
                scratch_parent=planner_cfg.get("scratch_parent"),
            )
        )
    return MockPlanner()


def make_executor(cfg: dict[str, Any]) -> Any:
    exec_cfg = cfg.get("executor") or {}
    kind = str(exec_cfg.get("type") or cfg.get("executor_type") or "mock")
    if kind == "vllm":
        return VLLMExecutor(
            model=str(exec_cfg.get("model", "Qwen/Qwen3-8B")),
            base_url=str(exec_cfg.get("base_url", "http://127.0.0.1:8000")),
            lora_name=exec_cfg.get("lora_name"),
            temperature=float(exec_cfg.get("temperature", 0.0)),
            max_tokens=int(exec_cfg.get("max_tokens", 1024)),
            gpu_fraction=float(exec_cfg.get("gpu_fraction", 1.0)),
            timeout_s=float(exec_cfg.get("timeout_s", 120)),
            chat_template_kwargs=exec_cfg.get("chat_template_kwargs"),
        )
    return MockExecutor()


def make_verifier(cfg: dict[str, Any]) -> Any:
    vcfg = cfg.get("verifier") or {}
    if vcfg.get("scores"):
        return ScriptedVerifier([float(x) for x in vcfg["scores"]])
    return ConstantVerifier(float(vcfg.get("value", 0.5)))


def make_env(kind: str, experiment_name: str, cfg: dict[str, Any]) -> BaseEnv:
    if kind == "appworld":
        extra = dict(cfg.get("appworld") or {})
        return AppWorldEnv(experiment_name=experiment_name, extra_kwargs=extra)
    return MockEnv()


def system_kwargs(name: str, cfg: dict[str, Any], task_id: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if name == "fixed_k":
        kwargs["k"] = int(cfg.get("fixed_k", cfg.get("k", 5)))
    if name in ("sft_plan", "router_seq", "sidekick"):
        adapter = (cfg.get("executor") or {}).get("lora_name") or cfg.get("adapter_name")
        if adapter:
            kwargs["adapter_name"] = adapter
    if name in ("router_seq", "sidekick"):
        if "verifier_threshold" in cfg:
            kwargs["verifier_threshold"] = float(cfg["verifier_threshold"])
    if name == "oracle_escalation":
        labels = cfg.get("oracle_labels") or {}
        steps = labels.get(task_id, cfg.get("oracle_steps") or [])
        kwargs["oracle_steps"] = [int(s) for s in steps]
    return kwargs


def run_single(job: dict[str, Any]) -> dict[str, Any]:
    out = Path(job["out"])
    run_id = job["run_id"]
    cfg = job["config"]
    prices = PriceSchedule.load(job["prices_path"])
    ledger = CostLedger(prices)
    planner = make_planner(cfg)
    executor = make_executor(cfg)
    verifier = make_verifier(cfg)
    env = make_env(job["env_kind"], job["experiment_name"], cfg)
    limits = make_limits(cfg)
    system = get_system(
        job["system"],
        planner=planner,
        executor=executor,
        verifier=verifier,
        limits=limits,
        **system_kwargs(job["system"], cfg, job["task_id"]),
    )
    log = EventLog(out, run_id)
    try:
        log.write_manifest(
            {
                "system": job["system"],
                "task_id": job["task_id"],
                "seed": job["seed"],
                "env": job["env_kind"],
                "campaign_id": job["campaign_id"],
                "experiment_name": job["experiment_name"],
            }
        )
        result = system.run(env, job["task_id"], job["seed"], log, ledger)
        dumped = result.model_dump()
        dest = result_path(out, run_id)
        dest.write_text(json.dumps(dumped, sort_keys=True) + "\n", encoding="utf-8")
        return dumped
    finally:
        log.close()
        closer = getattr(planner, "close", None)
        if callable(closer):
            closer()
        closer = getattr(executor, "close", None)
        if callable(closer):
            closer()


def _mp_worker(job: dict[str, Any]) -> dict[str, Any]:
    return run_single(job)


def write_combined(out: Path, campaign_id: str) -> Path:
    dest_dir = out / "results" / campaign_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "runs.jsonl"
    root = out / campaign_id
    lines: list[str] = []
    if root.exists():
        for path in sorted(root.rglob("result.json")):
            text = path.read_text(encoding="utf-8").strip()
            if text:
                lines.append(text)
    dest.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
    return dest


def run_campaign(
    *,
    system: str,
    split: str,
    tasks: int,
    seeds: list[int],
    out: str | Path,
    config: dict[str, Any] | None = None,
    workers: int = 8,
    env_kind: str | None = None,
    campaign_id: str | None = None,
) -> dict[str, Any]:
    cfg = dict(config or {})
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cid = campaign_id or cfg.get("campaign_id") or f"run_{_utc_stamp()}"
    kind = env_kind or cfg.get("env") or "mock"
    prices_path = str(cfg.get("prices") or DEFAULT_PRICES)
    if kind == "appworld":
        task_ids = appworld_task_ids(split, tasks)
    else:
        task_ids = mock_task_ids(tasks)
    jobs: list[dict[str, Any]] = []
    skipped = 0
    for task_id in task_ids:
        for seed in seeds:
            run_id = make_run_id(cid, system, seed, task_id)
            if result_path(out_dir, run_id).exists():
                skipped += 1
                continue
            jobs.append(
                {
                    "out": str(out_dir),
                    "run_id": run_id,
                    "system": system,
                    "task_id": task_id,
                    "seed": seed,
                    "config": cfg,
                    "prices_path": prices_path,
                    "env_kind": kind,
                    "campaign_id": cid,
                    "experiment_name": f"{cid}/{system}/{seed}/{task_id}",
                }
            )
    n_workers = max(1, int(workers))
    results: list[dict[str, Any]] = []
    if jobs:
        if n_workers <= 1 or len(jobs) == 1:
            results = [_mp_worker(job) for job in jobs]
        else:
            ctx = multiprocessing.get_context("fork")
            with ctx.Pool(min(n_workers, len(jobs))) as pool:
                results = list(pool.imap_unordered(_mp_worker, jobs))
    combined = write_combined(out_dir, cid)
    return {
        "campaign_id": cid,
        "n_jobs": len(jobs),
        "n_skipped": skipped,
        "n_finished": len(results),
        "combined": str(combined),
        "results": results,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sidekick.runner")
    parser.add_argument("--system", required=True, choices=list(SYSTEM_NAMES))
    parser.add_argument("--split", default="dev")
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--seeds", default="1")
    parser.add_argument("--out", required=True)
    parser.add_argument("--config")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--env", choices=["mock", "appworld"])
    parser.add_argument("--campaign-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    summary = run_campaign(
        system=args.system,
        split=args.split,
        tasks=args.tasks,
        seeds=parse_seeds(args.seeds),
        out=args.out,
        config=cfg,
        workers=args.workers,
        env_kind=args.env,
        campaign_id=args.campaign_id,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
