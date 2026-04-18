export interface DraftEvalGateResult {
  success: boolean;
  eval_results?: any[];
  eval_summary?: any;
  control_decision?: any;
  execution_record?: any;
  error?: string;
}
