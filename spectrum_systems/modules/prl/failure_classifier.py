"""PRL-01: Deterministic failure classifier.

No LLM. Pure lookup table. Fail-closed: unrecognized failure_class → unknown_failure.
Canonical system ownership per docs/architecture/system_registry.md.
"""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prl.failure_parser import ParsedFailure

KNOWN_FAILURE_CLASSES: frozenset[str] = frozenset({
    "pytest_selection_missing",
    "authority_shape_violation",
    "system_registry_mismatch",
    "contract_schema_violation",
    "missing_required_artifact",
    "trace_missing",
    "replay_mismatch",
    "policy_mismatch",
    "timeout",
    "rate_limited",
    "unknown_failure",
})

# Maps failure_class → CDE-compatible control signal recommendation.
# block > freeze > warn > allow (aggregation order).
CONTROL_SIGNAL: dict[str, str] = {
    "pytest_selection_missing": "warn",
    "authority_shape_violation": "block",
    "system_registry_mismatch": "block",
    "contract_schema_violation": "block",
    "missing_required_artifact": "block",
    "trace_missing": "block",
    "replay_mismatch": "freeze",
    "policy_mismatch": "block",
    "timeout": "freeze",
    "rate_limited": "freeze",
    "unknown_failure": "freeze",
}

# Canonical owning system per system_registry.md.
OWNING_SYSTEM: dict[str, str] = {
    "pytest_selection_missing": "PRL",
    "authority_shape_violation": "AEX",
    "system_registry_mismatch": "MAP",
    "contract_schema_violation": "EVL",
    "missing_required_artifact": "LIN",
    "trace_missing": "OBS",
    "replay_mismatch": "REP",
    "policy_mismatch": "TPA",
    "timeout": "PQX",
    "rate_limited": "PQX",
    "unknown_failure": "FRE",
}

# Remediation hints indexed by failure_class.
REMEDIATION_HINTS: dict[str, str] = {
    "pytest_selection_missing": (
        "Run: python -m pytest tests/ -q --collect-only to diagnose collection"
    ),
    "authority_shape_violation": (
        "Run: python scripts/run_authority_shape_preflight.py --suggest-only"
    ),
    "system_registry_mismatch": (
        "Run: python scripts/validate_system_registry.py"
    ),
    "contract_schema_violation": (
        "Run: python scripts/run_contract_preflight.py"
    ),
    "missing_required_artifact": (
        "Check artifact lineage via: python scripts/build_system_registry_artifact.py"
    ),
    "trace_missing": (
        "Import build_artifact_envelope from spectrum_systems.utils.artifact_envelope"
    ),
    "replay_mismatch": (
        "Run replay with fixed seed and compare output hashes"
    ),
    "policy_mismatch": (
        "Check contracts/governance/policy-registry-manifest.json for current policy"
    ),
    "timeout": (
        "Check PQX timeout settings and consider splitting the operation into smaller slices"
    ),
    "rate_limited": (
        "Implement retry with exponential backoff: 2s, 4s, 8s, 16s"
    ),
    "unknown_failure": (
        "Inspect raw_log_excerpt in capture record; route to FRE for structured diagnosis"
    ),
}


@dataclass(frozen=True)
class Classification:
    failure_class: str
    control_signal: str
    owning_system: str
    remediation_hint: str
    is_known: bool


def classify(parsed: ParsedFailure) -> Classification:
    """Classify a parsed failure deterministically. Unknown classes → unknown_failure."""
    fc = parsed.failure_class if parsed.failure_class in KNOWN_FAILURE_CLASSES else "unknown_failure"
    return Classification(
        failure_class=fc,
        control_signal=CONTROL_SIGNAL[fc],
        owning_system=OWNING_SYSTEM[fc],
        remediation_hint=REMEDIATION_HINTS[fc],
        is_known=(fc != "unknown_failure"),
    )


def aggregate_control_signal(signals: list[str]) -> str:
    """Aggregate multiple signals. Precedence: block > freeze > warn > allow."""
    if not signals:
        return "allow"
    if "block" in signals:
        return "block"
    if "freeze" in signals:
        return "freeze"
    if "warn" in signals:
        return "warn"
    return "allow"
