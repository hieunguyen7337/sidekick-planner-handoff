"""verify_configs: a registered upstream packet source may be pending, but only while absent."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "verify_configs", Path(__file__).resolve().parents[2] / "scripts" / "setup" / "verify_configs.py"
)
verify_configs = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify_configs)  # type: ignore[union-attr]


def test_no_declared_reason_means_the_source_must_resolve_now(tmp_path: Path):
    cfg = {"packet_source": str(tmp_path / "absent")}
    assert verify_configs.pending_packet_source(cfg) is None


def test_a_declared_reason_exempts_an_absent_source(tmp_path: Path):
    cfg = {"packet_source": str(tmp_path / "absent"), "packet_source_pending": "arm 3 not run"}
    assert verify_configs.pending_packet_source(cfg) == "arm 3 not run"


def test_the_exemption_lapses_once_the_upstream_arm_has_written_the_source(tmp_path: Path):
    produced = tmp_path / "produced"
    produced.mkdir()
    cfg = {"packet_source": str(produced), "packet_source_pending": "arm 3 not run"}
    assert verify_configs.pending_packet_source(cfg) is None


def test_a_blank_reason_is_not_an_exemption(tmp_path: Path):
    cfg = {"packet_source": str(tmp_path / "absent"), "packet_source_pending": "   "}
    assert verify_configs.pending_packet_source(cfg) is None
