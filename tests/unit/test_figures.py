"""Unit tests for figure generator (Brief X41).

All tests use tmp_path and scripted minimal report JSON fixtures.
No real campaign data or network connections are accessed in tests.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from scripts.analysis.figures import (
    MANDATORY_F5_ANNOTATION,
    generate_f1_depth_curve,
    generate_f2_channel_budget,
    generate_f3_tailoring_gap,
    generate_f4_mechanism,
    generate_f5_second_family,
    generate_f6_narrated_vs_executed,
    generate_f7_narrated_minus_executed,
    generate_f8_advice_cost_quality,
    generate_f9_channel_limit,
    generate_f10_depth_hstar,
    generate_f11_ni_forest,
    generate_f12_registered_forest,
    get_nested_key,
    load_report_json,
    run_figures,
    validate_output_path,
)


def _make_minimal_shape_post_guard() -> dict:
    return {
        "arms": {
            f"prefix_m{m}": {"goal_pass_all": 0.70 + 0.01 * m}
            for m in (2, 4, 6, 7, 8, 9, 10, 11)
        }
    }


def _make_minimal_zs_depth_m6_m9() -> dict:
    return {
        "arms": {
            "zs_m6": {"goal_pass_all": 0.6825},
            "zs_m9": {"goal_pass_all": 0.7845},
        }
    }


def _make_minimal_zs_depth_m9_m11() -> dict:
    return {
        "arms": {
            "zs_m9": {"goal_pass_all": 0.7845},
            "zs_m11": {"goal_pass_all": 0.8345},
        }
    }


def _make_minimal_ceiling_report() -> dict:
    return {
        "arms": {
            "ceiling_cap25": {"goal_pass_all": 0.8284},
            "ceiling_cap81": {"goal_pass_all": 0.7637},
        }
    }


def _make_minimal_frontier_report() -> dict:
    arms = {
        "executor_alone": {"cost_per_episode": 0.0, "goal_pass_all": 0.5289},
        "sft_plan": {"cost_per_episode": 23905.59, "goal_pass_all": 0.7181},
        "planner_alone": {"cost_per_episode": 684453.26, "goal_pass_all": 0.8284},
        "advise_fixed_k_3": {"cost_per_episode": 204499.76, "goal_pass_all": 0.7012},
        "advise_fixed_k_10": {"cost_per_episode": 64964.67, "goal_pass_all": 0.6964},
    }
    for m in (2, 4, 6, 7, 8, 9, 10, 11):
        arms[f"prefix_m{m}"] = {"cost_per_episode": 50000.0 * m, "goal_pass_all": 0.70 + 0.01 * m}
    return {"arms": arms}


def _make_minimal_advice_matched_report() -> dict:
    return {
        "arms": {
            "advice_fullctx_k10": {
                "planner_tokens_per_episode": 77651.5,
                "goal_pass_all": 0.7339,
            }
        }
    }


def _make_minimal_receiver_contrast(m: int, diff_pp: float, ci95_pp: list[float]) -> dict:
    return {
        "contrasts": {
            f"goal_pass_all_prefix_m{m}_zeroshot_minus_prefix_m{m}_tailored": {
                "diff_pp": diff_pp,
                "ci95_pp": ci95_pp,
            }
        }
    }


def _make_minimal_mechanism_report() -> dict:
    cum_dict = {
        str(pos): {
            "cum_first_uses_share": round(0.15 + 0.04 * pos, 4)
        }
        for pos in range(1, 21)
    }
    return {
        "m1_api_novelty": {
            "cumulative_by_position": cum_dict,
        },
        "m3_prefix_exhausted": {
            "primary": {
                "decompositions": {
                    "m6_to_m9": {
                        "contribution_handoff_subset_pp": 8.55,
                        "contribution_silenced_subset_pp": 1.65,
                        "share_of_rise_from_handoff_pct": 83.8,
                        "delta_total_pp": 10.21,
                    },
                    "m6_to_m11": {
                        "contribution_handoff_subset_pp": 9.19,
                        "contribution_silenced_subset_pp": 6.00,
                        "share_of_rise_from_handoff_pct": 60.5,
                        "delta_total_pp": 15.20,
                    },
                }
            }
        },
    }


def _make_minimal_qwen_curve_report() -> dict:
    return {
        "arms": {
            "qwen_prefix_m6": {"goal_pass_all": 0.4491},
            "qwen_prefix_m9": {"goal_pass_all": 0.7017},
            "qwen_prefix_m11": {"goal_pass_all": 0.7306},
        }
    }


def _make_minimal_narrated_tailored_report() -> dict:
    return {
        "arms": {
            "plan_only_iaware": {"goal_pass_all": 0.7181, "tgc_all": 0.3947},
            "narrated_m9": {"goal_pass_all": 0.7667, "tgc_all": 0.5263},
            "executed_m9": {"goal_pass_all": 0.7852, "tgc_all": 0.5614},
        },
        "contrasts": {
            "goal_pass_all_narrated_m9_minus_plan_only_iaware": {"diff_pp": 4.86, "ci95_pp": [-0.56, 10.61]},
            "tgc_all_narrated_m9_minus_plan_only_iaware": {"diff_pp": 13.16, "ci95_pp": [5.26, 21.93]},
            "goal_pass_all_executed_m9_minus_plan_only_iaware": {"diff_pp": 6.70, "ci95_pp": [1.44, 11.74]},
            "tgc_all_executed_m9_minus_plan_only_iaware": {"diff_pp": 16.67, "ci95_pp": [7.02, 25.44]},
            "goal_pass_all_executed_m9_minus_narrated_m9": {"diff_pp": 1.84, "ci95_pp": [-2.67, 6.76]},
            "tgc_all_executed_m9_minus_narrated_m9": {"diff_pp": 3.51, "ci95_pp": [-5.26, 11.4]},
        },
    }


def _make_minimal_narrated_untailored_report() -> dict:
    return {
        "arms": {
            "base_one_plan": {"goal_pass_all": 0.2885, "tgc_all": 0.0526},
            "narrated_zs_m9": {"goal_pass_all": 0.7676, "tgc_all": 0.4912},
            "executed_zs_m9": {"goal_pass_all": 0.7845, "tgc_all": 0.5526},
        },
        "contrasts": {
            "goal_pass_all_narrated_zs_m9_minus_base_one_plan": {"diff_pp": 47.92, "ci95_pp": [38.67, 56.27]},
            "tgc_all_narrated_zs_m9_minus_base_one_plan": {"diff_pp": 43.86, "ci95_pp": [30.70, 56.14]},
            "goal_pass_all_executed_zs_m9_minus_base_one_plan": {"diff_pp": 49.61, "ci95_pp": [41.64, 57.74]},
            "tgc_all_executed_zs_m9_minus_base_one_plan": {"diff_pp": 50.00, "ci95_pp": [35.96, 63.16]},
            "goal_pass_all_executed_zs_m9_minus_narrated_zs_m9": {"diff_pp": 1.69, "ci95_pp": [-4.16, 7.11]},
            "tgc_all_executed_zs_m9_minus_narrated_zs_m9": {"diff_pp": 6.14, "ci95_pp": [-2.63, 14.91]},
        },
    }


def _make_minimal_narrated_curve_report(tailored: bool) -> dict:
    if tailored:
        values = [(-2.51, [-8.68, 3.41]), (-1.84, [-6.76, 2.68]), (-0.49, [-4.10, 3.21])]
        prefix = "goal_pass_all_narrated_t_m{m}_minus_executed_t_m{m}"
    else:
        values = [(-6.96, [-13.67, 0.63]), (-1.69, [-7.10, 4.16]), (-6.58, [-9.98, -3.64])]
        prefix = "goal_pass_all_narrated_m{m}_minus_executed_m{m}"
    return {
        "contrasts": {
            prefix.format(m=m): {"diff_pp": diff, "ci95_pp_scenario": ci}
            for m, (diff, ci) in zip((6, 9, 11), values)
        }
    }


def _make_minimal_advice_at_price_report() -> dict:
    return {
        "arms": {
            "advise_k10_fullctx": {"goal_pass_all": 0.7339},
            "advise_k1_fullctx": {"goal_pass_all": 0.6630},
            "prefix_m9": {"goal_pass_all": 0.7852},
            "prefix_m11": {"goal_pass_all": 0.8098},
        }
    }


def _make_minimal_advice_at_price_cost_report() -> dict:
    return {
        "arms": {
            "advise_k10_fullctx": {"noncached_tokens_per_episode": 49819, "hosted_calls_per_episode": 2.46},
            "advise_k1_fullctx": {"noncached_tokens_per_episode": 1414410, "hosted_calls_per_episode": 19.02},
            "prefix_m9": {"noncached_tokens_per_episode": 357448, "hosted_calls_per_episode": 9.77},
            "prefix_m11": {"noncached_tokens_per_episode": 443361, "hosted_calls_per_episode": 11.25},
        }
    }


def _make_minimal_b2_decomposition_report() -> dict:
    means = {"T": 0.7899, "S": 0.7516, "N": 0.7658, "A": 0.7285}
    return {
        "arms": {arm: {"goal_pass_mean": mean, "n_scored": 171} for arm, mean in means.items()},
        "contrasts": {"D0": {"scenario": {"diff_pp": 6.13, "ci95_pp": [0.75, 12.71]}}},
    }


def _make_minimal_channel_fixes_report() -> dict:
    return {
        "limits": {
            "per_arm": {
                "takeover_k10": {"n": 171, "n_limit": 2, "rate": 0.011696},
                "show_k10": {"n": 171, "n_limit": 11, "rate": 0.064327},
                "advise_k10_neutral": {"n": 171, "n_limit": 14, "rate": 0.081871},
                "advise_k10": {"n": 171, "n_limit": 20, "rate": 0.116959},
            },
            "split": {
                "D0": {
                    "either_limit": {"n": 22, "contribution_pp": 4.07, "contribution_ci95_pp_scenario": [0.93, 7.72]},
                    "neither": {"n": 149, "contribution_pp": 2.06, "contribution_ci95_pp_scenario": [-0.53, 5.22]},
                }
            },
        }
    }


def _ni_cell(diff_pp: float, ci: list[float], n_pairs: int) -> dict:
    return {"diff_pp": diff_pp, "ci95_pp_scenario": ci, "n_pairs": n_pairs}


def _make_minimal_hstar_report() -> dict:
    counts = {6: (167, 4), 9: (128, 43), 11: (88, 83)}
    means = {
        "bplus": {6: (0.729942, 0.723473, 1.0), 9: (0.771357, 0.727844, 0.900884), 11: (0.813854, 0.7745, 0.855578)},
        "zs": {6: (0.712175, 0.705281, 1.0), 9: (0.774731, 0.732352, 0.900884), 11: (0.789164, 0.726523, 0.855578)},
    }
    handoff_only = {
        receiver: {
            f"m{m}": {
                "n": 171, "n_handoff": counts[m][0], "n_silenced": counts[m][1],
                "goal_pass": {"mean_all": all_, "mean_handoff": handoff, "mean_silenced": silenced},
            }
            for m, (all_, handoff, silenced) in by_m.items()
        }
        for receiver, by_m in means.items()
    }
    control_counts = {
        receiver: {f"m{m}": {"n_hstar_true": counts[m][0]} for m in counts} for receiver in means
    }
    ni = {
        "bplus": {
            "m9": {"goal_pass": {"all": _ni_cell(0.16, [-4.05, 4.65], 171),
                                 "handoff_only": _ni_cell(0.21, [-5.28, 6.31], 128)}},
            "m11": {"goal_pass": {"all": _ni_cell(4.410526, [-0.74, 10.67], 171),
                                  "handoff_only": _ni_cell(8.570455, [-1.63, 18.25], 88)}},
        },
        "zs": {
            "m9": {"goal_pass": {"all": _ni_cell(0.50, [-3.02, 5.36], 171),
                                 "handoff_only": _ni_cell(0.67, [-4.14, 6.93], 128)}},
            "m11": {"goal_pass": {"all": _ni_cell(1.94, [-2.17, 6.40], 171),
                                  "handoff_only": _ni_cell(3.77, [-4.78, 10.98], 88)}},
        },
    }
    return {
        "handoff_only": handoff_only,
        "handoff_control_counts": control_counts,
        "ni": ni,
        "rescued_m11": {"bplus": {"summary": {"goal_pass": _ni_cell(48.294118, [34.15, 66.41], 17)}}},
    }


def _make_minimal_depth_fixes_report() -> dict:
    return {"ni": {"bplus": {"m11": {"goal_pass": {"handoff_only": _ni_cell(-0.940845, [-9.53, 7.45], 71)}}}}}


def _make_minimal_robustness_report() -> dict:
    return {
        "F_e_ni_both_ceilings": {
            "ni_table": {
                "t_m11": {
                    "cap25_goal_pass_rate": {"diff_pp": -1.857018, "n_pairs": 114, "scenario": {"ci95_pp": [-8.51, 6.09]}}
                }
            }
        }
    }


def _make_minimal_planning_lit_report() -> dict:
    # Stored as planner minus arm, as CEILHI-03 is.
    return {
        "ceilhi": {
            "ni_reread": {
                "high_minus_prefix_c81_bplus_m11": {"goal_pass": _ni_cell(7.22193, [3.21, 11.47], 114)}
            }
        }
    }


def _populate_v2_fixtures(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in [
        ("b2_decomposition_20260923", _make_minimal_b2_decomposition_report()),
        ("j17_channel_fixes_20260924", _make_minimal_channel_fixes_report()),
        ("j17_hstar_20260924", _make_minimal_hstar_report()),
        ("j17_depth_fixes_20260924", _make_minimal_depth_fixes_report()),
        ("j16_robustness_20260923", _make_minimal_robustness_report()),
        ("j17_planning_lit_20260924", _make_minimal_planning_lit_report()),
    ]:
        (results_dir / f"{name}.report.json").write_text(json.dumps(payload))


# F12 fixtures are SYNTHETIC: every number below is invented for the test (300 pairs, 150 h*),
# and only the key layout follows the three held-out aggregate reports. The file names are the
# ones F12 reads, written under tmp_path.
F12_FIXTURE_NAMES = {
    "j12": "j12_depth_test_normal",
    "j10": "j10_a1_test_normal",
    "j11": "j11_lp2_test_normal",
}


def _f12_prediction(pid: str, left: str, right: str, diff_pp: float, ci: list[float], verdict: str,
                    threshold_pp: float = 0.0, n_handoff: int | None = None) -> dict:
    contrast = {"field": "goal_pass_rate", "n_pairs": 300,
                "scenario": {"clustering": "scenario", "diff_pp": diff_pp, "ci95_pp": ci}}
    if n_handoff is not None:
        contrast["n_handoff"] = n_handoff
    return {"id": pid, "left": left, "right": right, "threshold_pp": threshold_pp, "verdict": verdict,
            "contrast": contrast}


def _f12_secondary(pid: str, left: str, right: str, diff_pp: float, ci: list[float]) -> dict:
    return {"id": pid, "left": left, "right": right, "side": "not_resolved", "decision_bearing": False,
            "contrast": {"field": "goal_pass_rate", "n_pairs": 300,
                         "scenario": {"clustering": "scenario", "diff_pp": diff_pp, "ci95_pp": ci}}}


def _f12_j11_contrast(left: str, right: str, diff_pp: float, ci: list[float], reading: str,
                      threshold_pp: float = 0.0) -> dict:
    return {"left": left, "right": right, "field": "goal_pass_rate", "n_pairs": 300,
            "threshold_pp": threshold_pp, "reading": reading,
            "scenario": {"clustering": "scenario", "diff_pp": diff_pp, "ci95_pp": ci}}


def _make_synthetic_j12_report() -> dict:
    return {"split": "test_normal", "status": "COMPLETE", "predictions": [
        _f12_prediction("D1", "prefix_m11", "prefix_m6", 10.0, [5.0, 15.0], "supported"),
        _f12_prediction("D2", "prefix_zs_m11", "prefix_zs_m6", 6.0, [2.0, 10.0], "supported"),
        _f12_prediction("D3", "prefix_m11", "prefix_m6", 12.0, [4.0, 20.0], "supported", n_handoff=150),
        _f12_prediction("D4", "prefix_zs_m11", "prefix_zs_m6", -1.0, [-6.0, 4.0], "not_supported", n_handoff=150),
    ]}


def _make_synthetic_j10_report() -> dict:
    return {"split": "test_normal", "status": "COMPLETE", "predictions": [
        _f12_prediction("P1", "advise_k1_fullctx", "prefix_m11", -9.0, [-14.0, -4.0], "supported"),
        {"id": "P2", "kind": "cost_ratio", "verdict": "supported"},
        _f12_prediction("P3", "prefix_m11", "planner_alone_cap81", -2.0, [-8.0, 4.0], "not_supported",
                        threshold_pp=-7.0),
        _f12_prediction("P4", "prefix_zs_m11", "prefix_zs_m9", 1.0, [-1.0, 3.0], "directionally_consistent"),
        _f12_prediction("P5", "advise_k1_fullctx", "sft_plan", 3.0, [-2.0, 8.0], "supported"),
        _f12_prediction("P6", "takeover_k10", "advise_k10_fullctx", 4.0, [0.5, 7.5], "supported"),
    ], "amendment1": {"cf": {
        "predictions": [
            _f12_prediction("CF1", "advise_k10_neutral", "advise_k10_fullctx", 3.5, [1.0, 6.0], "supported"),
        ],
        "secondary": [
            _f12_secondary("CF2", "show_k10", "advise_k10_fullctx", 0.5, [-3.0, 4.0]),
            _f12_secondary("CF3", "takeover_k10", "advise_k10_neutral", -0.5, [-4.0, 3.0]),
        ],
    }}}


def _make_synthetic_j11_report() -> dict:
    return {"split": "test_normal", "status": "COMPLETE", "planner": {"code": "PX"}, "contrasts": {
        "L1": _f12_j11_contrast("T", "A", 4.5, [0.5, 8.5], "on_the_boundary"),
        "L2": _f12_j11_contrast("A1", "M_bplus_11", 9.0, [5.0, 13.0], "not_supported"),
        "L3": _f12_j11_contrast("M_bplus_11", "M_bplus_6", 0.2, [-4.0, 4.4], "not_supported"),
        # Registered as C − M^bplus_11 < +7; F12 draws it flipped: -1.5 [-6.5, +5.0] against -7.
        "L4": _f12_j11_contrast("C", "M_bplus_11", 1.5, [-5.0, 6.5], "supported", threshold_pp=7.0),
        "L5": _f12_j11_contrast("M_zs_11", "M_zs_6", 2.0, [-1.0, 5.0], "not_supported"),
    }}


def _populate_f12_fixtures(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    for key, payload in [("j12", _make_synthetic_j12_report()), ("j10", _make_synthetic_j10_report()),
                         ("j11", _make_synthetic_j11_report())]:
        (results_dir / f"{F12_FIXTURE_NAMES[key]}.report.json").write_text(json.dumps(payload))


def _edit_fixture(results_dir: Path, name: str, edit) -> None:
    path = results_dir / f"{name}.report.json"
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data))


def _populate_all_standard_fixtures(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(results_dir / "hj13_shape_post_guard_bands_20260923.report.json", "w") as f:
        json.dump(_make_minimal_shape_post_guard(), f)
    with open(results_dir / "hj13_zeroshot_depth_m6_m9_20260923.report.json", "w") as f:
        json.dump(_make_minimal_zs_depth_m6_m9(), f)
    with open(results_dir / "hj13_zeroshot_depth_m9_m11_20260923.report.json", "w") as f:
        json.dump(_make_minimal_zs_depth_m9_m11(), f)
    with open(results_dir / "hj13_ceiling_cap25_vs_cap81_20260923.report.json", "w") as f:
        json.dump(_make_minimal_ceiling_report(), f)
    with open(results_dir / "hj12_unified_frontier_scenario_20260923.report.json", "w") as f:
        json.dump(_make_minimal_frontier_report(), f)
    with open(results_dir / "hj13_advice_fullctx_matched_20260923.report.json", "w") as f:
        json.dump(_make_minimal_advice_matched_report(), f)
    for m, diff, ci in [(6, -4.12, [-10.41, 1.64]), (9, -0.06, [-7.06, 6.77]), (11, 2.46, [-1.48, 6.43])]:
        with open(results_dir / f"hj13_receiver_contrast_m{m}_20260923.report.json", "w") as f:
            json.dump(_make_minimal_receiver_contrast(m, diff, ci), f)
    with open(results_dir / "hj13_mechanism_zeroshot_20260923c.report.json", "w") as f:
        json.dump(_make_minimal_mechanism_report(), f)
    with open(results_dir / "hj15_qwen_curve_20260923.report.json", "w") as f:
        json.dump(_make_minimal_qwen_curve_report(), f)
    with open(results_dir / "hj16_narrated_tailored_complete_20260923.report.json", "w") as f:
        json.dump(_make_minimal_narrated_tailored_report(), f)
    with open(results_dir / "hj16_narrated_untailored_complete_20260923.report.json", "w") as f:
        json.dump(_make_minimal_narrated_untailored_report(), f)
    with open(results_dir / "hj16_narrated_curve_zs_20260923.report.json", "w") as f:
        json.dump(_make_minimal_narrated_curve_report(tailored=False), f)
    with open(results_dir / "hj16_narrated_curve_bplus_20260923.report.json", "w") as f:
        json.dump(_make_minimal_narrated_curve_report(tailored=True), f)
    with open(results_dir / "hj13_advice_at_price_20260923.report.json", "w") as f:
        json.dump(_make_minimal_advice_at_price_report(), f)
    with open(results_dir / "hj13_advice_at_price_cost_20260923.report.json", "w") as f:
        json.dump(_make_minimal_advice_at_price_cost_report(), f)
    _populate_v2_fixtures(results_dir)
    _populate_f12_fixtures(results_dir)


def test_missing_report_file_is_fatal(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    # Only create one file; the others are missing
    with open(results_dir / "hj13_shape_post_guard_bands_20260923.report.json", "w") as f:
        json.dump(_make_minimal_shape_post_guard(), f)

    with pytest.raises(SystemExit) as exc_info:
        run_figures(results_dir, out_dir, manifest_path, only_fig="F1")
    assert "Fatal [F1]" in str(exc_info.value)
    assert "required report file is missing" in str(exc_info.value)
    assert not (out_dir / "f1_depth_curve.pdf").exists()


def test_missing_json_key_is_fatal(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    _populate_all_standard_fixtures(results_dir)

    # Corrupt shape report by deleting a required key
    shape_path = results_dir / "hj13_shape_post_guard_bands_20260923.report.json"
    data = json.loads(shape_path.read_text())
    del data["arms"]["prefix_m6"]
    shape_path.write_text(json.dumps(data))

    with pytest.raises(SystemExit) as exc_info:
        run_figures(results_dir, out_dir, manifest_path, only_fig="F1")
    assert "Fatal [F1]" in str(exc_info.value)
    assert "arms.prefix_m6.goal_pass_all" in str(exc_info.value)


def test_empty_series_is_fatal(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    _populate_all_standard_fixtures(results_dir)

    # Empty cumulative dictionary for M1 in mechanism report
    mech_path = results_dir / "hj13_mechanism_zeroshot_20260923c.report.json"
    data = json.loads(mech_path.read_text())
    data["m1_api_novelty"]["cumulative_by_position"] = {}
    mech_path.write_text(json.dumps(data))

    with pytest.raises(SystemExit) as exc_info:
        run_figures(results_dir, out_dir, manifest_path, only_fig="F4")
    assert "Fatal [F4]" in str(exc_info.value)
    assert "empty series" in str(exc_info.value)


def test_manifest_lists_every_generated_figure_and_its_keys(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    _populate_all_standard_fixtures(results_dir)

    run_figures(results_dir, out_dir, manifest_path)
    assert manifest_path.is_file()

    manifest = json.loads(manifest_path.read_text())
    fig_ids = [entry["figure_id"] for entry in manifest]
    assert "F1" in fig_ids
    assert "F2" in fig_ids
    assert "F3" in fig_ids
    assert "F4" in fig_ids
    assert "F5" in fig_ids
    assert "F6" in fig_ids
    assert "F7" in fig_ids
    assert "F8" in fig_ids

    # Check F1 entry structure
    f1_entry = next(e for e in manifest if e["figure_id"] == "F1")
    assert f1_entry["column"] == "two-column"
    assert f1_entry["width_in"] == 7.0
    assert Path(f1_entry["file_pdf"]).is_file()
    assert Path(f1_entry["file_png"]).is_file()
    assert len(f1_entry["series"]) >= 2
    for s in f1_entry["series"]:
        assert len(s["json_keys"]) > 0

    # Check F6 entry structure
    f6_entry = next(e for e in manifest if e["figure_id"] == "F6")
    assert f6_entry["column"] == "two-column"
    assert Path(f6_entry["file_pdf"]).is_file()
    assert Path(f6_entry["file_png"]).is_file()
    assert len(f6_entry["series"]) == 2

    for figure_id in ("F7", "F8"):
        entry = next(e for e in manifest if e["figure_id"] == figure_id)
        assert Path(entry["file_pdf"]).is_file()
        assert Path(entry["file_png"]).is_file()
        assert entry["skipped_reason"] is None


def test_f5_no_floor_series_drawn(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    original_axhline = plt.Axes.axhline
    axhline_calls = []

    def mocked_axhline(self, *args, **kwargs):
        axhline_calls.append((args, kwargs))
        return original_axhline(self, *args, **kwargs)

    with patch.object(plt.Axes, "axhline", mocked_axhline):
        entry = generate_f5_second_family(results_dir, out_dir)

    assert entry["figure_id"] == "F5"
    assert entry["file_pdf"] is not None and Path(entry["file_pdf"]).is_file()
    assert entry["file_png"] is not None and Path(entry["file_png"]).is_file()
    assert entry["skipped_reason"] is None

    # Assert no horizontal floor line was drawn
    assert len(axhline_calls) == 0, f"Expected 0 axhline calls in F5, found {len(axhline_calls)}"

    # Assert series contains only the 3 prefix points and no floor series
    assert len(entry["series"]) == 1
    s = entry["series"][0]
    assert s["n_points"] == 3
    for k in s["json_keys"]:
        assert "floor" not in k.lower()
        assert "executor_alone" not in k.lower()
        assert "plan_only" not in k.lower()


def test_f5_mandatory_annotation_present(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    entry = generate_f5_second_family(results_dir, out_dir)
    assert entry["figure_id"] == "F5"
    assert "annotation" in entry
    assert entry["annotation"] == MANDATORY_F5_ANNOTATION
    assert "Floor not shown" in entry["annotation"]
    assert "QWEN-03" in entry["annotation"]


def test_f1_marginal_bands_are_suppressed_by_design(tmp_path: Path) -> None:
    """F1 must NOT shade per-arm marginal intervals even when the report has them.

    They carry between-task variance that this paired design removes, so they are
    2-3x wider than every contrast the paper claims. Drawing them beside those claims
    would invite the opposite conclusion. The keys stay in the report; the band stays off.
    """
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    # Add interval keys to shape report
    shape_path = results_dir / "hj13_shape_post_guard_bands_20260923.report.json"
    data = json.loads(shape_path.read_text())
    for m in (2, 4, 6, 7, 8, 9, 10, 11):
        data["arms"][f"prefix_m{m}"]["goal_pass_all_ci95"] = [0.65, 0.85]
    shape_path.write_text(json.dumps(data))

    original_fill_between = plt.Axes.fill_between
    fill_between_calls = []

    def mocked_fill_between(self, *args, **kwargs):
        fill_between_calls.append((args, kwargs))
        return original_fill_between(self, *args, **kwargs)

    with patch.object(plt.Axes, "fill_between", mocked_fill_between):
        entry = generate_f1_depth_curve(results_dir, out_dir)

    assert entry["figure_id"] == "F1"
    # The interval keys are present in the report, so suppression is a choice, not a gap.
    assert "goal_pass_all_ci95" in json.loads(shape_path.read_text())["arms"]["prefix_m9"]
    assert entry["series"][0]["has_confidence_band"] is False
    assert "paired" in entry["series"][0]["interval_note"]


def test_f6_narrated_vs_executed_generation_and_manifest(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    entry = generate_f6_narrated_vs_executed(results_dir, out_dir)
    assert entry["figure_id"] == "F6"
    assert entry["file_pdf"] is not None and Path(entry["file_pdf"]).is_file()
    assert entry["file_png"] is not None and Path(entry["file_png"]).is_file()
    assert len(entry["series"]) == 2
    for s in entry["series"]:
        assert s["n_points"] == 3
        assert len(s["json_keys"]) > 0


def test_f7_narrated_minus_executed_generation_and_manifest(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    errorbar_x = []
    original_errorbar = plt.Axes.errorbar

    def mocked_errorbar(self, *args, **kwargs):
        errorbar_x.append(list(args[0]))
        return original_errorbar(self, *args, **kwargs)

    with patch.object(plt.Axes, "errorbar", mocked_errorbar):
        entry = generate_f7_narrated_minus_executed(results_dir, out_dir)
    assert entry["figure_id"] == "F7"
    assert Path(entry["file_pdf"]).is_file()
    assert Path(entry["file_png"]).is_file()
    assert len(entry["series"]) == 2
    assert all(series["n_points"] == 3 for series in entry["series"])
    assert errorbar_x == [[5.92, 8.92, 10.92], [6.08, 9.08, 11.08]]
    assert "below zero mean execution beat narration" in entry["caption"]
    assert "not a difference-in-differences" in entry["caption"]


def test_f8_advice_cost_quality_generation_and_manifest(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    entry = generate_f8_advice_cost_quality(results_dir, out_dir)
    assert entry["figure_id"] == "F8"
    assert Path(entry["file_pdf"]).is_file()
    assert Path(entry["file_png"]).is_file()
    assert [series["n_points"] for series in entry["series"]] == [2, 2]
    assert "3.2× the tokens" in entry["caption"]
    assert "registered H2 test" in entry["caption"]


def test_validate_output_path_refuses_forbidden_locations() -> None:
    with pytest.raises(ValueError, match="forbidden: contains test_normal or test_challenge"):
        validate_output_path("/tmp/paper/figures/test_normal/fig1.pdf")

    with pytest.raises(ValueError, match="forbidden: contains test_normal or test_challenge"):
        validate_output_path("output/test_challenge/fig.png")

    with pytest.raises(ValueError, match="cannot write under"):
        validate_output_path("/scratch/n12194778/sidekick/results/paper/fig1.pdf")

    # Valid path does not raise
    validate_output_path(Path("paper/figures/fig1.pdf"))


def test_no_breakpoint_marker_in_depth_curve(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    _populate_all_standard_fixtures(results_dir)

    # Spy on axvline calls to ensure no vertical threshold line is drawn
    original_axvline = plt.Axes.axvline
    axvline_calls = []

    def mocked_axvline(self, *args, **kwargs):
        axvline_calls.append((args, kwargs))
        return original_axvline(self, *args, **kwargs)

    with patch.object(plt.Axes, "axvline", mocked_axvline):
        entry = generate_f1_depth_curve(results_dir, out_dir)

    assert entry["figure_id"] == "F1"
    # Verify no vertical lines were drawn
    assert len(axvline_calls) == 0, f"Expected 0 axvline calls in F1, found {len(axvline_calls)}: {axvline_calls}"


def test_f1_legend_placed_outside_axes(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    legend_calls = []
    original_legend = plt.Axes.legend

    def mocked_legend(self, *args, **kwargs):
        legend_calls.append((args, kwargs))
        return original_legend(self, *args, **kwargs)

    with patch.object(plt.Axes, "legend", mocked_legend):
        generate_f1_depth_curve(results_dir, out_dir)

    assert len(legend_calls) >= 1
    # Check that bbox_to_anchor was used to place legend outside axes
    _, kwargs = legend_calls[0]
    assert "bbox_to_anchor" in kwargs
    assert kwargs["bbox_to_anchor"][0] > 1.0


def test_f4_annotations_offset_from_curve(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    annotate_calls = []
    original_annotate = plt.Axes.annotate

    def mocked_annotate(self, *args, **kwargs):
        annotate_calls.append((args, kwargs))
        return original_annotate(self, *args, **kwargs)

    with patch.object(plt.Axes, "annotate", mocked_annotate):
        generate_f4_mechanism(results_dir, out_dir)

    # Find annotations for m=9 and m=11 in panel 1
    m9_ann = next((kwargs for args, kwargs in annotate_calls if args and "$m=9$" in str(args[0])), None)
    m11_ann = next((kwargs for args, kwargs in annotate_calls if args and "$m=11$" in str(args[0])), None)
    assert m9_ann is not None
    assert m11_ann is not None
    # m=9 should be offset left/up (xytext=(-8, 8), ha='right')
    assert m9_ann["xytext"][0] < 0 and m9_ann["xytext"][1] > 0
    # m=11 should be offset right/down (xytext=(8, -18), ha='left')
    assert m11_ann["xytext"][0] > 0 and m11_ann["xytext"][1] < 0


def test_f6_legend_placed_outside_axes(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_all_standard_fixtures(results_dir)

    legend_calls = []
    original_legend = plt.Axes.legend

    def mocked_legend(self, *args, **kwargs):
        legend_calls.append((args, kwargs))
        return original_legend(self, *args, **kwargs)

    with patch.object(plt.Axes, "legend", mocked_legend):
        generate_f6_narrated_vs_executed(results_dir, out_dir)

    assert len(legend_calls) == 1
    _, kwargs = legend_calls[0]
    assert "bbox_to_anchor" in kwargs
    assert kwargs["bbox_to_anchor"][0] > 1.0


def _spy(method_name: str):
    """Record the positional arguments of every call to one Axes method."""
    calls: list[tuple] = []
    original = getattr(plt.Axes, method_name)

    def spy(self, *args, **kwargs):
        calls.append((args, kwargs))
        return original(self, *args, **kwargs)

    return calls, patch.object(plt.Axes, method_name, spy)


def test_f9_channel_limit_points_and_split(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_v2_fixtures(results_dir)

    scatter_calls, scatter_patch = _spy("scatter")
    errorbar_calls, errorbar_patch = _spy("errorbar")
    with scatter_patch, errorbar_patch:
        entry = generate_f9_channel_limit(results_dir, out_dir)

    assert entry["figure_id"] == "F9"
    assert Path(entry["file_pdf"]).is_file() and Path(entry["file_png"]).is_file()
    # Left panel, in T, S, N, A order: x is the step-limit rate, y the arm mean.
    points = [(args[0][0], args[1][0]) for args, _ in scatter_calls]
    assert points == [(0.011696, 0.7899), (0.064327, 0.7516), (0.081871, 0.7658), (0.116959, 0.7285)]
    # Right panel: D0 whole, then its two parts; 4.07 + 2.06 = 6.13 by hand.
    assert [args[0][0] for args, _ in errorbar_calls] == [6.13, 4.07, 2.06]
    assert "(n = 22)" in entry["caption"] and "(n = 149)" in entry["caption"]
    keys = [k for s in entry["series"] for k in s["json_keys"]]
    assert "j17_channel_fixes_20260924.report.json:limits.per_arm.takeover_k10.rate" in keys
    assert "b2_decomposition_20260923.report.json:contrasts.D0.scenario.ci95_pp" in keys


def test_f9_refuses_missing_key_mismatched_population_and_parts_that_do_not_sum(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_channel_fixes_20260924", lambda d: d["limits"]["split"]["D0"].pop("neither"))
    with pytest.raises(SystemExit) as exc_info:
        generate_f9_channel_limit(results_dir, out_dir)
    assert "Fatal [F9]" in str(exc_info.value)
    assert "limits.split.D0.neither.n" in str(exc_info.value)

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_channel_fixes_20260924",
                  lambda d: d["limits"]["per_arm"]["show_k10"].update({"n": 114}))
    with pytest.raises(SystemExit, match="over 114"):
        generate_f9_channel_limit(results_dir, out_dir)

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_channel_fixes_20260924",
                  lambda d: d["limits"]["split"]["D0"]["neither"].update({"contribution_pp": 3.06}))
    with pytest.raises(SystemExit, match="sum to 7.13 pp but D0 is 6.13 pp"):
        generate_f9_channel_limit(results_dir, out_dir)


def test_f10_lines_and_population_counts(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_v2_fixtures(results_dir)

    plot_calls, plot_patch = _spy("plot")
    annotate_calls, annotate_patch = _spy("annotate")
    with plot_patch, annotate_patch:
        entry = generate_f10_depth_hstar(results_dir, out_dir)

    assert entry["figure_id"] == "F10"
    assert Path(entry["file_pdf"]).is_file() and Path(entry["file_png"]).is_file()
    lines = [(list(args[0]), list(args[1])) for args, _ in plot_calls]
    # Tailored panel first: all, h* handoff, silenced.
    assert lines[:3] == [
        ([6, 9, 11], [0.729942, 0.771357, 0.813854]),
        ([6, 9, 11], [0.723473, 0.727844, 0.7745]),
        ([6, 9, 11], [1.0, 0.900884, 0.855578]),
    ]
    assert len(lines) == 6
    labels = [args[0] for args, _ in annotate_calls]
    # Handoff and silenced sizes at each m, both panels; 167 + 4 = 128 + 43 = 88 + 83 = 171.
    assert labels == ["n = 167", "n = 128", "n = 88", "n = 4", "n = 43", "n = 83"] * 2
    assert "(171 pairs)" in entry["caption"]
    assert entry["fallback"].startswith("not taken")


def test_f10_refuses_missing_key_and_disagreeing_populations(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_hstar_20260924",
                  lambda d: d["handoff_only"]["zs"]["m9"]["goal_pass"].pop("mean_silenced"))
    with pytest.raises(SystemExit) as exc_info:
        generate_f10_depth_hstar(results_dir, out_dir)
    assert "Fatal [F10]" in str(exc_info.value)
    assert "handoff_only.zs.m9.goal_pass.mean_silenced" in str(exc_info.value)

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_hstar_20260924",
                  lambda d: d["handoff_control_counts"]["bplus"]["m11"].update({"n_hstar_true": 71}))
    with pytest.raises(SystemExit, match="bplus m=11 populations disagree"):
        generate_f10_depth_hstar(results_dir, out_dir)


def test_f11_rows_margin_negation_and_identity(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_v2_fixtures(results_dir)

    errorbar_calls, errorbar_patch = _spy("errorbar")
    axvline_calls, axvline_patch = _spy("axvline")
    annotate_calls, annotate_patch = _spy("annotate")
    with errorbar_patch, axvline_patch, annotate_patch:
        entry = generate_f11_ni_forest(results_dir, out_dir)

    assert entry["figure_id"] == "F11"
    assert Path(entry["file_pdf"]).is_file() and Path(entry["file_png"]).is_file()
    # Every row but the off-scale rescue is an error bar; CEILHI-03's stored +7.22193 is drawn negated.
    drawn = [args[0][0] for args, _ in errorbar_calls]
    assert drawn == [0.16, 0.21, 4.410526, 8.570455, -0.940845, 0.50, 0.67, 1.94, 3.77, -1.857018, -7.22193]
    assert [args[0] for args, _ in axvline_calls] == [-7.0, 0.0]
    assert "+48.29 [+34.15, +66.41]" in [args[0] for args, _ in annotate_calls]
    rescued = next(s for s in entry["series"] if s["ledger_ids"] == ["HSTAR-14"])
    assert rescued["drawn_offscale"] is True
    ceilhi = next(s for s in entry["series"] if s["ledger_ids"] == ["CEILHI-03"])
    assert ceilhi["negated"] is True
    # HSTAR-18 by hand: (71 x -0.940845 + 17 x 48.294118) / 88 = 754.200011 / 88 = 8.570455.
    assert entry["identity_check"]["weighted_pp"] == pytest.approx(8.570455, abs=1e-6)
    assert "flag-true (n = 71" in entry["caption"] and "rescued (n = 17" in entry["caption"]


def test_f11_refuses_missing_key_and_broken_identity(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_planning_lit_20260924", lambda d: d["ceilhi"].pop("ni_reread"))
    with pytest.raises(SystemExit) as exc_info:
        generate_f11_ni_forest(results_dir, out_dir)
    assert "Fatal [F11]" in str(exc_info.value)
    assert "ceilhi.ni_reread.high_minus_prefix_c81_bplus_m11.goal_pass.diff_pp" in str(exc_info.value)

    _populate_v2_fixtures(results_dir)
    _edit_fixture(results_dir, "j17_hstar_20260924",
                  lambda d: d["rescued_m11"]["bplus"]["summary"]["goal_pass"].update({"diff_pp": 40.0}))
    with pytest.raises(SystemExit, match="HSTAR-18 identity fails"):
        generate_f11_ni_forest(results_dir, out_dir)


def test_run_figures_subset_keeps_other_manifest_entries(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"
    _populate_all_standard_fixtures(results_dir)

    run_figures(results_dir, out_dir, manifest_path)
    first = json.loads(manifest_path.read_text())
    assert [e["figure_id"] for e in first] == [f"F{i}" for i in range(1, 13)]

    run_figures(results_dir, out_dir, manifest_path, only_fig="F9, f11")
    second = json.loads(manifest_path.read_text())
    assert [e["figure_id"] for e in second] == [f"F{i}" for i in range(1, 13)]
    assert second[0] == first[0]


def test_f12_rows_verdict_fills_margin_and_flip(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    _populate_f12_fixtures(results_dir)

    errorbar_calls, errorbar_patch = _spy("errorbar")
    vlines_calls, vlines_patch = _spy("vlines")
    axvline_calls, axvline_patch = _spy("axvline")
    text_calls, text_patch = _spy("text")
    with errorbar_patch, vlines_patch, axvline_patch, text_patch:
        entry = generate_f12_registered_forest(results_dir, out_dir)

    assert entry["figure_id"] == "F12"
    assert entry["file_pdf"].endswith("f12_registered_forest.pdf")
    assert entry["file_png"].endswith("f12_registered_forest.png")
    assert Path(entry["file_pdf"]).is_file() and Path(entry["file_png"]).is_file()
    assert "test_normal" not in Path(entry["file_pdf"]).name

    # J12 D1-D4, J10 P1 P3-P6 CF1-CF3, J11 L1-L5, in that order; P2 (a cost ratio) is not a row.
    # L4's stored +1.5 [-5.0, +6.5] (C - M) is drawn flipped as -1.5 [-6.5, +5.0].
    ids = [s["row_id"] for s in entry["series"]]
    assert ids == ["D1", "D2", "D3", "D4", "P1", "P3", "P4", "P5", "P6", "CF1", "CF2", "CF3",
                   "L1", "L2", "L3", "L4", "L5"]
    drawn = [args[0][0] for args, _ in errorbar_calls]
    assert drawn == [10.0, 6.0, 12.0, -1.0, -9.0, -2.0, 1.0, 3.0, 4.0, 3.5, 0.5, -0.5, 4.5, 9.0, 0.2, -1.5, 2.0]
    l4_index = ids.index("L4")
    _, l4_kwargs = errorbar_calls[l4_index]
    assert l4_kwargs["xerr"] == [[5.0], [6.5]]  # -1.5 - (-6.5) below, 5.0 - (-1.5) above
    l4 = entry["series"][l4_index]
    assert l4["flipped"] is True and l4["ci95_pp_scenario"] == [-6.5, 5.0] and l4["threshold_pp_drawn"] == -7.0
    p4 = entry["series"][ids.index("P4")]
    assert p4["ledger_ids"] == ["J10-05"] and p4["verdict"] == "directionally_consistent"
    assert p4["flipped"] is False and p4["non_inferiority"] is False and p4["threshold_pp_drawn"] == 0.0
    l5 = entry["series"][ids.index("L5")]
    assert l5["ledger_ids"] == ["J11-07"] and l5["ci95_pp_scenario"] == [-1.0, 5.0] and l5["verdict"] == "not_supported"

    # Marker fill by verdict: one style per class, not_supported open, on_the_boundary half-filled.
    styles = {}
    for (_, kwargs), series in zip(errorbar_calls, entry["series"]):
        style = (kwargs["markerfacecolor"], kwargs["fillstyle"])
        styles.setdefault(series["verdict"], set()).add(style)
    assert all(len(v) == 1 for v in styles.values())
    assert styles["not_supported"] == {("white", "full")}
    assert next(iter(styles["on_the_boundary"]))[1] == "left"
    # directionally consistent (P4) shares the unresolved class with CF2 and CF3's not_resolved.
    assert styles["directionally_consistent"] == styles["not_resolved"]
    assert len({next(iter(v)) for v in styles.values()}) == 4

    # The zero line spans the axes; the margin is a dashed segment on P3 and L4 only.
    assert [args[0] for args, _ in axvline_calls] == [0.0]
    assert [args[0] for args, _ in vlines_calls] == [-7.0, -7.0]
    assert [s["row_id"] for s in entry["series"] if s["non_inferiority"]] == ["P3", "L4"]

    # The verdict string sits at the right of every row, CF2 and CF3 marked not decision-bearing.
    verdict_texts = [args[2] for args, _ in text_calls]
    assert verdict_texts == [
        "supported", "supported", "supported", "not supported",
        "supported", "not supported", "directionally consistent", "supported", "supported", "supported",
        "not resolved†", "not resolved†",
        "on the boundary", "not supported", "not supported", "supported", "not supported",
    ]

    # Row labels carry n only where it differs from the common 300; the caption names the rest.
    labels = [s["label"] for s in entry["series"]]
    assert labels[2].endswith("(n = 150)") and labels[3].endswith("(n = 150)")
    assert not any("(n = 300)" in label for label in labels)
    # One arm pair, one name: J11's L1 (T − A) is J10's P6 contrast under the second planner.
    assert labels[ids.index("L1")] == "L1  takeover − correction-prompt advice"
    assert labels[ids.index("P6")] == "P6  takeover − correction-prompt advice"
    caption = entry["caption"]
    assert "300 pairs per row except D3 (n = 150), D4 (n = 150)" in caption
    assert "δ = −7.00 pp" in caption and "upper bound < +7.00 pp" in caption and "drawn flipped" in caption
    assert "† CF2, CF3: pre-specified, not decision-bearing." in caption
    assert "D1 J12-02" in caption and "CF3 J10-09" in caption and "L4 J11-06" in caption
    assert "P4 J10-05" in caption and "L5 J11-07" in caption
    assert caption.startswith("Every registered held-out (`test_normal`) `goal_pass` prediction of J12, J10 and J11")
    assert "J10's P2, a cost ratio, is not a `goal_pass` contrast and is not drawn" in caption
    assert "Directionally consistent (P4): the point lies on the predicted side of 0" in caption
    assert "drawn, it is −1.50 pp, [−6.50, +5.00], its lower bound 0.50 pp above the margin." in caption
    assert "M^bplus" not in caption
    keys = [k for s in entry["series"] for k in s["json_keys"]]
    assert "j12_depth_test_normal.report.json:predictions[D3].contrast.scenario.ci95_pp" in keys
    assert "j10_a1_test_normal.report.json:amendment1.cf.secondary[CF2].side" in keys
    assert "j11_lp2_test_normal.report.json:contrasts.L4.scenario.diff_pp" in keys
    assert "j10_a1_test_normal.report.json:predictions[P4].verdict" in keys
    assert "j11_lp2_test_normal.report.json:contrasts.L5.reading" in keys


def test_f12_refuses_missing_key_wrong_arms_unknown_verdict_and_incomplete_report(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j12"],
                  lambda d: d["predictions"][2]["contrast"]["scenario"].pop("ci95_pp"))
    with pytest.raises(SystemExit) as exc_info:
        generate_f12_registered_forest(results_dir, out_dir)
    assert "Fatal [F12]" in str(exc_info.value)
    assert "predictions[D3].contrast.scenario.ci95_pp" in str(exc_info.value)

    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j11"],
                  lambda d: d["contrasts"]["L4"].update({"left": "M_bplus_11", "right": "C"}))
    with pytest.raises(SystemExit, match="L4 in j11_lp2_test_normal.report.json is M_bplus_11 − C"):
        generate_f12_registered_forest(results_dir, out_dir)

    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j10"],
                  lambda d: d["amendment1"]["cf"]["secondary"][0].update({"side": "maybe"}))
    with pytest.raises(SystemExit, match="unknown verdict 'maybe'"):
        generate_f12_registered_forest(results_dir, out_dir)

    _populate_f12_fixtures(results_dir)
    # P3 at -5 against L4's flipped -7.
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j10"], lambda d: d["predictions"][2].update({"threshold_pp": -5.0}))
    with pytest.raises(SystemExit, match="disagree on one negative margin"):
        generate_f12_registered_forest(results_dir, out_dir)

    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j12"], lambda d: d.update({"status": "INCOMPLETE"}))
    with pytest.raises(SystemExit, match="COMPLETE test_normal read"):
        generate_f12_registered_forest(results_dir, out_dir)
    assert not (out_dir / "f12_registered_forest.pdf").exists()


def test_f12_refuses_wrong_field_wrong_split_margin_flag_mismatch_and_point_outside_interval(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"

    # A row whose contrast is on another field than goal_pass_rate.
    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j12"],
                  lambda d: d["predictions"][0]["contrast"].update({"field": "tgc"}))
    with pytest.raises(SystemExit, match=re.escape("D1 in j12_depth_test_normal.report.json is prefix_m11 − prefix_m6 on tgc")):
        generate_f12_registered_forest(results_dir, out_dir)

    # A COMPLETE report on another split than test_normal.
    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j10"], lambda d: d.update({"split": "dev"}))
    with pytest.raises(SystemExit, match=re.escape("j10_a1_test_normal.report.json is split 'dev', status 'COMPLETE'")):
        generate_f12_registered_forest(results_dir, out_dir)

    # A row F12 reads against 0 whose report carries a margin (P5 is predictions[4]) ...
    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j10"], lambda d: d["predictions"][4].update({"threshold_pp": -7.0}))
    with pytest.raises(SystemExit, match=re.escape("P5 threshold_pp is -7.0; F12 draws it as a row read against 0")):
        generate_f12_registered_forest(results_dir, out_dir)

    # ... and a non-inferiority row whose report carries 0.
    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j11"], lambda d: d["contrasts"]["L4"].update({"threshold_pp": 0.0}))
    with pytest.raises(SystemExit, match=re.escape("L4 threshold_pp is 0.0; F12 draws it as a non-inferiority row")):
        generate_f12_registered_forest(results_dir, out_dir)

    # A point outside its own interval.
    _populate_f12_fixtures(results_dir)
    _edit_fixture(results_dir, F12_FIXTURE_NAMES["j11"],
                  lambda d: d["contrasts"]["L3"]["scenario"].update({"diff_pp": 9.0}))
    with pytest.raises(SystemExit, match=re.escape("L3 point 9.0 lies outside [-4.0, 4.4]")):
        generate_f12_registered_forest(results_dir, out_dir)
    assert not (out_dir / "f12_registered_forest.pdf").exists()
