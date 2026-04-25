"""Authority drift linter.

Detects SHADOW_OWNERSHIP_OVERLAP by scanning text for ``<SYSTEM> <verb>``
phrases and cross-checking attribution against the canonical authority
ownership matrix at ``contracts/authority/authority_ownership_matrix.yaml``.

This module is fail-closed: a missing or malformed matrix raises
``AuthorityLinterError``. Findings are deterministic — every (system, verb,
line) combination yields exactly one finding with a stable suggested_fix.

The linter is linguistic-only. It does not reproduce decision, adjudication,
enforcement, or certification logic. It records what the matrix already says
and surfaces phrases that contradict it. CDE/TPA/GOV/SEL ownership boundaries
are unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MATRIX_PATH = REPO_ROOT / "contracts" / "authority" / "authority_ownership_matrix.yaml"

REASON_CODE = "SHADOW_OWNERSHIP_OVERLAP"

# Verbs that imply authority. The linter only flags drift when these verbs
# appear after a registered system token. Other verbs are ignored even when
# attributed to a system, because the matrix does not yet govern them.
_AUTHORITY_VERBS: tuple[str, ...] = (
    "decides",
    "determines",
    "approves",
    "adjudicates",
    "evaluates",
    "enforces",
    "executes",
    "promotes",
    "certifies",
    "gates",
    "packages",
    "routes",
    "annotates",
    "records",
    "governs",
    "defines",
    "provides",
    "supplies",
    "emits",
)

_VERB_GROUP = "|".join(_AUTHORITY_VERBS)
# Match a 3-letter system token (uppercase) followed by an optional adverb and
# then an authority verb. Restricting to uppercase tokens avoids false positives
# on common English words.
_SYSTEM_VERB_PATTERN = re.compile(
    rf"\b(?P<system>[A-Z]{{3}})\b(?P<gap>\s+(?:always\s+|never\s+|only\s+)?)(?P<verb>{_VERB_GROUP})\b"
)


class AuthorityLinterError(ValueError):
    """Raised when the authority linter cannot complete deterministically."""


def load_authority_matrix(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical authority ownership matrix.

    Fails closed on missing file, parse error, or schema-shape error.
    """
    matrix_path = Path(path) if path is not None else DEFAULT_MATRIX_PATH
    if not matrix_path.is_file():
        raise AuthorityLinterError(f"authority ownership matrix missing: {matrix_path}")
    try:
        payload = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise AuthorityLinterError(f"authority ownership matrix is malformed: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityLinterError("authority ownership matrix must be a YAML mapping")
    if not isinstance(payload.get("systems"), dict) or not payload["systems"]:
        raise AuthorityLinterError("authority ownership matrix missing 'systems' mapping")
    if not isinstance(payload.get("canonical_verb_owners"), dict):
        raise AuthorityLinterError("authority ownership matrix missing 'canonical_verb_owners'")
    return payload


def _normalize_verb(verb: str) -> str:
    return verb.strip().lower()


def _system_record(matrix: dict[str, Any], system: str) -> dict[str, Any] | None:
    systems = matrix.get("systems", {})
    record = systems.get(system)
    return record if isinstance(record, dict) else None


def _suggested_fix(system: str, verb: str, canonical_owner: str | None) -> str:
    """Build a deterministic canonical-owner phrasing.

    Examples:
        suggested_fix("TLC", "enforces", "SEL")
            -> "TLC routes; SEL enforces"
        suggested_fix("GOV", "decides", "CDE")
            -> "GOV certifies; CDE decides"
    """
    if not canonical_owner or canonical_owner == system:
        return f"remove forbidden attribution '{system} {verb}' (system does not own this verb)"
    primary_verb_map = {
        "TLC": "routes",
        "TPA": "adjudicates",
        "CDE": "decides",
        "GOV": "certifies",
        "PRA": "provides",
        "POL": "governs",
        "SEL": "enforces",
        "PQX": "executes",
    }
    fallback_verb = primary_verb_map.get(system, "operates")
    return f"{system} {fallback_verb}; {canonical_owner} {verb}"


def detect_authority_drift(
    text: str,
    *,
    matrix: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return SHADOW_OWNERSHIP_OVERLAP findings for ``text``.

    Each finding has the shape::

        {
            "reason_code": "SHADOW_OWNERSHIP_OVERLAP",
            "system": "TLC",
            "verb": "enforces",
            "canonical_owner": "SEL",
            "line": 12,
            "match": "TLC enforces",
            "suggested_fix": "TLC routes; SEL enforces",
        }

    Only verbs registered in the matrix's ``forbidden_verbs`` list for the
    system trigger a finding; allowed verbs are silently ignored. Systems that
    are not registered in the matrix (e.g. SEL, PQX, AEX) are silently ignored
    even when paired with authority verbs, because the matrix does not yet
    govern them.
    """
    if matrix is None:
        matrix = load_authority_matrix()

    findings: list[dict[str, Any]] = []
    for line_index, line in enumerate(text.splitlines(), start=1):
        for match in _SYSTEM_VERB_PATTERN.finditer(line):
            system = match.group("system")
            verb = _normalize_verb(match.group("verb"))
            record = _system_record(matrix, system)
            if record is None:
                continue
            forbidden = {_normalize_verb(v) for v in record.get("forbidden_verbs", [])}
            if verb not in forbidden:
                continue
            canonical_owner = matrix.get("canonical_verb_owners", {}).get(verb)
            findings.append(
                {
                    "reason_code": REASON_CODE,
                    "system": system,
                    "verb": verb,
                    "canonical_owner": canonical_owner,
                    "line": line_index,
                    "match": match.group(0),
                    "suggested_fix": _suggested_fix(system, verb, canonical_owner),
                }
            )
    return findings


def apply_authority_repair(text: str, findings: list[dict[str, Any]]) -> str:
    """Rewrite ``text`` so every drift finding becomes a canonical pattern.

    The repair is deterministic and idempotent: applying it twice yields the
    same result. Only spans referenced in ``findings`` are modified; surrounding
    text is left byte-for-byte identical.
    """
    if not findings:
        return text

    # Group findings by (system, verb) and replace each occurrence in line.
    # Because suggested_fix is deterministic for each pair, replacement is
    # safe to perform in a single pass per pair.
    replacements: dict[tuple[str, str], str] = {}
    for finding in findings:
        key = (str(finding["system"]), str(finding["verb"]))
        replacements[key] = str(finding["suggested_fix"])

    repaired = text
    for (system, verb), fix in replacements.items():
        # Replace `SYSTEM verb` (allowing optional adverb) regardless of line.
        pattern = re.compile(
            rf"\b{re.escape(system)}\b(?P<gap>\s+(?:always\s+|never\s+|only\s+)?){re.escape(verb)}\b"
        )
        repaired = pattern.sub(fix, repaired)
    return repaired


def is_clean(text: str, *, matrix: dict[str, Any] | None = None) -> bool:
    """True iff ``text`` contains no SHADOW_OWNERSHIP_OVERLAP drift."""
    return not detect_authority_drift(text, matrix=matrix)


def lint_file(path: Path, *, matrix: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run :func:`detect_authority_drift` against a file path.

    Findings are annotated with the relative file path so callers can compose
    multi-file reports without losing locality.
    """
    rel = str(path).replace("\\", "/")
    repo_prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel.startswith(repo_prefix):
        rel = rel[len(repo_prefix) :]

    if matrix is None:
        matrix = load_authority_matrix()

    excluded = tuple(matrix.get("scope", {}).get("excluded_path_prefixes", []) or [])
    if any(rel == item or rel.startswith(item.rstrip("/") + "/") for item in excluded):
        return []

    suffixes = tuple(matrix.get("scope", {}).get("default_scope_suffixes", []) or [])
    if suffixes and Path(rel).suffix.lower() not in suffixes:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise AuthorityLinterError(f"failed to read {rel}: {exc}") from exc

    findings = detect_authority_drift(text, matrix=matrix)
    for finding in findings:
        finding["path"] = rel
    return findings
