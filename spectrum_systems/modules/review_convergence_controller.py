"""ReviewConvergenceController: Run review-fix cycles until convergence or max iterations.

Tightens the loop: execute → review → if not clean, fix → re-review → repeat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from spectrum_systems.modules.review_fix_execution_loop import run_review_fix_execution_cycle


@dataclass
class ReviewConvergenceController:
    """Run review-fix cycles until output is clean or max_iterations is exceeded.

    For production use, supply output_dir, repo_root, and review_docs_dir so they
    are forwarded to run_review_fix_execution_cycle.  In tests those parameters are
    not needed because the underlying function is mocked.
    """

    max_iterations: int = 3
    artifact_store: Optional[Any] = None
    output_dir: Optional[Path] = None
    repo_root: Optional[Path] = None
    review_docs_dir: Optional[Path] = None

    def run_until_clean(
        self,
        request_artifact: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Run review-fix cycles until clean output or max iterations reached.

        Returns final_result_artifact with convergence_status CLEAN or
        BLOCKED_MAX_ITERATIONS.
        """
        current_request = request_artifact

        for iteration in range(1, self.max_iterations + 1):
            result = self._execute_cycle(current_request)

            if self._is_clean(result):
                result["convergence_iterations"] = iteration
                result["convergence_status"] = "CLEAN"
                self._emit_event("convergence_reached", result, trace_id)
                return result

            if iteration < self.max_iterations:
                current_request = self._advance_request(result)
                self._emit_event("fix_incomplete_retrying", result, trace_id)
            else:
                result["convergence_iterations"] = iteration
                result["convergence_status"] = "BLOCKED_MAX_ITERATIONS"
                self._emit_finding("max_iterations_exceeded", result, trace_id)
                return result

        # Unreachable — loop always returns within the for body
        return {"artifact_type": "error_artifact", "error": "unreachable"}

    def _execute_cycle(self, request_artifact: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate one cycle to run_review_fix_execution_cycle."""
        kwargs: Dict[str, Any] = {}
        if self.output_dir is not None:
            kwargs["output_dir"] = self.output_dir
        if self.repo_root is not None:
            kwargs["repo_root"] = self.repo_root
        if self.review_docs_dir is not None:
            kwargs["review_docs_dir"] = self.review_docs_dir
        return run_review_fix_execution_cycle(request_artifact, **kwargs)

    def _is_clean(self, result: Dict[str, Any]) -> bool:
        """Return True if the result has no remaining issues."""
        status = result.get("review_status")
        issues = result.get("remaining_issues", [])
        return (status == "pass") or (len(issues) == 0)

    def _advance_request(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Build the next iteration's request from the fixed artifact."""
        return {
            "artifact_type": "review_fix_execution_request_artifact",
            "input_artifact": result.get("fixed_artifact"),
            "trace_id": result.get("trace_id"),
            "iteration": result.get("iteration", 0) + 1,
        }

    def _emit_event(
        self,
        event_type: str,
        result: Dict[str, Any],
        trace_id: str,
    ) -> None:
        if self.artifact_store:
            self.artifact_store.put(
                {
                    "artifact_type": "convergence_event",
                    "event_type": event_type,
                    "trace_id": trace_id,
                    "result_id": result.get("artifact_id"),
                },
                namespace="observability/convergence",
            )

    def _emit_finding(
        self,
        finding_type: str,
        result: Dict[str, Any],
        trace_id: str,
    ) -> None:
        if self.artifact_store:
            self.artifact_store.put(
                {
                    "artifact_type": "finding_artifact",
                    "finding_type": finding_type,
                    "trace_id": trace_id,
                    "affected_artifact_id": result.get("artifact_id"),
                    "message": f"Review-fix convergence failed: {finding_type}",
                },
                namespace="governance/findings",
            )
