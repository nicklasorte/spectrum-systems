from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    path: str
    required: bool
    present: bool
    content_hash: str | None


@dataclass(frozen=True)
class NextStepInputs:
    source_refs: list[SourceRef]
    payloads: dict[str, Any]
    reason_codes: list[str]


REQUIRED_SOURCES = [
    "contracts/examples/system_roadmap.json",
    "docs/roadmaps/system_roadmap.md",
    "docs/roadmaps/rfx_cross_system_roadmap.md",
    "artifacts/system_dependency_priority_report.json",
    "artifacts/rmp_01_delivery_report.json",
    "artifacts/rmp_drift_report.json",
    "artifacts/blf_01_baseline_failure_fix/delivery_report.json",
]

OPTIONAL_SOURCES = [
    "contracts/review_artifact/H01_review.json",
    "docs/reviews/H01_pre_mvp_spine_review.md",
    "artifacts/rfx_04_loop_07_08/delivery_report.json",
]

OPTIONAL_GLOBS = [
    "artifacts/h01*_final*.json",
    "artifacts/h01*fix*plan*.json",
    "docs/reviews/H01*final*.md",
    "docs/reviews/H01*fix*plan*.md",
]



def _sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"



def _load_json_if_possible(path: Path) -> Any | None:
    if path.suffix.lower() != ".json":
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None



def load_inputs(repo_root: Path) -> NextStepInputs:
    refs: list[SourceRef] = []
    payloads: dict[str, Any] = {}
    reason_codes: list[str] = []

    for rel in REQUIRED_SOURCES:
        candidate = repo_root / rel
        present = candidate.is_file()
        content_hash = _sha256(candidate) if present else None
        refs.append(SourceRef(path=rel, required=True, present=present, content_hash=content_hash))
        if present:
            payloads[rel] = _load_json_if_possible(candidate)
        else:
            reason_codes.append(f"missing_required_artifact:{rel}")

    for rel in OPTIONAL_SOURCES:
        candidate = repo_root / rel
        present = candidate.is_file()
        refs.append(
            SourceRef(
                path=rel,
                required=False,
                present=present,
                content_hash=_sha256(candidate) if present else None,
            )
        )
        if present:
            payloads[rel] = _load_json_if_possible(candidate)

    for pattern in OPTIONAL_GLOBS:
        for candidate in sorted(repo_root.glob(pattern)):
            if not candidate.is_file():
                continue
            rel = str(candidate.relative_to(repo_root))
            refs.append(
                SourceRef(
                    path=rel,
                    required=False,
                    present=True,
                    content_hash=_sha256(candidate),
                )
            )
            payloads[rel] = _load_json_if_possible(candidate)

    deduped: dict[str, SourceRef] = {}
    for ref in refs:
        deduped[ref.path] = ref

    return NextStepInputs(
        source_refs=sorted(deduped.values(), key=lambda row: row.path),
        payloads=payloads,
        reason_codes=sorted(set(reason_codes)),
    )
