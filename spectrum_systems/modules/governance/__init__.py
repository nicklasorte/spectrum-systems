"""Governance modules for deterministic promotion/certification gates."""

from .done_certification import DoneCertificationError, run_done_certification
from .certification_integrity import (
    CertificationIntegrityError,
    run_certification_integrity_validation,
)
from .control_decision_consistency import (
    ControlDecisionConsistencyError,
    run_control_decision_consistency_validation,
)
from .policy_backtest_accuracy import PolicyBacktestAccuracyError, run_policy_backtest_accuracy
from .xrun_signal_quality import XRunSignalQualityError, run_xrun_signal_quality_validation
from .eval_auto_generation_quality import (
    EvalAutoGenerationQualityError,
    run_eval_auto_generation_quality_validation,
)
from .drift_response_validation import (
    DriftResponseValidationError,
    run_drift_response_validation,
)
from .system_registry_guard import (
    SystemRegistryGuardError,
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)

__all__ = [
    "DoneCertificationError",
    "run_done_certification",
    "CertificationIntegrityError",
    "run_certification_integrity_validation",
    "ControlDecisionConsistencyError",
    "run_control_decision_consistency_validation",
    "PolicyBacktestAccuracyError",
    "run_policy_backtest_accuracy",
    "XRunSignalQualityError",
    "run_xrun_signal_quality_validation",
    "EvalAutoGenerationQualityError",
    "run_eval_auto_generation_quality_validation",
    "DriftResponseValidationError",
    "run_drift_response_validation",
    "SystemRegistryGuardError",
    "evaluate_system_registry_guard",
    "load_guard_policy",
    "parse_system_registry",
]
