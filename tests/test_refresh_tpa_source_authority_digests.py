import hashlib
import json
from pathlib import Path

from scripts.refresh_tpa_source_authority_digests import refresh_policy


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_refresh_policy_recomputes_digests_and_is_deterministic(tmp_path: Path) -> None:
    index_root = tmp_path / "docs" / "source_indexes"
    index_root.mkdir(parents=True, exist_ok=True)
    (index_root / "source_inventory.json").write_text('{"a":1}\n', encoding="utf-8")
    (index_root / "obligation_index.json").write_text('{"b":2}\n', encoding="utf-8")
    (index_root / "component_source_map.json").write_text('{"c":3}\n', encoding="utf-8")

    policy_path = tmp_path / "config" / "policy" / "tpa_scope_policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(
        json.dumps(
            {
                "source_authority_refresh": {
                    "source_inventory_digest_sha256": "0" * 64,
                    "obligation_index_digest_sha256": "0" * 64,
                    "component_source_map_digest_sha256": "0" * 64,
                    "refresh_id": "old",
                    "refreshed_at": "old",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    import scripts.refresh_tpa_source_authority_digests as module

    module.DIGEST_PATHS = {
        "source_inventory_digest_sha256": index_root / "source_inventory.json",
        "obligation_index_digest_sha256": index_root / "obligation_index.json",
        "component_source_map_digest_sha256": index_root / "component_source_map.json",
    }

    first = refresh_policy(policy_path, refresh_id="RID-1", refreshed_at="2026-04-11T00:00:00Z")
    second = refresh_policy(policy_path, refresh_id="RID-1", refreshed_at="2026-04-11T00:00:00Z")

    assert first == second
    refresh = first["source_authority_refresh"]
    assert refresh["source_inventory_digest_sha256"] == _sha256(index_root / "source_inventory.json")
    assert refresh["obligation_index_digest_sha256"] == _sha256(index_root / "obligation_index.json")
    assert refresh["component_source_map_digest_sha256"] == _sha256(index_root / "component_source_map.json")


def test_refresh_policy_fails_when_index_missing(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps({"source_authority_refresh": {}}) + "\n", encoding="utf-8")

    import scripts.refresh_tpa_source_authority_digests as module

    module.DIGEST_PATHS = {"source_inventory_digest_sha256": tmp_path / "missing.json"}

    try:
        refresh_policy(policy_path)
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        assert True
