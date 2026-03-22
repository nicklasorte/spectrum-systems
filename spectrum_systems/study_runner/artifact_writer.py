"""
Artifact writer for the Spectrum Study Compiler runner.

Creates deterministic output directories, writes tabular artifacts as CSV,
and emits JSON manifests suitable for downstream review engines.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import csv
import json
import hashlib

from shared.adapters.artifact_emitter import create_provenance_record
from spectrum_systems.modules.runtime.trace_engine import validate_trace_context

from .load_config import StudyConfig
from .pipeline import Deployment, InterferenceResult, PathLossResult, ProtectionZone


def _ensure_dirs(base_output: Path) -> Dict[str, Path]:
    tables = base_output / "tables"
    figures = base_output / "figures"
    maps = base_output / "maps"
    for path in (base_output, tables, figures, maps):
        path.mkdir(parents=True, exist_ok=True)
    return {"base": base_output, "tables": tables, "figures": figures, "maps": maps}


def _build_run_id(config: StudyConfig) -> str:
    serialized = json.dumps(config.as_dict(), sort_keys=True)
    digest = hashlib.sha256(serialized.encode()).hexdigest()[:12]
    return f"run-{digest}"


def _provenance_record(
    *,
    run_id: str,
    workflow_step: str,
    source_document: str,
    source_revision: str,
    generated_by_version: str,
    policy_id: str,
    trace_id: str,
    span_id: str,
    timestamp: str,
) -> dict:
    normalized_run_id = run_id.upper()
    return create_provenance_record(
        record_id=f"PRV-{normalized_run_id}-{workflow_step.upper()}",
        record_type="artifact",
        source_document=source_document,
        source_revision=source_revision,
        workflow_name="spectrum-study-compiler",
        workflow_step=workflow_step,
        generated_by_system="SYS-004 Spectrum Study Compiler",
        generated_by_repo="nicklasorte/spectrum-systems",
        generated_by_version=generated_by_version,
        policy_id=policy_id,
        trace_id=trace_id,
        span_id=span_id,
        created_at=timestamp,
        updated_at=timestamp,
    )


def _write_csv(rows: List[dict], output_path: Path) -> None:
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_tables(
    tables: Dict[str, List[dict]], tables_dir: Path, provenance: dict
) -> List[dict]:
    metadata: List[dict] = []
    for name, rows in tables.items():
        path = tables_dir / f"{name}.csv"
        _write_csv(rows, path)
        metadata.append(
            {
                "artifact_id": f"ART-TBL-{name}",
                "artifact_type": "table",
                "title": name.replace("_", " ").title(),
                "description": f"Deterministic table for {name}.",
                "render_ref": str(path),
                "metrics": list(rows[0].keys()) if rows else [],
                "source_scenarios": [row.get("system") for row in rows if "system" in row],
                "status": "draft",
                "schema_version": "1.1.0",
                "provenance": provenance,
            }
        )
    return metadata


def write_figures_metadata(figures: List[dict], figures_dir: Path, provenance: dict) -> Path:
    enriched = []
    for figure in figures:
        updated = {**figure, "schema_version": "1.1.0", "provenance": provenance}
        enriched.append(updated)
    metadata_path = figures_dir / "figures_metadata.json"
    metadata_path.write_text(json.dumps(enriched, indent=2, sort_keys=True), encoding="utf-8")
    return metadata_path


def write_maps(zones: List[ProtectionZone], maps_dir: Path) -> Path:
    kml_path = maps_dir / "protection_zones.kml"
    placemarks = []
    for zone in zones:
        placemarks.append(
            f"<Placemark><name>{zone.system_name}</name>"
            f"<description>Status: {zone.status}</description>"
            f"<ExtendedData><Data name=\"radius_km\"><value>{zone.radius_km}</value></Data>"
            "</ExtendedData></Placemark>"
        )
    kml_body = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
        "<kml xmlns=\"http://www.opengis.net/kml/2.2\"><Document>"
        f"{''.join(placemarks)}</Document></kml>"
    )
    kml_path.write_text(kml_body, encoding="utf-8")
    return kml_path


def write_results_json(
    config: StudyConfig,
    deployments: List[Deployment],
    pathloss: List[PathLossResult],
    interference: List[InterferenceResult],
    zones: List[ProtectionZone],
    results_path: Path,
    run_id: str,
    timestamp: str,
) -> None:
    payload = {
        "run_id": run_id,
        "generated_at": timestamp,
        "config": config.as_dict(),
        "deployments": [asdict(item) for item in deployments],
        "pathloss": [asdict(item) for item in pathloss],
        "interference": [asdict(item) for item in interference],
        "protection_zones": [asdict(item) for item in zones],
    }
    results_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_study_summary(
    study_summary_path: Path,
    run_id: str,
    config: StudyConfig,
    evaluations: Dict[str, bool],
    table_metadata: List[dict],
    figures_metadata_path: Path,
    map_path: Path,
    timestamp: str,
) -> None:
    summary = {
        "run_id": run_id,
        "generated_at": timestamp,
        "system_id": "SYS-004",
        "downstream_consumers": ["working-paper-review-engine", "comment-resolution-engine"],
        "protection_evaluations": evaluations,
        "table_metadata": table_metadata,
        "figures_metadata_path": str(figures_metadata_path),
        "map_path": str(map_path),
        "schemas": {
            "study_output_schema": "1.1.0",
            "provenance_schema": "1.1.0",
        },
        "config_inputs": config.as_dict(),
    }
    study_summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")


def write_outputs(
    config: StudyConfig,
    pipeline_outputs: dict,
    logger,
    *,
    policy_id: str,
    generated_by_version: str,
    source_revision: str,
    trace_id: str,
    span_id: str,
) -> Dict[str, str]:
    trace_errors = validate_trace_context(trace_id, span_id)
    if trace_errors:
        raise ValueError(
            "artifact_writer requires valid trace context before writing outputs: "
            + "; ".join(trace_errors)
        )

    base_dirs = _ensure_dirs(Path("outputs"))
    timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    run_id = _build_run_id(config)
    provenance = _provenance_record(
        run_id=run_id,
        workflow_step="run_pipeline",
        source_document=str(config.config_path),
        source_revision=source_revision,
        generated_by_version=generated_by_version,
        policy_id=policy_id,
        trace_id=trace_id,
        span_id=span_id,
        timestamp=timestamp,
    )

    tables_metadata = write_tables(
        pipeline_outputs["tables"], base_dirs["tables"], provenance=provenance
    )
    figures_metadata_path = write_figures_metadata(
        pipeline_outputs["figures_metadata"], base_dirs["figures"], provenance
    )
    map_path = write_maps(pipeline_outputs["protection_zones"], base_dirs["maps"])

    results_path = Path("outputs") / "results.json"
    study_summary_path = Path("outputs") / "study_summary.json"

    write_results_json(
        config=config,
        deployments=pipeline_outputs["deployments"],
        pathloss=pipeline_outputs["pathloss"],
        interference=pipeline_outputs["interference"],
        zones=pipeline_outputs["protection_zones"],
        results_path=results_path,
        run_id=run_id,
        timestamp=timestamp,
    )
    write_study_summary(
        study_summary_path=study_summary_path,
        run_id=run_id,
        config=config,
        evaluations=pipeline_outputs["protection_evaluations"],
        table_metadata=tables_metadata,
        figures_metadata_path=figures_metadata_path,
        map_path=map_path,
        timestamp=timestamp,
    )

    logger.info(
        json.dumps(
            {
                "event": "artifact_writer.completed",
                "run_id": run_id,
                "outputs": {
                    "results": str(results_path),
                    "study_summary": str(study_summary_path),
                    "tables_dir": str(base_dirs["tables"]),
                    "figures_dir": str(base_dirs["figures"]),
                    "maps_dir": str(base_dirs["maps"]),
                },
            },
            sort_keys=True,
        )
    )

    return {
        "run_id": run_id,
        "results_path": str(results_path),
        "study_summary_path": str(study_summary_path),
        "tables_dir": str(base_dirs["tables"]),
        "figures_dir": str(base_dirs["figures"]),
        "maps_dir": str(base_dirs["maps"]),
    }
