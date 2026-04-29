"""Tests for PRL-01 failure_parser: regex-based CI log parsing."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.prl.failure_parser import (
    ParsedFailure,
    parse_log,
    parse_log_line,
)


class TestParseLogLine:
    def test_authority_shape_violation(self):
        line = "ERROR: authority_shape_violation detected in spectrum_systems/modules/foo.py"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "authority_shape_violation"
        assert "authority" in result.normalized_message.lower()

    def test_system_registry_mismatch(self):
        line = "system_registry_mismatch: canonical owner not registered for module bar"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "system_registry_mismatch"

    def test_srg_acronym_namespace_collision(self):
        line = "ACRONYM_NAMESPACE_COLLISION: PRL conflicts with existing namespace"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "system_registry_mismatch"

    def test_srg_removed_system_reference(self):
        line = "REMOVED_SYSTEM_REFERENCE: system FOO referenced but removed from registry"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "system_registry_mismatch"

    def test_srg_owner_introduction_forbidden(self):
        line = "SRG_OWNER_INTRODUCTION_FORBIDDEN: cannot introduce new owner outside governed flow"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "system_registry_mismatch"

    def test_contract_schema_violation_jsonschema(self):
        line = "jsonschema.exceptions.ValidationError: 'foo' is not valid under any of the given schemas"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "contract_schema_violation"

    def test_contract_schema_violation_additional_properties(self):
        line = "ValidationError: additionalProperties: false violated in artifact"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "contract_schema_violation"

    def test_missing_required_artifact(self):
        line = "halt: missing_required_artifact — artifact lineage_record not found"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "missing_required_artifact"

    def test_trace_missing(self):
        line = "ArtifactEnvelopeError: trace_refs.primary must be non-empty (trace missing)"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "trace_missing"

    def test_replay_mismatch(self):
        line = "FAIL: replay_hash_mismatch detected between run-1 and run-2"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "replay_mismatch"

    def test_policy_mismatch(self):
        line = "trust_policy_block: policy_mismatch for scope=promotion_readiness"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "policy_mismatch"

    def test_pytest_selection_missing_no_tests(self):
        line = "collected 0 items / no tests ran"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "pytest_selection_missing"

    def test_pytest_selection_missing_does_not_match_execution_failure(self):
        # A real assertion failure must NOT be misclassified as a selection failure.
        line = "FAILED tests/prl/test_foo.py::test_bar - AssertionError"
        result = parse_log_line(line)
        assert result is None or result.failure_class != "pytest_selection_missing"

    def test_timeout(self):
        line = "TimeoutError: execution timeout exceeded after 120s"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "timeout"

    def test_rate_limited(self):
        line = "RateLimitError: HTTP 429 too many requests"
        result = parse_log_line(line)
        assert result is not None
        assert result.failure_class == "rate_limited"

    def test_no_match_returns_none(self):
        line = "INFO: everything is fine, no issues detected"
        result = parse_log_line(line)
        assert result is None

    def test_empty_line_returns_none(self):
        assert parse_log_line("") is None
        assert parse_log_line("   ") is None

    def test_file_ref_extraction(self):
        line = "FAILED tests/prl/test_foo.py:42 authority_shape_violation"
        result = parse_log_line(line)
        assert result is not None
        assert any("test_foo.py" in f for f in result.file_refs)

    def test_file_ref_extraction_json(self):
        line = "ValidationError: additionalProperties violated in contracts/schemas/foo.json"
        result = parse_log_line(line)
        assert result is not None
        assert any("foo.json" in f for f in result.file_refs)

    def test_file_ref_extraction_yaml(self):
        line = "contract_schema_violation in .github/workflows/ci.yml"
        result = parse_log_line(line)
        assert result is not None
        assert any("ci.yml" in f for f in result.file_refs)

    def test_raw_excerpt_truncated_at_500(self):
        long_line = "authority_shape_violation " + "x" * 600
        result = parse_log_line(long_line)
        assert result is not None
        assert len(result.raw_excerpt) <= 500


class TestParseLog:
    def test_multiple_failures_parsed(self):
        log = "\n".join([
            "authority_shape_violation in foo.py",
            "system_registry_mismatch for bar module",
            "INFO: harmless line",
        ])
        results = parse_log(log)
        assert len(results) == 2
        classes = {r.failure_class for r in results}
        assert "authority_shape_violation" in classes
        assert "system_registry_mismatch" in classes

    def test_deduplication(self):
        line = "authority_shape_violation in foo.py"
        log = "\n".join([line, line, line])
        results = parse_log(log)
        assert len(results) == 1

    def test_empty_log_no_results(self):
        results = parse_log("")
        assert results == []

    def test_whitespace_only_no_results(self):
        results = parse_log("   \n  \n  ")
        assert results == []

    def test_nonzero_exit_with_no_match_produces_unknown(self):
        log = "something completely unrecognized happened"
        results = parse_log(log, exit_code=1)
        assert len(results) == 1
        assert results[0].failure_class == "unknown_failure"

    def test_zero_exit_with_no_match_produces_no_results(self):
        log = "something completely unrecognized happened"
        results = parse_log(log, exit_code=0)
        assert results == []

    def test_exit_code_propagated(self):
        log = "authority_shape_violation detected"
        results = parse_log(log, exit_code=2)
        assert len(results) == 1
        assert results[0].exit_code == 2

    def test_parsed_failure_is_immutable(self):
        log = "authority_shape_violation in foo.py"
        results = parse_log(log)
        assert len(results) == 1
        with pytest.raises((AttributeError, TypeError)):
            results[0].failure_class = "something_else"  # type: ignore[misc]

    def test_all_failure_classes_matched(self):
        lines = [
            "authority_shape_violation detected",
            "system_registry_mismatch found",
            "jsonschema.exceptions.ValidationError: schema invalid",
            "missing_required_artifact in lineage",
            "trace_id missing from artifact",
            "replay_hash_mismatch between runs",
            "policy_mismatch for trust policy",
            "collected 0 items",
            "TimeoutError: timed out",
            "RateLimitError: HTTP 429",
        ]
        expected_classes = {
            "authority_shape_violation",
            "system_registry_mismatch",
            "contract_schema_violation",
            "missing_required_artifact",
            "trace_missing",
            "replay_mismatch",
            "policy_mismatch",
            "pytest_selection_missing",
            "timeout",
            "rate_limited",
        }
        log = "\n".join(lines)
        results = parse_log(log)
        found_classes = {r.failure_class for r in results}
        assert found_classes == expected_classes
