#!/usr/bin/env python3
"""CL-25 thin CLI — render a core_loop_proof artifact for an operator.

Loads an existing ``core_loop_proof`` JSON file and prints a compact,
human-readable view that surfaces the terminal status, the elected
primary canonical reason, supporting reasons, per-stage status, and
transition continuity. The CLI is a renderer only; canonical authority
remains with AEX, PQX, EVL, TPA, CDE, SEL.

Exit codes:
  0  pass
  1  block / freeze
  2  invalid / missing / corrupt artifact
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


EXIT_PASS = 0
EXIT_BLOCK_OR_FREEZE = 1
EXIT_CORRUPT = 2


def _load_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render(proof: Mapping[str, Any]) -> str:
    if proof.get("artifact_type") != "core_loop_proof":
        raise ValueError(
            f"unexpected artifact_type: {proof.get('artifact_type')!r}"
        )

    lines = []
    lines.append("=" * 64)
    lines.append(
        f"CORE LOOP PROOF  proof_id={proof.get('proof_id')}  trace_id={proof.get('trace_id')}"
    )
    lines.append(f"audit_timestamp: {proof.get('audit_timestamp')}")
    lines.append(f"terminal_status: {proof.get('terminal_status')}")
    primary = proof.get("primary_reason") or {}
    lines.append("")
    lines.append("PRIMARY REASON")
    lines.append(f"  reason_code:        {primary.get('primary_canonical_reason')}")
    lines.append(f"  source_stage:       {primary.get('source_stage')}")
    lines.append(f"  next_allowed_action: {primary.get('next_allowed_action')}")
    failing = primary.get("failing_artifact_refs") or []
    if failing:
        lines.append("  failing_artifact_refs:")
        for r in failing:
            lines.append(f"    - {r}")
    supporting = primary.get("supporting_reasons") or []
    if supporting:
        lines.append("  supporting_reasons:")
        for s in supporting:
            lines.append(
                f"    - {s.get('reason_code')} (stage={s.get('stage')}) {s.get('detail') or ''}".rstrip()
            )

    lines.append("")
    lines.append("STAGES")
    stages = proof.get("stages") or {}
    for stage in ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL"):
        rec = stages.get(stage) or {}
        lines.append(
            f"  {stage}  status={rec.get('status', '-'):8} ref={rec.get('artifact_ref') or '-':32} reason={rec.get('reason_code') or '-'}"
        )

    lines.append("")
    lines.append("TRANSITIONS")
    for t in proof.get("transitions") or []:
        lines.append(
            f"  {t.get('from_stage')}->{t.get('to_stage')}  status={t.get('status', '-'):8} reason={t.get('reason_code') or '-'}"
        )

    lines.append("")
    lines.append(
        f"trace_continuity_ok: {proof.get('trace_continuity_ok')}  lineage={proof.get('lineage_chain_ref') or '-'}  replay={proof.get('replay_record_ref') or '-'}"
    )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Print core_loop_proof artifact")
    parser.add_argument(
        "--path",
        type=Path,
        default=REPO_ROOT / "contracts" / "examples" / "core_loop_proof.json",
        help="Path to a core_loop_proof JSON artifact.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON instead of the human-readable view.",
    )
    args = parser.parse_args(argv)

    try:
        proof = _load_json(args.path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CORRUPT

    if args.json:
        print(json.dumps(proof, indent=2))
    else:
        try:
            print(_render(proof))
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_CORRUPT

    status = (proof.get("terminal_status") or "").lower()
    if status == "pass":
        return EXIT_PASS
    if status in ("block", "freeze"):
        return EXIT_BLOCK_OR_FREEZE
    return EXIT_CORRUPT


if __name__ == "__main__":
    sys.exit(main())
