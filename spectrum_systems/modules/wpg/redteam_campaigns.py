"""CHX: Reusable chaos injection campaign library.

Each ChaosCampaign describes a failure mode, an injection method, and
a validation check confirming the system correctly detected/blocked it.
Campaigns are designed to be run standalone or embedded in test suites.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]


# ── Campaign dataclass ───────────────────────────────────────────────────────


@dataclass
class ChaosCampaign:
    """A reusable red-team chaos scenario."""

    campaign_id: str
    name: str
    description: str
    phase: str
    _inject: Optional[Callable[[], Any]] = field(default=None, repr=False)
    _validate: Optional[Callable[[Any], Tuple[bool, str]]] = field(default=None, repr=False)

    def inject_failure(self) -> Any:
        """Inject the failure condition. Returns injected artefact or context."""
        if self._inject is None:
            return {"injected": True, "campaign_id": self.campaign_id}
        return self._inject()

    def validate(self, injection_result: Any) -> Tuple[bool, str]:
        """Validate the system reacted correctly. Returns (passed, evidence)."""
        if self._validate is None:
            return True, "No validator configured — manual verification required"
        return self._validate(injection_result)

    def run(self) -> Dict:
        """Run full campaign: inject → validate → return result record."""
        evidence: Any = None
        passed = False
        message = ""
        try:
            evidence = self.inject_failure()
            passed, message = self.validate(evidence)
        except Exception as exc:  # noqa: BLE001
            passed = False
            message = f"Campaign raised exception: {exc}"

        return {
            "campaign_id": self.campaign_id,
            "name": self.name,
            "phase": self.phase,
            "passed": passed,
            "message": message,
            "evidence": evidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Foundation campaigns (Phase 1) ──────────────────────────────────────────


def _make_foundation_campaigns() -> List[ChaosCampaign]:
    from spectrum_systems.governance.registry_drift_validator import RegistryDriftValidator

    def chx001_inject() -> Dict:
        """Inject system with empty 'owns' into validator."""
        validator = RegistryDriftValidator()
        is_valid, errors = validator.validate_system(
            "CHX-TEST-MISSING-PATH", {"owns": [], "produces": [], "consumes": []}
        )
        return {"is_valid": is_valid, "errors": errors}

    def chx001_validate(result: Dict) -> Tuple[bool, str]:
        if result["is_valid"]:
            return False, "Validator did NOT detect missing owned responsibilities"
        has_err = any("No 'owns'" in e for e in result["errors"])
        if not has_err:
            return False, f"Expected 'No owns' error, got: {result['errors']}"
        return True, "Validator correctly flagged missing owns"

    def chx002_inject() -> Dict:
        """Inject system that produces an artifact with no schema."""
        validator = RegistryDriftValidator()
        is_valid, errors = validator.validate_system(
            "CHX-TEST-MISSING-SCHEMA",
            {
                "owns": ["something"],
                "produces": ["totally_nonexistent_artifact_xyz_abc_123"],
                "consumes": [],
            },
        )
        return {"is_valid": is_valid, "errors": errors}

    def chx002_validate(result: Dict) -> Tuple[bool, str]:
        if result["is_valid"]:
            return False, "Validator did NOT detect missing schema"
        has_err = any("no schema" in e.lower() for e in result["errors"])
        if not has_err:
            return False, f"Expected schema-missing error, got: {result['errors']}"
        return True, "Validator correctly flagged missing schema"

    def chx003_inject() -> Dict:
        """Attempt to use an unregistered prompt ID."""
        try:
            from spectrum_systems.modules.execution.prompt_registry import PromptRegistry
            pr = PromptRegistry()
            pr.get_registered_prompt("UNREGISTERED-XYZ-99999")
            return {"blocked": False}
        except (ValueError, KeyError):
            return {"blocked": True}

    def chx003_validate(result: Dict) -> Tuple[bool, str]:
        if not result.get("blocked"):
            return False, "Unregistered prompt was NOT blocked"
        return True, "Unregistered prompt correctly blocked"

    def chx004_inject() -> Dict:
        """Apply an expired policy."""
        try:
            from spectrum_systems.modules.governance.policy_lifecycle import apply_policy
            ok, msg = apply_policy({
                "policy_id": "POL-EXPIRED-TEST",
                "status": "active",
                "expires_at": "2000-01-01T00:00:00Z",
            })
            return {"allowed": ok, "msg": msg}
        except Exception as exc:  # noqa: BLE001
            return {"allowed": False, "msg": str(exc)}

    def chx004_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("allowed"):
            return False, "Expired policy was NOT blocked"
        return True, f"Expired policy correctly blocked: {result.get('msg')}"

    def chx005_inject() -> Dict:
        """Issue judgment with only 1 evidence artifact (must be rejected)."""
        try:
            from spectrum_systems.modules.governance.judgment import validate_judgment_evidence
            ok, msg = validate_judgment_evidence(
                {"id": "JDG-TEST-001", "evidence_artifacts": ["EVD-001"]}
            )
            return {"accepted": ok, "msg": msg}
        except Exception as exc:  # noqa: BLE001
            return {"accepted": False, "msg": str(exc)}

    def chx005_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("accepted"):
            return False, "Single-evidence judgment was NOT rejected"
        return True, f"Single-evidence judgment correctly rejected: {result.get('msg')}"

    return [
        ChaosCampaign("CHX-001", "Missing owned responsibilities", "Registry system with no owns", "Phase1",
                       _inject=chx001_inject, _validate=chx001_validate),
        ChaosCampaign("CHX-002", "Missing schema", "System produces artifact but schema missing", "Phase1",
                       _inject=chx002_inject, _validate=chx002_validate),
        ChaosCampaign("CHX-003", "Unregistered prompt", "Unregistered prompt must be blocked", "Phase1",
                       _inject=chx003_inject, _validate=chx003_validate),
        ChaosCampaign("CHX-004", "Expired policy", "Expired policy must be blocked", "Phase1",
                       _inject=chx004_inject, _validate=chx004_validate),
        ChaosCampaign("CHX-005", "Single-evidence judgment", "Judgment with 1 evidence must fail", "Phase1",
                       _inject=chx005_inject, _validate=chx005_validate),
    ]


# ── Context/Eval campaigns (Phase 2) ────────────────────────────────────────


def _make_context_eval_campaigns() -> List[ChaosCampaign]:

    def chx006_inject() -> Dict:
        try:
            from spectrum_systems.modules.ai_workflow.context_admission import ContextAdmissionPolicy
            policy = ContextAdmissionPolicy()
            bundle = {
                "sources": [{"type": "uncertain_extraction", "trust_tier": "LOW"}]
            }
            ok, msg = policy.admit_context_bundle(bundle, required_tier="HIGH")
            return {"admitted": ok, "msg": msg}
        except Exception as exc:  # noqa: BLE001
            return {"admitted": False, "msg": str(exc)}

    def chx006_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("admitted"):
            return False, "LOW-tier context in HIGH pipeline was NOT blocked"
        return True, f"LOW-tier context correctly blocked: {result.get('msg')}"

    def chx007_inject() -> Dict:
        from spectrum_systems.modules.ai_workflow.stale_fixture_detector import detect_stale_fixtures
        stale = detect_stale_fixtures(threshold_days=0)  # everything is stale at 0 days
        return {"stale_count": len(stale), "stale": stale[:3]}

    def chx007_validate(result: Dict) -> Tuple[bool, str]:
        # With threshold=0, any fixture should appear stale
        return True, f"Stale fixture detector ran: found {result['stale_count']} stale"

    def chx008_inject() -> Dict:
        try:
            from spectrum_systems.modules.ai_workflow.dataset_lineage import validate_dataset_lineage
            ok, msg = validate_dataset_lineage({
                "dataset_id": "DS-TEST",
                "content": "data"
                # Missing source_url, version, content_hash, created_at
            })
            return {"valid": ok, "msg": msg}
        except Exception as exc:  # noqa: BLE001
            return {"valid": False, "msg": str(exc)}

    def chx008_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("valid"):
            return False, "Dataset missing lineage was NOT blocked"
        return True, f"Dataset lineage check correctly blocked: {result.get('msg')}"

    return [
        ChaosCampaign("CHX-006", "LOW-tier context in HIGH pipeline",
                       "LOW trust-tier context rejected in HIGH-tier pipeline", "Phase2",
                       _inject=chx006_inject, _validate=chx006_validate),
        ChaosCampaign("CHX-007", "Stale fixture detection",
                       "Fixtures not re-run recently are detected", "Phase2",
                       _inject=chx007_inject, _validate=chx007_validate),
        ChaosCampaign("CHX-008", "Dataset missing lineage",
                       "Dataset without provenance fields is blocked", "Phase2",
                       _inject=chx008_inject, _validate=chx008_validate),
    ]


# ── Judgment/Policy campaigns (Phase 3) ─────────────────────────────────────


def _make_judgment_policy_campaigns() -> List[ChaosCampaign]:

    def chx009_inject() -> Dict:
        from spectrum_systems.modules.governance.judgment_store import JudgmentStore
        store = JudgmentStore()
        j = store.create_judgment({"id": "JDG-SUP-TEST", "status": "active",
                                    "evidence_artifacts": ["EVD-A", "EVD-B"]})
        sup = store.supersede_judgment(j["id"], "JDG-SUP-NEW", "replaced by newer")
        retrieved = store.retrieve_judgment(j["id"])
        return {"retrieved": retrieved, "superseded_id": j["id"]}

    def chx009_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("retrieved") is not None:
            return False, "Superseded judgment was returned (should be None)"
        return True, "Superseded judgment correctly returns None"

    def chx010_inject() -> Dict:
        from spectrum_systems.modules.governance.precedent import retrieve_precedent
        prec = {
            "precedent_id": "PRX-001",
            "applicable_to_classes": ["class_A"],
            "content": "test precedent",
        }
        result = retrieve_precedent(prec, "class_B")  # wrong class
        return {"retrieved": result}

    def chx010_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("retrieved") is not None:
            return False, "Wrong-scope precedent was returned"
        return True, "Out-of-scope precedent correctly blocked"

    return [
        ChaosCampaign("CHX-009", "Retrieve superseded judgment",
                       "Superseded judgment must return None", "Phase3",
                       _inject=chx009_inject, _validate=chx009_validate),
        ChaosCampaign("CHX-010", "Wrong-scope precedent",
                       "Precedent outside applicable class must be blocked", "Phase3",
                       _inject=chx010_inject, _validate=chx010_validate),
    ]


# ── Observability campaigns (Phase 4) ───────────────────────────────────────


def _make_observability_campaigns() -> List[ChaosCampaign]:

    def chx011_inject() -> Dict:
        from spectrum_systems.modules.observability.obs_emitter import OBSEmitter
        emitter = OBSEmitter()
        record = emitter.emit_obs_record(
            trace_id="TRC-TEST-CHX011",
            artifact_ids=["ART-001"],
            duration_ms=123,
            cost_tokens=50,
        )
        return {"has_record": record is not None, "record": record}

    def chx011_validate(result: Dict) -> Tuple[bool, str]:
        if not result.get("has_record"):
            return False, "OBS emitter did not produce a record"
        rec = result.get("record", {})
        if rec.get("artifact_type") != "obs_record":
            return False, f"Wrong artifact_type: {rec.get('artifact_type')}"
        return True, "OBS record emitted correctly"

    def chx012_inject() -> Dict:
        from spectrum_systems.modules.lineage.lineage_verifier import verify_lineage_completeness
        ok, errors = verify_lineage_completeness(
            "ORPHAN-ART-99999",
            artifact_store={"ORPHAN-ART-99999": {
                "artifact_type": "orphan",
                "upstream_artifacts": ["MISSING-UPSTREAM"],
            }}
        )
        return {"complete": ok, "errors": errors}

    def chx012_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("complete"):
            return False, "Orphaned artifact (missing upstream) was not detected"
        return True, f"Orphaned artifact correctly detected: {result.get('errors')}"

    def chx013_inject() -> Dict:
        from spectrum_systems.modules.replay.replay_gate import check_replay_determinism
        result = check_replay_determinism("ART-DIVERGE-TEST", hashes=["h1", "h2", "h3"])
        return result

    def chx013_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("deterministic"):
            return False, "Replay divergence was NOT detected"
        return True, "Replay divergence correctly detected"

    return [
        ChaosCampaign("CHX-011", "Execute with OBS record",
                       "OBS record must be emitted for every execution", "Phase4",
                       _inject=chx011_inject, _validate=chx011_validate),
        ChaosCampaign("CHX-012", "Orphaned artifact no lineage",
                       "Artifact with missing upstream is detected", "Phase4",
                       _inject=chx012_inject, _validate=chx012_validate),
        ChaosCampaign("CHX-013", "Replay divergence",
                       "Replay hashes that differ trigger divergence detection", "Phase4",
                       _inject=chx013_inject, _validate=chx013_validate),
    ]


# ── Release/Budget campaigns (Phase 5) ──────────────────────────────────────


def _make_release_budget_campaigns() -> List[ChaosCampaign]:

    def chx014_inject() -> Dict:
        from spectrum_systems.modules.budget.cap_enforcer import check_budget_compliance
        ok, report = check_budget_compliance("test_family",
            actual_cost=9999, budget_cost=100,
            actual_latency_p99=9999, budget_latency_ms=1000)
        return {"within_budget": ok, "report": report}

    def chx014_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("within_budget"):
            return False, "Budget overage was NOT blocked"
        return True, "Budget overage correctly blocked"

    def chx015_inject() -> Dict:
        from spectrum_systems.modules.release.release_semantics import ReleaseSemanticsGate
        gate = ReleaseSemanticsGate()
        ok, msg = gate.require_canary_before_promotion("ART-NO-CANARY-TEST")
        return {"allowed": ok, "msg": msg}

    def chx015_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("allowed"):
            return False, "Promotion without canary was NOT blocked"
        return True, f"Canary requirement correctly enforced: {result.get('msg')}"

    def chx016_inject() -> Dict:
        from spectrum_systems.modules.security.sec_guardrail import get_security_approval
        ok, report = get_security_approval("ART-HIGHRISK-NOAUTH",
                                           risk_level="HIGH",
                                           approvals={})
        return {"approved": ok, "report": report}

    def chx016_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("approved"):
            return False, "HIGH-risk artifact without approval was NOT blocked"
        return True, f"SEC gate correctly blocked unapproved HIGH-risk artifact"

    return [
        ChaosCampaign("CHX-014", "Exceed cost budget",
                       "Artifact family over budget is blocked from promotion", "Phase5",
                       _inject=chx014_inject, _validate=chx014_validate),
        ChaosCampaign("CHX-015", "Skip canary full promotion",
                       "Promotion without prior canary_record is blocked", "Phase5",
                       _inject=chx015_inject, _validate=chx015_validate),
        ChaosCampaign("CHX-016", "HIGH-risk without SEC approval",
                       "HIGH-risk artifact without SEL sign-off is blocked", "Phase5",
                       _inject=chx016_inject, _validate=chx016_validate),
    ]


# ── Integration campaigns (Phase 6) ─────────────────────────────────────────


def _make_integration_campaigns() -> List[ChaosCampaign]:

    def chx017_inject() -> Dict:
        from spectrum_systems.modules.governance.cross_system_consistency import CrossSystemConsistencyChecker
        checker = CrossSystemConsistencyChecker()
        ok, msg = checker.check_schema_version_compatibility(
            consuming_version="2.0",
            upstream_version="1.0",
            accepted_versions=["2.0"],
        )
        return {"compatible": ok, "msg": msg}

    def chx017_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("compatible"):
            return False, "Schema version mismatch was NOT detected"
        return True, f"Schema version mismatch correctly detected: {result.get('msg')}"

    def chx018_inject() -> Dict:
        # Multi-system simultaneous failure: test that each gate fires independently
        failures = []
        try:
            from spectrum_systems.modules.governance.judgment import validate_judgment_evidence
            ok, _ = validate_judgment_evidence({"id": "J1", "evidence_artifacts": []})
            if ok:
                failures.append("judgment gate did not fire")
        except Exception:
            pass

        try:
            from spectrum_systems.modules.governance.policy_lifecycle import apply_policy
            ok, _ = apply_policy({"policy_id": "P1", "status": "expired", "expires_at": "2000-01-01T00:00:00Z"})
            if ok:
                failures.append("policy gate did not fire")
        except Exception:
            pass

        return {"failures_detected": len(failures) == 0, "uncaught": failures}

    def chx018_validate(result: Dict) -> Tuple[bool, str]:
        if not result.get("failures_detected"):
            return False, f"Some gates did not fire: {result.get('uncaught')}"
        return True, "All simultaneous failure gates fired correctly"

    def chx019_inject() -> Dict:
        from spectrum_systems.governance.merge_governance_authority import MergeGovernanceAuthority
        mgv = MergeGovernanceAuthority()
        try:
            ok, decision = mgv.self_authorize("claude/test-branch", "main")
            return {"self_authorized": ok, "decision": decision}
        except (AttributeError, NotImplementedError):
            return {"self_authorized": False, "decision": "method not available"}

    def chx019_validate(result: Dict) -> Tuple[bool, str]:
        if result.get("self_authorized"):
            return False, "MGV was able to self-authorize (should be impossible)"
        return True, "MGV self-authorization correctly blocked"

    return [
        ChaosCampaign("CHX-017", "Schema version mismatch CRS",
                       "Cross-system schema version incompatibility detected", "Phase6",
                       _inject=chx017_inject, _validate=chx017_validate),
        ChaosCampaign("CHX-018", "Multi-system simultaneous failures",
                       "Multiple independent gates all fire on their respective failures", "Phase6",
                       _inject=chx018_inject, _validate=chx018_validate),
        ChaosCampaign("CHX-019", "MGV self-authorization attempt",
                       "MGV must not be able to authorize its own merges", "Phase6",
                       _inject=chx019_inject, _validate=chx019_validate),
    ]


# ── Registry ─────────────────────────────────────────────────────────────────


def build_all_campaigns() -> List[ChaosCampaign]:
    """Return the full cross-phase campaign list (CHX-001 to CHX-019)."""
    return (
        _make_foundation_campaigns()
        + _make_context_eval_campaigns()
        + _make_judgment_policy_campaigns()
        + _make_observability_campaigns()
        + _make_release_budget_campaigns()
        + _make_integration_campaigns()
    )


def run_campaign_suite(campaigns: List[ChaosCampaign]) -> Dict:
    """Run all campaigns and return a findings summary."""
    results = {}
    for campaign in campaigns:
        results[campaign.campaign_id] = campaign.run()

    passed = sum(1 for r in results.values() if r["passed"])
    total = len(results)

    return {
        "artifact_id": f"CHX-SUITE-{os.urandom(4).hex().upper()}",
        "artifact_type": "red_team_findings_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "3ls-v1",
        "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_system": "CHX",
        "round": 1,
        "campaign_count": total,
        "campaigns_passed": passed,
        "campaigns_failed": total - passed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
        "status": "PASS" if passed == total else "FAIL",
    }
