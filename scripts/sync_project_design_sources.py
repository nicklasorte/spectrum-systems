#!/usr/bin/env python3
"""Sync project-design source authority artifacts into spectrum-systems.

This script performs a narrow ingestion slice:
- discover project-design markdown/PDF/manifests in an upstream repo checkout,
- copy raw authority files into docs/source_raw/project_design,
- emit one structured JSON artifact per normalized source,
- rebuild project-design sections of source indexes,
- validate completeness with fail-closed behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "docs" / "source_raw" / "project_design"
STRUCTURED_ROOT = REPO_ROOT / "docs" / "source_structured"
INDEX_ROOT = REPO_ROOT / "docs" / "source_indexes"

REQUIRED_SOURCES = [
    "strategy_control_document",
    "canonical_harness_architecture_for_long_running_governed_ai_work",
    "agent_eval_integration_design",
    "ai_durability_strategy",
    "ai_operating_substrate",
    "context_as_infrastructure",
    "done_certification_gate_gov10",
    "durability_entropy_analysis",
    "foundation_design",
    "google_sre_mapping",
    "governed_api_adapter_design",
    "judgment_capture_reuse_system",
    "production_ai_workflow_best_practices",
    "sbge_design",
]

SOURCE_SCAN_DIRS = [
    "docs/architecture/project_design",
    "raw/strategic_sources/project_design",
    "raw/strategic_sources",
]

DOMAIN_BUCKETS = [
    "strategy",
    "foundation",
    "governance",
    "control",
    "evaluation",
    "judgment",
    "context",
    "adapter",
    "durability",
    "substrate",
    "harness",
]

KEYWORD_DOMAIN_MAP = {
    "strategy": ["strategy"],
    "foundation": ["foundation"],
    "governance": ["govern", "certification", "policy"],
    "control": ["control"],
    "evaluation": ["eval", "evaluation"],
    "judgment": ["judgment"],
    "context": ["context"],
    "adapter": ["adapter", "api"],
    "durability": ["durability", "entropy"],
    "substrate": ["substrate"],
    "harness": ["harness"],
}

MANIFEST_NAMES = {"readme.md", "source-manifest.json", "manifest.json", "index.json", "index.md", "backlog.md"}


@dataclass(frozen=True)
class CandidateFile:
    upstream_path: str
    absolute_path: Path
    file_type: str
    source_id_hint: str


def normalize_name(value: str) -> str:
    stem = Path(value).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem


def canonical_source_key(norm: str) -> str:
    aliases = {
        "mapping_google_sre_reliability_principles_to_spectrum_systems": "google_sre_mapping",
        "google_sre_mapping": "google_sre_mapping",
        "production_ready_best_practices_for_integrating_ai_models_into_automated_engineering_workflows": "production_ai_workflow_best_practices",
        "production_ai_workflow_best_practices": "production_ai_workflow_best_practices",
        "spectrum_systems_build_governance_engine_sbge_design": "sbge_design",
        "sbge_design": "sbge_design",
        "spectrum_systems_done_certification_gate_gov10_design": "done_certification_gate_gov10",
        "done_certification_gate_gov10": "done_certification_gate_gov10",
        "spectrum_systems_ai_integration_governed_api_adapter_design": "governed_api_adapter_design",
        "governed_api_adapter_design": "governed_api_adapter_design",
        "agent_eval_integration_design_spectrum_systems": "agent_eval_integration_design",
        "agent_eval_integration_design": "agent_eval_integration_design",
    }
    if norm in aliases:
        return aliases[norm]
    for required in REQUIRED_SOURCES:
        if required in norm:
            return required
    return norm


def discover_candidates(upstream_root: Path) -> list[CandidateFile]:
    candidates: list[CandidateFile] = []
    for relative in SOURCE_SCAN_DIRS:
        scan_dir = upstream_root / relative
        if not scan_dir.exists():
            continue
        for path in sorted(scan_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = str(path.relative_to(upstream_root)).replace("\\", "/")
            lower_name = path.name.lower()
            suffix = path.suffix.lower()
            if suffix not in {".md", ".pdf", ".json"}:
                continue
            if suffix == ".json" and lower_name not in MANIFEST_NAMES:
                continue
            if suffix == ".md" and lower_name in {".ds_store"}:
                continue
            file_type = "manifest" if lower_name in MANIFEST_NAMES else suffix.lstrip(".")
            candidates.append(
                CandidateFile(
                    upstream_path=rel_path,
                    absolute_path=path,
                    file_type=file_type,
                    source_id_hint=canonical_source_key(normalize_name(path.name)),
                )
            )
    return candidates


def group_candidates(candidates: list[CandidateFile]) -> dict[str, list[CandidateFile]]:
    grouped: dict[str, list[CandidateFile]] = {}
    for item in candidates:
        grouped.setdefault(item.source_id_hint, []).append(item)
    return grouped


def _get_upstream_ref(upstream_root: Path) -> str | None:
    if not (upstream_root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(upstream_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.SubprocessError:
        return None
    return result.stdout.strip() or None


def _copy_raw_file(source: CandidateFile, source_key: str) -> str:
    RAW_ROOT.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.absolute_path.read_bytes()).hexdigest()[:10]
    ext = source.absolute_path.suffix.lower()
    local_name = f"{source_key}__{digest}{ext}"
    destination = RAW_ROOT / local_name
    shutil.copy2(source.absolute_path, destination)
    return str(destination.relative_to(REPO_ROOT)).replace("\\", "/")


def _extract_pdf_text(path: Path) -> str:
    data = path.read_bytes()
    fragments = re.findall(rb"[ -~]{20,}", data)
    lines = [frag.decode("latin-1", errors="ignore").strip() for frag in fragments]
    deduped: list[str] = []
    for line in lines:
        if line and line not in deduped:
            deduped.append(line)
        if len(deduped) >= 60:
            break
    return "\n".join(deduped)


def _extract_md_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return text[:8000]


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        clean = line.strip().lstrip("#").strip()
        if len(clean) >= 6:
            return clean[:160]
    return fallback.replace("_", " ").title()


def _summary_from_text(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " ".join(lines[:2])[:400] if lines else "Summary unavailable from source content."


def _extract_obligations(text: str) -> list[str]:
    obligations: list[str] = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        lower = l.lower()
        if any(token in lower for token in ["must", "shall", "require", "fail closed"]):
            obligations.append(l[:220])
        if len(obligations) >= 3:
            break
    return obligations


def _component_tags(source_key: str, text: str) -> list[str]:
    blob = f"{source_key} {text}".lower()
    tags: list[str] = []
    for bucket, keywords in KEYWORD_DOMAIN_MAP.items():
        if any(keyword in blob for keyword in keywords):
            tags.append(bucket)
    if not tags:
        tags = ["governance"]
    return sorted(set(tags))


def build_structured_record(
    source_key: str,
    files: list[CandidateFile],
    upstream_repo: str,
    upstream_ref: str | None,
    ingestion_time: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw_paths: list[str] = []
    upstream_paths: list[str] = []
    combined_text_parts: list[str] = []
    file_types: set[str] = set()

    for item in files:
        upstream_paths.append(item.upstream_path)
        file_types.add(item.file_type)
        raw_paths.append(_copy_raw_file(item, source_key))
        if item.file_type == "md":
            combined_text_parts.append(_extract_md_text(item.absolute_path))
        elif item.file_type == "pdf":
            combined_text_parts.append(_extract_pdf_text(item.absolute_path))

    combined_text = "\n".join(combined_text_parts)
    title = _title_from_text(combined_text, source_key)
    summary = _summary_from_text(combined_text)
    obligation_lines = _extract_obligations(combined_text)
    component_tags = _component_tags(source_key, combined_text)
    preferred = next((p for p in raw_paths if p.endswith(".md")), raw_paths[0] if raw_paths else "")

    source_id = f"SRC-PROJECT-DESIGN-{source_key.upper().replace('-', '_')}"
    record = {
        "schema_version": "1.0.0",
        "source_id": source_id,
        "title": title,
        "normalized_name": source_key,
        "upstream_repo": upstream_repo,
        "upstream_paths": sorted(set(upstream_paths)),
        "upstream_ref": upstream_ref,
        "local_raw_paths": sorted(set(raw_paths)),
        "preferred_readable_source": preferred,
        "file_types_present": sorted(file_types),
        "document_type": "project_design",
        "summary": summary,
        "key_directives_or_obligations": obligation_lines,
        "component_tags": component_tags,
        "canonical_status": "available",
        "ingested_at": ingestion_time,
    }

    obligations = []
    for idx, line in enumerate(obligation_lines, start=1):
        obligations.append(
            {
                "obligation_id": f"OBL-{source_key.upper().replace('-', '_')}-{idx:02d}",
                "source_id": source_id,
                "source_path": preferred,
                "directive": line,
                "conservative_extraction": True,
            }
        )
    return record, obligations


def build_missing_record(source_key: str, upstream_repo: str, ingestion_time: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_id = f"SRC-PROJECT-DESIGN-{source_key.upper()}"
    record = {
        "schema_version": "1.0.0",
        "source_id": source_id,
        "title": source_key.replace("_", " ").title(),
        "normalized_name": source_key,
        "upstream_repo": upstream_repo,
        "upstream_paths": [],
        "upstream_ref": None,
        "local_raw_paths": [],
        "preferred_readable_source": "",
        "file_types_present": [],
        "document_type": "project_design",
        "summary": "Required source not discovered in upstream scan.",
        "key_directives_or_obligations": [],
        "component_tags": _component_tags(source_key, source_key),
        "canonical_status": "missing_upstream",
        "ingested_at": ingestion_time,
    }
    return record, []


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_indexes(records: list[dict[str, Any]], obligations: list[dict[str, Any]]) -> None:
    required_set = set(REQUIRED_SOURCES)
    inventory_rows = []
    component_map = {bucket: [] for bucket in DOMAIN_BUCKETS}
    for row in sorted(records, key=lambda r: r["source_id"]):
        normalized = row["normalized_name"]
        structured_path = f"docs/source_structured/project_design_{normalized}.json"
        completeness = row["canonical_status"] == "available"
        inventory_rows.append(
            {
                "source_id": row["source_id"],
                "normalized_name": normalized,
                "title": row["title"],
                "required": normalized in required_set,
                "completeness_status": "complete" if completeness else "missing",
                "upstream_repo": row["upstream_repo"],
                "upstream_ref": row["upstream_ref"],
                "upstream_paths": row["upstream_paths"],
                "local_raw_paths": row["local_raw_paths"],
                "structured_path": structured_path,
            }
        )
        for tag in row["component_tags"]:
            if tag in component_map:
                component_map[tag].append(row["source_id"])

    write_json(
        INDEX_ROOT / "source_inventory.json",
        {"index_name": "source_inventory", "schema_version": "2.0.0", "sources": inventory_rows},
    )
    write_json(
        INDEX_ROOT / "component_source_map.json",
        {
            "index_name": "component_source_map",
            "schema_version": "2.0.0",
            "domains": [{"domain": d, "source_ids": sorted(set(ids))} for d, ids in component_map.items()],
        },
    )
    write_json(
        INDEX_ROOT / "obligation_index.json",
        {"index_name": "obligation_index", "schema_version": "2.0.0", "obligations": sorted(obligations, key=lambda o: o["obligation_id"])},
    )


def validate_completeness(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_name = {row["normalized_name"]: row for row in records}
    for required in REQUIRED_SOURCES:
        row = by_name.get(required)
        if row is None:
            errors.append(f"missing structured entry for required source: {required}")
            continue
        if row["canonical_status"] != "available":
            errors.append(f"required source unavailable: {required}")
            continue
        for local_raw in row["local_raw_paths"]:
            if not (REPO_ROOT / local_raw).exists():
                errors.append(f"missing local raw path for required source {required}: {local_raw}")

    for row in records:
        structured_path = STRUCTURED_ROOT / f"project_design_{row['normalized_name']}.json"
        if not structured_path.exists():
            errors.append(f"missing structured file: {structured_path}")

    return errors


def run_sync(upstream_root: Path, upstream_repo: str, allow_missing_required: bool, validate_only: bool) -> int:
    ingestion_time = datetime.now(timezone.utc).isoformat()
    upstream_ref = _get_upstream_ref(upstream_root)
    discovered = discover_candidates(upstream_root)
    grouped = group_candidates(discovered)

    records: list[dict[str, Any]] = []
    obligations: list[dict[str, Any]] = []

    discovered_source_keys = {
        key for key, files in grouped.items() if any(item.file_type in {"md", "pdf"} for item in files)
    }
    target_sources = sorted(set(REQUIRED_SOURCES) | discovered_source_keys)
    for source_key in target_sources:
        files = grouped.get(source_key, [])
        if files:
            record, rec_obligations = build_structured_record(source_key, files, upstream_repo, upstream_ref, ingestion_time)
        else:
            record, rec_obligations = build_missing_record(source_key, upstream_repo, ingestion_time)
        records.append(record)
        obligations.extend(rec_obligations)

    if not validate_only:
        for row in records:
            path = STRUCTURED_ROOT / f"project_design_{row['normalized_name']}.json"
            write_json(path, row)
        update_indexes(records, obligations)

    failures = validate_completeness(records)
    if failures and not allow_missing_required:
        raise RuntimeError("Completeness validation failed (fail-closed):\n - " + "\n - ".join(failures))

    result = {
        "upstream_root": str(upstream_root),
        "upstream_repo": upstream_repo,
        "upstream_ref": upstream_ref,
        "discovered_count": len(discovered),
        "grouped_sources": sorted(grouped.keys()),
        "required_sources": REQUIRED_SOURCES,
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-root", type=Path, required=True, help="Path to local checkout of spectrum-data-lake")
    parser.add_argument("--upstream-repo", default="nicklasorte/spectrum-data-lake")
    parser.add_argument("--allow-missing-required", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if not args.upstream_root.exists():
        raise SystemExit(f"upstream root does not exist: {args.upstream_root}")

    try:
        return run_sync(
            upstream_root=args.upstream_root,
            upstream_repo=args.upstream_repo,
            allow_missing_required=args.allow_missing_required,
            validate_only=args.validate_only,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
