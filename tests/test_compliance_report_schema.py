import json
from pathlib import Path

import jsonschema


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "governance" / "compliance-scans" / "compliance-report.schema.json"


def test_compliance_report_schema_accepts_valid_report() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    report = {
        "schema_version": "1.0.0",
        "scan_date": "2026-03-15",
        "repos": [
            {
                "repo_name": "sample-engine",
                "repo_path": "/tmp/sample-engine",
                "compliant": False,
                "missing_requirements": ["CLAUDE.md", "tests/"],
                "warnings": ["README missing reference to spectrum-systems"],
            }
        ],
    }

    jsonschema.validate(instance=report, schema=schema)
