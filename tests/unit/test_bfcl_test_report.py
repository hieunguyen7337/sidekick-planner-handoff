"""Tests for scripts/analysis/bfcl_test_report.py (the one registered BFCL test read, E-prereg 8802a95).

Every fixture is a synthetic campaign under tmp_path, laid out as a real BFCL test episode is
(<results>/bfcl_<stem>_test_20260925/<system>/<seed>/<entry>/{result.json, events.jsonl, manifest.json}), with a
synthetic split file, synthetic committed configs, derived test configs (S2) and refill logs (S3). The design is
small (10 entries x seeds {1, 2} = 20 pairs per arm) and every asserted number is computed by hand beside it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

import pytest
import yaml

from scripts.analysis import bfcl_test_report as btr

REPO = Path(__file__).resolve().parents[2]
N = 10  # entries in the synthetic design -> 20 pairs per arm
KW = dict(n_boot=200, seed=btr.SEED, pool_seeds=btr.POOL_SEEDS, big_n=400, big_seed=btr.BIG_SEED)

SYSTEMS = {"planner_alone_cap81": "planner_alone", "takeover_k5": "fixed_k", "advise_k5_fullctx": "fixed_k",
           "advise_k5_neutral": "fixed_k", "plan_zs": "prompt_only", "executor_alone_zs": "executor_alone",
           "executor_alone_bplus": "executor_alone", **{s: "prefix_handoff" for s in btr.PREFIX_ARMS}}
CODEX = set(btr.ARMS) - {"executor_alone_zs", "executor_alone_bplus"}
# Default goal_pass per arm: every contrast is a constant difference, so every interval is its point.
BASE = {"planner_alone_cap81": 0.5, "takeover_k5": 0.9, "advise_k5_fullctx": 0.5, "advise_k5_neutral": 0.6,
        "plan_zs": 0.4, "executor_alone_zs": 0.2, "executor_alone_bplus": 0.1,
        "prefix_zs_m2": 0.3, "prefix_zs_m4": 0.35, "prefix_zs_m6": 0.45,
        "prefix_bplus_m2": 0.2, "prefix_bplus_m4": 0.3, "prefix_bplus_m6": 0.4}
DEV_IDS = ["multi_turn_base_901", "multi_turn_base_902", "multi_turn_base_903"]


def cid(stem: str) -> str:
    return f"bfcl_{stem}_test_20260925"


def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def _ev(run_id: str, entry: str, system: str, seed: int, step: int, actor: str, etype: str,
        payload: Optional[dict] = None, usage: Optional[dict] = None, error: Optional[str] = None) -> dict:
    return {"run_id": run_id, "task_id": entry, "system": system, "seed": seed, "step": step,
            "ts": "2026-09-28T00:00:00+00:00", "actor": actor, "event_type": etype, "payload": payload or {},
            "usage": usage, "env_state_hash": "0" * 64, "error_type": error}


class Tree:
    """A synthetic registered-read input: results root, derived configs, refill logs, split file, repo."""

    def __init__(self, base: Path, n: int = N) -> None:
        self.base = base
        self.results = base / "results"
        self.configs = base / "logs" / "bfcl_test_configs"
        self.refills = base / "logs" / "bfcl_refills"
        self.repo = base / "repo"
        self.split = base / "split.json"
        self.out = base / "out" / "bfcl_test.report.json"
        self.ids = [f"multi_turn_base_{i}" for i in range(n)]
        self.n = n
        self.ceiling = self.results / btr.TEST_CEILING_CID

    # -- episodes --------------------------------------------------------------------------------
    def episode(self, stem: str, entry: str, seed: int, gp: Optional[float], *, success: Any = "auto",
                error_type: Optional[str] = None, plan: str = "auto", asks: int = 0, force_quit: bool = False,
                local_force_quit: bool = False, divergence: bool = False, live: bool = True,
                flag: Optional[bool] = True, record: bool = True, cached_from: Optional[str] = None,
                manifest: Optional[Callable[[dict], None]] = None, system: Optional[str] = None,
                source_campaign: Optional[str] = None, turn_valid: Optional[list] = None,
                divergence_shape: str = "broken") -> Path:
        system = system or SYSTEMS[stem]
        c = cid(stem)
        ep = self.results / c / system / str(seed) / entry
        ep.mkdir(parents=True, exist_ok=True)
        run_id = f"{c}/{system}/{seed}/{entry}"
        if success == "auto":
            success = gp == 1.0
        if divergence:
            error_type, gp, success = "crash", None, False
        codex = {"model": "gpt-5.6-luna", "provider": "codex", "input_tokens": 10, "output_tokens": 1, "n_calls": 1}
        ev = [_ev(run_id, entry, system, seed, 0, "system", "run_start", {"limits": {"max_steps": 40}}),
              _ev(run_id, entry, system, seed, 0, "environment", "observation", {"text": "hi", "done": False})]
        ledger = n_calls = 0
        last = 1
        if divergence:
            ev.append(_ev(run_id, entry, system, seed, 6, "system", "error",
                          {"reason": "replay_divergence", "detail": "hash mismatch"}, error="crash"))
        elif stem == btr.CEILING:
            if plan == "planless":
                ev.append(_ev(run_id, entry, system, seed, 0, "planner", "error", {"raw_output": "x"}, codex,
                              error="parse_error"))
                error_type = error_type or "parse_error"
            else:
                ev.append(_ev(run_id, entry, system, seed, 0, "planner", "plan", {"packet": {"goal": "g"}}, codex))
            ledger = n_calls = 12
            ev.append(_ev(run_id, entry, system, seed, 1, "planner", "action", {"kind": "CODE", "code": "ls()"},
                          codex))
        elif stem in btr.PACKET_REPLAY_ARMS:
            if plan in ("live", "both"):
                ev.append(_ev(run_id, entry, system, seed, 0, "planner", "plan", {"packet": {"goal": "g"}}, codex))
                ledger += 1
            if plan in ("auto", "both"):
                src = cached_from or str(self.ceiling / "planner_alone" / str(seed) / entry / "events.jsonl")
                ev.append(_ev(run_id, entry, system, seed, 0, "planner", "plan", {"packet": {"goal": "g"}},
                              {"model": "gpt-5.6-luna", "provider": "cache", "n_calls": 1,
                               "raw": {"cached_from": src}}))
                ledger += 1
            n_calls = ledger + 2
            ledger += 2
            ev.append(_ev(run_id, entry, system, seed, 1, "executor", "action", {"kind": "CODE", "code": "pwd()"}))
        elif stem in btr.PREFIX_ARMS:
            m = int(stem[-1])
            if record:
                ev.append(_ev(run_id, entry, system, seed, m, "system", "report",
                              {"effective_m": m, "n_source_actions": 8, "handoff_occurred": flag,
                               "source_campaign": source_campaign or str(self.ceiling)}))
            last = m
            if live:
                last = m + 1
                ev.append(_ev(run_id, entry, system, seed, last, "executor", "action",
                              {"kind": "CODE", "code": "pwd()"}))
            n_calls = m
        else:
            ev.append(_ev(run_id, entry, system, seed, 1, "executor", "action", {"kind": "CODE", "code": "pwd()"}))
        for _ in range(asks):
            ev.append(_ev(run_id, entry, system, seed, last, "planner", "intervention",
                          {"forced": False, "correction": "try ls()"}, codex))
            ledger += 1
        if local_force_quit:
            ev.append(_ev(run_id, entry, system, seed, last, "environment", "evaluate",
                          {"success": False, "goal_pass_rate": gp, "horizon": "local",
                           "report": {"force_quit": True}}))
        if not divergence:
            ev.append(_ev(run_id, entry, system, seed, last, "environment", "evaluate",
                          {"success": success, "goal_pass_rate": gp,
                           "report": {"force_quit": force_quit, "turn_valid": turn_valid or [True, False]}}))
        ev.append(_ev(run_id, entry, system, seed, last, "system", "run_end", {}, error=error_type))
        if divergence and divergence_shape == "broken":
            # What the runner really writes for a replay divergence: prefix_handoff._broken_result appends ONE system
            # error event and returns before run_episode (src/sidekick/systems/prefix_handoff.py:119-130, :173-174),
            # so there is no run_start (loop.py:703 is its only writer); a refill deletes any earlier attempt.
            m = int(stem[-1]) if stem in btr.PREFIX_ARMS else 0
            ev = [_ev(run_id, entry, system, seed, m, "system", "error",
                      {"reason": "replay_divergence", "detail": "hash mismatch", "effective_m": m,
                       "handoff_occurred": True, "hash_ok": False}, error="crash")]
        (ep / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
        result = {"error_type": error_type, "goal_pass_rate": gp, "n_asks": asks, "n_interventions": asks,
                  "n_planner_calls": n_calls, "run_id": run_id, "seed": seed, "sgc": None, "steps": 12,
                  "success": success, "system": system, "task_id": entry,
                  "tgc": None if success is None else (1.0 if success else 0.0),
                  "totals": {"executor_tokens_total": 1000, "planner_calls_total": ledger, "planner_tokens_total": 5,
                             "usd_total": 0.01}}
        if success is None:
            result.pop("success")
        (ep / "result.json").write_text(json.dumps(result), encoding="utf-8")
        prov = {"split": "test", "git_sha": "a" * 40, "git_branch": "main", "git_dirty": False,
                "config_path": str(self.configs / f"{c}.yaml"), "config_campaign_id": c,
                "handoff_source_campaign": str(self.ceiling) if stem in btr.REPLAYING_ARMS else None,
                "planner_type": "codex" if stem in CODEX else "mock",
                "planner_model_requested": "gpt-5.6-luna" if stem in CODEX else None,
                "planner_reasoning_effort": "medium" if stem in CODEX else None,
                "planner_cli_version": "codex-cli 0.153.4" if stem in CODEX else None}
        man = {"campaign_id": c, "run_id": run_id, "seed": seed, "task_id": entry, "system": system, "env": "bfcl",
               "provenance": prov}
        if manifest is not None:
            manifest(man)
        (ep / "manifest.json").write_text(json.dumps(man), encoding="utf-8")
        return ep

    # -- configs -----------------------------------------------------------------------------------
    def committed(self, stem: str) -> dict:
        dev_src = str(self.results / btr.DEV_CEILING_CID)
        cfg: dict[str, Any] = {"env": "bfcl", "campaign_id": f"bfcl_{stem}_dev_20260924"}
        if stem in CODEX:
            cfg["planner"] = {"type": "codex", "model": "gpt-5.6-luna", "reasoning_effort": "medium"}
        else:
            cfg["planner"] = {"type": "mock"}
        if stem in btr.PACKET_REPLAY_ARMS:
            cfg["planner"].update(packet_source=dev_src, packet_system="planner_alone", on_missing="call_if_planless",
                                  packet_source_pending="produced by BFCL arm planner_alone_cap81 (dev), not yet run")
        if stem in btr.PREFIX_ARMS:
            cfg["handoff"] = {"source_campaign": dev_src, "source_system": "planner_alone", "m": int(stem[-1])}
            cfg["planner"].update(packet_source=dev_src, packet_system="planner_alone", on_missing="fail")
        cfg["limits"] = {"max_steps": 40}
        return cfg

    def write_configs(self, derive: Optional[Callable[[str, dict], None]] = None) -> None:
        (self.repo / "configs").mkdir(parents=True, exist_ok=True)
        self.configs.mkdir(parents=True, exist_ok=True)
        for stem in btr.ARMS:
            data = yaml.safe_dump(self.committed(stem), sort_keys=False).encode()
            (self.repo / "configs" / f"bfcl_{stem}.yaml").write_bytes(data)
            self.write_derived(stem, data, derive)

    def write_derived(self, stem: str, committed: bytes, derive=None, text_patch=None) -> None:
        cfg = yaml.safe_load(committed)
        cfg["campaign_id"] = cid(stem)
        test_src = str(self.ceiling)
        for block in ("planner", "handoff"):
            for k, v in list((cfg.get(block) or {}).items()):
                if isinstance(v, str) and v.endswith(btr.DEV_CEILING_CID):
                    cfg[block][k] = test_src
        if derive is not None:
            derive(stem, cfg)
        text = (f"# derived from configs/bfcl_{stem}.yaml blob {blob_sha(committed)}\n# HEAD {'b' * 40}\n"
                f"# written 2026-09-28T00:00:00Z\n" + yaml.safe_dump(cfg, sort_keys=False))
        if text_patch is not None:
            text = text_patch(text)
        (self.configs / f"{cid(stem)}.yaml").write_text(text, encoding="utf-8")

    def refill(self, stem: str, keys: list[tuple[str, int]], reason: str = "replay_divergence") -> None:
        self.refills.mkdir(parents=True, exist_ok=True)
        path = self.refills / f"{cid(stem)}.tsv"
        lines = [] if path.exists() else ["\t".join(btr.REFILL_HEADER)]
        for entry, seed in keys:
            lines.append("\t".join([cid(stem), str(seed), entry, "crash", reason, "1.pbs", "t"]))
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    def write_split(self, test: Optional[list[str]] = None, dev: Optional[list[str]] = None) -> None:
        test = self.ids if test is None else test
        dev = DEV_IDS if dev is None else dev
        self.split.write_text(json.dumps({"category": "multi_turn_base", "seed": 20260924, "n_dev": len(dev),
                                          "n_test": len(test), "dev": dev, "test": test}), encoding="utf-8")

    def git(self, prereg_text: Optional[str] = None) -> None:
        (self.repo / "docs").mkdir(parents=True, exist_ok=True)
        text = prereg_text if prereg_text is not None else (REPO / btr.PREREG_REL).read_text(encoding="utf-8")
        (self.repo / btr.PREREG_REL).write_text(text, encoding="utf-8")
        for args in (["init", "-q"], ["add", "-A"],
                     ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init"]):
            subprocess.run(["git", *args], cwd=self.repo, check=True, timeout=60, capture_output=True)

    def classes(self) -> dict[str, list[str]]:
        return {e: (["GorillaFileSystem"] if i % 2 else ["GorillaFileSystem", "MathAPI"])
                for i, e in enumerate(self.ids)}

    def report(self, **kw) -> dict:
        args = dict(KW, n_test_entries=self.n, entry_classes=self.classes())
        args.update(kw)
        return btr.build_report(self.results, self.configs, self.refills, self.split, self.repo, **args)

    def argv(self, *extra: str, confirm: Optional[str] = btr.CONFIRM_TOKEN) -> list[str]:
        out = ["--results-root", str(self.results), "--config-dir", str(self.configs), "--refill-dir",
               str(self.refills), "--split-file", str(self.split), "--repo-root", str(self.repo), "--out",
               str(self.out)]
        if confirm is not None:
            out += ["--confirm", confirm]
        return out + list(extra)


def make_tree(base: Path, *, n: int = N, values: Optional[Callable[[str, int, int], Optional[dict]]] = None,
              planless: frozenset = frozenset(), skip: frozenset = frozenset(), git: bool = False,
              derive: Optional[Callable[[str, dict], None]] = None) -> Tree:
    """Every one of the 13 arms complete. values(stem, i, seed) -> episode kwargs overriding the default (gp from
    BASE); planless: (entry, seed) keys the ceiling wrote no plan for (the packet arms plan them live)."""
    t = Tree(base, n)
    t.write_split()
    for stem in btr.ARMS:
        for i, entry in enumerate(t.ids):
            for seed in btr.SEEDS:
                if (stem, entry, seed) in skip:
                    continue
                kw: dict[str, Any] = {"gp": BASE[stem]}
                if (entry, seed) in planless:
                    if stem == btr.CEILING:
                        kw.update(plan="planless", gp=0.0)
                    elif stem in btr.PACKET_REPLAY_ARMS:
                        kw.update(plan="live")
                if values is not None:
                    kw.update(values(stem, i, seed) or {})
                gp = kw.pop("gp")
                t.episode(stem, entry, seed, gp, **kw)
    t.write_configs(derive)
    t.refills.mkdir(parents=True, exist_ok=True)
    if git:
        t.git()
    return t


@pytest.fixture(scope="module")
def happy(tmp_path_factory) -> tuple[Tree, dict]:
    t = make_tree(tmp_path_factory.mktemp("happy"))
    return t, t.report()


@pytest.fixture
def small(monkeypatch):
    """main() fixes the registered constants; the synthetic design is 10 entries, so shrink them here."""
    monkeypatch.setattr(btr, "N_TEST_ENTRIES", N)
    monkeypatch.setattr(btr, "N_BOOT", 200)
    monkeypatch.setattr(btr, "BIG_N", 400)


# ---- the happy path ------------------------------------------------------------------------------------
def test_happy_read_values_by_hand(happy):
    t, rep = happy
    json.dumps(rep)  # serialisable without a default
    assert rep["meta"]["status"] == "read"
    assert rep["meta"]["cluster_unit"] == "entry" and rep["meta"]["n_clusters"] == N
    assert rep["meta"]["seed"] == 20260925 and rep["meta"]["pool_seeds"] == [20260925, 1, 2, 3, 7, 101, 999]
    p = rep["predictions"]
    # P6 = 0.9 - 0.5 = +40.00 pp on every pair; the interval is its point, p two-sided at 0 = 0.
    assert p["P6"]["goal_pass"]["diff_pp"] == 40.0 and p["P6"]["goal_pass"]["ci95_entry"] == [40.0, 40.0]
    assert p["P6"]["verdict"] == "supported" and p["P6"]["goal_pass"]["p_registered"] == 0.0
    # P3 = 0.45 - 0.5 = -5.00 > -7.00: non-inferior; CF1 = 0.6 - 0.5 = +10.00.
    assert p["P3"]["goal_pass"]["diff_pp"] == -5.0 and p["P3"]["verdict"] == "supported"
    assert p["CF1"]["goal_pass"]["diff_pp"] == 10.0 and p["CF1"]["verdict"] == "supported"
    # D1 = 0.4 - 0.2 = +20; D2 = 0.45 - 0.3 = +15; D3, D4 the same with h* = 1 on all 20 pairs.
    assert [p[d]["goal_pass"]["diff_pp"] for d in ("D1", "D2", "D3", "D4")] == [20.0, 15.0, 20.0, 15.0]
    assert p["D3"]["goal_pass"]["n_handoff"] == 20 and p["D3"]["h_arm"] == "prefix_bplus_m6"
    assert all(p[d]["verdict"] == "supported" for d in ("D1", "D2", "D3", "D4"))
    for pid in btr.PRED_ORDER:
        assert p[pid]["n_pairs"] == 20 and p[pid]["n_divergent_excluded"] == 0 and p[pid]["divergent_excluded"] == []
        assert p[pid]["goal_pass"]["n_clusters"] == N
        assert "exploratory" not in p[pid] and "exploratory" not in p[pid]["goal_pass"]
        assert set(p[pid]["limit_rates"]) == {p[pid]["left"], p[pid]["right"]}
        assert set(p[pid]["ask_bounds_pp"]) == {p[pid]["left"], p[pid]["right"]}
    assert rep["families"]["D"]["m"] == 4 and rep["families"]["H"]["m"] == 1 and rep["families"]["N"]["m"] == 1
    assert rep["b1"]["B1_zs"]["reading"] == "holds" and rep["b1"]["B1_zs"]["goal_pass"]["diff_pp"] == -5.0
    assert rep["b1"]["B1_bplus"]["reading"] == "fails" and rep["b1"]["B1_bplus"]["goal_pass"]["diff_pp"] == -10.0
    s = rep["supporting"]
    assert s["S3"]["goal_pass"]["diff_pp"] == -10.0 and s["S3"]["reading_at_minus_7"] == "fails"
    assert s["S4"]["goal_pass"]["diff_pp"] == -10.0 and s["S5"]["goal_pass"]["diff_pp"] == 20.0
    assert s["CF3"]["reading"] == "executing the action adds to advice written under a neutral prompt"
    m4 = rep["m4_rows"]
    assert m4["m4_bplus_m4_minus_m2"]["exploratory"] is True
    assert m4["m4_zs_m4_minus_m2"]["all_pairs"]["goal_pass"]["diff_pp"] == 5.0
    assert m4["m4_zs_m6_minus_m4"]["hstar_from_left"]["goal_pass"]["diff_pp"] == 10.0
    assert rep["by_fdr"]["m"] == 13 and rep["by_fdr"]["not_in_family"] == []
    assert rep["planless_keys"]["n"] == 0 and rep["planless_keys"]["keys"] == []
    assert rep["sensitivity"]["key_exclusion"]["n_keys"] == 0
    assert rep["sensitivity"]["involved_classes"]["n_class_sets_design"] == 2
    assert rep["arms"]["prefix_zs_m6"]["hstar"]["n_hstar"] == 20


def test_happy_cost_conventions(happy):
    _t, rep = happy
    # takeover_k5 fixture: ledger = 1 (cached plan) + 2 = 3, cached planner events charged 1 -> live 2; attributed 3.
    c = rep["cost"]["takeover_k5"]
    assert c["calls_live_mean"] == 2.0 and c["calls_attributed_mean"] == 3.0 and c["calls_live_total"] == 40.0
    assert rep["cost"]["planner_alone_cap81"]["calls_live_mean"] == 12.0
    assert rep["guards"]["G9"]["takeover_k5"]["n_cached_plan_keys"] == 20
    assert rep["guards"]["G9"]["takeover_k5"]["sum_cached_plus_live"] == 20
    assert rep["guards"]["G6"]["planner_alone_cap81"]["n_config_sha256_unstamped"] == 20


def test_happy_sentences(happy):
    _t, rep = happy
    s = rep["sentences"]
    assert 'actions beat the registered correction-prompt advice' in s["P6"]
    assert "CF1 (advise_k5_neutral − advise_k5_fullctx), in the same paragraph: supported" in s["P6"]
    assert 'reported only as "actions beat correction-prompt advice"' in s["P6"]
    assert "non-inferiority to the medium-effort planner in this harness" in s["P3"]
    assert "B1 zs (handoff-only companion, h* from prefix_zs_m6): holds" in s["P3"]
    assert btr.BPLUS_DESC in s["D1"] and btr.BPLUS_DESC in s["D3"] and btr.BPLUS_DESC in s["B1_bplus"]
    assert "on BFCL, a later handoff raises the out-of-domain adapter's quality" in s["D1"]
    assert "0 divergent replay keys excluded" in s["D2"]
    assert all("tailored to BFCL" not in v for v in s.values())
    assert "never pooled" in s["pooling"]
    assert rep["predictions"]["P6"]["sentence"] == s["P6"]


# ---- G1-G3 through main() -------------------------------------------------------------------------------
def _refused(t: Tree, argv: list[str], guard: str, capsys) -> str:
    rc = btr.main(argv)
    err = capsys.readouterr().err
    assert rc == 2, err
    assert f"REFUSED ({guard})" in err, err
    assert not t.out.exists() and not btr.md_path(t.out).exists()
    return err


STATUS_FROZEN = "**Status**: **FROZEN** on commit, 2026-09-28."


@pytest.mark.parametrize("status,why", [
    ("**Status**: DRAFT, becomes FROZEN on commit.", "not FROZEN"),
    ("**Status**: **FROZEN** on commit; was DRAFT.", "DRAFT"),
    (STATUS_FROZEN + "\n\n**Status**: FROZEN again", "exactly one"),
])
def test_g1_status_line(tmp_path, capsys, small, status, why):
    t = make_tree(tmp_path)
    t.git(prereg_text=f"# E-prereg\n\n{status}\n\nbody\n")
    assert why in _refused(t, t.argv(), "G1", capsys)


def test_g1_modified_and_untracked(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    prereg = t.repo / btr.PREREG_REL
    prereg.write_text(prereg.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    assert "differs from HEAD" in _refused(t, t.argv(), "G1", capsys)
    subprocess.run(["git", "rm", "-q", "--cached", btr.PREREG_REL], cwd=t.repo, check=True, timeout=60)
    assert "not tracked" in _refused(t, t.argv(), "G1", capsys)


@pytest.mark.parametrize("confirm", [None, "A1_FROZEN", ""])
def test_g2_confirm(tmp_path, capsys, small, confirm):
    t = make_tree(tmp_path, git=True)
    _refused(t, t.argv(confirm=confirm), "G2", capsys)


def test_g3_out_under_results_root(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    argv = t.argv()
    argv[argv.index("--out") + 1] = str(t.results / "x.report.json")
    rc = btr.main(argv)
    assert rc == 2 and "REFUSED (G3)" in capsys.readouterr().err
    assert not (t.results / "x.report.json").exists()


def test_g3_one_read_and_disclosed_rerun(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    assert btr.main(t.argv()) == 0
    first = json.loads(t.out.read_text(encoding="utf-8"))
    first_sha = hashlib.sha256(t.out.read_bytes()).hexdigest()
    capsys.readouterr()
    rc = btr.main(t.argv())
    assert rc == 2 and "one read only" in capsys.readouterr().err
    assert hashlib.sha256(t.out.read_bytes()).hexdigest() == first_sha  # nothing rewritten
    assert btr.main(t.argv("--disclosed-rerun", "fixed a label")) == 0
    second = json.loads(t.out.read_text(encoding="utf-8"))
    dr_ = second["meta"]["disclosed_rerun"]
    assert dr_["reason"] == "fixed a label" and dr_["prior_sha256"] == first_sha
    assert dr_["prior_predictions"] == first["predictions"]


# ---- G4-G9 through main() --------------------------------------------------------------------------------
def _mutate_and_refuse(tmp_path, capsys, guard: str, mutate: Callable[[Tree], None], **tree_kw) -> str:
    t = make_tree(tmp_path, git=True, **tree_kw)
    mutate(t)
    return _refused(t, t.argv(), guard, capsys)


@pytest.mark.parametrize("name,guard,mutate,why", [
    ("split_short", "G4", lambda t: t.write_split(test=t.ids[:-1]), "distinct ids"),
    ("split_overlap", "G4", lambda t: t.write_split(dev=[t.ids[0]]), "overlap"),
    ("extra_key", "G5", lambda t: t.episode("takeover_k5", "multi_turn_base_77", 1, 0.5), "not a test id"),
    ("extra_seed", "G5", lambda t: t.episode("takeover_k5", t.ids[0], 3, 0.5), "seed 3"),
    ("duplicate", "G5", lambda t: t.episode("takeover_k5", t.ids[0], 1, 0.5, system="other"), "second result"),
    ("no_manifest", "G6", lambda t: (t.results / cid("plan_zs") / "prompt_only" / "1" / t.ids[0]
                                     / "manifest.json").unlink(), "no readable manifest"),
    ("split_dev", "G6", lambda t: t.episode("executor_alone_zs", t.ids[0], 1, 0.2,
                                            manifest=lambda m: m["provenance"].update(split="dev")),
     "provenance.split 'dev'"),
    ("cli", "G6", lambda t: t.episode("takeover_k5", t.ids[0], 1, 0.9, manifest=lambda m: m["provenance"].update(
        planner_cli_version="codex-cli 0.153.5")), "0.153.5"),
    ("model", "G6", lambda t: t.episode("planner_alone_cap81", t.ids[0], 1, 0.5, manifest=lambda m: m[
        "provenance"].update(planner_model_requested="gpt-5.6")), "planner_model_requested"),
    ("effort", "G6", lambda t: t.episode("takeover_k5", t.ids[0], 1, 0.9, manifest=lambda m: m[
        "provenance"].update(planner_reasoning_effort="high")), "planner_reasoning_effort"),
    ("config_path", "G6", lambda t: t.episode("executor_alone_zs", t.ids[0], 1, 0.2, manifest=lambda m: m[
        "provenance"].update(config_path="/somewhere/else.yaml")), "config_path"),
    ("unstamped_git", "G6", lambda t: t.episode("executor_alone_zs", t.ids[0], 1, 0.2, manifest=lambda m: m[
        "provenance"].update(git_sha=None)), "git_sha unstamped"),
    ("source", "G6", lambda t: t.episode("prefix_zs_m2", t.ids[0], 1, 0.3, manifest=lambda m: m[
        "provenance"].update(handoff_source_campaign="/x/bfcl_planner_alone_cap81_dev_20260924")),
     "handoff_source_campaign"),
    ("cfg_absent", "G7", lambda t: (t.configs / f"{cid('plan_zs')}.yaml").unlink(), "derived test config absent"),
    ("cfg_dev_id", "G7", lambda t: t.write_derived(
        "executor_alone_zs", (t.repo / "configs" / "bfcl_executor_alone_zs.yaml").read_bytes(),
        text_patch=lambda s: s + "# note: bfcl_x_dev_20260924\n"), "_dev_20260924"),
    ("cfg_extra_key", "G7", lambda t: t.write_derived(
        "takeover_k5", (t.repo / "configs" / "bfcl_takeover_k5.yaml").read_bytes(),
        derive=lambda s, c: c["limits"].update(max_steps=41)), "limits.max_steps"),
    ("cfg_on_missing", "G7", lambda t: t.write_derived(
        "advise_k5_fullctx", (t.repo / "configs" / "bfcl_advise_k5_fullctx.yaml").read_bytes(),
        derive=lambda s, c: c["planner"].update(on_missing="fail")), "on_missing"),
    ("cfg_source", "G7", lambda t: t.write_derived(
        "prefix_zs_m6", (t.repo / "configs" / "bfcl_prefix_zs_m6.yaml").read_bytes(),
        derive=lambda s, c: c["handoff"].update(source_campaign="/x/bfcl_planner_alone_cap81_test_20260925")),
     "handoff.source_campaign"),
    ("cfg_blob", "G7", lambda t: t.write_derived(
        "executor_alone_bplus", b"env: bfcl\ncampaign_id: other\nplanner:\n  type: mock\nlimits:\n  max_steps: 40\n"),
     "blob sha"),
    ("cfg_live_keys", "G7", lambda t: t.write_derived(
        "prefix_bplus_m2", (t.repo / "configs" / "bfcl_prefix_bplus_m2.yaml").read_bytes(),
        derive=lambda s, c: c["planner"].update(live_plan_keys=["1/multi_turn_base_0"])), "not planless"),
    ("gp_none", "G8", lambda t: t.episode("executor_alone_zs", t.ids[3], 2, None, success=False),
     "goal_pass_rate None"),
    ("live_plan", "G9", lambda t: t.episode("advise_k5_neutral", t.ids[2], 1, 0.6, plan="live"),
     "not planless"),
    ("no_plan", "G9", lambda t: t.episode("plan_zs", t.ids[2], 2, 0.4, plan="none"), "no plan event"),
    ("cached_outside", "G9", lambda t: t.episode("plan_zs", t.ids[2], 2, 0.4, cached_from="/elsewhere/e.jsonl"),
     "outside the test ceiling"),
    ("prefix_record_source", "G7", lambda t: t.episode("prefix_bplus_m6", t.ids[1], 1, 0.4,
                                                       source_campaign="/x/bfcl_planner_alone_cap81_dev_20260924"),
     "source_campaign"),
])
def test_data_guards_refuse(tmp_path, capsys, small, name, guard, mutate, why):
    err = _mutate_and_refuse(tmp_path, capsys, guard, mutate)
    assert why in err, err


def test_g5_smoke_and_other_campaigns_are_never_read(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    for junk in (f"{cid('takeover_k5')}_smoke_123", "bfcl_takeover_k5_qzs_test_20260925",
                 "bfcl_takeover_k5_dev_20260924", f"{cid('takeover_k5')}_dryrun"):
        d = t.results / junk / "fixed_k" / "3" / "not_a_test_id"
        d.mkdir(parents=True)
        (d / "result.json").write_text("{not json", encoding="utf-8")
    assert btr.main(t.argv()) == 0
    rep = json.loads(t.out.read_text(encoding="utf-8"))
    assert rep["meta"]["campaigns"]["takeover_k5"] == cid("takeover_k5")
    assert rep["predictions"]["P6"]["verdict"] == "supported"


# ---- G8 and the success companion -------------------------------------------------------------------------
def test_none_success_is_counted_not_refused(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"success": None} if (s, i, seed) == ("takeover_k5", 0, 1)
                  else None)
    rep = t.report()
    assert rep["arms"]["takeover_k5"]["n_success_missing"] == 1
    assert rep["predictions"]["P6"]["success"]["n_success_missing_dropped"] == 1
    assert rep["predictions"]["P6"]["success"]["n_pairs"] == 19
    assert rep["predictions"]["P6"]["goal_pass"]["n_pairs"] == 20


# ---- abort rules -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("stem", ["planner_alone_cap81", "takeover_k5", "advise_k5_fullctx"])
def test_abort_not_run(tmp_path, stem):
    t = make_tree(tmp_path, skip=frozenset({(stem, "multi_turn_base_4", 2)}))
    rep = t.report()
    assert rep["meta"]["status"] == "not_run" and rep["predictions"] is None
    assert rep["not_run"]["arms_below_300"] == [stem]
    assert rep["arms"][stem]["n_missing"] == 1 and rep["arms"][stem]["n_noncrash"] == 19
    dumped = json.dumps(rep)
    assert "p_registered" not in dumped and "p_two_sided" not in dumped and "diff_pp" not in dumped
    assert set(rep["arms"][stem]) >= {"n_noncrash", "n_crash", "n_divergent", "n_missing"}


def test_abort_neutral_incomplete_drops_cf1_cf3_only(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"error_type": "crash", "gp": None}
                  if (s, i, seed) == ("advise_k5_neutral", 3, 1) else None)
    rep = t.report()
    p = rep["predictions"]
    assert p["CF1"]["verdict"] == "not_run" and p["CF1"]["goal_pass"] is None
    assert rep["supporting"]["CF3"]["status"] == "not_run"
    assert rep["sensitivity"]["limit_split"]["CF1"]["status"] == "not_run"
    assert p["P6"]["verdict"] == "supported" and p["P3"]["verdict"] == "supported"
    assert rep["by_fdr"]["m"] == 11 and rep["by_fdr"]["not_in_family"] == ["CF1", "CF3"]
    assert "not run" in rep["sentences"]["CF1"] and "P6 and P3 stand" in rep["sentences"]["CF1"]


def test_abort_prefix_incomplete_d_member_unread_p1_m4(tmp_path):
    t = make_tree(tmp_path, skip=frozenset({("prefix_bplus_m2", "multi_turn_base_0", 1)}))
    rep = t.report()
    p, d = rep["predictions"], rep["families"]["D"]
    assert p["D1"]["verdict"] == "not_read" and p["D3"]["verdict"] == "not_read"
    assert d["m"] == 4 and d["p_raw_substituted_as_1"] == ["D1", "D3"]
    assert d["p_raw"]["D1"] == 1.0 and d["p_raw"]["D3"] == 1.0
    # D2 and D4 have p 0: Holm over (1, 0, 1, 0) leaves them at 0 -> supported.
    assert d["p_holm"]["D2"] == 0.0 and p["D2"]["verdict"] == "supported"
    assert "its p counts as 1 in Holm, which stays at m = 4" in rep["sentences"]["D1"]
    assert rep["supporting"]["S3"]["status"] == "read"  # S3 uses bplus_m6 and the ceiling only


# ---- divergent keys (S6, L9-L11) --------------------------------------------------------------------------
def _div_tree(tmp_path, stem: str, keys: list[tuple[int, int]], refill: bool = True, **kw) -> Tree:
    div = {(i, s) for i, s in keys}
    t = make_tree(tmp_path, values=lambda s, i, seed: {"divergence": True} if s == stem and (i, seed) in div
                  else None, **kw)
    if refill:
        t.refill(stem, [(t.ids[i], s) for i, s in keys])
    return t


KEYS15 = [(i, s) for i in range(10) for s in (1, 2)][:15]
KEYS16 = [(i, s) for i in range(10) for s in (1, 2)][:16]


def test_divergent_15_is_complete(tmp_path):
    rep = _div_tree(tmp_path, "prefix_zs_m6", KEYS15).report()
    arm = rep["arms"]["prefix_zs_m6"]
    assert arm["complete"] and arm["n_divergent"] == 15 and arm["n_crash"] == 15
    p3 = rep["predictions"]["P3"]
    assert p3["verdict"] == "supported" and p3["n_pairs"] == 5 and p3["n_divergent_excluded"] == 15
    assert len(p3["divergent_excluded"]) == 15 and "15 divergent replay keys excluded" in rep["sentences"]["P3"]
    assert rep["divergent_keys"]["per_arm"]["prefix_zs_m6"]["n"] == 15
    assert rep["divergent_keys"]["per_arm"]["prefix_zs_m2"]["n"] == 0


def test_divergent_16_makes_every_row_of_the_arm_incomplete(tmp_path):
    rep = _div_tree(tmp_path, "prefix_zs_m6", KEYS16).report()
    p = rep["predictions"]
    for pid in ("P3", "D2", "D4"):
        assert p[pid]["verdict"] == "not_read" and "over cap: 16" in p[pid]["reason"]
        assert p[pid]["n_divergent_excluded"] == 16
    for rid in ("B1_zs", "B1_zs_flag"):
        assert rep["b1"][rid]["status"] == "not_read" and rep["b1"][rid]["reading"] is None
    assert rep["d_flags"]["D4_flag"]["status"] == "not_read"
    assert rep["m4_rows"]["m4_zs_m6_minus_m4"]["all_pairs"]["status"] == "not_read"
    assert set(rep["by_fdr"]["not_in_family"]) == {"P3", "B1_zs", "D2", "D4"} and rep["by_fdr"]["m"] == 9
    assert rep["families"]["D"]["p_raw"]["D2"] == 1.0
    # the other rows stand
    assert p["P6"]["verdict"] == "supported" and p["D1"]["verdict"] == "supported"


def test_divergent_reason_without_refill_is_an_ordinary_crash(tmp_path):
    rep = _div_tree(tmp_path, "prefix_bplus_m4", [(2, 1)], refill=False).report()
    arm = rep["arms"]["prefix_bplus_m4"]
    assert arm["n_divergent"] == 0 and arm["n_divergent_reason_not_refilled"] == 1 and not arm["complete"]
    assert rep["m4_rows"]["m4_bplus_m4_minus_m2"]["all_pairs"]["status"] == "not_read"


def test_divergent_union_exclusion_for_d(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"divergence": True}
                  if (s, i, seed) in {("prefix_bplus_m6", 0, 1), ("prefix_bplus_m6", 1, 1),
                                      ("prefix_bplus_m2", 2, 1), ("prefix_bplus_m2", 3, 2),
                                      ("prefix_bplus_m2", 4, 2)} else None)
    t.refill("prefix_bplus_m6", [(t.ids[0], 1), (t.ids[1], 1)])
    t.refill("prefix_bplus_m2", [(t.ids[2], 1), (t.ids[3], 2), (t.ids[4], 2)])
    rep = t.report()
    d1 = rep["predictions"]["D1"]
    assert d1["n_divergent_excluded"] == 5 and d1["n_pairs"] == 15 and d1["verdict"] == "supported"
    assert rep["b1"]["B1_bplus"]["n_divergent_excluded"] == 2  # only bplus_m6's keys: the ceiling has none


def test_divergent_key_in_the_runners_real_broken_path_shape_is_counted(tmp_path):
    """The broken-replay log is one system error event with no run_start (the fixture's default divergence shape).
    replay_divergence.divergent_keys reads it as empty; the read counts it (hc.last_attempt semantics)."""
    t = _div_tree(tmp_path, "prefix_zs_m6", [(0, 1)], refill=False)
    t.refill("prefix_zs_m6", [(t.ids[0], 1)], reason="")  # the wrapper's reason column uses that blind helper
    events = (t.results / cid("prefix_zs_m6") / "prefix_handoff" / "1" / t.ids[0] / "events.jsonl").read_text()
    assert len(events.splitlines()) == 1 and "run_start" not in events
    assert btr.rd.divergent_keys(t.results / cid("prefix_zs_m6")) == []
    rep = t.report()
    arm = rep["arms"]["prefix_zs_m6"]
    assert arm["complete"] and arm["n_divergent"] == 1 and arm["divergent_keys"] == ["1/multi_turn_base_0"]
    assert arm["n_divergent_reason_without_run_start"] == 1 and arm["n_divergent_reason_not_refilled"] == 0
    p = rep["predictions"]
    # P3 = -5 pp on the 19 remaining pairs; D2 and D4 exclude the same key.
    assert p["P3"]["verdict"] == "supported" and p["P3"]["n_pairs"] == 19 and p["P3"]["n_divergent_excluded"] == 1
    assert p["D2"]["n_divergent_excluded"] == 1 and p["D4"]["divergent_excluded"] == ["1/multi_turn_base_0"]
    assert rep["divergent_keys"]["per_arm"]["prefix_zs_m6"]["n_divergent_reason_without_run_start"] == 1


def test_divergent_key_after_a_run_start_is_counted_too(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"divergence": True, "divergence_shape": "with_run_start"}
                  if (s, i, seed) == ("prefix_bplus_m6", 3, 2) else None)
    t.refill("prefix_bplus_m6", [(t.ids[3], 2)])
    arm = t.report()["arms"]["prefix_bplus_m6"]
    assert arm["complete"] and arm["n_divergent"] == 1 and arm["n_divergent_reason_without_run_start"] == 0


def test_refilled_crash_without_a_divergence_event_stays_ordinary(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"error_type": "crash", "gp": None}
                  if (s, i, seed) == ("prefix_zs_m4", 1, 1) else None)
    t.refill("prefix_zs_m4", [(t.ids[1], 1)], reason="")
    rep = t.report()
    arm = rep["arms"]["prefix_zs_m4"]
    assert arm["n_divergent"] == 0 and arm["n_divergent_reason_not_refilled"] == 0 and not arm["complete"]
    assert rep["m4_rows"]["m4_zs_m4_minus_m2"]["all_pairs"]["status"] == "not_read"


# ---- boundary rule, Holm-aware (L1) -----------------------------------------------------------------------
D1_MEANS = sorted([-0.01] * 15 + [0.005] * 20 + [0.05] * 965)  # lo = means[25] = 0.005; p_greater = 2*15/1000
FLAT = [0.2] * 1000
D2_SEED7 = sorted([-0.1] * 250 + [0.2] * 750)  # p_greater = 0.5 at seed 7 only


def test_boundary_holm_crossing_puts_d1_on_the_boundary(tmp_path, monkeypatch):
    t = make_tree(tmp_path)
    orig = btr._member_means

    def fake(row_id, kind, diffs, hs, labels, *, n_boot, seed):
        if row_id == "D1":
            return list(D1_MEANS)
        if row_id == "D2":
            return list(D2_SEED7) if seed == 7 else list(FLAT)
        if row_id in ("D3", "D4"):
            return list(FLAT)
        return orig(row_id, kind, diffs, hs, labels, n_boot=n_boot, seed=seed)

    monkeypatch.setattr(btr, "_member_means", fake)
    rep = t.report()
    d1 = rep["predictions"]["D1"]
    # Base: p = (0.03, 0, 0, 0) -> D1's Holm p = 1 x 0.03 = 0.03 -> supported. Seed 7: p = (0.03, 0.5, 0, 0) ->
    # D1 ranks third, Holm p = 2 x 0.03 = 0.06 > 0.05 -> not supported, while D1's own interval never moves.
    assert d1["holm"]["p_adjusted"] == pytest.approx(0.03)
    assert d1["verdict_before_boundary"] == "supported" and d1["verdict"] == "on_boundary"
    b = d1["boundary"]
    assert b["fired"] and b["within_window"] == {"lo": True, "hi": False} and b["flipping_seeds"] == [7]
    assert {row["lo_pp"] for row in b["bounds_by_seed"]} == {0.5}
    seven = next(row for row in b["bounds_by_seed"] if row["seed"] == 7)
    assert seven["p_holm"] == pytest.approx(0.06) and seven["verdict"] == "not_supported"
    assert b["bound_200k"]["decision_bearing"] is False and b["bound_200k"]["n_boot"] == 400
    assert rep["predictions"]["D2"]["verdict"] == "supported"  # its own bounds are 20 pp from 0: not fired
    assert "on the boundary" in rep["sentences"]["D1"]
    # D2 was re-decided with the family: at seed 7 its interval is [-10, +20] pp -> not supported. E:213-215 does not
    # fire for it (bounds 20 pp from 0), so the verdict stands, and the flip is disclosed, not voted.
    b2 = rep["predictions"]["D2"]["boundary"]
    assert b2["fired"] is False and b2["stable"] is True and b2["family_fired_by"] == ["D1"]
    assert b2["flipping_seeds_not_voted"] == [7]
    assert "differs at seed(s) [7]" in rep["sentences"]["D2"] and "disclosed, not voted" in rep["sentences"]["D2"]
    assert rep["predictions"]["D3"]["boundary"]["flipping_seeds_not_voted"] == []


# ---- reversals ------------------------------------------------------------------------------------------
def test_p6_and_cf1_reversed(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"gp": 0.3} if s in ("takeover_k5", "advise_k5_neutral")
                  else None)
    rep = t.report()
    p = rep["predictions"]
    assert p["P6"]["verdict"] == "reversed" and p["P6"]["goal_pass"]["diff_pp"] == -20.0
    assert p["CF1"]["verdict"] == "reversed"
    assert "reversed: a primary finding" in rep["sentences"]["P6"]
    assert "reversed: a primary finding (E:127)" in rep["sentences"]["CF1"]


def test_d_reversal_with_unadjusted_less_p_and_p3_never_reversed(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"gp": 0.2} if s == "prefix_zs_m6" else None)
    rep = t.report()
    d2, p3 = rep["predictions"]["D2"], rep["predictions"]["P3"]
    # D2 = 0.2 - 0.3 = -10 pp everywhere: upper bound < 0, p_less = 2 x share >= 0 = 0, Holm p (greater) = 1.
    assert d2["verdict"] == "reversed" and d2["reversal"]["upper_below_0"] is True
    assert d2["reversal"]["p_less"] == 0.0 and d2["reversal"]["p_less_adjusted"] is False
    assert d2["holm"]["p_adjusted"] == 1.0
    assert "direction 'less' p at 0, 2 × share ≥ 0, = 0.0000, unadjusted" in rep["sentences"]["D2"]
    # D2's p label is bootstrap_pvalue's 2 x share <= 0 (E:158-159), never "one-sided"
    assert "p = 2 × share ≤ 0 ('greater')" in rep["sentences"]["D2"] and "one-sided" not in rep["sentences"]["D2"]
    # P3 = 0.2 - 0.5 = -30 pp: not supported, never reversed.
    assert p3["verdict"] == "not_supported" and "reversal" not in p3
    assert "fails non-inferiority; P6 and CF1 do not depend on P3" in rep["sentences"]["P3"]


# ---- h* from the left arm ---------------------------------------------------------------------------------
def test_d4_takes_hstar_from_the_left_arm(tmp_path):
    def values(s, i, seed):
        if s == "prefix_zs_m6":
            return {"gp": 0.9, "live": False} if i < 5 else {"gp": 0.45}
        if s == "prefix_zs_m2" and i >= 5:
            return {"live": False}
        return None

    rep = make_tree(tmp_path, values=values).report()
    d4, d2 = rep["predictions"]["D4"]["goal_pass"], rep["predictions"]["D2"]["goal_pass"]
    # h* = 1 on m6 only for entries 5-9 (10 pairs, d = 0.45 - 0.3 = +15); the m6 h* = 0 pairs (d = +60) do not count.
    assert d4["diff_pp"] == 15.0 and d4["n_handoff"] == 10 and d4["n_h_missing"] == 0
    # D2 over all 20 pairs: (10 x 0.6 + 10 x 0.15) / 20 = 0.375.
    assert d2["diff_pp"] == 37.5
    assert rep["arms"]["prefix_zs_m6"]["hstar"]["n_hstar"] == 10
    assert rep["arms"]["prefix_zs_m6"]["hstar"]["n_terminal"] == 10


# ---- clusters ---------------------------------------------------------------------------------------------
def test_split_must_hold_the_registered_entry_count(tmp_path):
    t = make_tree(tmp_path)
    with pytest.raises(btr.GuardError) as exc:  # G4: a 10-id split is refused against the registered 150
        t.report(n_test_entries=150)
    assert exc.value.guard == "G4"


def test_estimate_asserts_one_cluster_per_design_entry_on_a_full_view():
    """E:201-202: a full view (nothing removed) with fewer entry clusters than the design is an AssertionError."""
    ctx = {"n_boot": 50, "seed": btr.SEED, "classes": None}
    keys = [(f"multi_turn_base_{i}", s) for i in range(9) for s in btr.SEEDS]
    view = {"keys": keys, "diffs": [0.1] * len(keys), "field": "goal_pass", "n_removed": 0,
            "n_design_entries": 10, "variant": "primary"}
    with pytest.raises(AssertionError, match="9 entry clusters on a full view; the design has 10"):
        btr.estimate(ctx, "P6", view)
    view["n_removed"] = 2  # two pairs removed (e.g. divergent keys): fewer clusters are then legitimate
    assert btr.estimate(ctx, "P6", view)["n_clusters"] == 9


def test_main_exits_1_when_a_full_view_loses_an_entry_cluster(tmp_path, capsys, small, monkeypatch):
    t = make_tree(tmp_path, git=True)
    orig = btr.pair_view

    def lossy(ctx, left, right, field="goal_pass", **kw):  # drops entry 0 without counting it as removed
        v = orig(ctx, left, right, field, **kw)
        idx = [i for i, k in enumerate(v["keys"]) if k[0] != t.ids[0]]
        for name in ("keys", "diffs", "left_values", "right_values", "left_error", "right_error", "left_hflag"):
            v[name] = [v[name][i] for i in idx]
        if v.get("left_hstar") is not None:
            v["left_hstar"] = [v["left_hstar"][i] for i in idx]
        v["n_pairs"] = len(idx)
        return v

    monkeypatch.setattr(btr, "pair_view", lossy)
    assert btr.main(t.argv()) == 1
    assert "entry clusters on a full view" in capsys.readouterr().err
    assert not t.out.exists() and not btr.md_path(t.out).exists()


def test_no_scenario_clustering_and_signflip_clusters_are_entries(tmp_path, monkeypatch):
    t = make_tree(tmp_path)

    def boom(*a, **k):
        raise AssertionError("scenario clustering used on BFCL ids")

    from scripts.analysis import j10_report
    from scripts.setup import hj1_gate
    monkeypatch.setattr(j10_report, "scenario_of", boom)
    monkeypatch.setattr(hj1_gate, "scenario_of", boom)
    monkeypatch.setattr(j10_report, "_cluster_labels", boom)
    rep = t.report()
    assert rep["meta"]["n_clusters"] == N
    assert all(rep["predictions"][p]["goal_pass"]["n_clusters"] == N for p in btr.PRED_ORDER)
    for p in ("P6", "P3", "CF1", "D1", "D2"):  # the non-ratio rows: the sign-flip runs on N entry clusters
        assert rep["predictions"][p]["sign_flip"]["status"] == "ok" and rep["predictions"][p]["sign_flip"][
            "n_clusters"] == N, p
    assert btr.N_TEST_ENTRIES == 150 and btr.SEEDS == (1, 2)


# ---- asks, force-quit, planless -----------------------------------------------------------------------------
def test_ask_bound_reaches_the_p6_sentence(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"asks": 2} if (s, i, seed) == ("takeover_k5", 1, 1) else None)
    rep = t.report()
    asks = rep["executor_asks"]["per_arm"]["takeover_k5"]
    # one episode with an answered ask in 20 -> 100 x 1 / 20 = 5.00 pp; two calls.
    assert asks["n_episodes_with_answered_ask"] == 1 and asks["n_answered_ask_calls"] == 2 and asks["bound_pp"] == 5.0
    assert rep["executor_asks"]["per_contrast"]["P6"]["bound_reaches_1pp"] is True
    assert "live-answered executor asks bound the arm means at takeover_k5 5.00 pp" in rep["sentences"]["P6"]
    assert rep["executor_asks"]["per_arm"]["executor_alone_zs"]["bound_pp"] == 0.0


def test_force_quit_count_from_the_final_evaluate_report(tmp_path):
    def values(s, i, seed):
        if s == "executor_alone_zs" and i in (0, 1) and seed == 1:
            return {"force_quit": True}
        if s == "executor_alone_zs" and i == 2 and seed == 1:
            return {"local_force_quit": True}  # an in-loop horizon='local' evaluate: not counted
        return None

    rep = make_tree(tmp_path, values=values).report()
    arm = rep["arms"]["executor_alone_zs"]
    assert arm["force_quit_count"] == 2 and arm["limit_rate"] == 0.0 and arm["n_force_quit_unrecorded"] == 0


def test_planless_keys_live_planned_and_key_exclusion(tmp_path):
    pl = frozenset({("multi_turn_base_0", 1)})
    rep = make_tree(tmp_path, planless=pl).report()
    assert rep["planless_keys"]["n"] == 1 and rep["planless_keys"]["keys"] == ["1/multi_turn_base_0"]
    g9 = rep["guards"]["G9"]["takeover_k5"]
    assert g9["n_live_plan_keys"] == 1 and g9["n_cached_plan_keys"] == 19 and g9["sum_cached_plus_live"] == 20
    kx = rep["sensitivity"]["key_exclusion"]
    assert kx["status"] == "ok" and kx["rows"]["P6"]["n_pairs_without_keys"] == 19
    # P3: the planless ceiling episode scored 0, so its pair is 0.45 - 0 = +45; without it every pair is -5.
    assert kx["rows"]["P3"]["goal_pass_without_keys"]["diff_pp"] == -5.0
    assert not any(r["differs"] for r in kx["rows"].values())


def test_planless_over_cap_reads_no_replaying_arm(tmp_path):
    pl = frozenset((f"multi_turn_base_{i}", s) for i in range(8) for s in (1, 2))  # 16 > 15
    rep = make_tree(tmp_path, planless=pl).report()
    assert rep["planless_keys"]["over_cap"] is True
    assert all(rep["predictions"][p]["verdict"] == "not_run" for p in btr.PRED_ORDER)
    assert rep["supporting"]["S4"]["status"] == "read" and rep["supporting"]["S5"]["status"] == "not_run"


# ---- sensitivities ----------------------------------------------------------------------------------------
def test_limit_split_parts_sum_and_p3_limit_excluded(tmp_path):
    def values(s, i, seed):
        if s == "advise_k5_fullctx" and i in (0, 1):
            return {"gp": 0.1, "error_type": "limit"}
        if s == "planner_alone_cap81" and i == 2 and seed == 2:
            return {"gp": 0.0, "error_type": "limit"}
        return None

    rep = make_tree(tmp_path, values=values).report()
    ls = rep["sensitivity"]["limit_split"]["P6"]
    assert ls["post_treatment"] and ls["n_limit_pairs"] == 4 and ls["n_neither"] == 16
    # d = 0.8 on the 4 limit pairs, 0.4 on the 16 others: contributions 0.8 x 4/20 = 16 and 0.4 x 16/20 = 32 pp.
    assert ls["contribution_limit_pairs"]["point_pp"] == 16.0 and ls["contribution_neither"]["point_pp"] == 32.0
    assert ls["all"]["point_pp"] == 48.0 == rep["predictions"]["P6"]["goal_pass"]["diff_pp"]
    l0 = rep["sensitivity"]["limit_as_0"]["P6"]["goal_pass"]
    # limit episodes set to 0: d = 0.9 on 4 pairs and 0.4 on 16 -> (3.6 + 6.4) / 20 = 0.5.
    assert l0["diff_pp"] == 50.0
    p3x = rep["sensitivity"]["p3_limit_excluded"]
    assert p3x["n_dropped"] == 1 and p3x["n_kept"] == 19 and p3x["ceiling_mean_dropped"] == 0.0
    assert p3x["goal_pass"]["diff_pp"] == -5.0 and p3x["reading_at_minus_7"] == "holds"
    assert "selects on the ceiling's own failures" in p3x["caveat"]
    assert rep["arms"]["advise_k5_fullctx"]["limit_rate"] == 0.2  # 4 of 20
    assert rep["predictions"]["P6"]["limit_rates"] == {"takeover_k5": 0.0, "advise_k5_fullctx": 0.2}


def test_involved_classes_sensitivity_counts_clusters_as_found(happy):
    _t, rep = happy
    ic = rep["sensitivity"]["involved_classes"]
    assert ic["status"] == "ok" and ic["rows"]["P6"]["n_clusters"] == 2 and ic["rows"]["P6"]["cluster_unit"] == "class_set"
    assert rep["exploratory"]["per_turn"]["arms"]["takeover_k5"]["turns"]["0"] == {"n_checked": 20, "n_passed": 20,
                                                                                   "share": 1.0}
    assert rep["exploratory"]["per_class_set"]["status"] == "ok"
    assert rep["exploratory"]["channel_content"]["status"] == "ok"


# ---- sentences, pure --------------------------------------------------------------------------------------
def _row(pid: str, verdict: str, **kw) -> dict:
    spec = btr.PRED_SPECS[pid]
    row = {"left": spec["left"], "right": spec["right"], "verdict": verdict, "status": "read",
           "goal_pass": {"status": "ok", "diff_pp": 3.0, "ci95_entry": [1.0, 5.0], "p_registered": 0.01},
           "holm": {"m": 1, "p_adjusted": 0.01}, "n_divergent_excluded": 0, "sign_flip": None}
    row.update(kw)
    return row


def _report(**preds) -> dict:
    base = {pid: _row(pid, "supported") for pid in btr.PRED_ORDER}
    base.update(preds)
    return {"predictions": base, "b1": {"B1_zs": {"reading": "fails", "left": "prefix_zs_m6",
                                                  "right": "planner_alone_cap81",
                                                  "goal_pass": {"diff_pp": -8.0, "ci95_entry": [-12.0, -4.0],
                                                                "n_handoff": 250, "n_h_missing": 0}}},
            "supporting": {}, "by_fdr": {"flags": []}}


@pytest.mark.parametrize("verdict,text", [
    ("supported", "J10's H-A1b replicates on BFCL"),
    ("not_supported", "fails to replicate; TGC and CF1 do not rescue it"),
    ("reversed", "a primary finding"),
    ("on_boundary", "on the boundary"),
])
def test_p6_sentences(verdict, text):
    s = btr.build_sentences(_report(P6=_row("P6", verdict), CF1=_row("CF1", "not_supported")))["P6"]
    assert text in s and 'actions beat the registered correction-prompt advice' in s
    assert "CF1 (advise_k5_neutral − advise_k5_fullctx), in the same paragraph: not supported" in s
    assert 'reported only as "actions beat correction-prompt advice"' not in s


@pytest.mark.parametrize("verdict,text", [
    ("supported", "non-inferior at −7.00 pp to the planner acting alone"),
    ("not_supported", "fails non-inferiority; P6 and CF1 do not depend on P3"),
    ("on_boundary", "on the boundary"),
])
def test_p3_sentences(verdict, text):
    s = btr.build_sentences(_report(P3=_row("P3", verdict)))["P3"]
    assert text in s and "non-inferiority to the medium-effort planner in this harness" in s
    assert "B1 zs (handoff-only companion, h* from prefix_zs_m6): fails, -8.00 pp" in s
    assert "never changes P3" in s


@pytest.mark.parametrize("verdict,text", [
    ("supported", 'P6 is reported only as "actions beat correction-prompt advice"'),
    ("not_supported", "the prompt effect does not replicate; P6 carries §8's qualification"),
    ("reversed", "a primary finding"),
    ("on_boundary", "on the boundary"),
])
def test_cf1_sentences(verdict, text):
    s = btr.build_sentences(_report(CF1=_row("CF1", verdict)))["CF1"]
    assert text in s


@pytest.mark.parametrize("d_all,d_h,text", [
    ("supported", "supported", "on BFCL, a later handoff raises the out-of-domain adapter's quality, and not only "
                               "through episodes the planner finishes itself"),
    ("supported", "not_supported", "the depth gain is not shown on real handoffs"),
    ("not_supported", "supported", "the dev depth span does not replicate on BFCL test for this receiver"),
])
def test_d_readings(d_all, d_h, text):
    s = btr.build_sentences(_report(D1=_row("D1", d_all), D3=_row("D3", d_h)))
    assert text in s["D1"] and text in s["D3"]
    assert btr.BPLUS_DESC in s["D1"]
    z = btr.build_sentences(_report(D2=_row("D2", d_all), D4=_row("D4", d_h)))
    assert "zero-shot receiver" in z["D2"] and btr.BPLUS_DESC not in z["D2"]


def test_d_member_outcomes():
    s = btr.build_sentences(_report(
        D1=_row("D1", "not_supported"), D2=_row("D2", "reversed", reversal={"p_less": 0.004}),
        D3=_row("D3", "on_boundary", boundary={"fired": True, "stable": False, "flipping_seeds": [7],
                                                "seeds": list(btr.POOL_SEEDS), "n_boot": 10000}),
        D4=_row("D4", "not_read", status="not_read", reason="prefix_zs_m6 incomplete")))
    assert "not replicated, never evidence of no effect" in s["D1"]
    assert "reversed: a primary finding" in s["D2"] and "0.0040, unadjusted" in s["D2"]
    assert "on the boundary: the Holm-aware verdict differs at seed(s) [7]" in s["D3"]
    assert "its p counts as 1 in Holm, which stays at m = 4" in s["D4"]


def test_sentence_carries_signflip_by_and_asks():
    rep = _report(P6=_row("P6", "supported", ask_bound_reaches_1pp=True,
                          ask_bounds_pp={"takeover_k5": 1.33, "advise_k5_fullctx": 0.0},
                          sign_flip={"status": "ok", "p_value": 0.2, "method": "monte_carlo",
                                     "alternative": "two-sided"}),
                  P3=_row("P3", "supported", sign_flip={"status": "import_error", "error": "boom"}))
    rep["by_fdr"] = {"flags": [{"id": "P6", "survives_by": False, "sentence": "P6 supported; does NOT survive "
                                                                             "Benjamini-Yekutieli"}]}
    s = btr.build_sentences(rep)
    assert "disagrees with the bootstrap verdict" in s["P6"]
    assert "does NOT survive Benjamini-Yekutieli" in s["P6"]
    assert "takeover_k5 1.33 pp" in s["P6"]
    assert "sign-flip p is unavailable (import_error" in s["P3"]


# ---- dev_reference (L6) -----------------------------------------------------------------------------------
def _dig(data: dict, dotted: str) -> Any:
    for part in dotted.split("."):
        data = data[part]
    return data


def test_dev_reference_equals_committed_dev_report_and_prereg():
    dev = json.loads((REPO / btr.DEV_REPORT_REL).read_text(encoding="utf-8"))
    prereg = (REPO / btr.PREREG_REL).read_text(encoding="utf-8")
    ref = btr.dev_reference()["rows"]
    for rid, row in ref.items():
        got = _dig(dev, row["dev_report_key"])
        assert got["diff_pp"] == row["diff_pp"], rid
        assert got["ci95_entry"] == pytest.approx(row["ci95_entry"]), rid
        for k in ("sd_pp", "p_two_sided", "p_ni", "n_handoff", "lower_above_margin"):
            if k in row:
                assert got[k] == row[k], (rid, k)
        if rid in btr.DEV_REFERENCE:  # quoted in the frozen prereg, registered orientation, never negated
            def fmt(x: float) -> str:
                return f"{x:+.2f}".replace("-", "−") if x < 0 else f"{x:.2f}"
            text = f"{fmt(row['diff_pp']) if row['diff_pp'] < 0 else '+' + fmt(row['diff_pp'])}"
            assert text in prereg, (rid, text)
            assert f"[{fmt(row['ci95_entry'][0])}, {fmt(row['ci95_entry'][1])}]" in prereg, rid
        else:
            assert row["label"] == "dev report value; not quoted in the prereg"
    assert btr.DEV_META["n_pairs"] == 150 and btr.DEV_META["n_clusters"] == 50


# ---- main(): the full run -----------------------------------------------------------------------------------
def test_main_full_run_shape(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    assert btr.main(t.argv()) == 0
    rep = json.loads(t.out.read_text(encoding="utf-8"))
    assert btr.md_path(t.out).is_file()
    for key in ("meta", "guards", "arms", "planless_keys", "divergent_keys", "predictions", "families", "b1",
                "d_flags", "m4_rows", "supporting", "sensitivity", "by_fdr", "executor_asks", "hstar_counts", "cost",
                "exploratory", "dev_reference", "sentences"):
        assert key in rep, key
    meta = rep["meta"]
    assert meta["status"] == "read" and meta["confirm"] == "E_FROZEN" and meta["disclosed_rerun"] is None
    assert meta["prereg_stamp"]["commit"] and meta["prereg_stamp"]["sha256"]
    assert meta["split_file"]["sha256"] and meta["script"]["sha256"]
    assert meta["n_boot"] == 200 and meta["seed"] == 20260925 and meta["big_n"] == 400
    assert meta["codex_pin"]["cli_version_last_token"] == "0.153.4"
    assert set(rep["predictions"]) == set(btr.PRED_ORDER)
    assert rep["predictions"]["P6"]["sign_flip"]["status"] == "ok"
    assert rep["predictions"]["D3"]["sign_flip"]["status"] == "not_applicable"


def test_main_not_run_writes_tallies(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True, skip=frozenset({("takeover_k5", "multi_turn_base_0", 1)}))
    # 'cannot complete' is a final judgement: without the acknowledgement nothing is written (E:303-304, E:305)
    err = _refused(t, t.argv(), "G5", capsys)
    assert "abort arms below 300 pairs" in err and "takeover_k5" in err
    assert btr.main(t.argv("--cannot-complete", "takeover_k5")) == 0
    rep = json.loads(t.out.read_text(encoding="utf-8"))
    assert rep["meta"]["status"] == "not_run" and rep["predictions"] is None
    assert rep["meta"]["cannot_complete_acknowledged"] == ["takeover_k5"]
    assert "not run" in btr.md_path(t.out).read_text(encoding="utf-8")


# ---- R fixes: G3 ledger, G5 acknowledgement, G7 all 13 arms, G6 disclosure ------------------------------------
def test_g3_a_second_read_to_another_out_path_is_refused(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    assert btr.main(t.argv()) == 0
    first_sha = hashlib.sha256(t.out.read_bytes()).hexdigest()
    ledger = t.repo / btr.READ_LEDGER_REL
    rows = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["report_sha256"] == first_sha and rows[0]["status"] == "read"
    capsys.readouterr()
    other = tmp_path / "elsewhere" / "second.report.json"
    argv = t.argv()
    argv[argv.index("--out") + 1] = str(other)
    rc = btr.main(argv)
    err = capsys.readouterr().err
    assert rc == 2 and "one read only" in err and "1 prior read(s)" in err and not other.exists()
    assert btr.main(argv + ["--disclosed-rerun", "moved the report"]) == 0
    second = json.loads(other.read_text(encoding="utf-8"))
    dr_ = second["meta"]["disclosed_rerun"]
    assert dr_["prior_report"] == os.path.realpath(t.out) and dr_["prior_sha256"] == first_sha
    assert len(dr_["prior_reads"]) == 1 and len(ledger.read_text(encoding="utf-8").splitlines()) == 2


def test_g5_cannot_complete_must_name_exactly_the_incomplete_arms(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True, values=lambda s, i, seed: {"error_type": "crash", "gp": None}
                  if (s, i, seed) == ("prefix_bplus_m4", 3, 1) else None)
    err = _refused(t, t.argv(), "G5", capsys)
    assert "prefix_bplus_m4" in err and "final judgement" in err
    _refused(t, t.argv("--cannot-complete", "prefix_bplus_m4,prefix_zs_m4"), "G5", capsys)
    _refused(t, t.argv("--cannot-complete", "prefix_bplus_m9"), "G5", capsys)
    assert btr.main(t.argv("--cannot-complete", "prefix_bplus_m4")) == 0
    rep = json.loads(t.out.read_text(encoding="utf-8"))
    assert rep["meta"]["status"] == "read" and rep["meta"]["cannot_complete_acknowledged"] == ["prefix_bplus_m4"]
    assert rep["m4_rows"]["m4_bplus_m4_minus_m2"]["all_pairs"]["status"] == "not_read"
    assert rep["predictions"]["D1"]["verdict"] == "supported"


def test_g5_a_complete_read_refuses_a_spurious_acknowledgement(tmp_path, capsys, small):
    t = make_tree(tmp_path, git=True)
    err = _refused(t, t.argv("--cannot-complete", "plan_zs"), "G5", capsys)
    assert "<none>" in err


def test_g7_an_absent_arm_refuses_a_read_but_not_a_not_run_report(tmp_path, capsys, small):
    import shutil
    t = make_tree(tmp_path, git=True)
    shutil.rmtree(t.results / cid("prefix_bplus_m4"))
    (t.configs / f"{cid('prefix_bplus_m4')}.yaml").unlink()
    err = _refused(t, t.argv(), "G7", capsys)
    assert "campaign directory absent for ['prefix_bplus_m4']" in err and "all 13" in err
    _refused(t, t.argv("--cannot-complete", "prefix_bplus_m4"), "G7", capsys)  # an ack never excuses an absent arm
    shutil.rmtree(t.results / cid("takeover_k5"))  # the not-run path: an abort arm below 300 (here: never started)
    assert btr.main(t.argv("--cannot-complete", "takeover_k5")) == 0
    rep = json.loads(t.out.read_text(encoding="utf-8"))
    assert rep["meta"]["status"] == "not_run" and rep["not_run"]["arms_below_300"] == ["takeover_k5"]
    assert rep["guards"]["G7"]["prefix_bplus_m4"]["status"].startswith("not_checked")


def test_g6_config_sha256_absence_is_disclosed(happy):
    _t, rep = happy
    g6 = rep["guards"]["G6"]["planner_alone_cap81"]
    assert g6["config_sha256_check"].startswith("not possible on 20 of 20 manifests")
    assert "S2 tripwire" in g6["config_identity"]
    assert g6["n_distinct_git_sha"] == 1 and g6["n_git_dirty_true"] == 0


# ---- R fixes: sentences and row frames ---------------------------------------------------------------------
@pytest.mark.parametrize("d_h,text", [
    ("on_boundary", "D3 is on the boundary, neither supported nor not supported (E:213-215): no joint reading"),
    ("not_read", "D3 is not read: no joint reading from the E:169-174 table"),
    ("reversed", "D3 is reversed, a primary finding (E:176-179); the E:169-174 table registers no joint reading"),
])
def test_d_reading_only_for_the_registered_outcomes(d_h, text):
    kw = {"status": "not_read", "reason": "prefix_bplus_m6 incomplete"} if d_h == "not_read" else {}
    s = btr.build_sentences(_report(D1=_row("D1", "supported"), D3=_row("D3", d_h, **kw)))
    assert text in s["D1"] and text in s["D3"]
    assert "the depth gain is not shown on real handoffs" not in s["D1"]


def test_not_replicated_is_printed_once_per_sentence():
    s = btr.build_sentences(_report(D1=_row("D1", "not_supported"), D3=_row("D3", "not_supported")))
    for rid in ("D1", "D3"):
        assert s[rid].count("not replicated, never evidence of no effect") == 1, s[rid]


def test_d1_and_d2_carry_their_hstar_companion_numbers(happy):
    _t, rep = happy
    s = rep["sentences"]
    assert ("printed with its h* companion D3 (handoff-only Σd·h*/Σh*, h* from prefix_bplus_m6): supported, "
            "+20.00 pp [+20.00, +20.00] over 20 handoff pairs (n_h_missing 0, counted as 0) (E:334)") in s["D1"]
    assert ("printed with its h* companion D4 (handoff-only Σd·h*/Σh*, h* from prefix_zs_m6): supported, "
            "+15.00 pp [+15.00, +15.00]") in s["D2"]
    assert "printed with its h* companion" not in s["D3"]


def test_p6_wording_never_asserts_the_claim():
    for v in ("not_supported", "reversed"):
        s = btr.build_sentences(_report(P6=_row("P6", v), CF1=_row("CF1", "not_supported")))["P6"]
        assert "P6 is the prediction that actions beat the registered correction-prompt advice" in s
        assert "P6 is described as" not in s
    s = btr.build_sentences(_report(P6=_row("P6", "reversed")))["P6"]
    assert "the registered correction-prompt advice beats actions on BFCL test" in s


def test_cf3_and_s_rows_carry_ask_bounds_but_not_the_forbidden_phrase(tmp_path):
    t = make_tree(tmp_path, values=lambda s, i, seed: {"asks": 1}
                  if s in ("advise_k5_neutral", "plan_zs") and seed == 1 and i < 3 else None)
    rep = t.report()
    # 3 of 20 episodes with an answered ask -> 15.00 pp
    assert rep["supporting"]["CF3"]["ask_bounds_pp"]["advise_k5_neutral"] == 15.0
    s = rep["sentences"]["CF3"]
    assert "advise_k5_neutral 15.00 pp" in s and "0 divergent replay keys excluded" in s
    assert "execution adds nothing" not in s
    assert "execution adds nothing" in rep["supporting"]["CF3"]["reading_rule"]
    md = btr.render_markdown(rep)
    s5 = next(x for x in md.splitlines() if x.startswith("- S5 ("))
    assert "plan_zs 15.00 pp" in s5


def test_d_signflip_is_set_against_the_unadjusted_bootstrap_p():
    sf = {"status": "ok", "p_value": 0.001, "method": "monte_carlo", "alternative": "greater"}

    def gp(p):
        return {"status": "ok", "diff_pp": 3.0, "ci95_entry": [1.0, 5.0], "p_registered": p}

    # fails only on Holm (unadjusted p 0.02): both unadjusted tests reject, so no disagreement is printed
    s = btr.build_sentences(_report(D1=_row("D1", "not_supported", sign_flip=sf, goal_pass=gp(0.02))))["D1"]
    assert "sign-flip" not in s
    s = btr.build_sentences(_report(D1=_row("D1", "not_supported", sign_flip=sf, goal_pass=gp(0.2))))["D1"]
    assert "disagrees with the unadjusted bootstrap p (0.2000" in s


def test_p3_qualifier_wherever_its_verdict_is_printed(happy):
    _t, rep = happy
    q = "non-inferiority to the medium-effort planner in this harness"
    assert q in rep["predictions"]["P3"]["reading_qualifier"] and q in rep["sentences"]["P3"]
    assert q in next(r for r in rep["by_fdr"]["rows"] if r["id"] == "P3")["reading_qualifier"]
    assert q in next(f for f in rep["by_fdr"]["flags"] if f["id"] == "P3")["sentence"]
    assert q in rep["sensitivity"]["key_exclusion"]["rows"]["P3"]["reading_qualifier"]
    assert q in rep["sensitivity"]["p3_limit_excluded"]["reading_qualifier"]


def test_sensitivity_rows_carry_the_divergent_frame(tmp_path):
    rep = _div_tree(tmp_path, "prefix_zs_m6", KEYS15).report()
    sens = rep["sensitivity"]
    p3x = sens["p3_limit_excluded"]
    assert p3x["n_divergent_excluded"] == 15 and len(p3x["divergent_excluded"]) == 15 and p3x["n_pairs"] == 5
    assert sens["key_exclusion"]["rows"]["P3"]["n_divergent_excluded"] == 15
    assert sens["key_exclusion"]["rows"]["P6"]["n_divergent_excluded"] == 0
    ic = sens["involved_classes"]["rows"]
    assert ic["P3"]["n_divergent_excluded"] == 15 and ic["D2"]["divergent_excluded"] == p3x["divergent_excluded"]
    assert ic["P6"]["n_divergent_excluded"] == 0 and ic["P6"]["divergent_excluded"] == []
