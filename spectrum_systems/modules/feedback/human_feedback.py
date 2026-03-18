"""
Human Feedback Record — spectrum_systems/modules/feedback/human_feedback.py

Data model and storage layer for governed human feedback artifacts.

Design principles
-----------------
- Feedback is a first-class artifact: schema-validated, uniquely identified,
  and immutably stored alongside the artifact it references.
- No silent overwrites: every save is append-only; existing records raise an
  error.
- Storage is flat JSON files under ``data/human_feedback/{feedback_id}.json``
  so that records are human-readable and trivially auditable.

Public API
----------
HumanFeedbackRecord
    Validated in-memory representation of a single feedback record.

FeedbackStore
    Persistence and retrieval layer for feedback records.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "schemas"
    / "human_feedback_record.schema.json"
)

_DEFAULT_STORE_DIR = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "human_feedback"
)

# ---------------------------------------------------------------------------
# Allowed enum values (kept in sync with schema)
# ---------------------------------------------------------------------------

_ARTIFACT_TYPES = frozenset({
    "meeting_minutes",
    "working_paper",
    "slide_intelligence",
    "pass_result",
    "pass_chain_record",
    "context_bundle",
    "evaluation_result",
})

_TARGET_LEVELS = frozenset({"artifact", "section", "claim"})

_REVIEWER_ROLES = frozenset({"engineer", "policy", "legal", "leadership"})

_ACTIONS = frozenset({
    "accept",
    "minor_edit",
    "major_edit",
    "reject",
    "rewrite",
    "needs_support",
})

_SOURCES_OF_TRUTH = frozenset({
    "transcript",
    "slides",
    "statute",
    "policy",
    "engineering_analysis",
    "external_reference",
})

_FAILURE_TYPES = frozenset({
    "extraction_error",
    "reasoning_error",
    "grounding_failure",
    "hallucination",
    "schema_violation",
    "unclear",
})

_SEVERITIES = frozenset({"low", "medium", "high", "critical"})

_EDIT_ACTIONS = frozenset({"minor_edit", "major_edit", "rewrite"})


# ---------------------------------------------------------------------------
# HumanFeedbackRecord
# ---------------------------------------------------------------------------


class HumanFeedbackRecord:
    """In-memory, validated representation of a single human feedback record.

    Attributes mirror the ``human_feedback_record.schema.json`` contract.

    Parameters
    ----------
    feedback_id:
        Unique identifier.  Auto-generated as a UUID4 if not provided.
    artifact_id:
        ID of the artifact being reviewed.
    artifact_type:
        Type of artifact (see schema enum).
    target_level:
        Granularity: ``artifact``, ``section``, or ``claim``.
    target_id:
        ID of the specific section or claim being reviewed.
    reviewer_id:
        Unique identifier of the reviewer.
    reviewer_role:
        Professional role of the reviewer.
    action:
        Reviewer disposition (see schema enum).
    original_text:
        Original AI-generated text.  Always preserved.
    rationale:
        Reviewer explanation.
    source_of_truth:
        Authoritative source the reviewer relied on.
    failure_type:
        AU-aligned failure classification.
    severity:
        Impact severity.
    golden_dataset:
        Whether this feedback should update the golden dataset.
    prompts:
        Whether this feedback should trigger a prompt update.
    retrieval_memory:
        Whether this feedback should update retrieval memory.
    edited_text:
        Reviewer-corrected text (required for edit/rewrite actions).
    timestamp:
        ISO-8601 creation timestamp.  Defaults to now (UTC).
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        target_level: str,
        target_id: str,
        reviewer_id: str,
        reviewer_role: str,
        action: str,
        original_text: str,
        rationale: str,
        source_of_truth: str,
        failure_type: str,
        severity: str,
        golden_dataset: bool,
        prompts: bool,
        retrieval_memory: bool,
        edited_text: Optional[str] = None,
        feedback_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        self.feedback_id: str = feedback_id or str(uuid.uuid4())
        self.artifact_id: str = artifact_id
        self.artifact_type: str = artifact_type
        self.target_level: str = target_level
        self.target_id: str = target_id
        self.reviewer_id: str = reviewer_id
        self.reviewer_role: str = reviewer_role
        self.action: str = action
        self.original_text: str = original_text
        self.edited_text: Optional[str] = edited_text
        self.rationale: str = rationale
        self.source_of_truth: str = source_of_truth
        self.failure_type: str = failure_type
        self.severity: str = severity
        self.golden_dataset: bool = golden_dataset
        self.prompts: bool = prompts
        self.retrieval_memory: bool = retrieval_memory
        self.timestamp: str = timestamp or datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate this record against the governed schema.

        Returns a list of validation error strings.  An empty list means the
        record is valid.

        The validation is intentionally lightweight (no external jsonschema
        library dependency) and checks all required fields and enum values.
        """
        errors: List[str] = []

        if not self.feedback_id:
            errors.append("feedback_id must be a non-empty string")
        if not self.artifact_id:
            errors.append("artifact_id must be a non-empty string")
        if self.artifact_type not in _ARTIFACT_TYPES:
            errors.append(f"artifact_type '{self.artifact_type}' not in allowed values")
        if self.target_level not in _TARGET_LEVELS:
            errors.append(f"target_level '{self.target_level}' not in allowed values")
        if not self.target_id:
            errors.append("target_id must be a non-empty string")
        if not self.reviewer_id:
            errors.append("reviewer_id must be a non-empty string")
        if self.reviewer_role not in _REVIEWER_ROLES:
            errors.append(f"reviewer_role '{self.reviewer_role}' not in allowed values")
        if self.action not in _ACTIONS:
            errors.append(f"action '{self.action}' not in allowed values")
        if not self.original_text:
            errors.append("original_text must be a non-empty string")
        if self.action in _EDIT_ACTIONS and not self.edited_text:
            errors.append(
                f"edited_text is required when action is '{self.action}'"
            )
        if not self.rationale:
            errors.append("rationale must be a non-empty string")
        if self.source_of_truth not in _SOURCES_OF_TRUTH:
            errors.append(f"source_of_truth '{self.source_of_truth}' not in allowed values")
        if self.failure_type not in _FAILURE_TYPES:
            errors.append(f"failure_type '{self.failure_type}' not in allowed values")
        if self.severity not in _SEVERITIES:
            errors.append(f"severity '{self.severity}' not in allowed values")
        if not isinstance(self.golden_dataset, bool):
            errors.append("should_update.golden_dataset must be a boolean")
        if not isinstance(self.prompts, bool):
            errors.append("should_update.prompts must be a boolean")
        if not isinstance(self.retrieval_memory, bool):
            errors.append("should_update.retrieval_memory must be a boolean")

        return errors

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-compatible dict matching the schema."""
        return {
            "feedback_id": self.feedback_id,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "target_level": self.target_level,
            "target_id": self.target_id,
            "reviewer": {
                "reviewer_id": self.reviewer_id,
                "reviewer_role": self.reviewer_role,
            },
            "action": self.action,
            "original_text": self.original_text,
            "edited_text": self.edited_text,
            "rationale": self.rationale,
            "source_of_truth": self.source_of_truth,
            "failure_type": self.failure_type,
            "severity": self.severity,
            "should_update": {
                "golden_dataset": self.golden_dataset,
                "prompts": self.prompts,
                "retrieval_memory": self.retrieval_memory,
            },
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanFeedbackRecord":
        """Deserialise from a dict (e.g., loaded from JSON).

        Parameters
        ----------
        data:
            Dict conforming to ``human_feedback_record.schema.json``.

        Returns
        -------
        HumanFeedbackRecord
        """
        reviewer = data.get("reviewer", {})
        should_update = data.get("should_update", {})
        return cls(
            feedback_id=data.get("feedback_id"),
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            target_level=data["target_level"],
            target_id=data["target_id"],
            reviewer_id=reviewer.get("reviewer_id", ""),
            reviewer_role=reviewer.get("reviewer_role", ""),
            action=data["action"],
            original_text=data["original_text"],
            edited_text=data.get("edited_text"),
            rationale=data["rationale"],
            source_of_truth=data["source_of_truth"],
            failure_type=data["failure_type"],
            severity=data["severity"],
            golden_dataset=should_update.get("golden_dataset", False),
            prompts=should_update.get("prompts", False),
            retrieval_memory=should_update.get("retrieval_memory", False),
            timestamp=data.get("timestamp"),
        )

    def __repr__(self) -> str:
        return (
            f"HumanFeedbackRecord(feedback_id={self.feedback_id!r}, "
            f"artifact_id={self.artifact_id!r}, "
            f"action={self.action!r}, "
            f"severity={self.severity!r})"
        )


# ---------------------------------------------------------------------------
# FeedbackStore
# ---------------------------------------------------------------------------


class FeedbackStore:
    """Persistence and retrieval layer for human feedback records.

    Records are stored as individual JSON files under
    ``{store_dir}/{feedback_id}.json``.  An artifact index is maintained at
    ``{store_dir}/_artifact_index.json`` mapping ``artifact_id`` to a list
    of ``feedback_id`` values.

    Parameters
    ----------
    store_dir:
        Root directory for feedback storage.  Defaults to
        ``data/human_feedback/``.
    """

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._store_dir: Path = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._index_path: Path = self._store_dir / "_artifact_index.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_feedback(self, record: HumanFeedbackRecord) -> Path:
        """Persist a validated feedback record.

        Parameters
        ----------
        record:
            ``HumanFeedbackRecord`` to save.

        Returns
        -------
        Path
            Path to the written JSON file.

        Raises
        ------
        ValueError
            If the record fails schema validation.
        FileExistsError
            If a record with the same ``feedback_id`` already exists.
        """
        errors = record.validate_against_schema()
        if errors:
            raise ValueError(
                f"Feedback record failed validation: {'; '.join(errors)}"
            )

        dest = self._store_dir / f"{record.feedback_id}.json"
        if dest.exists():
            raise FileExistsError(
                f"Feedback record '{record.feedback_id}' already exists at {dest}"
            )

        dest.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        self._update_index(record.artifact_id, record.feedback_id)
        return dest

    def load_feedback(self, feedback_id: str) -> HumanFeedbackRecord:
        """Load a feedback record by ID.

        Parameters
        ----------
        feedback_id:
            Unique feedback record identifier.

        Returns
        -------
        HumanFeedbackRecord

        Raises
        ------
        FileNotFoundError
            If no record with the given ID exists.
        """
        path = self._store_dir / f"{feedback_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No feedback record found for ID '{feedback_id}'"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return HumanFeedbackRecord.from_dict(data)

    def list_feedback(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[HumanFeedbackRecord]:
        """List all stored feedback records, optionally filtered.

        Parameters
        ----------
        filters:
            Key-value pairs to filter by.  Supported keys: ``artifact_id``,
            ``artifact_type``, ``action``, ``severity``, ``failure_type``,
            ``reviewer_id``, ``reviewer_role``, ``target_level``.

        Returns
        -------
        list[HumanFeedbackRecord]
            Matching records in no guaranteed order.
        """
        records: List[HumanFeedbackRecord] = []
        for path in sorted(self._store_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            record = HumanFeedbackRecord.from_dict(data)
            if filters and not _matches_filters(record, filters):
                continue
            records.append(record)
        return records

    def link_to_artifact(self, artifact_id: str) -> List[str]:
        """Return all feedback IDs linked to a given artifact.

        Parameters
        ----------
        artifact_id:
            Artifact identifier to look up.

        Returns
        -------
        list[str]
            List of feedback IDs.
        """
        index = self._load_index()
        return index.get(artifact_id, [])

    def update_artifact_index(self, artifact_id: str, feedback_id: str) -> None:
        """Explicitly link a feedback record to an artifact in the index.

        Idempotent: calling with an already-linked pair is a no-op.

        Parameters
        ----------
        artifact_id:
            Artifact identifier to link against.
        feedback_id:
            Feedback record identifier to register.
        """
        index = self._load_index()
        index.setdefault(artifact_id, [])
        if feedback_id not in index[artifact_id]:
            index[artifact_id].append(feedback_id)
        self._index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_index(self) -> Dict[str, List[str]]:
        if not self._index_path.exists():
            return {}
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _update_index(self, artifact_id: str, feedback_id: str) -> None:
        self.update_artifact_index(artifact_id, feedback_id)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _matches_filters(record: HumanFeedbackRecord, filters: Dict[str, Any]) -> bool:
    """Return True if ``record`` matches all supplied filter key-value pairs."""
    mapping: Dict[str, Any] = {
        "artifact_id": record.artifact_id,
        "artifact_type": record.artifact_type,
        "action": record.action,
        "severity": record.severity,
        "failure_type": record.failure_type,
        "reviewer_id": record.reviewer_id,
        "reviewer_role": record.reviewer_role,
        "target_level": record.target_level,
    }
    for key, value in filters.items():
        if key in mapping and mapping[key] != value:
            return False
    return True
