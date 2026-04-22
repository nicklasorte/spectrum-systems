"""Phase 4.2: Root Cause Analyzer

Automatically determine failure root cause within 5 minutes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

# Canonical cause codes
INPUT_CORRUPTION = "INPUT_CORRUPTION"
CODE_BUG = "CODE_BUG"
RESOURCE_LIMIT = "RESOURCE_LIMIT"
EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"


class RootCauseAnalyzer:
    """Analyze failure root cause from artifact + timeline + system state."""

    def analyze_failure(
        self,
        failure_artifact: Dict[str, Any],
        execution_timeline: List[Dict[str, Any]],
        system_state: Dict[str, Any],
    ) -> Tuple[str, Dict[str, Any]]:
        """Determine root cause. Returns (cause_code, detail_dict)."""
        reason_code = failure_artifact.get("reason_code", "")
        stack_trace = failure_artifact.get("stack_trace", "")
        failure_id = failure_artifact.get("failure_id", "")

        # Input corruption
        if reason_code == "VALIDATION_ERROR":
            return INPUT_CORRUPTION, {
                "cause": "Input validation failed",
                "suggestion": "Validate input schema before submission",
                "failure_id": failure_id,
            }

        # Resource limit
        if reason_code in ("TIMEOUT", "OOM"):
            return RESOURCE_LIMIT, {
                "cause": "Execution exceeded resource limit",
                "suggestion": "Increase timeout or optimize execution path",
                "available_memory_mb": system_state.get("available_memory"),
                "failure_id": failure_id,
            }

        # Code bug — identified via stack trace keywords
        bug_markers = ("AssertionError", "RuntimeError", "TypeError", "ValueError")
        if any(marker in stack_trace for marker in bug_markers):
            return CODE_BUG, {
                "cause": "Code assertion or runtime error",
                "suggestion": "Review code logic at failing callsite",
                "stack_trace": stack_trace[:300],
                "failure_id": failure_id,
            }

        # External dependency failure
        return EXTERNAL_DEPENDENCY, {
            "cause": "Unknown or external failure",
            "suggestion": "Check external dependencies and network connectivity",
            "failure_id": failure_id,
        }
