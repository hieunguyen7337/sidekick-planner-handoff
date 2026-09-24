"""The two planning-control dev arms (brief 20260924_ctrl_planning_controls): configs and wrapper.

WTP (wrong-task plan) and SP (self-plan) are the sft_plan floor with one thing moved each. As in
test_dev_arms, the keys that may differ from the source are stated here, not read from the
headers. The wrapper cases take the HJ12_GUARD_SELFTEST path of hj12_live.pbs: nothing is served
and nothing runs; the served-model probe reads a stub /v1/models.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from _pbs_arrays import read_bash_array
from sidekick.agents.planner import build_plan_prompt
from sidekick.agents.vllm_planner import PLAN_RESPONSE_FORMAT, VllmPlanner
from sidekick.provenance import planner_provenance
from sidekick.runner import make_executor, make_planner

REPO = Path(__file__).resolve().parents[2]
CONFIGS = REPO / "configs"
HJ12_LIVE = REPO / "scripts" / "pbs" / "hj12_live.pbs"
sys.path.insert(0, str(REPO / "scripts" / "setup"))
from verify_configs import validate_prompt_budget  # noqa: E402

DATE = "20260924"
ALIAS = "sft_b_plus"
SOURCE = "configs/hj8_sft_plan_bplus.yaml"
WTP, SP = "dev_sft_plan_wrongtask_bplus", "dev_sft_plan_selfplan_bplus"
STEMS = [WTP, SP]
REGISTRY: dict[str, tuple[str, ...]] = {
    WTP: ("campaign_id", "planner.packet_task_map"),
    SP: (
        "campaign_id", "planner.type", "planner.model", "planner.base_url", "planner.temperature",
        "planner.max_tokens", "planner.chat_template_kwargs.enable_thinking", "planner.reasoning_effort",
        "planner.scratch_parent", "planner.packet_source", "planner.packet_system", "planner.on_missing",
    ),
}
_MISSING = object()
SOURCE_RE = re.compile(r"^# Source: (configs/\S+\.yaml)(?:\s|$)")
DIFFERS_RE = re.compile(r"^# Differs from source in: (.+)$")


def _load(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), path
    return data


def _cfg(stem: str) -> dict:
    return _load(CONFIGS / f"{stem}.yaml")


def _flatten(value: object, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict) and value:
        out: dict[str, object] = {}
        for key, child in value.items():
            out.update(_flatten(child, f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value}


def _diff(a: dict, b: dict) -> set[str]:
    fa, fb = _flatten(a), _flatten(b)
    return {k for k in fa.keys() | fb.keys() if fa.get(k, _MISSING) != fb.get(k, _MISSING)}


def _header(stem: str) -> list[str]:
    header = []
    for line in (CONFIGS / f"{stem}.yaml").read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        header.append(line)
    return header


# --- configs ------------------------------------------------------------------------------------


@pytest.mark.parametrize("stem", STEMS)
def test_differs_from_the_floor_only_in_the_declared_keys(stem: str):
    header = _header(stem)
    sources = [m.group(1) for m in map(SOURCE_RE.match, header) if m]
    differs = [m.group(1) for m in map(DIFFERS_RE.match, header) if m]
    assert sources == [SOURCE]
    assert len(differs) == 1 and {f.strip() for f in differs[0].split(",")} == set(REGISTRY[stem])
    # Equality, not subset: a declared key that no longer differs is a stale declaration.
    assert _diff(_load(REPO / SOURCE), _cfg(stem)) == set(REGISTRY[stem])


@pytest.mark.parametrize("stem", STEMS)
def test_named_after_the_stem_dev_only_and_not_j10(stem: str):
    cfg = _cfg(stem)
    assert not stem.startswith("j10_") and cfg["campaign_id"] == f"{stem}_{DATE}"
    text = " ".join(line.lstrip("#").strip() for line in _header(stem))
    assert "EXPLORATORY, DEV ONLY" in text and "20260924_ctrl_planning_controls.md" in text
    assert "split" not in cfg and cfg["env"] == "appworld"
    assert validate_prompt_budget(cfg, f"configs/{stem}.yaml") == []


@pytest.mark.parametrize("stem", STEMS)
def test_submit_line_names_the_stem_and_date(stem: str):
    lines = [line[4:] for line in _header(stem) if line.startswith("#   ")]
    assert len(lines) == 1
    assert lines[0].startswith(f'qsub -v ARMS="{stem}",DATE={DATE}')
    assert lines[0].endswith("/scripts/pbs/hj12_live.pbs")


def test_wtp_changes_only_which_packet_is_read():
    planner = _cfg(WTP)["planner"]
    assert planner["packet_task_map"] == "configs/dev_wrongtask_plan_map.json"
    assert (REPO / planner["packet_task_map"]).is_file()
    assert (planner["type"], planner["model"], planner["on_missing"]) == ("codex", "gpt-5.6-luna", "fail")


def test_sp_plans_with_the_executors_own_alias_on_the_executors_server():
    cfg = _cfg(SP)
    planner, executor = cfg["planner"], cfg["executor"]
    assert planner["type"] == "vllm"
    assert planner["model"] == executor["lora_name"] == ALIAS
    assert planner["base_url"] == executor["base_url"] + "/v1"
    assert (planner["temperature"], planner["max_tokens"]) == (0.7, 2048)
    assert planner["chat_template_kwargs"] == {"enable_thinking": False}
    assert not any(k.startswith("packet_") for k in planner) and "on_missing" not in planner


# --- the self-plan planner, as built ------------------------------------------------------------


class _Response:
    status_code = 200
    text = ""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _Client:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict) -> _Response:  # noqa: A002 - mirrors httpx
        self.calls.append((url, json))
        return _Response({"choices": [{"message": {"content": self.reply}}], "usage": {}})


PACKET = ('{"packet_id": "p", "task_id": "t_1", "goal": "g", "plan_steps": [], "constraints": [], '
          '"success_criteria": [], "forbidden_actions": [], "context_digest": "", "created_at": "c"}')


def test_sp_planner_requests_carry_the_alias_to_the_executors_endpoint(monkeypatch):
    server = "http://127.0.0.1:21003"
    monkeypatch.setenv("SIDEKICK_VLLM_BASE_URL", server)
    monkeypatch.setenv("SIDEKICK_PLANNER_BASE_URL", server + "/v1")  # what hj12_live exports
    cfg = _cfg(SP)
    planner, executor = make_planner(cfg, seed=1), make_executor(cfg)
    assert type(planner) is VllmPlanner
    client = _Client(PACKET)
    planner._http = client
    planner.plan("t_1", "the goal", "the api docs")
    ((url, payload),) = client.calls
    assert payload["model"] == ALIAS == executor.lora_name
    # One server for both roles: the planner posts where the executor posts.
    assert url == executor._chat_url() == server + "/v1/chat/completions"
    # The plan prompt is the one luna's HJ-1 plans were made with, under the same packet schema.
    assert payload["messages"] == [{"role": "user", "content": build_plan_prompt("t_1", "the goal", "the api docs")}]
    assert payload["response_format"] == PLAN_RESPONSE_FORMAT
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}


def test_sp_provenance_records_the_alias_as_the_requested_planner():
    got = planner_provenance(_cfg(SP))
    assert (got["planner_type"], got["planner_model_requested"], got["planner_cli_version"]) == ("vllm", ALIAS, None)


# --- hj12_live.pbs: registry, routing, refusal, served-model probe ----------------------------


def _selftest(case: str, **extra: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items()
           if k not in ("ARMS", "ARMSET", "FULL_SEEDS", "DATE", "ALIAS_SFT_B_PLUS",
                        "SIDEKICK_VLLM_BASE_URL", "SIDEKICK_PLANNER_BASE_URL")}
    env.update(HJ12_GUARD_SELFTEST="1", GUARD_CASE=case, DATE=DATE, PY=sys.executable,
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", **extra)
    return subprocess.run(["timeout", "60", "bash", str(HJ12_LIVE)], cwd=str(REPO), env=env,
                          text=True, capture_output=True)


def _rows(proc: subprocess.CompletedProcess[str]) -> list[list[str]]:
    return [line.split("|") for line in proc.stdout.splitlines() if line.count("|") == 2]


def test_control_arms_is_the_two_sft_plan_arms():
    assert read_bash_array(HJ12_LIVE, "CONTROL_ARMS") == [
        f"sft_plan|${{REPO}}/configs/{stem}.yaml|{stem}" for stem in STEMS
    ]


def test_arms_selects_both_control_stems():
    proc = _selftest("arms_select", ARMS=" ".join(STEMS))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows = _rows(proc)
    assert [row[2] for row in rows] == STEMS
    for system, cfg, stem in rows:
        assert system == "sft_plan"
        assert Path(cfg).name == f"{stem}.yaml" and (CONFIGS / Path(cfg).name).is_file()


@pytest.mark.parametrize("armset", ["live", "all"])
def test_no_armset_selects_a_control_stem(armset: str):
    proc = _selftest("arms_select", ARMSET=armset)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    stems = [row[2] for row in _rows(proc)]
    assert stems and not set(stems) & set(STEMS)


def _route(cfg: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    return _selftest("planner_route", GUARD_CFG=str(cfg), SIDEKICK_VLLM_BASE_URL="http://127.0.0.1:21003", **extra)


def test_sp_routes_to_the_executors_server_and_gates_on_the_alias():
    proc = _route(CONFIGS / f"{SP}.yaml")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "self-plan route" in proc.stdout
    assert ("[hj12] selftest: route=self planner_base_url=http://127.0.0.1:21003/v1 "
            f"expect_model={ALIAS}") in proc.stdout


def test_wtp_stays_on_the_hosted_route():
    proc = _route(CONFIGS / f"{WTP}.yaml")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "[hj12] selftest: route=hosted planner_base_url=unset expect_model=gpt-5.6-luna" in proc.stdout


def _variant(tmp_path: Path, old: str, new: str) -> Path:
    text = (CONFIGS / f"{SP}.yaml").read_text(encoding="utf-8")
    assert old in text
    dest = tmp_path / f"{SP}.yaml"
    dest.write_text(text.replace(old, new, 1), encoding="utf-8")
    return dest


@pytest.mark.parametrize(
    "old, new",
    [
        ("  model: sft_b_plus\n", "  model: Qwen/Qwen3-8B\n"),  # a second model: nothing serves it
        ("    enable_thinking: false\nexecutor:",
         "    enable_thinking: false\n  packet_source: /tmp/x\nexecutor:"),  # a replay, not a self-plan
        ("  lora_name: sft_b_plus  #", "  lora_name: sft_other  #"),  # planner is not the executor
    ],
)
def test_any_other_vllm_planner_is_refused(tmp_path: Path, old: str, new: str):
    proc = _route(_variant(tmp_path, old, new))
    assert proc.returncode != 0
    assert "FATAL" in proc.stdout and "serves no second model" in proc.stdout
    assert "selftest: route=" not in proc.stdout


def test_the_alias_must_be_the_one_this_job_serves():
    proc = _route(CONFIGS / f"{SP}.yaml", ALIAS_SFT_B_PLUS="sft_b_plus_other")
    assert proc.returncode != 0 and "serves no second model" in proc.stdout


def _stub_dir(tmp_path: Path, served: list[str]) -> Path:
    stub = tmp_path / "stub"
    stub.mkdir()
    body = '{"object": "list", "data": [' + ", ".join(f'{{"id": "{i}"}}' for i in served) + "]}"
    (stub / "curl").write_text(f"#!/bin/bash\nprintf '%s' '{body}'\n", encoding="utf-8")
    (stub / "ss").write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    for exe in stub.iterdir():
        exe.chmod(0o755)
    return stub


def test_the_served_model_probe_accepts_the_alias(tmp_path: Path):
    stub = _stub_dir(tmp_path, ["ibm-granite/granite-4.2-8b", ALIAS])
    proc = _selftest("identity_probe", HJ8_STUB_DIR=str(stub))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"all LoRA aliases present in /v1/models ({ALIAS})" in proc.stdout
    assert "selftest: identity_probe passed" in proc.stdout


def test_the_served_model_probe_refuses_a_server_without_the_alias(tmp_path: Path):
    stub = _stub_dir(tmp_path, ["ibm-granite/granite-4.2-8b"])
    proc = _selftest("identity_probe", HJ8_STUB_DIR=str(stub))
    assert proc.returncode == 1
    assert f"missing LoRA alias(es): {ALIAS}" in proc.stdout
