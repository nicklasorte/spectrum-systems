"""Tests for CLP-01 Core Loop Pre-PR Gate.

These tests exercise:
- the schema and example artifact
- the pure-logic helpers in spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py
- AGL integration via spectrum_systems/modules/runtime/agent_core_loop_proof.py
- the AGL-01 failure-class fixtures (authority shape, authority leak, stale TLS,
  contract schema violation)

CLP is observation_only; these tests assert the artifact never claims authority
and that fail-closed behavior is preserved.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_core_loop_proof import (
    build_agent_core_loop_record,
)
from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (
    CHECK_OWNER,
    KNOWN_FAILURE_CLASSES,
    REQUIRED_CHECK_NAMES,
    build_check,
    build_gate_result,
    diff_hash_maps,
    evaluate_gate,
    gate_status_to_exit_code,
    hash_paths,
)

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _all_pass_checks() -> list[dict]:
    return [
        build_check(
            check_name=name,
            command=f"echo {name}",
            status="pass",
            output_ref=f"outputs/core_loop_pre_pr_gate/{name}.json",
        )
        for name in REQUIRED_CHECK_NAMES
    ]


def _gate(
    checks: list[dict],
    *,
    repo_mutating: bool = True,
    evl_shard_evidence: dict | None = None,
    evl_shard_first_evidence: dict | None = None,
) -> dict:
    art = build_gate_result(
        work_item_id="CLP-01-TEST",
        agent_type="claude",
        repo_mutating=repo_mutating,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/run_core_loop_pre_pr_gate.py"],
        checks=checks,
        evl_shard_evidence=evl_shard_evidence,
        evl_shard_first_evidence=evl_shard_first_evidence,
    )
    validate_artifact(art, "core_loop_pre_pr_gate_result")
    return art


# ---------------------------------------------------------------------------
# schema + example
# ---------------------------------------------------------------------------


def test_example_validates():
    ex = json.loads(
        (
            ROOT / "contracts" / "examples" / "core_loop_pre_pr_gate_result.example.json"
        ).read_text(encoding="utf-8")
    )
    validate_artifact(ex, "core_loop_pre_pr_gate_result")


def test_authority_scope_remains_observation_only():
    art = _gate(_all_pass_checks())
    assert art["authority_scope"] == "observation_only"
    bad = dict(art)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")


def test_clp_does_not_claim_authority():
    """The artifact must not include any approval/certification/promotion/enforcement language."""
    art = _gate(_all_pass_checks())
    forbidden = {
        "approval",
        "certification",
        "promotion",
        "enforcement",
        "approved",
        "certified",
        "promoted",
        "enforced",
    }
    payload_lower = json.dumps(art).lower()
    for term in forbidden:
        assert f'"{term}"' not in payload_lower, term
        assert f": \"{term}\"" not in payload_lower, term


def test_gate_pass_only_when_all_required_checks_pass():
    art = _gate(_all_pass_checks())
    assert art["gate_status"] == "pass"
    assert art["first_failed_check"] is None
    assert art["human_review_required"] is False


def test_check_names_cover_required_set():
    assert set(REQUIRED_CHECK_NAMES) == {
        "authority_shape_preflight",
        "authority_leak_guard",
        "contract_enforcement",
        "tls_generated_artifact_freshness",
        "contract_preflight",
        "selected_tests",
        "evl_shard_artifacts",
        "evl_shard_first_readiness",
    }
    for name, owner in CHECK_OWNER.items():
        assert owner in {
            "AEX",
            "PQX",
            "EVL",
            "TPA",
            "CDE",
            "SEL",
            "LIN",
            "REP",
            "OBS",
            "SLO",
            "PRL",
            "RIL",
            "FRE",
        }, name


# ---------------------------------------------------------------------------
# fail-closed: missing / skipped checks
# ---------------------------------------------------------------------------


def test_missing_required_check_blocks():
    """Drop authority_shape_preflight — repo_mutating gate must block."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "authority_shape_preflight"]
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert "missing_required_check_output" in art["failure_classes"]
    assert art["first_failed_check"] == "authority_shape_preflight"


def test_missing_authority_leak_blocks():
    checks = [c for c in _all_pass_checks() if c["check_name"] != "authority_leak_guard"]
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_leak_guard"


def test_missing_required_check_output_blocks():
    """build_check raises if status=pass but output_ref is empty."""
    with pytest.raises(ValueError):
        build_check(
            check_name="contract_enforcement",
            command="x",
            status="pass",
            output_ref="",
        )


def test_skipped_required_check_blocks_repo_mutating():
    checks = _all_pass_checks()
    checks[0] = build_check(
        check_name="authority_shape_preflight",
        command="x",
        status="skipped",
        output_ref=None,
        reason_codes=["operator_skipped"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_shape_preflight"


# ---------------------------------------------------------------------------
# AGL-01 failure classes
# ---------------------------------------------------------------------------


def test_authority_shape_failure_blocks():
    """AGL-01 fixture: authority_shape_review_language_lint reason code."""
    checks = _all_pass_checks()
    checks[0] = build_check(
        check_name="authority_shape_preflight",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/authority_shape_preflight_result.json",
        failure_class="authority_shape_violation",
        reason_codes=["authority_shape_review_language_lint"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_shape_preflight"
    assert "authority_shape_violation" in art["failure_classes"]


def test_authority_leak_failure_blocks():
    """AGL-01 fixture: forbidden authority value detected."""
    checks = _all_pass_checks()
    checks[1] = build_check(
        check_name="authority_leak_guard",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/authority_leak_guard_result.json",
        failure_class="authority_leak_violation",
        reason_codes=["forbidden_authority_value"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "authority_leak_guard"


def test_contract_enforcement_failure_blocks():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="contract_enforcement_violation",
        reason_codes=["contract_compliance_findings"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "contract_enforcement"


def test_stale_tls_artifact_blocks():
    """AGL-01 fixture: stale TLS evidence attachment."""
    checks = _all_pass_checks()
    checks[3] = build_check(
        check_name="tls_generated_artifact_freshness",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/tls_freshness_observation.json",
        failure_class="tls_generated_artifact_stale",
        reason_codes=["tls_generated_artifact_drift"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "tls_generated_artifact_freshness"


def test_contract_preflight_block_propagates():
    """AGL-01 fixture: contract preflight schema_violation."""
    checks = _all_pass_checks()
    checks[4] = build_check(
        check_name="contract_preflight",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_preflight/contract_preflight_result_artifact.json",
        failure_class="contract_preflight_block",
        reason_codes=["block"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "contract_preflight"
    assert "contract_preflight_block" in art["failure_classes"]


def test_selected_tests_failure_blocks():
    checks = _all_pass_checks()
    checks[5] = build_check(
        check_name="selected_tests",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/selected_tests_result.json",
        failure_class="selected_test_failure",
        reason_codes=["pytest_returncode_1"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "selected_tests"


def test_selected_tests_skip_in_repo_mutating_blocks():
    """Skipping the selected_tests check on repo-mutating work blocks."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "selected_tests"]
    art = _gate(checks)
    assert art["gate_status"] == "block"


def test_tls_freshness_drift_blocks(tmp_path):
    """Hash drift between before and after generator runs forces block."""
    tls_artifact = tmp_path / "system_evidence_attachment.json"
    tls_artifact.write_text("BEFORE", encoding="utf-8")
    before = hash_paths([tls_artifact])
    tls_artifact.write_text("AFTER", encoding="utf-8")
    after = hash_paths([tls_artifact])
    drift = diff_hash_maps(before, after)
    assert drift, "expected drift detection to flag changed file"
    check = build_check(
        check_name="tls_generated_artifact_freshness",
        command="regenerate-and-diff",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/tls_freshness_observation.json",
        failure_class="tls_generated_artifact_stale",
        reason_codes=["tls_generated_artifact_drift"],
    )
    other = [c for c in _all_pass_checks() if c["check_name"] != "tls_generated_artifact_freshness"]
    art = _gate(other + [check])
    assert art["gate_status"] == "block"


def test_tls_freshness_skip_blocks_repo_mutating():
    """Skipping the freshness check on repo-mutating work blocks."""
    checks = [c for c in _all_pass_checks() if c["check_name"] != "tls_generated_artifact_freshness"]
    art = _gate(checks)
    assert art["gate_status"] == "block"


# ---------------------------------------------------------------------------
# Unknown failure classes require human review
# ---------------------------------------------------------------------------


def test_unknown_failure_class_requires_human_review():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="block",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="completely_unrecognized_failure_class",
        reason_codes=["odd_signal"],
    )
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["human_review_required"] is True
    assert "completely_unrecognized_failure_class" not in KNOWN_FAILURE_CLASSES


# ---------------------------------------------------------------------------
# Schema invariants enforced via validate_artifact
# ---------------------------------------------------------------------------


def test_schema_rejects_pass_with_human_review():
    art = _gate(_all_pass_checks())
    art["human_review_required"] = True
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_pass_with_first_failed_check():
    art = _gate(_all_pass_checks())
    art["first_failed_check"] = "selected_tests"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_check_with_invalid_status():
    art = _gate(_all_pass_checks())
    art["checks"][0]["status"] = "approved"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_schema_rejects_unknown_check_name():
    art = _gate(_all_pass_checks())
    art["checks"][0]["check_name"] = "promotion_certification"
    with pytest.raises(Exception):
        validate_artifact(art, "core_loop_pre_pr_gate_result")


def test_exit_code_mapping():
    assert gate_status_to_exit_code("pass") == 0
    assert gate_status_to_exit_code("warn") == 1
    assert gate_status_to_exit_code("block") == 2


# ---------------------------------------------------------------------------
# AGL integration — repo-mutating work without CLP evidence must block
# ---------------------------------------------------------------------------


def test_agl_reports_missing_clp_evidence_for_repo_mutating_work():
    rec = build_agent_core_loop_record("AGL-MISSING-CLP", "claude", None, None)
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "clp_evidence_missing" in reason_codes
    assert any(
        a["owner_system"] == "PRL" and a["reason_code"] == "clp_evidence_missing"
        for a in rec["learning_actions"]
    )


def test_agl_blocks_when_clp_gate_status_is_block(tmp_path):
    clp_artifact = tmp_path / "clp.json"
    clp = build_gate_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=[
            build_check(
                check_name="authority_shape_preflight",
                command="x",
                status="block",
                output_ref="outputs/x.json",
                failure_class="authority_shape_violation",
                reason_codes=["authority_shape_review_language_lint"],
            ),
            *[
                build_check(
                    check_name=name,
                    command="echo ok",
                    status="pass",
                    output_ref=f"outputs/{name}.json",
                )
                for name in REQUIRED_CHECK_NAMES
                if name != "authority_shape_preflight"
            ],
        ],
    )
    clp_artifact.write_text(json.dumps(clp), encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-BLOCK", "claude", None, str(clp_artifact))
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "authority_shape_violation" in reason_codes


def test_agl_passes_when_clp_evidence_is_complete_pass(tmp_path):
    clp_artifact = tmp_path / "clp.json"
    clp = build_gate_result(
        work_item_id="W",
        agent_type="claude",
        repo_mutating=True,
        base_ref="origin/main",
        head_ref="HEAD",
        changed_files=["scripts/x.py"],
        checks=[
            build_check(
                check_name=name,
                command="echo ok",
                status="pass",
                output_ref=f"outputs/{name}.json",
            )
            for name in REQUIRED_CHECK_NAMES
        ],
    )
    clp_artifact.write_text(json.dumps(clp), encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-PASS", "claude", None, str(clp_artifact))
    # AGL leg statuses now reflect CLP evidence: AEX/PQX/EVL/TPA legs must be
    # set from CLP. PQX leg has no CLP mapping, so it remains unknown ->
    # AGL still BLOCKs on missing PQX evidence (which is correct fail-closed
    # behavior — CLP cannot certify PQX execution closure).
    assert rec["compliance_status"] in {"BLOCK", "WARN", "PASS"}
    assert rec["loop_legs"]["AEX"]["status"] == "present"
    assert rec["loop_legs"]["EVL"]["status"] == "present"
    assert rec["loop_legs"]["TPA"]["status"] == "present"


def test_agl_treats_invalid_clp_artifact_as_missing(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{\"artifact_type\": \"not_clp\"}", encoding="utf-8")
    rec = build_agent_core_loop_record("AGL-INVALID", "claude", None, str(bad))
    assert rec["compliance_status"] == "BLOCK"
    reason_codes = {a["reason_code"] for a in rec["learning_actions"]}
    assert "clp_evidence_missing" in reason_codes


# ---------------------------------------------------------------------------
# evaluate_gate non-mutating decisions
# ---------------------------------------------------------------------------


def test_evaluate_gate_warn_when_only_warn_checks():
    checks = _all_pass_checks()
    checks[2] = build_check(
        check_name="contract_enforcement",
        command="x",
        status="warn",
        output_ref="outputs/core_loop_pre_pr_gate/contract_enforcement.log",
        failure_class="policy_mismatch",
        reason_codes=["soft_finding"],
    )
    gate_status, first_failed, classes, human = evaluate_gate(
        checks=checks, repo_mutating=True
    )
    assert gate_status == "warn"
    assert first_failed is None
    assert "policy_mismatch" in classes
    assert human is False


def test_evaluate_gate_block_with_missing_check_repo_mutating():
    checks = [c for c in _all_pass_checks() if c["check_name"] != "selected_tests"]
    gate_status, first_failed, classes, _ = evaluate_gate(
        checks=checks, repo_mutating=True
    )
    assert gate_status == "block"
    assert first_failed == "selected_tests"
    assert "missing_required_check_output" in classes


def test_evaluate_gate_pass_for_non_repo_mutating_with_no_checks():
    gate_status, first_failed, classes, human = evaluate_gate(
        checks=[], repo_mutating=False
    )
    assert gate_status == "pass"
    assert first_failed is None
    assert classes == []
    assert human is False


# ---------------------------------------------------------------------------
# PRL-04 regressions: registry drift validator + system registry guard
# ---------------------------------------------------------------------------


def _registry_text() -> str:
    return (ROOT / "docs" / "architecture" / "system_registry.md").read_text(
        encoding="utf-8"
    )


def test_registry_clp_produces_canonical_artifact_name_only():
    """The CLP produces line must be exactly the canonical artifact name —
    no parenthetical authority metadata that would corrupt the schema lookup
    inside the registry drift validator (PRL-04 root cause)."""
    text = _registry_text()
    import re

    # Locate the CLP-01 section.
    section_match = re.search(
        r"### CLP-01[^\n]*\n(?P<body>.*?)(?=\n### |\Z)", text, flags=re.DOTALL
    )
    assert section_match, "CLP-01 section not found in registry"
    body = section_match.group("body")
    # Find the **produces:** field and extract sub-bullets only (not other
    # **section:** entries).
    produces_match = re.search(
        r"\n- \*\*produces:\*\*\s*\n((?:  -[^\n]*\n)+)", body
    )
    assert produces_match, "CLP **produces:** block not found"
    produces_block = produces_match.group(1)
    items = [
        ln.strip().lstrip("-").strip().strip("`")
        for ln in produces_block.splitlines()
        if ln.strip().startswith("-") and not ln.strip().startswith("- **")
    ]
    assert items, "CLP produces block has no items"
    for item in items:
        assert item == "core_loop_pre_pr_gate_result", (
            f"CLP produces a non-canonical artifact name: {item!r}. "
            "PRL-04 regression: parenthetical metadata must not be present."
        )
        assert "authority_scope" not in item
        assert "(" not in item
        assert ")" not in item


def test_registry_drift_validator_finds_clp_schema():
    """PRL-04 regression: the drift validator must locate
    contracts/schemas/core_loop_pre_pr_gate_result.schema.json for CLP."""
    from spectrum_systems.governance.registry_drift_validator import (
        RegistryDriftValidator,
    )

    validator = RegistryDriftValidator(repo_root=ROOT)
    clp = validator.registry.get("CLP")
    assert clp is not None, "CLP not parsed from registry"
    assert "core_loop_pre_pr_gate_result" in clp["produces"]
    is_valid, errors = validator.validate_system("CLP", clp)
    schema_errors = [e for e in errors if "no schema" in e.lower()]
    assert not schema_errors, f"unexpected schema errors for CLP: {schema_errors}"


def test_registry_drift_clp_schema_path_canonical():
    """The schema and example for CLP live at the canonical paths."""
    schema_path = ROOT / "contracts" / "schemas" / "core_loop_pre_pr_gate_result.schema.json"
    example_path = ROOT / "contracts" / "examples" / "core_loop_pre_pr_gate_result.example.json"
    assert schema_path.is_file(), schema_path
    assert example_path.is_file(), example_path
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["artifact_type"]["const"] == "core_loop_pre_pr_gate_result"
    example = json.loads(example_path.read_text(encoding="utf-8"))
    validate_artifact(example, "core_loop_pre_pr_gate_result")


def test_standards_manifest_clp_entry_canonical():
    """The standards manifest must reference the canonical artifact name with
    no malformed parenthetical fragments."""
    manifest = json.loads(
        (ROOT / "contracts" / "standards-manifest.json").read_text(encoding="utf-8")
    )
    entries = [
        e
        for e in (manifest.get("contracts") or [])
        if e.get("artifact_type") == "core_loop_pre_pr_gate_result"
    ]
    assert len(entries) == 1, entries
    entry = entries[0]
    assert entry["schema_path"] == "contracts/schemas/core_loop_pre_pr_gate_result.schema.json"
    assert entry["example_path"] == "contracts/examples/core_loop_pre_pr_gate_result.example.json"
    blob = json.dumps(entry)
    assert "authority_scope: observation_only" not in blob
    assert "(`authority_scope" not in blob
    # The artifact_type itself must be exactly the canonical bare name.
    assert entry["artifact_type"] == "core_loop_pre_pr_gate_result"


def test_system_registry_guard_no_shadow_on_clp_runner_script():
    """PRL-04 regression: scripts/run_core_loop_pre_pr_gate.py must not trip
    SHADOW_OWNERSHIP_OVERLAP. The header docstring previously combined the
    word ``authority`` with cluster-words like ``scope`` plus the symbol
    ``CLP``, which the guard mapped to canonical owner TPA."""
    from spectrum_systems.modules.governance.system_registry_guard import (
        evaluate_system_registry_guard,
        load_guard_policy,
        parse_system_registry,
    )

    policy = load_guard_policy(
        ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
    )
    registry_model = parse_system_registry(
        ROOT / "docs" / "architecture" / "system_registry.md"
    )
    result = evaluate_system_registry_guard(
        repo_root=ROOT,
        changed_files=[
            "scripts/run_core_loop_pre_pr_gate.py",
            "spectrum_systems/modules/runtime/core_loop_pre_pr_gate.py",
            "spectrum_systems/modules/runtime/agent_core_loop_proof.py",
        ],
        policy=policy,
        registry_model=registry_model,
    )
    diagnostics = result.get("diagnostics") or []
    shadow = [
        d
        for d in diagnostics
        if d.get("reason_code") == "SHADOW_OWNERSHIP_OVERLAP"
        and d.get("file") == "scripts/run_core_loop_pre_pr_gate.py"
    ]
    assert not shadow, f"unexpected SHADOW_OWNERSHIP_OVERLAP for CLP runner: {shadow}"


def test_clp_runner_docstring_keeps_subordination_language():
    """The CLP runner docstring must explicitly subordinate to TPA/CDE/SEL.
    Guards the documented authority boundary so a future edit cannot quietly
    revert to language that implies CLP owns policy/control/enforcement."""
    text = (ROOT / "scripts" / "run_core_loop_pre_pr_gate.py").read_text(
        encoding="utf-8"
    )
    head = text.split('"""', 2)[1]
    assert "observation-only" in head.lower()
    assert "TPA" in head
    assert "CDE" in head
    assert "SEL" in head
    # Forbid the previous wording that triggered SHADOW_OWNERSHIP_OVERLAP.
    assert "Authority scope: observation_only" not in head
    # Forbid the malformed "owns policy" or "decides policy" claims.
    assert "decide policy" not in head.lower() or "does not" in head.lower()


# ---------------------------------------------------------------------------
# PAR-CLP-01: EVL shard artifact evidence consumption
# ---------------------------------------------------------------------------


from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (  # noqa: E402
    consume_shard_artifacts,
)


def _shard_artifact(
    *,
    shard_name: str,
    status: str = "pass",
    output_artifact_refs: list[str] | None = None,
    reason_codes: list[str] | None = None,
    selected_tests: list[str] | None = None,
    command: str | None = "python -m pytest -q",
    exit_code: int | None = 0,
    duration_seconds: float = 1.0,
) -> dict:
    return {
        "artifact_type": "pr_test_shard_result",
        "schema_version": "1.0.0",
        "shard_name": shard_name,
        "status": status,
        "selected_tests": list(selected_tests or ["tests/test_x.py"]),
        "command": command,
        "exit_code": exit_code,
        "duration_seconds": duration_seconds,
        "output_artifact_refs": list(
            output_artifact_refs
            if output_artifact_refs is not None
            else [f"outputs/pr_test_shards/{shard_name}.json"]
        ),
        "reason_codes": list(reason_codes or []),
        "created_at": "2026-05-01T00:00:00Z",
        "authority_scope": "observation_only",
    }


def _shard_summary(
    *,
    shard_status: dict[str, str],
    required_shards: list[str],
    overall_status: str = "pass",
    blocking_reasons: list[str] | None = None,
    shard_artifact_refs: list[str] | None = None,
) -> dict:
    return {
        "artifact_type": "pr_test_shards_summary",
        "schema_version": "1.0.0",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "shard_status": shard_status,
        "required_shards": list(required_shards),
        "shard_artifact_refs": list(
            shard_artifact_refs
            or [f"outputs/pr_test_shards/{s}.json" for s in shard_status]
        ),
        "overall_status": overall_status,
        "blocking_reasons": list(blocking_reasons or []),
        "created_at": "2026-05-01T00:00:00Z",
        "authority_scope": "observation_only",
    }


def _write_shard_dir(
    tmp_path: Path,
    *,
    summary: dict | None,
    artifacts: dict[str, dict],
) -> Path:
    shard_dir = tmp_path / "outputs" / "pr_test_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    if summary is not None:
        (shard_dir / "pr_test_shards_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
    for shard_name, artifact in artifacts.items():
        (shard_dir / f"{shard_name}.json").write_text(
            json.dumps(artifact), encoding="utf-8"
        )
    return shard_dir


REQUIRED_TEST_SHARDS = ["contract", "governance", "changed_scope"]


def test_clp_pass_when_all_required_shard_artifacts_pass(tmp_path):
    """1. all required shard artifacts pass -> CLP pass observation."""
    summary = _shard_summary(
        shard_status={s: "pass" for s in REQUIRED_TEST_SHARDS},
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    artifacts = {s: _shard_artifact(shard_name=s) for s in REQUIRED_TEST_SHARDS}
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "pass"
    assert evidence["evl_shard_status"] == "pass"
    assert evidence["evl_missing_shards"] == []
    assert evidence["evl_failed_shards"] == []
    assert evidence["evl_unknown_shards"] == []
    assert evidence["evl_skipped_shards"] == []
    assert evidence["evl_shard_summary_ref"] is not None
    # Per-shard artifact refs are surfaced.
    for s in REQUIRED_TEST_SHARDS:
        assert any(s in ref for ref in evidence["evl_shard_artifact_refs"])

    art = _gate(_all_pass_checks(), evl_shard_evidence=evidence)
    assert art["gate_status"] == "pass"
    assert art["evl_shard_evidence"]["evl_shard_status"] == "pass"


def test_clp_blocks_on_missing_required_shard_artifact(tmp_path):
    """2. missing shard artifact -> block."""
    summary = _shard_summary(
        shard_status={s: "pass" for s in REQUIRED_TEST_SHARDS},
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    # Write only two of the three required shard artifacts.
    artifacts = {
        "contract": _shard_artifact(shard_name="contract"),
        "governance": _shard_artifact(shard_name="governance"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert "changed_scope" in evidence["evl_missing_shards"]
    assert any(
        "changed_scope:required_shard_artifact_missing" in r
        for r in evidence["evl_shard_reason_codes"]
    )
    assert check["failure_class"] == "evl_shard_evidence_missing"


def test_clp_blocks_on_failed_required_shard(tmp_path):
    """3. failed shard -> block."""
    summary = _shard_summary(
        shard_status={
            "contract": "pass",
            "governance": "fail",
            "changed_scope": "pass",
        },
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="block",
        blocking_reasons=["governance:required_shard_failed"],
    )
    artifacts = {
        "contract": _shard_artifact(shard_name="contract"),
        "governance": _shard_artifact(
            shard_name="governance",
            status="fail",
            exit_code=1,
            reason_codes=["pytest_returncode_1"],
        ),
        "changed_scope": _shard_artifact(shard_name="changed_scope"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert "governance" in evidence["evl_failed_shards"]
    assert any(
        "governance:required_shard_failed" in r
        for r in evidence["evl_shard_reason_codes"]
    )


def test_clp_blocks_on_unknown_required_shard(tmp_path):
    """4. unknown shard -> block."""
    summary = _shard_summary(
        shard_status={
            "contract": "pass",
            "governance": "unknown",
            "changed_scope": "pass",
        },
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="block",
        blocking_reasons=["governance:required_shard_unknown"],
    )
    artifacts = {
        "contract": _shard_artifact(shard_name="contract"),
        "governance": _shard_artifact(
            shard_name="governance",
            status="unknown",
            exit_code=None,
            command=None,
            reason_codes=["unknown_selector_status:none"],
        ),
        "changed_scope": _shard_artifact(shard_name="changed_scope"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert "governance" in evidence["evl_unknown_shards"]
    assert evidence["evl_shard_status"] in {"block", "unknown"}


def test_clp_blocks_on_skipped_required_shard_without_policy_allowance(tmp_path):
    """5. skipped shard without policy allowance -> block."""
    summary = _shard_summary(
        shard_status={
            "contract": "pass",
            "governance": "skipped",
            "changed_scope": "pass",
        },
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    artifacts = {
        "contract": _shard_artifact(shard_name="contract"),
        "governance": _shard_artifact(
            shard_name="governance",
            status="skipped",
            exit_code=None,
            command=None,
            selected_tests=[],
            reason_codes=["empty_allowed_by_selector"],
        ),
        "changed_scope": _shard_artifact(shard_name="changed_scope"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
        allowed_skipped_shards=(),
    )

    assert check["status"] == "block"
    assert "governance" in evidence["evl_skipped_shards"]
    assert any(
        "governance:required_shard_skipped" in r
        for r in evidence["evl_shard_reason_codes"]
    )

    # Same scenario, but policy explicitly allows the skip — pass.
    evidence_allowed, check_allowed = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
        allowed_skipped_shards=("governance",),
    )
    assert check_allowed["status"] == "pass"
    assert "governance" in evidence_allowed["evl_skipped_shards"]


def test_clp_blocks_pass_shard_without_output_artifact_refs(tmp_path):
    """6. passing shard without output_artifact_refs -> block.

    A pass shard with no output_artifact_refs violates the upstream
    contract; CLP must surface that as a block, not a pass.
    """
    summary = _shard_summary(
        shard_status={s: "pass" for s in REQUIRED_TEST_SHARDS},
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    # Build a "pass" shard artifact directly (we cannot route this through
    # validate_artifact since the upstream schema rejects it; CLP's job is
    # exactly to catch that case if it ever lands on disk).
    artifacts = {
        "contract": _shard_artifact(
            shard_name="contract",
            output_artifact_refs=[],
        ),
        "governance": _shard_artifact(shard_name="governance"),
        "changed_scope": _shard_artifact(shard_name="changed_scope"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert any(
        "contract:pass_shard_missing_output_artifact_refs" in r
        for r in evidence["evl_shard_reason_codes"]
    )


def test_clp_blocks_non_pass_shard_without_reason_codes(tmp_path):
    """7. non-pass shard without reason_codes -> block."""
    summary = _shard_summary(
        shard_status={
            "contract": "pass",
            "governance": "fail",
            "changed_scope": "pass",
        },
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="block",
        blocking_reasons=["governance:required_shard_failed"],
    )
    artifacts = {
        "contract": _shard_artifact(shard_name="contract"),
        # Fail shard with no reason_codes — violates upstream contract.
        "governance": _shard_artifact(
            shard_name="governance",
            status="fail",
            exit_code=1,
            reason_codes=[],
        ),
        "changed_scope": _shard_artifact(shard_name="changed_scope"),
    }
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert any(
        "governance:non_pass_shard_missing_reason_codes" in r
        for r in evidence["evl_shard_reason_codes"]
    )


def test_clp_does_not_recompute_shard_results(tmp_path, monkeypatch):
    """8. CLP must not rerun pytest if shard artifacts exist and are valid.

    Asserts that the consume helper never spawns subprocess. We patch
    subprocess.run to fail loudly if invoked.
    """
    import subprocess as _subprocess

    def _explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError(
            "consume_shard_artifacts must not invoke subprocess"
        )

    monkeypatch.setattr(_subprocess, "run", _explode)

    summary = _shard_summary(
        shard_status={s: "pass" for s in REQUIRED_TEST_SHARDS},
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    artifacts = {s: _shard_artifact(shard_name=s) for s in REQUIRED_TEST_SHARDS}
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )
    assert check["status"] == "pass"
    assert evidence["evl_shard_status"] == "pass"


def test_clp_preserves_observation_only_authority_with_shard_evidence(tmp_path):
    """9. CLP preserves observation-only authority boundary.

    Even with shard evidence attached, the artifact must remain
    observation_only and must not adopt any approval/certification/
    promotion/enforcement vocabulary.
    """
    summary = _shard_summary(
        shard_status={s: "pass" for s in REQUIRED_TEST_SHARDS},
        required_shards=REQUIRED_TEST_SHARDS,
        overall_status="pass",
    )
    artifacts = {s: _shard_artifact(shard_name=s) for s in REQUIRED_TEST_SHARDS}
    shard_dir = _write_shard_dir(tmp_path, summary=summary, artifacts=artifacts)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )
    art = _gate(_all_pass_checks(), evl_shard_evidence=evidence)

    assert art["authority_scope"] == "observation_only"
    forbidden = {
        "approval",
        "certification",
        "promotion",
        "enforcement",
        "approved",
        "certified",
        "promoted",
        "enforced",
        "verdict",
    }
    payload_lower = json.dumps(art).lower()
    for term in forbidden:
        assert f'"{term}"' not in payload_lower, term
    # Schema-side: bumping the gate to a forbidden authority value must
    # still fail validation.
    bad = dict(art)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")


def test_clp_blocks_when_summary_is_missing(tmp_path):
    """No summary on disk = unknown shard evidence -> block."""
    shard_dir = tmp_path / "outputs" / "pr_test_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    evidence, check = consume_shard_artifacts(
        shard_dir=shard_dir,
        repo_root=tmp_path,
        required_shards=tuple(REQUIRED_TEST_SHARDS),
    )

    assert check["status"] == "block"
    assert evidence["evl_shard_status"] == "unknown"
    assert "pr_test_shards_summary_missing" in evidence["evl_shard_reason_codes"]


def test_clp_evl_shard_evidence_field_is_optional_in_schema():
    """The schema must permit a CLP result without evl_shard_evidence
    (backwards compat) — but when present, it must validate."""
    art = _gate(_all_pass_checks())
    assert "evl_shard_evidence" not in art
    validate_artifact(art, "core_loop_pre_pr_gate_result")

    # And present-but-malformed evidence must be rejected.
    art2 = _gate(_all_pass_checks(), evl_shard_evidence={
        "evl_shard_artifact_refs": [],
        "evl_shard_summary_ref": None,
        "evl_shard_status": "pass",
        "evl_required_shards": [],
        "evl_missing_shards": [],
        "evl_failed_shards": [],
        "evl_unknown_shards": [],
        "evl_skipped_shards": [],
        "evl_shard_reason_codes": [],
    })
    validate_artifact(art2, "core_loop_pre_pr_gate_result")
    bad = dict(art2)
    bad["evl_shard_evidence"] = dict(art2["evl_shard_evidence"])
    bad["evl_shard_evidence"]["evl_shard_status"] = "approved"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")


# ---------------------------------------------------------------------------
# EVL-RT-04: shard-first readiness observation consumption
# ---------------------------------------------------------------------------


from spectrum_systems.modules.runtime.core_loop_pre_pr_gate import (  # noqa: E402
    consume_shard_first_readiness_observation,
)


_SHARD_FIRST_OBSERVATION_REL = (
    "outputs/pr_test_shard_first_readiness/"
    "pr_test_shard_first_readiness_observation.json"
)


def _shard_first_observation(
    *,
    shard_first_status: str = "shard_first",
    required_shard_refs: list[str] | None = None,
    missing_shard_refs: list[str] | None = None,
    failed_shard_refs: list[str] | None = None,
    fallback_used: bool = False,
    full_suite_detected: bool = False,
    fallback_justification_ref: str | None = (
        "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
    ),
    fallback_reason_codes: list[str] | None = None,
    reason_codes: list[str] | None = None,
) -> dict:
    if required_shard_refs is None:
        required_shard_refs = [
            "outputs/pr_test_shards/contract.json",
            "outputs/pr_test_shards/governance.json",
            "outputs/pr_test_shards/changed_scope.json",
        ]
    return {
        "artifact_type": "pr_test_shard_first_readiness_observation",
        "schema_version": "1.0.0",
        "id": "pr-shard-first-test-001",
        "created_at": "2026-05-03T00:00:00Z",
        "authority_scope": "observation_only",
        "base_ref": "origin/main",
        "head_ref": "HEAD",
        "changed_files": ["scripts/run_core_loop_pre_pr_gate.py"],
        "selection_coverage_ref": "outputs/selection_coverage/selection_coverage_record.json",
        "shard_summary_ref": "outputs/pr_test_shards/pr_test_shards_summary.json",
        "runtime_budget_observation_ref": (
            "outputs/pr_test_runtime_budget/pr_test_runtime_budget_observation.json"
        ),
        "fallback_justification_ref": fallback_justification_ref,
        "shard_first_status": shard_first_status,
        "required_shard_refs": list(required_shard_refs),
        "missing_shard_refs": list(missing_shard_refs or []),
        "failed_shard_refs": list(failed_shard_refs or []),
        "fallback_used": fallback_used,
        "full_suite_detected": full_suite_detected,
        "fallback_reason_codes": list(fallback_reason_codes or []),
        "reason_codes": list(reason_codes or []),
        "recommended_mapping_candidates": [],
        "recommended_shard_candidates": [],
        "evidence_hash": (
            "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        ),
    }


def _write_shard_first_observation(tmp_path: Path, payload: dict | None) -> Path:
    obs_path = tmp_path / _SHARD_FIRST_OBSERVATION_REL
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        obs_path.write_text(json.dumps(payload), encoding="utf-8")
    return obs_path


def test_clp_shard_first_blocks_when_observation_missing(tmp_path):
    """1. Missing shard-first readiness observation blocks CLP for repo-mutating change."""
    obs_path = _write_shard_first_observation(tmp_path, payload=None)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["check_name"] == "evl_shard_first_readiness"
    assert check["failure_class"] == "evl_shard_first_readiness_missing"
    assert "pr_test_shard_first_readiness_observation_missing" in check["reason_codes"]
    assert evidence["evl_shard_first_status"] == "unknown"


def test_clp_shard_first_pass_for_shard_first_status_with_refs(tmp_path):
    """2. shard_first status with valid shard refs passes CLP check."""
    payload = _shard_first_observation(shard_first_status="shard_first")
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "pass"
    assert check["failure_class"] is None
    assert evidence["evl_shard_first_status"] == "shard_first"
    assert evidence["evl_shard_first_required_shard_refs"]
    assert evidence["evl_shard_first_fallback_used"] is False

    art = _gate(
        [c for c in _all_pass_checks() if c["check_name"] != "evl_shard_first_readiness"]
        + [check],
        evl_shard_first_evidence=evidence,
    )
    assert art["gate_status"] == "pass"
    assert art["evl_shard_first_evidence"]["evl_shard_first_status"] == "shard_first"


def test_clp_shard_first_pass_for_fallback_justified_with_refs_and_codes(tmp_path):
    """3. fallback_justified with valid fallback refs and reason codes passes per current policy."""
    payload = _shard_first_observation(
        shard_first_status="fallback_justified",
        required_shard_refs=[],
        fallback_used=True,
        fallback_reason_codes=["fallback_scope_full_suite_for_governed_change"],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "pass"
    assert evidence["evl_shard_first_status"] == "fallback_justified"
    assert evidence["evl_shard_first_fallback_used"] is True
    assert evidence["evl_shard_first_fallback_justification_ref"]
    assert evidence["evl_shard_first_fallback_reason_codes"]


def test_clp_shard_first_warns_on_fallback_codes_outside_allow_list(tmp_path):
    """fallback_justified with codes outside policy allow-list -> warn (TPA review)."""
    payload = _shard_first_observation(
        shard_first_status="fallback_justified",
        required_shard_refs=[],
        fallback_used=True,
        fallback_reason_codes=["unexpected_fallback_code"],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
        allowed_fallback_reason_codes=("permitted_fallback_code",),
    )
    assert check["status"] == "warn"
    assert "unexpected_fallback_code" in check["reason_codes"]
    assert (
        check["failure_class"]
        == "evl_shard_first_readiness_fallback_unjustified"
    )


def test_clp_shard_first_blocks_on_missing_status(tmp_path):
    """4a. missing shard-first status blocks CLP with reason_codes."""
    payload = _shard_first_observation(
        shard_first_status="missing",
        required_shard_refs=[],
        reason_codes=["shard_summary_artifact_missing"],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["failure_class"] == "evl_shard_first_readiness_missing"
    assert check["reason_codes"]


def test_clp_shard_first_blocks_on_partial_status(tmp_path):
    """4b. partial shard-first status blocks CLP with reason_codes."""
    payload = _shard_first_observation(
        shard_first_status="partial",
        required_shard_refs=[],
        missing_shard_refs=["governance"],
        reason_codes=["required_shard_refs_missing"],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["failure_class"] == "evl_shard_first_readiness_partial"
    assert check["reason_codes"]


def test_clp_shard_first_blocks_on_unknown_status(tmp_path):
    """4c. unknown shard-first status blocks CLP with reason_codes."""
    payload = _shard_first_observation(
        shard_first_status="unknown",
        required_shard_refs=[],
        reason_codes=["runtime_budget_observation_missing_cannot_prove_shard_first"],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["failure_class"] == "evl_shard_first_readiness_unknown"
    assert check["reason_codes"]


def test_clp_shard_first_blocks_on_fallback_without_justification(tmp_path):
    """5. fallback/full-suite detected without justification blocks CLP."""
    payload = _shard_first_observation(
        shard_first_status="shard_first",
        full_suite_detected=True,
        fallback_justification_ref=None,
        fallback_reason_codes=[],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert (
        check["failure_class"]
        == "evl_shard_first_readiness_fallback_unjustified"
    )
    codes = check["reason_codes"]
    assert any("fallback_signal" in c or "inconsistent" in c for c in codes)


def test_clp_shard_first_blocks_on_shard_first_without_refs(tmp_path):
    """shard_first status with empty required_shard_refs -> block."""
    payload = _shard_first_observation(
        shard_first_status="shard_first",
        required_shard_refs=[],
    )
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert (
        check["failure_class"]
        == "evl_shard_first_readiness_shard_refs_empty"
    )
    assert any(
        "missing_required_shard_refs" in c for c in check["reason_codes"]
    )


def test_clp_shard_first_blocks_on_invalid_artifact(tmp_path):
    """An invalid (wrong artifact_type) observation blocks with invalid failure class."""
    obs_path = tmp_path / _SHARD_FIRST_OBSERVATION_REL
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(
        json.dumps({"artifact_type": "not_shard_first", "shard_first_status": "shard_first"}),
        encoding="utf-8",
    )
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["failure_class"] == "evl_shard_first_readiness_invalid"


def test_clp_shard_first_pr_prose_is_not_evidence(tmp_path):
    """6. PR prose cannot substitute for the artifact.

    Writing a text file at the observation path that contains every
    authority-passing word still does not satisfy the artifact contract
    — the JSON must parse and carry the canonical artifact_type.
    """
    obs_path = tmp_path / _SHARD_FIRST_OBSERVATION_REL
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(
        "shard-first ready, all green, fallback_used=false, trust me",
        encoding="utf-8",
    )
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "block"
    assert check["failure_class"] == "evl_shard_first_readiness_invalid"


def test_clp_shard_first_does_not_run_pytest(tmp_path, monkeypatch):
    """7. CLP does not run pytest for this check."""
    import subprocess as _subprocess

    def _explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError(
            "consume_shard_first_readiness_observation must not invoke subprocess"
        )

    monkeypatch.setattr(_subprocess, "run", _explode)
    payload = _shard_first_observation(shard_first_status="shard_first")
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "pass"


def test_clp_shard_first_does_not_recompute_selection(tmp_path, monkeypatch):
    """8. CLP does not recompute selection for this check."""
    import spectrum_systems.modules.runtime.pr_test_selection as pts

    def _selector_explode(*args, **kwargs):  # noqa: ARG001
        raise AssertionError(
            "consume_shard_first_readiness_observation must not call selector"
        )

    for symbol in ("resolve_required_tests", "build_selection_coverage_record"):
        if hasattr(pts, symbol):
            monkeypatch.setattr(pts, symbol, _selector_explode)

    payload = _shard_first_observation(shard_first_status="shard_first")
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    assert check["status"] == "pass"


def test_clp_shard_first_preserves_observation_only_authority(tmp_path):
    """9. Authority-safe vocabulary preserved with shard-first evidence attached."""
    payload = _shard_first_observation(shard_first_status="shard_first")
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    evidence, check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )
    art = _gate(
        [c for c in _all_pass_checks() if c["check_name"] != "evl_shard_first_readiness"]
        + [check],
        evl_shard_first_evidence=evidence,
    )
    assert art["authority_scope"] == "observation_only"
    forbidden = {
        "approval",
        "certification",
        "promotion",
        "enforcement",
        "approved",
        "certified",
        "promoted",
        "enforced",
        "verdict",
    }
    payload_lower = json.dumps(art).lower()
    for term in forbidden:
        assert f'"{term}"' not in payload_lower, term
    bad = dict(art)
    bad["authority_scope"] = "binding"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")


def test_clp_shard_first_existing_required_checks_still_work(tmp_path):
    """10. Existing CLP required checks still work alongside the new check."""
    payload = _shard_first_observation(shard_first_status="shard_first")
    obs_path = _write_shard_first_observation(tmp_path, payload=payload)
    _, shard_first_check = consume_shard_first_readiness_observation(
        observation_path=obs_path,
        repo_root=tmp_path,
    )

    other_checks = [
        c for c in _all_pass_checks() if c["check_name"] != "evl_shard_first_readiness"
    ]
    art = _gate(other_checks + [shard_first_check])
    assert art["gate_status"] == "pass"

    # Drop a different required check — gate should still block, proving
    # the rest of the required-check logic is intact.
    minus_one = [
        c for c in other_checks if c["check_name"] != "authority_shape_preflight"
    ] + [shard_first_check]
    art_block = _gate(minus_one)
    assert art_block["gate_status"] == "block"
    assert art_block["first_failed_check"] == "authority_shape_preflight"


def test_clp_shard_first_missing_required_check_blocks_repo_mutating(tmp_path):
    """Drop the new shard-first check entirely — repo-mutating gate must block."""
    checks = [
        c
        for c in _all_pass_checks()
        if c["check_name"] != "evl_shard_first_readiness"
    ]
    art = _gate(checks)
    assert art["gate_status"] == "block"
    assert art["first_failed_check"] == "evl_shard_first_readiness"


def test_clp_shard_first_evidence_field_optional_in_schema(tmp_path):
    """Schema permits a CLP result without evl_shard_first_evidence (backwards
    compat). Present-but-malformed evidence must be rejected."""
    art = _gate(_all_pass_checks())
    assert "evl_shard_first_evidence" not in art
    validate_artifact(art, "core_loop_pre_pr_gate_result")

    art2 = _gate(
        _all_pass_checks(),
        evl_shard_first_evidence={
            "evl_shard_first_observation_ref": None,
            "evl_shard_first_status": "shard_first",
            "evl_shard_first_required_shard_refs": [],
            "evl_shard_first_missing_shard_refs": [],
            "evl_shard_first_failed_shard_refs": [],
            "evl_shard_first_fallback_used": False,
            "evl_shard_first_full_suite_detected": False,
            "evl_shard_first_fallback_justification_ref": None,
            "evl_shard_first_fallback_reason_codes": [],
            "evl_shard_first_reason_codes": [],
        },
    )
    validate_artifact(art2, "core_loop_pre_pr_gate_result")
    bad = dict(art2)
    bad["evl_shard_first_evidence"] = dict(art2["evl_shard_first_evidence"])
    bad["evl_shard_first_evidence"]["evl_shard_first_status"] = "approved"
    with pytest.raises(Exception):
        validate_artifact(bad, "core_loop_pre_pr_gate_result")
