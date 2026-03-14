from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FIXTURES = BASE_DIR / "examples" / "outputs"
PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
DECISION_FINAL_STATES = {"approved", "rejected", "superseded"}


def load_artifact(name: str, fixtures_dir: Path = DEFAULT_FIXTURES) -> Dict[str, Any]:
    path = fixtures_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return json.loads(path.read_text())


def derive_top_risks(program_brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    risks = program_brief.get("top_risks", [])
    return sorted(
        risks,
        key=lambda r: (
            r.get("decision_readiness_effect", ""),
            r.get("category", ""),
            r.get("risk_id", ""),
        ),
    )


def derive_open_decisions(decision_log: Dict[str, Any]) -> List[Dict[str, Any]]:
    decisions = decision_log.get("decisions", [])
    filtered = [
        d for d in decisions if d.get("status") not in DECISION_FINAL_STATES
    ]

    def needed_by(decision: Dict[str, Any]) -> str:
        return decision.get("needed_by") or "9999-12-31T23:59:59Z"

    return sorted(filtered, key=lambda d: (needed_by(d), d.get("decision_id", "")))


def derive_missing_evidence(readiness: Dict[str, Any]) -> Dict[str, Any]:
    missing = readiness.get("decision_readiness", {}).get("missing_evidence", []) or []
    artifact_status = readiness.get("artifact_status", {})
    missing_artifacts = []
    for artifact_name, status_obj in artifact_status.items():
        if status_obj.get("status") in {"missing", "stale"}:
            missing_artifacts.append(
                {
                    "artifact": artifact_name,
                    "status": status_obj.get("status"),
                    "notes": status_obj.get("notes"),
                }
            )
    return {
        "missing_evidence": missing,
        "missing_artifacts": missing_artifacts,
    }


def derive_actions(nba: Dict[str, Any]) -> List[Dict[str, Any]]:
    actions = nba.get("actions", [])

    def priority(action: Dict[str, Any]) -> int:
        return PRIORITY_ORDER.get(action.get("priority", "medium"), 99)

    def due_date(action: Dict[str, Any]) -> str:
        return action.get("due_at") or "9999-12-31T23:59:59Z"

    return sorted(actions, key=lambda a: (priority(a), due_date(a), a.get("action_id", "")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Spectrum Program Advisor CLI (scaffold)")
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=DEFAULT_FIXTURES,
        help="Path to fixtures directory (defaults to examples/outputs)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("brief", help="Emit Program Brief JSON")
    subparsers.add_parser("readiness", help="Emit Study Readiness Assessment JSON")
    subparsers.add_parser("nba", help="Emit Next Best Action Memo JSON")
    subparsers.add_parser("top-risks", help="Emit top risks summary derived from Program Brief")
    subparsers.add_parser("open-decisions", help="Emit open decisions summary derived from Decision Log")
    subparsers.add_parser("missing-evidence", help="Emit missing evidence/artifact summary derived from readiness")

    args = parser.parse_args()
    fixtures_dir = args.fixtures.resolve()

    if args.command == "brief":
        payload = load_artifact("program_brief", fixtures_dir)
    elif args.command == "readiness":
        payload = load_artifact("study_readiness_assessment", fixtures_dir)
    elif args.command == "nba":
        payload = load_artifact("next_best_action_memo", fixtures_dir)
    elif args.command == "top-risks":
        brief = load_artifact("program_brief", fixtures_dir)
        payload = {"top_risks": derive_top_risks(brief)}
    elif args.command == "open-decisions":
        decision_log = load_artifact("decision_log", fixtures_dir)
        payload = {"open_decisions": derive_open_decisions(decision_log)}
    elif args.command == "missing-evidence":
        readiness = load_artifact("study_readiness_assessment", fixtures_dir)
        payload = derive_missing_evidence(readiness)
    else:
        raise ValueError(f"Unknown command: {args.command}")

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
