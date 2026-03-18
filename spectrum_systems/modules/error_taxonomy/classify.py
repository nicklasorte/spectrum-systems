"""
Classification Pipeline — spectrum_systems/modules/error_taxonomy/classify.py

Orchestrates normalization of source system signals into governed
ErrorClassificationRecord artifacts, storing them for downstream analysis.

Design principles
-----------------
- Every classification record preserves both raw signal and normalized codes.
- Classification records are schema-validated before persistence.
- Storage is flat JSON under ``data/error_classifications/{classification_id}.json``.
- Taxonomy version is always recorded.

Public API
----------
ErrorClassificationRecord
    In-memory, validated classification record.

ErrorClassifier
    Orchestrates classification from all source systems.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

from spectrum_systems.modules.error_taxonomy.catalog import ErrorTaxonomyCatalog
from spectrum_systems.modules.error_taxonomy.normalize import (
    ClassificationResult,
    normalize_eval_error,
    normalize_feedback_error,
    normalize_observability_error,
    normalize_regression_error,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "error_classification_record.schema.json"
)

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "error_classifications"
)


# ---------------------------------------------------------------------------
# ErrorClassificationRecord
# ---------------------------------------------------------------------------

class ErrorClassificationRecord:
    """In-memory, validated representation of a single classification record.

    Parameters
    ----------
    classification_id:
        Unique identifier.
    timestamp:
        ISO-8601 timestamp.
    context:
        Context dict (source_system is required).
    classifications:
        List of classification entry dicts.
    raw_inputs:
        Original source signal dict.
    taxonomy_version:
        Version string of the taxonomy catalog used.
    """

    def __init__(
        self,
        *,
        classification_id: str,
        timestamp: str,
        context: Dict[str, Any],
        classifications: List[Dict[str, Any]],
        raw_inputs: Dict[str, Any],
        taxonomy_version: str,
    ) -> None:
        self.classification_id = classification_id
        self.timestamp = timestamp
        self.context = context
        self.classifications = classifications
        self.raw_inputs = raw_inputs
        self.taxonomy_version = taxonomy_version

    # --- Serialisation ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification_id": self.classification_id,
            "timestamp": self.timestamp,
            "context": self.context,
            "classifications": self.classifications,
            "raw_inputs": self.raw_inputs,
            "taxonomy_version": self.taxonomy_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorClassificationRecord":
        return cls(
            classification_id=data["classification_id"],
            timestamp=data["timestamp"],
            context=data["context"],
            classifications=data["classifications"],
            raw_inputs=data["raw_inputs"],
            taxonomy_version=data["taxonomy_version"],
        )

    # --- Schema validation ------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this record against the JSON Schema.

        Returns a list of error messages.  Empty list means valid.
        """
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(self.to_dict()):
            errors.append(err.message)
        return errors

    # --- Persistence ------------------------------------------------------

    def save(self, store_dir: Optional[Path] = None) -> Path:
        """Persist this record to ``{store_dir}/{classification_id}.json``.

        Parameters
        ----------
        store_dir:
            Directory to save to.  Defaults to
            ``data/error_classifications/``.

        Returns
        -------
        Path
            Path to the saved file.

        Raises
        ------
        FileExistsError
            If a record with this ID already exists.
        """
        target_dir = store_dir or _DEFAULT_STORE_DIR
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        path = target_dir / f"{self.classification_id}.json"
        if path.exists():
            raise FileExistsError(
                f"Classification record '{self.classification_id}' already exists at {path}"
            )
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)
        return path

    @classmethod
    def load(cls, classification_id: str, store_dir: Optional[Path] = None) -> "ErrorClassificationRecord":
        """Load a classification record by ID.

        Raises
        ------
        FileNotFoundError
            If the record does not exist.
        """
        target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        path = target_dir / f"{classification_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Classification record '{classification_id}' not found at {path}")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)

    @classmethod
    def list_all(cls, store_dir: Optional[Path] = None) -> List["ErrorClassificationRecord"]:
        """Load all classification records from the store directory."""
        target_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        if not target_dir.exists():
            return []
        records = []
        for p in sorted(target_dir.glob("*.json")):
            with open(p, encoding="utf-8") as fh:
                records.append(cls.from_dict(json.load(fh)))
        return records


# ---------------------------------------------------------------------------
# ErrorClassifier
# ---------------------------------------------------------------------------

class ErrorClassifier:
    """Orchestrates classification from all source systems.

    Parameters
    ----------
    catalog:
        Loaded ``ErrorTaxonomyCatalog``.  If not provided, the default
        catalog is loaded.
    store_dir:
        Directory to persist classification records.
    """

    def __init__(
        self,
        catalog: Optional[ErrorTaxonomyCatalog] = None,
        store_dir: Optional[Path] = None,
    ) -> None:
        if catalog is None:
            catalog = ErrorTaxonomyCatalog.load_catalog()
        self._catalog = catalog
        self._store_dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR

    def _make_record(
        self,
        source_system: str,
        classifications: List[ClassificationResult],
        raw_inputs: Dict[str, Any],
        *,
        artifact_id: Optional[str] = None,
        artifact_type: Optional[str] = None,
        case_id: Optional[str] = None,
        pass_id: Optional[str] = None,
        pass_type: Optional[str] = None,
    ) -> ErrorClassificationRecord:
        """Build an ``ErrorClassificationRecord`` from normalized results."""
        context: Dict[str, Any] = {"source_system": source_system}
        if artifact_id is not None:
            context["artifact_id"] = artifact_id
        if artifact_type is not None:
            context["artifact_type"] = artifact_type
        if case_id is not None:
            context["case_id"] = case_id
        if pass_id is not None:
            context["pass_id"] = pass_id
        if pass_type is not None:
            context["pass_type"] = pass_type

        return ErrorClassificationRecord(
            classification_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context,
            classifications=[r.to_dict() for r in classifications],
            raw_inputs=raw_inputs,
            taxonomy_version=self._catalog.version,
        )

    def classify_eval_result(
        self,
        eval_result: Dict[str, Any],
        *,
        artifact_id: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> ErrorClassificationRecord:
        """Classify an evaluation result dict.

        Parameters
        ----------
        eval_result:
            ``EvalResult.to_dict()`` or raw failure info dict.
        """
        # Support both EvalResult dicts and raw failure_info dicts
        failure_info = eval_result.get("failure_info") or eval_result
        pass_id = eval_result.get("pass_id") or failure_info.get("pass_id")
        pass_type = eval_result.get("pass_type") or failure_info.get("pass_type", "")

        classifications = normalize_eval_error(failure_info)
        return self._make_record(
            "evaluation",
            classifications,
            eval_result,
            artifact_id=artifact_id,
            case_id=case_id,
            pass_id=pass_id,
            pass_type=pass_type,
        )

    def classify_feedback_record(
        self,
        feedback_record: Dict[str, Any],
    ) -> ErrorClassificationRecord:
        """Classify a human feedback record dict."""
        artifact_id = feedback_record.get("artifact_id")
        artifact_type = feedback_record.get("artifact_type")

        classifications = normalize_feedback_error(feedback_record)
        return self._make_record(
            "feedback",
            classifications,
            feedback_record,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
        )

    def classify_observability_record(
        self,
        obs_record: Dict[str, Any],
    ) -> ErrorClassificationRecord:
        """Classify an observability record dict."""
        artifact_id = obs_record.get("artifact_id")
        artifact_type = obs_record.get("artifact_type")
        pass_id = obs_record.get("pass_id")
        pass_type = obs_record.get("pass_type")

        # Flatten nested observability structure if needed
        flat: Dict[str, Any] = {}
        # Scores
        scores_raw = obs_record.get("scores", {})
        if isinstance(scores_raw, dict):
            flat["scores"] = scores_raw
        else:
            flat["scores"] = {}
        # Flags
        flags_raw = obs_record.get("flags", {})
        if isinstance(flags_raw, dict):
            flat["flags"] = flags_raw
        else:
            flat["flags"] = {}
        # Error types
        error_summary = obs_record.get("error_summary", {})
        flat["error_types"] = error_summary.get("error_types", []) if isinstance(error_summary, dict) else obs_record.get("error_types", [])
        flat["pass_type"] = pass_type or ""
        flat["failure_count"] = error_summary.get("failure_count", 0) if isinstance(error_summary, dict) else obs_record.get("failure_count", 0)

        classifications = normalize_observability_error(flat)
        return self._make_record(
            "observability",
            classifications,
            obs_record,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            pass_id=pass_id,
            pass_type=pass_type,
        )

    def classify_regression_report(
        self,
        report: Dict[str, Any],
    ) -> List[ErrorClassificationRecord]:
        """Classify a regression report dict.

        Returns one ``ErrorClassificationRecord`` per worst_regression entry.

        Parameters
        ----------
        report:
            ``RegressionReport`` dict containing ``worst_regressions`` array.
        """
        records: List[ErrorClassificationRecord] = []
        worst = report.get("worst_regressions", [])

        if not worst:
            # Classify at the report level if no worst_regressions
            summary = report.get("summary", {})
            if not summary.get("overall_pass", True):
                fake_entry = {
                    "dimension": "structural_score",
                    "delta": -0.1,
                    "severity": "hard_fail",
                    "explanation": "Overall regression failure with no dimension details.",
                }
                classifications = normalize_regression_error(fake_entry)
                records.append(self._make_record(
                    "regression",
                    classifications,
                    report,
                ))
            return records

        for entry in worst:
            classifications = normalize_regression_error(entry)
            pass_id = entry.get("pass_id")
            records.append(self._make_record(
                "regression",
                classifications,
                {"report_entry": entry, "report_id": report.get("report_id", "")},
                pass_id=pass_id,
            ))

        return records

    def classify_many(
        self,
        items: List[Dict[str, Any]],
        source_system: str,
    ) -> List[ErrorClassificationRecord]:
        """Classify a list of records from a given source system.

        Parameters
        ----------
        items:
            List of source record dicts.
        source_system:
            One of ``"evaluation"``, ``"feedback"``, ``"observability"``,
            ``"regression"``.

        Returns
        -------
        List[ErrorClassificationRecord]
        """
        _dispatch = {
            "evaluation": self.classify_eval_result,
            "feedback": self.classify_feedback_record,
            "observability": self.classify_observability_record,
        }
        if source_system == "regression":
            results = []
            for item in items:
                results.extend(self.classify_regression_report(item))
            return results

        fn = _dispatch.get(source_system)
        if fn is None:
            raise ValueError(f"Unknown source_system: '{source_system}'")
        return [fn(item) for item in items]
