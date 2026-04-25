#!/usr/bin/env python3
"""Authority-shape preflight for MET/dashboard artifacts and documentation.

Scans dashboard seed artifacts, metrics artifacts, and review docs for
authority-shaped vocabulary used outside canonical owner systems.

This check is broader than run_authority_leak_guard.py (which only covers
spectrum_systems/modules/). It applies authority vocabulary rules to
MET/dashboard paths that are not in the core module scope.

Usage:
    python scripts/run_authority_shape_preflight.py \\
      --base-ref main --head-ref HEAD \\
      --suggest-only \\
      --output outputs/authority_shape_preflight/authority_shape_preflight_result.json
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

from scripts.authority_leak_rules import (
    FORBIDDEN_FIELDS,
    FORBIDDEN_VALUES,
    _normalize,
    is_owner_path,
    load_authority_registry,
)

# Paths scanned by this preflight (not covered by run_authority_leak_guard.py).
DEFAULT_SCAN_PATHS: list[str] = [
    "artifacts/dashboard_seed",
    "artifacts/dashboard_metrics",
]

# Review doc glob patterns scanned in addition to DEFAULT_SCAN_PATHS.
# Only MET-prefixed review documents are checked; historical reviews that
# pre-date the authority-neutral vocabulary requirement are out of scope.
REVIEW_DOC_PATTERNS: list[str] = [
    "MET-*.md",
]

SCAN_SUFFIXES: frozenset[str] = frozenset({".json", ".md"})

# Authority-shaped artifact_type pattern (same as authority_shape_detector.py).
_ARTIFACT_AUTH_PATTERN = re.compile(
    r"(decision|certification|promotion|enforcement)", re.IGNORECASE
)

# Allowed canonical authority descriptions in documentation.
# Lines matching these patterns are considered boundary-description text,
# not authority claims, and are excluded from violation checks.
_ALLOWED_AUTHORITY_BOUNDARY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcde\s+decides?\b", re.IGNORECASE),
    re.compile(r"\bsel\s+enforces?\b", re.IGNORECASE),
    re.compile(r"\btpa\s+adjudicates?\b", re.IGNORECASE),
    re.compile(r"\bgov\s+certifies?\b", re.IGNORECASE),
    re.compile(r"\bpra\s+certifies?\b", re.IGNORECASE),
]


def _is_boundary_description(line: str) -> bool:
    """Return True if the line is explicitly describing authority boundaries."""
    return any(p.search(line) for p in _ALLOWED_AUTHORITY_BOUNDARY_PATTERNS)


def _extract_json_keys_values(
    payload: object, _depth: int = 0
) -> tuple[list[str], list[str]]:
    """Recursively collect all dict keys and string values."""
    keys: list[str] = []
    values: list[str] = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            keys.append(str(k).strip().lower())
            child_k, child_v = _extract_json_keys_values(v, _depth + 1)
            keys.extend(child_k)
            values.extend(child_v)
    elif isinstance(payload, list):
        for item in payload:
            child_k, child_v = _extract_json_keys_values(item, _depth + 1)
            keys.extend(child_k)
            values.extend(child_v)
    elif isinstance(payload, str):
        values.append(payload.strip().lower())
    return keys, values


def _scan_json(path: Path, rel_path: str) -> list[dict]:
    violations: list[dict] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [{"rule": "scan_error", "path": rel_path, "message": str(exc)}]

    if not isinstance(payload, dict):
        return violations

    # Check artifact_type for authority-shaped names.
    artifact_type = str(payload.get("artifact_type", "")).strip().lower()
    if artifact_type and _ARTIFACT_AUTH_PATTERN.search(artifact_type):
        violations.append(
            {
                "rule": "authority_shape_artifact_type",
                "path": rel_path,
                "artifact_type": artifact_type,
                "message": (
                    f"authority-shaped artifact_type '{artifact_type}' "
                    "outside canonical owners — use signal/observation vocabulary"
                ),
            }
        )

    # Check all keys and string values recursively.
    keys, values = _extract_json_keys_values(payload)

    for field in keys:
        if field in FORBIDDEN_FIELDS:
            violations.append(
                {
                    "rule": "forbidden_field",
                    "path": rel_path,
                    "token": field,
                    "message": (
                        f"forbidden authority field '{field}' outside canonical owners"
                    ),
                }
            )

    for value in values:
        if value in FORBIDDEN_VALUES:
            violations.append(
                {
                    "rule": "forbidden_value",
                    "path": rel_path,
                    "token": value,
                    "message": (
                        f"forbidden authority value '{value}' outside canonical owners"
                    ),
                }
            )

    return violations


def _scan_md(path: Path, rel_path: str) -> list[dict]:
    violations: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [{"rule": "scan_error", "path": rel_path, "message": str(exc)}]

    field_pattern = re.compile(
        r"\b(decision|enforcement_action|certification_status|certified|promoted|promotion_ready)\b",
        re.IGNORECASE,
    )
    value_pattern = re.compile(
        r"\b(allow|block|freeze|promote)\b",
        re.IGNORECASE,
    )

    for idx, line in enumerate(text.splitlines(), start=1):
        if _is_boundary_description(line):
            continue

        for match in field_pattern.finditer(line):
            violations.append(
                {
                    "rule": "forbidden_field",
                    "path": rel_path,
                    "line": idx,
                    "token": match.group(1).lower(),
                    "message": (
                        f"forbidden authority field '{match.group(1)}' "
                        "in documentation outside canonical owners"
                    ),
                    "context": line.strip()[:120],
                }
            )
        for match in value_pattern.finditer(line):
            violations.append(
                {
                    "rule": "forbidden_value",
                    "path": rel_path,
                    "line": idx,
                    "token": match.group(1).lower(),
                    "message": (
                        f"forbidden authority value '{match.group(1)}' "
                        "in documentation outside canonical owners"
                    ),
                    "context": line.strip()[:120],
                }
            )

    return violations


def _collect_candidates(scan_paths: list[str]) -> list[Path]:
    candidates: list[Path] = []
    # Artifact directories: scan all JSON files.
    for scan_path_str in scan_paths:
        scan_path = REPO_ROOT / scan_path_str
        if not scan_path.exists():
            continue
        if scan_path.is_file():
            if scan_path.suffix.lower() in SCAN_SUFFIXES:
                candidates.append(scan_path)
        else:
            candidates.extend(
                sorted(
                    p
                    for p in scan_path.rglob("*")
                    if p.is_file() and p.suffix.lower() in SCAN_SUFFIXES
                )
            )
    # Review docs: only MET-prefixed files to avoid flagging historical reviews
    # that pre-date the authority-neutral vocabulary requirement.
    reviews_dir = REPO_ROOT / "docs" / "reviews"
    if reviews_dir.is_dir():
        for pattern in REVIEW_DOC_PATTERNS:
            candidates.extend(sorted(reviews_dir.glob(pattern)))
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Authority-shape preflight for MET/dashboard artifacts"
    )
    parser.add_argument(
        "--registry",
        default="contracts/governance/authority_registry.json",
        help="Authority registry for owner path exclusions",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_shape_preflight_result.json",
        help="Output artifact path",
    )
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Additional paths to scan (in addition to defaults)",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git base ref (accepted for CLI compatibility; not used for file selection)",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git head ref (accepted for CLI compatibility; not used for file selection)",
    )
    parser.add_argument(
        "--suggest-only",
        action="store_true",
        help="Print violations but always exit 0 (non-blocking mode)",
    )
    args = parser.parse_args()

    registry_path = REPO_ROOT / args.registry
    if not registry_path.is_file():
        print(
            f"ERROR: authority registry missing: {registry_path}", file=sys.stderr
        )
        return 1
    registry = load_authority_registry(registry_path)

    scan_paths = DEFAULT_SCAN_PATHS + list(args.scan_path)
    candidates = _collect_candidates(scan_paths)

    violations: list[dict] = []
    scanned: list[str] = []

    for full_path in candidates:
        rel_path = _normalize(str(full_path))
        scanned.append(rel_path)

        if is_owner_path(rel_path, registry):
            continue  # canonical owners may use authority vocabulary

        suffix = full_path.suffix.lower()
        if suffix == ".json":
            violations.extend(_scan_json(full_path, rel_path))
        elif suffix == ".md":
            violations.extend(_scan_md(full_path, rel_path))

    status = "pass" if not violations else "fail"
    result: dict = {
        "status": status,
        "violation_count": len(violations),
        "scanned_file_count": len(scanned),
        "scanned_files": scanned,
        "violations": violations,
    }

    out_path = REPO_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if violations:
        for v in violations[:40]:
            tok = v.get("token", v.get("artifact_type", "?"))
            loc = f":{v['line']}" if "line" in v else ""
            print(f"  VIOLATION [{v['rule']}] {v['path']}{loc}  token={tok}")
        if len(violations) > 40:
            print(f"  ... and {len(violations) - 40} more")
        print(f"\nauthority shape preflight FAILED — {len(violations)} violation(s)")
        print(f"result written to: {out_path}")
    else:
        print(f"authority shape preflight PASSED — 0 violations across {len(scanned)} files")
        print(f"result written to: {out_path}")

    return 0 if (args.suggest_only or not violations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
