"""
Tests for spectrum_systems/modules/review_orchestrator.py

Covers:
  - load_review_manifest: all three manifests load and contain required fields
  - load_review_manifest: missing manifest raises FileNotFoundError
  - build_review_pack: pack contains expected keys for all three scopes
  - build_review_pack: failure modes are resolved from registry
  - render_claude_review_prompt: output is non-empty string containing scope context
  - render_claude_review_prompt: unknown scope raises FileNotFoundError
  - validate_review_output: valid sample output passes
  - validate_review_output: invalid JSON raises error (passed=False)
  - validate_review_output: output missing required fields fails validation
  - summarize_review_pack: returns non-empty string with scope_id
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from spectrum_systems.modules.review_orchestrator import (
    build_review_pack,
    load_review_manifest,
    render_claude_review_prompt,
    summarize_review_pack,
    validate_review_output,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_REVIEW_OUTPUT = REPO_ROOT / "reviews" / "output" / "sample.json"

_KNOWN_SCOPES = [
    "p_gap_detection",
    "p1_slide_intelligence",
    "q_working_paper",
]

_MANIFEST_REQUIRED_FIELDS = [
    "scope_id",
    "title",
    "purpose",
    "golden_path_role",
    "in_scope_files",
    "related_contracts",
    "related_tests",
    "related_design_docs",
    "upstream_dependencies",
    "downstream_consumers",
    "invariants",
    "known_edge_cases",
    "known_failure_modes",
]


# ─── load_review_manifest ─────────────────────────────────────────────────────

class TestLoadReviewManifest:
    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_known_scopes_load(self, scope_id: str) -> None:
        manifest = load_review_manifest(scope_id)
        assert isinstance(manifest, dict)
        assert manifest["scope_id"] == scope_id

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_all_required_fields_present(self, scope_id: str) -> None:
        manifest = load_review_manifest(scope_id)
        for field in _MANIFEST_REQUIRED_FIELDS:
            assert field in manifest, f"Missing field '{field}' in manifest for '{scope_id}'"

    def test_unknown_scope_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="nonexistent_scope"):
            load_review_manifest("nonexistent_scope")

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_in_scope_files_is_list(self, scope_id: str) -> None:
        manifest = load_review_manifest(scope_id)
        assert isinstance(manifest["in_scope_files"], list)
        assert len(manifest["in_scope_files"]) > 0

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_known_failure_modes_is_list(self, scope_id: str) -> None:
        manifest = load_review_manifest(scope_id)
        assert isinstance(manifest["known_failure_modes"], list)
        assert len(manifest["known_failure_modes"]) > 0


# ─── build_review_pack ────────────────────────────────────────────────────────

class TestBuildReviewPack:
    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_pack_contains_required_keys(self, scope_id: str) -> None:
        pack = build_review_pack(scope_id)
        for key in (
            "manifest",
            "file_list",
            "contract_list",
            "test_list",
            "design_docs_list",
            "failure_modes_list",
            "assembled_at",
        ):
            assert key in pack, f"Missing key '{key}' in review pack for '{scope_id}'"

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_file_list_is_non_empty(self, scope_id: str) -> None:
        pack = build_review_pack(scope_id)
        assert len(pack["file_list"]) > 0

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_failure_modes_resolved(self, scope_id: str) -> None:
        pack = build_review_pack(scope_id)
        assert len(pack["failure_modes_list"]) > 0
        for fm in pack["failure_modes_list"]:
            assert "id" in fm

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_assembled_at_is_iso_string(self, scope_id: str) -> None:
        pack = build_review_pack(scope_id)
        assembled_at = pack["assembled_at"]
        assert isinstance(assembled_at, str)
        assert "T" in assembled_at  # ISO 8601 format

    def test_unknown_scope_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            build_review_pack("does_not_exist")


# ─── render_claude_review_prompt ─────────────────────────────────────────────

class TestRenderClaudeReviewPrompt:
    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_prompt_is_non_empty_string(self, scope_id: str) -> None:
        prompt = render_claude_review_prompt(scope_id)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_prompt_contains_scope_id(self, scope_id: str) -> None:
        prompt = render_claude_review_prompt(scope_id)
        assert scope_id in prompt

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_prompt_contains_review_instructions(self, scope_id: str) -> None:
        prompt = render_claude_review_prompt(scope_id)
        assert "Review Instructions" in prompt

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_prompt_contains_verdict_instructions(self, scope_id: str) -> None:
        prompt = render_claude_review_prompt(scope_id)
        assert "GO_WITH_FIXES" in prompt

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_prompt_contains_at_least_one_in_scope_file(self, scope_id: str) -> None:
        manifest = load_review_manifest(scope_id)
        prompt = render_claude_review_prompt(scope_id)
        # At least the first in-scope file should appear in the prompt.
        first_file = manifest["in_scope_files"][0]
        assert first_file in prompt

    def test_unknown_scope_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            render_claude_review_prompt("does_not_exist")

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_no_unrendered_template_blocks(self, scope_id: str) -> None:
        prompt = render_claude_review_prompt(scope_id)
        # After rendering, no Jinja-style for-loop blocks should remain.
        assert "{% for" not in prompt
        assert "{% endfor" not in prompt


# ─── validate_review_output ──────────────────────────────────────────────────

class TestValidateReviewOutput:
    def test_valid_sample_passes(self) -> None:
        assert SAMPLE_REVIEW_OUTPUT.is_file(), (
            f"Sample review output not found at {SAMPLE_REVIEW_OUTPUT}"
        )
        result = validate_review_output(str(SAMPLE_REVIEW_OUTPUT))
        assert result["passed"] is True, f"Expected pass but got errors: {result['errors']}"
        assert result["errors"] == []

    def test_valid_sample_has_correct_review_id(self) -> None:
        result = validate_review_output(str(SAMPLE_REVIEW_OUTPUT))
        assert result["review_id"] == "rev-p-gap-detection-2026-03-17"

    def test_valid_sample_has_verdict(self) -> None:
        result = validate_review_output(str(SAMPLE_REVIEW_OUTPUT))
        assert result["verdict"] in {"GO", "GO_WITH_FIXES", "NO_GO"}

    def test_missing_file_fails(self) -> None:
        result = validate_review_output("/tmp/nonexistent_review_output.json")
        assert result["passed"] is False
        assert len(result["errors"]) > 0

    def test_invalid_json_fails(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write("{not valid json")
            tmp_path = f.name
        result = validate_review_output(tmp_path)
        assert result["passed"] is False
        assert len(result["errors"]) > 0

    def test_missing_required_fields_fails(self) -> None:
        invalid = {
            "review_id": "rev-test-2026-01-01",
            # Missing scope_id, review_type, reviewed_at, verdict, findings
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(invalid, f)
            tmp_path = f.name
        result = validate_review_output(tmp_path)
        assert result["passed"] is False
        assert len(result["errors"]) > 0

    def test_invalid_verdict_fails(self) -> None:
        with open(str(SAMPLE_REVIEW_OUTPUT), encoding="utf-8") as f:
            valid_output = json.load(f)
        invalid = {**valid_output, "verdict": "MAYBE"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(invalid, f)
            tmp_path = f.name
        result = validate_review_output(tmp_path)
        assert result["passed"] is False

    def test_invalid_finding_severity_fails(self) -> None:
        with open(str(SAMPLE_REVIEW_OUTPUT), encoding="utf-8") as f:
            valid_output = json.load(f)
        invalid = {**valid_output}
        invalid["findings"] = [
            {**invalid["findings"][0], "severity": "extreme"}
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(invalid, f)
            tmp_path = f.name
        result = validate_review_output(tmp_path)
        assert result["passed"] is False

    def test_finding_missing_required_field_fails(self) -> None:
        with open(str(SAMPLE_REVIEW_OUTPUT), encoding="utf-8") as f:
            valid_output = json.load(f)
        invalid = {**valid_output}
        # Remove required field 'why_it_matters' from first finding.
        finding_without_required = {
            k: v
            for k, v in invalid["findings"][0].items()
            if k != "why_it_matters"
        }
        invalid["findings"] = [finding_without_required]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(invalid, f)
            tmp_path = f.name
        result = validate_review_output(tmp_path)
        assert result["passed"] is False


# ─── summarize_review_pack ────────────────────────────────────────────────────

class TestSummarizeReviewPack:
    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_summary_is_non_empty_string(self, scope_id: str) -> None:
        summary = summarize_review_pack(scope_id)
        assert isinstance(summary, str)
        assert len(summary) > 50

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_summary_contains_scope_id(self, scope_id: str) -> None:
        summary = summarize_review_pack(scope_id)
        assert scope_id in summary

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_summary_contains_files_in_scope(self, scope_id: str) -> None:
        summary = summarize_review_pack(scope_id)
        assert "Files in scope" in summary

    @pytest.mark.parametrize("scope_id", _KNOWN_SCOPES)
    def test_summary_contains_failure_modes(self, scope_id: str) -> None:
        summary = summarize_review_pack(scope_id)
        assert "failure modes" in summary.lower()
