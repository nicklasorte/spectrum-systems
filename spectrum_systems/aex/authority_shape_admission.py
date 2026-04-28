"""AEX shift-left admission scan for authority-shaped vocabulary.

This module is the AEX-side admission boundary check that runs *before* the
existing ``authority_shape_preflight`` and ``system_registry_guard`` failures
would surface in CI. It catches the same class of issue earlier and emits a
structured ``authority_shape_admission_result`` artifact that PQX-equivalent
execution must consume before proceeding.

The scanner is non-owning. Canonical authority ownership lives in
``docs/architecture/system_registry.md``; this module does not redefine it.
It only:

* runs the existing static authority-shape preflight,
* layers context classification (manifest entry / schema property / generated
  report heading / non-owner module docstring / source / example),
* checks owner-context permission against the vocabulary clusters and the
  authority registry's canonical owners,
* surfaces a fail-closed reason code per diagnostic so FRE can emit a bounded
  repair candidate without inferring intent.

Stdlib-only by design: like the upstream preflight, this must run on the
minimal CI surface before contracts/jsonschema dependencies are available.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from spectrum_systems.governance.authority_shape_preflight import (
    AuthorityShapePreflightError,
    PreflightResult,
    Violation,
    VocabularyModel,
    evaluate_preflight,
    is_canonical_registry_path,
    is_guard_path,
    is_owner_path,
    load_vocabulary,
)


REASON_PROTECTED_TERM_NON_OWNER = "protected_term_in_non_owner_context"
REASON_PROTECTED_TERM_MANIFEST_ENTRY = "protected_term_in_non_owner_manifest_entry"
REASON_PROTECTED_TERM_REPORT_HEADING = "protected_term_in_generated_report_heading"
REASON_PROTECTED_TERM_DOCSTRING = "protected_term_in_non_owner_module_docstring"
REASON_UNKNOWN_OWNER_CONTEXT = "unknown_owner_context"
REASON_OWNER_CONTEXT_ALLOWED = "owner_context_allowed"


_REPORT_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_AUTHORITY_HEADING_TERMS = (
    "decision",
    "enforcement",
    "approval",
    "authority",
    "promotion",
    "certification",
    "rollback",
    "control",
    "release",
    "quarantine",
)


@dataclass(frozen=True)
class _ManifestEntry:
    file: str
    json_path: str
    line: int
    text: str


@dataclass(frozen=True)
class _ReportHeading:
    file: str
    line: int
    text: str


def classify_context_kind(rel_path: str) -> str:
    """Best-effort context-kind classifier for diagnostic enrichment."""
    norm = rel_path.replace("\\", "/").lstrip("./")
    if norm == "contracts/standards-manifest.json":
        return "manifest"
    if norm.endswith(".schema.json") or norm.startswith("contracts/schemas/"):
        return "schema"
    if norm.startswith("contracts/examples/"):
        return "example"
    if norm.startswith("docs/governance-reports/") or norm.startswith("docs/reviews/"):
        return "report"
    if norm.startswith("docs/"):
        return "doc"
    if norm.startswith("scripts/"):
        return "script"
    if norm.startswith("spectrum_systems/"):
        return "source"
    if norm.startswith("contracts/governance/"):
        return "manifest"
    if norm.startswith("contracts/"):
        return "manifest"
    return "unknown"


def _identifier_owner_allowed(rel_path: str, vocab: VocabularyModel, cluster_name: str) -> bool:
    for cluster in vocab.clusters:
        if cluster.name == cluster_name and is_owner_path(rel_path, cluster):
            return True
    return False


def _owner_for_cluster(vocab: VocabularyModel, cluster_name: str) -> str | None:
    for cluster in vocab.clusters:
        if cluster.name == cluster_name and cluster.canonical_owners:
            return cluster.canonical_owners[0]
    return None


def _owners_for_cluster(vocab: VocabularyModel, cluster_name: str) -> list[str]:
    for cluster in vocab.clusters:
        if cluster.name == cluster_name:
            return list(cluster.canonical_owners)
    return []


def _suggested_replacements(vocab: VocabularyModel, cluster_name: str) -> list[str]:
    for cluster in vocab.clusters:
        if cluster.name == cluster_name:
            return list(cluster.advisory_replacements)
    return []


def _violation_to_diagnostic(v: Violation, vocab: VocabularyModel) -> dict[str, Any]:
    rel = v.file
    context_kind = classify_context_kind(rel)
    owner_allowed = _identifier_owner_allowed(rel, vocab, v.cluster)
    fail_code: str
    if context_kind == "manifest":
        fail_code = REASON_PROTECTED_TERM_MANIFEST_ENTRY
    elif context_kind == "report":
        fail_code = REASON_PROTECTED_TERM_REPORT_HEADING
    elif context_kind in ("source", "script"):
        fail_code = REASON_PROTECTED_TERM_DOCSTRING if rel.endswith(".py") else REASON_PROTECTED_TERM_NON_OWNER
    else:
        fail_code = REASON_PROTECTED_TERM_NON_OWNER

    return {
        "status": "block",
        "file": rel,
        "line": v.line,
        "symbol": v.symbol,
        "cluster": v.cluster,
        "canonical_owner": v.canonical_owners[0] if v.canonical_owners else None,
        "canonical_owners": list(v.canonical_owners),
        "current_context": context_kind,
        "owner_context_allowed": owner_allowed,
        "context_kind": context_kind,
        "fail_closed_reason_code": fail_code,
        "suggested_safe_replacements": list(v.suggested_replacements),
        "rationale": v.rationale,
    }


def _walk_json_strings(node: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, list):
        for idx, child in enumerate(node):
            yield from _walk_json_strings(child, f"{path}[{idx}]")
    elif isinstance(node, dict):
        for key, value in node.items():
            yield path + "." + str(key), str(key)
            yield from _walk_json_strings(value, path + "." + str(key))


def _scan_manifest_entries(
    *,
    rel_path: str,
    full_path: Path,
    vocab: VocabularyModel,
) -> list[dict[str, Any]]:
    """Detect authority-shaped names in JSON manifest/example string values.

    The static identifier scanner already catches authority terms in JSON
    files, but this layer adds the manifest-entry diagnostic enrichment so
    the FRE repair candidate knows the violation lives in a
    structured-config string (e.g. ``allow_decision_proof`` listed as a
    contract artifact_type) rather than a free-form code identifier. It
    only reports per-entry diagnostics — the actual block decision is
    still made by the upstream preflight scan.
    """
    if not full_path.is_file():
        return []
    if is_guard_path(rel_path, vocab):
        return []
    if is_canonical_registry_path(rel_path, vocab):
        return []
    try:
        text = full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    safety_set = {s.lower() for s in vocab.safety_suffixes}
    diagnostics: list[dict[str, Any]] = []
    lines = text.splitlines()
    for json_path, value in _walk_json_strings(data):
        value_subtokens = {t for t in re.split(r"[_\W]+", value.lower()) if t}
        if value_subtokens & safety_set:
            continue
        if "not" in value_subtokens and "authority" in value_subtokens:
            # Standard "not_*_authority" non-authority disclaim assertion.
            continue
        for cluster in vocab.clusters:
            if is_owner_path(rel_path, cluster):
                continue
            for term in cluster.terms:
                token = term.lower().strip()
                if not token:
                    continue
                if re.search(r"(?:^|[_\s\W])" + re.escape(token) + r"(?:$|[_\s\W])", value.lower()):
                    line_no = next(
                        (idx + 1 for idx, line in enumerate(lines) if value in line and len(value) > 0),
                        0,
                    )
                    diagnostics.append(
                        {
                            "status": "block",
                            "file": rel_path,
                            "line": line_no,
                            "json_path": json_path,
                            "symbol": value,
                            "cluster": cluster.name,
                            "canonical_owner": cluster.canonical_owners[0] if cluster.canonical_owners else None,
                            "canonical_owners": list(cluster.canonical_owners),
                            "current_context": "manifest",
                            "owner_context_allowed": False,
                            "context_kind": "manifest",
                            "fail_closed_reason_code": REASON_PROTECTED_TERM_MANIFEST_ENTRY,
                            "suggested_safe_replacements": list(cluster.advisory_replacements),
                            "rationale": cluster.rationale,
                        }
                    )
                    break
    return diagnostics


def _scan_report_headings(
    *,
    rel_path: str,
    full_path: Path,
    vocab: VocabularyModel,
) -> list[dict[str, Any]]:
    """Detect authority-shape language inside generated report headings."""
    if not full_path.is_file():
        return []
    if is_guard_path(rel_path, vocab):
        return []
    if is_canonical_registry_path(rel_path, vocab):
        return []
    try:
        text = full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    diagnostics: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        match = _REPORT_HEADING_PATTERN.match(line)
        if not match:
            continue
        heading = match.group(1)
        lowered = heading.lower()
        for cluster in vocab.clusters:
            if is_owner_path(rel_path, cluster):
                continue
            for term in cluster.terms:
                if term in _AUTHORITY_HEADING_TERMS and re.search(r"\b" + re.escape(term) + r"\b", lowered):
                    diagnostics.append(
                        {
                            "status": "block",
                            "file": rel_path,
                            "line": idx,
                            "symbol": heading,
                            "cluster": cluster.name,
                            "canonical_owner": cluster.canonical_owners[0] if cluster.canonical_owners else None,
                            "canonical_owners": list(cluster.canonical_owners),
                            "current_context": "report",
                            "owner_context_allowed": False,
                            "context_kind": "report",
                            "fail_closed_reason_code": REASON_PROTECTED_TERM_REPORT_HEADING,
                            "suggested_safe_replacements": list(cluster.advisory_replacements),
                            "rationale": cluster.rationale,
                        }
                    )
                    break
            else:
                continue
            break
    return diagnostics


def _dedupe_diagnostics(diags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    out: list[dict[str, Any]] = []
    for d in diags:
        key = (
            d.get("file"),
            d.get("line"),
            d.get("symbol"),
            d.get("cluster"),
            d.get("fail_closed_reason_code"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


def evaluate_admission(
    *,
    repo_root: Path,
    changed_files: list[str],
    vocab: VocabularyModel,
    mode: str = "enforce",
) -> dict[str, Any]:
    """Evaluate AEX shift-left authority-shape admission.

    Returns an ``authority_shape_admission_result``-shaped payload. ``mode``:

    * ``enforce`` — admission ``status`` is ``block`` if any diagnostic blocks,
      so PQX is forbidden from proceeding without an accepted FRE repair
      candidate.
    * ``suggest-only`` — diagnostics are still emitted but ``status`` is
      ``pass`` (the CLI exits zero). Used for advisory shift-left runs.
    """
    if mode not in {"enforce", "suggest-only"}:
        raise AuthorityShapePreflightError(f"unsupported admission mode: {mode}")

    preflight: PreflightResult = evaluate_preflight(
        repo_root=repo_root,
        changed_files=changed_files,
        vocab=vocab,
        mode="suggest-only",
    )

    diagnostics: list[dict[str, Any]] = [
        _violation_to_diagnostic(v, vocab) for v in preflight.violations
    ]

    for rel in preflight.scanned_files:
        full_path = repo_root / rel
        if rel.endswith(".json"):
            diagnostics.extend(_scan_manifest_entries(
                rel_path=rel, full_path=full_path, vocab=vocab,
            ))
        if rel.endswith(".md"):
            diagnostics.extend(_scan_report_headings(
                rel_path=rel, full_path=full_path, vocab=vocab,
            ))

    diagnostics = _dedupe_diagnostics(diagnostics)
    block_count = sum(1 for d in diagnostics if d.get("status") == "block")
    pass_count = sum(1 for d in diagnostics if d.get("status") == "pass")

    has_block = block_count > 0
    if mode == "enforce":
        status = "block" if has_block else "pass"
    else:
        status = "pass"

    payload: dict[str, Any] = {
        "artifact_type": "authority_shape_admission_result",
        "schema_version": "1.0.0",
        "status": status,
        "mode": mode,
        "scanned_files": sorted(set(preflight.scanned_files)),
        "skipped_files": sorted(set(preflight.skipped_files)),
        "diagnostics": diagnostics,
        "summary": {
            "violation_count": len(diagnostics),
            "block_count": block_count,
            "pass_count": pass_count,
        },
        "non_authority_assertions": [
            "aex_admission_is_non_owning",
            "canonical_authority_unchanged",
            "no_decision_authority_emitted",
        ],
    }
    return payload


def admission_blocks(payload: Mapping[str, Any]) -> bool:
    """Return True when the admission artifact must block PQX progress."""
    return str(payload.get("status")) == "block"


__all__ = [
    "REASON_PROTECTED_TERM_NON_OWNER",
    "REASON_PROTECTED_TERM_MANIFEST_ENTRY",
    "REASON_PROTECTED_TERM_REPORT_HEADING",
    "REASON_PROTECTED_TERM_DOCSTRING",
    "REASON_UNKNOWN_OWNER_CONTEXT",
    "REASON_OWNER_CONTEXT_ALLOWED",
    "classify_context_kind",
    "evaluate_admission",
    "admission_blocks",
    "load_vocabulary",
]
