"""Deterministic, fail-closed contract impact analysis for governed schema changes."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from spectrum_systems.contracts import validate_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYZER_VERSION = "1.0.0"


class ContractImpactAnalysisError(ValueError):
    """Raised when contract impact analysis cannot be completed deterministically."""


@dataclass(frozen=True)
class AnalysisInput:
    changed_contract_paths: tuple[str, ...]
    changed_example_paths: tuple[str, ...]
    standards_manifest_path: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_show_json(repo_root: Path, ref: str, relative_path: str) -> dict[str, Any] | None:
    cmd = ["git", "-C", str(repo_root), "show", f"{ref}:{relative_path}"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout)


def _norm_type(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(sorted(str(item) for item in value))
    return tuple()


def _allows_null(schema: dict[str, Any]) -> bool:
    types = _norm_type(schema.get("type"))
    return "null" in types


def _detect_schema_risks(old_schema: dict[str, Any], new_schema: dict[str, Any]) -> dict[str, list[str]]:
    old_required = set(old_schema.get("required", []))
    new_required = set(new_schema.get("required", []))

    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})

    required_added = sorted(new_required - old_required)
    required_removed = sorted(old_required - new_required)

    removed_properties = sorted(set(old_props) - set(new_props))
    type_changes: list[str] = []
    enum_narrowing: list[str] = []
    nullability_tightening: list[str] = []

    for name in sorted(set(old_props) & set(new_props)):
        old_prop = old_props[name]
        new_prop = new_props[name]

        if _norm_type(old_prop.get("type")) != _norm_type(new_prop.get("type")):
            type_changes.append(name)

        old_enum = old_prop.get("enum")
        new_enum = new_prop.get("enum")
        if isinstance(old_enum, list) and isinstance(new_enum, list):
            removed_values = sorted(set(old_enum) - set(new_enum))
            if removed_values:
                enum_narrowing.append(name)

        if _allows_null(old_prop) and not _allows_null(new_prop):
            nullability_tightening.append(name)

    return {
        "required_added": required_added,
        "required_removed": required_removed,
        "removed_properties": removed_properties,
        "type_changes": type_changes,
        "enum_narrowing": enum_narrowing,
        "nullability_tightening": nullability_tightening,
    }


def _collect_impacted_paths(repo_root: Path, changed_contract_paths: Iterable[str]) -> dict[str, list[str]]:
    contract_names = {
        Path(path).name.replace(".schema.json", "")
        for path in changed_contract_paths
        if path.endswith(".schema.json")
    }
    search_tokens = sorted(contract_names | set(changed_contract_paths))

    impacted = {
        "examples": set(),
        "tests": set(),
        "runtime": set(),
        "scripts": set(),
        "consumers": set(),
        "manifest_refs": set(),
    }

    for file_path in sorted(repo_root.rglob("*")):
        if not file_path.is_file():
            continue
        rel = str(file_path.relative_to(repo_root))
        if rel.startswith(".git/"):
            continue
        if file_path.suffix not in {".py", ".json", ".md", ".yaml", ".yml", ".txt", ".sh"}:
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if not any(token in content for token in search_tokens):
            continue

        if rel.startswith("contracts/examples/"):
            impacted["examples"].add(rel)
        elif rel.startswith("tests/"):
            impacted["tests"].add(rel)
        elif rel.startswith("scripts/"):
            impacted["scripts"].add(rel)
        elif rel.startswith("spectrum_systems/"):
            impacted["runtime"].add(rel)
        else:
            impacted["consumers"].add(rel)

        if rel == "contracts/standards-manifest.json":
            impacted["manifest_refs"].add(rel)

    return {key: sorted(values) for key, values in impacted.items()}


def _classify_compatibility(risk_rows: list[dict[str, Any]], has_impacted_usage: bool, unresolved: bool) -> tuple[str, bool, list[str], list[str], bool]:
    reasons: list[str] = []
    remediations: list[str] = []

    breaking_detected = False
    caution_detected = False

    for row in risk_rows:
        contract_path = row["contract_path"]
        risks = row["risks"]
        if risks["required_added"]:
            caution_detected = True
            breaking_detected = True
            reasons.append(f"new required properties added in {contract_path}: {', '.join(risks['required_added'])}")
            remediations.append(f"update downstream examples/consumers for new required properties in {contract_path}")
        if risks["type_changes"]:
            breaking_detected = True
            reasons.append(f"property type changes in {contract_path}: {', '.join(risks['type_changes'])}")
        if risks["enum_narrowing"]:
            breaking_detected = True
            reasons.append(f"enum narrowing in {contract_path}: {', '.join(risks['enum_narrowing'])}")
        if risks["nullability_tightening"]:
            breaking_detected = True
            reasons.append(f"nullability tightened in {contract_path}: {', '.join(risks['nullability_tightening'])}")
        if risks["required_removed"] or risks["removed_properties"]:
            caution_detected = True
            reasons.append(
                f"required/property removals in {contract_path}: "
                f"required_removed={','.join(risks['required_removed']) or '-'} "
                f"removed_properties={','.join(risks['removed_properties']) or '-'}"
            )

    if unresolved:
        reasons.append("analysis unresolved for one or more changed contracts")
        remediations.append("provide valid baseline schema and contract references so compatibility can be determined")
        return "indeterminate", True, sorted(set(reasons)), sorted(set(remediations)), False

    if breaking_detected and has_impacted_usage:
        remediations.append("update impacted runtime/tests/scripts/examples before PQX execution")

    if breaking_detected:
        return "breaking", True, sorted(set(reasons)), sorted(set(remediations)), False
    if caution_detected:
        return "caution", False, sorted(set(reasons)), sorted(set(remediations)), True
    return "compatible", False, [], [], True


def analyze_contract_impact(
    *,
    repo_root: Path,
    changed_contract_paths: list[str],
    changed_example_paths: list[str] | None = None,
    standards_manifest_path: str = "contracts/standards-manifest.json",
    baseline_ref: str = "HEAD",
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not changed_contract_paths:
        raise ContractImpactAnalysisError("at least one changed contract path is required")

    normalized_contract_paths = sorted(set(changed_contract_paths))
    normalized_example_paths = sorted(set(changed_example_paths or []))

    risk_rows: list[dict[str, Any]] = []
    unresolved = False
    evidence_refs: list[str] = []

    for rel_path in normalized_contract_paths:
        schema_path = repo_root / rel_path
        if not schema_path.exists():
            unresolved = True
            evidence_refs.append(f"missing_changed_contract:{rel_path}")
            continue

        try:
            new_schema = _read_json(schema_path)
        except json.JSONDecodeError:
            unresolved = True
            evidence_refs.append(f"invalid_json:{rel_path}")
            continue

        old_schema = _git_show_json(repo_root, baseline_ref, rel_path)
        if old_schema is None:
            unresolved = True
            evidence_refs.append(f"missing_baseline:{baseline_ref}:{rel_path}")
            continue

        risks = _detect_schema_risks(old_schema, new_schema)
        risk_rows.append({"contract_path": rel_path, "risks": risks})

    impacted = _collect_impacted_paths(repo_root, normalized_contract_paths)
    has_impacted_usage = any(
        impacted[key] for key in ("examples", "tests", "runtime", "scripts", "consumers")
    )

    compatibility_class, blocking, blocking_reasons, required_remediations, safe_to_execute = _classify_compatibility(
        risk_rows, has_impacted_usage, unresolved
    )

    identity = AnalysisInput(
        changed_contract_paths=tuple(normalized_contract_paths),
        changed_example_paths=tuple(normalized_example_paths),
        standards_manifest_path=standards_manifest_path,
    )
    impact_id = hashlib.sha256(json.dumps(identity.__dict__, sort_keys=True).encode("utf-8")).hexdigest()

    artifact = {
        "artifact_type": "contract_impact_artifact",
        "schema_version": "1.0.0",
        "impact_id": impact_id,
        "generated_at": generated_at or _utc_now(),
        "analyzer_version": ANALYZER_VERSION,
        "standards_manifest_path": standards_manifest_path,
        "changed_contract_paths": normalized_contract_paths,
        "changed_example_paths": normalized_example_paths,
        "impacted_consumer_paths": impacted["consumers"],
        "impacted_test_paths": impacted["tests"],
        "impacted_runtime_paths": impacted["runtime"],
        "impacted_script_paths": impacted["scripts"],
        "compatibility_class": compatibility_class,
        "blocking": blocking,
        "blocking_reasons": blocking_reasons,
        "required_remediations": required_remediations,
        "safe_to_execute": safe_to_execute,
        "evidence_refs": sorted(set(evidence_refs + impacted["manifest_refs"] + impacted["examples"])),
        "summary": (
            f"compatibility={compatibility_class}; changed_contracts={len(normalized_contract_paths)}; "
            f"impacted_paths={sum(len(impacted[key]) for key in ('consumers', 'tests', 'runtime', 'scripts'))}"
        ),
    }

    validate_artifact(artifact, "contract_impact_artifact")
    return artifact


def write_contract_impact_artifact(artifact: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return output_path
