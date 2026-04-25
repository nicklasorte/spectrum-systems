"""Sandboxed harness execution for HOP-BATCH-3.

All candidate execution must pass through this module. It isolates runtime
behavior in a subprocess, denies unsafe operations, and returns structured
failure details for policy_observation downstream.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Mapping


class SandboxError(Exception):
    """Raised on sandbox infrastructure errors."""


@dataclass(frozen=True)
class SandboxConfig:
    timeout_seconds: float = 2.0
    memory_limit_mb: int = 256
    denied_read_path_prefixes: tuple[str, ...] = ()
    """Paths whose subtrees the candidate may not read.

    Used to keep eval-data (search and held-out cases) out of the
    candidate's reach so memorising them is not possible. Empty tuple
    keeps the previous behavior.
    """


@dataclass(frozen=True)
class SandboxResult:
    ok: bool
    output: dict[str, Any] | None
    violation_type: str | None
    detail: str | None


_CHILD_CODE = r'''
import builtins
import json
import os
import pathlib
import socket
import subprocess
import sys

class SandboxViolation(Exception):
    pass


def _deny(*_args, **_kwargs):
    raise SandboxViolation("sandbox_violation:operation_blocked")


def _resolve(path):
    return pathlib.Path(path).resolve()


def _is_write_mode(mode):
    return any(ch in mode for ch in ("w", "a", "x", "+"))


def _ensure_within(path, root):
    p = _resolve(path)
    if p == root:
        return
    if root not in p.parents:
        raise SandboxViolation(f"sandbox_violation:file_write_outside_temp:{p}")


def _ensure_not_under_denied(path, denied_roots):
    if not denied_roots:
        return
    p = _resolve(path)
    for d in denied_roots:
        if p == d or d in p.parents:
            raise SandboxViolation(f"sandbox_violation:read_denied_eval_data:{p}")


def _install_guards(tmp_root: pathlib.Path, denied_roots: list):
    original_open = builtins.open
    def guarded_open(file, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            _ensure_within(file, tmp_root)
        else:
            _ensure_not_under_denied(file, denied_roots)
        return original_open(file, mode, *args, **kwargs)

    builtins.open = guarded_open

    os_open = os.open
    def guarded_os_open(path, flags, *args, **kwargs):
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        if flags & write_flags:
            _ensure_within(path, tmp_root)
        else:
            _ensure_not_under_denied(path, denied_roots)
        return os_open(path, flags, *args, **kwargs)

    os.open = guarded_os_open

    path_open = pathlib.Path.open
    def guarded_path_open(self, mode="r", *args, **kwargs):
        if _is_write_mode(mode):
            _ensure_within(self, tmp_root)
        else:
            _ensure_not_under_denied(self, denied_roots)
        return path_open(self, mode, *args, **kwargs)

    pathlib.Path.open = guarded_path_open

    path_write_text = pathlib.Path.write_text
    def guarded_write_text(self, *args, **kwargs):
        _ensure_within(self, tmp_root)
        return path_write_text(self, *args, **kwargs)

    pathlib.Path.write_text = guarded_write_text

    path_write_bytes = pathlib.Path.write_bytes
    def guarded_write_bytes(self, *args, **kwargs):
        _ensure_within(self, tmp_root)
        return path_write_bytes(self, *args, **kwargs)

    pathlib.Path.write_bytes = guarded_write_bytes

    socket.socket = _deny
    socket.create_connection = _deny
    subprocess.Popen = _deny
    subprocess.run = _deny
    subprocess.call = _deny
    subprocess.check_call = _deny
    subprocess.check_output = _deny

    os.environ.clear()
    class _EnvProxy(dict):
        def __getitem__(self, _k):
            raise SandboxViolation("sandbox_violation:env_access")
        def get(self, _k, _d=None):
            raise SandboxViolation("sandbox_violation:env_access")
    os.environ = _EnvProxy()
    os.getenv = _deny


def _apply_resource_limits(mem_mb: int):
    try:
        import resource
    except Exception:
        return
    bytes_limit = int(mem_mb) * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))
    except Exception:
        pass


def main():
    payload = json.loads(sys.stdin.read())
    candidate = payload["candidate"]
    harness_input = payload["input"]
    tmp_root = pathlib.Path(payload["tmp_root"]).resolve()
    tmp_root.mkdir(parents=True, exist_ok=True)

    _apply_resource_limits(int(payload.get("memory_limit_mb", 256)))
    denied_roots = [
        pathlib.Path(p).resolve()
        for p in payload.get("denied_read_path_prefixes", []) or []
    ]
    _install_guards(tmp_root, denied_roots)

    try:
        repo_root = payload.get("repo_root")
        if isinstance(repo_root, str) and repo_root:
            sys.path.insert(0, repo_root)
        namespace = {}
        exec(candidate["code_source"], namespace, namespace)
        entry = namespace[candidate["code_entrypoint"]]
        output = entry(harness_input)
        print(json.dumps({"ok": True, "output": output}))
    except SandboxViolation as exc:
        print(json.dumps({"ok": False, "violation_type": "sandbox_violation", "detail": str(exc)}))
    except Exception as exc:
        print(json.dumps({"ok": False, "violation_type": "runtime_error", "detail": f"{type(exc).__name__}:{exc}"}))


if __name__ == "__main__":
    main()
'''


def execute_candidate(
    *,
    candidate_payload: Mapping[str, Any],
    harness_input: Mapping[str, Any],
    config: SandboxConfig | None = None,
) -> SandboxResult:
    cfg = config or SandboxConfig()
    with tempfile.TemporaryDirectory(prefix="hop_sandbox_") as temp_dir:
        payload = {
            "candidate": {
                "code_source": candidate_payload["code_source"],
                "code_entrypoint": candidate_payload["code_entrypoint"],
                "code_module": candidate_payload.get("code_module", ""),
            },
            "input": dict(harness_input),
            "tmp_root": temp_dir,
            "memory_limit_mb": cfg.memory_limit_mb,
            "repo_root": str((__import__("pathlib").Path(__file__).resolve().parents[3])),
            "denied_read_path_prefixes": list(cfg.denied_read_path_prefixes),
        }
        proc = subprocess.run(
            [sys.executable, "-I", "-c", _CHILD_CODE],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=cfg.timeout_seconds,
            env={},
            check=False,
        )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise SandboxError(f"hop_sandbox_process_error:rc={proc.returncode}:{stderr}")
    try:
        result = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        raise SandboxError("hop_sandbox_invalid_json") from exc
    if result.get("ok"):
        output = result.get("output")
        if not isinstance(output, dict):
            return SandboxResult(
                ok=False,
                output=None,
                violation_type="runtime_error",
                detail="sandbox_violation:non_object_output",
            )
        return SandboxResult(ok=True, output=output, violation_type=None, detail=None)
    return SandboxResult(
        ok=False,
        output=None,
        violation_type=result.get("violation_type", "runtime_error"),
        detail=result.get("detail", "unknown"),
    )
