"""HS-18 glossary registry loading and canonical term selection.

Narrow deterministic governance layer:
- strict schema validation for every glossary entry
- duplicate/ambiguous active-definition rejection
- exact-only canonical term matching (no fuzzy behavior)
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from spectrum_systems.contracts import load_schema


class GlossaryRegistryError(RuntimeError):
    """Fail-closed glossary registry/canonicalization error."""


def _canonical_requested_term(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise GlossaryRegistryError("glossary term reference must not be blank")
        return {
            "requested_term": text,
            "term_id": None,
            "canonical_term": text,
            "domain_scope": None,
            "required": True,
            "reference_mode": "text_exact",
        }

    if not isinstance(raw, Mapping):
        raise GlossaryRegistryError("glossary term reference must be a string or object")

    term_id = str(raw.get("term_id") or "").strip() or None
    canonical_term = str(raw.get("canonical_term") or "").strip() or None
    requested_term = str(raw.get("requested_term") or canonical_term or term_id or "").strip()
    domain_scope = str(raw.get("domain_scope") or "").strip() or None
    required = bool(raw.get("required", True))

    if not requested_term:
        raise GlossaryRegistryError("glossary term reference missing term text")
    if not term_id and not canonical_term:
        raise GlossaryRegistryError(
            "glossary term reference must include term_id or canonical_term for explicit canonicalization"
        )

    return {
        "requested_term": requested_term,
        "term_id": term_id,
        "canonical_term": canonical_term,
        "domain_scope": domain_scope,
        "required": required,
        "reference_mode": "explicit",
    }


def load_glossary_registry(entries: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    schema = load_schema("glossary_entry")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    normalized: List[Dict[str, Any]] = []
    for idx, entry in enumerate(entries):
        try:
            validator.validate(entry)
        except ValidationError as exc:
            raise GlossaryRegistryError(
                f"invalid glossary entry at index {idx}: {exc.message}"
            ) from exc
        normalized.append(deepcopy(entry))

    active_by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    active_by_term_text: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    for entry in normalized:
        if entry["status"] != "approved":
            continue
        key = (entry["term_id"], entry["domain_scope"])
        active_by_key.setdefault(key, []).append(entry)

        text_key = (entry["canonical_term"], entry["domain_scope"])
        active_by_term_text.setdefault(text_key, []).append(entry)

    for key, rows in active_by_key.items():
        if len(rows) > 1:
            raise GlossaryRegistryError(
                "duplicate active definitions detected for "
                f"term_id={key[0]!r} domain_scope={key[1]!r}"
            )

    for key, rows in active_by_term_text.items():
        term_ids = {row["term_id"] for row in rows}
        if len(term_ids) > 1:
            raise GlossaryRegistryError(
                "ambiguous active definitions detected for canonical_term="
                f"{key[0]!r} domain_scope={key[1]!r}"
            )

    return sorted(
        normalized,
        key=lambda row: (
            row["domain_scope"],
            row["term_id"],
            row["version"],
            row["glossary_entry_id"],
        ),
    )


def select_glossary_entries(
    registry_entries: Sequence[Dict[str, Any]],
    requested_terms: Sequence[Any],
    *,
    default_domain_scope: str,
    allow_deprecated: bool = False,
    fail_on_missing_required: bool = True,
) -> Dict[str, Any]:
    registry = load_glossary_registry(registry_entries)

    entries_by_term_id: Dict[Tuple[str, str], Dict[str, Any]] = {}
    entries_by_canonical_text: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for entry in registry:
        key = (entry["term_id"], entry["domain_scope"])
        if key not in entries_by_term_id:
            entries_by_term_id[key] = entry

        text_key = (entry["canonical_term"], entry["domain_scope"])
        if text_key in entries_by_canonical_text:
            if (
                entries_by_canonical_text[text_key]["status"] == "approved"
                and entry["status"] == "approved"
            ):
                raise GlossaryRegistryError(
                    "ambiguous active definitions detected for canonical_term="
                    f"{entry['canonical_term']!r} domain_scope={entry['domain_scope']!r}"
                )
        else:
            entries_by_canonical_text[text_key] = entry

    selected: List[Dict[str, Any]] = []
    unresolved_terms: List[str] = []

    for raw in requested_terms:
        requested = _canonical_requested_term(raw)
        scope = requested["domain_scope"] or default_domain_scope

        candidate = None
        if requested["term_id"]:
            candidate = entries_by_term_id.get((requested["term_id"], scope))
        elif requested["canonical_term"]:
            candidate = entries_by_canonical_text.get((requested["canonical_term"], scope))

        if candidate is None and requested["reference_mode"] == "text_exact":
            candidate = entries_by_canonical_text.get((requested["requested_term"], scope))

        if candidate is None:
            unresolved_terms.append(f"{requested['requested_term']}@{scope}")
            continue

        if candidate["status"] == "deprecated" and not allow_deprecated:
            raise GlossaryRegistryError(
                "deprecated glossary entry selection blocked for "
                f"term_id={candidate['term_id']!r} domain_scope={candidate['domain_scope']!r}"
            )

        selected.append(candidate)

    if unresolved_terms and fail_on_missing_required:
        raise GlossaryRegistryError(
            "missing required canonical glossary definitions: " + ", ".join(sorted(unresolved_terms))
        )

    unique_selected = {
        (entry["glossary_entry_id"], entry["term_id"], entry["domain_scope"], entry["version"]): deepcopy(entry)
        for entry in selected
    }
    ordered_selected = [
        unique_selected[key]
        for key in sorted(unique_selected.keys(), key=lambda value: (value[2], value[1], value[3], value[0]))
    ]

    return {
        "selected_entries": ordered_selected,
        "selected_glossary_entry_ids": [row["glossary_entry_id"] for row in ordered_selected],
        "unresolved_terms": sorted(set(unresolved_terms)),
        "match_mode": "exact",
        "selection_mode": "explicit_then_exact_text",
    }


__all__ = [
    "GlossaryRegistryError",
    "load_glossary_registry",
    "select_glossary_entries",
]
