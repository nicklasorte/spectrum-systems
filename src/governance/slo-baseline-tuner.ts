import { Pool } from "pg";

/**
 * SLO Baseline Tuner
 * Analyzes real SLI measurements, recommends SLO targets
 */

export interface PercentileAnalysis {
  sli_name: string;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
  mean: number;
  stddev: number;
}

export interface SLORecommendation {
  sli_name: string;
  current_target: number;
  recommended_target: number;
  confidence: "low" | "medium" | "high";
  reasoning: string;
  sample_count: number;
}

export class SLOBaselineTuner {
  private pool: Pool;

  constructor(pool: Pool) {
    this.pool = pool;
  }

  async analyzeSLIPercentiles(
    sliName: string,
    windowDays: number = 7
  ): Promise<PercentileAnalysis> {
    const result = await this.pool.query(
      `SELECT
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY value) as p75,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) as p90,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99,
        AVG(value) as mean,
        STDDEV(value) as stddev,
        COUNT(*) as sample_count
       FROM sli_measurements
       WHERE sli_name = $1 AND timestamp > NOW() - INTERVAL '1 day' * $2`,
      [sliName, windowDays]
    );

    const row = result.rows[0];
    return {
      sli_name: sliName,
      p50: parseFloat(row.p50),
      p75: parseFloat(row.p75),
      p90: parseFloat(row.p90),
      p95: parseFloat(row.p95),
      p99: parseFloat(row.p99),
      mean: parseFloat(row.mean),
      stddev: parseFloat(row.stddev),
    };
  }

  async recommendSLOTargets(
    windowDays: number = 7
  ): Promise<SLORecommendation[]> {
    const sliNames = [
      "eval_pass_rate",
      "cost_per_run",
      "drift_rate",
      "reproducibility_score",
      "trace_coverage",
    ];

    const recommendations: SLORecommendation[] = [];

    for (const sliName of sliNames) {
      const analysis = await this.analyzeSLIPercentiles(sliName, windowDays);

      let recommendedTarget: number;
      let reasoning: string;
      let confidence: "low" | "medium" | "high" = "medium";

      // Different SLIs have different recommendation strategies
      if (sliName === "eval_pass_rate") {
        recommendedTarget = analysis.p75; // stretch goal
        reasoning = `Current mean ${analysis.mean.toFixed(1)}%. Recommend p75 (${recommendedTarget.toFixed(1)}%) as stretch target.`;
      } else if (sliName === "cost_per_run") {
        recommendedTarget = analysis.p90; // cost-conscious
        reasoning = `Current mean ${analysis.mean.toFixed(1)} cents. Recommend p90 (${recommendedTarget.toFixed(1)}) for cost control.`;
      } else if (sliName === "drift_rate") {
        recommendedTarget = analysis.p50; // stability baseline
        reasoning = `Current mean ${analysis.mean.toFixed(2)}% per day. Recommend p50 (${recommendedTarget.toFixed(2)}%) as stability baseline.`;
      } else if (sliName === "reproducibility_score") {
        recommendedTarget = analysis.p95; // high bar for trust
        reasoning = `Current mean ${analysis.mean.toFixed(1)}%. Recommend p95 (${recommendedTarget.toFixed(1)}%) for high reproducibility.`;
      } else {
        recommendedTarget = analysis.p90; // default
        reasoning = `Current mean ${analysis.mean.toFixed(1)}%. Recommend p90 (${recommendedTarget.toFixed(1)}%).`;
      }

      if (analysis.stddev < analysis.mean * 0.1) {
        confidence = "high"; // low variance = high confidence
      }

      recommendations.push({
        sli_name: sliName,
        current_target: analysis.p50, // placeholder
        recommended_target: recommendedTarget,
        confidence,
        reasoning,
        sample_count: 0, // would populate from query
      });
    }

    return recommendations;
  }
}
