"""prefix_handoff: replay the planner's first m executed steps, then executor suffix."""
from __future__ import annotations

from typing import Any

from sidekick.environments.base import BaseEnv
from sidekick.prefix_source import HandoffPrefix, build_handoff_prefix
from sidekick.protocols.schemas import Event, RunResult, utc_now_iso
from sidekick.systems.loop import ConfigurableSystem, EpisodePrefix, RunLimits, SystemPolicy
from sidekick.trajectories.eventlog import EventLog


class _AfterRunStartLog:
    """Insert one extra event immediately after the first ``run_start``.

    The handoff record has to live in the last-attempt slice (after ``run_start``)
    so analysis that starts at the last ``run_start`` still sees it, and it has
    to be written before the live suffix loop records actions.
    """

    def __init__(self, log: EventLog, extra: Event) -> None:
        self._log = log
        self._extra = extra
        self._injected = False

    @property
    def run_id(self) -> str:
        return self._log.run_id

    def append(self, event: Event) -> None:
        self._log.append(event)
        if not self._injected and event.event_type == "run_start":
            self._log.append(self._extra)
            self._injected = True


class PrefixHandoff(ConfigurableSystem):
    name = "prefix_handoff"
    policy_defaults = SystemPolicy(
        plan_first=True,
        planner_drives=False,
        allow_executor_ask=True,
        review_every_k=None,
        use_router=False,
        gate_ask_with_verifier=False,
        adapter_name="sft_plan",
    )

    def __init__(
        self,
        planner: Any,
        executor: Any | None = None,
        verifier: Any | None = None,
        limits: RunLimits | None = None,
        policy: SystemPolicy | None = None,
        source_campaign: str | None = None,
        source_system: str = "planner_alone",
        m: int = 0,
        adapter_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.source_campaign = source_campaign
        self.source_system = source_system
        self.m = int(m)
        if adapter_name is not None:
            kwargs["adapter_name"] = adapter_name
        super().__init__(planner, executor=executor, verifier=verifier, limits=limits, policy=policy, **kwargs)

    def _event(
        self,
        log: EventLog,
        task_id: str,
        seed: int,
        *,
        step: int,
        actor: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        error: str | None = None,
        env_state_hash: str | None = None,
    ) -> Event:
        return Event(
            run_id=log.run_id,
            task_id=task_id,
            system=self.name,
            seed=seed,
            step=step,
            ts=utc_now_iso(),
            actor=actor,  # type: ignore[arg-type]
            event_type=event_type,  # type: ignore[arg-type]
            payload=payload or {},
            env_state_hash=env_state_hash,
            error_type=error,
        )

    def _broken_result(
        self,
        env: BaseEnv,
        task_id: str,
        seed: int,
        log: EventLog,
        ledger: Any,
        built: HandoffPrefix,
    ) -> RunResult:
        payload = {
            "reason": built.broken_reason,
            "detail": "; ".join(built.notes) if built.notes else built.broken_reason,
            "source_campaign": str(self.source_campaign) if self.source_campaign else "",
            "effective_m": built.effective_m,
            "n_source_actions": built.n_source_actions,
            "handoff_occurred": built.handoff_occurred,
            "hash_ok": built.hash_ok,
            "replayed_planner_tokens": built.replayed_planner_tokens,
        }
        log.append(
            self._event(
                log,
                task_id,
                seed,
                step=built.effective_m,
                actor="system",
                event_type="error",
                payload=payload,
                error="crash",
            )
        )
        try:
            env.close()
        except Exception:
            pass
        return RunResult(
            run_id=log.run_id,
            task_id=task_id,
            system=self.name,
            seed=seed,
            success=False,
            error_type="crash",
            totals=ledger.totals(),
        )

    def run(
        self,
        env: BaseEnv,
        task_id: str,
        seed: int,
        log: EventLog,
        ledger: Any,
        prefix: EpisodePrefix | None = None,
    ) -> RunResult:
        # Unconfigured (no source_campaign): behave like sft_plan so SYSTEM_NAMES
        # iteration tests still complete. A configured but missing path is broken.
        if not self.source_campaign:
            return super().run(env, task_id, seed, log, ledger, prefix=prefix)

        built = build_handoff_prefix(
            self.source_campaign,
            self.source_system,
            task_id,
            seed,
            self.m,
            env,
        )
        if built.broken_reason is not None:
            return self._broken_result(built.env, task_id, seed, log, ledger, built)

        # event_type="report": closed EventType; run_start is emitted by
        # run_episode; intervention would confound n_interventions; error is the
        # broken path. actor="system" distinguishes this from executor REPORT.
        extra = self._event(
            log,
            task_id,
            seed,
            step=built.effective_m,
            actor="system",
            event_type="report",
            payload={
                "effective_m": built.effective_m,
                "n_source_actions": built.n_source_actions,
                "handoff_occurred": built.handoff_occurred,
                "hash_ok": built.hash_ok,
                "replayed_planner_tokens": built.replayed_planner_tokens,
                "source_campaign": str(self.source_campaign),
            },
            env_state_hash=built.env.snapshot_hash(),
        )
        wrapped = _AfterRunStartLog(log, extra)
        return super().run(built.env, task_id, seed, wrapped, ledger, prefix=built.prefix)
