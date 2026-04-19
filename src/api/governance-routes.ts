import express, { Router } from "express";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

/**
 * Governance API Routes
 * Provides endpoints for dashboard and control loop
 */

export function createGovernanceRouter(pool: Pool): Router {
  const router = express.Router();

  // SLI Status
  router.get("/sli-status", async (req, res) => {
    try {
      const result = await pool.query(
        `SELECT 'eval_pass_rate' as sli_name, 0.95 as current_value, 0.90 as target_value,
                '% pass' as unit, 'healthy' as status, 'stable' as trend
         UNION ALL
         SELECT 'cost_per_run', 0.85, 0.75, '$/run', 'warning', 'up'
         UNION ALL
         SELECT 'eval_latency_p95', 1.2, 1.5, 's', 'healthy', 'down'
         UNION ALL
         SELECT 'policy_coverage', 0.88, 0.85, '% of flows', 'healthy', 'up'
         UNION ALL
         SELECT 'exception_backlog', 3.0, 10.0, 'active', 'healthy', 'stable'`
      );
      res.json(result.rows);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Drift Signals
  router.get("/drift-signals", async (req, res) => {
    try {
      const signals = [
        {
          artifact_id: uuidv4(),
          drift_type: "metric_distribution",
          current_value: 105.2,
          baseline_value: 100.0,
          recommendations: [
            "Investigate upstream model changes",
            "Check policy rollout percentage",
            "Compare to historical patterns",
          ],
        },
        {
          artifact_id: uuidv4(),
          drift_type: "entropy_vector_context",
          current_value: 0.42,
          baseline_value: 0.38,
          recommendations: [
            "Review context bundle version",
            "Check input data distribution",
          ],
        },
      ];
      res.json(signals);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Exception Backlog
  router.get("/exceptions/backlog", async (req, res) => {
    try {
      const backlog = {
        total_active: 3,
        overdue: 0,
        unconverted: 1,
        status: "healthy",
      };
      res.json(backlog);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Policies
  router.get("/policies", async (req, res) => {
    try {
      const policies = [
        {
          policy_name: "fast_track_approval",
          status: "active",
          rollout_percentage: 75,
          incidents_since_deployment: 0,
        },
        {
          policy_name: "enhanced_context_weighting",
          status: "active",
          rollout_percentage: 100,
          incidents_since_deployment: 1,
        },
      ];
      res.json(policies);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Lineage - Root Causes
  router.get("/lineage/root-causes/:artifactId", async (req, res) => {
    try {
      const roots = [
        {
          artifact_id: uuidv4(),
          artifact_kind: "policy_change",
          distance: 1,
        },
      ];
      res.json(roots);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Lineage - Impact
  router.get("/lineage/impact/:artifactId", async (req, res) => {
    try {
      const impacted = [
        {
          artifact_id: uuidv4(),
          artifact_kind: "eval_result",
          relationship: "caused_by",
        },
      ];
      res.json(impacted);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Control Signals
  router.get("/control-signals", async (req, res) => {
    try {
      const signals = [
        {
          signal_type: "drift_signal",
          severity: "warning",
          context: "metric_distribution shift detected",
          linked_playbook: "drift_metric_distribution",
        },
      ];
      res.json(signals);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // Escalation History
  router.get("/escalations", async (req, res) => {
    try {
      const limit = req.query.limit ? parseInt(req.query.limit as string) : 50;
      const escalations = [];
      res.json(escalations);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  return router;
}
