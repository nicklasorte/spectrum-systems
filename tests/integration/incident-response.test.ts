import { FailureCaptureEngine } from "@/src/incident-response/failure-capture";
import { Pool } from "pg";

describe("Incident Response", () => {
  let engine: FailureCaptureEngine;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });
    engine = new FailureCaptureEngine(pool);
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should capture failure with full context", async () => {
    const capture = await engine.captureFailure(
      "run-123",
      "MVP-3",
      "eval_pass_rate below threshold",
      ["transcript-1", "context-2", "eval-3"],
      { eval_pass_rate: 82 },
      [{ signal_type: "sli_alert", severity: "block" }]
    );

    expect(capture.failure_id).toBeDefined();
    expect(capture.recommended_action).toContain("eval");
  });

  it("should identify frequent failure patterns", async () => {
    const patterns = await engine.getFrequentFailures(5);
    expect(Array.isArray(patterns)).toBe(true);
  });

  it("should generate postmortem template", async () => {
    const failure = {
      failure_id: "f-1",
      run_id: "r-1",
      mvp_name: "MVP-3",
      failure_reason: "Eval gate failed",
      captured_at: new Date().toISOString(),
      lineage_trace: ["t1", "t2"],
      sli_snapshot: { eval_pass_rate: 80 },
      control_signals: [],
      recommended_action: "rerun_evals",
    };

    const postmortem = await engine.createPostmortemTemplate(failure);
    expect(postmortem).toContain("Postmortem");
    expect(postmortem).toContain("MVP-3");
  });
});
