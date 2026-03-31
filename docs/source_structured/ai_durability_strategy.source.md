# AI Durability Strategy — Structured Source Artifact

## Purpose
Repo-native structured source seed for RE-01 source authority indexing.

## machine_source_document
```json
{
  "source_id": "SRC-AI-DURABILITY-STRATEGY",
  "title": "AI Durability Strategy",
  "path": "docs/source_structured/ai_durability_strategy.source.md",
  "status": "active"
}
```

## machine_obligations
```json
[
  {
    "obligation_id": "OBL-AIDUR-ARTIFACT-SOR",
    "component_id": "COMP-ARTIFACT-AUTHORITY",
    "category": "artifact_authority",
    "description": "Treat governed artifacts as the system of record for decisions, handoffs, and lifecycle state.",
    "layer": "governance",
    "required_artifacts": ["governed_artifact", "artifact_envelope"],
    "required_gates": ["schema_validation_gate"],
    "status": "planned",
    "source_section": "core_principles"
  },
  {
    "obligation_id": "OBL-AIDUR-MODEL-REPLACEABLE",
    "component_id": "COMP-MODEL-ADAPTER",
    "category": "architecture_boundary",
    "description": "Constrain models to replaceable execution engines behind stable contract and adapter boundaries.",
    "layer": "architecture",
    "required_artifacts": ["adapter_contract", "execution_trace"],
    "required_gates": ["adapter_conformance_gate"],
    "status": "planned",
    "source_section": "replaceable_execution"
  },
  {
    "obligation_id": "OBL-AIDUR-SCHEMA-BEFORE-CONSUME",
    "component_id": "COMP-DOWNSTREAM-CONSUMPTION",
    "category": "validation_gate",
    "description": "Block downstream consumption when required schema validation is absent or fails.",
    "layer": "enforcement",
    "required_artifacts": ["schema_reference", "validated_payload"],
    "required_gates": ["schema_validation_gate", "fail_closed_gate"],
    "status": "planned",
    "source_section": "contract_enforcement"
  },
  {
    "obligation_id": "OBL-AIDUR-LINEAGE-BEFORE-PROMOTION",
    "component_id": "COMP-PROMOTION-CONTROL",
    "category": "lineage",
    "description": "Deny promotion when lineage evidence is missing, incomplete, or unverifiable.",
    "layer": "promotion",
    "required_artifacts": ["lineage_record", "certification_bundle"],
    "required_gates": ["lineage_integrity_gate", "promotion_gate"],
    "status": "planned",
    "source_section": "promotion_controls"
  },
  {
    "obligation_id": "OBL-AIDUR-CONTROL-EXTERNALIZED",
    "component_id": "COMP-CONTROL-AUTHORITY",
    "category": "authority_boundary",
    "description": "Keep control authority external to model execution and require explicit governed control decisions.",
    "layer": "control",
    "required_artifacts": ["control_decision", "policy_snapshot"],
    "required_gates": ["control_decision_gate"],
    "status": "planned",
    "source_section": "control_authority"
  },
  {
    "obligation_id": "OBL-AIDUR-EVAL-POLICY-BEFORE-PROMOTION",
    "component_id": "COMP-EVAL-POLICY-GATING",
    "category": "promotion_gating",
    "description": "Require evaluation and policy gates to pass before any promotion action is eligible.",
    "layer": "promotion",
    "required_artifacts": ["eval_result", "policy_decision"],
    "required_gates": ["eval_gate", "policy_gate", "promotion_gate"],
    "status": "planned",
    "source_section": "promotion_controls"
  },
  {
    "obligation_id": "OBL-AIDUR-FAIL-CLOSED-MISSING-EVIDENCE",
    "component_id": "COMP-FAIL-CLOSED-ENFORCEMENT",
    "category": "fail_closed",
    "description": "Fail closed when schema, trace, or policy evidence is missing at decision time.",
    "layer": "enforcement",
    "required_artifacts": ["schema_reference", "trace_record", "policy_decision"],
    "required_gates": ["fail_closed_gate"],
    "status": "planned",
    "source_section": "fail_closed_requirements"
  },
  {
    "obligation_id": "OBL-AIDUR-MEASURABLE-PROMOTION-ROLLOUT",
    "component_id": "COMP-ROLLOUT-GOVERNANCE",
    "category": "rollout_control",
    "description": "Gate promotion and rollout through measurable thresholds and explicit rollout policy states.",
    "layer": "operations",
    "required_artifacts": ["rollout_plan", "metric_thresholds", "promotion_decision"],
    "required_gates": ["readiness_gate", "rollout_gate"],
    "status": "planned",
    "source_section": "rollout_governance"
  },
  {
    "obligation_id": "OBL-AIDUR-LEARNING-PREVENTION-CLOSURE",
    "component_id": "COMP-LEARNING-LOOP",
    "category": "learning_prevention",
    "description": "Require learning-loop outputs to include recurrence prevention actions linked to prior failures.",
    "layer": "learning",
    "required_artifacts": ["failure_analysis", "prevention_action", "policy_update"],
    "required_gates": ["recurrence_prevention_gate"],
    "status": "planned",
    "source_section": "learning_and_prevention"
  }
]
```
