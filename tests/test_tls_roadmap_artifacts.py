from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TLS_DIR = REPO_ROOT / "artifacts" / "tls"
INITIAL_PATH = TLS_DIR / "tls_roadmap_initial.json"
REDTEAM_PATH = TLS_DIR / "tls_roadmap_redteam_report.json"
FIXED_PATH = TLS_DIR / "tls_roadmap_fixed.json"
FINAL_PATH = TLS_DIR / "tls_roadmap_final.json"

REQUIRED_ENTRY_FIELDS = {
    "id",
    "title",
    "purpose",
    "what_it_builds",
    "why_it_matters",
    "dependencies",
    "failure_modes_prevented",
    "artifacts_created",
    "tests_required",
    "acceptance_criteria",
    "authority_owner",
    "execution_scope",
    "safe_prompt_scope",
}
FORBIDDEN_AUTHORITY_VOCAB = ("decision", "enforcement", "approval", "certification", "promotion")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry_map(path: Path) -> dict[str, dict]:
    payload = _load(path)
    return {entry["id"]: entry for entry in payload["entries"]}


def test_roadmap_entries_complete() -> None:
    payload = _load(INITIAL_PATH)
    for entry in payload["entries"]:
        missing = REQUIRED_ENTRY_FIELDS - set(entry)
        assert not missing, f"{entry.get('id')} missing fields: {sorted(missing)}"
        assert entry["tests_required"], f"{entry['id']} must declare tests_required"
        assert entry["acceptance_criteria"], f"{entry['id']} must declare acceptance_criteria"


def test_initial_entries_are_complete() -> None:
    payload = _load(INITIAL_PATH)
    ids = {entry["id"] for entry in payload["entries"]}
    expected = {
        "TLS-RM-10",
        "TLS-RM-11",
        "TLS-RM-12",
        "TLS-RM-13",
        "TLS-RM-14",
        "TLS-RM-15",
        "TLS-RM-16",
        "TLS-RM-17",
        "TLS-RM-18",
        "TLS-RM-19",
        "TLS-RM-20",
    }
    assert ids == expected


def test_no_authority_boundary_violations_in_artifacts() -> None:
    for path in (INITIAL_PATH, REDTEAM_PATH, FIXED_PATH, FINAL_PATH):
        lowered = path.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_AUTHORITY_VOCAB:
            assert token not in lowered, f"forbidden authority token '{token}' found in {path}"


def test_no_oversized_bundles_in_final() -> None:
    payload = _load(FINAL_PATH)
    for bundle in payload["safe_bundles"]:
        assert 1 <= len(bundle["steps"]) <= 3, f"bundle too large: {bundle['bundle_id']}"


def test_redteam_fix_pairing_exists() -> None:
    entries = _load(FIXED_PATH)["entries"]
    ids = [entry["id"] for entry in entries]
    redteams = [eid for eid in ids if eid.startswith("TLS-RT-")]
    fixes = {eid for eid in ids if eid.startswith("TLS-FIX-")}
    for redteam_id in redteams:
        suffix = redteam_id.split("TLS-RT-")[1]
        assert f"TLS-FIX-{suffix}" in fixes, f"missing fix pair for {redteam_id}"


def test_deterministic_ordering() -> None:
    fixed = _load(FIXED_PATH)
    final = _load(FINAL_PATH)
    order = [entry["id"] for entry in fixed["entries"]]
    assert fixed["ordering"] == "deterministic_id_ascending"
    assert len(order) == len(set(order)), "fixed roadmap ids must be unique"
    assert final["recommended_execution_order"] == order


def test_no_step_depends_on_missing_artifacts() -> None:
    initial_ids = set(_entry_map(INITIAL_PATH))
    fixed_ids = set(_entry_map(FIXED_PATH))
    final_ids = set(_entry_map(FINAL_PATH))
    known_step_ids = initial_ids | fixed_ids | final_ids

    for path in (INITIAL_PATH, FIXED_PATH, FINAL_PATH):
        payload = _load(path)
        for entry in payload["entries"]:
            for dep in entry["dependencies"]:
                if dep.startswith("artifacts/"):
                    dep_path = REPO_ROOT / dep
                    assert dep_path.exists(), f"{entry['id']} missing dependency artifact: {dep}"
                elif dep.startswith("TLS-"):
                    assert dep in known_step_ids, f"{entry['id']} unknown step dependency: {dep}"


def test_no_dashboard_assumption() -> None:
    for path in (INITIAL_PATH, FIXED_PATH, FINAL_PATH):
        text = path.read_text(encoding="utf-8").lower()
        assert "dashboard logic" not in text
        assert "ui-only" not in text


def test_no_silent_fallback_language() -> None:
    for path in (INITIAL_PATH, FIXED_PATH, FINAL_PATH):
        text = path.read_text(encoding="utf-8").lower()
        assert "silent fallback" not in text
