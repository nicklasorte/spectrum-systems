"""Deterministic System Registry Guard (SRG) parser and overlap enforcement.

SRG is a mandatory governance guard invoked by admission/preflight surfaces.
It validates repository changes against canonical ownership boundaries defined in
`docs/architecture/system_registry.md`.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SystemRegistryGuardError(ValueError):
    """Raised when deterministic SRG evaluation cannot be completed."""


@dataclass(frozen=True)
class RegistrySystem:
    acronym: str
    full_name: str
    role: str
    owns: tuple[str, ...]
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    must_not_do: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class RegistryModel:
    source_path: str
    source_digest: str
    systems: dict[str, RegistrySystem]
    active_systems: tuple[str, ...]
    deprecated_systems: tuple[str, ...]
    removed_systems: tuple[str, ...]
    placeholder_systems: tuple[str, ...]


_SECTION_HEADER = re.compile(r"^##\s+(.+?)\s*$")
_SYSTEM_HEADER = re.compile(r"^###\s+([A-Z0-9]{2,8})\s*$")
_FIELD_LINE = re.compile(r"^\s*-\s+\*\*(acronym|full_name|role|owns|consumes|produces|must_not_do):\*\*\s*(.*)$")
_BULLET_LINE = re.compile(r"^\s*-\s+(.*)$")
_SYSTEM_MAP_ENTRY = re.compile(r"^\s*-\s+\*\*([A-Z0-9]{2,8})\*\*\s+—\s+(.*)$")
_SYSTEM_CANDIDATE_PATTERNS = [
    re.compile(r"^\s*###\s+([A-Z0-9]{3})\s*$"),
    re.compile(r"\*\*([A-Z0-9]{3})\*\*\s+—"),
    re.compile(r"\bacronym\s*:\s*`?([A-Z0-9]{3})`?"),
    re.compile(r"\b([A-Z0-9]{3})\s+system\b"),
]
_OWNER_CLAIM_PATTERNS = [
    re.compile(r"\bowns\b", re.IGNORECASE),
    re.compile(r"\bowner of\b", re.IGNORECASE),
    re.compile(r"\bcanonical owner\b", re.IGNORECASE),
    re.compile(r"\blifecycle owner\b", re.IGNORECASE),
    re.compile(r"\bresponsible for\b", re.IGNORECASE),
    re.compile(r"\bauthority\b", re.IGNORECASE),
    re.compile(r"\bcontrols\b", re.IGNORECASE),
    re.compile(r"\bgovers?ns\b", re.IGNORECASE),
    re.compile(r"\bemits\b", re.IGNORECASE),
    re.compile(r"\boverride\b", re.IGNORECASE),
]


def _normalize_tokens(text: str) -> list[str]:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    tokens: list[str] = []
    for token in lowered.split():
        if token.endswith("ies") and len(token) > 3:
            token = token[:-3] + "y"
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return tokens


def _stable_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_guard_policy(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemRegistryGuardError(f"guard policy file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemRegistryGuardError(f"guard policy JSON invalid: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemRegistryGuardError("guard policy must be a JSON object")
    return payload


def parse_system_registry(path: Path) -> RegistryModel:
    if not path.is_file():
        raise SystemRegistryGuardError(f"registry markdown not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    systems_from_map: dict[str, str] = {}
    current_section = ""
    in_system_map = False
    current_system: str | None = None
    collecting_list: str | None = None
    parsed: dict[str, dict[str, Any]] = {}

    for line in lines:
        section_match = _SECTION_HEADER.match(line)
        if section_match:
            current_section = section_match.group(1).strip().lower()
            in_system_map = current_section == "system map"

        if in_system_map:
            entry = _SYSTEM_MAP_ENTRY.match(line)
            if entry:
                acronym = entry.group(1).strip().upper()
                descriptor = entry.group(2).strip().lower()
                status = "active"
                if "deprecated" in descriptor:
                    status = "deprecated"
                if "historical" in descriptor or "removed" in descriptor or "not currently present" in descriptor:
                    status = "removed"
                if "placeholder" in descriptor:
                    status = "placeholder"
                systems_from_map[acronym] = status

        header = _SYSTEM_HEADER.match(line)
        if header:
            current_system = header.group(1).strip().upper()
            collecting_list = None
            parsed.setdefault(
                current_system,
                {
                    "acronym": current_system,
                    "full_name": "",
                    "role": "",
                    "owns": [],
                    "consumes": [],
                    "produces": [],
                    "must_not_do": [],
                },
            )
            continue

        if current_system is None:
            continue

        field = _FIELD_LINE.match(line)
        if field:
            name, remainder = field.groups()
            if name in {"acronym", "full_name", "role"}:
                parsed[current_system][name] = remainder.strip().strip("`")
                collecting_list = None
            else:
                collecting_list = name
            continue

        if collecting_list:
            bullet = _BULLET_LINE.match(line)
            if bullet:
                item = bullet.group(1).strip()
                if item and not item.startswith("**"):
                    parsed[current_system][collecting_list].append(item)
                continue
            if line.strip() and not line.strip().startswith("-"):
                collecting_list = None

    if "System Definitions" not in path.read_text(encoding="utf-8"):
        raise SystemRegistryGuardError("registry missing required 'System Definitions' section")

    systems: dict[str, RegistrySystem] = {}
    for acronym, row in parsed.items():
        owns = tuple(str(item).strip() for item in row["owns"] if str(item).strip())
        status = systems_from_map.get(acronym, "active")
        systems[acronym] = RegistrySystem(
            acronym=acronym,
            full_name=str(row.get("full_name") or "").strip(),
            role=str(row.get("role") or "").strip(),
            owns=owns,
            consumes=tuple(str(item).strip() for item in row["consumes"] if str(item).strip()),
            produces=tuple(str(item).strip() for item in row["produces"] if str(item).strip()),
            must_not_do=tuple(str(item).strip() for item in row["must_not_do"] if str(item).strip()),
            status=status,
        )

    if not systems:
        raise SystemRegistryGuardError("registry parsing failed: no system definitions found")

    owners: dict[str, str] = {}
    for acronym, system in systems.items():
        if system.status == "removed":
            continue
        for responsibility in system.owns:
            key = responsibility.strip().lower()
            if not key:
                continue
            if key in owners and owners[key] != acronym:
                raise SystemRegistryGuardError(
                    f"registry ownership conflict for '{responsibility}': {owners[key]} and {acronym}"
                )
            owners[key] = acronym

    digest = _stable_hash(
        {
            "systems": {
                key: {
                    "status": value.status,
                    "owns": list(value.owns),
                    "must_not_do": list(value.must_not_do),
                }
                for key, value in sorted(systems.items())
            }
        }
    )

    return RegistryModel(
        source_path=str(path),
        source_digest=digest,
        systems=systems,
        active_systems=tuple(sorted([k for k, v in systems.items() if v.status == "active"])),
        deprecated_systems=tuple(sorted([k for k, v in systems.items() if v.status == "deprecated"])),
        removed_systems=tuple(sorted([k for k, v in systems.items() if v.status == "removed"])),
        placeholder_systems=tuple(sorted([k for k, v in systems.items() if v.status == "placeholder"])),
    )


def evaluate_system_registry_guard(
    *,
    repo_root: Path,
    changed_files: list[str],
    policy: dict[str, Any],
    registry_model: RegistryModel,
) -> dict[str, Any]:
    changed_paths = sorted(set(path for path in changed_files if path))
    owners_by_responsibility: dict[str, str] = {}
    cluster_owner: dict[str, str] = {}

    clusters = policy.get("responsibility_clusters", {}) if isinstance(policy.get("responsibility_clusters"), dict) else {}
    synonym_groups = policy.get("synonym_groups", {}) if isinstance(policy.get("synonym_groups"), dict) else {}
    phrase_mappings = policy.get("phrase_mappings", {}) if isinstance(policy.get("phrase_mappings"), dict) else {}
    protected_seams = {
        str(key): str(value).upper()
        for key, value in (policy.get("protected_authority_seams", {}) or {}).items()
        if str(key).strip() and str(value).strip()
    }

    synonym_to_cluster: dict[str, str] = {}
    for cluster, words in clusters.items():
        words_list = list(words) if isinstance(words, list) else []
        for word in words_list:
            synonym_to_cluster[str(word).lower()] = str(cluster)
    for cluster, words in synonym_groups.items():
        words_list = list(words) if isinstance(words, list) else []
        for word in words_list:
            synonym_to_cluster[str(word).lower()] = str(cluster)
    for phrase, cluster in phrase_mappings.items():
        synonym_to_cluster[str(phrase).lower()] = str(cluster)

    def normalize_cluster(text: str) -> str | None:
        lowered = text.lower()
        for phrase, cluster in phrase_mappings.items():
            if phrase.lower() in lowered:
                return str(cluster)
        for token in _normalize_tokens(lowered):
            if token in synonym_to_cluster:
                return synonym_to_cluster[token]
        return None

    for acronym, system in registry_model.systems.items():
        if system.status not in {"active", "deprecated", "placeholder"}:
            continue
        for own in system.owns:
            key = own.lower().strip()
            owners_by_responsibility[key] = acronym
            cluster = normalize_cluster(own)
            if cluster and cluster not in cluster_owner:
                cluster_owner[cluster] = acronym

    detected_system_candidates: list[dict[str, Any]] = []
    detected_owner_claims: list[dict[str, Any]] = []
    overlaps_found: list[dict[str, Any]] = []
    shadow_owner_findings: list[dict[str, Any]] = []
    removed_refs: list[dict[str, Any]] = []
    registration_failures: list[dict[str, Any]] = []
    protected_violations: list[dict[str, Any]] = []
    acronym_collisions: list[dict[str, Any]] = []
    unowned_system_like_paths: list[dict[str, Any]] = []
    ambiguous_system_like_paths: list[dict[str, Any]] = []
    required_actions: list[str] = []
    reason_codes: set[str] = set()
    policy_system_like_prefixes = tuple(
        str(item)
        for item in (policy.get("system_like_path_prefixes") or [])
        if isinstance(item, str) and item.strip()
    )
    non_authority_prefixes = tuple(
        str(item)
        for item in (policy.get("non_authority_path_prefixes") or [])
        if isinstance(item, str) and item.strip()
    )
    non_authority_exact_paths = {
        str(item)
        for item in (policy.get("non_authority_exact_paths") or [])
        if isinstance(item, str) and item.strip()
    }
    authoritative_suffixes = tuple(
        str(item)
        for item in (policy.get("authoritative_owner_scan_suffixes") or [".md", ".py", ".txt", ".rst"])
        if isinstance(item, str) and item.strip()
    )
    policy_reserved_prefixes = tuple(
        str(item)
        for item in (policy.get("reserved_or_transitional_path_prefixes") or [])
        if isinstance(item, str) and item.strip()
    )

    owner_path_hints: dict[str, list[str]] = {}
    for acronym, system in registry_model.systems.items():
        if system.status not in {"active", "placeholder", "deprecated"}:
            continue
        owners = owner_path_hints.setdefault(acronym, [])
        owners.append(f"docs/architecture/system_registry.md::{acronym}")
        for own in system.owns:
            token = str(own or "").strip().lower().replace(" ", "_")
            if token:
                owners.append(token)

    diagnostics: list[dict[str, Any]] = []

    def _is_non_authority_path(rel_path: str) -> bool:
        if rel_path in non_authority_exact_paths:
            return True
        return bool(non_authority_prefixes and rel_path.startswith(non_authority_prefixes))

    def _is_authoritative_scan_path(rel_path: str) -> bool:
        if _is_non_authority_path(rel_path):
            return False
        if not authoritative_suffixes:
            return True
        return rel_path.endswith(authoritative_suffixes)

    for rel_path in changed_paths:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        if rel_path == "docs/architecture/system_registry.md":
            continue
        if not _is_authoritative_scan_path(rel_path):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            for pattern in _SYSTEM_CANDIDATE_PATTERNS:
                for match in pattern.finditer(line):
                    candidate = str(match.group(1)).upper()
                    if len(candidate) == 3:
                        detected_system_candidates.append(
                            {"system": candidate, "file": rel_path, "line": idx, "text": line.strip()}
                        )

            if any(p.search(line) for p in _OWNER_CLAIM_PATTERNS):
                system_match = re.search(r"\b([A-Z0-9]{3})\b", line)
                if system_match:
                    subject = system_match.group(1).upper()
                    claim = {
                        "system": subject,
                        "file": rel_path,
                        "line": idx,
                        "text": line.strip(),
                        "cluster": normalize_cluster(line),
                    }
                    detected_owner_claims.append(claim)
                    if subject in registry_model.removed_systems:
                        removed_refs.append(
                            {
                                "file": rel_path,
                                "line": idx,
                                "system": subject,
                                "reason": "removed/deprecated system referenced as active owner claim",
                                "resolution_category": "remove",
                            }
                        )
                        diagnostics.append(
                            {
                                "reason_code": "REMOVED_SYSTEM_REFERENCE",
                                "file": rel_path,
                                "line": idx,
                                "symbol": subject,
                                "resolution_category": "remove",
                            }
                        )
                        reason_codes.add("REMOVED_SYSTEM_REFERENCE")

                    cluster = claim["cluster"]
                    shadow_detected = False
                    if cluster:
                        canonical_owner = cluster_owner.get(cluster)
                        if canonical_owner and canonical_owner != subject:
                            shadow_detected = True
                            shadow_owner_findings.append(
                                {
                                    "file": rel_path,
                                    "line": idx,
                                    "system": subject,
                                    "cluster": cluster,
                                    "canonical_owner": canonical_owner,
                                    "reason": "semantic ownership overlap",
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            diagnostics.append(
                                {
                                    "reason_code": "SHADOW_OWNERSHIP_OVERLAP",
                                    "file": rel_path,
                                    "line": idx,
                                    "symbol": subject,
                                    "cluster": cluster,
                                    "canonical_owner": canonical_owner,
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            reason_codes.add("SHADOW_OWNERSHIP_OVERLAP")

                    suppress_protected_for_shadow = shadow_detected and subject not in registry_model.systems
                    for seam, owner in protected_seams.items():
                        if seam.lower() in line.lower() and subject != owner and not suppress_protected_for_shadow:
                            protected_violations.append(
                                {
                                    "file": rel_path,
                                    "line": idx,
                                    "protected_seam": seam,
                                    "claimed_owner": subject,
                                    "canonical_owner": owner,
                                    "reason": "protected authority seam claimed by non-owner",
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            diagnostics.append(
                                {
                                    "reason_code": "PROTECTED_AUTHORITY_VIOLATION",
                                    "file": rel_path,
                                    "line": idx,
                                    "symbol": subject,
                                    "responsibility": seam,
                                    "canonical_owner": owner,
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            reason_codes.add("PROTECTED_AUTHORITY_VIOLATION")

                    for responsibility, owner in owners_by_responsibility.items():
                        if responsibility and responsibility in line.lower() and subject in registry_model.systems and owner != subject:
                            overlaps_found.append(
                                {
                                    "file": rel_path,
                                    "line": idx,
                                    "system": subject,
                                    "responsibility": responsibility,
                                    "canonical_owner": owner,
                                    "reason": "direct ownership overlap",
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            diagnostics.append(
                                {
                                    "reason_code": "DIRECT_OWNERSHIP_OVERLAP",
                                    "file": rel_path,
                                    "line": idx,
                                    "symbol": subject,
                                    "responsibility": responsibility,
                                    "canonical_owner": owner,
                                    "resolution_category": "fold_into_owner",
                                }
                            )
                            reason_codes.add("DIRECT_OWNERSHIP_OVERLAP")

        active_or_known = set(registry_model.systems.keys())
        registry_changed = "docs/architecture/system_registry.md" in changed_paths
        for candidate_entry in detected_system_candidates:
            candidate = candidate_entry["system"]
            if candidate in active_or_known:
                status = registry_model.systems[candidate].status
                system_row = registry_model.systems[candidate]
                if registry_changed and (
                    not system_row.full_name
                    or not system_row.role
                    or not system_row.owns
                    or not system_row.consumes
                    or not system_row.produces
                    or not system_row.must_not_do
                ):
                    registration_failures.append(
                        {
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "system": candidate,
                            "reason": "new system registry entry missing required canonical fields",
                            "resolution_category": "register",
                        }
                    )
                    diagnostics.append(
                        {
                            "reason_code": "INCOMPLETE_SYSTEM_REGISTRATION",
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "symbol": candidate,
                            "resolution_category": "register",
                        }
                    )
                    reason_codes.add("INCOMPLETE_SYSTEM_REGISTRATION")
                if status == "removed" and rel_path != "docs/architecture/system_registry.md":
                    removed_refs.append(
                        {
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "system": candidate,
                            "reason": "removed/deprecated system referenced as active candidate",
                            "resolution_category": "remove",
                        }
                    )
                    diagnostics.append(
                        {
                            "reason_code": "REMOVED_SYSTEM_REFERENCE",
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "symbol": candidate,
                            "resolution_category": "remove",
                        }
                    )
                    reason_codes.add("REMOVED_SYSTEM_REFERENCE")
                continue
            if candidate == "SRG":
                registration_failures.append(
                    {
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "system": candidate,
                        "reason": "SRG must not be introduced as canonical system owner",
                        "resolution_category": "remove",
                    }
                )
                diagnostics.append(
                    {
                        "reason_code": "SRG_OWNER_INTRODUCTION_FORBIDDEN",
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "symbol": candidate,
                        "resolution_category": "remove",
                    }
                )
                reason_codes.add("SRG_OWNER_INTRODUCTION_FORBIDDEN")
                continue
            if not registry_changed:
                registration_failures.append(
                    {
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "system": candidate,
                        "reason": "new system introduced without same-change registry update",
                        "resolution_category": "register",
                    }
                )
                diagnostics.append(
                    {
                        "reason_code": "NEW_SYSTEM_MISSING_REGISTRATION",
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "symbol": candidate,
                        "resolution_category": "register",
                    }
                )
                reason_codes.add("NEW_SYSTEM_MISSING_REGISTRATION")
            else:
                registry_text = (repo_root / "docs/architecture/system_registry.md").read_text(encoding="utf-8")
                required_fields = ["**acronym:**", "**full_name:**", "**role:**", "**owns:**", "**consumes:**", "**produces:**", "**must_not_do:**"]
                header = f"### {candidate}"
                if header not in registry_text or any(field not in registry_text.split(header, 1)[1] for field in required_fields):
                    registration_failures.append(
                        {
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "system": candidate,
                            "reason": "new system registry entry missing required canonical fields",
                            "resolution_category": "register",
                        }
                    )
                    diagnostics.append(
                        {
                            "reason_code": "INCOMPLETE_SYSTEM_REGISTRATION",
                            "file": candidate_entry["file"],
                            "line": candidate_entry["line"],
                            "symbol": candidate,
                            "resolution_category": "register",
                        }
                    )
                    reason_codes.add("INCOMPLETE_SYSTEM_REGISTRATION")

            if candidate in registry_model.removed_systems:
                acronym_collisions.append(
                    {
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "system": candidate,
                        "reason": "acronym collision with retired namespace",
                        "resolution_category": "remove",
                    }
                )
                diagnostics.append(
                    {
                        "reason_code": "ACRONYM_NAMESPACE_COLLISION",
                        "file": candidate_entry["file"],
                        "line": candidate_entry["line"],
                        "symbol": candidate,
                        "resolution_category": "remove",
                    }
                )
                reason_codes.add("ACRONYM_NAMESPACE_COLLISION")

    if bool(policy.get("require_three_letter_system_tokens")):
        for rel_path in changed_paths:
            if rel_path == "docs/architecture/system_registry.md":
                continue
            if policy_reserved_prefixes and rel_path.startswith(policy_reserved_prefixes):
                continue
            if policy_system_like_prefixes and not rel_path.startswith(policy_system_like_prefixes):
                continue
            if _is_non_authority_path(rel_path):
                continue
            path = repo_root / rel_path
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            lines = content.splitlines()
            has_system_semantics = False
            for line in lines:
                if any(pattern.search(line) for pattern in _OWNER_CLAIM_PATTERNS) or any(
                    pattern.search(line) for pattern in _SYSTEM_CANDIDATE_PATTERNS
                ):
                    has_system_semantics = True
                    break
            if not has_system_semantics:
                continue

            matched_owners: list[str] = []
            lowered_path = rel_path.lower()
            for acronym, hints in owner_path_hints.items():
                if any(hint and hint in lowered_path for hint in hints):
                    matched_owners.append(acronym)
            if not matched_owners:
                unowned_system_like_paths.append(
                    {
                        "file": rel_path,
                        "reason": "system-like path changed without detectable 3-letter owner alignment",
                        "resolution_category": "convert_to_non_authority_artifact",
                    }
                )
                diagnostics.append(
                    {
                        "reason_code": "UNOWNED_SYSTEM_SURFACE",
                        "file": rel_path,
                        "line": None,
                        "symbol": None,
                        "resolution_category": "convert_to_non_authority_artifact",
                    }
                )
                reason_codes.add("UNOWNED_SYSTEM_SURFACE")
            elif len(set(matched_owners)) > 1:
                ambiguous_system_like_paths.append(
                    {
                        "file": rel_path,
                        "candidate_owners": sorted(set(matched_owners)),
                        "reason": "multiple 3-letter systems appear to match changed system-like path",
                        "resolution_category": "fold_into_owner",
                    }
                )
                diagnostics.append(
                    {
                        "reason_code": "AMBIGUOUS_SYSTEM_SURFACE",
                        "file": rel_path,
                        "line": None,
                        "symbol": None,
                        "resolution_category": "fold_into_owner",
                    }
                )
                reason_codes.add("AMBIGUOUS_SYSTEM_SURFACE")

    if overlaps_found:
        required_actions.append("Use the canonical owner responsibilities from docs/architecture/system_registry.md.")
    if shadow_owner_findings:
        required_actions.append("Narrow ownership language to non-owning support semantics or delegate to canonical owner.")
    if registration_failures:
        required_actions.append("Register allowed new systems in docs/architecture/system_registry.md within the same change set.")
    if removed_refs:
        required_actions.append("Mark historical systems as non-authoritative historical references, not active owners.")
    if protected_violations:
        required_actions.append("Restore protected authority seams to their canonical owner system.")
    if unowned_system_like_paths:
        required_actions.append("Declare explicit 3-letter ownership for changed system-like paths or mark them reserved/transitional.")
    if ambiguous_system_like_paths:
        required_actions.append("Resolve ambiguous 3-letter ownership claims to a single canonical owner per changed path.")

    failed = bool(
        overlaps_found
        or shadow_owner_findings
        or removed_refs
        or registration_failures
        or protected_violations
        or acronym_collisions
        or unowned_system_like_paths
        or ambiguous_system_like_paths
    )

    unique_diagnostics: list[dict[str, Any]] = []
    seen_diagnostics: set[str] = set()
    for item in diagnostics:
        key = _stable_hash(item)
        if key in seen_diagnostics:
            continue
        seen_diagnostics.add(key)
        unique_diagnostics.append(item)

    return {
        "artifact_type": "system_registry_guard_result",
        "status": "fail" if failed else "pass",
        "checked_files": changed_paths,
        "changed_files": changed_paths,
        "detected_system_candidates": detected_system_candidates,
        "detected_owner_claims": detected_owner_claims,
        "overlaps_found": overlaps_found,
        "shadow_owner_findings": shadow_owner_findings,
        "removed_system_references_found": removed_refs,
        "registration_failures": registration_failures,
        "protected_authority_violations": protected_violations,
        "acronym_collisions": acronym_collisions,
        "unowned_system_like_paths": unowned_system_like_paths,
        "ambiguous_system_like_paths": ambiguous_system_like_paths,
        "required_actions": sorted(set(required_actions)),
        "normalized_reason_codes": sorted(reason_codes),
        "diagnostics": unique_diagnostics,
        "registry_digest_or_version": registry_model.source_digest,
        "trace": {
            "registry_path": registry_model.source_path,
            "policy_version": str(policy.get("policy_version", "unknown")),
            "active_system_count": len(registry_model.active_systems),
            "deprecated_system_count": len(registry_model.deprecated_systems),
            "placeholder_system_count": len(registry_model.placeholder_systems),
            "removed_system_count": len(registry_model.removed_systems),
        },
    }


__all__ = [
    "SystemRegistryGuardError",
    "RegistrySystem",
    "RegistryModel",
    "load_guard_policy",
    "parse_system_registry",
    "evaluate_system_registry_guard",
]
