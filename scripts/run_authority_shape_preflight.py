#!/usr/bin/env python3
"""Static authority-shape preflight scanner for changed files (AGS-001).

This script is a static, non-owning scanner. It detects authority-shaped
identifiers in changed files and writes a diagnostic artifact. Canonical
ownership is declared in ``docs/architecture/system_registry.md`` and is
unchanged by this scanner.

Two diagnostic modes are supported:

* ``--suggest-only`` (default): report authority-shape diagnostics with
  file/line/symbol, authority cluster, canonical owner, and suggested
  replacements.
* ``--apply-safe-renames``: apply unambiguous, owner-safe renames using the
  contracted ``safe_rename_pairs`` table and re-scan. Guard scripts and
  canonical-owner files are protected from auto-remediation.

The script returns a failing diagnostic status (non-zero exit) when
authority-shaped leaks are detected. Downstream canonical owners and the
existing fail-closed checks consume this diagnostic; this scanner does not
own gating or perform any enforcement action.

Dependency-light by design: the scanner must work on the minimal CI surface
that is exercised before contracts/jsonschema dependencies are installed. We
therefore avoid the package-level ``spectrum_systems.governance`` ``__init__``
(which eagerly imports ``contract_impact`` and transitively requires
``jsonschema``) and load the preflight implementation by file path. The module
itself uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Load a stdlib-only module without triggering its package ``__init__``.

    The preflight intentionally bypasses ``spectrum_systems.governance`` package
    initialization — that ``__init__`` eagerly imports ``contract_impact``,
    which depends on ``jsonschema``. Loading by file path keeps the gate
    runnable on minimal CI surfaces.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_PREFLIGHT_PATH = REPO_ROOT / "spectrum_systems" / "governance" / "authority_shape_preflight.py"
_CHANGED_FILES_PATH = (
    REPO_ROOT / "spectrum_systems" / "modules" / "governance" / "changed_files.py"
)

_preflight = _load_module_from_path(
    "_authority_shape_preflight_core", _PREFLIGHT_PATH
)
_changed_files = _load_module_from_path(
    "_authority_shape_changed_files", _CHANGED_FILES_PATH
)

AuthorityShapePreflightError = _preflight.AuthorityShapePreflightError
evaluate_preflight = _preflight.evaluate_preflight
load_vocabulary = _preflight.load_vocabulary
ChangedFilesResolutionError = _changed_files.ChangedFilesResolutionError
resolve_changed_files = _changed_files.resolve_changed_files
REQUIRED_EVAL_IDS = (
    "authority_shape_contract_lint",
    "authority_shape_review_language_lint",
    "authority_owner_registry_consistency",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authority-shape preflight (AGS-001)")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref for changed-file resolution")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref for changed-file resolution")
    parser.add_argument("--changed-files", nargs="*", default=[], help="Explicit changed files")
    parser.add_argument(
        "--vocabulary",
        default="contracts/governance/authority_shape_vocabulary.json",
        help="Authority-shape vocabulary path",
    )
    parser.add_argument(
        "--output",
        default="outputs/authority_shape_preflight/authority_shape_preflight_result.json",
        help="Output artifact path",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--suggest-only",
        dest="mode",
        action="store_const",
        const="suggest-only",
        help="Report violations and suggested replacements (default)",
    )
    mode_group.add_argument(
        "--apply-safe-renames",
        dest="mode",
        action="store_const",
        const="apply-safe-renames",
        help="Apply unambiguous, owner-safe renames before re-checking",
    )
    parser.set_defaults(mode="suggest-only")
    return parser.parse_args()


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
        raise AuthorityShapePreflightError(str(exc)) from exc

    vocab_path = REPO_ROOT / args.vocabulary
    vocab = load_vocabulary(vocab_path)

    result = evaluate_preflight(
        repo_root=REPO_ROOT,
        changed_files=changed_files,
        vocab=vocab,
        mode=args.mode,
    )

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    owner_registry_path = REPO_ROOT / "contracts" / "governance" / "authority_owner_registry.json"
    eval_status = {
        "authority_shape_contract_lint": "pass" if not any(str(v.get("rule", "")).startswith("schema_") for v in payload.get("violations", [])) else "fail",
        "authority_shape_review_language_lint": "pass" if not any(str(v.get("rule", "")) == "review_language_unqualified_authority_claim" for v in payload.get("violations", [])) else "fail",
        "authority_owner_registry_consistency": "pass" if owner_registry_path.is_file() else "missing",
    }
    missing_or_failed = sorted(eval_id for eval_id in REQUIRED_EVAL_IDS if eval_status.get(eval_id) != "pass")
    payload["required_evals"] = {"statuses": eval_status, "missing_or_failed": missing_or_failed}
    if missing_or_failed:
        payload["status"] = "fail"
        payload.setdefault("summary", {})["required_eval_failures"] = len(missing_or_failed)
    if payload.get("violations"):
        first = payload["violations"][0]
        subsystem_counts: dict[str, int] = {}
        cluster_counts: dict[str, int] = {}
        owner_counts: dict[str, int] = {}
        replacement_usage: dict[str, int] = {}
        for item in payload["violations"]:
            file_path = str(item.get("file") or "")
            subsystem = file_path.split("/", 2)[1] if file_path.startswith("spectrum_systems/") and len(file_path.split("/")) > 1 else file_path.split("/", 1)[0]
            subsystem_counts[subsystem] = subsystem_counts.get(subsystem, 0) + 1
            cluster = str(item.get("cluster") or "unknown")
            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1
            for owner in item.get("canonical_owners", []) or []:
                owner_counts[str(owner)] = owner_counts.get(str(owner), 0) + 1
            for suggestion in item.get("suggested_replacements", []) or []:
                replacement_usage[str(suggestion)] = replacement_usage.get(str(suggestion), 0) + 1
        repeated = sorted([name for name, count in subsystem_counts.items() if count >= 3])
        payload["failure_packet"] = {
            "failure_class": "policy_mismatch",
            "subtype": "authority_boundary_drift",
            "violating_file": first.get("file"),
            "line": first.get("line"),
            "symbol": first.get("symbol"),
            "cluster": first.get("cluster"),
            "canonical_owners": first.get("canonical_owners", []),
            "suggested_neutral_terms": first.get("suggested_replacements", []),
            "first_failure_boundary": first.get("first_failure_boundary", "authority_shape_preflight"),
        }
        payload["control_mapping"] = {
            "unauthorized_authority_terms": "BLOCK",
            "ambiguous_review_claims": "BLOCK",
            "repeated_violation_action": "FREEZE" if repeated else "NONE",
            "freeze_subsystems": repeated,
        }
        payload["observability"] = {
            "violation_count_by_authority_cluster": cluster_counts,
            "violation_count_by_owning_subsystem": owner_counts,
            "first_failing_file": first.get("file"),
            "recurrence_by_pr": {
                "pr_ref": f"{args.base_ref}..{args.head_ref}",
                "violation_count": len(payload["violations"]),
                "subsystem_violation_count": subsystem_counts,
            },
            "suggested_replacement_usage": replacement_usage,
        }
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    summary = {
        "status": payload["status"],
        "mode": payload["mode"],
        "changed_files": changed_files,
        "violation_count": payload["summary"]["violation_count"],
        "applied_rename_count": payload["summary"]["applied_rename_count"],
        "refused_rename_count": payload["summary"]["refused_rename_count"],
        "output": str(output_path),
    }
    if payload["violations"]:
        summary["first_violations"] = [
            {
                "file": v["file"],
                "line": v["line"],
                "symbol": v["symbol"],
                "cluster": v["cluster"],
                "canonical_owners": v["canonical_owners"],
                "suggested_replacements": v["suggested_replacements"],
            }
            for v in payload["violations"][:10]
        ]
    print(json.dumps(summary, indent=2))
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
