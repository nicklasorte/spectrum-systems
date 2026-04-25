from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from spectrum_systems.cli.hop_cli import main
from spectrum_systems.modules.hop.experience_store import ExperienceStore


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def test_cli_list_top_candidates_and_trace(capsys, tmp_path: Path) -> None:
    schema_root = Path(__file__).resolve().parents[1] / "contracts" / "schemas" / "hop"
    store_root = tmp_path / "store"
    store = ExperienceStore(store_root, schema_root=schema_root)

    for idx, score in enumerate([0.7, 0.9], start=1):
        artifact = {
            "artifact_type": "harness_score",
            "artifact_id": f"score-{idx}",
            "schema_ref": "hop/harness_score.schema.json@1.0.0",
            "trace": {"trace_id": "trace-1", "timestamp": _now(), "steps": [{"name": "s", "status": "pass"}]},
            "content_hash": _hash({"score": score}),
            "created_at": _now(),
            "candidate_id": f"cand-{idx}",
            "score": score,
            "coverage": 1.0,
            "run_count": 20,
        }
        store.append(artifact, "harness_score")

    code = main(["--store", str(store_root), "list-top-candidates"])
    assert code == 0
    out = capsys.readouterr().out
    assert "cand-2" in out

    code = main(["--store", str(store_root), "inspect-trace", "trace-1"])
    assert code == 0
    out = capsys.readouterr().out
    assert "trace-1" in out
