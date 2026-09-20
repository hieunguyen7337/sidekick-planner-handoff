#!/usr/bin/env python3
"""R1 guards for scripts/pbs/hj8_frontier.pbs + SIDEKICK_VLLM_BASE_URL.

Not a pytest module. pyproject.toml testpaths is tests/ only.

Each case must be *seen to fire*. Zero planner calls. Does not qsub.
Does not write under /scratch/.../results/. Does not edit test_b1_pilot_guards.py.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path("/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15")
PBS = REPO / "scripts/pbs/hj8_frontier.pbs"
PY = Path(os.environ.get("PY", "/scratch/n12194778/sidekick/env/bin/python"))
CASES = REPO / "campaign/workers/scratch_A20/cases_r1_hj8.txt"


def write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def make_stub_dir(
    tmp: Path,
    *,
    curl_body: str,
    ss_pid: str | None = None,
    ps_pgid: str | None = None,
) -> Path:
    bindir = tmp / "bin"
    bindir.mkdir()
    write_exec(
        bindir / "curl",
        "#!/bin/bash\n"
        "printf '%s\\n' '" + curl_body.replace("'", "'\\''") + "'\n"
        "exit 0\n",
    )
    if ss_pid is not None:
        write_exec(
            bindir / "ss",
            "#!/bin/bash\n"
            "port=\"${VLLM_PORT:-21002}\"\n"
            f"pid=\"{ss_pid}\"\n"
            'echo "State Recv-Q Send-Q Local Address:Port Peer Address:Port Process"\n'
            'echo "LISTEN 0 2048 127.0.0.1:${port} 0.0.0.0:* users:((\\"vllm\\",pid=${pid},fd=3))"\n'
            "exit 0\n",
        )
    if ps_pgid is not None:
        write_exec(
            bindir / "ps",
            "#!/bin/bash\n"
            f"echo ' {ps_pgid}'\n"
            "exit 0\n",
        )
    return bindir


def run_pbs_selftest(case: str, stub_dir: Path | None = None, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HJ8_GUARD_SELFTEST"] = "1"
    env["GUARD_CASE"] = case
    env["PY"] = str(PY)
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    if stub_dir is not None:
        env["HJ8_STUB_DIR"] = str(stub_dir)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(PBS)],
        cwd=str(REPO),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )


def expect_fatal(case: str, needle: str, proc: subprocess.CompletedProcess[str]) -> str:
    out = proc.stdout
    assert proc.returncode != 0, f"{case}: guard did not abort (rc={proc.returncode})\n{out}"
    assert "FATAL" in out, f"{case}: no FATAL in output\n{out}"
    assert needle in out, f"{case}: missing {needle!r}\n{out}"
    print(f"GREP_NEEDLE case={case} needle={needle!r} count={out.count(needle)}")
    return out


def test_bash_n() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(PBS)],
        cwd=str(REPO),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 0, f"bash -n failed\n{proc.stdout}"


def test_source_contract() -> list[str]:
    text = PBS.read_text(encoding="utf-8")
    assert "8000" not in text, "literal 8000 remains in hj8_frontier.pbs"
    assert "pkill" not in text, "pkill remains in hj8_frontier.pbs"
    assert "setsid" in text
    assert 'trap kill_vllm EXIT' in text
    assert "#PBS -l walltime=10:00:00" in text
    assert "VLLM_PORT=$(( 20000 + jobnum % 20000 ))" in text
    assert "SIDEKICK_VLLM_BASE_URL" in text
    n_8000 = text.count("8000")
    n_pkill = text.count("pkill")
    print(f"GREP_SOURCE 8000_count={n_8000} pkill_count={n_pkill}")
    return ["ok source contract"]


def test_health_missing_alias() -> str:
    with tempfile.TemporaryDirectory(prefix="r1_missing_") as raw:
        stub = make_stub_dir(
            Path(raw),
            curl_body='{"object":"list","data":[{"id":"ibm-granite/granite-4.2-8b","object":"model"}]}',
        )
        proc = run_pbs_selftest("health_missing_alias", stub_dir=stub)
        return expect_fatal(
            "health_missing_alias",
            "missing LoRA alias(es): sft_b_plus",
            proc,
        )


def test_health_foreign_pgid() -> str:
    with tempfile.TemporaryDirectory(prefix="r1_foreign_") as raw:
        stub = make_stub_dir(
            Path(raw),
            curl_body='{"object":"list","data":[{"id":"ibm-granite/granite-4.2-8b"},{"id":"sft_b_plus"}]}',
            ss_pid="4242",
            ps_pgid="99999",
        )
        proc = run_pbs_selftest(
            "health_foreign_pgid",
            stub_dir=stub,
            extra_env={"VLLM_PID": "11111"},
        )
        return expect_fatal(
            "health_foreign_pgid",
            "held by pid=4242 pgid=99999, expected pgid=11111",
            proc,
        )


def test_arms_unknown_stem() -> str:
    proc = run_pbs_selftest(
        "arms_unknown",
        extra_env={"ARMS_STEM": "not_a_real_stem"},
    )
    out = expect_fatal("arms_unknown_stem", "unknown ARMS stem not_a_real_stem", proc)
    assert "valid stems:" in out, f"arms_unknown_stem: missing valid stems list\n{out}"
    assert "hj8_fixed_k_3" in out, f"arms_unknown_stem: missing a known stem in the list\n{out}"
    return out


def test_env_base_url() -> str:
    env = os.environ.copy()
    env["SIDEKICK_VLLM_BASE_URL"] = "http://127.0.0.1:27123"
    env["PYTHONPATH"] = f"{REPO / 'src'}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    proc = subprocess.run(
        [
            str(PY),
            "-c",
            "from sidekick.runner import make_executor\n"
            "ex = make_executor({'executor': {'type': 'vllm', 'model': 'm',"
            " 'base_url': 'http://127.0.0.1:8000'}})\n"
            "print(f'executor_base_url={ex.base_url}')\n"
            "assert ex.base_url.rstrip('/') == 'http://127.0.0.1:27123'\n"
            "print('GUARD_FIRED env_base_url')\n",
        ],
        cwd=str(REPO),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )
    out = proc.stdout
    assert proc.returncode == 0, f"env_base_url: rc={proc.returncode}\n{out}"
    assert "GUARD_FIRED env_base_url" in out, out
    assert "http://127.0.0.1:27123" in out, out
    print(f"GREP_NEEDLE case=env_base_url needle='GUARD_FIRED env_base_url' count={out.count('GUARD_FIRED env_base_url')}")
    return out


def test_cases_file_lists_four() -> None:
    names = [ln.strip() for ln in CASES.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert names == [
        "health_missing_alias",
        "health_foreign_pgid",
        "env_base_url",
        "arms_unknown_stem",
    ], names


def main() -> int:
    print(f"python={sys.version.replace(chr(10), ' ')}")
    print(f"pbs={PBS}")
    print(f"cases={CASES}")
    failures: list[str] = []
    tests = [
        ("bash_n", test_bash_n),
        ("source_contract", test_source_contract),
        ("cases_file", test_cases_file_lists_four),
        ("health_missing_alias", test_health_missing_alias),
        ("health_foreign_pgid", test_health_foreign_pgid),
        ("arms_unknown_stem", test_arms_unknown_stem),
        ("env_base_url", test_env_base_url),
    ]
    for name, fn in tests:
        try:
            result = fn()
            print(f"PASS {name}")
            if isinstance(result, str):
                for line in result.strip().splitlines():
                    print(f"  | {line}")
        except AssertionError as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
    print(f"n_pass={len(tests) - len(failures)} n_fail={len(failures)}")
    if failures:
        print("FAILURES")
        for item in failures:
            print(item)
        return 1
    print("ALL_GUARDS_FIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
