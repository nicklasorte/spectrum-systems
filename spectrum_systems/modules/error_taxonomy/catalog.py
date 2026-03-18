"""
Error Taxonomy Catalog — spectrum_systems/modules/error_taxonomy/catalog.py

Loads and exposes the canonical error taxonomy from the governed catalog file.

Design principles
-----------------
- One source of truth: the catalog JSON file is the authority.
- Catalog is validated against its JSON Schema before use.
- All lookups are by stable error_code strings.
- No external dependencies beyond the Python standard library and jsonschema.

Public API
----------
ErrorSubtype
    In-memory representation of one error subtype entry.

ErrorFamily
    In-memory representation of one error family.

ErrorTaxonomyCatalog
    Loaded, validated catalog with lookup helpers.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "config"
    / "error_taxonomy_catalog.json"
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "schemas"
    / "error_taxonomy_catalog.schema.json"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ErrorSubtype:
    """One error subtype entry from the taxonomy catalog.

    Attributes
    ----------
    error_code:
        Stable dot-notation code (e.g. ``GROUND.MISSING_REF``).
    error_name:
        Human-readable name.
    description:
        Description of this subtype.
    default_severity:
        Default severity: ``low``, ``medium``, ``high``, or ``critical``.
    detection_sources:
        List of systems that can detect this error.
    remediation_target:
        Primary remediation target system.
    examples:
        Illustrative examples.
    family_code:
        Parent family code (set when loaded from catalog).
    """

    error_code: str
    error_name: str
    description: str
    default_severity: str
    detection_sources: List[str]
    remediation_target: str
    examples: List[str]
    family_code: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], family_code: str = "") -> "ErrorSubtype":
        """Create from a catalog entry dict."""
        return cls(
            error_code=data["error_code"],
            error_name=data["error_name"],
            description=data["description"],
            default_severity=data["default_severity"],
            detection_sources=list(data["detection_sources"]),
            remediation_target=data["remediation_target"],
            examples=list(data.get("examples", [])),
            family_code=family_code,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "error_name": self.error_name,
            "description": self.description,
            "default_severity": self.default_severity,
            "detection_sources": self.detection_sources,
            "remediation_target": self.remediation_target,
            "examples": self.examples,
            "family_code": self.family_code,
        }


@dataclass
class ErrorFamily:
    """One error family from the taxonomy catalog.

    Attributes
    ----------
    family_code:
        Short uppercase code (e.g. ``GROUND``, ``EXTRACT``).
    family_name:
        Human-readable name.
    description:
        Description of this family.
    subtypes:
        List of error subtypes belonging to this family.
    """

    family_code: str
    family_name: str
    description: str
    subtypes: List[ErrorSubtype] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorFamily":
        """Create from a catalog entry dict."""
        family_code = data["family_code"]
        subtypes = [
            ErrorSubtype.from_dict(s, family_code=family_code)
            for s in data.get("subtypes", [])
        ]
        return cls(
            family_code=family_code,
            family_name=data["family_name"],
            description=data["description"],
            subtypes=subtypes,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_code": self.family_code,
            "family_name": self.family_name,
            "description": self.description,
            "subtypes": [s.to_dict() for s in self.subtypes],
        }


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

class ErrorTaxonomyCatalog:
    """Loaded and validated error taxonomy catalog.

    Parameters
    ----------
    data:
        Raw catalog dict (already loaded from JSON).
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = data
        self._families: List[ErrorFamily] = [
            ErrorFamily.from_dict(f) for f in data.get("error_families", [])
        ]
        # Build flat lookup index: error_code -> ErrorSubtype
        self._subtypes_by_code: Dict[str, ErrorSubtype] = {}
        self._families_by_code: Dict[str, ErrorFamily] = {}
        for family in self._families:
            self._families_by_code[family.family_code] = family
            for subtype in family.subtypes:
                self._subtypes_by_code[subtype.error_code] = subtype

    # --- Properties -------------------------------------------------------

    @property
    def taxonomy_id(self) -> str:
        return self._data["taxonomy_id"]

    @property
    def version(self) -> str:
        return self._data["version"]

    @property
    def description(self) -> str:
        return self._data["description"]

    # --- Lookup helpers ---------------------------------------------------

    def get_error(self, error_code: str) -> Optional[ErrorSubtype]:
        """Return the ``ErrorSubtype`` for a given code, or ``None``."""
        return self._subtypes_by_code.get(error_code)

    def get_family(self, family_code: str) -> Optional[ErrorFamily]:
        """Return the ``ErrorFamily`` for a given code, or ``None``."""
        return self._families_by_code.get(family_code)

    def list_families(self) -> List[ErrorFamily]:
        """Return all error families."""
        return list(self._families)

    def list_subtypes(self, family_code: Optional[str] = None) -> List[ErrorSubtype]:
        """Return all subtypes, optionally filtered to one family.

        Parameters
        ----------
        family_code:
            If provided, only return subtypes from that family.
        """
        if family_code is not None:
            family = self._families_by_code.get(family_code)
            return list(family.subtypes) if family else []
        return list(self._subtypes_by_code.values())

    def is_valid_code(self, error_code: str) -> bool:
        """Return True if ``error_code`` is known in the catalog."""
        return error_code in self._subtypes_by_code

    # --- Schema validation ------------------------------------------------

    def validate_against_schema(self) -> List[str]:
        """Validate the raw catalog data against its JSON Schema.

        Returns a list of validation error messages.  Empty list means valid.
        """
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        errors: List[str] = []
        validator = jsonschema.Draft202012Validator(schema)
        for err in validator.iter_errors(self._data):
            errors.append(err.message)
        return errors

    # --- Factory ----------------------------------------------------------

    @classmethod
    def load_catalog(cls, path: Optional[str] = None) -> "ErrorTaxonomyCatalog":
        """Load and return the taxonomy catalog.

        Parameters
        ----------
        path:
            Path to the catalog JSON file.  Defaults to the governed catalog
            at ``config/error_taxonomy_catalog.json``.
        """
        catalog_path = Path(path) if path else _CATALOG_PATH
        with open(catalog_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(data)


# ---------------------------------------------------------------------------
# Module-level default instance
# ---------------------------------------------------------------------------

def get_default_catalog() -> ErrorTaxonomyCatalog:
    """Return the default loaded taxonomy catalog."""
    return ErrorTaxonomyCatalog.load_catalog()
