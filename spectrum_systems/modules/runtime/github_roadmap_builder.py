"""Deterministic GitHub roadmap builder adapter.

Builds a bounded two-step roadmap artifact from repo-local source documents.
This module does not execute roadmap steps, make closure decisions, or orchestrate runtime execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.utils.deterministic_id import deterministic_id

_COMMAND = "/roadmap-2step"
_REQUIRED_DOCS = (
    Path("docs/vision.md"),
    Path("docs/roadmaps/system_roadmap.md"),
)
_OPTIONAL_DOCS = (
    Path("CONTRACTS.md"),
    Path("SYSTEMS.md"),
)


class GithubRoadmapBuilderError(ValueError):
    """Raised when source documents are missing or roadmap generation inputs are invalid."""


@dataclass(frozen=True)
class SourceDoc:
    path: Path
    content: str

    @property
    def digest(self) -> str:
        return sha256(self.content.encode("utf-8")).hexdigest()[:12]


def _require_non_empty_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GithubRoadmapBuilderError(f"{field} must be a non-empty string")
    return value.strip()


def _extract_keywords(command_body: str) -> list[str]:
    normalized = command_body.lower().replace("\n", " ")
    if _COMMAND in normalized:
        normalized = normalized.replace(_COMMAND, " ")

    tokens: list[str] = []
    for raw in normalized.replace(",", " ").replace(":", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum() or ch in {"-", "_"}).strip("-_")
        if len(token) >= 3 and token not in {"scope", "keyword", "keywords"}:
            tokens.append(token)

    ordered: list[str] = []
    for token in tokens:
        if token not in ordered:
            ordered.append(token)
    return ordered


def _load_source_docs(*, repo_root: Path) -> list[SourceDoc]:
    source_paths = list(_REQUIRED_DOCS) + list(_OPTIONAL_DOCS)
    docs: list[SourceDoc] = []

    for rel_path in source_paths:
        full_path = repo_root / rel_path
        if not full_path.exists():
            if rel_path in _REQUIRED_DOCS:
                raise GithubRoadmapBuilderError(f"required source doc is missing: {rel_path}")
            continue

        content = full_path.read_text(encoding="utf-8").strip()
        if not content:
            raise GithubRoadmapBuilderError(f"source doc is empty: {rel_path}")
        docs.append(SourceDoc(path=rel_path, content=content))

    if len(docs) < 2:
        raise GithubRoadmapBuilderError("at least two source docs are required to build a two-step roadmap")
    return docs


def _select_docs(*, docs: list[SourceDoc], keywords: list[str]) -> list[SourceDoc]:
    scored: list[tuple[int, str, SourceDoc]] = []
    for doc in docs:
        lowered = doc.content.lower()
        score = sum(lowered.count(keyword) for keyword in keywords)
        scored.append((score, str(doc.path), doc))

    ranked = sorted(scored, key=lambda row: (-row[0], row[1]))
    selected = [row[2] for row in ranked[:2]]
    if len(selected) != 2:
        raise GithubRoadmapBuilderError("failed to select exactly two source documents")
    return selected


def _source_ref(doc: SourceDoc) -> str:
    return f"{doc.path}#sha256:{doc.digest}"


def build_two_step_roadmap_from_sources(input_context: dict[str, Any]) -> dict[str, Any]:
    """Build exactly-two-step deterministic roadmap artifact from repo-local source docs."""
    context = input_context if isinstance(input_context, dict) else {}
    command_body = _require_non_empty_str(context.get("command_body"), field="input_context.command_body")
    emitted_at = _require_non_empty_str(context.get("emitted_at"), field="input_context.emitted_at")

    if _COMMAND not in command_body:
        raise GithubRoadmapBuilderError("command_body must include /roadmap-2step marker")

    repo_root_raw = context.get("repo_root", ".")
    repo_root = Path(repo_root_raw)
    docs = _load_source_docs(repo_root=repo_root)
    keywords = _extract_keywords(command_body)
    selected = _select_docs(docs=docs, keywords=keywords)

    source_refs = [_source_ref(doc) for doc in selected]
    roadmap_seed = {
        "pr_number": context.get("pr_number"),
        "source_event_ref": context.get("source_event_ref"),
        "command_body": command_body,
        "source_refs": source_refs,
    }
    roadmap_id = deterministic_id(prefix="r2s", namespace="github_roadmap_builder", payload=roadmap_seed).upper()

    steps = [
        {
            "step_id": "step_1",
            "description": f"Extract bounded implementation constraints from {selected[0].path}.",
            "required_inputs": [source_refs[0]],
            "expected_outputs": [f"constraints::{selected[0].path.name}"],
        },
        {
            "step_id": "step_2",
            "description": f"Map extracted constraints into governed continuation inputs using {selected[1].path}.",
            "required_inputs": [source_refs[1], "output:step_1"],
            "expected_outputs": ["governed_continuation_input"],
        },
    ]

    artifact = {
        "roadmap_id": roadmap_id,
        "schema_version": "1.0.0",
        "generated_at": emitted_at,
        "source_refs": source_refs,
        "steps": steps,
        "bounded": True,
        "step_count": 2,
    }
    validate_artifact(artifact, "roadmap_two_step_artifact")
    return artifact


__all__ = ["GithubRoadmapBuilderError", "build_two_step_roadmap_from_sources"]
