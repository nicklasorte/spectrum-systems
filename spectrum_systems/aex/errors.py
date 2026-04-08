"""AEX admission errors and canonical reason codes."""

from __future__ import annotations


class AEXAdmissionError(ValueError):
    """Raised when admission fails and execution must fail closed."""


MISSING_REQUIRED_FIELD = "missing_required_field"
INVALID_REQUEST_SHAPE = "invalid_request_shape"
UNKNOWN_EXECUTION_TYPE = "unknown_execution_type"
REPO_MUTATION_WITHOUT_ADMISSION = "repo_mutation_without_admission"
DIRECT_TLC_REPO_WRITE_FORBIDDEN = "direct_tlc_repo_write_forbidden"
DIRECT_PQX_REPO_WRITE_FORBIDDEN = "direct_pqx_repo_write_forbidden"
