"""
Golden Dataset — spectrum_systems/modules/evaluation/golden_dataset.py

Loads and validates curated golden test cases used for evaluation and
regression testing of the meeting-minutes → working-paper pipeline.

Each golden case is a directory under ``data/golden_cases/`` with the
following structure::

    data/golden_cases/<case_id>/
        metadata.json                  # case_id, domain, difficulty, notes
        input/
            transcript.txt             # required
            slides.pdf                 # optional
        expected_outputs/
            decisions.json             # required
            action_items.json          # required
            gaps.json                  # required
            contradictions.json        # required
            working_paper_sections.json  # optional

Design principles
-----------------
- No silent fallback: missing required files raise ``GoldenCaseError``.
- All case structures are validated on load.
- Deterministic: case loading order is sorted by case_id.
- No external dependencies beyond the Python standard library.

Public API
----------
GoldenCase
    Typed container for a single golden test case.

GoldenDataset
    Collection of GoldenCase instances with bulk-load helpers.

load_all_cases(root_dir) -> GoldenDataset
load_case(case_id, root_dir) -> GoldenCase
validate_case_structure(case_dir) -> list[str]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class GoldenCaseError(Exception):
    """Raised when a golden case directory has an invalid or incomplete structure."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_INPUT_FILES = ["transcript.txt"]
_REQUIRED_OUTPUT_FILES = ["decisions.json", "action_items.json", "gaps.json", "contradictions.json"]
_OPTIONAL_INPUT_FILES = ["slides.pdf"]
_OPTIONAL_OUTPUT_FILES = ["working_paper_sections.json"]
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GoldenCase:
    """A single curated golden test case.

    Attributes
    ----------
    case_id:
        Unique identifier derived from the case directory name.
    domain:
        Domain tag (e.g., ``"7ghz"``).
    difficulty:
        Difficulty level: ``"easy"``, ``"medium"``, or ``"hard"``.
    notes:
        Human-readable notes about the case.
    transcript:
        Raw transcript text (required).
    slides_path:
        Absolute path to the optional slides PDF, or ``None``.
    expected_decisions:
        Expected decisions list parsed from ``decisions.json``.
    expected_action_items:
        Expected action items list parsed from ``action_items.json``.
    expected_gaps:
        Expected gaps list parsed from ``gaps.json``.
    expected_contradictions:
        Expected contradictions list parsed from ``contradictions.json``.
    expected_working_paper_sections:
        Optional expected working paper sections.
    case_dir:
        Absolute path to the case directory.
    """

    case_id: str
    domain: str
    difficulty: str
    notes: str
    transcript: str
    slides_path: Optional[Path]
    expected_decisions: List[Any]
    expected_action_items: List[Any]
    expected_gaps: List[Any]
    expected_contradictions: List[Any]
    expected_working_paper_sections: Optional[List[Any]]
    case_dir: Path

    def expected_outputs(self) -> Dict[str, Any]:
        """Return all expected outputs as a single dict."""
        result: Dict[str, Any] = {
            "decisions": self.expected_decisions,
            "action_items": self.expected_action_items,
            "gaps": self.expected_gaps,
            "contradictions": self.expected_contradictions,
        }
        if self.expected_working_paper_sections is not None:
            result["working_paper_sections"] = self.expected_working_paper_sections
        return result


@dataclass
class GoldenDataset:
    """Collection of GoldenCase instances.

    Attributes
    ----------
    cases:
        List of loaded GoldenCase instances, sorted by ``case_id``.
    root_dir:
        Absolute path to the ``data/golden_cases/`` directory.
    """

    cases: List[GoldenCase] = field(default_factory=list)
    root_dir: Optional[Path] = None

    def __len__(self) -> int:
        return len(self.cases)

    def get_case(self, case_id: str) -> GoldenCase:
        """Return the case with the given ``case_id``.

        Raises
        ------
        KeyError
            If no case with that ID is found.
        """
        for case in self.cases:
            if case.case_id == case_id:
                return case
        raise KeyError(f"No golden case found with case_id='{case_id}'")

    def case_ids(self) -> List[str]:
        """Return sorted list of all case IDs."""
        return sorted(c.case_id for c in self.cases)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def validate_case_structure(case_dir: Path) -> List[str]:
    """Validate the directory structure of a single golden case.

    Parameters
    ----------
    case_dir:
        Path to the case directory (e.g., ``data/golden_cases/case_001``).

    Returns
    -------
    list[str]
        List of error messages.  An empty list means the structure is valid.
    """
    errors: List[str] = []

    if not case_dir.is_dir():
        errors.append(f"Case directory does not exist: {case_dir}")
        return errors

    # metadata.json
    metadata_path = case_dir / "metadata.json"
    if not metadata_path.exists():
        errors.append(f"Missing metadata.json in {case_dir}")
    else:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            for field_name in ("case_id", "domain", "difficulty", "notes"):
                if field_name not in metadata:
                    errors.append(f"metadata.json missing required field '{field_name}' in {case_dir}")
            difficulty = metadata.get("difficulty", "")
            if difficulty not in _VALID_DIFFICULTIES:
                errors.append(
                    f"metadata.json has invalid difficulty '{difficulty}' in {case_dir}; "
                    f"must be one of {sorted(_VALID_DIFFICULTIES)}"
                )
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"Failed to parse metadata.json in {case_dir}: {exc}")

    # input/ directory
    input_dir = case_dir / "input"
    if not input_dir.is_dir():
        errors.append(f"Missing input/ directory in {case_dir}")
    else:
        for fname in _REQUIRED_INPUT_FILES:
            if not (input_dir / fname).exists():
                errors.append(f"Missing required input file '{fname}' in {input_dir}")

    # expected_outputs/ directory
    outputs_dir = case_dir / "expected_outputs"
    if not outputs_dir.is_dir():
        errors.append(f"Missing expected_outputs/ directory in {case_dir}")
    else:
        for fname in _REQUIRED_OUTPUT_FILES:
            fpath = outputs_dir / fname
            if not fpath.exists():
                errors.append(f"Missing required output file '{fname}' in {outputs_dir}")
            else:
                try:
                    json.loads(fpath.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"Invalid JSON in '{fname}' in {outputs_dir}: {exc}")

    return errors


def load_case(case_id: str, root_dir: Path) -> GoldenCase:
    """Load a single golden case by ID.

    Parameters
    ----------
    case_id:
        The case directory name / identifier.
    root_dir:
        Path to the ``data/golden_cases/`` root directory.

    Returns
    -------
    GoldenCase

    Raises
    ------
    GoldenCaseError
        If the case directory is missing, structurally invalid, or contains
        unparseable files.
    """
    case_dir = root_dir / case_id
    errors = validate_case_structure(case_dir)
    if errors:
        raise GoldenCaseError(
            f"Golden case '{case_id}' has structural errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Load metadata
    metadata: Dict[str, Any] = json.loads(
        (case_dir / "metadata.json").read_text(encoding="utf-8")
    )

    # Load transcript
    transcript = (case_dir / "input" / "transcript.txt").read_text(encoding="utf-8")

    # Optional slides
    slides_path_candidate = case_dir / "input" / "slides.pdf"
    slides_path: Optional[Path] = slides_path_candidate if slides_path_candidate.exists() else None

    # Load required expected outputs
    outputs_dir = case_dir / "expected_outputs"
    expected_decisions = _load_json_list(outputs_dir / "decisions.json", "decisions.json")
    expected_action_items = _load_json_list(outputs_dir / "action_items.json", "action_items.json")
    expected_gaps = _load_json_list(outputs_dir / "gaps.json", "gaps.json")
    expected_contradictions = _load_json_list(outputs_dir / "contradictions.json", "contradictions.json")

    # Optional working paper sections
    wp_sections_path = outputs_dir / "working_paper_sections.json"
    expected_working_paper_sections: Optional[List[Any]] = None
    if wp_sections_path.exists():
        expected_working_paper_sections = _load_json_list(wp_sections_path, "working_paper_sections.json")

    return GoldenCase(
        case_id=metadata["case_id"],
        domain=metadata["domain"],
        difficulty=metadata["difficulty"],
        notes=metadata.get("notes", ""),
        transcript=transcript,
        slides_path=slides_path,
        expected_decisions=expected_decisions,
        expected_action_items=expected_action_items,
        expected_gaps=expected_gaps,
        expected_contradictions=expected_contradictions,
        expected_working_paper_sections=expected_working_paper_sections,
        case_dir=case_dir,
    )


def load_all_cases(root_dir: Path) -> GoldenDataset:
    """Load all golden cases from the given root directory.

    Parameters
    ----------
    root_dir:
        Path to ``data/golden_cases/``.

    Returns
    -------
    GoldenDataset
        All cases sorted by ``case_id``.

    Raises
    ------
    GoldenCaseError
        If any case fails structural validation.
    """
    if not root_dir.is_dir():
        raise GoldenCaseError(f"Golden cases root directory does not exist: {root_dir}")

    case_dirs = sorted(p for p in root_dir.iterdir() if p.is_dir())
    cases: List[GoldenCase] = []
    for case_dir in case_dirs:
        cases.append(load_case(case_dir.name, root_dir))

    return GoldenDataset(cases=cases, root_dir=root_dir)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_json_list(path: Path, label: str) -> List[Any]:
    """Load a JSON file and return its top-level list.

    Raises ``GoldenCaseError`` if the file is not valid JSON or not a list.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise GoldenCaseError(f"Failed to load '{label}': {exc}") from exc
    if not isinstance(data, list):
        raise GoldenCaseError(
            f"Expected a JSON array in '{label}', got {type(data).__name__}"
        )
    return data
