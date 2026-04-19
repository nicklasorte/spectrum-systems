import { ControlLoopEvaluator } from "@/src/governance/control-loop-decision";
import { Pool } from "pg";
import { v4 as uuidv4 } from "uuid";

describe("Control Loop Decision (Strict Governance)", () => {
  let evaluator: ControlLoopEvaluator;
  let pool: Pool;

  beforeAll(async () => {
    pool = new Pool({
      host: "localhost",
      database: "spectrum_test",
    });

    evaluator = new ControlLoopEvaluator(pool);
    await evaluator.initialize();
  });

  afterAll(async () => {
    await pool.end();
  });

  it("should evaluate artifact and return decision (read-only)", async () => {
    const decision = await evaluator.evaluateArtifact(
      uuidv4(),
      uuidv4(),
      "1.0",
      uuidv4()
    );

    // Returns decision artifact
    expect(decision.artifact_kind).toBe("control_loop_decision");
    expect(["allow", "warn", "freeze", "block"]).toContain(decision.decision);
  });

  it("should fail-closed on missing eval summary", async () => {
    const decision = await evaluator.evaluateArtifact(
      uuidv4(),
      uuidv4(),
      "1.0",
      uuidv4()
    );

    // No eval → block (fail-closed)
    expect(decision.decision).toBe("block");
    expect(decision.reason_codes).toContain("missing_eval_summary");
  });

  it("should NEVER create enforcement actions in code", async () => {
    // This test ensures we never call createEnforcementAction
    // All enforcement is external (CI/orchestration)

    const methods = Object.getOwnPropertyNames(
      Object.getPrototypeOf(evaluator)
    );

    // createEnforcementAction should NOT exist
    expect(methods).not.toContain("createEnforcementAction");
  });

  it("should allow CI to query decisions", async () => {
    // CI can query pending decisions
    const decisions = await evaluator.getDecisions(undefined, 10);
    expect(Array.isArray(decisions)).toBe(true);
  });

  it("should allow CI to query blocking decisions", async () => {
    // CI can query block/freeze decisions for prioritization
    const blocking = await evaluator.getBlockingDecisions(10);
    expect(Array.isArray(blocking)).toBe(true);
  });

  it("should not have enforcement_action creation", async () => {
    // Verify there's no method for creating enforcement actions
    // All enforcement is external
    const evaluatorMethods = Object.getOwnPropertyNames(
      Object.getPrototypeOf(evaluator)
    ).join(",");

    expect(evaluatorMethods).not.toContain("createEnforcement");
    expect(evaluatorMethods).not.toContain("recordEnforcement");
    expect(evaluatorMethods).not.toContain("approveEnforcement");
    expect(evaluatorMethods).not.toContain("markEnforcementActionExecuted");
  });
});
