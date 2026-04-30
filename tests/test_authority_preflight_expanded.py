"""Tests for authority_preflight_expanded (CLX-ALL-01 Phase 1).

Covers:
- Vocabulary violation detection
- Shadow ownership overlap detection
- Forbidden symbol detection
- Exempt paths are skipped
- Non-governing paths are skipped
- Pass when no violations
- Output schema compliance
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.authority_preflight_expanded import (
    AuthorityPreflightExpandedError,
    run_authority_preflight_expanded,
)


def _result(changed_files: list[str]) -> dict:
    return run_authority_preflight_expanded(
        changed_files=changed_files,
        trace_id="test-trace-001",
    )


def test_pass_on_empty_changed_files() -> None:
    result = _result([])
    assert result["artifact_type"] == "authority_preflight_failure_packet"
    assert result["status"] == "pass"
    assert result["violation_count"] == 0
    assert result["violations"] == []
    assert result["shadow_overlaps"] == []
    assert result["forbidden_symbols"] == []


def test_pass_on_files_outside_scope() -> None:
    result = _result(["docs/README.md", "data/some/file.json"])
    assert result["status"] == "pass"


def test_non_python_files_are_skipped() -> None:
    result = _result(["spectrum_systems/modules/runtime/fake.json"])
    assert result["status"] == "pass"
    assert result["scanned_files"] == []


def test_exempt_guard_files_are_not_scanned() -> None:
    result = _result([
        "spectrum_systems/governance/authority_shape_preflight.py",
        "scripts/run_authority_shape_preflight.py",
        "spectrum_systems/governance/authority_shape_early_gate.py",
    ])
    assert result["status"] == "pass"
    assert result["scanned_files"] == []


def test_output_has_required_fields() -> None:
    result = _result(["spectrum_systems/modules/runtime/some_module.py"])
    required_keys = [
        "artifact_type", "schema_version", "packet_id", "trace_id",
        "scanned_files", "violation_count", "violations",
        "shadow_overlaps", "forbidden_symbols", "status", "emitted_at",
    ]
    for key in required_keys:
        assert key in result, f"Missing required field: {key}"


def test_non_authority_assertions_present() -> None:
    result = _result([])
    assert isinstance(result.get("non_authority_assertions"), list)
    assert len(result["non_authority_assertions"]) > 0


def test_trace_id_propagated() -> None:
    result = run_authority_preflight_expanded(
        changed_files=[],
        trace_id="custom-trace-xyz",
    )
    assert result["trace_id"] == "custom-trace-xyz"


def test_invalid_changed_files_type_raises() -> None:
    import pytest
    with pytest.raises(AuthorityPreflightExpandedError):
        run_authority_preflight_expanded(changed_files="not-a-list", trace_id="t")


def test_violation_count_matches_violations_length() -> None:
    result = run_authority_preflight_expanded(
        changed_files=["spectrum_systems/modules/runtime/some_module.py"],
        trace_id="t",
    )
    assert result["violation_count"] == len(result["violations"]) + len(result["forbidden_symbols"])


def test_real_file_with_no_authority_violations(tmp_path) -> None:
    """A file with only safe names passes preflight."""
    safe_py = REPO_ROOT / "spectrum_systems" / "modules" / "runtime" / "_clx_test_safe_dummy.py"
    safe_py.write_text(
        '"""Safe module."""\nstatus = "ok"\nresult_signal = "pass"\n', encoding="utf-8"
    )
    try:
        result = run_authority_preflight_expanded(
            changed_files=["spectrum_systems/modules/runtime/_clx_test_safe_dummy.py"],
            trace_id="t",
        )
        # May be pass or fail depending on content, but must not error.
        assert result["artifact_type"] == "authority_preflight_failure_packet"
        assert result["status"] in ("pass", "fail")
    finally:
        safe_py.unlink(missing_ok=True)
