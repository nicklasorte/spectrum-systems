#!/usr/bin/env python3
"""Run deterministic PRA→NSX→PRG automation chain with workflow-level SLH hardening checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.runtime.pra_nsx_prg_loop import (  # noqa: E402
    PRAnchorError,
    build_resolution_failure_record,
    build_pr_anchor,
    build_pr_delta,
    cde_execution_mode,
    con_workflow_coverage_audit,
    con_workflow_front_door_enforcement,
    extract_changed_scope,
    extract_ci_review_findings,
    final_proofs,
    fre_failure_class_rerun_lock,
    get_repo_name,
    map_system_impact,
    normalize_pr_metadata,
    nsx_records,
    parse_pr_override,
    prg_records,
    red_team_and_fix_pack,
    resolve_pull_request,
    weak_seam_audits,
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run PRA/NSX/PRG governed automation loop")
    parser.add_argument("--pr-input", required=True, help="JSON payload with key pull_requests")
    parser.add_argument("--previous-anchor", help="Optional previous anchor artifact")
    parser.add_argument("--pr-number", type=int, help="Manual PR number input")
    parser.add_argument("--pr-url", help="Manual PR URL input")
    parser.add_argument("--output-dir", default="outputs/pra_nsx_prg")
    args = parser.parse_args(argv)

    payload = _read_json(Path(args.pr_input))
    repo_name = str(payload.get("repo_name") or get_repo_name(REPO_ROOT))
    pull_requests = payload.get("pull_requests") if isinstance(payload.get("pull_requests"), list) else []

    override = None
    try:
        override = parse_pr_override(pr_number=args.pr_number, pr_url=args.pr_url)
        resolution, selected_raw = resolve_pull_request(pull_requests=pull_requests, repo_name=repo_name, override=override)
    except PRAnchorError as exc:
        blocked = build_resolution_failure_record(repo_name=repo_name, reason=str(exc), override=override)
        out = Path(args.output_dir) / "pra_pull_request_resolution_record.json"
        _write(out, blocked)
        print(json.dumps({"status": "blocked", "reason": str(exc), "resolution_artifact": str(out)}, indent=2))
        return 1

    normalized = normalize_pr_metadata(pr_data=selected_raw)
    changed_scope = extract_changed_scope(normalized=normalized)
    ci_review = extract_ci_review_findings(normalized=normalized)
    impact = map_system_impact(changed_scope=changed_scope, ci_review=ci_review)
    anchor = build_pr_anchor(resolution=resolution, normalized=normalized, changed_scope=changed_scope, ci_review=ci_review)

    previous_anchor = _read_json(Path(args.previous_anchor)) if args.previous_anchor else None
    try:
        delta = build_pr_delta(previous_anchor=previous_anchor, current_anchor=anchor, impact=impact)
    except PRAnchorError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc), "previous_anchor": args.previous_anchor}, indent=2))
        return 1

    workflow_audit = con_workflow_coverage_audit(repo_root=REPO_ROOT)
    workflow_enforcement = con_workflow_front_door_enforcement(coverage=workflow_audit)
    rerun_lock = fre_failure_class_rerun_lock(
        failure_class="workflow_bypass" if workflow_enforcement.get("status") == "fail" else "runtime",
        targeted_subset=["tests/test_shift_left_preflight.py"],
        attempted_full_pytest=False,
    )
    weak = weak_seam_audits(anchor=anchor)
    weak["workflow"] = workflow_enforcement

    nsx = nsx_records(anchor=anchor, impact=impact, weak_seams=weak)
    prg = prg_records(anchor=anchor, nsx=nsx, delta=delta)
    cde = cde_execution_mode(anchor=anchor, weak=weak)
    rtfx = red_team_and_fix_pack(anchor=anchor, prg=prg)
    proofs = final_proofs(anchor=anchor, nsx=nsx, prg=prg, workflow=workflow_enforcement)

    output_dir = Path(args.output_dir)
    artifacts = [resolution, normalized, changed_scope, ci_review, impact, anchor, delta, workflow_audit, workflow_enforcement, rerun_lock, *weak.values(), *nsx.values(), *prg.values(), cde, *rtfx.values(), *proofs.values()]
    for artifact in artifacts:
        _write(output_dir / f"{artifact['artifact_type']}.json", artifact)

    summary = {
        "status": "pass" if cde.get("decision") != "halt" else "blocked",
        "repo_name": repo_name,
        "pr_number": anchor.get("pr_number"),
        "artifact_count": len(artifacts),
        "output_dir": str(output_dir),
        "execution_mode": cde.get("decision"),
    }
    _write(output_dir / "pra_nsx_prg_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
