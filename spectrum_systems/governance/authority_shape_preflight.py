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
class RegistryRules:
    """Section-aware rules applied only to canonical-registry paths.

    The registry document is the canonical authority-ownership reference, so
    cluster terms appearing inside any registry-tracked ``### CODE`` section
    legitimately define that system's authority surface. The exception is
    ``non_owning_support_systems`` (e.g. HOP), whose sections continue to
    apply the strict rules: cluster terms are flagged unless they appear in
    a boundary-disclaim field (``must_not_do:``) or in cross-cutting prose
    outside any ``### CODE`` section. A claim verb on the same line as a
    cluster term inside a non-owning-support section flags regardless of
    field, since it implies ownership. A negation token immediately
    associated with the claim verb (``never decides``, ``does not decide``)
    is treated as an explicit disclaim and allowed.
    """

    section_header_pattern: str
    h2_header_pattern: str
    field_bullet_pattern: str
    boundary_disclaim_field: str
    claim_position_fields: tuple[str, ...]
    claim_verbs: tuple[str, ...]
    boundary_clarification_markers: tuple[str, ...]
    non_owning_support_systems: frozenset[str]


@dataclass(frozen=True)
class VocabularyModel:
    scope_prefixes: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    canonical_registry_paths: tuple[str, ...]
    guard_path_prefixes: tuple[str, ...]
    clusters: tuple[ClusterSpec, ...]
    safety_suffixes: tuple[str, ...]
    safe_rename_pairs: tuple[tuple[str, str], ...]
    rename_include_suffixes: tuple[str, ...]
    rename_exclude_prefixes: tuple[str, ...]
    registry_rules: RegistryRules | None


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

    registry_rules_payload = payload.get("registry_rules")
    registry_rules: RegistryRules | None = None
    if isinstance(registry_rules_payload, dict):
        registry_rules = RegistryRules(
            section_header_pattern=str(
                registry_rules_payload.get("section_header_pattern")
                or r"^###[ \t]+([A-Z][A-Z0-9]{1,5})\b"
            ),
            h2_header_pattern=str(
                registry_rules_payload.get("h2_header_pattern") or r"^##[ \t]+\S"
            ),
            field_bullet_pattern=str(
                registry_rules_payload.get("field_bullet_pattern")
                or r"^[ \t]*-[ \t]+\*\*([A-Za-z][A-Za-z0-9 _]*?)\s*:\*\*"
            ),
            boundary_disclaim_field=str(
                registry_rules_payload.get("boundary_disclaim_field") or "must_not_do"
            ).lower(),
            claim_position_fields=tuple(
                str(f).lower()
                for f in registry_rules_payload.get("claim_position_fields", [])
            ),
            claim_verbs=tuple(
                str(v).lower() for v in registry_rules_payload.get("claim_verbs", [])
            ),
            boundary_clarification_markers=tuple(
                str(v).lower()
                for v in registry_rules_payload.get(
                    "boundary_clarification_markers", []
                )
            ),
            non_owning_support_systems=frozenset(
                str(s).strip().upper()
                for s in registry_rules_payload.get(
                    "non_owning_support_systems", []
                )
                if str(s).strip()
            ),
        )

    return VocabularyModel(
        scope_prefixes=tuple(str(p) for p in scope.get("default_scope_prefixes", [])),
        excluded_prefixes=tuple(str(p) for p in scope.get("excluded_path_prefixes", [])),
        canonical_registry_paths=tuple(
            _normalize_path(str(p)) for p in scope.get("canonical_registry_paths", [])
        ),
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
        registry_rules=registry_rules,
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


def is_canonical_registry_path(rel_path: str, vocab: VocabularyModel) -> bool:
    norm = _normalize_path(rel_path)
    return any(norm == _normalize_path(p) for p in vocab.canonical_registry_paths)


@dataclass(frozen=True)
class RegistryLineContext:
    """Per-line context for a canonical-registry file.

    ``section_code`` is the most recent ``### CODE`` header above this line,
    or ``None`` if the line is in the preamble or in a ``## ...`` block that
    has not yet introduced a ``### CODE`` subsection. ``current_field`` is
    the most recent ``- **field:**`` bullet within the current section, or
    ``None``. The field name is lowercased.
    """

    section_code: str | None
    current_field: str | None


def _compute_registry_contexts(
    lines: list[str], rules: RegistryRules
) -> list[RegistryLineContext]:
    section_re = re.compile(rules.section_header_pattern)
    h2_re = re.compile(rules.h2_header_pattern)
    field_re = re.compile(rules.field_bullet_pattern)

    contexts: list[RegistryLineContext] = []
    section_code: str | None = None
    current_field: str | None = None
    for line in lines:
        if h2_re.match(line) and not section_re.match(line):
            section_code = None
            current_field = None
        else:
            sec_match = section_re.match(line)
            if sec_match:
                section_code = sec_match.group(1)
                current_field = None
            else:
                field_match = field_re.match(line)
                if field_match:
                    field_name = field_match.group(1).strip().lower().replace(" ", "_")
                    current_field = field_name
        contexts.append(
            RegistryLineContext(section_code=section_code, current_field=current_field)
        )
    return contexts


_NEGATION_PATTERN = re.compile(
    r"\b(?:never|not|no|cannot|can\s*not|must\s*not|shall\s*not|should\s*not|"
    r"does\s*not|do\s*not|did\s*not|won\s*[' ]\s*t|doesn\s*[' ]\s*t|"
    r"don\s*[' ]\s*t|isn\s*[' ]\s*t|aren\s*[' ]\s*t|external\s+to)\b"
)


def _line_carries_claim_verb(line: str, claim_verbs: Iterable[str]) -> bool:
    """Return True if ``line`` contains a non-negated ownership-claim verb.

    The check is whole-word, case-insensitive, and matches whether the verb
    is written with underscores (``rolls_back``) or as a separated phrase
    (``rolls back``). It deliberately ignores incidental substrings.

    A line that contains a negation token (``never``, ``does not``,
    ``must not``, ``external to``, etc.) is treated as a disclaim and
    returns ``False`` even if it also contains a claim verb. The registry
    routinely uses sentences like ``HOP never decides promotion`` or
    ``module X is external to enforcement`` to spell out a non-ownership
    boundary; flagging those would force the document to lose precision
    without catching any new ownership claim.
    """
    if not line.strip():
        return False
    lowered = line.lower()
    if _NEGATION_PATTERN.search(lowered):
        return False
    for verb in claim_verbs:
        verb_l = verb.strip().lower()
        if not verb_l:
            continue
        spaced = verb_l.replace("_", " ")
        # Underscore form (whole word).
        if re.search(r"\b" + re.escape(verb_l) + r"\b", lowered):
            return True
        # Spaced form when the verb is multi-token.
        if spaced != verb_l and re.search(r"\b" + re.escape(spaced) + r"\b", lowered):
            return True
    return False


def filter_registry_violations(
    *,
    violations: list[Violation],
    lines: list[str],
    vocab: VocabularyModel,
) -> list[Violation]:
    """Drop violations whose context legitimately defines canonical ownership.

    Rules (applied only when the file is in
    ``vocab.canonical_registry_paths``):

    1. **Cross-cutting prose** — if the violation is in the preamble or in
       a ``## ...`` block that has no enclosing ``### CODE`` subsection,
       allow it. Such lines describe the registry's cross-cutting
       structure and are not an ownership claim by any single system.
    2. **Per-cluster canonical owner** — if the violation is inside a
       ``### CODE`` section where ``CODE`` is in the cluster's
       ``canonical_owners`` list, allow it. The owner is permitted to use
       its own authority terms.
    3. **Boundary disclaim** — if the violation is inside a ``### CODE``
       section under a ``- **must_not_do:**`` field and the line carries
       no non-negated claim verb, allow it. The field exists precisely
       to disclaim authority and must be able to name the disclaimed
       cluster.
    4. **Registry-tracked canonical owner definition** — if the violation is
       inside a ``### CODE`` section where ``CODE`` is **not** in
       ``non_owning_support_systems``, allow it. The registry is the
       canonical owner-definition surface; authority-shaped terms in those
       sections define ownership/boundary relationships and are legitimate.
    5. **Non-owning support section** — if the violation is inside a
       ``### CODE`` section where ``CODE`` is in
       ``non_owning_support_systems`` (e.g. HOP), keep it when the field
       is a claim-position field (``owns:``, ``produces:``, ``role:``,
       ``Canonical Artifacts Owned:``, ``Primary Code Paths:``) or when
       the line carries a non-negated claim verb. Also allow boundary
       clarification lines in descriptive fields (for example, delegation
       text naming downstream canonical owners).
    """
    if vocab.registry_rules is None:
        return violations

    rules = vocab.registry_rules
    contexts = _compute_registry_contexts(lines, rules)
    canonical_owners_by_cluster = {
        c.name: {o.upper() for o in c.canonical_owners} for c in vocab.clusters
    }
    claim_position = set(rules.claim_position_fields)
    boundary_markers = tuple(
        marker for marker in rules.boundary_clarification_markers if marker
    )

    out: list[Violation] = []
    for v in violations:
        if v.line < 1 or v.line > len(contexts):
            out.append(v)
            continue
        ctx = contexts[v.line - 1]
        if ctx.section_code is None:
            # Rule 1: cross-cutting prose, not an ownership claim.
            continue
        owners = canonical_owners_by_cluster.get(v.cluster, set())
        if ctx.section_code in owners:
            # Rule 2: per-cluster canonical owner using its own term.
            continue
        line_text = lines[v.line - 1] if v.line - 1 < len(lines) else ""
        carries_claim_verb = _line_carries_claim_verb(line_text, rules.claim_verbs)
        if ctx.current_field == rules.boundary_disclaim_field and not carries_claim_verb:
            # Rule 3: explicit boundary disclaim, no claim verb present.
            continue
        is_non_owning_support = ctx.section_code in rules.non_owning_support_systems
        if not is_non_owning_support:
            # Rule 4: canonical owner definition section in the registry.
            continue
        if ctx.current_field in claim_position or carries_claim_verb:
            # Rule 5a: non-owning support section claiming authority via
            # claim-position field or claim verb.
            out.append(v)
            continue
        lowered_line = line_text.lower()
        if any(marker in lowered_line for marker in boundary_markers):
            # Rule 5b: non-owning boundary clarification inside descriptive
            # fields is allowed.
            continue
        # Rule 5c: keep violation in non-owning support descriptive fields
        # unless the line explicitly clarifies non-ownership boundaries.
        out.append(v)
        continue
    return out


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
        file_violations = scan_file(full_path, rel_path, vocab)
        if is_canonical_registry_path(rel_path, vocab) and vocab.registry_rules is not None:
            try:
                file_text = full_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                file_text = ""
            file_violations = filter_registry_violations(
                violations=file_violations,
                lines=file_text.splitlines(),
                vocab=vocab,
            )
        violations.extend(file_violations)

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
    "RegistryRules",
    "RegistryLineContext",
    "VocabularyModel",
    "Violation",
    "Rename",
    "PreflightResult",
    "load_vocabulary",
    "scan_file",
    "is_guard_path",
    "is_owner_path",
    "is_canonical_registry_path",
    "filter_registry_violations",
    "apply_safe_renames",
    "evaluate_preflight",
]
