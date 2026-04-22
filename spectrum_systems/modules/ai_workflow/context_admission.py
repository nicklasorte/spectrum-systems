"""CTX: Context source admission with trust-tier enforcement.

Validates all context bundle inputs against trust-tier schema.
Blocks sources of insufficient trust tier or unknown type.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"

TIER_RANK: Dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}

TRUST_TIERS: Dict[str, List[str]] = {
    "HIGH": ["transcript", "official_minutes", "signed_policy", "transcript_artifact",
             "admission_bundle"],
    "MEDIUM": ["inferred_context", "synthesized_summary", "context_bundle",
               "context_bundle_record", "context_bundle_v2"],
    "LOW": ["uncertain_extraction", "synthetic_fixture"],
}

# Inverted map: source_type → tier
_SOURCE_TIER: Dict[str, str] = {
    source: tier
    for tier, sources in TRUST_TIERS.items()
    for source in sources
}


class ContextAdmissionPolicy:
    """Schema-validates context sources; blocks unknowns and under-tier inputs."""

    def __init__(self, schema_dir: Path | None = None):
        self.schema_dir = schema_dir or SCHEMA_DIR

    def _source_has_schema(self, source_type: str) -> bool:
        """Check schema existence, also trying the _artifact suffix variant."""
        clean = source_type.lower().replace(" ", "_").replace("-", "_")
        if (self.schema_dir / f"{clean}.schema.json").exists():
            return True
        # Many source types are schema-named as <type>_artifact
        return (self.schema_dir / f"{clean}_artifact.schema.json").exists()

    def _effective_tier(self, source: Dict) -> str:
        """Resolve effective trust tier for a source entry."""
        explicit = source.get("trust_tier", "UNKNOWN")
        if explicit and explicit != "UNKNOWN":
            return explicit
        # Fall back to type-derived tier
        return _SOURCE_TIER.get(source.get("type", ""), "UNKNOWN")

    def admit_context_bundle(
        self, bundle: Dict, required_tier: str = "HIGH"
    ) -> Tuple[bool, str]:
        """Admit context bundle only if all sources meet the required trust tier.

        Returns (admitted, reason).
        """
        required_rank = TIER_RANK.get(required_tier, 0)
        sources = bundle.get("sources", [])

        for source in sources:
            source_type = source.get("type", "UNKNOWN")

            if not self._source_has_schema(source_type):
                return False, f"Unknown source type '{source_type}': no schema found"

            effective_tier = self._effective_tier(source)
            actual_rank = TIER_RANK.get(effective_tier, 0)

            if actual_rank < required_rank:
                return (
                    False,
                    f"Source '{source_type}' tier '{effective_tier}' is below "
                    f"required '{required_tier}'",
                )

        return True, "Admitted"

    def classify_source(self, source_type: str) -> str:
        """Return the trust tier for a known source type."""
        return _SOURCE_TIER.get(source_type, "UNKNOWN")
