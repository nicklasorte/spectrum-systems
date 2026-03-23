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


def _run_cli(
    tmp_path: Path,
    artifact: dict,
    *,
    trace_id: str | None = "trace-cli-default-001",
    span_id: str | None = "span-cli-default-001",
    parent_span_id: str | None = "span-cli-parent-001",
    run_id: str | None = "run-cli-governed-001",
) -> subprocess.CompletedProcess[str]:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    args = [
        sys.executable,
        str(SCRIPT_PATH),
        "--artifact-path",
        str(artifact_path),
        "--data-lake-root",
        str(tmp_path),
    ]
    if trace_id is not None:
        args.extend(["--trace-id", trace_id])
    if span_id is not None:
        args.extend(["--span-id", span_id])
    if parent_span_id is not None:
        args.extend(["--parent-span-id", parent_span_id])
    if run_id is not None:
        args.extend(["--run-id", run_id])
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _stdout_payload(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.stdout.strip(), "expected JSON payload on stdout"
    return json.loads(result.stdout)


def test_cli_allow_returns_success_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    result = _run_cli(tmp_path, _artifact_payload())
    payload = _stdout_payload(result)
    assert result.returncode == 0
    assert payload["system_response"] == "allow"
    assert payload["trace_id"] == "trace-cli-default-001"
    assert payload["span_id"] == "span-cli-default-001"


def test_cli_require_review_is_non_blocking(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["evidence_anchors"] = [{"anchor_type": "pdf", "page_number": 0}]
    result = _run_cli(tmp_path, artifact)
    assert result.returncode == 0
    assert _stdout_payload(result)["system_response"] == "require_review"


def test_cli_require_rebuild_returns_nonzero_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["provenance"] = {}
    result = _run_cli(tmp_path, artifact)
    assert result.returncode != 0
    assert _stdout_payload(result)["system_response"] == "require_rebuild"


def test_cli_block_returns_nonzero_exit(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    artifact = _artifact_payload()
    artifact["source"]["source_id"] = "SRC-UNKNOWN"
    result = _run_cli(tmp_path, artifact)
    assert result.returncode != 0
    assert _stdout_payload(result)["system_response"] == "block"


def test_cli_honors_explicit_trace_context(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    result = _run_cli(
        tmp_path,
        _artifact_payload(),
        trace_id="trace-cli-explicit-001",
        span_id="span-cli-explicit-001",
        parent_span_id="span-cli-explicit-parent-001",
        run_id="run-cli-explicit-001",
    )
    payload = _stdout_payload(result)
    assert result.returncode == 0
    assert payload["trace_id"] == "trace-cli-explicit-001"
    assert payload["span_id"] == "span-cli-explicit-001"


def test_cli_missing_trace_context_fails_closed(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    result = _run_cli(
        tmp_path,
        _artifact_payload(),
        trace_id=None,
        span_id=None,
        parent_span_id=None,
        run_id=None,
    )
    payload = _stdout_payload(result)
    assert result.returncode != 0
    assert payload["system_response"] == "block"
    assert payload["error"]["code"] == "MISSING_TRACE_CONTEXT"
    assert payload["error"]["missing_fields"] == ["trace_id", "span_id", "parent_span_id", "run_id"]


def test_cli_machine_readable_output_contract_is_consistent(tmp_path: Path) -> None:
    _write_catalog(tmp_path, "SRC-BOOK-CLI-001")
    allow_result = _run_cli(tmp_path, _artifact_payload())
    block_result = _run_cli(
        tmp_path,
        _artifact_payload(),
        trace_id=None,
        span_id=None,
        parent_span_id=None,
        run_id=None,
    )

    allow_payload = _stdout_payload(allow_result)
    block_payload = _stdout_payload(block_result)

    assert allow_result.stderr == ""
    assert block_result.stderr == ""
    assert allow_payload["system_response"] == "allow"
    assert block_payload["system_response"] == "block"
    assert block_payload["error"]["code"] == "MISSING_TRACE_CONTEXT"
