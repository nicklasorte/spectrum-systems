#!/usr/bin/env python3
"""Sync project-design source authority artifacts into spectrum-systems."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_CANONICAL_REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = _CANONICAL_REPO_ROOT
RAW_ROOT = REPO_ROOT / "docs" / "source_raw" / "project_design"
STRUCTURED_ROOT = REPO_ROOT / "docs" / "source_structured"
INDEX_ROOT = REPO_ROOT / "docs" / "source_indexes"
TPA_POLICY_PATH = REPO_ROOT / "config" / "policy" / "tpa_scope_policy.json"
_WRITE_OVERRIDE_ENV = "SPECTRUM_ALLOW_SOURCE_AUTHORITY_WRITE"

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

DOMAIN_BUCKETS = ["strategy", "foundation", "governance", "control", "evaluation", "judgment", "context", "adapter", "durability", "substrate", "harness"]

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
    _assert_canonical_write_allowed(destination)
    shutil.copy2(source.absolute_path, destination)
    return str(destination.relative_to(REPO_ROOT)).replace("\\", "/")


def _assert_canonical_write_allowed(path: Path) -> None:
    canonical_roots = (
        (_CANONICAL_REPO_ROOT / "docs" / "source_indexes").resolve(),
        (_CANONICAL_REPO_ROOT / "docs" / "source_raw").resolve(),
        (_CANONICAL_REPO_ROOT / "docs" / "source_structured").resolve(),
    )
    path_resolved = path.resolve()
    if any(path_resolved.is_relative_to(root) for root in canonical_roots):
        if os.getenv(_WRITE_OVERRIDE_ENV) != "1":
            raise PermissionError(
                f"Refusing to mutate canonical source authority path without {_WRITE_OVERRIDE_ENV}=1: {path}"
            )


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


def _to_component_id(tags: list[str]) -> str:
    if not tags:
        return "COMP-PROJECT-DESIGN-GOVERNANCE"
    return f"COMP-PROJECT-DESIGN-{tags[0].upper().replace('-', '_')}"


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
    pdf_raw = next((p for p in raw_paths if p.endswith(".pdf")), f"docs/source_raw/project_design/{source_key}.pdf")
    source_status = "available" if any(p.endswith(".pdf") for p in raw_paths) else "missing"

    record = {
        "schema_version": "1.0.0",
        "source_document": {
            "source_id": source_id,
            "title": title,
            "file_path": pdf_raw,
            "status": source_status,
            "notes": (
                f"project_design sync from {upstream_repo}; upstream_ref={upstream_ref or 'unavailable'}; "
                f"upstream_paths={sorted(set(upstream_paths))}; local_raw_paths={sorted(set(raw_paths))}; "
                f"preferred_readable_source={preferred}; file_types_present={sorted(file_types)}; "
                f"ingested_at={ingestion_time}; summary={summary}"
            ),
        },
        "extraction": {
            "key_components": [{"id": f"KEY-{source_key.upper()}-01", "statement": summary}],
            "architectural_invariants": [{"id": f"INV-{source_key.upper()}-01", "statement": "Source obligations remain traceable to structured rows."}],
            "authority_boundaries": [{"id": f"AUTH-{source_key.upper()}-01", "statement": "Raw inputs remain authority inputs; structured rows are derived governance artifacts."}],
            "artifact_families": [{"id": f"ART-{source_key.upper()}-01", "statement": "This source contributes to source inventory, obligation index, and component map."}],
            "required_schemas": [{"id": f"SCHEMA-{source_key.upper()}-01", "statement": "Structured source artifact must satisfy source_design_extraction schema."}],
            "sequencing_constraints": [{"id": f"SEQ-{source_key.upper()}-01", "statement": "Index and digest refresh must run after structured-source sync."}],
            "failure_modes": [{"id": f"FAIL-{source_key.upper()}-01", "statement": "Missing required source evidence blocks governance progression."}],
            "fail_closed_requirements": [{"id": f"FC-{source_key.upper()}-01", "statement": "Completeness validation fails closed for missing required sources."}],
            "replayability_requirements": [{"id": f"REPLAY-{source_key.upper()}-01", "statement": "Repeat sync over unchanged inputs produces stable raw filenames and deterministic indexes."}],
            "observability_requirements": [{"id": f"OBS-{source_key.upper()}-01", "statement": "Inventory/index entries must expose source availability and obligation linkage."}],
            "certification_requirements": [{"id": f"CERT-{source_key.upper()}-01", "statement": "Downstream governance consumes refreshed source indexes and matching policy digests."}],
            "sre_alignment": [{"id": f"SRE-{source_key.upper()}-01", "statement": "Fail-closed authority checks reduce silent drift and stale-policy risk."}],
            "explicit_non_goals": [{"id": f"NG-{source_key.upper()}-01", "statement": "This ingestion slice does not implement roadmap compilation or execution automation."}],
            "roadmap_implications": [{"id": f"RM-{source_key.upper()}-01", "statement": "Roadmap planning must reference refreshed source authority indexes."}],
        },
        "source_traceability_rows": [],
    }

    obligations = []
    component_id = _to_component_id(component_tags)
    for idx, line in enumerate(obligation_lines, start=1):
        obligation_id = f"OBL-{source_key.upper().replace('-', '_')}-{idx:02d}"
        trace_row = {
            "trace_id": f"TRACE-{source_key.upper().replace('-', '_')}-{idx:03d}",
            "obligation_id": obligation_id,
            "component_id": component_id,
            "obligation_statement": line,
            "source_section": "first_pass_extraction",
            "source_excerpt": line,
        }
        record["source_traceability_rows"].append(trace_row)
        obligations.append(trace_row)

    if not record["source_traceability_rows"]:
        placeholder = {
            "trace_id": f"TRACE-{source_key.upper().replace('-', '_')}-000",
            "obligation_id": f"OBL-{source_key.upper().replace('-', '_')}-PLACEHOLDER",
            "component_id": component_id,
            "obligation_statement": "No explicit modal directive extracted; preserve source for governed retrieve.",
            "source_section": "placeholder",
            "source_excerpt": "",
        }
        record["source_traceability_rows"].append(placeholder)
        obligations.append(placeholder)

    return record, obligations


def build_missing_record(source_key: str, upstream_repo: str, ingestion_time: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_id = f"SRC-PROJECT-DESIGN-{source_key.upper()}"
    component_id = _to_component_id(_component_tags(source_key, source_key))
    record = {
        "schema_version": "1.0.0",
        "source_document": {
            "source_id": source_id,
            "title": source_key.replace("_", " ").title(),
            "file_path": f"docs/source_raw/project_design/{source_key}.pdf",
            "status": "missing",
            "notes": f"Required source missing during sync from {upstream_repo}; ingested_at={ingestion_time}",
        },
        "extraction": {
            "key_components": [{"id": f"KEY-{source_key.upper()}-01", "statement": "Missing source placeholder."}],
            "architectural_invariants": [{"id": f"INV-{source_key.upper()}-01", "statement": "Fail closed on missing required source."}],
            "authority_boundaries": [{"id": f"AUTH-{source_key.upper()}-01", "statement": "Do not infer obligations beyond explicit placeholders."}],
            "artifact_families": [{"id": f"ART-{source_key.upper()}-01", "statement": "Placeholder source authority artifact."}],
            "required_schemas": [{"id": f"SCHEMA-{source_key.upper()}-01", "statement": "Artifact conforms to source schema despite missing upstream source."}],
            "sequencing_constraints": [{"id": f"SEQ-{source_key.upper()}-01", "statement": "Missing source must block downstream progression."}],
            "failure_modes": [{"id": f"FAIL-{source_key.upper()}-01", "statement": "Required source unavailable."}],
            "fail_closed_requirements": [{"id": f"FC-{source_key.upper()}-01", "statement": "Validation fails closed for this missing source."}],
            "replayability_requirements": [{"id": f"REPLAY-{source_key.upper()}-01", "statement": "Missing placeholder persists deterministically until source is available."}],
            "observability_requirements": [{"id": f"OBS-{source_key.upper()}-01", "statement": "Missing status must be visible in inventory."}],
            "certification_requirements": [{"id": f"CERT-{source_key.upper()}-01", "statement": "Certification cannot proceed with missing required sources."}],
            "sre_alignment": [{"id": f"SRE-{source_key.upper()}-01", "statement": "Missing source detection is explicit and non-silent."}],
            "explicit_non_goals": [{"id": f"NG-{source_key.upper()}-01", "statement": "No fabricated source content."}],
            "roadmap_implications": [{"id": f"RM-{source_key.upper()}-01", "statement": "Roadmap operations remain blocked until source is ingested."}],
        },
        "source_traceability_rows": [
            {
                "trace_id": f"TRACE-{source_key.upper()}-000",
                "obligation_id": f"OBL-{source_key.upper()}-MISSING",
                "component_id": component_id,
                "obligation_statement": "Required source is missing; fail closed.",
                "source_section": "missing_source",
                "source_excerpt": "",
            }
        ],
    }
    return record, record["source_traceability_rows"]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    _assert_canonical_write_allowed(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def refresh_tpa_scope_policy_digests(*, refresh_id: str | None = None, refreshed_at: str | None = None) -> None:
    if not TPA_POLICY_PATH.exists():
        return
    payload = json.loads(TPA_POLICY_PATH.read_text(encoding="utf-8"))
    refresh = payload.get("source_authority_refresh")
    if not isinstance(refresh, dict):
        return
    refresh["source_inventory_digest_sha256"] = hashlib.sha256((INDEX_ROOT / "source_inventory.json").read_bytes()).hexdigest()
    refresh["obligation_index_digest_sha256"] = hashlib.sha256((INDEX_ROOT / "obligation_index.json").read_bytes()).hexdigest()
    refresh["component_source_map_digest_sha256"] = hashlib.sha256((INDEX_ROOT / "component_source_map.json").read_bytes()).hexdigest()
    if refresh_id:
        refresh["refresh_id"] = refresh_id
    if refreshed_at:
        refresh["refreshed_at"] = refreshed_at
    TPA_POLICY_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def update_indexes(records: list[dict[str, Any]], obligations: list[dict[str, Any]]) -> None:
    inventory_rows = []
    component_map: dict[str, dict[str, set[str]]] = {}
    obligation_rows = []
    for row in sorted(records, key=lambda r: r["source_document"]["source_id"]):
        document = row["source_document"]
        source_id = document["source_id"]
        normalized = source_id.replace("SRC-PROJECT-DESIGN-", "").lower()
        structured_path = f"docs/source_structured/project_design_{normalized}.json"
        inventory_rows.append(
            {
                "source_id": source_id,
                "title": document["title"],
                "file_path": document["file_path"],
                "status": document["status"],
                "structured_artifact": structured_path,
                "notes": document.get("notes", ""),
            }
        )
        for trace_row in row["source_traceability_rows"]:
            component_id = trace_row["component_id"]
            component_entry = component_map.setdefault(component_id, {"source_ids": set(), "obligation_ids": set()})
            component_entry["source_ids"].add(source_id)
            component_entry["obligation_ids"].add(trace_row["obligation_id"])
            obligation_rows.append(
                {
                    "obligation_id": trace_row["obligation_id"],
                    "source_id": source_id,
                    "trace_id": trace_row["trace_id"],
                    "component_id": component_id,
                    "category": "project_design",
                    "description": trace_row["obligation_statement"],
                    "layer": "governance",
                    "required_artifacts": [],
                    "required_gates": [],
                    "status": "planned",
                    "source_section": trace_row["source_section"],
                    "duplicate_allowed": False,
                    "duplicate_reason": "",
                }
            )

    write_json(INDEX_ROOT / "source_inventory.json", {"index_name": "source_inventory", "schema_version": "1.0.0", "sources": inventory_rows})
    write_json(
        INDEX_ROOT / "component_source_map.json",
        {
            "index_name": "component_source_map",
            "schema_version": "1.0.0",
            "components": [
                {
                    "component_id": cid,
                    "source_ids": sorted(values["source_ids"]),
                    "obligation_ids": sorted(values["obligation_ids"]),
                }
                for cid, values in sorted(component_map.items())
            ],
        },
    )
    write_json(
        INDEX_ROOT / "obligation_index.json",
        {"index_name": "obligation_index", "schema_version": "1.0.0", "obligations": sorted(obligation_rows, key=lambda o: (o["obligation_id"], o["source_id"], o["trace_id"]))},
    )


def validate_completeness(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_name = {
        row["source_document"]["source_id"].replace("SRC-PROJECT-DESIGN-", "").lower(): row
        for row in records
    }
    for required in REQUIRED_SOURCES:
        row = by_name.get(required)
        if row is None:
            errors.append(f"missing structured entry for required source: {required}")
            continue
        if row["source_document"]["status"] != "available":
            errors.append(f"required source unavailable: {required}")
            continue
        if not (REPO_ROOT / row["source_document"]["file_path"]).exists():
            errors.append(f"missing local raw path for required source {required}: {row['source_document']['file_path']}")

    for row in records:
        normalized = row["source_document"]["source_id"].replace("SRC-PROJECT-DESIGN-", "").lower()
        structured_path = STRUCTURED_ROOT / f"project_design_{normalized}.json"
        if not structured_path.exists():
            errors.append(f"missing structured file: {structured_path}")

    return errors


def run_sync(
    upstream_root: Path,
    upstream_repo: str,
    allow_missing_required: bool,
    validate_only: bool,
    refresh_tpa_digests: bool = False,
) -> int:
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
            normalized = row["source_document"]["source_id"].replace("SRC-PROJECT-DESIGN-", "").lower()
            path = STRUCTURED_ROOT / f"project_design_{normalized}.json"
            write_json(path, row)
        update_indexes(records, obligations)
        if refresh_tpa_digests:
            refresh_tpa_scope_policy_digests(
                refresh_id="SRC-AUTH-REFRESH-2026-04-11-SRC-01B",
                refreshed_at="2026-04-11T00:00:00Z",
            )

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
    parser.add_argument("--refresh-tpa-digests", action="store_true")
    args = parser.parse_args()

    if not args.upstream_root.exists():
        raise SystemExit(f"upstream root does not exist: {args.upstream_root}")

    try:
        return run_sync(
            upstream_root=args.upstream_root,
            upstream_repo=args.upstream_repo,
            allow_missing_required=args.allow_missing_required,
            validate_only=args.validate_only,
            refresh_tpa_digests=args.refresh_tpa_digests,
        )
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
