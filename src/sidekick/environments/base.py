"""Environment ABC for Sidekick systems."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sidekick.protocols.schemas import ExecutorAction, Observation


class BaseEnv(ABC):
    @abstractmethod
    def reset(self, task_id: str, seed: int) -> Observation: ...

    @abstractmethod
    def step(self, action: ExecutorAction) -> Observation: ...

    @abstractmethod
    def evaluate(self) -> dict: ...

    @abstractmethod
    def snapshot_hash(self) -> str: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def instruction(self) -> str: ...

    @property
    @abstractmethod
    def api_docs_digest(self) -> str: ...
