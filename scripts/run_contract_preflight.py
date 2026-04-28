#!/usr/bin/env python3
"""Fail-closed preflight gate for governed contract/schema changes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema, validate_artifact  # noqa: E402
from spectrum_systems.governance.contract_impact import analyze_contract_impact  # noqa: E402
from spectrum_systems.modules.runtime.changed_path_resolution import (  # noqa: E402
    resolve_changed_paths,
)
from spectrum_systems.modules.runtime.control_surface_enforcement import (  # noqa: E402
    ControlSurfaceEnforcementError,
    run_control_surface_enforcement,
)
from spectrum_systems.modules.runtime.control_surface_gap_extractor import (  # noqa: E402
    ControlSurfaceGapExtractionError,
    extract_control_surface_gaps,
)
from spectrum_systems.modules.runtime.control_surface_gap_to_pqx import (  # noqa: E402
    ControlSurfaceGapToPQXError,
    convert_gaps_to_pqx_work_items,
)
from spectrum_systems.modules.runtime.control_surface_manifest import (  # noqa: E402
    ControlSurfaceManifestError,
    build_control_surface_manifest,
)
from spectrum_systems.modules.runtime.pqx_execution_policy import (  # noqa: E402
    PQXExecutionPolicyError,
    evaluate_pqx_execution_policy,
)
from spectrum_systems.modules.runtime.pqx_required_context_enforcement import (  # noqa: E402
    PQXRequiredContextEnforcementError,
    enforce_pqx_required_context,
)
from spectrum_systems.modules.runtime.trust_spine_evidence_cohesion import (  # noqa: E402
    TrustSpineEvidenceCohesionError,
    evaluate_trust_spine_evidence_cohesion,
)
from spectrum_systems.modules.runtime.github_pr_autofix_contract_preflight import (  # noqa: E402
    emit_preflight_block_bundle,
)
from spectrum_systems.modules.runtime.preflight_selection_diagnostic import (  # noqa: E402
    build_pytest_selection_observation,
    is_pytest_selection_observation_class,
)
from spectrum_systems.modules.runtime.preflight_failure_normalizer import (  # noqa: E402
    normalize_preflight_failure,
)
from spectrum_systems.modules.governance.system_registry_guard import (  # noqa: E402
    evaluate_system_registry_guard,
    load_guard_policy,
    parse_system_registry,
)
from spectrum_systems.modules.runtime.preflight_ref_normalization import (  # noqa: E402
    normalize_preflight_ref_context,
)
from spectrum_systems.modules.runtime.test_inventory_integrity import (  # noqa: E402
    evaluate_test_inventory_integrity,
    refresh_baseline as refresh_test_inventory_baseline,
)
from spectrum_systems.modules.runtime.pytest_selection_integrity import (  # noqa: E402
    PytestSelectionIntegrityError,
    evaluate_pytest_selection_integrity,
)

DEFAULT_REQUIRED_SMOKE_TESTS = [
    "tests/test_roadmap_eligibility.py",
    "tests/test_next_step_decision.py",
    "tests/test_next_step_decision_policy.py",
    "tests/test_cycle_runner.py",
]

MASKING_MARKERS = (
    "schema validation",
    "validationerror",
    "required property",
    "roadmap_eligibility_artifact",
    "next_step_decision_artifact",
)
_PREFLIGHT_POLICY_VERSION = "1.0.0"
_CONTROL_SURFACE_ENFORCEMENT_TARGETS = {
    "contracts/examples/control_surface_manifest.json",
    "contracts/schemas/control_surface_manifest.schema.json",
    "spectrum_systems/modules/runtime/control_surface_manifest.py",
    "scripts/build_control_surface_manifest.py",
    "tests/test_control_surface_manifest.py",
}
_CONTROL_SURFACE_MANIFEST_PATH = REPO_ROOT / "outputs" / "control_surface_manifest" / "control_surface_manifest.json"
_CONTROL_SURFACE_ENFORCEMENT_PATH = (
    REPO_ROOT / "outputs" / "control_surface_enforcement" / "control_surface_enforcement_result.json"
)
_CONTROL_SURFACE_OBEDIENCE_PATH = REPO_ROOT / "outputs" / "control_surface_obedience" / "control_surface_obedience_result.json"
_TRUST_SPINE_INVARIANT_PATH = REPO_ROOT / "outputs" / "trust_spine_invariants" / "trust_spine_invariant_result.json"
_DONE_CERTIFICATION_PATH = REPO_ROOT / "outputs" / "done_certification" / "done_certification_record.json"
_TRUST_SPINE_COHESION_TARGETS = {
    "contracts/schemas/trust_spine_evidence_cohesion_result.schema.json",
    "contracts/examples/trust_spine_evidence_cohesion_result.json",
    "spectrum_systems/modules/runtime/trust_spine_evidence_cohesion.py",
    "scripts/run_trust_spine_evidence_cohesion.py",
    "spectrum_systems/modules/governance/done_certification.py",
    "spectrum_systems/orchestration/sequence_transition_policy.py",
    "scripts/run_contract_preflight.py",
    "tests/test_trust_spine_evidence_cohesion.py",
    "tests/test_done_certification.py",
    "tests/test_sequence_transition_policy.py",
    "tests/test_contract_preflight.py",
}
_CONTROL_SURFACE_GAP_PACKET_GOVERNANCE_PATHS = {
    "spectrum_systems/modules/runtime/control_surface_gap_loader.py",
    "spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py",
    "spectrum_systems/modules/runtime/pqx_slice_runner.py",
    "scripts/pqx_runner.py",
}
_CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS = [
    "tests/test_control_surface_gap_to_pqx.py",
    "tests/test_pqx_slice_runner.py",
]
_GOVERNED_PROMPT_SURFACE_REGISTRY = REPO_ROOT / "docs" / "governance" / "governed_prompt_surfaces.json"
_SYSTEM_REGISTRY_PATH = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
_SYSTEM_REGISTRY_GUARD_POLICY_PATH = REPO_ROOT / "contracts" / "governance" / "system_registry_guard_policy.json"
_TEST_INVENTORY_BASELINE_PATH = REPO_ROOT / "docs" / "governance" / "pytest_pr_inventory_baseline.json"
_PYTEST_SELECTION_INTEGRITY_POLICY_PATH = REPO_ROOT / "docs" / "governance" / "pytest_pr_selection_integrity_policy.json"
_DEFAULT_PR_INVENTORY_TARGETS = ["tests/test_eval_dataset_registry.py"]
_GOVERNED_PR_FALLBACK_PYTEST_TARGETS = [
    "tests/test_run_github_pr_autofix_contract_preflight.py",
    "tests/test_eval_dataset_registry.py",
    "tests/test_contracts.py",
]
_CANONICAL_PREFLIGHT_OUTPUT_PREFIX = "outputs/contract_preflight/"
_CANONICAL_PYTEST_EXECUTION_REF = f"{_CANONICAL_PREFLIGHT_OUTPUT_PREFIX}pytest_execution_record.json"
_CANONICAL_PYTEST_SELECTION_REF = f"{_CANONICAL_PREFLIGHT_OUTPUT_PREFIX}pytest_selection_integrity_result.json"
_GOVERNED_CHANGED_PATH_PREFIXES = (
    "contracts/",
    "scripts/",
    "spectrum_systems/",
    ".github/workflows/",
    "docs/governance/",
)

_REQUIRED_SURFACE_TEST_OVERRIDES: dict[str, list[str]] = {
    "scripts/run_autonomous_validation_run.py": ["tests/test_run_autonomous_validation_run.py"],
    "scripts/run_ops03_adversarial_stress_testing.py": ["tests/test_run_ops03_adversarial_stress_testing.py"],
    "scripts/run_trust_spine_evidence_cohesion.py": ["tests/test_trust_spine_evidence_cohesion.py"],
    "scripts/run_enforced_execution.py": ["tests/test_execution_contracts.py", "tests/test_control_executor.py"],
    "spectrum_systems/modules/runtime/control_surface_gap_loader.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "spectrum_systems/modules/runtime/pqx_slice_runner.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    "scripts/pqx_runner.py": _CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS,
    ".github/workflows/artifact-boundary.yml": [
        "tests/test_artifact_boundary_workflow_pytest_policy_observation.py",
        "tests/test_artifact_boundary_workflow_policy_observation.py",
    ],
}
def _load_required_surface_override_map(repo_root: Path) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {path: list(targets) for path, targets in _REQUIRED_SURFACE_TEST_OVERRIDES.items()}
    override_path = repo_root / "docs" / "governance" / "preflight_required_surface_test_overrides.json"
    if not override_path.is_file():
        return merged
    try:
        payload = json.loads(override_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return merged
    if not isinstance(payload, dict):
        return merged
    for path, targets in payload.items():
        if not isinstance(path, str) or not isinstance(targets, list):
            continue
        normalized_targets = [str(item) for item in targets if isinstance(item, str) and item.strip()]
        merged[path] = sorted(set(normalized_targets))
    return merged


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


@dataclass
class ChangedPathDetectionResult:
    changed_paths: list[str]
    changed_path_detection_mode: str
    refs_attempted: list[str]
    fallback_used: bool
    warnings: list[str]


@dataclass
class EvaluationSurfaceClassification:
    path: str
    classification: str
    reason: str
    requires_evaluation: bool
    surface: str


def _run(command: list[str], cwd: Path) -> CommandResult:
    proc = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    return CommandResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed contract/schema preflight gate")
    parser.add_argument("--base-ref", default="", help="Git base ref used for diff detection")
    parser.add_argument("--head-ref", default="", help="Git head ref used for diff detection")
    parser.add_argument("--event-name", default=None, help="Optional event context override for ref normalization")
    parser.add_argument("--changed-path", action="append", default=[], help="Optional explicit changed paths")
    parser.add_argument("--output-dir", default="outputs/contract_preflight", help="Preflight output directory")
    parser.add_argument(
        "--hardening-flow",
        action="store_true",
        help="Mark run as a hardening flow so unresolved downstream seam impact is frozen instead of directly allowed.",
    )
    parser.add_argument(
        "--execution-context",
        default="unspecified",
        help=(
            "Execution context for default PQX policy classification. "
            "Use 'pqx_governed' for governed PQX runs; direct/exploration contexts are non-authoritative."
        ),
    )
    parser.add_argument(
        "--pqx-wrapper-path",
        default=None,
        help="Optional path to canonical codex_pqx_task_wrapper payload for governed PQX required-context enforcement.",
    )
    parser.add_argument(
        "--authority-evidence-ref",
        default=None,
        help="Optional authority evidence ref used for governed required-context enforcement.",
    )
    parser.add_argument(
        "--refresh-test-inventory-baseline",
        action="store_true",
        help="Refresh governed PR/default pytest inventory baseline and exit.",
    )
    return parser.parse_args()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_common_provenance(*, source_head_ref: str) -> dict[str, Any]:
    source_commit_sha = (
        str(os.environ.get("GITHUB_SHA") or "").strip()
        or source_head_ref
        or str(os.environ.get("GIT_COMMIT") or "").strip()
        or "unknown"
    )
    return {
        "source_commit_sha": source_commit_sha,
        "source_head_ref": source_head_ref or "unknown",
        "workflow_run_id": str(os.environ.get("GITHUB_RUN_ID") or "local"),
        "producer_script": "scripts/run_contract_preflight.py",
        "produced_at": _utc_now(),
    }


def _is_governed_changed_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _GOVERNED_CHANGED_PATH_PREFIXES)


def _validate_canonical_ref_path(*, ref: str, expected_suffix: str) -> bool:
    normalized = ref.replace("\\", "/").lstrip("./")
    return normalized == expected_suffix


def _resolve_wrapper_path(repo_root: Path, wrapper_path_value: str) -> Path:
    wrapper_path = Path(wrapper_path_value)
    if not wrapper_path.is_absolute():
        wrapper_path = repo_root / wrapper_path
    return wrapper_path


def _attempt_build_missing_wrapper(
    *,
    repo_root: Path,
    wrapper_path: Path,
    base_ref: str,
    head_ref: str,
) -> dict[str, Any]:
    try:
        output_arg = str(wrapper_path.relative_to(repo_root))
    except ValueError:
        output_arg = str(wrapper_path)
    command = [
        sys.executable,
        str(repo_root / "scripts" / "build_preflight_pqx_wrapper.py"),
        "--base-ref",
        base_ref,
        "--head-ref",
        head_ref,
        "--output",
        output_arg,
    ]
    result = _run(command, cwd=repo_root)
    return {
        "attempted": True,
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "built": result.returncode == 0 and wrapper_path.exists(),
    }


def _all_governed_paths(repo_root: Path) -> list[str]:
    governed: list[str] = []
    for prefix in _GOVERNED_CHANGED_PATH_PREFIXES:
        root = repo_root / prefix
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                governed.append(str(path.relative_to(repo_root)))
    return sorted(set(governed))


def _diff_name_only(repo_root: Path, base_ref: str, head_ref: str) -> tuple[list[str], str | None]:
    diff = _run(["git", "diff", "--name-only", f"{base_ref}..{head_ref}"], cwd=repo_root)
    if diff.returncode != 0:
        return [], diff.combined_output
    paths = sorted({line.strip() for line in diff.stdout.splitlines() if line.strip()})
    return paths, None


def _github_sha_pair() -> tuple[str, str, str] | None:
    event_name = (os.environ.get("GITHUB_EVENT_NAME") or "").strip()
    base_sha = (os.environ.get("GITHUB_BASE_SHA") or "").strip()
    head_sha = (os.environ.get("GITHUB_HEAD_SHA") or "").strip()
    before_sha = (os.environ.get("GITHUB_BEFORE_SHA") or "").strip()
    sha = (os.environ.get("GITHUB_SHA") or "").strip()

    if event_name == "pull_request" and base_sha and head_sha:
        return base_sha, head_sha, "github_pr_sha_pair"
    if event_name == "push" and before_sha and sha and before_sha != "0000000000000000000000000000000000000000":
        return before_sha, sha, "github_push_sha_pair"
    return None


def _local_workspace_changes(repo_root: Path) -> list[str]:
    changes = _run(["git", "status", "--porcelain"], cwd=repo_root)
    if changes.returncode != 0:
        return []
    paths = []
    for line in changes.stdout.splitlines():
        if not line:
            continue
        path = line[3:].strip()
        if path:
            paths.append(path)
    return sorted(set(paths))


def detect_changed_paths(repo_root: Path, base_ref: str, head_ref: str, explicit: list[str] | None = None) -> ChangedPathDetectionResult:
    refs_attempted: list[str] = []
    warnings: list[str] = []

    if explicit:
        return ChangedPathDetectionResult(
            changed_paths=sorted(set(explicit)),
            changed_path_detection_mode="explicit_paths",
            refs_attempted=[],
            fallback_used=False,
            warnings=[],
        )

    # B: explicit base/head refs when resolvable.
    refs_attempted.append(f"{base_ref}..{head_ref}")
    diff_paths, error = _diff_name_only(repo_root, base_ref, head_ref)
    if not error:
        return ChangedPathDetectionResult(
            changed_paths=diff_paths,
            changed_path_detection_mode="base_head_diff",
            refs_attempted=refs_attempted,
            fallback_used=False,
            warnings=[],
        )
    warnings.append(f"base/head diff unavailable: {error}")

    if head_ref != "HEAD":
        refs_attempted.append(f"{base_ref}..HEAD")
        current_head_paths, current_head_error = _diff_name_only(repo_root, base_ref, "HEAD")
        if not current_head_error:
            return ChangedPathDetectionResult(
                changed_paths=current_head_paths,
                changed_path_detection_mode="base_to_current_head_fallback",
                refs_attempted=refs_attempted,
                fallback_used=True,
                warnings=warnings + ["head ref unavailable; used current HEAD fallback"],
            )
        warnings.append(f"base..HEAD fallback unavailable: {current_head_error}")

    # C: GitHub event-aware refs (PR base/head SHA; push before/current SHA).
    sha_pair = _github_sha_pair()
    if sha_pair:
        gh_base, gh_head, mode = sha_pair
        refs_attempted.append(f"{gh_base}..{gh_head}")
        gh_paths, gh_error = _diff_name_only(repo_root, gh_base, gh_head)
        if not gh_error:
            return ChangedPathDetectionResult(
                changed_paths=gh_paths,
                changed_path_detection_mode=mode,
                refs_attempted=refs_attempted,
                fallback_used=False,
                warnings=warnings,
            )
        warnings.append(f"github event ref diff unavailable: {gh_error}")

    # D: safe local fallback paths.
    local_changes = _local_workspace_changes(repo_root)
    local_governed = [path for path in local_changes if _is_governed_changed_path(path)]
    if local_governed:
        return ChangedPathDetectionResult(
            changed_paths=sorted(set(local_governed)),
            changed_path_detection_mode="local_workspace_status",
            refs_attempted=refs_attempted,
            fallback_used=True,
            warnings=warnings + ["using git status porcelain fallback"],
        )
    if local_changes:
        warnings.append("local workspace fallback had no governed surface paths; continuing to deeper fallback")

    refs_attempted.append("working_tree_vs_HEAD")
    working_tree = _run(["git", "diff", "--name-only", "HEAD"], cwd=repo_root)
    if working_tree.returncode == 0:
        paths = sorted({line.strip() for line in working_tree.stdout.splitlines() if line.strip()})
        governed_paths = [path for path in paths if _is_governed_changed_path(path)]
        if governed_paths:
            return ChangedPathDetectionResult(
                changed_paths=sorted(set(governed_paths)),
                changed_path_detection_mode="working_tree_diff_head",
                refs_attempted=refs_attempted,
                fallback_used=True,
                warnings=warnings + ["using working tree diff fallback"],
            )
        if paths:
            warnings.append("working tree fallback had no governed surface paths; degrading to full governed scan")
    else:
        warnings.append(f"working tree fallback unavailable: {working_tree.combined_output}")

    # E: fail-closed degraded full governed scan.
    governed = _all_governed_paths(repo_root)
    if governed:
        return ChangedPathDetectionResult(
            changed_paths=governed,
            changed_path_detection_mode="degraded_full_governed_scan",
            refs_attempted=refs_attempted,
            fallback_used=True,
            warnings=warnings + ["changed-path detection degraded; running full governed surface scan"],
        )

    # Canonical resolver fallback for explicit insufficient-context metadata surface.
    resolved = resolve_changed_paths(repo_root=repo_root, base_ref=base_ref, head_ref=head_ref, explicit=explicit)
    return ChangedPathDetectionResult(
        changed_paths=resolved.changed_paths,
        changed_path_detection_mode="detection_failed_no_governed_paths",
        refs_attempted=refs_attempted,
        fallback_used=True,
        warnings=warnings + ["changed-path detection failed and no governed paths were available"],
    )




def classify_changed_contracts(changed_paths: list[str]) -> dict[str, list[str]]:
    changed_schemas = sorted(
        path for path in changed_paths if path.startswith("contracts/schemas/") and path.endswith(".schema.json")
    )
    changed_examples = sorted(path for path in changed_paths if path.startswith("contracts/examples/") and path.endswith(".json"))
    governed_defs = sorted(
        path
        for path in changed_paths
        if path.startswith("contracts/") and path.endswith(".schema.json") and not path.startswith("contracts/schemas/")
    )
    return {
        "changed_contract_paths": changed_schemas,
        "changed_example_paths": changed_examples,
        "changed_governed_definitions": governed_defs,
    }




def _is_registry_governed_prompt_surface(path: str) -> bool:
    if not _GOVERNED_PROMPT_SURFACE_REGISTRY.exists():
        return False
    try:
        from scripts.check_governance_compliance import (
            classify_governed_surface_for_path,
            load_governed_prompt_surface_registry,
        )

        surfaces = load_governed_prompt_surface_registry(_GOVERNED_PROMPT_SURFACE_REGISTRY)
        return classify_governed_surface_for_path(path, surfaces) is not None
    except Exception:
        return False

def _is_forced_evaluation_surface(path: str) -> tuple[bool, str, str]:
    if path in _CONTROL_SURFACE_GAP_PACKET_GOVERNANCE_PATHS:
        return (
            True,
            "control_surface_gap_packet_governance",
            "control-surface gap packet governance seam changed",
        )
    if path.startswith("spectrum_systems/modules/runtime/"):
        return True, "runtime_module", "runtime module changed"
    if path.startswith("spectrum_systems/orchestration/"):
        return True, "orchestration", "orchestration path changed"
    if _is_registry_governed_prompt_surface(path):
        return True, "governed_prompt_surface", "registry-governed prompt surface changed"
    if (
        path.startswith("spectrum_systems/governance/")
        or path.startswith("scripts/")
        or path.startswith("contracts/governance/")
    ):
        return True, "governance", "governance/control surface changed"
    if path.startswith(".github/workflows/") and path.endswith(".yml"):
        return True, "ci_workflow_surface", "CI workflow surface changed"
    if path.startswith("tests/") and path.endswith(".py"):
        tied_markers = (
            "contract",
            "preflight",
            "schema",
            "roadmap_eligibility",
            "next_step_decision",
            "cycle_runner",
            "workflow",
        )
        if any(marker in path for marker in tied_markers):
            return True, "contract_tied_tests", "contract-tied test changed"
    return False, "other", "path does not map to governed contract surface"


def classify_evaluation_surfaces(changed_paths: list[str], classified_contracts: dict[str, list[str]]) -> dict[str, Any]:
    contract_surface_paths = set(
        classified_contracts["changed_contract_paths"]
        + classified_contracts["changed_example_paths"]
        + classified_contracts["changed_governed_definitions"]
    )
    classifications: list[EvaluationSurfaceClassification] = []
    required_paths: list[str] = []
    no_op_paths: list[str] = []
    evaluated_surfaces: set[str] = set()

    for path in sorted(set(changed_paths)):
        if path in contract_surface_paths:
            classifications.append(
                EvaluationSurfaceClassification(
                    path=path,
                    classification="evaluated",
                    reason="contract/example change is always evaluated",
                    requires_evaluation=True,
                    surface="contract_surface",
                )
            )
            required_paths.append(path)
            evaluated_surfaces.add("contract_surface")
            continue

        requires_eval, surface, reason = _is_forced_evaluation_surface(path)
        if requires_eval:
            classifications.append(
                EvaluationSurfaceClassification(
                    path=path,
                    classification="evaluated",
                    reason=reason,
                    requires_evaluation=True,
                    surface=surface,
                )
            )
            required_paths.append(path)
            evaluated_surfaces.add(surface)
            continue

        classifications.append(
            EvaluationSurfaceClassification(
                path=path,
                classification="no_applicable_contract_surface",
                reason=reason,
                requires_evaluation=False,
                surface=surface,
            )
        )
        no_op_paths.append(path)

    mode = "no-op" if not required_paths else ("full" if len(required_paths) == len(set(changed_paths)) else "partial")
    return {
        "evaluation_mode": mode,
        "path_classifications": [item.__dict__ for item in classifications],
        "required_paths": sorted(set(required_paths)),
        "no_op_paths": sorted(set(no_op_paths)),
        "evaluated_surfaces": sorted(evaluated_surfaces),
    }


def build_impact_map(repo_root: Path, changed_contract_paths: list[str], changed_example_paths: list[str]) -> dict[str, list[str]]:
    impact = analyze_contract_impact(
        repo_root=repo_root,
        changed_contract_paths=changed_contract_paths,
        changed_example_paths=changed_example_paths,
        baseline_ref="HEAD",
    )

    impacted_tests = set(impact.get("impacted_test_paths", []))
    impacted_runtime = set(impact.get("impacted_runtime_paths", []))
    impacted_scripts = set(impact.get("impacted_script_paths", []))

    producers = sorted(path for path in impacted_runtime if "orchestration" in path or "modules/runtime" in path)
    fixtures = sorted(path for path in impacted_tests if "/fixtures/" in path or "/helpers/" in path)
    consumers = sorted(path for path in impacted_tests if path not in fixtures)

    contract_names = {
        Path(path).name.replace(".schema.json", "")
        for path in changed_contract_paths
        if path.endswith(".schema.json")
    }

    required_smoke_tests: list[str] = []
    if "roadmap_eligibility_artifact" in contract_names:
        required_smoke_tests.extend(DEFAULT_REQUIRED_SMOKE_TESTS)

    required_smoke_tests.extend(path for path in consumers if path.endswith(".py") and Path(path).name.startswith("test_"))

    return {
        "producers": producers,
        "fixtures_or_builders": fixtures,
        "consumers": consumers,
        "scripts": sorted(impacted_scripts),
        "required_smoke_tests": sorted(set(required_smoke_tests)),
        "contract_impact_artifact": impact,
    }


def resolve_test_targets(repo_root: Path, impacted_paths: list[str]) -> list[str]:
    tests_root = repo_root / "tests"
    test_files = sorted(path for path in tests_root.rglob("test_*.py") if path.is_file()) if tests_root.is_dir() else []
    targets: set[str] = set()
    for rel_path in impacted_paths:
        candidate = Path(rel_path)
        if candidate.name.startswith("test_") and candidate.suffix == ".py":
            targets.add(rel_path)
            continue

        if rel_path.startswith("tests/helpers/") or rel_path.startswith("tests/fixtures/"):
            stem = candidate.stem
            if not stem:
                continue
            stem_needle = stem.lower()
            for test_file in test_files:
                rel_test = test_file.relative_to(repo_root).as_posix()
                try:
                    text = test_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if stem_needle in text.lower():
                    targets.add(rel_test)

    return sorted(targets)


def resolve_required_surface_tests(repo_root: Path, changed_paths: list[str]) -> dict[str, list[str]]:
    tests_root = repo_root / "tests"
    test_files = sorted(path for path in tests_root.rglob("test_*.py") if path.is_file()) if tests_root.is_dir() else []
    path_to_targets: dict[str, list[str]] = {}
    override_map = _load_required_surface_override_map(repo_root)
    for rel_path in changed_paths:
        targets: set[str] = set()
        for override in override_map.get(rel_path, []):
            targets.add(override)
        candidate = Path(rel_path)
        if rel_path.startswith("tests/test_") and rel_path.endswith(".py"):
            targets.add(rel_path)
        else:
            needles = {candidate.stem.lower(), candidate.name.lower()}
            needles = {needle for needle in needles if needle and needle not in {"test", "tests"}}
            for test_file in test_files:
                rel_test = test_file.relative_to(repo_root).as_posix()
                try:
                    text = test_file.read_text(encoding="utf-8").lower()
                except (OSError, UnicodeDecodeError):
                    continue
                if any(needle in text for needle in needles):
                    targets.add(rel_test)
        path_to_targets[rel_path] = sorted(targets)
    return path_to_targets


def validate_control_surface_gap_packet_test_expectations(
    *,
    changed_paths: list[str],
    resolved_targets_by_path: dict[str, list[str]],
) -> list[dict[str, str]]:
    expectation_failures: list[dict[str, str]] = []
    required = set(_CONTROL_SURFACE_GAP_PACKET_REQUIRED_TESTS)
    for path in changed_paths:
        if path not in _CONTROL_SURFACE_GAP_PACKET_GOVERNANCE_PATHS:
            continue
        resolved = set(resolved_targets_by_path.get(path, []))
        missing = sorted(required - resolved)
        if missing:
            expectation_failures.append(
                {
                    "path": path,
                    "reason": (
                        "control_surface_gap_packet governance path requires deterministic tests: "
                        + ", ".join(missing)
                    ),
                }
            )
    return expectation_failures


def _schema_name_from_example(path: str) -> str:
    normalized = Path(path).as_posix()
    if normalized.startswith("contracts/examples/stage_contracts/"):
        return "stage_contract"

    name = Path(path).name
    if name.endswith(".example.json"):
        return name.removesuffix(".example.json")
    return name.removesuffix(".json")


def validate_examples(changed_example_paths: list[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for rel_path in changed_example_paths:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            failures.append({"path": rel_path, "error": "example file missing"})
            continue

        payload = json.loads(full_path.read_text(encoding="utf-8"))
        schema_name = _schema_name_from_example(rel_path)
        try:
            schema = load_schema(schema_name)
        except Exception as exc:
            failures.append({"path": rel_path, "error": f"schema load failed for {schema_name}: {exc}"})
            continue

        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        try:
            validator.validate(payload)
        except Exception as exc:
            failures.append({"path": rel_path, "error": str(exc)})
    return failures


def _resolve_existing_pytest_targets(paths: list[str]) -> list[str]:
    return sorted({path for path in paths if (REPO_ROOT / path).is_file()})


def run_targeted_pytests(paths: list[str], *, execution_log: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for path in paths:
        cmd = [sys.executable, "-m", "pytest", "-q", path]
        result = _run(cmd, cwd=REPO_ROOT)
        if execution_log is not None:
            execution_log.append({"target": path, "command": " ".join(cmd), "returncode": result.returncode})
        if result.returncode != 0:
            failures.append(
                {
                    "path": path,
                    "command": " ".join(cmd),
                    "returncode": result.returncode,
                    "output": result.combined_output[-4000:],
                }
            )
    return failures


def build_pytest_execution_record(
    *,
    event_name: str,
    source_head_ref: str,
    execution_log: list[dict[str, Any]],
    selected_targets: list[str],
    fallback_targets: list[str],
    fallback_used: bool,
    targeted_selection_empty: bool,
    fallback_selection_empty: bool,
    selection_reason_codes: list[str],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for item in execution_log:
        entries.append(
            {
                "target": str(item.get("target", "")),
                "command": str(item.get("command", "")),
                "exit_code": int(item.get("returncode", 0)),
            }
        )
    effective_targets = sorted(
        {
            str(entry.get("target", "")).strip()
            for entry in entries
            if str(entry.get("target", "")).strip()
        }
    )
    aggregate_exit_code = 0
    if entries:
        aggregate_exit_code = max(int(entry.get("exit_code", 0)) for entry in entries)
    executed = len(entries) > 0
    failure_reason = None
    if not executed:
        failure_reason = "no_pytest_command_executed"
    elif aggregate_exit_code != 0:
        failure_reason = "pytest_command_failed"

    workflow_name = str(os.environ.get("GITHUB_WORKFLOW", "")).strip()
    workflow_job = str(os.environ.get("GITHUB_JOB", "")).strip()
    payload = {
        "artifact_type": "pytest_execution_record",
        "schema_version": "1.1.0",
        "event_name": event_name,
        "workflow_name": workflow_name or None,
        "workflow_job": workflow_job or None,
        "executed": executed,
        "pytest_command": " ; ".join(str(entry.get("command", "")) for entry in entries),
        "selected_targets": effective_targets,
        "configured_selected_targets": sorted(set(selected_targets)),
        "fallback_targets": sorted(set(fallback_targets)),
        "fallback_used": bool(fallback_used),
        "targeted_selection_empty": bool(targeted_selection_empty),
        "fallback_selection_empty": bool(fallback_selection_empty),
        "selection_reason_codes": sorted(set(selection_reason_codes)),
        "collection_count": None,
        "exit_code": aggregate_exit_code,
        "execution_count": len(entries),
        "execution_entries": entries,
        "timestamp": _utc_now(),
        "failure_reason": failure_reason,
    }
    payload.update(_build_common_provenance(source_head_ref=source_head_ref))
    payload["artifact_hash"] = _hash_payload(payload)
    return payload


def detect_masked_failures(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    masked: list[dict[str, Any]] = []
    for item in failures:
        output = str(item.get("output", "")).lower()
        if any(marker in output for marker in MASKING_MARKERS):
            masked.append(
                {
                    "path": item.get("path"),
                    "classification": "contract masking introduced",
                    "reason": "schema/contract failure signature detected before targeted test assertions",
                }
            )
    return masked


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Contract Preflight Report", ""]
    lines.append(f"- **status**: `{report['status']}`")
    lines.append(f"- **changed_contracts**: {len(report['changed_contracts'])}")
    lines.append(f"- **changed_examples**: {len(report['changed_examples'])}")
    detection = report.get("changed_path_detection", {})
    if detection:
        lines.append(f"- **changed_path_detection_mode**: `{detection.get('changed_path_detection_mode', 'unknown')}`")
        lines.append(f"- **fallback_used**: `{detection.get('fallback_used', False)}`")
        warnings = detection.get("warnings", [])
        lines.append(f"- **detection_warnings**: {len(warnings)}")
    lines.append("")

    lines.append("## Impacted seams")
    impact = report["impact"]
    for key in ("producers", "fixtures_or_builders", "consumers", "required_smoke_tests"):
        values = impact.get(key, [])
        lines.append(f"- **{key}** ({len(values)}):")
        for value in values:
            lines.append(f"  - `{value}`")
        if not values:
            lines.append("  - _none_")

    lines.append("")
    lines.append("## Preflight failures")
    for key in ("schema_example_failures", "producer_failures", "fixture_failures", "consumer_failures"):
        values = report.get(key, [])
        lines.append(f"- **{key}**: {len(values)}")
    control_surface_enforcement = report.get("control_surface_enforcement")
    if control_surface_enforcement:
        lines.append(f"- **control_surface_enforcement_status**: {control_surface_enforcement.get('enforcement_status')}")
        lines.append(f"- **control_surface_enforcement_blocking_reasons**: {len(control_surface_enforcement.get('blocking_reasons', []))}")
    gap_result = report.get("control_surface_gap_result")
    if gap_result:
        lines.append(f"- **control_surface_gap_status**: {gap_result.get('status')}")
        lines.append(f"- **control_surface_gap_count**: {len(gap_result.get('gaps', []))}")
        lines.append(f"- **control_surface_gap_pqx_conversion_error**: {report.get('control_surface_gap_pqx_conversion_error') or 'none'}")
    test_inventory = report.get("test_inventory_integrity")
    if isinstance(test_inventory, dict):
        lines.append(f"- **test_inventory_failure_class**: {test_inventory.get('failure_class', 'unknown')}")
        lines.append(f"- **test_inventory_selected_count**: {test_inventory.get('selected_count', 0)}")
        lines.append(f"- **test_inventory_baseline_expected_count**: {test_inventory.get('baseline_expected_count', 0)}")
    pytest_execution = report.get("pytest_execution")
    if isinstance(pytest_execution, dict):
        lines.append(f"- **pytest_execution_count**: {pytest_execution.get('pytest_execution_count', 0)}")
        lines.append(f"- **pytest_fallback_used**: {pytest_execution.get('fallback_used', False)}")
        lines.append(f"- **pytest_selected_target_count**: {len(pytest_execution.get('selected_targets', []))}")

    pytest_selection_integrity = report.get("pytest_selection_integrity")
    if isinstance(pytest_selection_integrity, dict):
        lines.append(f"- **pytest_selection_integrity_decision**: {pytest_selection_integrity.get('selection_integrity_decision', 'BLOCK')}")
        lines.append(f"- **pytest_selection_count**: {pytest_selection_integrity.get('selection_count', 0)}")
        lines.append(f"- **pytest_required_target_count**: {len(pytest_selection_integrity.get('required_test_targets', []))}")
        lines.append(f"- **pytest_selection_blocking_reasons**: {len(pytest_selection_integrity.get('blocking_reasons', []))}")

    lines.append("")
    pqx_execution_policy = report.get("pqx_execution_policy")
    if isinstance(pqx_execution_policy, dict):
        lines.append("## Default PQX execution policy")
        lines.append(f"- **classification**: `{pqx_execution_policy.get('classification', 'unknown')}`")
        lines.append(f"- **execution_context**: `{pqx_execution_policy.get('execution_context', 'unknown')}`")
        lines.append(f"- **policy_status**: `{pqx_execution_policy.get('status', 'unknown')}`")
        lines.append(f"- **authority_state**: `{pqx_execution_policy.get('authority_state', 'unknown')}`")
        lines.append(f"- **authority_resolution**: `{pqx_execution_policy.get('authority_resolution', 'unknown')}`")
        lines.append(
            f"- **authority_evidence_resolution_status**: `{pqx_execution_policy.get('authority_evidence_resolution_status', 'not_applicable')}`"
        )
        evidence_ref = pqx_execution_policy.get("authority_evidence_ref")
        lines.append(f"- **authority_evidence_ref**: `{evidence_ref}`" if evidence_ref else "- **authority_evidence_ref**: _none_")
        blocking_reasons = pqx_execution_policy.get("blocking_reasons", [])
        lines.append(f"- **blocking_reasons**: {', '.join(blocking_reasons) if blocking_reasons else 'none'}")
        lines.append("")
    required_context = report.get("pqx_required_context_enforcement")
    if isinstance(required_context, dict):
        lines.append("## PQX required context enforcement")
        lines.append(f"- **classification**: `{required_context.get('classification', 'unknown')}`")
        lines.append(f"- **execution_context**: `{required_context.get('execution_context', 'unknown')}`")
        lines.append(f"- **wrapper_present**: `{required_context.get('wrapper_present', False)}`")
        lines.append(f"- **wrapper_context_valid**: `{required_context.get('wrapper_context_valid', False)}`")
        lines.append(f"- **authority_context_valid**: `{required_context.get('authority_context_valid', False)}`")
        lines.append(f"- **enforcement_status**: `{required_context.get('status', 'unknown')}`")
        reasons = required_context.get("blocking_reasons", [])
        lines.append(f"- **blocking_reasons**: {', '.join(reasons) if reasons else 'none'}")
        lines.append("")

    if report.get("masked_failures"):
        lines.append("## Masked downstream failures")
        for item in report["masked_failures"]:
            lines.append(f"- `{item['path']}` — **contract masking introduced**")
    else:
        lines.append("## Masked downstream failures")
        lines.append("- none")

    lines.append("")
    lines.append("## Recommended repair areas")
    for area in report.get("recommended_repair_areas", []):
        lines.append(f"- {area}")
    if not report.get("recommended_repair_areas"):
        lines.append("- none")
    if report.get("bootstrap_failures"):
        lines.append("")
        lines.append("## Bootstrap failures")
        for item in report["bootstrap_failures"]:
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _should_run_control_surface_enforcement(changed_paths: list[str]) -> bool:
    return any(path in _CONTROL_SURFACE_ENFORCEMENT_TARGETS for path in changed_paths)


def evaluate_control_surface_enforcement(changed_paths: list[str]) -> dict[str, Any] | None:
    if not _should_run_control_surface_enforcement(changed_paths):
        return None

    manifest_path = REPO_ROOT / "outputs" / "control_surface_manifest" / "control_surface_manifest.json"
    if not manifest_path.is_file():
        try:
            manifest = build_control_surface_manifest()
        except ControlSurfaceManifestError as exc:
            return {
                "artifact_type": "control_surface_enforcement_result",
                "enforcement_status": "BLOCK",
                "blocking_reasons": ["CONTROL_SURFACE_ENFORCEMENT_INPUT_INVALID"],
                "error": str(exc),
                "manifest_ref": str(manifest_path.as_posix()),
            }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    try:
        result = run_control_surface_enforcement(
            manifest_path=manifest_path,
            manifest_ref="outputs/control_surface_manifest/control_surface_manifest.json",
        )
    except ControlSurfaceEnforcementError as exc:
        return {
            "artifact_type": "control_surface_enforcement_result",
            "enforcement_status": "BLOCK",
            "blocking_reasons": ["CONTROL_SURFACE_ENFORCEMENT_INPUT_INVALID"],
            "error": str(exc),
            "manifest_ref": str(manifest_path.as_posix()),
        }
    return result


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ControlSurfaceGapExtractionError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ControlSurfaceGapExtractionError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ControlSurfaceGapExtractionError(f"{label} must be a JSON object")
    return payload


def _load_json_object_optional(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_explicit_authority_evidence_ref(repo_root: Path, provided_ref: str | None) -> dict[str, Any]:
    if not isinstance(provided_ref, str) or not provided_ref.strip():
        return {
            "resolution_status": "not_provided",
            "authority_state": "authority_unknown_pending_evidence",
            "blocking_reasons": [],
            "evidence_ref": None,
            "evidence_kind": "unspecified",
        }
    ref = provided_ref.strip()
    candidate = Path(ref)
    resolved_path = candidate if candidate.is_absolute() else (repo_root / candidate)
    payload = _load_json_object_optional(resolved_path)
    if payload is None:
        return {
            "resolution_status": "invalid",
            "authority_state": "authority_unknown_pending_evidence",
            "blocking_reasons": ["INVALID_GOVERNED_PQX_AUTHORITY_EVIDENCE_REF"],
            "evidence_ref": ref,
            "evidence_kind": "unknown",
        }

    if payload.get("artifact_type") == "pqx_slice_execution_record":
        if payload.get("status") != "completed" or payload.get("certification_status") != "certified":
            return {
                "resolution_status": "invalid",
                "authority_state": "authority_unknown_pending_evidence",
                "blocking_reasons": ["INVALID_GOVERNED_PQX_AUTHORITY_EVIDENCE_REF"],
                "evidence_ref": ref,
                "evidence_kind": "pqx_slice_execution_record",
            }
        return {
            "resolution_status": "resolved",
            "authority_state": "authoritative_governed_pqx",
            "blocking_reasons": [],
            "evidence_ref": str(candidate),
            "evidence_kind": "pqx_slice_execution_record",
        }

    if payload.get("artifact_type") == "pqx_sequential_execution_trace":
        refs = payload.get("authority_evidence_refs")
        if not isinstance(refs, list) or not refs:
            return {
                "resolution_status": "invalid",
                "authority_state": "authority_unknown_pending_evidence",
                "blocking_reasons": ["INVALID_GOVERNED_PQX_AUTHORITY_EVIDENCE_REF"],
                "evidence_ref": ref,
                "evidence_kind": "pqx_sequential_execution_trace",
            }
        last_ref = refs[-1]
        if not isinstance(last_ref, str) or not last_ref.strip():
            return {
                "resolution_status": "invalid",
                "authority_state": "authority_unknown_pending_evidence",
                "blocking_reasons": ["INVALID_GOVERNED_PQX_AUTHORITY_EVIDENCE_REF"],
                "evidence_ref": ref,
                "evidence_kind": "pqx_sequential_execution_trace",
            }
        return _resolve_explicit_authority_evidence_ref(repo_root, last_ref)

    return {
        "resolution_status": "invalid",
        "authority_state": "authority_unknown_pending_evidence",
        "blocking_reasons": ["INVALID_GOVERNED_PQX_AUTHORITY_EVIDENCE_REF"],
        "evidence_ref": ref,
        "evidence_kind": str(payload.get("artifact_type") or "unknown"),
    }


def resolve_governed_pqx_authority_evidence(repo_root: Path) -> dict[str, Any]:
    evidence_candidates = sorted(
        list((repo_root / "data" / "pqx_runs").rglob("*.pqx_slice_execution_record.json"))
        + list((repo_root / "outputs").rglob("*pqx_slice_execution_record*.json"))
    )
    for path in evidence_candidates:
        payload = _load_json_object_optional(path)
        if not payload:
            continue
        if payload.get("artifact_type") != "pqx_slice_execution_record":
            continue
        if payload.get("status") != "completed":
            continue
        if payload.get("certification_status") != "certified":
            continue
        return {
            "resolution_status": "resolved",
            "authority_state": "authoritative_governed_pqx",
            "blocking_reasons": [],
            "evidence_ref": str(path),
            "evidence_kind": "pqx_slice_execution_record",
        }
    return {
        "resolution_status": "missing",
        "authority_state": "authority_unknown_pending_evidence",
        "blocking_reasons": ["MISSING_GOVERNED_PQX_AUTHORITY_EVIDENCE"],
        "evidence_ref": None,
        "evidence_kind": "pqx_slice_execution_record",
    }


def evaluate_control_surface_gap_bridge(output_dir: Path) -> dict[str, Any]:
    if not (
        _CONTROL_SURFACE_MANIFEST_PATH.is_file()
        and _CONTROL_SURFACE_ENFORCEMENT_PATH.is_file()
        and _CONTROL_SURFACE_OBEDIENCE_PATH.is_file()
    ):
        return {
            "status": "not_run",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": None,
            "blocking": False,
        }

    try:
        manifest = _load_json_object(_CONTROL_SURFACE_MANIFEST_PATH, label="control_surface_manifest")
        enforcement = _load_json_object(_CONTROL_SURFACE_ENFORCEMENT_PATH, label="control_surface_enforcement_result")
        obedience = _load_json_object(_CONTROL_SURFACE_OBEDIENCE_PATH, label="control_surface_obedience_result")
        gap_result = extract_control_surface_gaps(manifest, enforcement, obedience)
    except ControlSurfaceGapExtractionError as exc:
        return {
            "status": "conversion_failed",
            "gap_result": None,
            "gap_result_path": None,
            "pqx_work_items": None,
            "pqx_work_items_path": None,
            "conversion_error": str(exc),
            "blocking": True,
        }

    gap_result_path = output_dir / "control_surface_gap_result.json"
    gap_result_path.write_text(json.dumps(gap_result, indent=2) + "\n", encoding="utf-8")
    conversion_error: str | None = None
    pqx_work_items: list[dict[str, Any]] | None = None
    pqx_work_items_path: str | None = None
    try:
        pqx_work_items = convert_gaps_to_pqx_work_items(gap_result)
        pqx_path = output_dir / "control_surface_gap_pqx_work_items.json"
        pqx_path.write_text(json.dumps(pqx_work_items, indent=2) + "\n", encoding="utf-8")
        pqx_work_items_path = str(pqx_path)
    except ControlSurfaceGapToPQXError as exc:
        conversion_error = str(exc)

    blocker_gaps = [
        gap for gap in gap_result["gaps"] if isinstance(gap, dict) and gap.get("severity") == "blocker"
    ]
    conversion_failed = gap_result["status"] == "gaps_detected" and (conversion_error is not None or not pqx_work_items)
    blocking = bool(blocker_gaps or conversion_failed)
    status = "conversion_failed" if conversion_error else gap_result["status"]

    return {
        "status": status,
        "gap_result": gap_result,
        "gap_result_path": str(gap_result_path),
        "pqx_work_items": pqx_work_items,
        "pqx_work_items_path": pqx_work_items_path,
        "conversion_error": conversion_error,
        "blocking": blocking,
    }


def _should_run_trust_spine_cohesion(changed_paths: list[str]) -> bool:
    return any(path in _TRUST_SPINE_COHESION_TARGETS for path in changed_paths)


def evaluate_trust_spine_cohesion(changed_paths: list[str], output_dir: Path) -> dict[str, Any] | None:
    if not _should_run_trust_spine_cohesion(changed_paths):
        return None

    required_paths = [
        _CONTROL_SURFACE_MANIFEST_PATH,
        _CONTROL_SURFACE_ENFORCEMENT_PATH,
        _CONTROL_SURFACE_OBEDIENCE_PATH,
        _TRUST_SPINE_INVARIANT_PATH,
        _DONE_CERTIFICATION_PATH,
    ]
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        return None

    try:
        result = evaluate_trust_spine_evidence_cohesion(
            artifacts={
                "manifest": _load_json_object(_CONTROL_SURFACE_MANIFEST_PATH, label="control_surface_manifest"),
                "enforcement_result": _load_json_object(_CONTROL_SURFACE_ENFORCEMENT_PATH, label="control_surface_enforcement_result"),
                "obedience_result": _load_json_object(_CONTROL_SURFACE_OBEDIENCE_PATH, label="control_surface_obedience_result"),
                "invariant_result": _load_json_object(_TRUST_SPINE_INVARIANT_PATH, label="trust_spine_invariant_result"),
                "done_certification_record": _load_json_object(_DONE_CERTIFICATION_PATH, label="done_certification_record"),
            },
            refs={
                "manifest_ref": str(_CONTROL_SURFACE_MANIFEST_PATH),
                "enforcement_result_ref": str(_CONTROL_SURFACE_ENFORCEMENT_PATH),
                "obedience_result_ref": str(_CONTROL_SURFACE_OBEDIENCE_PATH),
                "invariant_result_ref": str(_TRUST_SPINE_INVARIANT_PATH),
                "done_certification_ref": str(_DONE_CERTIFICATION_PATH),
            },
        )
        Draft202012Validator(load_schema("trust_spine_evidence_cohesion_result"), format_checker=FormatChecker()).validate(result)
    except (TrustSpineEvidenceCohesionError, ControlSurfaceGapExtractionError) as exc:
        return {
            "artifact_type": "trust_spine_evidence_cohesion_result",
            "overall_decision": "BLOCK",
            "blocking_reasons": ["TRUST_SPINE_COHESION_INPUT_INVALID"],
            "error": str(exc),
        }

    cohesion_path = output_dir / "trust_spine_evidence_cohesion_result.json"
    cohesion_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["artifact_path"] = str(cohesion_path)
    return result


def map_preflight_control_signal(*, report: dict[str, Any], hardening_flow: bool, event_name: str = "") -> dict[str, Any]:
    changed_path_detection = report.get("changed_path_detection", {})
    detection_mode = str(changed_path_detection.get("changed_path_detection_mode", "unknown"))
    preflight_mode = str(changed_path_detection.get("preflight_mode", "explicit_or_local_inspection"))
    degraded = detection_mode == "degraded_full_governed_scan"
    masking_detected = bool(report.get("masked_failures"))
    has_propagation_failures = bool(report.get("schema_example_failures") or report.get("producer_failures"))
    impacted_downstream = bool(report.get("fixture_failures") or report.get("consumer_failures"))
    invariant_violations = bool(report.get("invariant_violations"))
    missing_required_surface = bool(report.get("missing_required_surface"))
    pqx_execution_policy = report.get("pqx_execution_policy") or {}
    pqx_policy_blocking = str(pqx_execution_policy.get("status", "")).lower() == "block"
    pqx_policy_warning = str(pqx_execution_policy.get("status", "")).lower() == "warn"
    inspection_only_commit_range = (
        preflight_mode == "commit_range_inspection"
        and str(pqx_execution_policy.get("execution_context", "unspecified")) == "unspecified"
        and pqx_policy_warning
    )
    governed_commit_range_with_authority = (
        preflight_mode == "commit_range_inspection"
        and str(pqx_execution_policy.get("execution_context", "unspecified")) == "pqx_governed"
        and str(pqx_execution_policy.get("status", "")).lower() == "allow"
        and str(pqx_execution_policy.get("authority_state", "")) == "authoritative_governed_pqx"
    )
    status = str(report.get("status", "failed"))

    if status == "skipped":
        return {
            "strategy_gate_decision": "BLOCK",
            "rationale": "skipped status is non-compliant unless explicitly justified",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if (
        masking_detected
        or has_propagation_failures
        or invariant_violations
        or (missing_required_surface and not (inspection_only_commit_range or governed_commit_range_with_authority))
        or pqx_policy_blocking
    ):
        return {
            "strategy_gate_decision": "BLOCK",
            "rationale": "preflight failed on propagation/masking/invariant/required-surface/PQX-policy risk",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if pqx_policy_warning and event_name == "pull_request":
        return {
            "strategy_gate_decision": "BLOCK",
            "rationale": "PR trust seam requires ALLOW-only pass semantics; WARN is fail-closed",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if pqx_policy_warning:
        return {
            "strategy_gate_decision": "ALLOW",
            "rationale": "inspection-only commit-range mode accepted without governed execution assertion",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if governed_commit_range_with_authority and not (
        masking_detected or has_propagation_failures or invariant_violations or pqx_policy_blocking or degraded
    ):
        return {
            "strategy_gate_decision": "ALLOW",
            "rationale": "commit-range inspection accepted with explicit governed PQX authority evidence",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if hardening_flow and impacted_downstream:
        return {
            "strategy_gate_decision": "FREEZE",
            "rationale": "hardening flow requires downstream seam repair before progression",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if status == "passed" and degraded and event_name == "pull_request":
        return {
            "strategy_gate_decision": "BLOCK",
            "rationale": "PR trust seam blocks degraded path resolution outcomes",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if status == "passed" and degraded:
        return {
            "strategy_gate_decision": "BLOCK",
            "rationale": "preflight passed under degraded full governed scan mode; fail-closed required",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    if status == "passed":
        return {
            "strategy_gate_decision": "ALLOW",
            "rationale": "preflight passed with clean detection and no masking risk",
            "changed_path_detection_mode": detection_mode,
            "degraded_detection": degraded,
        }
    return {
        "strategy_gate_decision": "BLOCK",
        "rationale": "preflight status unresolved or failed",
        "changed_path_detection_mode": detection_mode,
        "degraded_detection": degraded,
    }


def build_preflight_result_artifact(
    *,
    report: dict[str, Any],
    json_report_path: Path,
    markdown_report_path: Path,
    hardening_flow: bool,
) -> dict[str, Any]:
    detection = report.get("changed_path_detection", {})
    control_signal = map_preflight_control_signal(
        report=report,
        hardening_flow=hardening_flow,
        event_name=str(report.get("pytest_execution", {}).get("event_name", "")),
    )
    required_context = report.get("pqx_required_context_enforcement")
    if not isinstance(required_context, dict):
        required_context = {
            "classification": "exploration_only_or_non_governed",
            "execution_context": "unspecified",
            "wrapper_present": False,
            "wrapper_context_valid": True,
            "authority_context_valid": True,
            "authority_state": "non_authoritative_direct_run",
            "requires_pqx_execution": False,
            "enforcement_decision": "allow",
            "status": "allow",
            "blocking_reasons": [],
        }
    return {
        "artifact_type": "contract_preflight_result_artifact",
        "schema_version": "1.5.0",
        "preflight_status": report.get("status", "failed"),
        "changed_contracts": report.get("changed_contracts", []),
        "impacted_producers": report.get("impact", {}).get("producers", []),
        "impacted_fixtures": report.get("impact", {}).get("fixtures_or_builders", []),
        "impacted_consumers": report.get("impact", {}).get("consumers", []),
        "masking_detected": bool(report.get("masked_failures")),
        "recommended_repair_area": report.get("recommended_repair_areas", []),
        "report_paths": {
            "json_report_path": str(json_report_path),
            "markdown_report_path": str(markdown_report_path),
        },
        "generated_at": _utc_now(),
        "control_surface_gap_status": report.get("control_surface_gap_status", "not_run"),
        "control_surface_gap_result_ref": report.get("control_surface_gap_result_ref"),
        "pqx_gap_work_items_ref": report.get("pqx_gap_work_items_ref"),
        "control_surface_gap_blocking": bool(report.get("control_surface_gap_blocking", False)),
        "pytest_execution": report.get("pytest_execution", {}),
        "pytest_execution_record_ref": report.get("pytest_execution_record_ref"),
        "pytest_selection_integrity": report.get("pytest_selection_integrity", {}),
        "pytest_selection_integrity_result_ref": report.get("pytest_selection_integrity_result_ref"),
        "pytest_artifact_linkage": {
            "pytest_execution_record_ref": _CANONICAL_PYTEST_EXECUTION_REF,
            "pytest_execution_record_hash": str((report.get("pytest_execution_record") or {}).get("artifact_hash") or ""),
            "pytest_selection_integrity_result_ref": _CANONICAL_PYTEST_SELECTION_REF,
            "pytest_selection_integrity_result_hash": str((report.get("pytest_selection_integrity") or {}).get("artifact_hash") or ""),
        },
        "pqx_required_context_enforcement": {
            "classification": str(required_context.get("classification", "exploration_only_or_non_governed")),
            "execution_context": str(required_context.get("execution_context", "unspecified")),
            "wrapper_present": bool(required_context.get("wrapper_present", False)),
            "wrapper_context_valid": bool(required_context.get("wrapper_context_valid", False)),
            "authority_context_valid": bool(required_context.get("authority_context_valid", False)),
            "authority_state": str(required_context.get("authority_state", "non_authoritative_direct_run")),
            "requires_pqx_execution": bool(required_context.get("requires_pqx_execution", False)),
            "enforcement_decision": str(required_context.get("enforcement_decision", required_context.get("status", "block"))),
            "status": str(required_context.get("status", "block")),
            "blocking_reasons": sorted({str(reason) for reason in required_context.get("blocking_reasons", []) if str(reason)}),
        },
        "control_signal": control_signal,
        "trace": {
            "producer": "scripts/run_contract_preflight.py",
            "policy_version": _PREFLIGHT_POLICY_VERSION,
            "refs_attempted": detection.get("refs_attempted", []),
            "fallback_used": bool(detection.get("fallback_used", False)),
            "evaluation_mode": detection.get("evaluation_mode", "partial"),
            "skip_reason": report.get("skip_reason"),
            "changed_paths_resolved": detection.get("changed_paths_resolved", []),
            "evaluated_surfaces": detection.get("evaluated_surfaces", []),
            "provenance_ref": "contracts/standards-manifest.json",
        },
    }


def main() -> int:
    args = _parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if bool(getattr(args, "refresh_test_inventory_baseline", False)):
        refreshed = refresh_test_inventory_baseline(
            repo_root=REPO_ROOT,
            baseline_path=_TEST_INVENTORY_BASELINE_PATH,
            suite_targets=_DEFAULT_PR_INVENTORY_TARGETS,
        )
        print(json.dumps({"status": "baseline_refreshed", "baseline_path": str(_TEST_INVENTORY_BASELINE_PATH), "baseline": refreshed}, indent=2))
        return 0

    ref_context = normalize_preflight_ref_context(
        event_name=getattr(args, "event_name", None),
        cli_base_ref=getattr(args, "base_ref", ""),
        cli_head_ref=getattr(args, "head_ref", ""),
        env=os.environ,
    )
    if not ref_context.valid:
        report = {
            "status": "failed",
            "changed_contracts": [],
            "changed_examples": [],
            "changed_path_detection": {
                "changed_path_detection_mode": "ref_context_invalid",
                "changed_paths_resolved": [],
                "refs_attempted": [],
                "fallback_used": False,
                "warnings": [str(ref_context.invalid_reason)],
                "evaluation_mode": "blocked",
                "evaluated_surfaces": [],
                "ref_context": ref_context.as_dict(),
            },
            "impact": {"producers": [], "fixtures_or_builders": [], "consumers": [], "required_smoke_tests": []},
            "schema_example_failures": [],
            "producer_failures": [],
            "fixture_failures": [],
            "consumer_failures": [],
            "masked_failures": [],
            "recommended_repair_areas": ["preflight reference normalization"],
            "bootstrap_failures": ["preflight ref normalization failed closed"],
            "evaluation_classification": [],
            "missing_required_surface": [],
            "skip_reason": None,
            "invariant_violations": [str(ref_context.reason_code or "malformed_ref_context")],
            "control_surface_enforcement": None,
            "control_surface_gap_result": None,
            "control_surface_gap_pqx_work_items": None,
            "control_surface_gap_pqx_conversion_error": None,
            "trust_spine_evidence_cohesion": None,
            "pqx_execution_policy": {"status": "block", "blocking_reasons": [str(ref_context.reason_code or "malformed_ref_context")]},
            "pqx_required_context_enforcement": {"status": "block", "blocking_reasons": [str(ref_context.reason_code or "malformed_ref_context")]},
            "system_registry_guard_result": {"artifact_type": "system_registry_guard_result", "status": "pass", "normalized_reason_codes": []},
            "system_registry_guard_result_ref": None,
            "pytest_execution": {
                "event_name": str(ref_context.event_name or ""),
                "pytest_execution_count": 0,
                "pytest_commands": [],
                "selected_targets": [],
                "fallback_targets": [],
                "fallback_used": False,
                "targeted_selection_empty": True,
                "fallback_selection_empty": False,
                "selection_reason_codes": [],
            },
            "ref_context": ref_context.as_dict(),
            "root_cause_classification": {"failure_class": "missing_required_artifact", "reason_codes": [str(ref_context.reason_code or "malformed_ref_context")]},
            "repair_eligibility_rationale": "auto_repair_allowed: normalized ref context unavailable and must be reconstructed with bounded inputs",
            "secondary_exception": None,
        }
        json_path = output_dir / "contract_preflight_report.json"
        md_path = output_dir / "contract_preflight_report.md"
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_markdown(report), encoding="utf-8")
        preflight_artifact = build_preflight_result_artifact(
            report=report,
            json_report_path=json_path,
            markdown_report_path=md_path,
            hardening_flow=bool(args.hardening_flow),
        )
        preflight_artifact_path = output_dir / "contract_preflight_result_artifact.json"
        preflight_artifact_path.write_text(json.dumps(preflight_artifact, indent=2) + "\n", encoding="utf-8")
        emit_preflight_block_bundle(report=report, preflight_artifact=preflight_artifact, output_dir=output_dir)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "json_report": str(json_path),
                    "markdown_report": str(md_path),
                    "preflight_artifact": str(preflight_artifact_path),
                    "strategy_gate_decision": preflight_artifact["control_signal"]["strategy_gate_decision"],
                    "ref_context": ref_context.as_dict(),
                },
                indent=2,
            )
        )
        return 2

    detection = detect_changed_paths(REPO_ROOT, ref_context.base_ref, ref_context.head_ref, args.changed_path)
    registry_policy = load_guard_policy(_SYSTEM_REGISTRY_GUARD_POLICY_PATH)
    registry_model = parse_system_registry(_SYSTEM_REGISTRY_PATH)
    system_registry_guard_result = evaluate_system_registry_guard(
        repo_root=REPO_ROOT,
        changed_files=detection.changed_paths,
        policy=registry_policy,
        registry_model=registry_model,
    )
    srg_output_path = output_dir / "system_registry_guard_result.json"
    srg_output_path.write_text(json.dumps(system_registry_guard_result, indent=2) + "\n", encoding="utf-8")
    control_surface_gap_bridge = evaluate_control_surface_gap_bridge(output_dir)
    trust_spine_cohesion = evaluate_trust_spine_cohesion(detection.changed_paths, output_dir)
    classified = classify_changed_contracts(detection.changed_paths)
    surface_classification = classify_evaluation_surfaces(detection.changed_paths, classified)

    changed_contract_paths = classified["changed_contract_paths"]
    changed_governed_definitions = classified["changed_governed_definitions"]
    changed_contracts = changed_contract_paths + changed_governed_definitions
    changed_examples = classified["changed_example_paths"]
    detection_meta = {
        "changed_path_detection_mode": detection.changed_path_detection_mode,
        "changed_paths_resolved": detection.changed_paths,
        "refs_attempted": detection.refs_attempted,
        "fallback_used": detection.fallback_used,
        "warnings": detection.warnings,
        "evaluation_mode": surface_classification["evaluation_mode"],
        "evaluated_surfaces": surface_classification["evaluated_surfaces"],
        "ref_context": ref_context.as_dict(),
    }
    preflight_mode = (
        "commit_range_inspection"
        if not list(getattr(args, "changed_path", []) or [])
        and bool(ref_context.base_ref)
        and bool(ref_context.head_ref)
        else "explicit_or_local_inspection"
    )
    detection_meta["preflight_mode"] = preflight_mode
    pqx_execution_policy: dict[str, Any] | None = None
    pqx_required_context_enforcement: dict[str, Any] | None = None
    wrapper_payload: dict[str, Any] | None = None
    explicit_authority_resolution = _resolve_explicit_authority_evidence_ref(
        REPO_ROOT,
        getattr(args, "authority_evidence_ref", None),
    )
    wrapper_path_value = getattr(args, "pqx_wrapper_path", None)
    wrapper_resolution: dict[str, Any] | None = None
    if wrapper_path_value:
        wrapper_path = _resolve_wrapper_path(REPO_ROOT, str(wrapper_path_value))
        if not wrapper_path.exists():
            wrapper_resolution = _attempt_build_missing_wrapper(
                repo_root=REPO_ROOT,
                wrapper_path=wrapper_path,
                base_ref=str(getattr(args, "base_ref", "origin/main")),
                head_ref=str(getattr(args, "head_ref", "HEAD")),
            )
        try:
            wrapper_payload = json.loads(wrapper_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blocking_reasons = ["MALFORMED_PQX_TASK_WRAPPER"]
            if isinstance(wrapper_resolution, dict) and wrapper_resolution.get("attempted") and not wrapper_resolution.get("built"):
                blocking_reasons.insert(0, "MISSING_PQX_TASK_WRAPPER_AUTO_BUILD_FAILED")
            pqx_required_context_enforcement = {
                "classification": "governed_pqx_required",
                "execution_context": str(getattr(args, "execution_context", "unspecified") or "unspecified"),
                "wrapper_present": wrapper_path.exists(),
                "wrapper_context_valid": False,
                "authority_context_valid": False,
                "status": "block",
                "blocking_reasons": blocking_reasons,
                "error": str(exc),
            }
    detection_meta["pqx_wrapper_resolution"] = wrapper_resolution
    try:
        pqx_execution_policy = evaluate_pqx_execution_policy(
            changed_paths=detection.changed_paths,
            execution_context=getattr(args, "execution_context", "unspecified"),
            changed_path_detection_mode=detection.changed_path_detection_mode,
        ).to_dict()
    except PQXExecutionPolicyError as exc:
        pqx_execution_policy = {
            "policy_version": "1.0.0",
            "classification": "governed_pqx_required",
            "execution_context": str(getattr(args, "execution_context", "unspecified") or "unspecified"),
            "pqx_required": True,
            "status": "block",
            "authority_state": "non_authoritative_direct_run",
            "authority_resolution": "malformed_changed_path_input",
            "blocking_reasons": ["MALFORMED_CHANGED_PATH_INPUT"],
            "error": str(exc),
        }
    detection_meta["pqx_execution_policy"] = pqx_execution_policy
    if pqx_required_context_enforcement is None and isinstance(pqx_execution_policy, dict):
        authority_ref_for_enforcement = (
            explicit_authority_resolution.get("evidence_ref")
            if explicit_authority_resolution.get("resolution_status") == "resolved"
            else getattr(args, "authority_evidence_ref", None)
        )
        try:
            pqx_required_context_enforcement = enforce_pqx_required_context(
                classification=str(pqx_execution_policy.get("classification", "exploration_only_or_non_governed")),
                execution_context=getattr(args, "execution_context", "unspecified"),
                changed_paths=detection.changed_paths,
                pqx_task_wrapper=wrapper_payload,
                authority_evidence_ref=authority_ref_for_enforcement,
                preflight_mode=preflight_mode,
            ).to_dict()
        except PQXRequiredContextEnforcementError as exc:
            pqx_required_context_enforcement = {
                "classification": str(pqx_execution_policy.get("classification", "governed_pqx_required")),
                "execution_context": str(getattr(args, "execution_context", "unspecified") or "unspecified"),
                "wrapper_present": bool(wrapper_payload is not None),
                "wrapper_context_valid": False,
                "authority_context_valid": False,
                "status": "block",
                "blocking_reasons": ["MALFORMED_REQUIRED_CONTEXT_INPUT"],
                "error": str(exc),
            }
    detection_meta["pqx_required_context_enforcement"] = pqx_required_context_enforcement
    if (
        isinstance(pqx_required_context_enforcement, dict)
        and str(pqx_required_context_enforcement.get("status", "")).lower() == "block"
    ):
        reasons = list(pqx_required_context_enforcement.get("blocking_reasons", []))
        if isinstance(pqx_execution_policy, dict):
            pqx_execution_policy["status"] = "block"
            pqx_execution_policy["blocking_reasons"] = sorted(
                set(list(pqx_execution_policy.get("blocking_reasons", [])) + reasons)
            )
            pqx_execution_policy["authority_resolution"] = "pqx_required_context_enforcement_block"
            pqx_execution_policy["authority_state"] = "non_authoritative_direct_run"
    if (
        preflight_mode == "commit_range_inspection"
        and isinstance(pqx_execution_policy, dict)
        and isinstance(pqx_required_context_enforcement, dict)
        and str(pqx_required_context_enforcement.get("status", "")).lower() == "allow"
        and str(pqx_execution_policy.get("classification", "")) == "governed_pqx_required"
        and str(getattr(args, "execution_context", "unspecified") or "unspecified").strip() == "unspecified"
    ):
        pqx_execution_policy["status"] = "warn"
        pqx_execution_policy["authority_state"] = "unknown_pending_execution"
        pqx_execution_policy["authority_resolution"] = "pending_execution_context"
        pqx_execution_policy["blocking_reasons"] = []
    if isinstance(pqx_execution_policy, dict) and pqx_execution_policy.get("status") == "pending_evidence":
        authority_resolution = (
            explicit_authority_resolution
            if explicit_authority_resolution.get("resolution_status") in {"resolved", "invalid"}
            else resolve_governed_pqx_authority_evidence(REPO_ROOT)
        )
        pqx_execution_policy["authority_evidence_resolution_status"] = authority_resolution["resolution_status"]
        pqx_execution_policy["authority_evidence_ref"] = authority_resolution["evidence_ref"]
        pqx_execution_policy["authority_evidence_kind"] = authority_resolution["evidence_kind"]
        if authority_resolution["resolution_status"] == "resolved":
            pqx_execution_policy["status"] = "allow"
            pqx_execution_policy["authority_state"] = "authoritative_governed_pqx"
            pqx_execution_policy["authority_resolution"] = "resolved_from_repo_evidence"
            pqx_execution_policy["blocking_reasons"] = []
        else:
            commit_range_mode = detection.changed_path_detection_mode in {
                "base_head_diff",
                "base_to_current_head_fallback",
                "github_pr_sha_pair",
                "github_push_sha_pair",
            }
            pqx_execution_policy["status"] = "warn" if commit_range_mode else "block"
            pqx_execution_policy["authority_state"] = "authority_unknown_pending_evidence"
            pqx_execution_policy["authority_resolution"] = (
                "inspection_context_without_pqx_evidence" if commit_range_mode else "missing_repo_evidence"
            )
            pqx_execution_policy["blocking_reasons"] = authority_resolution["blocking_reasons"]

    test_inventory_eval = evaluate_test_inventory_integrity(
        repo_root=REPO_ROOT,
        baseline_path=_TEST_INVENTORY_BASELINE_PATH,
        suite_targets=_DEFAULT_PR_INVENTORY_TARGETS,
        execution_cwd=Path.cwd(),
    )
    test_inventory_payload = test_inventory_eval.payload
    test_inventory_artifact_path = output_dir / "test_inventory_integrity_result.json"
    test_inventory_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    test_inventory_artifact_path.write_text(json.dumps(test_inventory_payload, indent=2) + "\n", encoding="utf-8")
    is_pull_request_event = str(ref_context.event_name or "").strip() == "pull_request"
    pytest_execution_log: list[dict[str, Any]] = []
    selected_pytest_targets: list[str] = []
    fallback_pytest_targets: list[str] = []
    fallback_pytest_used = False
    targeted_selection_empty = False
    fallback_selection_empty = False
    pytest_selection_reason_codes: list[str] = []

    if detection.changed_path_detection_mode == "detection_failed_no_governed_paths":
        detection_invariants = ["changed-path detection failed before evaluation"]
        ref_raw = ref_context.raw_inputs
        if (
            ref_context.event_name == "push"
            and ref_context.fallback_used
            and not str(ref_raw.get("github_base_sha", "")).strip()
            and not str(ref_raw.get("github_head_sha", "")).strip()
        ):
            detection_invariants.append("contract_mismatch_from_bad_ref_resolution")
        report = {
            "status": "failed",
            "changed_contracts": [],
            "changed_examples": [],
            "changed_path_detection": detection_meta,
            "impact": {
                "producers": [],
                "fixtures_or_builders": [],
                "consumers": [],
                "required_smoke_tests": [],
            },
            "schema_example_failures": [],
            "producer_failures": [],
            "fixture_failures": [],
            "consumer_failures": [],
            "masked_failures": [],
            "recommended_repair_areas": ["contracts/"],
            "bootstrap_failures": ["changed-path detection failed and no governed paths were available"],
            "evaluation_classification": surface_classification["path_classifications"],
            "missing_required_surface": [],
            "skip_reason": None,
            "invariant_violations": detection_invariants,
            "control_surface_enforcement": None,
            "control_surface_gap_result": control_surface_gap_bridge["gap_result"],
            "control_surface_gap_pqx_work_items": control_surface_gap_bridge["pqx_work_items"],
            "control_surface_gap_pqx_conversion_error": control_surface_gap_bridge["conversion_error"],
            "trust_spine_evidence_cohesion": trust_spine_cohesion,
            "pqx_execution_policy": pqx_execution_policy,
            "pqx_required_context_enforcement": pqx_required_context_enforcement,
            "system_registry_guard_result": system_registry_guard_result,
            "system_registry_guard_result_ref": str(srg_output_path),
            "test_inventory_integrity": test_inventory_payload,
            "test_inventory_integrity_result_ref": str(test_inventory_artifact_path),
            "pytest_selection_integrity": {},
            "pytest_selection_integrity_result_ref": None,
        }
    elif not surface_classification["required_paths"]:
        report = {
            "status": "passed",
            "changed_contracts": [],
            "changed_examples": [],
            "changed_path_detection": detection_meta,
            "impact": {
                "producers": [],
                "fixtures_or_builders": [],
                "consumers": [],
                "required_smoke_tests": [],
            },
            "schema_example_failures": [],
            "producer_failures": [],
            "fixture_failures": [],
            "consumer_failures": [],
            "masked_failures": [],
            "recommended_repair_areas": [],
            "evaluation_classification": surface_classification["path_classifications"],
            "missing_required_surface": [],
            "skip_reason": "explicit no-op: changed paths have no applicable contract surface",
            "invariant_violations": [],
            "control_surface_enforcement": None,
            "control_surface_gap_result": control_surface_gap_bridge["gap_result"],
            "control_surface_gap_pqx_work_items": control_surface_gap_bridge["pqx_work_items"],
            "control_surface_gap_pqx_conversion_error": control_surface_gap_bridge["conversion_error"],
            "trust_spine_evidence_cohesion": trust_spine_cohesion,
            "pqx_execution_policy": pqx_execution_policy,
            "pqx_required_context_enforcement": pqx_required_context_enforcement,
            "system_registry_guard_result": system_registry_guard_result,
            "system_registry_guard_result_ref": str(srg_output_path),
            "test_inventory_integrity": test_inventory_payload,
            "test_inventory_integrity_result_ref": str(test_inventory_artifact_path),
            "pytest_selection_integrity": {},
            "pytest_selection_integrity_result_ref": None,
        }
    else:
        if changed_contract_paths:
            impact = build_impact_map(REPO_ROOT, changed_contract_paths, changed_examples)
            contract_impact_artifact = impact["contract_impact_artifact"]
        else:
            impact = {
                "producers": [],
                "fixtures_or_builders": [],
                "consumers": [],
                "required_smoke_tests": [],
            }
            contract_impact_artifact = None

        schema_example_failures = validate_examples(changed_examples)

        producer_targets = resolve_test_targets(REPO_ROOT, impact["producers"] + impact["consumers"])
        fixture_targets = resolve_test_targets(REPO_ROOT, impact["fixtures_or_builders"])
        smoke_targets = sorted(set(impact["required_smoke_tests"]))
        forced_eval_targets_by_path = resolve_required_surface_tests(REPO_ROOT, surface_classification["required_paths"])
        contract_surface_paths = set(changed_contracts + changed_examples)
        missing_required_surface = [
            {
                "path": path,
                "reason": "required contract surface changed but no deterministic evaluation target was found",
            }
            for path, targets in forced_eval_targets_by_path.items()
            if not targets and path not in contract_surface_paths
        ]
        missing_required_surface.extend(
            validate_control_surface_gap_packet_test_expectations(
                changed_paths=surface_classification["required_paths"],
                resolved_targets_by_path=forced_eval_targets_by_path,
            )
        )
        forced_targets = sorted({target for targets in forced_eval_targets_by_path.values() for target in targets})

        producer_eval_targets = sorted(set(producer_targets + forced_targets))
        selected_pytest_targets = sorted(set(producer_eval_targets + fixture_targets + smoke_targets))
        targeted_selection_empty = len(selected_pytest_targets) == 0
        if is_pull_request_event and targeted_selection_empty:
            pytest_selection_reason_codes.append("PR_PYTEST_SELECTED_TARGETS_EMPTY")
        producer_failures = run_targeted_pytests(producer_eval_targets, execution_log=pytest_execution_log) if producer_eval_targets else []
        fixture_failures = run_targeted_pytests(fixture_targets, execution_log=pytest_execution_log) if fixture_targets else []
        consumer_failures = run_targeted_pytests(smoke_targets, execution_log=pytest_execution_log) if smoke_targets else []

        masked_failures = detect_masked_failures(producer_failures + fixture_failures + consumer_failures)

        recommended_areas = []
        if schema_example_failures:
            recommended_areas.append("contracts/examples")
        if producer_failures:
            recommended_areas.append("spectrum_systems/orchestration and runtime producers")
        if fixture_failures:
            recommended_areas.append("tests/fixtures and tests/helpers builders")
        if consumer_failures:
            recommended_areas.append("targeted downstream consumer tests")
        if missing_required_surface:
            recommended_areas.append("required evaluation mapping for changed governance/runtime/test surfaces")

        report = {
            "status": "failed"
            if (schema_example_failures or producer_failures or fixture_failures or consumer_failures or missing_required_surface)
            else "passed",
            "changed_contracts": changed_contracts,
            "changed_examples": changed_examples,
            "changed_path_detection": detection_meta,
            "impact": {
                "producers": impact["producers"],
                "fixtures_or_builders": impact["fixtures_or_builders"],
                "consumers": impact["consumers"],
                "required_smoke_tests": impact["required_smoke_tests"],
            },
            "contract_impact_artifact": contract_impact_artifact,
            "schema_example_failures": schema_example_failures,
            "producer_failures": producer_failures,
            "fixture_failures": fixture_failures,
            "consumer_failures": consumer_failures,
            "masked_failures": masked_failures,
            "recommended_repair_areas": sorted(set(recommended_areas)),
            "evaluation_classification": surface_classification["path_classifications"],
            "missing_required_surface": missing_required_surface,
            "skip_reason": None,
            "invariant_violations": [],
            "control_surface_enforcement": evaluate_control_surface_enforcement(surface_classification["required_paths"]),
            "control_surface_gap_result": control_surface_gap_bridge["gap_result"],
            "control_surface_gap_pqx_work_items": control_surface_gap_bridge["pqx_work_items"],
            "control_surface_gap_pqx_conversion_error": control_surface_gap_bridge["conversion_error"],
            "trust_spine_evidence_cohesion": trust_spine_cohesion,
            "pqx_execution_policy": pqx_execution_policy,
            "pqx_required_context_enforcement": pqx_required_context_enforcement,
            "system_registry_guard_result": system_registry_guard_result,
            "system_registry_guard_result_ref": str(srg_output_path),
            "test_inventory_integrity": test_inventory_payload,
            "test_inventory_integrity_result_ref": str(test_inventory_artifact_path),
            "pytest_selection_integrity": {},
            "pytest_selection_integrity_result_ref": None,
        }
    if is_pull_request_event and report.get("status") == "passed" and not pytest_execution_log:
        fallback_pytest_targets = _resolve_existing_pytest_targets(_GOVERNED_PR_FALLBACK_PYTEST_TARGETS)
        fallback_pytest_used = True
        if "PR_PYTEST_SELECTED_TARGETS_EMPTY" not in pytest_selection_reason_codes:
            pytest_selection_reason_codes.append("PR_PYTEST_SELECTED_TARGETS_EMPTY")
        fallback_selection_empty = len(fallback_pytest_targets) == 0
        if fallback_pytest_targets:
            fallback_failures = run_targeted_pytests(fallback_pytest_targets, execution_log=pytest_execution_log)
            if fallback_failures:
                report["status"] = "failed"
                report["consumer_failures"] = sorted(
                    list(report.get("consumer_failures", [])) + fallback_failures,
                    key=lambda entry: str(entry.get("path", "")) if isinstance(entry, dict) else str(entry),
                )
                report["recommended_repair_areas"] = sorted(
                    set(report.get("recommended_repair_areas", []) + ["governed fallback PR pytest suite"])
                )
        else:
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_FALLBACK_TARGETS_EMPTY"])
            )
            report["recommended_repair_areas"] = sorted(
                set(report.get("recommended_repair_areas", []) + ["restore governed PR fallback pytest suite"])
            )

    report["pytest_execution"] = {
        "event_name": str(ref_context.event_name or ""),
        "pytest_execution_count": len(pytest_execution_log),
        "pytest_commands": [str(entry.get("command", "")) for entry in pytest_execution_log],
        "selected_targets": selected_pytest_targets,
        "fallback_targets": fallback_pytest_targets,
        "fallback_used": fallback_pytest_used,
        "targeted_selection_empty": targeted_selection_empty,
        "fallback_selection_empty": fallback_selection_empty,
        "selection_reason_codes": sorted(set(pytest_selection_reason_codes)),
    }
    pytest_execution_record = build_pytest_execution_record(
        event_name=str(ref_context.event_name or ""),
        source_head_ref=str(ref_context.head_ref or ""),
        execution_log=pytest_execution_log,
        selected_targets=selected_pytest_targets,
        fallback_targets=fallback_pytest_targets,
        fallback_used=fallback_pytest_used,
        targeted_selection_empty=targeted_selection_empty,
        fallback_selection_empty=fallback_selection_empty,
        selection_reason_codes=pytest_selection_reason_codes,
    )
    validate_artifact(pytest_execution_record, "pytest_execution_record")
    report["pytest_execution_record"] = pytest_execution_record
    pytest_execution_record_path = output_dir / "pytest_execution_record.json"
    pytest_execution_record_path.write_text(json.dumps(pytest_execution_record, indent=2) + "\n", encoding="utf-8")
    report["pytest_execution_record_ref"] = _CANONICAL_PYTEST_EXECUTION_REF
    pytest_execution_record_hash = str(pytest_execution_record.get("artifact_hash") or "")

    required_targets_for_integrity = sorted(set(smoke_targets + forced_targets)) if "smoke_targets" in locals() and "forced_targets" in locals() else []
    selection_provenance = _build_common_provenance(source_head_ref=str(ref_context.head_ref or ""))
    selection_provenance.update(
        {
            "source_pytest_execution_record_ref": _CANONICAL_PYTEST_EXECUTION_REF,
            "source_pytest_execution_record_hash": pytest_execution_record_hash,
        }
    )
    try:
        selection_eval = evaluate_pytest_selection_integrity(
            changed_paths=detection.changed_paths,
            selected_test_targets=sorted(set(selected_pytest_targets + fallback_pytest_targets)),
            required_test_targets=required_targets_for_integrity,
            pytest_execution_record=pytest_execution_record,
            policy_path=_PYTEST_SELECTION_INTEGRITY_POLICY_PATH,
            generated_at=_utc_now(),
            provenance=selection_provenance,
        )
        report["pytest_selection_integrity"] = selection_eval.payload
    except PytestSelectionIntegrityError:
        report["pytest_selection_integrity"] = {
            "artifact_type": "pytest_selection_integrity_result",
            "schema_version": "1.1.0",
            "changed_paths": sorted(set(detection.changed_paths)),
            "required_test_targets": required_targets_for_integrity,
            "selected_test_targets": sorted(set(selected_pytest_targets + fallback_pytest_targets)),
            "missing_required_targets": required_targets_for_integrity,
            "selection_count": len(sorted(set(selected_pytest_targets + fallback_pytest_targets))),
            "minimum_selection_threshold": 1,
            "threshold_satisfied": False,
            "impacted_surface_count": len(detection.changed_paths),
            "selection_integrity_decision": "BLOCK",
            "blocking_reasons": ["PYTEST_SELECTION_ARTIFACT_INVALID"],
            "generated_at": _utc_now(),
            "source_commit_sha": selection_provenance["source_commit_sha"],
            "source_head_ref": selection_provenance["source_head_ref"],
            "workflow_run_id": selection_provenance["workflow_run_id"],
            "producer_script": selection_provenance["producer_script"],
            "produced_at": selection_provenance["produced_at"],
            "source_pytest_execution_record_ref": selection_provenance["source_pytest_execution_record_ref"],
            "source_pytest_execution_record_hash": selection_provenance["source_pytest_execution_record_hash"],
        }
        report["pytest_selection_integrity"]["artifact_hash"] = _hash_payload(report["pytest_selection_integrity"])
    selection_integrity_valid = True
    try:
        validate_artifact(report["pytest_selection_integrity"], "pytest_selection_integrity_result")
    except Exception:
        selection_integrity_valid = False
        report["status"] = "failed"
        report["invariant_violations"] = sorted(set(report.get("invariant_violations", []) + ["PYTEST_SELECTION_ARTIFACT_INVALID"]))
        report["pytest_selection_integrity"] = {
            "artifact_type": "pytest_selection_integrity_result",
            "schema_version": "1.1.0",
            "changed_paths": sorted(set(detection.changed_paths)),
            "required_test_targets": required_targets_for_integrity,
            "selected_test_targets": sorted(set(selected_pytest_targets + fallback_pytest_targets)),
            "missing_required_targets": required_targets_for_integrity,
            "selection_count": len(sorted(set(selected_pytest_targets + fallback_pytest_targets))),
            "minimum_selection_threshold": 1,
            "threshold_satisfied": False,
            "impacted_surface_count": len(detection.changed_paths),
            "selection_integrity_decision": "BLOCK",
            "blocking_reasons": ["PYTEST_SELECTION_ARTIFACT_INVALID"],
            "generated_at": _utc_now(),
            "source_commit_sha": selection_provenance["source_commit_sha"],
            "source_head_ref": selection_provenance["source_head_ref"],
            "workflow_run_id": selection_provenance["workflow_run_id"],
            "producer_script": selection_provenance["producer_script"],
            "produced_at": selection_provenance["produced_at"],
            "source_pytest_execution_record_ref": selection_provenance["source_pytest_execution_record_ref"],
            "source_pytest_execution_record_hash": selection_provenance["source_pytest_execution_record_hash"],
        }
        report["pytest_selection_integrity"]["artifact_hash"] = _hash_payload(report["pytest_selection_integrity"])
    if report.get("pytest_selection_integrity", {}).get("artifact_hash") in {"", None}:
        report["pytest_selection_integrity"]["artifact_hash"] = _hash_payload(report["pytest_selection_integrity"])
    selection_integrity_path = output_dir / "pytest_selection_integrity_result.json"
    if selection_integrity_valid:
        selection_integrity_path.write_text(json.dumps(report["pytest_selection_integrity"], indent=2) + "\n", encoding="utf-8")
        report["pytest_selection_integrity_result_ref"] = _CANONICAL_PYTEST_SELECTION_REF
    else:
        report["pytest_selection_integrity_result_ref"] = _CANONICAL_PYTEST_SELECTION_REF

    if is_pull_request_event:
        if not bool(pytest_execution_record.get("executed", False)):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_EXECUTION_RECORD_REQUIRED"])
            )
            report["recommended_repair_areas"] = sorted(
                set(report.get("recommended_repair_areas", []) + ["restore canonical PR pytest execution path"])
            )
        if not report["pytest_execution"]["selected_targets"] and not report["pytest_execution"]["fallback_targets"]:
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_SELECTED_TARGETS_EMPTY"])
            )
            report["recommended_repair_areas"] = sorted(
                set(report.get("recommended_repair_areas", []) + ["restore deterministic PR pytest target selection"])
            )

        selection_integrity = report.get("pytest_selection_integrity") or {}
        selection_reasons = [str(item) for item in (selection_integrity.get("blocking_reasons") or []) if isinstance(item, str)]
        if str(selection_integrity.get("selection_integrity_decision") or "BLOCK") != "ALLOW":
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + selection_reasons + ["PR_PYTEST_SELECTION_INTEGRITY_REQUIRED"])
            )
            report["recommended_repair_areas"] = sorted(
                set(report.get("recommended_repair_areas", []) + ["restore deterministic PR pytest selection integrity coverage"])
            )
        execution_ref = str(report.get("pytest_execution_record_ref") or "").strip()
        selection_ref = str(report.get("pytest_selection_integrity_result_ref") or "").strip()
        if not _validate_canonical_ref_path(ref=execution_ref, expected_suffix=_CANONICAL_PYTEST_EXECUTION_REF):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_EXECUTION_REF_NON_CANONICAL"])
            )
        if not _validate_canonical_ref_path(ref=selection_ref, expected_suffix=_CANONICAL_PYTEST_SELECTION_REF):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_SELECTION_REF_NON_CANONICAL"])
            )
        execution_provenance_fields = [
            "source_commit_sha",
            "source_head_ref",
            "workflow_run_id",
            "producer_script",
            "produced_at",
            "artifact_hash",
        ]
        if any(not str(pytest_execution_record.get(field) or "").strip() for field in execution_provenance_fields):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_EXECUTION_PROVENANCE_MISSING"])
            )
        selection_provenance_fields = execution_provenance_fields + [
            "source_pytest_execution_record_ref",
            "source_pytest_execution_record_hash",
        ]
        if any(not str(selection_integrity.get(field) or "").strip() for field in selection_provenance_fields):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_SELECTION_PROVENANCE_MISSING"])
            )
        if str(selection_integrity.get("source_pytest_execution_record_ref") or "") != execution_ref:
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_PROVENANCE_LINK_MISMATCH"])
            )
        if str(selection_integrity.get("source_pytest_execution_record_hash") or "") != str(pytest_execution_record.get("artifact_hash") or ""):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_PROVENANCE_HASH_MISMATCH"])
            )
        if str(selection_integrity.get("source_commit_sha") or "") != str(pytest_execution_record.get("source_commit_sha") or ""):
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["PR_PYTEST_PROVENANCE_COMMIT_MISMATCH"])
            )
        detection_mode = str(report.get("changed_path_detection", {}).get("changed_path_detection_mode", ""))
        degraded_modes = {
            "local_workspace_status",
            "working_tree_diff_head",
            "degraded_full_governed_scan",
            "detection_failed_no_governed_paths",
            "base_to_current_head_fallback",
            "github_ref_context_fallback",
        }
        if detection_mode in degraded_modes:
            report["status"] = "failed"
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["DEGRADED_REF_RESOLUTION_PR_BLOCK"])
            )
            if detection_mode != "degraded_full_governed_scan":
                report["invariant_violations"] = sorted(
                    set(
                        report.get("invariant_violations", [])
                        + ["NON_EXHAUSTIVE_GOVERNED_PATH_RESOLUTION", "GOVERNED_SURFACE_DIFF_INCOMPLETE"]
                    )
                )

    if report["control_surface_enforcement"] and report["control_surface_enforcement"].get("enforcement_status") == "BLOCK":
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(
                report.get("invariant_violations", [])
                + report["control_surface_enforcement"].get("blocking_reasons", [])
            )
        )
        report["recommended_repair_areas"] = sorted(
            set(report["recommended_repair_areas"] + ["control surface manifest required coverage mappings"])
        )
    report["control_surface_gap_status"] = control_surface_gap_bridge["status"]
    report["control_surface_gap_result_ref"] = control_surface_gap_bridge["gap_result_path"]
    report["pqx_gap_work_items_ref"] = control_surface_gap_bridge["pqx_work_items_path"]
    report["control_surface_gap_blocking"] = control_surface_gap_bridge["blocking"]
    if control_surface_gap_bridge["blocking"]:
        report["status"] = "failed"
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["control surface gap to PQX triage bridge"])
        )
        if control_surface_gap_bridge["conversion_error"]:
            report["invariant_violations"] = sorted(
                set(report.get("invariant_violations", []) + ["CONTROL_SURFACE_GAP_TO_PQX_CONVERSION_FAILED"])
            )
    if isinstance(pqx_execution_policy, dict) and str(pqx_execution_policy.get("status", "")).lower() == "block":
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(report.get("invariant_violations", []) + list(pqx_execution_policy.get("blocking_reasons", [])))
        )
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["default PQX execution policy enforcement"])
        )
    if system_registry_guard_result.get("status") == "fail":
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(report.get("invariant_violations", []) + list(system_registry_guard_result.get("normalized_reason_codes", [])))
        )
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["system registry ownership boundaries"])
        )
    if test_inventory_eval.blocking:
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(report.get("invariant_violations", []) + [str(test_inventory_eval.failure_class)])
        )
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["pytest discovery/collection inventory integrity gate"])
        )
    cohesion_decision = (trust_spine_cohesion or {}).get("overall_decision") if isinstance(trust_spine_cohesion, dict) else None
    report["trust_spine_evidence_cohesion"] = trust_spine_cohesion
    report["trust_spine_evidence_cohesion_ref"] = (
        trust_spine_cohesion.get("artifact_path") if isinstance(trust_spine_cohesion, dict) else None
    )
    if cohesion_decision == "BLOCK":
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(report.get("invariant_violations", []) + (trust_spine_cohesion.get("blocking_reasons") or []))
        )
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["trust-spine evidence cohesion"])
        )
    pytest_execution = report.get("pytest_execution", {})
    pytest_execution_count = int(pytest_execution.get("pytest_execution_count", 0)) if isinstance(pytest_execution, dict) else 0
    if is_pull_request_event and not str(report.get("pytest_selection_integrity_result_ref") or "").strip():
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(report.get("invariant_violations", []) + ["PYTEST_SELECTION_ARTIFACT_MISSING", "PR_PYTEST_SELECTION_INTEGRITY_REQUIRED"])
        )

    if is_pull_request_event and report.get("status") == "passed" and pytest_execution_count < 1:
        report["status"] = "failed"
        report["invariant_violations"] = sorted(
            set(
                report.get("invariant_violations", [])
                + ["PR_PYTEST_EXECUTION_REQUIRED", "PREFLIGHT_PASS_WITHOUT_PYTEST_EXECUTION"]
            )
        )
        report["recommended_repair_areas"] = sorted(
            set(report.get("recommended_repair_areas", []) + ["run governed PR pytest execution before ALLOW"])
        )

    control_signal = map_preflight_control_signal(
        report=report,
        hardening_flow=bool(args.hardening_flow),
        event_name=str(ref_context.event_name or ""),
    )
    decision = str(control_signal.get("strategy_gate_decision", "BLOCK"))
    report["status"] = "failed" if decision in {"BLOCK", "FREEZE"} else "passed"
    classification_exception: str | None = None
    if report["status"] == "failed":
        try:
            normalized = normalize_preflight_failure(report)
            failure_class = normalized["failure_class"]
            reason_codes = list(report.get("invariant_violations", []))
            report["normalized_failure"] = normalized
        except Exception as exc:  # defensive fail-closed annotation only
            normalized = {
                "failure_class": "internal_preflight_error",
                "signals": {},
                "repairable": False,
            }
            failure_class, reason_codes = "internal_preflight_error", ["preflight_runtime_exception"]
            report["normalized_failure"] = normalized
            classification_exception = str(exc)
        report["root_cause_classification"] = {
            "failure_class": failure_class,
            "reason_codes": reason_codes,
        }
        assert report["root_cause_classification"]["failure_class"] in {
            "schema_violation",
            "contract_mismatch",
            "test_inventory_regression",
            "control_surface_gap",
            "downstream_test_failure",
            "internal_preflight_error",
        }
        if report["normalized_failure"]["repairable"]:
            report["repair_eligibility_rationale"] = "auto_repair_allowed: deterministic bounded failure classification"
        else:
            report["repair_eligibility_rationale"] = "escalation_required: non-repairable policy or unbounded runtime failure"
        report["secondary_exception"] = classification_exception
    else:
        report["root_cause_classification"] = {"failure_class": "none", "reason_codes": []}
        report["repair_eligibility_rationale"] = "not_applicable: preflight passed"
        report["secondary_exception"] = None

    json_path = output_dir / "contract_preflight_report.json"
    md_path = output_dir / "contract_preflight_report.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    preflight_artifact = build_preflight_result_artifact(
        report=report,
        json_report_path=json_path,
        markdown_report_path=md_path,
        hardening_flow=bool(args.hardening_flow),
    )
    preflight_schema = load_schema("contract_preflight_result_artifact")
    Draft202012Validator(preflight_schema, format_checker=FormatChecker()).validate(preflight_artifact)
    preflight_artifact_path = output_dir / "contract_preflight_result_artifact.json"
    preflight_artifact_path.write_text(json.dumps(preflight_artifact, indent=2) + "\n", encoding="utf-8")
    block_bundle_paths: dict[str, str] = {}
    if preflight_artifact["control_signal"]["strategy_gate_decision"] in {"BLOCK", "FREEZE"}:
        bundle = emit_preflight_block_bundle(
            report=report,
            preflight_artifact=preflight_artifact,
            output_dir=output_dir,
        )
        diagnosis_path = output_dir / "preflight_block_diagnosis_record.json"
        diagnosis_record = bundle["diagnosis"]
        if is_pytest_selection_observation_class(str(diagnosis_record.get("failure_class") or "")):
            diagnosis_record["pytest_selection_diagnostic"] = build_pytest_selection_observation(
                report=report,
                policy_path=_PYTEST_SELECTION_INTEGRITY_POLICY_PATH,
            )
            validate_artifact(diagnosis_record, "preflight_block_diagnosis_record")
            diagnosis_path.write_text(json.dumps(diagnosis_record, indent=2) + "\n", encoding="utf-8")
        block_bundle_paths = {
            "preflight_block_diagnosis_record": str(diagnosis_path),
            "preflight_repair_plan_record": str(output_dir / "preflight_repair_plan_record.json"),
            "failure_repair_candidate_artifact": str(output_dir / "failure_repair_candidate_artifact.json"),
            "preflight_repair_result_record": str(output_dir / "preflight_repair_result_record.json"),
            "failure_class": str(diagnosis_record["failure_class"]),
            "eligibility_decision": str(bundle["plan"]["eligibility_decision"]),
        }
        escalation_path = output_dir / "preflight_human_escalation_record.json"
        if escalation_path.exists():
            block_bundle_paths["preflight_human_escalation_record"] = str(escalation_path)

    print(
        json.dumps(
            {
                "status": report["status"],
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "preflight_artifact": str(preflight_artifact_path),
                "strategy_gate_decision": preflight_artifact["control_signal"]["strategy_gate_decision"],
                "block_bundle": block_bundle_paths,
            },
            indent=2,
        )
    )

    return 2 if preflight_artifact["control_signal"]["strategy_gate_decision"] in {"BLOCK", "FREEZE"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
