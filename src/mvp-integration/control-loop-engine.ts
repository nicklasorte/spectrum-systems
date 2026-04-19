import { Pool } from "pg";
import { SLIBackend } from "@/src/governance/sli-backend";
import { DriftDetector } from "@/src/governance/drift-detector";
import { PlaybookRegistry } from "@/src/governance/playbook-registry";

/**
 * Control Loop Engine
 * Queries governance state, makes allow/warn/freeze/block decisions
 */

export interface ControlSignal {
  signal_type: string;
  severity: "info" | "warn" | "freeze" | "block";
  context: string;
  linked_playbook?: string;
}

export class ControlLoopEngine {
  private sliBackend: SLIBackend;
  private driftDetector: DriftDetector;
  private playbookRegistry: PlaybookRegistry;

  constructor(
    sliBackend: SLIBackend,
    driftDetector: DriftDetector,
    playbookRegistry: PlaybookRegistry
  ) {
    this.sliBackend = sliBackend;
    this.driftDetector = driftDetector;
    this.playbookRegistry = playbookRegistry;
  }

  /**
   * Check all control signals for a given SLI
   * Returns list of signals that should affect promotion decision
   */
  async checkControlSignals(sliName: string): Promise<ControlSignal[]> {
    const signals: ControlSignal[] = [];

    // Check SLI burn-rate alerts
    const alerts = await this.sliBackend.getActiveAlerts(50);
    for (const alert of alerts) {
      if (alert.sli_name === sliName) {
        signals.push({
          signal_type: "sli_burn_rate",
          severity: alert.alert_level === "block" ? "block" : "warn",
          context: `Burn rate ${alert.current_burn_rate.toFixed(1)}x (threshold ${alert.threshold_burn_rate.toFixed(1)}x)`,
        });
      }
    }

    // Check drift signals
    const driftSignals = await this.driftDetector.getActiveDriftSignals(50);
    for (const drift of driftSignals) {
      signals.push({
        signal_type: "drift_detected",
        severity: "warn",
        context: `${drift.drift_type} shift ${drift.current_value.toFixed(2)}`,
      });
    }

    return signals;
  }

  /**
   * Make promotion decision based on all signals
   */
  async decidePromotion(
    artifactId: string,
    sliMeasurements: Record<string, number>
  ): Promise<{ allowed: boolean; reason: string; signals: ControlSignal[] }> {
    const signals = await this.checkControlSignals("eval_pass_rate");

    // Simple rule: allow if no severe signals
    const hasCritical = signals.some((s) => s.severity === "block");
    const hasFreeze = signals.some((s) => s.severity === "freeze");

    if (hasCritical) {
      return {
        allowed: false,
        reason: "BLOCK: critical control signal",
        signals,
      };
    }

    if (hasFreeze) {
      return {
        allowed: false,
        reason: "FREEZE: governance signal requires manual review",
        signals,
      };
    }

    return {
      allowed: true,
      reason: "All control checks passed",
      signals,
    };
  }
}
