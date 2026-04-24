"""Phase 7 Final Lock & Certification tests: ENT, PRG, gate rerun, CDE envelope, checkpoint.

GATE-7 compliance tests.
"""

import re
from pathlib import Path

import pytest

# ── System Registry Guard constants (mirrored for pre-flight detection) ───────
# These patterns replicate the guard logic from spectrum_systems/modules/governance/
# system_registry_guard.py so tests can catch ownership violations before CI.

_OWNER_CLAIM_PATTERNS_LOCAL = [
    re.compile(r"\bowns\b", re.IGNORECASE),
    re.compile(r"\bowner of\b", re.IGNORECASE),
    re.compile(r"\bcanonical owner\b", re.IGNORECASE),
    re.compile(r"\blifecycle owner\b", re.IGNORECASE),
    re.compile(r"\bresponsible for\b", re.IGNORECASE),
    re.compile(r"\bauthority\b", re.IGNORECASE),
    re.compile(r"\bcontrols\b", re.IGNORECASE),
    re.compile(r"\bgovers?ns\b", re.IGNORECASE),
    re.compile(r"\bemits\b", re.IGNORECASE),
    re.compile(r"\boverride\b", re.IGNORECASE),
]

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Files that touch the enforcement / decision-execution boundary require
# extra scrutiny: they must not claim ownership of protected system acronyms.
_ENFORCEMENT_BOUNDARY_FILES = [
    "spectrum_systems/modules/runtime/enforcement_gate.py",
    "spectrum_systems/modules/runtime/ctrl_loop_gates.py",
    "spectrum_systems/modules/runtime/control_loop.py",
    "spectrum_systems/modules/runtime/cde_decision_flow.py",
    "spectrum_systems/modules/observability/slo_definitions.py",
]


# ── ENT Entropy Detector ──────────────────────────────────────────────────────


class TestEntropyDetector:
    def setup_method(self):
        from spectrum_systems.modules.entropy.ent_detector import detect_repeated_corrections
        self.detect = detect_repeated_corrections

    def test_no_corrections_returns_empty(self):
        result = self.detect([])
        assert result == []

    def test_low_count_issues_not_flagged(self):
        corrections = [{"issue_type": "schema_mismatch"}, {"issue_type": "schema_mismatch"}]
        result = self.detect(corrections)
        assert not result  # 2 corrections, threshold is >2

    def test_high_count_issue_flagged(self):
        corrections = [{"issue_type": "registry_drift"}] * 3
        result = self.detect(corrections)
        assert len(result) == 1
        assert result[0]["issue_type"] == "registry_drift"
        assert result[0]["correction_count"] == 3

    def test_recommendation_present(self):
        corrections = [{"issue_type": "eval_gap"}] * 4
        result = self.detect(corrections)
        assert "recommendation" in result[0]
        assert "policy" in result[0]["recommendation"].lower() or "eval" in result[0]["recommendation"].lower()

    def test_multiple_issue_types_tracked_independently(self):
        corrections = [
            {"issue_type": "type_a"}, {"issue_type": "type_a"}, {"issue_type": "type_a"},
            {"issue_type": "type_b"}, {"issue_type": "type_b"},
        ]
        result = self.detect(corrections)
        types = {r["issue_type"] for r in result}
        assert "type_a" in types
        assert "type_b" not in types  # only 2, below threshold


# ── PRG Roadmap Alignment ────────────────────────────────────────────────────


class TestRoadmapAlignment:
    def test_emits_roadmap_alignment_record(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert record["artifact_type"] == "roadmap_alignment_record"

    def test_record_has_timestamp(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert record.get("timestamp")

    def test_record_has_roadmap_items_list(self):
        from spectrum_systems.governance.roadmap_alignment import emit_roadmap_alignment_record
        record = emit_roadmap_alignment_record()
        assert isinstance(record["roadmap_items"], list)


# ── Gate Rerun ───────────────────────────────────────────────────────────────


class TestGateRerun:
    def test_rerun_all_gates_returns_report(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        assert report["artifact_type"] == "gate_rerun_report"
        assert "gates" in report
        assert "overall_status" in report

    def test_all_phase_gates_present_in_report(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        expected = {"GATE-F", "GATE-C", "GATE-J", "GATE-O", "GATE-R", "GATE-I"}
        assert expected.issubset(set(report["gates"].keys()))

    def test_all_gates_pass(self):
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        failed_gates = [
            gid for gid, info in report["gates"].items()
            if not info["passed"]
        ]
        assert not failed_gates, f"Gates failed: {failed_gates}"
        assert report["overall_status"] == "GREEN"


# ── CDE Trust Envelope ────────────────────────────────────────────────────────


class TestCDETrustEnvelope:
    def setup_method(self):
        from spectrum_systems.governance.cde_trust_envelope import CDETrustEnvelope
        self.cde = CDETrustEnvelope()

    def test_create_produces_envelope_artifact(self):
        env = self.cde.create_trust_envelope()
        assert env["artifact_type"] == "cde_trust_envelope"

    def test_envelope_has_signature(self):
        env = self.cde.create_trust_envelope()
        assert env.get("signature")
        assert len(env["signature"]) > 10

    def test_envelope_has_bundle_hash(self):
        env = self.cde.create_trust_envelope()
        assert env.get("bundle_hash")
        assert len(env["bundle_hash"]) == 64  # SHA-256 hex

    def test_lock_sets_locked_flag(self):
        env = self.cde.lock_envelope()
        assert env["locked"] is True
        assert env.get("locked_at")

    def test_is_locked_returns_true_after_lock(self):
        self.cde.lock_envelope()
        assert self.cde.is_locked()

    def test_verify_promotion_against_locked_envelope(self):
        self.cde.lock_envelope()
        ok, msg = self.cde.verify_promotion_against_envelope({"artifact_type": "pqx_output"})
        assert ok

    def test_verify_promotion_fails_without_lock(self):
        ok, msg = self.cde.verify_promotion_against_envelope({})
        assert not ok


# ── PRG Checkpoint Review ────────────────────────────────────────────────────


class TestCheckpointReview:
    def setup_method(self):
        from spectrum_systems.governance.checkpoint_review import emit_checkpoint_review_artifact
        self.emit = emit_checkpoint_review_artifact

    def test_emits_checkpoint_review_artifact(self):
        rec = self.emit()
        assert rec["artifact_type"] == "checkpoint_review_artifact"

    def test_all_slis_present(self):
        rec = self.emit()
        expected_slis = {"eval_pass_rate", "lineage_completeness", "replay_determinism", "drift_rate_daily"}
        assert expected_slis.issubset(set(rec["slis"].keys()))

    def test_all_green_when_targets_met(self):
        rec = self.emit(
            eval_pass_rate=1.0,
            lineage_completeness_pct=100.0,
            replay_determinism_pct=100.0,
            drift_rate_daily=0.0,
            unregistered_prompt_count=0,
            expired_policy_count=0,
            cde_envelope_locked=True,
        )
        assert rec["summary"]["overall_status"] == "GREEN"

    def test_red_when_sli_breached(self):
        rec = self.emit(eval_pass_rate=0.80)  # below 95% target
        assert rec["slis"]["eval_pass_rate"]["status"] == "RED"
        assert rec["summary"]["overall_status"] == "RED"

    def test_governance_fields_present(self):
        rec = self.emit()
        gov = rec["governance"]
        assert "no_unregistered_prompts" in gov
        assert "no_expired_policies" in gov
        assert "cde_trust_envelope_locked" in gov


# ── RT-FINAL Comprehensive ────────────────────────────────────────────────────


class TestRTFinalComprehensive:
    """RT-FINAL: All bypass categories tested simultaneously."""

    def test_all_19_campaigns_blocked(self):
        """All 19 chaos scenarios must be blocked end-to-end."""
        from spectrum_systems.modules.wpg.redteam_campaigns import (
            build_all_campaigns,
            run_campaign_suite,
        )
        report = run_campaign_suite(build_all_campaigns())
        failed = [
            cid for cid, r in report["results"].items()
            if not r.get("passed")
        ]
        assert not failed, f"RT-FINAL: campaigns not blocked: {failed}"

    def test_cde_envelope_locks_and_validates(self):
        """CDE trust envelope must lock and validate promotions."""
        from spectrum_systems.governance.cde_trust_envelope import CDETrustEnvelope
        cde = CDETrustEnvelope()
        cde.lock_envelope()
        assert cde.is_locked()
        ok, _ = cde.verify_promotion_against_envelope({"artifact_type": "test"})
        assert ok

    def test_gate_rerun_all_green_before_final_lock(self):
        """Full gate rerun must show GREEN before issuing CDE lock."""
        from spectrum_systems.governance.gate_runner import rerun_all_gates
        report = rerun_all_gates()
        assert report["overall_status"] == "GREEN", (
            f"Not all gates green before lock: "
            + str({k: v["passed"] for k, v in report["gates"].items()})
        )

    def test_checkpoint_review_all_green(self):
        """PRG checkpoint review must show all GREEN SLIs."""
        from spectrum_systems.governance.checkpoint_review import emit_checkpoint_review_artifact
        rec = emit_checkpoint_review_artifact(
            eval_pass_rate=1.0,
            lineage_completeness_pct=100.0,
            replay_determinism_pct=100.0,
            drift_rate_daily=0.0,
            cde_envelope_locked=True,
        )
        assert rec["summary"]["overall_status"] == "GREEN"


# ── System Registry Guard Pre-Flight ─────────────────────────────────────────


def _owner_claim_violations(file_path: str) -> list[dict]:
    """Return owner-claim + 3-letter-symbol violations for a single file.

    Mirrors the SRG detection logic so tests catch violations before CI.
    A violation is a line that:
    1. Matches an owner-claim pattern (authority, emits, owns, governs, …), AND
    2. Contains a standalone 3-letter uppercase word (potential system acronym).
    """
    path = _REPO_ROOT / file_path
    if not path.exists():
        return []
    violations = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if any(p.search(line) for p in _OWNER_CLAIM_PATTERNS_LOCAL):
            m = re.search(r"\b([A-Z0-9]{3})\b", line)
            if m:
                violations.append({
                    "file": file_path,
                    "line": idx,
                    "symbol": m.group(1),
                    "text": line.strip()[:120],
                })
    return violations


class TestSystemRegistryGuardCompliance:
    """Pre-flight tests that replicate SRG ownership-claim detection.

    These run in the local test suite so boundary violations are caught before
    CI fires the full system_registry_guard. Adding files to the enforcement
    boundary here ensures any new runtime modules that touch decision or
    enforcement concepts are automatically checked.
    """

    @pytest.mark.parametrize("rel_path", _ENFORCEMENT_BOUNDARY_FILES)
    def test_enforcement_boundary_file_has_no_owner_claim_violations(self, rel_path: str) -> None:
        """No enforcement-boundary file may pair a 3-letter system symbol with owner-claim language."""
        violations = _owner_claim_violations(rel_path)
        assert not violations, (
            f"System registry guard violations in {rel_path}:\n"
            + "\n".join(f"  line {v['line']}: {v['symbol']!r} — {v['text']!r}" for v in violations)
        )

    def test_enforcement_gate_module_clean(self) -> None:
        """enforcement_gate.py must not reference protected system acronyms as owners."""
        violations = _owner_claim_violations("spectrum_systems/modules/runtime/enforcement_gate.py")
        assert violations == [], (
            "enforcement_gate.py has system registry guard violations: "
            + str(violations)
        )

    def test_ctrl_loop_gates_module_clean(self) -> None:
        """ctrl_loop_gates.py must not reference protected system acronyms as owners."""
        violations = _owner_claim_violations("spectrum_systems/modules/runtime/ctrl_loop_gates.py")
        assert violations == [], (
            "ctrl_loop_gates.py has system registry guard violations: "
            + str(violations)
        )

    def test_slo_definitions_module_clean(self) -> None:
        """slo_definitions.py must not reference protected system acronyms as owners."""
        violations = _owner_claim_violations("spectrum_systems/modules/observability/slo_definitions.py")
        assert violations == []

    def test_artifact_packager_module_clean(self) -> None:
        """artifact_packager.py must not reference protected system acronyms as owners."""
        violations = _owner_claim_violations("spectrum_systems/modules/artifact_packager.py")
        assert violations == []

    def test_srg_guard_module_itself_loads(self) -> None:
        """The system registry guard module must be importable (guards the guard)."""
        from spectrum_systems.modules.governance.system_registry_guard import (
            evaluate_system_registry_guard,
            load_guard_policy,
            parse_system_registry,
        )
        assert callable(evaluate_system_registry_guard)
        assert callable(load_guard_policy)
        assert callable(parse_system_registry)

    def test_srg_policy_file_is_valid_json(self) -> None:
        """The SRG policy file must be valid JSON and have protected_authority_seams."""
        import json
        policy_path = _REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
        assert policy_path.exists(), "SRG policy file missing"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        assert "protected_authority_seams" in policy
        assert isinstance(policy["protected_authority_seams"], dict)

    def test_srg_system_registry_is_parseable(self) -> None:
        """The system registry markdown must be parseable by the guard."""
        from spectrum_systems.modules.governance.system_registry_guard import parse_system_registry
        registry = parse_system_registry(_REPO_ROOT / "docs" / "architecture" / "system_registry.md")
        assert registry.systems, "Registry must define at least one system"
        assert registry.active_systems, "Registry must have at least one active system"

    def test_srg_full_run_on_enforcement_boundary_files(self) -> None:
        """Full SRG evaluation on enforcement-boundary files must return status=pass."""
        from spectrum_systems.modules.governance.system_registry_guard import (
            evaluate_system_registry_guard,
            load_guard_policy,
            parse_system_registry,
        )
        policy = load_guard_policy(
            _REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
        )
        registry = parse_system_registry(_REPO_ROOT / "docs" / "architecture" / "system_registry.md")
        result = evaluate_system_registry_guard(
            repo_root=_REPO_ROOT,
            changed_files=_ENFORCEMENT_BOUNDARY_FILES,
            policy=policy,
            registry_model=registry,
        )
        assert result["status"] == "pass", (
            f"SRG violations in enforcement-boundary files:\n"
            + "\n".join(
                f"  [{d['reason_code']}] {d['file']}:{d.get('line', '?')} sym={d.get('symbol')!r}"
                for d in result.get("diagnostics", [])
            )
        )


# ── Authority Leak Guard Pre-Flight ──────────────────────────────────────────


# Files in spectrum_systems/modules/ that are subject to ALG scanning and
# must not introduce forbidden vocabulary or authority-shape artifacts.
_ALG_BOUNDARY_FILES = [
    "spectrum_systems/modules/runtime/enforcement_gate.py",
    "spectrum_systems/modules/runtime/ctrl_loop_gates.py",
    "spectrum_systems/modules/observability/slo_definitions.py",
    "spectrum_systems/modules/artifact_packager.py",
]

_AUTHORITY_REGISTRY_PATH = _REPO_ROOT / "contracts" / "governance" / "authority_registry.json"


class TestAuthorityLeakGuardCompliance:
    """Pre-flight tests replicating ALG forbidden-vocabulary and authority-shape detection.

    These mirror scripts/authority_leak_rules.py and scripts/authority_shape_detector.py
    so that ALG violations are caught in local tests before CI runs the full guard.
    """

    @staticmethod
    def _registry() -> dict:
        from scripts.authority_leak_rules import load_authority_registry
        return load_authority_registry(_AUTHORITY_REGISTRY_PATH)

    def test_authority_registry_loads_with_required_keys(self) -> None:
        """authority_registry.json must be valid JSON with categories and forbidden_contexts."""
        registry = self._registry()
        assert "categories" in registry
        assert "forbidden_contexts" in registry
        assert "vocabulary_overrides" in registry

    def test_enforcement_gate_is_canonical_enforcement_owner(self) -> None:
        """enforcement_gate.py must be registered as a canonical enforcement owner."""
        from scripts.authority_leak_rules import is_owner_path
        registry = self._registry()
        assert is_owner_path(
            "spectrum_systems/modules/runtime/enforcement_gate.py", registry
        ), "enforcement_gate.py must be in authority_registry.json enforcement canonical_owners"

    def test_ctrl_loop_gates_has_vocabulary_overrides_for_control_values(self) -> None:
        """ctrl_loop_gates.py must have vocabulary overrides for 'block' and 'freeze'."""
        from scripts.authority_leak_rules import _get_override_set
        registry = self._registry()
        overrides = _get_override_set(
            registry, "allowed_values",
            "spectrum_systems/modules/runtime/ctrl_loop_gates.py",
        )
        assert "block" in overrides, "authority_registry.json must allow 'block' for ctrl_loop_gates.py"
        assert "freeze" in overrides, "authority_registry.json must allow 'freeze' for ctrl_loop_gates.py"

    @pytest.mark.parametrize("rel_path", _ALG_BOUNDARY_FILES)
    def test_no_forbidden_vocabulary_in_boundary_file(self, rel_path: str) -> None:
        """No ALG boundary file may contain forbidden authority vocabulary outside canonical owners."""
        from scripts.authority_leak_rules import find_forbidden_vocabulary
        path = _REPO_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} not yet created")
        violations = find_forbidden_vocabulary(path, self._registry())
        assert not violations, (
            f"ALG forbidden-vocabulary violations in {rel_path}:\n"
            + "\n".join(
                f"  line {v['line']}: {v['token']!r} — {v['message']}"
                for v in violations
            )
        )

    @pytest.mark.parametrize("rel_path", _ALG_BOUNDARY_FILES)
    def test_no_authority_shapes_in_boundary_file(self, rel_path: str) -> None:
        """No ALG boundary file may define authority-shaped artifact_type outside canonical owners."""
        from scripts.authority_shape_detector import detect_authority_shapes
        path = _REPO_ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} not yet created")
        violations = detect_authority_shapes(path, self._registry())
        assert not violations, (
            f"ALG authority-shape violations in {rel_path}:\n"
            + "\n".join(
                f"  [{v['rule']}] obj#{v.get('object_index', '?')}: {v['message']}"
                for v in violations
            )
        )

    def test_alg_enforcement_gate_vocabulary_clean(self) -> None:
        """enforcement_gate.py must pass full ALG vocabulary scan (canonical owner exemption)."""
        from scripts.authority_leak_rules import find_forbidden_vocabulary
        path = _REPO_ROOT / "spectrum_systems/modules/runtime/enforcement_gate.py"
        violations = find_forbidden_vocabulary(path, self._registry())
        assert violations == [], (
            "enforcement_gate.py has ALG vocabulary violations: " + str(violations)
        )

    def test_alg_enforcement_gate_shape_clean(self) -> None:
        """enforcement_gate.py must pass full ALG authority-shape scan (canonical owner exemption)."""
        from scripts.authority_shape_detector import detect_authority_shapes
        path = _REPO_ROOT / "spectrum_systems/modules/runtime/enforcement_gate.py"
        violations = detect_authority_shapes(path, self._registry())
        assert violations == [], (
            "enforcement_gate.py has ALG authority-shape violations: " + str(violations)
        )
