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

FIT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "setup" / "fit_feature_verifier.py"
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


def _row(split, step, transcript, needed, status="complete"):
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
    }


def _synthetic_branches(tmp_path: Path) -> Path:
    path = tmp_path / "branches.jsonl"
    rows = []
    leak = "OBS: Traceback (most recent call last): bad access_token 'AbCdEf12345678'"
    for i in range(20):
        rows.append(_row("train", 5 * (i % 2 + 1), leak, True))
        rows.append(_row("train", 5 * (i % 2 + 1) + 1, "OBS: Execution done", False))
        rows.append(_row("train", 5, "OBS: x", True, status="incomplete"))
        rows.append(_row("train", 5, "OBS: x", True, status="ambiguous"))
    for i in range(10):
        rows.append(_row("dev", 5, leak, True))
        rows.append(_row("dev", 6, "OBS: Execution done", False))
        rows.append(_row("dev", 5, "OBS: x", False, status="ambiguous"))
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return path


def test_prepare_dataset_drops_incomplete_excludes_ambiguous(tmp_path):
    rows = fit.read_rows(_synthetic_branches(tmp_path))
    train_rows, train_report = fit.prepare_dataset([r for r in rows if r["split"] == "train"])
    dev_rows, dev_report = fit.prepare_dataset([r for r in rows if r["split"] == "dev"])
    assert train_report["incomplete_dropped"] == 20
    assert train_report["ambiguous_excluded"] == 20
    assert train_report["n_kept_for_fit"] == 40
    assert train_report["n_positive_kept"] == 20 and train_report["n_negative_kept"] == 20
    assert dev_report["ambiguous_excluded"] == 10
    assert dev_report["n_kept_for_fit"] == 20
    assert all(r["label_status"] == "complete" for r in train_rows + dev_rows)


def test_fit_on_separable_data_recovers_auroc_1(tmp_path):
    result = fit.run_fit(_synthetic_branches(tmp_path), tmp_path / "artifacts", date="20260917")
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
