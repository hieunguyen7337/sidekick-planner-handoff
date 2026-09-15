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
    def api_docs_digest(self) -> str:
        """sha256 fingerprint of the API surface, for manifests. NOT for prompts."""

    @property
    def api_docs_prompt(self) -> str:
        """Model-readable listing of the available APIs, for the prompt prefix.

        Concrete rather than abstract so existing environments keep working; an env
        that returns "" simply tells the model nothing about its API surface, which
        is what every arm did before 2026-09-15 and why they all scored zero.
        """
        return ""
