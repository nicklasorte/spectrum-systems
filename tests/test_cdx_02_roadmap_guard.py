from __future__ import annotations

import json
from pathlib import Path

from spectrum_systems.modules.governance.cdx_02_roadmap_guard import evaluate_cdx_02_roadmap_guard


REPO_ROOT = Path(__file__).resolve().parents[1]
ROADMAP_PATH = REPO_ROOT / "docs" / "governance" / "cdx_02_3ls_roadmap.json"


def test_cdx_02_roadmap_guard_passes_for_repo_state() -> None:
    result = evaluate_cdx_02_roadmap_guard(repo_root=REPO_ROOT)
    assert result["status"] == "PASS"
    assert result["violations"] == []


def test_cdx_02_roadmap_has_exact_step_owner_mapping() -> None:
    roadmap = json.loads(ROADMAP_PATH.read_text(encoding="utf-8"))
    ids = [item["id"] for item in roadmap["steps"]]
    assert ids == [f"3LS-{idx:02d}" for idx in range(1, 45)]
    assert all(item["owner"] for item in roadmap["steps"])


def test_cdx_02_new_owners_are_restricted() -> None:
    roadmap = json.loads(ROADMAP_PATH.read_text(encoding="utf-8"))
    flagged = {item["owner"] for item in roadmap["steps"] if item.get("new_owner")}
    assert flagged == {"CRS", "MGV"}


def test_cdx_02_authority_source_is_canonical_registry() -> None:
    roadmap = json.loads(ROADMAP_PATH.read_text(encoding="utf-8"))
    assert roadmap["authority_source"] == "docs/architecture/system_registry.md"
