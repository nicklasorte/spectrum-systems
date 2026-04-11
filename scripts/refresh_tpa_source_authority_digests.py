#!/usr/bin/env python3
"""Refresh source-authority digest fields in config/policy/tpa_scope_policy.json."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "policy" / "tpa_scope_policy.json"
DIGEST_PATHS = {
    "source_inventory_digest_sha256": REPO_ROOT / "docs" / "source_indexes" / "source_inventory.json",
    "obligation_index_digest_sha256": REPO_ROOT / "docs" / "source_indexes" / "obligation_index.json",
    "component_source_map_digest_sha256": REPO_ROOT / "docs" / "source_indexes" / "component_source_map.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def refresh_policy(policy_path: Path, *, refresh_id: str | None = None, refreshed_at: str | None = None) -> dict:
    payload = json.loads(policy_path.read_text(encoding="utf-8"))
    refresh = payload.get("source_authority_refresh")
    if not isinstance(refresh, dict):
        raise ValueError("tpa_scope_policy.source_authority_refresh must be an object")

    for field, source_path in DIGEST_PATHS.items():
        if not source_path.is_file():
            raise FileNotFoundError(f"source-authority index not found for digest refresh: {source_path}")
        refresh[field] = _sha256(source_path)

    if refresh_id:
        refresh["refresh_id"] = refresh_id
    if refreshed_at:
        refresh["refreshed_at"] = refreshed_at

    policy_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-path", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--refresh-id", default="SRC-AUTH-REFRESH-2026-04-11-SRC-01C")
    parser.add_argument("--refreshed-at", default="2026-04-11T00:00:00Z")
    args = parser.parse_args()

    payload = refresh_policy(
        args.policy_path,
        refresh_id=args.refresh_id,
        refreshed_at=args.refreshed_at,
    )
    print(json.dumps(payload["source_authority_refresh"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
