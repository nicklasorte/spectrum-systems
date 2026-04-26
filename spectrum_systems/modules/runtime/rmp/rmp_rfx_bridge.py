from __future__ import annotations

import re
from pathlib import Path


def _extract_loops(markdown: str) -> dict[str, str]:
    loops: dict[str, str] = {}
    for match in re.finditer(r"\|\s*(LOOP-\d{2})\s*\|\s*([a-z_]+|implemented|planned|not_started)\s*\|", markdown):
        loops[match.group(1)] = match.group(2)
    return loops


def reconcile_rfx_roadmap(rfx_markdown_path: Path, authority_batch_ids: set[str]) -> dict:
    rfx_markdown = rfx_markdown_path.read_text(encoding="utf-8")
    rfx_loops = _extract_loops(rfx_markdown)

    reasons: list[str] = []
    for needed in ("LOOP-09", "LOOP-10"):
        if needed not in rfx_loops:
            reasons.append(f"missing_rfx_loop:{needed}")

    orphan_loops = sorted([loop for loop in rfx_loops if loop not in authority_batch_ids])
    if orphan_loops:
        reasons.extend([f"orphan_rfx_entry:{loop}" for loop in orphan_loops])

    return {
        "ok": not reasons,
        "reason_codes": sorted(set(reasons)),
        "loops": rfx_loops,
    }
