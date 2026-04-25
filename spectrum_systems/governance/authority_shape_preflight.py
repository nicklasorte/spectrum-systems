"""Authority-shape preflight scanner (AGS-001).

Static, non-owning scanner that detects authority-shaped terminology used by
non-owner systems and reports diagnostics to canonical owners. It does not
own runtime behavior, gating, or enforcement. Canonical ownership is
unchanged: admission/runtime stays with AEX, closure with CDE, enforcement
with SEL.

Driven by ``contracts/governance/authority_shape_vocabulary.json``. Designed
to sit upstream of the system-registry guard and authority-leak guard so the
same diagnostics they would later report are surfaced earlier with explicit
suggestions and (optionally) safe renames.

The scanner returns a failing diagnostic status (non-zero exit) when leaks
are detected. ``suggest-only`` reports diagnostics; ``apply-safe-renames``
applies unambiguous, owner-safe renames and re-scans. Guard scripts,
canonical owner files, and the vocabulary itself are protected from
auto-remediation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]


class AuthorityShapePreflightError(ValueError):
    """Raised when the preflight cannot complete deterministically."""


@dataclass(frozen=True)
class ClusterSpec:
    name: str
    terms: tuple[str, ...]
    canonical_owners: tuple[str, ...]
    owner_path_prefixes: tuple[str, ...]
    advisory_replacements: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class VocabularyModel:
    scope_prefixes: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    guard_path_prefixes: tuple[str, ...]
    clusters: tuple[ClusterSpec, ...]
    safety_suffixes: tuple[str, ...]
    safe_rename_pairs: tuple[tuple[str, str], ...]
    rename_include_suffixes: tuple[str, ...]
    rename_exclude_prefixes: tuple[str, ...]


@dataclass
class Violation:
    file: str
    line: int
    symbol: str
    cluster: str
    canonical_owners: tuple[str, ...]
    suggested_replacements: tuple[str, ...]
    rationale: str
    rule: str = "authority_shape_outside_owner"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "file": self.file,
            "line": self.line,
            "symbol": self.symbol,
            "cluster": self.cluster,
            "canonical_owners": list(self.canonical_owners),
            "suggested_replacements": list(self.suggested_replacements),
            "rationale": self.rationale,
        }


@dataclass
class Rename:
    file: str
    old: str
    new: str
    occurrences: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "from": self.old,
            "to": self.new,
            "occurrences": self.occurrences,
        }


@dataclass
class PreflightResult:
    status: str
    mode: str
    scanned_files: list[str]
    skipped_files: list[str]
    violations: list[Violation] = field(default_factory=list)
    suggestions: list[dict[str, Any]] = field(default_factory=list)
    applied_renames: list[Rename] = field(default_factory=list)
    refused_renames: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "authority_shape_preflight_result",
            "status": self.status,
            "mode": self.mode,
            "scanned_files": sorted(set(self.scanned_files)),
            "skipped_files": sorted(set(self.skipped_files)),
            "violations": [v.to_dict() for v in self.violations],
            "suggestions": self.suggestions,
            "applied_renames": [r.to_dict() for r in self.applied_renames],
            "refused_renames": self.refused_renames,
            "summary": {
                "violation_count": len(self.violations),
                "applied_rename_count": len(self.applied_renames),
                "refused_rename_count": len(self.refused_renames),
            },
        }


def load_vocabulary(path: Path) -> VocabularyModel:
    if not path.is_file():
        raise AuthorityShapePreflightError(f"vocabulary file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthorityShapePreflightError(f"vocabulary JSON invalid: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityShapePreflightError("vocabulary must be a JSON object")

    scope = payload.get("scope") or {}
    clusters_payload = payload.get("clusters") or {}
    if not isinstance(clusters_payload, dict) or not clusters_payload:
        raise AuthorityShapePreflightError("vocabulary missing clusters")

    clusters: list[ClusterSpec] = []
    for name, body in clusters_payload.items():
        if not isinstance(body, dict):
            raise AuthorityShapePreflightError(f"cluster '{name}' must be an object")
        terms = tuple(str(t).strip().lower() for t in body.get("terms", []) if str(t).strip())
        if not terms:
            raise AuthorityShapePreflightError(f"cluster '{name}' missing terms")
        clusters.append(
            ClusterSpec(
                name=str(name),
                terms=terms,
                canonical_owners=tuple(str(o) for o in body.get("canonical_owners", [])),
                owner_path_prefixes=tuple(str(p) for p in body.get("owner_path_prefixes", [])),
                advisory_replacements=tuple(str(r) for r in body.get("advisory_replacements", [])),
                rationale=str(body.get("rationale") or ""),
            )
        )

    safe_pairs_payload = payload.get("safe_rename_pairs") or []
    safe_pairs: list[tuple[str, str]] = []
    for entry in safe_pairs_payload:
        if not isinstance(entry, dict):
            continue
        old = str(entry.get("from") or "").strip()
        new = str(entry.get("to") or "").strip()
        if old and new and old != new:
            safe_pairs.append((old, new))

    remediation = payload.get("remediation_policy") or {}
    rename_targets = remediation.get("rename_targets") or {}

    return VocabularyModel(
        scope_prefixes=tuple(str(p) for p in scope.get("default_scope_prefixes", [])),
        excluded_prefixes=tuple(str(p) for p in scope.get("excluded_path_prefixes", [])),
        guard_path_prefixes=tuple(str(p) for p in scope.get("guard_path_prefixes", [])),
        clusters=tuple(clusters),
        safety_suffixes=tuple(str(s).lower() for s in payload.get("safety_suffixes", [])),
        safe_rename_pairs=tuple(safe_pairs),
        rename_include_suffixes=tuple(
            str(s) for s in rename_targets.get("include_suffixes", [".py", ".json", ".md"])
        ),
        rename_exclude_prefixes=tuple(
            str(p) for p in rename_targets.get("exclude_path_prefixes", [])
        ),
    )


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _path_matches_prefix(rel_path: str, prefix: str) -> bool:
    norm = _normalize_path(prefix)
    if not norm:
        return False
    if norm.endswith("/"):
        return rel_path.startswith(norm)
    return rel_path == norm or rel_path.startswith(norm + "/")


def _in_scope(rel_path: str, vocab: VocabularyModel) -> bool:
    if vocab.scope_prefixes and not any(
        _path_matches_prefix(rel_path, p) for p in vocab.scope_prefixes
    ):
        return False
    if any(_path_matches_prefix(rel_path, p) for p in vocab.excluded_prefixes):
        return False
    return True


def is_guard_path(rel_path: str, vocab: VocabularyModel) -> bool:
    return any(_path_matches_prefix(rel_path, p) for p in vocab.guard_path_prefixes)


def is_owner_path(rel_path: str, cluster: ClusterSpec) -> bool:
    return any(_path_matches_prefix(rel_path, p) for p in cluster.owner_path_prefixes)


_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _identifier_subtokens(identifier: str) -> set[str]:
    """Return lowercase subtokens of an identifier split by underscores."""
    return {token for token in identifier.lower().split("_") if token}


def _identifier_matches_term(identifier: str, term: str) -> bool:
    """Match a term against an identifier.

    Multi-token terms (containing ``_``) match as a contiguous substring on the
    underscore-token boundary. Single-token terms match any underscore-separated
    subtoken. This catches ``promotion_decision`` for the term ``decision`` and
    for the term ``promotion`` while ignoring incidental substrings like
    ``promoter`` or ``decisionless``.
    """
    lowered_id = identifier.lower()
    lowered_term = term.lower()
    if not lowered_term:
        return False
    if "_" in lowered_term:
        tokens = lowered_id.split("_")
        term_tokens = lowered_term.split("_")
        if not term_tokens:
            return False
        for start in range(0, len(tokens) - len(term_tokens) + 1):
            if tokens[start : start + len(term_tokens)] == term_tokens:
                return True
        return False
    return lowered_term in _identifier_subtokens(lowered_id)


def scan_file(path: Path, rel_path: str, vocab: VocabularyModel) -> list[Violation]:
    """Scan a single file and return violations.

    A file produces violations when, for any cluster it is *not* a canonical
    owner of, an authority-shaped term appears as a subtoken of any identifier
    on a line. Identifiers are detected language-agnostically so the same scan
    works for ``.py``, ``.json``, ``.md``, ``.yml``, etc.
    """
    if not path.is_file():
        return []
    if not _in_scope(rel_path, vocab):
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    violations: list[Violation] = []
    lines = text.splitlines()
    safety_set = set(vocab.safety_suffixes)
    for idx, line in enumerate(lines, start=1):
        for ident_match in _IDENTIFIER_PATTERN.finditer(line):
            identifier = ident_match.group(0)
            subtokens = _identifier_subtokens(identifier)
            if subtokens & safety_set:
                # An advisory/support framing is present in the identifier — the
                # non-owner has explicitly disambiguated authority shape.
                continue
            for cluster in vocab.clusters:
                if is_owner_path(rel_path, cluster):
                    continue
                for term in cluster.terms:
                    if _identifier_matches_term(identifier, term):
                        violations.append(
                            Violation(
                                file=rel_path,
                                line=idx,
                                symbol=identifier,
                                cluster=cluster.name,
                                canonical_owners=cluster.canonical_owners,
                                suggested_replacements=cluster.advisory_replacements,
                                rationale=cluster.rationale,
                            )
                        )
                        break
    return violations


def _can_apply_rename(rel_path: str, vocab: VocabularyModel) -> tuple[bool, str | None]:
    if any(is_owner_path(rel_path, c) for c in vocab.clusters):
        return False, "canonical_owner_path"
    if is_guard_path(rel_path, vocab):
        return False, "guard_path"
    if any(_path_matches_prefix(rel_path, p) for p in vocab.rename_exclude_prefixes):
        return False, "rename_excluded_path"
    if vocab.rename_include_suffixes and not rel_path.endswith(tuple(vocab.rename_include_suffixes)):
        return False, "unsupported_suffix"
    return True, None


def apply_safe_renames(
    *,
    repo_root: Path,
    rel_path: str,
    vocab: VocabularyModel,
) -> tuple[Rename | None, str | None]:
    """Apply unambiguous safe renames to ``rel_path`` if it is rename-eligible.

    Returns the rename record (with occurrence count) or a reason for refusal.
    Only literal text replacements from the safe-rename map are applied — never
    structural code changes, never guard files, never canonical-owner files.
    """
    eligible, reason = _can_apply_rename(rel_path, vocab)
    if not eligible:
        return None, reason

    full_path = repo_root / rel_path
    if not full_path.is_file():
        return None, "missing_file"
    try:
        original = full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None, "unreadable"

    updated = original
    total = 0
    applied_old: str | None = None
    applied_new: str | None = None
    for old, new in vocab.safe_rename_pairs:
        pattern = re.compile(r"\b" + re.escape(old) + r"\b")
        count = len(pattern.findall(updated))
        if count == 0:
            continue
        updated = pattern.sub(new, updated)
        total += count
        applied_old = applied_old or old
        applied_new = applied_new or new

    if total == 0:
        return None, "no_safe_pair_match"

    full_path.write_text(updated, encoding="utf-8")
    return Rename(file=rel_path, old=applied_old or "", new=applied_new or "", occurrences=total), None


def evaluate_preflight(
    *,
    repo_root: Path,
    changed_files: list[str],
    vocab: VocabularyModel,
    mode: str = "suggest-only",
) -> PreflightResult:
    if mode not in {"suggest-only", "apply-safe-renames"}:
        raise AuthorityShapePreflightError(f"unsupported mode: {mode}")

    scanned: list[str] = []
    skipped: list[str] = []
    applied: list[Rename] = []
    refused: list[dict[str, Any]] = []

    candidate_paths = sorted({_normalize_path(p) for p in changed_files if p})

    if mode == "apply-safe-renames":
        for rel_path in candidate_paths:
            if not _in_scope(rel_path, vocab):
                continue
            rename, reason = apply_safe_renames(
                repo_root=repo_root, rel_path=rel_path, vocab=vocab
            )
            if rename is not None:
                applied.append(rename)
            elif reason in {"guard_path", "canonical_owner_path", "rename_excluded_path"}:
                refused.append({"file": rel_path, "reason": reason})

    violations: list[Violation] = []
    for rel_path in candidate_paths:
        full_path = repo_root / rel_path
        if not full_path.is_file():
            skipped.append(rel_path)
            continue
        if not _in_scope(rel_path, vocab):
            skipped.append(rel_path)
            continue
        if is_guard_path(rel_path, vocab):
            scanned.append(rel_path)
            continue
        scanned.append(rel_path)
        violations.extend(scan_file(full_path, rel_path, vocab))

    suggestions = [
        {
            "file": v.file,
            "line": v.line,
            "symbol": v.symbol,
            "cluster": v.cluster,
            "canonical_owner": v.canonical_owners[0] if v.canonical_owners else None,
            "suggested_replacement": (
                v.suggested_replacements[0] if v.suggested_replacements else None
            ),
            "all_replacements": list(v.suggested_replacements),
        }
        for v in violations
    ]

    status = "fail" if violations else "pass"
    return PreflightResult(
        status=status,
        mode=mode,
        scanned_files=scanned,
        skipped_files=skipped,
        violations=violations,
        suggestions=suggestions,
        applied_renames=applied,
        refused_renames=refused,
    )


__all__ = [
    "AuthorityShapePreflightError",
    "ClusterSpec",
    "VocabularyModel",
    "Violation",
    "Rename",
    "PreflightResult",
    "load_vocabulary",
    "scan_file",
    "is_guard_path",
    "is_owner_path",
    "apply_safe_renames",
    "evaluate_preflight",
]
