from __future__ import annotations

import copy

import pytest
from jsonschema import Draft202012Validator

from spectrum_systems.aex.engine import AEXEngine
from spectrum_systems.contracts import load_example, load_schema, validate_artifact
from spectrum_systems.modules.runtime.context_governed_flow import (
    ContextGovernedFlowError,
    create_tlc_context_handoff,
    evaluate_tpa_context_admissibility,
    execute_bounded_context_assembly,
    route_context_slice_to_tpa,
)
from spectrum_systems.modules.runtime.hnx_execution_state import evaluate_context_stage_semantics


def _context_request() -> dict[str, object]:
    return {
        "request_id": "req-ctx-001",
        "prompt_text": "Modify context contracts and context assembly runtime for governed context capability",
        "trace_id": "trace-ctx-001",
        "created_at": "2026-04-09T00:00:00Z",
        "produced_by": "codex",
        "target_paths": [
            "contracts/schemas/context_bundle_record.schema.json",
            "spectrum_systems/modules/runtime/context_governed_flow.py",
        ],
        "requested_outputs": ["patch", "tests"],
        "source_prompt_kind": "codex_build_request",
    }


def _recipe() -> dict[str, object]:
    return load_example("context_recipe_spec")


def _sources(*, stale: bool = False, untrusted: bool = False, incompatible: bool = False, count: int = 2) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for idx in range(count):
        rows.append(
            {
                "source_ref": f"source:{idx}",
                "source_type": "governance_doc" if not incompatible else "unknown_type",
                "source_schema_ref": "contracts/schemas/roadmap_artifact.schema.json" if not incompatible else "",
                "freshness_age_seconds": 999999 if stale else 100,
                "trust_class": "untrusted" if untrusted else "trusted",
                "classification": "internal",
            }
        )
    return rows


def _admitted_lineage() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    admitted = AEXEngine().admit_codex_request(_context_request())
    assert admitted.accepted
    assert admitted.build_admission_record is not None
    assert admitted.normalized_execution_request is not None
    handoff = create_tlc_context_handoff(
        run_id="run-ctx-001",
        objective="governed context mutation",
        branch_ref="refs/heads/main",
        emitted_at="2026-04-09T00:00:00Z",
        build_admission_record=admitted.build_admission_record,
        normalized_execution_request=admitted.normalized_execution_request,
    )
    return admitted.build_admission_record, admitted.normalized_execution_request, handoff


# CTX-01 contract tests

def test_context_contract_examples_validate() -> None:
    for name in (
        "context_bundle_record",
        "context_source_admission_record",
        "context_conflict_record",
        "context_recipe_spec",
    ):
        validate_artifact(load_example(name), name)


def test_context_bundle_record_rejects_unknown_properties_and_missing_required() -> None:
    schema = load_schema("context_bundle_record")
    validator = Draft202012Validator(schema)
    payload = load_example("context_bundle_record")

    unknown = copy.deepcopy(payload)
    unknown["unexpected"] = "x"
    assert list(validator.iter_errors(unknown))

    missing = copy.deepcopy(payload)
    missing.pop("lineage")
    assert list(validator.iter_errors(missing))


# CTX-02 HNX stage semantics

def test_hnx_context_stage_semantics_require_lineage_for_assembly() -> None:
    blocked = evaluate_context_stage_semantics(stage_name="context_assembly", artifacts={})
    assert blocked["allowed"] is False
    assert "MISSING_REQUIRED_LINEAGE_BUILD_ADMISSION_RECORD" in blocked["validation_failures"]

    ready = evaluate_context_stage_semantics(
        stage_name="context_assembly",
        artifacts={
            "build_admission_record": {"ok": True},
            "normalized_execution_request": {"ok": True},
            "tlc_handoff_record": {"ok": True},
            "tpa_slice_artifact": {"ok": True},
        },
    )
    assert ready["allowed"] is True


# CTX-03 AEX admission

def test_aex_marks_context_capability_repo_mutation() -> None:
    result = AEXEngine().admit_codex_request(_context_request())
    assert result.accepted is True
    assert result.build_admission_record is not None
    assert "context_capability_repo_mutation" in result.build_admission_record["reason_codes"]


# CTX-04 TLC routing

def test_tlc_routes_context_slice_to_tpa_and_rejects_missing_lineage() -> None:
    admission, normalized, handoff = _admitted_lineage()
    routed = route_context_slice_to_tpa(
        build_admission_record=admission,
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
    )
    assert routed["route_status"] == "accepted"
    assert routed["next_system"] == "TPA"

    with pytest.raises(ContextGovernedFlowError, match="lineage_invalid"):
        route_context_slice_to_tpa(
            build_admission_record=admission,
            normalized_execution_request=normalized,
            tlc_handoff_record={},
        )


# CTX-05 TPA admissibility

def test_tpa_emits_slice_artifact_for_admissible_sources() -> None:
    _admission, normalized, handoff = _admitted_lineage()
    out = evaluate_tpa_context_admissibility(
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        context_recipe_spec=_recipe(),
        source_metadata=_sources(),
    )
    assert out["tpa_scope_policy"]["allow"] is True
    assert out["tpa_slice_artifact"]["decision"] == "allow"
    assert out["tpa_observability_summary"]["admitted_source_count"] == 2


def test_tpa_rejects_stale_untrusted_incompatible_or_over_budget_sources_fail_closed() -> None:
    _admission, normalized, handoff = _admitted_lineage()
    for sources in (
        _sources(stale=True),
        _sources(untrusted=True),
        _sources(incompatible=True),
        _sources(count=5),
    ):
        out = evaluate_tpa_context_admissibility(
            normalized_execution_request=normalized,
            tlc_handoff_record=handoff,
            context_recipe_spec=_recipe(),
            source_metadata=sources,
        )
        assert out["tpa_slice_artifact"]["decision"] == "deny"


# CTX-06 PQX bounded execution

def test_pqx_rejects_missing_lineage_and_executes_with_approved_lineage_deterministically() -> None:
    admission, normalized, handoff = _admitted_lineage()
    tpa = evaluate_tpa_context_admissibility(
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        context_recipe_spec=_recipe(),
        source_metadata=_sources(),
    )

    with pytest.raises(ContextGovernedFlowError, match="repo_write_lineage_missing_or_invalid"):
        execute_bounded_context_assembly(
            build_admission_record={},
            normalized_execution_request=normalized,
            tlc_handoff_record=handoff,
            tpa_slice_artifact=tpa["tpa_slice_artifact"],
            context_recipe_spec=_recipe(),
            approved_sources=_sources(),
            created_at="2026-04-09T00:00:00Z",
        )

    first = execute_bounded_context_assembly(
        build_admission_record=admission,
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        tpa_slice_artifact=tpa["tpa_slice_artifact"],
        context_recipe_spec=_recipe(),
        approved_sources=_sources(),
        created_at="2026-04-09T00:00:00Z",
    )
    second = execute_bounded_context_assembly(
        build_admission_record=admission,
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        tpa_slice_artifact=tpa["tpa_slice_artifact"],
        context_recipe_spec=_recipe(),
        approved_sources=_sources(),
        created_at="2026-04-09T00:00:00Z",
    )
    assert first["context_bundle_record"]["bundle_manifest_hash"] == second["context_bundle_record"]["bundle_manifest_hash"]


# Boundary ownership checks

def test_boundary_ownership_no_duplicate_responsibility_in_context_flow() -> None:
    admission, normalized, handoff = _admitted_lineage()
    tlc = route_context_slice_to_tpa(
        build_admission_record=admission,
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
    )
    assert "decision" not in tlc

    tpa = evaluate_tpa_context_admissibility(
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        context_recipe_spec=_recipe(),
        source_metadata=_sources(),
    )
    assert "pqx_slice_execution_record" not in tpa

    pqx = execute_bounded_context_assembly(
        build_admission_record=admission,
        normalized_execution_request=normalized,
        tlc_handoff_record=handoff,
        tpa_slice_artifact=tpa["tpa_slice_artifact"],
        context_recipe_spec=_recipe(),
        approved_sources=_sources(),
        created_at="2026-04-09T00:00:00Z",
    )
    assert pqx["context_bundle_record"]["admissibility_status"] == "approved"
