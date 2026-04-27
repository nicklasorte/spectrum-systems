"""GOV: Proof bundle size budget enforcement (NT-04..06).

A small, deterministic seam that validates proof artifacts against the
size/complexity budget declared in
``contracts/governance/proof_bundle_size_policy.json``. Bundles that exceed
the budget either block or are compressed deterministically:

  * compact bundles pass.
  * bloated bundles either block (default) or are reduced to summary-first,
    reference-only output with stable ordering.

GOV/PRA do not own policy authority — this module reports a validation
result and produces a compressed shape; downstream owners (CDE/SEL) decide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "contracts" / "governance" / "proof_bundle_size_policy.json"
)


CANONICAL_PROOF_BUNDLE_SIZE_REASON_CODES = {
    "PROOF_BUNDLE_OK",
    "PROOF_BUNDLE_TOO_MANY_EVIDENCE_REFS",
    "PROOF_BUNDLE_ONE_PAGE_TOO_LONG",
    "PROOF_BUNDLE_BLOCKING_DETAIL_CODES_TOO_MANY",
    "PROOF_BUNDLE_NESTING_TOO_DEEP",
    "PROOF_BUNDLE_REPEATED_EVIDENCE_REFS",
    "PROOF_BUNDLE_INLINE_EVIDENCE_FORBIDDEN",
    "PROOF_BUNDLE_SIZE_POLICY_UNAVAILABLE",
}


class ProofBundleSizeError(ValueError):
    """Raised when proof-bundle size validation cannot be performed."""


def load_proof_bundle_size_policy(
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    path = policy_path or DEFAULT_POLICY_PATH
    if not path.exists():
        raise ProofBundleSizeError(f"proof bundle size policy not found at {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProofBundleSizeError(
            f"proof bundle size policy invalid JSON: {exc}"
        ) from exc
    if data.get("artifact_type") != "proof_bundle_size_policy":
        raise ProofBundleSizeError(
            f"proof bundle size policy artifact_type mismatch: "
            f"{data.get('artifact_type')!r}"
        )
    if not isinstance(data.get("limits"), dict):
        raise ProofBundleSizeError("proof bundle size policy missing limits")
    return data


def _depth(obj: Any) -> int:
    if isinstance(obj, Mapping):
        return 1 + max((_depth(v) for v in obj.values()), default=0)
    if isinstance(obj, list):
        return 1 + max((_depth(v) for v in obj), default=0)
    return 0


def _evidence_ref_keys(bundle: Mapping[str, Any]) -> List[str]:
    return sorted(k for k in bundle.keys() if k.endswith("_ref"))


def _evidence_ref_values(bundle: Mapping[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for k in _evidence_ref_keys(bundle):
        v = bundle.get(k)
        if isinstance(v, str) and v.strip():
            out.append((k, v))
    return out


def validate_proof_bundle_size(
    bundle: Mapping[str, Any],
    *,
    artifact_type: Optional[str] = None,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a proof artifact against the size budget policy.

    Returns
    -------
    {"decision": "allow" | "block",
     "reason_code": str (canonical),
     "blocking_reasons": [str, ...],
     "metrics": {"evidence_ref_count": int,
                 "one_page_summary_chars": int,
                 "human_readable_chars": int,
                 "nested_depth": int,
                 "blocking_detail_codes": int,
                 "repeated_evidence_refs": int,
                 "inline_evidence_keys": [str, ...]}}
    """
    if not isinstance(bundle, Mapping):
        raise ProofBundleSizeError("bundle must be a mapping")

    pol = dict(policy) if policy is not None else load_proof_bundle_size_policy()
    atype = str(artifact_type or bundle.get("artifact_type") or "")
    limits = (pol.get("limits") or {}).get(atype) or {}

    if not limits:
        # No limits defined for this artifact type → unknown becomes block.
        return {
            "decision": "block",
            "reason_code": "PROOF_BUNDLE_SIZE_POLICY_UNAVAILABLE",
            "blocking_reasons": [
                f"no size budget defined for artifact_type={atype!r}"
            ],
            "metrics": {},
        }

    refs = _evidence_ref_values(bundle)
    one_page = ""
    if isinstance(bundle.get("trace_summary"), Mapping):
        one_page = str(bundle["trace_summary"].get("one_page_summary") or "")
    if not one_page:
        one_page = str(bundle.get("one_page_summary") or "")
    human = str(bundle.get("human_readable") or "")
    detail_codes = bundle.get("blocking_detail_codes") or []

    # Repeated refs detection: same ref value used by more than one ref key
    ref_value_counts: Dict[str, int] = {}
    for _k, v in refs:
        ref_value_counts[v] = ref_value_counts.get(v, 0) + 1
    repeated = sum(1 for _v, c in ref_value_counts.items() if c > 1)

    # Inline evidence keys check
    forbid_keys = set(limits.get("forbid_inline_evidence_keys") or [])
    inline_keys = sorted(k for k in bundle.keys() if k in forbid_keys)

    nested_depth = _depth(bundle)
    blocking_detail_count = len(detail_codes) if isinstance(detail_codes, list) else 0

    metrics = {
        "evidence_ref_count": len(refs),
        "one_page_summary_chars": len(one_page),
        "human_readable_chars": len(human),
        "nested_depth": nested_depth,
        "blocking_detail_codes": blocking_detail_count,
        "repeated_evidence_refs": repeated,
        "inline_evidence_keys": inline_keys,
    }

    blocking: List[str] = []
    reason_code = "PROOF_BUNDLE_OK"

    def _block(reason: str, why: str) -> None:
        nonlocal reason_code
        blocking.append(why)
        if reason_code == "PROOF_BUNDLE_OK":
            reason_code = reason

    max_refs = limits.get("max_top_level_evidence_refs")
    if isinstance(max_refs, int) and len(refs) > max_refs:
        _block(
            "PROOF_BUNDLE_TOO_MANY_EVIDENCE_REFS",
            f"{len(refs)} top-level evidence refs (>limit {max_refs})",
        )

    max_one = limits.get("max_one_page_summary_chars")
    if isinstance(max_one, int) and len(one_page) > max_one:
        _block(
            "PROOF_BUNDLE_ONE_PAGE_TOO_LONG",
            f"one_page_summary {len(one_page)} chars (>limit {max_one})",
        )

    max_human = limits.get("max_human_readable_chars")
    if isinstance(max_human, int) and len(human) > max_human:
        _block(
            "PROOF_BUNDLE_ONE_PAGE_TOO_LONG",
            f"human_readable {len(human)} chars (>limit {max_human})",
        )

    max_detail = limits.get("max_blocking_detail_codes")
    if isinstance(max_detail, int) and blocking_detail_count > max_detail:
        _block(
            "PROOF_BUNDLE_BLOCKING_DETAIL_CODES_TOO_MANY",
            f"{blocking_detail_count} blocking detail codes (>limit {max_detail})",
        )

    max_depth = limits.get("max_nested_depth")
    if isinstance(max_depth, int) and nested_depth > max_depth:
        _block(
            "PROOF_BUNDLE_NESTING_TOO_DEEP",
            f"nested depth {nested_depth} (>limit {max_depth})",
        )

    if repeated > 0:
        _block(
            "PROOF_BUNDLE_REPEATED_EVIDENCE_REFS",
            f"{repeated} ref values used more than once",
        )

    if inline_keys:
        _block(
            "PROOF_BUNDLE_INLINE_EVIDENCE_FORBIDDEN",
            f"inline evidence keys present: {','.join(inline_keys)}",
        )

    decision = "block" if blocking else "allow"
    return {
        "decision": decision,
        "reason_code": reason_code,
        "blocking_reasons": blocking,
        "metrics": metrics,
    }


def compress_proof_bundle(
    bundle: Mapping[str, Any],
    *,
    artifact_type: Optional[str] = None,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Produce a deterministic, summary-first, reference-only copy of a
    proof bundle. Inline evidence keys (forbidden by policy) are dropped
    and a count is recorded. Ordering follows ``stable_ordering`` from
    policy when applicable.

    The compressed bundle is intended to satisfy the size budget; callers
    should re-validate against ``validate_proof_bundle_size``.
    """
    if not isinstance(bundle, Mapping):
        raise ProofBundleSizeError("bundle must be a mapping")
    pol = dict(policy) if policy is not None else load_proof_bundle_size_policy()
    atype = str(artifact_type or bundle.get("artifact_type") or "")
    limits = (pol.get("limits") or {}).get(atype) or {}
    forbid_keys = set(limits.get("forbid_inline_evidence_keys") or [])

    # Drop inline evidence keys; record count
    suppressed = sorted([k for k in bundle.keys() if k in forbid_keys])
    compressed: Dict[str, Any] = {
        k: v for k, v in bundle.items() if k not in forbid_keys
    }

    # Stable ordering of evidence_*_ref keys
    stable_order = (
        (pol.get("stable_ordering") or {}).get("evidence_ref_order") or []
    )
    ordered: Dict[str, Any] = {}
    # Preserve canonical structural keys first, in the order they appear
    structural = [
        "artifact_type",
        "schema_version",
        "bundle_id",
        "index_id",
        "trace_id",
        "run_id",
        "final_status",
        "status",
        "canonical_blocking_category",
        "blocking_reason_canonical",
    ]
    for k in structural:
        if k in compressed:
            ordered[k] = compressed[k]
    # Then evidence refs in stable order
    for k in stable_order:
        if k in compressed:
            ordered[k] = compressed[k]
    # Finally everything else, in sorted order for determinism
    for k in sorted(compressed.keys()):
        if k not in ordered:
            ordered[k] = compressed[k]

    # Annotate suppression
    if suppressed:
        ordered["compression_notice"] = {
            "suppressed_inline_keys": suppressed,
            "policy_id": pol.get("policy_id"),
            "rationale": (pol.get("overflow_behavior") or {}).get(
                "alternative_rationale", "evidence referenced, not inlined"
            ),
        }

    return ordered


def validate_proof_artifacts(
    artifacts: Iterable[Mapping[str, Any]],
    *,
    policy: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Run validate_proof_bundle_size across an iterable of proof artifacts.
    Returns aggregate counts + a per-item list."""
    pol = dict(policy) if policy is not None else load_proof_bundle_size_policy()
    items: List[Dict[str, Any]] = []
    counts = {"allow": 0, "block": 0}
    for art in artifacts:
        if not isinstance(art, Mapping):
            continue
        res = validate_proof_bundle_size(art, policy=pol)
        items.append(
            {
                "artifact_type": art.get("artifact_type"),
                "result": res,
            }
        )
        counts[res["decision"]] = counts.get(res["decision"], 0) + 1
    overall = "allow" if counts.get("block", 0) == 0 else "block"
    return {"overall_decision": overall, "counts": counts, "items": items}


__all__ = [
    "CANONICAL_PROOF_BUNDLE_SIZE_REASON_CODES",
    "ProofBundleSizeError",
    "compress_proof_bundle",
    "load_proof_bundle_size_policy",
    "validate_proof_artifacts",
    "validate_proof_bundle_size",
]
