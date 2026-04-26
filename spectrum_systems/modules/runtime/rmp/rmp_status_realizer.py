from __future__ import annotations


def realize_status(batch: dict, evidence: dict[str, bool]) -> dict:
    reasons: list[str] = []
    if batch.get("status") == "implemented":
        if not evidence.get("code"):
            reasons.append("status_without_code")
        if not evidence.get("tests"):
            reasons.append("status_without_tests")
        if not evidence.get("artifacts"):
            reasons.append("status_without_artifacts")

    if batch.get("status") == "completed":
        for key in ("code", "tests", "artifacts"):
            if not evidence.get(key):
                reasons.append(f"status_without_{key}")

    return {"ok": not reasons, "reason_codes": sorted(set(reasons))}
