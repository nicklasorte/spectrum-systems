#!/usr/bin/env python3
"""Aggregator: load shard selection and result artifacts, validate them, and
write a final PR gate result.

This script aggregates evidence only.  It does NOT call any selection
functions, recompute which tests should run, or make gate-outcome calls.
Authority scope: observation_only.

Fail-closed: any exception → exit 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_DEFAULT_SHARD_DIR = str(REPO_ROOT / "outputs" / "pr_test_shards")
_DEFAULT_OUTPUT = str(REPO_ROOT / "outputs" / "pr_gate" / "pr_gate_result.json")
_DEFAULT_REQUIRED_SHARDS = "contract,governance,dashboard,changed_scope"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate shard artifacts and write a PR gate result.",
    )
    parser.add_argument(
        "--shard-dir",
        default=_DEFAULT_SHARD_DIR,
        help=f"Base directory for shard artifacts (default: {_DEFAULT_SHARD_DIR}).",
    )
    parser.add_argument(
        "--output",
        default=_DEFAULT_OUTPUT,
        help=f"Path for the gate result JSON (default: {_DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--required-shards",
        default=_DEFAULT_REQUIRED_SHARDS,
        help=(
            "Comma-separated list of required shard names "
            f"(default: {_DEFAULT_REQUIRED_SHARDS})."
        ),
    )
    parser.add_argument(
        "--shard-matrix-result",
        default="",
        help="GitHub Actions matrix result for shard-select job (success/failure/cancelled).",
    )
    return parser.parse_args()


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Return (parsed_dict, None) on success or (None, error_message) on failure."""
    if not path.is_file():
        return None, f"file not found: {path}"
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"json parse error in {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"expected JSON object in {path}, got {type(payload).__name__}"
    return payload, None


def _check_parity(shard_dir: Path) -> str:
    """Return 'pass', 'fail', or 'not_checked' for CI/precheck parity."""
    parity_path = shard_dir / "precheck_selection_parity.json"
    if not parity_path.is_file():
        return "not_checked"
    payload, err = _load_json_file(parity_path)
    if err or payload is None:
        return "not_checked"
    parity_status = payload.get("parity_status", "not_checked")
    if parity_status in ("pass", "fail"):
        return parity_status
    return "not_checked"


def _validate_selection(artifact: dict[str, Any], shard: str) -> str | None:
    """Return blocking reason string or None if valid."""
    if artifact.get("artifact_type") != "pr_test_shard_selection":
        return "invalid_shard_selection_artifact"
    return None


def _validate_result(artifact: dict[str, Any], shard: str) -> str | None:
    """Return blocking reason string or None if valid."""
    if artifact.get("artifact_type") != "pr_test_shard_result":
        return "invalid_shard_result_artifact"
    if artifact.get("authority_scope") != "observation_only":
        return "invalid_authority_scope"
    return None


def _evaluate_shard(
    shard: str,
    shard_dir: Path,
) -> tuple[str, str | None]:
    """Return (shard_status_label, blocking_reason | None).

    shard_status_label is a short string for reporting ('ok', 'block', etc.)
    """
    shard_path = shard_dir / shard

    # (a) Load selection artifact.
    selection_path = shard_path / f"{shard}_selection.json"
    selection, err = _load_json_file(selection_path)
    if err or selection is None:
        return "missing_selection", "missing_shard_selection_artifact"

    # (b) Validate selection.
    sel_reason = _validate_selection(selection, shard)
    if sel_reason:
        return "invalid_selection", sel_reason

    # (c) Load result artifact.
    result_path = shard_path / f"{shard}_result.json"
    result, err = _load_json_file(result_path)
    if err or result is None:
        return "missing_result", "missing_shard_result_artifact"

    # (d) Validate result.
    res_reason = _validate_result(result, shard)
    if res_reason:
        return "invalid_result", res_reason

    # (e) authority_scope already checked by _validate_result.

    # (f) Check selection status / result status.
    sel_status = selection.get("status", "")
    res_status = result.get("status", "")

    if sel_status == "block":
        return "blocked_selection", "shard_selection_blocked"

    if sel_status == "empty_allowed":
        if res_status == "skipped":
            return "ok_empty", None
        # If selection was empty_allowed but result was not skipped, treat as ok
        # (shard ran even though it could have been skipped — that is conservative).
        return "ok", None

    if sel_status == "selected":
        if res_status == "skipped":
            return "skipped_required", "skipped_required_shard"
        if res_status in ("fail", "block"):
            return "failed", "shard_failed"
        if res_status in ("pass", "ok"):
            return "ok", None
        # Unrecognized result status for a required shard — fail closed.
        return "failed", "unknown_shard_result_status"

    # Unrecognized selection status — fail closed rather than defaulting to pass.
    return "failed", "unknown_shard_selection_status"


def main() -> int:
    args = _parse_args()
    shard_dir = Path(args.shard_dir)
    output_path = Path(args.output)
    required_shards = [s.strip() for s in args.required_shards.split(",") if s.strip()]

    shard_statuses: dict[str, str] = {}
    blocking_reasons: list[str] = []
    trace_refs: list[str] = []

    # (a) Check whether the upstream shard-select matrix concluded successfully.
    matrix_result = (args.shard_matrix_result or "").strip().lower()
    if matrix_result and matrix_result != "success":
        blocking_reasons.append(f"shard_matrix_failed:{matrix_result}")
        trace_refs.append(f"shard_matrix_result={matrix_result}")

    for shard in required_shards:
        label, reason = _evaluate_shard(shard, shard_dir)
        shard_statuses[shard] = label
        if reason:
            blocking_reasons.append(f"{shard}:{reason}")
            trace_refs.append(f"shard={shard} label={label} reason={reason}")
        else:
            trace_refs.append(f"shard={shard} label={label}")

    # (g) CI/precheck parity check — parity failure is a blocking condition.
    parity_status = _check_parity(shard_dir)
    if parity_status == "fail":
        blocking_reasons.append("parity_check_failed")
        trace_refs.append("parity_status=fail")

    gate_status = "block" if blocking_reasons else "pass"

    artifact: dict[str, Any] = {
        "artifact_type": "pr_gate_result",
        "schema_version": "1.0.0",
        "status": gate_status,
        "required_shards": required_shards,
        "shard_statuses": shard_statuses,
        "blocking_reasons": blocking_reasons,
        "parity_status": parity_status,
        "authority_scope": "observation_only",
        "produced_at": datetime.now(timezone.utc).isoformat(),
        "trace_refs": trace_refs,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")

    if gate_status == "block":
        print(
            f"[run_pr_gate] BLOCK reasons={blocking_reasons}",
            file=sys.stderr,
        )
        return 1

    print(f"[run_pr_gate] PASS all shards OK → {output_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[run_pr_gate] FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
