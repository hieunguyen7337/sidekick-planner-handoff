"""Synthetic, CPU-only tests for FeatureVerifier and the fit script (W-4)."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from sidekick.agents.verifier import (
    FEATURE_SPEC_VERSION,
    FeatureVerifier,
    ThresholdRouter,
    feature_spec,
)
from sidekick.protocols.schemas import DelegationPacket, Event, ExecutorAction

FIT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "setup" / "fit_feature_verifier.py"
REAL_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "hj6_branches_dev_sample.jsonl"
_spec = importlib.util.spec_from_file_location("fit_feature_verifier", FIT_PATH)
fit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fit)


def base_state(**over):
    state = {
        "step": 1,
        "transcript": "INSTRUCTION: do the thing",
        "last_action": None,
        "last_observation": None,
        "n_asks": 0,
        "n_interventions": 0,
    }
    state.update(over)
    return state


def tiny_verifier(**over) -> FeatureVerifier:
    cols = feature_spec()["columns"]
    weights = {c: 0.0 for c in cols}
    weights.update(over.pop("weights", {}))
    return FeatureVerifier(weights=weights, **over)


# --- each feature fires, and is zero when it should be ----------------------


def test_step_and_counters_passthrough():
    feats = fit._extractor_features(base_state(step=7, n_asks=2, n_interventions=3))
    assert feats["step"] == 7.0
    assert feats["n_asks"] == 2.0
    assert feats["n_interventions"] == 3.0


def test_last_obs_is_error_fires_and_is_zero_otherwise():
    err = {"text": "Traceback (most recent call last):\n  ...", "error_type": None, "step": 1}
    ok = {"text": "Execution done", "error_type": None, "step": 1}
    assert fit._extractor_features(base_state(last_observation=err))["last_obs_is_error"] == 1.0
    assert fit._extractor_features(base_state(last_observation=ok))["last_obs_is_error"] == 0.0
    assert fit._extractor_features(base_state())["last_obs_is_error"] == 0.0


def test_consecutive_error_run_counts_trailing_errors():
    t = "\n".join(
        [
            "INSTRUCTION: x",
            "OBS: Execution done",
            "OBS: Traceback (most recent call last): boom",
            "OBS: TypeError: bad type",
        ]
    )
    feats = fit._extractor_features(base_state(transcript=t))
    assert feats["consecutive_error_run"] == 2.0
    feats = fit._extractor_features(base_state(transcript="INSTRUCTION: x\nOBS: fine"))
    assert feats["consecutive_error_run"] == 0.0


def test_last_action_repeat_fires_when_code_in_transcript():
    t = "PLAN: consider `x = 1`\nOBS: done"
    action = {"kind": "CODE", "code": "x = 1"}
    feats = fit._extractor_features(base_state(transcript=t, last_action=action))
    assert feats["last_action_repeat"] == 1.0
    feats = fit._extractor_features(
        base_state(transcript="OBS: done", last_action={"kind": "CODE", "code": "y = 2"})
    )
    assert feats["last_action_repeat"] == 0.0


def test_distinct_apis_counts_unique_dotted_calls():
    t = "PLAN: use messenger.post_message(a) and contacts.get_contact(); again messenger.post_message()"
    feats = fit._extractor_features(base_state(transcript=t))
    assert feats["distinct_apis"] == 2.0
    assert fit._extractor_features(base_state())["distinct_apis"] == 0.0


def test_token_leak_fires_and_is_zero_otherwise():
    leak = "OBS: response {'access_token': 'aB3xY9kQ2mNpR7sT'}"
    clean = "OBS: Execution done"
    assert fit._extractor_features(base_state(transcript=leak))["token_leak"] == 1.0
    assert fit._extractor_features(base_state(transcript=clean))["token_leak"] == 0.0


def test_transcript_chars_and_last_action_kind():
    t = "INSTRUCTION: abc"
    feats = fit._extractor_features(base_state(transcript=t, last_action={"kind": "CODE"}))
    assert feats["transcript_chars"] == float(len(t))
    assert feats["last_action_kind_CODE"] == 1.0
    assert feats["last_action_kind_REPORT"] == 0.0
    none_feats = fit._extractor_features(base_state())
    assert all(
        none_feats[f"last_action_kind_{k}"] == 0.0
        for k in ("CODE", "REPORT", "ASK_PLANNER", "COMPLETE")
    )


def test_missing_last_action_and_observation_extract_without_raising():
    state = {"step": 3, "transcript": "INSTRUCTION: x", "n_asks": 0, "n_interventions": 0}
    feats = fit._extractor_features(state)
    assert feats["last_obs_is_error"] == 0.0
    assert all(
        feats[f"last_action_kind_{k}"] == 0.0
        for k in ("CODE", "REPORT", "ASK_PLANNER", "COMPLETE")
    )


# --- spec vs vector order, asserted explicitly ------------------------------


def test_feature_order_in_spec_matches_emitted_vector():
    spec = feature_spec()
    verifier = tiny_verifier()
    state = base_state(
        step=5,
        transcript="OBS: TypeError: nope\nPLAN: messenger.post_message(x)",
        last_action={"kind": "CODE", "code": "messenger.post_message(x)"},
        n_asks=1,
        n_interventions=2,
    )
    feats = verifier.features(state)
    vector = verifier.vector(state)
    assert spec["columns"] == list(feats.keys())
    assert vector == [feats[c] for c in spec["columns"]]
    # explicitly, not by construction:
    expected = [
        feats["step"],
        feats["n_interventions"],
        feats["n_asks"],
        feats["last_obs_is_error"],
        feats["consecutive_error_run"],
        feats["last_action_repeat"],
        feats["distinct_apis"],
        feats["token_leak"],
        feats["transcript_chars"],
        feats["last_action_kind_CODE"],
        feats["last_action_kind_REPORT"],
        feats["last_action_kind_ASK_PLANNER"],
        feats["last_action_kind_COMPLETE"],
    ]
    assert vector == expected
    assert spec["version"] == FEATURE_SPEC_VERSION


def test_spec_mismatch_raises():
    cols = feature_spec()["columns"]
    weights = {c: 0.0 for c in cols}
    weights["not_a_column"] = 1.0
    with pytest.raises(ValueError):
        FeatureVerifier(weights=weights)


# --- fit script: filtering, metrics, threshold router ------------------------


def _row(split, step, transcript, needed, status="complete", ambiguous=False):
    return {
        "split": split,
        "step": step,
        "transcript": transcript,
        "last_action": None,
        "last_observation": None,
        "n_asks": 0,
        "n_interventions": 0,
        "needed": needed,
        "label_status": status,
        "ambiguous": ambiguous,
    }


def _synthetic_branches(tmp_path: Path) -> tuple[Path, Path]:
    train_rows = []
    dev_rows = []
    leak = "OBS: Traceback (most recent call last): bad access_token 'AbCdEf12345678'"
    for i in range(20):
        train_rows.append(_row("train", 5 * (i % 2 + 1), leak, True))
        train_rows.append(_row("train", 5 * (i % 2 + 1) + 1, "OBS: Execution done", False))
        train_rows.append(_row("train", 5, "OBS: x", True, status="incomplete"))
        train_rows.append(_row("train", 5, "OBS: x", True, ambiguous=True))
    for i in range(10):
        dev_rows.append(_row("dev", 5, leak, True))
        dev_rows.append(_row("dev", 6, "OBS: Execution done", False))
        dev_rows.append(_row("dev", 5, "OBS: x", False, ambiguous=True))
    train_path = tmp_path / "train_branches.jsonl"
    dev_path = tmp_path / "dev_branches.jsonl"
    train_path.write_text("\n".join(json.dumps(r) for r in train_rows), encoding="utf-8")
    dev_path.write_text("\n".join(json.dumps(r) for r in dev_rows), encoding="utf-8")
    return train_path, dev_path


def test_prepare_dataset_drops_incomplete_excludes_ambiguous(tmp_path):
    train_path, dev_path = _synthetic_branches(tmp_path)
    train_rows, train_report = fit.prepare_dataset(fit.read_rows(train_path))
    dev_rows, dev_report = fit.prepare_dataset(fit.read_rows(dev_path))
    assert train_report["incomplete_dropped"] == 20
    assert train_report["ambiguous_excluded"] == 20
    assert train_report["n_kept_for_fit"] == 40
    assert train_report["n_positive_kept"] == 20 and train_report["n_negative_kept"] == 20
    assert dev_report["ambiguous_excluded"] == 10
    assert dev_report["n_kept_for_fit"] == 20
    assert all(r["label_status"] == "complete" for r in train_rows + dev_rows)
    assert all(r.get("ambiguous") is not True for r in train_rows + dev_rows)


def test_fit_on_separable_data_recovers_auroc_1(tmp_path):
    train_path, dev_path = _synthetic_branches(tmp_path)
    result = fit.run_fit(train_path, dev_path, tmp_path / "artifacts", date="20260917")
    dev = result["report"]["dev"]
    assert dev["auroc_all_states"] == pytest.approx(1.0)
    train = result["report"]["train"]
    assert train["auroc_all_states"] == pytest.approx(1.0)
    weights_path = Path(result["artifact_dir"]) / "weights.json"
    verifier = FeatureVerifier.load(weights_path)
    pos = verifier.score(
        _row("train", 5, "OBS: Traceback (most recent call last): access_token 'AbCdEf12345678'", True)
    )
    neg = verifier.score(_row("train", 6, "OBS: Execution done", False))
    assert pos > neg
    assert (Path(result["artifact_dir"]) / "feature_spec.json").exists()
    metrics = json.loads((Path(result["artifact_dir"]) / "metrics.json").read_text())
    assert metrics["dev_filter"]["ambiguous_excluded"] == 10
    assert len(metrics["threats_to_validity"]) >= 2


def test_pure_noise_labels_land_near_05():
    rows = [_row("train", 5, f"OBS: Execution done msg {i}", bool(i % 2)) for i in range(60)]
    dev = [_row("dev", 5, f"OBS: fine {i}", bool((i + 1) % 2)) for i in range(30)]
    Xtr, ytr = fit.build_xy(rows)
    means, stds = fit.standardize_fit(Xtr)
    Xtr = fit.apply_standardize(Xtr, means, stds)
    params = fit.fit_logistic(Xtr, ytr)
    Xdev, ydev = fit.build_xy(dev)
    Xdev = fit.apply_standardize(Xdev, means, stds)
    probs = fit.predict_probs(params, Xdev)
    auc = fit.auroc(ydev, probs)
    assert 0.2 <= auc <= 0.8  # proves the metric is being computed, not asserted


def test_auroc_tie_aware_and_edge_cases():
    assert fit.auroc([1, 1], [0.5, 0.5]) == 0.5  # single class
    assert fit.auroc([0, 1], [0.3, 0.7]) == 1.0
    assert fit.auroc([1, 0], [0.3, 0.7]) == 0.0
    assert fit.auroc([0, 1], [0.5, 0.5]) == 0.5  # full tie


def test_threshold_router_over_feature_verifier_strict_gt():
    cols = feature_spec()["columns"]
    weights = {c: 0.0 for c in cols}
    weights["token_leak"] = 5.0
    verifier = FeatureVerifier(weights=weights)
    router = ThresholdRouter(verifier, threshold=0.5)
    leak_state = base_state(transcript="OBS: access_token 'AbCdEf12345678'")
    assert verifier.score(leak_state) == pytest.approx(0.9933071490757153)  # sigmoid(5.0)
    assert router.should_escalate(leak_state) is True
    clean_state = base_state(transcript="OBS: done")
    assert verifier.score(clean_state) == pytest.approx(0.5)
    # strict greater-than: score == threshold does NOT escalate
    assert router.should_escalate(clean_state) is False


def test_temperature_scaling_changes_confidence():
    cols = feature_spec()["columns"]
    weights = {c: 0.0 for c in cols}
    weights["transcript_chars"] = 10.0
    hot = FeatureVerifier(weights=dict(weights), temperature=10.0)
    cold = FeatureVerifier(weights=dict(weights), temperature=0.1)
    state = base_state(transcript="x" * 30)
    z = hot.logit(state)
    p_hot = hot.score(state)
    p_cold = cold.score(state)
    # logit is divided by temperature; low temperature saturates
    assert math.log(p_hot / (1 - p_hot)) == pytest.approx(z / 10.0)
    assert p_cold > p_hot
    assert p_cold == pytest.approx(1.0)  # saturated by T=0.1 with z=30


def test_tick_state_restriction_reported():
    rows = [_row("dev", 5 * (i + 1), f"OBS: tick {i}", bool(i % 2)) for i in range(10)]
    ticks = [r for r in rows if fit.is_tick_state(r)]
    assert len(ticks) == 10
    assert all(r["step"] % 5 == 0 for r in ticks)


# --- W-4b: real branches.jsonl shape, join, boolean ambiguous ---------------


def _intervention_steps(i: int, step: int) -> list[int]:
    steps: list[int] = []
    for s in [5 * (j + 1) for j in range(int(i))] + [int(step)]:
        if s not in steps:
            steps.append(s)
    return steps


def _write_episode(campaign_root: Path, seed: int, task_id: str, intervention_steps: list[int]) -> Path:
    """Minimal fixed_k events.jsonl with timer-tick interventions at the given steps."""
    run_id = f"camp/fixed_k/{seed}/{task_id}"
    ts = "2026-09-17T00:00:00+00:00"
    packet = DelegationPacket(
        packet_id="pkt-1", task_id=task_id, goal="do the task", created_at=ts
    )
    usage = {"model": "mock", "provider": "mock", "input_tokens": 4, "output_tokens": 2, "n_calls": 1}
    events: list[Event] = []

    def add(event_type: str, step: int, actor: str, payload: dict, **extra) -> None:
        body = {
            "run_id": run_id,
            "task_id": task_id,
            "system": "fixed_k",
            "seed": seed,
            "step": step,
            "ts": ts,
            "actor": actor,
            "event_type": event_type,
            "payload": payload,
        }
        body.update(extra)
        events.append(Event.model_validate(body))

    add("run_start", 0, "system", {"policy": {"review_every_k": 5}})
    add("observation", 0, "environment", {"text": "Do the task using apis.phone.send_message()", "done": False})
    add("plan", 0, "planner", {"packet": packet.model_dump()}, usage=usage)
    code = ExecutorAction(
        kind="CODE",
        code="apis.phone.send_message(access_token='AbCdEf12345678')",
        raw_output="code",
    ).model_dump()
    n_iv = 0
    ticks = set(intervention_steps)
    for step in range(1, max(intervention_steps) + 1):
        if step in ticks:
            n_iv += 1
            add(
                "intervention",
                step,
                "planner",
                {"correction": f"correction {n_iv}", "forced": True, "n_interventions": n_iv},
                usage=usage,
            )
        add("action", step, "executor", code, usage=usage)
        add("observation", step, "environment", {"text": f"OBS result at {step}", "done": False})
    dest = campaign_root / "fixed_k" / str(seed) / task_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.jsonl").write_text(
        "\n".join(e.model_dump_json() for e in events) + "\n", encoding="utf-8"
    )
    return dest


def test_cli_requires_separate_split_files_and_campaigns():
    with pytest.raises(SystemExit):
        fit.build_parser().parse_args(["--branches", "x.jsonl", "--out", "o"])
    args = fit.build_parser().parse_args(
        [
            "--train-branches",
            "t.jsonl",
            "--dev-branches",
            "d.jsonl",
            "--train-campaign",
            "/camp/train",
            "--dev-campaign",
            "/camp/dev",
        ]
    )
    assert args.train_branches == "t.jsonl"
    assert args.dev_branches == "d.jsonl"
    assert args.train_campaign == "/camp/train"
    assert args.dev_campaign == "/camp/dev"


def test_real_artifact_rows_lack_split_and_feature_keys():
    rows = fit.read_rows(REAL_FIXTURE)
    assert rows
    for r in rows:
        for key in (
            "split",
            "transcript",
            "last_action",
            "last_observation",
            "n_asks",
            "n_interventions",
        ):
            assert key not in r
        assert "ambiguous" in r
        assert r["label_status"] in fit.ALLOWED_LABEL_STATUS
    with pytest.raises(ValueError, match="transcript"):
        fit.build_xy(rows[:1])


def test_split_is_which_file_and_dev_rows_nonempty(tmp_path):
    rows = fit.read_rows(REAL_FIXTURE)
    train_path = tmp_path / "train_branches.jsonl"
    dev_path = tmp_path / "dev_branches.jsonl"
    train_path.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
    dev_path.write_text("\n".join(json.dumps(r) for r in rows[1:]) + "\n", encoding="utf-8")
    train_joined, _ = fit.join_episode_features(fit.read_rows(train_path), None, split="train")
    dev_joined, _ = fit.join_episode_features(fit.read_rows(dev_path), None, split="dev")
    assert train_joined, "train partition emptied"
    assert dev_joined, "dev partition emptied — the original bug defaulted every row to train"
    assert all(r["split"] == "train" for r in train_joined)
    assert all(r["split"] == "dev" for r in dev_joined)


def test_ambiguous_boolean_excluded_on_real_shape_not_label_status():
    rows = fit.read_rows(REAL_FIXTURE)
    labeled = []
    for r in rows:
        x = dict(r)
        x["label_status"] = "complete"
        x["needed"] = False
        x["ambiguous"] = True
        labeled.append(x)
    kept, report = fit.prepare_dataset(labeled)
    assert report["ambiguous_excluded"] > 0
    assert report["ambiguous_excluded"] == len(labeled)
    assert kept == []
    with pytest.raises(ValueError, match="label_status"):
        fit.prepare_dataset(
            [{**rows[0], "label_status": "ambiguous", "needed": False, "ambiguous": False}]
        )


def test_failed_join_is_dropped_not_fitted(tmp_path):
    rows = fit.read_rows(REAL_FIXTURE)
    by_ep: dict[tuple, list] = {}
    for r in rows:
        by_ep.setdefault((r["seed"], r["task_id"]), []).append(r)
    episodes = list(by_ep)
    assert len(episodes) >= 2
    joinable, missing = episodes[0], episodes[-1]
    campaign = tmp_path / "campaign"
    steps: list[int] = []
    for r in by_ep[joinable]:
        for s in _intervention_steps(r["i"], r["step"]):
            if s not in steps:
                steps.append(s)
    _write_episode(campaign, joinable[0], joinable[1], steps)

    joined, report = fit.join_episode_features(rows, campaign, split="dev")
    assert report["n_join_dropped"] > 0
    assert report["n_joined"] > 0
    assert joined, "dev_rows empty after partitioning"
    assert all(r["split"] == "dev" for r in joined)
    assert all((r["seed"], r["task_id"]) != missing for r in joined)
    assert all(r.get("transcript") for r in joined)
    feats = fit._extractor_features(joined[0])
    assert feats["transcript_chars"] > 0
    assert feats["last_action_kind_CODE"] == 1.0
    for r in by_ep[missing]:
        with pytest.raises(ValueError, match="transcript"):
            fit.build_xy([r])
    X, y = fit.build_xy(joined)
    assert len(X) == len(joined) == len(y)


def test_run_fit_joins_real_ids_and_reports_ambiguous_and_drops(tmp_path):
    rows = fit.read_rows(REAL_FIXTURE)
    by_ep: dict[tuple, list] = {}
    for r in rows:
        by_ep.setdefault((r["seed"], r["task_id"]), []).append(r)
    episodes = list(by_ep)
    campaign = tmp_path / "campaign"
    for ep in episodes[:-1]:
        steps: list[int] = []
        for r in by_ep[ep]:
            for s in _intervention_steps(r["i"], r["step"]):
                if s not in steps:
                    steps.append(s)
        _write_episode(campaign, ep[0], ep[1], steps)

    joinable_rows = [r for r in rows if (r["seed"], r["task_id"]) != episodes[-1]]
    missing_row = by_ep[episodes[-1]][0]

    def overlay(src: dict, needed: bool, *, ambiguous: bool = False) -> dict:
        x = dict(src)
        x["label_status"] = "complete"
        x["needed"] = needed
        x["ambiguous"] = ambiguous
        return x

    train_rows = [
        overlay(joinable_rows[0], True),
        overlay(joinable_rows[0], False),
        overlay(joinable_rows[0], False, ambiguous=True),
        dict(missing_row),
    ]
    dev_rows = [
        overlay(joinable_rows[0], True),
        overlay(joinable_rows[0], False),
        overlay(joinable_rows[0], False, ambiguous=True),
    ]
    train_path = tmp_path / "train_branches.jsonl"
    dev_path = tmp_path / "dev_branches.jsonl"
    train_path.write_text("\n".join(json.dumps(r) for r in train_rows) + "\n", encoding="utf-8")
    dev_path.write_text("\n".join(json.dumps(r) for r in dev_rows) + "\n", encoding="utf-8")
    result = fit.run_fit(
        train_path,
        dev_path,
        tmp_path / "artifacts",
        train_campaign=campaign,
        dev_campaign=campaign,
        date="20260917",
    )
    report = result["report"]
    assert report["dev_join"]["n_joined"] > 0
    assert report["dev_filter"]["ambiguous_excluded"] > 0
    assert report["train_join"]["n_join_dropped"] >= 1
    assert report["dev"]["n"] >= 2
    assert "dev_nll_before" in report
    assert "dev_nll_after" in report
    assert report["dev"]["nll"] is not None


# --- W-17: 1-D golden-section temperature fitting & NLL invariant -----------


def test_fit_temperature_three_regimes():
    import random

    rng = random.Random(0)
    z = [rng.gauss(0.0, 1.5) for _ in range(400)]
    p = [1.0 / (1.0 + math.exp(-zi)) for zi in z]
    y = [1 if rng.random() < pi else 0 for pi in p]

    # Case A: well-specified data (honest T = 1.0)
    t_a = fit.fit_temperature(p, y)
    assert 0.7 <= t_a <= 1.4
    probs_a_fit = fit.rescale_probs(p, t_a)
    assert fit.compute_nll(y, probs_a_fit) <= fit.compute_nll(y, p)

    # Case B: overconfident model (logits 3x too large, honest T ~ 3.0)
    z2 = [zi * 3.0 for zi in z]
    p2 = [1.0 / (1.0 + math.exp(-zi)) for zi in z2]
    t_b = fit.fit_temperature(p2, y)
    assert 2.2 <= t_b <= 4.0
    probs_b_fit = fit.rescale_probs(p2, t_b)
    assert fit.compute_nll(y, probs_b_fit) <= fit.compute_nll(y, p2)

    # Case C: uninformative scores against random labels (honest T large)
    y3 = [rng.randint(0, 1) for _ in range(400)]
    t_c = fit.fit_temperature(p2, y3)
    assert t_c >= 5.0
    probs_c_fit = fit.rescale_probs(p2, t_c)
    assert fit.compute_nll(y3, probs_c_fit) <= fit.compute_nll(y3, p2)


def test_fit_temperature_degenerate_inputs():
    assert fit.fit_temperature([], []) == 1.0
    assert fit.fit_temperature([0.2, 0.8], []) == 1.0
    assert fit.fit_temperature([0.2, 0.8], [1, 1]) == 1.0
    assert fit.fit_temperature([0.2, 0.8], [0, 0]) == 1.0


def test_fit_temperature_never_worse_than_one():
    # If uncalibrated is already optimal or optimizer cannot improve, guard returns 1.0
    probs = [0.1, 0.9, 0.1, 0.9]
    y = [0, 1, 0, 1]
    t = fit.fit_temperature(probs, y)
    nll_t = fit.compute_nll(y, fit.rescale_probs(probs, t))
    nll_1 = fit.compute_nll(y, probs)
    assert nll_t <= nll_1

