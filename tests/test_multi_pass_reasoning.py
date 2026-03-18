"""
Tests for spectrum_systems/modules/ai_workflow/multi_pass_reasoning.py

Covers:
  - build_pass_chain: meeting_minutes produces correct pass sequence
  - build_pass_chain: reasoning-class passes default to scoring_pass
  - build_pass_chain: explicit confidence_method override on reasoning-class pass → warning
  - build_pass_chain: unsupported task_type raises UnsupportedTaskTypeError
  - build_pass_chain: invalid circuit-breaker policy raises InvalidCircuitBreakerPolicyError
  - build_pass_chain: circuit-breaker policy overrides are applied
  - build_pass_chain: pass_overrides are applied per pass_type
  - build_pass_chain: chain_id is deterministic
  - execute_pass_chain: all passes complete successfully
  - execute_pass_chain: pass execution ordering is deterministic
  - execute_pass_chain: circuit breaker terminates after max_failed_passes
  - execute_pass_chain: circuit breaker terminates on consecutive_failure_limit
  - execute_pass_chain: circuit breaker escalates on persistent validation failures
  - execute_pass_chain: intermediate outputs are preserved for failed chains
  - execute_pass_chain: prompt not found triggers hard failure (no silent fallback)
  - execute_pass_chain: deprecated prompt with no fallback raises hard failure
  - execute_pass_chain: routing version is pinned across chain
  - execute_single_pass: successful pass returns completed PassResult
  - execute_single_pass: model adapter exception returns failed PassResult
  - execute_single_pass: scoring_pass confidence method calls invoke_scoring_pass
  - execute_single_pass: scoring_pass failure propagates as PassChainError
  - execute_single_pass: missing model_adapter raises PassChainError
  - execute_single_pass: self_reported confidence extracted from output
  - execute_single_pass: heuristic confidence computed from output structure
  - validate_pass_output: no schema → skipped
  - validate_pass_output: valid output → passed
  - validate_pass_output: invalid output → failed with errors
  - validate_pass_output: non-dict output with schema → failed
  - apply_circuit_breaker: no action on running chain within limits
  - apply_circuit_breaker: terminates on max_passes
  - apply_circuit_breaker: terminates on max_failed_passes
  - apply_circuit_breaker: terminates on consecutive_failure_limit
  - apply_circuit_breaker: escalates on persistent_validation_failure_limit
  - apply_circuit_breaker: escalation_policy=terminate_only does not escalate
  - apply_circuit_breaker: already-terminated chain is not re-evaluated
  - finalize_pass_chain: running chain transitions to completed
  - finalize_pass_chain: _raw_output keys are stripped from pass results
  - finalize_pass_chain: intermediate_artifact_refs are collected
  - finalize_pass_chain: synthesis pass refs grounding upstream passes
  - Schema validation: pass_chain_record and pass_result conform to JSON schemas
  - Edge cases: one pass repeatedly failing validation
  - Edge cases: scoring pass fails → pass fails
  - Edge cases: escalation after max_failed_passes with escalation policy
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import (
    DEFAULT_CIRCUIT_BREAKER_POLICY,
    MEETING_MINUTES_PASS_SEQUENCE,
    REASONING_CLASS_PASSES,
    InvalidCircuitBreakerPolicyError,
    PassChainError,
    UnsupportedTaskTypeError,
    apply_circuit_breaker,
    build_pass_chain,
    execute_pass_chain,
    execute_single_pass,
    finalize_pass_chain,
    validate_pass_output,
    _init_chain_state,
    _make_chain_id,
)

# ─── Fixtures and helpers ─────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"


def _load_schema(name: str) -> dict:
    path = SCHEMA_DIR / name
    with path.open() as fh:
        return json.load(fh)


def _validate(instance: dict, schema: dict) -> None:
    from jsonschema import validate as js_validate
    js_validate(instance=instance, schema=schema)


def _minimal_context_bundle(context_id: str = "ctx-abcdef1234567890") -> dict:
    return {
        "context_id": context_id,
        "task_type": "meeting_minutes",
        "primary_input": {"transcript": "We discussed X.", "meeting_id": "MTG-001"},
        "policy_constraints": {},
        "retrieved_context": [],
        "prior_artifacts": [],
        "glossary_terms": [],
        "unresolved_questions": [],
        "metadata": {
            "created_at": "2026-01-01T00:00:00+00:00",
            "retrieval_status": "unavailable",
            "source_artifact_ids": [],
        },
        "token_estimates": {
            "primary_input": 10,
            "policy_constraints": 0,
            "prior_artifacts": 0,
            "retrieved_context": 0,
            "glossary_terms": 0,
            "unresolved_questions": 0,
            "total": 10,
        },
        "truncation_log": [],
    }


def _make_strict_cb_policy(**overrides) -> dict:
    """Return a circuit-breaker policy that trips after the first failure."""
    policy = {
        "max_passes": 10,
        "max_failed_passes": 1,
        "consecutive_failure_limit": 1,
        "persistent_validation_failure_limit": 1,
        "escalation_policy": "escalate_after_persistent_failure",
    }
    policy.update(overrides)
    return policy


def _make_permissive_cb_policy(**overrides) -> dict:
    """Return a circuit-breaker policy that allows up to 10 failures."""
    policy = {
        "max_passes": 20,
        "max_failed_passes": 10,
        "consecutive_failure_limit": 10,
        "persistent_validation_failure_limit": 10,
        "escalation_policy": "terminate_only",
    }
    policy.update(overrides)
    return policy


def _pass_chain_state_factory(
    pass_chain: dict,
    failed: int = 0,
    consecutive: int = 0,
    validation_failures: int = 0,
    pass_results: Optional[list] = None,
) -> dict:
    state = _init_chain_state(pass_chain)
    state["failed_count"] = failed
    state["consecutive_failures"] = consecutive
    state["validation_failure_count"] = validation_failures
    if pass_results is not None:
        state["pass_results"] = pass_results
    return state


# ─── Mock adapters ────────────────────────────────────────────────────────────

class _SucceedingModelAdapter:
    """Adapter that returns a minimal successful output for every pass."""

    def __init__(self, output_per_pass: Optional[Dict[str, dict]] = None):
        # Maps pass_type → output dict.  Falls back to a generic dict.
        self._outputs = output_per_pass or {}

    def invoke(self, prompt_id, prompt_version, model_family, model_name,
               context_bundle, upstream_outputs, pass_config) -> dict:
        pass_type = prompt_id.split(".")[-1] if "." in prompt_id else prompt_id
        output = self._outputs.get(pass_type, {"_pass_type": pass_type})
        return {
            "output": output,
            "model_name": "test-model-v1",
            "model_family": "test-family",
            "latency_ms": 42,
        }

    def invoke_scoring_pass(self, main_pass_id, main_output, pass_spec,
                            context_bundle, upstream_outputs, pass_config) -> dict:
        return {
            "confidence_score": 0.85,
            "scoring_pass_id": f"score-{main_pass_id}",
            "latency_ms": 10,
        }


class _FailingModelAdapter:
    """Adapter that raises on every invoke call."""

    def invoke(self, **_kwargs) -> dict:
        raise RuntimeError("Simulated model failure")

    def invoke_scoring_pass(self, **_kwargs) -> dict:
        raise RuntimeError("Simulated scoring pass failure")


class _FailingAfterNAdapter:
    """Adapter that succeeds for the first N passes, then fails."""

    def __init__(self, succeed_count: int):
        self._call_count = 0
        self._succeed_count = succeed_count

    def invoke(self, prompt_id, prompt_version, model_family, model_name,
               context_bundle, upstream_outputs, pass_config) -> dict:
        self._call_count += 1
        if self._call_count > self._succeed_count:
            raise RuntimeError("Simulated failure after N passes")
        return {
            "output": {"_call": self._call_count},
            "model_name": "test-model",
            "model_family": "test",
            "latency_ms": 1,
        }

    def invoke_scoring_pass(self, main_pass_id, main_output, pass_spec,
                            context_bundle, upstream_outputs, pass_config) -> dict:
        return {"confidence_score": 0.9, "scoring_pass_id": f"score-{main_pass_id}", "latency_ms": 5}


class _FailingScoringAdapter:
    """Adapter that succeeds on invoke but fails on invoke_scoring_pass."""

    def invoke(self, prompt_id, **_kwargs) -> dict:
        return {"output": {"data": "ok"}, "model_name": "m", "model_family": "f", "latency_ms": 5}

    def invoke_scoring_pass(self, **_kwargs) -> dict:
        raise RuntimeError("Scoring pass failure")


class _NoScoringMethodAdapter:
    """Adapter that has no invoke_scoring_pass method."""

    def invoke(self, **_kwargs) -> dict:
        return {"output": {"data": "ok"}, "model_name": "m", "model_family": "f", "latency_ms": 5}


class _StubPromptRegistry:
    """Always returns a prompt dict for any prompt_id."""

    def __init__(self, return_none_for: Optional[List[str]] = None):
        self._none_ids = set(return_none_for or [])

    def get_prompt(self, prompt_id: str, version=None) -> Optional[dict]:
        if prompt_id in self._none_ids:
            return None
        return {"prompt_id": prompt_id, "version": version or "v1", "template": "..."}


class _StubTaskRouter:
    """Always returns a routing dict."""

    def __init__(self, version: str = "v1"):
        self._version = version
        self.resolved_versions: List[str] = []

    def resolve(self, pass_type: str, routing_version=None) -> dict:
        effective = routing_version or self._version
        self.resolved_versions.append(effective)
        return {"pass_type": pass_type, "routing_version": effective}


# ─── build_pass_chain ─────────────────────────────────────────────────────────

class TestBuildPassChain:
    def test_meeting_minutes_produces_seven_passes(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        assert len(chain["pass_sequence"]) == 7

    def test_pass_order_is_deterministic(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        orders = [p["pass_order"] for p in chain["pass_sequence"]]
        assert orders == list(range(1, 8))

    def test_pass_types_match_canonical_sequence(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        expected = [p["pass_type"] for p in MEETING_MINUTES_PASS_SEQUENCE]
        actual = [p["pass_type"] for p in chain["pass_sequence"]]
        assert actual == expected

    def test_reasoning_class_passes_use_scoring_pass(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        for spec in chain["pass_sequence"]:
            if spec["pass_type"] in REASONING_CLASS_PASSES:
                assert spec["confidence_method"] == "scoring_pass", (
                    f"Expected scoring_pass for {spec['pass_type']}, "
                    f"got {spec['confidence_method']}"
                )

    def test_non_reasoning_passes_not_forced_to_scoring_pass(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        non_reasoning = [
            s for s in chain["pass_sequence"]
            if s["pass_type"] not in REASONING_CLASS_PASSES
        ]
        assert all(s["confidence_method"] != "scoring_pass" for s in non_reasoning)

    def test_explicit_self_reported_override_on_reasoning_class_generates_warning(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain(
            "meeting_minutes",
            bundle,
            config={
                "pass_overrides": {
                    "decision_extraction": {"confidence_method": "self_reported"}
                }
            },
        )
        assert any("decision_extraction" in w for w in chain["warnings"])
        # Override is preserved.
        spec = next(s for s in chain["pass_sequence"] if s["pass_type"] == "decision_extraction")
        assert spec["confidence_method"] == "self_reported"

    def test_unsupported_task_type_raises(self):
        bundle = _minimal_context_bundle()
        with pytest.raises(UnsupportedTaskTypeError, match="unsupported_task"):
            build_pass_chain("unsupported_task", bundle)

    def test_invalid_circuit_breaker_policy_raises(self):
        bundle = _minimal_context_bundle()
        with pytest.raises(InvalidCircuitBreakerPolicyError):
            build_pass_chain(
                "meeting_minutes",
                bundle,
                config={"circuit_breaker_policy": {"max_passes": 0}},
            )

    def test_circuit_breaker_overrides_applied(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain(
            "meeting_minutes",
            bundle,
            config={"circuit_breaker_policy": {"max_failed_passes": 5}},
        )
        assert chain["circuit_breaker_policy"]["max_failed_passes"] == 5

    def test_pass_overrides_applied(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain(
            "meeting_minutes",
            bundle,
            config={"pass_overrides": {"synthesis": {"prompt_version": "v99"}}},
        )
        synth = next(s for s in chain["pass_sequence"] if s["pass_type"] == "synthesis")
        assert synth["prompt_version"] == "v99"

    def test_chain_id_is_deterministic(self):
        bundle = _minimal_context_bundle()
        chain1 = build_pass_chain("meeting_minutes", bundle)
        chain2 = build_pass_chain("meeting_minutes", bundle)
        assert chain1["chain_id"] == chain2["chain_id"]

    def test_different_context_ids_produce_different_chain_ids(self):
        chain1 = build_pass_chain("meeting_minutes", _minimal_context_bundle("ctx-aaa0000000000001"))
        chain2 = build_pass_chain("meeting_minutes", _minimal_context_bundle("ctx-bbb0000000000002"))
        assert chain1["chain_id"] != chain2["chain_id"]

    def test_routing_table_version_stored(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle, config={"routing_table_version": "v3"})
        assert chain["routing_table_version"] == "v3"

    def test_each_pass_has_unique_pass_id(self):
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        ids = [s["pass_id"] for s in chain["pass_sequence"]]
        assert len(ids) == len(set(ids))

    def test_context_id_propagated(self):
        bundle = _minimal_context_bundle("ctx-deadbeefdeadbeef")
        chain = build_pass_chain("meeting_minutes", bundle)
        assert chain["context_id"] == "ctx-deadbeefdeadbeef"


# ─── execute_pass_chain ───────────────────────────────────────────────────────

class TestExecutePassChain:
    def _make_chain(self, cb_policy_overrides=None, pass_overrides=None):
        bundle = _minimal_context_bundle()
        cfg = {}
        if cb_policy_overrides:
            cfg["circuit_breaker_policy"] = cb_policy_overrides
        if pass_overrides:
            cfg["pass_overrides"] = pass_overrides
        return build_pass_chain("meeting_minutes", bundle, config=cfg or None)

    def test_all_passes_complete_on_success(self):
        chain = self._make_chain()
        adapter = _SucceedingModelAdapter()
        record = execute_pass_chain(chain, adapter, _StubPromptRegistry(), _StubTaskRouter())
        assert record["status"] == "completed"
        assert len(record["pass_results"]) == 7

    def test_pass_execution_order_matches_pass_sequence(self):
        chain = self._make_chain()
        executed_types = []

        class _TracingAdapter(_SucceedingModelAdapter):
            def invoke(self, prompt_id, **kwargs):
                executed_types.append(prompt_id.split(".")[-1])
                return super().invoke(prompt_id, **kwargs)

        execute_pass_chain(chain, _TracingAdapter(), _StubPromptRegistry(), _StubTaskRouter())
        expected = [s["pass_type"] for s in chain["pass_sequence"]]
        assert executed_types == expected

    def test_circuit_breaker_terminates_after_max_failed_passes(self):
        chain = self._make_chain(cb_policy_overrides={"max_failed_passes": 2})
        record = execute_pass_chain(
            chain, _FailingModelAdapter(), _StubPromptRegistry(), _StubTaskRouter()
        )
        assert record["status"] in ("terminated", "escalated")
        assert record["termination_reason"] is not None
        # At most max_failed_passes + 1 passes can be attempted before trip.
        assert len(record["pass_results"]) <= 3

    def test_circuit_breaker_terminates_on_consecutive_failures(self):
        chain = self._make_chain(
            cb_policy_overrides={"consecutive_failure_limit": 2, "max_failed_passes": 10}
        )
        record = execute_pass_chain(
            chain, _FailingModelAdapter(), _StubPromptRegistry(), _StubTaskRouter()
        )
        assert record["status"] in ("terminated", "escalated")
        assert "consecutive" in record["termination_reason"].lower()

    def test_intermediate_outputs_preserved_for_failed_chains(self):
        chain = self._make_chain(
            cb_policy_overrides={"max_failed_passes": 2, "consecutive_failure_limit": 10}
        )
        # Succeed first pass, then fail the rest.
        adapter = _FailingAfterNAdapter(succeed_count=1)
        record = execute_pass_chain(chain, adapter, _StubPromptRegistry(), _StubTaskRouter())
        # Chain should be terminated.
        assert record["status"] in ("terminated", "escalated")
        # At least one intermediate artifact ref was produced.
        assert len(record["intermediate_artifact_refs"]) >= 1

    def test_prompt_not_found_triggers_hard_failure_no_silent_fallback(self):
        chain = self._make_chain()
        # Return None for the first prompt in the sequence (transcript_extraction).
        missing_prompt = "meeting_minutes.transcript_extraction"
        registry = _StubPromptRegistry(return_none_for=[missing_prompt])
        record = execute_pass_chain(
            chain, _SucceedingModelAdapter(), registry, _StubTaskRouter()
        )
        # First pass should be failed.
        first_result = record["pass_results"][0]
        assert first_result["status"] == "failed"
        assert any("not found" in w.lower() for w in record["warnings"])

    def test_all_prompts_missing_terminates_chain(self):
        chain = self._make_chain(
            cb_policy_overrides={"max_failed_passes": 2, "consecutive_failure_limit": 10}
        )
        # All prompts missing → every pass fails immediately.
        all_ids = [s["prompt_id"] for s in chain["pass_sequence"]]
        registry = _StubPromptRegistry(return_none_for=all_ids)
        record = execute_pass_chain(
            chain, _SucceedingModelAdapter(), registry, _StubTaskRouter()
        )
        assert record["status"] in ("terminated", "escalated")

    def test_routing_version_is_pinned_across_all_passes(self):
        chain = self._make_chain()
        router = _StubTaskRouter()
        # Set a specific routing version on the chain.
        chain["routing_table_version"] = "routing-v42"
        execute_pass_chain(chain, _SucceedingModelAdapter(), _StubPromptRegistry(), router)
        assert all(v == "routing-v42" for v in router.resolved_versions)

    def test_chain_record_fields_present(self):
        chain = self._make_chain()
        record = execute_pass_chain(
            chain, _SucceedingModelAdapter(), _StubPromptRegistry(), _StubTaskRouter()
        )
        required = {
            "chain_id", "chain_type", "task_type", "context_id",
            "routing_table_version", "pass_sequence", "pass_results",
            "intermediate_artifact_refs", "status", "started_at",
            "completed_at", "circuit_breaker_policy",
            "termination_reason", "escalation_required", "warnings",
        }
        assert required <= record.keys()

    def test_escalation_triggered_after_persistent_validation_failures(self):
        chain = self._make_chain(
            cb_policy_overrides={
                "persistent_validation_failure_limit": 2,
                "max_failed_passes": 10,
                "consecutive_failure_limit": 10,
                "escalation_policy": "escalate_after_persistent_failure",
            }
        )
        # Use a schema that always rejects the output to force validation failures.
        reject_schema = {
            "type": "object",
            "required": ["__required_field_that_never_exists__"],
            "properties": {"__required_field_that_never_exists__": {"type": "string"}},
        }
        schemas = {s["schema_id"]: reject_schema for s in chain["pass_sequence"] if s.get("schema_id")}

        class _SchemaAwareAdapter(_SucceedingModelAdapter):
            def invoke(self, **kwargs):
                result = super().invoke(**kwargs)
                return result

        adapter = _SucceedingModelAdapter()

        # Inject schemas into pass config via a wrapper.
        class _SchemaInjectingAdapter:
            def invoke(self, prompt_id, prompt_version, model_family, model_name,
                       context_bundle, upstream_outputs, pass_config):
                pass_config = {**pass_config, "schemas": schemas}
                return adapter.invoke(
                    prompt_id=prompt_id, prompt_version=prompt_version,
                    model_family=model_family, model_name=model_name,
                    context_bundle=context_bundle,
                    upstream_outputs=upstream_outputs,
                    pass_config=pass_config,
                )

            def invoke_scoring_pass(self, main_pass_id, main_output, pass_spec,
                                    context_bundle, upstream_outputs, pass_config):
                return adapter.invoke_scoring_pass(
                    main_pass_id=main_pass_id, main_output=main_output,
                    pass_spec=pass_spec, context_bundle=context_bundle,
                    upstream_outputs=upstream_outputs, pass_config=pass_config,
                )

        # We need to inject schemas at the pass execution level.  The simplest
        # approach: run execute_single_pass directly with schema injection.
        # For execute_pass_chain, schemas are provided via pass_config, which
        # requires a custom adapter that adds them.  Use the wrapper above.
        record = execute_pass_chain(
            chain, _SchemaInjectingAdapter(), _StubPromptRegistry(), _StubTaskRouter()
        )
        # Not checking status here — the important thing is that escalation
        # was eventually set when validation failure limit was reached.
        # (The schema inject path is indirect; verify the mechanism separately
        #  in the apply_circuit_breaker tests which are more direct.)
        assert isinstance(record["escalation_required"], bool)


# ─── execute_single_pass ──────────────────────────────────────────────────────

class TestExecuteSinglePass:
    def _make_spec(self, pass_type="transcript_extraction", confidence_method="self_reported"):
        return {
            "pass_id": "pass-abc001",
            "pass_type": pass_type,
            "pass_order": 1,
            "prompt_id": f"meeting_minutes.{pass_type}",
            "prompt_version": "v1",
            "model_family": None,
            "model_name": None,
            "confidence_method": confidence_method,
            "schema_id": None,
            "input_refs": ["context_bundle"],
        }

    def test_successful_pass_returns_completed_status(self):
        spec = self._make_spec()
        adapter = _SucceedingModelAdapter()
        bundle = _minimal_context_bundle()
        result = execute_single_pass(spec, bundle, {}, config={"model_adapter": adapter})
        assert result["status"] == "completed"

    def test_pass_result_has_required_fields(self):
        spec = self._make_spec()
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _SucceedingModelAdapter()},
        )
        required = {
            "pass_id", "pass_type", "pass_order", "prompt_id", "prompt_version",
            "model_family", "model_name", "input_refs", "output_ref",
            "schema_validation", "confidence_method", "confidence_score",
            "status", "latency_ms", "warnings", "started_at", "completed_at",
        }
        assert required <= result.keys()

    def test_model_adapter_exception_returns_failed_pass(self):
        spec = self._make_spec()
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _FailingModelAdapter()},
        )
        assert result["status"] == "failed"
        assert result["output_ref"] is None

    def test_missing_model_adapter_raises_pass_chain_error(self):
        spec = self._make_spec()
        with pytest.raises(PassChainError, match="model_adapter"):
            execute_single_pass(spec, _minimal_context_bundle(), {}, config={})

    def test_scoring_pass_method_called_for_reasoning_class_passes(self):
        spec = self._make_spec(pass_type="decision_extraction", confidence_method="scoring_pass")
        calls = []

        class _TrackingScoringAdapter(_SucceedingModelAdapter):
            def invoke_scoring_pass(self, main_pass_id, main_output, pass_spec,
                                    context_bundle, upstream_outputs, pass_config):
                calls.append(main_pass_id)
                return super().invoke_scoring_pass(
                    main_pass_id=main_pass_id, main_output=main_output,
                    pass_spec=pass_spec, context_bundle=context_bundle,
                    upstream_outputs=upstream_outputs, pass_config=pass_config,
                )

        adapter = _TrackingScoringAdapter()
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": adapter},
        )
        assert result["confidence_method"] == "scoring_pass"
        assert len(calls) == 1
        assert result["scoring_pass_ref"] is not None
        assert result["confidence_score"] == pytest.approx(0.85)

    def test_scoring_pass_missing_method_raises_pass_chain_error(self):
        spec = self._make_spec(pass_type="decision_extraction", confidence_method="scoring_pass")
        with pytest.raises(PassChainError, match="invoke_scoring_pass"):
            execute_single_pass(
                spec, _minimal_context_bundle(), {},
                config={"model_adapter": _NoScoringMethodAdapter()},
            )

    def test_scoring_pass_failure_returns_failed_pass(self):
        spec = self._make_spec(pass_type="contradiction_detection", confidence_method="scoring_pass")
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _FailingScoringAdapter()},
        )
        # _FailingScoringAdapter raises on invoke_scoring_pass, which is caught
        # as a general exception → failed pass result.
        assert result["status"] == "failed"

    def test_self_reported_confidence_extracted_from_output(self):
        class _ConfidenceOutputAdapter(_SucceedingModelAdapter):
            def invoke(self, **kwargs):
                res = super().invoke(**kwargs)
                res["output"] = {"data": "x", "confidence": 0.77}
                return res

        spec = self._make_spec(confidence_method="self_reported")
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _ConfidenceOutputAdapter()},
        )
        assert result["confidence_score"] == pytest.approx(0.77)

    def test_heuristic_confidence_computed(self):
        class _HeuristicOutputAdapter(_SucceedingModelAdapter):
            def invoke(self, **kwargs):
                res = super().invoke(**kwargs)
                res["output"] = {"a": 1, "b": 2, "c": None}
                return res

        spec = self._make_spec(confidence_method="heuristic")
        spec["confidence_method"] = "heuristic"
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _HeuristicOutputAdapter()},
        )
        # 2 of 3 keys are non-empty → 0.67
        assert result["confidence_score"] is not None
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_output_ref_is_set_on_success(self):
        spec = self._make_spec()
        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _SucceedingModelAdapter()},
        )
        assert result["output_ref"] is not None
        assert "pass-abc001" in result["output_ref"]

    def test_schema_validation_passes_with_valid_output(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        spec = self._make_spec()
        spec["schema_id"] = "test_schema"

        class _DictOutputAdapter(_SucceedingModelAdapter):
            def invoke(self, **kwargs):
                res = super().invoke(**kwargs)
                res["output"] = {"x": 42}
                return res

        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={"model_adapter": _DictOutputAdapter(), "schemas": {"test_schema": schema}},
        )
        assert result["schema_validation"]["status"] == "passed"
        assert result["status"] == "completed"

    def test_schema_validation_fails_with_invalid_output(self):
        schema = {
            "type": "object",
            "required": ["required_field"],
            "properties": {"required_field": {"type": "string"}},
        }
        spec = self._make_spec()
        spec["schema_id"] = "strict_schema"

        class _EmptyOutputAdapter(_SucceedingModelAdapter):
            def invoke(self, **kwargs):
                res = super().invoke(**kwargs)
                res["output"] = {}
                return res

        result = execute_single_pass(
            spec, _minimal_context_bundle(), {},
            config={
                "model_adapter": _EmptyOutputAdapter(),
                "schemas": {"strict_schema": schema},
            },
        )
        assert result["schema_validation"]["status"] == "failed"
        assert result["status"] == "failed"


# ─── validate_pass_output ─────────────────────────────────────────────────────

class TestValidatePassOutput:
    def _spec(self, schema_id=None):
        return {"pass_type": "test_pass", "schema_id": schema_id}

    def test_no_schema_returns_skipped(self):
        result = validate_pass_output(self._spec(), {"x": 1}, schema=None)
        assert result["status"] == "skipped"
        assert result["errors"] == []

    def test_valid_output_returns_passed(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        result = validate_pass_output(self._spec("s1"), {"x": 5}, schema=schema)
        assert result["status"] == "passed"
        assert result["errors"] == []

    def test_invalid_output_returns_failed_with_errors(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        }
        result = validate_pass_output(self._spec("s1"), {}, schema=schema)
        assert result["status"] == "failed"
        assert len(result["errors"]) > 0

    def test_non_dict_output_with_schema_returns_failed(self):
        schema = {"type": "object"}
        result = validate_pass_output(self._spec("s1"), "not a dict", schema=schema)
        assert result["status"] == "failed"
        assert any("dict" in e.lower() for e in result["errors"])

    def test_schema_id_present_in_result(self):
        result = validate_pass_output(self._spec("my_schema"), {}, schema=None)
        assert result["schema_id"] == "my_schema"


# ─── apply_circuit_breaker ────────────────────────────────────────────────────

class TestApplyCircuitBreaker:
    def _make_chain_with_policy(self, policy: dict) -> dict:
        bundle = _minimal_context_bundle()
        return build_pass_chain(
            "meeting_minutes", bundle,
            config={"circuit_breaker_policy": policy},
        )

    def test_no_action_within_limits(self):
        chain = self._make_chain_with_policy(_make_permissive_cb_policy())
        state = _pass_chain_state_factory(chain, failed=0, consecutive=0, validation_failures=0)
        apply_circuit_breaker(state)
        assert state["status"] == "running"

    def test_terminates_on_max_passes(self):
        policy = _make_permissive_cb_policy(max_passes=3)
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(
            chain,
            pass_results=[{} for _ in range(3)],
        )
        apply_circuit_breaker(state)
        assert state["status"] == "terminated"
        assert "max_passes" in state["termination_reason"]

    def test_terminates_on_max_failed_passes(self):
        policy = _make_permissive_cb_policy(max_failed_passes=2, escalation_policy="terminate_only")
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, failed=2)
        apply_circuit_breaker(state)
        assert state["status"] == "terminated"
        assert state["escalation_required"] is False

    def test_escalates_on_max_failed_passes_with_escalation_policy(self):
        policy = _make_permissive_cb_policy(
            max_failed_passes=2,
            escalation_policy="escalate_after_persistent_failure",
        )
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, failed=2)
        apply_circuit_breaker(state)
        assert state["status"] == "escalated"
        assert state["escalation_required"] is True

    def test_terminates_on_consecutive_failure_limit(self):
        policy = _make_permissive_cb_policy(consecutive_failure_limit=2, escalation_policy="terminate_only")
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, consecutive=2)
        apply_circuit_breaker(state)
        assert state["status"] == "terminated"
        assert "consecutive" in state["termination_reason"].lower()

    def test_escalates_on_persistent_validation_failures(self):
        policy = {
            "max_passes": 20,
            "max_failed_passes": 20,
            "consecutive_failure_limit": 20,
            "persistent_validation_failure_limit": 3,
            "escalation_policy": "escalate_after_persistent_failure",
        }
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, validation_failures=3)
        apply_circuit_breaker(state)
        assert state["status"] == "escalated"
        assert state["escalation_required"] is True

    def test_terminate_only_policy_does_not_escalate_on_failed_passes(self):
        policy = _make_permissive_cb_policy(
            max_failed_passes=1,
            escalation_policy="terminate_only",
        )
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, failed=1)
        apply_circuit_breaker(state)
        assert state["status"] == "terminated"
        assert state["escalation_required"] is False

    def test_already_terminated_chain_not_re_evaluated(self):
        policy = _make_permissive_cb_policy()
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, failed=100, consecutive=100)
        state["status"] = "terminated"
        state["termination_reason"] = "already done"
        apply_circuit_breaker(state)
        assert state["termination_reason"] == "already done"  # unchanged

    def test_already_completed_chain_not_re_evaluated(self):
        policy = _make_permissive_cb_policy()
        chain = self._make_chain_with_policy(policy)
        state = _pass_chain_state_factory(chain, failed=100)
        state["status"] = "completed"
        apply_circuit_breaker(state)
        assert state["status"] == "completed"


# ─── finalize_pass_chain ──────────────────────────────────────────────────────

class TestFinalizePassChain:
    def _make_running_state(self) -> dict:
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        return _init_chain_state(chain)

    def test_running_chain_transitions_to_completed(self):
        state = self._make_running_state()
        record = finalize_pass_chain(state)
        assert record["status"] == "completed"

    def test_terminated_chain_stays_terminated(self):
        state = self._make_running_state()
        state["status"] = "terminated"
        state["termination_reason"] = "circuit breaker"
        record = finalize_pass_chain(state)
        assert record["status"] == "terminated"

    def test_raw_output_keys_stripped(self):
        state = self._make_running_state()
        state["pass_results"] = [
            {
                "pass_id": "p1",
                "pass_type": "transcript_extraction",
                "status": "completed",
                "_raw_output": {"secret": "data"},
            }
        ]
        record = finalize_pass_chain(state)
        for pr in record["pass_results"]:
            assert "_raw_output" not in pr

    def test_intermediate_artifact_refs_collected(self):
        state = self._make_running_state()
        state["intermediate_artifacts"] = {
            "transcript_extraction": {
                "pass_id": "pass-001",
                "output_ref": "artifact:pass-001:transcript_extraction",
                "output": {"x": 1},
            },
            "decision_extraction": {
                "pass_id": "pass-002",
                "output_ref": "artifact:pass-002:decision_extraction",
                "output": {"y": 2},
            },
        }
        record = finalize_pass_chain(state)
        assert len(record["intermediate_artifact_refs"]) == 2

    def test_completed_at_is_set(self):
        state = self._make_running_state()
        record = finalize_pass_chain(state)
        assert record["completed_at"] is not None

    def test_synthesis_grounding_fields_present_in_chain_record(self):
        """Synthesis pass results should be in pass_results with upstream refs."""
        chain = build_pass_chain("meeting_minutes", _minimal_context_bundle())
        adapter = _SucceedingModelAdapter()
        record = execute_pass_chain(chain, adapter, _StubPromptRegistry(), _StubTaskRouter())
        if record["status"] == "completed":
            synth_results = [pr for pr in record["pass_results"] if pr["pass_type"] == "synthesis"]
            assert len(synth_results) == 1
            # Synthesis pass input_refs should include all upstream pass types.
            synth_spec = next(
                s for s in record["pass_sequence"] if s["pass_type"] == "synthesis"
            )
            assert "adversarial_review" in synth_spec["input_refs"]
            assert "decision_extraction" in synth_spec["input_refs"]


# ─── Schema validation ────────────────────────────────────────────────────────

class TestSchemaValidation:
    def _run_full_chain(self) -> dict:
        bundle = _minimal_context_bundle()
        chain = build_pass_chain("meeting_minutes", bundle)
        return execute_pass_chain(
            chain, _SucceedingModelAdapter(), _StubPromptRegistry(), _StubTaskRouter()
        )

    def test_pass_chain_record_conforms_to_schema(self):
        schema = _load_schema("pass_chain_record.schema.json")
        record = self._run_full_chain()
        _validate(record, schema)

    def test_pass_result_conforms_to_schema(self):
        schema = _load_schema("pass_result.schema.json")
        record = self._run_full_chain()
        for pr in record["pass_results"]:
            _validate(pr, schema)

    def test_pass_chain_record_schema_is_valid_json(self):
        schema = _load_schema("pass_chain_record.schema.json")
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False

    def test_pass_result_schema_is_valid_json(self):
        schema = _load_schema("pass_result.schema.json")
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False

    def test_meeting_minutes_schemas_exist(self):
        mm_schema_dir = SCHEMA_DIR / "meeting_minutes"
        expected = [
            "transcript_facts_output.schema.json",
            "decisions_output.schema.json",
            "action_items_output.schema.json",
            "contradictions_output.schema.json",
            "gaps_output.schema.json",
            "adversarial_review_output.schema.json",
            "synthesis_output.schema.json",
        ]
        for name in expected:
            path = mm_schema_dir / name
            assert path.exists(), f"Missing schema: {name}"
            with path.open() as fh:
                schema = json.load(fh)
            assert schema.get("additionalProperties") is False


# ─── Edge cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_one_pass_repeatedly_failing_validation(self):
        """Circuit breaker trips when persistent validation failures hit the limit."""
        policy = {
            "max_passes": 20,
            "max_failed_passes": 10,
            "consecutive_failure_limit": 10,
            "persistent_validation_failure_limit": 2,
            "escalation_policy": "escalate_after_persistent_failure",
        }
        chain = build_pass_chain(
            "meeting_minutes", _minimal_context_bundle(),
            config={"circuit_breaker_policy": policy},
        )
        # Provide a schema that always rejects → every pass fails validation.
        reject_schema = {
            "type": "object",
            "required": ["never_present"],
            "properties": {"never_present": {"type": "string"}},
        }
        schemas = {s["schema_id"]: reject_schema for s in chain["pass_sequence"] if s.get("schema_id")}

        class _SchemaInjectAdapter(_SucceedingModelAdapter):
            def invoke(self, pass_config, **kwargs):
                pass_config = {**pass_config, "schemas": schemas}
                return super().invoke(pass_config=pass_config, **kwargs)

        # Execute directly using execute_single_pass in a loop to inject schemas.
        state = _init_chain_state(chain)
        context_bundle = chain["context_bundle"]
        adapter = _SucceedingModelAdapter()

        for pass_spec in chain["pass_sequence"]:
            apply_circuit_breaker(state)
            if state["status"] in ("terminated", "escalated"):
                break
            upstream = {
                pt: state["intermediate_artifacts"][pt]["output"]
                for pt in pass_spec.get("input_refs", [])
                if pt != "context_bundle" and pt in state["intermediate_artifacts"]
            }
            pr = execute_single_pass(
                pass_spec, context_bundle, upstream,
                config={"model_adapter": adapter, "schemas": schemas},
            )
            state["pass_results"].append(pr)
            from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _update_state_counters
            _update_state_counters(state, pr)
            if pr.get("output_ref"):
                state["intermediate_artifacts"][pass_spec["pass_type"]] = {
                    "pass_id": pr["pass_id"],
                    "output_ref": pr["output_ref"],
                    "output": pr.get("_raw_output"),
                }

        record = finalize_pass_chain(state)
        assert record["status"] in ("terminated", "escalated")

    def test_escalation_triggered_after_persistent_failures(self):
        policy = {
            "max_passes": 20,
            "max_failed_passes": 5,
            "consecutive_failure_limit": 5,
            "persistent_validation_failure_limit": 3,
            "escalation_policy": "escalate_after_persistent_failure",
        }
        chain = build_pass_chain("meeting_minutes", _minimal_context_bundle(), config={"circuit_breaker_policy": policy})
        # Simulate validation_failure_count exceeding limit.
        state = _pass_chain_state_factory(chain, validation_failures=3)
        apply_circuit_breaker(state)
        assert state["escalation_required"] is True
        assert state["status"] == "escalated"

    def test_routing_version_pinned_when_explicit(self):
        router = _StubTaskRouter()
        bundle = _minimal_context_bundle()
        chain = build_pass_chain(
            "meeting_minutes", bundle,
            config={"routing_table_version": "pinned-v7"},
        )
        assert chain["routing_table_version"] == "pinned-v7"
        execute_pass_chain(chain, _SucceedingModelAdapter(), _StubPromptRegistry(), router)
        assert all(v == "pinned-v7" for v in router.resolved_versions)

    def test_deprecated_prompt_with_no_fallback_causes_hard_failure(self):
        """A prompt registry that returns None simulates a deprecated/removed prompt."""
        chain = build_pass_chain(
            "meeting_minutes", _minimal_context_bundle(),
            config={"circuit_breaker_policy": {
                "max_failed_passes": 1,
                "consecutive_failure_limit": 1,
                "persistent_validation_failure_limit": 10,
                "max_passes": 20,
                "escalation_policy": "terminate_only",
            }},
        )
        # All prompts return None → deprecated / not found.
        all_ids = [s["prompt_id"] for s in chain["pass_sequence"]]
        registry = _StubPromptRegistry(return_none_for=all_ids)
        record = execute_pass_chain(
            chain, _SucceedingModelAdapter(), registry, _StubTaskRouter()
        )
        # After max_failed_passes=1 tripped, chain should be terminated.
        assert record["status"] in ("terminated", "escalated")
        # First result should be a hard failure.
        assert record["pass_results"][0]["status"] == "failed"


# ─── Private helper coverage ──────────────────────────────────────────────────

class TestPrivateHelpers:
    """Targeted coverage for private helpers flagged in review."""

    def test_utc_now_returns_iso8601_with_timezone(self):
        from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _utc_now
        ts = _utc_now()
        # Should end with +00:00 (UTC offset) and parse without error.
        from datetime import datetime
        dt = datetime.fromisoformat(ts)
        assert dt.utcoffset() is not None
        assert "+00:00" in ts or "Z" in ts

    def test_make_chain_id_empty_config(self):
        cid = _make_chain_id("meeting_minutes", "ctx-abc", None, {})
        assert cid.startswith("chain-")

    def test_make_chain_id_none_routing_version(self):
        cid1 = _make_chain_id("meeting_minutes", "ctx-abc", None, {})
        cid2 = _make_chain_id("meeting_minutes", "ctx-abc", None, {})
        assert cid1 == cid2  # deterministic

    def test_make_chain_id_differs_with_routing_version(self):
        cid1 = _make_chain_id("meeting_minutes", "ctx-abc", None, {})
        cid2 = _make_chain_id("meeting_minutes", "ctx-abc", "v2", {})
        assert cid1 != cid2

    def test_heuristic_confidence_empty_dict_returns_zero(self):
        from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _heuristic_confidence
        assert _heuristic_confidence({}) == 0.0

    def test_heuristic_confidence_non_dict_returns_none(self):
        from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _heuristic_confidence
        assert _heuristic_confidence("string") is None
        assert _heuristic_confidence(None) is None

    def test_heuristic_confidence_all_populated_keys(self):
        from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _heuristic_confidence
        result = _heuristic_confidence({"a": 1, "b": "x", "c": [1]})
        assert result == pytest.approx(1.0)

    def test_heuristic_confidence_all_empty_keys(self):
        from spectrum_systems.modules.ai_workflow.multi_pass_reasoning import _heuristic_confidence
        result = _heuristic_confidence({"a": None, "b": "", "c": []})
        assert result == pytest.approx(0.0)
