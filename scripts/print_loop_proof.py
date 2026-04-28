#!/usr/bin/env python3
"""NT-13..15: Operator triage CLI for loop proof bundles.

Renders an existing loop_proof_bundle artifact (and optionally its
certification_evidence_index and previous evidence index) so a new
maintainer can answer the questions the bundle was designed to answer
without reading raw JSON first:

  - final status (pass / block / freeze)
  - failed or passed stage
  - owning system for the failed stage
  - canonical reason category + detail reason
  - evidence references
  - delta summary (added / removed / changed evidence)
  - stale or current proof status (when a freshness audit is supplied)
  - next recommended action

The CLI is a renderer only. It does not invent decisions; every line
maps to an existing field on the proof artifact, the certification
evidence index, the certification delta, or the freshness audit.

Exit codes follow the pattern used by other governance scripts:
  0  pass
  1  block / freeze
  2  corrupt / missing required evidence
  3  unknown reason code surface (operator must triage further)
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


EXIT_PASS = 0
EXIT_BLOCK_OR_FREEZE = 1
EXIT_CORRUPT_OR_MISSING = 2
EXIT_UNKNOWN_REASON = 3


def _load_json(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _ref_block(bundle: Mapping[str, Any]) -> Dict[str, Optional[str]]:
    """Collect well-known ref keys without requiring every key to exist."""
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
    refs: Dict[str, Optional[str]] = {}
    for k in keys:
        v = bundle.get(k)
        refs[k] = v if isinstance(v, str) and v.strip() else None
    return refs


def _format_section(title: str, lines: list[str]) -> str:
    bar = "-" * max(40, len(title) + 4)
    return "\n".join([title, bar, *lines])


def render_proof(
    *,
    bundle: Mapping[str, Any],
    evidence_index: Optional[Mapping[str, Any]] = None,
    delta: Optional[Mapping[str, Any]] = None,
    freshness: Optional[Mapping[str, Any]] = None,
) -> str:
    """Render a human-readable triage view of the proof bundle."""
    final_status = str(bundle.get("final_status") or "unknown")
    canonical = bundle.get("canonical_blocking_category") or "-"
    trace_summary = bundle.get("trace_summary") or {}
    failed_stage = trace_summary.get("failed_stage") or "-"
    overall_stage_status = trace_summary.get("overall_status") or "-"
    owning_system = trace_summary.get("owning_system") or "-"
    one_page = trace_summary.get("one_page_summary") or ""

    detail_reason = "-"
    if isinstance(one_page, str) and "detail_reason_code:" in one_page:
        for line in one_page.splitlines():
            line = line.strip()
            if line.startswith("detail_reason_code:"):
                detail_reason = line.split(":", 1)[1].strip()
                break

    next_action = "-"
    if isinstance(one_page, str) and "next_recommended_action:" in one_page:
        for line in one_page.splitlines():
            line = line.strip()
            if line.startswith("next_recommended_action:"):
                next_action = line.split(":", 1)[1].strip()
                break

    summary_lines = [
        f"bundle_id: {bundle.get('bundle_id', '-')}",
        f"trace_id: {bundle.get('trace_id', '-')}",
        f"run_id: {bundle.get('run_id', '-')}",
        f"final_status: {final_status}",
        f"trace_overall_status: {overall_stage_status}",
        f"failed_stage: {failed_stage}",
        f"owning_system: {owning_system}",
        f"canonical_reason_category: {canonical}",
        f"detail_reason_code: {detail_reason}",
        f"next_recommended_action: {next_action}",
    ]

    refs = _ref_block(bundle)
    ref_lines = [f"{k}: {v or '-'}" for k, v in refs.items()]

    out_sections = [_format_section("LOOP PROOF — SUMMARY", summary_lines)]
    out_sections.append(_format_section("EVIDENCE REFS", ref_lines))

    if isinstance(evidence_index, Mapping):
        cei_lines = [
            f"index_id: {evidence_index.get('index_id', '-')}",
            f"status: {evidence_index.get('status', '-')}",
            f"blocking_reason_canonical: {evidence_index.get('blocking_reason_canonical', '-')}",
        ]
        codes = evidence_index.get("blocking_detail_codes") or []
        if isinstance(codes, list) and codes:
            cei_lines.append(f"blocking_detail_codes: {', '.join(str(c) for c in codes[:8])}")
        missing = evidence_index.get("missing_references") or []
        if isinstance(missing, list) and missing:
            cei_lines.append(f"missing_references: {', '.join(str(m) for m in missing)}")
        out_sections.append(_format_section("CERTIFICATION EVIDENCE INDEX", cei_lines))

    if isinstance(delta, Mapping):
        delta_lines = [
            f"overall_delta_risk: {delta.get('overall_delta_risk', '-')}",
            f"added: {len(delta.get('added_refs') or [])}",
            f"removed: {len(delta.get('removed_refs') or [])}",
            f"changed_digest: {len(delta.get('changed_digest') or [])}",
            f"changed_status: {len(delta.get('changed_status') or [])}",
            f"changed_reason: {len(delta.get('changed_reason') or [])}",
            f"changed_owner: {len(delta.get('changed_owner') or [])}",
            f"unchanged: {len(delta.get('unchanged_refs') or [])}",
        ]
        out_sections.append(_format_section("CERTIFICATION DELTA", delta_lines))

    if isinstance(freshness, Mapping):
        fresh_lines = [
            f"status: {freshness.get('status', '-')}",
            f"canonical_reason: {freshness.get('canonical_reason', '-')}",
            f"stale_kinds: {', '.join(freshness.get('stale_kinds') or []) or '-'}",
            f"unknown_kinds: {', '.join(freshness.get('unknown_kinds') or []) or '-'}",
        ]
        out_sections.append(_format_section("PROOF FRESHNESS", fresh_lines))

    if isinstance(one_page, str) and one_page.strip():
        out_sections.append(_format_section("ONE-PAGE TRACE", [one_page]))

    return "\n\n".join(out_sections) + "\n"


def determine_exit_code(
    *,
    bundle: Mapping[str, Any],
    evidence_index: Optional[Mapping[str, Any]] = None,
    freshness: Optional[Mapping[str, Any]] = None,
) -> int:
    """Map proof state to a stable exit code."""
    final_status = str(bundle.get("final_status") or "").lower()
    canonical = str(bundle.get("canonical_blocking_category") or "").upper()

    if final_status not in {"pass", "block", "freeze"}:
        return EXIT_CORRUPT_OR_MISSING

    if isinstance(evidence_index, Mapping):
        cei_status = str(evidence_index.get("status") or "").lower()
        if cei_status == "frozen" or final_status == "freeze":
            return EXIT_BLOCK_OR_FREEZE
        if cei_status == "blocked" and final_status == "pass":
            # Inconsistent — bundle says pass but evidence index blocked.
            return EXIT_CORRUPT_OR_MISSING

    if isinstance(freshness, Mapping):
        if str(freshness.get("status") or "").lower() == "stale":
            return EXIT_BLOCK_OR_FREEZE

    if final_status == "pass":
        return EXIT_PASS
    if final_status in {"block", "freeze"}:
        if canonical == "UNKNOWN":
            return EXIT_UNKNOWN_REASON
        return EXIT_BLOCK_OR_FREEZE

    return EXIT_CORRUPT_OR_MISSING


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a loop proof bundle for operator triage. Reads the "
            "bundle JSON and prints summary, evidence refs, optional "
            "certification index, optional delta vs prior index, optional "
            "freshness audit, and the one-page trace. Exit code maps to "
            "pass / block-or-freeze / corrupt / unknown-reason."
        )
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="Path to loop_proof_bundle JSON",
    )
    parser.add_argument(
        "--evidence-index",
        type=Path,
        default=None,
        help="Optional path to certification_evidence_index JSON",
    )
    parser.add_argument(
        "--delta",
        type=Path,
        default=None,
        help="Optional path to certification_delta JSON",
    )
    parser.add_argument(
        "--freshness",
        type=Path,
        default=None,
        help="Optional path to trust_artifact_freshness_audit JSON",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        bundle = _load_json(args.bundle)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[print_loop_proof] {exc}", file=sys.stderr)
        return EXIT_CORRUPT_OR_MISSING

    if not isinstance(bundle, Mapping):
        print("[print_loop_proof] bundle is not a JSON object", file=sys.stderr)
        return EXIT_CORRUPT_OR_MISSING

    if str(bundle.get("artifact_type") or "") != "loop_proof_bundle":
        print(
            "[print_loop_proof] bundle artifact_type != loop_proof_bundle",
            file=sys.stderr,
        )
        return EXIT_CORRUPT_OR_MISSING

    try:
        evidence_index = _load_json(args.evidence_index)
        delta = _load_json(args.delta)
        freshness = _load_json(args.freshness)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[print_loop_proof] {exc}", file=sys.stderr)
        return EXIT_CORRUPT_OR_MISSING

    output = render_proof(
        bundle=bundle,
        evidence_index=evidence_index,
        delta=delta,
        freshness=freshness,
    )
    print(output)

    return determine_exit_code(
        bundle=bundle,
        evidence_index=evidence_index,
        freshness=freshness,
    )


if __name__ == "__main__":
    sys.exit(main())
