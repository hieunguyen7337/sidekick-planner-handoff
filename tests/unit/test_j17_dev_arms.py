"""J17 dev arms (brief DR-1): every section on hand-built data, expected values worked by hand.

World: 4 scenarios (sc00-sc03) x 2 tasks (_1, _2) x seeds {1, 2} = 16 keys per arm, in the runner's layout
<root>/<campaign>/<system>/<seed>/<task>/{result.json, events.jsonl, manifest.json}, under the REAL campaign
names, so main() runs end to end. Every arm's goal_pass is a constant (GP) except X1's two round-1 keys
(goal_pass 0), so most paired differences are constants and their intervals collapse onto the point:

  neutral_k1 - correction_k1 = 0.60 - 0.50 = +10 pp on 16 pairs; BOTH arms' campaigns also hold 8 seed-3
      rows at goal_pass 0.0, which must be ignored (pairing them would give 24 pairs and 16 x 10 / 24 pp);
  structured_k1 - correction_k1 = (14 x 0.75 + 2 x 0) / 16 - 0.50 = +15.625 pp; without the two round-1 keys
      +25 pp on 14 pairs;
  self_plan - floor = 0.40 - 0.70 = -30 pp on 15 pairs: the floor crashed on (sc03_2, 2), so n_dropped = 1.

Pricing, under the test price card (luna 0.20 / 0.02 / 1.20 USD per 1M tokens): a live call U (1000 input,
400 cached, 100 output, 50 reasoning) costs 600 x 0.2e-6 + 400 x 0.02e-6 + 150 x 1.2e-6 = 3.08e-4; the hj1b
source plan of task i (0..7) is U with 100 (i + 1) output tokens and costs 1.28e-4 + (100 (i + 1) + 50) x 1.2e-6,
mean 7.28e-4 over the 8 tasks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis import j17_dev_arms as dv

SCENARIOS = [f"sc{i:02d}" for i in range(4)]
TASKS = [f"{s}_{j}" for s in SCENARIOS for j in (1, 2)]
TASK_INDEX = {t: i for i, t in enumerate(TASKS)}
WRONG_MAP = {t: TASKS[(i + 2) % len(TASKS)] for i, t in enumerate(TASKS)}  # always another scenario
N_BOOT = 200
PRICES_YAML = ('schedule_date: "2026-09-15"\nmodels:\n  gpt-5.6-luna: {input: 0.20, cached_input: 0.02, output: 1.20}\n'
               "local:\n  usd_per_gpu_hour: 2.50\n")
U = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 1000, "cached_input_tokens": 400,
     "output_tokens": 100, "reasoning_output_tokens": 50, "n_calls": 1}
USD_PER_CALL = 600 * 0.20e-6 + 400 * 0.02e-6 + 150 * 1.20e-6  # 3.08e-4


def plan_usd(task: str) -> float:
    return 600 * 0.20e-6 + 400 * 0.02e-6 + (100 * (TASK_INDEX[task] + 1) + 50) * 1.20e-6


MEAN_PLAN_USD = sum(plan_usd(t) for t in TASKS) / len(TASKS)  # 7.28e-4
GP = {"neutral_k1": 0.60, "structured_k1": 0.75, "structured_k10": 0.70, "correction_k1": 0.50,
      "correction_k10": 0.55, "neutral_k10": 0.65, "takeover_k10": 0.80, "show_k10": 0.60, "prefix_m11": 0.85,
      "self_plan": 0.40, "wrong_task_plan": 0.10, "floor": 0.70, "executor_alone": 0.20}
SYSTEM = {"prefix_m11": "prefix_handoff", "self_plan": "sft_plan", "wrong_task_plan": "sft_plan", "floor": "sft_plan",
          "executor_alone": "executor_alone"}
CHANNEL = ("neutral_k1", "structured_k1", "structured_k10", "correction_k1", "correction_k10", "neutral_k10",
           "takeover_k10", "show_k10")
SEED3_ARMS = ("neutral_k1", "correction_k1")  # both arms of one contrast carry seed-3 rows
X1_EARLY = {("sc00_1", 1), ("sc01_1", 1)}
FLOOR_CRASH = ("sc03_2", 2)
SP_PARSE = ("sc02_2", 2)
EXEC_LIMIT = ("sc00_2", 1)
FENCED = "GOAL: set x\nSTEPS:\n```python\nx = 1\n```\nCHECK: x"
ROUND1_LOG = """[hj12] ---- full campaign (dev_advise_structured_fixed_k_1_fullctx_20260924) ----
{
  "campaign_id": "dev_advise_structured_fixed_k_1_fullctx_20260924",
  "n": 16
}
[hj12] ---- summary + manifest (dev_advise_structured_fixed_k_1_fullctx_20260924) ----
{
  "campaign_id": "dev_advise_structured_fixed_k_1_fullctx_20260924",
  "errors": {
    "crash": 14,
    "none": 2
  },
  "n_broken": 14,
  "planner_calls_live_total": 40,
  "ledger_totals": {
    "planner_calls_total": 40,
    "usd_total": 0.5
  }
}
[manifest] wrote x
"""


def _ev(event_type, actor, step, task, seed, usage=None, **payload):
    ev = {"event_type": event_type, "actor": actor, "step": step, "task_id": task, "seed": seed, "payload": payload}
    if usage is not None:
        ev["usage"] = usage
    return ev


def _exec(step, task, seed, kind="CODE"):
    return _ev("action", "executor", step, task, seed, usage={"model": "sft_b_plus", "provider": "vllm", "raw": {}},
               kind=kind, code="x = 1" if kind == "CODE" else None, message=None)


def _write(dest: Path, name: str, obj) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if name == "events.jsonl":
        (dest / name).write_text("".join(json.dumps(e) + "\n" for e in obj), encoding="utf-8")
    else:
        (dest / name).write_text(json.dumps(obj) + "\n", encoding="utf-8")


def source_path(root: Path, task: str, seed: int) -> Path:
    return root / dv.PACKET_SOURCE / dv.PACKET_SYSTEM / str(seed) / task / "events.jsonl"


def write_source(root: Path) -> None:
    """hj1b: a plan (U with 100 (i + 1) output tokens), two planner CODE actions (U each) and COMPLETE."""
    for seed in (1, 2):
        for task in TASKS:
            plan_u = dict(U, output_tokens=100 * (TASK_INDEX[task] + 1))
            evs = [_ev("run_start", "system", 0, task, seed, limits={}),
                   _ev("plan", "planner", 0, task, seed, usage=plan_u, packet={"task_id": task, "plan_steps": ["p"]}),
                   _ev("action", "planner", 1, task, seed, usage=dict(U), kind="CODE", code="a"),
                   _ev("action", "planner", 2, task, seed, usage=dict(U), kind="CODE", code="b"),
                   _ev("action", "planner", 3, task, seed, kind="COMPLETE")]
            _write(source_path(root, task, seed).parent, "events.jsonl", evs)


def cached_plan(root: Path, task: str, seed: int, source_task: str):
    usage = {"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0, "cached_input_tokens": 0,
             "output_tokens": 0, "reasoning_output_tokens": 0, "n_calls": 1,
             "raw": {"cached_from": str(source_path(root, source_task, seed)), "packet_task_source": source_task}}
    return _ev("plan", "planner", 0, task, seed, usage=usage, packet={"task_id": source_task, "plan_steps": ["p"]})


def episode(root: Path, label: str, task: str, seed: int):
    """(result row, events, manifest) of one synthetic episode."""
    key = (task, seed)
    gp = GP[label]
    err = {("floor", FLOOR_CRASH): "crash", ("self_plan", SP_PARSE): "parse_error",
           ("executor_alone", EXEC_LIMIT): "limit"}.get((label, key))
    if seed == 3 or (label == "structured_k1" and key in X1_EARLY):
        gp = 0.0
    evs = [_ev("run_start", "system", 0, task, seed, limits={"max_steps": 40})]
    n_int = ledger = n_calls = 0
    usd = 0.0
    if label in CHANNEL:
        n_int = 2 if label.endswith("_k1") else 1
        evs.append(cached_plan(root, task, seed, task))
        text = FENCED if label.startswith("structured") else "Consider re-reading the API docs first."
        for j in range(1, n_int + 1):
            evs.append(_ev("intervention", "planner", j, task, seed, usage=dict(U), correction=text, forced=False,
                           n_interventions=j))
            evs.append(_exec(j, task, seed))
        ledger = n_calls = 1 + n_int
        usd = n_int * USD_PER_CALL
        if label == "structured_k1" and key in X1_EARLY:
            usd = 2 * USD_PER_CALL
    elif label == "prefix_m11":
        evs.append(_ev("report", "system", 2, task, seed, effective_m=2, handoff_occurred=True, n_source_actions=3,
                       source_campaign=str(root / dv.PACKET_SOURCE)))
        evs.append(_exec(3, task, seed))
        n_calls = 3
    elif label in ("floor", "wrong_task_plan"):
        evs.append(cached_plan(root, task, seed, task if label == "floor" else WRONG_MAP[task]))
        ledger = n_calls = 1
    elif label == "self_plan":
        if key == SP_PARSE:
            evs.append(_ev("error", "planner", 0, task, seed, usage={"provider": "mock", "model": "sft_b_plus",
                                                                    "n_calls": 1}, method="plan", raw_output="??"))
        else:
            evs.append(_ev("plan", "planner", 0, task, seed,
                           usage={"model": "sft_b_plus", "provider": "vllm", "input_tokens": 5000,
                                  "cached_input_tokens": 0, "output_tokens": 300, "reasoning_output_tokens": 0,
                                  "n_calls": 1},
                           packet={"task_id": task, "plan_steps": ["own"]}))
        ledger = n_calls = 1
    if label != "self_plan" or key != SP_PARSE:
        evs.append(_exec(9, task, seed, kind="COMPLETE"))
    row = {"run_id": f"x/{task}/{seed}", "task_id": task, "seed": seed, "system": SYSTEM.get(label, "fixed_k"),
           "goal_pass_rate": gp, "tgc": 0.0 if err else gp, "success": gp >= 0.75 and not err, "steps": 3,
           "n_planner_calls": n_calls, "n_asks": 0, "n_interventions": n_int, "error_type": err, "sgc": None,
           "totals": {"planner_calls_total": ledger, "planner_tokens_total": 0, "usd_total": usd,
                      "per_actor": {"planner": {"input_tokens": 1000 * n_int, "cached_input_tokens": 400 * n_int,
                                                "output_tokens": 100 * n_int, "reasoning_output_tokens": 50 * n_int,
                                                "n_calls": ledger}}}}
    early = label == "structured_k1" and key in X1_EARLY
    manifest = {"created_at": "2026-09-28T00:00:00+00:00",
                "provenance": {"git_sha": ("1f1f991" if early else "72e00ce") + "0" * 33, "git_dirty": early,
                               "split": "dev", "correct_prompt": dv.ARM_INFO[label]["prompt"], "planner_type": "codex"}}
    return row, evs, manifest


def build_world(root: Path, skip: tuple[str, ...] = ()) -> None:
    write_source(root)
    for label, spec in dv.ARMS.items():
        if label in skip:
            continue
        seeds = (1, 2, 3) if label in SEED3_ARMS else (1, 2)
        for seed in seeds:
            for task in TASKS:
                row, evs, man = episode(root, label, task, seed)
                dest = root / spec["campaigns"][0] / SYSTEM.get(label, "fixed_k") / str(seed) / task
                _write(dest, "result.json", row)
                _write(dest, "events.jsonl", evs)
                _write(dest, "manifest.json", man)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("results")
    build_world(root)
    aux = tmp_path_factory.mktemp("aux")
    prices = aux / "prices.yaml"
    prices.write_text(PRICES_YAML, encoding="utf-8")
    log = aux / "round1.aqua.out"
    log.write_text(ROUND1_LOG, encoding="utf-8")
    out = tmp_path_factory.mktemp("out") / "dev_arms.report.json"
    code = dv.main(["--out", str(out), "--results-root", str(root), "--n-boot", str(N_BOOT), "--prices", str(prices),
                    "--x1-round1-log", str(log)])
    report = json.loads(out.read_text(encoding="utf-8"))
    return {"root": root, "prices": prices, "log": log, "out": out, "code": code, "report": report}


# ---- refusal ------------------------------------------------------------------
def test_refuse_path_markers():
    assert "_test_" in dv.refuse_path("/scratch/x/results/bfcl_prefix_test_m6_20260925")
    assert "test_normal" in dv.refuse_path("/scratch/x/results/j10_test_normal_arm")
    assert "test_challenge" in dv.refuse_path("/tmp/test_challenge_run")
    assert "J10/J11/J12" in dv.refuse_path("/tmp/results/j12_depth_arm")
    assert dv.refuse_path("/tmp/results/hj12_prefix_m11_20260923") is None
    assert dv.refuse_path("/tmp/results/dev_sft_plan_wrongtask_bplus_20260924") is None


def test_main_refuses_heldout_root_and_scratch_out(tmp_path_factory, capsys):
    out = tmp_path_factory.mktemp("refuse") / "r.json"
    assert dv.main(["--out", str(out), "--results-root", "/tmp/nowhere/test_normal"]) == 2
    assert dv.main(["--out", str(out), "--results-root", "/tmp/nowhere/results_test_x"]) == 2
    assert dv.main(["--out", "/scratch/n12194778/dev_arms.report.json", "--results-root", "/tmp/nowhere"]) == 2
    assert not out.exists()
    assert capsys.readouterr().out.count('"REFUSED"') == 3


# ---- the report as written by main ---------------------------------------------
def test_main_writes_json_and_md(world):
    assert world["code"] == 0
    rep = world["report"]
    assert rep["status"] == "COMPLETE"
    assert rep["protocol"] == dv.PROTOCOL
    md = world["out"].with_suffix(".md")
    assert md.is_file()
    text = md.read_text(encoding="utf-8")
    for cid in rep["contrasts"]:
        assert cid in text
    meta = rep["meta"]
    assert meta["seeds"] == [1, 2] and meta["n_boot"] == N_BOOT and meta["bootstrap_seed"] == 20260924
    assert meta["argv"][0] == "scripts/analysis/j17_dev_arms.py" and "--results-root" in meta["argv"]
    assert "git_sha" in meta and meta["status"] == "exploratory" and meta["split"] == "dev"


def test_every_contrast_is_labelled_and_carries_limits(world):
    rep = world["report"]
    assert list(rep["contrasts"]) == [c["id"] for c in dv.CONTRASTS]
    blocks = list(rep["contrasts"].values()) + list(rep["x1_sensitivity"]["contrasts"].values())
    blocks += list(rep["cost_contrasts"].values())
    for c in blocks:
        assert c["status"] == "exploratory" and c["split"] == "dev"
        assert {"left", "right"} <= set(c["limit_rate"])
    for c in rep["contrasts"].values():
        assert {"goal_pass", "tgc", "sgc", "n_pairs", "n_dropped"} <= set(c)
        assert c["goal_pass"]["metric"] == "goal_pass"


def test_pairing_is_seeds_1_2_and_seed3_is_ignored(world):
    rep = world["report"]
    for label, arm in rep["arms"].items():  # every arm AND comparator is restricted to seeds 1 and 2
        assert arm["seeds"] == [1, 2], label
        assert arm["n"] + arm["n_crash"] == 16, label
        assert arm["n_other_seed_rows_ignored"] == (8 if label in SEED3_ARMS else 0), label
    for label in SEED3_ARMS:
        arm = rep["arms"][label]
        assert arm["n"] == 16 and arm["goal_pass"] == pytest.approx(GP[label])  # the seed-3 rows are 0.0
    c = rep["contrasts"]["neutral_k1_minus_correction_k1"]
    assert c["n_pairs"] == 16 and c["n_dropped"] == 0
    assert c["goal_pass"]["diff_pp"] == pytest.approx(10.0)
    assert c["goal_pass"]["ci95_pp_scenario"] == pytest.approx([10.0, 10.0])
    assert c["goal_pass"]["ci95_pp_task"] == pytest.approx([10.0, 10.0])


def test_crash_is_dropped_and_counted(world):
    c = world["report"]["contrasts"]["self_plan_minus_floor"]
    assert c["n_pairs"] == 15 and c["n_expected"] == 16 and c["n_dropped"] == 1
    assert c["dropped"]["right"]["crash"] == 1 and c["dropped"]["left"]["crash"] == 0
    assert c["goal_pass"]["diff_pp"] == pytest.approx(-30.0)
    assert world["report"]["arms"]["floor"]["n_crash"] == 1


def test_limit_rate_beside_contrasts(world):
    c = world["report"]["contrasts"]["wrong_task_plan_minus_executor_alone"]
    assert c["limit_rate"]["right"]["paired"] == {"n": 16, "n_limit": 1, "rate": pytest.approx(1 / 16)}
    assert c["limit_rate"]["left"]["paired"]["n_limit"] == 0
    assert c["goal_pass"]["diff_pp"] == pytest.approx(-10.0)
    assert world["report"]["arms"]["executor_alone"]["limit"]["n_limit"] == 1


def test_build_caveat_only_on_executor_alone_contrasts(world):
    cs = world["report"]["contrasts"]
    assert cs["self_plan_minus_executor_alone"]["build_caveat"] == dv.BUILD_CAVEAT
    assert cs["wrong_task_plan_minus_executor_alone"]["build_caveat"] == dv.BUILD_CAVEAT
    assert "build_caveat" not in cs["self_plan_minus_floor"]


def test_sgc_contrast(world):
    # success iff goal_pass >= 0.75 and no error: prefix_m11 passes every unit, neutral_k1 none.
    s = world["report"]["contrasts"]["neutral_k1_minus_prefix_m11"]["sgc"]
    assert s["n_pairs"] == 8 and s["diff_pp"] == pytest.approx(-100.0)
    assert world["report"]["arms"]["prefix_m11"]["sgc"]["mean"] == pytest.approx(1.0)


# ---- X1 ------------------------------------------------------------------------
def test_x1_exclusion_sensitivity(world):
    rep = world["report"]
    main = rep["contrasts"]["structured_k1_minus_correction_k1"]["goal_pass"]
    assert main["diff_pp"] == pytest.approx(15.625)
    sens = rep["x1_sensitivity"]
    assert sens["excluded_keys"] == ["sc00_1/1", "sc01_1/1"]
    assert set(sens["contrasts"]) == {"structured_k1_minus_correction_k1", "structured_k1_minus_neutral_k1",
                                      "structured_k1_minus_structured_k10", "structured_k1_minus_prefix_m11"}
    s = sens["contrasts"]["structured_k1_minus_correction_k1"]
    assert s["n_pairs"] == 14 and s["n_expected"] == 14
    assert s["goal_pass"]["diff_pp"] == pytest.approx(25.0)
    assert s["goal_pass"]["ci95_pp_scenario"] == pytest.approx([25.0, 25.0])


def test_x1_provenance_and_round1_spend(world):
    x1 = world["report"]["x1_provenance"]
    assert x1["n_early"] == 2 and x1["n_late"] == 14
    assert x1["early_keys"] == ["sc00_1/1", "sc01_1/1"]
    assert all(r["git_dirty"] is True and r["n_run_start"] == 1 for r in x1["early_episodes"])
    r1 = x1["round1"]["summary"]
    assert r1["ledger_planner_calls_total"] == 40 and r1["ledger_usd_total"] == pytest.approx(0.5)
    assert r1["errors"] == {"crash": 14, "none": 2}
    assert r1["source"].endswith(":7-19")
    absent = x1["round1_spend_not_in_result_json"]
    assert absent["calls"] == 40 - 2 * 3
    assert absent["usd"] == pytest.approx(0.5 - 2 * 2 * USD_PER_CALL, abs=1e-6)


def test_parse_round1_log_missing(tmp_path_factory):
    d = tmp_path_factory.mktemp("nolog")
    assert dv.parse_round1_log(d / "absent.out", "c") is None
    (d / "other.out").write_text("nothing here\n", encoding="utf-8")
    assert dv.parse_round1_log(d / "other.out", "c") is None


# ---- pricing --------------------------------------------------------------------
def test_channel_arm_both_conventions(world):
    cost = world["report"]["arms"]["neutral_k1"]["cost"]
    assert cost["published"]["usd_per_episode"] == pytest.approx(2 * USD_PER_CALL, abs=1e-6)
    assert cost["attributed"]["usd_per_episode"] == pytest.approx(2 * USD_PER_CALL + MEAN_PLAN_USD, abs=1e-6)
    assert cost["published"]["hosted_calls_per_episode"] == pytest.approx(3.0)
    assert cost["published"]["calls_live_per_episode"] == pytest.approx(2.0)  # ledger 3 minus the cached plan
    calls = world["report"]["arms"]["neutral_k1"]["calls"]
    assert calls == {"ledger": pytest.approx(3.0), "n_planner": pytest.approx(3.0), "cached": pytest.approx(1.0),
                     "ledger_minus_cached": pytest.approx(2.0), "live": pytest.approx(2.0)}
    # a control's local plan call is in the ledger but is not a hosted call
    sp = world["report"]["arms"]["self_plan"]["calls"]
    assert sp["ledger"] == pytest.approx(1.0) and sp["ledger_minus_cached"] == pytest.approx(1.0)
    assert sp["live"] == 0.0
    wtp = world["report"]["arms"]["wrong_task_plan"]["calls"]
    assert wtp["cached"] == pytest.approx(1.0) and wtp["live"] == 0.0
    assert world["report"]["arms"]["neutral_k1"]["interventions_per_episode"] == pytest.approx(2.0)


def test_cost_ratio_advice_over_prefix(world):
    rep = world["report"]
    prefix = rep["arms"]["prefix_m11"]["cost"]["published"]["usd_per_episode"]
    assert prefix == pytest.approx(MEAN_PLAN_USD + 2 * USD_PER_CALL, abs=1e-6)  # plan + 2 replayed actions
    r = rep["cost_contrasts"]["neutral_k1_over_prefix_m11"]
    assert r["n_keys"] == 16
    usd = r["published"]["usd_per_episode"]
    assert usd["ratio_left_over_right"] == pytest.approx(2 * USD_PER_CALL / (MEAN_PLAN_USD + 2 * USD_PER_CALL), abs=1e-5)
    assert usd["ratio_ci95_scenario"][0] <= usd["ratio_left_over_right"] <= usd["ratio_ci95_scenario"][1]
    assert r["published"]["calls_live_per_episode"]["ratio_left_over_right"] is None  # the prefix has 0 live calls
    att = r["attributed"]["usd_per_episode"]["ratio_left_over_right"]
    assert att == pytest.approx((2 * USD_PER_CALL + MEAN_PLAN_USD) / (MEAN_PLAN_USD + 2 * USD_PER_CALL), abs=1e-5)


def test_self_plan_pricing_both_conventions(world):
    cp = world["report"]["controls_pricing"]["self_plan"]
    for conv in ("live", "attributed"):
        assert cp[conv]["usd_per_episode"] == 0.0 and cp[conv]["hosted_calls_per_episode"] == 0.0
        assert cp[conv]["noncached_tokens_per_episode"] == 0.0
    assert cp["local_plan_calls_total"] == 16  # 15 vllm plans + 1 failed parse (mock record)
    assert cp["n_local_plan_usages_vllm"] == 15 and cp["n_episodes_without_local_plan_usage"] == 1
    assert cp["local_plan_noncached_tokens_per_episode"] == pytest.approx(15 * 5300 / 16)
    assert cp["n_hosted_usage_records"] == 0
    arm = world["report"]["arms"]["self_plan"]
    assert set(arm["cost"]) >= {"live", "attributed"} and arm["cost"]["live"]["usd_per_episode"] == 0.0


def test_wrong_task_plan_pricing_both_conventions(world):
    cp = world["report"]["controls_pricing"]["wrong_task_plan"]
    assert cp["live"] == {"hosted_calls_per_episode": 0.0, "noncached_tokens_per_episode": 0.0,
                          "usd_per_episode": 0.0, "usd_total": 0.0}
    assert cp["attributed"]["hosted_calls_per_episode"] == pytest.approx(1.0)
    assert cp["attributed"]["usd_per_episode"] == pytest.approx(MEAN_PLAN_USD, abs=1e-6)
    assert cp["n_replayed_from_own_task"] == 0 and cp["n_replayed_from_other_task"] == 16
    assert cp["n_replayed_from_same_scenario_other_task"] == 0 and cp["n_source_missing"] == 0


def test_control_cost_row_prices_the_mapped_task_not_the_own_task(world):
    root = world["root"]
    card = dv.j17p._j12().load_price_card(world["prices"])
    task, seed = "sc00_1", 1
    ev = root / dv.ARMS["wrong_task_plan"]["campaigns"][0] / "sft_plan" / str(seed) / task / "events.jsonl"
    row = dv.control_cost_row(ev, card["models"], packet_source=root / dv.PACKET_SOURCE, task_id=task, seed=seed)
    assert row["live"] == {"hosted_calls": 0, "noncached_tokens": 0.0, "usd": 0.0}
    assert row["attributed"]["usd"] == pytest.approx(plan_usd(WRONG_MAP[task]), abs=1e-9)
    assert row["attributed"]["usd"] != pytest.approx(plan_usd(task), abs=1e-9)
    assert row["attributed"]["hosted_calls"] == 1 and row["replayed_from_tasks"] == [WRONG_MAP[task]]
    sp = root / dv.ARMS["self_plan"]["campaigns"][0] / "sft_plan" / str(seed) / task / "events.jsonl"
    row = dv.control_cost_row(sp, card["models"], packet_source=root / dv.PACKET_SOURCE, task_id=task, seed=seed)
    assert row["live"] == row["attributed"] == {"hosted_calls": 0, "noncached_tokens": 0.0, "usd": 0.0}
    assert row["local_plan_calls"] == 1 and row["local_plan_noncached_tokens"] == 5300.0


def test_replayed_plan_sources_are_surfaced(world):
    rep = world["report"]
    hj1b = f"{dv.PACKET_SOURCE}/{dv.PACKET_SYSTEM}"
    cp = rep["controls_pricing"]["wrong_task_plan"]
    assert cp["n_cached_from_outside_packet_source"] == 0 and cp["replayed_from_source_dirs"] == {hj1b: 16}
    rps = rep["replayed_plan_sources"]
    assert rps["wrong_task_plan"]["by_source"] == {hj1b: 16}
    assert rps["wrong_task_plan"]["n_outside_packet_source"] == 0 and rps["wrong_task_plan"]["n_seed_dir_mismatch"] == 0
    assert rps["neutral_k1"]["by_source"] == {hj1b: 24}  # every seed's events are scanned, seed 3 included
    assert rps["self_plan"]["n_cached_plan_usages"] == 0 and rps["self_plan"]["by_source"] == {}
    assert "replayed plan sources" in world["out"].with_suffix(".md").read_text(encoding="utf-8").lower()


def _wrong_plan_events(dest: Path, cached_from: str, task: str = "sc00_1", seed: int = 1) -> Path:
    usage = {"model": "gpt-5.6-luna", "provider": "cache", "input_tokens": 0, "cached_input_tokens": 0,
             "output_tokens": 0, "reasoning_output_tokens": 0, "n_calls": 1, "raw": {"cached_from": cached_from}}
    evs = [_ev("run_start", "system", 0, task, seed, limits={}),
           _ev("plan", "planner", 0, task, seed, usage=usage, packet={"task_id": "x", "plan_steps": ["p"]}),
           _exec(9, task, seed, kind="COMPLETE")]
    _write(dest, "events.jsonl", evs)
    return dest / "events.jsonl"


def test_control_cost_row_counts_a_source_outside_the_packet_source(world, tmp_path_factory):
    root, card = world["root"], dv.j17p._j12().load_price_card(world["prices"])
    other = tmp_path_factory.mktemp("elsewhere") / "hj1b_copy" / dv.PACKET_SYSTEM / "1" / "sc01_2"
    other.mkdir(parents=True)
    (other / "events.jsonl").write_text(source_path(root, "sc01_2", 1).read_text(encoding="utf-8"), encoding="utf-8")
    ev = _wrong_plan_events(tmp_path_factory.mktemp("ep") / "sft_plan" / "1" / "sc00_1", str(other / "events.jsonl"))
    row = dv.control_cost_row(ev, card["models"], packet_source=root / dv.PACKET_SOURCE, task_id="sc00_1", seed=1)
    assert row["n_cached_from_outside_packet_source"] == 1
    assert row["replayed_from_source_dirs"] == [f"hj1b_copy/{dv.PACKET_SYSTEM}"]
    assert row["attributed"]["usd"] == pytest.approx(plan_usd("sc01_2"), abs=1e-9)


@pytest.mark.parametrize("held_out", ["/tmp/nowhere/bfcl_prefix_test_m6/planner_alone/1/sc00_1/events.jsonl",
                                      "/tmp/nowhere/j10_test_normal_arm/planner_alone/1/sc00_1/events.jsonl"])
def test_control_cost_row_refuses_a_held_out_source(world, tmp_path_factory, held_out):
    card = dv.j17p._j12().load_price_card(world["prices"])
    ev = _wrong_plan_events(tmp_path_factory.mktemp("ep_ho") / "sft_plan" / "1" / "sc00_1", held_out)
    with pytest.raises(dv.HeldOutSourceError, match="replayed plan source"):
        dv.control_cost_row(ev, card["models"], packet_source=world["root"] / dv.PACKET_SOURCE, task_id="sc00_1",
                            seed=1)


def _only(label: str) -> tuple[str, ...]:
    return tuple(other for other in dv.ARMS if other != label)


def test_main_refuses_a_held_out_replayed_plan_source(world, tmp_path_factory, capsys):
    root = tmp_path_factory.mktemp("heldout_source")
    build_world(root, skip=_only("structured_k10"))  # a channel arm: j12's attributed pricing would read it
    dest = root / dv.ARMS["structured_k10"]["campaigns"][0] / "fixed_k" / "2" / "sc01_2"
    _wrong_plan_events(dest, "/tmp/nowhere/bfcl_prefix_test_m6/planner_alone/2/sc01_2/events.jsonl",
                       task="sc01_2", seed=2)
    out = tmp_path_factory.mktemp("out_heldout") / "dev_arms.report.json"
    capsys.readouterr()
    code = dv.main(["--out", str(out), "--results-root", str(root), "--n-boot", "50", "--prices", str(world["prices"]),
                    "--x1-round1-log", str(world["log"])])
    assert code == 2 and not out.exists()
    printed = capsys.readouterr().out
    assert '"REFUSED"' in printed and "replayed plan source" in printed and "structured_k10" in printed


def test_main_refuses_a_key_twice_within_one_arm(world, tmp_path_factory, capsys):
    root = tmp_path_factory.mktemp("dup")
    build_world(root, skip=_only("correction_k1"))
    row, _evs, _man = episode(root, "correction_k1", "sc00_1", 1)
    _write(root / dv.ARMS["correction_k1"]["campaigns"][0] / "fixed_k" / "1" / "sc00_1_copy", "result.json", row)
    out = tmp_path_factory.mktemp("out_dup") / "dev_arms.report.json"
    capsys.readouterr()
    code = dv.main(["--out", str(out), "--results-root", str(root), "--n-boot", "50", "--prices", str(world["prices"]),
                    "--x1-round1-log", str(world["log"])])
    assert code == 2 and not out.exists()
    printed = capsys.readouterr().out
    assert '"REFUSED"' in printed and "twice" in printed and "correction_k1" in printed


# ---- content, BY, confirmation ---------------------------------------------------
def test_advice_content(world):
    content = world["report"]["advice_content"]
    assert set(content) == set(dv.ADVICE_ARMS)
    s = content["structured_k1"]
    assert s["n_interventions"] == 32 and s["share_fenced_code"]["share"] == pytest.approx(1.0)
    assert s["median_chars"] == len(FENCED)
    assert content["correction_k10"]["n_interventions"] == 16
    assert content["correction_k10"]["share_fenced_code"]["share"] == pytest.approx(0.0)
    assert "content_block" in s["source_function"]


def _by_by_hand(ps: dict[str, float]) -> dict[str, float]:
    """BY step-up written out independently of cluster_inference: p_(r) m H(m) / r, min over ranks >= r, cap 1."""
    m = len(ps)
    h = sum(1.0 / j for j in range(1, m + 1))
    ranked = sorted(ps.items(), key=lambda kv: kv[1])
    out: dict[str, float] = {}
    for r, (cid, _p) in enumerate(ranked, start=1):
        out[cid] = min(1.0, min(p * m * h / rr for rr, (_c, p) in enumerate(ranked, start=1) if rr >= r))
    return out


def test_by_fdr_family(world):
    fdr = world["report"]["by_fdr"]
    assert fdr["m_p_two_sided"] == len(dv.CONTRASTS)
    assert set(fdr["rows"]) == {c["id"] for c in dv.CONTRASTS}
    assert fdr["decision_bearing"] is False
    rows = fdr["rows"]
    for p_key, tag in (("p_two_sided", "p_by"), ("p_signflip_two_sided", "p_by_signflip")):
        want = _by_by_hand({cid: r[p_key] for cid, r in rows.items() if r[p_key] is not None})
        for cid, r in rows.items():  # the report's p_by is BY of the report's own p, not of the other p
            assert r[tag] == (None if cid not in want else pytest.approx(want[cid], abs=1e-4)), (cid, tag)


def test_by_fdr_block_hand_values():
    # m = 3 usable bootstrap p, H(3) = 11/6, m H = 5.5: ranks 0.005 -> 0.0275; 0.03 -> 0.0825, lowered by the
    # step-up to rank 3's 0.04 x 5.5 / 3 = 0.073333. Sign-flip p: m = 4, H(4) = 25/12, m H = 8.3333: 0.001 ->
    # 0.008333; 0.02 -> 0.083333; 0.20 -> 0.555556; 0.5 -> 1.041667, capped at 1.
    p = {"a": (0.005, 0.20), "b": (0.04, 0.001), "c": (0.03, 0.5), "d": (None, 0.02)}
    contrasts = {cid: {"goal_pass": {"diff_pp": 1.0, "p_two_sided": pb, "p_signflip_two_sided": ps}}
                 for cid, (pb, ps) in p.items()}
    fdr = dv.by_fdr_block(contrasts, alpha=0.05)
    assert fdr["m_p_two_sided"] == 3 and fdr["m_p_signflip_two_sided"] == 4
    rows = fdr["rows"]
    assert rows["a"]["p_by"] == pytest.approx(0.0275)
    assert rows["b"]["p_by"] == pytest.approx(0.22 / 3)
    assert rows["c"]["p_by"] == pytest.approx(0.22 / 3)
    assert rows["d"]["p_by"] is None and rows["d"]["p_by_survives_alpha"] is None
    assert [rows[c]["p_by_survives_alpha"] for c in "abc"] == [True, False, False]
    assert rows["a"]["p_by_signflip"] == pytest.approx(0.2 * 25 / 9)
    assert rows["b"]["p_by_signflip"] == pytest.approx(0.001 * 25 / 3)
    assert rows["c"]["p_by_signflip"] == 1.0
    assert rows["d"]["p_by_signflip"] == pytest.approx(0.02 * 25 / 6)
    assert [rows[c]["p_by_signflip_survives_alpha"] for c in "abcd"] == [False, True, False, False]


def test_prefix_m11_identity_names_the_campaign(world):
    pm = world["report"]["prefix_m11_identity"]
    assert pm["campaigns"] == ["hj12_prefix_m11_20260923"] and pm["system"] == "prefix_handoff"
    assert pm["recomputed_p2_diff_pp"] == pytest.approx(-35.0)  # 0.50 - 0.85 in the synthetic world
    assert pm["n_pairs_p2"] == 16


# ---- a missing campaign -------------------------------------------------------------
def test_missing_campaign_exits_1_with_a_warning(tmp_path_factory, world):
    root = tmp_path_factory.mktemp("partial")
    build_world(root, skip=("wrong_task_plan",))
    out = tmp_path_factory.mktemp("out_partial") / "dev_arms.report.json"
    code = dv.main(["--out", str(out), "--results-root", str(root), "--n-boot", "50", "--prices", str(world["prices"]),
                    "--x1-round1-log", str(world["log"])])
    assert code == 1
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["status"] == "INCOMPLETE"
    assert any("dev_sft_plan_wrongtask_bplus_20260924 is missing" in w for w in rep["warnings"])
    assert rep["contrasts"]["wrong_task_plan_minus_floor"]["n_pairs"] == 0
    assert rep["arms"]["wrong_task_plan"]["n"] == 0


# ---- a tiny world worked by hand: 3 tasks x 2 seeds -----------------------------------
TINY_GP = {  # (task, seed) -> (left, right); right has a limit on (sb_1, 2)
    ("sa_1", 1): (1.0, 0.5), ("sa_1", 2): (1.0, 0.5),
    ("sa_2", 1): (0.5, 0.5), ("sa_2", 2): (1.0, 0.0),
    ("sb_1", 1): (0.0, 0.0), ("sb_1", 2): (1.0, 0.5),
}


def test_tiny_world_contrast_values_by_hand(tmp_path_factory):
    root = tmp_path_factory.mktemp("tiny")
    for (task, seed), (gl, gr) in TINY_GP.items():
        for camp, gp in (("t_left", gl), ("t_right", gr)):
            err = "limit" if (camp, task, seed) == ("t_right", "sb_1", 2) else None
            row = {"task_id": task, "seed": seed, "system": "fixed_k", "goal_pass_rate": gp,
                   "tgc": 0.0 if err else gp, "success": gp == 1.0 and not err, "n_planner_calls": 0,
                   "error_type": err, "totals": {"planner_calls_total": 0}}
            _write(root / camp / "fixed_k" / str(seed) / task, "result.json", row)
    arms = {label: dv.load_dev_arm(label, dv.j17p._arm((camp,), (1, 2), "executor"), root)
            for label, camp in (("L", "t_left"), ("R", "t_right"))}
    c = dv.contrast_block(arms, {"id": "t", "left": "L", "right": "R"}, n_boot=500, seed=dv.BOOTSTRAP_SEED)
    # goal_pass diffs (sa_1: 0.5, 0.5; sa_2: 0, 1.0; sb_1: 0, 0.5) -> 2.5 / 6 = +41.67 pp
    assert c["n_pairs"] == 6 and c["n_dropped"] == 0
    assert c["goal_pass"]["diff_pp"] == pytest.approx(100 * 2.5 / 6)
    assert c["goal_pass"]["printed"]["diff_pp"] == "+41.67"
    assert c["goal_pass"]["means_on_pairs"] == {"L": pytest.approx(4.5 / 6), "R": pytest.approx(2.0 / 6)}
    # TGC: right's limit episode (sb_1, 2) scores 0, so its diff is 1.0 instead of 0.5 -> 3.0 / 6
    assert c["tgc"]["diff_pp"] == pytest.approx(100 * 3.0 / 6)
    # SGC units (scenario, seed): left passes (sa, 2) and (sb, 2); right passes none -> 2 / 4
    assert c["sgc"]["n_pairs"] == 4 and c["sgc"]["diff_pp"] == pytest.approx(50.0)
    assert c["limit_rate"]["right"]["paired"] == {"n": 6, "n_limit": 1, "rate": pytest.approx(1 / 6)}
    lo, hi = c["goal_pass"]["ci95_pp_scenario"]
    assert lo <= c["goal_pass"]["diff_pp"] <= hi
    assert c["goal_pass"]["n_clusters_scenario"] == 2 and c["goal_pass"]["n_clusters_task"] == 3
    assert c["goal_pass_boundary_probe"] is None or c["goal_pass_boundary_probe"]["bounds"]
    # POOL-04 probe, forced by a window wider than any bound: 7 seeds, the registered seed reproduces the bound
    p = dv.contrast_block(arms, {"id": "t", "left": "L", "right": "R"}, n_boot=500, seed=dv.BOOTSTRAP_SEED,
                          probe_window_pp=1000.0, probe_big_n=700)["goal_pass_boundary_probe"]
    assert len(p["bounds"]) == 4  # lo and hi on both clusterings
    for b in p["bounds"]:
        assert set(b["by_seed_pp"]) == {str(s) for s in dv.j10.POOL04_SEEDS} and b["big_n"] == 700
        assert b["by_seed_pp"][str(dv.BOOTSTRAP_SEED)] == pytest.approx(b["bound_pp"])
        assert isinstance(b["sign_stable"], bool)
