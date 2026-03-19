"""
Adversarial Dataset — spectrum_systems/modules/evaluation/adversarial_dataset.py

Loads adversarial test cases from ``data/adversarial_cases/``.

Adversarial cases use a simpler directory structure than golden cases:
they do not have ``input/`` or ``expected_outputs/`` sub-directories, and
they carry additional metadata fields (``adversarial_type``,
``expected_difficulty``, ``expected_failure_modes``).

Directory layout::

    data/adversarial_cases/<case_id>/
        transcript.txt              # required
        metadata.json               # required (includes adversarial fields)
        reference_minutes.json      # optional (may be intentionally wrong)

Design principles
-----------------
- No silent fallback: missing required files raise ``AdversarialCaseError``.
- Empty expected outputs are used when loading into EvalRunner so that
  the engine runs on real adversarial input with no pre-baked answers.
- Adversarial metadata is preserved alongside the eval-compatible case
  object for downstream failure-flag computation.
- Do not sanitize adversarial inputs.

Public API
----------
AdversarialCase
    Typed container for a single adversarial test case.

AdversarialDataset
    Collection of AdversarialCase instances.

load_all_adversarial_cases(root_dir) -> AdversarialDataset
load_adversarial_case(case_id, root_dir) -> AdversarialCase
to_golden_case(adversarial_case) -> GoldenCase
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from spectrum_systems.modules.evaluation.golden_dataset import GoldenCase


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AdversarialCaseError(Exception):
    """Raised when an adversarial case directory has an invalid structure."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_ADVERSARIAL_TYPES = frozenset({
    "missing_decisions",
    "contradictory_decisions",
    "ambiguous_language",
    "duplicate_decisions",
    "noisy_transcript",
    "truncated_transcript",
    "overconfident_reference_minutes",
    "mixed_topics",
    "sparse_content",
    "redundant_repetition",
})

_VALID_DIFFICULTIES = frozenset({"easy", "medium", "hard"})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AdversarialCase:
    """A single adversarial test case.

    Attributes
    ----------
    case_id:
        Unique identifier derived from the case directory name.
    domain:
        Domain tag (e.g., ``"3.5ghz"``).
    adversarial_type:
        Category of failure mode being tested.
    expected_difficulty:
        Expected difficulty level: ``"easy"``, ``"medium"``, or ``"hard"``.
    expected_failure_modes:
        List of failure modes this case is designed to trigger.
    notes:
        Human-readable notes about this case.
    transcript:
        Raw transcript text (required).
    reference_minutes:
        Optional reference minutes dict (may be intentionally wrong).
    case_dir:
        Absolute path to the case directory.
    """

    case_id: str
    domain: str
    adversarial_type: str
    expected_difficulty: str
    expected_failure_modes: List[str]
    notes: str
    transcript: str
    reference_minutes: Optional[Dict[str, Any]]
    case_dir: Path


@dataclass
class AdversarialDataset:
    """Collection of AdversarialCase instances.

    Attributes
    ----------
    cases:
        List of loaded AdversarialCase instances, sorted by ``case_id``.
    root_dir:
        Absolute path to the ``data/adversarial_cases/`` directory.
    """

    cases: List[AdversarialCase] = field(default_factory=list)
    root_dir: Optional[Path] = None

    def __len__(self) -> int:
        return len(self.cases)

    def case_ids(self) -> List[str]:
        """Return sorted list of all case IDs."""
        return sorted(c.case_id for c in self.cases)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def load_adversarial_case(case_id: str, root_dir: Path) -> AdversarialCase:
    """Load a single adversarial case by ID.

    Parameters
    ----------
    case_id:
        The case directory name / identifier.
    root_dir:
        Path to the ``data/adversarial_cases/`` root directory.

    Returns
    -------
    AdversarialCase

    Raises
    ------
    AdversarialCaseError
        If the case directory is missing, structurally invalid, or
        contains unparseable files.
    """
    case_dir = root_dir / case_id
    errors = _validate_adversarial_case_structure(case_dir)
    if errors:
        raise AdversarialCaseError(
            f"Adversarial case '{case_id}' has structural errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    metadata: Dict[str, Any] = json.loads(
        (case_dir / "metadata.json").read_text(encoding="utf-8")
    )
    transcript = (case_dir / "transcript.txt").read_text(encoding="utf-8")

    ref_minutes: Optional[Dict[str, Any]] = None
    ref_path = case_dir / "reference_minutes.json"
    if ref_path.exists():
        try:
            ref_minutes = json.loads(ref_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AdversarialCaseError(
                f"Failed to parse reference_minutes.json for '{case_id}': {exc}"
            ) from exc

    return AdversarialCase(
        case_id=metadata["case_id"],
        domain=metadata.get("domain", "unknown"),
        adversarial_type=metadata["adversarial_type"],
        expected_difficulty=metadata["expected_difficulty"],
        expected_failure_modes=metadata.get("expected_failure_modes", []),
        notes=metadata.get("notes", ""),
        transcript=transcript,
        reference_minutes=ref_minutes,
        case_dir=case_dir,
    )


def load_all_adversarial_cases(root_dir: Path) -> AdversarialDataset:
    """Load all adversarial cases from the given root directory.

    Parameters
    ----------
    root_dir:
        Path to ``data/adversarial_cases/``.

    Returns
    -------
    AdversarialDataset
        All cases sorted by ``case_id``.

    Raises
    ------
    AdversarialCaseError
        If the root directory does not exist or any case fails validation.
    """
    if not root_dir.is_dir():
        raise AdversarialCaseError(
            f"Adversarial cases root directory does not exist: {root_dir}"
        )

    case_dirs = sorted(p for p in root_dir.iterdir() if p.is_dir())
    cases: List[AdversarialCase] = []
    for case_dir in case_dirs:
        cases.append(load_adversarial_case(case_dir.name, root_dir))

    return AdversarialDataset(cases=cases, root_dir=root_dir)


def to_golden_case(adv_case: AdversarialCase) -> GoldenCase:
    """Convert an ``AdversarialCase`` to a ``GoldenCase`` for use with EvalRunner.

    Expected outputs are all empty lists because adversarial cases have no
    reference answers.  Scores from EvalRunner will reflect the gap between
    what the engine extracts and the (empty) golden baseline.

    Parameters
    ----------
    adv_case:
        Adversarial case to convert.

    Returns
    -------
    GoldenCase
        Compatible with ``EvalRunner.run_case``.
    """
    return GoldenCase(
        case_id=adv_case.case_id,
        domain=adv_case.domain,
        difficulty=adv_case.expected_difficulty,
        notes=adv_case.notes,
        transcript=adv_case.transcript,
        slides_path=None,
        expected_decisions=[],
        expected_action_items=[],
        expected_gaps=[],
        expected_contradictions=[],
        expected_working_paper_sections=None,
        case_dir=adv_case.case_dir,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_adversarial_case_structure(case_dir: Path) -> List[str]:
    """Validate the directory structure of a single adversarial case.

    Returns a list of error messages.  An empty list means the structure is
    valid.
    """
    errors: List[str] = []

    if not case_dir.is_dir():
        errors.append(f"Case directory does not exist: {case_dir}")
        return errors

    # transcript.txt (at root, not under input/)
    transcript_path = case_dir / "transcript.txt"
    if not transcript_path.exists():
        errors.append(f"Missing transcript.txt in {case_dir}")

    # metadata.json
    metadata_path = case_dir / "metadata.json"
    if not metadata_path.exists():
        errors.append(f"Missing metadata.json in {case_dir}")
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for required_field in ("case_id", "adversarial_type", "expected_difficulty"):
                if required_field not in metadata:
                    errors.append(
                        f"metadata.json missing required field '{required_field}' in {case_dir}"
                    )
            adv_type = metadata.get("adversarial_type", "")
            if adv_type not in _VALID_ADVERSARIAL_TYPES:
                errors.append(
                    f"metadata.json has unknown adversarial_type '{adv_type}' in {case_dir}; "
                    f"must be one of {sorted(_VALID_ADVERSARIAL_TYPES)}"
                )
            difficulty = metadata.get("expected_difficulty", "")
            if difficulty not in _VALID_DIFFICULTIES:
                errors.append(
                    f"metadata.json has invalid expected_difficulty '{difficulty}' in {case_dir}; "
                    f"must be one of {sorted(_VALID_DIFFICULTIES)}"
                )
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Failed to parse metadata.json in {case_dir}: {exc}")

    return errors
