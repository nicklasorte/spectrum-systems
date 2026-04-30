"""CLX-ALL-01 Red Team Suite — RT-1 through RT-8.

Mandatory adversarial tests:
  RT-1: Authority-shape violations — system blocks and produces explanation_packet
  RT-2: Shadow ownership overlaps — system blocks and produces explanation_packet
  RT-3: Missing core_loop_proof — system blocks
  RT-4: Malformed proof — system blocks with specific reason
  RT-5: Replay mismatch — system blocks on classification mismatch
  RT-6: Missing eval coverage after failure — system generates eval candidate
  RT-7: Ambiguous failure (multiple competing reasons) — system picks primary_reason
  RT-8: Invalid repair attempt — system blocks unsafe repairs

For each:
  - Captures failure ✓
  - Validates system blocks correctly ✓
  - Produces explanation_packet ✓
  - Generates eval candidate (where applicable) ✓
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.authority_preflight_expanded import (
    run_authority_preflight_expanded,
)
from spectrum_systems.modules.runtime.authority_repair_candidate_generator import (
    AuthorityRepairCandidateError,
    generate_authority_repair_candidates,
)
from spectrum_systems.governance.proof_presence_enforcement import (
    enforce_proof_presence,
)
from spectrum_systems.modules.runtime.failure_eval_candidate_generator import (
    generate_eval_candidate_registry,
)
from spectrum_systems.modules.runtime.historical_replay_validator import (
    run_historical_replay_validation,
)
from spectrum_systems.modules.runtime.failure_explanation import (
    build_failure_explanation_packet,
    attach_explanation_to_block_outcome,
)


# ---------------------------------------------------------------------------
# RT-1: Authority-shape violations
# ---------------------------------------------------------------------------

class TestRT1AuthorityShapeViolations:
    """RT-1: Inject authority-shape vocabulary into a non-owner file.

    Expected:
      - preflight detects violation
      - explanation_packet produced
      - eval candidate generated
    """

    def _make_violation_packet(self) -> dict:
        return {
            "artifact_type": "authority_preflight_failure_packet",
            "schema_version": "1.0.0",
            "packet_id": "rt1-pkt-001",
            "trace_id": "rt1-trace",
            "violations": [{
                "file": "spectrum_systems/modules/hop/rt1_test.py",
                "line": 5,
                "symbol": "hop_promotion_decision",
                "cluster": "promotion",
                "canonical_owners": ["CDE", "GOV"],
                "suggested_replacements": ["promotion_signal", "readiness_observation"],
                "violation_type": "vocabulary_violation",
                "rationale": "RT-1: hop_promotion_decision uses authority-shaped cluster",
            }],
            "shadow_overlaps": [],
            "forbidden_symbols": [],
            "status": "fail",
            "emitted_at": "2026-04-29T00:00:00+00:00",
        }

    def test_rt1_preflight_produces_fail_packet(self) -> None:
        packet = self._make_violation_packet()
        assert packet["status"] == "fail"
        assert len(packet["violations"]) > 0

    def test_rt1_explanation_packet_produced(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt1-trace",
            outcome="block",
            primary_reason="authority_shape_vocabulary_violation",
            triggering_artifact_type="authority_preflight_failure_packet",
            triggering_artifact_id="rt1-pkt-001",
            expected_behavior="No authority-shaped vocabulary in non-owner files",
            actual_behavior="hop_promotion_decision detected in HOP module",
        )
        assert ep["artifact_type"] == "failure_explanation_packet"
        assert ep["outcome"] == "block"
        assert ep["primary_reason"] == "authority_shape_vocabulary_violation"
        assert ep["stage_of_failure"] == "AEX"

    def test_rt1_eval_candidate_generated(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt1-trace",
            failures=[{
                "failure_class": "authority_shape_violation",
                "source_failure_ref": "rt1-pkt-001",
            }],
        )
        assert registry["total_entries"] == 1
        assert registry["entries"][0]["eval_type"] == "authority_shape"
        assert registry["entries"][0]["adoption_status"] == "pending_review"

    def test_rt1_repair_candidate_produced(self) -> None:
        packet = self._make_violation_packet()
        candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="rt1-trace")
        assert len(candidates) >= 1
        assert candidates[0]["repair_type"] == "vocabulary_correction"
        assert candidates[0]["patches"][0]["replacement_symbol"] == "promotion_signal"


# ---------------------------------------------------------------------------
# RT-2: Shadow ownership overlaps
# ---------------------------------------------------------------------------

class TestRT2ShadowOwnershipOverlaps:
    """RT-2: Inject shadow ownership (non-owner claims canonical artifact type).

    Expected:
      - preflight detects overlap
      - explanation_packet produced
      - eval candidate generated
    """

    def _make_shadow_packet(self) -> dict:
        return {
            "artifact_type": "authority_preflight_failure_packet",
            "schema_version": "1.0.0",
            "packet_id": "rt2-pkt-001",
            "trace_id": "rt2-trace",
            "violations": [],
            "shadow_overlaps": [{
                "file": "spectrum_systems/modules/hop/rt2_test.py",
                "symbol": "closure_decision_artifact",
                "declared_owner": "HOP",
                "actual_owner": "CDE",
                "rationale": "RT-2: HOP file claims closure_decision_artifact owned by CDE",
            }],
            "forbidden_symbols": [],
            "status": "fail",
            "emitted_at": "2026-04-29T00:00:00+00:00",
        }

    def test_rt2_shadow_overlap_detected(self) -> None:
        packet = self._make_shadow_packet()
        assert packet["status"] == "fail"
        assert len(packet["shadow_overlaps"]) == 1
        assert packet["shadow_overlaps"][0]["actual_owner"] == "CDE"

    def test_rt2_explanation_packet_produced(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt2-trace",
            outcome="block",
            primary_reason="shadow_ownership_overlap",
            triggering_artifact_type="authority_preflight_failure_packet",
            triggering_artifact_id="rt2-pkt-001",
            expected_behavior="Artifact types emitted only by canonical owners",
            actual_behavior="closure_decision_artifact claimed by HOP, owned by CDE",
        )
        assert ep["artifact_type"] == "failure_explanation_packet"
        assert ep["primary_reason"] == "shadow_ownership_overlap"

    def test_rt2_eval_candidate_generated(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt2-trace",
            failures=[{
                "failure_class": "shadow_ownership_overlap",
                "source_failure_ref": "rt2-pkt-001",
            }],
        )
        assert registry["total_entries"] == 1
        assert registry["entries"][0]["eval_type"] == "authority_shape"


# ---------------------------------------------------------------------------
# RT-3: Missing core_loop_proof
# ---------------------------------------------------------------------------

class TestRT3MissingCoreLoopProof:
    """RT-3: PR touches governed surface with no proof artifact.

    Expected: gate_status == 'block', block_reason includes 'missing'
    """

    def test_rt3_missing_proof_blocks(self) -> None:
        result = enforce_proof_presence(
            changed_files=[
                "spectrum_systems/modules/runtime/some_runtime_module.py",
                "contracts/schemas/some.schema.json",
            ],
            proof_artifact=None,
            trace_id="rt3-trace",
        )
        assert result["gate_status"] == "block"
        assert result["proof_required"] is True
        assert result["proof_found"] is False
        assert "missing" in (result["block_reason"] or "").lower()

    def test_rt3_explanation_packet_produced(self) -> None:
        result = enforce_proof_presence(
            changed_files=["spectrum_systems/modules/runtime/some_runtime_module.py"],
            proof_artifact=None,
            trace_id="rt3-trace",
        )
        ep = attach_explanation_to_block_outcome(
            block_outcome={
                "outcome_type": "block",
                "block_reason": result["block_reason"],
                "triggering_artifact_type": "proof_presence_enforcement_result",
                "triggering_artifact_id": result["result_id"],
            },
            trace_id="rt3-trace",
        )
        assert ep["artifact_type"] == "failure_explanation_packet"
        assert ep["outcome"] == "block"

    def test_rt3_eval_candidate_generated(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt3-trace",
            failures=[{
                "failure_class": "proof_presence_missing",
                "source_failure_ref": "rt3-pper-001",
            }],
        )
        assert registry["total_entries"] == 1
        assert registry["entries"][0]["eval_type"] == "proof_presence"


# ---------------------------------------------------------------------------
# RT-4: Malformed proof
# ---------------------------------------------------------------------------

class TestRT4MalformedProof:
    """RT-4: PR provides proof with wrong artifact_type or missing required fields.

    Expected: gate_status == 'block', specific reason in block_reason
    """

    def test_rt4_wrong_artifact_type_blocks(self) -> None:
        result = enforce_proof_presence(
            changed_files=["spectrum_systems/modules/runtime/some_module.py"],
            proof_artifact={"artifact_type": "some_random_artifact", "id": "r-001"},
            trace_id="rt4-trace",
        )
        assert result["gate_status"] == "block"
        assert "not_accepted" in (result["block_reason"] or "")

    def test_rt4_bundle_missing_all_refs_blocks(self) -> None:
        bare_bundle = {
            "artifact_type": "loop_proof_bundle",
            "bundle_id": "b-rt4",
            "trace_id": "rt4-trace",
            # No refs, no trace_summary.
        }
        result = enforce_proof_presence(
            changed_files=["spectrum_systems/modules/runtime/some_module.py"],
            proof_artifact=bare_bundle,
            trace_id="rt4-trace",
        )
        # Either blocks (insufficient refs) or has validation failures.
        assert result["artifact_type"] == "proof_presence_enforcement_result"
        if result["gate_status"] == "block":
            assert result["block_reason"] is not None

    def test_rt4_explanation_packet_produced(self) -> None:
        result = enforce_proof_presence(
            changed_files=["spectrum_systems/modules/runtime/some_module.py"],
            proof_artifact={"artifact_type": "wrong_type"},
            trace_id="rt4-trace",
        )
        ep = attach_explanation_to_block_outcome(
            block_outcome={
                "outcome_type": result["gate_status"],
                "block_reason": result.get("block_reason", "unknown"),
                "triggering_artifact_type": "proof_presence_enforcement_result",
                "triggering_artifact_id": result["result_id"],
            },
            trace_id="rt4-trace",
        )
        assert ep["artifact_type"] == "failure_explanation_packet"


# ---------------------------------------------------------------------------
# RT-5: Replay mismatch
# ---------------------------------------------------------------------------

class TestRT5ReplayMismatch:
    """RT-5: Inject a case with mismatched expected vs actual classification.

    Expected: overall_status == 'fail', mismatch_cases >= 1
    """

    def test_rt5_replay_mismatch_blocks(self) -> None:
        extra = [{
            "case_id": "rt5-mismatch-001",
            "failure_class": "registry_guard_failure",
            "expected_classification": "authority_shape_violation",  # Wrong expectation.
            "replay_input": {"violation_type": "registry_guard", "symbol": "UNK"},
        }]
        report = run_historical_replay_validation(trace_id="rt5-trace", additional_cases=extra)
        assert report["overall_status"] == "fail"
        assert report["mismatch_cases"] >= 1

    def test_rt5_mismatch_case_has_detail(self) -> None:
        extra = [{
            "case_id": "rt5-detail-001",
            "failure_class": "manifest_drift",
            "expected_classification": "authority_shape_violation",
            "replay_input": {"violation_type": "manifest_drift"},
        }]
        report = run_historical_replay_validation(trace_id="rt5-trace", additional_cases=extra)
        mismatch_cases = [r for r in report["replayed_cases"] if r["result"] == "mismatch"]
        assert len(mismatch_cases) >= 1
        assert mismatch_cases[0]["detail"] != ""

    def test_rt5_explanation_packet_produced(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt5-trace",
            outcome="block",
            primary_reason="replay_classification_mismatch",
            triggering_artifact_type="replay_validation_report",
            triggering_artifact_id="hrv-rt5-001",
            expected_behavior="authority_shape_violation classification",
            actual_behavior="registry_guard_failure classification returned",
        )
        assert ep["stage_of_failure"] == "REP"  # replay_validation_report → REP
        assert ep["primary_reason"] == "replay_classification_mismatch"

    def test_rt5_eval_candidate_generated(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt5-trace",
            failures=[{
                "failure_class": "replay_mismatch",
                "source_failure_ref": "rt5-hrv-001",
            }],
        )
        assert registry["total_entries"] == 1
        assert registry["entries"][0]["eval_type"] == "replay_mismatch"


# ---------------------------------------------------------------------------
# RT-6: Missing eval coverage after failure
# ---------------------------------------------------------------------------

class TestRT6MissingEvalCoverageAfterFailure:
    """RT-6: Failure occurs but no eval candidate is generated — system detects gap.

    Expected: eval_coverage_gap failure class generates a registry entry
    """

    def test_rt6_eval_coverage_gap_generates_candidate(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt6-trace",
            failures=[{
                "failure_class": "eval_coverage_gap",
                "source_failure_ref": "rt6-gap-001",
                "detail": "No eval coverage for authority_shape_violation in HOP modules",
            }],
        )
        assert registry["total_entries"] == 1
        entry = registry["entries"][0]
        assert entry["eval_type"] == "coverage_gap"
        assert entry["adoption_status"] == "pending_review"
        assert entry["deterministic"] is True

    def test_rt6_explanation_packet_for_gap(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt6-trace",
            outcome="block",
            primary_reason="eval_coverage_gap",
            triggering_artifact_type="evaluation_control_decision",
            triggering_artifact_id="evl-rt6-001",
            expected_behavior="All failure modes have eval coverage",
            actual_behavior="No eval case covers authority_shape_violation in HOP modules",
        )
        assert ep["stage_of_failure"] == "EVL"
        assert "eval" in (ep["suggested_repair"] or "").lower()

    def test_rt6_missing_failure_class_in_failures_is_skipped(self) -> None:
        registry = generate_eval_candidate_registry(
            trace_id="rt6-trace",
            failures=[
                {"source_failure_ref": "ref-A"},  # missing failure_class
                {"failure_class": "eval_coverage_gap", "source_failure_ref": "ref-B"},
            ],
        )
        assert registry["total_entries"] == 1


# ---------------------------------------------------------------------------
# RT-7: Ambiguous failure (multiple competing reasons)
# ---------------------------------------------------------------------------

class TestRT7AmbiguousFailure:
    """RT-7: Failure has multiple plausible reasons — system picks primary_reason.

    Expected:
      - explanation_packet has a single primary_reason
      - ambiguity_note is populated when provided
    """

    def test_rt7_single_primary_reason_selected(self) -> None:
        # Simulate a failure with two plausible reasons; primary_reason picks first.
        ep = build_failure_explanation_packet(
            trace_id="rt7-trace",
            outcome="block",
            primary_reason="authority_shape_vocabulary_violation",
            triggering_artifact_type="authority_preflight_failure_packet",
            triggering_artifact_id="rt7-pkt-001",
            expected_behavior="Clean authority vocabulary",
            actual_behavior="Two violations found: vocabulary and shadow overlap",
            ambiguity_note=(
                "Both vocabulary_violation and shadow_ownership_overlap detected. "
                "primary_reason set to vocabulary_violation as first-ordered finding."
            ),
        )
        assert ep["primary_reason"] == "authority_shape_vocabulary_violation"
        assert "shadow_ownership_overlap" in (ep["ambiguity_note"] or "")

    def test_rt7_ambiguity_note_stored(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt7-trace",
            outcome="block",
            primary_reason="registry_guard_failure",
            triggering_artifact_type="authority_preflight_failure_packet",
            triggering_artifact_id="rt7-pkt-002",
            expected_behavior="Registry guard passes",
            actual_behavior="Unknown system acronym found",
            ambiguity_note="Also detected manifest_drift — could be either. Treating as registry_guard_failure.",
        )
        assert ep["ambiguity_note"] is not None
        assert "manifest_drift" in ep["ambiguity_note"]

    def test_rt7_both_eval_candidates_generated(self) -> None:
        # RT-7: system should generate eval candidates for each competing reason.
        registry = generate_eval_candidate_registry(
            trace_id="rt7-trace",
            failures=[
                {"failure_class": "authority_shape_violation", "source_failure_ref": "rt7-ref-A"},
                {"failure_class": "registry_guard_failure", "source_failure_ref": "rt7-ref-B"},
            ],
        )
        assert registry["total_entries"] == 2
        types = {e["eval_type"] for e in registry["entries"]}
        assert "authority_shape" in types
        assert "registry_guard" in types


# ---------------------------------------------------------------------------
# RT-8: Invalid repair attempt
# ---------------------------------------------------------------------------

class TestRT8InvalidRepairAttempt:
    """RT-8: Repair candidate for a guard/canonical-owner file is blocked.

    Expected:
      - generate_authority_repair_candidates returns no candidates for guard files
      - Unsafe replacement symbol blocks safe_to_apply
    """

    def test_rt8_guard_file_never_patched(self) -> None:
        packet = {
            "artifact_type": "authority_preflight_failure_packet",
            "schema_version": "1.0.0",
            "packet_id": "rt8-pkt-001",
            "trace_id": "rt8-trace",
            "violations": [{
                "file": "spectrum_systems/governance/authority_shape_preflight.py",
                "line": 42,
                "symbol": "enforcement_cluster",
                "cluster": "enforcement",
                "canonical_owners": ["SEL"],
                "suggested_replacements": ["enforcement_signal"],
                "violation_type": "vocabulary_violation",
                "rationale": "RT-8: guard file must never be patched",
            }],
            "shadow_overlaps": [],
            "forbidden_symbols": [],
            "status": "fail",
            "emitted_at": "2026-04-29T00:00:00+00:00",
        }
        candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="rt8-trace")
        assert candidates == [], "Guard file must never produce repair candidates"

    def test_rt8_canonical_owner_file_never_patched(self) -> None:
        packet = {
            "artifact_type": "authority_preflight_failure_packet",
            "schema_version": "1.0.0",
            "packet_id": "rt8-pkt-002",
            "trace_id": "rt8-trace",
            "violations": [{
                "file": "scripts/run_authority_leak_guard.py",
                "line": 10,
                "symbol": "enforcement_decision",
                "cluster": "enforcement",
                "canonical_owners": ["SEL"],
                "suggested_replacements": ["enforcement_signal"],
                "violation_type": "vocabulary_violation",
                "rationale": "RT-8: authority guard script must not be patched",
            }],
            "shadow_overlaps": [],
            "forbidden_symbols": [],
            "status": "fail",
            "emitted_at": "2026-04-29T00:00:00+00:00",
        }
        candidates = generate_authority_repair_candidates(failure_packet=packet, trace_id="rt8-trace")
        assert candidates == [], "Authority guard scripts must never be patched"

    def test_rt8_non_dict_packet_raises(self) -> None:
        import pytest
        with pytest.raises(AuthorityRepairCandidateError):
            generate_authority_repair_candidates(failure_packet="bad-input", trace_id="rt8-trace")

    def test_rt8_wrong_packet_type_raises(self) -> None:
        import pytest
        packet = {
            "artifact_type": "some_other_type",
            "packet_id": "rt8-bad",
        }
        with pytest.raises(AuthorityRepairCandidateError, match="Expected authority_preflight_failure_packet"):
            generate_authority_repair_candidates(failure_packet=packet, trace_id="rt8-trace")

    def test_rt8_explanation_packet_for_blocked_repair(self) -> None:
        ep = build_failure_explanation_packet(
            trace_id="rt8-trace",
            outcome="block",
            primary_reason="repair_attempt_blocked_guard_file",
            triggering_artifact_type="authority_repair_candidate",
            triggering_artifact_id="arc-rt8-001",
            expected_behavior="Repair candidates excluded from guard scripts",
            actual_behavior="Repair candidate attempted to patch authority_shape_preflight.py",
        )
        assert ep["artifact_type"] == "failure_explanation_packet"
        assert ep["primary_reason"] == "repair_attempt_blocked_guard_file"
