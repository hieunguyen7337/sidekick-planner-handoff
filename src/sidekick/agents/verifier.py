"""Verifier stub and a threshold router."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
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


# ---------------------------------------------------------------------------
# FeatureVerifier — logistic regression over features of trajectory_state.
#
# Frozen feature spec (feature_lr_v1). The extractor may use ONLY the keys
# produced by loop.trajectory_state (loop.py:492-500): step, transcript,
# last_action, last_observation, n_asks, n_interventions. Everything else is
# derived from the transcript string, whose lines are INSTRUCTION:/PLAN:/OBS:/
# INTERVENTION:/ANSWER:/ASK_IGNORED (and REPORT:/ASK: internal prefixes).
# Do not add fields to trajectory_state: W-5 owns loop.py this cycle.
# ---------------------------------------------------------------------------

FEATURE_SPEC_VERSION = "feature_lr_v1"

ACTION_KINDS = ("CODE", "REPORT", "ASK_PLANNER", "COMPLETE")  # NONE -> all zeros

# Attribute-chain call names in the transcript (from PLAN/INTERVENTION text and
# code echoed inside OBS tracebacks). Requires >= one dot so bare builtins
# (print, len, ...) never match.
_API_CALL_RE = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(")

# An access token in the transcript: access_token/bearer followed by a long
# credential-looking string.
_TOKEN_RE = re.compile(
    r"(?i)\b(access[_-]?token|bearer[_-]?token|api[_-]?key)\b\W*[:=]?\W*"
    r"[A-Za-z0-9_\-\.]{8,}"
)

_TRACEBACK_MARKERS = (
    "Traceback (most recent call last):",
    "SyntaxError",
    "NameError",
    "TypeError",
    "ValueError",
    "KeyError",
    "AttributeError",
    "IndexError",
    "ZeroDivisionError",
    "Exception:",
    "Error:",
)


def feature_spec() -> dict[str, Any]:
    """The frozen, ordered, named feature spec (also written to JSON by fit)."""
    features: list[dict[str, Any]] = [
        {"name": "step", "transform": "passthrough", "columns": ["step"]},
        {"name": "n_interventions", "transform": "passthrough", "columns": ["n_interventions"]},
        {"name": "n_asks", "transform": "passthrough", "columns": ["n_asks"]},
        {"name": "last_obs_is_error", "transform": "binary", "columns": ["last_obs_is_error"]},
        {
            "name": "consecutive_error_run",
            "transform": "count",
            "columns": ["consecutive_error_run"],
        },
        {"name": "last_action_repeat", "transform": "binary", "columns": ["last_action_repeat"]},
        {"name": "distinct_apis", "transform": "count", "columns": ["distinct_apis"]},
        {"name": "token_leak", "transform": "binary", "columns": ["token_leak"]},
        {"name": "transcript_chars", "transform": "count", "columns": ["transcript_chars"]},
        {
            "name": "last_action_kind",
            "transform": "onehot",
            "categories": list(ACTION_KINDS),
            "columns": [f"last_action_kind_{k}" for k in ACTION_KINDS],
        },
    ]
    columns = [c for f in features for c in f["columns"]]
    return {"version": FEATURE_SPEC_VERSION, "features": features, "columns": columns}


def _normalize_text(text: Any) -> str:
    return " ".join(str(text or "").split())


def _is_error_observation(last_observation: Any) -> bool:
    """True when the last observation is an error or contains a traceback."""
    if not isinstance(last_observation, dict):
        return False
    if last_observation.get("error_type") is not None:
        return True
    text = str(last_observation.get("text") or "")
    return any(marker in text for marker in _TRACEBACK_MARKERS)


def _extractor_features(state: dict[str, Any]) -> dict[str, float]:
    transcript = str(state.get("transcript") or "")

    last_observation = state.get("last_observation")
    obs_error = _is_error_observation(last_observation)

    # Consecutive-error run: trailing error OBS lines in the transcript.
    run = 0
    for line in reversed(transcript.split("\n")):
        if not line.startswith("OBS:"):
            continue
        if any(marker in line for marker in _TRACEBACK_MARKERS):
            run += 1
        else:
            break

    last_action = state.get("last_action")
    action_code = ""
    action_kind = "NONE"
    if isinstance(last_action, dict):
        action_kind = str(last_action.get("kind") or "NONE")
        action_code = _normalize_text(last_action.get("code") or last_action.get("message") or "")
    # Approximation: actions are not echoed to the transcript, so "repeats an
    # action seen earlier" is derived as the last action's code/message text
    # appearing anywhere earlier in the transcript (e.g. quoted in a PLAN or
    # INTERVENTION line, or echoed in an OBS traceback).
    repeat = 1.0 if action_code and action_code in transcript else 0.0

    distinct_apis = len({m.group(1) for m in _API_CALL_RE.finditer(transcript)})
    token_leak = 1.0 if _TOKEN_RE.search(transcript) else 0.0

    values: dict[str, float] = {
        "step": float(state.get("step") or 0),
        "n_interventions": float(state.get("n_interventions") or 0),
        "n_asks": float(state.get("n_asks") or 0),
        "last_obs_is_error": 1.0 if obs_error else 0.0,
        "consecutive_error_run": float(run),
        "last_action_repeat": repeat,
        "distinct_apis": float(distinct_apis),
        "token_leak": token_leak,
        "transcript_chars": float(len(transcript)),
    }
    for kind in ACTION_KINDS:
        values[f"last_action_kind_{kind}"] = 1.0 if action_kind == kind else 0.0
    return values

@dataclass
class FeatureVerifier:
    """Logistic-regression verifier over the frozen feature_lr_v1 spec.

    ``weights`` maps column name -> coefficient; ``temperature`` is the dev
    temperature-scaling factor (logit is divided by it). Column names must
    match the spec exactly — a mismatch raises rather than silently scoring.
    """

    weights: dict[str, float]
    intercept: float = 0.0
    temperature: float = 1.0
    spec: dict[str, Any] = field(default_factory=feature_spec)

    def __post_init__(self) -> None:
        columns = list(self.spec["columns"])
        missing = [c for c in columns if c not in self.weights]
        extra = [c for c in self.weights if c not in columns]
        if missing or extra:
            raise ValueError(
                f"weights/spec column mismatch (missing={missing}, extra={extra}); "
                "a model whose feature order is implied by code rather than "
                "recorded silently mis-scores when the extractor is reordered"
            )
        self._ordered = list(columns)
        self._w = [float(self.weights[c]) for c in self._ordered]
        temp = float(self.temperature)
        self._temperature = temp if temp > 0 else 1.0

    def features(self, trajectory_state: Any) -> dict[str, float]:
        state = trajectory_state if isinstance(trajectory_state, dict) else {}
        return _extractor_features(state)

    def vector(self, trajectory_state: Any) -> list[float]:
        feats = self.features(trajectory_state)
        return [float(feats[c]) for c in self._ordered]

    def logit(self, trajectory_state: Any) -> float:
        z = self.intercept + sum(w * x for w, x in zip(self._w, self.vector(trajectory_state)))
        return max(-30.0, min(30.0, z))

    def score(self, trajectory_state: Any) -> float:
        return float(1.0 / (1.0 + math.exp(-self.logit(trajectory_state) / self._temperature)))

    @classmethod
    def load(cls, path: str | Path) -> "FeatureVerifier":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            weights={c: float(v) for c, v in data["weights"].items()},
            intercept=float(data.get("intercept", 0.0)),
            temperature=float(data.get("temperature", 1.0)),
            spec=data.get("spec") or feature_spec(),
        )

    def save(self, path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "version": FEATURE_SPEC_VERSION,
                    "spec": self.spec,
                    "columns": self._ordered,
                    "weights": {c: w for c, w in zip(self._ordered, self._w)},
                    "intercept": self.intercept,
                    "temperature": self.temperature,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


@dataclass
class SelfVerifier:
    """Score is the executor's own P(ASK) on the action currently being gated.

    A missing measurement (``p_ask is None``) must not silently deny: ``score``
    returns +inf so the existing strict ``score > threshold`` gate allows the
    ask. A measured ``0.0`` is returned as ``0.0``.
    """

    def score(self, trajectory_state: Any) -> float:
        p_ask = trajectory_state.get("p_ask") if isinstance(trajectory_state, dict) else None
        if p_ask is None:
            return float("inf")
        return float(p_ask)
