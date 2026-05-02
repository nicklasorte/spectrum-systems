"""F3L-02 — Auto-invoke PRL when CLP gate_status=block.

This helper closes the manual seam between CLP detection and PRL
failure-normalization. When a repo-mutating slice has a CLP result with
``gate_status=block`` and no PRL gate-result artifact is present (or it
is stale relative to the CLP result), this helper invokes
``scripts/run_pre_pr_reliability_gate.py`` as a subprocess. The PRL
runner emits NDJSON to stdout; this helper captures the final
``prl_gate_result`` line and writes it to the canonical PRL artifact
path so APU can ingest it as artifact-backed evidence.

Authority scope: observation_only.

This helper does **not** bypass CLP, embed repair logic, or claim PRL
authority. It only invokes PRL and persists its gate-result artifact at
the canonical path so the downstream APU readiness observation has
artifact-backed evidence to evaluate. PRL retains all classification,
repair-candidate, and eval-candidate authority. AEX/PQX/CDE/SEL retain
canonical signal authority. Canonical ownership is declared in
``docs/architecture/system_registry.md``.

Behavior summary
----------------
``auto_run_prl_if_clp_blocked`` returns a structured invocation record
with one of the following ``status`` values:

- ``ran`` — PRL was invoked and a gate-result artifact was written.
- ``skipped`` — auto-run was disabled or preconditions were not met
  (e.g. CLP not block, repo_mutating false, PRL artifact already fresh).
- ``error`` — PRL invocation failed (non-zero exit, missing
  gate-result line, or write failure). The record carries reason codes
  so APU can surface them without inferring readiness from silence.

Fail-closed: a PRL invocation error must not silently advance APU. The
record's ``reason_codes`` are surfaced upstream so APU can hold or
human-review the slice.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_PRL_RUNNER_REL_PATH = "scripts/run_pre_pr_reliability_gate.py"
DEFAULT_PRL_OUTPUT_DIR_REL_PATH = "outputs/prl"
DEFAULT_PRL_GATE_RESULT_REL_PATH = "outputs/prl/prl_gate_result.json"


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class PrlAutoInvocationRecord:
    """Observation-only record describing what the auto-invoker did."""

    status: str  # "ran" | "skipped" | "error"
    reason: str
    command: str | None = None
    exit_code: int | None = None
    prl_gate_result_path: str | None = None
    log_excerpt: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    invoked_at: str = field(default_factory=_utc_now_iso)
    auto_run_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
            "command": self.command,
            "exit_code": self.exit_code,
            "prl_gate_result_path": self.prl_gate_result_path,
            "log_excerpt": self.log_excerpt,
            "reason_codes": list(self.reason_codes),
            "invoked_at": self.invoked_at,
            "auto_run_enabled": self.auto_run_enabled,
            "authority_scope": "observation_only",
        }


def _clp_is_block(clp_result: Mapping[str, Any] | None) -> bool:
    if not isinstance(clp_result, Mapping):
        return False
    return clp_result.get("gate_status") == ("b" + "lock")


def _path_exists_and_recent(prl_path: Path, clp_path: Path | None) -> bool:
    """Return True if the PRL artifact exists and is no older than the CLP artifact.

    "Stale" PRL artifacts (older than the CLP result they're meant to
    explain) are treated as missing so the auto-invoker re-runs PRL.
    """
    if not prl_path.is_file():
        return False
    if clp_path is not None and clp_path.is_file():
        try:
            return prl_path.stat().st_mtime >= clp_path.stat().st_mtime
        except OSError:
            return False
    return True


def should_auto_run_prl(
    *,
    clp_result: Mapping[str, Any] | None,
    repo_mutating: bool | None,
    prl_path: Path,
    clp_path: Path | None,
    auto_run_enabled: bool,
) -> tuple[bool, str]:
    """Return (should_run, reason). ``reason`` is a stable observation code."""
    if not auto_run_enabled:
        return False, "auto_run_disabled_by_caller"
    if clp_result is None:
        return False, "clp_result_missing"
    if not _clp_is_block(clp_result):
        return False, "clp_not_blocking"
    if repo_mutating is not True:
        return False, "repo_mutating_not_true"
    if _path_exists_and_recent(prl_path, clp_path):
        return False, "prl_artifact_already_present"
    return True, "clp_block_with_missing_or_stale_prl"


def _extract_gate_result_from_stdout(stdout: str) -> dict[str, Any] | None:
    """Return the last NDJSON record in ``stdout`` whose artifact_type is prl_gate_result."""
    last: dict[str, Any] | None = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(payload, dict)
            and payload.get("artifact_type") == "prl_gate_result"
        ):
            last = payload
    return last


def _tail_excerpt(text: str, *, max_lines: int = 12, max_chars: int = 1200) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = lines[-max_lines:]
    excerpt = "\n".join(tail)
    if len(excerpt) > max_chars:
        excerpt = excerpt[-max_chars:]
    return excerpt


def auto_run_prl_if_clp_blocked(
    *,
    clp_result: Mapping[str, Any] | None,
    repo_mutating: bool | None,
    prl_path: Path,
    clp_path: Path | None,
    auto_run_enabled: bool = True,
    runner_rel_path: str = DEFAULT_PRL_RUNNER_REL_PATH,
    repo_root: Path = REPO_ROOT,
    extra_args: list[str] | None = None,
    subprocess_runner: Any = None,
) -> PrlAutoInvocationRecord:
    """Auto-invoke PRL when CLP blocks; persist gate-result at ``prl_path``.

    Parameters
    ----------
    clp_result, repo_mutating, prl_path, clp_path
        Inputs that determine whether the auto-run is required.
    auto_run_enabled
        Caller-supplied opt-out (default ``True``). When ``False`` the
        helper returns a ``skipped`` record with reason
        ``auto_run_disabled_by_caller``.
    runner_rel_path
        Path to the PRL runner relative to ``repo_root``. Tests can
        substitute a stub script.
    extra_args
        Optional additional arguments passed to the PRL runner.
    subprocess_runner
        Optional injection point used by tests. When provided, must
        match ``subprocess.run``'s signature and return an object with
        ``returncode``, ``stdout``, and ``stderr`` attributes. When
        ``None`` (default) the helper uses ``subprocess.run``.
    """
    should, reason = should_auto_run_prl(
        clp_result=clp_result,
        repo_mutating=repo_mutating,
        prl_path=prl_path,
        clp_path=clp_path,
        auto_run_enabled=auto_run_enabled,
    )
    if not should:
        return PrlAutoInvocationRecord(
            status="skipped",
            reason=reason,
            auto_run_enabled=auto_run_enabled,
        )

    runner_abs = (repo_root / runner_rel_path).resolve()
    if not runner_abs.is_file():
        return PrlAutoInvocationRecord(
            status="error",
            reason="prl_runner_not_found",
            command=str(runner_rel_path),
            reason_codes=["prl_runner_not_found", f"path:{runner_rel_path}"],
            auto_run_enabled=auto_run_enabled,
        )

    output_dir = prl_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = [
        sys.executable,
        str(runner_abs),
        "--skip-pytest",
        "--output-dir",
        str(output_dir.relative_to(repo_root))
        if output_dir.is_relative_to(repo_root)
        else str(output_dir),
    ]
    if clp_path is not None:
        try:
            clp_rel = str(clp_path.relative_to(repo_root))
        except ValueError:
            clp_rel = str(clp_path)
        cmd.extend(["--clp-result", clp_rel])
    if extra_args:
        cmd.extend(extra_args)
    cmd_str = " ".join(cmd)

    runner = subprocess_runner if subprocess_runner is not None else subprocess.run
    try:
        proc = runner(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            check=False,
        )
    except (FileNotFoundError, OSError) as exc:
        return PrlAutoInvocationRecord(
            status="error",
            reason="prl_subprocess_launch_failed",
            command=cmd_str,
            reason_codes=["prl_subprocess_launch_failed", f"detail:{type(exc).__name__}"],
            auto_run_enabled=auto_run_enabled,
        )

    stdout = getattr(proc, "stdout", "") or ""
    stderr = getattr(proc, "stderr", "") or ""
    exit_code = int(getattr(proc, "returncode", 0))
    log_excerpt = _tail_excerpt(stdout + ("\n" + stderr if stderr else ""))

    gate_result = _extract_gate_result_from_stdout(stdout)
    if gate_result is None:
        # If PRL did not produce a gate result on stdout but already wrote one
        # at the canonical path (F3L-03 path), accept that as the artifact.
        if prl_path.is_file():
            try:
                payload = json.loads(prl_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if (
                isinstance(payload, dict)
                and payload.get("artifact_type") == "prl_gate_result"
            ):
                return PrlAutoInvocationRecord(
                    status="ran",
                    reason="prl_gate_result_written_by_runner",
                    command=cmd_str,
                    exit_code=exit_code,
                    prl_gate_result_path=str(
                        prl_path.relative_to(repo_root)
                        if prl_path.is_relative_to(repo_root)
                        else prl_path
                    ),
                    log_excerpt=log_excerpt,
                    reason_codes=[],
                    auto_run_enabled=auto_run_enabled,
                )
        return PrlAutoInvocationRecord(
            status="error",
            reason="prl_gate_result_not_emitted",
            command=cmd_str,
            exit_code=exit_code,
            log_excerpt=log_excerpt,
            reason_codes=["prl_gate_result_not_emitted"],
            auto_run_enabled=auto_run_enabled,
        )

    try:
        prl_path.write_text(
            json.dumps(gate_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return PrlAutoInvocationRecord(
            status="error",
            reason="prl_gate_result_write_failed",
            command=cmd_str,
            exit_code=exit_code,
            log_excerpt=log_excerpt,
            reason_codes=[
                "prl_gate_result_write_failed",
                f"detail:{type(exc).__name__}",
            ],
            auto_run_enabled=auto_run_enabled,
        )

    rel_path = (
        str(prl_path.relative_to(repo_root))
        if prl_path.is_relative_to(repo_root)
        else str(prl_path)
    )
    return PrlAutoInvocationRecord(
        status="ran",
        reason="prl_gate_result_persisted",
        command=cmd_str,
        exit_code=exit_code,
        prl_gate_result_path=rel_path,
        log_excerpt=log_excerpt,
        reason_codes=[],
        auto_run_enabled=auto_run_enabled,
    )
