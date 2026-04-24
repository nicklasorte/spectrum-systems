/**
 * Type definitions for MVP-2: Context Bundle Assembly
 */

export interface ContextItem {
  item_index: number;
  item_id: string;
  item_type:
    | "primary_input"
    | "policy_constraints"
    | "retrieved_context"
    | "prior_artifact"
    | "glossary_definition"
    | "unresolved_question";
  trust_level: "high" | "medium" | "low" | "untrusted";
  source_classification: "internal" | "external" | "inferred" | "user_provided";
  provenance_ref: string;
  provenance_refs: string[];
  content: any;
}

export interface ContextBundlePayload {
  artifact_type: "context_bundle";
  schema_version: "2.3.0";
  context_bundle_id: string;
  context_id: string;
  task_type: string;
  created_at: string;
  trace: {
    trace_id: string;
    run_id: string;
  };
  context_items: ContextItem[];
  source_segmentation: {
    classification_order: string[];
    classification_counts: {
      internal: number;
      external: number;
      inferred: number;
      user_provided: number;
    };
    item_refs_by_class: {
      internal: string[];
      external: string[];
      inferred: string[];
      user_provided: string[];
    };
    grounded_item_refs: string[];
    inferred_item_refs: string[];
  };
  primary_input: Record<string, any>;
  policy_constraints: Record<string, any> | string;
  retrieved_context: any[];
  prior_artifacts: any[];
  glossary_terms: any[];
  glossary_definitions: any[];
  glossary_canonicalization: {
    injection_enabled: boolean;
    match_mode: "exact";
    selection_mode: "explicit_then_exact_text";
    fail_on_missing_required: boolean;
    selected_glossary_entry_ids: string[];
    unresolved_terms: string[];
  };
  unresolved_questions: any[];
  metadata: {
    assembly_manifest_hash: string;
    input_artifact_ids: string[];
  };
  token_estimates: {
    primary_input: number;
    policy_constraints: number;
    prior_artifacts: number;
    retrieved_context: number;
    glossary_terms: number;
    glossary_definitions: number;
    unresolved_questions: number;
    total: number;
  };
  truncation_log: any[];
  priority_order: string[];
}

export interface ContextBundleAssemblyResult {
  success: boolean;
  context_bundle?: ContextBundlePayload;
  execution_record?: any;
  error?: string;
  error_codes?: string[];
}
