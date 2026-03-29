"""
Observability Metrics — spectrum_systems/modules/observability/metrics.py

Data model and storage layer for structured observability records.

Every significant AI workflow event (pass execution, evaluation, feedback)
is captured as an ``ObservabilityRecord`` and persisted under
``data/observability/{record_id}.json`` for aggregation and trend analysis.

Design principles
-----------------
- Every record maps to a pass_id and artifact_id.  No orphaned metrics.
- Records are schema-validated before persistence.
- Storage is flat JSON — human-readable and trivially auditable.
- Missing metrics = failure; never silently default critical scores.
- Observability must not mutate system outputs.

Public API
----------
ObservabilityRecord
    In-memory, validated observability record.

MetricsStore
    Persistence and retrieval layer for observability records.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.evaluation.error_taxonomy import ErrorType

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "schemas"
    / "observability_record.schema.json"
)

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "observability"
)

# ---------------------------------------------------------------------------
# Allowed enum values (kept in sync with schema)
# ---------------------------------------------------------------------------

_PIPELINE_STAGES = frozenset({"observe", "interpret", "validate", "learn"})

_VALID_ERROR_TYPES = frozenset(e.value for e in ErrorType)


# ---------------------------------------------------------------------------
# ObservabilityRecord
# ---------------------------------------------------------------------------


class ObservabilityRecord:
    """In-memory, validated representation of a single observability record.

    Parameters
    ----------
    artifact_id:
        ID of the artifact being measured.
    artifact_type:
        Type of artifact (e.g. ``pass_result``, ``evaluation_result``).
    pipeline_stage:
        Pipeline stage where this record was emitted
        (``observe`` | ``interpret`` | ``validate`` | ``learn``).
    pass_id:
        Unique identifier of the pass.
    pass_type:
        Type of the pass (e.g. ``extraction``, ``reasoning``).
    structural_score:
        Structural F1 score (0.0–1.0).
    semantic_score:
        Semantic F1 score (0.0–1.0).
    grounding_score:
        Fraction of grounded claims (0.0–1.0).
    latency_ms:
        Latency in milliseconds.
    schema_valid:
        Whether schema validation passed.
    grounding_passed:
        Whether all claims passed grounding.
    regression_passed:
        Whether no regression was detected.
    human_disagrees:
        Whether a human reviewer disagreed.
    error_types:
        List of ``ErrorType`` values from AU taxonomy.
    failure_count:
        Total number of failures.
    case_id:
        Golden case identifier (optional; set for evaluation records).
    tokens_used:
        Token count (optional).
    record_id:
        Unique identifier.  Auto-generated if not provided.
    timestamp:
        ISO-8601 timestamp.  Defaults to now (UTC).
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        pipeline_stage: str,
        pass_id: str,
        pass_type: str,
        structural_score: float,
        semantic_score: float,
        grounding_score: float,
        latency_ms: int,
        schema_valid: bool,
        grounding_passed: bool,
        regression_passed: bool,
        human_disagrees: bool,
        error_types: Optional[List[str]] = None,
        failure_count: int = 0,
        case_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        run_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        record_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.record_id: str = record_id or str(uuid.uuid4())
        self.timestamp: str = timestamp or datetime.now(timezone.utc).isoformat()
        self.run_id: str = run_id or f"run-{pass_id or self.record_id}"
        self.trace_id: str = trace_id or f"trace-{pass_id or self.record_id}"
        self.artifact_id: str = artifact_id
        self.artifact_type: str = artifact_type
        self.pipeline_stage: str = pipeline_stage
        self.pass_id: str = pass_id
        self.pass_type: str = pass_type
        self.structural_score: float = structural_score
        self.semantic_score: float = semantic_score
        self.grounding_score: float = grounding_score
        self.latency_ms: int = latency_ms
        self.tokens_used: Optional[int] = tokens_used
        self.schema_valid: bool = schema_valid
        self.grounding_passed: bool = grounding_passed
        self.regression_passed: bool = regression_passed
        self.human_disagrees: bool = human_disagrees
        self.error_types: List[str] = list(error_types or [])
        self.failure_count: int = failure_count
        self.case_id: Optional[str] = case_id

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_eval_result(
        cls,
        eval_result: Any,
        *,
        artifact_id: Optional[str] = None,
        artifact_type: str = "evaluation_result",
        pipeline_stage: str = "validate",
        pass_id: Optional[str] = None,
        pass_type: str = "eval_summary",
    ) -> "ObservabilityRecord":
        """Build an ObservabilityRecord from an EvalResult.

        Parameters
        ----------
        eval_result:
            An ``EvalResult`` instance from the evaluation framework.
        artifact_id:
            Override artifact ID.  Defaults to ``eval_result.case_id``.
        artifact_type:
            Artifact type string.
        pipeline_stage:
            Pipeline stage.  Defaults to ``"validate"``.
        pass_id:
            Pass identifier.  Defaults to a generated ID.
        pass_type:
            Pass type label.  Defaults to ``"eval_summary"``.

        Returns
        -------
        ObservabilityRecord
        """
        error_type_values = [e.error_type.value for e in eval_result.error_types]
        grounding_passed = eval_result.grounding_score >= 1.0 and not any(
            e.error_type.value in ("grounding_failure", "hallucination")
            for e in eval_result.error_types
        )
        return cls(
            artifact_id=artifact_id or eval_result.case_id,
            artifact_type=artifact_type,
            pipeline_stage=pipeline_stage,
            pass_id=pass_id or str(uuid.uuid4()),
            pass_type=pass_type,
            structural_score=eval_result.structural_score,
            semantic_score=eval_result.semantic_score,
            grounding_score=eval_result.grounding_score,
            latency_ms=eval_result.latency_summary.total_latency_ms,
            schema_valid=eval_result.schema_valid,
            grounding_passed=grounding_passed,
            regression_passed=not eval_result.regression_detected,
            human_disagrees=bool(eval_result.human_feedback_overrides),
            error_types=error_type_values,
            failure_count=len(eval_result.error_types),
            case_id=eval_result.case_id,
        )

    @classmethod
    def from_feedback(
        cls,
        feedback_record: Any,
        *,
        error_type: Optional[str] = None,
        pipeline_stage: str = "learn",
        pass_id: Optional[str] = None,
        pass_type: str = "human_feedback",
        structural_score: float = 0.0,
        semantic_score: float = 0.0,
        grounding_score: float = 0.0,
        latency_ms: int = 0,
        case_id: Optional[str] = None,
    ) -> "ObservabilityRecord":
        """Build an ObservabilityRecord from a HumanFeedbackRecord.

        This always sets ``human_disagrees=True`` because human feedback
        inherently represents a disagreement with or correction to the
        system output.

        Parameters
        ----------
        feedback_record:
            A ``HumanFeedbackRecord`` instance.
        error_type:
            AU-aligned error type string.  If omitted, derived from
            ``feedback_record.failure_type``.
        pipeline_stage:
            Pipeline stage.  Defaults to ``"learn"``.
        pass_id:
            Pass identifier.  Defaults to a generated UUID.
        pass_type:
            Pass type label.  Defaults to ``"human_feedback"``.
        structural_score:
            Structural score override (default ``0.0``).
        semantic_score:
            Semantic score override (default ``0.0``).
        grounding_score:
            Grounding score override (default ``0.0``).
        latency_ms:
            Latency override (default ``0``).
        case_id:
            Optional golden case identifier.

        Returns
        -------
        ObservabilityRecord
        """
        ft = error_type or feedback_record.failure_type
        # Normalise "unclear" to nearest taxonomy value
        if ft == "unclear":
            ft = "extraction_error"

        return cls(
            artifact_id=feedback_record.artifact_id,
            artifact_type=feedback_record.artifact_type,
            pipeline_stage=pipeline_stage,
            pass_id=pass_id or str(uuid.uuid4()),
            pass_type=pass_type,
            structural_score=structural_score,
            semantic_score=semantic_score,
            grounding_score=grounding_score,
            latency_ms=latency_ms,
            schema_valid=True,
            grounding_passed=(ft not in ("grounding_failure", "hallucination")),
            regression_passed=True,
            human_disagrees=True,
            error_types=[ft] if ft in _VALID_ERROR_TYPES else [],
            failure_count=1,
            case_id=case_id,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this record against the governed schema.

        Returns a list of validation error strings.  An empty list means
        the record is valid.
        """
        errors: List[str] = []

        if not self.record_id:
            errors.append("record_id must be a non-empty string")
        if not self.timestamp:
            errors.append("timestamp must be a non-empty string")
        if not self.artifact_id:
            errors.append("context.artifact_id must be a non-empty string")
        if not self.artifact_type:
            errors.append("context.artifact_type must be a non-empty string")
        if self.pipeline_stage not in _PIPELINE_STAGES:
            errors.append(
                f"context.pipeline_stage '{self.pipeline_stage}' not in "
                f"{sorted(_PIPELINE_STAGES)}"
            )
        if not self.pass_id:
            errors.append("pass_info.pass_id must be a non-empty string")
        if not self.pass_type:
            errors.append("pass_info.pass_type must be a non-empty string")

        # Scores
        for name, value in (
            ("structural_score", self.structural_score),
            ("semantic_score", self.semantic_score),
            ("grounding_score", self.grounding_score),
        ):
            if not isinstance(value, (int, float)):
                errors.append(f"metrics.{name} must be a number")
            elif not (0.0 <= value <= 1.0):
                errors.append(f"metrics.{name} must be between 0.0 and 1.0")

        if not isinstance(self.latency_ms, int) or self.latency_ms < 0:
            errors.append("metrics.latency_ms must be a non-negative integer")
        if self.tokens_used is not None and (
            not isinstance(self.tokens_used, int) or self.tokens_used < 0
        ):
            errors.append("metrics.tokens_used must be a non-negative integer when set")

        # Flags
        for fname in ("schema_valid", "grounding_passed", "regression_passed", "human_disagrees"):
            if not isinstance(getattr(self, fname), bool):
                errors.append(f"flags.{fname} must be a boolean")

        # Error types
        for et in self.error_types:
            if et not in _VALID_ERROR_TYPES:
                errors.append(
                    f"error_summary.error_types contains unknown value '{et}'"
                )
        if not isinstance(self.failure_count, int) or self.failure_count < 0:
            errors.append("error_summary.failure_count must be a non-negative integer")

        return errors

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict matching the schema."""
        context: Dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "pipeline_stage": self.pipeline_stage,
        }
        if self.case_id is not None:
            context["case_id"] = self.case_id

        metrics: Dict[str, Any] = {
            "structural_score": self.structural_score,
            "semantic_score": self.semantic_score,
            "grounding_score": self.grounding_score,
            "latency_ms": self.latency_ms,
        }
        if self.tokens_used is not None:
            metrics["tokens_used"] = self.tokens_used

        return {
            "record_id": self.record_id,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "context": context,
            "pass_info": {
                "pass_id": self.pass_id,
                "pass_type": self.pass_type,
            },
            "metrics": metrics,
            "flags": {
                "schema_valid": self.schema_valid,
                "grounding_passed": self.grounding_passed,
                "regression_passed": self.regression_passed,
                "human_disagrees": self.human_disagrees,
            },
            "error_summary": {
                "error_types": self.error_types,
                "failure_count": self.failure_count,
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservabilityRecord":
        """Deserialise from a JSON-compatible dict.

        Parameters
        ----------
        data:
            Dict conforming to ``observability_record.schema.json``.

        Returns
        -------
        ObservabilityRecord
        """
        ctx = data.get("context", {})
        pi = data.get("pass_info", {})
        metrics = data.get("metrics", {})
        flags = data.get("flags", {})
        es = data.get("error_summary", {})
        return cls(
            record_id=data.get("record_id"),
            timestamp=data.get("timestamp"),
            run_id=data.get("run_id"),
            trace_id=data.get("trace_id"),
            artifact_id=ctx.get("artifact_id", ""),
            artifact_type=ctx.get("artifact_type", ""),
            pipeline_stage=ctx.get("pipeline_stage", "observe"),
            case_id=ctx.get("case_id"),
            pass_id=pi.get("pass_id", ""),
            pass_type=pi.get("pass_type", ""),
            structural_score=metrics.get("structural_score", 0.0),
            semantic_score=metrics.get("semantic_score", 0.0),
            grounding_score=metrics.get("grounding_score", 0.0),
            latency_ms=metrics.get("latency_ms", 0),
            tokens_used=metrics.get("tokens_used"),
            schema_valid=flags.get("schema_valid", True),
            grounding_passed=flags.get("grounding_passed", True),
            regression_passed=flags.get("regression_passed", True),
            human_disagrees=flags.get("human_disagrees", False),
            error_types=es.get("error_types", []),
            failure_count=es.get("failure_count", 0),
        )

    def __repr__(self) -> str:
        return (
            f"ObservabilityRecord(record_id={self.record_id!r}, "
            f"pass_type={self.pass_type!r}, "
            f"artifact_id={self.artifact_id!r})"
        )


# ---------------------------------------------------------------------------
# MetricsStore
# ---------------------------------------------------------------------------


class MetricsStore:
    """Persistence and retrieval layer for observability records.

    Records are stored as individual JSON files under
    ``{store_dir}/{record_id}.json``.

    Parameters
    ----------
    store_dir:
        Root directory for observability storage.  Defaults to
        ``data/observability/``.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir: Path = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, record: ObservabilityRecord) -> Path:
        """Persist a validated observability record.

        Parameters
        ----------
        record:
            ``ObservabilityRecord`` to save.

        Returns
        -------
        Path
            Path to the written JSON file.

        Raises
        ------
        ValueError
            If the record fails schema validation.
        """
        errors = record.validate_against_schema()
        if errors:
            raise ValueError(
                f"ObservabilityRecord failed validation: {'; '.join(errors)}"
            )
        dest = self._store_dir / f"{record.record_id}.json"
        dest.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        return dest

    def load(self, record_id: str) -> ObservabilityRecord:
        """Load an observability record by ID.

        Parameters
        ----------
        record_id:
            Unique record identifier.

        Returns
        -------
        ObservabilityRecord

        Raises
        ------
        FileNotFoundError
            If no record with the given ID exists.
        """
        path = self._store_dir / f"{record_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No observability record found for ID '{record_id}'"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return ObservabilityRecord.from_dict(data)

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[ObservabilityRecord]:
        """List all stored observability records, optionally filtered.

        Parameters
        ----------
        filters:
            Key-value pairs to filter by.  Supported keys:
            ``artifact_id``, ``artifact_type``, ``case_id``,
            ``pipeline_stage``, ``pass_type``, ``pass_id``,
            ``human_disagrees``, ``schema_valid``, ``grounding_passed``,
            ``regression_passed``.

        Returns
        -------
        list[ObservabilityRecord]
            Matching records in chronological order.
        """
        records: List[ObservabilityRecord] = []
        for path in sorted(self._store_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            record = ObservabilityRecord.from_dict(data)
            if filters and not _matches_filters(record, filters):
                continue
            records.append(record)
        return records

    def aggregate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a basic aggregation summary over stored records.

        Parameters
        ----------
        filters:
            Same filter keys as ``list()``.

        Returns
        -------
        dict
            Summary with keys: ``record_count``, ``avg_structural_score``,
            ``avg_semantic_score``, ``avg_grounding_score``,
            ``avg_latency_ms``, ``failure_rate``, ``human_disagreement_rate``.
        """
        records = self.list(filters=filters)
        if not records:
            return {
                "record_count": 0,
                "avg_structural_score": None,
                "avg_semantic_score": None,
                "avg_grounding_score": None,
                "avg_latency_ms": None,
                "failure_rate": None,
                "human_disagreement_rate": None,
            }
        n = len(records)
        return {
            "record_count": n,
            "avg_structural_score": sum(r.structural_score for r in records) / n,
            "avg_semantic_score": sum(r.semantic_score for r in records) / n,
            "avg_grounding_score": sum(r.grounding_score for r in records) / n,
            "avg_latency_ms": sum(r.latency_ms for r in records) / n,
            "failure_rate": sum(1 for r in records if r.failure_count > 0) / n,
            "human_disagreement_rate": sum(1 for r in records if r.human_disagrees) / n,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _matches_filters(record: ObservabilityRecord, filters: Dict[str, Any]) -> bool:
    """Return True if ``record`` matches all supplied filter key-value pairs."""
    mapping: Dict[str, Any] = {
        "artifact_id": record.artifact_id,
        "artifact_type": record.artifact_type,
        "case_id": record.case_id,
        "pipeline_stage": record.pipeline_stage,
        "pass_type": record.pass_type,
        "pass_id": record.pass_id,
        "human_disagrees": record.human_disagrees,
        "schema_valid": record.schema_valid,
        "grounding_passed": record.grounding_passed,
        "regression_passed": record.regression_passed,
    }
    for key, value in filters.items():
        if key in mapping and mapping[key] != value:
            return False
    return True
