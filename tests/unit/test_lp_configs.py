"""LP arm configs: rendered from their hosted sources, differing only where declared, each driving
the locally served planner of its LP ceiling -- plus the refusals and the crash-only resume purge
in scripts/pbs/lp_live.pbs, and the smoke gate and campaign id of scripts/pbs/lp1_planner_alone.pbs.

The LP arms test whether the channel result holds across planner strength. They answer that only
if each is its source with the planner swapped and nothing else moved, and only if the planner it
builds is the one the ceiling ran. Both failure modes still produce believable numbers, so both
are pinned here rather than left to review.

The PBS self-tests run on trees built under tmp_path. The one case that reads
/scratch/n12194778/sidekick/results/ only reads it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from _pbs_arrays import read_bash_array
from sidekick.agents.planner import CachedPacketPlanner
from sidekick.agents.vllm_planner import VllmPlanner
from sidekick.runner import load_config, make_executor, make_planner

REPO = Path(__file__).resolve().parents[2]
PBS = REPO / "scripts" / "pbs" / "lp_live.pbs"
LP1_PBS = REPO / "scripts" / "pbs" / "lp1_planner_alone.pbs"
RESULTS = "/scratch/n12194778/sidekick/results"
# The first LP-1 ceiling: every episode parse_error at step 0 (job 25724309). It stays on disk and
# must never again be a replay source or a campaign this repo writes into.
VOID_LP1_CEILING = "lp1_planner_alone_cap81_qwen8b_20260923"
LP1_CEILING = "lp1_planner_alone_cap81_qwen8b_v2_20260923"

# Stated here rather than read from the ceiling configs, so a ceiling edit that changes the
# planner shows up as a failing test instead of silently re-pointing twenty arms.
EXPECTED_MODEL = {"lp1": "Qwen/Qwen3-8B", "lp2": "Qwen/Qwen3.8-27B-FP8"}
LIVE_SOURCE_STEMS = (
    "hj12_takeover_fixed_k_10",
    "hj12_advise_fixed_k_10_fullctx",
    "hj13_advise_fixed_k_1_fullctx",
    "hj8_sft_plan_bplus",
)


def _module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    # @dataclass resolves string annotations through sys.modules[cls.__module__].
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


mk = _module("make_lp_configs", "scripts/setup/make_lp_configs.py")
verify_configs = _module("verify_configs", "scripts/setup/verify_configs.py")

SPECS = mk.all_specs()
LIVE = [s for s in SPECS if s.kind == "live"]
PREFIX = [s for s in SPECS if s.kind == "prefix"]


def _cfg(spec) -> dict:
    return load_config(str(REPO / spec.out))


def test_the_set_is_twenty_configs_named_after_their_sources() -> None:
    assert {s.out for s in LIVE} == {
        f"configs/lp{n}_{src}.yaml" for n in (1, 2) for src in LIVE_SOURCE_STEMS
    }
    assert {(s.out, s.source) for s in PREFIX} == {
        (f"configs/lp{n}_prefix_{rx}_m{m}.yaml", f"configs/hj17_prefix_c81_{rx}_m{m}.yaml")
        for n in (1, 2)
        for rx in ("zs", "bplus")
        for m in (6, 9, 11)
    }


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_committed_config_is_the_generators_output_and_differs_only_where_declared(spec) -> None:
    assert mk.check(spec) == []


def test_the_diff_check_catches_an_undeclared_change_and_a_change_that_did_not_happen() -> None:
    spec = LIVE[0]
    src = mk.load(spec.source)
    drifted = yaml.safe_load(mk.render(spec))
    drifted["executor"]["temperature"] = 0.0
    assert "executor.temperature" in mk.changed_paths(src, drifted) - spec.declared

    stale = yaml.safe_load(mk.render(spec))
    stale["planner"]["packet_source"] = src["planner"]["packet_source"]
    assert "planner.packet_source" in spec.declared - mk.changed_paths(src, stale)


def test_the_diff_check_is_type_aware() -> None:
    # YAML 1 and true are == in Python; a knob flipping between them must still count.
    assert mk.changed_paths({"a": 1}, {"a": True}) == {"a"}


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_every_lp_config_builds_its_ceilings_local_planner(spec, tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("SIDEKICK_PLANNER_BASE_URL", raising=False)
    cfg = _cfg(spec)
    ceiling = load_config(str(REPO / mk.CEILINGS[spec.lp]))["planner"]
    assert cfg["planner"]["type"] == "vllm"
    assert cfg["planner"]["model"] == ceiling["model"] == EXPECTED_MODEL[spec.lp]
    for codex_only in mk.CODEX_ONLY_KEYS:
        assert codex_only not in cfg["planner"]
    # The real replay source may not exist yet (the LP ceilings are still running), so build
    # against a stand-in archive with the same producer subtree.
    (tmp_path / cfg["planner"]["packet_system"]).mkdir()
    cfg["planner"]["packet_source"] = str(tmp_path)
    planner = make_planner(cfg, seed=1)
    assert isinstance(planner, CachedPacketPlanner)
    assert planner.on_missing == "fail"
    inner = planner.inner
    assert isinstance(inner, VllmPlanner)
    assert inner.model == EXPECTED_MODEL[spec.lp]
    assert inner.base_url == ceiling["base_url"].rstrip("/")
    assert (inner.temperature, inner.max_tokens, inner.timeout_s) == (
        ceiling["temperature"],
        ceiling["max_tokens"],
        ceiling["timeout_s"],
    )
    assert inner.chat_template_kwargs == {"enable_thinking": False}


@pytest.mark.parametrize("spec", SPECS, ids=[s.stem for s in SPECS])
def test_replay_sources_name_the_matching_lp_ceiling(spec) -> None:
    cfg = _cfg(spec)
    ceiling_cid = load_config(str(REPO / mk.CEILINGS[spec.lp]))["campaign_id"]
    # An lp1 arm replaying the lp2 ceiling would compare one planner's reviews with another's plans.
    assert ceiling_cid.startswith(f"{spec.lp}_planner_alone_")
    want = f"{RESULTS}/{ceiling_cid}"
    assert cfg["planner"]["packet_source"] == want
    if spec.kind == "prefix":
        assert cfg["handoff"]["source_campaign"] == want
    assert cfg["campaign_id"] == f"{spec.stem}_{mk.DATE}"
    # verify_configs.py gates every PBS job on all configs: while the ceiling is absent the arm
    # must carry a pending reason, or every job on the box would refuse to start.
    assert verify_configs.pending_packet_source(cfg["planner"]) is not None or Path(want).exists()


def test_lp1_ceiling_is_v2_and_no_arm_replays_the_void_campaign() -> None:
    assert load_config(str(REPO / mk.CEILINGS["lp1"]))["campaign_id"] == LP1_CEILING
    assert VOID_LP1_CEILING not in LP1_CEILING  # so the substring check below cannot pass vacuously
    for spec in SPECS:
        assert VOID_LP1_CEILING not in (REPO / spec.out).read_text(encoding="utf-8"), spec.out


@pytest.mark.parametrize("spec", LIVE, ids=[s.stem for s in LIVE])
def test_live_arms_keep_their_sources_channel_and_receiver(spec) -> None:
    cfg, src = _cfg(spec), mk.load(spec.source)
    assert cfg["executor"] == src["executor"]
    assert make_executor(cfg).lora_name == "sft_b_plus"
    for knob in ("takeover", "correct_context", "fixed_k", "limits", "prices"):
        assert cfg.get(knob) == src.get(knob), knob


@pytest.mark.parametrize("spec", PREFIX, ids=[s.stem for s in PREFIX])
def test_prefix_arms_keep_their_sources_receiver_and_depth(spec) -> None:
    cfg, src = _cfg(spec), mk.load(spec.source)
    assert cfg["executor"] == src["executor"]
    m = int(re.search(r"_m(\d+)$", spec.stem).group(1))
    assert cfg["handoff"]["m"] == src["handoff"]["m"] == m
    want_lora = None if "_zs_" in spec.stem else "sft_b_plus"
    assert cfg["executor"]["lora_name"] == want_lora
    assert make_executor(cfg).lora_name == want_lora


@pytest.mark.parametrize("spec", PREFIX, ids=[s.stem for s in PREFIX])
def test_prefix_arms_are_registered_once_in_the_hj12_free_set(spec) -> None:
    # The cid stem must be the config's own stem: campaign_id is <stem>_<date> on both sides.
    want = f"prefix_handoff|${{REPO}}/{spec.out}|{spec.stem}"
    assert read_bash_array(REPO / "scripts" / "pbs" / "hj12_prefix.pbs", "FREE_ARMS").count(want) == 1
    assert Path(spec.out).stem == spec.stem


# ---- scripts/pbs/lp_live.pbs ---------------------------------------------------------------


def _pbs(**env_extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PY": sys.executable, "ARMSET": "", "ARMS": "", **env_extra}
    return subprocess.run(["bash", str(PBS)], env=env, capture_output=True, text=True, timeout=180)


def test_lp_live_pbs_parses() -> None:
    subprocess.run(["bash", "-n", str(PBS)], check=True)


@pytest.mark.parametrize("lp", ["lp1", "lp2"])
def test_armset_selects_exactly_that_lps_live_configs(lp) -> None:
    r = _pbs(LP_SELFTEST="select", ARMSET=lp)
    assert r.returncode == 0, r.stdout + r.stderr
    rows = [row.split("|") for row in r.stdout.split()]
    assert {stem for _sys, _cfg, stem in rows} == {s.stem for s in LIVE if s.lp == lp}
    for system, cfg, stem in rows:
        assert Path(cfg).name == f"{stem}.yaml" and (REPO / "configs" / Path(cfg).name).is_file()
        assert system == ("sft_plan" if "sft_plan" in stem else "fixed_k")


def test_no_armset_is_refused_rather_than_defaulted() -> None:
    r = _pbs(LP_SELFTEST="select")
    assert r.returncode == 2 and "FATAL" in r.stdout


def test_an_unknown_stem_is_refused() -> None:
    r = _pbs(LP_SELFTEST="select", ARMS="lp1_not_an_arm")
    assert r.returncode == 2 and "FATAL" in r.stdout


def _guard(*rels: str) -> subprocess.CompletedProcess:
    return _pbs(LP_SELFTEST="guard", LP_GUARD_CONFIGS=" ".join(str(REPO / rel) for rel in rels))


@pytest.mark.parametrize("lp", ["lp1", "lp2"])
def test_guard_accepts_the_live_configs_and_names_the_planner_to_serve(lp) -> None:
    r = _guard(*[s.out for s in LIVE if s.lp == lp])
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert f"PLANNER_MODEL|{EXPECTED_MODEL[lp]}" in lines
    assert sum(line.startswith("ARM|") for line in lines) == 4


def test_guard_refuses_a_hosted_codex_arm() -> None:
    r = _guard("configs/lp1_hj12_takeover_fixed_k_10.yaml", "configs/hj12_takeover_fixed_k_10.yaml")
    assert r.returncode != 0
    assert "need 'vllm'" in r.stdout
    assert not any(line.startswith("PLANNER_MODEL|") for line in r.stdout.splitlines())


def test_guard_refuses_two_planners_in_one_job() -> None:
    r = _guard("configs/lp1_hj12_takeover_fixed_k_10.yaml", "configs/lp2_hj12_takeover_fixed_k_10.yaml")
    assert r.returncode != 0 and "one job serves one planner" in r.stdout


def test_guard_refuses_a_receiver_the_job_does_not_serve() -> None:
    # A zero-shot prefix config asks for the base model; lp_live registers only sft_b_plus.
    r = _guard("configs/lp1_prefix_zs_m9.yaml")
    assert r.returncode != 0 and "silently hits the BASE model" in r.stdout


# ---- lp_live.pbs resume: refill ONLY crashed episodes ---------------------------------------
# timeout / parse_error are scored outcomes (B2 prereg §3, A1 r2): a resubmission that deleted and
# re-ran them would reroll the arm's failures. Only error_type == "crash" (or an unreadable
# result.json) may be purged, and an arm with 0 crashes is complete whatever else it scored. The
# same cases as tests/unit/test_hj12_within_arm_guard.py pins for hj12_live.pbs.

RESUME_PLANNED = 4


def _episode(root: Path, task_id: str, error_type: str | None, *, body: str | None = None) -> Path:
    dest = root / "fixed_k" / "1" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {"task_id": task_id, "system": "fixed_k", "seed": 1, "success": False, "error_type": error_type}
    (dest / "result.json").write_text(json.dumps(row) + "\n" if body is None else body, encoding="utf-8")
    (dest / "events.jsonl").write_text(json.dumps({"event_type": "run_start"}) + "\n", encoding="utf-8")
    return dest


def _campaign_manifest(out_root: Path, cid: str) -> None:
    # A prior full run always writes one, crashes or not; with it present, only the counts decide.
    dest = out_root / "results" / cid
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest.json").write_text("{}\n", encoding="utf-8")


def _resume_purge(out_root: Path, cid: str) -> str:
    r = _pbs(
        LP_SELFTEST="resume_purge",
        LP_SELFTEST_OUT=str(out_root),
        LP_SELFTEST_CID=cid,
        LP_SELFTEST_N_PLANNED=str(RESUME_PLANNED),
        # This tree's summarizer, not the one under the script's hard-coded REPO.
        LP_SUM=str(REPO / "scripts" / "setup" / "campaign_summarize.py"),
    )
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    return out


def test_lp_live_resume_purges_exactly_the_crashed_episode_and_arm_is_not_complete(tmp_path) -> None:
    cid = "resume_crash"
    root = tmp_path / cid
    kept = [_episode(root, f"t{i}", None) for i in range(3)]
    crashed = _episode(root, "t3", "crash")
    _campaign_manifest(tmp_path, cid)
    out = _resume_purge(tmp_path, cid)
    assert f"[purge-crashed-only] campaign={cid} removed crash=1 unreadable_result=0 no_result=0 kept=3" in out, out
    assert (
        f"[lp] selftest: resume_purge cid={cid} complete_before=0 n_runs=3 n_crashed=0 "
        f"n_planned={RESUME_PLANNED} complete_after=0"
    ) in out, out
    assert not crashed.exists(), out  # the whole directory: EventLog appends on a retry
    assert all((d / "result.json").is_file() for d in kept), out


def test_lp_live_resume_keeps_scored_parse_error_and_timeout_and_arm_is_complete(tmp_path) -> None:
    cid = "resume_scored"
    root = tmp_path / cid
    eps = [
        _episode(root, "t0", None),
        _episode(root, "t1", "limit"),
        _episode(root, "t2", "parse_error"),
        _episode(root, "t3", "timeout"),
    ]
    before = {p: p.read_bytes() for d in eps for p in sorted(d.iterdir())}
    _campaign_manifest(tmp_path, cid)
    out = _resume_purge(tmp_path, cid)
    assert f"[purge-crashed-only] campaign={cid} removed crash=0 unreadable_result=0 no_result=0 kept=4" in out, out
    # complete_before=1 is the resume scan skipping the arm: under --purge-broken it was never
    # complete, and every resubmission rerolled the parse_error and the timeout.
    assert (
        f"[lp] selftest: resume_purge cid={cid} complete_before=1 n_runs={RESUME_PLANNED} n_crashed=0 "
        f"n_planned={RESUME_PLANNED} complete_after=1"
    ) in out, out
    after = {p: p.read_bytes() for d in eps for p in sorted(d.iterdir())}
    assert after == before, out


def test_lp_live_resume_counts_an_empty_result_json_as_needing_a_refill(tmp_path) -> None:
    # A write killed mid-flight: the runner only checks that result.json exists, so left alone
    # this episode would never be re-run and the arm would be "complete" with a hole in it.
    cid = "resume_empty"
    root = tmp_path / cid
    kept = [_episode(root, f"t{i}", None) for i in range(3)]
    empty = _episode(root, "t3", None, body="")
    _campaign_manifest(tmp_path, cid)
    out = _resume_purge(tmp_path, cid)
    assert (
        f"[lp] selftest: resume_purge cid={cid} complete_before=0 n_runs=3 n_crashed=0 "
        f"n_planned={RESUME_PLANNED} complete_after=0"
    ) in out, out
    assert not empty.exists(), out
    assert all((d / "result.json").is_file() for d in kept), out


def test_lp_live_counts_plan_events_that_are_not_the_last_line(tmp_path) -> None:
    # A ceiling episode logs its plan at step 0 and run_end after it, so the plan is never the
    # final event. jq 1.6's -e judged only the last line, and the old per-line check counted 0.
    for i in range(3):
        dest = tmp_path / f"t{i}"
        dest.mkdir()
        types = ["run_start", "observation", "plan", "evaluate", "run_end"] if i < 2 else ["run_start", "error", "run_end"]
        (dest / "events.jsonl").write_text("".join(json.dumps({"event_type": t}) + "\n" for t in types), encoding="utf-8")
    r = _pbs(LP_SELFTEST="plan_count", LP_PLAN_ROOT=str(tmp_path))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "2"


def test_lp_live_no_longer_purges_scored_episodes() -> None:
    text = PBS.read_text(encoding="utf-8")
    assert "--purge-crashed-only" in text
    assert not re.search(r"^[^#]*--purge-broken", text, flags=re.MULTILINE)


# ---- scripts/pbs/lp1_planner_alone.pbs: the smoke gate and the campaign id --------------------
# Job 25724309's gate checked only the smoke runner's exit code and passed three episodes that had
# all ended parse_error in the plan call at step 0; the full run then measured nothing. The gate
# must read what the episodes wrote.


def _lp1(**env_extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("CID", "CFG", "LP1_SMOKE_DIR")}
    return subprocess.run(
        ["bash", str(LP1_PBS)], env={**env, **env_extra}, capture_output=True, text=True, timeout=120
    )


def _smoke_episode(root: Path, task_id: str, error_type: str | None, steps: int, *, failed_call: str | None = None,
                   body: str | None = None) -> None:
    dest = root / "planner_alone" / "1" / task_id
    dest.mkdir(parents=True, exist_ok=True)
    row = {"task_id": task_id, "system": "planner_alone", "seed": 1, "success": False,
           "steps": steps, "error_type": error_type}
    (dest / "result.json").write_text(json.dumps(row) + "\n" if body is None else body, encoding="utf-8")
    events = [{"event_type": "run_start", "step": 0, "actor": "system", "payload": {}}]
    if failed_call is not None:
        # What loop.call_planner logs when the planner raises PacketParseError.
        events.append({"event_type": "error", "step": 0, "actor": "planner", "error_type": "parse_error",
                       "payload": {"method": failed_call, "raw_output": '```json\n{"context": "API docs'}})
    (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _gate(tree: Path) -> tuple[int, str]:
    r = _lp1(LP1_SELFTEST="smoke_gate", LP1_SMOKE_DIR=str(tree))
    return r.returncode, r.stdout + r.stderr


def test_lp1_pbs_parses() -> None:
    subprocess.run(["bash", "-n", str(LP1_PBS)], check=True)


def test_lp1_smoke_gate_refuses_the_smoke_the_old_gate_passed(tmp_path) -> None:
    for i in range(3):
        _smoke_episode(tmp_path, f"t{i}", "parse_error", 0, failed_call="plan")
    rc, out = _gate(tmp_path)
    assert rc != 0, out
    assert "result.json=3 plan_parse_error=3 steps_zero=3 unreadable=0" in out, out
    assert "FATAL" in out and "parse_error in the plan call" in out, out


def test_lp1_smoke_gate_refuses_a_single_plan_parse_error(tmp_path) -> None:
    _smoke_episode(tmp_path, "t0", None, 9)
    _smoke_episode(tmp_path, "t1", "limit", 40)
    _smoke_episode(tmp_path, "t2", "parse_error", 0, failed_call="plan")
    rc, out = _gate(tmp_path)
    assert rc != 0, out
    assert "plan_parse_error=1 steps_zero=1" in out, out


def test_lp1_smoke_gate_refuses_when_every_episode_stopped_at_step_zero(tmp_path) -> None:
    # Not a parse failure, and not a crash either: still an arm that ran nothing past the plan.
    for i, et in enumerate(("api_error", "timeout", None)):
        _smoke_episode(tmp_path, f"t{i}", et, 0)
    rc, out = _gate(tmp_path)
    assert rc != 0, out
    assert "plan_parse_error=0 steps_zero=3" in out and "steps == 0" in out, out


def test_lp1_smoke_gate_passes_scored_endings_past_the_plan(tmp_path) -> None:
    _smoke_episode(tmp_path, "t0", None, 9)
    _smoke_episode(tmp_path, "t1", "limit", 40)
    # A parse failure in a LATER planner call is a scored outcome of the arm, not a dead plan.
    _smoke_episode(tmp_path, "t2", "parse_error", 6, failed_call="act")
    rc, out = _gate(tmp_path)
    assert rc == 0, out
    assert "result.json=3 plan_parse_error=0 steps_zero=0 unreadable=0" in out, out
    assert "smoke gate passed" in out, out


@pytest.mark.parametrize("body", [None, ""], ids=["no_result_json", "empty_result_json"])
def test_lp1_smoke_gate_refuses_nothing_to_judge(tmp_path, body) -> None:
    if body is not None:
        _smoke_episode(tmp_path, "t0", None, 9)
        _smoke_episode(tmp_path, "t1", None, 0, body=body)
    rc, out = _gate(tmp_path)
    assert rc != 0 and "nothing to judge the arm by" in out, out


def test_lp1_smoke_gate_refuses_the_real_void_smoke() -> None:
    # Read-only: jq and find over the tree job 25724309 wrote; nothing is written or deleted.
    tree = Path(RESULTS) / f"{VOID_LP1_CEILING}_smoke"
    if not tree.is_dir():
        pytest.skip(f"{tree} not present on this machine")
    rc, out = _gate(tree)
    assert rc != 0, out
    assert "plan_parse_error=3 steps_zero=3" in out, out


def test_lp1_campaign_id_is_the_configs() -> None:
    r = _lp1(LP1_SELFTEST="cid", CFG=str(REPO / mk.CEILINGS["lp1"]))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == f"CID|{LP1_CEILING}"
    r = _lp1(LP1_SELFTEST="cid", CFG=str(REPO / mk.CEILINGS["lp2"]))
    assert r.stdout.strip().splitlines()[-1] == f"CID|{load_config(str(REPO / mk.CEILINGS['lp2']))['campaign_id']}"


def test_lp1_refuses_a_cid_that_is_not_the_configs() -> None:
    r = _lp1(LP1_SELFTEST="cid", CFG=str(REPO / mk.CEILINGS["lp1"]), CID=VOID_LP1_CEILING)
    assert r.returncode != 0 and "FATAL" in r.stdout, r.stdout + r.stderr
    assert "CID|" not in r.stdout


def test_lp1_refuses_the_void_campaign_even_from_a_config_that_names_it(tmp_path) -> None:
    # e.g. a job pointed at a stale checkout's config: the void tree must not be resumed into,
    # nor its smoke tree cleared.
    old = tmp_path / "old_lp1.yaml"
    old.write_text(f"env: appworld\ncampaign_id: {VOID_LP1_CEILING}\n", encoding="utf-8")
    r = _lp1(LP1_SELFTEST="cid", CFG=str(old))
    assert r.returncode != 0 and "is VOID" in r.stdout, r.stdout + r.stderr
    assert "CID|" not in r.stdout
