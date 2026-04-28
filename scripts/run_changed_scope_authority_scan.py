#!/usr/bin/env python3
"""Early changed-scope authority vocabulary scan (ASF-01 / AEX preflight observation).

Runs the existing authority-shape vocabulary scanner against ONLY the changed
file set produced by ``--base-ref``..``--head-ref`` (or an explicit list).
Emits a ``changed_scope_authority_scan_record`` artifact that downstream RIL,
FRE and TPA stages consume.

This script is a non-owning observer:

- It does not change canonical authority ownership (declared in
  ``docs/architecture/system_registry.md``).
- It does not weaken or modify ``authority_shape_preflight``.
- It does not write to the working tree.
- It does not touch the network.
- It fails closed when the scanner cannot complete.

The artifact only carries findings, suggested replacements drawn from the
existing vocabulary, and a status (``pass``/``warn``/``block``). Authority
remains with CDE/SEL; this record is input only.
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


SCHEMA_VERSION = "1.0.0"
ARTIFACT_TYPE = "changed_scope_authority_scan_record"


class ChangedScopeAuthorityScanError(RuntimeError):
    """Raised when the changed-scope scan cannot complete deterministically."""


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ChangedScopeAuthorityScanError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_PREFLIGHT_PATH = REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py"
_CHANGED_FILES_PATH = (
    REPO_ROOT / "spectrum_systems" / "modules" / "governance" / "changed_files.py"
)

_preflight = _load_module_from_path(
    "_asf01_authority_shape_preflight_core", _PREFLIGHT_PATH
)
_changed_files = _load_module_from_path(
    "_asf01_authority_shape_changed_files", _CHANGED_FILES_PATH
)

evaluate_preflight = _preflight.evaluate_preflight
load_vocabulary = _preflight.load_vocabulary
ChangedFilesResolutionError = _changed_files.ChangedFilesResolutionError
resolve_changed_files = _changed_files.resolve_changed_files


_DEFAULT_VOCAB_PATH = "contracts/governance/authority_shape_vocabulary.json"
_DEFAULT_OUTPUT_PATH = (
    "outputs/authority_shape_preflight/changed_scope_authority_scan_record.json"
)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_run_id(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"asf01-{digest}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ASF-01 changed-scope authority scan. Runs the authority-shape "
            "vocabulary scan against changed files only and emits a "
            f"{ARTIFACT_TYPE} artifact."
        )
    )
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref")
    parser.add_argument(
        "--changed-files",
        nargs="*",
        default=[],
        help="Optional explicit changed-file list (overrides git resolution)",
    )
    parser.add_argument(
        "--vocabulary",
        default=_DEFAULT_VOCAB_PATH,
        help="Authority-shape vocabulary path",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_OUTPUT_PATH,
        help="Artifact output path",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Treat findings as block (default: warn). Fail-closed on scanner "
            "errors regardless of this flag."
        ),
    )
    return parser.parse_args()


def _guess_owning_system(rel_path: str) -> str:
    """Heuristic owning-system guess for a changed file.

    Used as a hint for RIL interpretation only; canonical ownership is the
    registry's job and is never inferred from this hint.
    """
    norm = rel_path.replace("\\", "/").lstrip("./")
    if norm.startswith("spectrum_systems/modules/runtime/met_"):
        return "MET"
    if norm.startswith("spectrum_systems/modules/met/") or norm.startswith("spectrum_systems/met/"):
        return "MET"
    if norm.startswith("spectrum_systems/modules/orchestration/"):
        return "TLC"
    if norm.startswith("spectrum_systems/modules/runtime/"):
        return "runtime_support"
    if norm.startswith("spectrum_systems/modules/governance/"):
        return "governance_support"
    if norm.startswith("docs/"):
        return "documentation"
    if norm.startswith("tests/"):
        return "tests"
    if norm.startswith("scripts/"):
        return "scripts"
    return "unknown"


def _local_context(rel_path: str, line_no: int) -> str | None:
    full = REPO_ROOT / rel_path
    if not full.is_file():
        return None
    try:
        text = full.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    lines = text.splitlines()
    if 1 <= line_no <= len(lines):
        snippet = lines[line_no - 1].strip()
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        return snippet
    return None


def _build_finding(
    *,
    finding_id: str,
    violation: dict[str, Any],
) -> dict[str, Any]:
    rel_path = str(violation.get("file", ""))
    line_no = int(violation.get("line", 0)) or 0
    return {
        "finding_id": finding_id,
        "file": rel_path,
        "line": line_no,
        "symbol": violation.get("symbol"),
        "cluster": violation.get("cluster"),
        "canonical_owners": list(violation.get("canonical_owners") or []),
        "suggested_replacements": list(violation.get("suggested_replacements") or []),
        "local_context": _local_context(rel_path, line_no),
        "owning_system_guess": _guess_owning_system(rel_path),
        "repair_scope": "changed_file_only",
        "rule": violation.get("rule") or "authority_shape_outside_owner",
        "rationale": violation.get("rationale"),
    }


def build_scan_record(
    *,
    repo_root: Path,
    changed_files: list[str],
    vocab,
    strict: bool = False,
) -> dict[str, Any]:
    """Run the scan and assemble the record artifact."""
    try:
        preflight_result = evaluate_preflight(
            repo_root=repo_root,
            changed_files=list(changed_files),
            vocab=vocab,
            mode="suggest-only",
        )
    except Exception as exc:  # fail-closed envelope
        raise ChangedScopeAuthorityScanError(
            f"authority-shape scanner failed: {exc}"
        ) from exc

    payload = preflight_result.to_dict()
    violations = payload.get("violations", []) or []

    findings: list[dict[str, Any]] = []
    for index, violation in enumerate(violations, start=1):
        findings.append(
            _build_finding(
                finding_id=f"f-{index:04d}",
                violation=violation,
            )
        )

    reason_codes: list[str] = []
    warnings: list[str] = []
    if findings:
        reason_codes.append("authority_shape_terms_in_changed_files")
        if strict:
            status = "block"
            reason_codes.append("strict_mode_block")
        else:
            status = "warn"
            warnings.append(
                "Authority-shape vocabulary detected in changed files. Treating "
                "as warn for early feedback. The binding authority_shape_preflight "
                "still gates CI."
            )
    else:
        status = "pass"

    record: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "run_id": _stable_run_id({"files": sorted(changed_files), "ts": _now_iso()}),
        "created_at": _now_iso(),
        "changed_files": sorted({f for f in changed_files if f}),
        "scanned_files": sorted(payload.get("scanned_files", []) or []),
        "skipped_files": sorted(payload.get("skipped_files", []) or []),
        "finding_count": len(findings),
        "findings": findings,
        "status": status,
        "reason_codes": reason_codes,
        "warnings": warnings,
        "non_authority_assertions": [
            "no_owner_registry_change",
            "no_allowlist_change",
            "no_source_mutation",
            "scan_only",
        ],
        "canonical_authority_source": "docs/architecture/system_registry.md",
    }
    return record


def main() -> int:
    args = _parse_args()
    try:
        changed_files = resolve_changed_files(
            repo_root=REPO_ROOT,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            explicit_changed_files=list(args.changed_files or []),
        )
    except ChangedFilesResolutionError as exc:
        raise ChangedScopeAuthorityScanError(str(exc)) from exc

    vocab_path = REPO_ROOT / args.vocabulary
    vocab = load_vocabulary(vocab_path)

    record = build_scan_record(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        strict=bool(args.strict),
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": record["status"],
        "finding_count": record["finding_count"],
        "changed_files": record["changed_files"],
        "output": str(output_path.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    if record["status"] == "block":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
