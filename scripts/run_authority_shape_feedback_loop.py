#!/usr/bin/env python3
"""ASF-01 authority-shape feedback loop wrapper.

Optional integration step that chains the existing authority-shape preflight
infrastructure with the new ASF-01 artifacts:

1. AEX preflight observation:
   ``scripts/run_changed_scope_authority_scan.py``
   produces ``changed_scope_authority_scan_record.json``.

2. RIL interpretation packet:
   ``authority_shape_interpretation_packet.json`` is built from the scan
   record's findings, mapping each one to ``authority_shape_violation`` with
   safe-repair guidance and an explicit unsafe-repair list.

3. FRE bounded repair candidate:
   ``authority_shape_repair_candidate.json`` is built from the interpretation
   packet, proposing only neutral vocabulary replacements drawn from the
   existing authority-shape vocabulary clusters. Replacements are ``proposed``,
   never ``applied``.

4. TPA policy/trust check:
   The repair candidate is validated by
   ``scripts/validate_authority_repair_candidate.py`` and the resulting
   ``authority_repair_policy_check_record.json`` is written to disk.

Authority is NOT bypassed. CDE is the sole decision authority and SEL the sole
enforcement authority. This wrapper produces input artifacts only.

The wrapper does NOT modify source files. ``--apply`` is intentionally absent.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_SCAN = _load_module_from_path(
    "_asf01_changed_scope_scan", REPO_ROOT / "scripts" / "run_changed_scope_authority_scan.py"
)
_VALIDATE = _load_module_from_path(
    "_asf01_validate_repair", REPO_ROOT / "scripts" / "validate_authority_repair_candidate.py"
)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_id(prefix: str, payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"{prefix}-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:12]}"


def build_interpretation_packet(
    *,
    scan_record: dict[str, Any],
    scan_record_path: str,
) -> dict[str, Any]:
    findings = scan_record.get("findings") or []
    interpreted: list[dict[str, Any]] = []
    for finding in findings:
        replacements = list(finding.get("suggested_replacements") or [])
        owners = list(finding.get("canonical_owners") or [])
        cluster = finding.get("cluster") or "unknown"
        interpreted.append(
            {
                "finding_id": finding["finding_id"],
                "file": finding.get("file"),
                "line": finding.get("line"),
                "symbol": finding.get("symbol"),
                "cluster": cluster,
                "failure_class": "authority_shape_violation",
                "likely_cause": (
                    f"A non-owner surface uses {cluster}-cluster vocabulary owned by "
                    f"{', '.join(owners) or 'canonical owners'}. Replace with neutral "
                    "framing inside the changed file only."
                ),
                "affected_owner_boundary": {
                    "canonical_owners": owners,
                    "canonical_authority_source": "docs/architecture/system_registry.md",
                },
                "safe_repair_strategy": {
                    "strategy": "rename_to_neutral_vocabulary",
                    "neutral_replacements": replacements,
                    "scope": "changed_file_only",
                },
                "unsafe_repair_patterns": [
                    "modify_authority_registry",
                    "add_allowlist_exception",
                    "weaken_preflight",
                    "rename_canonical_owner_artifact",
                    "rewrite_files_outside_changed_set",
                    "change_meaning_instead_of_vocabulary",
                ],
            }
        )

    status = "interpreted" if interpreted else "no_findings"
    reason_codes = list(scan_record.get("reason_codes") or [])
    if not interpreted:
        reason_codes.append("no_findings_to_interpret")

    return {
        "artifact_type": "authority_shape_interpretation_packet",
        "schema_version": "1.0.0",
        "packet_id": _stable_id("ril-asf01", {"run": scan_record.get("run_id"), "n": len(interpreted)}),
        "created_at": _now_iso(),
        "source_scan_record": {
            "artifact_type": "changed_scope_authority_scan_record",
            "path": scan_record_path,
            "run_id": scan_record.get("run_id", "unknown"),
        },
        "interpreted_findings": interpreted,
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "non_authority_assertions": [
            "interpretation_only",
            "no_owner_registry_change",
            "no_allowlist_change",
        ],
    }


def build_repair_candidate(
    *,
    packet: dict[str, Any],
    packet_path: str,
) -> dict[str, Any]:
    target_files: set[str] = set()
    replacements: list[dict[str, Any]] = []
    for finding in packet.get("interpreted_findings") or []:
        file = finding.get("file")
        symbol = finding.get("symbol")
        line = finding.get("line", 0)
        cluster = finding.get("cluster")
        repair = finding.get("safe_repair_strategy", {}) or {}
        candidates = list(repair.get("neutral_replacements") or [])
        if not file or not symbol or not candidates:
            continue
        target_files.add(file)
        proposed = candidates[0]
        replacements.append(
            {
                "file": file,
                "line": int(line) if isinstance(line, int) else 0,
                "current_symbol": symbol,
                "proposed_symbol": proposed,
                "reason": (
                    f"{cluster} authority belongs to "
                    f"{', '.join(finding.get('affected_owner_boundary', {}).get('canonical_owners') or []) or 'canonical owners'}. "
                    "Use neutral framing in non-owner surfaces."
                ),
                "replacement_class": "vocabulary_only",
                "cluster": cluster or "unknown",
            }
        )

    return {
        "artifact_type": "authority_shape_repair_candidate",
        "schema_version": "1.0.0",
        "repair_candidate_id": _stable_id(
            "fre-asf01",
            {"packet": packet.get("packet_id"), "n": len(replacements)},
        ),
        "created_at": _now_iso(),
        "source_interpretation_packet": {
            "artifact_type": "authority_shape_interpretation_packet",
            "path": packet_path,
            "packet_id": packet.get("packet_id", "unknown"),
        },
        "target_files": sorted(target_files),
        "replacements": replacements,
        "prohibited_actions": [
            "no_allowlist_change",
            "no_owner_registry_change",
            "no_cross_file_rewrite_without_evidence",
            "no_preflight_weakening",
            "no_authority_authorization",
            "no_meaning_change",
        ],
        "status": "proposed",
        "reason_codes": ["bounded_vocabulary_repair"] if replacements else ["no_repairs_needed"],
        "non_authority_assertions": [
            "proposal_only",
            "no_application",
            "scope_changed_files",
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--changed-files", nargs="*", default=[])
    parser.add_argument(
        "--output-dir",
        default="outputs/authority_shape_preflight",
        help="Directory to write the four ASF-01 artifacts",
    )
    parser.add_argument(
        "--vocabulary",
        default="contracts/governance/authority_shape_vocabulary.json",
    )
    parser.add_argument(
        "--neutral-vocabulary",
        default="contracts/governance/authority_neutral_vocabulary.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat scan findings as block (default: warn)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    out_dir = REPO_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    changed_files = _SCAN.resolve_changed_files(
        repo_root=REPO_ROOT,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        explicit_changed_files=list(args.changed_files or []),
    )
    vocab = _SCAN.load_vocabulary(REPO_ROOT / args.vocabulary)
    scan_record = _SCAN.build_scan_record(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        strict=bool(args.strict),
    )
    scan_path = out_dir / "changed_scope_authority_scan_record.json"
    scan_path.write_text(json.dumps(scan_record, indent=2) + "\n", encoding="utf-8")

    rel_scan = scan_path.relative_to(REPO_ROOT).as_posix()
    packet = build_interpretation_packet(scan_record=scan_record, scan_record_path=rel_scan)
    packet_path = out_dir / "authority_shape_interpretation_packet.json"
    packet_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

    rel_packet = packet_path.relative_to(REPO_ROOT).as_posix()
    candidate = build_repair_candidate(packet=packet, packet_path=rel_packet)
    candidate_path = out_dir / "authority_shape_repair_candidate.json"
    candidate_path.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")

    vocabulary_payload = json.loads((REPO_ROOT / args.vocabulary).read_text(encoding="utf-8"))
    neutral_payload = json.loads((REPO_ROOT / args.neutral_vocabulary).read_text(encoding="utf-8"))
    policy_record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=scan_record,
    )
    policy_path = out_dir / "authority_repair_policy_check_record.json"
    policy_path.write_text(json.dumps(policy_record, indent=2) + "\n", encoding="utf-8")

    summary = {
        "scan_status": scan_record["status"],
        "scan_findings": scan_record["finding_count"],
        "interpretation_status": packet["status"],
        "candidate_replacements": len(candidate["replacements"]),
        "policy_status": policy_record["status"],
        "outputs": {
            "scan": rel_scan,
            "interpretation": rel_packet,
            "candidate": candidate_path.relative_to(REPO_ROOT).as_posix(),
            "policy": policy_path.relative_to(REPO_ROOT).as_posix(),
        },
    }
    print(json.dumps(summary, indent=2))
    if scan_record["status"] == "block" or policy_record["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
