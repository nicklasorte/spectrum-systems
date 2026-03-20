"""Deterministic path contract for Strategic Knowledge artifacts in spectrum-data-lake."""

from __future__ import annotations

from pathlib import Path

SOURCE_DIR_BY_TYPE = {
    "book_pdf": Path("strategic_knowledge/raw/books"),
    "transcript": Path("strategic_knowledge/raw/transcripts"),
    "slide_deck": Path("strategic_knowledge/raw/slides"),
}

ARTIFACT_DIR_BY_TYPE = {
    "book_intelligence_pack": Path("strategic_knowledge/processed/book_intelligence"),
    "transcript_intelligence_pack": Path("strategic_knowledge/processed/transcript_intelligence"),
    "story_bank_entry": Path("strategic_knowledge/processed/story_bank"),
    "tactic_register": Path("strategic_knowledge/processed/tactic_registers"),
    "viewpoint_pack": Path("strategic_knowledge/processed/viewpoint_packs"),
    "evidence_map": Path("strategic_knowledge/processed/evidence_maps"),
}


def strategic_knowledge_root(data_lake_root: Path) -> Path:
    return data_lake_root / "strategic_knowledge"


def source_absolute_path(data_lake_root: Path, source_type: str, filename: str) -> Path:
    if source_type not in SOURCE_DIR_BY_TYPE:
        raise ValueError(f"Unsupported source_type: {source_type}")
    return data_lake_root / SOURCE_DIR_BY_TYPE[source_type] / filename


def artifact_absolute_path(
    data_lake_root: Path,
    artifact_type: str,
    source_id: str,
    artifact_id: str,
    artifact_version: str,
) -> Path:
    if artifact_type not in ARTIFACT_DIR_BY_TYPE:
        raise ValueError(f"Unsupported artifact_type: {artifact_type}")
    filename = f"{source_id}__{artifact_id}__v{artifact_version}.json"
    return data_lake_root / ARTIFACT_DIR_BY_TYPE[artifact_type] / filename


def required_data_lake_dirs() -> list[Path]:
    return [
        Path("strategic_knowledge/raw/books"),
        Path("strategic_knowledge/raw/transcripts"),
        Path("strategic_knowledge/raw/slides"),
        Path("strategic_knowledge/processed/book_intelligence"),
        Path("strategic_knowledge/processed/transcript_intelligence"),
        Path("strategic_knowledge/processed/slide_intelligence"),
        Path("strategic_knowledge/processed/story_bank"),
        Path("strategic_knowledge/processed/tactic_registers"),
        Path("strategic_knowledge/processed/viewpoint_packs"),
        Path("strategic_knowledge/processed/assumption_registers"),
        Path("strategic_knowledge/processed/contradiction_findings"),
        Path("strategic_knowledge/processed/evidence_maps"),
        Path("strategic_knowledge/indexes"),
        Path("strategic_knowledge/metadata"),
        Path("strategic_knowledge/lineage"),
    ]

