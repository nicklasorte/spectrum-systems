"""Contract test for the merge-conflict pressure scanner (MET observation only)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_merge_conflict_pressure_scan.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_mcp_scan", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_classifier_routes_known_high_risk_paths_high():
    m = _load_module()
    assert m._classify("apps/dashboard-3ls/app/api/intelligence/route.ts") == "high"
    assert m._classify("apps/dashboard-3ls/app/page.tsx") == "high"
    assert m._classify("docs/architecture/system_registry.md") == "high"


def test_classifier_routes_artifacts_low():
    m = _load_module()
    assert m._classify("artifacts/tls/system_evidence_attachment.json") == "low"
    assert m._classify("state/anything.json") == "low"
    assert m._classify("governance/reports/x.json") == "low"


def test_classifier_routes_source_medium():
    m = _load_module()
    assert m._classify("spectrum_systems/modules/runtime/foo.py") == "medium"
    assert m._classify("apps/dashboard-3ls/lib/foo.ts") == "medium"
    assert m._classify("contracts/governance/x.json") == "medium"


def test_scanner_writes_observation_only_artifact(tmp_path: Path):
    m = _load_module()
    out = tmp_path / "merge_conflict_pressure_record.json"
    m.main(["--base-ref", "HEAD", "--head-ref", "HEAD", "--output", str(out)])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["artifact_type"] == "merge_conflict_pressure_record"
    assert data["owner_system"] == "MET"
    # Observation only; no authority outcomes.
    assert "merge_conflict_pressure_observation_only" in data["reason_codes"]
    assert "no_authority_outcome" in data["reason_codes"]
    # HEAD-vs-HEAD has no parallel changes.
    assert data["overall_state"] == "no_pressure_observed"
    assert data["items"] == []


def test_scanner_reports_unknown_when_git_ref_lookup_fails(tmp_path: Path):
    m = _load_module()
    out = tmp_path / "merge_conflict_pressure_record.json"
    # An invalid ref that git cannot rev-parse must degrade to 'unknown'
    # rather than silently report 'no_pressure_observed'. A clean state from
    # a command failure is a false negative for operators.
    bad_ref = "DOES_NOT_EXIST_REF_FOR_MET_SCAN_TEST"
    m.main([
        "--base-ref",
        bad_ref,
        "--head-ref",
        "HEAD",
        "--output",
        str(out),
    ])
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["overall_state"] == "unknown"
    assert data["status"] == "unknown"
    assert "git_ref_lookup_failed" in data["reason_codes"]
    # A warning must name the failure mode so dashboards surface it.
    assert any("Git ref lookup failed" in w for w in data["warnings"])
    # base_resolved must NOT echo the bad ref string. `git rev-parse BAD_REF`
    # exits non-zero but writes BAD_REF to stdout; the scanner must route
    # through the return-code check and surface 'unknown' instead.
    assert data["base_resolved"] == "unknown"
    assert bad_ref not in data["base_resolved"]
    # The diagnostic must name 'did not resolve' (ref-resolution failure),
    # not 'merge-base returned empty' (the downstream symptom).
    assert any("did not resolve" in w for w in data["warnings"])
