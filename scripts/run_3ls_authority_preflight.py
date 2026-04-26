#!/usr/bin/env python3
"""3-Letter System Authority Boundary Firewall preflight.

Runs before full CI to catch protected vocabulary leaks earlier than the
existing scripts/run_authority_leak_guard.py CI gate.

This preflight does NOT define ownership. Canonical ownership is declared in
docs/architecture/system_registry.md and is read indirectly via the existing
authority registry. The preflight only reads non-owning support guidance from
contracts/governance/authority_registry.json::three_letter_system_boundary_guidance
to classify changed files and recommend neutral vocabulary.

Behavior:
- Resolves changed files via the shared changed_files helper.
- Loads the authority registry and the neutral vocabulary map.
- Reuses the existing leak detector for vocabulary detection.
- Reuses the existing shape detector for structural detection.
- Annotates every violation with the support classification of the changed
  path (boundary_role + canonical_authority_source).
- Suggests a neutral replacement for each forbidden vocabulary token.

Fail-closed:
- Missing registry, missing neutral vocabulary map, or scan failure all fail.
- Any violation fails.

This preflight does NOT replace scripts/run_authority_leak_guard.py.
The CI gate remains binding; the preflight is local fast feedback.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

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


DEFAULT_REGISTRY = "contracts/governance/authority_registry.json"
DEFAULT_NEUTRAL_VOCAB = "contracts/governance/authority_neutral_vocabulary.json"
DEFAULT_OUTPUT = "outputs/3ls_authority_preflight/3ls_authority_preflight_result.json"

SCAN_SUFFIXES = {".py", ".json", ".md", ".yaml", ".yml", ".txt"}

# H01F-4: Routing bypass guard
# Owner module that may legitimately use the unchecked symbol.
ROUTING_AUTHORITY_OWNER = "spectrum_systems/modules/orchestration/tlc_router.py"

# Test and tooling surfaces that probe the bypass guard. They reference the
# unchecked symbol intentionally to verify the guard's behaviour and must not
# self-trigger ROUTING_BYPASS_ATTEMPT findings. Adding to this list is a
# governance event: it requires a passing review_artifact justifying the
# probe path.
ROUTING_BYPASS_GUARD_PROBES: frozenset[str] = frozenset(
    {
        "scripts/run_3ls_authority_preflight.py",
        "tests/transcript_pipeline/test_no_unchecked_routing.py",
        "tests/transcript_pipeline/test_replay_integrity_h01.py",
    }
)

# Patterns that indicate a routing-bypass attempt:
#   1. Direct call to the unchecked internal entrypoint
#   2. Import of the unchecked symbol from any module
#   3. Re-export wrappers that surface unchecked routing
#   4. Public alias `route_artifact` that resurrects the legacy entrypoint
ROUTING_BYPASS_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    (
        "calls _route_artifact_unchecked directly",
        re.compile(r"\b_route_artifact_unchecked\s*\("),
    ),
    (
        "imports _route_artifact_unchecked",
        re.compile(r"\bimport\s+[^#\n]*\b_route_artifact_unchecked\b"),
    ),
    (
        "from-imports _route_artifact_unchecked",
        re.compile(r"\bfrom\s+\S+\s+import\s+[^#\n]*\b_route_artifact_unchecked\b"),
    ),
    (
        "re-exports unchecked routing symbol",
        re.compile(r"['\"]_route_artifact_unchecked['\"]"),
    ),
    (
        "defines or restores public route_artifact alias",
        re.compile(r"\broute_artifact\s*=\s*[A-Za-z_][\w\.]*"),
    ),
    (
        "defines public route_artifact function",
        re.compile(r"^\s*def\s+route_artifact\s*\(", re.MULTILINE),
    ),
)


class ThreeLetterAuthorityPreflightError(ValueError):
    """Raised when the 3LS authority preflight cannot complete deterministically."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed 3LS authority boundary preflight")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="Authority registry path")
    parser.add_argument(
        "--neutral-vocabulary",
        default=DEFAULT_NEUTRAL_VOCAB,
        help="Neutral vocabulary map path",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output artifact path")
    return parser.parse_args()


def load_neutral_vocabulary(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ThreeLetterAuthorityPreflightError(
            f"authority neutral vocabulary missing: {path}"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ThreeLetterAuthorityPreflightError(
            "authority neutral vocabulary must be a JSON object"
        )
    if payload.get("artifact_type") != "authority_neutral_vocabulary":
        raise ThreeLetterAuthorityPreflightError(
            "neutral vocabulary artifact_type must be 'authority_neutral_vocabulary'"
        )
    if "neutral_replacements" not in payload or "forbidden_terms" not in payload:
        raise ThreeLetterAuthorityPreflightError(
            "neutral vocabulary missing required keys: forbidden_terms, neutral_replacements"
        )
    return payload


def _normalize_path(path: str) -> str:
    raw = path.replace("\\", "/")
    repo_prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if raw.startswith(repo_prefix):
        raw = raw[len(repo_prefix):]
    return raw.strip("/")


def classify_three_letter_system(path: str, registry: dict[str, Any]) -> dict[str, Any]:
    """Classify a path against three_letter_system_boundary_guidance entries.

    Returns dict with system, boundary_role, support_match, and the
    canonical_authority_source used by that registry entry. If the path
    matches no declared support prefix, returns support_match=False with
    system='unknown' so the caller treats it as a non-support surface.

    This function does not assign ownership. Canonical ownership is declared
    in docs/architecture/system_registry.md and is referenced via
    canonical_authority_source.
    """
    normalized = _normalize_path(path)
    guidance = registry.get("three_letter_system_boundary_guidance", {})
    if not isinstance(guidance, dict):
        return {
            "system": "unknown",
            "boundary_role": None,
            "support_match": False,
            "canonical_authority_source": None,
        }
    best_match: dict[str, Any] | None = None
    best_match_len = -1
    for system, body in guidance.items():
        if not isinstance(body, dict):
            continue
        canonical_source = body.get(
            "canonical_authority_source",
            registry.get("three_letter_system_boundary_guidance", {}).get(
                "canonical_authority_source"
            ),
        )
        for prefix in body.get("support_path_prefixes", []) or []:
            prefix_norm = str(prefix).strip().rstrip("/")
            if not prefix_norm:
                continue
            if prefix_norm.endswith(".py") or prefix_norm.endswith(".json"):
                if normalized == prefix_norm and len(prefix_norm) > best_match_len:
                    best_match = {
                        "system": system,
                        "boundary_role": body.get("boundary_role"),
                        "support_match": True,
                        "canonical_authority_source": canonical_source,
                    }
                    best_match_len = len(prefix_norm)
            else:
                if normalized.startswith(prefix_norm + "/") and len(prefix_norm) > best_match_len:
                    best_match = {
                        "system": system,
                        "boundary_role": body.get("boundary_role"),
                        "support_match": True,
                        "canonical_authority_source": canonical_source,
                    }
                    best_match_len = len(prefix_norm)
    if best_match is not None:
        return best_match
    return {
        "system": "unknown",
        "boundary_role": None,
        "support_match": False,
        "canonical_authority_source": registry.get(
            "three_letter_system_boundary_guidance", {}
        ).get("canonical_authority_source"),
    }


def annotate_violation(
    violation: dict[str, Any],
    neutral_vocab: dict[str, Any],
    registry: dict[str, Any],
) -> dict[str, Any]:
    """Add boundary classification and suggested neutral terms to a violation.

    Classification is non-owning support guidance. Canonical ownership is
    referenced via canonical_authority_source on each registry entry.
    """
    annotated = dict(violation)
    classification = classify_three_letter_system(str(violation.get("path", "")), registry)
    annotated["three_letter_system"] = classification["system"]
    annotated["three_letter_system_support_match"] = classification["support_match"]
    annotated["boundary_role"] = classification.get("boundary_role")
    annotated["canonical_authority_source"] = classification.get("canonical_authority_source")

    token = str(violation.get("token", "")).strip().lower()
    replacements = neutral_vocab.get("neutral_replacements", {}) or {}
    suggestions = replacements.get(token, [])
    if suggestions:
        annotated["suggested_neutral_terms"] = list(suggestions)
    return annotated


def build_repair_suggestion(
    violation: dict[str, Any],
    neutral_vocab: dict[str, Any],
) -> dict[str, Any] | None:
    token = str(violation.get("token", "")).strip().lower()
    replacements = neutral_vocab.get("neutral_replacements", {}) or {}
    suggested_terms = replacements.get(token)
    if not suggested_terms:
        return None
    return {
        "path": violation.get("path"),
        "line": violation.get("line"),
        "forbidden_token": token,
        "suggested_terms": list(suggested_terms),
        "rationale": (
            "Non-owning support systems may verify and route gate evidence "
            "but may not claim protected vocabulary. Canonical responsibility "
            "is declared in docs/architecture/system_registry.md. Replace the "
            "forbidden token with one of the suggested neutral terms or move "
            "the surface to the canonical responsibility owner declared in "
            "the registry."
        ),
        "safe_autofix_available": False,
    }


def detect_routing_bypass(rel_path: str, repo_root: Path) -> list[dict[str, Any]]:
    """Detect routing-bypass attempts outside the routing authority owner.

    Reports a ROUTING_BYPASS_ATTEMPT violation when a non-owner file:
    - calls _route_artifact_unchecked directly
    - imports _route_artifact_unchecked
    - re-exports the unchecked symbol via __all__
    - defines a public route_artifact alias or function

    The routing authority owner (tlc_router.py) is the only file allowed to
    reference _route_artifact_unchecked. Helper / wrapper bypass patterns in
    any other path fail closed.
    """
    normalized = _normalize_path(rel_path)
    if normalized == ROUTING_AUTHORITY_OWNER:
        return []
    if normalized in ROUTING_BYPASS_GUARD_PROBES:
        return []
    full_path = repo_root / rel_path
    if not full_path.is_file() or full_path.suffix.lower() != ".py":
        return []

    try:
        text = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    findings: list[dict[str, Any]] = []
    for line_idx, raw_line in enumerate(text.splitlines(), start=1):
        # Strip comments to avoid false positives in commentary.
        line = raw_line.split("#", 1)[0]
        if not line.strip():
            continue
        for description, pattern in ROUTING_BYPASS_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "path": normalized,
                        "line": line_idx,
                        "token": "_route_artifact_unchecked"
                        if "_route_artifact_unchecked" in line
                        else "route_artifact",
                        "category": "routing_bypass",
                        "reason_code": "ROUTING_BYPASS_ATTEMPT",
                        "description": description,
                        "evidence_snippet": raw_line.strip()[:200],
                        "canonical_authority_source": ROUTING_AUTHORITY_OWNER,
                        "remediation": (
                            "External callers must use "
                            "spectrum_systems.modules.orchestration.tlc_router."
                            "route_with_gate_evidence. Routing without verified "
                            "gate evidence is prohibited."
                        ),
                    }
                )
    return findings


def run_preflight(
    *,
    repo_root: Path,
    changed_files: list[str],
    registry: dict[str, Any],
    neutral_vocab: dict[str, Any],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    routing_bypass_violations: list[dict[str, Any]] = []
    scanned_files: list[str] = []

    for rel_path in changed_files:
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        if full_path.suffix.lower() not in SCAN_SUFFIXES:
            continue

        scanned_files.append(rel_path)
        try:
            vocab_violations = find_forbidden_vocabulary(Path(rel_path), registry)
            shape_violations = detect_authority_shapes(Path(rel_path), registry)
        except (json.JSONDecodeError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
            raise ThreeLetterAuthorityPreflightError(
                f"failed to scan {rel_path}: {exc}"
            ) from exc

        for violation in list(vocab_violations) + list(shape_violations):
            annotated = annotate_violation(violation, neutral_vocab, registry)
            violations.append(annotated)
            repair = build_repair_suggestion(annotated, neutral_vocab)
            if repair is not None:
                repairs.append(repair)

        for bypass in detect_routing_bypass(rel_path, repo_root):
            routing_bypass_violations.append(bypass)
            violations.append(bypass)

    files_with_violations = sorted({str(v.get("path", "")) for v in violations})
    status = "fail" if violations else "pass"
    return {
        "artifact_type": "3ls_authority_preflight_result",
        "artifact_version": "1.0.0",
        "status": status,
        "changed_files": list(changed_files),
        "scanned_files": sorted(set(scanned_files)),
        "violations": violations,
        "suggested_repairs": repairs,
        "routing_bypass_findings": routing_bypass_violations,
        "summary": {
            "violation_count": len(violations),
            "files_with_violations": len(files_with_violations),
            "safe_autofix_available_count": sum(
                1 for r in repairs if r.get("safe_autofix_available")
            ),
            "routing_bypass_count": len(routing_bypass_violations),
        },
    }


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
        raise ThreeLetterAuthorityPreflightError(str(exc)) from exc

    registry_path = REPO_ROOT / args.registry
    if not registry_path.is_file():
        raise ThreeLetterAuthorityPreflightError(
            f"authority registry missing: {registry_path}"
        )
    registry = load_authority_registry(registry_path)

    neutral_vocab_path = REPO_ROOT / args.neutral_vocabulary
    neutral_vocab = load_neutral_vocabulary(neutral_vocab_path)

    result = run_preflight(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        registry=registry,
        neutral_vocab=neutral_vocab,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": result["status"],
                "changed_files": result["changed_files"],
                "violation_count": result["summary"]["violation_count"],
                "routing_bypass_count": result["summary"].get(
                    "routing_bypass_count", 0
                ),
                "output": str(output_path),
            },
            indent=2,
        )
    )
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
