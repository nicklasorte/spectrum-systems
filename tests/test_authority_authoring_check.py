"""Tests for AUTH-AUTHORING-01 pre-PR authority-safe authoring check.

These tests cover the changed-file scanner, schema validation, APR
integration shape, and red-team scenarios (negation, schema/example
content, generated artifacts, and unknown-state handling).

The authoring check is observation-only and does NOT replace the
canonical guards (authority_shape_preflight, authority_leak_guard,
system_registry_guard); those are exercised by their own test files.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCRIPT_PATH = REPO_ROOT / "scripts" / "run_authority_authoring_check.py"

from scripts import run_authority_authoring_check as authoring  # noqa: E402

# Load these so the test module fails fast if jsonschema isn't available.
from spectrum_systems.contracts import (  # noqa: E402
    list_supported_contracts,
    load_example,
    load_schema,
    validate_artifact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scan_text(rel_path: str, text: str):
    return authoring.scan_file(rel_path=rel_path, text=text)


def _evaluate(
    *,
    repo_root: Path,
    changed_files: list[str],
    output_artifact_ref: str = "outputs/authority_authoring_check/authority_authoring_check_record.json",
    base_ref: str = "origin/main",
    head_ref: str = "HEAD",
):
    owner_paths, _ = authoring._load_owner_path_prefixes()
    return authoring.evaluate_authoring_check(
        repo_root=repo_root,
        changed_files=changed_files,
        base_ref=base_ref,
        head_ref=head_ref,
        output_artifact_ref=output_artifact_ref,
        owner_paths=owner_paths,
    )


def _write(repo_root: Path, rel_path: str, text: str) -> None:
    p = repo_root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Schema + example
# ---------------------------------------------------------------------------

def test_record_schema_registered_and_example_validates() -> None:
    discovered = set(list_supported_contracts())
    assert "authority_authoring_check_record" in discovered
    schema = load_schema("authority_authoring_check_record")
    assert schema.get("additionalProperties") is False
    instance = load_example("authority_authoring_check_record")
    validate_artifact(instance, "authority_authoring_check_record")


def test_pass_status_requires_output_artifact_refs() -> None:
    instance = load_example("authority_authoring_check_record")
    assert instance["status"] == "pass"
    instance["output_artifact_refs"] = []
    from jsonschema.exceptions import ValidationError
    with pytest.raises(ValidationError):
        validate_artifact(instance, "authority_authoring_check_record")


def test_warn_status_requires_reason_codes() -> None:
    instance = load_example("authority_authoring_check_record")
    instance["status"] = "warn"
    instance["reason_codes"] = []
    from jsonschema.exceptions import ValidationError
    with pytest.raises(ValidationError):
        validate_artifact(instance, "authority_authoring_check_record")


# ---------------------------------------------------------------------------
# 2. Clean authored doc -> pass
# ---------------------------------------------------------------------------

def test_clean_doc_produces_no_findings(tmp_path: Path) -> None:
    rel = "docs/reviews/clean_doc.md"
    _write(tmp_path, rel, "This is a routine note about a build run. No reserved terms here.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["status"] == "pass"
    assert payload["unsafe_findings"] == []
    assert payload["protected_owner_findings"] == []
    assert payload["scanned_files"] == [rel]
    assert payload["output_artifact_refs"]


# ---------------------------------------------------------------------------
# 3. Reserved authority terms -> finding (each cluster individually so the
#    test scaffolding itself doesn't need to embed the full list).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("term", [
    "approve", "approval",
    "certify", "certification",
    "promote", "promotion",
    "enforce", "enforcement",
    "decide", "decision",
    "authorize", "authorization",
    "verdict",
])
def test_reserved_term_in_non_owner_doc_is_flagged(tmp_path: Path, term: str) -> None:
    rel = f"docs/reviews/{term}_doc.md"
    _write(tmp_path, rel, f"This document will {term} the slice.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["status"] == "warn"
    assert any(f["term"].lower() == term.lower() for f in payload["unsafe_findings"])
    assert authoring.RC_RESERVED in payload["reason_codes"]


# ---------------------------------------------------------------------------
# 4. Negated form is still detected
# ---------------------------------------------------------------------------

def test_negated_authority_term_is_flagged(tmp_path: Path) -> None:
    rel = "docs/reviews/negated.md"
    _write(tmp_path, rel, "This step does not certify the run, and never approves promotion.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["status"] == "warn"
    categories = {f["category"] for f in payload["unsafe_findings"]}
    assert "negated_authority_term" in categories
    assert authoring.RC_NEGATED in payload["reason_codes"]


# ---------------------------------------------------------------------------
# 5. Protected owner acronym used as ownership in non-owner doc
# ---------------------------------------------------------------------------

def test_protected_owner_acronym_ownership_shape_is_flagged(tmp_path: Path) -> None:
    rel = "scripts/build_some_helper.py"
    _write(tmp_path, rel, "# CDE owns the closure step in this helper.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert any(
        f["owner_acronym"] == "CDE" for f in payload["protected_owner_findings"]
    )
    assert authoring.RC_PROTECTED_OWNER in payload["reason_codes"]


def test_routine_owner_acronym_reference_does_not_trigger_protected_finding(
    tmp_path: Path,
) -> None:
    rel = "docs/notes/reference.md"
    _write(tmp_path, rel, "See the CDE artifact in docs/architecture/ for details.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["protected_owner_findings"] == []


# ---------------------------------------------------------------------------
# 6. Owner-context wording does not false-positive
# ---------------------------------------------------------------------------

def test_owner_context_self_path_is_skipped() -> None:
    """The scanner's own files are owner-context for AUTH-AUTHORING-01."""
    payload = _evaluate(
        repo_root=REPO_ROOT,
        changed_files=[
            "scripts/run_authority_authoring_check.py",
            "contracts/schemas/authority_authoring_check_record.schema.json",
            "contracts/examples/authority_authoring_check_record.example.json",
        ],
    )
    assert payload["status"] == "pass"
    skipped = {entry["file"]: entry["skip_reason"] for entry in payload["skipped_files"]}
    assert skipped["scripts/run_authority_authoring_check.py"] == "owner_path"
    assert (
        skipped["contracts/schemas/authority_authoring_check_record.schema.json"]
        == "owner_path"
    )


def test_canonical_owner_path_from_registry_is_skipped(tmp_path: Path) -> None:
    """A file inside a registry-declared owner path is skipped, not flagged."""
    # Use a known canonical owner path: enforcement_engine.py is the SEL-owned
    # enforcement source per contracts/governance/authority_registry.json.
    rel = "spectrum_systems/modules/runtime/enforcement_engine.py"
    _write(tmp_path, rel, "# enforcement: the SEL system enforces policies here.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    skipped = {entry["file"]: entry["skip_reason"] for entry in payload["skipped_files"]}
    # Owner path must show up as skipped with skip_reason owner_path - even
    # though the literal file does not exist in tmp_path, we wrote it above.
    assert skipped.get(rel) == "owner_path"


# ---------------------------------------------------------------------------
# 7. Generated artifact path skipped per policy
# ---------------------------------------------------------------------------

def test_generated_artifact_path_is_skipped(tmp_path: Path) -> None:
    rel = "outputs/some_subsystem/result.json"
    _write(tmp_path, rel, json.dumps({"decision": "noted"}))
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    skipped = {entry["file"]: entry["skip_reason"] for entry in payload["skipped_files"]}
    assert skipped[rel] == "generated_artifact"
    assert authoring.RC_GENERATED_SKIPPED in payload["reason_codes"]
    # Generated-only changed sets remain pass (no findings).
    assert payload["status"] == "pass"


# ---------------------------------------------------------------------------
# 8. Unknown scan state -> unknown with reason codes
# ---------------------------------------------------------------------------

def test_unreadable_authored_file_yields_unknown(tmp_path: Path, monkeypatch) -> None:
    rel = "docs/reviews/unreadable.md"
    _write(tmp_path, rel, "placeholder\n")

    real_read_text = Path.read_text

    def _failing_read_text(self, *args, **kwargs):
        if self.name == "unreadable.md":
            raise OSError("io failure simulation")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _failing_read_text)
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["status"] == "unknown"
    assert authoring.RC_SCAN_UNKNOWN in payload["reason_codes"]


# ---------------------------------------------------------------------------
# 9. Output artifact validates against the schema
# ---------------------------------------------------------------------------

def test_runtime_output_artifact_validates_against_schema(tmp_path: Path) -> None:
    rel = "docs/reviews/sample.md"
    _write(tmp_path, rel, "Routine notes only.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    validate_artifact(payload, "authority_authoring_check_record")


def test_runtime_output_artifact_with_findings_validates(tmp_path: Path) -> None:
    rel = "docs/reviews/withfindings.md"
    _write(tmp_path, rel, "We will promote this artifact and certify the result.\n")
    payload = _evaluate(repo_root=tmp_path, changed_files=[rel])
    assert payload["status"] == "warn"
    validate_artifact(payload, "authority_authoring_check_record")


# ---------------------------------------------------------------------------
# 10. APR integration - if integrated, includes artifact ref; existing
#     guards still run separately.
# ---------------------------------------------------------------------------

def test_apr_runner_includes_authoring_check_when_integrated() -> None:
    """If APR integrates the authoring check, it must:

    - declare the check via ``tpa_authority_authoring_check``;
    - keep the four canonical TPA checks
      (shape preflight, leak guard, system registry guard, contract
      compliance) as separate, independent invocations.

    This test asserts both halves so an accidental refactor cannot
    silently fold one canonical guard into the new authoring check.
    """
    apr = REPO_ROOT / "scripts" / "run_agent_pr_precheck.py"
    text = apr.read_text(encoding="utf-8")
    if "tpa_authority_authoring_check" not in text:
        pytest.skip("APR integration is optional - not enabled in this branch")
    # Existing canonical guards must still appear in the same file.
    for canonical in (
        "tpa_authority_shape",
        "tpa_authority_leak",
        "tpa_system_registry",
        "tpa_contract_compliance",
    ):
        assert canonical in text, f"APR is missing canonical TPA check: {canonical}"


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def test_cli_runs_and_emits_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--changed-files",
            "docs/reviews/none_present.md",
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    # Exit code may be 0 (file missing -> pass with all skipped).
    assert output_path.is_file(), proc.stdout + proc.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "authority_authoring_check_record"
    assert payload["status"] in {"pass", "warn", "block", "unknown"}
    validate_artifact(payload, "authority_authoring_check_record")
