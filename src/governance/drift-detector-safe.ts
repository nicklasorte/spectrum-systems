import { Pool } from "pg";

/**
 * Safe drift detection fixes
 */

export async function getSliceMetricsInBatch(
  pool: Pool,
  sliceIds: string[]
): Promise<Record<string, number>> {
  if (sliceIds.length === 0) return {};

  const placeholders = sliceIds.map((_, i) => `$${i + 1}`).join(",");
  const result = await pool.query(
    `SELECT slice_id, AVG(value) as avg_value
     FROM sli_measurements
     WHERE slice_id IN (${placeholders})
     GROUP BY slice_id`,
    sliceIds
  );

  const metricsBySlice: Record<string, number> = {};
  for (const row of result.rows) {
    metricsBySlice[row.slice_id] = row.avg_value;
  }

  return metricsBySlice;
}

export async function expireResolvedDriftSignals(pool: Pool): Promise<void> {
  await pool.query(
    `UPDATE drift_signals
     SET status = 'resolved'
     WHERE status = 'active'
     AND triggered_at < NOW() - INTERVAL '7 days'`
  );
}

export function tailorDriftRecommendations(driftType: string): string[] {
  const recommendations: Record<string, string[]> = {
    decision_divergence: [
      "Review outcome logic for inconsistency",
      "Check if policy changed recently",
      "Audit reviewer behavior for calibration drift",
    ],
    metric_distribution: [
      "Investigate upstream changes (model, policy, context)",
      "Compare to baseline metrics from last 30 days",
      "Check if new eval cases were added",
    ],
    exception_accumulation: [
      "Convert frequent exceptions into policy",
      "Retire unused exceptions",
      "Schedule policy review",
    ],
    trace_loss: [
      "Check trace context propagation in MVPs",
      "Verify all artifact creation includes trace_id",
      "Audit recent code changes to span handling",
    ],
  };

  return recommendations[driftType] || ["Review drift signal and take action"];
}
