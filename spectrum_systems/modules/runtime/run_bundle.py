"""Run Bundle Contract + Manifest Hardening (Prompt BD).

Validates a run-bundle manifest against the governed bundle contract BEFORE
runtime compatibility (BC) validation is attempted.  Every call produces a
deterministic decision artifact.

Hardening rules
---------------
output_contract
    The bundle must declare at least one results_summary_json, one
    provenance_json, one log_file, and at least one paper_relevant output.
paper_output_awareness
    At least one expected_output must have paper_relevant=True.
input_discipline
    All inputs declared with required=True must be explicitly listed.
provenance_minimums
    source_case_ids, manifest_author, creation_context, and at least one of
    rng_seed / rng_state_ref must be present and non-empty.
idempotency_declaration
    execution_policy.idempotency_mode must be declared and non-empty.

Failure types
-------------
manifest_invalid
    The manifest is missing required top-level fields or fails JSON Schema
    validation.
missing_required_input
    A required input has no explicit path declaration, or input validation
    on disk fails.
output_contract_invalid
    The expected_outputs array does not satisfy minimum output-type or
    paper_relevant requirements.
provenance_incomplete
    The provenance block is missing required replay fields.
idempotency_undefined
    execution_policy.idempotency_mode is absent or empty.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_OUTPUT_TYPES: List[str] = [
    "results_summary_json",
    "provenance_json",
    "log_file",
]

FAILURE_TYPE_VALUES = frozenset(
    {
        "manifest_invalid",
        "missing_required_input",
        "output_contract_invalid",
        "provenance_incomplete",
        "idempotency_undefined",
    }
)

_FAILURE_TYPE_PRIORITY: Dict[str, int] = {
    "manifest_invalid": 0,
    "missing_required_input": 1,
    "output_contract_invalid": 2,
    "provenance_incomplete": 3,
    "idempotency_undefined": 4,
}

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "run_bundle_manifest.schema.json"


# ---------------------------------------------------------------------------
# Public data class
# ---------------------------------------------------------------------------


class RunBundleManifest:
    """Thin wrapper around a parsed run-bundle manifest dict.

    Attributes
    ----------
    raw : dict
        The original parsed manifest data.
    """

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.raw = raw

    # Convenience accessors ------------------------------------------------

    @property
    def run_id(self) -> str:
        return str(self.raw.get("run_id", "unknown"))

    @property
    def bundle_version(self) -> Optional[str]:
        return self.raw.get("bundle_version")

    @property
    def inputs(self) -> List[Dict[str, Any]]:
        return self.raw.get("inputs") or []

    @property
    def expected_outputs(self) -> List[Dict[str, Any]]:
        return self.raw.get("expected_outputs") or []

    @property
    def provenance(self) -> Dict[str, Any]:
        return self.raw.get("provenance") or {}

    @property
    def execution_policy(self) -> Dict[str, Any]:
        return self.raw.get("execution_policy") or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_id(run_id: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{run_id}:{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"bdd_{digest}"


def _load_schema() -> Dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Loader + normaliser
# ---------------------------------------------------------------------------


def load_run_bundle_manifest(path: Path) -> RunBundleManifest:
    """Load a JSON manifest from *path* and return a :class:`RunBundleManifest`.

    Raises
    ------
    OSError
        When the file cannot be opened.
    json.JSONDecodeError
        When the file is not valid JSON.
    """
    raw: Dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return RunBundleManifest(raw)


def normalize_run_bundle_manifest(manifest: RunBundleManifest) -> RunBundleManifest:
    """Return a *new* :class:`RunBundleManifest` with stable-format fields.

    Normalisation only adjusts formatting (e.g. stripping whitespace from
    string fields).  It does NOT hide or correct semantic errors.
    """
    import copy

    raw = copy.deepcopy(manifest.raw)

    # Strip leading/trailing whitespace from top-level string fields.
    for key, value in raw.items():
        if isinstance(value, str):
            raw[key] = value.strip()

    return RunBundleManifest(raw)


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------


def validate_run_bundle_manifest(manifest: RunBundleManifest) -> List[str]:
    """Validate *manifest* against the JSON Schema.

    Returns a list of error strings; an empty list means the manifest
    conforms to the schema.
    """
    errors: List[str] = []
    try:
        schema = _load_schema()
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"manifest_invalid: cannot load bundle schema: {exc}")
        return errors

    validator = Draft202012Validator(schema)
    for ve in sorted(validator.iter_errors(manifest.raw), key=lambda e: list(e.path)):
        field_path = ".".join(str(p) for p in ve.path) or "(root)"
        errors.append(f"manifest_invalid: {field_path}: {ve.message}")

    return errors


def validate_expected_outputs(manifest: RunBundleManifest) -> List[str]:
    """Validate the expected_outputs array against hardening rules.

    Rules
    -----
    1. At least one output of each type in REQUIRED_OUTPUT_TYPES must be
       present.
    2. At least one output must have paper_relevant=True.
    """
    errors: List[str] = []
    outputs = manifest.expected_outputs

    present_types = {o.get("type") for o in outputs}

    for required_type in REQUIRED_OUTPUT_TYPES:
        if required_type not in present_types:
            errors.append(
                f"output_contract_invalid: missing required output type '{required_type}'"
            )

    has_paper_relevant = any(bool(o.get("paper_relevant")) for o in outputs)
    if not has_paper_relevant:
        errors.append(
            "output_contract_invalid: no expected_output is marked paper_relevant=true"
        )

    return errors


def validate_input_paths(
    manifest: RunBundleManifest,
    bundle_root: Optional[Path] = None,
) -> List[str]:
    """Validate that all required inputs are explicitly declared.

    When *bundle_root* is provided, also checks that each required input
    file actually exists on disk.
    """
    errors: List[str] = []
    for inp in manifest.inputs:
        if not inp.get("required"):
            continue
        path_str = inp.get("path")
        if not path_str:
            errors.append(
                "missing_required_input: a required input has no 'path' declared"
            )
            continue
        if bundle_root is not None:
            full_path = Path(bundle_root) / path_str if not Path(path_str).is_absolute() else Path(path_str)
            if not full_path.exists() or not full_path.is_file():
                errors.append(
                    f"missing_required_input: required input not found on disk: {path_str}"
                )
    return errors


def validate_output_contract(manifest: RunBundleManifest) -> List[str]:
    """Alias for :func:`validate_expected_outputs` for API completeness."""
    return validate_expected_outputs(manifest)


def validate_provenance_fields(manifest: RunBundleManifest) -> List[str]:
    """Validate that the provenance block meets minimum replay requirements.

    Required fields:
    - source_case_ids (non-empty list)
    - manifest_author (non-empty string)
    - creation_context (non-empty string)
    - at least one of rng_seed or rng_state_ref
    """
    errors: List[str] = []
    prov = manifest.provenance

    case_ids = prov.get("source_case_ids")
    if not case_ids or not isinstance(case_ids, list) or len(case_ids) == 0:
        errors.append(
            "provenance_incomplete: provenance.source_case_ids must be a non-empty list"
        )

    if not prov.get("manifest_author"):
        errors.append(
            "provenance_incomplete: provenance.manifest_author is required"
        )

    if not prov.get("creation_context"):
        errors.append(
            "provenance_incomplete: provenance.creation_context is required"
        )

    has_rng = prov.get("rng_seed") is not None or bool(prov.get("rng_state_ref"))
    if not has_rng:
        errors.append(
            "provenance_incomplete: provenance must declare rng_seed or rng_state_ref for replay"
        )

    return errors


def _validate_idempotency(manifest: RunBundleManifest) -> List[str]:
    errors: List[str] = []
    policy = manifest.execution_policy
    mode = policy.get("idempotency_mode")
    if not mode:
        errors.append(
            "idempotency_undefined: execution_policy.idempotency_mode must be declared"
        )
    return errors


# ---------------------------------------------------------------------------
# Bundle summary
# ---------------------------------------------------------------------------


def derive_bundle_summary(manifest: RunBundleManifest) -> Dict[str, Any]:
    """Return a concise summary dict suitable for audit artifacts."""
    outputs = manifest.expected_outputs
    paper_outputs = [o.get("path") for o in outputs if o.get("paper_relevant")]
    required_inputs = [i.get("path") for i in manifest.inputs if i.get("required")]

    return {
        "run_id": manifest.run_id,
        "bundle_version": manifest.bundle_version,
        "matlab_release": manifest.raw.get("matlab_release"),
        "runtime_version_required": manifest.raw.get("runtime_version_required"),
        "platform": manifest.raw.get("platform"),
        "worker_entrypoint": manifest.raw.get("worker_entrypoint"),
        "input_count": len(manifest.inputs),
        "required_input_count": len(required_inputs),
        "output_count": len(outputs),
        "paper_relevant_outputs": paper_outputs,
        "idempotency_mode": manifest.execution_policy.get("idempotency_mode"),
        "provenance_author": manifest.provenance.get("manifest_author"),
    }


# ---------------------------------------------------------------------------
# Failure type classifier
# ---------------------------------------------------------------------------


def classify_bundle_failure(triggering_conditions: List[str]) -> Optional[str]:
    """Return the most severe failure type in *triggering_conditions*."""
    found: Optional[str] = None
    found_priority = 999
    for condition in triggering_conditions:
        for failure_type, priority in _FAILURE_TYPE_PRIORITY.items():
            if condition.startswith(failure_type):
                if priority < found_priority:
                    found = failure_type
                    found_priority = priority
    return found


# ---------------------------------------------------------------------------
# Required actions mapping
# ---------------------------------------------------------------------------


def _build_required_actions(failure_type: Optional[str]) -> List[str]:
    mapping: Dict[str, List[str]] = {
        None: [],
        "manifest_invalid": [
            "correct_manifest_fields_to_satisfy_schema",
        ],
        "missing_required_input": [
            "add_all_required_inputs_to_bundle",
            "ensure_input_paths_exist_before_execution",
        ],
        "output_contract_invalid": [
            "declare_results_summary_json_in_expected_outputs",
            "declare_provenance_json_in_expected_outputs",
            "declare_log_file_in_expected_outputs",
            "mark_at_least_one_output_as_paper_relevant",
        ],
        "provenance_incomplete": [
            "declare_source_case_ids_in_provenance",
            "declare_manifest_author_in_provenance",
            "declare_creation_context_in_provenance",
            "declare_rng_seed_or_rng_state_ref_in_provenance",
        ],
        "idempotency_undefined": [
            "set_execution_policy_idempotency_mode_to_safe_rerun_or_strict_once",
        ],
    }
    return mapping.get(failure_type, ["review_triggering_conditions"])


# ---------------------------------------------------------------------------
# Top-level validation entry point
# ---------------------------------------------------------------------------


def validate_bundle_contract(
    manifest: RunBundleManifest,
    bundle_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run all BD hardening validators against *manifest*.

    Parameters
    ----------
    manifest:
        A :class:`RunBundleManifest` instance.
    bundle_root:
        Optional directory used to resolve relative input paths for
        on-disk existence checks.

    Returns
    -------
    dict
        A complete BD validation decision artifact.
    """
    created_at = _now_iso()
    run_id = manifest.run_id

    triggering_conditions: List[str] = []

    # 1. JSON Schema validation (fast-fail on structural errors)
    schema_errors = validate_run_bundle_manifest(manifest)
    triggering_conditions.extend(schema_errors)

    # 2. Hardening rules (run regardless so all problems are surfaced)
    triggering_conditions.extend(validate_expected_outputs(manifest))
    triggering_conditions.extend(validate_input_paths(manifest, bundle_root))
    triggering_conditions.extend(validate_provenance_fields(manifest))
    triggering_conditions.extend(_validate_idempotency(manifest))

    failure_type = classify_bundle_failure(triggering_conditions)
    valid = len(triggering_conditions) == 0

    required_actions = _build_required_actions(failure_type)
    bundle_summary = derive_bundle_summary(manifest)

    notes = (
        "Bundle manifest conforms to the governed run-bundle contract. "
        "Proceed to BC runtime compatibility validation."
        if valid
        else (
            f"Bundle manifest failed BD validation with failure type '{failure_type}'. "
            "Review triggering_conditions and address all issues before re-submission."
        )
    )

    return {
        "decision_id": _decision_id(run_id, created_at),
        "run_id": run_id,
        "created_at": created_at,
        "valid": valid,
        "failure_type": failure_type,
        "triggering_conditions": triggering_conditions,
        "required_actions": required_actions,
        "bundle_summary": bundle_summary,
        "notes": notes,
    }
