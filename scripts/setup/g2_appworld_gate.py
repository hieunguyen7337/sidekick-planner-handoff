#!/usr/bin/env python3
"""G2 AppWorld feasibility gate. CPU-only; run inside a PBS job."""
from __future__ import annotations

import json
import os
import resource
import sys
import time
import traceback
from multiprocessing import get_context
from pathlib import Path
from typing import Any

SCRATCH = Path(os.environ.get("SIDEKICK_SCRATCH", "/scratch/n12194778/sidekick"))
APPWORLD_ROOT = os.environ.get("APPWORLD_ROOT", str(SCRATCH / "appworld"))
LOGDIR = SCRATCH / "logs"
OUT = LOGDIR / "g2_appworld_gate.json"
os.environ["APPWORLD_ROOT"] = APPWORLD_ROOT
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")


def _now() -> float:
    return time.perf_counter()


def jsonable(obj: Any, depth: int = 0) -> Any:
    if depth > 6:
        return f"<maxdepth {type(obj).__name__}>"
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [jsonable(x, depth + 1) for x in obj[:50]]
    if isinstance(obj, dict):
        return {str(k): jsonable(v, depth + 1) for k, v in list(obj.items())[:80]}
    if hasattr(obj, "to_dict"):
        try:
            return jsonable(obj.to_dict(), depth + 1)
        except Exception as e:  # noqa: BLE001
            return {"to_dict_error": repr(e), "type": type(obj).__name__}
    if hasattr(obj, "__dict__") and not type(obj).__name__.startswith("App"):
        try:
            return {
                "type": type(obj).__name__,
                "attrs": {
                    k: jsonable(v, depth + 1)
                    for k, v in list(vars(obj).items())[:40]
                    if not k.startswith("_")
                },
            }
        except Exception:
            pass
    return {"type": type(obj).__name__, "repr": repr(obj)[:2000]}


def rss_hwm_kb() -> int:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])
    except OSError:
        pass
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def dump_docs_text(docs: Any) -> tuple[str, str | None]:
    raw = None
    compressed = None
    try:
        from appworld.common.io import dump_yaml  # type: ignore

        raw = dump_yaml(docs)
    except Exception:
        try:
            raw = json.dumps(docs, default=str)
        except Exception:
            raw = str(docs)
    if hasattr(docs, "compress_parameters"):
        try:
            cdocs = docs.compress_parameters()
            try:
                from appworld.common.io import dump_yaml  # type: ignore

                compressed = dump_yaml(cdocs)
            except Exception:
                compressed = json.dumps(cdocs, default=str)
        except Exception as e:  # noqa: BLE001
            compressed = f"<compress_parameters failed: {e!r}>"
    return raw, compressed


def run_ground_truth(world: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {"method": None, "execute_output": None, "error": None}
    gt = getattr(world.task, "ground_truth", None)
    rec["ground_truth_type"] = type(gt).__name__ if gt is not None else None
    rec["ground_truth_dir"] = (
        [n for n in dir(gt) if not n.startswith("_")] if gt is not None else None
    )
    if gt is None:
        rec["method"] = "print(1)_no_gt"
        rec["execute_output"] = world.execute("print(1)")
        return rec
    code = getattr(gt, "compiled_solution_code", None)
    if isinstance(code, str) and code.strip():
        rec["method"] = "compiled_solution_code+solution(apis, requester)"
        try:
            rec["execute_output"] = world.execute(code + "\nsolution(apis, requester)")
            return rec
        except Exception:
            rec["compiled_solution_code_error"] = traceback.format_exc()[-3000:]
    mod = getattr(gt, "compiled_solution_module", None)
    if mod is not None:
        rec["compiled_solution_module_type"] = type(mod).__name__
        src = getattr(mod, "solution", None)
        try:
            import inspect

            if src is not None:
                rec["method"] = "compiled_solution_module.solution source"
                rec["execute_output"] = world.execute(
                    inspect.getsource(src) + "\nsolution(apis, requester)"
                )
                return rec
        except Exception:
            rec["compiled_solution_module_error"] = traceback.format_exc()[-3000:]
    rec["method"] = "print(1)_fallback"
    rec["execute_output"] = world.execute("print(1)")
    return rec


def parallel_worker(payload: tuple[str, str]) -> dict[str, Any]:
    task_id, experiment_name = payload
    os.environ["APPWORLD_ROOT"] = APPWORLD_ROOT
    t0 = _now()
    rec: dict[str, Any] = {
        "task_id": task_id,
        "experiment_name": experiment_name,
        "ok": False,
        "pid": os.getpid(),
    }
    try:
        from appworld import AppWorld

        with AppWorld(
            task_id=task_id,
            experiment_name=experiment_name,
            ground_truth_mode="full",
            raise_on_failure=False,
        ) as world:
            rec["load_s"] = _now() - t0
            outs = []
            exec_times = []
            for i in range(3):
                et0 = _now()
                outs.append(str(world.execute("print(1)"))[:200])
                exec_times.append(_now() - et0)
            rec["execute_times_s"] = exec_times
            rec["execute_mean_s"] = sum(exec_times) / len(exec_times)
            rec["execute_outs"] = outs
            ev = world.evaluate()
            rec["evaluate"] = jsonable(ev)
            rec["task_completed"] = jsonable(world.task_completed())
            rec["ok"] = True
    except Exception:
        rec["error"] = traceback.format_exc()[-4000:]
    rec["rss_hwm_kb"] = rss_hwm_kb()
    rec["wall_s"] = _now() - t0
    return rec


def main() -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    Path(APPWORLD_ROOT).mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "host": os.uname().nodename,
        "job": os.environ.get("PBS_JOBID"),
        "appworld_root": APPWORLD_ROOT,
        "failures": [],
    }

    def fail(step: str, exc: BaseException) -> None:
        report["failures"].append(
            {"step": step, "error": traceback.format_exc()[-5000:], "repr": repr(exc)}
        )
        print(f"[g2] FAIL {step}: {exc}", file=sys.stderr)

    venv_bin = Path(sys.executable).parent
    env = os.environ.copy()
    env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
    env["APPWORLD_ROOT"] = APPWORLD_ROOT

    import subprocess

    def materialize_lfs_bundles() -> dict[str, Any]:
        """uv/pip git+https leaves Git LFS pointer files; appworld install needs the blobs."""
        rec: dict[str, Any] = {"files": {}}
        try:
            import appworld
            import httpx
        except Exception as e:  # noqa: BLE001
            rec["error"] = repr(e)
            return rec
        commit = os.environ.get(
            "APPWORLD_COMMIT", "42b5bcf3cd334fee33f0c37c02070a9f5807add5"
        )
        src = Path(appworld.__file__).resolve().parent / ".source"
        src.mkdir(parents=True, exist_ok=True)
        mapping = {
            "apps.bundle": "src/appworld/.source/apps.bundle",
            "tests.bundle": "src/appworld/.source/tests.bundle",
        }
        for name, repo_path in mapping.items():
            dest = src / name
            head = dest.read_bytes()[:80] if dest.exists() else b""
            is_ptr = head.startswith(b"version https://git-lfs")
            rec["files"][name] = {
                "path": str(dest),
                "exists": dest.exists(),
                "size_before": dest.stat().st_size if dest.exists() else 0,
                "was_lfs_pointer": is_ptr,
            }
            if dest.exists() and not is_ptr and dest.stat().st_size > 1000:
                rec["files"][name]["skipped"] = "already_materialized"
                continue
            urls = [
                f"https://media.githubusercontent.com/media/StonyBrookNLP/appworld/{commit}/{repo_path}",
                f"https://github.com/StonyBrookNLP/appworld/raw/{commit}/{repo_path}",
            ]
            ok = False
            last_err = None
            for url in urls:
                try:
                    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
                        r = client.get(url)
                        rec["files"][name].setdefault("attempts", []).append(
                            {"url": url, "status": r.status_code, "nbytes": len(r.content)}
                        )
                        if r.status_code == 200 and not r.content.startswith(
                            b"version https://git-lfs"
                        ) and len(r.content) > 1000:
                            dest.write_bytes(r.content)
                            rec["files"][name]["size_after"] = dest.stat().st_size
                            rec["files"][name]["fetched_from"] = url
                            ok = True
                            break
                        last_err = f"status={r.status_code} nbytes={len(r.content)} head={r.content[:60]!r}"
                except Exception as e:  # noqa: BLE001
                    last_err = repr(e)
                    rec["files"][name].setdefault("attempts", []).append(
                        {"url": url, "error": last_err}
                    )
            if not ok:
                rec["files"][name]["error"] = last_err
        return rec

    report["lfs_bundles"] = materialize_lfs_bundles()
    print("[g2] lfs_bundles", json.dumps(report["lfs_bundles"], indent=2)[:4000], flush=True)

    def run_cmd(step: str, args: list[str], timeout: int) -> dict[str, Any]:
        print(f"[g2] running {step}: {' '.join(args)}", flush=True)
        p = subprocess.run(
            args,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        rec = {
            "cmd": args,
            "returncode": p.returncode,
            "stdout": p.stdout[-20000:],
            "stderr": p.stderr[-20000:],
        }
        report[step] = rec
        print(p.stdout)
        print(p.stderr, file=sys.stderr)
        if p.returncode != 0:
            report["failures"].append({"step": step, "returncode": p.returncode})
        return rec

    run_cmd("appworld_install", [str(venv_bin / "appworld"), "install"], 600)
    run_cmd(
        "appworld_download_data",
        [
            str(venv_bin / "appworld"),
            "download",
            "data",
            "--root",
            APPWORLD_ROOT,
            "--with-setup",
        ],
        600,
    )
    run_cmd(
        "appworld_verify_tasks",
        [
            str(venv_bin / "appworld"),
            "verify",
            "tasks",
            "--root",
            APPWORLD_ROOT,
            "--with-setup",
        ],
        900,
    )

    try:
        from appworld import AppWorld, load_task_ids
    except Exception as e:  # noqa: BLE001
        fail("import_appworld", e)
        OUT.write_text(json.dumps(report, indent=2, default=str))
        return 1

    splits = {}
    for name in ("train", "dev", "test_normal", "test_challenge"):
        try:
            ids = list(load_task_ids(name))
            splits[name] = {"n": len(ids), "head": ids[:5]}
        except Exception as e:  # noqa: BLE001
            fail(f"load_task_ids:{name}", e)
            splits[name] = {"n": None, "error": repr(e)}
    report["split_sizes"] = splits
    report["split_sizes_expected"] = {
        "train": 105,
        "dev": 60,
        "test_normal": 168,
        "test_challenge": 417,
    }
    print("[g2] split sizes", json.dumps(splits, indent=2), flush=True)

    train_ids = splits.get("train", {}).get("head") or []
    if not train_ids:
        try:
            train_ids = list(load_task_ids("train"))[:8]
        except Exception as e:  # noqa: BLE001
            fail("train_ids", e)
            OUT.write_text(json.dumps(report, indent=2, default=str))
            return 1
    all_train = list(load_task_ids("train"))
    task_id = all_train[0]
    report["probe_task_id"] = task_id

    # first vs later world load + execute latency
    try:
        t0 = _now()
        world = AppWorld(
            task_id=task_id,
            experiment_name="g2_probe",
            ground_truth_mode="full",
            raise_on_failure=False,
        )
        first_load = _now() - t0
        instruction = world.task.instruction
        report["instruction_head"] = str(instruction)[:500]
        gt_rec = run_ground_truth(world)
        report["ground_truth_run"] = jsonable(gt_rec)
        ev = world.evaluate()
        report["evaluate_type"] = type(ev).__name__
        report["evaluate_dir"] = [n for n in dir(ev) if not n.startswith("_")]
        try:
            report["evaluate_to_dict"] = ev.to_dict()
        except Exception as e:  # noqa: BLE001
            report["evaluate_to_dict_error"] = repr(e)
            report["evaluate_repr"] = repr(ev)[:4000]
        try:
            report["evaluate_report"] = ev.report(print_it=False, colorize=False)
        except TypeError:
            try:
                report["evaluate_report"] = ev.report()
            except Exception as e:  # noqa: BLE001
                report["evaluate_report_error"] = repr(e)
        except Exception as e:  # noqa: BLE001
            report["evaluate_report_error"] = repr(e)
        try:
            report["task_completed"] = jsonable(world.task_completed())
        except Exception as e:  # noqa: BLE001
            report["task_completed_error"] = repr(e)

        docs = getattr(world.task, "api_docs", None)
        raw, compressed = dump_docs_text(docs)
        report["api_docs"] = {
            "raw_chars": len(raw) if raw else None,
            "raw_tokens_est": (len(raw) / 4.0) if raw else None,
            "compressed_chars": len(compressed) if isinstance(compressed, str) else None,
            "compressed_tokens_est": (len(compressed) / 4.0)
            if isinstance(compressed, str)
            else None,
            "compress_note": compressed[:300]
            if isinstance(compressed, str) and compressed.startswith("<")
            else None,
            "has_compress_parameters": hasattr(docs, "compress_parameters"),
        }
        (LOGDIR / "g2_api_docs_raw.txt").write_text(raw or "")
        if isinstance(compressed, str) and not compressed.startswith("<"):
            (LOGDIR / "g2_api_docs_compressed.txt").write_text(compressed)

        exec_times = []
        for _ in range(20):
            et0 = _now()
            world.execute("print(1)")
            exec_times.append(_now() - et0)
        report["execute_print1"] = {
            "n": 20,
            "mean_s": sum(exec_times) / 20,
            "min_s": min(exec_times),
            "max_s": max(exec_times),
            "times_s": exec_times,
        }
        world.close()

        t1 = _now()
        world2 = AppWorld(
            task_id=all_train[1] if len(all_train) > 1 else task_id,
            experiment_name="g2_probe_second",
            ground_truth_mode="full",
            raise_on_failure=False,
        )
        later_load = _now() - t1
        world2.close()
        report["load_times_s"] = {
            "first_world": first_load,
            "later_world": later_load,
        }
        print("[g2] load first", first_load, "later", later_load, flush=True)
        print("[g2] execute mean", report["execute_print1"]["mean_s"], flush=True)
        print("[g2] evaluate_to_dict", json.dumps(report.get("evaluate_to_dict"), default=str)[:4000], flush=True)
    except Exception as e:  # noqa: BLE001
        fail("single_task_probe", e)

    # 8 worlds in 8 processes
    par_ids = all_train[:8]
    while len(par_ids) < 8 and all_train:
        par_ids.append(all_train[len(par_ids) % len(all_train)])
    payloads = [(tid, f"g2_par/roll_out_{k}") for k, tid in enumerate(par_ids)]
    report["parallel"] = {"n": 8, "payloads": payloads}
    ctx = get_context("spawn")
    tpar = _now()
    try:
        with ctx.Pool(processes=8) as pool:
            results = pool.map(parallel_worker, payloads)
        report["parallel"]["wall_s"] = _now() - tpar
        report["parallel"]["results"] = results
        report["parallel"]["all_ok"] = all(r.get("ok") for r in results)
        rss = [r.get("rss_hwm_kb") or 0 for r in results]
        report["parallel"]["peak_rss_kb_per_process"] = rss
        report["parallel"]["peak_rss_kb_max"] = max(rss) if rss else None
        max_rss_kb = max(rss) if rss else 2_000_000
        # 32-CPU node: 1 world/process; memory often binds first.
        # Assume a 32-CPU / 256 GB compute node as a conservative Aqua CPU node lower bound.
        node_ram_kb = 256 * 1024 * 1024
        mem_bound = max(1, int(0.7 * node_ram_kb / max(max_rss_kb, 1)))
        report["parallel"]["max_safe_pool_32cpu"] = {
            "cpu_bound": 32,
            "mem_bound_at_256gb_70pct": mem_bound,
            "recommended": min(32, mem_bound),
            "note": "One world per process (freezegun). Recommended = min(32 CPUs, 70% of 256 GB / peak RSS).",
        }
        print("[g2] parallel all_ok", report["parallel"]["all_ok"], "wall", report["parallel"]["wall_s"], flush=True)
    except Exception as e:  # noqa: BLE001
        fail("parallel", e)

    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(f"[g2] wrote {OUT}", flush=True)
    nfail = len(report["failures"])
    print(f"[g2] failures={nfail}", flush=True)
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
