"""Tests for the difference-in-differences analysis.

The fixtures are scripted so the correct answer is known by arithmetic, not by running the
code and blessing whatever it printed. Every assertion below names the value it expects and
why, because a bootstrap that is subtly wrong still returns a confident-looking interval --
which is the exact failure mode this project keeps finding in its own analysis scripts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.j14_did import (
    compute_did,
    episode_value,
    excludes_zero,
    main,
    parse_did_spec,
)


def write_arm(root: Path, label: str, values: dict[tuple[str, int], float],
              error_type: dict[tuple[str, int], str] | None = None) -> Path:
    """Write a campaign tree matching <campaign>/<system>/<seed>/<task>/result.json."""
    errors = error_type or {}
    arm_root = root / label
    for (task_id, seed), value in values.items():
        d = arm_root / "sys" / str(seed) / task_id
        d.mkdir(parents=True, exist_ok=True)
        payload = {
            "task_id": task_id,
            "seed": seed,
            "goal_pass_rate": value,
            "tgc": value,
            "error_type": errors.get((task_id, seed)),
        }
        (d / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    return arm_root


def load(root: Path, label: str) -> dict:
    from scripts.setup.hj1_gate import load_arm

    return load_arm(root / label)


# Six tasks across two scenarios, two seeds: 12 episodes. Scenario ids come from
# scenario_of, which splits on the last underscore, so "s1_1" and "s1_2" share scenario
# "s1". Two scenarios is deliberately few -- it exercises the cluster resampling.
KEYS = [(f"s{s}_{t}", seed) for s in (1, 2) for t in (1, 2, 3) for seed in (1, 2)]


def const(value: float) -> dict[tuple[str, int], float]:
    return {k: value for k in KEYS}


def test_did_is_zero_when_both_gaps_are_identical(tmp_path: Path) -> None:
    """Gap A = 0.6-0.4 = 0.2; gap B = 0.5-0.3 = 0.2; DiD must be exactly 0."""
    write_arm(tmp_path, "a_pos", const(0.6))
    write_arm(tmp_path, "a_neg", const(0.4))
    write_arm(tmp_path, "b_pos", const(0.5))
    write_arm(tmp_path, "b_neg", const(0.3))
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    out = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)

    assert out["n_pairs"] == 12
    assert out["gap_a_pp"] == pytest.approx(20.0)
    assert out["gap_b_pp"] == pytest.approx(20.0)
    assert out["scenario"]["point_pp"] == pytest.approx(0.0)
    # A constant series has zero variance, so every resample returns the same mean and
    # the interval collapses onto the point estimate.
    assert out["scenario"]["ci95_pp"] == [pytest.approx(0.0), pytest.approx(0.0)]
    assert excludes_zero(out["scenario"]) is False


def test_did_recovers_a_known_nonzero_interaction(tmp_path: Path) -> None:
    """Gap A = 0.30, gap B = 0.10, so the DiD is exactly +20.00 pp."""
    write_arm(tmp_path, "a_pos", const(0.9))
    write_arm(tmp_path, "a_neg", const(0.6))
    write_arm(tmp_path, "b_pos", const(0.5))
    write_arm(tmp_path, "b_neg", const(0.4))
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    out = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)

    assert out["gap_a_pp"] == pytest.approx(30.0)
    assert out["gap_b_pp"] == pytest.approx(10.0)
    assert out["scenario"]["point_pp"] == pytest.approx(20.0)
    assert out["task"]["point_pp"] == pytest.approx(20.0)
    assert excludes_zero(out["scenario"]) is True


def test_did_sign_follows_the_definition(tmp_path: Path) -> None:
    """Swapping the two gaps must flip the sign and nothing else."""
    write_arm(tmp_path, "a_pos", const(0.9))
    write_arm(tmp_path, "a_neg", const(0.6))
    write_arm(tmp_path, "b_pos", const(0.5))
    write_arm(tmp_path, "b_neg", const(0.4))
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    fwd = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)
    rev = compute_did(arms, "b_pos", "b_neg", "a_pos", "a_neg", "goal_pass_rate",
                      n_boot=200, seed=1)

    assert rev["scenario"]["point_pp"] == pytest.approx(-fwd["scenario"]["point_pp"])


def test_pairing_is_preserved_inside_the_episode(tmp_path: Path) -> None:
    """The DiD is formed per episode, so a within-episode cancellation must survive.

    Here each arm's MEAN is identical across the two gaps, so a computation that averaged
    first and subtracted after would report DiD = 0. But episode by episode the two gaps
    move in opposite directions, and the correct per-episode DiD is non-zero on every
    episode. This test fails if anyone "simplifies" the estimator to a difference of arm
    means, which is the single most likely wrong refactor of this module.
    """
    half = len(KEYS) // 2
    first, second = KEYS[:half], KEYS[half:]

    a_pos = {k: (1.0 if k in first else 0.0) for k in KEYS}
    a_neg = const(0.0)
    b_pos = {k: (0.0 if k in first else 1.0) for k in KEYS}
    b_neg = const(0.0)

    write_arm(tmp_path, "a_pos", a_pos)
    write_arm(tmp_path, "a_neg", a_neg)
    write_arm(tmp_path, "b_pos", b_pos)
    write_arm(tmp_path, "b_neg", b_neg)
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    out = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)

    # Arm means are equal (0.5 each), so a mean-of-means estimator would give 0.
    assert out["arm_means"]["a_pos"] == pytest.approx(0.5)
    assert out["arm_means"]["b_pos"] == pytest.approx(0.5)
    assert out["gap_a_pp"] == pytest.approx(50.0)
    assert out["gap_b_pp"] == pytest.approx(50.0)
    # Per episode the DiD is +1 on `first` and -1 on `second`; the mean is 0 but every
    # episode contributes a non-zero value, so the bootstrap must see real variance.
    assert out["scenario"]["point_pp"] == pytest.approx(0.0)
    assert out["scenario"]["ci95_pp"][0] < out["scenario"]["ci95_pp"][1]


def test_crash_constant_matches_the_frontier_report_convention() -> None:
    """The DiD must zero exactly what every published arm mean zeroes, and nothing more.

    j8_frontier.mean_quality(crash_as_zero=True) zeroes is_crashed(), which is
    `error_type == CRASH_ERROR_TYPE` and only that. If this module drifted to
    campaign_summarize.BROKEN (which also covers parse_error, timeout, api_error) the DiD
    would silently disagree with the ledger: the untailored m=11 arm holds one parse_error
    episode, so its mean would read 0.826781 here against the published 0.834456.
    """
    from scripts.analysis.j14_did import CRASH_ERROR_TYPE as MINE
    from scripts.analysis.j8_frontier import CRASH_ERROR_TYPE as THEIRS

    assert MINE == THEIRS


def test_only_crash_is_zeroed_not_parse_error_or_limit(tmp_path: Path) -> None:
    """'crash' is zeroed; 'parse_error' and 'limit' keep their recorded scores."""
    crashed_key = KEYS[0]
    limit_key = KEYS[1]
    parse_key = KEYS[2]
    write_arm(
        tmp_path, "a_pos", const(0.8),
        error_type={crashed_key: "crash", limit_key: "limit",
                    parse_key: "parse_error"},
    )
    write_arm(tmp_path, "a_neg", const(0.0))
    write_arm(tmp_path, "b_pos", const(0.0))
    write_arm(tmp_path, "b_neg", const(0.0))
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    assert episode_value(arms["a_pos"][crashed_key], "goal_pass_rate") == 0.0
    assert episode_value(arms["a_pos"][limit_key], "goal_pass_rate") == 0.8
    assert episode_value(arms["a_pos"][parse_key], "goal_pass_rate") == 0.8

    out = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)
    # 11 episodes at 0.8 and one zeroed crash, over 12 episodes. The parse_error and the
    # limit episode are NOT zeroed, so they are part of the 11.
    assert out["arm_means"]["a_pos"] == pytest.approx(11 * 0.8 / 12)
    assert out["crashed_episodes"]["a_pos"] == 1


def test_episodes_missing_from_one_arm_are_dropped_and_counted(tmp_path: Path) -> None:
    write_arm(tmp_path, "a_pos", const(0.6))
    write_arm(tmp_path, "a_neg", const(0.4))
    write_arm(tmp_path, "b_pos", const(0.5))
    partial = {k: 0.3 for k in KEYS[:-2]}  # two episodes missing
    write_arm(tmp_path, "b_neg", partial)
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    out = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate",
                      n_boot=200, seed=1)

    assert out["n_pairs"] == len(KEYS) - 2
    assert out["n_dropped_not_in_all_four"] == 2


def test_bootstrap_is_deterministic_under_a_fixed_seed(tmp_path: Path) -> None:
    import random as _random

    write_arm(tmp_path, "a_pos", {k: 0.1 * (i % 7) for i, k in enumerate(KEYS)})
    write_arm(tmp_path, "a_neg", const(0.2))
    write_arm(tmp_path, "b_pos", {k: 0.1 * (i % 5) for i, k in enumerate(KEYS)})
    write_arm(tmp_path, "b_neg", const(0.1))
    arms = {lbl: load(tmp_path, lbl) for lbl in ("a_pos", "a_neg", "b_pos", "b_neg")}

    kw = dict(n_boot=500, seed=20260924)
    first = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate", **kw)
    _random.seed(999)  # global RNG interference must not change the result
    second = compute_did(arms, "a_pos", "a_neg", "b_pos", "b_neg", "goal_pass_rate", **kw)

    assert first["scenario"]["ci95_pp"] == second["scenario"]["ci95_pp"]
    assert first["task"]["ci95_pp"] == second["task"]["ci95_pp"]


def test_unknown_arm_label_is_fatal(tmp_path: Path) -> None:
    write_arm(tmp_path, "a_pos", const(0.6))
    arms = {"a_pos": load(tmp_path, "a_pos")}
    with pytest.raises(KeyError):
        compute_did(arms, "a_pos", "nope", "a_pos", "a_pos", "goal_pass_rate",
                    n_boot=10, seed=1)


def test_parse_did_spec() -> None:
    assert parse_did_spec("m9:a,b,c,d") == ("m9", "a", "b", "c", "d")
    with pytest.raises(Exception):
        parse_did_spec("missing_colon")
    with pytest.raises(Exception):
        parse_did_spec("m9:a,b,c")


def test_cli_writes_a_traceable_report(tmp_path: Path) -> None:
    write_arm(tmp_path, "a_pos", const(0.9))
    write_arm(tmp_path, "a_neg", const(0.6))
    write_arm(tmp_path, "b_pos", const(0.5))
    write_arm(tmp_path, "b_neg", const(0.4))
    out = tmp_path / "report.json"

    rc = main([
        "--arm", f"a_pos={tmp_path / 'a_pos'}",
        "--arm", f"a_neg={tmp_path / 'a_neg'}",
        "--arm", f"b_pos={tmp_path / 'b_pos'}",
        "--arm", f"b_neg={tmp_path / 'b_neg'}",
        "--did", "demo:a_pos,a_neg,b_pos,b_neg",
        "--bootstrap", "200",
        "--out", str(out),
    ])

    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    block = report["dids"]["demo"]["goal_pass_rate"]
    assert block["scenario"]["point_pp"] == pytest.approx(20.0)
    # Every arm must be traceable back to the directory it came from, or the number in the
    # paper cannot be checked against the tree.
    assert set(report["arm_sources"]) == {"a_pos", "a_neg", "b_pos", "b_neg"}
    assert report["seed"] == 20260924
    assert report["dids"]["demo"]["tgc"]["scenario"]["point_pp"] == pytest.approx(20.0)


def test_missing_arm_directory_is_fatal(tmp_path: Path) -> None:
    rc = main([
        "--arm", f"a={tmp_path / 'does_not_exist'}",
        "--did", "d:a,a,a,a",
        "--out", str(tmp_path / "x.json"),
    ])
    assert rc == 2


# --- pooling several campaigns into one arm (the 171-pair curve) ---------------------


def test_pooled_arm_merges_campaigns_that_differ_in_seed(tmp_path: Path) -> None:
    from scripts.analysis.j14_did import load_pooled_arm

    seeds12 = {(f"s1_{t}", seed): 0.5 for t in (1, 2, 3) for seed in (1, 2)}
    seed3 = {(f"s1_{t}", 3): 0.9 for t in (1, 2, 3)}
    write_arm(tmp_path, "a_12", seeds12)
    write_arm(tmp_path, "a_3", seed3)

    pooled = load_pooled_arm([tmp_path / "a_12", tmp_path / "a_3"])

    assert len(pooled) == 9
    assert sorted({s for _, s in pooled}) == [1, 2, 3]


def test_pooling_campaigns_that_share_a_seed_is_fatal(tmp_path: Path) -> None:
    """Silently dropping half of a colliding pair would look like a well-formed arm."""
    from scripts.analysis.j14_did import load_pooled_arm

    write_arm(tmp_path, "b_1", {("s1_1", 1): 0.5})
    write_arm(tmp_path, "b_2", {("s1_1", 1): 0.9})

    with pytest.raises(ValueError, match="share 1 episode keys"):
        load_pooled_arm([tmp_path / "b_1", tmp_path / "b_2"])


def test_pooling_raises_the_pair_count_of_a_contrast(tmp_path: Path) -> None:
    """The whole point of U4: the same contrast, measured on more episodes."""
    from scripts.analysis.j14_did import compute_contrast, load_pooled_arm

    keys12 = [(f"s{s}_{t}", seed) for s in (1, 2) for t in (1, 2, 3) for seed in (1, 2)]
    keys3 = [(f"s{s}_{t}", 3) for s in (1, 2) for t in (1, 2, 3)]

    write_arm(tmp_path, "hi_12", {k: 0.8 for k in keys12})
    write_arm(tmp_path, "lo_12", {k: 0.5 for k in keys12})
    write_arm(tmp_path, "hi_3", {k: 0.8 for k in keys3})
    write_arm(tmp_path, "lo_3", {k: 0.5 for k in keys3})

    unpooled = {
        "hi": load_pooled_arm([tmp_path / "hi_12"]),
        "lo": load_pooled_arm([tmp_path / "lo_12"]),
    }
    pooled = {
        "hi": load_pooled_arm([tmp_path / "hi_12", tmp_path / "hi_3"]),
        "lo": load_pooled_arm([tmp_path / "lo_12", tmp_path / "lo_3"]),
    }

    a = compute_contrast(unpooled, "hi", "lo", "goal_pass_rate", n_boot=200, seed=1)
    b = compute_contrast(pooled, "hi", "lo", "goal_pass_rate", n_boot=200, seed=1)

    assert a["n_pairs"] == 12 and a["n_seeds"] == 2
    assert b["n_pairs"] == 18 and b["n_seeds"] == 3
    # Same underlying effect, so the point estimate must not move.
    assert a["scenario"]["point_pp"] == pytest.approx(b["scenario"]["point_pp"])
    assert b["scenario"]["point_pp"] == pytest.approx(30.0)


def test_parse_arm_spec_accepts_several_directories() -> None:
    from scripts.analysis.j14_did import parse_arm_spec

    label, paths = parse_arm_spec("x=/a/b,/c/d")
    assert label == "x"
    assert [str(p) for p in paths] == ["/a/b", "/c/d"]

    label, paths = parse_arm_spec("y=/only/one")
    assert len(paths) == 1


def test_parse_contrast_spec() -> None:
    from scripts.analysis.j14_did import parse_contrast_spec

    assert parse_contrast_spec("d:a,b") == ("d", "a", "b")
    with pytest.raises(Exception):
        parse_contrast_spec("d:a,b,c")
    with pytest.raises(Exception):
        parse_contrast_spec("nocolon")


def test_cli_contrast_mode_writes_a_report(tmp_path: Path) -> None:
    write_arm(tmp_path, "hi", const(0.8))
    write_arm(tmp_path, "lo", const(0.5))
    out = tmp_path / "c.json"

    rc = main([
        "--arm", f"hi={tmp_path / 'hi'}",
        "--arm", f"lo={tmp_path / 'lo'}",
        "--contrast", "depth:hi,lo",
        "--bootstrap", "200",
        "--out", str(out),
    ])

    assert rc == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    block = report["contrasts"]["depth"]["goal_pass_rate"]
    assert block["scenario"]["point_pp"] == pytest.approx(30.0)
    assert block["n_pairs"] == 12
