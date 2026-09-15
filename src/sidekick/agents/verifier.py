"""Verifier stub and a threshold router."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class Verifier(Protocol):
    def score(self, trajectory_state: Any) -> float: ...


@dataclass
class ConstantVerifier:
    """Stub verifier. A trained multi-head model replaces this later."""

    value: float = 0.5

    def score(self, trajectory_state: Any) -> float:
        return float(self.value)


@dataclass
class ScriptedVerifier:
    """Returns scores in order, then repeats the last value."""

    scores: list[float] = field(default_factory=lambda: [0.5])
    _i: int = 0

    def score(self, trajectory_state: Any) -> float:
        if not self.scores:
            return 0.5
        if self._i >= len(self.scores):
            return float(self.scores[-1])
        value = float(self.scores[self._i])
        self._i += 1
        return value


@dataclass
class ThresholdRouter:
    """Escalate when ``verifier.score(state) > threshold`` (strict greater-than)."""

    verifier: Verifier
    threshold: float = 0.5

    def should_escalate(self, trajectory_state: Any) -> bool:
        return self.verifier.score(trajectory_state) > self.threshold
