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

Output (F3L-03):
  All NDJSON records continue to be emitted to stdout for backwards
  compatibility. When ``--output-dir`` is supplied (default
  ``outputs/prl/``), each artifact is also persisted to a stable file
  path so APU and replay consumers do not depend on the stdout NDJSON:

    <output-dir>/prl_gate_result.json                 — final gate result
    <output-dir>/prl_artifact_index.json              — index of all persisted refs
    <output-dir>/captures/<id>.json                   — pr_failure_capture_record
    <output-dir>/failure_packets/<id>.json            — pre_pr_failure_packet
    <output-dir>/repair_candidates/<id>.json          — prl_repair_candidate
    <output-dir>/eval_candidates/<id>.json            — eval_case_candidate
    <output-dir>/eval_cases/<id>.json                 — prl_eval_case
    <output-dir>/eval_generation_records/<id>.json    — prl_eval_generation_record

  ``failure_packet_refs`` / ``repair_candidate_refs`` /
  ``eval_candidate_refs`` in the prl_gate_result include the
  filesystem paths so APU can ingest them directly without parsing
  NDJSON. Existing ``<artifact_type>:<id>`` style refs continue to be
  emitted alongside the file paths to preserve backwards compatibility.

  ``prl_artifact_index.json`` is an observation-only index that points
  at every artifact persisted by this run. APU and replay consumers
  read it as the canonical entrypoint into the PRL evidence chain on
  disk. PRL retains classification, repair-candidate, and
  eval-candidate authority; the index does not introduce a new gate.
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
from spectrum_systems.modules.prl.clp_consumer import (
    load_clp_result as _load_clp_result_for_prl,
    parsed_failures_from_clp_result,
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

import hashlib
import jsonschema

_PRL_SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"

# F3L-03 — Stable artifact subdirectory layout under ``--output-dir``.
_PRL_ARTIFACT_SUBDIRS: dict[str, str] = {
    "pr_failure_capture_record": "captures",
    "pre_pr_failure_packet": "failure_packets",
    "prl_repair_candidate": "repair_candidates",
    "eval_case_candidate": "eval_candidates",
    "prl_eval_case": "eval_cases",
    "prl_eval_generation_record": "eval_generation_records",
}

# F3L-03 — Mapping from artifact_type to the index field that lists its refs.
_PRL_INDEX_FIELDS: dict[str, str] = {
    "pr_failure_capture_record": "capture_record_refs",
    "pre_pr_failure_packet": "failure_packet_refs",
    "prl_repair_candidate": "repair_candidate_refs",
    "eval_case_candidate": "eval_candidate_refs",
    "prl_eval_case": "eval_case_refs",
    "prl_eval_generation_record": "generation_record_refs",
}

DEFAULT_PRL_OUTPUT_DIR = "outputs/prl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"prl-gate-{ts}-{suffix}"


def _new_trace_id() -> str:
    return f"trace-prl-{uuid.uuid4().hex[:16]}"


def _persist_artifact(
    artifact: dict[str, Any],
    *,
    output_dir: Path | None,
) -> str | None:
    """Write ``artifact`` to a stable file path under ``output_dir``.

    Returns the artifact path relative to ``REPO_ROOT`` when persisted,
    or ``None`` when ``output_dir`` is ``None`` or the artifact_type
    has no canonical subdir (in which case stdout NDJSON remains the
    sole output).
    """
    if output_dir is None:
        return None
    artifact_type = artifact.get("artifact_type")
    subdir = _PRL_ARTIFACT_SUBDIRS.get(str(artifact_type))
    if not subdir:
        return None
    artifact_id = artifact.get("id")
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    target_dir = output_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{artifact_id}.json"
    target_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        return str(target_path.relative_to(REPO_ROOT))
    except ValueError:
        return str(target_path)


def _emit(artifact: dict[str, Any]) -> None:
    print(json.dumps(artifact, sort_keys=True), flush=True)


def _run_check(
    label: str,
    cmd: list[str],
    *,
    cwd: Path = REPO_ROOT,
    timeout: int = 600,
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


def _load_index_schema() -> dict[str, Any]:
    path = _PRL_SCHEMA_DIR / "prl_artifact_index.schema.json"
    if not path.exists():
        raise FileNotFoundError(
            f"prl_artifact_index schema missing — fail-closed: {path}"
        )
    with path.open() as f:
        return json.load(f)


def _build_artifact_index(
    *,
    run_id: str,
    trace_id: str,
    gate_recommendation: str | None,
    persisted: dict[str, list[str]],
    prl_gate_result_ref: str,
    clp_result_ref: str | None,
) -> dict[str, Any]:
    """Build a deterministic ``prl_artifact_index`` artifact.

    The index is observation-only. It points at every PRL artifact
    persisted to disk for this run so APU and replay consumers can
    reconstruct the PRL evidence chain from the file system alone,
    without parsing the legacy stdout NDJSON. PRL retains all
    classification, repair-candidate, and eval-candidate authority;
    the index does not introduce a new gate.
    """
    capture_refs = sorted(set(persisted.get("capture_record_refs", []) or []))
    failure_packet_refs = sorted(set(persisted.get("failure_packet_refs", []) or []))
    repair_refs = sorted(set(persisted.get("repair_candidate_refs", []) or []))
    eval_candidate_refs = sorted(set(persisted.get("eval_candidate_refs", []) or []))
    eval_case_refs = sorted(set(persisted.get("eval_case_refs", []) or []))
    generation_refs = sorted(set(persisted.get("generation_record_refs", []) or []))

    counts = {
        "failure_packets": len(failure_packet_refs),
        "repair_candidates": len(repair_refs),
        "eval_candidates": len(eval_candidate_refs),
        "generation_records": len(generation_refs),
        "capture_records": len(capture_refs),
        "eval_cases": len(eval_case_refs),
    }

    reason_codes: list[str] = []
    if not prl_gate_result_ref:
        reason_codes.append("prl_gate_result_ref_missing")
    if (
        counts["failure_packets"] > 0
        and counts["repair_candidates"] == 0
        and gate_recommendation in {"failed_gate", "gate_hold"}
    ):
        reason_codes.append("repair_candidates_missing_for_failure_packets")
    if (
        counts["failure_packets"] > 0
        and counts["eval_candidates"] == 0
        and gate_recommendation in {"failed_gate", "gate_hold"}
    ):
        reason_codes.append("eval_candidates_missing_for_failure_packets")

    hash_payload = {
        "prl_gate_result_ref": prl_gate_result_ref,
        "clp_result_ref": clp_result_ref,
        "failure_packet_refs": failure_packet_refs,
        "repair_candidate_refs": repair_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "generation_record_refs": generation_refs,
        "capture_record_refs": capture_refs,
        "eval_case_refs": eval_case_refs,
    }
    serialized = json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    evidence_hash = "sha256-" + hashlib.sha256(serialized).hexdigest()

    artifact_id = deterministic_id(
        prefix="prl-index",
        payload=hash_payload,
        namespace="prl::index",
    )

    artifact: dict[str, Any] = {
        "artifact_type": "prl_artifact_index",
        "schema_version": "1.0.0",
        "id": artifact_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "generated_at": _now_iso(),
        "clp_result_ref": clp_result_ref,
        "prl_gate_result_ref": prl_gate_result_ref,
        "failure_packet_refs": failure_packet_refs,
        "repair_candidate_refs": repair_refs,
        "eval_candidate_refs": eval_candidate_refs,
        "generation_record_refs": generation_refs,
        "capture_record_refs": capture_refs,
        "eval_case_refs": eval_case_refs,
        "artifact_counts": counts,
        "evidence_hash": evidence_hash,
        "reason_codes": reason_codes,
        "authority_scope": "observation_only",
        "gate_recommendation": gate_recommendation,
    }
    schema = _load_index_schema()
    try:
        jsonschema.validate(artifact, schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(
            f"prl_artifact_index schema validation failed: {exc.message}"
        ) from exc
    return artifact


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
        "failure_classes_sorted": sorted(set(failure_classes)),
        "failure_packet_refs_sorted": sorted(failure_packet_refs),
        "blocking_reasons_sorted": sorted(blocking_reasons),
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
    clp_result_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute the full pre-PR reliability gate. Returns the prl_gate_result artifact.

    F3L-03 — When ``output_dir`` is supplied, each emitted artifact is
    also persisted to a stable file path under that directory so APU
    and replay consumers can ingest file-based evidence rather than
    parsing the stdout NDJSON. The final ``prl_gate_result.json`` is
    written at ``output_dir/prl_gate_result.json``. NDJSON to stdout
    is preserved for backwards compatibility.
    """
    all_signals: list[str] = []
    failure_classes: list[str] = []
    failure_packet_refs: list[str] = []
    repair_candidate_refs: list[str] = []
    eval_candidate_refs: list[str] = []
    blocking_reasons: list[str] = []

    # F3L-03 — track persisted file paths grouped by index field so the
    # prl_artifact_index can list pure file refs (no <type>:<id> entries).
    persisted_paths: dict[str, list[str]] = {
        "capture_record_refs": [],
        "failure_packet_refs": [],
        "repair_candidate_refs": [],
        "eval_candidate_refs": [],
        "eval_case_refs": [],
        "generation_record_refs": [],
    }

    def _record(artifact: dict[str, Any]) -> str | None:
        path = _persist_artifact(artifact, output_dir=output_dir)
        if path:
            field = _PRL_INDEX_FIELDS.get(str(artifact.get("artifact_type")))
            if field:
                persisted_paths[field].append(path)
        return path

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    checks = _build_preflight_checks(base_ref, head_ref)
    if not skip_pytest:
        label, cmd, source = _PYTEST_CHECK
        if pytest_args:
            cmd = cmd + pytest_args
        checks.append((label, cmd, source))

    # CLP-02: Consume `core_loop_pre_pr_gate_result` evidence as structured PRL
    # input. CLP block becomes ParsedFailure records that flow through the
    # standard classify/repair/eval pipeline. PRL retains all repair authority;
    # this path performs no auto-repair.
    clp_failures: list[tuple[Any, str]] = []
    if clp_result_path is not None:
        clp_payload = _load_clp_result_for_prl(clp_result_path)
        if clp_payload is not None and clp_payload.get("gate_status") == "block":
            try:
                clp_relpath = str(clp_result_path.relative_to(REPO_ROOT))
            except ValueError:
                clp_relpath = str(clp_result_path)
            for parsed in parsed_failures_from_clp_result(
                clp_payload, clp_path=clp_relpath
            ):
                clp_failures.append((parsed, "clp_evidence"))

    for parsed, source in clp_failures:
        classification = classify(parsed)
        capture = build_capture_record(
            parsed=parsed,
            classification=classification,
            source=source,
            run_id=run_id,
            trace_id=trace_id,
        )
        _emit(capture)
        _record(capture)
        packet = build_failure_packet(
            capture_record=capture,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        _emit(packet)
        packet_path = _record(packet)
        repair = generate_repair_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        _emit(repair)
        repair_path = _record(repair)
        candidate = generate_eval_case_candidate(
            failure_packet=packet,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        _emit(candidate)
        candidate_path = _record(candidate)
        gated = advance_to_eval_case(
            candidate=candidate,
            classification=classification,
            run_id=run_id,
            trace_id=trace_id,
        )
        if gated is not None:
            _emit(gated)
            _record(gated)
        gen_record = build_generation_record(
            failure_packet=packet,
            candidate=candidate,
            gated_eval=gated,
            run_id=run_id,
            trace_id=trace_id,
        )
        _emit(gen_record)
        _record(gen_record)
        all_signals.append(classification.gate_signal)
        failure_classes.append(classification.failure_class)
        failure_packet_refs.append(f"pre_pr_failure_packet:{packet['id']}")
        if packet_path:
            failure_packet_refs.append(packet_path)
        repair_candidate_refs.append(f"prl_repair_candidate:{repair['id']}")
        if repair_path:
            repair_candidate_refs.append(repair_path)
        eval_candidate_refs.append(f"eval_case_candidate:{candidate['id']}")
        if candidate_path:
            eval_candidate_refs.append(candidate_path)
        if classification.gate_signal == "failed_gate":
            blocking_reasons.append(
                f"{classification.failure_class}: {parsed.normalized_message}"
            )

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
            _record(capture)

            packet = build_failure_packet(
                capture_record=capture,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(packet)
            packet_path = _record(packet)

            repair = generate_repair_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(repair)
            repair_path = _record(repair)

            candidate = generate_eval_case_candidate(
                failure_packet=packet,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(candidate)
            candidate_path = _record(candidate)

            gated = advance_to_eval_case(
                candidate=candidate,
                classification=classification,
                run_id=run_id,
                trace_id=trace_id,
            )
            if gated is not None:
                _emit(gated)
                _record(gated)

            gen_record = build_generation_record(
                failure_packet=packet,
                candidate=candidate,
                gated_eval=gated,
                run_id=run_id,
                trace_id=trace_id,
            )
            _emit(gen_record)
            _record(gen_record)

            all_signals.append(classification.gate_signal)
            failure_classes.append(classification.failure_class)
            failure_packet_refs.append(f"pre_pr_failure_packet:{packet['id']}")
            if packet_path:
                failure_packet_refs.append(packet_path)
            repair_candidate_refs.append(f"prl_repair_candidate:{repair['id']}")
            if repair_path:
                repair_candidate_refs.append(repair_path)
            eval_candidate_refs.append(f"eval_case_candidate:{candidate['id']}")
            if candidate_path:
                eval_candidate_refs.append(candidate_path)

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

    if output_dir is not None:
        gate_result_path = output_dir / "prl_gate_result.json"
        gate_result_path.write_text(
            json.dumps(gate_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            gate_result_ref = str(gate_result_path.relative_to(REPO_ROOT))
        except ValueError:
            gate_result_ref = str(gate_result_path)
        clp_result_ref: str | None = None
        if clp_result_path is not None:
            try:
                clp_result_ref = str(clp_result_path.relative_to(REPO_ROOT))
            except ValueError:
                clp_result_ref = str(clp_result_path)
        index = _build_artifact_index(
            run_id=run_id,
            trace_id=trace_id,
            gate_recommendation=gate_recommendation,
            persisted=persisted_paths,
            prl_gate_result_ref=gate_result_ref,
            clp_result_ref=clp_result_ref,
        )
        _emit(index)
        index_path = output_dir / "prl_artifact_index.json"
        index_path.write_text(
            json.dumps(index, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
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
        "--clp-result",
        default=None,
        help=(
            "Optional path to a core_loop_pre_pr_gate_result artifact. "
            "When supplied and gate_status=block, CLP-02 failure classes are "
            "normalized into PRL ParsedFailure records and processed by the "
            "standard classify/repair/eval pipeline. PRL retains all repair "
            "and classification authority — CLP-02 performs no auto-repair."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_PRL_OUTPUT_DIR,
        help=(
            "F3L-03 — directory under which PRL artifacts are persisted "
            "(default: outputs/prl). Each artifact is also written to a "
            "stable file path so downstream consumers (APU, replay) can "
            "ingest file-based evidence rather than parsing stdout NDJSON. "
            "Pass an empty string to disable file persistence and emit "
            "only the legacy stdout NDJSON stream."
        ),
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to pytest (use -- before pytest flags)",
    )
    args, unknown_args = parser.parse_known_args()

    run_id = args.run_id or _new_run_id()
    trace_id = args.trace_id or _new_trace_id()

    # Strip leading '--' separator that argparse.REMAINDER may include
    pytest_args = args.pytest_args or []
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    # Prepend any flags argparse treated as unknown (e.g. -v, -x, -k "expr")
    pytest_args = unknown_args + pytest_args

    clp_result_path: Path | None = None
    if args.clp_result:
        candidate = Path(args.clp_result)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        clp_result_path = candidate

    output_dir: Path | None = None
    if args.output_dir:
        out = Path(args.output_dir)
        if not out.is_absolute():
            out = REPO_ROOT / out
        output_dir = out

    try:
        gate_result = run_gate(
            run_id=run_id,
            trace_id=trace_id,
            skip_pytest=args.skip_pytest,
            pytest_args=pytest_args or None,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            clp_result_path=clp_result_path,
            output_dir=output_dir,
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
