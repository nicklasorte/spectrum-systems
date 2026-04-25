"""Bounded proposer for HOP harness candidates.

The proposer is the **only** module allowed to emit new candidate code.
It reads (read-only) from the experience store and produces a candidate
payload. It MUST NOT:

- modify eval cases or schemas;
- write to the experience store;
- call the evaluator;
- mutate any module other than the candidate's own file.

Every candidate it emits is a self-contained Python source string keyed
to a fresh ``candidate_id``. Downstream stages (admission, mutation
policy, safety scan, evaluator, store) are invoked by
``optimization_loop.run_proposer_cycle`` — never by the proposer itself.

BATCH-2 ships four deterministic mutation templates, each declaring a
``mutation_kind`` from
:func:`mutation_policy.list_allowed_mutation_kinds`. The templates are
text-level rewrites of the baseline harness body, all of which preserve
the FAQ-output contract validated by
``contracts/schemas/hop/harness_faq_output.schema.json``.

The proposer also requires:

- **per-cycle quota** — the optimization loop caps ``max_proposals`` per
  invocation; exceeding the quota fails-closed via
  :class:`ProposerQuotaExceeded`. This bounds wall-clock and store
  growth even if a calling driver is buggy.
- **lineage** — every proposal carries ``parent_candidate_id`` so the
  trace-diff and failure-analysis modules can reconstruct lineage.
- **provenance tags** — ``tags`` always include the mutation kind so the
  optimization loop can filter / dedupe.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.mutation_policy import (
    MutationProposal,
    list_allowed_mutation_kinds,
)

CANDIDATE_MODULE_PATH = "spectrum_systems/modules/hop/baseline_harness.py"
"""Repo-relative path of the only file the proposer may declare modified."""

DEFAULT_MAX_PROPOSALS = 4


class ProposerError(Exception):
    """Raised on proposer-internal violations."""


class ProposerQuotaExceeded(ProposerError):
    """Raised when a caller asks for more proposals than the quota allows."""


@dataclass(frozen=True)
class ProposerContext:
    """Read-only view onto the experience store the proposer may inspect.

    The proposer is given an *immutable* snapshot of the candidates,
    runs, and failure artifacts it should consider. It MUST NOT touch
    the live store.
    """

    prior_candidates: tuple[Mapping[str, Any], ...]
    prior_scores: tuple[Mapping[str, Any], ...]
    prior_failures: tuple[Mapping[str, Any], ...]
    prior_traces: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ProposalBundle:
    """Output of :func:`propose_candidates`.

    ``candidate_payload`` is a finalized HOP candidate envelope.
    ``mutation_proposal`` is the structured changeset summary the
    optimization loop hands to the mutation policy. The two are bound
    together — the loop must process them as a pair.
    """

    candidate_payload: dict[str, Any]
    mutation_proposal: MutationProposal


# ---------------------------------------------------------------------------
# deterministic mutation templates
# ---------------------------------------------------------------------------


def _additive_context_template(baseline_source: str) -> tuple[str, str]:
    """Append a deterministic, side-effect-free preamble comment block."""
    preamble = (
        "# hop_mutation:additive_context\n"
        "# Provenance: HOP-BATCH-2 proposer v1 (additive context).\n"
        "# This block is informational; it does not alter behavior.\n"
    )
    return preamble + baseline_source, "additive_context"


def _ordering_template(baseline_source: str) -> tuple[str, str]:
    """Stable-sort items by ``source_turn_indices`` before returning.

    Inserts a single line that sorts the items list immediately before
    the FAQ payload is finalized. The baseline already sorts within each
    item, so this is a redundant but additive guarantee — a minor
    `cost`-positive change suitable for frontier exploration.
    """
    needle = '    payload: dict[str, Any] = {\n'
    if needle not in baseline_source:
        raise ProposerError("hop_proposer_template_anchor_missing:ordering")
    insertion = (
        "    items.sort(key=lambda it: tuple(it.get('source_turn_indices', [])))\n"
    )
    return baseline_source.replace(needle, insertion + needle, 1), "ordering"


def _retrieval_logic_template(baseline_source: str) -> tuple[str, str]:
    """Prefer the *closest* assistant turn, tie-broken by index ascending.

    The baseline scans forward until the first assistant turn. This
    rewrite explicitly walks the same window but documents the choice
    via a deterministic helper variable — same behavior, refactored.
    """
    needle = "        # Find next assistant turn.\n"
    if needle not in baseline_source:
        raise ProposerError("hop_proposer_template_anchor_missing:retrieval_logic")
    replacement = (
        "        # Find next assistant turn (closest forward neighbor).\n"
        "        # hop_mutation:retrieval_logic — explicit closest-neighbor selection.\n"
    )
    return baseline_source.replace(needle, replacement, 1), "retrieval_logic"


def _prompt_structure_template(baseline_source: str) -> tuple[str, str]:
    """Add a deterministic post-processing step that strips trailing whitespace.

    Strips trailing whitespace from each item's question/answer before
    they reach the schema validator. This is a textual prompt-structure
    refinement; it does not change which Q/A pairs are extracted.
    """
    needle = '    payload: dict[str, Any] = {\n'
    if needle not in baseline_source:
        raise ProposerError("hop_proposer_template_anchor_missing:prompt_structure")
    insertion = (
        "    items = [\n"
        "        {\n"
        "            'question': it['question'].rstrip(),\n"
        "            'answer': it['answer'].rstrip(),\n"
        "            'source_turn_indices': it['source_turn_indices'],\n"
        "        }\n"
        "        for it in items\n"
        "    ]\n"
    )
    return baseline_source.replace(needle, insertion + needle, 1), "prompt_structure"


_TEMPLATES: tuple[Callable[[str], tuple[str, str]], ...] = (
    _additive_context_template,
    _ordering_template,
    _retrieval_logic_template,
    _prompt_structure_template,
)


# ---------------------------------------------------------------------------
# context loader
# ---------------------------------------------------------------------------


def load_proposer_context(
    store: ExperienceStore,
    *,
    max_records: int = 256,
) -> ProposerContext:
    """Snapshot the read-only proposer context from a live store.

    The snapshot is bounded to ``max_records`` per artifact type so a
    very large store cannot blow up the proposer's working memory.
    Records beyond the cap are silently dropped — the proposer is
    advisory, not authoritative.
    """
    if max_records <= 0:
        raise ProposerError(f"hop_proposer_invalid_max_records:{max_records}")

    def _take(it: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in it:
            out.append(rec)
            if len(out) >= max_records:
                break
        return out

    candidates: list[Mapping[str, Any]] = []
    for rec in _take(store.list_candidates()):
        try:
            candidates.append(
                store.read_artifact("hop_harness_candidate", rec["artifact_id"])
            )
        except Exception:
            continue
    scores: list[Mapping[str, Any]] = []
    for rec in _take(store.list_scores()):
        try:
            scores.append(store.read_artifact("hop_harness_score", rec["artifact_id"]))
        except Exception:
            continue
    failures: list[Mapping[str, Any]] = []
    for rec in _take(store.list_failures()):
        try:
            failures.append(
                store.read_artifact(
                    "hop_harness_failure_hypothesis", rec["artifact_id"]
                )
            )
        except Exception:
            continue
    traces: list[Mapping[str, Any]] = []
    for rec in _take(store.list_traces()):
        try:
            traces.append(store.read_artifact("hop_harness_trace", rec["artifact_id"]))
        except Exception:
            continue

    return ProposerContext(
        prior_candidates=tuple(candidates),
        prior_scores=tuple(scores),
        prior_failures=tuple(failures),
        prior_traces=tuple(traces),
    )


# ---------------------------------------------------------------------------
# core proposal
# ---------------------------------------------------------------------------


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _build_candidate_payload(
    *,
    new_source: str,
    parent_candidate_id: str,
    mutation_kind: str,
    cycle_index: int,
) -> dict[str, Any]:
    candidate_id = (
        f"proposer_{mutation_kind}_{cycle_index:04d}_{_short_hash(new_source)}"
    )
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(
            primary="hop_proposer",
            related=[parent_candidate_id, mutation_kind],
        ),
        "candidate_id": candidate_id,
        "harness_type": "transcript_to_faq",
        "code_module": "spectrum_systems.modules.hop.baseline_harness",
        "code_entrypoint": "run",
        "code_source": new_source,
        "declared_methods": ["run"],
        "parent_candidate_id": parent_candidate_id,
        "tags": ["proposer", "hop_batch2", mutation_kind],
        "created_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    return payload


def propose_candidates(
    *,
    baseline_candidate: Mapping[str, Any],
    context: ProposerContext,
    max_proposals: int = DEFAULT_MAX_PROPOSALS,
) -> list[ProposalBundle]:
    """Emit up to ``max_proposals`` mutation proposals.

    The proposer never persists artifacts, never invokes the evaluator,
    and never reads the on-disk eval files. ``context`` is the only
    read-only window onto historical store contents.
    """
    if not isinstance(baseline_candidate, Mapping):
        raise ProposerError("hop_proposer_invalid_baseline:not_mapping")
    if max_proposals <= 0:
        raise ProposerQuotaExceeded(
            f"hop_proposer_quota_exceeded:max_proposals={max_proposals}"
        )
    if max_proposals > len(_TEMPLATES):
        raise ProposerQuotaExceeded(
            f"hop_proposer_quota_exceeded:max_proposals={max_proposals}>templates={len(_TEMPLATES)}"
        )
    if not isinstance(context, ProposerContext):
        raise ProposerError("hop_proposer_invalid_context")

    baseline_id = baseline_candidate.get("candidate_id")
    baseline_source = baseline_candidate.get("code_source")
    if not isinstance(baseline_id, str) or not isinstance(baseline_source, str):
        raise ProposerError("hop_proposer_invalid_baseline:fields")

    seen_sources = {baseline_source}
    bundles: list[ProposalBundle] = []
    for cycle_index, template in enumerate(_TEMPLATES[:max_proposals]):
        new_source, mutation_kind = template(baseline_source)
        if new_source in seen_sources:
            # Templates are deterministic; if a duplicate sneaks in we
            # decline rather than emit a redundant candidate.
            continue
        seen_sources.add(new_source)
        if mutation_kind not in list_allowed_mutation_kinds():
            raise ProposerError(
                f"hop_proposer_internal_kind_unknown:{mutation_kind}"
            )
        candidate_payload = _build_candidate_payload(
            new_source=new_source,
            parent_candidate_id=baseline_id,
            mutation_kind=mutation_kind,
            cycle_index=cycle_index,
        )
        proposal = MutationProposal(
            candidate_id=candidate_payload["candidate_id"],
            candidate_code_source=new_source,
            candidate_module_path=CANDIDATE_MODULE_PATH,
            baseline_code_source=baseline_source,
            modified_paths=(CANDIDATE_MODULE_PATH,),
            mutation_kind=mutation_kind,
        )
        bundles.append(
            ProposalBundle(
                candidate_payload=candidate_payload,
                mutation_proposal=proposal,
            )
        )
    return bundles
