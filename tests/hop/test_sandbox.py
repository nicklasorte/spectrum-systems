"""Tests for the HOP sandbox execution layer.

The sandbox is the only authorized surface through which a candidate
runner may be executed. These tests assert it:

- Forwards normal output for a well-behaved runner.
- Blocks network, subprocess, and environment access from inside the
  worker.
- Blocks file writes outside the configured scratch dir.
- Surfaces wall-clock timeouts as :class:`SandboxTimeout`.
- Refuses to wrap non-importable runners (lambdas / inner functions).
- Cannot be silently bypassed via the optimization-loop wrapper.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from spectrum_systems.modules.hop import sandbox
from spectrum_systems.modules.hop.patterns import draft_verify
from spectrum_systems.modules.hop import baseline_harness


# ---------------------------------------------------------------------------
# Top-level runners reused by tests. They MUST live at module scope so the
# sandbox can re-import them in the worker process.
# ---------------------------------------------------------------------------


def _runner_echo(case_input: Mapping[str, Any]) -> dict[str, Any]:
    return {"echo": dict(case_input)}


def _runner_open_outside(case_input: Mapping[str, Any]) -> dict[str, Any]:
    # Try to write outside any scratch dir.
    target = "/tmp/hop_sandbox_test_should_be_blocked.txt"
    with open(target, "w", encoding="utf-8") as f:
        f.write("escape")
    return {"wrote_to": target}


def _runner_subprocess(case_input: Mapping[str, Any]) -> dict[str, Any]:
    import subprocess

    subprocess.run(["echo", "boom"], check=False)
    return {"shell": "ran"}


def _runner_network(case_input: Mapping[str, Any]) -> dict[str, Any]:
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
    return {"net": "ok"}


def _runner_env(case_input: Mapping[str, Any]) -> dict[str, Any]:
    # If env was scrubbed, USER returns None; the runner should signal that.
    return {"user": os.environ.get("USER", "<scrubbed>")}


def _runner_putenv(case_input: Mapping[str, Any]) -> dict[str, Any]:
    os.putenv("HOP_SANDBOX_LEAK", "1")
    return {"putenv": "ok"}


def _runner_sleep_forever(case_input: Mapping[str, Any]) -> dict[str, Any]:
    import time

    time.sleep(60.0)
    return {"slept": True}


def _runner_baseline(case_input: Mapping[str, Any]) -> dict[str, Any]:
    return baseline_harness.run(case_input)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_sandbox_returns_runner_output() -> None:
    out = sandbox.run_in_sandbox(
        runner=_runner_echo,
        case_input={"transcript_id": "t_one", "turns": []},
    )
    assert out == {"echo": {"transcript_id": "t_one", "turns": []}}


def test_sandbox_runs_baseline_harness_unmodified() -> None:
    out = sandbox.run_in_sandbox(
        runner=_runner_baseline,
        case_input={
            "transcript_id": "t_one_qa",
            "turns": [
                {"speaker": "user", "text": "What is HOP?"},
                {"speaker": "assistant", "text": "Harness Optimization Pipeline."},
            ],
        },
    )
    assert out["artifact_type"] == "hop_harness_faq_output"
    assert out["transcript_id"] == "t_one_qa"
    assert out["items"][0]["question"] == "What is HOP?"


def test_sandbox_runs_draft_verify_pattern() -> None:
    out = sandbox.run_in_sandbox(
        runner=(draft_verify.__name__, "run"),
        case_input={
            "transcript_id": "t_two",
            "turns": [
                {"speaker": "user", "text": "What is HOP?"},
                {"speaker": "assistant", "text": "It is a pipeline."},
            ],
        },
    )
    assert out["artifact_type"] == "hop_harness_faq_output"
    assert out["candidate_id"] == draft_verify.PATTERN_ID
    assert out["items"]


# ---------------------------------------------------------------------------
# blockers
# ---------------------------------------------------------------------------


def test_sandbox_blocks_subprocess() -> None:
    with pytest.raises(sandbox.SandboxBlocked):
        sandbox.run_in_sandbox(
            runner=_runner_subprocess,
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_blocks_network() -> None:
    with pytest.raises(sandbox.SandboxBlocked):
        sandbox.run_in_sandbox(
            runner=_runner_network,
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_blocks_env_putenv() -> None:
    with pytest.raises(sandbox.SandboxBlocked):
        sandbox.run_in_sandbox(
            runner=_runner_putenv,
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_scrubs_environment() -> None:
    out = sandbox.run_in_sandbox(
        runner=_runner_env,
        case_input={"transcript_id": "t", "turns": []},
    )
    assert out["user"] == "<scrubbed>"


def test_sandbox_blocks_writes_outside_scratch(tmp_path: Path) -> None:
    cfg = sandbox.SandboxConfig(scratch_dir=str(tmp_path / "scratch"))
    with pytest.raises(sandbox.SandboxBlocked):
        sandbox.run_in_sandbox(
            runner=_runner_open_outside,
            case_input={"transcript_id": "t", "turns": []},
            config=cfg,
        )


# ---------------------------------------------------------------------------
# limits
# ---------------------------------------------------------------------------


def test_sandbox_enforces_timeout() -> None:
    cfg = sandbox.SandboxConfig(timeout_seconds=0.5)
    with pytest.raises(sandbox.SandboxTimeout):
        sandbox.run_in_sandbox(
            runner=_runner_sleep_forever,
            case_input={"transcript_id": "t", "turns": []},
            config=cfg,
        )


# ---------------------------------------------------------------------------
# config errors — non-bypass guarantees
# ---------------------------------------------------------------------------


def test_sandbox_rejects_inner_function() -> None:
    def _inner(_case: Mapping[str, Any]) -> dict[str, Any]:
        return {"inner": True}

    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.run_in_sandbox(
            runner=_inner,
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_rejects_lambda() -> None:
    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.run_in_sandbox(
            runner=lambda c: c,  # type: ignore[arg-type, return-value]
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_rejects_invalid_runner_tuple() -> None:
    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.run_in_sandbox(
            runner=("only_one_part",),  # type: ignore[arg-type]
            case_input={"transcript_id": "t", "turns": []},
        )


def test_sandbox_rejects_invalid_case_input() -> None:
    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.run_in_sandbox(
            runner=_runner_echo,
            case_input="not-a-mapping",  # type: ignore[arg-type]
        )


def test_sandbox_config_validates_timeout() -> None:
    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.SandboxConfig(timeout_seconds=0)


def test_sandbox_config_validates_memory() -> None:
    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.SandboxConfig(memory_limit_bytes=0)


# ---------------------------------------------------------------------------
# wrapper helper
# ---------------------------------------------------------------------------


def test_make_sandboxed_runner_routes_through_sandbox() -> None:
    wrapped = sandbox.make_sandboxed_runner(runner=_runner_subprocess)
    with pytest.raises(sandbox.SandboxBlocked):
        wrapped({"transcript_id": "t", "turns": []})


def test_make_sandboxed_runner_rejects_inner_function() -> None:
    def _inner(_case: Mapping[str, Any]) -> dict[str, Any]:
        return {"inner": True}

    with pytest.raises(sandbox.SandboxConfigError):
        sandbox.make_sandboxed_runner(runner=_inner)
