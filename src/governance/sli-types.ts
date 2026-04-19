import { v4 as uuidv4 } from "uuid";

/**
 * SLI Type Definitions
 * Service Level Indicators for governance
 * Source: Agent Eval Integration, AI Operating Substrate
 */

export interface SLITarget {
  sli_name: string;
  unit: string;
  description: string;
  lower_bound?: number;
  upper_bound?: number;
  direction: "higher_is_better" | "lower_is_better";
}

export interface SLODefinition {
  artifact_kind: "slo_definition";
  artifact_id: string;
  slo_name: string;
  sli_name: string;
  target_value: number;
  window_days: number;
  error_budget_percentage: number;
  grace_period_minutes: number;
  created_at: string;
  owner: string;
  supersedes?: string;
}

export interface SLIMeasurement {
  artifact_kind: "sli_measurement";
  artifact_id: string;
  sli_name: string;
  run_id: string;
  timestamp: string;
  value: number;
  dimensions: Record<string, string>;
  trace_id: string;
}

export interface BurnRateAlert {
  artifact_kind: "burn_rate_alert";
  artifact_id: string;
  slo_id: string;
  sli_name: string;
  current_burn_rate: number;
  threshold_burn_rate: number;
  alert_level: "warn" | "freeze" | "block";
  triggered_at: string;
  window_hours: number;
  context: string;
}

export const DEFAULT_SLI_TARGETS: SLITarget[] = [
  {
    sli_name: "eval_pass_rate",
    unit: "percentage",
    description: "Percentage of eval cases passing",
    lower_bound: 0,
    upper_bound: 100,
    direction: "higher_is_better",
  },
  {
    sli_name: "drift_rate",
    unit: "percentage_per_day",
    description: "Daily change in failure rate",
    lower_bound: -100,
    upper_bound: 100,
    direction: "lower_is_better",
  },
  {
    sli_name: "reproducibility_score",
    unit: "percentage",
    description: "Replay match rate",
    lower_bound: 0,
    upper_bound: 100,
    direction: "higher_is_better",
  },
  {
    sli_name: "cost_per_run",
    unit: "cents",
    description: "Cost in USD cents per pipeline run",
    lower_bound: 0,
    direction: "lower_is_better",
  },
  {
    sli_name: "trace_coverage",
    unit: "percentage",
    description: "Percentage of runs with complete trace IDs",
    lower_bound: 0,
    upper_bound: 100,
    direction: "higher_is_better",
  },
];

export const DEFAULT_SLOS: Omit<SLODefinition, "artifact_id" | "created_at">[] = [
  {
    artifact_kind: "slo_definition",
    slo_name: "eval_reliability",
    sli_name: "eval_pass_rate",
    target_value: 99.0,
    window_days: 7,
    error_budget_percentage: 1.0,
    grace_period_minutes: 60,
    owner: "governance-team",
  },
  {
    artifact_kind: "slo_definition",
    slo_name: "stability",
    sli_name: "drift_rate",
    target_value: 0.5,
    window_days: 7,
    error_budget_percentage: 2.0,
    grace_period_minutes: 120,
    owner: "governance-team",
  },
  {
    artifact_kind: "slo_definition",
    slo_name: "trust",
    sli_name: "reproducibility_score",
    target_value: 95.0,
    window_days: 7,
    error_budget_percentage: 5.0,
    grace_period_minutes: 180,
    owner: "governance-team",
  },
  {
    artifact_kind: "slo_definition",
    slo_name: "cost_control",
    sli_name: "cost_per_run",
    target_value: 500,
    window_days: 7,
    error_budget_percentage: 10.0,
    grace_period_minutes: 30,
    owner: "governance-team",
  },
  {
    artifact_kind: "slo_definition",
    slo_name: "observability",
    sli_name: "trace_coverage",
    target_value: 95.0,
    window_days: 7,
    error_budget_percentage: 5.0,
    grace_period_minutes: 60,
    owner: "governance-team",
  },
];
