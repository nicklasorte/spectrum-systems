"""AEX authority-shape regression test.

If AEX-owned schemas, examples, modules, or artifacts re-introduce reserved
authority-cluster vocabulary (``enforce``/``enforcement``, ``certify``/``certification``,
``promote``/``promotion``, ``decision``/``verdict``/``adjudication``, ``control_decision``)
without a safety-suffix subtoken (``signal``/``observation``/``input``/
``recommendation``/``finding``/``evidence``/``advisory``/``request``/
``candidate``/``hint``/``summary``/``report``), this test fails — even if
the central authority-shape preflight passes for unrelated reasons.

This test is the AEX-specific counterpart to
``scripts/run_authority_shape_preflight.py`` and uses the same vocabulary
file (``contracts/governance/authority_shape_vocabulary.json``) so the two
checks cannot drift apart. Adding new AEX-owned files automatically extends
coverage.

AEX is admission-only. AEX may emit:

* admission_evidence_record
* admission_policy_observation
* admission_trace_record
* admission_replay_record
* sel_enforcement_input  (input surface — SEL/ENF retain compliance authority)
* gov_readiness_observation  (observation surface — GOV retains readiness)
* readiness_evidence
* policy_observation / compliance_observation

AEX must not own enforcement, certification, promotion, control, or final
outcome semantics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
VOCAB_PATH = REPO_ROOT / "contracts" / "governance" / "authority_shape_vocabulary.json"


# AEX-owned surfaces under inspection. All four kinds are checked.
AEX_OWNED_SCHEMA_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "contracts" / "schemas" / "admission_policy_observation.schema.json",
    REPO_ROOT / "contracts" / "schemas" / "admission_evidence_record.schema.json",
    REPO_ROOT / "contracts" / "schemas" / "admission_trace_record.schema.json",
)
AEX_SUPPLEMENTAL_SCHEMA_GLOB = REPO_ROOT / "schemas" / "aex"
AEX_OWNED_EXAMPLE_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "contracts" / "examples" / "admission_policy_observation.example.json",
    REPO_ROOT / "contracts" / "examples" / "admission_evidence_record.example.json",
    REPO_ROOT / "contracts" / "examples" / "admission_trace_record.example.json",
)
AEX_OWNED_PYTHON_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "spectrum_systems" / "aex" / "admission_replay.py",
    REPO_ROOT / "spectrum_systems" / "aex" / "observability_emitter.py",
    REPO_ROOT / "spectrum_systems" / "aex" / "sel_admission_signal.py",
)
AEX_OWNED_ARTIFACT_GLOB = REPO_ROOT / "artifacts" / "aex"


_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


def _load_vocab() -> dict:
    return json.loads(VOCAB_PATH.read_text(encoding="utf-8"))


def _safety_suffixes(vocab: dict) -> set[str]:
    return {str(s).strip().lower() for s in vocab.get("safety_suffixes", []) if str(s).strip()}


def _cluster_terms(vocab: dict) -> list[tuple[str, str]]:
    """Return (term, cluster_name) pairs for every reserved term across clusters."""
    pairs: list[tuple[str, str]] = []
    for cname, cval in (vocab.get("clusters") or {}).items():
        if not isinstance(cval, dict):
            continue
        for term in cval.get("terms", []) or []:
            t = str(term).strip().lower()
            if t:
                pairs.append((t, cname))
    return pairs


def _identifier_subtokens(identifier: str) -> set[str]:
    return {tok for tok in identifier.lower().split("_") if tok}


def _identifier_matches_term(identifier: str, term: str) -> bool:
    lowered_id = identifier.lower()
    lowered_term = term.lower()
    if not lowered_term:
        return False
    if "_" in lowered_term:
        tokens = lowered_id.split("_")
        term_tokens = lowered_term.split("_")
        for start in range(0, len(tokens) - len(term_tokens) + 1):
            if tokens[start : start + len(term_tokens)] == term_tokens:
                return True
        return False
    return lowered_term in _identifier_subtokens(lowered_id)


def _scan_text_for_violations(
    rel_path: str, text: str, vocab: dict
) -> list[tuple[int, str, str]]:
    """Return (line_no, identifier, cluster_name) for every reserved-term
    identifier without a safety-suffix subtoken.
    """
    safety_set = _safety_suffixes(vocab)
    cluster_terms = _cluster_terms(vocab)
    violations: list[tuple[int, str, str]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for ident_match in _IDENTIFIER_PATTERN.finditer(line):
            identifier = ident_match.group(0)
            subtokens = _identifier_subtokens(identifier)
            if subtokens & safety_set:
                continue
            for term, cname in cluster_terms:
                if _identifier_matches_term(identifier, term):
                    violations.append((line_no, identifier, cname))
                    break
    return violations


def _aex_owned_paths() -> list[Path]:
    paths: list[Path] = list(AEX_OWNED_SCHEMA_PATHS)
    if AEX_SUPPLEMENTAL_SCHEMA_GLOB.is_dir():
        paths.extend(sorted(AEX_SUPPLEMENTAL_SCHEMA_GLOB.glob("aex_*.schema.json")))
    paths.extend(AEX_OWNED_EXAMPLE_PATHS)
    paths.extend(AEX_OWNED_PYTHON_PATHS)
    if AEX_OWNED_ARTIFACT_GLOB.is_dir():
        paths.extend(sorted(AEX_OWNED_ARTIFACT_GLOB.glob("*.json")))
    return [p for p in paths if p.is_file()]


@pytest.mark.parametrize("path", _aex_owned_paths(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_aex_owned_file_uses_only_safety_suffixed_authority_terms(path: Path) -> None:
    """AEX-owned files must not name any identifier with a reserved
    cluster term unless the identifier also carries a safety-suffix
    subtoken (signal/observation/input/recommendation/finding/etc.).
    """
    vocab = _load_vocab()
    rel = str(path.relative_to(REPO_ROOT))
    text = path.read_text(encoding="utf-8")
    violations = _scan_text_for_violations(rel, text, vocab)
    if violations:
        rendered = "\n".join(
            f"  {rel}:{line}  '{ident}' [{cluster}]"
            for line, ident, cluster in violations[:30]
        )
        suffix = "" if len(violations) <= 30 else f"\n  ... +{len(violations) - 30} more"
        pytest.fail(
            "AEX authority-shape regression: AEX-owned file uses reserved "
            "authority terms without a safety-suffix subtoken. Use one of "
            "(signal/observation/input/recommendation/finding/evidence/advisory/"
            "request/candidate/hint/summary/report) so the identifier is "
            "exempted, or remove the term entirely.\n"
            f"{rendered}{suffix}"
        )


def test_aex_owned_assertions_use_input_or_observation_suffix() -> None:
    """AEX schemas/examples/artifacts must declare non-authority assertions
    using safety-suffixed labels (``aex_emits_*_input_only``,
    ``aex_emits_*_observation_only``, ``aex_emits_*_signal_only``). The
    older ``aex_does_not_own_*_authority`` vocabulary fails the central
    preflight and is forbidden.
    """
    forbidden_assertion_prefix = "aex_does_not_own_"
    found: list[str] = []
    for path in _aex_owned_paths():
        if path.suffix.lower() not in {".json", ".py", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden_assertion_prefix in text:
            found.append(str(path.relative_to(REPO_ROOT)))
    assert not found, (
        "AEX-owned files use the deprecated 'aex_does_not_own_*_authority' "
        "vocabulary. Rename to 'aex_emits_*_input_only' / "
        "'aex_emits_*_observation_only' / 'aex_emits_*_signal_only' so the "
        "identifier carries a safety-suffix subtoken.\n"
        + "\n".join(f"  {p}" for p in found)
    )


def test_aex_authority_shape_vocabulary_is_loadable() -> None:
    """The vocabulary file the central preflight uses must load and contain
    the cluster terms this regression test checks against. If this fails,
    the regression test is silently misconfigured."""
    vocab = _load_vocab()
    assert vocab.get("clusters"), "vocabulary missing clusters"
    cluster_names = {str(c).lower() for c in (vocab.get("clusters") or {}).keys()}
    for required in ("decision", "enforcement", "certification", "promotion", "control"):
        assert required in cluster_names, f"vocabulary missing cluster '{required}'"
    safety = _safety_suffixes(vocab)
    for needed in ("signal", "observation", "input"):
        assert needed in safety, f"vocabulary missing safety_suffix '{needed}'"
