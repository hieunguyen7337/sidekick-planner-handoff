"""Training-side helpers, including the split-leakage guard."""

from __future__ import annotations

from typing import Iterable


def assert_no_leakage(train_ids: Iterable[str], heldout_ids: Iterable[str]) -> None:
    """Raise if any held-out task id appears in the training set."""
    train = set(train_ids)
    heldout = set(heldout_ids)
    overlap = sorted(train & heldout)
    if overlap:
        raise ValueError(
            "Split leakage: held-out ids present in training manifest: "
            + ", ".join(overlap)
        )