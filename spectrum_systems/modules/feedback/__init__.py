"""
Feedback module — spectrum_systems/modules/feedback/__init__.py

Human Feedback Capture + Structured Review System (Prompt AO).

Public submodules
-----------------
human_feedback
    HumanFeedbackRecord and FeedbackStore data model.
feedback_ingest
    Ingestion helpers for creating and attaching feedback records.
claim_extraction
    Breaks documents into reviewable claim-level units.
review_session
    ReviewSession class for interactive multi-claim review flows.
feedback_mapping
    Bridge from feedback records to the AU error taxonomy.
"""
from spectrum_systems.modules.feedback.human_feedback import HumanFeedbackRecord, FeedbackStore
from spectrum_systems.modules.feedback.claim_extraction import extract_claims, ClaimUnit
from spectrum_systems.modules.feedback.review_session import ReviewSession
from spectrum_systems.modules.feedback.feedback_mapping import map_feedback_to_error_type

__all__ = [
    "HumanFeedbackRecord",
    "FeedbackStore",
    "extract_claims",
    "ClaimUnit",
    "ReviewSession",
    "map_feedback_to_error_type",
]
