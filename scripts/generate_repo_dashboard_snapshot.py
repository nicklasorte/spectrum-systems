#!/usr/bin/env python3
"""Generate deterministic repository snapshot for dashboard ingestion."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    ".tox",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

HOTSPOT_BUCKETS: list[tuple[str, tuple[str, ...], str]] = [
    ("PQX", ("pqx",), "PQX orchestration and execution pathways."),
    ("Control", ("control", "conductor", "slo"), "Control-layer and runtime gating logic."),
    ("Roadmap", ("roadmap",), "Roadmap-linked execution and sequencing support."),
    ("Review", ("review",), "Review ingestion and projection interfaces."),
    ("Judgment", ("judg",), "Judgment and policy decision logic."),
    ("Evaluation", ("eval", "factcheck"), "Evaluation and quality validation modules."),
    ("Replay", ("replay",), "Replay and rerun execution support."),
    (
        "Governed repair",
        ("repair", "remediation", "fix", "recovery"),
        "Governed repair and remediation pathways.",
    ),
]


@dataclass(frozen=True)
class RepoSurface:
    repo_root: Path
    runtime_root: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dashboard repository snapshot JSON.")
    parser.add_argument(
        "--output",
        default="artifacts/dashboard/repo_snapshot.json",
        help="Output path for snapshot JSON.",
    )
    return parser.parse_args()


def discover_repo_root() -> Path:
    script_repo_root = Path(__file__).resolve().parents[1]
    cwd = Path.cwd().resolve()

    if (cwd / ".git").exists() and (cwd / "README.md").exists():
        return cwd
    if (script_repo_root / ".git").exists():
        return script_repo_root

    raise RuntimeError("Unable to locate repository root.")


def iter_repo_files(repo_root: Path) -> Iterable[Path]:
    for path in sorted(repo_root.rglob("*")):
        relative_parts = path.relative_to(repo_root).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        if path.is_file():
            yield path


def detect_runtime_root(repo_root: Path) -> Path:
    preferred = repo_root / "spectrum_systems/modules/runtime"
    if preferred.exists():
        return preferred

    candidates = sorted(
        [
            p
            for p in repo_root.rglob("runtime")
            if p.is_dir() and "spectrum_systems" in p.parts and not any(part in IGNORED_DIRS for part in p.parts)
        ]
    )
    if candidates:
        return candidates[0]
    return preferred


def count_docs(repo_root: Path) -> int:
    doc_suffixes = {".md", ".mdx", ".rst", ".txt"}
    total = 0
    docs_root = repo_root / "docs"
    if docs_root.exists():
        total += sum(1 for p in docs_root.rglob("*") if p.is_file() and p.suffix.lower() in doc_suffixes)

    for top_doc in ["README.md", "CONSTITUTION.md", "GOVERNANCE.md"]:
        if (repo_root / top_doc).is_file():
            total += 1

    return total


def build_core_areas(repo_root: Path, runtime_root: Path) -> list[dict[str, str]]:
    area_candidates = [
        ("docs", "Governance, architecture, and operating documentation."),
        ("contracts", "Schema and example contract artifacts."),
        (str(runtime_root.relative_to(repo_root)), "Governed runtime module surface."),
        ("tests", "Deterministic validation and conformance coverage."),
        ("runs", "Run artifacts and execution records."),
        ("artifacts", "Generated artifacts for governed execution."),
    ]

    areas = [{"name": name, "description": description} for name, description in area_candidates if (repo_root / name).exists()]
    return sorted(areas, key=lambda area: area["name"])


def build_constitutional_center(repo_root: Path) -> list[str]:
    anchor = "docs/architecture/system_registry.md"
    preferred = [
        "README.md",
        "docs/architecture/system_registry.md",
        "docs/roadmaps/system_roadmap.md",
        "docs/runtime/runtime_governance.md",
        "docs/review-actions/README.md",
    ]
    existing = [path for path in preferred if (repo_root / path).is_file()]

    if anchor not in existing and (repo_root / anchor).is_file():
        existing.append(anchor)

    if anchor in existing:
        existing = [anchor] + sorted({item for item in existing if item != anchor})
    else:
        existing = sorted(set(existing))

    return existing


def build_runtime_hotspots(runtime_files: list[Path], runtime_root: Path) -> list[dict[str, object]]:
    hotspot_rows: list[dict[str, object]] = []

    for area, keywords, note in HOTSPOT_BUCKETS:
        count = 0
        for file_path in runtime_files:
            relative_name = str(file_path.relative_to(runtime_root)).lower()
            if any(keyword in relative_name for keyword in keywords):
                count += 1
        if count > 0:
            hotspot_rows.append({"area": area, "count": count, "note": note})

    return hotspot_rows


def build_operational_signals(
    repo_root: Path,
    root_counts: dict[str, int],
    runtime_files: list[Path],
    constitutional_center: list[str],
) -> list[dict[str, str]]:
    constitution_present = (repo_root / "docs/architecture/system_registry.md").is_file()
    governed_surface = root_counts["runtime_modules"] > 0 and root_counts["contracts_total"] > 0

    review_actions_count = 0
    review_actions_root = repo_root / "docs/review-actions"
    if review_actions_root.exists():
        review_actions_count = sum(1 for p in review_actions_root.rglob("*.md") if p.is_file())

    reviews_count = 0
    reviews_root = repo_root / "docs/reviews"
    if reviews_root.exists():
        reviews_count = sum(1 for p in reviews_root.rglob("*.md") if p.is_file())

    evidence_density = review_actions_count + reviews_count
    docs_to_runtime_ratio = root_counts["docs"] / max(root_counts["runtime_modules"], 1)

    runtime_prefixes = {file_path.stem.split("_")[0] for file_path in runtime_files}

    signals = [
        {
            "title": "Constitution present",
            "status": "Strong" if constitution_present else "Weak",
            "detail": "System registry foundation is present." if constitution_present else "System registry foundation is missing.",
        },
        {
            "title": "Governed execution surface",
            "status": "Strong" if governed_surface else "Watch",
            "detail": "Runtime and contract surfaces are both present."
            if governed_surface
            else "Runtime or contract surface appears incomplete.",
        },
        {
            "title": "Evidence and review density",
            "status": "Strong" if evidence_density >= 20 else "Watch" if evidence_density >= 5 else "Weak",
            "detail": f"Review artifacts detected: {evidence_density} markdown files.",
        },
        {
            "title": "Roadmap sprawl risk",
            "status": "Watch" if docs_to_runtime_ratio >= 4 else "Strong",
            "detail": f"Docs-to-runtime ratio: {docs_to_runtime_ratio:.2f}.",
        },
        {
            "title": "Runtime concentration",
            "status": "Watch" if len(runtime_prefixes) < 6 else "Strong",
            "detail": f"Distinct runtime filename prefixes: {len(runtime_prefixes)}.",
        },
        {
            "title": "Constitutional center coverage",
            "status": "Strong" if len(constitutional_center) >= 3 else "Watch",
            "detail": f"High-signal constitutional docs listed: {len(constitutional_center)}.",
        },
    ]

    return signals


def build_snapshot(surface: RepoSurface) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    all_files = list(iter_repo_files(surface.repo_root))
    runtime_files = sorted([p for p in surface.runtime_root.rglob("*.py") if p.is_file()]) if surface.runtime_root.exists() else []

    tests_root = surface.repo_root / "tests"
    tests_count = sum(1 for p in tests_root.rglob("test_*.py") if p.is_file()) if tests_root.exists() else 0

    schemas_root = surface.repo_root / "contracts/schemas"
    examples_root = surface.repo_root / "contracts/examples"
    schemas_count = sum(1 for p in schemas_root.rglob("*") if p.is_file()) if schemas_root.exists() else 0
    examples_count = sum(1 for p in examples_root.rglob("*") if p.is_file()) if examples_root.exists() else 0

    run_paths = [surface.repo_root / "runs", surface.repo_root / "artifacts/runtime", surface.repo_root / "artifacts/pqx_runs"]
    run_artifacts_count = 0
    for run_root in run_paths:
        if run_root.exists():
            run_artifacts_count += sum(1 for p in run_root.rglob("*") if p.is_file())

    constitutional_center = build_constitutional_center(surface.repo_root)
    root_counts = {
        "files_total": len(all_files),
        "runtime_modules": len(runtime_files),
        "tests": tests_count,
        "contracts_total": schemas_count + examples_count,
        "schemas": schemas_count,
        "examples": examples_count,
        "docs": count_docs(surface.repo_root),
        "run_artifacts": run_artifacts_count,
    }

    key_state_path = surface.repo_root / "artifacts/ops_master_01/current_run_state_record.json"
    key_bottleneck_path = surface.repo_root / "artifacts/ops_master_01/current_bottleneck_record.json"
    key_hard_gate_path = surface.repo_root / "artifacts/ops_master_01/hard_gate_status_record.json"
    key_state: dict[str, object] = {}
    if key_state_path.is_file():
        key_state["current_run_state_record"] = json.loads(key_state_path.read_text(encoding="utf-8"))
    if key_bottleneck_path.is_file():
        key_state["current_bottleneck_record"] = json.loads(key_bottleneck_path.read_text(encoding="utf-8"))
    if key_hard_gate_path.is_file():
        key_state["hard_gate_status_record"] = json.loads(key_hard_gate_path.read_text(encoding="utf-8"))

    return {
        "generated_at": generated_at,
        "freshness_timestamp_utc": generated_at,
        "repo_name": surface.repo_root.name,
        "root_counts": root_counts,
        "core_areas": build_core_areas(surface.repo_root, surface.runtime_root),
        "constitutional_center": constitutional_center,
        "runtime_hotspots": build_runtime_hotspots(runtime_files, surface.runtime_root),
        "operational_signals": build_operational_signals(
            surface.repo_root,
            root_counts,
            runtime_files,
            constitutional_center,
        ),
        "key_state": key_state,
    }


def write_snapshot(snapshot: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    previous_generated_at: str | None = None
    if output_path.is_file():
        try:
            previous_generated_at = str(json.loads(output_path.read_text(encoding="utf-8")).get("generated_at", "")).strip() or None
        except Exception:  # noqa: BLE001
            previous_generated_at = None

    if previous_generated_at:
        try:
            previous_dt = datetime.strptime(previous_generated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            current_dt = datetime.strptime(str(snapshot["generated_at"]), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if current_dt <= previous_dt:
                current_dt = previous_dt + timedelta(seconds=1)
                snapshot["generated_at"] = current_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                snapshot["freshness_timestamp_utc"] = snapshot["generated_at"]
        except (ValueError, KeyError):
            pass

    output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    try:
        repo_root = discover_repo_root()
        runtime_root = detect_runtime_root(repo_root)
        snapshot = build_snapshot(RepoSurface(repo_root=repo_root, runtime_root=runtime_root))
        write_snapshot(snapshot, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(str(Path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
