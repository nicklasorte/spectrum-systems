"""AEX: authority_preflight_expanded — shift-left authority violation detection (CLX-ALL-01 Phase 1).

Extends AGS-001 with three additional detection layers:
  1. Vocabulary violations — authority-shaped terms used by non-owners.
  2. Shadow ownership overlaps — a file declares ownership of a term that
     belongs to a different canonical system.
  3. Forbidden symbol misuse — decision/enforcement logic appearing outside
     canonical owner paths.

This module is non-owning and advisory. It emits ``authority_preflight_failure_packet``
artifacts for consumption by canonical owners (AEX/CDE/SEL). It does not
perform gating, enforcement, or structural expansion. Guard scripts and
canonical-owner files are always exempt from flagging.

Canonical ownership is declared in ``docs/architecture/system_registry.md``
and is NOT changed by this module.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]

# Forbidden symbol patterns: decision/enforcement logic that must not appear
# outside their canonical owner paths.
_FORBIDDEN_PATTERNS: list[tuple[str, str, list[str]]] = [
    (
        r"\bself\._decide\b|\bself\.decide\(",
        "decision_logic_outside_owner",
        ["CDE", "JDX"],
    ),
    (
        r"\bself\.enforce\b|\bself\.enforce\(",
        "enforcement_logic_outside_owner",
        ["SEL"],
    ),
    (
        r"\bself\.promote\b|\bself\.certify\b",
        "promotion_or_cert_logic_outside_owner",
        ["GOV", "CDE"],
    ),
]

# Authority vocabulary clusters (minimal subset needed for extended checks).
_VOCAB_CLUSTERS: list[dict[str, Any]] = [
    {
        "name": "decision",
        "terms": ["decision", "decides", "deciding"],
        "canonical_owners": ["JDX", "CDE"],
        "owner_path_substrings": ["closure_decision", "cde_decision", "judgment_engine", "pqx_judgment"],
        "replacements": ["decision_signal", "decision_observation", "decision_input", "decision_finding"],
    },
    {
        "name": "enforcement",
        "terms": ["enforcement", "enforces", "enforcing"],
        "canonical_owners": ["SEL"],
        "owner_path_substrings": ["enforcement_engine", "sel_enforcement", "system_enforcement"],
        "replacements": ["enforcement_signal", "compliance_observation", "enforcement_input"],
    },
    {
        "name": "promotion",
        "terms": ["promotion", "promotes", "promoting"],
        "canonical_owners": ["REL", "GOV", "CDE"],
        "owner_path_substrings": ["promotion_readiness", "promotion_decision", "merge_governance"],
        "replacements": ["promotion_signal", "readiness_observation", "promotion_input"],
    },
    {
        "name": "certification",
        "terms": ["certification", "certifies", "certifying"],
        "canonical_owners": ["GOV", "CDE"],
        "owner_path_substrings": ["certification_evidence", "done_certification"],
        "replacements": ["certification_input", "readiness_evidence", "certification_signal"],
    },
]

# Paths that are always exempt (guard scripts and canonical owner files).
_EXEMPT_PATH_SUBSTRINGS = [
    "authority_shape_preflight",
    "authority_shape_early_gate",
    "authority_leak_guard",
    "system_registry_guard",
    "authority_preflight_expanded",
    "run_authority",
    "validate_forbidden_authority",
    "authority_shape_vocabulary",
    "authority_linter",
    "authority_repair",
]

# Safety suffixes that neutralize a term (e.g., "decision_signal" is OK).
_SAFETY_SUFFIXES = frozenset([
    "signal", "observation", "input", "recommendation", "finding",
    "evidence", "advisory", "request", "record", "artifact", "packet",
    "report", "result", "summary", "trace",
])

# Scanned path prefixes (within repo).
_SCOPE_PREFIXES = [
    "spectrum_systems/",
    "scripts/",
    "contracts/",
    "tests/",
]


class AuthorityPreflightExpandedError(ValueError):
    """Raised when expanded preflight cannot complete deterministically."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _packet_id(trace_id: str) -> str:
    digest = hashlib.sha256(f"apfp-{trace_id}-{_now()}".encode()).hexdigest()[:12]
    return f"apfp-{digest}"


def _is_exempt(path_str: str) -> bool:
    low = path_str.lower()
    return any(sub in low for sub in _EXEMPT_PATH_SUBSTRINGS)


def _is_in_scope(path_str: str) -> bool:
    return any(path_str.startswith(pfx) for pfx in _SCOPE_PREFIXES)


def _relative(path: Path) -> str:
    rel = str(path).replace("\\", "/")
    prefix = str(REPO_ROOT).replace("\\", "/") + "/"
    if rel.startswith(prefix):
        rel = rel[len(prefix):]
    return rel


def _token_subtokens(symbol: str) -> list[str]:
    return [t.lower() for t in symbol.split("_") if t]


def _has_safety_suffix(symbol: str) -> bool:
    subtokens = _token_subtokens(symbol)
    return any(st in _SAFETY_SUFFIXES for st in subtokens)


def _is_owner_path(path_str: str, cluster: dict[str, Any]) -> bool:
    low = path_str.lower()
    return any(sub in low for sub in cluster["owner_path_substrings"])


def _scan_file_vocabulary(
    file_path: Path,
    rel: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return violations

    for cluster in _VOCAB_CLUSTERS:
        if _is_owner_path(rel, cluster):
            continue
        for lineno, line in enumerate(lines, 1):
            words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", line)
            for word in words:
                low = word.lower()
                for term in cluster["terms"]:
                    if term in _token_subtokens(low):
                        if not _has_safety_suffix(low):
                            violations.append({
                                "file": rel,
                                "line": lineno,
                                "symbol": word,
                                "cluster": cluster["name"],
                                "canonical_owners": cluster["canonical_owners"],
                                "suggested_replacements": cluster["replacements"],
                                "violation_type": "vocabulary_violation",
                                "rationale": (
                                    f"'{word}' uses authority-shaped cluster '{cluster['name']}' "
                                    f"outside canonical owner(s) {cluster['canonical_owners']}. "
                                    f"Use a safety suffix: {cluster['replacements'][:2]}."
                                ),
                            })
    return violations


def _scan_file_forbidden_symbols(
    file_path: Path,
    rel: str,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings

    for lineno, line in enumerate(lines, 1):
        for pattern, reason_code, owners in _FORBIDDEN_PATTERNS:
            if re.search(pattern, line):
                # Check if this file is a canonical owner path.
                if any(sub in rel.lower() for sub in ["closure_decision_engine", "enforcement_engine", "judgment_engine", "merge_governance"]):
                    continue
                findings.append({
                    "file": rel,
                    "line": lineno,
                    "symbol": line.strip()[:80],
                    "reason_code": reason_code,
                    "rationale": (
                        f"Forbidden symbol pattern '{pattern}' detected. "
                        f"This pattern is reserved for canonical owners {owners}."
                    ),
                })
    return findings


def _scan_file_shadow_overlaps(
    file_path: Path,
    rel: str,
    owner_registry: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Detect shadow ownership: a file claims ownership of a term belonging to another system."""
    # Test files reference canonical artifact types in fixtures — skip to avoid false positives.
    if rel.startswith("tests/"):
        return []
    overlaps: list[dict[str, Any]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return overlaps

    # Look for ownership claim patterns: artifact_type = "X" or class X that implies ownership.
    claim_patterns = [
        r'artifact_type\s*[=:]\s*["\']([a-z_]+)["\']',
        r'ARTIFACT_TYPE\s*=\s*["\']([a-z_]+)["\']',
        r'"artifact_type"\s*:\s*"([a-z_]+)"',
    ]

    for pattern in claim_patterns:
        for match in re.finditer(pattern, content):
            artifact_name = match.group(1)
            # Check if this artifact belongs to a different canonical owner.
            for owner_system, owned_artifacts in owner_registry.items():
                if artifact_name in owned_artifacts:
                    # Is this file in the owner's canonical path?
                    owner_paths = _get_owner_paths(owner_system)
                    if not any(p in rel.lower() for p in owner_paths):
                        overlaps.append({
                            "file": rel,
                            "symbol": artifact_name,
                            "declared_owner": _infer_module_owner(rel),
                            "actual_owner": owner_system,
                            "rationale": (
                                f"Artifact '{artifact_name}' is owned by {owner_system} "
                                f"but is claimed/emitted from non-owner path '{rel}'."
                            ),
                        })
    return overlaps


def _get_owner_paths(system: str) -> list[str]:
    paths = {
        "CDE": ["closure_decision", "cde_decision"],
        "SEL": ["enforcement_engine", "sel_enforcement", "system_enforcement"],
        "GOV": ["merge_governance", "certification_evidence"],
        "AEX": ["agent_golden_path", "admission"],
        "PQX": ["pqx_execution", "pqx_bundle", "pqx_slice"],
        "EVL": ["eval_registry", "evaluation_control", "required_eval"],
        "FRE": ["failure_diagnosis", "fre_repair"],
    }
    return paths.get(system, [])


def _infer_module_owner(rel: str) -> str:
    low = rel.lower()
    if "hop/" in low:
        return "HOP"
    if "governance/" in low:
        return "GOV"
    if "runtime/" in low:
        return "RUNTIME"
    return "UNKNOWN"


# Default registry: artifact types owned by each canonical system.
_DEFAULT_OWNER_REGISTRY: dict[str, list[str]] = {
    "CDE": ["closure_decision_artifact", "promotion_readiness_decision", "readiness_to_close"],
    "SEL": ["enforcement_action_record", "enforcement_block_record", "control_surface_enforcement_result"],
    "GOV": ["certification_evidence_index", "done_certification_record"],
    "AEX": ["build_admission_record", "normalized_execution_request", "admission_rejection_record"],
    "PQX": ["pqx_slice_execution_record", "pqx_bundle_execution_record", "pqx_execution_closure_record"],
    "EVL": ["required_eval_coverage", "evaluation_control_decision", "eval_slice_summary"],
    "FRE": ["failure_diagnosis_record", "repair_plan_artifact"],
}


def run_authority_preflight_expanded(
    *,
    changed_files: list[str],
    trace_id: str,
    run_id: str = "",
    base_ref: str = "",
    head_ref: str = "",
    owner_registry: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Run expanded authority preflight over changed files.

    Returns an ``authority_preflight_failure_packet``. Status is ``'pass'``
    when no violations, overlaps, or forbidden symbols are found; ``'fail'``
    otherwise.

    This function is deterministic: same inputs → same output.
    """
    if not isinstance(changed_files, list):
        raise AuthorityPreflightExpandedError("changed_files must be a list")

    registry = owner_registry if owner_registry is not None else _DEFAULT_OWNER_REGISTRY

    all_violations: list[dict[str, Any]] = []
    all_overlaps: list[dict[str, Any]] = []
    all_forbidden: list[dict[str, Any]] = []
    scanned: list[str] = []

    for rel_path in changed_files:
        if not isinstance(rel_path, str) or not rel_path.strip():
            continue
        rel = rel_path.strip()
        if not _is_in_scope(rel):
            continue
        if _is_exempt(rel):
            continue

        abs_path = REPO_ROOT / rel
        if not abs_path.is_file():
            continue

        if not rel.endswith(".py"):
            continue

        scanned.append(rel)
        all_violations.extend(_scan_file_vocabulary(abs_path, rel))
        all_forbidden.extend(_scan_file_forbidden_symbols(abs_path, rel))
        all_overlaps.extend(_scan_file_shadow_overlaps(abs_path, rel, registry))

    total_count = len(all_violations) + len(all_forbidden)
    status = "pass" if total_count == 0 and not all_overlaps else "fail"

    return {
        "artifact_type": "authority_preflight_failure_packet",
        "schema_version": "1.0.0",
        "packet_id": _packet_id(trace_id),
        "trace_id": trace_id,
        "run_id": run_id,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "scanned_files": scanned,
        "violation_count": total_count,
        "violations": all_violations,
        "shadow_overlaps": all_overlaps,
        "forbidden_symbols": all_forbidden,
        "status": status,
        "producer_authority": "AEX",
        "non_authority_assertions": [
            "This packet is advisory evidence only.",
            "Canonical owners (AEX/CDE/SEL) perform enforcement.",
            "This module does not gate, block, or enforce.",
        ],
        "emitted_at": _now(),
    }


__all__ = [
    "AuthorityPreflightExpandedError",
    "run_authority_preflight_expanded",
]
