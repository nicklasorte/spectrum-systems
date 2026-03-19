"""Tests for Artifact Lineage System (Prompt BS).

Covers:
- Full valid chain: simulation_input → simulation_output → evidence_pack →
  reasoning_trace → adversarial_result → synthesis → decision → slo_evaluation
- Schema validation (valid and invalid artifacts)
- Orphan detection
- Missing parent detection
- Circular dependency detection
- Incorrect lineage_depth
- Inconsistent root_artifact_ids
- Required parent type enforcement
- create_artifact_metadata helper
- link_artifacts enforcement
- compute_lineage_depth edge cases
- compute_root_artifacts edge cases
- validate_lineage_chain scenarios
- build_full_lineage_graph
- trace_to_root / trace_to_leaves
- detect_lineage_gaps
- enforce_no_orphans
- validate_full_registry
- CLI exit codes (0/1/2)
- SLO integration correctness
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.artifact_lineage import (  # noqa: E402
    ARTIFACT_TYPES,
    _REQUIRED_PARENT_TYPES,
    build_full_lineage_graph,
    compute_lineage_depth,
    compute_root_artifacts,
    create_artifact_metadata,
    detect_lineage_gaps,
    enforce_no_orphans,
    link_artifacts,
    trace_to_leaves,
    trace_to_root,
    validate_against_schema,
    validate_full_registry,
    validate_lineage_chain,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_NOW = "2026-03-19T12:00:00+00:00"


def _mk(
    artifact_id: str,
    artifact_type: str,
    parent_artifact_ids=None,
    lineage_depth: int = 0,
    root_artifact_ids=None,
    lineage_valid: bool = True,
    lineage_errors=None,
    created_by: str = "test-module",
    version: str = "1.0.0",
    created_at: str = _NOW,
) -> Dict[str, Any]:
    """Build a minimal valid artifact metadata dict."""
    return {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "parent_artifact_ids": parent_artifact_ids or [],
        "created_at": created_at,
        "created_by": created_by,
        "version": version,
        "lineage_depth": lineage_depth,
        "root_artifact_ids": root_artifact_ids if root_artifact_ids is not None else (
            [artifact_id] if not parent_artifact_ids else []
        ),
        "lineage_valid": lineage_valid,
        "lineage_errors": lineage_errors or [],
    }


def _full_chain_registry() -> Dict[str, Dict[str, Any]]:
    """Build a complete valid chain registry."""
    sim_in = _mk("SIM-IN-001", "simulation_input", lineage_depth=0, root_artifact_ids=["SIM-IN-001"])
    sim_out = _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1, root_artifact_ids=["SIM-IN-001"])
    ev_pack = _mk("EV-001", "evidence_pack", ["SIM-OUT-001"], lineage_depth=2, root_artifact_ids=["SIM-IN-001"])
    reas_trace = _mk("RT-001", "reasoning_trace", ["EV-001"], lineage_depth=3, root_artifact_ids=["SIM-IN-001"])
    adv_result = _mk("ADV-001", "adversarial_result", ["RT-001"], lineage_depth=4, root_artifact_ids=["SIM-IN-001"])
    synthesis = _mk("SYN-001", "synthesis", ["EV-001", "ADV-001"], lineage_depth=5, root_artifact_ids=["SIM-IN-001"])
    decision = _mk("DEC-001", "decision", ["SYN-001"], lineage_depth=6, root_artifact_ids=["SIM-IN-001"])
    slo_eval = _mk("SLO-001", "slo_evaluation", ["DEC-001", "SYN-001"], lineage_depth=7, root_artifact_ids=["SIM-IN-001"])

    return {
        "SIM-IN-001": sim_in,
        "SIM-OUT-001": sim_out,
        "EV-001": ev_pack,
        "RT-001": reas_trace,
        "ADV-001": adv_result,
        "SYN-001": synthesis,
        "DEC-001": decision,
        "SLO-001": slo_eval,
    }


# ===========================================================================
# 1. ARTIFACT TYPE CONSTANTS
# ===========================================================================


class TestArtifactTypes:
    def test_all_expected_types_present(self):
        expected = {
            "simulation_input", "simulation_output", "evidence_pack",
            "reasoning_trace", "adversarial_result", "synthesis",
            "decision", "slo_evaluation",
        }
        assert expected == ARTIFACT_TYPES

    def test_artifact_types_is_frozenset(self):
        assert isinstance(ARTIFACT_TYPES, frozenset)

    def test_required_parent_types_covers_non_root(self):
        non_root_types = ARTIFACT_TYPES - {"simulation_input"}
        for t in non_root_types:
            assert t in _REQUIRED_PARENT_TYPES, f"{t} missing from _REQUIRED_PARENT_TYPES"


# ===========================================================================
# 2. SCHEMA VALIDATION
# ===========================================================================


class TestSchemaValidation:
    def test_valid_root_artifact_passes_schema(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        valid, errors = validate_against_schema(artifact)
        assert valid, errors

    def test_valid_simulation_output_passes_schema(self):
        artifact = _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1, root_artifact_ids=["SIM-IN-001"])
        valid, errors = validate_against_schema(artifact)
        assert valid, errors

    def test_missing_artifact_id_fails_schema(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        del artifact["artifact_id"]
        valid, errors = validate_against_schema(artifact)
        assert not valid
        assert errors

    def test_unknown_artifact_type_fails_schema(self):
        artifact = _mk("X-001", "unknown_type")
        valid, errors = validate_against_schema(artifact)
        assert not valid

    def test_negative_lineage_depth_fails_schema(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        artifact["lineage_depth"] = -1
        valid, errors = validate_against_schema(artifact)
        assert not valid

    def test_additional_properties_rejected(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        artifact["extra_field"] = "not_allowed"
        valid, errors = validate_against_schema(artifact)
        assert not valid

    def test_missing_required_field_lineage_valid_fails(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        del artifact["lineage_valid"]
        valid, errors = validate_against_schema(artifact)
        assert not valid

    def test_all_artifact_types_valid_in_schema(self):
        for atype in ARTIFACT_TYPES:
            artifact = _mk(f"ART-{atype}", atype)
            valid, errors = validate_against_schema(artifact)
            assert valid, f"{atype}: {errors}"

    def test_lineage_errors_must_be_list(self):
        artifact = _mk("SIM-IN-001", "simulation_input")
        artifact["lineage_errors"] = "not-a-list"
        valid, errors = validate_against_schema(artifact)
        assert not valid


# ===========================================================================
# 3. CREATE ARTIFACT METADATA
# ===========================================================================


class TestCreateArtifactMetadata:
    def test_root_artifact_depth_zero(self):
        meta = create_artifact_metadata(
            "SIM-IN-001", "simulation_input", [], "test-module", "1.0.0"
        )
        assert meta["lineage_depth"] == 0

    def test_root_artifact_is_own_root(self):
        meta = create_artifact_metadata(
            "SIM-IN-001", "simulation_input", [], "test-module", "1.0.0"
        )
        assert meta["root_artifact_ids"] == ["SIM-IN-001"]

    def test_child_depth_one(self):
        reg = {"SIM-IN-001": _mk("SIM-IN-001", "simulation_input")}
        meta = create_artifact_metadata(
            "SIM-OUT-001", "simulation_output", ["SIM-IN-001"], "test-module", "1.0.0",
            registry=reg,
        )
        assert meta["lineage_depth"] == 1

    def test_child_root_ids_point_to_root(self):
        reg = {"SIM-IN-001": _mk("SIM-IN-001", "simulation_input")}
        meta = create_artifact_metadata(
            "SIM-OUT-001", "simulation_output", ["SIM-IN-001"], "test-module", "1.0.0",
            registry=reg,
        )
        assert "SIM-IN-001" in meta["root_artifact_ids"]

    def test_invalid_artifact_type_raises(self):
        with pytest.raises(ValueError, match="Unknown artifact_type"):
            create_artifact_metadata("X-001", "bad_type", [], "m", "1.0")

    def test_empty_artifact_id_raises(self):
        with pytest.raises(ValueError, match="artifact_id"):
            create_artifact_metadata("", "simulation_input", [], "m", "1.0")

    def test_lineage_valid_false_on_bad_chain(self):
        # simulation_input with a parent — invalid
        reg = {"GHOST": _mk("GHOST", "simulation_input")}
        meta = create_artifact_metadata(
            "SIM-IN-BAD", "simulation_input", ["GHOST"], "m", "1.0",
            registry=reg,
        )
        assert not meta["lineage_valid"]
        assert meta["lineage_errors"]

    def test_created_at_default_is_set(self):
        meta = create_artifact_metadata("SIM-IN-001", "simulation_input", [], "m", "1.0")
        assert meta["created_at"]

    def test_custom_created_at_passthrough(self):
        meta = create_artifact_metadata(
            "SIM-IN-001", "simulation_input", [], "m", "1.0", created_at="2026-01-01T00:00:00+00:00"
        )
        assert meta["created_at"] == "2026-01-01T00:00:00+00:00"


# ===========================================================================
# 4. LINK ARTIFACTS
# ===========================================================================


class TestLinkArtifacts:
    def test_valid_link_passes(self):
        reg = {"A": _mk("A", "simulation_input")}
        link_artifacts(["A"], "B", reg)  # Should not raise

    def test_missing_parent_raises(self):
        reg = {"A": _mk("A", "simulation_input")}
        with pytest.raises(ValueError, match="missing parents"):
            link_artifacts(["A", "MISSING"], "B", reg)

    def test_empty_parent_list_passes(self):
        reg = {}
        link_artifacts([], "B", reg)  # Root artifact — OK

    def test_all_missing_raises(self):
        reg = {}
        with pytest.raises(ValueError, match="missing parents"):
            link_artifacts(["GHOST-1", "GHOST-2"], "C", reg)


# ===========================================================================
# 5. COMPUTE LINEAGE DEPTH
# ===========================================================================


class TestComputeLineageDepth:
    def test_no_parents_is_zero(self):
        assert compute_lineage_depth("A", [], {}) == 0

    def test_one_parent_at_depth_zero(self):
        reg = {"P": _mk("P", "simulation_input", lineage_depth=0)}
        assert compute_lineage_depth("C", ["P"], reg) == 1

    def test_max_parent_depth_used(self):
        reg = {
            "P1": _mk("P1", "simulation_input", lineage_depth=0),
            "P2": _mk("P2", "simulation_output", ["P1"], lineage_depth=3),
        }
        assert compute_lineage_depth("C", ["P1", "P2"], reg) == 4

    def test_unknown_parent_handled(self):
        # Parent not in registry — treated as depth 1
        assert compute_lineage_depth("C", ["UNKNOWN"], {}) == 1

    def test_deep_chain_depth(self):
        reg = {}
        prev = "SIM-IN"
        reg[prev] = _mk(prev, "simulation_input", lineage_depth=0)
        for i in range(1, 8):
            current = f"ART-{i}"
            reg[current] = _mk(current, "simulation_output", [prev], lineage_depth=i)
            prev = current
        # Next child should be depth 8
        assert compute_lineage_depth("FINAL", [prev], reg) == 8


# ===========================================================================
# 6. COMPUTE ROOT ARTIFACTS
# ===========================================================================


class TestComputeRootArtifacts:
    def test_root_artifact_returns_self(self):
        roots = compute_root_artifacts("SIM-IN-001", [], {})
        assert roots == ["SIM-IN-001"]

    def test_child_returns_root(self):
        reg = {"SIM-IN-001": _mk("SIM-IN-001", "simulation_input")}
        roots = compute_root_artifacts("SIM-OUT-001", ["SIM-IN-001"], reg)
        assert "SIM-IN-001" in roots

    def test_deep_chain_returns_original_root(self):
        reg = _full_chain_registry()
        roots = compute_root_artifacts("SLO-001", ["DEC-001", "SYN-001"], reg)
        assert "SIM-IN-001" in roots

    def test_multiple_roots_deduplicated(self):
        reg = {
            "ROOT-A": _mk("ROOT-A", "simulation_input"),
            "ROOT-B": _mk("ROOT-B", "simulation_input"),
        }
        # Two parents each pointing to different roots via intermediate
        roots = compute_root_artifacts("CHILD", ["ROOT-A", "ROOT-B"], reg)
        assert sorted(roots) == ["ROOT-A", "ROOT-B"]

    def test_cycle_does_not_infinite_loop(self):
        # Artificially create a cycle in registry
        reg = {
            "A": _mk("A", "simulation_input", ["B"]),
            "B": _mk("B", "simulation_output", ["A"]),
        }
        # Should return without hanging
        roots = compute_root_artifacts("A", ["B"], reg)
        assert isinstance(roots, list)


# ===========================================================================
# 7. VALIDATE LINEAGE CHAIN
# ===========================================================================


class TestValidateLineageChain:
    def test_valid_root_passes(self):
        valid, errors = validate_lineage_chain("SIM-IN-001", "simulation_input", [], {})
        assert valid
        assert errors == []

    def test_root_with_parents_fails(self):
        reg = {"P": _mk("P", "simulation_input")}
        valid, errors = validate_lineage_chain("SIM-IN-001", "simulation_input", ["P"], reg)
        assert not valid
        assert any("must have no parents" in e for e in errors)

    def test_non_root_without_parents_fails(self):
        valid, errors = validate_lineage_chain("SIM-OUT-001", "simulation_output", [], {})
        assert not valid
        assert any("orphan" in e.lower() or "no parents" in e.lower() for e in errors)

    def test_missing_parent_error(self):
        valid, errors = validate_lineage_chain("SIM-OUT-001", "simulation_output", ["MISSING"], {})
        assert not valid
        assert any("missing" in e.lower() for e in errors)

    def test_wrong_parent_type_fails(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
        }
        # evidence_pack must link to simulation_output, not simulation_input directly
        valid, errors = validate_lineage_chain("EV-001", "evidence_pack", ["SIM-IN-001"], reg)
        assert not valid
        assert any("simulation_output" in e for e in errors)

    def test_correct_parent_type_passes(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1),
        }
        valid, errors = validate_lineage_chain("EV-001", "evidence_pack", ["SIM-OUT-001"], reg)
        assert valid, errors

    def test_synthesis_requires_both_parent_types(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1),
            "EV-001": _mk("EV-001", "evidence_pack", ["SIM-OUT-001"], lineage_depth=2),
        }
        # Only evidence_pack, missing adversarial_result
        valid, errors = validate_lineage_chain("SYN-001", "synthesis", ["EV-001"], reg)
        assert not valid
        assert any("adversarial_result" in e for e in errors)

    def test_synthesis_with_both_parent_types_passes(self):
        reg = _full_chain_registry()
        valid, errors = validate_lineage_chain(
            "SYN-001", "synthesis", ["EV-001", "ADV-001"],
            {k: v for k, v in reg.items() if k != "SYN-001"},
        )
        assert valid, errors

    def test_circular_dependency_detected(self):
        reg = {
            "A": _mk("A", "simulation_input", ["B"]),
            "B": _mk("B", "simulation_output", ["A"]),
        }
        valid, errors = validate_lineage_chain("A", "simulation_input", ["B"], reg)
        assert not valid
        assert any("circular" in e.lower() for e in errors)

    def test_slo_evaluation_requires_decision_and_synthesis(self):
        reg = _full_chain_registry()
        # Missing synthesis parent
        valid, errors = validate_lineage_chain(
            "SLO-001", "slo_evaluation", ["DEC-001"],
            {k: v for k, v in reg.items() if k != "SLO-001"},
        )
        assert not valid
        assert any("synthesis" in e for e in errors)


# ===========================================================================
# 8. FULL VALID CHAIN
# ===========================================================================


class TestFullValidChain:
    def test_full_chain_validates_cleanly(self):
        reg = _full_chain_registry()
        result = validate_full_registry(reg)
        assert result["valid"], result["artifact_results"]
        assert result["total_errors"] == 0

    def test_full_chain_no_orphans(self):
        reg = _full_chain_registry()
        # Should not raise
        enforce_no_orphans(reg)

    def test_full_chain_no_gaps(self):
        reg = _full_chain_registry()
        gaps = detect_lineage_gaps(reg)
        assert gaps["orphan_artifacts"] == []
        assert gaps["missing_parents"] == {}
        assert gaps["broken_chains"] == []

    def test_slo_can_trace_to_root(self):
        reg = _full_chain_registry()
        path = trace_to_root("SLO-001", reg)
        assert "SLO-001" in path
        assert "SIM-IN-001" in path

    def test_simulation_input_traces_to_leaves(self):
        reg = _full_chain_registry()
        leaves = trace_to_leaves("SIM-IN-001", reg)
        assert "SLO-001" in leaves
        assert "DEC-001" in leaves

    def test_lineage_depths_correct_in_chain(self):
        reg = _full_chain_registry()
        expected_depths = {
            "SIM-IN-001": 0,
            "SIM-OUT-001": 1,
            "EV-001": 2,
            "RT-001": 3,
            "ADV-001": 4,
            "SYN-001": 5,
            "DEC-001": 6,
            "SLO-001": 7,
        }
        for aid, depth in expected_depths.items():
            assert reg[aid]["lineage_depth"] == depth, f"{aid} depth mismatch"


# ===========================================================================
# 9. BUILD FULL LINEAGE GRAPH
# ===========================================================================


class TestBuildFullLineageGraph:
    def test_root_has_children(self):
        reg = _full_chain_registry()
        graph = build_full_lineage_graph(reg)
        assert "SIM-OUT-001" in graph["SIM-IN-001"]

    def test_leaf_has_no_children(self):
        reg = _full_chain_registry()
        graph = build_full_lineage_graph(reg)
        assert graph.get("SLO-001") == []

    def test_synthesis_has_child_decision(self):
        reg = _full_chain_registry()
        graph = build_full_lineage_graph(reg)
        assert "DEC-001" in graph["SYN-001"]

    def test_empty_registry_empty_graph(self):
        graph = build_full_lineage_graph({})
        assert graph == {}

    def test_all_artifacts_present_in_graph(self):
        reg = _full_chain_registry()
        graph = build_full_lineage_graph(reg)
        for aid in reg:
            assert aid in graph


# ===========================================================================
# 10. ORPHAN DETECTION
# ===========================================================================


class TestOrphanDetection:
    def test_orphan_simulation_output_detected(self):
        reg = {
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output"),  # No parents
        }
        gaps = detect_lineage_gaps(reg)
        assert "SIM-OUT-001" in gaps["orphan_artifacts"]

    def test_enforce_no_orphans_raises(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output"),  # No parents — orphan
        }
        with pytest.raises(ValueError, match="[Oo]rphan"):
            enforce_no_orphans(reg)

    def test_simulation_input_with_no_parents_not_orphan(self):
        reg = {"SIM-IN-001": _mk("SIM-IN-001", "simulation_input")}
        # Should not raise
        enforce_no_orphans(reg)
        gaps = detect_lineage_gaps(reg)
        assert "SIM-IN-001" not in gaps["orphan_artifacts"]

    def test_multiple_orphans_all_detected(self):
        reg = {
            "EV-001": _mk("EV-001", "evidence_pack"),
            "DEC-001": _mk("DEC-001", "decision"),
        }
        gaps = detect_lineage_gaps(reg)
        assert "EV-001" in gaps["orphan_artifacts"]
        assert "DEC-001" in gaps["orphan_artifacts"]


# ===========================================================================
# 11. MISSING PARENT DETECTION
# ===========================================================================


class TestMissingParentDetection:
    def test_missing_parent_in_gaps(self):
        reg = {
            "SIM-OUT-001": _mk(
                "SIM-OUT-001", "simulation_output", ["SIM-IN-MISSING"]
            ),
        }
        gaps = detect_lineage_gaps(reg)
        assert "SIM-OUT-001" in gaps["missing_parents"]
        assert "SIM-IN-MISSING" in gaps["missing_parents"]["SIM-OUT-001"]

    def test_existing_parent_not_reported_missing(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1),
        }
        gaps = detect_lineage_gaps(reg)
        assert "SIM-OUT-001" not in gaps["missing_parents"]

    def test_validate_lineage_chain_reports_missing_parents(self):
        valid, errors = validate_lineage_chain(
            "SIM-OUT-001", "simulation_output", ["GHOST-PARENT"], {}
        )
        assert not valid
        assert any("GHOST-PARENT" in e for e in errors)


# ===========================================================================
# 12. CIRCULAR DEPENDENCY DETECTION
# ===========================================================================


class TestCircularDependencyDetection:
    def test_direct_cycle(self):
        reg = {
            "A": _mk("A", "simulation_input", ["B"]),
            "B": _mk("B", "simulation_output", ["A"]),
        }
        valid, errors = validate_lineage_chain("A", "simulation_input", ["B"], reg)
        assert not valid
        assert any("circular" in e.lower() for e in errors)

    def test_indirect_cycle(self):
        reg = {
            "A": _mk("A", "simulation_input", ["C"]),
            "B": _mk("B", "simulation_output", ["A"]),
            "C": _mk("C", "evidence_pack", ["B"]),
        }
        valid, errors = validate_lineage_chain("A", "simulation_input", ["C"], reg)
        assert not valid
        assert any("circular" in e.lower() for e in errors)

    def test_no_cycle_valid_chain(self):
        reg = _full_chain_registry()
        valid, errors = validate_lineage_chain(
            "SLO-001", "slo_evaluation", ["DEC-001", "SYN-001"],
            {k: v for k, v in reg.items() if k != "SLO-001"},
        )
        assert valid

    def test_root_artifacts_cycle_guard(self):
        # Cycle in registry — compute_root_artifacts must not loop
        reg = {
            "A": _mk("A", "simulation_input", ["B"]),
            "B": _mk("B", "simulation_output", ["A"]),
        }
        result = compute_root_artifacts("A", ["B"], reg)
        assert isinstance(result, list)


# ===========================================================================
# 13. INCORRECT LINEAGE DEPTH
# ===========================================================================


class TestIncorrectLineageDepth:
    def test_depth_inconsistency_detected(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input", lineage_depth=0),
            "SIM-OUT-001": _mk(
                "SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=99
            ),  # Wrong!
        }
        gaps = detect_lineage_gaps(reg)
        assert "SIM-OUT-001" in gaps["depth_inconsistencies"]

    def test_correct_depth_not_in_inconsistencies(self):
        reg = _full_chain_registry()
        gaps = detect_lineage_gaps(reg)
        assert gaps["depth_inconsistencies"] == {}

    def test_depth_computed_from_max_parent(self):
        reg = {
            "P1": _mk("P1", "simulation_input", lineage_depth=0),
            "P2": _mk("P2", "simulation_output", ["P1"], lineage_depth=5),
        }
        depth = compute_lineage_depth("C", ["P1", "P2"], reg)
        assert depth == 6


# ===========================================================================
# 14. INCONSISTENT ROOT ARTIFACT IDS
# ===========================================================================


class TestInconsistentRootArtifactIds:
    def test_root_ids_computed_correctly(self):
        reg = {
            "SIM-IN-001": _mk("SIM-IN-001", "simulation_input"),
            "SIM-OUT-001": _mk("SIM-OUT-001", "simulation_output", ["SIM-IN-001"], lineage_depth=1),
        }
        roots = compute_root_artifacts("EV-001", ["SIM-OUT-001"], reg)
        assert roots == ["SIM-IN-001"]

    def test_two_root_paths_returns_both(self):
        reg = {
            "ROOT-A": _mk("ROOT-A", "simulation_input"),
            "ROOT-B": _mk("ROOT-B", "simulation_input"),
        }
        roots = compute_root_artifacts("MID", ["ROOT-A", "ROOT-B"], reg)
        assert sorted(roots) == ["ROOT-A", "ROOT-B"]

    def test_deep_chain_root_ids_stable(self):
        reg = _full_chain_registry()
        for aid in ["SIM-OUT-001", "EV-001", "RT-001", "ADV-001", "SYN-001", "DEC-001", "SLO-001"]:
            assert reg[aid]["root_artifact_ids"] == ["SIM-IN-001"]


# ===========================================================================
# 15. SLO INTEGRATION CORRECTNESS
# ===========================================================================


class TestSloIntegration:
    def test_slo_must_link_decision_and_synthesis(self):
        assert "decision" in _REQUIRED_PARENT_TYPES["slo_evaluation"]
        assert "synthesis" in _REQUIRED_PARENT_TYPES["slo_evaluation"]

    def test_decision_must_link_synthesis(self):
        assert "synthesis" in _REQUIRED_PARENT_TYPES["decision"]

    def test_slo_lineage_chain_valid_with_correct_parents(self):
        reg = _full_chain_registry()
        valid, errors = validate_lineage_chain(
            "SLO-001", "slo_evaluation", ["DEC-001", "SYN-001"],
            {k: v for k, v in reg.items() if k != "SLO-001"},
        )
        assert valid, errors

    def test_slo_traceable_to_simulation_input(self):
        reg = _full_chain_registry()
        path = trace_to_root("SLO-001", reg)
        assert "SIM-IN-001" in path

    def test_slo_artifact_schema_valid(self):
        artifact = _mk(
            "SLO-001", "slo_evaluation",
            ["DEC-001", "SYN-001"],
            lineage_depth=7,
            root_artifact_ids=["SIM-IN-001"],
        )
        valid, errors = validate_against_schema(artifact)
        assert valid, errors

    def test_full_registry_slo_valid(self):
        reg = _full_chain_registry()
        result = validate_full_registry(reg)
        slo_result = result["artifact_results"]["SLO-001"]
        assert slo_result["valid"], slo_result["errors"]


# ===========================================================================
# 16. TRACE TO ROOT / LEAVES
# ===========================================================================


class TestTracing:
    def test_trace_to_root_returns_path(self):
        reg = _full_chain_registry()
        path = trace_to_root("DEC-001", reg)
        assert "DEC-001" in path
        assert "SIM-IN-001" in path

    def test_trace_to_root_unknown_returns_empty(self):
        reg = _full_chain_registry()
        path = trace_to_root("NONEXISTENT", reg)
        assert path == []

    def test_trace_to_leaves_includes_all_downstream(self):
        reg = _full_chain_registry()
        leaves = trace_to_leaves("SIM-IN-001", reg)
        for aid in ["SIM-OUT-001", "EV-001", "RT-001", "ADV-001", "SYN-001", "DEC-001", "SLO-001"]:
            assert aid in leaves

    def test_trace_to_leaves_leaf_returns_empty(self):
        reg = _full_chain_registry()
        leaves = trace_to_leaves("SLO-001", reg)
        assert leaves == []

    def test_trace_to_leaves_unknown_returns_empty(self):
        reg = _full_chain_registry()
        leaves = trace_to_leaves("GHOST", reg)
        assert leaves == []


# ===========================================================================
# 17. VALIDATE FULL REGISTRY
# ===========================================================================


class TestValidateFullRegistry:
    def test_valid_registry_returns_valid_true(self):
        reg = _full_chain_registry()
        result = validate_full_registry(reg)
        assert result["valid"]

    def test_invalid_artifact_in_registry_fails(self):
        reg = _full_chain_registry()
        # Add an orphan non-root artifact
        reg["ORPHAN"] = _mk("ORPHAN", "decision")  # No parents
        result = validate_full_registry(reg)
        assert not result["valid"]

    def test_result_has_artifact_results_key(self):
        reg = _full_chain_registry()
        result = validate_full_registry(reg)
        assert "artifact_results" in result

    def test_result_has_gap_report_key(self):
        reg = _full_chain_registry()
        result = validate_full_registry(reg)
        assert "gap_report" in result

    def test_empty_registry_is_valid(self):
        result = validate_full_registry({})
        assert result["valid"]
        assert result["total_errors"] == 0


# ===========================================================================
# 18. CLI EXIT CODES
# ===========================================================================


class TestCLIExitCodes:
    def _write_artifacts(self, tmp_dir: Path, artifacts: list) -> None:
        for a in artifacts:
            (tmp_dir / f"{a['artifact_id']}.json").write_text(
                json.dumps(a), encoding="utf-8"
            )

    def test_exit_code_0_all_valid(self):
        from scripts.run_lineage_validation import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            reg = _full_chain_registry()
            self._write_artifacts(tmp_dir, list(reg.values()))
            out = tmp_dir / "report.json"
            code = main(["--dir", str(tmp_dir), "--output", str(out)])
            assert code == 0

    def test_exit_code_1_lineage_errors(self):
        from scripts.run_lineage_validation import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # Orphan artifact
            orphan = _mk("SIM-OUT-ORPHAN", "simulation_output")
            self._write_artifacts(tmp_dir, [orphan])
            out = tmp_dir / "report.json"
            code = main(["--dir", str(tmp_dir), "--output", str(out)])
            assert code == 1

    def test_exit_code_2_schema_errors(self):
        from scripts.run_lineage_validation import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            # Invalid artifact (unknown type)
            bad = _mk("BAD-001", "simulation_input")
            bad["artifact_type"] = "invalid_type"
            self._write_artifacts(tmp_dir, [bad])
            out = tmp_dir / "report.json"
            code = main(["--dir", str(tmp_dir), "--output", str(out)])
            assert code == 2

    def test_cli_writes_output_file(self):
        from scripts.run_lineage_validation import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            reg = _full_chain_registry()
            self._write_artifacts(tmp_dir, list(reg.values()))
            out = tmp_dir / "out" / "report.json"
            main(["--dir", str(tmp_dir), "--output", str(out)])
            assert out.exists()
            data = json.loads(out.read_text())
            assert "summary" in data

    def test_cli_missing_dir_exits_2(self):
        from scripts.run_lineage_validation import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--dir", "/nonexistent/path/xyz", "--output", "/tmp/out.json"])
        assert exc_info.value.code == 2

    def test_cli_output_contains_lineage_graph(self):
        from scripts.run_lineage_validation import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            reg = _full_chain_registry()
            self._write_artifacts(tmp_dir, list(reg.values()))
            out = tmp_dir / "report.json"
            main(["--dir", str(tmp_dir), "--output", str(out)])
            data = json.loads(out.read_text())
            assert "lineage_graph" in data
