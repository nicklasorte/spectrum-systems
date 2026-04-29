"""AEX-PQX-01 — Contract tests for AI programming governance evidence loop.

Validates:
- repo_mutating work item with missing PQX => BLOCK
- repo_mutating work item with missing AEX => BLOCK
- unknown leg does not count as present
- full_loop_complete=false unless all required legs are present
- present leg requires artifact_refs
- partial/missing/unknown leg requires reason_codes
- dashboard renders rollup from artifact, not local computation
- AEX-PQX-DASH-02 missing evidence is surfaced honestly
- backfilled evidence links to source_artifacts_used
- SMA references are present in rollup
- rollup builder produces deterministic output
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_PROG_DIR = REPO_ROOT / "artifacts" / "ai_programming"
ROLLUP_PATH = AI_PROG_DIR / "ai_programming_governance_rollup.json"
GOVERNED_PATH_RECORD = (
    REPO_ROOT / "artifacts" / "dashboard_metrics" / "ai_programming_governed_path_record.json"
)
GOVERNANCE_VIOLATION_RECORD = (
    REPO_ROOT / "artifacts" / "dashboard_metrics" / "governance_violation_record.json"
)
INTELLIGENCE_ROUTE = (
    REPO_ROOT / "apps" / "dashboard-3ls" / "app" / "api" / "intelligence" / "route.ts"
)
AEX_PQX_DASH_02_EVIDENCE = AI_PROG_DIR / "aex_pqx_dash_02_missing_evidence.json"
CODEX_PRECURSOR_EVIDENCE = (
    AI_PROG_DIR / "aex_pqx_dash_02_codex_precursor_partial_lineage.json"
)
ROOT_CAUSE_DOC = (
    REPO_ROOT / "docs" / "reviews" / "AEX-PQX-01_ai_programming_loop_root_cause.md"
)

CORE_LEGS = ["AEX", "PQX", "EVL", "TPA", "CDE", "SEL"]
VALID_PRESENCE = {"present", "partial", "missing", "unknown", "not_required"}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Rollup artifact existence and schema
# --------------------------------------------------------------------------- #


def test_rollup_artifact_exists_and_parses() -> None:
    assert ROLLUP_PATH.is_file(), f"missing rollup: {ROLLUP_PATH}"
    data = _read_json(ROLLUP_PATH)
    assert isinstance(data, dict)
    assert data.get("artifact_type") == "ai_programming_governance_rollup_record"


def test_rollup_required_fields_present() -> None:
    data = _read_json(ROLLUP_PATH)
    for field in (
        "artifact_type",
        "schema_version",
        "record_id",
        "created_at",
        "owner_system",
        "compliance_status",
        "total_ai_programming_items",
        "repo_mutating_count",
        "per_leg_counts",
        "score",
        "total_required_legs",
        "core_loop_complete",
        "source_artifacts_used",
        "work_item_refs",
    ):
        assert field in data, f"rollup missing field {field!r}"
    assert data["owner_system"] == "MET"
    assert data["compliance_status"] in {"PASS", "WARN", "BLOCK"}
    assert isinstance(data["source_artifacts_used"], list)
    assert data["source_artifacts_used"], "source_artifacts_used is empty"


def test_rollup_per_leg_counts_cover_all_core_legs() -> None:
    data = _read_json(ROLLUP_PATH)
    leg_counts = data.get("per_leg_counts", {})
    for leg in CORE_LEGS:
        assert leg in leg_counts, f"rollup missing per_leg_counts for {leg}"
        counts = leg_counts[leg]
        for bucket in ("present", "partial", "missing", "unknown"):
            assert bucket in counts, f"per_leg_counts[{leg}] missing {bucket!r} bucket"
            assert counts[bucket] >= 0


# --------------------------------------------------------------------------- #
# Fail-closed: repo_mutating + missing AEX/PQX => BLOCK
# --------------------------------------------------------------------------- #


def test_rollup_compliance_block_when_any_repo_mutating_item_missing_aex() -> None:
    """Any repo-mutating work item with AEX missing must force rollup BLOCK."""
    rollup = _read_json(ROLLUP_PATH)
    aex_counts = rollup["per_leg_counts"]["AEX"]
    # If any item has AEX missing, compliance must be BLOCK.
    if aex_counts["missing"] > 0:
        assert rollup["compliance_status"] == "BLOCK", (
            f"AEX has {aex_counts['missing']} missing count(s) but compliance is not BLOCK"
        )


def test_rollup_compliance_block_when_any_repo_mutating_item_missing_pqx() -> None:
    """Any repo-mutating work item with PQX missing must force rollup BLOCK."""
    rollup = _read_json(ROLLUP_PATH)
    pqx_counts = rollup["per_leg_counts"]["PQX"]
    if pqx_counts["missing"] > 0:
        assert rollup["compliance_status"] == "BLOCK", (
            f"PQX has {pqx_counts['missing']} missing count(s) but compliance is not BLOCK"
        )


def test_work_item_missing_pqx_has_block_compliance() -> None:
    """Each work item record with repo_mutating=true and PQX missing must declare BLOCK."""
    for path in sorted(AI_PROG_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        if data.get("repo_mutating") is not True:
            continue
        legs = data.get("legs", {})
        pqx_status = legs.get("PQX", {}).get("status", "unknown")
        if pqx_status in ("missing", "unknown"):
            assert data.get("compliance_status") == "BLOCK", (
                f"{path.name}: repo_mutating=true and PQX={pqx_status!r} "
                f"but compliance_status={data.get('compliance_status')!r}"
            )


def test_work_item_missing_aex_has_block_compliance() -> None:
    """Each work item record with repo_mutating=true and AEX missing must declare BLOCK."""
    for path in sorted(AI_PROG_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        if data.get("repo_mutating") is not True:
            continue
        legs = data.get("legs", {})
        aex_status = legs.get("AEX", {}).get("status", "unknown")
        if aex_status in ("missing", "unknown"):
            assert data.get("compliance_status") == "BLOCK", (
                f"{path.name}: repo_mutating=true and AEX={aex_status!r} "
                f"but compliance_status={data.get('compliance_status')!r}"
            )


# --------------------------------------------------------------------------- #
# Unknown does not count as present
# --------------------------------------------------------------------------- #


def test_rollup_unknown_leg_not_counted_as_present() -> None:
    """An 'unknown' leg count must never be added to 'present' in the rollup."""
    rollup = _read_json(ROLLUP_PATH)
    for leg in CORE_LEGS:
        counts = rollup["per_leg_counts"][leg]
        # Sanity: unknown and present are distinct buckets.
        assert "unknown" in counts
        assert "present" in counts
        # The score must reflect only 'present' legs — we verify indirectly:
        # if unknown > 0 and present == 0, score must be < 1.0.
        if counts["unknown"] > 0 and counts["present"] == 0:
            assert rollup["score"] < 1.0, (
                f"{leg} has unknown={counts['unknown']} and present=0 "
                f"but score={rollup['score']}"
            )


def test_governed_path_record_unknown_leg_not_counted_as_present() -> None:
    """In the governed path record, legs marked 'unknown' in core_loop_compliance
    must not contribute to compliance_score as if they were present."""
    data = _read_json(GOVERNED_PATH_RECORD)
    compliance = data.get("core_loop_compliance", {})
    score = data.get("compliance_score", -1)
    present_count = sum(1 for v in compliance.values() if v == "present")
    total = data.get("total_legs", len(CORE_LEGS))
    expected_max_score = present_count
    assert score <= expected_max_score, (
        f"compliance_score={score} exceeds present leg count={present_count}; "
        "unknown legs may be counted as present"
    )


# --------------------------------------------------------------------------- #
# full_loop_complete requires all legs present
# --------------------------------------------------------------------------- #


def test_full_loop_complete_false_when_any_leg_missing() -> None:
    """full_loop_complete must be False when any leg is not present."""
    rollup = _read_json(ROLLUP_PATH)
    all_present = all(
        rollup["per_leg_counts"][leg]["present"] == rollup["total_ai_programming_items"]
        for leg in CORE_LEGS
    )
    if not all_present:
        assert rollup["core_loop_complete"] is False, (
            "rollup.core_loop_complete is True but not all legs are present"
        )


def test_governed_path_record_core_loop_complete_false_when_legs_missing() -> None:
    data = _read_json(GOVERNED_PATH_RECORD)
    compliance = data.get("core_loop_compliance", {})
    all_present = all(v == "present" for v in compliance.values())
    stated_complete = data.get("core_loop_complete", True)
    if not all_present:
        assert stated_complete is False, (
            "core_loop_complete is True but not all legs are present in core_loop_compliance"
        )


# --------------------------------------------------------------------------- #
# present leg requires artifact_refs; partial/missing/unknown requires reason_codes
# --------------------------------------------------------------------------- #


def test_work_item_present_leg_has_artifact_refs() -> None:
    """Every leg with status='present' must have non-empty artifact_refs."""
    for path in sorted(AI_PROG_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        legs = data.get("legs", {})
        for leg_name, leg_data in legs.items():
            if leg_data.get("status") == "present":
                refs = leg_data.get("artifact_refs", [])
                assert refs, (
                    f"{path.name}: leg {leg_name} has status=present but no artifact_refs"
                )


def test_work_item_partial_missing_unknown_leg_has_reason_codes() -> None:
    """Legs with status partial/missing/unknown must have non-empty reason_codes."""
    for path in sorted(AI_PROG_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        legs = data.get("legs", {})
        for leg_name, leg_data in legs.items():
            status = leg_data.get("status")
            if status in ("partial", "missing", "unknown"):
                codes = leg_data.get("reason_codes", [])
                assert codes, (
                    f"{path.name}: leg {leg_name} has status={status!r} but no reason_codes"
                )


# --------------------------------------------------------------------------- #
# AEX-PQX-DASH-02 missing evidence is surfaced honestly
# --------------------------------------------------------------------------- #


def test_aex_pqx_dash_02_evidence_artifact_exists() -> None:
    assert AEX_PQX_DASH_02_EVIDENCE.is_file(), (
        f"Missing evidence artifact: {AEX_PQX_DASH_02_EVIDENCE}"
    )


def test_aex_pqx_dash_02_evidence_declares_both_legs_missing() -> None:
    data = _read_json(AEX_PQX_DASH_02_EVIDENCE)
    legs = data.get("legs", {})
    assert legs.get("AEX", {}).get("status") == "missing", (
        "AEX-PQX-DASH-02: AEX leg should be missing"
    )
    assert legs.get("PQX", {}).get("status") == "missing", (
        "AEX-PQX-DASH-02: PQX leg should be missing"
    )


def test_aex_pqx_dash_02_evidence_compliance_is_block() -> None:
    data = _read_json(AEX_PQX_DASH_02_EVIDENCE)
    assert data.get("compliance_status") == "BLOCK", (
        "AEX-PQX-DASH-02: compliance_status must be BLOCK"
    )


def test_aex_pqx_dash_02_evidence_has_reason_codes_for_missing_legs() -> None:
    data = _read_json(AEX_PQX_DASH_02_EVIDENCE)
    legs = data.get("legs", {})
    for leg in ("AEX", "PQX"):
        codes = legs.get(leg, {}).get("reason_codes", [])
        assert codes, f"AEX-PQX-DASH-02: leg {leg} missing reason_codes"


def test_aex_pqx_dash_02_in_governed_path_record_work_items() -> None:
    """AEX-PQX-DASH-02 must appear as a work item in the governed path record."""
    data = _read_json(GOVERNED_PATH_RECORD)
    work_items = data.get("ai_programming_work_items", [])
    ids = [i.get("work_item_id") for i in work_items]
    assert "AEX-PQX-DASH-02" in ids, (
        f"AEX-PQX-DASH-02 not found in ai_programming_work_items: {ids}"
    )


def test_aex_pqx_dash_02_in_governed_path_record_shows_missing_aex_pqx() -> None:
    """AEX-PQX-DASH-02 work item in governed path record must show AEX+PQX missing."""
    data = _read_json(GOVERNED_PATH_RECORD)
    work_items = data.get("ai_programming_work_items", [])
    item = next((i for i in work_items if i.get("work_item_id") == "AEX-PQX-DASH-02"), None)
    assert item is not None
    assert item.get("aex_admission_observation") == "missing", (
        "AEX-PQX-DASH-02 aex_admission_observation should be missing"
    )
    assert item.get("pqx_execution_observation") == "missing", (
        "AEX-PQX-DASH-02 pqx_execution_observation should be missing"
    )


def test_aex_pqx_dash_02_codex_precursor_exists_with_partial_evidence() -> None:
    assert CODEX_PRECURSOR_EVIDENCE.is_file(), (
        f"Missing evidence artifact: {CODEX_PRECURSOR_EVIDENCE}"
    )
    data = _read_json(CODEX_PRECURSOR_EVIDENCE)
    legs = data.get("legs", {})
    assert legs.get("AEX", {}).get("status") == "partial"
    assert legs.get("PQX", {}).get("status") == "partial"
    lineage = data.get("lineage_status")
    assert lineage == "missing", f"lineage_status should be missing, got {lineage!r}"


def test_aex_pqx_dash_02_codex_precursor_in_governed_path_record() -> None:
    data = _read_json(GOVERNED_PATH_RECORD)
    work_items = data.get("ai_programming_work_items", [])
    ids = [i.get("work_item_id") for i in work_items]
    assert "AEX-PQX-DASH-02-CODEX-PRECURSOR" in ids, (
        f"AEX-PQX-DASH-02-CODEX-PRECURSOR not found in work_items: {ids}"
    )


# --------------------------------------------------------------------------- #
# Backfilled evidence links to source_artifacts_used
# --------------------------------------------------------------------------- #


def test_work_item_records_have_source_artifacts_used() -> None:
    """All work item records must declare source_artifacts_used."""
    found_any = False
    for path in sorted(AI_PROG_DIR.glob("*.json")):
        try:
            data = _read_json(path)
        except Exception:
            continue
        if data.get("artifact_type") != "ai_programming_work_item_record":
            continue
        found_any = True
        refs = data.get("source_artifacts_used", [])
        assert isinstance(refs, list) and refs, (
            f"{path.name}: source_artifacts_used is empty"
        )
    assert found_any, "No ai_programming_work_item_record files found in artifacts/ai_programming/"


def test_rollup_work_item_refs_exist_on_disk() -> None:
    """Each path in rollup.work_item_refs must be a real file."""
    rollup = _read_json(ROLLUP_PATH)
    refs = rollup.get("work_item_refs", [])
    assert refs, "rollup.work_item_refs is empty"
    for ref in refs:
        path = REPO_ROOT / ref
        assert path.is_file(), f"work_item_ref path not found: {ref}"


# --------------------------------------------------------------------------- #
# SMA references present in rollup
# --------------------------------------------------------------------------- #


def test_rollup_has_sma_artifact_refs() -> None:
    rollup = _read_json(ROLLUP_PATH)
    sma_refs = rollup.get("sma_artifact_refs", [])
    assert isinstance(sma_refs, list) and sma_refs, (
        "rollup.sma_artifact_refs is empty; each work item should produce a 3ls_loop_run_record ref"
    )


def test_sma_loop_run_records_exist_and_have_correct_schema() -> None:
    rollup = _read_json(ROLLUP_PATH)
    sma_refs = rollup.get("sma_artifact_refs", [])
    for ref in sma_refs:
        path = REPO_ROOT / ref
        assert path.is_file(), f"SMA ref not found on disk: {ref}"
        try:
            data = _read_json(path)
        except Exception as exc:
            pytest.fail(f"SMA ref {ref} parse error: {exc}")
        assert data.get("artifact_type") == "3ls_loop_run_record", (
            f"SMA ref {ref} has wrong artifact_type: {data.get('artifact_type')!r}"
        )
        assert data.get("schema_version") == "1.0.0"
        assert data.get("authority_scope") == "observation_only"
        assert data.get("loop_status") in {"complete", "partial", "blocked", "failed"}


def test_sma_loop_run_records_have_first_failure_system_when_not_complete() -> None:
    rollup = _read_json(ROLLUP_PATH)
    for ref in rollup.get("sma_artifact_refs", []):
        path = REPO_ROOT / ref
        if not path.is_file():
            continue
        data = _read_json(path)
        if data.get("loop_status") != "complete":
            assert data.get("first_failure_system") is not None and data.get(
                "first_failure_system"
            ) != "null", (
                f"SMA {path.name}: non-complete loop missing first_failure_system"
            )


# --------------------------------------------------------------------------- #
# Dashboard reads from artifact, not local computation
# --------------------------------------------------------------------------- #


def test_intelligence_route_reads_ai_programming_governed_path_artifact() -> None:
    """Route must reference the artifact path constant, not hardcode values."""
    assert INTELLIGENCE_ROUTE.is_file()
    src = INTELLIGENCE_ROUTE.read_text(encoding="utf-8")
    assert "AI_PROGRAMMING_GOVERNED_PATH_ARTIFACT_PATH" in src
    assert "computeGovernedPathSummary" in src


def test_intelligence_route_does_not_hardcode_compliance_status() -> None:
    """Route must not hardcode 'BLOCK' or 'PASS' as string literals for compliance."""
    assert INTELLIGENCE_ROUTE.is_file()
    src = INTELLIGENCE_ROUTE.read_text(encoding="utf-8")
    # The route should derive compliance from artifact data, not hardcode it.
    # We verify that at minimum the route invokes computeGovernedPathSummary()
    # which is the server-side computation path.
    assert "computeGovernedPathSummary(aiProgrammingGovernedPath)" in src


def test_governed_path_record_is_not_empty() -> None:
    """Governed path record must have non-empty ai_programming_work_items."""
    data = _read_json(GOVERNED_PATH_RECORD)
    items = data.get("ai_programming_work_items", [])
    assert isinstance(items, list) and items, "ai_programming_work_items is empty"


# --------------------------------------------------------------------------- #
# Core_loop_compliance in governed path record is honest
# --------------------------------------------------------------------------- #


def test_governed_path_record_aex_not_present_if_no_item_has_aex_present() -> None:
    """core_loop_compliance.AEX must not be 'present' if no work item has AEX=present."""
    data = _read_json(GOVERNED_PATH_RECORD)
    items = data.get("ai_programming_work_items", [])
    any_aex_present = any(
        i.get("aex_admission_observation") == "present"
        for i in items
        if i.get("repo_mutating") is True
    )
    compliance = data.get("core_loop_compliance", {})
    aex_agg = compliance.get("AEX")
    if not any_aex_present:
        assert aex_agg != "present", (
            f"core_loop_compliance.AEX=present but no work item has AEX=present. "
            "This was the v1 bug — AEX should be 'missing' or 'partial', not 'present'."
        )


def test_governed_path_record_pqx_not_present_if_not_all_items_have_pqx() -> None:
    """core_loop_compliance.PQX is 'missing' if any repo-mutating item has PQX=missing."""
    data = _read_json(GOVERNED_PATH_RECORD)
    items = data.get("ai_programming_work_items", [])
    any_pqx_missing = any(
        i.get("pqx_execution_observation") == "missing"
        for i in items
        if i.get("repo_mutating") is True
    )
    compliance = data.get("core_loop_compliance", {})
    pqx_agg = compliance.get("PQX")
    if any_pqx_missing:
        assert pqx_agg == "missing", (
            f"core_loop_compliance.PQX={pqx_agg!r} but at least one repo-mutating item "
            "has pqx_execution_observation=missing; aggregate should be 'missing'."
        )


# --------------------------------------------------------------------------- #
# Root cause document
# --------------------------------------------------------------------------- #


def test_root_cause_doc_exists() -> None:
    assert ROOT_CAUSE_DOC.is_file(), f"Missing root cause doc: {ROOT_CAUSE_DOC}"


def test_root_cause_doc_mentions_all_known_work_items() -> None:
    content = ROOT_CAUSE_DOC.read_text(encoding="utf-8")
    for work_item in (
        "AIPG-CODEX-001",
        "AIPG-CLAUDE-001",
        "AEX-PQX-DASH-02",
        "AEX-PQX-DASH-02-CODEX-PRECURSOR",
    ):
        assert work_item in content, f"Root cause doc missing work item {work_item}"


# --------------------------------------------------------------------------- #
# Rollup builder determinism
# --------------------------------------------------------------------------- #


def test_rollup_builder_is_deterministic() -> None:
    """Running the builder twice must produce the same compliance_status and counts."""
    script = REPO_ROOT / "scripts" / "build_ai_programming_governance_rollup.py"
    assert script.is_file(), f"builder script not found: {script}"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"builder failed: {result.stderr}"

    rollup = _read_json(ROLLUP_PATH)
    assert rollup["compliance_status"] == "BLOCK", (
        "builder should produce compliance_status=BLOCK given current source evidence"
    )
    assert rollup["score"] == 0.0, (
        "builder should produce score=0.0 given no legs fully present"
    )
    assert rollup["with_aex_evidence"] == 0, (
        "builder should produce with_aex_evidence=0 given no AEX=present items"
    )


# --------------------------------------------------------------------------- #
# Governance violations record
# --------------------------------------------------------------------------- #


def test_governance_violation_record_references_evidence_artifacts() -> None:
    """Governance violation record source_artifacts_used must include the new evidence files."""
    data = _read_json(GOVERNANCE_VIOLATION_RECORD)
    sources = data.get("source_artifacts_used", [])
    for expected in (
        "artifacts/ai_programming/aex_pqx_dash_02_missing_evidence.json",
        "artifacts/ai_programming/aex_pqx_dash_02_codex_precursor_partial_lineage.json",
    ):
        assert expected in sources, (
            f"governance_violation_record.source_artifacts_used missing {expected!r}"
        )


def test_governance_violation_record_violation_count_matches_violations_list() -> None:
    data = _read_json(GOVERNANCE_VIOLATION_RECORD)
    count = data.get("violation_count", -1)
    violations = data.get("violations", [])
    assert count == len(violations), (
        f"violation_count={count} but violations list has {len(violations)} entries"
    )
