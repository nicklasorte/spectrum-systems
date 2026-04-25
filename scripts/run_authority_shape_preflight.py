#!/usr/bin/env python3
"""Authority-shape preflight: run the structural shape detector over the
changed-file set and emit a JSON artifact with violations and suggested
advisory-safe renames.

This is a developer-facing convenience: the fail-closed enforcement still
lives in ``run_authority_leak_guard.py`` and the CI guards. The preflight
exists so contributors can surface authority-shape risks (and their
suggested rewrites) before opening a PR.

Default mode (``--suggest-only``) always exits 0 — the script's job is
to produce a structured artifact, not to fail closed. Pass ``--strict``
to mirror the CI guard and exit 1 when violations are present.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.authority_leak_rules import (  # noqa: E402
    find_forbidden_vocabulary,
    load_authority_registry,
)
from scripts.authority_shape_detector import detect_authority_shapes  # noqa: E402
from spectrum_systems.modules.governance.changed_files import (  # noqa: E402
    ChangedFilesResolutionError,
    resolve_changed_files,
)


# Suggested advisory-safe rewrites for authority-shaped vocabulary tokens.
# These suggestions are advisory only — contributors are expected to choose
# the term that best matches the local semantics. The mapping is
# intentionally narrow so it does not collide with canonical-owner code.
_SUGGESTED_RENAMES: dict[str, str] = {
    "decision": "advisory_result",
    "promotion_decision": "release_readiness_signal",
    "control_decision": "control_input",
    "certification_record": "evidence_packet",
    "rollback_record": "rollback_signal",
    "promote": "advise_release",
    "promoted": "released_externally",
    "promotion_ready": "release_readiness_signal",
    "certification_status": "readiness_signal",
    "certified": "evidence_complete",
    "enforcement_action": "advisory_action",
    "allow": "ready_signal",
    "block": "risk_signal",
    "freeze": "warn_signal",
    "warn": "warn_signal",
    "approved": "evidence_complete",
    "rollback": "restoration_signal",
    "quarantine": "isolation_recommendation",
    "promotion gate": "release readiness check",
    "certification gate": "advisory readiness check",
    "control decision": "control input",
}


_AUTHORITY_TOKEN_RE = re.compile(
    r"\b(promotion_decision|rollback_record|control_decision|certification_record|"
    r"certification_status|promotion_ready|enforcement_action|"
    r"promotion gate|certification gate|control decision|"
    r"approved|certified|promoted|quarantine|rollback|promote|"
    r"allow|warn|block|freeze)\b",
    re.IGNORECASE,
)


def _suggest(token: str) -> str | None:
    return _SUGGESTED_RENAMES.get(token.lower())


def _scan_text_lines(rel_path: str, text: str) -> list[dict[str, object]]:
    """Surface advisory rewrite hints for human readers.

    The hints are non-fail-closed — they exist so a contributor can spot
    authority-shaped phrasing before opening a PR. The fail-closed gate is
    the leak guard.
    """
    hints: list[dict[str, object]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        for match in _AUTHORITY_TOKEN_RE.finditer(line):
            token = match.group(1)
            suggestion = _suggest(token)
            if not suggestion:
                continue
            hints.append(
                {
                    "rule": "authority_shape_text_hint",
                    "path": rel_path,
                    "line": idx,
                    "token": token,
                    "suggested_rename": suggestion,
                    "message": (
                        f"authority-shaped token '{token}' — consider "
                        f"'{suggestion}' if this is not a canonical owner reference"
                    ),
                }
            )
    return hints


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Authority-shape preflight (advisory)"
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git base ref for changed-file resolution",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git head ref for changed-file resolution",
    )
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=[],
        help="Explicit changed files (overrides git diff)",
    )
    parser.add_argument(
        "--registry",
        default="contracts/governance/authority_registry.json",
        help="Authority registry path",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_shape_preflight_result.json",
        help="Output artifact path",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--suggest-only",
        action="store_true",
        default=True,
        help="Always exit 0; emit suggestions in the artifact (default)",
    )
    mode.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Exit 1 on any violation (mirrors run_authority_leak_guard)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise SystemExit(f"hop_authority_shape_preflight_changed_files_error:{exc}") from exc

    registry_path = REPO_ROOT / args.registry
    if not registry_path.is_file():
        raise SystemExit(
            f"hop_authority_shape_preflight_missing_registry:{registry_path}"
        )
    registry = load_authority_registry(registry_path)

    structural_violations: list[dict[str, object]] = []
    vocabulary_violations: list[dict[str, object]] = []
    text_hints: list[dict[str, object]] = []
    scanned_files: list[str] = []

    for rel_path in changed_files:
        full_path = REPO_ROOT / rel_path
        if not full_path.is_file():
            continue
        if full_path.suffix.lower() not in {".py", ".json", ".md", ".yml", ".yaml", ".txt"}:
            continue

        scanned_files.append(rel_path)
        try:
            structural_violations.extend(
                detect_authority_shapes(Path(rel_path), registry)
            )
            vocabulary_violations.extend(
                find_forbidden_vocabulary(Path(rel_path), registry)
            )
            text_hints.extend(
                _scan_text_lines(rel_path, full_path.read_text(encoding="utf-8"))
            )
        except (json.JSONDecodeError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            raise SystemExit(
                f"hop_authority_shape_preflight_scan_error:{rel_path}:{exc}"
            ) from exc

    suggestions: list[dict[str, object]] = []
    for v in structural_violations:
        token = v.get("artifact_type") or v.get("schema_ref")
        if not isinstance(token, str):
            continue
        for needle, replacement in _SUGGESTED_RENAMES.items():
            if needle in token:
                suggestions.append(
                    {
                        "path": v.get("path"),
                        "rule": v.get("rule"),
                        "field": "artifact_type" if v.get("artifact_type") else "schema_ref",
                        "current": token,
                        "suggested_rename": token.replace(needle, replacement),
                    }
                )
                break

    has_violations = bool(structural_violations or vocabulary_violations)
    status = "fail" if has_violations else "pass"

    result = {
        "artifact_type": "authority_shape_preflight_result",
        "status": status,
        "mode": "strict" if args.strict else "suggest_only",
        "changed_files": changed_files,
        "scanned_files": sorted(set(scanned_files)),
        "structural_violations": structural_violations,
        "vocabulary_violations": vocabulary_violations,
        "text_hints": text_hints,
        "suggested_renames": suggestions,
        "summary": {
            "structural_violation_count": len(structural_violations),
            "vocabulary_violation_count": len(vocabulary_violations),
            "text_hint_count": len(text_hints),
            "suggestion_count": len(suggestions),
        },
    }

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "mode": result["mode"],
                "changed_files": changed_files,
                "structural_violation_count": result["summary"]["structural_violation_count"],
                "vocabulary_violation_count": result["summary"]["vocabulary_violation_count"],
                "text_hint_count": result["summary"]["text_hint_count"],
                "output": str(output_path),
            },
            indent=2,
        )
    )

    if args.strict and has_violations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
