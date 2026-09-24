"""Write data/bfcl_split_20260924.json: the seeded dev 50 / test 150 split of BFCL multi_turn_base.

Ids and the seed only. Unstratified, because docs/second_env_scoping_20260923.md names no stratum.
tests/unit/test_bfcl_env.py checks the committed file equals what this writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sidekick.environments.bfcl_env import DEFAULT_SPLIT_PATH, N_DEV, SPLIT_SEED, build_split, load_entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/setup/bfcl_split.py")
    parser.add_argument("--out", default=str(DEFAULT_SPLIT_PATH))
    parser.add_argument("--seed", type=int, default=SPLIT_SEED)
    args = parser.parse_args(argv)
    split = build_split(list(load_entries()), seed=args.seed, n_dev=N_DEV)
    Path(args.out).write_text(json.dumps(split, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: split[k] for k in ("category", "seed", "n_dev", "n_test")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
