"""
Tests for artifact packaging and study state model modules.

Covers:
  - study_state: empty_study_state, build_study_state, validate_study_state
  - artifact_packager: package_artifacts writes all required files, validate_package
  - meeting_minutes_pipeline: run_pipeline produces a valid package with study_state.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.study_state import (  # noqa: E402
    REQUIRED_KEYS,
    SCHEMA_VERSION,
    build_study_state,
    empty_study_state,
    validate_study_state,
)
from spectrum_systems.modules.artifact_packager import (  # noqa: E402
    PACKAGE_FILES,
    package_artifacts,
    validate_package,
)
from spectrum_systems.modules.meeting_minutes_pipeline import (  # noqa: E402
    build_run_id,
    run_pipeline,
)
from spectrum_systems.modules.runtime.trace_engine import start_span, start_trace  # noqa: E402
from spectrum_systems.study_runner.artifact_writer import write_outputs  # noqa: E402
from spectrum_systems.study_runner.load_config import (  # noqa: E402
    BandConfig,
    DeploymentConfig,
    PropagationModelConfig,
    ProtectionCriteria,
    StudyConfig,
    SystemConfig,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_EXTRACTION = {
    "action_items": [
        {
            "action_id": "AI-001",
            "task": "Run interference margin sensitivity test",
            "owner": "Ops Lead",
            "due_date": "2026-03-26",
            "status": "open",
            "dependencies": None,
        },
        {
            "action_id": "AI-002",
            "task": "Confirm alternate vendor lead time",
            "owner": "Program Manager",
            "due_date": "2026-03-21",
            "status": "open",
            "dependencies": None,
        },
    ],
    "decisions_made": [],
}

SAMPLE_SIGNALS = {
    "decisions_made": [
        {
            "decision_id": "DEC-001",
            "decision": "Proceed with updated antenna configuration",
            "rationale": "Updated config covers edge cases",
            "decision_owner": "Ops Lead",
            "agenda_item": "Interference test plan",
            "date_made": "2026-03-19",
        }
    ],
    "risks_or_open_questions": [
        {
            "issue_id": "RSK-001",
            "description": "Schedule slip if antenna delivery is delayed",
            "impact": "medium",
            "owner": "Program Manager",
            "target_resolution_date": "2026-03-21",
            "extraction_confidence": 0.9,
        }
    ],
}

SAMPLE_TRANSCRIPT = "Sample transcript for testing."


# ─── study_state: empty_study_state ───────────────────────────────────────────

def test_empty_study_state_has_all_required_keys() -> None:
    state = empty_study_state()
    for key in REQUIRED_KEYS:
        assert key in state, f"Missing required key: {key}"


def test_empty_study_state_all_lists() -> None:
    state = empty_study_state()
    for key in REQUIRED_KEYS:
        assert isinstance(state[key], list), f"Key '{key}' should be a list"


def test_empty_study_state_all_empty() -> None:
    state = empty_study_state()
    for key in REQUIRED_KEYS:
        assert state[key] == [], f"Key '{key}' should be empty list"


# ─── study_state: build_study_state ───────────────────────────────────────────

def test_build_study_state_has_all_required_keys() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    for key in REQUIRED_KEYS:
        assert key in state, f"Missing required key after build: {key}"


def test_build_study_state_action_items_mapped() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    assert len(state["action_items"]) == len(SAMPLE_EXTRACTION["action_items"])


def test_build_study_state_action_item_fields() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    item = state["action_items"][0]
    assert item["id"] == "AI-001"
    assert item["task"] == "Run interference margin sensitivity test"
    assert item["owner"] == "Ops Lead"
    assert item["source"] == "structured_extraction"


def test_build_study_state_risks_from_signals() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    assert len(state["risks"]) == len(SAMPLE_SIGNALS["risks_or_open_questions"])


def test_build_study_state_risk_fields() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    risk = state["risks"][0]
    assert risk["id"] == "RSK-001"
    assert "schedule slip" in risk["description"].lower()
    assert risk["source"] == "signals"


def test_build_study_state_decisions_from_signals() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    assert len(state["decisions"]) == len(SAMPLE_SIGNALS["decisions_made"])


def test_build_study_state_schema_version() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    assert state["schema_version"] == SCHEMA_VERSION


def test_build_study_state_empty_extraction() -> None:
    state = build_study_state({}, {})
    assert state["action_items"] == []
    assert state["risks"] == []
    assert state["decisions"] == []


# ─── study_state: validate_study_state ────────────────────────────────────────

def test_validate_study_state_valid_empty() -> None:
    state = empty_study_state()
    errors = validate_study_state(state)
    assert errors == []


def test_validate_study_state_valid_built() -> None:
    state = build_study_state(SAMPLE_EXTRACTION, SAMPLE_SIGNALS)
    errors = validate_study_state(state)
    assert errors == []


def test_validate_study_state_missing_key() -> None:
    state = empty_study_state()
    del state["action_items"]
    errors = validate_study_state(state)
    assert any("action_items" in e for e in errors)


def test_validate_study_state_wrong_type() -> None:
    state = empty_study_state()
    state["risks"] = "not a list"
    errors = validate_study_state(state)
    assert any("risks" in e for e in errors)


# ─── artifact_packager: package_artifacts ─────────────────────────────────────

def test_package_artifacts_creates_all_files(tmp_path: Path) -> None:
    result = package_artifacts(
        run_id="run-test001",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = Path(result["package_dir"])
    for filename in PACKAGE_FILES:
        assert (package_dir / filename).exists(), f"Missing file: {filename}"


def test_package_artifacts_study_state_valid(tmp_path: Path) -> None:
    result = package_artifacts(
        run_id="run-test002",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = Path(result["package_dir"])
    state = json.loads((package_dir / "study_state.json").read_text(encoding="utf-8"))
    errors = validate_study_state(state)
    assert errors == []


def test_package_artifacts_docx_stub_written(tmp_path: Path) -> None:
    result = package_artifacts(
        run_id="run-test003",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = Path(result["package_dir"])
    docx_path = package_dir / "meeting_minutes.docx"
    assert docx_path.exists()
    # Stub is a JSON marker, not a real DOCX.
    content = docx_path.read_bytes().decode("utf-8")
    data = json.loads(content)
    assert data["stub"] is True


def test_package_artifacts_real_docx(tmp_path: Path) -> None:
    docx_bytes = b"PK fake docx content"
    result = package_artifacts(
        run_id="run-test004",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
        docx_bytes=docx_bytes,
    )
    package_dir = Path(result["package_dir"])
    assert (package_dir / "meeting_minutes.docx").read_bytes() == docx_bytes


def test_package_artifacts_validation_passes(tmp_path: Path) -> None:
    result = package_artifacts(
        run_id="run-test005",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    assert result["validation"]["passed"] is True
    assert result["validation"]["errors"] == []


def test_package_artifacts_deterministic(tmp_path: Path) -> None:
    """Same inputs produce the same output files."""
    kwargs = dict(
        run_id="run-det001",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path / "run1",
    )
    r1 = package_artifacts(**kwargs)
    kwargs["artifacts_root"] = tmp_path / "run2"
    r2 = package_artifacts(**kwargs)
    for filename in ("structured_extraction.json", "signals.json", "study_state.json"):
        c1 = (Path(r1["package_dir"]) / filename).read_text(encoding="utf-8")
        c2 = (Path(r2["package_dir"]) / filename).read_text(encoding="utf-8")
        assert c1 == c2, f"Non-deterministic output in {filename}"


def test_package_artifacts_deterministic_study_state_timestamp_from_inputs(tmp_path: Path) -> None:
    extraction = dict(SAMPLE_EXTRACTION)
    extraction["generated_at"] = "2026-04-02T00:00:00Z"
    signals = dict(SAMPLE_SIGNALS)
    signals["generated_at"] = "2099-01-01T00:00:00Z"

    r1 = package_artifacts(
        run_id="run-det-ts-1",
        structured_extraction=extraction,
        signals=signals,
        artifacts_root=tmp_path / "run1",
    )
    r2 = package_artifacts(
        run_id="run-det-ts-1",
        structured_extraction=extraction,
        signals=signals,
        artifacts_root=tmp_path / "run2",
    )
    s1 = json.loads((Path(r1["package_dir"]) / "study_state.json").read_text(encoding="utf-8"))
    s2 = json.loads((Path(r2["package_dir"]) / "study_state.json").read_text(encoding="utf-8"))
    assert s1["generated_at"] == "2026-04-02T00:00:00Z"
    assert s1["generated_at"] == s2["generated_at"]


# ─── artifact_packager: validate_package ──────────────────────────────────────

def test_validate_package_passes_after_package(tmp_path: Path) -> None:
    package_artifacts(
        run_id="run-val001",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = tmp_path / "run-val001" / "meeting_minutes"
    report = validate_package(package_dir)
    assert report["passed"] is True


def test_validate_package_missing_file(tmp_path: Path) -> None:
    package_artifacts(
        run_id="run-val002",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = tmp_path / "run-val002" / "meeting_minutes"
    (package_dir / "study_state.json").unlink()
    report = validate_package(package_dir)
    assert report["passed"] is False
    assert any("study_state.json" in e for e in report["errors"])


def test_validate_package_action_item_count_mismatch(tmp_path: Path) -> None:
    package_artifacts(
        run_id="run-val003",
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = tmp_path / "run-val003" / "meeting_minutes"
    # Corrupt study_state action_items to create a count mismatch.
    state_path = package_dir / "study_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["action_items"] = []
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    report = validate_package(package_dir)
    assert report["passed"] is False
    assert any("action_items" in e for e in report["errors"])


# ─── meeting_minutes_pipeline: run_pipeline ───────────────────────────────────

def test_run_pipeline_produces_all_files(tmp_path: Path) -> None:
    result = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = Path(result["package_dir"])
    for filename in PACKAGE_FILES:
        assert (package_dir / filename).exists(), f"Missing: {filename}"


def test_run_pipeline_validation_passes(tmp_path: Path) -> None:
    result = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    assert result["validation"]["passed"] is True


def test_run_pipeline_study_state_has_required_keys(tmp_path: Path) -> None:
    result = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path,
    )
    package_dir = Path(result["package_dir"])
    state = json.loads((package_dir / "study_state.json").read_text(encoding="utf-8"))
    for key in REQUIRED_KEYS:
        assert key in state


def test_run_pipeline_explicit_run_id(tmp_path: Path) -> None:
    result = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        run_id="run-explicit01",
        artifacts_root=tmp_path,
    )
    assert result["run_id"] == "run-explicit01"
    assert "run-explicit01" in result["package_dir"]


def test_run_pipeline_derived_run_id_deterministic(tmp_path: Path) -> None:
    r1 = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path / "a",
    )
    r2 = run_pipeline(
        transcript_text=SAMPLE_TRANSCRIPT,
        structured_extraction=SAMPLE_EXTRACTION,
        signals=SAMPLE_SIGNALS,
        artifacts_root=tmp_path / "b",
    )
    assert r1["run_id"] == r2["run_id"]


def test_build_run_id_deterministic() -> None:
    assert build_run_id("hello") == build_run_id("hello")
    assert build_run_id("hello") != build_run_id("world")


def _sample_study_config(tmp_path: Path) -> StudyConfig:
    config_path = tmp_path / "study_config.yaml"
    config_path.write_text("study: test\n", encoding="utf-8")
    return StudyConfig(
        config_path=config_path,
        band=BandConfig(start_freq_mhz=3550.0, end_freq_mhz=3700.0),
        systems=[SystemConfig(name="System A", system_type="base")],
        propagation_model=PropagationModelConfig(model="ITM"),
        deployment=DeploymentConfig(
            base_station_density_per_km2=1.0,
            antenna_height_m=30.0,
            raw_density="1/km2",
            raw_height="30m",
        ),
        protection_criteria=ProtectionCriteria(i_n_db=-6.0, reliability=0.95, raw_i_n="-6 dB"),
    )


def _sample_pipeline_outputs() -> dict:
    return {
        "tables": {"deployments": [{"system": "System A", "distance_km": 10.0}]},
        "figures_metadata": [{"figure_id": "fig-1", "title": "Coverage"}],
        "protection_zones": [],
        "deployments": [],
        "pathloss": [],
        "interference": [],
        "protection_evaluations": {"System A": True},
    }


def test_study_runner_write_outputs_fails_without_trace_context(tmp_path: Path) -> None:
    config = _sample_study_config(tmp_path)
    with pytest.raises(ValueError, match="valid trace context"):
        write_outputs(
            config,
            _sample_pipeline_outputs(),
            logger=None,
            policy_id="regression-policy-v1.0.0",
            generated_by_version="abcdef123456",
            source_revision="rev123",
            trace_id="",
            span_id="",
        )


def test_study_runner_write_outputs_provenance_uses_runtime_values(tmp_path: Path, monkeypatch) -> None:
    config = _sample_study_config(tmp_path)
    trace_id = start_trace({"test": "study_runner"})
    span_id = start_span(trace_id, "write_outputs_test")

    class _Logger:
        def info(self, _msg: str) -> None:
            return

    monkeypatch.chdir(tmp_path)
    write_outputs(
        config,
        _sample_pipeline_outputs(),
        logger=_Logger(),
        policy_id="regression-policy-v1.0.0",
        generated_by_version="abcdef123456",
        source_revision="rev20260322",
        trace_id=trace_id,
        span_id=span_id,
    )

    summary = json.loads((tmp_path / "outputs" / "study_summary.json").read_text(encoding="utf-8"))
    provenance = summary["table_metadata"][0]["provenance"]
    assert provenance["policy_id"] == "regression-policy-v1.0.0"
    assert provenance["generated_by_version"] == "abcdef123456"
    assert provenance["source_revision"] == "rev20260322"
    assert provenance["trace_id"] == trace_id
    assert provenance["span_id"] == span_id
    assert provenance["source_revision"] != "rev0"
    assert provenance["generated_by_version"] != "design-notebook"
