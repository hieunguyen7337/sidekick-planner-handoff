# External Comparison: Published AppWorld Benchmark Results

Date: 2026-09-23  
Scope: Published external AppWorld evaluation results alongside our internal dev-split baseline and intervention arms.

---

## 1. Published External Results on AppWorld

The table below compiles published results on the AppWorld benchmark suite across autonomous agent architectures, training paradigms, and foundation models. Every external number is tagged with its verified source URL.

| System Name | Base Model(s) | Split | Metric | Value (%) | Year | Full Citation & Source URL |
|---|---|---|---|---|---|---|
| **AppWorld Baselines** | | | | | | |
| ReAct | GPT-4o (2024-05-13) | `test_normal` | TGC | 48.8% | 2024 | Trivedi et al., *AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | GPT-4o (2024-05-13) | `test_normal` | SGC | 32.1% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | GPT-4o (2024-05-13) | `test_challenge` | TGC | 30.2% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | GPT-4o (2024-05-13) | `test_challenge` | SGC | 13.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| Plan & Execute (PlanExec) | GPT-4o (2024-05-13) | `test_normal` | TGC | 44.6% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:271-272] |
| Plan & Execute (PlanExec) | GPT-4o (2024-05-13) | `test_normal` | SGC | 23.2% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:271-272] |
| Plan & Execute (PlanExec) | GPT-4o (2024-05-13) | `test_challenge` | TGC | 19.7% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:271-272] |
| Plan & Execute (PlanExec) | GPT-4o (2024-05-13) | `test_challenge` | SGC | 7.9% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:271-272] |
| Full Code + Reflexion | GPT-4o (2024-05-13) | `test_normal` | TGC | 33.9% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272] |
| Full Code + Reflexion | GPT-4o (2024-05-13) | `test_normal` | SGC | 26.8% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272] |
| Full Code + Reflexion | GPT-4o (2024-05-13) | `test_challenge` | TGC | 19.2% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272] |
| Full Code + Reflexion | GPT-4o (2024-05-13) | `test_challenge` | SGC | 12.2% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272] |
| Iterative Parallel Function Calling | GPT-4o (2024-05-13) | `test_normal` | TGC | 32.1% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272-273] |
| Iterative Parallel Function Calling | GPT-4o (2024-05-13) | `test_normal` | SGC | 16.1% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272-273] |
| Iterative Parallel Function Calling | GPT-4o (2024-05-13) | `test_challenge` | TGC | 18.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272-273] |
| Iterative Parallel Function Calling | GPT-4o (2024-05-13) | `test_challenge` | SGC | 10.1% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:272-273] |
| ReAct | GPT-4-Turbo (2024-04-09) | `test_normal` | TGC | 26.8% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | GPT-4-Turbo (2024-04-09) | `test_normal` | SGC | 12.5% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | GPT-4-Turbo (2024-04-09) | `test_challenge` | TGC | 17.5% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | GPT-4-Turbo (2024-04-09) | `test_challenge` | SGC | 5.8% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| Full Code + Reflexion | LLaMA-3-70B-Instruct | `test_normal` | TGC | 24.4% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| Full Code + Reflexion | LLaMA-3-70B-Instruct | `test_normal` | SGC | 17.9% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273-274] |
| Full Code + Reflexion | LLaMA-3-70B-Instruct | `test_challenge` | TGC | 7.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| Full Code + Reflexion | LLaMA-3-70B-Instruct | `test_challenge` | SGC | 4.3% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:274] |
| ReAct | LLaMA-3-70B-Instruct | `test_normal` | TGC | 20.8% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | LLaMA-3-70B-Instruct | `test_normal` | SGC | 8.9% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | LLaMA-3-70B-Instruct | `test_challenge` | TGC | 3.4% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | LLaMA-3-70B-Instruct | `test_challenge` | SGC | 0.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:273] |
| ReAct | DeepSeek-Coder-33B-Instruct | `test_normal` | TGC | 7.1% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | DeepSeek-Coder-33B-Instruct | `test_normal` | SGC | 1.8% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:274] |
| ReAct | DeepSeek-Coder-33B-Instruct | `test_challenge` | TGC | 2.9% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ReAct | DeepSeek-Coder-33B-Instruct | `test_challenge` | SGC | 0.7% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED campaign/workers/lit/extracts_20260922.md:274] |
| CodeAct | Mistral-7B-CodeAct | `test_normal` / `test_challenge` | TGC / SGC | 0.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| ToolLLaMA | ToolLLaMA-7B | `test_normal` / `test_challenge` | TGC / SGC | 0.0% | 2024 | Trivedi et al., *AppWorld*, ACL 2024. [OBSERVED https://arxiv.org/abs/2407.18901] [OBSERVED https://arxiv.org/html/2407.18901v1] |
| **Post-Training & Scaffolding Innovations** | | | | | | |
| LOOP | 32B Open LLM | AppWorld | TGC relative | +9.0 pp vs o1 (~71% TGC) | 2025 | Anonymous, *Reinforcement Learning for Long-Horizon Interactive LLM Agents*, arXiv:2502.01600. [OBSERVED https://arxiv.org/abs/2502.01600] [OBSERVED campaign/workers/lit/extracts_20260922.md:278-279] |
| CANOPY | Qwen3-14B | `test_normal` | TGC | 86.9% | 2026 | Pu, Li, Liu, Cao and Yang, *Explore More, Drift Less: Outcome-Only Reinforcement Learning Can Suffice for Long-Horizon Interactive Agents* (submitted 2026-09-01), arXiv:2609.01245. [OBSERVED https://arxiv.org/abs/2609.01245] |
| CANOPY | Qwen3-14B | `test_challenge` | TGC | 67.6% | 2026 | Pu, Li, Liu, Cao and Yang, *Explore More, Drift Less*, arXiv:2609.01245. [OBSERVED https://arxiv.org/abs/2609.01245] |
| ACE (Agentic Context Engineering) | DeepSeek-V3.1 | AppWorld Leaderboard | TGC relative gain | +17.1% relative (+10.6% on agents) | 2026 | Anonymous, *Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models*, ICLR 2026 / arXiv:2510.04618. [OBSERVED https://arxiv.org/abs/2510.04618] [OBSERVED campaign/workers/lit/extracts_20260922.md:282-283] |
| Early Experience | Llama-3.2-3B / Qwen-2.5-7B / Llama-3.1-8B | 8 Interactive Envs | Success Rate | [UNVERIFIED — specific AppWorld sub-table not published in abstract] | 2026 | Anonymous, *Agent Learning via Early Experience*, ICML 2026 / arXiv:2510.08558. [OBSERVED https://arxiv.org/abs/2510.08558] |
| AppWorld-UL (User-in-the-Loop) | Claude Opus 4.7 | `AppWorld-UL` (516 tasks) | Success Rate (Overall) | 48.6% | 2026 | Anonymous, *AppWorld-UL: Benchmarking Diverse Agent-User Interactions for Tool-Use*, ICML 2026 / arXiv:2607.20536. [OBSERVED https://arxiv.org/abs/2607.20536] |
| AppWorld-UL (User-in-the-Loop) | Claude Opus 4.7 | `AppWorld-UL` (Compositional subset) | Success Rate | 35.7% | 2026 | Anonymous, *AppWorld-UL*, arXiv:2607.20536. [OBSERVED https://arxiv.org/abs/2607.20536] |
| AppWorld-UL (User-in-the-Loop) | Claude Opus 4.7 | `AppWorld-UL` (Compositional subset) | Scenario Success (SGC) | 21.3% | 2026 | Anonymous, *AppWorld-UL*, arXiv:2607.20536. [OBSERVED https://arxiv.org/abs/2607.20536] |
| ProST | ~8B Open Models (SFT) | AppWorld | TGC | 26.0–33.0% | 2025 | Bijoy et al., *ProST: Progressive Sub-task Training for Pareto-Optimal Multi-agent Systems Using Small Language Models*, IJCNLP-AACL 2025 / arXiv:2509.04508. [OBSERVED https://arxiv.org/abs/2509.04508] [OBSERVED docs/literature_matrix.md:38] |
| Three Roles, One Model | Qwen3-8B (FP16 / AWQ, 3-role scaffold) | AppWorld | TGC | 8.9% (FP16) / 5.9% (AWQ) | 2026 | Anonymous, *Three Roles, One Model*, arXiv:2604.11465. [OBSERVED https://arxiv.org/abs/2604.11465] [OBSERVED docs/literature_matrix.md:95-96] |
| **Public Leaderboard Anchor for Planner Model** | | | | | | |
| Kecaipan Capybara Scaffold | `gpt-5.6-luna` | `test_normal` | TGC | 85.1% | 2026 | Official AppWorld Public Leaderboard JSON / https://appworld.dev/ [OBSERVED docs/PLAN.md:102-103] [OBSERVED campaign/workers/lit/extracts_20260922.md:288-290] |
| Kecaipan Capybara Scaffold | `gpt-5.6-luna` | `test_normal` | SGC | 73.2% | 2026 | Official AppWorld Public Leaderboard JSON / https://appworld.dev/ [OBSERVED docs/PLAN.md:102-103] [OBSERVED campaign/workers/lit/extracts_20260922.md:288-290] |
| Kecaipan Capybara Scaffold | `gpt-5.6-luna` | `test_challenge` | TGC | 73.4% | 2026 | Official AppWorld Public Leaderboard JSON / https://appworld.dev/ [OBSERVED docs/PLAN.md:102-103] [OBSERVED campaign/workers/lit/extracts_20260922.md:288-290] |
| Kecaipan Capybara Scaffold | `gpt-5.6-luna` | `test_challenge` | SGC | 52.5% | 2026 | Official AppWorld Public Leaderboard JSON / https://appworld.dev/ [OBSERVED docs/PLAN.md:102-103] [OBSERVED campaign/workers/lit/extracts_20260922.md:288-290] |

---

## 2. Our Internal Dev-Split Results (Intervention Arms)

All numbers below are measured strictly on the **dev** split (57 tasks, 114 paired episodes at 2 seeds) under our minimal interaction loop. Every number corresponds exactly to an entry in `docs/claims_ledger.md`.

| Arm | `goal_pass_rate` | Split / Evaluated Population | Ledger Claim ID | Context / Note |
|---|---|---|---|---|
| **executor alone** (`ibm-granite/granite-4.2-8b` + adapter) | 0.5289 | dev (all 114 episodes) | `ADV-FC-02`, `TAILOR-06` | Cross-build capability floor (`hj8_executor_alone_bplus_20260919`) |
| **one plan** (`sft_plan`, `iaware` build) | 0.7181 | dev (all 114 episodes) | `ADV-FC-01`, `ADV-FC-02`, `UF-01` | Initial prose plan from hosted planner; zero intermediate escalation |
| **advice k=10, full context** | 0.7339 | dev (all 114 episodes) | `ADV-FC-01` | Periodic prose critique every 10 steps with un-truncated context window |
| **takeover k=10** (action channel, matched trigger) | 0.8007 | dev (all 114 episodes) | `CHAN-C1-01` | Action execution at trigger step; point estimate only (CI pending) |
| **action prefix m=9** (tailored receiver) | 0.7852 | dev (all 114 episodes) | `SHAPE-01`, `SHAPE-06` | First 9 actions replayed from planner; post-terminal guard |
| **action prefix m=11** (tailored receiver) | 0.8098 | dev (all 114 episodes) | `SHAPE-06`, `PRED-01-RESULT`, `TAILOR-07` | First 11 actions replayed from planner; post-terminal guard |
| **ceiling, cap-25** (`planner_alone`) | 0.8284 | dev (all 114 episodes) | `CEIL-01`, `CEIL-02`, `CHAN-ZS-05` | Capped at 25 calls (source of replayed prefix trajectories) |
| **ceiling, cap-81** (`planner_alone`) | 0.7637 | dev (all 114 episodes) | `CEIL-01`, `CEIL-02`, `CEIL-03` | Capped at 81 calls; independent sample exhibiting over-acting degradation |

---

## 3. Explanatory Cross-Reference

For an explicit breakdown of the four methodological factors explaining why our dev figures (0.72–0.83) differ from published test-split leaderboard scores (and why our internal paired comparisons remain statistically valid and robust), see `docs/limitations_external_20260923.md`.
