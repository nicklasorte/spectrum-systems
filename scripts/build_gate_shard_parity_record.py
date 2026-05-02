#!/usr/bin/env python3
"""M3L-03 — Gate / Shard Parity Measurement builder.

Reads existing APR / CLP / M3L / shard-summary / per-shard artifacts and
emits a single ``gate_shard_parity_record`` measurement artifact that
captures whether APR, CLP, and the GitHub-driven shard runner reference
compatible EVL shard artifacts and report compatible shard statuses.

The builder is observation-only:

- It MUST NOT rerun tests.
- It MUST NOT invoke the shard runner.
- It MUST NOT recompute shard selection.
- It MUST NOT mutate any input artifact.
- It MUST NOT compute readiness or any gate signal.

Canonical owner systems remain unchanged; see
``docs/architecture/system_registry.md`` for the canonical registry.
The parity builder reads existing artifact refs only and emits
measurement observations only.

Exit codes
----------
0 — measurement record emitted (regardless of parity_status)
2 — at least one input path was supplied but unloadable
4 — internal builder error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import validate_artifact  # noqa: E402

DEFAULT_OUTPUT_REL_PATH = "outputs/gate_shard_parity/gate_shard_parity_record.json"
DEFAULT_APR_REL_PATH = "outputs/agent_pr_precheck/agent_pr_precheck_result.json"
DEFAULT_CLP_REL_PATH = "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json"
DEFAULT_M3L_REL_PATH = (
    "outputs/agent_3ls_path_measurement/agent_3ls_path_measurement_record.json"
)
DEFAULT_SUMMARY_REL_PATH = "outputs/pr_test_shards/pr_test_shards_summary.json"
DEFAULT_SHARD_DIR_REL_PATH = "outputs/pr_test_shards"


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _stable_record_id(work_item_id: str, created_at: str) -> str:
    raw = f"{work_item_id}|{created_at}".encode("utf-8")
    return "m3l-parity-" + hashlib.sha256(raw).hexdigest()[:16]


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _load_typed(path: Path | None, expected_type: str) -> dict[str, Any] | None:
    payload = _load_json(path)
    if payload is None:
        return None
    if payload.get("artifact_type") != expected_type:
        return None
    return payload


def load_apr_result(path: Path | None) -> dict[str, Any] | None:
    return _load_typed(path, "agent_pr_precheck_result")


def load_clp_result(path: Path | None) -> dict[str, Any] | None:
    return _load_typed(path, "core_loop_pre_pr_gate_result")


def load_m3l_result(path: Path | None) -> dict[str, Any] | None:
    return _load_typed(path, "agent_3ls_path_measurement_record")


def load_shard_summary(path: Path | None) -> dict[str, Any] | None:
    return _load_typed(path, "pr_test_shards_summary")


# ---------------------------------------------------------------------------
# Ref extraction helpers
# ---------------------------------------------------------------------------


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v]


def extract_apr_shard_refs(apr: Mapping[str, Any] | None) -> list[str]:
    """Pull APR's shard artifact refs from its `selected_test_refs` field.

    APR records the shard summary plus per-shard artifact paths in
    ``selected_test_refs`` after consuming the upstream
    ``pr_test_shards_summary``. The builder reads this field as-is; it
    does not recompute selection.
    """
    if apr is None:
        return []
    return list(_string_list(apr.get("selected_test_refs")))


def extract_clp_shard_refs(clp: Mapping[str, Any] | None) -> list[str]:
    """Pull CLP's shard artifact refs from its evl_shard_evidence section."""
    if clp is None:
        return []
    evidence = clp.get("evl_shard_evidence")
    if not isinstance(evidence, Mapping):
        return []
    return list(_string_list(evidence.get("evl_shard_artifact_refs")))


def extract_github_shard_refs(summary: Mapping[str, Any] | None) -> list[str]:
    """Pull GitHub-driven shard refs from the summary artifact."""
    if summary is None:
        return []
    refs = list(_string_list(summary.get("shard_artifact_refs")))
    summary_ref = summary.get("__self_ref")
    if isinstance(summary_ref, str) and summary_ref:
        if summary_ref not in refs:
            refs.insert(0, summary_ref)
    return refs


# ---------------------------------------------------------------------------
# Status classification helpers
# ---------------------------------------------------------------------------


def classify_apr_status(apr: Mapping[str, Any] | None) -> str:
    if apr is None:
        return "missing"
    status = apr.get("overall_status")
    if status in {"pass", "warn", "block", "human_review_required"}:
        return status
    return "unknown"


def classify_clp_status(clp: Mapping[str, Any] | None) -> str:
    if clp is None:
        return "missing"
    status = clp.get("gate_status")
    if status in {"pass", "warn", "block"}:
        return status
    return "unknown"


def classify_github_shard_status(summary: Mapping[str, Any] | None) -> str:
    """Derive a GitHub shard status from the upstream pr_test_shards summary.

    ``pass`` mirrors summary.overall_status == "pass". Any required-shard
    fail/missing/unknown surfaced by the summary's blocking_reasons collapses
    to ``fail`` / ``missing`` / ``unknown`` respectively. Otherwise ``block``
    mirrors summary.overall_status == "block".
    """
    if summary is None:
        return "missing"
    overall = summary.get("overall_status")
    if overall == "pass":
        return "pass"
    blocking = summary.get("blocking_reasons") or []
    if isinstance(blocking, list):
        # First blocking reason wins for status classification.
        for reason in blocking:
            if not isinstance(reason, str):
                continue
            if "required_shard_failed" in reason:
                return "fail"
            if "required_shard_missing" in reason:
                return "missing"
            if "required_shard_unknown" in reason:
                return "unknown"
    if overall == "block":
        return "block"
    return "unknown"


# ---------------------------------------------------------------------------
# Disk-presence check
# ---------------------------------------------------------------------------


def find_missing_artifact_refs(
    refs: list[str],
    *,
    repo_root: Path,
) -> list[str]:
    """Return refs whose resolved path does not exist on disk."""
    missing: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref in seen:
            continue
        seen.add(ref)
        candidate = (repo_root / ref).resolve() if not Path(ref).is_absolute() else Path(ref)
        if not candidate.is_file():
            missing.append(ref)
    return missing


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------


def _ref_set(refs: list[str]) -> set[str]:
    return {r for r in refs if isinstance(r, str) and r}


def _is_pass(status: str) -> bool:
    return status == "pass"


def _is_non_pass_failure(status: str) -> bool:
    """Statuses that should trigger ``github_escape`` / ``clp_github_mismatch``."""
    return status in {"fail", "block", "missing", "unknown"}


def detect_parity(
    *,
    apr_status: str,
    clp_status: str,
    github_shard_status: str,
    apr_shard_refs: list[str],
    clp_shard_refs: list[str],
    github_shard_refs: list[str],
    missing_artifact_refs: list[str],
    apr_present: bool,
    clp_present: bool,
    summary_present: bool,
) -> tuple[str, bool, bool, bool, list[dict[str, Any]], list[str]]:
    """Compute parity_status and the three mismatch booleans.

    Returns:
        (parity_status, github_escape, apr_clp_mismatch, clp_github_mismatch,
         mismatch_findings, reason_codes)
    """
    findings: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    # Step A — handle missing inputs (unknown).
    if not summary_present:
        reason_codes.append("shard_summary_missing")
    if not apr_present:
        reason_codes.append("apr_result_missing")
    if not clp_present:
        reason_codes.append("clp_result_missing")

    if not (summary_present and apr_present and clp_present):
        # Cannot evaluate parity without all three sources present.
        return ("unknown", False, False, False, findings, reason_codes)

    apr_set = _ref_set(apr_shard_refs)
    clp_set = _ref_set(clp_shard_refs)
    gh_set = _ref_set(github_shard_refs)

    apr_clp_mismatch = bool(apr_set) and bool(clp_set) and apr_set != clp_set
    if apr_clp_mismatch:
        only_apr = sorted(apr_set - clp_set)
        only_clp = sorted(clp_set - apr_set)
        findings.append(
            {
                "code": "apr_clp_shard_ref_mismatch",
                "message": (
                    "APR and CLP reference different shard artifact sets — "
                    f"APR-only: {only_apr}; CLP-only: {only_clp}"
                ),
                "artifact_refs": sorted(apr_set ^ clp_set),
            }
        )
        reason_codes.append("apr_clp_shard_ref_mismatch")

    apr_pass = _is_pass(apr_status)
    clp_pass = _is_pass(clp_status)
    gh_pass = _is_pass(github_shard_status)

    github_escape = apr_pass and _is_non_pass_failure(github_shard_status)
    if github_escape:
        findings.append(
            {
                "code": "github_escape_apr_pass_github_non_pass",
                "message": (
                    "APR overall_status is pass but GitHub shard status is "
                    f"{github_shard_status!r} — APR escape detected."
                ),
                "artifact_refs": sorted(gh_set),
            }
        )
        reason_codes.append("github_escape_apr_pass_github_non_pass")

    clp_github_mismatch = clp_pass and _is_non_pass_failure(github_shard_status)
    if clp_github_mismatch:
        findings.append(
            {
                "code": "clp_github_mismatch_clp_pass_github_non_pass",
                "message": (
                    "CLP gate_status is pass but GitHub shard status is "
                    f"{github_shard_status!r} — CLP/GitHub status drift."
                ),
                "artifact_refs": sorted(gh_set),
            }
        )
        reason_codes.append("clp_github_mismatch_clp_pass_github_non_pass")

    # Step B — record missing shard artifacts as a partial-parity finding.
    if missing_artifact_refs:
        findings.append(
            {
                "code": "shard_artifact_missing_on_disk",
                "message": (
                    "Shard artifact ref(s) not present on disk: "
                    f"{sorted(missing_artifact_refs)}"
                ),
                "artifact_refs": sorted(missing_artifact_refs),
            }
        )
        reason_codes.append("shard_artifact_missing_on_disk")

    # Step C — generic status drift (no specific mismatch above but the three
    # status fields disagree). For example: APR=warn, CLP=pass, GH=pass.
    statuses = (apr_status, clp_status, github_shard_status)
    aligned_pass = all(_is_pass(s) for s in statuses)
    if not aligned_pass and not (
        github_escape or clp_github_mismatch or apr_clp_mismatch
    ):
        findings.append(
            {
                "code": "shard_status_drift_observed",
                "message": (
                    "Shard statuses do not align across systems: "
                    f"apr={apr_status}, clp={clp_status}, github={github_shard_status}."
                ),
                "artifact_refs": [],
            }
        )
        reason_codes.append("shard_status_drift_observed")

    # Step D — classify parity_status.
    if missing_artifact_refs:
        parity_status = "partial"
    elif github_escape or clp_github_mismatch or apr_clp_mismatch:
        parity_status = "drift"
    elif aligned_pass and apr_set and clp_set and gh_set and apr_set == clp_set == gh_set:
        parity_status = "aligned"
    elif aligned_pass and (not apr_set or not clp_set or not gh_set):
        # Statuses align but at least one system reports no shard refs.
        findings.append(
            {
                "code": "shard_ref_set_empty_for_at_least_one_system",
                "message": (
                    "All systems report pass but at least one shard ref set "
                    f"is empty (apr={sorted(apr_set)}, clp={sorted(clp_set)}, "
                    f"github={sorted(gh_set)})."
                ),
                "artifact_refs": [],
            }
        )
        reason_codes.append("shard_ref_set_empty_for_at_least_one_system")
        parity_status = "partial"
    else:
        parity_status = "drift"

    # De-duplicate reason codes preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for code in reason_codes:
        if code in seen:
            continue
        seen.add(code)
        deduped.append(code)

    return (
        parity_status,
        github_escape,
        apr_clp_mismatch,
        clp_github_mismatch,
        findings,
        deduped,
    )


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------


def build_gate_shard_parity_record(
    *,
    work_item_id: str,
    base_ref: str,
    head_ref: str,
    apr_result: Mapping[str, Any] | None,
    clp_result: Mapping[str, Any] | None,
    m3l_result: Mapping[str, Any] | None,
    shard_summary: Mapping[str, Any] | None,
    apr_result_ref: str | None,
    clp_result_ref: str | None,
    m3l_result_ref: str | None,
    shard_summary_ref: str | None,
    repo_root: Path = REPO_ROOT,
    created_at: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    """Aggregate APR / CLP / M3L / shard-summary evidence into a parity record.

    Pure aggregation. No tests are run; no shard selection is recomputed;
    no upstream artifact is mutated.
    """
    ts = created_at or _utc_now_iso()
    rid = record_id or _stable_record_id(work_item_id, ts)

    apr_shard_refs = extract_apr_shard_refs(apr_result)
    clp_shard_refs = extract_clp_shard_refs(clp_result)
    github_shard_refs = extract_github_shard_refs(shard_summary)

    apr_status = classify_apr_status(apr_result)
    clp_status = classify_clp_status(clp_result)
    github_shard_status = classify_github_shard_status(shard_summary)

    # Aggregate shard_artifact_refs as union of all three systems' refs (sorted).
    all_refs: list[str] = []
    seen: set[str] = set()
    for ref in apr_shard_refs + clp_shard_refs + github_shard_refs:
        if ref not in seen:
            seen.add(ref)
            all_refs.append(ref)
    all_refs = sorted(all_refs)

    missing_refs = find_missing_artifact_refs(all_refs, repo_root=repo_root)

    (
        parity_status,
        github_escape,
        apr_clp_mismatch,
        clp_github_mismatch,
        mismatch_findings,
        reason_codes,
    ) = detect_parity(
        apr_status=apr_status,
        clp_status=clp_status,
        github_shard_status=github_shard_status,
        apr_shard_refs=apr_shard_refs,
        clp_shard_refs=clp_shard_refs,
        github_shard_refs=github_shard_refs,
        missing_artifact_refs=missing_refs,
        apr_present=apr_result is not None,
        clp_present=clp_result is not None,
        summary_present=shard_summary is not None,
    )

    record: dict[str, Any] = {
        "artifact_type": "gate_shard_parity_record",
        "schema_version": "1.0.0",
        "record_id": rid,
        "created_at": ts,
        "work_item_id": work_item_id,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "apr_result_ref": apr_result_ref,
        "clp_result_ref": clp_result_ref,
        "m3l_result_ref": m3l_result_ref,
        "shard_summary_ref": shard_summary_ref,
        "shard_artifact_refs": all_refs,
        "apr_shard_refs": list(apr_shard_refs),
        "clp_shard_refs": list(clp_shard_refs),
        "github_shard_refs": list(github_shard_refs),
        "apr_status": apr_status,
        "clp_status": clp_status,
        "github_shard_status": github_shard_status,
        "parity_status": parity_status,
        "github_escape": github_escape,
        "apr_clp_mismatch": apr_clp_mismatch,
        "clp_github_mismatch": clp_github_mismatch,
        "missing_artifact_refs": missing_refs,
        "mismatch_findings": mismatch_findings,
        "reason_codes": reason_codes,
        "authority_scope": "observation_only",
    }
    return record


def write_record(record: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="M3L-03 Gate / Shard Parity Measurement builder.",
    )
    parser.add_argument("--work-item-id", required=True)
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--apr-result", default=DEFAULT_APR_REL_PATH)
    parser.add_argument("--clp-result", default=DEFAULT_CLP_REL_PATH)
    parser.add_argument("--m3l-result", default=DEFAULT_M3L_REL_PATH)
    parser.add_argument("--shard-summary", default=DEFAULT_SUMMARY_REL_PATH)
    parser.add_argument(
        "--shard-artifact-dir",
        default=DEFAULT_SHARD_DIR_REL_PATH,
        help=(
            "Directory containing per-shard artifacts. Used only for "
            "presence checks; the builder never reads tests from this dir."
        ),
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT_REL_PATH)
    return parser.parse_args()


def _resolve(repo_root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    return p


def main() -> int:
    args = _parse_args()
    output_path = _resolve(REPO_ROOT, args.output)
    assert output_path is not None  # default is non-empty

    apr_path = _resolve(REPO_ROOT, args.apr_result)
    clp_path = _resolve(REPO_ROOT, args.clp_result)
    m3l_path = _resolve(REPO_ROOT, args.m3l_result)
    summary_path = _resolve(REPO_ROOT, args.shard_summary)

    apr = load_apr_result(apr_path)
    clp = load_clp_result(clp_path)
    m3l = load_m3l_result(m3l_path)
    summary = load_shard_summary(summary_path)

    invalid: list[str] = []
    if apr_path is not None and apr is None:
        invalid.append("apr")
    if clp_path is not None and clp is None:
        invalid.append("clp")
    if m3l_path is not None and m3l is None and m3l_path.is_file():
        # m3l is optional — only flag if the file exists but did not parse.
        invalid.append("m3l")
    if summary_path is not None and summary is None:
        invalid.append("shard_summary")

    record = build_gate_shard_parity_record(
        work_item_id=args.work_item_id,
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        apr_result=apr,
        clp_result=clp,
        m3l_result=m3l,
        shard_summary=summary,
        apr_result_ref=args.apr_result,
        clp_result_ref=args.clp_result,
        m3l_result_ref=args.m3l_result,
        shard_summary_ref=args.shard_summary,
    )

    validate_artifact(record, "gate_shard_parity_record")
    write_record(record, output_path)

    try:
        output_display = str(output_path.relative_to(REPO_ROOT))
    except ValueError:
        output_display = str(output_path)
    summary_out = {
        "parity_status": record["parity_status"],
        "github_escape": record["github_escape"],
        "apr_clp_mismatch": record["apr_clp_mismatch"],
        "clp_github_mismatch": record["clp_github_mismatch"],
        "missing_artifact_refs": record["missing_artifact_refs"],
        "reason_codes": record["reason_codes"],
        "output": output_display,
    }
    if invalid:
        summary_out["invalid_inputs"] = invalid
    print(json.dumps(summary_out, indent=2))
    return 2 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
