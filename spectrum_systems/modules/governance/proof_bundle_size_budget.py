"""Proof bundle size budget (NT-04..06).

A non-owning seam that evaluates trust proof artifacts (loop proof bundle,
certification evidence index, one-page trace) against a finite size and
complexity budget so:

  - bundles stay operator-readable (one-page summaries stay one page)
  - producers cannot inline evidence to mask fragility
  - duplicate / deeply-nested evidence cannot smuggle in extra weight

The seam evaluates an already-built bundle. It does NOT decide promotion
itself; it returns a canonical pass/block-with-reason that downstream
certification/control consume. When ``overflow_behavior == "compress"``
for the one-page trace, the seam returns a compressed rendering whose
output is deterministic for stable inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "contracts" / "governance" / "proof_bundle_size_policy.json"
)


CANONICAL_PROOF_SIZE_REASON_CODES = {
    "PROOF_SIZE_OK",
    "PROOF_SIZE_OVER_REF_BUDGET",
    "PROOF_SIZE_NESTED_TOO_DEEP",
    "PROOF_SIZE_OVER_LINE_BUDGET",
    "PROOF_SIZE_OVER_CHAR_BUDGET",
    "PROOF_SIZE_DUPLICATE_REFS",
    "PROOF_SIZE_INLINE_EVIDENCE",
}


class ProofBundleSizeError(ValueError):
    """Raised when the size budget cannot be deterministically evaluated."""


def load_proof_bundle_size_policy(
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise ProofBundleSizeError(
            f"proof bundle size policy not found at {path}"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProofBundleSizeError(
            f"proof bundle size policy invalid JSON: {exc}"
        ) from exc
    if data.get("artifact_type") != "proof_bundle_size_policy":
        raise ProofBundleSizeError(
            "proof bundle size policy artifact_type mismatch"
        )
    return data


_REF_KEY_SUFFIX = "_ref"


def _collect_top_level_refs(bundle: Mapping[str, Any]) -> List[str]:
    """Return the names of top-level keys that look like evidence references.

    A reference key ends in ``_ref`` and has a string (or ``None``) value.
    """
    refs: List[str] = []
    for key, value in bundle.items():
        if not isinstance(key, str):
            continue
        if key.endswith(_REF_KEY_SUFFIX) and (
            value is None or isinstance(value, str)
        ):
            refs.append(key)
    return refs


def _max_depth(payload: Any, _depth: int = 0) -> int:
    if isinstance(payload, Mapping):
        if not payload:
            return _depth
        return max(_max_depth(v, _depth + 1) for v in payload.values())
    if isinstance(payload, list):
        if not payload:
            return _depth
        return max(_max_depth(v, _depth + 1) for v in payload)
    return _depth


def _detect_inline_evidence(
    bundle: Mapping[str, Any], forbidden_keys: List[str]
) -> List[str]:
    """Return keys whose value is a Mapping (i.e., inline evidence) or
    a list of Mappings — both forms count as inline evidence and should
    instead be referenced by ``*_ref``.
    """
    offenders: List[str] = []
    for key in forbidden_keys:
        if key not in bundle:
            continue
        value = bundle[key]
        if isinstance(value, Mapping):
            offenders.append(key)
        elif isinstance(value, list) and any(isinstance(v, Mapping) for v in value):
            offenders.append(key)
    return offenders


def _detect_duplicate_refs(bundle: Mapping[str, Any]) -> List[str]:
    """Return ref-key names whose VALUES collide across more than one key.

    We treat ``None``/empty as not-a-reference so "all four are None" does
    not register as duplicates.
    """
    seen: Dict[str, List[str]] = {}
    for key in _collect_top_level_refs(bundle):
        value = bundle[key]
        if not isinstance(value, str) or not value.strip():
            continue
        seen.setdefault(value, []).append(key)
    duplicates: List[str] = []
    for value, keys in seen.items():
        if len(keys) > 1:
            duplicates.extend(sorted(keys))
    return sorted(set(duplicates))


def _evaluate_kind(
    *,
    kind: str,
    bundle: Mapping[str, Any],
    spec: Mapping[str, Any],
) -> Dict[str, Any]:
    blocking: List[str] = []
    decision = "allow"
    reason_code = "PROOF_SIZE_OK"

    def _block(reason: str, why: str) -> None:
        nonlocal decision, reason_code
        decision = "block"
        if reason_code == "PROOF_SIZE_OK":
            reason_code = reason
        blocking.append(why)

    refs = _collect_top_level_refs(bundle)
    max_refs = int(spec.get("max_top_level_evidence_refs", 16))
    if len(refs) > max_refs:
        _block(
            "PROOF_SIZE_OVER_REF_BUDGET",
            f"top-level evidence refs {len(refs)} > budget {max_refs}",
        )

    inline_offenders = _detect_inline_evidence(
        bundle, list(spec.get("forbid_inline_evidence_keys", []) or [])
    )
    if inline_offenders:
        _block(
            "PROOF_SIZE_INLINE_EVIDENCE",
            f"inline evidence keys present (must be ref'd): {inline_offenders}",
        )

    duplicate_refs = _detect_duplicate_refs(bundle)
    if duplicate_refs:
        _block(
            "PROOF_SIZE_DUPLICATE_REFS",
            f"duplicate evidence references across keys: {duplicate_refs}",
        )

    max_depth = int(spec.get("max_nested_depth", 3))
    actual_depth = _max_depth(bundle)
    if actual_depth > max_depth:
        _block(
            "PROOF_SIZE_NESTED_TOO_DEEP",
            f"nested depth {actual_depth} > budget {max_depth}",
        )

    human_readable = bundle.get("human_readable")
    max_chars = int(spec.get("max_human_readable_chars", 6000))
    if isinstance(human_readable, str) and len(human_readable) > max_chars:
        _block(
            "PROOF_SIZE_OVER_CHAR_BUDGET",
            f"human_readable {len(human_readable)} chars > budget {max_chars}",
        )

    one_page = None
    summary_block = bundle.get("trace_summary")
    if isinstance(summary_block, Mapping):
        one_page = summary_block.get("one_page_summary")
    if one_page is None:
        one_page = bundle.get("one_page_summary")
    max_lines = int(spec.get("max_one_page_summary_lines", spec.get("max_lines", 60)))
    if isinstance(one_page, str):
        line_count = len(one_page.splitlines())
        if line_count > max_lines:
            _block(
                "PROOF_SIZE_OVER_LINE_BUDGET",
                f"one_page_summary lines {line_count} > budget {max_lines}",
            )

    # certification_evidence_index also caps blocking_detail_codes
    if kind == "certification_evidence_index":
        max_codes = int(spec.get("max_blocking_detail_codes", 24))
        codes = bundle.get("blocking_detail_codes")
        if isinstance(codes, list) and len(codes) > max_codes:
            _block(
                "PROOF_SIZE_OVER_REF_BUDGET",
                f"blocking_detail_codes {len(codes)} > budget {max_codes}",
            )

    return {
        "kind": kind,
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "metrics": {
            "top_level_refs": len(refs),
            "max_depth": actual_depth,
            "human_readable_chars": (
                len(human_readable) if isinstance(human_readable, str) else 0
            ),
            "one_page_lines": (
                len(one_page.splitlines()) if isinstance(one_page, str) else 0
            ),
            "duplicate_refs": duplicate_refs,
            "inline_offenders": inline_offenders,
        },
    }


def evaluate_proof_bundle_size(
    *,
    bundle: Mapping[str, Any],
    kind: Optional[str] = None,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate a proof artifact against the size policy.

    ``kind`` is inferred from ``bundle["artifact_type"]`` when not supplied.
    Supported kinds: ``loop_proof_bundle``, ``certification_evidence_index``,
    ``one_page_trace``.
    """
    if not isinstance(bundle, Mapping):
        raise ProofBundleSizeError("bundle must be a mapping")

    pol = dict(policy) if policy is not None else load_proof_bundle_size_policy()
    inferred_kind = kind or str(bundle.get("artifact_type") or "")
    if inferred_kind not in pol:
        raise ProofBundleSizeError(
            f"unknown proof artifact kind {inferred_kind!r}"
        )
    spec = pol[inferred_kind]
    return _evaluate_kind(kind=inferred_kind, bundle=bundle, spec=spec)


def compress_one_page_trace(
    one_page: str,
    *,
    max_lines: int,
    max_chars: int,
) -> Dict[str, Any]:
    """Deterministically compress an oversized one-page trace.

    The compression keeps:
      - the first 5 lines (header / overall_status / failed_stage)
      - the last 5 lines (next_recommended_action / blocking action)
      - a single sentinel line summarising the elision

    Output ordering is stable for stable inputs.
    """
    if not isinstance(one_page, str):
        raise ProofBundleSizeError("one_page must be a string")

    lines = one_page.splitlines()
    if len(lines) <= max_lines and len(one_page) <= max_chars:
        return {
            "compressed": False,
            "output": one_page,
            "elided_lines": 0,
        }

    head = lines[:5]
    tail = lines[-5:] if len(lines) > 10 else []
    elided = max(0, len(lines) - len(head) - len(tail))
    sentinel = f"... [PROOF_SIZE_COMPRESSION elided {elided} lines, see referenced evidence] ..."
    compact = head + [sentinel] + tail

    output = "\n".join(compact)
    if len(output) > max_chars:
        # Hard truncate to the char budget but never split a line in two.
        truncated: List[str] = []
        used = 0
        for line in compact:
            if used + len(line) + 1 > max_chars:
                truncated.append(
                    f"... [PROOF_SIZE_COMPRESSION char-budget reached at {max_chars}] ..."
                )
                break
            truncated.append(line)
            used += len(line) + 1
        output = "\n".join(truncated)

    return {
        "compressed": True,
        "output": output,
        "elided_lines": elided,
    }


__all__ = [
    "CANONICAL_PROOF_SIZE_REASON_CODES",
    "ProofBundleSizeError",
    "compress_one_page_trace",
    "evaluate_proof_bundle_size",
    "load_proof_bundle_size_policy",
]
