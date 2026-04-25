"""Sandbox execution layer for HOP candidate harnesses.

The sandbox is the **only** authorized surface through which a candidate
harness's runtime code may be invoked by the optimization loop. It
isolates the candidate from the host process so that a bug, a
prompt-injection-style payload encoded in a transcript, or an
adversarial mutation cannot:

- open a network socket (``socket``, ``urllib``, ``requests``, ``httpx``);
- write outside an allowlisted scratch directory;
- spawn a child process (``subprocess``, ``os.system``, ``os.popen``,
  ``os.exec*``, ``os.fork``, ``os.spawn*``);
- read or mutate the parent process environment.

It also enforces a deterministic wall-clock timeout and a memory cap.

Defense-in-depth strategy
-------------------------

Truly untrusted Python is unsandboxable in-process. So the sandbox
runs the candidate in a forked worker process and applies *both*
OS-level limits and import-time monkey patches before handing control
to the runner:

1. **Process isolation.** Every invocation forks a fresh worker via
   ``multiprocessing`` (``fork`` start method on POSIX, ``spawn``
   fallback elsewhere). The parent process is never affected by the
   child's state.
2. **Resource limits.** On POSIX we set ``RLIMIT_AS`` (memory) and
   ``RLIMIT_CPU`` (cpu seconds) via the ``resource`` module before
   user code executes. Exceeded limits surface as
   ``SandboxResourceExceeded``.
3. **Wall-clock timeout.** The parent waits at most ``timeout_seconds``
   on the child; on expiry the child is killed (``SIGKILL``) and the
   parent raises ``SandboxTimeout``.
4. **Block forbidden modules.** Before the runner is called, the
   sandbox replaces ``socket.socket``, ``subprocess.Popen``,
   ``os.system``, ``os.popen``, ``os.execv*``, ``os.fork``,
   ``os.spawn*``, ``urllib.request.urlopen``, and the bound versions
   on already-imported submodules with a no-op that raises
   :class:`SandboxBlocked`.
5. **Constrain file writes.** ``builtins.open`` is wrapped to raise
   :class:`SandboxBlocked` for any write/append/update mode whose
   resolved target lies outside the allowlisted scratch dir.
6. **Scrub environment.** ``os.environ`` is replaced with an empty
   ``os._Environ`` and ``os.getenv`` returns ``None``. The PATH is
   pinned to a no-op value so child shells (if they slipped past the
   subprocess block) cannot find tools.

Failures
--------

The sandbox is **fail-closed**. Any of:

- import error in the runner module;
- candidate raising while running the case;
- forbidden action (network/subprocess/env/write outside scratch);
- resource exhaustion;
- timeout;

surfaces as a typed :class:`SandboxError` subclass, never a soft
return value. The optimization loop converts these to
``hop_harness_failure_hypothesis`` artifacts at the calling site so
the existing failure-handling pipeline stays canonical.

Determinism
-----------

The sandbox does NOT introduce non-determinism. The same input,
runner module, and candidate body produce the same output. Latency
is observable but not part of the artifact's content hash.

Usage
-----

The optimization loop wraps any candidate runner in
:func:`make_sandboxed_runner` and passes the wrapped callable to the
evaluator. Direct calls to a candidate module's ``run`` are
prohibited outside the evaluator's sandbox path.
"""

from __future__ import annotations

import importlib
import multiprocessing as mp
import os
import pickle
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

try:  # pragma: no cover - posix-only path covered by CI
    import resource  # type: ignore[import]

    _HAS_RESOURCE = True
except ImportError:  # pragma: no cover - non-posix fallback
    resource = None  # type: ignore[assignment]
    _HAS_RESOURCE = False


DEFAULT_TIMEOUT_SECONDS: float = 5.0
DEFAULT_MEMORY_LIMIT_BYTES: int = 256 * 1024 * 1024  # 256 MiB
DEFAULT_CPU_SECONDS: int = 10


class SandboxError(Exception):
    """Base class for sandbox failures. All sandbox errors are fail-closed."""


class SandboxBlocked(SandboxError):
    """A forbidden action was attempted (network, subprocess, env, write)."""


class SandboxTimeout(SandboxError):
    """Wall-clock timeout exceeded."""


class SandboxResourceExceeded(SandboxError):
    """Memory or CPU limit exceeded."""


class SandboxRuntimeError(SandboxError):
    """The candidate raised an unhandled exception."""


class SandboxConfigError(SandboxError):
    """Misconfigured sandbox invocation."""


@dataclass(frozen=True)
class SandboxConfig:
    """Immutable sandbox configuration.

    ``scratch_dir`` is the only filesystem location the candidate may
    write to. If unset, the sandbox creates a fresh per-invocation
    temp dir and removes it on completion. The parent process never
    reads from this dir; results travel back via the multiprocessing
    pipe only.
    """

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    memory_limit_bytes: int = DEFAULT_MEMORY_LIMIT_BYTES
    cpu_seconds: int = DEFAULT_CPU_SECONDS
    scratch_dir: str | None = None
    block_network: bool = True
    block_subprocess: bool = True
    block_env: bool = True
    block_writes_outside_scratch: bool = True

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise SandboxConfigError(
                f"hop_sandbox_invalid_timeout:{self.timeout_seconds}"
            )
        if self.memory_limit_bytes <= 0:
            raise SandboxConfigError(
                f"hop_sandbox_invalid_memory:{self.memory_limit_bytes}"
            )
        if self.cpu_seconds <= 0:
            raise SandboxConfigError(
                f"hop_sandbox_invalid_cpu:{self.cpu_seconds}"
            )


# ---------------------------------------------------------------------------
# blockers — installed inside the worker before the runner executes
# ---------------------------------------------------------------------------


def _install_blockers(scratch_dir: str, config: SandboxConfig) -> None:
    """Replace dangerous module-level callables with raising stubs.

    Runs inside the worker process. We pre-import network/SSL/HTTP
    modules first so their class hierarchies are intact (``ssl``
    subclasses ``socket.socket`` at import time), then patch the
    creation surfaces so candidate code that *calls* them fails
    closed.
    """

    def _blocked(reason: str) -> Callable[..., Any]:
        def _raise(*_args: Any, **_kwargs: Any) -> Any:
            raise SandboxBlocked(f"hop_sandbox_blocked:{reason}")

        return _raise

    if config.block_network:
        # Pre-import the modules whose class hierarchies depend on
        # socket / each other. After this block, replacing the
        # creation symbols can no longer break a downstream import.
        for preload in ("socket", "ssl", "http.client", "urllib.request"):
            try:
                importlib.import_module(preload)
            except ImportError:
                continue

        try:
            import socket as _socket  # type: ignore[import]

            class _BlockedSocket:  # noqa: D401 - sentinel
                """Class stand-in for ``socket.socket`` that always raises."""

                def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                    raise SandboxBlocked("hop_sandbox_blocked:network:socket.socket")

            # Replace the constructor surface but keep the class
            # nature so subclassing in already-imported modules
            # (``ssl.SSLSocket``) is unaffected.
            _socket.socket = _BlockedSocket  # type: ignore[assignment]
            _socket.create_connection = _blocked(  # type: ignore[assignment]
                "network:socket.create_connection"
            )
            if hasattr(_socket, "create_server"):
                _socket.create_server = _blocked(  # type: ignore[assignment]
                    "network:socket.create_server"
                )
        except ImportError:
            pass

        for mod_name in (
            "urllib.request",
            "urllib3",
            "requests",
            "httpx",
            "http.client",
        ):
            try:
                mod = importlib.import_module(mod_name)
            except ImportError:
                continue
            for attr in ("urlopen", "request", "get", "post", "HTTPConnection"):
                if hasattr(mod, attr):
                    setattr(mod, attr, _blocked(f"network:{mod_name}.{attr}"))

    if config.block_subprocess:
        try:
            import subprocess as _sp  # type: ignore[import]

            _sp.Popen = _blocked("subprocess:Popen")  # type: ignore[assignment]
            _sp.run = _blocked("subprocess:run")  # type: ignore[assignment]
            _sp.call = _blocked("subprocess:call")  # type: ignore[assignment]
            _sp.check_call = _blocked("subprocess:check_call")  # type: ignore[assignment]
            _sp.check_output = _blocked("subprocess:check_output")  # type: ignore[assignment]
        except ImportError:
            pass
        # os-level escalation paths
        for attr in (
            "system",
            "popen",
            "execv",
            "execve",
            "execvp",
            "execvpe",
            "fork",
            "forkpty",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
        ):
            if hasattr(os, attr):
                setattr(os, attr, _blocked(f"subprocess:os.{attr}"))

    if config.block_env:
        # Replace environ with an empty mapping. We use the same
        # ``os._Environ`` class so consumers expecting it still work.
        try:
            os.environ.clear()
        except Exception:  # pragma: no cover - environ is dict-like
            pass
        os.getenv = lambda key, default=None: default  # type: ignore[assignment]
        os.putenv = _blocked("env:os.putenv")  # type: ignore[assignment]
        os.unsetenv = _blocked("env:os.unsetenv")  # type: ignore[assignment]

    if config.block_writes_outside_scratch:
        scratch_path = Path(scratch_dir).resolve()
        import builtins

        _real_open = builtins.open

        def _guarded_open(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
            # Read modes are unrestricted (the candidate is allowed to
            # read schema/config files). Write/append/update modes must
            # land inside the scratch dir.
            mode_str = str(mode)
            if any(ch in mode_str for ch in ("w", "a", "x", "+")):
                try:
                    target = Path(os.fspath(file)).resolve()
                except Exception as exc:  # noqa: BLE001
                    raise SandboxBlocked(
                        f"hop_sandbox_blocked:write_unresolvable:{exc}"
                    ) from exc
                try:
                    target.relative_to(scratch_path)
                except ValueError as exc:
                    raise SandboxBlocked(
                        f"hop_sandbox_blocked:write_outside_scratch:{target}"
                    ) from exc
            return _real_open(file, mode, *args, **kwargs)

        builtins.open = _guarded_open  # type: ignore[assignment]


def _apply_resource_limits(config: SandboxConfig) -> None:
    """Apply OS-level resource limits inside the worker.

    No-op on platforms without ``resource`` (Windows). The wall-clock
    timeout in the parent process remains the backstop on those
    platforms.
    """
    if not _HAS_RESOURCE:
        return
    try:
        resource.setrlimit(  # type: ignore[union-attr]
            resource.RLIMIT_AS,  # type: ignore[union-attr]
            (config.memory_limit_bytes, config.memory_limit_bytes),
        )
    except (ValueError, OSError):  # pragma: no cover - platform variance
        pass
    try:
        resource.setrlimit(  # type: ignore[union-attr]
            resource.RLIMIT_CPU,  # type: ignore[union-attr]
            (config.cpu_seconds, config.cpu_seconds),
        )
    except (ValueError, OSError):  # pragma: no cover - platform variance
        pass


# ---------------------------------------------------------------------------
# worker entrypoint
# ---------------------------------------------------------------------------


def _serialize_exception(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "module": type(exc).__module__,
        "message": str(exc),
    }


def _worker_main(
    *,
    runner_module: str,
    runner_attr: str,
    case_input: Mapping[str, Any],
    scratch_dir: str,
    config: SandboxConfig,
    pipe: "mp.connection.Connection",
) -> None:
    """Child entrypoint. Sends ``("ok", payload)`` or ``("err", info)``."""
    try:
        _apply_resource_limits(config)
        _install_blockers(scratch_dir, config)
        try:
            module = importlib.import_module(runner_module)
        except Exception as exc:  # noqa: BLE001
            pipe.send(("err", "import_error", _serialize_exception(exc)))
            return
        runner = getattr(module, runner_attr, None)
        if runner is None or not callable(runner):
            pipe.send(
                (
                    "err",
                    "missing_runner",
                    {
                        "type": "AttributeError",
                        "module": runner_module,
                        "message": f"runner_attr_missing:{runner_attr}",
                    },
                )
            )
            return
        try:
            output = runner(case_input)
        except SandboxBlocked as exc:
            pipe.send(("err", "blocked", _serialize_exception(exc)))
            return
        except MemoryError as exc:
            pipe.send(("err", "resource_exceeded", _serialize_exception(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            pipe.send(("err", "runtime_error", _serialize_exception(exc)))
            return
        try:
            payload = pickle.dumps(output)
        except Exception as exc:  # noqa: BLE001
            pipe.send(("err", "unpicklable_output", _serialize_exception(exc)))
            return
        pipe.send(("ok", payload))
    finally:
        try:
            pipe.close()
        except Exception:  # pragma: no cover - close best-effort
            pass


def _resolve_runner_target(
    runner: Callable[[Mapping[str, Any]], Any] | tuple[str, str],
) -> tuple[str, str]:
    """Return ``(module_name, attr_name)`` for a runner reference.

    The sandbox can only hand picklable references to a forked worker.
    Bound methods, lambdas, and inner functions cannot cross the
    process boundary, so callers must either pass an
    importable function or a ``(module, attr)`` tuple.
    """
    if isinstance(runner, tuple):
        if len(runner) != 2 or not all(isinstance(p, str) for p in runner):
            raise SandboxConfigError("hop_sandbox_invalid_runner_tuple")
        return runner
    module_name = getattr(runner, "__module__", None)
    qualname = getattr(runner, "__qualname__", None)
    name = getattr(runner, "__name__", None)
    if not module_name or not name:
        raise SandboxConfigError("hop_sandbox_runner_not_importable")
    if qualname and "." in qualname and "<locals>" in qualname:
        raise SandboxConfigError(
            f"hop_sandbox_runner_not_top_level:{module_name}:{qualname}"
        )
    return module_name, name


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def _start_method() -> str:
    # ``fork`` is faster and inherits less state than ``spawn``. We prefer
    # fork on POSIX. On macOS where fork-with-threads is unsafe and on
    # Windows where fork is unavailable we fall back to spawn.
    if sys.platform.startswith("linux"):
        return "fork"
    return "spawn"


def run_in_sandbox(
    *,
    runner: Callable[[Mapping[str, Any]], Any] | tuple[str, str],
    case_input: Mapping[str, Any],
    config: SandboxConfig | None = None,
) -> Any:
    """Execute ``runner(case_input)`` inside an isolated worker.

    Parameters
    ----------
    runner
        Either a top-level importable function (must be addressable as
        ``module.attr``) or an explicit ``(module_name, attr_name)``
        tuple. Lambdas / inner functions cannot cross the process
        boundary and will raise :class:`SandboxConfigError`.
    case_input
        The eval-case input mapping. Must be picklable.
    config
        Sandbox configuration. Defaults to a conservative profile.

    Returns
    -------
    Any
        The runner's output value (already validated by the caller's
        downstream schema check).

    Raises
    ------
    SandboxBlocked
        Forbidden action was attempted.
    SandboxTimeout
        Wall-clock timeout exceeded.
    SandboxResourceExceeded
        Memory or CPU exhausted.
    SandboxRuntimeError
        Candidate raised an unhandled exception.
    SandboxConfigError
        Invalid runner reference or configuration.
    """
    cfg = config or SandboxConfig()
    module_name, attr_name = _resolve_runner_target(runner)

    if not isinstance(case_input, Mapping):
        raise SandboxConfigError("hop_sandbox_invalid_case_input")

    # Set up scratch dir. If the caller didn't provide one, manage a
    # per-call dir so the worker has a guaranteed write target.
    owns_scratch = cfg.scratch_dir is None
    if owns_scratch:
        scratch_dir = tempfile.mkdtemp(prefix="hop_sandbox_")
    else:
        scratch_dir = cfg.scratch_dir  # type: ignore[assignment]
        os.makedirs(scratch_dir, exist_ok=True)

    ctx = mp.get_context(_start_method())
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(
        target=_worker_main,
        kwargs={
            "runner_module": module_name,
            "runner_attr": attr_name,
            "case_input": dict(case_input),
            "scratch_dir": scratch_dir,
            "config": cfg,
            "pipe": child_conn,
        },
    )
    proc.start()
    child_conn.close()  # parent only reads

    try:
        if not parent_conn.poll(cfg.timeout_seconds):
            proc.kill()
            proc.join(timeout=1.0)
            raise SandboxTimeout(
                f"hop_sandbox_timeout:{cfg.timeout_seconds}s:{module_name}.{attr_name}"
            )
        try:
            message = parent_conn.recv()
        except EOFError as exc:
            proc.join(timeout=1.0)
            exit_code = proc.exitcode
            if exit_code is not None and exit_code < 0:
                raise SandboxResourceExceeded(
                    f"hop_sandbox_resource_exceeded:signal={-exit_code}"
                ) from exc
            raise SandboxRuntimeError(
                f"hop_sandbox_worker_died:exit={exit_code}"
            ) from exc
        proc.join(timeout=1.0)
    finally:
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)
        if owns_scratch:
            _safe_rmtree(scratch_dir)

    if not isinstance(message, tuple) or not message:
        raise SandboxRuntimeError(f"hop_sandbox_worker_protocol:{message!r}")

    tag = message[0]
    if tag == "ok":
        try:
            return pickle.loads(message[1])
        except Exception as exc:  # noqa: BLE001
            raise SandboxRuntimeError(
                f"hop_sandbox_unpickle_failed:{exc}"
            ) from exc

    if tag == "err":
        if len(message) != 3:
            raise SandboxRuntimeError(f"hop_sandbox_worker_protocol:{message!r}")
        _, kind, info = message
        detail = (
            f"{info.get('type', 'Exception')}:{info.get('message', '')}"
            if isinstance(info, Mapping)
            else str(info)
        )
        if kind == "blocked":
            raise SandboxBlocked(detail)
        if kind == "resource_exceeded":
            raise SandboxResourceExceeded(detail)
        if kind == "runtime_error":
            raise SandboxRuntimeError(detail)
        if kind == "import_error":
            raise SandboxRuntimeError(f"import_error:{detail}")
        if kind == "missing_runner":
            raise SandboxConfigError(f"missing_runner:{detail}")
        if kind == "unpicklable_output":
            raise SandboxRuntimeError(f"unpicklable_output:{detail}")
        raise SandboxRuntimeError(f"unknown:{kind}:{detail}")

    raise SandboxRuntimeError(f"hop_sandbox_worker_protocol:{message!r}")


def _safe_rmtree(path: str) -> None:
    """Best-effort removal of the per-call scratch dir."""
    import shutil

    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:  # pragma: no cover - cleanup is best-effort
        pass


def make_sandboxed_runner(
    *,
    runner: Callable[[Mapping[str, Any]], Any] | tuple[str, str],
    config: SandboxConfig | None = None,
) -> Callable[[Mapping[str, Any]], Any]:
    """Wrap ``runner`` so every call routes through the sandbox.

    The returned callable matches the evaluator's runner contract::

        out = wrapped(case_input)

    Sandbox failures propagate as exceptions; the evaluator already
    catches generic ``Exception`` per-case and emits a
    ``hop_harness_failure_hypothesis``, so blocked/timed-out/oom
    candidates fail closed via the existing path.
    """
    cfg = config or SandboxConfig()
    target = _resolve_runner_target(runner)

    def _call(case_input: Mapping[str, Any]) -> Any:
        return run_in_sandbox(runner=target, case_input=case_input, config=cfg)

    _call.__sandbox_config__ = cfg  # type: ignore[attr-defined]
    _call.__sandbox_target__ = target  # type: ignore[attr-defined]
    return _call


__all__ = [
    "DEFAULT_CPU_SECONDS",
    "DEFAULT_MEMORY_LIMIT_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "SandboxBlocked",
    "SandboxConfig",
    "SandboxConfigError",
    "SandboxError",
    "SandboxResourceExceeded",
    "SandboxRuntimeError",
    "SandboxTimeout",
    "make_sandboxed_runner",
    "run_in_sandbox",
]
