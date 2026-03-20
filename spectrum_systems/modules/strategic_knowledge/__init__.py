"""Strategic Knowledge module scaffold."""

from .catalog import register_source
from .pathing import (
    ARTIFACT_DIR_BY_TYPE,
    SOURCE_DIR_BY_TYPE,
    artifact_absolute_path,
    required_data_lake_dirs,
    source_absolute_path,
)
from .provenance import build_provenance, pdf_anchor, transcript_anchor, utc_now_iso

__all__ = [
    "ARTIFACT_DIR_BY_TYPE",
    "SOURCE_DIR_BY_TYPE",
    "artifact_absolute_path",
    "build_provenance",
    "pdf_anchor",
    "register_source",
    "required_data_lake_dirs",
    "source_absolute_path",
    "transcript_anchor",
    "utc_now_iso",
]
