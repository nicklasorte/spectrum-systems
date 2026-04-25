#!/usr/bin/env python3
"""Generate suggested repair patches for 3LS authority preflight violations.

This script reads the structured preflight result produced by
scripts/run_3ls_authority_preflight.py and emits a derived
3ls_authority_repair_suggestions artifact.

Hard constraints:
- Suggestions only. No source files are modified by this script.
- Suggestions never propose adding an allowlist override for non-owner files.
- For non-owner files, only neutral vocabulary replacements are suggested.
- For files that are declared canonical owners under
  three_letter_system_authority but still triggered a violation, the suggestion
  flags the violation as needing manual review by the system's owner team
  (not silent allowlist expansion).
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
        is_owner = bool(violation.get("three_letter_system_owner", False))
        owned_domains = violation.get("authority_domains_owned", []) or []

        if not token:
            continue

        suggested_terms = list(replacements.get(token, []))

        if is_owner:
            suggestions.append(
                {
                    "path": path,
                    "line": line,
                    "forbidden_token": token,
                    "suggested_terms": [],
                    "rationale": (
                        f"This file is a declared owner of "
                        f"{owned_domains or ['<unknown>']} under "
                        "authority_registry.json::three_letter_system_authority, "
                        "yet still triggered the leak guard. The forbidden "
                        "token may be valid here but must be reviewed manually "
                        "by the owning system's maintainers. Do NOT widen "
                        "vocabulary_overrides to silence this — confirm the "
                        "authority domain alignment first."
                    ),
                    "owner_authority_review_required": True,
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
                        "Forbidden authority semantics detected outside any "
                        "canonical owner. No direct neutral replacement is "
                        "registered for this token; restructure the surface "
                        "to remove the authority semantics or move the logic "
                        "to a canonical owner declared in "
                        "authority_registry.json."
                    ),
                    "owner_authority_review_required": False,
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
                    "TLC/PQX/RDX/MAP/DASHBOARD may verify and route gate "
                    "evidence but may not express control authority. Replace "
                    f"'{token}' with one of the suggested neutral terms."
                ),
                "owner_authority_review_required": False,
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
