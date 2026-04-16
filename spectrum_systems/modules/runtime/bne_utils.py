from __future__ import annotations

from typing import Any, Dict

from spectrum_systems.contracts import validate_artifact


class BNEBlockError(RuntimeError):
    """Fail-closed gate error for BNE-00 control surfaces."""


def ensure_contract(instance: Dict[str, Any], schema_name: str) -> Dict[str, Any]:
    validate_artifact(instance, schema_name)
    return instance


def block_if(condition: bool, message: str) -> None:
    if condition:
        raise BNEBlockError(message)
