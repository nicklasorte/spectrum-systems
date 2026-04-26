from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.runtime.rmp.rmp_authority_sync import sync_authority
from spectrum_systems.modules.runtime.rmp.rmp_mirror_validator import validate_markdown_mirror
from spectrum_systems.modules.runtime.rmp.rmp_rfx_bridge import reconcile_rfx_roadmap


def _write(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8")


def test_authority_sync_detects_drift_and_can_fix(tmp_path: Path) -> None:
    authority = {
        "batches": [
            {"batch_id": "TBH-001", "acronym": "TBH", "title": "One", "status": "completed", "depends_on": [], "hard_gate": True},
            {"batch_id": "TBH-002", "acronym": "TBH", "title": "Two", "status": "not_started", "depends_on": ["TBH-001"], "hard_gate": True},
        ]
    }
    a = tmp_path / "authority.json"
    m = tmp_path / "mirror.md"
    _write(a, json.dumps(authority))
    _write(m, "# Spectrum Systems — System Roadmap\n\n| batch_id | acronym | title | status | depends_on | hard_gate |\n| --- | --- | --- | --- | --- | --- |\n| TBH-001-DRIFT |")

    first = sync_authority(a, m)
    assert not first.ok
    assert any(code.startswith("missing_markdown_entry") for code in first.reason_codes)

    fixed = sync_authority(a, m, apply_fixes=True)
    assert fixed.ok
    assert sync_authority(a, m).ok


def test_mirror_validator_and_rfx_bridge(tmp_path: Path) -> None:
    authority = {"batches": [{"batch_id": "LOOP-09", "acronym": "RFX", "title": "Fix", "status": "not_started", "depends_on": ["LOOP-08"], "hard_gate": True}]}
    a = tmp_path / "authority.json"
    m = tmp_path / "mirror.md"
    rfx = tmp_path / "rfx.md"
    _write(a, json.dumps(authority))
    _write(
        m,
        "\n".join(
            [
                "# Spectrum Systems — System Roadmap",
                "- System source of truth (machine-readable): `contracts/examples/system_roadmap.json`",
                "| batch_id | acronym | title | status | depends_on | hard_gate |",
                "| --- | --- | --- | --- | --- | --- |",
                "| LOOP-09 | RFX | Fix | not_started | LOOP-08 | true |",
            ]
        ),
    )
    _write(rfx, "| LOOP-09 | planned |\n| LOOP-10 | planned |")

    mirror = validate_markdown_mirror(a, m)
    assert mirror["ok"]

    bridge = reconcile_rfx_roadmap(rfx, {"LOOP-09", "LOOP-10"})
    assert bridge["ok"]
