#!/usr/bin/env bash
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
REPO="/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15"
cd "$REPO"
PY="/scratch/n12194778/sidekick/env/bin/python"
export PYTHONPATH="${REPO}/src:${REPO}${PYTHONPATH:+:${PYTHONPATH}}"
RESULTS="/scratch/n12194778/sidekick/results"
OUT="${REPO}/campaign/results/hj8_frontier_iaware_20260921.report.json"

"$PY" "${REPO}/scripts/analysis/j8_frontier.py" \
  --arm oracle_escalation_iaware="${RESULTS}/hj8_oracle_escalation_20260921iaware" \
  --arm sft_plan_iaware="${RESULTS}/hj8_sft_plan_bplus_20260921iaware" \
  --arm sft_plan_base="${RESULTS}/hj8_sft_plan_bplus_20260919" \
  --arm fixed_k_10_iaware="${RESULTS}/hj8_fixed_k_10_20260921iaware" \
  --arm fixed_k_10_base="${RESULTS}/hj8_fixed_k_10_20260920" \
  --arm fixed_k_3_iaware="${RESULTS}/hj8_fixed_k_3_20260921iaware" \
  --arm fixed_k_3_base="${RESULTS}/hj8_fixed_k_3_20260920" \
  --arm oracle_escalation_base="${RESULTS}/hj8_oracle_escalation_20260920" \
  --out "$OUT"
rc=$?
echo "[E5] j8_frontier.py exit=$rc out=$OUT"

echo "==== E5 EXTRACT ===="
"$PY" - "$OUT" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
report = json.loads(path.read_text(encoding="utf-8"))
print("headline:", report.get("headline"))
print("headline_refused:", report.get("headline_refused"))
print("refusals:", report.get("refusals"))
print("arm_order:", list(report.get("arms", {})))
fields = (
    "n",
    "n_broken",
    "n_crashed",
    "n_survivors",
    "goal_pass_all",
    "goal_pass_survivors",
    "tgc_all",
    "tgc_survivors",
    "planner_calls_per_episode",
    "planner_calls_replay_inclusive_per_episode",
    "planner_calls_total",
    "error_types",
    "populations_coincide",
)
for label, arm in report.get("arms", {}).items():
    row = {k: arm.get(k) for k in fields}
    print(f"ARM {label}: {json.dumps(row, sort_keys=True)}")

wanted = [
    "goal_pass_all_sft_plan_iaware_minus_sft_plan_base",
    "goal_pass_survivors_sft_plan_iaware_minus_sft_plan_base",
    "tgc_all_sft_plan_iaware_minus_sft_plan_base",
    "tgc_survivors_sft_plan_iaware_minus_sft_plan_base",
    "goal_pass_all_fixed_k_10_iaware_minus_fixed_k_10_base",
    "goal_pass_survivors_fixed_k_10_iaware_minus_fixed_k_10_base",
    "tgc_all_fixed_k_10_iaware_minus_fixed_k_10_base",
    "tgc_survivors_fixed_k_10_iaware_minus_fixed_k_10_base",
    "goal_pass_all_fixed_k_3_iaware_minus_fixed_k_3_base",
    "goal_pass_survivors_fixed_k_3_iaware_minus_fixed_k_3_base",
    "tgc_all_fixed_k_3_iaware_minus_fixed_k_3_base",
    "tgc_survivors_fixed_k_3_iaware_minus_fixed_k_3_base",
    "goal_pass_all_oracle_escalation_iaware_minus_sft_plan_iaware",
    "goal_pass_survivors_oracle_escalation_iaware_minus_sft_plan_iaware",
    "tgc_all_oracle_escalation_iaware_minus_sft_plan_iaware",
    "tgc_survivors_oracle_escalation_iaware_minus_sft_plan_iaware",
]
contrasts = report.get("contrasts") or {}
for key in wanted:
    c = contrasts.get(key)
    if c is None:
        print(f"MISSING contrast {key}")
        continue
    print(
        "CONTRAST",
        key,
        json.dumps(
            {
                "diff": c.get("diff"),
                "ci95": c.get("ci95"),
                "diff_pp": c.get("diff_pp"),
                "ci95_pp": c.get("ci95_pp"),
                "n_pairs": c.get("n_pairs"),
                "n_pairs_dropped_crash": c.get("n_pairs_dropped_crash"),
                "n_pairs_shared": c.get("n_pairs_shared"),
                "population": c.get("population"),
                "left": c.get("left"),
                "right": c.get("right"),
            },
            sort_keys=True,
        ),
    )
print("h3:", json.dumps(report.get("h3")))
PY

echo "==== E5 CODEX LIVE COUNT (smoke definition; read-only) ===="
"$PY" - <<'PY'
import json
from pathlib import Path

roots = {
    "oracle_escalation_iaware": Path("/scratch/n12194778/sidekick/results/hj8_oracle_escalation_20260921iaware"),
    "oracle_escalation_base": Path("/scratch/n12194778/sidekick/results/hj8_oracle_escalation_20260920"),
}
for label, root in roots.items():
    live = 0
    n_files = 0
    n_episodes_with_live = 0
    for path in sorted(root.rglob("events.jsonl")):
        n_files += 1
        text = path.read_text(encoding="utf-8")
        ep_live = 0
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            ev = json.loads(raw)
            usage = ev.get("usage") or {}
            if ev.get("actor") == "planner" and usage.get("provider") == "codex":
                ep_live += max(1, int(usage.get("n_calls") or 1))
        live += ep_live
        if ep_live:
            n_episodes_with_live += 1
    print(
        json.dumps(
            {
                "label": label,
                "codex_planner_events": live,
                "n_events_files": n_files,
                "n_episodes_with_codex_planner": n_episodes_with_live,
            },
            sort_keys=True,
        )
    )
PY
exit "$rc"
