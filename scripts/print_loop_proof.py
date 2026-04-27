#!/usr/bin/env python3
"""NT-13: Operator triage CLI for loop proof bundles.

Read-only renderer for ``loop_proof_bundle`` and (optionally)
``certification_evidence_index``. The CLI does not contain business logic
— it formats existing proof/evidence signals for a maintainer.

Usage:
    python scripts/print_loop_proof.py <loop_proof_bundle.json> \\
        [--certification-evidence-index <cei.json>] \\
        [--previous <prev_loop_proof_bundle.json>]

Exit codes:
    0  — final_status == "pass"
    2  — final_status == "block"
    3  — final_status == "freeze"
    4  — corrupt or unreadable proof / missing required fields
    5  — unknown status (treated as block-equivalent for triage)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.governance.proof_bundle_size import (  # noqa: E402
    ProofBundleSizeError,
    validate_proof_bundle_size,
)
from spectrum_systems.modules.observability.reason_code_canonicalizer import (  # noqa: E402
    canonicalize_reason_code,
)
from spectrum_systems.modules.observability.trust_artifact_freshness import (  # noqa: E402
    TrustArtifactFreshnessError,
    audit_artifact_freshness,
)


EXIT_PASS = 0
EXIT_BLOCK = 2
EXIT_FREEZE = 3
EXIT_CORRUPT = 4
EXIT_UNKNOWN = 5


REQUIRED_BUNDLE_FIELDS = (
    "artifact_type",
    "bundle_id",
    "trace_id",
    "final_status",
)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _summarize_evidence_refs(bundle: Mapping[str, Any]) -> List[str]:
    out: List[str] = []
    for key in (
        "execution_record_ref",
        "output_artifact_ref",
        "eval_summary_ref",
        "control_decision_ref",
        "enforcement_action_ref",
        "replay_record_ref",
        "lineage_chain_ref",
        "certification_evidence_index_ref",
        "failure_trace_ref",
    ):
        v = bundle.get(key)
        if v:
            out.append(f"  {key}: {v}")
        else:
            out.append(f"  {key}: -")
    return out


def _changed_evidence_summary(
    current: Mapping[str, Any],
    previous: Optional[Mapping[str, Any]],
) -> List[str]:
    if previous is None:
        return ["  (no previous bundle supplied)"]
    keys = (
        "execution_record_ref",
        "output_artifact_ref",
        "eval_summary_ref",
        "control_decision_ref",
        "enforcement_action_ref",
        "replay_record_ref",
        "lineage_chain_ref",
        "certification_evidence_index_ref",
        "failure_trace_ref",
    )
    lines: List[str] = []
    for k in keys:
        c = current.get(k)
        p = previous.get(k)
        if c != p:
            lines.append(f"  {k}: {p or '-'} -> {c or '-'}")
    if not lines:
        lines.append("  (no changes since previous bundle)")
    return lines


def _next_action_for_status(
    bundle: Mapping[str, Any],
    cei: Optional[Mapping[str, Any]],
) -> str:
    final_status = bundle.get("final_status")
    if final_status == "pass":
        return "Promote: certification ready, control allowed, trace ok."
    trace = bundle.get("trace_summary") or {}
    failed_stage = trace.get("failed_stage")
    if final_status == "freeze":
        return (
            "Investigate freeze cause; halt promotion until upstream signal "
            "clears. Inspect SLO posture, control decision, certification index."
        )
    # block
    if failed_stage:
        return (
            f"Inspect failing stage {failed_stage!r} ({trace.get('owning_system') or '?'}) "
            "and remediate root cause."
        )
    if cei is not None:
        details = cei.get("blocking_detail_codes") or []
        if details:
            return f"Resolve blocking detail codes: {', '.join(details)}"
    return "Inspect bundle.canonical_blocking_category and certification evidence index."


def _render(
    bundle: Mapping[str, Any],
    cei: Optional[Mapping[str, Any]],
    previous: Optional[Mapping[str, Any]],
) -> str:
    final_status = str(bundle.get("final_status") or "unknown")
    canonical_blocking = bundle.get("canonical_blocking_category") or "-"
    trace = bundle.get("trace_summary") or {}
    failed_stage = trace.get("failed_stage") or "-"
    owning_system = trace.get("owning_system") or "-"
    overall_status = trace.get("overall_status") or "-"
    bundle_id = bundle.get("bundle_id") or "-"
    trace_id = bundle.get("trace_id") or "-"

    detail_code = "-"
    if final_status != "pass":
        # Look in failure_trace.primary_reason_code if attached, else
        # fall back to one_page_summary parsing
        if isinstance(bundle.get("primary_reason_code"), str):
            detail_code = bundle["primary_reason_code"]
        else:
            one_page = str(trace.get("one_page_summary") or "")
            for line in one_page.splitlines():
                if line.strip().startswith("detail_reason_code:"):
                    detail_code = line.split(":", 1)[1].strip() or "-"
                    break

    canon = canonicalize_reason_code(detail_code if detail_code != "-" else "")
    canonical_category = (
        canonical_blocking
        if canonical_blocking and canonical_blocking != "-"
        else (canon["canonical_category"] if canon["canonical_category"] != "UNKNOWN" else "-")
    )

    # Freshness check: best-effort against the bundle itself
    freshness_status = "unknown"
    try:
        freshness = audit_artifact_freshness(bundle)
        freshness_status = freshness["status"]
    except TrustArtifactFreshnessError:
        freshness_status = "unknown"

    # Size validation check (advisory in CLI; we still render even if blocked)
    size_status = "unknown"
    size_block_reasons: List[str] = []
    try:
        size_res = validate_proof_bundle_size(bundle)
        size_status = size_res["decision"]
        size_block_reasons = size_res.get("blocking_reasons") or []
    except ProofBundleSizeError:
        size_status = "unknown"

    cei_status = "-"
    cei_blocking = "-"
    if cei is not None:
        cei_status = str(cei.get("status") or "-")
        cei_blocking = str(cei.get("blocking_reason_canonical") or "-")

    lines: List[str] = []
    lines.append(f"LOOP PROOF — bundle_id={bundle_id} trace_id={trace_id}")
    lines.append("-" * 64)
    lines.append(f"final_status:               {final_status}")
    lines.append(f"overall_trace_status:       {overall_status}")
    lines.append(f"failed_or_passed_stage:     {failed_stage if failed_stage else '-'}")
    lines.append(f"owning_system:              {owning_system}")
    lines.append(f"canonical_reason_category:  {canonical_category}")
    lines.append(f"detail_reason_code:         {detail_code}")
    lines.append(f"freshness_status:           {freshness_status}")
    lines.append(f"size_validation:            {size_status}")
    if size_block_reasons:
        lines.append(f"size_block_reasons:         {'; '.join(size_block_reasons[:3])}")
    if cei is not None:
        lines.append(f"cert_index_status:          {cei_status}")
        lines.append(f"cert_index_block_canonical: {cei_blocking}")
    lines.append("")
    lines.append("evidence_refs:")
    lines.extend(_summarize_evidence_refs(bundle))
    lines.append("")
    lines.append("changed_evidence_since_previous:")
    lines.extend(_changed_evidence_summary(bundle, previous))
    lines.append("")
    lines.append(f"next_recommended_action: {_next_action_for_status(bundle, cei)}")
    lines.append("")
    one_page = trace.get("one_page_summary")
    if isinstance(one_page, str) and one_page.strip():
        lines.append("--- one-page trace ---")
        lines.append(one_page)
    return "\n".join(lines)


def _validate_required(bundle: Mapping[str, Any]) -> List[str]:
    missing: List[str] = []
    for k in REQUIRED_BUNDLE_FIELDS:
        if k not in bundle or bundle.get(k) in (None, ""):
            missing.append(k)
    if str(bundle.get("artifact_type") or "") != "loop_proof_bundle":
        missing.append("artifact_type==loop_proof_bundle")
    return missing


def _exit_code_for_status(final_status: str) -> int:
    if final_status == "pass":
        return EXIT_PASS
    if final_status == "block":
        return EXIT_BLOCK
    if final_status == "freeze":
        return EXIT_FREEZE
    return EXIT_UNKNOWN


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a loop proof bundle in a triage-friendly form."
    )
    parser.add_argument(
        "loop_proof_bundle_path",
        help="Path to a loop_proof_bundle JSON artifact.",
    )
    parser.add_argument(
        "--certification-evidence-index",
        dest="cei_path",
        default=None,
        help="Optional path to a certification_evidence_index JSON artifact.",
    )
    parser.add_argument(
        "--previous",
        dest="previous_path",
        default=None,
        help="Optional path to a previous loop_proof_bundle for diff.",
    )
    args = parser.parse_args(argv)

    bundle_path = Path(args.loop_proof_bundle_path)
    try:
        bundle = _read_json(bundle_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"CORRUPT_OR_MISSING: {exc}", file=sys.stderr)
        return EXIT_CORRUPT

    if not isinstance(bundle, dict):
        print("CORRUPT: root must be a JSON object", file=sys.stderr)
        return EXIT_CORRUPT

    missing = _validate_required(bundle)
    if missing:
        print(f"CORRUPT_OR_MISSING_REQUIRED: {', '.join(missing)}", file=sys.stderr)
        return EXIT_CORRUPT

    cei: Optional[Dict[str, Any]] = None
    if args.cei_path:
        try:
            cei = _read_json(Path(args.cei_path))
        except (FileNotFoundError, ValueError) as exc:
            print(f"CORRUPT_CEI: {exc}", file=sys.stderr)
            return EXIT_CORRUPT

    previous: Optional[Dict[str, Any]] = None
    if args.previous_path:
        try:
            previous = _read_json(Path(args.previous_path))
        except (FileNotFoundError, ValueError) as exc:
            print(f"CORRUPT_PREVIOUS: {exc}", file=sys.stderr)
            return EXIT_CORRUPT

    print(_render(bundle, cei, previous))

    return _exit_code_for_status(str(bundle.get("final_status") or "unknown"))


if __name__ == "__main__":
    raise SystemExit(main())
