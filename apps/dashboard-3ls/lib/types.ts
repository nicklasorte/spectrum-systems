// DSH-03: Truth-first classifier surface.
// Every dashboard signal must declare exactly one of these provenance modes.
// - artifact_store: schema-validated artifact under artifacts/**
// - repo_registry:  canonical repo registry / source-of-truth files
// - derived:        computed from one or more present artifacts (no inference gaps)
// - derived_estimate: computed from partial artifacts (provisional truth mode)
// - stub_fallback:  placeholder used when no artifact is available
// - unknown:        provenance cannot be determined or is missing entirely
export type DataSource =
  | 'artifact_store'
  | 'repo_registry'
  | 'derived'
  | 'derived_estimate'
  | 'stub_fallback'
  | 'unknown';

export type SignalStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

export interface ArtifactEnvelope {
  data_source: DataSource;
  generated_at: string;
  source_artifacts_used: string[];
  warnings: string[];
}

// DSH-03: Shared signal contract. Every displayable dashboard signal must conform.
// `confidence` is bounded [0,1]; values < 1 imply provisional/derived semantics.
// `reason_codes` carry machine-readable cause tags so the UI can render
// non-decorative explanations without parsing free-text warnings.
export interface DashboardSignal<TValue = unknown> {
  signal_id: string;
  label: string;
  value: TValue | 'unknown';
  status: SignalStatus;
  data_source: DataSource;
  confidence: number;
  source_artifacts_used: string[];
  warnings: string[];
  reason_codes: string[];
  last_updated: string;
}

// MG-Kernel artifact types
export interface CheckpointSummary {
  artifact_type: string;
  run_id: string;
  status: string;
  checkpoints: Array<{
    umbrella: string;
    status: string;
    checkpoint_artifact: string;
    run_id: string;
  }>;
}

export interface RunSummary {
  artifact_type: string;
  run_id: string;
  status: string;
  manual_residue_steps: number;
}

export interface LiveTruthBundle {
  artifact_type: string;
  production_dashboard_truth_probe: {
    matches_artifact_truth: boolean;
    status: string;
    owner: string;
  };
  live_deploy_truth_verification: {
    repo_live_divergence: boolean;
    status: string;
    owner: string;
  };
  stability_score: {
    stability: number;
    bottleneck_persistence: number;
    owner: string;
  };
}

export interface RegistryCrossCheck {
  artifact_type: string;
  status: string;
  checks: Record<string, boolean>;
}

export interface LearningDebtBundle {
  artifact_type: string;
  governance_debt_register: {
    manual_residue_steps: number;
    prompt_residue_ratio: number;
    non_zero_when_manual_work_remains: boolean;
    owner: string;
  };
}

// Roadmap artifact types
export interface GapAnalysis {
  artifact_type: string;
  timestamp: string;
  dominant_bottleneck: {
    id: string;
    statement: string;
    evidence: string[];
  };
  highest_risk_trust_gap: {
    id: string;
    statement: string;
    evidence: string[];
  };
  gap_classes: Record<string, string[]>;
  top_risks: string[];
}

export interface RoadmapStep {
  id: string;
  what: string;
  why: string;
  dependencies: string[];
  trust_gain: string;
  failure_prevention: string;
  system_layer_impacted: string;
}

export interface RoadmapTable {
  artifact_type: string;
  timestamp: string;
  step_count: number;
  steps: RoadmapStep[];
  not_to_build: string[];
}

export interface DomainState {
  status: string;
  evidence: string[];
}

export interface SystemState {
  artifact_type: string;
  timestamp: string;
  authority_precheck: {
    status: string;
    missing_required_paths: string[];
    missing_source_files: string[];
    missing_structured_artifacts: string[];
    digest_mismatches: string[];
    authority_gaps: string[];
  };
  domain_state: Record<string, DomainState>;
  repo_reality: {
    implemented_modules: unknown[];
    schema_backed_components: Array<{
      system_id: string;
      system: string;
      schema_files: string[];
    }>;
    test_backed_systems: Array<{
      system_id: string;
      system: string;
      evidence: string;
    }>;
    docs_only_systems: Array<{
      system_id: string;
      system: string;
      evidence: string;
    }>;
    dead_or_unused_surfaces: Array<{
      path: string;
      status: string;
      reason: string;
      file_count: number;
    }>;
  };
}

export interface Provenance {
  artifact_type: string;
  timestamp: string;
  mode: string;
  deterministic_ordering: boolean;
  input_hashes: Array<{ path: string; sha256: string }>;
  validation: {
    authority_precheck_valid: boolean;
    required_fields_present: boolean;
    step_count_exactly_24: boolean;
  };
  notes: string;
}

export interface RepoSnapshot {
  generated_at: string;
  freshness_timestamp_utc: string;
  repo_name: string;
  root_counts: {
    files_total: number;
    runtime_modules: number;
    tests: number;
    contracts_total: number;
    schemas: number;
    examples: number;
    docs: number;
    run_artifacts: number;
  };
  operational_signals: Array<{
    title: string;
    status: string;
    detail: string;
  }>;
  key_state: {
    current_run_state_record: {
      status: string;
      batch_id: string;
      generated_at: string;
      outcomes: string[];
    };
    current_bottleneck_record: {
      bottleneck_name: string;
      evidence: string[];
      impacted_layers: string[];
    };
    hard_gate_status_record: {
      pass_fail: string;
      signals: string[];
    };
  };
}
