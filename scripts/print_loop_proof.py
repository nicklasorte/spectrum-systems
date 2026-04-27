#!/usr/bin/env python3
"""Read-only loop proof triage renderer (NT-13)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _print(label: str, value: object) -> None:
    print(f"{label}: {value}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Print compact loop-proof triage summary.")
    parser.add_argument("--loop-proof", required=True)
    parser.add_argument("--evidence-index")
    args = parser.parse_args()

    try:
        proof = _load(args.loop_proof)
    except Exception as exc:
        print(f"status: corrupt\nerror: {exc}")
        return 3

    evidence = {}
    if args.evidence_index:
        try:
            evidence = _load(args.evidence_index)
        except Exception as exc:
            print(f"status: corrupt\nerror: evidence index unreadable: {exc}")
            return 3

    final_status = str(proof.get("final_status") or "corrupt")
    trace = proof.get("trace_summary") or {}
    delta = proof.get("delta_summary") or (evidence.get("delta_index") if isinstance(evidence, dict) else {}) or {}

    _print("final_status", final_status)
    _print("pass_block_freeze", final_status)
    _print("stage", trace.get("failed_stage") or "all_passed")
    _print("owning_system", trace.get("owning_system") or "-")
    _print("canonical_reason_category", proof.get("canonical_blocking_category") or evidence.get("blocking_reason_canonical") or "-")
    _print("detailed_reason", ",".join((evidence.get("blocking_detail_codes") or [])[:5]) or "-")

    refs = []
    for k, v in sorted(proof.items()):
        if k.endswith("_ref") and v:
            refs.append(f"{k}={v}")
    _print("evidence_refs", "; ".join(refs) if refs else "-")

    _print("freshness_status", proof.get("freshness_status") or evidence.get("freshness_status") or "unknown")
    changed = delta.get("changed_evidence_refs") or []
    _print("changed_evidence_summary", ",".join(changed) if changed else "none")

    if final_status == "pass":
        action = "Proceed with governed promotion path."
    elif final_status == "freeze":
        action = "Investigate freeze cause; remediate hard trust signal before retry."
    else:
        action = "Fix blocking reason and regenerate evidence index/proof bundle."
    _print("next_recommended_action", action)

    if final_status == "pass":
        return 0
    if final_status in {"block", "freeze"}:
        return 2
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
