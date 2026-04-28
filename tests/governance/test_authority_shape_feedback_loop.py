"""ASF-01 authority-shape feedback loop tests.

Cover the chain:

- changed-scope scan detects authority terms in MET docs/tests
- scan passes when only neutral replacements are present
- RIL interpretation packet maps findings to authority_shape_violation
- FRE repair candidate proposes only neutral replacements
- FRE repair candidate rejects allowlist changes
- FRE repair candidate rejects owner registry changes
- TPA policy check fails unsafe repairs
- TPA policy check passes safe vocabulary-only repairs
- artifacts validate against their schemas
- no network is required
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"
NEUTRAL_VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_neutral_vocabulary.json"

PACKET_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "authority_shape_interpretation_packet.schema.json"
)
CANDIDATE_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "authority_shape_repair_candidate.schema.json"
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_SCAN = _load_module(
    "_test_asf01_changed_scope_scan",
    REPO_ROOT / "scripts" / "run_changed_scope_authority_scan.py",
)
_VALIDATE = _load_module(
    "_test_asf01_validate_repair",
    REPO_ROOT / "scripts" / "validate_authority_repair_candidate.py",
)
_LOOP = _load_module(
    "_test_asf01_loop",
    REPO_ROOT / "scripts" / "run_authority_shape_feedback_loop.py",
)


@pytest.fixture()
def vocab():
    return _SCAN.load_vocabulary(VOCAB_PATH)


@pytest.fixture()
def vocabulary_payload():
    return json.loads(VOCAB_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def neutral_payload():
    return json.loads(NEUTRAL_VOCAB_PATH.read_text(encoding="utf-8"))


@pytest.fixture()
def block_network(monkeypatch):
    """Fail-loudly if anything tries to open a socket during these tests."""

    def _no_socket(*args, **kwargs):  # pragma: no cover - defensive
        raise RuntimeError("network access is forbidden in ASF-01 tests")

    monkeypatch.setattr(socket, "socket", _no_socket)


def _seed_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for rel, body in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return repo


# ---------------------------------------------------------------------------
# Scan tests
# ---------------------------------------------------------------------------


def test_changed_scope_scan_detects_authority_terms_in_met_docs(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_metrics_writeup.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    record = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_metrics_writeup.py"],
        vocab=vocab,
    )
    assert record["status"] == "warn"
    assert record["finding_count"] >= 1
    clusters = {f["cluster"] for f in record["findings"]}
    assert "promotion" in clusters or "decision" in clusters
    for f in record["findings"]:
        assert f["repair_scope"] == "changed_file_only"
        assert f["owning_system_guess"] in {"MET", "runtime_support"}


def test_changed_scope_scan_passes_on_neutral_replacements(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_metrics_writeup.py": (
                'METRIC = {"promotion_signal": "ready_for_gate_review"}\n'
            )
        },
    )
    record = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_metrics_writeup.py"],
        vocab=vocab,
    )
    assert record["status"] == "pass"
    assert record["finding_count"] == 0


def test_changed_scope_scan_strict_mode_blocks(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_metrics_writeup.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    record = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_metrics_writeup.py"],
        vocab=vocab,
        strict=True,
    )
    assert record["status"] == "block"
    assert "strict_mode_block" in record["reason_codes"]


# ---------------------------------------------------------------------------
# RIL interpretation tests
# ---------------------------------------------------------------------------


def test_interpretation_packet_maps_to_authority_shape_violation(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_view.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    scan = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    packet = _LOOP.build_interpretation_packet(
        scan_record=scan,
        scan_record_path="outputs/authority_shape_preflight/changed_scope_authority_scan_record.json",
    )
    assert packet["artifact_type"] == "authority_shape_interpretation_packet"
    assert packet["status"] == "interpreted"
    assert packet["interpreted_findings"]
    for f in packet["interpreted_findings"]:
        assert f["failure_class"] == "authority_shape_violation"
        assert f["safe_repair_strategy"]["scope"] == "changed_file_only"
        assert "modify_authority_registry" in f["unsafe_repair_patterns"]
        assert "add_allowlist_exception" in f["unsafe_repair_patterns"]
        assert (
            f["affected_owner_boundary"]["canonical_authority_source"]
            == "docs/architecture/system_registry.md"
        )


def test_interpretation_packet_validates_against_schema(tmp_path, vocab, block_network):
    jsonschema = pytest.importorskip("jsonschema")
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_view.py": (
                'METRIC = {"rollback_record": "abc"}\n'
            )
        },
    )
    scan = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    packet = _LOOP.build_interpretation_packet(
        scan_record=scan,
        scan_record_path="outputs/authority_shape_preflight/changed_scope_authority_scan_record.json",
    )
    schema = json.loads(PACKET_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=packet, schema=schema)


# ---------------------------------------------------------------------------
# FRE repair candidate tests
# ---------------------------------------------------------------------------


def test_repair_candidate_proposes_only_neutral_replacements(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_view.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    scan = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    packet = _LOOP.build_interpretation_packet(
        scan_record=scan, scan_record_path="x"
    )
    candidate = _LOOP.build_repair_candidate(packet=packet, packet_path="y")
    assert candidate["status"] == "proposed"
    assert candidate["replacements"]
    for r in candidate["replacements"]:
        assert r["replacement_class"] == "vocabulary_only"
    required = {
        "no_allowlist_change",
        "no_owner_registry_change",
        "no_cross_file_rewrite_without_evidence",
    }
    assert required.issubset(set(candidate["prohibited_actions"]))


def test_repair_candidate_validates_against_schema(tmp_path, vocab, block_network):
    jsonschema = pytest.importorskip("jsonschema")
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_view.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    scan = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    packet = _LOOP.build_interpretation_packet(scan_record=scan, scan_record_path="x")
    candidate = _LOOP.build_repair_candidate(packet=packet, packet_path="y")
    schema = json.loads(CANDIDATE_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=candidate, schema=schema)


# ---------------------------------------------------------------------------
# TPA policy check tests
# ---------------------------------------------------------------------------


def _safe_candidate() -> dict:
    return {
        "artifact_type": "authority_shape_repair_candidate",
        "schema_version": "1.0.0",
        "repair_candidate_id": "fre-asf01-test-safe",
        "source_interpretation_packet": {
            "artifact_type": "authority_shape_interpretation_packet",
            "path": "outputs/authority_shape_preflight/authority_shape_interpretation_packet.json",
            "packet_id": "ril-asf01-test",
        },
        "target_files": ["spectrum_systems/modules/runtime/met_view.py"],
        "replacements": [
            {
                "file": "spectrum_systems/modules/runtime/met_view.py",
                "line": 1,
                "current_symbol": "promotion_decision",
                "proposed_symbol": "promotion_signal",
                "reason": "MET surfaces emit signals, not decisions.",
                "replacement_class": "vocabulary_only",
                "cluster": "promotion",
            }
        ],
        "prohibited_actions": [
            "no_allowlist_change",
            "no_owner_registry_change",
            "no_cross_file_rewrite_without_evidence",
        ],
        "status": "proposed",
        "reason_codes": ["bounded_vocabulary_repair"],
    }


def _safe_scan_record() -> dict:
    return {
        "artifact_type": "changed_scope_authority_scan_record",
        "schema_version": "1.0.0",
        "run_id": "asf01-test",
        "changed_files": ["spectrum_systems/modules/runtime/met_view.py"],
        "findings": [],
        "finding_count": 0,
        "status": "warn",
        "reason_codes": [],
    }


def test_tpa_passes_safe_vocabulary_only_repairs(vocabulary_payload, neutral_payload, block_network):
    record = _VALIDATE.validate_candidate(
        candidate=_safe_candidate(),
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "pass"
    assert record["findings"] == []


def test_tpa_rejects_allowlist_change_intent(vocabulary_payload, neutral_payload, block_network):
    candidate = _safe_candidate()
    candidate["allowlist_changes"] = [
        {"path": "spectrum_systems/modules/runtime/met_view.py", "exempt": True}
    ]
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "forbidden_intent_field_present" in record["reason_codes"]


def test_tpa_rejects_owner_registry_target(vocabulary_payload, neutral_payload, block_network):
    candidate = _safe_candidate()
    candidate["target_files"] = ["contracts/governance/authority_registry.json"]
    candidate["replacements"][0]["file"] = "contracts/governance/authority_registry.json"
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record={
            **_safe_scan_record(),
            "changed_files": ["contracts/governance/authority_registry.json"],
        },
    )
    assert record["status"] == "fail"
    assert "target_protected_authority_file" in record["reason_codes"]


def test_tpa_rejects_non_vocabulary_only_replacement(
    vocabulary_payload, neutral_payload, block_network
):
    candidate = _safe_candidate()
    candidate["replacements"][0]["replacement_class"] = "structural_rewrite"
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "non_vocabulary_only_replacement" in record["reason_codes"]


def test_tpa_rejects_replacement_outside_changed_files(
    vocabulary_payload, neutral_payload, block_network
):
    candidate = _safe_candidate()
    candidate["target_files"] = ["spectrum_systems/modules/runtime/other_file.py"]
    candidate["replacements"][0]["file"] = "spectrum_systems/modules/runtime/other_file.py"
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "replacement_outside_changed_files" in record["reason_codes"]


def test_tpa_rejects_non_neutral_proposed_symbol(
    vocabulary_payload, neutral_payload, block_network
):
    candidate = _safe_candidate()
    candidate["replacements"][0]["proposed_symbol"] = "promotion_decision"
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "non_neutral_replacement" in record["reason_codes"]


def test_tpa_rejects_missing_required_prohibited_actions(
    vocabulary_payload, neutral_payload, block_network
):
    candidate = _safe_candidate()
    candidate["prohibited_actions"] = ["no_allowlist_change"]
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "missing_prohibited_actions" in record["reason_codes"]


def test_tpa_rejects_non_proposed_status(vocabulary_payload, neutral_payload, block_network):
    candidate = _safe_candidate()
    candidate["status"] = "applied"
    record = _VALIDATE.validate_candidate(
        candidate=candidate,
        vocabulary=vocabulary_payload,
        neutral_vocab=neutral_payload,
        scan_record=_safe_scan_record(),
    )
    assert record["status"] == "fail"
    assert "non_proposed_status" in record["reason_codes"]


# ---------------------------------------------------------------------------
# Determinism / no-network sanity
# ---------------------------------------------------------------------------


def test_loop_chain_is_deterministic_for_the_same_inputs(tmp_path, vocab, block_network):
    repo = _seed_repo(
        tmp_path,
        {
            "spectrum_systems/modules/runtime/met_view.py": (
                'METRIC = {"promotion_decision": "ready"}\n'
            )
        },
    )
    scan_a = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    scan_b = _SCAN.build_scan_record(
        repo_root=repo,
        changed_files=["spectrum_systems/modules/runtime/met_view.py"],
        vocab=vocab,
    )
    assert scan_a["finding_count"] == scan_b["finding_count"]
    assert scan_a["status"] == scan_b["status"]
    assert [f["symbol"] for f in scan_a["findings"]] == [f["symbol"] for f in scan_b["findings"]]
