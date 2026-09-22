"""Tests for the campaign provenance index generator.

The index is a documentation artifact, so the risk is not a wrong number but a *quietly
incomplete* one: a campaign that is cited and silently omitted, or a crash convention that
drifts from the one the frontier report scores with. Both are tested here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.analysis.campaign_index import (
    CRASH_ERROR_TYPE,
    build_index,
    campaign_ids_in_text,
    collect_citations,
    summarise_campaign,
    to_markdown,
)


def write_episode(root: Path, campaign: str, system: str, seed: int, task: str, **fields) -> None:
    d = root / campaign / system / str(seed) / f"{task}_v0"
    d.mkdir(parents=True, exist_ok=True)
    row = {"task_id": task, "seed": seed, "system": system}
    row.update(fields)
    (d / "result.json").write_text(json.dumps(row), encoding="utf-8")


def write_report(reports: Path, name: str, payload: dict) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    (reports / name).write_text(json.dumps(payload), encoding="utf-8")


# --- finding which campaigns are cited -------------------------------------------------


def test_campaign_ids_are_read_from_result_root_paths() -> None:
    text = json.dumps({
        "arm_sources": {
            "a": "/scratch/n12194778/sidekick/results/hj17_prefix_c81_zs_m6_20260923",
            "b": "/scratch/n12194778/sidekick/results/hj18_prefix_c81s3_zs_m6_20260924",
        }
    })
    assert campaign_ids_in_text(text) == {
        "hj17_prefix_c81_zs_m6_20260923",
        "hj18_prefix_c81s3_zs_m6_20260924",
    }


def test_a_bare_campaign_like_word_is_not_mistaken_for_a_citation() -> None:
    """Anchoring on the results root is the whole point: notes mention arm names freely."""
    text = json.dumps({"note": "compare hj17_prefix_c81_zs_m6_20260923 against the ceiling"})
    assert campaign_ids_in_text(text) == set()


def test_collect_citations_records_every_citing_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "a.json", {"src": f"{root}/camp_one"})
    write_report(reports, "b.json", {"src": f"{root}/camp_one", "other": f"{root}/camp_two"})

    citations = collect_citations(reports)

    assert citations["camp_one"]["used_by"] == ["a.json", "b.json"]
    assert citations["camp_two"]["used_by"] == ["b.json"]


def test_a_campaign_listed_only_as_an_excluded_candidate_is_not_a_dependency(tmp_path: Path) -> None:
    """The mechanism reports record ~21 rejected candidate paths that never existed.

    Counting those as dependencies made the index announce a provenance gap that does not
    exist, which is a worse failure than having no index.
    """
    reports = tmp_path / "reports"
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "mech.json", {
        "arms_used": {
            "primary": {"m6": f"{root}/real_arm/prefix_handoff"},
            "excluded_arms": [{"path": f"{root}/never_existed/prefix_handoff"}],
        }
    })

    index = build_index(reports, tmp_path / "results")

    assert index["campaigns"]["real_arm"]["is_dependency"] is True
    assert index["campaigns"]["never_existed"]["is_dependency"] is False
    assert index["campaigns"]["never_existed"]["listed_as_excluded_by"] == ["mech.json"]
    # The absent candidate must not be counted as a missing dependency.
    assert index["missing_dependencies"] == ["real_arm"]


def test_a_campaign_used_in_one_report_and_excluded_in_another_is_still_a_dependency(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "a.json", {"arms_used": {"primary": {"m6": f"{root}/c"}}})
    write_report(reports, "b.json", {"arms_used": {"excluded_arms": [{"path": f"{root}/c"}]}})

    index = build_index(reports, tmp_path / "results")

    assert index["campaigns"]["c"]["is_dependency"] is True
    assert index["campaigns"]["c"]["used_by"] == ["a.json"]
    assert index["campaigns"]["c"]["listed_as_excluded_by"] == ["b.json"]


def test_walk_strings_reports_the_key_path() -> None:
    from scripts.analysis.campaign_index import walk_strings

    pairs = dict(walk_strings({"a": {"b": ["x", "y"]}}))

    assert pairs["a.b.0"] == "x"
    assert pairs["a.b.1"] == "y"


# --- summarising one campaign ----------------------------------------------------------


def test_summary_counts_episodes_seeds_and_error_types(tmp_path: Path) -> None:
    for seed in (1, 2):
        for t in ("t1", "t2"):
            write_episode(tmp_path, "c", "sys", seed, t, goal_pass_rate=0.5, tgc=0.25, error_type=None)
    write_episode(tmp_path, "c", "sys", 3, "t3", goal_pass_rate=1.0, tgc=1.0, error_type="limit")

    rec = summarise_campaign(tmp_path / "c")

    assert rec["present"] is True
    assert rec["n_episodes"] == 5
    assert rec["n_tasks"] == 3
    assert rec["seeds"] == [1, 2, 3]
    assert rec["error_types"] == {"limit": 1, "none": 4}


def test_a_limit_episode_is_not_a_crash_and_keeps_its_score(tmp_path: Path) -> None:
    """`limit` counted as a crash would silently zero real scores across the whole index."""
    write_episode(tmp_path, "c", "sys", 1, "t1", goal_pass_rate=1.0, tgc=1.0, error_type="limit")

    rec = summarise_campaign(tmp_path / "c")

    assert rec["n_crashed"] == 0
    assert rec["goal_pass_mean"] == pytest.approx(1.0)


def test_a_crashed_episode_scores_zero(tmp_path: Path) -> None:
    write_episode(tmp_path, "c", "sys", 1, "t1", goal_pass_rate=1.0, tgc=1.0, error_type=None)
    write_episode(tmp_path, "c", "sys", 1, "t2", goal_pass_rate=1.0, tgc=1.0, error_type="crash")

    rec = summarise_campaign(tmp_path / "c")

    assert rec["n_crashed"] == 1
    assert rec["goal_pass_mean"] == pytest.approx(0.5)


def test_crash_constant_matches_the_frontier_report_convention() -> None:
    """Asserted against the source of truth rather than trusting the local copy."""
    from scripts.analysis import j8_frontier

    assert CRASH_ERROR_TYPE == j8_frontier.CRASH_ERROR_TYPE


def test_handoff_source_campaign_is_surfaced(tmp_path: Path) -> None:
    """A prefix arm's source is what distinguishes trajectory-paired from task-paired."""
    write_episode(
        tmp_path, "c", "sys", 1, "t1",
        goal_pass_rate=1.0,
        config={"handoff": {"source_campaign": "hj13_planner_alone_cap81_20260923"}},
    )

    rec = summarise_campaign(tmp_path / "c")

    assert rec["handoff_source_campaigns"] == ["hj13_planner_alone_cap81_20260923"]


def test_a_cited_but_absent_campaign_is_reported_not_dropped(tmp_path: Path) -> None:
    """Dropping it would make the index look complete while hiding a missing dependency."""
    reports = tmp_path / "reports"
    write_report(reports, "a.json", {"src": "/scratch/n12194778/sidekick/results/gone"})

    index = build_index(reports, tmp_path / "results")

    assert index["campaigns"]["gone"]["present"] is False
    assert index["n_campaigns_referenced"] == 1
    assert index["n_dependencies"] == 1
    assert index["n_dependencies_present"] == 0
    assert index["missing_dependencies"] == ["gone"]
    assert "MISSING" in to_markdown(index)


def test_unreadable_episode_is_counted_not_silently_skipped(tmp_path: Path) -> None:
    write_episode(tmp_path, "c", "sys", 1, "t1", goal_pass_rate=1.0)
    bad = tmp_path / "c" / "sys" / "1" / "t2_v0"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "result.json").write_text("{not json", encoding="utf-8")

    rec = summarise_campaign(tmp_path / "c")

    assert rec["error_types"].get("UNREADABLE") == 1
    assert rec["n_episodes"] == 2


# --- provenance recovered from the repo, and the gap it papers over ---------------------


def test_config_index_joins_on_campaign_id_not_filename(tmp_path: Path) -> None:
    """The runner derives the output directory from `campaign_id`, so that is the join.

    Filename convention would be wrong: hj19_prefix_m11_qwen_notk.yaml declares
    hj19_prefix_m11_qwen_notk_20260924, and the date suffix lives only in the field.
    """
    from scripts.analysis.campaign_index import index_configs

    cfgs = tmp_path / "configs"
    cfgs.mkdir()
    (cfgs / "whatever_name.yaml").write_text(
        "campaign_id: real_campaign_20260924\n"
        "handoff:\n"
        "  source_campaign: /scratch/x/results/src_campaign_20260923\n"
        "  m: 11\n"
        "policy_defaults:\n"
        "  lora_name: sft_b_plus\n",
        encoding="utf-8",
    )

    idx = index_configs(cfgs)

    assert "real_campaign_20260924" in idx
    assert idx["real_campaign_20260924"]["handoff_source_campaign"] == "src_campaign_20260923"
    assert idx["real_campaign_20260924"]["lora_name"] == "sft_b_plus"
    assert idx["real_campaign_20260924"]["handoff_m"] == 11


def test_config_provenance_is_kept_separate_from_the_run_record(tmp_path: Path) -> None:
    """A reader must be able to tell reconstructed provenance from recorded provenance."""
    reports = tmp_path / "reports"
    results = tmp_path / "results"
    cfgs = tmp_path / "configs"
    cfgs.mkdir()
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "a.json", {"arms_used": {"primary": {"m6": f"{root}/c"}}})
    write_episode(results, "c", "sys", 1, "t1", goal_pass_rate=0.5)
    (cfgs / "c.yaml").write_text(
        "campaign_id: c\npolicy_defaults:\n  lora_name: sft_b_plus\n", encoding="utf-8"
    )

    index = build_index(reports, results, cfgs)
    rec = index["campaigns"]["c"]

    assert rec["from_config"]["lora_name"] == "sft_b_plus"
    # The episode record itself carries no adapter, and the index must not pretend it does.
    assert "lora_name" not in rec


def test_lora_name_is_read_from_the_executor_block(tmp_path: Path) -> None:
    """It lives on `executor`, not `policy_defaults`.

    Reading only policy_defaults reported every tailored arm as untailored — a silent
    wrong answer of exactly the kind the adapter-alias comment in the config warns about.
    """
    from scripts.analysis.campaign_index import index_configs

    cfgs = tmp_path / "configs"
    cfgs.mkdir()
    (cfgs / "c.yaml").write_text(
        "campaign_id: c\nexecutor:\n  type: vllm\n  lora_name: sft_b_plus\n", encoding="utf-8"
    )

    assert index_configs(cfgs)["c"]["lora_name"] == "sft_b_plus"


def test_campaign_stem_strips_the_run_date() -> None:
    from scripts.analysis.campaign_index import campaign_stem

    assert campaign_stem("hj12_prefix_m11_20260923") == "hj12_prefix_m11"
    assert campaign_stem("hj12_prefix_m6_20260923rep") == "hj12_prefix_m6"
    assert campaign_stem("no_date_here") == "no_date_here"


def test_a_config_declaring_a_different_date_is_matched_and_flagged(tmp_path: Path) -> None:
    """The published dev prefix arms ran under ids their configs do not declare.

    Matching them silently would hide that re-running the config writes elsewhere;
    refusing to match them would drop the paper's primary arms from the index entirely.
    """
    from scripts.analysis.campaign_index import match_config

    config_index = {
        "hj12_prefix_m11_20260922": {
            "config_path": "configs/hj12_prefix_m11.yaml",
            "declared_campaign_id": "hj12_prefix_m11_20260922",
        }
    }

    got = match_config("hj12_prefix_m11_20260923", config_index)

    assert got["config_path"] == "configs/hj12_prefix_m11.yaml"
    assert got["config_match"] == "arm_stem"
    assert got["config_declares_a_different_campaign_id"] == "hj12_prefix_m11_20260922"


def test_an_exact_campaign_id_match_is_not_flagged_as_a_mismatch(tmp_path: Path) -> None:
    from scripts.analysis.campaign_index import match_config

    config_index = {"c_20260924": {"config_path": "configs/c.yaml", "declared_campaign_id": "c_20260924"}}

    got = match_config("c_20260924", config_index)

    assert got["config_match"] == "campaign_id"
    assert "config_declares_a_different_campaign_id" not in got


def test_an_ambiguous_stem_is_reported_rather_than_guessed(tmp_path: Path) -> None:
    from scripts.analysis.campaign_index import match_config

    config_index = {
        "c_20260922": {"config_path": "configs/a.yaml", "declared_campaign_id": "c_20260922"},
        "c_20260923": {"config_path": "configs/b.yaml", "declared_campaign_id": "c_20260923"},
    }

    got = match_config("c_20260924", config_index)

    assert got["config_match"] == "ambiguous"
    assert got["candidate_configs"] == ["configs/a.yaml", "configs/b.yaml"]


def test_index_surfaces_config_id_mismatches(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    results = tmp_path / "results"
    cfgs = tmp_path / "configs"
    cfgs.mkdir()
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "a.json", {"arms_used": {"primary": {"m11": f"{root}/arm_20260923"}}})
    write_episode(results, "arm_20260923", "sys", 1, "t1", goal_pass_rate=0.5)
    (cfgs / "arm.yaml").write_text("campaign_id: arm_20260922\n", encoding="utf-8")

    index = build_index(reports, results, cfgs)

    assert index["config_id_mismatches"] == ["arm_20260923"]
    assert "Config/campaign id mismatch" in to_markdown(index)


def test_a_malformed_config_does_not_abort_the_index(tmp_path: Path) -> None:
    from scripts.analysis.campaign_index import index_configs

    cfgs = tmp_path / "configs"
    cfgs.mkdir()
    (cfgs / "bad.yaml").write_text("campaign_id: [unclosed\n", encoding="utf-8")
    (cfgs / "good.yaml").write_text("campaign_id: fine\n", encoding="utf-8")

    idx = index_configs(cfgs)

    assert "fine" in idx


def test_markdown_lists_every_cited_campaign(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    results = tmp_path / "results"
    root = "/scratch/n12194778/sidekick/results"
    write_report(reports, "a.json", {"x": f"{root}/c_one", "y": f"{root}/c_two"})
    write_episode(results, "c_one", "sys", 1, "t1", goal_pass_rate=0.5)
    write_episode(results, "c_two", "sys", 1, "t1", goal_pass_rate=0.5)

    md = to_markdown(build_index(reports, results))

    assert "`c_one`" in md
    assert "`c_two`" in md
