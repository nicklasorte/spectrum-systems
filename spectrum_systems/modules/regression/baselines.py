"""
Baseline Management — spectrum_systems/modules/regression/baselines.py

Governs storage and retrieval of named regression baselines.

Design principles
-----------------
- Baselines are stored as JSON under data/regression_baselines/{name}/.
- No silent overwrites: an explicit ``update=True`` flag is required.
- Metadata is a governed artifact that records provenance.
- No external dependencies beyond the Python standard library.

Public API
----------
BaselineManager
    Save, load, list, and describe named baselines.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASELINES_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "regression_baselines"
)


# ---------------------------------------------------------------------------
# BaselineManager
# ---------------------------------------------------------------------------


class BaselineManager:
    """Manages named regression baselines on disk.

    Parameters
    ----------
    baselines_dir:
        Root directory where baselines are stored.  Each baseline is
        stored in a subdirectory named after the baseline.
    """

    def __init__(self, baselines_dir: Optional[Path] = None) -> None:
        self._root = baselines_dir or _DEFAULT_BASELINES_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_baseline(
        self,
        name: str,
        eval_results: List[Dict[str, Any]],
        observability_records: List[Dict[str, Any]],
        *,
        metadata: Optional[Dict[str, Any]] = None,
        update: bool = False,
        notes: str = "",
    ) -> Path:
        """Persist a named baseline to disk.

        Parameters
        ----------
        name:
            Baseline name (alphanumeric, hyphens, underscores).
        eval_results:
            List of serialised EvalResult dicts.
        observability_records:
            List of serialised ObservabilityRecord dicts.
        metadata:
            Optional additional metadata dict.  Standard fields are added
            automatically.
        update:
            Must be ``True`` to overwrite an existing baseline.  Raises
            ``BaselineExistsError`` if ``False`` and baseline already exists.
        notes:
            Human-readable notes to include in baseline metadata.

        Returns
        -------
        Path
            Directory where the baseline was written.
        """
        _validate_name(name)
        baseline_dir = self._root / name

        if baseline_dir.exists() and not update:
            raise BaselineExistsError(
                f"Baseline '{name}' already exists. "
                "Pass update=True to overwrite."
            )

        baseline_dir.mkdir(parents=True, exist_ok=True)

        # Build metadata
        meta: Dict[str, Any] = {
            "baseline_id": str(uuid.uuid4()),
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "golden_case_count": len(eval_results),
            "observability_record_count": len(observability_records),
            "notes": notes,
        }
        if metadata:
            meta.update(metadata)

        # Write files with stable ordering for deterministic comparisons
        _write_json(baseline_dir / "eval_results.json", eval_results)
        _write_json(baseline_dir / "observability_records.json", observability_records)
        _write_json(baseline_dir / "metadata.json", meta)

        return baseline_dir

    def load_baseline(self, name: str) -> Dict[str, Any]:
        """Load a named baseline from disk.

        Parameters
        ----------
        name:
            Baseline name.

        Returns
        -------
        dict
            Keys: eval_results, observability_records, metadata.

        Raises
        ------
        BaselineNotFoundError
            If no baseline with that name exists.
        BaselineLoadError
            If any file cannot be parsed.
        """
        baseline_dir = self._root / name
        if not baseline_dir.exists():
            raise BaselineNotFoundError(f"Baseline '{name}' not found at {baseline_dir}")

        return {
            "eval_results": _load_json(baseline_dir / "eval_results.json", name),
            "observability_records": _load_json(baseline_dir / "observability_records.json", name),
            "metadata": _load_json(baseline_dir / "metadata.json", name),
        }

    def list_baselines(self) -> List[str]:
        """Return sorted list of existing baseline names."""
        if not self._root.exists():
            return []
        return sorted(
            d.name
            for d in self._root.iterdir()
            if d.is_dir() and (d / "metadata.json").exists()
        )

    def describe_baseline(self, name: str) -> Dict[str, Any]:
        """Return the metadata for a named baseline.

        Raises
        ------
        BaselineNotFoundError
            If no baseline with that name exists.
        """
        baseline_dir = self._root / name
        meta_path = baseline_dir / "metadata.json"
        if not meta_path.exists():
            raise BaselineNotFoundError(f"Baseline '{name}' not found at {baseline_dir}")
        return _load_json(meta_path, name)

    def warn_if_determinism_mismatch(
        self,
        baseline_name: str,
        candidate_deterministic: bool,
    ) -> Optional[str]:
        """Return a warning string if determinism mode differs from baseline.

        Returns ``None`` if modes match or baseline metadata is unavailable.
        """
        try:
            meta = self.describe_baseline(baseline_name)
        except BaselineNotFoundError:
            return None

        baseline_deterministic = meta.get("deterministic_mode")
        if baseline_deterministic is None:
            return None

        if bool(baseline_deterministic) != candidate_deterministic:
            return (
                f"Determinism mode mismatch: baseline '{baseline_name}' was "
                f"{'deterministic' if baseline_deterministic else 'non-deterministic'}, "
                f"but candidate is "
                f"{'deterministic' if candidate_deterministic else 'non-deterministic'}. "
                "Results may not be directly comparable."
            )
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_name(name: str) -> None:
    import re
    if not re.match(r"^[A-Za-z0-9_-]+$", name):
        raise ValueError(
            f"Invalid baseline name '{name}'. "
            "Only alphanumeric characters, hyphens, and underscores are allowed."
        )


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_json(path: Path, name: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BaselineLoadError(
            f"Missing file for baseline '{name}': {path.name}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise BaselineLoadError(
            f"Corrupt JSON in baseline '{name}': {path.name} — {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class BaselineExistsError(Exception):
    """Raised when trying to overwrite a baseline without update=True."""


class BaselineNotFoundError(Exception):
    """Raised when a named baseline does not exist."""


class BaselineLoadError(Exception):
    """Raised when a baseline file cannot be loaded or parsed."""
