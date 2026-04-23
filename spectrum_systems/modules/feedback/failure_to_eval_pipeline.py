"""FailureToEvalPipeline: Wire classified failures into the eval candidate lifecycle.

Closes the learning loop:
  failure → classified → eval_candidate → governance_decision → eval_suite
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType


@dataclass
class FailureToEvalPipeline:
    """Route classified failures into eval candidate creation and governed adoption."""

    artifact_store: Any
    governance_system: Any
    eval_registry: Any

    def route_classified_error(
        self,
        classified_error_artifact: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Take a classified error artifact and create an eval_candidate for it.

        Returns eval_adoption_decision if governance approves, else the governance result.
        Missing error_type emits a finding artifact instead of proceeding.
        """
        error_type = classified_error_artifact.get("error_type")
        if not error_type:
            return self._emit_finding("MISSING_ERROR_TYPE", trace_id)

        eval_candidate = self._build_eval_candidate(
            classified_error_artifact=classified_error_artifact,
            trace_id=trace_id,
        )

        governance_result = self.governance_system.request_eval_adoption(
            eval_candidate=eval_candidate,
            trace_id=trace_id,
        )

        if governance_result.get("approved"):
            self.eval_registry.add_candidate(eval_candidate)
            return {
                "artifact_type": "eval_adoption_record",
                "adoption_status": "approved",
                "eval_candidate_id": eval_candidate.get("eval_candidate_id"),
                "trace_id": trace_id,
            }

        return governance_result

    def _build_eval_candidate(
        self,
        classified_error_artifact: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Build an eval_candidate from a classified error artifact."""
        error_type = classified_error_artifact.get("error_type")
        source_artifact = classified_error_artifact.get("source_artifact", {})

        candidate = {
            "artifact_type": "eval_candidate",
            "eval_candidate_id": f"EVC-{uuid.uuid4().hex[:12].upper()}",
            "source_error_type": error_type,
            "source_artifact_type": source_artifact.get("artifact_type"),
            "source_artifact_id": source_artifact.get("artifact_id"),
            "reproduction_fixture": self._build_fixture(classified_error_artifact),
            "expected_output": self._infer_expected_behavior(classified_error_artifact),
            "acceptance_criteria": self._build_criteria(error_type),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "trace_id": trace_id,
            "status": "candidate",
        }

        self.artifact_store.put(candidate, namespace="governance/eval_candidates")
        return candidate

    def _infer_expected_behavior(self, classified_error: Dict[str, Any]) -> Dict[str, Any]:
        """Reverse-engineer what should have happened given the error type."""
        error_type = classified_error.get("error_type")

        inference_rules = {
            ErrorType.extraction_error: "All required fields should be populated",
            ErrorType.reasoning_error: "Decision should be logically sound and well-justified",
            ErrorType.grounding_failure: "All claims should reference source material with citations",
            ErrorType.hallucination: "No factual claims beyond documented evidence",
            ErrorType.schema_violation: "Output should conform to declared schema",
        }

        return {
            "description": inference_rules.get(error_type, "Correct output"),
            "criteria": ["passes_schema", "passes_correctness_check"],
        }

    def _build_fixture(self, classified_error: Dict[str, Any]) -> Dict[str, Any]:
        """Build a reusable reproduction fixture from the error."""
        source = classified_error.get("source_artifact", {})
        return {
            "input": source,
            "expected_pass": False,
            "description": f"Reproduction case for {classified_error.get('error_type')}",
        }

    def _build_criteria(self, error_type: str) -> List[str]:
        """Build acceptance criteria for this error type."""
        return [
            "fixture_reproduces_error",
            "fix_passes_fixture",
            "no_regressions_on_baseline",
        ]

    def _emit_finding(self, category: str, trace_id: str) -> Dict[str, Any]:
        """Emit a finding artifact and halt instead of proceeding with missing data."""
        finding = {
            "artifact_type": "finding_artifact",
            "category": category,
            "trace_id": trace_id,
            "message": f"Cannot route error to eval: {category}",
        }
        self.artifact_store.put(finding, namespace="governance/findings")
        return finding
