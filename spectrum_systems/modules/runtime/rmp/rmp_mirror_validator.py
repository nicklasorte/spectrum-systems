from __future__ import annotations

import json
from pathlib import Path


REQUIRED_HEADERS = [
    "# Spectrum Systems — System Roadmap",
    "System source of truth (machine-readable): `contracts/examples/system_roadmap.json`",
    "| batch_id | acronym | title | status | depends_on | hard_gate |",
]


def validate_markdown_mirror(authority_path: Path, markdown_path: Path) -> dict:
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    reasons: list[str] = []
    for header in REQUIRED_HEADERS:
        if header not in markdown:
            reasons.append(f"mirror_missing_header:{header[:24]}")

    for row in authority.get("batches", []):
        if f"| {row['batch_id']} |" not in markdown:
            reasons.append(f"mirror_missing_batch:{row['batch_id']}")
        if f"| {row['batch_id']} | {row['acronym']} | {row['title']} | {row['status']}" not in markdown:
            reasons.append(f"mirror_status_mismatch:{row['batch_id']}")

    return {"ok": not reasons, "reason_codes": sorted(set(reasons))}
