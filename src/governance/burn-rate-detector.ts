import { v4 as uuidv4 } from "uuid";
import type { BurnRateAlert, SLODefinition } from "./sli-types";
import { SLIBackend } from "./sli-backend";

/**
 * Burn-Rate Detector
 * Monitors SLI trends with hysteresis and grace period
 * No decisions made here — only alert generation
 */

export class BurnRateDetector {
  private sliBackend: SLIBackend;
  private gracePeriodBuffer: Map<string, number> = new Map();
  private HYSTERESIS_THRESHOLD = 3;

  constructor(sliBackend: SLIBackend) {
    this.sliBackend = sliBackend;
  }

  async detectAndAlert(
    slo: SLODefinition,
    sliName: string
  ): Promise<BurnRateAlert | null> {
    const burnRate = await this.sliBackend.calculateBurnRate(sliName, 24);
    const errorBudgetPercentage = slo.error_budget_percentage;
    const sustainableBurnRate = errorBudgetPercentage / slo.window_days;

    let alertLevel: "warn" | "freeze" | "block" | null = null;

    if (burnRate > sustainableBurnRate * 2) alertLevel = "warn";
    if (burnRate > sustainableBurnRate * 5) alertLevel = "freeze";
    if (burnRate > sustainableBurnRate * 10) alertLevel = "block";

    if (!alertLevel) {
      this.gracePeriodBuffer.delete(slo.artifact_id);
      return null;
    }

    const consecutiveCount = (this.gracePeriodBuffer.get(slo.artifact_id) || 0) + 1;
    this.gracePeriodBuffer.set(slo.artifact_id, consecutiveCount);

    if (consecutiveCount < this.HYSTERESIS_THRESHOLD) {
      return null;
    }

    const alert: BurnRateAlert = {
      artifact_kind: "burn_rate_alert",
      artifact_id: uuidv4(),
      slo_id: slo.artifact_id,
      sli_name: sliName,
      current_burn_rate: burnRate,
      threshold_burn_rate: sustainableBurnRate,
      alert_level: alertLevel,
      triggered_at: new Date().toISOString(),
      window_hours: 24,
      context: `Burn rate ${burnRate.toFixed(2)}% per day exceeds sustainable ${sustainableBurnRate.toFixed(2)}%`,
    };

    await this.sliBackend.recordBurnRateAlert(
      slo.artifact_id,
      sliName,
      burnRate,
      sustainableBurnRate,
      alertLevel,
      24,
      alert.context
    );

    this.gracePeriodBuffer.delete(slo.artifact_id);
    return alert;
  }
}
