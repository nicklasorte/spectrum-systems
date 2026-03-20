"""Contract Runtime Dependency Enforcement (BN.6.1).

Owns the single source of truth for contract-validation runtime availability.
All control-plane entry points must call :func:`ensure_contract_runtime_available`
before running any schema-enforcement logic.

Fail-closed behaviour
---------------------
If ``jsonschema`` is not importable the system **must not** silently proceed.
Every entry point that enforces governed schemas is required to call
:func:`ensure_contract_runtime_available` early and handle the resulting
``ContractRuntimeError`` by terminating execution without emitting any artifact
that implies schema validation succeeded.

Exit code semantics
-------------------
CLIs that catch ``ContractRuntimeError`` should exit with code **3**
(execution/runtime failure).  This is distinct from:
  - exit 2 — governance halt (blocked by policy/gating)
  - exit 1 — continue with warning
  - exit 0 — continue

Rationale
---------
BN.6 introduced executable control behaviour, but test collection failed
because ``jsonschema`` was absent in the environment. That failure mode
undermines the safety guarantees of every governed artifact contract in the
control plane.  BN.6.1 makes contract validation a hard, explicitly-checked
runtime requirement so the system fails closed, not silently.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAILURE_REASON: str = "contract_runtime_unavailable"
# Reserved for future minimum-version enforcement.  Set to a PEP 440 version
# string (e.g. "4.0.0") to activate; None disables version checking.
_MIN_JSONSCHEMA_VERSION: Optional[str] = None  # enforce if repo pins a minimum


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ContractRuntimeError(RuntimeError):
    """Raised when the contract-validation runtime is unavailable or misconfigured.

    Attributes
    ----------
    failure_reason:
        Machine-readable reason code (always ``"contract_runtime_unavailable"``).
    message:
        Human-readable explanation.
    """

    failure_reason: str = FAILURE_REASON

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def as_payload(self) -> Dict[str, Any]:
        """Return a machine-readable error payload."""
        return {
            "failure_reason": self.failure_reason,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_contract_runtime_status() -> Dict[str, Any]:
    """Return a structured status dict describing contract-runtime availability.

    Returns
    -------
    dict with keys:
        ``available``     – bool; True when jsonschema can be imported
        ``package``       – str; "jsonschema"
        ``version``       – str or None; installed version if available
        ``failure_reason``– str or None; ``FAILURE_REASON`` when unavailable
        ``error``         – str or None; import error text when unavailable
    """
    try:
        import importlib.metadata as _meta
        import jsonschema  # noqa: F401
        try:
            version: Optional[str] = _meta.version("jsonschema")
        except Exception:  # noqa: BLE001
            version = getattr(sys.modules.get("jsonschema"), "__version__", None)
        return {
            "available": True,
            "package": "jsonschema",
            "version": version,
            "failure_reason": None,
            "error": None,
        }
    except ImportError as exc:
        return {
            "available": False,
            "package": "jsonschema",
            "version": None,
            "failure_reason": FAILURE_REASON,
            "error": str(exc),
        }


def format_contract_runtime_error(status: Dict[str, Any]) -> str:
    """Format a deterministic human-readable error string from a status dict.

    Always produces the same output for the same *status*, making the error
    message deterministic and testable.
    """
    if status.get("available"):
        return f"contract runtime available (jsonschema {status.get('version', 'unknown')})"
    base = (
        "Contract enforcement is unavailable: jsonschema is not installed or cannot be imported."
    )
    if status.get("error"):
        base = f"{base} Import error: {status['error']}"
    base = f"{base} Install it with: pip install jsonschema"
    return base


def ensure_contract_runtime_available() -> Dict[str, Any]:
    """Assert that the contract-validation runtime is available.

    Returns the status dict (``available=True``) when the runtime is present.

    Raises
    ------
    ContractRuntimeError
        If ``jsonschema`` cannot be imported.  The error message is
        deterministic and machine-readable via :meth:`ContractRuntimeError.as_payload`.
    """
    status = get_contract_runtime_status()
    if not status["available"]:
        raise ContractRuntimeError(format_contract_runtime_error(status))
    return status
