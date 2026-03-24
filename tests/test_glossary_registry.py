from __future__ import annotations

import pytest

from spectrum_systems.modules.runtime.glossary_registry import (
    GlossaryRegistryError,
    load_glossary_registry,
    select_glossary_entries,
)


_BASE_ENTRY = {
    "artifact_type": "glossary_entry",
    "schema_version": "1.0.0",
    "glossary_entry_id": "gle-a2f8fbe34b21d991",
    "term_id": "sla",
    "canonical_term": "SLA",
    "definition": "Service Level Agreement.",
    "domain_scope": "runtime",
    "version": "v1.0.0",
    "status": "approved",
    "provenance_refs": ["src-1"],
    "created_at": "2026-03-24T00:00:00Z",
}


def test_registry_load_validates_schema() -> None:
    load_glossary_registry([dict(_BASE_ENTRY)])


def test_duplicate_active_term_rejected() -> None:
    entry2 = dict(_BASE_ENTRY)
    entry2["glossary_entry_id"] = "gle-b2f8fbe34b21d991"
    entry2["version"] = "v1.0.1"
    with pytest.raises(GlossaryRegistryError, match="duplicate active definitions"):
        load_glossary_registry([dict(_BASE_ENTRY), entry2])


def test_ambiguous_active_canonical_term_rejected() -> None:
    entry2 = dict(_BASE_ENTRY)
    entry2["term_id"] = "service_level"
    entry2["glossary_entry_id"] = "gle-c2f8fbe34b21d991"
    with pytest.raises(GlossaryRegistryError, match="ambiguous active definitions"):
        load_glossary_registry([dict(_BASE_ENTRY), entry2])


def test_missing_required_definition_fail_closed() -> None:
    with pytest.raises(GlossaryRegistryError, match="missing required canonical"):
        select_glossary_entries(
            [dict(_BASE_ENTRY)],
            ["RTO"],
            default_domain_scope="runtime",
            fail_on_missing_required=True,
        )


def test_exact_only_matching_no_fuzzy_behavior() -> None:
    with pytest.raises(GlossaryRegistryError, match="missing required canonical"):
        select_glossary_entries(
            [dict(_BASE_ENTRY)],
            ["slaa"],
            default_domain_scope="runtime",
            fail_on_missing_required=True,
        )


def test_deprecated_selection_blocked_by_default() -> None:
    deprecated = dict(_BASE_ENTRY)
    deprecated["status"] = "deprecated"
    with pytest.raises(GlossaryRegistryError, match="deprecated glossary entry selection blocked"):
        select_glossary_entries(
            [deprecated],
            [{"requested_term": "SLA", "term_id": "sla", "domain_scope": "runtime"}],
            default_domain_scope="runtime",
            fail_on_missing_required=True,
            allow_deprecated=False,
        )


def test_deterministic_selected_order() -> None:
    entry2 = dict(_BASE_ENTRY)
    entry2.update(
        {
            "glossary_entry_id": "gle-b2f8fbe34b21d991",
            "term_id": "rto",
            "canonical_term": "RTO",
        }
    )
    result = select_glossary_entries(
        [entry2, dict(_BASE_ENTRY)],
        [
            {"requested_term": "RTO", "term_id": "rto", "domain_scope": "runtime"},
            {"requested_term": "SLA", "term_id": "sla", "domain_scope": "runtime"},
        ],
        default_domain_scope="runtime",
    )
    assert result["selected_glossary_entry_ids"] == [
        "gle-b2f8fbe34b21d991",
        "gle-a2f8fbe34b21d991",
    ]
