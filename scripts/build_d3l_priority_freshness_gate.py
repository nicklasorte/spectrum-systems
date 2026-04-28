#!/usr/bin/env python3
"""D3L-MASTER-01 Phase 1 — priority artifact freshness gate builder.

Validates artifacts/system_dependency_priority_report.json against the
registry contract and produces artifacts/tls/d3l_priority_freshness_gate.json:

  * valid JSON
  * schema valid (shape match)
  * generated_at present and parseable
  * generated_at not older than threshold (default 24h)
  * top_5 / global_ranked_systems entries reference only active_system_ids

If any check fails, the gate output records `status = "fail-closed"` and
documents the exact recompute command. The dashboard surface reads this
artifact and refuses to render Top 3 / Top 10 / All when status is not "ok".
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PRIORITY_PATH = REPO_ROOT / "artifacts" / "system_dependency_priority_report.json"
PRIORITY_TLS_PATH = REPO_ROOT / "artifacts" / "tls" / "system_dependency_priority_report.json"
CONTRACT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_registry_contract.json"
OUTPUT_PATH = REPO_ROOT / "artifacts" / "tls" / "d3l_priority_freshness_gate.json"

DEFAULT_STALE_HOURS = 24
RECOMPUTE_COMMAND = (
    "python scripts/build_tls_dependency_priority.py "
    "--candidates HOP,RAX,RSM,CAP,SEC,EVL,OBS,SLO --fail-if-missing "
    "&& python scripts/build_dashboard_3ls_with_tls.py --skip-next-build"
)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_priority_artifact() -> tuple[Path | None, str | None]:
    if PRIORITY_PATH.exists():
        return PRIORITY_PATH, "artifacts/system_dependency_priority_report.json"
    if PRIORITY_TLS_PATH.exists():
        return PRIORITY_TLS_PATH, "artifacts/tls/system_dependency_priority_report.json"
    return None, None


def _load_contract() -> dict | None:
    if not CONTRACT_PATH.exists():
        return None
    try:
        return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _validate_shape(payload: object) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, "payload_not_object"
    schema_version = payload.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.startswith("tls-"):
        return False, f"schema_version_invalid:{schema_version!r}"
    phase = payload.get("phase")
    if not isinstance(phase, str) or not phase.startswith("TLS-"):
        return False, f"phase_invalid:{phase!r}"
    for field in ("ranked_systems", "global_ranked_systems", "top_5", "requested_candidate_ranking"):
        if not isinstance(payload.get(field), list):
            return False, f"missing_list_field:{field}"
    for entry in payload.get("top_5", []):
        if not isinstance(entry, dict):
            return False, "top_5_entry_not_object"
        if "system_id" not in entry:
            return False, "top_5_entry_missing_system_id"
    return True, None


def _check_freshness(generated_at: str | None, stale_hours: int, now_iso: str) -> dict:
    out = {
        "generated_at": generated_at,
        "now_iso": now_iso,
        "stale_threshold_hours": stale_hours,
        "stale": False,
        "future_skewed": False,
        "parsed": False,
        "age_hours": None,
        "reason": None,
    }
    if not generated_at:
        out["reason"] = "generated_at_missing"
        return out
    try:
        gen = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        out["reason"] = f"generated_at_unparseable:{generated_at}"
        return out
    out["parsed"] = True
    now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    age = now - gen
    out["age_hours"] = round(age.total_seconds() / 3600.0, 4)
    if age.total_seconds() < -300:
        out["future_skewed"] = True
        out["reason"] = f"future_timestamp_by_{int(-age.total_seconds())}s"
        return out
    if age.total_seconds() > stale_hours * 3600:
        out["stale"] = True
        out["reason"] = f"older_than_{stale_hours}h"
    return out


def _ranking_universe_check(payload: dict, contract: dict | None) -> dict:
    out = {
        "ranking_universe_size": 0,
        "non_active_in_top_5": [],
        "non_active_in_global": [],
        "ok": False,
    }
    if not contract:
        out["reason"] = "contract_missing"
        return out
    universe = set(contract.get("ranking_universe", []))
    out["ranking_universe_size"] = len(universe)
    for row in payload.get("top_5", []):
        if not isinstance(row, dict):
            continue
        sid = row.get("system_id")
        if isinstance(sid, str) and sid not in universe:
            out["non_active_in_top_5"].append(sid)
    for row in payload.get("global_ranked_systems", []):
        if not isinstance(row, dict):
            continue
        sid = row.get("system_id")
        if isinstance(sid, str) and sid not in universe:
            out["non_active_in_global"].append(sid)
    out["ok"] = not out["non_active_in_top_5"]
    return out


def build_gate(now_iso: str, stale_hours: int) -> dict:
    artifact_path, source_relative = _resolve_priority_artifact()
    contract = _load_contract()
    gate: dict = {
        "artifact_type": "d3l_priority_freshness_gate",
        "phase": "D3L-MASTER-01",
        "schema_version": "d3l-master-01.v1",
        "generated_at": now_iso,
        "stale_threshold_hours": stale_hours,
        "recompute_command": RECOMPUTE_COMMAND,
        "checks": {},
        "status": "fail-closed",
        "blocking_reasons": [],
        "source_priority_artifact": source_relative,
        "source_contract_artifact": "artifacts/tls/d3l_registry_contract.json"
        if contract is not None
        else None,
    }

    if artifact_path is None:
        gate["checks"]["valid_json"] = False
        gate["checks"]["schema_valid"] = False
        gate["blocking_reasons"].append("priority_artifact_missing")
        return gate

    raw = artifact_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
        gate["checks"]["valid_json"] = True
    except json.JSONDecodeError as exc:
        gate["checks"]["valid_json"] = False
        gate["checks"]["schema_valid"] = False
        gate["blocking_reasons"].append(f"invalid_json:{exc}")
        return gate

    schema_ok, schema_reason = _validate_shape(payload)
    gate["checks"]["schema_valid"] = schema_ok
    if not schema_ok:
        gate["blocking_reasons"].append(f"schema_invalid:{schema_reason}")
        return gate

    generated_at = payload.get("generated_at") if isinstance(payload, dict) else None
    if not isinstance(generated_at, str):
        generated_at = None

    fresh = _check_freshness(generated_at, stale_hours, now_iso)
    gate["checks"]["freshness"] = fresh
    if not fresh["parsed"] or fresh["stale"] or fresh["future_skewed"]:
        gate["blocking_reasons"].append(
            fresh.get("reason") or "freshness_unknown"
        )

    universe = _ranking_universe_check(payload, contract)
    gate["checks"]["ranking_universe"] = universe
    if not universe["ok"]:
        if not contract:
            gate["blocking_reasons"].append("contract_missing")
        elif universe["non_active_in_top_5"]:
            gate["blocking_reasons"].append(
                "non_active_in_top_5:" + ",".join(universe["non_active_in_top_5"])
            )

    if not gate["blocking_reasons"]:
        gate["status"] = "ok"
    return gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--stale-hours", type=int, default=DEFAULT_STALE_HOURS)
    parser.add_argument("--now", type=str, default=None)
    args = parser.parse_args(argv)

    now_iso = args.now or _now_iso()
    gate = build_gate(now_iso=now_iso, stale_hours=args.stale_hours)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        rel = args.output.relative_to(REPO_ROOT)
    except ValueError:
        rel = args.output
    print(f"wrote {rel} status={gate['status']}")
    return 0 if gate["status"] == "ok" else 0


if __name__ == "__main__":
    sys.exit(main())
