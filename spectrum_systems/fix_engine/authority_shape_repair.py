"""FRE bounded repair-candidate generator for authority-shape violations.

This module is the FRE-side companion to
``spectrum_systems.aex.authority_shape_admission``. Given an
``authority_shape_admission_result`` (and optionally the upstream
``authority_shape_preflight_result`` and ``system_registry_guard_result``),
it produces one ``authority_shape_repair_candidate`` per blocking diagnostic.

Bounded behavior:

* Never emits broad path exclusions; broad exclusion proposals are rejected.
* Never invents a safe replacement when none is suggested by the vocabulary
  cluster — emits an ``incomplete`` candidate with a fail-closed reason code
  instead of guessing.
* Never auto-applies an identifier/schema-breaking rename. The candidate
  records whether the rename is content-only or identifier/schema-breaking
  so PQX-equivalent execution can route accordingly.
* Never elevates a non-owner support file into a canonical authority owner.

Authority guardrails (CDE, SEL, TPA, AEX) are unchanged. The candidate is
advisory — it is consumed by the existing control path, not by FRE itself.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


REJECT_BROAD_EXCLUSION = "broad_exclusion_rejected"
REJECT_OWNER_ELEVATION = "owner_elevation_rejected"
REASON_MISSING_SAFE_REPLACEMENT = "missing_safe_replacement"
REASON_UNKNOWN_OWNER_CONTEXT = "unknown_owner_context"
REASON_INCOMPLETE_TESTS = "missing_required_tests"


_BROAD_EXCLUSION_HINTS = (
    "docs/**",
    "scripts/**",
    "spectrum_systems/**",
    "contracts/**",
    "tests/**",
    "**",
    "*",
)


@dataclass(frozen=True)
class RepairOptions:
    """Caller-supplied repair-shape policy.

    ``allow_owner_elevation`` is intentionally not exposed — promoting a
    non-owner support file to a canonical authority owner is forbidden by
    the AEX/FRE/CDE boundary. The flag exists internally to make the
    rejection branch explicit and testable.
    """

    repair_id_seed: str = "aex-fre-auth-shape-01"
    allow_owner_elevation: bool = False


class FREAuthorityShapeRepairError(ValueError):
    """Raised when the repair generator cannot run deterministically."""


def _candidate_id(seed: str, file: str, line: int, symbol: str) -> str:
    digest = hashlib.sha256(f"{seed}|{file}|{line}|{symbol}".encode("utf-8")).hexdigest()[:12]
    return f"asrc-{digest}"


def _detect_broad_exclusion_proposal(diag: Mapping[str, Any]) -> bool:
    raw = diag.get("proposed_exclusion") or diag.get("exclusion") or ""
    text = str(raw).strip()
    if not text:
        return False
    return any(text.startswith(prefix) or text == prefix for prefix in _BROAD_EXCLUSION_HINTS)


def _classify_rename_kind(diag: Mapping[str, Any]) -> str:
    context_kind = str(diag.get("context_kind") or "")
    file = str(diag.get("file") or "")
    if context_kind in ("report", "doc"):
        return "content_only"
    if context_kind == "schema":
        return "schema_breaking"
    if context_kind in ("manifest", "example"):
        return "identifier_breaking"
    if file.endswith(".py"):
        return "identifier_breaking"
    return "content_only"


def _classify_risk(rename_kind: str, context_kind: str) -> str:
    if rename_kind == "schema_breaking":
        return "high"
    if rename_kind == "identifier_breaking":
        return "medium"
    if context_kind in ("report", "doc"):
        return "low"
    return "low"


def _required_tests_for(diag: Mapping[str, Any]) -> list[str]:
    """Return the deterministic required-tests list for a diagnostic."""
    base = [
        "tests/test_authority_shape_preflight.py",
        "tests/test_aex_authority_shape_admission.py",
        "tests/test_fre_authority_shape_repair.py",
        "tests/test_aex_fre_authority_shape_loop.py",
    ]
    context_kind = str(diag.get("context_kind") or "")
    if context_kind == "manifest":
        base.append("tests/test_nx_authority_shape_preflight_regression.py")
    if context_kind == "schema":
        base.append("tests/test_contract_preflight.py")
    return sorted(set(base))


def _affected_downstream_for(diag: Mapping[str, Any]) -> list[str]:
    file = str(diag.get("file") or "")
    affected: list[str] = []
    if file.startswith("contracts/schemas/"):
        # An example artifact mirrors the schema name when one exists.
        example = file.replace("contracts/schemas/", "contracts/examples/").replace(".schema.json", ".json")
        affected.append(example)
    if file.startswith("contracts/examples/"):
        schema = file.replace("contracts/examples/", "contracts/schemas/").replace(".json", ".schema.json")
        affected.append(schema)
    if file == "contracts/standards-manifest.json":
        affected.extend(["contracts/schemas/", "contracts/examples/"])
    if file.startswith("docs/"):
        affected.append(file)
    return sorted(set(affected))


def _select_safe_replacement(diag: Mapping[str, Any]) -> str | None:
    """Pick the first vocabulary-suggested replacement, lightly contextualized."""
    suggestions = diag.get("suggested_safe_replacements") or []
    if not suggestions:
        return None
    base = str(suggestions[0])
    symbol = str(diag.get("symbol") or "")
    if not symbol:
        return base
    cluster = str(diag.get("cluster") or "")
    context_kind = str(diag.get("context_kind") or "")
    # Manifest/example entries: rewrite a recognized authority compound to
    # its safe-suffix peer rather than just the bare cluster term.
    if context_kind in ("manifest", "example"):
        rewritten = _rewrite_manifest_symbol(symbol, cluster, base)
        if rewritten:
            return rewritten
    if context_kind == "report":
        return _rewrite_report_heading(symbol, cluster, base)
    return base


_REPORT_HEADING_REWRITES: dict[str, str] = {
    "enforcement": "Compliance",
    "decision": "Recommendation",
    "approval": "Review",
    "authority": "Advisory",
    "control": "Risk",
}


def _rewrite_report_heading(heading: str, cluster: str, fallback: str) -> str:
    cluster_lower = cluster.lower()
    replacement = _REPORT_HEADING_REWRITES.get(cluster_lower)
    if not replacement:
        return heading.replace(cluster_lower.capitalize(), fallback.capitalize())
    pattern = re.compile(re.escape(cluster_lower), re.IGNORECASE)
    return pattern.sub(replacement, heading)


def _rewrite_manifest_symbol(symbol: str, cluster: str, fallback: str) -> str:
    cluster_lower = cluster.lower()
    if not cluster_lower:
        return fallback
    pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(cluster_lower) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    if pattern.search(symbol):
        return pattern.sub(_short_safe_token(fallback), symbol)
    return fallback


def _short_safe_token(replacement: str) -> str:
    """Shorten an advisory replacement (e.g. ``promotion_signal``) to its tail."""
    if "_" in replacement:
        return replacement.split("_", 1)[1] or replacement
    return replacement


def generate_repair_candidate(
    *,
    diagnostic: Mapping[str, Any],
    admission_artifact_id: str,
    options: RepairOptions | None = None,
) -> dict[str, Any]:
    """Produce one ``authority_shape_repair_candidate`` from a diagnostic."""
    opts = options or RepairOptions()
    file = str(diagnostic.get("file") or "")
    line = int(diagnostic.get("line") or 0)
    symbol = str(diagnostic.get("symbol") or "")
    if not file or not symbol:
        raise FREAuthorityShapeRepairError("diagnostic missing file or symbol")

    fail_codes: list[str] = []

    if _detect_broad_exclusion_proposal(diagnostic):
        return _rejected_candidate(
            opts=opts,
            diagnostic=diagnostic,
            admission_ref=admission_artifact_id,
            reason=REJECT_BROAD_EXCLUSION,
        )

    if not opts.allow_owner_elevation and bool(diagnostic.get("propose_owner_elevation")):
        return _rejected_candidate(
            opts=opts,
            diagnostic=diagnostic,
            admission_ref=admission_artifact_id,
            reason=REJECT_OWNER_ELEVATION,
        )

    canonical_owner = diagnostic.get("canonical_owner")
    if not canonical_owner and not diagnostic.get("canonical_owners"):
        fail_codes.append(REASON_UNKNOWN_OWNER_CONTEXT)

    safe_replacement = _select_safe_replacement(diagnostic)
    if not safe_replacement:
        fail_codes.append(REASON_MISSING_SAFE_REPLACEMENT)

    rename_kind = _classify_rename_kind(diagnostic)
    risk = _classify_risk(rename_kind, str(diagnostic.get("context_kind") or ""))
    required_tests = _required_tests_for(diagnostic)
    affected_downstream = _affected_downstream_for(diagnostic)

    candidate_status = "ready"
    if fail_codes:
        candidate_status = "incomplete"
    if not required_tests:
        candidate_status = "incomplete"
        fail_codes.append(REASON_INCOMPLETE_TESTS)

    candidate: dict[str, Any] = {
        "artifact_type": "authority_shape_repair_candidate",
        "schema_version": "1.0.0",
        "candidate_id": _candidate_id(opts.repair_id_seed, file, line, symbol),
        "source_admission_ref": admission_artifact_id,
        "file": file,
        "line": line,
        "original_text": symbol,
        "safe_replacement": safe_replacement or "",
        "replacement_rationale": _build_rationale(diagnostic, safe_replacement),
        "rename_kind": rename_kind,
        "risk_level": risk,
        "context_kind": str(diagnostic.get("context_kind") or "unknown"),
        "cluster": str(diagnostic.get("cluster") or ""),
        "canonical_owner": canonical_owner if isinstance(canonical_owner, str) else None,
        "affected_downstream": affected_downstream,
        "required_tests": required_tests,
        "candidate_status": candidate_status,
        "fail_closed_reason_codes": sorted(set(fail_codes)),
        "non_authority_assertions": [
            "fre_repair_candidate_is_advisory",
            "no_broad_exclusion_proposed",
            "canonical_authority_unchanged",
        ],
    }
    json_path = diagnostic.get("json_path")
    if isinstance(json_path, str) and json_path:
        candidate["json_path"] = json_path
    if not safe_replacement:
        # Schema requires a min-length safe_replacement for "ready" candidates;
        # for incomplete candidates we still need a string that explains why.
        candidate["safe_replacement"] = "<missing-safe-replacement-vocab-required>"
    return candidate


def _rejected_candidate(
    *,
    opts: RepairOptions,
    diagnostic: Mapping[str, Any],
    admission_ref: str,
    reason: str,
) -> dict[str, Any]:
    file = str(diagnostic.get("file") or "")
    line = int(diagnostic.get("line") or 0)
    symbol = str(diagnostic.get("symbol") or "")
    return {
        "artifact_type": "authority_shape_repair_candidate",
        "schema_version": "1.0.0",
        "candidate_id": _candidate_id(opts.repair_id_seed, file, line, symbol),
        "source_admission_ref": admission_ref,
        "file": file,
        "line": line,
        "original_text": symbol or "<unknown>",
        "safe_replacement": "<rejected>",
        "replacement_rationale": (
            "Repair rejected: bounded FRE refuses broad exclusions or owner-elevation."
        ),
        "rename_kind": "content_only",
        "risk_level": "high",
        "context_kind": str(diagnostic.get("context_kind") or "unknown"),
        "cluster": str(diagnostic.get("cluster") or ""),
        "canonical_owner": None,
        "affected_downstream": [],
        "required_tests": _required_tests_for(diagnostic),
        "candidate_status": "rejected",
        "rejection_reason": reason,
        "fail_closed_reason_codes": [reason],
        "non_authority_assertions": [
            "fre_repair_candidate_is_advisory",
            "no_broad_exclusion_proposed",
            "canonical_authority_unchanged",
        ],
    }


def _build_rationale(diag: Mapping[str, Any], safe_replacement: str | None) -> str:
    cluster = diag.get("cluster") or "unknown"
    owner = diag.get("canonical_owner") or "canonical owner (per system registry)"
    if not safe_replacement:
        return (
            f"No safe replacement is declared in the {cluster} cluster vocabulary; "
            "FRE refuses to invent a replacement. Update the cluster vocabulary first."
        )
    return (
        f"Cluster '{cluster}' authority belongs to {owner}. Non-owner contexts must "
        f"surface inputs/observations/signals; replace with '{safe_replacement}' to "
        "preserve fail-closed authority shape."
    )


def generate_repair_candidates(
    *,
    admission_result: Mapping[str, Any],
    options: RepairOptions | None = None,
) -> list[dict[str, Any]]:
    """Produce a candidate per blocking diagnostic in the admission artifact."""
    if str(admission_result.get("artifact_type")) != "authority_shape_admission_result":
        raise FREAuthorityShapeRepairError(
            "input artifact_type must be authority_shape_admission_result"
        )
    artifact_id = str(admission_result.get("artifact_id") or "authority_shape_admission_result")
    candidates: list[dict[str, Any]] = []
    for diag in admission_result.get("diagnostics") or []:
        if str(diag.get("status")) != "block":
            continue
        candidates.append(
            generate_repair_candidate(
                diagnostic=diag,
                admission_artifact_id=artifact_id,
                options=options,
            )
        )
    return candidates


__all__ = [
    "REJECT_BROAD_EXCLUSION",
    "REJECT_OWNER_ELEVATION",
    "REASON_MISSING_SAFE_REPLACEMENT",
    "REASON_UNKNOWN_OWNER_CONTEXT",
    "REASON_INCOMPLETE_TESTS",
    "FREAuthorityShapeRepairError",
    "RepairOptions",
    "generate_repair_candidate",
    "generate_repair_candidates",
]
