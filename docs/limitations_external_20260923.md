# External Limitations and Non-Comparability Note (F7)

Date: 2026-09-23

This note records the four concrete methodological differences between our experimental setup and published AppWorld leaderboard systems, followed by an explanation of the within-arm paired design that our empirical claims rest upon.

## 1. Scaffold and Interaction Budget
Published AppWorld evaluations use the official full-featured scaffold (e.g., standard ReAct or CodeAct scaffolds with domain-specific reflection and recovery loops). In contrast, our experiments use a deliberately minimal interaction loop designed to isolate the steering and execution mechanisms without scaffold-induced confounding. In our minimal loop, the planner alone requires approximately 14.4 mean interactions per episode under a 25-call cap, whereas published leaderboard entries for equivalent frontier models report around 9.3 mean interactions per episode [OBSERVED campaign/workers/lit/extracts_20260922.md:288-292; OBSERVED docs/PLAN.md:102-103]. As articulated in our planning principles [OBSERVED docs/PLAN.md:25], our research objective is to "prove the mechanism, not beat the leaderboard"; a complex scaffold-calibration run was explicitly evaluated and declined to avoid obscuring the causal effect of handoff and advice interventions.

## 2. Benchmark Split
All results reported in this thesis are evaluated strictly on the **dev** split. We report zero numbers on `test_normal` or `test_challenge`. The confirmatory test-split execution is gated behind formal preregistration [OBSERVED docs/prereg_j9_freeze_20260920.md:§8.1] and has deliberately not been authorized during exploratory and development phases. Consequently, our dev-split figures and published test-split leaderboard numbers lie on different axes, and no direct ranking between them is claimed or implied.

## 3. Pinned Task Count
The pinned environment and dataset release used in this repository provides **57 of the 60** standard dev tasks [OBSERVED docs/feasibility/g2_appworld.md:30-37; OBSERVED campaign/workers/lit/extracts_20260922.md:266-267]. Three dev tasks requiring unsupported multi-party synchronization were excluded at environment setup time. Cross-paper comparisons against reported 60-task dev evaluations are therefore subject to this slight denominator difference and should not be treated as point-for-point equivalent.

## 4. Reasoning Effort and Model Configuration
Our hosted planner uses `gpt-5.6-luna` configured explicitly with `model_reasoning_effort: medium`, chosen and strictly frozen across all arms to maintain predictable inference costs [OBSERVED campaign/briefs/SEAM_CONTRACT.md; OBSERVED AGENTS.md:87-88]. Public leaderboard entries for `gpt-5.6-luna` or related models do not necessarily use `medium` reasoning effort (and may employ higher reasoning effort tiers or unconstrained thinking budgets). This difference in compute allocation per planning step directly affects raw task completion rates.

## 5. Validity of Paired Within-Benchmark Comparisons
While absolute scores cannot be compared against external leaderboard numbers, our experimental design is specifically optimized for internal validity. All arms are paired within task and random seed, executing against shared, pre-recorded planner trajectories and identical environment initializations. By controlling for task difficulty and planner variance through task-clustered paired bootstrap estimation, differences between our intervention arms (such as plan conditioning, advice channels, and prefix handoffs) are resolved with high statistical precision. Every substantive claim in this work rests upon these controlled within-benchmark contrasts rather than external leaderboard standing.
