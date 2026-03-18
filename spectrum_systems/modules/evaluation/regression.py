"""
Regression Harness — spectrum_systems/modules/evaluation/regression.py

Stores baseline evaluation results and compares current runs against them to
detect regressions.

Design principles
-----------------
- Baselines are stored as JSON files under ``data/eval_baselines/``.
- Thresholds are configurable via ``config/eval_config.yaml``.
- If a score drops below the baseline by more than the threshold → FAIL.
- No silent tolerance: regressions must be explicitly acknowledged or the
  run fails.
- No external dependencies beyond the Python standard library.

Public API
----------
BaselineRecord
    Stored baseline result for a single case.

RegressionResult
    Result of comparing a current run to a stored baseline.

RegressionHarness
    Manages baseline storage and comparison.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "structural_score": 0.05,
    "semantic_score": 0.05,
    "grounding_score": 0.05,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BaselineRecord:
    """Stored baseline result for a single evaluation case.

    Attributes
    ----------
    case_id:
        Identifier of the golden case.
    structural_score:
        Structural F1 score recorded in the baseline run.
    semantic_score:
        Semantic F1 score recorded in the baseline run.
    grounding_score:
        Grounding score recorded in the baseline run.
    recorded_at:
        ISO-8601 timestamp when the baseline was recorded.
    metadata:
        Arbitrary additional metadata stored with the baseline.
    """

    case_id: str
    structural_score: float
    semantic_score: float
    grounding_score: float
    recorded_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "structural_score": self.structural_score,
            "semantic_score": self.semantic_score,
            "grounding_score": self.grounding_score,
            "recorded_at": self.recorded_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineRecord":
        return cls(
            case_id=data["case_id"],
            structural_score=float(data["structural_score"]),
            semantic_score=float(data["semantic_score"]),
            grounding_score=float(data["grounding_score"]),
            recorded_at=data["recorded_at"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ScoreDelta:
    """Delta between current and baseline for a single score dimension.

    Attributes
    ----------
    dimension:
        Name of the score dimension (e.g., ``"structural_score"``).
    baseline:
        Baseline score value.
    current:
        Current run score value.
    delta:
        Current minus baseline (positive = improvement).
    threshold:
        Maximum permitted drop (negative delta) before this is a regression.
    is_regression:
        ``True`` if ``delta < -threshold``.
    """

    dimension: str
    baseline: float
    current: float
    delta: float
    threshold: float
    is_regression: bool


@dataclass
class RegressionResult:
    """Result of comparing a current run against a stored baseline.

    Attributes
    ----------
    case_id:
        Case identifier.
    has_baseline:
        ``True`` if a stored baseline exists for this case.
    regression_detected:
        ``True`` if any score dimension regressed beyond threshold.
    score_deltas:
        Per-dimension delta records.
    """

    case_id: str
    has_baseline: bool
    regression_detected: bool
    score_deltas: List[ScoreDelta] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class RegressionHarness:
    """Manages baseline storage and regression detection.

    Parameters
    ----------
    baselines_dir:
        Path to ``data/eval_baselines/``.
    thresholds:
        Per-dimension allowable drop before a regression is flagged.
        Keys: ``"structural_score"``, ``"semantic_score"``, ``"grounding_score"``.
        Defaults to ``0.05`` for all dimensions.
    """

    def __init__(
        self,
        baselines_dir: Path,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._baselines_dir = baselines_dir
        self._thresholds: Dict[str, float] = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def save_baseline(self, record: BaselineRecord) -> None:
        """Persist a baseline record to disk.

        Parameters
        ----------
        record:
            Baseline to save.  Overwrites any existing baseline for the case.
        """
        self._baselines_dir.mkdir(parents=True, exist_ok=True)
        path = self._baseline_path(record.case_id)
        path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")

    def load_baseline(self, case_id: str) -> Optional[BaselineRecord]:
        """Load a stored baseline for a case.

        Returns ``None`` if no baseline exists for the case.
        """
        path = self._baseline_path(case_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return BaselineRecord.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RegressionHarnessError(
                f"Failed to load baseline for case '{case_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def compare(
        self,
        case_id: str,
        structural_score: float,
        semantic_score: float,
        grounding_score: float,
    ) -> RegressionResult:
        """Compare current scores against the stored baseline.

        Parameters
        ----------
        case_id:
            Case identifier.
        structural_score:
            Current structural F1 score.
        semantic_score:
            Current semantic F1 score.
        grounding_score:
            Current grounding score.

        Returns
        -------
        RegressionResult
            If no baseline exists, ``has_baseline=False`` and
            ``regression_detected=False``.
        """
        baseline = self.load_baseline(case_id)
        if baseline is None:
            return RegressionResult(
                case_id=case_id,
                has_baseline=False,
                regression_detected=False,
            )

        current_scores = {
            "structural_score": structural_score,
            "semantic_score": semantic_score,
            "grounding_score": grounding_score,
        }
        baseline_scores = {
            "structural_score": baseline.structural_score,
            "semantic_score": baseline.semantic_score,
            "grounding_score": baseline.grounding_score,
        }

        score_deltas: List[ScoreDelta] = []
        regression_detected = False

        for dim in ("structural_score", "semantic_score", "grounding_score"):
            base_val = baseline_scores[dim]
            curr_val = current_scores[dim]
            delta = curr_val - base_val
            threshold = self._thresholds.get(dim, 0.05)
            is_regression = delta < -threshold
            if is_regression:
                regression_detected = True
            score_deltas.append(ScoreDelta(
                dimension=dim,
                baseline=base_val,
                current=curr_val,
                delta=delta,
                threshold=threshold,
                is_regression=is_regression,
            ))

        return RegressionResult(
            case_id=case_id,
            has_baseline=True,
            regression_detected=regression_detected,
            score_deltas=score_deltas,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _baseline_path(self, case_id: str) -> Path:
        return self._baselines_dir / f"{case_id}.json"


class RegressionHarnessError(Exception):
    """Raised when a baseline record cannot be loaded or is corrupt."""
