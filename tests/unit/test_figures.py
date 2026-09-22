"""Unit tests for figure generator (Brief X41).

All tests use tmp_path and scripted minimal report JSON fixtures.
No real campaign data or network connections are accessed in tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from scripts.analysis.figures import (
    generate_f1_depth_curve,
    generate_f2_channel_budget,
    generate_f3_tailoring_gap,
    generate_f4_mechanism,
    generate_f5_second_family,
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


def _populate_all_standard_fixtures(results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with open(results_dir / "hj13_shape_post_guard_20260923.report.json", "w") as f:
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


def test_missing_report_file_is_fatal(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    # Only create one file; the others are missing
    with open(results_dir / "hj13_shape_post_guard_20260923.report.json", "w") as f:
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
    shape_path = results_dir / "hj13_shape_post_guard_20260923.report.json"
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

    # Check F1 entry structure
    f1_entry = next(e for e in manifest if e["figure_id"] == "F1")
    assert f1_entry["column"] == "two-column"
    assert f1_entry["width_in"] == 7.0
    assert Path(f1_entry["file_pdf"]).is_file()
    assert Path(f1_entry["file_png"]).is_file()
    assert len(f1_entry["series"]) >= 2
    for s in f1_entry["series"]:
        assert len(s["json_keys"]) > 0


def test_skipped_figure_records_a_reason_and_does_not_fail(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    out_dir = tmp_path / "figures"
    manifest_path = out_dir / "figures_manifest.json"

    _populate_all_standard_fixtures(results_dir)

    # Qwen floor reports are absent by default
    entry = generate_f5_second_family(results_dir, out_dir)
    assert entry["figure_id"] == "F5"
    assert entry["file_pdf"] is None
    assert entry["file_png"] is None
    assert entry["skipped_reason"] is not None
    assert "Qwen floor reports" in entry["skipped_reason"]


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
