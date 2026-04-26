"""TLS-STACK-01 driver: run all five phases in order, fail-closed.

Usage:
    python scripts/build_tls_dependency_priority.py [--out DIR] [--fail-if-missing]

Each phase emits a schema-valid artifact under ``artifacts/tls/`` (or the
override directory). Failure at any phase halts the pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.tls_dependency_graph import registry_parser
from spectrum_systems.modules.tls_dependency_graph import evidence_scanner
from spectrum_systems.modules.tls_dependency_graph import classification as classification_module
from spectrum_systems.modules.tls_dependency_graph import trust_gaps as trust_gaps_module
from spectrum_systems.modules.tls_dependency_graph import ranking


PHASES = [
    ("phase_0_dependency_graph", "system_registry_dependency_graph.json"),
    ("phase_1_evidence", "system_evidence_attachment.json"),
    ("phase_2_classification", "system_candidate_classification.json"),
    ("phase_3_trust_gaps", "system_trust_gap_report.json"),
    ("phase_4_ranking", "system_dependency_priority_report.json"),
]


def _verify_required_artifacts(
    phase_dir: Path,
    top_level_out: Path,
) -> list[str]:
    missing: list[str] = []
    for _phase_name, artifact_name in PHASES:
        candidate = phase_dir / artifact_name
        if not candidate.is_file():
            missing.append(str(candidate))
    published = top_level_out / "system_dependency_priority_report.json"
    if not published.is_file():
        missing.append(str(published))
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "artifacts" / "tls"))
    parser.add_argument(
        "--top-level-out",
        default=str(REPO_ROOT / "artifacts"),
        help="The Phase 4 priority report is also published here so the dashboard can load it.",
    )
    parser.add_argument(
        "--candidates",
        default=None,
        help=(
            "Comma-separated system_ids the operator is focused on (e.g. "
            "H01,RFX,HOP,MET,METS). Used only to scope the printed summary; "
            "the governed priority artifact still ranks the full registry."
        ),
    )
    parser.add_argument(
        "--fail-if-missing",
        action="store_true",
        help=(
            "Fail closed if expected TLS artifacts are missing after build. "
            "Use in CI/deployment to prevent silent deploys without priority data."
        ),
    )
    args = parser.parse_args(argv)
    requested_candidates = [token.strip().upper() for token in args.candidates.split(",") if token.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    top_level_out = Path(args.top_level_out)
    top_level_out.mkdir(parents=True, exist_ok=True)
    candidate_filter = (
        {c.strip() for c in args.candidates.split(",") if c.strip()}
        if args.candidates
        else None
    )

    print("[TLS-00] parsing system registry…", flush=True)
    graph = registry_parser.write_artifact(out_dir / "system_registry_dependency_graph.json")
    if not graph["active_systems"]:
        print("FAIL: TLS-00 emitted zero active systems", file=sys.stderr)
        return 1

    print(f"[TLS-01] scanning repo evidence for {len(graph['active_systems'])} active systems…", flush=True)
    evidence = evidence_scanner.write_artifact(
        out_dir / "system_evidence_attachment.json", graph
    )

    print("[TLS-02] classifying candidates…", flush=True)
    classification = classification_module.write_artifact(
        out_dir / "system_candidate_classification.json", graph, evidence
    )

    print("[TLS-03] detecting trust gaps…", flush=True)
    trust_gaps = trust_gaps_module.write_artifact(
        out_dir / "system_trust_gap_report.json", graph, evidence, classification
    )

    print("[TLS-04] ranking systems…", flush=True)
    priority = ranking.write_artifact(
        out_dir / "system_dependency_priority_report.json",
        graph,
        evidence,
        classification,
        trust_gaps,
        requested_candidates=requested_candidates or None,
    )

    # Publish the priority report at the top of artifacts/ so the dashboard
    # can load it from a stable, well-known path.
    published = top_level_out / "system_dependency_priority_report.json"
    published.write_text(json.dumps(priority, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.fail_if_missing:
        missing = _verify_required_artifacts(out_dir, top_level_out)
        if missing:
            print("FAIL: missing required TLS artifacts:", file=sys.stderr)
            for path in missing:
                print(f" - {path}", file=sys.stderr)
            return 1

    print("OK")
    summary = {
        "top_5": [
            {"rank": r["rank"], "system_id": r["system_id"], "score": r["score"]}
            for r in priority["top_5"]
        ],
    }
    if candidate_filter is not None:
        candidate_rows = [
            {"rank": r["rank"], "system_id": r["system_id"], "score": r["score"]}
            for r in priority["ranked_systems"]
            if r["system_id"] in candidate_filter
        ]
        summary["candidates"] = sorted(candidate_filter)
        summary["candidate_ranking"] = candidate_rows
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
