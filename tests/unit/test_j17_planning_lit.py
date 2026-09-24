"""J17 planning-literature analyses: every function on hand-built data, expected values worked by hand.

World: 4 scenarios (sc00-sc03) x 2 tasks (_1, _2) x seeds {1, 2} = 16 keys per arm, in the runner's
layout <campaign>/<system>/<seed>/<task>/{result.json, events.jsonl, manifest.json}; an arm whose real
spec pools seed 3 gets a second campaign holding seed 3 (8 keys). Every arm's goal_pass is a constant
(GP) and its TGC equals it unless the episode has an error_type (then 0), so every paired difference
below is a constant and its bootstrap interval collapses onto the point:

  A  plan gain tailored 0.75 - 0.50 = +25 pp; plan gain base 0.25 - 0.25 = 0; DiD1 = +25 pp;
     G_plan 0.75 - 0.25 = +50 pp; G_act(m) 0.80 - 0.70 = +10 pp; DiD2(m) = 50 - 10 = +40 pp;
     same build 0.625 - 0.50 = +12.5 pp. exec_alone_base crashed on (sc03_2, 2): 15 common keys,
     scenario sizes 4, 4, 4, 3, so a constant difference has sign-flip p = 2 / 2**4 = 0.125.
  B  noop: 16 x stopped_before_acting; advise_k10: 1 limit; takeover_k10: 1 parse_error (other);
     prefix_c81_bplus_m6: 1 no_handoff of 24; sft_plan_bplus: 1 stopped_before_acting.
  C  high 0.90 (limit on (sc00_1, 2), TGC 0 there) against medium 0.80; high makes 2 priced planner
     calls per episode, medium 1, each 1000 input / 400 cached / 100 output / 50 reasoning tokens.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import b2_decomposition as b2
from scripts.analysis import j17_planning_lit as j17p

SCENARIOS = [f"sc{i:02d}" for i in range(4)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2)]
N_BOOT = 200
SYSTEM = {"executor": "executor_alone", "prefix": "prefix_handoff", "planner": "planner_alone"}
GP = {
    "exec_alone_bplus": 0.50, "sft_plan_bplus": 0.75, "exec_alone_base": 0.25, "prompt_only_base": 0.25,
    "sft_plan_bplus_0919": 0.625, "qwen_exec_alone": 0.25, "qwen_prompt_only": 0.25,
    **{f"prefix_bplus_m{m}": 0.80 for m in (6, 9, 11)}, **{f"prefix_zs_m{m}": 0.70 for m in (6, 9, 11)},
    "planner_alone_c81_high": 0.90, "planner_alone_c81_medium": 0.80,
    "prefix_c81_bplus_m11": 0.85, "prefix_c81_zs_m11": 0.80,
}
PLAN_ARMS = {"sft_plan_bplus", "sft_plan_bplus_0919", "prompt_only_base", "qwen_prompt_only"}
BASE_CRASH = ("exec_alone_base", ("sc03_2", 2))
ADVISE_LIMIT = ("advise_k10", ("sc00_1", 1))
TAKEOVER_PARSE = ("takeover_k10", ("sc00_2", 1))
HIGH_LIMIT = ("planner_alone_c81_high", ("sc00_1", 2))
SFT_STOP = ("sft_plan_bplus", ("sc01_2", 2))
NO_HANDOFF = ("prefix_c81_bplus_m6", ("sc01_1", 1))
FLAG_DIFF = ("prefix_c81_bplus_m6", ("sc02_1", 2))
QWEN_PLAN_DIFF = ("qwen_prompt_only", ("sc00_1", 1))
U = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 1000, "cached_input_tokens": 400,
     "output_tokens": 100, "reasoning_output_tokens": 50, "n_calls": 1}
# j12.price_usage_record at 0.20 / 0.02 / 1.20 USD per 1M: 600 x 0.2e-6 + 400 x 0.02e-6 + 150 x 1.2e-6.
USD_PER_CALL = 600 * 0.20e-6 + 400 * 0.02e-6 + 150 * 1.20e-6  # 3.08e-4
PRICES_YAML = ('schedule_date: "2026-09-15"\nmodels:\n  gpt-5.6-luna: {input: 0.20, cached_input: 0.02, output: 1.20}\n'
               "local:\n  usd_per_gpu_hour: 2.50\n")


def _ev(event_type, actor, step, usage=None, **payload):
    ev = {"event_type": event_type, "actor": actor, "step": step, "payload": payload}
    if usage is not None:
        ev["usage"] = usage
    return ev


def _act(actor, step, kind, usage=None):
    return _ev("action", actor, step, usage=usage, kind=kind, code="x = 1" if kind == "CODE" else None,
               message=None, ask_reason=None, confidence=None, raw_output=kind)


def _exec_usage(label):
    lora = "sft_b_plus" if "bplus" in label else None
    return {"model": lora or "ibm-granite/granite-4.2-8b", "provider": "vllm", "raw": {"lora_name": lora}}


def _cached_plan(task, seed, text):
    usage = {"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0, "cached_input_tokens": 0,
             "output_tokens": 0, "n_calls": 1,
             "raw": {"cached_from": f"/r/hj1b_planner_20260915/planner_alone/{seed}/{task}/events.jsonl"}}
    return _ev("plan", "planner", 0, usage=usage, packet={"task_id": task, "plan_steps": [text]},
               model_reasoning_effort=None)


def events_for(label, role, task, seed):
    key = (task, seed)
    timeout = 300 if label == "planner_alone_c81_high" else 120
    evs = [_ev("run_start", "system", 0, limits={"max_steps": 40, "max_planner_calls": 81, "per_step_timeout_s": timeout},
               policy={})]
    if role == "planner":
        high = label == "planner_alone_c81_high"
        return evs + [_ev("plan", "planner", 0, usage=dict(U), packet={"task_id": task, "plan_steps": ["live"]},
                          model_reasoning_effort="high" if high else "medium"),
                      _act("planner", 1, "CODE", usage=dict(U) if high else None),
                      _act("planner", 2, "COMPLETE")]
    if label in PLAN_ARMS:
        text = "other plan" if (label, key) == QWEN_PLAN_DIFF else f"plan {task} {seed}"
        evs.append(_cached_plan(task, seed, text))
    start = 1
    if role == "prefix":
        handoff = (label, key) != NO_HANDOFF
        evs.append(_ev("report", "system", 6, effective_m=6, handoff_occurred=handoff, n_source_actions=9,
                       source_campaign="/r/hj1b_planner_20260915"))
        if not handoff:
            return evs
        start = 7
    if label == "noop" or (label, key) == SFT_STOP:
        return evs + [_act("executor", start, "COMPLETE", usage=_exec_usage(label))]
    if (label, key) == TAKEOVER_PARSE:
        return evs + [_ev("error", "executor", 1, raw_output="??", attempts=3)]
    evs += [_act("executor", start, "CODE", usage=_exec_usage(label)),
            _ev("observation", "environment", start, text="ok", done=False, kind="CODE")]
    if (label, key) == FLAG_DIFF:  # an executor REPORT writes a `report` event without handoff_occurred
        evs += [_act("executor", start + 1, "REPORT", usage=_exec_usage(label)),
                _ev("report", "executor", start + 1, message="progress")]
        start += 1
    return evs + [_act("executor", start + 1, "COMPLETE", usage=_exec_usage(label))]


def write_episode(root, campaign, system, task, seed, *, gp, error_type=None, steps=2, n_planner_calls=0,
                  events=None, manifest=None):
    dest = root / campaign / system / str(seed) / task
    dest.mkdir(parents=True, exist_ok=True)
    row = {"run_id": f"{campaign}/{system}/{seed}/{task}", "task_id": task, "seed": seed, "system": system,
           "goal_pass_rate": gp, "tgc": 0.0 if error_type else gp, "success": gp == 1.0 and not error_type,
           "steps": steps, "n_planner_calls": n_planner_calls, "n_asks": 0, "error_type": error_type,
           "totals": {"planner_calls_total": n_planner_calls, "planner_tokens_total": 0}}
    (dest / "result.json").write_text(json.dumps(row) + "\n", encoding="utf-8")
    if events is not None:
        (dest / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    if manifest is not None:
        (dest / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return dest


def _manifest(label):
    if label != "planner_alone_c81_high":
        return {"created_at": "2026-09-20T00:00:00+00:00"}
    return {"created_at": "2026-09-24T08:00:00+00:00",
            "provenance": {"git_sha": "abc123", "git_dirty": True, "split": "dev", "lora_name": None,
                           "planner_reasoning_effort": "high",
                           "config_path": str(j17p.REPO_ROOT / "configs" / "dev_planner_alone_cap81_high.yaml")}}


def build_world(root: Path) -> dict[str, dict]:
    """Every ARMS label as t_<label> (seeds 1-2), plus t_<label>_s3 (seed 3) where the real arm pools it."""
    spec: dict[str, dict] = {}
    for label, real in j17p.ARMS.items():
        role = real["role"]
        camps = (f"t_{label}",) + ((f"t_{label}_s3",) if 3 in real["seeds"] else ())
        spec[label] = {"campaigns": camps, "seeds": real["seeds"], "role": role}
        for idx, camp in enumerate(camps):
            for seed in ((3,) if idx else (1, 2)):
                for task in TASKS:
                    key = (task, seed)
                    err = {BASE_CRASH: "crash", ADVISE_LIMIT: "limit", TAKEOVER_PARSE: "parse_error",
                           HIGH_LIMIT: "limit"}.get((label, key))
                    calls = 2 if label == "planner_alone_c81_high" else 1 if role == "planner" or label in PLAN_ARMS else 0
                    write_episode(root, camp, SYSTEM[role], task, seed, gp=GP.get(label, 0.5), error_type=err,
                                  steps=40 if err == "limit" else 2, n_planner_calls=calls,
                                  events=events_for(label, role, task, seed), manifest=_manifest(label))
    return spec


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("results")
    spec = build_world(root)
    repo = tmp_path_factory.mktemp("repo")
    (repo / "campaign" / "results").mkdir(parents=True)
    (repo / "campaign" / "results" / "x.report.json").write_text(
        json.dumps({"arms": {"hit": {"goal_pass_all": 0.75}, "miss": {"goal_pass_all": 0.7}}}), encoding="utf-8")
    prices = repo / "prices.yaml"
    prices.write_text(PRICES_YAML, encoding="utf-8")
    checks = ({"ledger": "T-1", "arm": "sft_plan_bplus", "report": "campaign/results/x.report.json",
               "key": "arms.hit.goal_pass_all", "seeds": (1, 2)},
              {"ledger": "T-2", "arm": "sft_plan_bplus", "report": "campaign/results/x.report.json",
               "key": "arms.miss.goal_pass_all", "seeds": (1, 2)},
              {"ledger": "T-3", "arm": "not_an_arm", "report": "campaign/results/x.report.json",
               "key": "arms.hit.goal_pass_all", "seeds": (1, 2)})
    report, code = j17p.build_report(results_root=root, arms_spec=spec, n_boot=N_BOOT, prices=prices,
                                     checks=checks, repo_root=repo)
    return {"root": root, "spec": spec, "report": report, "code": code, "repo": repo, "prices": prices}


# ---- paths ------------------------------------------------------------------
def test_refuse_path_heldout_and_j1x_components_only():
    assert "test_normal" in j17p.refuse_path("/scratch/x/results/test_normal/a")
    assert "test_challenge" in j17p.refuse_path("/tmp/test_challenge_run")
    assert "J10/J11/J12" in j17p.refuse_path("/tmp/results/j12_arm_20260924")
    assert "J10/J11/J12" in j17p.refuse_path("/tmp/results/j10_arm_20260924_dryrun/x")  # the brief allows none
    assert "J10/J11/J12" in j17p.refuse_path("/tmp/results/j11_lp2")
    # dev campaigns whose names merely contain j12_ / j13_ are read
    assert j17p.refuse_path("/tmp/results/hj12_prefix_m6_20260923") is None
    assert j17p.refuse_path("/tmp/results/hj13_prefix_zs_m9_20260923/prefix_handoff") is None


def test_refuse_out_under_scratch(tmp_path):
    assert "raw results" in j17p.refuse_out(Path("/scratch/n12194778/x.json"))
    assert j17p.refuse_out(tmp_path / "o.json") is None


def test_campaign_of_and_dig_and_rel():
    assert j17p._campaign_of("/r/hj1b_planner_20260915/planner_alone/1/t_1/events.jsonl", 3) == "hj1b_planner_20260915"
    assert j17p._campaign_of(None, 3) is None
    assert j17p._campaign_of("a/b", 3) is None
    assert j17p._dig({"a": {"b": {"c": 3}}}, "a.b.c") == 3
    assert j17p._dig({"a": 1}, "a.b") is None
    assert j17p._rel(j17p.REPO_ROOT / "configs" / "x.yaml") == "configs/x.yaml"
    assert j17p._rel("/elsewhere/x") == "/elsewhere/x"


# ---- one episode --------------------------------------------------------------
def test_episode_facts_prefix_counts_only_after_handoff_and_keeps_the_system_flag():
    events = [
        _ev("run_start", "system", 0, limits={"max_planner_calls": 81}),
        _ev("report", "system", 6, effective_m=6, handoff_occurred=True, source_campaign="/r/hj1b_planner_20260915"),
        _act("executor", 5, "CODE", usage=_exec_usage("bplus")),  # at or before m: not counted
        _act("executor", 7, "CODE", usage=_exec_usage("bplus")),
        _act("executor", 8, "ASK_PLANNER", usage=_exec_usage("bplus")),
        _act("planner", 8, "CODE"),  # a takeover move is the planner's, never the executor's
        _ev("report", "executor", 9, message="m"),  # executor REPORT: no handoff_occurred key
        _act("executor", 9, "COMPLETE"),
    ]
    f = j17p.episode_facts(events, "prefix")
    assert f["acting_actor"] == "executor"
    assert f["handoff_occurred"] is True
    assert f["handoff_flag_j10_reader"] is None  # the last report event wins there
    assert f["effective_m"] == 6 and f["prefix_source_campaign"] == "hj1b_planner_20260915"
    assert f["action_kinds"] == {"ASK_PLANNER": 1, "CODE": 1, "COMPLETE": 1}
    assert f["n_actions"] == 3 and f["n_acted"] == 1
    # three executor action events carry usage (steps 5, 7, 8); the step-9 COMPLETE has none
    assert f["executor_adapters"] == {"sft_b_plus|lora=sft_b_plus": 3}
    assert f["plan_source"] is None and f["plan_hash"] is None
    assert f["max_planner_calls"] == 81 and f["per_step_timeout_s"] is None


def test_episode_facts_planner_role_and_plan_sources():
    live = [_ev("run_start", "system", 0), _ev("plan", "planner", 0, usage=dict(U), packet={"p": 1},
                                              model_reasoning_effort="high"),
            _act("planner", 1, "CODE"), _act("planner", 2, "CODE"), _act("planner", 3, "COMPLETE")]
    f = j17p.episode_facts(live, "planner")
    assert f["acting_actor"] == "planner" and f["n_acted"] == 2 and f["n_actions"] == 3
    assert f["plan_source"] == "live:codex" and f["plan_effort"] == "high"
    cached = [_ev("run_start", "system", 0), _cached_plan("t_1", 1, "x"), _act("planner", 1, "CODE")]
    g = j17p.episode_facts(cached, "executor")
    assert g["plan_source"] == "replayed:hj1b_planner_20260915"
    assert g["n_acted"] == 0  # the executor never acted; the planner move is not its action
    same = j17p.episode_facts([_cached_plan("t_1", 1, "x")], "executor")["plan_hash"]
    other = j17p.episode_facts([_cached_plan("t_1", 1, "y")], "executor")["plan_hash"]
    assert g["plan_hash"] == same != other and len(same) == 16


def test_classify_every_branch():
    assert j17p.classify({"handoff_occurred": False, "n_acted": 3}, None, "prefix") == "no_handoff"
    assert j17p.classify({"handoff_occurred": None, "n_acted": 0}, "limit", "prefix") == "no_handoff"
    assert j17p.classify({"handoff_occurred": True, "n_acted": 0}, "limit", "prefix") == "limit"
    assert j17p.classify({"n_acted": 0}, "parse_error", "executor") == "other"
    assert j17p.classify({"n_acted": 0}, None, "executor") == "stopped_before_acting"
    assert j17p.classify({"n_acted": 2}, None, "planner") == "completed_after_acting"
    # handoff_occurred is not read outside prefix arms
    assert j17p.classify({"handoff_occurred": False, "n_acted": 1}, None, "executor") == "completed_after_acting"


def test_manifest_provenance():
    assert j17p.manifest_provenance(None)["git_sha"] is None
    p = j17p.manifest_provenance(_manifest("planner_alone_c81_high"))
    assert p == {"created_at": "2026-09-24T08:00:00+00:00", "git_sha": "abc123", "git_dirty": True,
                 "config_path": "configs/dev_planner_alone_cap81_high.yaml", "lora_name": None,
                 "planner_reasoning_effort": "high", "split": "dev"}


def test_episode_record_reads_events_and_manifest(tmp_path):
    dest = write_episode(tmp_path, "c", "executor_alone", "sc00_1", 1, gp=0.5, steps=3,
                         events=events_for("noop", "executor", "sc00_1", 1), manifest=_manifest("x"))
    (dest / "events.jsonl").write_text((dest / "events.jsonl").read_text() + "not json\n", encoding="utf-8")
    rec = j17p.episode_record({"steps": 3, "error_type": None}, dest / "events.jsonl", "executor")
    assert rec["category"] == "stopped_before_acting" and rec["steps"] == 3
    assert rec["n_unparseable_event_lines"] == 1 and rec["has_events"] is True
    assert rec["provenance"]["created_at"] == "2026-09-20T00:00:00+00:00"
    bare = j17p.episode_record({"steps": 1, "error_type": "limit"}, None, "executor")
    assert bare["has_events"] is False and bare["category"] == "limit" and bare["provenance"]["git_sha"] is None


# ---- one arm ------------------------------------------------------------------
def test_load_arm_pools_counts_crash_and_keys_records(world):
    arm = j17p.load_arm("exec_alone_base", world["spec"]["exec_alone_base"], world["root"])
    assert arm["summary"]["n_scored"] == 15 and arm["summary"]["n_crash"] == 1
    assert BASE_CRASH[1] not in arm["records"] and len(arm["records"]) == 15
    assert arm["campaigns"][0]["n_crash"] == 1 and arm["campaigns"][0]["n_scored"] == 15
    pooled = j17p.load_arm("show_k10", world["spec"]["show_k10"], world["root"])
    assert [c["n_scored"] for c in pooled["campaigns"]] == [16, 8]
    assert {r["campaign"] for r in pooled["records"].values()} == {"t_show_k10", "t_show_k10_s3"}


def test_load_arm_refuses_a_key_twice(world, tmp_path):
    spec = {"campaigns": ("t_noop", "t_noop"), "seeds": (1, 2), "role": "executor"}
    with pytest.raises(b2.PoolingError):
        j17p.load_arm("noop", spec, world["root"])


def test_provenance_summary_and_arm_provenance(world):
    arm = j17p.load_arm("planner_alone_c81_high", world["spec"]["planner_alone_c81_high"], world["root"])
    prov = j17p.arm_provenance(arm)
    s = prov["t_planner_alone_c81_high"]
    assert s["n_episodes"] == 16 and s["git_sha"] == {"abc123": 16} and s["split"] == {"dev": 16}
    assert s["planner_reasoning_effort"] == {"high": 16} and s["plan_source"] == {"live:codex": 16}
    assert s["plan_effort_recorded"] == {"high": 16} and s["per_step_timeout_s"] == {"300": 16}
    assert s["created_at_first"] == s["created_at_last"] == "2026-09-24T08:00:00+00:00"
    base = j17p.provenance_summary([{"provenance": j17p.manifest_provenance(None), "executor_adapters": {"m|lora=None": 2},
                                     "plan_source": None, "prefix_source_campaign": None, "max_planner_calls": 81}])
    assert base["git_sha"] == {"unrecorded": 1} and base["executor_adapter_episodes"] == {"m|lora=None": 1}
    assert base["plan_source"] == {"no_plan_event": 1} and base["max_planner_calls"] == {"81": 1}
    assert base["plan_effort_recorded"] == {} and base["per_step_timeout_s"] == {"unrecorded": 1}


# ---- inference --------------------------------------------------------------
def _series(diffs, keys):
    return {"keys": keys, "diffs": diffs, "n_dropped_missing_field": 0}


ONE_PER_SCENARIO = [(f"{s}_1", 1) for s in SCENARIOS]


def test_contrast_object_constant_difference_by_hand():
    obj = j17p.contrast_object(_series([0.25] * 4, ONE_PER_SCENARIO), "goal_pass", n_boot=N_BOOT, seed=7)
    assert obj["diff_pp"] == pytest.approx(25.0)
    assert obj["ci95_pp_scenario"] == pytest.approx([25.0, 25.0]) and obj["ci95_pp_task"] == pytest.approx([25.0, 25.0])
    assert obj["p_two_sided"] == 0.0 and obj["p_two_sided_task"] == 0.0  # every resample mean is 0.25 > 0
    assert obj["p_signflip_two_sided"] == pytest.approx(2 / 16) and obj["signflip_method"] == "exact"
    assert obj["n_pairs"] == 4 and obj["n_clusters_scenario"] == 4 and obj["n_clusters_task"] == 4
    assert obj["printed"]["diff_pp"] == "+25.00" and obj["printed"]["p_signflip_two_sided"] == "0.1250"


def test_contrast_object_threshold_empty_and_mixed():
    at7 = j17p.contrast_object(_series([0.05] * 4, ONE_PER_SCENARIO), "tgc", n_boot=N_BOOT, seed=7, threshold_pp=7.0)
    assert at7["p_two_sided"] == 0.0  # every mean 0.05 lies below 0.07: share >= t is 0
    assert at7["p_signflip_two_sided"] == pytest.approx(2 / 16)  # shifted diffs are the constant -0.02
    empty = j17p.contrast_object(_series([], []), "tgc", n_boot=N_BOOT, seed=7)
    assert empty["diff_pp"] is None and empty["n_pairs"] == 0
    mixed = j17p.contrast_object(_series([0.0, 1.0, 0.0, 1.0], ONE_PER_SCENARIO), "goal_pass", n_boot=N_BOOT, seed=7)
    assert mixed["diff_pp"] == pytest.approx(50.0)
    lo, hi = mixed["ci95_pp_scenario"]
    assert 0.0 <= lo <= 50.0 <= hi <= 100.0


def test_printed_pp():
    assert j17p.printed_pp(None) is None
    assert j17p.printed_pp(4.126) == "+4.13" and j17p.printed_pp(-4.126) == "-4.13" and j17p.printed_pp(0.0) == "+0.00"


def test_combo_series_definition_and_keys():
    a = {("x_1", 1): {"f": 1.0}, ("y_1", 1): {"f": 1.0}}
    b = {("x_1", 1): {"f": 0.5}, ("y_1", 1): {"f": 0.0}}
    c = {("x_1", 1): {"f": 0.25}, ("y_1", 1): {"f": 0.25}}
    d = {("x_1", 1): {"f": 0.0}, ("y_1", 1): {"f": 0.0}}
    eps = {"a": a, "b": b, "c": c, "d": d}
    did = j17p.combo_series(eps, ("a", "b", "c", "d"), "f", set(a))
    assert did["diffs"] == pytest.approx([0.25, 0.75])  # (1 - 0.5) - 0.25 and (1 - 0) - 0.25
    one = j17p.combo_series(eps, ("a", "b"), "f", {("y_1", 1)})
    assert one["keys"] == [("y_1", 1)] and one["diffs"] == [1.0]
    with pytest.raises(ValueError):
        j17p.combo_series(eps, ("a", "b", "c"), "f", set(a))
    assert j17p.definition(("a", "b")) == "a - b"
    assert j17p.definition(("a", "b", "c", "d")) == "(a - b) - (c - d)"


def test_contrast_entry_means_on_pairs():
    eps = {"l": {k: {"goal_pass_rate": 0.75, "tgc": 0.5} for k in ONE_PER_SCENARIO},
           "r": {k: {"goal_pass_rate": 0.5, "tgc": 0.5} for k in ONE_PER_SCENARIO}}
    e = j17p.contrast_entry(eps, ("l", "r"), set(ONE_PER_SCENARIO), n_boot=N_BOOT, seed=7)
    assert e["definition"] == "l - r"
    assert e["goal_pass"]["diff_pp"] == pytest.approx(25.0) and e["tgc"]["diff_pp"] == pytest.approx(0.0)
    assert e["goal_pass"]["means_on_pairs"] == {"l": 0.75, "r": 0.5}


def test_scored_keys_common_keys_limit_rate_seeds_only():
    eps = {"a": {("t_1", 1): {"goal_pass_rate": 1.0, "tgc": None}, ("t_1", 2): {"goal_pass_rate": 1.0, "tgc": 1.0},
                 ("t_2", 3): {"goal_pass_rate": 0.0, "tgc": 0.0, "error_type": "limit"}},
           "b": {("t_1", 2): {"goal_pass_rate": 0.0, "tgc": 0.0}, ("t_2", 3): {"goal_pass_rate": 0.0, "tgc": 0.0}}}
    assert j17p.scored_keys(eps["a"]) == {("t_1", 2), ("t_2", 3)}
    assert j17p.common_keys(eps, ("a", "b")) == {("t_1", 2), ("t_2", 3)}
    assert j17p.common_keys({}, ()) == set()
    assert j17p.limit_rate(eps["a"]) == {"n": 3, "n_limit": 1, "rate": pytest.approx(1 / 3)}
    assert j17p.limit_rate(eps["a"], {("t_1", 2)}) == {"n": 1, "n_limit": 0, "rate": 0.0}
    assert j17p.limit_rate({}) == {"n": 0, "n_limit": 0, "rate": None}
    assert set(j17p._seeds_only(eps["a"], (1, 2))) == {("t_1", 1), ("t_1", 2)}


def test_plan_identity():
    left = {("a_1", 1): {"plan_hash": "h1"}, ("b_1", 1): {"plan_hash": "h2"}, ("c_1", 1): {"plan_hash": None}}
    right = {("a_1", 1): {"plan_hash": "h1"}, ("b_1", 1): {"plan_hash": "zz"}, ("c_1", 1): {"plan_hash": "h3"}}
    got = j17p.plan_identity(left, right, set(left))
    assert got == {"n_keys": 3, "n_identical": 1, "n_differ": 1, "n_missing_plan": 1, "differ_examples": ["b_1/1"]}


def test_ni_reading():
    assert j17p.ni_reading([-3.0, 6.994]) == "holds"  # rounds to 6.99 < 7.00
    assert j17p.ni_reading([-3.0, 6.996]) == "fails"  # rounds to 7.00, not below
    assert j17p.ni_reading([1.0, 9.0]) == "fails"
    assert j17p.ni_reading(None) is None


# ---- B: census --------------------------------------------------------------
def _rec(category, steps, acted, error_type=None, handoff=None):
    return {"category": category, "steps": steps, "n_acted": acted, "n_actions": acted + 1,
            "action_kinds": {"CODE": acted, "COMPLETE": 1}, "acting_actor": "executor", "error_type": error_type,
            "has_events": True, "handoff_occurred": handoff, "handoff_flag_j10_reader": handoff}


def test_census_block_by_hand():
    recs = {("sc00_1", 1): _rec("stopped_before_acting", 1, 0), ("sc01_1", 1): _rec("completed_after_acting", 3, 2),
            ("sc02_1", 1): _rec("completed_after_acting", 5, 1), ("sc03_1", 1): _rec("limit", 40, 5, "limit")}
    b = j17p.census_block(recs, n_boot=N_BOOT, seed=7)
    cats = b["categories"]
    assert b["n_scored"] == 4
    assert cats["stopped_before_acting"]["n"] == 1 and cats["stopped_before_acting"]["share"] == 0.25
    assert cats["completed_after_acting"]["share"] == 0.5 and cats["limit"]["share"] == 0.25
    assert cats["no_handoff"]["share"] == 0.0 and cats["no_handoff"]["ci95_scenario"] == [0.0, 0.0]
    assert cats["limit"]["printed"] == "0.2500"
    lo, hi = cats["completed_after_acting"]["ci95_scenario"]
    assert 0.0 <= lo <= 0.5 <= hi <= 1.0
    assert b["median_steps"] == 4.0 and b["mean_steps"] == 12.25  # (3 + 5) / 2; (1 + 3 + 5 + 40) / 4
    assert b["median_acted"] == 1.5 and b["mean_acted"] == 2.0 and b["median_actions_any_kind"] == 2.5
    assert b["action_kinds_total"] == {"CODE": 8, "COMPLETE": 4}
    assert b["zero_acted_by_error_type"] == {"none": 1}
    assert b["n_clusters"] == {"scenario": 4, "task": 4} and b["n_handoff_flag_differs_from_j10_reader"] == 0
    assert b["n_no_handoff_acted"] == 0 and b["n_no_handoff_flag_missing"] == 0
    # a prefix arm: one no_handoff episode the executor still acted in (flag false), one with no flag
    pre = {("sc00_1", 1): _rec("no_handoff", 9, 2, handoff=False), ("sc01_1", 1): _rec("no_handoff", 6, 0),
           ("sc02_1", 1): _rec("completed_after_acting", 9, 3, handoff=True)}
    p = j17p.census_block(pre, n_boot=N_BOOT, seed=7)
    assert p["n_no_handoff_acted"] == 1 and p["n_no_handoff_flag_missing"] == 1
    assert p["categories"]["no_handoff"]["n"] == 2 and p["categories"]["no_handoff"]["share"] == pytest.approx(2 / 3)


def test_census_section_in_world(world):
    arms = world["report"]["term"]["arms"]
    assert set(arms) == set(j17p.CENSUS_ARMS)
    noop = arms["noop"]
    assert noop["categories"]["stopped_before_acting"]["n"] == 16
    assert noop["categories"]["stopped_before_acting"]["ci95_scenario"] == [1.0, 1.0]
    assert noop["median_acted"] == 0.0 and noop["zero_acted_by_error_type"] == {"none": 16}
    assert arms["advise_k10"]["categories"]["limit"]["n"] == 1
    assert arms["advise_k10"]["categories"]["limit"]["share"] == pytest.approx(1 / 16)
    assert arms["takeover_k10"]["categories"]["other"]["n"] == 1
    assert arms["takeover_k10"]["zero_acted_by_error_type"] == {"parse_error": 1}
    assert arms["sft_plan_bplus"]["categories"]["stopped_before_acting"]["n"] == 1
    m6 = arms["prefix_c81_bplus_m6"]
    assert m6["n_scored"] == 24 and m6["seeds"] == [1, 2, 3]
    assert m6["categories"]["no_handoff"]["n"] == 1 and m6["n_handoff_flag_differs_from_j10_reader"] == 1
    assert m6["action_kinds_total"] == {"CODE": 23, "COMPLETE": 23, "REPORT": 1}
    assert arms["exec_alone_base"]["n_crash_dropped"] == 1 and arms["exec_alone_base"]["n_scored"] == 15
    high = arms["planner_alone_c81_high"]
    assert high["acting_actor"] == {"planner": 16} and high["median_acted"] == 1.0
    assert high["categories"]["limit"]["n"] == 1 and high["categories"]["completed_after_acting"]["n"] == 15


# ---- A: tailoring x plan ------------------------------------------------------
def test_plantax_section_in_world(world):
    a = world["report"]["plantax"]
    assert a["pairing"]["n_keys"] == 15 and a["pairing"]["seeds"] == [1, 2]
    c = a["contrasts"]
    for cid, want in (("plan_gain_tailored", 25.0), ("plan_gain_base", 0.0), ("did1", 25.0), ("g_plan", 50.0),
                      ("g_act_m6", 10.0), ("g_act_m11", 10.0), ("did2_m6", 40.0), ("did2_m9", 40.0), ("did2_m11", 40.0)):
        for metric in ("goal_pass", "tgc"):
            obj = c[cid][metric]
            assert obj["diff_pp"] == pytest.approx(want, abs=1e-6), (cid, metric)
            assert obj["ci95_pp_scenario"] == pytest.approx([want, want], abs=1e-6)
            assert obj["n_pairs"] == 15
    assert c["did1"]["definition"] == "(sft_plan_bplus - exec_alone_bplus) - (prompt_only_base - exec_alone_base)"
    assert c["did1"]["goal_pass"]["p_signflip_two_sided"] == pytest.approx(0.125)  # 2 of 2**4 patterns
    assert c["plan_gain_base"]["goal_pass"]["p_two_sided"] == 1.0
    assert c["did1"]["goal_pass"]["means_on_pairs"]["sft_plan_bplus"] == pytest.approx(0.75)
    sb = a["sensitivity_same_build"]
    assert sb["n_keys"] == 15
    assert sb["plan_gain_tailored_same_build"]["goal_pass"]["diff_pp"] == pytest.approx(12.5)
    assert sb["did1_same_build"]["goal_pass"]["diff_pp"] == pytest.approx(12.5)
    q = a["qwen_floor"]
    assert q["n_keys"] == 16 and q["n_keys_goal_pass_identical"] == 16
    assert q["plan_gain"]["goal_pass"]["diff_pp"] == pytest.approx(0.0)
    pid = a["plan_identity"]
    assert pid["sft_plan_bplus vs prompt_only_base"]["n_identical"] == 15
    assert pid["qwen_prompt_only vs prompt_only_base"]["n_differ"] == 1
    assert pid["qwen_prompt_only vs prompt_only_base"]["differ_examples"] == ["sc00_1/1"]


# ---- C: the high-effort ceiling ---------------------------------------------------
def test_planner_token_totals(world):
    path = world["root"] / "t_planner_alone_c81_high" / "planner_alone" / "1" / "sc00_1" / "events.jsonl"
    got = j17p.planner_token_totals(path)
    assert got == {"input_tokens": 2000.0, "cached_input_tokens": 800.0, "output_tokens": 200.0,
                   "reasoning_output_tokens": 100.0, "n_usage_records": 2.0}
    assert j17p.planner_token_totals(world["root"] / "absent.jsonl")["n_usage_records"] == 0.0


def test_cost_rows_by_hand(world):
    card = j17p._j12().load_price_card(world["prices"])
    rows, info = j17p.cost_rows("high", world["root"] / "t_planner_alone_c81_high" / "planner_alone", (1, 2), card)
    assert info["n_rows"] == 16 and len(rows) == 16
    r = rows[("sc01_1", 1)]
    assert r["hosted_calls_per_episode"] == 2.0
    assert r["usd_per_episode"] == pytest.approx(2 * USD_PER_CALL)
    assert r["input_tokens"] == 2000.0


def test_cost_block_by_hand():
    keys = set(ONE_PER_SCENARIO)
    high = {k: {"hosted_calls_per_episode": 2.0, "usd_per_episode": 0.4, "input_tokens": 10.0,
                "cached_input_tokens": 4.0, "output_tokens": 2.0, "reasoning_output_tokens": 1.0} for k in keys}
    med = {k: {a: v / 2 for a, v in row.items()} for k, row in high.items()}
    med[("sc00_1", 1)]["usd_per_episode"] = None
    got = j17p.cost_block(high, med, keys, n_boot=N_BOOT, seed=j17p.BOOTSTRAP_SEED)
    calls = got["hosted_calls_per_episode"]
    assert calls["mean_high"] == 2.0 and calls["mean_medium"] == 1.0 and calls["ratio_high_over_medium"] == 2.0
    assert calls["ratio_ci95_scenario"] == [2.0, 2.0] and calls["ratio_ci95_task"] == [2.0, 2.0]
    assert calls["diff_high_minus_medium"] == 1.0 and calls["n_pairs"] == 4
    assert got["usd_per_episode"]["n_pairs"] == 3 and got["usd_per_episode"]["n_dropped_missing"] == 1


def test_ceilhi_section_in_world(world):
    c = world["report"]["ceilhi"]
    assert c["n_keys"] == 16
    assert c["quality"]["goal_pass"]["diff_pp"] == pytest.approx(10.0)
    assert c["quality"]["goal_pass"]["ci95_pp_scenario"] == pytest.approx([10.0, 10.0])
    # TGC: 15 keys at 0.9 - 0.8, one limit key at 0 - 0.8: (15 x 0.1 - 0.8) / 16 = 0.04375
    assert c["quality"]["tgc"]["diff_pp"] == pytest.approx(4.375)
    assert c["limit_rates"]["high"]["all_scored"] == {"n": 16, "n_limit": 1, "rate": 0.0625}
    assert c["limit_rates"]["medium"]["paired"] == {"n": 16, "n_limit": 0, "rate": 0.0}
    assert c["n_crash_seeds_1_2"] == {"high": 0, "medium": 0}
    assert c["run_settings"]["high"] == {"plan_effort_recorded": {"high": 16}, "per_step_timeout_s": {"300": 16},
                                         "max_planner_calls": {"81": 16}}
    assert c["run_settings"]["medium"]["per_step_timeout_s"] == {"120": 16}  # seed 3 is not read here
    axes = c["cost"]["axes"]
    assert c["cost"]["n_keys"] == 16
    assert axes["hosted_calls_per_episode"]["ratio_high_over_medium"] == pytest.approx(2.0)
    assert axes["usd_per_episode"]["mean_high"] == pytest.approx(2 * USD_PER_CALL)
    assert axes["usd_per_episode"]["mean_medium"] == pytest.approx(USD_PER_CALL)
    assert axes["cached_input_tokens"]["mean_high"] == 800.0 and axes["cached_input_tokens"]["mean_medium"] == 400.0
    assert axes["output_tokens"]["ratio_ci95_scenario"] == pytest.approx([2.0, 2.0])
    ni = c["ni_reread"]
    assert ni["n_keys"] == 16 and ni["margin_pp"] == 7.0
    hb = ni["high_minus_prefix_c81_bplus_m11"]["goal_pass"]
    assert hb["diff_pp"] == pytest.approx(5.0) and hb["reading"] == "holds" and hb["threshold_pp"] == 7.0
    assert hb["p_signflip_two_sided"] == pytest.approx(0.125)  # shifted constant 0.05 - 0.07
    hz = ni["high_minus_prefix_c81_zs_m11"]["goal_pass"]
    assert hz["diff_pp"] == pytest.approx(10.0) and hz["reading"] == "fails" and hz["reading_task"] == "fails"
    assert ni["medium_minus_prefix_c81_bplus_m11"]["goal_pass"]["diff_pp"] == pytest.approx(-5.0)
    assert ni["medium_minus_prefix_c81_zs_m11"]["goal_pass"]["reading"] == "holds"


# ---- ledger confirmation and the report ---------------------------------------------
def test_ledger_checks_in_world(world):
    rows = world["report"]["ledger_confirmation"]
    assert [r["ledger"] for r in rows] == ["T-1", "T-2"]  # T-3 names no arm here
    assert rows[0]["match"] is True and rows[0]["recomputed_goal_pass_mean"] == 0.75 and rows[0]["n"] == 16
    assert rows[1]["match"] is False and rows[1]["reported"] == 0.7


def test_build_report_status_provenance_and_exit(world):
    rep = world["report"]
    assert world["code"] == 0 and rep["status"] == "COMPLETE"
    assert rep["warnings"] == [f"arm {label}: 8 tasks observed, not 57" for label in world["spec"]]
    prov = rep["provenance"]["sft_plan_bplus"]
    assert prov["n_scored"] == 16 and prov["by_campaign"]["t_sft_plan_bplus"]["plan_source"] == {
        "replayed:hj1b_planner_20260915": 16}
    assert prov["by_campaign"]["t_sft_plan_bplus"]["executor_adapter_episodes"] == {"sft_b_plus|lora=sft_b_plus": 16}
    assert rep["provenance"]["prefix_bplus_m6"]["by_campaign"]["t_prefix_bplus_m6"]["prefix_source_campaign"] == {
        "hj1b_planner_20260915": 16}
    assert rep["settings"]["seed"] == j17p.BOOTSTRAP_SEED and rep["settings"]["n_boot"] == N_BOOT


def test_build_report_missing_campaign_exits_1(world, tmp_path):
    spec = {"noop": {"campaigns": ("absent_campaign",), "seeds": (1, 2), "role": "executor"}}
    rep, code = j17p.build_report(results_root=world["root"], arms_spec=spec, n_boot=N_BOOT, checks=())
    assert code == 1 and rep["status"] == "INCOMPLETE"
    assert "arm noop: campaign absent_campaign is missing" in rep["warnings"]
    assert "plantax" not in rep and "ceilhi" not in rep and rep["term"]["arms"]["noop"]["n_scored"] == 0


def test_main_refuses_and_writes(world, tmp_path, monkeypatch, capsys):
    assert j17p.main(["--out", str(tmp_path / "o.json"), "--results-root", "/tmp/test_normal"]) == 2
    assert j17p.main(["--out", "/scratch/n12194778/o.json", "--results-root", str(world["root"])]) == 2
    monkeypatch.setattr(j17p, "ARMS", {"noop": world["spec"]["noop"]})
    out = tmp_path / "rep" / "o.json"
    assert j17p.main(["--out", str(out), "--results-root", str(world["root"]), "--n-boot", "50"]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["term"]["arms"]["noop"]["categories"]["stopped_before_acting"]["n"] == 16
    assert '"status": "REFUSED"' in capsys.readouterr().out
