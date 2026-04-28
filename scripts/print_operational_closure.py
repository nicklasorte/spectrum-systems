#!/usr/bin/env python3
"""OC-25: Operator CLI — render the operational closure bundle.

Reads supplied evidence files (proof intake, bottleneck classification,
dashboard projection, closure packet, fast trust gate run, work
selection record, operator runbook entry) and renders a single
human-readable summary that an operator can use to identify the
correct next action.

Exit codes:
  0  pass
  1  block
  2  freeze
  3  unknown / insufficient evidence

The CLI is a renderer only. It does not invent decisions; every line
maps to an existing field on the supplied evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.operational_closure_bundle import (  # noqa: E402
    build_operational_closure_bundle,
)


EXIT_PASS = 0
EXIT_BLOCK = 1
EXIT_FREEZE = 2
EXIT_UNKNOWN = 3


def _load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def render(bundle: Mapping[str, Any]) -> str:
    q = bundle.get("operator_questions") or {}
    refs = bundle.get("evidence_refs") or {}
    lines = [
        f"bundle_id: {bundle.get('bundle_id', '-')}",
        f"audit_timestamp: {bundle.get('audit_timestamp', '-')}",
        f"overall_status: {bundle.get('overall_status', 'unknown')}",
        f"current_bottleneck: {q.get('current_bottleneck_label', '-')}",
        f"owning_three_letter_system: {q.get('owning_three_letter_system', '-')}",
        f"supporting_proof_ref: {q.get('proof_artifact_label', '-')}",
        f"dashboard_aligned_with_repo_truth: {q.get('dashboard_aligned_with_repo_truth', '-')}",
        f"fast_trust_gate_sufficient: {q.get('fast_trust_gate_sufficient', '-')}",
        f"next_work_item: {q.get('next_work_item_label', '-')}",
        f"justifying_failure_or_signal: {q.get('justifying_failure_or_signal', '-')}",
        "",
        "evidence_refs:",
    ]
    for k, v in sorted(refs.items()):
        lines.append(f"  {k}: {v if v else '-'}")
    return "\n".join(lines)


def status_to_exit(status: str) -> int:
    if status == "pass":
        return EXIT_PASS
    if status == "freeze":
        return EXIT_FREEZE
    if status == "block":
        return EXIT_BLOCK
    return EXIT_UNKNOWN


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render the OC-25 operational closure bundle for operator triage."
        )
    )
    parser.add_argument("--proof-intake", type=Path, default=None)
    parser.add_argument("--bottleneck", type=Path, default=None)
    parser.add_argument("--dashboard-projection", type=Path, default=None)
    parser.add_argument("--closure-packet", type=Path, default=None)
    parser.add_argument("--fast-trust-gate-run", type=Path, default=None)
    parser.add_argument("--work-selection", type=Path, default=None)
    parser.add_argument("--runbook", type=Path, default=None)
    parser.add_argument(
        "--bundle-id",
        type=str,
        default="ocb-cli-1",
        help="bundle id to write into the rendered artifact",
    )
    parser.add_argument(
        "--audit-timestamp",
        type=str,
        default="1970-01-01T00:00:00Z",
        help="audit timestamp to embed in the rendered artifact",
    )
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="print the underlying JSON bundle alongside the text summary",
    )
    args = parser.parse_args(argv)

    bundle = build_operational_closure_bundle(
        bundle_id=args.bundle_id,
        audit_timestamp=args.audit_timestamp,
        proof_intake=_load_json(args.proof_intake),
        bottleneck_classification=_load_json(args.bottleneck),
        dashboard_projection=_load_json(args.dashboard_projection),
        closure_packet=_load_json(args.closure_packet),
        fast_trust_gate_run=_load_json(args.fast_trust_gate_run),
        work_selection_record=_load_json(args.work_selection),
        operator_runbook_entry=_load_json(args.runbook),
    )

    print(render(bundle))
    if args.emit_json:
        print()
        print(json.dumps(bundle, indent=2, sort_keys=True))

    return status_to_exit(str(bundle.get("overall_status", "unknown")))


if __name__ == "__main__":
    raise SystemExit(main())
