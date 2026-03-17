"""
Review Orchestrator — spectrum_systems/modules/review_orchestrator.py

Assembles scoped review packs, renders Claude review prompts, and validates
review outputs against the review contract schema.

Design rules:
- Deterministic: no LLM calls, no network I/O.
- All paths resolved relative to the repository root.
- Manifest loading is strict: missing required fields raise ValueError.
- Prompt rendering uses stdlib string formatting (no external templating deps).
- Schema validation uses jsonschema (already a project dependency).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

# ─── Repo-relative paths ─────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFESTS_DIR = _REPO_ROOT / "reviews" / "manifests"
_FAILURE_MODES_REGISTRY = _REPO_ROOT / "reviews" / "failure_modes" / "failure_mode_registry.json"
_REVIEW_CONTRACT_SCHEMA = _REPO_ROOT / "standards" / "review-contract.schema.json"
_PROMPT_TEMPLATE = _REPO_ROOT / "templates" / "review" / "claude_review_prompt_template.md"

# Required fields in every review manifest.
_MANIFEST_REQUIRED_FIELDS = [
    "scope_id",
    "title",
    "purpose",
    "golden_path_role",
    "in_scope_files",
    "related_contracts",
    "related_tests",
    "related_design_docs",
    "upstream_dependencies",
    "downstream_consumers",
    "invariants",
    "known_edge_cases",
    "known_failure_modes",
]


# ─── Manifest loading ─────────────────────────────────────────────────────────

def load_review_manifest(scope_id: str) -> Dict[str, Any]:
    """Load and validate a review manifest by scope ID.

    Parameters
    ----------
    scope_id:
        Identifier matching the manifest filename prefix
        (e.g. ``"p_gap_detection"`` → ``reviews/manifests/p_gap_detection.review.json``).

    Returns
    -------
    dict
        Parsed manifest document.

    Raises
    ------
    FileNotFoundError
        If no manifest file exists for the given scope_id.
    ValueError
        If the manifest is missing required fields.
    """
    manifest_path = _MANIFESTS_DIR / f"{scope_id}.review.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Review manifest not found for scope '{scope_id}': {manifest_path}"
        )

    manifest: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    missing = [f for f in _MANIFEST_REQUIRED_FIELDS if f not in manifest]
    if missing:
        raise ValueError(
            f"Review manifest for '{scope_id}' is missing required fields: {missing}"
        )

    return manifest


# ─── Failure mode lookup ───────────────────────────────────────────────────────

def _load_failure_modes() -> Dict[str, Any]:
    """Load the failure mode registry, returning a dict keyed by failure mode id."""
    if not _FAILURE_MODES_REGISTRY.is_file():
        return {}
    registry: Dict[str, Any] = json.loads(
        _FAILURE_MODES_REGISTRY.read_text(encoding="utf-8")
    )
    return {fm["id"]: fm for fm in registry.get("failure_modes", [])}


# ─── Review pack assembly ──────────────────────────────────────────────────────

def build_review_pack(scope_id: str) -> Dict[str, Any]:
    """Assemble a review pack for a given scope.

    The review pack collects all context needed to produce a scoped review:
    manifest, file list, contracts, tests, design docs, and relevant failure
    modes from the registry.

    Parameters
    ----------
    scope_id:
        Identifier matching the review manifest.

    Returns
    -------
    dict
        A structured review pack with keys:
        ``manifest``, ``file_list``, ``contract_list``, ``test_list``,
        ``design_docs_list``, ``failure_modes_list``, ``assembled_at``.
    """
    manifest = load_review_manifest(scope_id)
    all_failure_modes = _load_failure_modes()

    # Resolve failure modes relevant to this manifest.
    relevant_failure_modes: List[Dict[str, Any]] = []
    for fm_id in manifest.get("known_failure_modes", []):
        if fm_id in all_failure_modes:
            relevant_failure_modes.append(all_failure_modes[fm_id])
        else:
            relevant_failure_modes.append({"id": fm_id, "note": "Not found in registry"})

    assembled_at = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    return {
        "manifest": manifest,
        "file_list": manifest.get("in_scope_files", []),
        "contract_list": manifest.get("related_contracts", []),
        "test_list": manifest.get("related_tests", []),
        "design_docs_list": manifest.get("related_design_docs", []),
        "failure_modes_list": relevant_failure_modes,
        "assembled_at": assembled_at,
    }


# ─── Prompt rendering ─────────────────────────────────────────────────────────

def _format_list_section(items: List[str], indent: str = "- ") -> str:
    """Format a list of strings as a markdown bullet list."""
    if not items:
        return "(none)"
    return "\n".join(f"{indent}`{item}`" for item in items)


def _format_plain_list_section(items: List[str], indent: str = "- ") -> str:
    """Format a list of strings as plain markdown bullets (no backticks)."""
    if not items:
        return "(none)"
    return "\n".join(f"{indent}{item}" for item in items)


def render_claude_review_prompt(scope_id: str) -> str:
    """Render a Claude review prompt for the given scope.

    Populates the prompt template with manifest data so that Claude receives
    explicit architecture context rather than having to infer it.

    Parameters
    ----------
    scope_id:
        Identifier matching the review manifest.

    Returns
    -------
    str
        Rendered markdown prompt string ready to pass to Claude.
    """
    manifest = load_review_manifest(scope_id)

    # Build the rendered prompt from the template file.
    template_text = _PROMPT_TEMPLATE.read_text(encoding="utf-8")

    # Replace Jinja-style block tags with rendered content.
    # We use a simple substitution approach — no external templating dependency.
    replacements: Dict[str, str] = {
        "{{ scope_id }}": scope_id,
        "{{ title }}": manifest.get("title", scope_id),
        "{{ purpose }}": manifest.get("purpose", ""),
        "{{ golden_path_role }}": manifest.get("golden_path_role", ""),
    }

    # Render the for-loop blocks.
    list_blocks = {
        r"\{%\s*for f in in_scope_files\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_list_section(manifest.get("in_scope_files", []))
        ),
        r"\{%\s*for c in related_contracts\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_list_section(manifest.get("related_contracts", []))
        ),
        r"\{%\s*for t in related_tests\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_list_section(manifest.get("related_tests", []))
        ),
        r"\{%\s*for d in related_design_docs\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_list_section(manifest.get("related_design_docs", []))
        ),
        r"\{%\s*for fm in known_failure_modes\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_list_section(manifest.get("known_failure_modes", []))
        ),
        r"\{%\s*for inv in invariants\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_plain_list_section(manifest.get("invariants", []))
        ),
        r"\{%\s*for ec in known_edge_cases\s*%\}.*?\{%\s*endfor\s*%\}": (
            _format_plain_list_section(manifest.get("known_edge_cases", []))
        ),
    }

    rendered = template_text
    for pattern, replacement in list_blocks.items():
        rendered = re.sub(pattern, replacement, rendered, flags=re.DOTALL)

    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    return rendered


# ─── Schema validation ────────────────────────────────────────────────────────

def validate_review_output(review_output_path: str) -> Dict[str, Any]:
    """Validate a Claude review output JSON file against the review contract schema.

    Parameters
    ----------
    review_output_path:
        Path to the review output JSON file to validate.

    Returns
    -------
    dict
        Validation result with keys:
        ``file``, ``review_id``, ``verdict``, ``passed`` (bool), ``errors`` (list[str]).
    """
    path = Path(review_output_path)

    try:
        instance: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return {
            "file": str(path),
            "review_id": "unknown",
            "verdict": "unknown",
            "passed": False,
            "errors": [f"Cannot load file: {exc}"],
        }

    if not _REVIEW_CONTRACT_SCHEMA.is_file():
        return {
            "file": str(path),
            "review_id": instance.get("review_id", "unknown"),
            "verdict": instance.get("verdict", "unknown"),
            "passed": False,
            "errors": [f"Review contract schema not found at {_REVIEW_CONTRACT_SCHEMA}"],
        }

    schema: Dict[str, Any] = json.loads(
        _REVIEW_CONTRACT_SCHEMA.read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    errors: List[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        path_parts = list(error.path)
        location = (
            f"[{'.'.join(str(p) for p in path_parts)}]" if path_parts else "[root]"
        )
        errors.append(f"Schema error at {location}: {error.message}")

    return {
        "file": str(path),
        "review_id": instance.get("review_id", "unknown"),
        "verdict": instance.get("verdict", "unknown"),
        "passed": len(errors) == 0,
        "errors": errors,
    }


# ─── Summarise review pack ────────────────────────────────────────────────────

def summarize_review_pack(scope_id: str) -> str:
    """Return a human-readable summary of the review pack for a given scope.

    Parameters
    ----------
    scope_id:
        Identifier matching the review manifest.

    Returns
    -------
    str
        Multi-line summary string.
    """
    pack = build_review_pack(scope_id)
    manifest = pack["manifest"]

    lines: List[str] = [
        f"Review Pack Summary — {scope_id}",
        "=" * 60,
        f"Title:            {manifest.get('title', '')}",
        f"Purpose:          {manifest.get('purpose', '')}",
        f"Golden path role: {manifest.get('golden_path_role', '')}",
        f"Assembled at:     {pack['assembled_at']}",
        "",
        f"Files in scope ({len(pack['file_list'])}):",
    ]
    for f in pack["file_list"]:
        lines.append(f"  - {f}")

    lines += ["", f"Contracts ({len(pack['contract_list'])}):", ]
    for c in pack["contract_list"]:
        lines.append(f"  - {c}")

    lines += ["", f"Tests ({len(pack['test_list'])}):", ]
    for t in pack["test_list"]:
        lines.append(f"  - {t}")

    lines += ["", f"Design docs ({len(pack['design_docs_list'])}):", ]
    for d in pack["design_docs_list"]:
        lines.append(f"  - {d}")

    lines += ["", f"Known failure modes ({len(pack['failure_modes_list'])}):", ]
    for fm in pack["failure_modes_list"]:
        lines.append(f"  - {fm.get('id', '?')}: {fm.get('title', fm.get('note', ''))}")

    return "\n".join(lines)
