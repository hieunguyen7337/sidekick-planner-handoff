"""Shared episode loop and run limits. All eight systems call this."""
from __future__ import annotations

import signal
from dataclasses import dataclass, replace
from typing import Any, Callable, Literal, Optional

from sidekick.agents.planner import (
    CodexTimeoutError,
    PacketParseError,
    PlannerClient,
    PlannerContextOverflow,
)
from sidekick.agents.verifier import ConstantVerifier, SelfVerifier, ThresholdRouter, Verifier
from sidekick.systems.action_review_gate import run_action_review
from sidekick.environments.base import BaseEnv
from sidekick.protocols.prompts import format_executor_action, render_executor_messages
from sidekick.protocols.schemas import (
    ActionParseError,
    DelegationPacket,
    Event,
    ExecutorAction,
    Observation,
    PlannerResponse,
    RunResult,
    Usage,
    parse_executor_action,
    utc_now_iso,
)
from sidekick.trajectories.eventlog import EventLog
from sidekick.training.sft_data import _history_from_events

try:
    from sidekick.cost.ledger import CostLedger
except ImportError:  # U2 seam may lag; runner tests skip if missing
    CostLedger = Any  # type: ignore[misc, assignment]


DEFAULT_MAX_STEPS = 40
DEFAULT_MAX_TOKENS_PER_EPISODE = 32000
DEFAULT_PER_STEP_TIMEOUT_S = 120.0
DEFAULT_MAX_PLANNER_CALLS = 25
# Extra attempts allowed when the executor's reply cannot be read as an action. Two, not
# more: a model that has missed the format three times running is not going to find it on
# the fourth, and the retries are charged to the episode's token budget like any other
# call. Each retry is logged as `parse_error_retry`, so the cost of format non-compliance
# stays visible instead of being absorbed into the score.
MAX_PARSE_RETRIES = 2


@dataclass
class RunLimits:
    max_steps: int = DEFAULT_MAX_STEPS
    max_tokens_per_episode: int = DEFAULT_MAX_TOKENS_PER_EPISODE
    per_step_timeout_s: float = DEFAULT_PER_STEP_TIMEOUT_S
    max_planner_calls: int = DEFAULT_MAX_PLANNER_CALLS


@dataclass
class SystemPolicy:
    plan_first: bool = True
    planner_drives: bool = False
    allow_executor_ask: bool = True
    review_every_k: int | None = None
    use_router: bool = False
    gate_ask_with_verifier: bool = False
    oracle_steps: frozenset[int] = frozenset()
    adapter_name: str | None = None
    verifier_threshold: float = 0.5
    review_proposed_action: bool = False
    takeover: bool = False
    # B2 "show, don't execute": at a forced review, call planner.act exactly as takeover does
    # (same prompt, same transcript), but deliver the parsed action to the executor as an
    # INTERVENTION turn instead of executing it. Isolates execution from content.
    advice_from_act: bool = False
    handoff_allowed: bool = False
    # None = whole transcript on the forced-review *advise* path only.
    # An integer is that many trailing lines. Default 8 matches every existing arm.
    correct_context_lines: int | None = 8
    # Prefix already finished: "stop" ends with the replayed outcome (default);
    # "continue" is the pre-guard behaviour (executor still acts).
    post_prefix_terminal: Literal["stop", "continue"] = "stop"


@dataclass
class EpisodePrefix:
    """Start `run_episode` from a replayed intervention prefix instead of reset.

    Default callers omit this; the scratch-start path is unchanged. ``events`` are
    the original-episode events up to and including the observation immediately
    before the focal intervention (last attempt, file order). ``start_step`` is
    that intervention's step ``s`` — the first step the branch itself will take.

    Counterfactual branches set ``skip_review_at_start=True`` so the scheduled
    reviewer does not fire at ``s``. The treated arm then injects the recorded
    correction via ``inject_correction``; the untreated arm leaves it None.
    Later scheduled ticks still call ``planner.correct()`` on the branch state
    unless ``skip_next_scheduled_review`` is True, in which case the next
    scheduled tick after ``s`` is also skipped in the arm that sets the flag.
    Counterfactual ``suppress_next`` sets the flag on both arms so the
    substitute cannot confound the contrast. That tick is the next step the
    schedule would actually have fired, not ``s + review_every_k``. Router-
    and oracle-triggered reviews are not scheduled reviews and are not skipped.
    ``local_eval_step`` is the next scheduled review step: ``env.evaluate()``
    runs *before* that review so the short-horizon GPR is uncontaminated.

    ``skip_next_scheduled_review`` defaults to False so callers that omit it
    reproduce today's skip-at-s-only behaviour.
    """

    events: list[Event]
    start_step: int
    inject_correction: str | None = None
    skip_review_at_start: bool = False
    local_eval_step: int | None = None
    skip_next_scheduled_review: bool = False


def next_scheduled_review_step(start_step: int, review_every_k: int | None) -> int | None:
    """First scheduled tick strictly after ``start_step``.

    This is the next step at which ``step % review_every_k == 0``, not
    ``start_step + review_every_k``. Returns None if the schedule would never
    fire again (``review_every_k`` missing or non-positive).
    """
    if review_every_k is None:
        return None
    k = int(review_every_k)
    if k <= 0:
        return None
    t = start_step - (start_step % k) + k
    if t <= start_step:
        t += k
    return t


def counters_from_events(events: list[Event]) -> tuple[int, int, int, int]:
    """Prefix counters: episode_tokens, n_asks, n_interventions, n_planner_calls."""
    tokens = 0
    n_asks = 0
    n_interventions = 0
    n_planner_calls = 0
    for ev in events:
        if ev.usage is not None:
            tokens += token_count(ev.usage)
            if ev.actor == "planner":
                n_planner_calls += max(1, int(ev.usage.n_calls or 1))
        if ev.event_type == "ask":
            n_asks += 1
        elif ev.event_type == "intervention":
            n_interventions += 1
    return tokens, n_asks, n_interventions, n_planner_calls


def last_observation_from_events(events: list[Event]) -> Observation:
    """Rebuild the last recorded observation so a prefix start need not reset."""
    for ev in reversed(events):
        if ev.event_type != "observation":
            continue
        payload = ev.payload or {}
        return Observation(
            text=str(payload.get("text") or ""),
            step=int(ev.step),
            done=bool(payload.get("done", False)),
            truncated=bool(payload.get("truncated", False)),
            env_state_hash=ev.env_state_hash,
            error_type=ev.error_type,
        )
    return Observation(text="", step=0)


def prefix_is_terminal(events: list[Event], last_obs: Observation) -> bool:
    """True when a replayed prefix already ended the source episode."""
    if last_obs.done:
        return True
    for ev in reversed(events):
        if ev.event_type != "action":
            continue
        return (ev.payload or {}).get("kind") == "COMPLETE"
    return False


def token_count(usage: Usage) -> int:
    """Count uncached input, output, and reasoning tokens for the episode budget.

    Cached input is excluded because it is resent transcript context, not new work
    that should consume the nominal per-episode token budget.
    """
    return int(
        max(0, usage.input_tokens - usage.cached_input_tokens)
        + usage.output_tokens
        + usage.reasoning_output_tokens
    )


def call_with_timeout(fn: Callable[[], Any], timeout_s: float) -> Any:
    """Run ``fn`` in the current thread, aborting via SIGALRM (no extra threads)."""
    if timeout_s is None or timeout_s <= 0:
        return fn()

    def _handle(signum: int, frame: Any) -> None:
        raise TimeoutError(f"timed out after {timeout_s}s")

    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle)
    signal.setitimer(signal.ITIMER_REAL, float(timeout_s))
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous)


class ConfigurableSystem:
    """Base class for the eight named systems; subclasses set ``name`` and ``policy_defaults``."""

    name: str = ""
    policy_defaults: SystemPolicy = SystemPolicy()

    def __init__(
        self,
        planner: PlannerClient,
        executor: Any | None = None,
        verifier: Verifier | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        **kwargs: Any,
    ) -> None:
        self.planner = planner
        self.executor = executor
        self.verifier = verifier
        self.limits = limits or RunLimits()
        base = policy or self.policy_defaults
        overlay = {k: v for k, v in kwargs.items() if hasattr(base, k) and (v is not None or k == "correct_context_lines")}
        self.policy = replace(base, **overlay)
        if self.policy.takeover and self.policy.advice_from_act:
            raise ValueError("takeover and advice_from_act are mutually exclusive channels")

    def run(
        self,
        env: BaseEnv,
        task_id: str,
        seed: int,
        log: EventLog,
        ledger: CostLedger,
        prefix: EpisodePrefix | None = None,
    ) -> RunResult:
        return run_episode(
            name=self.name,
            env=env,
            planner=self.planner,
            executor=self.executor,
            verifier=self.verifier,
            policy=self.policy,
            limits=self.limits,
            task_id=task_id,
            seed=seed,
            log=log,
            ledger=ledger,
            prefix=prefix,
        )


def run_episode(
    *,
    name: str,
    env: BaseEnv,
    planner: PlannerClient,
    executor: Any | None,
    verifier: Verifier | None,
    policy: SystemPolicy,
    limits: RunLimits,
    task_id: str,
    seed: int,
    log: EventLog,
    ledger: CostLedger,
    prefix: EpisodePrefix | None = None,
    sampling_seed: int | None = None,
) -> RunResult:
    n_asks = 0
    n_interventions = 0
    n_planner_calls = 0
    n_planner_actions = 0
    n_post_terminal_actions = 0
    handoff_step: int | None = None
    driver_is_planner = policy.planner_drives
    episode_tokens = 0
    error_type: Optional[str] = None
    packet: Optional[DelegationPacket] = None
    last_obs: Optional[Observation] = None
    last_action: Optional[ExecutorAction] = None
    last_p_ask: Optional[float] = None
    transcript: list[str] = []
    # `transcript` is a frozen wire format for the planner (INSTRUCTION:/PLAN:/OBS:/...).
    # `exec_turns` is the executor's conversation (assistant actions, user observations).
    # The redundancy is deliberate: changing `transcript` would invalidate a running
    # teacher-data campaign and the HJ-1 planner baseline.
    exec_turns: list[dict] = []
    exec_instruction = ""
    exec_api_docs = ""
    steps_taken = 0
    start_step = 1
    eval_result: dict[str, Any] = {
        "success": False,
        "tgc": None,
        "sgc": None,
        "goal_pass_rate": None,
        "report": {},
    }
    timeout_s = limits.per_step_timeout_s
    router = None
    if policy.use_router:
        router = ThresholdRouter(verifier or ConstantVerifier(), policy.verifier_threshold)

    def emit(
        *,
        step: int,
        actor: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        usage: Usage | None = None,
        env_state_hash: str | None = None,
        error: str | None = None,
    ) -> None:
        log.append(
            Event(
                run_id=log.run_id,
                task_id=task_id,
                system=name,
                seed=seed,
                step=step,
                ts=utc_now_iso(),
                actor=actor,  # type: ignore[arg-type]
                event_type=event_type,  # type: ignore[arg-type]
                payload=payload or {},
                usage=usage,
                env_state_hash=env_state_hash,
                error_type=error,
            )
        )

    def charge(actor: str, usage: Usage) -> None:
        nonlocal episode_tokens
        ledger.add(actor, usage)  # type: ignore[arg-type]
        episode_tokens += token_count(usage)

    def over_token_limit() -> bool:
        return episode_tokens >= limits.max_tokens_per_episode

    def call_planner(method: str, fn: Callable[[], PlannerResponse], step: int) -> PlannerResponse | None:
        nonlocal n_planner_calls, error_type
        if n_planner_calls >= limits.max_planner_calls:
            error_type = "limit"
            emit(
                step=step,
                actor="system",
                event_type="error",
                payload={"limit": "max_planner_calls", "n_planner_calls": n_planner_calls},
                error="limit",
            )
            return None
        attempts = 0
        last_exc: Exception | None = None
        while attempts < 2:
            attempts += 1
            n_planner_calls += 1
            try:
                resp = fn()
            except CodexTimeoutError as exc:
                last_exc = exc
                usage = exc.usage.model_copy(update={"n_calls": attempts})
                charge("planner", usage)
                emit(
                    step=step,
                    actor="planner",
                    event_type="error",
                    payload={"method": method, "attempt": attempts},
                    usage=usage,
                    error="timeout",
                )
                if attempts >= 2:
                    error_type = "timeout"
                    return None
                continue
            except TimeoutError as exc:
                last_exc = exc
                usage = Usage(
                    model=_client_model_id(planner, "planner"),
                    provider="mock",
                    n_calls=attempts,
                    raw={"error_type": "timeout"},
                )
                charge("planner", usage)
                emit(
                    step=step,
                    actor="planner",
                    event_type="error",
                    payload={"method": method, "attempt": attempts, "detail": str(exc)},
                    usage=usage,
                    error="timeout",
                )
                if attempts >= 2:
                    error_type = "timeout"
                    return None
                continue
            except PacketParseError as exc:
                usage = Usage(
                    model=_client_model_id(planner, "planner"),
                    provider="mock",
                    n_calls=attempts,
                    raw={"error_type": "parse_error"},
                )
                charge("planner", usage)
                emit(
                    step=step,
                    actor="planner",
                    event_type="error",
                    payload={"method": method, "raw_output": exc.raw_output[:4000]},
                    usage=usage,
                    error="parse_error",
                )
                error_type = "parse_error"
                return None
            except PlannerContextOverflow as exc:
                # A planner that cannot fit the episode in its context has exhausted a budget,
                # like the step or token caps, so this is a `limit` and the episode is still
                # evaluated and scored. `crash` would drop it from the analysis and resubmit it
                # forever -- hiding the failure and never terminating. No retry: the thread
                # only grows, so a second attempt cannot fit where the first did not.
                usage = exc.usage if exc.usage is not None else Usage(
                    model=_client_model_id(planner, "planner"),
                    provider="mock",
                    n_calls=attempts,
                    raw={"error_type": "limit"},
                )
                usage = usage.model_copy(update={"n_calls": attempts})
                charge("planner", usage)
                emit(
                    step=step,
                    actor="planner",
                    event_type="error",
                    payload={"method": method, "limit": "planner_context", "detail": str(exc)},
                    usage=usage,
                    error="limit",
                )
                error_type = "limit"
                return None
            usage = resp.usage.model_copy(update={"n_calls": attempts})
            resp = resp.model_copy(update={"usage": usage})
            charge("planner", usage)
            return resp
        error_type = error_type or "timeout"
        emit(
            step=step,
            actor="system",
            event_type="error",
            payload={"method": method, "detail": str(last_exc)},
            error=error_type,
        )
        return None

    def action_from_planner(
        resp: PlannerResponse, step: int, *, fatal_parse: bool = True
    ) -> ExecutorAction | None:
        nonlocal error_type
        raw = resp.raw_output or ""
        if policy.handoff_allowed and any(line.strip() == "HANDOFF" for line in raw.splitlines()):
            return ExecutorAction(kind="HANDOFF", raw_output=raw or "HANDOFF")
        if resp.code and resp.code.strip():
            return ExecutorAction(kind="CODE", code=resp.code, raw_output=raw or resp.code)
        try:
            return parse_executor_action(raw)
        except ActionParseError as exc:
            emit(
                step=step,
                actor="planner",
                event_type="error",
                payload={"raw_output": exc.raw_output[:4000]},
                usage=resp.usage,
                error="parse_error",
            )
            if fatal_parse:
                error_type = "parse_error"
            return None

    def measure_p_ask() -> bool:
        # Self-gate path: only SelfVerifier opted into first-token P(ASK).
        # ConstantVerifier (J6 default) must not change request or event shape.
        return isinstance(verifier, SelfVerifier)

    def p_ask_event_fields() -> dict[str, Any]:
        """Action/ask payload keys. Absent = feature off; null = on but unmeasurable."""
        if not measure_p_ask():
            return {}
        fields: dict[str, Any] = {"p_ask": last_p_ask}
        if last_p_ask is None:
            fields["p_ask_fallback"] = True
        return fields

    def action_from_executor(step: int, *, ban_ask_prefix: bool = False) -> ExecutorAction | None:
        nonlocal error_type, last_p_ask
        if executor is None:
            error_type = "crash"
            emit(step=step, actor="system", event_type="error", payload={"detail": "no executor"}, error="crash")
            return None
        messages = render_executor_messages(
            instruction=exec_instruction,
            api_docs=exec_api_docs,
            packet=packet,
            history=exec_turns,
        )
        # One unparseable generation used to end the episode outright. That makes the
        # score a measure of output-format luck rather than task ability: Granite 4.2
        # produced five distinct wrappers on 2026-09-15, so at even a few percent per
        # step, a 13-step episode dies on format alone about a third of the time -- and a
        # format-crippled executor scores LOW, which makes HJ-1's "is there a capability
        # gap" gate easier to pass for entirely the wrong reason. Ask again instead,
        # bounded, and log every retry so the format burden stays measurable rather than
        # hidden inside the score.
        action: ExecutorAction | None = None
        for attempt in range(MAX_PARSE_RETRIES + 1):
            try:
                complete_kw: dict[str, Any] = {
                    "lora_name": policy.adapter_name,
                    "task_id": task_id,
                }
                if sampling_seed is not None:
                    complete_kw["seed"] = sampling_seed
                if ban_ask_prefix:
                    complete_kw["ban_ask_prefix"] = True
                if measure_p_ask():
                    complete_kw["logprobs"] = True
                text, usage = call_with_timeout(
                    lambda: executor.complete(messages, **complete_kw),
                    timeout_s,
                )
            except TimeoutError as exc:
                usage = Usage(
                    model=_client_model_id(executor, "executor"),
                    provider="mock",
                    n_calls=1,
                    raw={"error_type": "timeout"},
                )
                last_p_ask = usage.p_ask
                charge("executor", usage)
                emit(
                    step=step,
                    actor="executor",
                    event_type="error",
                    payload={"detail": str(exc)},
                    usage=usage,
                    error="timeout",
                )
                error_type = "timeout"
                return None
            last_p_ask = usage.p_ask
            charge("executor", usage)
            try:
                action = parse_executor_action(text)
                break
            except ActionParseError as exc:
                if attempt >= MAX_PARSE_RETRIES:
                    emit(
                        step=step,
                        actor="executor",
                        event_type="error",
                        payload={"raw_output": exc.raw_output[:4000], "attempts": attempt + 1},
                        usage=usage,
                        error="parse_error",
                    )
                    error_type = "parse_error"
                    return None
                emit(
                    step=step,
                    actor="executor",
                    event_type="error",
                    payload={"raw_output": exc.raw_output[:2000], "attempt": attempt + 1},
                    usage=usage,
                    error="parse_error_retry",
                )
                messages = messages + [
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": (
                            "That reply could not be read as an action. Reply with exactly "
                            "one action and nothing else — a ```python fenced block, or a "
                            "line starting ASK_PLANNER:, REPORT:, or COMPLETE. No "
                            "explanation, no tags, no expected output."
                        ),
                    },
                ]
        if action is None:  # pragma: no cover - the loop above always returns or breaks
            error_type = "parse_error"
            return None
        payload = action.model_dump()
        payload.update(p_ask_event_fields())
        emit(
            step=step,
            actor="executor",
            event_type="action",
            payload=payload,
            usage=usage,
            env_state_hash=env.snapshot_hash(),
        )
        return action

    def trajectory_state(step: int) -> dict[str, Any]:
        return {
            "step": step,
            "transcript": "\n".join(transcript),
            "last_action": None if last_action is None else last_action.model_dump(),
            "last_observation": None if last_obs is None else last_obs.model_dump(),
            "n_asks": n_asks,
            "n_interventions": n_interventions,
            "p_ask": last_p_ask,
        }

    try:
        if prefix is not None:
            start_step = max(1, int(prefix.start_step))
            hist_instruction, hist_packet, hist_api_docs, hist_turns = _history_from_events(
                list(prefix.events)
            )
            exec_instruction = hist_instruction or env.instruction
            exec_api_docs = hist_api_docs or env.api_docs_prompt
            packet = hist_packet
            exec_turns = list(hist_turns)
            episode_tokens, n_asks, n_interventions, n_planner_calls = counters_from_events(
                list(prefix.events)
            )
            last_obs = last_observation_from_events(list(prefix.events))
            transcript.append(f"INSTRUCTION: {exec_instruction}")
            if packet is not None:
                transcript.append(f"PLAN: {packet.model_dump_json()}")
            for turn in exec_turns:
                content = str(turn.get("content") or "")
                if turn.get("role") != "user":
                    continue
                if content.startswith(("OBS:", "INTERVENTION:", "ANSWER:", "ASK_IGNORED")):
                    transcript.append(content)
        else:
            last_obs = env.reset(task_id, seed)
            exec_instruction = env.instruction
            exec_api_docs = env.api_docs_prompt
            transcript.append(f"INSTRUCTION: {env.instruction}")

        run_start_payload: dict[str, Any] = {
            "limits": {
                "max_steps": limits.max_steps,
                "max_tokens_per_episode": limits.max_tokens_per_episode,
                "per_step_timeout_s": limits.per_step_timeout_s,
                "max_planner_calls": limits.max_planner_calls,
            },
            "policy": {
                "plan_first": policy.plan_first,
                "planner_drives": policy.planner_drives,
                "allow_executor_ask": policy.allow_executor_ask,
                "review_every_k": policy.review_every_k,
                "use_router": policy.use_router,
                "gate_ask_with_verifier": policy.gate_ask_with_verifier,
                "adapter_name": policy.adapter_name,
            },
        }
        if policy.review_proposed_action:
            run_start_payload["policy"]["review_proposed_action"] = True
        if policy.takeover:
            run_start_payload["policy"]["takeover"] = True
        if policy.advice_from_act:
            run_start_payload["policy"]["advice_from_act"] = True
        if policy.handoff_allowed:
            run_start_payload["policy"]["handoff_allowed"] = True
        if prefix is not None:
            run_start_payload["prefix"] = {
                "start_step": start_step,
                "n_events": len(prefix.events),
                "episode_tokens": episode_tokens,
            }
            run_start_payload["policy"]["post_prefix_terminal"] = policy.post_prefix_terminal
        if sampling_seed is not None:
            run_start_payload["sampling_seed"] = int(sampling_seed)
        emit(
            step=0,
            actor="system",
            event_type="run_start",
            payload=run_start_payload,
            env_state_hash=last_obs.env_state_hash,
        )
        emit(
            step=0,
            actor="environment",
            event_type="observation",
            payload={"text": last_obs.text, "done": last_obs.done},
            env_state_hash=last_obs.env_state_hash,
        )

        if prefix is None and policy.plan_first:
            resp = call_planner(
                "plan",
                lambda: planner.plan(task_id, env.instruction, env.api_docs_prompt, timeout_s=timeout_s),
                0,
            )
            if resp is None:
                pass
            elif resp.packet is None:
                error_type = "parse_error"
                emit(
                    step=0,
                    actor="planner",
                    event_type="error",
                    payload={"raw_output": resp.raw_output[:4000]},
                    usage=resp.usage,
                    error="parse_error",
                )
            else:
                packet = resp.packet
                emit(
                    step=0,
                    actor="planner",
                    event_type="plan",
                    payload={
                        "packet": packet.model_dump(),
                        "parse_path": resp.usage.raw.get("packet_parse_path"),
                        "model": resp.usage.raw.get("resolved_model") or resp.usage.model,
                        "model_reasoning_effort": resp.usage.raw.get("resolved_model_reasoning_effort")
                        or resp.usage.raw.get("model_reasoning_effort"),
                        "thread_id": resp.thread_id, **_plan_event_fields(resp.usage.raw),
                    },
                    usage=resp.usage,
                )
                transcript.append(f"PLAN: {packet.model_dump_json()}")

        if error_type is None and over_token_limit():
            error_type = "limit"
            emit(
                step=0,
                actor="system",
                event_type="error",
                payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                error="limit",
            )

        prefix_terminal = False
        skip_live_loop = False
        if prefix is not None:
            prefix_terminal = prefix_is_terminal(list(prefix.events), last_obs)
            skip_live_loop = (
                policy.post_prefix_terminal == "stop" and prefix_terminal
            )
        if skip_live_loop:
            steps_taken = int(last_obs.step)

        for step in range(start_step, limits.max_steps + 1):
            if skip_live_loop:
                break
            if error_type is not None:
                break
            if over_token_limit():
                error_type = "limit"
                emit(
                    step=step,
                    actor="system",
                    event_type="error",
                    payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                    error="limit",
                )
                break
            steps_taken = step
            forced_action: ExecutorAction | None = None

            if (
                prefix is not None
                and prefix.local_eval_step is not None
                and step == prefix.local_eval_step
            ):
                try:
                    local_eval = env.evaluate()
                except Exception as exc:
                    local_eval = {
                        "success": False,
                        "tgc": None,
                        "sgc": None,
                        "goal_pass_rate": None,
                        "report": {"error": str(exc)},
                    }
                emit(
                    step=step,
                    actor="environment",
                    event_type="evaluate",
                    payload={**dict(local_eval), "horizon": "local"},
                    env_state_hash=env.snapshot_hash(),
                )

            force_review = False
            skip_scheduled = bool(
                prefix is not None and prefix.skip_review_at_start and step == start_step
            )
            if (
                prefix is not None
                and prefix.skip_next_scheduled_review
                and next_scheduled_review_step(start_step, policy.review_every_k) == step
            ):
                skip_scheduled = True
            if packet is not None and not policy.planner_drives:
                if (
                    policy.review_every_k
                    and policy.review_every_k > 0
                    and step % policy.review_every_k == 0
                    and not skip_scheduled
                ):
                    force_review = True
                if router is not None and router.should_escalate(trajectory_state(step)):
                    force_review = True
                if step in policy.oracle_steps:
                    force_review = True
            if (
                prefix is not None
                and prefix.inject_correction is not None
                and step == start_step
            ):
                n_interventions += 1
                correction = prefix.inject_correction
                emit(
                    step=step,
                    actor="planner",
                    event_type="intervention",
                    payload={
                        "n_interventions": n_interventions,
                        "correction": correction,
                        "forced": True,
                        "source": "replayed_focal",
                    },
                )
                transcript.append(f"INTERVENTION: {correction}")
                exec_turns.append({"role": "user", "content": f"INTERVENTION: {correction}"})
            elif force_review and packet is not None:
                if policy.takeover:
                    joined = "\n".join(transcript)
                    resp = call_planner(
                        "act",
                        lambda: planner.act(
                            task_id,
                            joined,
                            timeout_s=timeout_s,
                            allow_handoff=policy.handoff_allowed,
                        ),
                        step,
                    )
                    if resp is None:
                        break
                    forced_action = action_from_planner(resp, step, fatal_parse=False)
                    if forced_action is not None:
                        n_planner_actions += 1
                        emit(
                            step=step,
                            actor="planner",
                            event_type="action",
                            payload=forced_action.model_dump(),
                            usage=resp.usage,
                            env_state_hash=env.snapshot_hash(),
                        )
                    if over_token_limit():
                        error_type = "limit"
                        emit(
                            step=step,
                            actor="system",
                            event_type="error",
                            payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                            error="limit",
                        )
                        break
                elif policy.advice_from_act:
                    # Same call as the takeover branch above, argument for argument, so the
                    # planner sees an identical prompt. Only the delivery differs: the parsed
                    # action is shown to the executor as text and never reaches env.step.
                    # An unparseable reply shows nothing, exactly as takeover then executes
                    # nothing (action_from_planner has already logged it with its usage).
                    joined = "\n".join(transcript)
                    resp = call_planner(
                        "act",
                        lambda: planner.act(
                            task_id,
                            joined,
                            timeout_s=timeout_s,
                            allow_handoff=policy.handoff_allowed,
                        ),
                        step,
                    )
                    if resp is None:
                        break
                    shown_action = action_from_planner(resp, step, fatal_parse=False)
                    if shown_action is not None:
                        n_interventions += 1
                        correction = format_executor_action(shown_action)
                        shown_payload: dict[str, Any] = {
                            "n_interventions": n_interventions,
                            "correction": correction,
                            "forced": True,
                            "source": "shown_action",
                            "shown_kind": shown_action.kind,
                        }
                        emit(
                            step=step,
                            actor="planner",
                            event_type="intervention",
                            payload=shown_payload,
                            usage=resp.usage,
                        )
                        transcript.append(f"INTERVENTION: {correction}")
                        exec_turns.append({"role": "user", "content": f"INTERVENTION: {correction}"})
                    if over_token_limit():
                        error_type = "limit"
                        emit(
                            step=step,
                            actor="system",
                            event_type="error",
                            payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                            error="limit",
                        )
                        break
                else:
                    n_ctx = policy.correct_context_lines
                    if n_ctx is None:
                        delta_lines = transcript
                    elif n_ctx == 0:
                        delta_lines = []
                    else:
                        delta_lines = transcript[-n_ctx:]
                    delta = "\n".join(delta_lines)
                    resp = call_planner(
                        "correct",
                        lambda: planner.correct(packet, delta, timeout_s=timeout_s),
                        step,
                    )
                    if resp is None:
                        break
                    n_interventions += 1
                    correction = resp.correction or resp.raw_output
                    live_payload: dict[str, Any] = {
                        "n_interventions": n_interventions,
                        "correction": correction,
                        "forced": True,
                    }
                    if prefix is not None:
                        live_payload["source"] = "live_policy"
                    emit(
                        step=step,
                        actor="planner",
                        event_type="intervention",
                        payload=live_payload,
                        usage=resp.usage,
                    )
                    transcript.append(f"INTERVENTION: {correction}")
                    exec_turns.append({"role": "user", "content": f"INTERVENTION: {correction}"})
                    if over_token_limit():
                        error_type = "limit"
                        emit(
                            step=step,
                            actor="system",
                            event_type="error",
                            payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                            error="limit",
                        )
                        break

            if driver_is_planner:
                joined = "\n".join(transcript)
                resp = call_planner(
                    "act",
                    lambda: planner.act(
                        task_id,
                        joined,
                        timeout_s=timeout_s,
                        allow_handoff=policy.handoff_allowed,
                    ),
                    step,
                )
                if resp is None:
                    break
                action = action_from_planner(resp, step)
                if action is None:
                    break
                if action.kind == "HANDOFF":
                    # The handoff consumes the step index — episodes average 14
                    # steps against a 40 cap, so it costs nothing real, and the
                    # alternative re-entrancy is not worth the complexity.
                    handoff_step = step
                    driver_is_planner = False
                    emit(
                        step=step,
                        actor="planner",
                        event_type="handoff",
                        payload=action.model_dump(),
                        usage=resp.usage,
                        env_state_hash=env.snapshot_hash(),
                    )
                    continue
                emit(
                    step=step,
                    actor="planner",
                    event_type="action",
                    payload=action.model_dump(),
                    usage=resp.usage,
                    env_state_hash=env.snapshot_hash(),
                )
            else:
                action = forced_action if forced_action is not None else action_from_executor(step)
                if action is None:
                    break
                if prefix_terminal and forced_action is None:
                    n_post_terminal_actions += 1
                if policy.review_proposed_action and forced_action is None:
                    action = run_action_review(
                        action=action,
                        step=step,
                        packet=packet,
                        policy=policy,
                        verifier=verifier,
                        trajectory_state=trajectory_state(step),
                        transcript=transcript,
                        planner=planner,
                        timeout_s=timeout_s,
                        call_planner=call_planner,
                        emit=emit,
                        task_id=task_id,
                    )
                    if action is None:
                        break
                    if over_token_limit():
                        error_type = "limit"
                        emit(
                            step=step,
                            actor="system",
                            event_type="error",
                            payload={"limit": "max_tokens_per_episode", "episode_tokens": episode_tokens},
                            error="limit",
                        )
                        break

            last_action = action

            if action.kind == "ASK_PLANNER":
                allow = policy.allow_executor_ask and packet is not None
                gated = False
                self_gated = policy.gate_ask_with_verifier and isinstance(verifier, SelfVerifier)
                if allow and policy.gate_ask_with_verifier:
                    v = verifier or ConstantVerifier()
                    if not (v.score(trajectory_state(step)) > policy.verifier_threshold):
                        allow = False
                        gated = True
                if allow and packet is not None:
                    n_asks += 1
                    emit(
                        step=step,
                        actor="executor",
                        event_type="ask",
                        payload={
                            "n_asks": n_asks,
                            "ask_reason": action.ask_reason,
                            "gated": False,
                            **p_ask_event_fields(),
                        },
                        env_state_hash=env.snapshot_hash(),
                    )
                    delta = "\n".join(transcript[-8:] + [f"ASK: {action.ask_reason}"])
                    resp = call_planner(
                        "correct",
                        lambda: planner.correct(packet, delta, timeout_s=timeout_s),
                        step,
                    )
                    if resp is None:
                        break
                    answer = resp.correction or resp.raw_output
                    emit(
                        step=step,
                        actor="planner",
                        event_type="intervention",
                        payload={"n_asks": n_asks, "correction": answer, "forced": False},
                        usage=resp.usage,
                    )
                    transcript.append(f"ASK: {action.ask_reason}")
                    transcript.append(f"ANSWER: {answer}")
                    exec_turns.append({"role": "assistant", "content": format_executor_action(action)})
                    exec_turns.append({"role": "user", "content": f"ANSWER: {answer}"})
                    continue
                if gated and self_gated:
                    emit(
                        step=step,
                        actor="executor",
                        event_type="ask",
                        payload={
                            "ask_reason": action.ask_reason,
                            "gated": True,
                            "honoured": False,
                            "redecode": True,
                            **p_ask_event_fields(),
                        },
                        env_state_hash=env.snapshot_hash(),
                    )
                    retry = action_from_executor(step, ban_ask_prefix=True)
                    if retry is None:
                        break
                    last_action = retry
                    if retry.kind != "ASK_PLANNER":
                        action = retry
                    else:
                        transcript.append(f"ASK_IGNORED: {retry.ask_reason}")
                        exec_turns.append({"role": "assistant", "content": format_executor_action(retry)})
                        exec_turns.append({"role": "user", "content": "ASK_IGNORED"})
                        continue
                else:
                    emit(
                        step=step,
                        actor="executor",
                        event_type="ask",
                        payload={
                            "ask_reason": action.ask_reason,
                            "gated": gated,
                            "honoured": False,
                            **p_ask_event_fields(),
                        },
                        env_state_hash=env.snapshot_hash(),
                    )
                    transcript.append(f"ASK_IGNORED: {action.ask_reason}")
                    exec_turns.append({"role": "assistant", "content": format_executor_action(action)})
                    exec_turns.append({"role": "user", "content": "ASK_IGNORED"})
                    continue

            if action.kind == "REPORT":
                emit(
                    step=step,
                    actor="executor",
                    event_type="report",
                    payload={"message": action.message},
                    env_state_hash=env.snapshot_hash(),
                )
                transcript.append(f"REPORT: {action.message}")
                exec_turns.append({"role": "assistant", "content": format_executor_action(action)})
                continue

            if action.kind in ("CODE", "COMPLETE"):
                try:
                    last_obs = call_with_timeout(lambda: env.step(action), timeout_s)
                except TimeoutError as exc:
                    error_type = "timeout"
                    emit(
                        step=step,
                        actor="environment",
                        event_type="error",
                        payload={"detail": str(exc)},
                        error="timeout",
                    )
                    break
                emit(
                    step=step,
                    actor="environment",
                    event_type="observation",
                    payload={
                        "text": last_obs.text,
                        "done": last_obs.done,
                        "kind": action.kind,
                    },
                    env_state_hash=last_obs.env_state_hash,
                    error=last_obs.error_type,
                )
                exec_turns.append({"role": "assistant", "content": format_executor_action(action)})
                transcript.append(f"OBS: {last_obs.text}")
                exec_turns.append({"role": "user", "content": f"OBS: {last_obs.text}"})
                if action.kind == "COMPLETE" or last_obs.done:
                    break
            else:
                transcript.append(f"ACTION: {action.kind}")
        else:
            if error_type is None and not skip_live_loop:
                error_type = "limit"
                emit(
                    step=steps_taken,
                    actor="system",
                    event_type="error",
                    payload={"limit": "max_steps", "max_steps": limits.max_steps},
                    error="limit",
                )

        try:
            eval_result = env.evaluate()
        except Exception as exc:
            eval_result = {
                "success": False,
                "tgc": None,
                "sgc": None,
                "goal_pass_rate": None,
                "report": {"error": str(exc)},
            }
            if error_type is None:
                error_type = "crash"
        emit(
            step=steps_taken,
            actor="environment",
            event_type="evaluate",
            payload=dict(eval_result),
            env_state_hash=env.snapshot_hash(),
        )
    except Exception as exc:
        if error_type is None:
            error_type = "crash"
        emit(
            step=steps_taken,
            actor="system",
            event_type="error",
            payload={"detail": str(exc), "exc_type": type(exc).__name__},
            error="crash",
        )
    finally:
        env.close()

    success = bool(eval_result.get("success")) and error_type is None
    result = RunResult(
        run_id=log.run_id,
        task_id=task_id,
        system=name,
        seed=seed,
        success=success,
        tgc=eval_result.get("tgc"),
        sgc=eval_result.get("sgc"),
        goal_pass_rate=eval_result.get("goal_pass_rate"),
        steps=steps_taken,
        n_planner_calls=n_planner_calls,
        n_asks=n_asks,
        n_interventions=n_interventions,
        error_type=error_type,
        totals=ledger.totals(),
    )
    end_payload = result.model_dump()
    end_payload["n_planner_actions"] = n_planner_actions
    end_payload["handoff_step"] = handoff_step
    if prefix is not None:
        end_payload["n_post_terminal_actions"] = n_post_terminal_actions
    emit(
        step=steps_taken,
        actor="system",
        event_type="run_end",
        payload=end_payload,
        env_state_hash=env.snapshot_hash() if not getattr(env, "_closed", False) else None,
        error=error_type,
    )
    return result



def _client_model_id(client: Any, fallback: str) -> str:
    """Model id to stamp on the bookkeeping Usage of a FAILED client call.

    Prefer the configured model, then the client model, over the client CLASS name.
    `getattr(client, "name")` can be "codex-exec" or "vllm-executor", and
    `campaign_summarize` reads `usage.model` as model provenance -- so a class name
    there makes the gate report "the wrong model ran" for an arm that ran the right
    one. The fallback keeps mock clients without model metadata usable.
    """
    model = getattr(getattr(client, "config", None), "model", None)
    return model or getattr(client, "model", None) or getattr(client, "name", None) or fallback


def _plan_event_fields(raw: dict[str, Any]) -> dict[str, Any]:
    """Plan-event payload fields a planner left on its usage.raw: the source task of the WTP
    control (src/sidekick/agents/packet_remap.py), and nothing for any other planner, so every
    other arm's plan event keeps its shape. It lives at the end of the file, and is imported
    here rather than at the top, so that no line this file's citations name moves."""
    from sidekick.agents.packet_remap import plan_event_fields

    return plan_event_fields(raw)
