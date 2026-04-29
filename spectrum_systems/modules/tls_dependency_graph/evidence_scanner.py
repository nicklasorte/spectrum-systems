"""TLS-01 — Repo evidence scanner.

For every active system in the Phase 0 dependency graph, attach evidence
discovered in the repo:

* modules / source files referenced by registry primary_code_paths or
  matching the system id token,
* tests under ``tests/`` whose path or name references the system,
* schemas under ``schemas/`` referencing the system or one of its artifacts,
* docs under ``docs/`` referencing the system,
* reviews under ``reviews/`` and ``design-reviews/``,
* review-actions / scripts under ``scripts/``,
* artifacts under ``artifacts/``.

Fail-closed contract: a system with zero evidence is NOT silently skipped — it
is recorded with ``has_evidence=false`` and an explicit
``missing_evidence_reason`` so the next phase can act on it.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_VERSION = "tls-01.v1"


SCAN_BUCKETS: Sequence[tuple[str, Sequence[str]]] = (
    ("modules", ("spectrum_systems/", "modules/", "src/")),
    ("tests", ("tests/",)),
    ("schemas", ("schemas/",)),
    ("docs", ("docs/",)),
    ("reviews", ("reviews/", "design-reviews/")),
    ("review_actions", ("review-actions/",)),
    ("scripts", ("scripts/",)),
    ("artifacts", ("artifacts/",)),
)

# These extensions count as text and are scanned for system-id references.
TEXT_EXTS = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".sh", ".yaml", ".yml"}

# Skip paths that produce noise without evidentiary value.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", "package-lock.json", ".venv", "venv"}


def _iter_repo_files(buckets: Sequence[tuple[str, Sequence[str]]], root: Path) -> Iterable[tuple[str, Path]]:
    for bucket, prefixes in buckets:
        for prefix in prefixes:
            base = root / prefix.rstrip("/")
            if not base.exists() or not base.is_dir():
                continue
            # Sort rglob output so iteration order is deterministic across
            # runs/filesystems. Without this, the per-bucket cap dropped
            # different files on each run, flipping AEX trust signals.
            for p in sorted(base.rglob("*")):
                if not p.is_file():
                    continue
                rel_parts = p.relative_to(root).parts
                if any(part in SKIP_DIRS for part in rel_parts):
                    continue
                if p.suffix.lower() not in TEXT_EXTS:
                    continue
                yield bucket, p


def _system_token_patterns(system_id: str, artifacts_owned: Sequence[str]) -> List[re.Pattern]:
    patterns: List[re.Pattern] = []
    # Whole-token reference to the uppercase system id (avoids matching MAP in
    # words like 'mapping' by requiring non-alphanumeric boundaries).
    patterns.append(re.compile(rf"(?<![A-Za-z0-9_]){re.escape(system_id)}(?![A-Za-z0-9_])"))
    # Lowercase form, e.g. "aex" used in filenames or function names.
    patterns.append(re.compile(rf"(?<![A-Za-z0-9_]){re.escape(system_id.lower())}(?![A-Za-z0-9_])"))
    # Each owned artifact name (case-insensitive whole-token).
    for artifact in artifacts_owned:
        if not artifact:
            continue
        token = re.escape(artifact)
        patterns.append(re.compile(rf"(?<![A-Za-z0-9_]){token}(?![A-Za-z0-9_])", re.IGNORECASE))
    return patterns


def _path_matches(rel_path: str, system_id: str, primary_code_paths: Sequence[str]) -> bool:
    rel_norm = rel_path.replace("\\", "/")
    if any(rel_norm == cp or rel_norm.endswith("/" + cp) for cp in primary_code_paths):
        return True
    sid_lower = system_id.lower()
    sid_token = re.compile(rf"(?<![A-Za-z0-9])({re.escape(system_id)}|{re.escape(sid_lower)})(?![A-Za-z0-9])")
    return bool(sid_token.search(rel_norm))


def _file_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def attach_evidence(
    dependency_graph: Dict,
    repo_root: Optional[Path] = None,
    max_per_bucket: int = 25,
) -> Dict:
    """Build the evidence-attachment artifact dictionary."""

    root = repo_root or REPO_ROOT
    active = dependency_graph.get("active_systems") or []
    if not active:
        raise ValueError("dependency_graph has no active_systems; cannot attach evidence")

    by_system: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    by_system_seen: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    artifacts_index: Dict[str, Sequence[str]] = {n["system_id"]: n.get("artifacts_owned") or [] for n in active}
    code_paths_index: Dict[str, Sequence[str]] = {n["system_id"]: n.get("primary_code_paths") or [] for n in active}

    pattern_index: Dict[str, List[re.Pattern]] = {
        sid: _system_token_patterns(sid, artifacts_index[sid]) for sid in artifacts_index
    }

    for bucket, path in _iter_repo_files(SCAN_BUCKETS, root):
        rel = str(path.relative_to(root)).replace("\\", "/")
        text: Optional[str] = None
        for sid, patterns in pattern_index.items():
            already = by_system_seen[sid][bucket]
            if rel in already:
                continue
            if _path_matches(rel, sid, code_paths_index[sid]):
                already.add(rel)
                if len(by_system[sid][bucket]) < max_per_bucket:
                    by_system[sid][bucket].append(rel)
                continue
            if text is None:
                text = _file_text(path) or ""
            if any(p.search(text) for p in patterns):
                already.add(rel)
                if len(by_system[sid][bucket]) < max_per_bucket:
                    by_system[sid][bucket].append(rel)

    rows: List[Dict] = []
    for node in sorted(active, key=lambda n: n["system_id"]):
        sid = node["system_id"]
        ev = by_system.get(sid, {})
        # canonicalize bucket order
        evidence = {bucket: sorted(ev.get(bucket, [])) for bucket, _ in SCAN_BUCKETS}
        evidence_count = sum(len(v) for v in evidence.values())
        has_evidence = evidence_count > 0
        missing_reason: Optional[str] = None
        if not has_evidence:
            missing_reason = "no_repo_evidence_detected_for_token_or_artifacts"
        rows.append(
            {
                "system_id": sid,
                "has_evidence": has_evidence,
                "missing_evidence_reason": missing_reason,
                "evidence_count": evidence_count,
                "evidence": evidence,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "phase": "TLS-01",
        "source_dependency_graph_phase": dependency_graph.get("phase"),
        "systems": rows,
    }


def write_artifact(
    output_path: Path,
    dependency_graph: Dict,
    repo_root: Optional[Path] = None,
) -> Dict:
    payload = attach_evidence(dependency_graph, repo_root=repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
