import json
import sys
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
FIXTURES = BASE_DIR / "examples" / "outputs"

sys.path.insert(0, str(SRC_DIR))

import cli  # noqa: E402


class AdvisorCliTests(unittest.TestCase):
    def test_program_brief_fixture_loads(self) -> None:
        brief = cli.load_artifact("program_brief", FIXTURES)
        self.assertEqual(brief["artifact_type"], "program_brief")
        self.assertEqual(brief["program_id"], "PRG-SPEC-001")

    def test_top_risks_are_sorted_deterministically(self) -> None:
        brief = cli.load_artifact("program_brief", FIXTURES)
        risks = cli.derive_top_risks(brief)
        self.assertEqual(risks[0]["risk_id"], "RISK-001")
        self.assertEqual(risks[-1]["risk_id"], "RISK-002")

    def test_open_decisions_filters_and_sorts(self) -> None:
        decision_log = cli.load_artifact("decision_log", FIXTURES)
        open_decisions = cli.derive_open_decisions(decision_log)
        self.assertEqual(len(open_decisions), 2)
        self.assertEqual(open_decisions[0]["decision_id"], "DEC-001")
        self.assertTrue(all(d["status"] not in cli.DECISION_FINAL_STATES for d in open_decisions))

    def test_missing_evidence_summary(self) -> None:
        readiness = cli.load_artifact("study_readiness_assessment", FIXTURES)
        summary = cli.derive_missing_evidence(readiness)
        self.assertIn("Updated validation residuals", summary["missing_evidence"])
        self.assertEqual(summary["missing_artifacts"], [])

    def test_actions_sort_by_priority_then_due(self) -> None:
        nba = cli.load_artifact("next_best_action_memo", FIXTURES)
        actions = cli.derive_actions(nba)
        self.assertEqual(actions[0]["action_id"], "NBA-001")
        self.assertEqual(actions[1]["action_id"], "NBA-002")


if __name__ == "__main__":
    unittest.main()
