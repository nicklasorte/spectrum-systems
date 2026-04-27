#!/usr/bin/env python3
"""TLS-NEXT-01 integration builder.

Integrates TLS artifacts into a unified system graph artifact for dashboard/eval/control
surfaces with explicit fail-closed validation outputs.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_INPUTS = {
    "dependency_priority": "system_dependency_priority_report.json",
    "trust_gap": "tls/system_trust_gap_report.json",
    "classification": "tls/system_candidate_classification.json",
    "evidence": "tls/system_evidence_attachment.json",
    "dependency_graph": "tls/system_registry_dependency_graph.json",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_registry_system_ids(registry_path: Path) -> list[str]:
    text = registry_path.read_text(encoding="utf-8")
    ids = re.findall(r"^###\s+([A-Z0-9]{2,})\s*$", text, flags=re.MULTILINE)
    out: list[str] = []
    for sid in ids:
        if sid not in out:
            out.append(sid)
    return out


def _lineage(ref: str, artifact_type: str, step: str) -> dict[str, str]:
    return {
        "source_artifact_ref": ref,
        "artifact_type": artifact_type,
        "generation_step": step,
    }


def _status_for_node(*, trust_gap_signals: list[str], classification: str, data_source: str) -> str:
    if data_source == "stub_fallback":
        return "unknown"
    if trust_gap_signals:
        return "warning"
    if classification in {"future", "placeholder", "merged_or_demoted"}:
        return "warning"
    return "healthy"


def build_integration(*, repo_root: Path, artifacts_dir: Path, registry_path: Path, generated_at: str) -> tuple[int, dict[str, Any]]:
    missing_inputs: list[str] = []
    loaded: dict[str, dict[str, Any]] = {}

    for key, rel in REQUIRED_INPUTS.items():
        path = artifacts_dir / rel
        if not path.is_file():
            missing_inputs.append(str(path.relative_to(repo_root)))
            continue
        loaded[key] = _read_json(path)

    registry_system_ids = _parse_registry_system_ids(registry_path)
    classification_by_id = {row.get("system_id"): row for row in loaded.get("classification", {}).get("candidates", []) if isinstance(row, dict)}
    trust_gap_by_id = {row.get("system_id"): row for row in loaded.get("trust_gap", {}).get("systems", []) if isinstance(row, dict)}
    evidence_by_id = {row.get("system_id"): row for row in loaded.get("evidence", {}).get("systems", []) if isinstance(row, dict)}
    ranking_by_id = {
        row.get("system_id"): row
        for row in loaded.get("dependency_priority", {}).get("global_ranked_systems", [])
        if isinstance(row, dict)
    }
    graph_by_id = {
        row.get("system_id"): row
        for row in loaded.get("dependency_graph", {}).get("active_systems", [])
        if isinstance(row, dict)
    }

    all_ids = sorted(set(registry_system_ids) | set(classification_by_id) | set(trust_gap_by_id) | set(ranking_by_id) | set(graph_by_id))

    systems: list[dict[str, Any]] = []
    disconnected: list[str] = []
    missing_classification: list[str] = []
    missing_signal_source: list[str] = []

    for sid in all_ids:
        classification_row = classification_by_id.get(sid, {})
        gap_row = trust_gap_by_id.get(sid, {})
        evidence_row = evidence_by_id.get(sid, {})
        ranking_row = ranking_by_id.get(sid, {})
        graph_row = graph_by_id.get(sid, {})

        upstream = list((graph_row.get("upstream") or (ranking_row.get("dependencies") or {}).get("upstream") or []))
        downstream = list((graph_row.get("downstream") or (ranking_row.get("dependencies") or {}).get("downstream") or []))

        has_artifact_signal = any([
            bool(classification_row),
            bool(gap_row),
            bool(evidence_row),
            bool(ranking_row),
        ])
        if not has_artifact_signal:
            missing_signal_source.append(sid)

        classification = str(classification_row.get("classification") or "unknown")
        if classification == "unknown":
            missing_classification.append(sid)

        in_registry = sid in registry_system_ids
        data_source = "artifact_store" if has_artifact_signal else ("repo_registry" if in_registry else "stub_fallback")

        trust_gap_signals = list(gap_row.get("failing_signals") or ranking_row.get("trust_gap_signals") or [])
        gap_count = int(gap_row.get("gap_count") or len(trust_gap_signals) or 0)
        gaps_evaluated = int(gap_row.get("gaps_evaluated") or max(gap_count, 1))

        missing_eval_signals = sorted([s for s in trust_gap_signals if "eval" in s or "coverage" in s])
        eval_coverage_status = "missing" if missing_eval_signals else "present"

        if not upstream and not downstream:
            disconnected.append(sid)

        signal_lineage = {
            "classification": _lineage("artifacts/tls/system_candidate_classification.json", "system_candidate_classification", "TLS-02"),
            "trust_gap": _lineage("artifacts/tls/system_trust_gap_report.json", "system_trust_gap_report", "TLS-03"),
            "dependency_edges": _lineage("artifacts/tls/system_registry_dependency_graph.json", "system_registry_dependency_graph", "TLS-00"),
            "ranking": _lineage("artifacts/system_dependency_priority_report.json", "system_dependency_priority_report", "TLS-04"),
            "evidence": _lineage("artifacts/tls/system_evidence_attachment.json", "system_evidence_attachment", "TLS-01"),
        }

        systems.append(
            {
                "system_id": sid,
                "classification": classification,
                "in_repo_registry": in_registry,
                "data_source": data_source,
                "status": _status_for_node(
                    trust_gap_signals=trust_gap_signals,
                    classification=classification,
                    data_source=data_source,
                ),
                "dependency_edges": {"upstream": upstream, "downstream": downstream},
                "ranking_signals": {
                    "rank": ranking_row.get("rank"),
                    "score": ranking_row.get("score"),
                    "action": ranking_row.get("action"),
                    "trust_state": ranking_row.get("trust_state") or gap_row.get("trust_state"),
                    "why_now": ranking_row.get("why_now"),
                },
                "trust_gap_signals": trust_gap_signals,
                "eval_coverage_status": eval_coverage_status,
                "missing_eval_signals": missing_eval_signals,
                "derived_signals": {
                    "evaluation_coverage": eval_coverage_status,
                    "trust_gap_density": round(gap_count / max(gaps_evaluated, 1), 4),
                    "dependency_completeness": bool(upstream or downstream),
                    "artifact_presence": {
                        "classification": bool(classification_row),
                        "trust_gap": bool(gap_row),
                        "evidence": bool(evidence_row),
                        "ranking": bool(ranking_row),
                    },
                },
                "lineage": signal_lineage,
                "replay": {
                    "artifact_paths": [
                        "artifacts/tls/system_candidate_classification.json",
                        "artifacts/tls/system_trust_gap_report.json",
                        "artifacts/tls/system_evidence_attachment.json",
                        "artifacts/system_dependency_priority_report.json",
                    ],
                    "generation_commands": [
                        "python scripts/build_tls_dependency_priority.py --fail-if-missing",
                        "python scripts/tls_next_01_integration.py",
                    ],
                    "trace_linkage": f"tls-next-01:{sid}",
                },
            }
        )

    source_mix = {
        "artifact_store": sum(1 for row in systems if row["data_source"] == "artifact_store"),
        "repo_registry": sum(1 for row in systems if row["data_source"] == "repo_registry"),
        "derived": 0,
        "stub_fallback": sum(1 for row in systems if row["data_source"] == "stub_fallback"),
    }
    total = max(len(systems), 1)
    percentages = {k: round((v / total) * 100, 2) for k, v in source_mix.items()}

    eval_missing_count = sum(1 for row in systems if row["eval_coverage_status"] != "present")
    graph_complete = not disconnected and not missing_classification and not missing_signal_source
    artifact_dominates = source_mix["artifact_store"] > max(source_mix["stub_fallback"], source_mix["repo_registry"])
    fallback_minority = source_mix["stub_fallback"] < source_mix["artifact_store"]

    freeze_reasons: list[str] = []
    if missing_inputs:
        freeze_reasons.append("missing_required_artifacts")
    if source_mix["repo_registry"] <= 0:
        freeze_reasons.append("repo_registry_empty")
    if not graph_complete:
        freeze_reasons.append("system_graph_incomplete")
    if eval_missing_count > 0:
        freeze_reasons.append("eval_coverage_missing")
    if not artifact_dominates:
        freeze_reasons.append("artifact_store_not_dominant")
    if not fallback_minority:
        freeze_reasons.append("stub_fallback_not_minority")

    trust_posture = "FREEZE" if freeze_reasons else "WARN"

    integration_report = {
        "artifact_type": "tls_system_graph_integration_report",
        "phase": "TLS-INT-01",
        "generated_at": generated_at,
        "inputs": {key: f"artifacts/{rel}" for key, rel in REQUIRED_INPUTS.items()},
        "source_mix": {"counts": source_mix, "percentages": percentages},
        "trust_posture": trust_posture,
        "freeze_reasons": freeze_reasons,
        "repo_registry_count": source_mix["repo_registry"],
        "graph": {"system_count": len(systems), "systems": systems},
        "derived": {
            "eval_coverage": {
                "present_count": len(systems) - eval_missing_count,
                "missing_count": eval_missing_count,
            },
            "trust_gap_density": round(
                sum(row["derived_signals"]["trust_gap_density"] for row in systems) / total,
                4,
            ),
            "dependency_completeness": {
                "complete_count": sum(1 for row in systems if row["derived_signals"]["dependency_completeness"]),
                "incomplete_count": sum(1 for row in systems if not row["derived_signals"]["dependency_completeness"]),
            },
            "artifact_presence": {
                "full_presence_count": sum(
                    1
                    for row in systems
                    if all(bool(v) for v in row["derived_signals"]["artifact_presence"].values())
                ),
                "partial_or_missing_count": sum(
                    1
                    for row in systems
                    if not all(bool(v) for v in row["derived_signals"]["artifact_presence"].values())
                ),
            },
        },
        "replay": {
            "artifact_path": "artifacts/tls/system_graph_integration_report.json",
            "generation_command": "python scripts/tls_next_01_integration.py",
            "trace_linkage": "tls-next-01:integration",
        },
    }

    validation_report = {
        "artifact_type": "system_graph_validation_report",
        "phase": "TLS-INT-01-VALIDATE",
        "generated_at": generated_at,
        "status": "pass" if graph_complete else "fail",
        "checks": {
            "disconnected_nodes": disconnected,
            "missing_classification": missing_classification,
            "missing_signal_source": missing_signal_source,
        },
    }

    redteam_findings = {
        "artifact_type": "tls_integration_redteam_report",
        "phase": "TLS-INT-01-REDTEAM",
        "generated_at": generated_at,
        "status": "pass" if not freeze_reasons else "fail",
        "findings": {
            "stub_fallback_dominance": source_mix["stub_fallback"] >= source_mix["artifact_store"],
            "systems_without_artifact_signals": missing_signal_source,
            "disconnected_graph_nodes": disconnected,
        },
        "applied_fixes": [
            "stub_fallback constrained to systems missing all artifact signals",
            "repo registry mapping attached to each system node",
            "graph validation and fail-closed freeze reasons emitted",
        ],
    }

    roadmap = {
        "artifact_type": "tls_integration_roadmap",
        "phase": "TLS-INT-01-ROADMAP",
        "generated_at": generated_at,
        "completed_steps": [
            "TLS-INT-01 integration graph emitted",
            "system graph validation emitted",
            "eval coverage integration attached per system",
            "trust posture recomputation emitted",
            "red-team report emitted",
        ],
        "remaining_gaps": freeze_reasons,
        "next_recommended_phases": ["TLS-05", "TLS-06", "TLS-07"],
    }

    _write_json(artifacts_dir / "tls" / "system_graph_integration_report.json", integration_report)
    _write_json(artifacts_dir / "tls" / "system_graph_validation_report.json", validation_report)
    _write_json(artifacts_dir / "tls" / "tls_integration_redteam_report.json", redteam_findings)
    _write_json(artifacts_dir / "tls" / "tls_integration_roadmap.json", roadmap)

    return (0 if not freeze_reasons else 1), integration_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--artifacts-dir", default="")
    parser.add_argument("--registry-path", default="")
    parser.add_argument("--generated-at", default="")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve() if args.artifacts_dir else repo_root / "artifacts"
    registry_path = Path(args.registry_path).resolve() if args.registry_path else repo_root / "docs" / "architecture" / "system_registry.md"
    generated_at = args.generated_at or _utc_now()

    rc, report = build_integration(
        repo_root=repo_root,
        artifacts_dir=artifacts_dir,
        registry_path=registry_path,
        generated_at=generated_at,
    )
    print(
        json.dumps(
            {
                "status": "ok" if rc == 0 else "fail",
                "trust_posture": report.get("trust_posture"),
                "freeze_reasons": report.get("freeze_reasons"),
                "source_mix": report.get("source_mix", {}).get("counts", {}),
            },
            sort_keys=True,
        )
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
