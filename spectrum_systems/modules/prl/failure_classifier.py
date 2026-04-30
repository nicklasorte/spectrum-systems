"""PRL-01: Deterministic failure classifier.

No LLM. Pure lookup table. Fail-closed: unrecognized failure_class → unknown_failure.
Canonical system ownership per docs/architecture/system_registry.md.

Gate signal vocabulary uses neutral gate terms (failed_gate, gate_hold, gate_warn,
passed_gate) so PRL emits evidence signals rather than authority-bearing terms.
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

# Gate signal vocabulary: neutral evidence terms fed to CDE as input signals.
# CDE retains full authority over the resulting action.
# failed_gate > gate_hold > gate_warn > passed_gate (aggregation order)
GATE_SIGNAL: dict[str, str] = {
    "pytest_selection_missing": "gate_warn",
    "authority_shape_violation": "failed_gate",
    "system_registry_mismatch": "failed_gate",
    "contract_schema_violation": "failed_gate",
    "missing_required_artifact": "failed_gate",
    "trace_missing": "failed_gate",
    "replay_mismatch": "gate_hold",
    "policy_mismatch": "failed_gate",
    "timeout": "gate_hold",
    "rate_limited": "gate_hold",
    "unknown_failure": "gate_hold",
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
    gate_signal: str
    owning_system: str
    remediation_hint: str
    is_known: bool


def classify(parsed: ParsedFailure) -> Classification:
    """Classify a parsed failure deterministically. Unknown classes → unknown_failure."""
    fc = parsed.failure_class if parsed.failure_class in KNOWN_FAILURE_CLASSES else "unknown_failure"
    return Classification(
        failure_class=fc,
        gate_signal=GATE_SIGNAL[fc],
        owning_system=OWNING_SYSTEM[fc],
        remediation_hint=REMEDIATION_HINTS[fc],
        is_known=(fc != "unknown_failure"),
    )


def aggregate_gate_signal(signals: list[str]) -> str:
    """Aggregate multiple gate signals. Precedence: failed_gate > gate_hold > gate_warn > passed_gate."""
    if not signals:
        return "passed_gate"
    if "failed_gate" in signals:
        return "failed_gate"
    if "gate_hold" in signals:
        return "gate_hold"
    if "gate_warn" in signals:
        return "gate_warn"
    return "passed_gate"
