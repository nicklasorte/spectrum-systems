"""
Review Session — spectrum_systems/modules/feedback/review_session.py

Interactive review session management for claim-by-claim human feedback.

A ``ReviewSession`` loads an artifact, extracts its claims, and iterates
through them so a reviewer can record structured feedback on each.  The
session emits multiple ``HumanFeedbackRecord`` instances — one per reviewed
claim — and writes a session summary on close.

Design principles
-----------------
- Sessions are non-interactive by default (suitable for programmatic use).
- Feedback records are persisted incrementally; a crash mid-session does not
  lose already-recorded feedback.
- Reviewers may skip claims; skipped claims are excluded from the summary.

Public API
----------
ReviewSession
    Session context object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from spectrum_systems.modules.feedback.claim_extraction import ClaimUnit, extract_claims
from spectrum_systems.modules.feedback.human_feedback import FeedbackStore, HumanFeedbackRecord


# ---------------------------------------------------------------------------
# ReviewSession
# ---------------------------------------------------------------------------


class ReviewSession:
    """Manages an interactive review session over the claims of an artifact.

    Parameters
    ----------
    artifact_id:
        Unique identifier of the artifact under review.
    reviewer_id:
        Unique identifier of the reviewer.
    reviewer_role:
        Professional role of the reviewer.
    artifact:
        The artifact document dict (or plain string) to extract claims from.
    artifact_type:
        Type of the artifact (must be a valid ``artifact_type`` enum value).
    store:
        ``FeedbackStore`` to persist records.  A default store is created if
        not provided.
    """

    def __init__(
        self,
        artifact_id: str,
        reviewer_id: str,
        reviewer_role: str,
        artifact: Any,
        artifact_type: str = "working_paper",
        store: Optional[FeedbackStore] = None,
    ) -> None:
        self.artifact_id = artifact_id
        self.reviewer_id = reviewer_id
        self.reviewer_role = reviewer_role
        self.artifact = artifact
        self.artifact_type = artifact_type
        self._store = store or FeedbackStore()

        self._claims: List[ClaimUnit] = []
        self._feedback_records: List[HumanFeedbackRecord] = []
        self._started_at: Optional[str] = None
        self._closed_at: Optional[str] = None
        self._active: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_session(self) -> "ReviewSession":
        """Begin the session: extract claims from the artifact.

        Returns
        -------
        ReviewSession
            Self, for method chaining.

        Raises
        ------
        RuntimeError
            If the session has already been started or closed.
        """
        if self._active:
            raise RuntimeError("Session is already active.")
        if self._closed_at is not None:
            raise RuntimeError("Session has already been closed.")

        self._claims = extract_claims(self.artifact)
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._active = True
        return self

    def close_session(self) -> Dict[str, Any]:
        """End the session and return a summary dict.

        Returns
        -------
        dict
            Session summary including:

            - ``artifact_id``
            - ``reviewer_id``
            - ``started_at``, ``closed_at``
            - ``total_claims``
            - ``reviewed_claims``
            - ``skipped_claims``
            - ``feedback_ids`` — list of persisted feedback record IDs

        Raises
        ------
        RuntimeError
            If the session has not been started.
        """
        if not self._active:
            raise RuntimeError("Session is not active.  Call start_session() first.")

        self._closed_at = datetime.now(timezone.utc).isoformat()
        self._active = False

        reviewed = len(self._feedback_records)
        total = len(self._claims)

        return {
            "artifact_id": self.artifact_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role,
            "artifact_type": self.artifact_type,
            "started_at": self._started_at,
            "closed_at": self._closed_at,
            "total_claims": total,
            "reviewed_claims": reviewed,
            "skipped_claims": total - reviewed,
            "feedback_ids": [r.feedback_id for r in self._feedback_records],
        }

    # ------------------------------------------------------------------
    # Claim iteration
    # ------------------------------------------------------------------

    def iterate_claims(self) -> Generator[ClaimUnit, None, None]:
        """Yield each extracted claim in document order.

        Raises
        ------
        RuntimeError
            If the session has not been started.
        """
        if not self._active:
            raise RuntimeError("Session is not active.  Call start_session() first.")
        yield from self._claims

    # ------------------------------------------------------------------
    # Feedback recording
    # ------------------------------------------------------------------

    def record_feedback(
        self,
        claim_id: str,
        feedback: Dict[str, Any],
    ) -> HumanFeedbackRecord:
        """Record structured feedback for a specific claim.

        Parameters
        ----------
        claim_id:
            Identifier of the claim being reviewed.
        feedback:
            Dict of reviewer-supplied feedback fields.  Required keys:

            - ``action`` — reviewer disposition
            - ``rationale`` — explanation
            - ``source_of_truth`` — authoritative source relied upon
            - ``failure_type`` — AU-aligned failure classification
            - ``severity`` — impact severity
            - ``should_update`` — dict of downstream update flags

            Optional keys:

            - ``edited_text`` — corrected text (required for edit/rewrite actions)

        Returns
        -------
        HumanFeedbackRecord
            The persisted feedback record.

        Raises
        ------
        RuntimeError
            If the session is not active.
        ValueError
            If ``claim_id`` is not found in this session's claim set, or if
            the feedback record fails validation.
        """
        if not self._active:
            raise RuntimeError("Session is not active.  Call start_session() first.")

        # Locate the claim
        claim = next((c for c in self._claims if c.claim_id == claim_id), None)
        if claim is None:
            raise ValueError(
                f"Claim ID '{claim_id}' not found in session for artifact '{self.artifact_id}'"
            )

        should_update = feedback.get("should_update", {})

        record = HumanFeedbackRecord(
            artifact_id=self.artifact_id,
            artifact_type=self.artifact_type,
            target_level="claim",
            target_id=claim_id,
            reviewer_id=self.reviewer_id,
            reviewer_role=self.reviewer_role,
            action=feedback["action"],
            original_text=claim.claim_text,
            edited_text=feedback.get("edited_text"),
            rationale=feedback["rationale"],
            source_of_truth=feedback["source_of_truth"],
            failure_type=feedback["failure_type"],
            severity=feedback["severity"],
            golden_dataset=should_update.get("golden_dataset", False),
            prompts=should_update.get("prompts", False),
            retrieval_memory=should_update.get("retrieval_memory", False),
        )

        self._store.save_feedback(record)
        self._feedback_records.append(record)
        return record

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def claims(self) -> List[ClaimUnit]:
        """The extracted claims for this session (populated after start)."""
        return list(self._claims)

    @property
    def feedback_records(self) -> List[HumanFeedbackRecord]:
        """All feedback records recorded in this session so far."""
        return list(self._feedback_records)

    @property
    def is_active(self) -> bool:
        """Whether the session is currently active."""
        return self._active
