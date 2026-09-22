# Status X31 — Database State Consistency in Replay

## Overview
Work in progress for brief X31.
Initial assessment:
- `src/sidekick/replay.py` inspects `env_state_hash`, which represents observation history (`environment_io`), not the underlying database dump.
- Investigating direct AppWorld DB inspection mechanisms.
