import json
from pathlib import Path

from spectrum_systems.contracts import load_example, load_schema, validate_artifact


REPO_ROOT = Path(__file__).resolve().parents[1]
STANDARDS_MANIFEST = REPO_ROOT / "contracts" / "standards-manifest.json"
MANIFESTS_DIR = REPO_ROOT / "governance" / "examples" / "manifests"

MEETING_MINUTES_RECORD_CONSUMERS = {"meeting-minutes-engine", "spectrum-program-advisor"}


def test_meeting_minutes_record_example_validates() -> None:
    example = load_example("meeting_minutes_record")
    validate_artifact(example, "meeting_minutes_record")


def test_meeting_minutes_record_registered_in_manifest() -> None:
    manifest = STANDARDS_MANIFEST.read_text()
    manifest_data = json.loads(manifest)
    contracts = manifest_data.get("contracts", [])
    entry = next((c for c in contracts if c.get("artifact_type") == "meeting_minutes_record"), None)
    assert entry is not None, "meeting_minutes_record missing from standards-manifest"
    assert set(entry.get("intended_consumers", [])) == MEETING_MINUTES_RECORD_CONSUMERS


def test_meeting_minutes_record_schema_loads() -> None:
    schema = load_schema("meeting_minutes_record")
    assert schema["properties"]["artifact_type"]["const"] == "meeting_minutes_record"
    for field in ("meeting_id", "meeting_title", "date", "source_transcript", "provenance"):
        assert field in schema["required"]


def _load_governance_manifest(repo_name: str) -> dict:
    path = MANIFESTS_DIR / f"{repo_name}.spectrum-governance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_meeting_minutes_engine_declares_meeting_minutes_record() -> None:
    """meeting-minutes-engine governance manifest must declare meeting_minutes_record."""
    manifest = _load_governance_manifest("meeting-minutes-engine")
    contracts = manifest.get("contracts", {})
    assert "meeting_minutes_record" in contracts, (
        "meeting-minutes-engine.spectrum-governance.json must declare meeting_minutes_record"
    )


def test_spectrum_program_advisor_declares_meeting_minutes_record() -> None:
    """spectrum-program-advisor governance manifest must declare meeting_minutes_record."""
    manifest = _load_governance_manifest("spectrum-program-advisor")
    contracts = manifest.get("contracts", {})
    assert "meeting_minutes_record" in contracts, (
        "spectrum-program-advisor.spectrum-governance.json must declare meeting_minutes_record"
    )


def test_meeting_minutes_record_version_pin_matches_canonical() -> None:
    """Both consumer manifests must pin meeting_minutes_record at the canonical version."""
    manifest_data = json.loads(STANDARDS_MANIFEST.read_text())
    contracts = manifest_data.get("contracts", [])
    entry = next(c for c in contracts if c.get("artifact_type") == "meeting_minutes_record")
    canonical_version = entry["schema_version"]

    for repo_name in MEETING_MINUTES_RECORD_CONSUMERS:
        manifest = _load_governance_manifest(repo_name)
        pinned = manifest.get("contracts", {}).get("meeting_minutes_record")
        assert pinned == canonical_version, (
            f"{repo_name} pins meeting_minutes_record@{pinned!r} "
            f"but canonical version is {canonical_version!r}"
        )


def test_all_intended_consumers_declare_meeting_minutes_record() -> None:
    """Every repo listed as intended_consumer of meeting_minutes_record must declare it."""
    manifest_data = json.loads(STANDARDS_MANIFEST.read_text())
    contracts = manifest_data.get("contracts", [])
    entry = next(c for c in contracts if c.get("artifact_type") == "meeting_minutes_record")
    intended = entry.get("intended_consumers", [])

    for repo_name in intended:
        manifest_path = MANIFESTS_DIR / f"{repo_name}.spectrum-governance.json"
        if not manifest_path.exists():
            continue  # not-yet-enforceable — skip
        repo_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        declared = repo_manifest.get("contracts", {})
        assert "meeting_minutes_record" in declared, (
            f"{repo_name} is an intended_consumer of meeting_minutes_record "
            f"but does not declare it in its governance manifest"
        )


def _base_mmr() -> dict:
    """Return a minimal valid meeting_minutes_record for pattern testing."""
    return {
        "artifact_type": "meeting_minutes_record",
        "artifact_class": "coordination",
        "artifact_id": "MMR-TEST-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "2026.03.0",
        "record_id": "REC-TEST-001",
        "run_id": "run-20260318T000000Z",
        "created_at": "2026-03-18T00:00:00Z",
        "created_by": {"name": "Test", "role": "tester", "agent_type": "script"},
        "source_repo": "test/repo",
        "source_repo_version": "v1.0.0",
        "meeting_id": "MM-2026-03-18",
        "meeting_title": "Test Meeting",
        "date": "2026-03-18",
        "source_transcript": "transcripts/test.txt",
        "attendees": ["Alice"],
        "agenda_items": [],
        "decisions": [],
        "action_items": [],
        "open_questions": [],
        "provenance": {
            "generated_by": "test",
            "generation_timestamp": "2026-03-18T00:00:00Z",
            "source_file": "transcripts/test.txt",
        },
    }


def test_decision_id_valid_pattern_accepted() -> None:
    """decision_id conforming to ^DEC-[A-Z0-9][A-Z0-9._-]*$ must pass validation."""
    data = _base_mmr()
    data["decisions"] = [
        {"decision_id": "DEC-001", "description": "d", "rationale": "r", "decided_by": "team"}
    ]
    validate_artifact(data, "meeting_minutes_record")  # must not raise


def test_decision_id_invalid_pattern_rejected() -> None:
    """decision_id not conforming to the DEC- pattern must fail validation."""
    import jsonschema

    data = _base_mmr()
    data["decisions"] = [
        {"decision_id": "D-001", "description": "d", "rationale": "r", "decided_by": "team"}
    ]
    try:
        validate_artifact(data, "meeting_minutes_record")
        assert False, "Expected ValidationError for non-conforming decision_id"
    except jsonschema.ValidationError:
        pass


def test_action_id_valid_pattern_accepted() -> None:
    """action_id conforming to ^ACT-[A-Z0-9][A-Z0-9._-]*$ must pass validation."""
    data = _base_mmr()
    data["action_items"] = [
        {
            "action_id": "ACT-001",
            "description": "do something",
            "owner": "Alice",
            "due_date": "2026-04-01",
            "status": "open",
        }
    ]
    validate_artifact(data, "meeting_minutes_record")  # must not raise


def test_action_id_invalid_pattern_rejected() -> None:
    """action_id not conforming to the ACT- pattern must fail validation."""
    import jsonschema

    data = _base_mmr()
    data["action_items"] = [
        {
            "action_id": "AI-001",
            "description": "do something",
            "owner": "Alice",
            "due_date": "2026-04-01",
            "status": "open",
        }
    ]
    try:
        validate_artifact(data, "meeting_minutes_record")
        assert False, "Expected ValidationError for non-conforming action_id"
    except jsonschema.ValidationError:
        pass


def test_fup_id_valid_pattern_accepted() -> None:
    """followup_id conforming to ^FUP-[A-Z0-9][A-Z0-9._-]*$ must pass validation."""
    data = _base_mmr()
    data["gap_analysis"] = {
        "recommended_followups": [
            {
                "followup_id": "FUP-001",
                "type": "discuss",
                "text": "Discuss propagation model selection",
                "source_type": "slide",
                "source_id": "SLD-001",
            }
        ]
    }
    validate_artifact(data, "meeting_minutes_record")  # must not raise


def test_fup_id_invalid_pattern_rejected() -> None:
    """followup_id not conforming to the FUP- pattern must fail validation."""
    import jsonschema

    data = _base_mmr()
    data["gap_analysis"] = {
        "recommended_followups": [
            {
                "followup_id": "FOLLOWUP-001",
                "type": "discuss",
                "text": "Discuss propagation model selection",
                "source_type": "slide",
                "source_id": "SLD-001",
            }
        ]
    }
    try:
        validate_artifact(data, "meeting_minutes_record")
        assert False, "Expected ValidationError for non-conforming followup_id"
    except jsonschema.ValidationError:
        pass


def test_gap_id_valid_pattern_accepted_in_mmr() -> None:
    """gap_id conforming to ^GAP-[A-Z0-9][A-Z0-9._-]*$ must pass MMR validation."""
    data = _base_mmr()
    data["gap_analysis"] = {
        "canonical_gaps": [
            {
                "gap_id": "GAP-001",
                "gap_type": "missing_propagation_model",
                "description": "No propagation model specified",
                "severity": "high",
                "source_slide_id": None,
                "related_claim_ids": [],
            }
        ]
    }
    validate_artifact(data, "meeting_minutes_record")  # must not raise


def test_gap_id_invalid_pattern_rejected_in_mmr() -> None:
    """gap_id not conforming to the GAP- pattern must fail MMR validation."""
    import jsonschema

    data = _base_mmr()
    data["gap_analysis"] = {
        "canonical_gaps": [
            {
                "gap_id": "G-001",
                "gap_type": "missing_propagation_model",
                "description": "No propagation model specified",
                "severity": "high",
                "source_slide_id": None,
                "related_claim_ids": [],
            }
        ]
    }
    try:
        validate_artifact(data, "meeting_minutes_record")
        assert False, "Expected ValidationError for non-conforming gap_id"
    except jsonschema.ValidationError:
        pass


def _base_declog() -> dict:
    """Return a minimal valid decision_log for pattern testing."""
    return {
        "artifact_type": "decision_log",
        "artifact_id": "DECLOG-TEST-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "2026.03.0",
        "record_id": "REC-TEST-001",
        "run_id": "run-20260318T000000Z",
        "created_at": "2026-03-18T00:00:00Z",
        "created_by": {"name": "Test", "role": "tester", "agent_type": "script"},
        "source_repo": "test/repo",
        "source_repo_version": "v1.0.0",
        "program_id": "PRG-TEST-001",
        "decisions": [
            {
                "decision_id": "DEC-001",
                "title": "Test decision",
                "status": "proposed",
                "decision_type": "technical",
                "decision_readiness": {"status": "evidence_needed"},
            }
        ],
    }


def test_dec_id_valid_pattern_accepted_in_decision_log() -> None:
    """decision_id conforming to ^DEC-[A-Z0-9][A-Z0-9._-]*$ is accepted in decision_log."""
    data = _base_declog()
    validate_artifact(data, "decision_log")  # must not raise


def test_dec_id_valid_pattern_consistent_across_mmr_and_decision_log() -> None:
    """The same DEC-001 value must be accepted by both meeting_minutes_record and
    decision_log, proving DEC- pattern consistency across schemas."""
    valid_decision_id = "DEC-001"

    mmr_data = _base_mmr()
    mmr_data["decisions"] = [
        {"decision_id": valid_decision_id, "description": "d", "rationale": "r", "decided_by": "team"}
    ]
    validate_artifact(mmr_data, "meeting_minutes_record")  # must not raise

    declog_data = _base_declog()
    declog_data["decisions"][0]["decision_id"] = valid_decision_id
    validate_artifact(declog_data, "decision_log")  # must not raise


def test_dec_id_invalid_pattern_rejected_in_decision_log() -> None:
    """decision_id not conforming to ^DEC-[A-Z0-9][A-Z0-9._-]*$ is rejected in decision_log."""
    import jsonschema

    data = _base_declog()
    data["decisions"][0]["decision_id"] = "DEC-"  # no body after prefix
    try:
        validate_artifact(data, "decision_log")
        assert False, "Expected ValidationError for non-conforming decision_id"
    except jsonschema.ValidationError:
        pass


def _base_nba_memo() -> dict:
    """Return a minimal valid next_best_action_memo for pattern testing."""
    return {
        "artifact_type": "next_best_action_memo",
        "artifact_class": "coordination",
        "artifact_id": "NBA-MEMO-TEST-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "2026.03.0",
        "record_id": "REC-TEST-001",
        "run_id": "run-20260318T000000Z",
        "created_at": "2026-03-18T00:00:00Z",
        "created_by": {"name": "Test", "role": "tester", "agent_type": "script"},
        "source_repo": "test/repo",
        "source_repo_version": "v1.0.0",
        "program_id": "PRG-TEST-001",
        "actions": [
            {
                "action_id": "NBA-001",
                "title": "Test action",
                "priority": "high",
                "status": "planned",
            }
        ],
    }


def test_nba_memo_decision_dependency_invalid_pattern_rejected() -> None:
    """decision_dependency not conforming to ^DEC-[A-Z0-9][A-Z0-9._-]*$ is rejected in next_best_action_memo."""
    import jsonschema

    data = _base_nba_memo()
    data["actions"][0]["decision_dependency"] = "DEC-.BAD"  # starts with non-[A-Z0-9] after DEC-
    try:
        validate_artifact(data, "next_best_action_memo")
        assert False, "Expected ValidationError for non-canonical decision_dependency DEC-.BAD"
    except jsonschema.ValidationError:
        pass


def test_nba_memo_agent_type_expanded_values_accepted() -> None:
    """agent_type values ai_model and workflow added in canonical 6-value enum must be accepted."""
    for agent_type in ("ai_model", "workflow"):
        data = _base_nba_memo()
        data["created_by"]["agent_type"] = agent_type
        validate_artifact(data, "next_best_action_memo")  # must not raise
