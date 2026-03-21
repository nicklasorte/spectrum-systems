import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_strategic_knowledge_artifact.py"


def _artifact_payload() -> dict:
    return {
        "artifact_type": "book_intelligence_pack",
        "artifact_id": "ART-CLI-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "created_at": "2026-03-21T10:00:00Z",
        "source": {
            "source_id": "SRC-BOOK-CLI-001",
            "source_type": "book_pdf",
            "source_path": "strategic_knowledge/raw/books/book-cli.pdf",
        },
        "provenance": {
            "extraction_run_id": "run-cli-001",
            "extractor_version": "0.1.0",
        },
        "evidence_anchors": [{"anchor_type": "pdf", "page_number": 1}],
        "insights": ["Insight"],
        "themes": ["Theme"],
        "key_claims": ["Claim"],
    }


def _write_catalog(root: Path, source_id: str) -> None:
    payload = {
        "schema_version": "1.0.0",
        "catalog_version": "1.0.0",
        "updated_at": "2026-03-21T10:00:00Z",
        "sources": [
            {
                "artifact_type": "strategic_knowledge_source_ref",
                "schema_version": "1.0.0",
                "source_id": source_id,
                "source_type": "book_pdf",
                "source_path": "strategic_knowledge/raw/books/book-cli.pdf",
                "source_status": "ready",
                "registered_at": "2026-03-21T10:00:00Z",
                "metadata": {"title": "Book CLI"},
            }
        ],
    }
    path = root / "strategic_knowledge" / "metadata" / "source_catalog.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run_cli(tmp_path: Path, artifact: dict) -> subprocess.CompletedProcess[str]:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--artifact-path",
            str(artifact_path),
            "--data-lake-root",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_allow_returns_success_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    result = _run_cli(tmp_path, _artifact_payload())
    assert result.returncode == 0
    assert json.loads(result.stdout)["system_response"] == "allow"


def test_cli_require_review_is_non_blocking(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["evidence_anchors"] = [{"anchor_type": "pdf", "page_number": 0}]
    result = _run_cli(tmp_path, artifact)
    assert result.returncode == 0
    assert json.loads(result.stdout)["system_response"] == "require_review"


def test_cli_require_rebuild_returns_nonzero_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["provenance"] = {}
    result = _run_cli(tmp_path, artifact)
    assert result.returncode != 0
    assert json.loads(result.stdout)["system_response"] == "require_rebuild"


def test_cli_block_returns_nonzero_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["source"]["source_id"] = "SRC-UNKNOWN"
    result = _run_cli(tmp_path, artifact)
    assert result.returncode != 0
    assert json.loads(result.stdout)["system_response"] == "block"
