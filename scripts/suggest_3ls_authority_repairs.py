#!/usr/bin/env python3
"""Generate suggested repair patches for 3-letter system preflight violations.

This script reads the structured preflight result produced by
scripts/run_3ls_authority_preflight.py and emits a derived
3ls_authority_repair_suggestions artifact.

The suggestions are non-owning. Canonical responsibility is declared in
docs/architecture/system_registry.md. The suggester only proposes neutral
vocabulary replacements or a manual-review flag; it never widens allowlist
entries and never claims new ownership.

Hard constraints:
- Suggestions only. No source files are modified by this script.
- Suggestions never propose adding an allowlist override for non-support files.
- For non-support files, only neutral vocabulary replacements are suggested.
- For files that match a declared support prefix but still triggered a
  violation, the suggestion flags the violation as needing manual review
  against the canonical registry (not silent allowlist expansion).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


DEFAULT_INPUT = "outputs/3ls_authority_preflight/3ls_authority_preflight_result.json"
DEFAULT_OUTPUT = "outputs/3ls_authority_preflight/3ls_authority_repair_suggestions.json"
DEFAULT_NEUTRAL_VOCAB = "contracts/governance/authority_neutral_vocabulary.json"


class AuthorityRepairSuggestionError(ValueError):
    """Raised when repair suggestions cannot be generated deterministically."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate suggested repairs for 3LS authority preflight findings"
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Preflight result artifact path")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Suggestion artifact path")
    parser.add_argument(
        "--neutral-vocabulary",
        default=DEFAULT_NEUTRAL_VOCAB,
        help="Neutral vocabulary map path",
    )
    return parser.parse_args()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuthorityRepairSuggestionError(f"required input missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_suggestions(
    preflight_result: dict[str, Any],
    neutral_vocab: dict[str, Any],
) -> list[dict[str, Any]]:
    if preflight_result.get("artifact_type") != "3ls_authority_preflight_result":
        raise AuthorityRepairSuggestionError(
            "input artifact_type must be '3ls_authority_preflight_result'"
        )
    replacements = neutral_vocab.get("neutral_replacements", {}) or {}
    suggestions: list[dict[str, Any]] = []
    for violation in preflight_result.get("violations", []) or []:
        token = str(violation.get("token", "")).strip().lower()
        path = violation.get("path")
        line = violation.get("line")
        is_support_match = bool(
            violation.get("three_letter_system_support_match", False)
        )
        boundary_role = violation.get("boundary_role")
        canonical_source = violation.get(
            "canonical_authority_source",
            "docs/architecture/system_registry.md",
        )

        if not token:
            continue

        suggested_terms = list(replacements.get(token, []))

        if is_support_match:
            suggestions.append(
                {
                    "path": path,
                    "line": line,
                    "forbidden_token": token,
                    "suggested_terms": [],
                    "rationale": (
                        f"This file matches the support classification "
                        f"'{boundary_role or 'unknown'}' in the non-owning "
                        "boundary guidance. Canonical responsibility is "
                        f"declared in {canonical_source}. The forbidden "
                        "token may be valid only when the canonical "
                        "registry assigns the matching responsibility to "
                        "the file's surface. Confirm against the canonical "
                        "registry first; do NOT widen vocabulary_overrides "
                        "to silence this finding."
                    ),
                    "owner_authority_review_required": True,
                    "canonical_authority_source": canonical_source,
                    "propose_allowlist_override": False,
                }
            )
            continue

        if not suggested_terms:
            suggestions.append(
                {
                    "path": path,
                    "line": line,
                    "forbidden_token": token,
                    "suggested_terms": [],
                    "rationale": (
                        "Forbidden vocabulary detected on a path that does "
                        "not match any non-owning support entry. No direct "
                        "neutral replacement is registered for this token; "
                        "restructure the surface to remove the protected "
                        "semantics or move the logic to the canonical "
                        f"responsibility owner declared in {canonical_source}."
                    ),
                    "owner_authority_review_required": False,
                    "canonical_authority_source": canonical_source,
                    "propose_allowlist_override": False,
                }
            )
            continue

        suggestions.append(
            {
                "path": path,
                "line": line,
                "forbidden_token": token,
                "suggested_terms": suggested_terms,
                "rationale": (
                    "Non-owning support surfaces may verify and route gate "
                    "evidence but must not claim protected vocabulary. "
                    f"Canonical responsibility is declared in "
                    f"{canonical_source}. Replace '{token}' with one of "
                    "the suggested neutral terms."
                ),
                "owner_authority_review_required": False,
                "canonical_authority_source": canonical_source,
                "propose_allowlist_override": False,
            }
        )
    return suggestions


def build_artifact(
    preflight_result: dict[str, Any],
    suggestions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "artifact_type": "3ls_authority_repair_suggestions",
        "artifact_version": "1.0.0",
        "source_artifact": preflight_result.get("artifact_type"),
        "source_status": preflight_result.get("status"),
        "suggestions": suggestions,
        "summary": {
            "suggestion_count": len(suggestions),
            "owner_review_required_count": sum(
                1 for s in suggestions if s.get("owner_authority_review_required")
            ),
            "allowlist_override_proposed_count": sum(
                1 for s in suggestions if s.get("propose_allowlist_override")
            ),
        },
    }


def main() -> int:
    args = _parse_args()

    input_path = REPO_ROOT / args.input
    neutral_vocab_path = REPO_ROOT / args.neutral_vocabulary

    preflight_result = _load_json(input_path)
    neutral_vocab = _load_json(neutral_vocab_path)

    if neutral_vocab.get("artifact_type") != "authority_neutral_vocabulary":
        raise AuthorityRepairSuggestionError(
            "neutral vocabulary artifact_type must be 'authority_neutral_vocabulary'"
        )

    suggestions = build_suggestions(preflight_result, neutral_vocab)
    artifact = build_artifact(preflight_result, suggestions)

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "suggestion_count": artifact["summary"]["suggestion_count"],
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
