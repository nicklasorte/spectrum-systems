#!/usr/bin/env python3
"""PRL Pre-PR Reliability Gate.

Runs all governed preflight checks, captures failures as structured PRL artifacts,
generates repair candidates and eval candidates, and emits a prl_gate_result.

Gate signal mapping:
  failed_gate — schema violation, registry mismatch, authority violation, trace missing
  gate_hold   — unknown_failure, replay mismatch, timeout, rate limited
  gate_warn   — non-critical pytest failures
  passed_gate — zero failures

Exit codes:
  0  — passed_gate
  1  — failed_gate or gate_hold
  2  — gate_warn (non-zero to surface warnings in CI; can be overridden per policy)

All output is emitted to stdout as newline-delimited JSON artifact records.
The final line is the prl_gate_result.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.modules.prl.failure_parser import parse_log
from spectrum_systems.modules.prl.failure_classifier import (
    classify,
    aggregate_gate_signal,
)
from spectrum_systems.modules.prl.artifact_builder import (
    build_capture_record,
    build_failure_packet,
)
from spectrum_systems.modules.prl.repair_generator import generate_repair_candidate
from spectrum_systems.modules.prl.eval_generator import (
    generate_eval_case_candidate,
    advance_to_eval_case,
    build_generation_record,
)
from spectrum_systems.utils.artifact_envelope import build_artifact_envelope
from spectrum_systems.utils.deterministic_id import deterministic_id

import jsonschema

_PRL_SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"prl-gate-{ts}-{suffix}"


def _new_trace_id() -> str:
    return f"trace-prl-{uuid.uuid4().hex[:16]}"


def _emit(artifact: dict[str, Any]) -> None:
    print(json.dumps(artifact, sort_keys=True), flush=True)


def _run_check(
    label: str,
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    timeout: int = 120,
) -> tuple[int, str]:
    """Run a single preflight command. Returns (exit_code, combined_output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + "\n" + result.stderr
        return result.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 1, f"TimeoutError: {label} exceeded {timeout}s"
    except FileNotFoundError as exc:
        return 1, f"missing_required_artifact: command not found: {exc}"
    except Exception as exc:
        return 1, f"unknown_failure: {label} raised {type(exc).__name__}: {exc}"


def _load_gate_schema() -> dict[str, Any]:
    path = _PRL_SCHEMA_DIR / "prl_gate_result.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"prl_gate_result schema missing — fail-closed: {path}")
    with path.open() as f:
        return json.load(f)


def _build_gate_result(
    *,
    run_id: str,
    trace_id: str,
    gate_recommendation: str,
    failure_classes: list[str],
    failure_packet_refs: list[str],
    repair_candidate_refs: list[str],
    eval_candidate_refs: list[str],
    blocking_reasons: list[str],
) -> dict[str, Any]:
    ts = _now_iso()
    payload = {
        "run_id": run_id,
        "gate_recommendation": gate_recommendation,
        "failure_count": len(failure_packet_refs),
    }
    artifact_id = deterministic_id(
        prefix="prl-gate",
        payload=payload,
        namespace="prl::gate",
    )
    envelope = build_artifact_envelope(
        artifact_id=artifact_id,
        timestamp=ts,
        schema_version="1.0.0",
        primary_trace_ref=trace_id,
    )
    artifact: dict[str, Any] = {
        "artifact_type": "prl_gate_result",
        "schema_version": "1.0.0",
        "id": envelope["id"],
        "timestamp": envelope["timestamp"],
        "run_id": run_id,
        "trace_id": trace_id,
        "trace_refs": envelope["trace_refs"],
        "gate_recommendation": gate_recommendation,
        "failure_count": len(failure_packet_refs),
        "failure_classes": sorted(set(failure_classes)),
        "failure_packet_refs": failure_packet_refs,
        "repair_candidate_refs": repair_candidate_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "blocking_reasons": blocking_reasons,
        "gate_passed": gate_recommendation == "passed_gate",
    }
    schema = _load_gate_schema()
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"prl_gate_result schema validation failed: {exc.message}") from exc
    return artifact


_PYTEST_CHECK: tuple[str, list[str], str] = (
    "pytest_changed_scope",
    [sys.executable, "-m", "pytest", "-q", "--tb=short"],
    "pre_pr_gate",
)


def _build_preflight_checks(
    base_ref: str, head_ref: str
) -> list[tuple[str, list[str], str]]:
    return [
        (
            "authority_shape_preflight",
            [sys.executable, "scripts/run_authority_shape_preflight.py", "--suggest-only",
             "--base-ref", base_ref, "--head-ref", head_ref],
            "pre_pr_gate",
        ),
        (
            "system_registry_guard",
            [sys.executable, "scripts/run_system_registry_guard.py",
             "--base-ref", base_ref, "--head-ref", head_ref],
            "pre_pr_gate",
        ),
        (
            "contract_preflight",
            [sys.executable, "scripts/run_contract_preflight.py",
             "--base-ref", base_ref, "--head-ref", head_ref],
            "pre_pr_gate",
        ),
        (
            "build_preflight_pqx_wrapper",
            [sys.executable, "scripts/build_preflight_pqx_wrapper.py",
             "--base-ref", base_ref, "--head-ref", head_ref],
            "pre_pr_gate",
        ),
    ]


def run_gate(
    *,
    run_id: str,
    trace_id: str,
    skip_pytest: bool = False,
    pytest_args: list[str] | None = None,
    base_ref: str = "origin/main",
    head_ref: str = "HEAD",
) -> dict[str, Any]:
    """Execute the full pre-PR reliability gate. Returns the prl_gate_result artifact."""
    all_signals: list[str] = []
    failure_classes: list[str] = []
    failure_packet_refs: list[str] = []
    repair_candidate_refs: list[str] = []
    eval_candidate_refs: list[str] = []
    blocking_reasons: list[str] = []

    checks = _build_preflight_checks(base_ref, head_ref)
    if not skip_pytest:
        label, cmd, source = _PYTEST_CHECK
        if pytest_args:
            cmd = cmd + pytest_args
        checks.append((label, cmd, source))

    for label, cmd, source in checks:
        exit_code, output = _run_check(label, cmd)

        if exit_code == 0 and not output.strip():
            continue

        parsed_failures = parse_log(output, exit_code=exit_code if exit_code != 0 else None)

        for parsed in parsed_failures:
            classification = classify(parsed)

            capture = build_capture_record(
                parsed=parsed,
                classification=classification,
                source=source,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(capture)

            packet = build_failure_packet(
                capture_record=capture,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(packet)

            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(repair)

            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(candidate)

            gated = advance_to_eval_case(
                candidate=candidate,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            if gated is not None:
                _emit(gated)

            gen_record = build_generation_record(
                failure_packet=packet,
                candidate=candidate,
                gated_eval=gated,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(gen_record)

            all_signals.append(classification.gate_signal)
            failure_classes.append(classification.failure_class)
            failure_packet_refs.append(f"pre_pr_failure_packet:{packet['id']}")
            repair_candidate_refs.append(f"prl_repair_candidate:{repair['id']}")
            eval_candidate_refs.append(f"eval_case_candidate:{candidate['id']}")

            if classification.gate_signal == "failed_gate":
                blocking_reasons.append(
                    f"{classification.failure_class}: {parsed.normalized_message}"
                )

    gate_recommendation = aggregate_gate_signal(all_signals)

    gate_result = _build_gate_result(
        run_id=run_id,
        trace_id=trace_id,
        gate_recommendation=gate_recommendation,
        failure_classes=failure_classes,
        failure_packet_refs=failure_packet_refs,
        repair_candidate_refs=repair_candidate_refs,
        eval_candidate_refs=eval_candidate_refs,
        blocking_reasons=blocking_reasons,
    )
    _emit(gate_result)
    return gate_result


def main() -> int:
    parser = argparse.ArgumentParser(description="PRL Pre-PR Reliability Gate")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Override run_id (default: auto-generated)",
    )
    parser.add_argument(
        "--trace-id",
        default=None,
        help="Override trace_id (default: auto-generated)",
    )
    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip pytest execution (run preflight checks only)",
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git base ref for changed-file resolution (default: origin/main)",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git head ref for changed-file resolution (default: HEAD)",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to pytest (use -- before pytest flags)",
    )
    args = parser.parse_args()

    run_id = args.run_id or _new_run_id()
    trace_id = args.trace_id or _new_trace_id()

    # Strip leading '--' separator that argparse.REMAINDER may include
    pytest_args = args.pytest_args or []
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]

    try:
        gate_result = run_gate(
            run_id=run_id,
            trace_id=trace_id,
            skip_pytest=args.skip_pytest,
            pytest_args=pytest_args or None,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
        )
    except Exception as exc:
        error_record = {
            "artifact_type": "prl_gate_error",
            "run_id": run_id,
            "trace_id": trace_id,
            "error": str(exc),
            "timestamp": _now_iso(),
        }
        print(json.dumps(error_record, sort_keys=True), file=sys.stderr, flush=True)
        return 1

    recommendation = gate_result["gate_recommendation"]
    if recommendation == "passed_gate":
        return 0
    if recommendation == "gate_warn":
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
