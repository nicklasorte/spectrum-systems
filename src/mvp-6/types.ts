/**
 * Type definitions for MVP-6: Extraction Eval Gate
 */

export interface ExtractionEvalGateResult {
  success: boolean;
  eval_results?: any[];
  eval_summary?: any;
  control_decision?: any;
  execution_record?: any;
  error?: string;
}
