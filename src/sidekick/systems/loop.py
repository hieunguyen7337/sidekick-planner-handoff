"""Shared episode loop and run limits. All eight systems call this."""
from __future__ import annotations

import signal
from dataclasses import dataclass, replace
from typing import Any, Callable, Optional

from sidekick.agents.planner import CodexTimeoutError, PacketParseError, PlannerClient
from sidekick.agents.verifier import ConstantVerifier, ThresholdRouter, Verifier
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
        overlay = {k: v for k, v in kwargs.items() if hasattr(base, k) and v is not None}
        self.policy = replace(base, **overlay)

    def run(self, env: BaseEnv, task_id: str, seed: int, log: EventLog, ledger: CostLedger) -> RunResult:
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
) -> RunResult:
    n_asks = 0
    n_interventions = 0
    n_planner_calls = 0
    episode_tokens = 0
    error_type: Optional[str] = None
    packet: Optional[DelegationPacket] = None
    last_obs: Optional[Observation] = None
    last_action: Optional[ExecutorAction] = None
    transcript: list[str] = []
    # `transcript` is a frozen wire format for the planner (INSTRUCTION:/PLAN:/OBS:/...).
    # `exec_turns` is the executor's conversation (assistant actions, user observations).
    # The redundancy is deliberate: changing `transcript` would invalidate a running
    # teacher-data campaign and the HJ-1 planner baseline.
    exec_turns: list[dict] = []
    steps_taken = 0
    eval_result: dict[str, Any] = {"success": False, "tgc": None, "sgc": None, "report": {}}
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

    def action_from_planner(resp: PlannerResponse, step: int) -> ExecutorAction | None:
        nonlocal error_type
        if resp.code and resp.code.strip():
            return ExecutorAction(kind="CODE", code=resp.code, raw_output=resp.raw_output or resp.code)
        raw = resp.raw_output or ""
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
            error_type = "parse_error"
            return None

    def action_from_executor(step: int) -> ExecutorAction | None:
        nonlocal error_type
        if executor is None:
            error_type = "crash"
            emit(step=step, actor="system", event_type="error", payload={"detail": "no executor"}, error="crash")
            return None
        messages = render_executor_messages(
            instruction=env.instruction,
            api_docs=env.api_docs_prompt,
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
                text, usage = call_with_timeout(
                    lambda: executor.complete(
                        messages,
                        lora_name=policy.adapter_name,
                        task_id=task_id,
                    ),
                    timeout_s,
                )
            except TimeoutError as exc:
                usage = Usage(
                    model=_client_model_id(executor, "executor"),
                    provider="mock",
                    n_calls=1,
                    raw={"error_type": "timeout"},
                )
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
        emit(
            step=step,
            actor="executor",
            event_type="action",
            payload=action.model_dump(),
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
        }

    try:
        last_obs = env.reset(task_id, seed)
        transcript.append(f"INSTRUCTION: {env.instruction}")
        emit(
            step=0,
            actor="system",
            event_type="run_start",
            payload={
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
            },
            env_state_hash=last_obs.env_state_hash,
        )
        emit(
            step=0,
            actor="environment",
            event_type="observation",
            payload={"text": last_obs.text, "done": last_obs.done},
            env_state_hash=last_obs.env_state_hash,
        )

        if policy.plan_first:
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
                        "thread_id": resp.thread_id,
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

        for step in range(1, limits.max_steps + 1):
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

            force_review = False
            if packet is not None and not policy.planner_drives:
                if policy.review_every_k and policy.review_every_k > 0 and step % policy.review_every_k == 0:
                    force_review = True
                if router is not None and router.should_escalate(trajectory_state(step)):
                    force_review = True
                if step in policy.oracle_steps:
                    force_review = True
            if force_review and packet is not None:
                delta = "\n".join(transcript[-8:])
                resp = call_planner(
                    "correct",
                    lambda: planner.correct(packet, delta, timeout_s=timeout_s),
                    step,
                )
                if resp is None:
                    break
                n_interventions += 1
                correction = resp.correction or resp.raw_output
                emit(
                    step=step,
                    actor="planner",
                    event_type="intervention",
                    payload={"n_interventions": n_interventions, "correction": correction, "forced": True},
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

            if policy.planner_drives:
                joined = "\n".join(transcript)
                resp = call_planner(
                    "act",
                    lambda: planner.act(task_id, joined, timeout_s=timeout_s),
                    step,
                )
                if resp is None:
                    break
                action = action_from_planner(resp, step)
                if action is None:
                    break
                emit(
                    step=step,
                    actor="planner",
                    event_type="action",
                    payload=action.model_dump(),
                    usage=resp.usage,
                    env_state_hash=env.snapshot_hash(),
                )
            else:
                action = action_from_executor(step)
                if action is None:
                    break

            last_action = action

            if action.kind == "ASK_PLANNER":
                allow = policy.allow_executor_ask and packet is not None
                gated = False
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
                emit(
                    step=step,
                    actor="executor",
                    event_type="ask",
                    payload={"ask_reason": action.ask_reason, "gated": gated, "honoured": False},
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
            if error_type is None:
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
            eval_result = {"success": False, "tgc": None, "sgc": None, "report": {"error": str(exc)}}
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
        steps=steps_taken,
        n_planner_calls=n_planner_calls,
        n_asks=n_asks,
        n_interventions=n_interventions,
        error_type=error_type,
        totals=ledger.totals(),
    )
    emit(
        step=steps_taken,
        actor="system",
        event_type="run_end",
        payload=result.model_dump(),
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
