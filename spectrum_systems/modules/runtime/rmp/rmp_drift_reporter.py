from __future__ import annotations

import json
from pathlib import Path


def write_drift_report(path: Path, checks: dict[str, dict]) -> dict:
    failures = {name: result for name, result in checks.items() if not result.get("ok")}
    report = {
        "status": "pass" if not failures else "fail",
        "drift_detected": bool(failures),
        "checks": checks,
        "reason_codes": sorted({code for item in failures.values() for code in item.get("reason_codes", [])}),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
