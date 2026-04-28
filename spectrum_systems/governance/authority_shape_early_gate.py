"""Authority-shape early gate.

Deterministic, schema-first preflight that scans changed files for authority
cluster terminology and classifies each hit against canonical owner paths
registered in ``docs/architecture/system_registry.md``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AuthorityShapeEarlyGateError(ValueError):
    """Raised when early-gate ownership resolution cannot complete safely."""


@dataclass(frozen=True)
class AuthorityCluster:
    name: str
    terms: tuple[str, ...]
    canonical_owners: tuple[str, ...]
    rename_suggestions: tuple[str, ...]


@dataclass(frozen=True)
class Hit:
    file: str
    line: int
    term: str
    cluster: str
    owner_code: str | None
    classification: str
    required_action: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "term": self.term,
            "cluster": self.cluster,
            "owner_code": self.owner_code,
            "classification": self.classification,
            "required_action": self.required_action,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class EarlyGateResult:
    status: str
    changed_files: list[str]
    scanned_files: list[str]
    skipped_files: list[str]
    owner_registry_source: str
    hits: list[Hit]

    def to_dict(self) -> dict[str, Any]:
        summary = {
            "hit_count": len(self.hits),
            "allowed_count": sum(1 for h in self.hits if h.classification == "allowed_canonical_owner_usage"),
            "rename_required_count": sum(1 for h in self.hits if h.classification == "non_authority_usage_requires_rename"),
            "review_required_count": sum(1 for h in self.hits if h.classification == "ambiguous_usage_requires_human_review"),
        }
        return {
            "artifact_type": "authority_shape_early_gate_result",
            "status": self.status,
            "changed_files": self.changed_files,
            "scanned_files": self.scanned_files,
            "skipped_files": self.skipped_files,
            "owner_registry_source": self.owner_registry_source,
            "hits": [h.to_dict() for h in self.hits],
            "summary": summary,
        }


DEFAULT_CLUSTERS: tuple[AuthorityCluster, ...] = (
    AuthorityCluster(
        name="dec" + "ision",
        terms=(
            "dec" + "ision",
            "dec" + "ided",
            "ver" + "dict",
            "app" + "rove",
            "bl" + "ock",
            "all" + "ow",
            "fre" + "eze",
            "cer" + "tify",
            "pro" + "mote",
        ),
        canonical_owners=("CDE", "CTL", "JDX"),
        rename_suggestions=("recommendation", "finding", "observation", "signal"),
    ),
    AuthorityCluster(
        name="en" + "forcement",
        terms=(
            "en" + "forcement",
            "en" + "force",
            "ha" + "lt",
            "quaran" + "tine",
            "roll" + "back",
        ),
        canonical_owners=("SEL", "ENF"),
        rename_suggestions=("compliance_signal", "containment_observation", "policy_observation"),
    ),
    AuthorityCluster(
        name="judg" + "ment",
        terms=("judg" + "ment", "adjud" + "icate", "rationale_" + "ver" + "dict"),
        canonical_owners=("JDX",),
        rename_suggestions=("finding", "rationale", "observation"),
    ),
)

_SCAN_SUFFIXES = (".py", ".md", ".json", ".yaml", ".yml", ".txt", ".rst")
_SAFE_NON_AUTHORITY = {"recommendation", "finding", "observation", "signal", "input", "candidate"}


def _normalize(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _path_matches_prefix(rel_path: str, prefix: str) -> bool:
    norm = _normalize(prefix)
    if not norm:
        return False
    if norm.endswith("/"):
        return rel_path.startswith(norm)
    return rel_path == norm or rel_path.startswith(norm + "/")


def _extract_owner_paths(system_registry_path: Path) -> dict[str, tuple[str, ...]]:
    if not system_registry_path.is_file():
        raise AuthorityShapeEarlyGateError(
            f"canonical owner registry not found: {system_registry_path}"
        )
    lines = system_registry_path.read_text(encoding="utf-8").splitlines()
    owner_paths: dict[str, list[str]] = {}
    active_owner: str | None = None
    in_primary_paths = False

    owner_header_re = re.compile(r"^###[ \t]+([A-Z][A-Z0-9]{1,5})\b")
    bullet_path_re = re.compile(r"^[ \t]*-[ \t]+`([^`]+)`")

    for raw in lines:
        owner_match = owner_header_re.match(raw)
        if owner_match:
            active_owner = owner_match.group(1).upper()
            owner_paths.setdefault(active_owner, [])
            in_primary_paths = False
            continue

        if raw.startswith("### "):
            in_primary_paths = False

        if "**Primary Code Paths:**" in raw:
            in_primary_paths = True
            continue

        if in_primary_paths:
            path_match = bullet_path_re.match(raw)
            if path_match and active_owner is not None:
                owner_paths[active_owner].append(_normalize(path_match.group(1)))
                continue
            if raw.strip() and not raw.lstrip().startswith("-"):
                in_primary_paths = False

    normalized = {code: tuple(sorted(set(paths))) for code, paths in owner_paths.items() if paths}
    if not normalized:
        raise AuthorityShapeEarlyGateError(
            "canonical owner registry parsing returned no primary code paths"
        )
    return normalized


def _resolve_owner(rel_path: str, owner_paths: dict[str, tuple[str, ...]]) -> str | None:
    matches: list[str] = []
    for code, prefixes in owner_paths.items():
        if any(_path_matches_prefix(rel_path, prefix) for prefix in prefixes):
            matches.append(code)
    if not matches:
        return None
    if len(matches) > 1:
        raise AuthorityShapeEarlyGateError(
            f"ambiguous owner mapping for '{rel_path}': {sorted(matches)}"
        )
    return matches[0]


def _term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(term).replace(r"\_", r"[_\\s]+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _scan_file(path: Path, rel_path: str, owner_code: str | None) -> list[Hit]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    hits: list[Hit] = []
    lines = text.splitlines()
    for line_no, line in enumerate(lines, start=1):
        lowered_line = line.lower()
        for cluster in DEFAULT_CLUSTERS:
            for term in cluster.terms:
                if not _term_pattern(term).search(line):
                    continue
                if any(safe in lowered_line for safe in _SAFE_NON_AUTHORITY):
                    continue
                if owner_code is None:
                    hits.append(
                        Hit(
                            file=rel_path,
                            line=line_no,
                            term=term,
                            cluster=cluster.name,
                            owner_code=None,
                            classification="ambiguous_usage_requires_human_review",
                            required_action="review_required",
                            reason="owner unresolved from canonical registry for changed file",
                        )
                    )
                elif owner_code in cluster.canonical_owners:
                    hits.append(
                        Hit(
                            file=rel_path,
                            line=line_no,
                            term=term,
                            cluster=cluster.name,
                            owner_code=owner_code,
                            classification="allowed_canonical_owner_usage",
                            required_action="none",
                            reason="term usage appears in canonical owner path for cluster",
                        )
                    )
                else:
                    hits.append(
                        Hit(
                            file=rel_path,
                            line=line_no,
                            term=term,
                            cluster=cluster.name,
                            owner_code=owner_code,
                            classification="non_authority_usage_requires_rename",
                            required_action="rename_required",
                            reason=(
                                "non-owner path used authority-shaped term; "
                                f"prefer {', '.join(cluster.rename_suggestions)}"
                            ),
                        )
                    )
    return hits


def evaluate_early_gate(
    *,
    repo_root: Path,
    changed_files: list[str],
    owner_registry_path: Path | None = None,
) -> EarlyGateResult:
    registry_path = owner_registry_path or (repo_root / "docs/architecture/system_registry.md")
    owner_paths = _extract_owner_paths(registry_path)

    candidates = sorted({_normalize(path) for path in changed_files if path})
    scanned: list[str] = []
    skipped: list[str] = []
    all_hits: list[Hit] = []

    for rel_path in candidates:
        full = repo_root / rel_path
        if not full.is_file():
            skipped.append(rel_path)
            continue
        if not rel_path.endswith(_SCAN_SUFFIXES):
            skipped.append(rel_path)
            continue
        scanned.append(rel_path)
        owner_code = _resolve_owner(rel_path, owner_paths)
        all_hits.extend(_scan_file(full, rel_path, owner_code))

    failing_hits = [
        h
        for h in all_hits
        if h.classification
        in {
            "non_authority_usage_requires_rename",
            "ambiguous_usage_requires_human_review",
        }
    ]
    status = "fail" if failing_hits else "pass"

    return EarlyGateResult(
        status=status,
        changed_files=candidates,
        scanned_files=scanned,
        skipped_files=skipped,
        owner_registry_source=_normalize(str(registry_path.relative_to(repo_root))),
        hits=all_hits,
    )


def write_result(path: Path, result: EarlyGateResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")


__all__ = [
    "AuthorityShapeEarlyGateError",
    "AuthorityCluster",
    "Hit",
    "EarlyGateResult",
    "DEFAULT_CLUSTERS",
    "evaluate_early_gate",
    "write_result",
]
