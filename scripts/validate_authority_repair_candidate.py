#!/usr/bin/env python3
"""TPA policy/trust check for ASF-01 authority-shape repair candidates.

Validates that an ``authority_shape_repair_candidate`` artifact stays inside
the bounded-repair envelope:

- Every proposed replacement uses a neutral vocabulary term drawn from the
  existing authority-shape vocabulary clusters or the authority-neutral
  vocabulary map. No invented replacements.
- No edits to the authority registry.
- No allowlist or scope-prefix weakening.
- Every target file appears in the changed-scope scan record's changed-file
  set when one is supplied, otherwise the candidate must declare its
  changed-file scope inline.
- ``replacement_class`` is always ``vocabulary_only``.
- ``status`` remains ``proposed`` (TPA does not authorize, that is CDE).
- Required ``prohibited_actions`` are present.

This script is non-owning. It emits an
``authority_repair_policy_check_record`` and a non-zero exit on failure.
Authority remains with CDE/SEL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


ARTIFACT_TYPE = "authority_repair_policy_check_record"
SCHEMA_VERSION = "1.0.0"

REQUIRED_PROHIBITED_ACTIONS = (
    "no_allowlist_change",
    "no_owner_registry_change",
    "no_cross_file_rewrite_without_evidence",
)

DEFAULT_VOCAB_PATH = "contracts/governance/authority_shape_vocabulary.json"
DEFAULT_NEUTRAL_VOCAB_PATH = "contracts/governance/authority_neutral_vocabulary.json"


class AuthorityRepairPolicyError(RuntimeError):
    """Raised when the TPA policy check cannot complete deterministically."""


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, help="Path to repair candidate JSON")
    parser.add_argument(
        "--scan-record",
        default=None,
        help="Optional path to the source changed_scope_authority_scan_record",
    )
    parser.add_argument(
        "--vocabulary",
        default=DEFAULT_VOCAB_PATH,
        help="Authority-shape vocabulary path (provides allowed neutral replacements)",
    )
    parser.add_argument(
        "--neutral-vocabulary",
        default=DEFAULT_NEUTRAL_VOCAB_PATH,
        help="Authority neutral vocabulary path (extra approved neutral terms)",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_repair_policy_check_record.json",
        help="Output artifact path",
    )
    return parser.parse_args()


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise AuthorityRepairPolicyError(f"file missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AuthorityRepairPolicyError(f"invalid JSON {path}: {exc}") from exc


def _collect_approved_neutral_terms(
    *, vocabulary: dict[str, Any], neutral_vocab: dict[str, Any]
) -> set[str]:
    approved: set[str] = set()
    for cluster_body in (vocabulary.get("clusters") or {}).values():
        if not isinstance(cluster_body, dict):
            continue
        for replacement in cluster_body.get("advisory_replacements") or []:
            if isinstance(replacement, str) and replacement.strip():
                approved.add(replacement.strip().lower())
    for safe_pair in vocabulary.get("safe_rename_pairs") or []:
        if isinstance(safe_pair, dict):
            target = str(safe_pair.get("to") or "").strip().lower()
            if target:
                approved.add(target)
    for replacement_list in (neutral_vocab.get("neutral_replacements") or {}).values():
        if isinstance(replacement_list, list):
            for term in replacement_list:
                if isinstance(term, str) and term.strip():
                    approved.add(term.strip().lower())
    safety_suffixes = vocabulary.get("safety_suffixes") or []
    return approved


def _collect_forbidden_terms(
    *, vocabulary: dict[str, Any], neutral_vocab: dict[str, Any]
) -> set[str]:
    forbidden: set[str] = set()
    for cluster_body in (vocabulary.get("clusters") or {}).values():
        if not isinstance(cluster_body, dict):
            continue
        for term in cluster_body.get("terms") or []:
            if isinstance(term, str) and term.strip():
                forbidden.add(term.strip().lower())
    for term in neutral_vocab.get("forbidden_terms") or []:
        if isinstance(term, str) and term.strip():
            forbidden.add(term.strip().lower())
    return forbidden


def _has_safety_suffix(symbol: str, safety_suffixes: Iterable[str]) -> bool:
    tokens = {tok for tok in symbol.lower().split("_") if tok}
    return any(suffix.lower() in tokens for suffix in safety_suffixes)


def _replacement_is_neutral(
    *,
    proposed: str,
    approved_terms: set[str],
    forbidden_terms: set[str],
    safety_suffixes: Iterable[str],
) -> tuple[bool, str | None]:
    lowered = proposed.strip().lower()
    if not lowered:
        return False, "empty_replacement"
    tokens = {tok for tok in lowered.split("_") if tok}
    if any(tok in forbidden_terms for tok in tokens) and not _has_safety_suffix(
        lowered, safety_suffixes
    ):
        return False, "replacement_contains_forbidden_term_without_safety_suffix"
    if lowered in approved_terms:
        return True, None
    if _has_safety_suffix(lowered, safety_suffixes) and not any(
        tok in forbidden_terms for tok in tokens
    ):
        return True, None
    return False, "replacement_not_in_approved_neutral_vocabulary"


def _normalize_paths(values: Iterable[str]) -> set[str]:
    return {str(v).replace("\\", "/").strip().lstrip("./") for v in values if v}


def validate_candidate(
    *,
    candidate: dict[str, Any],
    vocabulary: dict[str, Any],
    neutral_vocab: dict[str, Any],
    scan_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    if candidate.get("artifact_type") != "authority_shape_repair_candidate":
        findings.append(
            {
                "rule": "candidate_artifact_type",
                "message": "candidate artifact_type must be 'authority_shape_repair_candidate'",
            }
        )
        reason_codes.append("invalid_artifact_type")

    status = candidate.get("status")
    if status != "proposed":
        findings.append(
            {
                "rule": "candidate_status_proposed",
                "message": f"candidate.status must remain 'proposed' (TPA does not authorize); got {status!r}",
            }
        )
        reason_codes.append("non_proposed_status")

    prohibited_actions = candidate.get("prohibited_actions") or []
    if not isinstance(prohibited_actions, list):
        prohibited_actions = []
    missing_required = [
        action for action in REQUIRED_PROHIBITED_ACTIONS if action not in prohibited_actions
    ]
    if missing_required:
        findings.append(
            {
                "rule": "required_prohibited_actions",
                "message": "candidate must declare required prohibited_actions",
                "missing": missing_required,
            }
        )
        reason_codes.append("missing_prohibited_actions")

    target_files = candidate.get("target_files") or []
    target_set = _normalize_paths(target_files)

    scan_changed: set[str] = set()
    if scan_record is not None:
        if scan_record.get("artifact_type") != "changed_scope_authority_scan_record":
            findings.append(
                {
                    "rule": "scan_record_artifact_type",
                    "message": "scan record artifact_type must be 'changed_scope_authority_scan_record'",
                }
            )
            reason_codes.append("invalid_scan_record_type")
        scan_changed = _normalize_paths(scan_record.get("changed_files") or [])
        out_of_scope = sorted(target_set - scan_changed) if scan_changed else []
        if out_of_scope:
            findings.append(
                {
                    "rule": "target_files_outside_changed_set",
                    "message": "candidate targets files outside the changed file set",
                    "files": out_of_scope,
                }
            )
            reason_codes.append("out_of_scope_target_files")

    approved_terms = _collect_approved_neutral_terms(
        vocabulary=vocabulary, neutral_vocab=neutral_vocab
    )
    forbidden_terms = _collect_forbidden_terms(
        vocabulary=vocabulary, neutral_vocab=neutral_vocab
    )
    safety_suffixes = vocabulary.get("safety_suffixes") or []

    replacements = candidate.get("replacements") or []
    if not isinstance(replacements, list):
        replacements = []

    for index, replacement in enumerate(replacements, start=1):
        if not isinstance(replacement, dict):
            findings.append(
                {
                    "rule": "replacement_object",
                    "message": f"replacement #{index} must be a JSON object",
                    "index": index,
                }
            )
            reason_codes.append("invalid_replacement_object")
            continue

        replacement_class = replacement.get("replacement_class")
        if replacement_class != "vocabulary_only":
            findings.append(
                {
                    "rule": "replacement_class_vocabulary_only",
                    "message": (
                        f"replacement #{index} replacement_class must be 'vocabulary_only'; "
                        f"got {replacement_class!r}"
                    ),
                    "index": index,
                }
            )
            reason_codes.append("non_vocabulary_only_replacement")

        target_file = str(replacement.get("file") or "").replace("\\", "/").strip().lstrip("./")
        if target_file and target_set and target_file not in target_set:
            findings.append(
                {
                    "rule": "replacement_outside_target_files",
                    "message": (
                        f"replacement #{index} file {target_file!r} is not in candidate target_files"
                    ),
                    "index": index,
                    "file": target_file,
                }
            )
            reason_codes.append("replacement_outside_target_files")

        if scan_changed and target_file and target_file not in scan_changed:
            findings.append(
                {
                    "rule": "replacement_outside_changed_files",
                    "message": (
                        f"replacement #{index} file {target_file!r} is not in the changed file set"
                    ),
                    "index": index,
                    "file": target_file,
                }
            )
            reason_codes.append("replacement_outside_changed_files")

        proposed = str(replacement.get("proposed_symbol") or "")
        ok, reason = _replacement_is_neutral(
            proposed=proposed,
            approved_terms=approved_terms,
            forbidden_terms=forbidden_terms,
            safety_suffixes=safety_suffixes,
        )
        if not ok:
            findings.append(
                {
                    "rule": "replacement_uses_approved_neutral_vocabulary",
                    "message": (
                        f"replacement #{index} proposed_symbol {proposed!r} is not approved neutral vocabulary"
                    ),
                    "index": index,
                    "reason": reason,
                }
            )
            reason_codes.append("non_neutral_replacement")

    forbidden_intent_keys = {
        "owner_registry_changes",
        "registry_edits",
        "allowlist_changes",
        "scope_prefix_changes",
        "preflight_changes",
        "vocabulary_changes",
    }
    for key in forbidden_intent_keys:
        if key in candidate and candidate[key]:
            findings.append(
                {
                    "rule": "forbidden_intent_field",
                    "message": f"candidate must not declare {key!r}",
                    "field": key,
                }
            )
            reason_codes.append("forbidden_intent_field_present")

    forbidden_target_prefixes = (
        "contracts/governance/authority_registry.json",
        "contracts/governance/authority_shape_vocabulary.json",
        "contracts/governance/authority_neutral_vocabulary.json",
        "contracts/governance/system_registry_guard_policy.json",
        "spectrum_systems/governance/authority_shape_preflight.py",
        "scripts/run_authority_shape_preflight.py",
        "scripts/run_authority_leak_guard.py",
        "scripts/authority_leak_rules.py",
        "scripts/authority_shape_detector.py",
        "scripts/run_3ls_authority_preflight.py",
        "docs/architecture/system_registry.md",
    )
    for entry in target_set:
        if entry in forbidden_target_prefixes:
            findings.append(
                {
                    "rule": "target_protected_authority_file",
                    "message": (
                        f"candidate targets protected authority file {entry!r}; not allowed"
                    ),
                    "file": entry,
                }
            )
            reason_codes.append("target_protected_authority_file")

    status_label = "pass" if not findings else "fail"
    record = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "record_id": f"tpa-asf01-{_stable_id({'cand': candidate.get('repair_candidate_id'), 'ts': _now_iso()})}",
        "created_at": _now_iso(),
        "candidate_ref": {
            "repair_candidate_id": candidate.get("repair_candidate_id"),
            "artifact_type": candidate.get("artifact_type"),
        },
        "scan_record_ref": (
            None
            if scan_record is None
            else {
                "run_id": scan_record.get("run_id"),
                "artifact_type": scan_record.get("artifact_type"),
            }
        ),
        "status": status_label,
        "reason_codes": sorted(set(reason_codes)),
        "findings": findings,
        "non_authority_assertions": [
            "policy_check_only",
            "no_authorization_emitted",
            "no_source_mutation",
        ],
        "canonical_authority_source": "docs/architecture/system_registry.md",
    }
    return record


def main() -> int:
    args = _parse_args()
    candidate_path = Path(args.candidate).resolve()
    candidate = _load_json(candidate_path)
    vocabulary = _load_json(REPO_ROOT / args.vocabulary)
    neutral_vocab = _load_json(REPO_ROOT / args.neutral_vocabulary)
    scan_record = None
    if args.scan_record:
        scan_record = _load_json(Path(args.scan_record).resolve())

    record = validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary,
        neutral_vocab=neutral_vocab,
        scan_record=scan_record,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"status": record["status"], "findings": len(record["findings"]), "output": str(output_path.relative_to(REPO_ROOT))}, indent=2))
    return 1 if record["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
