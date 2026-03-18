"""
Grounding Verifier — spectrum_systems/modules/evaluation/grounding.py

Claim-level grounding verification for synthesized outputs (especially
working-paper sections).

Every claim in a synthesized document must reference upstream pass artifacts
via ``upstream_pass_refs``.  This module enforces that contract at evaluation
time.

Design principles
-----------------
- NO silent passing: every ungrounded claim is a hard FAIL.
- NO tolerating missing references: a reference that does not exist in the
  provided upstream artifacts is a hard FAIL.
- Semantic mismatch detection: the referenced artifact must actually contain
  content related to the claim (substring / keyword overlap check).
- No external dependencies beyond the Python standard library.

Claim structure
---------------
A claim is a dict with at minimum::

    {
      "text": "<claim text>",
      "upstream_pass_refs": ["<pass_id_1>", ...]   # required; must be non-empty
    }

A document is a dict that may contain a ``"claims"`` list of claim dicts,
or a ``"sections"`` list where each section has a ``"claims"`` list.

Public API
----------
GroundingVerifier
    Main verifier class.

GroundingResult
    Result of verifying a single claim.

DocumentGroundingResult
    Aggregated result of verifying a full document.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GroundingResult:
    """Result of verifying a single claim.

    Attributes
    ----------
    claim_text:
        The claim text that was verified.
    grounded:
        ``True`` only if all upstream references exist and are semantically
        consistent with the claim.
    missing_refs:
        List of reference IDs declared in the claim but absent from
        ``upstream_artifacts``.
    mismatched_refs:
        List of reference IDs that exist but whose content does not
        semantically overlap with the claim text.
    """

    claim_text: str
    grounded: bool
    missing_refs: List[str] = field(default_factory=list)
    mismatched_refs: List[str] = field(default_factory=list)


@dataclass
class DocumentGroundingResult:
    """Aggregated grounding result for a full document.

    Attributes
    ----------
    grounded:
        ``True`` only if every claim in the document is grounded.
    total_claims:
        Number of claims verified.
    failed_claims:
        Number of claims that failed grounding.
    claim_results:
        Per-claim ``GroundingResult`` instances.
    """

    grounded: bool
    total_claims: int
    failed_claims: int
    claim_results: List[GroundingResult] = field(default_factory=list)

    @property
    def grounding_score(self) -> float:
        """Fraction of claims that are grounded (0.0–1.0)."""
        if self.total_claims == 0:
            return 1.0
        return (self.total_claims - self.failed_claims) / self.total_claims


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class GroundingVerifier:
    """Verifies that synthesized claims are traceable to upstream artifacts.

    Parameters
    ----------
    min_overlap_tokens:
        Minimum number of shared non-trivial tokens required for a reference
        to be considered semantically consistent with the claim.  Defaults to
        ``1`` (at least one meaningful word must overlap).
    """

    _STOP_WORDS = frozenset({
        "a", "an", "the", "and", "or", "of", "to", "in", "is", "are",
        "was", "were", "that", "this", "it", "its", "for", "on", "at",
        "by", "with", "from", "as", "be", "been", "being", "have", "has",
        "had", "do", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "can", "not", "no", "but", "if", "so",
        "than", "then", "we", "they", "he", "she", "i", "you", "our",
        "their", "his", "her", "my", "your",
    })

    def __init__(self, min_overlap_tokens: int = 1) -> None:
        self._min_overlap_tokens = min_overlap_tokens

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def verify_claim(
        self,
        claim: Dict[str, Any],
        upstream_artifacts: Dict[str, Any],
    ) -> GroundingResult:
        """Verify a single claim against upstream artifacts.

        Parameters
        ----------
        claim:
            Claim dict.  Must contain ``"text"`` and ``"upstream_pass_refs"``.
        upstream_artifacts:
            Mapping of ``pass_id -> artifact content`` (typically the
            ``intermediate_artifacts`` dict from a ``PassChainRecord``).

        Returns
        -------
        GroundingResult
            ``grounded=False`` if:

            * ``upstream_pass_refs`` is absent or empty,
            * any declared reference ID is absent from ``upstream_artifacts``,
            * any reference exists but its content does not semantically
              overlap with the claim text.
        """
        claim_text: str = claim.get("text", "")
        refs: List[str] = claim.get("upstream_pass_refs", [])

        # Rule 1 — claim must declare at least one upstream reference
        if not refs:
            return GroundingResult(
                claim_text=claim_text,
                grounded=False,
                missing_refs=[],
                mismatched_refs=[],
            )

        missing_refs: List[str] = []
        mismatched_refs: List[str] = []

        for ref_id in refs:
            if ref_id not in upstream_artifacts:
                missing_refs.append(ref_id)
            else:
                artifact_content = upstream_artifacts[ref_id]
                if not self._semantic_overlap(claim_text, artifact_content):
                    mismatched_refs.append(ref_id)

        grounded = not missing_refs and not mismatched_refs
        return GroundingResult(
            claim_text=claim_text,
            grounded=grounded,
            missing_refs=missing_refs,
            mismatched_refs=mismatched_refs,
        )

    def verify_document(
        self,
        document: Dict[str, Any],
        upstream_artifacts: Dict[str, Any],
    ) -> DocumentGroundingResult:
        """Verify all claims in a document.

        Extracts claims from:
        - ``document["claims"]`` (flat list), or
        - ``document["sections"]`` where each section may have a ``"claims"``
          list.

        Parameters
        ----------
        document:
            Synthesized document dict.
        upstream_artifacts:
            Mapping of ``pass_id -> artifact content``.

        Returns
        -------
        DocumentGroundingResult
        """
        claims = self._extract_claims(document)
        claim_results: List[GroundingResult] = []

        for claim in claims:
            result = self.verify_claim(claim, upstream_artifacts)
            claim_results.append(result)

        failed = sum(1 for r in claim_results if not r.grounded)
        return DocumentGroundingResult(
            grounded=(failed == 0),
            total_claims=len(claim_results),
            failed_claims=failed,
            claim_results=claim_results,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_claims(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract all claim dicts from a document structure."""
        claims: List[Dict[str, Any]] = []

        # Flat claims list
        if "claims" in document and isinstance(document["claims"], list):
            claims.extend(document["claims"])

        # Sectioned document
        if "sections" in document and isinstance(document["sections"], list):
            for section in document["sections"]:
                if isinstance(section, dict) and "claims" in section:
                    if isinstance(section["claims"], list):
                        claims.extend(section["claims"])

        return claims

    def _tokenize(self, text: str) -> frozenset:
        """Lowercase-tokenize text, removing stop words and punctuation."""
        raw_tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
        return frozenset(t for t in raw_tokens if t not in self._STOP_WORDS and len(t) > 1)

    def _artifact_text(self, artifact: Any) -> str:
        """Coerce an artifact to a searchable text string."""
        if isinstance(artifact, str):
            return artifact
        if isinstance(artifact, (dict, list)):
            try:
                import json as _json
                return _json.dumps(artifact)
            except (TypeError, ValueError):
                return str(artifact)
        return str(artifact)

    def _semantic_overlap(self, claim_text: str, artifact: Any) -> bool:
        """Return True if claim and artifact share ≥ min_overlap_tokens tokens."""
        artifact_str = self._artifact_text(artifact)
        claim_tokens = self._tokenize(claim_text)
        artifact_tokens = self._tokenize(artifact_str)
        if not claim_tokens:
            # Empty claim — treat as overlapping (no meaningful content to check)
            return True
        shared = claim_tokens & artifact_tokens
        return len(shared) >= self._min_overlap_tokens
