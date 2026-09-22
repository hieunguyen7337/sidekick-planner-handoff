#!/usr/bin/env python3
"""CLI for suffix-handoff SFT JSONL. Training itself is scripts/pbs/train_sft.pbs."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from sidekick.training.handoff_sft import main

if __name__ == "__main__":
    raise SystemExit(main())
