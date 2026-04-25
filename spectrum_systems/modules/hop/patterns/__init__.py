"""Reusable harness pattern modules.

Each submodule exports a ``run`` callable matching the evaluator's
runner contract::

    output = pattern.run(case_input)

Patterns are *building blocks* a candidate harness can compose. They
do not bypass the eval system: they emit
``hop_harness_faq_output``-shaped payloads that flow through the
evaluator's per-case schema gate exactly like the baseline harness.

A pattern MUST:

- be a standalone, importable module (no closure / lambda state);
- accept the eval-case input shape
  (``{"transcript_id": str, "turns": [...]}``);
- produce a schema-valid ``hop_harness_faq_output`` artifact;
- be deterministic;
- never call the evaluator, the experience store, or read raw eval
  files.

A pattern MUST NOT:

- self-certify;
- write to the experience store;
- short-circuit the evaluator's pass-criteria judges.

Pattern hooks consumed by the optimization loop are advisory only —
they expose ``run`` callables the loop can pass to the sandbox as the
runner under test, in addition to (not instead of) the candidate's
own runner.
"""

from spectrum_systems.modules.hop.patterns import (  # noqa: F401
    domain_router,
    draft_verify,
    label_primer,
)

PATTERN_KIND_DRAFT_VERIFY = "draft_verify"
PATTERN_KIND_LABEL_PRIMER = "label_primer"
PATTERN_KIND_DOMAIN_ROUTER = "domain_router"

PATTERN_REGISTRY: dict[str, str] = {
    PATTERN_KIND_DRAFT_VERIFY: "spectrum_systems.modules.hop.patterns.draft_verify",
    PATTERN_KIND_LABEL_PRIMER: "spectrum_systems.modules.hop.patterns.label_primer",
    PATTERN_KIND_DOMAIN_ROUTER: "spectrum_systems.modules.hop.patterns.domain_router",
}


def list_pattern_kinds() -> list[str]:
    return sorted(PATTERN_REGISTRY.keys())
