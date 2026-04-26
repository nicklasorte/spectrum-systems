from __future__ import annotations


def ensure_rfx_placement(roadmap: dict) -> dict:
    batches = list(roadmap.get("batches", []))
    ids = {b.get("batch_id") for b in batches}
    reasons: list[str] = []

    loop_09 = {
        "batch_id": "LOOP-09",
        "acronym": "RFX",
        "title": "Fix Integrity Proof",
        "status": "not_started",
        "depends_on": ["LOOP-08"],
        "hard_gate": True,
    }
    loop_10 = {
        "batch_id": "LOOP-10",
        "acronym": "RFX",
        "title": "Proof-Bound Closure",
        "status": "not_started",
        "depends_on": ["LOOP-09"],
        "hard_gate": True,
    }

    if "LOOP-09" not in ids:
        batches.append(loop_09)
        reasons.append("inserted_loop_09")
    if "LOOP-10" not in ids:
        batches.append(loop_10)
        reasons.append("inserted_loop_10")

    lookup = {b["batch_id"]: b for b in batches if "batch_id" in b}
    if lookup.get("LOOP-10", {}).get("depends_on") != ["LOOP-09"]:
        lookup["LOOP-10"]["depends_on"] = ["LOOP-09"]
        reasons.append("fixed_loop_10_dependency")

    roadmap["batches"] = batches
    return {"ok": True, "reason_codes": sorted(set(reasons)), "roadmap": roadmap}
