from __future__ import annotations

import sys

from spectrum_systems.modules.hop.sandbox import SandboxConfig, execute_candidate
from tests.hop.conftest import make_baseline_candidate


def test_sandbox_allows_baseline():
    candidate = make_baseline_candidate()
    result = execute_candidate(
        candidate_payload=candidate,
        harness_input={"transcript_id": "t1", "turns": [{"speaker": "u", "text": "What is HOP?"}]},
    )
    assert result.ok is True
    assert isinstance(result.output, dict)


def test_sandbox_blocks_network_access(tmp_path):
    mod = tmp_path / "payload_net.py"
    mod.write_text("def run(t):\n import socket\n socket.socket()\n return {}\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        candidate = make_baseline_candidate(code_source=mod.read_text(encoding="utf-8"))
        candidate["code_module"] = "payload_net"
        candidate["code_entrypoint"] = "run"
        result = execute_candidate(candidate_payload=candidate, harness_input={"transcript_id": "x", "utterances": []})
        assert result.ok is False
        assert result.violation_type == "sandbox_violation"
    finally:
        sys.path.remove(str(tmp_path))


def test_sandbox_blocks_subprocess(tmp_path):
    mod = tmp_path / "payload_mod.py"
    mod.write_text("def run(t):\n import subprocess\n subprocess.Popen(['echo','x'])\n return {}\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        candidate = make_baseline_candidate(code_source=mod.read_text(encoding="utf-8"))
        candidate["code_module"] = "payload_mod"
        candidate["code_entrypoint"] = "run"
        result = execute_candidate(
            candidate_payload=candidate,
            harness_input={"transcript_id": "x", "utterances": []},
            config=SandboxConfig(timeout_seconds=2.0),
        )
        assert result.ok is False
        assert result.violation_type == "sandbox_violation"
    finally:
        sys.path.remove(str(tmp_path))


def test_sandbox_blocks_file_write_outside_temp(tmp_path):
    mod = tmp_path / "payload_write.py"
    mod.write_text("def run(t):\n open('/tmp/hop_escape.txt','w').write('x')\n return {}\n", encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        candidate = make_baseline_candidate(code_source=mod.read_text(encoding="utf-8"))
        candidate["code_module"] = "payload_write"
        candidate["code_entrypoint"] = "run"
        result = execute_candidate(candidate_payload=candidate, harness_input={"transcript_id": "x", "utterances": []})
        assert result.ok is False
        assert result.violation_type == "sandbox_violation"
    finally:
        sys.path.remove(str(tmp_path))
