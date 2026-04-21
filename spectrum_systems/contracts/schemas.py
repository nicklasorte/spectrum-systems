"""
Schema definitions for Phases 27-28: Judge Calibration + Trace & Provenance Hardening.

All schemas are immutable contracts defining artifact structure.
Validation required on all artifact creation (fail-closed).
"""

# Phase 27: Judge Calibration Record
JUDGE_CALIBRATION_RECORD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-2020-12/schema",
    "title": "JudgeCalibrationRecord",
    "description": "Longitudinal calibration tracking: judge confidence vs actual correctness",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "calibration_id",
        "judge_id",
        "confidence_bucket",
        "total_decisions",
        "correct_decisions",
        "actual_accuracy",
        "expected_accuracy",
        "calibration_error",
        "is_miscalibrated",
        "measurement_period",
        "timestamp",
        "source_code_version"
    ],
    "properties": {
        "calibration_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "Unique immutable ID"
        },
        "judge_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "Which judge (policy, model, human)"
        },
        "confidence_bucket": {
            "type": "string",
            "enum": ["0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-0.95", "0.95-1.0"],
            "description": "Confidence range (e.g., '0.9-0.95' = decisions with 90-95% confidence)"
        },
        "total_decisions": {
            "type": "integer",
            "minimum": 1,
            "description": "How many decisions in this bucket"
        },
        "correct_decisions": {
            "type": "integer",
            "minimum": 0,
            "description": "How many were actually correct"
        },
        "actual_accuracy": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Observed accuracy: correct / total"
        },
        "expected_accuracy": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Judge's stated confidence (midpoint of bucket)"
        },
        "calibration_error": {
            "type": "number",
            "minimum": -1,
            "maximum": 1,
            "description": "expected - actual (positive = overconfident, negative = underconfident)"
        },
        "is_miscalibrated": {
            "type": "boolean",
            "description": "Flag if |calibration_error| > threshold (e.g., 0.05)"
        },
        "measurement_period": {
            "type": "string",
            "enum": ["daily", "weekly", "monthly"],
            "description": "How often calibration measured"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "When this record was created"
        },
        "source_code_version": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        }
    }
}

# Phase 27: Judge Disagreement Report
JUDGE_DISAGREEMENT_REPORT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-2020-12/schema",
    "title": "JudgeDisagreementReport",
    "description": "Judge disagreement with ground truth, trend, and severity breakdown",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "report_id",
        "judge_id",
        "period_days",
        "total_decisions",
        "disagreement_count",
        "disagreement_rate",
        "trend",
        "severity_breakdown",
        "timestamp",
        "recommendation"
    ],
    "properties": {
        "report_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "judge_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "period_days": {
            "type": "integer",
            "minimum": 1
        },
        "total_decisions": {
            "type": "integer",
            "minimum": 0
        },
        "disagreement_count": {
            "type": "integer",
            "minimum": 0
        },
        "disagreement_rate": {
            "type": "number",
            "minimum": 0,
            "maximum": 1
        },
        "trend": {
            "type": "string",
            "enum": ["rising", "stable", "falling", "unknown"]
        },
        "severity_breakdown": {
            "type": "object",
            "description": "Disagreement breakdown by confidence bucket"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "recommendation": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500
        }
    }
}

# Phase 28: Trace Context Manifest (W3C Trace Context + SLSA)
TRACE_CONTEXT_MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-2020-12/schema",
    "title": "TraceContextManifest",
    "description": "Complete trace context for artifact: W3C Trace Context + parent lineage + rerun metadata",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "artifact_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "parent_artifact_ids",
        "context_source_id",
        "execution_step",
        "created_timestamp",
        "lineage_depth",
        "trace_coverage_complete",
        "rerun_bundle_ref"
    ],
    "properties": {
        "artifact_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "ID of this artifact"
        },
        "trace_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{32}$",
            "description": "W3C Trace Context trace ID (32 hex chars)"
        },
        "span_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{16}$",
            "description": "W3C Trace Context span ID (16 hex chars)"
        },
        "parent_span_id": {
            "type": "string",
            "pattern": "^[0-9a-f]{16}$|^$",
            "description": "Parent span ID (linked causality)"
        },
        "parent_artifact_ids": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 3,
                "maxLength": 200
            },
            "description": "Explicit artifact dependencies"
        },
        "context_source_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "Where context came from (e.g., context_bundle_123)"
        },
        "execution_step": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "Which step created this (e.g., 'policy_evaluation', 'eval_execution')"
        },
        "created_timestamp": {
            "type": "string",
            "format": "date-time"
        },
        "lineage_depth": {
            "type": "integer",
            "minimum": 0,
            "description": "How many hops from root input"
        },
        "trace_coverage_complete": {
            "type": "boolean",
            "description": "Is full trace chain unbroken to root?"
        },
        "rerun_bundle_ref": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200,
            "description": "Reference to rerun_bundle for reproducing this artifact"
        }
    }
}

# Phase 28: Replay Fidelity Report
REPLAY_FIDELITY_REPORT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-2020-12/schema",
    "title": "ReplayFidelityReport",
    "description": "Validation that rerun bundles produce equivalent outputs",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "report_id",
        "original_artifact_id",
        "rerun_bundle_id",
        "fidelity_score",
        "structural_match",
        "schema_match",
        "content_similarity",
        "timestamp"
    ],
    "properties": {
        "report_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "original_artifact_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "rerun_bundle_id": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "fidelity_score": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Overall fidelity (0=completely different, 1=identical)"
        },
        "structural_match": {
            "type": "boolean",
            "description": "Does rerun output match schema/structure?"
        },
        "schema_match": {
            "type": "boolean",
            "description": "Does rerun pass same schema validation?"
        },
        "content_similarity": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Semantic similarity (not exact match)"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time"
        }
    }
}
