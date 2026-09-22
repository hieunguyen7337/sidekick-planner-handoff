#!/usr/bin/env python
"""Generate the LP arm configs: hosted channel and prefix arms re-run against a LOCALLY SERVED planner.

Why a generator rather than twenty hand copies: the LP arms test whether the channel result holds
across planner strength, and they only test that if each one is its hosted source with the planner
swapped and NOTHING else moved. A hand copy that also drifted an executor or limit knob would
confound planner identity with serving and still produce believable numbers. So every file is
rendered from its source, and `--check` (and tests/unit/test_lp_configs.py) re-derives it and
compares the parsed YAML, field by field, against a declared set of changes -- exactly that set,
so a change that failed to happen is caught as surely as one that should not have.

    python scripts/setup/make_lp_configs.py           # (re)write the 20 files, then check them
    python scripts/setup/make_lp_configs.py --check   # exit 1 on drift or an undeclared difference

The planner settings are read from the LP ceiling configs, never restated here, so a live arm
cannot silently disagree with the ceiling whose plans it replays.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
RESULTS = "/scratch/n12194778/sidekick/results"
DATE = "20260923"

# LP tag -> the ceiling config every derived arm inherits its planner block and replay source from.
CEILINGS = {
    "lp1": "configs/lp1_planner_alone_cap81_qwen8b.yaml",
    "lp2": "configs/lp2_planner_alone_cap81_qwen38_27b.yaml",
}

# Source stem -> which published result it carries (written into the header). Each source was
# confirmed as the config behind its campaign by that campaign's manifest.json `config_path`.
LIVE_SOURCES = {
    "hj12_takeover_fixed_k_10": "the takeover side of the matched-trigger pair (ledger CHAN-C1-02)",
    "hj12_advise_fixed_k_10_fullctx": "the advice side of the matched-trigger pair (ledger CHAN-C1-02)",
    "hj13_advise_fixed_k_1_fullctx": "the H2 advice-at-price arm (ledger CHAN-PRICE-01)",
    "hj8_sft_plan_bplus": (
        "the plan-only sft_plan floor that CHAN-C1-02 and CHAN-PRICE-01 contrast against "
        "(campaign hj8_sft_plan_bplus_20260921iaware; ledger ADV-FC-02)"
    ),
}

# Derived suffix -> source stem. HJ-17, not HJ-18: the LP ceilings run seeds 1,2 and HJ-18
# replays the seed-3 sample only, so HJ-17 is the pooled cap-81 arm with the matching seeds.
PREFIX_SOURCES = {
    f"prefix_{rx}_m{m}": f"hj17_prefix_c81_{rx}_m{m}" for rx in ("zs", "bplus") for m in (6, 9, 11)
}
PREFIX_WHY = "the seeds-1,2 half of the pooled cap-81 prefix arm (ledger POOL-01)"

# Planner keys only CodexExecPlanner reads. Dropped, not carried: run provenance stamps
# planner.reasoning_effort into every manifest, and "medium" there would describe a knob the
# local planner does not have.
CODEX_ONLY_KEYS = ("binary", "reasoning_effort", "scratch_parent")

# Planner keys copied from the ceiling config, in the order they are written.
CEILING_PLANNER_KEYS = (
    "type",
    "model",
    "base_url",
    "temperature",
    "max_tokens",
    "timeout_s",
    "chat_template_kwargs",
)

# The exact set of flattened key paths a derived config may -- and must -- differ in.
# planner.timeout_s is absent on purpose: source and ceiling both say 300, so it does not move.
LIVE_DECLARED = frozenset(
    {
        "campaign_id",
        "planner.type",
        "planner.model",
        "planner.base_url",
        "planner.temperature",
        "planner.max_tokens",
        "planner.chat_template_kwargs.enable_thinking",
        "planner.reasoning_effort",
        "planner.scratch_parent",
        "planner.packet_source",
        "planner.packet_source_pending",
    }
)
PREFIX_DECLARED = LIVE_DECLARED | {"handoff.source_campaign"}

_MISSING = object()


@dataclass(frozen=True)
class Spec:
    lp: str  # "lp1" | "lp2"
    kind: str  # "live" | "prefix"
    source: str  # repo-relative source config
    out: str  # repo-relative derived config
    why: str

    @property
    def stem(self) -> str:
        return Path(self.out).stem

    @property
    def label(self) -> str:
        return self.lp.upper().replace("LP", "LP-")  # "lp1" -> "LP-1"

    @property
    def declared(self) -> frozenset[str]:
        return PREFIX_DECLARED if self.kind == "prefix" else LIVE_DECLARED


def all_specs() -> list[Spec]:
    specs: list[Spec] = []
    for lp in CEILINGS:
        for src, why in LIVE_SOURCES.items():
            specs.append(Spec(lp, "live", f"configs/{src}.yaml", f"configs/{lp}_{src}.yaml", why))
        for suffix, src in PREFIX_SOURCES.items():
            specs.append(Spec(lp, "prefix", f"configs/{src}.yaml", f"configs/{lp}_{suffix}.yaml", PREFIX_WHY))
    return specs


def load(rel: str) -> dict[str, Any]:
    data = yaml.safe_load((REPO / rel).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{rel} is not a mapping")
    return data


def ceiling(lp: str) -> tuple[dict[str, Any], str]:
    """(planner block, campaign_id) of the LP ceiling config."""
    cfg = load(CEILINGS[lp])
    planner = cfg.get("planner") or {}
    if planner.get("type") != "vllm" or not planner.get("model"):
        raise ValueError(f"{CEILINGS[lp]} is not a vllm-planner ceiling")
    return planner, str(cfg["campaign_id"])


def replay_source(lp: str) -> str:
    return f"{RESULTS}/{ceiling(lp)[1]}"


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            out.update(flatten(value, path + "."))
        else:
            out[path] = value
    return out


def _same(a: Any, b: Any) -> bool:
    # Type-aware: YAML `1` and `true` compare equal in Python, and a knob flipping between them
    # is exactly the kind of silent change this check exists to catch.
    return type(a) is type(b) and a == b


def changed_paths(src: dict[str, Any], derived: dict[str, Any]) -> frozenset[str]:
    fa, fb = flatten(src), flatten(derived)
    return frozenset(k for k in fa.keys() | fb.keys() if not _same(fa.get(k, _MISSING), fb.get(k, _MISSING)))


def _get(data: dict[str, Any], path: str) -> Any:
    return flatten(data).get(path, _MISSING)


def _fmt(value: Any) -> str:
    if value is _MISSING:
        return "(absent)"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and len(value) > 60 and "/" not in value:
        return f'"{value[:57]}..."'
    return str(value)


def derived_planner(spec: Spec) -> dict[str, Any]:
    src_planner = load(spec.source).get("planner") or {}
    ceil_planner, ceil_cid = ceiling(spec.lp)
    planner: dict[str, Any] = {k: ceil_planner[k] for k in CEILING_PLANNER_KEYS if k in ceil_planner}
    planner["packet_source"] = replay_source(spec.lp)
    planner["packet_source_pending"] = (
        f"produced by the {spec.label} ceiling run ({ceil_cid}), which may not have landed yet"
    )
    for key, value in src_planner.items():
        if key in planner or key in CODEX_ONLY_KEYS or key in ("packet_source", "packet_source_pending"):
            continue
        planner[key] = value  # packet_system, on_missing, and anything else the source set
    return planner


_PLANNER_COMMENTS = {
    "type": [
        "# The LOCALLY SERVED planner. Every generation setting below is copied from {ceiling},",
        "# so reviews and actions come from the same serving configuration as the plans they follow.",
        "# scripts/pbs/lp_live.pbs serves it on a per-job port and exports SIDEKICK_PLANNER_BASE_URL,",
        "# which overrides base_url (src/sidekick/runner.py::resolve_planner_base_url).",
    ],
    "type/prefix": [
        "# The LOCALLY SERVED planner whose trajectory is replayed, settings copied from {ceiling}.",
        "# Nothing in a prefix arm should call it live, and no planner server is started for one, so",
        "# a stray call fails loudly instead of reaching hosted quota.",
    ],
    "packet_source": [
        "# The first plan is replayed from the {lp} ceiling itself, never from a hosted sample: a",
        "# hosted plan followed by local reviews would put two planners in one episode.",
    ],
    "packet_source/prefix": [
        "# The plan is replayed from the same {lp} ceiling episode as the prefix above.",
    ],
    "packet_source_pending": [
        "# verify_configs.py exempts the source only while the path is absent; once the ceiling has",
        "# written it, it must resolve like any other.",
    ],
    "on_missing": [
        "# Load-bearing: a cache miss must abort, never fall through to a live plan.",
    ],
}


def _planner_block(spec: Spec, planner: dict[str, Any]) -> list[str]:
    lines = ["planner:"]
    fill = {"ceiling": CEILINGS[spec.lp], "lp": spec.label}
    for key, value in planner.items():
        comments = _PLANNER_COMMENTS.get(f"{key}/{spec.kind}", _PLANNER_COMMENTS.get(key, []))
        for comment in comments:
            lines.append("  " + comment.format(**fill))
        dumped = yaml.safe_dump({key: value}, default_flow_style=False, sort_keys=False, width=10**6)
        lines.extend("  " + row for row in dumped.rstrip("\n").splitlines())
    return lines


def _body(spec: Spec, planner: dict[str, Any]) -> str:
    """The source text with its header dropped and campaign_id / planner / replay source replaced.

    Text-level, so the source's comments on executor, limits and prices survive verbatim; the
    semantic check in `check` is what guarantees nothing else moved.
    """
    lines = (REPO / spec.source).read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines) and (not lines[i].strip() or lines[i].startswith("#")):
        i += 1
    lines = lines[i:]
    out: list[str] = []
    hits = {"campaign_id": 0, "planner": 0, "source_campaign": 0}
    top = ""
    j = 0
    while j < len(lines):
        line = lines[j]
        m = re.match(r"^([A-Za-z_][\w-]*):", line)
        if m:
            top = m.group(1)
        if line.startswith("campaign_id:"):
            out.append(f"campaign_id: {spec.stem}_{DATE}")
            hits["campaign_id"] += 1
            j += 1
            continue
        if line.startswith("planner:"):
            # Top-level comments directly above the block describe the hosted planner
            # ("luna's HJ-1 plan is replayed"); they would be false here.
            while out and out[-1].startswith("#"):
                out.pop()
            out.extend(_planner_block(spec, planner))
            hits["planner"] += 1
            j += 1
            while j < len(lines) and (not lines[j].strip() or lines[j][0].isspace()):
                j += 1
            continue
        if spec.kind == "prefix" and top == "handoff" and re.match(r"^\s+source_campaign:", line):
            indent = line[: len(line) - len(line.lstrip())]
            out.append(f"{indent}source_campaign: {replay_source(spec.lp)}")
            hits["source_campaign"] += 1
            j += 1
            continue
        out.append(line)
        j += 1
    want = {"campaign_id": 1, "planner": 1, "source_campaign": 1 if spec.kind == "prefix" else 0}
    if hits != want:
        raise ValueError(f"{spec.source}: expected replacements {want}, made {hits}")
    return "\n".join(out) + "\n"


def _header(spec: Spec, src: dict[str, Any], derived: dict[str, Any]) -> str:
    lp = spec.label
    model = derived["planner"]["model"]
    kind = "live arm" if spec.kind == "live" else "prefix-replay arm"
    rows = [
        f"#   {path}: {_fmt(_get(src, path))} -> {_fmt(_get(derived, path))}"
        for path in sorted(changed_paths(src, derived))
    ]
    old_source = Path(str((src.get("planner") or {}).get("packet_source") or "")).name
    head = [
        f"# {lp} {kind} -- GENERATED by scripts/setup/make_lp_configs.py. Edit the generator, not this",
        "# file: tests/unit/test_lp_configs.py fails on any hand edit.",
        "#",
        f"# Source: {spec.source}, {spec.why}.",
        f"# The hosted planner (gpt-5.6-luna via codex) is replaced by the LOCALLY SERVED planner {model}",
        f"# from {CEILINGS[spec.lp]}, to test whether the channel result holds across planner",
        "# strength (plan 2026-09-23, unit A3). That test needs the source with the planner swapped and",
        "# nothing else moved, so this file differs from its source ONLY in these fields -- exactly this",
        "# set, compared on the parsed YAML by make_lp_configs.py --check and the unit test:",
        *rows,
        "#",
        f"# planner.packet_source moves off the hosted sample ({old_source}) so that every planner",
        f"#   token in an episode comes from {model}.",
        "# planner.reasoning_effort / scratch_parent are codex-only; provenance would stamp them.",
    ]
    if spec.kind == "live":
        head += [
            "#",
            "# Run with scripts/pbs/lp_live.pbs, which serves this planner and the granite executor together.",
        ]
    else:
        rx = "zero-shot granite, executor.lora_name null" if "_zs_" in spec.out else "granite + sft_b_plus"
        m = (derived.get("handoff") or {}).get("m")
        head += [
            f"# handoff.source_campaign moves with it: the replayed prefix is the {lp} ceiling's trajectory.",
            f"# Receiver: {rx}. Depth: m={m}. Both are the source's, unchanged.",
            "#",
            "# The planner block moves although nothing here should call the planner live: provenance",
            "# stamps planner.type/model into every manifest, and the source's codex block would file",
            f"# these episodes under gpt-5.6-luna when the replayed trajectory is {model}'s. A stray live",
            "# call can then reach only a local server, never hosted quota; the prefix gate still fails it.",
            "# Replay-only: needs the executor server alone (scripts/pbs/hj12_prefix.pbs, once its",
            "# FREE_ARMS lists this stem).",
        ]
    return "\n".join(head) + "\n"


def render(spec: Spec) -> str:
    src = load(spec.source)
    planner = derived_planner(spec)
    body = _body(spec, planner)
    derived = yaml.safe_load(body)
    return _header(spec, src, derived) + body


def check(spec: Spec) -> list[str]:
    errors: list[str] = []
    path = REPO / spec.out
    if not path.is_file():
        return [f"{spec.out}: missing; run scripts/setup/make_lp_configs.py"]
    have = path.read_text(encoding="utf-8")
    if have != render(spec):
        errors.append(f"{spec.out}: differs from what the generator renders (hand edit, or a stale file)")
    got = changed_paths(load(spec.source), yaml.safe_load(have) or {})
    extra, absent = sorted(got - spec.declared), sorted(spec.declared - got)
    if extra or absent:
        errors.append(
            f"{spec.out}: vs {spec.source}, undeclared differences {extra}; declared but unchanged {absent}"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="make_lp_configs.py", description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = parser.parse_args(argv)
    specs = all_specs()
    if not args.check:
        for spec in specs:
            (REPO / spec.out).write_text(render(spec), encoding="utf-8")
            print(f"wrote {spec.out} <- {spec.source}")
    errors = [e for spec in specs for e in check(spec)]
    if errors:
        print("FAILURES:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"{len(specs)} LP configs OK: each differs from its source in exactly its declared fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
