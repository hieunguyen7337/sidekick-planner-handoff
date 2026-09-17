# W-5 — the executor's own P(ASK) as the frontier knob

Repo (work here, nowhere else):
`/mnt/hpccs01/home/n12194778/iaes/.claude/worktrees/plan-2026-09-15`

## Why this exists

The campaign needs several operating points per system to draw a quality-versus-cost
frontier. For the sidekick those points were going to come from three DPO training runs.
They now come from **one adapter swept on a threshold τ**: gate the policy's own ASK on
the probability it assigned to asking. Zero extra training, any number of points, and the
same number is H3's calibration measurement. Your unit is what makes that sweep possible.

## Goal

1. The executor records, on every action, the probability it put on emitting an ASK.
2. A `SelfVerifier` returns that probability as the score the existing gate already reads.
3. A vetoed ASK is **re-decoded once with the ASK token banned**, instead of burning a
   step on `ASK_IGNORED`.

## What already exists — do not redesign it

- `src/sidekick/systems/loop.py:759-761` already gates asks:

  ```python
  allow = policy.allow_executor_ask and packet is not None
  if allow and policy.gate_ask_with_verifier:
      v = verifier or ConstantVerifier()
      if not (v.score(trajectory_state(step)) > policy.verifier_threshold):
  ```

  `ExecutionPolicy` already carries `gate_ask_with_verifier: bool` (`loop.py:60`) and
  `verifier_threshold: float` (`loop.py:63`). **The gate is built. It is fed a constant.**
- `src/sidekick/agents/verifier.py` defines `Verifier` as a Protocol with one method,
  `score(self, trajectory_state: Any) -> float`. Add to this file; do not restructure it.
- `trajectory_state` is built at `loop.py:492-500` and returns exactly:
  `step`, `transcript`, `last_action`, `last_observation`, `n_asks`, `n_interventions`.
- The executor contract is `complete(self, messages: list[dict], **kw) -> tuple[str, Usage]`
  (`src/sidekick/agents/executor.py:20`, implemented at `:83` by `VLLMExecutor` and at
  `:251` by `MockExecutor`).

## The seam contract — this is the part to get exactly right

🔺 **Do not change the `(text, usage)` return shape.** It has many callers, including the
branch machinery that is running live jobs right now. Carry the new number **on the
`Usage` object** as an optional field defaulting to `None`, so every existing caller is
untouched and a client that cannot supply it simply reports `None`.

- Request first-token logprobs from the server (`logprobs`, `top_logprobs`) and compute
  `p_ask` as the total probability mass, at the **first generated token position**, of the
  tokens that begin the ASK template. The only ASK text the policy ever emits is:

  `ASK_PLANNER: Review my progress so far and tell me the next step.`

  so the relevant prefix is whatever tokenises the start of `ASK_PLANNER`. Compute the
  mass over **every** top-k token whose string is a prefix of, or equal to, that opening —
  a single hardcoded token id is wrong, because the tokeniser may split it more than one
  way. If the server returns no logprobs, `p_ask` is `None`, never `0.0`.

  ⚠ `p_ask = 0.0` and `p_ask = None` must stay distinguishable all the way to the event
  log. A missing measurement silently recorded as zero probability is the single failure
  mode this campaign keeps hitting; a gate reading it would veto every ask and the run
  would look healthy.

- Record `p_ask` on the action event payload so it lands in `events.jsonl`.
- `SelfVerifier.score(trajectory_state)` returns the `p_ask` of the action currently being
  decided. It needs the value threaded to it; the state dict at `loop.py:492` is the
  natural carrier — add a key rather than inventing a side channel. When `p_ask` is
  `None`, `score` must return a value that leaves the ask **allowed**, and the episode must
  record that it fell back. Do not silently deny.
- Config wiring: `verifier: {kind: self_p_ask, threshold: <τ>}`, alongside however
  `verifier` is already resolved for the runner. Match the existing config style.

## The re-decode

At `loop.py:805-807` a vetoed ask currently appends `ASK_IGNORED` to the transcript and
spends the step. Replace that, **for the self-gated path only**, with one re-decode of the
same prompt with the ASK opening token(s) banned via `logit_bias`. Exactly one retry: if
the re-decode also produces an ask, fall back to today's `ASK_IGNORED` behaviour so the
loop cannot spin. Leave the behaviour of the non-self-gated path alone — `router_seq` and
the existing tests depend on it.

## Tests (required, and they must not need a GPU)

Against a fake OpenAI-compatible server, in the style already used in `tests/`:

- a response carrying logprobs yields the expected `p_ask`, including the case where the
  ASK opening is split across more than one candidate token;
- a response carrying **no** logprobs yields `p_ask is None`, the ask is allowed, and the
  fallback is recorded;
- `p_ask = 0.0` is preserved as `0.0` and is **not** conflated with `None` anywhere,
  including after a round trip through the event log;
- the gate vetoes exactly when `p_ask > threshold` is false, matching the strict
  greater-than already in `ThresholdRouter`;
- a vetoed ask re-decodes once with the ban applied, and a second ask falls back to
  `ASK_IGNORED` rather than looping;
- an episode with `gate_ask_with_verifier=False` behaves byte-identically to today.

## Constraints — read these, you are not covered by the login-node guard

- `aquarius01` is a **login node for steering only**. No `python`, `pip`, `tar`, `rsync` or
  `ffmpeg` there. Anything that computes goes in a PBS job via `hpc`, `hpc-py` or `qsub`.
  Put `timeout` on every command you run. Pin BLAS to one thread.
- **Do not submit any job.** Three J6 jobs are running or queued against live campaign
  trees; a stray submission corrupts them.
- **Do not commit.** Leave the work in the tree; the orchestrator reads the diff.
- Run the suite as `pytest tests -q --import-mode=importlib` — plain `pytest` dies on a
  duplicate test basename and the narrowed run that "fixes" it reports a healthy number
  for a subset. Baseline to match or beat: **286 passed, 1 skipped, 0 failures.**
- Write `campaign/workers/STATUS_W_5.md` and update it at every milestone with resume
  state, so a killed session can be continued rather than restarted.
- Ignore `.claude/worktrees/` and `.git/`.

## Return contract

- The diff, and the test output as emitted.
- One line each on: where `p_ask` is computed, where it is recorded, and where the
  `None`-vs-`0.0` distinction is enforced — each with `path:line`.
- Tag every factual claim `[OBSERVED <path>:<line>]` or `[INFERRED]`.
