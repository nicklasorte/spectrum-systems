#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_INVALID = 1
EXIT_CORRUPT = 2


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a compact RFX loop proof artifact for operators")
    parser.add_argument("--proof", type=Path, required=True, help="Path to rfx_loop_proof JSON")
    return parser.parse_args(argv)


def _load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"proof file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("proof payload must be an object")
    return payload


def render(proof: dict) -> str:
    lines = [
        "RFX LOOP PROOF",
        "--------------",
        f"status: {proof.get('status', '-')}",
        f"proof_id: {proof.get('proof_id', '-')}",
        f"run_id: {proof.get('run_id', '-')}",
        f"trace_id: {proof.get('trace_id', '-')}",
        f"owner_context: {proof.get('owner_context', '-')}",
        f"failing_stage: {proof.get('failing_stage', '-')}",
        f"primary_reason_code: {proof.get('primary_reason_code', '-')}",
        f"repair_hint: {(proof.get('debug') or {}).get('repair_hint', '-')}",
        f"operator_action: {(proof.get('debug') or {}).get('operator_action', '-')}",
    ]
    if proof.get("reason_codes_emitted"):
        lines.append("reason_codes_emitted: " + ", ".join(proof["reason_codes_emitted"]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        proof = _load(args.proof)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"[print_rfx_loop_proof] {exc}", file=sys.stderr)
        return EXIT_CORRUPT

    if proof.get("artifact_type") != "rfx_loop_proof":
        print("[print_rfx_loop_proof] artifact_type must be rfx_loop_proof", file=sys.stderr)
        return EXIT_CORRUPT

    print(render(proof), end="")
    return EXIT_PASS if proof.get("status") == "valid" else EXIT_INVALID


if __name__ == "__main__":
    raise SystemExit(main())
